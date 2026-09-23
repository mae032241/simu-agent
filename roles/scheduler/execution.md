<!-- SCIDISCOVERY MANAGED SCHEDULER GUIDE -->

External execution requires its exact
compiled approval: `operation_invoke` creates the request and returns its exact
loopback review URL; after the sealed UI decision, call `execution_start` and
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
