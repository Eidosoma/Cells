"""Independent saved-data gate arithmetic: SI Decimal laws and affine-map powers.

No original comparator, simulator, NumPy, or JAX dependency. RK4 coefficients
are obtained from four explicit stages, not the captured decay polynomial.
"""

import math
from collections import Counter
from decimal import Decimal, localcontext

COUNTS = {
    "kinetics": 208,
    "native_equilibrium_init": 26,
    "rk4_one_step": 78,
    "discrete": 5952,
    "continuous": 1984,
    "open": 2976,
    "refinement": 36,
    "equal_initial_open": 6,
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value):
    return type(value) in (float, int) and math.isfinite(value)


def kinetics(voltage):
    v = Decimal(str(voltage))
    activation = ((v + Decimal("0.006")) / Decimal("0.0064")).exp()
    inactivation = (-(v + Decimal("0.0253")) / Decimal("0.0035")).exp()
    target = (activation / (1 + activation), inactivation / (1 + inactivation))
    tau = (Decimal("0.008330") - Decimal("0.1163") * v, Decimal("1.620") - Decimal("15.500") * v)
    require(all(t > 0 for t in tau), "Nonpositive independent time constant")
    return target, tau


def single_step(q, target, tau, dt, engine):
    if engine == "betse":
        return (q + (dt / tau) * target) / (1 + dt / tau)
    require(engine == "cells", "Unknown independent integrator")
    k1 = (target - q) / tau
    k2 = (target - (q + dt * k1 / 2)) / tau
    k3 = (target - (q + dt * k2 / 2)) / tau
    k4 = (target - (q + dt * k3)) / tau
    return q + dt * (k1 + 2 * k2 + 2 * k3 + k4) / 6


def affine_power(q, target, tau, dt, count, engine):
    """Compose the independent one-step affine map by binary exponentiation."""
    b = single_step(Decimal(0), target, tau, dt, engine)
    a = single_step(Decimal(1), target, tau, dt, engine) - b
    while count:
        if count & 1:
            q = a * q + b
        a, b = a * a, a * b + b
        count //= 2
    return q


def timeline(case):
    times, events, offset = [0], [], 0
    for segment in case["segments"]:
        events.append((offset, segment["voltage_V"]))
        samples = segment["duration_us"] // segment["sample_every_us"]
        times += [offset + n * segment["sample_every_us"] for n in range(1, samples + 1)]
        offset += segment["duration_us"]
    event = 0
    voltages = []
    for t in times:
        while event + 1 < len(events) and events[event + 1][0] <= t:
            event += 1
        voltages.append(events[event][1])
    return times, voltages


def history(case, step_us, engine):
    state = tuple(Decimal(str(q)) for q in case["initial_gate"])
    rows = [list(map(float, state))]
    dt = Decimal(step_us) * Decimal("0.000001")
    for segment in case["segments"]:
        anchor = state
        target, tau = kinetics(segment["voltage_V"])
        count = segment["duration_us"] // segment["sample_every_us"]
        for index in range(1, count + 1):
            elapsed_us = index * segment["sample_every_us"]
            if engine == "continuous":
                elapsed = Decimal(elapsed_us) * Decimal("0.000001")
                state = tuple(
                    q + (old - q) * (-elapsed / t).exp()
                    for old, q, t in zip(anchor, target, tau, strict=True)
                )
            else:
                require(elapsed_us % step_us == 0, "Off-grid independent sample")
                state = tuple(
                    affine_power(old, q, t, dt, elapsed_us // step_us, engine)
                    for old, q, t in zip(anchor, target, tau, strict=True)
                )
            rows.append(list(map(float, state)))
    return rows


def build_reference(protocol, precision=80):
    with localcontext() as context:
        context.prec = precision
        statics = [kinetics(v) for v in protocol["voltages_V"]]
        start = tuple(Decimal(str(q)) for q in protocol["one_step_initial_gate"])
        one_step = [
            [
                float(single_step(q, target[g], tau[g], Decimal("0.001"), "cells"))
                for g, q in enumerate(start)
            ]
            for target, tau in statics
        ]
        discrete = {
            f"{engine}/{case['id']}/{dt}": history(case, dt, engine)
            for engine in ("betse", "cells")
            for case in protocol["cases"]
            for dt in protocol["step_us"]
        }
        continuous = {case["id"]: history(case, 1, "continuous") for case in protocol["cases"]}
        return {
            "statics": [
                ([float(q) for q in target], [float(t) for t in tau]) for target, tau in statics
            ],
            "one_step": one_step,
            "discrete": discrete,
            "continuous": continuous,
            "timelines": {case["id"]: timeline(case) for case in protocol["cases"]},
        }


def review(protocol, native, cells, reference):
    """Independently enumerate every original numerical check and diagnostic."""
    lim = protocol["limits"]
    rows, errors, refinement, hidden = {}, {}, [], {}

    def add(label, actual, expected, atol, rtol=0):
        require(label not in rows, "Duplicate independent comparison")
        require(finite(actual) and finite(expected), f"Nonfinite value: {label}")
        error = abs(actual - expected) / (atol + rtol * abs(expected))
        rows[label] = {
            "id": label,
            "actual": actual,
            "expected": expected,
            "normalized_error": error,
            "pass": error <= 1,
        }

    require(
        set(cells["kinetics"]) == set(cells["one_step"]) == {"numpy", "jax_eager", "jax_jit"},
        "Independent backend coverage differs",
    )
    for name, data in [("betse", native["kinetics"]), *cells["kinetics"].items()]:
        require(set(data) == {"target", "tau_s"}, "Unexpected kinetic fields")
        for field, axis, atol in (
            ("target", 0, lim["kinetic_gate_atol"]),
            ("tau_s", 1, lim["kinetic_tau_s_atol"]),
        ):
            require(len(data[field]) == 13, "Wrong static voltage count")
            for i, actual in enumerate(data[field]):
                require(len(actual) == 2, "Wrong static gate axis")
                for g, value in enumerate(actual):
                    add(
                        f"kinetics/{name}/{i}/{field}/{g}",
                        value,
                        reference["statics"][i][axis][g],
                        atol,
                        lim["kinetic_rtol"],
                    )
    require(len(native["equilibrium_initial_gate"]) == 13, "Wrong initialization count")
    for i, state in enumerate(native["equilibrium_initial_gate"]):
        require(len(state) == 2, "Wrong initial gate axis")
        for g, q in enumerate(state):
            add(
                f"native_equilibrium_init/{i}/{g}",
                q,
                reference["statics"][i][0][g],
                lim["kinetic_gate_atol"],
                lim["kinetic_rtol"],
            )
    for backend, data in cells["one_step"].items():
        require(len(data) == 13, "Wrong one-step voltage count")
        for i, state in enumerate(data):
            require(len(state) == 2, "Wrong one-step gate axis")
            for g, q in enumerate(state):
                add(
                    f"rk4_one_step/{backend}/{i}/{g}",
                    q,
                    reference["one_step"][i][g],
                    lim["discrete_gate_atol"],
                    lim["discrete_gate_rtol"],
                )

    keys = {f"{case['id']}/{dt}" for case in protocol["cases"] for dt in protocol["step_us"]}
    for engine, data in (("betse", native), ("cells", cells)):
        require(set(data["trajectories"]) == keys, "Independent trajectory coverage differs")
        for case in protocol["cases"]:
            exact = reference["continuous"][case["id"]]
            times, voltages = reference["timelines"][case["id"]]
            level_errors = []
            for dt in protocol["step_us"]:
                name = f"{case['id']}/{dt}"
                trace = data["trajectories"][name]
                require(
                    set(trace)
                    == {
                        "time_us",
                        "voltage_V",
                        "gate",
                        "open_fraction",
                        "steps",
                        "all_steps_valid",
                        "input_unchanged",
                    },
                    "Wrong trace fields",
                )
                require(
                    trace["time_us"] == times
                    and all(type(t) is int for t in trace["time_us"])
                    and trace["voltage_V"] == voltages
                    and all(finite(v) for v in trace["voltage_V"]),
                    "Independent event clock differs",
                )
                require(
                    type(trace["steps"]) is int and trace["steps"] == times[-1] // dt,
                    "Wrong update count",
                )
                require(
                    trace["all_steps_valid"] is True and trace["input_unchanged"] is True,
                    "Rejected stage/input evidence",
                )
                require(
                    len(trace["gate"]) == len(trace["open_fraction"]) == len(times),
                    "Wrong independent observation count",
                )
                require(trace["gate"][0] == case["initial_gate"], "Wrong fixture state")
                expected = reference["discrete"][f"{engine}/{name}"]
                for i, state in enumerate(trace["gate"]):
                    require(
                        len(state) == 2 and all(finite(q) and 0 <= q <= 1 for q in state),
                        "Invalid recorded gate",
                    )
                    for g, q in enumerate(state):
                        add(
                            f"discrete/{engine}/{name}/{i}/{g}",
                            q,
                            expected[i][g],
                            lim["discrete_gate_atol"],
                            lim["discrete_gate_rtol"],
                        )
                        if dt == protocol["step_us"][-1]:
                            bound = lim[
                                "native_finest_continuous_gate_atol"
                                if engine == "betse"
                                else "cells_finest_continuous_gate_atol"
                            ]
                            add(f"continuous/{engine}/{name}/{i}/{g}", q, exact[i][g], bound)
                    opened = trace["open_fraction"][i]
                    require(finite(opened) and 0 <= opened <= 1, "Invalid open fraction")
                    add(
                        f"open/{engine}/{name}/{i}",
                        opened,
                        state[0] * state[1],
                        lim["kinetic_gate_atol"],
                        lim["kinetic_rtol"],
                    )
                level_errors.append(
                    [
                        max(
                            abs(state[g] - target[g])
                            for state, target in zip(trace["gate"], exact, strict=True)
                        )
                        for g in range(2)
                    ]
                )
            errors[f"{engine}/{case['id']}"] = level_errors
            bounds = lim["native_error_ratio" if engine == "betse" else "cells_error_ratio"]
            for g in range(2):
                for level in range(2):
                    a, b = level_errors[level][g], level_errors[level + 1][g]
                    label = f"refinement/{engine}/{case['id']}/{g}/{level}"
                    if (
                        a > lim["refinement_roundoff_floor"]
                        and b > lim["refinement_roundoff_floor"]
                    ):
                        ratio = b / a
                        add(label, ratio, sum(bounds) / 2, (bounds[1] - bounds[0]) / 2)
                        refinement.append({"id": label, "status": "measured", "ratio": ratio})
                    else:
                        refinement.append(
                            {
                                "id": label,
                                "status": "roundoff_limited",
                                "coarse_error": a,
                                "fine_error": b,
                            }
                        )
        for dt in protocol["step_us"]:
            left = data["trajectories"][f"history_low_m/{dt}"]
            right = data["trajectories"][f"history_high_m/{dt}"]
            add(
                f"equal_initial_open/{engine}/{dt}",
                left["open_fraction"][0],
                right["open_fraction"][0],
                lim["kinetic_gate_atol"],
            )
            separation = max(
                abs(a - b) for a, b in zip(left["gate"][-1], right["gate"][-1], strict=True)
            )
            require(separation >= lim["minimum_history_gate_separation"], "Gate history collapsed")
            hidden[f"{engine}/{dt}"] = separation
    require(
        any(r["status"] == "measured" and "/cells/activation/0/" in r["id"] for r in refinement),
        "No resolved RK4 refinement",
    )
    differences = {
        key: [
            max(
                abs(a[g] - b[g])
                for a, b in zip(
                    native["trajectories"][key]["gate"],
                    cells["trajectories"][key]["gate"],
                    strict=True,
                )
            )
            for g in range(2)
        ]
        for key in sorted(keys)
    }
    return {
        "rows": rows,
        "continuous_max_gate_errors": errors,
        "refinement": refinement,
        "cross_engine_max_gate_differences": differences,
        "hidden_gate_separation": hidden,
    }


def match_saved(independent, saved):
    rows = independent["rows"]
    require(
        Counter(label.split("/")[0] for label in rows) == COUNTS, "Independent coverage differs"
    )
    require(
        len(saved["comparisons"]) == len(rows) == saved["comparison_count"] == 11266,
        "Saved comparison count differs",
    )
    original = {r["id"]: r for r in saved["comparisons"]}
    require(
        len(original) == len(saved["comparisons"]) and original == rows,
        "Independent arithmetic or full-row evidence differs",
    )
    require(all(r["pass"] for r in rows.values()), "Independent physical criterion rejected")
    require(saved["status"] == "pass" and saved["failed_comparisons"] == 0, "Saved verdict differs")
    require(
        saved["maximum_normalized_error"] == max(r["normalized_error"] for r in rows.values()),
        "Saved error maximum differs",
    )
    for field in ("continuous_max_gate_errors", "cross_engine_max_gate_differences"):
        require(independent[field] == saved[field], f"Independent {field} differs")
    require(
        sorted(independent["refinement"], key=lambda r: r["id"])
        == sorted(saved["refinement"], key=lambda r: r["id"]),
        "Refinement diagnostics differ",
    )
    require(
        Counter(r["status"] for r in independent["refinement"])
        == {"measured": 36, "roundoff_limited": 12},
        "Refinement scope differs",
    )
    return {
        "independent_comparisons": len(rows),
        "failed_comparisons": 0,
        "comparison_groups": COUNTS,
        "measured_refinements": 36,
        "roundoff_limited": 12,
        "hidden_history_checks": len(independent["hidden_gate_separation"]),
        "native_finest_max_gate_error": max(
            max(v[-1])
            for k, v in independent["continuous_max_gate_errors"].items()
            if k.startswith("betse/")
        ),
        "cells_finest_max_gate_error": max(
            max(v[-1])
            for k, v in independent["continuous_max_gate_errors"].items()
            if k.startswith("cells/")
        ),
    }
