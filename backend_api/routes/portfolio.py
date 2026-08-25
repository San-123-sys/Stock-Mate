from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from backend_api.core.config import settings
from backend_api.core.security import get_current_user
from backend_api.database.token_store import (
    get_all_baskets,
    get_cached_fundamentals,
    get_cached_news,
    get_cached_sector,
    get_ranked_basket,
    get_stale_or_missing_sectors,
    is_fundamentals_stale_or_missing,
    is_news_stale_or_missing,
    upsert_fundamentals_cache,
    upsert_news_cache,
    upsert_ranked_basket,
    upsert_sector_cache,
)
from backend_api.models.schemas import VixSnapshot
from backend_api.models.schemas import (
    BenchmarkPoint,
    BenchmarkResponse,
    HoldingMover,
    IndexSnapshot,
    MarketOverviewResponse,
    NewsArticle,
    NewsDigestResponse,
    PortfolioSummaryResponse,
    SectorAllocationResponse,
    SectorSlice,
    StockFinancialsResponse,
    StockFundamentals,
    SymbolNews,
    ThemedBasket,
    ThemedBasketsResponse,
)
from backend_api.services.broker_token_service import broker_token_service
from backend_api.services.market_data_service import market_data_service
from backend_api.services.sentiment_service import analyze_sentiment_batch
from backend_api.services.zerodha_service import zerodha_service
from backend_api.services.upstox_service import upstox_service

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

VALID_PERIODS = {"1M", "3M", "6M", "1Y"}
SECTOR_CONCENTRATION_THRESHOLD_PCT = 40.0
DEFAULT_NEWS_SYMBOLS = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"]

_PROVIDERS = ("zerodha", "upstox")
_PROVIDER_SERVICES = {"zerodha": zerodha_service, "upstox": upstox_service}


def _get_live_holdings(user_id: str) -> tuple[list[dict] | None, dict]:
    """
    Shared helper: fetch and merge live holdings from every broker linked
    for this user. Returns (holdings_or_None, short_circuit_fields). If
    holdings is None, short_circuit_fields contains
    linked/data_status/action_required/link_endpoint/message to return
    directly from the caller. Each holding dict is tagged with "_source"
    ("zerodha" or "upstox") so downstream consumers can badge/attribute it.
    """
    merged: list[dict] = []
    any_linked = False
    last_meta: dict = {}

    for provider in _PROVIDERS:
        if not broker_token_service.has_linked_account(user_id=user_id, provider=provider):
            continue
        any_linked = True

        tokens = broker_token_service.get_linked_tokens(user_id=user_id, provider=provider)
        if not tokens or not tokens.get("access_token"):
            last_meta = {
                "linked": True,
                "data_status": "token_missing",
                "action_required": "relink_broker",
                "link_endpoint": f"/api/{provider}/start",
                "message": f"{provider.capitalize()} linked, but token is unavailable. Reconnect {provider.capitalize()}.",
            }
            continue

        service = _PROVIDER_SERVICES[provider]
        try:
            holdings = service.fetch_holdings(access_token=tokens.get("access_token", ""))
        except Exception as exc:
            if service.is_relink_required_error(exc):
                last_meta = {
                    "linked": True,
                    "data_status": "relink_required",
                    "action_required": "relink_broker",
                    "link_endpoint": f"/api/{provider}/start",
                    "message": f"{provider.capitalize()} token expired or invalid. Reconnect {provider.capitalize()}.",
                }
            else:
                last_meta = {
                    "linked": True,
                    "data_status": "broker_api_unavailable",
                    "message": f"{provider.capitalize()} linked, but live portfolio fetch is temporarily unavailable: {exc}",
                }
            continue

        for holding in holdings:
            holding["_source"] = provider
        merged.extend(holdings)

    if not any_linked:
        return None, {
            "linked": False,
            "data_status": "not_linked",
            "action_required": "link_broker",
            "link_endpoint": "/api/zerodha/start",
            "message": "Broker not linked. Start Zerodha or Upstox linking flow.",
        }

    if not merged:
        return None, last_meta or {
            "linked": True,
            "data_status": "broker_api_unavailable",
            "message": "Broker linked, but live portfolio fetch is temporarily unavailable.",
        }

    return merged, {}


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _aggregate_holdings(holdings: list[dict]) -> dict:
    total_current_value = 0.0
    total_invested = 0.0

    for item in holdings:
        quantity = _to_float(item.get("quantity"), default=0.0)
        average_price = _to_float(item.get("average_price"), default=0.0)
        last_price = _to_float(item.get("last_price"), default=0.0)

        total_current_value += quantity * last_price
        total_invested += quantity * average_price

    total_pnl = total_current_value - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100.0) if total_invested > 0 else 0.0

    return {
        "holdings_count": len(holdings),
        "total_invested": round(total_invested, 2),
        "total_current_value": round(total_current_value, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
    }


def _sector_count_and_beta(holdings: list[dict]) -> tuple[int, float | None]:
    """Best-effort sector count + value-weighted average beta from cached/fetched fundamentals. Never raises."""
    try:
        symbols = sorted({
            (item.get("tradingsymbol") or item.get("symbol"))
            for item in holdings
            if (item.get("tradingsymbol") or item.get("symbol"))
        })
        if not symbols:
            return 0, None

        stale = get_stale_or_missing_sectors(symbols=symbols, max_age_days=7)
        for symbol in stale:
            sector = market_data_service.fetch_sector(symbol)
            upsert_sector_cache(symbol=symbol, sector=sector)

        sectors: set[str] = set()
        for symbol in symbols:
            cached = get_cached_sector(symbol=symbol)
            sector = (cached.get("sector") if cached else None) or "Other"
            sectors.add(sector)

        beta_by_symbol: dict[str, float] = {}
        for symbol in symbols:
            if is_fundamentals_stale_or_missing(symbol=symbol):
                data = market_data_service.fetch_fundamentals(symbol)
                upsert_fundamentals_cache(symbol=symbol, data=data)
            cached = get_cached_fundamentals(symbol=symbol)
            data = cached.get("data") if cached else None
            beta = data.get("beta") if data else None
            if beta is not None:
                beta_by_symbol[symbol] = float(beta)

        weighted_sum = 0.0
        weight_total = 0.0
        for item in holdings:
            symbol = item.get("tradingsymbol") or item.get("symbol")
            if not symbol or symbol not in beta_by_symbol:
                continue
            quantity = _to_float(item.get("quantity"), default=0.0)
            last_price = _to_float(item.get("last_price"), default=0.0)
            value = quantity * last_price
            weighted_sum += value * beta_by_symbol[symbol]
            weight_total += value

        portfolio_beta = (weighted_sum / weight_total) if weight_total > 0 else None
        return len(sectors), portfolio_beta
    except Exception:
        return 0, None


def _compute_health_score(holdings: list[dict], aggregate: dict) -> tuple[float | None, float | None]:
    try:
        from llm_orchestrator.utils.portfolio_analytics import build_portfolio_analytics
        sector_count, portfolio_beta = _sector_count_and_beta(holdings)
        analytics = build_portfolio_analytics(
            holdings=holdings,
            total_invested=aggregate["total_invested"],
            total_current_value=aggregate["total_current_value"],
            total_pnl=aggregate["total_pnl"],
            total_pnl_pct=aggregate["total_pnl_pct"],
            sector_count=sector_count,
            portfolio_beta=portfolio_beta,
        )
        health = analytics.get("portfolio_health", {})
        return health.get("score"), analytics.get("portfolio_beta")
    except Exception:
        return None, None


@router.get("/summary")
def portfolio_summary(current_user: dict = Depends(get_current_user)) -> PortfolioSummaryResponse:
    user_id = str(current_user.get("sub"))

    holdings, short_circuit = _get_live_holdings(user_id)
    if holdings is None:
        return PortfolioSummaryResponse(user_id=user_id, **short_circuit)

    aggregate = _aggregate_holdings(holdings)
    health_score, portfolio_beta = _compute_health_score(holdings, aggregate)
    return PortfolioSummaryResponse(
        user_id=user_id,
        linked=True,
        data_status="live",
        message="Live portfolio summary.",
        holdings=holdings,
        health_score=health_score,
        portfolio_beta=portfolio_beta,
        **aggregate,
    )



@router.get("/verify-broker")
def verify_broker_link(
    current_user: dict = Depends(get_current_user),
    account_id: str | None = Query(default=None),
) -> dict:
    user_id = str(current_user.get("sub"))
    tokens = broker_token_service.get_linked_tokens(
        user_id=user_id,
        provider="zerodha",
        account_id=account_id,
    )
    if not tokens:
        raise HTTPException(status_code=404, detail="No linked Zerodha account for user")

    access_token = tokens.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Missing access token for linked broker account")

    try:
        profile = zerodha_service.fetch_profile(access_token=access_token)
        holdings = zerodha_service.fetch_holdings(access_token=access_token)
    except Exception as exc:
        if zerodha_service.is_relink_required_error(exc):
            return {
                "linked": False,
                "action_required": "relink_broker",
                "link_endpoint": "/api/zerodha/start",
                "message": "Broker token expired or invalid. Reconnect Zerodha.",
                "error": str(exc),
            }
        return {
            "linked": True,
            "broker": "zerodha",
            "selected_account_id": tokens.get("account_id"),
            "is_primary": tokens.get("is_primary", False),
            "data_status": "broker_api_unavailable",
            "message": "Broker linked, but live verification is temporarily unavailable.",
            "error": str(exc),
        }

    sample = holdings[:5]
    return {
        "linked": True,
        "broker": "zerodha",
        "selected_account_id": tokens.get("account_id"),
        "is_primary": tokens.get("is_primary", False),
        "profile": {
            "user_id": profile.get("user_id"),
            "user_name": profile.get("user_name"),
            "email": profile.get("email"),
            "broker": profile.get("broker"),
        },
        "holdings_count": len(holdings),
        "holdings_preview": sample,
    }


@router.get("/benchmark")
def portfolio_benchmark(
    current_user: dict = Depends(get_current_user),
    period: str = Query(default="1M"),
) -> BenchmarkResponse:
    user_id = str(current_user.get("sub"))
    period = period.upper() if period.upper() in VALID_PERIODS else "1M"

    holdings, short_circuit = _get_live_holdings(user_id)
    if holdings is None:
        return BenchmarkResponse(user_id=user_id, period=period, **short_circuit)

    if not holdings:
        return BenchmarkResponse(
            user_id=user_id,
            linked=True,
            period=period,
            data_status="no_holdings",
            message="No holdings found to benchmark.",
        )

    try:
        nifty_series = market_data_service.fetch_index_close_series("^NSEI", period)
        if not nifty_series:
            return BenchmarkResponse(
                user_id=user_id,
                linked=True,
                period=period,
                data_status="market_data_unavailable",
                message="NIFTY 50 market data is temporarily unavailable.",
            )

        holding_series: list[tuple[float, dict[str, float]]] = []
        for item in holdings:
            symbol = item.get("tradingsymbol") or item.get("symbol")
            if not symbol:
                continue
            quantity = _to_float(item.get("quantity"), default=0.0)
            if quantity <= 0:
                continue
            close_series = market_data_service.fetch_close_series(symbol, period)
            if close_series:
                holding_series.append((quantity, close_series))

        if not holding_series:
            return BenchmarkResponse(
                user_id=user_id,
                linked=True,
                period=period,
                data_status="market_data_unavailable",
                message="Historical price data is temporarily unavailable for your holdings.",
            )

        dates = sorted(nifty_series.keys())

        last_known: dict[int, float] = {}
        portfolio_values: dict[str, float] = {}
        for date in dates:
            total = 0.0
            has_any = False
            for idx, (quantity, close_series) in enumerate(holding_series):
                price = close_series.get(date)
                if price is not None:
                    last_known[idx] = price
                price_to_use = last_known.get(idx)
                if price_to_use is not None:
                    total += quantity * price_to_use
                    has_any = True
            if has_any:
                portfolio_values[date] = total

        common_dates = [d for d in dates if d in portfolio_values]
        if not common_dates:
            return BenchmarkResponse(
                user_id=user_id,
                linked=True,
                period=period,
                data_status="market_data_unavailable",
                message="Could not align portfolio and market data.",
            )

        base_portfolio = portfolio_values[common_dates[0]]
        base_nifty = nifty_series[common_dates[0]]

        points = [
            BenchmarkPoint(
                date=date,
                portfolio_index=round((portfolio_values[date] / base_portfolio) * 100.0, 2) if base_portfolio else 0.0,
                nifty_index=round((nifty_series[date] / base_nifty) * 100.0, 2) if base_nifty else 0.0,
            )
            for date in common_dates
        ]

        aggregate = _aggregate_holdings(holdings)
        total_invested = aggregate["total_invested"]
        total_current_value = aggregate["total_current_value"]
        nifty_equivalent_value = None
        nifty_equivalent_diff = None
        if base_nifty and total_invested > 0:
            last_nifty = nifty_series[common_dates[-1]]
            nifty_equivalent_value = round(total_invested * (last_nifty / base_nifty), 2)
            nifty_equivalent_diff = round(nifty_equivalent_value - total_current_value, 2)

        return BenchmarkResponse(
            user_id=user_id,
            linked=True,
            period=period,
            data_status="live",
            message="Benchmark computed from current holdings against historical prices.",
            points=points,
            nifty_equivalent_value=nifty_equivalent_value,
            nifty_equivalent_diff=nifty_equivalent_diff,
        )
    except Exception as exc:
        return BenchmarkResponse(
            user_id=user_id,
            linked=True,
            period=period,
            data_status="market_data_unavailable",
            message=f"Benchmark computation is temporarily unavailable: {exc}",
        )


@router.get("/sector-allocation")
def portfolio_sector_allocation(
    current_user: dict = Depends(get_current_user),
) -> SectorAllocationResponse:
    user_id = str(current_user.get("sub"))

    holdings, short_circuit = _get_live_holdings(user_id)
    if holdings is None:
        return SectorAllocationResponse(user_id=user_id, **short_circuit)

    if not holdings:
        return SectorAllocationResponse(
            user_id=user_id,
            linked=True,
            data_status="no_holdings",
            message="No holdings found to analyze.",
        )

    try:
        symbols = sorted({
            (item.get("tradingsymbol") or item.get("symbol"))
            for item in holdings
            if (item.get("tradingsymbol") or item.get("symbol"))
        })

        stale = get_stale_or_missing_sectors(symbols=symbols, max_age_days=7)
        for symbol in stale:
            sector = market_data_service.fetch_sector(symbol)
            upsert_sector_cache(symbol=symbol, sector=sector)

        sector_by_symbol: dict[str, str] = {}
        for symbol in symbols:
            cached = get_cached_sector(symbol=symbol)
            sector_by_symbol[symbol] = (cached.get("sector") if cached else None) or "Other"

        sector_totals: dict[str, float] = {}
        total_value = 0.0
        for item in holdings:
            symbol = item.get("tradingsymbol") or item.get("symbol")
            if not symbol:
                continue
            quantity = _to_float(item.get("quantity"), default=0.0)
            last_price = _to_float(item.get("last_price"), default=0.0)
            value = quantity * last_price
            sector = sector_by_symbol.get(symbol, "Other")
            sector_totals[sector] = sector_totals.get(sector, 0.0) + value
            total_value += value

        if total_value <= 0:
            return SectorAllocationResponse(
                user_id=user_id,
                linked=True,
                data_status="no_holdings",
                message="No portfolio value to analyze.",
            )

        slices = [
            SectorSlice(sector=sector, value=round(value, 2), pct=round(value / total_value * 100.0, 2))
            for sector, value in sorted(sector_totals.items(), key=lambda kv: kv[1], reverse=True)
        ]

        over_concentrated = False
        over_sector = None
        over_pct = None
        if slices and slices[0].pct > SECTOR_CONCENTRATION_THRESHOLD_PCT:
            over_concentrated = True
            over_sector = slices[0].sector
            over_pct = slices[0].pct

        return SectorAllocationResponse(
            user_id=user_id,
            linked=True,
            data_status="live",
            message="Sector allocation computed from live holdings.",
            slices=slices,
            over_concentrated=over_concentrated,
            over_concentrated_sector=over_sector,
            over_concentrated_pct=over_pct,
        )
    except Exception as exc:
        return SectorAllocationResponse(
            user_id=user_id,
            linked=True,
            data_status="sector_data_unavailable",
            message=f"Sector allocation is temporarily unavailable: {exc}",
        )


@router.get("/stock/{symbol}")
def stock_financials(
    symbol: str,
    current_user: dict = Depends(get_current_user),
) -> StockFinancialsResponse:
    user_id = str(current_user.get("sub"))
    symbol = symbol.strip().upper()

    holdings, _short_circuit = _get_live_holdings(user_id)
    holding = None
    if holdings:
        for item in holdings:
            item_symbol = (item.get("tradingsymbol") or item.get("symbol") or "").upper()
            if item_symbol == symbol:
                holding = item
                break

    try:
        if is_fundamentals_stale_or_missing(symbol=symbol):
            data = market_data_service.fetch_fundamentals(symbol)
            upsert_fundamentals_cache(symbol=symbol, data=data)

        cached = get_cached_fundamentals(symbol=symbol)
        data = cached.get("data") if cached else None

        if not data:
            return StockFinancialsResponse(
                linked=holdings is not None,
                data_status="market_data_unavailable",
                message=f"Fundamentals for {symbol} are temporarily unavailable.",
                symbol=symbol,
                holding=holding,
            )

        return StockFinancialsResponse(
            linked=holdings is not None,
            data_status="live",
            message="Fundamentals loaded.",
            symbol=symbol,
            holding=holding,
            fundamentals=StockFundamentals(symbol=symbol, **data),
        )
    except Exception as exc:
        return StockFinancialsResponse(
            linked=holdings is not None,
            data_status="market_data_unavailable",
            message=f"Fundamentals fetch is temporarily unavailable: {exc}",
            symbol=symbol,
            holding=holding,
        )


@router.get("/market-overview")
def market_overview(current_user: dict = Depends(get_current_user)) -> MarketOverviewResponse:
    user_id = str(current_user.get("sub"))

    try:
        index_defs = [("^NSEI", "NIFTY 50"), ("^BSESN", "SENSEX")]
        indices = []
        for ticker_symbol, label in index_defs:
            snapshot = market_data_service.fetch_index_snapshot(ticker_symbol, label)
            if snapshot:
                indices.append(IndexSnapshot(**snapshot))

        vix = None
        vix_snapshot = market_data_service.get_india_vix()
        if vix_snapshot:
            vix_value = vix_snapshot["price"]
            if vix_value < 13:
                sentiment = "Extreme Greed"
            elif vix_value < 16:
                sentiment = "Greed"
            elif vix_value < 20:
                sentiment = "Neutral"
            elif vix_value < 25:
                sentiment = "Fear"
            else:
                sentiment = "Extreme Fear"
            vix = VixSnapshot(value=vix_value, sentiment=sentiment)

        holdings, _short_circuit = _get_live_holdings(user_id)
        movers: list[HoldingMover] = []
        if holdings:
            for item in holdings:
                symbol = item.get("tradingsymbol") or item.get("symbol")
                if not symbol:
                    continue
                quantity = _to_float(item.get("quantity"), default=0.0)
                average_price = _to_float(item.get("average_price"), default=0.0)
                last_price = _to_float(item.get("last_price"), default=0.0)
                if average_price <= 0:
                    continue
                change_pct = (last_price - average_price) / average_price * 100.0
                movers.append(
                    HoldingMover(
                        symbol=symbol,
                        change_pct=round(change_pct, 2),
                        current_value=round(quantity * last_price, 2),
                    )
                )

        movers_sorted = sorted(movers, key=lambda m: m.change_pct, reverse=True)
        top_gainers = [m for m in movers_sorted if m.change_pct > 0][:5]
        top_losers = sorted(
            [m for m in movers_sorted if m.change_pct < 0], key=lambda m: m.change_pct
        )[:5]

        if not indices:
            return MarketOverviewResponse(
                linked=holdings is not None,
                data_status="market_data_unavailable",
                message="Market index data is temporarily unavailable.",
                top_gainers=top_gainers,
                top_losers=top_losers,
                vix=vix,
            )

        return MarketOverviewResponse(
            linked=holdings is not None,
            data_status="live",
            message="Market overview loaded.",
            indices=indices,
            top_gainers=top_gainers,
            top_losers=top_losers,
            vix=vix,
        )
    except Exception as exc:
        return MarketOverviewResponse(
            linked=False,
            data_status="market_data_unavailable",
            message=f"Market overview is temporarily unavailable: {exc}",
        )


@router.get("/news")
def news_digest(current_user: dict = Depends(get_current_user)) -> NewsDigestResponse:
    user_id = str(current_user.get("sub"))

    try:
        holdings, _short_circuit = _get_live_holdings(user_id)

        if holdings:
            ranked = sorted(
                holdings,
                key=lambda item: _to_float(item.get("quantity"), default=0.0)
                * _to_float(item.get("last_price"), default=0.0),
                reverse=True,
            )
            symbols = []
            for item in ranked:
                symbol = (item.get("tradingsymbol") or item.get("symbol") or "").upper()
                if symbol and symbol not in symbols:
                    symbols.append(symbol)
                if len(symbols) >= 8:
                    break
        else:
            symbols = DEFAULT_NEWS_SYMBOLS

        items: list[SymbolNews] = []
        for symbol in symbols:
            if is_news_stale_or_missing(symbol=symbol):
                data = market_data_service.fetch_news(symbol)
                if data:
                    scores = analyze_sentiment_batch([article["title"] for article in data])
                    for article, score in zip(data, scores):
                        if score:
                            article["sentiment_label"] = score["label"]
                            article["sentiment_score"] = score["score"]
                upsert_news_cache(symbol=symbol, data=data)

            cached = get_cached_news(symbol=symbol)
            articles = cached.get("data") if cached else None
            if not articles:
                continue

            if settings.hf_api_token and any(a.get("sentiment_label") is None for a in articles):
                scores = analyze_sentiment_batch([a["title"] for a in articles])
                for article, score in zip(articles, scores):
                    if score:
                        article["sentiment_label"] = score["label"]
                        article["sentiment_score"] = score["score"]
                upsert_news_cache(symbol=symbol, data=articles)

            items.append(
                SymbolNews(
                    symbol=symbol,
                    articles=[NewsArticle(**article) for article in articles],
                )
            )

        if not items:
            return NewsDigestResponse(
                linked=holdings is not None,
                data_status="market_data_unavailable",
                message="News headlines are temporarily unavailable.",
            )

        return NewsDigestResponse(
            linked=holdings is not None,
            data_status="live",
            message="News digest loaded.",
            items=items,
        )
    except Exception as exc:
        return NewsDigestResponse(
            linked=False,
            data_status="market_data_unavailable",
            message=f"News digest is temporarily unavailable: {exc}",
        )


@router.get("/baskets")
def themed_baskets(current_user: dict = Depends(get_current_user)) -> ThemedBasketsResponse:
    user_id = str(current_user.get("sub"))

    try:
        holdings, _short_circuit = _get_live_holdings(user_id)

        held_symbols: set[str] = set()
        if holdings:
            for item in holdings:
                symbol = (item.get("tradingsymbol") or item.get("symbol") or "").upper()
                if symbol:
                    held_symbols.add(symbol)

        baskets = []
        for basket in get_all_baskets():
            theme = basket["theme"]
            description = basket["description"]
            original_symbols = basket["symbols"]

            # Check for cached ranked symbols (1 day refresh)
            ranked_symbols = get_ranked_basket(theme=theme)

            if ranked_symbols is None:
                # Not cached or stale; rank by performance
                ranked_symbols = market_data_service.rank_stocks_by_performance(
                    symbols=original_symbols,
                    max_stocks=5
                )
                # Cache the ranked symbols
                upsert_ranked_basket(theme=theme, ranked_symbols=ranked_symbols)

            held = [s for s in ranked_symbols if s.upper() in held_symbols]

            baskets.append(
                ThemedBasket(
                    theme=theme,
                    description=description,
                    symbols=ranked_symbols,
                    held_symbols=held,
                )
            )

        return ThemedBasketsResponse(
            linked=holdings is not None,
            data_status="live",
            message="Themed baskets loaded with top performers.",
            baskets=baskets,
        )
    except Exception as exc:
        return ThemedBasketsResponse(
            linked=False,
            data_status="unavailable",
            message=f"Themed baskets are temporarily unavailable: {exc}",
        )
