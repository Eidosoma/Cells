"""Bounded, non-overwriting CORE-010 artifact acceptance on the ordinary CPU engine."""

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import replace
from pathlib import Path
from time import monotonic, sleep

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cells.batch_io import load_batch_snapshot  # noqa: E402
from cells.batch_window_io import write_windowed_batch  # noqa: E402
from cells.core.runner import branch_checkpoint, run  # noqa: E402
from cells.core.specs import ChannelChange, ConfigError, read_json  # noqa: E402
from cells.core.windows import WindowPolicy  # noqa: E402
from cells.io import _sha256 as sha  # noqa: E402
from cells.io import _write_json as write_json  # noqa: E402
from cells.io import (  # noqa: E402
    load_snapshot,
    runtime_identity,
    source_hashes,
    write_run,
    write_snapshot,
)
from cells.window_io import write_windowed_run  # noqa: E402
from scripts import spatial_extracellular_acceptance_plan as plan  # noqa: E402
from scripts.audit_preserved_spatial_extracellular_reference import (  # noqa: E402
    ARCHIVE_SHA,
    extract_sources,
)
from scripts.audit_preserved_spatial_extracellular_reference import (  # noqa: E402
    audit as audit_reference,
)
from scripts.audit_spatial_extracellular_build import implementation, panel_results  # noqa: E402
from scripts.spatial_extracellular_acceptance_resources import (  # noqa: E402
    PROFILES,
    authenticate_prior_stop,
    from_registration,
    get_resources,
)
from scripts.spatial_extracellular_production_audit import authenticate, require  # noqa: E402
from scripts.verify_multispecies_build import (  # noqa: E402
    ARCHIVED_WORKER,
    REPLAY_WORKER,
    old_regressions,
)
from scripts.verify_windows_build import assert_full, baseline, payloads  # noqa: E402
from tests.spatial_extracellular_fixtures import REFERENCE, load_cases  # noqa: E402


def guard(output, started, resources=None):
    resources = resources or from_registration(read_json(output / "registration.json"))
    require(
        monotonic() - started <= resources.max_seconds,
        "CORE-010 wall budget exceeded; no automatic retry",
    )
    require(
        sum(p.stat().st_size for p in output.rglob("*") if p.is_file()) <= plan.MAX_BYTES,
        "CORE-010 artifact budget exceeded; no automatic retry",
    )


def context(output):
    registration = read_json(output / "registration.json")
    resources = from_registration(registration)
    require(
        source_hashes() == registration["source_hashes"]
        and runtime_identity() == registration["runtime"],
        "Registered source/runtime changed",
    )
    require(
        implementation(resources) == registration["implementation_files_sha256"],
        "Registered implementation changed",
    )


def eager(output, names):
    context(output)
    _, cases = load_cases()
    available = {c.id: c for c in cases}
    registration = read_json(output / "registration.json")
    lane = str(next(iter(os.sched_getaffinity(0))))
    require(
        len(os.sched_getaffinity(0)) == 1 and names == registration["eager_schedule"][lane],
        "Eager lane differs",
    )
    for name in names:
        print(f"Eager spatial CPU {lane}: {name}", flush=True)
        result = run(plan.registered_spec(available[name], "eager"))
        write_run(
            output / "eager" / name,
            result,
            checkpoint_times=(float(result.times[len(result.times) // 2]),),
            provenance={"operation": "CORE-010", "reference_case": name},
        )
        context(output)


class EagerWorkers:
    def __init__(self, output, cases):
        self.processes, self.logs = [], []
        self.schedule = plan.eager_schedule(cases)
        try:
            for cpu, names in self.schedule.items():
                log = (output / f"eager-cpu{cpu}.log").open("x")
                self.logs.append(log)
                self.processes.append(
                    subprocess.Popen(
                        [
                            "taskset",
                            "-c",
                            cpu,
                            sys.executable,
                            str(Path(__file__).resolve()),
                            "--output",
                            str(output),
                            "--worker-cases",
                            ",".join(names),
                        ],
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        cwd=ROOT,
                    )
                )
        except BaseException:
            self.close()
            raise

    def check(self):
        for process in self.processes:
            require(process.poll() in (None, 0), f"Eager worker failed: {process.returncode}")

    def finish(self, output, started):
        while any(p.poll() is None for p in self.processes):
            self.check()
            guard(output, started)
            sleep(0.25)
        self.check()

    def close(self):
        for process in self.processes:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
        for process in self.processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for handle in self.logs:
            handle.close()


def archived_check(output):
    require(
        sha(plan.RELEASE) == plan.RELEASE_SHA
        and sha(plan.PREVIOUS / "verification.json") == plan.PREVIOUS_SHA,
        "Old acceptance identity differs",
    )
    release = read_json(plan.RELEASE)
    previous = read_json(plan.PREVIOUS / "verification.json")
    authenticate(plan.PREVIOUS, previous["files_sha256"], extra=("verification.json",))
    snapshots, cohorts = [], []
    for path in sorted(plan.PREVIOUS.rglob("manifest.json")):
        manifest = read_json(path)
        if manifest.get("runtime", {}).get("cells_version") != "0.14.0":
            continue
        if manifest.get("kind") == "cells_complete_numerical_checkpoint":
            snapshots.append(str(path.parent))
        if manifest.get("kind") == "cells_independent_world_checkpoint":
            cohorts.append(str(path.parent))
    require(
        len(snapshots) == release["accepted_current_scalar_snapshots"] == 235
        and len(cohorts) == release["accepted_current_cohort_snapshots"] == 21,
        "Old checkpoint coverage differs",
    )
    for loader, path in ((load_snapshot, snapshots[0]), (load_batch_snapshot, cohorts[0])):
        try:
            loader(path)
        except ConfigError as error:
            require("source differs" in str(error), "Old checkpoint failed for unexpected reason")
        else:
            raise ValueError("Implicit old checkpoint migration was accepted")
    replay = plan.PREVIOUS / "jit/star_mono_short_pulse"
    request = {
        "source_hashes": release["source_hashes"],
        "runtime": release["runtime"],
        "snapshots": snapshots,
        "cohorts": cohorts,
        "replay_snapshot": str(next((replay / "snapshots").iterdir())),
        "replay_baseline": str(replay / "trajectory.npz"),
    }
    with tempfile.TemporaryDirectory(prefix="cells-core010-014-") as temporary:
        extract_sources(temporary)
        worker = subprocess.run(
            [sys.executable, "-c", ARCHIVED_WORKER],
            input=json.dumps(request),
            capture_output=True,
            text=True,
            timeout=600,
            cwd=temporary,
            env=os.environ | {"PYTHONPATH": str(Path(temporary) / "src")},
        )
    with (output / "archived-014.log").open("x") as log:
        log.write(worker.stdout + worker.stderr)
    require(worker.returncode == 0, f"Preserved checkpoint replay failed: {worker.stderr}")
    return json.loads(worker.stdout) | {
        "archive_sha256": ARCHIVE_SHA,
        "current_refuses_migration": True,
        "prior_payload_hashes": len(previous["files_sha256"]),
    }


def restart_cohorts(output):
    context(output)
    for group in plan.GROUPS:
        saved = load_batch_snapshot(output / "cohorts" / group / "snapshots/round-0000000004")
        write_windowed_batch(
            output / "cohort-resumed" / group,
            saved.spec,
            WindowPolicy(73, "full"),
            saved.checkpoints,
            provenance={"operation": "CORE-010 fresh-process cohort restart"},
        )
        context(output)
    return {"status": "pass", "cohort_restarts": len(plan.GROUPS)}


def child(output, name, args, *, request=None, timeout=600):
    worker = subprocess.run(
        args,
        input=None if request is None else json.dumps(request),
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=ROOT,
    )
    with (output / f"{name}.log").open("x") as handle:
        handle.write(worker.stdout + worker.stderr)
    require(worker.returncode == 0, f"{name} failed: {worker.stderr}")
    return json.loads(worker.stdout)


def verify(output, *, resources=None):
    resources = resources or get_resources()
    require(
        os.sched_getaffinity(0) == {0, 1, 2, 3}
        and all(os.environ.get(k) == "1" for k in plan.THREADS),
        "Require CPU 0-3 and one-thread numerical libraries",
    )
    output.mkdir(parents=True, exist_ok=False)
    started = monotonic()
    workers = None

    def timeout(signum, frame):
        raise TimeoutError("CORE-010 session wall budget reached")

    previous_handler = signal.signal(signal.SIGALRM, timeout)
    signal.alarm(resources.max_seconds)
    try:
        _, cases = load_cases()
        sources, runtime, identity = source_hashes(), runtime_identity(), implementation(resources)
        # This slice changes no production bytes, including version and all shared machinery.
        development = read_json(ROOT / "reports/core-010-implementation-closeout.json")
        require(
            development["source_hashes"] == sources and development["runtime"] == runtime,
            "Development production baseline changed",
        )
        with zipfile.ZipFile(
            output / "implementation_sources.zip", "x", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for name in identity:
                archive.write(ROOT / name, name)
        write_json(
            output / "registration.json",
            {
                **resources.registration_fields(),
                "source_hashes": sources,
                "runtime": runtime,
                "implementation_files_sha256": identity,
                "cpu_affinity": [0, 1, 2, 3],
                "thread_environment": {k: os.environ[k] for k in plan.THREADS},
                "eager_schedule": plan.eager_schedule(cases),
                "definitions": {
                    f"{mode}/{c.id}": plan.registered_spec(c, mode).to_dict()
                    for mode in ("jit", "eager", "refined")
                    for c in cases
                },
                "reference_solver_rerun": False,
                "scientific_inputs_changed": False,
                "development_closeout_sha256": sha(
                    ROOT / "reports/core-010-implementation-closeout.json"
                ),
            },
        )
        context(output)
        prior_stop = authenticate_prior_stop(resources)
        if prior_stop is not None:
            write_json(output / "prior-stopped-audit.json", prior_stop)
        print("Authenticate preserved reference and all accepted 0.14.0 checkpoints", flush=True)
        reference, archived = audit_reference(REFERENCE), archived_check(output)
        write_json(output / "reference-audit.json", reference)
        write_json(output / "archived-014-audit.json", archived)
        workers = EagerWorkers(output, cases)
        restarts = []
        for case in cases:
            for mode in ("jit", "refined"):
                print(f"Compiled spatial {mode}: {case.id}", flush=True)
                result = run(plan.registered_spec(case, mode))
                target = output / mode / case.id
                write_run(
                    target,
                    result,
                    checkpoint_times=(float(result.times[len(result.times) // 2]),),
                    provenance={"operation": "CORE-010", "reference_case": case.id},
                )
                if mode == "jit":
                    restarts.append(
                        {"path": str(target), "output": str(output / "resumed" / case.id)}
                    )
                workers.check()
                guard(output, started)
                context(output)
        print("Fresh-process complete scalar restarts", flush=True)
        restarted = child(
            output,
            "restart",
            [sys.executable, "-c", REPLAY_WORKER],
            request={"source_hashes": sources, "runtime": runtime, "runs": restarts},
        )
        case = next(c for c in cases if c.id == "membrane_block_release")
        target, at = plan.registered_spec(case), 0.0713
        parent_spec = replace(
            target,
            experiment=replace(
                target.experiment,
                end_time=at,
                observation_times=tuple(t for t in target.experiment.observation_times if t <= at),
                membranes=((ChannelChange(0, 1), ChannelChange(at, 1)),),
            ),
        )
        parent = run(parent_spec)
        write_snapshot(output / "branch-parent", parent.spec, parent.final)
        branched = run(target, branch_checkpoint(parent.spec, parent.final, target))
        write_run(
            output / "branch/membrane_block_release",
            branched,
            provenance={
                "operation": "future_branch",
                "parent_definition_sha256": parent.spec.fingerprint,
            },
        )
        for group, name in plan.WINDOW_CASES.items():
            print(f"Scalar windows and independently clocked cohort: {group}", flush=True)
            case = next(c for c in cases if c.id == name)
            write_windowed_run(
                output / "windows" / group, plan.registered_spec(case), WindowPolicy(128, "full")
            )
            write_windowed_batch(
                output / "cohorts" / group,
                plan.cohort(group, cases),
                WindowPolicy(plan.window_width(group), "full"),
                checkpoint_every_windows=4,
            )
            workers.check()
            guard(output, started)
        cohort_restarted = child(
            output,
            "cohort-restart",
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--output",
                str(output),
                "--restart-cohorts",
            ],
        )
        print("Exact earlier-family array replays", flush=True)
        old = old_regressions(output / "old-regression", monotonic())
        write_json(output / "old-model-regression.json", old)
        later = {}
        for previous in (
            ROOT / "runs/core-006-2026-09-09/acceptance-02",
            ROOT / "runs/core-007-2026-09-10/acceptance-03",
            ROOT / "runs/core-008-2026-09-10/acceptance-01",
            plan.PREVIOUS,
        ):
            receipt = read_json(previous / "verification.json")
            for name, record in receipt["runs"].items():
                if name.startswith("jit/"):
                    path = previous / name
                    require(
                        sha(path / "manifest.json") == record["manifest_sha256"],
                        "Old trajectory identity changed",
                    )
                    payloads(path, current=False)
                    spec, cp, wanted = baseline(path)
                    later[str(path.relative_to(ROOT))] = assert_full(run(spec, cp), wanted)
                    guard(output, started)
        later_receipt = {"status": "pass", "exact_arrays": later}
        write_json(output / "later-family-regression.json", later_receipt)
        workers.finish(output, started)
        workers.close()
        print("Independent physical, polynomial, stream and checkpoint audit", flush=True)
        panel = panel_results(output)
        context(output)
        guard(output, started)
        receipt = {
            "schema": "cells.core010_production_acceptance@1",
            "status": "pass",
            "source_hashes": sources,
            "runtime": runtime,
            "implementation_files_sha256": identity,
            "reference": reference,
            "archive": archived,
            **panel,
            "fresh_process_restart": restarted,
            "fresh_process_cohort_restart": cohort_restarted,
            "old_model_regression": old,
            "later_family_regression": later_receipt,
            "seconds": monotonic() - started,
            "files_sha256": {
                str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*")) if p.is_file()
            },
        }
        write_json(output / "verification.json", receipt)
        return {
            "status": "pass",
            "scalar_runs": len(panel["runs"]),
            "stream_runs": len(panel["streams"]),
            "seconds": receipt["seconds"],
            "verification_sha256": sha(output / "verification.json"),
            "stable_release_accepted": False,
            "next_gate": "Separate read-only audit and full unchanged-source regression matrix",
        }
    except BaseException as error:
        if workers is not None:
            workers.close()
        write_json(
            output / "failure.json",
            {
                "status": "failed",
                "type": type(error).__name__,
                "error": str(error),
                "seconds": monotonic() - started,
                "source_hashes": source_hashes(),
                "implementation_files_sha256": implementation(resources),
            },
        )
        raise
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker-cases")
    parser.add_argument("--restart-cohorts", action="store_true")
    parser.add_argument("--resource-plan", choices=tuple(PROFILES), default="v1")
    args = parser.parse_args()
    output = args.output.absolute()
    if args.worker_cases is not None:
        eager(output, args.worker_cases.split(","))
    else:
        result = (
            restart_cohorts(output)
            if args.restart_cohorts
            else verify(output, resources=get_resources(args.resource_plan))
        )
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
