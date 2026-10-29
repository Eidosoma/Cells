"""Independent common-stage factor wiring to the complete 38-field reference.

Only independent reference modules are imported. Each physical owner is resolved
from declared IDs; Decimal source-factor equations and the parent field/energy
equations remain separate equation owners.
"""

from copy import deepcopy
from decimal import localcontext

import numpy as np
from scipy.integrate import solve_ivp

from validation.regulation.betse_network_modulation_reference import alpha, d
from validation.regulation.integrated_network_regulation_v2_fixtures import parent_definition
from validation.tissue import surface_calcium_energy_reference as energy

flatten, unpack, initial = energy.flatten, energy.unpack, energy.initial


def bind(raw):
    c = energy.bind(parent_definition(raw))
    return dict(c, energy=c, rules=deepcopy(raw["model"]["network_regulation"]["rules"]))


def samples(c, state):
    values = unpack(c, state)
    species = [s["id"] for s in c["raw"]["model"]["ionic"]["species"]]
    free = np.stack(
        [
            (s.n0 + values["chemical_amount_increment"][i])[[s.ids.index(k) for k in species], s.cy]
            / s.volume[s.cy]
            for i, s in enumerate(c["stores"])
        ],
        axis=1,
    )
    outside = (c["ao"] + values["extracellular_amount_increment"]) / c["vo"]
    fuel = (c["energy_initial"] + values["energy_amount_increment_fmol"]) / c["energy_volumes"]
    outer_ids = [s["id"] for s in c["raw"]["model"]["ionic"]["extracellular"]]
    rows = []
    for rule in c["rules"]:
        cell = c["cell_ids"].index(rule["sample_cell_id"])
        owner = c["cell_ids"].index(c["pools"][rule["fuel_pool_id"]]["cell_id"])
        if cell != owner:
            raise ValueError("Rule reads another cytosol's fuel")
        ci = [*free[:, cell], *fuel[:, owner]]
        co = (
            [0.0] * len(ci)
            if rule["sample_exterior_id"] is None
            else [*outside[:, outer_ids.index(rule["sample_exterior_id"])], 0.0, 0.0, 0.0]
        )
        rows.append(list(zip(ci, co, strict=True)))
    return np.asarray(rows).reshape(len(rows), len(species) + 3, 2)


def factors(c, state, time):
    sample = samples(c, state)
    ion = c["raw"]["model"]["ionic"]
    ids = {
        "nak": [p["pump"]["id"] if p["pump"] is not None else None for p in ion["membranes"]],
        "channel": [p["id"] for p in ion["channels"]],
        "junction": [p["id"] for p in ion["junctions"]],
    }
    multipliers = {k: np.asarray([float(i is not None) for i in v]) for k, v in ids.items()}
    values = []
    with localcontext() as context:
        context.prec = 80
        for i, rule in enumerate(c["rules"]):
            conf = rule["configuration"]
            raw = dict(
                sample_mM=sample[i].tolist(),
                membrane_to_environment=[0],
                species_ids=[*[s["id"] for s in ion["species"]], "ATP", "ADP", "Pi"],
                species_valence=[*[s["valence"] for s in ion["species"]], 0, 0, 0],
                voltage_V=[0.0],
                faraday_C_mol=96485.0,
                gas_constant_J_mol_K=8.314,
                temperature_K=ion["temperature_K"],
            )
            channel = rule["kind"] == "channel"
            factor = float(
                alpha(conf, raw, 0, channel=channel) * (1 if channel else d(conf["max effect"]))
            )
            if not np.isfinite(factor) or not 0 <= factor <= 1:
                raise ValueError("Native availability factor outside [0,1]")
            values.append(factor)
            multipliers[rule["kind"]][ids[rule["kind"]].index(rule["target_id"])] = factor
    families = {
        "nak": ("pump_controls", "pump_id"),
        "channel": ("channel_controls", "channel_id"),
        "junction": ("junction_controls", "junction_id"),
    }
    controls = {}
    for kind, (family, key) in families.items():
        scheduled = np.zeros(len(ids[kind]))
        for row in c["raw"]["experiment"][family]:
            scheduled[ids[kind].index(row[key])] = next(
                v["availability"] for v in reversed(row["schedule"]) if v["time"] <= time
            )
        controls[kind] = dict(
            factor=multipliers[kind].tolist(),
            scheduled=scheduled.tolist(),
            effective=(scheduled * multipliers[kind]).tolist(),
        )
    return dict(rule_factors=values, samples_mM=sample.tolist(), controls=controls)


def evaluate(c, state, time):
    regulation = factors(c, state, time)
    raw = deepcopy(c["raw"])
    ion = raw["model"]["ionic"]
    for kind, family, key, ids in (
        (
            "nak",
            "pump_controls",
            "pump_id",
            [p["pump"]["id"] if p["pump"] is not None else None for p in ion["membranes"]],
        ),
        ("channel", "channel_controls", "channel_id", [p["id"] for p in ion["channels"]]),
        ("junction", "junction_controls", "junction_id", [p["id"] for p in ion["junctions"]]),
    ):
        for row in raw["experiment"][family]:
            row["schedule"] = [
                dict(
                    time=0.0,
                    availability=regulation["controls"][kind]["effective"][ids.index(row[key])],
                )
            ]
    slope, phi, proof = energy.evaluate(energy.bind(raw), state, time)
    return slope, phi, proof | dict(network_regulation=regulation)


def event_times(raw):
    events = {0.0, raw["experiment"]["end_time"], *raw["experiment"]["observation_times"]}
    for name, groups in raw["experiment"].items():
        if name.endswith("_controls"):
            for group in groups:
                events.update(r["time"] for r in group.get("schedule", group.get("controls", [])))
    return sorted(events)


def integrate(raw, *, rtol=2e-11, max_step_s=0.625e-6):
    c = bind(raw)
    state, knots = initial(c), event_times(raw)
    rows = [state.copy()]
    for left, right in zip(knots[:-1], knots[1:], strict=True):
        result = solve_ivp(
            lambda time, y, held=left: evaluate(c, y, held)[0],
            (left, right),
            state,
            method="DOP853",
            rtol=rtol,
            atol=1e-15,
            max_step=max_step_s,
        )
        if not result.success:
            raise RuntimeError(dict(left=left, right=right, message=result.message))
        state = result.y[:, -1]
        rows.append(state.copy())
    return (
        c,
        np.asarray(knots),
        np.stack(rows),
        dict(status="passed", rtol=rtol, atol=1e-15, max_step_s=max_step_s),
    )
