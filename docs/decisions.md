# Implementation decisions

## 1 — Finish the data workflow before the dashboard

Keep the selected TTC project and the original plan. The current milestone is an import plus a SQL report. FastAPI, React/TypeScript/Vite and the charcoal/off-white/amber dashboard follow once database tests pass. No portfolio edits, hosting registrations, domain work or purchases are part of this slice.

The available system Python is 3.10, but a usable Python 3.13 is installed under Anaconda. This project uses its own 3.13 virtual environment and a committed uv lockfile; it does not change the shared Anaconda environment. SQLAlchemy Core 2.1.8, Alembic 1.20.1 and psycopg 3.3.8 resolved during setup. FastAPI/frontend dependencies will be locked when their phases begin.

## 2 — PostgreSQL stays the database

This workload does not require distributed infrastructure. PostgreSQL provides transactions, constraints, JSONB for source payloads, indexes and readable analytical SQL. Core keeps queries explicit; Alembic gives schema changes a reviewed history. SQLite or a JSON-only preview would not verify PostgreSQL behaviour.

No Docker/PostgreSQL/Homebrew installation was found. A checksum-verified PostgreSQL 17.11 source build was completed entirely inside ignored `work/`. A Compose configuration also targets major 17. The app runner denies System V shared-memory creation during `initdb`, so the initial server needs to be started in Wentao's Terminal. No database integration results are claimed before that step. The optional local build is loopback-only and omits ICU/readline/zlib; it is for development, not a production server configuration.

## 3 — A hash identifies bytes, not an incident

The source has `_id`, but no documentation promises incident uniqueness or stable identifiers between cumulative exports. A snapshot UUID plus CSV row position identifies the ingested record. Exact source bytes are hashed for provenance. A separate payload fingerprint excludes `_id` to flag same-looking rows; it never removes them.

**Explain it:** If two buses produce identical recorded values, discarding one on a guess would change the count. Keeping both makes the uncertainty visible and reversible.

## 4 — Replace a cumulative snapshot atomically

A corrected file can edit, add or remove old rows. Appending it would count both old and corrected data. Build a complete immutable snapshot, verify the staged counts, then update one active pointer and the success audit in the same transaction. Reports select only that pointer. Retain old snapshots for provenance; a reversion can reuse one.

Every attempt starts an independently committed audit row before download. A session advisory lock covers downloading, validation and promotion for one resource. After an exception, rollback removes the staged rows and the audit records failure. A process crash leaves a running audit row for the next lock holder to close as interrupted. Tests include ordinary failure, competing importers and actual subprocess exit before commit; they require a running PostgreSQL server.

## 5 — Pin the lookup too

Cause codes and descriptions are separate data. A changing lookup could otherwise relabel an older report without changing its counts. Include the lookup snapshot, parser and contract versions in processing identity. A new lookup version may legitimately reprocess identical delay bytes. Reports use the delay snapshot's pinned mapping, even if a newer lookup is active.

## 6 — Treat missing, zero and unknown as separate facts

Only an unusable Date or malformed row width quarantines an otherwise structurally valid delay row. Missing route/category/time/duration values remain accepted and flagged. Invalid duration strings become null; reported zero remains zero with a warning. The valid-value sample count must accompany a median. Unknown causes remain visible as unmapped.

Route identifiers are text parsed conservatively from historical labels. Branches are not merged, and no current TTC route-name catalogue is invented. Timezone/overnight interpretation remains unconfirmed, so no UTC conversion is made.

## 7 — One report reads one snapshot

Run the report's queries in a read-only repeatable-read transaction, capture the active snapshot once, then bind its ID into every query. This prevents a refresh between the summary and the cause breakdown from mixing versions. Dates use explicit inclusive bounds; all values are bound parameters. Initial route/date indexes are hypotheses until a real PostgreSQL query plan is measured.

## 8 — Keep the evidence modest

Commit small attributed fixtures, hashes, a profile, tests and documentation. Ignore originals, environment files, build tools, database files and dumps. CI uses fixtures with a real PostgreSQL service and fails if database tests are accidentally disabled. No claims of deployments, users, successful CI runs, database timing or résumé impact are made without evidence.
