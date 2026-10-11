"""Separate SIM-from-neutral preparation adapter; CLI cannot run a trajectory.

The prospective preflight writes inputs and a source capsule before native loading.
It requests four fresh preparations and zero-amplitude event dispatch, without
entering transport, concentration updates, a solver loop, or the Cells runtime.

The first candidate stopped at absent tissue-profile metadata. Its packet is
retained; a new early guard rejects that unamended plan. Preparation success and
full-loop observer noninterference remain unqualified until a versioned bridge.
"""

import argparse
import hashlib
import json
import os
import struct
import subprocess
import sys
import time
import traceback
import warnings
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import alignment as a
import contact as c
import phase_bridge_context as ctx
import trajectory as native
import trajectory_context as old
import trajectory_evidence as evidence
from native_event_observer import NativeEventObserver, PreparationFence
from trajectory_check import unpack

CORE_ARRAYS = ("cc_cells", "cc_env", "cc_at_mem", "Dm_cells", "P_cells", "zs")
EVENT_ARRAYS = CORE_ARRAYS + (
    "vm",
    "rho_cells",
    "I_mem",
    "Phi_b",
    "Dm_base",
    "Dm_scheduled",
    "P_base",
    "P_mod",
    "fluxes_mem",
    "fluxes_gj",
    "NaKATP_block",
    "CaATP_block",
    "gj_block",
)


def arrays(sim, names):
    import numpy as np

    # Blocks can be native integer scalars. Retain them as scalars, do not cast
    # native state arrays to conceal a dtype discrepancy.
    result = {}
    for name in names:
        value = getattr(sim, name)
        if name == "zs":
            c.require(
                isinstance(value, np.ndarray) and value.dtype == np.int64,
                "Native valence dtype changed",
            )
            result[name] = {
                "dtype": value.dtype.str,
                "shape": list(value.shape),
                "values": value.tolist(),
                "bytes_sha256": hashlib.sha256(value.tobytes(order="C")).hexdigest(),
            }
        else:
            result[name] = (
                native.array_record(value) if isinstance(value, np.ndarray) else {"scalar": value}
            )
    return result


def event_snapshot(sim):
    return {
        "arrays": arrays(sim, EVENT_ARRAYS),
        "temperature_K": float(sim.T),
        "rho_channel": sim.rho_channel,
        "rho_pump": sim.rho_pump,
    }


def geometry(phase):
    cells, p = phase.cells, phase.p
    return {
        "cell_count": len(cells.cell_i),
        "membrane_count": len(cells.mem_i),
        "cell_centres_m": cells.cell_centres.tolist(),
        "cell_volumes_m3": cells.cell_vol.tolist(),
        "cell_areas_m2": cells.cell_sa.tolist(),
        "membrane_owners": cells.mem_to_cells.tolist(),
        "membrane_areas_m2": cells.mem_sa.tolist(),
        "configured_bath_volume_m3": float(p.vol_env),
        "effective_bath_volume_m3": float(len(cells.mem_i) * p.vol_env),
        "specific_capacitance_F_per_m2": p.cm,
        "diviterm_m": cells.diviterm.tolist(),
        "grid_shape": list(cells.X.shape),
    }


def fresh_phase(row, directory, prior):
    """Normal native load, seed and fresh SIM/init_core; no high-level init/sim run."""
    import numpy as np
    from betse.science.enum.enumphase import SimPhaseKind
    from betse.science.parameters import Parameters
    from betse.science.phase.phasecls import SimPhase
    from betse.science.simrunner import SimRunner
    from ruamel.yaml import YAML

    protocol, mapped = ctx.mapping(row["case"], row["dt_s"], row["event_mode"])
    ctx.require_dispatch_profiles(protocol)
    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    with (c.SOURCE / "betse/data/yaml/sim_config.yaml").open() as handle:
        configuration = a.configuration(yaml.load(handle), protocol, directory)
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


def metadata(phase, mapped, prior):
    sim, p, dyna = phase.sim, phase.p, phase.dyna
    settings = {
        name: getattr(p, name)
        for name in prior["settings"]
        if name not in ("solver", "temperature_K")
    } | {"solver": p.solver_type.name, "temperature_K": p.T}
    return {
        "phase": phase.kind.name,
        "run_sim_flag": p._run_sim,
        "dt_s": p.dt,
        "duration_s": p.total_time,
        "sampling_s": p.resample,
        "sample_stride": p.t_resample,
        "configured_steps": p.sim_tsteps,
        "constants": {"F": p.F, "R": p.R},
        "geometry": geometry(phase),
        "settings": settings,
        "thickness_m": p.tm,
        "species": [k for k, enabled in p.ions_dict.items() if enabled],
        "moving_ion_indices": [int(i) for i in sim.movingIons],
        "scheduled_options": p.scheduled_options,
        "global_options": p.global_options,
        "cut_event_enabled": dyna.event_cut is not None,
        "voltage_event_enabled": dyna._event_voltage is not None,
        "default_profile": dyna.tissue_default.name,
        "default_diffusion_m2_per_s": {
            ion: getattr(dyna.tissue_default, "Dm_" + ion)
            for ion in prior["base_protocol"]["expected_species"]
        },
        "profile_targets": {
            key: [int(i) for i in value] for key, value in dyna.tissue_target_inds.items()
        },
        "event_targets": {
            ion: [int(i) for i in getattr(dyna, "targets_" + ion + "mem")]
            for ion in ("Na", "K", "Cl")
            if mapped["event_mode"] == "zero_amplitude"
        },
        "init_pickle_path": p.init_pickle_filename,
        "sim_pickle_path": p.sim_pickle_filename,
        "init_pickle_present": Path(p.init_pickle_filename).is_file(),
        "sim_pickle_present": Path(p.sim_pickle_filename).is_file(),
    }


def check_preparation(row, result, prior, retained):
    """Exact preparation/input gates only, not a trajectory acceptance checker."""
    _, mapped = ctx.mapping(row["case"], row["dt_s"], row["event_mode"])
    m, initial = result["metadata"], result["initial"]
    c.require(result["row"] == row, "Preparation row changed")
    for key in ("core", "after_dynamics_core"):
        check_arrays(result[key], CORE_ARRAYS)
    for state in (result["event_initial"], result["event_final"]):
        check_arrays(state["arrays"], EVENT_ARRAYS)
    c.require(result["mapping"] == mapped, "Preparation mapping changed")
    c.require(
        m["phase"] == "SIM"
        and m["run_sim_flag"] is True
        and m["dt_s"] == m["sampling_s"] == row["dt_s"]
        and m["sample_stride"] == 1
        and m["duration_s"] == mapped["duration_s"]
        and m["configured_steps"] == mapped["steps"],
        "Native SIM clock not selected",
    )
    c.require(
        m["geometry"] == prior["geometry"]
        and m["settings"] == prior["settings"]
        and m["constants"] == prior["base_protocol"]["profiles"][row["profile"]]
        and m["thickness_m"] == prior["base_protocol"]["thickness_m"]
        and m["species"] == prior["base_protocol"]["expected_species"],
        "Preparation geometry/settings/species/constants changed",
    )
    c.require(result["core"] == result["after_dynamics_core"], "Dynamics changed core preparation")
    c.require(initial == retained["trace"]["initial"], "SIM preparation differs from retained INIT")
    state = result["event_initial"]
    c.require(
        state["temperature_K"] == m["settings"]["temperature_K"]
        and state["rho_channel"] == state["rho_pump"] == 1,
        "Event preparation changes temperature/channel/pump scaling",
    )
    event_arrays = state["arrays"]
    c.require(
        {key: event_arrays[key] for key in CORE_ARRAYS} == result["after_dynamics_core"],
        "Post-closure core arrays changed",
    )
    links = {
        "inside_mM": "cc_cells",
        "outside_mM": "cc_env",
        "voltage_V": "vm",
        "rho_C_per_m3": "rho_cells",
        "inward_current_A": "I_mem",
        "boundary_voltage_V": "Phi_b",
    }
    c.require(
        initial == {key: event_arrays[name]["values"] for key, name in links.items()},
        "Prepared state copies disagree",
    )
    c.require(event_arrays["Dm_cells"] == event_arrays["Dm_base"], "Diffusion baseline changed")
    c.require(
        event_arrays["zs"]["values"] == prior["base_protocol"]["expected_valence"],
        "Valence changed",
    )
    c.require(m["moving_ion_indices"] == list(range(6)), "Native moving-ion dispatch changed")
    for name in ("Dm_scheduled", "P_cells", "P_base", "P_mod", "fluxes_mem", "fluxes_gj"):
        values = event_arrays[name]["values"]
        c.require(all(v == 0 for v in flatten(values)), "Nonzero prepared " + name)
    for name in ("NaKATP_block", "CaATP_block", "gj_block"):
        value = event_arrays[name]
        c.require(
            all(v == 1 for v in flatten(value.get("values", value.get("scalar")))),
            "Pump/GJ block changed",
        )
    expected_permeabilities = [
        v * row["case"]["availability"] for v in prior["base_protocol"]["permeability_m_per_s"]
    ]
    for i, ion in enumerate(m["species"]):
        diffusion = m["default_diffusion_m2_per_s"][ion]
        # Match saved native diffusion bytes; do not reconstruct Dm by reversed
        # division/multiplication and introduce a rounding-dependent criterion.
        c.require(
            all(v == diffusion for v in event_arrays["Dm_cells"]["values"][i])
            and all(
                v / m["thickness_m"] == retained["permeability_m_per_s"][i][0]
                for v in event_arrays["Dm_cells"]["values"][i]
            )
            and abs(diffusion / m["thickness_m"] - expected_permeabilities[i]) <= 1e-24,
            "Native baseline permeability changed",
        )
    targets = list(range(m["geometry"]["membrane_count"]))
    c.require(
        m["default_profile"] == mapped["target_profile"]
        and m["profile_targets"] == {mapped["target_profile"]: targets},
        "Default target map differs",
    )
    for ion in ("Na", "K", "Cl"):
        expected = (
            0
            if row["event_mode"] == "disabled"
            else [*mapped["mapped_pulse_times_s"], 0.0, [mapped["target_profile"]], "None"]
        )
        c.require(
            m["scheduled_options"][ion + "_mem"] == expected, "Native scheduled input differs"
        )
    c.require(
        m["event_targets"]
        == ({} if row["event_mode"] == "disabled" else {ion: targets for ion in ("Na", "K", "Cl")})
        and all(
            v == 0
            for k, v in m["scheduled_options"].items()
            if k not in ("Na_mem", "K_mem", "Cl_mem")
        )
        and all(v == 0 for v in m["global_options"].values())
        and not m["cut_event_enabled"]
        and not m["voltage_event_enabled"],
        "Unexpected event or target",
    )
    c.require(
        not m["init_pickle_present"]
        and not m["sim_pickle_present"]
        and m["init_pickle_path"] != m["sim_pickle_path"],
        "Unexpected trajectory pickle",
    )
    probe = result["dispatch_probe"]
    labels = [
        mapped["raw_clock_scale"] * t for t in ctx.preflight_plan()["dispatch_elapsed_times_s"]
    ]
    c.require(
        probe["mode"] == "preparation_dispatch_only"
        and probe["integration_calls"] == 0
        and probe["hook_restored"] is True
        and len(probe["events"]) == len(labels),
        "Dispatch probe coverage differs",
    )
    for index, event in enumerate(probe["events"]):
        for key in ("before", "after"):
            check_arrays(event[key]["arrays"], EVENT_ARRAYS)
        c.require(
            event["index"] == index
            and event["raw_label_s"] == labels[index]
            and event["before"] == event["after"] == state
            and event["flux_ion_indices"] == [],
            "No-op dispatch changed native state/control bytes or labels",
        )
    c.require(result["event_final"] == state, "Post-probe preparation changed")


def check_arrays(records, names):
    c.require(set(records) == set(names), "Preparation array coverage differs")
    for name, record in records.items():
        if name == "zs":
            c.require(
                record["dtype"] == "<i8"
                and record["shape"] == [6]
                and len(record["values"]) == 6
                and all(type(v) is int for v in record["values"])
                and hashlib.sha256(struct.pack("<6q", *record["values"])).hexdigest()
                == record["bytes_sha256"],
                "Valence export bytes differ",
            )
        elif "scalar" in record:
            c.require(
                name in ("NaKATP_block", "gj_block")
                and set(record) == {"scalar"}
                and type(record["scalar"]) is int
                and record["scalar"] == 1,
                "Unexpected native scalar",
            )
        else:
            unpack(record)


def flatten(value):
    if isinstance(value, list):
        for item in value:
            yield from flatten(item)
    else:
        yield value


def prepare_worker(registration, output):
    import betse
    import numpy as np

    package = Path(betse.__file__).resolve().parent
    installed = {f"betse/{p.relative_to(package)}": c.sha(p) for p in package.rglob("*.py")}
    prior = evidence.trusted_registration()
    expected = {
        k: v
        for k, v in prior["upstream"]["files_sha256"].items()
        if k.startswith("betse/") and k.endswith(".py")
    }
    c.require(
        installed == expected and package.is_relative_to(c.REFERENCE_PYTHON.parent.parent),
        "Wrong native installation",
    )
    plan = registration["plan"]
    c.require(plan == ctx.preflight_plan(), "Preflight plan changed")
    c.require(registration["sources"] == old.sources(), "Registered adapter sources changed")
    c.require(
        registration["upstream_files_sha256"] == prior["upstream"]["files_sha256"],
        "Native source pin differs",
    )
    results = []
    with (
        warnings.catch_warnings(record=True) as caught,
        np.errstate(over="raise", invalid="raise", divide="raise"),
    ):
        warnings.simplefilter("error", RuntimeWarning)
        for index, row in enumerate(plan["rows"]):
            directory = output / f"preparation-{index:02d}"
            directory.mkdir(exist_ok=False)
            with PreparationFence(package / "science") as fence:
                phase, mapped = fresh_phase(row, directory, prior)
                core = arrays(phase.sim, CORE_ARRAYS)
                phase.sim.init_dynamics(phase)
                after_dynamics = arrays(phase.sim, CORE_ARRAYS)
                phase.sim.clear_storage(phase.cells, phase.p)
                phase.sim.update_V(phase.cells, phase.p)
            initial, event_initial = native.native_snapshot(phase.sim), event_snapshot(phase.sim)
            raw = [mapped["raw_clock_scale"] * t for t in plan["dispatch_elapsed_times_s"]]
            observer = NativeEventObserver(
                phase,
                package / "science",
                native.native_snapshot,
                native.native_fluxes,
                event_snapshot,
                raw,
            )
            with observer:
                for label in raw:
                    phase.dyna.fire_events(phase=phase, t=label)
            result = {
                "row": row,
                "mapping": mapped,
                "core": core,
                "after_dynamics_core": after_dynamics,
                "initial": initial,
                "event_initial": event_initial,
                "event_final": event_snapshot(phase.sim),
                "metadata": metadata(phase, mapped, prior),
                "dispatch_probe": observer.event_result(),
                "preparation_calls": fence.calls,
                "native_yaml_sha256": c.sha(directory / "native.yaml"),
            }
            # Save first; a failed gate never erases the actual preparation.
            c.write(directory / "result.json", result)
            retained_path = (
                evidence.SESSION
                / "native"
                / old.key(row["case"]["id"], row["profile"], row["dt_s"])
                / "observed/result.json"
            )
            retained = c.read(retained_path)
            check_preparation(row, result, prior, retained)
            results.append(
                {
                    "path": str((directory / "result.json").relative_to(output)),
                    "sha256": c.sha(directory / "result.json"),
                    "retained_init_sha256": c.sha(retained_path),
                }
            )
        c.require(not caught, "Native preparation emitted warnings")
    c.require(
        not any(n == "cells" or n.startswith("cells.") for n in sys.modules),
        "Preflight imported Cells",
    )
    return {
        "schema": "cells.betse_phase_bridge_preflight_result@1",
        "status": "preparation_checks_pass",
        "results": results,
        "installed_python_sha256": installed,
        "preparations": len(results),
        "event_dispatch_calls": len(results) * len(plan["dispatch_elapsed_times_s"]),
        "integration_calls": 0,
        "trajectory_run": False,
        "trajectory_qualified": False,
        "full_loop_observer_runtime_tested": False,
        "warnings": [],
    }


def preflight(output):
    ctx.authenticate()
    c.require(ctx.PRESERVATION.is_file(), "Preserve prior files first")
    plan = ctx.preflight_plan()
    # The retained first attempt exposed this missing prerequisite. Reject the
    # unamended candidate before another worker or output directory is created.
    for row in plan["rows"]:
        protocol, _ = ctx.mapping(row["case"], row["dt_s"], row["event_mode"])
        ctx.require_dispatch_profiles(protocol)
    output.mkdir(parents=True, exist_ok=False)
    registered = {
        "schema": "cells.betse_phase_bridge_preflight_registration@1",
        "created_utc": datetime.now(UTC).isoformat(),
        "plan": plan,
        "sources": old.sources(),
        "upstream_files_sha256": evidence.trusted_registration()["upstream"]["files_sha256"],
        "preservation_sha256": c.sha(ctx.PRESERVATION),
    }
    c.require(ctx.FILES <= set(registered["sources"]), "Missing preflight source")
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
        c.require(completed.returncode == 0, "Native preparation worker failed; see worker.log")
        worker = c.read(output / "worker.json")
        total = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
        c.require(total < plan["max_artifact_bytes"], "Preflight artifact budget exceeded")
        c.write(
            output / "completion.json",
            {
                "status": worker["status"],
                "elapsed_seconds": time.monotonic() - started,
                "registration_sha256": c.sha(output / "registration.json"),
                "sources_zip_sha256": c.sha(output / "sources.zip"),
                "worker_sha256": c.sha(output / "worker.json"),
                "artifact_bytes_before_receipt": total,
                "integration_calls": 0,
                "trajectory_run": False,
                "trajectory_qualified": False,
            },
        )
        print(json.dumps(c.read(output / "completion.json")))
    except Exception as error:
        c.write(
            output / "failure.json",
            {
                "status": "fail",
                "error": str(error),
                "traceback": traceback.format_exc(),
                "elapsed_seconds": time.monotonic() - started,
                "trajectory_qualified": False,
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
        c.write(
            destination / "worker.json",
            prepare_worker(c.read(destination / "registration.json"), destination),
        )
