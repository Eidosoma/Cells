"""Independent channel-state transport added to scalar calcium/ER/injury equations.

No Cells or JAX imports. Explicit owner loops update K and the free-cytosol
inventory once. Decimal Kv1.5 kinetics and independent GHK flux supply rates.
"""

import math
from copy import deepcopy
from decimal import localcontext

import numpy as np
from scipy.integrate import solve_ivp

from validation.tissue import kv1_reference
from validation.tissue import surface_mobile_channel_reference as joint
from validation.tissue import surface_repair_reference as prior

flatten, unpack = prior.flatten, prior.unpack
F, R = prior.base.F, prior.base.R


def bind(raw):
    base = deepcopy(raw)
    pops, edges = base["model"].pop("mobile_channels"), base["model"].pop("surface_edges")
    controls = base["experiment"].pop("mobile_channel_controls")
    base["model"]["id"] = "resolved_repair@1"
    c = prior.bind(base)
    k, n, e = len(pops), len(base["model"]["ionic"]["membranes"]), len(edges)
    c.update(
        mobile_channels=pops,
        surface_edges=edges,
        mobile_controls=controls,
        mobile_full=deepcopy(raw),
    )
    c["shapes"].update(
        channel_state_amount_increment=(k, 4, n),
        channel_state_transferred=(k, 4, e),
        channel_state_dissipated_energy_pJ=(k, 4, e),
        channel_gate_transferred=(k, 4, n),
        channel_gate_dissipated_energy_pJ=(k, 4, n),
        channel_gate_bias_work_pJ=(k, 4, n),
        mobile_channel_transferred=(k, n),
        mobile_channel_dissipated_energy_pJ=(k, n),
    )
    return c


def initial(c):
    return prior.initial(c)


def evaluate(c, state, time, *, channel_levels=None):
    slope, phi, proof = prior.evaluate(c, state, time, channel_levels=channel_levels)
    result, d, p = unpack(c, slope), unpack(c, state), c["layout"]
    m = c["raw"]["model"]
    patches = [v["id"] for v in m["membranes"]]
    ions = [s["id"] for s in m["species"]]
    potassium = ions.index("K")
    amount = (
        np.asarray(
            [
                [
                    [pop["initial_state_amount_fmol"][s][patch] for patch in patches]
                    for s in joint.STATES
                ]
                for pop in c["mobile_channels"]
            ]
        )
        + d["channel_state_amount_increment"]
    )
    density = amount / (np.asarray(p["membrane_area"]) * 1e12)
    physical_balance = 0.0
    for k, pop in enumerate(c["mobile_channels"]):
        for e, edge in enumerate(c["surface_edges"]):
            a, b = patches.index(edge["sender"]), patches.index(edge["receiver"])
            for q in range(4):
                flow = (
                    pop["diffusivity_um2_per_s"]
                    * edge["width_um"]
                    / edge["distance_um"]
                    * (density[k, q, a] - density[k, q, b])
                )
                result["channel_state_amount_increment"][k, q, a] -= flow
                result["channel_state_amount_increment"][k, q, b] += flow
                result["channel_state_transferred"][k, q, e] = flow
                if flow:
                    result["channel_state_dissipated_energy_pJ"][k, q, e] = (
                        1e-3
                        * R
                        * p["temperature"]
                        * flow
                        * math.log(density[k, q, a] / density[k, q, b])
                    )
        for j, patch in enumerate(m["membranes"]):
            i, o = p["membrane_cell"][j], p["membrane_outside"][j]
            vm = phi[i] - phi[len(c["vi"]) + o]
            if amount[k, :, j].sum() == 0:
                continue
            if pop["gate_mode"] == "dynamic":
                with localcontext() as context:
                    context.prec = 80
                    target, tau = kv1_reference.kinetics(float(vm), 5)
                    alpha = [float(t / s) for t, s in zip(target, tau, strict=True)]
                    beta = [float((1 - t) / s) for t, s in zip(target, tau, strict=True)]
                for edge, (a, b, gate) in enumerate(joint.TRANSITIONS):
                    forward, reverse = alpha[gate] * amount[k, a, j], beta[gate] * amount[k, b, j]
                    flow = forward - reverse
                    result["channel_state_amount_increment"][k, a, j] -= flow
                    result["channel_state_amount_increment"][k, b, j] += flow
                    result["channel_gate_transferred"][k, edge, j] = flow
                    result["channel_gate_dissipated_energy_pJ"][k, edge, j] = (
                        1e-3 * R * p["temperature"] * flow * math.log(forward / reverse)
                    )
                    result["channel_gate_bias_work_pJ"][k, edge, j] = (
                        1e-3 * R * p["temperature"] * flow * math.log(alpha[gate] / beta[gate])
                    )
            controls = next(
                row["schedule"]
                for row in c["mobile_controls"]
                if row["channel_id"] == pop["id"] and row["membrane_id"] == patch["id"]
            )
            availability = next(v["availability"] for v in reversed(controls) if v["time"] <= time)
            if channel_levels is not None:
                availability *= channel_levels[i]
            permeability = (
                pop["permeability_at_reference_density_m_per_s"]
                * density[k, 3, j]
                / pop["reference_density_fmol_per_um2"]
                * availability
            )
            store = c["stores"][i]
            index = store.ids.index("K")
            ci = (store.n0 + d["chemical_amount_increment"][i])[index, store.cy] / c["vi"][i]
            co = (c["ao"][potassium, o] + d["extracellular_amount_increment"][potassium, o]) / c[
                "vo"
            ][o]
            flux = prior.base.kinetic.transport.decimal_flux(
                float(ci),
                float(co),
                float(vm),
                1,
                p["temperature"],
                p["membrane_area"][j],
                permeability,
                1.0,
                1.0,
                dict(F=F, R=R),
            )
            chemical_drop = R * p["temperature"] * math.log(ci / co)
            heat = 1e-3 * flux * (chemical_drop + F * vm)
            result["amount_increment"][potassium, i] -= flux
            result["extracellular_amount_increment"][potassium, o] += flux
            result["chemical_amount_increment"][i, index, store.cy] -= flux
            result["mobile_channel_transferred"][k, j] = flux
            result["mobile_channel_dissipated_energy_pJ"][k, j] = heat
            physical_balance += -1e-3 * flux * (chemical_drop + F * vm) + heat
    return (
        flatten(c, result),
        phi,
        proof
        | dict(
            mobile_channel_energy_balance_pJ_s=physical_balance,
            physical_energy_balance_pJ_s=proof["physical_energy_balance_pJ_s"] + physical_balance,
        ),
    )


def integrate(raw, *, refinement=1, channel_segments=None):
    c = bind(raw)
    e = raw["experiment"]
    segments = channel_segments or [(0.0, None)]
    events = {0.0, e["end_time"], *(time for time, _ in segments)}
    for kind, rows in e.items():
        if kind.endswith("_controls"):
            for row in rows:
                events.update(v["time"] for v in row.get("schedule", row.get("controls", [])))
    state = initial(c)
    saved, evaluations = {0.0: state.copy()}, 0
    atols = flatten(
        c,
        {
            k: np.full(shape, (5e-32 if k.endswith("_C") else 1e-16) / refinement)
            for k, shape in c["shapes"].items()
        },
    )
    for left, right in zip(sorted(events), sorted(events)[1:], strict=False):
        levels = next(level for time, level in reversed(segments) if time <= left)
        solution = solve_ivp(
            lambda t, y, held=left, opened=levels: evaluate(c, y, held, channel_levels=opened)[0],
            (left, right),
            state,
            method="DOP853",
            rtol=1e-12 / refinement,
            atol=atols,
            max_step=2.5e-6 / refinement,
            dense_output=True,
        )
        assert solution.success, solution.message
        evaluations += solution.nfev
        for t in e["observation_times"]:
            if left < t <= right:
                saved[t] = solution.sol(t)
        state = solution.y[:, -1]
    return dict(
        times=e["observation_times"],
        state=np.stack([saved[t] for t in e["observation_times"]]),
        potential_V=np.stack(
            [
                evaluate(
                    c,
                    saved[t],
                    t,
                    channel_levels=next(level for time, level in reversed(segments) if time <= t),
                )[1]
                for t in e["observation_times"]
            ]
        ),
        evaluations=evaluations,
        method="DOP853; independent Decimal gates/GHK, calcium/ER and full-node field",
        refinement=refinement,
    )
