# Kalender Scheduling Service

This repository hosts a prototype for the hybrid calendar scheduling project described in the CP+LNS module specification. The current focus is on the constraint-programming plus large-neighbourhood-search pipeline. A future SWO module can be enabled via configuration once implemented.

## Getting Started

1. Copy `.env.example` to `.env` and adjust values (database credentials, scheduler module, Google placeholders).
2. Start the stack: `docker compose up --build`.
3. Apply the database schema automatically (the API creates tables on boot) or run `psql -f db/schema.sql` for manual setup.
4. Access the FastAPI docs at `http://localhost:8000/docs`.

### Google Calendar Integration

1. In Google Cloud Console create OAuth client credentials (Web application) and set the redirect URI to `http://localhost:8000/api/v1/google/auth/callback`.
2. Populate the Google fields in `.env` (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, etc.).
3. Start the stack and visit `GET /api/v1/google/auth/start` to obtain the authorization URL.
4. Complete the OAuth consent flow. The callback stores tokens in the `integration_credentials` table.
5. Trigger a sync via `POST /api/v1/google/sync` to pull Google Calendar events into the local database and auto-run the scheduler.
6. Run planning with either `POST /api/v1/scheduler/run` (CP+LNS) or `POST /api/v1/scheduler/run-swo` (SWO). Both endpoints return `runtime_ms`, the planned blocks, and any unscheduled tasks.

## Tests

Run `pytest` inside the API container or a local virtual environment. Example:

```bash
docker compose run --rm api pytest
```

To seed development data (10 sample tasks with durations between 2–6 hours):

```bash
docker compose run --rm api python app/cli.py
```

## Project Layout

- `app/` – FastAPI application, configuration, scheduling modules.
- `db/` – SQL schema for PostgreSQL bootstrap.
- `tests/` – Unit and integration tests.
- `docker-compose.yml` – Multi-container deployment (API + PostgreSQL).
