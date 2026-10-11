"""Detached D128 qualification: actual shared-worker regression gates the full matrix."""

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

import output_context as plan
from output_context import ctx, original, previous

REQUIRED_TESTS = {
    "test_same_worker_uses_disjoint_output_roles",
    "test_original_path_collision_regression",
    "test_probe_gate_precedes_matrix",
    "test_failed_probe_never_starts_matrix",
    "test_changed_probe_receipt_blocks_matrix",
    "test_registration_binding_refuses_changes",
    "test_all_numerical_checks_are_reused",
}


def receipt(path):
    ctx.need(path.is_relative_to(ctx.ROOT / "reports"), "Software receipt location")
    suites = ET.parse(path).getroot().findall("testsuite")
    cases = [c for suite in suites for c in suite.findall("testcase")]
    names = {(c.get("classname"), c.get("name")) for c in cases}
    ctx.need(
        len(cases) == len(names) == sum(int(s.get("tests", "0")) for s in suites) >= 25
        and all(int(s.get(k, "0")) == 0 for s in suites for k in ("failures", "errors", "skipped"))
        and all(c.find(k) is None for c in cases for k in ("failure", "error", "skipped"))
        and all("test_output_paths" in c.get("classname", "") for c in cases)
        and REQUIRED_TESTS <= {c.get("name", "").split("[")[0] for c in cases},
        "Incomplete/nonpassing output-layout software",
    )
    return dict(path=str(path.relative_to(ctx.ROOT)), sha256=ctx.sha(path), tests=len(cases))


def check(output, tests):
    """Short source-bound filesystem/orchestration tests; actual-model probe runs detached."""
    from preflight_job import artifacts

    previous.fresh(output)
    ctx.need(tests.is_relative_to(ctx.ROOT / "reports") and not tests.exists(), "Fresh receipt")
    ctx.path_for(ctx.ROOT, str(tests.relative_to(ctx.ROOT)))
    before = plan.sources()
    output.mkdir(parents=True)
    start = time.monotonic()
    ctx.write(output / "registration.json", dict(sources_sha256=before, test_timeout_seconds=60))
    try:
        with (
            (output / "tests.stdout.log").open("x") as out,
            (output / "tests.stderr.log").open("x") as err,
        ):
            previous.run_child(
                [
                    str(ctx.CELLS_PYTHON),
                    "-B",
                    "-m",
                    "pytest",
                    "-q",
                    "-W",
                    "error",
                    str(plan.HERE / "test_output_paths.py"),
                    "--junitxml=" + str(tests),
                    "--basetemp=" + str(output / "tests"),
                ],
                out,
                err,
                60,
            )
        software = receipt(tests)
        ctx.need(plan.sources() == before, "Sources changed during software check")
        ctx.need((output / "tests.stderr.log").read_bytes() == b"", "Software stderr")
        result = dict(
            status="output_layout_software_pass",
            software=software,
            sources_sha256=before,
            **artifacts(output),
            elapsed_seconds=time.monotonic() - start,
            actual_model_probe_complete=False,
            qualification_launched=False,
            automatic_followup=False,
        )
        ctx.write(output / "completion.json", result)
        return {k: result[k] for k in ("status", "software", "elapsed_seconds")}
    except BaseException:
        ctx.write(
            output / "failure.json",
            dict(status="software_failed", traceback=traceback.format_exc()),
        )
        raise


def software(evidence):
    from preflight_job import artifacts

    path = ctx.path_for(ctx.ROOT, evidence)
    ctx.need(
        path.is_relative_to(ctx.ROOT / "runs") and path.name == "completion.json", "Software packet"
    )
    done = ctx.read(path)
    ctx.need(
        done["status"] == "output_layout_software_pass"
        and done["sources_sha256"] == plan.sources()
        and all(
            done[k] is False
            for k in ("actual_model_probe_complete", "qualification_launched", "automatic_followup")
        )
        and not (path.parent / "failure.json").exists(),
        "Changed software context",
    )
    actual = artifacts(path.parent)
    ctx.need(
        actual["files_sha256"] == done["files_sha256"] | {"completion.json": ctx.sha(path)}
        and actual["pytest_internal_links"] == done["pytest_internal_links"],
        "Software artifacts changed",
    )
    ctx.need(
        receipt(ctx.ROOT / done["software"]["path"]) == done["software"], "Software XML changed"
    )
    return dict(path=evidence, sha256=ctx.sha(path), xml=done["software"])


def register(output, checked):
    previous.fresh(output)
    prior = plan.prerequisites()
    r = dict(
        schema="cells.live_recording_output_layout@1",
        decision="D128",
        duration_s=0.001,
        bounds=ctx.BOUNDS,
        phase_timeouts=plan.PHASE_TIMEOUTS,
        phases=["probe", "matrix"],
        output_layout_version=plan.LAYOUT_VERSION,
        output_layout=plan.LAYOUT,
        probe_keys=[plan.PROBE_KEY],
        cells_keys=sorted(ctx.read(ctx.LEGACY / "cells.json")["records"]),
        phase_counts=plan.COUNTS,
        prior=prior,
        sources_sha256=plan.sources(),
        software=software(checked),
        new_native_runs=0,
        partial_cells_reused=False,
        production_changed=False,
        scientific_tolerances_changed=False,
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


def authenticate(output, digest):
    ctx.need(ctx.sha(output / "registration.json") == digest, "Launch-bound registration changed")
    r = ctx.read(output / "registration.json")
    ctx.need(
        r["schema"] == "cells.live_recording_output_layout@1"
        and r["decision"] == "D128"
        and r["duration_s"] == 0.001
        and r["bounds"] == ctx.BOUNDS
        and r["phase_timeouts"] == plan.PHASE_TIMEOUTS
        and r["phases"] == ["probe", "matrix"]
        and r["output_layout_version"] == plan.LAYOUT_VERSION
        and r["output_layout"] == plan.LAYOUT
        and r["probe_keys"] == [plan.PROBE_KEY]
        and r["phase_counts"] == plan.COUNTS
        and r["new_native_runs"] == 0
        and all(
            r[k] is False
            for k in (
                "partial_cells_reused",
                "production_changed",
                "scientific_tolerances_changed",
                "automatic_retry",
                "automatic_followup",
            )
        ),
        "Output-layout scope changed",
    )
    plan.selected_keys(r, "matrix")
    ctx.need(r["sources_sha256"] == plan.sources(), "Frozen output-layout sources changed")
    ctx.capsule(output, r["sources_sha256"])
    ctx.need(software(r["software"]["path"]) == r["software"], "Software evidence changed")
    plan.authenticate_prior(r["prior"])
    return r


def probe_gate(output, r, digest):
    done = ctx.read(output / "probe-complete.json")
    ctx.need(
        done["status"] == "phase_pass"
        and done["phase"] == "probe"
        and done["registration_sha256"] == digest
        and done["result_sha256"] == ctx.sha(output / "probe.json")
        and done["files_sha256"] == ctx.inventory(output / "probe")
        and not (output / "probe-failure.json").exists()
        and (output / "probe.stderr.log").read_bytes() == b"",
        "Probe receipt changed/incomplete",
    )
    plan.gate("probe", ctx.read(output / "probe.json"), r)


def worker(output, digest, phase):
    ctx.need(phase in plan.PHASE_TIMEOUTS, "Unknown phase")
    try:
        r = authenticate(output, digest)
        if phase == "matrix":
            probe_gate(output, r, digest)
        directory = output / phase
        directory.mkdir(exist_ok=False)
        resource.setrlimit(resource.RLIMIT_AS, (ctx.BOUNDS["cells_address_space_bytes"],) * 2)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            from output_worker import worker as work

            result = work(directory, r, phase)
        plan.gate(phase, result, r)
        ctx.write(output / (phase + ".json"), result)
        authenticate(output, digest)
    except BaseException:
        ctx.write(
            output / (phase + "-failure.json"),
            dict(status="worker_failed", phase=phase, traceback=traceback.format_exc()),
        )
        raise


def execute(output, digest):
    ctx.need(not (output / "started.json").exists(), "Qualification already attempted")
    start = time.monotonic()

    def deadline(_signal, _frame):
        raise TimeoutError("Output-layout qualification overall deadline")

    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, ctx.BOUNDS["timeout_seconds"])
    try:
        ctx.write(
            output / "started.json",
            dict(pid=os.getpid(), started_utc=datetime.now(UTC).isoformat()),
        )
        r = authenticate(output, digest)
        ctx.need(
            ctx.prerequisite() == r["prior"]["accepted"], "Prerequisite changed before execution"
        )
        ctx.need(sorted(os.sched_getaffinity(0)) == ctx.BOUNDS["cpu_affinity"], "CPU affinity")
        resource.setrlimit(resource.RLIMIT_FSIZE, (ctx.BOUNDS["per_file_bytes"],) * 2)
        ctx.write(output / "native-reuse.json", r["prior"]["reused_native"])
        for phase in ("probe", "matrix"):
            if phase == "matrix":
                probe_gate(output, r, digest)
            phase_start = time.monotonic()
            with (
                (output / (phase + ".stdout.log")).open("x") as out,
                (output / (phase + ".stderr.log")).open("x") as err,
            ):
                previous.run_child(
                    [
                        str(ctx.CELLS_PYTHON),
                        "-B",
                        str(Path(__file__).resolve()),
                        "worker",
                        str(output),
                        "--registration-sha",
                        digest,
                        "--phase",
                        phase,
                    ],
                    out,
                    err,
                    plan.PHASE_TIMEOUTS[phase],
                )
            plan.gate(phase, ctx.read(output / (phase + ".json")), r)
            ctx.need(
                (output / (phase + ".stderr.log")).read_bytes() == b"", "Unexpected worker stderr"
            )
            authenticate(output, digest)
            ctx.budget(output)
            ctx.write(
                output / (phase + "-complete.json"),
                dict(
                    status="phase_pass",
                    phase=phase,
                    registration_sha256=digest,
                    result_sha256=ctx.sha(output / (phase + ".json")),
                    files_sha256=ctx.inventory(output / phase),
                    elapsed_seconds=time.monotonic() - phase_start,
                ),
            )
        probe_gate(output, r, digest)
        ctx.need(
            ctx.prerequisite() == r["prior"]["accepted"], "Prerequisite changed during execution"
        )
        used = ctx.budget(output)
        ctx.write(
            output / "completion.json",
            dict(
                status="live_recording_and_matched_windows_pass_pending_independent_review",
                files_sha256=original.payloads(output),
                elapsed_seconds=time.monotonic() - start,
                finished_utc=datetime.now(UTC).isoformat(),
                artifact_bytes_before_completion=used,
                output_layout_version=plan.LAYOUT_VERSION,
                actual_worker_probe_complete=True,
                probe_counts=plan.COUNTS["probe"],
                matrix_counts=plan.COUNTS["matrix"],
                native_runs_reused=36,
                new_native_runs=0,
                observer_pairs=18,
                observed_updates=6720,
                history_samples=13404,
                known_disabled_cut_notices=72,
                earlier_attempts_stay_failed=True,
                partial_cells_reused=False,
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
                status="output_layout_qualification_failed",
                elapsed_seconds=time.monotonic() - start,
                traceback=traceback.format_exc(),
                automatic_retry=False,
            ),
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def launch(output, checked):
    register(output, checked)
    digest = ctx.sha(output / "registration.json")
    try:
        with (
            (output / "runner.stdout.log").open("x") as out,
            (output / "runner.stderr.log").open("x") as err,
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
                    digest,
                ],
                cwd=ctx.ROOT,
                env=ctx.environment(),
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                start_new_session=True,
            )
        ack = dict(
            status="launched_detached",
            pid=child.pid,
            registration_sha256=digest,
            launched_utc=datetime.now(UTC).isoformat(),
            automatic_polling=False,
            phases=["probe", "matrix"],
            new_native_runs=0,
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
    parser.add_argument("action", choices=("check", "launch", "execute", "worker"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--tests", type=Path)
    parser.add_argument("--checked")
    parser.add_argument("--registration-sha")
    parser.add_argument("--phase", choices=tuple(plan.PHASE_TIMEOUTS))
    args = parser.parse_args()
    if args.action == "check":
        ctx.need(args.tests is not None, "Missing test receipt")
        print(json.dumps(check(args.output.absolute(), args.tests.absolute()), sort_keys=True))
    elif args.action == "launch":
        ctx.need(args.checked is not None, "Missing source-bound software evidence")
        print(json.dumps(launch(args.output.absolute(), args.checked), sort_keys=True))
    else:
        ctx.need(args.registration_sha is not None, "Missing launch binding")
        if args.action == "worker":
            ctx.need(args.phase is not None, "Missing worker phase")
            worker(args.output.absolute(), args.registration_sha, args.phase)
        else:
            execute(args.output.absolute(), args.registration_sha)
