"""One registered detached workflow: references must pass before native/Cells runs."""

import argparse
import importlib
import json
import os
import platform
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

import paired_context as ctx

c, io = ctx.c, ctx.io


def register(output, tests):
    c.require(
        output.is_relative_to(ctx.ROOT / "runs")
        and output != ctx.ROOT / "runs"
        and not output.exists(),
        "Use a fresh paired capture directory",
    )
    protocol = c.read(ctx.PROTOCOL)
    ctx.validate_protocol(protocol)
    with ctx.previous.prior.model_fence():
        prerequisite, _prepared = ctx.review.authenticate_review()
    r = {
        "schema": "cells.betse_paired_history_registration@1",
        "registered_utc": datetime.now(UTC).isoformat(),
        "protocol": protocol,
        "prerequisite": prerequisite,
        "views": ctx.views(protocol),
        "reference_runtime": ctx.feedback.reference_runtime(),
        "sources_sha256": ctx.sources(),
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
    gate = c.read(output / "reference-gate.json")
    c.require(
        gate["status"] == "pass"
        and gate["simulators_allowed"] is True
        and gate["selected_duration_s"] == r["protocol"]["candidate_duration_s"]
        and gate["reference_solves"] == r["protocol"]["reference_solves"],
        "Paired references did not pass",
    )
    files = {"reference.json", "reference-gate.json"}
    for name in r["views"]:
        files.add(name + "/reference-gate.json.gz")
        files.update(
            str(p.relative_to(output)) for p in (output / name / "reference").rglob("*.gz")
        )
    io.write(
        output / "reference-gate-passed.json",
        {
            "status": "pass",
            "registration_sha256": c.sha(output / "registration.json"),
            "reference_files_sha256": {name: c.sha(output / name) for name in sorted(files)},
        },
    )


def require_gate(output, r):
    receipt = c.read(output / "reference-gate-passed.json")
    c.require(
        receipt["status"] == "pass"
        and receipt["registration_sha256"] == c.sha(output / "registration.json")
        and all(c.sha(output / name) == h for name, h in receipt["reference_files_sha256"].items()),
        "Reference gate evidence changed",
    )
    gate = c.read(output / "reference-gate.json")
    expected = {"reference.json", "reference-gate.json"}
    for name, view in r["views"].items():
        expected.add(name + "/reference-gate.json.gz")
        expected |= {
            name + "/reference/" + variant + "/" + setting["id"] + "/result.json.gz"
            for variant in view["protocol"]["variants"]
            for setting in view["protocol"]["reference"]["solves"]
        }
    c.require(
        set(receipt["reference_files_sha256"]) == expected
        and gate["status"] == "pass"
        and gate["simulators_allowed"] is True
        and gate["selected_duration_s"] == r["protocol"]["candidate_duration_s"]
        and gate["reference_solves"] == r["protocol"]["reference_solves"],
        "Reference gate scope/membership differs",
    )


def worker(kind, output):
    r = ctx.authenticate(output)
    budget = r["protocol"]["resources"]
    resource.setrlimit(resource.RLIMIT_FSIZE, (budget["max_file_bytes"],) * 2)
    c.require(sorted(os.sched_getaffinity(0)) == budget["cpu_affinity"], "Worker CPU affinity")
    numerical = {k: os.environ.get(k) for k in ("JAX_DISABLE_JIT", "XLA_FLAGS")}
    runtime = r["views"]["a"]["preparation_registration"]["cells_runtime"]
    c.require(numerical == runtime["numerical_environment"], "Worker numerical environment")
    if kind != "reference":
        require_gate(output, r)
    interpreter = {
        "reference": ctx.feedback.REFERENCE_PYTHON,
        "betse": c.REFERENCE_PYTHON,
        "cells": c.CELLS_PYTHON,
    }[kind]
    c.require(Path(sys.executable) == interpreter, "Wrong worker interpreter")
    if kind == "reference":
        c.require(
            platform.python_version() == r["reference_runtime"]["python"]
            and c.environment()["packages"] == r["reference_runtime"]["packages"],
            "Independent reference runtime differs",
        )
    began = time.monotonic()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        driver = importlib.import_module("paired_workers")
        result = driver.worker(kind, r, output)
    io.write(
        output / f"{kind}.json",
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
    row = c.read(output / f"{kind}.json")
    expected_python = {
        "reference": ctx.feedback.REFERENCE_PYTHON,
        "betse": c.REFERENCE_PYTHON,
        "cells": c.CELLS_PYTHON,
    }[kind]
    c.require(
        row["registration_sha256"] == c.sha(output / "registration.json")
        and row["warnings"] == []
        and Path(row["environment"]["executable"]) == expected_python
        and row["cpu_affinity"] == r["protocol"]["resources"]["cpu_affinity"]
        and row["numerical_environment"]
        == r["views"]["a"]["preparation_registration"]["cells_runtime"]["numerical_environment"]
        and 0 < row["elapsed_seconds"] < r["protocol"]["resources"]["worker_timeout_seconds"][kind]
        and set(row["by_history"]) == set(row["history_ids"]) == set(r["views"]),
        "Worker provenance, scope, warnings or elapsed budget",
    )
    if kind == "reference":
        c.require(
            row["environment"]["packages"] == r["reference_runtime"]["packages"]
            and sum(v["reference_solves"] for v in row["by_history"].values())
            == r["protocol"]["reference_solves"],
            "Reference runtime/solve count",
        )
    elif kind == "betse":
        expected = {
            n: h
            for n, h in r["views"]["a"]["preparation_registration"]["upstream"][
                "files_sha256"
            ].items()
            if n.startswith("betse/") and n.endswith(".py")
        }
        c.require(
            all(v["installed_python_sha256"] == expected for v in row["by_history"].values())
            and row["environment"]["packages"] == c.locked_reference_packages(),
            "Native identity",
        )
        for field in ("native_runs", "native_updates"):
            c.require(
                sum(v[field] for v in row["by_history"].values()) == r["protocol"][field],
                "Native count",
            )
    else:
        c.require(
            all(
                v["accepted_runtime"]
                == r["views"][name]["preparation_registration"]["cells_runtime"]
                for name, v in row["by_history"].items()
            ),
            "Cells runtime",
        )
        c.require(
            sum(v["cells_trajectories"] for v in row["by_history"].values())
            == r["protocol"]["cells_trajectories"]
            and sum(v["resumed_segments"] for v in row["by_history"].values())
            == r["protocol"]["cells_resumed_segments"],
            "Cells trajectory/restart counts",
        )
    return row


def gated_sequence(run_worker, check_references, release, verify):
    """Explicitly requested steps 2 then 3; never continue after a failed gate."""
    reference = run_worker("reference")
    checked = check_references(reference)
    release()
    verify()
    native = run_worker("betse")
    verify()
    cells = run_worker("cells")
    return checked, native, cells


def alarm(_signum, _frame):
    raise TimeoutError("Paired history workflow exceeded its registered deadline")


def execute(output):
    began, stage = time.monotonic(), "authentication"
    try:
        budget = c.read(ctx.PROTOCOL)["resources"]
        signal.signal(signal.SIGALRM, alarm)
        signal.setitimer(signal.ITIMER_REAL, budget["total_timeout_seconds"])
        resource.setrlimit(resource.RLIMIT_FSIZE, (budget["max_file_bytes"],) * 2)
        r = ctx.authenticate(output)
        c.require(
            sorted(os.sched_getaffinity(0)) == budget["cpu_affinity"], "Controller CPU affinity"
        )
        io.write(
            output / "started.json",
            {"pid": os.getpid(), "started_utc": datetime.now(UTC).isoformat()},
        )
        environment = ctx.feedback.audit.preparation.old.ctx.worker_environment(
            r["views"]["a"]["preparation_registration"], output
        )

        def run(kind):
            nonlocal stage
            stage = kind
            remaining = budget["total_timeout_seconds"] - (time.monotonic() - began)
            c.require(remaining > 0, "No remaining capture budget")
            io.write(
                output / f"{kind}-started.json",
                {
                    "started_utc": datetime.now(UTC).isoformat(),
                    "reference_gate_passed": kind != "reference",
                },
            )
            interpreter = {
                "reference": ctx.feedback.REFERENCE_PYTHON,
                "betse": c.REFERENCE_PYTHON,
                "cells": c.CELLS_PYTHON,
            }[kind]
            with (output / f"{kind}.log").open("x") as stream:
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

        def references(aggregate):
            nonlocal stage
            stage = "paired_reference_convergence_and_signal_gate"
            with ctx.previous.prior.model_fence():
                from paired_compare import references as check

                return check(r, output, aggregate)

        checked, native, cells = gated_sequence(
            run, references, lambda: allow_simulators(output, r), lambda: require_gate(output, r)
        )
        stage = "coupled_state_refinement_restart_and_history_comparison"
        with ctx.previous.prior.model_fence():
            from paired_compare import check

            result = check(r, output, checked, native, cells)
        io.write(output / "comparison.json", result)
        c.require(
            result["status"] == "paired_capture_pass_pending_audit", "Paired comparison failed"
        )
        stage = "final_authentication"
        ctx.authenticate(output)
        require_gate(output, r)
        used = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
        c.require(used + 131072 < budget["max_artifact_bytes"], "Capture artifact budget")
        elapsed = time.monotonic() - began
        c.require(elapsed < budget["total_timeout_seconds"], "Capture deadline")
        io.write(
            output / "completion.json",
            result
            | {
                "schema": "cells.betse_paired_history_capture@1",
                "finished_utc": datetime.now(UTC).isoformat(),
                "elapsed_seconds": elapsed,
                "registration_sha256": c.sha(output / "registration.json"),
                "files_sha256": {
                    n: h
                    for n, h in ctx.previous.prior.packet_hashes(output).items()
                    if n not in ctx.previous.prior.OPERATIONAL
                },
                "artifact_bytes_before_receipt": used,
                "tests": r["tests"],
                "production_changed": False,
                "old_evidence_rewritten": False,
                "automatic_polling": False,
                "automatic_retry": False,
                "automatic_followup": False,
                "scope": "Fixed paired 2 ms channel/bath feedback, "
                "pending independent saved-data closeout.",
            },
        )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        io.write(
            output / "failure.json",
            {
                "status": "paired_capture_failed_not_qualified",
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
    with (
        (output / "runner.stdout.log").open("x") as stdout,
        (output / "runner.stderr.log").open("x") as stderr,
    ):
        process = subprocess.Popen(
            [
                "taskset",
                "-c",
                ",".join(map(str, r["protocol"]["resources"]["cpu_affinity"])),
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
        "resources": r["protocol"]["resources"],
        "reference_gate_before_simulators": True,
        "automatic_polling": False,
        "automatic_retry": False,
        "automatic_followup": False,
    }
    io.write(output / "launch.json", receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    start = sub.add_parser("launch")
    start.add_argument("output", type=Path)
    start.add_argument("--tests", type=Path, required=True)
    run = sub.add_parser("execute")
    run.add_argument("output", type=Path)
    probe = sub.add_parser("worker")
    probe.add_argument("kind", choices=("reference", "betse", "cells"))
    probe.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.action == "launch":
        print(json.dumps(launch(args.output.resolve(), args.tests.resolve()), indent=2))
    elif args.action == "execute":
        execute(args.output.resolve())
    else:
        worker(args.kind, args.output.resolve())
