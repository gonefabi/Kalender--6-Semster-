from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session
from app.integrations.google.auth import build_oauth_flow
from app.repositories.integration_credentials import upsert_credentials
from app.services.calendar_sync import CalendarSyncService

router = APIRouter()


def _get_scopes() -> list[str]:
    settings = get_settings()
    scopes = [scope.strip() for scope in settings.google_oauth_scopes.split(" ") if scope.strip()]
    return scopes or ["https://www.googleapis.com/auth/calendar"]


@router.get("/auth/start")
def start_google_auth(state: str | None = None) -> JSONResponse:
    flow = build_oauth_flow(state)
    authorization_url, new_state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )
    return JSONResponse({"authorization_url": authorization_url, "state": new_state})


@router.get("/auth/callback")
def google_auth_callback(request: Request, session: Session = Depends(get_session)) -> RedirectResponse:
    params = request.query_params
    if "error" in params:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=params["error"])

    # Check if authorization code is present
    if "code" not in params:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authorization code missing")

    state = params.get("state")
    flow = build_oauth_flow(state)
    flow.fetch_token(authorization_response=str(request.url))
    credentials = flow.credentials

    calendar_id = params.get("calendar_id") or get_settings().google_calendar_id or "primary"

    credential = upsert_credentials(
        session,
        provider="google_calendar",
        account_email=credentials.id_token.get("email") if credentials.id_token else None,
        calendar_id=calendar_id,
        access_token=credentials.token,
        refresh_token=credentials.refresh_token,
        token_expiry=credentials.expiry,
        scopes=_get_scopes(),
    )
    session.commit()

    redirect_target = get_settings().google_redirect_uri or "http://localhost:8000"
    return RedirectResponse(url=redirect_target, status_code=status.HTTP_302_FOUND)


@router.post("/sync")
def manual_sync(session: Session = Depends(get_session)) -> JSONResponse:
    # The SchedulingService requires a scheduler instance; reuse application singleton.
    from app.api.v1.endpoints.scheduler import _scheduling_service  # circular import avoidance

    sync_service = CalendarSyncService(_scheduling_service)
    try:
        result = sync_service.sync_google_calendar(session)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    session.commit()
    return JSONResponse({"imported_events": result.imported_events, "scheduler_ran": result.scheduler_ran})
