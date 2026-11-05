"""Verify a running built app, including packaged SQL and Home Screen assets."""
import argparse
import json
from urllib.error import HTTPError
from urllib.request import urlopen


def check(base: str, expected: int):
    with urlopen(base + "/", timeout=30) as response:
        assert response.status == 200 and b"/manifest.webmanifest" in response.read()
    with urlopen(base + "/manifest.webmanifest", timeout=30) as response:
        assert response.headers.get_content_type() == "application/manifest+json"
        manifest = json.load(response)
    for icon in manifest["icons"] + [{"src": "/apple-touch-icon.png"}]:
        with urlopen(base + icon["src"], timeout=30) as response:
            assert response.headers.get_content_type() == "image/png"
            assert response.read(8) == b"\x89PNG\r\n\x1a\n"
    with urlopen(base + "/api/v1/summary?route=102&start=2025-01-01&end=2025-01-31", timeout=30) as response:
        assert response.headers["Cache-Control"] == "no-store"
        summary = json.load(response)
        assert summary["summary"]["reported_records"] == expected
    for path in ["/api/v1/missing", "/missing.png"]:
        try:
            urlopen(base + path, timeout=30)
        except HTTPError as error:
            assert error.code == 404
            assert error.headers.get_content_type() == "application/json"
        else:
            raise AssertionError("A missing API/asset path returned success.")
    return {"status": "verified", "route_102_january_records": expected, "home_screen_assets": "served"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--expected-records", type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.base_url.rstrip("/"), args.expected_records)))
