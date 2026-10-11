"""Detached, read-only diagnosis of a sealed pump-only refinement miss."""

import argparse
import json
import os
import resource
import shutil
import signal
import subprocess
import sys
import time
import traceback
import warnings
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pump_relaxation_matched"))
import matched_job as prior  # noqa: E402

c, helpers, write, ROOT = prior.c, prior.helpers, prior.write, prior.ROOT
CAPTURE = ROOT / "runs/ref-005e-matched-10ms-2026-09-17/campaign-01"
REG_SHA = "4d62da1d279ecdc9b51ce06653e151e51e344dbe2ec0f93be5f892aad9293567"
DONE_SHA = "b1370c34ba9875b2f3d2a52b90803773552cef9eea0169e01a262723c0573cfc"
REFERENCE = prior.old.old.REFERENCE
STEPS, PRECISION = list(prior.STEPS), 80
SOURCE = ROOT / "upstream/betse-v1.5.0"
SOURCE_PATHS = [SOURCE / "betse/science/sim.py", SOURCE / "betse/science/sim_toolbox.py"]
SCOPE = dict(
    purpose="Separate bath storage arithmetic from recorded transfers; no acceptance change",
    variant="pump_only",
    duration_s=0.01,
    steps_s=STEPS,
    rows=3,
    updates=44800,
    species=["Na", "K", "Cl"],
    decimal_precision=PRECISION,
    exact_bath_scalar_matches=4032000,
    cpu_affinity=[0, 1, 2, 3],
    worker_seconds=900,
    controller_seconds=1200,
    worker_address_space_bytes=4 * 1024**3,
    per_file_bytes=16 * 1024**2,
    artifact_bytes=64 * 1024**2,
    free_disk_reserve_bytes=1024**3,
    new_simulator_runs=0,
    new_reference_integrations=0,
    physics_changed=False,
    scientific_tolerances_changed=False,
    original_convergence_verdict_changed=False,
    automatic_polling=False,
    automatic_retry=False,
    automatic_followup=False,
)


def sources():
    names = set(prior.sources()) | {str(p.relative_to(ROOT)) for p in HERE.glob("*.py")}
    names.update(str(p.relative_to(ROOT)) for p in SOURCE_PATHS)
    return {n: c.sha(c.child(ROOT, n)) for n in sorted(names)}


def links():
    return dict(
        directory=str(CAPTURE.relative_to(ROOT)),
        registration_sha256=REG_SHA,
        completion_sha256=DONE_SHA,
        comparison_sha256=c.sha(CAPTURE / "comparison.json"),
        reference_completion_sha256=c.sha(REFERENCE / "completion.json"),
        upstream_sha256={str(p.relative_to(ROOT)): c.sha(p) for p in SOURCE_PATHS},
    )


def inputs():
    prior.authenticate(CAPTURE, REG_SHA)
    prior.prerequisites()
    done, _ = c.packet(
        CAPTURE,
        "completion.json",
        DONE_SHA,
        extras=("launch.json", "runner.stdout.log", "runner.stderr.log"),
        count=18385,
    )
    result = c.read(CAPTURE / "comparison.json", None)
    c.need(
        done["status"] == "matched_10ms_numerical_miss_not_qualified"
        and done["producer_passed"] is result["producer_passed"] is False,
        "Preserve failed campaign disposition",
    )
    failures = [
        (case, field)
        for case, value in result["cases"].items()
        for field, value in value["refinement"].items()
        if not value["passed"]
    ]
    c.need(
        failures == [("pump_only", "amount")]
        and result["cells_checks"]["passed"]
        and all(v["cross_engine"]["failed_comparisons"] == 0 for v in result["cases"].values()),
        "Unexpected diagnostic target",
    )
    for phase in ("cells", "native", "comparison"):
        prior.stderr_check(phase, (CAPTURE / (phase + ".stderr.log")).read_text())
    expected = prior.ctx.inherited()["native_preparation"]["upstream"]["files_sha256"]
    c.need(
        all(c.sha(p) == expected[str(p.relative_to(SOURCE))] for p in SOURCE_PATHS),
        "Pinned arithmetic source",
    )
    return links()


def receipt(path):
    c.need(path.is_relative_to(ROOT / "reports"), "Test receipt location")
    result = c.e.software(path, 12)
    cases = ET.parse(path).getroot().findall("testsuite/testcase")
    required = {
        "test_saved_coordinates",
        "test_recorded_replay",
        "test_decimal_precision",
        "test_corrupted_record",
        "test_binding",
        "test_detached",
        "test_failed_child",
    }
    c.need(
        required <= {v.get("name", "").split("[")[0] for v in cases}
        and all("test_diagnosis" in v.get("classname", "") for v in cases),
        "Test coverage",
    )
    return result


def check(output, xml):
    helpers.previous.fresh(output)
    c.need(xml.is_relative_to(ROOT / "reports") and not xml.exists(), "Fresh test receipt")
    before, start = sources(), time.monotonic()
    output.mkdir(parents=True)
    write(output / "registration.json", dict(sources_sha256=before))
    helpers.previous.archive(output, before)
    try:
        with (
            (output / "tests.stdout.log").open("x") as out,
            (output / "tests.stderr.log").open("x") as err,
        ):
            helpers.run_child(
                [
                    str(ROOT / ".venv/bin/python"),
                    "-B",
                    "-m",
                    "pytest",
                    "-q",
                    "-W",
                    "error",
                    str(HERE / "test_diagnosis.py"),
                    "--junitxml=" + str(xml),
                    "--basetemp=" + str(output / "tests"),
                ],
                out,
                err,
                60,
            )
        tested = receipt(xml)
        c.need(
            before == sources() and (output / "tests.stderr.log").read_bytes() == b"",
            "Test context",
        )
        files, aliases = c.inventory(output, pytest_links=True)
        result = dict(
            status="bath_diagnosis_software_pass",
            sources_sha256=before,
            software=tested,
            files_sha256=files,
            pytest_internal_links=aliases,
            elapsed_seconds=time.monotonic() - start,
        )
        write(output / "completion.json", result)
        return {k: result[k] for k in ("status", "software", "elapsed_seconds")}
    except BaseException:
        write(
            output / "failure.json",
            dict(status="software_failed", traceback=traceback.format_exc()),
        )
        raise


def software(path):
    c.need(
        path.is_relative_to(ROOT / "runs") and path.name == "completion.json", "Software location"
    )
    done, _ = c.packet(path.parent, path.name, c.sha(path), pytest_links=True)
    c.need(
        done["status"] == "bath_diagnosis_software_pass" and done["sources_sha256"] == sources(),
        "Software/source binding",
    )
    c.capsule(path.parent, done["sources_sha256"])
    c.need(
        receipt(c.child(ROOT, done["software"]["path"])) == done["software"], "Software XML binding"
    )
    return dict(path=str(path.relative_to(ROOT)), sha256=c.sha(path), xml=done["software"])


def budget(output):
    files, _ = c.inventory(output)
    sizes = [(output / name).stat().st_size for name in files]
    c.need(
        all(n <= SCOPE["per_file_bytes"] for n in sizes)
        and sum(sizes) < SCOPE["artifact_bytes"] - 1024**2
        and shutil.disk_usage(output).free >= SCOPE["free_disk_reserve_bytes"],
        "Diagnosis disk bounds",
    )


def register(output, proof):
    helpers.previous.fresh(output)
    checked, inherited = software(proof), inputs()
    output.mkdir(parents=True)
    frozen = sources()
    write(
        output / "registration.json",
        dict(
            schema="cells.saved_bath_diagnosis@1",
            scope=SCOPE,
            input=inherited,
            software=checked,
            sources_sha256=frozen,
            runtime=prior.ctx.runtime(),
            registered_utc=datetime.now(UTC).isoformat(),
        ),
    )
    helpers.previous.archive(output, frozen)
    budget(output)


def authenticate(output, digest):
    c.need(c.sha(output / "registration.json") == digest, "Registration digest")
    r = c.read(output / "registration.json", None)
    c.need(
        r["schema"] == "cells.saved_bath_diagnosis@1"
        and r["scope"] == SCOPE
        and r["input"] == links()
        and r["sources_sha256"] == sources()
        and r["runtime"] == prior.ctx.runtime()
        and c.sha(CAPTURE / "completion.json") == DONE_SHA
        and c.sha(CAPTURE / "registration.json") == REG_SHA,
        "Diagnosis scope/input/runtime",
    )
    c.capsule(output, r["sources_sha256"])
    c.need(software(c.child(ROOT, r["software"]["path"])) == r["software"], "Test binding")
    return r


def gate(result):
    c.need(
        result["status"] == "saved_bath_arithmetic_replayed"
        and result["recorded_updates"] == SCOPE["updates"]
        and result["exact_bath_scalar_matches"] == SCOPE["exact_bath_scalar_matches"]
        and [v["dt_s"] for v in result["rows"]] == STEPS
        and result["new_simulator_runs"] == result["new_reference_integrations"] == 0
        and result["original_convergence_verdict_changed"] is False
        and result["matched_10ms_qualified"] is False,
        "Replay coverage/scope",
    )


def worker(output, digest):
    authenticate(output, digest)
    helpers.deadline(SCOPE["worker_seconds"])
    try:
        resource.setrlimit(resource.RLIMIT_AS, (SCOPE["worker_address_space_bytes"],) * 2)
        resource.setrlimit(resource.RLIMIT_FSIZE, (SCOPE["per_file_bytes"],) * 2)
        c.need(sorted(os.sched_getaffinity(0)) == SCOPE["cpu_affinity"], "CPU affinity")
        warnings.simplefilter("error")
        import bath_diagnosis

        result = bath_diagnosis.run(output, write)
        gate(result)
        result["worker_peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        write(output / "diagnosis.json", result)
        budget(output)
    except BaseException:
        write(
            output / "worker-failure.json",
            dict(status="replay_failed", traceback=traceback.format_exc()),
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def execute(output, digest):
    c.need(not (output / "started.json").exists(), "Diagnosis already attempted")
    start = time.monotonic()
    helpers.deadline(SCOPE["controller_seconds"])
    try:
        write(
            output / "started.json",
            dict(pid=os.getpid(), started_utc=datetime.now(UTC).isoformat()),
        )
        r = authenticate(output, digest)
        c.need(inputs() == r["input"], "Changed input packet")
        with (
            (output / "replay.stdout.log").open("x") as out,
            (output / "replay.stderr.log").open("x") as err,
        ):
            helpers.run_child(
                [
                    str(ROOT / ".venv/bin/python"),
                    "-B",
                    str(Path(__file__).resolve()),
                    "worker",
                    str(output),
                    "--registration-sha",
                    digest,
                ],
                out,
                err,
                SCOPE["worker_seconds"],
            )
        c.need((output / "replay.stderr.log").read_bytes() == b"", "Unexpected replay stderr")
        result = c.read(output / "diagnosis.json", None)
        gate(result)
        authenticate(output, digest)
        c.need(inputs() == r["input"], "Changed saved evidence")
        budget(output)
        files, _ = c.inventory(output)
        files = {
            k: v
            for k, v in files.items()
            if k not in ("launch.json", "runner.stdout.log", "runner.stderr.log")
        }
        write(
            output / "completion.json",
            dict(
                status=result["status"],
                files_sha256=files,
                elapsed_seconds=time.monotonic() - start,
                finished_utc=datetime.now(UTC).isoformat(),
                new_simulator_runs=0,
                original_convergence_verdict_changed=False,
                matched_10ms_qualified=False,
                automatic_followup=False,
            ),
        )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        write(
            output / "failure.json",
            dict(
                status="diagnosis_failed",
                traceback=traceback.format_exc(),
                elapsed_seconds=time.monotonic() - start,
                automatic_retry=False,
                automatic_followup=False,
            ),
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def launch(output, proof):
    register(output, proof)
    try:
        digest = c.sha(output / "registration.json")
        with (
            (output / "runner.stdout.log").open("x") as out,
            (output / "runner.stderr.log").open("x") as err,
        ):
            child = subprocess.Popen(
                [
                    "taskset",
                    "-c",
                    "0-3",
                    str(ROOT / ".venv/bin/python"),
                    "-B",
                    str(Path(__file__).resolve()),
                    "execute",
                    str(output),
                    "--registration-sha",
                    digest,
                ],
                cwd=ROOT,
                env=helpers.previous.environment(),
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                start_new_session=True,
            )
        result = dict(
            status="launched_detached",
            pid=child.pid,
            registration_sha256=digest,
            launched_utc=datetime.now(UTC).isoformat(),
            automatic_polling=False,
        )
        write(output / "launch.json", result)
        return result
    except BaseException:
        write(
            output / "launch-failure.json",
            dict(status="launch_failed", traceback=traceback.format_exc()),
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "launch", "execute", "worker"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--tests", type=Path)
    parser.add_argument("--software", type=Path)
    parser.add_argument("--registration-sha")
    args = parser.parse_args()
    required = dict(
        check="tests", launch="software", execute="registration_sha", worker="registration_sha"
    )[args.action]
    if getattr(args, required) is None:
        parser.error("Missing " + required)
    output = args.output.absolute()
    if args.action == "check":
        print(json.dumps(check(output, args.tests.absolute()), sort_keys=True))
    elif args.action == "launch":
        print(json.dumps(launch(output, args.software.absolute()), sort_keys=True))
    elif args.action == "execute":
        execute(output, args.registration_sha)
    else:
        worker(output, args.registration_sha)
