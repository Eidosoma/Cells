# The format sample (TABLE §7)

Tables of invented worlds (`../sample.py`), made by the run driver and written by the exporter that will write the registered tables. Then every number was
replaced: an integer by 7, a double by 0.5, a run's times by 0, 0.75, 1.5 and on (a restart's begin at 0.75). Every registered string is a placeholder, every
fingerprint a run of zeros, every time of day "a time", and the source's strings name their keys. **Nothing may be taken from it but keys and types:** no number,
length, order or equality.

- `table/`: the four consumers' tables. `table-retry/`: a retry's. Each with its `SHA256SUMS`, which is of these files.
- **What is in them:** a completed run of each kind of world (`inv_sample_cluster`, `inv_sample_lone`, `inv_sample_pair`, `inv_sample_sheet`) and one on the second-order integrator; a
  pool run of one pool and of two; a restart of an ionic run and of each pool run; a refused run of each kind (`definition` and `domain` at parse, `check` as a stop that keeps the rows
  before it, `harness` as a run that its driver ended and that has nothing but its record); two engine plants (a declared value, and two pools' channels exchanged); a run off its grid with
  the extra key `off_grid`; the retry folder.
- **Not in them:** a run that is `missing` (the key is an empty list here).

## Keys and types, to the leaf

`<...>` stands for a map's keys. `[]` is a list's items. A key with several types holds one of them by the kind of run. What stands under `definition` and `checks` is the engine's own (recorded, never
judged), and comes last. The lists are `python -m validation.ensemble_reexpression.sample keys FOLDER`'s.

### An ionic run's entry

```text
entry.declared_strings: list
entry.declared_strings[]: str
entry.host_patch: NoneType
entry.inputs: dict
entry.inputs.assembly: dict
entry.inputs.assembly.assembly_observable: str
entry.inputs.assembly.composed_file_fingerprint: str
entry.inputs.assembly.pool_seeds: dict
entry.inputs.assembly.pool_seeds.<cell ID>: int
entry.inputs.assembly.switch_list: dict
entry.inputs.assembly.switch_list.<channel ID>: list
entry.inputs.assembly.switch_list.<channel ID>[]: list
entry.inputs.assembly.switch_list.<channel ID>[][]: float
entry.inputs.cells: dict
entry.inputs.cells.<cell ID>: dict
entry.inputs.cells.<cell ID>.fixed_charge_equivalent_fmol: float
entry.inputs.cells.<cell ID>.initial_amount_fmol: dict
entry.inputs.cells.<cell ID>.initial_amount_fmol.<species>: float
entry.inputs.cells.<cell ID>.initial_charge_C: float
entry.inputs.cells.<cell ID>.initial_voltage_V: float
entry.inputs.cells.<cell ID>.volume_pL: float
entry.inputs.channels: dict, list
entry.inputs.channels.<channel ID>: dict
entry.inputs.channels.<channel ID>.abundance: float
entry.inputs.channels.<channel ID>.initial_gate: dict
entry.inputs.channels.<channel ID>.initial_gate.h: float
entry.inputs.channels.<channel ID>.initial_gate.m: float
entry.inputs.channels.<channel ID>.kinetic_law: str
entry.inputs.channels.<channel ID>.max_permeability_m_per_s: float
entry.inputs.channels.<channel ID>.membrane_id: str
entry.inputs.channels.<channel ID>.species_id: str
entry.inputs.closure: dict
entry.inputs.closure.gauge_reference: str
entry.inputs.controls: dict
entry.inputs.controls.channel: dict, list
entry.inputs.controls.channel.<channel ID>: list
entry.inputs.controls.channel.<channel ID>[]: list
entry.inputs.controls.channel.<channel ID>[][]: float
entry.inputs.controls.junction: dict, list
entry.inputs.controls.junction.<junction ID>: list
entry.inputs.controls.junction.<junction ID>[]: list
entry.inputs.controls.junction.<junction ID>[][]: float
entry.inputs.controls.leak: dict
entry.inputs.controls.leak.<membrane ID>: list
entry.inputs.controls.leak.<membrane ID>[]: list
entry.inputs.controls.leak.<membrane ID>[][]: float
entry.inputs.controls.pump: dict, list
entry.inputs.controls.pump.<membrane ID>: list
entry.inputs.controls.pump.<membrane ID>[]: list
entry.inputs.controls.pump.<membrane ID>[][]: float
entry.inputs.end_s: float
entry.inputs.faces: dict, list
entry.inputs.faces.<face ID>: dict
entry.inputs.faces.<face ID>.area_m2: float
entry.inputs.faces.<face ID>.diffusivity_m2_per_s: dict
entry.inputs.faces.<face ID>.diffusivity_m2_per_s.<species>: float
entry.inputs.faces.<face ID>.law: str
entry.inputs.faces.<face ID>.length_m: float
entry.inputs.faces.<face ID>.receiver: str
entry.inputs.faces.<face ID>.sender: str
entry.inputs.junctions: dict, list
entry.inputs.junctions.<junction ID>: dict
entry.inputs.junctions.<junction ID>.area_m2: float
entry.inputs.junctions.<junction ID>.from_cell: str
entry.inputs.junctions.<junction ID>.gate: dict
entry.inputs.junctions.<junction ID>.gate.initial_gate: float
entry.inputs.junctions.<junction ID>.gate.law: str
entry.inputs.junctions.<junction ID>.gate.minimum_open_fraction: float
entry.inputs.junctions.<junction ID>.gate.threshold_voltage_V: float
entry.inputs.junctions.<junction ID>.permeability_m_per_s: dict
entry.inputs.junctions.<junction ID>.permeability_m_per_s.<species>: float
entry.inputs.junctions.<junction ID>.to_cell: str
entry.inputs.material_tolerance_fmol: dict
entry.inputs.material_tolerance_fmol.<species>: float
entry.inputs.membranes: dict
entry.inputs.membranes.<membrane ID>: dict
entry.inputs.membranes.<membrane ID>.area_m2: float
entry.inputs.membranes.<membrane ID>.capacitance_F: float
entry.inputs.membranes.<membrane ID>.inside: str
entry.inputs.membranes.<membrane ID>.outside: str
entry.inputs.membranes.<membrane ID>.passive: dict
entry.inputs.membranes.<membrane ID>.passive.law: str
entry.inputs.membranes.<membrane ID>.passive.permeability_m_per_s: dict
entry.inputs.membranes.<membrane ID>.passive.permeability_m_per_s.<species>: float
entry.inputs.membranes.<membrane ID>.pump: NoneType, dict
entry.inputs.membranes.<membrane ID>.pump.capacity_fmol_per_s: float
entry.inputs.membranes.<membrane ID>.pump.km_atp_mM: float
entry.inputs.membranes.<membrane ID>.pump.km_k_mM: float
entry.inputs.membranes.<membrane ID>.pump.km_na_mM: float
entry.inputs.membranes.<membrane ID>.pump.law: str
entry.inputs.membranes.<membrane ID>.pump.metabolism: dict
entry.inputs.membranes.<membrane ID>.pump.metabolism.adp_mM: float
entry.inputs.membranes.<membrane ID>.pump.metabolism.atp_mM: float
entry.inputs.membranes.<membrane ID>.pump.metabolism.delta_g0_J_per_mol: float
entry.inputs.membranes.<membrane ID>.pump.metabolism.kind: str
entry.inputs.membranes.<membrane ID>.pump.metabolism.pi_mM: float
entry.inputs.membranes.<membrane ID>.pump.roles: dict
entry.inputs.membranes.<membrane ID>.pump.roles.potassium: str
entry.inputs.membranes.<membrane ID>.pump.roles.sodium: str
entry.inputs.membranes.<membrane ID>.pump.stoichiometry: dict
entry.inputs.membranes.<membrane ID>.pump.stoichiometry.<species>: int
entry.inputs.outside: dict
entry.inputs.outside.<region ID>: dict
entry.inputs.outside.<region ID>.fixed_charge_equivalent_fmol: float
entry.inputs.outside.<region ID>.initial_amount_fmol: dict
entry.inputs.outside.<region ID>.initial_amount_fmol.<species>: float
entry.inputs.outside.<region ID>.initial_charge_C: float
entry.inputs.outside.<region ID>.volume_pL: float
entry.inputs.species: dict
entry.inputs.species.<species>: int
entry.inputs.temperature_K: float
entry.off_grid: bool
entry.path: NoneType
entry.pool: NoneType
entry.potential_t: list
entry.potential_t[]: float
entry.potentials: dict
entry.potentials.<readout>: dict
entry.potentials.<readout>.<entity ID>: list
entry.potentials.<readout>.<entity ID>[]: float
entry.record: str
entry.record_sha256: str
entry.refusal: NoneType, dict
entry.refusal.kind: str
entry.refusal.message: str
entry.refusal.time_s: NoneType, float
entry.restart: NoneType, dict
entry.restart.step_index: int
entry.restart.through: str
entry.restart.time_s: float
entry.rows: dict
entry.rows.<readout>: dict
entry.rows.<readout>.<entity ID>: list
entry.rows.<readout>.<entity ID>[]: float
entry.seed_index: NoneType, int
entry.source: dict
entry.source.blas_threads: int
entry.source.checkout_dirty: bool
entry.source.cpu_model: str
entry.source.engine_revision: str
entry.source.jax: str
entry.source.jaxlib: str
entry.source.numpy: str
entry.source.python: str
entry.source.snapshot: str
entry.source.snapshot_patch_sha256: str
entry.status: str
entry.step_s: float
entry.steps: int
entry.strings: dict
entry.strings.<label>: str
entry.t: list
entry.t[]: float
entry.variant: NoneType, str
entry.world: str
entry.world_id: NoneType, int
entry.checks: dict
entry.checks.active_cells: int
entry.checks.boundary: str
entry.checks.calcium_pump_law: str
entry.checks.capacity: int
entry.checks.cell_id: int
entry.checks.cell_ids: list
entry.checks.cell_ids[]: int
entry.checks.channel_laws: dict
entry.checks.channel_laws.<channel ID>: str
entry.checks.closure_law: str
entry.checks.end_time: float
entry.checks.executed_steps: int
entry.checks.field_solver: str
entry.checks.gate_integrator: str
entry.checks.global_step_index: int
entry.checks.junction_heat_booking: str
entry.checks.junction_law: str
entry.checks.max_balance_error_fmol: float
entry.checks.max_capacitor_charge_error_C: float
entry.checks.max_electrode_charge_error_C: float
entry.checks.max_electrode_work_error_pJ: float
entry.checks.max_energy_balance_error_pJ: float
entry.checks.max_energy_balance_relative: float
entry.checks.max_extracellular_balance_error_fmol: float
entry.checks.max_global_balance_error_fmol: float
entry.checks.max_global_charge_bound_ratio: float
entry.checks.max_global_charge_error_C: float
entry.checks.max_metabolic_work_error_pJ: float
entry.checks.max_reservoir_work_error_pJ: float
entry.checks.membrane_transfer_ledger: str
entry.checks.model: str
entry.checks.observation_scope: str
entry.checks.pump_law: str
entry.checks.species_ids: list
entry.checks.species_ids[]: str
entry.checks.start_time: float
entry.checks.state_fields: list
entry.checks.state_fields[]: str
entry.checks.status: str
entry.checks.time_integrator: str
entry.definition: dict
entry.definition.ionic: dict
entry.definition.ionic.execution: dict
entry.definition.ionic.execution.backend: str
entry.definition.ionic.execution.capacity: int
entry.definition.ionic.execution.channel_capacity: int
entry.definition.ionic.execution.dt: float
entry.definition.ionic.execution.edge_capacity: int
entry.definition.ionic.execution.extracellular_capacity: int
entry.definition.ionic.execution.face_capacity: int
entry.definition.ionic.execution.field_solver: str
entry.definition.ionic.execution.jit: bool
entry.definition.ionic.execution.material_balance_atol_fmol: dict
entry.definition.ionic.execution.material_balance_atol_fmol.<species>: float
entry.definition.ionic.execution.max_steps: int
entry.definition.ionic.execution.max_trace_bytes: int
entry.definition.ionic.execution.membrane_capacity: int
entry.definition.ionic.execution.precision: str
entry.definition.ionic.execution.solver: str
entry.definition.ionic.experiment: dict
entry.definition.ionic.experiment.calcium_pump_controls: list
entry.definition.ionic.experiment.channel_controls: list
entry.definition.ionic.experiment.channel_controls[]: dict
entry.definition.ionic.experiment.channel_controls[].channel_id: str
entry.definition.ionic.experiment.channel_controls[].schedule: list
entry.definition.ionic.experiment.channel_controls[].schedule[]: dict
entry.definition.ionic.experiment.channel_controls[].schedule[].availability: float
entry.definition.ionic.experiment.channel_controls[].schedule[].time: float
entry.definition.ionic.experiment.end_time: float
entry.definition.ionic.experiment.junction_controls: list
entry.definition.ionic.experiment.junction_controls[]: dict
entry.definition.ionic.experiment.junction_controls[].junction_id: str
entry.definition.ionic.experiment.junction_controls[].schedule: list
entry.definition.ionic.experiment.junction_controls[].schedule[]: dict
entry.definition.ionic.experiment.junction_controls[].schedule[].availability: float
entry.definition.ionic.experiment.junction_controls[].schedule[].time: float
entry.definition.ionic.experiment.membrane_controls: list
entry.definition.ionic.experiment.membrane_controls[]: dict
entry.definition.ionic.experiment.membrane_controls[].membrane_id: str
entry.definition.ionic.experiment.membrane_controls[].schedule: list
entry.definition.ionic.experiment.membrane_controls[].schedule[]: dict
entry.definition.ionic.experiment.membrane_controls[].schedule[].availability: float
entry.definition.ionic.experiment.membrane_controls[].schedule[].time: float
entry.definition.ionic.experiment.observation_times: list
entry.definition.ionic.experiment.observation_times[]: float
entry.definition.ionic.experiment.pump_controls: list
entry.definition.ionic.experiment.pump_controls[]: dict
entry.definition.ionic.experiment.pump_controls[].pump_id: str
entry.definition.ionic.experiment.pump_controls[].schedule: list
entry.definition.ionic.experiment.pump_controls[].schedule[]: dict
entry.definition.ionic.experiment.pump_controls[].schedule[].availability: float
entry.definition.ionic.experiment.pump_controls[].schedule[].time: float
entry.definition.ionic.model: dict
entry.definition.ionic.model.cells: list
entry.definition.ionic.model.cells[]: dict
entry.definition.ionic.model.cells[].fixed_charge_equivalent_fmol: float
entry.definition.ionic.model.cells[].id: str
entry.definition.ionic.model.cells[].initial_amount_fmol: dict
entry.definition.ionic.model.cells[].initial_amount_fmol.<species>: float
entry.definition.ionic.model.cells[].initial_charge_C: float
entry.definition.ionic.model.cells[].volume_pL: float
entry.definition.ionic.model.channels: list
entry.definition.ionic.model.channels[]: dict
entry.definition.ionic.model.channels[].abundance: float
entry.definition.ionic.model.channels[].id: str
entry.definition.ionic.model.channels[].initial_gate: list
entry.definition.ionic.model.channels[].initial_gate[]: float
entry.definition.ionic.model.channels[].kinetic_law: str
entry.definition.ionic.model.channels[].max_permeability_m_per_s: float
entry.definition.ionic.model.channels[].membrane_id: str
entry.definition.ionic.model.channels[].permeant_ions: list
entry.definition.ionic.model.channels[].permeant_ions[]: dict
entry.definition.ionic.model.channels[].permeant_ions[].relative_permeability: float
entry.definition.ionic.model.channels[].permeant_ions[].species_id: str
entry.definition.ionic.model.closure: dict
entry.definition.ionic.model.closure.gauge_reference: str
entry.definition.ionic.model.closure.law: str
entry.definition.ionic.model.extracellular: list
entry.definition.ionic.model.extracellular[]: dict
entry.definition.ionic.model.extracellular[].boundary_potential_V: float
entry.definition.ionic.model.extracellular[].fixed_charge_equivalent_fmol: float
entry.definition.ionic.model.extracellular[].id: str
entry.definition.ionic.model.extracellular[].initial_amount_fmol: dict
entry.definition.ionic.model.extracellular[].initial_amount_fmol.<species>: float
entry.definition.ionic.model.extracellular[].initial_charge_C: float
entry.definition.ionic.model.extracellular[].reservoir: bool
entry.definition.ionic.model.extracellular[].volume_pL: float
entry.definition.ionic.model.faces: list
entry.definition.ionic.model.faces[]: dict
entry.definition.ionic.model.faces[].area_m2: float
entry.definition.ionic.model.faces[].diffusivity_m2_per_s: dict
entry.definition.ionic.model.faces[].diffusivity_m2_per_s.<species>: float
entry.definition.ionic.model.faces[].id: str
entry.definition.ionic.model.faces[].law: str
entry.definition.ionic.model.faces[].length_m: float
entry.definition.ionic.model.faces[].receiver: str
entry.definition.ionic.model.faces[].sender: str
entry.definition.ionic.model.id: str
entry.definition.ionic.model.junctions: list
entry.definition.ionic.model.junctions[]: dict
entry.definition.ionic.model.junctions[].area_m2: float
entry.definition.ionic.model.junctions[].gate: dict
entry.definition.ionic.model.junctions[].gate.initial_gate: float
entry.definition.ionic.model.junctions[].gate.law: str
entry.definition.ionic.model.junctions[].gate.minimum_open_fraction: float
entry.definition.ionic.model.junctions[].gate.threshold_voltage_V: float
entry.definition.ionic.model.junctions[].id: str
entry.definition.ionic.model.junctions[].law: str
entry.definition.ionic.model.junctions[].permeability_m_per_s: dict
entry.definition.ionic.model.junctions[].permeability_m_per_s.<species>: float
entry.definition.ionic.model.junctions[].receiver: str
entry.definition.ionic.model.junctions[].sender: str
entry.definition.ionic.model.membranes: list
entry.definition.ionic.model.membranes[]: dict
entry.definition.ionic.model.membranes[].area_m2: float
entry.definition.ionic.model.membranes[].calcium_pump: NoneType
entry.definition.ionic.model.membranes[].capacitance_F: float
entry.definition.ionic.model.membranes[].id: str
entry.definition.ionic.model.membranes[].inside: str
entry.definition.ionic.model.membranes[].law: str
entry.definition.ionic.model.membranes[].outside: str
entry.definition.ionic.model.membranes[].permeability_m_per_s: dict
entry.definition.ionic.model.membranes[].permeability_m_per_s.<species>: float
entry.definition.ionic.model.membranes[].pump: NoneType, dict
entry.definition.ionic.model.membranes[].pump.capacity_fmol_per_s: float
entry.definition.ionic.model.membranes[].pump.id: str
entry.definition.ionic.model.membranes[].pump.km_atp_mM: float
entry.definition.ionic.model.membranes[].pump.km_k_mM: float
entry.definition.ionic.model.membranes[].pump.km_na_mM: float
entry.definition.ionic.model.membranes[].pump.law: str
entry.definition.ionic.model.membranes[].pump.metabolism: dict
entry.definition.ionic.model.membranes[].pump.metabolism.adp_mM: float
entry.definition.ionic.model.membranes[].pump.metabolism.atp_mM: float
entry.definition.ionic.model.membranes[].pump.metabolism.delta_g0_J_per_mol: float
entry.definition.ionic.model.membranes[].pump.metabolism.kind: str
entry.definition.ionic.model.membranes[].pump.metabolism.pi_mM: float
entry.definition.ionic.model.membranes[].pump.roles: dict
entry.definition.ionic.model.membranes[].pump.roles.potassium: str
entry.definition.ionic.model.membranes[].pump.roles.sodium: str
entry.definition.ionic.model.membranes[].pump.stoichiometry: dict
entry.definition.ionic.model.membranes[].pump.stoichiometry.<species>: int
entry.definition.ionic.model.species: list
entry.definition.ionic.model.species[]: dict
entry.definition.ionic.model.species[].id: str
entry.definition.ionic.model.species[].valence: int
entry.definition.ionic.model.temperature_K: float
entry.definition.ionic.schema_version: int
entry.definition.made_from: dict
entry.definition.made_from.composed_file_sha256: str
entry.definition.made_from.composed_sha256: str
entry.definition.made_from.ionic_sha256: str
entry.definition.made_from.kind: str
entry.definition.made_from.near_misses: str
entry.definition.made_from.pools: list
entry.definition.made_from.pools[]: dict
entry.definition.made_from.pools[].channels: list
entry.definition.made_from.pools[].channels[]: str
entry.definition.made_from.pools[].levels: dict
entry.definition.made_from.pools[].levels.false: float
entry.definition.made_from.pools[].levels.true: float
entry.definition.made_from.pools[].observable: str
entry.definition.made_from.pools[].pool_sha256: str
entry.definition.made_from.pools[].seed: int
entry.definition.made_from.schema_version: int
entry.definition.made_from.worlds: list
entry.definition.made_from.worlds[]: dict
entry.definition.made_from.worlds[].definition_sha256: str
entry.definition.made_from.worlds[].switches: list
entry.definition.made_from.worlds[].switches[]: dict
entry.definition.made_from.worlds[].switches[].event: int
entry.definition.made_from.worlds[].switches[].level: float
entry.definition.made_from.worlds[].switches[].pool: int
entry.definition.made_from.worlds[].switches[].time: float
entry.definition.made_from.worlds[].world: int
```

### A pool run's entry

```text
pool run.declared_strings: list
pool run.declared_strings[]: str
pool run.host_patch: NoneType
pool run.inputs: dict
pool run.inputs.<cell ID>: dict
pool run.inputs.<cell ID>.channel: str
pool run.inputs.<cell ID>.pool: dict
pool run.inputs.<cell ID>.pool.end_time_s: float
pool run.inputs.<cell ID>.pool.initial_bond_indices: list
pool run.inputs.<cell ID>.pool.initial_bond_indices[]: int
pool run.inputs.<cell ID>.pool.initial_free_trimers: int
pool run.inputs.<cell ID>.pool.initial_nodes: list
pool run.inputs.<cell ID>.pool.initial_nodes[]: int
pool run.inputs.<cell ID>.pool.k_close_s_inv: float
pool run.inputs.<cell ID>.pool.k_fragment_dissolve_s_inv: float
pool run.inputs.<cell ID>.pool.k_off_s_inv: float
pool run.inputs.<cell ID>.pool.k_on_M_inv_s: float
pool run.inputs.<cell ID>.pool.max_events_per_world: int
pool run.inputs.<cell ID>.pool.model: str
pool run.inputs.<cell ID>.pool.pool_volume_L: float
pool run.inputs.<cell ID>.pool.root_node: int
pool run.inputs.<cell ID>.pool.topology: str
pool run.inputs.<cell ID>.pool.world_id_start: int
pool run.inputs.<cell ID>.pool.worlds: int
pool run.inputs.<cell ID>.seed: int
pool run.inputs.<cell ID>.stream_id: int
pool run.path: dict
pool run.path.<cell ID>: dict
pool run.path.<cell ID>.<world ID>: list
pool run.path.<cell ID>.<world ID>[]: list
pool run.path.<cell ID>.<world ID>[][]: float, int
pool run.pool: dict
pool run.pool.<cell ID>: dict
pool run.pool.<cell ID>.arrays: dict
pool run.pool.<cell ID>.arrays.bonds: list
pool run.pool.<cell ID>.arrays.bonds[]: int
pool run.pool.<cell ID>.arrays.dissolved: list
pool run.pool.<cell ID>.arrays.dissolved[]: int
pool run.pool.<cell ID>.arrays.dwell_completed_s: list
pool run.pool.<cell ID>.arrays.dwell_completed_s[]: list
pool run.pool.<cell ID>.arrays.dwell_completed_s[][]: float
pool run.pool.<cell ID>.arrays.event_count: list
pool run.pool.<cell ID>.arrays.event_count[]: int
pool run.pool.<cell ID>.arrays.fault: list
pool run.pool.<cell ID>.arrays.fault[]: int
pool run.pool.<cell ID>.arrays.first_passage_s: list
pool run.pool.<cell ID>.arrays.first_passage_s[]: list
pool run.pool.<cell ID>.arrays.first_passage_s[][]: float
pool run.pool.<cell ID>.arrays.fragments: list
pool run.pool.<cell ID>.arrays.fragments[]: list
pool run.pool.<cell ID>.arrays.fragments[][]: int
pool run.pool.<cell ID>.arrays.free: list
pool run.pool.<cell ID>.arrays.free[]: int
pool run.pool.<cell ID>.arrays.full_dwell_completed_s: list
pool run.pool.<cell ID>.arrays.full_dwell_completed_s[]: float
pool run.pool.<cell ID>.arrays.full_first_s: list
pool run.pool.<cell ID>.arrays.full_first_s[]: float
pool run.pool.<cell ID>.arrays.last_event_time_s: list
pool run.pool.<cell ID>.arrays.last_event_time_s[]: float
pool run.pool.<cell ID>.arrays.occupied: list
pool run.pool.<cell ID>.arrays.occupied[]: int
pool run.pool.<cell ID>.arrays.pending_event: list
pool run.pool.<cell ID>.arrays.pending_event[]: int
pool run.pool.<cell ID>.arrays.pending_time_s: list
pool run.pool.<cell ID>.arrays.pending_time_s[]: float
pool run.pool.<cell ID>.arrays.pending_valid: list
pool run.pool.<cell ID>.arrays.pending_valid[]: bool
pool run.pool.<cell ID>.arrays.reaction_counts: list
pool run.pool.<cell ID>.arrays.reaction_counts[]: list
pool run.pool.<cell ID>.arrays.reaction_counts[][]: int
pool run.pool.<cell ID>.arrays.removed: list
pool run.pool.<cell ID>.arrays.removed[]: int
pool run.pool.<cell ID>.arrays.single_returns: list
pool run.pool.<cell ID>.arrays.single_returns[]: int
pool run.pool.<cell ID>.arrays.time_s: list
pool run.pool.<cell ID>.arrays.time_s[]: float
pool run.pool.<cell ID>.seed: int
pool run.pool.<cell ID>.stream_id: int
pool run.potential_t: list
pool run.potentials: dict
pool run.record: str
pool run.record_sha256: str
pool run.refusal: NoneType
pool run.restart: NoneType, dict
pool run.restart.step_index: NoneType
pool run.restart.through: str
pool run.restart.time_s: float
pool run.rows: dict
pool run.seed_index: int
pool run.source: dict
pool run.source.blas_threads: int
pool run.source.checkout_dirty: bool
pool run.source.cpu_model: str
pool run.source.engine_revision: str
pool run.source.jax: str
pool run.source.jaxlib: str
pool run.source.numpy: str
pool run.source.python: str
pool run.source.snapshot: str
pool run.source.snapshot_patch_sha256: str
pool run.status: str
pool run.step_s: NoneType
pool run.steps: NoneType
pool run.strings: dict
pool run.strings.<label>: str
pool run.t: list
pool run.variant: str
pool run.world: str
pool run.world_id: NoneType
pool run.checks: dict
pool run.checks.<cell ID>: dict
pool run.checks.<cell ID>.backend: str
pool run.checks.<cell ID>.checkpoint_manifest_sha256: str
pool run.checks.<cell ID>.chunks: int
pool run.checks.<cell ID>.committed_events: int
pool run.checks.<cell ID>.compile_seconds: float
pool run.checks.<cell ID>.currently_full_cages: int
pool run.checks.<cell ID>.device: str
pool run.checks.<cell ID>.device_kind: str
pool run.checks.<cell ID>.dwell_by_size_total_s: list
pool run.checks.<cell ID>.dwell_by_size_total_s[]: float
pool run.checks.<cell ID>.elapsed_seconds: float
pool run.checks.<cell ID>.ever_full_cages: int
pool run.checks.<cell ID>.execute_seconds: float
pool run.checks.<cell ID>.experimental_validation: bool
pool run.checks.<cell ID>.final_attached_trimers: int
pool run.checks.<cell ID>.final_bond_histogram: list
pool run.checks.<cell ID>.final_bond_histogram[]: int
pool run.checks.<cell ID>.final_fragment_trimers: int
pool run.checks.<cell ID>.final_free_trimers: int
pool run.checks.<cell ID>.final_size_histogram: list
pool run.checks.<cell ID>.final_size_histogram[]: int
pool run.checks.<cell ID>.finished_utc: str
pool run.checks.<cell ID>.full_cage_dwell_total_s: float
pool run.checks.<cell ID>.initial_total_trimers: int
pool run.checks.<cell ID>.material_residual_trimers: int
pool run.checks.<cell ID>.model: str
pool run.checks.<cell ID>.precision: str
pool run.checks.<cell ID>.reaction_counts: dict
pool run.checks.<cell ID>.reaction_counts.association: int
pool run.checks.<cell ID>.reaction_counts.bond_break: int
pool run.checks.<cell ID>.reaction_counts.closure: int
pool run.checks.<cell ID>.reaction_counts.fragment_dissolution: int
pool run.checks.<cell ID>.rng: str
pool run.checks.<cell ID>.scope: str
pool run.checks.<cell ID>.status: str
pool run.checks.<cell ID>.through_time_s: float
pool run.checks.<cell ID>.total_seconds: float
pool run.checks.<cell ID>.worlds: int
pool run.definition: dict
pool run.definition.composed: dict
pool run.definition.composed.ionic: dict
pool run.definition.composed.ionic.execution: dict
pool run.definition.composed.ionic.execution.backend: str
pool run.definition.composed.ionic.execution.capacity: int
pool run.definition.composed.ionic.execution.channel_capacity: int
pool run.definition.composed.ionic.execution.dt: float
pool run.definition.composed.ionic.execution.edge_capacity: int
pool run.definition.composed.ionic.execution.extracellular_capacity: int
pool run.definition.composed.ionic.execution.face_capacity: int
pool run.definition.composed.ionic.execution.field_solver: str
pool run.definition.composed.ionic.execution.jit: bool
pool run.definition.composed.ionic.execution.material_balance_atol_fmol: dict
pool run.definition.composed.ionic.execution.material_balance_atol_fmol.<species>: float
pool run.definition.composed.ionic.execution.max_steps: int
pool run.definition.composed.ionic.execution.max_trace_bytes: int
pool run.definition.composed.ionic.execution.membrane_capacity: int
pool run.definition.composed.ionic.execution.precision: str
pool run.definition.composed.ionic.execution.solver: str
pool run.definition.composed.ionic.experiment: dict
pool run.definition.composed.ionic.experiment.calcium_pump_controls: list
pool run.definition.composed.ionic.experiment.channel_controls: list
pool run.definition.composed.ionic.experiment.channel_controls[]: dict
pool run.definition.composed.ionic.experiment.channel_controls[].channel_id: str
pool run.definition.composed.ionic.experiment.channel_controls[].schedule: list
pool run.definition.composed.ionic.experiment.channel_controls[].schedule[]: dict
pool run.definition.composed.ionic.experiment.channel_controls[].schedule[].availability: float
pool run.definition.composed.ionic.experiment.channel_controls[].schedule[].time: float
pool run.definition.composed.ionic.experiment.end_time: float
pool run.definition.composed.ionic.experiment.junction_controls: list
pool run.definition.composed.ionic.experiment.junction_controls[]: dict
pool run.definition.composed.ionic.experiment.junction_controls[].junction_id: str
pool run.definition.composed.ionic.experiment.junction_controls[].schedule: list
pool run.definition.composed.ionic.experiment.junction_controls[].schedule[]: dict
pool run.definition.composed.ionic.experiment.junction_controls[].schedule[].availability: float
pool run.definition.composed.ionic.experiment.junction_controls[].schedule[].time: float
pool run.definition.composed.ionic.experiment.membrane_controls: list
pool run.definition.composed.ionic.experiment.membrane_controls[]: dict
pool run.definition.composed.ionic.experiment.membrane_controls[].membrane_id: str
pool run.definition.composed.ionic.experiment.membrane_controls[].schedule: list
pool run.definition.composed.ionic.experiment.membrane_controls[].schedule[]: dict
pool run.definition.composed.ionic.experiment.membrane_controls[].schedule[].availability: float
pool run.definition.composed.ionic.experiment.membrane_controls[].schedule[].time: float
pool run.definition.composed.ionic.experiment.observation_times: list
pool run.definition.composed.ionic.experiment.observation_times[]: float
pool run.definition.composed.ionic.experiment.pump_controls: list
pool run.definition.composed.ionic.experiment.pump_controls[]: dict
pool run.definition.composed.ionic.experiment.pump_controls[].pump_id: str
pool run.definition.composed.ionic.experiment.pump_controls[].schedule: list
pool run.definition.composed.ionic.experiment.pump_controls[].schedule[]: dict
pool run.definition.composed.ionic.experiment.pump_controls[].schedule[].availability: float
pool run.definition.composed.ionic.experiment.pump_controls[].schedule[].time: float
pool run.definition.composed.ionic.model: dict
pool run.definition.composed.ionic.model.cells: list
pool run.definition.composed.ionic.model.cells[]: dict
pool run.definition.composed.ionic.model.cells[].fixed_charge_equivalent_fmol: float
pool run.definition.composed.ionic.model.cells[].id: str
pool run.definition.composed.ionic.model.cells[].initial_amount_fmol: dict
pool run.definition.composed.ionic.model.cells[].initial_amount_fmol.<species>: float
pool run.definition.composed.ionic.model.cells[].initial_charge_C: float
pool run.definition.composed.ionic.model.cells[].volume_pL: float
pool run.definition.composed.ionic.model.channels: list
pool run.definition.composed.ionic.model.channels[]: dict
pool run.definition.composed.ionic.model.channels[].abundance: float
pool run.definition.composed.ionic.model.channels[].id: str
pool run.definition.composed.ionic.model.channels[].initial_gate: list
pool run.definition.composed.ionic.model.channels[].initial_gate[]: float
pool run.definition.composed.ionic.model.channels[].kinetic_law: str
pool run.definition.composed.ionic.model.channels[].max_permeability_m_per_s: float
pool run.definition.composed.ionic.model.channels[].membrane_id: str
pool run.definition.composed.ionic.model.channels[].permeant_ions: list
pool run.definition.composed.ionic.model.channels[].permeant_ions[]: dict
pool run.definition.composed.ionic.model.channels[].permeant_ions[].relative_permeability: float
pool run.definition.composed.ionic.model.channels[].permeant_ions[].species_id: str
pool run.definition.composed.ionic.model.closure: dict
pool run.definition.composed.ionic.model.closure.gauge_reference: str
pool run.definition.composed.ionic.model.closure.law: str
pool run.definition.composed.ionic.model.extracellular: list
pool run.definition.composed.ionic.model.extracellular[]: dict
pool run.definition.composed.ionic.model.extracellular[].boundary_potential_V: float
pool run.definition.composed.ionic.model.extracellular[].fixed_charge_equivalent_fmol: float
pool run.definition.composed.ionic.model.extracellular[].id: str
pool run.definition.composed.ionic.model.extracellular[].initial_amount_fmol: dict
pool run.definition.composed.ionic.model.extracellular[].initial_amount_fmol.<species>: float
pool run.definition.composed.ionic.model.extracellular[].initial_charge_C: float
pool run.definition.composed.ionic.model.extracellular[].reservoir: bool
pool run.definition.composed.ionic.model.extracellular[].volume_pL: float
pool run.definition.composed.ionic.model.faces: list
pool run.definition.composed.ionic.model.faces[]: dict
pool run.definition.composed.ionic.model.faces[].area_m2: float
pool run.definition.composed.ionic.model.faces[].diffusivity_m2_per_s: dict
pool run.definition.composed.ionic.model.faces[].diffusivity_m2_per_s.<species>: float
pool run.definition.composed.ionic.model.faces[].id: str
pool run.definition.composed.ionic.model.faces[].law: str
pool run.definition.composed.ionic.model.faces[].length_m: float
pool run.definition.composed.ionic.model.faces[].receiver: str
pool run.definition.composed.ionic.model.faces[].sender: str
pool run.definition.composed.ionic.model.id: str
pool run.definition.composed.ionic.model.junctions: list
pool run.definition.composed.ionic.model.junctions[]: dict
pool run.definition.composed.ionic.model.junctions[].area_m2: float
pool run.definition.composed.ionic.model.junctions[].gate: dict
pool run.definition.composed.ionic.model.junctions[].gate.initial_gate: float
pool run.definition.composed.ionic.model.junctions[].gate.law: str
pool run.definition.composed.ionic.model.junctions[].gate.minimum_open_fraction: float
pool run.definition.composed.ionic.model.junctions[].gate.threshold_voltage_V: float
pool run.definition.composed.ionic.model.junctions[].id: str
pool run.definition.composed.ionic.model.junctions[].law: str
pool run.definition.composed.ionic.model.junctions[].permeability_m_per_s: dict
pool run.definition.composed.ionic.model.junctions[].permeability_m_per_s.<species>: float
pool run.definition.composed.ionic.model.junctions[].receiver: str
pool run.definition.composed.ionic.model.junctions[].sender: str
pool run.definition.composed.ionic.model.membranes: list
pool run.definition.composed.ionic.model.membranes[]: dict
pool run.definition.composed.ionic.model.membranes[].area_m2: float
pool run.definition.composed.ionic.model.membranes[].calcium_pump: NoneType
pool run.definition.composed.ionic.model.membranes[].capacitance_F: float
pool run.definition.composed.ionic.model.membranes[].id: str
pool run.definition.composed.ionic.model.membranes[].inside: str
pool run.definition.composed.ionic.model.membranes[].law: str
pool run.definition.composed.ionic.model.membranes[].outside: str
pool run.definition.composed.ionic.model.membranes[].permeability_m_per_s: dict
pool run.definition.composed.ionic.model.membranes[].permeability_m_per_s.<species>: float
pool run.definition.composed.ionic.model.membranes[].pump: dict
pool run.definition.composed.ionic.model.membranes[].pump.capacity_fmol_per_s: float
pool run.definition.composed.ionic.model.membranes[].pump.id: str
pool run.definition.composed.ionic.model.membranes[].pump.km_atp_mM: float
pool run.definition.composed.ionic.model.membranes[].pump.km_k_mM: float
pool run.definition.composed.ionic.model.membranes[].pump.km_na_mM: float
pool run.definition.composed.ionic.model.membranes[].pump.law: str
pool run.definition.composed.ionic.model.membranes[].pump.metabolism: dict
pool run.definition.composed.ionic.model.membranes[].pump.metabolism.adp_mM: float
pool run.definition.composed.ionic.model.membranes[].pump.metabolism.atp_mM: float
pool run.definition.composed.ionic.model.membranes[].pump.metabolism.delta_g0_J_per_mol: float
pool run.definition.composed.ionic.model.membranes[].pump.metabolism.kind: str
pool run.definition.composed.ionic.model.membranes[].pump.metabolism.pi_mM: float
pool run.definition.composed.ionic.model.membranes[].pump.roles: dict
pool run.definition.composed.ionic.model.membranes[].pump.roles.potassium: str
pool run.definition.composed.ionic.model.membranes[].pump.roles.sodium: str
pool run.definition.composed.ionic.model.membranes[].pump.stoichiometry: dict
pool run.definition.composed.ionic.model.membranes[].pump.stoichiometry.<species>: int
pool run.definition.composed.ionic.model.species: list
pool run.definition.composed.ionic.model.species[]: dict
pool run.definition.composed.ionic.model.species[].id: str
pool run.definition.composed.ionic.model.species[].valence: int
pool run.definition.composed.ionic.model.temperature_K: float
pool run.definition.composed.ionic.schema_version: int
pool run.definition.composed.pools: list
pool run.definition.composed.pools[]: dict
pool run.definition.composed.pools[].channels: list
pool run.definition.composed.pools[].channels[]: str
pool run.definition.composed.pools[].levels: dict
pool run.definition.composed.pools[].levels.false: float
pool run.definition.composed.pools[].levels.true: float
pool run.definition.composed.pools[].observable: str
pool run.definition.composed.pools[].pool: dict
pool run.definition.composed.pools[].pool.end_time_s: float
pool run.definition.composed.pools[].pool.event_chunk_size: int
pool run.definition.composed.pools[].pool.initial_bond_indices: list
pool run.definition.composed.pools[].pool.initial_bond_indices[]: int
pool run.definition.composed.pools[].pool.initial_free_trimers: int
pool run.definition.composed.pools[].pool.initial_nodes: list
pool run.definition.composed.pools[].pool.initial_nodes[]: int
pool run.definition.composed.pools[].pool.k_close_s_inv: float
pool run.definition.composed.pools[].pool.k_fragment_dissolve_s_inv: float
pool run.definition.composed.pools[].pool.k_off_s_inv: float
pool run.definition.composed.pools[].pool.k_on_M_inv_s: float
pool run.definition.composed.pools[].pool.max_events_per_world: int
pool run.definition.composed.pools[].pool.max_output_bytes: int
pool run.definition.composed.pools[].pool.max_wall_seconds: float
pool run.definition.composed.pools[].pool.model: str
pool run.definition.composed.pools[].pool.pool_volume_L: float
pool run.definition.composed.pools[].pool.recording: str
pool run.definition.composed.pools[].pool.root_node: int
pool run.definition.composed.pools[].pool.seed: int
pool run.definition.composed.pools[].pool.topology: str
pool run.definition.composed.pools[].pool.world_id_start: int
pool run.definition.composed.pools[].pool.worlds: int
pool run.definition.composed.schema_version: int
pool run.definition.pools: dict
pool run.definition.pools.<cell ID>: dict
pool run.definition.pools.<cell ID>.end_time_s: float
pool run.definition.pools.<cell ID>.event_chunk_size: int
pool run.definition.pools.<cell ID>.initial_bond_indices: list
pool run.definition.pools.<cell ID>.initial_bond_indices[]: int
pool run.definition.pools.<cell ID>.initial_free_trimers: int
pool run.definition.pools.<cell ID>.initial_nodes: list
pool run.definition.pools.<cell ID>.initial_nodes[]: int
pool run.definition.pools.<cell ID>.k_close_s_inv: float
pool run.definition.pools.<cell ID>.k_fragment_dissolve_s_inv: float
pool run.definition.pools.<cell ID>.k_off_s_inv: float
pool run.definition.pools.<cell ID>.k_on_M_inv_s: float
pool run.definition.pools.<cell ID>.max_events_per_world: int
pool run.definition.pools.<cell ID>.max_output_bytes: int
pool run.definition.pools.<cell ID>.max_wall_seconds: float
pool run.definition.pools.<cell ID>.model: str
pool run.definition.pools.<cell ID>.pool_volume_L: float
pool run.definition.pools.<cell ID>.recording: str
pool run.definition.pools.<cell ID>.root_node: int
pool run.definition.pools.<cell ID>.seed: int
pool run.definition.pools.<cell ID>.topology: str
pool run.definition.pools.<cell ID>.world_id_start: int
pool run.definition.pools.<cell ID>.worlds: int
```

### The table beside its runs

```text
table.consumer: str
table.kind: str
table.missing: list
table.part: int
table.units: dict
table.units.amount: str
table.units.energy: str
table.units.potential: str
table.units.time: str
```

**The retry's tables** hold the same keys and types.
