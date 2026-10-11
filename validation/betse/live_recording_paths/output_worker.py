"""D128 output ownership amendment; all D125 numerical checkers and public APIs retained."""

import sys

import output_context as plan
from matched_windows import Arrays, WindowCheck, baseline, disk_check, prior
from output_context import ctx


def worker(output, registration, phase):
    keys = plan.selected_keys(registration, phase)
    destinations = {key: plan.case_paths(output, key) for key in keys}
    import jax

    from cells.core.runner import run
    from cells.core.specs import parse_spec
    from cells.core.windows import WindowPolicy, run_windowed
    from cells.io import load_snapshot, write_run
    from cells.window_io import write_windowed_run

    ctx.need(
        jax.default_backend() == "cpu"
        and jax.config.x64_enabled
        and not jax.config.jax_disable_jit,
        "CPU float64/JIT required",
    )
    original = ctx.read(ctx.LEGACY / "registration.json")
    ctx.need(prior.runtime() == original["cells_reference_runtime"], "Cells runtime changed")
    old_records = ctx.read(ctx.LEGACY / "cells.json")["records"]
    records = {}
    for key in keys:
        previous = old_records[key]
        ctx.budget(output.parent, reserve=64 * 1024**2)
        case, step, jit = previous["case"], previous["step_s"], previous["jit"]
        spec = parse_spec(prior.definition(original["cases"][case], step, jit=jit))
        full = run(spec)
        paths = destinations[key]
        directory = paths["directory"]
        write_run(paths["baseline"], full, provenance=dict(protocol="D128", matched_case=case))
        baseline_files = ctx.inventory(paths["baseline"])
        report = dict(
            prior_overlap=baseline(full, ctx.LEGACY / previous["directory"]),
            windows=[],
            recordings=[],
            restarts=[],
        )
        for width, recording in ((1, "full"), (7, "observations"), (64, "checkpoints")):
            check = WindowCheck(full, width)
            result = run_windowed(spec, WindowPolicy(width, recording), sink=check)
            report["windows"].append(dict(width=width, recording=recording, **check.finish(result)))
        if jit and step == 25e-6:
            for recording in ("full", "observations", "checkpoints"):
                policy = WindowPolicy(7, recording)
                target = paths["recording_" + recording]
                write_windowed_run(target, spec, policy, checkpoint_times=(0.0005,))
                report["recordings"].append(
                    dict(recording=recording, **disk_check(target, full, policy))
                )
            loaded = load_snapshot(paths["recording_checkpoints"] / "snapshots/step-0000000020")
            arrays = Arrays()
            arrays.checkpoint(loaded.checkpoint, full.checkpoint_at(0.0005))
            resumed = run(loaded.spec, loaded.checkpoint)
            write_run(paths["resumed"], resumed)
            for name, value in zip(full.history._fields, full.history, strict=True):
                arrays.match(getattr(resumed.history, name), value[20:], "resumed/" + name)
            arrays.match(resumed.times, full.times[20:], "resumed/times")
            arrays.checkpoint(resumed.final, full.final)
            offset = sum(float(t) < loaded.checkpoint.time for t in full.observations.times)
            for name, value in vars(full.observations).items():
                arrays.match(
                    getattr(resumed.observations, name), value[offset:], "resumed/observed/" + name
                )
            check = WindowCheck(full, 3, loaded.checkpoint)
            result = run_windowed(
                loaded.spec, WindowPolicy(3, "full"), loaded.checkpoint, sink=check
            )
            report["restarts"].append(
                dict(loaded=arrays.report(), windows=check.finish(result, suffix=True))
            )
            ctx.need(result.diagnostics == resumed.diagnostics, "Restart diagnostic maxima")
            zero = WindowCheck(full, 3, full.final)
            zresult = run_windowed(spec, WindowPolicy(3), full.final, sink=zero)
            report["zero_length"] = zero.finish(zresult, suffix=True)
        if case == "pump_leak" and step == 50e-6:
            sparse = parse_spec(
                prior.definition(original["cases"][case], step, jit=jit, times=[0.0, 0.001])
            )
            sfull = run(sparse)
            arrays = Arrays()
            for name in full.history._fields:
                arrays.match(
                    getattr(sfull.history, name), getattr(full.history, name), "sparse/" + name
                )
            ctx.need(sfull.diagnostics == full.diagnostics, "Sparse observations lost diagnostics")
            check = WindowCheck(sfull, 7)
            result = run_windowed(sparse, WindowPolicy(7, "checkpoints"), sink=check)
            report["sparse_observation_schedule"] = dict(
                states=arrays.report(), windows=check.finish(result)
            )
        ctx.need(ctx.inventory(paths["baseline"]) == baseline_files, "Baseline output changed")
        report["output_layout_version"] = plan.LAYOUT_VERSION
        report["output_paths"] = plan.LAYOUT
        report["baseline_files_sha256"] = baseline_files
        ctx.write(directory / "comparison.json", report)
        records[key] = dict(
            directory=str(directory.relative_to(output)),
            sha256=ctx.sha(directory / "comparison.json"),
            windows=len(report["windows"]),
            recordings=len(report["recordings"]),
            restarts=len(report["restarts"]),
            restart_windows=len(report["restarts"]),
            zero_length=int("zero_length" in report),
            sparse=int("sparse_observation_schedule" in report),
            baseline_preserved=True,
        )
        ctx.budget(output.parent)
        print("Matched Cells windows exact: " + key, flush=True)
    ctx.need(
        len(records) == len(keys),
        "Cells matrix incomplete",
    )
    ctx.need(
        not any(n == "betse" or n.startswith("betse.") for n in sys.modules), "Cells imported BETSE"
    )
    result = dict(
        status=plan.STATUS[phase],
        output_layout_version=plan.LAYOUT_VERSION,
        records=records,
        full_trajectories=len(records),
        window_runs=sum(v["windows"] for v in records.values()),
        disk_recordings=sum(v["recordings"] for v in records.values()),
        restart_suffixes=sum(v["restarts"] for v in records.values()),
        restart_window_runs=sum(v["restart_windows"] for v in records.values()),
        zero_length_runs=sum(v["zero_length"] for v in records.values()),
        sparse_schedule_controls=sum(v["sparse"] for v in records.values()),
        runtime=prior.runtime(),
        rss=ctx.rss(),
        production_changed=False,
    )
    plan.gate(phase, result, registration)
    return result
