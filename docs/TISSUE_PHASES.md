# Carrying INIT state into SIM

`cells tissue-phase` prepares an explicit new SIM experiment from an accepted
INIT checkpoint. Material, charge, geometry, intrinsic gates and accounting
history carry forward exactly. The original accounting references remain in
place, so transfer and energy balances cover INIT and SIM together.

| INIT model | Prepared SIM model | Carried parent state |
| --- | --- | --- |
| `resolved_membrane_profiles@1` | `resolved_membrane_profile_epoch@1` | All 12 passive physical/history arrays |
| `resolved_active_membrane_profiles@1` | `resolved_active_membrane_profile_epoch@1` | All 19 active arrays, including channel/junction gates, channel transfers, pump cycles, heat and maintained-fuel work |
| `resolved_calcium_membrane_profiles@1` | `resolved_calcium_membrane_profile_epoch@1` | All 34 calcium/ER arrays, including free/bound inventories, gates, reactions and pump/transport history |
| `resolved_calcium_energy_membrane_profiles@1` | `resolved_calcium_energy_membrane_profile_epoch@1` | All 38 finite-fuel arrays, including the actual ATP/ADP/phosphate pools and regeneration/work history |
| `resolved_calcium_energy_water_membrane_profiles@1` | `resolved_calcium_energy_water_membrane_profile_epoch@1` | All 43 physical arrays, including current water volumes, finite fuel and original water/work accounting |
| `resolved_calcium_energy_water_repair_membrane_profiles@1` | `resolved_calcium_energy_water_repair_membrane_profile_epoch@1` | All 48 physical arrays, including damage, injury transfers and repair heat history |

Each family adds a phase clock. The active and finite-fuel transitions retain
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

The new SIM definition explicitly declares its controls, membrane events,
horizon and timestep. Its physical model, static profiles/defaults, owner order
and physical capacities must match INIT. No material or ledger is rebased.
The phase clock is the only state field reset to zero. Native membrane defaults
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

The active transition supports the directly prepared `resolved_tissue@12`
parent with maintained fuel. The calcium and finite-fuel transitions support
exactly the complete `resolved_calcium@6` and `resolved_calcium_energy@5` owners.
Water and water/repair transitions retain the complete version-two parents and
their 56-law catalog. Changing static geometry/defaults, owner remaps, cuts,
pressure/ECM events, configured-transport, mitochondrial or live-regulation transitions require
separate contracts. The native
phase lifecycle motivates the reset policy, while Cells evaluates membrane
pulses at RK stages; full native solver-loop equivalence remains separate.
The [passive component contract](../agent-work/cells-worker-01/workfiles/MEMBRANE_PROFILE_PHASE_HANDOFF.md)
describes the original transition rules. The
[active adapter](../src/cells/core/active_membrane_profile_phase_handoff.py)
applies these rules to the complete active state and its four control families.
