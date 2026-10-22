"""CPU/GPU cluster execution with separate material owners and complete observations."""

import time

import jax
import numpy as np

from cells.assembly.engine import device_for
from cells.assembly.spec import AssemblyError
from cells.assembly_cell.kernel import CoupledState
from cells.assembly_cell.spec import tick_at
from cells.assembly_cluster import MODEL_ID
from cells.assembly_cluster.kernel import advance
from cells.assembly_cluster.spec import channel_owners, parse_spec
from cells.assembly_pool import engine as pool
from cells.assembly_pool.spec import AVOGADRO
from cells.core.schedule import control_values
from cells.models.registry import get_model


def initial_state(spec):
    ionic = get_model(spec.ionic.model)
    y, _ = ionic.initial_values(spec.ionic)
    n, cells = spec.pool.worlds, len(spec.pools)
    return CoupledState(
        jax.tree.map(
            lambda *v: np.stack(v, axis=1), *(pool.initial_state(p.pool) for p in spec.pools)
        ),
        jax.tree.map(lambda v: np.broadcast_to(v, (n, *v.shape)).copy(), y),
        np.zeros(n, np.uint32),
        np.zeros(n, np.uint32),
        np.zeros((n, cells)),
        np.zeros(n, np.int32),
    )


def cell_pool(state, index):
    return jax.tree.map(lambda v: np.asarray(v)[:, index], state.pool)


def validate_state(spec, state):
    ionic = get_model(spec.ionic.model)
    if not isinstance(state, CoupledState):
        raise AssemblyError("Require complete assembly-cluster state")
    state = jax.tree.map(np.asarray, state)
    for value, template in zip(
        jax.tree.leaves(state), jax.tree.leaves(initial_state(spec)), strict=True
    ):
        if value.shape != template.shape or value.dtype != template.dtype:
            raise AssemblyError("Cluster checkpoint shape/dtype mismatch")
    for index, binding in enumerate(spec.pools):
        pool.validate_state(binding.pool, cell_pool(state, index))
    if (
        np.any(state.fault)
        or np.any(state.tick != state.tick[0])
        or np.any(state.tick > spec.ticks)
    ):
        raise AssemblyError("Cluster clock or ionic stage fault")
    if np.any(state.pool.time_s != state.tick[:, None] * spec.ionic.execution.dt):
        raise AssemblyError("Cell assembly and ionic observation clocks disagree")
    if np.any(
        state.pool.pending_valid
        & (state.pool.pending_event >= 0)
        & (state.pool.pending_time_s <= state.pool.time_s)
    ):
        raise AssemblyError("Cluster pending event must follow the observation boundary")
    if (
        np.any(state.segments < state.tick)
        or np.any(
            state.segments
            > state.tick.astype(np.uint64) + state.pool.event_count.astype(np.uint64).sum(axis=1)
        )
        or np.any(~np.isfinite(state.availability_exposure_s))
        or np.any(state.availability_exposure_s < 0)
        or np.any(state.availability_exposure_s > state.pool.time_s + 1e-10)
    ):
        raise AssemblyError("Invalid cluster integration/exposure ledger")
    checks = [
        ionic.check_values(jax.tree.map(lambda v, i=i: v[i], state.ionic), spec.ionic)
        for i in range(spec.pool.worlds)
    ]
    return state, {k: max(c[k] for c in checks) for k in checks[0]}


def summary(spec, state):
    ionic = get_model(spec.ionic.model)
    state, checks = validate_state(spec, state)
    _, layout = ionic.initial_values(spec.ionic)
    n = len(spec.pools)
    if hasattr(ionic, "ensemble_voltage"):
        voltage = np.stack(
            [
                ionic.ensemble_voltage(
                    jax.tree.map(lambda v, i=i: v[i], state.ionic),
                    layout,
                    spec.ionic,
                    float(state.pool.time_s[i, 0]),
                )
                for i in range(spec.pool.worlds)
            ]
        )
        voltage_axes = {
            "final_voltage_axis": "membrane_patch",
            "voltage_owner_ids": [p.id for p in spec.ionic.model.membranes],
        }
    else:
        voltage = ionic.cell_voltage(state.ionic.amount_increment, layout, xp=np)[:, :n]
        voltage_axes = {}
    ncav = len(getattr(spec.ionic.model, "calcium_channels", ()))
    cells = {
        binding.cell_id: pool.summary(binding.pool, cell_pool(state, i))
        | {"stream_id": binding.stream_id, "seed": binding.pool.seed}
        for i, binding in enumerate(spec.pools)
    }
    ip3 = {}
    if hasattr(ionic, "ip3_readouts"):
        concentration, fraction = ionic.ip3_readouts(state.ionic, layout, xp=np)
        ip3 = {
            "ip3": {
                "law": spec.ionic.model.ip3_release[0].law,
                "cell_ids": [r.cell_id for r in spec.ionic.model.ip3_release],
                "cytosol_mM": concentration.tolist(),
                "release_fraction": fraction.tolist(),
            }
        }
    return {
        "model": MODEL_ID,
        "physical_model": spec.ionic.to_dict()["model"]["id"],
        "worlds": spec.pool.worlds,
        "world_id_start": spec.pool.world_id_start,
        "cell_ids": [p.cell_id for p in spec.pools],
        "channel_ids": [c.id for c in spec.ionic.model.channels],
        "tick": int(state.tick[0]),
        "through_time_s": float(state.pool.time_s[0, 0]),
        "ionic_segments": int(state.segments.astype(np.uint64).sum()),
        "integrated_world_steps": int(state.tick.astype(np.uint64).sum()),
        "assembly_cells": cells,
        "committed_events": sum(c["committed_events"] for c in cells.values()),
        "ionic_accounting": checks,
        "final_voltage_V": voltage.tolist(),
        **voltage_axes,
        "channel_transferred_fmol": state.ionic.channel_transferred[
            ..., : len(spec.ionic.model.channels)
        ].tolist(),
        **(
            {
                "channel_transfer_axes": ["world", "species", "channel"],
                "channel_species_ids": list(spec.ionic.model.species_ids),
                "channel_relative_permeability": layout.channel_relative_permeability[
                    :, : len(spec.ionic.model.channels)
                ].tolist(),
            }
            if hasattr(layout, "channel_relative_permeability")
            else {}
        ),
        "availability_exposure_s": state.availability_exposure_s.tolist(),
        "coupling": {p.cell_id: p.to_dict()["coupling"] for p in spec.pools},
        **(
            {
                "calcium": {
                    "species_ids": list(spec.ionic.model.species_ids),
                    "cytosol_amounts_fmol": ionic.cytosol_amount(state.ionic, layout, xp=np)[
                        ..., :n
                    ].tolist(),
                    "er_voltage_V": np.stack(
                        [
                            ionic.er.voltage(
                                ionic.store_state(state.ionic, i),
                                ionic.store_layout(layout, i),
                                xp=np,
                            )
                            for i in range(n)
                        ],
                        axis=-1,
                    ).tolist(),
                }
            }
            if hasattr(ionic, "store_state")
            else {}
        ),
        **(
            {
                "calcium_channels": {
                    "ids": [c.id for c in spec.ionic.model.calcium_channels],
                    "gate": state.ionic.calcium_gate[..., :ncav].tolist(),
                    "transferred_fmol": state.ionic.calcium_channel_transferred[
                        ..., :ncav
                    ].tolist(),
                    "dissipated_energy_pJ": state.ionic.calcium_channel_dissipated_energy_pJ[
                        ..., :ncav
                    ].tolist(),
                }
            }
            if hasattr(spec.ionic.model, "calcium_channels")
            else {}
        ),
        "experimental_validation": False,
        **ip3,
        "scope": (
            "One-way assembly/channel hypothesis; separate neutral protein pools; "
            "explicitly owned extracellular regions; no protein energy or chemical feedback"
        ),
    }


def run(spec, *, backend="cpu", device_index=0, state=None, until=None, callback=None):
    started = time.monotonic()
    spec = parse_spec(spec.to_dict())
    ionic = get_model(spec.ionic.model)
    target = spec.ticks if until is None else tick_at(spec, until)
    current = initial_state(spec) if state is None else validate_state(spec, state)[0]
    if target < current.tick[0]:
        raise AssemblyError("Cannot run a cluster state backward")
    device = device_for(backend, device_index)
    _, layout = ionic.initial_values(spec.ionic)
    controls = control_values(spec.ionic, [0.0])
    control = type(controls)(*(v[0] for v in controls))
    p = spec.pool
    rest = jax.device_put(
        (
            np.arange(p.world_id_start, p.world_id_start + p.worlds, dtype=np.uint32),
            np.array([b.pool.seed for b in spec.pools], np.uint32),
            np.array([b.pool.root_node for b in spec.pools], np.uint32),
            np.array(
                [
                    [
                        b.pool.k_on_M_inv_s / (AVOGADRO * b.pool.pool_volume_L),
                        b.pool.k_close_s_inv,
                        b.pool.k_off_s_inv,
                        b.pool.k_fragment_dissolve_s_inv,
                    ]
                    for b in spec.pools
                ]
            ),
            np.array([b.pool.max_events_per_world for b in spec.pools], np.uint32),
            np.float64(spec.ionic.execution.dt),
            np.array([[b.inactive_availability, b.active_availability] for b in spec.pools]),
            channel_owners(spec),
            layout,
            control,
        ),
        device,
    )
    current = jax.device_put(current, device)
    tick, windows = int(np.asarray(current.tick)[0]), 0
    compile_s, execute_s, transfer_s, callback_s = 0.0, 0.0, 0.0, 0.0
    preparation_s = time.monotonic() - started
    compiled = None
    # Observation boundaries are registered grid points; window choices cannot
    # change the integration path or silently skip a requested observation.
    boundaries = sorted(
        {target, *(tick_at(spec, t) for t in spec.ionic.experiment.observation_times)}
    )
    while tick < target:
        boundary = min(t for t in boundaries if t > tick)
        count = min(spec.window_ticks, target - tick, boundary - tick)
        if compiled is None:
            began = time.monotonic()
            compiled = advance.lower(current, *rest, ticks=np.int32(count), model=ionic).compile()
            compile_s += time.monotonic() - began
        began = time.monotonic()
        current = compiled(current, *rest, ticks=np.int32(count))
        jax.block_until_ready(current)
        execute_s += time.monotonic() - began
        if any(v.device != device for v in jax.tree.leaves(current)):
            raise AssemblyError("Cluster state returned on the wrong device")
        began = time.monotonic()
        host = jax.tree.map(np.asarray, current)
        transfer_s += time.monotonic() - began
        windows += 1
        if callback:
            began = time.monotonic()
            callback(windows, host)
            callback_s += time.monotonic() - began
        if np.any(host.fault) or np.any(host.pool.fault):
            raise AssemblyError("Cluster assembly/event/ionic stage fault; partial state retained")
        tick += count
        if np.any(host.tick != tick):
            raise AssemblyError("Cluster tick failed to advance")
        if time.monotonic() - started > p.max_wall_seconds:
            raise AssemblyError("Cluster wall budget exceeded")
    began = time.monotonic()
    host = jax.tree.map(np.asarray, current)
    transfer_s += time.monotonic() - began
    began = time.monotonic()
    report = summary(spec, host)
    summary_s = time.monotonic() - began
    return host, report | {
        "backend": backend,
        "device": str(device),
        "device_kind": device.device_kind,
        "precision": "float64",
        "compile_seconds": compile_s,
        "execute_seconds": execute_s,
        "elapsed_seconds": time.monotonic() - started,
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
