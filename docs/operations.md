# Refresh, backup and query evidence

## Controlled source check

The CLI `commute refresh` imports lookup then cumulative delays. Per-resource
PostgreSQL advisory locks protect all invocations, including another terminal or
workflow. A source is validated/staged inside a transaction before its pointer
changes. Existing tests cover corrected files, failed input, rollback, a real
process crash, retry, overlapping importers and source reversion. If only the
lookup succeeds, the previous delay file still uses its pinned old lookup.

`.github/workflows/refresh.yml` adds a manual trigger and Monday 11:23 UTC source
check, with a single workflow concurrency group and 15-minute job timeout. Weekly
runs stay disabled until `COMMUTE_REFRESH_ENABLED=true`. The job requires the
`production` environment secret `IMPORT_DATABASE_URL`; it neither creates a
database nor runs migrations. Its final status step uses `data-health --public`,
which excludes internal diagnostics.

Only the official public download files/manifests go into a seven-day source
artifact. Database dumps, credentials and private audit diagnostics never go into
public artifacts. Seven-day Actions artifacts are a short recovery aid, not a
durable backup service. The database retains raw rows, provenance and immutable
snapshots independently. Download and retain originals privately if exact bytes
are needed beyond that window. Inspect Actions storage allowances before enabling
automation. Schedules can be delayed/dropped and inactive public repositories can
have them disabled; the manual trigger and actual freshness display remain the
authority. [GitHub schedule behaviour](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## Private logical backup and restore drill

Use PostgreSQL **17** client tools. On this checkout they are in `work/pg/bin`:

```sh
export PG_BIN="$PWD/work/pg/bin"
commute backup --directory data/backups
commute restore-check --manifest data/backups/REPLACE-WITH-RETURNED-MANIFEST.json
```

The backup command reports a real manifest path; the second example is a
placeholder. The commands use the private `DATABASE_URL` from the environment.
Passwords are not placed in subprocess arguments or saved manifests. The archive
and manifest have owner-only local permissions and remain ignored by Git.

The backup exports a read-only repeatable-read PostgreSQL snapshot and holds it
open while `pg_dump --snapshot` runs. It fingerprints every stored row, ordered by
primary key, with timestamps in UTC. This ties the archive's expected contents to
the same database state even when an import commits during the dump. A manifest
records archive SHA-256/size and all eight application/migration table hashes.

`restore-check` verifies the archive hash, creates a new random
`commute_restore_<hex>_test` database, restores in one transaction, compares all
table hashes, and removes only that scratch database. There is no caller-supplied
target, `--clean` or overwrite option. The account needs CREATEDB and access to
the `postgres` maintenance database. A managed account without that permission
needs a separate owner-created recovery project and a deliberate restore runbook;
do not point a restoration at the live application.

Only restore trusted backups you created: integrity hashes detect changed bytes,
not maliciously authored SQL. The logical dump deliberately excludes ownership
and grants. It restores this database's schema/data, not server-wide roles,
passwords, host configuration or the separately archived original CSV files.
Reapply dedicated role grants when rebuilding an environment.
[PostgreSQL dump](https://www.postgresql.org/docs/17/app-pgdump.html) and
[restore](https://www.postgresql.org/docs/17/app-pgrestore.html) documentation.

**Actual real-data drill:** `evidence/backup-restore.json` records the custom
uncompressed 54,611,555-byte archive, a 1.526-second backup and 2.220-second
restore/verification on the existing local server. All table fingerprints matched;
the scratch database was removed and the live route-102 report stayed at 65
January records. These are single local observations, not a recovery SLA.

The dedicated integration test commits a correction between exporting the backup
snapshot and running pg_dump. Restoration still contains the old one-row snapshot;
the live database contains both retained versions. Another test forces a restore
failure and verifies cleanup leaves the source database intact. Corrupted archive
checksums and escaped archive paths are refused before restore creation.

## Query plan and timings

```sh
python scripts/measure_queries.py
```

The script performs read-only summaries, captures one first call and five repeats
per filter and saves the actual `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` plans to
`evidence/query-measurements.json`.

| Filter, on 107,349 loaded records | First call | Median of five repeats | PostgreSQL plan |
| --- | ---: | ---: | --- |
| Route 102, January 2025 (65 records) | 4.537 ms | 0.429 ms | Index scan using `ix_delay_route_date`, 65 rows |
| All loaded dates/routes | 37.991 ms | 16.329 ms | Sequential scan, 107,349 rows |

The selective route uses the intended composite index; the broad report reads the
whole selected file, so a sequential scan is reasonable. Both observed plans hit
cached blocks without disk reads. No additional index or fabricated speed-up is
claimed. This measures database summary execution, not network/browser latency.

The server was already running, and OS/database caches were not cleared. A fresh
connection is **not** a cold-cache experiment. True cold-cache/hosted end-to-end
measurements remain future work; the evidence states that limit explicitly.
