"""Independent complete INIT and carried SIM integration, no production imports."""

import hashlib
import sys
from copy import deepcopy
from pathlib import Path
from types import ModuleType

import numpy as np
from scipy.integrate import solve_ivp

from validation.tissue import surface_calcium_energy_reference as fuel
from validation.topology import joint_water_profile_interventions_reference as scheduled


def target_definition(raw):
    result = deepcopy(raw)
    result["model"] = result["model"]["scheduled"]
    return result


def initial(request):
    context = scheduled.bind(request["simulation"])
    values = {
        name: np.asarray(row["values"]).reshape(row["shape"])
        for name, row in request["source"]["checkpoint"]["state"].items()
    }
    state = scheduled.flatten(context, values).copy()
    state[-1] = 0.0
    return context, state


def integrate(raw, *, initial_state=None, end_time=None):
    context = scheduled.bind(raw)
    zero = scheduled.initial(context)
    state = zero.copy() if initial_state is None else np.array(initial_state, copy=True)
    end = raw["experiment"]["end_time"] if end_time is None else end_time
    if (
        state.shape != zero.shape
        or not np.isfinite(state).all()
        or state[-1] != 0
        or isinstance(end, bool)
        or not np.isfinite(end)
        or not 0 <= end <= raw["experiment"]["end_time"]
    ):
        raise ValueError("Require a finite complete phase-zero state and bounded endpoint")
    clocks = {0.0, float(end)}
    for name, groups in raw["experiment"].items():
        if name.endswith("_controls"):
            for row in groups:
                key = "controls" if "controls" in row else "schedule"
                clocks.update(v["time"] for v in row[key] if 0 < v["time"] < end)
    clocks = sorted(clocks)
    times = sorted(
        {0.0, float(end), *(t for t in raw["experiment"]["observation_times"] if 0 <= t <= end)}
    )
    # Background transfers are small compared with bulk amounts/gates. A tighter
    # ledger floor resolves transient RK error instead of hiding it in a final
    # endpoint's pulse cancellation or the bulk-state absolute tolerance.
    floors = {
        name: np.full(
            shape,
            1e-29 if name.endswith("_C") else 1e-24 if name == "membrane_transferred" else 2e-14,
        )
        for name, shape in context["parent"]["shapes"].items()
    }
    atol = np.r_[context["process"].flatten(context["parent"], floors), 1e-22]
    saved = {0.0: state.copy()}
    evaluations = 0
    for left, right in zip(clocks[:-1], clocks[1:], strict=True):
        result = solve_ivp(
            lambda t, y, held=left: scheduled.evaluate(context, y, held_time=held)[0],
            (left, right),
            state,
            method="DOP853",
            rtol=2e-11,
            atol=atol,
            max_step=min(0.0625e-6, right - left),
            dense_output=True,
        )
        if not result.success:
            raise RuntimeError(result.message)
        state = result.y[:, -1].copy()
        for time in times:
            if left < time <= right:
                saved[time] = state.copy() if time == right else result.sol(time)
        evaluations += result.nfev
    return state, dict(
        method="Independent complete coupled owner DOP853, every held-control family",
        rhs_evaluations=evaluations,
        end_time_s=float(end),
        control_knots_s=clocks,
        observation_times_s=times,
        observations=np.stack([saved[t] for t in times]),
        relative_tolerance=2e-11,
        bulk_absolute_tolerance=2e-14,
        background_transfer_absolute_tolerance=1e-24,
        charge_absolute_tolerance_C=1e-29,
        clock_absolute_tolerance_s=1e-22,
        maximum_step_s=0.0625e-6,
    )


def dependency_manifest(root):
    """Capture imported oracle functions and legacy unqualified helpers."""
    root = Path(root).resolve()
    pending = [sys.modules[__name__]]
    seen, result = set(), {}
    while pending:
        module = pending.pop()
        if module.__name__ in seen:
            continue
        seen.add(module.__name__)
        path = Path(module.__file__).resolve()
        result[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
        for value in vars(module).values():
            name = (
                value.__name__
                if isinstance(value, ModuleType)
                else getattr(value, "__module__", "")
            )
            candidate = sys.modules.get(name)
            location = getattr(candidate, "__file__", None)
            if location and Path(location).resolve().is_relative_to(root / "validation"):
                pending.append(candidate)
    assert "validation/betse/contact.py" in result
    return dict(sorted(result.items()))


def carried_fuel_turnover(raw, initial_state):
    """Independent route-by-route gross consumption at the actual carried pools."""
    context = scheduled.bind(raw)
    process, parent = context["process"], context["parent"]
    data = process.unpack(parent, initial_state[:-1])
    amount = parent["energy_initial"] + data["energy_amount_increment_fmol"]
    n = len(parent["cell_ids"])
    owners = [*parent["patch_owners"], *parent["plasma_owners"], *range(n)]
    regeneration_owners = [
        parent["cell_ids"].index(parent["pools"][p["pool_id"]]["cell_id"])
        for p in raw["model"]["regeneration_ports"]
    ]
    clocks = {0.0, raw["experiment"]["end_time"]}
    for name, groups in raw["experiment"].items():
        if name.endswith("_controls"):
            for row in groups:
                clocks.update(
                    v["time"] for v in row["controls" if "controls" in row else "schedule"]
                )
    clocks.update(
        t
        for e in raw["model"]["interventions"]
        for t in (e["on_s"], (e["on_s"] + e["off_s"]) / 2, e["off_s"])
    )
    rows = []
    for time in sorted(clocks):
        state = initial_state.copy()
        state[-1] = time
        slope, _, _ = scheduled.evaluate(context, state)
        rates = process.unpack(parent, slope[:-1])
        pumps = [
            *rates["pump_cycles"],
            *rates["plasma_pump_cycles"],
            *rates["er_pump_transferred"][:, 0],
        ]
        exchange = fuel.chemistry.exchange(
            pumps, owners, rates["regeneration_cycles_fmol"].tolist(), regeneration_owners, n
        )
        gross = np.asarray(exchange["gross_hydrolysis_fmol_s"]) + exchange["gross_synthesis_fmol_s"]
        rows.append(
            dict(time_s=time, fractional_rate_s=float(np.max(gross / np.min(amount, axis=0))))
        )
    return max(v["fractional_rate_s"] for v in rows), rows
