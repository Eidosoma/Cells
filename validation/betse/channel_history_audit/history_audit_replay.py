"""Independent per-history reconstruction and frozen D099 replay; no simulator calls."""

from pathlib import Path
from unittest.mock import patch

import feedback_audit_math as am
import history_audit_cells as cells_math
import history_audit_context as ctx
import history_audit_math as hm
import paired_compare as frozen
from feedback_audit_native import Case, accumulated_atol
from feedback_audit_replay import Audit as PriorAudit
from feedback_audit_replay import capture_write_guard, maximum_error, refinement_decision
from history_audit_reference import Reference

c, io, require = ctx.c, ctx.io, am.require


def native_fixture(view, row, original):
    """Anchor physical preparation while independently allowing only declared gate changes."""
    require(row["phase"] == "INIT" and row["id"] == original["id"], "Native fixture phase/identity")
    for name in ("settings", "geometry", "source_constants", "core_initial"):
        require(row[name] == original[name], "Native physical preparation changed: " + name)
    f, base, gates = row["fixture"], original["fixture"], view["protocol"]["initial_gate"]
    require(
        f["applications"] == 1
        and f["declared_gate"] == gates
        and row["fixture_hook"] == {"calls": 1, "returns": 1}
        and row["hook_restored"] is True,
        "Native fixture application",
    )
    require(
        f["before"] == base["before"] and f["metadata"] == base["metadata"],
        "Native pre-fixture preparation/metadata",
    )
    require(
        f["after"]["physical"] == base["after"]["physical"]
        and f["after"]["network_current"] == base["after"]["network_current"],
        "Native fixture physical side effect",
    )
    actual, previous = f["after"]["channel"], base["after"]["channel"]
    require(set(actual) == set(previous), "Native channel fields")
    for name in actual:
        if name not in ("m", "h", "derived_m_times_h"):
            require(actual[name] == previous[name], "Native non-gate fixture side effect")
    count = row["geometry"]["membrane_count"]
    require(
        actual["m"] == [gates[0]] * count and actual["h"] == [gates[1]] * count,
        "Native wrong history",
    )
    require(
        actual["derived_m_times_h"] == [gates[0] * gates[1]] * count,
        "Native derived initial opening",
    )
    if row["mode"] == "observed":
        require(
            row["trace"]["initial"]["physical"] == original["trace"]["initial"]["physical"]
            and row["trace"]["initial"]["channel"] == actual,
            "Native full-loop initial state",
        )


class History:
    dynamic_resolve = PriorAudit.dynamic_resolve

    def __init__(self, name, view, workers):
        self.name, self.r, self.workers = name, view, workers
        self.capture = ctx.CAPTURE / name
        self.native_points = {}
        self.native_arrays = self.native_charge = self.checkpoints = self.checkpoint_arrays = 0
        self.reference = Reference(
            view,
            {
                key: io.read_compressed(self.capture / path)
                for key, path in workers["reference"]["records"].items()
            },
        )
        self.cells = cells_math.Cells(
            view,
            {
                key: io.read_compressed(self.capture / path)
                for key, path in workers["cells"]["records"].items()
            },
            {
                key: io.read_compressed(self.capture / path)
                for key, path in workers["cells"]["resumed"].items()
            },
        )
        self.prepared = c.read(ctx.prior.pilot.audit.CAPTURE / "betse.json")["rows"]
        self.definitions_and_checkpoints()

    def definitions_and_checkpoints(self):
        physics = self.r["preparation_registration"]["transport_protocol"]
        for variant in self.r["protocol"]["variants"]:
            require(
                am.ready.parameters(self.prepared[variant + "/observed"], variant, physics)
                == self.r["reference_parameters"][variant],
                "Independent paired parameters",
            )
        sources = {
            str(path.relative_to(ctx.ROOT / "src/cells")): c.sha(path)
            for path in (ctx.ROOT / "src/cells").rglob("*.py")
        }
        require(len(sources) == 51, "Checkpoint source extent")
        layouts = {}
        for key, record in self.cells.records.items():
            variant, backend, _step = key.split("/")
            dt = record["definition"]["execution"]["dt"]
            expected = am.ready.expected_definition(
                self.prepared[variant + "/observed"],
                variant,
                dt,
                self.r["preparation_registration"],
            )
            expected["execution"]["jit"] = backend == "jax_jit"
            require(
                expected == self.r["cells_definitions"][key] == record["definition"],
                "Independently reconstructed paired definition",
            )
            layout_key = variant, backend
            if layout_key not in layouts:
                layouts[layout_key] = cells_math.layout_contract(variant, self.name, backend)
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
                    self.capture / "cells" / key / name, row, index, sources, layouts[layout_key]
                )
                self.checkpoints += 1
        require(
            self.checkpoints == 12 and self.checkpoint_arrays == 648,
            "Per-history checkpoint coverage",
        )

    def native_case(self, relative, absolute):
        key = "/".join(relative.parts[1:-1])
        paths = self.workers["betse"]["records"][key]
        a, b = (
            io.read_compressed(self.capture / paths[mode]) for mode in ("observed", "unobserved")
        )
        require(
            absolute["amount_fmol"] == accumulated_atol(self.r, a), "Native accumulation budget"
        )
        for row in (a, b):
            native_fixture(self.r, row, self.prepared[row["id"] + "/observed"])
            ctx.prior.native_partials(row, self.capture / "native" / key / row["mode"])
        case = Case(self.r, a, b)
        self.native_arrays += case.arrays
        self.native_charge += case.charge_snapshots
        self.native_points[key] = case.points
        return case

    def decisions(self):
        protocol = self.r["protocol"]
        gate = io.read_compressed(self.capture / "reference-gate.json.gz")
        dynamic = c.read(self.capture / "trajectory-comparison.json")
        result = {}
        for variant in protocol["variants"]:
            primary = self.reference.records[variant + "/" + protocol["reference"]["primary"]]
            measured = dict.fromkeys(protocol["reference"]["comparison_absolute"], 0.0)
            for setting in protocol["reference"]["solves"]:
                if setting["id"] == protocol["reference"]["primary"]:
                    continue
                other = self.reference.records[variant + "/" + setting["id"]]
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
                measured == gate["measured_reference_disagreement"][variant],
                "Independent reference-error floors differ",
            )
            for engine, grids, points, backend in (
                ("native", protocol["native_steps_s"], self.native_points, ""),
                ("cells", protocol["cells_steps_s"], self.cells.points, "/jax_jit"),
            ):
                rows = [points[variant + backend + f"/dt_{dt:.8g}"] for dt in grids]
                oracle, fields = self.reference.primary_points(variant), {}
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
                    summary == dynamic["refinements"][engine + "/" + variant],
                    "Independent refinement decision differs",
                )
                result[engine + "/" + variant] = summary
        return result


def independent_signal(protocol, histories, saved):
    require(set(histories) == {"a", "b"}, "Signal history membership")
    result = {}
    for variant in protocol["variants"]:
        initial, final = [], []
        for name in ("a", "b"):
            ref = histories[name].reference
            key = variant + "/" + histories[name].r["protocol"]["reference"]["primary"]
            row = ref.records[key]
            require(
                row["sample_times_s"][-1] == protocol["candidate_duration_s"], "Signal final clock"
            )
            initial.append(ref.own(key, 0))
            final.append(ref.own(key, len(row["sample_times_s"]) - 1))
        require(set(initial[0]) == set(initial[1]), "Signal initial fields")
        for field in initial[0]:
            if field != "gate":
                require(initial[0][field] == initial[1][field], "Reference initial confound")
        voltage = hm.subtract(final[0]["voltage_V"], final[1]["voltage_V"])
        opened = hm.subtract(
            *[[m * h for m, h in zip(*point["gate"], strict=True)] for point in final]
        )
        am.ind.near(voltage, saved[variant]["voltage_contrast_V"], 1e-15, 0)
        am.ind.near(opened, saved[variant]["open_fraction_contrast"], 1e-14, 0)
        if variant == "active_channel":
            require(
                min(map(abs, voltage)) >= protocol["minimum_final_voltage_contrast_V"]
                and min(map(abs, opened)) >= protocol["minimum_final_open_fraction_contrast"],
                "Independent history signal below registered gate",
            )
        else:
            require(all(v == 0 for v in voltage), "Independent blocked voltage contrast")
        result[variant] = {"voltage_contrast_V": voltage, "open_fraction_contrast": opened}
    return result


class Audit:
    def __init__(self, data, output):
        self.data, self.r, self.output = data, data["registration"], output
        self.histories = {
            name: History(
                name,
                view,
                {kind: worker["by_history"][name] for kind, worker in data["workers"].items()},
            )
            for name, view in self.r["views"].items()
        }
        self.ledgers, self.writes, self.contrasts = [], set(), {}

    def contrast_points(self, engine, variant):
        identity = engine, variant
        if identity not in self.contrasts:
            paired = []
            for name in ("a", "b"):
                history = self.histories[name]
                if engine == "reference":
                    points = history.reference.primary_points(variant)
                elif engine == "native":
                    points = history.native_points[
                        variant + f"/dt_{self.r['protocol']['native_steps_s'][-1]:.8g}"
                    ]
                else:
                    require(engine == "cells", "Unknown contrast engine")
                    points = history.cells.points[
                        variant + f"/jax_jit/dt_{self.r['protocol']['cells_steps_s'][-1]:.8g}"
                    ]
                paired.append(points)
            for field in paired[0][0]:
                if field != "gate":
                    require(
                        paired[0][0][field] == paired[1][0][field], "Initial engine pair confound"
                    )
            self.contrasts[identity] = hm.contrast(*paired)
        return self.contrasts[identity]

    def contrast_resolve(self, name):
        parts = name.split("/")
        require(parts[0] == "history_contrast" and parts[3] == "observation", "Contrast identity")
        variant, engine, index, field, tail = parts[1], parts[2], int(parts[4]), parts[5], parts[6:]
        left, right = ("native", "cells") if engine == "cross_engine" else (engine, "reference")
        a, b = (self.contrast_points(e, variant) for e in (left, right))
        actual, expected = (
            (am.interval_transfer(v, index) for v in (a, b))
            if field == "interval_transfer_fmol"
            else (a[index][field], b[index][field])
        )
        return am.component(actual, tail), am.component(expected, tail), field

    def ledger_type(self, original):
        audit = self

        class TwinLedger(original):
            def __init__(self, absolute, relative=2e-11, failure_path=None):
                require(failure_path is not None, "Unbound paired replay ledger")
                self.source_path = Path(failure_path).relative_to(ctx.CAPTURE)
                self.case, self.seen, self.budget_checked = None, set(), False
                name = self.source_path.as_posix()
                if self.source_path.parts[0] in audit.histories:
                    history = audit.histories[self.source_path.parts[0]]
                    local = Path(*self.source_path.parts[1:])
                    name = local.as_posix()
                    self.protocol = history.r["protocol"]
                    if name.startswith("native/"):
                        self.case = history.native_case(local, absolute)
                        self.resolver, self.kind = self.case.resolve, "native"
                    elif name == "reference-failures.jsonl":
                        self.resolver, self.kind = history.reference.resolve, "reference"
                    elif name == "reference-dense-failures.jsonl":
                        self.resolver, self.kind = (
                            lambda n: history.reference.resolve(n, dense=True),
                            "reference_dense",
                        )
                    elif name == "cells-state-failures.jsonl":
                        self.resolver, self.kind = history.cells.resolve_state, "cells_state"
                    elif name.startswith("cells/"):
                        key = "/".join(local.parts[1:-1])
                        self.resolver, self.kind = (
                            lambda n: history.cells.resolve_pair(n, key),
                            "restart",
                        )
                    elif name.startswith("backend-"):
                        self.resolver, self.kind = history.cells.resolve_pair, "backend"
                    else:
                        require(name == "trajectory-failures.jsonl", "Unknown history ledger")
                        self.resolver, self.kind = history.dynamic_resolve, "trajectory"
                else:
                    require(name == "trajectory-failures.jsonl", "Unknown root ledger")
                    self.protocol = audit.r["views"]["a"]["protocol"]
                    self.resolver, self.kind = audit.contrast_resolve, "history_contrast"
                target = audit.output / "replayed" / self.source_path
                target.parent.mkdir(parents=True, exist_ok=True)
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
                            "Contrast budget changed",
                        )
                        self.budget_checked = True
                    if self.case is None:
                        require(name not in self.seen, "Duplicate paired numerical identity")
                        self.seen.add(name)
                    a, b, units = self.resolver(name)
                    require(units == unit, "Paired independent unit mismatch")
                    self.independent.add(
                        name, actual, expected, a, b, unit, self.absolute[unit], self.relative
                    )
                return super().compare(name, actual, expected, unit)

            def summary(self):
                if self.case is not None:
                    self.case.finish()
                return super().summary()

        return TwinLedger

    def recorded_write(self, path, value):
        relative = Path(path).relative_to(ctx.CAPTURE).as_posix()
        require(relative not in self.writes, "Duplicate paired output")
        saved = io.read_compressed(path) if relative.endswith(".gz") else c.read(path)
        require(value == saved, "Paired output does not replay: " + relative)
        self.writes.add(relative)

    def run(self):
        with (
            capture_write_guard(ctx.CAPTURE),
            patch.object(io, "Ledger", self.ledger_type(io.Ledger)),
            patch.object(io, "write", self.recorded_write),
            patch.object(io, "write_compressed", self.recorded_write),
        ):
            print(
                "Replaying both reference histories with alternate mathematical columns", flush=True
            )
            references = frozen.references(self.r, ctx.CAPTURE, self.data["workers"]["reference"])
            print(
                "Replaying native boundaries, full Cells states, restarts and paired contrasts",
                flush=True,
            )
            comparison = frozen.check(
                self.r,
                ctx.CAPTURE,
                references,
                self.data["workers"]["betse"],
                self.data["workers"]["cells"],
            )
            require(
                comparison == c.read(ctx.CAPTURE / "comparison.json"),
                "Paired frozen summary differs",
            )
        expected_writes = {"reference-gate.json", "history-contrasts.json"} | {
            name + "/" + file
            for name in self.histories
            for file in (
                "reference-gate.json.gz",
                "native-accounting.json.gz",
                "cells-accounting.json.gz",
                "trajectory-comparison.json",
            )
        }
        require(self.writes == expected_writes, "Paired replay output coverage")
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
                "Paired coarse rejections changed/omitted",
            )
            preserved[name] = len(original)
        groups = []
        for ledger in self.ledgers:
            independent = ledger.independent.summary()
            require(
                ledger.count == independent["identities"]
                and ledger.failed == independent["independent_numerical_rejections"],
                "Paired independent coverage/classification",
            )
            groups.append(
                {
                    "source": ledger.source_path.as_posix(),
                    "kind": ledger.kind,
                    "frozen": ledger.summary(),
                    "independent": independent,
                }
            )
        native_count = sum(v["independent"]["identities"] for v in groups if v["kind"] == "native")
        require(
            native_count == 7367280
            and sum(v.native_charge for v in self.histories.values()) == 2264,
            "Native complete paired coverage",
        )
        require(
            sum(v["kind"] == "history_contrast" for v in groups) == 6, "History contrast coverage"
        )
        refinements = {
            name + "/" + k: v
            for name, h in self.histories.items()
            for k, v in h.decisions().items()
        }
        signal = independent_signal(
            self.r["protocol"],
            self.histories,
            c.read(ctx.CAPTURE / "reference-gate.json")["signal"],
        )
        return {
            "groups": groups,
            "refinements": refinements,
            "independent_signal": signal,
            "frozen_comparisons_replayed": sum(v["frozen"]["comparisons"] for v in groups),
            "independent_identities": sum(v["independent"]["identities"] for v in groups),
            "independent_column_mismatches": sum(
                v["independent"]["column_mismatches"] for v in groups
            ),
            "native_identities": native_count,
            "native_charge_snapshots": sum(v.native_charge for v in self.histories.values()),
            "native_array_records": sum(v.native_arrays for v in self.histories.values()),
            "numeric_checkpoints": sum(v.checkpoints for v in self.histories.values()),
            "checkpoint_arrays": sum(v.checkpoint_arrays for v in self.histories.values()),
            "observer_pairs": 12,
            "restart_pairs": 4,
            "backend_pairs": 4,
            "preserved_coarse_diagnostic_failures": sum(preserved.values()),
            "coarse_rejections_by_history": preserved,
            "refinement_groups": len(refinements),
            "history_contrast_groups": 6,
            "reference_solves_replayed_not_rerun": 12,
        }
