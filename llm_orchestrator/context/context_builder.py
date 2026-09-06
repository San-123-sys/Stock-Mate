"""
Assembles a structured context dict from live portfolio + signals + analytics + watchlist + goals + RAG.
This context is passed to the LLM as the user's complete financial state.
"""
from __future__ import annotations

from llm_orchestrator.memory.goal_store import goal_store
from llm_orchestrator.memory.watchlist_store import watchlist_store
from llm_orchestrator.rag.retriever import rag_retriever
from llm_orchestrator.signals.signal_provider import PortfolioSignals, signal_provider
from llm_orchestrator.utils.portfolio_analytics import build_portfolio_analytics, calculate_sip_for_goal
from llm_orchestrator.utils.proactive_insights import generate_proactive_insights


def _build_rebalance_plan(holdings: list[dict]) -> dict | None:
    """
    Signal-driven (Black-Litterman) optimization summary, compact enough to drop
    into the LLM context so it can narrate concrete rebalance orders. Best-effort.
    """
    try:
        from backend_api.services.optimizer_service import optimizer_service

        result = optimizer_service.optimize(holdings=holdings, objective="black_litterman")
        if not result:
            return None
        return {
            "objective": "black_litterman",
            "note": result.get("note"),
            "current_stats": result.get("current_stats"),
            "optimized_stats": result.get("optimized_stats"),
            "views": result.get("views", []),
            "orders": result.get("orders", [])[:12],
            "target_weights": [
                {"symbol": w["symbol"], "target_pct": w["target_pct"]}
                for w in result.get("weights", [])
            ],
            "estimated_tax": (result.get("tax") or {}).get("estimated_tax"),
        }
    except Exception:
        return None


def build_portfolio_context(
    *,
    user_id: str,
    holdings: list[dict],
    account_id: str | None = None,
    detected_intent: str = "unknown",
    user_message: str = "",
    total_invested: float = 0.0,
    total_current_value: float = 0.0,
    total_pnl: float = 0.0,
    total_pnl_pct: float = 0.0,
    include_rebalance: bool = False,
) -> dict:
    """
    Returns a rich context dict fed into the system prompt and LLM.
    Includes: portfolio summary, per-holding signals, analytics (health score,
    SIP advice, tax analysis), watchlist, active goal with SIP calculation,
    proactive insights, and RAG knowledge chunks relevant to the query.
    """
    signals: PortfolioSignals = signal_provider.get_portfolio_signals(holdings=holdings)
    analytics = build_portfolio_analytics(
        holdings=holdings,
        total_invested=total_invested,
        total_current_value=total_current_value,
        total_pnl=total_pnl,
        total_pnl_pct=total_pnl_pct,
    )

    holdings_summary = []
    for h in holdings:
        qty = float(h.get("quantity") or 0)
        avg = float(h.get("average_price") or 0)
        last = float(h.get("last_price") or 0)
        pnl = (last - avg) * qty
        pnl_pct = ((last - avg) / avg * 100.0) if avg > 0 else 0.0

        # Match signal for this symbol
        sig = next(
            (s for s in signals.stock_signals if s.symbol == h.get("tradingsymbol")),
            None,
        )

        holdings_summary.append({
            "symbol": h.get("tradingsymbol"),
            "exchange": h.get("exchange"),
            "quantity": qty,
            "avg_price": round(avg, 2),
            "last_price": round(last, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "action_tag": sig.action_tag if sig else "Hold",
            "momentum": sig.momentum if sig else "neutral",
            "signal_notes": sig.notes if sig else "",
            "tft_forecast_7d_pct": sig.tft_forecast_7d_pct if sig else None,
            "sentiment_score": sig.sentiment_score if sig else None,
        })

    # ── Proactive insights ─────────────────────────────────────────────────
    proactive_insights = generate_proactive_insights(
        holdings=holdings,
        total_invested=total_invested,
        total_current_value=total_current_value,
        total_pnl=total_pnl,
        total_pnl_pct=total_pnl_pct,
        analytics=analytics,
    )

    # ── Watchlist ──────────────────────────────────────────────────────────
    user_watchlist = watchlist_store.get(user_id)

    # ── Active goal + SIP calculation ─────────────────────────────────────
    goal = goal_store.get_goal(user_id)
    goal_context: dict | None = None
    if goal:
        goal_store.update_current_amount(user_id, total_current_value)
        sip_calc = calculate_sip_for_goal(
            target_amount=goal.target_amount,
            current_amount=total_current_value,
            years=goal.years,
            expected_annual_return_pct=goal.expected_return_pct,
        )
        goal_context = {
            "label": goal.label,
            "target_amount": goal.target_amount,
            "current_amount": round(total_current_value, 2),
            "years": goal.years,
            "expected_return_pct": goal.expected_return_pct,
            "progress_pct": round(
                min(100.0, (total_current_value / goal.target_amount) * 100.0), 2
            ) if goal.target_amount > 0 else 0.0,
            "sip_calculation": sip_calc,
        }

    # ── RAG: retrieve relevant financial knowledge ─────────────────────────
    rag_query = user_message or detected_intent
    rag_chunks: list[str] = rag_retriever.retrieve(
        query=rag_query,
        intent=detected_intent,
        n_results=3,
    )

    rebalance_plan = _build_rebalance_plan(holdings) if include_rebalance else None

    return {
        "user_id": user_id,
        "account_id": account_id,
        "detected_intent": detected_intent,
        "rebalance_plan": rebalance_plan,
        "portfolio": {
            "total_invested": round(total_invested, 2),
            "total_current_value": round(total_current_value, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "holdings_count": len(holdings),
            "holdings": holdings_summary,
        },
        "analytics": analytics,
        "signals": {
            "overall_action": signals.overall_action,
            "portfolio_risk_level": signals.portfolio_risk_level,
            "top_risks": signals.top_risks,
            "top_strengths": signals.top_strengths,
            "signals_source": signals.signals_source,
        },
        "proactive_insights": proactive_insights,
        "watchlist": user_watchlist,
        "active_goal": goal_context,
        "rag_context": rag_chunks,
    }
