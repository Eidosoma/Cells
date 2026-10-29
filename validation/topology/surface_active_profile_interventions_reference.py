"""Independent native pulse/owners plus all 56-law active equations and ledgers."""

from copy import deepcopy

import numpy as np
from scipy.integrate import solve_ivp

from validation.tissue import surface_kinetic_reference as active
from validation.topology import membrane_profile_phase_handoff_reference as passive_history
from validation.topology import surface_profile_interventions_reference as membrane


def parent_definition(raw):
    value = membrane.parent_definition(raw)
    value["model"]["id"] = "resolved_tissue@12"
    return value


def bind(raw):
    return dict(raw=deepcopy(raw), parent=active.bind(parent_definition(raw)))


def initial(context):
    return np.r_[active.initial(context["parent"]), 0.0]


def flatten(context, values):
    return np.r_[
        active.flatten(context["parent"], values), np.asarray(values["phase_clock_s"]).ravel()
    ]


def evaluate(context, state, *, held_time=None):
    clock = float(state[-1])
    raw, events = membrane.permeability(context["raw"], clock)
    raw["model"]["id"] = "resolved_tissue@12"
    if held_time is not None:
        for kind in ("membrane", "junction", "channel", "pump"):
            for group in raw["experiment"][kind + "_controls"]:
                a = next(
                    v["availability"] for v in reversed(group["schedule"]) if v["time"] <= held_time
                )
                group["schedule"] = [dict(time=0.0, availability=a)]
    current = active.bind(raw)
    slope, phi, proof = active.evaluate(current, state[:-1], clock)
    return np.r_[slope, 1.0], phi, proof | dict(events=events)


def field_observables(context, state, slope, phi):
    """Independent complete physical rates from owner loops and capacitor solve."""
    c = context["parent"]
    m = c["raw"]["model"]
    values, derivative = (active.unpack(c, v[:-1]) for v in (state, slope))
    species = [v["id"] for v in m["species"]]
    cells = [v["id"] for v in m["cells"]]
    outside = [v["id"] for v in m["extracellular"]]
    mids = [v["id"] for v in m["membranes"]]
    n = len(cells)
    total = np.array(derivative["membrane_transferred"], copy=True)
    heat = np.array(derivative["membrane_dissipated_energy_pJ"], copy=True)
    for k, population in enumerate(m["channels"]):
        j = mids.index(population["membrane_id"])
        total[:, j] += derivative["channel_transferred"][:, k]
        heat[j] += derivative["channel_dissipated_energy_pJ"][:, k].sum()
    for j, patch in enumerate(m["membranes"]):
        pump = patch["pump"]
        if pump is not None:
            cycles = derivative["pump_cycles"][j]
            total[species.index(pump["roles"]["sodium"]), j] += 3 * cycles
            total[species.index(pump["roles"]["potassium"]), j] -= 2 * cycles
        heat[j] += derivative["pump_dissipated_energy_pJ"][j]
    z = np.asarray([v["valence"] for v in m["species"]])[:, None]
    qdot = (
        active.F
        * 1e-15
        * np.sum(
            z * np.c_[derivative["amount_increment"], derivative["extracellular_amount_increment"]],
            axis=0,
        )
    )
    stage = active.base.stage(c, state[:-1], float(state[-1]))
    stage["junction_open"] = np.asarray(stage["junction_open"]) * values["junction_gate"]
    matrix, active_nodes, reservoir, _, floating, _ = active.electrical.topology(stage)
    pins = ~active_nodes | reservoir
    for group in floating:
        pins[group[0]] = True
    free = np.flatnonzero(~pins)
    dphi = np.zeros_like(phi)
    dphi[free] = np.linalg.solve(matrix[np.ix_(free, free)], qdot[free])
    voltage = np.asarray(
        [
            phi[cells.index(p["inside"])] - phi[n + outside.index(p["outside"])]
            for p in m["membranes"]
        ]
    )
    dv = np.asarray(
        [
            dphi[cells.index(p["inside"])] - dphi[n + outside.index(p["outside"])]
            for p in m["membranes"]
        ]
    )
    junction_voltage = np.asarray(
        [phi[cells.index(v["sender"])] - phi[cells.index(v["receiver"])] for v in m["junctions"]]
    )
    chemical = (
        1e-3
        * active.R
        * m["temperature_K"]
        * (
            np.sum(np.log(stage["ci"]) * derivative["amount_increment"])
            + np.sum(np.log(stage["co"]) * derivative["extracellular_amount_increment"])
        )
    )
    capacitor = 1e12 * np.sum(
        np.asarray([p["capacitance_F"] for p in m["membranes"]]) * voltage * dv
    )
    dissipation = (
        heat.sum()
        + derivative["junction_dissipated_energy_pJ"].sum()
        + derivative["face_dissipated_energy_pJ"].sum()
    )
    reservoir_power = derivative["reservoir_work_pJ"].sum()
    electrode_power = derivative["electrode_work_pJ"].sum()
    metabolic = derivative["metabolic_work_pJ"].sum()
    return dict(
        membrane_flux_fmol_s=total,
        membrane_current_A=active.F * 1e-15 * np.sum(z * total, axis=0),
        membrane_voltage_V=voltage,
        membrane_voltage_rate_V_s=dv,
        junction_voltage_V=junction_voltage,
        membrane_dissipation_pJ_s=heat,
        junction_dissipation_pJ_s=derivative["junction_dissipated_energy_pJ"],
        face_dissipation_pJ_s=derivative["face_dissipated_energy_pJ"],
        electrode_current_A=derivative["electrode_charge_transferred_C"],
        channel_flux_fmol_s=derivative["channel_transferred"],
        pump_cycles=derivative["pump_cycles"],
        chemical_energy_rate_pJ_s=chemical,
        capacitor_energy_rate_pJ_s=capacitor,
        dissipation_pJ_s=dissipation,
        reservoir_power_pJ_s=reservoir_power,
        electrode_power_pJ_s=electrode_power,
        metabolic_power_pJ_s=metabolic,
        energy_balance_pJ_s=chemical
        + capacitor
        + dissipation
        - reservoir_power
        - electrode_power
        - metabolic,
    )


def integrate(raw):
    context = bind(raw)
    state = initial(context)
    clocks = sorted(
        {
            0.0,
            raw["experiment"]["end_time"],
            *(
                v["time"]
                for kind in ("membrane", "junction", "channel", "pump")
                for row in raw["experiment"][kind + "_controls"]
                for v in row["schedule"]
            ),
        }
    )
    atol = np.r_[
        active.flatten(
            context["parent"],
            {
                key: np.full(shape, 1e-29 if key.endswith("_C") else 2e-14)
                for key, shape in context["parent"]["shapes"].items()
            },
        ),
        1e-22,
    ]
    evaluations = 0
    for left, right in zip(clocks, clocks[1:], strict=False):
        solution = solve_ivp(
            lambda t, y, held=left: evaluate(context, y, held_time=held)[0],
            (left, right),
            state,
            method="DOP853",
            rtol=2e-11,
            atol=atol,
            max_step=min(0.125e-6, right - left),
        )
        if not solution.success:
            raise RuntimeError(solution.message)
        state = solution.y[:, -1]
        evaluations += solution.nfev
    return state, dict(
        method="DOP853 with all four exact held-control families", rhs_evaluations=evaluations
    )


def conservation(context, state):
    """Untouched complete history; explicit channel/pump owner aggregation."""
    raw = deepcopy(context["raw"])
    m = raw["model"]
    values = active.unpack(context["parent"], state[:-1])
    total = np.array(values["membrane_transferred"], copy=True)
    species = [row["id"] for row in m["species"]]
    membranes = [row["id"] for row in m["membranes"]]
    for k, population in enumerate(m["channels"]):
        j = membranes.index(population["membrane_id"])
        total[:, j] += values["channel_transferred"][:, k]
    for j, patch in enumerate(m["membranes"]):
        pump = patch["pump"]
        if pump is not None:
            total[species.index(pump["roles"]["sodium"]), j] += 3 * values["pump_cycles"][j]
            total[species.index(pump["roles"]["potassium"]), j] -= 2 * values["pump_cycles"][j]
    fields = {
        key: np.array(values[key], copy=True)
        for key in passive_history.scheduled.passive.bind(membrane.parent_definition(raw))["shapes"]
    }
    fields["membrane_transferred"] = total
    fields["phase_clock_s"] = np.asarray([state[-1]])
    m.pop("channels")
    for patch in m["membranes"]:
        patch.pop("pump")
    for edge in m["junctions"]:
        edge.pop("gate")
    for kind in ("channel", "pump"):
        raw["experiment"].pop(kind + "_controls")
    raw["execution"].pop("channel_capacity")
    c = passive_history.scheduled.bind(raw)
    proof = passive_history.conservation(raw, passive_history.scheduled.flatten(c, fields))
    extra_heat = float(
        np.sum(values["channel_dissipated_energy_pJ"]) + np.sum(values["pump_dissipated_energy_pJ"])
    )
    fuel_work = float(np.sum(values["metabolic_work_pJ"]))
    proof["energy_residual_pJ"] += extra_heat - fuel_work
    proof["dissipated_energy_pJ"] += extra_heat
    proof["work_pJ"] += fuel_work
    proof["maintained_fuel_work_pJ"] = fuel_work
    proof["channel_and_pump_dissipation_pJ"] = extra_heat
    return proof
