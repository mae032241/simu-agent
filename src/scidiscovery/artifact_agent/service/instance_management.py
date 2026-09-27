"""Short-lived local capabilities for direct research-instance management."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class InstanceManagementCapabilityError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class InstanceManagementCapability:
    session_key: str
    expires_at: str


def issue_instance_management_capability(
    *,
    session_key: str,
    secret: bytes,
    now: datetime | None = None,
    lifetime: timedelta = timedelta(minutes=15),
) -> str:
    _validate_secret(secret)
    _validate_session_key(session_key)
    current = _utc(now)
    if lifetime <= timedelta(0) or lifetime > timedelta(hours=1):
        raise ValueError("instance-management capability lifetime is invalid")
    payload = json.dumps(
        {
            "expires_at": _timestamp(current + lifetime),
            "session_key": session_key,
            "version": 1,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    nonce = os.urandom(12)
    ciphertext = AESGCM(_capability_key(secret)).encrypt(
        nonce,
        payload,
        b"scidiscovery.instance-management.v1",
    )
    return _encode(nonce + ciphertext)


def verify_instance_management_capability(
    token: str,
    *,
    secret: bytes,
    now: datetime | None = None,
) -> InstanceManagementCapability:
    _validate_secret(secret)
    if not isinstance(token, str) or len(token) > 2048:
        raise InstanceManagementCapabilityError(
            "instance-management capability is invalid"
        )
    try:
        sealed = _decode(token)
        if len(sealed) < 29:
            raise ValueError
        payload = AESGCM(_capability_key(secret)).decrypt(
            sealed[:12],
            sealed[12:],
            b"scidiscovery.instance-management.v1",
        )
        value = json.loads(payload)
        if not isinstance(value, dict) or value.get("version") != 1:
            raise ValueError
        session_key = value["session_key"]
        expires_at = value["expires_at"]
        _validate_session_key(session_key)
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except (
        InvalidTag,
        KeyError,
        TypeError,
        ValueError,
        UnicodeError,
        json.JSONDecodeError,
    ) as error:
        raise InstanceManagementCapabilityError(
            "instance-management capability is invalid"
        ) from error
    if expiry <= _utc(now):
        raise InstanceManagementCapabilityError(
            "instance-management capability has expired"
        )
    return InstanceManagementCapability(
        session_key=session_key,
        expires_at=expires_at,
    )


def _validate_secret(secret: bytes) -> None:
    if type(secret) is not bytes or len(secret) < 32:
        raise ValueError("instance-management secret must contain at least 32 bytes")


def _validate_session_key(session_key: str) -> None:
    if not isinstance(session_key, str) or not 1 <= len(session_key) <= 256:
        raise ValueError("scheduler session key is invalid")


def _capability_key(secret: bytes) -> bytes:
    return hashlib.sha256(
        b"scidiscovery.instance-management.key.v1\0" + secret
    ).digest()


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _utc(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("instance-management time must be timezone-aware")
    return current.astimezone(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


__all__ = [
    "InstanceManagementCapability",
    "InstanceManagementCapabilityError",
    "issue_instance_management_capability",
    "verify_instance_management_capability",
]
