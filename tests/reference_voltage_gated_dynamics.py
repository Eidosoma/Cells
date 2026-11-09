"""NUM-007 coupled scalar method experiment; no production Cells/JAX imports.

Reuse unchanged dimension-independent NUM-006 record/grid helpers. Independently
express native-unit gate rates and hyperbolic permeation for implicit solves;
the candidate instead calls the frozen SPEC-006 Bernoulli/gate evaluator.
"""

import copy
import hashlib
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from time import monotonic

import numpy as np
from scipy.integrate import solve_ivp

from tests import reference_multispecies as ionic
from tests import reference_multispecies_dynamics as old
from tests import reference_voltage_gated_channel as spec

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "configs/reference/voltage_gated_trajectories_v1.json"
PANEL_SHA256 = "aa07cd7c200a2a93c9484d7b45d5a47a28a766e3958db1511bd230af4a5bd9e0"
ResourceLimit = old.ResourceLimit
candidate_grid = old.candidate_grid
comparison_grid = old.comparison_grid
sample_record = old.sample_record
canonical = old.canonical
MAX_STEPS = old.MAX_STEPS


class DomainViolation(ValueError):
    """A real numerical trial leaves the specified physical/gate domain."""


@dataclass(frozen=True)
class Control(old.Control):
    availability: float

    def __post_init__(self):
        super().__post_init__()
        spec.fraction(self.availability, "channel availability")


@dataclass(frozen=True)
class Case(old.Case):
    channel: spec.Channel

    def __post_init__(self):
        super().__post_init__()
        if self.horizon_s > 2 or any(type(c) is not Control for c in self.controls):
            raise ValueError("NUM-007 requires channel controls and horizons <= 2 seconds")
        spec.Resolved(self.parameters, self.channel)

    @property
    def size(self):
        return 2 * self.species_count + 5

    @property
    def gate_start(self):
        return 2 * self.species_count + 2


def resolve_cases(plan, physical):
    definitions = {c["id"]: c["definition"] for c in physical["cases"]}
    cases = []
    for item in plan["cases"]:
        definition = copy.deepcopy(definitions[item["assembly"]])
        preparation = item["preparation"]
        if preparation is not None:
            allowed = {"initial_gate", "initial_voltage_V", "fixed_charge_equivalent_fmol"}
            if set(preparation) not in ({"initial_gate"}, allowed):
                raise ValueError("Preparation requires explicit gates and paired voltage/charge")
            definition["channel"]["initial_gate"] = preparation["initial_gate"]
            for key in allowed - {"initial_gate"}:
                if key in preparation:
                    definition["assembly"]["cell"][key] = preparation[key]
        resolved = spec.resolve(definition)
        p, profile = resolved.assembly, plan["profiles"][item["profile"]]
        controls = []
        for c in profile["controls"]:
            blocked = c["blocked_species"]
            if len(set(blocked)) != len(blocked) or not set(blocked) <= set(p.species_ids):
                raise ValueError("Blocked species must be unique existing IDs")
            controls.append(
                Control(
                    c["time_s"],
                    tuple(0.0 if s in blocked else c["leak"] for s in p.species_ids),
                    c["pump"],
                    c["availability"],
                )
            )
        cases.append(Case(item["id"], p, profile["horizon_s"], tuple(controls), resolved.channel))
    if len(cases) != 14 or len({c.id for c in cases}) != 14:
        raise ValueError("Require fourteen distinct frozen cases")
    return tuple(cases)


def load_panel():
    if hashlib.sha256(PANEL.read_bytes()).hexdigest() != PANEL_SHA256:
        raise ValueError("Frozen NUM-007 panel changed")
    plan = ionic.load_json(PANEL)
    physical = ROOT / plan["physical_panel"]
    if hashlib.sha256(physical.read_bytes()).hexdigest() != plan["physical_panel_sha256"]:
        raise ValueError("Frozen SPEC-006 physical panel changed")
    return plan, resolve_cases(plan, ionic.load_json(physical))


def initial_state(case, *, absolute=False):
    state = old.initial_state(case, absolute=absolute)
    state[case.gate_start : case.gate_start + 2] = (
        case.channel.initial_gate.m,
        case.channel.initial_gate.h,
    )
    return state


def domain(case, state, *, absolute=False):
    try:
        amount, v, x = old.domain(case, state, absolute=absolute)
        if not -0.120 <= v <= 0.060:
            raise ValueError("Voltage outside gate domain")
        gates = np.asarray(state)[case.gate_start : case.gate_start + 2]
        if np.any(gates < 0) or np.any(gates > 1):
            raise ValueError("Gate outside [0, 1]")
        return amount, v, x
    except ValueError as error:
        raise DomainViolation(str(error)) from error


def hyperbolic_rhs(case, control, state):
    p, c, n = case.parameters, case.channel, case.species_count
    amount, v, xs = domain(case, state)
    base = old.hyperbolic_rhs(case, control, state)
    m, h = state[case.gate_start : case.gate_start + 2]
    mv = 1000 * v
    mi = 1 / (1 + math.exp(-(mv + 6) / 6.4))
    hi = 1 / (1 + math.exp((mv + 25.3) / 3.5))
    dm = 1000 * (mi - m) / (8.33 - 0.1163 * mv)
    dh = 1000 * (hi - h) / (1620 - 15.5 * mv)
    slot = p.species_ids.index(c.species_id)
    ci, co, x = amount[slot] / p.volume_pL, p.bath_mM[slot], xs[slot]
    b = 1.0 if x == 0 else x / (2 * math.tanh(x / 2))
    flux = (
        p.area_m2
        * c.max_permeability_m_per_s
        * c.abundance
        * control.availability
        * m
        * h
        / 1e-15
        * ((co - ci) * b - (co + ci) * x / 2)
    )
    potential = old.R * p.temperature_K * math.log(ci / co) + p.valence[slot] * old.F * v
    result = np.r_[base, dm, dh, flux]
    result[slot] += flux
    result[2 * n + 1] -= 1e-3 * flux * potential
    if not np.isfinite(result).all():
        raise DomainViolation("Nonfinite coupled reference derivative")
    return result


def bernoulli_rhs(case, control, state):
    domain(case, state, absolute=True)
    n, g = case.species_count, case.gate_start
    result = spec.evaluate(
        spec.Resolved(case.parameters, case.channel),
        tuple(float(v) for v in state[:n]),
        spec.Gate(float(state[g]), float(state[g + 1])),
        leak_control=control.leak,
        pump_control=control.pump,
        availability=control.availability,
    )
    return np.r_[
        result.amount_rate_fmol_per_s,
        result.baseline.passive_fmol_per_s,
        result.baseline.pump_cycles_fmol_per_s,
        result.ionic_dissipation_rate_pJ_per_s,
        result.gate_rate_per_s,
        result.channel_flux_fmol_per_s,
    ]


class Budget(old.Budget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.min_gate, self.max_gate = 1.0, 0.0
        self.min_voltage, self.max_voltage = math.inf, -math.inf

    def rhs(self, function, case, control, state, *, absolute=False):
        self.check()
        self.calls += 1
        if self.calls > self.max_calls:
            raise ResourceLimit("Attempt RHS budget exhausted, including Jacobian probes")
        amount, v, x = domain(case, state, absolute=absolute)
        gates = state[case.gate_start : case.gate_start + 2]
        self.minimum_amount = min(self.minimum_amount, float(np.min(amount)))
        self.max_abs_x = max(self.max_abs_x, float(np.max(np.abs(x))))
        self.min_gate, self.max_gate = (
            min(self.min_gate, float(min(gates))),
            max(self.max_gate, float(max(gates))),
        )
        self.min_voltage, self.max_voltage = min(self.min_voltage, v), max(self.max_voltage, v)
        return function(case, control, state)

    def summary(self):
        return {
            "rhs_calls": self.calls,
            "minimum_trial_amount_fmol": self.minimum_amount,
            "max_trial_abs_x": self.max_abs_x,
            "trial_gate_range": [self.min_gate, self.max_gate],
            "trial_voltage_range_V": [self.min_voltage, self.max_voltage],
        }


def recorded(case, times, states, coeffs, degrees, shifts, denominators):
    steps = len(times) - 1
    return old.recorded(
        times,
        states,
        np.asarray(coeffs).reshape(steps, case.size, 6),
        degrees,
        np.asarray(shifts).reshape(steps, 5),
        np.asarray(denominators).reshape(steps, 5),
    )


def integrate_reference(case, settings, *, budget=None):
    if settings["method"] not in ("Radau", "BDF"):
        raise ValueError("Unsupported independent solver")
    for name in ("rtol", "atol", "max_step_s"):
        ionic.number(settings[name], name, positive=True)
    budget = Budget() if budget is None else budget
    started, state = monotonic(), initial_state(case)
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
                raise ValueError("Unexpected pinned SciPy dense degree")
            coeffs.append(c)
            degrees.append(degree)
            shifts.append(shift)
            denominators.append(denominator)
        for key in totals:
            totals[key] += getattr(result, key)
        state = result.y[:, -1].copy()
    arrays = recorded(case, times, states, coeffs, degrees, shifts, denominators)
    return arrays, {
        "status": "complete",
        **settings,
        **totals,
        **budget.summary(),
        "accepted_steps": len(times) - 1,
        "seconds": monotonic() - started,
    }


def integrate_candidate(case, dt, *, budget=None):
    mesh = candidate_grid(case, dt)
    budget = Budget() if budget is None else budget
    started, state = monotonic(), initial_state(case, absolute=True)
    history, times, coeffs, rejection = [state.copy()], [0.0], [], None
    for left, right in zip(mesh[:-1], mesh[1:], strict=True):
        step, control = right - left, case.control_at(float(left))

        def rhs(value, label, time, held=control, start=left, end=right):
            nonlocal rejection
            try:
                return budget.rhs(bernoulli_rhs, case, held, value, absolute=True)
            except DomainViolation as error:
                rejection = {
                    "reason": str(error),
                    "stage": label,
                    "time_s": float(time),
                    "interval_left_s": float(start),
                    "interval_right_s": float(end),
                    "absolute_state": [
                        float(v) if math.isfinite(v) else str(float(v)) for v in value
                    ],
                    "control": asdict(held),
                }
                raise

        try:
            k1 = rhs(state, "k1", left)
            k2 = rhs(state + step * k1 / 2, "k2", left + step / 2)
            k3 = rhs(state + step * k2 / 2, "k3", left + step / 2)
            k4 = rhs(state + step * k3, "k4", right)
            following = state + step / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
            final_slope = rhs(following, "endpoint", right)
        except DomainViolation:
            break
        change = following - state
        c = np.zeros((case.size, 6))
        c[:, 0], c[:, 1] = state, step * k1
        c[:, 2] = 3 * change - step * (2 * k1 + final_slope)
        c[:, 3] = -2 * change + step * (k1 + final_slope)
        coeffs.append(c)
        state = following
        times.append(float(right))
        history.append(state.copy())
    steps = len(times) - 1
    arrays = recorded(
        case, times, history, coeffs, [3] * steps, np.zeros((steps, 5)), np.ones((steps, 5))
    )
    return arrays, {
        "status": "rejected" if rejection else "complete",
        "method": "RK4",
        "dt_s": dt,
        **budget.summary(),
        "accepted_steps": steps,
        "seconds": monotonic() - started,
        "rejected_trial": rejection,
    }
