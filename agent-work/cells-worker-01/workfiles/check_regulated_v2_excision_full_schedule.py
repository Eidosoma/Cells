"""Freeze and detach the retained 150-us host schedule/archive qualification.

The 27-check focused component stays immutable. This new job restores the
original full-schedule family and adds production cut/archive panels at the
independent accepted 50-us and 150-us checkpoints. It starts no trajectory
compiler and does not rerun the independent trajectory producer.
"""

import argparse
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = "agent-work/cells-worker-01/workfiles/"
SELF = WORK + "check_regulated_v2_excision_full_schedule.py"
TEST = "tests/unit/test_surface_calcium_energy_regulated_v2_excision_full_schedule.py"
ORIGINAL_TEST = "tests/unit/test_surface_calcium_energy_regulated_v2_excision.py"
ORIGINAL = Path("/mnt/workspaces/Cells/regulated-v2-excision-host-20261029-03")
BASE = Path("/mnt/workspaces/Cells/regulated-v2-excision-host-20261029-05")
BASE_SHA = "959e1595ad9ae7dca30939d99d0a7828c129abd1f65cebb5762b082492b168be"
REFERENCE = Path("/mnt/workspaces/Cells/calcium-energy-regulated-v2-excision-reference-20261029-01")
REFERENCE_SHA = "b81a4882743abf33e9ba1d91bdb3cf7a1eb9030169ba9de8f9b62e3457ddfb28"
WALL_SECONDS = 7200


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def hashes(root):
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob("*")) if p.is_file()}


def functions(path):
    return {
        n.name: ast.dump(n, include_attributes=False)
        for n in ast.parse(path.read_text()).body
        if isinstance(n, ast.FunctionDef)
    }


def environment(output, *, source=None):
    env = os.environ.copy()
    env.update(
        dict.fromkeys(
            ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"),
            "1",
        )
    )
    root = source or output / "snapshot"
    env.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        PYTHONPATH=str(root / "src") + os.pathsep + str(root),
        JAX_PLATFORMS="cpu",
        JAX_ENABLE_X64="true",
        JAX_DISABLE_JIT="true",
        CUDA_VISIBLE_DEVICES="",
        JAX_ENABLE_COMPILATION_CACHE="false",
        XLA_FLAGS="--xla_cpu_multi_thread_eigen=false",
        MALLOC_ARENA_MAX="2",
        CELLS_COMPONENT_EVIDENCE=str(output / "evidence"),
        XDG_CACHE_HOME=str(output / "cache"),
        JAX_COMPILATION_CACHE_DIR=str(output / "cache/jax"),
        TMPDIR=str(output / "tmp"),
    )
    return env


def bounded(command, directory, cwd, env, *, timeout):
    directory.mkdir()
    sys.path[:0] = [str(cwd / "src"), str(cwd)]
    from validation.assembly.component_process import run_bounded

    run_bounded(
        command,
        directory=directory,
        cwd=cwd,
        env=env,
        timeout=timeout,
        max_rss_bytes=2**30,
        min_available_bytes=8 * 2**30,
    )


def prepare(output):
    output.mkdir(exist_ok=False)
    for name in ("tmp", "cache", "evidence", "initial_owned"):
        (output / name).mkdir()
    for relative in (SELF, TEST):
        target = output / "initial_owned" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    ruff = str(Path(sys.executable).parent / "ruff")
    for name, args in (
        ("imports", ["check", "--no-cache", "--select", "I", "--fix", SELF, TEST]),
        ("format", ["format", "--no-cache", SELF, TEST]),
        ("lint", ["check", "--no-cache", SELF, TEST]),
    ):
        bounded(
            [ruff, *args],
            output / ("prepare-" + name),
            ROOT,
            environment(output, source=ROOT),
            timeout=60,
        )
    assert sha(BASE / "result.json") == BASE_SHA
    component = read(BASE / "result.json")
    assert component["status"] == "passed" and component["tests"] == dict(
        tests=27, errors=0, failures=0, skipped=0
    )
    for relative, expected in component["source_sha256"].items():
        assert sha(BASE / "snapshot" / relative) == expected
    previous = read(BASE / "frozen-sources.json")["after_sha256"]
    assert hashes(BASE / "snapshot") == previous
    snapshot = output / "snapshot"
    for relative in previous:
        target = snapshot / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((BASE / "snapshot" / relative).read_bytes())
    for relative in (SELF, TEST):
        target = snapshot / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    # The peer's files are frozen and verified; this only enables field/state
    # mapping and independent instantaneous comparisons, not integration jobs.
    assert sha(REFERENCE / "HANDOFF.json") == REFERENCE_SHA
    reference = read(REFERENCE / "HANDOFF.json")
    for relative, expected in reference["source_sha256"].items():
        path = ROOT / relative
        assert sha(path) == expected, relative
        target = snapshot / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    for relative, expected in reference["unchanged_component_source_sha256"].items():
        assert sha(snapshot / relative) == expected, relative
    after = hashes(snapshot)
    assert {p: h for p, h in after.items() if p.startswith("src/")} == {
        p: h for p, h in previous.items() if p.startswith("src/")
    }
    old, new = functions(ORIGINAL / "snapshot" / ORIGINAL_TEST), functions(snapshot / TEST)
    assert all(new.get(name) == body for name, body in old.items())
    write(
        output / "original-schedule-proof.json",
        dict(
            status="passed",
            original_source=str(ORIGINAL / "snapshot" / ORIGINAL_TEST),
            original_sha256=sha(ORIGINAL / "snapshot" / ORIGINAL_TEST),
            exact_original_functions_sha256={
                name: hashlib.sha256(body.encode()).hexdigest() for name, body in old.items()
            },
            horizon_s=150e-6,
            original_tests_retained=25,
            additional_late_checkpoint_panels=2,
            original_fixture_and_checks_unchanged=True,
            physics_and_tolerances_unchanged=True,
        ),
    )
    write(
        output / "frozen-sources.json",
        dict(
            status="frozen",
            after_sha256=after,
            inherited_focused_component=str(BASE / "result.json"),
            inherited_component_sha256=BASE_SHA,
            source_package_byte_identical_to_focused_component=True,
            shared_files_written=False,
            dispatch_patch_reapplied=False,
            reference_handoff=str(REFERENCE / "HANDOFF.json"),
            reference_handoff_sha256=REFERENCE_SHA,
            reference_sources_sha256=reference["source_sha256"],
        ),
    )
    env = environment(output)
    command = [
        sys.executable,
        "-B",
        "-m",
        "pytest",
        "-vv",
        "-s",
        "-x",
        "-p",
        "no:cacheprovider",
        "--basetemp=" + str(output / "tmp/pytest"),
        "--junitxml=" + str(output / "full-tests.xml"),
        str(snapshot / TEST),
    ]
    write(
        output / "inputs.json",
        dict(
            status="prepared",
            command=command,
            affinity=[7],
            max_wall_seconds=WALL_SECONDS,
            max_host_rss_bytes=2**30,
            min_available_memory_bytes=8 * 2**30,
            compiled_execution=False,
            gpu=False,
            environment={
                k: env[k]
                for k in (
                    "PYTHONPATH",
                    "JAX_PLATFORMS",
                    "JAX_ENABLE_X64",
                    "JAX_DISABLE_JIT",
                    "XLA_FLAGS",
                    "CUDA_VISIBLE_DEVICES",
                    "JAX_ENABLE_COMPILATION_CACHE",
                    "OPENBLAS_NUM_THREADS",
                    "OMP_NUM_THREADS",
                    "MKL_NUM_THREADS",
                    "NUMEXPR_NUM_THREADS",
                )
            },
            physical_horizon_s=150e-6,
            reference_checkpoint_times_s=[50e-6, 150e-6],
            independent_trajectory_recomputed=False,
            automatic_followup=False,
        ),
    )
    bounded(
        [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            str(snapshot / TEST),
        ],
        output / "prepare-collect",
        snapshot,
        env,
        timeout=120,
    )
    assert "27 tests collected" in (output / "prepare-collect/stdout.log").read_text()
    assert hashes(snapshot) == after
    for p in snapshot.rglob("*"):
        if p.is_file():
            p.chmod(0o444)
    for p in sorted(
        (p for p in snapshot.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True
    ):
        p.chmod(0o555)
    snapshot.chmod(0o555)
    print(
        json.dumps(
            dict(
                status="prepared",
                output=str(output),
                files=len(after),
                tests_collected=27,
                full_150us_schedule_retained=True,
                compiled_execution=False,
            )
        )
    )
    return 0


def launch(output):
    assert sha(Path(__file__)) == sha(output / "snapshot" / SELF)
    assert read(output / "original-schedule-proof.json")["status"] == "passed"
    assert not (output / "job-launch.json").exists()
    command = [
        sys.executable,
        "-B",
        str(output / "snapshot" / SELF),
        "--output",
        str(output),
        "--action",
        "run",
    ]
    with (output / "driver.log").open("xb") as log:
        child = subprocess.Popen(
            command,
            cwd=output / "snapshot",
            env=environment(output),
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    receipt = dict(
        status="launched",
        pid=child.pid,
        started_utc=datetime.now(UTC).isoformat(),
        command=command,
        source_manifest_sha256=sha(output / "frozen-sources.json"),
        expected_duration_over_10_minutes=True,
        estimated_minutes=[30, 75],
        max_wall_seconds=WALL_SECONDS,
        max_host_rss_bytes=2**30,
        min_available_memory_bytes=8 * 2**30,
        compiled_execution=False,
        automatic_polling=False,
    )
    write(output / "job-launch.json", receipt)
    print(json.dumps(receipt))
    return 0


def run(output):
    assert sha(Path(__file__)) == sha(output / "snapshot" / SELF)
    frozen = read(output / "frozen-sources.json")
    assert hashes(output / "snapshot") == frozen["after_sha256"]
    inputs = read(output / "inputs.json")
    write(
        output / "job-status.json",
        dict(status="running", pid=os.getpid(), started_utc=datetime.now(UTC).isoformat()),
    )
    command = ["/usr/bin/time", "-v", "-o", str(output / "external-time.txt"), *inputs["command"]]
    began, failure = time.monotonic(), None
    try:
        bounded(
            command,
            output / "host-guard",
            output / "snapshot",
            environment(output),
            timeout=WALL_SECONDS,
        )
    except Exception as error:
        failure = dict(
            type=type(error).__name__, message=str(error), traceback=traceback.format_exc()
        )
    unchanged = hashes(output / "snapshot") == frozen["after_sha256"]
    counts = dict.fromkeys(("tests", "errors", "failures", "skipped"), 0)
    if (output / "full-tests.xml").exists():
        for suite in ET.parse(output / "full-tests.xml").getroot().iter("testsuite"):
            for k in counts:
                counts[k] += int(suite.get(k, "0"))
    passed = (
        failure is None and unchanged and counts == dict(tests=27, errors=0, failures=0, skipped=0)
    )
    result = dict(
        status="passed" if passed else "failed",
        tests=counts,
        error=failure,
        elapsed_seconds=time.monotonic() - began,
        sources_unchanged=unchanged,
        source_manifest_sha256=sha(output / "frozen-sources.json"),
        retained_original_schedule=read(output / "original-schedule-proof.json"),
        inherited_focused_component=str(BASE / "result.json"),
        inherited_focused_component_sha256=BASE_SHA,
        host_guard=read(output / "host-guard/result.json") if passed else None,
        reference_handoff_sha256=REFERENCE_SHA,
        physical_horizon_s=150e-6,
        compiled_execution=False,
        shared_source_edits=False,
        automatic_followup=False,
    )
    result["output_sha256"] = {
        p: h
        for p, h in hashes(output).items()
        if p not in {"driver.log", "job-status.json", "job-launch.json", "result.json"}
    }
    write(output / "result.json", result)
    if not passed:
        write(output / "failure.json", result)
    write(
        output / "job-status.json",
        dict(
            status=result["status"],
            pid=os.getpid(),
            tests=counts,
            elapsed_seconds=result["elapsed_seconds"],
        ),
    )
    print(
        json.dumps(dict(status=result["status"], tests=counts, receipt=str(output / "result.json")))
    )
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--action", choices=("prepare", "launch", "run"), required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.parent == Path("/mnt/workspaces/Cells")
    assert output.name.startswith("regulated-v2-excision-full-schedule-")
    assert sorted(os.sched_getaffinity(0)) == [7]
    try:
        return {"prepare": prepare, "launch": launch, "run": run}[args.action](output)
    except Exception as error:
        failure = dict(
            status="failed",
            action=args.action,
            type=type(error).__name__,
            message=str(error),
            traceback=traceback.format_exc(),
        )
        if output.exists():
            write(output / ("failure-" + args.action + ".json"), failure)
            if args.action == "run":
                write(output / "job-status.json", failure)
        print(json.dumps(failure))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
