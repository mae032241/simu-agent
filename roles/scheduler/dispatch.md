<!-- SCIDISCOVERY MANAGED SCHEDULER GUIDE -->

Codex dispatch: use only the queued Run's returned agent_type and explicit model
and reasoning_effort from execution_profile.profile. Disable parent history with
fork_context=false (or fork_turns="none"). Initially ask the child to wait for
scheduler attachment; do not send Run metadata or control tokens in chat.
If spawn exposes no native thread ID, ask only that child to describe and call
worker_identity, report the returned thread_id/model/reasoning_effort, and wait.
These are control-plane attachment coordinates, never scientific evidence. Do not
substitute its nickname or task path, or ask it to infer an ID from files.
Bind the actual native thread ID from spawn or this platform-backed query with scid_call(name="worker_attach",
arguments={"name": <queued Run name>, "thread_id": <actual child ID>}), then
send the instruction to begin its queued assignment. If awaiting attachment,
complete this binding and follow up rather than creating another Run.

An idle local_trusted child may receive a new task only after attachment to the
new Run, with identical Operation ID, compiled digest, native agent_type and known matching actual model and
reasoning effort, and never for independent review of its own work. Unknown
historical profiles do not establish a match. Reuse requires worker_open_assignment
again with the new workspace, bindings and budget; no queued Run means no work.
Control-admitted reuse permits avoiding reprinting only while the complete role
remains in the child context; Local open.reading_guidance identifies unchanged contracts
from the preceding attached Run without exposing hashes. It also classifies current inputs
as unchanged, changed, new or unknown from immutable bindings and their uses. Unchanged
does not prove retained memory or prior reading; reassessment may reuse retained originals,
with targeted rereading for missing context or needed verification. Lost/compacted context requires
rereading; each new task, objective/input binding, language, budget and output/
recovery instruction is still current-Run information, regardless of role reuse.
Local Workers retain their declared workspace/Skill/native permissions.
Children publish below their opened workspace through worker_submit_result.
Completion chat is untrusted transport: read run_status and its sealed output
only after completed, never relay the child's scientific summary or paths.

Dispatch from the created Run execution_profile, not current defaults or platform
telemetry. Invoke freezes that configuration without a prior preflight. If optional
preflight returns normalized_request, retain and pass it unchanged without printing
or retyping it. After a lost response, inspect the named Run before retrying; changed
defaults do not authorize overwriting its frozen request. Never fall back to another model
after platform rejection. Do not create permanent roles per model or instance;
new assignments carry language changes. Close idle Agents if close_agent exists;
interrupt is not closure. Without closure, report capacity limits instead of
repeatedly spawning incompatible Agents.

Use operation_invoke's executor-specific result: an Agent's frozen execution
profile and deadline control dispatch; Transform outputs and Effect/Approval
identities or review URLs must be preserved. Read its detail entry only when
additional Run context can change the next action. Exact failures and normalized
requests retain their original meaning and must not be treated as success.
