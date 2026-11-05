import argparse
from dataclasses import asdict
from datetime import date
import json
from pathlib import Path
import sys

import httpx
from sqlalchemy.exc import SQLAlchemyError

from commute.db.connection import database_engine
from commute.db.backup import BackupError, create_backup, restore_check
from commute.db.explorer import health as public_health
from commute.db.reports import data_health, route_report
from commute.ingest.fetch import DownloadSession, load_manifest_file
from commute.ingest.pipeline import ImportFailed, import_resource
from commute.ingest.registry import CODES, DELAYS


def emit(value):
    print(json.dumps(value, indent=2, default=str, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Know Your Commute — historical TTC bus delay records")
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("fetch", help="Archive the official metadata, README, lookup and CSV")
    fetch.add_argument("--directory", type=Path, default=Path("data/raw"))
    refresh = commands.add_parser("refresh", help="Download and import official lookup then delays")
    refresh.add_argument("--directory", type=Path, default=Path("data/raw"))
    local = commands.add_parser("import-bundle", help="Import archived files after verifying their manifest hashes")
    local.add_argument("--manifest", type=Path, required=True)
    report = commands.add_parser("report", help="Read a route/date SQL report from the active snapshot")
    report.add_argument("--route", help="Exact derived identifier, e.g. 102 or 102D; omit for all records")
    report.add_argument("--start", type=date.fromisoformat, required=True)
    report.add_argument("--end", type=date.fromisoformat, required=True)
    health = commands.add_parser("data-health", help="Show latest attempt, last success and active snapshot separately")
    health.add_argument("--public", action="store_true", help="Use the public projection, excluding internal diagnostics")
    backup = commands.add_parser("backup", help="Create a consistent PostgreSQL dump and table checksums")
    backup.add_argument("--directory", type=Path, default=Path("data/backups"))
    restore = commands.add_parser("restore-check", help="Verify a trusted backup in a new temporary database, then remove it")
    restore.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    engine, downloads = None, None
    try:
        if args.command in {"fetch", "refresh"}:
            downloads = DownloadSession(args.directory)
        if args.command == "fetch":
            downloads.resource(CODES)
            downloads.resource(DELAYS)
            emit({"manifest": str(downloads.write_manifest())})
            return 0
        engine = database_engine()
        if args.command in {"refresh", "import-bundle"}:
            for resource in (CODES, DELAYS):
                if args.command == "refresh":
                    load = lambda r=resource: downloads.resource(r)
                else:
                    load = lambda r=resource: load_manifest_file(args.manifest.resolve(), r)
                result = import_resource(engine, resource, load)
                emit({"resource": resource.key, **asdict(result)})
            if downloads:
                emit({"manifest": str(downloads.write_manifest())})
        elif args.command == "report":
            emit(route_report(engine, args.route, args.start, args.end))
        elif args.command == "backup":
            emit({"status": "backed_up", "manifest": str(create_backup(engine, args.directory))})
        elif args.command == "restore-check":
            emit(restore_check(engine, args.manifest))
        else:
            emit(public_health(engine) if args.public else data_health(engine))
        return 0
    except ImportFailed as exc:
        emit({"status": "failed", "run_id": str(exc.run_id), "error_code": exc.code, "message": str(exc)})
        return 1
    except (ValueError, OSError, BackupError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except httpx.HTTPError:
        print("Official download failed. Check the network and retry; archived files remain available.", file=sys.stderr)
        return 1
    except SQLAlchemyError:
        print("Database operation failed. Check PostgreSQL, DATABASE_URL and migrations; see docs/runbook.md.", file=sys.stderr)
        return 1
    finally:
        if downloads:
            downloads.close()
        if engine:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
