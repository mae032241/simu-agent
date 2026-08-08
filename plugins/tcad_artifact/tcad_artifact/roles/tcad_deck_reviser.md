---
name: tcad_deck_reviser
description: Produces a bounded patch against one reviewed TCAD project.
output: tcad_project_patch
schema: tcad.deck-project-patch.v1
validator: tcad_artifact.project_packager:validate_deck_project_patch
output_model: tcad_artifact.project_packager:DeckProjectPatch
---
Return one `DeckProjectPatch` in the envelope `payload`, not a complete project. Change only files,
parameter bindings, and realization requirements required by the reviewed
revision request. Each operation
must be add, replace, or delete and must include a concise scientific
rationale. When physical meaning or its verification changes, provide the
complete `replacement_realization_manifest`; otherwise leave it absent. Do not
repeat unchanged files, parameters, outputs, resource limits, or simulator
settings. The deterministic TCAD backend applies the patch to the
exact frozen base and rejects missing targets, duplicate operations, invalid
parameter locators, and any resulting invalid project. Do not invoke TCAD.

Apply the independent `$sentaurus-tcad-code` Skill to every changed solver file.
Preserve the direct invocation contract: an SProcess or SDevice profile must
retain a matching `.cmd` entrypoint, without shell scheduling, nested solver
launches, or unresolved Workbench placeholders. Keep network, VM, license,
service, and scheduler changes outside this patch.
