# ReliefMesh Backend

System of record for incidents, resources, assignments, and the audit trail
in the ReliefMesh crisis-coordination platform.

## Purpose

During a disaster, reports come in from ingestion (WhatsApp/SMS via n8n) and
get triaged by an AI service, which recommends what to do (assign a
resource, replan around a blocked road, etc.). A human dispatcher approves
or overrides those recommendations. **This backend is the single source of
truth that all of that funnels through.** It owns:

- The incident/resource/assignment data model and their state machines.
- Concurrency safety — two simultaneous requests can never assign the same
  resource twice.
- Atomicity — a multi-step operation (e.g. replanning) either fully applies
  or fully rolls back, never partially.
- The append-only audit trail of every decision and state change.

**This backend deliberately does not do AI reasoning, deduplication, or
priority scoring.** It receives decisions from the AI service / n8n / a
human and enforces that applying them is safe and consistent. If you're
integrating a new AI/n8n flow and find yourself wanting the backend to
"decide" something, that decision belongs upstream — the backend should
only be asked to validate and persist it.

## Architecture overview

```
app/
  api/routes/        FastAPI routers — one file per resource, thin: parse
                      request, call a service function, return its result.
  api/deps.py         Shared dependencies (DB session, optional API key auth).
  api/common_responses.py  Reusable OpenAPI error-response fragments.
  core/               Config, domain exception types, free-text domain values.
  db/                 SQLAlchemy engine/session/declarative base.
  models/             SQLAlchemy ORM models + the fixed status enums.
  schemas/            Pydantic request/response models (the actual wire
                      contract — read these first when integrating).
  services/           All business logic lives here: locking, state-machine
                      transitions, atomic transactions, audit logging.
    state_machine.py     Single source of truth for allowed status
                          transitions (incident/resource/assignment).
    id_generator.py      Human-readable IDs (INC-1042, AMB-02, ASG-887) via
                          native Postgres sequences.
    assignment_service.py   Create/update assignments; the locking
                             primitives reused by replanning.
    replanning_service.py   The road-block-reassignment flow.
    dashboard_service.py    Read-only aggregation for the frontend.
alembic/               Migrations (single initial migration; schema is small
                        and stable — see "Migrations" below).
scripts/seed_demo_data.py   Seeds the canonical Krishna Apartments demo.
tests/                 pytest suite, run against a real (isolated) Postgres.
```

**Design choices worth knowing before you change anything:**

- `Incident.type` and `Resource.type` are free-text strings, not enums —
  new incident/resource types need zero backend code changes. Incident
  *status* and resource/assignment *status* ARE fixed enums with explicit
  transition tables in `state_machine.py`; don't add ad-hoc `if status ==`
  checks anywhere else.
- Every entity ID is human-readable and generated via a Postgres sequence
  (`nextval()`), not app-side counters — atomic under concurrency for free.
- Resource `capacity` exists on the model but is **not** consumed/decremented
  by assignment logic in this MVP — it's descriptive only.
- Double-booking a resource is prevented three ways at once: `SELECT ...
  FOR UPDATE` row locks (fixed ID order, to avoid deadlocks), a re-check of
  state after the lock is acquired, and a partial unique index in Postgres
  (`assignments(resource_id) WHERE status IN ('ASSIGNED','ACTIVE')`) as a
  hard backstop. See `assignment_service.py` and `replanning_service.py`.
- The audit trail (`action_logs`) is append-only by omission: there is no
  PATCH/PUT/DELETE route for it anywhere, so it can't be rewritten via the
  API.

## Prerequisites

- Python 3.11+
- Docker Desktop (for PostgreSQL)
- `pip install -r requirements.txt` inside a virtualenv

## Docker / PostgreSQL setup

The backend expects a single PostgreSQL 16 instance holding two databases:
the dev/demo database (`reliefmesh`) and an isolated test database
(`reliefmesh_test`, created automatically the first time you run the test
suite — see below).

If you don't already have the container running:

```bash
docker run -d --name reliefmesh-postgres \
  -e POSTGRES_USER=reliefmesh \
  -e POSTGRES_PASSWORD=reliefmesh \
  -e POSTGRES_DB=reliefmesh \
  -p 5432:5432 \
  postgres:16-alpine
```

If it already exists, just make sure it's running:

```bash
docker start reliefmesh-postgres
docker ps --filter name=reliefmesh-postgres
```

## Environment variables

Copy `.env.example` to `.env` and adjust as needed:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg2://reliefmesh:reliefmesh@localhost:5432/reliefmesh` | Dev/demo database connection. |
| `AUTH_ENABLED` | `false` | If `true`, every request needs a matching `X-API-Key` header. Off by default so the demo/local dev is never blocked. |
| `API_KEY` | `change-me` | Checked only when `AUTH_ENABLED=true`. |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins. |
| `APP_ENV` | `local` | Informational only, surfaced in `/health`. |
| `TEST_DATABASE_URL` | *(unset)* | Optional override for the isolated test database (defaults to `reliefmesh_test` on the same host/credentials). See "Test database isolation." |

## Migrations

Alembic-managed, schema in `alembic/versions/` (currently one migration
covering the full initial schema: `incidents`, `resources`, `assignments`,
`action_logs`, their enums, sequences, and the partial-unique locking
constraint).

```bash
alembic upgrade head        # apply migrations (dev database, via DATABASE_URL)
alembic revision -m "..."   # create a new migration after a model change
alembic downgrade -1        # roll back one migration
```

## Starting the backend

```bash
uvicorn app.main:app --reload --port 8000
```

- **API docs (Swagger UI): http://localhost:8000/docs**
- ReDoc: http://localhost:8000/redoc
- Raw OpenAPI schema: http://localhost:8000/openapi.json
- Health check: http://localhost:8000/health — verifies the process *and*
  the live Postgres connection; poll this from n8n/infra, not `/docs`.

## Running tests

```bash
pytest
```

### Test database isolation

Tests run against **real PostgreSQL**, never SQLite — the assignment/
replanning tests exercise genuine `SELECT ... FOR UPDATE` locking and
concurrent-transaction behavior that SQLite can't reproduce. To keep this
from writing test data into your dev/demo database:

- `tests/conftest.py` overrides `DATABASE_URL` to point at a separate
  `reliefmesh_test` database (same Postgres instance/credentials) *before*
  the app is imported anywhere.
- A session-scoped fixture creates that database if it doesn't exist yet
  and runs `alembic upgrade head` against it.
- A function-scoped fixture `TRUNCATE`s all app tables after every test, so
  tests are independent and repeatable.

Your dev database (`reliefmesh`) is never touched by `pytest`. You can
point tests at a different database (e.g. in CI) via `TEST_DATABASE_URL`.

## Seeding the Krishna Apartments demo

```bash
python -m scripts.seed_demo_data --reset
```

This is the canonical demo script — it drives the **real service layer**
(not raw SQL), so it's also an end-to-end smoke test of the exact code path
the live demo uses. It:

1. Registers a 10-resource fleet (5 ambulances, 2 rescue units, a
   volunteer, a shelter, a hospital), ordered so the IDs land exactly on
   `AMB-02` and `AMB-05`.
2. Creates incident `INC-1042` ("Water entering Krishna Apartments Block C.
   My grandmother cannot walk.").
3. Assigns `AMB-02` + `RESCUE-01` to it (an AI recommendation is logged
   too).
4. Replans: `AMB-02` hits a road block, so `AMB-05` takes over. `AMB-02` is
   released, the old assignment is superseded (not deleted).

After running, `GET /dashboard` and `GET /activity-log` show the fully
resolved narrative, ready to walk through live.

**Seed reset behavior:** by default the script *adds* to whatever's already
in the target database. Pass `--reset` to `TRUNCATE`
incidents/resources/assignments/action_logs first (and reset the ambulance/
rescue-unit ID sequences, so `AMB-02`/`AMB-05`/`RESCUE-01` land correctly
again) — only do this against your local dev database, never anything
shared. Pass `--fleet-only` to seed just the resource roster and skip the
incident/assignment/replan narrative.

## Important API endpoints

All routes except `/health` are versionless and (optionally, see
`AUTH_ENABLED`) require an `X-API-Key` header. Full request/response
schemas and examples are in Swagger UI at `/docs` — this is a map, not a
substitute.

| Method & path | Purpose |
|---|---|
| `GET /health` | Liveness + DB connectivity check. |
| `POST /incidents` | Create an incident (ingestion/AI → backend). |
| `GET /incidents`, `GET /incidents/{id}` | List/get incidents, with status/severity/type/priority filters. |
| `PATCH /incidents/{id}` | Update incident fields (not status). |
| `POST /incidents/{id}/resolve`, `POST /incidents/{id}/cancel` | Terminal status transitions. |
| `POST /resources` | Register a resource (starts `AVAILABLE`). |
| `GET /resources`, `GET /resources/{id}` | List/get resources, with status/type filters. |
| `POST /resources/{id}/status` | Direct status transition (e.g. maintenance). |
| `POST /assignments` | Atomically assign one or more available resources to an incident. |
| `GET /assignments`, `GET /assignments/{id}` | List/get assignments, filterable by incident/resource/status. |
| `POST /assignments/{id}/status` | Transition to `ACTIVE`/`COMPLETED`/`CANCELLED` (never `SUPERSEDED` — that's replanning-only). |
| `POST /replanning` | Swap a resource on a live assignment for replacement(s), atomically. **The critical demo path.** |
| `GET /activity-log`, `POST /activity-log`, `GET /activity-log/{id}` | Append-only audit trail; filterable, paginated. |
| `GET /dashboard` | Frontend-ready aggregated snapshot (counts, recent activity, current incidents/resources). |

## Example integration flow (n8n)

A typical end-to-end flow through n8n for a new report:

1. Ingestion webhook receives a raw report (WhatsApp/SMS) → n8n forwards
   the text to the AI service for extraction.
2. n8n calls `POST /incidents` with the AI's structured output (see payload
   below). The backend assigns `INC-1042` and logs `incident_received`.
3. n8n asks the AI service for a resource recommendation, gets back
   resource IDs, and (after human approval if your flow requires it) calls
   `POST /assignments` with those resource IDs and `decision_source` set
   appropriately.
4. If a field report says a resource can't reach the scene (e.g. a road
   block), n8n calls `POST /replanning` with the old resource and the AI's
   suggested replacement(s).
5. n8n polls `GET /activity-log?since=<timestamp>` and/or `GET /dashboard`
   to drive notifications and the operator view.

## Example AI → backend payloads

**Reporting a new incident** (`POST /incidents`):

```json
{
  "location": "Krishna Apartments, Block C",
  "latitude": 12.9352,
  "longitude": 77.6146,
  "type": "flood",
  "severity": "CRITICAL",
  "people_affected": 4,
  "needs": ["medical", "evacuation"],
  "confidence": 0.88,
  "priority_score": 94,
  "report_metadata": {
    "channel": "whatsapp",
    "raw_text": "Water entering Krishna Apartments Block C. My grandmother cannot walk."
  }
}
```

`report_metadata` is not stored on the incident row — it's recorded into
the `incident_received` action-log entry for provenance (source channel,
raw text, merged report IDs, etc.).

**Assigning resources after approval** (`POST /assignments`):

```json
{
  "incident_id": "INC-1042",
  "resource_ids": ["AMB-02", "RESCUE-01"],
  "decision_source": "ai",
  "approved_by": "dispatcher_1",
  "reason": "Medical emergency involving a vulnerable person",
  "ai_recommendation": {
    "incident_id": "INC-1042",
    "priority_score": 94,
    "recommended_resources": ["AMB-02", "RESCUE-01"],
    "reason": "Medical emergency involving a vulnerable person",
    "confidence": 0.91
  }
}
```

`ai_recommendation` is optional — pass it through when the assignment
fulfills a specific AI recommendation, and it gets logged as its own
`ai_recommendation_received` audit entry alongside the assignment.

## Replanning flow

`POST /replanning` is the road-block scenario: a dispatched resource can no
longer reach the incident, and the AI/human decision is to swap it for a
different one.

```json
{
  "incident_id": "INC-1042",
  "old_resource_id": "AMB-02",
  "new_resource_ids": ["AMB-05"],
  "reason": "road_blocked",
  "decision_source": "ai",
  "approved_by": "dispatcher_1"
}
```

What happens, atomically (all in one DB transaction — see
`replanning_service.py`):

1. The incident is locked and checked (must not already be
   `RESOLVED`/`CANCELLED`).
2. The old assignment is locked — by `old_assignment_id` if given, else the
   current assignment for `incident_id` + `old_resource_id` — and
   re-validated as still live (`ASSIGNED`/`ACTIVE`) *after* the lock is
   held. This is what makes concurrent replans of the same assignment safe:
   the loser blocks on the lock, then sees the new state and fails cleanly
   instead of double-superseding it.
3. The old resource and all replacement resources are locked together, in
   sorted-ID order (never deadlocks against a concurrent
   assignment/replan touching an overlapping resource set).
4. All replacement resources must be `AVAILABLE`, checked before anything
   is mutated — an unavailable replacement leaves the old assignment
   completely untouched (`409 Conflict`).
5. The old assignment becomes `SUPERSEDED` (kept forever, never deleted)
   and the old resource becomes `AVAILABLE` again.
6. New `Assignment` row(s) are created (`ASSIGNED`) and the replacement
   resource(s) become `DISPATCHED`.
7. Every step is written to `action_logs` (`assignment_superseded`,
   `assignment_created`, plus `ai_recommendation_received` if one was
   passed) with enough metadata to reconstruct the full history later.
8. Commit, or roll back everything on any failure — including the
   partial-unique-index backstop catching a race that got past the row
   locks.

The response includes the incident (with its current live assignments),
the superseded assignment, and the new assignment(s) — everything a
frontend needs to update its view in one call.
