"""
ResponseAgent: calls Groq (default/free) or OpenAI based on LLM_PROVIDER config.
Groq uses the same OpenAI-compatible SDK interface.
Returns a structured ChatReply.
"""
from __future__ import annotations

import json
import textwrap
from dataclasses import dataclass
from pathlib import Path

from groq import Groq
from openai import OpenAI

from backend_api.core.config import settings

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "system_prompt.txt"
_SYSTEM_PROMPT_TEMPLATE: str = _PROMPT_PATH.read_text(encoding="utf-8")


@dataclass
class ChatReply:
    answer: str
    action_tag: str        # Hold | Trim | Add | Watch | Rebalance | None
    why: str
    risk_note: str
    confidence: str        # low | medium | high
    detected_intent: str = "unknown"
    confidence_score: float = 0.0
    next_steps: list[str] | None = None
    proactive_insights: list[dict] | None = None
    portfolio_health: dict | None = None
    raw_response: str = ""


_EXTRACTION_INSTRUCTION = textwrap.dedent("""

    ---
    After your conversational reply, output a JSON block on its own line (nothing else on that line):
    {"action_tag": "...", "why": "...", "risk_note": "...", "confidence": "..."}
    Use action_tag values: Hold | Trim | Add | Watch | Rebalance | None
    Use confidence values: low | medium | high
""")

_CONCISE_STYLE_INSTRUCTION = textwrap.dedent("""

    Style guardrails:
    - Keep response concise and punchy by default.
    - Use 2-4 short lines and avoid long paragraphs.
    - Target ~35-70 words unless user explicitly asks for a deep explanation.
""")

_EXPLAIN_STYLE_INSTRUCTION = textwrap.dedent("""

    Style guardrails:
    - User explicitly selected explain mode.
    - Give a fuller explanation, not a one-liner.
    - Use 3-6 short paragraphs or bullet-like blocks.
    - Target roughly 140-260 words.
    - Still be sharp, readable, and concrete.
""")

_MAX_REPLY_WORDS = 80
_MAX_REPLY_LINES = 4


def _extract_mode(user_message: str) -> tuple[str, str]:
    text = (user_message or "").strip()
    if text.startswith("[MODE:EXPLAIN]"):
        return "explain", text.replace("[MODE:EXPLAIN]", "", 1).strip()
    if text.startswith("[MODE:QUICK]"):
        return "quick", text.replace("[MODE:QUICK]", "", 1).strip()
    return "quick", user_message


def _build_client() -> tuple[object, str]:
    """
    Returns (client, model) based on LLM_PROVIDER setting.
    Priority: groq → openai → None (fallback mode).
    """
    provider = (settings.llm_provider or "groq").lower()

    if provider == "groq" and settings.groq_api_key:
        return Groq(api_key=settings.groq_api_key), settings.groq_model

    if provider == "openai" and settings.openai_api_key:
        return OpenAI(api_key=settings.openai_api_key), settings.openai_model

    # auto-detect: try groq first, then openai
    if settings.groq_api_key:
        return Groq(api_key=settings.groq_api_key), settings.groq_model
    if settings.openai_api_key:
        return OpenAI(api_key=settings.openai_api_key), settings.openai_model

    return None, ""


class ResponseAgent:
    def __init__(self) -> None:
        self._client, self._model = _build_client()

    def is_available(self) -> bool:
        return self._client is not None

    def reply(
        self,
        *,
        user_message: str,
        portfolio_context: dict,
        conversation_history: list[dict],
        response_mode: str = "quick",
    ) -> ChatReply:
        requested_mode = (response_mode or "quick").strip().lower()
        if requested_mode in {"quick", "explain"}:
            mode = requested_mode
            cleaned_user_message = user_message
        else:
            mode, cleaned_user_message = _extract_mode(user_message)

        if self._client is None:
            return self._fallback_reply(
                portfolio_context=portfolio_context,
                reason="No LLM API key configured. Add GROQ_API_KEY to .env (free at console.groq.com).",
            )

        # Extract RAG chunks before serializing full context
        rag_chunks: list[str] = portfolio_context.pop("rag_context", [])
        rag_str = (
            "\n\n---\n\n".join(rag_chunks)
            if rag_chunks
            else "(No additional knowledge retrieved for this query.)"
        )

        context_str = json.dumps(portfolio_context, ensure_ascii=False, indent=2)
        history_str = self._format_history(conversation_history)
        response_mode_instruction = self._response_mode_instruction(mode)
        system_msg = (
            _SYSTEM_PROMPT_TEMPLATE
            .replace("{rag_context}", rag_str)
            .replace("{portfolio_context}", context_str)
            .replace("{conversation_history}", history_str or "(no prior conversation)")
            .replace("{response_mode_instruction}", response_mode_instruction)
        )

        style_instruction = _CONCISE_STYLE_INSTRUCTION
        max_tokens = 600
        clamp_words = _MAX_REPLY_WORDS
        clamp_lines = _MAX_REPLY_LINES
        if mode == "explain":
            style_instruction = _EXPLAIN_STYLE_INSTRUCTION
            max_tokens = 1100
            clamp_words = 320
            clamp_lines = 12

        messages = [{"role": "system", "content": system_msg + style_instruction + _EXTRACTION_INSTRUCTION}]
        for turn in conversation_history:
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": cleaned_user_message})

        # gpt-oss models are reasoning models that spend tokens on hidden chain-of-thought
        # before writing the reply; keep reasoning light so max_tokens isn't burned before
        # the actual answer is produced.
        extra_kwargs = {}
        if "gpt-oss" in self._model:
            extra_kwargs["reasoning_effort"] = "low"

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=0.5,
                max_tokens=max_tokens,
                **extra_kwargs,
            )
            raw = response.choices[0].message.content or ""
            parsed = self._parse(raw, max_words=clamp_words, max_lines=clamp_lines)
            if not parsed.answer.strip():
                return self._fallback_reply(
                    portfolio_context=portfolio_context,
                    reason="LLM returned an empty response.",
                )
            return parsed
        except Exception as exc:
            return self._fallback_reply(
                portfolio_context=portfolio_context,
                reason=f"LLM temporarily unavailable ({exc.__class__.__name__}: {exc}).",
            )

    @staticmethod
    def _format_history(history: list[dict]) -> str:
        lines = []
        for turn in history:
            role = turn.get("role", "user").capitalize()
            lines.append(f"{role}: {turn.get('content', '')}")
        return "\n".join(lines)

    @staticmethod
    def _parse(raw: str, *, max_words: int, max_lines: int) -> ChatReply:
        """Split conversational text from the trailing JSON metadata block."""
        answer_lines = []
        meta: dict = {}

        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                try:
                    meta = json.loads(stripped)
                except json.JSONDecodeError:
                    answer_lines.append(line)
            else:
                answer_lines.append(line)

        answer_text = ResponseAgent._clamp_answer(
            "\n".join(answer_lines).strip(),
            max_words=max_words,
            max_lines=max_lines,
        )

        return ChatReply(
            answer=answer_text,
            action_tag=meta.get("action_tag", "None"),
            why=meta.get("why", ""),
            risk_note=meta.get("risk_note", ""),
            confidence=meta.get("confidence", "medium"),
            raw_response=raw,
        )

    @staticmethod
    def _clamp_answer(text: str, *, max_words: int, max_lines: int) -> str:
        # Hard guardrail to keep chat replies short even if model drifts verbose.
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) > max_lines:
            lines = lines[:max_lines]
        compact = "\n".join(lines)

        words = compact.split()
        if len(words) <= max_words:
            return compact

        return " ".join(words[:max_words]).rstrip(" ,.;:-") + "..."

    @staticmethod
    def _response_mode_instruction(mode: str) -> str:
        if mode == "explain":
            return (
                "Explain mode is active. Give a fuller answer with reasoning, interpretation, and concrete next actions. "
                "Use 3-6 short paragraphs or grouped lines, around 140-260 words, while staying practical and witty."
            )
        return (
            "Quick mode is active. Keep the reply crisp: 2-4 short lines, around 35-70 words total, "
            "with one verdict, one key data point, one action, and one follow-up question."
        )

    @staticmethod
    def _fallback_reply(*, portfolio_context: dict, reason: str) -> ChatReply:
        portfolio = portfolio_context.get("portfolio", {})
        total_pnl_pct = float(portfolio.get("total_pnl_pct") or 0.0)
        invested = float(portfolio.get("total_invested") or 0.0)
        current = float(portfolio.get("total_current_value") or 0.0)
        holdings_count = int(portfolio.get("holdings_count") or 0)

        direction = "up" if total_pnl_pct >= 0 else "down"
        answer = (
            f"I can still give you a quick portfolio snapshot while AI chat is offline. "
            f"You currently have {holdings_count} holdings with about ₹{current:,.2f} current value "
            f"on ₹{invested:,.2f} invested — {direction} {abs(total_pnl_pct):.2f}% overall. "
            f"({reason})"
        )
        answer = ResponseAgent._clamp_answer(
            answer,
            max_words=_MAX_REPLY_WORDS,
            max_lines=_MAX_REPLY_LINES,
        )

        return ChatReply(
            answer=answer,
            action_tag="Watch" if total_pnl_pct < 0 else "Hold",
            why="Fallback summary generated from live portfolio data.",
            risk_note="This is insight, not financial advice.",
            confidence="low",
            raw_response=answer,
        )


