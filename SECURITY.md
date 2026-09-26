# Security

Do not report simulator license data, private keys, live service secrets, or
confidential scientific inputs in a public issue.

Before publishing a release, verify that it contains none of the following:

- `/etc/scidiscovery` secrets or policies copied from a live machine;
- `/var/lib/scidiscovery` databases or CAS payloads;
- generated `.codex` configuration;
- SSH identities, known-host databases, real host/IP data, or VM paths;
- Sentaurus licenses, proprietary binaries, manuals, or customer decks;
- research inputs or results that are not approved for disclosure.

The loopback approval UI is designed for a trusted local user and must not be
exposed to an untrusted network without a separate authentication and transport
security layer.

The default `LocalTrustedBackend` assumes cooperative local Agents and a trusted
host user. Root/Worker routing uses client-supplied platform metadata: a native
shell that can reach the control socket can forge Root metadata. The default
installer runs control, UI and the local TCAD service under the same service UID,
normally the installing user's UID. A Worker with that UID and filesystem access
can also read or modify control databases, CAS and the approval receipt secret.
Separate daemons do not isolate these credentials. A same-UID peer credential or
a token stored with mode `0600` does not distinguish Root from Worker.

Binding, qualification, approval and budget gates constrain normal interface use;
they do not contain a hostile same-UID shell. `SEC-002` remains open. Stronger
isolation requires an independently trusted launcher to bind caller identity and
an OS/sandbox boundary that denies Workers access to control sockets, state and
secrets. Existing native sandbox restrictions may narrow access but are not a
framework guarantee of that boundary.

Execution policies are allow-lists. Review executable paths, arguments,
environment variables, input roots, limits, and output bounds before enabling a
real solver profile. The TCAD adapter enforces domain runner and host restrictions;
core control binds the exact request to authorization, budgets and lifecycle.
Both layers are required for supported execution.
