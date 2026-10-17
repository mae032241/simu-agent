"""Shared archive file verification and publication; no service or database imports."""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path


class ArchiveError(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def safe_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}", value) or value in {".", ".."}:
        raise ArchiveError("invalid storage identity")
    return value


def check_path(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ArchiveError("symbolic links are unsupported in managed archive paths")
    return path


def hash_file(path):
    check_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise ArchiveError("archive source is not a regular file")
        sha = hashlib.sha256()
        with os.fdopen(fd, "rb", closefd=False) as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                sha.update(chunk)
        after = os.fstat(fd)
        if (info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ArchiveError("archive file changed while hashing")
        return {"size_bytes": info.st_size, "sha256": sha.hexdigest(), "mode": stat.S_IMODE(info.st_mode),
                "source_stat": [info.st_dev, info.st_ino, info.st_mtime_ns, info.st_ctime_ns]}
    finally:
        os.close(fd)


def fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def durable_json(path, value):
    check_path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(canonical(value))
            stream.flush()
            os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, path)
    fsync_directory(path.parent)


def copy_verified(source, destination, entry):
    """Copy before unlink, including on the same filesystem, to preserve drafts."""
    check_path(source)
    check_path(destination)
    if entry["kind"] == "directory":
        destination.mkdir(parents=True, exist_ok=True, mode=0o700)
        return
    if destination.exists():
        actual = hash_file(destination)
        if any(actual[key] != entry[key] for key in ("sha256", "size_bytes", "mode")):
            raise ArchiveError("destination file collision")
        return
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = destination.with_name(destination.name + ".archive-copy")
    parent_mode = stat.S_IMODE(destination.parent.stat().st_mode)
    descriptor = None
    try:
        os.chmod(destination.parent, parent_mode | 0o700)
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb", closefd=False) as output, open(source, "rb") as input_file:
            for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
                output.write(chunk)
            output.flush()
            os.fchmod(descriptor, entry["mode"])
            os.fsync(descriptor)
        actual = hash_file(temporary)
        if any(actual[key] != entry[key] for key in ("sha256", "size_bytes")):
            raise ArchiveError("copy verification failed")
        # CAS may acquire a new owner while this instance is restoring. Publish
        # without replacement, matching the CAS store's own immutable protocol.
        try:
            os.link(temporary, destination, follow_symlinks=False)
        except FileExistsError:
            actual = hash_file(destination)
            if any(actual[key] != entry[key] for key in ("sha256", "size_bytes", "mode")):
                raise ArchiveError("destination appeared with different content or permissions")
        fsync_directory(destination.parent)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temporary.unlink(missing_ok=True)
        finally:
            os.chmod(destination.parent, parent_mode)
