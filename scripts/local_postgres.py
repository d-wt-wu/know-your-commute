#!/usr/bin/env python3
"""Optional, project-local PostgreSQL for machines without Docker. No system install."""

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
PREFIX = WORK / "pg"
PGDATA = WORK / "pgdata"
VERSION = "17.11"
SHA256 = "dd27f2b3c59e73ed14aa3324901242bf69a032a6347805f274e6260322d42979"
ENV = {**os.environ, "PGPASSWORD": "commute_local"}


def run(args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def install():
    if (PREFIX / "bin/pg_ctl").exists():
        return
    WORK.mkdir(exist_ok=True)
    archive = WORK / f"postgresql-{VERSION}.tar.bz2"
    url = f"https://ftp.postgresql.org/pub/source/v{VERSION}/{archive.name}"
    with urllib.request.urlopen(url, timeout=60) as response:
        raw = response.read()
    if hashlib.sha256(raw).hexdigest() != SHA256:
        raise RuntimeError("PostgreSQL source checksum did not match.")
    archive.write_bytes(raw)
    with tarfile.open(archive) as tar:
        tar.extractall(WORK, filter="data")
    source = WORK / f"postgresql-{VERSION}"
    commands = [
        ["./configure", f"--prefix={PREFIX}", "--without-icu", "--without-readline", "--without-zlib"],
        ["make", "-j6"], ["make", "install"],
    ]
    for i, args in enumerate(commands):
        print(f"Building local PostgreSQL: step {i + 1}/3", flush=True)
        with (WORK / f"postgres-setup-{i}.log").open("w") as log:
            run(args, cwd=source, stdout=log, stderr=subprocess.STDOUT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["setup", "start", "stop", "status"])
    args = parser.parse_args()
    if args.action == "setup":
        install()
        if not (PGDATA / "PG_VERSION").exists():
            password = WORK / "pg-init-password"
            password.write_text("commute_local\n")
            password.chmod(0o600)
            try:
                run([PREFIX / "bin/initdb", "-D", PGDATA, "-U", "commute", "--encoding=UTF8",
                     "--locale=C", "--auth-local=trust", "--auth-host=scram-sha-256", f"--pwfile={password}"])
            finally:
                password.unlink(missing_ok=True)
    if args.action in {"setup", "start"}:
        status = subprocess.run([str(PREFIX / "bin/pg_ctl"), "-D", str(PGDATA), "status"], capture_output=True)
        if status.returncode:
            # A loopback-only developer database, never a system service.
            run([PREFIX / "bin/pg_ctl", "-D", PGDATA, "-l", WORK / "postgres-server.log",
                 "-o", f"-h 127.0.0.1 -p 54329 -k {WORK}", "-w", "start"])
        for database in ["commute", "commute_test"]:
            result = subprocess.run(
                [str(PREFIX / "bin/psql"), "-h", "127.0.0.1", "-p", "54329", "-U", "commute",
                 "-d", "postgres", "-tAc", f"SELECT 1 FROM pg_database WHERE datname = '{database}'"],
                env=ENV, capture_output=True, text=True, check=True,
            )
            if result.stdout.strip() != "1":
                run([PREFIX / "bin/createdb", "-h", "127.0.0.1", "-p", "54329", "-U", "commute", database], env=ENV)
        print("Local PostgreSQL is ready at 127.0.0.1:54329 (commute and commute_test).")
    elif args.action == "stop":
        run([PREFIX / "bin/pg_ctl", "-D", PGDATA, "-m", "fast", "-w", "stop"])
    else:
        run([PREFIX / "bin/pg_ctl", "-D", PGDATA, "status"])


if __name__ == "__main__":
    main()
