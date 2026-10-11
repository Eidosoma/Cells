"""Bounded CORE-009 production acceptance through the ordinary shared CPU engine."""

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

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cells.batch_io import load_batch_snapshot  # noqa: E402
from cells.batch_window_io import write_windowed_batch  # noqa: E402
from cells.core.batch import BatchSpec, WorldSpec  # noqa: E402
from cells.core.runner import branch_checkpoint, run  # noqa: E402
from cells.core.specs import ConfigError, ContactChange  # noqa: E402
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
from cells.models import finite_extracellular as model  # noqa: E402
from cells.window_io import write_windowed_run  # noqa: E402
from scripts.audit_finite_extracellular_build import audit, audit_run  # noqa: E402
from scripts.audit_preserved_finite_extracellular_reference import (  # noqa: E402
    ARCHIVE_SHA,
    extract_sources,
)
from scripts.audit_preserved_finite_extracellular_reference import (  # noqa: E402
    audit as audit_reference,
)
from scripts.verify_batch_windows_build import audit_cohort, suffix  # noqa: E402
from scripts.verify_multispecies_build import (  # noqa: E402
    ARCHIVED_WORKER,
    REPLAY_WORKER,
    old_regressions,
)
from scripts.verify_windows_build import (  # noqa: E402
    assert_full,
    audit_windows,
    baseline,
    payloads,
)
from tests.finite_extracellular_fixtures import REFERENCE, load_cases, spec_for  # noqa: E402

RELEASE = ROOT / "runs/core-008-2026-09-10/release-audit.json"
RELEASE_SHA = "e03a211726888d3962825db544bba6742aa09603031d68ebbbc4745542393f08"
PREVIOUS = ROOT / "runs/core-008-2026-09-10/acceptance-01"
PREVIOUS_SHA = "6d60fd732bfd0f8a068fb0a0b342f9487f9b0b74326f73d8af84aefc7f6a9b43"
MAX_SECONDS, MAX_BYTES = 3600, 2 * 2**30
THREADS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")


def guard(output, started):
    if monotonic() - started > MAX_SECONDS:
        raise ValueError("CORE-009 session wall budget exceeded; no automatic retry")
    if sum(p.stat().st_size for p in output.rglob("*") if p.is_file()) > MAX_BYTES:
        raise ValueError("CORE-009 artifact budget exceeded; no automatic retry")


def eager_worker(output, names):
    registration = json.loads((output / "registration.json").read_text())
    assert (
        source_hashes() == registration["source_hashes"]
        and runtime_identity() == registration["runtime"]
    )
    _, cases = load_cases()
    available = {c.id: c for c in cases}
    assert set(names) <= available.keys() and len(names) == len(set(names))
    for name in names:
        print(f"Eager graph on CPU {sorted(os.sched_getaffinity(0))}: {name}", flush=True)
        with np.load(REFERENCE / name / "refined.npz", allow_pickle=False) as saved:
            spec = spec_for(available[name], jit=False, samples=saved["sample_times_s"])
        result = run(spec)
        write_run(
            output / "eager" / name,
            result,
            checkpoint_times=(float(result.times[len(result.times) // 2]),),
            provenance={"operation": "CORE-009", "reference_case": name},
        )
        assert source_hashes() == registration["source_hashes"]


class EagerWorkers:
    def __init__(self, output, cases):
        self.processes, self.logs = [], []
        groups, durations = [[] for _ in range(4)], [0.0] * 4
        for case in sorted(cases, key=lambda c: (-c.horizon_s, c.id)):
            cpu = min(range(4), key=lambda i: durations[i])
            groups[cpu].append(case.id)
            durations[cpu] += case.horizon_s
        self.schedule = {str(cpu): names for cpu, names in enumerate(groups) if names}
        try:
            for cpu, names in self.schedule.items():
                handle = (output / f"eager-cpu{cpu}.log").open("x")
                self.logs.append(handle)
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
                        stdout=handle,
                        stderr=subprocess.STDOUT,
                        cwd=ROOT,
                    )
                )
        except BaseException:
            self.close()
            raise

    def check(self):
        for process in self.processes:
            if process.poll() not in (None, 0):
                raise ValueError(f"Eager worker {process.pid} failed: {process.returncode}")

    def finish(self, output, started):
        while any(p.poll() is None for p in self.processes):
            self.check()
            guard(output, started)
            sleep(0.25)
        self.check()

    def close(self):
        for p in self.processes:
            if p.poll() is None:
                p.send_signal(signal.SIGINT)
        for p in self.processes:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
        for handle in self.logs:
            handle.close()


def archive_check(output):
    assert sha(RELEASE) == RELEASE_SHA and sha(PREVIOUS / "verification.json") == PREVIOUS_SHA
    release = json.loads(RELEASE.read_text())
    snapshots, cohorts = [], []
    for root in release["accepted_roots"]:
        for path in sorted((RELEASE.parent / root).rglob("manifest.json")):
            m = json.loads(path.read_text())
            if m.get("runtime", {}).get("cells_version") != "0.13.0":
                continue
            if m.get("kind") == "cells_complete_numerical_checkpoint":
                snapshots.append(str(path.parent))
            if m.get("kind") == "cells_independent_world_checkpoint":
                cohorts.append(str(path.parent))
    assert len(snapshots) == release["accepted_current_scalar_snapshots"] == 162
    assert len(cohorts) == release["accepted_current_cohort_snapshots"] == 16
    for loader, path in ((load_snapshot, snapshots[0]), (load_batch_snapshot, cohorts[0])):
        try:
            loader(path)
        except ConfigError as error:
            assert "source differs" in str(error)
        else:
            raise AssertionError("Old checkpoint was silently migrated")
    replay = PREVIOUS / "jit/star_mono_short_pulse"
    request = {
        "source_hashes": release["source_hashes"],
        "runtime": release["runtime"],
        "snapshots": snapshots,
        "cohorts": cohorts,
        "replay_snapshot": str(next((replay / "snapshots").iterdir())),
        "replay_baseline": str(replay / "trajectory.npz"),
    }
    with tempfile.TemporaryDirectory(prefix="cells-core009-old-") as directory:
        extract_sources(directory)
        worker = subprocess.run(
            [sys.executable, "-c", ARCHIVED_WORKER],
            input=json.dumps(request),
            capture_output=True,
            text=True,
            timeout=420,
            cwd=directory,
            env=os.environ | {"PYTHONPATH": str(Path(directory) / "src")},
        )
    with (output / "archived-013.log").open("x") as handle:
        handle.write(worker.stdout + worker.stderr)
    assert worker.returncode == 0, worker.stderr
    result = json.loads(worker.stdout)
    result["exact_physical_graph_replay"] = result.pop("exact_source_pair_replay")
    return result | {"archive_sha256": ARCHIVE_SHA, "current_refuses_migration": True}


def verify(output):
    output.mkdir(parents=True, exist_ok=False)
    started = monotonic()
    assert os.sched_getaffinity(0) == {0, 1, 2, 3}
    assert all(os.environ.get(k) == "1" for k in THREADS)
    sources, runtime = source_hashes(), runtime_identity()
    files = sorted(
        {p for folder in ("src/cells", "tests", "scripts") for p in (ROOT / folder).rglob("*.py")}
        | {
            ROOT / n
            for n in (
                "pyproject.toml",
                "requirements-lock.txt",
                "requirements-reference.txt",
                "docs/FINITE_EXTRACELLULAR.md",
                "configs/finite_extracellular_cell.json",
            )
        }
    )
    identity = {str(p.relative_to(ROOT)): sha(p) for p in files}
    with zipfile.ZipFile(
        output / "implementation_sources.zip", "x", compression=zipfile.ZIP_DEFLATED
    ) as capsule:
        for path in files:
            capsule.write(path, path.relative_to(ROOT))
    write_json(
        output / "registration.json",
        {
            "source_hashes": sources,
            "runtime": runtime,
            "files_sha256": identity,
            "max_seconds": MAX_SECONDS,
            "max_artifact_bytes": MAX_BYTES,
            "cpu_affinity": [0, 1, 2, 3],
            "eager_lanes": 4,
            "thread_environment": {k: os.environ[k] for k in THREADS},
            "reference_solver_rerun": False,
            "scientific_inputs_changed": False,
        },
    )
    workers = None

    def timeout(signum, frame):
        raise TimeoutError("CORE-009 session wall budget reached")

    previous_handler = signal.signal(signal.SIGALRM, timeout)
    signal.alarm(MAX_SECONDS)
    try:
        print("Authenticating preserved reference and complete 0.13.0 snapshots", flush=True)
        reference_audit = audit_reference(REFERENCE)
        write_json(output / "reference-audit.json", reference_audit)
        archived = archive_check(output)
        write_json(output / "archived-013-audit.json", archived)
        plan, cases = load_cases()
        workers = EagerWorkers(output, cases)
        write_json(output / "eager-schedule.json", workers.schedule)
        records, restarts, expected, definitions = {}, [], {}, {}
        for case in cases:
            print(f"Compiled finite-outside acceptance: {case.id}", flush=True)
            with np.load(REFERENCE / case.id / "refined.npz", allow_pickle=False) as saved:
                spec = spec_for(case, samples=saved["sample_times_s"])
            result = run(spec)
            path = output / "jit" / case.id
            write_run(
                path,
                result,
                checkpoint_times=(float(result.times[len(result.times) // 2]),),
                provenance={"operation": "CORE-009", "reference_case": case.id},
            )
            expected[case.id], records[f"jit/{case.id}"] = audit_run(
                path, case.definition(), plan, REFERENCE / case.id
            )
            definitions[case.id] = spec
            restarts.append({"path": str(path), "output": str(output / "resumed" / case.id)})
            workers.check()
            guard(output, started)
        print("Fresh-process complete-state restart for all fourteen cases", flush=True)
        worker = subprocess.run(
            [sys.executable, "-c", REPLAY_WORKER],
            input=json.dumps({"source_hashes": sources, "runtime": runtime, "runs": restarts}),
            capture_output=True,
            text=True,
            timeout=300,
            cwd=ROOT,
        )
        with (output / "restart.log").open("x") as handle:
            handle.write(worker.stdout + worker.stderr)
        assert worker.returncode == 0, worker.stderr
        for case in cases:
            _, records[f"resumed/{case.id}"] = audit_run(
                output / "resumed" / case.id, case.definition(), plan, REFERENCE / case.id
            )
        print("Future-only branch retaining every membrane and junction history", flush=True)
        target = definitions["star_mono"]
        parent_spec = replace(
            target,
            experiment=replace(
                target.experiment,
                end_time=0.02,
                observation_times=tuple(
                    t for t in target.experiment.observation_times if t <= 0.02
                ),
                junctions=tuple(
                    (ContactChange(0, 1), ContactChange(0.02, 0)) for _ in target.model.junctions
                ),
            ),
        )
        parent = run(parent_spec)
        write_snapshot(output / "branch-parent", parent.spec, parent.final)
        branched = run(target, branch_checkpoint(parent.spec, parent.final, target))
        write_run(
            output / "branch/star_mono_continue",
            branched,
            provenance={
                "operation": "future_branch",
                "parent_definition_sha256": parent.spec.fingerprint,
            },
        )
        case = next(c for c in cases if c.id == "star_mono")
        _, records["branch/star_mono_continue"] = audit_run(
            output / "branch/star_mono_continue",
            case.definition(),
            plan,
            REFERENCE / case.id,
            branch=True,
        )
        windows, cohorts = {}, {}
        cohort_cases = {
            group: [c.id for c in cases if ("divalent" in c.id) == (group == "divalent")]
            for group in ("mono", "divalent")
        }
        for group, names in cohort_cases.items():
            print(
                f"Full windows and topology-heterogeneous independent-clock cohorts: {group}",
                flush=True,
            )
            name = names[-1]
            path = output / "windows" / group
            write_windowed_run(path, definitions[name], WindowPolicy(37, "full"))
            windows[group] = audit_windows(path, expected[name])
            batch = BatchSpec(
                tuple(WorldSpec(i + 1, definitions[name]) for i, name in enumerate(names)),
                12,
                50000,
                2**29,
            )
            wanted = {i + 1: expected[name] for i, name in enumerate(names)}
            path = output / "cohorts" / group
            write_windowed_batch(path, batch, WindowPolicy(37, "full"), checkpoint_every_windows=1)
            cohorts[group] = audit_cohort(path, wanted)
            saved = load_batch_snapshot(path / "snapshots/round-0000000001")
            resumed = output / "cohort-resumed" / group
            write_windowed_batch(resumed, saved.spec, WindowPolicy(23, "full"), saved.checkpoints)
            cohorts[f"resumed/{group}"] = audit_cohort(
                resumed, {i: suffix(v, saved.checkpoints[i], model) for i, v in wanted.items()}
            )
            guard(output, started)
        workers.finish(output, started)
        workers.close()
        for case in cases:
            _, records[f"eager/{case.id}"] = audit_run(
                output / "eager" / case.id, case.definition(), plan, REFERENCE / case.id
            )
        print("Exact regression of the nine earlier production families", flush=True)
        old = old_regressions(output / "old-regression", monotonic())
        write_json(output / "old-model-regression.json", old)
        later = {}
        for previous in (
            ROOT / "runs/core-006-2026-09-09/acceptance-02",
            ROOT / "runs/core-007-2026-09-10/acceptance-03",
            PREVIOUS,
        ):
            receipt = json.loads((previous / "verification.json").read_text())
            for name, record in receipt["runs"].items():
                if name.startswith("jit/"):
                    path = previous / name
                    assert sha(path / "manifest.json") == record["manifest_sha256"]
                    payloads(path, current=False)
                    spec, cp, wanted = baseline(path)
                    later[str(path.relative_to(ROOT))] = assert_full(run(spec, cp), wanted)
                    guard(output, started)
        write_json(
            output / "ionic-channel-regression.json", {"status": "pass", "exact_arrays": later}
        )
        assert source_hashes() == sources and runtime_identity() == runtime
        assert all(sha(ROOT / n) == v for n, v in identity.items())
        guard(output, started)
        receipt = {
            "status": "pass",
            "source_hashes": sources,
            "runtime": runtime,
            "reference": reference_audit,
            "archive": archived,
            "runs": records,
            "windows": windows,
            "cohorts": cohorts,
            "cohort_cases": cohort_cases,
            "fresh_process_restart": json.loads(worker.stdout),
            "old_model_regression": old,
            "ionic_channel_exact_arrays": later,
            "jit_eager_comparison_factor": 0.001,
            "eager_worker_schedule": workers.schedule,
            "seconds": monotonic() - started,
            "implementation_files_sha256": identity,
            "files_sha256": {
                str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*")) if p.is_file()
            },
        }
        write_json(output / "verification.json", receipt)
        return audit(output)
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
    args = parser.parse_args()
    if args.worker_cases is not None:
        eager_worker(args.output.resolve(), args.worker_cases.split(","))
    else:
        print(json.dumps(verify(args.output.resolve()), indent=2, sort_keys=True, allow_nan=False))
