"""Durable bytes-first content-addressed storage for SciDiscovery."""

from __future__ import annotations

import hashlib
import errno
import os
import stat
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


class CASIntegrityError(RuntimeError):
    """Stored bytes do not match their content address or declared size."""


class CASConfigurationError(RuntimeError):
    """The requested CAS root is unsafe or unusable."""


class CASObjectMissingError(CASIntegrityError):
    """A referenced content-addressed object is absent."""


@dataclass(frozen=True)
class CASObject:
    sha256: str
    size_bytes: int
    path: Path


class ContentAddressedStore:
    """Filesystem CAS using fsync and atomic no-replace publication."""

    def __init__(
        self,
        root: Path | str,
        *,
        file_mode: int = 0o600,
        directory_mode: int = 0o700,
    ) -> None:
        if file_mode not in {0o600, 0o640}:
            raise ValueError("CAS file mode must be 0600 or 0640")
        if directory_mode not in {0o700, 0o770}:
            raise ValueError("CAS directory mode must be 0700 or 0770")
        self.file_mode = file_mode
        self.directory_mode = directory_mode
        self.root = _validate_root(root)
        self._ensure_directory_durable(self.root)
        self.objects_root = self.root / "sha256"
        self._ensure_directory_durable(self.objects_root)

    def put(self, content: bytes) -> CASObject:
        if type(content) is not bytes:
            raise TypeError("CAS content must be bytes")

        digest = hashlib.sha256(content).hexdigest()
        size_bytes = len(content)
        destination = self.path_for(digest)
        try:
            self.verify(digest, expected_size=size_bytes)
            return CASObject(digest, size_bytes, destination)
        except CASObjectMissingError:
            pass

        self._ensure_directory_durable(destination.parent)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{digest}.",
            dir=destination.parent,
        )
        temporary = Path(temporary_name)
        try:
            try:
                os.fchmod(descriptor, self.file_mode)
                self._write_temporary(descriptor, content)
            except Exception:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
                raise
            self._verify_path(
                temporary,
                expected_sha256=digest,
                expected_size=size_bytes,
            )
            self._publish(temporary, destination)
            self._fsync_directory(destination.parent)
            self._verify_path(
                destination,
                expected_sha256=digest,
                expected_size=size_bytes,
            )
        finally:
            temporary.unlink(missing_ok=True)

        return CASObject(digest, size_bytes, destination)

    def read(self, digest: str, *, expected_size: int | None = None) -> bytes:
        path = self.path_for(digest)
        try:
            observed, content = self._read_path(path, include_content=True)
        except FileNotFoundError as error:
            raise CASObjectMissingError(f"CAS object is missing: {digest}") from error
        if observed[0] != digest:
            raise CASIntegrityError(
                "CAS object hash mismatch: "
                f"expected {digest}, observed {observed[0]}"
            )
        if expected_size is not None and observed[1] != expected_size:
            raise CASIntegrityError(
                "CAS object size mismatch: "
                f"expected {expected_size}, observed {observed[1]}"
            )
        assert content is not None
        return content

    def verify(self, digest: str, *, expected_size: int | None = None) -> CASObject:
        path = self.path_for(digest)
        try:
            observed_digest, observed_size = self._hash_path(path)
        except FileNotFoundError as error:
            raise CASObjectMissingError(f"CAS object is missing: {digest}") from error
        if observed_digest != digest:
            raise CASIntegrityError(
                "CAS object hash mismatch: "
                f"expected {digest}, observed {observed_digest}"
            )
        if expected_size is not None and observed_size != expected_size:
            raise CASIntegrityError(
                "CAS object size mismatch: "
                f"expected {expected_size}, observed {observed_size}"
            )
        return CASObject(digest, observed_size, path)

    @contextmanager
    def open_verified(self, digest: str, *, expected_size: int | None = None):
        """Stream an exact original using the same verified, no-follow descriptor."""
        try:
            descriptor = self._open_no_follow(self.path_for(digest), directory=False)
        except FileNotFoundError as error:
            raise CASObjectMissingError(f"CAS object is missing: {digest}") from error
        with os.fdopen(descriptor, "rb") as source:
            observed, size = hashlib.sha256(), 0
            while block := source.read(1024 * 1024):
                observed.update(block)
                size += len(block)
            if observed.hexdigest() != digest or (expected_size is not None and size != expected_size):
                raise CASIntegrityError("CAS original failed hash or size verification")
            source.seek(0)
            yield source

    def path_for(self, digest: str) -> Path:
        _validate_digest(digest)
        return self.objects_root / digest[:2] / digest[2:]

    def iter_digests(self) -> tuple[str, ...]:
        """Return valid content-address paths without modifying the store."""

        if not self.objects_root.exists():
            return ()
        digests: list[str] = []
        for prefix in sorted(self.objects_root.iterdir()):
            if (
                prefix.is_symlink()
                or not prefix.is_dir()
                or not _is_lower_hex(prefix.name, 2)
            ):
                continue
            for candidate in sorted(prefix.iterdir()):
                metadata = os.lstat(candidate)
                if stat.S_ISREG(metadata.st_mode) and _is_lower_hex(
                    candidate.name,
                    62,
                ):
                    digests.append(prefix.name + candidate.name)
        return tuple(digests)

    def iter_unrecognized_paths(self) -> tuple[Path, ...]:
        """Report non-temporary files that do not follow the CAS layout."""

        if not self.objects_root.exists():
            return ()
        invalid: list[Path] = []
        for candidate in sorted(self.objects_root.rglob("*")):
            if candidate.is_symlink():
                invalid.append(candidate)
                continue
            if candidate.is_dir():
                continue
            relative = candidate.relative_to(self.objects_root)
            if (
                candidate.is_symlink()
                or len(relative.parts) != 2
                or not _is_lower_hex(relative.parts[0], 2)
                or not _is_lower_hex(relative.parts[1], 62)
            ):
                invalid.append(candidate)
        return tuple(invalid)

    def discard(self, digest: str) -> bool:
        """Unlink one exact verified CAS object during serialized maintenance."""

        try:
            value = self.verify(digest)
        except CASObjectMissingError:
            return False
        value.path.unlink()
        self._fsync_directory(value.path.parent)
        return True

    @staticmethod
    def _write_temporary(descriptor: int, content: bytes) -> None:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())

    @staticmethod
    def _publish(temporary: Path, destination: Path) -> None:
        try:
            os.link(temporary, destination, follow_symlinks=False)
        except FileExistsError:
            # A concurrent writer won. The caller verifies the published bytes.
            return

    @classmethod
    def _fsync_directory(cls, directory: Path) -> None:
        descriptor = cls._open_no_follow(directory, directory=True)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _ensure_directory_durable(self, directory: Path) -> None:
        directory = directory.absolute()
        current = Path(directory.anchor)
        for component in directory.parts[1:]:
            candidate = current / component
            try:
                metadata = os.lstat(candidate)
            except FileNotFoundError:
                try:
                    os.mkdir(candidate, self.directory_mode)
                except FileExistsError:
                    metadata = os.lstat(candidate)
                else:
                    os.chmod(candidate, self.directory_mode)
                    self._fsync_directory(current)
                    metadata = os.lstat(candidate)
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                raise CASConfigurationError(
                    f"CAS directory path must not contain symlinks: {candidate}"
                )
            current = candidate

    def _verify_path(
        self,
        path: Path,
        *,
        expected_sha256: str,
        expected_size: int,
    ) -> None:
        observed_sha256, observed_size = self._hash_path(path)
        if observed_sha256 != expected_sha256 or observed_size != expected_size:
            raise CASIntegrityError(
                f"CAS path failed verification: {path}"
            )

    @classmethod
    def _hash_path(cls, path: Path) -> tuple[str, int]:
        observed, _ = cls._read_path(path, include_content=False)
        return observed

    @classmethod
    def _read_path(
        cls,
        path: Path,
        *,
        include_content: bool,
    ) -> tuple[tuple[str, int], bytes | None]:
        descriptor = cls._open_no_follow(path, directory=False)
        digest = hashlib.sha256()
        size_bytes = 0
        chunks: list[bytes] | None = [] if include_content else None
        try:
            while block := os.read(descriptor, 1024 * 1024):
                digest.update(block)
                size_bytes += len(block)
                if chunks is not None:
                    chunks.append(block)
        finally:
            os.close(descriptor)
        content = b"".join(chunks) if chunks is not None else None
        return (digest.hexdigest(), size_bytes), content

    @staticmethod
    def _open_no_follow(path: Path, *, directory: bool) -> int:
        absolute = path.absolute()
        no_follow = getattr(os, "O_NOFOLLOW", 0)
        directory_flag = getattr(os, "O_DIRECTORY", 0)
        close_on_exec = getattr(os, "O_CLOEXEC", 0)
        current: int | None = os.open(
            absolute.anchor,
            os.O_RDONLY | directory_flag | no_follow | close_on_exec,
        )
        try:
            components = absolute.parts[1:]
            if not components:
                descriptor = current
                current = None
            else:
                for component in components[:-1]:
                    assert current is not None
                    next_descriptor = os.open(
                        component,
                        os.O_RDONLY | directory_flag | no_follow | close_on_exec,
                        dir_fd=current,
                    )
                    os.close(current)
                    current = next_descriptor
                flags = os.O_RDONLY | no_follow | close_on_exec
                if directory:
                    flags |= directory_flag
                assert current is not None
                descriptor = os.open(components[-1], flags, dir_fd=current)
        except OSError as error:
            if error.errno in (errno.ELOOP, errno.ENOTDIR):
                raise CASIntegrityError(
                    f"CAS path contains a symlink or non-directory: {path}"
                ) from error
            raise
        finally:
            if current is not None:
                os.close(current)

        metadata = os.fstat(descriptor)
        expected_type = stat.S_ISDIR if directory else stat.S_ISREG
        if not expected_type(metadata.st_mode):
            os.close(descriptor)
            expected = "directory" if directory else "regular file"
            raise CASIntegrityError(f"CAS path is not a {expected}: {path}")
        return descriptor


def _validate_digest(digest: str) -> None:
    if type(digest) is not str or not _is_lower_hex(digest, 64):
        raise ValueError("CAS digest must be 64 lowercase hexadecimal characters")


def _validate_root(root: Path | str) -> Path:
    if not isinstance(root, (Path, str)):
        raise TypeError("CAS root must be a filesystem path")
    return Path(root).expanduser().absolute()


def _is_lower_hex(value: str, length: int) -> bool:
    return (
        len(value) == length
        and value.lower() == value
        and all(character in "0123456789abcdef" for character in value)
    )


__all__ = [
    "CASIntegrityError",
    "CASConfigurationError",
    "CASObject",
    "CASObjectMissingError",
    "ContentAddressedStore",
]
