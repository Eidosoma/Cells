"""Actual finer native preparation/dispatch only; no full-loop or Cells call."""

import argparse
import importlib
import resource
import sys
import traceback
import warnings
from pathlib import Path

import refined_dispatch_check as check
import refined_dispatch_context as ctx

c = ctx.c
legacy = importlib.import_module("dispatch_preflight")
base, snapshot, native = legacy.base, legacy.snapshot, legacy.native


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
        configuration = legacy.alignment.configuration(yaml.load(handle), protocol, directory)
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


def prepare_row(row, directory, prior, package, plan):
    directory.mkdir(parents=True, exist_ok=False)
    packet = {}
    with legacy.PreparationFence(package / "science") as fence:
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
    with legacy.PreparationFence(package / "science"):
        packet["metadata"] = base.save_ready_before_metadata(
            directory, packet["ready"], lambda: legacy.metadata(phase, directory, mapped, prior)
        )
    original, preparation, references = legacy.retained(row)
    check.check_prepared(row, packet, prior, original, plan, preparation)
    # Reuse the unmodified read-only event observer and per-event durable writer.
    packet["dispatch"] = legacy.dispatch(phase, package, mapped, directory)
    base.write_stage(directory, "dispatch", packet["dispatch"])
    with legacy.PreparationFence(package / "science"):
        packet["final"] = {
            "state": snapshot.event_snapshot(phase.sim),
            "metadata": legacy.metadata(phase, directory, mapped, prior),
            "junctions": base.junctions(phase),
        }
    base.write_stage(directory, "final", packet["final"])
    result = check.check_row(row, packet, prior, original, plan, preparation)
    c.write(
        directory / "result.json",
        result
        | {
            "row": row,
            "retained_files_sha256": references,
            "files_sha256": ctx.audit_context.packet_hashes(directory),
        },
    )
    return packet, result


def worker(registered, output):
    import betse
    import numpy as np
    import refined_dispatch_job as job

    job.validate_registration(registered)
    plan = registered["plan"]
    resource.setrlimit(resource.RLIMIT_FSIZE, (plan["max_worker_file_bytes"],) * 2)
    prior = ctx.legacy.evidence.trusted_registration()
    package = Path(betse.__file__).resolve().parent
    installed = {"betse/" + str(p.relative_to(package)): c.sha(p) for p in package.rglob("*.py")}
    expected = {
        n: h
        for n, h in registered["upstream"]["files_sha256"].items()
        if n.startswith("betse/") and n.endswith(".py")
    }
    environment = c.environment()
    c.require(
        installed == expected
        and len(installed) == 332
        and package.is_relative_to(c.REFERENCE_PYTHON.parent.parent)
        and environment["packages"] == c.locked_reference_packages()
        and environment["executable"] == str(c.REFERENCE_PYTHON)
        and environment["python"] == "3.13.5",
        "Wrong native installation/runtime",
    )
    results, controls = [], {}
    with (
        warnings.catch_warnings(record=True) as caught,
        np.errstate(over="raise", invalid="raise", divide="raise"),
    ):
        warnings.simplefilter("error", RuntimeWarning)
        for h in plan["hold_steps_s"]:
            packets = {}
            for row in [r for r in ctx.rows(plan) if r["dt_s"] == h]:
                packet, result = prepare_row(row, output / ctx.key(row), prior, package, plan)
                packets[row["condition"]] = packet
                results.append(
                    result
                    | {
                        "row": row,
                        "path": ctx.key(row) + "/result.json",
                        "sha256": c.sha(output / ctx.key(row) / "result.json"),
                    }
                )
                c.require(
                    sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
                    < plan["max_artifact_bytes"] - 1024**2,
                    "Artifact budget exhausted",
                )
            controls[f"{h:.8f}"] = check.legacy.check_controls(packets, plan)
        c.require(not caught, "Native preparation emitted Python warnings")
    c.require(
        not any(n.split(".")[0] in ("cells", "jax") for n in sys.modules),
        "Native preflight imported Cells/JAX",
    )
    result = {
        "schema": "cells.betse_refined_dispatch_worker@1",
        "status": "refined_dispatch_checks_pass",
        "preparations": len(results),
        "event_dispatch_calls": sum(r["event_dispatch_calls"] for r in results),
        "targeted_dispatches": sum(
            r["event_dispatch_calls"]
            for r in results
            if r["row"]["condition"] in ("zero_amplitude", "suppression_recovery")
        ),
        "nonzero_targeted_dispatches": sum(
            r["event_dispatch_calls"]
            for r in results
            if r["row"]["condition"] == "suppression_recovery"
        ),
        "control_values_checked": sum(r["control_values_checked"] for r in results),
        "maximum_baseline_scaled_control_error": max(
            r["maximum_baseline_scaled_control_error"] for r in results
        ),
        "results": results,
        "controls": controls,
        "installed_python_sha256": installed,
        "package_path": str(package),
        "environment": environment,
        "warnings": [],
        "registration_sha256": c.sha(output / "registration.json"),
        "sources": registered["sources"],
        "integration_calls": 0,
    } | dict.fromkeys(ctx.FALSE_FLAGS, False)
    job.validate_worker(result, registered, output)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    destination = args.output.resolve()
    try:
        c.write(
            destination / "worker.json",
            worker(c.read(destination / "registration.json"), destination),
        )
    except BaseException:
        c.write(
            destination / "worker-failure.json",
            {
                "status": "native_preflight_failed",
                "traceback": traceback.format_exc(),
                "trajectory_qualified": False,
                "automatic_retry": False,
            },
        )
        raise
