"""Explicit scientific views of registered figure file formats, with private patches."""
import hashlib
import json
from scidiscovery.artifact_agent.schema.common import canonical_json

SOURCE_CONTROL = ("source_sha256", "recovered_image_sha256", "page_image_index", "pdf_object_id", "pdf_object_generation", "recovery_tool", "recovery_tool_version")


def project_figure_file(name, raw):
    if not name.endswith(".json"):
        return raw, {}
    value = json.loads(raw)
    patches = []
    def remove(path, keys):
        target = value
        for part in path:
            target = target[part]
        for key in keys:
            if key in target:
                patches.append([list(path)+[key], target.pop(key)])
    if name == "selected_family/selection.json":
        public = {"materials": [{"name": item["data_item"], "media_type": item["media_type"]} for item in value["members"]]}
        return canonical_json(public), {"selection": value}
    if name == "figure_request/request.json":
        remove(("source",), SOURCE_CONTROL)
    elif name == "figure_manifest/evidence.json":
        remove(("source",), ("image_sha256", "pdf_sha256", "pdf_object"))
        remove(("provenance",), ("spec_sha256",))
        for i in range(len(value["provenance"]["output_artifacts"])):
            remove(("provenance","output_artifacts",i), ("sha256",))
    elif name == "validation_reports/validation_report.json":
        remove((), ("manifest_sha256", "bundle_fingerprint_sha256"))
        for key in ("series", "supporting_tables"):
            for i in range(len(value.get(key, ()))):
                remove((key,i), ("csv_sha256",))
    return canonical_json(value), {"patches": patches, "original_sha256": hashlib.sha256(raw).hexdigest()}


def restore_figure_file(raw, metadata):
    control = metadata.get("figure_control")
    if control is None:
        raise ValueError("figure scientific file has no sealed original")
    if "selection" in control:
        expected, _ = project_figure_file("selected_family/selection.json", canonical_json(control["selection"]))
        if expected != raw:
            raise ValueError("figure selection differs from sealed material")
        return canonical_json(control["selection"])
    if not control:
        return raw
    value = json.loads(raw)
    for path, content in control["patches"]:
        target = value
        for part in path[:-1]:
            target = target[part]
        if path[-1] in target:
            raise ValueError("private figure field supplied in scientific material")
        target[path[-1]] = content
    original = canonical_json(value)
    if hashlib.sha256(original).hexdigest() != control["original_sha256"]:
        raise ValueError("figure original differs from its immutable proof")
    return original
