<!-- SCIDISCOVERY MANAGED SCHEDULER GUIDE -->

For TCAD analysis, experiment_plan/experiment_review identify the original
execution plan and its matching review. Bind newer retrospective analysis plans
and reviews in current_progress. Use artifact_catalog(view="producer_inputs") to
recover exact immediate producer ports and current access names. Use its explicit
parents_fallback for historical, cross-instance, unavailable or ambiguous producers.
Read run_status(view="detail", response_profile="compat", output_paths=[]) only for a terminal binding, native or
recovery diagnostic, and use artifact_catalog(view="parents") for the indicated
ordered parent schema/kind fallback;
null aliases are missing inputs, never permission to choose a newer record.
Inspect both recovery.draft_available and recovery.recovery_pending: an immutable
subset may be delivered while the old directory still requires preservation.
native_execution reports only observed local computation, not Agent reasoning
time or scientific success. No telemetry does not mean no native errors occurred.
After failure, select a bounded continuation from saved work and actual errors;
do not repeat an unchanged full calculation that cannot fit the remaining budget.

Before creating analysis that needs inspection, bind execution_outputs'
result_artifact_name on the declared execution_result port together with the
necessary outputs. Frozen Run inputs cannot be amended. If the result is absent,
select a new correctly bound analysis or allow bounded analysis to state the
missing inspection evidence; do not search for the latest execution implicitly.
