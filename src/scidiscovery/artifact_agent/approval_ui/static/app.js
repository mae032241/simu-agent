"use strict";

const activateTab = (tabList, selectedTab) => {
  tabList.querySelectorAll("[data-review-target]").forEach((tab) => {
    const selected = tab === selectedTab;
    tab.classList.toggle("is-active", selected);
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
    const panel = document.getElementById(tab.dataset.reviewTarget);
    if (panel) panel.hidden = !selected;
  });
};

document.querySelectorAll(".review-tabs").forEach((tabList) => {
  const tabs = Array.from(tabList.querySelectorAll("[data-review-target]"));
  tabs.forEach((tab, index) => {
    tab.tabIndex = tab.classList.contains("is-active") ? 0 : -1;
    tab.addEventListener("click", () => activateTab(tabList, tab));
    tab.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      let next = index;
      if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
      if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
      if (event.key === "Home") next = 0;
      if (event.key === "End") next = tabs.length - 1;
      activateTab(tabList, tabs[next]);
      tabs[next].focus();
    });
  });
});

document.querySelectorAll("[data-tree-action]").forEach((button) => {
  button.addEventListener("click", () => {
    const subject = button.closest(".raw-subject-body");
    const tree = subject ? subject.querySelector(".tree") : null;
    if (!tree) return;
    const shouldOpen = button.dataset.treeAction === "expand";
    tree.querySelectorAll("details").forEach((node) => {
      node.open = shouldOpen;
    });
  });
});

document.querySelectorAll("[data-parameter-search]").forEach((input) => {
  input.addEventListener("input", () => {
    const scope = input.closest(".semantic-section");
    if (!scope) return;
    const query = input.value.trim().toLocaleLowerCase();
    scope.querySelectorAll("[data-parameter-item]").forEach((item) => {
      const text = (item.dataset.parameterText || "").toLocaleLowerCase();
      const matches = !query || text.includes(query);
      item.hidden = !matches;
      if (query && matches && item.tagName === "DETAILS") item.open = true;
    });
    scope.querySelectorAll("[data-parameter-group]").forEach((group) => {
      const visible = Array.from(
        group.querySelectorAll("[data-parameter-item]"),
      ).some((item) => !item.hidden);
      group.hidden = Boolean(query) && !visible;
      if (query && visible && group.tagName === "DETAILS") group.open = true;
    });
  });
});

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
