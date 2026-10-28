"""Independent 39-field binding plus a Decimal prescribed-repair clock oracle.

The stage assembly reuses independent scalar chemistry/electrical/injury
references. This module imports no production Cells equations or integrators.
The long scalar clocks do not extend the short coupled fixture's claim scope.
"""

from copy import deepcopy
from decimal import Decimal, localcontext

import numpy as np
from scipy.integrate import solve_ivp

from validation.tissue import surface_calcium_reference as base
from validation.tissue import surface_repair_reference as repair

flatten, unpack = base.flatten, base.unpack
initial, evaluate = repair.initial, repair.evaluate


def bind(raw):
    if raw["model"]["id"] != "resolved_repair@4":
        raise ValueError("Require the versioned 53-law prescribed repair definition")
    prior = deepcopy(raw)
    patches = prior["model"].pop("injury_patches")
    controls = prior["experiment"].pop("injury_controls")
    prior["model"]["id"] = "resolved_calcium@10"
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


def clock(damage, hazard, closure, elapsed):
    """Exact damage and opened/closed increments for one held-control segment."""
    with localcontext() as context:
        context.prec = 80
        d, a, b, t = (Decimal(str(v)) for v in (damage, hazard, closure, elapsed))
        if not (0 <= d <= 1 and a >= 0 and b >= 0 and t >= 0):
            raise ValueError("Require bounded damage and nonnegative finite rates/time")
        rate = a + b
        if not rate:
            return float(d), 0.0, 0.0
        equilibrium = a / rate
        decay = (-rate * t).exp()
        integral = equilibrium * t + (d - equilibrium) * (1 - decay) / rate
        result = equilibrium + (d - equilibrium) * decay
        return float(result), float(a * (t - integral)), float(b * integral)


def integrate(raw, *, channel_segments=None, rtol=1e-12, atol=1e-16, charge_atol=5e-32):
    """Established adaptive algorithm, binding @4 without changing old references."""
    c = bind(raw)
    e = raw["experiment"]
    segments = channel_segments or [(0.0, None)]
    events = {0.0, e["end_time"], *(t for t, _ in segments)}
    for kind, rows in e.items():
        if kind.endswith("_controls"):
            for row in rows:
                events.update(p["time"] for p in row.get("schedule", row.get("controls", [])))
    state = initial(c)
    saved, evaluations = {0.0: state.copy()}, 0
    atols = flatten(
        c,
        {
            k: np.full(shape, charge_atol if k.endswith("_C") else atol)
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
        charge_atol=charge_atol,
    )
