---
name: scid-decision-corpus-maintenance
description: Reconcile SciDiscovery's current architecture truth with plans, audits, qualification reports, bilingual documentation, and superseded design decisions. Use when adding, pruning, archiving, restoring, or auditing decision documents or when readers cannot tell which status is current; not for ordinary prose editing.
---

# Maintain the SciDiscovery Decision Corpus

Keep the active design corpus small and authoritative without falsifying historical evidence. Review is read-only unless the user asks to edit or reorganize documents.

## Identify document roles

Classify each relevant document by what it is allowed to claim:

- **Current normative:** architecture, contracts, invariants, supported behavior, and current qualification boundaries.
- **Active proposal:** a not-yet-shipped change with explicit acceptance criteria and unresolved risks.
- **Current audit ledger:** a result bound to an exact candidate, revision, environment, and evidence set; it is current only within that scope.
- **Historical audit or postmortem:** an immutable account of what happened, including temporary identifiers and failures.
- **Tutorial or reference:** user-facing instructions derived from current behavior, not an architecture decision owner.
- **Generated projection:** disposable output whose editable source must be identified.

Use current code, configuration, installed-entry behavior, inbound links, newer decisions, and machine-validated registries to determine ownership. Dates, filenames, test counts, and words such as “current” are discovery hints, not authority.

## Reconcile supersession

Whenever adding or updating a decision, search for documents covering the same rule, mechanism, rejected alternative, status, or qualification claim. Classify overlap as:

- **No supersession:** both documents own distinct current facts.
- **Partial supersession:** retain both, make ownership explicit, and cross-link the surviving facts.
- **Full supersession:** move unique rationale, alternatives, negative guarantees, compatibility obligations, and reintroduction conditions to the new owner before archiving the old current-facing document.

Never rewrite a historical audit to make it match later code. Archive or relabel it and point readers to the current owner. Never promote a passing test count, mock run, historical solver output, or provisional Artifact into a current scientific qualification claim.

## Keep current prose resolvable

On current normative and user-facing surfaces, every reference must be resolvable from the repository at HEAD. Remove development-session narration, temporary ports, candidate nicknames, reviewer dialogue, and repair chronology unless they define a current contract. Preserve those facts in the exact audit or postmortem that owns them.

Maintain one home for each rule. Link instead of copying long protocol text across README, architecture, role prompts, plans, and qualification pages. When code and prose disagree, report the discrepancy; do not silently choose whichever makes the status greener.

For English/Chinese pairs, update only the counterpart sections affected by the source change, preserve reviewed unchanged wording, and verify terminology and meaning manually. A pairing hash cannot prove semantic equivalence. Do not translate scientific content merely to make an approval pass unless the requested workflow owns that scientific judgment.

## Report or edit safely

Before changes, produce a small ownership map naming the current owner, overlapping documents, inbound links, and proposed disposition: keep, narrow, cross-link, archive, or delete. Deletion requires proof that no unique current rationale, compatibility rule, or plausible reintroduction warning remains.

After authorized edits, repair links and bilingual counterparts, then run the relevant documentation, architecture-constraint, release-manifest, and `git diff --check` gates. Summarize what became authoritative, what became historical, what remains intentionally unresolved, and which evidence was not revalidated.
