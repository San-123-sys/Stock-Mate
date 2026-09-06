from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    import yfinance as yf
    _HAS_YFINANCE = True
except Exception:
    yf = None
    _HAS_YFINANCE = False

PERIOD_MAP = {
    "1M": "1mo",
    "3M": "3mo",
    "6M": "6mo",
    "1Y": "1y",
}


class MarketDataService:
    def resolve_period(self, period: str) -> str:
        return PERIOD_MAP.get(period.upper(), "1mo")

    def _history_for_symbol(self, base_symbol: str, yf_period: str):
        if not _HAS_YFINANCE:
            return None

        for suffix in (".NS", ".BO"):
            try:
                ticker = yf.Ticker(f"{base_symbol}{suffix}")
                hist = ticker.history(period=yf_period)
                if hist is not None and not hist.empty:
                    return hist
            except Exception as exc:
                logger.warning("yfinance history fetch failed for %s%s: %s", base_symbol, suffix, exc)
        return None

    def fetch_close_series(self, base_symbol: str, period: str) -> dict[str, float]:
        """Returns {"YYYY-MM-DD": close_price} for the given base symbol (no suffix), or {} on failure."""
        yf_period = self.resolve_period(period)
        hist = self._history_for_symbol(base_symbol, yf_period)
        if hist is None:
            return {}

        try:
            series = {}
            for ts, row in hist.iterrows():
                date_key = ts.strftime("%Y-%m-%d")
                close = row.get("Close")
                if close is not None:
                    series[date_key] = float(close)
            return series
        except Exception as exc:
            logger.warning("Failed to parse close series for %s: %s", base_symbol, exc)
            return {}

    def fetch_close_history(self, base_symbol: str, years: int = 3) -> dict[str, float]:
        """
        Longer daily close history than fetch_close_series (which caps at 1Y),
        for portfolio optimization. Returns {"YYYY-MM-DD": close} or {} on failure.
        """
        yf_period = "5y" if years > 2 else "2y"
        hist = self._history_for_symbol(base_symbol, yf_period)
        if hist is None:
            return {}
        try:
            series: dict[str, float] = {}
            for ts, row in hist.iterrows():
                close = row.get("Close")
                if close is not None:
                    series[ts.strftime("%Y-%m-%d")] = float(close)
            return series
        except Exception as exc:
            logger.warning("Failed to parse close history for %s: %s", base_symbol, exc)
            return {}

    def fetch_index_close_series(self, ticker_symbol: str, period: str) -> dict[str, float]:
        """For index/raw tickers that already include their own symbol format (e.g. ^NSEI)."""
        if not _HAS_YFINANCE:
            return {}

        yf_period = self.resolve_period(period)
        try:
            ticker = yf.Ticker(ticker_symbol)
            hist = ticker.history(period=yf_period)
            if hist is None or hist.empty:
                return {}
            series = {}
            for ts, row in hist.iterrows():
                date_key = ts.strftime("%Y-%m-%d")
                close = row.get("Close")
                if close is not None:
                    series[date_key] = float(close)
            return series
        except Exception as exc:
            logger.warning("yfinance history fetch failed for %s: %s", ticker_symbol, exc)
            return {}

    def fetch_sector(self, base_symbol: str) -> str | None:
        if not _HAS_YFINANCE:
            return None

        for suffix in (".NS", ".BO"):
            try:
                ticker = yf.Ticker(f"{base_symbol}{suffix}")
                info = ticker.info
                sector = info.get("sector") if isinstance(info, dict) else None
                if sector:
                    return sector
            except Exception as exc:
                logger.warning("yfinance sector fetch failed for %s%s: %s", base_symbol, suffix, exc)
        return None

    def fetch_fundamentals(self, base_symbol: str) -> dict | None:
        if not _HAS_YFINANCE:
            return None

        for suffix in (".NS", ".BO"):
            try:
                ticker = yf.Ticker(f"{base_symbol}{suffix}")
                info = ticker.info
                if not isinstance(info, dict) or not info:
                    continue
                return {
                    "long_name": info.get("longName"),
                    "sector": info.get("sector"),
                    "market_cap": info.get("marketCap"),
                    "pe_ratio": info.get("trailingPE"),
                    "forward_pe": info.get("forwardPE"),
                    "dividend_yield": info.get("dividendYield"),
                    "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                    "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
                    "beta": info.get("beta"),
                    "currency": info.get("currency"),
                }
            except Exception as exc:
                logger.warning("yfinance fundamentals fetch failed for %s%s: %s", base_symbol, suffix, exc)
        return None

    def fetch_index_snapshot(self, ticker_symbol: str, label: str) -> dict | None:
        if not _HAS_YFINANCE:
            return None

        try:
            ticker = yf.Ticker(ticker_symbol)
            hist = ticker.history(period="5d")
            if hist is None or hist.empty or len(hist) < 2:
                return None
            closes = hist["Close"].dropna()
            if len(closes) < 2:
                return None
            price = float(closes.iloc[-1])
            prior = float(closes.iloc[-2])
            change = price - prior
            change_pct = (change / prior * 100.0) if prior else 0.0
            return {
                "symbol": ticker_symbol,
                "label": label,
                "price": round(price, 2),
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
            }
        except Exception as exc:
            logger.warning("yfinance index snapshot fetch failed for %s: %s", ticker_symbol, exc)
            return None

    def get_fundamentals_bulk(self, symbols: list[str]) -> dict[str, dict]:
        """Fetch fundamentals (incl. beta/sector) for multiple symbols. Best-effort — a failure for one symbol never blocks the rest."""
        results: dict[str, dict] = {}
        for symbol in symbols:
            data = self.fetch_fundamentals(symbol)
            if data:
                results[symbol] = data
        return results

    def get_india_vix(self) -> dict | None:
        return self.fetch_index_snapshot("^INDIAVIX", "India VIX")

    def get_current_price(self, base_symbol: str) -> float | None:
        if not _HAS_YFINANCE:
            return None

        for suffix in (".NS", ".BO"):
            try:
                ticker = yf.Ticker(f"{base_symbol}{suffix}")
                hist = ticker.history(period="1d")
                if hist is not None and not hist.empty:
                    return float(hist["Close"].iloc[-1])
            except Exception as exc:
                logger.warning("yfinance price fetch failed for %s%s: %s", base_symbol, suffix, exc)
        return None

    def fetch_news(self, base_symbol: str, limit: int = 8) -> list[dict] | None:
        if not _HAS_YFINANCE:
            return None

        for suffix in (".NS", ".BO"):
            try:
                ticker = yf.Ticker(f"{base_symbol}{suffix}")
                raw_items = ticker.news
                if not raw_items:
                    continue
                articles = []
                for item in raw_items[:limit]:
                    if not isinstance(item, dict):
                        continue
                    content = item.get("content", item)
                    title = content.get("title") or item.get("title")
                    if not title:
                        continue
                    link = (
                        (content.get("canonicalUrl") or {}).get("url")
                        or (content.get("clickThroughUrl") or {}).get("url")
                        or item.get("link")
                    )
                    publisher = (content.get("provider") or {}).get("displayName") or item.get("publisher")
                    pub_date = content.get("pubDate") or item.get("providerPublishTime")
                    articles.append({
                        "title": title,
                        "publisher": publisher,
                        "link": link,
                        "published_at": str(pub_date) if pub_date else None,
                    })
                if articles:
                    return articles
            except Exception as exc:
                logger.warning("yfinance news fetch failed for %s%s: %s", base_symbol, suffix, exc)
        return None

    def calculate_performance_score(self, base_symbol: str) -> tuple[float, dict[str, float]] | None:
        """
        Calculate a composite performance score for a stock based on:
        - YTD return (40% weight)
        - 3M performance (35% weight)
        - Volume/momentum (25% weight)
        
        Returns (score, {"ytd_return": float, "3m_return": float, "momentum": float}) or None if insufficient data.
        """
        if not _HAS_YFINANCE:
            return None

        try:
            ytd_history = self._history_for_symbol(base_symbol, "ytd")
            three_m_history = self._history_for_symbol(base_symbol, "3mo")
            one_d_history = self._history_for_symbol(base_symbol, "5d")
            
            if ytd_history is None or ytd_history.empty or three_m_history is None or three_m_history.empty:
                return None

            # YTD return
            ytd_open = float(ytd_history["Close"].iloc[0]) if len(ytd_history) > 0 else None
            ytd_close = float(ytd_history["Close"].iloc[-1]) if len(ytd_history) > 0 else None
            ytd_return = ((ytd_close - ytd_open) / ytd_open * 100.0) if ytd_open and ytd_close else 0.0

            # 3M return
            m3_open = float(three_m_history["Close"].iloc[0]) if len(three_m_history) > 0 else None
            m3_close = float(three_m_history["Close"].iloc[-1]) if len(three_m_history) > 0 else None
            m3_return = ((m3_close - m3_open) / m3_open * 100.0) if m3_open and m3_close else 0.0

            # Volume momentum (relative volume change)
            momentum = 0.0
            if one_d_history is not None and not one_d_history.empty and len(one_d_history) > 1:
                recent_vol = float(one_d_history["Volume"].iloc[-1]) if "Volume" in one_d_history.columns else 0
                avg_vol = float(one_d_history["Volume"].mean()) if "Volume" in one_d_history.columns else 0
                if avg_vol > 0:
                    momentum = (recent_vol - avg_vol) / avg_vol * 100.0

            # Composite score: YTD (40%), 3M (35%), Momentum (25%)
            # Normalize scores to 0-100 range for weighting
            ytd_normalized = max(0, min(100, (ytd_return + 50) / 1.5))  # Map to 0-100
            m3_normalized = max(0, min(100, (m3_return + 50) / 1.5))
            momentum_normalized = max(0, min(100, (momentum + 50) / 1.5))

            composite_score = (
                ytd_normalized * 0.40 +
                m3_normalized * 0.35 +
                momentum_normalized * 0.25
            )

            return (composite_score, {
                "ytd_return": round(ytd_return, 2),
                "3m_return": round(m3_return, 2),
                "momentum": round(momentum, 2),
            })
        except Exception as exc:
            logger.warning("performance score calculation failed for %s: %s", base_symbol, exc)
            return None

    def rank_stocks_by_performance(self, symbols: list[str], max_stocks: int = 5) -> list[str]:
        """
        Rank stocks by composite performance score (YTD, 3M, momentum).
        Returns top N symbols ordered by score (highest first).
        Only includes stocks with sufficient data.
        """
        scored_stocks: list[tuple[str, float]] = []
        
        for symbol in symbols:
            result = self.calculate_performance_score(symbol)
            if result is not None:
                score, _ = result
                scored_stocks.append((symbol, score))

        if not scored_stocks:
            return symbols[:max_stocks]

        # Sort by score descending, return top N
        ranked = sorted(scored_stocks, key=lambda x: x[1], reverse=True)
        return [symbol for symbol, _ in ranked[:max_stocks]]


market_data_service = MarketDataService()
