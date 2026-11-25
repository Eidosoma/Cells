# Part 2: the literal blocks

These are `inputs_part2.json`'s blocks, in its own form, printed by the author's program. They are the captured definitions' canonical form, as Part 1's are (`SPEC.md` §2.5): the field names of the snapshot's own parser, with a label in place of every registered ID, the derived declarations of `PART2.md` §2.2 written out, every schedule written, and entities as maps by their ID. `PART2.md` §2 says what each key is, §2.3 what the captured form holds and these do not, and §2.4 how they are compared.

**The author compared them leaf by leaf with the captured definitions' parsed form** (the snapshot's parser, parse only, no run): 1,130 leaves of the four ionic children, all equal (252, 270, 282 and 326). The nested ionic model of each assembly-regulated cluster parses to its child's, leaf for leaf.

**What an ionic run's `inputs` holds** (`TABLE.md` §3), by world:

| World | Keys of `inputs` |
| --- | --- |
| `spatial_calcium` | `ionic` (§1), `stores` (§2), `calcium_controls` (§7) |
| `plasma_calcium` | those, and `plasma_transport` (§4) |
| `gated_calcium` | those, and `calcium_channels` (§5) |
| `ip3_calcium` | those, with `stores` of §3, and `ip3_release` (§6) |
| `cluster_<child>` | its child's, with `ionic.controls.channel` the schedule the run declared (class E), and `assembly` (`TABLE.md` §3) |

A pool run's `inputs` are §8.

## 1. `ionic`, of all eight worlds

```json
{
 "temperature_K": 298.15,
 "species": {"Na": 1, "K": 1, "Cl": -1, "Ca": 2},
 "cells": {
  "cell_0": {"volume_pL": 0.5, "initial_amount_fmol": {"Cl": 4.0, "K": 70.0, "Na": 6.0, "Ca": 0.001}, "fixed_charge_equivalent_fmol": -72.00386556853812, "initial_voltage_V": -0.06, "initial_charge_C": -1.8e-13},
  "cell_1": {"volume_pL": 0.7, "initial_amount_fmol": {"Cl": 7.0, "K": 91.0, "Na": 10.5, "Ca": 0.0014}, "fixed_charge_equivalent_fmol": -94.50429245483049, "initial_voltage_V": -0.04, "initial_charge_C": -1.44e-13}
 },
 "outside": {
  "local": {"volume_pL": 2.0, "initial_amount_fmol": {"Cl": 220.0, "K": 8.0, "Na": 280.0, "Ca": 0.016}, "fixed_charge_equivalent_fmol": -68.02864197663136, "initial_charge_C": 3.24e-13},
  "near": {"volume_pL": 1.0, "initial_amount_fmol": {"Cl": 105.0, "K": 8.0, "Na": 120.0, "Ca": 0.01}, "fixed_charge_equivalent_fmol": -23.02, "initial_charge_C": 0.0},
  "far": {"volume_pL": 3.0, "initial_amount_fmol": {"Cl": 345.0, "K": 9.0, "Na": 450.0, "Ca": 0.018000000000000002}, "fixed_charge_equivalent_fmol": -114.036, "initial_charge_C": 0.0}
 },
 "closure": {"gauge_reference": "local"},
 "membranes": {
  "membrane_0": {"inside": "cell_0", "outside": "local", "area_m2": 3e-10, "capacitance_F": 3e-12, "passive": {"law": "constant_field", "permeability_m_per_s": {"Cl": 8e-11, "K": 2e-10, "Na": 1e-11, "Ca": 5e-08}}, "pump": {"law": "nak_pump_positive", "roles": {"sodium": "Na", "potassium": "K"}, "stoichiometry": {"Na": -3, "K": 2}, "capacity_fmol_per_s": 0.05, "km_na_mM": 12.0, "km_k_mM": 0.2, "km_atp_mM": 0.5, "metabolism": {"kind": "maintained_fuel", "atp_mM": 1.5, "adp_mM": 0.1, "pi_mM": 0.1, "delta_g0_J_per_mol": -37000.0}}},
  "membrane_1": {"inside": "cell_1", "outside": "local", "area_m2": 3.6e-10, "capacitance_F": 3.6e-12, "passive": {"law": "constant_field", "permeability_m_per_s": {"Cl": 8e-11, "K": 2e-10, "Na": 1e-11, "Ca": 5e-08}}, "pump": {"law": "nak_pump_positive", "roles": {"sodium": "Na", "potassium": "K"}, "stoichiometry": {"Na": -3, "K": 2}, "capacity_fmol_per_s": 0.1, "km_na_mM": 12.0, "km_k_mM": 0.2, "km_atp_mM": 0.5, "metabolism": {"kind": "maintained_fuel", "atp_mM": 1.5, "adp_mM": 0.1, "pi_mM": 0.1, "delta_g0_J_per_mol": -37000.0}}}
 },
 "channels": {
  "channel_0": {"membrane_id": "membrane_0", "species_id": "K", "kinetic_law": "kv15_mh", "max_permeability_m_per_s": 3e-10, "abundance": 0.5, "initial_gate": {"m": 0.2, "h": 0.7}},
  "channel_1": {"membrane_id": "membrane_1", "species_id": "K", "kinetic_law": "kv15_mh", "max_permeability_m_per_s": 3e-10, "abundance": 0.6, "initial_gate": {"m": 0.2, "h": 0.7}}
 },
 "junctions": {
  "junction": {"from_cell": "cell_0", "to_cell": "cell_1", "area_m2": 1e-10, "permeability_m_per_s": {"Cl": 4e-10, "K": 5e-10, "Na": 3e-10, "Ca": 2e-08}, "gate": {"initial_gate": 0.6, "law": "junction_relaxation", "minimum_open_fraction": 0.1, "threshold_voltage_V": 0.015}}
 },
 "faces": {
  "face_0": {"sender": "local", "receiver": "near", "area_m2": 1e-11, "length_m": 2e-05, "diffusivity_m2_per_s": {"Cl": 2e-09, "K": 1.7e-09, "Na": 1.2e-09, "Ca": 7e-10}, "law": "logmean_face"},
  "face_1": {"sender": "near", "receiver": "far", "area_m2": 1e-11, "length_m": 2e-05, "diffusivity_m2_per_s": {"Cl": 2e-09, "K": 1.7e-09, "Na": 1.2e-09, "Ca": 7e-10}, "law": "logmean_face"},
  "face_2": {"sender": "far", "receiver": "local", "area_m2": 1e-11, "length_m": 2e-05, "diffusivity_m2_per_s": {"Cl": 2e-09, "K": 1.7e-09, "Na": 1.2e-09, "Ca": 7e-10}, "law": "logmean_face"}
 },
 "controls": {
  "leak": {"membrane_0": [[0.0, 1.0]], "membrane_1": [[0.0, 1.0]]},
  "pump": {"membrane_0": [[0.0, 1.0]], "membrane_1": [[0.0, 1.0]]},
  "channel": {"channel_0": [[0.0, 1.0]], "channel_1": [[0.0, 1.0]]},
  "junction": {"junction": [[0.0, 1.0]]}
 },
 "material_tolerance_fmol": {"Cl": 2e-11, "K": 2e-11, "Na": 2e-11, "Ca": 1e-10},
 "end_s": 0.02
}
```

## 2. `stores`, of `spatial_calcium`, `plasma_calcium` and `gated_calcium`

```json
{
 "cell_0": {
  "law": "mass_action_passive",
  "temperature_K": 298.15,
  "standard_concentration_mM": 1.0,
  "species": {
   "Ca": {"valence": 2, "standard_mu_RT": 0.0},
   "B": {"valence": -2, "standard_mu_RT": 0.0},
   "CaB": {"valence": 0, "standard_mu_RT": -6.907755278982137},
   "Ca2B": {"valence": 2, "standard_mu_RT": -11.512925464970229},
   "K": {"valence": 1, "standard_mu_RT": 0.0},
   "Na": {"valence": 1, "standard_mu_RT": 0.0},
   "Cl": {"valence": -1, "standard_mu_RT": 0.0}
  },
  "compartments": {
   "cytosol": {
    "volume_pL": 0.5,
    "initial_amount_fmol": {"Ca": 0.001, "B": 0.025, "CaB": 0.005, "Ca2B": 0.0005, "K": 70.0, "Na": 6.0, "Cl": 4.0}
   },
   "er": {
    "volume_pL": 0.05,
    "initial_amount_fmol": {"Ca": 0.01, "B": 0.0025, "CaB": 0.0005, "Ca2B": 5e-05, "K": 7.0, "Na": 0.6000000000000001, "Cl": 0.4}
   }
  },
  "reactions": {
   "bind_0_first": {
    "compartment": "cytosol",
    "reactants": {"Ca": 1, "B": 1},
    "products": {"CaB": 1},
    "forward_rate_per_s": 1000.0
   },
   "bind_0_second": {
    "compartment": "cytosol",
    "reactants": {"Ca": 1, "CaB": 1},
    "products": {"Ca2B": 1},
    "forward_rate_per_s": 100.0
   },
   "bind_1_first": {
    "compartment": "er",
    "reactants": {"Ca": 1, "B": 1},
    "products": {"CaB": 1},
    "forward_rate_per_s": 1000.0
   },
   "bind_1_second": {
    "compartment": "er",
    "reactants": {"Ca": 1, "CaB": 1},
    "products": {"Ca2B": 1},
    "forward_rate_per_s": 100.0
   }
  },
  "membrane": {
   "cytosol": "cytosol",
   "er": "er",
   "area_m2": 1e-09,
   "capacitance_F": 1.0000000000000001e-11,
   "initial_voltage_V": 0.0,
   "initial_charge_C": 0.0,
   "permeability_m_per_s": {"Ca": 1e-08, "B": 0.0, "CaB": 0.0, "Ca2B": 0.0, "K": 1e-07, "Na": 0.0, "Cl": 0.0},
   "pump": {"law": "calcium_pump_positive", "capacity_fmol_per_s": 0.003, "km_ca_mM": 0.001, "km_atp_mM": 0.5, "atp_mM": 1.5, "adp_mM": 0.1, "pi_mM": 0.1, "delta_g0_at_1M_J_per_mol": -19875.971492394227},
   "release": {"law": "hill_product_factor", "permeability_m_per_s": 1e-07, "activation_mM": 0.001, "activation_n": 2, "inhibition_mM": 0.02, "inhibition_n": 2}
  }
 },
 "cell_1": {
  "law": "mass_action_passive",
  "temperature_K": 298.15,
  "standard_concentration_mM": 1.0,
  "species": {
   "Ca": {"valence": 2, "standard_mu_RT": 0.0},
   "B": {"valence": -2, "standard_mu_RT": 0.0},
   "CaB": {"valence": 0, "standard_mu_RT": -6.907755278982137},
   "Ca2B": {"valence": 2, "standard_mu_RT": -11.512925464970229},
   "K": {"valence": 1, "standard_mu_RT": 0.0},
   "Na": {"valence": 1, "standard_mu_RT": 0.0},
   "Cl": {"valence": -1, "standard_mu_RT": 0.0}
  },
  "compartments": {
   "cytosol": {
    "volume_pL": 0.7,
    "initial_amount_fmol": {"Ca": 0.0014, "B": 0.034999999999999996, "CaB": 0.006999999999999999, "Ca2B": 0.0007, "K": 91.0, "Na": 10.5, "Cl": 7.0}
   },
   "er": {
    "volume_pL": 0.06999999999999999,
    "initial_amount_fmol": {"Ca": 0.013999999999999999, "B": 0.0034999999999999996, "CaB": 0.0007, "Ca2B": 7e-05, "K": 9.1, "Na": 1.05, "Cl": 0.7}
   }
  },
  "reactions": {
   "bind_0_first": {
    "compartment": "cytosol",
    "reactants": {"Ca": 1, "B": 1},
    "products": {"CaB": 1},
    "forward_rate_per_s": 1000.0
   },
   "bind_0_second": {
    "compartment": "cytosol",
    "reactants": {"Ca": 1, "CaB": 1},
    "products": {"Ca2B": 1},
    "forward_rate_per_s": 100.0
   },
   "bind_1_first": {
    "compartment": "er",
    "reactants": {"Ca": 1, "B": 1},
    "products": {"CaB": 1},
    "forward_rate_per_s": 1000.0
   },
   "bind_1_second": {
    "compartment": "er",
    "reactants": {"Ca": 1, "CaB": 1},
    "products": {"Ca2B": 1},
    "forward_rate_per_s": 100.0
   }
  },
  "membrane": {
   "cytosol": "cytosol",
   "er": "er",
   "area_m2": 1.4e-09,
   "capacitance_F": 1.4e-11,
   "initial_voltage_V": 0.0,
   "initial_charge_C": 0.0,
   "permeability_m_per_s": {"Ca": 1e-08, "B": 0.0, "CaB": 0.0, "Ca2B": 0.0, "K": 1e-07, "Na": 0.0, "Cl": 0.0},
   "pump": {"law": "calcium_pump_positive", "capacity_fmol_per_s": 0.0042, "km_ca_mM": 0.001, "km_atp_mM": 0.5, "atp_mM": 1.5, "adp_mM": 0.1, "pi_mM": 0.1, "delta_g0_at_1M_J_per_mol": -19875.971492394227},
   "release": {"law": "hill_product_factor", "permeability_m_per_s": 1e-07, "activation_mM": 0.001, "activation_n": 2, "inhibition_mM": 0.02, "inhibition_n": 2}
  }
 }
}
```

## 3. `stores`, of `ip3_calcium`

```json
{
 "cell_0": {
  "law": "mass_action_passive",
  "temperature_K": 298.15,
  "standard_concentration_mM": 1.0,
  "species": {
   "Ca": {"valence": 2, "standard_mu_RT": 0.0},
   "B": {"valence": -2, "standard_mu_RT": 0.0},
   "CaB": {"valence": 0, "standard_mu_RT": -6.907755278982137},
   "Ca2B": {"valence": 2, "standard_mu_RT": -11.512925464970229},
   "K": {"valence": 1, "standard_mu_RT": 0.0},
   "Na": {"valence": 1, "standard_mu_RT": 0.0},
   "Cl": {"valence": -1, "standard_mu_RT": 0.0},
   "IP3": {"valence": -3, "standard_mu_RT": 0.0},
   "IP3_buffer": {"valence": 0, "standard_mu_RT": 0.0},
   "IP3_bound": {"valence": -3, "standard_mu_RT": -9.210340371976184}
  },
  "compartments": {
   "cytosol": {
    "volume_pL": 0.5,
    "initial_amount_fmol": {"Ca": 0.001, "B": 0.025, "CaB": 0.005, "Ca2B": 0.0005, "K": 70.0, "Na": 6.0, "Cl": 4.0, "IP3": 5e-05, "IP3_buffer": 0.0005, "IP3_bound": 0.0001}
   },
   "er": {
    "volume_pL": 0.05,
    "initial_amount_fmol": {"Ca": 0.01, "B": 0.0025, "CaB": 0.0005, "Ca2B": 5e-05, "K": 7.0, "Na": 0.6000000000000001, "Cl": 0.4, "IP3": 2.0000000000000003e-06, "IP3_buffer": 5e-05, "IP3_bound": 1e-05}
   }
  },
  "reactions": {
   "bind_0_first": {
    "compartment": "cytosol",
    "reactants": {"Ca": 1, "B": 1},
    "products": {"CaB": 1},
    "forward_rate_per_s": 1000.0
   },
   "bind_0_second": {
    "compartment": "cytosol",
    "reactants": {"Ca": 1, "CaB": 1},
    "products": {"Ca2B": 1},
    "forward_rate_per_s": 100.0
   },
   "bind_1_first": {
    "compartment": "er",
    "reactants": {"Ca": 1, "B": 1},
    "products": {"CaB": 1},
    "forward_rate_per_s": 1000.0
   },
   "bind_1_second": {
    "compartment": "er",
    "reactants": {"Ca": 1, "CaB": 1},
    "products": {"Ca2B": 1},
    "forward_rate_per_s": 100.0
   },
   "ip3_binding": {
    "compartment": "cytosol",
    "reactants": {"IP3": 1, "IP3_buffer": 1},
    "products": {"IP3_bound": 1},
    "forward_rate_per_s": 20000.0
   }
  },
  "membrane": {
   "cytosol": "cytosol",
   "er": "er",
   "area_m2": 1e-09,
   "capacitance_F": 1.0000000000000001e-11,
   "initial_voltage_V": 0.0,
   "initial_charge_C": 0.0,
   "permeability_m_per_s": {"Ca": 1e-08, "B": 0.0, "CaB": 0.0, "Ca2B": 0.0, "K": 1e-07, "Na": 0.0, "Cl": 0.0, "IP3": 0.0, "IP3_buffer": 0.0, "IP3_bound": 0.0},
   "pump": {"law": "calcium_pump_positive", "capacity_fmol_per_s": 0.003, "km_ca_mM": 0.001, "km_atp_mM": 0.5, "atp_mM": 1.5, "adp_mM": 0.1, "pi_mM": 0.1, "delta_g0_at_1M_J_per_mol": -19875.971492394227},
   "release": {"law": "hill_product_factor", "permeability_m_per_s": 1e-07, "activation_mM": 0.001, "activation_n": 2, "inhibition_mM": 0.02, "inhibition_n": 2}
  }
 },
 "cell_1": {
  "law": "mass_action_passive",
  "temperature_K": 298.15,
  "standard_concentration_mM": 1.0,
  "species": {
   "Ca": {"valence": 2, "standard_mu_RT": 0.0},
   "B": {"valence": -2, "standard_mu_RT": 0.0},
   "CaB": {"valence": 0, "standard_mu_RT": -6.907755278982137},
   "Ca2B": {"valence": 2, "standard_mu_RT": -11.512925464970229},
   "K": {"valence": 1, "standard_mu_RT": 0.0},
   "Na": {"valence": 1, "standard_mu_RT": 0.0},
   "Cl": {"valence": -1, "standard_mu_RT": 0.0},
   "IP3": {"valence": -3, "standard_mu_RT": 0.0},
   "IP3_buffer": {"valence": 0, "standard_mu_RT": 0.0},
   "IP3_bound": {"valence": -3, "standard_mu_RT": -9.210340371976184}
  },
  "compartments": {
   "cytosol": {
    "volume_pL": 0.7,
    "initial_amount_fmol": {"Ca": 0.0014, "B": 0.034999999999999996, "CaB": 0.006999999999999999, "Ca2B": 0.0007, "K": 91.0, "Na": 10.5, "Cl": 7.0, "IP3": 9.1e-05, "IP3_buffer": 0.0007, "IP3_bound": 0.00014}
   },
   "er": {
    "volume_pL": 0.06999999999999999,
    "initial_amount_fmol": {"Ca": 0.013999999999999999, "B": 0.0034999999999999996, "CaB": 0.0007, "Ca2B": 7e-05, "K": 9.1, "Na": 1.05, "Cl": 0.7, "IP3": 2.8e-06, "IP3_buffer": 7e-05, "IP3_bound": 1.4e-05}
   }
  },
  "reactions": {
   "bind_0_first": {
    "compartment": "cytosol",
    "reactants": {"Ca": 1, "B": 1},
    "products": {"CaB": 1},
    "forward_rate_per_s": 1000.0
   },
   "bind_0_second": {
    "compartment": "cytosol",
    "reactants": {"Ca": 1, "CaB": 1},
    "products": {"Ca2B": 1},
    "forward_rate_per_s": 100.0
   },
   "bind_1_first": {
    "compartment": "er",
    "reactants": {"Ca": 1, "B": 1},
    "products": {"CaB": 1},
    "forward_rate_per_s": 1000.0
   },
   "bind_1_second": {
    "compartment": "er",
    "reactants": {"Ca": 1, "CaB": 1},
    "products": {"Ca2B": 1},
    "forward_rate_per_s": 100.0
   },
   "ip3_binding": {
    "compartment": "cytosol",
    "reactants": {"IP3": 1, "IP3_buffer": 1},
    "products": {"IP3_bound": 1},
    "forward_rate_per_s": 20000.0
   }
  },
  "membrane": {
   "cytosol": "cytosol",
   "er": "er",
   "area_m2": 1.4e-09,
   "capacitance_F": 1.4e-11,
   "initial_voltage_V": 0.0,
   "initial_charge_C": 0.0,
   "permeability_m_per_s": {"Ca": 1e-08, "B": 0.0, "CaB": 0.0, "Ca2B": 0.0, "K": 1e-07, "Na": 0.0, "Cl": 0.0, "IP3": 0.0, "IP3_buffer": 0.0, "IP3_bound": 0.0},
   "pump": {"law": "calcium_pump_positive", "capacity_fmol_per_s": 0.0042, "km_ca_mM": 0.001, "km_atp_mM": 0.5, "atp_mM": 1.5, "adp_mM": 0.1, "pi_mM": 0.1, "delta_g0_at_1M_J_per_mol": -19875.971492394227},
   "release": {"law": "hill_product_factor", "permeability_m_per_s": 1e-07, "activation_mM": 0.001, "activation_n": 2, "inhibition_mM": 0.02, "inhibition_n": 2}
  }
 }
}
```

## 4. `plasma_transport`, of `plasma_calcium`, `gated_calcium` and `ip3_calcium`

```json
{
 "membrane_0": {
  "pump": {"law": "calcium_pump_positive", "capacity_fmol_per_s": 0.002, "km_ca_mM": 0.001, "km_atp_mM": 0.5, "atp_mM": 1.5, "adp_mM": 0.1, "pi_mM": 0.1, "delta_g0_at_1M_J_per_mol": -19875.971492394227},
  "exchanger": {"law": "exchanger_3na_1ca", "capacity_fmol_per_s": 0.002, "km_na_mM": 20.0, "km_ca_mM": 0.001}
 },
 "membrane_1": {
  "pump": {"law": "calcium_pump_positive", "capacity_fmol_per_s": 0.0028, "km_ca_mM": 0.001, "km_atp_mM": 0.5, "atp_mM": 1.5, "adp_mM": 0.1, "pi_mM": 0.1, "delta_g0_at_1M_J_per_mol": -19875.971492394227},
  "exchanger": {"law": "exchanger_3na_1ca", "capacity_fmol_per_s": 0.0028, "km_na_mM": 20.0, "km_ca_mM": 0.001}
 }
}
```

## 5. `calcium_channels`, of `gated_calcium` and `ip3_calcium`

```json
{
 "calcium_channel_0": {"membrane_id": "membrane_0", "species_id": "Ca", "kinetic_law": "cav12_m2h", "max_permeability_m_per_s": 2e-06, "abundance": 0.5, "initial_gate": {"m": 0.2, "h": 0.7}},
 "calcium_channel_1": {"membrane_id": "membrane_1", "species_id": "Ca", "kinetic_law": "cav12_m2h", "max_permeability_m_per_s": 2e-06, "abundance": 0.6, "initial_gate": {"m": 0.2, "h": 0.7}}
}
```

## 6. `ip3_release`, of `ip3_calcium`

```json
{
 "cell_0": {"species_id": "IP3", "law": "hill_product_factor", "activation_mM": 0.00015, "activation_n": 2},
 "cell_1": {"species_id": "IP3", "law": "hill_product_factor", "activation_mM": 0.00015, "activation_n": 2}
}
```

## 7. `calcium_controls`

Of `ip3_calcium`. `gated_calcium` has no `ip3_binding`, `plasma_calcium` has neither that nor `calcium_channel`, and `spatial_calcium` has none of `calcium_pump`, `exchanger`, `calcium_channel` and `ip3_binding`.

```json
{
 "store_passive": {"cell_0": {"Ca": [[0.0, 1.0]], "K": [[0.0, 1.0]]}, "cell_1": {"Ca": [[0.0, 1.0]], "K": [[0.0, 1.0]]}},
 "store_pump": {"cell_0": [[0.0, 1.0]], "cell_1": [[0.0, 1.0]]},
 "store_release": {"cell_0": [[0.0, 1.0]], "cell_1": [[0.0, 1.0]]},
 "reactions": {"cell_0": {"bind_0_first": [[0.0, 1.0]], "bind_0_second": [[0.0, 1.0]], "bind_1_first": [[0.0, 1.0]], "bind_1_second": [[0.0, 1.0]], "ip3_binding": [[0.0, 1.0]]}, "cell_1": {"bind_0_first": [[0.0, 1.0]], "bind_0_second": [[0.0, 1.0]], "bind_1_first": [[0.0, 1.0]], "bind_1_second": [[0.0, 1.0]], "ip3_binding": [[0.0, 1.0]]}},
 "calcium_pump": {"membrane_0": [[0.0, 1.0]], "membrane_1": [[0.0, 1.0]]},
 "exchanger": {"membrane_0": [[0.0, 1.0]], "membrane_1": [[0.0, 1.0]]},
 "calcium_channel": {"calcium_channel_0": [[0.0, 1.0]], "calcium_channel_1": [[0.0, 1.0]]}
}
```

## 8. A pool run of a cluster (`cluster_<child> s0 pool`)

The four clusters have the same two pools, which are `base`'s with two worlds. Another seed index differs in `seed` alone (`inputs_part2.json` `seeds`).

```json
{
 "cell_0": {
  "channel": "channel_0",
  "stream_id": 0,
  "seed": 20260925,
  "pool": {"model": "pool_model", "topology": "pool_topology", "initial_nodes": [10, 12, 14, 16, 18], "initial_bond_indices": [20, 21, 24, 26, 28], "root_node": 10, "initial_free_trimers": 50, "pool_volume_L": 5e-15, "k_on_M_inv_s": 10000000.0, "k_close_s_inv": 1000.0, "k_off_s_inv": 300.0, "k_fragment_dissolve_s_inv": 1.0, "world_id_start": 0, "worlds": 2, "end_time_s": 0.02, "max_events_per_world": 100000}
 },
 "cell_1": {
  "channel": "channel_1",
  "stream_id": 1,
  "seed": 20260926,
  "pool": {"model": "pool_model", "topology": "pool_topology", "initial_nodes": [10, 12, 14, 16, 18], "initial_bond_indices": [20, 21, 24, 26, 28], "root_node": 10, "initial_free_trimers": 50, "pool_volume_L": 5e-15, "k_on_M_inv_s": 10000000.0, "k_close_s_inv": 1000.0, "k_off_s_inv": 300.0, "k_fragment_dissolve_s_inv": 1.0, "world_id_start": 0, "worlds": 2, "end_time_s": 0.02, "max_events_per_world": 100000}
 }
}
```
