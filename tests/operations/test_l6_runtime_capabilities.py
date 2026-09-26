from __future__ import annotations

from pathlib import Path

from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from curve_score.science_operations import Components
from tests.operations import test_m2_curve_analysis_boundary as curve
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as SCIENCE_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
