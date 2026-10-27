"""Independent joint-state kinetics/diffusion and Decimal/full-node ion reference.

No Cells/JAX imports. Channel and leak permeabilities are assembled explicitly
from state amounts and independent control clocks. The existing independent
pump reference owns the ion, field, boundary and ATP calculations.
"""

import copy
import math
from decimal import localcontext

import numpy as np
from scipy.integrate import solve_ivp

from validation.tissue import kv1_reference
from validation.tissue import surface_mobile_pump_reference as prior

STATES = ("m0h0", "m0h1", "m1h0", "m1h1")
TRANSITIONS = ((0, 2, 0), (1, 3, 0), (0, 1, 1), (2, 3, 1))
F, R = prior.F, prior.R
initial, flatten, unpack = prior.initial, prior.flatten, prior.unpack


def bind(raw):
    modified = copy.deepcopy(raw)
    for p in modified["model"]["mobile_populations"]:
        p["permeability_at_reference_density_m_per_s"] = {
            s: 0.0 for s in p["permeability_at_reference_density_m_per_s"]
        }
    for group in modified["experiment"]["membrane_controls"]:
        group["schedule"] = [dict(time=0.0, availability=1.0)]
    c = prior.bind(modified)
    m = raw["model"]
    k, n, e = len(m["mobile_channels"]), len(m["membranes"]), len(m["surface_edges"])
    return dict(
        prior=c,
        raw=copy.deepcopy(raw),
        shapes=c["shapes"]
        | dict(
            channel_state_amount_increment=(k, 4, n),
            channel_state_transferred=(k, 4, e),
            channel_state_dissipated_energy_pJ=(k, 4, e),
            channel_gate_transferred=(k, 4, n),
            channel_gate_dissipated_energy_pJ=(k, 4, n),
            channel_gate_bias_work_pJ=(k, 4, n),
        ),
    )


def availability(raw, kind, ident, time, *, patch=None):
    groups = raw["experiment"][kind + "_controls"]
    group = next(
        g
        for g in groups
        if g[kind + "_id"] == ident and (patch is None or g["membrane_id"] == patch)
    )
    return next(c["availability"] for c in reversed(group["schedule"]) if c["time"] <= time)


def evaluate(c, state, time):
    d, m = unpack(c, state), c["raw"]["model"]
    ions = [s["id"] for s in m["species"]]
    patches = [p["id"] for p in m["membranes"]]
    permeability = np.asarray(
        [[p["permeability_m_per_s"][s] for p in m["membranes"]] for s in ions]
    )
    amount = (
        np.asarray(
            [
                [[p["initial_state_amount_fmol"][s][patch] for patch in patches] for s in STATES]
                for p in m["mobile_channels"]
            ]
        )
        + d["channel_state_amount_increment"]
    )
    density = np.zeros_like(amount)
    for j, patch in enumerate(m["membranes"]):
        area = patch["area_m2"] * 1e12
        for k, pop in enumerate(m["mobile_populations"]):
            relative = (
                (pop["initial_amount_fmol"][patch["id"]] + d["surface_amount_increment"][k, j])
                / area
                / pop["reference_density_fmol_per_um2"]
            )
            for s, ion in enumerate(ions):
                permeability[s, j] += (
                    relative * pop["permeability_at_reference_density_m_per_s"][ion]
                )
        permeability[:, j] *= availability(c["raw"], "membrane", patch["id"], time)
        for k, pop in enumerate(m["mobile_channels"]):
            density[k, :, j] = amount[k, :, j] / area
            permeability[ions.index(pop["species_id"]), j] += (
                density[k, 3, j]
                / pop["reference_density_fmol_per_um2"]
                * pop["permeability_at_reference_density_m_per_s"]
                * availability(c["raw"], "channel", pop["id"], time, patch=patch["id"])
            )
    cp = c["prior"]
    cl = cp["prior"]
    ci = cl["ionic"]
    ci = ci | dict(layout=ci["layout"] | dict(membrane_permeability=permeability))
    cp = cp | dict(prior=cl | dict(ionic=ci))
    rate, phi, proof = prior.evaluate(cp, flatten(cp, d), time)
    result = unpack(cp, rate)
    for name, shape in c["shapes"].items():
        if name not in result:
            result[name] = np.zeros(shape)
    cell_ids = [v["id"] for v in m["cells"]]
    outside_ids = [v["id"] for v in m["extracellular"]]
    for k, pop in enumerate(m["mobile_channels"]):
        for e, edge in enumerate(m["surface_edges"]):
            i, j = patches.index(edge["sender"]), patches.index(edge["receiver"])
            for q in range(4):
                flow = (
                    pop["diffusivity_um2_per_s"]
                    * edge["width_um"]
                    / edge["distance_um"]
                    * (density[k, q, i] - density[k, q, j])
                )
                result["channel_state_transferred"][k, q, e] = flow
                result["channel_state_amount_increment"][k, q, i] -= flow
                result["channel_state_amount_increment"][k, q, j] += flow
                if flow != 0:
                    result["channel_state_dissipated_energy_pJ"][k, q, e] = (
                        1e-3
                        * R
                        * m["temperature_K"]
                        * flow
                        * math.log(density[k, q, i] / density[k, q, j])
                    )
        for j, patch in enumerate(m["membranes"]):
            if pop["gate_mode"] == "frozen" or amount[k, :, j].sum() == 0:
                continue
            voltage = (
                phi[cell_ids.index(patch["inside"])]
                - phi[len(cell_ids) + outside_ids.index(patch["outside"])]
            )
            with localcontext() as context:
                context.prec = 80
                target, tau = kv1_reference.kinetics(float(voltage), 5)
                alpha = [float(t / s) for t, s in zip(target, tau, strict=True)]
                beta = [float((1 - t) / s) for t, s in zip(target, tau, strict=True)]
            for t, (source, dest, gate) in enumerate(TRANSITIONS):
                forward = alpha[gate] * amount[k, source, j]
                backward = beta[gate] * amount[k, dest, j]
                flow = forward - backward
                result["channel_gate_transferred"][k, t, j] = flow
                result["channel_state_amount_increment"][k, source, j] -= flow
                result["channel_state_amount_increment"][k, dest, j] += flow
                result["channel_gate_dissipated_energy_pJ"][k, t, j] = (
                    1e-3 * R * m["temperature_K"] * flow * math.log(forward / backward)
                )
                result["channel_gate_bias_work_pJ"][k, t, j] = (
                    1e-3 * R * m["temperature_K"] * flow * math.log(alpha[gate] / beta[gate])
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
                for key in (
                    "membrane_controls",
                    "junction_controls",
                    "pump_controls",
                    "channel_controls",
                )
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
        method="DOP853; independent Decimal gates/ATPase, state diffusion and full-node field",
        rtol=2e-11 / refinement,
        amount_energy_atol=2e-14 / refinement,
        electrode_charge_atol_C=1e-29 / refinement,
    )
