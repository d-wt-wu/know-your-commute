"""Apply the app migration, replay an attributed bundle and configure an API login.

Requires a previously linked/deployed Neon project and its private .env.local.
Never creates a Neon project, resets a password, drops data or runs test cleanup.
"""
import argparse
from dataclasses import asdict
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import secrets
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from alembic import command
from alembic.config import Config
from dotenv import dotenv_values, set_key
import sqlalchemy as sa
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from commute.db.connection import database_engine
from commute.db.permissions import create_api_login, grant_api_reads, verify_api_role
from commute.db.reports import route_report
from commute.ingest.fetch import load_manifest_file
from commute.ingest.pipeline import import_resource
from commute.ingest.registry import CODES, DELAYS


def setup(environment_file: Path, manifest: Path, role: str, output: Path):
    values = dotenv_values(environment_file, interpolate=False)
    direct = values.get("DATABASE_URL_UNPOOLED")
    pooled = values.get("DATABASE_URL")
    if not direct or not pooled:
        raise ValueError("Run neon deploy to obtain both PostgreSQL connection variables first.")
    owner = make_url(direct)
    if not (owner.host or "").endswith(".neon.tech"):
        raise ValueError("This command requires an explicit Neon environment; local setup is separate.")
    linked = json.loads((ROOT / ".neon").read_text())
    if linked.get("branch") != "production":
        raise ValueError("Select the intended production branch before running this setup command.")
    existing = values.get("COMMUTE_API_DATABASE_URL")
    api_url = make_url(existing) if existing else None
    if api_url and not api_url.password:
        raise ValueError("Existing API connection is missing its password. It was preserved.")
    if api_url and (api_url.username != role or api_url.database != owner.database or api_url.host != make_url(pooled).host):
        raise ValueError("Existing API configuration targets another role/database. It was preserved.")
    writer = database_engine(direct, purpose="writer")
    api = None
    started = time.perf_counter()
    try:
        with writer.connect() as connection:
            before = connection.scalar(sa.text("SELECT to_regclass('public.alembic_version')"))
            app_tables = connection.scalar(sa.text("SELECT to_regclass('public.source_resources')"))
            if app_tables and not before:
                raise ValueError("Existing application tables lack migration history; review before changing them.")
            role_exists = connection.scalar(sa.text("SELECT EXISTS (SELECT FROM pg_roles WHERE rolname=:role)"), {"role": role})
            if role_exists and not api_url:
                raise ValueError("API login already exists but its credential is not configured. Its password was not reset.")
            connection.rollback()
            config = Config(str(ROOT / "alembic.ini"))
            config.set_main_option("script_location", str(ROOT / "migrations"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            command.check(config)
        imports, reruns = [], []
        for resource in (CODES, DELAYS):
            result = import_resource(writer, resource, lambda r=resource: load_manifest_file(manifest, r))
            imports.append({"resource": resource.key, **asdict(result)})
        for resource in (CODES, DELAYS):
            result = import_resource(writer, resource, lambda r=resource: load_manifest_file(manifest, r))
            if result.status != "no_change":
                raise ValueError("The identical-bundle rerun did not return no_change.")
            reruns.append({"resource": resource.key, **asdict(result)})
        if api_url is None:
            api_url = make_url(pooled).set(username=role, password=secrets.token_urlsafe(36))
            # Save before creating the login, so an interrupted setup can reuse
            # the same credential rather than rotate or lose it on a retry.
            set_key(str(environment_file), "COMMUTE_API_DATABASE_URL", api_url.render_as_string(hide_password=False))
            os.chmod(environment_file, 0o600)
        with writer.begin() as connection:
            created = create_api_login(connection, role, api_url.password)
            grant_api_reads(connection, role)
        api = database_engine(api_url)
        with api.connect() as connection:
            verify_api_role(connection)
            database = connection.scalar(sa.text("SELECT current_database()"))
            version = connection.scalar(sa.text("SHOW server_version"))
            tls = connection.connection.driver_connection.pgconn.ssl_in_use
            login = connection.scalar(sa.text("SELECT current_user"))
        denied = {}
        for name, query in {"writes": "DELETE FROM delay_records WHERE false", "raw_reads": "SELECT * FROM raw_records LIMIT 1"}.items():
            with api.connect() as connection:
                try:
                    connection.execute(sa.text(query))
                except DBAPIError as exc:
                    if exc.orig.sqlstate not in {"42501", "25006"}:
                        raise ValueError("API permission probe failed for an unexpected reason.") from None
                    denied[name] = exc.orig.sqlstate
                else:
                    raise ValueError("The API credential unexpectedly allowed a forbidden operation.")
        report = route_report(api, "102", date(2025, 1, 1), date(2025, 1, 31))
        with writer.connect() as connection:
            migration = connection.scalar(sa.text("SELECT version_num FROM alembic_version"))
        evidence = {"checked_at": datetime.now(timezone.utc).isoformat(),
                    "target": {"project_id": linked["projectId"], "branch": linked["branch"]},
                    "database": {"name": database, "version": version, "tls_active": tls, "api_login": login},
                    "migration": migration, "imports": imports, "identical_reruns": reruns,
                    "api_role_created": created, "denied_operations": denied,
                    "route_102_january_summary": report["summary"],
                    "coverage": report["loaded_coverage"], "source": report["source"],
                    "quality": report["quality"], "elapsed_seconds": round(time.perf_counter() - started, 3)}
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2, default=str) + "\n")
        return {"status": "verified", "database": database, "tls_active": tls, "api_login": login,
                "reported_records": report["quality"]["accepted_count"], "route_102_january": report["summary"],
                "identical_reruns": [r["status"] for r in reruns], "writes_and_raw_reads": "denied", "evidence": str(output)}
    finally:
        if api is not None:
            api.dispose()
        writer.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env.local")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--role", default="commute_api")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/evidence/neon-database.json")
    args = parser.parse_args()
    try:
        print(json.dumps(setup(args.env_file, args.manifest.resolve(), args.role, args.output), indent=2, default=str))
    except Exception as exc:
        # Driver tracebacks/utility statements can contain private connection details.
        print("Neon database setup failed (" + type(exc).__name__ + "). Previous data and credentials were retained.", file=sys.stderr)
        if isinstance(exc, ValueError):
            print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
