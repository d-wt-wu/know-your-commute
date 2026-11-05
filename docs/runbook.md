# Local setup and recovery

Run commands from the project directory. No hosting account, domain or paid service is required. PostgreSQL 17 and Python 3.13 are the current local targets.

## Environment

```sh
uv sync --locked
source .venv/bin/activate
export PYTHONPATH="$PWD/src"
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
