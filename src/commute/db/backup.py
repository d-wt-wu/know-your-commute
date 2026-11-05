"""Logical backups whose restored contents can be checked against the same MVCC snapshot.

Only restore into a new, randomly named scratch database. This module deliberately
offers no switch that overwrites an existing database.
"""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from uuid import uuid4

import sqlalchemy as sa

from commute.db.connection import database_engine
from commute.db.schema import metadata

TABLE_KEYS = {table.name: tuple(column.name for column in table.primary_key)
              for table in metadata.tables.values()}
TABLE_KEYS["alembic_version"] = ("version_num",)


class BackupError(RuntimeError):
    pass


def _tool(name: str, pg_bin: Path | None = None) -> str:
    directory = pg_bin or os.environ.get("PG_BIN")
    path = str(Path(directory) / name) if directory else shutil.which(name)
    if not path or not Path(path).is_file():
        raise BackupError(f"Install PostgreSQL 17 client tools or set PG_BIN; {name} is unavailable.")
    version = subprocess.run([path, "--version"], check=True, capture_output=True, text=True)
    if not re.search(r"\b17\.", version.stdout):
        raise BackupError("Use PostgreSQL 17 client tools for this project's PostgreSQL 17 backups.")
    return path


def _environment(url) -> dict[str, str]:
    # Credentials stay out of process arguments, manifests and printed results.
    env = {key: value for key, value in os.environ.items() if not key.startswith("PG")}
    for key, value in {"PGHOST": url.host, "PGPORT": url.port, "PGUSER": url.username,
                       "PGPASSWORD": url.password, "PGDATABASE": url.database}.items():
        if value is not None:
            env[key] = str(value)
    for key, value in url.query.items():
        if key not in {"sslmode", "sslrootcert", "sslcert", "sslkey", "channel_binding", "connect_timeout"}:
            raise BackupError(f"Unsupported backup connection option: {key}")
        env["PGCONNECT_TIMEOUT" if key == "connect_timeout" else "PG" + key.replace("_", "").upper()] = str(value)
    env.setdefault("PGCONNECT_TIMEOUT", "10")
    return env


def _run(arguments, *, url, stdout=None):
    try:
        result = subprocess.run(arguments, env=_environment(url), stdin=subprocess.DEVNULL,
                                stdout=stdout or subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=300)
    except subprocess.TimeoutExpired:
        raise BackupError(f"{Path(arguments[0]).name} exceeded five minutes; recovery was not verified.") from None
    if result.returncode:
        # A subprocess diagnostic can include hostnames or connection details.
        raise BackupError(f"{Path(arguments[0]).name} failed (exit {result.returncode}); no successful restore is recorded.")


def fingerprint(connection) -> dict:
    """Hash every stored row, ordered by its actual primary key, including audits/raw data."""
    connection.execute(sa.text("SET LOCAL TIME ZONE 'UTC'"))
    output = {}
    quote = connection.dialect.identifier_preparer.quote
    for table, keys in sorted(TABLE_KEYS.items()):
        digest, count = hashlib.sha256(), 0
        ordering = ", ".join(quote(key) for key in keys)
        rows = connection.execute(sa.text(
            f"SELECT to_jsonb(t)::text FROM public.{quote(table)} AS t ORDER BY {ordering}"
        ).execution_options(stream_results=True))
        for row in rows:
            digest.update(row[0].encode("utf-8") + b"\n")
            count += 1
        output[table] = {"rows": count, "sha256": digest.hexdigest()}
    return output


def _sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def create_backup(engine, directory: Path, pg_bin: Path | None = None) -> Path:
    executable = _tool("pg_dump", pg_bin)
    directory.mkdir(parents=True, exist_ok=True)
    basename = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex
    archive, manifest = directory / (basename + ".dump"), directory / (basename + ".json")
    created_archive = created_manifest = False
    try:
        with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
            with connection.begin():
                connection.execute(sa.text("SET TRANSACTION READ ONLY"))
                exported = connection.scalar(sa.text("SELECT pg_export_snapshot()"))
                expected = fingerprint(connection)
                server = connection.scalar(sa.text("SHOW server_version"))
                with archive.open("xb") as handle:
                    created_archive = True
                    os.chmod(archive, 0o600)
                    # Exporting keeps the hashes and dump consistent even during a refresh.
                    _run([executable, "--format=custom", "--compress=0", "--no-owner", "--no-privileges",
                          "--snapshot", exported], url=engine.url, stdout=handle)
        evidence = {"format_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                    "server_version": server, "archive": archive.name,
                    "archive_bytes": archive.stat().st_size, "archive_sha256": _sha256(archive),
                    "fingerprints": expected}
        with manifest.open("x") as handle:
            created_manifest = True
            os.chmod(manifest, 0o600)
            json.dump(evidence, handle, indent=2)
            handle.write("\n")
        return manifest
    except BaseException:
        if created_archive:
            archive.unlink(missing_ok=True)
        if created_manifest:
            manifest.unlink(missing_ok=True)
        raise


def checked_archive(manifest: Path) -> tuple[Path, dict]:
    evidence = json.loads(manifest.read_text())
    name = evidence.get("archive", "")
    if evidence.get("format_version") != 1 or Path(name).name != name or not name.endswith(".dump"):
        raise BackupError("Invalid backup manifest or archive filename.")
    if set(evidence.get("fingerprints", {})) != set(TABLE_KEYS):
        raise BackupError("Backup manifest does not cover every application table.")
    archive = manifest.parent / name
    if archive.stat().st_size != evidence["archive_bytes"] or _sha256(archive) != evidence["archive_sha256"]:
        raise BackupError("Backup checksum mismatch. Restore was refused.")
    return archive, evidence


def restore_check(engine, manifest: Path, pg_bin: Path | None = None) -> dict:
    """Restore a trusted local dump into a newly created database, verify, then remove it.

    The database account needs CREATEDB. Managed hosts without it should use a
    separate manually created recovery project; never restore over the live app.
    """
    archive, expected = checked_archive(manifest)
    executable = _tool("pg_restore", pg_bin)
    name = "commute_restore_" + uuid4().hex + "_test"
    admin = database_engine(engine.url.set(database="postgres"))
    restored = None
    created = False
    try:
        with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            # Internally generated hex identifier; no caller-supplied target or --clean.
            connection.execute(sa.text(f'CREATE DATABASE "{name}" TEMPLATE template0'))
            created = True
        target = engine.url.set(database=name)
        _run([executable, "--exit-on-error", "--single-transaction", "--no-owner", "--no-privileges",
              "--dbname", name, str(archive)], url=target)
        restored = database_engine(target)
        with restored.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
            with connection.begin():
                connection.execute(sa.text("SET TRANSACTION READ ONLY"))
                actual = fingerprint(connection)
        if actual != expected["fingerprints"]:
            raise BackupError("Restored contents differ from the backup snapshot. Recovery check failed.")
        return {"status": "verified", "archive_sha256": expected["archive_sha256"],
                "fingerprints": actual, "scratch_database_removed": True}
    finally:
        if restored is not None:
            restored.dispose()
        try:
            if created:
                with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
                    connection.execute(sa.text(f'DROP DATABASE "{name}"'))
        finally:
            admin.dispose()
