"""Model-free, high-precision reference for a small isolated-gate contact.

This module never imports either simulator. Discrete propagation predicts each
integrator's own error; the continuous reference does not prefer either one.
"""

import importlib
import json
import math
import sys
from decimal import Decimal, localcontext
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
c = importlib.import_module("contact")
PROTOCOL = HERE / "protocol.json"
BACKENDS = ("numpy", "jax_eager", "jax_jit")


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_protocol(p):
    c.require(
        json.dumps(p, sort_keys=True, allow_nan=False)
        == json.dumps(c.read(PROTOCOL), sort_keys=True, allow_nan=False),
        "Unregistered channel protocol",
    )
    c.require(p["schema"] == "cells.betse_kv1p5_contact_protocol@1", "Wrong schema")
    c.require(p["upstream_revision"] == c.REVISION, "Wrong source revision")
    c.require(p["kinetic_law"] == "betse_kv1p5_mh@1", "Wrong channel law")
    c.require(p["fixture_temperature_K"] == 298.15, "Unspecified temperature regime")
    c.require(p["step_us"] == [1000, 500, 250], "Unregistered refinement")
    c.require(p["voltage_domain_V"] == [-0.12, 0.06], "Wrong engineering domain")
    voltages = p["voltages_V"] + [s["voltage_V"] for case in p["cases"] for s in case["segments"]]
    c.require(all(number(v) and -0.12 <= v <= 0.06 for v in voltages), "Invalid voltage")
    ids = [case["id"] for case in p["cases"]]
    c.require(len(ids) == len(set(ids)) == 6, "Wrong case coverage")
    for case in p["cases"]:
        c.require(
            len(case["initial_gate"]) == 2
            and all(number(q) and 0 <= q <= 1 for q in case["initial_gate"]),
            "Invalid initial gate",
        )
        for s in case["segments"]:
            duration, every = s["duration_us"], s["sample_every_us"]
            c.require(type(duration) is type(every) is int, "Noninteger clock")
            c.require(duration > 0 and every > 0 and duration % every == 0, "Invalid samples")
            c.require(all(every % dt == 0 for dt in p["step_us"]), "Off-grid observation")


def grid(case):
    times, volts, anchor = [0], [case["segments"][0]["voltage_V"]], 0
    for segment in case["segments"]:
        volts[-1] = segment["voltage_V"]  # Right-continuous event readout, state stays continuous.
        for delta in range(
            segment["sample_every_us"], segment["duration_us"] + 1, segment["sample_every_us"]
        ):
            times.append(anchor + delta)
            volts.append(segment["voltage_V"])
        anchor += segment["duration_us"]
    return times, volts


def kinetics_decimal(voltage):
    """Independent expressions in source mV/ms, returned in seconds."""
    v = Decimal(str(voltage)) * 1000
    target = (
        1 / (1 + (-(v + Decimal("6")) / Decimal("6.4")).exp()),
        1 / (1 + ((v + Decimal("25.3")) / Decimal("3.5")).exp()),
    )
    tau = (
        (Decimal("8.330") - Decimal("0.1163") * v) / 1000,
        (Decimal("1620") - Decimal("15.500") * v) / 1000,
    )
    return target, tau


def propagate(gate, target, tau, elapsed_us, dt_us, method):
    elapsed = Decimal(elapsed_us) / 1_000_000
    if method == "continuous":
        factors = [(-elapsed / t).exp() for t in tau]
    else:
        c.require(method in ("betse", "rk4"), "Unknown discrete reference")
        c.require(elapsed_us % dt_us == 0, "Off-grid reference time")
        steps = elapsed_us // dt_us
        x = [Decimal(dt_us) / 1_000_000 / t for t in tau]
        if method == "betse":
            factors = [(1 + value) ** (-steps) for value in x]
        else:
            factors = [(1 - v + v**2 / 2 - v**3 / 6 + v**4 / 24) ** steps for v in x]
    return tuple(qinf + (q - qinf) * f for q, qinf, f in zip(gate, target, factors, strict=True))


def reference_trace(case, dt_us, method, precision=70):
    with localcontext() as context:
        context.prec = precision
        state = tuple(Decimal(str(q)) for q in case["initial_gate"])
        gates = [[float(q) for q in state]]
        for segment in case["segments"]:
            target, tau = kinetics_decimal(segment["voltage_V"])
            anchor = state
            for elapsed in range(
                segment["sample_every_us"],
                segment["duration_us"] + 1,
                segment["sample_every_us"],
            ):
                state = propagate(anchor, target, tau, elapsed, dt_us, method)
                gates.append([float(q) for q in state])
        return gates


def validate_trace(case, dt_us, trace):
    times, volts = grid(case)
    c.require(
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
        "Unexpected trace fields",
    )
    c.require(trace["time_us"] == times and trace["voltage_V"] == volts, "Wrong event grid")
    c.require(
        all(type(t) is int for t in trace["time_us"])
        and all(number(v) for v in trace["voltage_V"]),
        "Nonnumeric event grid",
    )
    c.require(len(trace["gate"]) == len(trace["open_fraction"]) == len(times), "Truncated trace")
    c.require(
        type(trace["steps"]) is int and trace["steps"] == times[-1] // dt_us, "Wrong step count"
    )
    c.require(
        trace["all_steps_valid"] is True and trace["input_unchanged"] is True,
        "Invalid stage or changed input",
    )
    c.require(trace["gate"][0] == case["initial_gate"], "Implicit state reinitialization")
    for row, opened in zip(trace["gate"], trace["open_fraction"], strict=True):
        c.require(len(row) == 2 and all(number(q) and 0 <= q <= 1 for q in row), "Invalid gate")
        c.require(number(opened) and 0 <= opened <= 1, "Invalid open fraction")


def evaluate(protocol, native, cells):
    validate_protocol(protocol)
    limits = protocol["limits"]
    precision = limits["decimal_precision"]
    ids = [case["id"] for case in protocol["cases"]]
    keys = {f"{name}/{dt}" for name in ids for dt in protocol["step_us"]}
    c.require(
        set(native["trajectories"]) == set(cells["trajectories"]) == keys,
        "Wrong trajectory coverage",
    )
    c.require(
        set(cells["kinetics"]) == set(cells["one_step"]) == set(BACKENDS),
        "Missing Cells kernel backend",
    )
    checks, refinements = [], []

    def compare(label, actual, expected, atol, rtol=0):
        score = c.normalized_error(actual, expected, atol, rtol)
        checks.append(
            {
                "id": label,
                "actual": actual,
                "expected": expected,
                "normalized_error": score,
                "pass": score <= 1,
            }
        )

    statics = {"betse": native["kinetics"]} | cells["kinetics"]
    with localcontext() as context:
        context.prec = precision
        for name, result in statics.items():
            c.require(set(result) == {"target", "tau_s"}, "Wrong kinetic fields")
            c.require(
                len(result["target"]) == len(result["tau_s"]) == len(protocol["voltages_V"]),
                "Wrong voltage coverage",
            )
            for index, v in enumerate(protocol["voltages_V"]):
                expected = kinetics_decimal(v)
                for field, values, absolute in zip(
                    ("target", "tau_s"),
                    expected,
                    (limits["kinetic_gate_atol"], limits["kinetic_tau_s_atol"]),
                    strict=True,
                ):
                    c.require(len(result[field][index]) == 2, "Wrong gate axis")
                    for gate in range(2):
                        compare(
                            f"kinetics/{name}/{index}/{field}/{gate}",
                            result[field][index][gate],
                            float(values[gate]),
                            absolute,
                            limits["kinetic_rtol"],
                        )
        initial = native["equilibrium_initial_gate"]
        c.require(len(initial) == len(protocol["voltages_V"]), "Wrong initialization coverage")
        for index, v in enumerate(protocol["voltages_V"]):
            target, tau = kinetics_decimal(v)
            c.require(len(initial[index]) == 2, "Wrong initialization gate axis")
            for gate in range(2):
                compare(
                    f"native_equilibrium_init/{index}/{gate}",
                    initial[index][gate],
                    float(target[gate]),
                    limits["kinetic_gate_atol"],
                    limits["kinetic_rtol"],
                )
            g0 = tuple(Decimal(str(q)) for q in protocol["one_step_initial_gate"])
            expected = propagate(g0, target, tau, 1000, 1000, "rk4")
            for backend in BACKENDS:
                rows = cells["one_step"][backend]
                c.require(
                    len(rows) == len(protocol["voltages_V"]) and len(rows[index]) == 2,
                    "Wrong one-step coverage",
                )
                for gate in range(2):
                    compare(
                        f"rk4_one_step/{backend}/{index}/{gate}",
                        rows[index][gate],
                        float(expected[gate]),
                        limits["discrete_gate_atol"],
                        limits["discrete_gate_rtol"],
                    )

    error_by_case = {}
    for case in protocol["cases"]:
        exact = reference_trace(case, protocol["step_us"][0], "continuous", precision)
        for engine, result, method in (("betse", native, "betse"), ("cells", cells, "rk4")):
            errors = []
            for dt in protocol["step_us"]:
                name = f"{case['id']}/{dt}"
                trace = result["trajectories"][name]
                validate_trace(case, dt, trace)
                discrete = reference_trace(case, dt, method, precision)
                for i, (state, predicted) in enumerate(zip(trace["gate"], discrete, strict=True)):
                    for gate in range(2):
                        compare(
                            f"discrete/{engine}/{name}/{i}/{gate}",
                            state[gate],
                            predicted[gate],
                            limits["discrete_gate_atol"],
                            limits["discrete_gate_rtol"],
                        )
                        if dt == protocol["step_us"][-1]:
                            tolerance = limits[
                                "native_finest_continuous_gate_atol"
                                if engine == "betse"
                                else "cells_finest_continuous_gate_atol"
                            ]
                            compare(
                                f"continuous/{engine}/{name}/{i}/{gate}",
                                state[gate],
                                exact[i][gate],
                                tolerance,
                            )
                    compare(
                        f"open/{engine}/{name}/{i}",
                        trace["open_fraction"][i],
                        state[0] * state[1],
                        limits["kinetic_gate_atol"],
                        limits["kinetic_rtol"],
                    )
                errors.append(
                    [
                        max(abs(a[g] - b[g]) for a, b in zip(trace["gate"], exact, strict=True))
                        for g in range(2)
                    ]
                )
            error_by_case[f"{engine}/{case['id']}"] = errors
            bounds = limits["native_error_ratio" if engine == "betse" else "cells_error_ratio"]
            for gate in range(2):
                for level in range(2):
                    coarse, fine = errors[level][gate], errors[level + 1][gate]
                    label = f"refinement/{engine}/{case['id']}/{gate}/{level}"
                    if min(coarse, fine) <= limits["refinement_roundoff_floor"]:
                        # Roundoff-limited is an explicit non-test of observed order.
                        refinements.append(
                            {
                                "id": label,
                                "status": "roundoff_limited",
                                "coarse_error": coarse,
                                "fine_error": fine,
                            }
                        )
                    else:
                        ratio = fine / coarse
                        compare(label, ratio, sum(bounds) / 2, (bounds[1] - bounds[0]) / 2)
                        refinements.append({"id": label, "status": "measured", "ratio": ratio})

    for engine, result in (("betse", native), ("cells", cells)):
        for dt in protocol["step_us"]:
            a = result["trajectories"][f"history_low_m/{dt}"]
            b = result["trajectories"][f"history_high_m/{dt}"]
            compare(
                f"equal_initial_open/{engine}/{dt}",
                a["open_fraction"][0],
                b["open_fraction"][0],
                limits["kinetic_gate_atol"],
            )
            separation = max(abs(x - y) for x, y in zip(a["gate"][-1], b["gate"][-1], strict=True))
            c.require(
                separation >= limits["minimum_history_gate_separation"],
                "Independent gate history was collapsed",
            )
    c.require(
        any(r["status"] == "measured" and "/cells/activation/0/" in r["id"] for r in refinements),
        "Missing resolved RK4 activation refinement",
    )
    cross_engine = {
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
        "status": "pass" if all(row["pass"] for row in checks) else "failed",
        "comparison_count": len(checks),
        "failed_comparisons": sum(not r["pass"] for r in checks),
        "maximum_normalized_error": max(row["normalized_error"] for row in checks),
        "comparisons": checks,
        "refinement": refinements,
        "continuous_max_gate_errors": error_by_case,
        "cross_engine_max_gate_differences": cross_engine,
        "isolated_gate_protocols": len(ids),
        "trajectories_per_engine": len(keys),
        "coupled_cell_qualified": False,
        "biology_validated": False,
        "gpu_tested": False,
        "independent_audit_complete": False,
    }
