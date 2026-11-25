# The worlds, what a canonical definition must hold, and the runs (Part 1)

`inputs.json` governs the numbers. Where this text and it differ, stop and ask.

## 0. Units and constants

- **Units:** amounts in fmol, volumes in pL, concentrations in mM (1 mM = 1 fmol/pL = 1 mol/m³), areas in m², lengths in m,
  permeabilities in m/s, diffusivities in m²/s, capacitances in F, charges in C, potentials in V, energies in pJ, times in s.
- **Constants:** F = 6.02214076 × 10²³ × 1.602176634 × 10⁻¹⁹ C/mol and R = 6.02214076 × 10²³ × 1.380649 × 10⁻²³ J/mol/K, each the double
  product, and 1 fmol = 10⁻¹⁵ mol. They are in `inputs.json`. Both sides use them.
- **A declared number** is its nearest double, as `inputs.json` prints it.
- **ε = 2⁻⁵².**

## 1. The consumers

| Consumer | What legacy ran | Worlds here | Equations |
| --- | --- | --- | --- |
| `jupiter` | The JUPITER readiness check's two arms: two cells, one junction, three outside regions joined by three faces, one Na/K pump and one Kv1.5-type channel per cell | `jupiter_baseline`, `jupiter_pump_release` (both pumps off from 5 to 10 ms) | Same |
| `cell` | The assembly-regulated cell: one cell, one finite outside region, one pump, one channel, whose availability is set by one assembly pool. 64 worlds a seed | `cell` | Same, and the pool is live code |
| `base` | The assembly-regulated cluster's base: the JUPITER cluster with two pools, one per cell. 8 worlds a seed | `base` | Same, and the pool is live code |
| `integrated` | The integrated ensemble's world: seven cells, twelve gated junctions, one finite outside region, no pump, leak or channel. The junctions' availability follows a schedule: 1, 0.5 from 5 ms, 0 from 10 ms, 1 from 15 ms | `integrated` | Same |

**"Same equations"** means that the re-expression keeps the model's equations and changes only the code and the way it is
declared. A band applies. No consumer of Part 1 is a changed model.

**What the re-expression of Part 1 is.** Each ionic world is a closed world of the engine's inner tissue model, version 3, integrated by
RK4. Each assembly world is a run of the live assembly pool, whose event path becomes the ionic world's channel schedule (§3.2).

## 2. What a canonical definition must hold

**The rule.** A world's block in `inputs.json` is the content of the captured definition, value for value, in canonical terms.
A candidate's definition holds it, at the precision of §2.4. The exporter writes the block back from **the definition the engine parsed
and ran**, not from this folder (`TABLE.md` §3).

### 2.1 By name

| In the block | In the canonical definition |
| --- | --- |
| `species`, `temperature_K` | Species Na, K, Cl with valences +1, +1, −1. No other row. No species registry, kind, operator or label |
| `cells`, `outside` | Each compartment's volume, initial amounts, fixed charge and initial charge. No region is held: every `held` is false |
| `gauge`, `gauge_potential_V` | The closure's gauge reference, at 0 V. The world is closed: no reservoir, no electrode |
| `membranes` | Inside, outside, area, capacitance, the constant-field permeability of every species, the pump (or none). No calcium pump |
| `membranes[].pump` | The Na/K pump on maintained fuel: 3 Na out and 2 K in a cycle, its capacity, its three constants and its fuel |
| `channels` | One population per cell: its membrane, its permeant species K (relative permeability 1), its maximal permeability, its abundance, its two gates' initial values (m, h in that order). No factor, no block |
| `junctions` | `sender` (the captured `from_cell`), `receiver` (`to_cell`), area, permeabilities and the one-gate relaxation law's threshold, minimum and initial gate |
| `faces` | Sender, receiver, area, length and a diffusivity per species |
| `controls` | Schedules as `[time, value]`, each in force from its time. `leak` is a membrane's availability, `pump` the pump's, `channel` the population's, `junction` the junction's |
| `material_tolerance_fmol` | The execution's material tolerance per species |
| `end_s` | The horizon, 0.02 s |

**Which pieces a world names** (laws, the model, the solver, the field solver, the closure, the observable) is in the strings note, by label. **The full set of strings that a run declares is recorded and compared exactly** (`TABLE.md` §3 `strings` and `declared_strings`, §5): a missing label, an extra label and an extra string each make the run a departing echo, so an extra operator, kind or law is visible.

### 2.2 Derived declarations, by rule

Legacy declares a specific capacitance and an initial voltage. The canonical form declares a capacitance and a charge.

- **Capacitance** = area × specific capacitance, the double product. `inputs.json` holds it as `capacitance_F`.
- **A cell's initial charge** = capacitance × initial voltage, the double product (`initial_charge_C`).
- **An outside region's initial charge** = minus the correctly rounded sum of the charges of the cells that face it, and 0 for a region
  that no membrane faces.
- **Fixed charges** are the captured ones. The inner model's charge anchor admits them: the largest disagreement between a captured
  fixed charge and its rule is 5.1 × 10⁻²⁴ C, far below the model's anchor floor of 10⁻²⁰ C.
- **The captured leak multipliers** are 1 for every species at every time, so one availability of 1 per membrane holds them. A per-species
  multiplier has no canonical counterpart and none is used.
- **The captured pump multiplier** becomes the pump's availability, and the captured open fraction the junction's availability.

### 2.3 What has no counterpart, and is left out

- Array capacities and padding.
- The observation at 7.3 × 10⁻⁵ s (`jupiter`) and at 3.713 × 10⁻³ s (`integrated`). They are off the grid, and the inner model refuses an
  observation that is not an accepted boundary. Legacy's values there are interpolants. They are not compared.
- `integrated`: the captured pump schedules of membranes that have no pump.
- The window size, the trace budget and the backend.

### 2.4 The echo's precision

A candidate's block is compared with `inputs.json`'s block (`CRITERIA.md` §5). The literal blocks are in §2.5.
- numbers to 10⁻¹² relative, each against its own value. A declared zero is exactly zero;
- **an outside region's initial charge** to 10⁻¹² of the sum of the magnitudes of the charges of the cells that face it, since it is a sum
  that cancels;
- **a cell's `initial_voltage_V`** is derived by the exporter as `initial_charge_C` divided by the capacitance of its membrane, since a canonical definition declares a charge and not a voltage. It is compared to 10⁻¹² relative;
- a number in a schedule or a time, to 10⁻¹² relative. Integers, strings and booleans, exactly;
- **maps by key, never by order.** A JSON 4 equals 4.0. An empty list is `[]` and an empty map is `{}`, and either may stand for the other where §2.5 shows an empty one;
- **a default that one party writes out and the other omits refuses nothing.** The defaults are: `held` false, `gauge_potential_V` 0.0, a membrane's `pump` null, empty `junctions`, `faces` and `channels`, an empty entry of `controls`, and in a pool block `initial_bond_indices` (the bonds between initial nodes that the graph has), `root_node` 10 and `world_id_start` 0;
- **a schedule** is compared as §3.2 says, with the initial entry [0, 1] set apart;
- **class E, not echo:** `controls.channel` of `cell` and `base` (`inputs.json` holds a sentence in its place), `inputs.assembly`'s `pool_seeds` and `switch_list`, and **a pool run's `seed`** (`CRITERIA.md` §4.1). `inputs.assembly`'s `assembly_observable` is an echo of a label, and its `composed_file_fingerprint` is recorded;
- **recorded, not compared:** a pool's `harness` fields (`event_chunk_size`, `recording`, `max_output_bytes`, `max_wall_seconds`), since a candidate's pool run records events;
- a key that `inputs.json` does not hold is recorded, and refuses nothing.

### 2.5 The literal blocks, one per kind of run

These are `inputs.json`'s blocks, in its own form. They are the captured definitions' canonical form with labels in place of registered IDs: a `law` is the label of the law the captured definition names in that place, the derived declarations of §2.2 and the voltage of §2.4 are written out, and so is every default. `controls.channel` of `cell` and `base` holds a sentence. A field that no captured definition holds is not here.

**`jupiter`** (`jupiter_baseline`; `jupiter_pump_release` differs in `controls.pump` alone, [[0.0, 1.0], [0.005, 0.0], [0.01, 1.0]] for both membranes):

```json
{
 "temperature_K": 298.15,
 "species": {"Na": 1, "K": 1, "Cl": -1},
 "cells": {
  "cell_0": {"volume_pL": 0.5, "initial_amount_fmol": {"Cl": 4.0, "K": 70.0, "Na": 6.0}, "fixed_charge_fmol": -72.00186556853812, "initial_voltage_V": -0.06, "initial_charge_C": -1.8e-13},
  "cell_1": {"volume_pL": 0.7, "initial_amount_fmol": {"Cl": 7.0, "K": 91.0, "Na": 10.5}, "fixed_charge_fmol": -94.5014924548305, "initial_voltage_V": -0.04, "initial_charge_C": -1.44e-13}
 },
 "outside": {
  "local": {"volume_pL": 2.0, "initial_amount_fmol": {"Cl": 220.0, "K": 8.0, "Na": 280.0}, "fixed_charge_fmol": -67.99664197663137, "initial_charge_C": 3.24e-13, "held": false},
  "near": {"volume_pL": 1.0, "initial_amount_fmol": {"Cl": 105.0, "K": 8.0, "Na": 120.0}, "fixed_charge_fmol": -23.0, "initial_charge_C": 0.0, "held": false},
  "far": {"volume_pL": 3.0, "initial_amount_fmol": {"Cl": 345.0, "K": 9.0, "Na": 450.0}, "fixed_charge_fmol": -114.0, "initial_charge_C": 0.0, "held": false}
 },
 "gauge": "local",
 "gauge_potential_V": 0.0,
 "membranes": {
  "membrane_0": {"inside": "cell_0", "outside": "local", "area_m2": 3e-10, "capacitance_F": 3e-12, "law": "constant_field", "permeability_m_per_s": {"Cl": 8e-11, "K": 2e-10, "Na": 1e-11}, "pump": {"law": "nak_pump_positive", "sodium_out": 3, "potassium_in": 2, "capacity_fmol_per_s": 0.05, "km_na_mM": 12.0, "km_k_mM": 0.2, "km_atp_mM": 0.5, "fuel": {"law": "maintained_fuel", "atp_mM": 1.5, "adp_mM": 0.1, "pi_mM": 0.1, "delta_g0_J_per_mol": -37000.0}}},
  "membrane_1": {"inside": "cell_1", "outside": "local", "area_m2": 3.6e-10, "capacitance_F": 3.6e-12, "law": "constant_field", "permeability_m_per_s": {"Cl": 8e-11, "K": 2e-10, "Na": 1e-11}, "pump": {"law": "nak_pump_positive", "sodium_out": 3, "potassium_in": 2, "capacity_fmol_per_s": 0.1, "km_na_mM": 12.0, "km_k_mM": 0.2, "km_atp_mM": 0.5, "fuel": {"law": "maintained_fuel", "atp_mM": 1.5, "adp_mM": 0.1, "pi_mM": 0.1, "delta_g0_J_per_mol": -37000.0}}}
 },
 "channels": {
  "channel_0": {"membrane": "membrane_0", "law": "kv15_mh", "species": "K", "max_permeability_m_per_s": 3e-10, "abundance": 0.5, "initial_gates": {"m": 0.2, "h": 0.7}},
  "channel_1": {"membrane": "membrane_1", "law": "kv15_mh", "species": "K", "max_permeability_m_per_s": 3e-10, "abundance": 0.6, "initial_gates": {"m": 0.2, "h": 0.7}}
 },
 "junctions": {
  "junction": {"sender": "cell_0", "receiver": "cell_1", "area_m2": 1e-10, "law": "constant_field", "permeability_m_per_s": {"Cl": 4e-10, "K": 5e-10, "Na": 3e-10}, "gate": {"law": "junction_relaxation", "threshold_voltage_V": 0.015, "minimum_open_fraction": 0.1, "initial_gate": 0.6}}
 },
 "faces": {
  "face_0": {"law": "logmean_face", "sender": "local", "receiver": "near", "area_m2": 1e-11, "length_m": 2e-05, "diffusivity_m2_per_s": {"Cl": 2e-09, "K": 1.7e-09, "Na": 1.2e-09}},
  "face_1": {"law": "logmean_face", "sender": "near", "receiver": "far", "area_m2": 1e-11, "length_m": 2e-05, "diffusivity_m2_per_s": {"Cl": 2e-09, "K": 1.7e-09, "Na": 1.2e-09}},
  "face_2": {"law": "logmean_face", "sender": "far", "receiver": "local", "area_m2": 1e-11, "length_m": 2e-05, "diffusivity_m2_per_s": {"Cl": 2e-09, "K": 1.7e-09, "Na": 1.2e-09}}
 },
 "controls": {
  "leak": {"membrane_0": [[0.0, 1.0]], "membrane_1": [[0.0, 1.0]]},
  "pump": {"membrane_0": [[0.0, 1.0]], "membrane_1": [[0.0, 1.0]]},
  "channel": {"channel_0": [[0.0, 1.0]], "channel_1": [[0.0, 1.0]]},
  "junction": {"junction": [[0.0, 1.0]]}
 },
 "material_tolerance_fmol": {"Cl": 2e-11, "K": 2e-11, "Na": 2e-11},
 "end_s": 0.02
}
```

**`cell`:**

```json
{
 "temperature_K": 298.15,
 "species": {"Na": 1, "K": 1, "Cl": -1},
 "cells": {
  "cell_0": {"volume_pL": 1.0, "initial_amount_fmol": {"Na": 12.0, "K": 140.0, "Cl": 10.0}, "fixed_charge_fmol": -142.008291415725, "initial_voltage_V": -0.08, "initial_charge_C": -8.000000000000001e-13}
 },
 "outside": {
  "outside": {"volume_pL": 1.0, "initial_amount_fmol": {"Na": 140.0, "K": 4.0, "Cl": 120.0}, "fixed_charge_fmol": -23.991708584274992, "initial_charge_C": 8.000000000000001e-13, "held": false}
 },
 "gauge": "outside",
 "gauge_potential_V": 0.0,
 "membranes": {
  "membrane_0": {"inside": "cell_0", "outside": "outside", "area_m2": 1e-09, "capacitance_F": 1.0000000000000001e-11, "law": "constant_field", "permeability_m_per_s": {"Na": 5e-10, "K": 1.8e-09, "Cl": 1.4e-10}, "pump": {"law": "nak_pump_positive", "sodium_out": 3, "potassium_in": 2, "capacity_fmol_per_s": 0.09999999999999999, "km_na_mM": 12.0, "km_k_mM": 0.2, "km_atp_mM": 0.5, "fuel": {"law": "maintained_fuel", "atp_mM": 1.5, "adp_mM": 0.1, "pi_mM": 0.1, "delta_g0_J_per_mol": -37000.0}}}
 },
 "channels": {
  "channel_0": {"membrane": "membrane_0", "law": "kv15_mh", "species": "K", "max_permeability_m_per_s": 1e-08, "abundance": 1.0, "initial_gates": {"m": 0.2, "h": 0.8}}
 },
 "junctions": {},
 "faces": {},
 "controls": {"leak": {"membrane_0": [[0.0, 1.0]]}, "pump": {"membrane_0": [[0.0, 1.0]]}, "channel": "the pool's path (SPEC.md section 3.2)", "junction": {}},
 "material_tolerance_fmol": {"Na": 2e-11, "K": 2e-11, "Cl": 2e-11},
 "end_s": 0.02
}
```

**`base`:** the `jupiter_baseline` block above, with `controls.channel` the sentence of `cell`.

**`integrated`:**

```json
{
 "temperature_K": 298.15,
 "species": {"Na": 1, "K": 1, "Cl": -1},
 "cells": {
  "cell_0": {"volume_pL": 0.460614559625212, "initial_amount_fmol": {"Cl": 3.6584827313820227, "K": 68.27668980701006, "Na": 3.6320489857623492}, "fixed_charge_fmol": -68.25087407181402, "initial_voltage_V": -0.020573879941257294, "initial_charge_C": -5.962894098195377e-14},
  "cell_1": {"volume_pL": 0.4558462907444638, "initial_amount_fmol": {"Cl": 3.9245077488853, "K": 66.35430133846228, "Na": 4.20224517181489}, "fixed_charge_fmol": -66.63245156070748, "initial_voltage_V": -0.013907213274749855, "initial_charge_C": -3.982907906817775e-14},
  "cell_2": {"volume_pL": 0.4491832606546999, "initial_amount_fmol": {"Cl": 4.166599373141808, "K": 64.18658942527874, "Na": 4.739732661046016}, "fixed_charge_fmol": -64.75993579700193, "initial_voltage_V": -0.007240546607505364, "initial_charge_C": -2.055946304374643e-14},
  "cell_3": {"volume_pL": 0.4567553253082257, "initial_amount_fmol": {"Cl": 4.54134098117871, "K": 64.05059463076579, "Na": 5.428639359891615}, "fixed_charge_fmol": -64.93791024126357, "initial_voltage_V": -0.0005738799409941017, "initial_charge_C": -1.6626144847526947e-15},
  "cell_4": {"volume_pL": 0.45623012693402465, "initial_amount_fmol": {"Cl": 4.840272555473904, "K": 62.760332626228816, "Na": 6.03070409547561}, "fixed_charge_fmol": -63.950582143005555, "initial_voltage_V": 0.006092786725719652, "initial_charge_C": 1.7562571314980532e-14},
  "cell_5": {"volume_pL": 0.46207333837976106, "initial_amount_fmol": {"Cl": 5.210313706297759, "K": 62.33194608316596, "Na": 6.724040705557431}, "fixed_charge_fmol": -63.84528977260093, "initial_voltage_V": 0.012759453392520041, "initial_charge_C": 3.6983775742207336e-14},
  "cell_6": {"volume_pL": 0.8617615649509048, "initial_amount_fmol": {"Cl": 10.291684011825442, "K": 113.9503456438611, "Na": 13.689275504043644}, "fixed_charge_fmol": -117.3472413437859, "initial_voltage_V": 0.019426120059112404, "initial_charge_C": 6.713375051634713e-14}
 },
 "outside": {
  "outside": {"volume_pL": 6.75, "initial_amount_fmol": {"Cl": 810.0, "K": 27.0, "Na": 978.75}, "fixed_charge_fmol": -195.75, "initial_charge_C": 5.095645242338089e-24, "held": false}
 },
 "gauge": "outside",
 "gauge_potential_V": 0.0,
 "membranes": {
  "membrane_0": {"inside": "cell_0", "outside": "outside", "area_m2": 2.8982837049796536e-10, "capacitance_F": 2.8982837049796537e-12, "law": "constant_field", "permeability_m_per_s": {"Cl": 0.0, "K": 0.0, "Na": 0.0}, "pump": null},
  "membrane_1": {"inside": "cell_1", "outside": "outside", "area_m2": 2.863915169870302e-10, "capacitance_F": 2.8639151698703023e-12, "law": "constant_field", "permeability_m_per_s": {"Cl": 0.0, "K": 0.0, "Na": 0.0}, "pump": null},
  "membrane_2": {"inside": "cell_2", "outside": "outside", "area_m2": 2.839490463666793e-10, "capacitance_F": 2.839490463666793e-12, "law": "constant_field", "permeability_m_per_s": {"Cl": 0.0, "K": 0.0, "Na": 0.0}, "pump": null},
  "membrane_3": {"inside": "cell_3", "outside": "outside", "area_m2": 2.897146887330887e-10, "capacitance_F": 2.897146887330887e-12, "law": "constant_field", "permeability_m_per_s": {"Cl": 0.0, "K": 0.0, "Na": 0.0}, "pump": null},
  "membrane_4": {"inside": "cell_4", "outside": "outside", "area_m2": 2.8825186414031455e-10, "capacitance_F": 2.8825186414031456e-12, "law": "constant_field", "permeability_m_per_s": {"Cl": 0.0, "K": 0.0, "Na": 0.0}, "pump": null},
  "membrane_5": {"inside": "cell_5", "outside": "outside", "area_m2": 2.8985391932140514e-10, "capacitance_F": 2.8985391932140516e-12, "law": "constant_field", "permeability_m_per_s": {"Cl": 0.0, "K": 0.0, "Na": 0.0}, "pump": null},
  "membrane_6": {"inside": "cell_6", "outside": "outside", "area_m2": 3.4558496659169997e-10, "capacitance_F": 3.4558496659169998e-12, "law": "constant_field", "permeability_m_per_s": {"Cl": 0.0, "K": 0.0, "Na": 0.0}, "pump": null}
 },
 "channels": {},
 "junctions": {
  "junction_0": {"sender": "cell_0", "receiver": "cell_6", "area_m2": 5.825317809332204e-11, "law": "constant_field", "permeability_m_per_s": {"Cl": 7.807692307692307e-10, "K": 7.538461538461537e-10, "Na": 5.115384615384615e-10}, "gate": {"law": "junction_relaxation", "threshold_voltage_V": 0.01, "minimum_open_fraction": 0.05, "initial_gate": 0.24}},
  "junction_1": {"sender": "cell_0", "receiver": "cell_5", "area_m2": 5.7554939330037774e-11, "law": "constant_field", "permeability_m_per_s": {"Cl": 7.807692307692307e-10, "K": 7.538461538461537e-10, "Na": 5.115384615384615e-10}, "gate": {"law": "junction_relaxation", "threshold_voltage_V": 0.015, "minimum_open_fraction": 0.1, "initial_gate": 0.64}},
  "junction_2": {"sender": "cell_0", "receiver": "cell_1", "area_m2": 5.7513896887967e-11, "law": "constant_field", "permeability_m_per_s": {"Cl": 7.807692307692307e-10, "K": 7.538461538461537e-10, "Na": 5.115384615384615e-10}, "gate": {"law": "junction_relaxation", "threshold_voltage_V": 0.02, "minimum_open_fraction": 0.2, "initial_gate": 0.96}},
  "junction_3": {"sender": "cell_1", "receiver": "cell_2", "area_m2": 5.884055808628286e-11, "law": "constant_field", "permeability_m_per_s": {"Cl": 7.807692307692307e-10, "K": 7.538461538461537e-10, "Na": 5.115384615384615e-10}, "gate": {"law": "junction_relaxation", "threshold_voltage_V": 0.01, "minimum_open_fraction": 0.05, "initial_gate": 0.24}},
  "junction_4": {"sender": "cell_1", "receiver": "cell_6", "area_m2": 5.667902067092806e-11, "law": "constant_field", "permeability_m_per_s": {"Cl": 7.807692307692307e-10, "K": 7.538461538461537e-10, "Na": 5.115384615384615e-10}, "gate": {"law": "junction_relaxation", "threshold_voltage_V": 0.015, "minimum_open_fraction": 0.1, "initial_gate": 0.64}},
  "junction_5": {"sender": "cell_2", "receiver": "cell_3", "area_m2": 5.7016806692219477e-11, "law": "constant_field", "permeability_m_per_s": {"Cl": 7.807692307692307e-10, "K": 7.538461538461537e-10, "Na": 5.115384615384615e-10}, "gate": {"law": "junction_relaxation", "threshold_voltage_V": 0.02, "minimum_open_fraction": 0.2, "initial_gate": 0.96}},
  "junction_6": {"sender": "cell_2", "receiver": "cell_6", "area_m2": 5.6030560529393776e-11, "law": "constant_field", "permeability_m_per_s": {"Cl": 7.807692307692307e-10, "K": 7.538461538461537e-10, "Na": 5.115384615384615e-10}, "gate": {"law": "junction_relaxation", "threshold_voltage_V": 0.01, "minimum_open_fraction": 0.05, "initial_gate": 0.24}},
  "junction_7": {"sender": "cell_3", "receiver": "cell_4", "area_m2": 5.6594315116849386e-11, "law": "constant_field", "permeability_m_per_s": {"Cl": 7.807692307692307e-10, "K": 7.538461538461537e-10, "Na": 5.115384615384615e-10}, "gate": {"law": "junction_relaxation", "threshold_voltage_V": 0.015, "minimum_open_fraction": 0.1, "initial_gate": 0.64}},
  "junction_8": {"sender": "cell_3", "receiver": "cell_6", "area_m2": 5.870118897467249e-11, "law": "constant_field", "permeability_m_per_s": {"Cl": 7.807692307692307e-10, "K": 7.538461538461537e-10, "Na": 5.115384615384615e-10}, "gate": {"law": "junction_relaxation", "threshold_voltage_V": 0.02, "minimum_open_fraction": 0.2, "initial_gate": 0.96}},
  "junction_9": {"sender": "cell_4", "receiver": "cell_5", "area_m2": 5.80967370223378e-11, "law": "constant_field", "permeability_m_per_s": {"Cl": 7.807692307692307e-10, "K": 7.538461538461537e-10, "Na": 5.115384615384615e-10}, "gate": {"law": "junction_relaxation", "threshold_voltage_V": 0.01, "minimum_open_fraction": 0.05, "initial_gate": 0.24}},
  "junction_10": {"sender": "cell_4", "receiver": "cell_6", "area_m2": 5.785360400037625e-11, "law": "constant_field", "permeability_m_per_s": {"Cl": 7.807692307692307e-10, "K": 7.538461538461537e-10, "Na": 5.115384615384615e-10}, "gate": {"law": "junction_relaxation", "threshold_voltage_V": 0.015, "minimum_open_fraction": 0.1, "initial_gate": 0.64}},
  "junction_11": {"sender": "cell_5", "receiver": "cell_6", "area_m2": 5.806741432300732e-11, "law": "constant_field", "permeability_m_per_s": {"Cl": 7.807692307692307e-10, "K": 7.538461538461537e-10, "Na": 5.115384615384615e-10}, "gate": {"law": "junction_relaxation", "threshold_voltage_V": 0.02, "minimum_open_fraction": 0.2, "initial_gate": 0.96}}
 },
 "faces": {},
 "controls": {
  "leak": {"membrane_0": [[0.0, 1.0]], "membrane_1": [[0.0, 1.0]], "membrane_2": [[0.0, 1.0]], "membrane_3": [[0.0, 1.0]], "membrane_4": [[0.0, 1.0]], "membrane_5": [[0.0, 1.0]], "membrane_6": [[0.0, 1.0]]},
  "pump": {},
  "channel": {},
  "junction": {"junction_0": [[0.0, 1.0], [0.005, 0.5], [0.01, 0.0], [0.015, 1.0]], "junction_1": [[0.0, 1.0], [0.005, 0.5], [0.01, 0.0], [0.015, 1.0]], "junction_2": [[0.0, 1.0], [0.005, 0.5], [0.01, 0.0], [0.015, 1.0]], "junction_3": [[0.0, 1.0], [0.005, 0.5], [0.01, 0.0], [0.015, 1.0]], "junction_4": [[0.0, 1.0], [0.005, 0.5], [0.01, 0.0], [0.015, 1.0]], "junction_5": [[0.0, 1.0], [0.005, 0.5], [0.01, 0.0], [0.015, 1.0]], "junction_6": [[0.0, 1.0], [0.005, 0.5], [0.01, 0.0], [0.015, 1.0]], "junction_7": [[0.0, 1.0], [0.005, 0.5], [0.01, 0.0], [0.015, 1.0]], "junction_8": [[0.0, 1.0], [0.005, 0.5], [0.01, 0.0], [0.015, 1.0]], "junction_9": [[0.0, 1.0], [0.005, 0.5], [0.01, 0.0], [0.015, 1.0]], "junction_10": [[0.0, 1.0], [0.005, 0.5], [0.01, 0.0], [0.015, 1.0]], "junction_11": [[0.0, 1.0], [0.005, 0.5], [0.01, 0.0], [0.015, 1.0]]}
 },
 "material_tolerance_fmol": {"Cl": 2e-11, "K": 2e-11, "Na": 2e-11},
 "end_s": 0.02
}
```

**A pool run** (`cell s<k> pool`; `base s<k> pool` has one block for each of `cell_0` and `cell_1`). Its echo is, per cell, the pool block with its `channel` and its `stream_id`. Its `seed`, which is `seeds[k]`, is written with them and is class E (§2.4):

```json
{
 "channel": "channel_0",
 "stream_id": 0,
 "seed": 20260920,
 "pool": {
 "model": "pool_model",
 "topology": "pool_topology",
 "initial_nodes": [
  10,
  12,
  14,
  16,
  18
 ],
 "initial_bond_indices": [
  20,
  21,
  24,
  26,
  28
 ],
 "root_node": 10,
 "initial_free_trimers": 50,
 "pool_volume_L": 5e-15,
 "k_on_M_inv_s": 10000000.0,
 "k_close_s_inv": 100.0,
 "k_off_s_inv": 10.0,
 "k_fragment_dissolve_s_inv": 1.0,
 "world_id_start": 0,
 "worlds": 64,
 "end_time_s": 0.02,
 "max_events_per_world": 100000
 }
}
```

**The assembly observable** that an ionic run of `cell` or `base` records is the label `assembly_observable` (`TABLE.md` §3 `inputs.assembly`). It is the rule of §3.2. `inputs.json`'s `coupling` block holds the same label and the two levels (1 and 0), and is informational. `base`'s pools differ from `cell`'s in `k_close_s_inv` (1000), `k_off_s_inv` (300), `worlds` (8), `seed` and `stream_id`.

## 3. What a candidate declares, for the comparison to be lawful

### 3.1 The ionic worlds

| Item | `jupiter`, `cell`, `base` | `integrated` |
| --- | --- | --- |
| Model | The inner tissue model, version 3, with no kind and no operator | The same |
| Integrator | RK4, the classical one. **Declared order 4** | The same |
| Steps h₁, h₂, h₃ | 25, 12.5 and 6.25 µs | 100, 50 and 25 µs |
| Retry step | 3.125 µs | 12.5 µs |
| Why these steps | The channel law's own bound for RK4 is 25 µs, so legacy's 100 and 50 µs are refused by the model | No gated channel, so the model admits 100 µs |
| Field solver | By D147's rule (below). `jupiter` and `base` have free field offsets (their `near` and `far` regions), so they declare **the floor variant** of the factored capacitor reduction (label `field_solver_floor`). `cell` has none and declares the factored capacitor reduction itself (label `field_solver`) | No free field offset: the factored capacitor reduction (label `field_solver`) |
| Heat | Integrated by RK4 with the other states. No heat booking is declared | The same |
| Observation times | On the grid. They include every time of `potential_times_s` (§4) | The same |
| Backend | The CPU, double precision | The same |
| Rows | Every accepted row is recorded | The same |

- **The field solver is not part of the equations compared.** It solves the same algebraic field. Which variant a world declares is the standing rule of D147 (D156 for a composite, which follows its inner model): a definition with at least one free field
  offset declares the floor variant, and one with none keeps its own. The builders apply it with `validation/tissue/field_solver_choice.py`'s `declare()`, and never by hand. D147 also asks for its floor guard to be **rerun with constants before the floor variant serves a run of record**, and no rerun is recorded.
  It is made after the registration tag, on the registered head's frozen snapshot, and recorded before the first registered run (the protocol's §5). An early retro-check of it exists and cannot replace it, because programs that it traces change before the campaign. This folder assumes nothing of its outcome.
- **The candidate's own step** need not be legacy's. The two are compared at the same times (§4).
- **h₁ equals the channel law's stated bound exactly** (25 µs). The engine must admit a step that is equal to the bound. The rehearsal sits at the same bound (§8), so a strict comparison in the engine is found there and not in the campaign.
- **A step that an event splits** is one accepted step for each part. The run then has more accepted rows than its grid (`TABLE.md` §3).

### 3.2 The assembly worlds

**The pool run.** For each seed and each cell's pool, the live assembly pool runs the block's definition to its `end_time_s`. The worlds are
IDs 0 to 63 (`cell`) or 0 to 7 (`base`), the seeds are `pools.<cell>.seeds`, and the initial state is the block's. Each pool
run is recorded as `TABLE.md` §3 says: its 19 final arrays and its event path.

**The event path** of a world and a cell is the list of its committed events, in order: `[time, availability after it]`. The availability is
1 if the number of set bits of the bond mask is at least the number of set bits of the occupied mask, and 0 otherwise. It is 1
before the first event.

**"The path" in this folder is the reference path,** `reference_paths.json`, for a world and a cell. A run's own recorded path is called **the run's own path**, and is class E against the reference path. Every other use of "the path" in this folder, in `TABLE.md`, `PLANTS.md` and `CRITERIA.md`, is the reference path.

**The schedule.** The availability of the channel of that cell, in that world, is the path's: 1 at time 0, and the availability after
each event from that event's time on. An entry that repeats the value before it may be left in or left out. An off-grid change splits the step there.
- **The initial entry [0, 1] is not a change.** It is the level before the first event, and every schedule begins with it. **A change** of a schedule is an entry after it whose value differs from the value before it. **The changes of the path** are its events whose availability differs from the availability before them, beginning with 1. So the path
  `[[0.2, 0], [0.3, 0], [0.4, 1]]` has two changes, at 0.2 and at 0.4. A schedule is compared with the path's changes after its first entry [0, 1] is set apart and the repeats are removed.
- **The event times are the pool's doubles.** They are not rounded, shifted or snapped. No captured event lies within 1.8 × 10⁻⁴ of a step
  from a grid point, at any step down to 1.5625 µs, so the clock's near-miss rule cannot refuse one (measured on the snapshot's own pool code).
- **The availability multiplies the channel only.** It touches no gate, pump, leak, junction or face.
- **The pool never reads the ionic side.**

**The ionic worlds judged.** World IDs 0 to 7 of each of the four seeds, for `cell` and for `base`: 32 ionic families each. For
`cell` the pools are judged on all 64 worlds a seed, and the ionic side on 8 of them. Nothing is said of the ionic side of IDs 8 to 63.

### 3.3 The assembly coupling, as decided

**Dated line, 25 November 2026 (the lead's note).** The user decided the form of the coupling (the plan's G-7): a driver runs the live pool and writes its switch path into the ionic world's channel controls. The ionic world stays the inner model, version 3, on RK4. No run informed the decision. An operator on the composite is not built now, and this registration
holds no form of it. A run of one departs from its strings note and is refused. (An earlier draft of this folder, commit 5f550674, registered a second form, with a held availability, as reported only. It is removed, as the simpler thing to judge.)

**The driver is the builder's.** It makes the schedule from the pool run of the same seed, world and cell. What it made is recorded by the ionic run's definition in the run's inputs, by name (`TABLE.md` §3):
- **the assembly observable,** the law that turns a pool's topology into an availability. It is a registered law with an ID and a page, of the family `assembly_observable` (the user's word). Label `assembly_observable`;
- **the composed file's fingerprint;**
- **the pool's seeds;**
- **the switch list,** the changes of availability that the driver wrote, per channel.

## 4. The runs and the compared times

**`inputs.json` lists every registered run:** its name, consumer, family, world, seed index, world ID, step, role and variant.
- **A family** is the three runs of one world (and one seed and world ID) at h₁, h₂, h₃. Its class S entries need all three.
- **Roles:** `judged`, `support` (the restarts) and `plant` (a declared change).
- **The retry's runs** are registered by rule, only when owed (`CRITERIA.md` §7): `<family> h=<step> retry`.
- **Counts:** `jupiter` 6 judged, 1 support, 1 plant. `integrated` 3 judged. `cell` 4 pool, 96 ionic, 1 support. `base` 4 pool, 96 ionic, 1 support, 1 plant. 214 in all.

**Compared times.**
- **`jupiter` and `integrated`,** for every readout but the potentials: the grid of `history_times`, i × spacing from its first to its last (`inputs.json`). Every run has a row at each.
- **The potentials** (`voltage`, `phi_out`): the block's `potential_times_s`. For `cell` and `base`, 0 and then the block's `summary_times_s`.
- **`cell`:** `end_s`. **`base`:** `end_s`, and for `voltage` and `channel_K` also the other `summary_times_s`.
- **A time matches a registered one within 10⁻¹² s** of it. The captured observation times themselves carry a last digit (0.0075 s is held as
  0.007500000000000001 s), so no comparison reads a time by its bits.
- **The first row of a run is time 0** and its V₀ is read there (`READOUTS.md` §5).

**Grid points, and what is on the grid.** The point k h of a run is the double product of the integer k and the declared step's double h.
- **On the grid.** A declared change, observation or row time t is on the grid if it differs from some k h by at most 2 ε t. That is the rounding of forming both: t is a declared decimal rounded to a double (ε/2 t), h is a declared decimal rounded to a double, which puts ε/2 t into k h, and the product rounds once more (ε/2 t). The three add to 1.5 ε t.
- **What a builder declares.** Every step and every change, observation or row time is written as the decimal of `inputs.json`, never as a product, a quotient or a sum of other numbers. Every registered time is then an integer multiple of every registered step, so each is on the grid.
- **An off-grid change is a named refusal.** In `jupiter` and `integrated` no change is off the grid. A run whose step list splits at one has more accepted steps than end_s/step_s, and it is refused with the reason `off_grid_change` (`CRITERIA.md` §5). In `cell` and `base` the changes are the pool's events, which split steps by design. A pool event between 2 ε t and 10⁻⁶ of a step from a grid point
  is the engine's near miss and is refused by it, and no captured event is (§3.2).

**Windows.** The captured `window-*.npz` files are read in the natural order of their names, and their numbers are zero-padded, so that the text order is the same. Adjacent windows share one row, at their boundary. **The earlier window owns it,** and the later window's first row is not read.

**The order of an index.** Wherever an index pairs rows with entities, the index is the entity's position in the captured definition's list, in **natural order** (the order in which the definition gives them). So `junction_2` comes before `junction_10`, and a text sort would be wrong. World IDs are the pool's, in order. (`READOUTS.md` §2 gives the index of each array.)

**A restart** (a support run) resumes a checkpoint of its judged run at the checkpoint's time. It continues that run's clock, so its `t` starts at the checkpoint's time and not at 0, and its `steps` counts the accepted steps after the checkpoint. "Every compared time" for it is every compared time after that. The row at the checkpoint's time is needed only if the run holds one.

## 5. The scales

**The rule** (the numbers are `inputs.json`'s, `worlds.<w>.scales`; the checker recomputes them from the block alone). Let T = `end_s`,
V* = 0.12 V (the gate law's domain), T_K the temperature, z the valence, χ = 1 + |z| F V*/(R T_K), and c* the larger of the two
initial concentrations of the species on the two sides (mM).

| Quantity | Scale |
| --- | --- |
| `leak_x` | max over membranes of P_x A/10⁻¹⁵ × c* × χ × T, in fmol |
| `channel_K` | max over channels of P_max × abundance × A/10⁻¹⁵ × c* × χ × T. Opening and availability are taken as 1 |
| `junction_x` | max over junctions of P_x A/10⁻¹⁵ × c* × χ × T. Gate and availability are taken as 1 |
| `face_x` | max over faces of D_x A/L/10⁻¹⁵ × c* × χ × T |
| `pump` | max over membranes of capacity × T, in fmol of cycles |
| `n_cell_x` | max over cells of the sum of the scales of the routes that touch it, the pump's times its stoichiometry |
| `n_out_x` | max over regions of the same sum, faces included |
| Gates | 1 |
| A passive route's heat | Σ_x (its transfer scale) × 10⁻³ R T_K (1 + |ln(c_a/c_b)| + |z| F V*/(R T_K)), in pJ |
| A pump's heat | capacity × T × 10⁻³ × (|ΔG⁰| + R T_K |ln(ADP Pi/(1000 ATP))| + 3 R T_K (1 + |ln Na ratio| + F V*/(R T_K)) + 2 R T_K (1 + |ln K ratio| + F V*/(R T_K))) |
| `heat_membrane` | max over membranes of the sum of its leak's, pump's and channels' heat scales |
| `heat_junction`, `heat_face` | max over junctions, over faces |
| `voltage` | max |V₀| + max over membranes of (F 10⁻¹⁵/C) Σ_x |z| × the cell's sum of route scales |
| `phi_out` | R T_K/F |
| An entry named `<readout>_summary` | The scale of `<readout>` |
| `energy_identity` | The sum over membranes of `heat_membrane`'s terms (leak, pump, channels), over junctions and over faces, plus the pumps' work, plus the amounts' and the capacitors' terms. Work: Σ over pumps of capacity × T × 10⁻³ × (|ΔG⁰| + R T_K |ln(ADP Pi/(1000 ATP))|). Amounts: Σ over compartments and species of (the sum of the scales of the routes that touch it) × 10⁻³ R T_K (1 + |ln(initial concentration)|), in the numeric mM of the concentration. Capacitors: Σ over membranes of 10¹² C s(`voltage`)² |

**`stores`,** beside `scales` in `inputs.json`: the declared amounts that an entry reads, for §6's `e_store`. `n_cell_x`: the largest initial amount of x among the cells. `n_out_x`: among the regions. `voltage`: the largest of (F 10⁻¹⁵/C) Σ_x |z| n₀ over the membranes, n₀ the initial amounts of its cell. `energy_identity`: Σ over compartments and species of 10⁻³ R T_K (1 + |ln(initial concentration)|) n₀, plus Σ over membranes of 10¹² C s(`voltage`) (F 10⁻¹⁵/C) Σ_x |z| n₀. Every other entry has none. **`p`** (the declared order of the candidate, 4 here) and **`closure_terms_V`** (the closure of a potential that has its own, §6) are beside them.

**Why this scale.** It is the gross one-way throughput that a readout is formed from, so a rounding or a solver residual relative to it is
the one the arithmetic makes. It comes from the declared values alone. It is at least the magnitude of the captured ledger in every
entry, and far above it where a net flow is the small difference of two large ones (leak of Cl, the faces).

## 6. The rounding count, derived

A transfer y after S steps is the sum of S increments, each a step times a rate.
- **Additions:** a step adds to a stored value at most five times (the engine's own ledger allowance, 2.5 ε a step, is the same count). Each
  rounds at most ε/2 of a value of at most s. So at most 5 (S + 1) ε/2 × s.
- **Rates:** a rate is evaluated with at most 64 roundings of terms no larger than the gross one-way rate. Over the run the steps sum to the gross throughput,
  which s holds. So at most 64 ε/2 × s, with no factor S.
- **Feedback:** a state's own rounding moves a rate by less than one part in a hundred of the first bound.
- **Total:** at most (5 (S + 1) + 64 + a hundredth of the first) ε/2 × s, which is at most 16 (S + 1) ε/2 × s for S ≥ 8.

So **e_round(S) = 8 ε (S + 1) s**, FR-38's form (`8 ε S s`), with this derivation.

**What e_round assumes about the state.** It counts a state that stores increments from declared references: each state starts at exactly 0, and an addition rounds at most ε/2 of a value of at most s. This is the engine's documented state form: the inner tissue model's state holds `amount_increment` from declared references, and its potentials are formed from the charge anchors and the increments (the engine's
documentation of its state; the author read it at 49529e71, as protocol §11 says). **V₀ is the run's own voltage at time 0** (`READOUTS.md` §5), so a difference between a declared voltage and the voltage an engine formed from its charge anchor does not enter a band.

**What a state that stored amounts would do,** by arithmetic on the inputs alone. Each addition to n₀ + d rounds by at most ε/2 of n₀, and there are at most 5 (S + 1) of them, so at most 2.5 ε (S + 1) n₀. A voltage formed from amounts and fixed charges rounds a few more times in each evaluation, at terms of size (F 10⁻¹⁵/C) Σ |z| n₀, which is less than 10⁻³ of the first. At S = 3,200 (or 800 in `integrated`) this is 1.2 × 10² to 2.8 × 10³ times the band of `n_cell_x` and `voltage` at U_c = 0, and 0.8 to 1.0 × 10⁴ times the band of `n_out_x`. A correct engine of that form would be refused by the bands without it.
**So the bands of the entries that read an amount hold e_store(S) = 2.5 ε (S + 1) × `stores`** (`inputs.json`; 0 for every other entry), for the candidate's own S_c alone, since legacy stores increments (its arrays are `amount_increment`). It admits both forms, and the margins of the C0 power check stay above 1.3 × 10³ (`PLANTS.md` §8). The rehearsal holds a world with amounts as large against its s as the registered ones (§8), so that an engine that stored amounts, or formed V from amounts plus fixed charges, is seen there and not in the campaign.

**The closure bound** is on the potentials that a field solver leaves in error, and not on its current residual.
- **A node's charge.** The live model accepts a node whose relative charge residual is at most 2 × 10⁻¹² (its declared `CHARGE_RTOL`). That is a potential error of at most 2 × 10⁻¹² of the potential, so at most 2 × 10⁻¹² V*. Legacy forms a membrane's voltage from its charges directly, with no solve to leave an error.
- **A free offset** (the `near` and `far` regions). A current residual R_k at a component is a potential error, δ = K⁻¹ R, with K the conductances of the routes that the free components share. For one component that is |R_k|/ΣG_k, with ΣG_k the conductances incident to it. `near` and `far` share a face. The row sum of K⁻¹ is at most 2.01 times 1/ΣG_k (arithmetic on the declared values of the JUPITER cluster), and δ is at most 2.01 times that of one component.
  Legacy accepts |R_k| at most 2 × 10⁻¹² of the largest diffusion or drift current of any route (its own rule, with a negligible absolute 10⁻²³ A), and the live default solver at most 0.01 × 2 × 10⁻¹² of the largest net route current. A route's diffusion or drift current is at most its own conductance times a driving force, which is a diffusion potential (R T_K/F) |ln (concentration ratio)| or a voltage, and both are
  below V*. No conductance anywhere exceeds 0.53 of the smallest ΣG_k (arithmetic on the declared values of the JUPITER cluster). So δ ≤ 2.01 × 0.53 × 2 × 10⁻¹² V* = 2.13 × 10⁻¹² V*.
- **The floor variant** (`jupiter`, `base`) also accepts |R_k| ≤ 10³ ε Σ G (|φ_s| + |φ_r|) over the routes incident to k. So δ ≤ 2.01 × 10³ ε × 2 max|φ| = 9.0 × 10⁻¹³ max|φ| ≤ 9.0 × 10⁻¹³ V* (2.01 from the shared face, as above), below the share above.
  **The cap is not a small current residual:** in the JUPITER cluster, at the declared initial values, it is 15 to 29 times 2 × 10⁻¹² of the largest current (1,550 to 2,930 times the default solver's target, and D147 measured 8 to 2,200 on another tissue). The route currents there nearly cancel, so the same cap is a potential error of 1.1 × 10⁻¹⁶ V. A bound on the current residual would not hold for the floor variant, and this one does.
- **What it does to a flux.** A potential error δ moves a flux by at most |z| F δ/(R T_K) of its gross one-way rate, which is a share δ/V* × (χ − 1)/χ of the scale s, since s holds χ. (χ − 1)/χ is 0.82 for a monovalent ion and 0.90 for a divalent one. So at δ ≤ 2.13 × 10⁻¹² V* it is at most 1.8 to 1.9 × 10⁻¹² s, inside 2 × 10⁻¹² s. **e_close = 4 × 10⁻¹² s** is two codes at that share.
- **`phi_out` is a potential, and has its own closure.** Its error is δ itself, and not a share of s = R T_K/F. Both codes may be at the limit of what they admit, each with δ ≤ 2.13 × 10⁻¹² V*, so **e_close(`phi_out`) = 4.3 × 10⁻¹² V* = 5.16 × 10⁻¹³ V** (`inputs.json` `closure_terms_V`), two codes at that limit rounded up. The criterion does not depend on one code alone being below half of it. The other potentials need none: `voltage` has a node's charge residual of 2 × 10⁻¹² V* from one code alone, inside its e_close of 4 × 10⁻¹² s(`voltage`).

## 7. The references

**The legacy captures,** `/mnt/workspaces/Cells/legacy-captures-20261125/`, read-only. `legacy_part1.json` pins them: the sha256 of
the science set's `MANIFEST.json`, the origin's manifest and the snapshot's. Every file the judge reads is in that manifest with its sha256.
- **`jupiter`:** `runs/jupiter_baseline-{h,h2,h4}` and `runs/jupiter_pump_release-{h,h2,h4}`: `history.*` at the compared rows, `observations.*` for the
  potentials. h is 100 µs, h/2 50 µs, h/4 25 µs.
- **`cell`:** `runs/cell-{h,h2,h4}-s{0..3}/checkpoint/state.npz` and `result.json` (`final_voltage_V`).
- **`base`:** `runs/cluster_base-{h,h2,h4}-s{0..3}/checkpoint/state.npz`, and `observations/tick-*.json` at the ticks of 5, 10 and 20 ms. h is 50 µs.
- **The pools:** the same checkpoints, and `reference_paths.json`.

**The legacy side's own classes** are in `legacy_part1.json`, by the rule of `CRITERIA.md` §4.3 with `inputs.json`'s scales. Every one of the
entries of `jupiter`, `cell`, `base` and `integrated` is **unresolved**: both of its step-halving differences are below the threshold. The largest observed differences are
about one part in 10¹² of the gross scale. So the reference side has no order to judge. Its error estimate U_l still enters the band.

**`integrated`:** `extra-49529e71/runs/finite_junction_cluster-{h,h2,h4}` (`legacy_part1.json` `integrated_capture` pins its manifest and its origin's), at h, h/2 and h/4 of 100 µs. It was captured at the pre-cleanup revision, where legacy's source equals the
snapshot's byte for byte (the lead's and the plan's statement, and the author's `git diff`). Its definition is the configuration, unchanged.

**The captures' machine** is `legacy_part1.json`'s `cpu_model`. Class E holds on that machine.

**An independent reference** exists for the JUPITER cluster and, with a prescribed availability, for `base`: a scalar ODE of the same equations, with its own code and no engine import (`validation/betse/spatial_cluster/reference.py`). It corroborates the captures before any run: its agreement with the captured h/4 rows within 3 × 10⁻⁹ relative and 3 × 10⁻¹² absolute, entry by entry, is its own registered criterion, and a disagreement is a C0 fault of the references.
The author ran it on both JUPITER arms on 25 November: every state field agrees at every compared time, with the worst entry at 3.7 × 10⁻⁵ of that criterion. It does not cover `cell` or `integrated` as they stand, nor the pools. It decides nothing on the candidate's side.

## 8. The rehearsal set

`inputs_rehearsal.json` has `inputs.json`'s schema (with `p`, `stores`, `closure_terms_V` and `scales` in every world), with its own worlds and runs, named `inv_<name>`, and none of this folder's volumes, amounts, permeabilities,
rates, seeds or times. No step and no horizon of this folder is used, with one exception: a family that sits **exactly at the channel law's stated step bound** (h₁ = 25 µs), which a strict comparison in the engine would refuse. It holds, at least:
- a two-cell cluster with a pump schedule **and free field offsets** (class S, R, D, the potentials; it is the one that exercises the floor variant of the solver and the closure of `phi_out`), with h₁ at that bound;
- a one-cell assembly world and a two-pool assembly world (class E on the pool, the path, the schedule and a restart), and a small cluster of gated junctions with a schedule;
- **one world whose amounts are as large against s as the registered ones,** so that an engine that stores amounts, or forms V from amounts plus fixed charges, is found here: `stores`/`scales` at least 4.3 × 10⁴ for `n_cell_x`, 6.3 × 10⁴ for `n_out_x`, 2.5 × 10⁴ for `voltage` and 4.7 × 10⁴ for `energy_identity` (the largest of `inputs.json`), with a **fixed charge off the electroneutral rule** in the captured style: the decimal of the declared fixed charge is the rounded one, so that the rule and it disagree (up to 5.1 × 10⁻²⁴ C in the captures). Its honest run must pass every entry that reads an amount;
- one family on the engine's IMEX integrator, with **`p` = 2 in its world's block**, at steps where its order is resolved. No RK4 family can be resolved at an admissible step, and the resolved branch of class S must be exercised. **Its identities are reported and not judged:** an honest order-2 run need not close `energy_identity` at the class of an order-4 run;
- one restart, one refusal of each kind (`TABLE.md` §4), one run stopped by the engine's own check, one run whose declared change is off the grid (the reason `off_grid_change`), and one whose schedule writes out a default that the other party omits;
- one run of each consumer's kind whose `steps`, `t` and restart follow §4.

**Files, makers and readers.** All of them are in `validation/ensemble_reexpression/rehearsal/`.

| File | Holds | Maker | Reader |
| --- | --- | --- | --- |
| `inputs_rehearsal.json` | The invented worlds, the runs, `scales`, `stores`, `closure_terms_V`, `p`, the steps of every family | Rehearsal runner | Builders' exporter and judge |
| `runs/` | The frozen snapshot's runs on those definitions, at h, h/2 and h/4 (the captured steps), as `window-*.npz`, `checkpoint/state.npz`, `observations/tick-*.json` | Rehearsal runner | Judge |
| `legacy_rehearsal.json` | The legacy classes, the captured steps and step counts, and the manifests' sha256, as `legacy_part1.json` | Rehearsal runner | Judge |
| `reference_paths_rehearsal.json` | The event paths of the invented pools, as `reference_paths.json` | Rehearsal runner | Judge |
| `margins_rehearsal.json`, `plants_manifest_rehearsal.json` | The invented power and structural plants' distances, ratios, margins and provenance | Rehearsal runner | Judge |
| `registered_strings_rehearsal.json` | The strings note of the rehearsal, with `rehearsal_revision` | Lead | Judge, and the exporter's check |
| `table-rehearsal/table_<consumer>.json`, `SHA256SUMS` | The builders' honest tables of those runs | Builders | Judge |
| `judge_plants/` | The **honest tables that the judge's plants need** (the split of a heat among leak, pump and channel among them): **invented by the judge, recorded as fabricated,** from no engine run and no capture | Judge | Judge |

The reference side of the rehearsal is the frozen legacy snapshot, run on those definitions by the rehearsal's runner.
