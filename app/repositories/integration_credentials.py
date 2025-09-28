from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models


def get_latest(session: Session, provider: str) -> models.IntegrationCredential | None:
    statement = (
        select(models.IntegrationCredential)
        .where(models.IntegrationCredential.provider == provider)
        .order_by(models.IntegrationCredential.created_at.desc())
        .limit(1)
    )
    return session.scalars(statement).first()


def upsert_credentials(
    session: Session,
    *,
    provider: str,
    account_email: str | None,
    calendar_id: str | None,
    access_token: str | None,
    refresh_token: str | None,
    token_expiry: datetime | None,
    scopes: Iterable[str] | None,
) -> models.IntegrationCredential:
    credential = get_latest(session, provider)
    scope_list = list(scopes) if scopes is not None else None
    if credential is None:
        credential = models.IntegrationCredential(
            provider=provider,
            account_email=account_email,
            calendar_id=calendar_id,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expiry=token_expiry,
            scopes=scope_list,
        )
        session.add(credential)
    else:
        credential.account_email = account_email
        credential.calendar_id = calendar_id
        credential.access_token = access_token
        credential.refresh_token = refresh_token or credential.refresh_token
        credential.token_expiry = token_expiry
        credential.scopes = scope_list or credential.scopes
        session.add(credential)
    session.flush()
    return credential
