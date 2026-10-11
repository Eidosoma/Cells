"""Registered native FULL/Cells checked-RK4 panel, with detached bounded execution."""

import argparse
import hashlib
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

import alignment as a
import cluster_alignment as cluster
import cluster_evidence as evidence
import contact as c
import trajectory_context as ctx
from native_observer import NativeStepObserver


def native_snapshot(sim):
    return {
        "inside_mM": sim.cc_cells.tolist(),
        "outside_mM": sim.cc_env.tolist(),
        "voltage_V": sim.vm.tolist(),
        "rho_C_per_m3": sim.rho_cells.tolist(),
        "inward_current_A": sim.I_mem.tolist(),
        "boundary_voltage_V": sim.Phi_b.tolist(),
    }


def native_fluxes(sim):
    return {
        "density_mol_per_m2_s": sim.fluxes_mem.tolist(),
        "junction_density_mol_per_m2_s": sim.fluxes_gj.tolist(),
    }


def array_record(value):
    import numpy as np

    array = np.asarray(value)
    c.require(
        array.dtype == np.float64 and np.isfinite(array).all(), "Non-float64/nonfinite export"
    )
    return {
        "dtype": array.dtype.str,
        "shape": list(array.shape),
        "values": array.tolist(),
        "bytes_sha256": hashlib.sha256(array.tobytes(order="C")).hexdigest(),
    }


def native_worker(registered, output):
    import betse
    import numpy as np
    from betse.science.enum.enumphase import SimPhaseKind
    from betse.science.parameters import Parameters
    from betse.science.phase.phasecls import SimPhase
    from betse.science.simrunner import SimRunner
    from ruamel.yaml import YAML

    protocol = registered["protocol"]
    package = Path(betse.__file__).resolve().parent
    installed = {f"betse/{p.relative_to(package)}": c.sha(p) for p in package.rglob("*.py")}
    expected = {
        k: v
        for k, v in registered["upstream"]["files_sha256"].items()
        if k.startswith("betse/") and k.endswith(".py")
    }
    c.require(installed == expected, "Installed BETSE differs")
    c.require(package.is_relative_to(c.REFERENCE_PYTHON.parent.parent), "Wrong BETSE import")
    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    with (c.SOURCE / "betse/data/yaml/sim_config.yaml").open() as handle:
        yaml_base = yaml.load(handle)
    results = {}
    for case in protocol["cases"]:
        for profile in protocol["native_constant_profiles"]:
            constants = registered["base_protocol"]["profiles"][profile]
            for dt in protocol["native_steps_s"]:
                identifier = ctx.key(case["id"], profile, dt)
                paired = {}
                for mode in ("observed", "unobserved"):
                    directory = output / "native" / identifier / mode
                    directory.mkdir(parents=True, exist_ok=False)
                    config = a.configuration(yaml_base, ctx.native_protocol(case, dt), directory)
                    with (directory / "native.yaml").open("x") as handle:
                        yaml.dump(config, handle)
                    p = Parameters()
                    p.load(str(directory / "native.yaml"))
                    p.F, p.R = constants["F"], constants["R"]
                    np.random.seed(registered["base_protocol"]["seed"])
                    seeded = SimRunner(p).seed()
                    cells = seeded.cells
                    actual_geometry = {
                        "cell_count": len(cells.cell_i),
                        "membrane_count": len(cells.mem_i),
                        "cell_centres_m": cells.cell_centres.tolist(),
                        "cell_volumes_m3": cells.cell_vol.tolist(),
                        "cell_areas_m2": cells.cell_sa.tolist(),
                        "membrane_owners": cells.mem_to_cells.tolist(),
                        "membrane_areas_m2": cells.mem_sa.tolist(),
                    }
                    c.require(
                        actual_geometry
                        == {k: registered["geometry"][k] for k in cluster.GEOMETRY_FIELDS},
                        "Native seeded geometry changed",
                    )
                    phase = SimPhase(kind=SimPhaseKind.INIT, cells=cells, p=p)
                    sim = phase.sim
                    sim.init_core(phase)
                    observer = NativeStepObserver(
                        sim, package / "science/sim.py", native_snapshot, native_fluxes
                    )
                    if mode == "observed":
                        with observer:
                            sim.run_sim_core(phase)
                    else:
                        sim.run_sim_core(phase)
                    settings = {
                        name: getattr(p, name)
                        for name in registered["settings"]
                        if name not in ("solver", "temperature_K")
                    } | {"solver": p.solver_type.name, "temperature_K": p.T}
                    c.require(settings == registered["settings"], "Native mechanism flags changed")
                    trace = observer.result() if mode == "observed" else None
                    if trace is not None:
                        for step in trace["steps"]:
                            # Derived update-clock columns, never substitutes for native labels.
                            step["before_elapsed_s"] = step["index"] * p.dt
                            step["after_elapsed_s"] = (step["index"] + 1) * p.dt
                    record = {
                        "id": identifier,
                        "mode": mode,
                        "dt_s": p.dt,
                        "constants": {"F": p.F, "R": p.R},
                        "geometry": actual_geometry,
                        "settings": settings,
                        "rho_channel": sim.rho_channel,
                        "species": [k for k, v in p.ions_dict.items() if v],
                        "valence": sim.zs.tolist(),
                        "permeability_m_per_s": (sim.Dm_cells / p.tm).tolist(),
                        "configured_steps": p.init_tsteps,
                        "ordinary": {
                            name: array_record(getattr(sim, name)) for name in ctx.ORDINARY_NAMES
                        },
                        "final": {
                            name: array_record(getattr(sim, name)) for name in ctx.FINAL_NAMES
                        },
                        "trace": trace,
                        "native_yaml_sha256": c.sha(directory / "native.yaml"),
                        "native_pickle_present": Path(p.init_pickle_filename).is_file(),
                    }
                    c.write(directory / "result.json", record)
                    paired[mode] = record
                c.require(
                    paired["observed"]["ordinary"] == paired["unobserved"]["ordinary"]
                    and paired["observed"]["final"] == paired["unobserved"]["final"],
                    "Observer changes exported native arrays",
                )
                results[identifier] = {
                    mode: str(
                        (output / "native" / identifier / mode / "result.json").relative_to(output)
                    )
                    for mode in paired
                }
                print(json.dumps({"native_pair_completed": identifier}), flush=True)
    c.require(
        not any(n == "cells" or n.startswith("cells.") for n in sys.modules),
        "Native worker imported Cells",
    )
    return {
        "engine": "actual_betse_full_init_loop",
        "results": results,
        "environment": c.environment(),
        "installed_python_sha256": installed,
        "package_path": str(package),
        "trajectory_run": True,
    }


def cells_worker(registered, output):
    import jax

    from cells.core.runner import run
    from cells.core.specs import parse_spec
    from cells.io import runtime_identity
    from cells.models import finite_extracellular as model

    c.require(
        jax.default_backend() == "cpu"
        and jax.config.x64_enabled
        and not jax.config.jax_disable_jit,
        "Require CPU/float64 with JIT available",
    )
    c.require(runtime_identity() == registered["cells_runtime"], "Cells runtime changed")
    results = {}
    for identifier, definition in registered["cells_definitions"].items():
        spec = parse_spec(definition)
        result = run(spec)
        record = {
            "id": identifier,
            "definition": definition,
            "times": array_record(result.times),
            "history": {
                name: array_record(value) for name, value in result.history._asdict().items()
            },
            "observations": {
                name: array_record(value) for name, value in vars(result.observations).items()
            },
            "diagnostics": {name: float(value) for name, value in result.diagnostics.items()},
            "timings": result.timings,
            "final_step_index": result.final.step_index,
        }
        directory = output / "cells" / identifier
        directory.mkdir(parents=True, exist_ok=False)
        c.write(directory / "result.json", record)
        results[identifier] = str((directory / "result.json").relative_to(output))
        print(json.dumps({"cells_run_completed": identifier}), flush=True)
    c.require(
        not any(n == "betse" or n.startswith("betse.") for n in sys.modules),
        "Cells worker imported BETSE",
    )
    return {
        "engine": "unchanged_cells_checked_rk4_runner",
        "results": results,
        "accepted_runtime": runtime_identity(),
        "source_path": model.__file__,
        "source_sha256": c.sha(model.__file__),
        "device": "cpu",
        "x64_enabled": True,
        "jit_disabled": False,
        "trajectory_run": True,
    }


def register(output):
    output.mkdir(parents=True, exist_ok=False)
    ctx.authenticate()
    protocol = c.read(ctx.PROTOCOL)
    saved = c.read(evidence.SESSION / "betse.json")
    registered = {
        "schema": "cells.betse_trajectory_registration@1",
        "registered_utc": datetime.now(UTC).isoformat(),
        "protocol": protocol,
        "base_protocol": c.read(a.PROTOCOL),
        "upstream": c.inspect_source(),
        "sources": ctx.sources(),
        "prior_closeout_sha256": ctx.PRIOR_SHA,
        "preservation_sha256": c.sha(ctx.PRESERVATION),
        "cells_runtime": c.read(ctx.PRESERVATION)["runtime"],
        "geometry": saved["geometry"],
        "settings": saved["settings"],
        "cells_definitions": {
            ctx.key(case["id"], backend, dt): ctx.definition(case, dt, backend)
            for case in protocol["cases"]
            for backend in protocol["cells_backends"]
            for dt in protocol["cells_steps_s"]
        },
    }
    c.require(ctx.NEW_FILES <= set(registered["sources"]), "Missing panel source")
    c.write(output / "registration.json", registered)
    with zipfile.ZipFile(output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in registered["sources"]:
            archive.write(c.HERE / name, arcname=name)
    return registered


def execute(output):
    started = time.monotonic()
    try:
        registered = c.read(output / "registration.json")
        c.write(
            output / "started.json",
            {"pid": os.getpid(), "started_utc": datetime.now(UTC).isoformat()},
        )
        protocol = registered["protocol"]
        env = os.environ | {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(output / "matplotlib-cache"),
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "JAX_PLATFORMS": "cpu",
            "JAX_ENABLE_X64": "true",
        }
        env.pop("PYTHONPATH", None)
        for kind, python in (("betse", c.REFERENCE_PYTHON), ("cells", c.CELLS_PYTHON)):
            remaining = protocol["total_timeout_seconds"] - (time.monotonic() - started)
            c.require(remaining > 0, "Panel wall budget exhausted")
            with (
                (output / f"{kind}.stdout.log").open("x") as out,
                (output / f"{kind}.stderr.log").open("x") as err,
            ):
                subprocess.run(
                    [
                        "taskset",
                        "-c",
                        protocol["cpu_affinity"],
                        str(python),
                        "-B",
                        str(Path(__file__).resolve()),
                        "worker",
                        kind,
                        str(output),
                    ],
                    cwd=c.ROOT,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=out,
                    stderr=err,
                    timeout=min(remaining, protocol["worker_timeout_seconds"]),
                    check=True,
                )
            c.require(
                sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
                < protocol["max_artifact_bytes"],
                "Artifact budget exhausted",
            )
        from trajectory_check import audit_data

        comparison = audit_data(registered, output)
        c.write(output / "comparison.json", comparison)
        c.require(
            comparison["status"] == "pass", "Trajectory comparison failed; retain full packet"
        )
        ctx.authenticate()
        c.require(
            all(c.sha(c.HERE / name) == digest for name, digest in registered["sources"].items()),
            "Captured source changed",
        )
        c.require(
            time.monotonic() - started < protocol["total_timeout_seconds"],
            "Panel wall budget exhausted",
        )
        c.require(
            sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
            < protocol["max_artifact_bytes"] - 65536,
            "Artifact budget exhausted",
        )
        # Outer stdout/stderr and launch receipt are operational logs, not finalized payloads.
        payloads = {
            str(p.relative_to(output)): c.sha(p)
            for p in output.rglob("*")
            if p.is_file()
            and p.name not in ("runner.stdout.log", "runner.stderr.log", "launch.json")
        }
        c.write(
            output / "verification.json",
            {
                "schema": "cells.betse_trajectory_capture@1",
                "status": "pass",
                "seconds": time.monotonic() - started,
                "finished_utc": datetime.now(UTC).isoformat(),
                "registration_sha256": c.sha(output / "registration.json"),
                "files_sha256": payloads,
                "trajectory_run": True,
                "biological_validation": False,
            },
        )
    except BaseException:
        c.write(
            output / "failure.json",
            {
                "status": "failed_not_qualified",
                "seconds": time.monotonic() - started,
                "traceback": traceback.format_exc(),
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
                registered["protocol"]["cpu_affinity"],
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
    }
    c.write(output / "launch.json", receipt)
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("launch", "execute"):
        sub.add_parser(action).add_argument("output", type=Path)
    worker = sub.add_parser("worker")
    worker.add_argument("kind", choices=("betse", "cells"))
    worker.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if args.action == "launch":
        launch(output)
    elif args.action == "execute":
        execute(output)
    else:
        registered = c.read(output / "registration.json")
        c.require(
            all(c.sha(c.HERE / n) == digest for n, digest in registered["sources"].items()),
            "Worker source changed",
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = (native_worker if args.kind == "betse" else cells_worker)(registered, output)
        result["warnings"] = [
            {"category": w.category.__name__, "message": str(w.message)} for w in caught
        ]
        result["registration_sha256"] = c.sha(output / "registration.json")
        c.write(output / f"{args.kind}.json", result)
