from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Imadztrades Shadow AI Trading Desk"
    app_version: str = "0.18.0-backend-complete"
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")
    database_url: str | None = Field(default=None)
    anthropic_api_key: str | None = Field(default=None)
    anthropic_model: str = Field(default="claude-sonnet-4-20250514")
    anthropic_api_version: str = Field(default="2023-06-01")
    anthropic_base_url: str = Field(default="https://api.anthropic.com")
    anthropic_api_format: str = Field(default="anthropic")
    anthropic_auth_scheme: str = Field(default="x-api-key")
    telegram_bot_token: str | None = Field(default=None)
    telegram_chat_id: str | None = Field(default=None)
    telegram_auto_send_narrative: bool = Field(default=False)

    market_data_provider: str | None = Field(default=None)
    twelvedata_api_key: str | None = Field(default=None)
    market_ingest_symbols: str = Field(default="XAUUSD,XAGUSD")
    market_ingest_timeframes: str = Field(default="M5,M15,H1,H4,D")
    market_ingest_interval_seconds: int = Field(default=300)
    market_ingest_autostart: bool = Field(default=False)
    market_ingest_auto_analysis: bool = Field(default=False)
    market_ingest_auto_analysis_timeframe: str = Field(default="M15")
    market_ingest_auto_analysis_provider: str = Field(default="rules")

    calendar_provider: str | None = Field(default=None)
    trading_economics_api_key: str | None = Field(default=None)
    calendar_refresh_interval_seconds: int = Field(default=3600)
    calendar_relevant_countries: str = Field(default="United States")
    calendar_relevant_events: str = Field(default="")
    calendar_autostart: bool = Field(default=False)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
