# Reconstruct a latent signal after an operator and noise shift

Determine which mechanisms merit further investigation for recovering an eight
coordinate latent signal x from y = diag(a) x + Gaussian noise. Source observations
have mild attenuation and low noise; the target condition has stronger attenuation
and higher noise. Explain which assumptions each mechanism uses and where its
source behavior stops predicting performance under the target condition.

## Available information

`dataset.json` contains 128 labeled source training examples, 64 labeled public
source validation examples, and 64 labeled **public target stress** examples. Each
split supplies its exact diagonal operator and noise standard deviation. Coordinates
are independent zero mean Gaussians with decreasing variance. All labels, the seed,
and the generation procedure are public. There is no hidden reward, private target
set, external service, or claimed real world distribution.

Use source training labels to estimate parameters. Use validation and stress labels
only to evaluate the two reference mechanisms in this initial comparison; do not fit
parameters with them. Further mechanisms may be proposed with an explicit assumption
and evaluation plan. A visible stress result is evidence about this public fixture.

## Constraints and deliverables

Use Python's standard library, a fixed dataset, one CPU process, at most sixty
seconds per experiment, and at most three managed executions for the initial
comparison. No network or external solver is needed. Compare a learned source
diagonal linear inverse with an operator and noise aware ridge inverse using source
training estimates of latent variance. This pair is an initial measurement; propose
another mechanism if the evidence exposes a consequential weakness.

For each successful run deliver `artifacts/result.json` version 1 containing finite
source validation and public target stress latent MSE metrics, an explicit evaluation
key and minimization direction, plus labeled `predictions.json` and `method.json`
artifacts. Preserve exact dataset, runnable source, arguments, process outcome, and
limitations so another reader can reproduce the measurement from retained originals.

Complete the task when both mechanisms have comparable retained measurements, a
chosen runnable solution with a justified assumption and limitations is delivered,
and another reader can reproduce its measurements from the delivered originals.
Report whether source and stress rankings agree, explain the decision, and distinguish
public stress performance from unmeasured generalization. If evidence is inadequate
for a choice, identify the missing evidence and the next experiment that can change
the decision. A failed execution supplies no reconstruction measurement.
