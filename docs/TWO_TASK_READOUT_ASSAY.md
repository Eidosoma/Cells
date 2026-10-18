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

## Refining the distributed cue

The [distributed timing protocol](../validation/assays/distributed_timing_protocol.json)
checks a concrete risk in the successful 75/25 panel: a nanovolt-scale decoding
margin needs temporal checks on this changed physical cue. It authenticates and
reuses the completed **0.25-us** trajectories, then simulates all 140 cases at
**0.125 and 0.0625 us**, giving **280 new worlds per backend**. Source shares,
doses, events, initial state, geometry, strengths and the **64-us** horizon stay
fixed. These are already inspected cases, so this is numerical self-refinement,
not fresh held-out validation. Re-evaluating the saved coarse observations must
exactly reproduce the previous three-time and final-time voltage reader reports.

The [analysis](../validation/assays/distributed_timing.py) reports two calibration
conditions for both voltage observation modes. Resolution-matched calibration
fits the unchanged template algorithm to calibration rows at each timestep.
Frozen-coarse calibration always uses the saved 0.25-us calibration curves and
changes only the evaluation observations. The latter exposes common voltage
shifts that recalibration could hide. Neither condition uses evaluation strength
or labels to fit or predict, and both are retained without choosing whichever
gives a better outcome. Known-answer checks include a shared response shift
that preserves decoding after recalibration but changes fixed-reader decisions.

For each evaluated task, the **0.125-to-0.0625-us signed score change** must be no
larger than both **2 nV** and **10% of the absolute finest-step score** to meet
the declared drift criterion. Prediction and abstention changes, correctness at
every level and the original-to-finest comparison are reported separately.
The primary question is whether the resolution-matched three-time reader retains
both correct and resolved labels in all sixteen joint cases at every step, with
stable finest-step scores and decisions. The **2-nV** abstention margin remains
unchanged. Exact null scores have zero relative allowance and cannot count as a
positive decoding result.

The earlier paired-contrast analysis is reused for all **63 early/late pairs**,
including **28 null pairs**, with its existing absolute, relative and
convergence-order interpretation limits. A passing numerical suite does not
require stable contrasts or successful decoding. No tested-step comparison is a
continuum error bound or biological noise model; disconnected and source-cell
readout limitations remain.

The [checks](../tests/unit/test_distributed_timing.py) preserve all new full
trajectories on disk as four-world batches finish, retaining only readout
vectors and four finest-step worlds for replay. CPU/L4 arrays are compared one
world at a time using existing physical tolerances; within-run reorder,
partition, window and snapshot replay remain bitwise. Finer traces require a
**4-GiB** batch working bound and **12-GiB** artifact/cache allowance; the
**8-GiB** worker RSS and **40-minute** wall limits remain. Every arm has equal
solver work, and both GPU utilization measures are recorded. The runner freezes
source and inputs before new simulation and schedules no follow-up job.

## Reading unstimulated cells

The [unstimulated-cell protocol](../validation/assays/unstimulated_readout_protocol.json)
tests a limitation of the earlier reader: it could directly observe both
stimulated source cells. The primary observation now contains only cells
**2, 3, 5, 6 and 7**, excluding sources **1 and 4**. All five cells are selected
before new responses are simulated, without searching for a favorable subset.
Area-weighted voltage at **40, 48 and 64 us** gives **15 features**. A separate
all-seven-cell reader provides a comparator on the same inputs; its features
and calibration cannot enter the primary fit.

Calibration and evaluation both use **0.0625 us**, the finest step in the
completed temporal audit. This explicit operating point avoids mixing response
curves from different timesteps. The previous audit does not independently
certify convergence of the restricted reader or its new test strengths.
Physical equations, geometry, 75/25 source allocation, dose, pulse times and
**64-us** horizon remain unchanged. Calibration retains **0.4/0.6/0.8**;
fresh evaluation uses **0.4375/0.5625/0.6375/0.7625**, disjoint from previous
panels and chosen symmetrically around 0.6 before inspecting new responses.

The unchanged template algorithm and **2-nV** margin are fitted separately
in each arm and observation mode. Both labels must be correct and resolved
in all **16 joint cases** to meet the primary scientific target. The final-time,
1-uV-margin, centroid, all-cell and input-only comparators, plus the 32 fixed
curve-label shuffles, are all retained. Input history on the five unstimulated
cells is a null control because their channel controls never change. Successful
decoding is an outcome, not a requirement for numerical acceptance.

The disconnected arm uses the same restricted support. It helps assess the
role of junctions, but leaves extracellular and electrical coupling available;
separate per-arm calibration also does not test reader transfer. Even a positive
result would establish synthetic decodability by an external reader, not
biological sensing, multiple causal consumers or polycomputing.

The [checks](../tests/unit/test_unstimulated_readout.py) verify source-cell
exclusion with synthetic perturbations and confirm that evaluation metadata
cannot change predictions. They stream **140 worlds per backend** to disk,
reproduce all **60 calibration worlds** against authenticated finest-step
trajectories, and preserve conservation, physical CPU/L4 tolerances and bitwise
reorder, partition, window and snapshot replay. Each arm executes **28,672
panel steps**. Both GPU utilization measures are recorded; compilation and
host work remain included. Results and job status belong in
[Progress](../PROGRESS.md).

## Diagnosing weak unstimulated signals

The [saved-trajectory diagnostic](../validation/assays/unstimulated_diagnostic.py)
separates small propagated signals from ambiguity in the calibrated reader.
It authenticates the completed unstimulated-cell panel and reproduces all seven
reader modes and 32 label shuffles. It then reconstructs voltage at every saved
step using the same charge, capacitance and boundary-potential law, checking the
result against the archived membrane voltages and reader observations. Cell
averages retain the reader's membrane-area weighting; the legacy arithmetic
patch mean is a different observable. No transport is integrated again.

At fixed strength and other input label, location and timing pairs supply
separate source-cell and unstimulated-cell time courses. The diagnostic records
all pairs, their three-time feature distances and their final-interval trends.
For the existing fixed-curve score, which is 1-Lipschitz, both opposite-label
cases can clear margin `m` only if their feature distance exceeds `2m`.
This is a necessary condition, not a guarantee of successful decoding.

The earlier strength-tangent and calibration-residual probes are applied to
both tasks. Known labels, strengths and paired counterparts are used only to
explain the saved failure; they do not enter a replacement reader. These are
post-hoc diagnostics, without new holdouts, threshold tuning or convergence
claims. Trends through **64 us** cannot establish behavior beyond that horizon.
This diagnosis used the ordinary dynamic-junction runtime qualified through
**64 us**. Its **256-us** extension has since passed separate CPU/L4 numerical
qualification, recorded in [PROGRESS](../PROGRESS.md). The longer-observation
assay is defined below; the earlier reader results remain frozen. The
[known-answer checks](../tests/unit/test_unstimulated_diagnostic.py) cover voltage
reconstruction, area weighting, pair-distance limits, signal trends and the
distinction between strength ambiguity and interpolation error.

## Longer observations with the same cues

The [long-observation protocol](../validation/assays/long_observation_protocol.json)
tests whether more propagation time improves the restricted readout. Its purpose
is to separate a horizon effect from stronger stimulation, extra features,
reader retuning or timestep sensitivity. All 140 cases from the unstimulated
assay are reused, including calibration strengths, evaluation strengths, five
arms, physical cell identities, source shares and pulse doses/times. This is a
controlled extension of already inspected cases, not fresh generalization or
independent biological replication.

Three observation panels each retain exactly **15 primary voltage features**:
**40/48/64 us**, **80/96/128 us**, and **160/192/256 us**. All exclude source cells
1 and 4. The last panel at **dt = 0.0625 us** is the predeclared primary endpoint;
the earlier panels and separate all-cell/final-time comparators cannot replace
it after results are seen. The unchanged template algorithm is fitted only to
calibration rows, separately for each panel and timestep, at the same **2-nV**
margin. Every inherited reader mode and all 32 fixed shuffles are retained.

All worlds run through **256 us** at **0.25, 0.125 and 0.0625 us**. In addition to
matched calibration, readers frozen at the coarsest step expose shared numerical
shifts. Both label contrasts and signed reader scores use the existing absolute
and relative stability thresholds. Stability, resolution and decoding failure
remain scientific outcomes, with no threshold changes or continuum-error claim.
The finest run's first 64 us is compared with every archived original world,
including its original readouts; those earlier results remain frozen.

Four-world batches use **1,024-step windows**. Every state array and sampled field
is written to disk, with complete per-world inputs and window boundaries;
memory retains only the current window and compact readout vectors. Reordering,
partitioning and a disk restart at **127.9375 us** with a changed window size
must reproduce the saved histories and observations exactly. Every arm has the
same **200,704 world-step** budget per backend across the three timesteps.
CPU/L4 comparisons, conservation/domain checks, GPU-busy and measured SM-active
are recorded separately from the decoding outcome. Current results and run
artifacts are tracked in [PROGRESS](../PROGRESS.md).

## Wider cue separation at fixed dose

The [cue-separation protocol](../validation/assays/cue_separation_protocol.json)
tests one change suggested by the unresolved timing signal: move the late pulse
from **24–32 us to 104–112 us**, keeping the early pulse at **8–16 us**. This
increases onset separation from **16 to 96 us**, without increasing the **8-us**
pulse width or either source's area-integrated inhibition. The single sixfold
separation is fixed before new responses are simulated; this is not a search
over cue times. Location-only cues remain at **16–24 us**, and the original
75/25 location allocation and 50/50 timing-only allocation stay fixed.

The primary endpoint remains **15 unstimulated-cell voltage features at
160/192/256 us**, at **dt = 0.0625 us**, with the same **2-nV margin**. Both cues
have ended before this endpoint: the first primary observation is **48 us**
after the late pulse ends. The three-strength calibration curves are fitted
to the new responses using the unchanged reader algorithm, separately by panel
and timestep; evaluation rows cannot fit the curves. The same four evaluation
strengths have already been inspected, so this tests a controlled intervention,
not fresh generalization. Correct forced choices, resolved decisions and
finest-step stability remain distinct outcomes.

The earlier **40/48/64-us** panel now precedes the late pulse, and the
**80/96/128-us** panel spans it. They remain visible comparisons, but cannot
replace the primary endpoint or demonstrate decoding after both cues.
All inherited reader modes, 32 label shuffles, matched/frozen-coarse calibration
and paired location/timing contrasts are retained without lowering tolerances.

The [implementation](../validation/assays/cue_separation.py) reuses the completed
long-observation assay's reader, observation and archive functions. The same
runner executes **420 worlds per backend**, equally budgeted across five arms,
at all three timesteps through **256 us**. Only **42 of the 140 case inputs**
change. The [checks](../tests/unit/test_cue_separation.py) compare all windows of
the **98 unchanged cases** with authenticated saved histories at each timestep.
For changed cases, they compare the common prefix strictly before the old
24-us onset. They preserve comparisons of unchanged features and reader reports
from the unchanged location-only and no-cue arms.

Nonintegrating preparation checks verify every control sample, pulse boundary,
per-source dose, observation support and memory budget. A disk restart at
**103.9375 us** in a delayed-cue world crosses the new **104/112-us** events
using **257-step** windows; reordered and partitioned replay also remain exact
requirements. Numerical/domain/conservation checks, CPU/L4 comparisons and
both utilization measurements remain independent of scientific success.
The preceding assay's registered source files and evidence remain unchanged.
Current execution status and results belong in [PROGRESS](../PROGRESS.md).

The [saved-data diagnosis](../validation/assays/cue_separation_diagnostic.py)
replays the original reader reports and shuffles at all three timesteps, then
reconstructs the 28 joint-case voltage histories from authenticated windows.
Shared window endpoints must agree and are counted once; reconstructed voltages
must reproduce archived observations and all three panels' voltage features.
The existing pair-distance, strength-direction and calibration-residual probes
describe the primary timing cases. Saved control-arm features supply comparisons.

For each adjacent timestep pair, the diagnosis also crosses the two saved
readers with the two sets of observations. This separates score changes caused
by changed voltage features from those caused by changed calibration curves,
reporting both orders because these contributions can depend on order.
The [known-answer checks](../tests/unit/test_cue_separation_diagnostic.py) cover
window seams, corrupted observations and a common shift hidden by recalibration.
No integration, new calibration scheme, observation-time selection or threshold
adjustment occurs. The three finite timesteps and post-hoc geometry do not
establish a continuum error bound or fresh generalization.

The [baseline-transfer diagnostic](../validation/assays/baseline_transfer_diagnostic.py)
tests whether the saved no-cue response accounts for common timestep drift.
It uses the lowest-ID no-cue calibration case as one shared reference per
backend and timestep, and verifies that every duplicate no-cue observation is
identical. Stimulated cases, evaluation strengths and task labels do not fit
this reference. Only the original **15-feature long256 voltage panel** is used.
All nine source/target timestep combinations and all five arms remain reported.

Subtracting a common reference from both calibration vertices and observations
must preserve matched curve distances, scores and resolved decisions within the
inherited replay tolerance. Any roundoff-level forced-label differences in
unresolved nulls remain visible. For transfer, source response curves remain
fixed in these translated coordinates and the target observation uses its own
no-cue reference. This supplies target-domain control information; it does not
demonstrate transfer without that information. The
[known-answer checks](../tests/unit/test_baseline_transfer_diagnostic.py) separate
a removable common offset from cue-dependent changes that subtraction must
retain. Translation cannot improve within-timestep separation of timing from
strength. Original scientific outcomes and thresholds remain fixed.

## Location allocation and source-pulse order

The [source-order protocol](../validation/assays/source_order_protocol.json)
tests a new temporal question: **which of the two source cells was stimulated
first?** Each source receives one **8-us** pulse. Order 0 applies source 1 at
**8–16 us** and source 4 at **104–112 us**; order 1 reverses these assignments.
Location retains the **75/25 versus 25/75** division of the total cue dose.
The order-only arm uses equal source doses, and location-only retains its
simultaneous **16–24-us** pulses. Each source's integrated inhibition at a given
strength equals that in the preceding common-pulse encoding. This task does
not complete or replace the earlier common early/late classification result.

Calibration strengths remain **0.4, 0.6 and 0.8**. Four evaluation strengths,
**0.45625, 0.54375, 0.65625 and 0.74375**, are fixed before simulation and are
disjoint from the earlier protocol panels. All label combinations occur in
all five arms, giving **140 identities at each of three timesteps** per backend.
The primary result still uses the **15 voltages from unstimulated cells** at
**160/192/256 us**, matched calibration at **0.0625 us**, and the **2-nV** margin.
Earlier panels, alternative readers and baseline-assisted transfer remain
comparisons. Internal `timing` and `timing_only` keys are compatibility names
for source order; reports carry their explicit meanings. The new strengths
test interpolation within this deterministic tissue, not biological replication.

The [acceptance checks](../tests/unit/test_source_order.py) independently verify
every control sample and per-source dose without integrating during preparation.
Across the three timesteps, **120 worlds** reproduce unchanged predecessor
histories and features: all no-cue cases and location-only calibration cases.
The remaining **300 worlds** reproduce only the common history before **8 us**.
New strengths and source-order responses are not required to match old responses.
Full state archives, conservation and domain checks, CPU/L4 tolerances, restart
across the second pulse, reordering and partitioning reuse the established
runner. All **986** preceding assay and diagnostic sources remain unchanged.

All nine source/target timestep transfers also use a shared no-cue calibration
reference, with unchanged matched scores checked explicitly. This comparison
supplies target-timestep control information and cannot replace the primary
endpoint. Numerical acceptance, task resolution and timestep stability remain
separate outcomes. Each arm has the same world-step budget; GPU-busy and measured
SM-active utilization retain their sampling coverage. Execution status belongs
in [PROGRESS](../PROGRESS.md).

The [source-order diagnosis](../validation/assays/source_order_diagnostic.py)
authenticates the completed archive and replays all reader and baseline-transfer
reports before examining the joint failures. For each task it distinguishes a
competing curve that changes one label from a curve that changes both. Two
oracle probes separately supply the true other label or the true cue strength;
they describe missing information and cannot replace the original reader.
The inherited interpolation-residual probe tests whether moving the observation
onto its known calibration curve would change the score.

Contrasts between the four label combinations at each strength describe the
directions of the two effects and their possible cancellation. This is an
algebraic description, not evidence of a causal nonlinear interaction. Complete
joint voltage histories also retain both one-label and two-label differences,
including their late-time trends. Timestep attribution uses both orders of
crossing fixed readers with fixed observations, before and after subtracting
the no-cue reference. The [known-answer checks](../tests/unit/test_source_order_diagnostic.py)
separate label collisions, strength ambiguity, shared offsets and genuine
threshold crossings. These post-hoc probes leave the source-order endpoint,
margin and failed cases unchanged.

### Later observations with the same source-order cues

The [512-us follow-up protocol](../validation/assays/source_order_long/protocol.json)
tests whether waiting longer separates the overlapping remote responses. Its
primary panel is fixed at **320/384/512 us**, before simulating beyond the
previous endpoint. The same 140 identities, strengths, pulse timing, per-source
doses, five arms, three timesteps, tissue and initial conditions are retained.
The reader still uses **15 unstimulated-cell voltages**, matched calibration at
**0.0625 us** and the **2-nV margin**. These are reused evaluation cases in a
paired follow-up, not a fresh holdout cohort. Earlier panels and other readers
cannot replace the later primary result.

The [checks](../tests/unit/test_source_order_long.py) compare all **420 world
histories per backend through 256 us** with their saved predecessors. All three
earlier feature panels and their complete reader reports must reproduce exactly.
The numerical laws and tolerances are unchanged; the work ceiling rises to
8192 steps solely to retain the finest timestep through 512 us. Four-world
batches and 1024-step windows keep the existing memory bound. Complete state
archives, conservation/domain checks, CPU/L4 comparisons, reordered/partitioned
worlds and disk restart across the second pulse extend through the new endpoint.

The protocol binds the completed 512-us native runtime qualification and the
saved-data source-order diagnosis. The former covers its fixed synthetic cases
at 1/0.5/0.25 us; the assay separately retains 0.25/0.125/0.0625-us refinement.
Task resolution and score stability remain reported scientific outcomes,
separate from numerical acceptance. Equal world-step budgets, actual arm
timings and both utilization measurements remain recorded. Results and run
status belong in [PROGRESS](../PROGRESS.md).

The [charge-precision repair protocol](../validation/assays/source_order_long/precision_protocol.json)
retains this experiment while correcting cancellation in the ionic charge sum
that drives membrane voltage. It sums signed concentrations with compensation
before multiplying by Faraday's constant; the physical equation and all
tolerances remain unchanged. Independent 80-digit arithmetic checks exercise
near-neutral mixtures, and all 18 configured native BETSE reference trajectories
are compared again on CPU/L4 using the authenticated saved captures.

For this arithmetic correction, older 256-us histories and features are compared
with their existing numerical tolerances, with bitwise equality and all earlier
reader-decision differences reported separately. Original archives and scientific
reports remain frozen. Restart, windowing and world reordering within the
corrected implementation still require bitwise agreement. The failed 512-us run
is diagnostic evidence, not a successful acceptance reference.

The [saved-feature diagnosis](../validation/assays/source_order_long_diagnostic.py)
replays all four observation panels and the reference-assisted reports from the
completed precision repair. It compares the 256-us and 512-us results using the
existing competing-curve, true-strength, true-other-label and interpolation
probes. These probes distinguish ambiguity with cue strength from weak order
responses without supplying hidden information to the original reader.

One exploratory comparator uses the same five unstimulated cells at **128, 256
and 512 us**, after both source pulses have ended. Earlier transient and later
response samples may separate order from strength. It retains **15 voltage
features**, the same calibration-only reader, all five arms, three timesteps,
fixed label shuffles and the **2-nV margin**, with no rescaling or search over
observation times. The original 320/384/512-us primary result remains fixed.
These are inspected cases; any promising comparator needs a separate registered
experiment with new evaluation strengths. Execution and outcomes belong in
[PROGRESS](../PROGRESS.md).

The [confirmation design](../validation/assays/source_order_long/spanning_confirmation_plan.json)
fixes eight new strengths spanning both calibration intervals, including weak
cues, and pairs the spanning and late-only observations on the same trajectories.
The [execution protocol](../validation/assays/source_order_long/spanning_protocol.json)
and [checks](../tests/unit/test_source_order_spanning.py) implement that fixed
design: **32 joint evaluation cases**, five arms, three timesteps and **660
worlds per backend**. Both observation panels retain 15 voltage features and
the same calibration cases and margin. Per-case paired results retain gains,
losses and unresolved cases; improvement is separate from complete resolution.

The established windowed harness receives module-scoped protocol and cohort
parameters, restored after the checks. Its integration, archive, restart and
CPU/L4 comparison paths remain unchanged. All calibration and no-cue histories
must reproduce the accepted precision repair bitwise through 512 us; the new
stimulated evaluation cases reproduce their common pre-cue history through
8 us. Explicit old/new identity mappings and unchanged calibration curves are
checked. Each arm has **630,784 world-steps per backend**, with actual arm
timings and both GPU utilization measurements recorded. The saved design is a
historical artifact; registration, launch and results are recorded only in
[PROGRESS](../PROGRESS.md).
