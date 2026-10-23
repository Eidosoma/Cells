"""Independent scalar injury/flux assembly and segmented adaptive reference.

Reuses the independent full-node electrical and chemistry reference, never
production Cells, JAX, the injury RHS, scatter, or fixed-step integrator.
"""

import math
from copy import deepcopy

import numpy as np
from scipy.integrate import solve_ivp

from validation.tissue import surface_calcium_reference as base

flatten, unpack = base.flatten, base.unpack


def bind(raw):
    prior = deepcopy(raw)
    patches = prior["model"].pop("injury_patches")
    controls = prior["experiment"].pop("injury_controls")
    prior["model"]["id"] = "resolved_calcium@6"
    c = base.bind(prior)
    mids = [p["id"] for p in prior["model"]["ionic"]["membranes"]]
    c["injury"] = [next(p for p in patches if p["membrane_id"] == k) for k in mids]
    c["injury_controls"] = [
        next(p["schedule"] for p in controls if p["membrane_id"] == k) for k in mids
    ]
    c["injury_full"] = deepcopy(raw)
    nm, ns = len(mids), len(prior["model"]["ionic"]["species"])
    c["shapes"].update(
        damage=(nm,),
        damage_opened=(nm,),
        damage_closed=(nm,),
        injury_transferred=(ns, nm),
        injury_dissipated_energy_pJ=(ns, nm),
    )
    return c


def initial(c):
    state = unpack(c, base.initial(c))
    state["damage"] = np.array([p["initial_damage"] for p in c["injury"]])
    return flatten(c, state)


def analytic_damage(damage, hazard, closure, elapsed):
    rate = hazard + closure
    return (
        damage
        if rate == 0
        else damage * math.exp(-rate * elapsed) - hazard / rate * math.expm1(-rate * elapsed)
    )


def evaluate(c, state, time):
    slope, phi, proof = base.evaluate(c, state, time)
    result, d, p = unpack(c, slope), unpack(c, state), c["layout"]
    species = c["raw"]["model"]["species"]
    rt = base.R * p["temperature"]
    chemical, electric, heat_total = 0.0, 0.0, 0.0
    for j, patch in enumerate(c["injury"]):
        held = next(v for v in reversed(c["injury_controls"][j]) if v["time"] <= time)
        damage = d["damage"][j]
        opened = patch["injury_rate_per_s"] * held["injury"] * (1 - damage)
        closed = patch["resealing_rate_per_s"] * held["resealing"] * damage
        result["damage"][j], result["damage_opened"][j], result["damage_closed"][j] = (
            opened - closed,
            opened,
            closed,
        )
        i, o = p["membrane_cell"][j], p["membrane_outside"][j]
        store = c["stores"][i]
        vm = phi[i] - phi[len(c["vi"]) + o]
        for s, ion in enumerate(species):
            permeability = patch["permeability_m_per_s"][ion["id"]]
            if not permeability:
                continue
            chemical_index = store.ids.index(ion["id"])
            ci = (store.n0 + d["chemical_amount_increment"][i])[chemical_index, store.cy] / c["vi"][
                i
            ]
            co = (c["ao"][s, o] + d["extracellular_amount_increment"][s, o]) / c["vo"][o]
            x = ion["valence"] * base.F * vm / rt
            flux = (
                p["membrane_area"][j]
                * permeability
                * damage
                / 1e-15
                * (ci - co if x == 0 else x * (ci - co * math.exp(-x)) / -math.expm1(-x))
            )
            heat = 1e-3 * flux * (rt * math.log(ci / co) + ion["valence"] * base.F * vm)
            result["amount_increment"][s, i] -= flux
            result["extracellular_amount_increment"][s, o] += flux
            result["chemical_amount_increment"][i, chemical_index, store.cy] -= flux
            result["injury_transferred"][s, j] = flux
            result["injury_dissipated_energy_pJ"][s, j] = heat
            chemical -= 1e-3 * flux * rt * math.log(ci / co)
            electric -= 1e-3 * flux * ion["valence"] * base.F * vm
            heat_total += heat
    return (
        flatten(c, result),
        phi,
        proof
        | dict(
            injury_energy_balance_pJ_s=chemical + electric + heat_total,
            physical_energy_balance_pJ_s=proof["physical_energy_balance_pJ_s"]
            + chemical
            + electric
            + heat_total,
        ),
    )


def integrate(raw, *, rtol=1e-12, atol=1e-16):
    c = bind(raw)
    e = raw["experiment"]
    events = {0.0, e["end_time"]}
    for kind, rows in e.items():
        if kind.endswith("_controls"):
            for row in rows:
                events.update(p["time"] for p in row.get("schedule", row.get("controls", [])))
    state = initial(c)
    saved, evaluations = {0.0: state.copy()}, 0
    atols = flatten(
        c,
        {
            k: np.full(shape, 5e-32 if k.endswith("_C") else atol)
            for k, shape in c["shapes"].items()
        },
    )
    for left, right in zip(sorted(events), sorted(events)[1:], strict=False):
        solution = solve_ivp(
            lambda t, y, held=left: evaluate(c, y, held)[0],
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
        method="segmented DOP853 with independent full-node roots and scalar injury/flux",
        rtol=rtol,
        atol=atol,
    )
