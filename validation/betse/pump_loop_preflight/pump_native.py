"""Real pinned BETSE seed -> INIT driver; no replacement transport or integration."""

import importlib
import sys
import traceback
from pathlib import Path

import pump_context as ctx
from pump_observer import PumpLoopObserver, numeric, old

native = importlib.import_module("loop_native")
c = ctx.c


def snapshot(sim):
    return native.snapshot(sim) | {
        "reported_NaK_rate": None if not hasattr(sim, "rate_NaKATP") else numeric(sim.rate_NaKATP),
        "rho_pump": numeric(sim.rho_pump),
        "pump_block": numeric(sim.NaKATP_block),
    }


def fixture(phase, variant, result):
    c.require(not result, "Repeated pump fixture")
    before = snapshot(phase.sim)
    phase.sim.rho_pump = variant["rho_pump"]
    phase.p.cluster_open = variant["cluster_open"]
    after = snapshot(phase.sim)
    c.require(before["physical"] == after["physical"], "Fixture changed physical state")
    result.update(
        before=before,
        after=after,
        applications=1,
        declared=dict(rho_pump=variant["rho_pump"], cluster_open=variant["cluster_open"]),
    )


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
        plan = r["protocol"]
        yaml = YAML(typ="safe")
        yaml.default_flow_style = False
        with (directory / "native.yaml").open("x") as handle:
            yaml.dump(ctx.configuration(template, plan, variant, directory), handle)
        p = Parameters()
        p.load(str(directory / "native.yaml"))
        source_constants = dict(F=p.F, R=p.R)
        p.F, p.R = (plan["constants"][key] for key in ("F", "R"))
        c.require(
            {k: getattr(p, k) for k in plan["pump_parameters"]} == plan["pump_parameters"],
            "Native maintained metabolism/kinetics changed",
        )
        np.random.seed(plan["seed"])
        cells = SimRunner(p).seed().cells
        geometry = dict(
            cell_count=len(cells.cell_i),
            membrane_count=len(cells.mem_i),
            cell_centres_m=cells.cell_centres.tolist(),
            cell_volumes_m3=cells.cell_vol.tolist(),
            cell_areas_m2=cells.cell_sa.tolist(),
            membrane_owners=cells.mem_to_cells.tolist(),
            membrane_areas_m2=cells.mem_sa.tolist(),
            diviterm_m=cells.diviterm.tolist(),
            configured_bath_volume_m3=p.vol_env,
            effective_bath_volume_m3=len(cells.mem_i) * p.vol_env,
            specific_capacitance_F_per_m2=p.cm,
            boundary_faces=list(map(int, cells.bflags_mems)),
        )
        c.require(
            {k: geometry[k] for k in ctx.GEOMETRY_FIELDS} == r["expected_geometry"],
            "Seed geometry changed",
        )
        c.write(directory / "geometry.json", geometry)
        phase = SimPhase(kind=SimPhaseKind.INIT, cells=cells, p=p)
        sim = phase.sim
        sim.init_core(phase)
        fixed = {}
        if mode == "observed":
            observer = PumpLoopObserver(
                phase,
                package / "science",
                snapshot,
                lambda value: c.write(directory / "loop-entry.json", value),
            )
        hook = old.InitialConditionHook(
            phase, package / "science", lambda value: fixture(value, variant, fixed), observer
        )
        with hook:
            sim.run_sim_core(phase)
        c.require(
            p.dt == plan["dt_s"] and p.init_tsteps == plan["steps"], "Actual INIT clock changed"
        )
        c.require(Path(p.init_pickle_filename).is_file(), "Native checkpoint missing")
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
        settings |= dict(
            solver=p.solver_type.name,
            temperature_K=p.T,
            thickness_m=p.tm,
            constants=dict(F=p.F, R=p.R),
            pump_parameters={k: getattr(p, k) for k in plan["pump_parameters"]},
        )
        row = dict(
            id=variant["id"],
            mode=mode,
            phase=phase.kind.name,
            settings=settings,
            geometry=geometry,
            source_constants=source_constants,
            fixture=fixed,
            fixture_hook=dict(calls=hook.calls, returns=hook.returns),
            hook_restored=sys.getprofile() is None,
            final=snapshot(sim),
            final_arrays={
                key: native.ctx.array_record(getattr(sim, name))
                for key, name in native.PHYSICAL.items()
            },
            histories={
                name: native.ctx.array_record(getattr(sim, name)) for name in native.HISTORIES
            },
            metadata=native.metadata(phase),
            moving_ions=list(map(int, sim.movingIons)),
            sodium_index=int(sim.iNa),
            potassium_index=int(sim.iK),
            dt_s=p.dt,
            steps=p.init_tsteps,
            trace=None if observer is None else observer.result(),
            native_pickle=str(Path(p.init_pickle_filename).relative_to(directory)),
        )
        c.write(directory / "result.json", row)
        return row
    except BaseException:
        c.write(
            directory / "failure.json",
            dict(
                status="native_preparation_failed",
                traceback=traceback.format_exc(),
                hook_restored=sys.getprofile() is None,
            ),
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
        "Installed BETSE differs",
    )
    c.require(
        c.locked_reference_packages() == c.environment()["packages"], "Native package lock changed"
    )
    with (c.SOURCE / "betse/data/yaml/sim_config.yaml").open() as handle:
        template = YAML(typ="safe").load(handle)
    rows = {}
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        for variant in r["protocol"]["variants"]:
            for mode in r["protocol"]["modes"]:
                rows[variant["id"] + "/" + mode] = run_row(
                    r, variant, mode, output, package, template
                )
                used = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
                c.require(
                    used < r["protocol"]["resources"]["artifact_bytes"] - 32 * 1024**2,
                    "Artifact quota",
                )
    c.require(
        not any(k == "cells" or k.startswith("cells.") for k in sys.modules),
        "Native imported Cells",
    )
    return dict(
        rows=rows,
        installed_python_sha256=installed,
        environment=c.environment(),
        package_path=str(package),
        engine="unmodified_betse_FULL_INIT_with_declared_setup_fixture",
    )
