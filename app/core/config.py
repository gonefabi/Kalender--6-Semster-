from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow",
    )

    app_env: Literal["development", "production", "test"] = Field(default="development", validation_alias="APP_ENV")
    app_port: int = Field(default=8000, validation_alias="APP_PORT")
    scheduler_module: Literal["CP_LNS", "SWO"] = Field(default="CP_LNS", validation_alias="SCHEDULER_MODULE")

    database_url: str = Field(validation_alias="DATABASE_URL")

    google_project_id: str | None = Field(default=None, validation_alias="GOOGLE_PROJECT_ID")
    google_client_id: str | None = Field(default=None, validation_alias="GOOGLE_CLIENT_ID")
    google_client_secret: str | None = Field(default=None, validation_alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str | None = Field(default=None, validation_alias="GOOGLE_REDIRECT_URI")
    google_oauth_scopes: str = Field(default="https://www.googleapis.com/auth/calendar", validation_alias="GOOGLE_OAUTH_SCOPES")
    google_webhook_secret: str | None = Field(default=None, validation_alias="GOOGLE_WEBHOOK_SECRET")
    google_refresh_token: str | None = Field(default=None, validation_alias="GOOGLE_REFRESH_TOKEN")
    google_calendar_id: str | None = Field(default=None, validation_alias="GOOGLE_CALENDAR_ID")
    oauthlib_insecure_transport: str | None = Field(default=None, alias="OAUTHLIB_INSECURE_TRANSPORT")


@lru_cache(1)
def get_settings() -> Settings:
    """Return cached settings instance to avoid reparsing env variables."""

    return Settings()  # type: ignore[call-arg]
