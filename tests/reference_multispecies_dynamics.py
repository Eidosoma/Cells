"""Bounded NUM-006 CPU method experiment, independent of production Cells/JAX.

Implicit solves use an independent hyperbolic RHS in amount increments. The RK4
probe uses SPEC-005's Bernoulli evaluator in absolute amounts. Dense coefficients
are retained in a data-only representation, not pickled solver objects.
"""

import hashlib
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from time import monotonic

import numpy as np
from scipy.integrate import solve_ivp

from tests import reference_multispecies as spec

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "configs/reference/multispecies_trajectories_v1.json"
PANEL_SHA256 = "24895a45a27067626e370543513a59d27e21f2afec7d3f09b5d4ceef2dddc84a"
F = 6.02214076e23 * 1.602176634e-19
R = 6.02214076e23 * 1.380649e-23
QF = F * 1e-15
MAX_STEPS = 100000
MAX_CALLS = 100000
MAX_SAMPLES = 100000


class ResourceLimit(ValueError):
    """Bounded work is exhausted; no automatic continuation."""


@dataclass(frozen=True)
class Control:
    time_s: float
    leak: tuple[float, ...]
    pump: float

    def __post_init__(self):
        spec.number(self.time_s, "control time", nonnegative=True)
        spec.number(self.pump, "pump control", nonnegative=True)
        if not isinstance(self.leak, tuple) or not self.leak:
            raise ValueError("Leak controls must be a nonempty immutable tuple")
        for value in self.leak:
            spec.number(value, "leak control", nonnegative=True)
        if self.pump > 1 or any(v > 1 for v in self.leak):
            raise ValueError("Control multipliers must be in [0, 1]")


@dataclass(frozen=True)
class Case:
    id: str
    parameters: spec.Resolved
    horizon_s: float
    controls: tuple[Control, ...]

    def __post_init__(self):
        spec.identifier(self.id)
        spec.number(self.horizon_s, "horizon", positive=True)
        if self.horizon_s > 10:
            raise ValueError("Reference horizons are bounded by 10 seconds")
        if not isinstance(self.controls, tuple) or not self.controls:
            raise ValueError("Controls must be a nonempty immutable tuple")
        times = [c.time_s for c in self.controls]
        if times[0] != 0 or any(b <= a for a, b in zip(times[:-1], times[1:], strict=True)):
            raise ValueError("Controls must start at zero and be strictly increasing")
        if times[-1] > self.horizon_s:
            raise ValueError("Control lies beyond the horizon")
        if any(len(c.leak) != self.species_count for c in self.controls):
            raise ValueError("Controls must bind every declared species")

    @property
    def species_count(self):
        return len(self.parameters.species_ids)

    @property
    def size(self):
        return 2 * self.species_count + 2

    def control_at(self, time):
        spec.number(time, "query time", nonnegative=True)
        if time > self.horizon_s:
            raise ValueError("Control query outside horizon")
        slot = np.searchsorted([c.time_s for c in self.controls], time, side="right") - 1
        return self.controls[slot]

    def definition(self):
        return asdict(self)


def load_panel():
    if hashlib.sha256(PANEL.read_bytes()).hexdigest() != PANEL_SHA256:
        raise ValueError("Frozen numerical panel identity changed")
    plan = spec.load_json(PANEL)
    physical_path = ROOT / plan["physical_panel"]
    if hashlib.sha256(physical_path.read_bytes()).hexdigest() != plan["physical_panel_sha256"]:
        raise ValueError("Frozen physical panel identity changed")
    definitions = {c["id"]: c["assembly"] for c in spec.load_json(physical_path)["cases"]}
    cases = []
    for item in plan["cases"]:
        p = spec.resolve(definitions[item["assembly"]])
        profile = plan["profiles"][item["profile"]]
        controls = []
        for control in profile["controls"]:
            blocked = control["blocked_species"]
            if len(set(blocked)) != len(blocked) or not set(blocked) <= set(p.species_ids):
                raise ValueError("Blocked species must be unique existing IDs")
            controls.append(
                Control(
                    control["time_s"],
                    tuple(0.0 if s in blocked else control["leak"] for s in p.species_ids),
                    control["pump"],
                )
            )
        cases.append(Case(item["id"], p, profile["horizon_s"], tuple(controls)))
    if len(cases) != 14 or len({c.id for c in cases}) != len(cases):
        raise ValueError("The frozen panel requires fourteen unique cases")
    return plan, tuple(cases)


def state_array(case, state):
    result = np.asarray(state, dtype=np.float64)
    if result.shape != (case.size,) or not np.isfinite(result).all():
        raise ValueError("Trial state has invalid shape or nonfinite coordinates")
    return result


def initial_state(case, *, absolute=False):
    result = np.zeros(case.size)
    if absolute:
        result[: case.species_count] = case.parameters.initial_amount_fmol
    return result


def canonical(case, state, *, absolute):
    values = np.asarray(state, dtype=float).copy()
    if absolute:
        values[..., : case.species_count] -= case.parameters.initial_amount_fmol
    return values


def domain(case, state, *, absolute=False):
    values = state_array(case, state)
    p, count = case.parameters, case.species_count
    delta = values[:count] - p.initial_amount_fmol if absolute else values[:count]
    amount = values[:count] if absolute else np.asarray(p.initial_amount_fmol) + delta
    if not np.isfinite(amount).all() or np.any(amount <= 0):
        raise ValueError("Every trial amount must remain finite and positive")
    voltage = p.initial_voltage_V + QF / p.capacitance_F * math.fsum(np.asarray(p.valence) * delta)
    xs = np.asarray(p.valence) * F * voltage / (R * p.temperature_K)
    if not np.isfinite(xs).all() or np.max(np.abs(xs)) > 50:
        raise ValueError("Trial voltage exceeds the per-species dimensionless domain")
    return amount, voltage, xs


def hyperbolic_rhs(case, control, state):
    """Independent equation formulation, never calls SPEC-005's flux/pump evaluator."""
    p, count = case.parameters, case.species_count
    n, voltage, x = domain(case, state)
    ci, co = n / p.volume_pL, np.asarray(p.bath_mM)
    h = np.ones(count)
    nonzero = x != 0
    h[nonzero] = x[nonzero] / (2 * np.tanh(x[nonzero] / 2))
    leak = (
        p.area_m2
        * np.asarray(p.permeability_m_per_s)
        * control.leak
        / 1e-15
        * ((co - ci) * h - (co + ci) * x / 2)
    )
    mu = R * p.temperature_K * np.log(ci / co) + np.asarray(p.valence) * F * voltage
    nu = np.zeros(count)
    cycles, energy = 0.0, 0.0
    if p.pump_id is not None:
        sodium, potassium = (p.species_ids.index(s) for s in p.pump_roles)
        nu[sodium], nu[potassium] = -3.0, 2.0
        energy = p.drive_J_per_mol - 3 * mu[sodium] + 2 * mu[potassium]
        cycles = p.capacity_fmol_per_s * control.pump * np.tanh(-energy / (2 * R * p.temperature_K))
    dissipated = -1e-3 * (math.fsum(leak * mu) + cycles * energy)
    result = np.r_[leak + nu * cycles, leak, cycles, dissipated]
    if not np.isfinite(result).all():
        raise ValueError("Nonfinite independent derivative")
    return result


def bernoulli_rhs(case, control, absolute_state):
    state = state_array(case, absolute_state)
    domain(case, state, absolute=True)
    result = spec.evaluate(
        case.parameters,
        tuple(float(n) for n in state[: case.species_count]),
        leak_control=control.leak,
        pump_control=control.pump,
    )
    return np.r_[
        result.amount_rate_fmol_per_s,
        result.passive_fmol_per_s,
        result.pump_cycles_fmol_per_s,
        1e12 * (math.fsum(result.passive_dissipation_W) + result.pump_dissipation_W),
    ]


class Budget:
    def __init__(self, *, deadline=None, max_calls=MAX_CALLS):
        if type(max_calls) is not int or not 0 < max_calls <= MAX_CALLS:
            raise ValueError("Invalid bounded RHS allowance")
        self.deadline = deadline
        self.max_calls = max_calls
        self.calls = 0
        self.minimum_amount = math.inf
        self.max_abs_x = 0.0

    def check(self):
        if self.deadline is not None and monotonic() >= self.deadline:
            raise ResourceLimit("Scientific session wall-time budget exhausted")

    def rhs(self, function, case, control, state, *, absolute=False):
        self.check()
        self.calls += 1
        if self.calls > self.max_calls:
            raise ResourceLimit("Attempt RHS budget exhausted, including Jacobian probes")
        amount, _, x = domain(case, state, absolute=absolute)
        self.minimum_amount = min(self.minimum_amount, float(np.min(amount)))
        self.max_abs_x = max(self.max_abs_x, float(np.max(np.abs(x))))
        return function(case, control, state)


def sample_record(case, arrays, kind, samples):
    """Replay only recorded dense data; exact stored native states at native times."""
    sample = np.asarray(samples, dtype=float)
    if sample.ndim != 1 or not np.isfinite(sample).all() or np.any(np.diff(sample) < 0):
        raise ValueError("Samples must be finite and nondecreasing")
    if len(sample) > MAX_SAMPLES:
        raise ResourceLimit("Comparison sample budget exhausted")
    times = arrays["native_times_s"]
    if len(sample) and (sample[0] < times[0] or sample[-1] > times[-1]):
        raise ValueError("Sample outside the recorded trajectory")
    slots = np.clip(np.searchsorted(times, sample, side="right") - 1, 0, len(times) - 2)
    result = np.empty((len(sample), case.size))
    for slot in np.unique(slots):
        selected = np.flatnonzero(slots == slot)
        t = sample[selected]
        degree = int(arrays["degree"][slot])
        coeff = arrays["coefficients"][slot, :, : degree + 1]
        if kind == "BDF":
            x = (t - arrays["shift"][slot, :degree, None]) / arrays["denominator"][
                slot, :degree, None
            ]
            values = coeff[:, 1:] @ np.cumprod(x, axis=0) + coeff[:, 0, None]
        else:
            theta = (t - times[slot]) / (times[slot + 1] - times[slot])
            if kind == "RK4":
                values = coeff[:, 0, None] + theta * (
                    coeff[:, 1, None] + theta * (coeff[:, 2, None] + theta * coeff[:, 3, None])
                )
            elif kind == "Radau":
                values = coeff[:, 1:] @ np.cumprod(np.tile(theta, (degree, 1)), axis=0)
                values += coeff[:, 0, None]
            else:
                raise ValueError("Unsupported dense record kind")
        result[selected] = values.T
    indices = np.searchsorted(times, sample)
    exact = times[indices] == sample
    result[exact] = arrays["native_state"][indices[exact]]
    return canonical(case, result, absolute=kind == "RK4")


def recorded(times, states, coefficients, degrees, shifts, denominators):
    arrays = {
        "native_times_s": np.asarray(times),
        "native_state": np.asarray(states),
        "coefficients": np.asarray(coefficients),
        "degree": np.asarray(degrees, dtype=np.int64),
        "shift": np.asarray(shifts),
        "denominator": np.asarray(denominators),
    }
    if not all(np.isfinite(v).all() for v in arrays.values()):
        raise ValueError("Nonfinite native/dense record")
    for value in arrays.values():
        value.flags.writeable = False
    return arrays


def integrate_reference(case, settings, *, budget=None):
    if settings["method"] not in ("Radau", "BDF"):
        raise ValueError("Unsupported independent solver")
    for name in ("rtol", "atol", "max_step_s"):
        spec.number(settings[name], name, positive=True)
    budget = Budget() if budget is None else budget
    started = monotonic()
    state = initial_state(case)
    times, states, coeffs, degrees, shifts, denominators = [0.0], [state.copy()], [], [], [], []
    totals = {"nfev": 0, "njev": 0, "nlu": 0}
    for slot, control in enumerate(case.controls):
        end = case.controls[slot + 1].time_s if slot + 1 < len(case.controls) else case.horizon_s
        if end == control.time_s:
            continue

        def rhs(time, value, held=control):
            return budget.rhs(hyperbolic_rhs, case, held, value)

        result = solve_ivp(
            rhs,
            (control.time_s, end),
            state,
            method=settings["method"],
            rtol=settings["rtol"],
            atol=settings["atol"],
            max_step=settings["max_step_s"],
            dense_output=True,
        )
        if not result.success or result.t[-1] != end:
            raise ValueError(f"Independent solver failed: {result.message}")
        if len(times) + len(result.t) - 2 > MAX_STEPS:
            raise ResourceLimit("Accepted-step budget exhausted")
        for value in result.y.T:
            domain(case, value)
        times.extend(result.t[1:])
        states.extend(result.y.T[1:])
        # Data-only capture of the pinned SciPy 1.18.1 Radau/BDF dense basis.
        for polynomial in result.sol.interpolants:
            c, shift, denominator = np.zeros((case.size, 6)), np.zeros(5), np.ones(5)
            if settings["method"] == "Radau":
                degree = polynomial.Q.shape[1]
                c[:, 0], c[:, 1 : degree + 1] = polynomial.y_old, polynomial.Q
            else:
                degree = polynomial.order
                c[:, : degree + 1] = polynomial.D.T
                shift[:degree], denominator[:degree] = polynomial.t_shift, polynomial.denom
            if not 1 <= degree <= 5:
                raise ValueError("Unexpected dense polynomial degree in the pinned solver")
            coeffs.append(c)
            degrees.append(degree)
            shifts.append(shift)
            denominators.append(denominator)
        for key in totals:
            totals[key] += getattr(result, key)
        state = result.y[:, -1].copy()
    arrays = recorded(times, states, coeffs, degrees, shifts, denominators)
    return arrays, {
        **settings,
        **totals,
        "rhs_calls": budget.calls,
        "accepted_steps": len(times) - 1,
        "seconds": monotonic() - started,
        "minimum_trial_amount_fmol": budget.minimum_amount,
        "max_trial_abs_x": budget.max_abs_x,
    }


def candidate_grid(case, dt):
    spec.number(dt, "candidate step", positive=True)
    ratio = case.horizon_s / dt
    if not math.isfinite(ratio) or ratio > MAX_STEPS:
        raise ResourceLimit("Candidate step budget exhausted")
    count = math.ceil(ratio)
    if count + len(case.controls) > MAX_STEPS:
        raise ResourceLimit("Candidate event/grid budget exhausted")
    return np.unique(
        np.r_[np.arange(count) * dt, [c.time_s for c in case.controls], case.horizon_s]
    )


def integrate_candidate(case, dt, *, budget=None):
    times = candidate_grid(case, dt)
    budget = Budget() if budget is None else budget
    started = monotonic()
    state = initial_state(case, absolute=True)
    history, coeffs = [state.copy()], []
    for left, right in zip(times[:-1], times[1:], strict=True):
        h, control = right - left, case.control_at(float(left))

        def rhs(value, held=control):
            return budget.rhs(bernoulli_rhs, case, held, value, absolute=True)

        k1 = rhs(state)
        k2 = rhs(state + h * k1 / 2)
        k3 = rhs(state + h * k2 / 2)
        k4 = rhs(state + h * k3)
        following = state + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        final_slope = rhs(following)  # Old-interval control, including event endpoints.
        delta = following - state
        c = np.zeros((case.size, 6))
        c[:, 0], c[:, 1] = state, h * k1
        c[:, 2] = 3 * delta - h * (2 * k1 + final_slope)
        c[:, 3] = -2 * delta + h * (k1 + final_slope)
        coeffs.append(c)
        state = following
        history.append(state.copy())
    arrays = recorded(
        times,
        history,
        coeffs,
        [3] * (len(times) - 1),
        np.zeros((len(times) - 1, 5)),
        np.ones((len(times) - 1, 5)),
    )
    return arrays, {
        "method": "RK4",
        "dt_s": dt,
        "rhs_calls": budget.calls,
        "accepted_steps": len(times) - 1,
        "seconds": monotonic() - started,
        "minimum_trial_amount_fmol": budget.minimum_amount,
        "max_trial_abs_x": budget.max_abs_x,
    }


def comparison_grid(case, candidate):
    pieces = []
    for dt in candidate["steps_s"]:
        times = candidate_grid(case, dt)
        pieces.append(times)
        pieces.extend(times[:-1] + f * np.diff(times) for f in candidate["comparison_fractions"])
    result = np.unique(np.concatenate(pieces))
    if len(result) > MAX_SAMPLES:
        raise ResourceLimit("Comparison grid exceeds its sample budget")
    return result
