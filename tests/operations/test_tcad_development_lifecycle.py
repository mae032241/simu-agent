"""Development attempts must remain repairable without a scientific handoff."""

import pytest


@pytest.mark.parametrize("field,value", [("capture", "workspace_file"), ("max_bytes", 1024)])
def test_raw_output_declarations_reject_control_generated_fields(field, value):
    from pydantic import ValidationError
    from tcad_artifact.project_materializer import DeclaredRawOutput
    with pytest.raises(ValidationError, match="extra_forbidden"):
        DeclaredRawOutput.model_validate({
            "name": "profile", "relative_path": "profile.tdr",
            "media_type": "application/octet-stream", field: value,
        })
