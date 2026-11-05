#!/usr/bin/env python3
"""Serve the built dashboard and API on one loopback-only origin."""

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    directory = Path(os.environ.get("COMMUTE_WEB_DIR", ROOT / "web/dist"))
    if not (directory / "index.html").is_file():
        raise SystemExit("Build the dashboard first: npm --prefix web ci && npm --prefix web run build")
    # A convenience for the existing developer setup, never a production secret.
    os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://commute:commute_local@127.0.0.1:54329/commute")
    os.environ["COMMUTE_WEB_DIR"] = str(directory.resolve())
    import uvicorn
    uvicorn.run("commute.api.app:app", host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
