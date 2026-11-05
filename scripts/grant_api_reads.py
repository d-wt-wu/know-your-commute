"""Grant application reads to an existing dedicated API login using the owner URL."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from commute.db.connection import database_engine
from commute.db.permissions import grant_api_reads

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", required=True)
    args = parser.parse_args()
    engine = database_engine()
    try:
        with engine.begin() as connection:
            grant_api_reads(connection, args.role)
        print("Granted the dedicated API role explicit SELECT access. No write access was added.")
    finally:
        engine.dispose()
