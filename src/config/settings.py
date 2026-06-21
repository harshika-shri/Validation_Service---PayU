from decimal import Decimal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str | None = Field(default=None, validation_alias="DATABASE_URL")
    POSTGRES_USER: str = "db"
    POSTGRES_PASSWORD: str = "tiger"
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "PayU_db"

    JWT_SECRET_KEY: str = Field(default="", validation_alias="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    GMAIL_TOKEN_PATH: str = "secrets/token.json"
    GMAIL_ATTACHMENT_DOWNLOAD_DIR: str = "downloads/attachments"

    GEMINI_API_KEY: str = Field(
        default="",
        validation_alias="GEMINI_API_KEY",
    )
    GEMINI_MODEL: str = "gemini-2.5-flash-lite"

    GROQ_API_KEY: str = Field(
        default="",
        validation_alias="GROQ_API_KEY",
    )
    GROQ_API_BASE_URL: str = Field(
        default="https://api.groq.com/openai/v1",
        validation_alias="GROQ_API_BASE_URL",
    )
    GROQ_LLM_MODEL: str = Field(
        default="llama-3.1-8b-instant",
        validation_alias="GROQ_LLM_MODEL",
    )
    GROQ_LLM_MAX_TOKENS: int = Field(
        default=512,
        validation_alias="GROQ_LLM_MAX_TOKENS",
    )

    PO_DATE_WINDOW_DAYS: int = Field(
        default=365,
        validation_alias="PO_DATE_WINDOW_DAYS",
    )

    UNIT_PRICE_VARIANCE_TOLERANCE: Decimal = Field(
        default=Decimal("0.01"),
        validation_alias="UNIT_PRICE_VARIANCE_TOLERANCE",
    )

    AMOUNT_ROUNDING_TOLERANCE: Decimal = Field(
        default=Decimal("0.05"),
        validation_alias="AMOUNT_ROUNDING_TOLERANCE",
    )

    @model_validator(mode="after")
    def build_database_url(self) -> "Settings":
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql+asyncpg://"
                f"{self.POSTGRES_USER}:"
                f"{self.POSTGRES_PASSWORD}@"
                f"{self.POSTGRES_HOST}:"
                f"{self.POSTGRES_PORT}/"
                f"{self.POSTGRES_DB}"
            )

        return self


settings = Settings()
