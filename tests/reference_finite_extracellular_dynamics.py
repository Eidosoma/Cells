"""NUM-009 independent hyperbolic/reduced references and full-increment RK4.

Reuse only dimension-independent native/dense helpers. No production Cells/JAX.
"""

import json
import math
from dataclasses import asdict
from time import monotonic
from types import SimpleNamespace

import numpy as np
from scipy.integrate import solve_ivp

from tests import finite_extracellular_numerical_data as data
from tests import reference_multispecies_dynamics as ionic

Case, Control, spec = data.Case, data.Control, data.spec
initial_state, load_panel = data.initial_state, data.load_panel
ResourceLimit = ionic.ResourceLimit
candidate_grid, comparison_grid = ionic.candidate_grid, ionic.comparison_grid


class DomainViolation(ValueError):
    """An actual stage is outside the unchanged physical domain."""


def domain(case, value):
    a = np.asarray(value, dtype=float)
    if a.shape != (case.size,) or not np.isfinite(a).all():
        raise DomainViolation("Nonfinite or incomplete finite-world trial")
    p = case.layout.split(a)
    try:
        physical = data.physical_state(case, a)
        spec.validate_state(case.world, physical)
    except ValueError as error:
        raise DomainViolation(str(error)) from error
    amounts = case.initial_amount + p["amount"]
    outside = case.outside_initial + p["extracellular_amount"]
    w = case.world
    voltage = np.array(
        [
            m.initial_voltage_V
            + data.QF
            / m.capacitance_F
            * math.fsum(z * d for z, d in zip(w.valence, p["amount"][i], strict=True))
            for i, m in enumerate(w.membranes)
        ]
    )
    factor = np.asarray(w.valence) * data.F / (data.R * w.temperature_K)
    xs = voltage[:, None] * factor
    edge_x = np.asarray([voltage[a] - voltage[b] for a, b in case.endpoints])[:, None] * factor
    gates = np.r_[p["membrane_gate"].ravel(), p["junction_gate"]]
    charge = data.QF * math.fsum(
        z * math.fsum((p["extracellular_amount"][s], *p["amount"][:, s]))
        for s, z in enumerate(w.valence)
    )
    if not np.isfinite(xs).all() or np.max(np.abs(xs), initial=0) > 50:
        raise DomainViolation("Local dimensionless voltage outside domain")
    if not np.isfinite(edge_x).all() or np.max(np.abs(edge_x), initial=0) > 50:
        raise DomainViolation("Junction dimensionless voltage outside domain, even when off")
    if any(not -0.120 <= voltage[i] <= 0.060 for i in case.channel_cells):
        raise DomainViolation("Channel-owning cell voltage outside gate domain")
    if abs(charge) > spec.CHARGE_TOLERANCE_C:
        raise DomainViolation("Increment countercharge constraint violated")
    return (
        amounts,
        outside,
        voltage,
        xs,
        edge_x,
        gates,
        max(abs(charge), abs(spec.countercharge_increment(w, physical))),
    )


def hyperbolic_rhs(case, control, state):
    """Independent current-outside equations; never substitute a bath parameter."""
    amount, outside, voltage, xs, edge_x, _, _ = domain(case, state)
    w, layout = case.world, case.layout
    result = np.zeros(case.size)
    out, p = layout.split(result), layout.split(state)
    ci = amount / np.asarray([c.volume_pL for c in w.cells])[:, None]
    co = outside / w.extracellular.volume_pL
    rt, z = data.R * w.temperature_K, np.asarray(w.valence)
    membrane = np.zeros_like(ci)
    for i, m in enumerate(w.membranes):
        x = xs[i]
        b = np.ones(layout.s)
        mask = x != 0
        b[mask] = x[mask] / (2 * np.tanh(x[mask] / 2))
        base = (co - ci[i]) * b - (co + ci[i]) * x / 2
        leak = m.area_m2 * np.asarray(m.permeability_m_per_s) * control.value.leak[i] / 1e-15 * base
        mu = rt * np.log(ci[i] / co) + z * data.F * voltage[i]
        nu, cycles, affinity = np.zeros(layout.s), 0.0, 0.0
        if m.pump is not None:
            nu = np.asarray(m.pump.stoichiometry)
            affinity = m.pump.drive_J_per_mol + math.fsum(nu * mu)
            cycles = (
                m.pump.capacity_fmol_per_s * control.value.pump[i] * np.tanh(-affinity / (2 * rt))
            )
        out["leak_transferred"][i] = leak
        out["pump_cycles"][i] = cycles
        membrane[i] = leak + nu * cycles
        dissipated = -1e-3 * (math.fsum(leak * mu) + cycles * affinity)
        if i in case.channel_cells:
            k = case.channel_cells.index(i)
            ch = w.channels[k]
            mg, hg = p["membrane_gate"][k]
            mv = 1000 * voltage[i]
            mi = 1 / (1 + math.exp(-(mv + 6) / 6.4))
            hi = 1 / (1 + math.exp((mv + 25.3) / 3.5))
            out["membrane_gate"][k] = (
                1000 * (mi - mg) / (8.33 - 0.1163 * mv),
                1000 * (hi - hg) / (1620 - 15.5 * mv),
            )
            s = w.species_ids.index(ch.species_id)
            flow = (
                m.area_m2
                * ch.max_permeability_m_per_s
                * ch.abundance
                * control.value.channel[k]
                * mg
                * hg
                / 1e-15
                * base[s]
            )
            out["channel_transferred"][k] = flow
            membrane[i, s] += flow
            dissipated -= 1e-3 * flow * mu[s]
        out["membrane_dissipated_energy_pJ"][i] = dissipated
    terms = [[[float(x)] for x in row] for row in membrane]
    # Owned membrane routes only: junction terms never enter this reduction.
    out["extracellular_amount"][:] = [-math.fsum(membrane[:, s]) for s in range(layout.s)]
    for j, (edge, (a, b)) in enumerate(zip(w.junctions, case.endpoints, strict=True)):
        x, gate, dv = edge_x[j], p["junction_gate"][j], voltage[a] - voltage[b]
        factor = np.ones(layout.s)
        mask = x != 0
        factor[mask] = x[mask] / (2 * np.tanh(x[mask] / 2))
        residual = np.asarray(edge.residual_fraction)
        flow = (
            edge.area_m2
            * np.asarray(edge.permeability_m_per_s)
            * control.value.junction[j]
            * (residual + (1 - residual) * gate)
            / 1e-15
            * ((ci[a] - ci[b]) * factor + (ci[a] + ci[b]) * x / 2)
        )
        av = edge.sensitivity_per_V * dv
        log_term = float(np.logaddexp(av, -av)) - edge.sensitivity_per_V * edge.half_voltage_V
        target = math.exp(-float(np.logaddexp(0.0, log_term)))
        out["junction_gate"][j] = (target - gate) / edge.tau_s
        out["junction_transferred"][j] = flow
        mu = rt * np.log(ci[b] / ci[a]) - z * data.F * dv
        out["junction_dissipated_energy_pJ"][j] = -1e-3 * math.fsum(flow * mu)
        for s, f in enumerate(flow):
            terms[a][s].append(-float(f))
            terms[b][s].append(float(f))
    out["amount"][:] = [[math.fsum(row) for row in cell] for cell in terms]
    if not np.isfinite(result).all():
        raise DomainViolation("Nonfinite independent finite-world derivative")
    return result


def bernoulli_rhs(case, control, state):
    domain(case, state)
    return case.layout.pack(
        spec.evaluate(case.world, data.physical_state(case, state), control.value).rate
    )


class Budget(ionic.Budget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.min_outside = math.inf
        self.max_edge_x = self.max_charge = 0.0
        self.min_gate, self.max_gate = 1.0, 0.0
        self.min_voltage, self.max_voltage = math.inf, -math.inf
        self.min_channel_voltage, self.max_channel_voltage = math.inf, -math.inf

    def rhs(self, function, case, control, state):
        self.check()
        self.calls += 1
        if self.calls > self.max_calls:
            raise ResourceLimit("Attempt RHS budget exhausted, including Jacobian probes")
        amount, outside, voltage, local_x, edge_x, gates, charge = domain(case, state)
        self.minimum_amount = min(self.minimum_amount, float(np.min(amount)))
        self.min_outside = min(self.min_outside, float(np.min(outside)))
        self.max_abs_x = max(self.max_abs_x, float(np.max(np.abs(local_x), initial=0)))
        self.max_edge_x = max(self.max_edge_x, float(np.max(np.abs(edge_x), initial=0)))
        self.max_charge = max(self.max_charge, charge)
        self.min_voltage = min(self.min_voltage, float(np.min(voltage)))
        self.max_voltage = max(self.max_voltage, float(np.max(voltage)))
        for i in case.channel_cells:
            self.min_channel_voltage = min(self.min_channel_voltage, float(voltage[i]))
            self.max_channel_voltage = max(self.max_channel_voltage, float(voltage[i]))
        self.min_gate = min(self.min_gate, float(np.min(gates, initial=1)))
        self.max_gate = max(self.max_gate, float(np.max(gates, initial=0)))
        return function(case, control, state)

    def summary(self):
        return {
            "rhs_calls": self.calls,
            "minimum_trial_amount_fmol": self.minimum_amount,
            "minimum_trial_outside_amount_fmol": self.min_outside,
            "max_trial_countercharge_C": self.max_charge,
            "max_trial_abs_x": self.max_abs_x,
            "max_trial_edge_abs_x": self.max_edge_x,
            "trial_gate_range": [min(self.min_gate, self.max_gate), self.max_gate],
            "trial_voltage_range_V": [self.min_voltage, self.max_voltage],
            "trial_channel_voltage_range_V": [self.min_channel_voltage, self.max_channel_voltage]
            if self.min_channel_voltage != math.inf
            else None,
        }


def sample_record(case, arrays, kind, samples):
    # Zero amount-count adapter: all stored coordinates are already increments.
    adapter = SimpleNamespace(
        size=case.size, species_count=0, parameters=SimpleNamespace(initial_amount_fmol=np.empty(0))
    )
    return ionic.sample_record(adapter, arrays, kind, samples)


def recorded(case, times, states, coefficients, degrees, shifts, denominators):
    steps = len(times) - 1
    return ionic.recorded(
        times,
        states,
        np.asarray(coefficients).reshape(steps, case.size, 6),
        degrees,
        np.asarray(shifts).reshape(steps, 5),
        np.asarray(denominators).reshape(steps, 5),
    )


def integrate_reference(case, settings, *, budget=None):
    if settings["method"] not in ("Radau", "BDF"):
        raise ValueError("Unsupported independent solver")
    for name in ("rtol", "atol", "max_step_s"):
        spec.ion.number(settings[name], name, positive=True)
    budget = Budget() if budget is None else budget
    started = monotonic()
    state = initial_state(case)[: case.layout.reduced_size]
    times, states, coeffs, degrees, shifts, denominators = (
        [0.0],
        [data.expand(case, state)],
        [],
        [],
        [],
        [],
    )
    totals = {"nfev": 0, "njev": 0, "nlu": 0}
    for slot, control in enumerate(case.controls):
        end = case.controls[slot + 1].time_s if slot + 1 < len(case.controls) else case.horizon_s
        if end == control.time_s:
            continue

        def rhs(time, value, held=control):
            full = data.expand(case, value)
            return budget.rhs(hyperbolic_rhs, case, held, full)[: case.layout.reduced_size]

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
        if len(times) + len(result.t) - 2 > ionic.MAX_STEPS:
            raise ResourceLimit("Accepted-step budget exhausted")
        full = data.expand(case, result.y.T)
        for value in full:
            domain(case, value)
        times.extend(result.t[1:])
        states.extend(full[1:])
        for polynomial in result.sol.interpolants:
            c = np.zeros((case.layout.reduced_size, 6))
            shift, denominator = np.zeros(5), np.ones(5)
            if settings["method"] == "Radau":
                degree = polynomial.Q.shape[1]
                c[:, 0], c[:, 1 : degree + 1] = polynomial.y_old, polynomial.Q
            else:
                degree = polynomial.order
                c[:, : degree + 1] = polynomial.D.T
                shift[:degree], denominator[:degree] = polynomial.t_shift, polynomial.denom
            if not 1 <= degree <= 5:
                raise ValueError("Unexpected pinned SciPy dense degree")
            coeffs.append(data.expand(case, c.T).T)
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
    started, state = monotonic(), initial_state(case)
    history, times, coeffs, rejection = [state.copy()], [0.0], [], None
    for left, right in zip(mesh[:-1], mesh[1:], strict=True):
        step, control = right - left, case.control_at(float(left))

        def rhs(value, label, time, held=control, start=left, end=right):
            nonlocal rejection
            try:
                return budget.rhs(bernoulli_rhs, case, held, value)
            except DomainViolation as error:
                rejection = {
                    "reason": str(error),
                    "stage": label,
                    "time_s": float(time),
                    "interval_left_s": float(start),
                    "interval_right_s": float(end),
                    "increment_state": [
                        float(v) if math.isfinite(v) else str(float(v)) for v in value
                    ],
                    "control": json.loads(json.dumps(asdict(held))),
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
