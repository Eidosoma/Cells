"""Detached full-SIM-loop pilot; capture controls now, independent audit on request."""

import argparse
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

import cluster_alignment as cluster
import contact as c
import full_loop_bridge_check as check
import full_loop_bridge_context as ctx
import phase_bridge as legacy
import profile_bridge as preparation
import trajectory as native
import trajectory_context as old
import trajectory_evidence as evidence
from full_loop_observer import FullLoopObserver

OPERATIONAL = {"launch.json", "runner.stdout.log", "runner.stderr.log"}


def artifact_bytes(output):
    return sum(p.stat().st_size for p in output.rglob("*") if p.is_file())


def check_budget(output, plan):
    # Native libraries write their own seed/SIM pickles. This is a checked
    # between-row panel limit, not a claim of filesystem-wide quota enforcement.
    c.require(
        artifact_bytes(output) < plan["max_artifact_bytes"] - 1024 * 1024,
        "Pilot artifact budget exhausted; preserve evidence without retry",
    )


def manifest(output):
    return {
        str(p.relative_to(output)): c.sha(p)
        for p in sorted(output.rglob("*"))
        if p.is_file() and str(p.relative_to(output)) not in OPERATIONAL
    }


def validate_registration(registered):
    ctx.validate_plan(registered["plan"])
    prelaunch = c.read(ctx.PRELAUNCH)
    c.require(
        registered["schema"] == "cells.betse_full_loop_bridge_registration@1"
        and registered["prior_handoff_sha256"] == ctx.PRIOR_SHA
        and registered["prelaunch_sha256"] == c.sha(ctx.PRELAUNCH)
        and registered["preservation_sha256"] == c.sha(ctx.PRESERVATION)
        and registered["prior_trajectory_registration_sha256"]
        == evidence.ANCHORS["registration.json"],
        "Pilot registration provenance differs",
    )
    c.require(
        prelaunch["status"] == "adapter_checks_pass_not_native_execution"
        and prelaunch["plan_sha256"] == c.sha(ctx.PLAN)
        and prelaunch["test_receipt_sha256"] == c.sha(c.ROOT / prelaunch["test_receipt"])
        and registered["sources"] == prelaunch["sources"] == old.sources()
        and ctx.FILES <= set(registered["sources"])
        and registered["rows"] == ctx.rows(registered["plan"]),
        "Untested/changed pilot sources or coverage",
    )
    prior = evidence.trusted_registration()
    c.require(
        registered["upstream"]["files_sha256"] == prior["upstream"]["files_sha256"]
        and c.sha(c.SOURCE / "betse/data/yaml/sim_config.yaml")
        == prior["upstream"]["files_sha256"]["betse/data/yaml/sim_config.yaml"],
        "Native configuration source differs",
    )
    expected = {
        str(ctx.retained_path(row, mode).relative_to(c.ROOT)): c.sha(ctx.retained_path(row, mode))
        for row in registered["rows"]
        for mode in ctx.MODES
    }
    c.require(
        registered["retained_init_files_sha256"] == expected, "Retained INIT references differ"
    )


def numerical_record(phase, row, mode, directory, prior, observer):
    sim, p = phase.sim, phase.p
    trace = observer.result() if observer is not None else None
    if trace is not None:
        for step in trace["steps"]:
            step["before_elapsed_s"] = step["index"] * p.dt
            step["after_elapsed_s"] = (step["index"] + 1) * p.dt
    return {
        "id": old.key(row["case"]["id"], row["profile"], row["dt_s"]),
        "mode": mode,
        "dt_s": p.dt,
        "constants": {"F": p.F, "R": p.R},
        "geometry": {k: legacy.geometry(phase)[k] for k in cluster.GEOMETRY_FIELDS},
        "settings": {
            name: getattr(p, name)
            for name in prior["settings"]
            if name not in ("solver", "temperature_K")
        }
        | {"solver": p.solver_type.name, "temperature_K": p.T},
        "rho_channel": sim.rho_channel,
        "species": [k for k, enabled in p.ions_dict.items() if enabled],
        "valence": sim.zs.tolist(),
        "permeability_m_per_s": (sim.Dm_cells / p.tm).tolist(),
        "configured_steps": p.sim_tsteps,
        "ordinary": {name: native.array_record(getattr(sim, name)) for name in old.ORDINARY_NAMES},
        "final": {name: native.array_record(getattr(sim, name)) for name in old.FINAL_NAMES},
        "trace": trace,
        "native_yaml_sha256": c.sha(directory / "native.yaml"),
        "native_pickle_present": Path(p.sim_pickle_filename).is_file(),
    }


def run_row(row, mode, directory, prior, package):
    c.require(mode in ctx.MODES and sys.getprofile() is None, "Unexpected observation context")
    directory.mkdir(parents=True, exist_ok=False)
    c.write(
        directory / "started.json",
        {"row": row, "mode": mode, "started_utc": datetime.now(UTC).isoformat()},
    )
    observer = None
    try:
        # Do not reuse prepare_row: it has already initialized dynamics and fired
        # probe events. This helper only seeds and creates a fresh SIM/init_core.
        phase, mapped = preparation.fresh_phase(row, directory, prior)
        c.write(directory / "core.json", preparation.core_snapshot(phase))
        if mode == "observed":
            observer = FullLoopObserver(
                phase,
                package / "science",
                native.native_snapshot,
                native.native_fluxes,
                legacy.event_snapshot,
                directory,
                preparation.core_snapshot,
                lambda: preparation.metadata(phase, directory, mapped, prior),
            )
            with observer:
                phase.sim.run_sim_core(phase)
            c.write(directory / "events.json", observer.event_result())
        else:
            phase.sim.run_sim_core(phase)
        final_state = legacy.event_snapshot(phase.sim)
        c.write(directory / "final-state.json", final_state)
        final_metadata = preparation.metadata(phase, directory, mapped, prior)
        c.write(directory / "final-metadata.json", final_metadata)
        result = {
            "schema": "cells.betse_full_loop_bridge_row@1",
            "status": "exported_not_qualified",
            "row": row,
            "mode": mode,
            "numerical": numerical_record(phase, row, mode, directory, prior, observer),
            "final_state": final_state,
            "final_metadata": final_metadata,
            "final_junctions": preparation.junctions(phase),
            "lifecycle": observer.lifecycle_result() if observer is not None else None,
            "hook_restored": sys.getprofile() is None,
        }
        c.write(directory / "result.json", result)
    except BaseException:
        c.write(
            directory / "failure.json",
            {
                "status": "failed_not_qualified",
                "row": row,
                "mode": mode,
                "traceback": traceback.format_exc(),
                "hook_restored": sys.getprofile() is None,
            },
        )
        if observer is not None:
            try:
                c.write(directory / "partial-observer.json", observer.partial())
            except Exception:
                c.write(
                    directory / "partial-export-failure.json", {"traceback": traceback.format_exc()}
                )
        raise


def worker(registered, output):
    import betse
    import numpy as np

    validate_registration(registered)
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
    results, pair_checks, variant_checks = [], [], []
    current_case, variants = None, {}
    with (
        warnings.catch_warnings(record=True) as caught,
        np.errstate(over="raise", invalid="raise", divide="raise"),
    ):
        warnings.simplefilter("error", RuntimeWarning)
        for row in registered["rows"]:
            if current_case != row["case"]["id"]:
                if variants:
                    variant_checks.append(check.check_variants(variants))
                current_case, variants = row["case"]["id"], {}
            pair = {}
            prepared = check.prepared_packet(row)
            for mode in ctx.MODES:
                directory = output / "native" / ctx.key(row) / mode
                run_row(row, mode, directory, prior, package)
                check_budget(output, plan)
                packet = check.read_packet(directory, mode)
                checked = check.check_row(
                    row, mode, packet, prior, c.read(ctx.retained_path(row, mode)), prepared
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
                print(json.dumps({"native_run_completed": ctx.key(row), "mode": mode}), flush=True)
            pair_checks.append(check.check_pair(pair))
            variants[row["variant"]] = pair["observed"]
        variant_checks.append(check.check_variants(variants))
        c.require(not caught, "Native pilot emitted Python warnings")
    c.require(
        len(results) == plan["native_runs"]
        and sum(r["observed_steps"] for r in results) == plan["observed_steps"]
        and len(pair_checks) == 6
        and len(variant_checks) == 2,
        "Incomplete pilot coverage",
    )
    c.require(
        not any(n == "cells" or n.startswith("cells.") for n in sys.modules),
        "Native pilot imported Cells",
    )
    return {
        "schema": "cells.betse_full_loop_bridge_worker@1",
        "status": "capture_controls_pass_pending_independent_audit",
        "results": results,
        "observer_pairs": pair_checks,
        "variant_controls": variant_checks,
        "native_runs": len(results),
        "observed_steps": plan["observed_steps"],
        "event_dispatch_calls_observed": plan["observed_steps"],
        "enabled_target_event_dispatches_observed": 80,
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
    ctx.validate_plan(plan)
    prelaunch = c.read(ctx.PRELAUNCH)
    c.require(prelaunch["sources"] == old.sources(), "Pilot source changed after focused checks")
    upstream = c.inspect_source()
    registered = {
        "schema": "cells.betse_full_loop_bridge_registration@1",
        "registered_utc": datetime.now(UTC).isoformat(),
        "plan": plan,
        "rows": ctx.rows(plan),
        "sources": old.sources(),
        "upstream": upstream,
        "prior_handoff_sha256": ctx.PRIOR_SHA,
        "prior_trajectory_registration_sha256": evidence.ANCHORS["registration.json"],
        "prelaunch_sha256": c.sha(ctx.PRELAUNCH),
        "preservation_sha256": c.sha(ctx.PRESERVATION),
        "retained_init_files_sha256": {
            str(ctx.retained_path(row, mode).relative_to(c.ROOT)): c.sha(
                ctx.retained_path(row, mode)
            )
            for row in ctx.rows(plan)
            for mode in ctx.MODES
        },
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
    return registered


def execute(output):
    started = time.monotonic()
    try:
        registered = c.read(output / "registration.json")
        validate_registration(registered)
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
        c.require(remaining > 0, "Pilot wall budget exhausted before worker")
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
            "Pilot controls failed",
        )
        ctx.preservation_check()
        validate_registration(registered)
        check_budget(output, plan)
        payloads = manifest(output)
        c.require(
            time.monotonic() - started < plan["total_timeout_seconds"],
            "Pilot wall budget exhausted",
        )
        c.write(
            output / "capture.json",
            {
                "schema": "cells.betse_full_loop_bridge_capture@1",
                "status": result["status"],
                "elapsed_seconds": time.monotonic() - started,
                "finished_utc": datetime.now(UTC).isoformat(),
                "registration_sha256": c.sha(output / "registration.json"),
                "files_sha256": payloads,
                "artifact_bytes_before_receipt": artifact_bytes(output),
                "native_runs": result["native_runs"],
                "observed_steps": result["observed_steps"],
                "trajectory_run": True,
                "trajectory_qualified": False,
                "independent_audit_run": False,
                "expanded_bridge_qualified": False,
                "nonzero_intervention": False,
                "cells_runs": 0,
                "biology_validated": False,
                "gpu_tested": False,
            },
        )
    except BaseException:
        c.write(
            output / "failure.json",
            {
                "status": "failed_not_qualified",
                "elapsed_seconds": time.monotonic() - started,
                "traceback": traceback.format_exc(),
                "files_sha256": manifest(output),
                "trajectory_qualified": False,
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
                },
            )
            raise
