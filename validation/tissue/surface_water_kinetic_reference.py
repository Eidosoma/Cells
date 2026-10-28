"""Independent maintained pumps, shared channels and compliant-volume dynamics.

No production Cells or JAX imports. The separate 19-field ionic context retains
the full-node field solve and scalar/Decimal kinetics; an 80-digit water oracle
uses its current ion amounts and the same stage volumes. ATP/ADP/Pi are external
maintained reservoirs, not finite osmolyte inventories in these compartments.
"""

from copy import deepcopy

import numpy as np
from scipy.integrate import solve_ivp

from validation.tissue import surface_kinetic_reference as ionic
from validation.tissue import surface_water_reference as passive_water
from validation.tissue import water_volume_reference as water

F, R = ionic.F, ionic.R
flatten, unpack = ionic.flatten, ionic.unpack
CONTROL_KINDS = ("membrane", "junction", "channel", "pump", "water")
WATER_FIELDS = (
    "volume_increment_pL",
    "extracellular_volume_increment_pL",
    "water_transferred_pL",
    "water_dissipated_energy_pJ",
)


def bind(raw):
    if raw["model"]["id"] != "resolved_water@2":
        raise ValueError("Require resolved_water@2")
    if raw["model"]["temperature_K"] != 298.15:
        raise ValueError("Unscaled shared-channel source kinetics require exactly 298.15 K")
    prior = deepcopy(raw)
    m = prior["model"]
    m["id"] = "resolved_tissue@7"
    m.pop("water_compartments")
    m.pop("water_membranes")
    prior["experiment"].pop("water_controls")
    for patch in m["membranes"]:
        pump = patch["pump"]
        if pump is not None and pump["metabolism"]["kind"] != "maintained_chemical_reservoirs@1":
            raise ValueError("Active-water reference requires maintained pump chemistry")
    base = ionic.bind(prior)

    # Reuse independent ownership/domain validation without giving the older
    # passive evaluator a 23-field context or importing production projections.
    projected = deepcopy(raw)
    projected["model"]["id"] = "resolved_water@1"
    projected["model"].pop("channels")
    for patch in projected["model"]["membranes"]:
        patch.pop("pump")
    for junction in projected["model"]["junctions"]:
        junction.pop("gate")
    for kind in ("channel", "pump"):
        projected["experiment"].pop(kind + "_controls")
    projected["execution"].pop("channel_capacity", None)
    bounded = passive_water.bind(projected)
    shapes = base["shapes"] | {name: bounded["shapes"][name] for name in WATER_FIELDS}
    return dict(
        base,
        raw=deepcopy(raw),
        ionic=base,
        water_case=bounded["water_case"],
        water_controls=bounded["water_controls"],
        minimum_volume_pL=bounded["minimum_volume_pL"],
        maximum_volume_pL=bounded["maximum_volume_pL"],
        shapes=shapes,
    )


def initial(c):
    fields = unpack(c["ionic"], ionic.initial(c["ionic"]))
    fields.update({name: np.zeros(c["shapes"][name]) for name in WATER_FIELDS})
    return flatten(c, fields)


def evaluate(c, state, time):
    d = unpack(c, state)
    volume = np.r_[
        c["vi"] + d["volume_increment_pL"],
        c["vo"] + d["extracellular_volume_increment_pL"],
    ]
    amount = np.c_[c["ai"] + d["amount_increment"], c["ao"] + d["extracellular_amount_increment"]]
    if (
        not np.isfinite(volume).all()
        or np.any(volume <= c["minimum_volume_pL"])
        or np.any(volume >= c["maximum_volume_pL"])
        or not np.isfinite(amount).all()
        or np.any(amount <= 0)
    ):
        raise ValueError("Reference stage is outside its positive-ion/bounded-volume domain")
    n = len(c["vi"])
    current = dict(c["ionic"], vi=volume[:n], vo=volume[n:])
    slope, phi, proof = ionic.evaluate(current, flatten(c["ionic"], d), time)
    result = unpack(c["ionic"], slope)
    edges = [
        dict(
            edge,
            hydraulic_permeability_m_per_Pa_s=edge["hydraulic_permeability_m_per_Pa_s"]
            * next(row["availability"] for row in reversed(schedule) if row["time"] <= time),
        )
        for edge, schedule in zip(c["water_case"]["edges"], c["water_controls"], strict=True)
    ]
    flow = water.evaluate(dict(c["water_case"], edges=edges), volume, amount)
    result.update(
        volume_increment_pL=flow["volume_rate_pL_s"][:n],
        extracellular_volume_increment_pL=flow["volume_rate_pL_s"][n:],
        water_transferred_pL=flow["edge_flow_pL_s"],
        water_dissipated_energy_pJ=flow["edge_dissipation_pJ_s"],
    )
    material_rate = np.c_[result["amount_increment"], result["extracellular_amount_increment"]]
    chemical = (
        1e-3 * R * c["layout"]["temperature"] * np.sum(np.log(amount / volume) * material_rate)
    )
    charge_rate = 1e-15 * F * np.sum(np.asarray(c["layout"]["valence"]) * material_rate, axis=0)
    capacitor = 1e12 * np.dot(phi, charge_rate)
    passive_heat = sum(
        np.sum(result[kind + "_dissipated_energy_pJ"]) for kind in ("membrane", "junction", "face")
    )
    channel_heat = np.sum(result["channel_dissipated_energy_pJ"])
    pump_heat = np.sum(result["pump_dissipated_energy_pJ"])
    maintained_power = np.sum(result["metabolic_work_pJ"])
    ionic_heat = passive_heat + channel_heat + pump_heat
    total_balance = (
        chemical + capacitor + ionic_heat + flow["energy_balance_pJ_s"] - maintained_power
    )
    return (
        flatten(c, result),
        phi,
        proof
        | dict(
            physical_energy_balance_pJ_s=float(total_balance),
            chemical_energy_rate_pJ_s=float(chemical),
            capacitor_energy_rate_pJ_s=float(capacitor),
            passive_dissipation_pJ_s=float(passive_heat),
            channel_dissipation_pJ_s=float(channel_heat),
            pump_dissipation_pJ_s=float(pump_heat),
            ionic_dissipation_pJ_s=float(ionic_heat),
            maintained_metabolic_power_pJ_s=float(maintained_power),
            water_free_energy_rate_pJ_s=flow["free_energy_rate_pJ_s"],
            water_dissipation_pJ_s=float(flow["edge_dissipation_pJ_s"].sum()),
            water_energy_balance_pJ_s=flow["energy_balance_pJ_s"],
            water_volume_rate_balance_pL_s=flow["volume_balance_pL_s"],
        ),
    )


def integrate(raw, *, refinement=1):
    if type(refinement) is not int or refinement < 1:
        raise ValueError("Refinement must be a positive integer")
    c, experiment = bind(raw), raw["experiment"]
    events = sorted(
        {
            0.0,
            experiment["end_time"],
            *(
                row["time"]
                for kind in CONTROL_KINDS
                for group in experiment[kind + "_controls"]
                for row in group["schedule"]
            ),
        }
    )
    times = experiment["observation_times"]
    state, evaluations = initial(c), 0
    saved = {0.0: state.copy()}
    atols = flatten(
        c,
        {
            name: np.full(shape, (1e-29 if name.endswith("_C") else 2e-14) / refinement)
            for name, shape in c["shapes"].items()
        },
    )
    for left, right in zip(events, events[1:], strict=False):
        solution = solve_ivp(
            lambda t, y, held=left: evaluate(c, y, held)[0],
            (left, right),
            state,
            method="DOP853",
            rtol=2e-11 / refinement,
            atol=atols,
            max_step=1e-5 / refinement,
            dense_output=True,
        )
        if not solution.success:
            raise RuntimeError(solution.message)
        evaluations += solution.nfev
        for t in times:
            if left < t <= right:
                saved[t] = solution.sol(t)
        state = solution.y[:, -1]
    return dict(
        times=times,
        state=np.stack([saved[t] for t in times]),
        potential_V=np.stack([evaluate(c, saved[t], t)[1] for t in times]),
        evaluations=evaluations,
        refinement=refinement,
        method="DOP853; full-node ionic field, Decimal shared channels/pumps and osmotic water",
        rtol=2e-11 / refinement,
        amount_volume_energy_atol=2e-14 / refinement,
        electrode_charge_atol_C=1e-29 / refinement,
        max_step_s=1e-5 / refinement,
        event_times=events,
    )
