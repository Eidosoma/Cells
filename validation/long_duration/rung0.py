"""FR-8 rung 0: the fine engine's order through a switch (RUNG0_20261119.md; D224 item 3).

Restart windows of H2, stage 0's harness world (worlds.h2: projective qual-01's F1 world at a
3600 s horizon). Each window is a new run that imports a saved full state from stage 0's R3 (H2 at
0.25 ms, from snapshot 24e516c7; its kept rows) into H2 at dt = 2^-k ms, from the window's start
to its end. It claims no continuity with R3. The engine model is resolved_pump_tissue@3 alone.
Development, not judged.

run WINDOW K OUT_DIR    one window at dt = 2^-K ms; rows.npz (the full state at every 1 ms row)
                        and run.json (the record).
analyse OUTPUT ROOT     every window's arms under ROOT/WINDOW/k{K}: the registered readings.
synthetic OUTPUT        the order function on synthetic sequences (16:4:1, 4:2:1, at the floor).

This module imports nothing from harness_judge.py or m4_settling.py; it reuses harness.Keeper
and harness.snapshot_revision.
"""

import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REGISTRATION = HERE / "rung0_20261119.json"
EPS = float(np.finfo(float).eps)


def registration():
    return json.loads(REGISTRATION.read_text())


def dt_of(k):
    """dt = 2^-k ms, exactly: the 1 ms grid's products are on every arm's grid."""
    return 1e-3 / 2**k


def at_ms(ms):
    """The time of an integer millisecond count: the 1 ms grid's own float product."""
    return int(ms) * 1e-3


def millisecond_rows(start_ms, end_ms):
    return [i * 1e-3 for i in range(int(start_ms), int(end_ms) + 1)]


def window_raw(window, k):
    """H2 at dt_k with the window's horizon and 1 ms observations over the window. A window that
    ends before the cue's off-edge drops that schedule entry (it lies beyond its horizon)."""
    from validation.long_duration import worlds

    w = registration()["windows"][window]
    dt, end = dt_of(k), at_ms(w["end_ms"])
    raw = worlds.h2(dt)
    raw["experiment"]["end_time"] = end
    raw["experiment"]["observation_times"] = millisecond_rows(w["start_ms"], w["end_ms"])
    raw["execution"]["max_steps"] = int(math.ceil(end / dt)) + 8
    for group in raw["experiment"]["channel_controls"]:
        group["schedule"] = [c for c in group["schedule"] if c["time"] <= end]
    return raw


def saved_row(model, t):
    """The full state at time t from stage 0's R3 (its kept rows), as the model's state type."""
    with np.load(Path(registration()["source"]["rows"])) as archive:
        times = archive["times"]
        i = np.flatnonzero(times == t)
        if len(i) != 1:
            raise ValueError(f"R3 has no kept row at {t!r}")
        return model.STATE_TYPE(*(np.array(archive[f][i[0]]) for f in model.STATE_TYPE._fields))


def checkpoint(spec, model, t):
    """A checkpoint of this definition at t holding R3's saved state (validated by the runner)."""
    from cells.execution.grid import EventGrid
    from cells.execution.schedule import event_index
    from cells.execution.state import Checkpoint, initialise

    initial = initialise(spec)
    return Checkpoint(
        saved_row(model, t), initial.layout, t, EventGrid(spec).exact_index(t), event_index(spec, t)
    )


def run(window, k, out_dir):
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.definitions.specs import parse_spec
    from cells.execution import blas_threads
    from cells.execution.windows import WindowPolicy, run_windowed
    from cells.registry.models import get_model
    from validation.long_duration import harness

    reg = registration()
    w = reg["windows"][window]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=False)
    record = dict(
        study="FR-8 rung 0",
        window=window,
        k=k,
        dt_s=dt_of(k),
        start_s=at_ms(w["start_ms"]),
        end_s=at_ms(w["end_ms"]),
        engine_model="resolved_pump_tissue@3",
        registration=reg["registration"],
        judged=False,
        snapshot_revision=harness.snapshot_revision(),
        cpu_affinity=sorted(os.sched_getaffinity(0)),
        started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    started = time.perf_counter()
    try:
        spec = parse_spec(window_raw(window, k))
        model = get_model(spec.model)
        start = at_ms(w["start_ms"])
        keeper = harness.Keeper([t for t in spec.experiment.observation_times if t >= start])
        policy = WindowPolicy(window_steps=reg["window_steps"], row_checks="device")
        result = run_windowed(spec, policy, checkpoint(spec, model, start), sink=keeper)
        times, rows = keeper.stacked()
        np.savez_compressed(out / "rows.npz", times=times, **rows)
        record.update(
            status="complete",
            steps=int(result.resources["executed_steps"]),
            off_nominal_boundaries=int(result.resources["resident_off_nominal_events"]),
            timings={k_: float(v) for k_, v in result.timings.items()},
            diagnostics={k_: float(v) for k_, v in result.diagnostics.items()},
            row_checks=json.loads(json.dumps(result.resources.get("row_checks"), default=str)),
            blas=blas_threads.libraries(),
        )
    except Exception as error:  # A refusal is a result, kept.
        record.update(status="refused", error_type=type(error).__name__, error=str(error))
    record["seconds"] = time.perf_counter() - started
    (out / "run.json").write_text(json.dumps(record, indent=1, default=str) + "\n")
    print(json.dumps({x: record.get(x) for x in ("window", "k", "status", "steps", "seconds")}))
    return 0 if record["status"] == "complete" else 1


# ------------------------------------------------------------------ the readings


def classes(rows):
    """Per row: membrane voltages [patch], concentrations [species, cell] and the gates by law
    {nav_m, nav_h, kir_m, kir_h} [cell], from the engine's own readouts (H2 at any dt: the layout
    does not depend on dt)."""
    from cells.definitions.specs import parse_spec
    from cells.models import surface_pump_projective as projective
    from cells.registry.models import get_model

    spec = parse_spec(window_raw("WA", 0))
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    cells = np.asarray(p.active, dtype=bool)
    laws = np.asarray(p.channel_laws)
    active = np.asarray(p.channel_active, dtype=bool)
    nav, kir = active & (laws == 2), active & (laws == 1)
    out = dict(voltage=[], concentration=[], nav_m=[], nav_h=[], kir_m=[], kir_h=[])
    for i in range(len(rows["amount_increment"])):
        row = model.STATE_TYPE(*(rows[f][i] for f in model.STATE_TYPE._fields))
        out["voltage"].append(projective.membrane_voltage(row, p))
        ci, _ = model.physical_amounts(row, p)
        out["concentration"].append(ci[:, cells] / p.volume[cells])
        g = np.asarray(row.channel_gate)
        out["nav_m"].append(g[0, nav])
        out["nav_h"].append(g[1, nav])
        out["kir_m"].append(g[0, kir])
        out["kir_h"].append(g[1, kir])
    out = {key: np.asarray(v) for key, v in out.items()}
    out["gate"] = np.concatenate([out[g] for g in ("nav_m", "nav_h", "kir_m", "kir_h")], axis=1)
    return out


SCALES = dict(voltage=0.1, concentration=1.0, gate=1.0, nav_m=1.0, nav_h=1.0, kir_m=1.0, kir_h=1.0)


def difference(a, b, key):
    """Per row: the largest |a - b| over a class's entries (relative for concentration)."""
    d = np.abs(np.asarray(a) - np.asarray(b))
    if key == "concentration":
        d = d / np.abs(np.asarray(b))
    return d.reshape(len(d), -1).max(axis=1, initial=0.0)


def order(coarse, fine, floor):
    """The sup-norm ratio's order log2(coarse / fine), or None where either is not above its
    floor (a difference at the floor carries no order)."""
    if not (coarse > floor and fine > floor and math.isfinite(coarse) and math.isfinite(fine)):
        return None
    return math.log2(coarse / fine)


def synthetic(output=None):
    """The order function on synthetic sequences: 16:4:1 (p = 2), 4:2:1 (p = 1), and a sequence
    whose finer difference sits at the floor (no order)."""
    floor = 1e-12
    out = dict(
        second_order=order(16e-6 - 4e-6, 4e-6 - 1e-6, floor),
        first_order=order(4e-6 - 2e-6, 2e-6 - 1e-6, floor),
        at_the_floor=order(1e-11, 1e-12, floor),
    )
    out["passed"] = bool(
        out["second_order"] is not None
        and abs(out["second_order"] - 2) < 1e-12
        and out["first_order"] is not None
        and abs(out["first_order"] - 1) < 1e-12
        and out["at_the_floor"] is None
    )
    if output:
        Path(output).write_text(json.dumps(out, indent=1) + "\n")
    return out


if __name__ == "__main__":
    command = sys.argv[1]
    if command == "run":
        sys.exit(run(sys.argv[2], int(sys.argv[3]), sys.argv[4]))
    if command == "synthetic":
        print(json.dumps(synthetic(sys.argv[2])))
        sys.exit(0)
    raise SystemExit("usage: rung0.py run WINDOW K OUT_DIR | synthetic OUTPUT")
