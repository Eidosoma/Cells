"""Independent chemical-particle water coupling and endpoint thermodynamics.

No production Cells or JAX imports. Scalar owned chemistry, full-node electrical
roots and the separate Decimal water oracle are composed at current volumes.
"""

import math
from copy import copy, deepcopy
from decimal import Decimal, localcontext

import numpy as np
from scipy.integrate import solve_ivp

from validation.tissue import surface_calcium_reference as calcium
from validation.tissue import surface_water_reference as passive_water
from validation.tissue import water_volume_reference as water

flatten, unpack = calcium.flatten, calcium.unpack
R, F = calcium.R, calcium.F
WATER_FIELDS = (
    "volume_increment_pL",
    "extracellular_volume_increment_pL",
    "water_transferred_pL",
    "water_dissipated_energy_pJ",
)


def bind(raw):
    if (
        raw["model"]["id"] != "resolved_calcium_water@1"
        or raw["model"].get("chemical_osmotic_coupling") != "ideal_all_cytosol_species_fixed_er@1"
    ):
        raise ValueError("Require declared owned chemical particles and fixed ER")
    prior = deepcopy(raw)
    for key in ("chemical_osmotic_coupling", "water_compartments", "water_membranes"):
        prior["model"].pop(key)
    prior["model"]["id"] = "resolved_calcium@10"
    prior["experiment"].pop("water_controls")
    base = calcium.bind(prior)
    passive = deepcopy(raw["model"]["ionic"])
    passive.update(
        id="resolved_water@1",
        water_compartments=deepcopy(raw["model"]["water_compartments"]),
        water_membranes=deepcopy(raw["model"]["water_membranes"]),
    )
    passive.pop("channels")
    for patch in passive["membranes"]:
        patch.pop("pump")
    for junction in passive["junctions"]:
        junction.pop("gate")
    bounded = passive_water.bind(
        dict(
            model=passive,
            experiment={
                k: deepcopy(raw["experiment"][k])
                for k in (
                    "end_time",
                    "observation_times",
                    "membrane_controls",
                    "junction_controls",
                    "water_controls",
                )
            },
            execution=deepcopy(raw["execution"]),
        )
    )
    return dict(
        base,
        calcium=base,
        definition=deepcopy(raw),
        water_case=bounded["water_case"],
        water_controls=bounded["water_controls"],
        minimum_volume_pL=bounded["minimum_volume_pL"],
        maximum_volume_pL=bounded["maximum_volume_pL"],
        shapes=base["shapes"] | {key: bounded["shapes"][key] for key in WATER_FIELDS},
    )


def initial(c):
    d = unpack(c["calcium"], calcium.initial(c["calcium"]))
    d.update({key: np.zeros(c["shapes"][key]) for key in WATER_FIELDS})
    return flatten(c, d)


def context(c, d):
    volume = np.r_[
        c["vi"] + d["volume_increment_pL"], c["vo"] + d["extracellular_volume_increment_pL"]
    ]
    if (
        not np.isfinite(volume).all()
        or np.any(volume <= c["minimum_volume_pL"])
        or np.any(volume >= c["maximum_volume_pL"])
    ):
        raise ValueError("Independent chemical-water volume outside bounds")
    n = len(c["vi"])
    stores = []
    for i, original in enumerate(c["stores"]):
        local = copy(original)
        local.volume = original.volume.copy()
        local.volume[local.cy] = volume[i]
        stores.append(local)
    return dict(c["calcium"], vi=volume[:n], vo=volume[n:], stores=stores), volume


def particles(c, d):
    names = c["stores"][0].ids
    count = len(c["vi"])
    result = np.zeros((len(names), count + len(c["vo"])))
    for i, store in enumerate(c["stores"]):
        result[:, i] = (store.n0 + d["chemical_amount_increment"][i])[:, store.cy]
    for s, ion in enumerate(c["raw"]["model"]["species"]):
        result[names.index(ion["id"]), count:] = c["ao"][s] + d["extracellular_amount_increment"][s]
    return result


def evaluate(c, state, time, *, channel_levels=None):
    d = unpack(c, state)
    current, volume = context(c, d)
    slope, phi, proof = calcium.evaluate(
        current, flatten(current, d), time, channel_levels=channel_levels
    )
    result = unpack(current, slope)
    amount = particles(c, d)
    edges = [
        dict(
            edge,
            hydraulic_permeability_m_per_Pa_s=edge["hydraulic_permeability_m_per_Pa_s"]
            * next(row["availability"] for row in reversed(schedule) if row["time"] <= time),
        )
        for edge, schedule in zip(c["water_case"]["edges"], c["water_controls"], strict=True)
    ]
    for index, edge in enumerate(c["water_case"]["edges"]):
        if edge["hydraulic_permeability_m_per_Pa_s"] == 0 and (
            d["water_transferred_pL"][index] != 0 or d["water_dissipated_energy_pJ"][index] != 0
        ):
            raise ValueError("A sealed water interface cannot own transfer or heat")
    flow = water.evaluate(dict(c["water_case"], edges=edges), volume, amount)
    n = len(c["vi"])
    result.update(
        volume_increment_pL=flow["volume_rate_pL_s"][:n],
        extracellular_volume_increment_pL=flow["volume_rate_pL_s"][n:],
        water_transferred_pL=flow["edge_flow_pL_s"],
        water_dissipated_energy_pJ=flow["edge_dissipation_pJ_s"],
    )
    return (
        flatten(c, result),
        phi,
        proof
        | dict(
            physical_energy_balance_pJ_s=proof["physical_energy_balance_pJ_s"]
            + flow["energy_balance_pJ_s"],
            water_energy_balance_pJ_s=flow["energy_balance_pJ_s"],
            water_dissipation_pJ_s=float(np.sum(flow["edge_dissipation_pJ_s"])),
            water_volume_rate_balance_pL_s=flow["volume_balance_pL_s"],
            chemical_particle_count_fmol=np.sum(amount, axis=0).tolist(),
        ),
    )


def free_energy_change(c, state, time=0.0):
    """Independent endpoint G: direct Decimal molecular energies, fixed capacitors."""
    d = unpack(c, state)
    current, volume = context(c, d)
    _, phi, _ = calcium.evaluate(current, flatten(current, d), time)
    if "initial_phi" not in c:
        c["initial_phi"] = calcium.evaluate(c["calcium"], calcium.initial(c["calcium"]), 0.0)[1]
    n = len(c["vi"])
    with localcontext() as precision:
        precision.prec = 80

        def dec(value):
            return Decimal(str(float(value)))

        rt = dec(R) * dec(c["layout"]["temperature"]) * Decimal("0.001")
        energy = Decimal(0)
        for i, store in enumerate(c["stores"]):
            for j in range(len(store.ids)):
                for k in range(store.n0.shape[1]):
                    amount0 = dec(store.n0[j, k])
                    amount = dec(store.n0[j, k] + d["chemical_amount_increment"][i, j, k])
                    current_volume = volume[i] if k == store.cy else store.volume[k]
                    before = amount0 * (
                        dec(store.mu0[j])
                        + (amount0 / (dec(store.volume[k]) * dec(store.c0))).ln()
                        - 1
                    )
                    after = amount * (
                        dec(store.mu0[j])
                        + (amount / (dec(current_volume) * dec(store.c0))).ln()
                        - 1
                    )
                    energy += rt * (after - before)
            delta_voltage = (
                F
                * 1e-15
                / store.cap
                * math.fsum(store.z * d["chemical_amount_increment"][i, :, store.er])
            )
            energy += dec(
                0.5e12
                * store.cap
                * delta_voltage
                * (2 * store.membrane["initial_voltage_V"] + delta_voltage)
            )
        for s in range(c["ao"].shape[0]):
            for k in range(len(c["vo"])):
                a0, a = (
                    dec(c["ao"][s, k]),
                    dec(c["ao"][s, k] + d["extracellular_amount_increment"][s, k]),
                )
                energy += rt * (
                    a * ((a / dec(volume[n + k])).ln() - 1) - a0 * ((a0 / dec(c["vo"][k])).ln() - 1)
                )
        initial_volume = np.r_[c["vi"], c["vo"]]
        case = c["water_case"]
        for i, (v0, v) in enumerate(zip(initial_volume, volume, strict=True)):
            inert = dec(case["impermeant_amount_fmol"][i])
            energy -= rt * inert * (dec(v) / dec(v0)).ln()
            extension0 = dec(v0) - dec(case["reference_volume_pL"][i])
            extension = dec(v) - dec(case["reference_volume_pL"][i])
            energy += Decimal("0.001") * (
                dec(case["bulk_modulus_Pa"][i])
                / (2 * dec(case["reference_volume_pL"][i]))
                * (extension**2 - extension0**2)
                + dec(case["pressure_offset_Pa"][i]) * (dec(v) - dec(v0))
            )
        for patch in c["raw"]["model"]["membranes"]:
            i = [row["id"] for row in c["raw"]["model"]["cells"]].index(patch["inside"])
            o = n + [row["id"] for row in c["raw"]["model"]["extracellular"]].index(
                patch["outside"]
            )
            initial_voltage = c["initial_phi"][i] - c["initial_phi"][o]
            voltage = phi[i] - phi[o]
            energy += dec(
                0.5e12
                * patch["capacitance_F"]
                * (voltage - initial_voltage)
                * (voltage + initial_voltage)
            )
        return float(energy)


def integrate(raw, *, channel_segments=None, rtol=1e-12, atol=1e-16, charge_atol=5e-32):
    c = bind(raw)
    e = raw["experiment"]
    segments = channel_segments or [(0.0, None)]
    events = {0.0, e["end_time"], *(t for t, _ in segments)}
    for kind, groups in e.items():
        if kind.endswith("_controls"):
            for row in groups:
                events.update(p["time"] for p in row.get("schedule", row.get("controls", [])))
    state = initial(c)
    saved, evaluations = {0.0: state.copy()}, 0
    atols = flatten(
        c,
        {
            key: np.full(shape, charge_atol if key.endswith("_C") else atol)
            for key, shape in c["shapes"].items()
        },
    )
    for left, right in zip(sorted(events), sorted(events)[1:], strict=False):
        levels = next(level for start, level in reversed(segments) if start <= left)
        solution = solve_ivp(
            lambda t, y, held=left, opened=levels: evaluate(c, y, held, channel_levels=opened)[0],
            (left, right),
            state,
            method="DOP853",
            rtol=rtol,
            atol=atols,
            max_step=5e-6,
            dense_output=True,
        )
        assert solution.success, solution.message
        evaluations += solution.nfev
        for time in e["observation_times"]:
            if left < time <= right:
                saved[time] = solution.sol(time)
        state = solution.y[:, -1]
    return dict(
        times=e["observation_times"],
        state=np.stack([saved[t] for t in e["observation_times"]]),
        evaluations=evaluations,
        method="segmented DOP853 independent chemistry/field and Decimal water",
        rtol=rtol,
        atol=atol,
        charge_atol=charge_atol,
    )
