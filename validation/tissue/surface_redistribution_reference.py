"""Independent diffusion edges + full-node ionic roots + adaptive DOP853.

No production Cells/JAX imports. The earlier independent Decimal transport and
full-node field reference is reused for the ionic subproblem. Surface movement,
density-to-permeability conversion and heat are implemented here explicitly.
"""

import copy
import math

import numpy as np
from scipy.integrate import solve_ivp

from validation.tissue import surface_dynamics_reference as ionic


def bind(raw):
    base = ionic.bind(raw)
    m = raw["model"]
    k, n, e = len(m["mobile_populations"]), len(m["membranes"]), len(m["surface_edges"])
    return dict(
        ionic=base,
        raw=copy.deepcopy(raw),
        shapes=base["shapes"]
        | dict(
            surface_amount_increment=(k, n),
            surface_transferred=(k, e),
            surface_dissipated_energy_pJ=(k, e),
        ),
    )


initial, unpack, flatten = ionic.initial, ionic.unpack, ionic.flatten


def evaluate(c, state, time):
    m, values = c["raw"]["model"], unpack(c, state)
    ids = [p["id"] for p in m["membranes"]]
    ions = [s["id"] for s in m["species"]]
    populations = m["mobile_populations"]
    density = np.zeros_like(values["surface_amount_increment"])
    permeability = np.asarray(c["ionic"]["layout"]["membrane_permeability"]).copy()
    for k, p in enumerate(populations):
        for j, patch in enumerate(m["membranes"]):
            amount = (
                p["initial_amount_fmol"][patch["id"]] + values["surface_amount_increment"][k, j]
            )
            density[k, j] = amount / (patch["area_m2"] * 1e12)
            for s, ion in enumerate(ions):
                permeability[s, j] += (
                    p["permeability_at_reference_density_m_per_s"][ion]
                    * density[k, j]
                    / p["reference_density_fmol_per_um2"]
                )
    ic = c["ionic"] | dict(layout=c["ionic"]["layout"] | dict(membrane_permeability=permeability))
    rate, phi, proof = ionic.evaluate(ic, flatten(ic, values), time)
    result = unpack(ic, rate)
    delta = np.zeros_like(density)
    transfer = np.zeros(c["shapes"]["surface_transferred"])
    heat = np.zeros_like(transfer)
    for k, p in enumerate(populations):
        for e, edge in enumerate(m["surface_edges"]):
            i, j = ids.index(edge["sender"]), ids.index(edge["receiver"])
            flow = (
                p["diffusivity_um2_per_s"]
                * edge["width_um"]
                / edge["distance_um"]
                * (density[k, i] - density[k, j])
            )
            transfer[k, e] = flow
            delta[k, i] -= flow
            delta[k, j] += flow
            if flow != 0:
                heat[k, e] = (
                    1e-3
                    * ionic.R
                    * m["temperature_K"]
                    * flow
                    * math.log(density[k, i] / density[k, j])
                )
    result.update(
        surface_amount_increment=delta,
        surface_transferred=transfer,
        surface_dissipated_energy_pJ=heat,
    )
    return flatten(c, result), phi, proof


def integrate(raw, *, refinement=1):
    c = bind(raw)
    experiment = raw["experiment"]
    times = experiment["observation_times"]
    events = sorted(
        {
            0.0,
            experiment["end_time"],
            *(
                v["time"]
                for kind in ("membrane", "junction")
                for group in experiment[kind + "_controls"]
                for v in group["schedule"]
            ),
        }
    )
    state, evaluations = initial(c), 0
    result = {0.0: state.copy()}
    atols = flatten(
        c,
        {
            k: np.full(shape, (1e-29 if k.endswith("_C") else 2e-14) / refinement)
            for k, shape in c["shapes"].items()
        },
    )
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
        for t in times:
            if left < t <= right:
                result[t] = sol.sol(t)
        state = sol.y[:, -1]
    return dict(
        times=times,
        state=np.stack([result[t] for t in times]).tolist(),
        potential_V=np.stack([evaluate(c, result[t], t)[1] for t in times]).tolist(),
        rhs_evaluations=evaluations,
        method="DOP853; independent diffusion and full-node/Decimal ionic reference",
        rtol=2e-11 / refinement,
        amount_energy_atol=2e-14 / refinement,
        electrode_charge_atol_C=1e-29 / refinement,
    )
