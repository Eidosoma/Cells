"""FR-8 rung 1: the arms of RUNG1_20261119.md, and first its control (D232, the entry §10.3).

The control is today's integrator, imex_ars222_face_electromigration@1, with X2
(step_doubled_energy@1) at the registered cap, on rung 1's registered arms for today's ID at
their full registered horizons (§3, §10.3, §10.4). Development, not judged.

Engine models: resolved_pump_tissue@3 (H2); resolved_pump_composite@1 over
resolved_pump_tissue@3 with scheduled_species_turnover@1 and species_regulated_availability@1
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
"""

import hashlib
import json
import os
import sys
import time
from fractions import Fraction
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REGISTRATION = HERE / "rung1_20261119.json"
EPS = float(np.finfo(float).eps)
TODAY = "imex_ars222_face_electromigration@1"
FULL_MS = (1, 2, 5, 10, 20, 50, 100)
SLOW_MS = (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000)  # §10.4 adds 1-100 ms.
W0_MS = ("0.125", "0.25", "0.5", "1", "2", "5", "10")
WINDOWS = ("WS", "WA", "WC", "WB")
H2_END_MS, SLOW_END_MS = 3_600_000, 1_790_000
W0_END_MS, W0_DOSE_MS, W0_WRITE_MS = 60_000, 20_000, 40_000


class ImportRefused(ValueError):
    pass


def registration():
    return json.loads(REGISTRATION.read_text())


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


def run(arm, out_dir, x2=True, development=None):
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
        return run(argv[1], argv[2], x2="--x2-off" not in argv[3:])
    if len(argv) == 2 and argv[0] == "smoke":
        return smoke(argv[1])
    if argv == ["arms"]:
        print("\n".join(control_arms()))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
