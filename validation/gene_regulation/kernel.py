"""templated_polymerisation@1 on its own half-steps in NumPy, for the tests (G4): a world of
worlds.py advanced without compiling it, two half-steps of dt/2 per step as the composite's split
step takes them. Every row the operator lists is impermeant and its world has no channel, so the
inner step leaves them and the operator's fields unchanged: these half-steps are the world's
dynamics for them. Development, not judged.
"""

import copy
import math
from types import SimpleNamespace

import numpy as np

from cells.definitions.specs import parse_spec
from cells.operators import OPERATORS
from cells.operators import templated_polymerisation as polymerisation
from cells.registry.models import get_model
from validation.gene_regulation import worlds

OP = OPERATORS[worlds.POLYMERISATION]


def block(raw):
    """The operator's raw declaration in a world's definition."""
    (out,) = [o for o in raw["model"]["operators"] if o["law"] == worlds.POLYMERISATION]
    return out


def truncated(raw, end):
    """raw with its horizon cut to `end`, keeping the outputs up to it and ending on one."""
    out = copy.deepcopy(raw)
    e, x = out["experiment"], out["execution"]
    e["end_time"] = float(end)
    e["observation_times"] = [t for t in e["observation_times"] if t < end - 1e-9] + [float(end)]
    x["max_steps"] = int(math.ceil(end / x["dt"])) + 8
    return out


def controls(raw, declaration, only=None):
    """The world's rates at time 0 by route; with `only`, every other route's at zero. A release's
    durable fraction and class (the sheet's §9) are their declared or time-0 values whatever
    `only` is."""
    rate = {
        c["route_id"]: c["schedule"][0]["value"]
        for c in raw["experiment"]["polymerisation_controls"]
    }

    def values(routes):
        return np.array([rate[r.id] if only in (None, r.id) else 0.0 for r in routes])

    releases = [r for _, r in polymerisation.releases_of(declaration)]
    return SimpleNamespace(
        polymerisation_initiation_rate=values(declaration.chains),
        polymerisation_degradation_rate=values(declaration.degradations),
        polymerisation_transfer_capacity=values(declaration.transfers),
        polymerisation_release_fraction=np.array(
            [rate[r.id] if r.durable_fraction is None else r.durable_fraction for r in releases]
        ),
        polymerisation_release_class=np.array(
            [rate[r.label.id] if r.label is not None else 1.0 for r in releases]
        ),
    )


def run(raw, *, only=None, record=False):
    """(spec, layout, {step: state} at every output, per-half-step increments of the chains' and
    degradations' heats when `record`) of raw's horizon, rates held at their time-0 values."""
    spec = parse_spec(raw)
    state, p = get_model(spec.model).initial_values(spec)
    state = type(state)(*(np.asarray(v) for v in state))
    (declaration,) = [d for d in spec.model.operators if d.law == worlds.POLYMERISATION]
    control = controls(raw, declaration, only)
    dt = spec.execution.dt
    wanted = {int(round(float(t) / dt)) for t in spec.experiment.observation_times}
    steps = int(round(float(spec.experiment.end_time) / dt))
    states, increments = {0: state}, []
    for k in range(1, steps + 1):
        for _ in range(2):
            new, ok = OP.half_step(state, dt / 2, control, p, xp=np)
            if not bool(ok):
                raise RuntimeError(f"the half-step was refused at step {k}")
            if record:  # The chains', degradations' and releases' heat increments.
                increments.append(
                    np.concatenate(
                        [
                            new.poly_chain_heat_pJ - state.poly_chain_heat_pJ,
                            new.poly_degradation_heat_pJ - state.poly_degradation_heat_pJ,
                            np.ravel(new.poly_release_heat_pJ - state.poly_release_heat_pJ),
                        ]
                    )
                )
            state = new
        if k in wanted or k == steps:
            states[k] = state
    return spec, p, states, increments
