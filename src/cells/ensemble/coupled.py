"""Scheduler interface for the existing event-split assembly/cell engine."""

import json
from pathlib import Path

from cells.assembly.engine import device_for
from cells.assembly_cell import engine, io


def run(spec, *, backend="gpu", state=None, callback=None):
    def record(window, current):
        if callback:
            callback(window, current, None)

    state, result = engine.run(spec, backend=backend, state=state, callback=record)
    # Keep assembly observables alongside the ionic response; the physical
    # state and assembly event times come from the existing coupled engine.
    result = result["assembly"] | result
    result.update(
        completed_shells=int((state.pool.full_first_s >= 0).sum()),
        completion_event="first_full_20_site_30_bond_cage",
        integrated_world_steps=int(state.tick.astype("uint64").sum()),
    )
    return state, result


def write_checkpoint(path, spec, state, *, execution, provenance=None):
    return io.write_checkpoint(
        path,
        spec,
        state,
        backend=execution["backend"],
        provenance={"operation": "ensemble", "execution": execution, "parent": provenance},
    )


def load_checkpoint(path, *, backend="gpu"):
    record = json.loads((Path(path) / "manifest.json").read_text())
    execution = (record.get("provenance") or {}).get("execution", {})
    device = device_for(backend, 0)
    if execution.get("backend") != backend or execution.get("device_kind") != device.device_kind:
        raise ValueError("Coupled ensemble checkpoint device kind changed")
    return io.load_checkpoint(path, backend=backend)
