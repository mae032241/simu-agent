"""Small escaped scientific result presentation, with no state or service imports."""
import base64
import hashlib
import html
import json

from .configuration_form import SCRIPT_CSP as CONFIG_SCRIPT_CSP


CSS = '''
:root{color-scheme:light;font:16px/1.65 system-ui,-apple-system,"Noto Sans CJK SC","Microsoft YaHei",sans-serif;color:#263c43;background:#f5f7f8;font-synthesis:none}
*{box-sizing:border-box}[hidden]{display:none!important}body{margin:0}main{max-width:1120px;margin:auto;padding:28px 36px 72px}
.app-brand{display:flex;align-items:center;gap:10px;padding-bottom:25px;margin-bottom:26px;border-bottom:1px solid #dce4e6;color:#244c4d;font-size:.85rem;font-weight:750;letter-spacing:.04em}.brand-mark{width:26px;height:26px;display:inline-grid;place-items:center;border-radius:8px;background:#176b5b;color:#fff;font-size:.9rem}.brand-caption{margin-left:auto;color:#718086;font-weight:450;letter-spacing:0}
h1{margin:0 0 15px;font-size:2rem;line-height:1.35;letter-spacing:-.035em;color:#203b40}h2{font-size:1.35rem;line-height:1.45;margin:0 0 12px}h3{font-size:1rem;margin:24px 0 8px}p{margin:10px 0 16px}nav{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:24px}a{color:#236653;text-underline-offset:4px}nav a{font-size:.9rem;font-weight:600}
section,details{background:white;border:1px solid #dce4e6;border-radius:14px;padding:24px;margin:20px 0;overflow-wrap:anywhere}summary{cursor:pointer;font-weight:650;line-height:1.65}summary::marker{color:#7b8e91}details[open]>summary{margin-bottom:16px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:20px}.cards section{margin:0}.cards p{margin:8px 0 20px}.metric{font:600 1.35rem/1.4 ui-monospace,monospace;overflow-wrap:anywhere}.note{color:#66797e;font-size:.9rem}.gap{color:#814021}.finding{white-space:pre-wrap;overflow-wrap:anywhere}.badge{display:inline-block;padding:3px 10px;background:#e6f1ed;border-radius:20px}.hero{border-left:5px solid #176b5b}.empty{text-align:center;padding:28px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.82rem}code{overflow-wrap:anywhere;font-size:.85em}li{margin:8px 0}table{border-collapse:collapse;width:100%}td,th{text-align:left;border-bottom:1px solid #e4e9eb;padding:12px;vertical-align:top}th{font-weight:600}
button,.primary{display:inline-block;padding:12px 22px;border:1px solid transparent;border-radius:9px;background:#176b5b;color:white;font:inherit;font-size:.95rem;font-weight:650;cursor:pointer;text-decoration:none;line-height:1.5;transition:background .15s}button:hover,.primary:hover{background:#105346}button:disabled{opacity:.5;cursor:default}.secondary-button,.secondary button{background:#fff;border:1px solid #cbd8da;color:#38575d}.secondary-button:hover,.secondary button:hover{background:#eef4f3}button:focus-visible,a:focus-visible,summary:focus-visible{outline:3px solid #8cbab0;outline-offset:4px}form{margin:16px 0}label{display:block;margin:16px 0 8px;font-size:.94rem;font-weight:650}input,select,textarea{font:inherit;font-size:.95rem;padding:11px 13px;border:1px solid #b9c9ce;border-radius:8px;background:#fff;color:#203b40;max-width:100%}input:not([type=checkbox]):not([type=hidden]),select,textarea{display:block;width:100%}input::placeholder,textarea::placeholder{color:#8a999e}input:focus,select:focus,textarea:focus{outline:3px solid #dfefea;border-color:#4b907c}textarea{min-height:100px;resize:vertical}input[type=checkbox]{accent-color:#176b5b;vertical-align:middle;margin-right:8px}.check-label{font-weight:450}.event{padding:12px 0;border-bottom:1px solid #e2e7e8}.event:last-child{border:0}.event p{white-space:pre-wrap;margin:5px 0}.steps{display:flex;gap:10px;flex-wrap:wrap;padding:0;list-style:none}.steps li{padding:8px 12px;border-radius:6px;background:#e0ede8}
.connection{font-size:.8rem;color:#5d7875;margin:0 0 18px}.connection[data-state=offline]{color:#946027}.setup-intro{color:#62777e;max-width:800px;margin-bottom:26px}.setup-nav{margin:0 0 18px}.setup-flow{max-width:940px}.setup-progress{display:grid;grid-template-columns:repeat(3,1fr);list-style:none;margin:28px 0 25px;padding:0;border-bottom:1px solid #d8e3e5}.setup-progress li{position:relative;display:flex;gap:10px;align-items:center;padding:0 0 20px;margin:0;color:#7d8e93;font-size:.95rem;font-weight:550}.setup-progress li span{display:grid;place-items:center;width:29px;height:29px;background:#e9edef;border-radius:50%;font-size:.85rem}.setup-progress li.is-current{color:#176b5b;font-weight:750}.setup-progress li.is-current:after{position:absolute;bottom:-1px;left:0;width:90%;height:3px;background:#176b5b;content:"";border-radius:3px}.setup-progress li.is-current span{background:#176b5b;color:white}.setup-progress li.is-complete span{background:#dcece6;color:#176b5b}
.setup-panel{padding:32px 38px;margin:0;box-shadow:0 8px 30px #223a4010}.section-heading{max-width:760px;margin-bottom:24px}.eyebrow{display:block;font-size:.75rem;letter-spacing:.08em;color:#64877d;font-weight:750;margin-bottom:9px}.section-heading h2{font-size:1.55rem;letter-spacing:-.025em;margin-bottom:10px}.section-heading p{font-size:.92rem;color:#62777e;margin:0}.section-heading h2:focus{outline:none}.config-field{min-width:0;margin:24px 0}.config-field>label{margin:0 0 9px}.required-mark{display:inline-block;color:#6c827c;background:#edf4f1;border-radius:4px;padding:1px 6px;font-size:.67rem;line-height:1.5;margin-left:6px;font-weight:500;vertical-align:middle}.field-help{display:block;color:#687e83;font-size:.81rem;font-weight:400;margin-top:9px;line-height:1.7;max-width:750px}.field-error{margin:8px 0;color:#a2542c;font-size:.82rem}.field-key{display:block;font:400 .72rem/1.6 ui-monospace,monospace;color:#84969b;overflow-wrap:anywhere;margin-top:4px}.task-mode{max-width:320px;margin-bottom:22px}.config-field textarea[name=task_text]{min-height:170px}.path-heading{border-top:1px solid #e7ecee;padding-top:3px;margin-top:30px}.path-heading h3{font-size:1.05rem;margin-bottom:4px}.path-heading .note{margin-top:0}.path-base{color:#7b8c91;font-size:.78rem;margin:23px 0 0;padding:0;border:0;background:transparent}.path-base>summary{font-weight:450}.path-base p{font-size:.76rem;margin:10px 0 0}.path-base code{display:block;margin-top:6px}.setup-actions{display:flex;align-items:center;justify-content:space-between;gap:18px;flex-wrap:wrap;margin-top:30px;padding-top:23px;border-top:1px solid #e5ebec}.setup-actions>.note{font-size:.8rem;margin:0}.setup-actions form{margin:0}.setup-check{display:block;margin:22px 0 0 auto}.model-fields{display:grid;grid-template-columns:2fr 1fr 1fr;gap:20px}.model-fields .config-field,.budget-fields .config-field{margin:4px 0 20px}.subsection-title{margin:16px 0 18px;padding-top:22px;border-top:1px solid #e5ebec}.budget-fields{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}.summary-note{display:inline-block;margin-left:14px;color:#809297;font-size:.78rem;font-weight:400}.permission-settings,.advanced-settings{background:#fafcfc;border-radius:10px;padding:19px 22px;margin:20px 0 0}.permission-settings .config-field{margin:18px 0}.advanced-category,.structured-setting{border-radius:8px;padding:16px 20px;margin:12px 0;background:white}.advanced-category>summary{font-size:.9rem}.advanced-category .note{font-size:.8rem}.config-node{padding:15px;border:1px solid #dce5e8;border-radius:8px;margin:12px 0;background:#f9fbfb}.config-node label{font-size:.8rem;margin:10px 0}.config-node button,.config-string-row button,.advanced-category button{font-size:.78rem;padding:7px 12px}.config-node .config-children{margin-left:14px}.config-string-row{display:flex;align-items:start;gap:10px;margin:10px 0}.config-string-row textarea{min-height:46px}.config-string-row button{flex-shrink:0}.setup-tools{padding:18px 24px;margin:24px 0 0;background:transparent;border-style:dashed}.setup-tools>summary{font-size:.88rem;color:#607b7d}.tools-grid{display:grid;grid-template-columns:1fr 1fr;gap:28px}.tools-grid>div{min-width:0}.tools-grid h3{margin:8px 0}.tools-grid button{font-size:.8rem;padding:9px 14px}.tools-grid label{font-size:.81rem}.tools-grid input{font-size:.82rem}.setup-notice,#config-edited-note{padding:17px 22px;border:1px solid #dfba83;background:#fff8ed;color:#865718;border-radius:10px;font-size:.9rem}.import-notice{padding:13px 18px;border:1px solid #c7dfd5;background:#edf6f0;color:#466b5a;border-radius:9px;font-size:.82rem}.review-summary{margin:26px 0;display:grid;grid-template-columns:1fr 1fr;gap:0 28px}.review-summary>div{padding:15px 0;border-bottom:1px solid #e5ebed;min-width:0}.review-summary dt{font-size:.8rem;color:#6c8388;margin-bottom:5px}.review-summary dd{margin:0;font-size:.95rem;font-weight:600;overflow-wrap:anywhere}.review-path{font-size:.9rem;font-weight:550}.review-full-path{padding:0;margin:7px 0 0;border:0;background:transparent;border-radius:0;color:#71868c;font-size:.73rem;font-weight:400}.review-full-path>summary{font-weight:450}.review-full-path[open]>summary{margin-bottom:7px}.review-full-path code{display:block;font-size:.72rem;font-weight:400;color:#6e8187;line-height:1.65}.confirmation>.finding{padding:19px 22px;background:#f5f8f7;border-radius:9px;font-size:.94rem}.permission-review{font-size:.82rem}.permission-review th:first-child{width:26%}.permission-limit{font-size:.8rem;color:#855a32}.effective-details{padding:15px 19px;font-size:.83rem}.advanced-review{font-size:.84rem;color:#60777d;margin-top:24px}.confirmation>.setup-actions{margin-top:24px}
@media(max-width:750px){main{padding:22px 20px 50px}.brand-caption{display:none}.setup-panel{padding:25px}.model-fields{grid-template-columns:1fr 1fr}.model-fields .config-field:first-child{grid-column:1/-1}.budget-fields{grid-template-columns:1fr}.budget-fields .config-field{margin-bottom:13px}.budget-fields .field-help{max-width:none}.tools-grid{grid-template-columns:1fr}.setup-progress{gap:10px}.setup-progress li{font-size:.8rem;gap:6px}.setup-progress li span{width:25px;height:25px;flex-shrink:0}.summary-note{display:block;margin:5px 0 0 20px}.review-summary{grid-template-columns:1fr}.setup-actions{align-items:stretch}.setup-actions>button,.setup-actions form,.setup-actions form button{width:100%}.setup-actions>.note{order:2}.setup-check{width:100%}.permission-review td,.permission-review th{padding:9px 6px}.config-node .config-children{margin-left:0}}
@media(max-width:450px){main{padding:18px 14px 40px}.app-brand{padding-bottom:18px;margin-bottom:22px}h1{font-size:1.65rem}section,details{padding:18px}.setup-panel{padding:22px 18px}.section-heading h2{font-size:1.3rem}.setup-progress li{font-size:.73rem;gap:5px;align-items:flex-start}.setup-progress li span{width:21px;height:21px;font-size:.7rem}.model-fields{display:block}.model-fields .config-field{margin:22px 0}.permission-settings,.advanced-settings{padding:16px}.advanced-category,.structured-setting{padding:13px}.setup-intro{font-size:.9rem}.config-field{margin:24px 0}.field-help{font-size:.78rem}.path-base{font-size:.72rem}.setup-nav{gap:15px}.setup-tools{padding:16px 18px}}
'''

PROGRESS_SCRIPT = """
const connection = document.querySelector('[data-live-url]');
const panel = document.querySelector('[data-progress]');
let timer, generation = 0, cursor = panel?.dataset.cursor || '', progressURL = panel?.dataset.progress || '';
let rows = panel ? JSON.parse(panel.querySelector('[data-raw-events]').textContent) : [];
function append(item) {
  const row = document.createElement('article'); row.className = 'event';
  const text = document.createElement('p');
  const states = {started:'开始', updated:'进行中', completed:'已完成', failed:'失败'};
  if (item.type === 'message') text.textContent = item.text;
  else if (item.type === 'tool') text.textContent = '工具 ' + item.tool + ' · ' + states[item.status];
  else if (item.type === 'session.started') text.textContent = '研究助手已连接';
  else if (item.type === 'turn.completed') text.textContent = '本次助手工作已结束，等待阶段结论';
  else if (item.type === 'usage') text.textContent = '用量更新：输入 ' + item.usage.input_tokens + ' / 输出 ' + item.usage.output_tokens + ' tokens';
  else return;
  row.appendChild(text);
  if (item.omitted_characters) { const note = document.createElement('small'); note.textContent = '本条公开文本已截短'; row.appendChild(note); }
  const events = panel.querySelector('[data-events]'); events.appendChild(row);
  while (events.children.length > 200) events.removeChild(events.firstChild);
}
async function poll(selectedGeneration) {
  if (!progressURL || selectedGeneration !== generation) return;
  const status = panel.querySelector('[data-stream-status]');
  try {
    const response = await fetch(progressURL + (cursor ? '&cursor=' + encodeURIComponent(cursor) : ''), {cache:'no-store'});
    if (selectedGeneration !== generation) return;
    if (!response.ok) throw new Error('公开进度暂不可用');
    const value = await response.json();
    if (selectedGeneration !== generation) return;
    status.textContent = value.progress_label;
    for (const item of value.events) { rows.push(item); append(item); }
    if (rows.length > 200) rows.splice(0, rows.length - 200);
    panel.querySelector('[data-raw-events]').textContent = JSON.stringify(rows, null, 2);
    if (value.restart_required) { status.textContent += '；请重新打开此进度页以读取新来源'; return; }
    cursor = value.cursor || cursor;
  } catch (_) { if (selectedGeneration === generation) status.textContent = '进度连接暂不可用，正在重连'; }
  if (selectedGeneration === generation) timer = window.setTimeout(() => poll(selectedGeneration), 2000);
}
function follow(current) {
  if (!panel?.dataset.followLatest) return;
  const next = current?.url || '';
  if (next === progressURL) {
    if (!current) panel.querySelector('[data-stream-status]').textContent = '尚无研究阶段；状态会自动更新';
    return;
  }
  generation++; window.clearTimeout(timer); progressURL = next; cursor = ''; rows = [];
  panel.querySelector('[data-events]').replaceChildren();
  panel.querySelector('[data-raw-events]').textContent = '[]';
  panel.querySelector('[data-progress-heading]').textContent = current ? '第 ' + current.step + ' 阶段 · ' + current.role + ' · 公开工作' : '当前助手的公开工作';
  panel.querySelector('[data-stream-status]').textContent = current ? '正在读取当前阶段状态…' : '尚无研究阶段；状态会自动更新';
  poll(generation);
}
if (panel && !panel.dataset.followLatest) poll(generation);
let source;
const rendered = new Map();
// Editable forms outside these slots are never replaced. A correction-note
// form inside a live action slot also keeps its user's draft.
document.addEventListener('input', event => {
  const slot = event.target.closest('[id^="live-"]');
  const form = event.target.closest('form');
  if (slot && form) form.dataset.liveDraft = 'true';
});
function connect() {
  if (!connection || source) return;
  source = new EventSource(connection.dataset.liveUrl);
  source.addEventListener('snapshot', event => {
    try {
      const value = JSON.parse(event.data);
      for (const [id, markup] of Object.entries(value.fragments)) {
        const slot = document.getElementById(id);
        if (!slot || rendered.get(id) === markup) continue;
        const drafts = Array.from(slot.querySelectorAll('form[data-live-draft]'));
        const focused = slot.contains(document.activeElement) ? document.activeElement : null;
        slot.innerHTML = markup; rendered.set(id, markup);
        for (const draft of drafts) {
          const action = draft.getAttribute('action');
          const trigger = draft.querySelector('[name=ack_correction]')?.value;
          const replacement = Array.from(slot.querySelectorAll('form')).find(form =>
            form.getAttribute('action') === action && form.querySelector('[name=ack_correction]')?.value === trigger);
          if (replacement) {
            // Keep the actual editable controls and their draft text. Hidden
            // bindings below receive this snapshot's current nonce/CSRF.
            replacement.replaceWith(draft);
            focused?.focus({preventScroll:true});
          } else {
            // The action ceased to apply. Preserve its text separately while
            // the live hero continues following authoritative state.
            let shelf = document.getElementById('live-drafts');
            if (!shelf) { shelf = document.createElement('section'); shelf.id = 'live-drafts'; const note = document.createElement('p'); note.textContent = '研究状态已变化；以下未提交说明已保留，请按最新状态操作。'; shelf.appendChild(note); connection.insertAdjacentElement('afterend', shelf); }
            draft.querySelectorAll('button[type=submit]').forEach(button => { button.disabled = true; });
            shelf.appendChild(draft);
          }
        }
      }
      for (const form of document.querySelectorAll('form[action]')) {
        const action = form.getAttribute('action').split('/').pop();
        if (!value.csrf[action]) continue;
        const nonce = form.querySelector('[name="nonce"]'), csrf = form.querySelector('[name="csrf"]');
        if (nonce && csrf) { nonce.value = value.nonce; csrf.value = value.csrf[action]; }
      }
      follow(value.current);
      connection.textContent = '已连接 · 状态自动同步'; connection.dataset.state = 'connected';
    } catch (_) { connection.textContent = '状态暂不可用，正在重连'; connection.dataset.state = 'offline'; }
  });
  source.addEventListener('unavailable', () => { connection.textContent = '状态暂不可用，正在自动重连'; connection.dataset.state = 'offline'; });
  source.onerror = () => { connection.textContent = '连接中断，正在自动重连；已填写内容保留'; connection.dataset.state = 'offline'; };
}
connect();
window.addEventListener('pagehide', () => { source?.close(); source = null; generation++; window.clearTimeout(timer); });
window.addEventListener('pageshow', event => { if (event.persisted) { connect(); if (panel && progressURL) poll(generation); } });
"""
SCRIPT_SOURCE = "'sha256-" + base64.b64encode(hashlib.sha256(PROGRESS_SCRIPT.encode()).digest()).decode() + "'"
STYLE_SOURCE = "'sha256-" + base64.b64encode(hashlib.sha256(CSS.encode()).digest()).decode() + "'"
CSP = "default-src 'none'; style-src " + STYLE_SOURCE + "; script-src " + SCRIPT_SOURCE + " " + CONFIG_SCRIPT_CSP + "; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"


def escape(value):
    return html.escape(str(value), quote=True)


def page(title, body, *, live=False):
    return ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>'+escape(title)
        +'</title><style>'+CSS+'</style></head><body><main><div class="app-brand"><span class="brand-mark" aria-hidden="true">S</span>SciDiscovery<span class="brand-caption">研究工作空间</span></div><h1>'+escape(title)+'</h1>'
        +body+'</main>'+('<script>'+PROGRESS_SCRIPT+'</script>' if live else '')+'</body></html>').encode()


def excerpt(value, limit):
    text = value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,allow_nan=False)
    omitted = max(0,len(text)-limit)
    return ('<div class="finding">'+escape(text[:limit])+'</div>'
        + ('<p class="note">'+str(omitted)+' 个字符未展开；可下载完整结论原文。</p>' if omitted else ''))


def result(step, job, payload, seal):
    base='/nodes/'+str(step)
    body=('<nav><a href="/results">阶段结论</a><a href="'+base+'">第 '+str(step)
        +'</a><a href="'+base+'/science">下载完整结论原文</a><a href="'+base+'/materials">'
        +str(len(seal['materials']))+' 份研究文件</a></nav>')
    body+='<section><h2>结论说明</h2><p>本阶段已留下结论原文。是否达到研究目标，请结合研究者写下的发现、局限和待解决问题判断。</p></section>'
    body+='<p class="note">已记录的阶段 '+str(step)+' · '+escape(job['role'])+'. 记录完成不等于科学结论已获认可。</p>'
    comparison=((job.get('history') or {}).get('view') or {}).get('candidates')
    comparison=comparison if isinstance(comparison,dict) else {}
    body+='<section><h2>研究发现</h2>'+excerpt(payload.get('summary','原文未提供'),512)
    body+=excerpt(payload.get('scientific_result',payload.get('summary','原文未提供')),4096)+'</section>'
    body+='<div class="cards"><section><h2>候选方案的已有观察</h2><p class="note">以下是本阶段开始时已有的观察，后续证据未计入。指标需要结合完整结论判断。</p>'
    facts=comparison.get('candidate_facts') or []
    for fact in facts:
        body+='<article><h3>'+escape(fact.get('id','未注明的候选方案'))+'</h3>'
        body+='<p>评估：'+escape(fact.get('evaluation_key','原文未注明'))+'</p>'
        body+='<p class="metric">'+escape(fact.get('metric','未知'))+'</p><p>指标方向：'+escape(fact.get('direction','unknown'))+'</p>'
        if fact.get('evaluation_key_truncated'):
            body+='<p class="gap">原始摘要中的评估标识已截短。</p>'
        body+='</article>'
    if not facts:
        body+='<p class="gap">本阶段的输入摘要未列出候选方案观察，可查看完整原文。</p>'
    if comparison.get('candidate_facts_omitted_count'):
        body+='<p class="gap">'+str(comparison['candidate_facts_omitted_count'])+'条候选方案观察未在摘要中展开，请查看完整原文。</p>'
    body+='<p>观察覆盖范围：'+escape(comparison.get('coverage','unknown'))+'</p></section>'
    body+='<section><h2>研究者的建议</h2>'
    ordinary_a=job['role']=='A' and not job.get('formal_review') and payload.get('next_action')!='audit'
    recommended=payload.get('candidate_recommendation') if ordinary_a else None
    if ordinary_a:
        body+=('<p>本阶段综合评估建议：<strong>'+escape(recommended)+'</strong></p>' if recommended is not None else
            '<p class="gap">本次综合评估未推荐候选方案。</p>')
    else:
        body+='<p class="gap">此阶段没有普通综合评估的候选推荐。</p>'
    previous=comparison.get('a_recommended')
    if previous:
        body+='<details><summary>本阶段开始前的综合评估建议</summary><p>A'+escape(previous['author_step'])+': '+escape(previous['candidate_id'])+'</p></details>'
    body+='<p class="note">研究者的建议、指标观察、交付情况和正式评审各自保留。</p></section></div>'
    body+='<section><h2>局限与待解决问题</h2>'
    limits=payload.get('limitations') or []
    for value in limits[:6]:body+=excerpt(value,1200)
    if len(limits)>6:body+='<p>'+str(len(limits)-6)+'条局限未展开，请下载完整结论原文。</p>'
    if not limits:body+='<p>原文未单列局限。</p>'
    if payload.get('remaining_question') is not None:body+='<h3>待解决问题</h3>'+excerpt(payload['remaining_question'],2048)
    body+='</section>'
    fields=('scope','coverage','candidate_count','latest_a_step','view_status',
        'candidate_facts_omitted_count','audits_omitted_count',
        'failed_candidate_count','unknown_candidate_count','candidate_alerts','candidate_alerts_omitted_count',
        'public_audits','limitation')
    public={key:comparison[key] for key in fields if key in comparison}
    body+='<details><summary>高级：比较范围与未展开内容</summary><pre>'+escape(json.dumps(public,ensure_ascii=False,indent=2))+'</pre>'
    body+='<p class="note">摘要未展开的内容仍可在完整结论和研究文件中查看。</p></details>'
    return page('阶段结论 · 第 '+str(step),body)
