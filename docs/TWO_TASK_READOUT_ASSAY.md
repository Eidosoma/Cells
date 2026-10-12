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
