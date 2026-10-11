"""Reuse Cells, adaptive references and a separate opt-in GPU kernel probe."""

import copy
import time
from types import SimpleNamespace

import common as u


def reference(output, preparation, plan):
    u.module_path("pump_matched_pilot")
    import pilot_reference

    prepared = dict(preparation, protocol=plan)
    prepared["cases"] = copy.deepcopy(preparation["cases"])
    for case in prepared["cases"].values():
        case["end_time_s"] = plan["duration_s"]
    result = pilot_reference.worker(prepared, output)
    u.write(output / "reference.json", result)
    return {k: v for k, v in result.items() if k != "records"}


def cells(output, preparation, plan):
    u.module_path("pump_matched_pilot")
    module = u.private(
        "_fresh_cpu_cells", u.ROOT / "validation/betse/pump_matched_pilot/pilot_cells.py"
    )
    original = module.ctx

    def definition(case, dt, *, jit=True):
        return original.definition(case, dt, jit=jit, times=plan["common_times_s"])

    module.ctx = SimpleNamespace(**(vars(original) | {"definition": definition}))
    prepared = dict(preparation, protocol=plan)
    prepared["cases"] = copy.deepcopy(preparation["cases"])
    for case in prepared["cases"].values():
        case["end_time_s"] = plan["duration_s"]
    result = module.worker(prepared, output)
    result.update(
        duration_s=plan["duration_s"], registration_sha256=u.sha(output / "registration.json")
    )
    u.write(output / "cells.json", result)
    return {k: v for k, v in result.items() if k not in ("records", "resumes")}


def gpu(output, preparation, plan, cpu_output, *, variants=u.VARIANTS):
    import jax
    import numpy as np

    from cells.core.runner import _analyse_segment, _compiled_checked_rollout, timeline
    from cells.core.schedule import control_values, event_index
    from cells.core.specs import parse_spec
    from cells.core.state import Checkpoint
    from cells.models.registry import get_model

    u.module_path("pump_matched_pilot")
    import pilot_context

    jax.config.update("jax_enable_x64", True)
    device = jax.devices("gpu")[0]
    u.need(device.platform in ("gpu", "cuda") and jax.config.x64_enabled, "CUDA float64 required")
    cpu = u.read(cpu_output / "cells.json")
    records = []
    for name in variants:
        case = dict(preparation["cases"][name], end_time_s=plan["duration_s"])
        for dt in plan["cells_steps_s"]:
            began = time.monotonic()
            spec = parse_spec(pilot_context.definition(case, dt, times=plan["common_times_s"]))
            model = get_model(spec.model)
            state, layout = model.initial_values(spec)
            times = timeline(spec)
            controls = control_values(spec, times[:-1])
            args = jax.device_put(
                (state, np.diff(times), controls, model.parameters(spec, layout), layout.active),
                device,
            )
            jax.block_until_ready(args)
            start_compile = time.monotonic()
            compiled = _compiled_checked_rollout.lower(
                *args, model.rhs, model.domain_valid
            ).compile()
            compile_s = time.monotonic() - start_compile
            start_run = time.monotonic()
            final, history, valid = compiled(*args)
            jax.block_until_ready((final, history, valid))
            execute_s = time.monotonic() - start_run
            u.need(bool(np.asarray(valid).all()), "GPU rejected an RK4 stage")
            u.need(
                all(v.device == device for v in jax.tree.leaves(final)),
                "GPU result placed on another device",
            )
            arrays = tuple(
                np.concatenate((np.asarray(a)[None], np.asarray(b)), axis=0)
                for a, b in zip(state, history, strict=True)
            )
            start = Checkpoint(state, layout, 0.0, 0, event_index(spec, 0.0))
            _, observations, _, diagnostics = _analyse_segment(
                spec, start, times, arrays, final, layout, list(spec.experiment.observation_times)
            )
            key = pilot_context.key(name, dt) + "/jax_jit"
            directory = output / name / format(dt, ".8g")
            directory.mkdir(parents=True)
            np.savez_compressed(
                directory / "trajectory.npz",
                accepted_times=times,
                **dict(zip(state._fields, arrays, strict=True)),
            )
            # Save complete initial/final state and layout as a probe artifact;
            # it is deliberately not a public Cells GPU-checkpoint schema.
            np.savez_compressed(directory / "initial.npz", **state._asdict(), **layout._asdict())
            np.savez_compressed(
                directory / "final.npz",
                **{k: np.asarray(v) for k, v in final._asdict().items()},
                **layout._asdict(),
            )
            errors = {}
            with np.load(
                cpu_output / cpu["records"][key]["directory"] / "trajectory.npz", allow_pickle=False
            ) as saved:
                u.need(np.array_equal(times, saved["accepted_times"]), "GPU/CPU time grids differ")
                for field, values in zip(state._fields, arrays, strict=True):
                    target = saved[field]
                    error = np.abs(values - target)
                    u.need(
                        values.shape == target.shape and bool(np.isfinite(values).all()),
                        "GPU state shape/domain",
                    )
                    u.need(
                        bool((error <= 2e-12 + 2e-11 * np.abs(target)).all()),
                        "GPU/CPU state mismatch: " + field,
                    )
                    errors[field] = float(error.max(initial=0.0))
                voltage = np.asarray(observations.voltage_V)
                u.need(
                    bool(
                        (
                            np.abs(voltage - saved["observed_voltage_V"])
                            <= 2e-10 + 2e-11 * np.abs(saved["observed_voltage_V"])
                        ).all()
                    ),
                    "GPU/CPU voltage mismatch",
                )
            midpoint = int(np.flatnonzero(times == plan["restart_time_s"])[0])
            np.savez_compressed(
                directory / "restart.npz",
                **{k: v[midpoint] for k, v in zip(state._fields, arrays, strict=True)},
                **layout._asdict(),
            )
            with np.load(directory / "restart.npz", allow_pickle=False) as saved:
                resumed_state = model.STATE_TYPE(*(saved[k].copy() for k in state._fields))
                resumed_layout = model.LAYOUT_TYPE(*(saved[k].copy() for k in layout._fields))
            resume_args = jax.device_put(
                (
                    resumed_state,
                    np.diff(times[midpoint:]),
                    control_values(spec, times[midpoint:-1]),
                    model.parameters(spec, resumed_layout),
                    resumed_layout.active,
                ),
                device,
            )
            resume_kernel = _compiled_checked_rollout.lower(
                *resume_args, model.rhs, model.domain_valid
            ).compile()
            _, suffix, suffix_valid = resume_kernel(*resume_args)
            jax.block_until_ready((suffix, suffix_valid))
            u.need(bool(np.asarray(suffix_valid).all()), "GPU restart domain")
            u.need(
                all(
                    np.array_equal(v[midpoint + 1 :], np.asarray(w))
                    for v, w in zip(arrays, suffix, strict=True)
                ),
                "GPU saved restart suffix differs",
            )
            row = dict(
                case=name,
                dt_s=dt,
                device=str(device),
                gpu_kind=device.device_kind,
                precision="float64",
                state_errors=errors,
                diagnostics=diagnostics,
                compile_seconds=compile_s,
                execute_seconds=execute_s,
                total_seconds=time.monotonic() - began,
                saved_restart_exact=True,
                trajectory_sha256=u.sha(directory / "trajectory.npz"),
                unchanged_checked_rk4_kernel=True,
                public_gpu_backend=False,
                source_spec_backend="cpu",
                execution_override="explicit CUDA kernel probe",
            )
            u.write(directory / "result.json", row)
            records.append(row)
            print("GPU matched trajectory:", key, flush=True)
    result = dict(
        status="gpu_kernel_probe_pass",
        records=records,
        trajectories=len(records),
        public_gpu_backend=False,
        speedup_established=False,
    )
    u.write(output / "gpu.json", result)
    return result
