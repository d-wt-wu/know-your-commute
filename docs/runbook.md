# Local setup and recovery

Run commands from the project directory. No hosting account, domain or paid service is required. PostgreSQL 17 and Python 3.13 are the current local targets.

## Environment

```sh
uv sync --locked
source .venv/bin/activate
export PYTHONPATH="$PWD/src"
export UV_CACHE_DIR="$PWD/work/uv-cache"
export NPM_CONFIG_CACHE="$PWD/work/npm-cache"
set -a
source .env.example
set +a
```

If uv is absent but Python 3.13 is available, a project-local bootstrap is sufficient:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install uv==0.13.7
UV_CACHE_DIR="$PWD/work/uv-cache" .venv/bin/uv sync --locked
```

On this Mac, the existing Python 3.13 used for bootstrap is `/opt/anaconda3/bin/python3.13`. No shared packages were changed. The app runner marks ignored `.pth` files hidden, which can prevent editable package discovery on macOS/Python 3.13; the explicit `PYTHONPATH` above handles this. Normal installed wheels do not require that workaround.

The example database credentials are for a loopback-only developer database. Production credentials and separate read-only API/import roles will be configured during deployment; do not reuse these examples publicly. Real `.env` files stay ignored.

## Run the dashboard and API

With the local database already running and loaded:

```sh
npm --prefix web ci
npm --prefix web run build
.venv/bin/python scripts/run_local.py
```

Open `http://127.0.0.1:8000/`. The current checkout already has a build, so the launcher alone is enough until source changes. It serves the frontend and API on one origin, binds only to loopback and respects an explicitly provided `DATABASE_URL`; otherwise it uses the existing local example. Ctrl+C stops this app process without stopping PostgreSQL.

For development, keep the API on 8000 and run `npm --prefix web run dev` in a second terminal. Vite serves 5173 and proxies `/api`; no broad CORS policy is needed. Rebuild and reload after frontend source changes when using the built single-origin server. Direct links to `/data-health` and `/about` work; unknown API/assets keep their error status.

The API reference is at `/docs`; the contract and snapshot-pinning behaviour are documented in `docs/api.md`. Clock-time heatmaps are deliberately deferred while source timezone/overnight semantics remain unresolved.

## Browser verification and CI

The actual local dashboard was checked in the app's browser using real records. Verified flows include route/keyboard submission, date changes, pagination with focus retained, reload, back/forward, sort order, empty results, partial coverage, a real backend-unavailable response and successful retry after service recovery. Mobile checks used a 375-pixel viewport, confirmed no page-wide overflow and scrolled the table independently. Final screenshots are in `docs/screenshots/`.

The prepared automated browser suite uses a separate synthetic database, never the real-source database:

```sh
export BROWSER_TEST_DATABASE_URL='postgresql+psycopg://commute:commute_local@127.0.0.1:54329/commute_browser_test'
.venv/bin/python scripts/seed_browser.py
cd web
npx playwright install chromium
npm run test:e2e
```

The seeder can create/reset only the exact database `commute_browser_test`. Its 40 synthetic rows are labelled in code and deliberately exercise missing duration, zero, unknown code and pagination. Its route-102 expected count is 35, distinct from the real source's January count of 65. The suite owns port 8002, starts the built app, and refuses to reuse an existing server. Use `npm run test:e2e -- --list` for collection only.

Current verification: seeding and its PostgreSQL summary were checked, and all six desktop/mobile cases collected. The suite's headless execution and remote GitHub Actions execution are still unverified; local GUI QA used the app's browser-control tools. CI is configured to install the browser and run these cases after the Python checks/frontend build. Do not describe the prepared workflow as a passing remote CI run.

## Database options

If Docker is installed:

```sh
docker compose up -d --wait db
docker compose exec db createdb -U commute commute_test
```

`createdb` is a one-time step; an already-existing-database message is harmless. The Compose volume survives container restarts. Do not use `docker compose down -v` as a routine stop because it deletes the developer database.

If Docker/PostgreSQL are absent, the optional source build is isolated to `work/`. It needs `cc`, `make` and standard Unix tools; macOS command line tools are already installed on the inspected machine. The official PostgreSQL 17.11 source is checked against a recorded SHA-256 before compilation. Nothing is added to system paths, applications or startup services.

```sh
python scripts/local_postgres.py setup
python scripts/local_postgres.py status
python scripts/local_postgres.py stop
python scripts/local_postgres.py start
```

`setup` builds if necessary, creates only its own data directory, starts a loopback-only server on 54329, and creates `commute` and `commute_test` if absent. The build omits ICU, readline and zlib for the local workflow. Its data files, logs, binaries and build source are ignored by Git. It does not start at login. Do not copy this configuration into production.

**Observed app restriction:** `initdb` failed at `shmget(... size=56 ...)` with `Operation not permitted` in this app's restricted runner. This is a real startup blocker, not a failed data test. Run `setup` in your own Mac Terminal; then the app can use the running loopback server. Do not change PostgreSQL's source or substitute another engine to hide the limitation.

Resolved for this checkout: Wentao started the server from Terminal, local connection access was granted, and the full Phase 1 gate passed. The status helper now checks the connected server's data directory through SQL; process inspection alone can incorrectly report an externally started server as stopped inside the app. Restarting a stopped server still belongs in Terminal while the startup restriction applies.

## Apply migrations, test and import

```sh
alembic upgrade head
pytest
commute refresh
commute data-health
commute report --route 102 --start 2025-01-01 --end 2025-01-31
```

The initial source inspection already archived files in `data/raw/` on the working machine. To import these exact bytes rather than redownload:

```sh
commute import-bundle --manifest data/raw/download-manifest.json
```

That untracked bundle is available in this checkout, not guaranteed after cloning. `commute fetch` or `refresh` creates new content-addressed files and a manifest path. Manifests live beside their archived files; `import-bundle` verifies content hashes. `docs/source-manifest.json` is a tracked record of the inspected bundle's provenance, not an independently downloadable bundle containing the raw data.

The lookup imports before delays. A lookup failure stops the bundle workflow. If lookup succeeds and delays fail, existing reports still use the old delay snapshot's pinned lookup, so causes are not silently relabelled. Inspect the two resource attempts separately.

For a single reproducible gate, including the real import, safe rerun, PostgreSQL tests and independent raw-CSV/report comparison:

```sh
.venv/bin/python scripts/verify_phase1.py --local-postgres
```

Use this command in Terminal while the app's startup restriction applies. If PostgreSQL is already available through Docker/another installation and the URLs are configured, omit `--local-postgres`. The script requires every database test to run, then imports the archived official bundle (or downloads one if absent), checks a safe real rerun, and checks route 102/January 2025 against a separate calculation from source cells. It writes `docs/evidence/` and appends a success entry to progress **only if the whole gate passes**. Timings carry their actual conditions and existing-snapshot statuses. A failed prerequisite is logged in ignored `work/phase1-failed-check.json`.

## Reproduce Phase 0

```sh
commute fetch
python scripts/profile_sources.py --manifest data/raw/download-manifest.json --write-fixture
```

For a new download, replace the example manifest with the actual returned path. The existing default reproduces the original inspected source while those archived bytes remain available. The script verifies the source/lookup/README hashes, profiles all accepted rows, writes the source manifest/profile, and deliberately regenerates the tracked 20-record fixture when `--write-fixture` is supplied. Review the diff if using a later source; source changes can legitimately change that fixture. See `tests/fixtures/manifest.json` for original row positions and sampling rules.

## Tests and CI

- Unit tests use small fixtures and simulated HTTP responses. They require no network or database.
- Integration tests use a dedicated PostgreSQL database whose name ends in `_test`. Their setup applies Alembic migrations and checks agreement with Core metadata. Each test truncates only that configured test database.
- Scenarios include corrected cumulative files, identical-looking rows, same-byte reruns, malformed input, missing/zero durations, schema additions, lookup/parser changes, snapshot reversion, transaction rollback, actual child-process death, competing importers and consistent reporting during refresh.
- Local pytest skips the database group with an explicit reason if `TEST_DATABASE_URL` is absent. CI sets `REQUIRE_INTEGRATION_TESTS=1`, making that omission an error. CI has a real PostgreSQL 17 service and no live City-download dependency.
- The workflow is configured locally; a successful GitHub Actions run is not claimed until this repository is published and it actually runs.

## Failure recovery

Read `commute data-health`: latest attempt, latest successful attempt and active snapshot are distinct. On failed download, schema validation or staging, the previous active delay data remains selected. Retry the same command after fixing the cause. Unknown codes/extra named columns are retained and reported, rather than fixed by dropping rows.

After a process crash, PostgreSQL rolls back the uncommitted data and releases its session lock. The next import for that resource marks leftover running audit rows interrupted before retrying. A currently running attempt is not automatically stale by elapsed time; the database lock is the authority. A competing import receives `resource_busy` and can retry later.

No automatic snapshot deletion or manual pointer-editing command is provided. Keep historical provenance during this milestone. A previously processed byte-for-byte source reversion safely reactivates its old snapshot through the normal importer.

For a broken local test database, recreate **only** `commute_test` intentionally, then reapply migrations. Do not point integration tests at `commute` or a shared database. No backup/restore performance or production-recovery claim has been established in Phase 0; a restore drill belongs to Phase 4.

## Wentao's interview walkthrough

Start with fixture `_id=1`. Its manifest points back to original CSV row 2. Follow the saved raw payload, typed `Date`, derived route `102`, code `MFESA`, and the pinned lookup description. Explain which transformations are reversible through the raw record.

Then read the hand-calculated SQL test: route 102 has three matching records with recorded delays `[10, missing, 0]`, so the numeric sample count is two and the median is five. Change one input and predict the result before rerunning the test. Explain why the source's 300 repeated extra payloads are retained, why a cumulative correction replaces a snapshot, and why none of these counts is a trip-level probability.

For the web slice, follow `route=102` and the dates from the address bar to `FilterQuery`, the shared `Filters` selection, the pinned snapshot and `route_summary.sql`, then the typed response and React metric/chart. Explain why the chart and page-2 request include the returned snapshot ID. Changing the real January end date from the 31st to the 15th changes the record count from 65 to 39; both were checked against original CSV cells. Date-form submission and pagination focus were browser bugs caught after the API tests already passed.
