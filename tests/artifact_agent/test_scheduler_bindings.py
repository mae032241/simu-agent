from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from scidiscovery.artifact_agent.service import (
    SchedulerBindingService,
    SchedulerInstanceClosed,
    SchedulerInstanceConflict,
    SchedulerNameConflict,
    SchedulerNameNotFound,
)


def test_semantic_binding_survives_service_restart(tmp_path: Path) -> None:
    database = tmp_path / "scheduler-bindings.sqlite3"
    first = SchedulerBindingService(database)
    first.bind(
        instance="interactive",
        namespace="task",
        name="review_candidate_model",
        object_id="tsk_internal_identity",
    )

    restarted = SchedulerBindingService(database)
    assert restarted.resolve(
        instance="interactive",
        namespace="task",
        name="review_candidate_model",
    ) == "tsk_internal_identity"
    assert restarted.find_name(
        instance="interactive",
        namespace="task",
        object_id="tsk_internal_identity",
    ) == "review_candidate_model"


def test_semantic_name_rebinding_fails_closed(tmp_path: Path) -> None:
    bindings = SchedulerBindingService(tmp_path / "scheduler-bindings.sqlite3")
    bindings.bind(
        instance="interactive",
        namespace="artifact",
        name="approved_context",
        object_id="art_first",
    )

    with pytest.raises(SchedulerNameConflict, match="already bound"):
        bindings.bind(
            instance="interactive",
            namespace="artifact",
            name="approved_context",
            object_id="art_second",
        )

    with pytest.raises(SchedulerNameNotFound, match="unknown artifact name"):
        bindings.resolve(
            instance="interactive",
            namespace="artifact",
            name="missing_context",
        )


def test_same_semantic_name_isolated_between_scheduler_instances(tmp_path: Path) -> None:
    bindings = SchedulerBindingService(tmp_path / "scheduler-bindings.sqlite3")
    bindings.bind(
        instance="campaign_one",
        namespace="execution",
        name="baseline",
        object_id="exe_one",
    )
    bindings.bind(
        instance="campaign_two",
        namespace="execution",
        name="baseline",
        object_id="exe_two",
    )

    assert bindings.resolve(
        instance="campaign_one", namespace="execution", name="baseline"
    ) == "exe_one"
    assert bindings.resolve(
        instance="campaign_two", namespace="execution", name="baseline"
    ) == "exe_two"


def test_control_object_owner_resolves_instance_and_semantic_revision(
    tmp_path: Path,
) -> None:
    bindings = SchedulerBindingService(tmp_path / "scheduler-bindings.sqlite3")
    instance = bindings.create_instance(
        name="approval_display",
        title="Approval display",
        objective="Show exact instance ownership in the local UI.",
    )
    expected = bindings.bind(
        instance=instance.instance_id,
        namespace="approval",
        name="foundation_review.rev2",
        logical_name="foundation_review",
        revision=2,
        object_id="apr_internal",
        request_fingerprint="a" * 64,
    )

    assert bindings.find_owner(
        namespace="approval", object_id="apr_internal"
    ) == (instance, expected)
    assert bindings.find_owner(
        namespace="approval", object_id="apr_missing"
    ) is None


def test_research_instance_lifecycle_and_session_binding_survive_restart(
    tmp_path: Path,
) -> None:
    database = tmp_path / "scheduler-bindings.sqlite3"
    first = SchedulerBindingService(database)
    instance = first.create_instance(
        name="fig4_sims",
        title="Fig. 4 SIMS",
        objective="Reproduce the bounded Fig. 4 profile.",
    )
    first.bind_session(session_key="sch_session", instance_id=instance.instance_id)

    restarted = SchedulerBindingService(database)
    assert restarted.session_instance(session_key="sch_session") == instance.instance_id
    assert restarted.select_instance(name="fig4_sims") == instance
    assert restarted.list_instances(state="active") == (instance,)

    closed = restarted.close_instance(instance_id=instance.instance_id)
    assert closed.state == "closed"
    with pytest.raises(SchedulerInstanceClosed, match="closed"):
        restarted.require_active_instance(instance_id=instance.instance_id)


def test_research_instance_name_is_idempotent_only_for_identical_metadata(
    tmp_path: Path,
) -> None:
    bindings = SchedulerBindingService(tmp_path / "scheduler-bindings.sqlite3")
    first = bindings.create_instance(
        name="dark_current",
        title="Dark current",
        objective="Test one complete-device baseline.",
    )
    assert bindings.create_instance(
        name="dark_current",
        title="Dark current",
        objective="Test one complete-device baseline.",
    ) == first
    with pytest.raises(SchedulerInstanceConflict, match="different metadata"):
        bindings.create_instance(
            name="dark_current",
            title="Different title",
            objective="Test one complete-device baseline.",
        )


def test_instance_proposal_does_not_create_until_human_decision(
    tmp_path: Path,
) -> None:
    bindings = SchedulerBindingService(tmp_path / "scheduler-bindings.sqlite3")
    proposal = bindings.prepare_instance_proposal(
        name="fig4_user_reviewed",
        title="Fig. 4 user-reviewed instance",
        objective="Reproduce one frozen Fig. 4 baseline.",
        session_key="sch_user_review",
    )

    assert proposal.state == "pending"
    assert bindings.list_instances() == ()
    assert bindings.session_instance(session_key="sch_user_review") is None

    activated = bindings.apply_instance_proposal_decision(
        approval_id=proposal.approval_id,
        selected_option="create_instance",
    )
    assert activated is not None
    assert activated.state == "activated"
    instance = bindings.select_instance(name="fig4_user_reviewed")
    assert bindings.session_instance(
        session_key="sch_user_review"
    ) == instance.instance_id


def test_instance_proposal_revision_request_leaves_no_instance(
    tmp_path: Path,
) -> None:
    bindings = SchedulerBindingService(tmp_path / "scheduler-bindings.sqlite3")
    proposal = bindings.prepare_instance_proposal(
        name="needs_revision",
        title="Needs revision",
        objective="Review this scope before creating an instance.",
        session_key="sch_revision",
    )
    revised = bindings.apply_instance_proposal_decision(
        approval_id=proposal.approval_id,
        selected_option="revise_instance",
    )
    assert revised is not None
    assert revised.state == "revision_requested"
    assert bindings.list_instances() == ()
    assert bindings.session_instance(session_key="sch_revision") is None


def test_revision_lookup_is_scoped_by_instance_and_logical_name(tmp_path: Path) -> None:
    bindings = SchedulerBindingService(tmp_path / "scheduler-bindings.sqlite3")
    fingerprint = "a" * 64
    bindings.bind(
        instance="first",
        namespace="artifact",
        name="paper_source",
        logical_name="paper_source",
        revision=1,
        object_id="art_first",
        request_fingerprint=fingerprint,
    )
    bindings.bind(
        instance="first",
        namespace="artifact",
        name="paper_source.rev2",
        logical_name="paper_source",
        revision=2,
        object_id="art_second",
        request_fingerprint="b" * 64,
    )
    assert bindings.next_revision(
        instance="first", namespace="artifact", logical_name="paper_source"
    ) == ("paper_source.rev3", 3)
    assert bindings.find_revision(
        instance="first",
        namespace="artifact",
        logical_name="paper_source",
        request_fingerprint=fingerprint,
    ).object_id == "art_first"
    assert bindings.find_revision(
        instance="second",
        namespace="artifact",
        logical_name="paper_source",
        request_fingerprint=fingerprint,
    ) is None


def test_legacy_binding_database_is_migrated_without_rewriting_identity(
    tmp_path: Path,
) -> None:
    database = tmp_path / "scheduler-bindings.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE scheduler_bindings (
                instance TEXT NOT NULL,
                namespace TEXT NOT NULL,
                name TEXT NOT NULL,
                object_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (instance, namespace, name)
            )
            """
        )
        connection.execute(
            "INSERT INTO scheduler_bindings VALUES (?, ?, ?, ?, ?)",
            ("interactive", "artifact", "paper_source", "art_legacy", "2026-01-01T00:00:00Z"),
        )

    bindings = SchedulerBindingService(database)
    migrated = bindings.get_binding(
        instance="interactive", namespace="artifact", name="paper_source"
    )
    assert migrated.object_id == "art_legacy"
    assert migrated.logical_name == "paper_source"
    assert migrated.revision == 1
    assert migrated.request_fingerprint is None
    legacy = bindings.get_instance(instance_id="interactive")
    assert legacy.name == "legacy.interactive"
    assert legacy.state == "closed"
