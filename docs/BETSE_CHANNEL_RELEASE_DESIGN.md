# REF-004d: channel suppression/release, input design

D101, 2026-09-15. D100's [independent paired-history closeout](../reports/REF004C_PAIRED_HISTORY_CLOSEOUT.md)
passes. The next question is whether a transient transport block preserves
different intrinsic channel histories and gives different responses on release.
This step checks **input semantics and instantaneous model composition**, not
a new trajectory, native dispatch, physiological drug model or memory experiment.

## Reuse the architecture, change experiment data

Keep the seven cells, one shared finite bath, K-only Kv1p5 channels, matched
constants, 298.15 K and separate initial histories a/b. Existing production
`finite_extracellular@1` already separates intrinsic m/h, maximum permeability,
abundance and experimental availability. No new state, kernel, solver, organ
branch, framework or GPU implementation is needed for the proposed input.

The [design settings](../validation/betse/channel_release_design/plan.json) propose
one square availability block between 0.5 and 1 ms inside a 2 ms window:

| Condition | Before 0.5 ms | 0.5 to 1 ms | From 1 ms |
| --- | --- | --- | --- |
| Baseline | 1 | 1 | 1 |
| Explicit no-op switches | 1 | 1 | 1 |
| Static availability block | 0 | 0 | 0 |
| Suppression/release | 1 | 0 | 1 |

Both histories use the same schedules. Even the static block retains a positive
intrinsic maximum permeability: it tests availability, unlike D099's zero-maximum
control. No background leak, pump, junction, noise, chemistry or geometry change.
The existing 2 ms horizon is a **candidate**, not evidence that the new response
is resolvable or representative of slower recovery. Do not select or extend it
from the saved initial-rate or constant-input evidence. Register a future
reference/domain/signal gate before running coupled release trajectories.

## Native boundary: prescribed input, not a BETSE tissue event

The pinned FULL network [channel loop](../upstream/betse-v1.5.0/betse/science/chemistry/networks.py:3115)
evaluates its molecular modulation, advances gates, then uses
`DChan = P * rel_perm * maxDm * moddy` for channel transport. The
[Kv1p5 gate path](../upstream/betse-v1.5.0/betse/science/channels/vg_k.py:76)
does not consume `maxDm` or `modulator` in its kinetic update. Source-byte and
structural checks support this statement only for this pinned path, not other
channel families or FAST behavior.

Propose an explicit, host-side numeric parameter intervention:

`maxDm(t) = immutable_unsuppressed_maxDm * availability(t)`

Restore from the immutable baseline on every application, not by multiplying
the previously blocked value. Keep the pre-existing constant modulation,
relative permeability, thickness, abundance and targeting unchanged. Do not
write arbitrary `eval` expressions, change the upstream implementation, replace
the gate updater or reset m/h. This is an adapter-applied external input, **not**
an unmodified built-in BETSE suppression/recovery event, inhibitor chemistry,
ligand occupancy or evidence of a drug's action. It remains unexecuted here.

The earlier REF-003e passive tissue pulse changed a different permeability path
using a smooth additive waveform. Its successful dispatch cannot qualify this
channel intervention. Reusing that event would not necessarily block channel
transport at all. Retain the existing FULL INIT preparation for the first
candidate; SIM/profile transitions would introduce a separate question.

## Clock, conservation and state boundaries

- Define input at elapsed step boundaries, right-continuously. The proposed
  switch times lie exactly on all native 25/12.5/6.25 microsecond and Cells
  50/25/12.5 microsecond grids. Integer/Decimal input generation does not sample
  BETSE's inclusive endpoint-labelled loop clock. Record both clocks and prove
  their mapping in the future native preflight.
- All stages of a Cells interval hold its left-boundary input, including the
  left interval's endpoint slope. An observation at a switch uses the new input.
  No state or accumulated transfer jumps. Observer times do not alter the grid.
- A zero availability gives exactly zero channel transport and its associated
  amount, current and dissipation rates; **intrinsic m/h still evolve**. Blocking
  one contribution is not freezing the entire cell or clearing past ledgers.
- Every membrane transfer has one intracellular owner and one opposite shared-
  bath contribution. Gate variables are not material inventories. State-dependent
  voltage and gate rates must use the same solver stage as those transfers.
- A release may change instantaneous current at continuous state. Distinguish
  fresh right-sided current from the preceding interval's integrated current;
  never compare them as if they were the same observable.
- Future piecewise reference integration must restart each solver at exact input
  boundaries with the complete continuous state. Preserve distinct one-sided
  slopes; do not interpolate a smooth polynomial across a discontinuity. A block
  interval has an analytic held-voltage gate check in this no-other-flux fixture.

## What this step actually checks

The new validation-only [compiler/source checks](../validation/betse/channel_release_design/release_design.py)
and [model probes](../validation/betse/channel_release_design/release_probes.py)
compile eight data-defined configurations and inspect all 24 candidate Cells
grids through the real resource/timeline guards. Test switch-adjacent floats,
right-continuous controls, unchanged other inputs, padding and observer independence.

At six **already saved active states** (a/b at 0, 0.5 and 1 ms), evaluate
availability 0, 0.25 and 1 on NumPy, eager JAX and compiled JAX: 54 instantaneous
RHS/readout probes. Those are not release-trajectory states. Independently
reconstruct every complete RHS using D094's 80-digit equations and D097's
explicit ownership assembly, reusing D097's unit-specific instantaneous budgets.
Check exact blocked zeros, unchanged gate rates, quarter-availability scaling,
all nonzero stored transfer history, full state/layout/input non-mutation and
negative/corruption controls. Integration entry points are forbidden in these
software probes. No checkpoint is newly executed or qualified.

The software result belongs in a separate report. No detached simulation or
follow-up audit is launched by this design. Existing sources, original pending-
audit receipts and all 21 coarse misses stay unchanged. No production release,
broader BETSE parity, native restart or biological qualification follows.

## Following bounded steps

1. Native input-application/single-update preflight: actual prepared channel
   objects, both histories, matched baseline/no-op/block/release inputs. Prove
   parameter-only application, untouched full state/ledgers, absolute restoration,
   gate-first order, targets, clock mapping and one conservative transport update.
   Observe/record native values; static source inspection is insufficient.
2. After reviewing that evidence, register piecewise independent references and
   signal/domain/convergence criteria. Separate input correctness from response
   qualification; do not tune a criterion to obtain a positive memory result.
3. Only then run the smallest own-state paired comparison, with no-op/blocked
   controls, fixed-input refinement, complete switch/restart state and separate
   saved-data audit. Long jobs launch detached and return for user status, with
   no automatic polling, retries or follow-up work.

For future GPUs the schedules remain bounded numeric arrays, gates remain local
state, and shared-bath transfers require a stage-consistent reduction. Independent
history/world pairs can batch; cells sharing a bath cannot be treated as
independent simulations. A source-specific host input adapter does not belong
inside a compiled production kernel. No optimization or GPU work is needed now.
