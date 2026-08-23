from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Stock-Mate Backend")
    app_env: str = os.getenv("APP_ENV", "dev")
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("APP_PORT", "8000"))

    zerodha_api_key: str = os.getenv("ZERODHA_API_KEY", "")
    zerodha_api_secret: str = os.getenv("ZERODHA_API_SECRET", "")
    zerodha_redirect_url: str = os.getenv(
        "ZERODHA_REDIRECT_URL", "http://localhost:8000/api/zerodha/callback"
    )

    upstox_api_key: str = os.getenv("UPSTOX_API_KEY", "")
    upstox_api_secret: str = os.getenv("UPSTOX_API_SECRET", "")
    upstox_redirect_url: str = os.getenv(
        "UPSTOX_REDIRECT_URL", "http://localhost:8000/api/upstox/callback"
    )

    jwt_secret: str = os.getenv("JWT_SECRET", "change-me-in-prod")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_exp_minutes: int = int(os.getenv("JWT_EXP_MINUTES", "120"))
    broker_token_secret: str = os.getenv("BROKER_TOKEN_SECRET", "change-me-too")
    oauth_state_hmac_secret: str = os.getenv("OAUTH_STATE_HMAC_SECRET", "replace-state-hmac-secret")
    oauth_state_ttl_minutes: int = int(os.getenv("OAUTH_STATE_TTL_MINUTES", "15"))

    # LLM provider: "groq" (free) or "openai"
    llm_provider: str = os.getenv("LLM_PROVIDER", "groq")

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    hf_api_token: str = os.getenv("HF_API_TOKEN", "")

    chat_session_ttl_minutes: int = int(os.getenv("CHAT_SESSION_TTL_MINUTES", "60"))
    chat_max_history: int = int(os.getenv("CHAT_MAX_HISTORY", "20"))

    smtp_server: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_username: str = os.getenv("SMTP_USERNAME", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:5174")


settings = Settings()
