"""Independent full-node electrical roots, scalar chemistry and adaptive ODE.

No production Cells/JAX imports. Reuses independently checked Decimal ionic
laws and scalar ER/PMCA/NCX/Cav equations; external exchange is assembled using
explicit owner loops, and physical energy is differentiated independently.
"""

import math
from copy import deepcopy

import numpy as np
from scipy.integrate import solve_ivp

from tests.reference_gated_calcium import scalar_flux, scalar_kinetics
from tests.reference_ip3_calcium import IP3Store
from tests.reference_plasma_calcium import scalar_rates
from validation.tissue import surface_field_reference as electrical
from validation.tissue import surface_kinetic_reference as kinetic

F, R = kinetic.F, kinetic.R
flatten, unpack = kinetic.flatten, kinetic.unpack
ER_FIELDS = (
    "chemical_amount_increment",
    "reaction_extent",
    "reaction_dissipated_energy_pJ",
    "er_passive_transferred",
    "er_pump_transferred",
    "er_release_transferred",
    "er_transport_dissipated_energy_pJ",
)


def bind(raw):
    c = kinetic.bind(
        dict(model=raw["model"]["ionic"], experiment=raw["experiment"], execution=raw["execution"])
    )
    c["full"] = deepcopy(raw)
    ids = [p["id"] for p in c["raw"]["model"]["cells"]]
    stores = {p["cell_id"]: p["model"] for p in raw["model"]["stores"]}
    bindings = {p["cell_id"]: p for p in raw["model"]["ip3_release"]}
    c["stores"] = [IP3Store(dict(model=stores[k]), bindings[k]) for k in ids]
    n = len(ids)
    nm = len(c["raw"]["model"]["membranes"])
    for name, value in zip(
        ER_FIELDS, c["stores"][0].unpack(np.zeros(c["stores"][0].size)), strict=True
    ):
        c["shapes"][name] = (n, *value.shape)
    c["shapes"].update(
        plasma_pump_cycles=(nm,),
        plasma_exchange_cycles=(nm,),
        plasma_dissipated_energy_pJ=(2, nm),
        calcium_gate=(2, nm),
        calcium_channel_transferred=(nm,),
        calcium_channel_dissipated_energy_pJ=(nm,),
        plasma_metabolic_work_pJ=(nm,),
        er_metabolic_work_pJ=(n,),
    )
    return c


def initial(c):
    d = unpack(c, kinetic.initial(c))
    d["calcium_gate"] = np.array(
        [[v["initial_gate"][k] for v in c["full"]["model"]["calcium_channels"]] for k in ("m", "h")]
    )
    return flatten(c, d)


def held(c, family, owner, time):
    group = c["full"]["experiment"][family]
    row = group[owner]
    values = row["controls"] if family == "store_controls" else row["schedule"]
    return next(v for v in reversed(values) if v["time"] <= time)


def evaluate(c, state, time, *, channel_levels=None):
    d = unpack(c, state)
    ion = c["raw"]["model"]
    m = c["full"]["model"]
    p = c["layout"]
    ids = [s["id"] for s in ion["species"]]
    ca = ids.index(m["plasma_transport"]["calcium_species"])
    na = ids.index(m["plasma_transport"]["sodium_species"])
    free = np.stack(
        [
            (s.n0 + d["chemical_amount_increment"][i])[[s.ids.index(k) for k in ids], s.cy]
            for i, s in enumerate(c["stores"])
        ],
        axis=1,
    )
    dr, phi, proof = kinetic.evaluate(
        c, state, time, inside_amount=free, channel_levels=channel_levels
    )
    result = unpack(c, dr)
    ci = free / c["vi"]
    co = (c["ao"] + d["extracellular_amount_increment"]) / c["vo"]
    n = len(c["vi"])
    for j, patch in enumerate(ion["membranes"]):
        i, o = p["membrane_cell"][j], p["membrane_outside"][j]
        vm = phi[i] - phi[n + o]
        route = m["plasma_transport"]["membranes"][j]
        control = held(c, "plasma_controls", j, time)
        pmca, ncx, gp, gx, drive = scalar_rates(
            ci[na, i],
            co[na, o],
            ci[ca, i],
            co[ca, o],
            vm,
            p["temperature"],
            route["pump"],
            route["exchanger"],
            (control["pump"], control["exchanger"]),
        )
        target, tau = scalar_kinetics(vm)
        result["calcium_gate"][:, j] = (target - d["calcium_gate"][:, j]) / tau
        ch = m["calcium_channels"][j]
        opening = (
            d["calcium_gate"][0, j] ** 2
            * d["calcium_gate"][1, j]
            * held(c, "calcium_channel_controls", j, time)["availability"]
        )
        inward, diss = scalar_flux(
            ci[ca, i],
            co[ca, o],
            vm,
            p["temperature"],
            patch["area_m2"],
            ch["max_permeability_m_per_s"] * ch["abundance"] * opening,
        )
        for s, outward in ((ca, pmca + ncx - inward), (na, -3 * ncx)):
            result["amount_increment"][s, i] -= outward
            result["extracellular_amount_increment"][s, o] += outward
        result["plasma_pump_cycles"][j] = pmca
        result["plasma_exchange_cycles"][j] = ncx
        result["plasma_dissipated_energy_pJ"][:, j] = -1e-3 * np.array([pmca * gp, ncx * gx])
        result["calcium_channel_transferred"][j] = -inward
        result["calcium_channel_dissipated_energy_pJ"][j] = diss
        result["plasma_metabolic_work_pJ"][j] = -1e-3 * drive * pmca
    chemical = (
        1e-3 * R * p["temperature"] * np.sum(np.log(co) * result["extracellular_amount_increment"])
    )
    er_power = 0.0
    for i, s in enumerate(c["stores"]):
        local = np.concatenate([d[k][i].ravel() for k in ER_FIELDS])
        parts = s.unpack(s.rhs(local, held(c, "store_controls", i, time)))
        for j, k in enumerate(ids):
            parts[0][s.ids.index(k), s.cy] += result["amount_increment"][j, i]
        for k, v in zip(ER_FIELDS, parts, strict=True):
            result[k][i] = v
        pump = s.membrane["pump"]
        drive = (
            0
            if pump is None
            else pump["delta_g0_J_per_mol"]
            + s.rt * math.log(pump["adp_mM"] * pump["pi_mM"] / pump["atp_mM"])
        )
        result["er_metabolic_work_pJ"][i] = -1e-3 * drive * parts[4][0]
        chemical += (
            1e-3
            * s.rt
            * np.sum(
                (
                    s.mu0[:, None]
                    + np.log((s.n0 + d["chemical_amount_increment"][i]) / (s.volume * s.c0))
                )
                * parts[0]
            )
        )
        voltage = s.membrane["initial_voltage_V"] + F * 1e-15 / s.cap * math.fsum(
            s.z * d["chemical_amount_increment"][i, :, s.er]
        )
        er_power += 1e12 * voltage * F * 1e-15 * math.fsum(s.z * parts[0][:, s.er])
    raw = kinetic.base.stage(c, state, time)
    raw["ci"] = ci
    matrix, active, reservoir, _, floating, _ = electrical.topology(raw)
    pins = ~active | reservoir
    for members in floating:
        pins[members[0]] = True
    free_nodes = np.flatnonzero(~pins)
    current = (
        F
        * 1e-15
        * (
            np.asarray(p["valence"]).T
            @ np.c_[result["amount_increment"], result["extracellular_amount_increment"]]
        )[0]
    )
    dv = np.zeros_like(phi)
    dv[free_nodes] = np.linalg.solve(matrix[np.ix_(free_nodes, free_nodes)], current[free_nodes])
    np.testing.assert_allclose(matrix @ dv, current, atol=3e-23, rtol=2e-12)
    electric = 0.0
    for j, patch in enumerate(ion["membranes"]):
        i, o = p["membrane_cell"][j], n + p["membrane_outside"][j]
        electric += 1e12 * patch["capacitance_F"] * (phi[i] - phi[o]) * (dv[i] - dv[o])
    dissipation = sum(
        float(np.sum(v)) for k, v in result.items() if k.endswith("_dissipated_energy_pJ")
    )
    work = sum(
        float(np.sum(result[k]))
        for k in ("metabolic_work_pJ", "plasma_metabolic_work_pJ", "er_metabolic_work_pJ")
    )
    return (
        flatten(c, result),
        phi,
        proof
        | dict(physical_energy_balance_pJ_s=chemical + electric + er_power + dissipation - work),
    )


def integrate(raw, *, channel_segments=None):
    c = bind(raw)
    e = raw["experiment"]
    segments = channel_segments or [(0.0, None)]
    events = {0.0, e["end_time"], *(t for t, _ in segments)}
    for kind, groups in e.items():
        if kind.endswith("_controls"):
            for row in groups:
                events.update(v["time"] for v in row.get("schedule", row.get("controls", [])))
    times = e["observation_times"]
    state = initial(c)
    result = {0.0: state.copy()}
    evaluations = 0
    atols = flatten(
        c,
        {
            k: np.full(shape, 1e-29 if k.endswith("_C") else 2e-14)
            for k, shape in c["shapes"].items()
        },
    )
    events = sorted(events)
    for left, right in zip(events, events[1:], strict=False):
        levels = next(level for time, level in reversed(segments) if time <= left)
        sol = solve_ivp(
            lambda t, y, held=left, opened=levels: evaluate(c, y, held, channel_levels=opened)[0],
            (left, right),
            state,
            method="DOP853",
            rtol=2e-11,
            atol=atols,
            max_step=5e-5,
            dense_output=True,
        )
        assert sol.success, sol.message
        evaluations += sol.nfev
        for t in times:
            if left < t <= right:
                result[t] = sol.sol(t)
        state = sol.y[:, -1]
    potentials = []
    for t in times:
        levels = next(level for time, level in reversed(segments) if time <= t)
        potentials.append(evaluate(c, result[t], t, channel_levels=levels)[1])
    return dict(
        times=times,
        state=np.stack([result[t] for t in times]).tolist(),
        potential_V=np.stack(potentials).tolist(),
        rhs_evaluations=evaluations,
        method="segmented DOP853, full-node roots, Decimal ions, scalar ER/PMCA/NCX/Cav",
        rtol=2e-11,
        amount_energy_gate_atol=2e-14,
        electrode_charge_atol_C=1e-29,
    )
