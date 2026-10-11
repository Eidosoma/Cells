"""Common-clock execution, component conservation and complete coupled observations."""

import time

import jax
import numpy as np

from cells.assembly.engine import device_for
from cells.assembly.spec import AssemblyError
from cells.assembly_cell import MODEL_ID
from cells.assembly_cell.kernel import CoupledState, advance
from cells.assembly_cell.spec import parse_spec, tick_at
from cells.assembly_pool import engine as pool
from cells.assembly_pool.spec import AVOGADRO
from cells.core.schedule import PhysicalIonicGraphControl, control_values
from cells.models import kinetic_finite_extracellular as ionic


def initial_state(spec):
    y, _ = ionic.initial_values(spec.ionic)
    n = spec.pool.worlds
    return CoupledState(
        pool.initial_state(spec.pool),
        jax.tree.map(lambda v: np.broadcast_to(v, (n, *v.shape)).copy(), y),
        np.zeros(n, np.uint32),
        np.zeros(n, np.uint32),
        np.zeros(n),
        np.zeros(n, np.int32),
    )


def validate_state(spec, state):
    if not isinstance(state, CoupledState):
        raise AssemblyError("Require complete coupled state")
    state = jax.tree.map(np.asarray, state)
    pool.validate_state(spec.pool, state.pool)
    for value, template in zip(
        jax.tree.leaves(state), jax.tree.leaves(initial_state(spec)), strict=True
    ):
        if value.shape != template.shape or value.dtype != template.dtype:
            raise AssemblyError("Coupled checkpoint shape/dtype mismatch")
    if (
        np.any(state.fault)
        or np.any(state.tick != state.tick[0])
        or np.any(state.tick > spec.ticks)
    ):
        raise AssemblyError("Coupled clock or ionic stage fault")
    if np.any(state.pool.time_s != state.tick * spec.ionic.execution.dt):
        raise AssemblyError("Assembly and ionic observation clocks disagree")
    if (
        np.any(state.segments < state.tick)
        or np.any(state.segments > state.tick.astype(np.uint64) + state.pool.event_count)
        or np.any(~np.isfinite(state.availability_exposure_s))
        or np.any(state.availability_exposure_s < 0)
        or np.any(state.availability_exposure_s > state.pool.time_s + 1e-10)
    ):
        raise AssemblyError("Invalid coupled integration/exposure ledger")
    checks = []
    for i in range(spec.pool.worlds):
        checks.append(
            ionic.check_values(jax.tree.map(lambda v, i=i: v[i], state.ionic), spec.ionic)
        )
    maxima = {k: max(c[k] for c in checks) for k in checks[0]}
    return state, maxima


def summary(spec, state):
    state, checks = validate_state(spec, state)
    _, layout = ionic.initial_values(spec.ionic)
    voltages = ionic.cell_voltage(state.ionic.amount_increment, layout, xp=np)[:, 0]
    return {
        "model": MODEL_ID,
        "worlds": spec.pool.worlds,
        "tick": int(state.tick[0]),
        "through_time_s": float(state.pool.time_s[0]),
        "ionic_segments": int(state.segments.astype(np.uint64).sum()),
        "assembly": pool.summary(spec.pool, state.pool),
        "ionic_accounting": checks,
        "final_voltage_V": voltages.tolist(),
        "channel_transferred_fmol": state.ionic.channel_transferred[:, 0].tolist(),
        "availability_exposure_s": state.availability_exposure_s.tolist(),
        "coupling": spec.to_dict()["coupling"],
        "experimental_validation": False,
        "scope": "One-way kinetic hypothesis; no protein energy or chemical feedback model",
    }


def run(spec, *, backend="cpu", device_index=0, state=None, until=None, callback=None):
    started = time.monotonic()
    spec = parse_spec(spec.to_dict())
    target = spec.ticks if until is None else tick_at(spec, until)
    current = initial_state(spec) if state is None else validate_state(spec, state)[0]
    if target < current.tick[0]:
        raise AssemblyError("Cannot run a coupled state backward")
    began = time.monotonic()
    device = device_for(backend, device_index)
    _, layout = ionic.initial_values(spec.ionic)
    control = PhysicalIonicGraphControl(*(v[0] for v in control_values(spec.ionic, [0.0])))
    p = spec.pool
    constants = np.asarray(
        [
            p.k_on_M_inv_s / (AVOGADRO * p.pool_volume_L),
            p.k_close_s_inv,
            p.k_off_s_inv,
            p.k_fragment_dissolve_s_inv,
        ]
    )
    current = jax.device_put(current, device)
    rest = jax.device_put(
        (
            np.arange(p.world_id_start, p.world_id_start + p.worlds, dtype=np.uint32),
            np.uint32(p.seed),
            np.uint32(p.root_node),
            constants,
            np.uint32(p.max_events_per_world),
            np.float64(spec.ionic.execution.dt),
            np.array([spec.inactive_availability, spec.active_availability]),
            layout,
            control,
        ),
        device,
    )
    tick, windows, execute_s, compile_s = int(np.asarray(current.tick)[0]), 0, 0.0, 0.0
    compiled = {}
    preparation_s = time.monotonic() - started
    transfer_s, callback_s = 0.0, 0.0
    while tick < target:
        count = min(spec.window_ticks, target - tick)
        if count not in compiled:
            start = time.monotonic()
            compiled[count] = advance.lower(current, *rest, ticks=count).compile()
            compile_s += time.monotonic() - start
        start = time.monotonic()
        current = compiled[count](current, *rest)
        jax.block_until_ready(current)
        execute_s += time.monotonic() - start
        if any(v.device != device for v in jax.tree.leaves(current)):
            raise AssemblyError("Coupled state returned on the wrong device")
        start_transfer = time.monotonic()
        host = jax.tree.map(np.asarray, current)
        transfer_s += time.monotonic() - start_transfer
        windows += 1
        if callback:
            start_callback = time.monotonic()
            callback(windows, host)
            callback_s += time.monotonic() - start_callback
        if np.any(host.fault) or np.any(host.pool.fault):
            raise AssemblyError("Coupled assembly/event/ionic stage fault; partial state retained")
        tick += count
        if np.any(host.tick != tick):
            raise AssemblyError("Coupled tick failed to advance")
        if time.monotonic() - began > p.max_wall_seconds:
            raise AssemblyError("Coupled wall budget exceeded")
    start_transfer = time.monotonic()
    host = jax.tree.map(np.asarray, current)
    transfer_s += time.monotonic() - start_transfer
    start_summary = time.monotonic()
    report = summary(spec, host)
    summary_s = time.monotonic() - start_summary
    return host, report | {
        "backend": backend,
        "device": str(device),
        "device_kind": device.device_kind,
        "precision": "float64",
        "compile_seconds": compile_s,
        "execute_seconds": execute_s,
        "elapsed_seconds": time.monotonic() - began,
        "phase_timings": {
            "preparation_seconds": preparation_s,
            "compile_seconds": compile_s,
            "execute_seconds": execute_s,
            "host_transfer_seconds": transfer_s,
            "callback_seconds": callback_s,
            "final_validation_summary_seconds": summary_s,
            "total_run_seconds": time.monotonic() - started,
        },
        "windows": windows,
    }
