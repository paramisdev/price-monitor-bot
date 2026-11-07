from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: SecretStr
    admin_chat_id: int

    database_path: Path = Path("data/prices.db")
    books_url: str = "http://books.toscrape.com/catalogue/page-1.html"
    max_pages: int = Field(default=5, ge=1, le=100)
    check_interval_minutes: int = Field(default=60, ge=1)
    request_timeout_seconds: float = Field(default=20.0, gt=0)
    log_level: LogLevel = "INFO"
