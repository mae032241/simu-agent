"use strict";

document.querySelectorAll(".decision-panel form").forEach((form) => {
  const textarea = form.querySelector("textarea[name='rationale']");
  const state = form.querySelector(".rationale-state");
  form.querySelectorAll("input[name='selected_option']").forEach((radio) => {
    radio.addEventListener("change", () => {
      const required = radio.dataset.requiresRationale === "true";
      if (textarea) textarea.required = required;
      if (state) state.textContent = required ? "必填" : "选填";
    });
  });
  form.addEventListener("submit", () => {
    const button = form.querySelector("button[type='submit']");
    if (button) button.disabled = true;
  });
});
