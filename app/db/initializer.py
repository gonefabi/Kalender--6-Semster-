from __future__ import annotations

from sqlalchemy import text

from app.core.config import get_settings
from app.db import models
from app.db.base import Base
from app.db.session import engine


def create_database_schema() -> None:
    """Create core tables if they do not exist."""

    Base.metadata.create_all(bind=engine)

    # Ensure timezone behavior
    with engine.begin() as connection:
        connection.execute(text("SET timezone TO 'UTC';"))


__all__ = ["create_database_schema"]
