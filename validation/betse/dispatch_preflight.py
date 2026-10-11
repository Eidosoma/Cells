"""Bounded real nonzero native dispatch; no trajectory entry is permitted."""

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

import alignment
import contact as c
import dispatch_preflight_check as check
import dispatch_preflight_context as ctx
import phase_bridge as snapshot
import profile_bridge as base
import trajectory as native
import trajectory_context as old
import trajectory_evidence as evidence
from native_event_observer import NativeEventObserver, PreparationFence


def manifest(output, exclude=frozenset()):
    result = {}
    for p in sorted(output.rglob("*")):
        c.require(not p.is_symlink(), "Attempt contains linked artifacts")
        if p.is_file() and str(p.relative_to(output)) not in exclude:
            result[str(p.relative_to(output))] = c.sha(p)
    return result


def retained(row):
    original = (
        evidence.SESSION
        / "native"
        / old.key(row["case"]["id"], row["profile"], row["dt_s"])
        / "observed/result.json"
    )
    index = 4 if row["case"]["id"] == "blocked" else 1
    prepared = c.ROOT / "runs/ref-003e0-v2-2026-09-12/preflight-01" / f"preparation-{index:02d}"
    paths = [original, prepared / "core.json", prepared / "ready.json"]
    return (
        c.read(original),
        {n: c.read(prepared / (n + ".json")) for n in ("core", "ready")},
        {str(p.relative_to(c.ROOT)): c.sha(p) for p in paths},
    )


def fresh_phase(row, directory, prior):
    import numpy as np
    from betse.science.enum.enumphase import SimPhaseKind
    from betse.science.parameters import Parameters
    from betse.science.phase.phasecls import SimPhase
    from betse.science.simrunner import SimRunner
    from ruamel.yaml import YAML

    protocol, mapped = ctx.mapping(row)
    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    with (c.SOURCE / "betse/data/yaml/sim_config.yaml").open() as handle:
        configuration = alignment.configuration(yaml.load(handle), protocol, directory)
    with (directory / "native.yaml").open("x") as handle:
        yaml.dump(configuration, handle)
    p = Parameters()
    p.load(str(directory / "native.yaml"))
    constants = prior["base_protocol"]["profiles"][row["profile"]]
    p.F, p.R = constants["F"], constants["R"]
    np.random.seed(prior["base_protocol"]["seed"])
    seeded = SimRunner(p).seed()
    phase = SimPhase(kind=SimPhaseKind.SIM, cells=seeded.cells, p=p)
    phase.sim.init_core(phase)
    return phase, mapped


def metadata(phase, directory, mapped, prior):
    result = base.metadata(phase, directory, mapped, prior)
    dyna = phase.dyna
    # The generic legacy metadata helper only enumerates zero-amplitude targets.
    # Read the actual enabled targets explicitly for this new event-mode contract.
    ions = ("Na", "K", "Cl") if mapped["events_enabled"] else ()
    result["event_targets"] = {
        ion: [int(i) for i in getattr(dyna, "targets_" + ion + "mem")] for ion in ions
    }
    result["event_effectors"] = {
        ion: {
            "scalar": float(getattr(dyna, "scalar_" + ion + "mem")),
            "dynamic_values": [
                float(getattr(dyna, "dyna_" + ion + "mem")(t)) for t in mapped["raw_labels_s"]
            ],
            "function": getattr(dyna, "function_" + ion + "mem"),
            "multiplier": float(getattr(dyna, "mem_mult_" + ion + "mem")),
            "pulse_times_s": [
                float(getattr(dyna, prefix + ion + "mem"))
                for prefix in ("t_on_", "t_off_", "t_change_")
            ],
        }
        for ion in ions
    }
    return result


def dispatch(phase, package, mapped, directory):
    import numpy as np

    labels = np.linspace(0, phase.p.total_time, mapped["steps"]).tolist()
    c.require(labels == mapped["raw_labels_s"], "Actual native linspace labels differ")
    observer = NativeEventObserver(
        phase,
        package / "science",
        native.native_snapshot,
        native.native_fluxes,
        snapshot.event_snapshot,
        labels,
    )
    events = directory / "events"
    events.mkdir(exist_ok=False)
    try:
        with observer:
            for index, t in enumerate(labels):
                phase.dyna.fire_events(phase=phase, t=t)
                c.write(events / f"{index:04d}.json", observer.events[-1])
        return observer.event_result()
    except Exception:
        c.write(
            directory / "dispatch-partial.json",
            {
                "events": observer.events,
                "open_event": observer.open_event,
                "hook_restored": sys.getprofile() is None,
            },
        )
        raise


def prepare_row(row, directory, prior, package, plan):
    directory.mkdir(exist_ok=False)
    packet = {}
    with PreparationFence(package / "science") as fence:
        phase, mapped = fresh_phase(row, directory, prior)
        packet["core"] = base.core_snapshot(phase)
        base.write_stage(directory, "core", packet["core"])
        phase.sim.init_dynamics(phase)
        packet["dynamics"] = base.core_snapshot(phase)
        base.write_stage(directory, "dynamics", packet["dynamics"])
        phase.sim.clear_storage(phase.cells, phase.p)
        phase.sim.update_V(phase.cells, phase.p)
    packet["ready"] = {
        "row": row,
        "mapping": mapped,
        "state": snapshot.event_snapshot(phase.sim),
        "initial": native.native_snapshot(phase.sim),
        "preparation_calls": fence.calls,
        "hook_restored": sys.getprofile() is None,
    }
    with PreparationFence(package / "science"):
        packet["metadata"] = base.save_ready_before_metadata(
            directory, packet["ready"], lambda: metadata(phase, directory, mapped, prior)
        )
    original, preparation, references = retained(row)
    check.check_prepared(row, packet, prior, original, plan, preparation)
    packet["dispatch"] = dispatch(phase, package, mapped, directory)
    base.write_stage(directory, "dispatch", packet["dispatch"])
    with PreparationFence(package / "science"):
        packet["final"] = {
            "state": snapshot.event_snapshot(phase.sim),
            "metadata": metadata(phase, directory, mapped, prior),
            "junctions": base.junctions(phase),
        }
    base.write_stage(directory, "final", packet["final"])
    result = check.check_row(row, packet, prior, original, plan, preparation)
    c.write(
        directory / "result.json",
        result
        | {"row": row, "retained_files_sha256": references, "files_sha256": manifest(directory)},
    )
    return packet, result


def validate_registration(registration):
    ctx.validate_plan(registration["plan"])
    pre = c.read(ctx.PRELAUNCH)
    c.require(
        registration["schema"] == "cells.betse_nonzero_dispatch_registration@1"
        and registration["prior_review_sha256"] == ctx.PRIOR_SHA
        and registration["prelaunch_sha256"] == c.sha(ctx.PRELAUNCH)
        and registration["preservation_sha256"] == c.sha(ctx.PRESERVATION)
        and pre["status"] == "software_checks_pass_not_native_execution"
        and pre["plan_sha256"] == c.sha(ctx.PLAN)
        and pre["test_receipt_sha256"] == c.sha(c.ROOT / pre["test_receipt"])
        and registration["plan"] == c.read(ctx.PLAN)
        and registration["sources"] == pre["sources"] == old.sources()
        and ctx.FILES <= set(registration["sources"]),
        "Registered input/source/test provenance differs",
    )
    c.require(
        registration["upstream"]["files_sha256"]
        == evidence.trusted_registration()["upstream"]["files_sha256"],
        "Registered upstream changed",
    )


def worker(registration, output):
    import betse
    import numpy as np

    validate_registration(registration)
    plan = registration["plan"]
    resource.setrlimit(
        resource.RLIMIT_FSIZE, (plan["max_worker_file_bytes"], plan["max_worker_file_bytes"])
    )
    prior = evidence.trusted_registration()
    package = Path(betse.__file__).resolve().parent
    installed = {"betse/" + str(p.relative_to(package)): c.sha(p) for p in package.rglob("*.py")}
    expected = {
        n: h
        for n, h in prior["upstream"]["files_sha256"].items()
        if n.startswith("betse/") and n.endswith(".py")
    }
    c.require(
        installed == expected and package.is_relative_to(c.REFERENCE_PYTHON.parent.parent),
        "Wrong native installation",
    )
    packets, results = {}, []
    with (
        warnings.catch_warnings(record=True) as caught,
        np.errstate(over="raise", invalid="raise", divide="raise"),
    ):
        warnings.simplefilter("error", RuntimeWarning)
        for row in ctx.rows(plan):
            packet, result = prepare_row(row, output / row["condition"], prior, package, plan)
            packets[row["condition"]] = packet
            results.append(result)
            c.require(
                sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
                < plan["max_artifact_bytes"] - 1024 * 1024,
                "Artifact budget exhausted",
            )
        c.require(not caught, "Native preparation emitted Python warnings")
    controls = check.check_controls(packets, plan)
    c.require(
        not any(n == "cells" or n.startswith("cells.") for n in sys.modules),
        "Native preflight imported Cells",
    )
    return {
        "schema": "cells.betse_nonzero_dispatch_worker@1",
        "status": "nonzero_dispatch_checks_pass",
        "preparations": len(results),
        "event_dispatch_calls": sum(r["event_dispatch_calls"] for r in results),
        "targeted_dispatches": 80,
        "nonzero_targeted_dispatches": 40,
        "control_values_checked": sum(r["control_values_checked"] for r in results),
        "maximum_baseline_scaled_control_error": max(
            r["maximum_baseline_scaled_control_error"] for r in results
        ),
        "controls": controls,
        "installed_python_sha256": installed,
        "environment": c.environment(),
        "warnings": [],
        "integration_calls": 0,
        "trajectory_run": False,
        "trajectory_qualified": False,
    }


def execute_worker(output, plan, timeout):
    with (output / "worker.log").open("x") as log:
        return subprocess.run(
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
            stdout=log,
            stderr=subprocess.STDOUT,
            env=os.environ
            | {
                "PYTHONDONTWRITEBYTECODE": "1",
                "MPLBACKEND": "Agg",
                "OPENBLAS_NUM_THREADS": "1",
                "OMP_NUM_THREADS": "1",
                "MKL_NUM_THREADS": "1",
            },
            timeout=timeout,
            check=False,
        )


def preflight(output):
    c.require(not output.exists(), "Refuse to reuse a native attempt")
    ctx.preservation_check()
    plan = c.read(ctx.PLAN)
    ctx.validate_plan(plan)
    upstream = c.inspect_source()
    registration = {
        "schema": "cells.betse_nonzero_dispatch_registration@1",
        "registered_utc": datetime.now(UTC).isoformat(),
        "plan": plan,
        "sources": old.sources(),
        "prior_review_sha256": ctx.PRIOR_SHA,
        "prelaunch_sha256": c.sha(ctx.PRELAUNCH),
        "preservation_sha256": c.sha(ctx.PRESERVATION),
        "upstream": upstream,
    }
    validate_registration(registration)
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    try:
        c.write(output / "registration.json", registration)
        with zipfile.ZipFile(
            output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for n in registration["sources"]:
                archive.write(c.HERE / n, arcname=n)
        remaining = plan["total_timeout_seconds"] - (time.monotonic() - started)
        c.require(remaining > 0, "Preparation total deadline exhausted")
        completed = execute_worker(output, plan, min(plan["worker_timeout_seconds"], remaining))
        c.require(
            completed.returncode == 0, "Native preparation failed; partial artifacts retained"
        )
        result = c.read(output / "worker.json")
        c.require(
            result["status"] == "nonzero_dispatch_checks_pass"
            and result["preparations"] == 4
            and result["event_dispatch_calls"] == 160
            and result["integration_calls"] == 0
            and result["trajectory_qualified"] is False,
            "Incomplete/overclaimed worker result",
        )
        total = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
        c.require(total < plan["max_artifact_bytes"], "Artifact limit exceeded")
        c.require(
            time.monotonic() - started < plan["total_timeout_seconds"],
            "Preparation total deadline exceeded",
        )
        c.write(
            output / "completion.json",
            {
                k: result[k]
                for k in (
                    "status",
                    "preparations",
                    "event_dispatch_calls",
                    "targeted_dispatches",
                    "nonzero_targeted_dispatches",
                    "control_values_checked",
                    "maximum_baseline_scaled_control_error",
                    "integration_calls",
                    "trajectory_run",
                    "trajectory_qualified",
                )
            }
            | {
                "elapsed_seconds": time.monotonic() - started,
                "artifact_bytes_before_receipt": total,
                "files_sha256": manifest(output),
            },
        )
        print(
            json.dumps(
                {k: v for k, v in c.read(output / "completion.json").items() if k != "files_sha256"}
            )
        )
    except Exception as error:
        c.write(
            output / "failure.json",
            {
                "status": "fail",
                "error": str(error),
                "traceback": traceback.format_exc(),
                "elapsed_seconds": time.monotonic() - started,
                "trajectory_qualified": False,
                "files_sha256": manifest(output),
            },
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "worker"))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if args.action == "preflight":
        preflight(output)
    else:
        try:
            c.write(output / "worker.json", worker(c.read(output / "registration.json"), output))
        except Exception as error:
            c.write(
                output / "worker-failure.json",
                {
                    "status": "fail",
                    "error": str(error),
                    "traceback": traceback.format_exc(),
                    "trajectory_qualified": False,
                },
            )
            raise
