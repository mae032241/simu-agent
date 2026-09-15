"""Isolated Chromium navigation/ownership flow, without scientific computation."""
import json, os, sys, tempfile
from pathlib import Path
repository=Path.cwd()
for relative in ("src","plugins/tcad_artifact","."):
    sys.path.insert(0,str(repository/relative))
sys.path.append("/tmp/scid-workbench-browser")
from playwright.sync_api import sync_playwright
from scidiscovery.artifact_agent.approval_ui.app import ApprovalUI
from scidiscovery.artifact_agent.approval_ui.trajectory import TrajectoryStore
from scidiscovery.artifact_agent.service.instance_management import issue_instance_management_capability
from tests.operations.test_instance_read_model import system, artifact, approval, run
from types import SimpleNamespace

evidence=Path(__file__).resolve().parent
mode=sys.argv[1] if len(sys.argv)>1 else "flow"
with tempfile.TemporaryDirectory(prefix="home-navigation-") as temporary:
    root=Path(temporary)
    fixture=system.__wrapped__(root)
    instance=fixture.bindings.get_instance(instance_id=fixture.a)
    other=fixture.bindings.get_instance(instance_id=fixture.b)
    plan=artifact(fixture,"plan",{"message":"仅用于导航验证的不可变原件"},instance=fixture.a)
    launch=approval(fixture,"navigation.approval",(plan.ref,),instance=fixture.a,kind="execution_authorization")
    run(fixture,"navigation.sample",instance=fixture.a,output=plan.ref)
    fixture.runs.recent_ids=lambda *,instance_id,limit: tuple(r.run_id for r in fixture.runs.records.values() if r.instance_id==instance_id)[-limit:]
    original_session="sch_"+"1"*32;other_session="sch_"+"2"*32
    fixture.bindings.bind_session(session_key=original_session,instance_id=fixture.a)
    fixture.bindings.bind_session(session_key=other_session,instance_id=fixture.b)
    runtime=SimpleNamespace(scheduler_bindings=fixture.bindings,approvals=fixture.approvals)
    ui=ApprovalUI(fixture.approvals,bindings=fixture.bindings,read_model=fixture.model,
        instance_management_secret=b"b"*32,trajectory_store=TrajectoryStore(root/"views.sqlite3"))
    base=ui.start();browser_env=dict(os.environ)
    font=Path("/mnt/c/Windows/Fonts/msyh.ttc")
    if font.is_file():
        fonts=root/"fonts";fonts.mkdir();(fonts/font.name).symlink_to(font)
        config=root/"fonts.conf";config.write_text(f"<fontconfig><include ignore_missing='yes'>/etc/fonts/fonts.conf</include><dir>{fonts}</dir><cachedir>{root}/font-cache</cachedir></fontconfig>")
        browser_env["FONTCONFIG_FILE"]=str(config)
    try:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True,env=browser_env,
                args=["--no-sandbox","--no-zygote","--single-process","--disable-gpu","--disable-dev-shm-usage","--js-flags=--max-old-space-size=32","--disable-features=BackForwardCache"])
            context=browser.new_context(viewport={"width":1280,"height":900},locale="zh-CN")
            page=context.new_page();page.set_default_timeout(8000)
            errors=[];page.on("pageerror",lambda error:errors.append(str(error)))
            token=issue_instance_management_capability(session_key=original_session,secret=b"b"*32)
            assert page.goto(base+"/instances?capability="+token).status==200
            assert page.locator(".home-session").get_by_text(instance.title,exact=True).count()==1
            heights={"home":page.evaluate("document.documentElement.scrollHeight")}
            if mode.startswith("link_"):
                access=context.request.post(base+"/instances/access",form={"capability":token,"csrf":ui.session_id,
                    "instance_id":instance.instance_id,"scope":"read"},headers={"Origin":base},max_redirects=0)
                assert access.status==303
                paths={"link_node":f"/instance/{instance.instance_id}/nodes/run%3Anavigation.sample",
                    "link_evidence":f"/instance/{instance.instance_id}/evidence/{plan.artifact_id}","link_review":launch.review_path}
                response=page.goto(base+paths[mode])
                print(json.dumps({"page":mode,"status":response.status}),flush=True)
                assert response.status==200,page.locator("body").inner_text()[:500]
                assert page.locator(".global-navigation .home-button").count()==1
                page.locator(".global-navigation .home-button").click()
                page.wait_for_url(base+"/")
                assert page.locator("form[action='/instances/select']").count()==1
                context.close();browser.close()
                print(json.dumps({"fixture_only":True,"page":mode,"return_to_home_preserves_context":True}))
                raise SystemExit(0)
            if mode == "home":
                page.screenshot(path=str(evidence/"home-wide.png"))
                page.set_viewport_size({"width":390,"height":900})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+2")
                page.screenshot(path=str(evidence/"home-390.png"))
                context.close();browser.close()
                print(json.dumps({"fixture_only":True,"page":"home","widths":[1280,390],"height":heights["home"]}))
                raise SystemExit(0)
            page.locator(".home-entry[href='/instances/manage']").click()
            assert page.locator("form[action='/instances/select']").count()==0
            assert page.locator("form[action='/instances/create']").count()==0
            heights["directory"]=page.evaluate("document.documentElement.scrollHeight")
            if mode == "directory":
                page.screenshot(path=str(evidence/"directory-wide.png"))
                page.set_viewport_size({"width":390,"height":900})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+2")
                page.screenshot(path=str(evidence/"directory-390.png"))
                context.close();browser.close()
                print(json.dumps({"fixture_only":True,"page":"directory","widths":[1280,390],"height":heights["directory"]}))
                raise SystemExit(0)
            if mode == "browse":
                card=page.locator(".instance-directory-card").filter(has=page.get_by_role("heading",name=instance.title,exact=True))
                card.get_by_role("button",name="查看状态与轨迹",exact=True).click()
                page.wait_for_url("**/instance/"+instance.instance_id)
                assert page.locator("#trajectory").count()==1
                page.locator(".global-navigation .home-button").click()
                page.wait_for_url(base+"/")
                assert page.locator("form[action='/instances/select']").count()==1
                assert runtime.scheduler_bindings.session_instance(session_key=original_session)==instance.instance_id
                assert runtime.scheduler_bindings.session_instance(session_key=other_session)==other.instance_id
                context.close();browser.close()
                print(json.dumps({"fixture_only":True,"directory_to_workbench_to_home":True,"browsing_did_not_rebind":True}))
                raise SystemExit(0)
            # Ownership confirmation is tested separately to bound browser memory.
            page.locator(".global-navigation .home-button").click()
            page.wait_for_url(base+"/")
            # A transfer is a separate visible confirmation, never a browsing side effect.
            form=page.locator("form[action='/instances/select']")
            form.locator("select").select_option(other.name);form.locator("button").click()
            assert page.get_by_role("heading",name="确认科研会话接续").count()==1
            assert runtime.scheduler_bindings.session_instance(session_key=other_session)==other.instance_id
            page.get_by_role("link",name="取消并返回首页").click()
            assert runtime.scheduler_bindings.session_instance(session_key=other_session)==other.instance_id
            form=page.locator("form[action='/instances/select']")
            form.locator("select").select_option(other.name);form.locator("button").click()
            page.get_by_role("button",name="确认接续到当前会话").click()
            page.wait_for_url("**/instance/"+other.instance_id)
            assert runtime.scheduler_bindings.session_instance(session_key=original_session)==other.instance_id
            assert runtime.scheduler_bindings.session_instance(session_key=other_session) is None
            assert fixture.runs.status("navigation.sample").state=="completed"
            assert runtime.approvals.status(launch.approval_id).status=="pending"
            assert not errors,errors
            context.close();browser.close()
            result={"fixture_only":True,"widths":[1280],"heights":heights,"browser_context_preserved":True,"transfer_confirmation":True,
                "cancellation_did_not_rebind":True,"old_task_unchanged":True,"scientific_decision_unchanged":True,
                "javascript_errors":errors}
            (evidence/"BROWSER_TRANSFER.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
            print(json.dumps(result,ensure_ascii=False))
    finally:
        ui.stop()
