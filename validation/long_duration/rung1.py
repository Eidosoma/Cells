"""FR-8 rung 1: the arms of RUNG1_20261119.md, and first its control (D232, the entry §10.3).

The control is today's integrator, cells.solver.imex_ars222_face_electromigration@1, with X2
(cells.execution.step_doubled_energy@1) at the registered cap, on rung 1's registered arms for today's ID at
their full registered horizons (§3, §10.3, §10.4). Development, not judged.

Engine models: cells.model.resolved_pump_tissue@3 (H2); cells.model.resolved_pump_composite@1 over
cells.model.resolved_pump_tissue@3 with cells.operator.scheduled_species_turnover@1 and cells.operator.species_regulated_availability@1
(W0).

**Rule (b) (docs/CHECKPOINT_CONTINUITY_DESIGN.md §7).** H2's windows WS, WA, WC and WB are new runs
of H2 whose declared initial values are R3's saved state at the window's start: start_state,
section 7's name for the import. They claim no continuity with R3, and each is judged on its own.
- Each run computes the sha256 of R3's rows.npz, refuses a mismatch with the registered digest,
  and records the digest, R3's producing revision and its record's identity (§0; rung 0's §9.5
  rule).
- The import carries R3's amounts (with the charges that follow) and channel gates as the
  definition's initial values; the ledgers start at zero.
- Every schedule is re-timed by the window's start.

**Times.** Every time an arm declares (observation rows, cue edges, W0's interventions, the
horizon) is the arm's own grid product i * dt, so every edge and row lies on the grid exactly. Rows
are matched across arms by their integer millisecond (§10.4).

run ARM OUT_DIR [--x2-off]   one arm: H2-WA-k3, H2-WN-k0, H2-full-5, H2-slow-200, W0-0.125.
                             --x2-off is fallback (ii)'s instrument check (today's ID only).
arms                         the control's arms, one per line.
smoke OUT_DIR                development smokes of each path (no registered window or row).
instrument OUTPUT ROOT       I1a and I4 (§5, §10.5), read before any reading.
analyse OUTPUT ROOT INSTR    the readings (§4, §5, §10); refuses unless INSTR validated.
timed ARM OUT_DIR REF_DIR    the cost re-run (§10.1): its rows against REF_DIR's, bitwise.
plant STEP_MS OUTPUT         FR-3's plant at another step (§10.1; a cross-check under §10.6).
calm-run STEP_MS SOURCE_DIR OUT_DIR   §10.8's calm probe at a step (development).
step-change OUT_DIR [--no-window]     §10.9's step change, 20 ms to 1 ms and back (development).
c-run OUT_DIR [ARM]                   a registered windowed arm: H2-C, §10.10's (the default),
                                      or H2-N2C, §10.20's N2 with C.
run ARM OUT_DIR --solver=ID           an arm under another time integrator (§6, set after the
                                      definition is built).
stage-a-read OUTPUT ARM_DIR CONTROL   §6's reading: N2 alone on the slow phase against R3.
c-timed OUT_DIR REF_DIR [ARM]         (c): the arm's timed re-run, rows checked bitwise.
c-judge OUTPUT C_DIR [FULL1_COST C_COST] [--arm=ARM] [--plant=PLANT]
                                      the arm's verdict: §10.10's on H2-C, §10.20's on H2-N2C
                                      (with (b)'s in-world plant record, PLANT).
calm-read OUTPUT ROOT SOURCE_DIR       its reading (development, information).
inworld-plant ARM OUTPUT [AT_MS] [--solver=ID]
                             §10.7's plant in the arm's world at its step (AT_MS: development;
                             ID set after the definition is built, §10.16's route).
"""

import copy
import dataclasses
import hashlib
import json
import math
import os
import sys
import time
from fractions import Fraction
from pathlib import Path

import numpy as np

from validation import id_table

HERE = Path(__file__).resolve().parent
REGISTRATION = HERE / "rung1_20261119.json"
EPS = float(np.finfo(float).eps)
TODAY = "cells.solver.imex_ars222_face_electromigration@1"
FULL_MS = (1, 2, 5, 10, 20, 50, 100)
SLOW_MS = (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000)  # §10.4 adds 1-100 ms.
W0_MS = ("0.125", "0.25", "0.5", "1", "2", "5", "10")
WINDOWS = ("WS", "WA", "WC", "WB")
H2_END_MS, SLOW_END_MS = 3_600_000, 1_790_000
W0_END_MS, W0_DOSE_MS, W0_WRITE_MS = 60_000, 20_000, 40_000


class ImportRefused(ValueError):
    pass


def registration():
    return id_table.load(REGISTRATION)


def x2_block():
    e = registration()["energy_check"]
    return dict(check=e["check"], integration_error_cap=e["integration_error_cap"])


# ------------------------------------------------------------------ arms and steps


def control_arms():
    """The control's arms (§10.3, with §10.4's slow-phase arms), in launch order."""
    arms = [f"H2-{w}-k{k}" for k in range(9, -1, -1) for w in WINDOWS]
    arms += [f"H2-WN-k{k}" for k in range(9, -1, -1)]
    arms += [f"H2-full-{n}" for n in FULL_MS]
    arms += [f"H2-slow-{n}" for n in SLOW_MS]
    arms += [f"W0-{q}" for q in W0_MS]
    return arms


def step_of(text):
    """(step in ms as a Fraction, dt in s): 2^-k ms as 1e-3 / 2^k (the 1 ms grid's own products
    scaled), and a whole number of ms as its decimal."""
    q = Fraction(text)
    if q.numerator == 1 and q.denominator > 1:
        k = q.denominator.bit_length() - 1
        if q.denominator != 2**k:
            raise ValueError(f"step {text} ms is neither 2^-k ms nor a whole number of ms")
        return q, 1e-3 / 2**k
    if q.denominator != 1:
        raise ValueError(f"step {text} ms is neither 2^-k ms nor a whole number of ms")
    return q, float(f"{int(q)}e-3")


def parse_arm(arm):
    """(world, kind, step in ms as a Fraction, dt in s, window or None, k or None)."""
    parts = arm.split("-")
    if parts[0] == "H2" and parts[1] in (*WINDOWS, "WN"):
        k = int(parts[2].removeprefix("k"))
        return "H2", "window", Fraction(1, 2**k), 1e-3 / 2**k, parts[1], k
    if parts[0] == "H2" and parts[1] in ("full", "slow"):  # Fallback (ii) adds full-0.5, -0.25.
        return "H2", parts[1], *step_of(parts[2]), None, None
    if parts[0] == "W0":
        return "W0", "full", *step_of(parts[1]), None, None
    raise ValueError(f"unknown arm {arm!r}")


def grid_time(ms, step_ms, dt):
    """The grid's own product i * dt at an integer millisecond count (a multiple of the step)."""
    i = Fraction(ms) / step_ms
    if i.denominator != 1:
        raise ValueError(f"{ms} ms is not on the {step_ms} ms grid")
    return int(i) * dt


def ms_of(t):
    return int(round(float(t) * 1000))


# ------------------------------------------------------------------ the import (rule (b))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def source():
    """R3's rows, checked against the registered digest and revision: (path, record, provenance)."""
    reg = registration()["H2"]["source"]
    path = Path(reg["rows"])
    digest = sha256(path)
    if digest != reg["sha256"]:
        raise ImportRefused(
            f"R3's rows.npz has sha256 {digest}, not the registered {reg['sha256']}"
        )
    record_path = path.parent / "run.json"
    record_bytes = record_path.read_bytes()
    record = json.loads(record_bytes)
    if record.get("snapshot_revision") != reg["revision"] or record.get("status") != "complete":
        raise ImportRefused("R3's record does not name the registered revision, or is incomplete")
    provenance = dict(
        rows=str(path),
        rows_sha256=digest,
        registered_sha256=reg["sha256"],
        revision=record["snapshot_revision"],
        record=str(record_path),
        record_sha256=hashlib.sha256(record_bytes).hexdigest(),
        record_identity={
            key: record.get(key)
            for key in (
                "measurement",
                "arm",
                "dt_s",
                "registration",
                "run_of_record",
                "started_utc",
                "finished_utc",
                "status",
                "steps",
            )
        },  # fmt: skip
    )
    return path, record, provenance


def retimed(schedule, start_ms, end_ms, step_ms, dt):
    """A piecewise-constant schedule seen from the window's start: the value in force at the start
    (the last change at or before it, compared in integer milliseconds) at t = 0, then each later
    change inside the window at its re-based grid time."""
    rows = sorted(schedule, key=lambda r: ms_of(r["time"]))
    first = rows[0]["availability"]
    for row in rows:
        if ms_of(row["time"]) <= start_ms:
            first = row["availability"]
    out = [dict(time=0.0, availability=float(first))]
    for row in rows:
        m = ms_of(row["time"])
        if start_ms < m <= end_ms:
            at = grid_time(m - start_ms, step_ms, dt)
            out.append(dict(time=at, availability=row["availability"]))
    return out


def start_state(window, k, span=None):
    """Rule (b): H2 at dt = 2^-k ms over the window, whose declared initial values are R3's saved
    state at the window's start; and the import's record (provenance and its check). span (start,
    end) in ms replaces the window for development smokes only."""
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.definitions.specs import parse_spec
    from cells.models import surface_pump_projective as projective
    from cells.registry.models import get_model
    from validation.long_duration import worlds
    from validation.tissue.excitable_import import CONTROL_GROUPS, carry_amounts

    if span is None:
        w = registration()["H2"]["windows"][window]
        start_ms, end_ms = int(w["start_ms"]), int(w["end_ms"])
    else:
        start_ms, end_ms = (int(v) for v in span)
    path, r3, provenance = source()
    r3_spec = parse_spec(worlds.h2(r3["dt_s"]))
    model = get_model(r3_spec.model)
    _, p0 = model.initial_values(r3_spec)
    with np.load(path) as archive:
        times = archive["times"]
        found = np.flatnonzero(times == start_ms * 1e-3)
        if len(found) != 1:
            raise ImportRefused(f"R3 has no kept row at {start_ms} ms")
        row = model.STATE_TYPE(*(np.array(archive[f][found[0]]) for f in model.STATE_TYPE._fields))
    ci, co = (np.asarray(v) for v in model.physical_amounts(row, p0))
    step_ms, dt = Fraction(1, 2**k), 1e-3 / 2**k
    raw = worlds.h2(dt)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    species = [s["id"] for s in m["species"]]
    valence = [s["valence"] for s in m["species"]]
    carry_amounts(m["cells"], ci[:, : len(m["cells"])], np.zeros_like(ci), species, valence)
    carry_amounts(m["extracellular"], co[:, : len(m["extracellular"])], np.zeros_like(co),
                  species, valence)  # fmt: skip
    gates = np.asarray(row.channel_gate)
    for j, c in enumerate(m["channels"]):
        c["initial_gate"] = [float(g) for g in gates[: len(c["initial_gate"]), j]]
    if m.get("junctions") or np.asarray(row.junction_gate).size:
        raise ImportRefused("H2 declares no junctions; a junction gate would not be carried")
    for group, _ in (*CONTROL_GROUPS, ("junction_controls", "junction_id")):
        for control in e.get(group, []):
            control["schedule"] = retimed(control["schedule"], start_ms, end_ms, step_ms, dt)
    length = end_ms - start_ms
    e["end_time"] = grid_time(length, step_ms, dt)
    e["observation_times"] = [grid_time(i, step_ms, dt) for i in range(length + 1)]
    x["max_steps"] = int(Fraction(length) / step_ms) + 8
    # The import's check: the definition's initial state against R3's row, before any step.
    spec = parse_spec(raw)
    state, p = model.initial_values(spec)
    c1, o1 = (np.asarray(v) for v in model.physical_amounts(state, p))
    check = dict(
        amounts_cells_max_abs_fmol=float(np.max(np.abs(c1 - ci))),
        amounts_extracellular_max_abs_fmol=float(np.max(np.abs(o1 - co))),
        gates_max_abs=float(np.max(np.abs(np.asarray(state.channel_gate) - gates))),
        voltage_max_abs_V=float(np.max(np.abs(np.asarray(projective.membrane_voltage(state, p))
                                              - np.asarray(projective.membrane_voltage(row, p0))))),
    )  # fmt: skip
    record = dict(
        rule="(b): a new run of H2 whose initial values are R3's saved state; no continuity with "
        "R3 is claimed",
        source=provenance,
        start_ms=start_ms,
        end_ms=end_ms,
        carried=["amounts (cells and extracellular)", "the charges that follow", "channel gates"],
        ledgers="start at zero",
        import_check=check,
    )
    return raw, record


# ------------------------------------------------------------------ definitions


def definition(arm, x2=True, development=None):
    """The arm's raw definition and its extra record (import provenance, the times it declares).
    development: dict(span=(start, end) ms for a window, or end_ms) for smokes only."""
    from validation.long_duration import rung0, worlds

    world, kind, step_ms, dt, window, k = parse_arm(arm)
    extra = {}
    if world == "H2" and kind == "window" and window == "WN":
        raw = rung0.window_raw("WN", k)  # Rung 0's WN definition, unchanged (no import).
    elif world == "H2" and kind == "window":
        raw, extra["import"] = start_state(window, k, (development or {}).get("span"))
    elif world == "H2":
        end_ms = H2_END_MS if kind == "full" else SLOW_END_MS
        end_ms = (development or {}).get("end_ms", end_ms)
        raw = worlds.h2(dt)
        e, x = raw["experiment"], raw["execution"]
        r3_ms = [ms_of(t) for t in worlds.harness_observation_times()]
        rows = [m for m in r3_ms if m <= end_ms and Fraction(m) % step_ms == 0]
        e["end_time"] = grid_time(end_ms, step_ms, dt)
        e["observation_times"] = [grid_time(m, step_ms, dt) for m in rows]
        for group in e["channel_controls"]:
            group["schedule"] = [
                dict(c, time=grid_time(ms_of(c["time"]), step_ms, dt))
                for c in group["schedule"]
                if ms_of(c["time"]) <= end_ms
            ]
        x["max_steps"] = int(Fraction(end_ms) / step_ms) + 8
        extra["cue_s"] = [c["time"] for g in e["channel_controls"] if g["channel_id"] == "cue_0"
                          for c in g["schedule"]]  # fmt: skip
    else:
        end_ms = (development or {}).get("end_ms", W0_END_MS)
        rows = sorted({
            *range(0, W0_END_MS + 1, 1000),
            *range(W0_DOSE_MS + 10, W0_DOSE_MS + 2001, 10),
            *range(W0_WRITE_MS + 10, W0_WRITE_MS + 2001, 10),
        })  # fmt: skip
        rows = [m for m in rows if m <= end_ms and Fraction(m) % step_ms == 0]
        dose, write = (grid_time(m, step_ms, dt) if m < end_ms else None
                       for m in (W0_DOSE_MS, W0_WRITE_MS))  # fmt: skip
        raw = worlds.w0(end=grid_time(end_ms, step_ms, dt), dt=dt,
                        observation_times=[grid_time(m, step_ms, dt) for m in rows],
                        dose=dose, write=write)  # fmt: skip
        extra["interventions_s"] = dict(dose=dose, write=write)
    if raw["execution"].get("solver") != TODAY:
        raise ValueError(f"{arm}: the control runs {TODAY}, not {raw['execution'].get('solver')}")
    if x2:
        raw["execution"]["energy_check"] = x2_block()
    return raw, extra


# ------------------------------------------------------------------ one arm


def run(arm, out_dir, x2=True, development=None, solver=None):
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.definitions.specs import parse_spec
    from cells.execution import blas_threads
    from cells.execution.windows import WindowPolicy, run_windowed
    from validation.long_duration import harness

    reg = registration()
    world, kind, step_ms, dt, window, k = parse_arm(arm)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=False)
    record = dict(
        study="FR-8 rung 1, the control (D232; RUNG1_20261119.md §10.3)",
        arm=arm,
        world=world,
        kind=kind,
        window=window,
        k=k,
        step_ms=str(step_ms),
        dt_s=dt,
        integrator=TODAY,
        energy_check=x2_block() if x2 else None,
        fallback_ii=not x2,
        development=development,
        engine_models=reg["engine_models"]["H2" if world == "H2" else "W0"],
        registration=reg["registration"],
        judged=False,
        snapshot_revision=harness.snapshot_revision(),
        cpu_affinity=sorted(os.sched_getaffinity(0)),
        nice=os.nice(0),
        started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    started = time.perf_counter()
    keeper = None
    try:
        raw, extra = definition(arm, x2, development)
        if solver is not None:  # §6 and §10.15-10.17: the new ID set after the definition.
            raw["execution"]["solver"] = solver
            record["integrator"] = solver
        record.update(extra)
        (out / "definition.json").write_text(json.dumps(raw, indent=1) + "\n")
        spec = parse_spec(raw)
        keeper = harness.Keeper(spec.experiment.observation_times)
        policy = WindowPolicy(window_steps=reg["window_steps"], row_checks="device")
        result = run_windowed(spec, policy, sink=keeper)
        record.update(
            status="complete",
            steps=int(result.resources["executed_steps"]),
            off_nominal_boundaries=int(result.resources["resident_off_nominal_events"]),
            energy_check_summary=result.resources.get("energy_check"),
            timings={key: float(v) for key, v in result.timings.items()},
            diagnostics={key: float(v) for key, v in result.diagnostics.items()},
            row_checks=json.loads(json.dumps(result.resources.get("row_checks"), default=str)),
            blas=blas_threads.libraries(),
        )
    except Exception as error:  # A refusal is a result, kept (§0).
        record.update(status="refused", error_type=type(error).__name__, error=str(error))
    record["seconds"] = time.perf_counter() - started
    if keeper is not None and keeper.rows:
        times = np.asarray(sorted(keeper.rows))
        columns = list(zip(*(keeper.rows[t] for t in times), strict=True))
        rows = {name: np.stack(v) for name, v in zip(keeper.fields, columns, strict=True)}
        np.savez_compressed(out / "rows.npz", times=times, **rows)
        record.update(rows_kept=len(times), last_row_s=float(times[-1]),
                      rows_partial=record["status"] != "complete")  # fmt: skip
    (out / "run.json").write_text(json.dumps(record, indent=1, default=str) + "\n")
    keys = ("arm", "status", "steps", "seconds", "error")
    print(json.dumps({key: record.get(key) for key in keys}))
    return 0 if record["status"] == "complete" else 1


# ------------------------------------------------------------------ the readings (§4, §5, §10)

CLASS_KEYS = ("voltage", "concentration", "gate")
SCALES = dict(voltage=0.1, concentration=1.0, gate=1.0)  # Rung 0's floor scales.
B_P = dict(voltage=2e-5, concentration=2e-4, gate=None)  # The method's bar (§10.1); gates: info.
B_A = dict(voltage=2e-6, concentration=2e-5, gate=1e-5)  # The reference's bar (§10.1).
BARS = dict(B_P=B_P, B_A=B_A)
LEVEL_V, CROSSING_S, PEAK_RELATIVE = -0.05, 5e-4, 1e-3  # Stage 0's §5.3 event criteria.
CUE_MS, CUE_OFF_MS, RECOVERY_THROUGH_MS = 1_800_000, 1_800_300, 1_830_000
WA_SPAN_MS = (1_799_990, 1_801_000)
RUNG0_ROOTS = dict(
    window="/mnt/workspaces/Cells/fr8-rung0-20261119/records-cf1ca34b",
    WN="/mnt/workspaces/Cells/fr8-rung0-20261119/records-58c336c0",
)
STAGE0_HARNESS = "/mnt/workspaces/Cells/fr8-stage0-20261118/records-24e516c7/harness"
HISTORY_FLOORS = (("_pJ", 2e-8), ("_C", 3e-25))  # Else amounts and cycles: 1e-10 fmol.
# The engine's refusals that are an arm's result (§0, §10.5): every run-time NumericalError (a
# step's domain failure, X2, a row's ledgers), and a ConfigError only from a step bound. Any other
# exception (admission, grid, observation, trace limits, the driver's own) is unclassified: a fault.
STEP_BOUND_MESSAGES = ("step exceeds", "requires a smaller step", "exceeds the explicit-rate bound")
X2_MESSAGE = "Step-doubled energy check failed"


def load_rows(directory):
    """(record, rows dict with 'times') of an arm directory; rows is None without kept rows."""
    directory = Path(directory)
    record = json.loads((directory / "run.json").read_text())
    path = directory / "rows.npz"
    if not path.is_file():
        return record, None
    with np.load(path) as archive:  # Each array once: an indexed npz decompresses per access.
        return record, {f: archive[f] for f in archive.files}


def model_of(raw):
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.definitions.specs import parse_spec
    from cells.registry.models import get_model

    spec = parse_spec(raw)
    model = get_model(spec.model)
    return model, model.initial_values(spec)[1]


def classes(raw, rows):
    """Per row: voltages [patch], concentrations [species, cell] and gates [flat], from the
    engine's own readouts on the definition's own layout (H2: @3; W0: the composite's inner
    view)."""
    from cells.models import surface_pump_projective as projective

    model, p = model_of(raw)
    composite = hasattr(model, "inner_state")
    fields = model.STATE_TYPE._fields
    out = dict(voltage=[], concentration=[], gate=[])
    for i in range(len(rows["times"])):
        row = model.STATE_TYPE(*(rows[f][i] for f in fields))
        if composite:
            state, view = model.inner_state(row), model.view(p, row, xp=np)
            ci, _ = model.inner.physical_amounts(state, view)
        else:
            state, view = row, p
            ci, _ = model.physical_amounts(row, p)
        cells = np.asarray(view.active, dtype=bool)
        out["voltage"].append(np.asarray(projective.membrane_voltage(state, view)))
        out["concentration"].append(np.asarray(ci)[:, cells] / np.asarray(view.volume)[cells])
        gates = [np.asarray(state.channel_gate)[np.asarray(view.channel_gate_active, dtype=bool)]]
        if np.asarray(state.junction_gate).size:
            gates.append(np.asarray(state.junction_gate)[np.asarray(view.junction_active, bool)])
        out["gate"].append(np.concatenate(gates))
    return {key: np.asarray(v) for key, v in out.items()}


def difference(a, b, key):
    """Per row: the largest |a - b| over a class's entries (relative for concentration)."""
    d = np.abs(np.asarray(a) - np.asarray(b))
    if key == "concentration":
        d = d / np.abs(np.asarray(b))
    return d.reshape(len(d), -1).max(axis=1, initial=0.0)


def floor_of(key, steps):
    return registration()["order"]["readable_factor"] * np.asarray(steps, float) * EPS * SCALES[key]


def bound(d_coarse, d_fine, floor_coarse, floor_fine, tenth):
    """A reference's error bound at a row and class (§3, §10.4, §10.6), or None (undetermined):
    its finest ladder difference where the order from its three finest arms is at least 1; its
    floor where that difference sits at or below it; with no order (below 1), its larger
    difference or floor only if that is at most `tenth`, a tenth of the adequacy bar for its
    class (stage 0's own ratio); otherwise undetermined."""
    if d_fine <= floor_fine:
        return floor_fine
    if d_coarse > floor_coarse and d_coarse >= 2.0 * d_fine:  # log2(coarse / fine) >= 1.
        return d_fine
    spread = max(d_coarse, d_fine, floor_fine)
    return spread if spread <= tenth else None


class Series:
    """A trajectory at integer-millisecond rows: its classes, its steps from its start, its
    record. start_ms: where its steps start; offset_ms: added to its row times (a re-based
    window's start; 0 for absolute times; by default start_ms)."""

    def __init__(self, directory, raw=None, start_ms=0, steps_per_ms=1.0, offset_ms=None):
        self.directory = Path(directory)
        self.record, self.rows = load_rows(directory)
        self.complete = self.record.get("status", "complete") == "complete"
        self.start_ms, self.steps_per_ms = start_ms, float(steps_per_ms)
        self.offset_ms = start_ms if offset_ms is None else offset_ms
        if self.rows is None:
            self.ms, self.c, self.times = np.zeros(0, dtype=np.int64), None, np.zeros(0)
            return
        if raw is None:
            raw = json.loads((self.directory / "definition.json").read_text())
        self.raw = raw
        self.ms = np.asarray([self.offset_ms + ms_of(t) for t in self.rows["times"]], np.int64)
        self.times = self.offset_ms * 1e-3 + np.asarray(self.rows["times"], dtype=float)
        self.c = classes(raw, self.rows)
        self.index = {int(m): i for i, m in enumerate(self.ms)}

    def at(self, ms):
        return np.asarray([self.index[int(m)] for m in ms], dtype=np.int64)

    def steps(self, ms):
        return (np.asarray(ms, dtype=np.int64) - self.start_ms) * self.steps_per_ms


def subset(series, keep):
    """The series at the rows a boolean mask over its rows keeps (a judge's second row set)."""
    s = copy.copy(series)
    s.rows = {k: np.asarray(v)[keep] for k, v in series.rows.items()}
    s.ms, s.times = series.ms[keep], series.times[keep]
    s.c = classes(series.raw, s.rows)
    s.index = {int(m): i for i, m in enumerate(s.ms)}
    return s


class Ladder:
    """A reference (finest) and its two coarser arms: the §3 bound per row and class."""

    def __init__(self, coarse, middle, finest, name):
        self.coarse, self.middle, self.finest, self.name = coarse, middle, finest, name

    def has(self, m):
        return int(m) in self.finest.index

    def bounds(self, ms):
        ic, im, i_f = (s.at(ms) for s in (self.coarse, self.middle, self.finest))
        out = {}
        for key in CLASS_KEYS:
            dc = difference(self.coarse.c[key][ic], self.middle.c[key][im], key)
            df = difference(self.middle.c[key][im], self.finest.c[key][i_f], key)
            fc, ff = floor_of(key, self.middle.steps(ms)), floor_of(key, self.finest.steps(ms))
            e = np.asarray([b if (b := bound(*v, B_A[key] / 10)) is not None else np.nan
                            for v in zip(dc, df, fc, ff, strict=True)])  # fmt: skip
            out[key] = dict(bound=e, d_coarse=dc, d_fine=df, floor_coarse=fc, floor_fine=ff)
        return out


def decide(delta, e, budget, key):
    """One row and class (§4; §10.1: B_A judges the reference's bound): 'pass', 'fail',
    'undetermined', or 'info' where the bar has no cap for the class."""
    if budget is None:
        return "info"
    if not np.isfinite(e) or e > B_A[key]:
        return "undetermined"
    if delta + e <= budget:
        return "pass"
    if delta - e > budget:
        return "fail"
    return "undetermined"


def compare(arm, parts, ms):
    """The arm's rows `ms` against their references: parts is [(ladder, mask over ms, extra
    bound per class or None)]. Per class: deltas, bounds and the reference refinement."""
    n = len(ms)
    out = {key: dict(delta=np.full(n, np.nan), bound=np.full(n, np.nan),
                     d_coarse=np.full(n, np.nan), d_fine=np.full(n, np.nan),
                     floor_fine=np.full(n, np.nan)) for key in CLASS_KEYS}  # fmt: skip
    for ladder, mask, extra in parts:
        if not mask.any():
            continue
        sub = ms[mask]
        ia, ir = arm.at(sub), ladder.finest.at(sub)
        b = ladder.bounds(sub)
        for key in CLASS_KEYS:
            out[key]["delta"][mask] = difference(arm.c[key][ia], ladder.finest.c[key][ir], key)
            e = b[key]["bound"] + (0.0 if extra is None else extra[key](sub))
            out[key]["bound"][mask] = e
            for name in ("d_coarse", "d_fine", "floor_fine"):
                out[key][name][mask] = b[key][name]
    return out


def verdict_rows(table, ms, bar):
    """The rows' verdict under a bar: fail (with its first failing row), undetermined, or pass."""
    first_fail, undetermined = None, 0
    for key in CLASS_KEYS:
        for j, (d, e) in enumerate(zip(table[key]["delta"], table[key]["bound"], strict=True)):
            v = decide(d, e, BARS[bar][key], key)
            if v == "fail" and (first_fail is None or ms[j] < first_fail["ms"]):
                first_fail = dict(ms=int(ms[j]), cls=key, value=float(d), bound=float(e),
                                  budget=BARS[bar][key])  # fmt: skip
            undetermined += v == "undetermined"
    if first_fail:
        return dict(verdict="fail", cause=dict(kind="breach", **first_fail))
    if undetermined:
        return dict(verdict="undetermined", undetermined_row_classes=undetermined)
    return dict(verdict="pass")


REFUSAL_KINDS = (  # (message fragment, what stops the rung); X2's kinds kept apart (§10.6).
    ("exceeds the registration's cap", "X2: the per-row integration-error cap (the cap binds)"),
    ("out-of-band steps are held", "X2: the whole-run count of out-of-band held steps"),
    ("the order condition", "X2: the whole-run order band of the step ratio"),
    ("corrected residual exceeds", "X2: the per-row allowance (a misbooking's signature)"),
    ("held step's change exceeds", "X2: a held step's change above today's bound"),
    ("non-finite residual", "X2: a non-finite residual, flow or magnitude"),
    ("domain failure", "the step's own check (its domain, with the membrane-rate ceiling)"),
    ("Resolved junction step exceeds", "the junction-gate bound (definition)"),
    ("explicit-rate stability bound", "the explicit-rate bound (definition)"),
    ("calcium pump rate bound", "the calcium pump bound (definition)"),
    ("kind's explicit-rate bound", "a kind's explicit-rate bound (definition)"),
    ("accounting failed", "a row's ledger checks"),
    ("Invalid resolved inventory", "a row's inventory checks"),
    ("dissipation cannot be negative", "a row's dissipation check"),
    ("observation field failed", "a row's field check"),
)


def refusal_of(record):
    """An incomplete arm's verdict and what stopped it: the engine's refusal (a result, of a
    named kind), or an unclassified fault."""
    error_type, message = record.get("error_type"), str(record.get("error") or "")
    result = error_type == "NumericalError" or (
        error_type == "ConfigError" and any(m in message for m in STEP_BOUND_MESSAGES)
    )
    named = next((label for fragment, label in REFUSAL_KINDS if fragment in message), None)
    cause = dict(
        kind="refusal" if result else "unclassified (a fault)",
        stops=named if result else None,
        error_type=error_type,
        message=record.get("error"),
        last_row_s=record.get("last_row_s"),
        x2=message.startswith(X2_MESSAGE),
        x2_cap_binds=result and "exceeds the registration's cap" in message,
    )
    return dict(verdict="fail" if result else "fault", cause=cause)


def worst(verdicts):
    for v in ("fault", "fail", "undetermined"):
        if v in verdicts:
            return v
    return "pass"


# ------------------------------------------------------------------ references


def rung0_ladder(window):
    from validation.long_duration import rung0

    raw = rung0.window_raw(window, 0)
    start = 0 if window == "WN" else int(registration()["H2"]["windows"][window]["start_ms"])
    root = Path(RUNG0_ROOTS["WN" if window == "WN" else "window"]) / window
    arms = [Series(root / f"k{k}", raw, start, 2**k, offset_ms=0) for k in (7, 8, 9)]
    return Ladder(*arms, f"rung 0's {window} k = 7-9")


def stage0_ladder():
    from validation.long_duration import worlds

    arms = [Series(Path(STAGE0_HARNESS) / name, worlds.h2(dt), 0, per)
            for name, dt, per in (("R1", 1e-3, 1), ("R2", 5e-4, 2), ("R3", 2.5e-4, 4))]  # fmt: skip
    return Ladder(*arms, "stage 0's R1-R3")


def w0_ladder(root):
    arms = [Series(Path(root) / f"W0-{q}", None, 0, per)
            for q, per in (("0.5", 2), ("0.25", 4), ("0.125", 8))]  # fmt: skip
    return Ladder(*arms, "W0 at 0.5, 0.25 and 0.125 ms")


def window_start(window):
    return 0 if window == "WN" else int(registration()["H2"]["windows"][window]["start_ms"])


def window_arm(root, window, k, sub=""):
    return Series(Path(root) / sub / f"H2-{window}-k{k}", None, window_start(window), 2**k)


# ------------------------------------------------------------------ events (§10.1, §10.2)


def events(times_s, v0, through_ms=RECOVERY_THROUGH_MS):
    """Cell_0's pre-value at 1800 s, its peak response after it, its first two crossings of -50 mV
    after it and its recovery times (stage 0's §5.3), on the rows given."""
    from validation.long_duration import harness_judge as hj

    t, v = np.asarray(times_s, dtype=float), np.asarray(v0, dtype=float)
    at = np.flatnonzero(np.round(t * 1000).astype(np.int64) == CUE_MS)
    if not len(at):
        return None
    pre = float(v[at[0]])
    after = np.flatnonzero(t > CUE_MS * 1e-3 + 1e-9)
    peak_i = after[np.argmax(np.abs(v[after] - pre))]
    through = min(through_ms * 1e-3, float(t[-1]))
    return dict(
        pre_V=pre,
        peak_V=float(abs(v[peak_i] - pre)),
        peak_ms=int(round(t[peak_i] * 1000)),
        crossings=hj.crossings(t, v, LEVEL_V, CUE_MS * 1e-3)[:2],
        recovery_s={
            f"{d * 1e3:g}_mV": hj.recovery_time(t, v, pre, d, CUE_OFF_MS * 1e-3, through)
            for d in (1e-3, 1e-4)
        },
    )


def series_events(s):
    return events(s.times, s.c["voltage"][:, 0])


def decide_event(diff, e, criterion):
    if e is None or not np.isfinite(e):
        return "undetermined"
    if diff + e <= criterion:
        return "pass"
    if diff - e > criterion:
        return "fail"
    return "undetermined"


def ladder_events(ladder):
    """The reference's events on its three arms, with the bounds of its peak and crossing times
    (§10.5, §10.6: the same rule as rows, the tenth being a tenth of stage 0's event criterion;
    the peak's floor is twice the voltage floor at its row, a crossing time's is the voltage floor
    over the reference's slope between its bracketing rows)."""
    ev = [series_events(s) for s in (ladder.coarse, ladder.middle, ladder.finest)]
    c, m, f = ev
    peak_ms = [f["peak_ms"]]
    fv_m = 2 * float(floor_of("voltage", ladder.middle.steps(peak_ms))[0])
    fv_f = 2 * float(floor_of("voltage", ladder.finest.steps(peak_ms))[0])
    f["peak_bound_V"] = bound(abs(c["peak_V"] - m["peak_V"]), abs(m["peak_V"] - f["peak_V"]),
                              fv_m, fv_f, PEAK_RELATIVE * f["peak_V"] / 10)  # fmt: skip
    t, v = ladder.finest.times, ladder.finest.c["voltage"][:, 0]
    for j, (xc, xm, xf) in enumerate(zip(c["crossings"], m["crossings"], f["crossings"],
                                         strict=False)):  # fmt: skip
        i = int(np.searchsorted(t, xf["time_s"]))
        slope = abs((v[i] - v[i - 1]) / (t[i] - t[i - 1])) if 0 < i < len(t) else 0.0
        row_ms = [int(round(t[min(i, len(t) - 1)] * 1000))]
        floor_t = (float(floor_of("voltage", ladder.finest.steps(row_ms))[0]) / slope
                   if slope else math.inf)  # fmt: skip
        floor_tm = (float(floor_of("voltage", ladder.middle.steps(row_ms))[0]) / slope
                    if slope else math.inf)  # fmt: skip
        f["crossings"][j] = dict(xf, bound_s=bound(abs(xc["time_s"] - xm["time_s"]),
                                                   abs(xm["time_s"] - xf["time_s"]),
                                                   floor_tm, floor_t, CROSSING_S / 10))  # fmt: skip
    return f


def judge_events(arm_ev, ref_ev):
    """§10.1: the peak and the timing pairs against the reference, decided with its bounds; a
    pair located between rows over 1 ms apart takes no timing pass; recovery is reported."""
    from validation.long_duration import harness_judge as hj

    if arm_ev is None:
        return dict(verdict="fail", reason="no row at 1800 s")
    d_peak = abs(arm_ev["peak_V"] - ref_ev["peak_V"])
    crit = PEAK_RELATIVE * ref_ev["peak_V"]
    peak = dict(test_V=arm_ev["peak_V"], ref_V=ref_ev["peak_V"], test_ms=arm_ev["peak_ms"],
                ref_ms=ref_ev["peak_ms"], difference_V=d_peak, bound_V=ref_ev["peak_bound_V"],
                criterion_V=crit)  # fmt: skip
    peak["verdict"] = decide_event(d_peak, ref_ev["peak_bound_V"], crit)
    pairs, verdicts = [], []
    a, b = arm_ev["crossings"], ref_ev["crossings"]
    for x, y in zip(a, b, strict=False):
        dt = abs(x["time_s"] - y["time_s"])
        located = hj.located(x, 1e-3) and hj.located(y, 1e-3)
        v = ("fail" if x["direction"] != y["direction"] or not located
             else decide_event(dt, y.get("bound_s"), CROSSING_S))  # fmt: skip
        pairs.append(dict(test_s=x["time_s"], ref_s=y["time_s"], difference_s=dt,
                          bound_s=y.get("bound_s"), test_spacing_s=x["spacing_s"],
                          ref_spacing_s=y["spacing_s"], located=located,
                          direction=[x["direction"], y["direction"]], verdict=v))  # fmt: skip
        verdicts.append(v)
    if len(a) != len(b):
        verdicts.append("fail")
    timing = dict(pairs=pairs, crossings_test=len(a), crossings_ref=len(b),
                  verdict=worst(verdicts or ["pass"]))  # fmt: skip
    return dict(peak=peak, timing=timing, verdict=worst([peak["verdict"], timing["verdict"]]),
                recovery=dict(test=arm_ev["recovery_s"], ref=ref_ev["recovery_s"]))  # fmt: skip


def w0_events(arm, ref):
    """Information (§10.1): per intervention, the peak over patches of |Vm - Vm(t)| from t to the
    next intervention or the end, against the reference's; and any crossing of -50 mV after it."""
    from validation.long_duration import harness_judge as hj

    out = {}
    for name, t0, t1 in (("dose", W0_DOSE_MS, W0_WRITE_MS), ("write", W0_WRITE_MS, W0_END_MS)):
        row = {}
        for label, s in (("test", arm), ("ref", ref)):
            i0 = s.index.get(t0)
            if i0 is None:
                row[label] = None
                continue
            v = s.c["voltage"]
            span = np.flatnonzero((s.ms > t0) & (s.ms <= t1))
            peak = float(np.max(np.abs(v[span] - v[i0]), initial=0.0)) if len(span) else None
            crossings = [c | dict(patch=j) for j in range(v.shape[1])
                         for c in hj.crossings(s.times, v[:, j], LEVEL_V, t0 * 1e-3)
                         if c["time_s"] <= t1 * 1e-3]  # fmt: skip
            row[label] = dict(peak_V=peak, crossings=crossings)
        if row.get("test") and row.get("ref") and row["ref"]["peak_V"]:
            row["relative_difference"] = (abs(row["test"]["peak_V"] - row["ref"]["peak_V"])
                                          / row["ref"]["peak_V"])  # fmt: skip
        out[name] = row
    return out


# ------------------------------------------------------------------ histories (§10.2)


def history_floor(name):
    for suffix, floor in HISTORY_FLOORS:
        if name.endswith(suffix):
            return floor
    return 1e-10


def histories(arm, parts, ms, base=None):
    """Information: each accumulator's largest |delta| / max(|ref|, floor) over the rows, against
    the reference's (a re-based window's as increments from its start: base, the reference row
    there)."""
    fields = json.loads((Path(STAGE0_HARNESS) / "R3" / "run.json").read_text())["history_fields"]
    out = {}
    for name in fields:
        if name not in arm.rows:
            continue
        best = dict(relative=0.0, ms=None)
        for ladder, mask, _ in parts:
            if not mask.any():
                continue
            sub = ms[mask]
            a = np.asarray(arm.rows[name])[arm.at(sub)]
            r = np.asarray(ladder.finest.rows[name])[ladder.finest.at(sub)]
            if base is not None:
                r = r - np.asarray(ladder.finest.rows[name])[ladder.finest.at([base])][0]
            rel = np.abs(a - r) / np.maximum(np.abs(r), history_floor(name))
            rel = rel.reshape(len(sub), -1).max(axis=1, initial=0.0)
            j = int(np.argmax(rel))
            if rel[j] > best["relative"]:
                best = dict(relative=float(rel[j]), ms=int(sub[j]))
        out[name] = best | dict(stage0_budget=2e-5, floor=history_floor(name))
    return out


# ------------------------------------------------------------------ the instrument (§5, §10.5)


def instrument(output, root):
    """I1a and I4, read before any reading: the re-based control at k = 9 against rung 0's k = 9
    on each window, and WA at k = 2 against R3's kept rows, within B_A at every row and class
    (§10.5); WN against rung 0's WN (X2 alone; reported). Writes OUTPUT (JSON) and the import's
    effect per row (OUTPUT.npz) that §10.5 carries into each window row's bound."""
    import jax

    jax.config.update("jax_enable_x64", True)
    from validation.long_duration import rung0

    out = dict(study="FR-8 rung 1, the control", I4=rung0.synthetic(), I1a={}, effect={})
    effects = {}
    for window in (*WINDOWS, "WN"):
        arm = window_arm(root, window, 9)
        used = "X2 on"
        if not arm.complete and Path(root, "x2-off", f"H2-{window}-k9").is_dir():
            arm, used = window_arm(root, window, 9, "x2-off"), "fallback (ii): X2 off"
        if not arm.complete:
            out["I1a"][window] = dict(passed=False, reason="the control at k = 9 is incomplete",
                                      record=refusal_of(arm.record))  # fmt: skip
            continue
        ref = rung0_ladder(window).finest
        ms = np.asarray([m for m in arm.ms if m in ref.index], dtype=np.int64)
        row, eff = dict(rows=len(ms), arm=used), {}
        for key in CLASS_KEYS:
            d = difference(arm.c[key][arm.at(ms)], ref.c[key][ref.at(ms)], key)
            eff[key] = d
            j = int(np.argmax(d))
            row[key] = dict(max=float(d[j]), at_ms=int(ms[j]), B_A=B_A[key],
                            within=bool(np.all(d <= B_A[key])))  # fmt: skip
        row["bitwise"] = bool(all(np.array_equal(arm.rows[f], ref.rows[f])
                                  for f in arm.rows if f != "times"))  # fmt: skip
        row["passed"] = all(row[key]["within"] for key in CLASS_KEYS)
        out["I1a"][window] = row
        effects[window] = (ms, eff)
    arm = window_arm(root, "WA", 2)
    if arm.complete:
        r3 = stage0_ladder().finest
        ms = np.asarray([m for m in arm.ms if m in r3.index], dtype=np.int64)
        row = dict(rows=len(ms))
        for key in CLASS_KEYS:
            d = difference(arm.c[key][arm.at(ms)], r3.c[key][r3.at(ms)], key)
            j = int(np.argmax(d))
            row[key] = dict(max=float(d[j]), at_ms=int(ms[j]), B_A=B_A[key],
                            within=bool(np.all(d <= B_A[key])))  # fmt: skip
        row["passed"] = all(row[key]["within"] for key in CLASS_KEYS)
    else:
        row = dict(passed=False, record=refusal_of(arm.record))
    out["I1a"]["WA_k2_against_R3"] = row
    out["passed"] = bool(out["I4"]["passed"] and all(
        out["I1a"][w].get("passed") for w in (*WINDOWS, "WA_k2_against_R3")))  # fmt: skip
    out["verdict"] = "validated" if out["passed"] else "instrument not validated"
    arrays = {}
    for w, (ms, eff) in effects.items():
        arrays[f"{w}_ms"] = ms
        arrays.update({f"{w}_{key}": v for key, v in eff.items()})
    np.savez_compressed(Path(output).with_suffix(".npz"), **arrays)
    Path(output).write_text(json.dumps(out, indent=1, default=float) + "\n")
    print(
        json.dumps(
            dict(verdict=out["verdict"], I1a={w: r.get("passed") for w, r in out["I1a"].items()})
        )
    )
    return 0 if out["passed"] else 1


def import_effect(instrument_output, window):
    """§10.5: the import's measured effect per row and class on a window, carried into its rows'
    bounds."""
    with np.load(Path(instrument_output).with_suffix(".npz")) as archive:
        ms = archive[f"{window}_ms"]
        eff = {key: archive[f"{window}_{key}"] for key in CLASS_KEYS}
    index = {int(m): i for i, m in enumerate(ms)}
    return {key: (lambda sub, key=key: np.asarray([eff[key][index[int(m)]] for m in sub]))
            for key in CLASS_KEYS}  # fmt: skip


# ------------------------------------------------------------------ the analysis


def dt_star(rungs):
    """rungs: [(step in ms, verdict, cause)] ascending. dt*: the largest rung passing with every
    finer rung passing (§4); what binds: the first rung above it that does not pass."""
    last = None
    for step, verdict, cause in rungs:
        if verdict == "pass":
            last = step
            continue
        out = dict(binds=dict(rung_ms=step, verdict=verdict, cause=cause))
        if verdict == "fail":
            return out | dict(dt_star_ms=last if last is not None else "none on the ladder")
        return out | dict(dt_star_ms="undetermined", at_least_ms=last)
    return dict(dt_star_ms=last, binds="the ladder's coarsest rung passes")


def arm_reading(arm, parts, ms_sets, extra_verdicts=()):
    """An arm's verdict per bar and row set ('common', 'own'), with its retention table."""
    if not arm.complete:
        r = refusal_of(arm.record)
        return {bar: {s: r for s in ms_sets} for bar in BARS}, None
    out, tables = {}, {}
    for name, ms in ms_sets.items():
        tables[name] = (ms, compare(arm, parts(ms), ms))
    for bar in BARS:
        out[bar] = {}
        for name, (ms, table) in tables.items():
            v = verdict_rows(table, ms, bar)
            for label, ev in extra_verdicts:  # Both causes are kept when both fail.
                if ev in ("fail", "undetermined") and worst([v["verdict"], ev]) == ev:
                    causes = [c for c in (v.get("cause"),) if c]
                    v = dict(verdict=ev, cause=dict(kind="events", which=label, also=causes))
            out[bar][name] = v
    return out, tables


def save_retention(directory, name, tables):
    """§10.3: per arm, the error at every row read and class, and the reference refinement."""
    arrays = {}
    for rows, (ms, table) in tables.items():
        arrays[f"{rows}_ms"] = ms
        for key, values in table.items():
            for field, v in values.items():
                arrays[f"{rows}_{key}_{field}"] = v
    np.savez_compressed(Path(directory) / f"{name}.npz", **arrays)


def reference_count(ladder):
    """§10.6: a reference ladder's rows by how their bound arises, per class (reported)."""
    ms = ladder.finest.ms
    b = ladder.bounds(ms)
    out = {}
    for key in CLASS_KEYS:
        e, df, ff = b[key]["bound"], b[key]["d_fine"], b[key]["floor_fine"]
        dc, fc = b[key]["d_coarse"], b[key]["floor_coarse"]
        ordered = (df > ff) & (dc > fc) & (dc >= 2.0 * df)
        out[key] = dict(rows=len(ms), at_floor=int((df <= ff).sum()), order_at_least_1=int(
            ordered.sum()), no_order_within_a_tenth=int((np.isfinite(e) & (df > ff) & ~ordered)
            .sum()), undetermined=int((~np.isfinite(e)).sum()),
            undetermined_ms=[int(m) for m in ms[~np.isfinite(e)][:20]])  # fmt: skip
    return out


def x2_of(arm):
    r = arm.record
    return dict(status=r.get("status"), steps=r.get("steps"), summary=r.get("energy_check_summary"),
                refusal=None if arm.complete else refusal_of(r)["cause"])  # fmt: skip


def analyse(output, root, instrument_output):
    """The control's readings (§4, §5, §10). Refuses unless the instrument was validated."""
    import jax

    jax.config.update("jax_enable_x64", True)
    check = json.loads(Path(instrument_output).read_text())
    if not check.get("passed"):
        raise SystemExit("the instrument was not validated: no reading is read (§5)")
    root = Path(root)
    retention = Path(output).with_suffix("")
    retention.mkdir(exist_ok=True)
    out = dict(study="FR-8 rung 1, the control (today's ID, X2 on)", instrument=check["verdict"],
               readings={}, arms={}, events={}, histories={}, orders={})  # fmt: skip
    stage0 = stage0_ladder()
    r0 = {w: rung0_ladder(w) for w in WINDOWS}
    effects = {w: import_effect(instrument_output, w) for w in WINDOWS}
    wa_events = ladder_events(r0["WA"])
    wa_events["recovery_s"] = series_events(stage0.finest)["recovery_s"]

    def full_parts(ms):
        span = (ms >= WA_SPAN_MS[0]) & (ms <= WA_SPAN_MS[1])
        return [(r0["WA"], span, None), (stage0, ~span, None)]

    # H2 (S): the slow-phase arms (§10.4), on R3's rows.
    rungs = {bar: {s: [] for s in ("common", "own")} for bar in BARS}
    for n in SLOW_MS:
        arm = Series(root / f"H2-slow-{n}", None, 0, 1.0 / n)
        ms_sets = dict(own=arm.ms, common=arm.ms[arm.ms % 10_000 == 0]) if arm.c is not None else {}
        verdicts, tables = arm_reading(arm, lambda ms: [(stage0, np.ones(len(ms), bool), None)],
                                       ms_sets or dict(own=None, common=None))  # fmt: skip
        if tables:
            save_retention(retention, f"H2-slow-{n}", tables)
            out["histories"][f"H2-slow-{n}"] = histories(
                arm, [(stage0, np.ones(len(arm.ms), bool), None)], arm.ms
            )
        out["arms"][f"H2-slow-{n}"] = dict(x2=x2_of(arm), readings=verdicts)
        for bar in BARS:
            for s in ("common", "own"):
                v = verdicts[bar][s]
                rungs[bar][s].append((n, v["verdict"], v.get("cause")))
    out["readings"]["H2 (S)"] = {
        bar: {s: dt_star(rungs[bar][s]) for s in rungs[bar]} for bar in BARS
    }

    # H2 (I): window rungs (k = 9..0) and the full runs through the cue.
    ladder_I = {bar: {s: [] for s in ("common", "own", "trajectory_only")} for bar in BARS}
    x2_dropped = []
    for k in range(9, -1, -1):
        step = 1.0 / 2**k
        comp = {bar: {s: [] for s in ladder_I[bar]} for bar in BARS}
        for window in WINDOWS:
            arm = window_arm(root, window, k)
            name = f"H2-{window}-k{k}"
            if not arm.complete and refusal_of(arm.record)["cause"]["x2"]:
                x2_dropped.append(name)  # Fallback (ii): this rung of this window leaves dt*.
                out["arms"][name] = dict(x2=x2_of(arm), left_dt_star="fallback (ii)")
                full = {0: "H2-full-1", 1: "H2-full-0.5", 2: "H2-full-0.25"}.get(k)
                if window == "WA" and not (full and (root / full).is_dir()):
                    # No event check at this rung (no full run carries it): never a pass (§10.1).
                    for bar in BARS:
                        for s in comp[bar]:
                            comp[bar][s].append(dict(verdict="undetermined", cause=dict(
                                kind="no event check", which="WA refused by X2")))  # fmt: skip
                continue
            ev_verdict = []
            if window == "WA" and arm.complete:
                ev = judge_events(series_events(arm), wa_events)
                out["events"][name] = ev
                ev_verdict = [("WA events", ev["verdict"])]
            ms_sets = (
                dict(own=arm.ms, common=arm.ms[arm.ms % 100 == 0])
                if arm.c is not None
                else dict(own=None, common=None)
            )
            extra = effects[window]
            parts = lambda ms, w=window, x=extra: [(r0[w], np.ones(len(ms), bool), x)]  # noqa: E731
            verdicts, tables = arm_reading(arm, parts, ms_sets, ev_verdict)
            traj, _ = arm_reading(arm, parts, dict(common=ms_sets["common"]))
            if tables:
                save_retention(retention, name, tables)
                out["histories"][name] = histories(
                    arm, parts(arm.ms), arm.ms, base=window_start(window)
                )
            out["arms"][name] = dict(x2=x2_of(arm), readings=verdicts)
            for bar in BARS:
                comp[bar]["common"].append(verdicts[bar]["common"])
                comp[bar]["own"].append(verdicts[bar]["own"])
                comp[bar]["trajectory_only"].append(traj[bar]["common"])
        full_name = {0: "H2-full-1", 1: "H2-full-0.5", 2: "H2-full-0.25"}.get(k)
        if full_name and (k == 0 or (root / full_name).is_dir()):  # 1 ms; fallback (ii)'s runs.
            arm = Series(root / full_name, None, 0, float(2**k))
            _, verdicts, traj = full_reading(arm, full_parts, out, retention, wa_events, full_name)
            for bar in BARS:
                comp[bar]["common"].append(verdicts[bar]["common"])
                comp[bar]["own"].append(verdicts[bar]["own"])
                comp[bar]["trajectory_only"].append(traj[bar]["common"])
        for bar in BARS:
            for s in ladder_I[bar]:
                if comp[bar][s]:
                    v = worst([c["verdict"] for c in comp[bar][s]])
                    cause = next((c.get("cause") for c in comp[bar][s] if c["verdict"] == v), None)
                    ladder_I[bar][s].append((step, v, cause))
    for n in FULL_MS[1:]:
        arm = Series(root / f"H2-full-{n}", None, 0, 1.0 / n)
        _, verdicts, traj = full_reading(arm, full_parts, out, retention, wa_events, f"H2-full-{n}")
        for bar in BARS:
            ladder_I[bar]["common"].append(
                (n, verdicts[bar]["common"]["verdict"], verdicts[bar]["common"].get("cause"))
            )
            ladder_I[bar]["own"].append(
                (n, verdicts[bar]["own"]["verdict"], verdicts[bar]["own"].get("cause"))
            )
            ladder_I[bar]["trajectory_only"].append(
                (n, traj[bar]["common"]["verdict"], traj[bar]["common"].get("cause"))
            )
    for bar in BARS:
        for s in ladder_I[bar]:
            ladder_I[bar][s].sort(key=lambda r: r[0])
    out["readings"]["H2 (I)"] = {
        bar: {s: dt_star(ladder_I[bar][s]) for s in ladder_I[bar]} for bar in BARS
    }
    out["fallback_ii"] = dict(window_rungs_refused_by_x2=x2_dropped,
                              needed=bool(x2_dropped))  # fmt: skip

    # W0 (S) and (I), against its own ladder at 0.5, 0.25 and 0.125 ms.
    w0 = w0_ladder(root)
    ladder_W = {r: {bar: {s: [] for s in ("common", "own")} for bar in BARS} for r in ("S", "I")}
    for q in W0_MS:
        step = float(Fraction(q))
        arm = Series(root / f"W0-{q}", None, 0, 1.0 / step)
        name = f"W0-{q}"
        for reading, limit in (("S", W0_DOSE_MS), ("I", W0_END_MS + 1)):
            if arm.c is not None:
                keep = arm.ms < limit
                ms_sets = dict(own=arm.ms[keep], common=arm.ms[keep & (arm.ms % 1000 == 0)])
            else:
                ms_sets = dict(own=None, common=None)
            verdicts, tables = arm_reading(
                arm, lambda ms: [(w0, np.ones(len(ms), bool), None)], ms_sets
            )
            if tables and reading == "I":
                save_retention(retention, name, tables)
                out["histories"][name] = histories(
                    arm, [(w0, np.ones(len(arm.ms), bool), None)], arm.ms
                )
                out["events"][name] = w0_events(arm, w0.finest)
            out["arms"].setdefault(name, dict(x2=x2_of(arm), readings={}))["readings"][reading] = (
                verdicts
            )
            for bar in BARS:
                for s in ("common", "own"):
                    v = verdicts[bar][s]
                    ladder_W[reading][bar][s].append((step, v["verdict"], v.get("cause")))
    for reading in ("S", "I"):
        out["readings"][f"W0 ({reading})"] = {
            bar: {s: dt_star(ladder_W[reading][bar][s]) for s in ("common", "own")} for bar in BARS
        }

    out["orders"] = orders(root)
    # §10.6: until the in-world plants are run, no claimed step has X2's sensitivity shown in its
    # world; X2's refusals are reported by kind, and only the per-row cap is "the cap binds".
    for reading in out["readings"].values():
        for bar in reading.values():
            for result in bar.values():
                if isinstance(result.get("dt_star_ms"), (int, float)):
                    result["x2_sensitivity"] = "not shown (the in-world plants are not yet run)"
    out["refusals_by_kind"] = {}
    for name, arm in out["arms"].items():
        refusal = (arm.get("x2") or {}).get("refusal")
        if refusal:
            out["refusals_by_kind"].setdefault(refusal.get("stops") or refusal["kind"], []).append(
                name
            )
    out["x2_cap_binds_today"] = sorted(
        name for name, arm in out["arms"].items()
        if ((arm.get("x2") or {}).get("refusal") or {}).get("x2_cap_binds")
    )  # fmt: skip
    out["reference_counts"] = {
        "W0": reference_count(w0),
        "R1-R3": reference_count(stage0),
        **{f"rung 0 {w}": reference_count(r0[w]) for w in WINDOWS},
    }
    Path(output).write_text(json.dumps(out, indent=1, default=float) + "\n")
    print(
        json.dumps(
            {k: {bar: v[bar]["common"] for bar in BARS} for k, v in out["readings"].items()},
            default=float,
        )[:3000]
    )
    return 0


def full_reading(arm, full_parts, out, retention, wa_events, name):
    """A full run through the cue (H2's (I)): rows against WA's ladder in its span and R3's
    elsewhere, with stage 0's events required (§10.1)."""
    if arm.c is None or not arm.complete:
        r = (
            refusal_of(arm.record)
            if not arm.complete
            else dict(verdict="fail", cause=dict(kind="no rows"))
        )
        v = {bar: {s: r for s in ("common", "own")} for bar in BARS}
        out["arms"][name] = dict(x2=x2_of(arm), readings=v)
        return None, v, v
    ev = judge_events(series_events(arm), wa_events)
    out["events"][name] = ev
    ms_sets = dict(own=arm.ms, common=arm.ms[arm.ms % 100 == 0])
    verdicts, tables = arm_reading(arm, full_parts, ms_sets, [("events", ev["verdict"])])
    traj, _ = arm_reading(arm, full_parts, dict(common=ms_sets["common"]))
    save_retention(retention, name, tables)
    out["histories"][name] = histories(arm, full_parts(arm.ms), arm.ms)
    out["arms"][name] = dict(x2=x2_of(arm), readings=verdicts, trajectory_only=traj)
    return ev["verdict"], verdicts, traj


def orders(root):
    """Also reported (§4): the order from sup-norm ratios, on each window's control arms (k = 0-9)
    and on the halving triples of the full, slow-phase and W0 arms, above rung 0's floor."""
    out = {}

    def triple(arms, ms):
        d = {}
        for key in CLASS_KEYS:
            (a, b, c) = arms
            dab = float(np.max(difference(a.c[key][a.at(ms)], b.c[key][b.at(ms)], key), initial=0))
            dbc = float(np.max(difference(b.c[key][b.at(ms)], c.c[key][c.at(ms)], key), initial=0))
            fb = float(floor_of(key, [b.steps([ms[-1]])[0]])[0])
            fc = float(floor_of(key, [c.steps([ms[-1]])[0]])[0])
            p = math.log2(dab / dbc) if dab > fb and dbc > fc else None
            d[key] = dict(D_coarse=dab, D_fine=dbc, p=p)
        return d

    for window in WINDOWS:
        arms = {k: window_arm(root, window, k) for k in range(10)}
        if all(a.complete and a.c is not None for a in arms.values()):
            ms = arms[9].ms
            out[window] = {f"k{k}-{k + 2}": triple((arms[k], arms[k + 1], arms[k + 2]), ms)
                           for k in range(8)}  # fmt: skip
    for label, names, per in (
        ("W0", ("0.5", "0.25", "0.125"), (2, 4, 8)),
        ("W0", ("1", "0.5", "0.25"), (1, 2, 4)),
        ("W0", ("2", "1", "0.5"), (0.5, 1, 2)),
        ("H2-slow", ("20", "10", "5"), (0.05, 0.1, 0.2)),
        ("H2-slow", ("200", "100", "50"), (0.005, 0.01, 0.02)),
        ("H2-slow", ("2000", "1000", "500"), (0.0005, 0.001, 0.002)),
        ("H2-full", ("20", "10", "5"), (0.05, 0.1, 0.2)),
    ):
        arms = [
            Series(Path(root) / f"{label}-{n}", None, 0, s) for n, s in zip(names, per, strict=True)
        ]
        if all(a.complete and a.c is not None for a in arms):
            common = sorted(set(arms[0].ms) & set(arms[1].ms) & set(arms[2].ms))
            out[f"{label} {'/'.join(names)} ms"] = triple(arms, np.asarray(common, np.int64))
    return out


# ------------------------------------------------------------------ the cost and the plant


def timed(arm, out_dir, reference_dir):
    """§10.1's cost reading: the dt* arm re-run (on the timed lane, by its runner script) and its
    rows against the arm's own, bitwise; seconds per simulated second from its record."""
    code = run(arm, out_dir)
    record = json.loads((Path(out_dir) / "run.json").read_text())
    _, mine = load_rows(out_dir)
    _, theirs = load_rows(reference_dir)
    same = mine is not None and theirs is not None and set(mine) == set(theirs) and all(
        np.array_equal(mine[f], theirs[f]) for f in mine)  # fmt: skip
    simulated = float(record.get("last_row_s") or 0.0) - (0.0)
    t = record.get("timings", {})
    fixed = t.get("preflight_seconds", 0.0) + t.get("window_compile_or_cache_seconds", 0.0)
    cost = dict(arm=arm, rows_bitwise_equal=bool(same), simulated_s=simulated,
                total_seconds=t.get("total_run_seconds"), preflight_and_compile_seconds=fixed,
                seconds_per_simulated_second=(t.get("total_run_seconds", 0.0) - fixed) / simulated
                if simulated else None,
                total_seconds_per_simulated_second=t.get("total_run_seconds", 0.0) / simulated
                if simulated else None, cpu_affinity=record.get("cpu_affinity"),
                void=not same)  # fmt: skip
    (Path(out_dir) / "cost.json").write_text(json.dumps(cost, indent=1) + "\n")
    print(json.dumps(cost))
    return code


PLANT_AT_MS = dict(H2=1_000_000, W0=10_000)  # §10.6: on every rung's grid, before any event.
PLANT_RELATIVE = 1e-6  # FR-3's registered size (site_occupancy_acceptance_plants.WORK_RELATIVE).
PLANT_FIELD, PLANT_SLOT, PLANT_RESUME_STEPS = "pump_dissipated_energy_pJ", 0, 10  # §10.7.
BINDING_MESSAGE = "does not hold its state's residual"


def inworld_plant(arm, output, at_ms=None, solver=None):
    """§10.7's plant in the arm's own world at the arm's step (the largest step claimed).

    The arm's registered definition runs at its full horizon through the scalar windows with its
    registered policy; the checkpoint at T is taken with checkpoint_at on the window holding T.
    The planted checkpoint (cell_0's pump heat, pump_dissipated_energy_pJ at membrane slot 0, x
    (1 + 1e-6)) and the unplanted one are resumed in the same definition with a 10-step window,
    then stopped. Sensitivity is shown when both tests hold: the binding at load (the planted
    resume refused with X2's binding message, the control resumed) and the in-step test, eps* =
    (floor_T + sum|a|_T / 16) / heat(T) <= 1e-6 (FR-18's plant model in evaluate_x). A world that
    cannot run the step is a result, not a miss. at_ms replaces T for development only. solver, when
    given, is set after the arm's definition is built, as §10.16's wrapper set N2's ID after
    rung1.definition returned (§10.20 (b)); the record names it and its route."""
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.definitions.specs import ConfigError, parse_spec
    from cells.execution import energy_check as energy
    from cells.execution.errors import NumericalError
    from cells.execution.windows import WindowPolicy, iter_windows
    from cells.registry.models import get_model
    from validation.long_duration import harness

    world, _, step_ms, dt, _, _ = parse_arm(arm)
    plant_ms = PLANT_AT_MS[world] if at_ms is None else int(at_ms)
    row = dict(arm=arm, world=world, step_ms=str(step_ms), dt_s=dt, plant_ms=plant_ms,
               development=at_ms is not None, field=PLANT_FIELD, slot=PLANT_SLOT,
               relative=PLANT_RELATIVE, energy_check=x2_block(), integrator=solver or TODAY,
               solver_route=None if solver is None else (
                   "set after rung1.definition returned (§10.16's route), not X2_QUALIFY_SOLVER"),
               snapshot_revision=harness.snapshot_revision(),
               started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))  # fmt: skip
    started = time.perf_counter()
    registered = WindowPolicy(window_steps=registration()["window_steps"], row_checks="device")
    short = WindowPolicy(window_steps=PLANT_RESUME_STEPS, row_checks="device")
    try:
        raw, _ = definition(arm)
        if solver is not None:  # §10.16's route: the ID set after the definition is built.
            raw["execution"]["solver"] = solver
        spec = parse_spec(raw)
        t = grid_time(plant_ms, step_ms, dt)
        cp = None
        for window in iter_windows(spec, registered):
            if window.final.time >= t:
                cp = window.checkpoint_at(t)
                break
        if cp is None:
            raise ConfigError(f"the run ended before the plant time {plant_ms} ms")
    except (NumericalError, ConfigError) as error:  # The world cannot run the step: a result.
        row.update(cannot_run=True, sensitivity="cannot run (a result, not a miss)",
                   error_type=type(error).__name__, error=str(error))  # fmt: skip
        return _plant_done(row, output, started)
    model = get_model(spec.model)
    row_terms, _ = energy.terms(model, spec, cp.layout)
    p = model.parameters(spec, cp.layout)
    r, f, m = (float(v) for v in jax.jit(row_terms)(cp.state, p))
    k = int(cp.step_index)
    floor = float(energy.floor(max(k, 1), m))
    s = float(cp.energy_check.sum_abs_a)
    values = np.asarray(getattr(cp.state, PLANT_FIELD)).copy()
    heat = float(values[PLANT_SLOT])
    values[PLANT_SLOT] = heat * (1.0 + PLANT_RELATIVE)
    planted = dataclasses.replace(cp, state=cp.state._replace(**{PLANT_FIELD: values}))

    def resumed(checkpoint):
        try:
            windows = iter_windows(spec, short, checkpoint)
            first = next(windows)
            windows.close()  # A 10-step window, then stop: no whole-run condition is decided.
            return dict(admitted=True, refusal=None, steps=int(first.final.step_index) - k)
        except (NumericalError, ConfigError) as error:
            return dict(admitted=False, refusal=f"{type(error).__name__}: {error}")

    control, plant_resume = resumed(cp), resumed(planted)
    eps_star = (floor + energy.KAPPA * s) / abs(heat) if heat else math.inf
    binding = bool(control["admitted"] and not plant_resume["admitted"]
                   and BINDING_MESSAGE in (plant_resume["refusal"] or ""))  # fmt: skip
    in_step = bool(eps_star <= PLANT_RELATIVE)
    row.update(
        steps_k=k, R_pJ=r, F_pJ=f, M_pJ=m, floor_pJ=floor, sum_abs_a_pJ=s, heat_pJ=heat,
        plant_pJ=abs(heat) * PLANT_RELATIVE, eps_star=eps_star, control=control,
        planted=plant_resume, binding_shown=binding, in_step_shown=in_step,
        sensitivity=("X2's sensitivity shown at this step" if binding and in_step
                     else f"binding shown; in-step eps* = {eps_star:.3g}" if binding
                     else "not shown"),
    )  # fmt: skip
    return _plant_done(row, output, started)


def _plant_done(row, output, started):
    row["seconds"] = time.perf_counter() - started
    Path(output).write_text(json.dumps(row, indent=1, default=float) + "\n")
    print(json.dumps({k: row.get(k) for k in ("arm", "sensitivity", "eps_star", "error")}))
    return 0


def plant(step_text, output):
    """§10.1 at the largest step claimed: FR-3's registered plant (X2's qualify_x2.run_plant),
    its world's step set to step_text ms. Its world refusing the step is a result, kept."""
    import functools

    import jax

    jax.config.update("jax_enable_x64", True)
    from validation.energy_step_doubling import qualify_x2
    from validation.tissue import site_occupancy_acceptance_fixtures as af

    _, dt = step_of(step_text)
    af.registered_world = functools.partial(af.registered_world, dt=dt)
    try:
        qualify_x2.run_plant(output)
        row = json.loads(Path(output).read_text())
        refusal = row["planted"]["refusal"] or ""
        row["caught"] = bool(
            row["control"]["admitted"]
            and not row["planted"]["admitted"]
            and "does not hold its state's residual" in refusal
        )
    except Exception as error:  # The plant's world refused at this step: a result, kept.
        row = dict(id="fr3plant-q1_eps_1e-1", caught=False, cannot_run=True,
                   error_type=type(error).__name__, error=str(error))  # fmt: skip
    row["step_ms"], row["dt_s"] = step_text, dt
    Path(output).write_text(json.dumps(row, indent=1, default=float) + "\n")
    print(json.dumps({k: row.get(k) for k in ("step_ms", "caught", "cannot_run", "error")}))
    return 0


# ------------------------------------------------------------- §10.8's calm probe (development)

CALM_FROM_MS, CALM_TO_MS = (
    1_000_000,
    1_790_000,
)  # Well past H2's start-up transient; before the cue.
CALM_STEPS = ("20", "50", "100", "200", "250")  # Up to the 292 ms explicit-rate bound.


def calm_start(source_dir, step_text):
    """Rule (b), development only (§10.8): H2 at the step from CALM_FROM_MS to CALM_TO_MS, whose
    declared initial values are the source arm's saved state at CALM_FROM_MS (the control's
    H2-slow-1); the source's sha256 and identity are recorded."""
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.definitions.specs import parse_spec
    from cells.registry.models import get_model
    from validation.long_duration import worlds
    from validation.tissue.excitable_import import CONTROL_GROUPS, carry_amounts

    source_dir = Path(source_dir)
    record = json.loads((source_dir / "run.json").read_text())
    rows_path = source_dir / "rows.npz"
    provenance = dict(
        rows=str(rows_path),
        rows_sha256=sha256(rows_path),
        arm=record.get("arm"),
        revision=record.get("snapshot_revision"),
        dt_s=record.get("dt_s"),
    )
    source_raw = json.loads((source_dir / "definition.json").read_text())
    model = get_model(parse_spec(source_raw).model)
    _, p0 = model.initial_values(parse_spec(source_raw))
    with np.load(rows_path) as archive:
        found = np.flatnonzero(np.round(archive["times"] * 1000).astype(np.int64) == CALM_FROM_MS)
        if len(found) != 1:
            raise ImportRefused(f"the source has no row at {CALM_FROM_MS} ms")
        row = model.STATE_TYPE(*(np.array(archive[f][found[0]]) for f in model.STATE_TYPE._fields))
    ci, co = (np.asarray(v) for v in model.physical_amounts(row, p0))
    step_ms, dt = step_of(step_text)
    raw = worlds.h2(dt)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    species = [s["id"] for s in m["species"]]
    valence = [s["valence"] for s in m["species"]]
    carry_amounts(m["cells"], ci[:, : len(m["cells"])], np.zeros_like(ci), species, valence)
    carry_amounts(m["extracellular"], co[:, : len(m["extracellular"])], np.zeros_like(co),
                  species, valence)  # fmt: skip
    gates = np.asarray(row.channel_gate)
    for j, c in enumerate(m["channels"]):
        c["initial_gate"] = [float(g) for g in gates[: len(c["initial_gate"]), j]]
    for group, _ in (*CONTROL_GROUPS, ("junction_controls", "junction_id")):
        for control in e.get(group, []):
            control["schedule"] = retimed(
                control["schedule"], CALM_FROM_MS, CALM_TO_MS, step_ms, dt
            )
    length = CALM_TO_MS - CALM_FROM_MS
    e["end_time"] = grid_time(length, step_ms, dt)
    e["observation_times"] = [grid_time(i, step_ms, dt) for i in range(0, length + 1, 10_000)]
    x["max_steps"] = int(Fraction(length) / step_ms) + 8
    x["energy_check"] = x2_block()
    return raw, dict(rule="(b), development only (§10.8)", source=provenance, from_ms=CALM_FROM_MS,
                     to_ms=CALM_TO_MS)  # fmt: skip


def calm_run(step_text, source_dir, out_dir):
    """One step of §10.8's calm probe: the re-based run with X2 on, its rows every 10 s."""
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.definitions.specs import parse_spec
    from cells.execution.windows import WindowPolicy, run_windowed
    from validation.long_duration import harness

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=False)
    record = dict(study="FR-8 rung 1, §10.8's calm probe (development, not a registered verdict)",
                  step_ms=step_text, energy_check=x2_block(), snapshot_revision=
                  harness.snapshot_revision(), cpu_affinity=sorted(os.sched_getaffinity(0)),
                  started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))  # fmt: skip
    started, keeper = time.perf_counter(), None
    try:
        raw, record["import"] = calm_start(source_dir, step_text)
        (out / "definition.json").write_text(json.dumps(raw, indent=1) + "\n")
        spec = parse_spec(raw)
        keeper = harness.Keeper(spec.experiment.observation_times)
        policy = WindowPolicy(window_steps=registration()["window_steps"], row_checks="device")
        result = run_windowed(spec, policy, sink=keeper)
        record.update(status="complete", steps=int(result.resources["executed_steps"]),
                      energy_check_summary=result.resources.get("energy_check"),
                      timings={k: float(v) for k, v in result.timings.items()})  # fmt: skip
    except Exception as error:  # A refusal is a result, kept.
        record.update(status="refused", error_type=type(error).__name__, error=str(error))
    record["seconds"] = time.perf_counter() - started
    if keeper is not None and keeper.rows:
        times = np.asarray(sorted(keeper.rows))
        columns = list(zip(*(keeper.rows[t] for t in times), strict=True))
        rows = {name: np.stack(v) for name, v in zip(keeper.fields, columns, strict=True)}
        np.savez_compressed(out / "rows.npz", times=times, **rows)
        record.update(rows_kept=len(times), last_row_s=float(times[-1]))
    (out / "run.json").write_text(json.dumps(record, indent=1, default=str) + "\n")
    print(json.dumps({k: record.get(k) for k in ("step_ms", "status", "steps", "error")}))
    return 0


def calm_read(output, root, source_dir):
    """§10.8's reading: per step, its status and refusal kind, X2's summary, and its rows against
    R3 (with R1-R3's bounds, under both bars) and against the source arm, over the calm window."""
    import jax

    jax.config.update("jax_enable_x64", True)
    stage0 = stage0_ladder()
    source = Series(source_dir, None, 0, 1.0)
    out = dict(study="§10.8's calm probe (development, information)", steps={})
    ladder = []
    for step in CALM_STEPS:
        d = Path(root) / f"calm-{step}"
        arm = Series(d, None, CALM_FROM_MS, 1.0 / float(Fraction(step)))
        entry = dict(x2=x2_of(arm))
        if arm.complete and arm.c is not None:
            ms = arm.ms
            table = compare(arm, [(stage0, np.ones(len(ms), bool), None)], ms)
            entry["readings"] = {bar: verdict_rows(table, ms, bar) for bar in BARS}
            entry["largest_vs_R3"] = {k: float(np.nanmax(v["delta"])) for k, v in table.items()}
            i_s = source.at(ms)
            entry["largest_vs_source"] = {
                key: float(np.max(difference(arm.c[key][arm.at(ms)], source.c[key][i_s], key)))
                for key in CLASS_KEYS
            }
        else:
            r = refusal_of(arm.record)
            entry["readings"] = {bar: r for bar in BARS}
        out["steps"][step] = entry
        ladder.append((float(Fraction(step)), entry["readings"]))
    for bar in BARS:
        rungs = [(s, r[bar]["verdict"], r[bar].get("cause")) for s, r in ladder]
        out[f"largest_{bar}"] = dt_star(rungs)
    Path(output).write_text(json.dumps(out, indent=1, default=float) + "\n")
    print(json.dumps({bar: out[f"largest_{bar}"] for bar in BARS}, default=float)[:1500])
    return 0


# ------------------------------------------------------------- §10.9's step change (development)

STEP_COARSE_MS, STEP_FINE_MS = 20, 1
STEP_WINDOW_MS = (1_799_980, 1_802_000)  # Holds the cue's edges and the crossing.
STEP_END_MS = 1_830_000


def step_change(out_dir, window=True):
    """§10.9 (development): H2 at a nominal 20 ms with 1 ms steps inside STEP_WINDOW_MS, made by
    no-op schedule entries (kir_0's availability kept at 1), with X2 on; X2's per-step record
    (EnergyRows) is kept for every step, and its whole-run decision at the end."""
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.definitions.specs import parse_spec
    from cells.execution import energy_check as energy
    from cells.execution.grid import EventGrid
    from cells.execution.windows import WindowPolicy, iter_windows
    from validation.long_duration import harness, worlds

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=False)
    dt = float(f"{STEP_COARSE_MS}e-3")
    n_end = STEP_END_MS // STEP_COARSE_MS
    raw = worlds.h2(dt)
    e, x = raw["experiment"], raw["execution"]
    end = n_end * dt
    e["end_time"] = end
    for group in e["channel_controls"]:
        group["schedule"] = [c for c in group["schedule"] if c["time"] <= end]
    fine = []
    if window:
        lo, hi = STEP_WINDOW_MS
        fine = [m * 1e-3 for m in range(lo + STEP_FINE_MS, hi, STEP_FINE_MS) if m % STEP_COARSE_MS]
        kir = next(g for g in e["channel_controls"] if g["channel_id"] == "kir_0")
        kir["schedule"] = kir["schedule"] + [dict(time=t, availability=1.0) for t in fine]
    e["observation_times"] = [0.0, end]
    x["max_steps"] = n_end + len(fine) + 8
    x["energy_check"] = x2_block()
    (out / "definition.json").write_text(json.dumps(raw) + "\n")
    spec = parse_spec(raw)
    grid = EventGrid(spec)
    record = dict(study="FR-8 rung 1, §10.9 (development): X2 across a step change",
                  window_ms=list(STEP_WINDOW_MS) if window else None, coarse_ms=STEP_COARSE_MS,
                  fine_ms=STEP_FINE_MS, extras=len(grid.extras), energy_check=x2_block(),
                  snapshot_revision=harness.snapshot_revision(),
                  started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))  # fmt: skip
    started = time.perf_counter()
    keys = ("counted", "q", "out_band", "ratio", "relative")
    steps = {key: [] for key in ("t0", "dt", *keys)}
    policy = WindowPolicy(window_steps=registration()["window_steps"], row_checks="device")
    last = None
    try:
        for w in iter_windows(spec, policy):
            last = w
            rows = w.final.energy_check.rows if w.final.energy_check is not None else None
            if rows is None:
                continue
            times = np.asarray(w.times, dtype=float)
            n = len(rows.q)
            steps["t0"].append(times[:n])
            steps["dt"].append(np.diff(times)[:n])
            for key in keys:
                steps[key].append(np.asarray(getattr(rows, key))[:n])
        record["status"] = "complete"
        record["summary"] = energy.summary(last.final.energy_check) if last else None
    except Exception as error:  # A refusal is a result, kept.
        record.update(status="refused", error_type=type(error).__name__, error=str(error),
                      refusal=refusal_of(dict(error_type=type(error).__name__, error=str(error)))[
                          "cause"])  # fmt: skip
    record["seconds"] = time.perf_counter() - started
    arrays = {k: np.concatenate(v) if v else np.zeros(0) for k, v in steps.items()}
    np.savez_compressed(out / "steps.npz", **arrays)
    record["regimes"] = step_regimes(arrays, window)
    record["switches"] = step_switches(arrays) if window else None
    (out / "run.json").write_text(json.dumps(record, indent=1, default=float) + "\n")
    print(json.dumps({k: record.get(k) for k in ("status", "error")}))
    return 0


def step_regimes(a, window):
    """Per regime: counted steps, held out-of-band, the median counted q, the largest per-row ratio
    and relative integration error."""
    lo, hi = (m * 1e-3 for m in STEP_WINDOW_MS)
    masks = {"20 ms before": a["t0"] < lo - 1e-9, "1 ms inside": (a["t0"] >= lo - 1e-9)
             & (a["t0"] < hi - 1e-9), "20 ms after": a["t0"] >= hi - 1e-9} if window else {
             "20 ms throughout": np.ones(len(a["t0"]), bool)}  # fmt: skip
    out = {}
    for name, m in masks.items():
        counted = a["counted"][m].astype(bool)
        q = a["q"][m][counted]
        out[name] = dict(
            steps=int(m.sum()),
            step_sizes_s=sorted({round(float(v), 9) for v in a["dt"][m]})[:4],
            counted=int(counted.sum()),
            held_out_of_band=int(a["out_band"][m].astype(bool).sum()),
            median_q=float(np.median(q)) if len(q) else None,
            q_outside_band=int(((q < 3.5) | (q > 4.6)).sum()),
            largest_ratio=float(np.max(a["ratio"][m], initial=0.0)),
            largest_relative=float(np.max(a["relative"][m], initial=0.0)),
        )
    return out


def step_switches(a, before=5, after=12):
    """At each switch, the steps around it: start, size, counted, q, held out of band, ratio."""
    out = {}
    for name, ms in (("to 1 ms", STEP_WINDOW_MS[0]), ("back to 20 ms", STEP_WINDOW_MS[1])):
        i = int(np.searchsorted(a["t0"], ms * 1e-3 - 1e-9))
        rows = []
        for j in range(max(0, i - before), min(len(a["t0"]), i + after)):
            rows.append(dict(t0=float(a["t0"][j]), dt=float(a["dt"][j]),
                             counted=bool(a["counted"][j]),
                             q=float(a["q"][j]) if np.isfinite(a["q"][j]) else None,
                             held_out_of_band=bool(a["out_band"][j]),
                             ratio=float(a["ratio"][j])))  # fmt: skip
        out[name] = rows
    return out


# ------------------------------------------------------------- §10.10: C's registered arm

C_COARSE_MS, C_FINE = 20, 1e-3
C_WINDOW = dict(start_time=1799.98, end_time=1802.0)
C_END_MS, C_ALL_FINE_STEPS = 3_600_000, 3_600_000  # Today's dt*(I), 1 ms, over the arm's horizon.
N2_FINAL = "cells.solver.imex_ars222_implicit_conductances@1"  # N2 with (a), the final ID (§10.20, §10.21).
# The registered windowed arms: H2 from 0 to 3600 s on the fine-window clock, X2 on. H2-N2C's
# window ends are the 100 ms grid's own products, 17999 x 0.1 and 18020 x 0.1, and its cue edges
# are re-declared at their grid products: the off-edge at 18003 x 0.1 = 1800.3000000000002, not
# the decimal 1800.3 that worlds.h2 declares (§10.20). H2-C's definition is unchanged.
WINDOWED = {
    "H2-C": dict(section="§10.10", study="C's registered arm", coarse_ms=C_COARSE_MS,
                 window=C_WINDOW, solver=TODAY, steps=181_919, regrid_cue=False),
    "H2-N2C": dict(section="§10.20", study="N2 with C's registered arm", coarse_ms=100,
                   window=dict(start_time=17999 * 0.1, end_time=18020 * 0.1), solver=N2_FINAL,
                   steps=38_079, regrid_cue=True),
}  # fmt: skip


def c_definition(arm="H2-C"):
    """A registered windowed arm (WINDOWED): H2 from 0 to 3600 s at its coarse step, with 1 ms
    inside its window (execution.fine_windows), under its ID, X2 on. §10.10's H2-C is today's
    integrator at 20 ms, [1799.98, 1802.00] s; §10.20's H2-N2C is the final N2 ID at 100 ms,
    [1799.9, 1802.0] s, its cue edges re-declared at their grid products. Its rows are R3's kept
    rows that are points of its own clock, read off EventGrid(spec); the cue's edges are checked
    to be points, and the clock to hold exactly the registered steps, before any run."""
    from cells.definitions.specs import ConfigError, parse_spec
    from cells.execution.grid import EventGrid
    from validation.long_duration import worlds

    a = WINDOWED[arm]
    dt = float(f"{a['coarse_ms']}e-3")
    n_end = C_END_MS // a["coarse_ms"]
    raw = worlds.h2(dt)
    e, x = raw["experiment"], raw["execution"]
    e["end_time"] = n_end * dt
    e["observation_times"] = [0.0, n_end * dt]
    x["max_steps"] = a["steps"] + 8
    x["energy_check"] = x2_block()
    if a["solver"] != TODAY:
        x["solver"] = a["solver"]
    if a["regrid_cue"]:  # §10.20: each cue edge at its grid product i x dt.
        for g in e["channel_controls"]:
            if g["channel_id"] == "cue_0":
                for c in g["schedule"]:
                    c["time"] = round(c["time"] / dt) * dt
    x["fine_windows"] = dict(
        method="cells.execution.fixed_fine_windows@1", dt=C_FINE, windows=[dict(a["window"])]
    )
    grid = EventGrid(parse_spec(raw))
    points = {grid[i] for i in range(len(grid))}
    cue = [c["time"] for g in e["channel_controls"] if g["channel_id"] == "cue_0"
           for c in g["schedule"]]  # fmt: skip
    if any(t not in points for t in cue):
        raise ConfigError(f"a cue edge is not a point of the clock: {cue}")
    if len(grid) - 1 != a["steps"]:
        raise ConfigError(f"{arm}: the clock holds {len(grid) - 1} steps, not {a['steps']}")
    r3 = worlds.harness_observation_times()
    rows = sorted(t for t in r3 if t in points)
    if a["regrid_cue"]:  # Read off the clock: R3's rows by their integer millisecond (§10.4).
        wanted = {ms_of(t) for t in r3}
        rows = sorted(t for t in points if ms_of(t) in wanted)
        if len({ms_of(t) for t in rows}) != len(rows):
            raise ConfigError(f"{arm}: two of its rows share an integer millisecond")
    e["observation_times"] = rows
    return raw, dict(clock_points=len(grid), rows=len(rows), cue_s=cue)


def c_run(out_dir, arm="H2-C"):
    """A registered windowed arm (WINDOWED), recorded as the control's arms are (definition, rows,
    run record)."""
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.definitions.specs import parse_spec
    from cells.execution import blas_threads
    from cells.execution.windows import WindowPolicy, run_windowed
    from validation.long_duration import harness

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=False)
    a = WINDOWED[arm]
    record = dict(study=f"FR-8 rung 1, {a['study']} ({a['section']})", arm=arm,
                  integrator=a["solver"], energy_check=x2_block(),
                  snapshot_revision=harness.snapshot_revision(),
                  cpu_affinity=sorted(os.sched_getaffinity(0)), nice=os.nice(0),
                  started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))  # fmt: skip
    started, keeper = time.perf_counter(), None
    try:
        raw, extra = c_definition(arm)
        record.update(extra, fine_windows=raw["execution"]["fine_windows"])
        (out / "definition.json").write_text(json.dumps(raw, indent=1) + "\n")
        spec = parse_spec(raw)
        keeper = harness.Keeper(spec.experiment.observation_times)
        policy = WindowPolicy(window_steps=registration()["window_steps"], row_checks="device")
        result = run_windowed(spec, policy, sink=keeper)
        record.update(
            status="complete",
            steps=int(result.resources["executed_steps"]),
            off_nominal_boundaries=int(result.resources["resident_off_nominal_events"]),
            fine_windows_record=json.loads(json.dumps(result.resources.get("fine_windows"),
                                                      default=str)),
            energy_check_summary=result.resources.get("energy_check"),
            timings={k: float(v) for k, v in result.timings.items()},
            blas=blas_threads.libraries(),
        )  # fmt: skip
    except Exception as error:  # A refusal is a result, kept.
        record.update(status="refused", error_type=type(error).__name__, error=str(error))
    record["seconds"] = time.perf_counter() - started
    if keeper is not None and keeper.rows:
        times = np.asarray(sorted(keeper.rows))
        columns = list(zip(*(keeper.rows[t] for t in times), strict=True))
        rows = {name: np.stack(v) for name, v in zip(keeper.fields, columns, strict=True)}
        np.savez_compressed(out / "rows.npz", times=times, **rows)
        record.update(rows_kept=len(times), last_row_s=float(times[-1]))
    (out / "run.json").write_text(json.dumps(record, indent=1, default=str) + "\n")
    print(json.dumps({k: record.get(k) for k in ("status", "steps", "seconds", "error")}))
    return 0


def c_timed(out_dir, reference_dir, arm="H2-C"):
    """(c)'s cost (§10.10, §10.20): the arm re-run (on the timed lane, by its runner script), its
    rows against the arm's, bitwise; seconds per simulated second from its record."""
    c_run(out_dir, arm)
    record = json.loads((Path(out_dir) / "run.json").read_text())
    _, mine = load_rows(out_dir)
    _, theirs = load_rows(reference_dir)
    same = mine is not None and theirs is not None and set(mine) == set(theirs) and all(
        np.array_equal(mine[f], theirs[f]) for f in mine)  # fmt: skip
    t = record.get("timings", {})
    fixed = t.get("preflight_seconds", 0.0) + t.get("window_compile_or_cache_seconds", 0.0)
    simulated = float(record.get("last_row_s") or 0.0)
    per = (t.get("total_run_seconds", 0.0) - fixed) / simulated if simulated else None
    cost = dict(
        rows_bitwise_equal=bool(same),
        simulated_s=simulated,
        total_seconds=t.get("total_run_seconds"),
        preflight_and_compile_seconds=fixed,
        seconds_per_simulated_second=per,
        cpu_affinity=record.get("cpu_affinity"),
        void=not same,
    )
    (Path(out_dir) / "cost.json").write_text(json.dumps(cost, indent=1) + "\n")
    print(json.dumps(cost))
    return 0


def c_judge(output, c_dir, full1_cost=None, c_cost=None, arm="H2-C", plant=None):
    """A windowed arm's verdict (§10.10 on H2-C, §10.20 on H2-N2C): (a) the (I) reading under B_P
    with the event criteria (B_A reported), on all of its rows and on the 100 ms common rows; (b)
    X2's decision and kind, and for H2-N2C the sensitivity standard, "binding shown, eps* reported",
    from (b)'s in-world plant record (plant); (c) the step-count gain over 1 ms, with the timed cost
    ratio beside it when given."""
    import jax

    jax.config.update("jax_enable_x64", True)
    arm_id, a = arm, WINDOWED[arm]  # Before `arm` names the arm's Series below.
    arm = Series(c_dir, None, 0, 1.0)
    study = "C's arm" if arm_id == "H2-C" else a["study"]
    out = dict(study=f"FR-8 rung 1, {study} judged under {a['section']}", arm=arm_id)
    # §10.24: the judge's own source, the snapshot it runs from (its runner's working directory).
    snap = Path.cwd() / "SNAPSHOT.json"
    meta = json.loads(snap.read_text()) if snap.is_file() else {}
    out["source"] = dict(snapshot=str(Path.cwd()) if meta else None,
                         git_revision=meta.get("git_revision"),
                         patch_sha256=meta.get("patch_sha256"),
                         driver=str(Path(__file__).resolve()))  # fmt: skip
    stage0 = stage0_ladder()
    wa = rung0_ladder("WA")
    wa_events = ladder_events(wa)
    wa_events["recovery_s"] = series_events(stage0.finest)["recovery_s"]

    def parts(ms):
        span = (ms >= WA_SPAN_MS[0]) & (ms <= WA_SPAN_MS[1])
        return [(wa, span, None), (stage0, ~span, None)]

    record = arm.record
    if not arm.complete or arm.c is None:
        out["verdict"] = dict(a="fail", b="fail", c=None, cause=refusal_of(record))
    else:
        ev = judge_events(series_events(arm), wa_events)
        sets = dict(own=arm.ms, common=arm.ms[arm.ms % 100 == 0])
        verdicts, tables = arm_reading(arm, parts, sets, [("events", ev["verdict"])])
        retention = Path(output).with_suffix("")
        retention.mkdir(exist_ok=True)
        save_retention(retention, arm_id, tables)
        out["events"] = ev
        out["readings"] = verdicts
        out["largest_deltas"] = {s: {k: float(np.nanmax(v["delta"])) for k, v in tbl[1].items()}
                                 for s, tbl in tables.items()}  # fmt: skip
        out["histories"] = histories(arm, parts(arm.ms), arm.ms)
        a_pass = all(verdicts["B_P"][s]["verdict"] == "pass" for s in sets)
        summary = record.get("energy_check_summary") or {}
        steps = int(record.get("steps") or 0)
        gain = C_ALL_FINE_STEPS / steps if steps else None
        cost = None
        if full1_cost and c_cost:
            f = json.loads(Path(full1_cost).read_text())
            c = json.loads(Path(c_cost).read_text())
            if not c.get("void") and c.get("seconds_per_simulated_second"):
                cost = f["seconds_per_simulated_second"] / c["seconds_per_simulated_second"]
            out["cost"] = {"today_1ms": f, "C" if arm_id == "H2-C" else "arm": c, "ratio": cost}
        sensitivity, binding = ("shown at 20 ms by H2's plant (§10.7; "
                                "records-d03ca463/plants/H2-slow-20.json)"), True  # fmt: skip
        if arm_id != "H2-C":  # §10.20 (b): binding shown, eps* reported, from its plant record.
            row = json.loads(Path(plant).read_text()) if plant else {}
            binding = bool(row.get("binding_shown"))
            sensitivity = dict(record=str(plant) if plant else None, text=row.get("sensitivity"),
                               binding_shown=binding, eps_star=row.get("eps_star"),
                               plant_arm=row.get("arm"), plant_ms=row.get("plant_ms"),
                               integrator=row.get("integrator"),
                               solver_route=row.get("solver_route"))  # fmt: skip
        out["x2"] = dict(decision="passes" if arm.complete else "refused", summary=summary,
                         sensitivity=sensitivity)  # fmt: skip
        out["gain"] = dict(steps=steps, all_fine_steps=C_ALL_FINE_STEPS, step_gain=gain,
                           cost_ratio=cost, threshold=10)  # fmt: skip
        out["verdict"] = dict(
            a="pass" if a_pass else worst([verdicts["B_P"][s]["verdict"] for s in sets]),
            b="pass" if arm.complete and binding else "fail",
            c="pass" if gain is not None and gain >= 10 else "fail",
        )
        out["verdict"]["C" if arm_id == "H2-C" else "arm"] = (
            f"passes {a['section']}"
            if all(out["verdict"][k] == "pass" for k in ("a", "b", "c"))
            else f"does not pass {a['section']}"
        )
        if a["regrid_cue"]:  # The lead's addition: (a) also on rule (i)'s rows, a subset (§10.23).
            from validation.long_duration import worlds

            r3 = set(worlds.harness_observation_times())
            keep = np.asarray([float(t) in r3 for t in arm.rows["times"]])
            sub = subset(arm, keep)
            ev_i = judge_events(series_events(sub), wa_events)
            sets_i = dict(own=sub.ms, common=sub.ms[sub.ms % 100 == 0])
            verdicts_i, _ = arm_reading(sub, parts, sets_i, [("events", ev_i["verdict"])])
            a_i = [verdicts_i["B_P"][s]["verdict"] for s in sets_i]
            out["subset_exact_rows"] = dict(
                rule="(i): R3's kept rows whose decimal time is exactly a point of the clock, a "
                "subset of the registered rows (ii); information beside the registered verdict",
                rows=int(keep.sum()), events=ev_i, readings=verdicts_i,
                a="pass" if all(v == "pass" for v in a_i) else worst(a_i),
            )  # fmt: skip
    Path(output).write_text(json.dumps(out, indent=1, default=float) + "\n")
    print(json.dumps(out.get("verdict"), default=float))
    return 0


# ------------------------------------------------------------- §6: N2 alone past 5 ms


def stage_a_read(output, arm_dir, control_dir):
    """§6's reading: the N2-alone arm on H2's slow phase (0-1790 s at 100 ms, X2 on) against R3
    at R3's 10 s rows, under both bars, with what binds; today's ID at the same step beside it."""
    import jax

    jax.config.update("jax_enable_x64", True)
    stage0 = stage0_ladder()
    arm = Series(arm_dir, None, 0, 1.0 / 100)
    out = dict(study="FR-8 rung 1, §6: N2 alone past 5 ms on the slow phase",
               arm=arm.record.get("arm"), integrator=arm.record.get("integrator"),
               x2=x2_of(arm))  # fmt: skip
    if arm.complete and arm.c is not None:
        ms = arm.ms
        table = compare(arm, [(stage0, np.ones(len(ms), bool), None)], ms)
        out["readings"] = {bar: verdict_rows(table, ms, bar) for bar in BARS}
        out["largest_deltas"] = {k: float(np.nanmax(v["delta"])) for k, v in table.items()}
        out["rows"] = len(ms)
    else:
        out["readings"] = {bar: refusal_of(arm.record) for bar in BARS}
    control = json.loads((Path(control_dir) / "run.json").read_text())
    out["control"] = dict(arm=control.get("arm"), integrator=control.get("integrator"),
                          status=control.get("status"), error=control.get("error"),
                          snapshot=control.get("snapshot_revision"))  # fmt: skip
    Path(output).write_text(json.dumps(out, indent=1, default=float) + "\n")
    print(json.dumps({k: out.get(k) for k in ("readings", "largest_deltas")}, default=float)[:900])
    return 0


SMOKES = (  # Development only: no registered window, horizon or row.
    ("H2-WA-k0", dict(span=(600_000, 600_050))),
    ("H2-WA-k3", dict(span=(600_000, 600_050))),
    ("H2-full-5", dict(end_ms=10_000)),
    ("W0-1", dict(end_ms=2_000)),
)


def smoke(out_dir):
    """Development smokes of each path (the import at 600 s, a short full run, a short W0): status
    and records only; none is a registered arm or read as one."""
    codes = []
    for arm, development in SMOKES:
        codes.append(run(arm, Path(out_dir) / arm, development=development))
    return max(codes)


def main(argv):
    if len(argv) >= 3 and argv[0] == "run":
        solver = next((a.split("=", 1)[1] for a in argv[3:] if a.startswith("--solver=")), None)
        return run(argv[1], argv[2], x2="--x2-off" not in argv[3:], solver=solver)
    if len(argv) == 4 and argv[0] == "stage-a-read":
        return stage_a_read(argv[1], argv[2], argv[3])
    if len(argv) == 2 and argv[0] == "smoke":
        return smoke(argv[1])
    if len(argv) == 3 and argv[0] == "instrument":
        return instrument(argv[1], argv[2])
    if len(argv) == 4 and argv[0] == "analyse":
        return analyse(argv[1], argv[2], argv[3])
    if len(argv) == 4 and argv[0] == "timed":
        return timed(argv[1], argv[2], argv[3])
    if len(argv) == 3 and argv[0] == "plant":
        return plant(argv[1], argv[2])
    if len(argv) >= 3 and argv[0] == "inworld-plant":
        solver = next((a.split("=", 1)[1] for a in argv[3:] if a.startswith("--solver=")), None)
        rest = [a for a in argv[3:] if not a.startswith("--")]
        if len(rest) <= 1:
            return inworld_plant(argv[1], argv[2], *rest, solver=solver)
    if len(argv) == 4 and argv[0] == "calm-run":
        return calm_run(argv[1], argv[2], argv[3])
    if len(argv) == 4 and argv[0] == "calm-read":
        return calm_read(argv[1], argv[2], argv[3])
    if len(argv) in (2, 3) and argv[0] == "step-change":
        return step_change(argv[1], window="--no-window" not in argv[2:])
    if len(argv) in (2, 3) and argv[0] == "c-run":
        return c_run(*argv[1:])
    if len(argv) in (3, 4) and argv[0] == "c-timed":
        return c_timed(*argv[1:])
    if len(argv) >= 3 and argv[0] == "c-judge":
        options = dict(a[2:].split("=", 1) for a in argv[3:] if a.startswith("--"))
        rest = [a for a in argv[3:] if not a.startswith("--")]
        if len(rest) in (0, 2) and not set(options) - {"arm", "plant"}:
            return c_judge(argv[1], argv[2], *rest, **options)
    if argv == ["arms"]:
        print("\n".join(control_arms()))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
