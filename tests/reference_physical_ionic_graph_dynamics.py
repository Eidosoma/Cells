"""NUM-008 coupled CPU experiment; independent hyperbolic and Bernoulli paths.

No production Cells/JAX imports. Reuse only frozen local reference equations
and dimension-independent native-grid/dense-record helpers from NUM-006/007.
"""

import json
import math
from dataclasses import asdict
from functools import lru_cache
from time import monotonic

import numpy as np
from scipy.integrate import solve_ivp

from tests import physical_ionic_graph_numerical_data as data
from tests import reference_multispecies_dynamics as ionic
from tests import reference_voltage_gated_dynamics as channel

Case, Control, spec = data.Case, data.Control, data.spec
load_panel, initial_state, canonical = data.load_panel, data.initial_state, data.canonical
PANEL, PANEL_SHA256 = data.PANEL, data.PANEL_SHA256
ResourceLimit = ionic.ResourceLimit
candidate_grid, comparison_grid = ionic.candidate_grid, ionic.comparison_grid


class DomainViolation(ValueError):
    """An actual trial is outside the frozen physical graph domain."""


def domain(case, value, *, absolute=False):
    a = np.asarray(value, dtype=float)
    if a.shape != (case.size,) or not np.isfinite(a).all():
        raise DomainViolation("Nonfinite or incomplete graph trial")
    parts = case.layout.split(a)
    delta = parts["amount"] - case.initial_amount if absolute else parts["amount"]
    amounts = parts["amount"] if absolute else case.initial_amount + delta
    if not np.isfinite(amounts).all() or np.any(amounts <= 0):
        raise DomainViolation("Every graph trial amount must be positive and finite")
    voltages = np.array(
        [
            p.initial_voltage_V
            + data.QF
            / p.capacitance_F
            * math.fsum(z * d for z, d in zip(p.valence, delta[i], strict=True))
            for i, p in enumerate(case.graph.cells)
        ]
    )
    factor = np.asarray(case.graph.valence) * data.F / (data.R * case.graph.cells[0].temperature_K)
    local_x = voltages[:, None] * factor
    edge_x = np.asarray([voltages[a] - voltages[b] for a, b in case.endpoints])[:, None] * factor
    if not np.isfinite(local_x).all() or np.max(np.abs(local_x), initial=0) > 50:
        raise DomainViolation("Local dimensionless voltage outside domain")
    if not np.isfinite(edge_x).all() or np.max(np.abs(edge_x), initial=0) > 50:
        raise DomainViolation("Junction dimensionless voltage outside domain, even when off")
    for i in case.channel_cells:
        if not -0.120 <= voltages[i] <= 0.060:
            raise DomainViolation("Channel-owning cell voltage outside gate domain")
    gates = np.r_[parts["membrane_gate"].ravel(), parts["junction_gate"]]
    if np.any(gates < 0) or np.any(gates > 1):
        raise DomainViolation("Graph gate outside [0, 1]")
    if any(
        p.pump_id is None and parts["pump_cycles"][i] != 0 for i, p in enumerate(case.graph.cells)
    ):
        raise DomainViolation("Absent pump cannot own cycle history")
    return amounts, voltages, local_x, edge_x, gates


@lru_cache(maxsize=64)
def local_cases(case):
    result = []
    for i, p in enumerate(case.graph.cells):
        controls = tuple(
            ionic.Control(c.time_s, c.value.leak[i], c.value.pump[i]) for c in case.controls
        )
        if i in case.channel_cells:
            k = case.channel_cells.index(i)
            controls = tuple(
                channel.Control(c.time_s, c.value.leak[i], c.value.pump[i], c.value.channel[k])
                for c in case.controls
            )
            result.append(
                channel.Case(
                    case.id + "_" + p.cell_id,
                    p,
                    case.horizon_s,
                    controls,
                    case.graph.channels[k].channel,
                )
            )
        else:
            result.append(ionic.Case(case.id + "_" + p.cell_id, p, case.horizon_s, controls))
    return tuple(result)


def local_state(case, values, index):
    p = case.layout.split(values)
    result = np.r_[
        p["amount"][index],
        p["leak_transferred"][index],
        p["pump_cycles"][index],
        p["membrane_dissipated_energy_pJ"][index],
    ]
    if index in case.channel_cells:
        k = case.channel_cells.index(index)
        result = np.r_[result, p["membrane_gate"][k], p["channel_transferred"][k]]
    return result


def hyperbolic_rhs(case, control, state):
    """Same complete stage, old independent local laws, separately expressed edges."""
    amount, voltage, _, edge_x, _ = domain(case, state)
    result = np.zeros(case.size)
    out, current = case.layout.split(result), case.layout.split(state)
    count = case.layout.s
    for i, local in enumerate(local_cases(case)):
        if i in case.channel_cells:
            k = case.channel_cells.index(i)
            held = channel.Control(
                control.time_s,
                control.value.leak[i],
                control.value.pump[i],
                control.value.channel[k],
            )
            rate = channel.hyperbolic_rhs(local, held, local_state(case, state, i))
            out["membrane_gate"][k] = rate[2 * count + 2 : 2 * count + 4]
            out["channel_transferred"][k] = rate[-1]
        else:
            held = ionic.Control(control.time_s, control.value.leak[i], control.value.pump[i])
            rate = ionic.hyperbolic_rhs(local, held, local_state(case, state, i))
        out["amount"][i], out["leak_transferred"][i] = rate[:count], rate[count : 2 * count]
        out["pump_cycles"][i], out["membrane_dissipated_energy_pJ"][i] = rate[
            2 * count : 2 * count + 2
        ]
    contributions = [
        [[float(out["amount"][i, s])] for s in range(count)] for i in range(case.layout.n)
    ]
    concentrations = amount / np.asarray([p.volume_pL for p in case.graph.cells])[:, None]
    rt = data.R * case.graph.cells[0].temperature_K
    for j, (edge, (a, b)) in enumerate(zip(case.graph.junctions, case.endpoints, strict=True)):
        x, gate, dv = edge_x[j], current["junction_gate"][j], voltage[a] - voltage[b]
        f = np.ones(count)
        nonzero = x != 0
        f[nonzero] = x[nonzero] / (2 * np.tanh(x[nonzero] / 2))
        ca, cb = concentrations[a], concentrations[b]
        p, r = np.asarray(edge.permeability_m_per_s), np.asarray(edge.residual_fraction)
        flow = (
            edge.area_m2
            * p
            * control.value.junction[j]
            * (r + (1 - r) * gate)
            / 1e-15
            * ((ca - cb) * f + (ca + cb) * x / 2)
        )
        # log(2*cosh(a*dv))-a*Vh, then reciprocal-logistic, avoids overflow.
        av = edge.sensitivity_per_V * dv
        log_term = float(np.logaddexp(av, -av)) - edge.sensitivity_per_V * edge.half_voltage_V
        target = math.exp(-float(np.logaddexp(0.0, log_term)))
        out["junction_gate"][j] = (target - gate) / edge.tau_s
        out["junction_transferred"][j] = flow
        mu = rt * np.log(cb / ca) - np.asarray(case.graph.valence) * data.F * dv
        out["junction_dissipated_energy_pJ"][j] = -1e-3 * math.fsum(flow * mu)
        for s, value in enumerate(flow):
            contributions[a][s].append(-float(value))
            contributions[b][s].append(float(value))
    for i in range(case.layout.n):
        for s in range(count):
            out["amount"][i, s] = math.fsum(contributions[i][s])
    if not np.isfinite(result).all():
        raise DomainViolation("Nonfinite independent graph derivative")
    return result


def bernoulli_rhs(case, control, state):
    domain(case, state, absolute=True)
    return case.layout.pack(spec.evaluate(case.graph, case.layout.state(state), control.value).rate)


class Budget(ionic.Budget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.max_edge_x = 0.0
        self.min_gate, self.max_gate = 1.0, 0.0
        self.min_voltage, self.max_voltage = math.inf, -math.inf
        self.min_channel_voltage, self.max_channel_voltage = math.inf, -math.inf

    def rhs(self, function, case, control, state, *, absolute=False):
        self.check()
        self.calls += 1
        if self.calls > self.max_calls:
            raise ResourceLimit("Attempt RHS budget exhausted, including Jacobian probes")
        amount, voltage, local_x, edge_x, gates = domain(case, state, absolute=absolute)
        self.minimum_amount = min(self.minimum_amount, float(np.min(amount)))
        self.max_abs_x = max(self.max_abs_x, float(np.max(np.abs(local_x), initial=0)))
        self.max_edge_x = max(self.max_edge_x, float(np.max(np.abs(edge_x), initial=0)))
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
            "max_trial_abs_x": self.max_abs_x,
            "max_trial_edge_abs_x": self.max_edge_x,
            "trial_gate_range": [min(self.min_gate, self.max_gate), self.max_gate],
            "trial_voltage_range_V": [self.min_voltage, self.max_voltage],
            "trial_channel_voltage_range_V": (
                [self.min_channel_voltage, self.max_channel_voltage]
                if self.min_channel_voltage != math.inf
                else None
            ),
        }


def sample_record(case, arrays, kind, samples):
    # The unchanged dense helper needs only extent and canonical amount anchors.
    # Supply an explicit flattened coordinate adapter, not biological species IDs.
    from types import SimpleNamespace

    adapter = SimpleNamespace(
        size=case.size,
        species_count=case.layout.amount_count,
        parameters=SimpleNamespace(initial_amount_fmol=case.initial_amount.ravel()),
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
        spec.ionic.number(settings[name], name, positive=True)
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
        if len(times) + len(result.t) - 2 > ionic.MAX_STEPS:
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
