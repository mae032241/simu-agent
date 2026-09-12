"""Shared review branching and non-blocking catalog diagnostics.

Candidate ports describe receiving capacity, never qualification. Actual Run
identity, verdict, history and coverage remain the responsibility of admission.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from scidiscovery.operation_contract import active_direct_revision_ports

if TYPE_CHECKING:
    from .catalog import CompiledCatalog
    from .spec import InputPortSpec, OutputPortSpec


def review_input_mode(
    *, operation_id: str, port_name: str, usage: str,
    direct_base_port: str | None = None,
    reviewer_operation: str | None = None,
    reviewer_input_port: str | None = None,
) -> Literal["background", "direct_revision", "review_subject", "witness"]:
    if usage == "evidence_inventory":
        return "background"
    if port_name == direct_base_port:
        return "direct_revision"
    if operation_id == reviewer_operation and port_name == reviewer_input_port:
        return "review_subject"
    return "witness"


def _can_receive(target: InputPortSpec, source: OutputPortSpec) -> bool:
    # Mirrors only the schema/media possibility of a concrete port binding;
    # codecs and resource digests are a separate compiler boundary.
    if target.schema_id == "*" and target.media_types == ("*/*",):
        return True
    return (target.schema_id == source.schema_id
            and bool(set(target.media_types) & set(source.media_types)))


def review_receiver_diagnostics(catalog: CompiledCatalog) -> tuple[dict, ...]:
    """Describe possible producer/consumer review seams without rejecting them.

Optional inputs are considered only in the scenario where this subject is
bound. Cardinality and shared-witness coverage require concrete Run identities.
    """
    operations = [catalog.operation(name) for name in catalog.operation_ids()]
    rows = []
    for consumer in operations:
        for subject in consumer.spec.inputs:
            direct = active_direct_revision_ports(
                consumer,
                {p.name for p in consumer.spec.inputs if p.min_items > 0}
                | {subject.name},
            )
            base = direct[0].name if direct else None
            mode_args = dict(operation_id=consumer.spec.operation_id,
                             port_name=subject.name, usage=subject.usage,
                             direct_base_port=base)
            if review_input_mode(**mode_args) == "background":
                continue
            for producer in operations:
                edge = producer.spec.review
                if edge is None or edge.reviewer_operation is None:
                    continue
                outputs = [p for p in producer.spec.outputs
                           if p.name in edge.subject_outputs
                           and _can_receive(subject, p)]
                if not outputs:
                    continue
                mode = review_input_mode(
                    **mode_args, reviewer_operation=edge.reviewer_operation,
                    reviewer_input_port=edge.reviewer_input_port,
                )
                reviewer = catalog.operation(edge.reviewer_operation)
                candidates = tuple(
                    p.name for p in consumer.spec.inputs
                    if any(_can_receive(p, out) for out in reviewer.spec.outputs)
                )
                rows.append({
                    "consumer_operation": consumer.spec.operation_id,
                    "subject_port": subject.name,
                    "subject_optional": subject.min_items == 0,
                    "producer_operation": producer.spec.operation_id,
                    "producer_outputs": tuple(p.name for p in outputs),
                    "reviewer_operation": edge.reviewer_operation,
                    "mode": mode,
                    "candidate_ports": candidates,
                    "status": ("receiver_missing" if mode == "witness"
                               and not candidates else "requires_bound_validation"),
                })
    return tuple(rows)
