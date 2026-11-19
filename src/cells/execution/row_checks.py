"""Compiled row checks of a scalar window's accepted rows (WindowPolicy row_checks="device").

docs/WINDOW_DEVICE_CHECKS_DESIGN.md §4 and §9. On the scalar windowed path, the host's
check_values tests every accepted row (core.runner._analyse_segment). In device mode a second
compiled program runs the model's device checks over the window's rows, which are already on the
device, and returns one summary per window. The device checks are the same tests with the same
bounds (models/surface_pump_checks.py). The window rollout's executable is untouched, so times,
histories, observations and checkpoints are those of host mode by construction.

The device is a pass filter with a guard band (R3, the lead's ruling 2). A window is handed to
the host's check_values, which decides it with today's exception class and message, when:
* any check failed on any of its rows, or
* any ledger's residual exceeds HOST_DECIDES_ABOVE of its bound on any row.
Only a window that is clean with that margin is accepted on the device's word. Its diagnostics are
then the device's maxima, reported and not judged (ruling 3); they agree with the host's to
rounding, not bitwise.

Qualification: CPU only, so a GPU backend is refused, and so is a composition with a live
retiring operator (admit; design §9.2).
"""

import inspect
from dataclasses import dataclass, field, replace
from time import perf_counter
from types import MappingProxyType
from typing import Any, NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions.specs import ConfigError
from cells.execution import energy_check as energy
from cells.execution import phases
from cells.registry.models import get_model

HOST_DECIDES_ABOVE = 0.5  # The guard band: above this ratio to its bound, the host decides.
MODES = ("host", "device")
HOOKS = ("device_checks", "device_check_constants", "DEVICE_CHECKS", "DEVICE_DIAGNOSTICS")
HANDED_BACK = ("failed", "above_band")  # Why the host decided a window.


def _takes_margins(checks):
    try:
        return "margins" in inspect.signature(checks).parameters
    except (TypeError, ValueError):
        return False


def _live_retiring(model, spec):
    """A composition's retiring operators that are live in this definition (models/
    pump_composite.py): its device checks then read adjusted rows."""
    retiring = getattr(getattr(model, "composition", model), "retiring", ())
    if not retiring:
        return ()
    _, p = model.initial_values(spec)
    return tuple(op for op in retiring if not op.statically_idle(p))


def admit(spec):
    """Refuse device row checks for a definition they cannot serve (fail-closed).

    Two cases are refused because they are not yet qualified (the lead's rulings of 16 November
    2026, D187: no claim without teeth):
    - a GPU backend: the GPU's host-against-device spread is unmeasured;
    - a composition with a live retiring operator: its device checks read adjusted rows, and
      that branch's refusals have no planted test yet.
    """
    if not spec.execution.jit:
        raise ConfigError("row_checks device requires a compiled run (execution.jit true)")
    if spec.execution.backend != "cpu":
        raise ConfigError(
            "row_checks device is qualified on the CPU only; a GPU backend is refused until a "
            "GPU measurement exists"
        )
    model = get_model(spec.model)
    missing = [name for name in HOOKS if not hasattr(model, name)]
    if missing:
        raise ConfigError(
            "row_checks device requires the model's device checks; missing " + ", ".join(missing)
        )
    if not _takes_margins(model.device_checks):
        raise ConfigError("row_checks device requires device checks that report margins")
    checks = tuple(model.DEVICE_CHECKS)
    if len(checks) < 3 or checks[0] != "domain" or checks[-1] != "dissipation":
        raise ConfigError(
            "row_checks device requires DEVICE_CHECKS (domain, ledgers..., dissipation)"
        )
    if _live_retiring(model, spec):
        raise ConfigError(
            "row_checks device is not yet qualified for a composition with a live retiring "
            "operator: its adjusted rows' refusals have no planted test"
        )


def _window_checks(start, history, count, first_step, parameters, constants, *, checks):
    """Every accepted row of one window through the model's device checks, by a scan.

    Row 0 is the window's start, its own predecessor; history row k - 1 is row k, with
    predecessor row k - 1. Rows past count (the window's real steps) are masked. Row k's
    accepted-step count is first_step + k, the host check's value for it. Returns each check's
    first failing row (-1: none), each diagnostic's maximum and each ledger's largest ratio to
    its bound, over rows 0..count.
    """
    failed, maxima, ratios = checks(start, start, parameters, constants, first_step, margins=True)
    first = jnp.where(failed, 0, -1).astype(jnp.int64)

    def advance(carry, inputs):
        previous, first, maxima, ratios = carry
        row, index = inputs
        failed, values, rate = checks(
            previous, row, parameters, constants, first_step + index, margins=True
        )
        live = index <= count
        first = jnp.where(live & (first < 0) & failed, index, first)
        maxima = jnp.where(live, jnp.maximum(maxima, values), maxima)
        ratios = jnp.where(live, jnp.maximum(ratios, rate), ratios)
        return (row, first, maxima, ratios), None

    width = jax.tree.leaves(history)[0].shape[0]
    indices = jnp.arange(1, width + 1, dtype=jnp.int64)
    (_, first, maxima, ratios), _ = jax.lax.scan(
        advance, (start, first, maxima, ratios), (history, indices)
    )
    return first, maxima, ratios


_compiled_window_checks = jax.jit(_window_checks, static_argnames=("checks",))


class Summary(NamedTuple):
    """One window's device summary (host arrays)."""

    first: np.ndarray  # [checks] first failing row, -1 for none
    maxima: np.ndarray  # [diagnostics]
    ratios: np.ndarray  # [ledgers] largest |residual| / bound


@dataclass(frozen=True)
class Outcome:
    """Who decided one window's row checks, and the device's view of its margins."""

    decided_by: str  # "device" or "host"
    handed_back: str | None  # None (device-decided), "failed" or "above_band"
    ratios: MappingProxyType  # {ledger: largest |residual| / bound over the window's rows}
    failing: MappingProxyType = field(default_factory=lambda: MappingProxyType({}))  # {check: row}
    temp_bytes: int | None = None  # The run's check program's temporaries (a run's constant).

    def to_dict(self):
        """The window's record (windows.jsonl); temp_bytes is the run's, in its resources."""
        return {
            "decided_by": self.decided_by,
            "handed_back": self.handed_back,
            "ratios": dict(self.ratios),
            "failing": dict(self.failing),
        }


def decide(summary, checks, ledgers, band=None):
    """The window's Outcome: the device decides only a clean window within the band."""
    band = HOST_DECIDES_ABOVE if band is None else band
    failing = {c: int(r) for c, r in zip(checks, summary.first, strict=True) if r >= 0}
    ratios = MappingProxyType({k: float(v) for k, v in zip(ledgers, summary.ratios, strict=True)})
    if failing:
        return Outcome("host", "failed", ratios, MappingProxyType(failing))
    if not np.all(summary.ratios <= band):  # A NaN ratio is not within the band.
        return Outcome("host", "above_band", ratios)
    return Outcome("device", None, ratios)


@dataclass
class DeviceRowChecks:
    """One run's compiled window checks: the model's device checks with their constants placed
    once, the executable compiled at the first window, and the host's diagnostic key order.

    Built from the run's start checkpoint. The host's check_values runs once on that row: its
    keys must be DEVICE_DIAGNOSTICS as a set, so the two lists of a model cannot drift apart
    silently, and device-decided diagnostics are given in its order.
    """

    spec: Any
    model: Any
    device: Any
    constants: Any
    host_keys: tuple
    ledgers: tuple
    executable: Any = None
    temp_bytes: int | None = None

    @classmethod
    def build(cls, spec, checkpoint, device):
        from cells.execution.runner import check_steps

        admit(spec)
        model = get_model(spec.model)
        row = model.STATE_TYPE(*(np.asarray(v)[None] for v in checkpoint.state))
        host = model.check_values(row, spec, **check_steps(model, checkpoint.step_index, 1))
        if set(host) != set(model.DEVICE_DIAGNOSTICS):
            raise ConfigError(
                "row_checks device requires the model's device diagnostics to be its host "
                "diagnostics; they differ in "
                + ", ".join(sorted(set(host) ^ set(model.DEVICE_DIAGNOSTICS)))
            )
        constants = model.device_check_constants(spec)
        if energy.selected(spec):  # Today's two leaves, the registration's cap, and the switch.
            constants = energy.StepDoubledConstants(
                constants.material_atol,
                constants.energy_rtol,
                np.asarray(spec.energy_check.integration_error_cap, dtype=np.float64),
            )
        constants = jax.device_put(constants, device)
        return cls(spec, model, device, constants, tuple(host), tuple(model.DEVICE_CHECKS[1:-1]))

    def compile(self, start, history, parameters):
        """Compile for the window's shapes (device arrays or ShapeDtypeStructs); seconds."""
        began = perf_counter()
        args = (start, history, np.int64(0), np.int64(0), parameters, self.constants)
        lowered = _compiled_window_checks.lower(*args, checks=self.model.device_checks)
        ratios = lowered.out_info[2]
        if ratios.shape != (len(self.ledgers),):
            raise ConfigError(
                f"Device checks report {ratios.shape} margins for {len(self.ledgers)} ledgers"
            )
        self.executable = lowered.compile()
        try:
            self.temp_bytes = int(self.executable.memory_analysis().temp_size_in_bytes)
        except (AttributeError, TypeError, NotImplementedError):
            self.temp_bytes = None
        return perf_counter() - began

    def launch(self, start, history, count, first_step, parameters):
        """The window's device summary, dispatched (device arrays; nothing waits)."""
        return self.executable(
            start, history, np.int64(count), np.int64(first_step), parameters, self.constants
        )

    def outcome(self, launched):
        """(Summary, Outcome) of a launched window; waits for the device."""
        summary = Summary(*(np.asarray(v) for v in launched))
        outcome = decide(summary, self.model.DEVICE_CHECKS, self.ledgers)
        if outcome.decided_by == "host":
            phases.mark(
                "row_checks.handed_back",
                reason=outcome.handed_back,
                max_ratio=max(outcome.ratios.values(), default=0.0),
                failing=",".join(outcome.failing) or "none",
            )
        return summary, replace(outcome, temp_bytes=self.temp_bytes)

    def diagnostics(self, summary):
        """A device-decided window's diagnostics, under the host's keys in the host's order."""
        device = dict(zip(self.model.DEVICE_DIAGNOSTICS, map(float, summary.maxima), strict=True))
        return {key: device[key] for key in self.host_keys}


def merge_outcomes(total, outcome):
    """Accumulate window outcomes into a run's report (WindowedResult.resources)."""
    total["windows"] += 1
    total["check_temp_bytes"] = outcome.temp_bytes
    if outcome.decided_by == "host":
        total["host_decided"][outcome.handed_back] += 1
    for name, value in outcome.ratios.items():
        total["max_ratios"][name] = max(total["max_ratios"].get(name, 0.0), value)


def new_report(band=None):
    return {
        "mode": "device",
        "band": HOST_DECIDES_ABOVE if band is None else band,
        "windows": 0,
        "host_decided": {reason: 0 for reason in HANDED_BACK},
        "max_ratios": {},
        "check_temp_bytes": None,
    }
