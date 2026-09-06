"""
Run directly: python tests/test_backend/test_optimizer_service.py
Requires PyPortfolioOpt (pip install PyPortfolioOpt). Skips if unavailable.
"""
from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd

from backend_api.services import optimizer_service as mod


def _synthetic_prices(seed: int = 0) -> dict[str, dict[str, float]]:
    """4 assets, 400 trading days, asset D much less volatile than the rest."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2022-01-03", periods=400).strftime("%Y-%m-%d")
    vols = {"AAA": 0.020, "BBB": 0.018, "CCC": 0.022, "DDD": 0.004}
    drift = {"AAA": 0.0004, "BBB": 0.0003, "CCC": 0.0005, "DDD": 0.0002}
    out: dict[str, dict[str, float]] = {}
    for sym, vol in vols.items():
        rets = rng.normal(drift[sym], vol, size=len(dates))
        prices = 100.0 * np.cumprod(1.0 + rets)
        out[sym] = dict(zip(dates, prices.astype(float)))
    return out


def _holdings() -> list[dict]:
    return [
        {"tradingsymbol": "AAA", "quantity": 10, "last_price": 100.0, "average_price": 60.0},
        {"tradingsymbol": "BBB", "quantity": 10, "last_price": 100.0, "average_price": 90.0},
        {"tradingsymbol": "CCC", "quantity": 10, "last_price": 100.0, "average_price": 120.0},
        {"tradingsymbol": "DDD", "quantity": 10, "last_price": 100.0, "average_price": 95.0},
    ]


def _run(objective: str = "min_vol") -> dict | None:
    prices = _synthetic_prices()
    with patch.object(mod, "_cached_history", side_effect=lambda s: prices.get(s, {})):
        return mod.optimizer_service.optimize(holdings=_holdings(), objective=objective)


def test_min_vol_weights_are_valid():
    res = _run("min_vol")
    assert res is not None
    total = sum(w["target_pct"] for w in res["weights"])
    assert abs(total - 100.0) < 1.0
    # 4 assets -> adaptive per-name cap of max(25%, 2/n) = 50%
    assert all(w["target_pct"] <= 50.0 + 1e-6 for w in res["weights"])


def test_min_vol_beats_equal_weight_variance():
    res = _run("min_vol")
    assert res["optimized_stats"]["volatility"] <= res["current_stats"]["volatility"] + 1e-9


def test_low_vol_asset_gets_the_weight_cap():
    res = _run("min_vol")
    by_sym = {w["symbol"]: w["target_pct"] for w in res["weights"]}
    assert by_sym["DDD"] == max(by_sym.values())


def test_orders_never_exceed_portfolio_value():
    res = _run("min_vol")
    buy_value = sum(o["est_value"] for o in res["orders"] if o["action"] == "BUY")
    assert buy_value <= res["total_value"] + 1e-6


def test_too_few_holdings_returns_none():
    prices = _synthetic_prices()
    two = _holdings()[:2]
    with patch.object(mod, "_cached_history", side_effect=lambda s: prices.get(s, {})):
        assert mod.optimizer_service.optimize(holdings=two, objective="min_vol") is None


def test_tax_estimate_present_and_signed():
    res = _run("min_vol")
    assert res["tax"] is not None
    # all holdings long-term by default -> only LTCG bucket populated
    assert res["tax"]["stcg_gain"] == 0.0
    assert all(ln["term"] == "long" for ln in res["tax_lines"])
    assert res["tax"]["estimated_tax"] >= 0.0


def test_short_term_flag_moves_gain_to_stcg():
    prices = _synthetic_prices()
    with patch.object(mod, "_cached_history", side_effect=lambda s: prices.get(s, {})):
        res = mod.optimizer_service.optimize(
            holdings=_holdings(), objective="min_vol", short_term_symbols={"AAA"}
        )
    aaa = [ln for ln in res["tax_lines"] if ln["symbol"] == "AAA"]
    if aaa:  # AAA is only in tax_lines if it was a SELL
        assert aaa[0]["term"] == "short"


def test_projection_has_monthly_points_and_var():
    res = _run("min_vol")
    assert len(res["projection_optimized"]["points"]) == 12
    assert res["projection_optimized"]["var_95_1d_pct"] > 0
    assert res["projection_current"]["cvar_95_1d_pct"] >= res["projection_current"]["var_95_1d_pct"]


def test_black_litterman_runs_or_falls_back():
    prices = _synthetic_prices()

    class FakeSig:
        def __init__(self, sym, tag):
            self.symbol, self.action_tag = sym, tag

    class FakeSignals:
        stock_signals = [FakeSig("AAA", "Add"), FakeSig("CCC", "Trim")]

    fake_provider = type("P", (), {"get_portfolio_signals": lambda self, **_: FakeSignals()})()
    import llm_orchestrator.signals.signal_provider as sp

    with patch.object(mod, "_cached_history", side_effect=lambda s: prices.get(s, {})), \
         patch.object(sp, "signal_provider", fake_provider):
        res = mod.optimizer_service.optimize(holdings=_holdings(), objective="black_litterman")
    assert res is not None
    assert any(v["action_tag"] == "Add" for v in res["views"])


if __name__ == "__main__":
    if not mod._HAS_PYPFOPT:
        print("SKIP: PyPortfolioOpt not installed")
        raise SystemExit(0)
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
