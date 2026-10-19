"""Small escaped scientific result presentation, with no state or service imports."""
import base64
import hashlib
import html
import json


CSS = '''
:root{color-scheme:light;font:16px/1.55 system-ui,sans-serif;color:#20343c;background:#f2f5f5}
body{margin:0}main{max-width:1080px;margin:auto;padding:24px}h1{font-size:2rem;line-height:1.2}
h2{font-size:1.2rem}h3{font-size:1rem}nav{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:20px}
a{color:#205c70;text-underline-offset:3px}section,details{background:white;border:1px solid #d9e2e4;
border-radius:10px;padding:18px;margin:16px 0;overflow-wrap:anywhere}summary{cursor:pointer;font-weight:650}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}
.cards section{margin:0}.metric{font:600 1.35rem/1.4 ui-monospace,monospace;overflow-wrap:anywhere}
.note{color:#52666d}.gap{color:#814021}.finding{white-space:pre-wrap;overflow-wrap:anywhere}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.85rem}li{margin:8px 0}
table{border-collapse:collapse;width:100%}td,th{text-align:left;border-bottom:1px solid #e2e7e8;padding:8px}
button{padding:8px 16px;cursor:pointer}form{display:inline-block;margin:8px}textarea{display:block;max-width:100%}
@media(max-width:600px){main{padding:14px}h1{font-size:1.6rem}section,details{padding:14px}}
'''
STYLE_SOURCE = "'sha256-" + base64.b64encode(hashlib.sha256(CSS.encode()).digest()).decode() + "'"
CSP = "default-src 'none'; style-src " + STYLE_SOURCE + "; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"


def escape(value):
    return html.escape(str(value), quote=True)


def page(title, body):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>'+escape(title)
        +'</title><style>'+CSS+'</style></head><body><main><h1>'+escape(title)+'</h1>'
        +body+'</main></body></html>').encode()


def excerpt(value, limit):
    text = value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,allow_nan=False)
    omitted = max(0,len(text)-limit)
    return ('<div class="finding">'+escape(text[:limit])+'</div>'
        + ('<p class="note">'+str(omitted)+' characters omitted; read the complete scientific JSON below.</p>' if omitted else ''))


def result(step, job, payload, seal):
    base='/nodes/'+str(step)
    body=('<nav><a href="/results">Scientific results</a><a href="'+base+'">Node '+str(step)
        +'</a><a href="'+base+'/science">Complete scientific JSON</a><a href="'+base+'/materials">'
        +str(len(seal['materials']))+' sealed deliverables</a></nav>')
    body+='<p class="note">Exact sealed node '+str(step)+' · '+escape(job['role'])+'. Sealing and execution success do not establish scientific acceptance.</p>'
    comparison=((job.get('history') or {}).get('view') or {}).get('candidates')
    comparison=comparison if isinstance(comparison,dict) else {}
    body+='<section><h2>Scientific finding</h2>'+excerpt(payload.get('summary','Not provided'),512)
    body+=excerpt(payload.get('scientific_result',payload.get('summary','Not provided')),4096)+'</section>'
    body+='<div class="cards"><section><h2>Candidate observations</h2><p class="note">Frozen at this node’s input boundary in source order; later evidence is not included. Metrics alone do not establish scientific acceptance.</p>'
    facts=comparison.get('candidate_facts') or []
    for fact in facts:
        body+='<article><h3>'+escape(fact.get('id','Unknown candidate'))+'</h3>'
        body+='<p>Evaluation: '+escape(fact.get('evaluation_key','Unknown evaluation'))+'</p>'
        body+='<p class="metric">'+escape(fact.get('metric','Unknown'))+'</p><p>Direction: '+escape(fact.get('direction','unknown'))+'</p>'
        if fact.get('evaluation_key_truncated'):
            body+='<p class="gap">Evaluation key is shortened in the original frozen summary.</p>'
        body+='</article>'
    if not facts:
        body+='<p class="gap">No candidate facts are displayed in this frozen summary; this does not establish that no candidates exist.</p>'
    if comparison.get('candidate_facts_omitted_count'):
        body+='<p class="gap">'+str(comparison['candidate_facts_omitted_count'])+' candidate facts omitted in the frozen summary. Read the complete original conclusions.</p>'
    body+='<p>Observation coverage: '+escape(comparison.get('coverage','unknown'))+'</p></section>'
    body+='<section><h2>Scientific recommendation</h2>'
    ordinary_a=job['role']=='A' and not job.get('formal_review') and payload.get('next_action')!='audit'
    recommended=payload.get('candidate_recommendation') if ordinary_a else None
    if ordinary_a:
        body+=('<p>This sealed A recommends: <strong>'+escape(recommended)+'</strong></p>' if recommended is not None else
            '<p class="gap">This sealed A makes no candidate recommendation. An earlier recommendation is not substituted.</p>')
    else:
        body+='<p class="gap">This node is not an ordinary A recommendation.</p>'
    previous=comparison.get('a_recommended')
    if previous:
        body+='<details><summary>Earlier A recommendation at the input boundary</summary><p>A'+escape(previous['author_step'])+': '+escape(previous['candidate_id'])+'</p></details>'
    body+='<p class="note">An authored recommendation is separate from observed metrics, delivery and formal review. This display grants no execution permission.</p></section></div>'
    body+='<details><summary>Limitations and remaining question</summary>'
    limits=payload.get('limitations') or []
    for value in limits[:6]:body+=excerpt(value,1200)
    if len(limits)>6:body+='<p>'+str(len(limits)-6)+' limitations omitted; read the complete scientific JSON.</p>'
    if not limits:body+='<p>No limitations were supplied in this scientific original.</p>'
    if payload.get('remaining_question') is not None:body+='<h3>Remaining question</h3>'+excerpt(payload['remaining_question'],2048)
    body+='</details>'
    fields=('scope','coverage','candidate_count','latest_a_step','view_status',
        'candidate_facts_omitted_count','audits_omitted_count',
        'failed_candidate_count','unknown_candidate_count','candidate_alerts','candidate_alerts_omitted_count',
        'public_audits','limitation')
    public={key:comparison[key] for key in fields if key in comparison}
    body+='<details><summary>Frozen comparison scope and omissions</summary><pre>'+escape(json.dumps(public,ensure_ascii=False,indent=2))+'</pre>'
    body+='<p class="note">Omitted details are not absent facts. Complete scientific conclusions and deliverables remain at their exact node links.</p></details>'
    return page('Scientific result · Node '+str(step),body)
