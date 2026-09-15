"use strict";

// Localize only timestamps and UI interaction, never scientific report prose.
document.querySelectorAll("time.local-time[datetime]").forEach((element) => {
  const date = new Date(element.getAttribute("datetime"));
  if (Number.isNaN(date.getTime())) return;
  element.title = element.getAttribute("datetime");
  element.textContent = new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
    hour12: false, timeZoneName: "short",
  }).format(date);
});

// Every enhanced link remains an ordinary, independently usable HTML page.
let diagnosticRequest = null;
document.addEventListener("click", async (event) => {
  if (!(event.target instanceof Element)) return;
  const link = event.target.closest("a[data-diagnostic-api]");
  if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  const target = link.closest(".diagnostic-event")?.querySelector(".diagnostic-lazy");
  if (!target) return;
  const endpoint = new URL(link.dataset.diagnosticApi, window.location.href);
  if (endpoint.origin !== window.location.origin) return;
  event.preventDefault();
  if (diagnosticRequest) diagnosticRequest.abort();
  const controller = new AbortController();
  diagnosticRequest = controller;
  const timer = window.setTimeout(() => controller.abort(), 15000);
  target.replaceChildren();
  const original = document.createElement("a");
  original.href = link.href;
  original.textContent = "在完整页面读取与翻页";
  const status = document.createElement("p");
  status.textContent = "正在读取这条错误的原记录…";
  target.append(original, status);
  link.setAttribute("aria-busy", "true");
  try {
    const response = await fetch(endpoint, {
      credentials: "same-origin", cache: "no-store", referrerPolicy: "no-referrer",
      headers: {"Accept": "application/json"}, signal: controller.signal,
    });
    if (!response.ok) throw new Error("read_failed");
    const raw = await response.text();
    if (raw.length > 256 * 1024) throw new Error("read_limit");
    const value = JSON.parse(raw);
    if (typeof value.text !== "string") throw new Error("missing_text");
    const text = document.createElement("pre");
    text.className = "diagnostic-text";
    text.textContent = value.text;
    status.textContent = value.next_offset == null
      ? "已读取本分段。其他错误、日志或分段请在完整页面核对。"
      : "已读取一个日志分段；完整页面可继续读取后续字节。";
    target.append(text);
  } catch (error) {
    status.textContent = "本次读取未完成。请使用上方完整页面入口重试；原记录与任务状态不受影响。";
  } finally {
    window.clearTimeout(timer);
    link.removeAttribute("aria-busy");
    if (diagnosticRequest === controller) diagnosticRequest = null;
  }
});

// Notifications name changed control records. They never replace a document,
// submit a form, or read scientific payloads on behalf of the user.
(() => {
  const page = document.querySelector("main[data-instance-id]");
  const instance = page?.dataset.instanceId;
  if (!instance || instance.length > 256) return;
  let instancePath;
  try {
    instancePath = encodeURIComponent(instance);
  } catch (error) {
    return;
  }
  const header = page.querySelector(".workbench-header") || page;
  const status = header.querySelector(".workbench-update-status") || document.createElement("p");
  if (!status.isConnected) {
    status.className = "workbench-update-status";
    status.setAttribute("role", "status");
    header.append(status);
  }
  const banner = document.createElement("div");
  banner.className = "workbench-update-banner bounded-note";
  banner.setAttribute("aria-live", "polite");
  banner.hidden = true;
  header.append(banner);

  const changed = new Map();
  const revisions = new Map();
  const snapshots = new Map();
  const nodeKey = /^(run|artifact|approval|execution):[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}$/;
  let cursor = "";
  let source = null;
  let transportErrors = 0;
  let polling = typeof window.EventSource !== "function";
  let pollTimer = null;
  let pollRequest = null;
  let pollDeadline = null;
  let stopped = false;
  let resetRequired = false;
  let overflow = false;

  function remember(map, key, value) {
    map.delete(key);
    if (map.size >= 200) map.delete(map.keys().next().value);
    map.set(key, value);
  }

  function showChanges() {
    if (!changed.size && !resetRequired && !overflow) return;
    banner.replaceChildren();
    const text = document.createElement("p");
    text.textContent = resetRequired
      ? "更新游标需要重置。请刷新当前视图；这不表示原历史发生了变化。"
      : "以下节点已有新的控制记录，当前页面仍保留您正在阅读的内容。";
    banner.append(text);
    const list = document.createElement("ul");
    for (const key of changed.keys()) {
      const item = document.createElement("li");
      const link = document.createElement("a");
      link.href = `/instance/${instancePath}/nodes/${encodeURIComponent(key)}`;
      link.textContent = key.length > 120 ? key.slice(0, 120) + "…" : key;
      item.append(link);
      list.append(item);
    }
    if (changed.size) banner.append(list);
    if (overflow) {
      const more = document.createElement("p");
      more.textContent = "还有变化未逐条列出，请刷新后查看。";
      banner.append(more);
    }
    const refresh = document.createElement("a");
    refresh.href = window.location.href;
    refresh.textContent = "更新当前视图";
    banner.append(refresh);
    banner.hidden = false;
  }

  function markChanged(key) {
    if (changed.size < 8 || changed.has(key)) changed.set(key, true);
    else overflow = true;
  }

  function pause() {
    if (source) source.close();
    source = null;
    window.clearTimeout(pollTimer);
    pollTimer = null;
    window.clearTimeout(pollDeadline);
    pollDeadline = null;
    if (pollRequest) pollRequest.abort();
  }

  function schedulePoll() {
    if (stopped || document.hidden || !polling || pollTimer !== null) return;
    pollTimer = window.setTimeout(() => {
      pollTimer = null;
      pollMetadata();
    }, 10000);
  }

  function usePolling() {
    polling = true;
    if (source) source.close();
    source = null;
    status.textContent = "实时通知暂不可用；可见页面将每 10 秒读取一次有界状态。原链接仍可使用。";
    schedulePoll();
  }

  // A bounded change stamp for UI metadata only; never an artifact identity.
  function stamp(node) {
    const text = JSON.stringify(node);
    if (text.length > 16384) return null;
    let value = 2166136261;
    for (let index = 0; index < text.length; index += 1) {
      value = Math.imul(value ^ text.charCodeAt(index), 16777619);
    }
    return `${text.length}:${value >>> 0}`;
  }

  async function pollMetadata() {
    if (stopped || document.hidden || !polling || pollRequest) return;
    const controller = new AbortController();
    pollRequest = controller;
    pollDeadline = window.setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch(`/api/instances/${instancePath}/overview`, {
        credentials: "same-origin", cache: "no-store", referrerPolicy: "no-referrer",
        headers: {"Accept": "application/json"}, signal: controller.signal,
      });
      if (response.status === 401 || response.status === 403) {
        stopped = true;
        status.textContent = "浏览凭据已不可用，请从原本地管理入口重新打开。当前页面保持不变。";
        return;
      }
      if (!response.ok) throw new Error("metadata_unavailable");
      const raw = await response.text();
      if (new TextEncoder().encode(raw).byteLength > 256 * 1024) throw new Error("metadata_limit");
      const value = JSON.parse(raw);
      const active = Array.isArray(value.active_tasks) ? value.active_tasks : [];
      const recent = Array.isArray(value.nodes?.items) ? value.nodes.items : [];
      for (const node of [...active.slice(0, 90), ...recent.slice(0, 100)]) {
        if (!node || typeof node.key !== "string" || !nodeKey.test(node.key)) continue;
        const revision = stamp(node);
        if (revision === null) continue;
        if (snapshots.has(node.key) && snapshots.get(node.key) !== revision) markChanged(node.key);
        remember(snapshots, node.key, revision);
      }
      status.textContent = "正在用有界元数据检查已知节点的变化；完整内容由您选择读取。";
      showChanges();
    } catch (error) {
      if (!stopped && !document.hidden) status.textContent = "本次状态读取未完成；稍后重试，或使用原链接手动刷新。";
    } finally {
      window.clearTimeout(pollDeadline);
      pollDeadline = null;
      if (pollRequest === controller) pollRequest = null;
      schedulePoll();
    }
  }

  function connect() {
    if (stopped || document.hidden || source) return;
    if (polling) {
      schedulePoll();
      return;
    }
    const endpoint = new URL(`/api/instances/${instancePath}/events`, window.location.origin);
    if (cursor) endpoint.searchParams.set("after", cursor);
    let connection;
    try {
      connection = new EventSource(endpoint.href);
    } catch (error) {
      usePolling();
      return;
    }
    source = connection;
    connection.addEventListener("nodes", (event) => {
      if (source !== connection || stopped || document.hidden) return;
      try {
        if (event.data.length > 128 * 1024) throw new Error("event_limit");
        const value = JSON.parse(event.data);
        if (!value || !Array.isArray(value.events) || typeof value.cursor !== "string" || value.cursor.length > 512) {
          throw new Error("event_invalid");
        }
        cursor = value.cursor;
        transportErrors = 0;
        if (value.reset_required === true) {
          resetRequired = true;
          revisions.clear();
        }
        for (const item of value.events.slice(0, 100)) {
          if (!item || typeof item.node_key !== "string" || !nodeKey.test(item.node_key)
              || typeof item.revision !== "string" || item.revision.length > 128) continue;
          if (revisions.get(item.node_key) === item.revision) continue;
          remember(revisions, item.node_key, item.revision);
          markChanged(item.node_key);
        }
        if (value.events.length > 100) overflow = true;
        status.textContent = "实时通知已连接；节点变化将提示您手动更新视图。";
        showChanges();
      } catch (error) {
        usePolling();
      }
    });
    connection.addEventListener("view_error", () => {
      if (source === connection) usePolling();
    });
    connection.onerror = () => {
      if (source !== connection || stopped || document.hidden) return;
      transportErrors += 1;
      if (transportErrors >= 3) usePolling();
      else status.textContent = "通知连接中断，正在按原游标重新连接。您可继续使用当前页面。";
      // EventSource resumes with the server's Last-Event-ID until the fallback.
    };
  }

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) pause();
    else connect();
  });
  function stop() {
    stopped = true;
    pause();
    if (diagnosticRequest) diagnosticRequest.abort();
  }
  window.addEventListener("beforeunload", stop);
  window.addEventListener("pagehide", stop);
  window.addEventListener("pageshow", (event) => {
    if (event.persisted) {
      stopped = false;
      connect();
    }
  });
  connect();
})();
