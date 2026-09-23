"""Instance, inventory, and Artifact routes for the Root scheduler facade."""

from __future__ import annotations

import hashlib
from typing import Any
from urllib.parse import urlencode

from ..schema.common import canonical_sha256
from ..service.intake import USER_TEXT_MEDIA_TYPE, USER_TEXT_SOURCE_ORIGIN
from ..service.instance_management import issue_instance_management_capability
from ..service.scheduler_bindings import SchedulerBinding
from .mcp_root_shared import RootToolError, identity_word as _identity_word

class RootInstanceRoutes:
    def instance_current(self) -> dict[str, Any]:
        if self.session_key is not None:
            if not self.bindings.client_enabled(session_key=self.session_key):
                return {"state": "paused", "management_url": self._instance_management_url()}
            bound = self.bindings.session_instance(session_key=self.session_key)
            if bound is None:
                self.instance = None
                return {
                    "state": "unbound",
                    "management_url": self._instance_management_url(),
                }
            self.instance = bound
        value = self.bindings.get_instance(instance_id=self._instance_id())
        result = self._instance_value(value)
        if (self.session_key is not None and self.instance_management_secret is not None
                and self.approval_base_url is not None):
            result["management_url"] = self._instance_management_url()
        return result

    def instance_list(self, *, state: str | None) -> dict[str, Any]:
        return {
            "instances": [
                self._instance_value(value)
                for value in self.bindings.list_instances(state=state)
            ]
        }

    def instance_close(self) -> dict[str, Any]:
        with self._create_lock:
            instance_id = self._instance_id()
            for binding in self.bindings.list(instance=instance_id, namespace="run"):
                if self.runs.status(binding.object_id).state in {"queued", "running"}:
                    raise RootToolError("research instance has an active scientific Run")
            for binding in self.bindings.list(instance=instance_id, namespace="approval"):
                if self.approvals.status(binding.object_id).status == "pending":
                    raise RootToolError("research instance has a pending human review")
            for binding in self.bindings.list(
                instance=instance_id, namespace="execution"
            ):
                if self.executions.status(binding.object_id).state not in {
                    "collected",
                    "abandoned",
                }:
                    raise RootToolError(
                        "research instance has an unfinished or uncollected execution"
                    )
            value = self.bindings.close_instance(instance_id=instance_id)
            self.instance = None
            return self._instance_value(value)

    def _instance_management_url(self) -> str:
        if (
            self.session_key is None
            or self.instance_management_secret is None
            or self.approval_base_url is None
        ):
            raise RootToolError(
                "local research-instance management is unavailable"
            )
        capability = issue_instance_management_capability(
            session_key=self.session_key,
            secret=self.instance_management_secret,
        )
        return (
            self.approval_base_url.rstrip("/")
            + "/sessions/" + self.session_key + "?"
            + urlencode({"capability": capability})
        )

    def scientific_current(self) -> dict[str, Any]:
        instance_id = self._instance_id()
        latest: dict[str, SchedulerBinding] = {}
        for binding in self.bindings.list(instance=instance_id, namespace="artifact"):
            previous = latest.get(binding.logical_name)
            if previous is None or binding.revision > previous.revision:
                latest[binding.logical_name] = binding
        return {
            "selections": [
                {
                    "kind": item.kind,
                    "artifact_name": next(
                        (
                            binding.name
                            for binding in self.bindings.list(
                                instance=instance_id, namespace="artifact"
                            )
                            if item.artifact_ref is not None
                            and binding.object_id == item.artifact_ref.artifact_id
                        ),
                        latest[item.logical_name].name,
                    ),
                    "selected_at": item.selected_at,
                }
                for item in self.bindings.scientific_selections(instance=instance_id)
                if item.logical_name in latest
            ]
        }

    def scientific_current_select(
        self, *, name: str, kind: str, expected_artifact_name: str | None
    ) -> dict[str, Any]:
        artifact_id = self._resolve_input_artifact(name)
        binding = self._binding("artifact", name)
        envelope = self.artifacts.get_by_id(artifact_id)
        if envelope.kind != kind:
            raise RootToolError(
                f"{name}: scientific object kind is {envelope.kind}, expected {kind}"
            )
        expected_ref = None
        if expected_artifact_name is not None:
            expected_id = self._resolve_input_artifact(expected_artifact_name)
            expected_ref = self.artifacts.get_by_id(expected_id).ref
        selected = self.bindings.select_scientific_object(
            instance=self._instance_id(),
            kind=kind,
            logical_name=binding.logical_name,
            artifact_ref=envelope.ref,
            expected_ref=expected_ref,
        )
        return {
            "kind": selected.kind,
            "artifact_name": binding.name,
            "selected_at": selected.selected_at,
        }

    def scientific_inventory(self, *, include_operations: bool = True) -> dict[str, Any]:
        """Return only latest scientific records and explicit current selections."""

        instance_id = self._instance_id()
        latest: dict[str, SchedulerBinding] = {}
        for binding in self.bindings.list(instance=instance_id, namespace="artifact"):
            previous = latest.get(binding.logical_name)
            if previous is None or binding.revision > previous.revision:
                latest[binding.logical_name] = binding
        selections = {
            item.kind: item.logical_name
            for item in self.bindings.scientific_selections(instance=instance_id)
        }
        objects = []
        for binding in sorted(latest.values(), key=lambda item: item.logical_name):
            envelope = self.artifacts.get_by_id(binding.object_id)
            signal = self.runs.signal_for_output(envelope.ref, require_current=False) if self.runs is not None else None
            objects.append(
                {
                    "artifact_name": binding.name,
                    "historical": self._is_historical(envelope),
                    "kind": envelope.kind,
                    "schema": envelope.schema_id,
                    "revision": binding.revision,
                    "selected_current": any(
                        logical_name == binding.logical_name
                        for logical_name in selections.values()
                    ),
                    "claim_admissible": (
                        envelope.labels.get("scientific_claim_admissible") != "false"
                    ),
                    "producer_handoff": (
                        signal.verdict if signal is not None else None
                    ),
                }
            )
        return {
            "objects": objects,
            **({"public_operations": self.operation_catalog(scope="public")["operations"]} if include_operations else {}),
            "current_selections": [
                {"kind": kind, "logical_name": logical_name}
                for kind, logical_name in sorted(selections.items())
            ],
        }

    def lifecycle_events(self, *, limit: int | None = None) -> dict[str, Any]:
        """Read changed lifecycle states through a durable service-owned cursor."""

        instance_id = self._instance_id()
        states: list[tuple[str, str, str]] = []
        for binding in self.bindings.list(instance=instance_id, namespace="run"):
            states.append(("run", binding.name, self.runs.status(binding.object_id).state))
        for binding in self.bindings.list(instance=instance_id, namespace="approval"):
            states.append(
                ("approval", binding.name, self.approvals.status(binding.object_id).status)
            )
        for binding in self.bindings.list(instance=instance_id, namespace="execution"):
            states.append(
                ("execution", binding.name, self.executions.status(binding.object_id).state)
            )
        if len(states) > 1024:
            raise RootToolError("scheduler lifecycle inventory exceeds its bounded view")
        observer = self.session_key or f"facade:{instance_id}"
        changes = self.bindings.observe_state_changes(
            instance=instance_id,
            observer_key=observer,
            states=tuple(states),
            limit=limit,
        )
        return {
            "poll_again": limit is not None and len(changes) == limit,
            "events": [
                {
                    "object_type": item.object_type,
                    "name": item.name,
                    "previous_state": item.previous_state,
                    "state": item.state,
                    "observed_at": item.observed_at,
                }
                for item in changes
            ]
        }

    def artifact_ingest_file(
        self,
        *,
        name: str,
        relative_path: str,
        media_type: str | None,
        on_conflict: str,
    ) -> dict[str, Any]:
        prepared = self.intake.prepare_file(
            relative_path=relative_path, media_type=media_type
        )
        fingerprint = canonical_sha256(
            {
                "operation": "artifact_ingest_file",
                "relative_path": prepared.relative_path,
                "media_type": prepared.media_type,
                "payload_sha256": hashlib.sha256(prepared.content).hexdigest(),
            }
        )
        with self._create_lock:
            target = self._creation_target(
                "artifact", name, fingerprint, on_conflict
            )
            if target.existing_object_id is None:
                reference = self.intake.ingest_prepared(prepared)
                binding = self._bind_target(
                    "artifact", target, reference.artifact_id, fingerprint
                )
            else:
                binding = self._binding("artifact", target.name)
        return {**self._binding_value(binding), "state": "bound"}

    def artifact_ingest_text(
        self,
        *,
        name: str,
        text: str,
        on_conflict: str,
    ) -> dict[str, Any]:
        content = text.encode("utf-8")
        fingerprint = canonical_sha256(
            {
                "operation": "artifact_ingest_text",
                "kind": "source_text",
                "schema_id": "opaque",
                "payload_schema_version": 1,
                "media_type": USER_TEXT_MEDIA_TYPE,
                "source_origin": USER_TEXT_SOURCE_ORIGIN,
                "payload_sha256": hashlib.sha256(content).hexdigest(),
            }
        )
        with self._create_lock:
            target = self._creation_target(
                "artifact", name, fingerprint, on_conflict
            )
            if target.existing_object_id is None:
                reference = self.intake.ingest_text(content=content)
                binding = self._bind_target(
                    "artifact", target, reference.artifact_id, fingerprint
                )
            else:
                binding = self._binding("artifact", target.name)
        return {**self._binding_value(binding), "state": "bound"}

    def artifact_catalog(self, *, name: str, view: str = "detail",
                         parent_offset: int = 0, parent_limit: int = 16) -> dict[str, Any]:
        binding = self._binding("artifact", name)
        envelope = self.artifacts.get_by_id(binding.object_id)
        if len(envelope.parent_refs) > 4096:
            raise RootToolError("artifact_catalog direct parent limit exceeded (4096)")
        metadata = {
            **self._binding_value(binding), "kind": envelope.kind, "schema": envelope.schema_id,
            "payload_schema_version": envelope.payload_schema_version, "media_type": envelope.media_type,
            "size_bytes": envelope.size_bytes,
        }
        if view == "producer_inputs":
            return self._producer_inputs_catalog(
                name=name,
                envelope=envelope,
                offset=parent_offset,
                limit=parent_limit,
            )
        total = len(envelope.parent_refs)
        if view == "summary":
            return {**metadata, "parent_count": total}
        if view == "parents" and parent_offset > total:
            raise RootToolError(f"parent_offset {parent_offset} exceeds parent_count {total}")
        refs = (envelope.parent_refs[parent_offset:parent_offset + parent_limit]
                if view == "parents" else envelope.parent_refs)
        instance_id = self._instance_id()
        parent_artifact_names = [
            self.bindings.find_name(
                instance=instance_id,
                namespace="artifact",
                object_id=parent.artifact_id,
            )
            for parent in refs
        ]
        labels = {
            key: value
            for key, value in envelope.labels.items()
            if not _identity_word(key)
        }
        parents = []
        for parent, parent_name in zip(refs, parent_artifact_names):
            metadata = self.artifacts.catalog(parent) if parent_name is not None else None
            parents.append({"artifact_name": parent_name,
                "schema": metadata.schema_id if metadata else None,
                "kind": metadata.kind if metadata else None,
                "producer": {key: metadata.labels[key] for key in
                    ("operation_id", "operation_output_port") if key in metadata.labels} if metadata else None})
        if view == "parents":
            end = parent_offset + len(parents)
            result = {"name": name, "schema": envelope.schema_id, "parents": parents,
                      "parent_count": total, "next_offset": end if end < total else None}
            if envelope.schema_id == "scidiscovery.tool-evidence-manifest.v1":
                self._project_manifest_parents(envelope, refs, parents, result)
            return result
        return {
            **self._binding_value(binding),
            "kind": envelope.kind,
            "schema": envelope.schema_id,
            "payload_schema_version": envelope.payload_schema_version,
            "media_type": envelope.media_type,
            "size_bytes": envelope.size_bytes,
            "created_at": envelope.created_at,
            "labels": labels,
            "parent_artifact_names": parent_artifact_names,
            "parents": parents,
        }

    def _producer_inputs_catalog(
        self, *, name: str, envelope: Any, offset: int, limit: int
    ) -> dict[str, Any]:
        family = self._producer_output_family_from_envelope(name, envelope)
        subject = {
            "artifact_name": name,
            "artifact_ref": envelope.ref.model_dump(mode="json"),
            "kind": envelope.kind,
            "schema": envelope.schema_id,
        }
        fallback = {"tool": "artifact_catalog", "name": name, "view": "parents"}
        if family is None:
            if offset:
                raise RootToolError(
                    f"parent_offset {offset} exceeds producer_input_count 0"
                )
            return {
                "subject": subject,
                "producer": {
                    "kind": None,
                    "operation_id": None,
                    "operation_version": None,
                    "operation_digest": None,
                    "availability": "unavailable",
                    "unavailable_reason": "producer_unavailable",
                },
                "producer_inputs": [],
                "producer_input_count": 0,
                "next_offset": None,
                "parents_fallback": fallback,
            }
        cross_instance = (
            family.producer_instance_id is not None
            and family.producer_instance_id != self._instance_id()
        )
        ordered = tuple(
            sorted(
                family.producer_inputs,
                key=lambda item: (item.port_name, item.item_index),
            )
        )
        if offset > len(ordered):
            raise RootToolError(
                f"parent_offset {offset} exceeds producer_input_count {len(ordered)}"
            )
        page = ordered[offset : offset + limit]
        inputs = []
        for item in page:
            current_access_name = self.bindings.find_name(
                instance=self._instance_id(),
                namespace="artifact",
                object_id=item.ref.artifact_id,
            )
            inputs.append(
                {
                    "port_name": item.port_name,
                    "item_index": item.item_index,
                    "artifact_ref": item.ref.model_dump(mode="json"),
                    "artifact_name": None if cross_instance else item.artifact_name,
                    "source_name": None if cross_instance else item.source_name,
                    "current_access_name": current_access_name,
                    "kind": item.ref.kind,
                    "schema": item.ref.schema_id,
                }
            )
        end = offset + len(inputs)
        availability = (
            "cross_instance" if cross_instance else family.contract_availability
        )
        reason = "cross_instance" if cross_instance else family.unavailable_reason
        return {
            "subject": subject,
            "producer": {
                "kind": family.producer_kind,
                "operation_id": family.operation_id,
                "operation_version": family.operation_version,
                "operation_digest": family.operation_digest,
                "availability": availability,
                "unavailable_reason": reason,
            },
            "producer_inputs": inputs,
            "producer_input_count": len(ordered),
            "next_offset": end if end < len(ordered) else None,
            "parents_fallback": fallback,
        }

    def _project_manifest_parents(
        self, envelope: Any, refs: tuple[Any, ...], parents: list[dict[str, Any]],
        result: dict[str, Any],
    ) -> None:
        """Join sealed manifest aliases to current names by exact direct-parent refs."""
        from ..schema.refs import ArtifactRef
        from ..service.tool_evidence import ToolEvidenceManifest
        try:
            manifest = ToolEvidenceManifest.model_validate_json(
                self.artifacts.read(envelope.ref)
            )
        except (KeyError, TypeError, ValueError, UnicodeError):
            result["manifest_projection"] = {"status": "unavailable",
                "reason": "manifest_invalid"}
            return
        invalid_records = 0
        parsed_records = []
        for record in manifest.records:
            try:
                ref = ArtifactRef.model_validate(record.get("artifact_ref"))
            except (AttributeError, ValueError):
                invalid_records += 1
                continue
            parsed_records.append((ref, {key: record.get(key) for key in
                ("alias", "tool_name", "media_type", "size_bytes", "metadata")}))
        page_records = 0
        for ref, parent in zip(refs, parents):
            bindings = [{"source_alias": alias, "port_name": binding.port_name}
                for alias, binding in manifest.bindings.items()
                if binding.artifact_ref == ref]
            records = [record for identity, record in parsed_records if identity == ref]
            if bindings:
                parent["manifest_bindings"] = bindings
            if records:
                parent["manifest_records"] = records
                page_records += len(records)
        unmapped_bindings = sum(
            binding.artifact_ref not in envelope.parent_refs
            for binding in manifest.bindings.values()
        )
        unmapped_records = sum(
            identity not in envelope.parent_refs for identity, _ in parsed_records
        )
        result["manifest_projection"] = {
            "status": (
                "complete"
                if not invalid_records and not unmapped_bindings and not unmapped_records
                else "partial"
            ),
            "binding_count": len(manifest.bindings),
            "record_count": len(manifest.records),
            "invalid_record_count": invalid_records,
            "unmapped_binding_count": unmapped_bindings,
            "unmapped_record_count": unmapped_records,
            "page_record_count": page_records,
        }



__all__ = ["RootInstanceRoutes"]
