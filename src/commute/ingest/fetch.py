"""Bounded official downloads, content-addressed originals, and verifiable manifests."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import time

import httpx

from commute.ingest.adapter import ContractError
from commute.ingest.registry import CODES, DELAYS, DATASET_ID, PACKAGE_URL, README_ID, Resource

MAX_BYTES = 50 * 1024 * 1024
OFFICIAL_HOST = "ckan0.cf.opendata.inter.prod-toronto.ca"


def now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class SourceFile:
    data: bytes
    url: str
    retrieved_at: datetime
    source_last_modified: str | None = None
    provenance: dict | None = None

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


def request_bytes(client: httpx.Client, url: str, *, attempts: int = 3) -> tuple[bytes, dict]:
    parsed = httpx.URL(url)
    if parsed.scheme != "https" or parsed.host != OFFICIAL_HOST:
        raise ContractError("Source URL must use the official Toronto HTTPS host.")
    for attempt in range(attempts):
        try:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                if response.url.host != OFFICIAL_HOST:
                    raise ContractError("Download redirected outside the official host.")
                length = response.headers.get("content-length")
                if length and int(length) > MAX_BYTES:
                    raise ContractError("Download exceeds the configured 50 MiB limit.")
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise ContractError("Download exceeds the configured 50 MiB limit.")
                    chunks.append(chunk)
                data = b"".join(chunks)
                headers = {key: response.headers[key] for key in ("etag", "last-modified", "content-type") if key in response.headers}
            if not data or "text/html" in headers.get("content-type", "").lower() or data.lstrip().lower().startswith((b"<!doctype html", b"<html")):
                raise ContractError("Empty or HTML response cannot be used as a source file.")
            return data, headers
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            retryable = not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code == 429 or exc.response.status_code >= 500
            if not retryable or attempt + 1 == attempts:
                raise
            time.sleep(0.25 * (2 ** attempt))
    raise AssertionError("Unreachable retry state")


class DownloadSession:
    def __init__(self, directory: Path, client: httpx.Client | None = None):
        self.directory = directory.resolve()
        self.client = client or httpx.Client(timeout=httpx.Timeout(45, connect=10), follow_redirects=True)
        self.owns_client = client is None
        self.package = None
        self.manifest = {"dataset_id": DATASET_ID, "resources": []}

    def close(self):
        if self.owns_client:
            self.client.close()

    def _save(self, data: bytes, name: str) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{hashlib.sha256(data).hexdigest()}-{name}"
        if not path.exists():
            with tempfile.NamedTemporaryFile(dir=self.directory, suffix=".partial", delete=False) as file:
                temporary = Path(file.name)
                file.write(data)
            try:
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
        elif path.read_bytes() != data:
            raise ContractError("Archived bytes do not match the content-addressed path.")
        return path

    def prepare(self):
        if self.package is not None:
            return
        data, _ = request_bytes(self.client, PACKAGE_URL)
        package = json.loads(data)
        if not package.get("success") or package["result"]["id"] != DATASET_ID:
            raise ContractError("Unexpected CKAN dataset metadata.")
        self.package = package["result"]
        self.manifest.update({"package_sha256": hashlib.sha256(data).hexdigest(),
                              "package_path": self._save(data, "package.json").name,
                              "metadata_modified": self.package["metadata_modified"]})
        self._download(README_ID, "readme.xlsx")

    def _download(self, resource_id: str, filename: str) -> SourceFile:
        resource = next((r for r in self.package["resources"] if r["id"] == resource_id), None)
        if resource is None:
            raise ContractError(f"Official resource {resource_id} is missing; update the registry after inspection.")
        data, headers = request_bytes(self.client, resource["url"])
        if filename.endswith(".xlsx") and not data.startswith(b"PK"):
            raise ContractError("README download is not an XLSX archive.")
        path = self._save(data, filename)
        retrieved_at = now()
        entry = {"id": resource_id, "name": resource["name"], "url": resource["url"],
                 "path": path.name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                 "retrieved_at": retrieved_at.isoformat(), "source_last_modified": resource.get("last_modified"),
                 "http_headers": headers}
        self.manifest["resources"].append(entry)
        self.write_manifest()
        return SourceFile(data, resource["url"], retrieved_at, resource.get("last_modified"),
                          {**entry, "input_kind": "official_download", "package_sha256": self.manifest["package_sha256"],
                           "metadata_modified": self.manifest["metadata_modified"],
                           "readme_sha256": next((r["sha256"] for r in self.manifest["resources"] if r["id"] == README_ID), None)})

    def resource(self, resource: Resource) -> SourceFile:
        self.prepare()
        return self._download(resource.official_id, f"{resource.kind}.csv")

    def write_manifest(self) -> Path:
        # Retain each attempt's manifest, rather than replacing a shared latest.json.
        path = self.directory / f"manifest-{hashlib.sha256(json.dumps(self.manifest, sort_keys=True).encode()).hexdigest()}.json"
        path.write_text(json.dumps(self.manifest, indent=2) + "\n")
        return path


def load_manifest_file(manifest_path: Path, resource: Resource) -> SourceFile:
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("dataset_id") != DATASET_ID:
        raise ContractError("Manifest is for a different dataset.")
    entry = next((r for r in manifest["resources"] if r["id"] == resource.official_id), None)
    if entry is None:
        raise ContractError("Required resource is missing from the download manifest.")
    path = manifest_path.parent / entry["path"]
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise ContractError("Local file checksum differs from its download manifest.")
    timestamp = datetime.fromisoformat(entry["retrieved_at"])
    if timestamp.tzinfo is None:
        raise ContractError("Manifest retrieval time must include a timezone.")
    return SourceFile(data, entry["url"], timestamp, entry.get("source_last_modified"),
                      {**entry, "input_kind": "verified_manifest",
                       "package_sha256": manifest.get("package_sha256"),
                       "metadata_modified": manifest.get("metadata_modified"),
                       "readme_sha256": next((r["sha256"] for r in manifest["resources"] if r["id"] == README_ID), None)})
