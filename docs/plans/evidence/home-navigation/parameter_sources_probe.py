"""Bounded, read-only provenance inspection through the installed HTTP UI."""
from collections import Counter
from html.parser import HTMLParser
import http.cookiejar
import json
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlencode, urlsplit
import urllib.request

class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.forms=[]; self.form=None; self.rows=[]; self.row=None; self.depth=0; self.headers=[]; self.in_th=False
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='form': self.form={'action':attrs.get('action'),'fields':{}}
        if tag=='input' and self.form is not None and attrs.get('name'):
            self.form['fields'][attrs['name']]=attrs.get('value','')
        if tag=='tr':
            if self.depth==0: self.row={'name':'','text':[],'links':[]}
            self.depth+=1
        if self.row is not None:
            if tag=='th': self.in_th=True
            if tag=='a' and attrs.get('href'): self.row['links'].append(attrs['href'])
    def handle_endtag(self,tag):
        if tag=='form' and self.form is not None: self.forms.append(self.form); self.form=None
        if tag=='th': self.in_th=False
        if tag=='tr' and self.depth:
            self.depth-=1
            if not self.depth: self.rows.append(self.row); self.row=None
    def handle_data(self,text):
        if self.row is not None:
            self.row['text'].append(text)
            if self.in_th: self.row['name']+=text

access_path=Path(sys.argv[1]); access=json.loads(access_path.read_text())
url=urlsplit(access['url']); base=url.scheme+'://'+url.netloc
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def read(path,form=None):
    request=urllib.request.Request(path if path.startswith('http') else base+path,
        data=urlencode(form).encode() if form is not None else None,
        headers={'Origin':base,'Content-Type':'application/x-www-form-urlencoded'} if form is not None else {})
    with opener.open(request,timeout=15) as response:
        raw=response.read(1024*1024+1)
        if len(raw)>1024*1024: raise ValueError('probe response exceeds 1 MiB')
        return raw.decode(), response.geturl()
try:
    home=Page(); home.feed(read(access['url'])[0])
    form=next(f for f in home.forms if f['action']=='/instances/access' and f['fields'].get('scope')=='read')
    raw,location=read(form['action'],form['fields']); page=Page(); page.feed(raw)
    rows=[r for r in page.rows if r['name'] and r['links']]
    evidence=[]; counts=Counter(); details=Counter()
    for row in rows:
        path=next((p for p in row['links'] if '/evidence/' in p),None)
        if not path: continue
        parsed=urlsplit(path); pointer=parse_qs(parsed.query).get('pointer',[''])[0]
        category='comparison_variable' if '/variables/' in pointer else 'case_setting' if '/settings/' in pointer else 'parameter_claim' if '/claims/' in pointer else 'implementation_binding' if 'parameter_bindings/' in pointer else 'other'
        counts[category]+=1
        text=' '.join(row['text'])
        details['source_unknown_rows']+=int('来源未记录/是否默认未知' in text)
        details['acquisition_unknown_rows']+=int('获得方式未记录' in text)
        details['ascii_parameter_names']+=int(row['name'].isascii())
        if len(evidence)>=6 or (sum(item['category']==category for item in evidence)>=3): continue
        pieces=parsed.path.split('/')
        api='/api/instances/'+pieces[2]+'/evidence/'+pieces[4]+'?'+urlencode({'pointer':pointer})
        source=json.loads(read(api)[0]); payload=source.get('payload')
        evidence.append({'name':row['name'],'category':category,'schema_id':source.get('schema_id'),
            'json_pointer':pointer,'payload_state':source.get('payload_state'),
            'original_keys':sorted(payload) if isinstance(payload,dict) else [],
            'has_rationale':bool(payload.get('rationale')) if isinstance(payload,dict) else None,
            'has_epistemic_status':'epistemic_status' in payload if isinstance(payload,dict) else None,
            'has_direct_citation':any(k in payload for k in ('sources','source_key','evidence_keys','evidence_class')) if isinstance(payload,dict) else None})
    result={'instance':access['name'],'parameter_rows':len(rows),'categories':dict(counts),'display_counts':dict(details),
        'original_source_samples':evidence,'read_access_posts':1,'scientific_writes':0}
    target=Path(__file__).with_name('PARAMETER_SOURCE_DIAGNOSIS.json')
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))
finally:
    access_path.unlink(missing_ok=True)
