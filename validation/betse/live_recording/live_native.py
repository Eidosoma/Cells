"""Same native seed/INIT/physics; new streaming observer, no growing JSON trace."""

import copy
import gc
import sys
import time
import traceback
from pathlib import Path

import live_context as ctx
from live_observer import HISTORY_SOURCE, StreamObserver, history_specs

sys.path.insert(0, str(ctx.HERE.parent / "pump_loop_preflight"))
import pump_native as prior  # noqa: E402
import record_codec as codec  # noqa: E402


def settings(p, plan):
    result = {
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
    return result | dict(
        solver=p.solver_type.name,
        temperature_K=p.T,
        thickness_m=p.tm,
        constants=dict(F=p.F, R=p.R),
        pump_parameters={k: getattr(p, k) for k in plan["pump_parameters"]},
    )


def history_inventory(sim):
    """Numeric payload bytes only; not Python container bytes or whole-process RSS."""
    import numpy as np

    result = {}
    for name, value in vars(sim).items():
        if (name.endswith("_time") or name == "time") and isinstance(value, list):
            result[name] = dict(
                samples=len(value), numeric_payload_bytes=sum(np.asarray(v).nbytes for v in value)
            )
    return result


def run_row(r, variant, mode, directory, package, template):
    import numpy as np
    from betse.science.enum.enumphase import SimPhaseKind
    from betse.science.parameters import Parameters
    from betse.science.phase.phasecls import SimPhase
    from betse.science.simrunner import SimRunner
    from ruamel.yaml import YAML

    directory.mkdir(parents=True, exist_ok=False)
    observer = None
    started = time.monotonic()
    try:
        plan = r["protocol"]
        yaml = YAML(typ="safe")
        yaml.default_flow_style = False
        with (directory / "native.yaml").open("x") as handle:
            yaml.dump(prior.ctx.configuration(template, plan, variant, directory), handle)
        p = Parameters()
        p.load(str(directory / "native.yaml"))
        source_constants = dict(F=p.F, R=p.R)
        p.F, p.R = (plan["constants"][name] for name in ("F", "R"))
        ctx.need(
            {k: getattr(p, k) for k in plan["pump_parameters"]} == plan["pump_parameters"],
            "Maintained pump chemistry changed",
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
        ctx.need(
            {k: geometry[k] for k in prior.ctx.GEOMETRY_FIELDS} == r["expected_geometry"],
            "Geometry",
        )
        ctx.write(directory / "geometry.json", geometry)
        phase = SimPhase(kind=SimPhaseKind.INIT, cells=cells, p=p)
        sim = phase.sim
        sim.init_core(phase)
        fixed = {}

        def header(initial):
            ctx.need(p.dt == plan["dt_s"] and p.init_tsteps == plan["steps"], "INIT clock changed")
            return dict(
                kind="native_header",
                schema="cells.native_pump_row@1",
                row=dict(
                    id=variant["id"],
                    mode=mode,
                    phase=phase.kind.name,
                    settings=settings(p, plan),
                    geometry=geometry,
                    source_constants=source_constants,
                    fixture=fixed,
                    metadata=prior.native.metadata(phase),
                    moving_ions=list(map(int, sim.movingIons)),
                    sodium_index=int(sim.iNa),
                    potassium_index=int(sim.iK),
                    dt_s=p.dt,
                    steps=p.init_tsteps,
                ),
                trace=None if mode == "unobserved" else dict(initial=initial),
                histories=history_specs(sim, p.init_tsteps),
            )

        with codec.RecordSink(directory / "stream", max_output_bytes=32 * 1024**2) as sink:
            observer = StreamObserver(
                phase,
                package / "science",
                prior.snapshot,
                header,
                sink,
                observed=mode == "observed",
            )
            hook = prior.old.InitialConditionHook(
                phase,
                package / "science",
                lambda value: prior.fixture(value, variant, fixed),
                observer,
            )
            before = ctx.rss()
            with hook:
                sim.run_sim_core(phase)
            after = ctx.rss()
            ctx.need(Path(p.init_pickle_filename).is_file(), "Missing native pickle")
            manifest = observer.finish(
                dict(
                    final=prior.snapshot(sim),
                    final_arrays={
                        key: prior.native.ctx.array_record(getattr(sim, name))
                        for key, name in prior.native.PHYSICAL.items()
                    },
                    fixture_hook=dict(calls=hook.calls, returns=hook.returns),
                    hook_restored=sys.getprofile() is None,
                    native_pickle=str(Path(p.init_pickle_filename).relative_to(directory)),
                )
            )
        histories = history_inventory(sim)
        ctx.need(
            all(histories[name]["samples"] == plan["steps"] - 1 for name in HISTORY_SOURCE),
            "Native histories changed",
        )
        result = dict(
            status="live_row_captured_not_independently_qualified",
            id=variant["id"],
            mode=mode,
            steps=observer.updates,
            observed_updates=observer.updates if mode == "observed" else 0,
            history_samples=observer.samples,
            peak_pending_updates=observer.peak_pending_updates,
            observer_horizon_lists=False,
            native_histories_unchanged=True,
            native_memory_bounded=False,
            native_history_inventory=histories,
            native_history_numeric_payload_bytes=sum(
                v["numeric_payload_bytes"] for v in histories.values()
            ),
            rss_before_loop=before,
            rss_after_loop=after,
            rss_after_recording=ctx.rss(),
            elapsed_seconds=time.monotonic() - started,
            stream=manifest,
        )
        ctx.write(directory / "capture.json", result)
        return result
    except BaseException:
        ctx.write(
            directory / "failure.json",
            dict(
                status="live_row_failed",
                traceback=traceback.format_exc(),
                hook_restored=sys.getprofile() is None,
            ),
        )
        if observer is not None:
            ctx.write(directory / "partial-observer.json", observer.partial())
        raise


def worker(output, registration):
    import betse
    import numpy as np
    from ruamel.yaml import YAML
    from stream_compare import compare

    original = ctx.read(ctx.LEGACY / "registration.json")
    package = Path(betse.__file__).resolve().parent
    installed = {f"betse/{p.relative_to(package)}": ctx.sha(p) for p in package.rglob("*.py")}
    expected = {
        k: v
        for k, v in original["native_preparation"]["upstream"]["files_sha256"].items()
        if k.startswith("betse/") and k.endswith(".py")
    }
    ctx.need(
        installed == expected and package.is_relative_to(ctx.NATIVE_PYTHON.parent.parent),
        "Native source",
    )
    ctx.need(
        prior.c.environment()["packages"] == prior.c.locked_reference_packages(), "Native runtime"
    )
    with (prior.c.SOURCE / "betse/data/yaml/sim_config.yaml").open() as handle:
        template = YAML(typ="safe").load(handle)
    records, pairs, observed = {}, [], {}
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        for index, label in enumerate(registration["native_labels"]):
            ctx.budget(output, reserve=64 * 1024**2)
            identifier, step_string, mode = label.split("/")
            step = float(step_string.removeprefix("dt_"))
            current = copy.deepcopy(original["native_preparation"])
            current["protocol"].update(dt_s=step, duration_s=0.001, steps=round(0.001 / step))
            variant = next(v for v in current["protocol"]["variants"] if v["id"] == identifier)
            directory = output / "native" / f"{index:02d}"
            captured = run_row(current, variant, mode, directory, package, template)
            match = compare(directory / "stream", ctx.CODEC / "rows" / f"{index:02d}")
            base = "/".join(label.split("/")[:2])
            if mode == "observed":
                observed[base] = directory / "stream"
            else:
                pair = compare(observed.pop(base), directory / "stream", common=True)
                pairs.append(dict(label=base, **pair))
            record = dict(
                label=label,
                directory=str(directory.relative_to(output)),
                overlap=match,
                capture_sha256=ctx.sha(directory / "capture.json"),
                observed_updates=captured["observed_updates"],
                history_samples=captured["history_samples"],
            )
            ctx.write(directory / "comparison.json", record)
            records[label] = record
            ctx.budget(output)
            print("Live native row exact: " + label, flush=True)
            # Caller-owned native histories are released between rows, not pruned during a run.
            gc.collect()
    ctx.need(len(records) == 36 and len(pairs) == 18 and not observed, "Live matrix incomplete")
    ctx.need(
        not any(n == "cells" or n.startswith("cells.") for n in sys.modules),
        "Native imported Cells",
    )
    return dict(
        status="live_overlap_pass_pending_independent_review",
        records=records,
        observer_pairs=pairs,
        native_runs=len(records),
        observed_updates=sum(v["observed_updates"] for v in records.values()),
        history_samples=sum(v["history_samples"] for v in records.values()),
        installed_python_sha256=installed,
        environment=prior.c.environment(),
        native_memory_bounded=False,
    )
