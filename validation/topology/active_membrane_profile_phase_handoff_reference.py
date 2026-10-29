"""Independent active INIT/SIM handoff with continuous physical accounting.

The existing independent 56-law equations are unchanged. This module adds only
an explicit carried initial state, endpoint and exact held-control segments.
No production model or integration routine is imported.
"""

import hashlib
import sys
from copy import deepcopy
from pathlib import Path
from types import ModuleType

import numpy as np
from scipy.integrate import solve_ivp

from validation.topology import surface_active_profile_interventions_reference as scheduled


def target_definition(epoch):
    raw = deepcopy(epoch)
    raw["model"] = raw["model"]["scheduled"]
    return raw


def initial(request):
    context = scheduled.bind(request["simulation"])
    values = {
        name: np.asarray(row["values"]).reshape(row["shape"])
        for name, row in request["source"]["checkpoint"]["state"].items()
    }
    state = scheduled.flatten(context, values).copy()
    state[-1] = 0.0
    return context, state


def integrate(raw, *, initial_state=None, end_time=None):
    """DOP853 from an explicit phase-zero state, saving every requested sample."""
    context = scheduled.bind(raw)
    zero = scheduled.initial(context)
    state = zero.copy() if initial_state is None else np.array(initial_state, copy=True)
    end = raw["experiment"]["end_time"] if end_time is None else end_time
    if (
        state.shape != zero.shape
        or not np.isfinite(state).all()
        or state[-1] != 0.0
        or isinstance(end, bool)
        or not np.isfinite(end)
        or not 0 <= end <= raw["experiment"]["end_time"]
    ):
        raise ValueError("Require a finite complete phase-zero state and bounded endpoint")
    clocks = sorted(
        {
            0.0,
            float(end),
            *(
                value["time"]
                for kind in ("membrane", "junction", "channel", "pump")
                for row in raw["experiment"][kind + "_controls"]
                for value in row["schedule"]
                if 0 < value["time"] < end
            ),
        }
    )
    times = sorted(
        {0.0, float(end), *(t for t in raw["experiment"]["observation_times"] if 0 <= t <= end)}
    )
    saved = {0.0: state.copy()}
    atol = np.r_[
        scheduled.active.flatten(
            context["parent"],
            {
                name: np.full(shape, 1e-29 if name.endswith("_C") else 2e-14)
                for name, shape in context["parent"]["shapes"].items()
            },
        ),
        1e-22,
    ]
    evaluations = 0
    for left, right in zip(clocks[:-1], clocks[1:], strict=True):
        solution = solve_ivp(
            lambda t, y, held=left: scheduled.evaluate(context, y, held_time=held)[0],
            (left, right),
            state,
            method="DOP853",
            rtol=2e-11,
            atol=atol,
            max_step=min(0.125e-6, right - left),
            dense_output=True,
        )
        if not solution.success:
            raise RuntimeError(solution.message)
        state = solution.y[:, -1].copy()
        for time in times:
            if left < time <= right:
                saved[time] = state.copy() if time == right else solution.sol(time)
        evaluations += solution.nfev
    return state, dict(
        method="Independent 20-field DOP853 with four exact held-control families",
        rhs_evaluations=evaluations,
        end_time_s=float(end),
        control_knots_s=clocks,
        observation_times_s=times,
        observations=np.stack([saved[t] for t in times]),
        relative_tolerance=2e-11,
        amount_energy_gate_absolute_tolerance=2e-14,
        charge_absolute_tolerance_C=1e-29,
        clock_absolute_tolerance_s=1e-22,
        maximum_step_s=0.125e-6,
    )


def dependency_manifest(root):
    """Include imported oracle functions as well as modules (notably require)."""
    root = Path(root).resolve()
    pending = [sys.modules[__name__]]
    seen, result = set(), {}
    while pending:
        module = pending.pop()
        if module.__name__ in seen:
            continue
        seen.add(module.__name__)
        path = Path(module.__file__).resolve()
        with path.open("rb") as stream:
            result[str(path.relative_to(root))] = hashlib.file_digest(stream, "sha256").hexdigest()
        for value in vars(module).values():
            name = (
                value.__name__
                if isinstance(value, ModuleType)
                else getattr(value, "__module__", "")
            )
            candidate = sys.modules.get(name)
            location = getattr(candidate, "__file__", None)
            # Legacy standalone oracles import helpers under names such as
            # ``contact``. Bind their actual files, not just package prefixes.
            if location and Path(location).resolve().is_relative_to(root / "validation"):
                pending.append(candidate)
    assert "validation/betse/contact.py" in result
    return dict(sorted(result.items()))
