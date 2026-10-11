"""D106 saved-data reconstruction with alternate numerical columns; no integration."""

from pathlib import Path
from unittest.mock import patch

import history_audit_replay as earlier
import release_audit_cells as cells_math
import release_audit_context as ctx
import release_audit_math as control
import timed_compare as frozen
import timed_native_check as native_check
from feedback_audit_replay import Audit as PriorAudit
from feedback_audit_replay import capture_write_guard, maximum_error, refinement_decision
from release_audit_native import Case, accumulated_atol

c, io, am = ctx.c, ctx.io, control.am
require = c.require


class Reference:
    """Use the closed D105 review; reconstruct only this audit's sample/side readouts."""

    def __init__(self, history, view):
        self.r, self.records, self.points, self.sides = view, {}, {}, {}
        for condition in view["protocol"]["variants"]:
            p, schedule = view["reference_parameters"][condition], view["schedules"][condition]
            for solve in view["protocol"]["reference"]["solves"]:
                key = condition + "/" + solve["id"]
                self.records[key] = io.read_compressed(
                    ctx.pilot.CAPTURE / "reference" / history / key / "result.json.gz"
                )
            primary = self.records[condition + "/" + view["protocol"]["reference"]["primary"]]
            points = []
            for time_s in view["protocol"]["common_times_s"]:
                index = primary["sample_times_s"].index(time_s)
                own = control.readout(
                    p, primary["sample_states"][index], control.availability(schedule, time_s)
                )
                saved = primary["readouts"][index]
                require(set(own) == set(saved), "Closed reference readout membership")
                for field in own:
                    am.ind.near(own[field], saved[field], 1e-15, 2e-11)
                points.append(saved)
            self.points[condition] = points
            self.sides[condition] = {"left": [], "right": []}
            for time_s in (view["protocol"]["duration_s"] / 4, view["protocol"]["duration_s"] / 2):
                index = primary["sample_times_s"].index(time_s)
                for side in self.sides[condition]:
                    self.sides[condition][side].append(
                        control.readout(
                            p,
                            primary["sample_states"][index],
                            control.availability(schedule, time_s, side),
                        )
                    )

    def primary_points(self, condition):
        return self.points[condition]


class History:
    def __init__(self, name, view, workers):
        self.name, self.r, self.workers = name, view, workers
        self.capture = ctx.CAPTURE / name
        self.native_points, self.native_sides = {}, {}
        self.native_arrays = self.native_charge = self.checkpoints = self.checkpoint_arrays = 0
        self.reference = Reference(name, view)
        self.cells = cells_math.Cells(
            view,
            {
                k: io.read_compressed(self.capture / p)
                for k, p in workers["cells"]["records"].items()
            },
            {
                k: io.read_compressed(self.capture / p)
                for k, p in workers["cells"]["resumed"].items()
            },
        )
        self.cells.side_probes(
            {
                k: io.read_compressed(self.capture / p)
                for k, p in workers["cells"]["side_probes"].items()
            }
        )
        self.prepared = c.read(ctx.prior.prior.pilot.audit.CAPTURE / "betse.json")["rows"]
        self.definitions_and_checkpoints()

    def definitions_and_checkpoints(self):
        prepared = self.prepared["active_channel/observed"]
        parameters = am.ready.parameters(
            prepared, "active_channel", self.r["preparation_registration"]["transport_protocol"]
        )
        require(
            all(parameters == p for p in self.r["reference_parameters"].values()),
            "Independent timed physical parameters",
        )
        sources = {
            str(path.relative_to(ctx.ROOT / "src/cells")): c.sha(path)
            for path in (ctx.ROOT / "src/cells").rglob("*.py")
        }
        require(len(sources) == 51, "Checkpoint source extent")
        layouts = {}
        for key, record in self.cells.records.items():
            condition, backend, _step = key.split("/")
            dt = record["definition"]["execution"]["dt"]
            expected = am.ready.expected_definition(
                prepared, "active_channel", dt, self.r["preparation_registration"]
            )
            expected["execution"]["jit"] = backend == "jax_jit"
            expected["experiment"]["end_time"] = self.r["protocol"]["duration_s"]
            expected["experiment"]["observation_times"] = self.r["protocol"]["common_times_s"]
            for row in expected["experiment"]["channel_controls"]:
                row["schedule"] = self.r["schedules"][condition]
            require(
                expected == self.r["cells_definitions"][key] == record["definition"],
                "Independent timed definition",
            )
            if backend not in layouts:
                layouts[backend] = cells_math.layout_contract("active_channel", self.name, backend)
            selected = [("final-checkpoint", record, len(record["times"]["values"]) - 1)]
            if key in self.cells.resumed:
                resumed = self.cells.resumed[key]
                selected += [
                    (
                        "midpoint-checkpoint",
                        record,
                        round(self.r["protocol"]["restart_time_s"] / dt),
                    ),
                    ("resumed-checkpoint", resumed, len(resumed["times"]["values"]) - 1),
                ]
            for name, row, index in selected:
                self.checkpoint_arrays += cells_math.checkpoint(
                    self.capture / "cells" / key / name, row, index, sources, layouts[backend]
                )
                self.checkpoints += 1
        require(
            self.checkpoints == 24 and self.checkpoint_arrays == 1296, "Timed checkpoint coverage"
        )

    def native_case(self, relative, absolute):
        key = "/".join(relative.parts[1:-1])
        paths = self.workers["betse"]["records"][self.name + "/" + key]
        a, b = (
            io.read_compressed(ctx.CAPTURE / paths[mode]) for mode in ("observed", "unobserved")
        )
        require(
            absolute["amount_fmol"] == accumulated_atol(self.r, a), "Native accumulation budget"
        )
        for row in (a, b):
            earlier.native_fixture(self.r, row, self.prepared["active_channel/observed"])
            ctx.prior.prior.native_partials(row, self.capture / "native" / key / row["mode"])
        case = Case(self.r, a, b)
        self.native_arrays += case.arrays
        self.native_charge += case.charge_snapshots
        self.native_points[key], self.native_sides[key] = case.points, case.sides
        return case

    def dynamic_resolve(self, name):
        parts = name.split("/")
        if parts[0] == "no_op":
            step = float(parts[1])
            a, b = (self.cells.points[v + f"/jax_jit/dt_{step:.8g}"] for v in ("baseline", "no_op"))
        elif parts[0] in ("native", "cells") and parts[2] in ("left", "right"):
            engine, condition, side = parts[:3]
            dt = self.r["protocol"][engine + "_steps_s"][-1]
            key = condition + ("/jax_jit" if engine == "cells" else "") + f"/dt_{dt:.8g}"
            points = self.cells.sides if engine == "cells" else self.native_sides
            a, b = points[key][side], self.reference.sides[condition][side]
        else:
            return PriorAudit.dynamic_resolve(self, name)
        j = parts.index("observation")
        index, field, tail = int(parts[j + 1]), parts[j + 2], parts[j + 3 :]
        left, right = (
            (am.interval_transfer(v, index) for v in (a, b))
            if field == "interval_transfer_fmol"
            else (a[index][field], b[index][field])
        )
        return am.component(left, tail), am.component(right, tail), field

    def decisions(self):
        protocol = self.r["protocol"]
        gate = c.read(ctx.pilot.CAPTURE / "reference-gate.json")
        dynamic = c.read(self.capture / "trajectory-comparison.json")["dynamic"]
        result = {}
        for condition in protocol["variants"]:
            primary = self.reference.records[condition + "/" + protocol["reference"]["primary"]]
            measured = dict.fromkeys(protocol["reference"]["comparison_absolute"], 0.0)
            for setting in protocol["reference"]["solves"]:
                if setting["id"] == protocol["reference"]["primary"]:
                    continue
                other = self.reference.records[condition + "/" + setting["id"]]
                for field in measured:
                    if field == "interval_transfer_fmol":
                        error = max(
                            abs(a - b)
                            for j in range(1, len(primary["readouts"]))
                            for a, b in zip(
                                am.interval_transfer(other["readouts"], j),
                                am.interval_transfer(primary["readouts"], j),
                                strict=True,
                            )
                        )
                    else:
                        error = maximum_error(other["readouts"], primary["readouts"], field)
                    measured[field] = max(measured[field], error)
            require(
                measured == gate["measured_reference_disagreement"][self.name + "/" + condition],
                "Independent timed reference-error floors",
            )
            for engine, grids, points, backend in (
                ("native", protocol["native_steps_s"], self.native_points, ""),
                ("cells", protocol["cells_steps_s"], self.cells.points, "/jax_jit"),
            ):
                rows = [points[condition + backend + f"/dt_{dt:.8g}"] for dt in grids]
                oracle, fields = self.reference.primary_points(condition), {}
                for field in protocol["refinement"]["required_fields"]:
                    values = [maximum_error(row, oracle, field) for row in rows]
                    changes = [maximum_error(rows[i], rows[i + 1], field) for i in range(2)]
                    fields[field] = refinement_decision(
                        values,
                        changes,
                        measured[field],
                        protocol["trajectory_absolute"][field],
                        protocol["refinement"],
                    )
                summary = {
                    "status": "pass" if all(v["passed"] for v in fields.values()) else "fail",
                    "fields": fields,
                }
                require(
                    summary == dynamic["refinements"][engine + "/" + condition],
                    "Independent timed refinement decision",
                )
                result[engine + "/" + condition] = summary
        return result


class Audit:
    contrast_points = earlier.Audit.contrast_points
    contrast_resolve = earlier.Audit.contrast_resolve

    def __init__(self, data, output):
        self.data, self.output = data, output
        self.r = data["registration"] | {
            "protocol": c.read(frozen.paired_compare.ctx.PROTOCOL)
            | {
                "variants": data["registration"]["plan"]["conditions"],
                "common_times_s": data["registration"]["plan"]["common_times_s"],
            }
        }
        self.histories = {
            name: History(
                name,
                view,
                {
                    "cells": data["workers"]["cells"]["by_history"][name],
                    "betse": data["workers"]["betse"],
                },
            )
            for name, view in self.r["views"].items()
        }
        self.ledgers, self.writes, self.contrasts = [], set(), {}

    def ledger_type(self, original, native=False):
        audit = self

        class TwinLedger(original):
            def __init__(self, absolute, relative=2e-11, failure_path=None):
                if native:
                    failure_path, relative = relative, absolute["relative"]
                require(failure_path is not None, "Unbound timed replay ledger")
                self.source_path = Path(failure_path).relative_to(ctx.CAPTURE)
                self.case, self.seen, self.budget_checked = None, set(), False
                name = self.source_path.as_posix()
                if self.source_path.parts[0] in audit.histories:
                    history = audit.histories[self.source_path.parts[0]]
                    local = Path(*self.source_path.parts[1:])
                    name, self.protocol = local.as_posix(), history.r["protocol"]
                    if name.startswith("native/"):
                        require(native, "Unintercepted native ledger")
                        self.case = history.native_case(local, absolute)
                        self.resolver, self.kind = self.case.resolve, "native"
                    elif name == "cells-state-failures.jsonl":
                        self.resolver, self.kind = history.cells.resolve_state, "cells_state"
                    elif name == "cells-side-failures.jsonl":
                        self.resolver, self.kind = history.cells.resolve_side, "cells_sides"
                    elif name.startswith("cells/"):
                        key = "/".join(local.parts[1:-1])
                        self.resolver, self.kind = (
                            lambda n: history.cells.resolve_pair(n, key),
                            "restart",
                        )
                    elif name.startswith("backend-"):
                        self.resolver, self.kind = history.cells.resolve_pair, "backend"
                    else:
                        require(name == "trajectory-failures.jsonl", "Unknown timed history ledger")
                        self.resolver, self.kind = history.dynamic_resolve, "trajectory"
                else:
                    require(name == "trajectory-failures.jsonl", "Unknown timed root ledger")
                    self.protocol = audit.r["views"]["a"]["protocol"]
                    self.resolver, self.kind = audit.contrast_resolve, "history_contrast"
                target = audit.output / "replayed" / self.source_path
                target.parent.mkdir(parents=True, exist_ok=True)
                if native:
                    super().__init__(absolute, target)
                else:
                    super().__init__(absolute, relative, target)
                self.independent = am.Crosscheck(audit.output / "independent-mismatches.jsonl")
                audit.ledgers.append(self)

            def compare(self, name, actual, expected, unit):
                if not isinstance(expected, list):
                    if not self.budget_checked and self.kind == "history_contrast":
                        multiplier = audit.r["protocol"][
                            "cross_engine_contrast_budget_multiplier"
                            if name.split("/")[2] == "cross_engine"
                            else "contrast_budget_multiplier"
                        ]
                        require(
                            self.absolute
                            == {
                                k: v * multiplier
                                for k, v in self.protocol["trajectory_absolute"].items()
                            }
                            and self.relative == self.protocol["comparison_relative"],
                            "Timed contrast budget",
                        )
                        self.budget_checked = True
                    if self.case is None:
                        require(name not in self.seen, "Duplicate timed numerical identity")
                        self.seen.add(name)
                    a, b, units = self.resolver(name)
                    require(units == unit, "Timed independent unit mismatch")
                    self.independent.add(
                        name, actual, expected, a, b, unit, self.absolute[unit], self.relative
                    )
                return super().compare(name, actual, expected, unit)

            def summary(self):
                if self.case is not None:
                    self.case.finish()
                    require(
                        self.case.accounting["means"] == self.remix_records
                        and self.case.accounting["diagnostics"] == self.original_guard_rejections,
                        "Independent complete mean/old-diagnostic records",
                    )
                return super().summary()

        return TwinLedger

    def recorded_write(self, path, value):
        relative = Path(path).relative_to(ctx.CAPTURE).as_posix()
        require(relative not in self.writes, "Duplicate timed output")
        saved = io.read_compressed(path) if relative.endswith(".gz") else c.read(path)
        require(value == saved, "Timed output does not replay: " + relative)
        self.writes.add(relative)

    def run(self):
        with (
            capture_write_guard(ctx.CAPTURE),
            capture_write_guard(ctx.pilot.CAPTURE),
            patch.object(io, "Ledger", self.ledger_type(io.Ledger)),
            patch.object(
                native_check, "Ledger", self.ledger_type(native_check.Ledger, native=True)
            ),
            patch.object(io, "write", self.recorded_write),
            patch.object(io, "write_compressed", self.recorded_write),
        ):
            print(
                "Reconstructing timed native boundaries, both-side readouts and full Cells state; "
                "no integration",
                flush=True,
            )
            comparison = frozen.check(
                self.data["registration"],
                ctx.CAPTURE,
                self.data["workers"]["betse"],
                self.data["workers"]["cells"],
            )
            require(
                comparison == c.read(ctx.CAPTURE / "comparison.json"),
                "Frozen timed comparison differs",
            )
        expected_writes = {"native-accounting.json.gz", "history-contrasts.json"} | {
            h + "/" + f
            for h in self.histories
            for f in (
                "cells-accounting.json.gz",
                "cells-sides.json.gz",
                "trajectory-comparison.json",
            )
        }
        require(self.writes == expected_writes, "Timed output coverage")
        preserved = {}
        for name in self.histories:
            relative = name + "/trajectory-failures.jsonl"
            original = [
                io.parse(line) for line in (ctx.CAPTURE / relative).read_text().splitlines()
            ]
            replayed = [
                io.parse(line)
                for line in (self.output / "replayed" / relative).read_text().splitlines()
            ]
            require(
                original == replayed
                and len(original)
                == self.data["plan"]["expected_coarse_rejections_by_history"][name],
                "Timed coarse rejections changed/omitted",
            )
            preserved[name] = len(original)
        groups = []
        for ledger in self.ledgers:
            independent = ledger.independent.summary()
            require(
                ledger.count == independent["identities"]
                and ledger.failed == independent["independent_numerical_rejections"],
                "Timed independent coverage/classification",
            )
            groups.append(
                {
                    "source": ledger.source_path.as_posix(),
                    "kind": ledger.kind,
                    "frozen": ledger.summary(),
                    "independent": independent,
                }
            )
        refinements = {
            name + "/" + k: v
            for name, h in self.histories.items()
            for k, v in h.decisions().items()
        }
        native = [ledger for ledger in self.ledgers if ledger.kind == "native"]
        counts = {
            "native_identities": sum(row.count for row in native),
            "total_identities": sum(row.count for row in self.ledgers),
            "ledger_groups": len(groups),
            "native_charge_snapshots": sum(v.native_charge for v in self.histories.values()),
            "native_array_records": sum(v.native_arrays for v in self.histories.values()),
            "zero_flux_means": sum(len(row.remix_records) for row in native),
            "original_identity_diagnostics": sum(
                len(row.original_guard_rejections) for row in native
            ),
            "numeric_checkpoints": sum(v.checkpoints for v in self.histories.values()),
            "checkpoint_arrays": sum(v.checkpoint_arrays for v in self.histories.values()),
            "refinement_groups": len(refinements),
            "history_contrast_groups": sum(v["kind"] == "history_contrast" for v in groups),
        }
        require(
            all(counts[k] == self.data["plan"][k] for k in counts),
            "Timed independent complete scope: " + str(counts),
        )
        return counts | {
            "groups": groups,
            "refinements": refinements,
            "frozen_comparisons_replayed": counts["total_identities"],
            "independent_identities": sum(v["independent"]["identities"] for v in groups),
            "independent_column_mismatches": sum(
                v["independent"]["column_mismatches"] for v in groups
            ),
            "observer_pairs": 24,
            "restart_pairs": 8,
            "backend_pairs": 8,
            "preserved_coarse_diagnostic_failures": sum(preserved.values()),
            "coarse_rejections_by_history": preserved,
            "closed_reference_review_identities_authenticated_not_replayed": 1485380,
        }
