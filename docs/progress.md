# Progress — Know Your Commute

Project owner: **Wentao Wu**. Updated 5 November 2026 (America/Toronto).

**Current status: Phases 0 and 1 complete.** The real PostgreSQL workflow is verified. Next: Phase 2, a tested FastAPI reporting API. The React dashboard follows the API; the existing portfolio remains separate and unchanged.

## Phase 0 — Complete

- Read the full chosen project plan and dated career context; copied the plan into `docs/project-plan.md`. No project brainstorming was reopened.
- Checked local guidance and Git boundaries. No applicable `AGENTS.md` was found. The project is its own Git repository; it has no remote or deployment configured.
- Used a project-local Python 3.13 environment and committed the dependency lockfile. Node 22.17.1 is available for the later frontend. No shared Anaconda packages were changed.
- Downloaded official CKAN metadata, README XLSX, the 2025-onward CSV and the code lookup. Recorded URLs, SHA-256 hashes, UTC retrieval times and publisher modification strings.
- Verified the real 11-column CSV schema, which differs from the older README's names. The data contract records duration definitions and unresolved identifier, timezone, overnight-service and zero-value semantics.
- Profiled 107,349 records dated 2025-01-01 through 2026-09-30. Saved a deterministic attributed 20-row fixture, its original source row positions and the complete small lookup.
- Preserved unknown codes, published encoding issues, route ambiguity, weekday mismatches and repeated payloads. No deduplication removed records.
- Built checksum-verified PostgreSQL 17.11 inside ignored `work/`, with Compose as another setup path. Wentao started the server from Terminal after the app runner blocked its initial shared-memory creation.

## Phase 1 — Complete

Verified 05 November 2026 at 15:19 EST. Machine: local macOS/arm64, Python 3.13.5, PostgreSQL 17.11. Full evidence: `docs/evidence/phase1-checks.json`.

| Acceptance check | Actual result |
| --- | --- |
| Unit and PostgreSQL integration suite | **43 passed, 0 skipped**; 20 PostgreSQL cases |
| Alembic | Migration 0001 applied; downgrade/upgrade round trip passed; Core metadata check reported no pending operations |
| First real import | 46 official lookup entries and **107,349 delay records** accepted; 0 rejected delay rows |
| Quality preservation | 46,723 delay records retained with one or more flags; 599 rows in repeated-payload groups kept |
| Identical real-source rerun | Both resources returned `no_change`; active snapshot IDs and analytical counts unchanged |
| Corrected cumulative file | Integration test replaced the active version while retaining old raw provenance |
| Bad headers, bad dates, HTML and timeout | Failure/rejection cases passed; previous good active data stayed available |
| Failure after staging | New rows rolled back; retry succeeded |
| Actual child-process exit before commit | No partial snapshot promoted; next import marked the abandoned run interrupted and succeeded |
| Competing importers | Second attempt was refused before loading; later retry was safe |
| Lookup/parser revisions and source reversion | Pinned mapping preserved old meaning; deliberate reprocessing/reactivation passed |
| Report during refresh | Summary, daily counts and causes stayed on the same selected snapshot |
| Real SQL report, exact route 102, January 2025 inclusive | **65 records**, 65 numeric delay samples, 1 reported zero; median recorded delay **20 minutes** |
| Independent raw-CSV check | Record count, numeric sample count and median matched; daily/cause totals each reconciled to 65 |
| CLI and local database helper | Real CLI report matched captured results; SQL-based server status and setup rerun succeeded |

The SQL report is captured in `docs/evidence/route-102-2025-01.json`; latest attempts, last successes and active versions are captured separately in `docs/evidence/data-health.json`.

### What the database tests caught

The first PostgreSQL run caught a lookup-loading bug that parser unit tests did not expose: `dict()` treated SQLAlchemy's result as a mapping rather than consuming row pairs. Explicit row unpacking fixed it. The full 43-test suite then passed. This is an explainable regression caught by testing the real database workflow.

The startup script's process-only status check also misread a Terminal-started server inside the restricted runner. It now verifies the connected server's data directory through SQL. Server startup/stop still belongs in Terminal while the app's process/shared-memory restriction applies; connecting to the running server works after local connection access is granted.

### Measurements, with limits

One observed local gate run, with an already running server and successful first imports:

- Lookup plus 107,349-row import: 5.715 seconds.
- Same-byte lookup/delay rerun: 0.020 seconds.
- Route/date report: 5.27 ms.
- Database size after the gate: 79,345,331 bytes.

These are recorded single-run observations, not controlled cold-cache benchmarks, production service guarantees or résumé impact claims. The initial validation/download-only record is preserved as historical evidence in `docs/evidence/local-checks.json`; it is superseded by the successful database gate.

## Other verification

- Real `commute fetch` reproduced the inspected resource hashes; evidence in `docs/evidence/source-fetch.json`.
- Wheel/source-distribution build passed and packaged all four report SQL resources; raw data, database files, environment secrets and local tools were excluded.
- Dependency lock check and Python compilation passed.
- All ten files in the existing portfolio source were hashed before and after implementation and were unchanged, including the research paper/photo assets.
- GitHub Actions is configured locally, but no remote CI run, public repository, live API, browser app, deployment or users are claimed.

## Next task — Phase 2

Implement the read-only FastAPI route listing, shared route/date filters, summaries/patterns, stable record pagination and data-health response models. Reuse the snapshot-selection/report definitions and test each endpoint against a hand-checked PostgreSQL fixture. Keep internal provenance/error diagnostics out of the public response.

After that API gate, build the React/TypeScript/Vite dashboard with charcoal, off-white and warm amber, accessible filters/charts, URL state and explicit historical-data limitations. No portfolio changes, account provisioning or purchases are needed for those local phases.
