from __future__ import annotations

import sqlite3

from scidiscovery.artifact_agent.storage.sqlite import SQLiteArtifactRegistry
from architecture_operation_test_plugin.plugin import ARCHITECTURE_TEST_PLUGIN as PLUGIN
from scidiscovery.operations.catalog import compile_catalog


def _schema(database_path) -> tuple[tuple[str, str, str], ...]:
    with sqlite3.connect(database_path) as connection:
        return tuple(
            connection.execute(
                "SELECT type, name, sql FROM sqlite_master "
                "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
            ).fetchall()
        )


def test_catalog_compilation_does_not_change_sqlite_schema(tmp_path) -> None:
    database = tmp_path / "registry.sqlite3"
    SQLiteArtifactRegistry(database)
    before = _schema(database)
    compile_catalog((PLUGIN,))
    after = _schema(database)
    assert after == before
