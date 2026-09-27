import copy, hashlib, io, json, os, sys, tempfile, threading
from collections import deque
from pathlib import Path
from types import SimpleNamespace as NS
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote

root=Path.cwd(); fixture_root=Path('/tmp/scid-workbench-real-fixture')
for relative in ('src','plugins/tcad_artifact','plugins/curve_score','plugins/curve_figure_evidence'):
    sys.path.insert(0,str(root/relative))
sys.path.insert(0,'/tmp/scid-workbench-browser')
from playwright.sync_api import sync_playwright
from scidiscovery.artifact_agent.approval_ui import presentation
from scidiscovery.artifact_agent.approval_ui.read_model import InstanceReadModel
from scidiscovery.artifact_agent.approval_ui.workbench_render import render_workbench, render_node
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.artifact_agent.storage import ArtifactNotFoundError, CASObjectMissingError
from scidiscovery.general_science_views import build_presentation as general
from tcad_artifact.instance_views import build_presentation as tcad

data=json.loads((fixture_root/'fixture.json').read_text())
artifacts={a['artifact_id']:a for a in data['artifacts']}
instance=data['overview']['instance']['instance_id']
names={}
for node in data['nodes'].values():
    for item in node.get('inputs',[])+node.get('outputs',[])+node.get('objective_refs',[]):
        if item.get('key'):names[item['artifact_id']]=item['key'].split(':',1)[1]
for a in artifacts.values():
    for p in a.get('provenance',[]):
        if p.get('key'):names[p['artifact_id']]=p['key'].split(':',1)[1]
def ref(value): return ArtifactRef.model_validate(value)
class Artifacts:
    def get_by_id(self,identity):
        if identity not in artifacts:raise ArtifactNotFoundError(identity)
        a=artifacts[identity]
        return NS(artifact_id=identity,ref=ref(a['ref']),schema_id=a['schema_id'],size_bytes=a['size_bytes'],
            media_type=a['media_type'],content_encoding='identity',parent_refs=tuple(ref(p) for p in a['parents']),
            supersedes_ref=ref(a['supersedes']['ref']) if a.get('supersedes') else None,labels={})
    def catalog(self,reference):
        value=self.get_by_id(reference.artifact_id)
        assert value.ref==reference
        return value
    def read(self,reference):
        path=fixture_root/(reference.artifact_id+'.bin')
        if not path.is_file():raise CASObjectMissingError(reference.sha256)
        value=path.read_bytes()
        assert hashlib.sha256(value).hexdigest()==reference.sha256
        return value
class Bindings:
    def get_instance(self,**kwargs):return NS(instance_id=instance)
    def find_name(self,*,instance,namespace,object_id):return names.get(object_id) if namespace=='artifact' else object_id
    def get_binding(self,*,instance,namespace,name):return NS(namespace=namespace,name=name,object_id=namespace+':'+name)
runs={}
for node in data['nodes'].values():
    if node['kind']=='run':
        runs[node['key']]=NS(run_id=node['key'],instance_id=instance,state=node['state'],
            inputs=tuple(NS(port_name=i.get('port_name',''),artifact_ref=ref(i['ref'])) for i in node.get('inputs',[])),
            output_ref=ref(node['outputs'][0]['ref']) if node.get('outputs') else None)
design=json.loads((fixture_root/'design-metadata.json').read_text())
by_name={name:ref(artifacts[identity]['ref']) for identity,name in names.items() if identity in artifacts}
design_inputs=[]
for port in design['bound_inputs']:
    for name in port['artifact_names']:
        if name in by_name:design_inputs.append(NS(port_name=port['port'],artifact_ref=by_name[name]))
assert 'research_objective' in [i.port_name for i in design_inputs]
runs['design']=NS(run_id='design',instance_id=instance,state='completed',inputs=tuple(design_inputs),output_ref=by_name[design['output_artifact_name']])
class Runs:
    def status(self,key):return runs[key]
    def related_runs(self,*,artifact_ref,**kwargs):return tuple(r for r in runs.values() if r.output_ref==artifact_ref)
model=InstanceReadModel(artifacts=Artifacts(),bindings=Bindings(),runs=Runs(),approvals=None,executions=None,operation_catalog=None)
presentation.entry_points=lambda **kwargs:(NS(name='general_science',load=lambda:general),NS(name='tcad_artifact',load=lambda:tcad))
pages={}; checks={}
for label,original in data['nodes'].items():
    node=copy.deepcopy(original)
    if node['kind']=='run':
        context=model.node_context(instance,node['key'])
        binding=model._binding(instance,node['key'])
        objectives,gaps=model._objective_navigation(instance,binding,model._roots(instance,binding))
        node['objective_refs']=objectives;node['gaps']=gaps
    else:
        roots=tuple(ref(i['ref']) for i in node['inputs']+node['outputs'])
        views,gaps=model._lineage_views(instance,roots,presentation=True)
        context={'artifacts':views,'gaps':gaps,'focus_artifact_ids':[r.artifact_id for r in roots]}
        if node.get('request'):
            envelope=model.artifacts.get_by_id(node['request']['artifact_id'])
            node['request']=model._presentation_view(instance,envelope)
    node['objective_records']=[model._artifact_view(instance,model.artifacts.get_by_id(i['artifact_id']),pointer='/statement') for i in node.get('objective_refs',[])[:2]]
    display=presentation.build_presentation(context['artifacts'],focus_artifact_ids=context['focus_artifact_ids'],task_artifact_ids=context.get('task_artifact_ids',[]))
    display['gaps'].extend(context['gaps'])
    pages['/'+label]=render_node(node,instance_id=instance,presentation=display)
    checks[label]={'focus':context['focus_artifact_ids'],'objective_count':len(node.get('objective_refs',[])),
        'context_gaps':[i.get('code') for i in context['gaps']],'node_gaps':[i.get('code') for i in node.get('gaps',[])]}
    if label=='current_review':
        overview=copy.deepcopy(data['overview'])
        overview.update(objective_refs=node['objective_refs'],objective_records=node['objective_records'],gaps=node['gaps'],
            display_node={'key':node['key']},presentation=display)
        pages['/overview']=render_workbench(overview,browse_base='/instance/'+instance,csrf_token='fixture',can_manage=False)
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        path=unquote(urlparse(self.path).path)
        if path in pages:raw=pages[path];media='text/html; charset=utf-8'
        elif path.startswith('/static/'):
            name=path.rsplit('/',1)[-1]
            if name not in ('style.css','workbench.js','app.js'):return self.send_error(404)
            raw=(root/'src/scidiscovery/artifact_agent/approval_ui/static'/name).read_bytes()
            media='text/css' if name.endswith('.css') else 'text/javascript'
        elif '/evidence/' in path:
            identity=path.rsplit('/',1)[-1]
            if identity not in artifacts or not (fixture_root/(identity+'.bin')).is_file():return self.send_error(404)
            raw=(fixture_root/(identity+'.bin')).read_bytes();media=artifacts[identity]['media_type']
        elif path.startswith('/api/') and '/events' in path:
            self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
            self.wfile.write(b'event: nodes\ndata: {"events":[],"cursor":""}\n\n');self.wfile.flush()
            self.server.snapshot_stop.wait(10);return
        elif path.startswith('/api/'):
            raw=b'{"items":[],"gaps":[],"events":[]}';media='application/json'
        else:return self.send_error(404)
        self.send_response(200);self.send_header('Content-Type',media);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_POST(self):self.send_error(405)
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
server.snapshot_stop=threading.Event()
threading.Thread(target=server.serve_forever,daemon=True).start()
base=f'http://127.0.0.1:{server.server_port}'
out=root/'docs/plans/evidence/instance-workbench';errors=[];results=[]
with tempfile.TemporaryDirectory(prefix='workbench-replay-font-') as temporary:
    env=dict(os.environ);font=Path('/mnt/c/Windows/Fonts/msyh.ttc')
    if font.is_file():
        directory=Path(temporary)/'fonts';directory.mkdir();(directory/font.name).symlink_to(font)
        config=Path(temporary)/'fonts.conf';config.write_text(f'<fontconfig><include ignore_missing="yes">/etc/fonts/fonts.conf</include><dir>{directory}</dir><cachedir>{temporary}/cache</cachedir></fontconfig>');env['FONTCONFIG_FILE']=str(config)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,env=env,args=['--no-sandbox','--no-zygote','--single-process','--disable-gpu','--disable-dev-shm-usage','--js-flags=--max-old-space-size=64'])
        context=browser.new_context(viewport={'width':1280,'height':900},locale='zh-CN')
        page=context.new_page();page.set_default_timeout(10000);page.on('pageerror',lambda e:errors.append(str(e)))
        for path in pages:
            assert page.goto(base+path).status==200
            row={'page':path,'height':page.evaluate('document.documentElement.scrollHeight'),
                'default_visible_text':page.locator('body').inner_text()[:3000],
                'wide_fits':page.evaluate('document.documentElement.scrollWidth<=innerWidth+2')}
            page.screenshot(path=str(out/('usability-'+path[1:]+'-wide.png')))
            if path=='/current_review':
                assert page.locator('.conclusion-value strong').first.inner_text()=='通过'
                assert row['height']<=2400,row['height']
            if path=='/failed_run':assert '没有可展示的本节点封存结论' in page.locator('body').inner_text()
            params=page.locator('details.parameters-panel')
            if params.count():
                params.locator(':scope > summary').click()
                params.scroll_into_view_if_needed()
                row['numeric_tokens_unbroken']=params.locator('.value-number').evaluate_all("nodes=>nodes.filter(n=>n.getClientRects().length).every(n=>{const r=document.createRange();r.selectNodeContents(n);return r.getClientRects().length===1})")
                assert row['numeric_tokens_unbroken']
                page.screenshot(path=str(out/('usability-'+path[1:]+'-parameters.png')))
                params.locator(':scope > summary').click()
            figures=page.locator('details.figures-panel')
            if figures.count():
                figures.locator(':scope > summary').click();figures.scroll_into_view_if_needed()
                page.locator('img').first.scroll_into_view_if_needed()
                page.wait_for_function('Array.from(document.images).some(i=>i.complete&&i.naturalWidth>0)')
                row['image_loaded']=True
                page.screenshot(path=str(out/('usability-'+path[1:]+'-figures.png')))
                figures.locator(':scope > summary').click()
            page.set_viewport_size({'width':390,'height':900});page.evaluate('scrollTo(0,0)')
            row['mobile_fits']=page.evaluate('document.documentElement.scrollWidth<=innerWidth+2')
            page.screenshot(path=str(out/('usability-'+path[1:]+'-390.png')))
            page.set_viewport_size({'width':1280,'height':900});results.append(row)
        context.close();browser.close()
server.snapshot_stop.set();server.shutdown();server.server_close()
record={'pages':results,'projection_checks':checks,'javascript_errors':errors,'only_captured_originals':True,
    'sse': 'isolated fixture, no production live-stream claim', 'production_state_read':False,'scientific_execution_started':False}
(out/'USABILITY_REAL_REPLAY.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'pages':[{k:v for k,v in r.items() if k!='default_visible_text'} for r in results],
    'projection_checks':checks,'javascript_errors':errors},ensure_ascii=False))
