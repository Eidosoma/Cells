"""Saved piecewise reference checks using the distinct audited algebra, no solvers."""

import bisect
import math
from decimal import localcontext

import feedback_audit_math as independent
import feedback_io as io
import piecewise_reference as layout


def effective(p, u):
    io.require(
        type(u) in (int, float) and math.isfinite(u) and 0 <= u <= 1, "Invalid saved availability"
    )
    return p | {"Pmax_m_per_s": [u * value for value in p["Pmax_m_per_s"]]}


def readout(p, state, u):
    return independent.readout(effective(p, u), state)


def rhs(p, state, u):
    q, m, h, _energy = independent.unpack(p, state)
    rates = independent.ready.vector_field(effective(p, u), q, m, h)
    channels = [i for i, enabled in enumerate(p["channel_enabled"]) if enabled]
    return (
        rates["inward_K_fmol_per_s"]
        + [rates["gate_rate_per_s"][j][i] for j in range(2) for i in channels]
        + rates["dissipation_pJ_per_s"]
    )


def pairs(ledger, name, a, b):
    io.require(set(a) == set(b), "Reference readout fields differ")
    for field in b:
        ledger.compare(name + "/" + field, a[field], b[field], field)


def analytic_gates(p, initial, time_s):
    _q, m, h, _energy = independent.unpack(p, initial)
    voltage = readout(p, initial, 0)["voltage_V"]
    result = [[], []]
    with localcontext() as context:
        context.prec = 80
        d = independent.ind.decimal
        for i, v in enumerate(voltage):
            targets, taus = independent.ind.kinetics(v)
            for j, start in enumerate((m[i], h[i])):
                result[j].append(
                    float(targets[j] + (d(start) - targets[j]) * (-d(time_s) / taus[j]).exp())
                )
    return result


def state_in_segment(piece, time_s):
    times = piece["accepted_times_s"]
    io.require(times[0] <= time_s <= times[-1], "Cross-boundary interpolation forbidden")
    index = max(0, bisect.bisect_left(times, time_s) - 1)
    return independent.dense(piece["dense_intervals"][index], time_s)


def segment_at(record, time_s):
    pieces = record["segments"]
    io.require(pieces[0]["start_s"] <= time_s <= pieces[-1]["end_s"], "Outside reference window")
    return pieces[bisect.bisect_right([p["start_s"] for p in pieces], time_s) - 1]


def domain_and_block(ledger, name, p, state, piece, t):
    observed = readout(p, state, piece["availability"])
    q, _m, _h, energy = independent.unpack(p, state)
    io.require(all(e >= -1e-12 for e in energy), "Negative reference dissipation")
    if piece["availability"] == 0:
        q0, _m0, _h0, energy0 = independent.unpack(p, piece["accepted_states"][0])
        io.require(q == q0 and energy == energy0, "Blocked material/energy carry changed")
        for field in ("flux_fmol_per_s", "permeability_m_per_s", "inward_current_A"):
            io.require(all(v == 0 for v in observed[field]), "Blocked transport is nonzero")
        ledger.compare(
            name + "/analytic_gate",
            observed["gate"],
            analytic_gates(p, piece["accepted_states"][0], t - piece["start_s"]),
            "gate",
        )
    return observed


def validate_record(row, p, gates, schedule, setting, plan, reference, ledger, dense, name):
    n = len(p["volume_pL"])
    channels = [i for i, enabled in enumerate(p["channel_enabled"]) if enabled]
    k = len(channels)
    io.require(
        row["setting"] == setting and row["initial_gate"] == gates and row["schedule"] == schedule,
        "Reference settings differ",
    )
    io.require(
        row["state_axes"]
        == {
            "cell_count": n,
            "channel_cell_indices": channels,
            "order": ["q_fmol", "m_active", "h_active", "energy_pJ"],
        },
        "Reference axes differ",
    )
    specs = layout.segments(schedule, plan["duration_s"])
    io.require(
        len(row["segments"]) == len(specs) and len(row["switches"]) == len(specs) - 1,
        "Reference segment coverage differs",
    )
    carry = [0.0] * n + [gates[0]] * k + [gates[1]] * k + [0.0] * n
    calls = steps = 0
    for s, (piece, spec) in enumerate(zip(row["segments"], specs, strict=True)):
        tag = name + f"/segment/{s}"
        io.require(all(piece[key] == value for key, value in spec.items()), "Segment input differs")
        times, states, intervals = (
            piece[key] for key in ("accepted_times_s", "accepted_states", "dense_intervals")
        )
        io.require(
            len(times) == len(states) == len(intervals) + 1
            and len(times) >= 2
            and times[0] == spec["start_s"]
            and times[-1] == spec["end_s"]
            and all(type(t) in (int, float) and math.isfinite(t) for t in times)
            and all(a < b for a, b in zip(times[:-1], times[1:], strict=True)),
            "Segment clock/coverage differs",
        )
        io.require(states[0] == carry, "Continuous state reset at an input boundary")
        stats = piece["stats"]
        io.require(
            stats["success"] is True
            and stats["status"] == 0
            and stats["accepted_steps"] == len(times) - 1
            and 0 < stats["nfev"] <= stats["rhs_calls_including_jacobian"],
            "Reference solver status differs",
        )
        calls += stats["rhs_calls_including_jacobian"]
        steps += stats["accepted_steps"]
        for j, (t, state) in enumerate(zip(times, states, strict=True)):
            domain_and_block(ledger, tag + f"/accepted/{j}", p, state, piece, t)
        for j, interval in enumerate(intervals):
            io.require(
                interval["method"] == setting["method"]
                and (interval["left_s"], interval["right_s"], interval["y_left"])
                == (times[j], times[j + 1], states[j])
                and times[j + 1] - times[j] <= setting["max_step_s"] * (1 + 1e-12),
                "Dense interval crosses a boundary or exceeds its step cap",
            )
            # Validate every coefficient, not only a potentially cancelling evaluation.
            list(independent.flat(interval["coefficients"]))
            dense.compare(
                tag + f"/endpoint/{j}",
                states[j + 1],
                independent.dense(interval, times[j + 1]),
                "state",
            )
            for fraction in plan["dense_probe_fractions"]:
                t = times[j] + fraction * (times[j + 1] - times[j])
                domain_and_block(
                    ledger,
                    tag + f"/dense/{j}/{fraction}",
                    p,
                    independent.dense(interval, t),
                    piece,
                    t,
                )
        carry = states[-1]
    io.require(
        row["stats"]["segment_integrations"] == len(specs)
        and row["stats"]["accepted_steps"] == steps <= reference["max_accepted_steps_per_solve"]
        and row["stats"]["rhs_calls_including_jacobian"]
        == calls
        <= reference["max_rhs_calls_per_solve"],
        "Reference resource counts differ",
    )
    for j, switch in enumerate(row["switches"]):
        left, right = row["segments"][j : j + 2]
        before, after = left["accepted_states"][-1], right["accepted_states"][0]
        io.require(
            switch["time_s"] == right["start_s"]
            and switch["state_before"] == before == after == switch["state_after"]
            and switch["left_availability"] == left["availability"]
            and switch["right_availability"] == right["availability"],
            "Switch carry/input differs",
        )
        for side, piece in (("left", left), ("right", right)):
            tag = name + f"/switch/{j}/{side}"
            pairs(ledger, tag, switch[side + "_readout"], readout(p, before, piece["availability"]))
            actual, expected = switch[side + "_rhs"], rhs(p, before, piece["availability"])
            io.require(len(actual) == len(expected), "Switch derivative axes differ")
            for lo, hi, unit in (
                (0, n, "flux_fmol_per_s"),
                (n, n + 2 * k, "gate_rate_per_s"),
                (n + 2 * k, 2 * n + 2 * k, "power_pJ_per_s"),
            ):
                ledger.compare(tag + "/rhs/" + unit, actual[lo:hi], expected[lo:hi], unit)
        io.require(
            switch["left_rhs"][n : n + 2 * k] == switch["right_rhs"][n : n + 2 * k],
            "Availability changed intrinsic gate rates",
        )
    times = layout.sample_times(plan["duration_s"], plan["sample_dt_s"])
    io.require(
        row["sample_times_s"] == times
        and len(row["sample_states"]) == len(row["readouts"]) == len(times),
        "Sample grid differs",
    )
    for j, (t, state, saved) in enumerate(
        zip(times, row["sample_states"], row["readouts"], strict=True)
    ):
        tag, piece = name + f"/sample/{j}", segment_at(row, t)
        if t == piece["start_s"]:
            io.require(
                state == piece["accepted_states"][0], "Sample differs from exact start carry"
            )
        if t == piece["end_s"]:
            io.require(state == piece["accepted_states"][-1], "Sample differs from exact end carry")
        dense.compare(tag, state, state_in_segment(piece, t), "state")
        actual = domain_and_block(ledger, tag, p, state, piece, t)
        pairs(ledger, tag, saved, actual)
        q, _m, _h, energy = independent.unpack(p, state)
        ledger.compare(
            tag + "/thermodynamics", math.fsum(energy), independent.dissipated(p, q), "energy_pJ"
        )


def peak_difference(a, b):
    return max(abs(x - y) for x, y in zip(independent.flat(a), independent.flat(b), strict=True))


def signal_gate(plan, data, records):
    """Prospective resolution thresholds, not a demand for a biological memory effect."""
    outcomes = {}
    units = {
        "block_effect": "voltage_V",
        "post_release_change": "voltage_V",
        "release_flux": "flux_fmol_per_s",
        "block_gate_change": "gate",
    }
    minima = dict(
        zip(
            units,
            (
                plan["signal"][k]
                for k in (
                    "minimum_block_effect_V",
                    "minimum_post_release_voltage_change_V",
                    "minimum_release_flux_fmol_per_s",
                    "minimum_block_gate_change",
                )
            ),
            strict=True,
        )
    )
    for history in plan["histories"]:
        measured = {key: [] for key in units}
        magnitudes = dict.fromkeys(units, 1.0)
        for setting in data["reference"]["solves"]:
            release = records[f"{history}/suppression_release/{setting['id']}"]
            baseline = records[f"{history}/baseline/{setting['id']}"]
            b = release["sample_times_s"].index(plan["block_time_s"])
            r = release["sample_times_s"].index(plan["release_time_s"])
            start, end, final = (release["readouts"][i] for i in (b, r, -1))
            measured["block_effect"].append(
                peak_difference(end["voltage_V"], baseline["readouts"][r]["voltage_V"])
            )
            measured["post_release_change"].append(
                peak_difference(final["voltage_V"], end["voltage_V"])
            )
            measured["release_flux"].append(max(abs(v) for v in end["flux_fmol_per_s"]))
            measured["block_gate_change"].append(peak_difference(end["gate"], start["gate"]))
            for key, unit in units.items():
                magnitudes[key] = max(
                    magnitudes[key],
                    *(
                        abs(v)
                        for point in (start, end, final, baseline["readouts"][r])
                        for v in independent.flat(point[unit])
                    ),
                )
        outcomes[history] = {}
        for key, values in measured.items():
            # Two readout uncertainties bound a difference; use this also for flux conservatively.
            threshold = minima[key] + plan["signal"]["reference_uncertainty_multiplier"] * (
                data["reference"]["comparison_absolute"][units[key]]
                + data["comparison_relative"] * magnitudes[key]
            )
            outcomes[history][key] = {
                "values_by_solver": values,
                "required_minimum": threshold,
                "relative_uncertainty_magnitude_bound": magnitudes[key],
                "pass": min(values) >= threshold,
            }
    return {
        "by_history": outcomes,
        "pass": all(row["pass"] for h in outcomes.values() for row in h.values()),
        "window_s": plan["duration_s"],
        "window_extended": False,
        "positive_history_effect_required": False,
    }


def check(r, output, aggregate):
    data, plan = r["inputs"], r["plan"]
    settings = data["reference"]["solves"]
    expected = {
        f"{h}/{v}/{s['id']}": f"reference/{h}/{v}/{s['id']}/result.json.gz"
        for h in plan["histories"]
        for v in plan["conditions"]
        for s in settings
    }
    io.require(
        aggregate["records"] == expected
        and aggregate["reference_paths"] == len(expected)
        and aggregate["segment_integrations"] == plan["segment_integrations"],
        "Reference path coverage",
    )
    absolute = data["reference"]["comparison_absolute"] | {
        "gate_rate_per_s": 2e-9,
        "power_pJ_per_s": 2e-7,
    }
    ledger = io.Ledger(absolute, data["comparison_relative"], output / "reference-failures.jsonl")
    dense = io.Ledger({"state": 5e-13}, 2e-13, output / "dense-failures.jsonl")
    records, disagreement = {}, {}
    for history, gates in plan["histories"].items():
        for condition in plan["conditions"]:
            group = f"{history}/{condition}"
            for setting in settings:
                key = group + "/" + setting["id"]
                row = io.read_compressed(output / expected[key])
                validate_record(
                    row,
                    data["parameters"][history],
                    gates,
                    data["schedules"][condition],
                    setting,
                    plan,
                    data["reference"],
                    ledger,
                    dense,
                    key,
                )
                records[key] = row
            primary = records[group + "/" + data["reference"]["primary"]]
            maximum = dict.fromkeys(data["reference"]["comparison_absolute"], 0.0)
            for setting in settings:
                other = records[group + "/" + setting["id"]]
                for j, (a, b) in enumerate(
                    zip(other["readouts"], primary["readouts"], strict=True)
                ):
                    for field in a:
                        ledger.compare(
                            group + f"/{setting['id']}/agreement/{j}/" + field,
                            a[field],
                            b[field],
                            field,
                        )
                        maximum[field] = max(maximum[field], peak_difference(a[field], b[field]))
                    if j:
                        a0, b0 = other["readouts"][j - 1], primary["readouts"][j - 1]
                        da = [
                            x - y
                            for x, y in zip(a["transfer_fmol"], a0["transfer_fmol"], strict=True)
                        ]
                        db = [
                            x - y
                            for x, y in zip(b["transfer_fmol"], b0["transfer_fmol"], strict=True)
                        ]
                        ledger.compare(
                            group + f"/{setting['id']}/interval/{j}",
                            da,
                            db,
                            "interval_transfer_fmol",
                        )
                        maximum["interval_transfer_fmol"] = max(
                            maximum["interval_transfer_fmol"], peak_difference(da, db)
                        )
                for j, (a, b) in enumerate(
                    zip(other["switches"], primary["switches"], strict=True)
                ):
                    for side in ("left", "right"):
                        pairs(
                            ledger,
                            group + f"/{setting['id']}/switch_agreement/{j}/{side}",
                            a[side + "_readout"],
                            b[side + "_readout"],
                        )
            disagreement[group] = maximum
        for setting in settings:
            baseline = records[f"{history}/baseline/{setting['id']}"]
            for condition in ("no_op", "suppression_release"):
                other = records[f"{history}/{condition}/{setting['id']}"]
                for j, t in enumerate(other["sample_times_s"]):
                    if condition == "suppression_release" and t >= plan["block_time_s"]:
                        break  # State is continuous at the switch, but fresh flux is right-sided.
                    pairs(
                        ledger,
                        f"{history}/{condition}/{setting['id']}/control/{j}",
                        other["readouts"][j],
                        baseline["readouts"][j],
                    )
    signal = signal_gate(plan, data, records)
    primary = data["reference"]["primary"]
    a, b = (records[f"{h}/suppression_release/{primary}"]["readouts"][-1] for h in ("a", "b"))
    contrast = {
        "final_a_minus_b_voltage_V": [
            x - y for x, y in zip(a["voltage_V"], b["voltage_V"], strict=True)
        ],
        "final_a_minus_b_open_fraction": [
            ma * ha - mb * hb for ma, ha, mb, hb in zip(*a["gate"], *b["gate"], strict=True)
        ],
    }
    passed = ledger.failed == dense.failed == 0 and signal["pass"]
    return {
        "schema": "cells.betse_release_reference_gate@1",
        "status": "pass" if passed else "fail",
        "comparison": ledger.summary(),
        "dense_replay": dense.summary(),
        "measured_reference_disagreement": disagreement,
        "signal": signal,
        "history_diagnostic": contrast,
        "reference_paths": len(expected),
        "segment_integrations": plan["segment_integrations"],
        "selected_primary": primary,
        "candidate_duration_s": plan["duration_s"],
        "reference_ready_for_later_simulator_design": passed,
        "simulator_execution_allowed": False,
        "release_response_qualified": False,
        "biology_validated": False,
        "gpu_tested": False,
        "domain_scope": "RHS, accepted states, saved samples and three interior probes "
        "per dense interval; not a global proof",
    }
