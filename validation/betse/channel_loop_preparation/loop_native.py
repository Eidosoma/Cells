"""Real fresh seed/init_core/run_sim_core, with no replacement numerical method."""

import sys
import traceback
from pathlib import Path

import loop_context as ctx
from loop_observer import ChannelLoopObserver, InitialConditionHook

c, t = ctx.c, ctx.t
PHYSICAL = {
    "inside_mM": "cc_cells",
    "outside_mM": "cc_env",
    "at_membrane_mM": "cc_at_mem",
    "voltage_V": "vm",
    "rho_C_per_m3": "rho_cells",
    "boundary_voltage_V": "Phi_b",
    "ordinary_density_mol_per_m2_s": "fluxes_mem",
    "junction_density_mol_per_m2_s": "fluxes_gj",
    "extra_current_density_A_per_m2": "extra_J_mem",
    "Jmem_A_per_m2": "Jmem",
    "Jn_A_per_m2": "Jn",
    "I_mem_A": "I_mem",
    "extra_rho_cells_C_per_m3": "extra_rho_cells",
    "extra_rho_env_C_per_m3": "extra_rho_env",
}
HISTORIES = (
    "time",
    "cc_time",
    "cc_env_time",
    "vm_time",
    "I_mem_time",
    "rho_cells_time",
    "rate_NaKATP_time",
    "gjopen_time",
    "dd_time",
)


def channel(sim):
    return None if sim.molecules is None else next(iter(sim.molecules.core.channels.values()), None)


def channel_snapshot(sim):
    import numpy as np

    chan = channel(sim)
    if chan is None:
        return None
    core = chan.channel_core
    return {
        "m": core.m.tolist(),
        "h": core.h.tolist(),
        "P": None if not hasattr(core, "P") else core.P.tolist(),
        "derived_m_times_h": (core.m * core.h).tolist(),
        "DChan_m2_per_s": None if core.DChan is None else core.DChan.tolist(),
        "density_mol_per_m2_s": core.chan_flux.tolist(),
        "modulator": np.asarray(core.modulator).tolist(),
    }


def snapshot(sim):
    return {
        "physical": {
            key: None if not hasattr(sim, name) else ctx.array_record(getattr(sim, name))["values"]
            for key, name in PHYSICAL.items()
        },
        "channel": channel_snapshot(sim),
        "network_current": [0.0] * sim.mdl
        if sim.molecules is None
        else sim.molecules.core.extra_J_mem.tolist(),
    }


def metadata(phase):
    sim, p = phase.sim, phase.p
    chan = channel(sim)
    net = None if sim.molecules is None else sim.molecules.core
    return {
        "species": [k for k, enabled in p.ions_dict.items() if enabled],
        "valence": sim.zs.tolist(),
        "sim_temperature_K": sim.T,
        "rho_channel": sim.rho_channel,
        "ordinary_diffusivity_m2_per_s": sim.Dm_cells.tolist(),
        "network_inventory": None
        if net is None
        else {
            key: list(getattr(net, key))
            for key in (
                "molecules",
                "reactions",
                "reactions_env",
                "transporters",
                "channels",
                "modulators",
            )
        },
        "channel": None
        if chan is None
        else {
            "name": chan.name,
            "class": chan.channel_class,
            "type": chan.channel_type,
            "targets": chan.channel_core.targets.tolist(),
            "target_profiles": chan.channel_profiles_list,
            "init_active": chan.init_active,
            "maxDm_m2_per_s": chan.maxDm,
            "ions": chan.channel_core.ions,
            "relative_permeability": chan.channel_core.rel_perm,
            "powers": [chan.channel_core._mpower, chan.channel_core._hpower],
            "time_unit": chan.channel_core.time_unit,
            "alpha_eval_string": chan.alpha_eval_string,
        },
    }


def apply_fixture(phase, gate, variant, directory, records):
    """The ONLY native experimental state write: explicitly declared initial m/h."""
    sim = phase.sim
    before = snapshot(sim)
    c.require(not records, "Repeated initial fixture")
    chan = channel(sim)
    c.require((chan is not None) == variant["channel"], "Wrong initialized channel inventory")
    if chan is not None:
        c.require(
            before["channel"]["P"] is None and before["channel"]["DChan_m2_per_s"] is None,
            "Channel advanced before initial fixture",
        )
        chan.channel_core.m[:] = gate[0]
        chan.channel_core.h[:] = gate[1]
    after = snapshot(sim)
    c.require(
        before["physical"] == after["physical"]
        and before["network_current"] == after["network_current"],
        "Initial gate fixture changed physical inventories/voltage/current",
    )
    records.update(
        {
            "before": before,
            "after": after,
            "metadata": metadata(phase),
            "declared_gate": gate,
            "applications": 1,
        }
    )
    c.write(directory / "fixture.json", records)


def run_row(r, variant, mode, output, package, template):
    import numpy as np
    from betse.science.enum.enumphase import SimPhaseKind
    from betse.science.parameters import Parameters
    from betse.science.phase.phasecls import SimPhase
    from betse.science.simrunner import SimRunner
    from ruamel.yaml import YAML

    directory = output / "native" / variant["id"] / mode
    directory.mkdir(parents=True, exist_ok=False)
    observer = None
    try:
        yaml = YAML(typ="safe")
        yaml.default_flow_style = False
        with (directory / "native.yaml").open("x") as handle:
            yaml.dump(ctx.configuration(template, r, variant, directory), handle)
        p = Parameters()
        p.load(str(directory / "native.yaml"))
        source_constants = {"F": p.F, "R": p.R}
        p.F, p.R = (r["transport_protocol"]["constants"][key] for key in ("F", "R"))
        np.random.seed(r["transport_protocol"]["seed"])
        cells = SimRunner(p).seed().cells
        g = {
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
        c.write(directory / "geometry.json", g)
        c.require(
            {k: g[k] for k in t.GEOMETRY_FIELDS} == r["expected_geometry"], "Geometry changed"
        )
        phase = SimPhase(kind=SimPhaseKind.INIT, cells=cells, p=p)
        sim = phase.sim
        sim.init_core(phase)
        core_initial = {
            "inside_mM": sim.cc_cells.tolist(),
            "outside_mM": sim.cc_env.tolist(),
            "gate_initialization_voltage_V": sim.vm.tolist(),
        }
        c.write(directory / "core.json", core_initial)
        settings = {
            name: getattr(p, name)
            for name in (
                "is_ecm",
                "cell_polarizability",
                "cluster_open",
                "alpha_NaK",
                "alpha_Ca",
                "Ca_dyn",
                "molecules_enabled",
                "grn_enabled",
                "fluid_flow",
                "deformation",
                "deform_osmo",
                "dynamic_noise",
                "channel_noise_level",
                "v_sensitive_gj",
                "gj_surface",
                "substances_affect_charge",
            )
        }
        settings |= {
            "solver": p.solver_type.name,
            "temperature_K": p.T,
            "thickness_m": p.tm,
            "constants": {"F": p.F, "R": p.R},
        }
        fixture = {}
        if mode == "observed":
            observer = ChannelLoopObserver(
                phase,
                package / "science",
                snapshot,
                lambda entry: c.write(directory / "loop-entry.json", entry),
            )
        hook = InitialConditionHook(
            phase,
            package / "science",
            lambda phase: apply_fixture(
                phase, r["protocol"]["initial_gate"], variant, directory, fixture
            ),
            observer,
        )
        with hook:
            sim.run_sim_core(phase)
        c.require(
            p.init_tsteps == r["protocol"]["steps"] and p.dt == r["protocol"]["dt_s"],
            "Actual INIT step count/duration differs",
        )
        c.require(Path(p.init_pickle_filename).is_file(), "Native INIT restart artifact missing")
        final = snapshot(sim)
        # Exact bytes are compared for all exported physical fields, gate arrays,
        # active-path flux and the ordinary native sampled histories. Pickles
        # retain full native objects but differ in their embedded output paths.
        arrays = {key: ctx.array_record(getattr(sim, name)) for key, name in PHYSICAL.items()}
        if channel(sim) is not None:
            core = channel(sim).channel_core
            arrays |= {
                "channel/" + name: ctx.array_record(getattr(core, name))
                for name in ("m", "h", "P", "DChan", "chan_flux")
            }
        result = {
            "id": variant["id"],
            "mode": mode,
            "geometry": g,
            "settings": settings,
            "source_constants": source_constants,
            "core_initial": core_initial,
            "fixture": fixture,
            "final": final,
            "final_arrays": arrays,
            "histories": {name: ctx.array_record(getattr(sim, name)) for name in HISTORIES},
            "smooth_weight_mem": sim.smooth_weight_mem.tolist(),
            "smooth_weight_other": sim.smooth_weight_o.tolist(),
            "trace": None if observer is None else observer.result(),
            "fixture_hook": {"calls": hook.calls, "returns": hook.returns},
            "hook_restored": sys.getprofile() is None,
            "native_pickle": str(Path(p.init_pickle_filename).relative_to(directory)),
            "dt_s": p.dt,
            "steps": p.init_tsteps,
            "phase": phase.kind.name,
        }
        c.write(directory / "result.json", result)
        return result
    except BaseException:
        c.write(
            directory / "failure.json",
            {
                "status": "failed_not_qualified",
                "traceback": traceback.format_exc(),
                "hook_restored": sys.getprofile() is None,
            },
        )
        if observer is not None:
            c.write(directory / "partial-observer.json", observer.partial())
        raise


def worker(r, output):
    import betse
    import numpy as np
    from ruamel.yaml import YAML

    package = Path(betse.__file__).resolve().parent
    installed = {f"betse/{p.relative_to(package)}": c.sha(p) for p in package.rglob("*.py")}
    expected = {
        k: v
        for k, v in r["upstream"]["files_sha256"].items()
        if k.startswith("betse/") and k.endswith(".py")
    }
    c.require(
        installed == expected and package.is_relative_to(c.REFERENCE_PYTHON.parent.parent),
        "Installed native source differs",
    )
    c.require(
        c.locked_reference_packages() == c.environment()["packages"], "Native package lock differs"
    )
    with (c.SOURCE / "betse/data/yaml/sim_config.yaml").open() as handle:
        template = YAML(typ="safe").load(handle)
    rows = {}
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        for variant in r["transport_protocol"]["variants"]:
            for mode in r["protocol"]["modes"]:
                row = run_row(r, variant, mode, output, package, template)
                rows[variant["id"] + "/" + mode] = row
                used = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
                c.require(
                    used + 8 * 1024**2 < r["protocol"]["resources"]["max_artifact_bytes"],
                    "Preparation artifact budget exhausted",
                )
    c.require(
        not any(k == "cells" or k.startswith("cells.") for k in sys.modules),
        "Native preparation imported Cells",
    )
    return {
        "rows": rows,
        "installed_python_sha256": installed,
        "package_path": str(package),
        "environment": c.environment(),
        "engine": "unmodified_betse_FULL_INIT_with_declared_initial_gate_fixture",
    }
