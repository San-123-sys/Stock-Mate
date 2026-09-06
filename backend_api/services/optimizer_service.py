"""
Mean-variance portfolio optimization on live merged broker holdings.

Produces an efficient frontier, min-volatility / max-Sharpe target portfolios,
and concrete BUY/SELL share orders to move the current portfolio toward the
target. Uses Ledoit-Wolf covariance shrinkage + per-name weight caps + L2
regularization because raw sample-covariance mean-variance produces unstable,
extreme allocations ("error maximization").
"""
from __future__ import annotations

import logging
import time

import numpy as np
import pandas as pd

from backend_api.services.market_data_service import market_data_service

logger = logging.getLogger(__name__)

try:
    from pypfopt import EfficientFrontier, expected_returns, objective_functions, risk_models
    from pypfopt.black_litterman import BlackLittermanModel
    from pypfopt.discrete_allocation import DiscreteAllocation, get_latest_prices

    _HAS_PYPFOPT = True
except Exception:  # pragma: no cover - import guard
    _HAS_PYPFOPT = False

MIN_HOLDINGS = 3
MIN_HISTORY_ROWS = 250
MAX_WEIGHT = 0.25
L2_GAMMA = 0.1
RISK_FREE_RATE = 0.065  # ~India 10y G-Sec
FRONTIER_POINTS = 25
HISTORY_YEARS = 3
_CACHE_TTL_SECONDS = 6 * 3600

# Capital-gains tax (India, FY25+): LTCG 12.5% over a ₹1.25L annual exemption,
# STCG 20%. Acquisition dates are unknown from the broker API, so callers pass
# the symbols they know are short-term; everything else is assumed long-term.
LTCG_RATE = 0.125
STCG_RATE = 0.20
LTCG_EXEMPTION_INR = 125_000.0

# action_tag -> annual return delta applied on top of the historical prior,
# turning the chat assistant's signals into Black-Litterman views.
_VIEW_DELTA = {"Add": 0.06, "Trim": -0.06, "Watch": -0.03}
_PROJECTION_SIMS = 2000
_PROJECTION_HORIZON = 252
_PROJECTION_STEP = 21

# symbol -> (fetched_at, {date: close})
_history_cache: dict[str, tuple[float, dict[str, float]]] = {}


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _cached_history(symbol: str) -> dict[str, float]:
    now = time.time()
    hit = _history_cache.get(symbol)
    if hit and (now - hit[0]) < _CACHE_TTL_SECONDS:
        return hit[1]
    series = market_data_service.fetch_close_history(symbol, years=HISTORY_YEARS)
    if series:
        _history_cache[symbol] = (now, series)
    return series


class OptimizerService:
    def optimize(
        self,
        *,
        holdings: list[dict],
        objective: str = "min_vol",
        short_term_symbols: set[str] | None = None,
    ) -> dict | None:
        """
        Returns a result dict (see OptimizeResponse schema) or None when there is
        not enough data (< MIN_HOLDINGS symbols with sufficient price history).
        Raises only on genuinely unexpected failures.

        objective: "min_vol" | "max_sharpe" | "black_litterman"
        short_term_symbols: symbols the user has flagged as held <= 1 year,
        used only for the capital-gains tax estimate on SELL orders.
        """
        if not _HAS_PYPFOPT:
            raise RuntimeError("PyPortfolioOpt is not installed")

        short_term = {s.upper() for s in (short_term_symbols or set())}

        # --- current portfolio state -------------------------------------------------
        current_shares: dict[str, float] = {}
        current_value: dict[str, float] = {}
        avg_price: dict[str, float] = {}
        for item in holdings:
            symbol = (item.get("tradingsymbol") or item.get("symbol") or "").upper()
            if not symbol:
                continue
            qty = _to_float(item.get("quantity"))
            last_price = _to_float(item.get("last_price"))
            if qty <= 0:
                continue
            current_shares[symbol] = current_shares.get(symbol, 0.0) + qty
            current_value[symbol] = current_value.get(symbol, 0.0) + qty * last_price
            avg_price[symbol] = _to_float(item.get("average_price"), default=last_price)

        symbols = sorted(current_shares)
        if len(symbols) < MIN_HOLDINGS:
            return None

        # --- price history ---------------------------------------------------------
        series_by_symbol: dict[str, pd.Series] = {}
        for symbol in symbols:
            series = _cached_history(symbol)
            if len(series) >= MIN_HISTORY_ROWS:
                s = pd.Series(series, dtype="float64")
                s.index = pd.to_datetime(s.index)
                series_by_symbol[symbol] = s.sort_index()

        if len(series_by_symbol) < MIN_HOLDINGS:
            return None

        prices = pd.DataFrame(series_by_symbol).dropna()
        if len(prices) < MIN_HISTORY_ROWS or prices.shape[1] < MIN_HOLDINGS:
            return None

        used_symbols = list(prices.columns)
        total_value = sum(current_value.get(s, 0.0) for s in used_symbols)
        if total_value <= 0:
            return None

        # --- optimization --------------------------------------------------------
        mu = expected_returns.mean_historical_return(prices)
        cov = risk_models.CovarianceShrinkage(prices).ledoit_wolf()

        # Per-name cap must leave slack above equal-weight or max_sharpe's
        # reformulation becomes infeasible for small portfolios.
        max_weight = min(1.0, max(MAX_WEIGHT, 2.0 / len(used_symbols)))

        note = None
        views: list[dict] = []

        if objective == "black_litterman":
            posterior_mu, views, bl_note = self._black_litterman(mu, cov, holdings, used_symbols)
            note = bl_note
            if posterior_mu is not None:
                target_weights, opt_stats = self._solve(posterior_mu, cov, "max_sharpe", max_weight)
                if target_weights is None:
                    note = "Signal-driven returns have no max-Sharpe solution; showing min-risk instead."
            else:
                target_weights, opt_stats = None, None
        else:
            target_weights, opt_stats = self._solve(mu, cov, objective, max_weight)
            if target_weights is None and objective == "max_sharpe":
                note = "Max-Sharpe has no solution (all expected returns negative); showing min-risk instead."

        if target_weights is None:
            target_weights, opt_stats = self._solve(mu, cov, "min_vol", max_weight)
        if target_weights is None:
            return None

        current_w = np.array([current_value.get(s, 0.0) / total_value for s in used_symbols])
        current_stats = self._stats(current_w, mu.to_numpy(), cov.to_numpy())

        frontier = self._frontier(mu, cov, max_weight)

        # --- discrete allocation -> orders -------------------------------------------
        latest_prices = get_latest_prices(prices)
        da = DiscreteAllocation(
            {s: target_weights[s] for s in used_symbols},
            latest_prices,
            total_portfolio_value=total_value,
        )
        alloc, leftover = da.greedy_portfolio()

        orders = []
        for symbol in used_symbols:
            target_qty = int(alloc.get(symbol, 0))
            delta = target_qty - int(round(current_shares.get(symbol, 0.0)))
            if delta == 0:
                continue
            price = float(latest_prices.get(symbol, 0.0))
            orders.append(
                {
                    "symbol": symbol,
                    "action": "BUY" if delta > 0 else "SELL",
                    "shares": abs(delta),
                    "price": round(price, 2),
                    "est_value": round(abs(delta) * price, 2),
                }
            )
        orders.sort(key=lambda o: o["est_value"], reverse=True)

        weights = [
            {
                "symbol": symbol,
                "current_pct": round(current_value.get(symbol, 0.0) / total_value * 100.0, 2),
                "target_pct": round(target_weights[symbol] * 100.0, 2),
            }
            for symbol in used_symbols
        ]
        weights.sort(key=lambda w: w["target_pct"], reverse=True)

        # --- capital-gains tax estimate on the SELL orders --------------------------
        tax, tax_lines = self._tax(orders, avg_price, short_term)

        # --- Monte Carlo projection + 1-day VaR/CVaR ------------------------------
        daily = prices[used_symbols].pct_change().dropna().to_numpy()
        target_w = np.array([target_weights[s] for s in used_symbols])
        projection_current = self._project(daily @ current_w, total_value)
        projection_optimized = self._project(daily @ target_w, total_value)

        return {
            "frontier": frontier,
            "current_stats": current_stats,
            "optimized_stats": opt_stats,
            "weights": weights,
            "orders": orders,
            "leftover_cash": round(float(leftover), 2),
            "total_value": round(total_value, 2),
            "note": note,
            "tax": tax,
            "tax_lines": tax_lines,
            "projection_current": projection_current,
            "projection_optimized": projection_optimized,
            "views": views,
        }

    # ------------------------------------------------------------------------------
    def _new_ef(self, mu, cov, max_weight: float, l2: bool = True) -> "EfficientFrontier":
        ef = EfficientFrontier(mu, cov, weight_bounds=(0.0, max_weight))
        # max_sharpe reformulates the problem and cannot carry extra objectives.
        if l2:
            ef.add_objective(objective_functions.L2_reg, gamma=L2_GAMMA)
        return ef

    def _solve(self, mu, cov, objective: str, max_weight: float):
        try:
            if objective == "max_sharpe":
                ef = self._new_ef(mu, cov, max_weight, l2=False)
                ef.max_sharpe(risk_free_rate=RISK_FREE_RATE)
            else:
                ef = self._new_ef(mu, cov, max_weight)
                ef.min_volatility()
            cleaned = ef.clean_weights()
            ret, vol, sharpe = ef.portfolio_performance(risk_free_rate=RISK_FREE_RATE)
            return cleaned, {
                "expected_return": round(float(ret), 4),
                "volatility": round(float(vol), 4),
                "sharpe": round(float(sharpe), 2),
            }
        except Exception as exc:
            logger.warning("Optimizer solve failed for objective=%s: %s", objective, exc)
            return None, None

    def _frontier(self, mu, cov, max_weight: float) -> list[dict]:
        lo, hi = float(mu.min()), float(mu.max())
        if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
            return []
        points: list[dict] = []
        for target in np.linspace(lo, hi, FRONTIER_POINTS):
            try:
                ef = self._new_ef(mu, cov, max_weight)
                ef.efficient_return(target_return=float(target))
                ret, vol, sharpe = ef.portfolio_performance(risk_free_rate=RISK_FREE_RATE)
                points.append(
                    {
                        "ret": round(float(ret), 4),
                        "volatility": round(float(vol), 4),
                        "sharpe": round(float(sharpe), 2),
                    }
                )
            except Exception:
                continue
        return points

    def _black_litterman(self, mu, cov, holdings: list[dict], used_symbols: list[str]):
        """
        Blend the historical-return prior with views derived from the chat
        assistant's per-stock action tags (Add / Trim / Watch). Returns
        (posterior_mu_or_None, views_list, note).
        """
        try:
            from llm_orchestrator.signals.signal_provider import signal_provider

            signals = signal_provider.get_portfolio_signals(holdings=holdings)
            tag_by_symbol = {
                s.symbol.upper(): s.action_tag for s in signals.stock_signals if s.symbol
            }
        except Exception as exc:
            logger.warning("Signal provider unavailable for Black-Litterman: %s", exc)
            return None, [], "Signals unavailable — showing base optimization."

        absolute_views: dict[str, float] = {}
        views: list[dict] = []
        for symbol in used_symbols:
            tag = tag_by_symbol.get(symbol)
            delta = _VIEW_DELTA.get(tag)
            if delta is None:
                continue
            view_ret = float(mu[symbol]) + delta
            absolute_views[symbol] = view_ret
            views.append(
                {"symbol": symbol, "action_tag": tag, "view_return_pct": round(view_ret * 100.0, 2)}
            )

        if not absolute_views:
            return None, [], "No active buy/trim signals — showing base (min-risk) optimization."

        try:
            bl = BlackLittermanModel(cov, pi=mu, absolute_views=absolute_views)
            posterior = bl.bl_returns()
            return posterior, views, "Returns blended with signal-driven views (Black-Litterman)."
        except Exception as exc:
            logger.warning("Black-Litterman solve failed: %s", exc)
            return None, views, "Black-Litterman failed — showing base optimization."

    def _tax(self, orders: list[dict], avg_price: dict[str, float], short_term: set[str]):
        lines: list[dict] = []
        ltcg_gain = 0.0
        stcg_gain = 0.0
        for order in orders:
            if order["action"] != "SELL":
                continue
            symbol = order["symbol"]
            gain = order["shares"] * (order["price"] - avg_price.get(symbol, order["price"]))
            term = "short" if symbol in short_term else "long"
            if term == "short":
                stcg_gain += gain
            else:
                ltcg_gain += gain
            lines.append(
                {
                    "symbol": symbol,
                    "shares": order["shares"],
                    "realized_gain": round(gain, 2),
                    "term": term,
                }
            )

        ltcg_taxable = max(0.0, ltcg_gain - LTCG_EXEMPTION_INR)
        est_tax = ltcg_taxable * LTCG_RATE + max(0.0, stcg_gain) * STCG_RATE
        tax = {
            "estimated_tax": round(est_tax, 2),
            "realized_gain": round(ltcg_gain + stcg_gain, 2),
            "ltcg_gain": round(ltcg_gain, 2),
            "stcg_gain": round(stcg_gain, 2),
            "ltcg_taxable_gain": round(ltcg_taxable, 2),
            "ltcg_exemption_inr": LTCG_EXEMPTION_INR,
            "ltcg_rate_pct": LTCG_RATE * 100.0,
            "stcg_rate_pct": STCG_RATE * 100.0,
            "note": (
                "Estimate only. Holdings are assumed held over 1 year (LTCG) unless "
                "flagged short-term; broker holdings carry no acquisition date. "
                "LTCG below the ₹1.25L annual exemption is untaxed. Consult a CA."
            ),
        }
        return tax, lines

    def _project(self, portfolio_daily_returns: np.ndarray, start_value: float) -> dict:
        r = portfolio_daily_returns[np.isfinite(portfolio_daily_returns)]
        if r.size < 30:
            return {
                "points": [],
                "var_95_1d_pct": 0.0,
                "cvar_95_1d_pct": 0.0,
                "var_95_1d_value": 0.0,
                "cvar_95_1d_value": 0.0,
            }
        mu_d, sd_d = float(np.mean(r)), float(np.std(r))
        rng = np.random.default_rng(42)
        shocks = rng.normal(mu_d, sd_d, size=(_PROJECTION_SIMS, _PROJECTION_HORIZON))
        paths = np.cumprod(1.0 + shocks, axis=1) * start_value

        points = []
        for t in range(_PROJECTION_STEP, _PROJECTION_HORIZON + 1, _PROJECTION_STEP):
            col = paths[:, t - 1]
            points.append(
                {
                    "month": t // _PROJECTION_STEP,
                    "p5": round(float(np.percentile(col, 5)), 2),
                    "p50": round(float(np.percentile(col, 50)), 2),
                    "p95": round(float(np.percentile(col, 95)), 2),
                }
            )

        var_q = float(np.percentile(r, 5))
        tail = r[r <= var_q]
        cvar_q = float(tail.mean()) if tail.size else var_q
        return {
            "points": points,
            "var_95_1d_pct": round(-var_q * 100.0, 2),
            "cvar_95_1d_pct": round(-cvar_q * 100.0, 2),
            "var_95_1d_value": round(-var_q * start_value, 2),
            "cvar_95_1d_value": round(-cvar_q * start_value, 2),
        }

    def _stats(self, weights: np.ndarray, mu: np.ndarray, cov: np.ndarray) -> dict:
        ret = float(weights @ mu)
        vol = float(np.sqrt(max(weights @ cov @ weights, 0.0)))
        sharpe = (ret - RISK_FREE_RATE) / vol if vol > 0 else 0.0
        return {
            "expected_return": round(ret, 4),
            "volatility": round(vol, 4),
            "sharpe": round(sharpe, 2),
        }


optimizer_service = OptimizerService()
