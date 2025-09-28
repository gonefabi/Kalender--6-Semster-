from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.repositories import meetings
from app.repositories.integration_credentials import get_latest as get_integration
from app.services.scheduling import SchedulingService
from app.integrations.google import calendar as google_calendar


GOOGLE_PROVIDER = "google_calendar"


@dataclass(slots=True)
class SyncResult:
    imported_events: int
    scheduler_ran: bool


class CalendarSyncService:
    """Synchronise meetings from Google Calendar and trigger scheduling."""

    def __init__(self, scheduling_service: SchedulingService) -> None:
        self._scheduling_service = scheduling_service

    def sync_google_calendar(self, session: Session, *, run_scheduler: bool = True) -> SyncResult:
        credential = get_integration(session, GOOGLE_PROVIDER)
        if credential is None:
            raise RuntimeError("Google Calendar is not connected")
        if not credential.calendar_id:
            raise RuntimeError("Stored Google Calendar credential has no calendar_id")

        service = google_calendar.build_calendar_service(
            access_token=credential.access_token,
            refresh_token=credential.refresh_token,
            token_expiry=credential.token_expiry,
            scopes=credential.scopes or ["https://www.googleapis.com/auth/calendar"],
        )

        count = 0
        existing = {
            meeting.external_id: meeting
            for meeting in meetings.list_meetings(session)
            if meeting.external_id
        }
        for event in google_calendar.list_events(service, calendar_id=credential.calendar_id):
            event_id = event.get("id")
            if not event_id:
                continue
            start = google_calendar.parse_event_datetime(event, "start")
            end = google_calendar.parse_event_datetime(event, "end")
            if start is None or end is None:
                continue
            summary = event.get("summary", "(No title)")

            meeting = existing.get(event_id)
            if meeting is None:
                meeting = meetings.create_or_update_external_meeting(
                    session,
                    external_id=event_id,
                    title=summary,
                    start_time=start,
                    end_time=end,
                    source="google",
                    metadata_payload={"raw": event},
                )
                existing[event_id] = meeting
            else:
                meetings.update_meeting_from_event(
                    session,
                    meeting,
                    title=summary,
                    start_time=start,
                    end_time=end,
                    metadata={"raw": event},
                )
            count += 1

        scheduler_ran = False
        if run_scheduler and count:
            self._scheduling_service.run_cp_schedule(session, label="google-sync")
            scheduler_ran = True

        return SyncResult(imported_events=count, scheduler_ran=scheduler_ran)
