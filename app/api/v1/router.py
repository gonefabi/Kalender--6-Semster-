from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import google_auth, health, meetings, scheduler, tasks

api_router = APIRouter()
api_router.include_router(health.router, tags=["system"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(meetings.router, prefix="/meetings", tags=["meetings"])
api_router.include_router(scheduler.router, prefix="/scheduler", tags=["scheduler"])
api_router.include_router(google_auth.router, prefix="/google", tags=["google"])
