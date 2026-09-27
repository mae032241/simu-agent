"use strict";

// Home cards reveal their destination; they never submit a management action.
function revealHomeSection() {
  const id = window.location.hash.slice(1);
  if (id !== "create-instance" && id !== "pending-approvals") return;
  const section = document.getElementById(id);
  if (!section) return;
  if (section instanceof HTMLDetailsElement) section.open = true;
  const create = section.querySelector("details[data-create-instance]");
  if (create) create.open = true;
  section.scrollIntoView({block: "start"});
}
window.addEventListener("hashchange", revealHomeSection);
document.addEventListener("click", (event) => {
  const link = event.target instanceof Element && event.target.closest("a.home-entry");
  if (link && link.hash === window.location.hash) revealHomeSection();
});
revealHomeSection();
