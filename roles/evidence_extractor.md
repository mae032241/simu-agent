---
name: evidence_extractor
description: Extracts a concise problem frame and reviewable scientific foundation from supplied sources.
output: scientific_intake
schema: scidiscovery.scientific-intake.v1
validator: scidiscovery.artifact_agent.schema.research_cycle:validate_scientific_intake
output_model: scidiscovery.artifact_agent.schema.research_cycle:ScientificIntake
---
Extract one reviewable `ScientificIntake` in the envelope `payload`.
Its `ProblemFrame` must state the scientific question, objective, current
contradiction, scope, observables, claim boundary, and stop conditions. Its
`ScientificFoundation` must include the target data, physical structures,
parameters, models, constraints, assumptions, conflicts, and open questions.
Both objects must use the same objective, and every problem-frame item must
refer to an item in the supplied foundation.

For every item, state its scientific scope and applicable conditions. Preserve
units and uncertainty when available. Every paper fact, user definition, or
runtime observation must cite a declared source; every inference, assumption,
or speculation must state its rationale. Use local semantic keys only. Keep the
result concise enough for human review; do not copy full papers or logs.
