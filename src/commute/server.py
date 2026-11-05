"""Container entry point. Local previews use scripts/run_local.py instead."""
import os


def main():
    if not os.environ.get("DATABASE_URL"):
        raise SystemExit("Set DATABASE_URL to the dedicated read-only API connection.")
    try:
        port = int(os.environ.get("PORT", "8000"))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        raise SystemExit("PORT must be a number between 1 and 65535.") from None
    import uvicorn
    uvicorn.run("commute.api.app:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
