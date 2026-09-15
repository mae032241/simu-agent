"""Browser acceptance against the installed loopback service; no scientific actions."""
import base64,json,os,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path
from urllib.parse import urlsplit
sys.path.insert(0,'/tmp/scid-content-browser-libs')
import websocket
access=json.loads(Path('/tmp/scid-settings-acceptance-access.json').read_text())
evidence=Path(__file__).resolve().parent
url=urlsplit(access['management_url']);base=f'{url.scheme}://{url.netloc}'
report={'instance_name':access['instance_name'],'javascript_errors':[],'http_errors':[]}
with tempfile.TemporaryDirectory(prefix='scid-settings-live-browser-') as directory:
 root=Path(directory);env=dict(os.environ);font=Path('/mnt/c/Windows/Fonts/msyh.ttc')
 if font.is_file():
  fonts=root/'fonts';fonts.mkdir();(fonts/font.name).symlink_to(font)
  conf=root/'fonts.conf';conf.write_text(f'<fontconfig><include ignore_missing="yes">/etc/fonts/fonts.conf</include><dir>{fonts}</dir><cachedir>{root}/font-cache</cachedir></fontconfig>');env['FONTCONFIG_FILE']=str(conf)
 profile=root/'chrome';profile.mkdir();chrome=None
 try:
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
     if value.get('method')=='Network.responseReceived' and value['params']['response']['status']>=400:
      r=value['params']['response'];report['http_errors'].append({'status':r['status'],'path':urlsplit(r['url']).path})
     if value.get('id')==ident:
      assert 'error' not in value,value;return value.get('result',{})
   def evaluate(expression):
    value=call('Runtime.evaluate',{'expression':expression,'returnByValue':True})
    assert 'exceptionDetails' not in value,value
    return value['result'].get('value')
   def until(expression):
    deadline=time.monotonic()+15
    while not evaluate(expression):
     if time.monotonic()>=deadline:
      raise AssertionError({'waiting':expression,'page':evaluate('document.body.innerText.slice(-1600)'),'events':report})
     time.sleep(.1)
   def navigate(path,ready):
    call('Page.navigate',{'url':base+path});until(ready)
   def snapshot():
    return evaluate('Object.fromEntries([...document.querySelectorAll(".agent-settings-form [name^=default_]")].map(e=>[e.name,e.value]))')
   call('Runtime.enable');call('Network.enable');call('Page.enable')
   call('Emulation.setDeviceMetricsOverride',{'width':412,'height':915,'deviceScaleFactor':1,'mobile':False})
   call('Page.navigate',{'url':access['management_url']});until('Boolean(document.querySelector(".home-session"))')
   navigate('/instances/manage','Boolean(document.querySelector(".instance-directory-card"))')
   card='([...document.querySelectorAll(".instance-directory-card")].find(e=>e.textContent.includes("当前会话已绑定")))'
   assert evaluate(card+'?.querySelector("h2").textContent.trim()')==access['title'].strip()
   assert evaluate(card+'.querySelector("input[name=destination][value=manage]") !== null')
   assert evaluate(card+'.querySelector("input[name=destination][value=settings]") !== null')
   evaluate(card+'.scrollIntoView()')
   (evidence/'LIVE_ENTRIES.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',{'format':'png'})['data']))
   evaluate(card+'.querySelector("input[name=destination][value=settings]").closest("form").requestSubmit()')
   until('Boolean(document.querySelector(".agent-settings-form"))')
   assert evaluate('!document.querySelector("[name=default_model]").disabled')
   assert evaluate('document.documentElement.scrollWidth <= innerWidth')
   assert not evaluate('Boolean(document.querySelector(".management-confirm"))')
   settings_path=evaluate('location.pathname');before=snapshot()
   revision=int(evaluate('document.querySelector("[name=expected_revision]").value'))
   effective=evaluate('[...document.querySelectorAll(".agent-setting-field small")].map(e=>e.textContent)')
   report.update(separate_entries=True,settings_editable=True,instance_overrides=before,effective_defaults=effective,revision_before=revision)
   (evidence/'LIVE_SETTINGS.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':True})['data']))
   evaluate('document.querySelector(".agent-settings-form").requestSubmit(document.querySelector("button[value=save]"))')
   until('location.pathname.endsWith("/settings") && document.querySelector("[name=expected_revision]")?.value === '+json.dumps(str(revision+1)))
   assert snapshot()==before
   report.update(unchanged_settings_saved=True,save_returns_to_settings=True,revision_after=revision+1)
   option_names=evaluate('[...document.querySelector("select[name=operation]").options].map(e=>e.value).filter(Boolean)')
   checked=[]
   for operation in ('science.experiment.design.v1','tcad.deck.author.initial.v1'):
    assert operation in option_names
    navigate(settings_path+'?operation='+operation,'Boolean(document.querySelector("[name=operation_model]")) && document.querySelector("[name=operation_id]").value === '+json.dumps(operation))
    assert evaluate('!document.querySelector("[name=operation_model]").disabled && !document.querySelector("[name=operation_reasoning_effort]").disabled')
    checked.append(operation)
   report.update(role_settings_available=checked,operation_option_count=len(option_names))
   navigate(settings_path.removesuffix('/settings')+'/manage','document.body.textContent.includes("当前维护状态")')
   assert not evaluate('Boolean(document.querySelector(".agent-settings-form"))')
   report.update(archive_page_separate=True,mobile_no_horizontal_overflow=True,scientific_actions_invoked=False,archive_actions_invoked=False)
   assert not report['javascript_errors'] and not report['http_errors'],report
   ws.close()
 finally:
  if chrome is not None:chrome.terminate();chrome.wait(timeout=10)
(evidence/'LIVE_RESULT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
