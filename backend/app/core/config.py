from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    PROJECT_NAME: str = "SE_ML_effy"
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@postgres:5432/se_ml_effy"
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    JWT_SECRET_KEY: str = "se_ml_effy_super_secret_jwt_key_change_in_production_32bytes"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    RATE_LIMIT_LOGIN: str = "5/minute"
    RATE_LIMIT_SIGNUP: str = "5/minute"

    # Anti-spam budgets for user-generated content. Keyed per authenticated user
    # (see app.core.limiter.user_or_ip_key), not per IP, so one abusive account
    # cannot be hidden behind a shared campus NAT and so a shared NAT cannot
    # throttle everyone on it.
    RATE_LIMIT_POST: str = "5/minute"
    RATE_LIMIT_COMMENT: str = "15/minute"
    RATE_LIMIT_MESSAGE: str = "20/minute"
    RATE_LIMIT_REACTION: str = "60/minute"
    RATE_LIMIT_UPLOAD: str = "10/minute"
    # Memory writes go into a system prompt, so the budget is generous enough for
    # editing a profile by hand but not for scripting thousands of rows into it.
    RATE_LIMIT_MEMORY: str = "30/minute"

    # LLM Provider Configuration.
    # Gemini is the default: the agent needs an 8B-class tool-calling model, and
    # running one locally costs ~5GB of RAM that a containerised dev box does not
    # reliably have (the llama-server runner gets OOM-killed mid-generation).
    # Ollama is kept as a fully supported fallback — set LLM_PROVIDER=ollama.
    LLM_PROVIDER: str = "gemini"  # "gemini" | "ollama"
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"
    # A cold 8B model has to load before it answers, and a reschedule costs
    # several round-trips (list_events -> update_event -> final answer).
    OLLAMA_TIMEOUT: float = 300.0
    # The agent prompt plus course grounding plus tool schemas exceeds Ollama's
    # 4096-token default, and an over-long prompt is truncated silently.
    OLLAMA_NUM_CTX: int = 8192
    OLLAMA_NUM_PREDICT: int = 800
    # Greedy decoding: scheduling is extraction, not creative writing.
    OLLAMA_TEMPERATURE: float = 0.0
    OLLAMA_MAX_TOOL_TURNS: int = 4
    OLLAMA_KEEP_ALIVE: str = "24h"

    GEMINI_API_KEY: str = ""
    # The current flash model. Older ids (2.5, 2.0, 1.5) are progressively being
    # closed to new projects and answer NOT_FOUND at generate time even though
    # list_models() still returns them, so prefer the newest and let
    # llm_client.FALLBACK_GEMINI_MODELS walk backwards if a key cannot reach it.
    GEMINI_MODEL: str = "gemini-3.6-flash"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
