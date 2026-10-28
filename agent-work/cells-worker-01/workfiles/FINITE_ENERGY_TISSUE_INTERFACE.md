# Resolved finite-energy tissue interface

Proposed `resolved_energy@1` interface for the Chief's shared-hook work.
The baseline is `resolved_tissue@7`, fixed geometry/volume and finite closed
outside owners. Every cell has exactly one finite ATP/ADP/Pi owner.

## Raw additions

`model.energy_pools`, normalized to cell order:

```json
{
  "id": "energy_0",
  "cell_id": "cell_0",
  "law": "finite_atp_adp_pi_transformed@1",
  "initial_amount_fmol": {"ATP": 0.003, "ADP": 0.0002, "Pi": 0.0002},
  "delta_g0_J_per_mol": -37000.0
}
```

Volume and temperature are owned by the named cell and ionic model. There are
no duplicate volume/temperature fields. Each present Na/K pump replaces its
maintained metabolism object with:

```json
{"kind": "finite_energy_pool@1", "pool_id": "energy_0"}
```

The referenced pool must belong to that membrane's inside cell. Existing pump
law, roles, stoichiometry, capacity and Km are retained; unused maintained ATP,
ADP, Pi or standard-energy fields are rejected.

`model.regeneration_ports` is an explicit ordered list, including empty:

```json
{
  "id": "regeneration_0",
  "pool_id": "energy_0",
  "law": "driven_atp_regeneration_tanh@1",
  "capacity_fmol_per_s": 0.1,
  "supplied_energy_J_per_mol": 80000.0
}
```

`experiment.regeneration_controls` has exactly one identified schedule per port:
`{"regeneration_id": "regeneration_0", "schedule": [{"time": 0.0,
"availability": 1.0}]}`. Execution adds `regeneration_capacity`; the existing
kinetic/channel capacities retain their meaning. All owner/route/control IDs
are strict, unique and explicit; schedules use the existing right-continuous
availability convention.

## Python names and shared hooks

- `MODEL_ID = "resolved_energy@1"`, `METABOLISM_ID = "finite_energy_pool@1"`.
- Frozen dataclasses `EnergyPool`, `RegenerationPort`, `PoolMetabolism`,
  `FinitePump`, `Membrane`, `SurfaceEnergyModel`, `Execution`, `Experiment`,
  `Change` in `cells.core.surface_energy_spec`.
- `SurfaceEnergyModel` extends `surface_kinetic_spec.SurfaceCavModel`.
- `Execution` extends kinetic `Execution` with `regeneration_capacity`.
- `Experiment.regenerations` holds ordered per-port schedules.
- `Change.regeneration` holds the corresponding availability tuple.
- `Control` fields in order: `membrane`, `junction`, `channel`, `pump`,
  `regeneration`. Union all five control clocks.
- `initial_ionic_spec(spec)` returns the initial maintained-pool
  `resolved_tissue@7` projection. It reconstructs initial pump concentrations
  from each pool's initial amounts/current fixed cell volume. This is an
  initialization/parser/layout helper, not the evolving model.
- `parse`, `to_dict` preserve the finite declarations and call the deferred
  `cells.models.surface_energy.check_definition` after full construction.

## Complete model state

Retain all 19 active ionic state fields and add:

| Field | Axes |
| --- | --- |
| `energy_amount_increment_fmol` | energy_species, cell_slot |
| `regeneration_cycles_fmol` | regeneration_slot |
| `regeneration_dissipated_energy_pJ` | regeneration_slot |
| `regeneration_supplied_work_pJ` | regeneration_slot |

Total: 23 fields. `BATCH_CAPACITIES` extends the kinetic capacities with
`regeneration_capacity`. Existing `metabolic_work_pJ` is an internal pump/pool
transfer diagnostic integrated using the current drive. Its old
initial-drive-times-cycles identity does not apply. The complete balance uses
finite-pool free energy, pump/transport heat, regeneration heat and signed
regeneration supply; metabolic work is not an external source.

The worker owns spec/model/fixtures/reference/stage tests/example; the Chief
owns shared dispatch/controls/ensemble hooks and execution/qualification.
