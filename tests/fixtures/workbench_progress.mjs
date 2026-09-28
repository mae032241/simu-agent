// Execute the shipped script against a small DOM transport fixture. This checks
// refresh behavior, not browser layout or CSS.
import {readFileSync} from "node:fs";
import vm from "node:vm";
import assert from "node:assert/strict";

class Element {
  constructor() { this.children = []; this.dataset = {}; this.isConnected = true; this._text = ""; }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(x => x.textContent ?? x).join(""); }
  set innerHTML(_) { throw Error("untrusted markup inserted"); }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this._text = ""; this.children = items; }
  setAttribute() {}
  querySelector(key) { return this.select?.[key] || null; }
  querySelectorAll(key) { return this.selectAll?.[key] || []; }
  closest() { return this.parent || null; }
}

const page = new Element(), header = new Element(), progress = new Element();
const live = new Element(), copy = new Element(), children = new Element(), history = new Element();
page.dataset.instanceId = "instance-one";
progress.dataset.experimentKey = "run:experiment";
copy.dataset.displayCopy = "run:experiment";
progress.select = {"[data-experiment-live]": live};
children.dataset = {experimentChildren: "run:experiment", childOffset: "0"};
history.dataset = {experimentChildren: "run:experiment", childOffset: "8"};
history.textContent = "older stages being read";
children.parent = new Element(); children.parent.open = true;
page.select = {".workbench-header": header, "[data-experiment-key]": progress, "[data-display-copy]": copy};
page.selectAll = {"[data-experiment-children]": [children, history]};
const events = new Map(), timers = new Map(); let sequence = 0;
const document = {
  hidden: false, querySelector: key => key === "meta[name='summary-retry-enabled']" ? {content: "true"}
    : key === "meta[name='workbench-csrf']" ? {content: "test-csrf"} : page, querySelectorAll: () => [],
  createElement: () => new Element(), createDocumentFragment: () => new Element(),
  addEventListener: (key, action) => events.set(key, action),
};
const requests = [];
const value = {key: "run:experiment", state: "running", experiment_progress: {stages: [], executions: []},
  display_copy: {state: "ready", items: [{title: "<img onerror=alert(1)>", summary: "尚不能判断。"}]},
  experiment_children: {total: 10, pending_approvals: 1, next_offset: 8, items: [
    {kind: "stage", parent_key: "run:experiment", reference: "sealed/a", title: "设计", version: 2},
    {kind: "approval", key: "approval:exact", parent_key: "run:experiment", title: "执行审批", state: "pending"}]}};
const window = {
  location: {origin: "http://localhost", href: "http://localhost/instance/one"},
  setTimeout: (action, delay) => { const id = ++sequence; timers.set(id, {action, delay}); return id; },
  clearTimeout: id => timers.delete(id), addEventListener() {},
};
const context = {document, window, Element, AbortController, TextEncoder, URL, console,
  fetch: async (url, options) => { requests.push({url, options}); return {ok: true, status: 200, text: async () => JSON.stringify(value)}; }};
vm.runInNewContext(readFileSync(process.argv[2], "utf8"), context);
async function tick() {
  const entry = [...timers].find(([, timer]) => timer.delay === 10000);
  assert.ok(entry, "missing next refresh");
  timers.delete(entry[0]); entry[1].action();
  await new Promise(resolve => setImmediate(resolve));
}
await tick();
assert.equal(requests.length, 1);
assert.match(requests[0].url, /run%3Aexperiment\?view=metadata$/);
assert.equal(requests[0].options.credentials, "same-origin");
assert.match(live.textContent, /运行中/);
assert.match(children.textContent, /设计 · v2/);
assert.match(children.textContent, /待审批/);
assert.match(children.textContent, /更早的子节点/);
assert.equal(history.textContent, "older stages being read");
assert.equal(children.parent.open, true);
assert.match(copy.textContent, /<img onerror=alert\(1\)>/);
value.display_copy = {state: "failed", items: [], retry: {cache_key: "exact-copy", generation: 2}};
await tick();
assert.match(copy.textContent, /重新整理/);
const form = copy.children[0].children.find(child => child.method === "post");
assert.equal(form.action, "/instance/instance-one/display-summary/retry");
assert.equal(form.children.find(child => child.name === "generation").value, "2");
value.display_copy = {state: "queued", items: []};
value.state = "completed";
await tick();
assert.match(live.textContent, /报告已交付/);
assert.doesNotMatch(copy.textContent, /重新整理/);
document.hidden = true; events.get("visibilitychange")();
assert.equal(timers.size, 0, "hidden pages must stop polling");
console.log("workbench progress refresh passed");
