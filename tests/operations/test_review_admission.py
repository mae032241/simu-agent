from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.review_admission import review_receiver_diagnostics
from curve_score.plugin import PLUGIN as CURVE
from tcad_artifact.plugin import PLUGIN as TCAD


def _catalog(tcad=TCAD):
    return compile_catalog((CORE_PLUGIN, GENERAL, CURVE, tcad))


def test_receiver_diagnostic_detects_missing_plan_review_without_blocking_catalog():
    package_id = "tcad.reviewed-deck-package.v2"
    old = TCAD.model_copy(update={"operations": tuple(
        op.model_copy(update={"inputs": tuple(p for p in op.inputs if p.name != "experiment_review")})
        if op.operation_id == package_id else op for op in TCAD.operations
    )})
    rows = review_receiver_diagnostics(_catalog(old))
    missing = [r for r in rows if r["consumer_operation"] == package_id
               and r["subject_port"] == "experiment_plan"]
    assert missing
    assert all(r["status"] == "receiver_missing" for r in missing)

    fixed = [r for r in review_receiver_diagnostics(_catalog())
             if r["consumer_operation"] == package_id
             and r["subject_port"] == "experiment_plan"]
    assert {r["producer_operation"] for r in fixed} == {
        "science.experiment.materialize.v1", "science.experiment.revise.v1",
    }
    assert all(r["candidate_ports"] == ("experiment_review",)
               and r["status"] == "requires_bound_validation" for r in fixed)


def test_receiver_diagnostics_preserve_review_revision_and_background_modes():
    for catalog in (compile_catalog((CORE_PLUGIN, GENERAL)), _catalog()):
        rows = review_receiver_diagnostics(catalog)
        assert any(r["mode"] == "review_subject" for r in rows)
        assert any(r["mode"] == "direct_revision" for r in rows)
        for row in rows:
            subject = next(p for p in catalog.operation(row["consumer_operation"]).spec.inputs
                           if p.name == row["subject_port"])
            assert subject.usage != "evidence_inventory"
            if row["mode"] in {"review_subject", "direct_revision"}:
                assert row["status"] == "requires_bound_validation"


def test_wildcard_inventory_can_receive_a_review_but_is_not_a_review_subject():
    inventory = next(p for op in TCAD.operations for p in op.inputs
                     if p.name == "current_progress" and p.schema_id == "*")
    package_id = "tcad.reviewed-deck-package.v2"
    plugin = TCAD.model_copy(update={"operations": tuple(
        op.model_copy(update={"inputs": tuple(p for p in op.inputs
                                             if p.name != "experiment_review")
                             + (inventory,)})
        if op.operation_id == package_id else op for op in TCAD.operations
    )})
    rows = [r for r in review_receiver_diagnostics(_catalog(plugin))
            if r["consumer_operation"] == package_id]
    assert not any(r["subject_port"] == "current_progress" for r in rows)
    plan_rows = [r for r in rows if r["subject_port"] == "experiment_plan"]
    assert plan_rows
    assert all(r["candidate_ports"] == ("current_progress",)
               and r["status"] == "requires_bound_validation" for r in plan_rows)
