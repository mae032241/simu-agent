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
            bound = self.bindings.session_instance(session_key=self.session_key)
            if bound is None:
                self.instance = None
                return {
                    "state": "unbound",
                    "management_url": self._instance_management_url(),
                }
            self.instance = bound
        value = self.bindings.get_instance(instance_id=self._instance_id())
        return self._instance_value(value)

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
            + "/instances?"
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

    def scientific_inventory(self) -> dict[str, Any]:
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
            "public_operations": self.operation_catalog(scope="public")["operations"],
            "current_selections": [
                {"kind": kind, "logical_name": logical_name}
                for kind, logical_name in sorted(selections.items())
            ],
        }

    def lifecycle_events(self) -> dict[str, Any]:
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
        )
        return {
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

    def artifact_catalog(self, *, name: str) -> dict[str, Any]:
        binding = self._binding("artifact", name)
        envelope = self.artifacts.get_by_id(binding.object_id)
        if len(envelope.parent_refs) > 4096:
            raise RootToolError("artifact_catalog direct parent limit exceeded (4096)")
        instance_id = self._instance_id()
        parent_artifact_names = [
            self.bindings.find_name(
                instance=instance_id,
                namespace="artifact",
                object_id=parent.artifact_id,
            )
            for parent in envelope.parent_refs
        ]
        labels = {
            key: value
            for key, value in envelope.labels.items()
            if not _identity_word(key)
        }
        parents = []
        for parent, parent_name in zip(envelope.parent_refs, parent_artifact_names):
            metadata = self.artifacts.catalog(parent) if parent_name is not None else None
            parents.append({"artifact_name": parent_name,
                "schema": metadata.schema_id if metadata else None,
                "kind": metadata.kind if metadata else None,
                "producer": {key: metadata.labels[key] for key in
                    ("operation_id", "operation_output_port") if key in metadata.labels} if metadata else None})
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



__all__ = ["RootInstanceRoutes"]
