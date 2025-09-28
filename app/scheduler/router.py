from __future__ import annotations

from enum import Enum

from app.core.config import get_settings


class SchedulerType(str, Enum):
    CP_LNS = "CP_LNS"
    SWO = "SWO"


def get_active_scheduler_type() -> SchedulerType:
    """Return the scheduler type specified in settings."""

    settings = get_settings()
    return SchedulerType(settings.scheduler_module)


class SchedulerRouter:
    """Placeholder router that will return scheduler implementations."""

    def __init__(self, cp_scheduler: object, swo_scheduler: object | None = None) -> None:
        self._cp_scheduler = cp_scheduler
        self._swo_scheduler = swo_scheduler

    def resolve(self) -> object:
        scheduler_type = get_active_scheduler_type()
        if scheduler_type is SchedulerType.CP_LNS:
            return self._cp_scheduler
        if self._swo_scheduler is None:
            raise NotImplementedError("SWO module is not implemented yet")
        return self._swo_scheduler
