from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.integrations.google.auth import credentials_from_tokens


def build_calendar_service(
    *,
    access_token: str | None,
    refresh_token: str | None,
    token_expiry: datetime | None,
    scopes: Iterable[str],
):
    """Construct a Google Calendar API service client."""

    creds = credentials_from_tokens(
        access_token=access_token,
        refresh_token=refresh_token,
        token_expiry=token_expiry,
        scopes=list(scopes),
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def list_events(
    service,
    *,
    calendar_id: str,
    time_min: datetime | None = None,
    time_max: datetime | None = None,
):
    """Yield event payloads from Google Calendar within optional range."""

    params: dict[str, object] = {
        "calendarId": calendar_id,
        "singleEvents": True,
        "orderBy": "startTime",
    }
    if time_min is not None:
        params["timeMin"] = _encode_google_datetime(time_min)
    if time_max is not None:
        params["timeMax"] = _encode_google_datetime(time_max)

    try:
        page_token: str | None = None
        while True:
            response = service.events().list(pageToken=page_token, **params).execute()
            for item in response.get("items", []):
                yield item
            page_token = response.get("nextPageToken")
            if not page_token:
                break
    except HttpError as exc:  # pragma: no cover - requires live API
        raise RuntimeError(f"Google Calendar API error: {exc}") from exc


def _encode_google_datetime(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def parse_event_datetime(payload: dict, key: str) -> datetime | None:
    value = payload.get(key)
    if value is None:
        return None
    date_time = value.get("dateTime") or value.get("date")
    if date_time is None:
        return None
    dt = datetime.fromisoformat(date_time.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


__all__ = [
    "build_calendar_service",
    "list_events",
    "parse_event_datetime",
]
