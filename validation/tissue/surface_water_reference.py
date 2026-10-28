"""Independent full-node electrical/solute and compliant-volume reference.

No production Cells or JAX imports. Ionic and water ownership are assembled
separately at the same stage; only concentrations use the evolving volumes.
"""

from copy import deepcopy

import numpy as np
from scipy.integrate import solve_ivp

from validation.tissue import surface_dynamics_reference as ionic
from validation.tissue import water_volume_reference as water

F, R = ionic.F, ionic.R
initial, flatten, unpack = ionic.initial, ionic.flatten, ionic.unpack


def bind(raw):
    if raw["model"]["id"] != "resolved_water@1":
        raise ValueError("Require resolved_water@1")
    prior = deepcopy(raw)
    m = prior["model"]
    if any(p["reservoir"] for p in m["extracellular"]):
        raise ValueError("Water reference requires closed finite extracellular owners")
    declarations, membranes = m.pop("water_compartments"), m.pop("water_membranes")
    schedules = prior["experiment"].pop("water_controls")
    m["id"] = "resolved_tissue@1"
    base = ionic.bind(prior)
    nodes = [p["id"] for p in (*m["cells"], *m["extracellular"])]
    patches = [p["id"] for p in m["membranes"]]

    def indexed(rows, key, expected):
        mapping = {row[key]: row for row in rows}
        if len(mapping) != len(rows) or set(mapping) != set(expected):
            raise ValueError("Incomplete or duplicated water ownership: " + key)
        return [mapping[name] for name in expected]

    owners = indexed(declarations, "compartment_id", nodes)
    membrane_data = indexed(membranes, "membrane_id", patches)
    controls = [row["schedule"] for row in indexed(schedules, "membrane_id", patches)]
    for schedule in controls:
        times = [row["time"] for row in schedule]
        levels = [row["availability"] for row in schedule]
        if (
            not times
            or times[0] != 0
            or not np.isfinite(times).all()
            or np.any(np.diff(times) <= 0)
            or times[-1] > raw["experiment"]["end_time"]
            or not np.isfinite(levels).all()
            or not all(0 <= value <= 1 for value in levels)
        ):
            raise ValueError("Invalid right-continuous water schedule")
    minimum = np.asarray([row["minimum_volume_pL"] for row in owners])
    maximum = np.asarray([row["maximum_volume_pL"] for row in owners])
    volumes = np.r_[base["vi"], base["vo"]]
    references = np.asarray([row["reference_volume_pL"] for row in owners])
    if (
        not np.isfinite(minimum).all()
        or not np.isfinite(maximum).all()
        or np.any(minimum <= 0)
        or np.any(volumes <= minimum)
        or np.any(volumes >= maximum)
        or np.any(references <= minimum)
        or np.any(references >= maximum)
    ):
        raise ValueError("Initial and reference volumes must lie strictly inside declared bounds")
    case = water.bind(
        dict(
            temperature_K=m["temperature_K"],
            initial_volume_pL=volumes,
            reference_volume_pL=references,
            amount_fmol=np.c_[base["ai"], base["ao"]],
            impermeant_amount_fmol=[row["impermeant_amount_fmol"] for row in owners],
            bulk_modulus_Pa=[row["bulk_modulus_Pa"] for row in owners],
            pressure_offset_Pa=[row["pressure_offset_Pa"] for row in owners],
            edges=[
                dict(
                    sender=nodes.index(patch["inside"]),
                    receiver=nodes.index(patch["outside"]),
                    area_m2=patch["area_m2"],
                    hydraulic_permeability_m_per_Pa_s=row["hydraulic_permeability_m_per_Pa_s"],
                )
                for patch, row in zip(m["membranes"], membrane_data, strict=True)
            ],
        )
    )
    # This separate context prevents the inherited 12-field evaluator from
    # silently acquiring outer water fields when it unpacks/constructs slopes.
    return dict(
        base,
        raw=deepcopy(raw),
        ionic=base,
        water_case=case,
        water_controls=deepcopy(controls),
        minimum_volume_pL=minimum,
        maximum_volume_pL=maximum,
        shapes=base["shapes"]
        | dict(
            volume_increment_pL=(len(base["vi"]),),
            extracellular_volume_increment_pL=(len(base["vo"]),),
            water_transferred_pL=(len(patches),),
            water_dissipated_energy_pJ=(len(patches),),
        ),
    )


def evaluate(c, state, time):
    d = unpack(c, state)
    volume = np.r_[
        c["vi"] + d["volume_increment_pL"],
        c["vo"] + d["extracellular_volume_increment_pL"],
    ]
    if (
        not np.isfinite(volume).all()
        or np.any(volume <= c["minimum_volume_pL"])
        or np.any(volume >= c["maximum_volume_pL"])
    ):
        raise ValueError("Reference stage volume is outside its declared domain")
    n = len(c["vi"])
    prior = dict(c["ionic"], vi=volume[:n], vo=volume[n:])
    slope, phi, proof = ionic.evaluate(prior, flatten(c["ionic"], d), time)
    result = unpack(c["ionic"], slope)
    amount = np.c_[c["ai"] + d["amount_increment"], c["ao"] + d["extracellular_amount_increment"]]
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
    ionic_heat = sum(
        np.sum(result[kind + "_dissipated_energy_pJ"]) for kind in ("membrane", "junction", "face")
    )
    total_balance = chemical + capacitor + ionic_heat + flow["energy_balance_pJ_s"]
    return (
        flatten(c, result),
        phi,
        proof
        | dict(
            physical_energy_balance_pJ_s=float(total_balance),
            chemical_energy_rate_pJ_s=float(chemical),
            capacitor_energy_rate_pJ_s=float(capacitor),
            ionic_dissipation_pJ_s=float(ionic_heat),
            water_free_energy_rate_pJ_s=flow["free_energy_rate_pJ_s"],
            water_dissipation_pJ_s=float(flow["edge_dissipation_pJ_s"].sum()),
            water_energy_balance_pJ_s=flow["energy_balance_pJ_s"],
            water_volume_rate_balance_pL_s=flow["volume_balance_pL_s"],
        ),
    )


def integrate(raw, *, refinement=1):
    c = bind(raw)
    if type(refinement) is not int or refinement < 1:
        raise ValueError("Refinement must be a positive integer")
    experiment = raw["experiment"]
    events = sorted(
        {
            0.0,
            experiment["end_time"],
            *(
                change["time"]
                for kind in ("membrane", "junction", "water")
                for group in experiment[kind + "_controls"]
                for change in group["schedule"]
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
            max_step=1e-4 / refinement,
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
        method="DOP853; independent full-node ionic field, Decimal transport and osmotic water",
        rtol=2e-11 / refinement,
        amount_volume_energy_atol=2e-14 / refinement,
        electrode_charge_atol_C=1e-29 / refinement,
    )
