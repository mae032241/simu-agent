"""Deterministic, execution-free TCAD Artifact transformations."""

from __future__ import annotations

from difflib import unified_diff
from hashlib import sha256
from typing import Mapping

from scidiscovery.artifact_agent.schema.common import canonical_json, canonical_sha256
from scidiscovery.artifact_agent.transforms import TransformOutput

from .project_packager import (
    DeckProjectDraft,
    DeckProjectPatch,
    DeckReviewReport,
    ReviewedDeckPackage,
    TCADRuntimeManifest,
    apply_deck_project_patch,
    attest_runtime_contract,
    deck_project_diff,
    validate_deck_review_against_project,
)


DECK_PATCH_PROFILE = "tcad.deck-project-apply-patch.v1"
DECK_COMPARE_PROFILE = "tcad.deck-project-compare.v1"
DECK_REVIEW_VALIDATION_PROFILE = "tcad.deck-review-validate.v1"
REVIEWED_DECK_PACKAGE_PROFILE = "tcad.reviewed-deck-package.v1"
RUNTIME_ATTESTATION_PROFILE = "tcad.runtime-attestation.v1"


class TCADProjectTransformAdapter:
    @staticmethod
    def supports_transform_profile(profile: str) -> bool:
        return profile in {
            DECK_PATCH_PROFILE,
            DECK_COMPARE_PROFILE,
            DECK_REVIEW_VALIDATION_PROFILE,
            REVIEWED_DECK_PACKAGE_PROFILE,
            RUNTIME_ATTESTATION_PROFILE,
        }

    @staticmethod
    def required_input_parentage(profile: str) -> tuple[tuple[str, str], ...]:
        if profile == REVIEWED_DECK_PACKAGE_PROFILE:
            return (("review", "project"),)
        if profile == RUNTIME_ATTESTATION_PROFILE:
            return (("runtime_manifest", "reviewed_package"),)
        return ()

    def transform(
        self, *, profile: str, inputs: Mapping[str, bytes]
    ) -> tuple[TransformOutput, ...]:
        if profile == DECK_REVIEW_VALIDATION_PROFILE:
            return self._validate_review(inputs)
        if profile == DECK_COMPARE_PROFILE:
            return self._compare_projects(inputs)
        if profile == REVIEWED_DECK_PACKAGE_PROFILE:
            return self._package_reviewed_project(inputs)
        if profile == RUNTIME_ATTESTATION_PROFILE:
            return self._attest_runtime(inputs)
        if profile != DECK_PATCH_PROFILE:
            raise ValueError("unsupported TCAD project transform profile")
        return self._apply_patch(inputs)

    @staticmethod
    def _compare_projects(inputs: Mapping[str, bytes]) -> tuple[TransformOutput, ...]:
        if set(inputs) != {"base_project", "revised_project"}:
            raise ValueError(
                "TCAD deck comparison requires base_project and revised_project inputs"
            )
        base = DeckProjectDraft.model_validate_json(inputs["base_project"], strict=True)
        revised = DeckProjectDraft.model_validate_json(
            inputs["revised_project"], strict=True
        )
        difference = {
            "schema_version": 1,
            "base_project_sha256": canonical_sha256(base.model_dump(mode="json")),
            "revised_project_sha256": canonical_sha256(
                revised.model_dump(mode="json")
            ),
            **deck_project_diff(base, revised),
            "file_deltas": _file_deltas(base, revised),
        }
        return (
            TransformOutput(
                label="primary",
                content=canonical_json(difference),
                kind="tcad_project_diff",
                schema="tcad.deck-project-diff.v1",
                payload_schema_version=1,
                media_type="application/json",
            ),
        )

    @staticmethod
    def _apply_patch(inputs: Mapping[str, bytes]) -> tuple[TransformOutput, ...]:
        if set(inputs) != {"base_project", "project_patch"}:
            raise ValueError(
                "TCAD deck patch requires base_project and project_patch inputs"
            )
        base = DeckProjectDraft.model_validate_json(inputs["base_project"], strict=True)
        patch = DeckProjectPatch.model_validate_json(inputs["project_patch"], strict=True)
        revised = apply_deck_project_patch(base, patch)
        difference = {"schema_version": 1, **deck_project_diff(base, revised)}
        return (
            TransformOutput(
                label="primary",
                content=canonical_json(revised.model_dump(mode="json")),
                kind="tcad_project",
                schema="tcad.deck-project.v1",
                payload_schema_version=1,
                media_type="application/json",
            ),
            TransformOutput(
                label="diff",
                content=canonical_json(difference),
                kind="tcad_project_diff",
                schema="tcad.deck-project-diff.v1",
                payload_schema_version=1,
                media_type="application/json",
            ),
        )

    @staticmethod
    def _validate_review(inputs: Mapping[str, bytes]) -> tuple[TransformOutput, ...]:
        if set(inputs) != {"project", "review"}:
            raise ValueError("TCAD deck review validation requires project and review")
        project = DeckProjectDraft.model_validate_json(inputs["project"], strict=True)
        review = DeckReviewReport.model_validate_json(inputs["review"], strict=True)
        validate_deck_review_against_project(project, review)
        result = {
            "schema_version": 1,
            "valid": True,
            "verdict": review.verdict,
            "execution_ready": review.execution_ready,
            "requirements_declared": len(project.realization_manifest),
            "requirements_reviewed": len(review.requirement_reviews),
        }
        return (
            TransformOutput(
                label="primary",
                content=canonical_json(result),
                kind="tcad_deck_review_attestation",
                schema="tcad.deck-review-attestation.v1",
                payload_schema_version=1,
                media_type="application/json",
            ),
        )

    @staticmethod
    def _package_reviewed_project(
        inputs: Mapping[str, bytes],
    ) -> tuple[TransformOutput, ...]:
        if set(inputs) != {"project", "review"}:
            raise ValueError("reviewed deck package requires project and review")
        package = ReviewedDeckPackage(
            project=DeckProjectDraft.model_validate_json(
                inputs["project"], strict=True
            ),
            review=DeckReviewReport.model_validate_json(inputs["review"], strict=True),
        )
        return (
            TransformOutput(
                label="primary",
                content=canonical_json(package.model_dump(mode="json")),
                kind="packaged_project",
                schema="tcad.reviewed-deck-package.v1",
                payload_schema_version=1,
                media_type="application/json",
            ),
        )

    @staticmethod
    def _attest_runtime(inputs: Mapping[str, bytes]) -> tuple[TransformOutput, ...]:
        if set(inputs) != {"reviewed_package", "runtime_manifest"}:
            raise ValueError(
                "runtime attestation requires reviewed_package and runtime_manifest"
            )
        report = attest_runtime_contract(
            ReviewedDeckPackage.model_validate_json(
                inputs["reviewed_package"], strict=True
            ),
            TCADRuntimeManifest.model_validate_json(
                inputs["runtime_manifest"], strict=True
            ),
        )
        return (
            TransformOutput(
                label="primary",
                content=canonical_json(report.model_dump(mode="json")),
                kind="runtime_attestation",
                schema="tcad.runtime-attestation.v1",
                payload_schema_version=1,
                media_type="application/json",
            ),
        )


__all__ = [
    "DECK_PATCH_PROFILE",
    "DECK_COMPARE_PROFILE",
    "DECK_REVIEW_VALIDATION_PROFILE",
    "REVIEWED_DECK_PACKAGE_PROFILE",
    "RUNTIME_ATTESTATION_PROFILE",
    "TCADProjectTransformAdapter",
]


def _file_deltas(
    base: DeckProjectDraft, revised: DeckProjectDraft
) -> tuple[dict[str, object], ...]:
    base_files = {item.relative_path: item.content for item in base.files}
    revised_files = {item.relative_path: item.content for item in revised.files}
    deltas: list[dict[str, object]] = []
    for path in sorted(set(base_files) | set(revised_files)):
        before = base_files.get(path)
        after = revised_files.get(path)
        if before == after:
            continue
        rendered = "".join(
            unified_diff(
                [] if before is None else before.splitlines(keepends=True),
                [] if after is None else after.splitlines(keepends=True),
                fromfile=f"base/{path}",
                tofile=f"revised/{path}",
                n=3,
            )
        )
        deltas.append(
            {
                "relative_path": path,
                "base_sha256": None
                if before is None
                else sha256(before.encode("utf-8")).hexdigest(),
                "revised_sha256": None
                if after is None
                else sha256(after.encode("utf-8")).hexdigest(),
                "unified_diff": rendered,
            }
        )
    return tuple(deltas)
