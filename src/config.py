from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str = Field(alias="TELEGRAM_BOT_TOKEN")
    openai_api_key: str = Field(alias="OPENAI_API_KEY")
    database_url: str = Field(alias="DATABASE_URL")

    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")
    openai_embedding_model: str = Field(default="text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL")
    bot_username: str = Field(default="", alias="BOT_USERNAME")

    admin_ids: str = Field(default="", alias="ADMIN_IDS")

    use_webhook: bool = Field(default=False, alias="USE_WEBHOOK")
    webhook_base_url: str = Field(default="", alias="WEBHOOK_BASE_URL")
    webhook_path: str = Field(default="/telegram/webhook", alias="WEBHOOK_PATH")
    webhook_host: str = Field(default="0.0.0.0", alias="WEBHOOK_HOST")
    webhook_port: int = Field(default=8080, ge=1, le=65535, alias="WEBHOOK_PORT")

    polling_allowed_updates: str = Field(default="message", alias="POLLING_ALLOWED_UPDATES")
    max_user_message_chars: int = Field(default=4000, ge=32, alias="MAX_USER_MESSAGE_CHARS")
    max_embedding_chars: int = Field(default=2000, ge=16, alias="MAX_EMBEDDING_CHARS")

    summary_hour_utc: int = Field(default=18, ge=0, le=23, alias="SUMMARY_HOUR_UTC")
    summary_minute_utc: int = Field(default=0, ge=0, le=59, alias="SUMMARY_MINUTE_UTC")
    weekly_day_of_week: str = Field(default="mon", alias="WEEKLY_DAY_OF_WEEK")
    tz: str = Field(default="UTC", alias="TZ")

    @property
    def admin_id_set(self) -> set[int]:
        if not self.admin_ids.strip():
            return set()
        return {int(x.strip()) for x in self.admin_ids.split(",") if x.strip()}

    @property
    def polling_updates(self) -> list[str]:
        updates = [x.strip() for x in self.polling_allowed_updates.split(",") if x.strip()]
        return updates or ["message"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
