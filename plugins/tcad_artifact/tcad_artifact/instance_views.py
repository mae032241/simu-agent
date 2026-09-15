"""Pure TCAD presentation over exact, already authorized immutable records."""

from collections.abc import Mapping

from scidiscovery.artifact_agent.approval_ui.presentation import (
    MISSING, NO_SOURCE, NO_UNCERTAINTY, add_fields, add_gap, citation,
    empty, items, parameter, pointer, source, dependency_cohort, dependency_complete, ParameterPageRows,
)


PARAMETERS = "scidiscovery.device-parameter-set.v1"
REQUIREMENTS = "scidiscovery.device-parameter-requirements.v1"
CATALOG = "scidiscovery.evidence-source-catalog.v1"
PROJECT = "tcad.deck-project.v1"
PACKAGE = "tcad.reviewed-deck-package.v2"
REVIEW = "tcad.deck-review-report.v1"
_REVIEW_FIELDS = (("verdict", "实现审查结论"), ("summary", "正式摘要"), ("rationale", "审查理由"),
    ("physical_fidelity", "物理忠实性"), ("implementation_fidelity", "实现忠实性"),
    ("numerical_protocol_fidelity", "数值协议"), ("undeclared_defaults", "未声明默认值"),
    ("findings", "审查意见"), ("missing_inputs", "缺失输入"), ("execution_ready", "记录中的执行就绪性"))
_PROJECT_FIELDS = (("solver_kind", "求解器"), ("tool_profile", "工具配置"), ("entrypoint", "执行入口"),
    ("arguments", "执行参数"), ("resource_limits", "资源与时限"), ("expected_outputs", "预期产物与案例范围"),
    ("runtime_assertions", "运行时核验"))


def _claim_rows(result, artifact, payload, cohort):
    complete = dependency_complete(artifact, cohort)
    cohort = dependency_cohort(artifact, cohort)
    catalogs = [a for a in cohort if a.get("schema_id") == CATALOG and isinstance(a.get("payload"), Mapping)]
    requirements = [a for a in cohort if a.get("schema_id") == REQUIREMENTS and isinstance(a.get("payload"), Mapping)
                    and a["payload"].get("requirement_set_key") == payload.get("requirement_set_key")]
    for i, claim in enumerate(items(payload.get("claims"))):
        if len(result["parameters"]) >= 128:
            add_gap(result, "parameter_rows_limited", artifact)
            return
        if not isinstance(claim, Mapping):
            continue
        path = pointer("claims", i)
        source_entries, reported = [], []
        unresolved = False
        for j, observation in enumerate(items(claim.get("observations"))[:64]):
            if not isinstance(observation, Mapping):
                continue
            opath = path + pointer("observations", j)
            reported.append({"value": observation.get("reported_value", MISSING), "unit": observation.get("reported_unit", MISSING),
                "conditions": observation.get("conditions", ()), "evidence_mode": observation.get("evidence_mode", MISSING),
                "source": source(artifact, opath)})
            key = observation.get("source_key")
            matches = [(catalog, k, entry) for catalog in catalogs
                       for k, entry in enumerate(items(catalog["payload"].get("sources")))
                       if isinstance(entry, Mapping) and key is not None and entry.get("source_key") == key]
            if len(matches) != 1 or not complete or any(a.get("gaps") for a in catalogs):
                unresolved = True
                add_gap(result, "source_catalog_ambiguous" if matches else "source_catalog_missing", artifact, opath, source_key=key)
                continue
            catalog, k, entry = matches[0]
            cited = citation(catalog, pointer("sources", k), entry, locator=observation.get("locator", MISSING))
            cited["locator_source"] = source(artifact, opath + "/locator") if "locator" in observation else source(artifact, opath)
            source_entries.append(cited)
        name, scope = claim.get("parameter_key", MISSING), payload.get("parameter_set_key", MISSING)
        fields = {key: source(artifact, path + pointer(field)) for key, field in (
            ("name", "parameter_key"), ("selected_value", "selected_value"), ("unit", "unit"),
            ("conditions", "conditions"), ("epistemic_status", "epistemic_status"), ("rationale", "selection_rationale")) if field in claim}
        if "parameter_set_key" in payload:
            fields["case_scope"] = source(artifact, "/parameter_set_key")
        matches = [(requirement, k, item) for requirement in requirements
                   for k, item in enumerate(items(requirement["payload"].get("parameters")))
                   if isinstance(item, Mapping) and item.get("parameter_key") == claim.get("parameter_key")]
        if len(matches) == 1 and complete and not any(a.get("gaps") for a in requirements):
            requirement, k, item = matches[0]
            if "display_name" in item:
                name = item["display_name"]
                fields["name"] = source(requirement, pointer("parameters", k, "display_name"))
            if "device_scope" in item:
                scope = item["device_scope"]
                fields["case_scope"] = source(requirement, pointer("parameters", k, "device_scope"))
        elif len(matches) > 1:
            add_gap(result, "parameter_requirements_ambiguous", artifact, path)
        uncertainty = claim.get("tuning") or NO_UNCERTAINTY
        if claim.get("tuning") is not None:
            fields["uncertainty"] = source(artifact, path + "/tuning")
        result["parameters"].append(parameter(artifact, path, name=name,
            selected_value=claim.get("selected_value", MISSING), unit=claim.get("unit", MISSING),
            conditions=claim.get("conditions", MISSING), case_scope=scope,
            epistemic_status=claim.get("epistemic_status", NO_SOURCE), uncertainty=uncertainty,
            rationale=claim.get("selection_rationale", MISSING), reported_values=reported,
            sources=source_entries, field_sources=fields, record_type="器件参数声明",
            source_status="展示暂未解析到引用（缺失、歧义或读取不完整）" if unresolved else None))


def _project_rows(result, artifact, project, base="", cohort=()):
    complete = dependency_complete(artifact, cohort)
    cohort = dependency_cohort(artifact, cohort)
    add_fields(result, artifact, "执行范围", _PROJECT_FIELDS, payload=project, path=base, kind="execution_scope")
    if project.get("result_kind") == "implementation_gap":
        add_fields(result, artifact, "实现缺口", (("summary", "正式说明"), ("missing_inputs", "缺失输入"),
            ("affected_work", "受影响任务"), ("suggested_resolution", "原记录建议")), payload=project, path=base)
    for collection, value_field, name_field in (("parameter_bindings", "declared_value", "name"),
                                               ("case_parameter_bindings", "realized_value", "scientific_path")):
        for i, binding in enumerate(items(project.get(collection))):
            if not isinstance(binding, Mapping) or len(result["parameters"]) >= 128:
                continue
            path = base + pointer(collection, i)
            refs = []
            if binding.get("evidence_source"):
                refs.append({"title": binding["evidence_source"], "locator": binding.get("evidence_locator", MISSING),
                    "url": None, "accessed_at": None, "source": source(artifact, path)})
            source_status = None
            key = binding.get("approved_parameter_key")
            if key:
                sets = [a for a in cohort if a.get("schema_id") == PARAMETERS and isinstance(a.get("payload"), Mapping)]
                matches = [(a, k, c) for a in sets for k, c in enumerate(items(a["payload"].get("claims")))
                           if isinstance(c, Mapping) and c.get("parameter_key") == key]
                if len(matches) == 1 and complete and not any(a.get("gaps") for a in sets):
                    a, k, claim = matches[0]
                    refs.append({"title": "绑定的器件参数：" + str(key), "locator": pointer("claims", k),
                        "source": source(a, pointer("claims", k)), "acquisition": "绑定参数记录"})
                else:
                    source_status = "展示暂未解析到绑定参数（缺失、歧义或读取不完整）"
                    add_gap(result, "bound_parameter_unresolved", artifact, path, parameter_key=key)
            status = binding.get("evidence_class") or NO_SOURCE
            uncertainty = NO_UNCERTAINTY
            if status in {"tool_default", "solver_default", "default"}:
                uncertainty = "工具默认值；适用性未证实；未提供估计"
                if not refs:
                    add_gap(result, "default_source_missing", artifact, path)
            result["parameters"].append(parameter(artifact, path, name=binding.get(name_field, MISSING),
                selected_value=binding.get(value_field, MISSING), unit=binding.get("unit", MISSING),
                conditions={key: binding[key] for key in ("relative_path", "locator", "materialization_kind", "source_line_start", "source_line_end", "derivation") if key in binding},
                case_scope={key: binding[key] for key in ("experiment_key", "case_key", "approved_parameter_key") if key in binding} or "本实现记录；案例范围未记录",
                epistemic_status=status, uncertainty=uncertainty, rationale=binding.get("rationale") or binding.get("derivation") or MISSING,
                sources=refs, record_type="实现参数绑定", source_status=source_status, field_sources={key: source(artifact, path + pointer(field)) for key, field in (
                    ("name", name_field), ("selected_value", value_field), ("unit", "unit"),
                    ("epistemic_status", "evidence_class"), ("rationale", "rationale")) if field in binding}))


def build_presentation(artifacts, *, parameter_target=None, parameter_after=0, parameter_limit=8):
    result = empty()
    if parameter_target is not None:
        result["parameters"] = ParameterPageRows(parameter_after, parameter_limit)
    for artifact in artifacts:
        if parameter_target is not None and artifact["artifact_id"] != parameter_target:
            continue
        payload, schema = artifact.get("payload"), artifact.get("schema_id")
        if not isinstance(payload, Mapping):
            continue
        if schema == PARAMETERS:
            add_fields(result, artifact, "器件参数依据", (("title", "参数集"), ("objective", "目标")))
            _claim_rows(result, artifact, payload, artifacts)
        elif schema == REQUIREMENTS:
            add_fields(result, artifact, "参数要求", (("title", "要求集"), ("objective", "目标"), ("parameters", "参数与适用条件")))
        elif schema == CATALOG:
            add_fields(result, artifact, "来源目录", (("catalog_key", "目录标识"),))
        elif schema == PROJECT:
            _project_rows(result, artifact, payload, cohort=artifacts)
        elif schema == PACKAGE:
            project = payload.get("project")
            review = payload.get("review")
            if isinstance(project, Mapping):
                _project_rows(result, artifact, project, "/project", cohort=artifacts)
            if isinstance(review, Mapping):
                add_fields(result, artifact, "匹配实现审查", _REVIEW_FIELDS, payload=review, path="/review")
            add_fields(result, artifact, "冻结执行输入", (("resolved_inputs", "精确解析输入"),), kind="execution_scope")
        elif schema == REVIEW:
            add_fields(result, artifact, "实现独立审查", _REVIEW_FIELDS)
        elif schema in {"scidiscovery.device-parameter-coverage.v1", "scidiscovery.parameter-uncertainty.v1"}:
            add_fields(result, artifact, "参数覆盖与不确定性记录", (("status", "记录状态"), ("items", "逐参数依据")))
    return result


DISPLAY_POINTERS = {
    PARAMETERS: ("/parameter_set_key", "/requirement_set_key", "/title", "/objective", "/claims"),
    REQUIREMENTS: ("/requirement_set_key", "/title", "/objective", "/parameters"),
    CATALOG: ("/catalog_key", "/sources"),
    PROJECT: tuple(pointer(key) for key, _ in _PROJECT_FIELDS) + ("/parameter_bindings", "/case_parameter_bindings", "/result_kind", "/summary", "/missing_inputs", "/affected_work", "/suggested_resolution"),
    REVIEW: tuple(pointer(key) for key, _ in _REVIEW_FIELDS),
    "scidiscovery.device-parameter-coverage.v1": ("/status", "/items"),
    "scidiscovery.parameter-uncertainty.v1": ("/status", "/items"),
}
DISPLAY_POINTERS[PACKAGE] = tuple("/project" + p for p in DISPLAY_POINTERS[PROJECT]) + tuple("/review" + p for p in DISPLAY_POINTERS[REVIEW]) + ("/resolved_inputs",)
build_presentation.display_pointers = DISPLAY_POINTERS

build_presentation.parameter_schemas = (PARAMETERS, PROJECT, PACKAGE)

build_presentation.parameter_dependencies = (CATALOG, REQUIREMENTS, PARAMETERS)
