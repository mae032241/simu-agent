# Independent review: user-text ingestion and historical continuation

Verdict: **REVISE**. Review date: 2026-09-14.

The proposed immutable text Artifact plus explicitly bound optional input is a good minimal direction. It can satisfy the user's goal without a new scientific extraction stage, context entity, scheduler workflow, or control-owned interpretation. The proposal is not yet safe to implement as written: blanket input/reference changes have concrete effects on unchanged calls and downstream evidence cohorts. Preserve the Agent/control responsibility split as the deciding constraint.

Review subject is exactly the five-point proposal supplied by the parent, including its acceptance criteria. Reviewed repository: `/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2`; HEAD `096a13fd89aacf2d4e73f77e87ab3174e5f89ec3`, with existing uncommitted handoff work. Read-only source review; no tests, solver, installation, control-plane calls, production databases, or Worker directories were used. Only this report was written. File references below are relative to that repository and refer to the inspected working tree.

## Must fix before implementation

### 1. Preserve existing source-reference acceptance when the optional note is absent

**High impact; proposal points 2 and 4.** Adding an unbound `current_progress` inventory port can change the output schema of an unchanged call.

`operation_contract.py:567-577` activates `evidence-source-enum.v2` whenever the declaration contains any visible `evidence_inventory` input. It does not require that input to be bound. The enum then includes only bound aliases permitted by `context_sources` (`operation_contract.py:545-550`).

A reachable counterexample is `science.hypothesis.propose.v1`: its existing inputs are `prior_signal` and default `claim_evidence`, with no inventory port (`general_science_agent_operations.py:450-464`; defaults at 45-56). Its output has `/evidence` source paths (124-129). The contextual validator explicitly permits source keys owned by the qualified foundation, including its item evidence keys (`general_science_components.py:133-138`). Adding optional inventory context activates a narrower JSON Schema enum and rejects a previously valid foundation-key citation before that validator can accept it. No user note is needed to trigger this regression.

**Minimum amendment:** state that the projection must preserve every existing purpose-specific source domain, including foundation-owned keys, and that an absent optional input must not narrow accepted outputs. Do not solve this by asking Workers to rewrite their citation tables or add copies of the foundation's original sources. Include a no-note hypothesis submission with a foundation-owned source key as a directed regression case.

### 2. Separate supplementary provenance from the exact source/review cohort

**High impact; proposal points 2, 4 and 5.** Reusing `evidence_inventory` and adding context sources is not merely a readability change.

Three existing consumers demonstrate the issue:

- `mcp_root_operation_routes.py:598-606` puts every Run input whose usage is `claim_evidence`, `evidence_inventory`, or `cached_excerpt` into `ProducerOutputFamily.evidence_sources`. Thus an inventory note is automatically a frozen scientific-family source, regardless of the author's intent or whether the note was cited.
- `parameter_operations.py:402-407` treats all contextual aliases except `required_parameter_checklist` as parameter source aliases. Blanket `context_sources` expansion makes a background note eligible as a `source_catalog` entry. Downstream qualification derives its frozen source set from the extraction family (561-577) and requires exact ordered audit parents (628-639). A note added only to the parameter audit is an extra parent and causes qualification rejection after a successful audit. A note added during extraction may instead be absorbed into the frozen source cohort and become mandatory downstream. Neither is a neutral background-input addition.
- `general_science_components.py:108-113` computes the exact sources for evidence revision as every audit parent except the prior intake. All Run inputs become output parents (`service/runs.py:1237`). A background note supplied to an intake audit therefore becomes a required `source_material` member in a later bounded evidence revision.

This is not an argument against citing a user's statement. A Worker must be able to cite the note as the note; whether it supports a scientific claim remains a scientific judgment. Readability, citation availability, original evidence-family membership, and independent-review authority must not be collapsed by a shared helper.

**Minimum amendment:** enumerate and adjust these existing purpose-specific consumers using declared ports and exact existing bindings. Keep complete provenance, but do not infer the exact evidence cohort from all parents or all contextual aliases. Preserve exact original source, review and approval checks. Notes intentionally supplied as formal source material use the appropriate existing source port; background notes must not silently enter that set. No new truth classifier or second source registry is needed. Blanket additions cannot be approved until these paths compose through the next admission/qualification step.

### 3. Define a bounded capacity rule that retains the selected historical context

**Medium impact; proposal points 1–3.** The plan says to preserve existing declarations and carry old records plus the note, but the ports are already bounded at four items: experiment feedback (`general_science_experiment_operations.py:35-45`), TCAD author/review (`plugin.py:448-454`), and TCAD analysis (`result_analysis.py:575`). Generic analysis also has four, with a different per-item byte limit (`curve_score/science_operations.py:266-271`). A legal four-record context cannot accept a fifth note unchanged.

The total bound bytes still count on-demand inputs, and a repeated Artifact across ports is rejected (`operations/invoke.py:171-202`). Moving a duplicate into another port or declaring an on-demand note does not create capacity. For example, hypothesis proposal currently has only a 2 MiB aggregate input budget (`general_science_agent_operations.py:465-467`).

**Minimum amendment:** choose an explicit UTF-8 byte bound for text intake and compatible port/aggregate capacities. Define how the selected node's necessary exact records plus the note fit; use a small justified capacity adjustment where needed. Do not silently evict an original objective/review or truncate, summarize, merge, or normalize the note to fit. If still outside the supported bound, report the located limit rather than presenting the continuation as complete. Cover multibyte text, whitespace/newline preservation, and a saturated four-record context.

### 4. Make recovery and deployment compatibility explicit

**Medium impact; acceptance criteria.** “Restart recovery” must distinguish two existing operations on saved work.

`resume_from` requires the same compiled Operation digest and the exact ordered input references (`service/runs.py:1597-1602`). Adding a note changes those inputs; changing compiled port/reference declarations changes the digest even for a no-note call. Existing queued/running Runs also require their original compiled version and digest (`runs.py:1350-1354`). They cannot transparently continue under a replacement contract.

`draft_from` already supports a failed Run of the same Operation with new inputs/contract, subject to same-instance/backend identity, saved-draft verification and attempt budgets (`runs.py:1436-1455`). Its assignment explicitly treats the draft as starting material, not evidence, and requires checking the new bindings (`run_assignment.py:79-90`). Old drafts lacking persisted recovery policy may still require the former compiled contract to verify (`runs.py:1466-1468`); do not promise all historical drafts are recoverable.

**Minimum amendment:** use ordinary new Runs for completed historical nodes, and `draft_from` when incorporating a new note into preserved failed work. Retain unchanged strict `resume_from` semantics. Preserve/drain active assignments before changing their catalog and explicitly test the supported restart path. Do not inherit review decisions or extend attempts automatically.

Do not overstate the update risk: sealed same-version scientific outputs are not automatically retired by a digest change. `_operation_output_contract` intentionally permits compatible same-version drift while retaining output-kind/schema/media and review-edge checks (`mcp_root_operation_routes.py:1601-1629`). Approval contract identity is derived from `review.approval` (`operations/catalog.py:732-737`). Preserve that behavior; avoid an unnecessary blanket version bump or new historical requalification workflow.

### 5. Specify the Worker-visible origin and reading path

**Medium impact; proposal points 1 and 4.** Storing an origin label is necessary but does not by itself show that origin to a fresh Worker. `run_assignment.py:44-63` projects aliases, paths, descriptions, media, usage, exposure and historical status, but no Artifact labels. Analysis start files index those inputs (`curve_score/analysis_workspace.py:177-189`); raw text fails the optional JSON excerpt attempt and remains only linked (193-200).

**Minimum amendment:** state how the exact note alias/path and mechanically recorded user-via-scheduler origin appear in the existing assignment/instructions and compact analysis entry. A link to the complete raw text is sufficient; a new summary/extraction artifact is unnecessary. Keep the raw payload unchanged, and distinguish the user's statement from qualified scientific evidence. Verify both normal and native-analysis reading paths, and a fresh or reused Agent reopening a new assignment.

## Scope and goal fit

Independent source enumeration confirms **25 public Agent Operations: 9 with `current_progress`, 16 without**. The nine are three generic experiment Operations, generic result diagnosis, four TCAD author/review Operations, and TCAD analysis. The 16 remaining are eight generic evidence/hypothesis Operations, three curve Operations, two TCAD parameter Operations, and three figure Operations. Some use direct `OperationSpec` constructors rather than the common `scientific_agent_operation` helper (`tcad_artifact/parameter_operations.py:927-950`; `tcad_artifact/plugin.py:363` and 595), so one helper edit does not establish full coverage.

The selected-node behavior should be described as **starting a new, explicitly bound continuation from an exact historical node**, not rewinding current heads or mutating the old node. Existing `artifact_catalog` exposes ordered parent names and schemas (`mcp_root_instance_routes.py:247-284`). Normal experiment design can consume an old plan plus note, but still requires the exact objective, portfolio and critic cohort (`general_science_experiment_operations.py:64-102`), and an admissible critic disposition (`general_science_experiment_components.py:169-183`). The resulting intent uses the existing materialization and review path. The plan correctly rejects manufacturing a negative review or treating a note as `change_request`/approval. Arbitrary invariant-changing edits remain outside this convenience feature.

The proposed Root text ingress can reuse the immutable storage and semantic-name fingerprint flow (`intake.py:68-85`; `mcp_root_instance_routes.py:215-245`). Registration and invocation can remain separate tools. No new scientific preprocessing or framework layer is warranted. A dedicated note port or phased coverage would be optional implementation choices, not required architectural changes; the properties above are required whichever spelling is chosen.

## Focused implementation acceptance

Use a small directed set, plus one installed-entry check; no full suite is required by this review:

1. Exact Unicode/multiline/whitespace text survives registration, restart, materialization and a subsequent Run unchanged. Same request is idempotent; changed text creates a new revision while the old binding remains readable.
2. Existing no-note hypothesis submission with foundation-owned citation still succeeds; a note citation succeeds through the same compiled schema and submission path. Unknown aliases remain rejected.
3. An audit with a background note completes and its proper next admission/qualification succeeds without converting that note into an original evidence source. Missing or substituted original source/review still fails.
4. A selected historical node plus all necessary context and a new note fits the declared capacity. Failed work plus new note uses `draft_from`; unchanged `resume_from` succeeds and changed-input `resume_from` rejects as before. Compatible sealed historical output remains usable.
5. Fresh/reused assignment and native analysis entry expose the note's full-file path and origin. The next task binds that exact original note rather than relying on memory or a copied summary.
6. The installed Root schema advertises the text tool, the compiled catalog/assignment includes intended optional inputs, and generated Root enabled-tools configuration exposes the tool (`platforms/codex.py:38`, 270, 678). Review/approval/execution authority remains unchanged.

Existing all-input integrity reads during submission (`runs.py:1065-1086`) are not introduced by this proposal and are not a reason to add another validation pass or rewrite this subsystem. This review identifies plan amendments, not verified implementation failures or a claim that no future regression is possible.
