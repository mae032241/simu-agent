"""Capability grouping and real Run-owned source publication; no external network."""
import json
from pathlib import Path

import pytest

from scidiscovery import source_capture
from scidiscovery.operations.tooling import operation_agent_type, operation_role_instructions
from tests.operations.test_general_transform_operations import _intake


def mock_original(monkeypatch):
    def fetch(url, *, reserve_request, timeout):
        reserve_request(url)
        return b"Measured target at a bounded depth.", "text/plain", {
            "origin": "public_web", "url": url, "requested_url": url,
            "retrieved_at": "2026-09-17T01:00:00+00:00", "redirect_count": 0}
    monkeypatch.setattr(source_capture, "fetch_source", fetch)


@pytest.mark.parametrize("url", ["http://example.org", "file:///etc/passwd", "https://user:pass@example.org", "https://example.org:8443/"])
def test_capture_rejects_non_public_url_shapes(url):
    with pytest.raises(ValueError):
        source_capture.public_source_url(url)


def test_capture_rejects_private_dns_and_redirect_targets(monkeypatch):
    monkeypatch.setattr(source_capture, "_resolve_addresses", lambda *a, **k: ["127.0.0.1"])
    with pytest.raises(ValueError, match="non-public"):
        source_capture.fetch_source("https://example.org/", reserve_request=lambda _: None, timeout=1)


def test_http_redirect_to_private_address_is_never_connected(monkeypatch):
    def addresses(host, *args, **kwargs):
        return ["93.184.216.34" if host == "example.org" else "127.0.0.1"]
    monkeypatch.setattr(source_capture, "_resolve_addresses", addresses)
    connected = []
    class Redirect:
        status = 302
        def getheader(self, name):
            return "https://internal.example/secret"
    class Connection:
        def __init__(self, host, address, timeout): connected.append(address)
        def request(self, *args, **kwargs): pass
        def getresponse(self): return Redirect()
        def close(self): pass
    monkeypatch.setattr(source_capture, "_PinnedHTTPSConnection", Connection)
    with pytest.raises(ValueError, match="non-public"):
        source_capture.fetch_source("https://example.org/", reserve_request=lambda _: None, timeout=5)
    assert connected == ["93.184.216.34"]
