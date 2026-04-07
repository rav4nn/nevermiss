from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/nevermiss",
        alias="DATABASE_URL",
    )
    encryption_key: str = Field(default="your-encryption-key", alias="ENCRYPTION_KEY")
    nextauth_secret: str = Field(default="your-nextauth-secret", alias="NEXTAUTH_SECRET")
    gemini_api_key: str = Field(default="your-gemini-api-key", alias="GEMINI_API_KEY")
    dodo_api_key: str = Field(default="your-dodo-api-key", alias="DODO_API_KEY")
    dodo_webhook_secret: str = Field(default="your-dodo-webhook-secret", alias="DODO_WEBHOOK_SECRET")
    dodo_product_monthly: str = Field(default="dodo_product_monthly_placeholder", alias="DODO_PRODUCT_MONTHLY")
    dodo_product_yearly: str = Field(default="dodo_product_yearly_placeholder", alias="DODO_PRODUCT_YEARLY")
    resend_api_key: str = Field(default="your-resend-api-key", alias="RESEND_API_KEY")
    sentry_dsn: str = Field(default="your-sentry-dsn", alias="SENTRY_DSN")
    cors_origins: list[str] = Field(
        default_factory=lambda: ["https://nevermiss.my", "http://localhost:3000"],
        alias="CORS_ORIGINS",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
