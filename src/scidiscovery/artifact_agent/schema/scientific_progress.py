"""Scientific caller fields; identities and provenance are supplied by control."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class ScientificIntent(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, str_strip_whitespace=True)
    intent: Literal['change_mechanism', 'gather_evidence', 'refine', 'validate', 'diagnose']
    target: str = Field(min_length=1, max_length=512, description='Scientific question or contradiction this task addresses.')
    expected: str = Field(min_length=1, max_length=1024, description='Observation that would change the current judgment; not a promised outcome.')


class ProgressAssessment(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, str_strip_whitespace=True)
    task_name: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}$', description='Exact terminal task name associated with the current goal. Running tasks use the report summary to describe waiting.')
    outcome: Literal['advance', 'no_progress', 'unknown']
    reason: str = Field(min_length=1, max_length=1024, description='What the sealed result changes about the goal; negative results may advance it.')
    evidence_names: list[Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}$")]] = Field(default_factory=list, max_length=8,
        description='Exact visible scientific artifact names, including the sealed task output. Missing output support projects as unknown, never success.')
    limitations: str = Field(default='', max_length=1024)
