"""One small candidate settings page through Chromium/CDP, serial and bounded."""
import base64,json,os,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path
sys.path.insert(0,'/tmp/scid-content-browser-libs')
import websocket
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.approval_ui.app import ApprovalUI
from scidiscovery.artifact_agent.approval_ui.read_model import InstanceReadModel
from scidiscovery.artifact_agent.approval_ui.trajectory import TrajectoryStore
from scidiscovery.artifact_agent.approval_ui.access import management_cookie
from scidiscovery.artifact_agent.service.instance_management import issue_instance_management_capability
from scidiscovery.artifact_agent.service.instance_archive import InstanceArchive

evidence=Path(sys.argv[1]);report={'javascript_errors':[],'http_errors':[]}
with tempfile.TemporaryDirectory(prefix='scid-settings-browser-') as d:
 root=Path(d);project=root/'project';project.mkdir()
 runtime=open_runtime(project_root=project,state_root=root/'state',worker_backend='hardened',approval_receipt_secret=b's'*32)
 instance=runtime.scheduler_bindings.create_instance(name='browser.settings',title='科研实例 · Agent 设置',objective='仅验证配置页面，不开展科学研究')
 model=InstanceReadModel(artifacts=runtime.artifacts,bindings=runtime.scheduler_bindings,runs=runtime.runs,approvals=runtime.approvals,executions=runtime.executions,operation_catalog=runtime.operation_catalog)
 ui=ApprovalUI(runtime.approvals,bindings=runtime.scheduler_bindings,read_model=model,instance_management_secret=b's'*32,trajectory_store=TrajectoryStore(root/'views.sqlite3'),instance_archive=InstanceArchive(runtime),maintenance=runtime.maintenance)
 original_valid_origin=ui._valid_origin
 def observe_origin(origin):
  valid=original_valid_origin(origin);report.setdefault('origin_checks',[]).append({'origin':origin,'accepted':valid});return valid
 ui._valid_origin=observe_origin
 base=ui.start();cookie=management_cookie(issue_instance_management_capability(session_key='sch_'+'a'*32,secret=b's'*32),max_age=3600).split(';')[0]
 env=dict(os.environ);font=Path('/mnt/c/Windows/Fonts/msyh.ttc')
 if font.is_file():
  fonts=root/'fonts';fonts.mkdir();(fonts/font.name).symlink_to(font)
  conf=root/'fonts.conf';conf.write_text(f'<fontconfig><include ignore_missing="yes">/etc/fonts/fonts.conf</include><dir>{fonts}</dir><cachedir>{root}/font-cache</cachedir></fontconfig>');env['FONTCONFIG_FILE']=str(conf)
 chrome=None
 try:
  profile=root/'chrome';profile.mkdir()
  with (root/'chrome.log').open('wb') as log:
   chrome=subprocess.Popen(['/tmp/scid-workbench-browsers/chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell','--headless','--no-sandbox','--no-zygote','--single-process','--disable-gpu','--disable-dev-shm-usage','--remote-debugging-port=0','--user-data-dir='+str(profile),'--js-flags=--max-old-space-size=32','--disable-features=BackForwardCache','about:blank'],stdout=log,stderr=log,env=env)
   deadline=time.monotonic()+10;port_file=profile/'DevToolsActivePort'
   while not port_file.exists():
    assert time.monotonic()<deadline,'browser startup timeout';time.sleep(.1)
   port=port_file.read_text().splitlines()[0]
   with urllib.request.urlopen(f'http://127.0.0.1:{port}/json',timeout=10) as response:target=next(v for v in json.load(response) if v['type']=='page')
   ws=websocket.create_connection(target['webSocketDebuggerUrl'],timeout=15,suppress_origin=True);counter=[0]
   def call(method,params=None):
    counter[0]+=1;ident=counter[0];ws.send(json.dumps({'id':ident,'method':method,'params':params or {}}))
    while True:
     value=json.loads(ws.recv())
     if value.get('method')=='Runtime.exceptionThrown':report['javascript_errors'].append(value['params']['exceptionDetails'].get('text'))
     if value.get('method')=='Network.responseReceived' and value['params']['response']['status']>=400:report['http_errors'].append(value['params']['response']['status'])
     if value.get('id')==ident:
      assert 'error' not in value,value;return value.get('result',{})
   def evaluate(expression):
    value=call('Runtime.evaluate',{'expression':expression,'returnByValue':True})
    assert 'exceptionDetails' not in value,value
    return value['result'].get('value')
   call('Runtime.enable');call('Network.enable');call('Page.enable')
   name,value=cookie.split('=',1);call('Network.setCookie',{'name':name,'value':value,'url':base,'path':'/','httpOnly':True,'sameSite':'Strict'})
   call('Emulation.setDeviceMetricsOverride',{'width':412,'height':915,'deviceScaleFactor':1,'mobile':False})
   call('Page.navigate',{'url':base+'/instances/manage'})
   deadline=time.monotonic()+10
   while not evaluate('Boolean(document.querySelector("input[name=destination][value=settings]"))'):
    assert time.monotonic()<deadline;time.sleep(.1)
   assert evaluate('Boolean(document.querySelector("input[name=destination][value=manage]"))')
   (evidence/'SEPARATE_ENTRIES_MOBILE.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':True})['data']))
   evaluate('document.querySelector("input[name=destination][value=settings]").closest("form").requestSubmit()')
   deadline=time.monotonic()+10
   while not evaluate('Boolean(document.querySelector(".agent-settings-form"))'):
    assert time.monotonic()<deadline;time.sleep(.1)
   assert evaluate('document.documentElement.scrollWidth <= window.innerWidth')
   assert evaluate('!document.querySelector("[name=default_model]").disabled && !document.querySelector(".management-confirm")')
   evaluate('document.querySelector("[name=default_model]").value="gpt-5.6-luna"; document.querySelector("[name=default_narrative_language]").value="zh-CN"; document.querySelector("[name=default_model]").dispatchEvent(new Event("input",{bubbles:true}))')
   preview=evaluate('document.querySelector("[data-settings-preview]").textContent');assert 'gpt-5.6-luna' in preview,preview
   (evidence/'SETTINGS_MOBILE.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':True})['data']))
   evaluate('document.querySelector(".agent-settings-form").requestSubmit(document.querySelector("button[value=save]"))')
   deadline=time.monotonic()+10
   while runtime.scheduler_bindings.agent_settings(instance.instance_id)['revision']!=1:
    if time.monotonic()>=deadline:
     diagnostic=evaluate('({path:location.pathname,text:document.body.innerText.slice(-2000),invalid:[...document.querySelectorAll(":invalid")].map(e=>({name:e.name,message:e.validationMessage}))})')
     print(json.dumps({'save_diagnostic':diagnostic,'events':report},ensure_ascii=False),flush=True)
     raise AssertionError('save timeout')
    time.sleep(.1)
   saved=runtime.scheduler_bindings.agent_settings(instance.instance_id)
   assert saved['settings']['defaults']=={'model':'gpt-5.6-luna','narrative_language':'zh-CN'}
   deadline=time.monotonic()+10
   while not evaluate('location.pathname.endsWith("/settings")'):
    assert time.monotonic()<deadline;time.sleep(.1)
   report.update(separate_entries=True,settings_entry_grants_edit=True,save_returns_to_settings=True,mobile_no_horizontal_overflow=True,change_preview=True,browser_save=True,saved_revision=1,scientific_runs_started=0)
   assert not runtime.runs.active_ids(instance_id=instance.instance_id,limit=10)
   assert not report['javascript_errors'] and not report['http_errors'],report
   ws.close()
 finally:
  if chrome is not None:chrome.terminate();chrome.wait(timeout=10)
  ui.stop()
(evidence/'BROWSER_RESULT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
