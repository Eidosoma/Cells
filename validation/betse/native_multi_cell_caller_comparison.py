"""Prepare and run one independent original-source multi-cell comparison.

Preparation reads saved evidence and source bytes only. A separately bound
release permits one reference attempt from an immutable checkout snapshot.
The complete native record is saved before its strict comparison view. Failed
inputs, source calls, observers or runtime bindings never become a match.
"""

import argparse
import json
import os
import resource
import runpy
import sys
import traceback
from pathlib import Path

from validation import source_snapshot
from validation.betse import native_multi_cell_caller_comparison_inputs as inputs
from validation.betse import native_multi_cell_caller_comparison_runtime as runtime
from validation.betse import native_multi_cell_caller_native as native
from validation.betse import native_multi_cell_caller_native_source as original
from validation.betse import native_multi_cell_caller_qualification as parent_runner
from validation.betse import native_single_cell_prefix_payload as payload
from validation.betse import native_single_cell_prefix_qualification as shared

ROOT = Path(__file__).resolve().parents[2]
OWN = "validation/betse/native_multi_cell_caller_comparison.py"
TEST = "tests/unit/test_native_multi_cell_caller_comparison.py"
KINDS = (
    "cells.multi_cell_caller_comparison_plan@1",
    "cells.multi_cell_caller_comparison_release@1",
)
PURPOSE = "independent_original_source_multi_cell_caller_comparison"
ENDPOINT = "cell_index"
PROHIBITED = frozenset(("cells", "betse", "jax", "jaxlib"))
NO_CREDIT = dict(
    scientific_qualification=False,
    independent_physical_oracle=False,
    physical_geometry_admitted=False,
    full_package_or_phase_admitted=False,
    ordinary_checkpoint_admitted=False,
    invalidated_postcut_owners_cleared=0,
)


def _error(error):
    try:
        return shared.exception_record(error)
    except Exception as secondary:
        record = native._fallback_error(error)
        record["recording_error"] = native._fallback_error(secondary)
        return record


def _terminal(path, record):
    """A failed terminal write cannot hide an already retained primary error."""
    try:
        shared.write(path, record)
        return True
    except Exception as error:
        record["terminal_capture_error"] = _error(error)
        record["terminal_requested_status"] = record.get("status")
        record["status"] = "failed"
        if "accepted_source_comparisons" in record:
            record["accepted_source_comparisons"] = 0
        # The resource guard durably owns this stderr stream. This is a
        # fallback record, never a replacement success artifact.
        sys.stderr.write(
            "CELLS_TERMINAL_CAPTURE_FAILURE "
            + json.dumps(dict(path=str(path), outcome=record), sort_keys=True, allow_nan=False)
            + "\n"
        )
        sys.stderr.flush()
        return False


def _same(left, right):
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(
        right, sort_keys=True, allow_nan=False
    )


def unique_pins(rows):
    values = {}
    for row in rows:
        if type(row) is not dict or set(row) != {"path", "sha256"}:
            raise ValueError("Require exact retained-file pins")
        if row["path"] in values and values[row["path"]] != row:
            raise ValueError("Conflicting retained-file pin")
        values[row["path"]] = row
    return [values[key] for key in sorted(values)]


def import_guard(attempted):
    def guard(event, args):
        if event == "import" and args[0].split(".")[0] in PROHIBITED:
            attempted.append(args[0])
            raise ImportError("Independent reference refuses model/package imports: " + args[0])

    return guard


def verify_imports(modules=None):
    modules = sys.modules if modules is None else modules
    if found := sorted(name for name in modules if name.split(".")[0] in PROHIBITED):
        raise ValueError("Independent worker contains prohibited modules: " + ", ".join(found))


def protected_output(output, prepared, plan):
    output = shared.execution_output(output, prepared, plan)
    protected = [
        ROOT,
        Path(plan["parent_diagnostic"]),
        Path(plan["parent_prepared"]),
        *(Path(row["path"]) for row in plan["external_inputs"]),
        *(Path(row["path"]) for row in plan["runtime_inventory"]["files"]),
    ]
    if any(output.is_relative_to(path) or path.is_relative_to(output) for path in protected):
        raise ValueError("Output overlaps retained source, evidence or runtime")
    return output


def _saved_bindings(diagnostic, parent, saved):
    rows = [
        shared.pin(diagnostic / name)
        for name in ("result.json", "diagnostic.json", "root-review.json")
    ]
    rows += [shared.pin(parent / "plan.json"), shared.pin(parent / "source/SNAPSHOT.json")]
    rows += [
        pin
        for row in saved["captures"]
        for pin in inputs.capture_files(diagnostic / row["path"], row)
    ]
    _, _, image_path = native.inputs(saved["raw"], saved["configuration"])
    rows.append(shared.pin(image_path))
    rows += [
        dict(path=str(shared.NATIVE / name), sha256=h) for name, h in original.pins_for().items()
    ]
    rows += saved["parent_plan"]["external_inputs"]
    return unique_pins(rows)


def prepare(destination, diagnostic, parent, *, cpu=3):
    """Bind a complete saved legacy caller and fresh reference code; no replay."""
    destination = shared.output_path(destination)
    diagnostic, parent = shared.output_path(diagnostic), shared.output_path(parent)
    if type(cpu) is not int or os.sched_getaffinity(0) != {cpu}:
        raise ValueError("Declare the actual single preparation CPU")
    if any(
        destination.is_relative_to(p) or p.is_relative_to(destination)
        for p in (ROOT, diagnostic, parent, shared.NATIVE)
    ):
        raise ValueError("Preparation overlaps retained source or evidence")
    saved = inputs.saved_caller(diagnostic, parent)
    external = _saved_bindings(diagnostic, parent, saved)
    inventory = runtime.prepare_inventory(saved["parent_plan"]["runtime_paths"])
    protection = dict(
        runtime_paths=saved["parent_plan"]["runtime_paths"],
        parent_diagnostic=str(diagnostic),
        parent_prepared=str(parent),
        external_inputs=external,
        runtime_inventory=inventory,
    )
    protected_output(destination, diagnostic, protection)
    _, sites = original.source_nodes(shared.NATIVE)
    shared.verify_pins(external)
    destination.mkdir(parents=True, exist_ok=False)
    try:
        closure = runpy.run_path(str(ROOT / shared.CLOSURE))["closure"]
        files = closure(
            ROOT,
            [
                OWN,
                TEST,
                "tests/unit/test_native_multi_cell_caller_comparison_inputs.py",
                "tests/unit/test_native_multi_cell_caller_comparison_runtime.py",
                "tests/unit/test_native_multi_cell_caller_native.py",
                "tests/unit/test_native_multi_cell_caller_compare.py",
            ],
        )
        files[shared.CLOSURE] = source_snapshot.digest(ROOT / shared.CLOSURE)
        for directory in {Path(name).parent for name in files}:
            for path in (ROOT / directory).glob("*.json"):
                files[str(path.relative_to(ROOT))] = source_snapshot.digest(path)
        frozen = source_snapshot.freeze(ROOT, destination / "source", {p: p for p in files})
        captures = [
            dict(label=row["label"], **shared.pin(diagnostic / row["path"]))
            for row in saved["captures"]
        ]
        plan = dict(
            kind=KINDS[0],
            purpose=PURPOSE,
            case=saved["case"],
            stop_after=ENDPOINT,
            parent_diagnostic=str(diagnostic),
            parent_prepared=str(parent),
            input_capture={k: captures[0][k] for k in ("path", "sha256")},
            owned_trial={k: captures[-1][k] for k in ("path", "sha256")},
            saved_captures=captures,
            configuration=saved["configuration"],
            snapshot_sha256=source_snapshot.digest(destination / "source/SNAPSHOT.json"),
            git_revision=frozen["git_revision"],
            external_inputs=external,
            native_source_root=str(shared.NATIVE),
            original_source_sites=sites,
            runtime_paths=saved["parent_plan"]["runtime_paths"],
            runtime_inventory=inventory,
            interpreter=str(Path(sys.executable).absolute()),
            cpu=cpu,
            limits=shared.LIMITS,
            comparison="exact_final_three_caches_two_MT_streams_five_alias_observations",
            native_executions=1,
            cells_replays=0,
            automatic_retry=False,
            native_package_imports=[],
            normalized_parameters_phase_callbacks_only=True,
            capture_transport=payload.KIND,
            capture_read_policy=inputs.CAPTURE_READ_POLICY,
            **NO_CREDIT,
        )
        source_snapshot.assert_checkout_unchanged(destination / "source")
        shared.verify_pins(external)
        runtime.verify_inventory(inventory)
        shared.write(destination / "plan.json", plan)
        (destination / "plan.json").chmod(0o444)
        return plan
    except BaseException as error:
        _terminal(
            destination / "preparation-failure.json",
            dict(
                status="failed", error=_error(error), traceback=traceback.format_exc(), **NO_CREDIT
            ),
        )
        raise


def verify_plan(prepared, plan_sha256):
    prepared = shared.output_path(prepared)
    if source_snapshot.digest(prepared / "plan.json") != plan_sha256:
        raise ValueError("Changed multi-cell comparison plan")
    plan = shared.read(prepared / "plan.json")
    fixed = dict(
        kind=KINDS[0],
        purpose=PURPOSE,
        stop_after=ENDPOINT,
        limits=shared.LIMITS,
        native_executions=1,
        cells_replays=0,
        automatic_retry=False,
        native_package_imports=[],
        normalized_parameters_phase_callbacks_only=True,
        capture_transport=payload.KIND,
        capture_read_policy=inputs.CAPTURE_READ_POLICY,
        comparison="exact_final_three_caches_two_MT_streams_five_alias_observations",
        **NO_CREDIT,
    )
    if (
        (prepared / "preparation-failure.json").exists()
        or not _same({k: plan.get(k) for k in fixed}, fixed)
        or plan.get("case") not in parent_runner.CASES
        or type(plan.get("cpu")) is not int
        or plan.get("native_source_root") != str(shared.NATIVE)
    ):
        raise ValueError("Incomplete or widened comparison plan")
    source_snapshot.verify(prepared / "source", manifest_sha256=plan["snapshot_sha256"])
    shared.verify_pins(plan["external_inputs"])
    runtime.verify_inventory(plan["runtime_inventory"])
    diagnostic, parent = (
        shared.output_path(plan["parent_diagnostic"]),
        shared.output_path(plan["parent_prepared"]),
    )
    saved = inputs.saved_caller(diagnostic, parent)
    captures = [
        dict(label=row["label"], **shared.pin(diagnostic / row["path"]))
        for row in saved["captures"]
    ]
    if (
        plan["case"] != saved["case"]
        or not _same(plan["configuration"], saved["configuration"])
        or plan["runtime_paths"] != saved["parent_plan"]["runtime_paths"]
        or plan["saved_captures"] != captures
        or plan["input_capture"] != {k: captures[0][k] for k in ("path", "sha256")}
        or plan["owned_trial"] != {k: captures[-1][k] for k in ("path", "sha256")}
        or any(
            row not in plan["external_inputs"] for row in _saved_bindings(diagnostic, parent, saved)
        )
    ):
        raise ValueError("Changed saved caller input/lineage/runtime binding")
    _, sites = original.source_nodes(shared.NATIVE)
    if not _same(sites, plan["original_source_sites"]):
        raise ValueError("Changed original-source statement or method binding")
    return plan


def verify(prepared, plan_sha256, release):
    plan = verify_plan(prepared, plan_sha256)
    grant = shared.read(release)
    fixed = dict(
        kind=KINDS[1],
        plan_sha256=plan_sha256,
        snapshot_sha256=plan["snapshot_sha256"],
        case=plan["case"],
        stop_after=ENDPOINT,
        allow_one_native_reference=True,
        **NO_CREDIT,
    )
    review = grant.get("source_review")
    if (
        not _same({k: grant.get(k) for k in fixed}, fixed)
        or type(review) is not dict
        or set(review) != {"path", "sha256"}
    ):
        raise ValueError("Exact source-reviewed single-reference release required")
    shared.verify_pins([review])
    if os.sched_getaffinity(0) != {plan["cpu"]}:
        raise ValueError("Wrong declared reference CPU")
    return plan


def claim(prepared, plan_sha256, release, output):
    """One immutable reference attempt per preparation, including failed starts."""
    record = dict(plan_sha256=plan_sha256, release=shared.pin(release), output=str(output))
    path = Path(prepared) / "reference-claim.json"
    # O_EXCL is the claim; unlike a replace-based writer it cannot race another launch.
    with path.open("x") as handle:
        json.dump(record, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    path.chmod(0o444)
    return shared.pin(path)


def verify_claim(prepared, plan_sha256, release, output):
    path = Path(prepared) / "reference-claim.json"
    expected = dict(plan_sha256=plan_sha256, release=shared.pin(release), output=str(output))
    if shared.read(path) != expected:
        raise ValueError("Reference claim does not name this exact attempt")
    return shared.pin(path)


def _saved_artifacts(output, outcome):
    """Retain secondary serialization failures without hiding the primary result."""
    saved = []
    for name in (
        "source-summary.json",
        "native-full.json",
        "native-comparison.json",
        "comparison.json",
        "runtime-before-source.json",
        "runtime-after-source.json",
        "runtime-refusal.json",
    ):
        path = output / name
        if not path.is_file():
            continue
        try:
            saved.extend(payload.files(path))
        except Exception as error:
            row = dict(path=str(path), error=_error(error))
            try:
                row["raw_unvalidated_file"] = shared.pin(path)
            except Exception as secondary:
                row["raw_pin_error"] = _error(secondary)
            outcome.setdefault("artifact_capture_errors", []).append(row)
            outcome.update(status="failed", accepted_source_comparisons=0)
    return saved


def _retain_runtime_refusal(output, error, outcome):
    if not isinstance(error, runtime.RuntimeInventoryError):
        return
    try:
        shared.write(output / "runtime-refusal.json", error.partial)
    except Exception as secondary:
        outcome["runtime_partial_capture_error"] = _error(secondary)


def worker(prepared, plan_sha256, release, output):
    plan = verify(prepared, plan_sha256, release)
    source = Path(prepared) / "source"
    if ROOT != source or str(Path(sys.executable).absolute()) != plan["interpreter"]:
        raise ValueError("Worker must use the frozen source and declared interpreter")
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    output = protected_output(output, prepared, plan)
    authorization = verify_claim(prepared, plan_sha256, release, output)
    # A direct second worker invocation cannot reuse a prior launch claim.
    with (output / "worker-started.json").open("x") as handle:
        json.dump(dict(claim=authorization, pid=os.getpid()), handle)
        handle.write("\n")
    attempted, before = [], None
    sys.addaudithook(import_guard(attempted))
    outcome = dict(
        status="failed",
        accepted_source_comparisons=0,
        reference_calls_attempted=0,
        stop_after=ENDPOINT,
        **NO_CREDIT,
    )
    try:
        verify_imports()
        before = runtime.preflight(plan["runtime_inventory"], source)
        shared.write(output / "runtime-before-source.json", before)
        saved = inputs.saved_caller(Path(plan["parent_diagnostic"]), Path(plan["parent_prepared"]))
        outcome["reference_calls_attempted"] = 1
        reference = native.evaluate(
            saved["raw"],
            plan["configuration"],
            Path(plan["native_source_root"]),
            record_exception=shared.exception_record,
        )
        summary = {
            key: reference[key]
            for key in (
                "status",
                "source_body_completed",
                "source_error",
                "capture_error",
                "failed_stage",
                "actual_source_executions",
                "capture_errors",
            )
        }
        # Keep the primary source/capture graph in the eventual worker terminal
        # even if the first evidence file cannot be written. Still attempt the
        # complete forensic capture, but a summary failure prevents comparison.
        outcome["source_summary"] = summary
        try:
            shared.write(output / "source-summary.json", summary)
        except Exception as capture_error:
            outcome["source_summary_capture_error"] = _error(capture_error)
        serialized = shared.archive.snapshot(reference)
        payload.write(output / "native-full.json", serialized)
        if "source_summary_capture_error" in outcome:
            raise RuntimeError("Source summary capture failed; complete reference retained")
        if (
            summary["status"] != "source_completed"
            or summary["source_body_completed"] is not True
            or summary["source_error"] is not None
            or summary["capture_error"] is not None
            or summary["capture_errors"]
            or summary["failed_stage"] is not None
        ):
            raise RuntimeError("Original source or capture failed; complete reference retained")
        selected = native.comparison_record(serialized)
        payload.write(output / "native-comparison.json", selected)
        from validation.betse.native_multi_cell_caller_compare import compare

        comparison = compare(payload.read(plan["owned_trial"]["path"]), selected)
        shared.write(output / "comparison.json", comparison)
        verify(prepared, plan_sha256, release)
        verify_imports()
        if attempted:
            raise RuntimeError("Reference attempted prohibited package imports")
        outcome.update(
            status="exact_source_match" if comparison["exact_match"] else "source_mismatch",
            accepted_source_comparisons=int(comparison["exact_match"]),
        )
    except Exception as error:
        outcome["error"] = _error(error)
        _retain_runtime_refusal(output, error, outcome)
    finally:
        outcome["attempted_prohibited_imports"] = attempted
        try:
            verify_imports()
            shared.write(output / "runtime-producers.json", shared.runtime_inventory(source))
            if before is not None:
                shared.write(
                    output / "runtime-after-source.json",
                    runtime.finish(plan["runtime_inventory"], source, before),
                )
            else:
                outcome["dependency_preflight_incomplete"] = True
            outcome["runtime_producers"] = shared.pin(output / "runtime-producers.json")
        except Exception as error:
            outcome["runtime_capture_error"] = _error(error)
            _retain_runtime_refusal(output, error, outcome)
            outcome.update(status="failed", accepted_source_comparisons=0)
        outcome["saved_files"] = _saved_artifacts(output, outcome)
        _terminal(output / "worker-result.json", outcome)
    return 0 if outcome["status"] == "exact_source_match" else 1


def launch(prepared, plan_sha256, release, output):
    plan = verify(prepared, plan_sha256, release)
    output = protected_output(output, prepared, plan)
    output.mkdir(parents=True, exist_ok=False)
    error = process = None
    try:
        authorization = claim(prepared, plan_sha256, release, output)
        (output / "process").mkdir()
        shared.write(
            output / "inputs.json",
            dict(
                plan_sha256=plan_sha256,
                release=shared.pin(release),
                claim=authorization,
                case=plan["case"],
                stop_after=ENDPOINT,
                **NO_CREDIT,
            ),
        )
        if shared.guard.memory_available() < 12 * 2**30:
            raise RuntimeError("Reference launch requires 12 GiB available host memory")
        process = shared.guard.run_bounded(
            [
                plan["interpreter"],
                "-B",
                "-m",
                "validation.betse.native_multi_cell_caller_comparison",
                "worker",
                "--prepared",
                str(prepared),
                "--plan-sha256",
                plan_sha256,
                "--release",
                str(release),
                "--output",
                str(output),
            ],
            directory=output / "process",
            cwd=Path(prepared) / "source",
            env=shared.environment(Path(prepared) / "source", plan),
            **plan["limits"],
        )
        child = shared.read(output / "worker-result.json")
        if (
            process["returncode"]
            or child["status"] != "exact_source_match"
            or type(child.get("accepted_source_comparisons")) is not int
            or child["accepted_source_comparisons"] != 1
            or type(child.get("reference_calls_attempted")) is not int
            or child.get("reference_calls_attempted") != 1
            or child.get("attempted_prohibited_imports") != []
            or not _same({k: child.get(k) for k in NO_CREDIT}, NO_CREDIT)
        ):
            raise RuntimeError("Reference/comparison did not produce an exact match")
    except Exception as caught:
        error = _error(caught)
    record = dict(
        status="failed" if error else "exact_source_match_pending_review",
        process=process,
        error=error,
        case=plan["case"],
        stop_after=ENDPOINT,
        worker_result=None,
        process_receipts=[],
        automatic_retry=False,
        accepted_scientific_cases=0,
        **NO_CREDIT,
    )
    for path, key in (
        (output / "worker-result.json", "worker_result"),
        *(
            (output / "process" / name, "process_receipts")
            for name in ("result.json", "failure.json", "resource-stop.json")
        ),
    ):
        try:
            if path.is_file():
                row = shared.pin(path)
                if key == "worker_result":
                    record[key] = row
                else:
                    record[key].append(row)
        except Exception as capture_error:
            record.setdefault("terminal_input_capture_errors", []).append(
                dict(path=str(path), error=_error(capture_error))
            )
            record["status"] = "failed"
    _terminal(output / ("failure.json" if record["status"] == "failed" else "result.json"), record)
    return int(record["status"] == "failed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    item = sub.add_parser("prepare")
    item.add_argument("--output", type=Path, required=True)
    item.add_argument("--diagnostic", type=Path, required=True)
    item.add_argument("--parent", type=Path, required=True)
    item.add_argument("--cpu", type=int, default=3)
    for name in ("run", "worker"):
        item = sub.add_parser(name)
        item.add_argument("--prepared", type=Path, required=True)
        item.add_argument("--plan-sha256", required=True)
        item.add_argument("--release", type=Path, required=True)
        item.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
        prepare(args.output, args.diagnostic, args.parent, cpu=args.cpu)
        return 0
    return (worker if args.command == "worker" else launch)(
        args.prepared, args.plan_sha256, args.release, args.output
    )


if __name__ == "__main__":
    raise SystemExit(main())
