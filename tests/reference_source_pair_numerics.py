"""NUM-004 independent integration/ledger/observation machinery, not Cells.

The frozen SPEC-003 NumPy equations are unchanged. Implicit methods evolve
primary increments; the independent RK4 probe evolves absolute concentrations.
All 18 history coordinates are diagnostics and never feed back into the RHS.
"""

import copy
import json
from dataclasses import dataclass
from time import perf_counter

import numpy as np
from numpy.polynomial import Polynomial
from scipy.integrate import solve_ivp

from tests import reference_source_pair as eq

PROTOCOL = eq.ROOT / "configs/reference/source_emt_pair_numerics_v1.json"
PRIMARY, LEAK, PUMP, ION, LOCAL, MIRNA = (
    slice(0, 12),
    slice(12, 18),
    slice(18, 20),
    slice(20, 23),
    slice(23, 29),
    29,
)
SIZE = 30


def protocol():
    return json.loads(PROTOCOL.read_text())


@dataclass
class Model:
    panel: dict
    case: dict

    def __post_init__(self):
        self.panel, self.case = copy.deepcopy(self.panel), copy.deepcopy(self.case)
        self.anchor, self.context = eq.initial_state(self.panel, self.case)
        self.ends = [e["time"] for e in self.case.get("events", [])] + [self.case["end_time"]]
        self.starts = [0.0] + self.ends[:-1]
        self.held = []
        for time in self.starts:
            controls = eq.controls_at(self.panel, self.case, time)
            self.held.append(
                self.case | {"events": [], "controls": {k: v.tolist() for k, v in controls.items()}}
            )
        self.area, self.volume = eq.geometry(self.panel)
        self.incidence = np.zeros(2)
        self.incidence[self.case.get("edge", [0, 1])] = [-1, 1]

    @property
    def end(self):
        return self.ends[-1]

    def slot(self, time):
        return min(np.searchsorted(self.starts, time, side="right") - 1, len(self.held) - 1)

    def initial(self):
        return np.r_[self.anchor.ravel(), np.zeros(18)]

    def derivative(self, value, slot, *, increments=False):
        if np.shape(value) != (SIZE,) or not np.isfinite(value).all():
            raise ValueError("Expected 30 finite primary/history coordinates")
        primary = value[:12].reshape(6, 2)
        if increments:
            primary = primary + self.anchor
        r = eq.evaluate(primary, self.context, self.panel, self.held[slot])
        factor = self.area / self.volume
        return np.r_[
            r["primary_rate"].ravel(),
            r["leak_flux"].ravel() * factor,
            r["pump_cycle_flux"] * factor,
            r["junction_flux"][:3] * factor,
            r["local_rate"][3:].ravel(),
            r["junction_flux"][3] * factor,
        ]


def check_times(times, start, end):
    t = np.asarray(times, dtype=float)
    if t.ndim != 1 or not np.isfinite(t).all() or np.any(np.diff(t) < 0):
        raise ValueError("Times must be finite and sorted")
    if t.size and (t[0] < start or t[-1] > end):
        raise ValueError("Sampling outside accepted time interval")
    return t


def domain(model, values):
    values = np.asarray(values)
    if values.ndim != 2 or values.shape[1] != SIZE or not np.isfinite(values).all():
        raise ValueError("Invalid complete history array")
    y = values[:, :12].reshape(-1, 6, 2)
    voltage = ((y[:, 0] + y[:, 1] - y[:, 2]) - model.context[0]) * (
        model.panel["parameters"]["F"]
        * model.volume
        / (model.area * model.panel["parameters"]["cm"])
    )
    if (
        np.any(y[:, :3] < 1e-6)
        or np.any(y[:, :3] > 1000)
        or np.any(y[:, 3:] < 0)
        or np.any(y[:, 3:] > 1000)
    ):
        raise ValueError("Primary path outside declared concentration domain")
    vmax = max(np.max(abs(voltage)), np.max(abs(voltage[:, 0] - voltage[:, 1])))
    if vmax > 0.2:
        raise ValueError("Primary path outside declared electrical domain")
    return {
        "minimum_ion": float(y[:, :3].min()),
        "minimum_regulation": float(y[:, 3:].min()),
        "maximum_primary": float(y.max()),
        "maximum_absolute_voltage": float(vmax),
    }


def accounting(model, values):
    values = np.asarray(values)
    predicted = np.broadcast_to(model.anchor, (len(values), 6, 2)).copy()
    predicted[:, :3] += values[:, LEAK].reshape(-1, 3, 2)
    predicted[:, :3] += np.array([-3.0, 2.0, 0.0])[None, :, None] * values[:, PUMP, None].transpose(
        0, 2, 1
    )
    predicted[:, :3] += values[:, ION, None] * model.incidence
    predicted[:, 3:] += values[:, LOCAL].reshape(-1, 3, 2)
    predicted[:, 3] += values[:, MIRNA, None] * model.incidence
    error = predicted - values[:, :12].reshape(-1, 6, 2)
    return {
        "ionic": float(np.max(abs(error[:, :3]))),
        "regulatory": float(np.max(abs(error[:, 3:]))),
    }


def bounded_jacobian(model, value, slot, rhs):
    jac = np.zeros((SIZE, SIZE))
    for column in range(12):
        h = 1e-5
        for _ in range(10):
            offset = np.zeros(SIZE)
            offset[column] = h
            try:
                plus = rhs(value + offset)
                minus = rhs(value - offset)
                jac[:, column] = (plus - minus) / (2 * h)
                break
            except ValueError as error:
                if "budget" in str(error):
                    raise
                try:
                    plus = rhs(value + offset)
                    plus2 = rhs(value + 2 * offset)
                    jac[:, column] = (-3 * rhs(value) + 4 * plus - plus2) / (2 * h)
                    break
                except ValueError as forward_error:
                    if "budget" in str(forward_error):
                        raise
                    h *= 0.1
        else:
            raise ValueError("No valid primary Jacobian stencil")
    return jac


@dataclass
class Reference:
    model: Model
    segments: list
    stats: dict

    def sample(self, times):
        times = check_times(times, 0, self.model.end)
        result = np.empty((len(times), SIZE))
        slots = np.minimum(
            np.searchsorted(self.model.ends, times, side="right"), len(self.segments) - 1
        )
        for index, sol in enumerate(self.segments):
            mask = slots == index
            if np.any(mask):
                result[mask] = sol.sol(times[mask]).T
        result[:, :12] += self.model.anchor.ravel()
        domain(self.model, result)
        return result


def integrate_reference(model, *, method="Radau", refinement=1, max_step=None):
    if method not in ("Radau", "BDF") or refinement <= 0 or not np.isfinite(refinement):
        raise ValueError("Unsupported reference settings")
    settings = model.panel["future_numerical_gate"]
    extra = protocol()
    max_step = extra["reference_max_step"] if max_step is None else max_step
    if not np.isfinite(max_step) or max_step <= 0:
        raise ValueError("Invalid reference max step")
    state = np.zeros(SIZE)
    start = perf_counter()
    calls = 0
    segments = []
    for slot, (a, b) in enumerate(zip(model.starts, model.ends, strict=True)):

        def rhs(time, value, active=slot):
            nonlocal calls
            calls += 1
            limits = extra["independent_limits"]
            if (
                calls > limits["rhs_calls_per_case"]
                or perf_counter() - start > limits["seconds_per_case"]
            ):
                raise ValueError("Reference budget exceeded")
            return model.derivative(value, active, increments=True)

        def jac(time, value, active=slot):
            return bounded_jacobian(model, value, active, lambda y: rhs(time, y))

        sol = solve_ivp(
            rhs,
            (a, b),
            state,
            method=method,
            rtol=settings["reference_rtol"] * refinement,
            atol=settings["reference_atol"] * refinement,
            max_step=max_step,
            jac=jac,
            dense_output=True,
        )
        if not sol.success or sol.t[-1] != b:
            raise ValueError(f"Reference integration failed: {sol.message}")
        np.testing.assert_array_equal(sol.y[:, 0], state)
        state = sol.y[:, -1].copy()
        accepted = sol.y.T.copy()
        accepted[:, :12] += model.anchor.ravel()
        domain(model, accepted)
        segments.append(sol)
    return Reference(
        model,
        segments,
        {
            "method": method,
            "refinement": refinement,
            "max_step": max_step,
            "rtol": settings["reference_rtol"] * refinement,
            "atol": settings["reference_atol"] * refinement,
            "calls_including_jacobian": calls,
            "accepted_steps": sum(len(s.t) - 1 for s in segments),
            "seconds": perf_counter() - start,
        },
    )


class ProbeFailure(ValueError):
    def __init__(self, message, times, values, trial):
        super().__init__(message)
        self.times, self.values, self.trial = np.asarray(times), np.asarray(values), trial


def grid(model, dt):
    if (
        not np.isfinite(dt)
        or dt <= 0
        or model.end / dt > protocol()["independent_limits"]["rk_steps_per_case"]
    ):
        raise ValueError("Invalid RK4 step or step budget")
    ticks = np.arange(int(np.ceil(model.end / dt))) * dt
    return np.unique(np.r_[ticks[ticks < model.end], model.starts, model.end])


def integrate_rk4(model, dt, *, start_time=0, initial=None):
    all_times = grid(model, dt)
    if start_time not in all_times:
        raise ValueError("Restart must be an accepted grid boundary")
    times = all_times[all_times >= start_time]
    value = model.initial() if initial is None else np.asarray(initial).copy()
    if start_time != 0 and initial is None:
        raise ValueError("Restart requires complete state")
    history, slopes = [value.copy()], []
    begun = perf_counter()
    limit = protocol()["independent_limits"]["seconds_per_case"]
    for index, (a, b) in enumerate(zip(times[:-1], times[1:], strict=True)):
        slot, h = model.slot(a), b - a
        trial = value
        try:
            if perf_counter() - begun > limit:
                raise ValueError("RK4 budget exceeded")
            k1 = model.derivative(value, slot)
            trial = value + h * k1 / 2
            k2 = model.derivative(trial, slot)
            trial = value + h * k2 / 2
            k3 = model.derivative(trial, slot)
            trial = value + h * k3
            k4 = model.derivative(trial, slot)
            trial = value + h * (k1 + 2 * k2 + 2 * k3 + k4) / 6
            end_slope = model.derivative(trial, slot)
        except ValueError as error:
            raise ProbeFailure(str(error), times[: index + 1], history, trial) from error
        slopes.append((k1, end_slope))
        value = trial
        history.append(value.copy())
    return (
        times,
        np.asarray(history),
        np.asarray(slopes),
        {"dt": dt, "steps": len(times) - 1, "seconds": perf_counter() - begun},
    )


def cubic_coefficients(times, values, slopes):
    h = np.diff(times)[:, None]
    change = values[1:] - values[:-1]
    left, right = slopes[:, 0] * h, slopes[:, 1] * h
    return np.stack(
        (values[:-1], left, 3 * change - 2 * left - right, -2 * change + left + right), axis=1
    )


def sample_cubic(times, values, coefficients, samples):
    samples = check_times(samples, times[0], times[-1])
    indices = np.clip(np.searchsorted(times, samples, side="right") - 1, 0, len(times) - 2)
    theta = (samples - times[indices]) / (times[indices + 1] - times[indices])
    c = coefficients[indices]
    result = ((c[:, 3] * theta[:, None] + c[:, 2]) * theta[:, None] + c[:, 1]) * theta[:, None] + c[
        :, 0
    ]
    endpoint = np.searchsorted(times, samples)
    exact = times[endpoint] == samples
    result[exact] = values[endpoint[exact]]
    return result


def polynomial_bounds(coefficients):
    """Check every real stationary point, not merely requested observations."""
    coeff = np.asarray(coefficients)
    if coeff.ndim != 2 or not np.isfinite(coeff).all():
        raise ValueError("Nonfinite polynomial coefficients")
    bounds = []
    for column in coeff.T:
        polynomial = Polynomial(column)
        roots = polynomial.deriv().roots()
        points = [0.0, 1.0] + [
            float(r.real) for r in roots if abs(r.imag) <= 1e-12 and 0 < r.real < 1
        ]
        values = polynomial(points)
        bounds.append((values.min(), values.max()))
    return np.asarray(bounds).T


def check_polynomial(model, coefficients):
    """Primary and affine voltage extrema; caches/scales are reconstructed."""
    coeff = np.asarray(coefficients).copy()
    primary = coeff[:, :12]
    shaped = primary.reshape(len(coeff), 6, 2)
    volts = shaped[:, 0] + shaped[:, 1] - shaped[:, 2]
    volts[0] -= model.context[0]
    volts *= (
        model.panel["parameters"]["F"]
        * model.volume
        / (model.area * model.panel["parameters"]["cm"])
    )
    low, high = polynomial_bounds(np.c_[primary, volts, volts[:, 0] - volts[:, 1]])
    lower = np.r_[np.full(6, 1e-6), np.zeros(6), [-0.2] * 3]
    upper = np.r_[np.full(12, 1000), [0.2] * 3]
    if np.any(low < lower) or np.any(high > upper):
        raise ValueError("Whole interpolant outside declared primary/voltage domain")
    return float(low[6:12].min())


def native_polynomials(reference):
    """Power coefficients of installed SciPy Radau/BDF dense outputs on [0,1]."""
    for segment in reference.segments:
        for interpolant in segment.sol.interpolants:
            if reference.stats["method"] == "Radau":
                coeff = np.vstack((interpolant.y_old, interpolant.Q.T))
            else:
                h = interpolant.t - interpolant.t_old
                basis = Polynomial([1.0])
                coeff = np.zeros((interpolant.order + 1, SIZE))
                coeff[0] = interpolant.D[0]
                for j in range(interpolant.order):
                    basis *= Polynomial(
                        [
                            (interpolant.t_old - interpolant.t_shift[j]) / interpolant.denom[j],
                            h / interpolant.denom[j],
                        ]
                    )
                    coeff[: len(basis.coef)] += basis.coef[:, None] * interpolant.D[j + 1]
            coeff[0, :12] += reference.model.anchor.ravel()
            yield interpolant.t_old, interpolant.t, coeff


def comparison_grid(model, accepted_times):
    times = np.asarray(accepted_times)
    irregular = np.asarray(model.panel["future_numerical_gate"]["observation_times"])
    return np.unique(
        np.r_[times, (times[:-1] + times[1:]) / 2, irregular[irregular <= model.end], model.starts]
    )


def observations(model, times, values):
    """Bulk readouts at every comparison point; cross-checked against frozen RHS."""
    domain(model, values)
    y = values[:, :12].reshape(-1, 6, 2)
    count = len(y)
    p = model.panel["parameters"]
    vm = (
        (y[:, 0] + y[:, 1] - y[:, 2] - model.context[0])
        * p["F"]
        * model.volume
        / (model.area * p["cm"])
    )
    start, end = model.case.get("edge", [0, 1])
    delta = vm[:, start] - vm[:, end]
    scale = (
        np.broadcast_to(np.ones(4), (count, 4)).copy()
        if model.case["gate"] is None
        else eq.gate_scales(delta, model.panel, model.case).T
    )
    slots = np.minimum(
        np.searchsorted(model.starts, times, side="right") - 1, len(model.starts) - 1
    )
    leak_control = np.asarray([held["controls"]["leak"] for held in model.held])[slots]
    pump_control = np.asarray([held["controls"]["pump"] for held in model.held])[slots]
    diffusion = np.tile(
        model.case.get("membrane_diffusion", model.panel["membrane_diffusion"]), (1, count)
    )
    leak, pump, _ = eq.membrane_flux(
        y.transpose(1, 0, 2).reshape(6, -1),
        vm.ravel(),
        diffusion,
        {"leak": leak_control.transpose(1, 0, 2).reshape(3, -1), "pump": pump_control.ravel()},
        model.panel,
    )
    leak = leak.reshape(3, count, 2).transpose(1, 0, 2)
    pump = pump.reshape(3, count, 2).transpose(1, 0, 2)
    x = delta[:, None] * np.array([1.0, 1.0, -1.0, -1.0]) * p["q"] / (p["kb"] * p["T"])
    donor = np.where(x >= 0, y[:, :4, start], y[:, :4, end])
    d = np.r_[model.panel["junction_ion_diffusion"], model.panel["junction_mirna_diffusion"]]
    junction = d / p["GJ_len"] * (y[:, :4, start] - y[:, :4, end] + x * donor) * scale
    ionic = np.asarray([held["controls"]["ion_contact"] for held in model.held])[slots]
    mirna = np.asarray([held["controls"]["mirna_contact"] for held in model.held])[slots]
    junction *= np.c_[np.repeat(ionic[:, None], 3, axis=1), mirna]
    packet = np.zeros((count, 17, 2))
    packet[:, eq.PRIMARY_INDEX] = y
    packet[:, eq.CONTEXT_INDEX] = model.context
    packet[:, 8] = y[:, 3]
    ratio = y[:, 3] / 40
    packet[:, 9:16] = (
        y[:, 4, None, :]
        * ratio[:, None, :] ** np.arange(7)[None, :, None]
        / (1 + ratio[:, None, :]) ** 6
    )
    return {
        "voltage": vm,
        "gate_scale": scale,
        "membrane_and_junction_flux": np.c_[
            leak.reshape(count, 6), pump.reshape(count, 6), junction
        ],
        "packet": packet,
    }


def scores(model, times, actual, expected, *, targets=None, ledgers=True):
    targets = (
        model.panel["future_numerical_gate"]["candidate_error_targets"]
        if targets is None
        else targets
    )

    def score(a, b, tolerances):
        return float(np.max(abs(a - b) / (tolerances["atol"] + tolerances["rtol"] * abs(b))))

    result = {
        "ionic_concentration": score(
            actual[:, :6], expected[:, :6], targets["ionic_concentration"]
        ),
        "regulatory_coordinate": score(
            actual[:, 6:12], expected[:, 6:12], targets["regulatory_coordinate"]
        ),
    }
    observed_a, observed_b = (observations(model, times, x) for x in (actual, expected))
    for name in ("voltage", "gate_scale", "membrane_and_junction_flux"):
        result[name] = score(observed_a[name], observed_b[name], targets[name])
    if ledgers:
        ledger_targets = protocol()["ledger_error_targets"]
        result["ionic_history"] = score(
            actual[:, 12:23], expected[:, 12:23], ledger_targets["ionic"]
        )
        result["regulatory_history"] = score(
            actual[:, 23:], expected[:, 23:], ledger_targets["regulatory"]
        )
    return result
