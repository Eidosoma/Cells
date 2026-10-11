"""Source-bound checks and one detached read-only numerical review, with no polling."""

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

import review_context as ctx
import saved_review

c, e, util, write = ctx.c, ctx.e, ctx.util, ctx.util.write
BOUNDS = dict(
    cpu_affinity=[0, 1, 2, 3],
    timeout_seconds=21600,
    address_space_bytes=16 * 1024**3,
    per_file_bytes=64 * 1024**2,
    artifact_bytes=256 * 1024**2,
    free_disk_reserve_bytes=1024**3,
)
REQUIRED = {
    "test_contract",
    "test_row_selection",
    "test_real_stream",
    "test_saved_updates",
    "test_saved_cells",
    "test_conclusion",
    "test_import_fence",
    "test_binding",
    "test_detached",
    "test_failure",
    "test_completion",
}


def receipt(path):
    c.need(path.is_relative_to(ctx.ROOT / "reports"), "Review receipt path")
    result = e.software(path, 20)
    cases = ET.parse(path).getroot().findall("testsuite/testcase")
    c.need(
        REQUIRED <= {v.get("name", "").split("[")[0] for v in cases}
        and all("test_review" in v.get("classname", "") for v in cases),
        "Review test coverage",
    )
    return result


def check(output, tests):
    util.fresh(output)
    c.need(tests.is_relative_to(ctx.ROOT / "reports") and not tests.exists(), "Fresh review XML")
    frozen, start = ctx.sources(), time.monotonic()
    output.mkdir(parents=True)
    write(output / "registration.json", dict(sources_sha256=frozen))
    util.archive(output, frozen)
    try:
        with (
            (output / "tests.stdout.log").open("x") as out,
            (output / "tests.stderr.log").open("x") as err,
        ):
            subprocess.run(
                [
                    str(ctx.ROOT / ".venv/bin/python"),
                    "-B",
                    "-m",
                    "pytest",
                    "-q",
                    "-W",
                    "error",
                    str(ctx.HERE / "test_review.py"),
                    "--junitxml=" + str(tests),
                    "--basetemp=" + str(output / "tests"),
                ],
                cwd=ctx.ROOT,
                env=util.environment(),
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                timeout=60,
                check=True,
            )
        proof = receipt(tests)
        c.need(
            frozen == ctx.sources() and (output / "tests.stderr.log").read_bytes() == b"",
            "Review test context",
        )
        files, aliases = c.inventory(output, pytest_links=True)
        result = dict(
            status="saved_review_software_pass",
            sources_sha256=frozen,
            software=proof,
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
        path.is_relative_to(ctx.ROOT / "runs") and path.name == "completion.json", "Software path"
    )
    done, _ = c.packet(path.parent, path.name, c.sha(path), pytest_links=True)
    c.need(
        done["status"] == "saved_review_software_pass" and done["sources_sha256"] == ctx.sources(),
        "Review software/source binding",
    )
    c.capsule(path.parent, done["sources_sha256"])
    c.need(receipt(c.child(ctx.ROOT, done["software"]["path"])) == done["software"], "XML binding")
    return dict(path=str(path.relative_to(ctx.ROOT)), sha256=c.sha(path), xml=done["software"])


def budget(output):
    files, _ = c.inventory(output)
    sizes = [(output / name).stat().st_size for name in files]
    c.need(
        all(n <= BOUNDS["per_file_bytes"] for n in sizes)
        and sum(sizes) < BOUNDS["artifact_bytes"] - 1024**2
        and shutil.disk_usage(output).free >= BOUNDS["free_disk_reserve_bytes"],
        "Review disk bounds",
    )


def register(output, proof):
    util.fresh(output)
    checked = software(proof)
    with e.model_fence():
        inputs = ctx.authenticate_inputs()
    output.mkdir(parents=True)
    sources = ctx.sources()
    write(
        output / "registration.json",
        dict(
            schema="cells.saved_relaxation_review@1",
            scope=ctx.SCOPE,
            bounds=BOUNDS,
            rows=ctx.rows(),
            inputs=inputs,
            sources_sha256=sources,
            software=checked,
            python=sys.version,
            registered_utc=datetime.now(UTC).isoformat(),
        ),
    )
    util.archive(output, sources)
    budget(output)


def authenticate(output, digest):
    c.need(c.sha(output / "registration.json") == digest, "Review registration digest")
    r = c.read(output / "registration.json", None)
    c.need(
        r["schema"] == "cells.saved_relaxation_review@1"
        and r["scope"] == ctx.SCOPE
        and r["bounds"] == BOUNDS
        and r["rows"] == ctx.rows()
        and r["sources_sha256"] == ctx.sources()
        and r["python"] == sys.version,
        "Review scope/source/runtime binding",
    )
    c.capsule(output, r["sources_sha256"])
    c.need(software(c.child(ctx.ROOT, r["software"]["path"])) == r["software"], "Review software")
    c.need(ctx.authenticate_inputs() == r["inputs"], "Review input binding")
    return r


def execute(output, digest):
    c.need(not (output / "started.json").exists(), "Review already attempted")
    start = time.monotonic()

    def expired(*_):
        raise TimeoutError("Saved review exceeded its six-hour hard cap")

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, BOUNDS["timeout_seconds"])
    try:
        write(
            output / "started.json",
            dict(pid=os.getpid(), started_utc=datetime.now(UTC).isoformat()),
        )
        c.need(sorted(os.sched_getaffinity(0)) == BOUNDS["cpu_affinity"], "Review CPU affinity")
        resource.setrlimit(resource.RLIMIT_AS, (BOUNDS["address_space_bytes"],) * 2)
        resource.setrlimit(resource.RLIMIT_FSIZE, (BOUNDS["per_file_bytes"],) * 2)
        warnings.simplefilter("error")
        with e.model_fence():
            authenticate(output, digest)
            result = saved_review.run(output, write, budget)
            c.need(
                result["passed"] is True
                and result["matched_10ms_qualified"] is True
                and result["failed_comparisons"] == 0
                and len(result["refinements"]) == 36
                and all(v["passed"] for v in result["refinements"].values()),
                "Independent rejection",
            )
            authenticate(output, digest)
        budget(output)
        files, _ = c.inventory(output)
        write(
            output / "completion.json",
            dict(
                status="case_specific_10ms_numerics_independently_reviewed",
                elapsed_seconds=time.monotonic() - start,
                finished_utc=datetime.now(UTC).isoformat(),
                files_sha256={n: h for n, h in files.items() if n not in ctx.EXTRAS},
                reviewer_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                native_rows=18,
                native_observed_steps=235200,
                finest_observer_pairs=6,
                decoded_cells_trajectories=24,
                full_state_restart_suffixes=6,
                checkpoint_links=6,
                matched_10ms_qualified=True,
                qualification_scope="case-specific native timesteps",
                original_common_range_passed=False,
                original_verdict_changed=False,
                physics_rerun=False,
                scientific_tolerances_changed=False,
                production_changed=False,
                biology_validated=False,
                gpu_tested=False,
                full_betse_parity=False,
                steady_state_qualified=False,
                automatic_followup=False,
            ),
        )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        write(
            output / "failure.json",
            dict(
                status="independent_review_failed_not_qualified",
                elapsed_seconds=time.monotonic() - start,
                traceback=traceback.format_exc(),
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
                    str(ctx.ROOT / ".venv/bin/python"),
                    "-B",
                    str(Path(__file__).resolve()),
                    "execute",
                    str(output),
                    "--registration-sha",
                    digest,
                ],
                cwd=ctx.ROOT,
                env=util.environment(),
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
            dict(status="not_launched", traceback=traceback.format_exc()),
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "launch", "execute"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--tests", type=Path)
    parser.add_argument("--software", type=Path)
    parser.add_argument("--registration-sha")
    args = parser.parse_args()
    needed = dict(check="tests", launch="software", execute="registration_sha")[args.action]
    if getattr(args, needed) is None:
        parser.error("Missing input for " + args.action)
    if args.action == "check":
        print(json.dumps(check(args.output.absolute(), args.tests.absolute()), sort_keys=True))
    elif args.action == "launch":
        print(json.dumps(launch(args.output.absolute(), args.software.absolute()), sort_keys=True))
    else:
        execute(args.output.absolute(), args.registration_sha)
