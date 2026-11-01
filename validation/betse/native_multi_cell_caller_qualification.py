"""Guarded real non-SVG multi-cell caller diagnostics, stopping at cell_index.

The upstream fixture and every validation replay execute inside the same
resource guard. Retained initial/clip/lifecycle states authenticate a fresh
live caller; they never populate it. Preparation is metadata-only. A completed
diagnostic still needs an independent original-source comparison and does not
admit physical geometry, a checkpoint or downstream geometry/ECM methods.
"""

import argparse
import ast
import json
import os
import resource
import runpy
import sys
import traceback
from pathlib import Path

from validation import source_snapshot
from validation.betse import native_single_cell_prefix_qualification as shared

ROOT = Path(__file__).resolve().parents[2]
OWN = "validation/betse/native_multi_cell_caller_qualification.py"
TEST = "tests/unit/test_native_multi_cell_caller_qualification.py"
CASES = ("caller-square-core", "caller-hex-core")
ENDPOINT = "cell_index"
STAGES = (
    "owned_image_request",
    "initial_pre_mesh",
    "clip_request",
    "clip_to_curve",
    "lifecycle_request",
    "post_clip_lifecycle",
    "multi_cell_request",
    "cell_index",
)
KINDS = ("cells.multi_cell_caller_diagnostic_plan@1", "cells.multi_cell_caller_release@1")
SOURCE_TABLES = (
    ("src/cells/processes/betse_native_single_cell_caller_lattice_source.py", ""),
    ("src/cells/processes/betse_native_single_cell_image_mask_source.py", ""),
    ("src/cells/processes/betse_native_multi_cell_caller_source.py", "betse/science"),
)
CONTROLS = dict(
    kind="cells.betse_make_voronoi_controls@1",
    single_cell=False,
    svg_override=False,
    alpha_shape=0.05,
    use_centroids=True,
    refine_mesh=False,
    maximum_voronoi_steps=2,
    voronoi_convergence=1e-30,
)


def configuration():
    # Height/spacing are native defaults. The other values explicitly select
    # the retained lifecycle fixture, not the complete YAML/Parameters setup.
    return {
        "world options": {
            "cell height": 1e-5,
            "cell spacing": 2.6e-8,
            "simulate single cell": False,
            "import from svg": None,
            "alpha shape": 0.05,
            "use centers": True,
            "mesh refinement": {
                "refine mesh": False,
                "maximum steps": 2,
                "convergence threshold": 1e-30,
            },
        }
    }


def _same(left, right):
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(
        right, sort_keys=True, allow_nan=False
    )


def _declaration(case, raw):
    if (
        case not in CASES
        or type(raw) is not dict
        or raw.get("lifecycle_case") != case
        or "native_option_recipe" not in raw
        or raw["native_option_recipe"] is not None
        or not _same(raw.get("controls"), CONTROLS)
    ):
        raise ValueError("Require the declared non-SVG, non-refining multi-cell input")


def _native_inputs(repository):
    expected = {str(shared.DEFAULTS): shared.DEFAULTS_SHA256}
    for name, prefix in SOURCE_TABLES:
        tree = ast.parse((repository / name).read_text())
        rows = next(
            ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "NATIVE_PINS" for t in node.targets)
        )
        for relative, digest in rows.items():
            path = str(shared.NATIVE / prefix / source_snapshot.relative_path(relative))
            if path in expected and expected[path] != digest:
                raise ValueError("Conflicting original source pins")
            expected[path] = digest
    return expected


def prepare(destination, *, repository=ROOT, cpu=3, runtime_paths=()):
    destination = shared.execution_output(destination, repository, {"runtime_paths": runtime_paths})
    if type(cpu) is not int or cpu not in os.sched_getaffinity(0):
        raise ValueError("Select an available CPU")
    destination.mkdir(parents=True, exist_ok=False)
    try:
        closure = runpy.run_path(str(repository / shared.CLOSURE))["closure"]
        files = closure(repository, [OWN, TEST])
        files[shared.CLOSURE] = source_snapshot.digest(repository / shared.CLOSURE)
        for parent in {Path(name).parent for name in files}:
            for path in (repository / parent).glob("*.json"):
                files[str(path.relative_to(repository))] = source_snapshot.digest(path)
        external = _native_inputs(repository)
        overlays = []
        for raw in runtime_paths:
            path = Path(raw).absolute()
            if not path.is_dir() or path.is_relative_to(repository) or path.is_symlink():
                raise ValueError("Require an explicit external runtime overlay")
            overlays.append(str(path))
            for file in path.rglob("*"):
                if file.is_file() and "__pycache__" not in file.parts:
                    row = shared.pin(file)
                    if row["path"] in external and external[row["path"]] != row["sha256"]:
                        raise ValueError("Runtime overlay conflicts with original source")
                    external[row["path"]] = row["sha256"]
        pins = [dict(path=name, sha256=value) for name, value in sorted(external.items())]
        shared.verify_pins(pins)
        frozen = destination / "source"
        snapshot = source_snapshot.freeze(repository, frozen, {name: name for name in files})
        plan = dict(
            kind=KINDS[0],
            purpose="multi_cell_caller_source_diagnostic_only",
            cases=list(CASES),
            configuration=configuration(),
            fixture_controls=CONTROLS,
            scalar_provenance=dict(
                path=str(shared.DEFAULTS), sha256=shared.DEFAULTS_SHA256, lines=[160, 164]
            ),
            snapshot_sha256=source_snapshot.digest(frozen / "SNAPSHOT.json"),
            git_revision=snapshot["git_revision"],
            runner_sha256=source_snapshot.digest(frozen / OWN),
            external_inputs=pins,
            runtime_paths=overlays,
            interpreter=str(Path(sys.executable).absolute()),
            cpu=cpu,
            limits=shared.LIMITS,
            stop_after=ENDPOINT,
            execution_stages=list(STAGES),
            source_review_required_before_release=True,
            automatic_retry=False,
            **shared.NO_CREDIT,
        )
        shared.verify_pins(pins)
        shared.write(destination / "plan.json", plan)
        (destination / "plan.json").chmod(0o444)
        return plan
    except BaseException:
        shared.write(
            destination / "preparation-failure.json",
            dict(traceback=traceback.format_exc(), **shared.NO_CREDIT),
        )
        raise


def verify_plan(prepared, expected_sha256):
    prepared = shared.output_path(prepared)
    if source_snapshot.digest(prepared / "plan.json") != expected_sha256:
        raise ValueError("Changed multi-cell diagnostic plan")
    plan = shared.read(prepared / "plan.json")
    if (
        (prepared / "preparation-failure.json").exists()
        or plan.get("kind") != KINDS[0]
        or plan.get("purpose") != "multi_cell_caller_source_diagnostic_only"
        or plan.get("cases") != list(CASES)
        or not _same(plan.get("configuration"), configuration())
        or not _same(plan.get("fixture_controls"), CONTROLS)
        or not _same(plan.get("limits"), shared.LIMITS)
        or plan.get("stop_after") != ENDPOINT
        or plan.get("execution_stages") != list(STAGES)
        or not _same({key: plan.get(key) for key in shared.NO_CREDIT}, shared.NO_CREDIT)
        or type(plan.get("cpu")) is not int
        or plan.get("automatic_retry") is not False
        or plan.get("source_review_required_before_release") is not True
    ):
        raise ValueError("Incomplete or widened multi-cell diagnostic plan")
    source = prepared / "source"
    source_snapshot.verify(source, manifest_sha256=plan["snapshot_sha256"])
    if source_snapshot.digest(source / OWN) != plan["runner_sha256"]:
        raise ValueError("Changed multi-cell worker")
    shared.verify_pins(plan["external_inputs"])
    if any(
        dict(path=name, sha256=digest) not in plan["external_inputs"]
        for name, digest in _native_inputs(source).items()
    ):
        raise ValueError("Original source authority is missing from plan pins")
    return plan


def verify_release(prepared, expected_sha256, release_path, case):
    plan = verify_plan(prepared, expected_sha256)
    release = shared.read(release_path)
    review = release.get("source_review")
    if (
        release.get("kind") != KINDS[1]
        or release.get("plan_sha256") != expected_sha256
        or release.get("snapshot_sha256") != plan["snapshot_sha256"]
        or release.get("case") != case
        or case not in CASES
        or release.get("stop_after") != ENDPOINT
        or release.get("allow_actual_source_diagnostic") is not True
        or release.get("scientific_qualification") is not False
        or type(review) is not dict
        or set(review) != {"path", "sha256"}
    ):
        raise ValueError("Exact multi-cell case, endpoint and reviewed source release required")
    shared.verify_pins([review])
    if os.sched_getaffinity(0) != {plan["cpu"]}:
        raise ValueError("Require the declared single CPU")
    return plan


class PrerequisiteRejected(ValueError):
    def __init__(self, request, trial, stage):
        super().__init__("Incomplete source prerequisite at " + stage)
        self.request, self.trial, self.stage = request, trial, stage


def _state(request, state, status, stage):
    if getattr(state, "status", None) != status:
        raise PrerequisiteRejected(request, state, stage)
    return state


def _pipeline(case, output, *, fixtures, initial, clipped, lifecycle, multi):
    if case not in CASES:
        raise ValueError("Unknown multi-cell case")
    values = {}

    def fixture():
        request, raw = fixtures.declaration(case, output)
        try:
            _declaration(case, raw)
        except Exception as error:
            raise PrerequisiteRejected(request, raw, STAGES[0]) from error
        values["initial_request"] = request
        return dict(request=request, native_comparison_inputs=raw, configuration=configuration())

    def initial_state():
        request = values["initial_request"]
        values["initial_state"] = _state(
            request, initial.prepare(request), "source_completed_unqualified", STAGES[1]
        )
        return values["initial_state"]

    def clip_request():
        values["clip_request"] = clipped.from_initial_mesh(
            values["initial_request"], values["initial_state"]
        )
        return values["clip_request"]

    def clip_state():
        request = values["clip_request"]
        values["clip_state"] = _state(
            request, clipped.prepare(request), "source_clipped_rebuilt_unqualified", STAGES[3]
        )
        return values["clip_state"]

    def lifecycle_request():
        values["lifecycle_request"] = lifecycle.from_clipped(
            values["clip_request"], values["clip_state"]
        )
        return values["lifecycle_request"]

    def lifecycle_state():
        request = values["lifecycle_request"]
        values["lifecycle_state"] = _state(
            request, lifecycle.prepare(request), "source_lifecycle_completed_unqualified", STAGES[5]
        )
        return values["lifecycle_state"]

    def caller_request():
        values["caller_request"] = multi.from_lifecycle(
            values["lifecycle_request"],
            values["lifecycle_state"],
            configuration(),
            law_id=multi.LAW_ID,
        )
        return values["caller_request"]

    def caller():
        owner = values["owner"] = multi.prepare(values["caller_request"])
        trial = owner.trial
        if trial.source_completed is not True:
            raise PrerequisiteRejected(values["caller_request"], trial, STAGES[7])
        return trial

    return tuple(
        zip(
            STAGES,
            (
                fixture,
                initial_state,
                clip_request,
                clip_state,
                lifecycle_request,
                lifecycle_state,
                caller_request,
                caller,
            ),
            strict=True,
        )
    )


def _steps(case, output):
    # All scientific imports and fixture construction stay under release and
    # resource gates. Authentication/replay calls are counted as work.
    from cells.processes import betse_initial_mesh_preparation as initial
    from cells.processes import betse_mesh_clip_preparation as clipped
    from cells.processes import betse_mesh_lifecycle_preparation as lifecycle
    from cells.processes import betse_native_multi_cell_caller as multi
    from validation.betse import betse_mesh_lifecycle_preparation_fixtures as fixtures

    return _pipeline(
        case,
        output,
        fixtures=fixtures,
        initial=initial,
        clipped=clipped,
        lifecycle=lifecycle,
        multi=multi,
    )


def worker(prepared, plan_sha256, release, case, output):
    plan = verify_release(prepared, plan_sha256, release, case)
    source = Path(prepared) / "source"
    if ROOT != source or str(Path(sys.executable).absolute()) != plan["interpreter"]:
        raise ValueError("Worker must use the declared interpreter and immutable source")
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    output = shared.execution_output(output, prepared, plan)
    evidence, work = shared.Evidence(output), shared.WorkLog(output, source, phases=STAGES)
    result = None
    try:
        with work.active():
            result = shared.run_stages(_steps(case, output), evidence, work)
        shared.write(output / "runtime-producers.json", shared.runtime_inventory(source))
        verify_plan(prepared, plan_sha256)
    except Exception as error:
        evidence.failure(error)
        result = dict(
            status="diagnostic_failed",
            failed_stage=work.phase,
            source_error=None if work.failure else shared.exception_record(error),
            observer_error=work.failure,
            interrupted_exception_graph=shared.exception_record(error) if work.failure else None,
            prior_result=result,
            captures=evidence.rows,
            observed_source_entry_attempts=work.count,
            accepted_cases=0,
            **shared.NO_CREDIT,
        )
    shared.write(
        output / "diagnostic.json",
        dict(case=case, plan_sha256=plan_sha256, stop_after=ENDPOINT, **result),
    )
    return 0 if result["status"] == "source_completed_unqualified" else 1


def launch(prepared, plan_sha256, release, case, output):
    plan = verify_release(prepared, plan_sha256, release, case)
    output = shared.execution_output(output, prepared, plan)
    output.mkdir(parents=True, exist_ok=False)
    source = Path(prepared) / "source"
    command = [
        plan["interpreter"],
        "-B",
        "-m",
        "validation.betse.native_multi_cell_caller_qualification",
        "worker",
        "--prepared",
        str(prepared),
        "--plan-sha256",
        plan_sha256,
        "--release",
        str(release),
        "--case",
        case,
        "--output",
        str(output),
    ]
    failure = process = None
    try:
        (output / "process").mkdir()
        shared.write(
            output / "inputs.json",
            dict(
                case=case,
                stop_after=ENDPOINT,
                plan_sha256=plan_sha256,
                release=shared.pin(release),
                **shared.NO_CREDIT,
            ),
        )
        if shared.guard.memory_available() < 12 * 2**30:
            raise RuntimeError("Diagnostic launch requires 12 GiB available host memory")
        process = shared.guard.run_bounded(
            command,
            directory=output / "process",
            cwd=source,
            env=shared.environment(source, plan),
            **plan["limits"],
        )
        diagnostic = shared.read(output / "diagnostic.json")
        if (
            diagnostic.get("status") != "source_completed_unqualified"
            or diagnostic.get("stop_after") != ENDPOINT
            or diagnostic.get("completed_stages") != list(STAGES)
        ):
            raise RuntimeError("Worker did not complete the declared multi-cell caller")
    except Exception as error:
        failure = shared.exception_record(error)
    record = dict(
        status="failed" if failure else "completed_unqualified",
        case=case,
        stop_after=ENDPOINT,
        process=process,
        failure=failure,
        diagnostic=shared.pin(output / "diagnostic.json")
        if (output / "diagnostic.json").is_file()
        else None,
        process_receipts=[
            shared.pin(path)
            for name in ("result.json", "failure.json", "resource-stop.json")
            if (path := output / "process" / name).is_file()
        ],
        automatic_retry=False,
        accepted_cases=0,
        **shared.NO_CREDIT,
    )
    shared.write(output / ("failure.json" if failure else "result.json"), record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--cpu", type=int, default=3)
    p.add_argument("--runtime-path", type=Path, action="append", default=[])
    for name in ("launch", "worker"):
        p = commands.add_parser(name)
        p.add_argument("--prepared", type=Path, required=True)
        p.add_argument("--plan-sha256", required=True)
        p.add_argument("--release", type=Path, required=True)
        p.add_argument("--case", choices=CASES, required=True)
        p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.output, cpu=args.cpu, runtime_paths=args.runtime_path)
    elif args.command == "launch":
        result = launch(args.prepared, args.plan_sha256, args.release, args.case, args.output)
        raise SystemExit(0 if result["status"] == "completed_unqualified" else 1)
    else:
        raise SystemExit(
            worker(args.prepared, args.plan_sha256, args.release, args.case, args.output)
        )


if __name__ == "__main__":
    main()
