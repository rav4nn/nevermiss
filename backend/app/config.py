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
    stripe_secret_key: str = Field(default="your-stripe-secret-key", alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str = Field(
        default="your-stripe-webhook-secret",
        alias="STRIPE_WEBHOOK_SECRET",
    )
    price_monthly: str = Field(default="price_monthly_placeholder", alias="PRICE_MONTHLY")
    price_yearly: str = Field(default="price_yearly_placeholder", alias="PRICE_YEARLY")
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
