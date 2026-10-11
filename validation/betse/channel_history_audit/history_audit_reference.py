"""D100 explicit-history reference identities with alternate saved-state algebra."""

import bisect
import math

import history_audit_math as am

require = am.require


class Reference:
    def __init__(self, r, records):
        self.r, self.records, self.calculated = r, records, {}
        p = r["protocol"]
        require(
            set(records)
            == {v + "/" + s["id"] for v in p["variants"] for s in p["reference"]["solves"]},
            "Independent reference coverage",
        )
        for key, record in records.items():
            variant, setting_id = key.split("/")
            setting = next(s for s in p["reference"]["solves"] if s["id"] == setting_id)
            self.validate(record, r["reference_parameters"][variant], setting, p)

    @staticmethod
    def validate(record, parameters, setting, protocol):
        n = len(parameters["volume_pL"])
        active = [i for i, v in enumerate(parameters["channel_enabled"]) if v]
        require(
            record["state_axes"]
            == {
                "cell_count": n,
                "channel_cell_indices": active,
                "order": ["q_fmol", "m_active", "h_active", "energy_pJ"],
            },
            "Reference coordinate metadata",
        )
        require(
            record["setting"] == setting and record["initial_gate"] == protocol["initial_gate"],
            "Reference solver setting/history",
        )
        times, states, intervals = (
            record["accepted_times_s"],
            record["accepted_states"],
            record["dense_intervals"],
        )
        require(
            len(times) == len(states) == len(intervals) + 1
            and times[0] == 0
            and times[-1] == protocol["duration_s"],
            "Reference accepted grid extent",
        )
        require(
            states[0] == am.initial(parameters, protocol["initial_gate"]),
            "Reference initial coordinates",
        )
        for i, interval in enumerate(intervals):
            require(
                0 < times[i + 1] - times[i] <= setting["max_step_s"] * (1 + 1e-12),
                "Reference accepted step limit",
            )
            require(
                (interval["left_s"], interval["right_s"], interval["y_left"], interval["method"])
                == (times[i], times[i + 1], states[i], setting["method"]),
                "Reference dense boundary metadata",
            )
        stats = record["stats"]
        require(
            stats["success"] is True
            and stats["status"] == 0
            and stats["accepted_steps"] == len(intervals),
            "Reference solver completion",
        )
        require(
            0
            < stats["nfev"]
            <= stats["rhs_calls_including_jacobian"]
            <= protocol["reference"]["max_rhs_calls_per_solve"]
            and len(intervals) <= protocol["reference"]["max_accepted_steps_per_solve"],
            "Reference solver resource counters",
        )
        require(
            all(
                type(stats[k]) is int and stats[k] >= 0
                for k in ("nfev", "njev", "nlu", "rhs_calls_including_jacobian", "accepted_steps")
            ),
            "Reference integer counters",
        )
        require(
            math.isfinite(stats["elapsed_seconds"]) and stats["elapsed_seconds"] > 0,
            "Reference solve timing",
        )
        tick, end = protocol["reference"]["sample_dt_s"], protocol["duration_s"]
        expected = [i * tick for i in range(round(end / tick))] + [end]
        require(
            record["sample_times_s"] == expected
            and len(record["sample_states"]) == len(record["readouts"]) == len(expected),
            "Reference common sample grid",
        )
        for state in states:
            am.readout(parameters, state)

    def own(self, key, index):
        identity = key, index
        if identity not in self.calculated:
            p = self.r["reference_parameters"][key.split("/")[0]]
            state = self.records[key]["sample_states"][index]
            result = am.readout(p, state)
            require(all(v >= -1e-12 for v in result["energy_pJ"]), "Negative reference energy")
            if not key.startswith("active_channel/"):
                require(
                    all(v == 0 for v in result["transfer_fmol"] + result["energy_pJ"]),
                    "Inactive reference transfer",
                )
            self.calculated[identity] = result
        return self.calculated[identity]

    def resolve(self, name, dense=False):
        parts = name.split("/")
        key, action, index = "/".join(parts[:2]), parts[2], int(parts[3])
        row, p = self.records[key], self.r["reference_parameters"][parts[0]]
        tail = parts[4:]
        if dense:
            if action == "sample":
                time_s = row["sample_times_s"][index]
                interval = max(0, bisect.bisect_left(row["accepted_times_s"], time_s) - 1)
                actual, expected = (
                    row["sample_states"][index],
                    am.dense(row["dense_intervals"][interval], time_s),
                )
            else:
                require(action == "accepted", "Unknown reference dense identity")
                interval = row["dense_intervals"][index]
                actual, expected = (
                    row["accepted_states"][index + 1],
                    am.dense(interval, interval["right_s"]),
                )
            unit = "state"
        elif action == "readout":
            unit, tail = tail[0], tail[1:]
            actual, expected = row["readouts"][index][unit], self.own(key, index)[unit]
        elif action == "thermodynamics":
            q, _m, _h, energy = am.unpack(p, row["sample_states"][index])
            actual, expected, unit = math.fsum(energy), am.dissipated(p, q), "energy_pJ"
        elif action == "analytic":
            cell, tail = int(tail[0]), tail[1:]
            actual = [row["readouts"][index]["gate"][j][cell] for j in range(2)]
            expected, unit = (
                am.analytic_gate(
                    p["initial_voltage_V"][cell],
                    row["sample_times_s"][index],
                    self.r["protocol"]["initial_gate"],
                ),
                "gate",
            )
        else:
            require(action == "agreement", "Unknown reference identity")
            unit, tail = tail[0], tail[1:]
            primary = self.records[parts[0] + "/" + self.r["protocol"]["reference"]["primary"]]
            if unit == "interval_transfer_fmol":
                actual, expected = (
                    am.interval_transfer(record["readouts"], index) for record in (row, primary)
                )
            else:
                actual, expected = row["readouts"][index][unit], primary["readouts"][index][unit]
        return am.component(actual, tail), am.component(expected, tail), unit

    def primary_points(self, variant):
        row = self.records[variant + "/" + self.r["protocol"]["reference"]["primary"]]
        return [
            row["readouts"][row["sample_times_s"].index(t)]
            for t in self.r["protocol"]["common_times_s"]
        ]
