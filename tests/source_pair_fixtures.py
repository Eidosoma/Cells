"""Test-only named schema/column adapter; frozen numerical oracles remain unchanged."""

import copy

import numpy as np

from cells.core.specs import parse_spec
from tests import reference_source_pair_numerics as ref


def definition(
    case=None, *, dt=0.01, jit=True, capacity=2, membrane_capacity=2, edge_capacity=1, samples=None
):
    panel = ref.eq.load_panel()
    case = panel["cases"][1] if case is None else case
    primary, context = ref.eq.initial_state(panel, case)
    ions, regulation = primary[:3], primary[3:]
    ids, mem_ids, contact_id, bath_id = [101, 102], [201, 202], 301, 401
    diffusion = case.get("membrane_diffusion", panel["membrane_diffusion"])
    times = [0.0] + [entry["time"] for entry in case.get("events", [])]
    controls = [ref.eq.controls_at(panel, case, time) for time in times]
    membranes = []
    for slot, identity in enumerate(mem_ids):
        group = {"membrane_id": identity}
        for key in ("leak", "pump"):
            schedule, previous = [], None
            for time, held in zip(times, controls, strict=True):
                value = held[key][:, slot].tolist() if key == "leak" else float(held[key][slot])
                if value != previous:
                    schedule.append(
                        {"time": time, "multipliers" if key == "leak" else "multiplier": value}
                    )
                previous = value
            group[key] = schedule
        membranes.append(group)
    contacts = []
    for name, key in (("ions", "ion_contact"), ("mirna", "mirna_contact")):
        contacts.append(
            {
                "route": name,
                "contact_id": contact_id,
                "schedule": [
                    {"time": time, "multiplier": float(held[key])}
                    for i, (time, held) in enumerate(zip(times, controls, strict=True))
                    if i == 0 or float(held[key]) != float(controls[i - 1][key])
                ],
            }
        )
    edge = case.get("edge", [0, 1])
    return {
        "schema_version": 1,
        "model": {
            "id": "bitsey_emt_pair@1",
            "ionic_species": ["Na", "K", "Cl"],
            "regulatory_coordinates": ["miR200_total", "Zeb_mRNA_total", "ZEB_prot"],
            "units": {
                "time": "bitsey_time_unit",
                "ionic_concentration": "mol/m3",
                "regulatory_coordinate": "bitsey_scaled_coordinate",
                "voltage": "V",
                "length": "m",
                "diffusion": "m2/bitsey_time_unit",
            },
            "population": {"count": 2, "cell_ids": ids},
            "initial_state": {"ions": ions.tolist(), "regulation": regulation.tolist()},
            "parameters": {
                "parameter_set": "bitsey-b2cb370-emt-pair-simple",
                "context": {
                    name: row.tolist()
                    for name, row in zip(("P", "snail", "ST"), context, strict=True)
                },
                "membranes": [
                    {
                        "membrane_id": mem_ids[i],
                        "owner_cell_id": identity,
                        "bath_id": bath_id,
                        "diffusion": [row[i] for row in diffusion],
                    }
                    for i, identity in enumerate(ids)
                ],
                "bath": {"kind": "clamped", "bath_id": bath_id, "ions": panel["bath_ions"]},
                "contact": {
                    "contact_id": contact_id,
                    "from_cell_id": ids[edge[0]],
                    "to_cell_id": ids[edge[1]],
                    "ion_diffusion": panel["junction_ion_diffusion"],
                    "mirna_diffusion": panel["junction_mirna_diffusion"],
                    "gate_profile": case["gate"],
                    "swap_hemichannels": case.get("swap_hemichannels", False),
                },
            },
        },
        "experiment": {
            "end_time": case["end_time"],
            "source": {"kind": "none"},
            "observation_times": [0.0, case["end_time"]] if samples is None else list(samples),
            "membrane_controls": membranes,
            "contact_controls": contacts,
        },
        "execution": {
            "backend": "cpu",
            "precision": "float64",
            "solver": "rk4",
            "dt": dt,
            "capacity": capacity,
            "jit": jit,
            "max_steps": 200000,
            "max_trace_bytes": 536870912,
            "edge_capacity": edge_capacity,
            "membrane_capacity": membrane_capacity,
        },
    }


def spec_for(case=None, **kwargs):
    return parse_spec(definition(case, **kwargs))


def values(state):
    leading = state.ions.shape[:-2]
    return np.concatenate(
        (
            state.ions[..., :, :2].reshape((*leading, 6)),
            state.regulation[..., :, :2].reshape((*leading, 6)),
            state.leak_history[..., :, :2].reshape((*leading, 6)),
            state.pump_history[..., :2],
            state.ion_transferred[..., :, 0],
            state.local_regulation[..., :, :2].reshape((*leading, 6)),
            state.mirna_transferred[..., :1],
        ),
        axis=-1,
    )


def reference_model(spec):
    """Interpret all data and control groups independently of production resolution."""
    panel = copy.deepcopy(ref.eq.load_panel())
    m, e = spec.model, spec.experiment
    panel["constructed_initials"]["configured"] = {
        "primary": [list(row) for row in (*m.initial_ions, *m.initial_regulation)],
        "context": [list(row) for row in m.context],
    }
    panel["bath_ions"] = list(m.bath_ions)
    panel["junction_ion_diffusion"] = list(m.contact.ion_diffusion)
    panel["junction_mirna_diffusion"] = m.contact.mirna_diffusion
    case = {
        "id": "configured",
        "name": "configured",
        "initial": "configured",
        "gate": m.contact.gate_profile,
        "swap_hemichannels": m.contact.swap_hemichannels,
        "edge": [m.cell_ids.index(m.contact.from_cell_id), m.cell_ids.index(m.contact.to_cell_id)],
        "membrane_diffusion": np.array([a.diffusion for a in m.membranes]).T.tolist(),
        "end_time": e.end_time,
        "events": [],
    }
    times = sorted(
        {p.time for g in e.membranes for p in (*g.leak, *g.pump)}
        | {p.time for group in e.contacts for p in group}
    )
    for time in times:
        controls = {
            "leak": np.array(
                [[p for p in g.leak if p.time <= time][-1].multipliers for g in e.membranes]
            ).T.tolist(),
            "pump": [[p for p in g.pump if p.time <= time][-1].multiplier for g in e.membranes],
            "ion_contact": [p for p in e.contacts[0] if p.time <= time][-1].open_fraction,
            "mirna_contact": [p for p in e.contacts[1] if p.time <= time][-1].open_fraction,
        }
        if time == 0:
            case["controls"] = controls
        else:
            case["events"].append({"time": time, "set": controls})
    return ref.Model(panel, case)
