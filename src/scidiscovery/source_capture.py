"""Bounded public HTTPS originals for evidence Operations; no new MCP surface."""
from __future__ import annotations

import http.client
import ipaddress
import json
import socket
import ssl
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from pydantic import Field

from .artifact_agent.schema.common import SchemaModel
from .artifact_agent.service.local_workspace import write_control_workspace_file
from .operations.tooling import WorkerToolDefinition

MAX_SOURCE_BYTES = 16 * 1024 * 1024
MEDIA_TYPES = {"application/pdf", "text/html", "text/plain", "text/csv", "application/json"}


class SourceCaptureInput(SchemaModel):
    url: str = Field(min_length=1, max_length=2048, description="Public HTTPS original, not a search snippet. The tool preserves exact bytes and assigns the citation alias.")


def public_source_url(url: str):
    parts = urlsplit(url)
    if (len(url) > 2048 or parts.scheme != "https" or not parts.hostname or parts.username or parts.password
            or parts.port not in (None, 443) or any(ord(c) < 33 for c in url)):
        raise ValueError("source URL must be public HTTPS on port 443 without credentials")
    return parts



def _resolve_addresses(host, timeout):
    lookup = subprocess.run([sys.executable, "-I", "-S", "-B", "-c",
        "import json,socket,sys; print(json.dumps(list(dict.fromkeys(v[4][0] for v in socket.getaddrinfo(sys.argv[1],443,type=socket.SOCK_STREAM)))[:64]))",
        host], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=max(0, min(5, timeout)), check=False)
    if lookup.returncode:
        raise ValueError("source DNS resolution failed: " + lookup.stderr.decode("utf-8", errors="replace")[-1024:])
    return json.loads(lookup.stdout)

class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, address, timeout):
        super().__init__(host, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        # Connect to the checked address without a second DNS lookup; validate TLS
        # against the original host. Redirects repeat both address and policy checks.
        raw = socket.create_connection((self.address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def fetch_source(url, *, reserve_request, timeout):
    deadline = time.monotonic() + timeout
    original = url
    redirects = []
    for _ in range(5):
        parts = public_source_url(url)
        reserve_request(url)
        ips = _resolve_addresses(parts.hostname, deadline - time.monotonic())
        if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
            raise ValueError("source URL resolved to a non-public address")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("source capture deadline exceeded")
        connection = _PinnedHTTPSConnection(parts.hostname, ips[0], min(remaining, 15))
        try:
            path = parts.path or "/"
            if parts.query:
                path += "?" + parts.query
            connection.request("GET", path, headers={"User-Agent": "SciDiscovery/1.0", "Accept-Encoding": "identity"})
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                if not location:
                    raise ValueError("source redirect has no Location")
                redirects.append(url)
                url = urljoin(url, location)
                continue
            if response.status != 200:
                raise ValueError(f"source retrieval returned HTTP {response.status}")
            if response.getheader("Content-Encoding", "identity").lower() != "identity":
                raise ValueError("source content encoding is unsupported")
            media_type = response.getheader("Content-Type", "").split(";", 1)[0].lower().strip()
            if media_type not in MEDIA_TYPES:
                raise ValueError(f"source media type unsupported: {media_type}")
            content_length = response.getheader("Content-Length")
            if content_length is not None and int(content_length) > MAX_SOURCE_BYTES:
                raise ValueError("source exceeds 16 MiB limit")
            chunks = []
            total = 0
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("source capture deadline exceeded")
                if connection.sock is not None:
                    connection.sock.settimeout(min(remaining, 15))
                chunk = response.read1(min(65536, MAX_SOURCE_BYTES + 1 - total))
                total += len(chunk)
                if total > MAX_SOURCE_BYTES:
                    raise ValueError("source exceeds 16 MiB limit")
                if not chunk:
                    break
                chunks.append(chunk)
            raw = b"".join(chunks)
            if content_length is not None and len(raw) != int(content_length):
                raise ValueError("source response is incomplete")
            if not raw:
                raise ValueError("source response is empty")
            return raw, media_type, {
                "origin": "public_web", "requested_url": original, "url": url,
                "redirect_count": len(redirects), "retrieved_at": datetime.now(timezone.utc).isoformat(),
            }
        finally:
            connection.close()
    raise ValueError("source redirect limit exceeded")


def capture_source(parsed, context):
    public_source_url(parsed.url)
    record = next((r for r in context.evidence()
                   if r["metadata"].get("origin") == "public_web"
                   and r["metadata"].get("requested_url") == parsed.url), None)
    if record is None:
        raw, media_type, metadata = fetch_source(parsed.url,
            reserve_request=context.reserve_network_request,
            timeout=max(0, min(45, context.remaining_seconds)))
        record = context.accept_evidence(raw=raw, media_type=media_type,
            metadata=metadata, external_source=True)
    else:
        raw = context.read_evidence(record["alias"])
    suffix = {"application/pdf": ".pdf", "text/html": ".html", "application/json": ".json", "text/csv": ".csv"}.get(record["media_type"], ".txt")
    path = Path(".operation-tools/sources") / (record["alias"] + suffix)
    write_control_workspace_file(context.workspace, path, raw, mode=0o400, replace=True, create_parents=True)
    result = {"status": "captured", "source_alias": record["alias"],
              "path": str(context.workspace / path), "media_type": record["media_type"],
              "size_bytes": record["size_bytes"], "provenance": record["metadata"],
              "instruction": "Inspect the saved original; cite source_alias. Capture alone does not verify a scientific claim."}
    context.finish_attempt(result_status="captured", response=result, successful=True)
    return result


SOURCE_CAPTURE_TOOL = WorkerToolDefinition(
    name="worker_capture_source", description="Preserve one public HTTPS original (up to 16 MiB, five hops and 45 seconds) for citation; return a local path, automatic alias and provenance, not full content. Private addresses, credentials and non-443 ports are refused.",
    input_model=SourceCaptureInput, capability="evidence.capture_source",
    contextual_handler=capture_source, network_access=True, record_attempts=True,
    evidence_ports=("tool_evidence", "recovery_manifest_output"),
)
