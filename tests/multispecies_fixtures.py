"""Production-schema adapter and comparison coordinates; never an oracle RHS."""

import numpy as np

from cells.core.specs import MULTISPECIES_ID, parse_spec


def definition(case, *, dt=0.01, jit=True, capacity=1, membrane_capacity=1, samples=None):
    p = case.parameters

    def mapped(values):
        return dict(zip(p.species_ids, values, strict=True))

    pump = None
    if p.pump_id is not None:
        pump = {
            "id": p.pump_id,
            "law": "nak_atp_affinity_tanh@1",
            "roles": dict(zip(("sodium", "potassium"), p.pump_roles, strict=True)),
            "stoichiometry": dict(zip(p.pump_roles, (-3, 2), strict=True)),
            "capacity_fmol_per_s": p.capacity_fmol_per_s,
            "drive_J_per_mol": p.drive_J_per_mol,
        }
    return {
        "schema_version": 1,
        "model": {
            "id": MULTISPECIES_ID,
            "species": [
                {"id": s, "valence": z} for s, z in zip(p.species_ids, p.valence, strict=True)
            ],
            "cell": {
                "id": p.cell_id,
                "volume_pL": p.volume_pL,
                "initial_amount_fmol": mapped(p.initial_amount_fmol),
                "fixed_charge_equivalent_fmol": p.fixed_charge_equivalent_fmol,
                "initial_voltage_V": p.initial_voltage_V,
            },
            "bath": {
                "id": p.bath_id,
                "temperature_K": p.temperature_K,
                "concentration_mM": mapped(p.bath_mM),
                "background_charge_mM": p.bath_background_charge_mM,
            },
            "membrane": {
                "id": p.membrane_id,
                "inside": p.cell_id,
                "outside": p.bath_id,
                "area_m2": p.area_m2,
                "specific_capacitance_F_per_m2": p.specific_capacitance_F_per_m2,
                "passive": {
                    "law": "constant_field@1",
                    "permeability_m_per_s": mapped(p.permeability_m_per_s),
                },
                "pump": pump,
            },
        },
        "experiment": {
            "end_time": case.horizon_s,
            "observation_times": [0.0, case.horizon_s] if samples is None else list(samples),
            "membrane_controls": {
                "membrane_id": p.membrane_id,
                "leak": [{"time": c.time_s, "multipliers": mapped(c.leak)} for c in case.controls],
                "pump": [{"time": c.time_s, "multiplier": c.pump} for c in case.controls],
            },
        },
        "execution": {
            "backend": "cpu",
            "precision": "float64",
            "solver": "rk4",
            "dt": dt,
            "capacity": capacity,
            "membrane_capacity": membrane_capacity,
            "jit": jit,
            "max_steps": 100000,
            "max_trace_bytes": 268435456,
            # The frozen NUM-006 panel explicitly declares this species override.
            # Production never selects numerical behavior by a species' label.
            "material_balance_atol_fmol": {s: 1e-12 if s == "Ca" else 1e-10 for s in p.species_ids},
        },
    }


def spec_for(case, **kwargs):
    return parse_spec(definition(case, **kwargs))


def canonical_values(case, state):
    return np.concatenate(
        (
            state.amount[..., :, 0] - case.parameters.initial_amount_fmol,
            state.leak_transferred[..., :, 0],
            state.pump_cycles[..., :1],
            state.dissipated_energy_pJ[..., :1],
        ),
        axis=-1,
    )
