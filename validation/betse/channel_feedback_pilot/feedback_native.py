"""Longer native INIT adapter; unchanged loop, fixture, observer and physical laws."""

import importlib
import sys
import traceback
from pathlib import Path

import feedback_context as ctx
import feedback_io as io

old = importlib.import_module("loop_native")
observer_module = importlib.import_module("loop_observer")
c = ctx.c


def geometry(cells, p):
    return {
        "cell_count": len(cells.cell_i),
        "membrane_count": len(cells.mem_i),
        "cell_centres_m": cells.cell_centres.tolist(),
        "cell_volumes_m3": cells.cell_vol.tolist(),
        "cell_areas_m2": cells.cell_sa.tolist(),
        "membrane_owners": cells.mem_to_cells.tolist(),
        "membrane_areas_m2": cells.mem_sa.tolist(),
        "diviterm_m": cells.diviterm.tolist(),
        "configured_bath_volume_m3": p.vol_env,
        "effective_bath_volume_m3": len(cells.mem_i) * p.vol_env,
        "specific_capacitance_F_per_m2": p.cm,
        "grid_shape": list(cells.X.shape),
    }


def fresh_probes(trace, geometry, phase, variant, r):
    """Post-hoc native constitutive probes on COPIES, never inside the observer."""
    import numpy as np
    from betse.science.sim_toolbox import electroflux

    p, results = phase.p, []
    for time_s in r["protocol"]["common_times_s"]:
        index = round(time_s / p.dt)
        saved = trace["initial"] if index == 0 else trace["steps"][index - 1]["after_voltage"]
        physical, channel = saved["physical"], saved["channel"]
        gate = (
            np.zeros(geometry["membrane_count"], dtype=np.float64)
            if channel is None
            else np.array(channel["m"]) * np.array(channel["h"])
        )
        permeability = (
            gate
            * r["preparation_registration"]["transport_protocol"]["max_permeability_m_per_s"]
            * variant["permeability_fraction"]
        )
        outside = np.array(physical["outside_mM"][1], dtype=np.float64, copy=True)
        inside = np.array(
            [physical["inside_mM"][1][owner] for owner in geometry["membrane_owners"]],
            dtype=np.float64,
        )
        voltage = np.array(physical["voltage_V"], dtype=np.float64, copy=True)
        valence = np.ones(geometry["membrane_count"], dtype=np.float64)
        before = {
            "outside_K_mM": outside.tolist(),
            "inside_K_mM": inside.tolist(),
            "voltage_V": voltage.tolist(),
            "valence": valence.tolist(),
            "permeability_m_per_s": permeability.tolist(),
        }
        density = electroflux(outside, inside, permeability * p.tm, p.tm, valence, voltage, p.T, p)
        c.require(
            density.dtype == np.float64 and np.isfinite(density).all(), "Invalid native fresh probe"
        )
        results.append(
            {
                "elapsed_s": time_s,
                "source": "betse.science.sim_toolbox.electroflux",
                "evaluation": "post_hoc_copied_completed_state_not_interval_current",
                "inputs_before": before,
                "voltage_after_V": voltage.tolist(),
                "valence_after": valence.tolist(),
                "inward_density_mol_per_m2_s": density.tolist(),
            }
        )
    return results


def run_row(r, variant, step, mode, output, package, template):
    import numpy as np
    from betse.science.enum.enumphase import SimPhaseKind
    from betse.science.parameters import Parameters
    from betse.science.phase.phasecls import SimPhase
    from betse.science.simrunner import SimRunner
    from ruamel.yaml import YAML

    directory = output / "native" / ctx.key(variant["id"], step) / mode
    directory.mkdir(parents=True, exist_ok=False)
    registration, observer = ctx.loop_registration(r, step), None
    try:
        yaml = YAML(typ="safe")
        yaml.default_flow_style = False
        with (directory / "native.yaml").open("x") as stream:
            yaml.dump(
                ctx.audit.preparation.configuration(template, registration, variant, directory),
                stream,
            )
        p = Parameters()
        p.load(str(directory / "native.yaml"))
        source_constants = {"F": p.F, "R": p.R}
        p.F, p.R = (registration["transport_protocol"]["constants"][k] for k in ("F", "R"))
        np.random.seed(registration["transport_protocol"]["seed"])
        cells = SimRunner(p).seed().cells
        g = geometry(cells, p)
        c.require(g == r["geometry"], "Native geometry changed")
        io.write(directory / "geometry.json", g)
        phase = SimPhase(kind=SimPhaseKind.INIT, cells=cells, p=p)
        sim = phase.sim
        sim.init_core(phase)
        initial = {
            "inside_mM": sim.cc_cells.tolist(),
            "outside_mM": sim.cc_env.tolist(),
            "gate_initialization_voltage_V": sim.vm.tolist(),
        }
        io.write(directory / "core.json", initial)
        settings = {
            k: getattr(p, k)
            for k in r["native_settings"][variant["id"]]
            if k not in ("solver", "temperature_K", "thickness_m", "constants")
        }
        settings |= {
            "solver": p.solver_type.name,
            "temperature_K": p.T,
            "thickness_m": p.tm,
            "constants": {"F": p.F, "R": p.R},
        }
        c.require(
            settings == r["native_settings"][variant["id"]], "Native mechanism settings changed"
        )
        fixture = {}
        if mode == "observed":
            observer = observer_module.ChannelLoopObserver(
                phase,
                package / "science",
                old.snapshot,
                lambda entry: io.write(directory / "loop-entry.json", entry),
            )
        hook = observer_module.InitialConditionHook(
            phase,
            package / "science",
            lambda active: old.apply_fixture(
                active, r["protocol"]["initial_gate"], variant, directory, fixture
            ),
            observer,
        )
        with hook:
            sim.run_sim_core(phase)
        c.require(
            p.dt == step and p.init_tsteps == registration["protocol"]["steps"],
            "Native actual grid differs",
        )
        c.require(Path(p.init_pickle_filename).is_file(), "Missing native INIT serialization")
        final, trace = old.snapshot(sim), None if observer is None else observer.result()
        arrays = {
            name: old.ctx.array_record(getattr(sim, attr)) for name, attr in old.PHYSICAL.items()
        }
        if old.channel(sim) is not None:
            core = old.channel(sim).channel_core
            arrays |= {
                "channel/" + name: old.ctx.array_record(getattr(core, name))
                for name in ("m", "h", "P", "DChan", "chan_flux")
            }
        probes = None if trace is None else fresh_probes(trace, g, phase, variant, r)
        c.require(old.snapshot(sim) == final, "Post-hoc probe changed live native state")
        result = {
            "id": variant["id"],
            "mode": mode,
            "geometry": g,
            "settings": settings,
            "source_constants": source_constants,
            "core_initial": initial,
            "fixture": fixture,
            "final": final,
            "final_arrays": arrays,
            "histories": {name: old.ctx.array_record(getattr(sim, name)) for name in old.HISTORIES},
            "smooth_weight_mem": sim.smooth_weight_mem.tolist(),
            "smooth_weight_other": sim.smooth_weight_o.tolist(),
            "trace": trace,
            "fixture_hook": {"calls": hook.calls, "returns": hook.returns},
            "hook_restored": sys.getprofile() is None,
            "native_pickle": str(Path(p.init_pickle_filename).relative_to(directory)),
            "dt_s": p.dt,
            "steps": p.init_tsteps,
            "phase": phase.kind.name,
            "fresh_probes": probes,
        }
        io.write_compressed(directory / "result.json.gz", result)
        return result
    except BaseException:
        io.write(
            directory / "failure.json",
            {
                "status": "native_failed_not_qualified",
                "traceback": traceback.format_exc(),
                "hook_restored": sys.getprofile() is None,
            },
        )
        if observer is not None:
            io.write_compressed(directory / "partial-observer.json.gz", observer.partial())
        raise


def worker(r, output):
    import betse
    import numpy as np
    from ruamel.yaml import YAML

    package = Path(betse.__file__).resolve().parent
    installed = {"betse/" + str(p.relative_to(package)): c.sha(p) for p in package.rglob("*.py")}
    expected = {
        n: h
        for n, h in r["preparation_registration"]["upstream"]["files_sha256"].items()
        if n.startswith("betse/") and n.endswith(".py")
    }
    c.require(
        installed == expected and package.is_relative_to(c.REFERENCE_PYTHON.parent.parent),
        "Installed BETSE source differs",
    )
    c.require(
        c.environment()["packages"] == c.locked_reference_packages(), "Native package lock differs"
    )
    with (c.SOURCE / "betse/data/yaml/sim_config.yaml").open() as stream:
        template = YAML(typ="safe").load(stream)
    results = {}
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        for variant in r["preparation_registration"]["transport_protocol"]["variants"]:
            for step in r["protocol"]["native_steps_s"]:
                pair = {}
                identifier = ctx.key(variant["id"], step)
                for mode in ("observed", "unobserved"):
                    pair[mode] = run_row(r, variant, step, mode, output, package, template)
                exclude = {"mode", "trace", "fresh_probes"}
                c.require(
                    {k: v for k, v in pair["observed"].items() if k not in exclude}
                    == {k: v for k, v in pair["unobserved"].items() if k not in exclude},
                    "Observer changed native exports/history",
                )
                results[identifier] = {
                    mode: f"native/{identifier}/{mode}/result.json.gz" for mode in pair
                }
                used = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
                c.require(
                    used + 16 * 1024**2 < r["protocol"]["resources"]["max_artifact_bytes"],
                    "Native artifact budget exhausted",
                )
                print(f"native pair completed: {identifier}", flush=True)
    c.require(
        not any(n.split(".")[0] in ("cells", "jax", "jaxlib") for n in sys.modules),
        "Native imported Cells/JAX",
    )
    return {
        "engine": "unmodified_betse_FULL_INIT_with_frozen_fixture_and_observer",
        "records": results,
        "installed_python_sha256": installed,
        "package_path": str(package),
        "native_runs": 24,
        "native_updates": 4480,
        "observer_pairs": 12,
        "trajectory_run": True,
    }
