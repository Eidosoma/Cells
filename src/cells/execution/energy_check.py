"""The step-doubled energy check: FR-18's criterion X2, the engine's opt-in energy check (D224).

A definition selects it with execution.energy_check (definitions/energy_check_spec.py), and
registered and judged runs must. The rule is the registration's,
docs/FR18_CRITERION_X_2026-11-18.md, and this module follows that note's implementation
section. validation/energy_step_doubling/ holds the registered harness, the check's independent
reference.

**Why it works.** The energy residual R is constant along an exact trajectory, so each step's change
in R is that step's own local error. For ARS(2,2,2) the error scales as dt^3, and two half steps
from the same state carry a quarter of it. A misbooking scales as dt per step and appears whole in
both. So the step doubling subtracts the integration error from the residual, and what remains
holds every misbooking at its full size.

**Each accepted step** is also taken as two half steps from the same accepted state with the step's
held control (doubled, at the model's step function, so a composite's operators are included). On
the device the step gives, at the full step's end, the residual R, the flows F and the magnitude
M = F + T + O, and R'' at the half steps' end. The per-step check is then decided on the host from
those scalars and the run-level record, in the same code for host and device row checks:
- held steps: an operator's event step or halves the step's validity refuses (rule 1), and an
  out-of-band counted step (q outside [3.5, 4.6]); a held step carries a = 0 and must meet today's
  bound at its row;
- counted steps: not held under rule 1, with |d''| > 1000 eps M; q = d / d'';
- a = 4/3 (d - d''); C_k = R_k - sum(a) - sum(held d); floor_k = 2.5 eps k M_k;
- refused at the row: |C_k| > floor_k + sum|a| / 16, a held step above today's bound, or the
  registration's cap, sum|a| > cap x F_k + floor_k (form B, D224 as amended);
- at the run's end, decided over the whole run as registered: the median of the counted q in
  [3.5, 4.6] (none counted: at rounding, not applied), and at most max(8, ceil(0.02 |Q|))
  out-of-band held steps.
In an X2 run today's energy bound is not applied as a verdict (surface_pump.checked_rows and
surface_pump_checks.row_checks, static switches); the energy ledger is still evaluated and
reported, and every other ledger is checked as today.

**The run-level record** (EnergyCheckRecord) rides in the checkpoint (Checkpoint.energy_check):
R at the checkpoint's row, the sums of a, |a| and the held steps' d, every counted q, the
out-of-band held count and the running maxima. Every sum is carried as a left fold, so a run split
into windows or restarted from a checkpoint gives exactly what one segment gives. A checkpoint's
record binds its state: the state's residual, evaluated again, must lie within the row's floor of
the record's R (binding below). The binding is the only energy guard on a loaded checkpoint, since
an edited row's jump would enter the next step's d and d'' alike, be held as out of band, and pass
inside the held steps' sum. It holds within the floor, not exactly, because the residual inside the
rollout and the residual evaluated alone are different compiled programs (they differ by a few
tenths of eps M).

Scope: ARS(2,2,2) only, on the scalar runner and its windows (cells.execution.runner.run,
cells.execution.windows); the batch and vector paths and the projective mode refuse it. The
evidence on FR-8's worlds stops at dt = 5 ms. The cost is two extra half steps and two residual
evaluations per step.
"""

import math
from dataclasses import dataclass, field, replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions.specs import ConfigError, digest
from cells.execution.errors import NumericalError

# The models this check reads (surface_tissue, surface_pump) are imported where it runs, so a
# process that only imports the runner, with the check off, imports what it did before X2.

KAPPA = 1.0 / 16.0  # X2's allowance on the integration error.
BAND = (3.5, 4.6)  # The order condition's band, and X2's out-of-band test.
COUNT_FACTOR = 1000.0  # A counted step: |d''| > 1000 eps M.
HELD_CAP = (8, 0.02)  # At most max(8, ceil(0.02 |Q|)) out-of-band held steps.
EPS = float(np.finfo(np.float64).eps)
VALUES_PER_STEP = 5  # R, R'', F, M and the halves' validity, kept per step on the device.
MESSAGE = "Step-doubled energy check failed: "
DIAGNOSTICS = (
    "max_step_doubled_energy_ratio",
    "max_integration_error_relative",
    "max_held_step_energy_ratio",
)


class StepDoubledConstants(NamedTuple):
    """The device row checks' constants in an X2 run: today's two leaves (row_checks reads them by
    name) and the registration's cap. Its type is the static switch: APPLY_ENERGY_BOUND, a class
    attribute and so no leaf, tells row_checks that today's energy bound is not a verdict here, so
    CheckConstants, crossrev's bindings and world_key do not move when X2 is off."""

    material_atol: object
    energy_rtol: object
    integration_error_cap: object

    APPLY_ENERGY_BOUND = False


@dataclass(frozen=True, eq=False)
class EnergyCheckRecord:
    """X2's run-level record at a checkpoint's row (the module docstring)."""

    residual: float  # R at the checkpoint's row.
    sum_a: float
    sum_abs_a: float
    sum_held_d: float
    counted_q: np.ndarray  # Every counted step's q, in step order (read-only).
    held_out_of_band: int
    max_ratio: float = 0.0
    max_integration_error: float = 0.0
    max_held_ratio: float = 0.0
    last_integration_error: float = 0.0
    # The segment that ended at this row (EnergyRows), so RunResult.checkpoint_at gives the record
    # at any of its rows; None at a run's first row, after a load, or after a segment without
    # steps. Never stored or compared.
    rows: object = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        q = np.array(self.counted_q, dtype=np.float64).reshape(-1)
        q.setflags(write=False)
        object.__setattr__(self, "counted_q", q)
        scalars = (
            self.residual,
            self.sum_a,
            self.sum_abs_a,
            self.sum_held_d,
            self.max_ratio,
            self.max_integration_error,
            self.max_held_ratio,
            self.last_integration_error,
        )
        if not all(isinstance(v, float) and math.isfinite(v) for v in scalars) or not np.all(
            np.isfinite(q)
        ):
            raise ConfigError("A step-doubled energy record holds finite floats only")
        if type(self.held_out_of_band) is not int or self.held_out_of_band < 0:
            raise ConfigError("A step-doubled energy record's held count is a nonnegative integer")

    def same(self, other):
        """Exact equality, field by field (the restart and round-trip checks)."""
        return (
            isinstance(other, EnergyCheckRecord)
            and all(
                getattr(self, k) == getattr(other, k)
                for k in (
                    "residual",
                    "sum_a",
                    "sum_abs_a",
                    "sum_held_d",
                    "held_out_of_band",
                    "max_ratio",
                    "max_integration_error",
                    "max_held_ratio",
                    "last_integration_error",
                )  # fmt: skip
            )
            and self.counted_q.tobytes() == other.counted_q.tobytes()
        )

    def to_dict(self):
        """The record's scalars (its counted q are stored beside it as an array)."""
        return dict(
            residual=self.residual,
            sum_a=self.sum_a,
            sum_abs_a=self.sum_abs_a,
            sum_held_d=self.sum_held_d,
            held_out_of_band=self.held_out_of_band,
            max_ratio=self.max_ratio,
            max_integration_error=self.max_integration_error,
            max_held_ratio=self.max_held_ratio,
            last_integration_error=self.last_integration_error,
        )

    @classmethod
    def from_dict(cls, data, counted_q):
        names = (*cls.__dataclass_fields__,)
        expected = set(names) - {"counted_q", "rows"}
        if not isinstance(data, dict) or set(data) != expected:
            raise ConfigError("Invalid step-doubled energy record fields")
        floats = {k: data[k] for k in expected if k != "held_out_of_band"}
        if not all(type(v) is float for v in floats.values()):
            raise ConfigError("A step-doubled energy record holds finite floats only")
        return cls(counted_q=counted_q, **data)


@dataclass(frozen=True, eq=False)
class EnergyRows:
    """A segment's record after each of its accepted steps: the record it started from (without its
    own rows, so no chain of segments is kept) and the per-step arrays check_segment formed. The
    record after j steps is the one a run split at that row carries, bit for bit."""

    start: EnergyCheckRecord
    residual: np.ndarray
    sum_a: np.ndarray
    sum_abs_a: np.ndarray
    sum_held_d: np.ndarray
    counted: np.ndarray
    q: np.ndarray
    out_band: np.ndarray
    ratio: np.ndarray
    relative: np.ndarray
    held_ratio: np.ndarray

    def record_at(self, j):
        """The record after the segment's first j accepted steps (0: the one it started from)."""
        if j == 0:
            return self.start
        s = self.start
        head = slice(0, j)
        return EnergyCheckRecord(
            residual=float(self.residual[j - 1]),
            sum_a=float(self.sum_a[j - 1]),
            sum_abs_a=float(self.sum_abs_a[j - 1]),
            sum_held_d=float(self.sum_held_d[j - 1]),
            counted_q=np.concatenate((s.counted_q, self.q[head][self.counted[head]])),
            held_out_of_band=s.held_out_of_band + int(np.count_nonzero(self.out_band[head])),
            max_ratio=max(s.max_ratio, float(np.max(self.ratio[head]))),
            max_integration_error=max(s.max_integration_error, float(np.max(self.relative[head]))),
            max_held_ratio=max(s.max_held_ratio, float(np.max(self.held_ratio[head]))),
            last_integration_error=float(self.relative[j - 1]),
            rows=self,
        )


def selected(spec):
    return getattr(spec, "energy_check", None) is not None


# ------------------------------------------------------------------ the model's terms


def _ledger_model(model):
    """The model whose ledger path the check reads: a frozen family's composition, else itself."""
    if hasattr(model, "composition") and hasattr(model, "module"):
        return model.composition
    return model


def require_support(model):
    """Refuse a model that lacks the step and residual functions the wrapper calls."""
    base = _ledger_model(model)
    need = ["checked_step", "device_balances"]
    need += (
        ["inner", "inner_magnitudes", "_adjusted", "_live_retiring"]
        if hasattr(base, "inner_balances")
        else ["channel_magnitudes", "ledger_limits"]
    )
    missing = [n for n in need if not hasattr(base if n != "checked_step" else model, n)]
    if missing:
        raise ConfigError(
            "execution.energy_check needs a model with " + ", ".join(missing) + " (refused)"
        )


def stored_terms_abs(state, p, *, xp):
    """T: the tissue ledger's stored terms (surface_tissue.balances) as absolute values, element
    by element: each inventory element's two chemical terms, cytosol and outside, and each patch's
    electric term; non-finite elements count as 0 (the registered recorder's form)."""
    from cells.laws.electrochemistry import R as GAS_R
    from cells.models import surface_tissue as tissue

    _, _, dv = tissue.capacitor_change(state, p, xp=xp)
    scale = 1e-3 * GAS_R * p.temperature
    total = 0.0
    for delta, anchor, volume, mask in (
        (state.amount_increment, p.amount_reference, p.volume, p.active),
        (state.extracellular_amount_increment, p.extracellular_amount_reference,
         p.extracellular_volume, p.outside_active),
    ):  # fmt: skip
        a = xp.where(mask, anchor, 1.0)
        first = xp.abs(scale * delta * (xp.log(a / volume) - 1))
        second = xp.abs(scale * (a + delta) * xp.log1p(delta / a))
        total = total + xp.sum(xp.where(xp.isfinite(first), first, 0.0))
        total = total + xp.sum(xp.where(xp.isfinite(second), second, 0.0))
    electric = xp.abs(
        0.5e12 * p.membrane_capacitance * dv * (2 * p.initial_membrane_voltage_V + dv)
    )
    return total + xp.sum(xp.where(xp.isfinite(electric), electric, 0.0))


def _kinds_stored_abs(structure, row, p, *, xp):
    """The declared kinds' |stored_pJ| ledger terms (0 without kinds)."""
    if structure is None or not getattr(structure, "kinds", ()):
        return 0.0
    from cells.models import surface_pump_v3

    total = 0.0
    for kind in surface_pump_v3._kinds(structure):
        if kind.ledger_terms is not None:
            terms = kind.ledger_terms(row, p, xp=xp)
            if "stored_pJ" in terms:
                total = total + xp.sum(xp.abs(terms["stored_pJ"]))
    return total


def _magnitude(value, *, xp):
    return 0.0 if value is None else xp.sum(xp.abs(value))


def terms(model, spec, layout):
    """(terms, residual): device functions of a row and the layout. terms gives (R, F, M) at the
    row, as the registered recorder forms them (R the energy ledger as the device checks evaluate
    it; F its flows; M = F + T + O, T the stored terms, O the model's own energy magnitude and the
    kinds' |stored_pJ|); residual gives R alone (the half steps' end)."""
    base = _ledger_model(model)
    tol = np.asarray(spec.execution.material_balance_atol_fmol, dtype=np.float64)
    rtol = float(base.ENERGY_RTOL[spec.execution.solver])
    if hasattr(base, "inner_balances"):  # A composite: its inner ledgers with the operators.
        retiring = bool(base._live_retiring(layout))  # Static: a layout shape, as checks read it.
        index = base.inner.LEDGERS.index("energy")
        structure = getattr(base.inner, "structure", None)

        def row_terms(row, p):
            adjusted = base._adjusted(row, p, xp=jnp) if retiring else row
            energy = base.device_balances(row, p)["energy"]
            if retiring:
                m = base.inner_magnitudes(adjusted, p, xp=jnp, adjust=False)
            else:
                m = base.inner_magnitudes(row, p, xp=jnp)
            flows, _ = base.inner.ledger_limits(
                adjusted, p, tol, rtol, steps=0, magnitudes=m, xp=jnp
            )
            inner_row, inner_p = base.inner.inner_state(adjusted), base.inner.inner_layout(p)
            other = _magnitude(m[index], xp=jnp) + _kinds_stored_abs(
                structure, inner_row, inner_p, xp=jnp
            )
            return energy, flows, flows + stored_terms_abs(inner_row, inner_p, xp=jnp) + other

    else:  # @3 alone.
        index = base.LEDGERS.index("energy")
        structure = getattr(base, "structure", None)

        def row_terms(row, p):
            energy = base.device_balances(row, p)["energy"]
            m = base.channel_magnitudes(row, p, xp=jnp)
            flows, _ = base.ledger_limits(row, p, tol, rtol, steps=0, magnitudes=m, xp=jnp)
            other = _magnitude(m[index], xp=jnp) + _kinds_stored_abs(structure, row, p, xp=jnp)
            return energy, flows, flows + stored_terms_abs(row, p, xp=jnp) + other

    def residual(row, p):
        return base.device_balances(row, p)["energy"]

    return row_terms, residual


# ------------------------------------------------------------------ the step-doubling wrapper


def doubled(checked_step, row_terms, residual):
    """The model's checked step taken whole and as two half steps from the same accepted state
    with the step's held control: (the full step's state, its validity, (R, R'', F, M at the full
    step's end, the halves' validity))."""

    def step(state, dt, control, p, active):
        full, ok = checked_step(state, dt, control, p, active)
        half, first = checked_step(state, 0.5 * dt, control, p, active)
        half, second = checked_step(half, 0.5 * dt, control, p, active)
        energy, flows, magnitude = row_terms(full, p)
        return full, ok, (energy, residual(half, p), flows, magnitude, first & second)

    return step


_STEPS = {}  # (id(model), the definition's digest, retiring) -> (model, its doubled step).
_STEPS_KEPT = 16


def doubled_step(model, spec, layout):
    """doubled() for this model, definition and layout, one object per definition: a run
    restarted, or run again, in this process reuses its compiled rollout, as today's rollouts do
    (their static arguments are the model's own functions). The key holds everything the step's
    closures read: the model, the definition (its tolerances and solver) and whether the layout
    has a live retiring operator."""
    base = _ledger_model(model)
    retiring = bool(base._live_retiring(layout)) if hasattr(base, "inner_balances") else False
    key = (id(model), digest(spec.to_dict()), retiring)
    kept = _STEPS.get(key)
    if kept is not None and kept[0] is model:
        return kept[1]
    step = doubled(model.checked_step, *terms(model, spec, layout))
    if len(_STEPS) >= _STEPS_KEPT:
        _STEPS.pop(next(iter(_STEPS)))
    _STEPS[key] = (model, step)
    return step


def _idle(value):
    nan = jnp.full((), jnp.nan)
    return (nan, nan, nan, nan, jnp.asarray(False))


def _discrete_rollout(state, steps, controls, parameters, active, step):
    def advance(carry, inputs):
        current, previous_ok = carry
        dt, control = inputs
        updated, ok, values = jax.lax.cond(
            previous_ok,
            lambda y: step(y, dt, control, parameters, active),
            lambda y: (y, jnp.array(False), _idle(y)),
            current,
        )
        return (updated, ok), (updated, ok, values)

    (final, _), (history, valid, values) = jax.lax.scan(
        advance, (state, jnp.array(True)), (steps, controls)
    )
    return final, history, valid, values


def _window_rollout(state, steps, controls, parameters, active, enabled, step):
    """runner._window_rollout's fixed shape, the checked step doubled; disabled slots idle."""

    def advance(carry, inputs):
        current, previous_ok = carry
        dt, control, real_step = inputs
        updated, ok, values = jax.lax.cond(
            real_step & previous_ok,
            lambda y: step(y, dt, control, parameters, active),
            lambda y: (y, previous_ok, _idle(y)),
            current,
        )
        return (updated, ok), (updated, ok, values)

    (final, _), (history, valid, values) = jax.lax.scan(
        advance, (state, jnp.array(True)), (steps, controls, enabled)
    )
    return final, history, valid, values


compiled_discrete_rollout = jax.jit(_discrete_rollout, static_argnums=(5,))
compiled_window_rollout = jax.jit(_window_rollout, static_argnums=(6,))
eager_discrete_rollout = _discrete_rollout


def trace_bytes(spec, steps):
    """The check's own per-step values on the device, with the estimate's margin of 2."""
    return 2 * 8 * VALUES_PER_STEP * (steps + 1) if selected(spec) else 0


def event_mask(spec, times, model):
    """Rule 1's event steps among a segment's steps: those starting where an operator's record
    changes (the registered harness's event_steps, read from the definition the model checks)."""
    definition = model.module.composite(spec) if hasattr(model, "module") else spec
    marks, previous = set(), None
    for change in getattr(definition.experiment, "changes", ()):
        operators = getattr(change, "operators", None)
        if operators is not None and previous is not None and operators != previous:
            marks.add(float(change.time))
        previous = operators
    return np.array([float(t) in marks for t in times[:-1]], dtype=bool)


def initial_record(residual_value):
    return EnergyCheckRecord(float(residual_value), 0.0, 0.0, 0.0, np.zeros(0), 0)


def residual_at(model, spec, checkpoint):
    """R at a checkpoint's row, on its device (the run's first record)."""
    _, residual = terms(model, spec, checkpoint.layout)
    params = model.parameters(spec, checkpoint.layout)
    return float(jax.jit(residual)(checkpoint.state, params))


def floor(k, magnitude):
    """The registration's rounding floor at row k: 2.5 eps k M_k."""
    from cells.models.surface_pump import LEDGER_STEP_ROUNDING

    return LEDGER_STEP_ROUNDING * EPS * k * magnitude


def check_binding(model, spec, checkpoint):
    """Refuse a checkpoint whose record does not hold its state's residual: |R(state) - R| above
    the row's floor, 2.5 eps max(k, 1) M_k, with M_k evaluated at the row (NaN refuses). The
    record's own R stays the next step's start, so a restart continues the record bit for bit."""
    row_terms, _ = terms(model, spec, checkpoint.layout)
    params = model.parameters(spec, checkpoint.layout)
    energy, _, magnitude = (float(v) for v in jax.jit(row_terms)(checkpoint.state, params))
    difference = abs(energy - checkpoint.energy_check.residual)
    allowed = floor(max(int(checkpoint.step_index), 1), magnitude)
    if not difference <= allowed:
        raise ConfigError(
            "Checkpoint's step-doubled energy record does not hold its state's residual "
            f"(|R(state) - R| {difference:.3e} pJ, floor {allowed:.3e} pJ at step "
            f"{int(checkpoint.step_index)})"
        )


# ------------------------------------------------------------------ the check


def _fold(start, values):
    """start + values[0] + values[1] + ..., each partial a left fold (np.add.accumulate), so a
    run split at any row continues bit for bit."""
    return np.cumsum(np.concatenate(([start], values)))[1:]


def check_segment(spec, record, first_step, values, events, *, rtol):
    """(the record after a segment's accepted steps, their diagnostics), or NumericalError at the
    first row that fails. values: the rollout's (R, R'', F, M, halves' validity) per step; events:
    rule 1's event steps; first_step: the segment's first row's global step index (its start)."""
    energy, half, flows, magnitude, halves = (np.asarray(v) for v in values)
    n = energy.size
    if n == 0:
        return record, dict.fromkeys(DIAGNOSTICS, 0.0)
    from cells.models.surface_tissue import ENERGY_ATOL_PJ as atol

    cap = spec.energy_check.integration_error_cap
    k = first_step + 1 + np.arange(n, dtype=np.float64)
    previous = np.concatenate(([record.residual], energy[:-1]))
    with np.errstate(all="ignore"):
        d = energy - previous
        dh = half - previous
        held1 = ~halves.astype(bool) | events | ~np.isfinite(dh)
        counted = ~held1 & (np.abs(np.where(held1, 0.0, dh)) > COUNT_FACTOR * EPS * magnitude)
        q = np.where(counted, d / np.where(counted, dh, 1.0), np.nan)
        out_band = counted & ~((q >= BAND[0]) & (q <= BAND[1]))
        hold = held1 | out_band
        a = np.where(hold, 0.0, 4.0 / 3.0 * (d - np.where(held1, 0.0, dh)))
        sum_a = _fold(record.sum_a, a)
        sum_abs = _fold(record.sum_abs_a, np.abs(a))
        held = _fold(record.sum_held_d, np.where(hold, d, 0.0))
        corrected = energy - sum_a - held
        rounding = floor(k, magnitude)
        allowance = rounding + KAPPA * sum_abs
        held_bound = atol + rtol * flows
        finite = (
            np.isfinite(energy) & np.isfinite(flows) & np.isfinite(magnitude) & np.isfinite(d)
            & np.isfinite(corrected) & np.isfinite(sum_abs)
        )  # fmt: skip
        failures = (
            ("a non-finite residual, flow or magnitude", ~finite),
            ("the corrected residual exceeds its floor and a sixteenth of the integration error",
             np.abs(corrected) > allowance),
            ("a held step's change exceeds today's bound at its row",
             hold & (np.abs(d) > held_bound)),
            ("the integration error exceeds the registration's cap",
             sum_abs > cap * flows + rounding),
        )  # fmt: skip
        # The earliest failing row, whatever the window width (its first reason at that row).
        first = [(int(np.flatnonzero(bad)[0]), reason) for reason, bad in failures if bad.any()]
        if first:
            j, reason = min(first, key=lambda item: item[0])
            raise NumericalError(
                MESSAGE + f"{reason} at accepted step {int(k[j])} "
                f"(|C| {abs(corrected[j]):.3e} pJ, allowance {allowance[j]:.3e} pJ, "
                f"sum |a| {sum_abs[j]:.3e} pJ, F {flows[j]:.3e} pJ)"
            )
        ratio = np.where(
            allowance > 0, np.abs(corrected) / np.where(allowance > 0, allowance, 1.0),
            np.where(corrected == 0, 0.0, np.inf),
        )  # fmt: skip
        # Sum |a| / F, as the registration reports it; 0 at a row without flows, where the cap
        # is the floor alone.
        relative = np.where(flows > 0, sum_abs / np.where(flows > 0, flows, 1.0), 0.0)
        held_ratio = np.where(hold, np.abs(d) / held_bound, 0.0)
    diagnostics = {
        "max_step_doubled_energy_ratio": float(np.max(ratio)),
        "max_integration_error_relative": float(np.max(relative)),
        "max_held_step_energy_ratio": float(np.max(held_ratio)),
    }
    start = record if record.rows is None else replace(record, rows=None)
    rows = EnergyRows(start, energy, sum_a, sum_abs, held, counted, q, out_band, ratio, relative,
                      held_ratio)  # fmt: skip
    return rows.record_at(n), diagnostics


def summary(record):
    """The run-level quantities the run's end decides and reports."""
    counted = int(record.counted_q.size)
    return dict(
        check="cells.execution.step_doubled_energy@1",
        counted_steps=counted,
        median_step_ratio=float(np.median(record.counted_q)) if counted else None,
        held_out_of_band=record.held_out_of_band,
        held_cap=max(HELD_CAP[0], math.ceil(HELD_CAP[1] * counted)),
        largest_ratio=record.max_ratio,
        integration_error_largest=record.max_integration_error,
        integration_error_end=record.last_integration_error,
        largest_held_ratio=record.max_held_ratio,
    )


def decide(record):
    """The whole-run conditions at the run's end, as registered (amendment 2 was not adopted):
    the summary, or NumericalError naming the condition that fails."""
    out = summary(record)
    median = out["median_step_ratio"]
    if median is not None and not BAND[0] <= median <= BAND[1]:
        raise NumericalError(
            MESSAGE + f"the order condition: the median step ratio {median:.4g} over "
            f"{out['counted_steps']} counted steps lies outside [{BAND[0]}, {BAND[1]}]"
        )
    if out["held_out_of_band"] > out["held_cap"]:
        raise NumericalError(
            MESSAGE + f"{out['held_out_of_band']} out-of-band steps are held, above the cap of "
            f"{out['held_cap']} for {out['counted_steps']} counted steps"
        )
    return out
