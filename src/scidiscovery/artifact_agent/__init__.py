"""Immutable Artifact and task control-plane package.

The package initializer is intentionally side-effect free.  Callers import
services from their owning modules so loading one boundary cannot initialize
unrelated schemas, plugins, storage, or runtime state.
"""

__all__: tuple[str, ...] = ()
