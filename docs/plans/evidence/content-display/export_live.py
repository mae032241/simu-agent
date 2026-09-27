"""Freeze authorized UI originals for isolated display replay; no science writes."""
from html.parser import HTMLParser
import hashlib
import http.cookiejar
import json
from pathlib import Path
import sys
from urllib.parse import urlencode, urlsplit, quote
import urllib.request

class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.forms=[]; self.form=None; self.links=[]
    def handle_starttag(self, tag, pairs):
        attrs=dict(pairs)
        if tag=='form': self.form={'action':attrs.get('action'),'fields':{}}
        if tag=='input' and self.form is not None and attrs.get('name'):
            self.form['fields'][attrs['name']]=attrs.get('value','')
        if tag=='a' and attrs.get('href'): self.links.append(attrs['href'])
    def handle_endtag(self, tag):
        if tag=='form' and self.form is not None: self.forms.append(self.form); self.form=None

access_path=Path(sys.argv[1]); access=json.loads(access_path.read_text())
url=urlsplit(access['url']); base=url.scheme+'://'+url.netloc
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
out=Path('/tmp/scid-content-live');out.mkdir(exist_ok=True)
def read(path, form=None):
    request=urllib.request.Request(path if path.startswith('http') else base+path,
        data=urlencode(form).encode() if form is not None else None,
        headers={'Origin':base,'Content-Type':'application/x-www-form-urlencoded'} if form is not None else {})
    with opener.open(request,timeout=15) as response:
        raw=response.read(4*1024*1024+1)
        if len(raw)>4*1024*1024: raise ValueError('read bound exceeded')
        return raw,response.geturl()
try:
    home=Page(); home.feed(read(access['url'])[0].decode())
    form=next(f for f in home.forms if f['action']=='/instances/access' and f['fields'].get('scope')=='read')
    raw,location=read(form['action'],form['fields']);page=Page();page.feed(raw.decode())
    instance=urlsplit(location).path.split('/')[2]; records=[]
    for catalog in access['catalogs']:
        raw,_=read('/api/instances/'+instance+'/nodes/'+quote('artifact:'+catalog['name'],safe=''))
        node=json.loads(raw); identity=node['artifact_id']
        original,_=read('/instance/'+instance+'/evidence/'+identity+'?format=download')
        assert len(original)==catalog['size_bytes']
        sha=hashlib.sha256(original).hexdigest(); assert sha==node['ref']['sha256']
        (out/identity).write_bytes(original)
        records.append({'name':catalog['name'],'catalog':catalog,'view':node,'sha256':sha})
    plans=[]
    for href in page.links:
        if '/evidence/' not in href or not ('variables' in href or 'settings' in href): continue
        identity=urlsplit(href).path.split('/')[-1]
        if identity in plans: continue
        plans.append(identity)
        raw,_=read('/api/instances/'+instance+'/evidence/'+identity)
        node=json.loads(raw)
        original,_=read('/instance/'+instance+'/evidence/'+identity+'?format=download')
        assert hashlib.sha256(original).hexdigest()==node['ref']['sha256']
        (out/identity).write_bytes(original)
        records.append({'name':'visible_plan_'+str(len(plans)),'view':node,'sha256':node['ref']['sha256']})
        if len(plans)>=2: break
    (out/'records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
    summary={'instance_name':access['name'],'read_access_posts':1,'scientific_writes':0,'records':[
        {'name':r['name'],'schema':r['view']['schema_id'],'bytes':r['view']['size_bytes'],'sha256':r['sha256']} for r in records]}
    Path(__file__).with_name('LIVE_ORIGINALS.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False))
finally:
    access_path.unlink(missing_ok=True)
