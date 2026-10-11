"""Frozen D104 replay with independently reconstructed numerical columns.

Uses the alternate audited RHS, nested dense basis and endpoint free energy.
No simulator or reference solver runs. This is not a third ODE solution.
"""

import bisect
import math
from decimal import Decimal
from unittest.mock import patch

import history_audit_math as am
import piecewise_check as frozen
import timed_context as ctx

c, io = ctx.c, ctx.io


class Reference:
    def __init__(self, r, records):
        self.r, self.rows, self.cache = r, records, {}

    def memo(self, key, calculate):
        if key not in self.cache:
            self.cache[key] = calculate()
        return self.cache[key]

    def parameters(self, key):
        return self.r["inputs"]["parameters"][key.split("/")[0]]

    def own(self, key, identity, state, u):
        def calculate():
            value = am.readout(self.parameters(key), state)
            for name in ("flux_fmol_per_s", "inward_current_A", "permeability_m_per_s"):
                value[name] = [u * x for x in value[name]]
            return value

        return self.memo((key, identity, u, "readout"), calculate)

    def sample(self, key, index):
        row = self.rows[key]
        schedule = self.r["inputs"]["schedules"][key.split("/")[1]]
        u = ctx.availability(schedule, row["sample_times_s"][index])
        return self.own(key, ("sample", index), row["sample_states"][index], u)

    def piece(self, key, time_s):
        pieces = self.rows[key]["segments"]
        return pieces[bisect.bisect_right([s["start_s"] for s in pieces], time_s) - 1]

    def dense(self, piece, time_s):
        index = max(0, bisect.bisect_left(piece["accepted_times_s"], time_s) - 1)
        return am.dense(piece["dense_intervals"][index], time_s)

    def analytic(self, key, piece, time_s):
        start = piece["accepted_states"][0]
        p = self.parameters(key)
        _q, m, h, _e = am.unpack(p, start)
        volts = am.readout(p, start)["voltage_V"]
        gates = [
            am.analytic_gate(v, time_s - piece["start_s"], [m[i], h[i]])
            for i, v in enumerate(volts)
        ]
        return [[value[j] for value in gates] for j in range(2)]

    def switch(self, key, index, side):
        piece = self.rows[key]["segments"][index + (side == "right")]
        state = self.rows[key]["segments"][index]["accepted_states"][-1]
        return self.own(key, ("switch", index), state, piece["availability"])

    def switch_rhs(self, key, index, side):
        def calculate():
            p = self.parameters(key)
            state = self.rows[key]["segments"][index]["accepted_states"][-1]
            q, m, h, _e = am.unpack(p, state)
            u = self.rows[key]["segments"][index + (side == "right")]["availability"]
            rates = am.field.rates(p, q, m, h)
            return {
                "flux_fmol_per_s": [u * v for v in rates["inward_K_fmol_per_s"]],
                "gate_rate_per_s": [v for group in rates["gate_rate_per_s"] for v in group],
                "power_pJ_per_s": [u * v for v in rates["dissipation_pJ_per_s"]],
            }

        return self.memo((key, index, side, "rhs"), calculate)

    def validate(self):
        plan = self.r["plan"]
        settings = self.r["inputs"]["reference"]["solves"]
        expected = {
            f"{h}/{v}/{s['id']}"
            for h in plan["histories"]
            for v in plan["conditions"]
            for s in settings
        }
        c.require(set(self.rows) == expected, "Independent reference membership")
        tick = Decimal(str(plan["sample_dt_s"]))
        times = [float(i * tick) for i in range(int(Decimal(str(plan["duration_s"])) / tick) + 1)]
        for key, row in self.rows.items():
            h, condition, method = key.split("/")
            schedule = self.r["inputs"]["schedules"][condition]
            c.require(
                row["schedule"] == schedule and row["sample_times_s"] == times,
                "Independent reference clocks",
            )
            c.require(row["initial_gate"] == plan["histories"][h], "Independent initial history")
            c.require(
                row["setting"] == next(s for s in settings if s["id"] == method),
                "Independent solver setting",
            )
            carry = am.initial(self.parameters(key), plan["histories"][h])
            c.require(len(row["segments"]) == len(schedule), "Independent segment count")
            for i, (piece, control) in enumerate(zip(row["segments"], schedule, strict=True)):
                end = schedule[i + 1]["time"] if i + 1 < len(schedule) else plan["duration_s"]
                c.require(
                    piece["start_s"] == control["time"]
                    and piece["end_s"] == end
                    and piece["availability"] == control["availability"]
                    and piece["accepted_states"][0] == carry,
                    "Independent boundary continuity",
                )
                for name in (
                    "nfev",
                    "njev",
                    "nlu",
                    "rhs_calls_including_jacobian",
                    "accepted_steps",
                ):
                    c.require(
                        type(piece["stats"][name]) is int and piece["stats"][name] >= 0,
                        "Reference integer counter",
                    )
                for state in piece["accepted_states"]:
                    self.own(key, ("accepted", i, tuple(state)), state, piece["availability"])
                carry = piece["accepted_states"][-1]
            c.require(
                math.isfinite(row["stats"]["elapsed_seconds"])
                and row["stats"]["elapsed_seconds"] > 0,
                "Reference solve timing",
            )

    def resolve(self, name, dense=False):
        parts = name.split("/")
        key, action = "/".join(parts[:3]), parts[3]
        row = self.rows[key]
        p = self.parameters(key)
        if action == "segment":
            index, item, j = int(parts[4]), parts[5], int(parts[6])
            piece = row["segments"][index]
            if item == "endpoint":
                interval = piece["dense_intervals"][j]
                a, b, unit, tail = (
                    piece["accepted_states"][j + 1],
                    am.dense(interval, interval["right_s"]),
                    "state",
                    parts[7:],
                )
            else:
                if item == "accepted":
                    state, t, tail = (
                        piece["accepted_states"][j],
                        piece["accepted_times_s"][j],
                        parts[8:],
                    )
                    c.require(parts[7] == "analytic_gate", "Independent accepted identity")
                else:
                    c.require(
                        item == "dense" and parts[8] == "analytic_gate",
                        "Independent dense identity",
                    )
                    interval, fraction = piece["dense_intervals"][j], float(parts[7])
                    t = interval["left_s"] + fraction * (interval["right_s"] - interval["left_s"])
                    state, tail = am.dense(interval, t), parts[9:]
                a = self.own(key, tuple(parts[4 : -len(tail)]), state, piece["availability"])[
                    "gate"
                ]
                b = self.memo((key, index, t, "analytic"), lambda: self.analytic(key, piece, t))
                unit = "gate"
        elif action == "sample":
            j = int(parts[4])
            if dense:
                t = row["sample_times_s"][j]
                a, b, unit, tail = (
                    row["sample_states"][j],
                    self.dense(self.piece(key, t), t),
                    "state",
                    parts[5:],
                )
            else:
                field, tail = parts[5], parts[6:]
                if field == "analytic_gate":
                    t = row["sample_times_s"][j]
                    a, b, unit = (
                        self.sample(key, j)["gate"],
                        self.memo(
                            (key, j, "analytic_sample"),
                            lambda: self.analytic(key, self.piece(key, t), t),
                        ),
                        "gate",
                    )
                elif field == "thermodynamics":
                    q, _m, _h, energy = am.unpack(p, row["sample_states"][j])
                    a, b, unit = math.fsum(energy), am.dissipated(p, q), "energy_pJ"
                else:
                    a, b, unit = row["readouts"][j][field], self.sample(key, j)[field], field
        elif action in ("switch", "switch_agreement"):
            j, side, field = int(parts[4]), parts[5], parts[6]
            if field == "rhs":
                unit, tail = parts[7], parts[8:]
                n = len(p["volume_pL"])
                bounds = {
                    "flux_fmol_per_s": (0, n),
                    "gate_rate_per_s": (n, 3 * n),
                    "power_pJ_per_s": (3 * n, 4 * n),
                }
                lo, hi = bounds[unit]
                a, b = row["switches"][j][side + "_rhs"][lo:hi], self.switch_rhs(key, j, side)[unit]
            else:
                unit, tail = field, parts[7:]
                a = row["switches"][j][side + "_readout"][field]
                primary = "/".join(parts[:2]) + "/" + self.r["inputs"]["reference"]["primary"]
                b = self.switch(primary if action == "switch_agreement" else key, j, side)[field]
        elif action in ("agreement", "control", "interval"):
            j = int(parts[4])
            primary = "/".join(parts[:2]) + "/" + self.r["inputs"]["reference"]["primary"]
            if action == "control":
                primary = parts[0] + "/baseline/" + parts[2]
            if action == "interval":
                a, b = (
                    am.subtract(
                        self.sample(k, j)["transfer_fmol"], self.sample(k, j - 1)["transfer_fmol"]
                    )
                    for k in (key, primary)
                )
                unit, tail = "interval_transfer_fmol", parts[5:]
            else:
                unit, tail = parts[5], parts[6:]
                a, b = self.sample(key, j)[unit], self.sample(primary, j)[unit]
        else:
            raise ValueError("Unknown independent reference identity: " + name)
        return am.component(a, tail), am.component(b, tail), unit


def review(output):
    original = c.read(ctx.CAPTURE / "registration.json")
    aggregate = c.read(ctx.CAPTURE / "reference.json")
    records = {
        key: io.read_compressed(ctx.CAPTURE / path) for key, path in aggregate["records"].items()
    }
    own = Reference(original, records)
    own.validate()
    crossed = am.Crosscheck(output / "reference-independent-failures.jsonl")
    ledger_class = io.Ledger

    class ReviewLedger(ledger_class):
        def __init__(self, absolute, relative=2e-11, failure_path=None):
            super().__init__(absolute, relative, output / ("reference-replay-" + failure_path.name))

        def compare(self, name, actual, expected, unit):
            if not isinstance(expected, list):
                a, b, derived_unit = own.resolve(name, dense=set(self.absolute) == {"state"})
                c.require(derived_unit == unit, "Independent reference units differ")
                crossed.add(name, actual, expected, a, b, unit, self.absolute[unit], self.relative)
            super().compare(name, actual, expected, unit)

    # Only a validation ledger is instrumented; numerical model code is never patched.
    with patch.object(frozen.io, "Ledger", ReviewLedger):
        replayed = frozen.check(original, ctx.CAPTURE, aggregate)
    saved = c.read(ctx.CAPTURE / "reference-gate.json")
    c.require(replayed == saved and replayed["status"] == "pass", "Frozen reference replay differs")
    # Independent threshold arithmetic on reconstructed readouts, not the replay's signal result.
    for history, metrics in saved["signal"]["by_history"].items():
        values = {name: [] for name in metrics}
        magnitudes = dict.fromkeys(metrics, 1.0)
        units = {
            "block_effect": "voltage_V",
            "post_release_change": "voltage_V",
            "release_flux": "flux_fmol_per_s",
            "block_gate_change": "gate",
        }
        for setting in original["inputs"]["reference"]["solves"]:
            key = f"{history}/suppression_release/{setting['id']}"
            row = records[key]
            bi, ri = (
                row["sample_times_s"].index(original["plan"][k])
                for k in ("block_time_s", "release_time_s")
            )
            start, release, final = (own.sample(key, j) for j in (bi, ri, len(row["readouts"]) - 1))
            base = own.sample(f"{history}/baseline/{setting['id']}", ri)

            def diff(a, b):
                return max(abs(x) for x in am.flat(am.subtract(a, b)))

            values["block_effect"].append(diff(release["voltage_V"], base["voltage_V"]))
            values["post_release_change"].append(diff(final["voltage_V"], release["voltage_V"]))
            values["release_flux"].append(max(abs(x) for x in release["flux_fmol_per_s"]))
            values["block_gate_change"].append(diff(release["gate"], start["gate"]))
            for name, unit in units.items():
                magnitudes[name] = max(
                    magnitudes[name],
                    *(abs(x) for p in (start, release, final, base) for x in am.flat(p[unit])),
                )
        for name, metric in metrics.items():
            unit = units[name]
            threshold = 4 * original["inputs"]["trajectory_absolute_for_signal_only"][unit] + 2 * (
                original["inputs"]["reference"]["comparison_absolute"][unit]
                + original["inputs"]["comparison_relative"] * magnitudes[name]
            )
            c.require(
                threshold == metric["required_minimum"]
                and all(v >= threshold for v in values[name])
                and metric["pass"] is True,
                "Independent reference signal threshold failed",
            )
            c.require(
                all(
                    math.isclose(a, b, rel_tol=2e-11, abs_tol=1e-12)
                    for a, b in zip(values[name], metric["values_by_solver"], strict=True)
                ),
                "Signal columns differ",
            )
    primary = original["inputs"]["reference"]["primary"]
    a, b = (
        own.sample(
            f"{h}/suppression_release/{primary}",
            len(records[f"{h}/suppression_release/{primary}"]["readouts"]) - 1,
        )
        for h in ("a", "b")
    )
    diagnostic = {
        "final_a_minus_b_voltage_V": am.subtract(a["voltage_V"], b["voltage_V"]),
        "final_a_minus_b_open_fraction": am.subtract(
            [m * h for m, h in zip(*a["gate"], strict=True)],
            [m * h for m, h in zip(*b["gate"], strict=True)],
        ),
    }
    c.require(
        all(
            math.isclose(actual, expected, rel_tol=2e-11, abs_tol=1e-12)
            for name in diagnostic
            for actual, expected in zip(
                diagnostic[name], saved["history_diagnostic"][name], strict=True
            )
        ),
        "Independent signed history diagnostic differs",
    )
    summary = crossed.summary()
    c.require(
        summary["identities"] == c.read(ctx.PLAN)["reference_review_identities"]
        and summary["column_mismatches"] == summary["independent_numerical_rejections"] == 0,
        "Independent reference columns rejected",
    )
    return {
        "status": "piecewise_reference_review_closed",
        "independent": summary,
        "frozen_replay": saved,
        "independent_history_diagnostic": diagnostic,
        "reference_completion_sha256": ctx.REFERENCE_SHA,
        "reference_integrator_rerun": False,
        "model_imports": [],
        "release_response_qualified": False,
        "biology_validated": False,
        "gpu_tested": False,
    }
