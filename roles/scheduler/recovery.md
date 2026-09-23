<!-- SCIDISCOVERY MANAGED SCHEDULER GUIDE -->

Continuing a completed node creates an ordinary new Run with the old sealed output
as an input. For failed work with new inputs or a changed compiled contract, use
draft_from for the same Operation's validated saved draft; it remains provisional
work, not scientific evidence. Use resume_from only when the original ordered inputs
and compiled contract are unchanged. Preserve the existing recovery source, backend
and attempt-budget checks; do not automatically extend attempts. Report unavailable
saved work as a bounded gap. A new or reused Agent must open the new assignment;
its prior memory never substitutes for newly bound records.

For an Agent action, dispatch only the `agent_type` returned by control. After
the child returns, read `run_status`; accept scientific content only when the
Run is `completed`. A failed or timed-out Run must be recorded explicitly;
retry creates a new Run with fresh bindings and budget. The scheduler may set
`max_attempts` on invoke (and optional preflight) to select the total recovery-chain
Run budget, including its first Run. Omission inherits the selected recovery
source's scheduler budget, or the existing Operation default policy. Inspect
`recovery.attempt_budget` and actual saved progress before extending an exhausted
chain; extension is a new immutable request and never changes earlier Runs.
Do not extend automatically or repeat an unchanged computation that cannot fit
the single-Run budget. A platform may reuse an
idle Agent only for the same compiled Operation, after creating the new Run;
its memory never substitutes for bound records. Different Operations and
independent review of that Agent's own work require a fresh Agent.
