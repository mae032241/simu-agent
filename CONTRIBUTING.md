# Contributing

1. Keep generic control-plane changes separate from domain plugins.
2. Do not place control identifiers or lifecycle fields in role prompts or role
   payloads.
3. Add deterministic code for mechanical transformations; use Agents only for
   scientific judgment or simulator authoring/review.
4. Add focused tests for every behavior change, then run `pytest -q`.
5. Keep tracked examples free of credentials, licenses, live hosts, and
   machine-specific absolute paths.
6. Update both English and Chinese README or installation documents when their
   shared behavior changes.

Real TCAD output is evidence only for the exact reviewed project and execution
contract. Unit tests and mock adapters do not qualify scientific claims.
