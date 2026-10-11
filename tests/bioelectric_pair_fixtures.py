"""Test-only schema/column adapter. The frozen oracle never imports production."""

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from cells.core.specs import parse_spec
from tests import reference_bioelectric_pair as reference

ROOT = Path(__file__).resolve().parents[1]


def definition(
    case, *, dt=0.001, jit=True, capacity=2, membrane_capacity=2, edge_capacity=1, samples=None
):
    data = json.loads((ROOT / "configs/bioelectric_pair_baseline.json").read_text())
    p = case.parameters
    m, e, x = (data[k] for k in ("model", "experiment", "execution"))
    m["initial_state"] = {
        "amount_fmol": p.initial_amount.tolist(),
        "volume_pL": [c.volume_pL for c in p.cells],
        "voltage_V": p.initial_voltage.tolist(),
    }
    for c, a in zip(p.cells, m["parameters"]["membranes"], strict=True):
        for key in (
            "area_m2",
            "specific_capacitance_F_per_m2",
            "permeability_m_per_s",
            "pump_capacity_fmol_per_s",
        ):
            value = getattr(c, key)
            a[key] = list(value) if isinstance(value, tuple) else value
    m["parameters"]["bath"].update(
        concentration_mM=list(p.cells[0].bath_mM),
        temperature_K=p.temperature,
        atp_free_energy_J_per_mol=p.cells[0].atp_free_energy_J_per_mol,
    )
    contact = asdict(p.junction)
    a, b = contact.pop("endpoints")
    for key in ("permeability_m_per_s", "residual"):
        contact[key] = list(contact[key])
    contact.update(
        from_cell_id=m["population"]["cell_ids"][a], to_cell_id=m["population"]["cell_ids"][b]
    )
    m["parameters"]["contact"].update(contact)
    e.update(
        end_time=case.horizon,
        observation_times=[0, case.horizon] if samples is None else list(samples),
    )
    # Minimize independent groups: include only their actual changes. This tests
    # the engine's event union, not just a premerged all-groups-at-every-event input.
    for i, group in enumerate(e["membrane_controls"]):
        for key in ("leak", "pump"):
            schedule, previous = [], None
            for c in case.controls:
                value = [row[i] for row in c.leak] if key == "leak" else c.pump[i]
                if value != previous:
                    schedule.append(
                        {"time": c.time, "multipliers" if key == "leak" else "multiplier": value}
                    )
                previous = value
            group[key]["schedule"] = schedule
    e["contact"]["schedule"] = [
        {"time": c.time, "multiplier": c.contact}
        for i, c in enumerate(case.controls)
        if i == 0 or c.contact != case.controls[i - 1].contact
    ]
    x.update(
        dt=dt,
        jit=jit,
        capacity=capacity,
        membrane_capacity=membrane_capacity,
        edge_capacity=edge_capacity,
    )
    return data


def spec_for(case, **kwargs):
    return parse_spec(definition(case, **kwargs))


def case_for(spec, name="configured"):
    """Independent schema interpretation; do not import the production event union."""
    cells = tuple(
        reference.cell.Parameters(
            volume_pL=c.volume_pL,
            area_m2=c.membrane.area_m2,
            specific_capacitance_F_per_m2=c.membrane.specific_capacitance_F_per_m2,
            temperature_K=c.bath.temperature_K,
            initial_mM=tuple(np.asarray(c.initial_amount) / c.volume_pL),
            bath_mM=c.bath.concentration_mM,
            permeability_m_per_s=c.membrane.permeability_m_per_s,
            initial_voltage_V=c.initial_voltage_V,
            pump_capacity_fmol_per_s=c.membrane.pump_capacity_fmol_per_s,
            atp_free_energy_J_per_mol=c.bath.atp_free_energy_J_per_mol,
        )
        for c in spec.model.cells
    )
    ids = [c.cell_id for c in spec.model.cells]
    contact = asdict(spec.model.contact)
    contact.pop("contact_id")
    endpoints = tuple(ids.index(contact.pop(key)) for key in ("from_cell_id", "to_cell_id"))
    p = reference.Parameters(cells, reference.Junction(endpoints=endpoints, **contact))
    e = spec.experiment
    boundaries = {c.time for g in e.membranes for c in (*g.leak, *g.pump)} | {
        c.time for c in e.contact
    }
    changes = []
    for time in sorted(boundaries):
        leak = [[c for c in g.leak if c.time <= time][-1].multipliers for g in e.membranes]
        pump = tuple([c for c in g.pump if c.time <= time][-1].multiplier for g in e.membranes)
        control = [c for c in e.contact if c.time <= time][-1].open_fraction
        changes.append(reference.Control(time, tuple(zip(*leak, strict=True)), pump, control))
    return reference.Case(name, name, p, e.end_time, tuple(changes))


def physical_values(state):
    leading = state.amount.shape[:-2]
    return np.concatenate(
        (
            state.amount[..., :, :2].reshape((*leading, 6)),
            state.leak_transferred[..., :, :2].reshape((*leading, 6)),
            state.pump_cycles[..., :2],
            state.transferred[..., :, 0],
            state.gate[..., :1],
            state.dissipated_energy_pJ,
        ),
        axis=-1,
    )


def assert_targets(p, actual, expected):
    errors = reference.trajectory_errors(p, actual, expected)
    targets = reference.load_panel()[0]["targets"]
    for name, value in errors.items():
        assert np.isfinite(value) and value <= targets[name], (name, value, targets[name])
    return errors
