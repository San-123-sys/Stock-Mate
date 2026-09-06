"""
PortfolioExplanationPipeline: The main entry-point for the chatbot.

Capabilities (Cleo-level):
  - 14 intents: portfolio_summary, performance, allocation, position_analysis,
    risk, rebalancing, next_action, watchlist, tax_analysis, goal_tracking,
    stock_comparison, sip_advice, portfolio_health, market_overview
  - Dynamic next_steps per intent
  - Watchlist mutations (add/remove via natural language)
  - Goal extraction and SIP calculation
  - Proactive insight injection into reply

Usage:
    from llm_orchestrator.pipelines.portfolio_explanation_pipeline import pipeline
    reply = pipeline.run(user_id=..., message=..., portfolio_summary=...)
"""
from __future__ import annotations

import re

from backend_api.core.config import settings
from llm_orchestrator.agents.response_agent import ChatReply, ResponseAgent
from llm_orchestrator.context.context_builder import build_portfolio_context
from llm_orchestrator.memory.goal_store import goal_store
from llm_orchestrator.memory.session_store import SessionStore
from llm_orchestrator.memory.watchlist_store import watchlist_store
from llm_orchestrator.utils.intent_router import (
    classify_intent,
    estimate_confidence_score,
    extract_ticker_symbols,
    get_next_steps,
    intent_supported_for_portfolio,
)
from llm_orchestrator.utils.portfolio_analytics import calculate_sip_for_goal

# ── Module-level singletons ────────────────────────────────────────────────
_agent = ResponseAgent()
_store = SessionStore(
    ttl_minutes=settings.chat_session_ttl_minutes,
    max_history=settings.chat_max_history,
)

# ── Goal extraction patterns ──────────────────────────────────────────────
_GOAL_AMOUNT_RE = re.compile(
    r"(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)\s*(?:lakh|l|lac|crore|cr|k|thousand|million)?",
    re.IGNORECASE,
)
_GOAL_YEARS_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:year|yr|years|yrs)",
    re.IGNORECASE,
)
_RUPEE_MULTIPLIERS = {
    "lakh": 1e5, "lac": 1e5, "l": 1e5,
    "crore": 1e7, "cr": 1e7,
    "thousand": 1e3, "k": 1e3,
    "million": 1e6,
}


def _parse_rupee_amount(text: str) -> float | None:
    """Extract a rupee amount from text, handling lakh/crore multipliers."""
    pattern = re.compile(
        r"(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)\s*(lakh|lac|l|crore|cr|k|thousand|million)?",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return None
    num_str = match.group(1).replace(",", "")
    multiplier_str = (match.group(2) or "").lower()
    multiplier = _RUPEE_MULTIPLIERS.get(multiplier_str, 1.0)
    try:
        return float(num_str) * multiplier
    except ValueError:
        return None


def _parse_years(text: str) -> float | None:
    match = _GOAL_YEARS_RE.search(text)
    if match:
        return float(match.group(1))
    return None


def _handle_watchlist_intent(user_id: str, message: str) -> str | None:
    """
    Detects watchlist add/remove commands and mutates the watchlist.
    Returns a mutation confirmation message if a mutation was performed,
    else None (meaning: let the LLM handle it).
    """
    lower = message.lower()
    symbols = extract_ticker_symbols(message)

    is_add = any(kw in lower for kw in ["add", "track", "watch", "start tracking", "follow"])
    is_remove = any(kw in lower for kw in ["remove", "delete", "stop watching", "untrack", "stop tracking"])

    if symbols:
        if is_remove:
            removed = []
            for sym in symbols:
                if watchlist_store.remove(user_id, sym):
                    removed.append(sym)
            if removed:
                return f"Removed **{', '.join(removed)}** from your watchlist. ✅ Your watchlist now has {len(watchlist_store.get(user_id))} stocks."

        if is_add:
            for sym in symbols:
                watchlist_store.add(user_id, sym)
            wl = watchlist_store.get(user_id)
            return (
                f"Added **{', '.join(symbols)}** to your watchlist. 👀 "
                f"You're now tracking {len(wl)} stock{'s' if len(wl) != 1 else ''}: {', '.join(wl)}."
            )

    return None  # Let LLM handle "show my watchlist" etc.


def _handle_goal_intent(user_id: str, message: str, current_portfolio_value: float) -> str | None:
    """
    Detects goal-setting commands, parses target/timeline, stores goal,
    and returns a SIP calculation response.
    """
    lower = message.lower()
    is_set = any(kw in lower for kw in ["my goal is", "i want to reach", "i want", "target", "corpus", "set a goal", "set goal"])
    if not is_set:
        return None

    target = _parse_rupee_amount(message)
    years = _parse_years(message)

    if not target or not years:
        return None  # not enough info — let LLM ask for clarification

    goal = goal_store.set_goal(
        user_id,
        target_amount=target,
        current_amount=current_portfolio_value,
        years=years,
        label=f"Reach ₹{target:,.0f}",
    )
    sip = calculate_sip_for_goal(
        target_amount=target,
        current_amount=current_portfolio_value,
        years=years,
        expected_annual_return_pct=12.0,
    )

    return (
        f"🎯 Goal set: **{goal.label}** in **{years:.0f} year{'s' if years != 1 else ''}**.\n\n"
        f"{sip['note']}\n\n"
        f"I'll track your progress against this goal every time we chat. "
        f"Want me to suggest which of your holdings to SIP into to get there?"
    )


class PortfolioExplanationPipeline:
    def run(
        self,
        *,
        user_id: str,
        message: str,
        portfolio_summary: dict,
        response_mode: str = "quick",
    ) -> ChatReply:
        detected_intent = classify_intent(message)
        holdings = portfolio_summary.get("holdings", [])
        total_current_value = portfolio_summary.get("total_current_value", 0.0)
        total_invested = portfolio_summary.get("total_invested", 0.0)

        # ── Pre-LLM mutations (watchlist / goal parsing) ─────────────────
        mutation_reply: str | None = None

        if detected_intent == "watchlist":
            mutation_reply = _handle_watchlist_intent(user_id, message)

        if detected_intent == "goal_tracking":
            mutation_reply = _handle_goal_intent(user_id, message, total_current_value)

        # ── Build full context (always — mutation reply still gets context) ─
        context = build_portfolio_context(
            user_id=user_id,
            holdings=holdings,
            account_id=portfolio_summary.get("account_id"),
            detected_intent=detected_intent,
            user_message=message,
            total_invested=total_invested,
            total_current_value=total_current_value,
            total_pnl=portfolio_summary.get("total_pnl", 0.0),
            total_pnl_pct=portfolio_summary.get("total_pnl_pct", 0.0),
            include_rebalance=(detected_intent == "rebalancing"),
        )

        confidence_score = estimate_confidence_score(
            intent=detected_intent,
            holdings_count=len(holdings),
            has_llm=_agent.is_available(),
        )
        next_steps = get_next_steps(detected_intent)

        # ── If mutation was handled locally, return without LLM call ──────
        if mutation_reply:
            reply = ChatReply(
                answer=mutation_reply,
                action_tag="None",
                why="Watchlist or goal mutation performed locally.",
                risk_note="",
                confidence="high",
                detected_intent=detected_intent,
                confidence_score=confidence_score,
                next_steps=next_steps,
            )
            _store.add_turn(user_id, "user", message)
            _store.add_turn(user_id, "assistant", reply.answer)
            return reply

        # ── Retrieve session history + call LLM ──────────────────────────
        history = _store.get_history(user_id)
        reply = _agent.reply(
            user_message=message,
            portfolio_context=context,
            conversation_history=history,
            response_mode=response_mode,
        )

        reply.detected_intent = detected_intent
        reply.confidence_score = confidence_score
        reply.next_steps = next_steps

        # ── Prepend top proactive insight if high-priority and not already addressed ──
        proactive = context.get("proactive_insights", [])
        high_priority = [p for p in proactive if p.get("priority") == "high"]
        if high_priority and detected_intent == "portfolio_summary":
            top = high_priority[0]
            # Only prepend if the insight isn't already in the LLM answer
            if top["title"].split("—")[0].strip().lstrip("⚠️📉✅🎯💰 ") not in reply.answer:
                reply.answer = f"**Heads up:** {top['message']}\n\n---\n\n{reply.answer}"

        # ── Persist turns ─────────────────────────────────────────────────
        _store.add_turn(user_id, "user", message)
        _store.add_turn(user_id, "assistant", reply.answer)
        return reply

    def clear_session(self, user_id: str) -> None:
        _store.clear(user_id)


pipeline = PortfolioExplanationPipeline()

