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
from types import SimpleNamespace
from html.parser import HTMLParser
import http.cookiejar
from urllib.parse import urlencode, urlsplit
class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.forms=[];self.form=None
    def handle_starttag(self,tag,pairs):
        a=dict(pairs)
        if tag=='form': self.form={'action':a.get('action'),'fields':{}}
        if tag=='input' and self.form is not None and a.get('name'): self.form['fields'][a['name']]=a.get('value','')
    def handle_endtag(self,tag):
        if tag=='form' and self.form is not None:self.forms.append(self.form);self.form=None
mode=sys.argv[1]; evidence=Path(__file__).resolve().parent
access_path=Path('/tmp/scid-content-postinstall-access.json');access=json.loads(access_path.read_text())
url=urlsplit(access['url']);base=url.scheme+'://'+url.netloc
jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
with opener.open(access['url'],timeout=15) as r: html=r.read().decode()
page=Page();page.feed(html)
form=next(f for f in page.forms if f['action']=='/instances/access' and f['fields'].get('scope')=='read')
request=urllib.request.Request(base+form['action'],data=urlencode(form['fields']).encode(),headers={'Origin':base,'Content-Type':'application/x-www-form-urlencoded'})
with opener.open(request,timeout=15) as r:
    instance=SimpleNamespace(instance_id=urlsplit(r.geturl()).path.split('/')[2]);r.read()
cookie='; '.join(c.name+'='+c.value for c in jar)
records=json.loads(Path('/tmp/scid-content-live/records.json').read_text())
references={r['name']:SimpleNamespace(artifact_id=r['view']['artifact_id']) for r in records}
report={'mode':mode,'live_installed_service':True,'instance_name':access['name'],'read_access_posts':1,'scientific_writes':0,'http_errors':[],'javascript_errors':[]}
with tempfile.TemporaryDirectory(prefix='scid-content-live-browser-') as directory:
    directory=Path(directory)
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
            for c in jar: call('Network.setCookie',{'name':c.name,'value':c.value,'url':base})
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
                screenshot('LIVE_curves-1280.png')
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
                screenshot('LIVE_parameters-1280.png')
                href=evaluate("Array.from(document.querySelectorAll('a')).find(e=>e.innerText==='下一页参数').getAttribute('href')")
                navigate(href)
                report['second_page_count']=evaluate("document.querySelector('.parameter-page > p').innerText")
                assert '9–16' in report['second_page_count']
            call('Emulation.setDeviceMetricsOverride',{'width':390,'height':900,'deviceScaleFactor':1,'mobile':False})
            report['mobile_overflow']=evaluate('document.documentElement.scrollWidth>innerWidth+2')
            assert not report['mobile_overflow']
            screenshot('LIVE_'+mode+'-390.png')
            assert not report['http_errors'] and not report['javascript_errors'],report
            report['pass']=True
            ws.close()
    finally:
        if chrome is not None:
            chrome.terminate()
            try: chrome.wait(timeout=5)
            except subprocess.TimeoutExpired: chrome.kill();chrome.wait()
        (evidence/f'LIVE_{mode}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(report,ensure_ascii=False))
