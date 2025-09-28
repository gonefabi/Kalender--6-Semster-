from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from app.core.config import get_settings


@dataclass(slots=True)
class GoogleOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: Sequence[str]


def _build_config() -> GoogleOAuthConfig:
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise RuntimeError("Google OAuth client credentials are not configured")
    redirect_uri = settings.google_redirect_uri or "http://localhost:8000/api/v1/google/auth/callback"
    scopes = [scope.strip() for scope in settings.google_oauth_scopes.split(" ") if scope.strip()]
    if not scopes:
        scopes = ["https://www.googleapis.com/auth/calendar"]
    return GoogleOAuthConfig(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        redirect_uri=redirect_uri,
        scopes=scopes,
    )


def build_oauth_flow(state: str | None = None) -> Flow:
    config = _build_config()
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "redirect_uris": [config.redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=config.scopes,
        state=state,
    )
    flow.redirect_uri = config.redirect_uri
    return flow


def credentials_from_tokens(
    *,
    access_token: str | None,
    refresh_token: str | None,
    token_expiry: datetime | None,
    scopes: Sequence[str],
) -> Credentials:
    config = _build_config()
    expiry = token_expiry
    if expiry is not None:
        # google-auth expects naive UTC timestamps for comparisons
        if expiry.tzinfo is not None:
            expiry = expiry.astimezone(timezone.utc).replace(tzinfo=None)
        else:
            expiry = expiry
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=config.client_id,
        client_secret=config.client_secret,
        scopes=list(scopes),
    )
    if expiry is not None:
        creds.expiry = expiry
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
    return creds


__all__ = [
    "GoogleOAuthConfig",
    "build_oauth_flow",
    "credentials_from_tokens",
]
