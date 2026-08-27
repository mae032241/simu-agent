"""Bounded public-HTTPS fetcher for reproducible task evidence."""

from __future__ import annotations

import ipaddress
import os
import socket
import ssl
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path


MAX_WEB_BYTES = 8 * 1024 * 1024
MAX_REDIRECTS = 4
FAKE_IP_NETWORK = ipaddress.ip_network("198.18.0.0/15")
FAKE_IP_OPT_IN_ENV = "SCID_WEB_FETCH_ALLOW_FAKE_IP"


class WebFetchError(RuntimeError):
    pass


@dataclass(frozen=True)
class FetchedWebEvidence:
    original_url: str
    final_url: str
    accessed_at: str
    http_status: int
    media_type: str
    body: bytes
    text: str
    text_truncated: bool


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def fetch_web_evidence(url: str, *, max_chars: int = 131072) -> FetchedWebEvidence:
    if not 1 <= max_chars <= 262144:
        raise ValueError("max_chars must be between 1 and 262144")
    original = _validate_public_https(url)
    current = original
    context = ssl.create_default_context()
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=context),
        _NoRedirect(),
    )
    for _ in range(MAX_REDIRECTS + 1):
        request = urllib.request.Request(
            current,
            headers={
                "User-Agent": "SciDiscovery-WebEvidence/1.0",
                "Accept": "text/html,text/plain,application/json,application/pdf,application/xml;q=0.9,*/*;q=0.1",
            },
            method="GET",
        )
        try:
            response = opener.open(request, timeout=15)
        except urllib.error.HTTPError as error:
            if error.code in {301, 302, 303, 307, 308}:
                location = error.headers.get("Location")
                if not location:
                    raise WebFetchError("web redirect has no location") from error
                current = _validate_public_https(
                    urllib.parse.urljoin(current, location)
                )
                continue
            raise WebFetchError(f"web request returned HTTP {error.code}") from error
        except (OSError, urllib.error.URLError) as error:
            raise WebFetchError("web request failed") from error
        with response:
            status = int(response.status)
            if not 200 <= status <= 299:
                raise WebFetchError(f"web request returned HTTP {status}")
            body = response.read(MAX_WEB_BYTES + 1)
            if len(body) > MAX_WEB_BYTES:
                raise WebFetchError("web response exceeds byte limit")
            media_type = response.headers.get_content_type().lower()
            charset = response.headers.get_content_charset()
        text = _extract_text(body, media_type=media_type, charset=charset)
        return FetchedWebEvidence(
            original_url=original,
            final_url=current,
            accessed_at=_timestamp(),
            http_status=status,
            media_type=(
                f"{media_type}; charset={charset}"
                if charset and media_type.startswith("text/")
                else media_type
            ),
            body=body,
            text=text[:max_chars],
            text_truncated=len(text) > max_chars,
        )
    raise WebFetchError("web redirect limit exceeded")


def _validate_public_https(value: str) -> str:
    if not isinstance(value, str) or len(value) > 4096 or any(
        ord(character) < 32 for character in value
    ):
        raise WebFetchError("web URL is invalid")
    parsed = urllib.parse.urlsplit(value)
    try:
        port = parsed.port
    except ValueError as error:
        raise WebFetchError("web URL has an invalid port") from error
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
    ):
        raise WebFetchError("web evidence requires a public HTTPS URL")
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(
                parsed.hostname, 443, type=socket.SOCK_STREAM
            )
        }
    except OSError as error:
        raise WebFetchError("web hostname resolution failed") from error
    if not addresses or any(not _is_allowed_web_address(item) for item in addresses):
        raise WebFetchError("web hostname does not resolve exclusively to public addresses")
    return urllib.parse.urlunsplit(
        ("https", parsed.netloc.lower(), parsed.path or "/", parsed.query, "")
    )


def _is_allowed_web_address(value: str) -> bool:
    address = ipaddress.ip_address(value)
    if address.is_global:
        return True
    return (
        os.environ.get(FAKE_IP_OPT_IN_ENV) == "1"
        and address.version == 4
        and address in FAKE_IP_NETWORK
    )


def _extract_text(body: bytes, *, media_type: str, charset: str | None) -> str:
    if media_type == "application/pdf":
        return _extract_pdf(body)
    if media_type == "text/html":
        decoded = body.decode(charset or "utf-8", errors="replace")
        parser = _TextExtractor()
        parser.feed(decoded)
        return "\n".join(parser.parts)
    if media_type.startswith("text/") or media_type in {
        "application/json",
        "application/xml",
    }:
        return body.decode(charset or "utf-8", errors="replace")
    raise WebFetchError(f"unsupported web evidence media type: {media_type}")


def _extract_pdf(body: bytes) -> str:
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "source.pdf"
        source.write_bytes(body)
        try:
            completed = subprocess.run(
                ["pdftotext", "-layout", str(source), "-"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=20,
                check=False,
            )
        except FileNotFoundError as error:
            raise WebFetchError("pdftotext is unavailable") from error
        except subprocess.TimeoutExpired as error:
            raise WebFetchError("web PDF extraction timed out") from error
        if completed.returncode != 0:
            raise WebFetchError("web PDF extraction failed")
        return completed.stdout.decode("utf-8", errors="replace")


def _timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


__all__ = [
    "FetchedWebEvidence",
    "FAKE_IP_NETWORK",
    "FAKE_IP_OPT_IN_ENV",
    "MAX_WEB_BYTES",
    "WebFetchError",
    "fetch_web_evidence",
]
