"""Current-result provenance survives the three bounded presentation layers."""
from types import SimpleNamespace as NS
import pytest

from scidiscovery.artifact_agent.approval_ui import presentation
from scidiscovery.artifact_agent.approval_ui.presentation_render import render_presentation
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.general_science_views import build_presentation as general
from tests.operations.test_instance_read_model import system, bind, run


@pytest.mark.parametrize("kind,title,prompt", [
    ("execution_authorization", "执行审批", "是否授权执行本次冻结的实验对象"),
    ("scientific_foundation", "科研依据审批", "是否批准本次提交的科研依据"),
    ("plugin_custom_request", "科研审批", "请审阅本次冻结请求"),
])
def test_production_approval_kind_is_not_reinterpreted(system, kind, title, prompt):
    from scidiscovery.artifact_agent.approval_ui.render import render_review
    from scidiscovery.artifact_agent.approval_ui.workbench_render import render_node
    from scidiscovery.artifact_agent.schema.approval import ApprovalOption, LocalIdentityRef
    subject = record(system, "subject", "fixture.subject", {})
    question = "Exact original action and its limits remain visible. " * 12
    launch = system.approvals.create_request(approval_id="kind-fixture", kind=kind,
        subject_refs=(subject.ref,), question=question, requested_by=system.actor,
        options=(ApprovalOption(option_id="exact_option", label="Custom original option", description="Original conditions", requires_rationale=True),
                 ApprovalOption(option_id="decline",label="Decline",description="Do not authorize",requires_rationale=False)),
        idempotency_key="kind-fixture")
    review = system.approvals.review(launch.approval_id, access_token=launch.access_token)
    before = system.artifacts.read(review.request_ref)
    page = render_review(review, access_token=launch.access_token,
        identity=LocalIdentityRef(identity_id="fixture",display_name="测试用户")).decode()
    assert f"<h1>{title}</h1>" in page and f"<h2>{prompt}</h2>" in page
    visible_intro = page.split("<div class='question'>",1)[1].split("<details",1)[0]
    assert "Exact original action and its limits remain visible." in visible_intro
    assert "value='exact_option'" in page and "Custom original option" in page
    assert "data-requires-rationale='true'" in page
    if kind != "scientific_foundation":
        assert "是否批准本次提交的科研依据" not in page
    node = render_node({"kind":"approval", "key":"approval:fixture", "state":"pending",
        "request":{"payload":{"kind":kind,"question":question}}}, instance_id=system.a).decode()
    assert f"<h2>{title}</h2>" in node and "Exact original action" in node
    assert system.artifacts.read(review.request_ref) == before
    assert system.approvals.status(launch.approval_id).status == "pending"


def record(s, name, schema, payload, parents=()):
    value = s.artifacts.register(canonical_json(payload), ArtifactRegistration(kind="fixture", schema_id=schema,
        payload_schema_version=1, creator=s.actor, media_type="application/json", parent_refs=parents), idempotency_key=name)
    bind(s, s.a, "artifact", name, value.artifact_id)
    return value


def provider(monkeypatch):
    monkeypatch.setattr(presentation, "_provider_entries", lambda discover: (NS(name="general", load=lambda: general),))


def test_large_inputs_cannot_replace_current_completed_review(system, monkeypatch):
    provider(monkeypatch)
    s = system
    old = [record(s, f"background-{i}", "scidiscovery.scientific-review.v1",
        {"verdict":"blocked", "summary":"old background " + "z"*57000}) for i in range(5)]
    current = record(s, "current", "scidiscovery.scientific-review.v1",
        {"verdict":"pass", "summary":"Exact current summary"})
    run(s,"current-run",inputs=tuple(NS(port_name="current_progress",artifact_ref=r.ref) for r in old),output=current.ref)
    context=s.model.node_context(s.a,"run:current-run")
    assert context["artifacts"][0]["artifact_id"] == current.artifact_id
    value=presentation.build_presentation(context["artifacts"],focus_artifact_ids=context["focus_artifact_ids"])
    assert value["sections"][0]["items"][0]["source"]["artifact_id"] == current.artifact_id
    html=render_presentation(value,evidence_href=lambda a,p:"/original/"+a,image_href=lambda a:"/image/"+a)
    main=html.split("<section class='conclusion-card'>",1)[1].split("</section>",1)[0]
    assert "通过" in main and "Exact current summary" in main
    assert "old background" not in main and "存在阻断" not in main


def test_parameters_keep_exact_plan_scope_and_review_findings_links(system, monkeypatch):
    provider(monkeypatch)
    s = system
    payload = {"proposals":[{"variables":[{"variable_key":"depth", "baseline_value":5}]}]}
    plan = record(s, "bound-plan", "scidiscovery.experiment-portfolio.v1", payload)
    old = record(s, "historical-plan", "scidiscovery.experiment-portfolio.v1", payload)
    review = record(s, "review-output", "scidiscovery.scientific-review.v1", {"verdict":"pass", "findings":[{"detail":"scope"}]})
    run(s, "scoped-review", inputs=(NS(port_name="experiment_plan",artifact_ref=plan.ref),
        NS(port_name="current_progress",artifact_ref=old.ref)), output=review.ref)
    context = s.model.node_context(s.a,"run:scoped-review")
    assert context["task_artifact_ids"] == [plan.artifact_id]
    value = presentation.build_presentation(context["artifacts"], focus_artifact_ids=context["focus_artifact_ids"],
        task_artifact_ids=context["task_artifact_ids"])
    page = render_presentation(value, evidence_href=lambda a,p:"/original/"+a+p, image_href=lambda a:"/image/"+a)
    main = page.split("<section class='conclusion-card'>",1)[1].split("</section>",1)[0]
    assert "/original/"+plan.artifact_id in main and old.artifact_id not in main
    assert "/original/"+review.artifact_id+"/findings" in main
    assert "本节点成果 / 绑定计划中的参数 · 预览 1 条" in page
    assert "关联依据 / 历史参数 · 预览 1 条" in page


def test_failed_run_does_not_adopt_input_verdict(system, monkeypatch):
    provider(monkeypatch)
    old=record(system,"old","scidiscovery.scientific-review.v1",{"verdict":"pass","summary":"Earlier result"})
    run(system,"failed",state="failed",inputs=(NS(port_name="current_progress",artifact_ref=old.ref),))
    context=system.model.node_context(system.a,"run:failed")
    assert context["focus_artifact_ids"] == []
    value=presentation.build_presentation(context["artifacts"],focus_artifact_ids=[])
    html=render_presentation(value,evidence_href=lambda a,p:"/original/"+a,image_href=lambda a:"/image/"+a)
    main=html.split("<section class='conclusion-card'>",1)[1].split("</section>",1)[0]
    assert "没有可展示的本节点封存结论" in main
    assert "Earlier result" not in main and "通过" not in main
    assert "Earlier result" in html


def test_materialized_plan_uses_exact_design_objective_port(system):
    s=system
    original=record(s,"objective","scidiscovery.research-objective.v1",{"statement":"Original"})
    feedback=record(s,"feedback","scidiscovery.research-objective.v1",{"statement":"Background"})
    old=record(s,"prior","scidiscovery.experiment-portfolio.v1",{},(feedback.ref,))
    intent=record(s,"intent","scidiscovery.experiment-design-intent.v1",{},(old.ref,original.ref,feedback.ref))
    plan=record(s,"plan","scidiscovery.experiment-portfolio.v1",{},(intent.ref,))
    producer=run(s,"design",inputs=(NS(port_name="research_objective",artifact_ref=original.ref),
        NS(port_name="current_progress",artifact_ref=old.ref),NS(port_name="user_context",artifact_ref=feedback.ref)),output=intent.ref)
    run(s,"review",inputs=(NS(port_name="experiment_plan",artifact_ref=plan.ref),))
    s.runs.related_runs=lambda *,artifact_ref,**kwargs: (producer,) if artifact_ref==intent.ref else ()
    binding=s.model._binding(s.a,"run:review")
    refs,gaps=s.model._objective_navigation(s.a,binding,s.model._roots(s.a,binding))
    assert [r["artifact_id"] for r in refs]==[original.artifact_id]
    assert gaps==[]


def test_plan_revision_uses_prior_port_not_same_schema_background(system):
    s=system
    first=record(s,"original","scidiscovery.research-objective.v1",{"statement":"Original"})
    other=record(s,"other","scidiscovery.research-objective.v1",{"statement":"Other"})
    prior=record(s,"prior-plan","scidiscovery.experiment-portfolio.v1",{},(first.ref,))
    background=record(s,"background-plan","scidiscovery.experiment-portfolio.v1",{},(other.ref,))
    revised=record(s,"revised","scidiscovery.experiment-portfolio.v1",{},(prior.ref,background.ref))
    producer=run(s,"revision",inputs=(NS(port_name="experiment_plan",artifact_ref=prior.ref),
        NS(port_name="current_progress",artifact_ref=background.ref)),output=revised.ref)
    s.runs.related_runs=lambda *,artifact_ref,**kwargs: (producer,) if artifact_ref==revised.ref else ()
    binding=s.model._binding(s.a,"artifact:revised")
    refs,gaps=s.model._objective_navigation(s.a,binding,(revised.ref,))
    assert [r["artifact_id"] for r in refs]==[first.artifact_id] and not gaps


def test_large_approval_exposes_own_question_without_control_field_dump(system):
    envelope=record(system,"large-request","scidiscovery.approval-request",
        {"kind":"run_request","question":"Authorize this exact object?","options":[],"nonce_hash":"x"*90000})
    value=system.model._presentation_view(system.a,envelope)
    assert value["payload"]["question"]=="Authorize this exact object?"
    assert "nonce_hash" not in value["payload"]
    assert value["original"]["artifact_id"]==envelope.artifact_id
