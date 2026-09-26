"""Domain-neutral experiment Operation declarations."""

from __future__ import annotations

from .general_science_agent_operations import (
    _EVIDENCE_APPROVAL_PROVIDER,
    _FOUNDATION_ADMISSION,
    _agent,
    _input as _agent_input,
    _output as _agent_output,
)
from .general_science_control_operations import (
    _input as _transform_input,
    _output as _transform_output,
    _transform,
)
from .operations.spec import ComponentRef, InputAdmissionSpec, InputValidationSpec, ReviewSpec


AGENT_OPERATIONS = ()


TRANSFORM_OPERATIONS = (
    _transform(
        "science.objective.project.v1",
        "Project the exact research objective declared by a foundation.",
        "A qualified foundation declares an explicit objective contract.",
        "Inferring a new objective or changing scientific content.",
        component="objective_project",
        inputs=(
            _transform_input(
                "scientific_foundation",
                "Qualified foundation containing the objective contract.",
                "scidiscovery.scientific-foundation.v1",
                usage="prior_signal",
                required_non_null_fields=("objective_contract",),
            ),
        ),
        outputs=(
            _transform_output(
                "research_objective",
                "Exact research objective contract.",
                "research_objective",
                "scidiscovery.research-objective.v1",
                "objective_validator",
            ),
        ),
        input_admission=_FOUNDATION_ADMISSION,
    ),
)



__all__ = ["AGENT_OPERATIONS", "OPERATIONS", "TRANSFORM_OPERATIONS"]


# A new design, including intentional revisions, uses normal foundation admission.
# It has one primary output and intentionally no mandatory review edge.

OPERATIONS = AGENT_OPERATIONS + TRANSFORM_OPERATIONS
