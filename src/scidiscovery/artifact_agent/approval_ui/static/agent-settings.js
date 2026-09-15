"use strict";
for (const form of document.querySelectorAll(".agent-settings-form")) {
  const preview = form.querySelector("[data-settings-preview]");
  const refresh = () => {
    const changes = [];
    for (const field of form.querySelectorAll("[data-original]")) {
      if (field.value !== field.dataset.original) {
        changes.push(`${field.dataset.settingLabel}：${field.dataset.original || "继承"} → ${field.value || "继承"}`);
      }
    }
    if (preview) preview.textContent = changes.length ? changes.join("；") + "。仅影响后续任务。" : "尚无修改。";
  };
  form.addEventListener("input", refresh);
  form.addEventListener("change", refresh);
}
