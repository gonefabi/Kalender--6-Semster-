from __future__ import annotations

import logging

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.db.initializer import create_database_schema


logger = logging.getLogger(__name__)

settings = get_settings()


def create_app() -> FastAPI:
    """Construct the FastAPI application and configure routes."""

    app = FastAPI(title="Hybrid Calendar Scheduler", version="0.1.0")
    app.include_router(api_router, prefix="/api/v1")

    @app.on_event("startup")
    def on_startup() -> None:
        logger.info("Initializing database schema")
        create_database_schema()

    return app


app = create_app()
