from __future__ import annotations

import math


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Portfolio Health Score (0–100)
# ---------------------------------------------------------------------------

def compute_portfolio_health_score(
    *,
    holdings_count: int,
    concentration_top1_pct: float,
    concentration_top3_pct: float,
    total_pnl_pct: float,
    risk_flags: list[str],
    diversification_score: float,
    sector_count: int = 0,
    portfolio_beta: float | None = None,
) -> dict:
    """
    Composite health score (0–100) with six components:
    • Diversification  (20 pts): holdings spread + concentration
    • Performance      (25 pts): portfolio-level P&L %
    • Risk mgmt        (20 pts): absence of risk flags
    • Concentration    (15 pts): single-stock weight penalty
    • Sector spread    (10 pts): number of distinct sectors held
    • Beta fit         (10 pts): how close portfolio beta is to market-neutral (~1.0)
    """
    # — Diversification component (0–20) ————————————————————————
    div_score = min(diversification_score / 100.0, 1.0) * 20.0

    # — Performance component (0–25) —————————————————————————————
    # Sigmoid-like mapping: -20%→0, 0%→12.5, +20%→25
    perf_clamped = max(-20.0, min(20.0, total_pnl_pct))
    perf_score = ((perf_clamped + 20.0) / 40.0) * 25.0

    # — Risk management component (0–20) ————————————————————————
    penalty_per_flag = 6.5
    risk_score = max(0.0, 20.0 - len(risk_flags) * penalty_per_flag)

    # — Concentration component (0–15) ——————————————————————————
    if concentration_top1_pct >= 70:
        conc_score = 0.0
    elif concentration_top1_pct >= 50:
        conc_score = 5.0
    elif concentration_top1_pct >= 35:
        conc_score = 10.0
    else:
        conc_score = 15.0

    # — Sector spread component (0–10) ———————————————————————————
    # 4+ distinct sectors held → full marks
    sector_score = min(sector_count / 4.0, 1.0) * 10.0

    # — Beta fit component (0–10) ————————————————————————————————
    if portfolio_beta is None:
        beta_score = 5.0
    elif 0.8 <= portfolio_beta <= 1.2:
        beta_score = 10.0
    elif 0.5 <= portfolio_beta < 0.8 or 1.2 < portfolio_beta <= 1.6:
        beta_score = 6.0
    else:
        beta_score = 2.0

    total = round(div_score + perf_score + risk_score + conc_score + sector_score + beta_score, 1)
    total = max(0.0, min(100.0, total))

    if total >= 80:
        grade, verdict = "A", "Excellent — well-diversified with solid returns."
    elif total >= 65:
        grade, verdict = "B", "Good — a few areas to tighten up."
    elif total >= 50:
        grade, verdict = "C", "Average — concentration or performance dragging you down."
    elif total >= 35:
        grade, verdict = "D", "Needs work — significant risk or drawdown detected."
    else:
        grade, verdict = "F", "Critical — take action on risk and diversification now."

    return {
        "score": total,
        "grade": grade,
        "verdict": verdict,
        "components": {
            "diversification": round(div_score, 1),
            "performance": round(perf_score, 1),
            "risk_management": round(risk_score, 1),
            "concentration": round(conc_score, 1),
            "sector_spread": round(sector_score, 1),
            "beta_fit": round(beta_score, 1),
        },
    }


# ---------------------------------------------------------------------------
# SIP Suitability Advisor
# ---------------------------------------------------------------------------

def compute_sip_advice(
    *,
    holdings: list[dict],
    total_invested: float,
    total_pnl_pct: float,
) -> dict:
    """
    Suggests SIP candidates and monthly amounts based on portfolio composition.
    """
    if not holdings or total_invested <= 0:
        return {
            "recommended_monthly_sip": 0.0,
            "sip_candidates": [],
            "note": "No holdings data available for SIP advice.",
        }

    rows = []
    for h in holdings:
        qty = _safe_float(h.get("quantity"))
        avg = _safe_float(h.get("average_price"))
        last = _safe_float(h.get("last_price"))
        invested = qty * avg
        current = qty * last
        pnl_pct = ((current - invested) / invested * 100.0) if invested > 0 else 0.0
        weight_pct = (invested / total_invested * 100.0) if total_invested > 0 else 0.0
        rows.append({
            "symbol": h.get("tradingsymbol", "?"),
            "pnl_pct": pnl_pct,
            "weight_pct": weight_pct,
            "last_price": last,
        })

    # SIP candidates: holdings that are underweight (<15%) and not in heavy loss (>-20%)
    candidates = [
        r for r in rows
        if r["weight_pct"] < 15.0 and r["pnl_pct"] > -20.0 and r["pnl_pct"] < 25.0
    ]
    # If no underweight candidates, suggest the top performers (momentum SIP)
    if not candidates:
        candidates = sorted(rows, key=lambda r: r["pnl_pct"], reverse=True)[:2]

    # Sort by "most underweight" first (candidates that need balance)
    candidates = sorted(candidates, key=lambda r: r["weight_pct"])[:3]

    # Suggested monthly SIP: ~5–10% of total invested / 12
    suggested_monthly = round(max(500.0, total_invested * 0.07 / 12.0), -2)  # round to nearest ₹100

    return {
        "recommended_monthly_sip": suggested_monthly,
        "sip_candidates": [
            {
                "symbol": c["symbol"],
                "current_weight_pct": round(c["weight_pct"], 2),
                "recent_pnl_pct": round(c["pnl_pct"], 2),
                "reason": (
                    "Underweight — good for averaging down via SIP"
                    if c["weight_pct"] < 10
                    else "Balanced weight — suitable for steady SIP accumulation"
                ),
            }
            for c in candidates
        ],
        "note": (
            "SIP into underweight, non-loss positions helps rebalance gradually. "
            "Not financial advice — DYOR."
        ),
    }


# ---------------------------------------------------------------------------
# Goal SIP Calculator
# ---------------------------------------------------------------------------

def calculate_sip_for_goal(
    *,
    target_amount: float,
    current_amount: float,
    years: float,
    expected_annual_return_pct: float = 12.0,
) -> dict:
    """
    Calculates monthly SIP needed to reach a corpus goal using PMT formula.
    Default expected return: 12% annualized (reasonable for diversified equity SIP).
    """
    if target_amount <= current_amount:
        return {
            "monthly_sip_needed": 0.0,
            "shortfall": 0.0,
            "months": 0,
            "note": "You've already reached your goal! 🎉",
        }

    shortfall = target_amount - current_amount
    months = int(years * 12)
    if months == 0:
        return {
            "monthly_sip_needed": shortfall,
            "shortfall": shortfall,
            "months": 0,
            "note": "Goal is immediate — lump sum needed.",
        }

    r = expected_annual_return_pct / 100.0 / 12.0  # monthly rate
    # FV = PMT * [((1+r)^n - 1) / r] * (1+r)
    # PMT = FV * r / (((1+r)^n - 1) * (1+r))
    factor = (((1 + r) ** months) - 1) / r * (1 + r)
    # Current investments grow too — future value of existing portfolio
    existing_fv = current_amount * ((1 + r) ** months)
    remaining_fv = max(0.0, target_amount - existing_fv)

    if remaining_fv <= 0:
        monthly_sip = 0.0
        note = "Your existing portfolio may already reach this goal if it grows at the expected rate. Keep it invested! ✅"
    else:
        monthly_sip = round(remaining_fv / factor, 2)
        note = (
            f"To reach ₹{target_amount:,.0f} in {years:.1f} years at {expected_annual_return_pct}% "
            f"annualized, you need ₹{monthly_sip:,.0f}/month. Your existing ₹{current_amount:,.0f} "
            f"is already working for you."
        )

    return {
        "monthly_sip_needed": monthly_sip,
        "shortfall": round(shortfall, 2),
        "months": months,
        "expected_annual_return_pct": expected_annual_return_pct,
        "note": note,
    }


# ---------------------------------------------------------------------------
# Tax Analysis Helper
# ---------------------------------------------------------------------------

# Equity capital-gains tax, India (Budget 2024, FY25+):
# LTCG 12.5% on gains above a ₹1.25L annual exemption; STCG a flat 20%.
LTCG_RATE_PCT = 12.5
STCG_RATE_PCT = 20.0
LTCG_EXEMPTION_INR = 125_000


def build_tax_analysis(
    *,
    holdings: list[dict],
    total_invested: float,
) -> dict:
    """
    Provides LTCG/STCG guidance.
    Note: Zerodha holdings API does not include buy dates; we provide concept-level analysis.
    For exact tax computation, users need their broker's P&L statement.
    """
    if not holdings:
        return {
            "ltcg_threshold_inr": LTCG_EXEMPTION_INR,
            "ltcg_rate_pct": LTCG_RATE_PCT,
            "stcg_rate_pct": STCG_RATE_PCT,
            "unrealized_gains": 0.0,
            "unrealized_losses": 0.0,
            "net_unrealized": 0.0,
            "holdings_with_gains": [],
            "holdings_with_losses": [],
            "tax_loss_harvesting_candidates": [],
            "note": "No holdings to analyze.",
        }

    gains_rows, loss_rows = [], []
    for h in holdings:
        qty = _safe_float(h.get("quantity"))
        avg = _safe_float(h.get("average_price"))
        last = _safe_float(h.get("last_price"))
        invested = qty * avg
        current = qty * last
        pnl = current - invested
        pnl_pct = (pnl / invested * 100.0) if invested > 0 else 0.0
        symbol = h.get("tradingsymbol", "?")

        entry = {
            "symbol": symbol,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "current_value": round(current, 2),
        }
        if pnl >= 0:
            gains_rows.append(entry)
        else:
            loss_rows.append(entry)

    total_gains = sum(r["pnl"] for r in gains_rows)
    total_losses = sum(r["pnl"] for r in loss_rows)

    # Tax-loss harvesting: losses that can offset gains
    harvesting_candidates = sorted(loss_rows, key=lambda r: r["pnl"])[:3]

    return {
        "ltcg_threshold_inr": LTCG_EXEMPTION_INR,
        "ltcg_rate_pct": LTCG_RATE_PCT,
        "stcg_rate_pct": STCG_RATE_PCT,
        "unrealized_gains": round(total_gains, 2),
        "unrealized_losses": round(total_losses, 2),
        "net_unrealized": round(total_gains + total_losses, 2),
        "holdings_with_gains": sorted(gains_rows, key=lambda r: r["pnl"], reverse=True),
        "holdings_with_losses": sorted(loss_rows, key=lambda r: r["pnl"]),
        "tax_loss_harvesting_candidates": harvesting_candidates,
        "note": (
            "Holdings held > 1 year: LTCG at 12.5% on gains above the ₹1.25L annual exemption. "
            "Holdings held ≤ 1 year: STCG at a flat 20% (Budget 2024). "
            "Exact holding periods require your broker's P&L report. Consult a CA for your specific situation."
        ),
    }


# ---------------------------------------------------------------------------
# Core Analytics (original, extended)
# ---------------------------------------------------------------------------

def build_portfolio_analytics(
    *,
    holdings: list[dict],
    total_invested: float,
    total_current_value: float,
    total_pnl: float,
    total_pnl_pct: float,
    sector_count: int = 0,
    portfolio_beta: float | None = None,
) -> dict:
    if not holdings:
        return {
            "largest_position": None,
            "smallest_position": None,
            "top_winner": None,
            "top_loser": None,
            "concentration_top1_pct": 0.0,
            "concentration_top3_pct": 0.0,
            "diversification_score": 0.0,
            "portfolio_beta": None,
            "portfolio_health": compute_portfolio_health_score(
                holdings_count=0,
                concentration_top1_pct=0.0,
                concentration_top3_pct=0.0,
                total_pnl_pct=0.0,
                risk_flags=["no_holdings"],
                diversification_score=0.0,
                sector_count=0,
                portfolio_beta=None,
            ),
            "sip_advice": compute_sip_advice(
                holdings=[], total_invested=0.0, total_pnl_pct=0.0
            ),
            "tax_analysis": build_tax_analysis(holdings=[], total_invested=0.0),
            "risk_flags": ["no_holdings"],
        }

    rows: list[dict] = []
    for h in holdings:
        symbol = h.get("tradingsymbol") or h.get("symbol") or "?"
        quantity = _safe_float(h.get("quantity"))
        avg_price = _safe_float(h.get("average_price"))
        last_price = _safe_float(h.get("last_price"))

        invested = quantity * avg_price
        current = quantity * last_price
        pnl = current - invested
        pnl_pct = (pnl / invested * 100.0) if invested > 0 else 0.0

        rows.append(
            {
                "symbol": symbol,
                "invested": invested,
                "current": current,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
            }
        )

    rows_by_current = sorted(rows, key=lambda r: r["current"], reverse=True)
    rows_by_pnl = sorted(rows, key=lambda r: r["pnl"], reverse=True)

    total_current = total_current_value if total_current_value > 0 else sum(r["current"] for r in rows)
    top1 = rows_by_current[0]["current"] if rows_by_current else 0.0
    top3 = sum(r["current"] for r in rows_by_current[:3]) if rows_by_current else 0.0

    concentration_top1_pct = (top1 / total_current * 100.0) if total_current > 0 else 0.0
    concentration_top3_pct = (top3 / total_current * 100.0) if total_current > 0 else 0.0

    # Diversification score (0–100): higher holdings + lower concentration → better
    holdings_count = len(rows)
    count_component = min(holdings_count / 12.0, 1.0) * 50.0
    concentration_component = max(0.0, (100.0 - concentration_top3_pct)) * 0.5
    diversification_score = round(min(100.0, count_component + concentration_component), 2)

    risk_flags: list[str] = []
    if concentration_top1_pct >= 45:
        risk_flags.append("single_stock_concentration_high")
    if concentration_top3_pct >= 75:
        risk_flags.append("top3_concentration_high")
    if total_pnl_pct <= -10:
        risk_flags.append("portfolio_drawdown_high")
    if total_pnl < 0 and total_invested > 0:
        risk_flags.append("overall_portfolio_negative")

    # Per-holding rank (for stock comparison)
    holdings_ranked = [
        {
            "symbol": r["symbol"],
            "current": round(r["current"], 2),
            "pnl": round(r["pnl"], 2),
            "pnl_pct": round(r["pnl_pct"], 2),
            "weight_pct": round(r["current"] / total_current * 100.0, 2) if total_current > 0 else 0.0,
        }
        for r in sorted(rows, key=lambda r: r["pnl_pct"], reverse=True)
    ]

    portfolio_health = compute_portfolio_health_score(
        holdings_count=holdings_count,
        concentration_top1_pct=concentration_top1_pct,
        concentration_top3_pct=concentration_top3_pct,
        total_pnl_pct=total_pnl_pct,
        risk_flags=risk_flags,
        diversification_score=diversification_score,
        sector_count=sector_count,
        portfolio_beta=portfolio_beta,
    )

    sip_advice = compute_sip_advice(
        holdings=holdings,
        total_invested=total_invested,
        total_pnl_pct=total_pnl_pct,
    )

    tax_analysis = build_tax_analysis(
        holdings=holdings,
        total_invested=total_invested,
    )

    return {
        "largest_position": {
            "symbol": rows_by_current[0]["symbol"],
            "current": round(rows_by_current[0]["current"], 2),
            "weight_pct": round((rows_by_current[0]["current"] / total_current * 100.0), 2)
            if total_current > 0 else 0.0,
        } if rows_by_current else None,
        "smallest_position": {
            "symbol": rows_by_current[-1]["symbol"],
            "current": round(rows_by_current[-1]["current"], 2),
            "weight_pct": round((rows_by_current[-1]["current"] / total_current * 100.0), 2)
            if total_current > 0 else 0.0,
        } if rows_by_current else None,
        "top_winner": {
            "symbol": rows_by_pnl[0]["symbol"],
            "pnl": round(rows_by_pnl[0]["pnl"], 2),
            "pnl_pct": round(rows_by_pnl[0]["pnl_pct"], 2),
        } if rows_by_pnl else None,
        "top_loser": {
            "symbol": rows_by_pnl[-1]["symbol"],
            "pnl": round(rows_by_pnl[-1]["pnl"], 2),
            "pnl_pct": round(rows_by_pnl[-1]["pnl_pct"], 2),
        } if rows_by_pnl else None,
        "concentration_top1_pct": round(concentration_top1_pct, 2),
        "concentration_top3_pct": round(concentration_top3_pct, 2),
        "diversification_score": diversification_score,
        "portfolio_beta": round(portfolio_beta, 2) if portfolio_beta is not None else None,
        "holdings_ranked": holdings_ranked,
        "portfolio_health": portfolio_health,
        "sip_advice": sip_advice,
        "tax_analysis": tax_analysis,
        "risk_flags": risk_flags,
    }

    if not holdings:
        return {
            "largest_position": None,
            "smallest_position": None,
            "top_winner": None,
            "top_loser": None,
            "concentration_top1_pct": 0.0,
            "concentration_top3_pct": 0.0,
            "diversification_score": 0.0,
            "risk_flags": ["no_holdings"],
        }

    rows: list[dict] = []
    for h in holdings:
        symbol = h.get("tradingsymbol") or h.get("symbol") or "?"
        quantity = _safe_float(h.get("quantity"))
        avg_price = _safe_float(h.get("average_price"))
        last_price = _safe_float(h.get("last_price"))

        invested = quantity * avg_price
        current = quantity * last_price
        pnl = current - invested
        pnl_pct = (pnl / invested * 100.0) if invested > 0 else 0.0

        rows.append(
            {
                "symbol": symbol,
                "invested": invested,
                "current": current,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
            }
        )

    rows_by_current = sorted(rows, key=lambda r: r["current"], reverse=True)
    rows_by_pnl = sorted(rows, key=lambda r: r["pnl"], reverse=True)

    total_current = total_current_value if total_current_value > 0 else sum(r["current"] for r in rows)
    top1 = rows_by_current[0]["current"] if rows_by_current else 0.0
    top3 = sum(r["current"] for r in rows_by_current[:3]) if rows_by_current else 0.0

    concentration_top1_pct = (top1 / total_current * 100.0) if total_current > 0 else 0.0
    concentration_top3_pct = (top3 / total_current * 100.0) if total_current > 0 else 0.0

    # Simple diversification score (0-100): higher holdings count + lower concentration => better
    holdings_count = len(rows)
    count_component = min(holdings_count / 12.0, 1.0) * 50.0
    concentration_component = max(0.0, (100.0 - concentration_top3_pct)) * 0.5
    diversification_score = round(min(100.0, count_component + concentration_component), 2)

    risk_flags: list[str] = []
    if concentration_top1_pct >= 45:
        risk_flags.append("single_stock_concentration_high")
    if concentration_top3_pct >= 75:
        risk_flags.append("top3_concentration_high")
    if total_pnl_pct <= -10:
        risk_flags.append("portfolio_drawdown_high")
    if total_pnl < 0 and total_invested > 0:
        risk_flags.append("overall_portfolio_negative")

    return {
        "largest_position": {
            "symbol": rows_by_current[0]["symbol"],
            "current": round(rows_by_current[0]["current"], 2),
            "weight_pct": round((rows_by_current[0]["current"] / total_current * 100.0), 2)
            if total_current > 0
            else 0.0,
        }
        if rows_by_current
        else None,
        "smallest_position": {
            "symbol": rows_by_current[-1]["symbol"],
            "current": round(rows_by_current[-1]["current"], 2),
            "weight_pct": round((rows_by_current[-1]["current"] / total_current * 100.0), 2)
            if total_current > 0
            else 0.0,
        }
        if rows_by_current
        else None,
        "top_winner": {
            "symbol": rows_by_pnl[0]["symbol"],
            "pnl": round(rows_by_pnl[0]["pnl"], 2),
            "pnl_pct": round(rows_by_pnl[0]["pnl_pct"], 2),
        }
        if rows_by_pnl
        else None,
        "top_loser": {
            "symbol": rows_by_pnl[-1]["symbol"],
            "pnl": round(rows_by_pnl[-1]["pnl"], 2),
            "pnl_pct": round(rows_by_pnl[-1]["pnl_pct"], 2),
        }
        if rows_by_pnl
        else None,
        "concentration_top1_pct": round(concentration_top1_pct, 2),
        "concentration_top3_pct": round(concentration_top3_pct, 2),
        "diversification_score": diversification_score,
        "risk_flags": risk_flags,
    }
