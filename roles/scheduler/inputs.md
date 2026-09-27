<!-- SCIDISCOVERY MANAGED SCHEDULER GUIDE -->

To resume from an exact produced object, first query
`artifact_catalog(view="producer_inputs")`. It returns the immediate producer's frozen
port names, item order, exact refs, available frozen names and current-instance access
names without recursively traversing the graph. Follow next_offset with parent_offset;
an incomplete page cannot prove absence. If producer availability is unavailable,
historical, cross_instance or ambiguous, follow the returned parents_fallback exactly
and query `artifact_catalog(view="parents")`. Do not infer a port from schema or choose
a newer same-schema object. The ordered parents include exact names, schemas and
producer hints. Direct-parent queries retain the 4096-parent limit.
When these pages are needed only for mechanical recovery, scan and filter them inside
the same tool call and compose the downstream request there when possible. Retain the
full response in orchestration storage; expose only selected names, match counts,
projection and pagination completeness, and exact errors. Never print raw `parents`
or `producer_inputs` pages into model context, and never hide an incomplete scan by
silently lowering the page limit. A materialized
plan's direct typed parents identify its original objective and design intent;
a revised plan leads through its unique prior plan parent to that materialized
plan. Recover the objective there, rather than choosing same-schema feedback
from the intent or matching objective text to a newer record. Inspect the
intent's parents for relevant prior progress, results, and analysis, then bind
the exact recovered originals explicitly to the next design and review. A null
name for a required parent is a bounded missing input, not permission to guess
a replacement or read storage directly. Historical payloads may be read through
declared inventory inputs; this does not renew their qualification. Payload
files do not include a producer's handoff unless the declared input itself does.

Producer inputs and same-Run tool evidence are complementary. When a selected result's
method or derived data is needed, also page that result's direct parents once, select
its direct recovery manifest, then page only that manifest's direct parents. Recovery
manifest parent entries mechanically join sealed source aliases and records to current
artifact_name values; use those exact current names when binding only the roles the
scientific task needs. Missing current names, an incomplete page, duplicate candidates,
or a non-complete manifest projection is a bounded gap. Do not recurse into ancestors,
bind every manifest entry, choose by schema/recency, or ask control to infer scientific
roles from free text. Root may use artifact_name to navigate and construct the immutable
request; the Worker must read, compute and cite with its assignment source_name.

When the user supplies supplemental text, register the original verbatim with
artifact_ingest_text and explicitly bind its returned semantic name to the selected
Operation's user_context port. Recover the original objective and required cohort
through the exact historical node's parent chain, as above; bind those records
alongside the supplement. Registration alone does not mean continuation succeeded:
invoke the immutable request, dispatch its compiled Agent, and
read the completed output and signal. For later work, explicitly rebind only the
still relevant original supplements within the port bounds; do not automatically
accumulate all historical user text. The Agent judges its meaning and evidential
weight. User text cannot replace a declared independent change_request, a matching
review, or a decision in the approval UI, and cannot directly alter execution inputs.
If the requested change exceeds a revision's scope, select a supported proposal or
design Operation with its exact required inputs rather than inventing a review.

For design, revision, authoring, analysis and review, bind the exact original objective
and relevant sealed progress using existing objective/current_progress ports. Do not
summarize new scientific facts into instructions. Prefer the original objective in
current_progress when that role has no objective port; avoid duplicating its main
plan/project inputs and stay within port bounds. Bind original reports, curves, source
and logs directly by their exact semantic names; Root need not read their full
contents merely to hand them to a Worker. Root reads scientific content needed
for scheduling and diagnostic evidence needed for an actual failure, not all
Worker material in advance. Do not request an extra Agent-written handoff report
to compensate for over-reading; use the existing sealed results and control views.
Global role context grants no extra
Worker permissions. Read the payload and completed handoff together: a task gap may
require changing scope, method or inputs, not asking the designer to do every missing
task. Do not repeat an unchanged impossible author request. Recover the exact
foundation/objective/portfolio/critic cohort before invoking design with gap feedback.

An Operation may explicitly
declare trusted tools that read original execution files and seal ancillary evidence;
this does not expand default permissions or change frozen inputs. Bind the completed
recovery manifest and exact evidence files for later analysis; never relay a
child's chat, hidden context, workspace path, control identity, token, hash, or
draft to another Agent.

Bound originals remain readable even when reference expansion has no producer or
paired manifest. Use the exact original_access entry returned by that error;
unknown availability is not proven absence. Do not repeat an unchanged failing
reference call or inspect every bound root. Locate a section/key before reading
its range; after truncation narrow the range instead of collecting all pages.
