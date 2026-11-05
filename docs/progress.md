# Progress — Know Your Commute

Project owner: **Wentao Wu**. Updated 5 November 2026 (America/Toronto).

## Phase 0 — Complete

- Read the full chosen project plan and dated career context. Copied the plan into `docs/project-plan.md`; no project brainstorming was reopened.
- Checked ancestor/local guidance and Git boundaries. No applicable `AGENTS.md` was found; the new project is an independent Git repository. The existing portfolio is a separate repository and was not edited.
- Inspected Python, Node, Docker/PostgreSQL and build tools. Used an isolated Python 3.13 environment; locked dependencies. Node 22.17.1 is available but no frontend has been scaffolded before the data gate.
- Downloaded official CKAN metadata, README XLSX, the 2025-onward CSV and the code lookup. Resolved resource IDs to their current URLs; recorded SHA-256 hashes, retrieval times and source modification strings.
- Verified the exact 11-column CSV schema, which differs from the older README names. Recorded the meanings of delay/gap and unresolved identifier, timezone, service-day and zero-value semantics in `data-contract.md`.
- Profiled 107,349 real records: all are usable under the minimum date contract; 46,723 have at least one quality flag. Observed dates span 2025-01-01 through 2026-09-30. These are Python validation results, not a database import or reliability measure.
- Saved a deterministic, attributed 20-row fixture with original row positions, plus the complete small lookup. Preserved unknown codes, encoding defects, route ambiguity, weekday mismatches and repeated payloads.
- Compiled checksum-verified PostgreSQL 17.11 inside ignored `work/`. Compose and a project-local startup script provide clear setup paths. The actual server startup restriction is recorded below.

## Phase 1 — Implemented; acceptance gate pending

Implemented:

- SQLAlchemy Core schema and frozen Alembic migration `0001` for resources, snapshots, attempts, raw rows, analytical rows, code versions and rejects.
- Official downloads with bounded size/timeouts/retries, HTML detection, immutable originals and checksum-verified bundle replay.
- Per-resource locks, an independently committed attempt log, staged count reconciliation, pinned lookup versions and atomic promotion. Same-byte no-change, parser/lookup reprocessing and source reactivation paths are present.
- Route/date SQL reports with numeric duration sample counts, observed-day counts, cause mapping and traceable examples. Bound parameters and one repeatable-read snapshot keep the queries consistent.
- Validation/download unit cases and 20 PostgreSQL integration cases, including actual child-process death, rollback, corrected cumulative data, simultaneous importers and refresh during reporting.
- GitHub Actions configuration using a real PostgreSQL service. It has not run remotely; nothing has been uploaded or deployed.
- `scripts/verify_phase1.py` performs the actual database gate, real import/rerun and independent raw-CSV/report comparison, and writes success evidence only on completion.

Verification actually run:

| Check | Result |
| --- | --- |
| `python scripts/profile_sources.py --write-fixture` with project Python path | Real source opened/profiled; fixture generated; original hashes verified |
| `pytest` without `TEST_DATABASE_URL` | **23 passed, 20 skipped**; skips are explicitly the unavailable PostgreSQL group |
| PostgreSQL-dialect compile of frozen migration upgrade/downgrade | Passed; generated SQL inspected; not a migration applied to a database |
| CLI help and Python compilation | Passed |
| Real `commute fetch --directory data/verified-fetch` | Passed; captured official resources match the inspection hashes; evidence in `docs/evidence/source-fetch.json` |
| Wheel/source-distribution build | Passed; all four SQL report resources are included in the wheel |
| `uv lock --check` | Passed |
| PostgreSQL source compilation | Passed; official checksum verified |
| `python scripts/local_postgres.py setup` inside app runner | **Blocked:** `initdb` cannot create a System V shared-memory segment (`shmget`, Operation not permitted) |

All ten files in the existing portfolio source were hashed before and after implementation and were unchanged, including its paper/photo assets. The local project has no remote or deployment configured.

**Not yet claimed:** a real PostgreSQL import, passing database integration tests, SQL output from PostgreSQL, import/query performance, a running API, a browser demo, deployed URLs or users. A 107,349-row Python profile does not substitute for the database acceptance gate.

## Blocking action and next task

The PostgreSQL binaries and startup script are ready. The restricted app runner cannot start the server. Run the following in the Mac's own Terminal, or start the server there and resume this chat:

```sh
cd /Users/davidwu/Documents/Codex/know-your-commute
.venv/bin/python scripts/verify_phase1.py --local-postgres
```

This is the complete gate, not a permission request for hosting. It uses the already archived official source and a separate `commute_test` database. If any check fails, retain the failure output and fix the implementation; do not mark Phase 1 complete. The script appends a verified completion entry and saves actual evidence only after every check passes.

Once that gate passes, continue Phase 2's tested FastAPI reporting API. Build the React/TypeScript/Vite dashboard only after the data workflow is verified. Preserve charcoal/off-white/warm amber and the existing portfolio's paper/photos; no portfolio work is authorized in this slice.
