"""Detached same-1 ms live recording and matched-window qualification, no follow-up."""

import argparse
import json
import os
import resource
import signal
import subprocess
import time
import traceback
import warnings
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import live_context as ctx


def receipt(path):
    ctx.need(path.is_relative_to(ctx.ROOT / "reports"), "Software receipt location")
    suites = ET.parse(path).getroot().findall("testsuite")
    cases = [v for s in suites for v in s.findall("testcase")]
    ctx.need(len(cases) == sum(int(s.get("tests", "0")) for s in suites) >= 79, "Software coverage")
    ctx.need(
        all(int(s.get(k, "0")) == 0 for s in suites for k in ("failures", "errors", "skipped"))
        and all(v.find(k) is None for v in cases for k in ("failure", "error", "skipped")),
        "Nonpassing software",
    )
    ctx.need(
        all("test_live_recording" in v.get("classname", "") for v in cases), "Wrong software suite"
    )
    names = {v.get("name", "").split("[")[0] for v in cases}
    ctx.need(
        {
            "test_actual_native_smoke",
            "test_actual_cells_smoke",
            "test_saved_real_boundary_replay_exact",
            "test_pending_buffers_release_with_gc_disabled",
        }
        <= names,
        "Missing actual-boundary/simulator preflight",
    )
    ctx.need(
        sum(v.get("name", "").startswith("test_actual_native_smoke[") for v in cases) == 2
        and sum(v.get("name", "") == "test_actual_cells_smoke" for v in cases) == 1
        and sum(
            v.get("name", "").startswith("test_saved_real_boundary_replay_exact[") for v in cases
        )
        == 12,
        "Incomplete actual preflight matrix",
    )
    return dict(path=str(path.relative_to(ctx.ROOT)), sha256=ctx.sha(path), tests=len(cases))


def register(output, tests):
    ctx.need(
        output.is_relative_to(ctx.ROOT / "runs")
        and output != ctx.ROOT / "runs"
        and not output.exists(),
        "Fresh run directory required",
    )
    evidence = ctx.prerequisite()
    r = dict(
        schema="cells.live_recording_qualification@1",
        decision="D125",
        duration_s=0.001,
        bounds=ctx.BOUNDS,
        prior=evidence,
        software=receipt(tests),
        sources_sha256=ctx.sources(),
        native_labels=sorted(ctx.read(ctx.CODEC / "registration.json")["records"]),
        cells_keys=sorted(ctx.read(ctx.LEGACY / "cells.json")["records"]),
        native_runs=36,
        cells_full_trajectories=24,
        window_widths=[1, 7, 64],
        disk_recording_policies=["full", "observations", "checkpoints"],
        scientific_tolerances_changed=False,
        production_changed=False,
        native_histories_pruned=False,
        native_memory_bounded=False,
        automatic_retry=False,
        automatic_followup=False,
        registered_utc=datetime.now(UTC).isoformat(),
    )
    output.mkdir(parents=True)
    try:
        ctx.budget(output, reserve=64 * 1024**2)
        ctx.write(output / "registration.json", r)
        with zipfile.ZipFile(
            output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for name in r["sources_sha256"]:
                archive.write(ctx.ROOT / name, arcname=name)
        authenticate(output, ctx.sha(output / "registration.json"))
    except BaseException:
        ctx.write(
            output / "registration-failure.json",
            dict(status="not_launched", traceback=traceback.format_exc()),
        )
        raise
    return r


def authenticate(output, expected_sha):
    ctx.need(
        ctx.sha(output / "registration.json") == expected_sha, "Launch-bound registration changed"
    )
    r = ctx.read(output / "registration.json")
    ctx.need(
        r["schema"] == "cells.live_recording_qualification@1"
        and r["bounds"] == ctx.BOUNDS
        and r["duration_s"] == 0.001,
        "Run scope changed",
    )
    ctx.need(r["sources_sha256"] == ctx.sources(), "Frozen sources changed")
    ctx.capsule(output, r["sources_sha256"])
    ctx.need(receipt(ctx.ROOT / r["software"]["path"]) == r["software"], "Software receipt changed")
    ctx.hashes(ctx.AUDIT, r["prior"]["audit_files_sha256"])
    ctx.hashes(ctx.CODEC, r["prior"]["codec_files_sha256"])
    return r


def gate(phase, result, r):
    if phase == "native":
        ctx.need(
            result["status"] == "live_overlap_pass_pending_independent_review"
            and result["native_runs"] == 36
            and len(result["observer_pairs"]) == 18
            and sorted(result["records"]) == r["native_labels"]
            and result["observed_updates"] == 6720
            and result["history_samples"] == 13404
            and result["native_memory_bounded"] is False,
            "Native matrix gate",
        )
        for row in result["records"].values():
            ctx.need(
                row["overlap"]["failed_comparisons"] == 0 and row["overlap"]["exact_scalars"] > 0,
                "Native overlap failed",
            )
        ctx.need(
            all(pair["failed_comparisons"] == 0 for pair in result["observer_pairs"]),
            "Observer interference",
        )
    else:
        ctx.need(
            phase == "cells"
            and result["status"] == "matched_windows_pass_pending_independent_review"
            and sorted(result["records"]) == r["cells_keys"],
            "Cells matrix gate",
        )
        for name, value in dict(
            full_trajectories=24,
            window_runs=72,
            disk_recordings=18,
            restart_suffixes=6,
            restart_window_runs=6,
            zero_length_runs=6,
            sparse_schedule_controls=2,
        ).items():
            ctx.need(result[name] == value, "Cells coverage: " + name)
        for name, value in dict(windows=72, recordings=18, restarts=6).items():
            ctx.need(
                sum(v[name] for v in result["records"].values()) == value, "Cells row coverage"
            )


def worker(output, phase, expected_sha):
    try:
        r = authenticate(output, expected_sha)
        resource.setrlimit(resource.RLIMIT_AS, (ctx.BOUNDS[phase + "_address_space_bytes"],) * 2)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            if phase == "native":
                from live_native import worker as work
            else:
                ctx.need(phase == "cells", "Unknown worker")
                from matched_windows import worker as work
            result = work(output, r)
        ctx.write(output / (phase + ".json"), result)
        gate(phase, result, r)
        authenticate(output, expected_sha)
    except BaseException:
        ctx.write(
            output / (phase + "-failure.json"),
            dict(status="worker_failed", phase=phase, traceback=traceback.format_exc()),
        )
        raise


def payloads(output):
    return {
        n: h
        for n, h in ctx.inventory(output).items()
        if n not in ("launch.json", "runner.stdout.log", "runner.stderr.log")
    }


def execute(output, expected_sha):
    ctx.need(not (output / "started.json").exists(), "Run already attempted")
    started = time.monotonic()

    def deadline(_signal, _frame):
        raise TimeoutError("Live/window qualification wall-time cap")

    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, ctx.BOUNDS["timeout_seconds"])
    try:
        ctx.write(
            output / "started.json",
            dict(pid=os.getpid(), started_utc=datetime.now(UTC).isoformat()),
        )
        r = authenticate(output, expected_sha)
        ctx.need(ctx.prerequisite() == r["prior"], "Prerequisite changed before execution")
        ctx.need(sorted(os.sched_getaffinity(0)) == ctx.BOUNDS["cpu_affinity"], "CPU affinity")
        resource.setrlimit(resource.RLIMIT_FSIZE, (ctx.BOUNDS["per_file_bytes"],) * 2)
        for phase in ("native", "cells"):
            python = ctx.NATIVE_PYTHON if phase == "native" else ctx.CELLS_PYTHON
            with (
                (output / (phase + ".stdout.log")).open("x") as stdout,
                (output / (phase + ".stderr.log")).open("x") as stderr,
            ):
                subprocess.run(
                    [
                        str(python),
                        "-B",
                        str(Path(__file__).resolve()),
                        "worker",
                        str(output),
                        "--phase",
                        phase,
                        "--registration-sha",
                        expected_sha,
                    ],
                    cwd=ctx.ROOT,
                    env=ctx.environment(),
                    stdin=subprocess.DEVNULL,
                    stdout=stdout,
                    stderr=stderr,
                    check=True,
                    timeout=ctx.BOUNDS[phase + "_timeout_seconds"],
                )
            gate(phase, ctx.read(output / (phase + ".json")), r)
            notices = (output / (phase + ".stderr.log")).read_text().splitlines()
            expected_notices = (
                ["[betse] Ignoring cutting event, as cut profiles are disabled."] * 72
                if phase == "native"
                else []
            )
            ctx.need(notices == expected_notices, "Unexpected worker stderr")
            ctx.budget(output)
            ctx.write(
                output / (phase + "-complete.json"),
                dict(status="phase_pass", phase=phase, elapsed_seconds=time.monotonic() - started),
            )
        authenticate(output, expected_sha)
        ctx.need(ctx.prerequisite() == r["prior"], "Prerequisite changed during execution")
        used = ctx.budget(output)
        ctx.write(
            output / "completion.json",
            dict(
                status="live_recording_and_matched_windows_pass_pending_independent_review",
                files_sha256=payloads(output),
                elapsed_seconds=time.monotonic() - started,
                finished_utc=datetime.now(UTC).isoformat(),
                artifact_bytes_before_completion=used,
                native_runs=36,
                exact_native_overlaps=36,
                observer_pairs=18,
                observed_updates=6720,
                history_samples=13404,
                cells_full_trajectories=24,
                cells_window_runs=72,
                cells_disk_recordings=18,
                cells_restart_suffixes=6,
                known_disabled_cut_notices=72,
                native_memory_bounded=False,
                independent_live_review_complete=False,
                longer_horizon_qualified=False,
                production_changed=False,
                scientific_tolerances_changed=False,
                biology_validated=False,
                gpu_tested=False,
                automatic_followup=False,
            ),
        )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        ctx.write(
            output / "failure.json",
            dict(
                status="live_window_qualification_failed",
                elapsed_seconds=time.monotonic() - started,
                traceback=traceback.format_exc(),
                automatic_retry=False,
            ),
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def launch(output, tests):
    register(output, tests)
    expected_sha = ctx.sha(output / "registration.json")
    try:
        with (
            (output / "runner.stdout.log").open("x") as stdout,
            (output / "runner.stderr.log").open("x") as stderr,
        ):
            child = subprocess.Popen(
                [
                    "taskset",
                    "-c",
                    "0-3",
                    str(ctx.CELLS_PYTHON),
                    "-B",
                    str(Path(__file__).resolve()),
                    "execute",
                    str(output),
                    "--registration-sha",
                    expected_sha,
                ],
                cwd=ctx.ROOT,
                env=ctx.environment(),
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
            )
        ack = dict(
            status="launched_detached",
            pid=child.pid,
            registration_sha256=expected_sha,
            launched_utc=datetime.now(UTC).isoformat(),
            automatic_polling=False,
        )
        ctx.write(output / "launch.json", ack)
        return ack
    except BaseException:
        ctx.write(
            output / "launch-failure.json",
            dict(status="not_launched", traceback=traceback.format_exc()),
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("launch", "execute", "worker"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--tests", type=Path)
    parser.add_argument("--phase", choices=("native", "cells"))
    parser.add_argument("--registration-sha")
    args = parser.parse_args()
    if args.action == "launch":
        ctx.need(args.tests is not None, "Missing --tests")
        print(json.dumps(launch(args.output.resolve(), args.tests.resolve()), sort_keys=True))
    else:
        ctx.need(args.registration_sha is not None, "Missing registration binding")
        if args.action == "execute":
            execute(args.output.resolve(), args.registration_sha)
        else:
            ctx.need(args.phase is not None, "Missing --phase")
            worker(args.output.resolve(), args.phase, args.registration_sha)
