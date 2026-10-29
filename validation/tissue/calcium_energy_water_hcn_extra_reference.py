"""Independent finite fuel, owned chemical cytosol/ER and compliant water.

No production Cells/JAX imports. Rebinding the separately validated finite-pool
reference refreshes all three pumps and chemical cytosol volumes at each stage.
Molecular chemical species and three neutral fuel species own their energy once.
"""

import math
from copy import deepcopy
from decimal import Decimal, localcontext

import numpy as np
from scipy.integrate import solve_ivp

from validation.chemistry import finite_energy_reference as chemistry
from validation.tissue import calcium_water_reference as chemical_water
from validation.tissue import surface_calcium_energy_reference as energy
from validation.tissue import water_volume_reference as water

MODEL_ID = "resolved_calcium_energy_water@2"
CHEMICAL_COUPLING = "ideal_all_cytosol_species_fixed_er@1"
ENERGY_COUPLING = "neutral_ideal_atp_adp_pi@1"
F, R = energy.F, energy.R
flatten, unpack = energy.flatten, energy.unpack
EXTRA_FIELDS = (*chemical_water.WATER_FIELDS, "pool_volume_work_pJ")


def _chemical_water_context(raw):
    """Bind all 56 calcium laws, with passive geometry only for water parameters.

    The frozen chemical-water @1 binder selects calcium @10. This explicit
    full-catalog binding selects @11; only its water geometry is projected.
    No reduced channel or maintained-pool field/RHS is evaluated here.
    """
    parent = deepcopy(raw)
    for key in ("chemical_osmotic_coupling", "water_compartments", "water_membranes"):
        parent["model"].pop(key)
    parent["model"]["id"] = "resolved_calcium@11"
    parent["experiment"].pop("water_controls")
    base = energy.calcium.bind(parent)
    geometry = deepcopy(raw["model"]["ionic"])
    geometry.update(
        id="resolved_water@1",
        water_compartments=deepcopy(raw["model"]["water_compartments"]),
        water_membranes=deepcopy(raw["model"]["water_membranes"]),
    )
    geometry.pop("channels")
    for patch in geometry["membranes"]:
        patch.pop("pump")
    for junction in geometry["junctions"]:
        junction.pop("gate")
    bounded = chemical_water.passive_water.bind(
        dict(
            model=geometry,
            experiment={
                key: deepcopy(raw["experiment"][key])
                for key in (
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
        shapes=base["shapes"]
        | {key: bounded["shapes"][key] for key in chemical_water.WATER_FIELDS},
    )


def bind(raw):
    m = raw["model"]
    if (
        m["id"] != MODEL_ID
        or m.get("chemical_osmotic_coupling") != CHEMICAL_COUPLING
        or m.get("energy_osmotic_coupling") != ENERGY_COUPLING
    ):
        raise ValueError("Require joint finite-pool/chemical-particle water coupling identities")
    if any(
        {s["id"] for s in row["model"]["species"]} & {"ATP", "ADP", "Pi"} for row in m["stores"]
    ):
        raise ValueError("Finite fuel species cannot also be chemical-store particles")
    parent = deepcopy(raw)
    parent["model"]["id"] = "resolved_calcium_energy@5"
    for key in (
        "chemical_osmotic_coupling",
        "energy_osmotic_coupling",
        "water_compartments",
        "water_membranes",
    ):
        parent["model"].pop(key)
    parent["experiment"].pop("water_controls")
    base = energy.bind(parent)
    for row in m["stores"]:
        store = row["model"]
        owner = base["cell_ids"].index(row["cell_id"])
        cytosol = next(v for v in store["compartments"] if v["id"] == store["membrane"]["cytosol"])
        if cytosol["volume_pL"] != base["vi"][owner]:
            raise ValueError("Chemical cytosol and cell water must share one physical volume")
    projected = energy._project(base, base["energy_initial"])
    projected["model"].update(
        chemical_osmotic_coupling=CHEMICAL_COUPLING,
        water_compartments=deepcopy(m["water_compartments"]),
        water_membranes=deepcopy(m["water_membranes"]),
    )
    projected["experiment"]["water_controls"] = deepcopy(raw["experiment"]["water_controls"])
    bounded = _chemical_water_context(projected)
    shapes = base["shapes"] | {key: bounded["shapes"][key] for key in chemical_water.WATER_FIELDS}
    shapes["pool_volume_work_pJ"] = (len(base["cell_ids"]),)
    return dict(
        base,
        raw=deepcopy(raw),
        energy=base,
        chemical_water=bounded,
        water_case=bounded["water_case"],
        water_controls=bounded["water_controls"],
        minimum_volume_pL=bounded["minimum_volume_pL"],
        maximum_volume_pL=bounded["maximum_volume_pL"],
        pool_maximum_osmolyte_amount_fmol=2 * base["energy_initial"][0]
        + base["energy_initial"][1]
        + base["energy_initial"][2],
        shapes=shapes,
    )


def initial(c):
    d = unpack(c["energy"], energy.initial(c["energy"]))
    d.update({key: np.zeros(c["shapes"][key]) for key in EXTRA_FIELDS})
    return flatten(c, d)


def volumes(c, d):
    v = np.r_[c["vi"] + d["volume_increment_pL"], c["vo"] + d["extracellular_volume_increment_pL"]]
    if (
        not np.isfinite(v).all()
        or np.any(v <= c["minimum_volume_pL"])
        or np.any(v >= c["maximum_volume_pL"])
    ):
        raise ValueError("Joint reference volume is outside its positive bounded domain")
    return v


def current_energy_context(c, d):
    """Update all declared physical cytosol owners before any pump projection."""
    v = volumes(c, d)
    raw = deepcopy(c["energy"]["raw"])
    ion = raw["model"]["ionic"]
    for i, row in enumerate(ion["cells"]):
        row["volume_pL"] = float(v[i])
    n = len(ion["cells"])
    for i, row in enumerate(ion["extracellular"]):
        row["volume_pL"] = float(v[n + i])
    for row in raw["model"]["stores"]:
        owner = c["cell_ids"].index(row["cell_id"])
        store = row["model"]
        for compartment in store["compartments"]:
            if compartment["id"] == store["membrane"]["cytosol"]:
                compartment["volume_pL"] = float(v[owner])
    return energy.bind(raw)


def particles(c, d):
    """No exterior fuel, ionic duplicates, extra ER particles or bound moieties."""
    chemical = chemical_water.particles(c["chemical_water"], d)
    fuel = c["energy_initial"] + d["energy_amount_increment_fmol"]
    return np.vstack((chemical, np.c_[fuel, np.zeros((3, len(c["vo"])))]))


def evaluate(c, state, time, *, channel_levels=None):
    if np.ndim(state) != 1 or np.size(state) != sum(
        int(np.prod(shape)) for shape in c["shapes"].values()
    ):
        raise ValueError("Require the complete flat 43-field reference state")
    d = unpack(c, state)
    if not np.isfinite(state).all():
        raise ValueError("The complete joint reference state must be finite")
    for key in ("water_dissipated_energy_pJ", "regeneration_dissipated_energy_pJ"):
        if np.any(d[key] < -(4096 * np.finfo(np.float64).eps)):
            raise ValueError("Water and regeneration heat cannot be negative")
    support = np.zeros(len(c["cell_ids"]), dtype=bool)
    for edge in c["water_case"]["edges"]:
        if edge["hydraulic_permeability_m_per_Pa_s"] > 0:
            support[edge["sender"]] = True
    if np.any(d["pool_volume_work_pJ"][~support] != 0):
        raise ValueError("A cell without a water port cannot own pool volume work")
    v = volumes(c, d)
    current = current_energy_context(c, d)
    slope, phi, proof = energy.evaluate(
        current, flatten(current, d), time, channel_levels=channel_levels
    )
    result = unpack(current, slope)
    chemical = chemical_water.particles(c["chemical_water"], d)
    amount = particles(c, d)
    for index, edge in enumerate(c["water_case"]["edges"]):
        if edge["hydraulic_permeability_m_per_Pa_s"] == 0 and (
            d["water_transferred_pL"][index] != 0 or d["water_dissipated_energy_pJ"][index] != 0
        ):
            raise ValueError("Permanently sealed water routes cannot own flow or heat")
    edges = [
        dict(
            edge,
            hydraulic_permeability_m_per_Pa_s=edge["hydraulic_permeability_m_per_Pa_s"]
            * next(row["availability"] for row in reversed(schedule) if row["time"] <= time),
        )
        for edge, schedule in zip(c["water_case"]["edges"], c["water_controls"], strict=True)
    ]
    flow = water.evaluate(dict(c["water_case"], edges=edges), v, amount)
    n = len(c["cell_ids"])
    fuel = c["energy_initial"] + d["energy_amount_increment_fmol"]
    pool_values = [
        chemistry.thermodynamics(fuel[:, i], v[i], c["temperature"], c["energy_delta_g0"][i])
        for i in range(n)
    ]
    pool_volume = np.array(
        [
            value["volume_derivative_pJ_per_pL"] * flow["volume_rate_pL_s"][i]
            for i, value in enumerate(pool_values)
        ]
    )
    pool_material = np.array(
        [
            1e-3
            * np.dot(
                value["chemical_potential_J_mol"], result["energy_amount_increment_fmol"][:, i]
            )
            for i, value in enumerate(pool_values)
        ]
    )
    result.update(
        volume_increment_pL=flow["volume_rate_pL_s"][:n],
        extracellular_volume_increment_pL=flow["volume_rate_pL_s"][n:],
        water_transferred_pL=flow["edge_flow_pL_s"],
        water_dissipated_energy_pJ=flow["edge_dissipation_pJ_s"],
        pool_volume_work_pJ=pool_volume,
    )
    # Form the declared energy gradient separately. Missing or duplicated fuel
    # particles must not hide behind the water oracle's own cancellation.
    nonpool_gradient = 1e-3 * (
        flow["hydrostatic_pressure_Pa"]
        - R
        * c["temperature"]
        * (chemical.sum(axis=0) + c["water_case"]["impermeant_amount_fmol"])
        / v
    )
    volume_power = float(np.dot(nonpool_gradient, flow["volume_rate_pL_s"]) + pool_volume.sum())
    water_heat = float(np.sum(flow["edge_dissipation_pJ_s"]))
    volume_balance = volume_power + water_heat
    internal = (
        np.asarray(proof["pool_internal_transfer_balance_pJ_s"])
        + pool_volume
        - result["pool_volume_work_pJ"]
    )
    total_heat = sum(
        float(np.sum(value))
        for key, value in result.items()
        if key.endswith("_dissipated_energy_pJ")
    )
    supplied = float(np.sum(result["regeneration_supplied_work_pJ"]))
    other_work = float(np.sum(result["reservoir_work_pJ"]) + np.sum(result["electrode_work_pJ"]))
    return (
        flatten(c, result),
        phi,
        proof
        | dict(
            physical_energy_balance_pJ_s=float(
                proof["physical_energy_balance_pJ_s"] + volume_balance
            ),
            pool_free_energy_rate_pJ_s=(pool_material + pool_volume).tolist(),
            pool_volume_power_pJ_s=pool_volume.tolist(),
            pool_internal_transfer_balance_pJ_s=internal.tolist(),
            chemical_particle_count_fmol=chemical.sum(axis=0).tolist(),
            pool_osmolyte_amount_fmol=fuel.sum(axis=0).tolist(),
            pool_maximum_osmolyte_amount_fmol=c["pool_maximum_osmolyte_amount_fmol"].tolist(),
            osmotic_pressure_Pa=flow["osmotic_pressure_Pa"].tolist(),
            water_volume_free_energy_rate_pJ_s=volume_power,
            water_dissipation_pJ_s=water_heat,
            water_energy_balance_pJ_s=volume_balance,
            water_volume_rate_balance_pL_s=flow["volume_balance_pL_s"],
            physical_free_energy_rate_pJ_s=supplied + other_work - total_heat,
            non_regeneration_external_power_pJ_s=other_work,
            regeneration_is_only_external_energy=other_work == 0,
        ),
    )


def _chemical_free_energy(joint, state, time):
    """Direct molecular/compliance/capacitor G, with actual current-pool fields."""
    d = unpack(joint, state)
    volume = volumes(joint, d)
    current = current_energy_context(joint, d)
    _, phi, _ = energy.evaluate(current, flatten(current, d), time)
    c = joint["chemical_water"]
    if "initial_phi" not in c:
        c["initial_phi"] = energy.evaluate(joint["energy"], energy.initial(joint["energy"]), 0.0)[1]
    n = len(c["vi"])
    with localcontext() as precision:
        precision.prec = 80

        def dec(value):
            return Decimal(str(float(value)))

        rt = dec(R) * dec(c["layout"]["temperature"]) * Decimal("0.001")
        chemical_g = Decimal(0)
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
                    chemical_g += rt * (after - before)
            delta_voltage = (
                F
                * 1e-15
                / store.cap
                * math.fsum(store.z * d["chemical_amount_increment"][i, :, store.er])
            )
            chemical_g += dec(
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
                chemical_g += rt * (
                    a * ((a / dec(volume[n + k])).ln() - 1) - a0 * ((a0 / dec(c["vo"][k])).ln() - 1)
                )
        initial_volume = np.r_[c["vi"], c["vo"]]
        case = c["water_case"]
        for i, (v0, v) in enumerate(zip(initial_volume, volume, strict=True)):
            inert = dec(case["impermeant_amount_fmol"][i])
            chemical_g -= rt * inert * (dec(v) / dec(v0)).ln()
            extension0 = dec(v0) - dec(case["reference_volume_pL"][i])
            extension = dec(v) - dec(case["reference_volume_pL"][i])
            chemical_g += Decimal("0.001") * (
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
            chemical_g += dec(
                0.5e12
                * patch["capacitance_F"]
                * (voltage - initial_voltage)
                * (voltage + initial_voltage)
            )
        return float(chemical_g)


def free_energy_change(c, state, time=0.0):
    """Chemical/capacitor/compliance G plus each current-volume fuel G once."""
    d = unpack(c, state)
    v = volumes(c, d)
    value = _chemical_free_energy(c, state, time)
    fuel = c["energy_initial"] + d["energy_amount_increment_fmol"]
    return value + sum(
        chemistry.free_energy_change(
            c["energy_initial"][:, i],
            fuel[:, i],
            c["vi"][i],
            v[i],
            c["temperature"],
            c["energy_delta_g0"][i],
        )
        for i in range(len(c["cell_ids"]))
    )


class ReferenceIntegrationError(RuntimeError):
    def __init__(self, message, diagnostics):
        super().__init__(message)
        self.diagnostics = diagnostics


def integrate(raw, *, refinement=1, max_step_s=1.25e-6, channel_segments=None):
    if (
        type(refinement) is not int
        or refinement < 1
        or not energy._number(max_step_s, positive=True)
    ):
        raise ValueError("Require positive integer refinement and finite positive step cap")
    c, e = bind(raw), raw["experiment"]
    segments = channel_segments or [(0.0, None)]
    if (
        segments[0][0] != 0
        or any(not energy._number(t) or t > e["end_time"] for t, _ in segments)
        or any(b[0] <= a[0] for a, b in zip(segments, segments[1:], strict=False))
    ):
        raise ValueError("Require ordered assembly-owner levels from time zero")
    events = {0.0, e["end_time"], *(t for t, _ in segments)}
    for name, groups in e.items():
        if name.endswith("_controls"):
            events.update(
                row["time"]
                for group in groups
                for row in group.get("schedule", group.get("controls", []))
            )
    y, evaluations = initial(c), 0
    saved = {0.0: y.copy()}
    atols = flatten(
        c,
        {
            key: np.full(shape, (1e-29 if key.endswith("_C") else 2e-14) / refinement)
            for key, shape in c["shapes"].items()
        },
    )

    def rhs(t, state, held, levels):
        nonlocal evaluations
        evaluations += 1
        try:
            return evaluate(c, state, held, channel_levels=levels)[0]
        except Exception as error:
            raise ReferenceIntegrationError(
                str(error),
                dict(
                    time_s=float(t),
                    held_control_time_s=float(held),
                    state=[float(v) if np.isfinite(v) else str(v) for v in state],
                    evaluations=evaluations,
                    automatic_retry=False,
                ),
            ) from error

    for left, right in zip(sorted(events), sorted(events)[1:], strict=False):
        levels = next(value for start, value in reversed(segments) if start <= left)
        answer = solve_ivp(
            lambda t, state, held=left, opened=levels: rhs(t, state, held, opened),
            (left, right),
            y,
            method="DOP853",
            rtol=2e-11 / refinement,
            atol=atols,
            max_step=max_step_s / refinement,
            dense_output=True,
        )
        if not answer.success:
            raise ReferenceIntegrationError(
                answer.message,
                dict(
                    time_s=float(answer.t[-1]),
                    state=answer.y[:, -1].tolist(),
                    evaluations=evaluations,
                    automatic_retry=False,
                ),
            )
        for time in e["observation_times"]:
            if left < time <= right:
                saved[time] = answer.y[:, -1].copy() if time == right else answer.sol(time)
        y = answer.y[:, -1]
    return dict(
        times=e["observation_times"],
        state=np.stack([saved[t] for t in e["observation_times"]]),
        evaluations=evaluations,
        potential_V=np.stack(
            [
                evaluate(
                    c,
                    saved[t],
                    t,
                    channel_levels=next(value for start, value in reversed(segments) if start <= t),
                )[1]
                for t in e["observation_times"]
            ]
        ),
        method="DOP853 independent owned chemistry, live finite fuel and Decimal osmotic water",
        refinement=refinement,
        rtol=2e-11 / refinement,
        amount_volume_energy_atol=2e-14 / refinement,
        electrode_charge_atol_C=1e-29 / refinement,
        max_step_s=max_step_s / refinement,
        event_times=sorted(events),
    )
