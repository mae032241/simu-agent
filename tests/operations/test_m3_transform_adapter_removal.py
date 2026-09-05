from __future__ import annotations

import ast
from pathlib import Path



REPOSITORY = Path(__file__).resolve().parents[2]
REMOVED_ADAPTERS = {
    "CompiledTransformAdapter",
    "CurveScoreTransformAdapter",
    "InGaAsFig4TransformAdapter",
    "ScientificStateTransformAdapter",
    "TCADProjectTransformAdapter",
}
TRANSFORM_MODULES = (
    REPOSITORY / "src/scidiscovery/artifact_agent/transforms.py",
    REPOSITORY / "plugins/curve_score/curve_score/transform_adapter.py",
    REPOSITORY / "plugins/ingaas_fig4/ingaas_fig4/transform_adapter.py",
    REPOSITORY / "plugins/tcad_artifact/tcad_artifact/transform_adapter.py",
)
OPERATION_COMPONENT_MODULES = (
    REPOSITORY / "plugins/curve_score/curve_score/operation_transforms.py",
    REPOSITORY / "plugins/tcad_artifact/tcad_artifact/operation_transforms.py",
)


def test_domain_transforms_have_no_profile_adapter_or_legacy_bridge() -> None:
    for path in TRANSFORM_MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        classes = {
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        }
        functions = {
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        }
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        assert not classes & REMOVED_ADAPTERS, path
        assert "supports_transform_profile" not in functions, path
        assert "TransformOutput" not in imports, path

    for path in OPERATION_COMPONENT_MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert not any(
            isinstance(node, ast.FunctionDef) and node.name == "_legacy"
            for node in ast.walk(tree)
        ), path


def test_only_one_compiled_transform_invoker_remains() -> None:
    path = REPOSITORY / "src/scidiscovery/operations/invoke.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assert not {
        node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
    } & REMOVED_ADAPTERS
    assert [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "execute_compiled_transform"
    ] == ["execute_compiled_transform"]
