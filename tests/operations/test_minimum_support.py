"""Fixed role decisions measured through real open, startup and copied readers.

Frozen before any candidate change (baseline HEAD 0620774):

* initial_h  -- propose the initial mechanism portfolio from the original task.
  Needs the verbatim task, the role contract and the boundary-declaration rules
  (H separates prohibitions/conditions with boundary_declarations).
* h_revision -- revise the previous portfolio against the frame and foundation.
  Needs the complete frame, foundation, previous portfolio and the boundary
  rules (derived boundaries are revised with boundary_declarations.revises).
* w_portfolio -- choose the next discriminating experiment within current H
  after A feedback.  Needs the complete H portfolio, original goal, A analysis
  and prior W report.
* a_results -- judge W's contribution and route the next action.  Needs the W
  report, H portfolio, goal, adopted stage receipt, every captured attempt file
  (including the uncited failure), the derived ledger records and the capture
  inventory coverage.

Each role reads its core plus the frozen sections required by its stated decision,
including boundary-declaration rules. Complete detailed contracts stay readable;
none/all sensitivity is measured separately.

Every required exact object is read once (dedup by exact private ArtifactRef on
both sides, the conservative denominator).  A read is skipped only when the
default view already delivered that object's decision content and the test
verifies it field by field against the original.  Navigation that a Worker
cannot avoid (grouped input metadata only addressable by pointer) is counted.
"""
import re

import pytest


# On-demand role_reference sections each decision reads beyond the core checklist.
# Frozen from the decision statements above (written in 78aedd3, before the
# compacted contract existed) by responsibility, conservatively: every
# responsibility the decision exercises, and always closeout/boundary/proxy
# sections when the decision touches them (the task text names a validation
# proxy that misses the target, so every case touches proxy and boundaries).
# SCID_M12_SECTIONS=none|all give the lower/upper sensitivity bounds; savings
# below the 'all' bound depend on on-demand reading.


def _tagged(core):
    return {name.strip() for tags in re.findall(r'\[([a-z0-9_, ]+)\]', core) for name in tags.split(',')}


@pytest.mark.parametrize('operation', ['science.hypothesis.propose.v1', 'science.experiment.v1',
    'science.result.analyze.v1'])
def test_compact_core_names_every_reference_section_and_loses_no_contract_text(operation):
    from scidiscovery.artifact_agent.schema.role_result import split_reference, with_reference, BOUNDARY_GUIDANCE
    from scidiscovery.operations.tooling import operation_role_instructions
    from tests.operations.test_root_scheduler_ownership import structured_catalog
    full = operation_role_instructions(structured_catalog().operation(operation))
    core, sections = split_reference(full)
    assert sections and 2000 <= len(core.encode()) <= 4600
    # Every on-demand section is named by a checklist item: no responsibility is unreachable.
    assert set(sections) <= _tagged(core)
    assert split_reference(with_reference(core, sections)) == (core, sections)
    assert sections['boundary_declarations'] == BOUNDARY_GUIDANCE.strip()
    # Core keeps at most a few boundary sentences; the full boundary text is on demand once.
    assert BOUNDARY_GUIDANCE.strip()[:200] not in core


def test_removed_role_sentences_are_only_code_enforced_rules():
    """Old role text = reference sections + the listed removals (each enforced in code)."""
    from scidiscovery import general_science_resources as h, general_science_experiment_task as w
    from scidiscovery import general_science_result_analysis as a
    from scidiscovery.artifact_agent.schema.role_result import split_reference
    flat = lambda text: ' '.join(text.split())
    for module, full, removed in (
            (h, h.IDEATOR_PROMPT, ('never invent one or manufacture a qualified foundation', 'reviews are not inherited')),
            (w, w.PROMPT, ('never author hashes or internal bindings',)),
            (a, a.PROMPT, ('Do not invent experiment/plan/objective keys', 'do not author their duplicate handoff fields'))):
        core, sections = split_reference(full)
        joined = flat(' '.join(sections.values()))
        for sentence in removed:
            assert sentence not in joined and sentence not in flat(core)
