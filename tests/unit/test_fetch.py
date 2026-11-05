from datetime import datetime, timezone
import hashlib
import json

import httpx
import pytest

from commute.ingest.adapter import ContractError
from commute.ingest.fetch import DownloadSession, load_manifest_file, request_bytes
from commute.ingest.registry import CODES, DELAYS, DATASET_ID, PACKAGE_URL, README_ID

URL = "https://ckan0.cf.opendata.inter.prod-toronto.ca/test.csv"


def test_transient_status_retries_but_404_does_not(monkeypatch):
    monkeypatch.setattr("commute.ingest.fetch.time.sleep", lambda _: None)
    seen = []
    def response(request):
        seen.append(request)
        return httpx.Response(503 if len(seen) < 3 else 200, content=b"real,csv\n1,2\n")
    with httpx.Client(transport=httpx.MockTransport(response)) as client:
        assert request_bytes(client, URL)[0].startswith(b"real,csv")
    assert len(seen) == 3
    seen.clear()
    def missing(request):
        seen.append(request)
        return httpx.Response(404)
    with httpx.Client(transport=httpx.MockTransport(missing)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            request_bytes(client, URL)
    assert len(seen) == 1


@pytest.mark.parametrize("headers,body", [({"content-type": "text/html"}, b"error"), ({}, b"<html>error</html>"), ({}, b""), ({"content-length": "999999999"}, b"csv")])
def test_bad_success_responses_are_not_accepted(headers, body):
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, headers=headers, content=body))) as client:
        with pytest.raises(ContractError):
            request_bytes(client, URL)


def test_external_or_non_https_sources_are_rejected():
    with httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail("must not make request"))) as client:
        for url in ["http://ckan0.cf.opendata.inter.prod-toronto.ca/test", "https://example.com/test"]:
            with pytest.raises(ContractError):
                request_bytes(client, url)


def test_download_bundle_and_verified_manifest_round_trip(tmp_path):
    ids = [README_ID, CODES.official_id, DELAYS.official_id]
    entries = [{"id": key, "name": key, "url": f"https://ckan0.cf.opendata.inter.prod-toronto.ca/{key}", "last_modified": "2026-10-26T12:32:23"} for key in ids]
    metadata = {"success": True, "result": {"id": DATASET_ID, "metadata_modified": "2026-10-29", "resources": entries}}
    def response(request):
        if str(request.url) == PACKAGE_URL:
            return httpx.Response(200, json=metadata)
        return httpx.Response(200, content=b"PK-test-README" if request.url.path.endswith(README_ID) else b"_id,CODE,DESCRIPTION\n1,A,Test\n")
    with httpx.Client(transport=httpx.MockTransport(response)) as client:
        downloads = DownloadSession(tmp_path, client)
        source = downloads.resource(CODES)
        downloads.resource(DELAYS)
        manifest = downloads.write_manifest()
        loaded = load_manifest_file(manifest, CODES)
        assert source.data == loaded.data and source.sha256 == loaded.sha256
        assert loaded.retrieved_at.tzinfo is not None
        assert loaded.provenance["readme_sha256"] == hashlib.sha256(b"PK-test-README").hexdigest()
        data = json.loads(manifest.read_text())
        (tmp_path / next(e["path"] for e in data["resources"] if e["id"] == CODES.official_id)).write_bytes(b"tampered")
        with pytest.raises(ContractError, match="checksum"):
            load_manifest_file(manifest, CODES)
