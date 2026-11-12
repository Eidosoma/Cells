"""Coarse projective execution of one world: fine bursts and verified jumps.

Selected by a definition's execution.projective block (core/projective_spec.py)
through cells.core.runner.run. The fine engine is reused unchanged as the inner
integrator: every burst is the model's checked step on the definition's own
event grid, compiled once as the window rollout of core/runner.py, and every
accepted fine row passes the model's check_values (domain, every ledger at its
fine bound, nonnegative and nondecreasing dissipation).

Cycle. After a burst of K fine steps ending at grid index i, a jump to index
j = i + M is attempted only if
  * [t_i, t_{j+K}] lies inside one declared window and ends at or before the
    next scheduled input change, observation time and the horizon, so the jump
    never crosses an event and every event and observation sees a fine row;
  * no input change lies in the slope rows (t_{i-2m}, t_i];
  * the membrane-voltage rate and every gate's distance from its steady state
    at the burst end are within the declared thresholds;
  * M passes the jump rule: fixed, or error-controlled (numerics/projective.py:
    settling |v_1 - v_0| and the curvature from the previous slope, normalized
    by the declared tolerances, bounded by safety_factor).
The jumped row y_j = y_i + r (y_i - y_{i-m}) must pass the model's domain and
control-domain checks and check_values together with y_i, and its energy-ledger
change must satisfy |dE| <= energy_defect_atol_pJ + energy_defect_rtol * (flows
through the jump). A jump failing these is halved (down to min_steps) or not
taken. The next burst verifies it: its fine steps and checks must succeed; the
post-jump correction (distance of its end from the slow continuation of the
jump, the fast transient the jump excited) and the a posteriori estimate (the
jump's error estimate with the secant curvature between the slopes before and
after it), both normalized by the tolerances, must not exceed max_correction;
and the voltage-rate and gate-distance thresholds must hold at its end.
Otherwise the jump is rejected:
the jumped row and that burst are discarded, the run continues with fine
bursts from y_i, and the next attempt is at most rejection_shrink of the
rejected length (cooldown_bursts fine bursts when that falls below min_steps).

Jumped rows are accepted rows. Linear ledgers are affine in the state and are
preserved by the extrapolation up to its rounding (recorded per jump against
the affine prediction); the energy ledger is nonlinear and has the declared
per-jump bound above, while every row, fine or jumped, still passes the fine
cumulative bounds of check_values. Every jump, rejection and fallback is
recorded in the result's projective report.
"""

import math
from bisect import bisect_right
from dataclasses import dataclass
from time import perf_counter

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.devices import execution_device
from cells.core.errors import NumericalError
from cells.core.grid import EventGrid, clock_checks, require_refinement_model
from cells.core.resources import trace_bytes
from cells.core.runner import (
    RunResult,
    _compiled_window_rollout,
    check_steps,
    integration_steps,
    takes_steps,
    validate_checkpoint,
)
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError
from cells.core.state import Checkpoint, initialise
from cells.models import surface_pump_projective as readouts
from cells.models.registry import get_model
from cells.numerics import projective as method

ROW_FINE, ROW_JUMP = 0, 1
SHORTEN_ATTEMPTS = 4  # Halvings of a jump that fails its row checks.
CLOCK_CHUNK = 2**20  # Fine intervals per step-admission call.


@dataclass(frozen=True)
class ProjectiveRunResult(RunResult):
    """RunResult whose rows are fine rows and jumped rows (row_kinds 0 and 1)."""

    row_kinds: np.ndarray
    projective: dict

    def checkpoint_at(self, time):
        matches = np.flatnonzero(self.times == time)
        if not len(matches):
            raise ConfigError("Checkpoints require an exact accepted time; see accepted_times")
        index = int(matches[0])
        state = type(self.history)(*(np.array(values[index], copy=True) for values in self.history))
        return Checkpoint(
            jax.device_put(state, execution_device(self.spec.execution.backend)),
            self.final.layout,
            float(time),
            EventGrid(self.spec).exact_index(float(time)),
            event_index(self.spec, time),
        )


def _burst_checks(start, history, count, first, parameters, constants, *, checks):
    """The model's device checks of every burst row against its predecessor.

    first is the burst start's global step index: history row k is index
    first + 1 + k, the host check's step count for that row. Returns the first
    failing row (-1 if none), its failed checks, and the maximum of each
    diagnostic over the burst's real rows.
    """
    previous = jax.tree.map(lambda s, h: jnp.concatenate((s[None], h[:-1]), axis=0), start, history)
    steps = first + 1 + jnp.arange(jax.tree.leaves(history)[0].shape[0], dtype=jnp.int64)
    failed, values = jax.vmap(checks, in_axes=(0, 0, None, None, 0))(
        previous, history, parameters, constants, steps
    )
    real = jnp.arange(failed.shape[0]) < count
    failed = failed & real[:, None]
    bad = jnp.any(failed, axis=1)
    first = jnp.where(jnp.any(bad), jnp.argmax(bad), -1)
    maxima = jnp.max(jnp.where(real[:, None], values, 0.0), axis=0)
    return first, failed[jnp.maximum(first, 0)], maxima


_compiled_burst_checks = jax.jit(_burst_checks, static_argnames=("checks",))
# In-process executables by function, static model functions and argument
# shapes, so runs of one definition shape compile once (as core/vector_windows).
_EXECUTABLES = {}
_EXECUTABLE_LIMIT = 8


def _executable(function, args, statics, kwargs=None):
    """(executable, compile seconds or 0.0 when reused)."""
    leaves, tree = jax.tree.flatten(args)
    key = (
        function,
        statics,
        tuple(sorted((kwargs or {}).items())),
        tree,
        tuple(
            (
                np.shape(v),
                v.dtype if hasattr(v, "dtype") else np.asarray(v).dtype,
                getattr(v, "sharding", None),
            )
            for v in leaves
        ),  # fmt: skip
    )
    if key in _EXECUTABLES:
        return _EXECUTABLES[key], 0.0
    began = perf_counter()
    compiled = function.lower(*args, *statics, **(kwargs or {})).compile()
    if len(_EXECUTABLES) >= _EXECUTABLE_LIMIT:
        _EXECUTABLES.pop(next(iter(_EXECUTABLES)))
    _EXECUTABLES[key] = compiled
    return compiled, perf_counter() - began


class _Bursts:
    """Fixed-width compiled bursts of the model's checked step (runner window rollout).

    The steps are the ordinary window rollout of core/runner.py. Rows are
    checked by the model's check_values on the host ("host"), or by its device
    checks on the device-resident burst ("device"); either refusal raises.
    """

    def __init__(self, spec, model, layout, width, row_checks="host"):
        self.spec, self.model, self.width = spec, model, width
        self.device = execution_device(spec.execution.backend)
        self.parameters = jax.device_put(model.parameters(spec, layout), self.device)
        self.active = jax.device_put(layout.active, self.device)
        self.row_checks = row_checks
        if row_checks == "device":
            self.constants = jax.device_put(model.device_check_constants(spec), self.device)
        self.compiled = None
        self.compiled_checks = None
        self.compile_seconds = 0.0
        self.execute_seconds = 0.0
        self.check_seconds = 0.0

    def run(self, state, times, first):
        """(final device state, host rows [start, ...], diagnostics); raises on refusal.

        first is the global step index of times[0]: the rows' step counts.
        """
        final, rows, history, count = self._step(state, times)
        began = perf_counter()
        if self.row_checks == "device":
            diagnostics = self._device_checks(state, history, count, times, first)
        else:
            counted = check_steps(self.model, first, count + 1)
            diagnostics = self.model.check_values(rows, self.spec, **counted)
        self.check_seconds += perf_counter() - began
        return final, rows, diagnostics

    def _device_checks(self, state, history, count, times, first):
        model = self.model
        args = (
            jax.device_put(state, self.device),
            history,
            np.int64(count),
            np.int64(first),
            self.parameters,
            self.constants,
        )
        if self.compiled_checks is None:
            self.compiled_checks, seconds = _executable(
                _compiled_burst_checks, args, (), dict(checks=model.device_checks)
            )
            self.compile_seconds += seconds
        first, failed, maxima = (np.asarray(v) for v in self.compiled_checks(*args))
        if int(first) >= 0:
            names = [c for c, f in zip(model.DEVICE_CHECKS, failed, strict=True) if f]
            raise NumericalError(
                model.device_failure_message(names[0])
                + f" at {times[int(first) + 1]} s (device row checks: {', '.join(names)})"
            )
        return dict(zip(model.DEVICE_DIAGNOSTICS, (float(v) for v in maxima), strict=True))

    def advance(self, state, times):
        """The fine steps alone: (final device state, host rows); raises on a refused step."""
        final, rows, _, _ = self._step(state, times)
        return final, rows

    def _step(self, state, times):
        spec, model = self.spec, self.model
        steps = integration_steps(spec, times)
        controls = control_values(spec, times[:-1])
        count, padding = len(steps), self.width - len(steps)
        enabled = np.arange(self.width) < count
        steps = np.pad(steps, (0, padding))
        controls = jax.tree.map(
            lambda v: np.pad(v, ((0, padding), *((0, 0) for _ in v.shape[1:]))), controls
        )
        args = jax.device_put(
            (state, steps, controls, self.parameters, self.active, enabled), self.device
        )
        if self.compiled is None:
            self.compiled, seconds = _executable(
                _compiled_window_rollout,
                args,
                (
                    getattr(model, "rhs", None),
                    getattr(model, "domain_valid", None),
                    getattr(model, "checked_step", None),
                ),
            )
            self.compile_seconds += seconds
        began = perf_counter()
        final, history, valid = self.compiled(*args)
        jax.block_until_ready((final, history))
        self.execute_seconds += perf_counter() - began
        failed = np.flatnonzero(~np.asarray(valid[:count]))
        if len(failed):
            k = int(failed[0])
            raise NumericalError(
                f"{spec.execution.solver} trial/endpoint domain failure on "
                f"[{times[k]}, {times[k + 1]}]; no invalid step accepted or repaired"
            )
        rows = model.STATE_TYPE(
            *(
                np.concatenate((np.asarray(a)[None], np.asarray(b)[:count]), axis=0)
                for a, b in zip(state, history, strict=True)
            )
        )
        return final, rows, history, count


def _row(rows, i):
    return type(rows)(*(np.asarray(v[i]) for v in rows))


def _merge(total, current):
    for name, value in current.items():
        total[name] = max(total.get(name, 0.0), float(value))


def _admit_clock(spec, grid):
    """check_steps over every fine interval of the grid, in bounded chunks (clock_checks)."""
    check = clock_checks(spec)
    for times in grid.windows(0, CLOCK_CHUNK):
        check(integration_steps(spec, times), times)


class _Run:
    def __init__(self, spec, checkpoint):
        self.spec, self.config = spec, spec.projective
        self.model = get_model(spec.model)
        if not spec.execution.jit:
            raise ConfigError("Projective execution requires a compiled (jit) definition")
        if not hasattr(self.model, "checked_step"):
            raise ConfigError("Projective execution requires the model's checked step")
        require_refinement_model(spec)
        self.grid = EventGrid(spec)
        _admit_clock(spec, self.grid)
        self.checkpoint = initialise(spec) if checkpoint is None else checkpoint
        validate_checkpoint(spec, self.checkpoint, self.grid)
        self.layout = self.checkpoint.layout
        self.p = readouts.host_layout(self.layout)
        self.bursts = _Bursts(
            spec, self.model, self.layout, self.config.burst_steps, self.config.row_checks
        )
        self.changes = sorted({c.time for c in spec.experiment.changes})
        self.observations = sorted(spec.experiment.observation_times)
        self.end = spec.experiment.end_time
        self.tolerance = {k: getattr(self.config.tolerance, k) for k in readouts.COORDINATES}
        # Accepted rows, as chunks: (times, kinds, rows).
        self.chunks = []
        self.row_count = 0
        self.diagnostics = {}
        self.jumps, self.rejections, self.fallbacks = [], [], []
        self.fine_steps = self.jumped_steps = self.discarded_steps = 0
        self.ledger_check_seconds = 0.0

    # Grid helpers ------------------------------------------------------------
    def times(self, start, stop):
        return np.fromiter((self.grid[k] for k in range(start, stop + 1)), dtype=np.float64)

    def control(self, time):
        values = control_values(self.spec, [time])
        return type(values)(*(v[0] for v in values))

    def next_after(self, points, time):
        k = bisect_right(points, time)
        return points[k] if k < len(points) else np.inf

    def window_at(self, time):
        for w in self.config.windows:
            if w.start_time <= time < w.end_time:
                return w
        return None

    # Storage ------------------------------------------------------------------
    def append(self, times, kinds, rows):
        self.chunks.append((times, kinds, rows))
        self.row_count += len(times)
        if trace_bytes(self.spec, self.row_count) > self.spec.execution.max_trace_bytes:
            raise ConfigError("Projective accepted rows exceed max_trace_bytes")

    def pop(self):
        times, _, _ = self.chunks.pop()
        self.row_count -= len(times)

    # Records ------------------------------------------------------------------
    def fallback(self, time, reason, **details):
        self.fallbacks.append(dict(time_s=float(time), reason=reason, **details))

    # Jump planning ------------------------------------------------------------
    def coordinates(self, rows, k):
        return readouts.coordinates(self.model, _row(rows, k), self.p)

    def plan(self, index, rows, times, previous):
        """(steps, estimate dict) of the jump to attempt at index, or (0, reason dict)."""
        cfg, h = self.config, self.spec.execution.dt
        K, m = cfg.burst_steps, cfg.slope_steps
        t = float(times[-1])
        window = self.window_at(t)
        if window is None:
            return 0, None  # Fine stepping outside windows is not a fallback.
        if len(times) - 1 < K:
            return 0, dict(reason="short_burst")
        first = float(times[-1 - 2 * m])
        if any(first < c <= t for c in self.changes):
            return 0, dict(reason="event_in_slope_rows")
        if self.cooldown:
            self.cooldown -= 1
            return 0, dict(reason="cooldown", remaining=self.cooldown)
        valid, rate, distance = readouts.settling(
            self.model, _row(rows, len(times) - 1), self.control(t), self.p
        )
        settle_info = dict(voltage_rate_V_per_s=rate, gate_distance=distance)
        if not valid:
            return 0, dict(reason="readouts_invalid")
        if rate > cfg.safety.max_membrane_voltage_rate_V_per_s:
            return 0, dict(reason="voltage_rate", **settle_info)
        if distance > cfg.safety.max_gate_distance:
            return 0, dict(reason="gate_distance", **settle_info)
        boundary = min(
            self.next_after(self.changes, t),
            self.next_after(self.observations, t),
            window.end_time,
            self.end,
        )
        b = bisect_right(self.grid, boundary) - 1
        bound = b - K - index
        z = [self.coordinates(rows, k) for k in (len(times) - 1 - 2 * m, len(times) - 1 - m, -1)]
        tz = [float(times[k]) for k in (len(times) - 1 - 2 * m, len(times) - 1 - m, -1)]
        v0 = {k: (z[1][k] - z[0][k]) / (tz[1] - tz[0]) for k in z[2]}
        v1 = {k: (z[2][k] - z[1][k]) / (tz[2] - tz[1]) for k in z[2]}
        span = tz[2] - tz[1]
        midpoint = 0.5 * (tz[1] + tz[2])
        self.slope = (midpoint, v1)
        if previous is not None and any(previous[0] < c <= t for c in self.changes):
            previous = None  # A slope from another control regime says nothing here.
        if previous is not None:
            # Secant curvature from the previous slope; the settling term is the
            # chord change that this slow curvature does not explain.
            elapsed = midpoint - previous[0]
            second = {k: (v1[k] - previous[1][k]) / elapsed for k in v1}
            curvature = method.normalized(second, self.tolerance)
            settle = method.normalized(
                {k: v1[k] - v0[k] - second[k] * span for k in v1}, self.tolerance
            )
            curvature_source = "previous_slope"
        else:
            # Within one burst the two are not separable: count the whole chord
            # change as both settling and curvature (conservative).
            second = None
            settle = method.normalized({k: v1[k] - v0[k] for k in v1}, self.tolerance)
            curvature = settle / span
            curvature_source = "within_burst"
        estimate = dict(
            settle_per_s=settle,
            curvature_per_s2=curvature,
            curvature_source=curvature_source,
            boundary_steps=int(bound),
            second=second,
            **settle_info,
        )
        rule = cfg.jump
        limits = dict(rule=rule.max_steps, boundary=int(bound))
        if rule.rule == "error_controlled":
            duration = method.admissible_jump(settle, curvature, span, rule.safety_factor)
            limits["error_estimate"] = (
                rule.max_steps if not math.isfinite(duration) else int(min(duration / h, 2**53))
            )
            if self.last_jump is not None:
                limits["growth"] = int(rule.max_growth * self.last_jump)
        if self.cap is not None:
            limits["rejection_cap"] = int(self.cap)
        binding = min(limits, key=limits.get)
        steps = limits[binding]
        estimate.update(limits=limits, binding=binding)
        if steps < rule.min_steps:
            return 0, dict(reason=binding, **estimate)
        estimate.update(v1=v1, chord_span_s=span)
        return int(steps), estimate

    def attempt(self, index, rows, times, steps):
        """The checked jump for up to SHORTEN_ATTEMPTS halvings: (jump dict or None, failures)."""
        cfg, m = self.config, self.config.slope_steps
        last, base = _row(rows, len(times) - 1), _row(rows, len(times) - 1 - m)
        t, t_base = float(times[-1]), float(times[-1 - m])
        energy_last = readouts.energy(self.model, last, self.p)
        failures = []
        for _ in range(SHORTEN_ATTEMPTS):
            if steps < cfg.jump.min_steps:
                break
            target = float(self.grid[index + steps])
            ratio = (target - t) / (t - t_base)
            jumped = method.extrapolate(last, base, ratio)
            reason, details = self.check_jump(
                last, jumped, target, energy_last, (index, index + steps)
            )
            if reason is None:
                details.update(
                    steps=int(steps),
                    to_time_s=target,
                    ratio=float(ratio),
                    jumped=jumped,
                    ledgers=self.ledger_record(last, base, jumped, ratio),
                )
                return details, failures
            failures.append(dict(steps=int(steps), reason=reason, **_plain(details)))
            steps //= 2
        return None, failures

    def check_jump(self, last, jumped, target, energy_last, indices):
        """(None, details) for a jumped row passing every row check, else (reason, details).

        indices: the global step indices of last and jumped (their step counts).
        """
        model, p = self.model, self.p
        check = getattr(model.domain_valid, "with_control", None)
        with np.errstate(all="ignore"):
            try:
                ok = (
                    check(jumped, self.control(target), p, p.active, xp=np)
                    if check is not None
                    else model.domain_valid(jumped, p, p.active, xp=np)
                )
            except (ArithmeticError, ValueError, np.linalg.LinAlgError):
                ok = False
        if not bool(ok):
            return "domain", {}
        began = perf_counter()
        try:
            pair = type(last)(*(np.stack((a, b)) for a, b in zip(last, jumped, strict=True)))
            counted = {"steps": list(indices)} if takes_steps(model) else {}
            diagnostics = model.check_values(pair, self.spec, **counted)
        except NumericalError as error:
            return "checks: " + str(error), {}
        finally:
            self.ledger_check_seconds += perf_counter() - began
        residual, flows = readouts.energy(model, jumped, p)
        flow = abs(flows - energy_last[1])
        details = dict(
            energy_defect_pJ=float(abs(residual - energy_last[0])),
            energy_flow_pJ=float(flow),
            energy_bound_pJ=float(cfg_energy_bound(self.config.safety, flow)),
            diagnostics=diagnostics,
        )
        if not details["energy_defect_pJ"] <= details["energy_bound_pJ"]:
            return "energy_defect", details
        return None, details

    def ledger_record(self, last, base, jumped, ratio):
        """Linear ledgers at the jump: residuals and their distance from the affine value."""
        values = [readouts.linear_ledgers(self.model, row, self.p) for row in (base, last, jumped)]
        record = {}
        for name in values[2]:
            # The fine drift of the residual over the chord, carried over the jump.
            carried = ratio * (values[1][name] - values[0][name])
            predicted = values[1][name] + carried
            record[name] = dict(
                before=float(np.max(np.abs(values[1][name]), initial=0.0)),
                after=float(np.max(np.abs(values[2][name]), initial=0.0)),
                jump_change=float(np.max(np.abs(values[2][name] - values[1][name]), initial=0.0)),
                carried_fine_drift=float(np.max(np.abs(carried), initial=0.0)),
                affine_excess=float(np.max(np.abs(values[2][name] - predicted), initial=0.0)),
            )
        return record

    def correction(self, jump, rows, times):
        """Post-jump correction and a posteriori estimate, in tolerance units.

        correction: distance of the verifying burst's end from the slow
        continuation of the jump (slope, plus the curvature term when the
        curvature was estimated), i.e. the fast transient the jump excited.
        a_posteriori: the jump's error estimate with the secant curvature
        between the slope before the jump and the verifying burst's slope.
        """
        z_end = self.coordinates(rows, -1)
        elapsed = float(times[-1]) - jump["to_time_s"]
        lead = jump["to_time_s"] - jump["midpoint"]
        second = jump["second"]
        drift = {
            k: jump["v1"][k] * elapsed
            + (0.0 if second is None else 0.5 * second[k] * ((lead + elapsed) ** 2 - lead**2))
            for k in z_end
        }
        correction = method.normalized(
            {k: z_end[k] - jump["z"][k] - drift[k] for k in z_end}, self.tolerance
        )
        midpoint, slope = _slope(self, rows, times)
        secant = method.normalized(
            {k: (slope[k] - jump["v1"][k]) / (midpoint - jump["midpoint"]) for k in slope},
            self.tolerance,
        )
        record = jump["record"]
        estimate = method.error_estimate(
            record["to_time_s"] - record["from_time_s"],
            record["settle_per_s"],
            secant,
            record["chord_span_s"],
        )
        return correction, estimate, secant

    # Main loop ------------------------------------------------------------------
    def execute(self):
        cfg = self.config
        K = cfg.burst_steps
        model = self.model
        last_index = len(self.grid) - 1
        index = self.checkpoint.step_index
        state = jax.device_put(self.checkpoint.state, self.bursts.device)
        start = model.STATE_TYPE(*(np.asarray(v)[None] for v in self.checkpoint.state))
        self.append(np.asarray([self.checkpoint.time]), np.asarray([ROW_FINE], np.int8), start)
        self.cap, self.cooldown, self.last_jump, self.slope = None, 0, None, None
        previous = None  # (chord midpoint time, slope) of the last accepted burst.
        pending = None
        while index < last_index:
            count = min(K, last_index - index)
            times = self.times(index, index + count)
            try:
                final, rows, diagnostics = self.bursts.run(state, times, index)
            except NumericalError as error:
                if pending is None:
                    raise
                index, state, previous = self.reject(pending, f"burst: {error}", count)
                pending = None
                continue
            if pending is not None:
                reason, details = self.verify(pending, rows, times)
                if reason is not None:
                    index, state, previous = self.reject(pending, reason, count, **details)
                    pending = None
                    continue
                pending["record"].update(details)
                _merge(self.diagnostics, pending["diagnostics"])
                self.jumps.append(pending["record"])
                self.jumped_steps += pending["record"]["steps"]
                self.last_jump, self.cap = pending["record"]["steps"], None
                pending = None
            _merge(self.diagnostics, diagnostics)
            self.append(times[1:], np.full(count, ROW_FINE, np.int8), _tail(rows))
            self.fine_steps += count
            index += count
            state = final
            if index >= last_index:
                break
            self.slope = None
            steps, estimate = self.plan(index, rows, times, previous)
            slope = self.slope if self.slope is not None else _slope(self, rows, times)
            if steps == 0:
                if estimate is not None:
                    self.fallback(times[-1], estimate.pop("reason"), **_plain(estimate))
                self.last_jump = None
                previous = slope
                continue
            jump, failures = self.attempt(index, rows, times, steps)
            if jump is None:
                self.fallback(times[-1], "jump_checks", attempts=failures, **_plain(estimate))
                self.last_jump = None
                previous = slope
                continue
            jumped, target = jump.pop("jumped"), jump["to_time_s"]
            diagnostics = jump.pop("diagnostics")
            record = dict(
                from_time_s=float(times[-1]),
                **jump,
                shortened=failures,
                estimate_normalized=method.error_estimate(
                    target - float(times[-1]),
                    estimate["settle_per_s"],
                    estimate["curvature_per_s2"],
                    estimate["chord_span_s"],
                ),
                **_plain(estimate),
            )
            pending = dict(
                index=index,
                state=state,
                slope=slope,
                record=record,
                diagnostics=diagnostics,
                z=readouts.coordinates(model, jumped, self.p),
                v1=estimate["v1"],
                second=estimate["second"],
                midpoint=slope[0],
                to_time_s=target,
            )
            jumped_row = model.STATE_TYPE(*(np.asarray(v)[None] for v in jumped))
            self.append(np.asarray([target]), np.asarray([ROW_JUMP], np.int8), jumped_row)
            index += jump["steps"]
            state = jax.device_put(jumped, self.bursts.device)
            previous = slope
        if pending is not None:  # Unreachable: a jump always leaves room for its burst.
            raise NumericalError("Projective jump ended without its verifying burst")
        return index, state

    def verify(self, pending, rows, times):
        cfg = self.config
        correction, estimate, secant = self.correction(pending, rows, times)
        valid, rate, distance = readouts.settling(
            self.model, _row(rows, len(times) - 1), self.control(float(times[-1])), self.p
        )
        details = dict(
            correction_normalized=correction,
            a_posteriori_normalized=estimate,
            secant_curvature_per_s2=secant,
            verify_voltage_rate_V_per_s=rate,
            verify_gate_distance=distance,
        )
        if not valid:
            return "verify_readouts_invalid", details
        if correction > cfg.safety.max_correction:
            return "correction", details
        if estimate > cfg.safety.max_correction:
            return "a_posteriori_estimate", details
        if rate > cfg.safety.max_membrane_voltage_rate_V_per_s:
            return "verify_voltage_rate", details
        if distance > cfg.safety.max_gate_distance:
            return "verify_gate_distance", details
        return None, details

    def reject(self, pending, reason, count, **details):
        record = dict(pending["record"], reason=reason, **details)
        self.rejections.append(record)
        self.pop()  # The jumped row; its burst was never stored.
        self.discarded_steps += count
        shrunk = int(self.config.safety.rejection_shrink * record["steps"])
        if shrunk < self.config.jump.min_steps:
            self.cap, self.cooldown = None, self.config.safety.cooldown_bursts
        else:
            self.cap = shrunk
        self.last_jump = None
        return pending["index"], pending["state"], pending["slope"]

    def report(self, timings):
        cfg = self.config
        counts = {}
        for item in self.fallbacks:
            counts[item["reason"]] = counts.get(item["reason"], 0) + 1
        traversed = self.fine_steps + self.jumped_steps
        return dict(
            method=cfg.method,
            row_checks=cfg.row_checks,
            fine_steps=self.fine_steps,
            jumped_steps=self.jumped_steps,
            discarded_fine_steps=self.discarded_steps,
            traversed_steps=traversed,
            fine_step_fraction=self.fine_steps / traversed if traversed else 1.0,
            step_speedup=traversed / max(1, self.fine_steps + self.discarded_steps),
            jumps=len(self.jumps),
            rejections=len(self.rejections),
            fallback_counts=counts,
            jump_log=self.jumps,
            rejection_log=self.rejections,
            fallback_log=self.fallbacks,
            timings=timings,
        )


def cfg_energy_bound(safety, flow):
    return safety.energy_defect_atol_pJ + safety.energy_defect_rtol * flow


def _tail(rows):
    return type(rows)(*(v[1:] for v in rows))


def _slope(run, rows, times):
    """(chord midpoint, slope) of a burst's last chord, for the next curvature estimate."""
    m = run.config.slope_steps
    if len(times) - 1 < m:
        return None
    a, b = run.coordinates(rows, len(times) - 1 - m), run.coordinates(rows, -1)
    ta, tb = float(times[-1 - m]), float(times[-1])
    return 0.5 * (ta + tb), {k: (b[k] - a[k]) / (tb - ta) for k in b}


def _plain(values):
    """JSON-ready copy of an estimate record (slope and curvature vectors dropped)."""
    return {k: v for k, v in values.items() if k not in ("v1", "second")}


def run_projective(spec, checkpoint=None, *, started=None):
    """Projective execution of a parsed definition with an execution.projective block."""
    started = perf_counter() if started is None else started
    if spec.projective is None:
        raise ConfigError("Projective execution requires an execution.projective block")
    work = _Run(spec, checkpoint)
    prepared = perf_counter()
    index, state = work.execute()
    executed = perf_counter()
    times = np.concatenate([c[0] for c in work.chunks])
    kinds = np.concatenate([c[1] for c in work.chunks])
    columns = zip(*(c[2] for c in work.chunks), strict=True)
    history = work.model.STATE_TYPE(*(np.concatenate(values, axis=0) for values in columns))
    requested = [t for t in spec.experiment.observation_times if t >= work.checkpoint.time]
    observations = work.model.observe_history(times, history, work.layout, requested, spec)
    for values in (times, kinds, *history):
        values.setflags(write=False)
    final = Checkpoint(
        state, work.layout, float(times[-1]), index, event_index(spec, float(times[-1]))
    )
    timings = {
        "preparation_seconds": prepared - started,
        "compile_or_cache_seconds": work.bursts.compile_seconds,
        "execute_seconds": work.bursts.execute_seconds,
        "fine_check_seconds": work.bursts.check_seconds,
        "jump_check_seconds": work.ledger_check_seconds,
        "loop_seconds": executed - prepared,
        "analysis_seconds": perf_counter() - executed,
        "total_run_seconds": perf_counter() - started,
    }
    return ProjectiveRunResult(
        spec,
        final,
        work.checkpoint.step_index,
        times,
        history,
        observations,
        timings,
        work.diagnostics,
        kinds,
        work.report(timings),
    )
