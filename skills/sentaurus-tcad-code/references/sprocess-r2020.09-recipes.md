# SProcess R-2020.09 Authoring Recipes

Use this index before searching the full PDF. These constructs are transcribed
from the matching manual; angle-bracket tokens are author substitutions, not
literal solver syntax. Case values and physical choices must come from the
task.

Manual basis throughout: *Sentaurus Process User Guide*, R-2020.09, SHA-256
`bcaf5cfe87bd276a2068fa6681a0b62b2526512b65a710a660d892c45ceaf5d9`.
PDF page numbers below are physical pages used by the bundled extraction helper;
printed page labels are identified explicitly and must not be passed to it.

## Contents

- Minimal authoring order
- One-dimensional structure
- Alloy composition
- Independent cases
- Custom conservative state
- Diffusion step
- Mesh refinement
- Raw PLX and TDR output
- Targeted fallback lookup

## Minimal authoring order

Write in this order before broad lookup:

1. Coordinate convention, increasing `line x` locations, and tagged bounds.
2. Region and initialization, including alloy composition.
3. A task-specific solution state and its equation or callback. Declare a
   shared custom solution once before a multi-case procedure; do not execute
   `solution ... add` again on every procedure call.
4. Explicit initial and boundary conditions.
5. One smallest case dispatch and one raw output.
6. Remaining cases through the same implementation path.
7. A separate minimal initialization entrypoint only when needed.

Register that auxiliary file only through the solver-neutral
`development_initialization_entrypoint` declaration; never replace the
production entrypoint or ask control to derive a shortened deck.

Do not use a built-in dopant name for a custom transported inventory merely
because the paper discusses that chemical species. Built-in states can activate
built-in bulk/active/defect callbacks. A phenomenological custom PDE should use
its own explicit solution name unless the experiment plan requires the built-in
semantics.

## One-dimensional structure

The required construction pattern is:

```tcl
line x location=0<um> spacing=<near-spacing><um> tag=front
line x location=<depth><um> spacing=<far-spacing><um> tag=back
region <Material> xlo=front xhi=back
init ...
```

Locations must be increasing. If a second independent structure is created in
the same command file, issue `line clear` before the new `line`, `region`, and
`init` sequence. See PDF pages 74, 77, 947, 967, and 1134. `line clear` removes
line declarations and stored mesh ticks; the reviewer must still verify that
the complete case construction is independent.

## Alloy composition

`InGaAs` is a built-in alloy material, but the endpoint convention and mole
fraction fields must be checked rather than inferred from the chemical formula.
Use the release's alloy-field helper through `init fields.values=` only after
confirming which endpoint the task's composition denotes. The generic form is:

```tcl
init fields.values=[MoleFractionFields <AlloyMaterial> <fraction>]
```

See PDF pages 58-63 for alloy interpolation and PDF pages 1099 and 1131 for
`MoleFractionFields`. Do not silently map `0.83` to a simulator endpoint.

## Independent cases

Prefer a single implementation procedure whose direct calls contain every
case-varying value. Put each planned case on one unique call line so it can be
declared as a source anchor. Before constructing a later structure in the same
entrypoint, use the documented `line clear` sequence above; do not rely on
variable reassignment alone as proof that mesh, regions, fields, or history are
fresh.

A unique case anchor is traceability, not physical proof. The independent
reviewer must compare all direct call values and the procedure body with the
experiment plan.

## Custom conservative state

For a custom transported scalar, use a fresh solution and an explicit Alagator
equation. The release-matched base form is:

```tcl
solution name=<State> add !negative !damp solve
pdbSetString <Material> <State> Equation \
  "ddt(<State>) - <diffusivity-expression>*grad(<State>)"
```

Sentaurus Process applies the outer divergence for the gradient flux form. See
printed pages 627-633 (PDF pages 663-669), including the worked forms at
PDF pages 668-671. Use
`EquationProc` only when a callback is actually needed to construct a
case-dependent equation; its callback contract is on PDF pages 679-683.

`solution ... add` creates a simulator-global solution definition (command
reference PDF pages 1285-1287). In a native multi-case deck, place that
declaration outside the case procedure and use unconditional `solve` when the
task requires the state in every case. `ifpresent=<same-state>` is not an
equivalent substitute. Recreate/initialize the data field inside each case,
but do not re-add the solution definition.

Do not use `UserDiffPreProcess` as an assumed way to disable an earlier built-in
callback. The manual describes it as a late hook that preserves built-in
preprocessing (PDF pages 681-682), so it cannot by itself prove that a failing
built-in initialization path is bypassed.

For a Dirichlet value at a real interface, use the material side explicitly:

```tcl
pdbSetBoolean <Interface> <State> Fixed_<MaterialSide> 1
pdbSetString <Interface> <State> Equation_<MaterialSide> \
  "<State>_<MaterialSide> - <boundary-value>"
```

The interface and material-side names must exist in the structure. One
`Gas_<Material>` setting cannot express two different values at two boundaries
that share the same interface identity; create a physically declared support
material or separate the cases/geometry instead of relying on coordinate
position. See PDF page 633.

## Diffusion step

Specify units explicitly. A bounded isothermal step uses:

```tcl
diffuse temperature=<temperature><C> time=<duration><s> maxstep=<step><s>
```

See PDF pages 208-209 and command reference PDF pages 1008-1015. The default
time and `maxstep` units are not assumed when the experiment plan uses seconds.

## Mesh refinement

Use explicit `line` spacing for the minimal 1D candidate. Add `refinebox` only
when the planned numerical tier requires it, and apply it with an explicit
`grid remesh`:

```tcl
refinebox min=<...> max=<...> xrefine=<...> <Material>
grid remesh
```

See PDF pages 82 and 786-792. Do not add adaptive fields or interface criteria
that the comparison plan does not declare.

## Raw PLX and TDR output

Select only raw fields required downstream and write them to declared safe
paths:

```tcl
SetPlxList {<State> <OtherRawField>}
WritePlx results/<case>.plx
struct tdr=results/<case>
```

`SetPlxList` has no default selected fields. See PDF pages 83-84, 586, and 1268.
The author must list workspace-file outputs in `deck/declarations.json`; the
control plane registers paths but does not infer them from these commands.

## Targeted fallback lookup

If a required construct is not covered here, query one indexed topic, then
extract its pages. Before the first source write, stop after one lookup and
preserve the unresolved item rather than trying synonym after synonym. After
preflight, search the first exact diagnostic token or command excerpt, not a
broad scientific phrase.
