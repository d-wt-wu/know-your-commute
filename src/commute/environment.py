"""Explicit environment-file loading; production hosts inject variables instead."""
from pathlib import Path

from dotenv import load_dotenv


def load_environment(path: Path):
    if not path.is_file():
        raise ValueError("Environment file is missing. Finish Neon sign-in and run neon deploy first.")
    # Preserve injected values and literal password characters such as ${...}.
    load_dotenv(path, override=False, interpolate=False)
