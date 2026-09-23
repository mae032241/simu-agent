<!-- SCIDISCOVERY MANAGED SCHEDULER GUIDE -->

Await platform completion notifications when available; avoid alternating sleep
and unchanged status calls. Query for attachment, a real diagnostic question or
a deadline, not to repeat an unchanged status. Keep required user updates concise
and based on new events; do not reread results just to report waiting. Request state
and needed fields in one run_status call; check that response's state before using
its scientific content. Unfinished Runs expose no sealed results. Do not precede a
result read with an empty-path status check. Use
`run_status(response_profile="poll", output_paths=[])` only for necessary polling
or status-only diagnostics. It keeps lifecycle, exact safe diagnostics and recovery
gate status without expanding bindings, native/tool records, recovery detail or signal text.
For every MCP reply, handle the transport `isError` result before parsing its JSON payload;
preserve the returned code, path and message instead of turning it into a parse failure.
Fetch exact bindings with view="detail" when constructing or recovering a task
requires them, or to resolve a specific provenance question. Expand timing, native records and logs for an actual
diagnostic question, not routine polling. Default completed
summary excerpts are navigation aids, not complete scientific results.
When the response reports completed, read the formal conclusion, limitations, remaining contradiction
and next-action rationale together with scheduler_signal. Choose the read once:
use known paths directly; index only an unknown structure; read the whole payload
once if the decision needs most of its fields. Indexing is not a prerequisite.
For a LayeredDiagnosisReport, these existing paths give the scheduling context
in one values call (replace the Run name):

```json
{"name":"analysis","response_profile":"decision","output_paths":["/summary","/overall_verdict","/claim_allowed","/limitations","/remaining_contradiction","/next_action","/objective_assessment","/hypothesis_assessments"]}
```

This is a reading example, not a required output shape for every Operation.
Historical optional fields may be missing or null; interpret the available original
and signal without treating absence alone as an evidence gap. Expand evidence or
method details only to answer a specific unresolved scheduling question, not to
fill a routine checklist. For a design, read the current objectives,
feasibility and deferred-goal rationale before choosing implementation or redesign;
do not request entire proposal, variable or validation arrays merely to pass the plan
to another role. Bind the sealed original for that role's own reading. Selected values appear in
selected_output with original pointers; they are not a complete sealed_output.
Pointers start inside the payload: /summary, not /payload/summary. Only when needed
paths are unknown, use response_profile="navigation" with output_mode="index" for
the root field directory. Navigation returns signal availability without signal text.
Follow output_index.next_offset with index_offset on the same path; nested objects
can be indexed by their exact pointer. The directory has no field values. Read
needed originals with selected output_paths. For most/all fields, use
output_paths=[""] once instead of directory-plus-nearly-full selection. Use
view="detail" only when exact bindings/timing or an uncapped original are needed.
Retain values already read; never refetch their constituent fields or expand the
handoff/status to repeat the same scientific conclusion. The formal payload is the
scientific content authority; use scheduler_signal for control context. Keep exact
responses and requests in orchestration storage, and emit only the decision-relevant
selected values. Do not accumulate all pages and print them together: native shell
and functions.exec output are not protected by registered-tool response budgets.
Preserve exact errors, omissions and original access paths in that selection. Missing,
omitted, null and empty are distinct: follow omitted-value child paths only as
needed. Never read a full payload merely to discover names, or an index merely to
confirm known paths. Judge the original content together with scheduler_signal.

Before using an analysis to select more work, identify the completed Run's actual
scope. A plotting, packaging, or deployment acceptance Run cannot silently become
a refit or mechanism verdict. Keep three things separate: the Worker's sealed facts
and scientific limits, the objective assessment within the exact scoped plan, and
the scheduler's marginal-value judgment under the user's current cost constraints.
`next_action` and handoff hints are original report advice, never commands or catalog
authority. State which possible result of a candidate follow-up could change the
current decision. If none could, stop without manufacturing a stop Run or turning
the user's unwillingness to invest into physical evidence. An inconclusive verdict
or invalid execution may remain recorded while the scheduler legitimately stops;
numerical repair is selected only when it can affect the decision and is authorized.

For a known report Schema, use response_profile="decision" to request the decision's
exact conclusion, limitations, remaining contradiction and scheduler_signal together
with completed state. For an unknown Schema, read one bounded navigation index first
and then make one decision read for exact paths;
never impose generic scientific fields on every Artifact. Inspect execution
summary log_index before requesting detail; equal excerpts list all sources once,
and omission markers point to the original detail. Keep distinct errors exact.
