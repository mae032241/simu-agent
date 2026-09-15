"""Real Chromium layout/form checks using isolated synthetic research records."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

repository = Path.cwd()
for relative in ("src", "plugins/tcad_artifact", "plugins/curve_score", "plugins/curve_figure_evidence", "."):
    sys.path.insert(0, str(repository / relative))
sys.path.append("/tmp/scid-workbench-browser")
from playwright.sync_api import sync_playwright
from PIL import Image, ImageDraw
from scidiscovery.artifact_agent.approval_ui import presentation
from scidiscovery.artifact_agent.approval_ui.app import ApprovalUI
from scidiscovery.artifact_agent.approval_ui.read_model import InstanceReadModel
from scidiscovery.artifact_agent.approval_ui.trajectory import TrajectoryStore
from scidiscovery.artifact_agent.service.maintenance import StateMaintenanceLock
from scidiscovery.artifact_agent.schema.approval import ApprovalOption
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.service.instance_archive import InstanceArchive
from scidiscovery.artifact_agent.service.instance_management import issue_instance_management_capability
from scidiscovery.general_science_views import build_presentation as general_view
from tcad_artifact.instance_views import build_presentation as tcad_view
from tests.operations.test_instance_presentations import parameter_family
from tests.operations.test_instance_read_model import system as read_fixture

presentation.entry_points = lambda **kwargs: (SimpleNamespace(name="general_science", load=lambda: general_view),
    SimpleNamespace(name="tcad_artifact", load=lambda: tcad_view))
evidence = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix="workbench-browser-fixture-") as temporary:
    project, state = Path(temporary) / "project", Path(temporary) / "state"
    project.mkdir()
    state.mkdir()
    # Browser checks need stored approvals and display reads, not compilation of
    # every scientific Operation. Those contracts have separate isolated tests.
    fixture = read_fixture.__wrapped__(state)
    runtime = SimpleNamespace(project_root=project, state_root=state, actor=fixture.actor,
        artifacts=fixture.artifacts, scheduler_bindings=fixture.bindings, runs=fixture.runs,
        approvals=fixture.approvals, executions=fixture.executions, operation_catalog=None,
        maintenance=StateMaintenanceLock(state / "maintenance.lock"))
    instance = runtime.scheduler_bindings.create_instance(name="ui.fixture", title="审批与轨迹验收 · 合成示例",
        objective="仅用于界面验收；不代表 Fig4 科学结论")
    def register(name, schema, payload, parents=(), raw=None, media="application/json"):
        envelope = runtime.artifacts.register(canonical_json(payload) if raw is None else raw,
            ArtifactRegistration(kind="fixture", schema_id=schema, payload_schema_version=1,
                creator=runtime.actor, media_type=media, parent_refs=parents), idempotency_key=name)
        runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace="artifact", name=name, object_id=envelope.artifact_id)
        return envelope
    goal = register("goal", "scidiscovery.research-objective.v1", {"statement": "恢复掺杂深度、曲线形状及前尾平台的一致性（合成验收目标）"})
    plan = register("plan", "scidiscovery.experiment-portfolio.v1", {"objective": "合成界面验收",
        "proposals": [{"experiment_key": "shape", "objectives": ["深度", "形状", "平台区"],
            "current_objectives": ["比较深度与曲线形状"], "implementation_notes": "大源码只在明确请求时读取。" * 2000}]}, (goal.ref,))
    references = [plan.ref]
    family = parameter_family(source_type="web_snapshot")
    import copy
    claim = family[0]["payload"]["claims"][0]
    requirement = family[2]["payload"]["parameters"][0]
    for index in range(1, 12):
        extra = copy.deepcopy(claim)
        extra["parameter_key"] = f"fixture_parameter_{index}"
        extra["observations"][0]["locator"] = "合成来源定位：" + "附录表格中的原始条目与实验条件；" * 18
        family[0]["payload"]["claims"].append(extra)
        family[2]["payload"]["parameters"].append({**requirement,
            "parameter_key": extra["parameter_key"], "display_name": f"界面验收参数 {index}（仅合成示例）"})
    family[1]["payload"]["sources"][0]["title"] = "合成来源题目，用于验证长引用的换行与原件入口。" * 10
    for record in family:
        references.append(register(record["artifact_id"], record["schema_id"], record["payload"]).ref)
    plot = Image.new("RGB", (900, 340), "white")
    drawing = ImageDraw.Draw(plot)
    drawing.line([(70, 40), (70, 280), (850, 280)], fill="#607080", width=2)
    drawing.line([(70, 85), (200, 85), (400, 105), (600, 230), (850, 245)], fill="#2468a0", width=4)
    drawing.line([(70, 90), (200, 92), (400, 112), (600, 210), (850, 237)], fill="#b55f30", width=4)
    drawing.text((80, 305), "SYNTHETIC UI FIXTURE - no scientific result", fill="#334455")
    image_bytes = io.BytesIO()
    plot.save(image_bytes, format="PNG")
    references.append(register("figure", "fixture.figure", None, raw=image_bytes.getvalue(), media="image/png").ref)
    launch = runtime.approvals.create_request(approval_id="apr_visual_fixture", kind="execution_authorization", subject_refs=tuple(references),
        question="合成验收：当前任务、参数来源与不确定性是否足以支持下一步？",
        options=tuple(ApprovalOption(option_id=value, label=label,
            description="按已编译的操作审批契约记录这一选择。", requires_rationale=False)
            for value,label in (("authorize_execution","授权执行"),("reject_execution","拒绝执行"))),
        idempotency_key="approval.fixture", requested_by=runtime.actor)
    runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace="approval", name="visual.review", object_id=launch.approval_id)
    model = InstanceReadModel(artifacts=runtime.artifacts, bindings=runtime.scheduler_bindings, runs=runtime.runs,
        approvals=runtime.approvals, executions=runtime.executions, operation_catalog=runtime.operation_catalog)
    ui = ApprovalUI(runtime.approvals, bindings=runtime.scheduler_bindings, read_model=model,
        instance_management_secret=b"b" * 32, maintenance=runtime.maintenance,
        instance_archive=InstanceArchive(runtime), trajectory_store=TrajectoryStore(state / "ui/workbench.sqlite3"))
    base = ui.start()
    browser_env = dict(os.environ)
    cjk_font = Path("/mnt/c/Windows/Fonts/msyh.ttc")
    if cjk_font.is_file():
        font_directory = Path(temporary) / "fonts"
        font_directory.mkdir()
        (font_directory / cjk_font.name).symlink_to(cjk_font)
        font_config = Path(temporary) / "fonts.conf"
        font_config.write_text(f'<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig>'
            f'<include ignore_missing="yes">/etc/fonts/fonts.conf</include><dir>{font_directory}</dir>'
            f'<cachedir>{Path(temporary) / "font-cache"}</cachedir></fontconfig>')
        browser_env["FONTCONFIG_FILE"] = str(font_config)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, env=browser_env,
                args=["--no-sandbox", "--no-zygote", "--single-process", "--disable-gpu", "--disable-dev-shm-usage", "--js-flags=--max-old-space-size=64"])
            if "--no-js" in sys.argv:
                context=browser.new_context(java_script_enabled=False, viewport={"width":1280,"height":900})
                page=context.new_page(); page.set_default_timeout(5000)
                assert page.goto(base + launch.review_path).status == 200
                assert page.locator('form[action$="/decision"]').count() == 1
                assert page.locator('button[type="submit"]').is_enabled()
                page.locator('details.parameters-panel > summary').click()
                assert page.locator('.parameter-table').first.is_visible()
                assert runtime.approvals.status(launch.approval_id).status == "pending"
                context.close();browser.close()
                print(json.dumps({"no_js_native_form":True,"no_decision_submitted":True,"details_operable":True}))
                raise SystemExit(0)
            context = browser.new_context(viewport={"width":1280,"height":900}, locale="zh-CN")
            page = context.new_page(); page.set_default_timeout(8000)
            page.route("**/*", lambda route: route.continue_() if route.request.method == "GET" else route.abort())
            errors=[]; page.on("pageerror", lambda error: errors.append(str(error)))
            assert page.goto(base + launch.review_path).status == 200
            assert page.locator('form[action$="/decision"]').count() == 1
            assert page.locator('h1').inner_text() == "执行审批"
            assert "是否批准本次提交的科研依据" not in page.locator('body').inner_text()
            assert page.locator('input[name="selected_option"]').evaluate_all("nodes=>nodes.map(n=>n.value)") == ["authorize_execution","reject_execution"]
            assert page.locator('details[open]').count() == 0
            height = page.evaluate('document.documentElement.scrollHeight')
            page.screenshot(path=str(evidence / "usability-pending-r2-wide.png"))
            params=page.locator("details.parameters-panel")
            params.locator(":scope > summary").click()
            assert page.locator(".parameter-table tbody tr").count() >= 3
            params.scroll_into_view_if_needed()
            page.screenshot(path=str(evidence / "usability-pending-r2-parameters.png"))
            params.locator(":scope > summary").click()
            figures=page.locator("details.figures-panel")
            figures.locator(":scope > summary").click()
            page.locator("img").first.scroll_into_view_if_needed()
            page.wait_for_function("document.querySelector('img').complete && document.querySelector('img').naturalWidth > 0")
            page.screenshot(path=str(evidence / "usability-pending-r2-figure.png"))
            figures.locator(":scope > summary").click()
            widths=[]
            for width in (768,390):
                page.set_viewport_size({"width":width,"height":900}); page.evaluate("scrollTo(0,0)")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+2")
                assert page.locator(".review-main").bounding_box()["y"] < page.locator(".decision-column").bounding_box()["y"]
                page.screenshot(path=str(evidence / f"usability-pending-r2-{width}.png")); widths.append(width)
            context.close(); browser.close()
            result={"fixture_only":True,"request_kind":"execution_authorization","option_ids":["authorize_execution","reject_execution"],"pending_form":True,"no_decision_submitted":True,
                "image_loaded":True,"mobile_evidence_before_decision":True,"widths":[1280,*widths],
                "default_height":height,"javascript_errors":errors}
            assert not errors, errors
            (evidence/"USABILITY_PENDING_BROWSER_R2.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
            print(json.dumps(result,ensure_ascii=False))
    finally:
        ui.stop()
