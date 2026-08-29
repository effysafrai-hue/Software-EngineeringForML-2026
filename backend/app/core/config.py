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

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.6-flash"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
