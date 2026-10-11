"""Detached D077 capture; reuse the frozen native runner, not the narrow pilot plan."""

import argparse
import hashlib
import json
import os
import resource
import subprocess
import sys
import time
import traceback
import warnings
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import contact as c
import expanded_bridge_check as check
import expanded_bridge_context as ctx
import full_loop_bridge as native
import full_loop_bridge_check as shared
import full_loop_bridge_context as pilot
import trajectory_context as sources
import trajectory_evidence as evidence


def reference_hashes(rows):
    return {
        str(pilot.retained_path(row, mode).relative_to(c.ROOT)): c.sha(
            pilot.retained_path(row, mode)
        )
        for row in rows
        for mode in ctx.MODES
    }


def validate_registration(registered):
    ctx.validate_plan(registered["plan"])
    prelaunch = c.read(ctx.PRELAUNCH)
    c.require(
        registered["schema"] == "cells.betse_expanded_bridge_registration@1"
        and registered["pilot_closeout_sha256"] == ctx.ANCHORS["completion.json"]
        and registered["prelaunch_sha256"] == c.sha(ctx.PRELAUNCH)
        and registered["preservation_sha256"] == c.sha(ctx.PRESERVATION)
        and registered["prior_trajectory_registration_sha256"]
        == evidence.ANCHORS["registration.json"],
        "Expanded registration provenance differs",
    )
    c.require(
        prelaunch["status"] == "adapter_checks_pass_not_native_execution"
        and prelaunch["plan_sha256"] == c.sha(ctx.PLAN)
        and prelaunch["test_receipt_sha256"] == c.sha(c.ROOT / prelaunch["test_receipt"])
        and registered["sources"] == prelaunch["sources"] == sources.sources()
        and ctx.FILES <= set(registered["sources"])
        and registered["rows"] == ctx.rows(registered["plan"]),
        "Untested/changed expanded sources or coverage",
    )
    for name, digest in prelaunch["new_files_sha256_before_prelaunch"].items():
        c.require(c.sha(c.ROOT / name) == digest, "Frozen expanded preflight file changed: " + name)
    prior = evidence.trusted_registration()
    c.require(
        registered["upstream"]["files_sha256"] == prior["upstream"]["files_sha256"]
        and c.sha(c.SOURCE / "betse/data/yaml/sim_config.yaml")
        == prior["upstream"]["files_sha256"]["betse/data/yaml/sim_config.yaml"],
        "Native configuration source differs",
    )
    c.require(
        registered["retained_init_files_sha256"] == reference_hashes(registered["rows"]),
        "Retained INIT references differ",
    )


def check_capsule(output, registered):
    with zipfile.ZipFile(output / "sources.zip") as archive:
        c.require(
            len(archive.namelist()) == len(set(archive.namelist()))
            and set(archive.namelist()) == set(registered["sources"]),
            "Expanded source capsule coverage differs",
        )
        c.require(
            {n: hashlib.sha256(archive.read(n)).hexdigest() for n in archive.namelist()}
            == registered["sources"],
            "Expanded source capsule bytes differ",
        )


def require_coverage(plan, results, pairs, variants, overlaps):
    expected = [(row, mode) for row in ctx.rows(plan) for mode in ctx.MODES]
    c.require(
        [(r["row"], r["mode"]) for r in results] == expected
        and len(results) == plan["native_runs"]
        and all(r["status"] == "capture_row_checks_pass" for r in results)
        and all(
            r["observed_steps"]
            == (round(plan["duration_s"] / r["row"]["dt_s"]) if r["mode"] == "observed" else 0)
            for r in results
        )
        and sum(r["observed_steps"] for r in results) == plan["observed_steps"],
        "Incomplete expanded run/step coverage",
    )
    row_keys = [pilot.key(row) for row in ctx.rows(plan)]
    c.require(
        pairs == [{"key": key, "status": "observer_pair_exact"} for key in row_keys],
        "Incomplete observer-pair coverage",
    )
    c.require(
        variants
        == [
            {"key": pilot.key(row), "status": "variant_control_exact", "variant": row["variant"]}
            for row in ctx.rows(plan)
            if row["variant"] != "baseline"
        ],
        "Incomplete profile/no-op variant coverage",
    )
    c.require(
        overlaps
        == [
            {"key": pilot.key(row), "mode": mode, "status": "original_pilot_overlap_exact"}
            for row, mode in expected
            if ctx.overlap(row)
        ],
        "Incomplete original-pilot overlap coverage",
    )
    c.require(
        len(pairs) == plan["observer_pairs"]
        and len(variants) == plan["variant_comparisons"]
        and len(overlaps) == plan["pilot_overlap_runs"]
        and sum(r["observed_steps"] for r in results if r["row"]["variant"] == "zero_amplitude")
        == plan["enabled_target_dispatches"],
        "Expanded control totals differ",
    )


def worker(registered, output):
    import betse
    import numpy as np

    validate_registration(registered)
    check_capsule(output, registered)
    plan, prior = registered["plan"], evidence.trusted_registration()
    c.require(sorted(os.sched_getaffinity(0)) == [0, 1, 2, 3], "Worker CPU affinity differs")
    resource.setrlimit(resource.RLIMIT_FSIZE, (plan["max_worker_file_bytes"],) * 2)
    package = Path(betse.__file__).resolve().parent
    installed = {"betse/" + str(p.relative_to(package)): c.sha(p) for p in package.rglob("*.py")}
    c.require(
        installed
        == {
            n: h
            for n, h in prior["upstream"]["files_sha256"].items()
            if n.startswith("betse/") and n.endswith(".py")
        }
        and package.is_relative_to(c.REFERENCE_PYTHON.parent.parent),
        "Installed BETSE differs from pinned source",
    )
    results, pairs, variants, overlaps = [], [], [], []
    current_group, baseline = None, None
    with (
        warnings.catch_warnings(record=True) as caught,
        np.errstate(over="raise", invalid="raise", divide="raise"),
    ):
        warnings.simplefilter("error", RuntimeWarning)
        for row in registered["rows"]:
            group = ctx.group_key(row)
            if group != current_group:
                c.require(row["variant"] == "baseline", "Control group must start with baseline")
                current_group, baseline = group, None
            pair = {}
            for mode in ctx.MODES:
                directory = output / "native" / pilot.key(row) / mode
                native.run_row(row, mode, directory, prior, package)
                native.check_budget(output, plan)
                packet = shared.read_packet(directory, mode)
                checked = check.check_row(
                    row, mode, packet, prior, c.read(pilot.retained_path(row, mode))
                )
                if ctx.overlap(row):
                    overlaps.append(
                        {
                            "key": pilot.key(row),
                            "mode": mode,
                            **check.check_overlap(row, mode, packet),
                        }
                    )
                c.write(directory / "checks.json", checked)
                pair[mode] = packet
                results.append(
                    {
                        "row": row,
                        "mode": mode,
                        "path": str((directory / "result.json").relative_to(output)),
                        "sha256": c.sha(directory / "result.json"),
                        **checked,
                    }
                )
                print(
                    json.dumps({"native_run_completed": pilot.key(row), "mode": mode}), flush=True
                )
            pairs.append({"key": pilot.key(row), **shared.check_pair(pair)})
            if row["variant"] == "baseline":
                baseline = pair["observed"]
            else:
                c.require(baseline is not None, "Missing baseline control")
                variants.append(
                    {"key": pilot.key(row), **check.check_variant(baseline, pair["observed"])}
                )
            # Keep one baseline and one current pair, never the whole expanded panel.
        c.require(not caught, "Native expanded capture emitted Python warnings")
    require_coverage(plan, results, pairs, variants, overlaps)
    c.require(
        not any(n == "cells" or n.startswith("cells.") for n in sys.modules),
        "Native expanded worker imported Cells",
    )
    return {
        "schema": "cells.betse_expanded_bridge_worker@1",
        "status": "capture_controls_pass_pending_independent_audit",
        "results": results,
        "observer_pairs": pairs,
        "variant_controls": variants,
        "pilot_overlap": overlaps,
        "native_runs": len(results),
        "observed_steps": plan["observed_steps"],
        "event_dispatch_calls_observed": plan["observed_steps"],
        "enabled_target_event_dispatches_observed": plan["enabled_target_dispatches"],
        "installed_python_sha256": installed,
        "package_path": str(package),
        "environment": c.environment(),
        "warnings": [],
        "trajectory_run": True,
        "trajectory_qualified": False,
        "expanded_bridge_qualified": False,
        "nonzero_intervention": False,
        "cells_runs": 0,
        "biology_validated": False,
        "gpu_tested": False,
    }


def register(output):
    ctx.preservation_check()
    plan = c.read(ctx.PLAN)
    ctx.resource_estimate(plan)
    registered = {
        "schema": "cells.betse_expanded_bridge_registration@1",
        "registered_utc": datetime.now(UTC).isoformat(),
        "plan": plan,
        "rows": ctx.rows(plan),
        "sources": sources.sources(),
        "upstream": c.inspect_source(),
        "pilot_closeout_sha256": ctx.ANCHORS["completion.json"],
        "prior_trajectory_registration_sha256": evidence.ANCHORS["registration.json"],
        "prelaunch_sha256": c.sha(ctx.PRELAUNCH),
        "preservation_sha256": c.sha(ctx.PRESERVATION),
        "retained_init_files_sha256": reference_hashes(ctx.rows(plan)),
    }
    validate_registration(registered)
    c.require(
        output.is_relative_to(c.ROOT / "runs") and output != c.ROOT / "runs",
        "Use a fresh run subdirectory",
    )
    output.mkdir(parents=True, exist_ok=False)
    c.write(output / "registration.json", registered)
    with zipfile.ZipFile(output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in registered["sources"]:
            archive.write(c.HERE / name, arcname=name)
    check_capsule(output, registered)
    return registered


def execute(output):
    started = time.monotonic()
    try:
        registered = c.read(output / "registration.json")
        validate_registration(registered)
        check_capsule(output, registered)
        plan = registered["plan"]
        c.write(
            output / "started.json",
            {"pid": os.getpid(), "started_utc": datetime.now(UTC).isoformat()},
        )
        env = os.environ | {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(output / "matplotlib-cache"),
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
        env.pop("PYTHONPATH", None)
        remaining = plan["total_timeout_seconds"] - (time.monotonic() - started)
        c.require(remaining > 0, "Expanded wall budget exhausted before worker")
        with (output / "worker.log").open("x") as log:
            subprocess.run(
                [
                    "taskset",
                    "-c",
                    plan["cpu_affinity"],
                    str(c.REFERENCE_PYTHON),
                    "-B",
                    str(Path(__file__).resolve()),
                    "worker",
                    str(output),
                ],
                cwd=c.ROOT,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=min(remaining, plan["worker_timeout_seconds"]),
                check=True,
            )
        result = c.read(output / "worker.json")
        c.require(
            result["status"] == "capture_controls_pass_pending_independent_audit",
            "Expanded controls failed",
        )
        require_coverage(
            plan,
            result["results"],
            result["observer_pairs"],
            result["variant_controls"],
            result["pilot_overlap"],
        )
        preserved = ctx.preservation_check()
        validate_registration(registered)
        check_capsule(output, registered)
        native.check_budget(output, plan)
        payloads = native.manifest(output)
        c.require(
            time.monotonic() - started < plan["total_timeout_seconds"],
            "Expanded wall budget exhausted",
        )
        c.write(
            output / "capture.json",
            {
                "schema": "cells.betse_expanded_bridge_capture@1",
                "status": result["status"],
                "elapsed_seconds": time.monotonic() - started,
                "finished_utc": datetime.now(UTC).isoformat(),
                "registration_sha256": c.sha(output / "registration.json"),
                "files_sha256": payloads,
                "artifact_bytes_before_receipt": native.artifact_bytes(output),
                "native_runs": result["native_runs"],
                "observed_steps": result["observed_steps"],
                "observer_pairs": len(result["observer_pairs"]),
                "variant_comparisons": len(result["variant_controls"]),
                "pilot_overlap_runs": len(result["pilot_overlap"]),
                "trajectory_run": True,
                "trajectory_qualified": False,
                "independent_audit_run": False,
                "expanded_bridge_qualified": False,
                "nonzero_intervention": False,
                "cells_runs": 0,
                "biology_validated": False,
                "gpu_tested": False,
                "automatic_retry": False,
                **preserved,
            },
        )
    except BaseException:
        c.write(
            output / "failure.json",
            {
                "status": "failed_not_qualified",
                "elapsed_seconds": time.monotonic() - started,
                "traceback": traceback.format_exc(),
                "files_sha256": native.manifest(output),
                "trajectory_qualified": False,
                "expanded_bridge_qualified": False,
                "automatic_retry": False,
            },
        )
        raise


def launch(output):
    registered = register(output)
    with (
        (output / "runner.stdout.log").open("x") as out,
        (output / "runner.stderr.log").open("x") as err,
    ):
        process = subprocess.Popen(
            [
                "taskset",
                "-c",
                registered["plan"]["cpu_affinity"],
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
    receipt = {
        "status": "launched_detached",
        "pid": process.pid,
        "launched_utc": datetime.now(UTC).isoformat(),
        "registration_sha256": c.sha(output / "registration.json"),
        "worker_timeout_seconds": registered["plan"]["worker_timeout_seconds"],
        "total_timeout_seconds": registered["plan"]["total_timeout_seconds"],
        "independent_audit": "await_user_instruction",
        "automatic_polling": False,
    }
    c.write(output / "launch.json", receipt)
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("launch", "execute", "worker"))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    destination = args.output.resolve()
    if args.command == "launch":
        launch(destination)
    elif args.command == "execute":
        execute(destination)
    else:
        try:
            c.write(
                destination / "worker.json",
                worker(c.read(destination / "registration.json"), destination),
            )
        except BaseException:
            c.write(
                destination / "worker-failure.json",
                {
                    "status": "failed_not_qualified",
                    "traceback": traceback.format_exc(),
                    "trajectory_qualified": False,
                    "expanded_bridge_qualified": False,
                },
            )
            raise
