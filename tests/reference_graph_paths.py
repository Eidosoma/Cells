"""Losslessly recorded, bounded implicit paths (NUM-005c1).

The NUM-005b numerical implementation is an immutable evidence dependency. This
new orchestration reuses its equations, stencils and dense checks unchanged;
the recording policy is explicit, not a monkeypatch of a frozen module.
"""

import json
from pathlib import Path
from time import perf_counter

import numpy as np
from scipy.integrate import BDF, Radau

from tests import reference_source_graph_numerics as ref

TAIL_RESERVE = 4 * 1024**2


def save_arrays(path, arrays, root, limit):
    """Exclusive, lossless ZIP; conservatively budget the uncompressed batch.

    Reserve room for indexes and final/failure receipts. Compression is a storage
    policy only: no quantization, changed dtype, omitted coefficients or samples.
    """
    path, root = Path(path), Path(root)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Artifact must be inside its budget root")
    arrays = {name: np.asarray(value) for name, value in arrays.items()}
    if any(a.dtype.hasobject for a in arrays.values()):
        raise ValueError("Object arrays are not reference evidence")
    used = sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
    estimate = sum(a.nbytes for a in arrays.values()) + 4096 * len(arrays)
    if used + estimate + TAIL_RESERVE > limit:
        raise ref.BudgetExceeded("Artifact budget exceeded before writing compressed batch")
    with path.open("xb") as handle:
        np.savez_compressed(handle, **arrays)


class Recorder:
    """One bounded window, with bit-exact accepted-state carries across windows."""

    def __init__(self, model, output, resources, artifact_root):
        self.model, self.output = model, output
        self.resources, self.root = resources, artifact_root
        self.width = resources["window_steps"]
        size = model.coordinates.size
        self.times = np.empty(self.width + 1)
        self.values = np.empty((self.width + 1, size))
        self.coefficients = np.zeros((self.width, 6, size))
        self.degrees = np.zeros(self.width, dtype=np.int64)
        self.times[0], self.values[0] = 0.0, np.zeros(size)
        self.buffered = self.chunks = self.steps = 0

    @property
    def last(self):
        return self.values[self.buffered]

    def append(self, time, value, coefficients):
        i = self.buffered
        self.coefficients[i, : len(coefficients)] = coefficients
        self.degrees[i] = len(coefficients) - 1
        self.buffered += 1
        self.steps += 1
        self.times[self.buffered], self.values[self.buffered] = time, value
        if self.buffered == self.width:
            self.flush()

    def flush(self):
        if not self.buffered:
            return
        size = self.buffered
        path = self.output / f"chunk-{self.chunks:06d}.npz"
        save_arrays(
            path,
            {
                "times": self.times[: size + 1],
                "increments": self.values[: size + 1],
                "coefficients": self.coefficients[:size],
                "degrees": self.degrees[:size],
                "anchor": self.model.anchor,
                "context": self.model.context,
            },
            self.root,
            self.resources["artifact_budget_bytes"],
        )
        entry = {
            "path": path.name,
            "sha256": ref.sha(path),
            "steps": size,
            "start": float(self.times[0]),
            "end": float(self.times[size]),
        }
        with (self.output / "chunks.jsonl").open("a") as handle:
            handle.write(json.dumps(entry, sort_keys=True, allow_nan=False) + "\n")
        print(f"t={self.times[size]:.9g}, accepted_steps={self.steps}", flush=True)
        self.times[0], self.values[0] = self.times[size], self.values[size]
        self.coefficients.fill(0)
        self.buffered = 0
        self.chunks += 1


def integrate(model, output, *, method, refinement, duration, numerics, resources, artifact_root):
    """A fresh implicit attempt, never an adaptive resume from a saved snapshot."""
    if method not in ("Radau", "BDF") or refinement not in (1.0, 0.1):
        raise ValueError("Unregistered implicit method/refinement")
    if not np.isfinite(duration) or duration <= 0:
        raise ValueError("Invalid reference duration")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    begun, calls, steps = perf_counter(), 0, 0
    solver = recorder = None
    last_input, last_time = np.zeros(model.coordinates.size), 0.0
    extrema, jac_checks, dense_error = {}, [], 0.0

    def guard():
        if perf_counter() - begun > resources["worker_timeout_seconds"]:
            raise ref.BudgetExceeded("Reference wall budget exceeded")
        if calls > resources["rhs_calls_per_reference_trajectory"]:
            raise ref.BudgetExceeded("Reference RHS-call budget exceeded")

    def rhs(time, value):
        nonlocal calls, last_input, last_time
        calls += 1
        last_input, last_time = value.copy(), float(time)
        guard()
        return model.derivative(value, increments=True)

    def jac(time, value):
        return ref.jacobian(model, value, lambda y: rhs(time, y))

    try:
        ref.write_json(output / "case.json", model.case)
        width, size = resources["window_steps"], model.coordinates.size
        if type(width) is not int or not 1 <= width <= 256:
            raise ValueError("Invalid bounded reference width")
        estimated = 8 * (32 * (width + 1) * size + 16 * size * size)
        if estimated > resources["estimated_array_budget_bytes"]:
            raise ref.BudgetExceeded("Reference working array estimate exceeds budget")
        recorder = Recorder(model, output, resources, artifact_root)
        jac_checks.append(ref.check_jacobian(model, recorder.last, lambda y: rhs(0.0, y)))
        solver_type = Radau if method == "Radau" else BDF
        solver = solver_type(
            rhs,
            0.0,
            recorder.last.copy(),
            duration,
            rtol=numerics["rtol"] * refinement,
            atol=numerics["atol"] * refinement,
            max_step=numerics["reference_max_step"],
            jac=jac,
        )
        while solver.status == "running":
            guard()
            if steps >= resources["max_steps_per_trajectory"]:
                raise ref.BudgetExceeded("Reference accepted-step budget exceeded")
            message = solver.step()
            if solver.status == "failed":
                raise ValueError(f"Implicit solver refused step: {message}")
            interpolant = solver.dense_output()
            c = ref.dense_coefficients(interpolant, method)
            theta = np.array([0.0, 0.113, 0.37, 0.5, 0.613, 0.91, 1.0])
            query = interpolant.t_old + theta * (interpolant.t - interpolant.t_old)
            actual_theta = (query - interpolant.t_old) / (interpolant.t - interpolant.t_old)
            reconstructed = ref.evaluate_polynomial(c, actual_theta)
            native = interpolant(query).T
            score = float(np.max(abs(reconstructed - native) / (2e-11 + 2e-12 * abs(native))))
            if not np.isfinite(score) or score > 1:
                raise ValueError("Dense coefficient adapter differs from installed SciPy")
            dense_error = max(dense_error, score)
            np.testing.assert_allclose(reconstructed[0], recorder.last, atol=2e-11, rtol=2e-12)
            np.testing.assert_allclose(reconstructed[-1], solver.y, atol=2e-11, rtol=2e-12)
            ref.merge_extrema(
                extrema, ref.check_curve(model, c, accounting_atol=numerics["accounting_atol"])
            )
            ref.check_curve(model, solver.y[None, :], accounting_atol=numerics["accounting_atol"])
            steps += 1
            recorder.append(solver.t, solver.y, c)
        if solver.t != duration or solver.status != "finished":
            raise ValueError("Reference did not reach exact requested clock")
        jac_checks.append(ref.check_jacobian(model, solver.y, lambda y: rhs(solver.t, y)))
        recorder.flush()
        guard()
        report = {
            "status": "complete_not_yet_cross_qualified",
            "method": method,
            "refinement": refinement,
            "start": 0.0,
            "end": float(solver.t),
            "rtol": numerics["rtol"] * refinement,
            "atol": numerics["atol"] * refinement,
            "max_step": numerics["reference_max_step"],
            "accepted_steps": steps,
            "rhs_calls_including_solver_jacobian": calls,
            "nfev": solver.nfev,
            "njev": solver.njev,
            "nlu": solver.nlu,
            "seconds": perf_counter() - begun,
            "window_steps": width,
            "chunks": recorder.chunks,
            "estimated_working_array_bytes": estimated,
            "dense_adapter_maximum_score": dense_error,
            "whole_curve": extrema,
            "jacobian_checks": jac_checks,
            "snapshot_semantics": "complete_state_not_adaptive_restart",
            "storage": "lossless_numpy_savez_compressed_no_dtype_change",
            "case_sha256": ref.sha(output / "case.json"),
            "index_sha256": ref.sha(output / "chunks.jsonl"),
        }
        ref.write_json(output / "trajectory.json", report)
        return report
    except Exception as error:
        preservation_error = None
        try:
            if recorder is not None:
                recorder.flush()
            save_arrays(
                output / "last-evaluation.npz",
                {
                    "time": np.asarray(last_time),
                    "increments": last_input,
                    "anchor": model.anchor,
                    "context": model.context,
                },
                artifact_root,
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
                "calls": calls,
                "seconds": perf_counter() - begun,
                "last_solver_time": None if solver is None else float(solver.t),
                "completed_chunks": 0 if recorder is None else recorder.chunks,
                "preservation_error": preservation_error,
            },
        )
        raise
