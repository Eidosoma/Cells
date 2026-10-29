"""Independent native coefficient capability plus complete coupled owner oracles."""

from copy import deepcopy

import numpy as np
from scipy.integrate import solve_ivp

from validation.tissue import surface_calcium_energy_reference as fuel
from validation.tissue import surface_calcium_reference as calcium
from validation.topology import surface_profile_interventions_reference as membrane

OWNERS = {
    "resolved_calcium_membrane_profiles@1": ("resolved_calcium@6", calcium),
    "resolved_calcium_energy_membrane_profiles@1": ("resolved_calcium_energy@5", fuel),
}
EXTRA = ("profile_preparation", "interventions", "phase", "timing_policy", "reset_policy")


def parent_definition(raw):
    result = deepcopy(raw)
    mid, process = OWNERS[result["model"]["id"]]
    for key in EXTRA:
        result["model"].pop(key)
    result["model"]["id"] = mid
    for key in ("intervention_capacity", "intervention_target_capacity"):
        result["execution"].pop(key)
    return result, process


def bind(raw):
    value, process = parent_definition(raw)
    return dict(raw=deepcopy(raw), process=process, parent=process.bind(value))


def initial(context):
    return np.r_[context["process"].initial(context["parent"]), 0.0]


def flatten(context, values):
    return np.r_[
        context["process"].flatten(context["parent"], values),
        np.asarray(values["phase_clock_s"]).ravel(),
    ]


def stage_definition(raw, time, held_time=None):
    complete, process = parent_definition(raw)
    # Only selected coefficient entries return from the native parameter view.
    # No passive field, state, control, pump parameter or free concentration is used.
    leaf = deepcopy(raw["model"]["ionic"])
    leaf.update({key: deepcopy(raw["model"][key]) for key in EXTRA})
    leaf["profile_preparation"] = {
        "provenance": raw["model"]["profile_preparation"]["provenance"][
            "direct_parameter_preparation"
        ]
    }
    proxy = dict(raw, model=leaf)
    parameters, events = membrane.permeability(proxy, time)
    coefficients = {p["id"]: p["permeability_m_per_s"] for p in parameters["model"]["membranes"]}
    for patch in complete["model"]["ionic"]["membranes"]:
        patch["permeability_m_per_s"] = coefficients[patch["id"]]
    if held_time is not None:
        for name, groups in complete["experiment"].items():
            if name.endswith("_controls"):
                for row in groups:
                    key = "controls" if "controls" in row else "schedule"
                    chosen = deepcopy(next(v for v in reversed(row[key]) if v["time"] <= held_time))
                    chosen["time"] = 0.0
                    row[key] = [chosen]
    return complete, process, events


def evaluate(context, state, *, held_time=None):
    complete, process, events = stage_definition(context["raw"], float(state[-1]), held_time)
    current = process.bind(complete)
    slope, phi, proof = process.evaluate(current, state[:-1], float(state[-1]))
    return np.r_[slope, 1.0], phi, proof | dict(native_events=events)


def integrate(raw):
    context = bind(raw)
    state = initial(context)
    times = {0.0, raw["experiment"]["end_time"]}
    for name, groups in raw["experiment"].items():
        if name.endswith("_controls"):
            for row in groups:
                key = "controls" if "controls" in row else "schedule"
                times.update(v["time"] for v in row[key])
    times = sorted(times)
    atol = np.r_[
        context["process"].flatten(
            context["parent"],
            {
                name: np.full(shape, 1e-29 if name.endswith("_C") else 2e-14)
                for name, shape in context["parent"]["shapes"].items()
            },
        ),
        1e-22,
    ]
    evaluations = 0
    for left, right in zip(times, times[1:], strict=False):
        result = solve_ivp(
            lambda t, y, held=left: evaluate(context, y, held_time=held)[0],
            (left, right),
            state,
            method="DOP853",
            rtol=2e-11,
            atol=atol,
            max_step=min(0.0625e-6, right - left),
        )
        if not result.success:
            raise RuntimeError(result.message)
        state = result.y[:, -1]
        evaluations += result.nfev
    return state, dict(
        method="DOP853, complete coupled owner, all held-control clocks",
        rhs_evaluations=evaluations,
    )
