"""Complete durable transport diagnostics, bound by content identity."""

import hashlib
import os
from pathlib import Path


def preserve_log(root: Path, stream: str, raw: bytes) -> Path:
    directory = root / "logs"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.is_symlink() or directory.is_symlink():
        raise ValueError("transport log directory must not be a symlink")
    path = directory / (hashlib.sha256(raw).hexdigest() + "." + stream + ".log")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        if path.is_symlink() or path.stat().st_size != len(raw):
            raise ValueError("transport log differs from its content identity")
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != path.name.split('.')[0]:
            raise ValueError("transport log differs from its content identity")
    else:
        with os.fdopen(fd, "wb") as file:
            file.write(raw)
    return path
