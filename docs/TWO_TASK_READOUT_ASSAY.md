# Two tasks from one tissue trajectory

This first assay asks whether a fixed external reader can recover **where** a
short cue occurred and **whether it occurred early or late**, from the same
subsequent tissue trajectory. It implements the first observation experiment in
the [polycomputing design](MULTISCALE_EXECUTION_ARCHITECTURE.md#polycomputing-several-functions-in-the-same-evolving-substrate).
Its results can be negative. Numerical qualification and successful decoding
are separate outcomes; [Progress](../PROGRESS.md) owns run status and evidence.

The [frozen protocol](../validation/assays/two_task_protocol.json) fixes the
input panel, reader, splits, margins, controls and resource bounds before
held-out evaluation. It authenticates the completed BETSE prerequisite and
the unchanged [seven-cell fixture](../configs/betse_spatial_junction.json).
BETSE calibrates and verifies this bioelectric layer of the larger Cells model;
the new cue panel is a synthetic experiment, without a new claim of native
mixed-intervention equivalence or biological calibration.

## Physical inputs and shared execution

All runs use `betse_spatial_nak_kv1p5_dynamic_gj@1`, fixed geometry and the
existing fourteen-array state. They last **64 microseconds**, with 1-microsecond
steps. The longer 256-microsecond array qualification does not extend this
ordinary runtime's declared horizon.

Location selects cell ID 1 or 4. A cue transiently inhibits its Kv1p5 channel
availability for eight microseconds. Early and late pulses occupy [8,16) and
[24,32) microseconds. Inhibition is normalized by source membrane area, so
locations receive the same area-integrated control dose at a given strength.
This matches the imposed control, not the resulting ionic current or energy
use. Pumps and intrinsic channel gates continue evolving.

| Arm | Physical input |
| --- | --- |
| Location only | Location varies; the pulse is fixed at [16,24) microseconds |
| Timing only | Timing varies; the inhibition budget is split across both source cells |
| Joint | Location and timing vary independently |
| Disconnected | Joint inputs with gap-junction availability held at zero |
| No cue | Channel availability remains unchanged |

Each arm executes sixteen worlds: four location/timing pairs at four strengths.
The unused label in a single-task arm creates duplicate physical inputs; those
duplicates are **excluded from scoring**, and do not become extra replicates.
Equal run counts keep solver work comparable: 1,024 steps per arm. No-cue
duplicates deliberately test that task metadata cannot change the trajectory.

These are independent worlds with stable integer IDs, grouped in batches of
four through the existing guarded CPU/GPU runner. Both readers observe each
joint trajectory; adding the second reader never duplicates its physics.
Full histories, inputs, diagnostics, per-batch timing and resource measurements
are retained. Reordering worlds, changing batch partitions, changing observation
cadence and restarting from a complete checkpoint must preserve the trajectory.
This prepares independent-world distribution; it is not a multi-GPU benchmark.

## Readers, calibration and controls

The [passive reader](../src/cells/assays/readout.py) receives only membrane voltage,
physical cell ownership, membrane areas and accepted sample times. It returns
area-weighted voltage for all seven cell IDs at **40, 48 and 64 microseconds**:
21 features, all after cue removal. Two binary classifiers use that shared
support. Each fits two class means, with no feature search or tuned scaling.
Neither reader can access task labels, world IDs, controls, random seeds or
material/clock ledgers as features.

Calibration strengths are 0.4 and 0.8; held-out strengths are 0.5 and 0.7.
Joint and control arms use four predefined folds. Each fold excludes one
complete location/timing combination from calibration and evaluates it at both
held-out strengths: six calibration and two evaluation worlds. Every held-out
world is scored once. Single-task arms score their four unique held-out cases.
These deterministic inputs are not independent biological preparations; no
population confidence interval or significance claim follows.

Reports retain the fitted means, splits, signed scores, predictions, confusion
matrices, per-task accuracy and joint accuracy. A declared **2-nanovolt** distance
margin marks unresolved voltage decisions; this is a synthetic numerical
criterion, not an experimentally calibrated sensor precision. Forced-choice
accuracy and unresolved cases are reported separately. A **1-microvolt** margin
sensitivity and a seven-feature final-time-only reader are also reported.

Two input-only baselines use the same classifier and 21-feature count. One sees
channel availability at the readout times, after the cue has ended. The other
sees availability at 12, 20 and 28 microseconds, while inputs may be present;
it tests the encoding with earlier information and is labelled accordingly.
Thirty-two fixed calibration-label shuffles provide descriptive null results.
No baseline or arm is required to achieve a selected task score to pass the
engineering checks.

Disconnecting gap junctions does not remove extracellular/electrical routes or
direct observations of source cells. Its scores measure this particular route
intervention; failure to reach chance is not evidence of a broken control.
CPU/L4 comparisons use the existing physical-unit tolerances, retain both
sets of decoder outcomes and flag any decision disagreements.

## Interpretation and reproduction

The three-time reader has external post-cue buffering. The final-time-only
reader removes that particular buffer, but neither demonstrates long-lived
memory, a biological consumer, reconstruction through turnover, or heredity.
There is no feedback into the tissue and no invented ATP cost for offline
analysis. Causal consumers and interventions on candidate memory carriers are
later experiments requiring explicit mechanisms and accounting.

The [qualification tests](../tests/unit/test_two_task_readout.py) use the existing
detached runner with `--component-protocol validation/assays/two_task_protocol.json`.
Run outputs belong under `/mnt/workspaces/Cells`; registration freezes source,
inputs and test inventory. Qualification records both GPU-busy and measured
SM-active coverage, without a utilization acceptance threshold. The current
prerequisite paths identify local evidence, not files bundled in a public clone.
The fixture and assay definitions are portable; authenticating this historical
qualification additionally requires its bound evidence artifacts.

## Diagnosing an encoding or readout failure

The [saved-data diagnostic](../validation/assays/two_task_diagnostic.py) investigates
the original failure without changing the protocol, simulator, readers or saved
results. It authenticates the completed evidence and unchanged sources, then
replays the original analysis before applying explicitly post-hoc comparisons.
[Progress](../PROGRESS.md) records the results and next experiment.

Raw input history encodes location and timing **jointly**: each pair inhibits
a different cell/time coordinate. Holding out a whole pair can therefore remove
the entire feature that identifies that input. For a binary task, the omitted
pair's class is calibrated on one remaining pair; the other class averages two.
In an equal-source-amplitude example with mean calibration deficit `m` and test
deficit `a`, the squared distances are `a² + m²` to its own class and
`a² + m²/2` to the other. The centroid rule then predicts the wrong label even
though the input contains the information. A factorized positive oracle with
separate location and timing features does not test this failure mode. The
[diagnostic checks](../tests/unit/test_two_task_diagnostic.py) include this
known-answer counterexample and confirm that no-cue inputs remain unresolved.

The analysis retains two comparisons with distinct interpretations:

- **Balanced calibration:** include all four location/timing pairs at the
  original calibration strengths, then evaluate the original held-out strengths.
  This checks strength generalization, not an unseen combination. Report all
  input and voltage modes, including nulls, without selecting a preferred fold.
- **Fixed input marginalization:** sum channel-availability deficits over time
  for location, or over cells for timing, and keep the original combination
  splits. This checks the known encoding with seven or three features; it is
  neither a tissue measurement nor the original matched 21-feature baseline.

Paired voltage contrasts isolate a change in timing, location or strength while
holding the other two fixed. All original cases are included, including already
inspected evaluation data. Their magnitudes and calibration-direction alignment
describe competing effects; they are not a new fitted reader, a noise model or
a significance test. CPU/L4 agreement alone does not establish temporal accuracy
for a few-nanovolt difference. Such a signal needs a specific refinement check
and a justified resolution criterion before a revised scientific claim. Any
subsequent assay must declare its generalization question, reader and controls
before evaluating fresh inputs; post-hoc success cannot replace the frozen result.

Reproduce this short CPU analysis from the repository root with an unused output
directory (the completed source artifacts must be available):

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. JAX_PLATFORMS=cpu \
OPENBLAS_NUM_THREADS=1 python -B -m validation.assays.two_task_diagnostic \
  /mnt/workspaces/Cells/two-task-diagnosis-reproduction
```

`--source` can point to a relocated copy of the same bound completed evidence.
The tool saves its inputs, diagnostic source, result and completion/failure
artifact. It launches no simulator, GPU workload or follow-up job.

## Timing-refinement follow-up

The [timing protocol](../validation/assays/timing_refinement_protocol.json) tests
whether the weak paired response is stable under temporal refinement. This
resolves a concrete risk: agreement of two devices on large background voltages
does not establish accuracy of their much smaller early/late difference.
It reuses all eighty original worlds at **1, 0.5 and 0.25 microseconds**, preserving
the 64-microsecond horizon, physical event times, doses, geometry, initial state
and readout support. Only the integration step changes. Junction availability
and fixed boundary masks are binary, so this does not introduce the known
timestep-dependent fractional stored-opening block.

For each fixed arm, strength and location, subtract the early-cue voltage vector
from the late-cue vector before comparing resolutions. The report retains all
three 21-feature contrasts, successive changes, magnitudes and direction
alignment. It includes twenty cue pairs and sixteen null pairs; the unused
location label in the timing-only arm is excluded from pairing. Repeated null
inputs are numerical controls, not extra biological preparations.

The **0.5-to-0.25-microsecond** change must be no larger than **2 nV in Euclidean
norm** and **10% of the finest contrast** to meet the declared stability limits.
The finest contrast must separately exceed **4 nV** to exceed the declared reader
scale. These thresholds use the original synthetic reader margin and a fixed
relative-change criterion; they are not measured sensor precision. The original
1-microsecond contrast is compared with the finest result using the same limits.
Successive-change ratios are reported, but first-order consistency is interpreted
only when both changes exceed five times a conservative allowance derived from
the existing voltage comparison tolerances. Small unresolved changes cannot
establish convergence order. These are comparisons between tested timesteps,
not a continuum error certificate or fresh held-out decoding validation.

The [checks](../tests/unit/test_two_task_timing_refinement.py) use known synthetic
contrasts to distinguish null, weak, stable and step-sensitive results. The
simulation panel must reproduce the original same-backend 1-microsecond evidence
under the established field-specific physical tolerances, recording exact
agreement and all nonidentical fields separately. Historical GPU executions can
differ in floating-point rounding; that comparison does not impose bitwise
identity. Within-run reorder, partition, window and snapshot replay remain
bitwise across all fourteen state arrays at the finest step. Conservation/domain
checks and CPU/L4 comparisons retain their existing physical tolerances.
Signal stability remains a reported outcome rather than an acceptance gate.
The existing detached runner accepts this protocol with `--component-protocol`;
it freezes inputs and source, records GPU-busy and measured SM-active coverage,
and writes completion/failure artifacts without scheduling another run.

## Fresh strength interpolation with calibrated response curves

The [template-reader protocol](../validation/assays/template_readout_protocol.json)
addresses the diagnosed calibration geometry and the much larger effect of cue
strength. Its separate protocol is necessary because both the reader and the
generalization question change. The original combination-holdout failure remains
part of the evidence. [Progress](../PROGRESS.md) records execution and outcomes.

All four location/timing combinations are calibrated at strengths **0.4, 0.6 and
0.8**. Four previously unused strengths, **0.45, 0.55, 0.65 and 0.75**, form the
evaluation panel. This tests interpolation in strength with known combinations;
it does not test an unseen location/timing combination. The midpoint supplies
two fixed interpolation segments without adaptive template density. Each of the
five original arms runs 28 worlds, for **140 worlds per backend**. Unused labels
in single-task arms are excluded from fitting and scoring: eight unique
evaluation cases per single task and sixteen per joint/control arm. These remain
deterministic synthetic inputs, not biological replicates.

The [external reader](../validation/assays/template_readout.py) joins the three
calibration observations for each label combination into a piecewise-linear
response curve in the unchanged 21-dimensional voltage space. For each new
observation it computes the nearest point on each of the two segments, clipping
the segment coordinate to its endpoints. Evaluation strength is **not supplied**
to this computation. There is no fitted feature scaling, feature search or
evaluation-label access. All fitting is separate within each physical arm.

For each task, let `d0` and `d1` be the distances to the nearest curves carrying
label 0 and label 1. The score is `(d0 - d1) / 2`; positive predicts 1, otherwise
0. A decision is resolved only when its absolute score exceeds **2 nV**. This
half-gap has voltage units and changes by at most the Euclidean perturbation of
the observation when the calibration curves are fixed. It does not account for
uncertain calibration or establish biological sensor precision. Every curve
distance, inferred segment coordinate, fitted vertex, score and abstention is
retained, including confidently wrong predictions.

The primary outcome is whether both labels are correct and resolved in all
sixteen fresh joint cases; failure does not fail numerical qualification. Fixed
comparisons include balanced centroid reading on the same calibration set,
final-time-only voltage, the **1-uV** margin, earlier input history and input at
readout. Thirty-two seeded permutations relabel whole calibration curves while
preserving their vertices; repeated and identity permutations are retained, with
no significance claim. No-cue and disconnected controls retain their original
interpretations. Neither comparator selection nor changes to the decoder after
seeing these fresh responses are part of this protocol.

Physics, geometry, cue schedules, readout times and the **64-us** horizon remain
unchanged. The simulation uses the prior panel's finest verified **0.25-us**
step; the new strengths do not inherit a separate convergence certificate.
The [checks](../tests/unit/test_two_task_templates.py) reproduce forty shared
calibration trajectories, verify conservation/domain limits and exact replay,
and compare all fresh CPU/L4 histories with existing physical tolerances.
Synthetic projection, encoding, strength-confound, null and calibration-isolation
checks run before simulation. The existing detached runner freezes this protocol
and all source before evaluating fresh responses; it records both GPU utilization
measures and launches no automatic follow-up.

This is one passive external decoder producing two labels from one observation.
It does not introduce causal consumers, feedback or resource costs into the
tissue, and a positive result would establish synthetic decodability rather than
biological polycomputing, reconstruction or heredity.

## Diagnosing weak template margins

The [saved-data geometry diagnostic](../validation/assays/template_diagnostic.py)
authenticates the completed template assay and first reproduces all six reader
modes and all 32 curve-label shuffles on both saved backends. It does not rerun
the simulator or change calibration, margins or archived results.

For each evaluated timing case, it compares the observed voltage vector with
the interpolation on its true calibration curve at its known strength. The
residual measures the sampled mismatch with that linear approximation, including
numerical effects. Moving the observation onto this fixed curve is a diagnostic
counterfactual: the half-gap score can change by no more than the residual's
Euclidean norm. This checks whether removing that particular residual would
bring the timing score above the original margin. It does not correct the
opposite curve or bound curvature between sampled strengths.

Separately, the diagnostic pairs early and late observations at equal strength
and location. It resolves their difference along and perpendicular to the local
strength direction of the opposite-timing calibration curve, retaining both
vectors and the parallel fraction of squared norm. A large parallel component
means that a change in inferred strength can imitate much of the timing change
within this feature space. The actual nearest-curve distances, inferred strength
shifts and endpoint clipping are also retained, so this local projection is not
substituted for the reader's full distance calculation. On flat null curves,
the returned segment position is a tie choice and cannot identify cue strength.

Known strengths, true labels and paired evaluation observations are additional
information used **only for diagnosis**. These probes are not valid replacement
reader scores, fresh held-out validation or biological noise estimates. The
[known-answer checks](../tests/unit/test_template_diagnostic.py) distinguish
linear but confounded curves, orthogonal task effects, calibration curvature,
null responses and altered saved scores. Results and the next experiment belong
in [Progress](../PROGRESS.md).

Reproduce the short CPU analysis using an unused output directory:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. JAX_PLATFORMS=cpu \
OPENBLAS_NUM_THREADS=1 python -B -m validation.assays.template_diagnostic \
  /mnt/workspaces/Cells/template-geometry-reproduction
```

`--source` can point to a relocated copy of the same bound evidence. The tool
saves source hashes, all per-case probes and a completion/failure artifact;
it launches no simulation or follow-up job.

## Distributed source cue

The [distributed-cue protocol](../validation/assays/distributed_cue_protocol.json)
tests a physical input change motivated by the saved response geometry. The
timing-only arm shares its dose equally between both source cells and retains a
larger timing component perpendicular to the strength response. The new
hypothesis is that a **75/25** allocation retains some of that timing component
while its spatial bias still carries location. This single split is the midpoint
between the earlier one-cell cue and the timing-only **50/50** cue; it is fixed
before evaluating new responses, without a mixture search.

Location 0 allocates 75% of the area-integrated inhibition to source cell 1 and
25% to cell 4; location 1 swaps these shares. The location-only, joint and
disconnected arms all use that allocation. Timing-only remains 50/50 and no-cue
remains zero. For source area `A_j`, fractional inhibition is
`strength * share_j * min(A_1, A_4) / A_j`, so unequal source areas cannot change
the total dose. Pulse durations and times, geometry, physical equations,
**0.25-us** step, **64-us** horizon and **40/48/64-us** observations stay fixed.

Calibration retains strengths **0.4, 0.6 and 0.8** with all label combinations.
Evaluation uses **0.425, 0.575, 0.625 and 0.775**, disjoint from every strength
in the earlier panels and chosen symmetrically around 0.6 without inspecting new
responses. The same passive template reader, **2-nV** primary margin, six reader
modes and 32 curve-label shuffles are reused unchanged. The primary target is
both labels correct and resolved in all sixteen fresh joint cases; every
failure and abstention is retained separately from numerical qualification.
This new-panel test does not provide a matched estimate of improvement over
the earlier held-out strengths or establish biological polycomputing.

The [checks](../tests/unit/test_distributed_cue.py) independently integrate each
source's dose and verify pulse timing before any fresh simulation. They reuse
the existing runner, conservation/domain checks, physical CPU/L4 tolerances and
bitwise within-run replay. Twenty-four unchanged calibration worlds in the
timing-only and no-cue arms are compared with authenticated saved evidence;
the deliberately changed location-coded arms are excluded from that historical
reproduction check. All five arms retain equal solver work, with GPU-busy and
measured SM-active coverage recorded. Earlier timestep refinement does not
certify convergence of this changed cue. Execution status and results belong in
[Progress](../PROGRESS.md); no automatic follow-up is scheduled.
