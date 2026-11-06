# Progress — Know Your Commute

Project owner: **Wentao Wu**. Updated 5 November 2026 (America/Toronto).

**Current status: Phases 0–3 complete locally; Phase 4 gates passed locally and on GitHub.** The real-data importer/API/dashboard now have backup/restore verification, query-plan evidence, read-only API grants and passing automated browser checks. The source is public and the deployment container passed remote build/startup checks. Neon database setup is now verified; the public web-service release remains pending. See the latest Neon milestone below. The existing portfolio remains separate and unchanged.

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
- The API and browser app now work locally. GitHub Actions now passed on the public repository (see Phase 4); no external app deployment or users are claimed.

## Phase 2 — Complete locally

- Added typed read-only FastAPI endpoints for route search, summaries, observed-day/cause patterns, bounded source-record pagination, process health, database readiness and public data health.
- One shared query model validates route/date/snapshot inputs. Dates are inclusive; unknown/repeated parameters and invalid sort/page inputs fail clearly.
- Every response pins one snapshot in a read-only repeatable-read transaction. The browser passes that snapshot to charts and subsequent pages, so separate HTTP requests do not mix source versions during a refresh.
- Public projections exclude raw diagnostics, paths, headers and private source provenance. Secret-looking exception text was deliberately used in privacy tests and did not reach responses.
- **63 Python cases passed, 0 skipped**, including 20 new API/database cases plus the original 43. A known Starlette/httpx test-client deprecation warning remains; it does not fail the current pinned checks.
- Actual HTTP requests on the real database returned 65 route-102 January records, 65 duration samples and a 20-minute recorded median. Summary, daily/cause totals and page 2 reconciled on the same snapshot. Missing API paths returned JSON 404 instead of SPA HTML.
- Evidence: `docs/evidence/phase2-checks.json`, captured API responses and OpenAPI. Contract: `docs/api.md`.

## Phase 3 — Complete locally

- Built the React/TypeScript/Vite dashboard in charcoal, off-white and warm amber. It reads the actual API rather than hardcoded success statistics.
- Added route/date controls, recorded-count/duration metrics, daily and cause charts, chart data tables, bounded source rows with flags, pagination/sort, data health and About/definitions pages.
- Route/date/sort/page filters survive reload and browser back/forward. Snapshot selection is pinned for the current view; a fresh shared URL selects the then-active source.
- Verified desktop and 375-pixel mobile layouts through the app's actual browser-control tools. No page-wide mobile overflow; the source table scrolls inside its own region. Route input/Enter submission and pagination focus were checked.
- Verified loading, empty, partial-coverage and real backend-unavailable states. Restarting the test backend and pressing Try again recovered successfully.
- Browser QA caught and fixed a page-change scroll jump, a date edit lost when only draft React state was read, and ambiguous cross-year range labels. Date submission now reads displayed FormData values; page updates retain content/focus.
- Route 102, January 1–15, showed **39 records**, matching an independent calculation from the original CSV. The full January view remains 65 / median 20 / numeric n=65.
- Strict TypeScript checks and the production build passed. Explorer/charts load separately from About/Data health. The final main preview returned no console errors/warnings.
- `scripts/run_local.py` serves the built frontend and API with one loopback-only command; real HTTP requests verified the launcher. Preview processes are stopped after QA; PostgreSQL remains running.
- Evidence: `docs/evidence/phase3-checks.json` and `docs/screenshots/`.

## Phase 4 — Verified locally and on GitHub

- **68 Python checks passed, 0 skipped**, including 43 PostgreSQL integration cases. Added real dump/restore consistency during a concurrent correction, failed-restore cleanup, corrupt archive refusal and a SELECT-only API role check.
- **Eight Playwright cases passed** across desktop/mobile, covering filters/history/pagination, loading/empty/partial/failure/retry states, contained mobile layout and Home Screen assets. The initial restricted browser launch failed before any page ran. Normal process approval enabled execution. One first-run pagination timeout passed in isolation and in the subsequent complete suite; no unproven product fix or automatic retry was introduced.
- Restored the real database's 54,611,555-byte custom dump into a newly generated scratch database. All eight table fingerprints matched; the scratch database was removed. The live route-102 January report remained unchanged at 65 records. Evidence: `docs/evidence/backup-restore.json`.
- The backup's table hashes and dump share an exported PostgreSQL snapshot, so a refresh cannot make their expected contents disagree. Dumps/credentials/private diagnostics stay out of Git and public artifacts.
- Measured the actual route/date and all-data SQL summaries. The 65-row route filter used `ix_delay_route_date`; the 107,349-row broad query used a sequential scan. Median of five repeated calls: 0.429 ms and 16.329 ms. Both plans used cached blocks; no additional index or true cold-cache result is claimed. Evidence: `docs/evidence/query-measurements.json`.
- Added a manual and opt-in weekly refresh workflow, per-workflow concurrency, existing database-lock protection, public freshness output and seven-day public-source artifacts. No production secret exists and scheduled imports stay disabled until explicitly configured after a manual run.
- Added explicit grants for a separately provisioned API login. All public reporting endpoints worked under SELECT-only grants. Record writes, schema creation and raw/rejected-table reads were refused by PostgreSQL.
- Actual [GitHub Actions run](https://github.com/d-wt-wu/know-your-commute/actions/runs/42126800606) passed on implementation commit `98721d3`: **68 Python tests**, **eight browser cases**, frontend build, Docker image build and running-container smoke check. The first run caught missing PostgreSQL 17 client packages; using the official signed apt repository fixed that setup failure. Evidence: `docs/evidence/github-ci.json`.

## Phase 5 — Release prepared; hosting not provisioned

- Prepared a multi-stage Docker image for the API/frontend, non-root runtime, bounded database connection pool, secret-excluding build context and a Render Free candidate configuration using external PostgreSQL. Docker is unavailable on this Mac; the image was built and started successfully on the GitHub Linux runner.
- Added a web app manifest, generated PNG/Apple touch icons, standalone metadata, larger mobile touch controls and Safari installation instructions. Eight browser cases verify the assets are really served. A physical iPhone installation remains unverified until the HTTPS website exists. No native App Store project is claimed.
- Checked current official Render/Neon/Apple limits and documented the website-first route in `docs/deployment.md`: proposed Render Free + Neon Free, no domain purchase or Apple membership needed for a Home Screen web app. Account/plan choices remain the owner's decision.
- Published the source/history to the public GitHub repository `https://github.com/d-wt-wu/know-your-commute` and verified its passing remote checks.
- Remaining: complete hosting sign-ins/permissions and confirm the Free plans, migrate/import the external database with a private writer connection, deploy with a separate read-only API connection, verify HTTPS and physical iPhone installation, then finish the case study/demo. No live app URL, deployment, users, purchase or portfolio edit is claimed. Render requires GitHub identity/email authorization; Neon is at sign-in. Automatic approval review rejected initiating Neon’s GitHub sign-in because new third-party account access needs explicit authorization. Neither hosting account authorization nor provisioning was completed.

Recovery/automation details: `docs/operations.md`. The existing portfolio, paper and photos remain separate. True cold-cache and hosted end-to-end measurements remain future work; local summary timings are not production guarantees.

## Neon connection — verified 5 November 2026

- Linked the owner-specified project `shiny-frog-92110874`, production branch, and deployed the existing Postgres-only policy. Three private environment variables were pulled; no paid service or extra backend primitive was added.
- The existing Neon database is PostgreSQL **18.6**. Applied Alembic migration 0001 and checked Core metadata agreement before importing the attributed official bundle. Loaded **107,349 delay rows** and **46 lookup entries**; identical reruns returned `no_change`.
- Created an ordinary SQL API login with five explicit read grants. The real hosted connection used TLS and refused writes/raw-record reads. A complete setup rerun preserved the private credential file and reused the login.
- Kept psycopg/SQLAlchemy for the Python backend. API reads select the pooled API connection; writers/migrations/backups select the direct connection and reject pooler URLs. Environment files remain private and ignored.
- Added root `npm run build` / `npm start`, explicit environment-file loading and a read-only startup guard. **73 Python tests passed, zero skipped**; the root config/frontend build passed. CI now also targets major 18, matching the hosted database.
- **Two read-only browser journeys passed against real Neon**, desktop and mobile: source summary/patterns, route/date filtering, paging, reload/history and data health. Route 102 January returned 65 / median 20 / n=65; January 1–15 returned 39.
- Fetched the exact requested Neon skill; it matched the installed file. All seven local skills were up to date. Added a project-pinned OAuth MCP entry because the bundled server was absent from the current Codex inventory. No inline API key or existing global-server rewrite. MCP runtime/authentication is not verified in this chat.
- Actual failures: CLI browser auth timed out once; normal global install hit EACCES, so `npx neon@latest` is the fallback; local database tests needed network access before all cases passed. Hosted backup verification needs PostgreSQL 18 clients and remains unrun.
- The public website host and physical iPhone install remain pending. The app was started locally against hosted Neon and stopped after tests. Existing portfolio/paper/photos remain separate.

Evidence and full change log: `docs/neon-setup.md`, `docs/evidence/neon-checks.json`, `neon-database.json`, `neon-rerun.json`.

- Final Neon integration CI: [run 42140733466](https://github.com/d-wt-wu/know-your-commute/actions/runs/42140733466) passed on implementation commit `3c43bc2`, with PostgreSQL 17/18, 73 Python cases and eight synthetic browser cases per job, plus both container build/startup checks. Real-Neon desktop/mobile checks remain separately verified.
- Render GitHub authorization is complete, but its separate account-confirmation form requires the owner to review the prefilled email and terms before account creation. No Render service has been created.
