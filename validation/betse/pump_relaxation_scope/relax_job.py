"""D130 source-bound closeout and one detached 10 ms reference-only study."""

import argparse
import json
import os
import resource
import shutil
import signal
import subprocess
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import relax_context as ctx
import relax_reference as reference

c, previous = ctx.c, ctx.previous
write = previous.write
REQUIRED = {
    "test_real_r0_authentication",
    "test_longer_reference_smoke",
    "test_scope_mutations",
    "test_reference_corruptions",
    "test_prefix_corruption",
    "test_worker_import_fence",
    "test_detached_launch",
    "test_child_timeout_cleanup",
    "test_registration_binding",
}


def receipt(path):
    c.need(path.is_relative_to(c.ROOT / "reports"), "Scoping receipt path")
    result = c.e.software(path, 40)
    cases = ET.parse(path).getroot().findall("testsuite/testcase")
    c.need(
        len(cases) == len({(v.get("classname"), v.get("name")) for v in cases}) == result["tests"]
        and all("test_relax_scope" in v.get("classname", "") for v in cases)
        and REQUIRED <= {v.get("name", "").split("[")[0] for v in cases},
        "Scoping software coverage",
    )
    return result


def check(output, tests):
    previous.fresh(output)
    c.need(tests.is_relative_to(c.ROOT / "reports") and not tests.exists(), "Fresh scoping XML")
    before, started = ctx.sources(), time.monotonic()
    output.mkdir(parents=True)
    write(output / "registration.json", dict(sources_sha256=before, test_timeout_seconds=60))
    previous.archive(output, before)
    try:
        with (
            (output / "tests.stdout.log").open("x") as out,
            (output / "tests.stderr.log").open("x") as err,
        ):
            run_child(
                [
                    str(c.ROOT / ".venv/bin/python"),
                    "-B",
                    "-m",
                    "pytest",
                    "-q",
                    "-W",
                    "error",
                    str(ctx.HERE / "test_relax_scope.py"),
                    "--junitxml=" + str(tests),
                    "--basetemp=" + str(output / "tests"),
                ],
                out,
                err,
                60,
            )
        software = receipt(tests)
        c.need(
            ctx.sources() == before and (output / "tests.stderr.log").read_bytes() == b"",
            "Scoping software context/stderr",
        )
        files, links = c.inventory(output, pytest_links=True)
        done = dict(
            status="reference_scoping_software_pass",
            sources_sha256=before,
            software=software,
            files_sha256=files,
            pytest_internal_links=links,
            elapsed_seconds=time.monotonic() - started,
            full_study_launched=False,
            automatic_followup=False,
        )
        write(output / "completion.json", done)
        return {k: done[k] for k in ("status", "software", "elapsed_seconds")}
    except BaseException:
        write(
            output / "failure.json",
            dict(status="software_failed", traceback=traceback.format_exc()),
        )
        raise


def software(path):
    c.need(
        path.is_relative_to(c.ROOT / "runs") and path.name == "completion.json",
        "Scoping software packet",
    )
    done, _ = c.packet(path.parent, path.name, c.sha(path), pytest_links=True)
    c.need(
        done["status"] == "reference_scoping_software_pass"
        and done["sources_sha256"] == ctx.sources()
        and done["full_study_launched"] is False
        and done["automatic_followup"] is False,
        "Scoping software binding",
    )
    c.capsule(path.parent, done["sources_sha256"])
    c.need(
        receipt(c.child(c.ROOT, done["software"]["path"])) == done["software"],
        "Scoping XML binding",
    )
    return dict(path=str(path.relative_to(c.ROOT)), sha256=c.sha(path), xml=done["software"])


def closeout(output, checked):
    previous.fresh(output)
    proof, sources = software(checked), ctx.sources()
    facts = ctx.authenticate_r0()
    output.mkdir(parents=True)
    try:
        write(
            output / "registration.json",
            dict(sources_sha256=sources, software=proof, review_completion_sha256=ctx.AUDIT_SHA),
        )
        previous.archive(output, sources)
        write(output / "closeout.json", facts)
        write(output / "resource-context.json", ctx.resource_context())
        write(output / "readiness.json", ctx.readiness(ctx.inherited()))
        c.need(sources == ctx.sources(), "Closeout sources changed")
        files, _ = c.inventory(output)
        write(
            output / "completion.json",
            dict(
                status="r0_closed_r1_reference_scoping_ready",
                created_utc=datetime.now(UTC).isoformat(),
                files_sha256=files,
                sources_sha256=sources,
                software=proof,
                audit_completion_sha256=ctx.AUDIT_SHA,
                native_runs=0,
                cells_runs=0,
                reference_solves=0,
                full_campaign_launched=False,
                automatic_followup=False,
            ),
        )
        return dict(
            status="r0_closed_r1_reference_scoping_ready",
            completion_sha256=c.sha(output / "completion.json"),
        )
    except BaseException:
        write(
            output / "failure.json",
            dict(status="closeout_failed", traceback=traceback.format_exc()),
        )
        raise


def closed(path):
    c.need(
        path.is_relative_to(c.ROOT / "runs") and path.name == "completion.json", "Closeout location"
    )
    done, _ = c.packet(path.parent, path.name, c.sha(path), count=5)
    c.need(
        done["status"] == "r0_closed_r1_reference_scoping_ready"
        and done["sources_sha256"] == ctx.sources()
        and done["audit_completion_sha256"] == ctx.AUDIT_SHA
        and done["reference_solves"] == 0
        and done["full_campaign_launched"] is False,
        "Closeout scope/binding",
    )
    c.capsule(path.parent, done["sources_sha256"])
    c.need(
        software(c.child(c.ROOT, done["software"]["path"])) == done["software"],
        "Closeout software binding",
    )
    c.need(
        c.read(path.parent / "closeout.json", None) == ctx.authenticate_r0(),
        "Reviewed evidence changed",
    )
    return dict(path=str(path.relative_to(c.ROOT)), sha256=c.sha(path))


def budget(output):
    limits = c.read(ctx.SCOPE)["bounds"]
    files, _ = c.inventory(output)
    sizes = [c.child(output, k).stat().st_size for k in files]
    c.need(all(n <= limits["per_file_bytes"] for n in sizes), "Reference file budget")
    c.need(sum(sizes) < limits["artifact_bytes"] - 1024**2, "Reference artifact budget")
    c.need(
        shutil.disk_usage(output).free >= limits["free_disk_reserve_bytes"],
        "Reference disk reserve",
    )
    return sum(sizes)


def register(output, closeout_path):
    previous.fresh(output)
    proof = closed(closeout_path)
    scope, old = c.read(ctx.SCOPE), ctx.inherited()
    plan, cases = ctx.preparation(scope, old)
    sources = ctx.sources()
    result = dict(
        schema="cells.pump_reference_scope_registration@1",
        decision="D130",
        registered_utc=datetime.now(UTC).isoformat(),
        scope=scope,
        protocol=plan,
        cases=cases,
        inherited_registration_sha256=c.sha(c.LEGACY / "registration.json"),
        inherited_reference_sha256=c.sha(c.LEGACY / "reference.json"),
        r0_closeout=proof,
        sources_sha256=sources,
        runtime=ctx.runtime(),
        reference_import_fence=list(ctx.FORBIDDEN_REFERENCE),
        native_runs=0,
        cells_runs=0,
        automatic_followup=False,
    )
    output.mkdir(parents=True)
    try:
        write(output / "registration.json", result)
        previous.archive(output, sources)
        budget(output)
    except BaseException:
        write(
            output / "registration-failure.json",
            dict(status="not_launched", traceback=traceback.format_exc()),
        )
        raise
    return result


def authenticate(output, expected_sha, *, full):
    c.need(c.sha(output / "registration.json") == expected_sha, "Scoping registration digest")
    r = c.read(output / "registration.json", None)
    scope, old = c.read(ctx.SCOPE), ctx.inherited()
    plan, cases = ctx.preparation(scope, old)
    c.need(
        r["schema"] == "cells.pump_reference_scope_registration@1"
        and r["decision"] == "D130"
        and r["scope"] == scope
        and r["protocol"] == plan
        and r["cases"] == cases
        and r["sources_sha256"] == ctx.sources()
        and r["runtime"] == ctx.runtime()
        and r["inherited_registration_sha256"] == c.sha(c.LEGACY / "registration.json")
        and r["inherited_reference_sha256"] == c.sha(c.LEGACY / "reference.json")
        and r["reference_import_fence"] == list(ctx.FORBIDDEN_REFERENCE)
        and r["native_runs"] == r["cells_runs"] == 0
        and r["automatic_followup"] is False,
        "Scoping registration context changed",
    )
    c.capsule(output, r["sources_sha256"])
    if full:
        c.need(
            closed(c.child(c.ROOT, r["r0_closeout"]["path"])) == r["r0_closeout"],
            "Changed R0 closeout",
        )
    return r


def deadline(seconds):
    def expired(_signal, _frame):
        raise TimeoutError("Reference-scoping deadline exceeded")

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)


def run_child(command, out, err, timeout):
    process = subprocess.Popen(
        command,
        cwd=c.ROOT,
        env=previous.environment(),
        stdin=subprocess.DEVNULL,
        stdout=out,
        stderr=err,
        start_new_session=True,
    )
    try:
        code = process.wait(timeout=timeout)
        if code:
            raise subprocess.CalledProcessError(code, command)
    except BaseException:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        raise


def worker(output, expected_sha):
    r = authenticate(output, expected_sha, full=False)
    limits = r["scope"]["bounds"]
    deadline(limits["worker_timeout_seconds"])
    resource.setrlimit(resource.RLIMIT_AS, (limits["worker_address_space_bytes"],) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (limits["per_file_bytes"],) * 2)
    c.need(sorted(os.sched_getaffinity(0)) == limits["cpu_affinity"], "Reference worker affinity")
    import warnings

    warnings.simplefilter("error")
    try:
        result = reference.run(r, output, write, budget)
        c.need(r["sources_sha256"] == ctx.sources(), "Reference sources changed during solve")
        result["worker_peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        write(output / "reference.json", result)
    except BaseException:
        write(
            output / "reference-failure.json",
            dict(status="reference_scope_failed", traceback=traceback.format_exc()),
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def gate(result, r, output):
    labels = sorted(
        f"{v}/{s['id']}"
        for v in r["scope"]["variants"]
        for s in r["protocol"]["reference"]["solves"]
    )
    c.need(
        result["status"] == "reference_10ms_scope_pass_pending_independent_review"
        and sorted(result["records"]) == labels
        and result["reference_solves"] == 18
        and result["agreement"]["status"] == "independent_reference_gate_pass",
        "Reference terminal coverage",
    )
    for name in (
        "native_ladder_qualified",
        "matched_10ms_qualified",
        "steady_state_qualified",
        "biology_validated",
        "production_changed",
        "automatic_followup",
    ):
        c.need(result[name] is False, "Expanded scoping result")
    c.need(result["native_runs"] == result["cells_runs"] == 0, "Unexpected simulator run")
    for label, row in result["records"].items():
        c.need(
            row["path"] == "reference/" + label + "/result.json"
            and c.sha(c.child(output, row["path"])) == row["sha256"]
            and row["prefix"]["compared_samples"] == 161,
            "Reference output link",
        )


def execute(output, expected_sha):
    c.need(
        output.is_relative_to(c.ROOT / "runs") and not (output / "started.json").exists(),
        "Scoping already attempted",
    )
    start = time.monotonic()
    deadline(c.read(ctx.SCOPE)["bounds"]["controller_timeout_seconds"])
    try:
        write(
            output / "started.json",
            dict(started_utc=datetime.now(UTC).isoformat(), pid=os.getpid()),
        )
        r = authenticate(output, expected_sha, full=True)
        c.need(
            sorted(os.sched_getaffinity(0)) == r["scope"]["bounds"]["cpu_affinity"],
            "Controller affinity",
        )
        with (
            (output / "reference.stdout.log").open("x") as out,
            (output / "reference.stderr.log").open("x") as err,
        ):
            run_child(
                [
                    str(c.ROOT / ".venv/bin/python"),
                    "-B",
                    str(Path(__file__).resolve()),
                    "worker",
                    str(output),
                    "--registration-sha",
                    expected_sha,
                ],
                out,
                err,
                r["scope"]["bounds"]["worker_timeout_seconds"],
            )
        c.need((output / "reference.stderr.log").read_bytes() == b"", "Reference stderr")
        result = c.read(output / "reference.json", None)
        gate(result, r, output)
        authenticate(output, expected_sha, full=True)
        used = budget(output)
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
                finished_utc=datetime.now(UTC).isoformat(),
                elapsed_seconds=time.monotonic() - start,
                files_sha256=files,
                artifact_bytes_before_completion=used,
                reference_sha256=c.sha(output / "reference.json"),
                **{k: v for k, v in result.items() if k not in ("status", "records")},
            ),
        )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        write(
            output / "failure.json",
            dict(
                status="reference_scoping_failed_not_qualified",
                elapsed_seconds=time.monotonic() - start,
                traceback=traceback.format_exc(),
                automatic_retry=False,
                automatic_followup=False,
            ),
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def launch(output, closeout_path):
    register(output, closeout_path)
    expected_sha = c.sha(output / "registration.json")
    try:
        with (
            (output / "runner.stdout.log").open("x") as out,
            (output / "runner.stderr.log").open("x") as err,
        ):
            p = subprocess.Popen(
                [
                    "taskset",
                    "-c",
                    "0-3",
                    str(c.ROOT / ".venv/bin/python"),
                    "-B",
                    str(Path(__file__).resolve()),
                    "execute",
                    str(output),
                    "--registration-sha",
                    expected_sha,
                ],
                cwd=c.ROOT,
                env=previous.environment(),
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                start_new_session=True,
            )
        ack = dict(
            status="launched_detached",
            pid=p.pid,
            registration_sha256=expected_sha,
            launched_utc=datetime.now(UTC).isoformat(),
            automatic_polling=False,
        )
        write(output / "launch.json", ack)
        return ack
    except BaseException:
        write(
            output / "launch-failure.json",
            dict(status="not_launched", traceback=traceback.format_exc()),
        )
        raise


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("check", "closeout", "launch", "execute", "worker"))
    p.add_argument("output", type=Path)
    p.add_argument("--tests", type=Path)
    p.add_argument("--software", type=Path)
    p.add_argument("--closeout", type=Path)
    p.add_argument("--registration-sha")
    args = p.parse_args()
    output = args.output.absolute()
    required = dict(
        check="tests",
        closeout="software",
        launch="closeout",
        execute="registration_sha",
        worker="registration_sha",
    )[args.action]
    if getattr(args, required) is None:
        p.error("--" + required.replace("_", "-") + " required")
    if args.action == "check":
        print(json.dumps(check(output, args.tests.absolute()), sort_keys=True))
    elif args.action == "closeout":
        print(json.dumps(closeout(output, args.software.absolute()), sort_keys=True))
    elif args.action == "launch":
        print(json.dumps(launch(output, args.closeout.absolute()), sort_keys=True))
    elif args.action == "execute":
        execute(output, args.registration_sha)
    else:
        worker(output, args.registration_sha)
