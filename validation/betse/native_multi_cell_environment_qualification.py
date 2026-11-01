"""Reviewed, guarded fresh multi-cell ordinary prefix through make_maskM.

Preparation and software controls do not run source. A separate exact release
is required for each actual diagnostic. Saved owners are evidence, never inputs
for object hydration. Nine ordinary methods share one actual issued caller.
"""

import argparse
import copy
import hashlib
import importlib.abc
import os
import resource
import runpy
import sys
import traceback
from pathlib import Path

from validation import source_snapshot
from validation.betse import native_multi_cell_caller_qualification as prior
from validation.betse import native_multi_cell_environment_native as native
from validation.betse import native_single_cell_prefix_payload as payload

shared = prior.shared
ROOT = Path(__file__).resolve().parents[2]
OWN = "validation/betse/native_multi_cell_environment_qualification.py"
FILES = tuple(
    "validation/betse/native_multi_cell_environment_" + name + ".py"
    for name in ("qualification", "native", "compare")
)
TESTS = tuple(
    "tests/unit/test_native_multi_cell_environment_" + name + ".py"
    for name in ("qualification", "native", "compare")
)
PAYLOAD_TEST = "tests/unit/test_native_single_cell_prefix_payload.py"
CASES, ENDPOINT = prior.CASES, native.ENDPOINT
STAGES = (*prior.STAGES[:6], "ordinary_request", "cell_index", "make_maskM")
KINDS = ("cells.multi_environment_diagnostic_plan@1", "cells.multi_environment_release@1")
PURPOSE = "fresh_multi_cell_ordinary_source_diagnostic_only"
CONTROLS = prior.CONTROLS
CAPTURE_POLICY = dict(
    ordinary_metadata_bytes=payload.MAX_METADATA,
    request_metadata_bytes=payload.REQUEST_METADATA,
    request_label="ordinary_request",
    request_filename="capture-0006.json",
    request_fields=["caller_request", "identity"],
    caller_request_fields=[
        "lifecycle_request",
        "lifecycle_state",
        "configuration_json",
        "identity",
        "grid_descriptor",
    ],
)
SOFTWARE_GROUPS = {
    "all": "",
    "runtime-integration": "runtime_namespace",
    "numpy-integration": "numpy_helper",
    "source-repairs": "repair_c or numpy_helper",
    "capture-metadata": "capture_metadata or failed_capture_stops or repair_c5 or prefix_payload",
}


def _request_capture_schema(value):
    """Closed wire shape only; full lineage is checked by the comparison reader."""
    if type(value) is not dict or set(value) != set(CAPTURE_POLICY["request_fields"]):
        raise ValueError("Changed ordinary request capture schema")
    request = value["caller_request"]
    if (
        type(request) is not dict
        or set(request) != set(CAPTURE_POLICY["caller_request_fields"])
        or type(request["lifecycle_request"]) is not dict
        or type(request["lifecycle_state"]) is not dict
        or type(request["configuration_json"]) is not str
        or request["grid_descriptor"] != "native_grid_size_yaml_alias@1"
        or any(
            type(identity) is not str
            or len(identity) != 64
            or any(c not in "0123456789abcdef" for c in identity)
            for identity in (value["identity"], request["identity"])
        )
    ):
        raise ValueError("Changed descriptor-bearing request capture schema")


def _capture_limit(label, path):
    if label != CAPTURE_POLICY["request_label"]:
        return CAPTURE_POLICY["ordinary_metadata_bytes"]
    if Path(path).name != CAPTURE_POLICY["request_filename"]:
        raise ValueError("Nested request capture has the wrong occurrence")
    return CAPTURE_POLICY["request_metadata_bytes"]


def _write_capture(label, path, serialized):
    limit = _capture_limit(label, path)
    if label == CAPTURE_POLICY["request_label"]:
        _request_capture_schema(serialized)
    return payload.write(path, serialized, metadata_bytes=limit)


def _read_capture(path, row, *, expand, pins_only=False):
    """Authenticate role, occurrence and the same bytes decoded under its cap."""
    path = Path(path)
    if (
        type(row) is not dict
        or set(row) != {"label", "path", "status", "sha256"}
        or row["label"] not in STAGES
        or row["path"] != f"capture-{STAGES.index(row['label']):04d}.json"
        or path.name != row["path"]
        or row["status"] != "saved"
        or type(row["sha256"]) is not str
        or len(row["sha256"]) != 64
        or any(c not in "0123456789abcdef" for c in row["sha256"])
    ):
        raise ValueError("Changed ordinary capture role or binding")
    kwargs = dict(metadata_bytes=_capture_limit(row["label"], path), expected_sha256=row["sha256"])
    value = payload.read(path, expand=expand, **kwargs)
    if row["label"] == CAPTURE_POLICY["request_label"]:
        _request_capture_schema(value)
    return payload.files(path, **kwargs) if pins_only else value


def read_capture(path, row, *, expand=True):
    return _read_capture(path, row, expand=expand)


def capture_files(path, row):
    return _read_capture(path, row, expand=False, pins_only=True)


def configuration():
    return dict(prior.configuration(), **{"general options": {"comp grid size": 25}})


def _native_inputs(repository):
    rows = prior._native_inputs(repository)
    for relative, digest in native.pins_for().items():
        name = str(shared.NATIVE / relative)
        if name in rows and rows[name] != digest:
            raise ValueError("Conflicting original source authority")
        rows[name] = digest
    return rows


def prepare(destination, *, repository=ROOT, cpu=6, runtime_paths=()):
    """One-way current-checkout snapshot; original files are pinned, not copied."""
    repository = Path(repository).absolute()
    destination = shared.execution_output(destination, repository, {"runtime_paths": runtime_paths})
    if type(cpu) is not int or cpu not in os.sched_getaffinity(0):
        raise ValueError("Select an available single CPU")
    destination.mkdir(parents=True, exist_ok=False)
    try:
        closure = runpy.run_path(str(repository / shared.CLOSURE))["closure"]
        files = closure(repository, [*FILES, *TESTS, PAYLOAD_TEST])
        files[shared.CLOSURE] = source_snapshot.digest(repository / shared.CLOSURE)
        for parent in {Path(name).parent for name in files}:
            for path in (repository / parent).glob("*.json"):
                files[str(path.relative_to(repository))] = source_snapshot.digest(path)
        external, overlays = _native_inputs(repository), []
        for raw in runtime_paths:
            path = Path(raw).absolute()
            if not path.is_dir() or path.is_relative_to(repository) or path.is_symlink():
                raise ValueError("Require an explicit external runtime overlay")
            overlays.append(str(path))
            for file in path.rglob("*"):
                if file.is_file() and "__pycache__" not in file.parts:
                    row = shared.pin(file)
                    if row["path"] in external and external[row["path"]] != row["sha256"]:
                        raise ValueError("Conflicting runtime/source pin")
                    external[row["path"]] = row["sha256"]
        pins = [dict(path=p, sha256=h) for p, h in sorted(external.items())]
        shared.verify_pins(pins)
        snapshot = source_snapshot.freeze(repository, destination / "source", {p: p for p in files})
        plan = dict(
            kind=KINDS[0],
            purpose=PURPOSE,
            cases=list(CASES),
            configuration=configuration(),
            fixture_controls=CONTROLS,
            snapshot_sha256=source_snapshot.digest(destination / "source/SNAPSHOT.json"),
            git_revision=snapshot["git_revision"],
            runner_sha256=files[OWN],
            external_inputs=pins,
            runtime_paths=overlays,
            interpreter=str(Path(sys.executable).absolute()),
            cpu=cpu,
            limits=shared.LIMITS,
            stop_after=ENDPOINT,
            execution_stages=list(STAGES),
            ordinary_methods=list(native.METHODS),
            capture_transport=payload.KIND,
            capture_policy=CAPTURE_POLICY,
            source_review_required_before_release=True,
            automatic_retry=False,
            **shared.NO_CREDIT,
        )
        source_snapshot.assert_checkout_unchanged(destination / "source")
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
        raise ValueError("Changed ordinary diagnostic plan")
    plan = shared.read(prepared / "plan.json")
    fixed = dict(
        kind=KINDS[0],
        purpose=PURPOSE,
        cases=list(CASES),
        configuration=configuration(),
        fixture_controls=CONTROLS,
        limits=shared.LIMITS,
        stop_after=ENDPOINT,
        execution_stages=list(STAGES),
        ordinary_methods=list(native.METHODS),
        capture_transport=payload.KIND,
        capture_policy=CAPTURE_POLICY,
        source_review_required_before_release=True,
        automatic_retry=False,
        **shared.NO_CREDIT,
    )
    if (
        (prepared / "preparation-failure.json").exists()
        or not prior._same({key: plan.get(key) for key in fixed}, fixed)
        or type(plan.get("cpu")) is not int
    ):
        raise ValueError("Incomplete or widened ordinary diagnostic plan")
    source_snapshot.verify(prepared / "source", manifest_sha256=plan["snapshot_sha256"])
    if source_snapshot.digest(prepared / "source" / OWN) != plan["runner_sha256"]:
        raise ValueError("Changed frozen worker")
    shared.verify_pins(plan["external_inputs"])
    if any(
        dict(path=p, sha256=h) not in plan["external_inputs"]
        for p, h in _native_inputs(prepared / "source").items()
    ):
        raise ValueError("Missing original source authority")
    return plan


def verify_release(prepared, digest, release, case):
    plan = verify_plan(prepared, digest)
    grant = shared.read(release)
    fixed = dict(
        kind=KINDS[1],
        plan_sha256=digest,
        snapshot_sha256=plan["snapshot_sha256"],
        case=case,
        stop_after=ENDPOINT,
        allow_actual_source_diagnostic=True,
        scientific_qualification=False,
    )
    review = grant.get("source_review")
    if (
        case not in CASES
        or not prior._same({key: grant.get(key) for key in fixed}, fixed)
        or type(review) is not dict
        or set(review) != {"path", "sha256"}
    ):
        raise ValueError("Exact ordinary endpoint and reviewed release required")
    shared.verify_pins([review])
    if os.sched_getaffinity(0) != {plan["cpu"]}:
        raise ValueError("Require the declared one CPU")
    return plan


def _pipeline(case, output, *, fixtures, initial, clipped, lifecycle, multi, environment):
    # Reuse only the first six prerequisite actions, with their original error
    # handling. The fresh ordinary request is constructed before caller birth.
    old = prior._pipeline(
        case,
        output,
        fixtures=fixtures,
        initial=initial,
        clipped=clipped,
        lifecycle=lifecycle,
        multi=multi,
    )
    retained, actions = {}, []
    for name, action in old[:6]:

        def step(name=name, action=action):
            value = action()
            retained[name] = value
            if name == STAGES[0]:
                value = dict(value, configuration=configuration())
            return value

        actions.append((name, step))

    def request():
        value = environment.from_lifecycle(
            retained["lifecycle_request"],
            retained["post_clip_lifecycle"],
            configuration(),
            law_id=environment.LAW_ID,
        )
        retained["request"] = value
        return value

    def caller():
        owner = multi.prepare(retained["request"].caller_request)
        retained["caller_owner"] = owner
        if owner.trial.source_completed is not True:
            raise prior.PrerequisiteRejected(retained["request"], owner.trial, "cell_index")
        return owner.trial

    def ordinary():
        req = environment.from_caller(retained["caller_owner"], law_id=environment.LAW_ID)
        retained["continuation_request"] = req
        owner = environment.prepare_continuation(req)
        retained["environment_owner"] = owner
        if owner.trial.source_completed is not True:
            raise prior.PrerequisiteRejected(req, owner.trial, ENDPOINT)
        return owner.trial

    return (*actions, (STAGES[6], request), (STAGES[7], caller), (STAGES[8], ordinary))


def _steps(case, output):
    from cells.processes import betse_initial_mesh_preparation as initial
    from cells.processes import betse_mesh_clip_preparation as clipped
    from cells.processes import betse_mesh_lifecycle_preparation as lifecycle
    from cells.processes import betse_native_multi_cell_caller as multi
    from cells.processes import betse_native_multi_cell_environment as environment
    from validation.betse import betse_mesh_lifecycle_preparation_fixtures as fixtures

    return _pipeline(
        case,
        output,
        fixtures=fixtures,
        initial=initial,
        clipped=clipped,
        lifecycle=lifecycle,
        multi=multi,
        environment=environment,
    )


def worker(prepared, digest, release, case, output):
    plan = verify_release(prepared, digest, release, case)
    source = Path(prepared) / "source"
    if ROOT != source or str(Path(sys.executable).absolute()) != plan["interpreter"]:
        raise ValueError("Use the frozen source and declared interpreter")
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    output = shared.execution_output(output, prepared, plan)
    evidence, work = (
        shared.Evidence(output, sidecars=True, capture_writer=_write_capture),
        shared.WorkLog(output, source, phases=STAGES),
    )
    result = None
    stage = "source_execution"
    try:
        with work.active():
            result = shared.run_stages(_steps(case, output), evidence, work)
            stage = "postprocessing.source_observer_finalization"
        stage = "postprocessing.saved_geometry_diagnostics"
        if result["status"] == "source_completed_unqualified":
            from validation.betse.native_multi_cell_environment_compare import (
                diagnostics_from_cache,
            )

            final = payload.read(output / evidence.rows[-1]["path"])
            # Observation of saved typed bits has no live-owner/source entry.
            domain = diagnostics_from_cache(final["cache"])
            shared.write(output / "domain-diagnostics.json", domain)
            result["domain_diagnostics"] = shared.pin(output / "domain-diagnostics.json")
        stage = "postprocessing.runtime_inventory"
        shared.write(output / "runtime-producers.json", shared.runtime_inventory(source))
        stage = "postprocessing.end_pin_verification"
        verify_plan(prepared, digest)
    except Exception as error:
        prior = copy.deepcopy(result)
        recording_error = None
        try:
            evidence.failure(error)
        except Exception as secondary:
            recording_error = shared.exception_record(secondary)
        if stage == "source_execution":
            result = dict(
                status="diagnostic_failed",
                failed_stage=work.phase,
                source_error=None if work.failure else shared.exception_record(error),
                observer_error=work.failure,
                interrupted_exception_graph=shared.exception_record(error)
                if work.failure
                else None,
                prior_result=prior,
                captures=evidence.rows,
                observed_source_entry_attempts=work.count,
                accepted_cases=0,
                **shared.NO_CREDIT,
            )
        else:
            # A metadata failure cannot rewrite a completed source call or
            # erase a primary source/observer failure already in its result.
            result = dict(
                prior or {},
                status="diagnostic_failed",
                accepted_cases=0,
                failed_stage=(prior or {}).get("failed_stage") or stage,
                source_error=(prior or {}).get("source_error"),
                observer_error=(prior or {}).get("observer_error") or work.failure,
                interrupted_exception_graph=(prior or {}).get("interrupted_exception_graph"),
                completed_stages=list((prior or {}).get("completed_stages", [])),
                prior_result=prior,
                captures=evidence.rows,
                observed_source_entry_attempts=work.count,
                postprocessing_stage=stage,
                postprocessing_error=shared.exception_record(error),
                **shared.NO_CREDIT,
            )
        if recording_error is not None:
            result["failure_capture_error"] = recording_error
    shared.write(
        output / "diagnostic.json",
        dict(case=case, plan_sha256=digest, stop_after=ENDPOINT, **result),
    )
    return int(result["status"] != "source_completed_unqualified")


def launch(prepared, digest, release, case, output):
    plan = verify_release(prepared, digest, release, case)
    output = shared.execution_output(output, prepared, plan)
    output.mkdir(parents=True, exist_ok=False)
    process = failure = None
    try:
        (output / "process").mkdir()
        shared.write(
            output / "inputs.json",
            dict(
                case=case,
                stop_after=ENDPOINT,
                plan_sha256=digest,
                release=shared.pin(release),
                **shared.NO_CREDIT,
            ),
        )
        if shared.guard.memory_available() < 12 * 2**30:
            raise RuntimeError("Require 12 GiB available launch memory")
        command = [
            plan["interpreter"],
            "-B",
            "-m",
            "validation.betse.native_multi_cell_environment_qualification",
            "worker",
            "--prepared",
            str(prepared),
            "--plan-sha256",
            digest,
            "--release",
            str(release),
            "--case",
            case,
            "--output",
            str(output),
        ]
        process = shared.guard.run_bounded(
            command,
            directory=output / "process",
            cwd=Path(prepared) / "source",
            env=shared.environment(Path(prepared) / "source", plan),
            **plan["limits"],
        )
        recorded = shared.read(output / "diagnostic.json")
        if (
            process["returncode"] != 0
            or recorded.get("status") != "source_completed_unqualified"
            or recorded.get("completed_stages") != list(STAGES)
            or recorded.get("stop_after") != ENDPOINT
        ):
            raise RuntimeError("Ordinary diagnostic did not complete its exact boundary")
    except Exception as error:
        failure = shared.exception_record(error)
    result = dict(
        status="failed" if failure else "completed_unqualified",
        case=case,
        stop_after=ENDPOINT,
        process=process,
        failure=failure,
        diagnostic=shared.pin(output / "diagnostic.json")
        if (output / "diagnostic.json").is_file()
        else None,
        process_receipts=[
            shared.pin(output / "process" / p)
            for p in ("result.json", "failure.json", "resource-stop.json")
            if (output / "process" / p).is_file()
        ],
        automatic_retry=False,
        accepted_cases=0,
        **shared.NO_CREDIT,
    )
    shared.write(output / ("failure.json" if failure else "result.json"), result)
    return result


def software_child(output, group="all"):
    """All controls run behind import and native-file entry blockades."""
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    import pytest

    attempts = []

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in {
                "cells",
                "betse",
                "numpy",
                "scipy",
                "PIL",
                "jax",
                "jaxlib",
            }:
                attempts.append(fullname)
                raise AssertionError("Scientific import forbidden: " + fullname)

    blocker = Block()
    previous = sys.getprofile()

    def profile(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if event == "call" and frame.f_code.co_filename.startswith(str(shared.NATIVE) + "/"):
            attempts.append(frame.f_code.co_qualname)
            raise AssertionError("Actual original source entry forbidden")

    (output / "case-reports").mkdir()

    class Reports:
        def pytest_runtest_logreport(self, report):
            if report.when == "call" or report.failed:
                key = hashlib.sha256((report.nodeid + report.when).encode()).hexdigest()
                shared.write(
                    output / "case-reports" / (key + ".json"),
                    dict(
                        nodeid=report.nodeid,
                        when=report.when,
                        outcome=report.outcome,
                        traceback=str(report.longrepr) if report.failed else None,
                        native_entry_attempts=list(attempts),
                    ),
                )

    try:
        sys.meta_path.insert(0, blocker)
        sys.setprofile(profile)
        arguments = [
            "-q",
            "--noconftest",
            "-c",
            "/dev/null",
            "-p",
            "no:cacheprovider",
            *(str(ROOT / p) for p in TESTS),
            "--junitxml=" + str(output / "tests.xml"),
            "--basetemp=" + str(output / "tmp"),
        ]
        if SOFTWARE_GROUPS[group]:
            arguments += ["-k", SOFTWARE_GROUPS[group]]
        if group == "capture-metadata":
            arguments.append(str(ROOT / PAYLOAD_TEST))
        code = pytest.main(arguments, plugins=[Reports()])
    finally:
        sys.setprofile(previous)
        sys.meta_path.remove(blocker)
        shared.write(
            output / "native-entry-guard.json", dict(attempted=attempts, scientific_credit=False)
        )
        shared.write(output / "runtime-producers.json", shared.runtime_inventory(ROOT))
    shared.write(output / "pytest-exit.json", dict(returncode=int(code)))
    return int(code) if not attempts else 1


def software(output, group="all", *, cpu=6):
    if group not in SOFTWARE_GROUPS:
        raise ValueError("Unknown focused software group")
    output = shared.execution_output(output, ROOT, {"runtime_paths": []})
    output.mkdir(parents=True, exist_ok=False)
    plan = prepare(output / "prepared", cpu=cpu)
    source = output / "prepared/source"
    (output / "process").mkdir()
    env = shared.environment(source, plan)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    process = shared.guard.run_bounded(
        [
            plan["interpreter"],
            "-B",
            "-m",
            "validation.betse.native_multi_cell_environment_qualification",
            "software-child",
            "--output",
            str(output),
            "--group",
            group,
        ],
        directory=output / "process",
        cwd=source,
        env=env,
        **plan["limits"],
    )
    # The frozen bytes/loaded producers decide the execution, not a later HEAD.
    source_snapshot.verify(source, manifest_sha256=plan["snapshot_sha256"])
    producers = shared.read(output / "runtime-producers.json")
    for name, row in producers.items():
        if source_snapshot.digest(row["path"]) != row["sha256"]:
            raise ValueError("Changed loaded producer: " + name)
        if name.startswith("validation.") and not Path(row["path"]).is_relative_to(source):
            raise ValueError("Validation producer escaped immutable source")
    drift = None
    try:
        source_snapshot.assert_checkout_unchanged(source)
    except Exception as error:
        drift = shared.exception_record(error)
    result = dict(
        status="passed" if process["returncode"] == 0 else "failed",
        group=group,
        process=process,
        snapshot=shared.pin(source / "SNAPSHOT.json"),
        source_pins={p: shared.pin(source / p) for p in (*FILES, *TESTS)},
        checkout_drift=drift,
        integration_pending=drift is not None,
        native_entry_guard=shared.pin(output / "native-entry-guard.json"),
        **shared.NO_CREDIT,
    )
    shared.write(output / "software-result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    item = sub.add_parser("prepare")
    item.add_argument("--output", type=Path, required=True)
    item.add_argument("--cpu", type=int, default=6)
    item.add_argument("--runtime-path", type=Path, action="append", default=[])
    for name in ("software", "software-child"):
        item = sub.add_parser(name)
        item.add_argument("--output", type=Path, required=True)
        item.add_argument("--group", choices=SOFTWARE_GROUPS, default="all")
    for name in ("launch", "worker"):
        item = sub.add_parser(name)
        item.add_argument("--prepared", type=Path, required=True)
        item.add_argument("--plan-sha256", required=True)
        item.add_argument("--release", type=Path, required=True)
        item.add_argument("--case", choices=CASES, required=True)
        item.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
        prepare(args.output, cpu=args.cpu, runtime_paths=args.runtime_path)
    elif args.command == "software":
        return int(software(args.output, args.group)["status"] != "passed")
    elif args.command == "software-child":
        return software_child(args.output, args.group)
    elif args.command == "worker":
        return worker(args.prepared, args.plan_sha256, args.release, args.case, args.output)
    else:
        return int(
            launch(args.prepared, args.plan_sha256, args.release, args.case, args.output)["status"]
            != "completed_unqualified"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
