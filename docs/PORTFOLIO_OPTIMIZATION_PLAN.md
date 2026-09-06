# Portfolio Optimization — Implementation Plan

Ported and adapted from the standalone *Parallel Portfolio Optimization Dashboard*
into Stock-Mate as a first-class, holdings-integrated feature.

## Goal

Turn "your portfolio has problems" (existing health score / sector alerts) into
"here is exactly what to do about it": an efficient-frontier optimizer that runs
on the user's **real merged broker holdings** and emits **concrete buy/sell share
orders**.

The differentiator is **not** "an optimizer exists" (mean-variance is 1952,
commodity). It is: optimization on live consolidated Zerodha + Upstox holdings,
tax-aware for the Indian market, with the rebalance driven by the same signals
the chat assistant already talks about (Black-Litterman + LLM views, Phase 4).

## Reuse (already in the codebase)

| Piece | Location | Used for |
|---|---|---|
| `_get_live_holdings()`, `_aggregate_holdings()`, `_to_float()` | `backend_api/routes/portfolio.py` | merged holdings + short-circuit envelope |
| `market_data_service` | `backend_api/services/market_data_service.py` | yfinance price history (needs one new method) |
| `MockSignalProvider` | `llm_orchestrator/signals/signal_provider.py` | per-stock action tags → BL views (Phase 4) |
| `data_status` response envelope | all portfolio routes | consistent not-linked / no-holdings / unavailable states |
| Recharts, framer-motion, Tailwind v4, lucide-react | `frontend/` | frontend page |

New dependency: **`PyPortfolioOpt>=1.5.5`** (pulls `cvxpy`, `scipy`). One library,
covers Markowitz + Ledoit-Wolf shrinkage + discrete allocation + Black-Litterman.

## Explicitly dropped from the source project

- Parallel-computing speedup benchmark tab (coursework framing, no product value)
- `multiprocessing` random-sampling optimizer (replaced by a real solver)
- matplotlib (frontend already uses Recharts)

---

## Phase 1 — Core optimizer (backend) ✅ this change

**`backend_api/services/market_data_service.py`**
- Add `fetch_close_history(base_symbol, years=3)` → `{ "YYYY-MM-DD": close }`
  using yfinance `period="5y"` (trimmed), `.NS`/`.BO` suffix fallback like the
  existing helpers.

**`backend_api/services/optimizer_service.py`** (new)
- `optimize(holdings, objective)`:
  1. Extract symbols, current values, current weights, current share counts.
  2. Fetch ~3y daily closes per symbol; align on common dates into a DataFrame.
     In-process TTL cache (6h) keyed by symbol.
     `ponytail:` in-memory cache, lost on restart — add a `price_history_cache`
     table if yfinance latency bites.
  3. Drop symbols with < ~250 rows of history. If < 3 remain → return `None`
     (route maps to `data_status="insufficient_data"`).
  4. `mu = expected_returns.mean_historical_return(prices)`
  5. `S = risk_models.CovarianceShrinkage(prices).ledoit_wolf()` — raw sample
     covariance produces unstable, extreme weights; shrinkage is not optional.
  6. Constraints: long-only, `weight_bounds=(0, 0.25)` per name, plus
     `objective_functions.L2_reg` (gamma 0.1) for further stability.
  7. Objectives: `min_volatility` (default) and `max_sharpe`
     (`risk_free_rate=0.065`, India). `max_sharpe` falls back to `min_volatility`
     with a `note` if all expected returns are negative.
  8. Efficient frontier: ~25 (volatility, return, sharpe) points via
     `efficient_return(target)` sweeps, each in a fresh `EfficientFrontier`,
     per-point try/except.
  9. Current-portfolio stats from the current weight vector against the same
     `mu` / `S`.
  10. `DiscreteAllocation(target_weights, latest_prices,
      total_portfolio_value=current_total).greedy_portfolio()` → target shares.
      Orders = `target_shares - current_shares` split into BUY / SELL rows.

**`backend_api/models/schemas.py`** — add:
`FrontierPoint`, `PortfolioStats`, `OptimizedWeight`, `RebalanceOrder`,
`OptimizeResponse`.

**`backend_api/routes/portfolio.py`** — add:
`GET /api/portfolio/optimize?objective=min_vol|max_sharpe`
- Same `_get_live_holdings` short-circuit as siblings.
- `< 3` holdings or thin history → friendly `data_status`, never a 500.

**`backend_api/app.py`** — no change (portfolio router already registered).

**`backend_api/requirements.txt`** — add `PyPortfolioOpt>=1.5.5`.

**Test** — `tests/test_optimizer_service.py`:
synthetic 4-asset price frame; assert target weights sum to ~1, respect the 25%
cap, min-vol variance < equal-weight variance, discrete allocation value does not
exceed portfolio value.

---

## Phase 2 — Frontend page ✅ this change

**`frontend/src/services/api.js`** — `portfolio.optimize(objective)`.

**`frontend/src/pages/OptimizePage.jsx`** (new)
- Objective toggle: **Min Risk** (default) / Max Sharpe.
- Efficient frontier scatter (Recharts `ScatterChart`): frontier curve, current
  portfolio marked `✕`, optimized marked `★`.
- Current vs Optimized stat row: expected return, volatility, Sharpe.
- Weights table: current % → target %.
- **Rebalance orders table** — BUY/SELL, shares, est. value. The actionable payoff.
- Mandatory disclaimer banner: estimates from historical data, not investment
  advice; expected-return estimates are noisy, min-risk is the robust default.
- `data_status` handling mirrors `NewsDigestPage` (loading shimmer / empty state).

**`frontend/src/App.jsx`** — protected route `/optimize`.

**`frontend/src/components/AppShell.jsx`** — nav item (`Scale` icon, "Optimize").

---

## Phase 3 — India-specific differentiators ✅ done

1. **Tax-aware rebalancing.** `optimizer_service._tax()` estimates STCG (20%) vs
   LTCG (12.5%, ₹1.25L annual exemption) on the SELL orders using
   `average_price` from holdings. `GET /optimize?short_term=SYM1,SYM2` flags
   holdings held ≤ 1 year; everything else assumed LTCG.
   `ponytail:` Kite/Upstox holdings carry no acquisition date — the frontend
   exposes a per-symbol "held ≤ 1 yr" toggle that re-runs the optimize call.
   Upgrade path: tradebook CSV import (Zerodha Console / Upstox Reports — free,
   manual) or Upstox Trade History API (free, automatable). Deferred.
2. **Monte Carlo projection + 1-day VaR/CVaR.** `optimizer_service._project()` —
   2000 normal-return paths, 252-day horizon, monthly p5/p50/p95 checkpoints for
   both current and optimized weights. Frontend renders a 12-month cone.
   Rates note: the older `build_tax_analysis()` in `portfolio_analytics.py` still
   uses pre-2024 rates (10% / 15% / ₹1L) — not touched here; worth a follow-up.

## Phase 4 — Black-Litterman + LLM views ✅ done

- `optimizer_service._black_litterman()` — `objective=black_litterman`:
  `signal_provider.get_portfolio_signals()` action tags → absolute views on top
  of the historical prior (`_VIEW_DELTA`: Add +6%, Trim −6%, Watch −3%);
  `BlackLittermanModel(cov, pi=mu, absolute_views=...)` → posterior → max-Sharpe.
  Falls back to min-vol with a `note` when there are no active views or the
  solve is infeasible. `views` list returned for the UI.
- Chat: `context_builder._build_rebalance_plan()` runs the BL optimize when
  `detected_intent == "rebalancing"` and injects a compact plan (orders, target
  weights, stat deltas, tax, views) into `context["rebalance_plan"]`.
  `system_prompt.txt` rebalancing playbook updated to use the real orders.

## Phase 5 — Wiring & docs ✅ (partial)

- ✅ Dashboard teaser card (`OptimizeTeaser` in `DashboardPage.jsx`) — lazy,
  non-blocking `optimize("min_vol")` call once live holdings ≥ 3 are known;
  shows "Sharpe X → Y in N trades" with a link to `/optimize`.
- ✅ README: intro sentence, How It Works step 7, Features entry, architecture row.
- ✅ Stale tax rates fixed in `portfolio_analytics.build_tax_analysis()`
  (now 12.5% / 20% / ₹1.25L, matching the RAG knowledge base and Phase 3).
- Deferred: tradebook CSV / Upstox Trade History import for real acquisition dates.

---

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Mean-variance "error maximization" — tiny return-estimate changes swing weights | Ledoit-Wolf shrinkage + 25% weight cap + L2 reg + **min-vol is the default** |
| yfinance latency for 15–30 holdings (one call each) | 6h in-process history cache; daily result cache later |
| Portfolios with < 3 holdings | skip optimization, friendly `data_status` |
| Users treat it as advice | disclaimer banner, min-risk default, "aggressive estimate" label on max-Sharpe |

## Build order

Phase 1 + 2 = working shippable feature. Then Phase 4 (the unique part), then 3, then 5.
