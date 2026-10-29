# Explicit passive INIT-to-SIM handoff

The operation prepares a new `resolved_membrane_profile_epoch@1` simulation from
an accepted `resolved_membrane_profiles@1` INIT checkpoint. The Chief owns shared
dispatch, ensemble integration and shared status. All runtime changes are in
new owned adapter/spec/model files; qualified scheduled dynamics and numerical
engines remain unchanged.

## Physical contract

The source is an ordinary scheduled passive INIT definition and complete
checkpoint. Its accepted grid position, input position, numerical phase clock,
typed state/layout, padding, actual-control field and all original accounting
checks must pass. A seal covers the full definition, clocks and typed arrays.
Each array records its dtype, shape and scalar values, with lossless integer
owner validation and strict float/int/bool distinctions.

The new SIM definition retains the exact physical model, original inventory and
charge anchors, full static profile/default preparation, physical owner order
and padded capacities. Version 1 permits explicit new SIM events, zero-based
controls, horizon, timestep and intervention padding. It refuses changed static
preparations/defaults, physical owners, references or capacity remaps. This
scope avoids inventing a changed-default or changed-route history policy.

All twelve parent arrays carry forward exactly: intracellular/extracellular
increments, membrane/junction/face transfers, reservoir supply, all three
dissipation integrals, electrode charge, reservoir work and electrode work.
No array is zeroed or rebased. The original INIT reference amounts, charges,
capacitor voltages and physical geometry remain the accounting origin. The new
state therefore checks the complete INIT-plus-SIM history with the same passive
equations. The only reset state field is the one-entry `phase_clock_s`.

The source checkpoint's accepted time and actual numerical phase clock are both
archived. The new SIM accepted time, step and phase clock start at zero with the
new control schedule's initial event position. Observations expose the archived
INIT phase clock and accepted INIT time plus current SIM clock as elapsed time.
Ordinary snapshot resume preserves SIM clock and history. Distinct epoch state
and layout types, model identity and source record prevent ordinary resume or
branch from performing an INIT-to-SIM transition.

An accepted interior INIT checkpoint may be deliberately selected as the end of
initialization; the complete original definition and selected checkpoint remain
archived. This is an explicit operation, not an implicit truncation during
resume. Validation proves checkpoint compatibility and accounting, without
recomputing an arbitrary user's entire prior trajectory. Manufactured evolved
INIT controls are separately compared with an independent adaptive solution.

## Native phase scope

Pinned `SimRunner.sim` loads the evolved INIT simulator, supplies it to a new SIM
phase and does not call `init_core`. `run_sim_core` calls `init_dynamics`, clears
output storage, updates voltage and builds a phase-local time vector from zero.
`init_profiles` restores declared membrane diffusion; `init_dynamics` copies
that static baseline into Dm_base and zeros Dm_scheduled.

The declared reset policy replays the identical qualified static preparation
and native defaults, copies its baseline diffusion and zeros the scheduled
buffer before the first SIM pulse evaluation. The frozen membrane kernel then
applies its smooth logistic tails at each RK stage. A zero buffer does not mean
zero pulse at SIM time zero. INIT scheduling remains inactive. Optional native
noise, channels, pumps, pressure/ECM and other writers are outside this passive
model. No native solver-loop trajectory parity is claimed.

## API and artifacts

`cells.core.membrane_profile_phase_handoff` provides `capture_source`,
`prepare`, `replay`, `write_preparation` and `read_preparation`.
`cells.core.surface_profile_epoch_spec` provides `SurfaceProfileEpochModel`,
`parse`, `to_dict` and `scheduled_spec`.

```python
from copy import deepcopy
from cells.core import membrane_profile_phase_handoff as handoff
from cells.core import surface_profile_epoch_spec as epoch
from cells.core import surface_profile_interventions_spec as scheduled

# init_spec and init_checkpoint describe an accepted evolved INIT state.
# sim_spec explicitly declares the new SIM experiment and event schedules.
request = {
    "kind": handoff.REQUEST_KIND,
    "policies": deepcopy(epoch.POLICIES),
    "source": handoff.capture_source(init_spec, init_checkpoint),
    "simulation": scheduled.to_dict(sim_spec),
}
prepared = handoff.prepare(request)
sim_epoch = epoch.parse(prepared.definition)
handoff.write_preparation("new-sim-epoch", prepared)
assert handoff.read_preparation("new-sim-epoch") == prepared
```

The portable definition embeds the complete source and reset contract. The
sealed provenance retains the complete request, both clocks, reset arrays,
original-owner preservation checks and prepared-definition identity. Replay
rebuilds and compares the entire artifact. Output directories do not overwrite
existing paths. Original checkpoint files, qualified examples and runtime input
paths are not required to replay the embedded source.

## Qualification and integration

The protocol pins the native files/function ASTs, frozen scheduled model and
independent references. Scientific checks use evolved INIT trajectories, exact
handoff invariants, complete post-handoff fields/RHS/potentials, owner-loop
material/charge balances and Decimal chemical/capacitor/work accounting. SIM
continuation starts from nonzero INIT histories and is compared with independent
segmented DOP853 integration and RK4 refinement. Refusals cover corrupted owners,
history, clocks, typed arrays, reset records and ordinary resume/branch attempts.
Separate bounded CPU processes check compiled JAX RHS/isolation and short eager
public execution with exact snapshot resume and both observed clocks.

The isolated workspace starts from the immutable qualified scheduled
Development03 engine, overlays only the three new runtime files and applies
two test dispatch routes. Root's concurrent live runner/window repair does not
change this captured engine. The separate proposed shared patch uses Root's
post-profile-integration specs/registry/ensemble bases and remains unapplied.
The handoff receipt records exact hashes, result counts, resource guards and
portable examples. Shared public integration checks remain the Chief's work.
