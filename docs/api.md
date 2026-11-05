# Reporting API, version 1

Local origin: `http://127.0.0.1:8000`. Interactive reference: `/docs`. Captured OpenAPI schema: [api-openapi.json](evidence/api-openapi.json). All application endpoints are GET-only under `/api/v1`; no import/admin action is exposed.

## Endpoints

| Path | Response |
| --- | --- |
| `/health` | Process liveness, independent of the database |
| `/ready` | Database connection readiness; data availability remains separate |
| `/routes` | Historical route identifiers/labels, per-route record counts and observed date bounds; unassigned route record count is separate |
| `/summary` | Matching count, numeric duration sample counts, recorded-value statistics, quality scope and definitions |
| `/patterns` | Observed daily counts, all cause codes/descriptions including unmapped values, calendar weekdays based on Date |
| `/records` | Stable bounded pages of matching source records and quality flags |
| `/data-health` | Latest attempt, last success and selected snapshot for each resource, with source-wide quality |

## One filter definition

`route`, `start`, `end` and `snapshot_id` share the same validation and selection code across reporting endpoints.

- `route` is an exact text identifier, trimmed at the API boundary. Omit it for all accepted records, including unassigned routes. Branches such as `102D` remain separate from `102`.
- `start` and `end` are real calendar dates in `YYYY-MM-DD` form, inclusive at both ends. Omitted bounds default to the selected snapshot's observed date bounds. Reversed ranges, including a default that creates a reversed range, return 422. Values outside loaded coverage are not silently clamped; the response sets `extends_beyond_loaded_dates`.
- `snapshot_id` optionally chooses an immutable successful snapshot for the delay resource. Omit it to capture the current active snapshot. An unavailable/wrong-resource UUID returns 404. Reports retain pinned lookup meaning even when a newer lookup is active.
- `/routes` also accepts `q`, up to 80 characters. Search is case-insensitive literal substring matching against identifiers/recorded labels; `%` is not a wildcard. Route entries are sorted by identifier length and identifier, not a reliability ranking. Unassigned counts describe the date/route selection before text search.
- `/records` accepts `page` (1–10000), `page_size` (1–100, default 25), and `sort` (`date_desc` default or `date_asc`). Ordering uses recorded Date, recorded Time with nulls last, then unique source row position. Offset pagination is stable within a selected immutable snapshot.
- Unknown or repeated query parameter names are rejected with 422. Dates represented as epoch strings are not accepted. Sort clauses come from an allowlist; values are bound parameters.

## Keep a browser view consistent

First request `/summary` with route/dates. Read `context.snapshot.id`, then pass it as `snapshot_id` to `/patterns`, `/records` and subsequent table pages. The dashboard does this automatically. It resets selection when filters change or the visitor explicitly checks for newer imported data.

Each endpoint also uses a read-only repeatable-read transaction, selecting the snapshot once for all queries in that response. Multi-query results cannot mix snapshots if an import is promoted midway through the request. Queries have a five-second statement timeout. Imports run separately through the CLI.

The URL stores the route/date filters, sort and page for reload/back/forward. The browser's pinned snapshot is maintained for the current selection; a fresh shared URL selects the then-active import. This distinction is deliberate: URLs preserve filter intent, while the API exposes snapshot identity for exact reproduction.

## Response context and public boundary

Every reporting response includes effective filters, selected snapshot identity, observed source date coverage, source/lookup hashes/IDs and retrieval/import metadata. Publisher timestamps remain strings without an invented timezone; actual retrieval/import instants are emitted in UTC. Record times remain source wall-clock values.

Summary `quality` is explicitly scoped to the entire selected file; filtered `summary.flagged_records` describes only the matching rows. A record may have several flags. Numeric summaries exclude null durations, include reported zeroes, and return numbers rather than Decimal strings. Empty selections return count/sample size zero, null duration summaries and empty pattern/record arrays.

Data health projects only safe fields. It does not return raw payloads, filesystem paths, request headers, source provenance dictionaries, error summaries, traces or database credentials. Failed attempts receive a fixed public message, while detailed local audit diagnostics stay internal. The source URL is exposed only if it is an official Toronto HTTPS URL without embedded credentials.

Errors use `{"error": {"code": "...", "message": "..."}}`, with sanitized field/message details for validation. Database failures return a generic 503. Liveness can stay healthy during a database failure; readiness returns 503. A reachable database with no loaded delay snapshot returns `data_not_loaded` from reports. Unknown API and asset paths preserve errors and never fall through to SPA HTML.

## Actual verification

The full Python suite passed **63 cases**, including 20 new API cases against PostgreSQL. Tests cover hand-calculated summary values, inclusive boundaries, branch separation, literal search, invalid inputs, empty values, null versus zero, pagination across a refresh, public error privacy, data availability and SPA/API routing. One known deprecation warning concerns the pinned Starlette test client's httpx compatibility transport; it does not fail the checks.

Real HTTP calls for route 102 / January 2025 returned 65 records, 65 numeric duration samples and a 20-minute median, matching the independently verified source result. Summary, patterns and page 2 used the same snapshot. Captured responses and checks are in `docs/evidence/api-*.json` and [phase2-checks.json](evidence/phase2-checks.json).

Implementation references: [FastAPI query models](https://fastapi.tiangolo.com/tutorial/query-param-models/), [error handling](https://fastapi.tiangolo.com/tutorial/handling-errors/), [lifespan](https://fastapi.tiangolo.com/advanced/events/). The synchronous route functions match the synchronous SQLAlchemy/psycopg workflow; an async rewrite is not required for this workload.
