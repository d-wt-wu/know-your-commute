# Implementation decisions

## 1 — Finish the data workflow before the dashboard

Keep the selected TTC project and the original plan. The import and SQL report passed first; the tested FastAPI layer and charcoal/off-white/amber React dashboard followed. No portfolio edits, hosting registrations, domain work or purchases are part of these local milestones.

The available system Python is 3.10, but a usable Python 3.13 is installed under Anaconda. This project uses its own 3.13 virtual environment and a committed uv lockfile; it does not change the shared Anaconda environment. SQLAlchemy Core 2.1.8, Alembic 1.20.1 and psycopg 3.3.8 resolved during setup. FastAPI 0.162.0, Pydantic 2.14.3 and uvicorn 0.54.0 were added for the API. React 19.3.1, Vite 8.3.6, React Router and Recharts are locked in the frontend package lockfile. React Router supplies URL/history behaviour; Recharts is the single chart library.

## 2 — PostgreSQL stays the database

This workload does not require distributed infrastructure. PostgreSQL provides transactions, constraints, JSONB for source payloads, indexes and readable analytical SQL. Core keeps queries explicit; Alembic gives schema changes a reviewed history. SQLite or a JSON-only preview would not verify PostgreSQL behaviour.

No Docker/PostgreSQL/Homebrew installation was found. A checksum-verified PostgreSQL 17.11 source build was completed entirely inside ignored `work/`. A Compose configuration also targets major 17. The app runner denies System V shared-memory creation during `initdb`, so Wentao started the server from Terminal. After local connection access was granted, all 20 PostgreSQL integration cases and the real import/rerun passed. The optional local build is loopback-only and omits ICU/readline/zlib; it is for development, not a production server configuration.

## 3 — A hash identifies bytes, not an incident

The source has `_id`, but no documentation promises incident uniqueness or stable identifiers between cumulative exports. A snapshot UUID plus CSV row position identifies the ingested record. Exact source bytes are hashed for provenance. A separate payload fingerprint excludes `_id` to flag same-looking rows; it never removes them.

**Explain it:** If two buses produce identical recorded values, discarding one on a guess would change the count. Keeping both makes the uncertainty visible and reversible.

## 4 — Replace a cumulative snapshot atomically

A corrected file can edit, add or remove old rows. Appending it would count both old and corrected data. Build a complete immutable snapshot, verify the staged counts, then update one active pointer and the success audit in the same transaction. Reports select only that pointer. Retain old snapshots for provenance; a reversion can reuse one.

Every attempt starts an independently committed audit row before download. A session advisory lock covers downloading, validation and promotion for one resource. After an exception, rollback removes the staged rows and the audit records failure. A process crash leaves a running audit row for the next lock holder to close as interrupted. Tests passed against PostgreSQL for ordinary failure, competing importers and actual subprocess exit before commit.

## 5 — Pin the lookup too

Cause codes and descriptions are separate data. A changing lookup could otherwise relabel an older report without changing its counts. Include the lookup snapshot, parser and contract versions in processing identity. A new lookup version may legitimately reprocess identical delay bytes. Reports use the delay snapshot's pinned mapping, even if a newer lookup is active.

## 6 — Treat missing, zero and unknown as separate facts

Only an unusable Date or malformed row width quarantines an otherwise structurally valid delay row. Missing route/category/time/duration values remain accepted and flagged. Invalid duration strings become null; reported zero remains zero with a warning. The valid-value sample count must accompany a median. Unknown causes remain visible as unmapped.

Route identifiers are text parsed conservatively from historical labels. Branches are not merged, and no current TTC route-name catalogue is invented. Timezone/overnight interpretation remains unconfirmed, so no UTC conversion is made.

## 7 — One report reads one snapshot

Run the report's queries in a read-only repeatable-read transaction, capture the active snapshot once, then bind its ID into every query. This prevents a refresh between the summary and the cause breakdown from mixing versions. Dates use explicit inclusive bounds; all values are bound parameters. Initial route/date indexes are hypotheses until a real PostgreSQL query plan is measured.

## 8 — Keep the evidence modest

Commit small attributed fixtures, hashes, a profile, tests and documentation. Ignore originals, environment files, build tools, database files and dumps. CI uses fixtures with a real PostgreSQL service and fails if database tests are accidentally disabled. No claims of deployments, users, successful CI runs, database timing or résumé impact are made without evidence.

## 9 — What the first database run caught

The first PostgreSQL run applied and round-tripped the migration, then exposed a lookup-loading bug: passing SQLAlchemy's result object directly to `dict()` followed an unsupported mapping path. Explicitly unpacking the `(code, description)` rows fixed it. All 43 tests then passed, including the 20 database cases. This is a concrete example of why passing parser unit tests did not establish that the database workflow worked.

The subsequent first real import and identical rerun are measured in `docs/evidence/phase1-checks.json`. These are single local observations with an already running server, not controlled performance benchmarks or user-impact claims.

## 10 — Keep a view stable across HTTP requests

A read-only transaction stabilizes one response, but cannot stabilize separate summary, chart and pagination requests by itself. Each reporting response therefore returns a snapshot ID. The browser gets the summary first and pins that ID for patterns/records and subsequent pages. A new filter or explicit source check can select the current active import. The API also allows exact snapshot reproduction independently from the browser's filter-only share URL.

The public response models are deliberately smaller than internal import/health dictionaries. They expose meaningful provenance and safe statuses while excluding raw failure traces, private paths and request headers. API errors were tested with secret-looking exception text to ensure it did not reach the response.

## 11 — Let source uncertainty shape the interface

The dashboard plots observed daily counts and source causes, provides chart data tables and keeps quality flags inspectable on source rows. It does not invent zero-count periods, reliability scores, route-name mappings or an hour heatmap while overnight/timezone semantics remain unconfirmed. Source-wide quality and matching-row quality are labelled separately.

Date inputs submit their displayed values through FormData. Browser QA caught that relying only on draft React state could lose an accessibility-driven date edit. Pagination keeps existing content and button focus during a page fetch, avoiding a scroll jump caused by removing the whole result view. Multi-year labels include both years. These are browser-level behaviours that API-only tests could not establish.

## 12 — Separate real-source QA from synthetic browser CI

Local browser verification used the real PostgreSQL import and independently checked route/date totals. The Playwright suite uses an explicitly labelled synthetic 40-row fixture in `commute_browser_test`; its seeding command refuses any other database name. No test fixture replaces the main `commute` database. All eight desktop/mobile cases now pass locally, including filters/history/pagination, failures/retry, layout and Home Screen asset delivery. Running Chromium required the normal process approval mechanism because the restricted app runner could not launch it. Remote CI is recorded separately in progress.

## 13 — Verify a backup against the state actually dumped

A row count alone cannot detect corrupted or changed content. Export one repeatable-read snapshot, hash every row of every application table in primary-key order, and give the same snapshot to pg_dump. Restoring that dump into a new scratch database must reproduce every hash, even if a refresh commits meanwhile. No restore command overwrites an existing database. The real 107,349-row source passed this drill; private dumps stay outside Git and public artifacts.

## 14 — Start with the website and iPhone Home Screen version

The existing responsive interface and API already support the first useful phone experience. Add a manifest, app icons, standalone metadata, larger touch controls and clear Safari installation instructions. Keep record requests online so cached API results do not obscure source freshness. A native client can reuse the API later, but Apple membership and App Store review are separate decisions. This keeps the chosen Python/SQL project focused while making its actual interface usable on phones.

## 15 — Measure before adding another index

The real selective route-102/January summary used `ix_delay_route_date` for 65 rows. The all-data summary used a sequential scan over 107,349 rows. Repeated local summary calls had medians of 0.429 ms and 16.329 ms respectively; both plans read cached blocks. No index change is justified by those observations. Preserve the plans and actual conditions; do not describe a fresh connection as a cold-cache result or invent an optimization percentage.
