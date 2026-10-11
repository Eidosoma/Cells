"""Independent timed Cells state, both-side RHS, and full checkpoint reconstruction."""

import feedback_audit_math as am
import release_audit_context as ctx
import release_audit_math as control
from feedback_audit_cells import Cells as PriorCells
from feedback_audit_cells import digest, packed, points
from history_audit_cells import layout_contract as layout_contract
from history_audit_cells import raw_array as raw_array
from history_audit_cells import raw_checkpoint

require, ind, ready = am.require, am.ind, am.ready


def initial_from_definition(definition):
    state = {name: ready.zeros(shape) for name, shape in ready.STATE_SHAPES.items()}
    channels = [
        entry["channel"] for entry in definition["model"]["cells"] if entry["channel"] is not None
    ]
    require(len(channels) <= len(state["gate"][0]), "Initial channel extent")
    for i, channel in enumerate(channels):
        gates = channel["initial_gate"]
        require(set(gates) == {"m", "h"}, "Initial gate fields")
        for j, name in enumerate(("m", "h")):
            value = ind.finite(gates[name])
            require(0 <= value <= 1, "Initial gate domain")
            state["gate"][j][i] = value
    return state


class Cells(PriorCells):
    def validate(self, key, row):
        p, definition = (
            self.r["reference_parameters"][key.split("/")[0]],
            self.r["cells_definitions"][key],
        )
        enabled = any(p["channel_enabled"])
        times, history, obs = self.values[key]
        dt, end = definition["execution"]["dt"], definition["experiment"]["end_time"]
        count = round(end / dt)
        require(
            row["id"] == key and row["definition"] == row["canonical_definition"] == definition,
            "Cells definition identity",
        )
        require(
            row["runtime"] == self.r["preparation_registration"]["cells_runtime"],
            "Cells runtime identity",
        )
        require(
            row["start_step"] == 0
            and row["final_step_index"] == count
            and times == [i * dt for i in range(count)] + [end],
            "Cells full accepted clock",
        )
        require(set(history) == set(ready.STATE_SHAPES), "Cells complete history membership")
        initial = initial_from_definition(definition)
        for name, shape in ready.STATE_SHAPES.items():
            require(
                row["history"][name]["shape"] == [count + 1, *shape]
                and history[name][0] == initial[name],
                "Cells history shape/initial state",
            )
        for j in range(len(times)):
            state = {name: values[j] for name, values in history.items()}
            inactive = [
                state[k]
                for k in (
                    "leak_transferred",
                    "pump_cycles",
                    "junction_gate",
                    "junction_transferred",
                    "junction_dissipated_energy_pJ",
                )
            ]
            inactive += [
                state["amount_increment"][0],
                state["amount_increment"][2],
                state["extracellular_amount_increment"][0],
                state["extracellular_amount_increment"][2],
                [v[7:] for v in state["amount_increment"]],
                [v[1:] for v in state["extracellular_amount_increment"]],
                [v[7:] for v in state["gate"]],
                state["channel_transferred"][7:],
                state["dissipated_energy_pJ"][7:],
            ]
            if not enabled:
                inactive += [state["gate"]]
            require(all(v == 0 for v in am.flat(inactive)), "Cells inactive state/padding")
            schedule = self.r["schedules"][key.split("/")[0]]
            own = control.readout(
                p, packed(history, j, enabled), control.availability(schedule, times[j])
            )
            if j and control.availability(schedule, times[j - 1]) == 0:
                for field in (
                    "amount_increment",
                    "extracellular_amount_increment",
                    "dissipated_energy_pJ",
                    "channel_transferred",
                ):
                    require(
                        history[field][j] == history[field][j - 1],
                        "Independent blocked Cells carry",
                    )
            require(all(v >= -1e-12 for v in own["energy_pJ"]), "Cells negative dissipation")
        require(
            obs["times"] == self.r["protocol"]["common_times_s"], "Cells common observation grid"
        )
        self.points[key] = points(obs)
        self.own_points[key] = [
            control.readout(
                p, packed(history, round(t / dt), enabled), control.availability(schedule, t)
            )
            for t in obs["times"]
        ]

    def side_probes(self, records):
        self.sides, self.side_metrics = {}, {}
        require(set(records) == set(self.records), "Independent Cells side coverage")
        for key, rows in records.items():
            definition = self.r["cells_definitions"][key]
            condition = key.split("/")[0]
            schedule, p = self.r["schedules"][condition], self.r["reference_parameters"][condition]
            require(
                [r["time_s"] for r in rows]
                == [self.r["protocol"]["duration_s"] / 4, self.r["protocol"]["duration_s"] / 2],
                "Independent Cells side clock",
            )
            sides = {"left": [], "right": []}
            for row in rows:
                index = round(row["time_s"] / definition["execution"]["dt"])
                state = {k: v[index] for k, v in self.values[key][1].items()}
                require(row["state"] == state, "Independent complete side state")
                for side in sides:
                    u = control.availability(schedule, row["time_s"], side)
                    actual = row[side]
                    require(actual["availability"] == u, "Independent side availability")
                    rhs, rates = control.full_rhs(definition, p, state, u)
                    require(set(actual["rhs"]) == set(rhs), "Independent complete side RHS")
                    prefix = f"{key}/{row['time_s']}/{side}"
                    for name, expected in rhs.items():
                        unit = (
                            "gate_rate_per_s"
                            if name == "gate"
                            else "power_pJ_per_s"
                            if "energy" in name
                            else "flux_fmol_per_s"
                        )
                        self.side_metrics[prefix + "/rhs/" + name] = (
                            actual["rhs"][name],
                            expected,
                            unit,
                        )
                        if u == 0 and name != "gate":
                            require(
                                all(v == 0 for v in am.flat(actual["rhs"][name])),
                                "Independent blocked RHS",
                            )
                    for name, field in (
                        ("flux_fmol_per_s", "inward_K_fmol_per_s"),
                        ("permeability_m_per_s", "permeability_m_per_s"),
                        ("power_pJ_per_s", "dissipation_pJ_per_s"),
                    ):
                        expected = rates[field] + [0.0] * (
                            definition["execution"]["channel_capacity"] - 7
                        )
                        self.side_metrics[prefix + "/" + name] = (actual[name], expected, name)
                    value = control.readout(p, packed(self.values[key][1], index, True), u)
                    value.update(
                        flux_fmol_per_s=actual["flux_fmol_per_s"][:7],
                        permeability_m_per_s=actual["permeability_m_per_s"][:7],
                        inward_current_A=[
                            p["F"] * 1e-15 * v for v in actual["flux_fmol_per_s"][:7]
                        ],
                    )
                    sides[side].append(value)
            self.sides[key] = sides

    def resolve_side(self, name):
        parts = name.split("/")
        count = 7 if parts[5] == "rhs" else 6
        a, b, unit = self.side_metrics["/".join(parts[:count])]
        return am.component(a, parts[count:]), am.component(b, parts[count:]), unit


def event_index(definition, time_s):
    experiment = definition["experiment"]
    schedules = [row[name] for row in experiment["membrane_controls"] for name in ("leak", "pump")]
    schedules += [row["schedule"] for row in experiment["channel_controls"]]
    require(not experiment["junction_controls"], "Timed checkpoint junction scope")
    times = sorted({row["time"] for schedule in schedules for row in schedule})
    require(times and times[0] == 0 and time_s >= 0, "Independent event origin")
    return sum(t <= time_s for t in times) - 1


def checkpoint(directory, record, index, source_hashes, layout):
    manifest = ctx.c.read(directory / "manifest.json")
    require(
        set(manifest)
        == {
            "schema_version",
            "kind",
            "spec",
            "spec_sha256",
            "clock",
            "random_state",
            "runtime",
            "source_hashes",
            "state_sha256",
            "manifest_sha256",
        },
        "Paired checkpoint manifest fields",
    )
    require(
        manifest["manifest_sha256"]
        == digest({k: v for k, v in manifest.items() if k != "manifest_sha256"}),
        "Paired checkpoint manifest digest",
    )
    require(
        manifest["schema_version"] == 1
        and manifest["kind"] == "cells_complete_numerical_checkpoint"
        and manifest["random_state"] is None,
        "Paired checkpoint kind",
    )
    require(
        manifest["spec"] == record["definition"] == record["canonical_definition"]
        and manifest["spec_sha256"] == digest(record["canonical_definition"]),
        "Paired checkpoint definition",
    )
    require(
        manifest["runtime"] == record["runtime"] and manifest["source_hashes"] == source_hashes,
        "Paired checkpoint runtime/source",
    )
    require(
        manifest["clock"]
        == {
            "time": record["times"]["values"][index],
            "step_index": record["start_step"] + index,
            "event_index": event_index(record["definition"], record["times"]["values"][index]),
        },
        "Paired checkpoint full clock",
    )
    require(
        manifest["state_sha256"] == ctx.c.sha(directory / "state.npz"),
        "Paired checkpoint file digest",
    )
    expected = layout | {
        name: {
            "dtype": "<f8",
            "shape": shape,
            "sha256": ctx.prior.pilot.review.numeric_digest(
                {"dtype": "<f8", "values": record["history"][name]["values"][index]}
            ),
        }
        for name, shape in ready.STATE_SHAPES.items()
    }
    require(
        raw_checkpoint(directory / "state.npz") == expected, "Paired complete state/layout bytes"
    )
    return len(expected)
