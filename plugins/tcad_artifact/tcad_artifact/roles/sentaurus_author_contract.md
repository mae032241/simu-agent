# Frozen Sentaurus authoring contract

Treat one execution unit as `solver + solver-language entrypoint + arguments ->
raw solver outputs`. An SProcess entrypoint is an SProcess/Tcl `.cmd`; an
SDevice entrypoint is an SDevice `.cmd` plus declared native inputs. Shell,
Python, nested solver launches, scheduler commands and detached processes are
runner responsibilities and must not appear in a direct solver deck.

Read `deck/contract/materialization-spec.json`, write complete solver source
under `deck/files/`, then declare the production entrypoint, optional bounded
initialization entrypoint, one unique source anchor per planned case and only
solver-native TDR/PLX/PLT outputs in `deck/declarations.json`. The control plane
validates safe paths, exact case values and traceability; it does not generate
or interpret solver physics.

Make each case-varying value visible in solver source or a declared native
include. Prefer independent execution units; a native multi-case procedure is
valid only when it recreates the complete structure, fields, model state and
history for every case. Trace each declared output to a real solver statement.
Do not embed scoring, masks, thresholds, scientific verdicts or derived reports.

For a bounded failure revision, preserve the exact invocation and stop at the
earliest failed layer: contract, capability, parser, initialization, first
solve, continuation/process step, or raw-output contract. Reread the current
source around the first actionable locator, change one construct, preserve the
scientific plan, and use a new debug run name only after a source change.

For R-2020.09 SProcess, use increasing `line x` locations and tagged bounds;
reset independent later structures explicitly; keep alloy endpoint convention
explicit; declare a custom transported state once and give it explicit initial
and boundary conditions; include units on process time and temperature; apply
mesh refinement with an explicit remesh; select raw PLX fields before writing.
If the supplied plan or capability does not settle a required construct, report
the gap instead of guessing another release's syntax.
