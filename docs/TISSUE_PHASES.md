# Carrying INIT state into SIM

`cells tissue-phase` prepares an explicit new SIM experiment from an accepted
INIT checkpoint. Material, charge, geometry, intrinsic gates and accounting
history carry forward exactly. The original accounting references remain in
place, so transfer and energy balances cover INIT and SIM together.

| INIT model | Prepared SIM model | Carried parent state |
| --- | --- | --- |
| `resolved_membrane_profiles@1` | `resolved_membrane_profile_epoch@1` | All 12 passive physical/history arrays |
| `resolved_active_membrane_profiles@1` | `resolved_active_membrane_profile_epoch@1` | All 19 active arrays, including channel/junction gates, channel transfers, pump cycles, heat and maintained-fuel work |
| `resolved_active_profile_barriers@1` | `resolved_active_profile_barrier_epoch@1` | All 19 active arrays, with membrane and extracellular schedules evaluated on the new shared SIM clock |
| `resolved_calcium_profile_barriers@1` | `resolved_calcium_profile_barrier_epoch@1` | All 34 full-catalog calcium arrays, including chemical stores and their histories, with both schedules on the new SIM clock |
| `resolved_calcium_energy_profile_barriers@1` | `resolved_calcium_energy_profile_barrier_epoch@1` | All 38 finite-fuel arrays, including current pools and regeneration histories, with both schedules on the new SIM clock |
| `resolved_calcium_energy_water_profile_barriers@1` | `resolved_calcium_energy_water_profile_barrier_epoch@1` | All 43 physical arrays, including actual volumes, fuel and water/work histories, with both schedules on the new SIM clock |
| `resolved_calcium_energy_water_repair_profile_barriers@1` | `resolved_calcium_energy_water_repair_profile_barrier_epoch@1` | All 48 physical arrays, including damage, injury transfers and repair histories, with both schedules on the new SIM clock |
| `resolved_calcium_membrane_profiles@1` | `resolved_calcium_membrane_profile_epoch@1` | All 34 calcium/ER arrays, including free/bound inventories, gates, reactions and pump/transport history |
| `resolved_calcium_energy_membrane_profiles@1` | `resolved_calcium_energy_membrane_profile_epoch@1` | All 38 finite-fuel arrays, including the actual ATP/ADP/phosphate pools and regeneration/work history |
| `resolved_calcium_energy_water_membrane_profiles@1` | `resolved_calcium_energy_water_membrane_profile_epoch@1` | All 43 physical arrays, including current water volumes, finite fuel and original water/work accounting |
| `resolved_calcium_energy_water_repair_membrane_profiles@1` | `resolved_calcium_energy_water_repair_membrane_profile_epoch@1` | All 48 physical arrays, including damage, injury transfers and repair heat history |
| `resolved_active_extracellular_barriers@1` | `resolved_active_extracellular_barrier_epoch@1` | All 19 full-catalog ionic arrays, including gates, transfers and maintained-fuel work |
| `resolved_calcium_extracellular_barriers@1` | `resolved_calcium_extracellular_barrier_epoch@1` | All 34 calcium arrays, including chemical stores, gates and transport histories |
| `resolved_calcium_energy_extracellular_barriers@1` | `resolved_calcium_energy_extracellular_barrier_epoch@1` | All 38 finite-fuel arrays, including actual pools, consumption and regeneration histories |
| `resolved_calcium_energy_water_extracellular_barriers@1` | `resolved_calcium_energy_water_extracellular_barrier_epoch@1` | All 43 physical arrays, including actual volumes, finite fuel and extracellular transfer histories |
| `resolved_calcium_energy_water_repair_extracellular_barriers@1` | `resolved_calcium_energy_water_repair_extracellular_barrier_epoch@1` | All 48 physical arrays, including damage, injury transfers and repair heat history |
| `resolved_passive_bath_events@1` | `resolved_passive_bath_epoch@1` | All 13 non-clock arrays, including transport histories and variable reservoir chemical work; a separate initial SIM controller operation |
| `resolved_active_bath_events@1` | `resolved_active_bath_epoch@1` | All 20 non-clock arrays, including the complete 56-law catalog's gates and transport/work histories; a separate initial SIM controller operation |

Each family retains a phase clock. The active and finite-fuel transitions retain
their complete 56-law channel catalog and physical owners. Each transition has
its own typed state and provenance; coupled states cannot fall through to a
parent preparation. Current scientific and execution qualification scopes are
recorded in [Progress](../PROGRESS.md).

SIM starts its own clock at zero. The accepted INIT time and its numerical
phase clock are both archived. Ordinary restart continues the current phase;
it does not perform this transition.

## Prepare a portable example

Both example requests embed a complete evolved INIT checkpoint and an explicit
SIM definition:

| Example | Physical state carried into SIM | INIT / SIM duration |
| --- | --- | --- |
| [Passive](../examples/tissue_phase/README.md) | Twelve passive physical/history arrays | 10 / 10 microseconds |
| [Active](../examples/active_tissue_phase/README.md) | Nineteen arrays, including the 56-law channel catalog, intrinsic gates and pump work | 8 / 8 microseconds |

For the passive example:

```bash
python -m cells tissue-phase prepare examples/tissue_phase/continued.request.json \
  --output /mnt/workspaces/Cells/phase-example
python -m cells tissue-phase validate /mnt/workspaces/Cells/phase-example
python -m cells tissue-phase replay /mnt/workspaces/Cells/phase-example/provenance.json \
  --output /mnt/workspaces/Cells/phase-replayed
```

Use `examples/active_tissue_phase/continued.request.json` with fresh output
directories for the active example. Every output directory must be new.
`definition.json` selects the corresponding passive or active epoch model;
`provenance.json` contains the complete source, both clocks, reset policy,
preserved physical arrays and replay recipe.
Validation checks both files against that recipe, including JSON value types.
Replay does not require the original checkpoint directory or source example.

These examples are manufactured numerical cases, not measured tissues or
demonstrations of biological settling. Their source states retain nonzero
transport and energy histories. The components compare initialization and
subsequent SIM dynamics against independent adaptive solutions at two timesteps.
The active case changes all four control families without resetting intrinsic
gates or prior work. Current qualification scopes are recorded in
[Progress](../PROGRESS.md).

## Start from your own INIT snapshot

Provide an accepted INIT snapshot from one of the scheduled models above and
an ordinary scheduled SIM definition from the same family, with identical
physical owners and static profile preparation:

```bash
python -m cells tissue-phase from-snapshot \
  /mnt/workspaces/Cells/init-run/checkpoint_final \
  /mnt/workspaces/Cells/new-sim.json \
  --output /mnt/workspaces/Cells/new-sim-epoch
```

The source snapshot must satisfy the usual source/runtime compatibility checks.
The command authenticates it and embeds its full typed state in the preparation.
An accepted interior INIT checkpoint can deliberately end initialization;
the complete original definition and selected checkpoint are retained.

For active tissue, use `resolved_active_membrane_profiles@1` for both the source
INIT and target SIM definitions. Preparation returns
`resolved_active_membrane_profile_epoch@1`. Its four membrane, junction, channel
and pump control families may declare new SIM schedules. This does not reset
intrinsic gates, pump cycles, transferred ions or work already performed during
INIT. The scheduled background membrane buffer is separate from channel
conductance and pump kinetics.

For complete calcium or finite-fuel tissue, supply the matching ordinary
scheduled model from the table above for both INIT and SIM. The transition
retains free and bound calcium, ER contents, intrinsic gates and all original
accounting references. Finite-fuel SIM starts with the ATP, ADP and phosphate
actually present at the accepted INIT checkpoint. Its initial turnover check
uses those carried pools. A new phase does not replenish fuel or reset spent
work. Each owner's complete control families may declare explicit SIM schedules.

The water and water/repair transitions carry the actual evolved volumes as well
as calcium and fuel pools. Their timestep admission checks pump turnover using
those carried pools at the current volumes. A new phase does not refill stores,
restore the original volumes, remove damage or erase repair history. Their public
interface and independent component qualifications are tracked separately in
[Progress](../PROGRESS.md); support in the interface is not a long-term recovery
or GPU qualification.

The new SIM definition explicitly declares its controls, prescribed events,
horizon and timestep. Its physical model, static profiles/defaults, owner order
and physical capacities must match INIT. No material or ledger is rebased.
The phase clock is the only state field reset to zero. For membrane profiles,
native membrane defaults
are replayed and the scheduled buffer starts empty before the first pulse
evaluation; smooth pulse tails can already be nonzero at SIM time zero.

This command prepares inputs without advancing SIM. Use ordinary or windowed
execution after checking the selected resource policy:

```bash
python -m cells windowed validate /mnt/workspaces/Cells/new-sim-epoch/definition.json \
  --window-steps 8
```

Independent ensemble admission requires `simulation.execution.jit: true` in
the request or SIM input. Prepare a new artifact after changing execution
settings; editing a generated definition alone breaks its recipe identity.

## Extracellular barrier phases

The complete ionic, calcium, finite-fuel, water and repair barrier models use the same `tissue-phase`
commands. INIT holds the prepared extracellular coefficients fixed. SIM may
declare a new opening pulse and controls, while preserving the identical static
barrier preparation, fixed modulators, physical owners and accounting anchors.
All earlier face transfers, heat and each owner's chemical, fuel, water and
damage histories remain in the state. Standalone barrier transitions require
only their ECM preparation; no membrane-profile artifact is introduced.

These models calculate barrier coefficients directly from the phase clock;
there is no mutable coefficient buffer to clear. At SIM time zero the pulse is
evaluated using the original static coefficients, including its smooth tails.
The preparation records that rule explicitly. Finite-fuel timestep admission
uses gross consumption plus synthesis divided by the actual carried pools at
all control and barrier boundaries. Water models also use current compartment
volumes. Ordinary restart retains
both the current SIM clock and the archived INIT clocks.

The initial checks cover carried states and independent instantaneous physics.
Portable execution, complete trajectories and compiled/GPU qualification retain
their separate evidence in [Progress](../PROGRESS.md).

## Combined membrane and extracellular phases

The complete ionic, calcium, finite-fuel, water and repair combined models also
use `tissue-phase from-snapshot`, with an ordinary SIM definition of the same
model. The corresponding epoch retains the full `resolved_tissue@12`,
`resolved_calcium@11`, `resolved_calcium_energy@5`,
`resolved_calcium_energy_water@2` or `resolved_calcium_energy_water_repair@2`
physical owner. Both static
preparation recipes, all physical owner capacities and the original accounting
references must match INIT. SIM may declare new membrane events, an
extracellular event and control schedules.

Only the shared phase clock resets. All 19, 34, 38, 43 or 48 physical arrays remain
exact, including intrinsic gates, membrane/face/channel transfers, pump cycles
and work. Calcium stores and finite-fuel pools keep their original references;
consumption and regeneration histories remain continuous.
Water and repair epochs also retain the actual cell/extracellular volumes,
water transfers, volume-work accounting, damage and injury/repair histories.
Initial fuel turnover is checked against the carried pools at their current
volumes across both intervention schedules and complete control boundaries.
The record distinguishes two rules: the membrane scheduled buffer starts empty
before evaluation, while extracellular coefficients have no stateful buffer.
Both schedules evaluate their smooth tails at SIM time zero. Neither rule clears
physical transfer history or adds structural repair energy.

Typed snapshots retain the complete source and both preparation records. A
previous SIM epoch cannot be supplied as an ordinary INIT source. Independent
stage, public execution and complete-trajectory evidence remain separate in
[Progress](../PROGRESS.md). Each complete owner requires its own qualification;
ordinary combined-model support does not imply a qualified phase transition.

## Ideal-reservoir bath phases

The passive and complete ionic [bath models](TISSUE_GEOMETRY.md#schedule-ideal-reservoir-bath-composition)
use the same `tissue-phase` preparation, validation, replay and `from-snapshot`
commands. Supply an ordinary bath model in INIT and a SIM definition from the
same family. INIT must be an accepted checkpoint; an ordinary SIM checkpoint
or a previous epoch is refused. Resetting a SIM clock could otherwise erase a
composition change already represented by that clock.

All 13 passive or 20 active non-clock arrays carry exactly, including
`reservoir_chemical_work_pJ`. The original physical owners, inventories, fixed
background charges, boundary voltages, geometry, capacities and accounting
anchors remain identical. The target may declare new held controls, bath
targets and native bath events. The SIM phase clock starts at zero.

A smooth SIM pulse can already have a nonzero dose at time zero. Preparation
therefore records `controller_operation` separately: its supplied material,
charge, compensating electrode charge, and chemical/electrical work are added
to the carried physical history. The saved transport histories are preserved;
physical totals change by exactly this declared operation. The CLI summary
uses `carried_fields` for the full non-clock list and exposes
`controller_operation`. It does not mislabel the extra chemical-work integral
as one of the original passive/ionic parent arrays.

Portable preparation embeds the complete source and both clocks, and replay
authenticates the operation as well as the target definition. Ordinary snapshots
and windowed restarts retain the SIM clock, archived INIT clocks and every
ledger. Changing backend or JIT settings requires a new preparation from the
request: editing a generated definition invalidates its controller-operation
identity. Ensemble admission requires the newly prepared SIM definition to
declare `jit: true`; host admission does not qualify GPU execution.
The embedded source history contributes to the working-storage estimate.
Declare `window_steps` to fit the retained history and the simulation's trace
budget; the public bath-epoch checks use eight-step ensemble windows.
Qualification remains scoped in [Progress](../PROGRESS.md); short
carry, stage and restart checks do not establish complete bath transients or
compiled/GPU execution. Full calcium/fuel bath transitions have the additional
contracts below and their own qualification evidence.

### Calcium and finite-fuel bath phases

`resolved_open_calcium_bath_epoch@1` and
`resolved_open_calcium_energy_bath_epoch@1` extend this workflow to the complete
calcium/ER and finite-fuel bath owners. Their ordinary INIT inputs are
`resolved_open_calcium_bath_events@1` and
`resolved_open_calcium_energy_bath_events@1`, respectively. They use the same
public preparation, snapshot, validation and replay commands.

All **35 / 39 nonclock arrays** carry exactly, including actual chemical-store
increments, pump and channel histories, variable reservoir chemical work and,
for the fuel owner, ATP/ADP/phosphate increments and regeneration histories.
Only the phase clock resets. Original physical inventories, energy references,
fixed charges, reservoir flags and declared storage limits remain unchanged.
The new SIM bath operation is recorded separately and adds its declared dose,
compensating electrode charge and external work to the carried physical state.

Admission uses the actual carried state. Carried ionic totals plus the positive
SIM pulse envelope must fit the declared hard ionic-moiety ceilings. Finite
fuel checks gross hydrolysis plus synthesis against the actual carried pool
amounts for every held SIM control and independent pulse corner, retaining the
**0.05-per-step** limit and all inherited guards. A check using only the original
declared fuel amounts cannot substitute for this carried-pool check. The
prepared handoff records the admitted step, ionic envelope and pool witness;
replay verifies them with the full source state.

For these two owners, every successful `tissue-phase` command also prints that
verified record as `carried_admission` in its JSON output. `step_s` is the checked
SIM step; `ionic_moiety_upper_fmol` is the conservative ionic envelope in the
definition's species order. `pool_turnover` distinguishes finite fuel and, when
present, reports actual and original ATP/ADP/Pi amounts, saved increments, all
held-control/pulse-corner counts and the worst fractional turnover rate. Pool
arrays use ATP, ADP, Pi rows and the definition's active cell order. This exposes
the admission evidence without advancing SIM. The fuel bound is one check;
other gate, chemical, bath-ramp and resource limits still constrain execution.

The full calcium/fuel observers remain available, with archived INIT time and
SIM elapsed time added. Shared public routing and the component's independent
physical comparisons have separate results in [Progress](../PROGRESS.md).
Short carry/replay/restart probes establish interface behavior; full bath
trajectories, native solver-loop comparisons and compiled/GPU runs require
their own evidence.

## Clocks and supported scope

Snapshots preserve the complete SIM state, phase clock and embedded INIT
history. Observations expose `phase_clock_s`, the archived `init_phase_clock_s`
and `elapsed_time_s`:

```text
elapsed_time_s = accepted INIT checkpoint time + current SIM phase_clock_s
```

The accepted INIT time and numerical INIT phase clock can differ by floating
point roundoff, so both are retained. An ordinary resume or branch cannot turn
an INIT state into this epoch or silently restart a SIM clock.

The active membrane and combined membrane/barrier transitions support the
`resolved_tissue@12` parent with maintained fuel. The calcium membrane transition
supports `resolved_calcium@6`; its standalone ECM and combined membrane/barrier counterparts use
the complete `resolved_calcium@11` catalog. Finite-fuel transitions use
`resolved_calcium_energy@5`.
Water and water/repair transitions retain the complete version-two parents and
their 56-law catalog. Changing static geometry/defaults, owner remaps, cuts,
pressure events, other barrier-owner families, configured-transport,
mitochondrial or live-regulation transitions require
separate contracts. The native
phase lifecycle motivates the reset policy, while Cells evaluates membrane
pulses at RK stages; full native solver-loop equivalence remains separate.
The [passive component contract](../agent-work/cells-worker-01/workfiles/MEMBRANE_PROFILE_PHASE_HANDOFF.md)
describes the original transition rules. The
[active adapter](../src/cells/core/active_membrane_profile_phase_handoff.py)
applies these rules to the complete active state and its four control families.
