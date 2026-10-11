"""Bounded CORE-007 CPU acceptance; frozen references, complete shared-engine paths.

No new implicit solves, fits, GPU jobs or checkpoint migration. Existing evidence
is read-only; every attempted session has a new, non-overwriting destination.
"""

import argparse
import json
import os
import shutil
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
from cells.core.specs import ChannelChange, ConfigError, load_spec  # noqa: E402
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
from cells.models import voltage_gated_membrane as model  # noqa: E402
from cells.window_io import write_windowed_run  # noqa: E402
from scripts.audit_preserved_voltage_gated_reference import (  # noqa: E402
    ARCHIVE_SHA,
    extract_sources,
)
from scripts.audit_preserved_voltage_gated_reference import audit as audit_reference  # noqa: E402
from scripts.audit_voltage_gated_build import REFERENCE, audit, audit_run, canonical  # noqa: E402
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
from tests import voltage_gated_numerical_checks as checks  # noqa: E402
from tests.reference_voltage_gated_dynamics import load_panel  # noqa: E402
from tests.voltage_gated_fixtures import spec_for  # noqa: E402

RELEASE = ROOT / "runs/core-006-2026-09-09/release-audit.json"
RELEASE_SHA = "ec084d0f626fbb3793714bbb7ea346688d1f1244078869507396a57aec1f5005"
PREVIOUS = ROOT / "runs/core-006-2026-09-09/acceptance-02"
PREVIOUS_SHA = "2d9352e55e2744f5eb3a41eb51a010d3cac83d3459b928fb495b1a69f39d9ee7"
MAX_SECONDS = 2400
MAX_BYTES = 1024 * 2**20


def eager_worker(output, names):
    """One independent CPU lane, no changes to the engine's eager execution."""
    started = monotonic()
    registration = json.loads((output / "registration.json").read_text())
    assert source_hashes() == registration["source_hashes"]
    assert runtime_identity() == registration["runtime"]
    _, cases = load_panel()
    available = {c.id: c for c in cases}
    assert len(names) == len(set(names)) and set(names) <= available.keys()
    for name in names:
        assert monotonic() - started < MAX_SECONDS
        case = available[name]
        print(f"Eager CPU {sorted(os.sched_getaffinity(0))}: {name}", flush=True)
        with np.load(REFERENCE / name / "refined.npz", allow_pickle=False) as data:
            spec = spec_for(case, jit=False, samples=data["sample_times_s"])
        result = run(spec)
        write_run(
            output / "eager" / name,
            result,
            checkpoint_times=(float(result.times[len(result.times) // 2]),),
            provenance={"operation": "CORE-007", "reference_case": name},
        )
        assert source_hashes() == registration["source_hashes"]


class EagerWorkers:
    """Four explicitly owned CPU processes; always reap them on success/failure."""

    def __init__(self, output, cases):
        self.processes, self.logs = [], []
        groups = [[] for _ in range(4)]
        durations = [0.0] * 4
        pending = [c for c in cases if not (output / "eager" / c.id / "manifest.json").exists()]
        for case in sorted(pending, key=lambda c: (-c.horizon_s, c.id)):
            cpu = min(range(4), key=lambda i: durations[i])
            groups[cpu].append(case.id)
            durations[cpu] += case.horizon_s
        self.schedule = {str(cpu): group for cpu, group in enumerate(groups) if group}
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
                raise ValueError(
                    f"Eager verification worker {process.pid} failed: {process.returncode}"
                )

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


def reuse_completed(source, output, plan, cases):
    """Re-audit and copy only completed runs, binding their original registration."""
    if source is None:
        return None
    source = source.resolve()
    registration = json.loads((source / "registration.json").read_text())
    assert registration["source_hashes"] == source_hashes()
    assert registration["runtime"] == runtime_identity()
    for name, value in registration["files_sha256"].items():
        if name != "scripts/verify_voltage_gated_build.py":
            assert sha(ROOT / name) == value
    reused = {}
    for case in cases:
        for mode in ("jit", "eager"):
            name = f"{mode}/{case.id}"
            path = source / name
            if not (path / "manifest.json").exists():
                continue
            _, record = audit_run(
                path, json.loads(json.dumps(case.definition())), plan, REFERENCE / case.id
            )
            assert load_spec(path / "resolved_config.json").execution.jit == (mode == "jit")
            shutil.copytree(path, output / name)
            reused[name] = record["manifest_sha256"]
    return {
        "source": str(source),
        "registration_sha256": sha(source / "registration.json"),
        "failure_sha256": sha(source / "failure.json"),
        "copied_manifests_sha256": reused,
        "unchanged_production": True,
        "changed_harness_file": "scripts/verify_voltage_gated_build.py",
    }


def guard(output, started):
    if monotonic() - started > MAX_SECONDS:
        raise ValueError("CORE-007 session wall budget exceeded; no automatic retry")
    if sum(p.stat().st_size for p in output.rglob("*") if p.is_file()) > MAX_BYTES:
        raise ValueError("CORE-007 artifact budget exceeded; no automatic retry")


def archive_check(output):
    assert sha(RELEASE) == RELEASE_SHA and sha(PREVIOUS / "verification.json") == PREVIOUS_SHA
    release = json.loads(RELEASE.read_text())
    snapshots, cohorts = [], []
    for root in release["accepted_roots"]:
        for path in sorted((RELEASE.parent / root).rglob("manifest.json")):
            m = json.loads(path.read_text())
            if m.get("runtime", {}).get("cells_version") != "0.11.0":
                continue
            if m.get("kind") == "cells_complete_numerical_checkpoint":
                snapshots.append(str(path.parent))
            if m.get("kind") == "cells_independent_world_checkpoint":
                cohorts.append(str(path.parent))
    assert len(snapshots) == release["accepted_current_scalar_snapshots"] == 226
    assert len(cohorts) == release["accepted_current_cohort_snapshots"] == 22
    for loader, path in ((load_snapshot, snapshots[0]), (load_batch_snapshot, cohorts[0])):
        try:
            loader(path)
        except ConfigError as error:
            assert "source differs" in str(error)
        else:
            raise AssertionError("Old checkpoint was silently migrated")
    replay = PREVIOUS / "jit/divalent_short_pulse"
    request = {
        "source_hashes": release["source_hashes"],
        "runtime": release["runtime"],
        "snapshots": snapshots,
        "cohorts": cohorts,
        "replay_snapshot": str(next((replay / "snapshots").iterdir())),
        "replay_baseline": str(replay / "trajectory.npz"),
    }
    with tempfile.TemporaryDirectory(prefix="cells-core007-old-") as directory:
        extract_sources(directory)
        worker = subprocess.run(
            [sys.executable, "-c", ARCHIVED_WORKER],
            input=json.dumps(request),
            capture_output=True,
            text=True,
            timeout=360,
            cwd=directory,
            env=os.environ | {"PYTHONPATH": str(Path(directory) / "src")},
        )
    with (output / "archived-011.log").open("x") as handle:
        handle.write(worker.stdout + worker.stderr)
    assert worker.returncode == 0, worker.stderr
    result = json.loads(worker.stdout)
    # The reusable worker's historical field name says source_pair; the actual
    # replay target above is explicitly the multispecies divalent pulse.
    result["exact_multispecies_replay"] = result.pop("exact_source_pair_replay")
    return result | {
        "archive_sha256": ARCHIVE_SHA,
        "current_refuses_migration": True,
        "replayed_run": str(replay.relative_to(ROOT)),
    }


def verify(output, reuse=None):
    output.mkdir(parents=True, exist_ok=False)
    started = monotonic()
    assert os.sched_getaffinity(0) == {4}, "Acceptance requires one pinned CPU: taskset -c 4"
    sources, runtime = source_hashes(), runtime_identity()
    # Capture the full local Python dependency closure of verification/test code,
    # plus production, packaging and the runnable example definitions.
    files = sorted(
        {p for folder in ("src/cells", "scripts", "tests") for p in (ROOT / folder).rglob("*.py")}
        | {
            ROOT / n
            for n in (
                "pyproject.toml",
                "requirements-lock.txt",
                "requirements-reference.txt",
                "configs/voltage_gated_baseline.json",
                "configs/voltage_gated_pulse.json",
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
            "cpu_affinity": [4],
            "eager_worker_cpu_affinities": [[0], [1], [2], [3]],
            "scheduling_revision": 3,
            "reason": (
                "333.369 s per 1000 eager steps exceeds the original serial forecast; "
                "complete criteria unchanged; full per-window checkpoint evidence projects "
                "to 521 MiB, requiring a 1 GiB artifact allocation"
            ),
            "reference_solver_rerun": False,
        },
    )
    workers = None
    try:
        print("Auditing preserved NUM-007 and 0.11.0 checkpoints", flush=True)
        reference_audit = audit_reference(REFERENCE)
        write_json(output / "reference-audit.json", reference_audit)
        archived = archive_check(output)
        write_json(output / "archived-011-audit.json", archived)
        plan, cases = load_panel()
        reused = reuse_completed(reuse, output, plan, cases)
        write_json(output / "reused-runs.json", reused)
        workers = EagerWorkers(output, cases)
        write_json(output / "eager-schedule.json", workers.schedule)
        records, restarts, expected, definitions = {}, [], {}, {}
        for case in cases:
            print(f"Compiled channel reference qualification: {case.id}", flush=True)
            with np.load(REFERENCE / case.id / "refined.npz", allow_pickle=False) as values:
                samples = values["sample_times_s"]
            path = output / "jit" / case.id
            if not (path / "manifest.json").exists():
                spec = spec_for(case, jit=True, samples=samples)
                result = run(spec)
                middle = float(result.times[len(result.times) // 2])
                write_run(
                    path,
                    result,
                    checkpoint_times=(middle,),
                    provenance={"operation": "CORE-007", "reference_case": case.id},
                )
            data, record = audit_run(
                path, json.loads(json.dumps(case.definition())), plan, REFERENCE / case.id
            )
            records[f"jit/{case.id}"] = record
            expected[case.id], definitions[case.id] = data, load_spec(path / "resolved_config.json")
            restarts.append({"path": str(path), "output": str(output / "resumed" / case.id)})
            workers.check()
            guard(output, started)
        print("Fresh-process complete-state restart for all fourteen cases", flush=True)
        worker = subprocess.run(
            [sys.executable, "-c", REPLAY_WORKER],
            input=json.dumps({"source_hashes": sources, "runtime": runtime, "runs": restarts}),
            capture_output=True,
            text=True,
            timeout=240,
            cwd=ROOT,
        )
        with (output / "restart.log").open("x") as handle:
            handle.write(worker.stdout + worker.stderr)
        assert worker.returncode == 0, worker.stderr
        for case in cases:
            _, records[f"resumed/{case.id}"] = audit_run(
                output / "resumed" / case.id,
                json.loads(json.dumps(case.definition())),
                plan,
                REFERENCE / case.id,
            )
        print("Counterfactual pulse omission preserving the original gates and ledgers", flush=True)
        parent = run(definitions["mono_short_pulse"])
        cp = parent.checkpoint_at(0.0203)
        write_snapshot(output / "branch-parent", parent.spec, cp)
        changed = replace(
            parent.spec,
            experiment=replace(
                parent.spec.experiment,
                channel=(
                    ChannelChange(0, 0),
                    ChannelChange(0.0203, 0),
                    ChannelChange(0.0204, 0),
                    ChannelChange(0.2, 1),
                ),
            ),
        )
        branched = run(changed, branch_checkpoint(parent.spec, cp, changed))
        write_run(
            output / "branch/mono_pulse_omitted",
            branched,
            provenance={
                "operation": "future_branch",
                "parent_definition_sha256": parent.spec.fingerprint,
            },
        )
        off = next(c for c in cases if c.id == "mono_channel_off")
        _, records["branch/mono_pulse_omitted"] = audit_run(
            output / "branch/mono_pulse_omitted",
            json.loads(json.dumps(off.definition())),
            plan,
            REFERENCE / off.id,
            branch=True,
        )
        cohorts, windows = {}, {}
        for prefix in ("mono", "divalent"):
            print(
                f"Scalar windows, independent-clock cohorts and resumed cohorts: {prefix}",
                flush=True,
            )
            name = prefix + "_short_pulse"
            path = output / "windows" / prefix
            write_windowed_run(
                path, definitions[name], WindowPolicy(129, "full"), checkpoint_times=(0.0203,)
            )
            windows[prefix] = audit_windows(path, expected[name])
            selected = [c for c in cases if c.id.startswith(prefix)]
            batch = BatchSpec(
                tuple(WorldSpec(i + 1, definitions[c.id]) for i, c in enumerate(selected)),
                9,
                50000,
                2**29,
            )
            wanted = {i + 1: expected[c.id] for i, c in enumerate(selected)}
            path = output / "cohorts" / prefix
            write_windowed_batch(path, batch, WindowPolicy(129, "full"), checkpoint_every_windows=1)
            cohorts[prefix] = audit_cohort(path, wanted)
            saved = load_batch_snapshot(path / "snapshots/round-0000000001")
            resumed = output / "cohort-resumed" / prefix
            write_windowed_batch(resumed, saved.spec, WindowPolicy(73, "full"), saved.checkpoints)
            cohorts[f"resumed/{prefix}"] = audit_cohort(
                resumed, {i: suffix(v, saved.checkpoints[i], model) for i, v in wanted.items()}
            )
            guard(output, started)
        print("Exact regression of the eight earlier model families", flush=True)
        old = old_regressions(output, monotonic())
        write_json(output / "old-model-regression.json", old)
        previous = json.loads((PREVIOUS / "verification.json").read_text())
        multispecies = {}
        for name, record in previous["runs"].items():
            if not name.startswith("jit/"):
                continue
            path = PREVIOUS / name
            assert sha(path / "manifest.json") == record["manifest_sha256"]
            payloads(path, current=False)
            spec, cp, wanted = baseline(path)
            multispecies[name] = assert_full(run(spec, cp), wanted)
        write_json(
            output / "multispecies-regression.json",
            {"status": "pass", "exact_arrays": multispecies},
        )
        print("Completing and independently auditing the eager verification lanes", flush=True)
        workers.finish(output, started)
        workers.close()
        for case in cases:
            data, record = audit_run(
                output / "eager" / case.id,
                json.loads(json.dumps(case.definition())),
                plan,
                REFERENCE / case.id,
            )
            records[f"eager/{case.id}"] = record
            for prefix in ("", "observed_"):
                assert checks.errors(
                    case.definition(),
                    canonical(expected[case.id], case.definition(), prefix),
                    canonical(data, case.definition(), prefix),
                    plan["trajectory_limits"],
                    factor=0.001,
                )["pass"]
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
            "old_model_regression": old,
            "multispecies_exact_arrays": multispecies,
            "fresh_process_restart": json.loads(worker.stdout),
            "jit_eager_comparison_factor": 0.001,
            "eager_worker_schedule": workers.schedule,
            "reused_runs": reused,
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reuse", type=Path)
    parser.add_argument("--worker-cases")
    args = parser.parse_args()
    if args.worker_cases is not None:
        eager_worker(args.output.resolve(), args.worker_cases.split(","))
    else:
        print(
            json.dumps(
                verify(args.output.resolve(), args.reuse), indent=2, sort_keys=True, allow_nan=False
            )
        )
