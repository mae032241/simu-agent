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
  const progressPanel = page.querySelector("[data-experiment-key]");
  const copyPanel = page.querySelector("[data-display-copy]");
  const copyActions = page.querySelector("[data-display-actions]");
  const displayStage = copyPanel?.dataset.displayStage || "";
  const liveNode = progressPanel?.dataset.experimentKey || copyPanel?.dataset.displayCopy;
  const liveProgress = Boolean(liveNode);

  function retryForm(copy, key, stage = "") {
    if (!copy) return null;
    if (["queued", "running"].includes(copy.state)) {
      const button = document.createElement("button");
      button.type = "button"; button.disabled = true; button.textContent = "导读整理中…";
      return button;
    }
    const generate = copy.state === "not_generated";
    if (!generate && !copy.retry) return null;
    if (document.querySelector("meta[name='summary-retry-enabled']")?.content !== "true") {
      // Reuse the server's exact reason and same-origin access form.
      const template = document.querySelector("#summary-unavailable");
      if (template?.content) return template.content.cloneNode(true);
      const note = document.createElement("p");
      note.textContent = "导读操作暂不可用，请刷新页面核对。";
      return note;
    }
    const csrf = document.querySelector("meta[name='workbench-csrf']")?.content;
    if (!csrf) return null;
    const form = document.createElement("form");
    form.method = "post";
    form.action = `/instance/${instancePath}/display-summary/${generate ? "generate" : "retry"}`;
    form.dataset.summaryRetry = "";
    const fields = {csrf, node_key: key};
    if (!generate) Object.assign(fields, copy.retry);
    if (stage) fields.stage_reference = stage;
    for (const [name, value] of Object.entries(fields)) {
      const input = document.createElement("input");
      input.type = "hidden"; input.name = name; input.value = String(value);
      form.append(input);
    }
    const button = document.createElement("button");
    button.type = "submit"; button.textContent = generate ? "生成导读" : "重新整理";
    const note = document.createElement("small");
    note.textContent = "仅整理展示文案，不修改科学结果。";
    form.append(button, note);
    return form;
  }

  document.addEventListener("submit", event => {
    if (!(event.target instanceof Element) || !event.target.matches("form[data-summary-retry]")) return;
    const button = event.target.querySelector("button[type='submit']");
    if (button) { button.disabled = true; button.textContent = "正在提交…"; }
  });

  function updateCopy(node) {
    if (!copyPanel || node.key !== copyPanel.dataset.displayCopy || !node.display_copy) return;
    if ((node.stage_reference || "") !== displayStage) return;
    const copy = node.display_copy;
    const content = document.createDocumentFragment();
    for (const item of (copy.items || []).slice(0, 4)) {
      const title = document.createElement("h3");
      const summary = document.createElement("p");
      title.textContent = item.title;
      summary.textContent = item.summary;
      content.append(title, summary);
    }
    if (!copy.items?.length) {
      const message = document.createElement("p");
      message.textContent = ["queued", "running"].includes(copy.state)
        ? "展示导读正在整理；可直接阅读下方原始结果。" : copy.state === "not_generated"
        ? "该版本尚未生成导读，可阅读下方原文。" : "展示整理暂不可用，以下保留原始结果。";
      content.append(message);
    }
    const retry = retryForm(copy, node.key, displayStage);
    if (copyActions) copyActions.replaceChildren(...(retry ? [retry] : []));
    copyPanel.replaceChildren(content);
  }

  function updateExperiment(node) {
    if (!progressPanel || node.key !== progressPanel.dataset.experimentKey || !node.experiment_progress) return;
    const target = progressPanel.querySelector("[data-experiment-live]");
    if (!target) return;
    const values = node.experiment_progress;
    const labels = {queued: "等待负责人接入", running: "运行中", completed: "报告已交付", failed: "任务失败",
      created: "尚未提交", authorized: "已授权", submitted: "已提交", cancelling: "取消中",
      cancelled: "已取消", succeeded: "求解结束", collected: "结果已收集", abandoned: "已放弃"};
    const phases = {design: "设计", implementation: "实现", debug: "调试", execution: "执行", validity: "有效性判断"};
    const tools = {worker_experiment_prepare: "准备实验实现", worker_experiment_debug: "诊断实验实现",
      worker_experiment_execute: "查询或操作执行服务", worker_experiment_stage: "封存阶段结论",
      worker_submit_result: "提交最终报告", worker_reference_read: "读取材料", worker_open_assignment: "读取实验任务"};
    const time = value => value && !Number.isNaN(Date.parse(value)) ? new Date(value).toLocaleString() : "未记录";
    const content = document.createDocumentFragment();
    const line = text => {
      const p = document.createElement("p");
      p.textContent = text;
      content.append(p);
    };
    line(`实验负责人：${labels[node.state] || node.state} · 最近活动：${time(values.last_activity_at)}`);
    if (values.latest_activity) {
      line(`最近操作：${tools[values.latest_activity.tool_name] || "处理实验材料"}（${values.latest_activity.completed_at ? "调用已返回" : "尚未记录返回"}）`);
    }
    const stages = document.createElement("p");
    stages.textContent = "已封存交付：";
    for (const item of (values.stages || []).slice(0, 5)) {
      const link = document.createElement("a");
      link.href = `/instance/${instancePath}/nodes/${encodeURIComponent(node.key)}?stage_reference=${encodeURIComponent(item.reference)}`;
      link.textContent = phases[item.stage] || "阶段";
      stages.append(link, " ");
    }
    if (!values.stages?.length) stages.append("尚无阶段交付");
    content.append(stages);
    if (!values.executions?.length) line(values.gaps?.length ? "执行记录暂不可读。" : "尚无正式执行记录；负责人可能仍在准备或分析。");
    for (const execution of (values.executions || []).slice(0, 4)) {
      const heading = document.createElement("h3");
      const link = document.createElement("a");
      link.href = `/instance/${instancePath}/nodes/${encodeURIComponent(execution.key)}`;
      link.textContent = `${execution.name} · ${labels[execution.state] || execution.state}`;
      heading.append(link);
      content.append(heading);
      const observation = execution.execution_progress || {};
      line(`最近观测：${time(observation.observed_at)}`);
      if (observation.refresh_failed) line("最近刷新失败；保留上次观测，无法确认求解器是否仍在推进。");
      const progress = observation.progress || {};
      if (typeof progress.elapsed_seconds === "number") line(`观测时已运行 ${progress.elapsed_seconds} 秒；求解完成比例未知。`);
      for (const log of (progress.log_activity || []).slice(0, 2)) {
        line(`日志更新：${time(log.updated_at)}${log.last_line ? " · " + log.last_line : ""}`);
      }
      const collection = execution.collection_progress || {};
      const phase = {inspect_manifest: "读取文件清单", verify_cache: "校验已有文件", download_archive: "下载结果归档", extract_archive: "解包并校验结果"}[collection.phase];
      if (phase) line(`收集阶段：${phase}`);
      if (typeof collection.archive_bytes === "number" && collection.phase === "download_archive") line(`归档已接收 ${collection.archive_bytes} 字节`);
      if (typeof collection.completed_bytes === "number" && collection.total_bytes > 0 && collection.completed_bytes <= collection.total_bytes) {
        const bar = document.createElement("progress");
        bar.max = collection.total_bytes;
        bar.value = collection.completed_bytes;
        bar.setAttribute("aria-label", "结果文件校验进度");
        content.append(bar);
        line(`结果文件已校验：${(100 * collection.completed_bytes / collection.total_bytes).toFixed(1)}%`);
      }
    }
    if (values.omitted_executions || values.gaps?.length) line("此处为部分执行记录；完整记录或读取缺口请在研究轨迹中核对。");
    target.replaceChildren(content);
    const children = node.experiment_children;
    if (!children) return;
    for (const container of page.querySelectorAll("[data-experiment-children]")) {
      if (container.dataset.experimentChildren !== node.key || container.dataset.childOffset !== "0") continue;
      const fragment = document.createDocumentFragment();
      const addNote = text => {
        const p = document.createElement("p");
        p.textContent = text;
        fragment.append(p);
      };
      if (children.pending_approvals) addNote(`待处理审批：${children.pending_approvals}`);
      const list = document.createElement("ol");
      list.className = "experiment-child-list";
      for (const child of (children.items || []).slice(0, 8)) {
        const row = document.createElement("li");
        row.className = "experiment-child";
        const link = document.createElement("a");
        const stage = child.kind === "stage";
        link.href = `/instance/${instancePath}/nodes/${encodeURIComponent(stage ? child.parent_key : child.key)}`
          + (stage ? `?stage_reference=${encodeURIComponent(child.reference)}` : "");
        link.textContent = child.title + (stage ? ` · v${child.version}` : "");
        if (child.display_title) link.textContent += ` · ${child.display_title}（自动导读）`;
        const state = document.createElement("span");
        state.className = "workbench-state";
        state.textContent = stage ? "已封存" : ({pending: "待审批", decided: "已决定", expired: "已过期",
          cancelled_by_human: "用户已取消"}[child.state] || labels[child.state] || child.state);
        row.append(link, " ", state);
        const timestamp = document.createElement("p");
        timestamp.textContent = time(child.source_time);
        row.append(timestamp);
        if (child.kind === "approval") {
          const action = document.createElement("div");
          action.className = "approval-next-action";
          const title = document.createElement("strong");
          title.textContent = child.state === "pending" ? "待你决定" : "审批记录";
          action.append(title);
          for (const text of [child.approval_summary?.question, child.approval_summary?.resource_summary,
            child.approval_summary?.selected_label ? `决定：${child.approval_summary.selected_label}` : ""]) {
            if (text) { const p = document.createElement("p"); p.textContent = text; action.append(p); }
          }
          const open = document.createElement("a");
          open.href = link.href; open.className = "approval-action-link";
          open.textContent = child.state === "pending" ? "查看关键参数并审批" : "查看审批结果";
          action.append(open); row.append(action);
        }
        const retry = stage ? retryForm(child.display_copy || {state: "not_generated"}, child.parent_key, child.reference) : null;
        if (retry) row.append(retry);
        if (child.parent_key !== node.key) {
          const source = document.createElement("p");
          source.textContent = "原实验的执行记录，当前为恢复任务。";
          row.append(source);
        }
        list.append(row);
      }
      fragment.append(list);
      if (!children.items?.length) addNote("尚无阶段、执行或审批记录。");
      if (children.gaps?.length) addNote("部分子节点暂不可读或超出本次读取范围；请在全部记录中核对。");
      if (children.next_offset !== null && children.next_offset !== undefined) {
        const next = document.createElement("a");
        next.href = `/instance/${instancePath}/nodes/${encodeURIComponent(node.key)}?child_offset=${encodeURIComponent(children.next_offset)}#experiment-children`;
        next.textContent = "更早的子节点";
        fragment.append(next);
      }
      container.replaceChildren(fragment);
      const panel = container.closest("details.experiment-children");
      const count = panel?.querySelector("summary .panel-count");
      if (count) count.textContent = String(children.total);
    }
  }

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
    if (stopped || document.hidden || (!polling && !liveProgress) || pollTimer !== null) return;
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
    if (stopped || document.hidden || (!polling && !liveProgress) || pollRequest) return;
    const controller = new AbortController();
    pollRequest = controller;
    pollDeadline = window.setTimeout(() => controller.abort(), 8000);
    try {
      const endpoint = liveProgress
        ? `/api/instances/${instancePath}/nodes/${encodeURIComponent(liveNode)}?view=metadata${displayStage ? "&stage_reference=" + encodeURIComponent(displayStage) : ""}`
        : `/api/instances/${instancePath}/overview`;
      const response = await fetch(endpoint, {
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
      if (liveProgress) updateCopy(value);
      if (liveProgress) updateExperiment(value);
      const active = Array.isArray(value.active_tasks) ? value.active_tasks : [];
      const recent = Array.isArray(value.nodes?.items) ? value.nodes.items : [];
      for (const node of (liveProgress ? [value] : [...active.slice(0, 90), ...recent.slice(0, 100)])) {
        if (!node || typeof node.key !== "string" || !nodeKey.test(node.key)) continue;
        const revision = stamp(node);
        if (revision === null) continue;
        if (snapshots.has(node.key) && snapshots.get(node.key) !== revision) markChanged(node.key);
        remember(snapshots, node.key, revision);
      }
      status.textContent = liveProgress ? "实验状态已更新；科学结论与历史原文保持当前版本。" : "正在用有界元数据检查已知节点的变化；完整内容由您选择读取。";
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
    schedulePoll();
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
