"""Bounded, checked RK4 mechanics for independent fixed-control graph candidates.

No production/native imports, implicit method overrides or phenotype acceptance.
Full short-fixture evidence is explicit; this is not long-time qualification.
"""

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import numpy as np

from tests import reference_graph_paths as paths
from tests import reference_source_graph_numerics as ref

REVISION = "checked_graph_rk4@1-engineering"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class Grid:
    step: float
    end: float

    def __post_init__(self):
        if (
            isinstance(self.step, bool)
            or isinstance(self.end, bool)
            or not np.isfinite(self.step)
            or not np.isfinite(self.end)
            or self.step <= 0
            or self.end <= 0
            or not np.isfinite(self.end / self.step)
            or self.end / self.step >= 2**53
        ):
            raise ValueError("Invalid global RK4 grid")

    @property
    def count(self):
        count = math.ceil(self.end / self.step)
        # Division may round to either side of an integer. Match the actual
        # multiplication grid, including a shortened exact final interval.
        while count > 1 and (count - 1) * self.step >= self.end:
            count -= 1
        while count * self.step < self.end:
            count += 1
        return count

    def time(self, index):
        if type(index) is not int or index < 0:
            raise ValueError("Expected a nonnegative global tick")
        return min(index * self.step, self.end)

    def points(self, start_step=0):
        yield self.time(start_step)
        for tick in range(start_step, self.count):
            a, b = self.time(tick), self.time(tick + 1)
            if not b > a:
                raise ValueError("RK4 clock cannot advance in binary64")
            yield a + (b - a) / 2
            yield b


def rk4_step(rhs, time, end, value):
    """Classical RK4 plus endpoint slope; retain exact tested operation ordering."""
    h = end - time
    if not np.isfinite(h) or h <= 0:
        raise ValueError("Nonpositive RK4 interval")
    k1 = rhs(time, value)
    k2 = rhs(time + h / 2, value + h * k1 / 2)
    k3 = rhs(time + h / 2, value + h * k2 / 2)
    k4 = rhs(end, value + h * k3)
    result = value + h * (k1 + 2 * k2 + 2 * k3 + k4) / 6
    right = rhs(end, result)
    change, left, right_scaled = result - value, h * k1, h * right
    coefficients = np.stack(
        (value, left, 3 * change - 2 * left - right_scaled, -2 * change + left + right_scaled)
    )
    return result, np.stack((k1, k2, k3, k4, right)), coefficients


def check_state(model, value, accounting_atol):
    """Constant-state domain/accounting checks without solving polynomial roots."""
    if value.shape != (model.coordinates.size,) or not np.isfinite(value).all():
        raise ValueError("Invalid complete candidate state")
    model.validate_primary(value[: 6 * model.n].reshape(6, model.n) + model.anchor)
    maximum = float(np.max(abs(ref.residual(model, value))))
    if maximum > accounting_atol:
        raise ValueError("Candidate stage accounting failed")
    if np.any(value[ref.blocked_coordinates(model)] != 0):
        raise ValueError("Blocked candidate history changed")
    return maximum


def contract(model, grid, numerics, identity):
    return {
        "revision": REVISION,
        "case": model.case,
        "step": grid.step,
        "end": grid.end,
        "numerics": numerics,
        "numerical_source_runtime_identity": identity,
    }


def load_checkpoint(directory, chunk, expected_contract):
    """Only hash-checked recorded accepted boundaries, never arbitrary state injection."""
    directory = Path(directory).absolute()
    attempt = ref.read_json(directory / "attempt.json")
    if attempt["contract"] != expected_contract or attempt["contract_sha256"] != digest(
        expected_contract
    ):
        raise ValueError("Candidate checkpoint numerical identity differs")
    if type(chunk) is not int or chunk < 0:
        raise ValueError("Invalid checkpoint chunk")
    entry = None
    with (directory / "chunks.jsonl").open() as handle:
        for index, line in enumerate(handle):
            if index == chunk:
                entry = json.loads(line)
                break
    if entry is None or entry["path"] != f"chunk-{chunk:06d}.npz":
        raise ValueError("Checkpoint is not a recorded boundary")
    path = directory / entry["path"]
    if path.resolve() != path or ref.sha(path) != entry["sha256"]:
        raise ValueError("Candidate checkpoint payload differs")
    with np.load(path, allow_pickle=False) as data:
        state = data["increments"][-1].copy()
        step, time = int(data["ticks"][-1]), float(data["times"][-1])
        np.testing.assert_array_equal(data["anchor"], expected_contract["case"]["primary"])
        np.testing.assert_array_equal(data["context"], expected_contract["case"]["context"])
    grid = Grid(expected_contract["step"], expected_contract["end"])
    if (
        not 0 < step <= grid.count
        or time != grid.time(step)
        or entry["end"] != time
        or entry["end_tick"] != step
    ):
        raise ValueError("Checkpoint global clock differs")
    return {
        "parent_directory": str(directory),
        "parent_chunk": chunk,
        "parent_attempt_sha256": ref.sha(directory / "attempt.json"),
        "parent_chunk_sha256": entry["sha256"],
        "contract_sha256": digest(expected_contract),
        "tick": step,
        "time": time,
        "increments": state.tolist(),
    }


def sample_window(data, times):
    """Cubic interior samples; exact accepted endpoints are copied, not reconstructed."""
    times = np.asarray(times, dtype=np.float64)
    t, values, c = (data[k] for k in ("times", "increments", "coefficients"))
    if (
        times.ndim != 1
        or not np.isfinite(times).all()
        or np.any(np.diff(times) < 0)
        or (len(times) and (times[0] < t[0] or times[-1] > t[-1]))
    ):
        raise ValueError("Candidate sample outside its bounded window")
    right = np.searchsorted(t, times)
    indices = np.minimum(np.maximum(right - 1, 0), len(t) - 2)
    theta = ((times - t[indices]) / (t[indices + 1] - t[indices]))[:, None]
    chosen = c[indices]
    result = ((chosen[:, 3] * theta + chosen[:, 2]) * theta + chosen[:, 1]) * theta + chosen[:, 0]
    exact = t[right] == times
    result[exact] = values[right[exact]]
    return result


class Recorder:
    """Detached bounded windows and complete accepted checkpoints, no history list."""

    def __init__(self, model, output, resources, root, grid, tick, value, consumer):
        self.model, self.output, self.resources, self.root = model, output, resources, root
        self.grid, self.consumer = grid, consumer
        self.width, size = resources["window_steps"], model.coordinates.size
        self.times = np.empty(self.width + 1)
        self.ticks = np.empty(self.width + 1, dtype=np.int64)
        self.values = np.empty((self.width + 1, size))
        self.coefficients = np.empty((self.width, 4, size))
        self.slopes = np.empty((self.width, 5, size))
        self.times[0], self.ticks[0], self.values[0] = grid.time(tick), tick, value
        self.buffered = self.chunks = 0
        self.raw_array_bytes = self.recording_seconds = self.comparison_seconds = 0

    def append(self, tick, value, slopes, coefficients):
        index = self.buffered
        self.slopes[index], self.coefficients[index] = slopes, coefficients
        self.buffered += 1
        self.times[self.buffered], self.ticks[self.buffered], self.values[self.buffered] = (
            self.grid.time(tick),
            tick,
            value,
        )
        if self.buffered == self.width:
            self.flush()

    def flush(self, *, compare=True):
        width = self.buffered
        if not width:
            return
        begun = perf_counter()
        data = {
            "times": self.times[: width + 1].copy(),
            "ticks": self.ticks[: width + 1].copy(),
            "increments": self.values[: width + 1].copy(),
            "coefficients": self.coefficients[:width].copy(),
            "slopes": self.slopes[:width].copy(),
            "anchor": self.model.anchor,
            "context": self.model.context,
        }
        path = self.output / f"chunk-{self.chunks:06d}.npz"
        paths.save_arrays(path, data, self.root, self.resources["artifact_budget_bytes"])
        entry = {
            "path": path.name,
            "sha256": ref.sha(path),
            "steps": width,
            "start": float(data["times"][0]),
            "end": float(data["times"][-1]),
            "start_tick": int(data["ticks"][0]),
            "end_tick": int(data["ticks"][-1]),
        }
        with (self.output / "chunks.jsonl").open("a") as handle:
            handle.write(json.dumps(entry, sort_keys=True, allow_nan=False) + "\n")
        self.raw_array_bytes += sum(value.nbytes for value in data.values())
        self.times[0], self.ticks[0], self.values[0] = (
            data["times"][-1],
            data["ticks"][-1],
            data["increments"][-1],
        )
        self.buffered = 0
        self.chunks += 1
        self.recording_seconds += perf_counter() - begun
        if compare and self.consumer is not None:
            begun = perf_counter()
            self.consumer.consume(data)
            self.comparison_seconds += perf_counter() - begun


def integrate(
    model,
    output,
    *,
    step,
    end,
    numerics,
    resources,
    identity,
    artifact_root,
    comparison=None,
    initial=None,
):
    """Fresh or exact accepted-boundary continuation; one live state across windows."""
    grid = Grid(step, end)
    expected = contract(model, grid, numerics, identity)
    tick, value = 0, np.zeros(model.coordinates.size)
    if initial is not None:
        checked = load_checkpoint(initial["parent_directory"], initial["parent_chunk"], expected)
        if initial != checked:
            raise ValueError("Checkpoint carry was changed")
        tick, value = checked["tick"], np.asarray(checked["increments"], dtype=np.float64)
    start_tick = tick
    if tick >= grid.count:
        raise ValueError("Candidate continuation has no remaining steps")
    output, root = Path(output), Path(artifact_root)
    if output.resolve() != output.absolute() or not output.absolute().is_relative_to(
        root.absolute()
    ):
        raise ValueError("Candidate output must be unlinked and inside its budget root")
    output.mkdir(parents=True, exist_ok=False)
    begun, calls, steps, estimated = perf_counter(), 0, 0, 0
    recorder = None
    last_time, last_input = grid.time(tick), value.copy()
    integration_seconds = curve_seconds = 0.0
    stage_residual, extrema = 0.0, {}

    def guard():
        if perf_counter() - begun > resources["worker_timeout_seconds"]:
            raise ref.BudgetExceeded("Candidate wall budget exceeded")

    def rhs(time, trial):
        nonlocal calls, last_time, last_input, stage_residual
        last_time, last_input = float(time), trial.copy()
        guard()
        stage_residual = max(stage_residual, check_state(model, trial, numerics["accounting_atol"]))
        calls += 1
        result = model.derivative(trial, increments=True)
        if result.shape != trial.shape or not np.isfinite(result).all():
            raise ValueError("Nonfinite or incomplete candidate RHS")
        return result

    try:
        ref.write_json(
            output / "attempt.json",
            {
                "contract": expected,
                "contract_sha256": digest(expected),
                "resources": resources,
                "initial": initial,
                "start_tick": start_tick,
            },
        )
        width, size = resources["window_steps"], model.coordinates.size
        if type(width) is not int or not 1 <= width <= 256:
            raise ValueError("Invalid candidate window width")
        if grid.count > resources["max_steps_per_trajectory"]:
            raise ref.BudgetExceeded("Candidate global step budget exceeded")
        # Comparison batches follow this window, but all three immutable
        # reference samplers AND their grid streams can each retain a width-256
        # dense window. Account for those independently of the candidate width.
        estimated = 8 * (
            (width + 1) * (160 * size + 384 * model.n) + 6 * 257 * (8 * size + 20) + 128 * size
        )
        if estimated > resources["estimated_array_budget_bytes"]:
            raise ref.BudgetExceeded("Candidate working array estimate exceeds budget")
        check_state(model, value, numerics["accounting_atol"])
        paths.save_arrays(
            output / "initial.npz",
            {
                "tick": np.asarray(tick),
                "time": np.asarray(grid.time(tick)),
                "increments": value,
                "anchor": model.anchor,
                "context": model.context,
            },
            root,
            resources["artifact_budget_bytes"],
        )
        if comparison is not None:
            comparison.open(start_tick, grid, guard)
        recorder = Recorder(model, output, resources, root, grid, tick, value, comparison)
        while tick < grid.count:
            guard()
            a, b = grid.time(tick), grid.time(tick + 1)
            phase = perf_counter()
            result, slopes, coefficients = rk4_step(rhs, a, b, value)
            integration_seconds += perf_counter() - phase
            phase = perf_counter()
            ref.merge_extrema(
                extrema,
                ref.check_curve(model, coefficients, accounting_atol=numerics["accounting_atol"]),
            )
            curve_seconds += perf_counter() - phase
            tick, value, steps = tick + 1, result, steps + 1
            recorder.append(tick, value, slopes, coefficients)
        recorder.flush()
        compared = comparison.finish() if comparison is not None else None
        if compared is not None and compared["status"] != "pass":
            raise ValueError("Short candidate reference disagreement; no automatic refinement")
        guard()
        paths.save_arrays(
            output / "final.npz",
            {
                "tick": np.asarray(tick),
                "time": np.asarray(grid.time(tick)),
                "increments": value,
                "anchor": model.anchor,
                "context": model.context,
            },
            root,
            resources["artifact_budget_bytes"],
        )
        guard()
        report = {
            "status": "complete_engineering_candidate_not_long_qualified",
            "revision": REVISION,
            "start": grid.time(start_tick),
            "end": grid.time(tick),
            "start_tick": start_tick,
            "end_tick": tick,
            "step": step,
            "steps": steps,
            "rhs_calls": calls,
            "seconds": perf_counter() - begun,
            "window_steps": width,
            "chunks": recorder.chunks,
            "estimated_working_array_bytes": estimated,
            "maximum_stage_accounting_residual": stage_residual,
            "whole_curve": extrema,
            "timings": {
                "integration_and_stage_checks": integration_seconds,
                "cubic_domain_checks": curve_seconds,
                "window_recording": recorder.recording_seconds,
                "comparison_and_sample_recording": recorder.comparison_seconds,
            },
            "raw_trajectory_array_bytes": recorder.raw_array_bytes,
            "comparison": compared,
            "attempt_sha256": ref.sha(output / "attempt.json"),
            "index_sha256": ref.sha(output / "chunks.jsonl"),
            "initial_sha256": ref.sha(output / "initial.npz"),
            "final_sha256": ref.sha(output / "final.npz"),
            "long_time_step_selected": False,
            "production_changed": False,
        }
        ref.write_json(output / "trajectory.json", report)
        return report
    except Exception as error:
        preservation_error = None
        try:
            if recorder is not None:
                recorder.flush(compare=False)
            paths.save_arrays(
                output / "last-evaluation.npz",
                {
                    "time": np.asarray(last_time),
                    "increments": last_input,
                    "accepted_time": np.asarray(grid.time(tick)),
                    "accepted_tick": np.asarray(tick),
                    "accepted_increments": value,
                    "anchor": model.anchor,
                    "context": model.context,
                },
                root,
                resources["artifact_budget_bytes"],
            )
        except Exception as secondary:
            preservation_error = f"{type(secondary).__name__}: {secondary}"
        ref.write_json(
            output / "failure.json",
            {
                "status": "incomplete" if isinstance(error, ref.BudgetExceeded) else "refused",
                "exception": type(error).__name__,
                "message": str(error),
                "steps": steps,
                "rhs_calls": calls,
                "accepted_tick": tick,
                "accepted_time": grid.time(tick),
                "seconds": perf_counter() - begun,
                "completed_chunks": 0 if recorder is None else recorder.chunks,
                "preservation_error": preservation_error,
                "long_time_step_selected": False,
            },
        )
        raise
    finally:
        if comparison is not None:
            comparison.close()
