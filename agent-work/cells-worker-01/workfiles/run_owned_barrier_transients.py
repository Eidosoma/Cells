"""Guarded pilot, or an explicitly launched detached full-10us suite."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from pathlib import Path

OWNED_OUTPUT = None


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def verify(bundle):
    manifest = read(bundle / "manifest.json")
    for name, expected in manifest["file_sha256"].items():
        assert sha(bundle / name) == expected, name
    receipt = manifest["stage_handoff"]
    assert sha(Path(receipt["path"])) == receipt["sha256"]
    return manifest


def completed_successfully(error, changed, counts, completed, expected, pilot):
    return (
        error is None
        and not changed
        and completed == expected
        and (pilot or counts == dict(tests=6, errors=0, failures=0, skipped=0))
    )


def main():
    global OWNED_OUTPUT
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--pilot", action="store_true")
    mode.add_argument("--launch", action="store_true")
    mode.add_argument("--execute", action="store_true")
    p.add_argument("--completed-pilot", type=Path)
    p.add_argument("--runner-sha256")
    a = p.parse_args()
    bundle = a.bundle.resolve()
    output = a.output.resolve()
    if a.execute or a.pilot:
        output.mkdir(parents=True, exist_ok=False)
        OWNED_OUTPUT = output
        assert a.runner_sha256 == sha(Path(__file__).resolve()), "Worker supervisor changed"
    manifest = verify(bundle)
    if a.check:
        print(
            json.dumps(
                dict(
                    status="verified",
                    manifest_sha256=sha(bundle / "manifest.json"),
                    numerical_work_run=False,
                )
            )
        )
        return 0
    if a.launch or a.execute:
        assert a.completed_pilot is not None, "Root launch requires the completed bounded pilot"
        pilot = read(a.completed_pilot / "result.json")
        assert pilot["status"] == "passed" and pilot["pilot_only"] is True
        assert pilot["bundle_manifest_sha256"] == sha(bundle / "manifest.json")
        for name, expected in pilot["output_sha256"].items():
            assert sha(a.completed_pilot / name) == expected
    if a.launch:
        assert not output.exists()
        available = next(
            int(row.split()[1]) * 1024
            for row in Path("/proc/meminfo").read_text().splitlines()
            if row.startswith("MemAvailable:")
        )
        assert available >= 12 * 2**30, "Need12GiB available before this1GiB worker"
        launch = output.with_name(output.name + "-launch")
        launch.mkdir(exist_ok=False)
        command = [
            sys.executable,
            "-B",
            str(Path(__file__).resolve()),
            "--execute",
            "--bundle",
            str(bundle),
            "--output",
            str(output),
            "--completed-pilot",
            str(a.completed_pilot.resolve()),
            "--runner-sha256",
            sha(Path(__file__).resolve()),
        ]
        with (launch / "supervisor.log").open("wb") as log:
            process = subprocess.Popen(
                command,
                cwd=bundle,
                stdout=log,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True,
            )
        now = datetime.now(UTC)
        write(
            launch / "launch.json",
            dict(
                status="launched",
                utc=now.isoformat(),
                pid=process.pid,
                command=command,
                bundle_manifest_sha256=sha(bundle / "manifest.json"),
                cpu=3,
                supervisor=dict(
                    path=str(Path(__file__).resolve()), sha256=sha(Path(__file__).resolve())
                ),
                available_before_launch_bytes=available,
                expected_duration_minutes=[90, 180],
                automatic_polling=False,
                automatic_retry=False,
                failure=str(output / "failure.json"),
                max_child_tree_rss_bytes=2**30,
                min_host_reserve_bytes=8 * 2**30,
                estimated_completion_utc=[
                    (now + timedelta(minutes=n)).isoformat() for n in (90, 180)
                ],
                durable_log=str(launch / "supervisor.log"),
                result=str(output / "result.json"),
                automatic_followup=False,
            ),
        )
        print(
            json.dumps(
                dict(status="launched", receipt=str(launch / "launch.json"), pid=process.pid)
            )
        )
        return 0
    os.sched_setaffinity(0, {3})
    workspace = bundle / "workspace"
    env = os.environ | dict(
        PYTHONPATH=str(workspace / "src") + ":" + str(workspace),
        PYTHONDONTWRITEBYTECODE="1",
        JAX_PLATFORMS="cpu",
        JAX_ENABLE_X64="true",
        JAX_DISABLE_JIT="true",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        MALLOC_ARENA_MAX="2",
        CELLS_BARRIER_BUNDLE=str(bundle),
        CELLS_BARRIER_OUTPUT=str(output),
    )
    sys.path[:0] = [str(workspace / "src"), str(workspace)]
    from validation.assembly.component_process import run_bounded
    from validation.transport.owned_barrier_transient_fixtures import DATASETS

    if not a.pilot:
        paths = [
            a.completed_pilot / "evidence/energy-reseal" / f"pilot-{role}-{factor}-chunk0.json"
            for role in ("reference", "production")
            for factor in (1, 2)
        ]
        for path in paths:
            assert read(path)["status"] == "completed"
            target = output / path.relative_to(a.completed_pilot)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            shutil.copyfile(path.with_suffix(".npz"), target.with_suffix(".npz"))
        write(
            output / "retained-pilot.json",
            dict(
                path=str(a.completed_pilot / "result.json"),
                sha256=sha(a.completed_pilot / "result.json"),
                reused_integration_units=4,
                rerun=False,
            ),
        )
    for name in (
        "stage-result.json",
        "stage-tests.xml",
        "public-result.json",
        "public-tests.xml",
        "public-verification.json",
    ):
        shutil.copyfile(bundle / "retained" / name, output / ("retained-" + name))
    commands = []
    for dataset in ["energy-reseal"] if a.pilot else DATASETS:
        for role in ("reference", "production"):
            for factor in (1, 2):
                for chunk in [0] if a.pilot else range(4):
                    tag = f"{dataset}-{role}-{factor}-chunk{chunk}"
                    argv = [
                        sys.executable,
                        "-B",
                        str(workspace / "tests/owned_barrier_transient_helpers.py"),
                        "--bundle",
                        str(bundle),
                        "--output",
                        str(output),
                        "--dataset",
                        dataset,
                        "--role",
                        role,
                        "--factor",
                        str(factor),
                        "--chunk",
                        str(chunk),
                    ]
                    if a.pilot:
                        argv.append("--pilot")
                    commands.append((tag, argv, 120 if a.pilot else 480))
        if a.pilot:
            argv = [
                sys.executable,
                "-B",
                str(workspace / "tests/owned_barrier_transient_helpers.py"),
                "--bundle",
                str(bundle),
                "--output",
                str(output),
                "--dataset",
                dataset,
                "--role",
                "comparison",
                "--pilot",
            ]
        else:
            argv = [
                sys.executable,
                "-B",
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "--basetemp=" + str(output / (dataset + "-tmp")),
                "--junitxml=" + str(output / (dataset + "-tests.xml")),
                "tests/unit/test_owned_barrier_transients.py::test_complete_scheduled_barrier_transient_refinement["
                + dataset
                + "]",
            ]
        commands.append((dataset + "-comparison", argv, 60 if a.pilot else 180))
    write(
        output / "inputs.json",
        dict(
            utc=datetime.now(UTC).isoformat(),
            commands=[dict(name=n, argv=v, timeout_seconds=t) for n, v, t in commands],
            bundle=str(bundle),
            bundle_manifest_sha256=sha(bundle / "manifest.json"),
            affinity=sorted(os.sched_getaffinity(0)),
            pilot_only=a.pilot,
            supervisor=dict(
                path=str(Path(__file__).resolve()), sha256=sha(Path(__file__).resolve())
            ),
            retained_stage_checks=62,
            retained_public_checks=17,
            full_suite_launched=not a.pilot,
            automatic_followup=False,
        ),
    )
    print(
        json.dumps(
            dict(status="running", output=str(output), pilot_only=a.pilot, units=len(commands))
        ),
        flush=True,
    )
    checks = []
    error = None
    try:
        for name, argv, timeout in commands:
            write(
                output / "job-status.json",
                dict(status="running", stage=name, utc=datetime.now(UTC).isoformat()),
            )
            directory = output / (name + "-guard")
            directory.mkdir()
            resource = run_bounded(
                argv,
                directory=directory,
                cwd=workspace,
                env=env,
                timeout=timeout,
                max_rss_bytes=2**30,
                min_available_bytes=8 * 2**30,
            )
            checks.append(
                dict(
                    name=name,
                    resource_receipt=str(directory / "result.json"),
                    elapsed_seconds=resource["elapsed_seconds"],
                )
            )
    except Exception as exception:
        error = dict(
            type=type(exception).__name__, message=str(exception), traceback=traceback.format_exc()
        )
        write(output / "failure.json", error)
    changed = [n for n, v in manifest["file_sha256"].items() if sha(bundle / n) != v]
    counts = dict(tests=0, errors=0, failures=0, skipped=0)
    for path in output.glob("*-tests.xml"):
        if path.name.startswith("retained-"):
            continue
        for suite in ET.parse(path).getroot().iter("testsuite"):
            for key in counts:
                counts[key] += int(suite.get(key, "0"))
    passed = completed_successfully(error, changed, counts, len(checks), len(commands), a.pilot)
    if not passed and error is None:
        error = dict(
            type="IncompleteQualification",
            message=(
                "Require complete commands, unchanged frozen sources "
                "and exactly six passing comparisons"
            ),
            counts=counts,
            changed_bundle_files=changed,
        )
        write(output / "failure.json", dict(status="failed", error=error))
    write(
        output / "job-status.json",
        dict(status="passed" if passed else "failed", utc=datetime.now(UTC).isoformat()),
    )
    artifacts = {
        p.relative_to(output).as_posix(): sha(p)
        for p in sorted(output.rglob("*"))
        if p.is_file() and p.name not in ("result.json",)
    }
    result = dict(
        status="passed" if passed else "failed",
        utc=datetime.now(UTC).isoformat(),
        pilot_only=a.pilot,
        completed_units=checks,
        error=error,
        changed_bundle_files=changed,
        new_comparison_counts=counts,
        retained_stage_checks=62,
        retained_public_checks=17,
        bundle_manifest_sha256=sha(bundle / "manifest.json"),
        output_sha256=artifacts,
        full_trajectory_credit=passed and not a.pilot,
        automatic_followup=False,
    )
    write(output / "result.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "output_sha256"}), flush=True)
    return 0 if result["status"] == "passed" else 1


def guarded_main():
    try:
        return main()
    except Exception as error:
        # Only a worker that created its new output directory may write here.
        # An existing job or failed launch preflight is never overwritten.
        if OWNED_OUTPUT is not None:
            failure = dict(
                status="failed",
                utc=datetime.now(UTC).isoformat(),
                type=type(error).__name__,
                error=str(error),
                traceback=traceback.format_exc(),
                full_trajectory_credit=False,
                automatic_retry=False,
                automatic_followup=False,
            )
            write(OWNED_OUTPUT / "failure.json", failure)
            write(OWNED_OUTPUT / "result.json", failure)
            write(OWNED_OUTPUT / "job-status.json", dict(status="failed", utc=failure["utc"]))
        raise


if __name__ == "__main__":
    raise SystemExit(guarded_main())
