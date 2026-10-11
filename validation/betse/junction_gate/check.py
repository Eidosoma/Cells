"""Native compatibility, physical-time separation and CPU/L4 process qualification."""

import argparse
import sys
import time
from functools import partial
from pathlib import Path

import compatibility
import jax
import jax.numpy as jnp
import numpy as np
import reference

from cells.processes import junction_gate as gate

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fresh_rerun"))
import common as u  # noqa: E402


def maximum(value):
    return float(np.max(np.abs(value)))


def native_check(directory, protocol):
    panel = u.read(directory / "native/panel.json")
    u.need(panel["protocol"] == protocol, "Native clamp protocol changed")
    expected = {
        (count, dt)
        for count in protocol["calls_per_outer_step"]
        for dt in protocol["native_steps_s"]
    }
    u.need(
        len(panel["rows"]) == len(expected)
        and {(r["calls_per_outer_step"], r["dt_s"]) for r in panel["rows"]} == expected,
        "Missing or duplicate native clamp rows",
    )
    params = gate.Parameters(protocol["threshold_voltage_V"], protocol["minimum_open_fraction"])
    volts = np.repeat(protocol["voltages_V"], len(protocol["initial_gates"]))
    initial = np.tile(protocol["initial_gates"], len(protocol["voltages_V"]))
    tol = protocol["tolerances"]
    reports, errors = [], {count: [] for count in protocol["calls_per_outer_step"]}
    physical_ends, value = [], initial.copy()
    for phase in protocol["phases"]:
        value = reference.solution(
            value, volts * phase["voltage_multiplier"], *params, phase["duration_s"]
        )
        physical_ends.append(value)
    for row in panel["rows"]:
        path = directory / "native" / row["path"]
        u.need(u.sha(path) == row["sha256"] and row["observer_pair_exact"], "Native clamp changed")
        with np.load(path, allow_pickle=False) as archive:
            history, times, phases = archive["gate"], archive["times_s"], archive["phase"]
        dt, calls = row["dt_s"], row["calls_per_outer_step"]
        lengths = [round(p["duration_s"] / dt) for p in protocol["phases"]]
        u.need(row["steps"] == sum(lengths), "Native clamp step count changed")
        np.testing.assert_array_equal(times, np.arange(sum(lengths) + 1) * dt)
        np.testing.assert_array_equal(phases[1:], np.repeat(np.arange(len(lengths)), lengths))
        np.testing.assert_array_equal(history[0], initial)
        np.testing.assert_array_equal(row["initialization"]["sim_gate"], initial)
        np.testing.assert_allclose(
            row["initialization"]["class_gate"],
            compatibility.class_initialization(volts, 1.0, params),
            rtol=tol["source_gate_rtol"],
            atol=tol["source_gate_atol"],
        )
        voltage = (
            np.asarray([p["voltage_multiplier"] for p in protocol["phases"]])[phases[1:], None]
            * volts
        )
        block = np.asarray([p["availability"] for p in protocol["phases"]])[phases[1:], None]
        adapted = history[:-1].copy()
        for _ in range(calls):
            adapted = compatibility.step(adapted, voltage, block, dt, params)
        np.testing.assert_allclose(
            adapted, history[1:], rtol=tol["source_gate_rtol"], atol=tol["source_gate_atol"]
        )
        end = lengths[0] + 1
        matched = reference.solution(initial, volts, *params, times[:end], clock=calls)
        normal_clock = reference.solution(initial, volts, *params, times[:end])
        error = maximum(history[:end] - matched)
        errors[calls].append(error)
        clock_difference = maximum(history[:end] - normal_clock)
        if calls == 3:
            u.need(
                clock_difference > tol["minimum_clock_difference"], "Source clock difference absent"
            )
        phase_ends = np.cumsum(lengths)
        np.testing.assert_array_equal(history[phase_ends[2]], 0)
        blocking_difference = maximum(history[phase_ends[2]] - physical_ends[2])
        u.need(
            blocking_difference > tol["minimum_block_state_difference"],
            "Native blocking incorrectly equated to physical availability",
        )
        reports.append(
            {
                "path": row["path"],
                "dt_s": dt,
                "calls_per_outer_step": calls,
                "max_adapter_error": maximum(adapted - history[1:]),
                "unblocked_matched_clock_error": error,
                "unblocked_physical_clock_difference": clock_difference,
                "blocked_intrinsic_state_difference": blocking_difference,
            }
        )
    u.write(directory / "native-checks.json", {"rows": reports, "refinement_errors": errors})
    for local in errors.values():
        u.need(local[-1] <= tol["native_finest_gate_atol"], "Native clamp finest error")
        for coarse, fine in zip(local[:-1], local[1:], strict=True):
            u.need(
                fine <= tol["native_refinement_ratio_max"] * coarse + 1e-12,
                "Native clamp refinement failed",
            )
    return reports


def device_inputs(protocol):
    threshold, minimum, voltage, fraction = np.meshgrid(
        protocol["device_thresholds_V"],
        protocol["device_minimums"],
        protocol["voltages_V"],
        protocol["device_initial_fractions"],
        indexing="ij",
    )
    threshold, minimum, voltage, fraction = (
        a.ravel() for a in (threshold, minimum, voltage, fraction)
    )
    return minimum + (1 - minimum) * fraction, voltage, gate.Parameters(threshold, minimum)


@partial(jax.jit, static_argnames=("steps",))
def evolve(initial, voltage, parameters, dt, *, steps):
    return jax.lax.fori_loop(
        0, steps, lambda _, state: gate.advance_clamped(state, voltage, parameters, dt), initial
    )


def device_check(directory, protocol, backend, analytic):
    devices = jax.devices(backend)
    u.need(devices and devices[0].platform == backend, "Requested process backend unavailable")
    device = devices[0]
    initial, voltage, parameters = device_inputs(protocol)
    index = np.arange(protocol["device_worlds"]) % len(initial)
    initial, voltage = initial[index], voltage[index]
    parameters = gate.Parameters(*(p[index] for p in parameters))
    u.need(
        np.all(gate.domain_valid(initial, voltage, parameters, 1.0, xp=np)),
        "Invalid device fixture",
    )

    def put(array):
        return jax.device_put(np.asarray(array, dtype=np.float64), device)

    state, volts = put(initial), put(voltage)
    params = gate.Parameters(*(put(p) for p in parameters))
    dt, phases = protocol["device_step_s"], protocol["phases"]
    histories, began = [np.asarray(state)], time.monotonic()
    checkpoint = directory / f"{backend}-checkpoint.npz"
    for i, phase in enumerate(phases):
        state = evolve(
            state,
            volts * phase["voltage_multiplier"],
            params,
            dt,
            steps=round(phase["duration_s"] / dt),
        )
        state.block_until_ready()
        u.need(state.dtype == jnp.float64 and state.devices() == {device}, "Wrong dtype/device")
        host = np.asarray(state)
        u.need(
            np.all(
                gate.domain_valid(
                    host,
                    voltage * phase["voltage_multiplier"],
                    parameters,
                    phase["availability"],
                    dt,
                    xp=np,
                )
            ),
            "Gate left physical domain",
        )
        histories.append(host)
        if i == 1:
            np.savez_compressed(
                checkpoint,
                gate=host,
                voltage=voltage,
                threshold=parameters.threshold_voltage_V,
                minimum=parameters.minimum_open_fraction,
                next_phase=np.asarray(i + 1),
                physical_time_s=np.asarray(sum(p["duration_s"] for p in phases[: i + 1])),
                dt_s=np.asarray(dt),
            )
    elapsed = time.monotonic() - began
    history = np.asarray(histories)
    target = analytic[:, index]
    np.testing.assert_allclose(
        history, target, rtol=0, atol=protocol["tolerances"]["physical_gate_atol"]
    )
    # Save/load every state/parameter/clock coordinate used by this clamp harness.
    # This is gate-state replay, not a production world checkpoint qualification.
    with np.load(checkpoint, allow_pickle=False) as saved:
        u.need(
            float(saved["physical_time_s"]) == sum(p["duration_s"] for p in phases[:2])
            and float(saved["dt_s"]) == dt
            and int(saved["next_phase"]) == 2,
            "Gate checkpoint clock changed",
        )
        resumed, resume_voltage = put(saved["gate"]), put(saved["voltage"])
        resume_parameters = gate.Parameters(put(saved["threshold"]), put(saved["minimum"]))
    for phase in phases[2:]:
        resumed = evolve(
            resumed,
            resume_voltage * phase["voltage_multiplier"],
            resume_parameters,
            dt,
            steps=round(phase["duration_s"] / dt),
        )
    np.testing.assert_array_equal(np.asarray(resumed), history[-1])
    parts = []
    for selection in (slice(0, len(initial) // 2), slice(len(initial) // 2, None)):
        local = put(initial[selection])
        local_parameters = gate.Parameters(*(put(p[selection]) for p in parameters))
        for phase in phases:
            local = evolve(
                local,
                put(voltage[selection]) * phase["voltage_multiplier"],
                local_parameters,
                dt,
                steps=round(phase["duration_s"] / dt),
            )
        parts.append(np.asarray(local))
    np.testing.assert_array_equal(np.concatenate(parts), history[-1])
    np.savez_compressed(
        directory / f"{backend}-history.npz",
        gate=history,
        route_index=index,
        availability=np.asarray([p["availability"] for p in phases]),
        phase_open_fraction=history[1:] * np.asarray([p["availability"] for p in phases])[:, None],
    )
    return history, {
        "backend": backend,
        "device": str(device),
        "device_kind": device.device_kind,
        "dtype": str(state.dtype),
        "worlds": len(initial),
        "compile_and_execution_seconds": elapsed,
        "max_analytic_error": maximum(history - target),
        "gate_disk_restart_exact": True,
        "world_partition_exact": True,
    }


def physical_reference(directory, protocol):
    """Record numerical reference evidence before enforcing its error limit."""
    initial, voltage, params = device_inputs(protocol)
    values, reports = [initial], []
    for phase_index, phase in enumerate(protocol["phases"]):
        v = voltage * phase["voltage_multiplier"]
        answer = reference.ode(values[-1], v, *params, phase["duration_s"])
        times = np.linspace(0, phase["duration_s"], 21)
        exact = reference.solution(values[-1], v, *params, times)
        difference = np.abs(answer.sol(times).T - exact)
        sample, route = np.unravel_index(np.argmax(difference), difference.shape)
        reports.append(
            {
                "phase": phase_index,
                "max_error": maximum(difference),
                "steps": len(answer.t) - 1,
                "nfev": answer.nfev,
                "max_accepted_step_s": float(np.max(np.diff(answer.t))),
                "worst_time_s": float(times[sample]),
                "worst_route": {
                    "index": int(route),
                    "threshold_V": float(params.threshold_voltage_V[route]),
                    "minimum": float(params.minimum_open_fraction[route]),
                    "voltage_V": float(v[route]),
                    "initial": float(values[-1][route]),
                },
            }
        )
        values.append(exact[-1])
    analytic = np.asarray(values)
    np.savez_compressed(
        directory / "reference.npz",
        gate=analytic,
        initial=initial,
        voltage=voltage,
        threshold=params.threshold_voltage_V,
        minimum=params.minimum_open_fraction,
    )
    u.write(
        directory / "reference-checks.json",
        {"atol": protocol["tolerances"]["physical_gate_atol"], "phases": reports},
    )
    error = max(row["max_error"] for row in reports)
    u.need(
        error <= protocol["tolerances"]["physical_gate_atol"],
        f"Independent ODE disagreement: {error:.17g}; see comparison/reference-checks.json",
    )
    return analytic, [row["max_error"] for row in reports]


def check(output):
    protocol = u.read(output / "protocol.json")
    initial_runtime = u.runtime()
    u.need(jax.config.x64_enabled and not jax.config.jax_disable_jit, "Require float64/JIT")
    u.need(gate.LAW_ID == protocol["law"], "Wrong named gate process")
    native = native_check(output, protocol)
    directory = output / "comparison"
    directory.mkdir(exist_ok=False)
    analytic, ode_errors = physical_reference(directory, protocol)
    cpu, cpu_report = device_check(directory, protocol, "cpu", analytic)
    gpu, gpu_report = device_check(directory, protocol, "gpu", analytic)
    np.testing.assert_allclose(cpu, gpu, rtol=0, atol=protocol["tolerances"]["physical_gate_atol"])
    u.need(initial_runtime == u.runtime(), "Gate checker runtime changed")
    return {
        "status": "junction_gate_process_cpu_gpu_pass",
        "law": gate.LAW_ID,
        "native_rows": native,
        "native_recorded_bare_pairs": len(native),
        "native_clamp_routes": len(protocol["voltages_V"]) * len(protocol["initial_gates"]),
        "native_checks_sha256": u.sha(output / "native-checks.json"),
        "independent_ode_max_errors": ode_errors,
        "devices": [cpu_report, gpu_report],
        "max_cpu_gpu_error": maximum(cpu - gpu),
        "runtime": initial_runtime,
        "comparison_files_sha256": u.inventory(directory),
        "coupled_free_voltage_qualified": False,
        "production_world_gate_selectable": False,
        "biological_validation": False,
        "multi_gpu_scaling": False,
        "scope": protocol["physical_scope"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    u.write(args.output / "comparison-result.json", check(args.output))
