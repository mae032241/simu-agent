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

Execution policies are allow-lists. Review executable paths, arguments,
environment variables, input roots, limits, and output bounds before enabling a
real solver profile.
