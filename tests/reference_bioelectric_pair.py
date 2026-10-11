"""Independent NUM-003 CPU oracle and method experiments, not a Cells backend.

Reuses only the independently qualified one-cell reference, never Cells or the
SPEC-002 calculator. Junction flux uses a symmetric hyperbolic expression.
SciPy evolves amount increments; the RK4 probe evolves absolute amounts.
Three dissipation quadratures are diagnostics, not biological state.
"""

import json
from dataclasses import asdict, dataclass, replace
from functools import cached_property
from pathlib import Path
from time import perf_counter

import numpy as np
from scipy.integrate import solve_ivp

from tests import reference_bioelectric as cell

F, R, Z, NU = cell.F, cell.R, cell.Z, cell.NU
QF = cell.CHARGE_PER_FMOL
AMOUNT = slice(0, 6)
LEAK = slice(6, 12)
PUMP = slice(12, 14)
TRANSFER = slice(14, 17)
GATE = 17
DISSIPATION = slice(18, 21)
SIZE = 21
KINETIC = (*range(6), GATE)
MAX_STEPS = 100000
MAX_CALLS = 100000
MAX_SECONDS = 60.0
PANEL_PATH = (
    Path(__file__).resolve().parents[1] / "configs/reference/bioelectric_pair_panel_v1.json"
)
STATE_COLUMNS = (
    "Na_A_fmol",
    "Na_B_fmol",
    "K_A_fmol",
    "K_B_fmol",
    "Cl_A_fmol",
    "Cl_B_fmol",
    "Na_A_leak_fmol",
    "Na_B_leak_fmol",
    "K_A_leak_fmol",
    "K_B_leak_fmol",
    "Cl_A_leak_fmol",
    "Cl_B_leak_fmol",
    "A_pump_cycles_fmol",
    "B_pump_cycles_fmol",
    "Na_oriented_transfer_fmol",
    "K_oriented_transfer_fmol",
    "Cl_oriented_transfer_fmol",
    "gate_fraction",
    "diagnostic_leak_dissipation_pJ",
    "diagnostic_pump_dissipation_pJ",
    "diagnostic_junction_dissipation_pJ",
)


@dataclass(frozen=True)
class Junction:
    endpoints: tuple[int, int] = (0, 1)
    area_m2: float = 1e-11
    permeability_m_per_s: tuple[float, ...] = (1e-8, 5e-9, 2e-9)
    residual: tuple[float, ...] = (0.1, 0.1, 0.0)
    sensitivity_per_V: float = 100.0
    half_voltage_V: float = 0.04
    tau_s: float = 0.2
    initial_gate: float = 0.25

    def __post_init__(self):
        if len(self.endpoints) != 2 or any(type(i) is not int for i in self.endpoints):
            raise ValueError("Junction endpoints must be two integer slots")
        if set(self.endpoints) != {0, 1}:
            raise ValueError("The reference requires one edge between the two distinct cells")
        object.__setattr__(self, "endpoints", tuple(self.endpoints))
        for name in ("area_m2", "sensitivity_per_V", "tau_s"):
            if not np.isfinite(getattr(self, name)) or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if not np.isfinite(self.half_voltage_V) or self.half_voltage_V < 0:
            raise ValueError("Half-voltage must be finite and nonnegative")
        if not np.isfinite(self.initial_gate) or not 0 <= self.initial_gate <= 1:
            raise ValueError("Initial gate must be in [0,1]")
        for name in ("permeability_m_per_s", "residual"):
            values = np.asarray(getattr(self, name), dtype=float)
            if values.shape != (3,) or not np.isfinite(values).all() or np.any(values < 0):
                raise ValueError(f"Invalid {name}")
            if name == "residual" and np.any(values > 1):
                raise ValueError("Residual fractions must be in [0,1]")
            object.__setattr__(self, name, tuple(float(v) for v in values))

    def target(self, delta_v):
        if not np.isfinite(delta_v):
            raise ValueError("Nonfinite gate voltage")
        a, v = self.sensitivity_per_V, self.half_voltage_V
        return float(np.exp(-np.logaddexp.reduce([0.0, a * (-delta_v - v), a * (delta_v - v)])))


@dataclass(frozen=True)
class Parameters:
    cells: tuple[cell.Parameters, ...] = (
        cell.Parameters(),
        cell.Parameters(initial_mM=(18, 130, 15), initial_voltage_V=-0.045),
    )
    junction: Junction = Junction()

    def __post_init__(self):
        if len(self.cells) != 2 or not all(isinstance(p, cell.Parameters) for p in self.cells):
            raise ValueError("Exactly two independently specified physical cells are required")
        if not isinstance(self.junction, Junction):
            raise ValueError("Invalid junction parameters")
        object.__setattr__(self, "cells", tuple(self.cells))
        for name in ("bath_mM", "temperature_K", "atp_free_energy_J_per_mol"):
            if getattr(self.cells[0], name) != getattr(self.cells[1], name):
                raise ValueError("Version 1 requires a common bath, temperature and chemical drive")
        if abs(np.diff(self.initial_voltage)[0] * F / (R * self.temperature)) > cell.MAX_ABS_X:
            raise ValueError("Initial junction voltage outside the dimensionless domain")

    @cached_property
    def initial_amount(self):
        result = np.column_stack([p.initial_amount for p in self.cells])
        result.setflags(write=False)
        return result

    @cached_property
    def capacitance(self):
        result = np.array([p.capacitance for p in self.cells])
        result.setflags(write=False)
        return result

    @cached_property
    def initial_voltage(self):
        result = np.array([p.initial_voltage_V for p in self.cells])
        result.setflags(write=False)
        return result

    @property
    def temperature(self):
        return self.cells[0].temperature_K

    def voltage(self, amount):
        delta = np.asarray(amount) - self.initial_amount
        return self.initial_voltage + QF / self.capacitance * np.einsum("s,...sc->...c", Z, delta)


@dataclass(frozen=True)
class Control:
    time: float = 0.0
    leak: tuple[tuple[float, ...], ...] = ((1, 1), (1, 1), (1, 1))
    pump: tuple[float, ...] = (1, 1)
    contact: float = 1.0

    def __post_init__(self):
        if not np.isfinite(self.time) or self.time < 0:
            raise ValueError("Control time must be finite and nonnegative")
        if not np.isfinite(self.contact) or not 0 <= self.contact <= 1:
            raise ValueError("Contact control must lie in [0,1]")
        for name, shape in (("leak", (3, 2)), ("pump", (2,))):
            values = np.asarray(getattr(self, name), dtype=float)
            if values.shape != shape or not np.isfinite(values).all():
                raise ValueError(f"Invalid {name} control shape or values")
            if np.any(values < 0) or np.any(values > 1):
                raise ValueError(f"{name} controls must lie in [0,1]")
            converted = (
                tuple(tuple(float(v) for v in row) for row in values)
                if name == "leak"
                else tuple(float(v) for v in values)
            )
            object.__setattr__(self, name, converted)

    @cached_property
    def membrane_controls(self):
        return tuple(
            cell.Control(leak=np.asarray(self.leak)[:, i], pump=self.pump[i]) for i in range(2)
        )


@dataclass(frozen=True)
class Case:
    id: str
    name: str
    parameters: Parameters = Parameters()
    horizon: float = 10.0
    controls: tuple[Control, ...] = (Control(),)

    def __post_init__(self):
        if not np.isfinite(self.horizon) or not 0 < self.horizon <= 10:
            raise ValueError("Reference horizon must lie in (0,10] seconds")
        object.__setattr__(self, "controls", tuple(self.controls))
        times = [c.time for c in self.controls]
        if not times or times[0] != 0 or np.any(np.diff(times) <= 0) or times[-1] > self.horizon:
            raise ValueError("Controls must start at zero and increase within the horizon")

    def control_at(self, time):
        if not np.isfinite(time) or not 0 <= time <= self.horizon:
            raise ValueError("Control query outside the reference horizon")
        index = np.searchsorted([c.time for c in self.controls], time, side="right") - 1
        return self.controls[index]

    def definition(self):
        return asdict(self)


def load_panel(path=PANEL_PATH):
    data = json.loads(path.read_text())
    if data["schema_version"] != 1:
        raise ValueError("Unsupported pair-panel schema")
    base = data["base"]
    cases = []
    for row in data["cases"]:
        unknown = set(row) - {"id", "name", "horizon", "cell_overrides", "junction", "controls"}
        if unknown:
            raise ValueError(f"Unknown case fields: {unknown}")
        overrides = row.get("cell_overrides", {})
        if set(overrides) - {"0", "1"}:
            raise ValueError("Unknown cell override slot")
        cells = tuple(
            cell.Parameters(**(p | overrides.get(str(i), {}))) for i, p in enumerate(base["cells"])
        )
        parameters = Parameters(cells, Junction(**(base["junction"] | row.get("junction", {}))))
        controls = tuple(Control(**c) for c in row.get("controls", base["controls"]))
        cases.append(
            Case(row["id"], row["name"], parameters, row.get("horizon", base["horizon"]), controls)
        )
    if [c.id for c in cases] != [f"Q{i:02d}" for i in range(20)]:
        raise ValueError("Frozen panel must contain Q00 through Q19 exactly once in order")
    return data, tuple(cases)


def initial_state(parameters, *, increments=False):
    state = np.zeros(SIZE)
    if not increments:
        state[AMOUNT] = parameters.initial_amount.ravel()
    state[GATE] = parameters.junction.initial_gate
    return state


def unpack(parameters, state, *, increments):
    value = np.asarray(state)
    if value.shape != (SIZE,) or not np.isfinite(value).all():
        raise ValueError("Trial state requires 21 finite coordinates")
    if not 0 <= value[GATE] <= 1:
        raise ValueError("Trial gate outside [0,1]; no clipping permitted")
    delta = value[AMOUNT].reshape(3, 2)
    if not increments:
        delta = delta - parameters.initial_amount
    amount = parameters.initial_amount + delta if increments else value[AMOUNT].reshape(3, 2)
    if np.any(amount <= 0):
        raise ValueError("Trial ion amounts must be strictly positive")
    voltage = parameters.initial_voltage + QF / parameters.capacitance * (Z @ delta)
    voltages = np.r_[voltage, voltage[0] - voltage[1]]
    if np.max(np.abs(voltages)) * F / (R * parameters.temperature) > cell.MAX_ABS_X:
        raise ValueError("Membrane or junction voltage outside abs(zF deltaV/RT) <= 50")
    return amount, voltage, float(value[GATE])


def junction_flux(parameters, amount, voltage, gate, control):
    edge = parameters.junction
    a, b = edge.endpoints
    ca, cb = (
        amount[:, a] / parameters.cells[a].volume_pL,
        amount[:, b] / parameters.cells[b].volume_pL,
    )
    x = Z * F * (voltage[a] - voltage[b]) / (R * parameters.temperature)
    h = np.ones(3)
    mask = x != 0
    h[mask] = x[mask] / (2 * np.tanh(x[mask] / 2))
    residual = np.asarray(edge.residual)
    amplitude = (
        edge.area_m2
        * np.asarray(edge.permeability_m_per_s)
        * control.contact
        * (residual + (1 - residual) * gate)
        / 1e-15
    )
    return amplitude * ((ca - cb) * h + (ca + cb) * x / 2)


def rates(parameters, amount, voltage, gate, control):
    local = [
        cell.fluxes(p, amount[:, i], voltage[i], control.membrane_controls[i])
        for i, p in enumerate(parameters.cells)
    ]
    leak = np.column_stack([row[0] for row in local])
    cycles = np.array([row[1] for row in local])
    mu = np.column_stack([row[2] for row in local])
    cycle_energy = np.array([row[3] for row in local])
    edge = parameters.junction
    a, b = edge.endpoints
    transfer = junction_flux(parameters, amount, voltage, gate, control)
    gate_rate = (edge.target(voltage[a] - voltage[b]) - gate) / edge.tau_s
    # Every term is evaluated from this same stage state. Diagnostics are pJ/s.
    dissipation = -1e-3 * np.array(
        [np.sum(leak * mu), cycles @ cycle_energy, transfer @ (mu[:, b] - mu[:, a])]
    )
    return leak, cycles, transfer, gate_rate, dissipation


def derivative(parameters, control, state, *, increments):
    amount, voltage, gate = unpack(parameters, state, increments=increments)
    leak, cycles, transfer, gate_rate, dissipation = rates(
        parameters, amount, voltage, gate, control
    )
    change = leak + NU[:, None] * cycles
    a, b = parameters.junction.endpoints
    change[:, a] -= transfer
    change[:, b] += transfer
    result = np.r_[change.ravel(), leak.ravel(), cycles, transfer, gate_rate, dissipation]
    if not np.isfinite(result).all():
        raise ValueError("Nonfinite pair derivative")
    return result


def bounded_jacobian(parameters, state, rhs, *, step=1e-6):
    """Only seven kinetic columns; second-order differences with valid probes.

    Unlike SciPy's default forward differencing at g=1, every evaluated gate
    remains in [0,1]. No state projection and no differentiation of ledgers.
    """
    unpack(parameters, state, increments=True)
    result = np.zeros((SIZE, SIZE))
    for coordinate in KINETIC:
        h = step
        for _ in range(10):
            change = np.zeros(SIZE)
            change[coordinate] = h

            def valid(value):
                try:
                    unpack(parameters, value, increments=True)
                    return True
                except ValueError:
                    return False

            if valid(state + change) and valid(state - change):
                column = (rhs(state + change) - rhs(state - change)) / (2 * h)
                break
            if valid(state + change) and valid(state + 2 * change):
                column = (-3 * rhs(state) + 4 * rhs(state + change) - rhs(state + 2 * change)) / (
                    2 * h
                )
                break
            if valid(state - change) and valid(state - 2 * change):
                column = (3 * rhs(state) - 4 * rhs(state - change) + rhs(state - 2 * change)) / (
                    2 * h
                )
                break
            h /= 10
        else:
            raise ValueError("No valid bounded Jacobian stencil")
        result[:, coordinate] = column
    return result


def domain_summary(parameters, values):
    values = np.asarray(values)
    if (
        values.ndim != 2
        or values.shape[1] != SIZE
        or not len(values)
        or not np.isfinite(values).all()
    ):
        raise ValueError("Invalid sampled state array")
    amount = values[:, AMOUNT].reshape(-1, 3, 2)
    gate = values[:, GATE]
    voltage = parameters.voltage(amount)
    largest = (
        max(np.max(np.abs(voltage)), np.max(np.abs(voltage[:, 0] - voltage[:, 1])))
        * F
        / (R * parameters.temperature)
    )
    if np.any(amount <= 0) or np.any(gate < 0) or np.any(gate > 1) or largest > cell.MAX_ABS_X:
        raise ValueError("Sampled amount, voltage or gate outside the declared domain")
    return {
        "minimum_amount_fmol": float(np.min(amount)),
        "gate_range": [float(np.min(gate)), float(np.max(gate))],
        "max_abs_x": float(largest),
    }


@dataclass
class Reference:
    case: Case
    segments: list
    stats: dict

    def sample(self, times):
        times = checked_samples(times, 0, self.case.horizon)
        result = np.empty((len(times), SIZE))
        ends = [s.t[-1] for s in self.segments]
        slots = np.minimum(np.searchsorted(ends, times, side="right"), len(ends) - 1)
        for i, segment in enumerate(self.segments):
            mask = slots == i
            if np.any(mask):
                result[mask] = segment.sol(times[mask]).T
        result[:, AMOUNT] += self.case.parameters.initial_amount.ravel()
        if len(result):
            domain_summary(self.case.parameters, result)
        return result


def integrate_reference(case, *, method="Radau", rtol=1e-11, atol=1e-13, max_step=0.25):
    if method not in ("Radau", "BDF"):
        raise ValueError("Use Radau or BDF for this qualification")
    if not np.isfinite([rtol, atol, max_step]).all() or min(rtol, atol, max_step) <= 0:
        raise ValueError("Invalid reference settings")
    state = initial_state(case.parameters, increments=True)
    start = perf_counter()
    calls = jac_calls = 0
    minimum = float(np.min(case.parameters.initial_amount))
    gate_min = gate_max = case.parameters.junction.initial_gate
    largest = 0.0
    segments = []
    for i, control in enumerate(case.controls):
        end = case.controls[i + 1].time if i + 1 < len(case.controls) else case.horizon
        if end == control.time:
            continue

        def rhs(time, value, applied=control):
            nonlocal calls, minimum, gate_min, gate_max, largest
            calls += 1
            if calls > MAX_CALLS or perf_counter() - start > MAX_SECONDS:
                raise ValueError("Reference RHS/time budget exceeded")
            amount, voltage, gate = unpack(case.parameters, value, increments=True)
            minimum = min(minimum, float(np.min(amount)))
            gate_min, gate_max = min(gate_min, gate), max(gate_max, gate)
            largest = max(
                largest,
                float(np.max(np.abs(np.r_[voltage, voltage[0] - voltage[1]])))
                * F
                / (R * case.parameters.temperature),
            )
            return derivative(case.parameters, applied, value, increments=True)

        def jacobian(time, value):
            nonlocal jac_calls
            jac_calls += 1
            return bounded_jacobian(case.parameters, value, lambda y: rhs(time, y))

        solution = solve_ivp(
            rhs,
            (control.time, end),
            state,
            method=method,
            rtol=rtol,
            atol=atol,
            max_step=max_step,
            jac=jacobian,
            dense_output=True,
        )
        if not solution.success or solution.t[-1] != end or not np.isfinite(solution.y).all():
            raise ValueError(f"Reference failed for {case.id}: {solution.message}")
        state = solution.y[:, -1].copy()
        unpack(case.parameters, state, increments=True)
        segments.append(solution)
    return Reference(
        case,
        segments,
        {
            "method": method,
            "rtol": rtol,
            "atol": atol,
            "max_step_s": max_step,
            "jacobian": "boundary_aware_second_order_7_column_finite_difference",
            "seconds": perf_counter() - start,
            "nfev": sum(s.nfev for s in segments),
            "njev": jac_calls,
            "nlu": sum(s.nlu for s in segments),
            "accepted_steps": sum(len(s.t) - 1 for s in segments),
            "rhs_calls_including_jacobian": calls,
            "trial_domain": {
                "minimum_amount_fmol": minimum,
                "gate_range": [gate_min, gate_max],
                "max_abs_x": largest,
            },
        },
    )


def probe_grid(case, dt):
    if not np.isfinite(dt) or dt <= 0:
        raise ValueError("Timestep must be finite and positive")
    ratio = case.horizon / dt
    if not np.isfinite(ratio) or ratio + len(case.controls) > MAX_STEPS:
        raise ValueError("RK4 step budget exceeded")
    return np.unique(
        np.r_[np.arange(int(np.ceil(ratio))) * dt, [c.time for c in case.controls], case.horizon]
    )


class ProbeFailure(ValueError):
    def __init__(self, message, trial, times, values):
        super().__init__(message)
        self.trial = trial
        self.times = np.asarray(times)
        self.values = np.asarray(values)


def integrate_rk4_probe(case, dt):
    times = probe_grid(case, dt)
    value = initial_state(case.parameters)
    history = [value.copy()]
    start = perf_counter()
    minimum, gate_min, gate_max, largest = (
        float(np.min(value[AMOUNT])),
        value[GATE],
        value[GATE],
        0.0,
    )
    for index, (a, b) in enumerate(zip(times[:-1], times[1:], strict=True)):
        h, control = b - a, case.control_at(a)

        def rhs(y, stage, trial_time, applied=control, accepted_index=index):
            nonlocal minimum, gate_min, gate_max, largest
            try:
                if perf_counter() - start > MAX_SECONDS:
                    raise ValueError("RK4 wall-time budget exceeded")
                amount, voltage, gate = unpack(case.parameters, y, increments=False)
                result = derivative(case.parameters, applied, y, increments=False)
            except ValueError as error:
                raise ProbeFailure(
                    str(error),
                    {"time_s": float(trial_time), "stage": stage, "state": y.tolist()},
                    times[: accepted_index + 1],
                    history,
                ) from error
            minimum = min(minimum, float(np.min(amount)))
            gate_min, gate_max = min(gate_min, gate), max(gate_max, gate)
            largest = max(
                largest,
                float(np.max(np.abs(np.r_[voltage, voltage[0] - voltage[1]])))
                * F
                / (R * case.parameters.temperature),
            )
            return result

        k1 = rhs(value, "k1", a)
        k2 = rhs(value + h * k1 / 2, "k2", a + h / 2)
        k3 = rhs(value + h * k2 / 2, "k3", a + h / 2)
        k4 = rhs(value + h * k3, "k4", b)
        value = value + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        rhs(value, "accepted_endpoint", b)
        history.append(value.copy())
    return (
        times,
        np.asarray(history),
        {
            "method": "independent_numpy_RK4_probe",
            "dt_s": dt,
            "accepted_steps": len(times) - 1,
            "maximum_actual_step_s": float(np.max(np.diff(times))),
            "seconds": perf_counter() - start,
            "trial_domain": {
                "minimum_amount_fmol": minimum,
                "gate_range": [float(gate_min), float(gate_max)],
                "max_abs_x": largest,
            },
        },
    )


def checked_samples(samples, start, end):
    samples = np.asarray(samples, dtype=float)
    if samples.ndim != 1 or not np.isfinite(samples).all() or np.any(np.diff(samples) < 0):
        raise ValueError("Samples must be finite and nondecreasing")
    if len(samples) and (samples[0] < start or samples[-1] > end):
        raise ValueError("Samples outside the accepted/reference horizon")
    return samples


def hermite_coefficients(case, times, values):
    slopes = [
        (
            derivative(case.parameters, case.control_at(t), values[i], increments=False),
            derivative(case.parameters, case.control_at(t), values[i + 1], increments=False),
        )
        for i, t in enumerate(times[:-1])
    ]
    f0, f1 = np.asarray(slopes).transpose(1, 0, 2)
    h, delta = np.diff(times)[:, None], np.diff(values, axis=0)
    return h * f0, 3 * delta - h * (2 * f0 + f1), -2 * delta + h * (f0 + f1)


def polynomial_extrema(y0, a, b, c):
    """Extrema of y0 + theta*(a + theta*(b + theta*c)) on [0,1]."""
    lower, upper = np.minimum(y0, y0 + a + b + c), np.maximum(y0, y0 + a + b + c)
    discriminant = b * b - 3 * c * a
    quadratic = (c != 0) & (discriminant >= 0)
    roots = []
    for sign in (-1, 1):
        root = np.full_like(a, -1.0)
        root[quadratic] = (-b[quadratic] + sign * np.sqrt(discriminant[quadratic])) / (
            3 * c[quadratic]
        )
        roots.append(root)
    linear = (c == 0) & (b != 0)
    root = np.full_like(a, -1.0)
    root[linear] = -a[linear] / (2 * b[linear])
    roots.append(root)
    for theta in roots:
        mask = (theta > 0) & (theta < 1)
        value = y0[mask] + theta[mask] * (a[mask] + theta[mask] * (b[mask] + theta[mask] * c[mask]))
        lower[mask] = np.minimum(lower[mask], value)
        upper[mask] = np.maximum(upper[mask], value)
    return lower, upper


def interpolant_domain(parameters, values, coefficients):
    """Check cubic interior extrema, not only the requested observation samples."""
    # Use increments for amounts, avoiding a second absolute endpoint sum.
    lower, upper = polynomial_extrema(np.zeros_like(values[:-1]), *coefficients)
    lower, upper = values[:-1] + lower, values[:-1] + upper
    minimum = min(float(np.min(lower[:, AMOUNT])), float(np.min(values[:, AMOUNT])))
    gates = [
        min(float(np.min(lower[:, GATE])), float(np.min(values[:, GATE]))),
        max(float(np.max(upper[:, GATE])), float(np.max(values[:, GATE]))),
    ]
    v0 = parameters.voltage(values[:-1, AMOUNT].reshape(-1, 3, 2))

    def voltage_components(v):
        return np.column_stack([v, v[:, 0] - v[:, 1]])

    vcoeff = [
        voltage_components(
            QF / parameters.capacitance * np.einsum("s,tsc->tc", Z, v[:, AMOUNT].reshape(-1, 3, 2))
        )
        for v in coefficients
    ]
    low_v, high_v = polynomial_extrema(voltage_components(v0), *vcoeff)
    largest = (
        max(float(np.max(np.abs(low_v))), float(np.max(np.abs(high_v))))
        * F
        / (R * parameters.temperature)
    )
    if minimum <= 0 or gates[0] < 0 or gates[1] > 1 or largest > cell.MAX_ABS_X:
        raise ValueError("Cubic interpolant leaves the amount/gate/voltage domain")
    return {
        "minimum_amount_fmol": minimum,
        "gate_range": gates,
        "max_abs_x": largest,
        "scope": "floating-point polynomial extrema of every cubic interval",
    }


def sample_probe(case, times, values, samples, *, method="hermite", coefficients=None):
    if method not in ("hermite", "linear"):
        raise ValueError("Unknown observation method")
    samples = checked_samples(samples, times[0], times[-1])
    slots = np.minimum(np.searchsorted(times, samples, side="right") - 1, len(times) - 2)
    theta = ((samples - times[slots]) / (times[slots + 1] - times[slots]))[:, None]
    if method == "linear":
        result = values[slots] + theta * (values[slots + 1] - values[slots])
    else:
        if coefficients is None:
            coefficients = hermite_coefficients(case, times, values)
        a, b, c = [v[slots] for v in coefficients]
        result = values[slots] + theta * (a + theta * (b + theta * c))
    # Never round-trip a stored endpoint through interpolation arithmetic.
    exact = np.searchsorted(times, samples)
    mask = times[exact] == samples
    result[mask] = values[exact[mask]]
    if len(result):
        domain_summary(case.parameters, result)
    return result


def observation_grid(times):
    return np.unique(np.r_[times, *(times[:-1] + q * np.diff(times) for q in (0.25, 0.5, 0.75))])


def trajectory_errors(parameters, actual, expected):
    if (
        actual.shape != expected.shape
        or not np.isfinite(actual).all()
        or not np.isfinite(expected).all()
    ):
        raise ValueError("Invalid trajectory comparison")
    result = {
        name: float(np.max(np.abs(actual[:, slots] - expected[:, slots]), initial=0))
        for name, slots in (
            ("amount_fmol", AMOUNT),
            ("leak_fmol", LEAK),
            ("pump_cycles_fmol", PUMP),
            ("transfer_fmol", TRANSFER),
            ("gate_fraction", GATE),
            ("dissipation_pJ", DISSIPATION),
        )
    }
    actual_v = parameters.voltage(actual[:, AMOUNT].reshape(-1, 3, 2))
    expected_v = parameters.voltage(expected[:, AMOUNT].reshape(-1, 3, 2))
    result["voltage_V"] = float(np.max(np.abs(actual_v - expected_v), initial=0))
    return result


def grand_potential_pJ(parameters, amount):
    amount = np.asarray(amount)
    volumes = np.array([p.volume_pL for p in parameters.cells])
    bath = np.asarray(parameters.cells[0].bath_mM)[:, None]
    chemical = (
        1e-3
        * R
        * parameters.temperature
        * np.sum(amount * (np.log(amount / volumes / bath) - 1), axis=(-2, -1))
    )
    electrical = 0.5e12 * np.sum(parameters.capacitance * parameters.voltage(amount) ** 2, axis=-1)
    return chemical + electrical


def balances(parameters, values):
    amount = values[:, AMOUNT].reshape(-1, 3, 2)
    leak = values[:, LEAK].reshape(-1, 3, 2)
    cycles = values[:, PUMP]
    transfer = values[:, TRANSFER]
    expected = leak + NU[None, :, None] * cycles[:, None, :]
    a, b = parameters.junction.endpoints
    expected[:, :, a] -= transfer
    expected[:, :, b] += transfer
    residual = amount - parameters.initial_amount - expected
    charge_v = QF / parameters.capacitance * np.einsum("s,tsc->tc", Z, residual)
    potential = grand_potential_pJ(parameters, amount) - grand_potential_pJ(
        parameters, parameters.initial_amount
    )
    supplied = -1e-3 * parameters.cells[0].atp_free_energy_J_per_mol * np.sum(cycles, axis=1)
    energy = potential + np.sum(values[:, DISSIPATION], axis=1) - supplied
    return {
        "amount_fmol": float(np.max(np.abs(residual), initial=0)),
        "charge_as_voltage_V": float(np.max(np.abs(charge_v), initial=0)),
        "energy_pJ": float(np.max(np.abs(energy), initial=0)),
    }


def local_spectrum(case):
    state = initial_state(case.parameters, increments=True)
    jac = bounded_jacobian(
        case.parameters,
        state,
        lambda y: derivative(case.parameters, case.controls[0], y, increments=True),
    )
    kinetic = jac[np.ix_(KINETIC, KINETIC)]
    eigenvalues = np.linalg.eigvals(kinetic)
    return {
        "coordinates": "six amount increments plus gate",
        "eigenvalues_real_per_s": eigenvalues.real.tolist(),
        "eigenvalues_imag_per_s": eigenvalues.imag.tolist(),
        "spectral_radius_per_s": float(np.max(np.abs(eigenvalues))),
    }


def cell_case(case, slot):
    """Independently integrated one-cell comparison for a blocked junction."""
    return cell.Case(
        f"{case.id}_cell_{slot}",
        case.parameters.cells[slot],
        case.horizon,
        tuple(replace(c.membrane_controls[slot], time=c.time) for c in case.controls),
    )
