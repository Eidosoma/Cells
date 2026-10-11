"""Explicitly authorized sequence: saved-reference review, native, Cells, comparison."""

import argparse
import importlib
import json
import os
import resource
import signal
import subprocess
import sys
import time
import traceback
import warnings
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import timed_context as ctx

c, io = ctx.c, ctx.io


def register(output, tests):
    c.require(
        output.is_relative_to(ctx.ROOT / "runs")
        and output != ctx.ROOT / "runs"
        and not output.exists(),
        "Use fresh timed output",
    )
    plan = c.read(ctx.PLAN)
    ctx.validate_plan(plan)
    with ctx.model_fence():
        prerequisite = ctx.prerequisite()
    r = {
        "schema": "cells.betse_timed_release_registration@1",
        "registered_utc": datetime.now(UTC).isoformat(),
        "plan": plan,
        "prerequisite": prerequisite,
        "views": ctx.views(plan),
        "sources_sha256": ctx.sources(),
        "historical_reports_sha256": ctx.reports(),
        "tests": ctx.test_receipt(tests),
    }
    output.mkdir(parents=True, exist_ok=False)
    try:
        io.write(output / "registration.json", r)
        with zipfile.ZipFile(
            output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for name in r["sources_sha256"]:
                archive.write(ctx.ROOT / name, arcname=name)
        ctx.authenticate(output)
    except BaseException:
        io.write(
            output / "registration-failure.json",
            {
                "status": "registration_failed_not_launched",
                "traceback": traceback.format_exc(),
                "automatic_retry": False,
            },
        )
        raise
    return r


def allow_simulators(output, r):
    review = c.read(output / "reference-review.json")
    c.require(
        review["status"] == "piecewise_reference_review_closed"
        and review["independent"]["identities"] == r["plan"]["reference_review_identities"]
        and review["independent"]["column_mismatches"]
        == review["independent"]["independent_numerical_rejections"]
        == 0
        and review["reference_completion_sha256"] == ctx.REFERENCE_SHA,
        "Reference review did not pass",
    )
    io.write(
        output / "reference-review-passed.json",
        {
            "status": "pass",
            "registration_sha256": c.sha(output / "registration.json"),
            "reference_review_sha256": c.sha(output / "reference-review.json"),
            "simulators_allowed": True,
        },
    )


def require_gate(output, r):
    gate = c.read(output / "reference-review-passed.json")
    review = c.read(output / "reference-review.json")
    c.require(
        gate["status"] == "pass"
        and gate["simulators_allowed"] is True
        and gate["registration_sha256"] == c.sha(output / "registration.json")
        and gate["reference_review_sha256"] == c.sha(output / "reference-review.json")
        and review["status"] == "piecewise_reference_review_closed"
        and review["reference_completion_sha256"] == ctx.REFERENCE_SHA
        and review["independent"]["identities"] == r["plan"]["reference_review_identities"]
        and review["independent"]["column_mismatches"]
        == review["independent"]["independent_numerical_rejections"]
        == 0,
        "Reference review gate evidence differs",
    )


def worker(kind, output):
    c.require(kind in ("betse", "cells"), "Unknown timed worker")
    r = ctx.authenticate(output)
    require_gate(output, r)
    resource.setrlimit(resource.RLIMIT_FSIZE, (r["plan"]["resources"]["max_file_bytes"],) * 2)
    expected = c.REFERENCE_PYTHON if kind == "betse" else c.CELLS_PYTHON
    c.require(
        Path(sys.executable) == expected
        and sorted(os.sched_getaffinity(0)) == r["plan"]["resources"]["cpu_affinity"],
        "Timed worker interpreter/affinity",
    )
    numerical = {k: os.environ.get(k) for k in ("JAX_DISABLE_JIT", "XLA_FLAGS")}
    c.require(
        numerical
        == r["views"]["a"]["preparation_registration"]["cells_runtime"]["numerical_environment"],
        "Timed worker numerical environment",
    )
    began = time.monotonic()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        driver = importlib.import_module("timed_native" if kind == "betse" else "timed_cells")
        result = driver.worker(r, output)
    io.write(
        output / (kind + ".json"),
        result
        | {
            "registration_sha256": c.sha(output / "registration.json"),
            "elapsed_seconds": time.monotonic() - began,
            "environment": c.environment(),
            "cpu_affinity": sorted(os.sched_getaffinity(0)),
            "numerical_environment": numerical,
            "warnings": [
                {"category": w.category.__name__, "message": str(w.message)} for w in caught
            ],
        },
    )


def validate_worker(r, output, kind):
    row = c.read(output / (kind + ".json"))
    expected = c.REFERENCE_PYTHON if kind == "betse" else c.CELLS_PYTHON
    c.require(
        row["registration_sha256"] == c.sha(output / "registration.json")
        and row["warnings"] == []
        and Path(row["environment"]["executable"]) == expected
        and row["cpu_affinity"] == r["plan"]["resources"]["cpu_affinity"]
        and row["numerical_environment"]
        == r["views"]["a"]["preparation_registration"]["cells_runtime"]["numerical_environment"]
        and 0 < row["elapsed_seconds"] < r["plan"]["resources"]["worker_timeout_seconds"][kind],
        "Timed worker provenance",
    )
    if kind == "betse":
        expected_source = r["views"]["a"]["preparation_registration"]["upstream"]["files_sha256"]
        c.require(
            row["installed_python_sha256"]
            == {
                n: h
                for n, h in expected_source.items()
                if n.startswith("betse/") and n.endswith(".py")
            }
            and row["environment"]["packages"] == c.locked_reference_packages()
            and row["test_only_subset"] is False,
            "Native runtime/source",
        )
        c.require(
            all(row[k] == r["plan"][k] for k in ("native_runs", "native_updates", "observer_pairs"))
            and row["input_applications"] == r["plan"]["native_input_applications"],
            "Native worker coverage",
        )
    else:
        c.require(
            set(row["by_history"]) == set(r["views"])
            and row["cells_trajectories"] == r["plan"]["cells_trajectories"]
            and row["resumed_segments"] == r["plan"]["cells_resumed_segments"],
            "Cells worker coverage",
        )
        for history, view in r["views"].items():
            c.require(
                row["by_history"][history]["accepted_runtime"]
                == view["preparation_registration"]["cells_runtime"],
                "Cells runtime",
            )
    return row


def gated_sequence(review, release, verify, run, compare):
    checked = review()
    release()
    verify()
    native = run("betse")
    verify()
    cells = run("cells")
    return checked, compare(native, cells)


def alarm(_signal, _frame):
    raise TimeoutError("Timed release job deadline")


def execute(output):
    began, stage = time.monotonic(), "authentication"
    try:
        budget = c.read(ctx.PLAN)["resources"]
        signal.signal(signal.SIGALRM, alarm)
        signal.setitimer(signal.ITIMER_REAL, budget["total_timeout_seconds"])
        resource.setrlimit(resource.RLIMIT_FSIZE, (budget["max_file_bytes"],) * 2)
        with ctx.model_fence():
            r = ctx.authenticate(output)
            c.require(
                sorted(os.sched_getaffinity(0)) == budget["cpu_affinity"],
                "Timed controller affinity",
            )
            io.write(
                output / "started.json",
                {"pid": os.getpid(), "started_utc": datetime.now(UTC).isoformat()},
            )
            environment = ctx.feedback.audit.preparation.old.ctx.worker_environment(
                r["views"]["a"]["preparation_registration"], output
            )

            def review():
                nonlocal stage
                stage = "independent_saved_reference_review"
                from timed_reference_review import review as check

                value = check(output)
                io.write(output / "reference-review.json", value)
                return value

            def run(kind):
                nonlocal stage
                stage = kind
                remaining = budget["total_timeout_seconds"] - (time.monotonic() - began)
                c.require(remaining > 0, "No remaining worker budget")
                io.write(
                    output / (kind + "-started.json"),
                    {"started_utc": datetime.now(UTC).isoformat(), "reference_review_passed": True},
                )
                interpreter = c.REFERENCE_PYTHON if kind == "betse" else c.CELLS_PYTHON
                with (output / (kind + ".log")).open("x") as stream:
                    subprocess.run(
                        [
                            str(interpreter),
                            "-B",
                            str(Path(__file__).resolve()),
                            "worker",
                            kind,
                            str(output),
                        ],
                        cwd=ctx.ROOT,
                        env=environment,
                        stdin=subprocess.DEVNULL,
                        stdout=stream,
                        stderr=subprocess.STDOUT,
                        check=True,
                        timeout=min(remaining, budget["worker_timeout_seconds"][kind]),
                    )
                return validate_worker(r, output, kind)

            def compare(native, cells):
                nonlocal stage
                stage = "timed_state_accounting_refinement_and_contact"
                from timed_compare import check

                result = check(r, output, native, cells)
                io.write(output / "comparison.json", result)
                c.require(
                    result["status"] == "timed_release_capture_pass_pending_audit",
                    "Timed trajectory comparisons rejected",
                )
                return result

            reviewed, result = gated_sequence(
                review,
                lambda: allow_simulators(output, r),
                lambda: require_gate(output, r),
                run,
                compare,
            )
            stage = "final_authentication"
            ctx.authenticate(output)
            require_gate(output, r)
            hashes = ctx.packet_hashes(output)
            used = sum((output / name).stat().st_size for name in hashes)
            c.require(used + 131072 < budget["max_artifact_bytes"], "Timed artifact cap")
            elapsed = time.monotonic() - began
            c.require(elapsed < budget["total_timeout_seconds"], "Timed elapsed budget")
            io.write(
                output / "completion.json",
                result
                | {
                    "schema": "cells.betse_timed_release_capture@1",
                    "decision": "D105",
                    "finished_utc": datetime.now(UTC).isoformat(),
                    "elapsed_seconds": elapsed,
                    "registration_sha256": c.sha(output / "registration.json"),
                    "files_sha256": {n: h for n, h in hashes.items() if n not in ctx.OPERATIONAL},
                    "artifact_bytes_before_receipt": used,
                    "reference_review": reviewed["independent"],
                    "tests": r["tests"],
                    "production_changed": False,
                    "old_evidence_rewritten": False,
                    "automatic_polling": False,
                    "automatic_retry": False,
                    "automatic_followup": False,
                },
            )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        io.write(
            output / "failure.json",
            {
                "status": "timed_release_failed_not_qualified",
                "stage": stage,
                "elapsed_seconds": time.monotonic() - began,
                "traceback": traceback.format_exc(),
                "automatic_retry": False,
                "automatic_followup": False,
            },
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def launch(output, tests):
    r = register(output, tests)
    try:
        with (
            (output / "runner.stdout.log").open("x") as stdout,
            (output / "runner.stderr.log").open("x") as stderr,
        ):
            process = subprocess.Popen(
                [
                    "taskset",
                    "-c",
                    ",".join(map(str, r["plan"]["resources"]["cpu_affinity"])),
                    str(c.CELLS_PYTHON),
                    "-B",
                    str(Path(__file__).resolve()),
                    "execute",
                    str(output),
                ],
                cwd=ctx.ROOT,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
            )
        receipt = {
            "status": "launched_detached",
            "pid": process.pid,
            "launched_utc": datetime.now(UTC).isoformat(),
            "registration_sha256": c.sha(output / "registration.json"),
            "resources": r["plan"]["resources"],
            "reference_review_before_simulators": True,
            "automatic_polling": False,
            "automatic_retry": False,
            "automatic_followup": False,
        }
        io.write(output / "launch.json", receipt)
        return receipt
    except BaseException:
        io.write(
            output / "launch-failure.json",
            {"status": "launch_failed", "traceback": traceback.format_exc()},
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    start = sub.add_parser("launch")
    start.add_argument("output", type=Path)
    start.add_argument("--tests", type=Path, nargs="+", required=True)
    sub.add_parser("execute").add_argument("output", type=Path)
    child = sub.add_parser("worker")
    child.add_argument("kind", choices=("betse", "cells"))
    child.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.action == "launch":
        print(
            json.dumps(launch(args.output.resolve(), [p.resolve() for p in args.tests]), indent=2)
        )
    elif args.action == "execute":
        execute(args.output.resolve())
    else:
        worker(args.kind, args.output.resolve())
