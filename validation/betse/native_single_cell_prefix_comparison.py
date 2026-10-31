"""Freeze and run one independent original-source comparison of a saved prefix.

Preparation is metadata only. A separate exact-plan release permits one native
reference child, followed by the stdlib comparator. No Cells trajectory is
replayed, no retry is automatic, and matched source caches do not establish
physical accuracy or full application equivalence.
"""

import argparse
import os
import resource
import runpy
import sys
import traceback
from pathlib import Path

from validation import source_snapshot
from validation.betse import native_single_cell_prefix_native as native
from validation.betse import native_single_cell_prefix_qualification as prior

ROOT = Path(__file__).resolve().parents[2]
OWN = "validation/betse/native_single_cell_prefix_comparison.py"
NATIVE = "validation/betse/native_single_cell_prefix_native.py"
COMPARE = "validation/betse/native_single_cell_prefix_compare.py"
TEST = "tests/unit/test_native_single_cell_prefix_native.py"
KINDS = (
    "cells.single_cell_prefix_comparison_plan@1",
    "cells.single_cell_prefix_comparison_release@1",
)
METHODS = ("before", *native.METHODS)


def prepare(destination, diagnostic, parent, *, cpu=3):
    """Bind saved input/evidence and fresh code; never execute a fixture/model."""
    destination = prior.output_path(destination)
    diagnostic, parent = Path(diagnostic).absolute(), Path(parent).absolute()
    if any(
        destination.is_relative_to(p) or p.is_relative_to(destination)
        for p in (ROOT, diagnostic, parent, prior.NATIVE)
    ):
        raise ValueError("Preparation overlaps source or retained evidence")
    if type(cpu) is not int or os.sched_getaffinity(0) != {cpu}:
        raise ValueError("Declare the actual single preparation CPU")
    result = prior.read(diagnostic / "result.json")
    recorded = prior.read(diagnostic / "diagnostic.json")
    if (
        result.get("status") != "completed_unqualified"
        or result.get("failure") is not None
        or result.get("diagnostic") != prior.pin(diagnostic / "diagnostic.json")
        or recorded.get("status") != "source_completed_unqualified"
        or recorded.get("completed_stages") != list(prior.STAGES)
        or recorded.get("observer_error") is not None
        or recorded.get("source_error") is not None
    ):
        raise ValueError("Require a completed saved source prefix with all five captures")
    parent_plan = prior.verify_plan(parent, recorded["plan_sha256"])
    case = recorded["case"]
    if case not in prior.CASES or case != result["case"]:
        raise ValueError("Unregistered saved input case")
    captures = recorded["captures"]
    if [r.get("label") for r in captures] != list(prior.STAGES) or any(
        r.get("status") != "saved" for r in captures
    ):
        raise ValueError("Incomplete or reordered saved captures")
    for row in captures:
        relative = source_snapshot.relative_path(row["path"])
        if source_snapshot.digest(diagnostic / relative) != row["sha256"]:
            raise ValueError("Changed saved stage capture")
    declared = prior.read(diagnostic / captures[0]["path"])["native_comparison_inputs"]
    _, image_path = native.inputs(declared, parent_plan["configuration"])
    _, sites = native.source_nodes(prior.NATIVE)
    external = [
        prior.pin(diagnostic / name)
        for name in ("result.json", "diagnostic.json", "root-review.json")
    ]
    external += [prior.pin(diagnostic / row["path"]) for row in captures]
    external += [prior.pin(image_path), prior.pin(parent / "plan.json")]
    external += [prior.pin(prior.NATIVE / name) for name in native.NATIVE_PINS]
    # Runtime overlays are the same authenticated bytes used by the saved run.
    external += [
        p
        for p in parent_plan["external_inputs"]
        if any(Path(p["path"]).is_relative_to(q) for q in parent_plan["runtime_paths"])
    ]
    external = list({r["path"]: r for r in external}.values())
    prior.verify_pins(external)
    destination.mkdir(parents=True, exist_ok=False)
    try:
        closure = runpy.run_path(str(ROOT / prior.CLOSURE))["closure"]
        files = closure(
            ROOT,
            [OWN, NATIVE, COMPARE, TEST, "tests/unit/test_native_single_cell_prefix_compare.py"],
        )
        files[prior.CLOSURE] = source_snapshot.digest(ROOT / prior.CLOSURE)
        for directory in {Path(name).parent for name in files}:
            for path in (ROOT / directory).glob("*.json"):
                files[str(path.relative_to(ROOT))] = source_snapshot.digest(path)
        snapshot = source_snapshot.freeze(
            ROOT, destination / "source", {name: name for name in files}
        )
        plan = dict(
            kind=KINDS[0],
            purpose="independent_original_source_prefix_comparison",
            case=case,
            parent_diagnostic=str(diagnostic),
            parent_prepared=str(parent),
            input_capture=prior.pin(diagnostic / captures[0]["path"]),
            owned_trial=prior.pin(diagnostic / captures[-1]["path"]),
            configuration=parent_plan["configuration"],
            snapshot_sha256=source_snapshot.digest(destination / "source/SNAPSHOT.json"),
            git_revision=snapshot["git_revision"],
            external_inputs=external,
            native_source_root=str(prior.NATIVE),
            original_source_sites=sites,
            runtime_paths=parent_plan["runtime_paths"],
            interpreter=str(Path(sys.executable).absolute()),
            cpu=cpu,
            limits=prior.LIMITS,
            stages=list(METHODS),
            comparison="exact_typed_values_source_layout_and_MT_state",
            native_executions=1,
            cells_replays=0,
            automatic_retry=False,
            independent_physical_oracle=False,
            physical_geometry_admitted=False,
            full_package_or_phase_admitted=False,
            ordinary_checkpoint_admitted=False,
        )
        source_snapshot.assert_checkout_unchanged(destination / "source")
        prior.verify_pins(external)
        prior.write(destination / "plan.json", plan)
        (destination / "plan.json").chmod(0o444)
        return plan
    except BaseException:
        prior.write(
            destination / "preparation-failure.json",
            dict(traceback=traceback.format_exc(), scientific_acceptance=False),
        )
        raise


def verify(prepared, plan_sha256, release):
    prepared = prior.output_path(prepared)
    if source_snapshot.digest(prepared / "plan.json") != plan_sha256:
        raise ValueError("Changed comparison plan")
    plan = prior.read(prepared / "plan.json")
    if (
        (prepared / "preparation-failure.json").exists()
        or plan.get("kind") != KINDS[0]
        or plan.get("limits") != prior.LIMITS
        or plan.get("stages") != list(METHODS)
        or plan.get("native_executions") != 1
        or type(plan.get("native_executions")) is not int
        or plan.get("cells_replays") != 0
        or type(plan.get("cells_replays")) is not int
        or type(plan.get("cpu")) is not int
        or plan.get("automatic_retry") is not False
        or plan.get("independent_physical_oracle") is not False
        or plan.get("physical_geometry_admitted") is not False
        or plan.get("full_package_or_phase_admitted") is not False
        or plan.get("ordinary_checkpoint_admitted") is not False
        or plan.get("case") not in prior.CASES
    ):
        raise ValueError("Incomplete or widened comparison plan")
    source_snapshot.verify(prepared / "source", manifest_sha256=plan["snapshot_sha256"])
    prior.verify_pins(plan["external_inputs"])
    grant = prior.read(release)
    if (
        grant.get("kind") != KINDS[1]
        or grant.get("plan_sha256") != plan_sha256
        or grant.get("snapshot_sha256") != plan["snapshot_sha256"]
        or grant.get("case") != plan["case"]
        or grant.get("allow_one_native_reference") is not True
        or grant.get("physical_geometry_admitted") is not False
        or type(grant.get("source_review")) is not dict
        or set(grant["source_review"]) != {"path", "sha256"}
    ):
        raise ValueError("Exact source-reviewed single-reference release required")
    prior.verify_pins([grant["source_review"]])
    if os.sched_getaffinity(0) != {plan["cpu"]}:
        raise ValueError("Wrong declared reference CPU")
    return plan


def worker(prepared, plan_sha256, release, output):
    plan = verify(prepared, plan_sha256, release)
    if (
        ROOT != Path(prepared) / "source"
        or str(Path(sys.executable).absolute()) != plan["interpreter"]
    ):
        raise ValueError("Reference worker must use frozen source and interpreter")
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    output = Path(output)
    attempted = []

    def block_models(event, args):
        if event == "import" and args[0].split(".")[0] in {"cells", "betse", "jax", "jaxlib"}:
            attempted.append(args[0])
            raise ImportError("Independent reference refuses model/package imports: " + args[0])

    sys.addaudithook(block_models)
    outcome = dict(
        status="failed",
        accepted_source_comparisons=0,
        physical_geometry_admitted=False,
        ordinary_checkpoint_admitted=False,
        native_executions=0,
    )
    try:
        declared = prior.read(plan["input_capture"]["path"])["native_comparison_inputs"]
        outcome["native_executions"] = 1
        reference = native.evaluate(
            declared,
            plan["configuration"],
            Path(plan["native_source_root"]),
            record_exception=prior.exception_record,
        )
        # Existing independent archive transport only; no production decoder.
        serialized = prior.archive.snapshot(reference)
        prior.write(output / "native.json", serialized)
        from validation.betse.native_single_cell_prefix_compare import compare

        comparison = compare(prior.read(plan["owned_trial"]["path"]), serialized)
        prior.write(output / "comparison.json", comparison)
        verify(prepared, plan_sha256, release)
        if attempted or any(name == "cells" or name.startswith("cells.") for name in sys.modules):
            raise RuntimeError("Reference imported the tested model")
        outcome.update(
            status="exact_source_match" if comparison["exact_match"] else "source_mismatch",
            accepted_source_comparisons=int(comparison["exact_match"]),
            native=prior.pin(output / "native.json"),
            comparison=prior.pin(output / "comparison.json"),
        )
    except Exception as error:
        outcome["error"] = prior.exception_record(error)
    finally:
        outcome["attempted_model_imports"] = attempted
        try:
            prior.write(output / "runtime-producers.json", prior.runtime_inventory(ROOT))
            outcome["runtime_producers"] = prior.pin(output / "runtime-producers.json")
        except Exception as capture_error:
            outcome["runtime_capture_error"] = prior.exception_record(capture_error)
            outcome["status"] = "failed"
            outcome["accepted_source_comparisons"] = 0
        prior.write(output / "worker-result.json", outcome)
    return 0 if outcome["status"] == "exact_source_match" else 1


def launch(prepared, plan_sha256, release, output):
    plan = verify(prepared, plan_sha256, release)
    output = prior.execution_output(output, prepared, plan)
    protected = [Path(plan[k]["path"]) for k in ("input_capture", "owned_trial")]
    if any(p.is_relative_to(output) for p in protected):
        raise ValueError("Output overlaps retained input evidence")
    output.mkdir(parents=True, exist_ok=False)
    process, error = None, None
    try:
        (output / "process").mkdir()
        prior.write(
            output / "inputs.json",
            dict(plan_sha256=plan_sha256, release=prior.pin(release), case=plan["case"]),
        )
        if prior.guard.memory_available() < 12 * 2**30:
            raise RuntimeError("Reference launch requires 12 GiB available")
        process = prior.guard.run_bounded(
            [
                plan["interpreter"],
                "-B",
                "-m",
                "validation.betse.native_single_cell_prefix_comparison",
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
            env=prior.environment(Path(prepared) / "source", plan),
            **plan["limits"],
        )
        child = prior.read(output / "worker-result.json")
        if process["returncode"] or child["status"] != "exact_source_match":
            raise RuntimeError("Reference/comparison did not produce an exact match")
    except Exception as caught:
        error = prior.exception_record(caught)
    result = dict(
        status="failed" if error else "exact_source_match_pending_review",
        process=process,
        error=error,
        worker_result=prior.pin(output / "worker-result.json")
        if (output / "worker-result.json").is_file()
        else None,
        accepted_scientific_cases=0,
        physical_geometry_admitted=False,
        ordinary_checkpoint_admitted=False,
        automatic_retry=False,
    )
    prior.write(output / ("failure.json" if error else "result.json"), result)
    return int(error is not None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--diagnostic", type=Path, required=True)
    p.add_argument("--parent", type=Path, required=True)
    p.add_argument("--cpu", type=int, default=3)
    for command in ("run", "worker"):
        p = sub.add_parser(command)
        p.add_argument("--prepared", type=Path, required=True)
        p.add_argument("--plan-sha256", required=True)
        p.add_argument("--release", type=Path, required=True)
        p.add_argument("--output", type=Path, required=True)
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
