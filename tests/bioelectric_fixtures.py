"""Test-only schema adapter; physical oracle remains independent of Cells."""

import json
from pathlib import Path

import numpy as np

from cells.core.specs import parse_spec
from tests.reference_bioelectric import Case, Control, Parameters

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {"amount_fmol": 1e-7, "leak_fmol": 1e-7, "pump_cycles_fmol": 1e-7, "voltage_V": 1e-6}


def definition(case, *, dt=0.005, jit=True, capacity=1, membrane_capacity=1, samples=None):
    data = json.loads((ROOT / "configs/bioelectric_baseline.json").read_text())
    p = case.parameters
    data["model"]["initial_state"] = {
        "amount_fmol": p.initial_amount.tolist(),
        "volume_pL": p.volume_pL,
        "voltage_V": p.initial_voltage_V,
    }
    data["model"]["parameters"]["membrane"].update(
        area_m2=p.area_m2,
        specific_capacitance_F_per_m2=p.specific_capacitance_F_per_m2,
        permeability_m_per_s=list(p.permeability_m_per_s),
        pump_capacity_fmol_per_s=p.pump_capacity_fmol_per_s,
    )
    data["model"]["parameters"]["bath"].update(
        concentration_mM=list(p.bath_mM),
        temperature_K=p.temperature_K,
        atp_free_energy_J_per_mol=p.atp_free_energy_J_per_mol,
    )
    e = data["experiment"]
    e.update(
        end_time=case.horizon,
        observation_times=[0, case.horizon] if samples is None else list(samples),
    )
    # Separate declarations preserve every explicit boundary, even if one group
    # happens to retain its value there. No production scheduler in the oracle.
    e["membrane_controls"]["leak"]["schedule"] = [
        {"time": c.time, "multipliers": list(c.leak)} for c in case.controls
    ]
    e["membrane_controls"]["pump"]["schedule"] = [
        {"time": c.time, "multiplier": c.pump} for c in case.controls
    ]
    data["execution"].update(dt=dt, jit=jit, capacity=capacity, membrane_capacity=membrane_capacity)
    return data


def spec_for(case, **kwargs):
    return parse_spec(definition(case, **kwargs))


def case_for(spec, name="configured"):
    """Interpret serialized controls independently; do not use engine union code."""
    m, e = spec.model, spec.experiment
    params = Parameters(
        volume_pL=m.volume_pL,
        area_m2=m.membrane.area_m2,
        specific_capacitance_F_per_m2=m.membrane.specific_capacitance_F_per_m2,
        temperature_K=m.bath.temperature_K,
        initial_mM=tuple(np.asarray(m.initial_amount) / m.volume_pL),
        bath_mM=m.bath.concentration_mM,
        permeability_m_per_s=m.membrane.permeability_m_per_s,
        initial_voltage_V=m.initial_voltage_V,
        pump_capacity_fmol_per_s=m.membrane.pump_capacity_fmol_per_s,
        atp_free_energy_J_per_mol=m.bath.atp_free_energy_J_per_mol,
    )
    changes = []
    for time in sorted({p.time for p in (*e.leak, *e.pump)}):
        leak = [p for p in e.leak if p.time <= time][-1].multipliers
        pump = [p for p in e.pump if p.time <= time][-1].multiplier
        changes.append(Control(time, leak, pump))
    return Case(name, params, e.end_time, tuple(changes))


def physical_values(state):
    return np.concatenate(
        (state.amount[..., :, 0], state.leak_transferred[..., :, 0], state.pump_cycles[..., :1]),
        axis=-1,
    )


def errors(parameters, actual, expected):
    delta = np.abs(actual - expected[..., :7])
    return {
        "amount_fmol": float(np.max(delta[..., :3], initial=0)),
        "leak_fmol": float(np.max(delta[..., 3:6], initial=0)),
        "pump_cycles_fmol": float(np.max(delta[..., 6], initial=0)),
        "voltage_V": float(
            np.max(
                np.abs(parameters.voltage(actual[..., :3]) - parameters.voltage(expected[..., :3])),
                initial=0,
            )
        ),
    }


def assert_targets(values):
    for name, value in values.items():
        assert np.isfinite(value) and value <= TARGETS[name], (name, value, TARGETS[name])
