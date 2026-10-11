"""Detached, source-bound finer native preflight; no automatic trajectory or audit."""

import argparse
import json
import os
import subprocess
import time
import traceback
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import refined_dispatch_context as ctx

c = ctx.c


def inputs(plan):
    return {
        ctx.key(row): {
            "row": row,
            "protocol": ctx.mapping(row)[0],
            "mapping": ctx.mapping(row)[1],
            "controls": ctx.held.held_schedule(
                c.read(ctx.held.PLAN), row["condition"], row["dt_s"]
            ),
        }
        for row in ctx.rows(plan)
    }


def validate_registration(r):
    ctx.validate_plan(r["plan"])
    pre = c.read(ctx.PRELAUNCH)
    c.require(
        r["schema"] == "cells.betse_refined_dispatch_registration@1"
        and r["plan"] == pre["plan"] == c.read(ctx.PLAN)
        and r["audit_completion_sha256"] == ctx.AUDIT_SHA
        and r["prelaunch_sha256"] == c.sha(ctx.PRELAUNCH)
        and r["preservation_sha256"] == pre["preservation_sha256"] == c.sha(ctx.PRESERVATION),
        "Registered identity/plan differs",
    )
    c.require(
        pre["status"] == "software_checks_pass_not_native_execution"
        and pre["test_receipt_sha256"] == c.sha(c.ROOT / pre["test_receipt"])
        and r["sources"] == pre["sources"] == ctx.sources()
        and len(r["sources"]) == 98
        and all(c.sha(c.HERE / n) == h for n, h in r["sources"].items()),
        "Registered source/test provenance differs",
    )
    for n, h in pre["new_files_sha256_before_prelaunch"].items():
        c.require(c.sha(c.ROOT / n) == h, "Frozen finer-dispatch input changed: " + n)
    c.require(
        r["upstream"] == ctx.legacy.evidence.trusted_registration()["upstream"]
        and r["inputs"] == inputs(r["plan"]),
        "Registered upstream/inputs differ",
    )
    ctx.preservation_check()


def row_paths(count):
    return {
        "core.json",
        "dynamics.json",
        "ready.json",
        "metadata.json",
        "dispatch.json",
        "final.json",
        "native.yaml",
        "INITS/world_1.betse.gz",
    } | {f"events/{k:04d}.json" for k in range(count)}


def validate_worker(w, registered, output):
    p = registered["plan"]
    c.require(
        w["schema"] == "cells.betse_refined_dispatch_worker@1"
        and w["status"] == "refined_dispatch_checks_pass"
        and w["registration_sha256"] == c.sha(output / "registration.json")
        and w["sources"] == registered["sources"]
        and w["warnings"] == []
        and type(w["integration_calls"]) is int
        and w["integration_calls"] == 0
        and all(w[k] is False for k in ctx.FALSE_FLAGS),
        "Wrong/overclaimed native result",
    )
    c.require(
        all(
            type(w[k]) is int and w[k] == p[k]
            for k in (
                "preparations",
                "event_dispatch_calls",
                "targeted_dispatches",
                "nonzero_targeted_dispatches",
                "control_values_checked",
            )
        ),
        "Native coverage differs",
    )
    c.require([r["row"] for r in w["results"]] == ctx.rows(p), "Native row coverage/order differs")
    expected_controls = {
        f"{h:.8f}": {
            "status": "exact_preparation_controls_pass",
            "baseline_zero_dispatch_equal": True,
            "fresh_normal_preparations_equal": True,
        }
        for h in p["hold_steps_s"]
    }
    c.require(w["controls"] == expected_controls, "Missing/different exact control panel")
    expected_sources = {
        n: h
        for n, h in registered["upstream"]["files_sha256"].items()
        if n.startswith("betse/") and n.endswith(".py")
    }
    c.require(
        w["installed_python_sha256"] == expected_sources
        and len(expected_sources) == 332
        and Path(w["package_path"]).is_relative_to(c.REFERENCE_PYTHON.parent.parent)
        and w["environment"]["packages"] == c.locked_reference_packages()
        and w["environment"]["executable"] == str(c.REFERENCE_PYTHON)
        and w["environment"]["python"] == "3.13.5",
        "Native result provenance differs",
    )
    for row in w["results"]:
        directory = output / ctx.key(row["row"])
        count = ctx.mapping(row["row"])[1]["steps"]
        saved = c.read(directory / "result.json")
        expected = row_paths(count)
        actual = ctx.audit_context.packet_hashes(directory)
        c.require(
            row["path"] == ctx.key(row["row"]) + "/result.json"
            and row["sha256"] == actual["result.json"]
            and set(actual) == expected | {"result.json"}
            and set(saved["files_sha256"]) == expected
            and all(actual[n] == h for n, h in saved["files_sha256"].items()),
            "Native row payload coverage/digests differ",
        )
        c.require(
            {k: v for k, v in saved.items() if k not in ("files_sha256", "retained_files_sha256")}
            == {k: v for k, v in row.items() if k not in ("path", "sha256")},
            "Native row receipt linkage differs",
        )
        c.require(
            row["status"] == "refined_dispatch_checks_pass"
            and row["integration_calls"] == 0
            and row["trajectory_qualified"] is False
            and row["event_dispatch_calls"] == count
            and row["control_values_checked"] == count * 360
            and 0 <= row["maximum_baseline_scaled_control_error"] <= p["control_atol"],
            "Native row check verdict differs",
        )
        events = c.read(directory / "dispatch.json")["events"]
        c.require(
            len(events) == count
            and all(
                c.read(directory / f"events/{k:04d}.json") == event
                for k, event in enumerate(events)
            ),
            "Durable/aggregate dispatch records differ",
        )
        # Exact retained reference paths are derived, not trusted from a worker receipt.
        retained = import_retained(row["row"])
        c.require(saved["retained_files_sha256"] == retained, "Retained preparation links differ")
    c.require(
        w["maximum_baseline_scaled_control_error"]
        == max(r["maximum_baseline_scaled_control_error"] for r in w["results"]),
        "Aggregate control error differs",
    )


def import_retained(row):
    import dispatch_preflight

    return dispatch_preflight.retained(row)[2]


def payloads(output):
    return {
        n: h
        for n, h in ctx.audit_context.packet_hashes(output).items()
        if n not in ctx.audit_context.OPERATIONAL
    }


def execute(output):
    began, stage = time.monotonic(), "validation"
    try:
        registered = c.read(output / "registration.json")
        validate_registration(registered)
        ctx.audit_job.capsule(output, registered)
        p = registered["plan"]
        c.write(
            output / "started.json",
            {"pid": os.getpid(), "started_utc": datetime.now(UTC).isoformat()},
        )
        env = os.environ | {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(output / "matplotlib-cache"),
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        }
        env.pop("PYTHONPATH", None)
        remaining = p["total_timeout_seconds"] - (time.monotonic() - began)
        c.require(remaining > 0, "Preflight total deadline exhausted")
        stage = "native_preflight"
        with (output / "worker.log").open("x") as log:
            process = subprocess.run(
                [
                    "taskset",
                    "-c",
                    p["cpu_affinity"],
                    str(c.REFERENCE_PYTHON),
                    "-B",
                    str(ctx.HERE / "refined_dispatch_native.py"),
                    str(output),
                ],
                cwd=c.ROOT,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=min(remaining, p["worker_timeout_seconds"]),
                check=False,
            )
        c.require(process.returncode == 0, "Native preflight failed; preserve partial evidence")
        stage = "receipt_validation"
        result = c.read(output / "worker.json")
        validate_worker(result, registered, output)
        validate_registration(registered)
        preserved = ctx.preservation_check()
        size = sum(f.stat().st_size for f in output.rglob("*") if f.is_file())
        elapsed = time.monotonic() - began
        c.require(
            size < p["max_artifact_bytes"] - 1024**2 and elapsed < p["total_timeout_seconds"],
            "Preflight resource cap exceeded",
        )
        c.write(
            output / "completion.json",
            {
                "schema": "cells.betse_refined_dispatch_completion@1",
                "status": "refined_dispatch_checks_pass_not_response_qualification",
                "finished_utc": datetime.now(UTC).isoformat(),
                "elapsed_seconds": elapsed,
                "registration_sha256": c.sha(output / "registration.json"),
                "preparations": result["preparations"],
                "event_dispatch_calls": result["event_dispatch_calls"],
                "targeted_dispatches": result["targeted_dispatches"],
                "nonzero_targeted_dispatches": result["nonzero_targeted_dispatches"],
                "control_values_checked": result["control_values_checked"],
                "maximum_baseline_scaled_control_error": result[
                    "maximum_baseline_scaled_control_error"
                ],
                "integration_calls": 0,
                "files_sha256": payloads(output),
                "artifact_bytes_before_receipt": size,
                "independent_audit_run": False,
                **dict.fromkeys(ctx.FALSE_FLAGS, False),
                **preserved,
            },
        )
        print(
            json.dumps(
                {
                    "status": "refined_dispatch_checks_pass_not_response_qualification",
                    "elapsed_seconds": elapsed,
                }
            ),
            flush=True,
        )
    except BaseException:
        c.write(
            output / "failure.json",
            {
                "status": "refined_dispatch_failed_not_qualified",
                "stage": stage,
                "elapsed_seconds": time.monotonic() - began,
                "traceback": traceback.format_exc(),
                "files_sha256": payloads(output),
                "trajectory_qualified": False,
                "automatic_retry": False,
                "automatic_trajectory_launch": False,
            },
        )
        raise


def register(output):
    c.require(
        output.is_relative_to(c.ROOT / "runs")
        and output != c.ROOT / "runs"
        and not output.exists()
        and not output.is_relative_to(ctx.AUDIT)
        and not output.is_relative_to(ctx.audit_context.SESSION),
        "Use a fresh preflight directory",
    )
    ctx.preservation_check()
    plan = c.read(ctx.PLAN)
    registered = {
        "schema": "cells.betse_refined_dispatch_registration@1",
        "registered_utc": datetime.now(UTC).isoformat(),
        "plan": plan,
        "sources": ctx.sources(),
        "audit_completion_sha256": ctx.AUDIT_SHA,
        "prelaunch_sha256": c.sha(ctx.PRELAUNCH),
        "preservation_sha256": c.sha(ctx.PRESERVATION),
        "upstream": c.inspect_source(),
        "inputs": inputs(plan),
    }
    validate_registration(registered)
    output.mkdir(parents=True, exist_ok=False)
    c.write(output / "registration.json", registered)
    with zipfile.ZipFile(output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in registered["sources"]:
            archive.write(c.HERE / name, arcname=name)
    ctx.audit_job.capsule(output, registered)


def launch(output):
    register(output)
    try:
        with (
            (output / "runner.stdout.log").open("x") as out,
            (output / "runner.stderr.log").open("x") as err,
        ):
            process = subprocess.Popen(
                [
                    "taskset",
                    "-c",
                    "0-3",
                    str(c.CELLS_PYTHON),
                    "-B",
                    str(Path(__file__).resolve()),
                    "execute",
                    str(output),
                ],
                cwd=c.ROOT,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                start_new_session=True,
            )
    except BaseException:
        c.write(
            output / "failure.json",
            {
                "status": "launch_failed_not_started",
                "traceback": traceback.format_exc(),
                "automatic_retry": False,
            },
        )
        raise
    receipt = {
        "status": "launched_detached",
        "pid": process.pid,
        "launched_utc": datetime.now(UTC).isoformat(),
        "registration_sha256": c.sha(output / "registration.json"),
        "worker_timeout_seconds": 300,
        "total_timeout_seconds": 360,
        "automatic_polling": False,
        "automatic_retry": False,
        "automatic_trajectory_launch": False,
        "independent_audit": "await_user_instruction",
    }
    c.write(output / "launch.json", receipt)
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("launch", "execute"))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    (launch if args.action == "launch" else execute)(args.output.resolve())
