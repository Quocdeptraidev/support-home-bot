from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "may-homestay-support-bot"
    app_env: Literal["development", "test", "staging", "production"] = "development"
    app_debug: bool = False
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    app_timezone: str = "Asia/Ho_Chi_Minh"

    database_url: str = "postgresql+asyncpg://homestay:change_me@db:5432/homestay_support"
    redis_url: str = "redis://redis:6379/0"
    redis_idempotency_ttl_seconds: int = Field(default=86400, ge=60)

    fb_bypass_signature_verification: bool = False
    fb_page_access_token: SecretStr = SecretStr("")
    fb_app_secret: SecretStr = SecretStr("")
    fb_verify_token: SecretStr = SecretStr("")
    fb_api_version: str = ""
    fb_graph_base_url: str = "https://graph.facebook.com"
    fb_request_timeout_seconds: float = Field(default=10, gt=0)

    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = ""
    openai_classification_model: str = ""
    openai_response_model: str = ""
    openai_max_output_tokens: int = Field(default=500, ge=1, le=10000)
    openai_request_timeout_seconds: float = Field(default=30, gt=0)
    ai_safety_check_enabled: bool = True
    ai_max_conversation_history: int = Field(default=10, ge=1, le=50)
    ai_escalation_confidence_threshold: float = Field(default=0.65, ge=0, le=1)

    telegram_bot_token: SecretStr = SecretStr("")
    telegram_chat_id: str = ""
    telegram_api_base_url: str = "https://api.telegram.org"
    telegram_request_timeout_seconds: float = Field(default=10, gt=0)

    google_calendar_id: str | None = None
    google_service_account_info: SecretStr | None = None

    fb_api_rate_limit: int = Field(default=200, ge=1)
    fb_api_rate_window_seconds: int = Field(default=3600, ge=1)

    admin_username: str = ""
    admin_password: SecretStr = SecretStr("")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def classification_model(self) -> str:
        return self.openai_classification_model or self.openai_model

    @property
    def response_model(self) -> str:
        return self.openai_response_model or self.openai_model


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
