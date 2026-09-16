"""
Central application configuration.
Loaded from environment variables / .env file.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "FraudShield AI"
    ENVIRONMENT: str = "development"

    SECRET_KEY: str = "insecure-dev-secret-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    DATABASE_URL: str = "postgresql+psycopg2://fraudshield:fraudshield@localhost:5432/fraudshield"

    REDIS_URL: str = "redis://localhost:6379/0"

    LLM_PROVIDER: str = "none"  # claude | openai | gemini | groq | local | none
    ANTHROPIC_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str | None = None

    FRONTEND_ORIGIN: str = "http://localhost:5173"

    RISK_LOW_MAX: int = 30
    RISK_MEDIUM_MAX: int = 70


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
