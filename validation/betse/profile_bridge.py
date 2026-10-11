"""Explicit default-profile preparation bridge with durable intermediate evidence.

This CLI can prepare and dispatch zero-amplitude native events, not integrate a
trajectory. Frozen REF-003d/D073 adapters and production remain unchanged.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
import warnings
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import alignment as alignment
import contact as c
import phase_bridge as legacy
import profile_bridge_check as check
import profile_bridge_context as ctx
import trajectory as native
import trajectory_context as old
import trajectory_evidence as evidence
from native_event_observer import NativeEventObserver, PreparationFence


def write_stage(directory, name, payload):
    c.require(name in check.STAGES, "Unknown preparation stage")
    path = directory / (name + ".json")
    c.write(path, payload)
    return c.sha(path)


def save_ready_before_metadata(directory, ready, metadata_factory):
    """A metadata exception must not discard the already copied physical state."""
    write_stage(directory, "ready", ready)
    result = metadata_factory()
    write_stage(directory, "metadata", result)
    return result


def junctions(phase):
    return {
        "weights": native.array_record(phase.cells.gj_default_weights),
        "membrane_neighbours": [int(i) for i in phase.cells.nn_i],
        "cell_neighbours": [[int(i) for i in indices] for indices in phase.cells.cell_nn_connected],
    }


def core_snapshot(phase):
    return {
        "arrays": legacy.arrays(phase.sim, legacy.CORE_ARRAYS),
        "geometry": legacy.geometry(phase),
        "junctions": junctions(phase),
    }


def metadata(phase, directory, mapped, prior):
    sim, p, dyna = phase.sim, phase.p, phase.dyna
    species = [key for key, enabled in p.ions_dict.items() if enabled]

    def profile_record(profile):
        if profile is None:
            return None
        return {
            "name": profile.name,
            "diffusion_m2_per_s": {ion: float(getattr(profile, "Dm_" + ion)) for ion in species},
        }

    paths = {
        name: Path(getattr(p, name + "_pickle_filename")).resolve()
        for name in ("seed", "init", "sim")
    }
    c.require(
        all(path.is_relative_to(directory) for path in paths.values()),
        "Native outputs escape preparation directory",
    )
    return {
        "phase": phase.kind.name,
        "run_sim_flag": p._run_sim,
        "profiles_enabled": p.is_tissue_profiles,
        "dt_s": p.dt,
        "duration_s": p.total_time,
        "sampling_s": p.resample,
        "sample_stride": p.t_resample,
        "configured_steps": p.sim_tsteps,
        "constants": {"F": p.F, "R": p.R},
        "geometry": legacy.geometry(phase),
        "settings": {
            name: getattr(p, name)
            for name in prior["settings"]
            if name not in ("solver", "temperature_K")
        }
        | {"solver": p.solver_type.name, "temperature_K": p.T},
        "thickness_m": p.tm,
        "species": species,
        "moving_ion_indices": [int(i) for i in sim.movingIons],
        "configured_default": profile_record(p.tissue_default),
        "resolved_default": profile_record(getattr(dyna, "tissue_default", None)),
        "profile_names": list(dyna.tissue_name_to_profile),
        "additional_profile_count": len(p.tissue_profiles),
        "cut_profile_count": len(p.cut_profiles),
        "membrane_targets": {
            name: [int(i) for i in indices] for name, indices in dyna.tissue_target_inds.items()
        },
        "cell_targets": {
            name: [int(i) for i in indices] for name, indices in dyna.cell_target_inds.items()
        },
        "scheduled_options": p.scheduled_options,
        "global_options": p.global_options,
        "cut_event_configured": bool(p._conf["cutting event"]["event happens"]),
        "cut_event_enabled": dyna.event_cut is not None,
        "voltage_event_configured": bool(p._conf["apply external voltage"]["event happens"]),
        "voltage_event_enabled": dyna._event_voltage is not None,
        "event_targets": {
            ion: [int(i) for i in getattr(dyna, "targets_" + ion + "mem")]
            for ion in ("Na", "K", "Cl")
            if mapped["event_mode"] == "zero_amplitude"
        },
        "paths": {name: str(path.relative_to(directory)) for name, path in paths.items()},
        "pickles_present": {name: path.is_file() for name, path in paths.items()},
    }


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
    c.require(
        p.is_tissue_profiles is mapped["profiles_enabled"], "Native profile configuration differs"
    )
    constants = prior["base_protocol"]["profiles"][row["profile"]]
    p.F, p.R = constants["F"], constants["R"]
    np.random.seed(prior["base_protocol"]["seed"])
    seeded = SimRunner(p).seed()
    phase = SimPhase(kind=SimPhaseKind.SIM, cells=seeded.cells, p=p)
    phase.sim.init_core(phase)
    return phase, mapped


def prepare_row(row, directory, prior, package, plan):
    directory.mkdir(exist_ok=False)
    packet = {}
    with PreparationFence(package / "science") as fence:
        phase, mapped = fresh_phase(row, directory, prior)
        packet["core"] = core_snapshot(phase)
        write_stage(directory, "core", packet["core"])
        phase.sim.init_dynamics(phase)
        packet["dynamics"] = core_snapshot(phase)
        write_stage(directory, "dynamics", packet["dynamics"])
        phase.sim.clear_storage(phase.cells, phase.p)
        phase.sim.update_V(phase.cells, phase.p)
    packet["ready"] = {
        "row": row,
        "mapping": mapped,
        "state": legacy.event_snapshot(phase.sim),
        "initial": native.native_snapshot(phase.sim),
        "preparation_calls": fence.calls,
        "hook_restored": sys.getprofile() is None,
    }
    packet["metadata"] = save_ready_before_metadata(
        directory, packet["ready"], lambda: metadata(phase, directory, mapped, prior)
    )
    # Validate the resolved prerequisite before attempting any dispatch. The
    # already saved core/dynamics/ready/metadata records survive a failed gate.
    check.check_metadata(row, packet["metadata"], prior, mapped)
    labels = [mapped["raw_clock_scale"] * t for t in plan["dispatch_elapsed_times_s"]]
    observer = NativeEventObserver(
        phase,
        package / "science",
        native.native_snapshot,
        native.native_fluxes,
        legacy.event_snapshot,
        labels,
    )
    with observer:
        for t in labels:
            phase.dyna.fire_events(phase=phase, t=t)
    packet["dispatch"] = observer.event_result()
    write_stage(directory, "dispatch", packet["dispatch"])
    packet["final"] = {
        "state": legacy.event_snapshot(phase.sim),
        "metadata": metadata(phase, directory, mapped, prior),
        "junctions": junctions(phase),
    }
    write_stage(directory, "final", packet["final"])
    retained_path = (
        evidence.SESSION
        / "native"
        / old.key(row["case"]["id"], row["profile"], row["dt_s"])
        / "observed/result.json"
    )
    result = check.check_row(row, packet, prior, c.read(retained_path), plan)
    c.write(
        directory / "result.json",
        result
        | {
            "row": row,
            "files_sha256": {
                name + ".json": c.sha(directory / (name + ".json")) for name in check.STAGES
            },
            "native_yaml_sha256": c.sha(directory / "native.yaml"),
            "retained_init_sha256": c.sha(retained_path),
            "trajectory_qualified": False,
        },
    )
    return packet


def worker(registration, output):
    import betse
    import numpy as np

    package = Path(betse.__file__).resolve().parent
    prior = evidence.trusted_registration()
    expected = {
        name: digest
        for name, digest in prior["upstream"]["files_sha256"].items()
        if name.startswith("betse/") and name.endswith(".py")
    }
    installed = {
        "betse/" + str(path.relative_to(package)): c.sha(path) for path in package.rglob("*.py")
    }
    c.require(
        installed == expected and package.is_relative_to(c.REFERENCE_PYTHON.parent.parent),
        "Wrong native installation",
    )
    plan = registration["plan"]
    ctx.validate_plan(plan)
    c.require(
        plan == c.read(ctx.PLAN) and registration["sources"] == old.sources(),
        "Registered preparation inputs/sources changed",
    )
    c.require(registration["prior_handoff_sha256"] == ctx.PRIOR_SHA, "Prior handoff differs")
    c.require(
        registration["upstream"]["files_sha256"] == prior["upstream"]["files_sha256"]
        and c.sha(c.SOURCE / "betse/data/yaml/sim_config.yaml")
        == prior["upstream"]["files_sha256"]["betse/data/yaml/sim_config.yaml"],
        "Native configuration source changed",
    )
    packets, results = {}, []
    with (
        warnings.catch_warnings(record=True) as caught,
        np.errstate(over="raise", invalid="raise", divide="raise"),
    ):
        warnings.simplefilter("error", RuntimeWarning)
        for index, row in enumerate(ctx.rows(plan)):
            directory = output / f"preparation-{index:02d}"
            packet = prepare_row(row, directory, prior, package, plan)
            packets[row["case"]["id"], row["variant"]] = packet
            results.append(
                {
                    "path": str((directory / "result.json").relative_to(output)),
                    "sha256": c.sha(directory / "result.json"),
                }
            )
        c.require(not caught, "Preparation emitted Python warnings")
    comparison = check.check_controls(packets, plan)
    c.require(
        not any(name == "cells" or name.startswith("cells.") for name in sys.modules),
        "Native preparation imported Cells",
    )
    return {
        "schema": "cells.betse_profile_bridge_preflight_result@2",
        "status": "preparation_checks_pass",
        "results": results,
        "controls": comparison,
        "preparations": len(results),
        "event_dispatch_calls": len(results) * len(plan["dispatch_elapsed_times_s"]),
        "installed_python_sha256": installed,
        "environment": c.environment(),
        "warnings": [],
        "integration_calls": 0,
        "trajectory_run": False,
        "trajectory_qualified": False,
        "full_loop_observer_runtime_tested": False,
    }


def preflight(output):
    ctx.authenticate()
    plan = c.read(ctx.PLAN)
    ctx.validate_plan(plan)
    for row in ctx.rows(plan):
        ctx.mapping(row)
    c.require(ctx.PRESERVATION.is_file(), "Preserve prior evidence first")
    upstream = c.inspect_source()
    c.require(
        upstream["files_sha256"] == evidence.trusted_registration()["upstream"]["files_sha256"],
        "Native source checkout differs from accepted baseline",
    )
    output.mkdir(parents=True, exist_ok=False)
    registered = {
        "schema": "cells.betse_profile_bridge_preflight_registration@2",
        "registered_utc": datetime.now(UTC).isoformat(),
        "plan": plan,
        "prior_handoff_sha256": ctx.PRIOR_SHA,
        "sources": old.sources(),
        "upstream": upstream,
        "preservation_sha256": c.sha(ctx.PRESERVATION),
    }
    c.require(ctx.FILES <= set(registered["sources"]), "Missing preparation source")
    c.write(output / "registration.json", registered)
    with zipfile.ZipFile(output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in registered["sources"]:
            archive.write(c.HERE / name, arcname=name)
    started = time.monotonic()
    try:
        with (output / "worker.log").open("x") as log:
            completed = subprocess.run(
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
                env=os.environ | {"PYTHONDONTWRITEBYTECODE": "1", "MPLBACKEND": "Agg"},
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=plan["worker_timeout_seconds"],
                check=False,
            )
        c.require(
            completed.returncode == 0,
            "Native preparation failed; partial states and worker.log retained",
        )
        result = c.read(output / "worker.json")
        total = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
        c.require(total < plan["max_artifact_bytes"], "Preparation artifact limit exceeded")
        manifest = {
            str(path.relative_to(output)): c.sha(path)
            for path in sorted(output.rglob("*"))
            if path.is_file()
        }
        c.write(
            output / "completion.json",
            {
                "status": result["status"],
                "elapsed_seconds": time.monotonic() - started,
                "files_sha256": manifest,
                "artifact_bytes_before_receipt": total,
                "preparations": result["preparations"],
                "event_dispatch_calls": result["event_dispatch_calls"],
                "integration_calls": 0,
                "trajectory_run": False,
                "trajectory_qualified": False,
            },
        )
        print(
            json.dumps(
                {
                    key: value
                    for key, value in c.read(output / "completion.json").items()
                    if key != "files_sha256"
                }
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
                "files_sha256": {
                    str(path.relative_to(output)): c.sha(path)
                    for path in sorted(output.rglob("*"))
                    if path.is_file()
                },
            },
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "worker"))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    destination = args.output.resolve()
    if args.command == "preflight":
        preflight(destination)
    else:
        try:
            c.write(
                destination / "worker.json",
                worker(c.read(destination / "registration.json"), destination),
            )
        except Exception as error:
            c.write(
                destination / "worker-failure.json",
                {
                    "status": "fail",
                    "error": str(error),
                    "traceback": traceback.format_exc(),
                    "trajectory_qualified": False,
                },
            )
            raise
