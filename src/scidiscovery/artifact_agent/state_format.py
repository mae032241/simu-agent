"""Reject incompatible control stores before opening or creating databases.

The marker identifies a storage generation, independently of package versions.
Only an empty directory may be initialized; existing data is never migrated.
"""
from __future__ import annotations

import fcntl
import json
import os
import stat
from pathlib import Path

STATE_FORMAT = "scidiscovery-state-v3"
MARKER = ".scidiscovery-state.json"


class StateFormatError(RuntimeError):
    pass


def ensure_state_format(root: Path | str, *, shared_group: bool = False, initialize: bool = True) -> None:
    root = Path(root).expanduser().absolute()
    if initialize:
        root.mkdir(parents=True, exist_ok=True, mode=0o750 if shared_group else 0o700)
    error = f"Incompatible or unmarked SciDiscovery state at {root}; use a new empty state root."
    try:
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except FileNotFoundError:
        if not initialize:
            return
        raise
    except OSError as exc:
        raise StateFormatError(error) from exc
    try:
        # Lock the directory itself so rejecting old state does not alter it.
        fcntl.flock(directory, fcntl.LOCK_EX)
        try:
            descriptor = os.open(MARKER, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        except FileNotFoundError:
            with os.scandir(directory) as entries:
                if next(entries, None) is not None:
                    raise StateFormatError(error)
            if not initialize:
                return
            descriptor = os.open(MARKER, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o640 if shared_group else 0o600, dir_fd=directory)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write((json.dumps({"format": STATE_FORMAT}) + "\n").encode())
                stream.flush()
                os.fsync(stream.fileno())
            os.fsync(directory)
            return
        except OSError as exc:
            raise StateFormatError(error) from exc
        with os.fdopen(descriptor, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise StateFormatError(error)
            raw = stream.read(1025)
        try:
            if len(raw) > 1024 or json.loads(raw) != {"format": STATE_FORMAT}:
                raise ValueError("unknown state format")
        except (ValueError, UnicodeError) as exc:
            raise StateFormatError(error) from exc
    finally:
        os.close(directory)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("state_root", type=Path)
    parser.add_argument("--shared-group", action="store_true")
    parser.add_argument("--check", action="store_true", help="Validate existing state without creating a directory or marker")
    args = parser.parse_args()
    ensure_state_format(args.state_root, shared_group=args.shared_group, initialize=not args.check)
