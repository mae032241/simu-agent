<!-- SCIDISCOVERY MANAGED SCHEDULER GUIDE -->

External execution requires exact control authorization. For TCAD, invoke the
complete `tcad.study.execute` task with its exact project, independent review,
capability and scientific subject. Control prepares and seals the reviewed package
and returns its semantic name in `prepared_outputs`; do not schedule packaging or
project an embedded execution plan. Scientific file slots use `file_reference`;
never move large input files through JSON or model context.

Within both configured inclusive storage and wall-time limits, invoke reports policy
authorization with no human approval request. Otherwise follow the configured human
review URL and sealed UI decision, or report the explicit denial. Agent parameters
cannot raise administrative limits. Do not interpret policy authorization as an
independent scientific review. Use `execution_start` only after authorization and
bounded `execution_sync`. Sync refreshes status and logs only. Once the original
solver is terminal, explicitly call `execution_collect`, inspect `execution_status`
until collected, and use `execution_outputs` for the registered semantic names.
Collection is bounded background I/O; repeating an active request does not extend
its budget. On collection failure, read its engineering diagnostic and resume
the same execution explicitly; do not call `execution_start` again. Use
`diagnostic_read` for a returned scoped engineering reference, never a server path.
Human decisions remain exclusively in the loopback approval UI.

Use execution_outputs to register one exact collected execution. Its
result_artifact_name is the authoritative result binding returned by that call
on every page; null means it is not yet available. Use that exact name when
creating analysis, not an earlier status snapshot or a newer unrelated execution.

A retry, revision or renamed request retains the original scientific budget owner.
For an unknown submission, query the original execution; never start a second job.
The TCAD runner job wire is v4; local/remote policy digests and budget capabilities
must match the installed contract. Collection/preview limits are separate from the
configured logical task storage allowance.
