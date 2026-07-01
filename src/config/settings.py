from decimal import Decimal

from pydantic import Field, computed_field, model_validator
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

    REDIS_HOST: str = Field(default="redis", validation_alias="REDIS_HOST")
    REDIS_PORT: int = Field(default=6379, validation_alias="REDIS_PORT")
    REDIS_DB: int = Field(default=0, validation_alias="REDIS_DB")
    REDIS_STREAM_NAME: str = Field(
        default="extraction.events",
        validation_alias="REDIS_STREAM_NAME",
    )
    REDIS_STREAM_CONSUMER_GROUP: str = Field(
        default="validation-service",
        validation_alias="REDIS_STREAM_CONSUMER_GROUP",
    )
    REDIS_STREAM_CONSUMER_NAME: str = Field(
        default="validation-consumer",
        validation_alias="REDIS_STREAM_CONSUMER_NAME",
    )
    REDIS_STREAM_BATCH_SIZE: int = Field(
        default=10,
        validation_alias="REDIS_STREAM_BATCH_SIZE",
    )
    REDIS_STREAM_BLOCK_MS: int = Field(
        default=5000,
        validation_alias="REDIS_STREAM_BLOCK_MS",
    )
    REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS: float = Field(
        default=5.0,
        validation_alias="REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS",
    )
    REDIS_SOCKET_TIMEOUT_BUFFER_SECONDS: float = Field(
        default=5.0,
        validation_alias="REDIS_SOCKET_TIMEOUT_BUFFER_SECONDS",
    )
    VALIDATION_EVENTS_STREAM: str = Field(
        default="validation.events",
        validation_alias="VALIDATION_EVENTS_STREAM",
    )

    CELERY_TASK_DEFAULT_QUEUE: str = "validation"
    CELERY_TASK_MAX_RETRIES: int = 3
    CELERY_TASK_RETRY_BACKOFF_SECONDS: int = 60
    VALIDATION_TASK_TIMEOUT_SECONDS: int = Field(
        default=1800,
        validation_alias="VALIDATION_TASK_TIMEOUT_SECONDS",
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

    @computed_field
    @property
    def REDIS_SOCKET_TIMEOUT_SECONDS(self) -> float:
        block_seconds = self.REDIS_STREAM_BLOCK_MS / 1000.0

        return block_seconds + self.REDIS_SOCKET_TIMEOUT_BUFFER_SECONDS

    @computed_field
    @property
    def CELERY_BROKER_URL(self) -> str:
        return (
            f"redis://{self.REDIS_HOST}:"
            f"{self.REDIS_PORT}/{self.REDIS_DB}"
        )

    @computed_field
    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        return self.CELERY_BROKER_URL

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
