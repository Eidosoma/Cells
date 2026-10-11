"""Actual fresh native objects and separate single updates; no full release run."""

import copy
import importlib
import sys
import traceback
from pathlib import Path

import release_context as ctx
import release_input as inputs

c, io, old = ctx.c, ctx.io, inputs.old
geometry_of = importlib.import_module("feedback_native").geometry


def prepare_group(r, history, step, directory, template):
    import numpy as np
    from betse.science.parameters import Parameters
    from betse.science.simrunner import SimRunner
    from ruamel.yaml import YAML

    data = r["data"][history]
    view = copy.deepcopy(data["preparation_registration"])
    duration = ctx.c.read(ctx.design.PLAN)["duration_s"]
    view["protocol"].update(dt_s=step, duration_s=duration, steps=round(duration / step))
    active = next(v for v in view["transport_protocol"]["variants"] if v["id"] == "active_channel")
    directory.mkdir(parents=True, exist_ok=False)
    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    with (directory / "native.yaml").open("x") as stream:
        yaml.dump(old.ctx.configuration(template, view, active, directory), stream)
    p = Parameters()
    p.load(str(directory / "native.yaml"))
    source_constants = {"F": p.F, "R": p.R}
    p.F, p.R = (view["transport_protocol"]["constants"][key] for key in ("F", "R"))
    np.random.seed(view["transport_protocol"]["seed"])
    cells = SimRunner(p).seed().cells
    geometry = geometry_of(cells, p)
    c.require(geometry == data["geometry"], "Native preparation geometry differs")
    settings = {
        key: getattr(p, key)
        for key in data["settings"]
        if key not in ("solver", "temperature_K", "thickness_m", "constants")
    } | {
        "solver": p.solver_type.name,
        "temperature_K": p.T,
        "thickness_m": p.tm,
        "constants": {"F": p.F, "R": p.R},
    }
    c.require(settings == data["settings"], "Native physical settings differ")
    # This is a candidate clock derived from actual configured Parameters, not a run.
    # p.dt is installed by SimPhase(INIT), not by Parameters.load/seed.
    labels = np.linspace(0.0, p.init_tsteps * p.init_time_step, p.init_tsteps).tolist()
    c.require(
        p.init_time_step == step and p.init_tsteps == round(duration / step),
        "Configured clock differs",
    )
    c.require(
        labels == data["saved_labels"][f"{step:.8g}"], "Clock differs from audited native loop"
    )
    prep = {
        "geometry": geometry,
        "settings": settings,
        "source_constants": source_constants,
        "native_yaml_sha256": c.sha(directory / "native.yaml"),
        "dt_s": p.init_time_step,
        "candidate_steps": p.init_tsteps,
        "candidate_labels_s": labels,
        "labels_origin": "actual_Parameters_numpy_linspace_matches_saved_FULL_loop_not_new_loop",
    }
    io.write(directory / "preparation.json", prep)
    return p, cells, prep


def one_case(r, history, step, condition, query, mode, p, cells, science, directory):
    import numpy as np
    from betse.science.enum.enumphase import SimPhaseKind
    from betse.science.phase.phasecls import SimPhase

    data = r["data"][history]
    # Native init_core draws channel_noise_factor even when its effect is zero.
    # Give every fresh case the same declared initialization, including controls.
    seed = data["preparation_registration"]["transport_protocol"]["seed"]
    np.random.seed(seed)
    directory.mkdir(parents=True, exist_ok=False)
    row = {
        "history": history,
        "condition": condition,
        "query_index": query,
        "mode": mode,
        "dt_s": step,
        "initialization_seed": seed,
    }
    try:
        phase = SimPhase(kind=SimPhaseKind.INIT, cells=cells, p=p)
        c.require(p.dt == step, "Actual INIT phase timestep differs")
        sim = phase.sim
        sim.init_core(phase)
        sim.init_dynamics(phase)
        fixture = {}
        active = {"id": "active_channel", "channel": True}
        old.apply_fixture(phase, data["initial_gate"], active, directory, fixture)
        sim.update_V(cells, p)
        start = old.snapshot(sim)
        metadata = old.metadata(phase)
        row.update(fixture=fixture, initial=start, initial_metadata=metadata)
        io.write_compressed(directory / "initial.json.gz", row)
        c.require(
            start == data["saved_initial"][f"{step:.8g}"],
            "Actual starting state differs from audited history",
        )
        c.require(
            metadata == data["saved_metadata"][f"{step:.8g}"],
            "Actual native channel metadata differs",
        )
        channel = old.channel(sim)
        # The native YAML loader retains a float subclass; the numeric input API
        # deliberately accepts built-in scalars only. Metadata was checked above.
        controller = inputs.AvailabilityInput(float(channel.maxDm))

        # A single actual active update supplies nonzero inventories/current/gate history.
        row["prime"] = {}
        inputs.single_update(phase, science, mode, 0.0, record=row["prime"])
        primed = old.snapshot(sim)
        c.require(
            primed["physical"]["inside_mM"] != start["physical"]["inside_mM"],
            "Priming transfer absent",
        )
        c.require(any(primed["channel"]["density_mol_per_m2_s"]), "No stored priming channel flux")
        guard = inputs.numeric_inventory(phase)
        row["primed_numeric_inventory"] = guard
        row["applications"] = []
        plan = c.read(ctx.design.PLAN)
        table = ctx.design.native_intervals(plan, condition, step)
        for time in r["plan"]["protocol_query_times_s"][: query + 1]:
            entry = next(item for item in table if item["start_s"] == time)
            before = old.snapshot(sim)
            applied = controller.apply(channel, entry["availability"])
            after = old.snapshot(sim)
            after_guard = inputs.numeric_inventory(phase)
            application = applied | {
                "protocol_query_s": time,
                "candidate_step_index": entry["step_index"],
                "candidate_native_label_s": data["saved_labels"][f"{step:.8g}"][
                    entry["step_index"]
                ],
                "actual_completed_single_updates": 1,
                "integration_between_applications": False,
                "before": before,
                "after": after,
                "numeric_inventory_after": after_guard,
            }
            row["applications"].append(application)
            c.require(
                before == after == primed and after_guard == guard,
                "Input changed native state or numeric layout",
            )
            application["fresh"] = inputs.fresh_flux(phase)
            c.require(
                old.snapshot(sim) == primed and inputs.numeric_inventory(phase) == guard,
                "Fresh probe mutated native state",
            )
        io.write_compressed(directory / "input-applied.json.gz", row)
        last = row["applications"][-1]
        row["probe"] = {}
        inputs.single_update(
            phase, science, mode, last["candidate_native_label_s"], record=row["probe"]
        )
        row.update(
            final=old.snapshot(sim),
            final_metadata=old.metadata(phase),
            smooth_weight_mem=sim.smooth_weight_mem.tolist(),
            smooth_weight_other=sim.smooth_weight_o.tolist(),
            actual_elapsed_single_updates_s=2 * step,
            single_updates=2,
            full_simulator_loop_executed=False,
            protocol_query_time_is_simulated_elapsed_time=False,
            hook_restored=sys.getprofile() is None,
        )
        io.write_compressed(directory / "result.json.gz", row)
        return row
    except BaseException:
        io.write_compressed(directory / "partial.json.gz", row)
        io.write(
            directory / "failure.json",
            {
                "status": "native_preflight_failed",
                "traceback": traceback.format_exc(),
                "hook_restored": sys.getprofile() is None,
            },
        )
        raise


def comparable(row):
    result = copy.deepcopy(row)
    result.pop("mode")
    for stage in ("prime", "probe"):
        result[stage].pop("observer")
    return result


def worker(r, output, *, selections=None):
    import betse
    import numpy as np
    from ruamel.yaml import YAML

    package = Path(betse.__file__).resolve().parent
    expected = r["data"]["a"]["preparation_registration"]["upstream"]["files_sha256"]
    installed = {"betse/" + str(p.relative_to(package)): c.sha(p) for p in package.rglob("*.py")}
    c.require(package.is_relative_to(c.REFERENCE_PYTHON.parent.parent), "Wrong native origin")
    c.require(
        installed
        == {n: h for n, h in expected.items() if n.startswith("betse/") and n.endswith(".py")},
        "Installed native source differs",
    )
    c.require(
        c.environment()["packages"] == c.locked_reference_packages(), "Native package lock differs"
    )
    with (c.SOURCE / "betse/data/yaml/sim_config.yaml").open() as stream:
        template = YAML(typ="safe").load(stream)
    preparations, records = {}, {}
    selected = (
        selections
        if selections is not None
        else [
            (history, step, condition, query)
            for history in r["plan"]["histories"]
            for step in r["plan"]["native_steps_s"]
            for condition in r["plan"]["conditions"]
            for query in range(len(r["plan"]["protocol_query_times_s"]))
        ]
    )
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        for history in r["plan"]["histories"]:
            for step in r["plan"]["native_steps_s"]:
                local = [item for item in selected if item[:2] == (history, step)]
                if not local:
                    continue
                group = f"{history}/dt_{step:.8g}"
                p, cells, prep = prepare_group(
                    r, history, step, output / "native" / group, template
                )
                preparations[group] = prep
                for _, _, condition, query in local:
                    key = f"{group}/{condition}/query_{query}"
                    pair, paths = {}, {}
                    for mode in r["plan"]["modes"]:
                        directory = output / "native" / key / mode
                        pair[mode] = one_case(
                            r,
                            history,
                            step,
                            condition,
                            query,
                            mode,
                            p,
                            cells,
                            package / "science",
                            directory,
                        )
                        paths[mode] = str((directory / "result.json.gz").relative_to(output))
                    c.require(
                        comparable(pair["observed"]) == comparable(pair["unobserved"]),
                        "Read-only observer changed native case",
                    )
                    records[key] = paths
                print(f"Completed release-input group: {group}", flush=True)
    c.require(
        not any(n.split(".")[0] in {"cells", "jax", "jaxlib"} for n in sys.modules),
        "Native worker imported Cells",
    )
    return {
        "engine": "pinned_native_preparation_external_maxDm_input_and_single_updates",
        "installed_python_sha256": installed,
        "preparations": preparations,
        "records": records,
        "geometry_seeds": len(preparations),
        "fresh_phases": 2 * len(records),
        "single_updates": 4 * len(records),
        "observer_pairs": len(records),
        "full_simulator_loop_executed": False,
        "release_response_qualified": False,
        "test_only_subset": selections is not None,
    }
