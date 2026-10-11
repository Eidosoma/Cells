"""Timed native FULL INIT capture; unmodified simulator and explicit parameter hook."""

import sys
import traceback
from pathlib import Path

import feedback_native as previous
import timed_context as ctx
from timed_input import TimedInput

c, io, old = ctx.c, ctx.io, previous.old
observer_module, geometry = previous.observer_module, previous.geometry


def probe(trace, g, phase, variant, r, condition, t, side="right"):
    view = r | {"protocol": r["protocol"] | {"common_times_s": [t]}}
    u = ctx.availability(r["schedules"][condition], t, side)
    return previous.fresh_probes(trace, g, phase, variant | {"permeability_fraction": u}, view)[0]


def timed_probes(trace, g, phase, variant, r, condition):
    return [
        probe(trace, g, phase, variant, r, condition, t) for t in r["protocol"]["common_times_s"]
    ]


def side_probes(trace, g, phase, variant, r, condition):
    times = [r["protocol"]["duration_s"] / 4, r["protocol"]["duration_s"] / 2]
    return [
        {
            "time_s": t,
            "left": probe(trace, g, phase, variant, r, condition, t, "left"),
            "right": probe(trace, g, phase, variant, r, condition, t, "right"),
        }
        for t in times
    ]


def run_row(r, variant, step, mode, output, package, template, condition):
    import numpy as np
    from betse.science.enum.enumphase import SimPhaseKind
    from betse.science.parameters import Parameters
    from betse.science.phase.phasecls import SimPhase
    from betse.science.simrunner import SimRunner
    from ruamel.yaml import YAML

    directory = output / "native" / ctx.key(condition, step) / mode
    directory.mkdir(parents=True, exist_ok=False)
    registration, observer = ctx.feedback.loop_registration(r, step), None
    try:
        yaml = YAML(typ="safe")
        yaml.default_flow_style = False
        with (directory / "native.yaml").open("x") as stream:
            yaml.dump(
                ctx.feedback.audit.preparation.configuration(
                    template, registration, variant, directory
                ),
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
        hook = TimedInput(
            phase,
            package / "science",
            lambda active: old.apply_fixture(
                active, r["protocol"]["initial_gate"], variant, directory, fixture
            ),
            r["schedules"][condition],
            r["protocol"]["duration_s"],
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
        probes = None if trace is None else timed_probes(trace, g, phase, variant, r, condition)
        c.require(old.snapshot(sim) == final, "Post-hoc probe changed live native state")
        result = {
            "id": variant["id"],
            "condition": condition,
            "timed_input": hook.result(),
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
            "side_probes": None
            if trace is None
            else side_probes(trace, g, phase, variant, r, condition),
        }
        c.require(old.snapshot(sim) == final, "One-sided probes changed live native state")
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


def worker(r, output, selections=None):
    import betse
    import numpy as np
    from ruamel.yaml import YAML

    package = Path(betse.__file__).resolve().parent
    installed = {"betse/" + str(p.relative_to(package)): c.sha(p) for p in package.rglob("*.py")}
    upstream = r["views"]["a"]["preparation_registration"]["upstream"]["files_sha256"]
    c.require(
        installed
        == {n: h for n, h in upstream.items() if n.startswith("betse/") and n.endswith(".py")}
        and package.is_relative_to(c.REFERENCE_PYTHON.parent.parent),
        "Native source identity",
    )
    c.require(
        c.environment()["packages"] == c.locked_reference_packages(), "Native runtime identity"
    )
    with (c.SOURCE / "betse/data/yaml/sim_config.yaml").open() as stream:
        template = YAML(typ="safe").load(stream)
    selected = (
        selections
        if selections is not None
        else [
            (h, v, s)
            for h in r["plan"]["histories"]
            for v in r["plan"]["conditions"]
            for s in r["plan"]["native_steps_s"]
        ]
    )
    records, updates, applications = {}, 0, 0
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        for history, condition, step in selected:
            view = r["views"][history]
            variant = next(
                v
                for v in view["preparation_registration"]["transport_protocol"]["variants"]
                if v["id"] == "active_channel"
            )
            pair = {
                mode: run_row(
                    view, variant, step, mode, output / history, package, template, condition
                )
                for mode in ("observed", "unobserved")
            }
            exclude = {"mode", "trace", "fresh_probes", "side_probes"}
            c.require(
                {k: v for k, v in pair["observed"].items() if k not in exclude}
                == {k: v for k, v in pair["unobserved"].items() if k not in exclude},
                "Timed observer changed native state",
            )
            name = history + "/" + ctx.key(condition, step)
            records[name] = {
                mode: f"{history}/native/{ctx.key(condition, step)}/{mode}/result.json.gz"
                for mode in pair
            }
            updates += sum(row["steps"] for row in pair.values())
            applications += sum(len(row["timed_input"]["applications"]) for row in pair.values())
            print("Timed native pair complete:", name, flush=True)
    c.require(
        not any(n.split(".")[0] in {"cells", "jax", "jaxlib"} for n in sys.modules),
        "Native imported Cells",
    )
    return {
        "engine": "pinned_betse_FULL_INIT_external_timed_maxDm",
        "records": records,
        "installed_python_sha256": installed,
        "package_path": str(package),
        "native_runs": 2 * len(records),
        "native_updates": updates,
        "input_applications": applications,
        "observer_pairs": len(records),
        "test_only_subset": selections is not None,
    }
