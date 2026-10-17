"""User background remains readable without becoming a formal evidence source."""
from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import pytest

from scidiscovery.artifact_agent.schema.approval import LocalIdentityRef
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from tests.operations.test_hypothesis_objective_boundary import _proposal
from tests.operations.test_hypothesis_review_routing import _critic


def test_user_context_is_declared_only_on_public_agents():
    from curve_score.plugin import PLUGIN as CURVE
    from curve_figure_evidence.plugin import PLUGIN as FIGURE
    from tcad_artifact.plugin import PLUGIN as TCAD
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE, FIGURE, TCAD))
    for name in catalog.operation_ids():
        spec = catalog.operation(name).spec
        ports = [port for port in spec.inputs if port.name == "user_context"]
        if spec.executor.kind != "agent" or spec.catalog_scope != "public":
            assert ports == []
            continue
        assert len(ports) == 1
        port = ports[0]
        assert (port.min_items, port.max_items, port.max_item_bytes) == (0, 4, 32768)
        assert (port.usage, port.exposure, port.schema_id) == ("prior_signal", "on_demand", "opaque")
        assert port.codec.plugin_id == port.schema_resource.plugin_id == "general_science"
        assert port.codec.component_id == "opaque_codec"
        for output in spec.outputs:
            assert ("user_context" in output.context_sources) == (output.context_validator is not None)
