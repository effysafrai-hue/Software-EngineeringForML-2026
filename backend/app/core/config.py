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

    # LLM Provider Configuration
    LLM_PROVIDER: str = "ollama"  # "ollama" | "gemini"
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
    GEMINI_MODEL: str = "gemini-1.5-flash"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
