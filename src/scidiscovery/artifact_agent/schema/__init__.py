"""Schema package with no eager aggregate exports.

Import each schema from its owning module.  Keeping this initializer empty
prevents an unrelated control-plane import from loading domain contracts.
"""

__all__: tuple[str, ...] = ()
