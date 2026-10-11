"""Saved reference convergence, analytic controls and dense-polynomial replay."""

import bisect
import math
from decimal import Decimal, localcontext

import feedback_io as io
import feedback_reference as ref


def flat(value):
    if isinstance(value, list):
        for v in value:
            yield from flat(v)
    else:
        io.require(type(value) in (int, float) and math.isfinite(value), "Invalid numeric state")
        yield value


def dense_value(record, time_s):
    left, right = record["left_s"], record["right_s"]
    io.require(left <= time_s <= right and left < right, "Dense evaluation outside interval")
    x = (time_s - left) / (right - left)
    initial, coefficients = record["y_left"], record["coefficients"]
    if record["method"] == "DOP853":
        io.require(
            len(coefficients) == 7 and all(len(v) == len(initial) for v in coefficients),
            "DOP853 dense shape",
        )
        values = [0.0] * len(initial)
        for i, row in enumerate(reversed(coefficients)):
            factor = x if i % 2 == 0 else 1 - x
            values = [(a + b) * factor for a, b in zip(values, row, strict=True)]
        return [a + b for a, b in zip(values, initial, strict=True)]
    io.require(
        record["method"] == "Radau"
        and len(coefficients) == len(initial)
        and all(len(v) == 3 for v in coefficients),
        "Radau dense shape",
    )
    return [
        base + math.fsum(c * x ** (j + 1) for j, c in enumerate(row))
        for base, row in zip(initial, coefficients, strict=True)
    ]


def sample_state(record, time_s):
    index = bisect.bisect_left(record["accepted_times_s"], time_s) - 1
    index = max(0, min(index, len(record["dense_intervals"]) - 1))
    return dense_value(record["dense_intervals"][index], time_s)


def thermodynamic_dissipation(p, q):
    """Total passive dissipation is the closed-system free-energy decrease."""
    with localcontext() as context:
        context.prec = 80
        d = lambda v: Decimal(str(v))  # noqa: E731
        delta_chemical = Decimal(0)
        delta_capacitor = Decimal(0)
        for i, transfer in enumerate(q):
            initial, volume, transfer = d(p["initial_K_fmol"][i]), d(p["volume_pL"][i]), d(transfer)
            amount = initial + transfer
            delta_chemical += amount * (amount / volume).ln() - initial * (initial / volume).ln()
            capacitance = d(p["area_m2"][i]) * d(p["cm_F_per_m2"])
            v0 = d(p["initial_voltage_V"][i])
            voltage = v0 + d(p["F"]) * Decimal("1e-15") * transfer / capacitance
            delta_capacitor += capacitance * (voltage**2 - v0**2) * Decimal("5e11")
        initial, volume = d(p["outside_K_fmol"]), d(p["outside_volume_pL"])
        amount = initial - sum(map(d, q))
        delta_chemical += amount * (amount / volume).ln() - initial * (initial / volume).ln()
        return float(
            -delta_chemical * d(p["R"]) * d(p["temperature_K"]) * Decimal(".001") - delta_capacitor
        )


def point_pairs(left, right, previous_left=None, previous_right=None):
    io.require(set(left) == set(right), "Readout fields differ")
    for field in left:
        yield field, left[field], right[field]
    if previous_left is not None:
        yield (
            "interval_transfer_fmol",
            [
                a - b
                for a, b in zip(left["transfer_fmol"], previous_left["transfer_fmol"], strict=True)
            ],
            [
                a - b
                for a, b in zip(
                    right["transfer_fmol"], previous_right["transfer_fmol"], strict=True
                )
            ],
        )


def validate_record(record, p, setting, protocol):
    io.require(record["setting"] == setting, "Reference settings differ")
    times, states = record["accepted_times_s"], record["accepted_states"]
    io.require(
        times[0] == 0
        and times[-1] == protocol["duration_s"]
        and all(a < b for a, b in zip(times[:-1], times[1:], strict=True)),
        "Reference accepted clocks differ",
    )
    io.require(
        len(times) == len(states) == len(record["dense_intervals"]) + 1,
        "Reference interval coverage",
    )
    io.require(states[0] == ref.initial_state(p), "Reference initial state differs")
    io.require(
        record["stats"]["success"] is True
        and record["stats"]["status"] == 0
        and record["stats"]["accepted_steps"] == len(times) - 1,
        "Reference solver failed",
    )
    io.require(
        len(times) - 1 <= protocol["reference"]["max_accepted_steps_per_solve"]
        and record["stats"]["rhs_calls_including_jacobian"]
        <= protocol["reference"]["max_rhs_calls_per_solve"],
        "Reference budget violated",
    )
    for i, interval in enumerate(record["dense_intervals"]):
        io.require(
            (interval["left_s"], interval["right_s"], interval["y_left"])
            == (times[i], times[i + 1], states[i]),
            "Reference dense boundary differs",
        )
        io.require(interval["method"] == setting["method"], "Reference dense method differs")
        io.require(
            times[i + 1] - times[i] <= setting["max_step_s"] * (1 + 1e-12),
            "Reference step cap exceeded",
        )
    tick = protocol["reference"]["sample_dt_s"]
    expected_times = [i * tick for i in range(round(protocol["duration_s"] / tick))] + [
        protocol["duration_s"]
    ]
    io.require(
        record["sample_times_s"] == expected_times
        and len(record["sample_states"]) == len(record["readouts"]) == len(expected_times),
        "Reference sampling differs",
    )


def check(r, output, aggregate):
    protocol = r["protocol"]
    settings = protocol["reference"]["solves"]
    expected = {v + "/" + s["id"] for v in protocol["variants"] for s in settings}
    io.require(
        set(aggregate["records"]) == expected and aggregate["reference_solves"] == 12,
        "Reference solve coverage differs",
    )
    ledger = io.Ledger(
        protocol["reference"]["comparison_absolute"],
        protocol["comparison_relative"],
        output / "reference-failures.jsonl",
    )
    dense = io.Ledger({"state": 5e-13}, 2e-13, output / "reference-dense-failures.jsonl")
    records, errors = {}, {}
    for variant in protocol["variants"]:
        p = r["reference_parameters"][variant]
        rows = {}
        for setting in settings:
            key = variant + "/" + setting["id"]
            row = io.read_compressed(output / aggregate["records"][key])
            validate_record(row, p, setting, protocol)
            for j, (t, state, readout) in enumerate(
                zip(row["sample_times_s"], row["sample_states"], row["readouts"], strict=True)
            ):
                dense.compare(key + f"/sample/{j}", state, sample_state(row, t), "state")
                actual = ref.readout(p, state)
                for name, a, b in point_pairs(readout, actual):
                    ledger.compare(key + f"/readout/{j}/" + name, a, b, name)
                q, _m, _h, energy = ref.unpack(p, state)
                io.require(all(e >= -1e-12 for e in energy), "Negative reference dissipation")
                ledger.compare(
                    key + f"/thermodynamics/{j}",
                    math.fsum(energy),
                    thermodynamic_dissipation(p, q),
                    "energy_pJ",
                )
                if variant != "active_channel":
                    io.require(
                        all(v == 0 for v in q + energy), "Nonzero inactive reference transport"
                    )
                if variant == "blocked_channel":
                    for i, voltage in enumerate(p["initial_voltage_V"]):
                        mi = 1 / (1 + math.exp(-(voltage + 0.006) / 0.0064))
                        hi = 1 / (1 + math.exp((voltage + 0.0253) / 0.0035))
                        expected_gate = [
                            mi + (0.2 - mi) * math.exp(-t / (0.008330 - 0.1163 * voltage)),
                            hi + (0.6 - hi) * math.exp(-t / (1.620 - 15.5 * voltage)),
                        ]
                        ledger.compare(
                            key + f"/analytic/{j}/{i}",
                            [readout["gate"][0][i], readout["gate"][1][i]],
                            expected_gate,
                            "gate",
                        )
            for i, interval in enumerate(row["dense_intervals"]):
                dense.compare(
                    key + f"/accepted/{i}",
                    row["accepted_states"][i + 1],
                    dense_value(interval, interval["right_s"]),
                    "state",
                )
            rows[setting["id"]] = row
        primary = rows[protocol["reference"]["primary"]]
        maximum = dict.fromkeys(protocol["reference"]["comparison_absolute"], 0.0)
        for name, other in rows.items():
            if name == protocol["reference"]["primary"]:
                continue
            previous_a = previous_b = None
            for j, (a, b) in enumerate(zip(other["readouts"], primary["readouts"], strict=True)):
                for field, left, right in point_pairs(a, b, previous_a, previous_b):
                    ledger.compare(variant + f"/{name}/agreement/{j}/" + field, left, right, field)
                    maximum[field] = max(
                        maximum[field],
                        max(abs(x - y) for x, y in zip(flat(left), flat(right), strict=True)),
                    )
                previous_a, previous_b = a, b
        errors[variant] = maximum
        records[variant] = {
            "times_s": primary["sample_times_s"],
            "states": primary["sample_states"],
            "readouts": primary["readouts"],
        }
    summary = {
        "schema": "cells.betse_channel_feedback_reference_gate@1",
        "status": "pass" if ledger.failed == dense.failed == 0 else "fail",
        "comparison": ledger.summary(),
        "dense_replay": dense.summary(),
        "measured_reference_disagreement": errors,
        "selected_primary": protocol["reference"]["primary"],
        "reference_solves": 12,
        "reference_solutions": records,
        "reference_convergence_checked": ledger.failed == dense.failed == 0,
        "coupled_trajectory_qualified": False,
        "biology_validated": False,
    }
    io.write_compressed(output / "reference-gate.json.gz", summary)
    return summary
