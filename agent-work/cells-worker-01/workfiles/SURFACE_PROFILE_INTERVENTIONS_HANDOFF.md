# Scheduled passive membrane profiles

Owner: Cells Key Developer (`cells-worker-01`). The Chief owns shared dispatch,
ensemble integration, public tests and shared status. This component changes no
parent field equations, numerical integrator, qualified preparation or shared
dispatch file.

## Stable interface

- Model ID: `resolved_membrane_profiles@1`.
- Spec: `cells.core.surface_profile_interventions_spec`, with
  `SurfaceProfileInterventionModel`, `Execution`, `parse`, `to_dict`, `base_spec`,
  `bindings`, `artifact` and `replay`.
- Runtime: `cells.models.surface_profile_interventions`, with the usual model
  hooks, plus `check_checkpoint` and `ensemble_voltage`.
- Timing policy: `phase_clock_rk_stage_native_logistic@1`.
- Reset policy: `fresh_phase_zero_scheduled_sim_only@1`.

The physical fields of the model exactly match its prepared ordinary
`resolved_tissue@1` source. `profile_preparation` retains the complete
`{definition, provenance}` pair from either the direct static profile bridge or
the joined initial geometry/profile bridge. Experiment and execution settings
are declared separately. Full source replay and typed JSON identity checks are
required; neither a coefficient-only record nor a changed physical parent is
accepted.

Each intervention declares exactly `name`, `kind`, `profiles`, `on_s`, `off_s`,
`change_s`, `amplitude`, `spatial`, `source_function` and `dynamic_factor`.
Supported kinds are `Na_mem`, `K_mem`, `Cl_mem` and `Ca_mem`, at most one of each.
Targets retain profile occurrence order and duplicates. `spatial` is null or
`{values, axis}`, with `axis` equal to `occurrence` or `membrane`. Named source
functions require explicit sampled values; they are never evaluated here.
Constant dynamic factors and explicit spatial/amplitude factors can be signed
only when the conservative all-time diffusion bound remains nonnegative.

Execution adds `intervention_capacity` (0 through 4) and
`intervention_target_capacity` (0 through 65536). Padding is neutral. The
unapplied `surface_profile_interventions_dispatch.patch` demonstrates only the
parse, serialization and registry routes in an isolated source copy; it is not
the Chief's final integration patch.

## Physical and timing contract

The frozen native compiler and intervention kernel determine family order,
default-Dm multipliers, ordered assignment and last duplicate occurrence. Na/K
events ignore their ion-enabled flags, while Cl/Ca retain the native guards.
Native layout order can differ from model order; stable membrane IDs bind them.
Explicit physical thickness converts total native diffusion to permeability.

The one-entry `phase_clock_s` state has derivative one and starts at zero only
for a fresh phase. Existing RK4 stages advance that clock and evaluate the
unchanged native logistic pulse, including its smooth tails. INIT suppresses
all scheduled membrane effects. SIM applies the events. Checkpoints preserve
the clock and validate it against accepted time metadata; changing phase on a
checkpoint branch is refused. No automatic biological INIT-to-SIM handoff is
defined.

Pinned native `sim.py` establishes that phase initialization copies `Dm_base`
and zeros `Dm_scheduled`, and both native solver loops fire events only in SIM.
For this membrane-only subset, each event overwrites every selected entry each
time. Fresh zero scheduled buffers at each stage therefore match the supported
native carry-buffer arithmetic. This defines RK-stage pulse sampling; it does
not claim native solver-loop trajectory parity.

SIM steps are limited to the shortest transition time divided by eight.
The nominal `execution.dt` receives a separate scalar relative-roundoff check.
Actual differences of absolute clock labels receive a bounded endpoint-scale
allowance of two horizon ULPs, or sixteen epsilons of the step ceiling when
larger. These checks preserve the declared timestep and physical event times;
large horizons cannot relax the nominal bound.

Actual finite, nonnegative permeability drives the unchanged parent field and
full state derivative. A separate union of possible membrane routes is used
only for historical ledger support, so a route that closes later can retain
its earlier transfer. This support union never supplies physical fluxes or
potentials. The varying kinetic prefactor adds no storage term; the existing
material, charge, capacitor, chemical-energy and passive-dissipation ledgers
remain intact. Invalid actual permeability or clocks are refused without
clipping or accepting a corrupted step.

Pressure/ECM events, cuts, remaps, moving geometry, unknown callbacks and
automatic native phase transfer are outside this model.

## Evidence and integration

The protocol is `validation/topology/surface_profile_interventions_protocol.json`.
The independent reference uses Decimal pulse arithmetic, explicit ordered owner
assignments and the frozen complete passive field/derivative reference. It does
not import production model or JAX equations. Cases include INIT, SIM, disabled
ion flags, safe negative events, temporarily closed routes and empty schedules;
a joined geometry/profile case retains both complete preparation chains.

Qualification compares complete fields, derivatives, potentials, material and
energy balances across pulse phases. A short NumPy RK4 refinement is compared
with an independent adaptive solution with exactly segmented held controls.
Separate bounded CPU processes exercise a compiled complete JAX RHS, vmap
invalid-world isolation, time gradients, and eager public snapshot/resume.
Public replay is not a compiled-trajectory qualification. Guards require CPU7,
one numerical thread, at most 1 GiB process-tree RSS and at least 8 GiB host
reserve. Failed evidence remains in its original development directory.

The handoff receipt records exact component receipts, source/artifact hashes,
resource metrics, examples and limitations. The Chief should integrate the
stable model/spec interfaces, add the ensemble route and run the already
prepared public contract tests. No previous qualified component suite or
unrelated active job is part of this component's verification.

The exported `examples/direct-four-ion` and `examples/geometry-profiles`
directories each contain a complete `definition.json` and sealed `artifact.json`.
The latter retains the full preparation chain and compiled binding identity:

```python
import json
from pathlib import Path
from cells.core import surface_profile_interventions_spec as scheduled

record = json.loads(Path("examples/direct-four-ion/artifact.json").read_text())
spec = scheduled.replay(record)
assert scheduled.parse(scheduled.to_dict(spec)) == spec
```

After the Chief's dispatch integration, ordinary public definition and snapshot
loaders use the same model/spec hooks. Qualification freezes the old numerical
engine source in its isolated workspace; later Chief-owned window/runner changes
do not alter the meaning or provenance of these captured component checks.
