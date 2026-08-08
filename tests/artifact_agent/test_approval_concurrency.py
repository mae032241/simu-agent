from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from scidiscovery.artifact_agent import LocalIdentityRef
from scidiscovery.artifact_agent.service import ApprovalError, ApprovalService

from ._approval_fixtures import (
    RECEIPT_SECRET,
    SERVICE_ACTOR,
    create_request,
    make_approval_fixture,
)


def test_opposite_concurrent_choices_produce_one_decision_and_restart_is_stable(
    tmp_path: Path,
) -> None:
    fixture = make_approval_fixture(tmp_path)
    launch = create_request(fixture)
    review = fixture.approvals.review("review_one", access_token=launch.access_token)
    identity = LocalIdentityRef(identity_id="user_da", display_name="Local User")

    def decide(option: str):
        try:
            return fixture.approvals.record_ui_decision(
                approval_id="review_one",
                access_token=launch.access_token,
                csrf_token=review.csrf_token,
                decision_nonce=review.decision_nonce,
                selected_option=option,
                rationale="required change" if option == "revise" else "",
                decided_by=identity,
                ui_session_id="ui_concurrent",
            )
        except ApprovalError as error:
            return type(error).__name__

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(decide, ("approve", "revise")))
    refs = [result for result in results if not isinstance(result, str)]
    assert len(refs) == 1
    assert len(fixture.artifacts.list_artifacts(kind="human_decision")) == 1

    restarted = ApprovalService(
        artifacts=fixture.artifacts,
        database_path=tmp_path / "state" / "approvals.sqlite3",
        service_actor=SERVICE_ACTOR,
        receipt_secret=RECEIPT_SECRET,
    )
    status = restarted.status("review_one")
    assert status.decision_ref == refs[0]
    assert len(fixture.artifacts.list_artifacts(kind="human_decision")) == 1
