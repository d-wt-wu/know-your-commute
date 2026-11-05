# Know Your Commute — TTC Delay Explorer

An independent project by **Wentao Wu** for exploring historical reported TTC bus delay records. The first slice is a Python/PostgreSQL data workflow: preserve the source, validate it, replace cumulative snapshots safely, and answer route/date questions with SQL.

**Status:** Phases 0–1 verified against PostgreSQL 17.11: **43 tests passed**, including 20 database integration cases. The real source imported 107,349 records; an identical rerun reused the active snapshot. Route 102 for January 2025 matched an independent CSV calculation. See [progress](docs/progress.md) and [verification evidence](docs/evidence/phase1-checks.json). The FastAPI API and React dashboard are the next phases. There is no deployed app or public repository yet.

Record counts cannot establish a bus trip's delay probability or rank route reliability: this source has no scheduled/operated-trip denominator. Recorded delay minutes describe delay to the following bus's schedule. They are not passenger-minutes lost. This is historical data, not live arrivals.

## Start locally

Use Python 3.13, [uv](https://docs.astral.sh/uv/getting-started/installation/), and PostgreSQL 17. Dependencies are resolved in `uv.lock`. Do not install dependencies into your system Python.

```sh
uv sync --locked
source .venv/bin/activate
export PYTHONPATH="$PWD/src"
set -a
source .env.example
set +a
```

The explicit Python path also handles a macOS development-runner quirk where ignored `.pth` files are marked hidden. It is unnecessary for a normal wheel installation.

With Docker:

```sh
docker compose up -d --wait db
docker compose exec db createdb -U commute commute_test
```

If Docker and PostgreSQL are both absent, an optional project-local build is available. It needs the macOS command line build tools (or equivalent Unix tools), downloads verified PostgreSQL source, and writes only inside ignored `work/`. It installs no system service. In a restricted app runner, execute this in your own Terminal if shared-memory startup is denied:

```sh
python scripts/local_postgres.py setup
```

Then:

```sh
alembic upgrade head
pytest
commute refresh
commute report --route 102 --start 2025-01-01 --end 2025-01-31
commute data-health
```

`refresh` imports the official lookup first, then the current cumulative CSV. It archives the README, metadata and originals with hashes. The terminal output includes the retained manifest path. Import those exact bytes again with:

```sh
commute import-bundle --manifest data/raw/manifest-REPLACE-WITH-ACTUAL-HASH.json
```

This example path is a placeholder, not a created file. Use the path returned by `fetch` or `refresh`. For a download without a database, run `commute fetch`.

See [the runbook](docs/runbook.md) for failure recovery, archived downloads and the existing local source bundle. Integration tests refuse cleanup unless `TEST_DATABASE_URL` names a database ending in `_test`. CI requires those tests to run; a missing URL cannot silently pass the database gate there.

## What is implemented

- CSV contract verified against the official 2025-onward CSV, the older README and the independently versioned lookup.
- Attributed 20-record fixture with original source positions, plus the small official lookup. Synthetic test records are labelled separately.
- SQLAlchemy Core tables and a frozen Alembic migration for resources, snapshots, attempts, raw rows, typed rows, rejects and code descriptions.
- Audited imports with per-resource locks, checksums, parser/contract versions, pinned lookup versions and atomic active-snapshot replacement.
- SQL route/date totals, duration sample counts, daily counts, causes and traceable examples. Queries use bound values and one consistent snapshot.
- pytest validation/download tests and PostgreSQL integration scenarios; a GitHub Actions workflow is prepared locally.

## Read the evidence and decisions

| Document | Purpose |
| --- | --- |
| [Progress](docs/progress.md) | What has actually run, what remains blocked, next step |
| [Data contract](docs/data-contract.md) | Exact observed columns, definitions, validation and ambiguities |
| [Source manifest](docs/source-manifest.json) / [profile](docs/source-profile.json) | URLs, hashes, retrieval/source timestamps and measured quality |
| [Decisions](docs/decisions.md) | Why snapshots, PostgreSQL, row positions and a pinned lookup |
| [Metrics](docs/metrics.md) | Report meanings, zero/missing handling and limitations |
| [Runbook](docs/runbook.md) | Setup, commands, recovery and reproduction |
| [Original project plan](docs/project-plan.md) | Chosen scope and later phases |

## Attribution

Data: [City of Toronto / TTC Bus Delay Data](https://open.toronto.ca/dataset/ttc-bus-delay-data/).

Contains information licensed under the [Open Government Licence – Toronto](https://open.toronto.ca/open-data-licence/).

This project is independent of the TTC and City of Toronto. No official endorsement is implied. Data retains its publisher's licence; no ownership of source data is claimed.
