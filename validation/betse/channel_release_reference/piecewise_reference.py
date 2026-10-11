"""Independent float64 integration with 80-digit RHS and exact input boundaries.

The solver sees one fixed availability per segment, including its endpoint RHS.
All 28 continuous coordinates carry across a switch. Neither simulator is used.
"""

import bisect
import math
import sys
import time
from decimal import Decimal

import feedback_io as io
import paired_reference as base


def availability(value):
    io.require(
        type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1,
        "Invalid reference availability",
    )
    return value


def segments(schedule, duration):
    io.require(schedule and schedule[0]["time"] == 0 and duration > 0, "Invalid schedule origin")
    starts = [row["time"] for row in schedule]
    io.require(
        all(type(v) in (int, float) and math.isfinite(v) for v in starts)
        and all(a < b for a, b in zip(starts, starts[1:] + [duration], strict=True)),
        "Unordered or out-of-window schedule",
    )
    return [
        {"start_s": a, "end_s": b, "availability": availability(row["availability"])}
        for row, a, b in zip(schedule, starts, starts[1:] + [duration], strict=True)
    ]


def sample_times(duration, step):
    end, tick = Decimal(str(duration)), Decimal(str(step))
    io.require(end > 0 and tick > 0 and end / tick == int(end / tick), "Incomplete sample grid")
    return [float(i * tick) for i in range(int(end / tick) + 1)]


def derivative(p, state, value):
    u = availability(value)
    rates = base.derivative(p, state)
    n, channels = base.axes(p)
    return (
        [u * v for v in rates[:n]]
        + rates[n : n + 2 * len(channels)]
        + [u * v for v in rates[n + 2 * len(channels) :]]
    )


def readout(p, state, value):
    u = availability(value)
    result = base.readout(p, state)
    for name in ("flux_fmol_per_s", "permeability_m_per_s", "inward_current_A"):
        result[name] = [u * v for v in result[name]]
    return result


def integrate(p, gates, schedule, setting, plan, reference):
    import numpy as np
    from scipy.integrate import solve_ivp

    began = time.monotonic()
    n, channels = base.axes(p)
    state = base.initial_state(p, gates)
    atol = (
        [setting["atol_q_fmol"]] * n
        + [setting["atol_gate"]] * (2 * len(channels))
        + [setting["atol_energy_pJ"]] * n
    )
    pieces, solutions, calls = [], [], 0
    for spec in segments(schedule, plan["duration_s"]):
        u = spec["availability"]
        start_calls = calls

        def rhs(_t, y, held=u):
            nonlocal calls
            calls += 1
            io.require(calls <= reference["max_rhs_calls_per_solve"], "Reference RHS budget")
            return np.asarray(derivative(p, y.tolist(), held), dtype=np.float64)

        solution = solve_ivp(
            rhs,
            (spec["start_s"], spec["end_s"]),
            np.asarray(state, dtype=np.float64),
            method=setting["method"],
            rtol=setting["rtol"],
            atol=np.asarray(atol, dtype=np.float64),
            max_step=setting["max_step_s"],
            dense_output=True,
        )
        io.require(
            solution.success and solution.status == 0 and solution.t[-1] == spec["end_s"],
            "Reference segment failed",
        )
        io.require(
            solution.y.dtype == np.float64 and np.all(np.isfinite(solution.y)),
            "Invalid reference precision/state",
        )
        piece = spec | {
            "accepted_times_s": solution.t.tolist(),
            "accepted_states": solution.y.T.tolist(),
            "dense_intervals": [
                base.dense_record(poly, setting["method"]) for poly in solution.sol.interpolants
            ],
            "stats": {
                "success": bool(solution.success),
                "status": int(solution.status),
                "message": solution.message,
                "nfev": solution.nfev,
                "njev": solution.njev,
                "nlu": solution.nlu,
                "rhs_calls_including_jacobian": calls - start_calls,
                "accepted_steps": len(solution.t) - 1,
            },
        }
        io.require(piece["accepted_states"][0] == state, "Reference solver reset its carry")
        pieces.append(piece)
        solutions.append(solution)
        state = piece["accepted_states"][-1]
        io.require(
            sum(x["stats"]["accepted_steps"] for x in pieces)
            <= reference["max_accepted_steps_per_solve"],
            "Reference step budget",
        )
    times = sample_times(plan["duration_s"], plan["sample_dt_s"])
    states, readouts = [], []
    starts = [piece["start_s"] for piece in pieces]
    for t in times:
        index = bisect.bisect_right(starts, t) - 1
        piece, solution = pieces[index], solutions[index]
        y = (
            piece["accepted_states"][0]
            if t == piece["start_s"]
            else piece["accepted_states"][-1]
            if t == piece["end_s"]
            else solution.sol(t).tolist()
        )
        derivative(p, y, piece["availability"])
        states.append(y)
        readouts.append(readout(p, y, piece["availability"]))
    switches = []
    for left, right in zip(pieces[:-1], pieces[1:], strict=True):
        before, after = left["accepted_states"][-1], right["accepted_states"][0]
        switches.append(
            {
                "time_s": right["start_s"],
                "state_before": before,
                "state_after": after,
                "left_availability": left["availability"],
                "right_availability": right["availability"],
                "left_readout": readout(p, before, left["availability"]),
                "right_readout": readout(p, after, right["availability"]),
                "left_rhs": derivative(p, before, left["availability"]),
                "right_rhs": derivative(p, after, right["availability"]),
            }
        )
    return {
        "setting": setting,
        "initial_gate": gates,
        "schedule": schedule,
        "state_axes": {
            "cell_count": n,
            "channel_cell_indices": channels,
            "order": ["q_fmol", "m_active", "h_active", "energy_pJ"],
        },
        "segments": pieces,
        "switches": switches,
        "sample_times_s": times,
        "sample_states": states,
        "readouts": readouts,
        "stats": {
            "rhs_calls_including_jacobian": calls,
            "accepted_steps": sum(x["stats"]["accepted_steps"] for x in pieces),
            "segment_integrations": len(pieces),
            "elapsed_seconds": time.monotonic() - began,
        },
    }


def worker(r, output):
    data, plan, records = r["inputs"], r["plan"], {}
    count = 0
    for history, gates in plan["histories"].items():
        for condition in plan["conditions"]:
            for setting in data["reference"]["solves"]:
                key = f"{history}/{condition}/{setting['id']}"
                row = integrate(
                    data["parameters"][history],
                    gates,
                    data["schedules"][condition],
                    setting,
                    plan,
                    data["reference"],
                )
                path = output / "reference" / key / "result.json.gz"
                path.parent.mkdir(parents=True, exist_ok=False)
                io.write_compressed(path, row)
                records[key] = str(path.relative_to(output))
                count += row["stats"]["segment_integrations"]
                print("reference complete", key, flush=True)
    forbidden = {"cells", "betse", "jax", "jaxlib"}
    io.require(
        not any(name.split(".")[0] in forbidden for name in sys.modules),
        "Simulator imported by independent reference",
    )
    return {
        "engine": "piecewise_decimal_rhs_scipy_dop853_radau",
        "records": records,
        "reference_paths": len(records),
        "segment_integrations": count,
        "rhs_precision_digits": 80,
        "integration_precision": "float64",
        "simulator_imports": [],
    }
