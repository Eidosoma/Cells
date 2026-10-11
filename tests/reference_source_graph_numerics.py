"""Bounded, independent fixed-graph implicit reference machinery (NUM-005b).

No Cells/native imports and no phenotype feedback. One live SciPy solver crosses
recording boundaries; disk chunks retain complete increments and dense curves.
Snapshots are physical/ledger state, not a promise of adaptive-solver restart.
"""

import hashlib
import json
from pathlib import Path
from time import perf_counter

import numpy as np
from numpy.polynomial import Polynomial
from scipy.integrate import BDF, Radau

from tests import reference_source_graph as graph
from tests.reference_source_pair_numerics import polynomial_bounds

MAX_DEGREE = 5


class BudgetExceeded(RuntimeError):
    """Incomplete work, never a numerical or biological pass/failure."""


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    with Path(path).open("xb") as handle:
        handle.write(raw)


def read_json(path):
    return json.loads(Path(path).read_text())


def save_arrays(path, arrays, root, limit):
    """Check uncompressed payload estimate before allocating/writing a ZIP batch."""
    used = sum(p.stat().st_size for p in Path(root).rglob("*") if p.is_file())
    estimate = sum(np.asarray(a).nbytes for a in arrays.values()) + 4096 * len(arrays)
    if used + estimate + 65536 > limit:
        raise BudgetExceeded("Artifact budget exceeded before writing batch")
    with Path(path).open("xb") as handle:
        np.savez(handle, **arrays)


def absolute(model, increments):
    values = np.asarray(increments, dtype=float).copy()
    values[..., model.coordinates.primary] += model.anchor.ravel()
    return values


def residual(model, increments):
    """Linear reconstruction in increment coordinates, also valid for coefficients."""
    v = np.asarray(increments)
    s = model.coordinates
    prediction = np.zeros((*v.shape[:-1], 6, model.n))
    prediction[..., :3, :] = v[..., s.leak].reshape(*v.shape[:-1], 3, model.n)
    prediction[..., :3, :] += np.array([-3.0, 2.0, 0.0])[:, None] * v[..., s.pump][..., None, :]
    prediction[..., 3:, :] = v[..., s.local].reshape(*v.shape[:-1], 3, model.n)
    ionic = v[..., s.ionic].reshape(*v.shape[:-1], 3, model.e)
    mirna = v[..., s.mirna]
    for i, (a, b) in enumerate(model.edges):
        prediction[..., :3, a] -= ionic[..., :, i]
        prediction[..., :3, b] += ionic[..., :, i]
        prediction[..., 3, a] -= mirna[..., i]
        prediction[..., 3, b] += mirna[..., i]
    return prediction.reshape(*v.shape[:-1], 6 * model.n) - v[..., s.primary]


def blocked_coordinates(model):
    s = model.coordinates
    leak = np.flatnonzero((model.membrane_diffusion * model.controls["leak"]).ravel() == 0)
    pump = np.flatnonzero(
        (model.controls["pump"] == 0) | np.all(model.membrane_diffusion == 0, axis=0)
    )
    ionic = np.flatnonzero((model.ionic_diffusion * model.controls["ion_contact"]).ravel() == 0)
    mirna = np.flatnonzero(model.mirna_diffusion * model.controls["mirna_contact"] == 0)
    return np.r_[
        s.leak.start + leak, s.pump.start + pump, s.ionic.start + ionic, s.mirna.start + mirna
    ]


def check_curve(model, coefficients, *, accounting_atol=2e-9):
    """All stationary points of primary, affine electrical and residual polynomials.

    Floating-point root checks, not interval-certified enclosures. Coefficients
    are powers of normalized time and primary *increments* about the fixed anchor.
    """
    c = np.asarray(coefficients)
    if c.ndim != 2 or not 1 <= len(c) <= 6 or c.shape[1] != model.coordinates.size:
        raise ValueError("Invalid dense coefficient shape")
    if not np.isfinite(c).all():
        raise ValueError("Nonfinite dense coefficients")
    primary = c[:, model.coordinates.primary].copy()
    primary[0] += model.anchor.ravel()
    p = model.panel["parameters"]
    shaped = primary.reshape(len(c), 6, model.n)
    volts = shaped[:, 0] + shaped[:, 1] - shaped[:, 2]
    volts[0] -= model.context[0]
    volts *= p["F"] * model.volume / (model.area * p["cm"])
    delta = np.array([volts[:, a] - volts[:, b] for a, b in model.edges]).reshape(model.e, len(c)).T
    low, high = polynomial_bounds(np.c_[primary, volts, delta])
    lower = np.r_[
        np.full(3 * model.n, 1e-6), np.zeros(3 * model.n), np.full(model.n + model.e, -0.2)
    ]
    upper = np.r_[np.full(6 * model.n, 1000.0), np.full(model.n + model.e, 0.2)]
    if np.any(low < lower) or np.any(high > upper):
        raise ValueError("Whole dense curve outside primary/electrical domain")
    electrical = np.maximum(abs(low[6 * model.n :]), abs(high[6 * model.n :]))
    exponent = max(
        electrical[: model.n].max() * p["F"] / (p["R"] * p["T"]),
        electrical[model.n :].max(initial=0) * p["q"] / (p["kb"] * p["T"]),
    )
    if exponent > 50:
        raise ValueError("Whole dense curve outside electrical exponent domain")
    error = float(np.max(abs(polynomial_bounds(residual(model, c)))))
    if error > accounting_atol:
        raise ValueError("Whole dense curve accounting failed")
    if np.any(c[:, blocked_coordinates(model)] != 0):
        raise ValueError("Blocked history is not exactly zero")
    return {
        "minimum_ion": float(low[: 3 * model.n].min()),
        "minimum_regulation": float(low[3 * model.n : 6 * model.n].min()),
        "maximum_primary": float(high[: 6 * model.n].max()),
        "maximum_absolute_voltage": float(electrical.max()),
        "maximum_electrical_exponent": float(exponent),
        "maximum_accounting_residual": error,
    }


def merge_extrema(total, item):
    for key, value in item.items():
        operation = min if key.startswith("minimum") else max
        total[key] = operation(total.get(key, value), value)


def jacobian(model, value, rhs, *, step=1e-5):
    """Bounded central/one-sided second-order stencil; passive columns are zero."""
    matrix = np.zeros((model.coordinates.size, model.coordinates.size))
    for column in range(6 * model.n):
        h = step
        for _ in range(10):
            offset = np.zeros_like(value)
            offset[column] = h
            try:
                matrix[:, column] = (rhs(value + offset) - rhs(value - offset)) / (2 * h)
                break
            except ValueError:
                for direction in (1, -1):
                    try:
                        one, two = (
                            rhs(value + direction * offset),
                            rhs(value + 2 * direction * offset),
                        )
                        matrix[:, column] = direction * (-3 * rhs(value) + 4 * one - two) / (2 * h)
                        break
                    except ValueError:
                        continue
                else:
                    h *= 0.1
                    continue
                break
        else:
            raise ValueError("No valid Jacobian stencil")
    return matrix


def check_jacobian(model, value, rhs=None):
    """Separate five-point derivative check, at a different stencil scale."""
    if rhs is None:
        rhs = lambda y: model.derivative(y, increments=True)  # noqa: E731
    actual = jacobian(model, value, rhs)
    expected = np.zeros_like(actual)
    schemes = []
    for column in range(6 * model.n):
        h = 1e-4
        for _ in range(10):
            offset = np.zeros_like(value)
            offset[column] = h
            try:
                expected[:, column] = (
                    rhs(value - 2 * offset)
                    - 8 * rhs(value - offset)
                    + 8 * rhs(value + offset)
                    - rhs(value + 2 * offset)
                ) / (12 * h)
                schemes.append("central_five_point")
                break
            except ValueError:
                for direction in (1, -1):
                    try:
                        samples = [rhs(value + direction * k * offset) for k in range(5)]
                        expected[:, column] = (
                            direction
                            * (
                                -25 * samples[0]
                                + 48 * samples[1]
                                - 36 * samples[2]
                                + 16 * samples[3]
                                - 3 * samples[4]
                            )
                            / (12 * h)
                        )
                        schemes.append(f"one_sided_five_point/{direction}")
                        break
                    except ValueError:
                        continue
                else:
                    h *= 0.1
                    continue
                break
        else:
            raise ValueError("No valid independent Jacobian check stencil")
    score = float(np.max(abs(actual - expected) / (2e-6 + 2e-5 * abs(expected))))
    if not np.isfinite(score) or score > 1:
        raise ValueError(f"Independent Jacobian check failed: {score}")
    # Histories cannot influence any row, including other histories.
    altered = value.copy()
    altered[6 * model.n :] += np.arange(len(altered) - 6 * model.n) + 1.25
    np.testing.assert_array_equal(rhs(altered), rhs(value))
    return {
        "maximum_score": score,
        "primary_column_schemes": schemes,
        "passive_columns_exact": True,
    }


def dense_coefficients(interpolant, method):
    """Read the installed, pinned SciPy polynomial; no sampled polynomial fit."""
    if method == "Radau":
        return np.vstack((interpolant.y_old, interpolant.Q.T))
    if method != "BDF" or not 1 <= interpolant.order <= MAX_DEGREE:
        raise ValueError("Unsupported dense interpolant")
    coeff = np.zeros((interpolant.order + 1, len(interpolant.D[0])))
    coeff[0] = interpolant.D[0]
    basis = Polynomial([1.0])
    for j in range(interpolant.order):
        basis *= Polynomial(
            [
                (interpolant.t_old - interpolant.t_shift[j]) / interpolant.denom[j],
                (interpolant.t - interpolant.t_old) / interpolant.denom[j],
            ]
        )
        coeff[: len(basis.coef)] += basis.coef[:, None] * interpolant.D[j + 1]
    return coeff


def evaluate_polynomial(coefficients, theta):
    return np.polynomial.polynomial.polyval(np.asarray(theta), coefficients).T


def integrate(model, output, *, method, refinement, duration, numerics, resources, artifact_root):
    """One complete attempt; a receipt exists only after the exact final clock."""
    if method not in ("Radau", "BDF") or refinement not in (1.0, 0.1):
        raise ValueError("Unregistered implicit method/refinement")
    if not np.isfinite(duration) or duration <= 0:
        raise ValueError("Invalid reference duration")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    size, width = model.coordinates.size, resources["window_steps"]
    if type(width) is not int or not 1 <= width <= 256:
        raise ValueError("Invalid bounded reference width")
    estimated = 8 * (32 * (width + 1) * size + 16 * size * size)
    if estimated > resources["estimated_array_budget_bytes"]:
        raise BudgetExceeded("Reference working array estimate exceeds budget")
    write_json(output / "case.json", model.case)
    begun, calls, steps, chunks = perf_counter(), 0, 0, 0
    times = np.empty(width + 1)
    values = np.empty((width + 1, size))
    coeffs = np.zeros((width, MAX_DEGREE + 1, size))
    degrees = np.zeros(width, dtype=np.int64)
    times[0], values[0] = 0.0, np.zeros(size)
    buffered = 0
    extrema, jac_checks = {}, []
    dense_error = 0.0
    last_input, last_time = values[0].copy(), 0.0
    solver = None

    def guard():
        if perf_counter() - begun > resources["worker_timeout_seconds"]:
            raise BudgetExceeded("Reference wall budget exceeded")
        if calls > resources["rhs_calls_per_reference_trajectory"]:
            raise BudgetExceeded("Reference RHS-call budget exceeded")

    def rhs(time, value):
        nonlocal calls, last_input, last_time
        calls += 1
        last_input, last_time = value.copy(), float(time)
        guard()
        return model.derivative(value, increments=True)

    def jac(time, value):
        return jacobian(model, value, lambda y: rhs(time, y))

    def flush():
        nonlocal chunks, buffered
        if not buffered:
            return
        name = f"chunk-{chunks:06d}.npz"
        arrays = {
            "times": times[: buffered + 1],
            "increments": values[: buffered + 1],
            "coefficients": coeffs[:buffered],
            "degrees": degrees[:buffered],
            "anchor": model.anchor,
            "context": model.context,
        }
        save_arrays(output / name, arrays, artifact_root, resources["artifact_budget_bytes"])
        entry = {
            "path": name,
            "sha256": sha(output / name),
            "steps": buffered,
            "start": float(times[0]),
            "end": float(times[buffered]),
        }
        with (output / "chunks.jsonl").open("a") as handle:
            handle.write(json.dumps(entry, sort_keys=True, allow_nan=False) + "\n")
        print(
            f"{model.case['id']} {method}/{refinement:g}: t={times[buffered]:.6g}, steps={steps}",
            flush=True,
        )
        times[0], values[0] = times[buffered], values[buffered]
        coeffs.fill(0)
        chunks += 1
        buffered = 0

    try:
        jac_checks.append(check_jacobian(model, values[0], lambda y: rhs(0.0, y)))
        solver_type = Radau if method == "Radau" else BDF
        solver = solver_type(
            rhs,
            0.0,
            values[0].copy(),
            duration,
            rtol=numerics["rtol"] * refinement,
            atol=numerics["atol"] * refinement,
            max_step=numerics["reference_max_step"],
            jac=jac,
        )
        while solver.status == "running":
            guard()
            if steps >= resources["max_steps_per_trajectory"]:
                raise BudgetExceeded("Reference accepted-step budget exceeded")
            message = solver.step()
            if solver.status == "failed":
                raise ValueError(f"Implicit solver refused step: {message}")
            interpolant = solver.dense_output()
            c = dense_coefficients(interpolant, method)
            # Independent evaluator versus SciPy at endpoints and irregular interior points.
            theta = np.array([0.0, 0.113, 0.37, 0.5, 0.613, 0.91, 1.0])
            query = interpolant.t_old + theta * (interpolant.t - interpolant.t_old)
            # Recover the same floating-point theta as SciPy at actual global clocks.
            actual_theta = (query - interpolant.t_old) / (interpolant.t - interpolant.t_old)
            reconstructed, native = evaluate_polynomial(c, actual_theta), interpolant(query).T
            score = float(np.max(abs(reconstructed - native) / (2e-11 + 2e-12 * abs(native))))
            if score > 1 or not np.isfinite(score):
                raise ValueError("Dense coefficient adapter differs from installed SciPy")
            dense_error = max(dense_error, score)
            np.testing.assert_allclose(reconstructed[0], values[buffered], atol=2e-11, rtol=2e-12)
            np.testing.assert_allclose(reconstructed[-1], solver.y, atol=2e-11, rtol=2e-12)
            checked = check_curve(model, c, accounting_atol=numerics["accounting_atol"])
            merge_extrema(extrema, checked)
            # Accepted states are checked separately from polynomial endpoint roundoff.
            check_curve(model, solver.y[None, :], accounting_atol=numerics["accounting_atol"])
            coeffs[buffered, : len(c)] = c
            degrees[buffered] = len(c) - 1
            buffered += 1
            times[buffered], values[buffered] = solver.t, solver.y
            steps += 1
            if buffered == width:
                flush()
        if solver.t != duration or solver.status != "finished":
            raise ValueError("Reference did not reach exact requested clock")
        jac_checks.append(check_jacobian(model, solver.y, lambda y: rhs(solver.t, y)))
        flush()
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
            "chunks": chunks,
            "estimated_working_array_bytes": estimated,
            "dense_adapter_maximum_score": dense_error,
            "whole_curve": extrema,
            "jacobian_checks": jac_checks,
            "snapshot_semantics": "complete_state_not_adaptive_restart",
            "case_sha256": sha(output / "case.json"),
            "index_sha256": sha(output / "chunks.jsonl"),
        }
        write_json(output / "trajectory.json", report)
        return report
    except Exception as error:
        # Preserve the last completed snapshot plus failing evaluation when budget permits.
        try:
            flush()
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
        except BudgetExceeded:
            pass
        write_json(
            output / "failure.json",
            {
                "status": "incomplete" if isinstance(error, BudgetExceeded) else "refused",
                "exception": type(error).__name__,
                "message": str(error),
                "steps": steps,
                "calls": calls,
                "seconds": perf_counter() - begun,
                "last_solver_time": None if solver is None else float(solver.t),
                "completed_chunks": chunks,
            },
        )
        raise


def validate_chunk_index(directory, report):
    """Validate the entire small metadata stream even for endpoint-only sampling."""
    count, steps, clock = 0, 0, 0.0
    with (directory / "chunks.jsonl").open() as handle:
        for line in handle:
            item = json.loads(line)
            if (
                item["path"] != f"chunk-{count:06d}.npz"
                or type(item["steps"]) is not int
                or not 1 <= item["steps"] <= report["window_steps"]
                or item["start"] != clock
                or not np.isfinite(item["end"])
                or not item["end"] > clock
            ):
                raise ValueError("Invalid reference index inventory/clock")
            count, steps, clock = count + 1, steps + item["steps"], item["end"]
    if (
        count != report["chunks"]
        or steps != report["accepted_steps"]
        or clock != report["end"]
        or report["start"] != 0
    ):
        raise ValueError("Incomplete reference index inventory")


class Trajectory:
    """Hash-checked, monotonically sampled disk trajectory; at most one cached chunk."""

    def __init__(self, directory):
        self.directory = Path(directory)
        self.report = read_json(self.directory / "trajectory.json")
        if self.report["status"] != "complete_not_yet_cross_qualified":
            raise ValueError("Incomplete reference trajectory")
        for name, key in (("case.json", "case_sha256"), ("chunks.jsonl", "index_sha256")):
            if sha(self.directory / name) != self.report[key]:
                raise ValueError("Reference index/case hash mismatch")
        validate_chunk_index(self.directory, self.report)
        self.model = graph.Model(read_json(self.directory / "case.json"))
        self._iterator, self._current, self._last_query = self.chunks(), None, -np.inf

    def chunks(self):
        previous, clock, count, steps = np.zeros(self.model.coordinates.size), 0.0, 0, 0
        with (self.directory / "chunks.jsonl").open() as index:
            for line in index:
                entry = json.loads(line)
                if entry["path"] != f"chunk-{count:06d}.npz":
                    raise ValueError("Chunk inventory/order mismatch")
                path = self.directory / entry["path"]
                if sha(path) != entry["sha256"]:
                    raise ValueError("Reference chunk hash mismatch")
                with np.load(path, allow_pickle=False) as data:
                    item = {name: data[name] for name in data.files}
                t, v, c, d = (item[k] for k in ("times", "increments", "coefficients", "degrees"))
                width, size = entry["steps"], self.model.coordinates.size
                if (
                    not 1 <= width <= self.report["window_steps"]
                    or t.shape != (width + 1,)
                    or v.shape != (width + 1, size)
                    or c.shape != (width, 6, size)
                    or d.shape != (width,)
                    or d.dtype.kind not in "iu"
                    or np.any(d < 1)
                    or np.any(d > 5)
                    or not all(np.isfinite(x).all() for x in (t, v, c))
                    or t[0] != clock
                    or t[0] != entry["start"]
                    or t[-1] != entry["end"]
                    or np.any(np.diff(t) <= 0)
                ):
                    raise ValueError("Invalid reference chunk shape/clock")
                np.testing.assert_array_equal(item["anchor"], self.model.anchor)
                np.testing.assert_array_equal(item["context"], self.model.context)
                np.testing.assert_array_equal(v[0], previous)
                for i, degree in enumerate(d):
                    if np.any(c[i, degree + 1 :] != 0):
                        raise ValueError("Nonzero polynomial padding")
                previous, clock = v[-1].copy(), float(t[-1])
                count, steps = count + 1, steps + width
                yield item
        if (
            clock != self.report["end"]
            or count != self.report["chunks"]
            or steps != self.report["accepted_steps"]
        ):
            raise ValueError("Incomplete reference chunk inventory")

    def grid(self):
        yield 0.0
        for item in self.chunks():
            for a, b in zip(item["times"][:-1], item["times"][1:], strict=True):
                yield float(a + (b - a) / 2)
                yield float(b)

    def sample(self, times):
        times = np.asarray(times)
        if (
            times.ndim != 1
            or not np.isfinite(times).all()
            or np.any(np.diff(times) < 0)
            or (
                len(times)
                and (times[0] < max(0, self._last_query) or times[-1] > self.report["end"])
            )
        ):
            raise ValueError("Reference samples must be sorted, monotone and in range")
        result = np.empty((len(times), self.model.coordinates.size))
        for j, time in enumerate(times):
            while self._current is None or time > self._current["times"][-1]:
                self._current = next(self._iterator)
            t, v, c = (self._current[k] for k in ("times", "increments", "coefficients"))
            right = np.searchsorted(t, time)
            if t[right] == time:
                result[j] = v[right]
            else:
                i = right - 1
                theta = (time - t[i]) / (t[i + 1] - t[i])
                result[j] = evaluate_polynomial(c[i], theta)
            self._last_query = float(time)
        return result
