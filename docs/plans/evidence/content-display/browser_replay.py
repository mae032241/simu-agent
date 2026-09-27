"""Render authorized Fig.4 payload copies through candidate HTTP UI in isolated state."""
import base64
import subprocess
import time
import urllib.request
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from urllib.parse import quote

sys.path.insert(0, '/tmp/scid-content-browser-libs')
import websocket
from scidiscovery.artifact_agent.service.artifacts import ArtifactService
from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
from scidiscovery.artifact_agent.service.approvals import ApprovalService
from scidiscovery.artifact_agent.schema.refs import ActorRef
from scidiscovery.artifact_agent.approval_ui import presentation
from scidiscovery.artifact_agent.approval_ui.app import ApprovalUI
from scidiscovery.artifact_agent.approval_ui.access import access_cookie
from scidiscovery.artifact_agent.approval_ui.read_model import InstanceReadModel
from scidiscovery.artifact_agent.approval_ui.trajectory import TrajectoryStore
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.general_science_views import build_presentation as general
from tcad_artifact.instance_views import build_presentation as tcad
from curve_figure_evidence.instance_views import build_presentation as figure

mode=sys.argv[1]; evidence=Path(__file__).resolve().parent
saved=Path('/tmp/scid-content-live');records=json.loads((saved/'records.json').read_text())
# Source-mode replay: real installed registration is separately tested with wheels.
presentation.entry_points=lambda **_: tuple(SimpleNamespace(name=name,load=lambda p=p:p) for name,p in
    (('general',general),('tcad',tcad),('figure',figure)))
report={'mode':mode,'source_payloads_exact':True,'isolated_control_bindings':True,'production_scientific_writes':0,
    'http_errors':[],'javascript_errors':[]}
with tempfile.TemporaryDirectory(prefix='scid-content-browser-') as directory:
    directory=Path(directory);project=directory/'project';project.mkdir()
    actor=ActorRef(actor_id="display-replay",actor_type="service")
    artifacts=ArtifactService.open(cas_root=directory/'cas',database_path=directory/'artifacts.sqlite3')
    bindings=SchedulerBindingService(directory/'bindings.sqlite3')
    approvals=ApprovalService(artifacts=artifacts,database_path=directory/'approvals.sqlite3',service_actor=actor,receipt_secret=b's'*32)
    runtime=SimpleNamespace(artifacts=artifacts,scheduler_bindings=bindings,approvals=approvals,
        actor=actor,runs=None,executions=None,operation_catalog=None)
    instance=runtime.scheduler_bindings.create_instance(name='fig4.display.replay',title='Fig.4 原始资料展示回放',objective='仅验证显示；不重新判定科学结果。')
    references={}
    for r in records:
        original=r['view'];raw=(saved/original['artifact_id']).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==r['sha256']
        catalog=r.get('catalog',{}); labels=catalog.get('labels',{})
        item=runtime.artifacts.register(raw,ArtifactRegistration(kind=original['ref']['kind'],schema_id=original['schema_id'],
            payload_schema_version=1,media_type=original['media_type'],creator=runtime.actor,labels=labels),idempotency_key=r['name'])
        runtime.scheduler_bindings.bind(instance=instance.instance_id,namespace='artifact',name=r['name'],object_id=item.artifact_id,
            request_fingerprint=labels.get('operation_invocation_fingerprint'))
        references[r['name']]=item
    model=InstanceReadModel(artifacts=runtime.artifacts,bindings=runtime.scheduler_bindings,runs=runtime.runs,
        approvals=runtime.approvals,executions=runtime.executions,operation_catalog=runtime.operation_catalog)
    ui=ApprovalUI(runtime.approvals,bindings=runtime.scheduler_bindings,read_model=model,instance_management_secret=b's'*32,trajectory_store=TrajectoryStore(directory/'workbench.sqlite3'))
    base=ui.start(); cookie=access_cookie(instance.instance_id,ui.browser_access.issue(instance.instance_id)).split(';')[0]
    env=dict(os.environ);font=Path('/mnt/c/Windows/Fonts/msyh.ttc')
    if font.is_file():
        fonts=directory/'fonts';fonts.mkdir();(fonts/font.name).symlink_to(font)
        config=directory/'fonts.conf';config.write_text(f"<fontconfig><include ignore_missing='yes'>/etc/fonts/fonts.conf</include><dir>{fonts}</dir><cachedir>{directory}/font-cache</cachedir></fontconfig>")
        env['FONTCONFIG_FILE']=str(config)
    chrome=None
    try:
        profile=directory/'chrome';profile.mkdir()
        with (directory/'chrome.log').open('wb') as log:
            chrome=subprocess.Popen(['/tmp/scid-workbench-browsers/chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell',
                '--headless','--no-sandbox','--no-zygote','--single-process','--disable-gpu','--disable-dev-shm-usage',
                '--remote-debugging-port=0','--user-data-dir='+str(profile),'--js-flags=--max-old-space-size=32',
                '--disable-features=BackForwardCache','about:blank'],stdout=log,stderr=log,env=env)
            port_file=profile/'DevToolsActivePort'
            deadline=time.monotonic()+10
            while not port_file.exists():
                assert time.monotonic()<deadline, 'Chromium startup timeout'
                time.sleep(.1)
            port=port_file.read_text().splitlines()[0]
            with urllib.request.urlopen('http://127.0.0.1:'+port+'/json',timeout=10) as response:
                target=next(v for v in json.load(response) if v['type']=='page')
            ws=websocket.create_connection(target['webSocketDebuggerUrl'],timeout=15,suppress_origin=True)
            def call(method,params=None):
                counter_box[0]+=1;ident=counter_box[0]
                ws.send(json.dumps({'id':ident,'method':method,'params':params or {}}))
                while True:
                    message=json.loads(ws.recv())
                    if message.get('method')=='Network.responseReceived':
                        r=message['params']['response']
                        if r['status']>=400: report['http_errors'].append({'url':r['url'].split('?')[0],'status':r['status']})
                    if message.get('method')=='Runtime.exceptionThrown':
                        report['javascript_errors'].append(message['params']['exceptionDetails'].get('text'))
                    if message.get('id')==ident:
                        assert 'error' not in message,message
                        return message.get('result',{})
            counter_box=[0]
            def evaluate(expression):
                value=call('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
                assert 'exceptionDetails' not in value,value
                return value['result'].get('value')
            def navigate(path):
                call('Page.navigate',{'url':base+path})
                deadline=time.monotonic()+10
                while True:
                    if evaluate('document.readyState')=='complete' and evaluate('location.pathname')==path.split('?')[0]: break
                    assert time.monotonic()<deadline,'page load timeout'
                    time.sleep(.1)
            def screenshot(name):
                value=call('Page.captureScreenshot',{'format':'png'})
                (evidence/name).write_bytes(base64.b64decode(value['data']))
            call('Page.enable');call('Network.enable');call('Runtime.enable')
            key,value=cookie.split('=',1);call('Network.setCookie',{'name':key,'value':value,'url':base})
            call('Emulation.setDeviceMetricsOverride',{'width':1280,'height':900,'deviceScaleFactor':1,'mobile':False})
            if mode=='curves':
                path='/instance/'+instance.instance_id+'/nodes/'+quote('artifact:fig4_continuation_figure_materialized_1',safe='')
                navigate(path)
                assert evaluate("document.querySelectorAll('.figure-card img').length")==3
                evaluate("Promise.all(Array.from(document.querySelectorAll('.figure-card img')).map(async e=>{e.loading='eager';await e.decode();return e.naturalWidth;}))")
                report['image_labels']=evaluate("Array.from(document.querySelectorAll('.figure-card figcaption')).map(e=>e.innerText)")
                report['default_height']=evaluate('document.documentElement.scrollHeight')
                assert report['default_height']<=2400,report
                evaluate("document.querySelector('.figures-panel').scrollIntoView()")
                screenshot('curves-1280.png')
                evaluate("document.querySelector('.curve-evidence-panel').open=true")
                hrefs=evaluate("Array.from(document.querySelectorAll('.csv-download')).map(e=>e.getAttribute('href'))")
                assert len(hrefs)==2
                for href in hrefs:
                    req=urllib.request.Request(base+href,headers={'Cookie':cookie})
                    with urllib.request.urlopen(req,timeout=10) as response:
                        report.setdefault('csv_sha256',[]).append(hashlib.sha256(response.read()).hexdigest())
                assert set(report['csv_sha256'])=={r['sha256'] for r in records if r['view']['media_type']=='text/csv'}
            else:
                original=references['visible_plan_1']
                path=f'/instance/{instance.instance_id}/evidence/{original.artifact_id}?view=parameters'
                navigate(path)
                text=evaluate('document.body.innerText')
                assert '来源未记录/是否默认未知' not in text and '实验设计取值' in text
                report['first_page_count']=evaluate("document.querySelector('.parameter-page > p').innerText")
                evaluate("document.querySelector('.parameter-detail').open=true")
                report['first_detail']=evaluate("document.querySelector('.parameter-detail[open]').innerText")
                assert '变量类型' in report['first_detail'] and '物理参数' in report['first_detail'] and '对照角色：预期变化' in report['first_detail']
                screenshot('parameters-1280.png')
                href=evaluate("Array.from(document.querySelectorAll('a')).find(e=>e.innerText==='下一页参数').getAttribute('href')")
                navigate(href)
                report['second_page_count']=evaluate("document.querySelector('.parameter-page > p').innerText")
                assert '9–16' in report['second_page_count']
            call('Emulation.setDeviceMetricsOverride',{'width':390,'height':900,'deviceScaleFactor':1,'mobile':False})
            report['mobile_overflow']=evaluate('document.documentElement.scrollWidth>innerWidth+2')
            assert not report['mobile_overflow']
            screenshot(mode+'-390.png')
            assert not report['http_errors'] and not report['javascript_errors'],report
            report['pass']=True
            ws.close()
    finally:
        if chrome is not None:
            chrome.terminate()
            try: chrome.wait(timeout=5)
            except subprocess.TimeoutExpired: chrome.kill();chrome.wait()
        ui.stop()
        (evidence/f'BROWSER_{mode}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(report,ensure_ascii=False))
