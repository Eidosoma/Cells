"""Independent finite transformed pools, ion kinetics and compliant-volume flow.

No Cells or JAX imports. Finite pools are neutral ideal osmolytes additional to
declared background particles. Their 1-M transformed free energy is owned once;
the water oracle supplies only flow, heat and partial-volume energy derivatives.
"""

from copy import deepcopy

import numpy as np
from scipy.integrate import solve_ivp

from validation.chemistry import finite_energy_reference as chemistry
from validation.tissue import surface_energy_reference as energy
from validation.tissue import surface_water_reference as passive_water
from validation.tissue import water_volume_reference as water

F, R = energy.F, energy.R
flatten, unpack = energy.flatten, energy.unpack
MODEL_ID = "resolved_energy_water@1"
COUPLING = "neutral_ideal_atp_adp_pi@1"
CONTROL_KINDS = (*energy.CONTROL_KINDS, "water")
EXTRA_FIELDS = (
    "volume_increment_pL",
    "extracellular_volume_increment_pL",
    "water_transferred_pL",
    "water_dissipated_energy_pJ",
    "pool_volume_work_pJ",
)


def bind(raw):
    if raw["model"]["id"] != MODEL_ID or raw["model"].get("energy_osmotic_coupling") != COUPLING:
        raise ValueError(
            "Require resolved_energy_water@1 with explicit neutral ideal pool coupling"
        )
    projected = deepcopy(raw)
    projected["model"]["id"] = "resolved_energy@1"
    for name in ("energy_osmotic_coupling", "water_compartments", "water_membranes"):
        projected["model"].pop(name)
    projected["experiment"].pop("water_controls")
    base = energy.bind(projected)

    # Independent passive projection for existing water ownership/domain checks.
    # No production schema/model projection is used; all accepted references
    # retain their own unmodified contexts and field counts.
    projected = deepcopy(raw)
    projected["model"]["id"] = "resolved_water@1"
    for name in ("energy_osmotic_coupling", "energy_pools", "regeneration_ports", "channels"):
        projected["model"].pop(name)
    for patch in projected["model"]["membranes"]:
        patch.pop("pump")
    for junction in projected["model"]["junctions"]:
        junction.pop("gate")
    for kind in ("channel", "pump", "regeneration"):
        projected["experiment"].pop(kind + "_controls")
    for name in ("channel_capacity", "regeneration_capacity"):
        projected["execution"].pop(name, None)
    bounded = passive_water.bind(projected)
    shapes = (
        base["shapes"]
        | {name: bounded["shapes"][name] for name in EXTRA_FIELDS if name != "pool_volume_work_pJ"}
        | dict(pool_volume_work_pJ=(len(base["vi"]),))
    )
    pool = base["energy_initial"]
    return dict(
        base,
        raw=deepcopy(raw),
        energy=base,
        water_case=bounded["water_case"],
        water_controls=bounded["water_controls"],
        minimum_volume_pL=bounded["minimum_volume_pL"],
        maximum_volume_pL=bounded["maximum_volume_pL"],
        pool_maximum_osmolyte_amount_fmol=2 * pool[0] + pool[1] + pool[2],
        shapes=shapes,
    )


def initial(c):
    fields = unpack(c["energy"], energy.initial(c["energy"]))
    fields.update({name: np.zeros(c["shapes"][name]) for name in EXTRA_FIELDS})
    return flatten(c, fields)


def evaluate(c, state, time):
    d = unpack(c, state)
    volume = np.r_[
        c["vi"] + d["volume_increment_pL"],
        c["vo"] + d["extracellular_volume_increment_pL"],
    ]
    ionic_amount = np.c_[
        c["ai"] + d["amount_increment"], c["ao"] + d["extracellular_amount_increment"]
    ]
    if (
        not np.isfinite(state).all()
        or not np.isfinite(volume).all()
        or not np.isfinite(ionic_amount).all()
        or np.any(volume <= c["minimum_volume_pL"])
        or np.any(volume >= c["maximum_volume_pL"])
        or np.any(ionic_amount <= 0)
    ):
        raise ValueError("Reference stage is outside its finite positive-ion/bounded-volume domain")
    n = len(c["vi"])
    nested = dict(c["energy"]["ionic"], vi=volume[:n], vo=volume[n:])
    current = dict(
        c["energy"], vi=volume[:n], vo=volume[n:], energy_volumes=volume[:n], ionic=nested
    )
    slope, phi, proof = energy.evaluate(current, flatten(c["energy"], d), time)
    result = unpack(c["energy"], slope)
    pool_amount = c["energy_initial"] + d["energy_amount_increment_fmol"]
    # Pool particles have no exterior inventory. Keep all three species distinct
    # in the pressure oracle; never sum its 1-mM pool mixing energy with Gpool.
    particles = np.vstack((ionic_amount, np.c_[pool_amount, np.zeros((3, len(c["vo"])))]))
    edges = [
        dict(
            edge,
            hydraulic_permeability_m_per_Pa_s=edge["hydraulic_permeability_m_per_Pa_s"]
            * next(row["availability"] for row in reversed(schedule) if row["time"] <= time),
        )
        for edge, schedule in zip(c["water_case"]["edges"], c["water_controls"], strict=True)
    ]
    flow = water.evaluate(dict(c["water_case"], edges=edges), volume, particles)
    pool_volume, pool_chemical = np.zeros(n), np.zeros(n)
    for i in range(n):
        values = chemistry.thermodynamics(
            pool_amount[:, i], volume[i], c["layout"]["temperature"], c["energy_delta_g0"][i]
        )
        pool_volume[i] = values["volume_derivative_pJ_per_pL"] * flow["volume_rate_pL_s"][i]
        pool_chemical[i] = 1e-3 * np.dot(
            values["chemical_potential_J_mol"], result["energy_amount_increment_fmol"][:, i]
        )
    result.update(
        volume_increment_pL=flow["volume_rate_pL_s"][:n],
        extracellular_volume_increment_pL=flow["volume_rate_pL_s"][n:],
        water_transferred_pL=flow["edge_flow_pL_s"],
        water_dissipated_energy_pJ=flow["edge_dissipation_pJ_s"],
        pool_volume_work_pJ=pool_volume,
    )
    pool_transfer = np.zeros(n)
    for j, patch in enumerate(c["raw"]["model"]["membranes"]):
        pool_transfer[c["cell_ids"].index(patch["inside"])] += result["metabolic_work_pJ"][j]
    for j, port in enumerate(c["raw"]["model"]["regeneration_ports"]):
        owner = c["cell_ids"].index(c["pools"][port["pool_id"]]["cell_id"])
        pool_transfer[owner] += (
            result["regeneration_dissipated_energy_pJ"][j]
            - result["regeneration_supplied_work_pJ"][j]
        )
    pool_free_rate = pool_chemical + pool_volume
    internal = pool_free_rate + pool_transfer - result["pool_volume_work_pJ"]
    # Form the full volume gradient independently of the water oracle's zero
    # residual. An omitted pool particle must not hide behind that identity.
    nonpool_gradient = 1e-3 * (
        flow["hydrostatic_pressure_Pa"]
        - R
        * c["layout"]["temperature"]
        * (ionic_amount.sum(axis=0) + c["water_case"]["impermeant_amount_fmol"])
        / volume
    )
    volume_power = np.dot(nonpool_gradient, flow["volume_rate_pL_s"]) + pool_volume.sum()
    water_heat = flow["edge_dissipation_pJ_s"].sum()
    volume_balance = volume_power + water_heat
    total = proof["physical_energy_balance_pJ_s"] + volume_balance
    return (
        flatten(c, result),
        phi,
        proof
        | dict(
            physical_energy_balance_pJ_s=float(total),
            pool_free_energy_rate_pJ_s=pool_free_rate.tolist(),
            pool_volume_power_pJ_s=pool_volume.tolist(),
            pool_internal_transfer_balance_pJ_s=internal.tolist(),
            pool_osmolyte_amount_fmol=pool_amount.sum(axis=0).tolist(),
            pool_maximum_osmolyte_amount_fmol=c["pool_maximum_osmolyte_amount_fmol"].tolist(),
            osmotic_pressure_Pa=flow["osmotic_pressure_Pa"].tolist(),
            water_volume_free_energy_rate_pJ_s=float(volume_power),
            water_dissipation_pJ_s=float(water_heat),
            water_energy_balance_pJ_s=float(volume_balance),
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
            max_step=1.25e-6 / refinement,
            dense_output=True,
        )
        if not solution.success:
            raise RuntimeError(solution.message)
        evaluations += solution.nfev
        for t in experiment["observation_times"]:
            if left < t <= right:
                saved[t] = solution.sol(t)
        state = solution.y[:, -1]
    times = experiment["observation_times"]
    return dict(
        times=times,
        state=np.stack([saved[t] for t in times]),
        potential_V=np.stack([evaluate(c, saved[t], t)[1] for t in times]),
        evaluations=evaluations,
        refinement=refinement,
        method="DOP853; full-node ionic kinetics, finite pools and Decimal osmotic water",
        rtol=2e-11 / refinement,
        amount_volume_energy_atol=2e-14 / refinement,
        electrode_charge_atol_C=1e-29 / refinement,
        max_step_s=1.25e-6 / refinement,
        event_times=events,
    )
