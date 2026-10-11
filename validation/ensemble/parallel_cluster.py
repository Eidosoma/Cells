"""Detached numerical screening of parallel-world candidates against qualified Cells.

This is a bounded execution experiment, not a new physical model or automatic
promotion. Both candidates retain the ordinary engine, stage checks, summaries
and checkpoint codec. All rounding differences are saved and reject exact parity.
"""

import argparse
import json
import os
import resource
import shutil
import subprocess
import time
import traceback
from dataclasses import replace
from functools import partial
from pathlib import Path

import jax
import numpy as np

from cells.assembly.io import runtime, write_json
from cells.assembly_cell.io import flatten, load_checkpoint, write_checkpoint
from cells.assembly_cluster import engine
from cells.assembly_cluster.spec import parse_spec
from cells.core.output_paths import within_output_root
from cells.ensemble import cli
from cells.ensemble.families import bind_definition

if __package__:
    from validation.assembly.cluster_partition_replay import differences

    from . import parallel_kernel as candidate_kernel
    from . import profile_cluster as profile
    from . import rounding_cluster as rounding
    from . import step_cluster as steps
else:
    import parallel_kernel as candidate_kernel
    import profile_cluster as profile
    import rounding_cluster as rounding
    import step_cluster as steps
    from cluster_partition_replay import differences

PHASE_CAP = 2700
RESERVE = 4 * 1024**3
WORKER_ALLOWANCE = 14 * 1024**3
GPU_ONLY_MODES = ("gpu_screen", "larger_gpu_screen", "energy_gpu_screen")
LARGE_GPU_MODES = ("larger_gpu_screen", "energy_gpu_screen")
ENERGY_SCREEN_VARIANT = "parallel_scalar_membrane_sum"
SCREEN_VARIANTS = (*candidate_kernel.VARIANTS, ENERGY_SCREEN_VARIANT)


def need(value, message):
    if not value:
        raise ValueError(message)


def progress(root, **values):
    write_json(root / "status.json", {"time": time.time(), **values}, replace=True)


def authenticate(root):
    record = cli.read(root / "registration.json")
    need(cli.sources() == record["production_sources_sha256"], "Production source changed")
    for name, digest in record["drivers_sha256"].items():
        need(cli.sha(root / "source" / name) == digest, "Experimental driver changed: " + name)
    parent = Path(record["parent"])
    need(cli.sha(parent / "result.json") == record["parent_result_sha256"], "Parent changed")
    profile.authenticate_parent(parent)
    if record["mode"] == "rounding_trace":
        need(
            rounding.authenticate_previous(
                Path(record["rounding_parent"]["path"]), parse_spec(record["definition"]), record
            )
            == record["rounding_parent"],
            "Previous candidate screen changed",
        )
    if record["mode"] == "saved_steps":
        need(
            steps.authenticate_previous(
                Path(record["step_parent"]["path"]), parse_spec(record["definition"]), record
            )
            == record["step_parent"],
            "Previous rounding trace changed",
        )
    if record["mode"] == "gpu_screen":
        need(
            steps.authenticate_gpu_screen(
                Path(record["gpu_screen_parent"]["path"]), parse_spec(record["definition"]), record
            )
            == record["gpu_screen_parent"],
            "Previous saved-step screen changed",
        )
    if record["mode"] == "larger_gpu_screen":
        spec = parse_spec(record["definition"])
        need(
            spec.pool.worlds == 65 and record["partition_worlds"] == [32, 33],
            "Larger screen requires 65 worlds and partitions 32+33",
        )
        need(
            authenticate_larger_parent(
                Path(record["larger_screen_parent"]["path"]), spec, record, parent
            )
            == record["larger_screen_parent"],
            "Previous complete GPU screen changed",
        )
        need(
            qualified_slices(parent, spec) == record["qualified_reference_slices"],
            "Qualified world references changed",
        )
    if record["mode"] == "energy_steps":
        need(
            authenticate_energy_parent(
                Path(record["energy_step_parent"]["path"]),
                parse_spec(record["definition"]),
                record,
                parent,
            )
            == record["energy_step_parent"],
            "Saved energy witness evidence changed",
        )
    if record["mode"] == "energy_gpu_screen":
        spec = parse_spec(record["definition"])
        need(
            spec.pool.worlds == 65 and record["partition_worlds"] == [32, 33],
            "Energy qualification requires 65 worlds and partitions 32+33",
        )
        need(
            authenticate_energy_screen(
                Path(record["energy_screen_parent"]["path"]), spec, record, parent
            )
            == record["energy_screen_parent"],
            "Passing energy witnesses changed",
        )
        need(
            qualified_slices(parent, spec) == record["qualified_reference_slices"],
            "Qualified energy-screen references changed",
        )
    return record


def rebound(spec, *, worlds, first):
    return parse_spec(
        bind_definition(
            spec.to_dict(),
            worlds=worlds,
            world_id_start=first,
            seed=(spec.pool.seed - spec.pools[0].stream_id) % 2**32,
        )
    )


def screen_settings(variants, cpu_width, gpu_width, run_wall_seconds):
    need(
        variants
        and len(set(variants)) == len(variants)
        and all(v in SCREEN_VARIANTS for v in variants),
        "Require distinct supported candidates",
    )
    need(
        type(cpu_width) is int
        and 1 <= cpu_width <= 32
        and type(gpu_width) is int
        and (
            1 <= gpu_width <= 32 or (gpu_width == 64 and list(variants) == [ENERGY_SCREEN_VARIANT])
        ),
        "Screen widths require CPU 1..32 and GPU 1..32, or the membrane-sum GPU at 64",
    )
    need(
        type(run_wall_seconds) in (int, float)
        and np.isfinite(run_wall_seconds)
        and 0 < run_wall_seconds <= PHASE_CAP,
        "Run wall budget must be finite, positive and within the phase cap",
    )
    return {
        "variants": list(variants),
        "tile_width_by_backend": {"cpu": cpu_width, "gpu": gpu_width},
        "run_wall_seconds": float(run_wall_seconds),
    }


def with_run_budget(spec, seconds):
    """Change only resource policy; preserve physics, clocks, streams and checks."""
    raw = spec.to_dict()
    for binding in raw["pools"]:
        binding["pool"]["max_wall_seconds"] = seconds
    return parse_spec(raw)


def same_world_physics(original, spec):
    """Only world membership and the wall allowance may change between references."""
    normalized = with_run_budget(
        rebound(original, worlds=spec.pool.worlds, first=spec.pool.world_id_start),
        spec.pool.max_wall_seconds,
    )
    need(normalized.to_dict() == spec.to_dict(), "Reference physical definition differs")


def authenticate_larger_parent(path, spec, settings, parent):
    result, done, previous = (
        cli.read(path / name) for name in ("result.json", "completion.json", "registration.json")
    )
    # Check the mode before following the evidence chain; never recurse into another expansion.
    need(previous["mode"] == "gpu_screen", "Require the completed three-world GPU screen")
    need(result["status"] == done["status"] == "completed", "GPU screen is incomplete")
    need(done["result_sha256"] == cli.sha(path / "result.json"), "GPU screen result changed")
    need(result["registration_sha256"] == cli.sha(path / "registration.json"), "GPU screen changed")
    authenticate(path)
    need(Path(previous["parent"]) == parent, "Larger screen uses a different qualified campaign")
    need(
        previous["drivers_sha256"]["parallel_kernel.py"]
        == cli.sha(Path(candidate_kernel.__file__)),
        "Larger screen candidate differs from screened candidate",
    )
    for key in ("variants", "tile_width_by_backend"):
        need(previous[key] == settings[key], "Larger screen execution differs: " + key)
    need(
        settings["variants"] == ["parallel_scalar_linear_sums"],
        "Require the screened GPU candidate",
    )
    need(settings["tile_width_by_backend"]["gpu"] == 32, "Larger screen requires 32-lane GPU tiles")
    same_world_physics(parse_spec(previous["definition"]), spec)
    for name, digest in previous["production_sources_sha256"].items():
        need(cli.sha(path / "source/cells" / name) == digest, "Frozen GPU screen source changed")
    for name, digest in result["evidence_sha256"].items():
        need(cli.sha(path / name) == digest, "GPU screen evidence changed: " + name)
    variant = settings["variants"][0]
    need(
        result["variants"][variant]["bounded_numerical_checks_pass"] is True,
        "Previous GPU screen did not pass",
    )
    old = parse_spec(previous["definition"])
    need(
        spec.pool.world_id_start <= old.pool.world_id_start
        and old.pool.world_id_start + old.pool.worlds
        <= spec.pool.world_id_start + spec.pool.worlds,
        "Larger screen must include the preceding reference worlds",
    )
    return {
        "path": str(path),
        "result_sha256": cli.sha(path / "result.json"),
        "cpu_reference_world_id_start": old.pool.world_id_start,
        "cpu_reference_worlds": old.pool.worlds,
    }


def authenticate_energy_parent(path, spec, settings, parent):
    result, done, previous = (
        cli.read(path / name) for name in ("result.json", "completion.json", "registration.json")
    )
    need(
        result["mode"] == previous["mode"] == "larger_gpu_screen",
        "Require a completed larger GPU screen",
    )
    need(result["status"] == done["status"] == "completed", "Larger screen is incomplete")
    need(done["result_sha256"] == cli.sha(path / "result.json"), "Larger screen result changed")
    need(
        result["registration_sha256"] == cli.sha(path / "registration.json"),
        "Larger screen changed",
    )
    authenticate(path)
    need(Path(previous["parent"]) == parent, "Energy witnesses use a different qualified campaign")
    need(previous["definition"] == spec.to_dict(), "Energy witness physical definition differs")
    for key in ("variants", "tile_width_by_backend", "run_wall_seconds"):
        need(previous[key] == settings[key], "Energy witness execution differs: " + key)
    need(settings["variants"] == [steps.ENERGY_BASELINE], "Require the rejected energy baseline")
    need(
        previous["drivers_sha256"]["parallel_kernel.py"]
        == cli.sha(Path(candidate_kernel.__file__)),
        "Energy baseline candidate changed",
    )
    for name, digest in previous["production_sources_sha256"].items():
        need(cli.sha(path / "source/cells" / name) == digest, "Frozen larger-screen source changed")
    for name, digest in result["evidence_sha256"].items():
        need(cli.sha(path / name) == digest, "Larger-screen evidence changed: " + name)
    outcome = result["variants"][steps.ENERGY_BASELINE]
    need(outcome["bounded_numerical_checks_pass"] is False, "Require a rejected larger trajectory")
    need(
        outcome["cpu_gpu_comparison"]["passed"] is True, "Require passing scalar CPU/GPU agreement"
    )
    for backend in ("cpu", "gpu"):
        need(
            cli.read(path / backend / "result.json")["reference_reproduced"] is True,
            "Larger scalar reference was not reproduced",
        )
    checks = cli.read(path / "gpu" / steps.ENERGY_BASELINE / "result.json")["comparisons"]
    for key in ("scalar_reference", "disk_roundtrip", "changed_window_restart", "world_partition"):
        need(not checks[key]["different_fields"], "Larger endpoint replay failed: " + key)
    reference = load_arrays(path / "gpu/reference-trace.npz")
    batched = load_arrays(path / "gpu" / steps.ENERGY_BASELINE / "full-trace.npz")
    return {
        "path": str(path),
        "result_sha256": cli.sha(path / "result.json"),
        "witnesses": steps.energy_witnesses(reference, batched),
    }


def require_energy_screen_pass(result):
    summary = result["variants"][steps.ENERGY_BASELINE]
    need(summary["diagnostic_reproduction_pass"] is True, "Energy witnesses did not reproduce")
    need(
        summary["saved_step_exact_by_experiment"][ENERGY_SCREEN_VARIANT]["gpu"] is True,
        "Membrane-sum witnesses did not pass",
    )


def authenticate_energy_screen(path, spec, settings, parent):
    """Bind saved-step evidence or widen a passed trajectory with the same wrapper."""
    result, done, previous = (
        cli.read(path / name) for name in ("result.json", "completion.json", "registration.json")
    )
    need(
        result["mode"] == previous["mode"]
        and previous["mode"] in ("energy_steps", "energy_gpu_screen"),
        "Require completed energy witnesses or a passed energy trajectory",
    )
    need(result["status"] == done["status"] == "completed", "Energy witnesses are incomplete")
    need(done["result_sha256"] == cli.sha(path / "result.json"), "Energy witness result changed")
    need(
        result["registration_sha256"] == cli.sha(path / "registration.json"),
        "Energy witnesses changed",
    )
    authenticate(path)
    need(Path(previous["parent"]) == parent, "Energy screen uses a different qualified campaign")
    need(previous["definition"] == spec.to_dict(), "Energy screen physical definition differs")
    need(
        settings["variants"] == [ENERGY_SCREEN_VARIANT],
        "Select only the passed membrane-sum wrapper",
    )
    need(
        previous["run_wall_seconds"] == settings["run_wall_seconds"],
        "Energy screen execution differs: run_wall_seconds",
    )
    if previous["mode"] == "energy_steps":
        need(
            previous["tile_width_by_backend"] == settings["tile_width_by_backend"],
            "Energy screen execution differs: tile_width_by_backend",
        )
        require_energy_screen_pass(result)
        reference = Path(previous["energy_step_parent"]["path"])
    else:
        outcome = result["variants"][ENERGY_SCREEN_VARIANT]
        need(
            outcome["bounded_numerical_checks_pass"] is True
            and outcome["eligible_for_performance_measurement"] is True
            and outcome["candidate_backends"] == ["gpu"]
            and outcome["cpu_execution"] == "scalar_reference"
            and outcome["cpu_gpu_comparison"]["passed"] is True,
            "Wider tiles require the passed complete GPU trajectory and scalar CPU reference",
        )
        need(
            previous["variants"] == settings["variants"]
            and previous["tile_width_by_backend"]["cpu"] == settings["tile_width_by_backend"]["cpu"]
            and previous["tile_width_by_backend"]["gpu"] == 32
            and settings["tile_width_by_backend"]["gpu"] == 64,
            "Wider qualification permits only GPU width 32 to 64; other settings stay fixed",
        )
        reference = Path(previous["energy_screen_parent"]["reference_screen"]["path"])
    for implementation in (Path(candidate_kernel.__file__), Path(steps.__file__)):
        need(
            previous["drivers_sha256"][implementation.name] == cli.sha(implementation),
            "Passing energy implementation changed: " + implementation.name,
        )
    for name, digest in previous["production_sources_sha256"].items():
        need(cli.sha(path / "source/cells" / name) == digest, "Frozen energy source changed")
    for name, digest in result["evidence_sha256"].items():
        need(cli.sha(path / name) == digest, "Energy witness evidence changed: " + name)
    return {
        "path": str(path),
        "result_sha256": cli.sha(path / "result.json"),
        "reference_screen": {
            "path": str(reference),
            "result_sha256": cli.sha(reference / "result.json"),
        },
        "reference_trace_sha256": cli.sha(reference / "gpu/reference-trace.npz"),
    }


def execution_candidate(variant, width):
    if variant == ENERGY_SCREEN_VARIANT:
        return steps.energy_experiment(variant, width)
    return candidate_kernel.candidate(variant, width=width)


def qualified_slices(parent, spec):
    """Bind an ordered, gap-free set of complete states from an authenticated campaign."""
    start, end = spec.pool.world_id_start, spec.pool.world_id_start + spec.pool.worlds
    slices = []
    for task in cli.read(parent / "result.json")["result_records"]:
        directory = parent / "tasks" / task
        original = parse_spec(cli.read(directory / "result.json")["definition"])
        first = original.pool.world_id_start
        low, high = max(start, first), min(end, first + original.pool.worlds)
        if low >= high:
            continue
        same_world_physics(original, spec)
        checkpoint = directory / "checkpoint"
        manifest = cli.read(checkpoint / "manifest.json")
        need(
            manifest["definition"] == original.to_dict(), "Checkpoint definition differs from task"
        )
        slices.append(
            {
                "checkpoint": str(checkpoint),
                "manifest_sha256": cli.sha(checkpoint / "manifest.json"),
                "state_sha256": cli.sha(checkpoint / "state.npz"),
                "world_id_start": low,
                "worlds": high - low,
                "slice_start": low - first,
            }
        )
    slices.sort(key=lambda row: row["world_id_start"])
    cursor = start
    for row in slices:
        need(row["world_id_start"] == cursor, "Qualified reference world gap or overlap")
        cursor += row["worlds"]
    need(cursor == end, "Qualified reference world range is incomplete")
    return slices


def qualified_endpoint(record, spec):
    pieces = []
    for row in record["qualified_reference_slices"]:
        saved, state, _ = load_checkpoint(Path(row["checkpoint"]), backend="gpu")
        same_world_physics(saved, spec)
        start, count = row["slice_start"], row["worlds"]
        pieces.append({k: np.asarray(v)[start : start + count] for k, v in flatten(state).items()})
    joined = {k: np.concatenate([p[k] for p in pieces]) for k in pieces[0]}
    state = rounding.state_from_arrays(engine.initial_state(spec), joined)
    state, _ = engine.validate_state(spec, state)
    need(np.all(state.tick == spec.ticks), "Qualified reference is not the complete endpoint")
    return state


def fresh_scalar_trace(root, directory, spec, backend):
    """Retain every scalar tick, including partial evidence if reference execution fails."""
    trace = rounding.TickTrace(flatten(engine.initial_state(spec)), spec.ticks)

    def observe(window, state):
        trace.append(window, flatten(state))
        if window == 1 or window % 20 == 0:
            progress(
                root,
                phase=backend,
                step="scalar_reference",
                completed_windows=window,
                tick=int(state.tick[0]),
            )

    try:
        state, report = engine.run(replace(spec, window_ticks=1), backend=backend, callback=observe)
        trajectory_comparison(trace)
        trace.save(directory / "reference-trace.npz")
        return state, report
    except Exception:
        trace.save(directory / "reference-failure-partial-trace.npz")
        cli.write(
            directory / "reference-failure.json",
            {
                "status": "failed",
                "traceback": traceback.format_exc(),
                "completed_ticks": len(trace.samples) - 1,
            },
        )
        raise


def save_arrays(path, state):
    with path.open("xb") as stream:
        np.savez_compressed(stream, **{k: np.asarray(v) for k, v in flatten(state).items()})


def load_arrays(path):
    with np.load(path, allow_pickle=False) as values:
        return {k: values[k].copy() for k in values.files}


def cpu_gpu_agreement(left, right):
    need(set(left) == set(right), "CPU/GPU fields differ")
    maximum = 0.0
    count = 0
    for key, value in left.items():
        expected = right[key]
        need(
            value.shape == expected.shape and value.dtype == expected.dtype,
            "CPU/GPU shape or dtype differs: " + key,
        )
        if value.dtype.kind in "bui":
            np.testing.assert_array_equal(value, expected, err_msg=key)
        else:
            np.testing.assert_allclose(value, expected, rtol=3e-10, atol=3e-13, err_msg=key)
            maximum = max(maximum, float(np.max(np.abs(value - expected), initial=0)))
        count += value.size
    return {
        "passed": True,
        "scalars": count,
        "maximum_absolute_difference": maximum,
        "rtol": 3e-10,
        "atol": 3e-13,
    }


def trajectory_comparison(trace):
    need(len(trace.samples) == trace.ticks + 1, "Full trajectory is incomplete")
    return {
        "compared_ticks": trace.ticks,
        "compared_states_including_initial": len(trace.samples),
        "first_divergence": trace.first,
        "different_fields": trace.first_by_field,
    }


def bounded_screen_pass(record, phases, variant, comparison):
    if not comparison["passed"]:
        return False
    if record["mode"] in GPU_ONLY_MODES:
        return (
            phases["cpu"]["role"] == "scalar_reference_only"
            and phases["cpu"]["reference_reproduced"]
            and phases["gpu"]["variants"][variant]["all_exact_checks_pass"]
            and (record["mode"] not in LARGE_GPU_MODES or phases["gpu"]["reference_reproduced"])
        )
    return all(phases[b]["variants"][variant]["all_exact_checks_pass"] for b in phases)


def phase(root, backend):
    record = authenticate(root)
    directory = root / backend
    directory.mkdir()
    cli.write(directory / "runtime.json", runtime())
    if record["mode"] == "rounding_trace":
        return rounding.phase(root, directory, backend, record, partial(progress, root))
    if record["mode"] in ("saved_steps", "energy_steps"):
        need(record["mode"] != "energy_steps" or backend == "gpu", "Energy steps require the GPU")
        return steps.phase(root, directory, backend, record, partial(progress, root))
    spec = parse_spec(record["definition"])
    progress(root, phase=backend, step="scalar_reference")
    if backend == "cpu":
        reference, report = engine.run(spec, backend=backend)
    elif record["mode"] in LARGE_GPU_MODES:
        qualified = qualified_endpoint(record, spec)
        save_arrays(directory / "qualified-reference.npz", qualified)
        if record["mode"] == "energy_gpu_screen":
            reference, report = qualified, engine.summary(spec, qualified)
        else:
            reference, report = fresh_scalar_trace(root, directory, spec, backend)
    else:
        _, original, _ = load_checkpoint(Path(record["parent_checkpoint"]), backend="gpu")
        first = record["parent_slice_start"]
        reference = jax.tree.map(lambda value: value[first : first + spec.pool.worlds], original)
        reference, _ = engine.validate_state(spec, reference)
        report = engine.summary(spec, reference)
    save_arrays(directory / "reference.npz", reference)
    cli.write(directory / "reference.json", report)
    reference_trace = None
    if record["mode"] in GPU_ONLY_MODES:
        if record["mode"] == "energy_gpu_screen":
            previous = Path(record["energy_screen_parent"]["reference_screen"]["path"])
            if backend == "gpu":
                source = previous / "gpu/reference-trace.npz"
                reference_trace = load_arrays(source)
                expected = {k: v[-1] for k, v in reference_trace.items()}
                role = "reused_authenticated_scalar_trace_and_qualified_checkpoints"
            else:
                source = previous / "cpu/reference.npz"
                expected = load_arrays(source)
                role = "fresh_scalar_cpu_against_all_prior_worlds"
            comparison = differences(expected, flatten(reference))
            cli.write(
                directory / "reference-provenance.json",
                {
                    "role": role,
                    "source": str(source),
                    "source_sha256": cli.sha(source),
                    "reference_screen": record["energy_screen_parent"]["reference_screen"],
                },
            )
        elif record["mode"] == "gpu_screen":
            trace_root = Path(record["gpu_screen_parent"]["reference_trace"]["path"])
            reference_trace = load_arrays(trace_root / backend / "reference-trace.npz")
            comparison = differences(
                {k: v[-1] for k, v in reference_trace.items()}, flatten(reference)
            )
        elif backend == "gpu":
            reference_trace = load_arrays(directory / "reference-trace.npz")
            comparison = differences(flatten(qualified), flatten(reference))
        else:
            previous = record["larger_screen_parent"]
            start = previous["cpu_reference_world_id_start"] - spec.pool.world_id_start
            count = previous["cpu_reference_worlds"]
            expected = load_arrays(Path(previous["path"]) / "cpu/reference.npz")
            comparison = differences(
                expected, {k: v[start : start + count] for k, v in flatten(reference).items()}
            ) | {"world_id_start": previous["cpu_reference_world_id_start"], "worlds": count}
        cli.write(directory / "reference-replay-comparison.json", comparison)
        need(not comparison["different_fields"], "Scalar reference endpoint changed")
        if backend == "cpu":
            cli.write(
                directory / "result.json",
                {
                    "status": "completed",
                    "backend": backend,
                    "role": "scalar_reference_only",
                    "reference_reproduced": True,
                    "comparison": comparison,
                    "scientifically_qualified": False,
                },
            )
            return
    outcomes = {}
    tile_width = record["tile_width_by_backend"][backend]
    for variant in record["variants"]:
        target = directory / variant
        target.mkdir()
        last = None
        active_run = None
        trajectory = None
        window_checks = {}

        def run(
            label,
            definition=spec,
            *,
            run_variant=variant,
            output_dir=target,
            tick_trace=None,
            recorded_windows=window_checks,
            **kwargs,
        ):
            nonlocal last, active_run
            last = None
            active_run = {
                "label": label,
                "started_time": time.time(),
                "worlds": definition.pool.worlds,
                "world_id_start": definition.pool.world_id_start,
                "window_ticks": definition.window_ticks,
                "run_wall_seconds": definition.pool.max_wall_seconds,
                "tile_width": tile_width,
            }
            progress(root, phase=backend, variant=run_variant, step=label)
            window_check = {"compared_windows": 0, "different_fields": {}}

            def observe(window, state):
                nonlocal last
                last = state
                if reference_trace is not None:
                    values = flatten(state)
                    tick = int(state.tick[0])
                    if label == "full":
                        first = tick_trace.append(window, values)
                        if first is not None:
                            cli.write(output_dir / "full-first-divergence.json", first)
                    else:
                        start = definition.pool.world_id_start - spec.pool.world_id_start
                        expected = {
                            k: v[tick, start : start + definition.pool.worlds]
                            for k, v in reference_trace.items()
                        }
                        delta = differences(expected, values)
                        if delta["different_fields"] and not window_check["different_fields"]:
                            save_arrays(output_dir / (label + "-first-different-state.npz"), state)
                            rounding.save_arrays(
                                output_dir / (label + "-first-reference-state.npz"), expected
                            )
                        for key, value in delta["different_fields"].items():
                            window_check["different_fields"].setdefault(
                                key, {"tick": tick, **value}
                            )
                        window_check["compared_windows"] += 1
                if window == 1 or window % 20 == 0:
                    progress(
                        root,
                        phase=backend,
                        variant=run_variant,
                        step=label,
                        completed_windows=window,
                        tick=int(state.tick[0]),
                    )

            state, report = engine.run(definition, backend=backend, callback=observe, **kwargs)
            save_arrays(output_dir / (label + ".npz"), state)
            cli.write(
                output_dir / (label + ".json"),
                report | {"execution_candidate": run_variant, "execution": active_run},
            )
            if reference_trace is not None:
                if label == "full":
                    tick_trace.save(output_dir / "full-trace.npz")
                    window_check = trajectory_comparison(tick_trace)
                else:
                    need(
                        window_check["compared_windows"] == report["windows"] > 0,
                        "Missing replay windows",
                    )
                cli.write(output_dir / (label + "-trajectory-comparison.json"), window_check)
                recorded_windows[label + "_trajectory"] = window_check
            return state

        try:
            with execution_candidate(variant, tile_width):
                if reference_trace is not None:
                    samples = [
                        {k: v[tick] for k, v in reference_trace.items()}
                        for tick in range(spec.ticks + 1)
                    ]
                    trajectory = rounding.TickTrace(
                        flatten(engine.initial_state(spec)), spec.ticks, reference=samples
                    )
                full = run(
                    "full",
                    replace(spec, window_ticks=1) if trajectory is not None else spec,
                    tick_trace=trajectory,
                )
                baseline_difference = differences(flatten(reference), flatten(full))
                cli.write(target / "scalar-comparison.json", baseline_difference)
                half = run("half", until=0.01)
                provenance = {
                    "experimental_variant": variant,
                    "tile_width": tile_width,
                    "registration_sha256": cli.sha(root / "registration.json"),
                    "candidate_sha256": record["drivers_sha256"]["parallel_kernel.py"],
                    "scientifically_qualified": False,
                }
                if variant == ENERGY_SCREEN_VARIANT:
                    provenance["energy_wrapper_sha256"] = record["drivers_sha256"][
                        "step_cluster.py"
                    ]
                write_checkpoint(
                    target / "checkpoint", spec, half, backend=backend, provenance=provenance
                )
                need(
                    cli.read(target / "checkpoint/manifest.json")["provenance"] == provenance,
                    "Candidate checkpoint provenance changed",
                )
                saved, checkpoint, _ = load_checkpoint(target / "checkpoint", backend=backend)
                roundtrip = differences(flatten(half), flatten(checkpoint))
                resumed = run("resumed", replace(saved, window_ticks=7), state=checkpoint)
                restart = differences(flatten(full), flatten(resumed))
                pieces = []
                first = spec.pool.world_id_start
                partitions = record.get("partition_worlds", [1, 2])
                need(
                    sum(partitions) == spec.pool.worlds,
                    "Partitions do not cover the full world range",
                )
                for index, world_count in enumerate(partitions):
                    part = rebound(spec, worlds=world_count, first=first)
                    pieces.append(flatten(run(f"partition-{index}", part)))
                    first += world_count
                joined = {k: np.concatenate([piece[k] for piece in pieces]) for k in pieces[0]}
                partition = differences(flatten(full), joined)
                checks = {
                    "scalar_reference": baseline_difference,
                    "disk_roundtrip": roundtrip,
                    "changed_window_restart": restart,
                    "world_partition": partition,
                    **window_checks,
                }
                accepted = all(not check["different_fields"] for check in checks.values())
                outcome = {
                    "status": "exact_checks_pass" if accepted else "rejected_exact_replay",
                    "all_exact_checks_pass": accepted,
                    "comparisons": checks,
                    "scientifically_qualified": False,
                }
                cli.write(target / "result.json", outcome)
                outcomes[variant] = outcome
        except Exception:
            outcome = {
                "status": "failed",
                "all_exact_checks_pass": False,
                "traceback": traceback.format_exc(),
                "failed_time": time.time(),
                "active_run": active_run,
                "scientifically_qualified": False,
            }
            if last is not None:
                save_arrays(target / "failure-last-window.npz", last)
            if trajectory is not None and not (target / "full-trace.npz").exists():
                trajectory.save(target / "failure-partial-trace.npz")
            cli.write(target / "failure.json", outcome)
            outcomes[variant] = outcome
        finally:
            jax.clear_caches()
    cli.write(
        directory / "result.json",
        {
            "status": "completed",
            "backend": backend,
            "variants": outcomes,
            "reference_reproduced": True if record["mode"] in GPU_ONLY_MODES else None,
            "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        },
    )


def controller(root):
    monitor = profile.ResourceMonitor(root)
    began = time.time()
    try:
        record = authenticate(root)
        monitor.thread.start()
        backends = ("gpu",) if record["mode"] == "energy_steps" else ("cpu", "gpu")
        for backend in backends:
            need(
                profile.memory_available() >= WORKER_ALLOWANCE + RESERVE,
                "Require 14 GiB worker allowance plus 4 GiB host reserve",
            )
            need(
                shutil.disk_usage(root).free >= RESERVE + 2 * 1024**3,
                "Require output/cache allowance and disk reserve",
            )
            environment = os.environ.copy()
            environment["JAX_PLATFORMS"] = "cpu" if backend == "cpu" else "cuda"
            command = [
                record["python"][backend],
                "-B",
                str(root / "source/parallel_cluster.py"),
                "_phase",
                str(root),
                "--backend",
                backend,
            ]
            with (
                (root / (backend + ".stdout.log")).open("x") as stdout,
                (root / (backend + ".stderr.log")).open("x") as stderr,
            ):
                subprocess.run(
                    command,
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout,
                    stderr=stderr,
                    check=True,
                    timeout=PHASE_CAP,
                )
        monitor.finish()
        outcomes = {}
        phases = {backend: cli.read(root / backend / "result.json") for backend in backends}
        for variant in record["variants"]:
            if record["mode"] in ("saved_steps", "energy_steps"):
                experiments = (
                    steps.ENERGY_EXPERIMENTS
                    if record["mode"] == "energy_steps"
                    else steps.EXPERIMENTS
                )
                outcomes[variant] = {
                    "diagnostic_reproduction_pass": all(
                        p["trace_reproduced"] for p in phases.values()
                    ),
                    "saved_step_exact_by_experiment": {
                        name: {
                            b: p["experiments"][name]["all_saved_steps_exact"]
                            for b, p in phases.items()
                        }
                        for name in experiments
                    },
                    "scientifically_qualified": False,
                }
                continue
            if record["mode"] == "rounding_trace":
                outcomes[variant] = {
                    "diagnostic_reproduction_pass": all(
                        p["trace_reproduces_prior_screen"] for p in phases.values()
                    ),
                    "first_divergence_by_backend": {
                        b: p["first_divergence"] for b, p in phases.items()
                    },
                    "scientifically_qualified": False,
                }
                continue
            endpoints = [
                root / "cpu/reference.npz"
                if b == "cpu" and record["mode"] in GPU_ONLY_MODES
                else root / b / variant / "full.npz"
                for b in ("cpu", "gpu")
            ]
            missing = [str(p.relative_to(root)) for p in endpoints if not p.exists()]
            if missing:
                comparison = {"passed": False, "status": "not_evaluated", "missing": missing}
            else:
                try:
                    comparison = cpu_gpu_agreement(*(load_arrays(p) for p in endpoints))
                except Exception:
                    comparison = {"passed": False, "traceback": traceback.format_exc()}
            passed = bounded_screen_pass(record, phases, variant, comparison)
            outcomes[variant] = {
                "cpu_gpu_comparison": comparison,
                "bounded_numerical_checks_pass": passed,
                (
                    "eligible_for_performance_measurement"
                    if record["mode"] in LARGE_GPU_MODES
                    else "eligible_for_larger_qualification"
                ): passed,
                "candidate_backends": ["gpu"]
                if record["mode"] in GPU_ONLY_MODES
                else ["cpu", "gpu"],
                "cpu_execution": "scalar_reference"
                if record["mode"] in GPU_ONLY_MODES
                else variant,
            }
        result = {
            "status": "completed",
            "mode": record["mode"],
            "variants": outcomes,
            "elapsed_seconds": time.time() - began,
            "finished_time": time.time(),
            "registration_sha256": cli.sha(root / "registration.json"),
            "evidence_sha256": {
                str(p.relative_to(root)): cli.sha(p)
                for backend in backends
                for p in sorted((root / backend).rglob("*"))
                if p.is_file()
            },
            "production_default_changed": False,
            "automatic_followup": False,
            "scope": {
                "energy_gpu_screen": (
                    f"Complete 65-world membrane-sum GPU trajectory/replay qualification "
                    f"with {record['tile_width_by_backend']['gpu']}-world tiles; "
                    "authenticated scalar GPU trace, fresh scalar CPU, partitions 32+33; "
                    "no performance claim, CPU-batching qualification or default change"
                ),
                "energy_steps": (
                    "65-world saved-step GPU energy-rounding diagnosis; "
                    "scalar/baseline reproduction and protected original operations; "
                    "no trajectory or performance acceptance"
                ),
                "larger_gpu_screen": (
                    "Complete 65-world GPU trajectory/replay qualification against scalar CPU/GPU; "
                    "two full 32-lane tiles and a partial tile, partitions 32+33; "
                    "no CPU-batching qualification, performance claim or default change"
                ),
                "gpu_screen": (
                    "Complete three-world GPU trajectory/replay screen against scalar CPU/GPU; "
                    "no CPU-batching qualification, performance claim or default change"
                ),
                "saved_steps": (
                    "Saved-step operator diagnosis; no trajectory or performance acceptance"
                ),
                "rounding_trace": (
                    "One-tick rounding diagnosis; no candidate acceptance or performance claim"
                ),
                "screen": (
                    "Bounded three-world CPU/L4 screening only; "
                    "no speedup, SM-use or broader qualification claim"
                ),
            }[record["mode"]],
        }
        cli.write(root / "result.json", result)
        cli.write(
            root / "completion.json",
            {"status": "completed", "result_sha256": cli.sha(root / "result.json")},
        )
        progress(root, status="completed", variants=outcomes)
    except BaseException:
        if monitor.thread.is_alive():
            monitor.stop.set()
            monitor.thread.join(timeout=10)
        cli.write(
            root / "failure.json",
            {
                "status": "failed",
                "traceback": traceback.format_exc(),
                "elapsed_seconds": time.time() - began,
            },
        )
        raise


def launch(
    parent,
    output,
    *,
    variants=candidate_kernel.DEFAULT_VARIANTS,
    cpu_tile_width=32,
    gpu_tile_width=32,
    run_wall_seconds=600.0,
    rounding_parent=None,
    step_parent=None,
    gpu_screen_parent=None,
    larger_screen_parent=None,
    energy_step_parent=None,
    energy_screen_parent=None,
):
    need(
        sum(
            p is not None
            for p in (
                rounding_parent,
                step_parent,
                gpu_screen_parent,
                larger_screen_parent,
                energy_step_parent,
                energy_screen_parent,
            )
        )
        <= 1,
        "Select only one diagnostic or GPU screen mode",
    )
    settings = screen_settings(variants, cpu_tile_width, gpu_tile_width, run_wall_seconds)
    need(
        settings["variants"] == [ENERGY_SCREEN_VARIANT]
        if energy_screen_parent is not None
        else ENERGY_SCREEN_VARIANT not in settings["variants"],
        "The membrane-sum candidate requires --energy-screen-parent and no other variants",
    )
    need(within_output_root(output) and not output.exists(), "Require a fresh workspace output")
    _, registration = profile.authenticate_parent(parent)
    need(
        registration["definition"]["kind"] == "assembly_cluster_ensemble@1",
        "Require a completed qualified ensemble",
    )
    anchor = cli.read(parent / "tasks/task-00000/result.json")
    original = parse_spec(anchor["definition"])
    need(
        original.pool.worlds >= 6 and original.pool.end_time_s == 0.02,
        "Require a 20-ms parent containing the three selected worlds",
    )
    need(
        original.ionic.to_dict()["model"]["id"] == "spatial_calcium@4",
        "This screen targets the qualified IP3/assembly workload",
    )
    large = any(
        p is not None for p in (larger_screen_parent, energy_step_parent, energy_screen_parent)
    )
    spec = with_run_budget(
        rebound(
            original,
            worlds=65 if large else 3,
            first=original.pool.world_id_start + (0 if large else 3),
        ),
        run_wall_seconds,
    )
    previous = (
        None
        if rounding_parent is None
        else rounding.authenticate_previous(rounding_parent, spec, settings)
    )
    witnesses = (
        None if step_parent is None else steps.authenticate_previous(step_parent, spec, settings)
    )
    gpu_screen = (
        None
        if gpu_screen_parent is None
        else steps.authenticate_gpu_screen(gpu_screen_parent, spec, settings)
    )
    larger_screen = (
        None
        if larger_screen_parent is None
        else authenticate_larger_parent(larger_screen_parent, spec, settings, parent)
    )
    energy_steps = (
        None
        if energy_step_parent is None
        else authenticate_energy_parent(energy_step_parent, spec, settings, parent)
    )
    energy_screen = (
        None
        if energy_screen_parent is None
        else authenticate_energy_screen(energy_screen_parent, spec, settings, parent)
    )
    reference_slices = (
        qualified_slices(parent, spec)
        if larger_screen is not None or energy_screen is not None
        else None
    )
    mode = "screen"
    if previous is not None:
        mode = "rounding_trace"
    elif witnesses is not None:
        mode = "saved_steps"
    elif gpu_screen is not None:
        mode = "gpu_screen"
    elif larger_screen is not None:
        mode = "larger_gpu_screen"
    elif energy_steps is not None:
        mode = "energy_steps"
    elif energy_screen is not None:
        mode = "energy_gpu_screen"
    need(profile.memory_available() >= WORKER_ALLOWANCE + RESERVE, "Insufficient host memory")
    need(shutil.disk_usage(output.parent).free >= RESERVE + 2 * 1024**3, "Insufficient disk")
    output.mkdir()
    source = output / "source"
    source.mkdir()
    shutil.copytree(
        Path(cli.__file__).parents[1],
        source / "cells",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    drivers = [
        Path(__file__),
        Path(candidate_kernel.__file__),
        Path(profile.__file__),
        Path(profile.gpu_counters.__file__),
        Path(rounding.__file__),
        Path(steps.__file__),
        Path(__file__).parents[1] / "assembly/cluster_partition_replay.py",
    ]
    for driver in drivers:
        shutil.copyfile(driver, source / driver.name)
    record = {
        "created_time": time.time(),
        "mode": mode,
        "rounding_parent": previous,
        "step_parent": witnesses,
        "gpu_screen_parent": gpu_screen,
        "larger_screen_parent": larger_screen,
        "energy_step_parent": energy_steps,
        "energy_screen_parent": energy_screen,
        "qualified_reference_slices": reference_slices,
        "partition_worlds": [32, 33] if large else [1, 2],
        "trace_window_ticks": None if mode == "screen" else 1,
        "parent": str(parent),
        "parent_result_sha256": cli.sha(parent / "result.json"),
        "parent_checkpoint": str(parent / "tasks/task-00000/checkpoint"),
        "parent_slice_start": 3,
        "definition": spec.to_dict(),
        "production_sources_sha256": cli.sources(),
        "drivers_sha256": {p.name: cli.sha(source / p.name) for p in drivers},
        "python": {b: f"/mnt/workspaces/Cells/venv-{b}/bin/python" for b in ("cpu", "gpu")},
        **settings,
        "original_run_wall_seconds": original.pool.max_wall_seconds,
        "phase_wall_cap_seconds": PHASE_CAP,
        "cpu_affinity": [4, 5],
        "prelaunch_resource_requirements": {
            "worker_allowance_bytes": WORKER_ALLOWANCE,
            "host_reserve_bytes": RESERVE,
            "output_cache_allowance_bytes": 2 * 1024**3,
            "disk_reserve_bytes": RESERVE,
            "live_rss_limit_enforced": False,
        },
        "checks": [
            "all-state exact scalar parity",
            "ordinary per-stage/accounting checks",
            "exact full disk restart with 7-tick windows",
            "exact partitions 1+2",
            "CPU/GPU existing rtol=3e-10 atol=3e-13; integer/boolean states exact",
        ],
        "production_default_changed": False,
        "automatic_followup": False,
        "scope": "Candidate screening, not general numerical or performance qualification",
    }
    if previous is not None:
        record["checks"] = [
            "complete state after each of 1600 physical ticks",
            "first differing tick and first differing tick for each state field",
            "both traced endpoints exactly reproduce the preceding screen",
            "same-input isolated field and full RHS probes before/after first divergence",
            "ordinary stage/accounting checks with unchanged tolerances",
        ]
        record["scope"] = "Rounding diagnosis only; no automatic acceptance, fix or follow-up"
    if witnesses is not None:
        record["step_experiments"] = list(steps.EXPERIMENTS)
        record["checks"] = [
            "reference and unchanged candidate reproduce saved steps from their own inputs",
            "all-state exact comparison after each selected step from identical reference inputs",
            "union of first differing ticks per field on CPU/L4, plus final step",
            "ordinary stage/accounting checks with unchanged tolerances",
            "save lowered and optimized compiler text without changing function outputs",
        ]
        record["scope"] = (
            "Saved-step operation isolation only; no trajectory acceptance or follow-up"
        )
    if mode in GPU_ONLY_MODES:
        record["execution_policy_by_backend"] = {
            "cpu": "scalar_reference_only",
            "gpu": settings["variants"][0],
        }
        record["checks"] += [
            "fresh scalar CPU endpoint exactly reproduces authenticated CPU reference",
            "complete GPU state exactly matches scalar trace at every physical tick",
            "half, resumed and partition states exactly match scalar trace at every output window",
        ]
        record["scope"] = (
            "GPU trajectory/replay screening with scalar CPU comparison; "
            "CPU batching remains unqualified; no performance claim or follow-up"
        )
    if larger_screen is not None:
        record["checks"] = [
            "65 worlds cover two full 32-lane tiles plus one padded partial tile",
            "fresh scalar GPU trace endpoint exactly reproduces qualified campaign checkpoints",
            "fresh scalar CPU endpoint reproduces previous three-world CPU reference subset",
            "complete candidate GPU state exactly matches fresh scalar trace at all 1600 ticks",
            "ordinary per-stage/accounting checks with unchanged tolerances",
            "exact full disk roundtrip and restart with 7-tick windows",
            "exact world partitions 32+33",
            "half, resumed and partition states match scalar trace at every output window",
            "all 65 CPU/GPU endpoints rtol=3e-10 atol=3e-13; integer/boolean states exact",
        ]
        record["scope"] = (
            "65-world GPU trajectory/replay qualification against scalar references; "
            "no CPU batching, performance claim, default change or automatic follow-up"
        )
    if energy_steps is not None:
        record["step_experiments"] = list(steps.ENERGY_EXPERIMENTS)
        record["execution_policy_by_backend"] = {
            "cpu": "reuse_authenticated_reference_evidence",
            "gpu": "saved_energy_witness_steps",
        }
        record["checks"] = [
            "authenticate complete rejected 65-world trace and unchanged production/baseline",
            "cover each world's first divergence, worst ULP case, recovery and final tick",
            "scalar and original candidate reproduce each saved step from their own inputs",
            "each experimental step starts from the identical complete scalar reference state",
            "complete state exact comparisons; ordinary domain/conservation checks unchanged",
            "retain before/after states and unmodified-output lowered/optimized compiler text",
        ]
        record["scope"] = (
            "GPU energy-rounding isolation at saved 65-world steps; "
            "no full-trajectory qualification, performance claim, default change or follow-up"
        )
    if energy_screen is not None:
        full_tiles, partial_worlds = divmod(spec.pool.worlds, gpu_tile_width)
        record["gpu_tile_coverage"] = {
            "tile_width": gpu_tile_width,
            "full_tiles": full_tiles,
            "partial_worlds": partial_worlds,
            "padding_worlds": (-spec.pool.worlds) % gpu_tile_width,
            "partition_worlds": record["partition_worlds"],
        }
        record["checks"] = [
            "unchanged membrane-sum wrapper and batching code bound to passing evidence",
            f"65 worlds, {full_tiles} full {gpu_tile_width}-world tiles and a partial tile "
            f"with {partial_worlds} real worlds",
            "authenticate complete scalar GPU trace and reproduce its qualified endpoint",
            "fresh scalar CPU endpoint exactly reproduces all 65 prior reference worlds",
            "complete candidate state exactly matches scalar GPU at each of 1600 ticks",
            "ordinary per-stage, domain and conservation checks with unchanged tolerances",
            "exact complete disk roundtrip, restart with 7-tick windows and partitions 32+33",
            "half, restart and partitions match scalar trace at every output window",
            "all CPU/GPU endpoints rtol=3e-10 atol=3e-13; integer/boolean states exact",
        ]
        record["scope"] = (
            "65-world membrane-sum GPU qualification using the authenticated scalar GPU trace "
            "and a fresh scalar CPU run; no performance claim, default change or follow-up"
        )
    environment = os.environ.copy()
    environment.update(
        PYTHONPATH=str(source),
        PYTHONDONTWRITEBYTECODE="1",
        JAX_ENABLE_X64="1",
        JAX_PLATFORMS="cpu",
        XLA_PYTHON_CLIENT_PREALLOCATE="false",
        XLA_PYTHON_CLIENT_MEM_FRACTION="0.2",
    )
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        environment[name] = "1"
    for name, subdir in (
        ("TMPDIR", "tmp"),
        ("XDG_CACHE_HOME", "cache"),
        ("CUDA_CACHE_PATH", "cache/cuda"),
        ("JAX_COMPILATION_CACHE_DIR", "cache/jax"),
    ):
        path = output / subdir
        path.mkdir(parents=True, exist_ok=True)
        environment[name] = str(path)
    command = [
        "taskset",
        "-c",
        "4,5",
        record["python"]["cpu"],
        "-B",
        str(source / "parallel_cluster.py"),
        "_run",
        str(output),
    ]
    record["command"] = command
    record["environment"] = {
        name: value
        for name, value in environment.items()
        if name.startswith(("JAX_", "XLA_", "CUDA_"))
        or name
        in {
            "PYTHONPATH",
            "PYTHONDONTWRITEBYTECODE",
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS",
            "TMPDIR",
            "XDG_CACHE_HOME",
        }
    }
    cli.write(output / "registration.json", record)
    with (output / "stdout.log").open("x") as stdout, (output / "stderr.log").open("x") as stderr:
        child = subprocess.Popen(
            command,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
            close_fds=True,
        )
    receipt = {
        "status": "launched",
        "pid": child.pid,
        "time": time.time(),
        "output": str(output),
        "maximum_phase_seconds": PHASE_CAP,
    }
    cli.write(output / "launch.json", receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("launch")
    start.add_argument("--parent", type=Path, required=True)
    start.add_argument("--output", type=Path, required=True)
    start.add_argument(
        "--variants",
        nargs="+",
        choices=SCREEN_VARIANTS,
        default=candidate_kernel.DEFAULT_VARIANTS,
    )
    start.add_argument("--cpu-tile-width", type=int, default=32)
    start.add_argument("--gpu-tile-width", type=int, default=32)
    start.add_argument("--run-wall-seconds", type=float, default=600.0)
    diagnostic = start.add_mutually_exclusive_group()
    diagnostic.add_argument("--rounding-parent", type=Path)
    diagnostic.add_argument("--step-parent", type=Path)
    diagnostic.add_argument("--gpu-screen-parent", type=Path)
    diagnostic.add_argument("--larger-screen-parent", type=Path)
    diagnostic.add_argument("--energy-step-parent", type=Path)
    diagnostic.add_argument("--energy-screen-parent", type=Path)
    sub.add_parser("_run").add_argument("output", type=Path)
    internal = sub.add_parser("_phase")
    internal.add_argument("output", type=Path)
    internal.add_argument("--backend", choices=("cpu", "gpu"), required=True)
    args = parser.parse_args()
    if args.command == "launch":
        receipt = launch(
            args.parent.resolve(),
            args.output.resolve(),
            variants=args.variants,
            cpu_tile_width=args.cpu_tile_width,
            gpu_tile_width=args.gpu_tile_width,
            run_wall_seconds=args.run_wall_seconds,
            rounding_parent=None
            if args.rounding_parent is None
            else args.rounding_parent.resolve(),
            step_parent=None if args.step_parent is None else args.step_parent.resolve(),
            gpu_screen_parent=None
            if args.gpu_screen_parent is None
            else args.gpu_screen_parent.resolve(),
            larger_screen_parent=None
            if args.larger_screen_parent is None
            else args.larger_screen_parent.resolve(),
            energy_step_parent=None
            if args.energy_step_parent is None
            else args.energy_step_parent.resolve(),
            energy_screen_parent=None
            if args.energy_screen_parent is None
            else args.energy_screen_parent.resolve(),
        )
        print(json.dumps(receipt, indent=2))
    elif args.command == "_run":
        controller(args.output.resolve())
    else:
        phase(args.output.resolve(), args.backend)
