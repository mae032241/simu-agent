"""Real browser submission, isolated synthetic approval only; never production."""
import sys, tempfile, json, os, http.client
from pathlib import Path
from urllib.parse import urlparse, urlencode
for p in ('src','plugins/tcad_artifact','plugins/curve_score','plugins/curve_figure_evidence','.'):
    sys.path.insert(0,str(Path(p).resolve()))
if os.environ.get('SCID_BROWSER_PYTHONPATH'):
    sys.path.append(os.environ['SCID_BROWSER_PYTHONPATH'])
from playwright.sync_api import sync_playwright
from tests.operations.test_instance_read_model import system,artifact
from scidiscovery.artifact_agent.approval_ui.app import ApprovalUI
from scidiscovery.artifact_agent.schema.approval import ApprovalOption
class TraceUI(ApprovalUI):
    def _error(self,handler,status,*args,**kwargs):
        ex=sys.exc_info()[1]
        print(json.dumps({'http_error':int(status),'cause':str(ex) if ex else None,'origin':handler.headers.get('Origin')},ensure_ascii=False),flush=True)
        return super()._error(handler,status,*args,**kwargs)
with tempfile.TemporaryDirectory(prefix='scid-approval-post-') as tmp:
    s=system.__wrapped__(Path(tmp))
    obj=artifact(s,'synthetic_subject',instance=s.a)
    opts=tuple(ApprovalOption(option_id=k,label=v,description='Isolated fixture only',requires_rationale=False) for k,v in [('authorize_execution','授权执行'),('reject_execution','拒绝执行')])
    launch=s.approvals.create_request(approval_id='synthetic_execution',kind='execution_authorization',subject_refs=(obj.ref,),question='Synthetic UI test only',options=opts,requested_by=s.actor,idempotency_key='synthetic')
    s.bindings.bind(instance=s.a,namespace='approval',name='synthetic',object_id=launch.approval_id)
    ui=TraceUI(s.approvals,port=0,bindings=s.bindings,read_model=s.model,instance_management_secret=b'x'*32)
    base=ui.start()
    assert urlparse(base).port != 8765
    try:
      with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=['--no-sandbox','--no-zygote','--single-process','--disable-gpu','--disable-dev-shm-usage','--js-flags=--max-old-space-size=64'])
        page=browser.new_page(java_script_enabled='--no-js' not in sys.argv)
        origins=[]
        page.on('request',lambda r: origins.append(r.headers.get('origin')) if r.url.endswith('/decision') else None)
        page.on('response',lambda r: print(json.dumps({'response_status':r.status,'path':r.url.split('?')[0]}),flush=True) if '/decision' in r.url else None)
        response=page.goto(base+launch.review_path)
        assert response.status == 200
        assert response.headers['referrer-policy']=='same-origin'
        form=page.locator('form[action$="/decision"]').evaluate('(f) => Object.fromEntries(new FormData(f))')
        form['selected_option']='authorize_execution'
        endpoint=urlparse(base)
        for origin in (None,'null','http://example.invalid',base):
            headers={'Content-Type':'application/x-www-form-urlencoded'}
            if origin is not None: headers['Origin']=origin
            values={**form,'csrf':'invalid'} if origin==base else form
            connection=http.client.HTTPConnection(endpoint.hostname,endpoint.port,timeout=5)
            connection.request('POST',f'/review/{launch.approval_id}/decision',body=urlencode(values),headers=headers)
            rejected=connection.getresponse()
            assert rejected.status==403
            rejected.read();connection.close()
            assert s.approvals.status(launch.approval_id).status=='pending'
        page.locator('input[value="authorize_execution"]').check()
        with page.expect_navigation(): page.locator('button.submit-decision').click()
        assert origins==[base], origins
        assert s.approvals.status(launch.approval_id).status=='decided'
        print(json.dumps({'final_url':page.url.split('?')[0],'status':s.approvals.status(launch.approval_id).status},ensure_ascii=False),flush=True)
        browser.close()
    finally: ui.stop()
