"""Independent Decimal ATPase, diffusion and full-node electric accounting.

No production Cells/JAX imports. The reference applies the independently
evaluated pump flux directly to named ion owners and solves the full capacitor
derivative system, rather than reusing the production scatter or reduced solve.
"""

import math

import numpy as np
from scipy.integrate import solve_ivp

from validation.betse.pump_contact.pump_reference import oracle as pump_oracle
from validation.tissue import surface_dynamics_reference as ionic
from validation.tissue import surface_field_reference as electrical
from validation.tissue import surface_redistribution_reference as prior

F, R = ionic.F, ionic.R
initial, flatten, unpack = ionic.initial, ionic.flatten, ionic.unpack


def bind(raw):
    c = prior.bind(raw)
    m = raw["model"]
    k, n, e = len(m["mobile_pumps"]), len(m["membranes"]), len(m["surface_edges"])
    return dict(
        prior=c,
        raw=c["raw"],
        shapes=c["shapes"]
        | dict(
            pump_surface_amount_increment=(k, n),
            pump_surface_transferred=(k, e),
            pump_surface_dissipated_energy_pJ=(k, e),
            pump_cycles=(k, n),
            pump_dissipated_energy_pJ=(k, n),
            metabolic_work_pJ=(k, n),
        ),
    )


def evaluate(c, state, time):
    d, m = unpack(c, state), c["raw"]["model"]
    derivative, phi, proof = prior.evaluate(c["prior"], flatten(c["prior"], d), time)
    result = unpack(c["prior"], derivative)
    for name, shape in c["shapes"].items():
        if name not in result:
            result[name] = np.zeros(shape)
    ic = c["prior"]["ionic"]
    raw = ionic.stage(ic, flatten(ic, d), time)
    p, n = ic["layout"], len(ic["qi"])
    ions = [s["id"] for s in m["species"]]
    patches = [p["id"] for p in m["membranes"]]
    cell, outside, supply = (
        result[k]
        for k in ("amount_increment", "extracellular_amount_increment", "reservoir_supplied")
    )
    density = np.zeros(c["shapes"]["pump_surface_amount_increment"])
    for k, pump in enumerate(m["mobile_pumps"]):
        na, ka = (ions.index(pump["roles"][r]) for r in ("sodium", "potassium"))
        meta = pump["metabolism"]
        for j, patch in enumerate(m["membranes"]):
            amount = (
                pump["initial_amount_fmol"][patch["id"]] + d["pump_surface_amount_increment"][k, j]
            )
            density[k, j] = amount / (patch["area_m2"] * 1e12)
            i, o = p["membrane_cell"][j], p["membrane_outside"][j]
            group = next(
                v
                for v in c["raw"]["experiment"]["pump_controls"]
                if v["pump_id"] == pump["id"] and v["membrane_id"] == patch["id"]
            )
            availability = next(
                v["availability"] for v in reversed(group["schedule"]) if v["time"] <= time
            )
            case = dict(
                id=pump["id"],
                na_in_mM=float(raw["ci"][na, i]),
                na_out_mM=float(raw["co"][na, o]),
                k_in_mM=float(raw["ci"][ka, i]),
                k_out_mM=float(raw["co"][ka, o]),
                temperature_K=m["temperature_K"],
                area_m2=patch["area_m2"],
                alpha_mol_m2_s=float(pump["turnover_per_s"] * amount * 1e-15 / patch["area_m2"]),
                availability=availability,
                voltage_V=float(phi[i] - phi[n + o]),
                delta_g0_J_mol=meta["delta_g0_J_per_mol"],
                **{v: meta[v] for v in ("atp_mM", "adp_mM", "pi_mM")},
                **{v: pump[v] for v in ("km_na_mM", "km_k_mM", "km_atp_mM")},
            )
            rate = pump_oracle(case, {"F": F, "R": R})
            result["pump_cycles"][k, j] = -rate["na_in_fmol_s"] / 3
            result["pump_dissipated_energy_pJ"][k, j] = rate["dissipation_pJ_s"]
            result["metabolic_work_pJ"][k, j] = rate["chemical_input_power_pJ_s"]
            for species, key in ((na, "na_in_fmol_s"), (ka, "k_in_fmol_s")):
                inward = rate[key]
                cell[species, i] += inward
                if p["reservoir"][o]:
                    supply[species, o] += inward
                else:
                    outside[species, o] -= inward
        for edge_id, edge in enumerate(m["surface_edges"]):
            i, j = patches.index(edge["sender"]), patches.index(edge["receiver"])
            flow = (
                pump["diffusivity_um2_per_s"]
                * edge["width_um"]
                / edge["distance_um"]
                * (density[k, i] - density[k, j])
            )
            result["pump_surface_transferred"][k, edge_id] = flow
            result["pump_surface_amount_increment"][k, i] -= flow
            result["pump_surface_amount_increment"][k, j] += flow
            if flow != 0:
                result["pump_surface_dissipated_energy_pJ"][k, edge_id] = (
                    1e-3 * R * m["temperature_K"] * flow * math.log(density[k, i] / density[k, j])
                )
    matrix, active, reservoir, _, floating, _ = electrical.topology(raw)
    pins = ~active | reservoir
    for members in floating:
        pins[members[0]] = True
    free = np.flatnonzero(~pins)
    charge = 1e-15 * F * (np.asarray(p["valence"]).T @ np.c_[cell, outside])[0]
    velocity = np.zeros_like(phi)
    velocity[free] = np.linalg.solve(matrix[np.ix_(free, free)], charge[free])
    np.testing.assert_allclose(
        (matrix @ velocity)[active & ~reservoir],
        charge[active & ~reservoir],
        rtol=2e-12,
        atol=2e-23,
    )
    electrode = np.where(p["reservoir"], (matrix @ velocity)[n:], 0.0)
    mu = R * p["temperature"] * np.log(raw["co"]) + F * np.asarray(p["valence"]) * phi[n:]
    result.update(
        amount_increment=cell,
        extracellular_amount_increment=outside,
        reservoir_supplied=supply,
        electrode_charge_transferred_C=electrode,
        reservoir_work_pJ=1e-3 * np.sum(mu * supply, axis=0),
        electrode_work_pJ=1e12 * phi[n:] * electrode,
    )
    return flatten(c, result), phi, proof


def integrate(raw, *, refinement=1):
    c = bind(raw)
    e = raw["experiment"]
    events = sorted(
        {
            0.0,
            e["end_time"],
            *(
                v["time"]
                for key in ("membrane_controls", "junction_controls", "pump_controls")
                for group in e[key]
                for v in group["schedule"]
            ),
        }
    )
    state = initial(c)
    results = {0.0: state.copy()}
    atols = flatten(
        c,
        {
            k: np.full(shape, (1e-29 if k.endswith("_C") else 2e-14) / refinement)
            for k, shape in c["shapes"].items()
        },
    )
    evaluations = 0
    for left, right in zip(events, events[1:], strict=False):
        sol = solve_ivp(
            lambda t, y, held=left: evaluate(c, y, held)[0],
            (left, right),
            state,
            method="DOP853",
            rtol=2e-11 / refinement,
            atol=atols,
            max_step=raw["execution"]["dt"] / (2 * refinement),
            dense_output=True,
        )
        assert sol.success, sol.message
        evaluations += sol.nfev
        for t in e["observation_times"]:
            if left < t <= right:
                results[t] = sol.sol(t)
        state = sol.y[:, -1]
    return dict(
        times=e["observation_times"],
        state=np.stack([results[t] for t in e["observation_times"]]).tolist(),
        potential_V=np.stack(
            [evaluate(c, results[t], t)[1] for t in e["observation_times"]]
        ).tolist(),
        rhs_evaluations=evaluations,
        method="DOP853; independent Decimal ATPase/diffusion/full-node field",
        rtol=2e-11 / refinement,
        amount_energy_atol=2e-14 / refinement,
        electrode_charge_atol_C=1e-29 / refinement,
    )
