"""Frozen replay with independent streaming columns and guarded output redirection."""

import builtins
import importlib
import io as stdio
import os
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import feedback_audit_context as ctx
import feedback_audit_math as am
from feedback_audit_cells import Cells, checkpoint
from feedback_audit_native import Case, accumulated_atol
from feedback_audit_reference import Reference

c, io, require = ctx.c, ctx.io, am.require
frozen_reference = importlib.import_module("feedback_reference_check")
frozen_compare = importlib.import_module("feedback_compare")


@contextmanager
def capture_write_guard(capture):
    """Reject any accidental write open on the immutable capture, including NPZ."""
    original_open, original_io_open, original_os_open = builtins.open, stdio.open, os.open

    def check(path, writing):
        if writing and not isinstance(path, int):
            resolved = Path(os.fsdecode(path)).resolve()
            require(not resolved.is_relative_to(capture), "Write into immutable capture forbidden")

    def guarded_open(path, mode="r", *args, **kwargs):
        check(path, any(ch in mode for ch in "wax+"))
        return original_open(path, mode, *args, **kwargs)

    def guarded_io_open(path, mode="r", *args, **kwargs):
        check(path, any(ch in mode for ch in "wax+"))
        return original_io_open(path, mode, *args, **kwargs)

    def guarded_os_open(path, flags, *args, **kwargs):
        check(path, flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        return original_os_open(path, flags, *args, **kwargs)

    with (
        patch.object(builtins, "open", guarded_open),
        patch.object(stdio, "open", guarded_io_open),
        patch.object(os, "open", guarded_os_open),
    ):
        yield


def refinement_decision(values, own, reference_error, budget, policy):
    floor = max(
        budget * policy["roundoff_fraction_of_budget"],
        policy["reference_error_floor_multiplier"] * reference_error,
    )
    passed = all(
        second <= floor or second <= policy["required_error_ratio_max"] * first
        for first, second in ((values[0], values[1]), (values[1], values[2]), (own[0], own[1]))
    )
    return {
        "errors_to_reference": values,
        "own_refinement_differences": own,
        "floor": floor,
        "classification": "reference_or_roundoff_limited"
        if max(values + own) <= floor
        else "resolved_refinement",
        "passed": passed,
    }


def maximum_error(left, right, field):
    return max(
        abs(a - b)
        for x, y in zip(left, right, strict=True)
        for a, b in zip(am.flat(x[field]), am.flat(y[field]), strict=True)
    )


class Audit:
    def __init__(self, data, output):
        self.data, self.r, self.output = data, data["registration"], output
        self.ledgers, self.native_points, self.writes = [], {}, set()
        self.native_arrays = self.native_charge = self.checkpoint_arrays = self.checkpoints = 0
        self.reference = Reference(
            self.r,
            {
                key: io.read_compressed(ctx.CAPTURE / path)
                for key, path in data["workers"]["reference"]["records"].items()
            },
        )
        cells = data["workers"]["cells"]
        records = {
            key: io.read_compressed(ctx.CAPTURE / path) for key, path in cells["records"].items()
        }
        resumed = {
            key: io.read_compressed(ctx.CAPTURE / path) for key, path in cells["resumed"].items()
        }
        self.cells = Cells(self.r, records, resumed)
        self.definitions_and_checkpoints()

    def definitions_and_checkpoints(self):
        previous = c.read(ctx.pilot.audit.CAPTURE / "betse.json")["rows"]
        physics = self.r["preparation_registration"]["transport_protocol"]
        for variant in self.r["protocol"]["variants"]:
            original = previous[variant + "/observed"]
            require(
                am.ready.parameters(original, variant, physics)
                == self.r["reference_parameters"][variant],
                "Independent parameter ownership differs",
            )
        sources = {
            str(path.relative_to(ctx.ROOT / "src/cells")): c.sha(path)
            for path in (ctx.ROOT / "src/cells").rglob("*.py")
        }
        require(len(sources) == 51, "Checkpoint production source extent")
        for key, record in self.cells.records.items():
            variant, backend, _step = key.split("/")
            dt = record["definition"]["execution"]["dt"]
            expected = am.ready.expected_definition(
                previous[variant + "/observed"], variant, dt, self.r["preparation_registration"]
            )
            expected["execution"]["jit"] = backend == "jax_jit"
            require(
                expected == self.r["cells_definitions"][key] == record["definition"],
                "Independent Cells definition differs",
            )
            directory = ctx.CAPTURE / "cells" / key
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
                self.checkpoint_arrays += checkpoint(
                    directory / name, row, index, sources, c.read, c.sha
                )
                self.checkpoints += 1
        require(self.checkpoints == 24, "Checkpoint coverage differs")

    def native_case(self, relative, absolute):
        key = "/".join(relative.parts[1:-1])
        paths = self.data["workers"]["betse"]["records"][key]
        a, b = (
            io.read_compressed(ctx.CAPTURE / paths[mode]) for mode in ("observed", "unobserved")
        )
        require(
            absolute["amount_fmol"] == accumulated_atol(self.r, a),
            "Independent native accumulation budget differs",
        )
        for row in (a, b):
            ctx.native_partials(row, ctx.CAPTURE / "native" / key / row["mode"])
        case = Case(self.r, a, b)
        self.native_arrays += case.arrays
        self.native_charge += case.charge_snapshots
        self.native_points[key] = case.points
        return case

    def dynamic_resolve(self, name):
        parts = name.split("/")
        observation = parts.index("observation")
        prefix, index, field, tail = (
            parts[:observation],
            int(parts[observation + 1]),
            parts[observation + 2],
            parts[observation + 3 :],
        )
        engine = prefix[0]
        if engine == "cross_engine":
            variant = prefix[1]
            a = self.native_points[variant + f"/dt_{self.r['protocol']['native_steps_s'][-1]:.8g}"]
            b = self.cells.points[
                variant + f"/jax_jit/dt_{self.r['protocol']['cells_steps_s'][-1]:.8g}"
            ]
        else:
            require(engine in ("native", "cells"), "Unknown trajectory engine")
            own = prefix[-1] == "own_refinement"
            key = "/".join(prefix[1:-1] if own else prefix[1:])
            points = self.native_points if engine == "native" else self.cells.points
            a, b = points[key], self.reference.primary_points(prefix[1])
            if own:
                grid = self.r["protocol"][
                    "native_steps_s" if engine == "native" else "cells_steps_s"
                ]
                current = float(key.split("dt_")[-1])
                position = grid.index(current)
                require(position > 0, "Invalid own-refinement pair")
                previous = key.rsplit("dt_", 1)[0] + f"dt_{grid[position - 1]:.8g}"
                a, b = points[previous], points[key]
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
                require(failure_path is not None, "Unbound frozen numerical ledger")
                self.source_path = Path(failure_path).relative_to(ctx.CAPTURE)
                self.case, self.seen = None, set()
                name = self.source_path.as_posix()
                if name.startswith("native/"):
                    self.case = audit.native_case(self.source_path, absolute)
                    self.resolver = self.case.resolve
                    self.kind = "native"
                elif name == "reference-failures.jsonl":
                    self.resolver, self.kind = audit.reference.resolve, "reference"
                elif name == "reference-dense-failures.jsonl":
                    self.resolver, self.kind = (
                        lambda n: audit.reference.resolve(n, dense=True),
                        "reference_dense",
                    )
                elif name == "cells-state-failures.jsonl":
                    self.resolver, self.kind = audit.cells.resolve_state, "cells_state"
                elif name.startswith("cells/"):
                    key = "/".join(self.source_path.parts[1:-1])
                    self.resolver, self.kind = lambda n: audit.cells.resolve_pair(n, key), "restart"
                elif name.startswith("backend-"):
                    self.resolver, self.kind = audit.cells.resolve_pair, "backend"
                else:
                    require(name == "trajectory-failures.jsonl", "Unknown frozen numerical ledger")
                    self.resolver, self.kind = audit.dynamic_resolve, "trajectory"
                target = audit.output / "replayed" / self.source_path
                target.parent.mkdir(parents=True, exist_ok=True)
                super().__init__(absolute, relative, target)
                self.independent = am.Crosscheck(audit.output / "independent-mismatches.jsonl")
                audit.ledgers.append(self)

            def compare(self, name, actual, expected, unit):
                if not isinstance(expected, list):
                    if self.case is None:
                        require(name not in self.seen, "Duplicate frozen numerical identity")
                        self.seen.add(name)
                    independent_a, independent_b, independent_unit = self.resolver(name)
                    require(unit == independent_unit, "Independent comparison unit differs")
                    self.independent.add(
                        name,
                        actual,
                        expected,
                        independent_a,
                        independent_b,
                        unit,
                        self.absolute[unit],
                        self.relative,
                    )
                return super().compare(name, actual, expected, unit)

            def summary(self):
                if self.case is not None:
                    self.case.finish()
                return super().summary()

        return TwinLedger

    def recorded_write(self, path, value):
        relative = Path(path).relative_to(ctx.CAPTURE).as_posix()
        require(relative not in self.writes, "Duplicate frozen output")
        saved = io.read_compressed(path) if relative.endswith(".gz") else c.read(path)
        require(value == saved, "Frozen output does not replay: " + relative)
        self.writes.add(relative)

    def decisions(self):
        protocol = self.r["protocol"]
        gate = io.read_compressed(ctx.CAPTURE / "reference-gate.json.gz")
        dynamic = c.read(ctx.CAPTURE / "trajectory-comparison.json")
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

    def run(self):
        original = io.Ledger
        with (
            capture_write_guard(ctx.CAPTURE),
            patch.object(io, "Ledger", self.ledger_type(original)),
            patch.object(io, "write", self.recorded_write),
            patch.object(io, "write_compressed", self.recorded_write),
        ):
            print("Checking reference replay and independent columns", flush=True)
            reference = frozen_reference.check(
                self.r, ctx.CAPTURE, self.data["workers"]["reference"]
            )
            require(reference["status"] == "pass", "Original reference no longer passes")
            print("Checking native/Cells replay and independent columns", flush=True)
            comparison = frozen_compare.check(
                self.r,
                ctx.CAPTURE,
                reference,
                self.data["workers"]["betse"],
                self.data["workers"]["cells"],
            )
            require(
                comparison == c.read(ctx.CAPTURE / "capture-comparison.json"),
                "Frozen capture summary differs",
            )
        require(
            self.writes
            == {
                "reference-gate.json.gz",
                "native-accounting.json.gz",
                "cells-accounting.json.gz",
                "trajectory-comparison.json",
            },
            "Frozen output coverage differs",
        )
        replayed = self.output / "replayed/trajectory-failures.jsonl"
        original_failures = [
            io.parse(line)
            for line in (ctx.CAPTURE / "trajectory-failures.jsonl").read_text().splitlines()
        ]
        replayed_failures = [io.parse(line) for line in replayed.read_text().splitlines()]
        require(
            replayed_failures == original_failures and len(original_failures) == 14,
            "Coarse diagnostic failures were changed/omitted",
        )
        groups = []
        for ledger in self.ledgers:
            independent = ledger.independent.summary()
            require(
                ledger.count == independent["identities"]
                and ledger.failed == independent["independent_numerical_rejections"],
                "Independent coverage/classification differs",
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
            native_count == 5181760 and self.native_charge == 2264,
            "Full native audit coverage differs",
        )
        refinements = self.decisions()
        return {
            "groups": groups,
            "refinements": refinements,
            "frozen_comparisons_replayed": sum(v["frozen"]["comparisons"] for v in groups),
            "independent_identities": sum(v["independent"]["identities"] for v in groups),
            "independent_column_mismatches": sum(
                v["independent"]["column_mismatches"] for v in groups
            ),
            "native_identities": native_count,
            "native_charge_snapshots": self.native_charge,
            "native_array_records": self.native_arrays,
            "numeric_checkpoints": self.checkpoints,
            "checkpoint_arrays": self.checkpoint_arrays,
            "observer_pairs": 12,
            "restart_pairs": 4,
            "backend_pairs": 4,
            "preserved_coarse_diagnostic_failures": len(original_failures),
            "refinement_groups": len(refinements),
            "reference_solves_replayed_not_rerun": 12,
        }
