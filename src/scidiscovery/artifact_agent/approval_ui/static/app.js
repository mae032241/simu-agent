"use strict";

document.querySelectorAll(".decision-panel form").forEach((form) => {
  const textarea = form.querySelector("textarea[name='rationale']");
  const state = form.querySelector(".rationale-state");
  const budget = form.querySelector("input[name='additional_wall_time_hours']");
  const preview = form.querySelector('.budget-extension-preview');
  const updateBudget = () => {
    if (!budget) return;
    const selected = form.querySelector("input[name='selected_option']:checked");
    budget.disabled = !selected || !['authorize_execution', 'authorize_execution_with_exception', 'approve'].includes(selected.value);
    const extra = Number(budget.value);
    preview.textContent = budget.disabled ? '仅批准执行时可追加预算' :
      (Number.isFinite(extra) && extra > 0 ? `确认后累计时长上限：${Number(budget.dataset.currentSeconds) / 3600 + extra} 小时` : '不追加累计预算');
  };
  if (budget) budget.addEventListener('input', updateBudget);
  updateBudget();
  form.querySelectorAll("input[name='selected_option']").forEach((radio) => {
    radio.addEventListener("change", () => {
      const required = radio.dataset.requiresRationale === "true";
      if (textarea) textarea.required = required;
      if (state) state.textContent = required ? "必填" : "选填";
      updateBudget();
    });
  });
  form.addEventListener("submit", () => {
    const button = form.querySelector("button[type='submit']");
    if (button) button.disabled = true;
  });
});
