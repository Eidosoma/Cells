"""Independent CPU reference and numerical-method probe for SPEC-001.

No Cells or design-calculator imports. This is not a registered simulator model.
The SciPy oracle evolves amount *increments*, whereas the RK4 method probe evolves
absolute amounts. Both append an independent dissipation quadrature (pJ), which
is a reference diagnostic, not additional primary state required by SPEC-001.
"""

from dataclasses import asdict, dataclass, replace
from time import perf_counter

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

F = 6.02214076e23 * 1.602176634e-19
R = 6.02214076e23 * 1.380649e-23
MOL_PER_FMOL = 1e-15
CHARGE_PER_FMOL = F * MOL_PER_FMOL
Z = np.array([1.0, 1.0, -1.0])
NU = np.array([-3.0, 2.0, 0.0])
MAX_ABS_X = 50.0
MAX_REFERENCE_HORIZON = 100000.0
MAX_REFERENCE_EVALUATIONS = 100000
MAX_PROBE_STEPS = 100000


@dataclass(frozen=True)
class Parameters:
    volume_pL: float = 1.0
    area_m2: float = 1e-9
    specific_capacitance_F_per_m2: float = 0.01
    temperature_K: float = 298.15
    initial_mM: tuple[float, ...] = (12.0, 140.0, 10.0)
    bath_mM: tuple[float, ...] = (145.0, 5.0, 150.0)
    permeability_m_per_s: tuple[float, ...] = (1e-10, 1e-9, 1e-10)
    initial_voltage_V: float = -0.065
    pump_capacity_fmol_per_s: float = 0.02
    atp_free_energy_J_per_mol: float = -50000.0

    def __post_init__(self):
        for name in ("volume_pL", "area_m2", "specific_capacitance_F_per_m2", "temperature_K"):
            value = getattr(self, name)
            if not np.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        for name in ("initial_mM", "bath_mM", "permeability_m_per_s"):
            values = np.asarray(getattr(self, name), dtype=float)
            if values.shape != (3,) or not np.isfinite(values).all():
                raise ValueError(f"{name} requires three finite values in Na/K/Cl order")
            if np.any(values < 0) or (name != "permeability_m_per_s" and np.any(values == 0)):
                raise ValueError(f"{name} outside its positive/nonnegative domain")
            object.__setattr__(self, name, tuple(float(v) for v in values))
        if not np.isfinite([self.initial_voltage_V, self.atp_free_energy_J_per_mol]).all():
            raise ValueError("Voltage and chemical drive must be finite")
        if not np.isfinite(self.pump_capacity_fmol_per_s) or self.pump_capacity_fmol_per_s < 0:
            raise ValueError("Pump capacity must be finite and nonnegative")
        if abs(Z @ self.bath_mM) > 1e-12:
            raise ValueError("This reference requires an electroneutral Na/K/Cl bath")
        if not np.isfinite(self.capacitance) or self.capacitance <= 0:
            raise ValueError("Derived capacitance must be finite and positive")
        if not np.isfinite(self.initial_amount).all() or np.any(self.initial_amount <= 0):
            raise ValueError("Derived initial amounts must be finite and positive")
        if not np.isfinite(self.fixed_anion_equivalent) or self.fixed_anion_equivalent < 0:
            raise ValueError("Initial anchors require nonnegative fixed anion equivalent")
        if abs(self.initial_voltage_V * F / (R * self.temperature_K)) > MAX_ABS_X:
            raise ValueError("Initial voltage exceeds the declared dimensionless domain")

    @property
    def initial_amount(self):
        return np.asarray(self.initial_mM) * self.volume_pL

    @property
    def capacitance(self):
        return self.area_m2 * self.specific_capacitance_F_per_m2

    @property
    def fixed_anion_equivalent(self):
        return Z @ self.initial_amount - self.capacitance * self.initial_voltage_V / CHARGE_PER_FMOL

    def voltage(self, amount):
        return self.initial_voltage_V + CHARGE_PER_FMOL / self.capacitance * (
            (np.asarray(amount) - self.initial_amount) @ Z
        )


@dataclass(frozen=True)
class Control:
    time: float = 0.0
    leak: tuple[float, ...] = (1.0, 1.0, 1.0)
    pump: float = 1.0

    def __post_init__(self):
        values = np.asarray(self.leak, dtype=float)
        if values.shape != (3,) or not np.isfinite(values).all():
            raise ValueError("Leak control requires three finite values")
        if not np.isfinite(self.pump) or np.any(values < 0) or np.any(values > 1):
            raise ValueError("Control multipliers must lie in [0, 1]")
        if not 0 <= self.pump <= 1 or not np.isfinite(self.time) or self.time < 0:
            raise ValueError("Invalid pump multiplier or event time")
        object.__setattr__(self, "leak", tuple(float(v) for v in values))


@dataclass(frozen=True)
class Case:
    name: str
    parameters: Parameters = Parameters()
    horizon: float = 10.0
    controls: tuple[Control, ...] = (Control(),)

    def __post_init__(self):
        if not np.isfinite(self.horizon) or not 0 < self.horizon <= MAX_REFERENCE_HORIZON:
            raise ValueError("Reference horizon outside bounded domain")
        object.__setattr__(self, "controls", tuple(self.controls))
        times = np.asarray([c.time for c in self.controls])
        if times.size == 0 or times[0] != 0 or np.any(np.diff(times) <= 0):
            raise ValueError("Controls must start at zero and be strictly increasing")
        if times[-1] > self.horizon:
            raise ValueError("Control lies beyond the horizon")

    def control_at(self, time):
        slot = np.searchsorted([c.time for c in self.controls], time, side="right") - 1
        if slot < 0 or time > self.horizon or not np.isfinite(time):
            raise ValueError("Control query outside the case horizon")
        return self.controls[slot]

    def definition(self):
        return asdict(self)


def fluxes(parameters, amount, voltage, control):
    """Symmetric hyperbolic constant-field form; independent of the B(x) calculator."""
    n = np.asarray(amount)
    if n.shape != (3,) or not np.isfinite(n).all() or np.any(n <= 0):
        raise ValueError("Reference trial amounts must be finite and strictly positive")
    ci, co = n / parameters.volume_pL, np.asarray(parameters.bath_mM)
    x = Z * F * voltage / (R * parameters.temperature_K)
    if not np.isfinite(x).all() or np.any(np.abs(x) > MAX_ABS_X):
        raise ValueError("Reference trial voltage exceeds abs(zFV/RT) <= 50")
    # H(x) = x/(2 tanh(x/2)) is even and has a removable singularity.
    h = np.ones(3)
    nonzero = x != 0
    h[nonzero] = x[nonzero] / (2 * np.tanh(x[nonzero] / 2))
    leak = (
        parameters.area_m2
        * np.asarray(parameters.permeability_m_per_s)
        * np.asarray(control.leak)
        / MOL_PER_FMOL
        * ((co - ci) * h - (co + ci) * x / 2)
    )
    delta_mu = R * parameters.temperature_K * np.log(ci / co) + Z * F * voltage
    cycle_energy = parameters.atp_free_energy_J_per_mol + NU @ delta_mu
    cycles = (
        parameters.pump_capacity_fmol_per_s
        * control.pump
        * np.tanh(-cycle_energy / (2 * R * parameters.temperature_K))
    )
    return leak, float(cycles), delta_mu, float(cycle_energy)


def derivative(parameters, control, state, *, increments):
    state = np.asarray(state)
    if state.shape != (8,) or not np.isfinite(state).all():
        raise ValueError("Reference trial state requires eight finite coordinates")
    delta = state[:3] if increments else state[:3] - parameters.initial_amount
    amount = parameters.initial_amount + delta if increments else state[:3]
    voltage = parameters.initial_voltage_V + CHARGE_PER_FMOL / parameters.capacitance * (Z @ delta)
    leak, cycles, delta_mu, cycle_energy = fluxes(parameters, amount, voltage, control)
    dissipation_pJ_per_s = -1e12 * MOL_PER_FMOL * (leak @ delta_mu + cycles * cycle_energy)
    return np.r_[leak + NU * cycles, leak, cycles, dissipation_pJ_per_s]


def initial_state(parameters, *, increments=False):
    state = np.zeros(8)
    if not increments:
        state[:3] = parameters.initial_amount
    return state


@dataclass
class Reference:
    case: Case
    segments: list
    stats: dict

    def sample(self, times):
        times = np.asarray(times, dtype=float)
        if times.ndim != 1 or not np.isfinite(times).all() or np.any(np.diff(times) < 0):
            raise ValueError("Samples must be finite and nondecreasing")
        if times.size and (times[0] < 0 or times[-1] > self.case.horizon):
            raise ValueError("Samples outside reference horizon")
        values = np.empty((len(times), 8))
        ends = [segment.t[-1] for segment in self.segments]
        for i, time in enumerate(times):
            slot = min(np.searchsorted(ends, time, side="right"), len(ends) - 1)
            values[i] = self.segments[slot].sol(time)
        values[:, :3] += self.case.parameters.initial_amount
        return values


def integrate_reference(case, *, method="Radau", rtol=1e-11, atol=1e-13, max_step=0.25):
    """Integrate each constant-control interval separately, including exact endpoints."""
    if method not in ("Radau", "BDF", "DOP853"):
        raise ValueError("Unsupported reference solver")
    if not np.isfinite([rtol, atol, max_step]).all() or min(rtol, atol, max_step) <= 0:
        raise ValueError("Reference tolerances and maximum step must be finite and positive")
    state = initial_state(case.parameters, increments=True)
    segments = []
    trials = {
        "minimum_amount_fmol": float(np.min(case.parameters.initial_amount)),
        "max_abs_x": 0.0,
    }
    evaluations = 0
    start = perf_counter()
    for index, control in enumerate(case.controls):
        end = case.controls[index + 1].time if index + 1 < len(case.controls) else case.horizon
        if end == control.time:
            continue

        def rhs(time, value, applied=control):
            nonlocal evaluations
            evaluations += 1
            if evaluations > MAX_REFERENCE_EVALUATIONS:
                raise ValueError("Reference exceeds RHS evaluation budget")
            result = derivative(case.parameters, applied, value, increments=True)
            trials["minimum_amount_fmol"] = min(
                trials["minimum_amount_fmol"],
                float(np.min(case.parameters.initial_amount + value[:3])),
            )
            voltage = (
                case.parameters.initial_voltage_V
                + CHARGE_PER_FMOL / case.parameters.capacitance * (Z @ value[:3])
            )
            trials["max_abs_x"] = max(
                trials["max_abs_x"], abs(float(F * voltage / (R * case.parameters.temperature_K)))
            )
            return result

        solution = solve_ivp(
            rhs,
            (control.time, end),
            state,
            method=method,
            rtol=rtol,
            atol=atol,
            max_step=max_step,
            dense_output=True,
        )
        if not solution.success or solution.t[-1] != end or not np.isfinite(solution.y).all():
            raise ValueError(f"Reference failed for {case.name}: {solution.message}")
        state = solution.y[:, -1].copy()
        segments.append(solution)
    return Reference(
        case,
        segments,
        {
            "method": method,
            "rtol": rtol,
            "atol": atol,
            "max_step_s": max_step,
            "seconds": perf_counter() - start,
            "nfev": sum(s.nfev for s in segments),
            "njev": sum(s.njev for s in segments),
            "nlu": sum(s.nlu for s in segments),
            "accepted_steps": sum(len(s.t) - 1 for s in segments),
            "rhs_calls_including_jacobian_probes": evaluations,
            "trial_domain": trials,
        },
    )


def probe_grid(case, dt):
    if not np.isfinite(dt) or dt <= 0:
        raise ValueError("Probe timestep must be finite and positive")
    count = int(np.ceil(case.horizon / dt))
    if count + len(case.controls) > MAX_PROBE_STEPS:
        raise ValueError("Probe exceeds step budget")
    return np.unique(np.r_[np.arange(count) * dt, [c.time for c in case.controls], case.horizon])


def integrate_rk4_probe(case, dt):
    """Independent scalar CPU method experiment, not Cells' production integrator."""
    times = probe_grid(case, dt)
    state = initial_state(case.parameters)
    history = [state.copy()]
    minimum = float(np.min(state[:3]))
    start = perf_counter()
    for a, b in zip(times[:-1], times[1:], strict=True):
        h, control = b - a, case.control_at(a)

        def rhs(value, applied=control):
            nonlocal minimum
            minimum = min(minimum, float(np.min(value[:3])))
            return derivative(case.parameters, applied, value, increments=False)

        k1 = rhs(state)
        k2 = rhs(state + h * k1 / 2)
        k3 = rhs(state + h * k2 / 2)
        k4 = rhs(state + h * k3)
        state = state + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        rhs(state)  # Also check each accepted endpoint, not only internal stages.
        history.append(state.copy())
    return (
        times,
        np.asarray(history),
        {
            "method": "independent_numpy_RK4_probe",
            "dt_s": dt,
            "accepted_steps": len(times) - 1,
            "minimum_trial_amount_fmol": minimum,
            "seconds": perf_counter() - start,
        },
    )


def trajectory_errors(parameters, actual, expected):
    return {
        "amount_fmol": float(np.max(np.abs(actual[:, :3] - expected[:, :3]), initial=0)),
        "leak_fmol": float(np.max(np.abs(actual[:, 3:6] - expected[:, 3:6]), initial=0)),
        "pump_cycles_fmol": float(np.max(np.abs(actual[:, 6] - expected[:, 6]), initial=0)),
        "voltage_V": float(
            np.max(
                np.abs(parameters.voltage(actual[:, :3]) - parameters.voltage(expected[:, :3])),
                initial=0,
            )
        ),
        "dissipation_pJ": float(np.max(np.abs(actual[:, 7] - expected[:, 7]), initial=0)),
    }


def sample_probe(case, times, values, samples, *, method="linear"):
    """Read-only interpolation experiment; Hermite slopes use interval-held controls."""
    samples = np.asarray(samples, dtype=float)
    if method not in ("linear", "hermite"):
        raise ValueError("Unknown probe observation method")
    if samples.ndim != 1 or not np.isfinite(samples).all() or np.any(np.diff(samples) < 0):
        raise ValueError("Probe samples must be finite and nondecreasing")
    if samples.size and (samples[0] < times[0] or samples[-1] > times[-1]):
        raise ValueError("Probe samples outside accepted trajectory")
    result = np.empty((len(samples), values.shape[1]))
    for index, time in enumerate(samples):
        left = min(np.searchsorted(times, time, side="right") - 1, len(times) - 2)
        if time == times[left] or time == times[left + 1]:
            result[index] = values[left if time == times[left] else left + 1]
            continue
        h = times[left + 1] - times[left]
        theta = (time - times[left]) / h
        delta = values[left + 1] - values[left]
        if method == "linear":
            result[index] = values[left] + theta * delta
        else:
            applied = case.control_at(times[left])
            f0 = derivative(case.parameters, applied, values[left], increments=False)
            f1 = derivative(case.parameters, applied, values[left + 1], increments=False)
            # Increment form preserves exactly constant intervals, unlike a
            # weighted sum of two large absolute amount vectors.
            result[index] = values[left] + theta * (
                h * f0
                + theta * (3 * delta - h * (2 * f0 + f1) + theta * (-2 * delta + h * (f0 + f1)))
            )
    return result


def local_spectrum(parameters, amount, control):
    """Finite-difference 3-ion Jacobian at one state, not a global stability bound."""
    state = initial_state(parameters, increments=True)
    state[:3] = amount - parameters.initial_amount
    step = 1e-6
    columns = []
    for coordinate in range(3):
        change = np.zeros(8)
        change[coordinate] = step
        columns.append(
            (
                derivative(parameters, control, state + change, increments=True)[:3]
                - derivative(parameters, control, state - change, increments=True)[:3]
            )
            / (2 * step)
        )
    eigenvalues = np.linalg.eigvals(np.column_stack(columns))
    return {
        "amount_probe_fmol": step,
        "eigenvalues_real_per_s": eigenvalues.real.tolist(),
        "eigenvalues_imag_per_s": eigenvalues.imag.tolist(),
        "spectral_radius_per_s": float(np.max(np.abs(eigenvalues))),
    }


def grand_potential_pJ(parameters, amount):
    n = np.asarray(amount)
    chemical = (
        MOL_PER_FMOL
        * R
        * parameters.temperature_K
        * np.sum(n * (np.log(n / parameters.volume_pL / parameters.bath_mM) - 1), axis=-1)
    )
    electrical = 0.5 * parameters.capacitance * parameters.voltage(n) ** 2
    return 1e12 * (chemical + electrical)


def balances(parameters, values):
    delta, leak, cycles = values[:, :3] - parameters.initial_amount, values[:, 3:6], values[:, 6]
    material = delta - leak - cycles[:, None] * NU
    energy_change = grand_potential_pJ(parameters, values[:, :3]) - grand_potential_pJ(
        parameters, parameters.initial_amount
    )
    supplied = -1e12 * MOL_PER_FMOL * parameters.atp_free_energy_J_per_mol * cycles
    return {
        "amount_fmol": float(np.max(np.abs(material), initial=0)),
        "charge_as_voltage_V": float(
            np.max(np.abs(material @ Z * CHARGE_PER_FMOL / parameters.capacitance), initial=0)
        ),
        "energy_pJ": float(np.max(np.abs(energy_change + values[:, 7] - supplied), initial=0)),
    }


def passive_equilibrium(parameters):
    """Independent finite-capacitance Donnan equilibrium with a maintained bath."""
    thermal = R * parameters.temperature_K / F

    def amounts(voltage):
        return (
            parameters.volume_pL * np.asarray(parameters.bath_mM) * np.exp(-Z * voltage / thermal)
        )

    def residual(voltage):
        return parameters.capacitance * (
            voltage - parameters.initial_voltage_V
        ) / CHARGE_PER_FMOL - Z @ (amounts(voltage) - parameters.initial_amount)

    voltage = brentq(residual, -0.5, 0.5, xtol=1e-15)
    return voltage, amounts(voltage)


def panel():
    base = Parameters()
    cases = [
        Case("baseline_1s", horizon=1.0),
        Case("baseline_10s"),
        Case("leak_only", controls=(Control(pump=0),)),
        Case("pump_only", controls=(Control(leak=(0, 0, 0)),)),
        Case("all_off", controls=(Control(leak=(0, 0, 0), pump=0),)),
        Case(
            "independent_controls",
            controls=(
                Control(),
                Control(2.03, pump=0),
                Control(3.11, (0, 1, 1), 0),
                Control(4.13, pump=0),
                Control(5.07),
            ),
        ),
        Case(
            "simultaneous_controls",
            controls=(Control(), Control(2.03, (0, 0, 0), 0), Control(5.07)),
        ),
        Case(
            "short_pulse",
            horizon=1.0,
            controls=(Control(pump=0), Control(0.203), Control(0.207, pump=0)),
        ),
    ]
    for multiplier in (0.5, 2.0):
        for name, changes in (
            ("area", {"area_m2": base.area_m2 * multiplier}),
            ("volume", {"volume_pL": base.volume_pL * multiplier}),
            (
                "permeability",
                {"permeability_m_per_s": tuple(p * multiplier for p in base.permeability_m_per_s)},
            ),
            (
                "pump_capacity",
                {"pump_capacity_fmol_per_s": base.pump_capacity_fmol_per_s * multiplier},
            ),
        ):
            cases.append(Case(f"{name}_{multiplier:g}x", parameters=replace(base, **changes)))
    cases.append(
        Case(
            "heterogeneous_leaks",
            parameters=replace(base, permeability_m_per_s=(2e-10, 5e-10, 2e-10)),
        )
    )
    cases.append(
        Case("reverse_drive", parameters=replace(base, atp_free_energy_J_per_mol=0.0), horizon=1.0)
    )
    return tuple(cases)
