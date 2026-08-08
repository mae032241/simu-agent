# TCAD Transport Contract

The interactive Agent never receives machine credentials or a solver-side
control socket. `CommandTCADExecutorAdapter` invokes one administrator-owned,
short-lived executable for each operation. The executable reads one canonical
JSON object from standard input and writes one bounded JSON response to standard
output.

Request envelope:

```json
{
  "schema_version": 1,
  "operation": "prepare|submit|status|collect",
  "payload": {}
}
```

Successful response:

```json
{
  "schema_version": 1,
  "operation": "status",
  "ok": true,
  "payload": {}
}
```

The operations are deliberately small:

- `prepare` receives local descriptors for `job.json` and `project.tar` and
  returns the descriptor that the solver-side user runner can read.
- `submit` returns immediately with `run_id` and `state`.
- `status` performs one short state query and returns one state.
- `collect` runs only after terminal state, materializes verified outputs under
  the supplied local result root, and returns their descriptors.

The transport must not wait for a solver job, repeatedly poll, generate a deck,
change the package, approve a request, or write SciDiscovery state. Credentials,
connectivity, and the production tool policy stay in administrator-owned
configuration outside the Agent boundary.

For the supported VMware deployment, each transport call invokes the existing
Windows OpenSSH client and a dependency-free Python 3.6 runner in the VM
user's project directory. No VM-side SciDiscovery service, new SSH key, sudo,
or port proxy is required.
