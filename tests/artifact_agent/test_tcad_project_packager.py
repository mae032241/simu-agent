from __future__ import annotations

import json
import tarfile
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from tcad_artifact.execution_control import (
    TCADExecutionFacade,
    TCADExecutionPolicy,
    ToolProfile,
)
from tcad_artifact.project_packager import (
    DeckFile,
    DeckFilePatch,
    DeckProjectDraft,
    DeckProjectPatch,
    DeckRequirementReview,
    DeckReviewReport,
    PackagerError,
    ParameterBinding,
    ParameterBindingPatch,
    ProjectExpectedOutput,
    ProjectResourceLimits,
    RealizationRequirement,
    ReviewedDeckPackage,
    RuntimeAttestation,
    RuntimeOutputRecord,
    TCADRuntimeManifest,
    RuntimeAssertion,
    apply_deck_project_patch,
    attest_runtime_contract,
    deck_project_diff,
    package_deck_project,
    package_deck_project_json,
    package_reviewed_deck_json,
    validate_deck_project_output,
    validate_deck_review_against_project,
)


def _draft() -> DeckProjectDraft:
    return DeckProjectDraft(
        tool_profile="shell_smoke",
        files=(
            DeckFile(
                relative_path="run.sh",
                content="printf 'curve\\n' > curve.plt\n",
            ),
            DeckFile(
                relative_path="parameters.inc",
                content="temperature_k=140\n",
            ),
        ),
        entrypoint="run.sh",
        arguments=(),
        expected_outputs=(
            ProjectExpectedOutput(
                name="curve",
                relative_path="curve.plt",
                media_type="text/plain",
                max_bytes=1024,
            ),
        ),
        parameter_bindings=(
            ParameterBinding(
                name="temperature_k",
                declared_value="140",
                unit="K",
                relative_path="parameters.inc",
                locator="temperature_k=140",
                evidence_class="paper_fact",
                evidence_source="reference paper",
                evidence_locator="Table I",
                rationale="The paper reports the measurement temperature.",
                requirement_keys=("temperature_control",),
            ),
        ),
        runtime_assertions=(
            RuntimeAssertion(
                description="The curve output must be present.",
                expected_output_name="curve",
            ),
        ),
        realization_manifest=(
            RealizationRequirement(
                requirement_key="temperature_control",
                category="numerical_protocol",
                requirement="Run the case at 140 K.",
                evidence_class="paper_fact",
                evidence_source="reference paper",
                evidence_locator="Table I",
                rationale="The measurement temperature is fixed by the target study.",
                implementation_status="implemented",
                relative_path="parameters.inc",
                locator="temperature_k=140",
                verification_mode="static_review",
            ),
            RealizationRequirement(
                requirement_key="curve_output",
                category="observable",
                requirement="Collect the declared curve output.",
                evidence_class="experiment_plan",
                evidence_source="smoke validation plan",
                evidence_locator="curve check",
                rationale="The curve is the only observable in this fixture.",
                implementation_status="implemented",
                relative_path="run.sh",
                locator="curve.plt",
                verification_mode="runtime_output",
                expected_output_name="curve",
            ),
        ),
        resource_limits=ProjectResourceLimits(
            wall_time_seconds=10,
            cpu_time_seconds=10,
            max_memory_bytes=256 * 1024 * 1024,
            max_output_bytes=1024 * 1024,
            max_processes=8,
        ),
    )


def _passing_review(project: DeckProjectDraft | None = None) -> DeckReviewReport:
    value = project or _draft()
    return DeckReviewReport(
        verdict="pass",
        summary="The complete fixture is internally consistent.",
        rationale="Every declared requirement maps to an exact implementation.",
        physical_fidelity="pass",
        implementation_fidelity="pass",
        syntax_fidelity="pass",
        numerical_protocol_fidelity="pass",
        requirement_reviews=tuple(
            DeckRequirementReview(
                requirement_key=item.requirement_key,
                status="pass",
                rationale="The declared locator and verification method are consistent.",
            )
            for item in value.realization_manifest
        ),
        execution_ready=True,
    )


def test_packager_is_deterministic_and_produces_runnable_job(tmp_path: Path) -> None:
    packaged = package_deck_project(_draft(), output_root=tmp_path / "packages")
    repeated = package_deck_project(_draft(), output_root=tmp_path / "packages")

    assert packaged == repeated
    assert packaged.job_spec.input_archive.sha256 == packaged.archive.sha256
    assert packaged.job_spec.arguments == ("run.sh",)
    assert packaged.project_sha256 in packaged.package_directory.name

    with tarfile.open(packaged.archive.local_path, "r") as archive:
        members = archive.getmembers()
        assert [item.name for item in members] == ["parameters.inc", "run.sh"]
        assert all(item.uid == 0 and item.gid == 0 and item.mtime == 0 for item in members)
        assert archive.extractfile("run.sh").read() == b"printf 'curve\\n' > curve.plt\n"

    raw_job = Path(packaged.job_spec_file.local_path).read_bytes()
    assert json.loads(raw_job) == packaged.job_spec.model_dump(mode="json")

    runner = TCADExecutionFacade(
        policy=TCADExecutionPolicy(
            allowed_input_roots=(str(packaged.package_directory),),
            tools=(ToolProfile(profile_id="shell_smoke", executable="/bin/sh"),),
        ),
        state_root=tmp_path / "tcad-state",
    )
    submitted = runner.tcad_submit(submission=packaged.job_spec_file)
    deadline = time.monotonic() + 5
    while True:
        status = runner.tcad_status(run_id=submitted["run_id"])
        if status["done"]:
            break
        assert time.monotonic() < deadline
        time.sleep(0.02)
    assert status["state"] == "succeeded"


@pytest.mark.parametrize(
    "path",
    ["/absolute.cmd", "../escape.cmd", "nested//empty.cmd", "windows\\path.cmd"],
)
def test_packager_rejects_unsafe_deck_paths(path: str) -> None:
    with pytest.raises(ValidationError, match="unsafe relative path"):
        DeckFile(relative_path=path, content="go\n")


def test_project_contract_rejects_missing_entrypoint_and_bad_bindings() -> None:
    with pytest.raises(ValidationError, match="entrypoint must name one project file"):
        DeckProjectDraft(
            **{
                **_draft().model_dump(mode="python"),
                "entrypoint": "missing.cmd",
            }
        )

    with pytest.raises(
        ValidationError, match="parameter evidence fields must be supplied together"
    ):
        ParameterBinding(
            name="temperature_k",
            declared_value="140",
            unit="K",
            relative_path="parameters.inc",
            locator="temperature_k=140",
            evidence_class="paper_fact",
        )

    with pytest.raises(ValidationError, match="parameter binding file must exist"):
        DeckProjectDraft(
            **{
                **_draft().model_dump(mode="python"),
                "parameter_bindings": (
                    {
                        "name": "temperature_k",
                        "declared_value": "140",
                        "unit": "K",
                        "relative_path": "missing.inc",
                        "locator": "temperature_k=140",
                    },
                ),
            }
        )


def test_existing_package_tampering_is_detected(tmp_path: Path) -> None:
    packaged = package_deck_project(_draft(), output_root=tmp_path / "packages")
    archive = Path(packaged.archive.local_path)
    archive.chmod(0o640)
    archive.write_bytes(b"tampered")

    with pytest.raises(PackagerError, match="existing package differs"):
        package_deck_project(_draft(), output_root=tmp_path / "packages")


def test_deck_patch_changes_only_declared_file_and_binding() -> None:
    base = _draft()
    patch = DeckProjectPatch(
        file_operations=(
            DeckFilePatch(
                operation="replace",
                relative_path="parameters.inc",
                content="temperature_k=150\n",
            ),
        ),
        parameter_binding_operations=(
            ParameterBindingPatch(
                operation="replace",
                name="temperature_k",
                binding=ParameterBinding(
                    name="temperature_k",
                    declared_value="150",
                    unit="K",
                    relative_path="parameters.inc",
                    locator="temperature_k=150",
                    evidence_class="numerical_assumption",
                    evidence_source="reviewed experiment",
                    evidence_locator="case control_temperature",
                    rationale="Bounded control value selected before execution.",
                    requirement_keys=("temperature_control",),
                ),
            ),
        ),
        replacement_realization_manifest=(
            RealizationRequirement(
                requirement_key="temperature_control",
                category="numerical_protocol",
                requirement="Run the case at 150 K.",
                evidence_class="numerical_assumption",
                evidence_source="reviewed experiment",
                evidence_locator="case control_temperature",
                rationale="The bounded control changes only the case temperature.",
                implementation_status="implemented",
                relative_path="parameters.inc",
                locator="temperature_k=150",
                verification_mode="static_review",
            ),
            base.realization_manifest[1],
        ),
        rationale="Change one reviewed control temperature.",
    )
    revised = apply_deck_project_patch(base, patch)
    assert revised.entrypoint == base.entrypoint
    assert revised.resource_limits == base.resource_limits
    assert revised.parameter_bindings[0].declared_value == "150"
    assert deck_project_diff(base, revised) == {
        "file_changes": [
            {"relative_path": "parameters.inc", "operation": "replace"}
        ],
        "parameter_binding_changes": ["temperature_k"],
        "realization_requirement_changes": ["temperature_control"],
        "frozen_field_changes": [],
    }


def test_new_author_output_requires_traceable_realization_manifest() -> None:
    valid = _draft().model_dump(mode="json")
    assert validate_deck_project_output(valid)["realization_manifest"]

    without_manifest = {**valid, "realization_manifest": []}
    with pytest.raises(ValueError, match="non-empty realization_manifest"):
        validate_deck_project_output(without_manifest)

    without_parameter_coverage = {
        **valid,
        "parameter_bindings": [
            {
                **valid["parameter_bindings"][0],
                "requirement_keys": [],
            }
        ],
    }
    with pytest.raises(ValueError, match="require requirement_keys"):
        validate_deck_project_output(without_parameter_coverage)


def test_deck_review_must_cover_exact_embedded_manifest() -> None:
    report = _passing_review()
    validate_deck_review_against_project(_draft(), report)

    incomplete = report.model_copy(
        update={"requirement_reviews": report.requirement_reviews[:1]}
    )
    with pytest.raises(ValueError, match="exact realization manifest"):
        validate_deck_review_against_project(_draft(), incomplete)


def test_only_a_passing_review_can_form_an_execution_package(tmp_path: Path) -> None:
    reviewed = ReviewedDeckPackage(project=_draft(), review=_passing_review())
    raw = json.dumps(
        reviewed.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    packaged = package_reviewed_deck_json(raw, output_root=tmp_path / "packages")
    assert Path(packaged.job_spec_file.local_path).is_file()

    failing = _passing_review().model_copy(
        update={"verdict": "revise", "execution_ready": False}
    )
    with pytest.raises(ValidationError, match="passing execution-ready review"):
        ReviewedDeckPackage(project=_draft(), review=failing)


def test_runtime_attestation_closes_only_the_declared_execution_contract() -> None:
    reviewed = ReviewedDeckPackage(project=_draft(), review=_passing_review())
    manifest = TCADRuntimeManifest(
        started_at="2026-08-07T00:00:00Z",
        completed_at="2026-08-07T00:00:01Z",
        terminal_state="succeeded",
        exit_code=0,
        error="",
        outputs=(
            RuntimeOutputRecord(
                name="curve",
                relative_path="curve.plt",
                media_type="text/plain",
                sha256="a" * 64,
                size_bytes=12,
            ),
        ),
    )
    attestation = attest_runtime_contract(reviewed, manifest)
    assert isinstance(attestation, RuntimeAttestation)
    assert attestation.verdict == "pass"
    assert attestation.scope == "execution_contract_only"

    missing = manifest.model_copy(update={"outputs": ()})
    rejected = attest_runtime_contract(reviewed, missing)
    assert rejected.verdict == "fail"
    assert rejected.missing_required_outputs == ("curve",)


def test_deck_patch_rejects_unknown_replace_target() -> None:
    patch = DeckProjectPatch(
        file_operations=(
            DeckFilePatch(
                operation="replace",
                relative_path="missing.cmd",
                content="go\n",
            ),
        ),
        rationale="Invalid fixture.",
    )
    with pytest.raises(PackagerError, match="replace target does not exist"):
        apply_deck_project_patch(_draft(), patch)


def test_canonical_artifact_bytes_can_be_packaged_without_agent_rewrite(
    tmp_path: Path,
) -> None:
    raw = json.dumps(
        _draft().model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    packaged = package_deck_project_json(raw, output_root=tmp_path / "packages")
    assert Path(packaged.job_spec_file.local_path).is_file()

    noncanonical = json.dumps(_draft().model_dump(mode="json"), indent=2).encode()
    with pytest.raises(PackagerError, match="canonical JSON"):
        package_deck_project_json(noncanonical, output_root=tmp_path / "other")
