"""Exact producer-family and input-origin resolution shared by admission and freeze."""
from __future__ import annotations

from typing import Any
from ..schema.refs import ArtifactRef
from ..schema.common import canonical_sha256, ContractDiagnostic
from ...operations.invoke import (
    InvocationArtifact, OperationInvocationError, ProducerOutputFamily,
    ProducerFamilyMember, ProducerInputProjection, ProducerEvidenceSource,
)
from ...operations.spec import input_source_requirement


class OperationOrigins:
    def __init__(self, *, artifacts, bindings, runs, catalog, instance_id):
        self.artifacts = artifacts
        self.bindings = bindings
        self.runs = runs
        self._operation_catalog = catalog
        self.instance_id = instance_id

    def _instance_id(self):
        return self.instance_id

    def review_author_runs(self, artifact_name, ref):
        """Resolve authors only through verified producers and declared projections.

        Arbitrary parents, copied labels and nearby same-schema objects confer no
        authorship. The configured source bound also limits this traversal.
        """
        limit = self.runs.agent_settings.progression.related_source_limit
        visited, active, cache = set(), set(), {}

        def resolve(name, current):
            if current in active or (current not in visited and len(visited) >= limit):
                raise OperationInvocationError("review_authorship_unavailable",
                    message="The exact subject's authorship cannot be resolved within the configured source bound.")
            if current in cache:
                return cache[current]
            visited.add(current)
            active.add(current)
            envelope = self.artifacts.verify(current)
            tool_run = envelope.labels.get("tool_producer_run")
            if tool_run:
                owner = self.runs.status(tool_run)
                records = [r for r in self.runs.tool_evidence(tool_run)
                    if ArtifactRef.model_validate(r['artifact_ref']) == current
                    and r['tool_name'] == envelope.labels.get('tool_name')]
                if owner.instance_id != self.instance_id or len(records) != 1:
                    raise OperationInvocationError("review_authorship_unavailable",
                        message="The subject has no verified original tool receipt in this instance.")
                authors = {tool_run}
            else:
                family = self._producer_output_family_from_envelope(name, envelope)
                if family is None or family.producer_instance_id != self.instance_id:
                    raise OperationInvocationError("review_subject_not_authored",
                        message="Select an authored scientific result for independent review. Original text alone can be analyzed by a source-based scientific task; control cannot establish review authorship for this input.")
                if family.producer_run_id:
                    authors = {family.producer_run_id}
                else:
                    if family.contract_availability != 'current':
                        raise OperationInvocationError("review_authorship_unavailable",
                            message="The subject's exact transformation contract is unavailable.")
                    ports = self._operation_catalog.operation(family.operation_id).spec.authorship_source_ports
                    sources = [item for item in family.producer_inputs if item.port_name in ports]
                    if not sources:
                        raise OperationInvocationError("review_authorship_unavailable",
                            message="This transformation does not declare traceable scientific contributors; review its authored source or repair the plugin contract.")
                    authors = set().union(*(resolve(item.artifact_name, item.ref) for item in sources))
            active.remove(current)
            cache[current] = authors
            return authors

        return frozenset(resolve(artifact_name, ref))

    def validate_inputs(self, compiled, inputs):
        """Re-derive every declared edge, comparing refs rather than navigation names."""
        ports = {port.name: port for port in compiled.spec.inputs}
        resolved = {port.name: [] for port in compiled.spec.inputs if port.derivation is None}
        actual = {port.name: [] for port in compiled.spec.inputs}
        for item in inputs:
            envelope = self.artifacts.catalog(item.artifact_ref)
            actual[item.port_name].append(item.artifact_ref)
            if ports[item.port_name].derivation is None:
                resolved[item.port_name].append(InvocationArtifact(
                    artifact_name=item.artifact_name, ref=envelope.ref,
                    schema_id=envelope.schema_id, media_type=envelope.media_type,
                    size_bytes=envelope.size_bytes, parent_refs=envelope.parent_refs))
        resolved = {port: tuple(items) for port, items in resolved.items()}
        self._derive_operation_inputs(compiled, resolved)
        derived = {}
        for port in compiled.spec.inputs:
            if port.derivation is None:
                continue
            expected = resolved.get(port.name, ())
            if tuple(actual[port.name]) != tuple(item.ref for item in expected):
                raise OperationInvocationError("input_origin_mismatch", port=port.name)
            derived.update(((port.name, item.ref), item) for item in expected)
        return derived

    def _producer_output_family_from_envelope(
        self,
        artifact_name: str,
        envelope: Any,
    ) -> ProducerOutputFamily | None:
        run_family = self._run_output_family(envelope)
        if run_family is not None:
            return run_family
        return self._transform_output_family(artifact_name, envelope)

    def _run_output_family(self, envelope: Any) -> ProducerOutputFamily | None:
        if self.runs is None:
            return None
        status = self.runs.completed_for_output(envelope.ref)
        if status is None or status.output_ref is None:
            return None
        is_primary_output = status.output_ref == envelope.ref
        if not is_primary_output and not any(
            ref == envelope.ref for _, ref in self.runs.evidence_output_refs(status)
        ):
            return None
        if any(envelope.labels.get(key) != expected for key, expected in (
            ("operation_id", status.operation_id),
            ("operation_version", status.operation_version),
            ("operation_digest", status.operation_digest),
        )):
            raise OperationInvocationError("producer_family_inconsistent")
        port_name = envelope.labels.get("operation_output_port")
        counts: dict[str, int] = {}
        producer_inputs = []
        for item in status.inputs:
            counts[item.port_name] = counts.get(item.port_name, 0) + 1
            producer_inputs.append(
                ProducerInputProjection(
                    port_name=item.port_name,
                    item_index=counts[item.port_name],
                    ref=item.artifact_ref,
                    artifact_name=item.artifact_name,
                    source_name=item.source_name,
                )
            )
        sources = tuple(
            ProducerEvidenceSource(
                source_kind="run_input",
                source_name=value.source_name,
                ref=value.artifact_ref,
            )
            for value in status.inputs
            if value.usage
            in {"claim_evidence", "evidence_inventory", "cached_excerpt"}
        )
        family_identity = canonical_sha256(
            {
                "producer": "run",
                "operation": status.operation_id,
                "operation_version": status.operation_version,
                "operation_digest": status.operation_digest,
                "run_id": status.run_id,
                "primary_ref": status.output_ref,
            }
        )
        try:
            producer = self._operation_catalog.recorded_operation(status.operation_id, version=status.operation_version, digest=status.operation_digest)
        except KeyError:
            producer = None
        if producer is None:
            return ProducerOutputFamily(
                primary_ref=status.output_ref,
                operation_id=status.operation_id,
                operation_version=status.operation_version,
                operation_digest=status.operation_digest,
                producer_kind="run",
                producer_instance_id=status.instance_id,
                producer_run_id=status.run_id,
                contract_availability="historical",
                unavailable_reason="producer_contract_unavailable",
                members=(
                    ProducerFamilyMember(port_name=port_name, item_name=None, ref=envelope.ref),
                ) if isinstance(port_name, str) else (),
                evidence_sources=sources,
                producer_inputs=tuple(producer_inputs),
                family_identity=family_identity,
            )
        if producer.spec.executor.kind != "agent":
            return None
        selected_port = next(
            (
                port
                for port in producer.spec.outputs
                if port.name == port_name
                and ((port.collection is None) == is_primary_output)
            ),
            None,
        )
        if selected_port is None or not self._artifact_matches_output_port(
            envelope, selected_port
        ):
            return None
        return ProducerOutputFamily(
            primary_ref=status.output_ref,
            operation_id=producer.spec.operation_id,
            operation_version=status.operation_version,
            operation_digest=status.operation_digest,
            producer_kind="run",
            producer_instance_id=status.instance_id,
            producer_run_id=status.run_id,
            contract_availability="current",
            unavailable_reason=None,
            members=(
                ProducerFamilyMember(
                    port_name=selected_port.name,
                    item_name=None,
                    ref=envelope.ref,
                ),
            ),
            evidence_sources=sources,
            producer_inputs=tuple(producer_inputs),
            reviewer_operation=(
                producer.spec.review.reviewer_operation
                if producer.spec.review is not None
                else None
            ),
            review_subject_outputs=(
                producer.spec.review.subject_outputs
                if producer.spec.review is not None
                else ()
            ),
            family_identity=family_identity,
        )

    def _transform_output_family(
        self,
        artifact_name: str,
        envelope: Any,
        *,
        verify_inputs: bool = True,
    ) -> ProducerOutputFamily | None:
        labels = envelope.labels
        operation_id = labels.get("operation_id")
        operation_version = labels.get("operation_version")
        operation_digest = labels.get("operation_digest")
        invocation_fingerprint = labels.get("operation_invocation_fingerprint")
        if (
            not isinstance(operation_id, str)
            or not isinstance(operation_version, str)
            or not isinstance(operation_digest, str)
            or not isinstance(invocation_fingerprint, str)
            or labels.get("transform_profile") != operation_id
        ):
            return None
        if labels.get("operation_invocation_instance", self._instance_id()) != self._instance_id():
            return None
        output_label = labels.get("output_label")
        if not isinstance(output_label, str):
            return None
        # Older outputs already have an exact durable creation binding. Recover
        # its family boundary from that binding, never from equal request bytes.
        suffix = "." + output_label
        legacy_name = (artifact_name if output_label == "primary" else
                       artifact_name[:-len(suffix)] if artifact_name.endswith(suffix) else None)
        invocation_name = labels.get("operation_invocation_name", legacy_name)
        if not isinstance(invocation_name, str) or not invocation_name:
            return None
        family_identity = canonical_sha256(
            {
                "producer": "transform",
                "instance": self._instance_id(),
                "invocation_name": invocation_name,
                "operation": operation_id,
                "operation_version": operation_version,
                "operation_digest": operation_digest,
                "invocation_fingerprint": invocation_fingerprint,
                "ordered_parents": envelope.parent_refs,
            }
        )

        instance_bindings = self.bindings.list(
            instance=self._instance_id(), namespace="artifact", name_prefix=invocation_name
        )
        subject_bindings = tuple(
            binding
            for binding in instance_bindings
            if binding.object_id == envelope.artifact_id
        )
        if not any(
            binding.name == artifact_name
            and binding.request_fingerprint == invocation_fingerprint
            for binding in subject_bindings
        ):
            return None
        siblings: dict[str, Any] = {}
        for binding in instance_bindings:
            if binding.request_fingerprint != invocation_fingerprint:
                continue
            candidate = self.artifacts.get_by_id(binding.object_id)
            candidate_labels = candidate.labels
            output_label = candidate_labels.get("output_label")
            if not isinstance(output_label, str):
                continue
            expected_name = invocation_name if output_label == "primary" else invocation_name + "." + output_label
            if binding.name != expected_name:
                continue
            if (candidate_labels.get("operation_invocation_name", invocation_name) != invocation_name
                    or candidate_labels.get("operation_invocation_instance", self._instance_id()) != self._instance_id()):
                raise OperationInvocationError("producer_family_inconsistent")
            if candidate.parent_refs != envelope.parent_refs or any(
                candidate_labels.get(key) != expected
                for key, expected in (
                    ("operation_id", operation_id),
                    ("operation_version", operation_version),
                    ("operation_digest", operation_digest),
                    ("transform_profile", operation_id),
                    ("operation_invocation_fingerprint", invocation_fingerprint),
                )
            ):
                raise OperationInvocationError("producer_family_inconsistent")
            output_label = candidate_labels.get("output_label")
            if not isinstance(output_label, str):
                raise OperationInvocationError("producer_family_inconsistent")
            existing = siblings.get(output_label)
            if existing is not None and existing.ref != candidate.ref:
                raise OperationInvocationError("producer_family_inconsistent")
            siblings[output_label] = candidate
        if "primary" not in siblings or envelope.ref not in {
            value.ref for value in siblings.values()
        }:
            return None

        def unavailable(reason: str) -> ProducerOutputFamily:
            return ProducerOutputFamily(
                primary_ref=siblings["primary"].ref,
                operation_id=operation_id,
                operation_version=operation_version,
                operation_digest=operation_digest,
                producer_kind="transform",
                producer_instance_id=self._instance_id(),
                producer_run_id=None,
                contract_availability="historical",
                unavailable_reason=reason,
                members=(),
                evidence_sources=(),
                producer_inputs=(),
                family_identity=family_identity,
            )
        try:
            compiled = self._operation_catalog.recorded_operation(operation_id, version=operation_version, digest=operation_digest)
        except KeyError:
            return unavailable("producer_contract_unavailable")
        if compiled.spec.executor.kind != "transform":
            return unavailable("producer_contract_unavailable")
        input_groups = self._transform_input_groups(compiled, envelope.parent_refs, verify_inputs=verify_inputs)
        if input_groups is None:
            return unavailable("producer_input_mapping_ambiguous")
        ordered_members = self._validated_transform_members(compiled, siblings)
        if ordered_members is None:
            return None
        return ProducerOutputFamily(
            primary_ref=siblings["primary"].ref,
            operation_id=operation_id,
            operation_version=operation_version,
            operation_digest=operation_digest,
            producer_kind="transform",
            producer_instance_id=self._instance_id(),
            producer_run_id=None,
            contract_availability="current",
            unavailable_reason=None,
            members=ordered_members,
            evidence_sources=(),
            producer_inputs=tuple(
                ProducerInputProjection(
                    port_name=port.name,
                    item_index=index,
                    ref=item.ref,
                )
                for port in compiled.spec.inputs
                for index, item in enumerate(input_groups[port.name], start=1)
            ),
            reviewer_operation=(
                compiled.spec.review.reviewer_operation
                if compiled.spec.review is not None
                else None
            ),
            review_subject_outputs=(
                compiled.spec.review.subject_outputs
                if compiled.spec.review is not None
                else ()
            ),
            family_identity=family_identity,
        )

    def _transform_input_groups(
        self, compiled: Any, parent_refs: tuple[Any, ...], *, verify_inputs: bool = True
    ) -> dict[str, tuple[Any, ...]] | None:
        if len(parent_refs) != len(set(parent_refs)):
            return None
        # Provenance-only restriction checks need immutable port metadata, not
        # another content hash pass over potentially large original materials.
        read = self.artifacts.verify if verify_inputs else self.artifacts.catalog
        envelopes = tuple(read(ref) for ref in parent_refs)
        ports = compiled.spec.inputs
        solutions: list[dict[str, tuple[Any, ...]]] = []

        def visit(port_index: int, offset: int, values: dict[str, tuple[Any, ...]]) -> None:
            if len(solutions) > 1:
                return
            if port_index == len(ports):
                if offset == len(envelopes):
                    solutions.append(dict(values))
                return
            port = ports[port_index]
            remaining_min = sum(item.min_items for item in ports[port_index + 1 :])
            remaining_max = sum(item.max_items for item in ports[port_index + 1 :])
            lower = max(port.min_items, len(envelopes) - offset - remaining_max)
            upper = min(port.max_items, len(envelopes) - offset - remaining_min)
            for count in range(lower, upper + 1):
                selected = envelopes[offset : offset + count]
                if not all(self._artifact_matches_input_port(item, port) for item in selected):
                    continue
                values[port.name] = selected
                visit(port_index + 1, offset + count, values)
            values.pop(port.name, None)

        visit(0, 0, {})
        return solutions[0] if len(solutions) == 1 else None

    def _validated_transform_members(
        self, compiled: Any, siblings: dict[str, Any]
    ) -> tuple[ProducerFamilyMember, ...] | None:
        by_port: dict[str, list[Any]] = {}
        valid_ports = {port.name for port in compiled.spec.outputs}
        for candidate in siblings.values():
            port_name = candidate.labels.get("operation_output_port")
            if port_name not in valid_ports:
                return None
            by_port.setdefault(port_name, []).append(candidate)
        expected_labels: list[tuple[str, str, int]] = []
        output_count = 0
        for port in compiled.spec.outputs:
            values = by_port.get(port.name, [])
            if not port.min_items <= len(values) <= port.max_items:
                return None
            if not all(self._artifact_matches_output_port(item, port) for item in values):
                return None
            for index in range(1, len(values) + 1):
                label = (
                    "primary"
                    if output_count == 0
                    else port.name
                    if port.collection is None and len(values) == 1
                    else f"{port.name}_{index:03d}"
                )
                expected_labels.append((label, port.name, index))
                output_count += 1
        if {label for label, _, _ in expected_labels} != set(siblings):
            return None
        if any(
            siblings[label].labels.get("operation_output_port") != port_name
            for label, port_name, _ in expected_labels
        ):
            return None
        return tuple(
            ProducerFamilyMember(
                port_name=port_name,
                item_name=(None if label == "primary" else label),
                ref=siblings[label].ref,
            )
            for label, port_name, _ in expected_labels
        )

    def _derived_parent_refs(self, ref, port):
        """Prefer exact control receipt edges over inherited task input parents."""
        envelope = self.artifacts.verify(ref)
        parents = envelope.parent_refs
        producer_id = envelope.labels.get('tool_producer_run')
        producer = None
        if self.runs is not None and producer_id and envelope.labels.get('tool_name'):
            producer = self.runs.status(producer_id)
            if producer.instance_id != self._instance_id():
                raise OperationInvocationError('input_origin_unavailable', port=port.name)
            receipts = [item for item in self.runs.tool_evidence(producer_id)
                if ArtifactRef.model_validate(item['artifact_ref']) == ref]
            if len(receipts) != 1 or receipts[0]['tool_name'] != envelope.labels['tool_name']:
                raise OperationInvocationError('input_origin_unavailable', port=port.name)
            if receipts[0].get('control_parents'):
                direct = tuple(ArtifactRef.model_validate(item) for item in receipts[0]['control_parents'])
                if any(parent not in parents for parent in direct):
                    raise OperationInvocationError('input_origin_unavailable', port=port.name)
                parents = direct
                producer = None  # Explicit edges require no historical inference.
            elif receipts[0].get('metadata', {}).get('derived_from'):
                direct = tuple(self.runs.source_descriptor(producer, alias).artifact_ref
                    for alias in receipts[0]['metadata']['derived_from'])
                if any(parent not in parents for parent in direct):
                    raise OperationInvocationError('input_origin_unavailable', port=port.name)
                parents, producer = direct, None
        matches = [parent for parent in parents
            if self._artifact_matches_input_port(self.artifacts.catalog(parent), port)]
        if producer is not None and len(matches) > 1:
            inherited = {item.artifact_ref for item in producer.inputs}
            matches = [parent for parent in matches if parent not in inherited]
        return matches

    @staticmethod
    def _artifact_matches_input_port(envelope: Any, port: Any) -> bool:
        return bool(
            (port.schema_id == "*" or envelope.schema_id == port.schema_id)
            and (port.media_types == ("*/*",) or envelope.media_type in port.media_types)
            and (port.max_item_bytes is None or envelope.size_bytes <= port.max_item_bytes)
        )

    @staticmethod
    def _artifact_matches_output_port(envelope: Any, port: Any) -> bool:
        return bool(
            envelope.kind == port.kind
            and envelope.schema_id == port.schema_id
            and envelope.payload_schema_version == port.payload_schema_version
            and envelope.media_type in port.media_types
            and (port.max_item_bytes is None or envelope.size_bytes <= port.max_item_bytes)
        )

    def _derive_operation_inputs(self, compiled, resolved):
        """Resolve only declared producer edges of exact selected immutable anchors."""
        ports = {port.name: port for port in compiled.spec.inputs}
        def bind(port):
            if port.name in resolved or port.derivation is None:
                return
            rule = port.derivation
            bind(ports[rule.anchor_port])
            anchors = resolved.get(rule.anchor_port, ())
            if not anchors and port.min_items == 0:
                resolved[port.name] = ()
                return
            def reject(reason):
                anchor = ports[rule.anchor_port]
                while anchor.derivation is not None:
                    anchor = ports[anchor.derivation.anchor_port]
                message = {
                    "input_origin_missing": "The selected material does not supply the required scientific source. ",
                    "input_origin_ambiguous": "The selected material has ambiguous required sources. ",
                }.get(reason, "The selected material's exact source is unavailable or incompatible. ")
                requirement = input_source_requirement(port)
                message_limit = ContractDiagnostic.model_json_schema()['properties']['message']['maxLength']
                if len(message + requirement) > message_limit:
                    requirement = ("Select original user task text or an exact structured goal source. Read this action's source_requirements for the selected input. Control resolves bindings; copying or renaming does not establish provenance."
                        if rule.source_original_text else
                        "Read this action's source_requirements for the selected input. If only originals exist, choose a source-based task that accepts them. Copying or renaming originals does not establish provenance. Control resolves bindings.")
                raise OperationInvocationError(reason, port=anchor.name if anchor.agent_visible else None,
                    message=message + requirement)
            if len(anchors) != 1:
                reject("input_origin_ambiguous" if anchors else "input_origin_missing")
            def family_for(ref):
                name = self.bindings.find_name(instance=self._instance_id(),
                    namespace="artifact", object_id=ref.artifact_id)
                if name is None:
                    reject("input_origin_unavailable")
                self.artifacts.verify(ref)
                return self._producer_output_family_from_envelope(name, self.artifacts.catalog(ref))
            refs = [anchors[0].ref]
            def matches_source(ref):
                envelope = self.artifacts.catalog(ref)
                if envelope.schema_id in rule.source_schemas:
                    return True
                if rule.source_original_text:
                    from ..schema.research_objective import is_original_text_objective
                    return is_original_text_objective(ref, envelope.media_type, envelope.labels)
                return False
            if rule.source_paths and not matches_source(anchors[0].ref):
                candidates = []
                for path in rule.source_paths:
                    selected = [anchors[0].ref]
                    for edge in path:
                        following = []
                        for ref in selected:
                            family = family_for(ref)
                            if family is not None and family.producer_instance_id == self._instance_id():
                                following.extend(item.ref for item in family.producer_inputs if item.port_name == edge)
                        selected = list(dict.fromkeys(following))
                    candidates.extend(ref for ref in selected
                        if matches_source(ref))
                refs = list(dict.fromkeys(candidates))
                if len(refs) != 1:
                    reject("input_origin_ambiguous" if refs else "input_origin_missing")
            for edge in rule.producer_input_path:
                following = []
                for ref in refs:
                    family = family_for(ref)
                    if family is None or family.producer_instance_id != self._instance_id():
                        reject("input_origin_unavailable")
                    following.extend(item.ref for item in family.producer_inputs if item.port_name == edge)
                refs = list(dict.fromkeys(following))
                if not refs:
                    reject("input_origin_missing")
            private_names = {}
            family = None
            if rule.select == "parents":
                # Only the exact anchor's immutable direct parents are candidates.
                # No public parent alias, completed author, head or global lookup
                # is needed to bind a control-owned typed execution package.
                refs = list(dict.fromkeys(parent for ref in refs
                    for parent in self._derived_parent_refs(ref, port)))
                private_names = {ref: anchors[0].artifact_name for ref in refs}
            elif rule.select != "subject":
                if len(refs) != 1:
                    reject("input_origin_ambiguous")
                family = family_for(refs[0])
                historical_hypothesis_sources = (family is not None
                    and compiled.spec.operation_id == "science.hypothesis.criticize.v1"
                    and rule.anchor_port == "hypothesis_portfolio" and rule.select == "sources"
                    and family.operation_id == "science.hypothesis.propose.v1"
                    and family.producer_run_id is not None
                    and any(item.ref == refs[0] and item.port_name == "hypothesis_portfolio"
                            for item in family.members))
                if (family is None or family.producer_instance_id != self._instance_id()
                        or (family.contract_availability != "current" and not historical_hypothesis_sources)):
                    reject("input_origin_unavailable")
                refs = ([item.ref for item in family.members if item.ref != family.primary_ref]
                        if rule.select == "siblings" else [item.ref for item in family.evidence_sources])
                refs = list(dict.fromkeys(refs))
            if rule.producer_output_port is not None:
                if len(refs) != 1:
                    reject("input_origin_ambiguous")
                family = family_for(refs[0])
                if family is None or family.contract_availability != "current" or family.producer_instance_id != self._instance_id():
                    reject("input_origin_unavailable")
                producer = self._operation_catalog.recorded_operation(family.operation_id, version=family.operation_version, digest=family.operation_digest)
                declared = next((item for item in producer.spec.outputs if item.name == rule.producer_output_port), None)
                if declared is None:
                    reject("input_origin_output_undeclared")
                if family.producer_run_id is None:
                    candidates = [item.ref for item in family.members if item.port_name == declared.name]
                else:
                    original = self.runs.status(family.producer_run_id)
                    if original.state != "completed" or original.output_ref != family.primary_ref:
                        reject("input_origin_unavailable")
                    exact_evidence = {ArtifactRef.model_validate(item["artifact_ref"])
                        for item in self.runs.tool_evidence(original.run_id)}
                    candidates = [original.output_ref, *self.artifacts.catalog(original.output_ref).parent_refs]
                    candidates.extend(ref for _, ref in self.runs.evidence_output_refs(original))
                    candidates = [ref for ref in dict.fromkeys(candidates)
                        if self.artifacts.catalog(ref).labels.get("operation_output_port") == declared.name
                        and self.artifacts.catalog(ref).labels.get("operation_digest") == original.operation_digest
                        and (ref == original.output_ref
                            or self.artifacts.catalog(ref).labels.get("tool_producer_run") == original.run_id
                            or (declared.name in {"tool_evidence", "attachments"} and ref in exact_evidence))]
                refs = list(dict.fromkeys(candidates))
                # Private artifacts deliberately have no public name binding.
                private_names = {ref: anchors[0].artifact_name for ref in refs} if not port.agent_visible else {}
            if len(refs) < port.min_items or len(refs) > port.max_items:
                reject("input_origin_ambiguous" if len(refs) > port.max_items else "input_origin_missing")
            values = []
            for ref in refs:
                name = private_names.get(ref) or self.bindings.find_name(instance=self._instance_id(), namespace="artifact", object_id=ref.artifact_id)
                if name is None:
                    reject("input_origin_unavailable")
                envelope = self.artifacts.catalog(ref)
                self.artifacts.verify(ref)
                family = self._producer_output_family_from_envelope(name, envelope) if ref not in private_names else family
                signal = self.runs.signal_for_output(ref, require_current=False) if self.runs else None
                values.append(InvocationArtifact(artifact_name=name, ref=ref, schema_id=envelope.schema_id,
                    media_type=envelope.media_type, size_bytes=envelope.size_bytes,
                    current=self.runs.input_is_current(instance_id=self._instance_id(), artifact_name=name, artifact_ref=ref) if self.runs else False,
                    parent_refs=envelope.parent_refs, labels=tuple(sorted(envelope.labels.items())),
                    historical=self._is_historical(envelope), handoff_verdict=signal.verdict if signal else None,
                    producer_run_id=family.producer_run_id if family else None,
                    producer_inputs=tuple((item.port_name,item.ref) for item in family.producer_inputs) if family else None))
            resolved[port.name] = tuple(values)
        for port in compiled.spec.inputs:
            bind(port)

    def _is_historical(self, envelope: Any) -> bool:
        operation_id = envelope.labels.get("operation_id")
        if operation_id is None:
            return False
        try:
            producer = self._operation_catalog.recorded_operation(operation_id, version=envelope.labels.get("operation_version"), digest=envelope.labels.get("operation_digest"))
        except KeyError:
            return True
        return False
