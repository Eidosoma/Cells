"""Fresh issued multi-world mapping diagnostic; no saved-owner hydration.

Preparation and blocked software are unreleased. A separate exact reviewed
release is mandatory before constructing a caller or executing source work.
"""

import argparse
import copy
import os
import resource
import runpy
import sys
from pathlib import Path
from types import FunctionType

from validation import source_snapshot
from validation.betse import native_multi_cell_environment_qualification as prefix
from validation.betse import native_tissue_to_grid_native as native

shared, payload = prefix.shared, prefix.payload
ROOT = Path(__file__).resolve().parents[2]
OWN = "validation/betse/native_tissue_to_grid_qualification.py"
MODULE = "validation.betse.native_tissue_to_grid_qualification"
FILES = tuple(
    "validation/betse/native_tissue_to_grid_" + n + ".py"
    for n in ("qualification", "native", "compare")
)
TESTS = tuple(
    "tests/unit/test_native_tissue_to_grid_" + n + ".py"
    for n in ("qualification", "native", "compare")
)
ENDPOINT, CASES = native.ENDPOINT, prefix.CASES
STAGES = (*prefix.STAGES, "world_data", "mapping_probes")
KINDS = ("cells.tissue_to_grid_plan@2", "cells.tissue_to_grid_release@2")
PURPOSE = "fresh_issued_multi_world_mapping_source_diagnostic"
SOFTWARE_GROUPS = {
    "all": "",
    "ast": "source_ast",
    "focused": "not source_ast",
    "tail-transition": "",
    "mapping-repairs": "",
}
CAPTURE_POLICY = copy.deepcopy(prefix.CAPTURE_POLICY)
RESULT_KIND = "cells.issued_tissue_to_grid_capture@1"
read_capture = prefix.read_capture
capture_files = prefix.capture_files


class WorldDataContinuationRejected(ValueError):
    """Keep the completed actual Poisson trial if its tail continuation fails."""

    def __init__(self, source_error, poisson_trial):
        super().__init__("World data continuation failed after the retained Poisson trial")
        self.source_error = source_error
        self.capture_error = None
        self.upstream_trial = poisson_trial
        self.partial = dict(
            completed_poisson_trial=poisson_trial, usable_world_child_available=False
        )
        self.stage = "world_data_tail"


def _retarget(function, **globals):
    result = FunctionType(
        function.__code__,
        dict(function.__globals__, **globals),
        function.__name__,
        function.__defaults__,
        function.__closure__,
    )
    result.__kwdefaults__ = function.__kwdefaults__
    return result


class StageTimings(prefix.StageTimings):
    _checkpoint = _retarget(prefix.StageTimings._checkpoint, STAGES=STAGES)


class TimedEvidence(prefix.TimedEvidence):
    save = _retarget(prefix.TimedEvidence.save, STAGES=STAGES)
    failure = _retarget(prefix.TimedEvidence.failure, STAGES=STAGES)


def configuration():
    return prefix.configuration()


def _fixed(wall_seconds=480):
    return dict(
        kind=KINDS[0],
        purpose=PURPOSE,
        cases=list(CASES),
        configuration=configuration(),
        fixture_controls=prefix.CONTROLS,
        stop_after=ENDPOINT,
        execution_stages=list(STAGES),
        ordinary_methods=list(native.METHODS),
        probe_policy=native.PROBE_POLICY,
        world_owner_prerequisites=["poisson", "six_store_data_tail"],
        limits=prefix._diagnostic_limits(wall_seconds),
        capture_transport=payload.KIND,
        capture_policy=CAPTURE_POLICY,
        source_review_required_before_release=True,
        automatic_retry=False,
        **shared.NO_CREDIT,
    )


def _native_inputs(repository):
    result = prefix._native_inputs(repository)
    for name, digest in native.pins_for().items():
        path = str(shared.NATIVE / name)
        if path in result and result[path] != digest:
            raise ValueError("Conflicting mapping source pins")
        result[path] = digest
    return result


def prepare(destination, *, repository=ROOT, cpu=6, runtime_paths=(), wall_seconds=480):
    repository = Path(repository).absolute()
    destination = shared.execution_output(destination, repository, {"runtime_paths": runtime_paths})
    if type(cpu) is not int or cpu not in os.sched_getaffinity(0):
        raise ValueError("Declare one available preparation CPU")
    fixed = _fixed(wall_seconds)
    destination.mkdir(parents=True, exist_ok=False)
    try:
        closure = runpy.run_path(str(repository / shared.CLOSURE))["closure"]
        files = closure(repository, [*FILES, *TESTS])
        files[shared.CLOSURE] = source_snapshot.digest(repository / shared.CLOSURE)
        for parent in {Path(name).parent for name in files}:
            for path in (repository / parent).glob("*.json"):
                files[str(path.relative_to(repository))] = source_snapshot.digest(path)
        external, overlays = _native_inputs(repository), []
        for raw in runtime_paths:
            path = Path(raw).absolute()
            if not path.is_dir() or path.is_symlink() or path.is_relative_to(repository):
                raise ValueError("Explicit external runtime overlay required")
            overlays.append(str(path))
            for item in path.rglob("*"):
                if item.is_file() and "__pycache__" not in item.parts:
                    row = shared.pin(item)
                    if row["path"] in external and external[row["path"]] != row["sha256"]:
                        raise ValueError("Conflicting external runtime pin")
                    external[row["path"]] = row["sha256"]
        pins = [dict(path=p, sha256=h) for p, h in sorted(external.items())]
        shared.verify_pins(pins)
        snapshot = source_snapshot.freeze(repository, destination / "source", {p: p for p in files})
        plan = dict(
            fixed,
            snapshot_sha256=source_snapshot.digest(destination / "source/SNAPSHOT.json"),
            git_revision=snapshot["git_revision"],
            runner_sha256=files[OWN],
            external_inputs=pins,
            runtime_paths=overlays,
            interpreter=str(Path(sys.executable).absolute()),
            cpu=cpu,
        )
        source_snapshot.assert_checkout_unchanged(destination / "source")
        shared.verify_pins(pins)
        shared.write(destination / "plan.json", plan)
        (destination / "plan.json").chmod(0o444)
        return plan
    except BaseException as error:
        shared.write(
            destination / "preparation-failure.json",
            dict(error=shared.exception_record(error), **shared.NO_CREDIT),
        )
        raise


def verify_plan(prepared, digest):
    prepared = shared.output_path(prepared)
    if source_snapshot.digest(prepared / "plan.json") != digest:
        raise ValueError("Changed mapping diagnostic plan")
    plan = shared.read(prepared / "plan.json")
    if type(plan.get("limits")) is not dict:
        raise ValueError("Missing mapping diagnostic plan resource limits")
    fixed = _fixed(plan["limits"].get("timeout"))
    if (
        (prepared / "preparation-failure.json").exists()
        or not native.prefix.same({k: plan.get(k) for k in fixed}, fixed)
        or type(plan.get("cpu")) is not int
    ):
        raise ValueError("Incomplete or widened mapping plan")
    source_snapshot.verify(prepared / "source", manifest_sha256=plan["snapshot_sha256"])
    if source_snapshot.digest(prepared / "source" / OWN) != plan["runner_sha256"]:
        raise ValueError("Changed frozen mapping runner")
    shared.verify_pins(plan["external_inputs"])
    if any(
        dict(path=p, sha256=h) not in plan["external_inputs"]
        for p, h in _native_inputs(prepared / "source").items()
    ):
        raise ValueError("Missing mapping source authority")
    return plan


def verify_release(prepared, digest, release, case):
    return _retarget(
        prefix.verify_release, verify_plan=verify_plan, KINDS=KINDS, ENDPOINT=ENDPOINT, CASES=CASES
    )(prepared, digest, release, case)


def _pipeline(
    case,
    output,
    *,
    fixtures,
    initial,
    clipped,
    lifecycle,
    multi,
    environment,
    poisson,
    world,
    mapping,
):
    retained = {}

    class EnvironmentAPI:
        def __getattr__(self, name):
            return getattr(environment, name)

        def prepare_continuation(self, request):
            owner = environment.prepare_continuation(request)
            retained["environment_owner"] = owner
            return owner

    actions = prefix._pipeline(
        case,
        output,
        fixtures=fixtures,
        initial=initial,
        clipped=clipped,
        lifecycle=lifecycle,
        multi=multi,
        environment=EnvironmentAPI(),
    )

    def operators():
        request = poisson.from_environment(retained["environment_owner"], law_id=poisson.LAW_ID)
        owner = poisson.prepare_continuation(request)
        retained["poisson_owner"] = owner
        return owner.trial

    def tail():
        request = world.from_poisson(retained["poisson_owner"], law_id=world.LAW_ID)
        owner = world.prepare_continuation(request)
        retained["world_owner"] = owner
        return owner.trial

    def world_data():
        poisson_trial = operators()
        try:
            tail_trial = tail()
        except BaseException as primary:
            raise WorldDataContinuationRejected(primary, poisson_trial) from primary
        # One outer recorder phase, with both separate source trials intact.
        # Their source/body/wrapper ledgers describe work, not extra cases.
        return dict(poisson=poisson_trial, tail=tail_trial)

    def probes():
        parent = world._authority(retained["world_owner"])
        caller = world._prefix(parent).caller
        declared = tuple(mapping.Probe(**p) for p in native.probe_inputs(caller))
        request = mapping.from_world(retained["world_owner"], declared, law_id=mapping.LAW_ID)
        owner = mapping.prepare(request)
        context = mapping._authority(owner)
        if owner.trial.source_completed is not True:
            raise prefix.prior.PrerequisiteRejected(request, owner.trial, ENDPOINT)
        return dict(
            kind=RESULT_KIND,
            probe_policy=native.PROBE_POLICY,
            request=mapping._request_record(request),
            trial=owner.trial,
            inputs=context.input_cache,
            environment_cache=retained["environment_owner"].trial.cache,
            stream_before=parent.trial.stream_after,
            stream_after=mapping.core.initial._rng_stream(world._prefix(parent).rng),
            work_is_not_independent_cases=True,
        )

    return (*actions, (STAGES[9], world_data), (STAGES[10], probes))


def _steps(case, output):
    from cells.processes import betse_initial_mesh_preparation as initial
    from cells.processes import betse_mesh_clip_preparation as clipped
    from cells.processes import betse_mesh_lifecycle_preparation as lifecycle
    from cells.processes import betse_native_multi_cell_tissue_to_grid as mapping
    from validation.betse import betse_mesh_lifecycle_preparation_fixtures as fixtures

    return _pipeline(
        case,
        output,
        fixtures=fixtures,
        initial=initial,
        clipped=clipped,
        lifecycle=lifecycle,
        multi=mapping.multi,
        environment=mapping.world.environment,
        poisson=mapping.world.poisson,
        world=mapping.world,
        mapping=mapping,
    )


def worker(prepared, digest, release, case, output):
    plan = verify_release(prepared, digest, release, case)
    source = Path(prepared) / "source"
    if ROOT != source or str(Path(sys.executable).absolute()) != plan["interpreter"]:
        raise ValueError("Frozen source and declared interpreter required")
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    output = shared.execution_output(output, prepared, plan)
    work = shared.WorkLog(output, source, phases=STAGES)
    timing = StageTimings(output, work)
    evidence = TimedEvidence(
        shared.Evidence(output, sidecars=True, capture_writer=prefix._write_capture), timing
    )
    result = None
    stage = "source_execution"
    try:
        with work.active():
            result = shared.run_stages(timing.steps(_steps(case, output)), evidence, work)
            stage = "postprocessing.observer_finalization"
        if result["status"] == "source_completed_unqualified":
            stage = "postprocessing.mapping_diagnostics"
            from validation.betse.native_tissue_to_grid_compare import diagnostics

            final = prefix.read_capture(output / evidence.rows[-1]["path"], evidence.rows[-1])
            shared.write(output / "domain-diagnostics.json", diagnostics(final))
            result["domain_diagnostics"] = shared.pin(output / "domain-diagnostics.json")
        stage = "postprocessing.runtime_inventory"
        shared.write(output / "runtime-producers.json", shared.runtime_inventory(source))
        stage = "postprocessing.end_pin_verification"
        verify_plan(prepared, digest)
    except Exception as error:
        prior = copy.deepcopy(result)
        try:
            evidence.failure(error)
        except Exception as capture:
            capture_record = shared.exception_record(capture)
        else:
            capture_record = None
        result = dict(
            prior or {},
            status="diagnostic_failed",
            accepted_cases=0,
            failed_stage=(prior or {}).get("failed_stage")
            or (work.phase if stage == "source_execution" else stage),
            source_error=(prior or {}).get("source_error")
            or (
                shared.exception_record(error)
                if stage == "source_execution" and not work.failure
                else None
            ),
            observer_error=(prior or {}).get("observer_error") or work.failure,
            prior_result=prior,
            captures=evidence.rows,
            observed_source_entry_attempts=work.count,
            failure_capture_error=capture_record,
            **shared.NO_CREDIT,
        )
        if stage != "source_execution":
            result.update(
                postprocessing_stage=stage, postprocessing_error=shared.exception_record(error)
            )
    shared.write(
        output / "diagnostic.json",
        dict(
            case=case,
            plan_sha256=digest,
            stop_after=ENDPOINT,
            timing_observation_failures=timing.failures,
            **result,
        ),
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
            raise RuntimeError("Require 12GiB launch memory")
        process = shared.guard.run_bounded(
            [
                plan["interpreter"],
                "-B",
                "-m",
                MODULE,
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
            ],
            directory=output / "process",
            cwd=Path(prepared) / "source",
            env=shared.environment(Path(prepared) / "source", plan),
            **plan["limits"],
        )
        record = shared.read(output / "diagnostic.json")
        if record.get("status") != "source_completed_unqualified" or record.get(
            "completed_stages"
        ) != list(STAGES):
            raise RuntimeError("Fresh mapping diagnostic did not reach exact endpoint")
    except Exception as error:
        failure = shared.exception_record(error)
    result = dict(
        status="failed" if failure else "completed_unqualified",
        case=case,
        stop_after=ENDPOINT,
        process=process,
        failure=failure,
        automatic_retry=False,
        accepted_cases=0,
        diagnostic=shared.pin(output / "diagnostic.json")
        if (output / "diagnostic.json").is_file()
        else None,
        process_receipts=[
            shared.pin(output / "process" / p)
            for p in ("result.json", "failure.json", "resource-stop.json")
            if (output / "process" / p).is_file()
        ],
        **shared.NO_CREDIT,
    )
    shared.write(output / ("failure.json" if failure else "result.json"), result)
    return result


def supervised_launch(prepared, digest, release, case, output):
    # Reuse the reviewed output-domain check and protected failure writer. The
    # coordinator runs long controllers detached with their existing logs.
    return _retarget(prefix.supervised_launch, verify_plan=verify_plan, launch=launch)(
        prepared, digest, release, case, output
    )


def _software_selection(group, items):
    if group not in ("tail-transition", "mapping-repairs"):
        return prefix._software_selection(group, items)
    selected, deselected = [], []
    for item in items:
        name = getattr(item, "originalname", None) or item.name.split("[", 1)[0]
        parts = ["tail", "dispatch_after_one_fresh", "exact_seven_cache_pairs"]
        if group == "mapping-repairs":
            parts += ["descriptor_factory", "return_retained", "forensic", "capture_after_return"]
        destination = selected if any(part in name for part in parts) else deselected
        destination.append(item)
    return selected, deselected


def software_child(output, group="all"):
    # Only tiny synthetic list/ndarray conversions use NumPy. The inherited
    # native-file/import blockade stays active; RNG and numerical operators
    # are forbidden explicitly before any test can run.
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    import numpy as np

    saved, attempted = [], []

    def forbidden(name):
        def entry(*args, **kwargs):
            attempted.append(name)
            raise AssertionError("Actual RNG/operator forbidden: " + name)

        return entry

    for label, module in (("random", np.random), ("linalg", np.linalg)):
        for name, value in tuple(vars(module).items()):
            if (
                not name.startswith("_")
                and callable(value)
                and not (isinstance(value, type) and issubclass(value, BaseException))
            ):
                saved.append((module, name, value))
                setattr(module, name, forbidden(label + "." + name))
    try:
        result = _retarget(
            prefix.software_child,
            ROOT=ROOT,
            TESTS=TESTS,
            SOFTWARE_GROUPS=SOFTWARE_GROUPS,
            _software_selection=_software_selection,
        )(output, group)
    finally:
        for module, name, value in saved:
            setattr(module, name, value)
        shared.write(
            output / "synthetic-array-guard.json",
            dict(
                allowed="small synthetic ndarray conversion and inspection only",
                actual_rng_or_operator_attempts=attempted,
                actual_source_reference_credit=0,
            ),
        )
    return int(result) if not attempted else 1


def software(output, group="all", *, cpu=6):
    if group not in SOFTWARE_GROUPS:
        raise ValueError("Unknown focused group")
    output = shared.execution_output(output, ROOT, {"runtime_paths": []})
    output.mkdir(parents=True, exist_ok=False)
    try:
        plan = prepare(output / "prepared", cpu=cpu, wall_seconds=480)
    except BaseException as error:
        result = dict(
            status="failed_preexecution",
            group=group,
            failure=shared.exception_record(error),
            tests_started=False,
            failed_stage="immutable_source_preparation",
            automatic_retry=False,
            guard_closure_available=False,
            **shared.NO_CREDIT,
        )
        shared.write(output / "software-result.json", result)
        raise
    source = output / "prepared/source"
    (output / "process").mkdir()
    env = shared.environment(source, plan)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    process = failure = None
    try:
        process = shared.guard.run_bounded(
            [
                plan["interpreter"],
                "-B",
                "-m",
                MODULE,
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
    except Exception as error:
        failure = shared.exception_record(error)
    source_snapshot.verify(source, manifest_sha256=plan["snapshot_sha256"])
    drift = None
    try:
        source_snapshot.assert_checkout_unchanged(source)
    except Exception as error:
        drift = shared.exception_record(error)
    result = dict(
        status="failed" if failure else "passed",
        group=group,
        process=process,
        failure=failure,
        snapshot=shared.pin(source / "SNAPSHOT.json"),
        checkout_drift=drift,
        integration_pending=drift is not None,
        source_pins={p: shared.pin(source / p) for p in (*FILES, *TESTS)},
        **shared.NO_CREDIT,
    )
    if (output / "native-entry-guard.json").is_file():
        guard = shared.read(output / "native-entry-guard.json")
        if guard["attempted"]:
            result.update(status="failed", guard_violation=True)
    else:
        result.update(status="failed", guard_closure_missing=True)
    if (output / "runtime-producers.json").is_file():
        for name, row in shared.read(output / "runtime-producers.json").items():
            if source_snapshot.digest(row["path"]) != row["sha256"] or (
                name.startswith("validation.") and not Path(row["path"]).is_relative_to(source)
            ):
                raise ValueError("Unbound immutable software producer: " + name)
    shared.write(output / "software-result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    item = sub.add_parser("prepare")
    item.add_argument("--output", type=Path, required=True)
    item.add_argument("--cpu", type=int, default=6)
    item.add_argument("--wall-seconds", type=int, choices=(480, 1800), default=480)
    item.add_argument("--runtime-path", type=Path, action="append", default=[])
    for name in ("software", "software-child"):
        item = sub.add_parser(name)
        item.add_argument("--output", type=Path, required=True)
        item.add_argument("--group", choices=SOFTWARE_GROUPS, default="all")
    for name in ("worker", "launch", "supervise"):
        item = sub.add_parser(name)
        for flag, typ in (
            ("prepared", Path),
            ("plan-sha256", str),
            ("release", Path),
            ("case", str),
            ("output", Path),
        ):
            item.add_argument("--" + flag, type=typ, required=True)
    args = parser.parse_args()
    if args.command in ("prepare", "software", "launch", "supervise"):
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
    if args.command == "prepare":
        prepare(
            args.output,
            cpu=args.cpu,
            runtime_paths=args.runtime_path,
            wall_seconds=args.wall_seconds,
        )
        return 0
    if args.command == "software":
        return int(software(args.output, args.group)["status"] != "passed")
    if args.command == "software-child":
        return software_child(args.output, args.group)
    if args.command == "worker":
        return worker(args.prepared, args.plan_sha256, args.release, args.case, args.output)
    launcher = supervised_launch if args.command == "supervise" else launch
    return int(
        launcher(args.prepared, args.plan_sha256, args.release, args.case, args.output)["status"]
        != "completed_unqualified"
    )


if __name__ == "__main__":
    raise SystemExit(main())
