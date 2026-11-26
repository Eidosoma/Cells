"""FR-8 rung 0: the fine engine's order through a switch (RUNG0_20261119.md; D224 item 3).

Restart windows of H2, stage 0's harness world (worlds.h2: projective qual-01's F1 world at a
3600 s horizon). Each window is a new run that imports a saved full state from stage 0's R3 (H2 at
0.25 ms, from snapshot 24e516c7; its kept rows) into H2 at dt = 2^-k ms, from the window's start
to its end. It claims no continuity with R3. The engine model is cells.model.resolved_pump_tissue@3 alone.
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
    if w.get("no_channels"):  # Amendment 1's WN: pump and passive leaks only, no gates, no cue.
        raw["model"]["channels"] = []
        raw["experiment"]["channel_controls"] = []
        raw["execution"]["channel_capacity"] = 0
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
        engine_model="cells.model.resolved_pump_tissue@3",
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
        start_point = None if w.get("from_initial") else checkpoint(spec, model, start)
        result = run_windowed(spec, policy, start_point, sink=keeper)
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


def classes(rows, window="WA"):
    """Per row: membrane voltages [patch], concentrations [species, cell] and the gates by law
    {nav_m, nav_h, kir_m, kir_h} [cell], from the engine's own readouts, on the window's own
    layout (which does not depend on dt; WN's has no channels, so its gate classes are empty)."""
    from cells.definitions.specs import parse_spec
    from cells.models import surface_pump_projective as projective
    from cells.registry.models import get_model

    spec = parse_spec(window_raw(window, 0))
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
    rows_count = len(out["voltage"])
    for g in ("nav_m", "nav_h", "kir_m", "kir_h"):
        out[g] = out[g].reshape(rows_count, -1)
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


# ------------------------------------------------------------------ the registered analysis

CLASS_KEYS = ("voltage", "concentration", "gate", "nav_m", "nav_h", "kir_m", "kir_h")


def load_arm(root, window, k):
    """One arm's run record and rows. The readings pair the arms' rows by position, so an arm is
    refused unless its record names this registration, window and k at dt_k, and, once complete,
    its rows are the window's registered 1 ms grid, every time exactly (the fourth review's
    finding 3)."""
    reg = registration()
    directory = Path(root) / window / f"k{k}"
    record = json.loads((directory / "run.json").read_text())
    expected = dict(registration=reg["registration"], window=window, k=k, dt_s=dt_of(k))
    found = {x: record.get(x) for x in expected}
    if found != expected:
        raise ValueError(f"{directory}: its record names {found}, not {expected}")
    if record["status"] != "complete":
        return record, None, None
    with np.load(directory / "rows.npz") as archive:
        rows = {f: archive[f] for f in archive.files}
    w = reg["windows"][window]
    if not np.array_equal(rows["times"], millisecond_rows(w["start_ms"], w["end_ms"])):
        raise ValueError(f"{directory}: its rows are not {window}'s registered 1 ms grid")
    return record, rows["times"], rows


def in_band(p, band):
    return p is not None and band[0] <= p <= band[1]


def span_orders(reg, window, arms, steps, span):
    """Per class: D_k (the sup-norm of |z_k - z_(k+1)| over the span's rows), its floor, and p_k
    (readable pairs only), with each k's dt."""
    ks = sorted(arms)
    times = arms[ks[0]][0]
    lo, hi = (at_ms(v) for v in span)
    mask = (times > lo) & (times <= hi)
    out = {}
    for key in CLASS_KEYS:
        d = {k: float(np.max(difference(arms[k][1][key], arms[k + 1][1][key], key)[mask],
                             initial=0.0)) for k in ks[:-1]}  # fmt: skip
        floor = {k: reg["readable_factor"] * steps[k + 1] * EPS * SCALES[key] for k in ks[:-1]}
        p = {k: order(d[k], d[k + 1], floor[k + 1]) for k in ks[:-2]}
        out[key] = dict(
            D={str(k): d[k] for k in ks[:-1]},
            floor={str(k): floor[k] for k in ks[:-1]},
            p={str(k): p[k] for k in ks[:-2]},
            dt_s={str(k): dt_of(k) for k in ks[:-2]},
        )
    return out


def readable(entry):
    return [
        (int(k), v)
        for k, v in sorted(entry["p"].items(), key=lambda kv: int(kv[0]))
        if v is not None
    ]


def finest(entry, count):
    return [v for _, v in readable(entry)[-count:]]


def tie_back(reg, arms):
    """I3: WA at k = 2 against R3's kept rows on WA's 1 ms rows (every state field, bitwise)."""
    times, rows = arms[2][0], arms[2][2]
    with np.load(Path(reg["source"]["rows"])) as archive:
        source_times = archive["times"]
        index = [int(np.flatnonzero(source_times == t)[0]) for t in times]
        fields = [f for f in archive.files if f != "times"]
        bitwise = all(np.array_equal(rows[f], archive[f][index]) for f in fields)
        source_classes = classes({f: archive[f][index] for f in fields})
    largest = float(np.max(np.abs(arms[2][1]["voltage"] - source_classes["voltage"]), initial=0.0))
    return dict(bitwise=bool(bitwise), largest_voltage_difference_V=largest)


def transient_rates(reg, window, k, times, rows, span):
    """(C)'s extras: over the span's rows of the finest arm, the largest fastest-gate rate (max
    1/tau over the gated channels) and membrane_rate (1/s), from the engine's own readouts."""
    from cells.definitions.specs import parse_spec
    from cells.execution.schedule import control_values
    from cells.models import surface_pump_v3 as v3
    from cells.registry.models import get_model

    spec = parse_spec(window_raw(window, k))
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    lo, hi = (at_ms(v) for v in span)
    chosen = [i for i, t in enumerate(times) if lo < t <= hi]
    controls = control_values(spec, [float(times[i]) for i in chosen])
    gated = np.asarray(p.channel_gate_active, dtype=bool)
    gate_rate = membrane = 0.0
    with np.errstate(all="ignore"):
        for j, i in enumerate(chosen):
            row = model.STATE_TYPE(*(rows[f][i] for f in model.STATE_TYPE._fields))
            control = type(controls)(*(np.asarray(v)[j] for v in controls))
            values = model.readouts(row, control, p, xp=np)
            tau = np.asarray(values.channel_tau_s)
            gate_rate = max(gate_rate, float(np.max(np.where(gated, 1.0 / tau, 0.0), initial=0.0)))
            membrane = max(membrane, float(v3.membrane_rate(row, control, p, xp=np)))
    return dict(fastest_gate_rate_per_s=gate_rate, membrane_rate_per_s=membrane)


def analyse(output, root):
    import jax

    jax.config.update("jax_enable_x64", True)
    reg = registration()
    ks = list(range(reg["k_range"][0], reg["k_range"][1] + 1))
    second, first = reg["bands"]["second"], reg["bands"]["first"]
    out = dict(study="FR-8 rung 0", registration=reg["registration"], judged=False,
               engine_model="cells.model.resolved_pump_tissue@3", I1=synthetic(), windows={})  # fmt: skip
    data = {}
    for window in ("WS", "WA", "WC", "WB"):
        arms, steps, records = {}, {}, {}
        for k in ks:
            record, times, rows = load_arm(root, window, k)
            records[k] = {
                x: record.get(x) for x in ("status", "error", "steps", "off_nominal_boundaries")
            }
            if rows is not None:
                arms[k] = (times, classes(rows), rows)
                steps[k] = record["steps"]
        entry = dict(arms=records)
        if len(arms) != len(ks):
            entry["incomplete"] = sorted(set(ks) - set(arms))
            out["windows"][window] = entry
            continue
        if any(not np.array_equal(arms[k][0], arms[ks[0]][0]) for k in ks):
            raise ValueError(f"{window}'s arms differ in their rows")
        entry["spans"] = {
            name: span_orders(reg, window, {k: arms[k][:2] for k in ks}, steps, span)
            for name, span in reg["windows"][window]["spans"].items()
        }
        out["windows"][window] = entry
        data[window] = (arms, steps)
    w = out["windows"]
    complete = all("spans" in w.get(x, {}) for x in ("WS", "WA", "WC", "WB"))
    verdict = dict(complete=complete)
    if complete:
        ws = w["WS"]["spans"]["slow"]
        verdict["I1"] = out["I1"]["passed"]
        verdict["I2"] = all(
            readable(ws[c]) and all(in_band(v, second) for _, v in readable(ws[c]))
            for c in CLASS_KEYS
        )
        tie = tie_back(reg, data["WA"][0])
        wa_t = w["WA"]["spans"]["transient"]
        tie["faithful"] = (
            tie["bitwise"]
            or tie["largest_voltage_difference_V"] <= 1e-3 * wa_t["voltage"]["D"]["2"]
        )
        verdict["I3"] = tie
        a0, a2 = data["WA"][0][0][1], data["WA"][0][2][1]
        times = data["WA"][0][0][0]
        lo, hi = (at_ms(v) for v in reg["windows"]["WA"]["spans"]["transient"])
        mask = (times > lo) & (times <= hi)
        verdict["I4"] = {c: float(np.max(difference(a0[c], a2[c], c)[mask], initial=0.0))
                         for c in ("voltage", "gate")}  # fmt: skip
        instruments = verdict["I1"] and verdict["I2"] and tie["faithful"]
        verdict["instruments_pass"] = bool(instruments)
        coarse = [k for k in ks if dt_of(k) >= 2.5e-4]
        c_recovers = all(
            len(finest(wa_t[c], 2)) == 2 and all(in_band(v, second) for v in finest(wa_t[c], 2))
            for c in CLASS_KEYS
        )
        c_drops = any(
            v is not None and v < 1.6
            for c in CLASS_KEYS
            for k, v in readable(wa_t[c])
            if k in coarse
        )
        verdict["C"] = bool(c_recovers and c_drops)
        b_spans = [wa_t, w["WC"]["spans"]["upswing"], w["WB"]["spans"]["downswing"]]
        verdict["B"] = any(
            len(finest(s[c], 2)) == 2 and all(in_band(v, first) for v in finest(s[c], 2))
            for s in b_spans
            for c in ("gate", "nav_m", "nav_h", "kir_m", "kir_h")
        )
        arms_all = [w[x]["arms"][k] for x in ("WS", "WA", "WC", "WB") for k in ks]
        a1 = any((r.get("off_nominal_boundaries") or 0) > 0 for r in arms_all)
        pre, post = w["WA"]["spans"]["pre_edge"], w["WA"]["spans"]["post_edge"]
        a2_ = any(
            post[c]["p"][str(k)] is not None
            and post[c]["p"][str(k)] <= 1.6
            and pre[c]["p"][str(k)] is not None
            and pre[c]["p"][str(k)] >= 1.8
            for c in CLASS_KEYS
            for k in ks[:-2]
        )
        wc = w["WC"]["spans"]["upswing"]
        wc_clean = all(
            all(v >= 1.8 for _, v in readable(wc[c])) and readable(wc[c]) for c in CLASS_KEYS
        )
        wa_drops = any(v < 1.6 for c in CLASS_KEYS for _, v in readable(wa_t[c]))
        a3 = bool(wc_clean and wa_drops)
        verdict["A"] = dict(A1=bool(a1), A2=bool(a2_), A3=a3, implicated=bool(a1 or a2_ or a3))
        no_edge = [wc, w["WB"]["spans"]["downswing"]]
        verdict["A_excluded_as_necessary"] = any(
            v < 1.6 for s in no_edge for c in CLASS_KEYS for k, v in readable(s[c]) if k in coarse
        )

        def unsettled(s):
            return any(
                len(finest(s[c], 3)) == 3
                and max(finest(s[c], 3)) - min(finest(s[c], 3)) > 0.5
                and not in_band(finest(s[c], 3)[-1], second)
                and not in_band(finest(s[c], 3)[-1], first)
                for c in CLASS_KEYS
            )

        verdict["D"] = any(unsettled(s) for s in b_spans)
        identified = [x for x in ("A", "B", "C", "D")
                      if (verdict[x]["implicated"] if x == "A" else verdict[x])]  # fmt: skip
        verdict["identified"] = identified if instruments else []
        verdict["outcome"] = (
            "instrument not validated"
            if not instruments
            else ", ".join(identified)
            if identified
            else "not identified"
        )
        # (C)'s extras and the deliverable.
        finest_k = ks[-1]
        times_f, _, rows_f = data["WA"][0][finest_k]
        rates = transient_rates(reg, "WA", finest_k, times_f, rows_f,
                                reg["windows"]["WA"]["spans"]["transient"])  # fmt: skip
        rates["dt_times_rate"] = {
            str(k): dict(gate=dt_of(k) * rates["fastest_gate_rate_per_s"],
                         membrane=dt_of(k) * rates["membrane_rate_per_s"]) for k in ks
        }  # fmt: skip
        crossover = {}
        for c in CLASS_KEYS:
            pairs = readable(wa_t[c])
            best = None
            for k, v in reversed(pairs):
                if in_band(v, second):
                    best = k
                else:
                    break
            crossover[c] = None if best is None else dict(k=best, dt_s=dt_of(best))
        rates["crossover"] = crossover
        verdict["C_extras"] = rates
        deliverable = {}
        for window, span in (("WA", "transient"), ("WC", "upswing"), ("WB", "downswing")):
            s = w[window]["spans"][span]
            deliverable[window] = {}
            for c in CLASS_KEYS:
                pick = [(k, v) for k, v in readable(s[c]) if 1.5 <= v <= 2.5]
                if pick:
                    k, v = pick[-1]
                    deliverable[window][c] = dict(
                        pair=k, p=v, finer_arm_error=s[c]["D"][str(k)] / (2**v - 1)
                    )
                else:
                    deliverable[window][c] = None
        arms_wa = data["WA"][0]
        budgets = reg["budgets"]
        meets = {}
        for k in ks:
            e = {
                c: float(
                    np.max(difference(arms_wa[k][1][c], arms_wa[finest_k][1][c], c), initial=0.0)
                )
                for c in ("voltage", "concentration", "gate")
            }
            ok = (
                e["voltage"] <= budgets["voltage_V"]
                and e["concentration"] <= budgets["relative_concentration"]
                and e["gate"] <= budgets["gate"]
            )
            meets[str(k)] = dict(errors_against_finest=e, within=bool(ok))
        within = [k for k in ks if meets[str(k)]["within"] and k != finest_k]
        deliverable["largest_dt_within_stage0_budgets"] = (
            dict(k=min(within), dt_s=dt_of(min(within))) if within else None
        )
        deliverable["arms_against_finest"] = meets
        verdict["deliverable"] = deliverable
    out["verdict"] = verdict
    with open(output, "x") as stream:
        json.dump(out, stream, indent=1, default=str)
        stream.write("\n")
    print(json.dumps({x: verdict.get(x) for x in ("complete", "instruments_pass", "outcome")}))
    return 0


# ------------------------------------------------------------------ amendment 1


def window_arms(root, window, ks):
    """Every arm of one window: (times, classes, rows) per k, the steps, and the run records."""
    arms, steps, records = {}, {}, {}
    for k in ks:
        record, times, rows = load_arm(root, window, k)
        records[k] = {
            x: record.get(x) for x in ("status", "error", "steps", "off_nominal_boundaries")
        }
        if rows is not None:
            arms[k] = (times, classes(rows, window), rows)
            steps[k] = record["steps"]
    return arms, steps, records


def with_readable(entry, need, keys=CLASS_KEYS):
    """The classes with at least `need` readable orders."""
    return [c for c in keys if len(readable(entry[c])) >= need]


def analyse_wn(output, root):
    """Amendment 1's control, read alone: WN's power and its two finest readable orders."""
    import jax

    jax.config.update("jax_enable_x64", True)
    reg = registration()
    ks = list(range(reg["k_range"][0], reg["k_range"][1] + 1))
    second = reg["bands"]["second"]
    arms, steps, records = window_arms(root, "WN", ks)
    out = dict(study="FR-8 rung 0", amendment=1, window="WN", judged=False, arms=records)
    if len(arms) != len(ks):
        out.update(outcome="incomplete", missing=sorted(set(ks) - set(arms)))
    else:
        span = span_orders(
            reg, "WN", {k: arms[k][:2] for k in ks}, steps, reg["windows"]["WN"]["spans"]["control"]
        )
        powered = with_readable(span, reg["amendment_1"]["power_min_orders"])
        passes = bool(powered) and all(
            all(in_band(v, second) for v in finest(span[c], 2)) for c in powered
        )
        out.update(
            span=span,
            powered_classes=powered,
            outcome="no power" if not powered else ("passes" if passes else "fails"),
        )
    with open(output, "x") as stream:
        json.dump(out, stream, indent=1)
        stream.write("\n")
    print(json.dumps({x: out.get(x) for x in ("outcome", "powered_classes")}))
    return 0


def analyse_amended(output, root, wn_output):
    """The main windows under amendment 1, opened only after WN passed: every rule decided on the
    classes that have its readable pairs, and "untested" where none has."""
    import jax

    jax.config.update("jax_enable_x64", True)
    wn = json.loads(Path(wn_output).read_text())
    if wn.get("outcome") != "passes":
        raise SystemExit("Amendment 1: the main windows are opened only after WN passes")
    reg = registration()
    ks = list(range(reg["k_range"][0], reg["k_range"][1] + 1))
    second, first = reg["bands"]["second"], reg["bands"]["first"]
    coarse = [k for k in ks if dt_of(k) >= 2.5e-4]
    out = dict(study="FR-8 rung 0", amendment=1, judged=False, I1=synthetic(),
               I2=dict(control="WN", outcome=wn["outcome"]), windows={})  # fmt: skip
    data = {}
    for window in ("WA", "WC", "WB"):
        arms, steps, records = window_arms(root, window, ks)
        entry = dict(arms=records)
        if len(arms) == len(ks):
            entry["spans"] = {
                name: span_orders(reg, window, {k: arms[k][:2] for k in ks}, steps, span)
                for name, span in reg["windows"][window]["spans"].items()
            }
            data[window] = (arms, steps)
        out["windows"][window] = entry
    w = out["windows"]
    if not all("spans" in w[x] for x in ("WA", "WC", "WB")):
        out["outcome"] = "incomplete"
    else:
        tie = tie_back(reg, data["WA"][0])
        wa_t = w["WA"]["spans"]["transient"]
        tie["faithful"] = (
            tie["bitwise"]
            or tie["largest_voltage_difference_V"] <= 1e-3 * wa_t["voltage"]["D"]["2"]
        )
        times = data["WA"][0][0][0]
        lo, hi = (at_ms(v) for v in reg["windows"]["WA"]["spans"]["transient"])
        mask = (times > lo) & (times <= hi)
        a0, a2 = data["WA"][0][0][1], data["WA"][0][2][1]
        i4 = {c: float(np.max(difference(a0[c], a2[c], c)[mask], initial=0.0))
              for c in ("voltage", "gate")}  # fmt: skip
        instruments = out["I1"]["passed"] and wn["outcome"] == "passes" and tie["faithful"]
        verdict = dict(I3=tie, I4=i4, instruments_pass=bool(instruments), untested={})
        # (C): every class with two readable orders recovers; some class drops at a coarse pair.
        evaluable = with_readable(wa_t, 2)
        verdict["untested"]["C"] = sorted(set(CLASS_KEYS) - set(evaluable))
        if not evaluable:
            verdict["C"] = "untested"
        else:
            recovers = all(all(in_band(v, second) for v in finest(wa_t[c], 2)) for c in evaluable)
            drops = any(v < 1.6 for c in CLASS_KEYS for k, v in readable(wa_t[c]) if k in coarse)
            verdict["C"] = bool(recovers and drops)
        # (B): a gate class with two readable orders, both in the first-order band.
        gates = ("gate", "nav_m", "nav_h", "kir_m", "kir_h")
        b_spans = {"WA transient": wa_t, "WC upswing": w["WC"]["spans"]["upswing"],
                   "WB downswing": w["WB"]["spans"]["downswing"]}  # fmt: skip
        b_eval = {n: with_readable(s, 2, gates) for n, s in b_spans.items()}
        verdict["untested"]["B"] = {n: sorted(set(gates) - set(v)) for n, v in b_eval.items()}
        if not any(b_eval.values()):
            verdict["B"] = "untested"
        else:
            verdict["B"] = any(
                all(in_band(v, first) for v in finest(b_spans[n][c], 2))
                for n, cs in b_eval.items()
                for c in cs
            )
        # (A): A1 from the records; A2 and A3 decided only where readable.
        arms_all = [w[x]["arms"][k] for x in ("WA", "WC", "WB") for k in ks]
        a1 = any((r.get("off_nominal_boundaries") or 0) > 0 for r in arms_all)
        pre, post = w["WA"]["spans"]["pre_edge"], w["WA"]["spans"]["post_edge"]
        pairs = [
            (c, k)
            for c in CLASS_KEYS
            for k in ks[:-2]
            if pre[c]["p"][str(k)] is not None and post[c]["p"][str(k)] is not None
        ]
        if not pairs:
            a2 = "untested"
        else:
            a2 = any(post[c]["p"][str(k)] <= 1.6 and pre[c]["p"][str(k)] >= 1.8 for c, k in pairs)
        wc = w["WC"]["spans"]["upswing"]
        wc_eval = with_readable(wc, 1)
        if not wc_eval:
            a3 = "untested"
        else:
            wc_clean = all(all(v >= 1.8 for _, v in readable(wc[c])) for c in wc_eval)
            wa_drops = any(v < 1.6 for c in CLASS_KEYS for _, v in readable(wa_t[c]))
            a3 = bool(wc_clean and wa_drops)
        verdict["A"] = dict(A1=bool(a1), A2=a2, A3=a3,
                            implicated=bool(a1 or a2 is True or a3 is True))  # fmt: skip
        no_edge = [wc, w["WB"]["spans"]["downswing"]]
        coarse_readable = [v for s in no_edge for c in CLASS_KEYS for k, v in readable(s[c])
                           if k in coarse]  # fmt: skip
        verdict["A_excluded_as_necessary"] = (
            "untested" if not coarse_readable else any(v < 1.6 for v in coarse_readable)
        )
        # (D): a class with three readable orders that does not settle.
        d_eval = [(n, c) for n, s in b_spans.items() for c in with_readable(s, 3)]
        if not d_eval:
            verdict["D"] = "untested"
        else:
            verdict["D"] = any(
                max(finest(b_spans[n][c], 3)) - min(finest(b_spans[n][c], 3)) > 0.5
                and not in_band(finest(b_spans[n][c], 3)[-1], second)
                and not in_band(finest(b_spans[n][c], 3)[-1], first)
                for n, c in d_eval
            )
        flags = dict(A=verdict["A"]["implicated"], B=verdict["B"] is True,
                     C=verdict["C"] is True, D=verdict["D"] is True)  # fmt: skip
        identified = [x for x in ("A", "B", "C", "D") if flags[x]]
        verdict["identified"] = identified if instruments else []
        verdict["outcome"] = (
            "instrument not validated"
            if not instruments
            else ", ".join(identified)
            if identified
            else "not identified"
        )
        # (C)'s extras and the deliverable, as registered (§5, §6).
        finest_k = ks[-1]
        times_f, _, rows_f = data["WA"][0][finest_k]
        rates = transient_rates(reg, "WA", finest_k, times_f, rows_f,
                                reg["windows"]["WA"]["spans"]["transient"])  # fmt: skip
        rates["dt_times_rate"] = {
            str(k): dict(gate=dt_of(k) * rates["fastest_gate_rate_per_s"],
                         membrane=dt_of(k) * rates["membrane_rate_per_s"]) for k in ks
        }  # fmt: skip
        crossover = {}
        for c in CLASS_KEYS:
            best = None
            for k, v in reversed(readable(wa_t[c])):
                if in_band(v, second):
                    best = k
                else:
                    break
            crossover[c] = None if best is None else dict(k=best, dt_s=dt_of(best))
        rates["crossover"] = crossover
        verdict["C_extras"] = rates
        deliverable = {}
        for window, span in (("WA", "transient"), ("WC", "upswing"), ("WB", "downswing")):
            s = w[window]["spans"][span]
            deliverable[window] = {}
            for c in CLASS_KEYS:
                pick = [(k, v) for k, v in readable(s[c]) if 1.5 <= v <= 2.5]
                deliverable[window][c] = (
                    dict(pair=pick[-1][0], p=pick[-1][1],
                         finer_arm_error=s[c]["D"][str(pick[-1][0])] / (2 ** pick[-1][1] - 1))
                    if pick else None
                )  # fmt: skip
        arms_wa, budgets, meets = data["WA"][0], reg["budgets"], {}
        for k in ks:
            e = {
                c: float(
                    np.max(difference(arms_wa[k][1][c], arms_wa[finest_k][1][c], c), initial=0.0)
                )
                for c in ("voltage", "concentration", "gate")
            }
            ok = (
                e["voltage"] <= budgets["voltage_V"]
                and e["concentration"] <= budgets["relative_concentration"]
                and e["gate"] <= budgets["gate"]
            )
            meets[str(k)] = dict(errors_against_finest=e, within=bool(ok))
        within = [k for k in ks if meets[str(k)]["within"] and k != finest_k]
        deliverable["largest_dt_within_stage0_budgets"] = (
            dict(k=min(within), dt_s=dt_of(min(within))) if within else None
        )
        deliverable["arms_against_finest"] = meets
        verdict["deliverable"] = deliverable
        out["verdict"] = verdict
        out["outcome"] = verdict["outcome"]
    with open(output, "x") as stream:
        json.dump(out, stream, indent=1, default=str)
        stream.write("\n")
    print(json.dumps({"outcome": out.get("outcome")}))
    return 0


if __name__ == "__main__":
    command = sys.argv[1]
    if command == "run":
        sys.exit(run(sys.argv[2], int(sys.argv[3]), sys.argv[4]))
    if command == "synthetic":
        print(json.dumps(synthetic(sys.argv[2])))
        sys.exit(0)
    if command == "analyse":
        sys.exit(analyse(sys.argv[2], sys.argv[3]))
    if command == "analyse_wn":
        sys.exit(analyse_wn(sys.argv[2], sys.argv[3]))
    if command == "analyse_amended":
        sys.exit(analyse_amended(sys.argv[2], sys.argv[3], sys.argv[4]))
    raise SystemExit(
        "usage: rung0.py run WINDOW K OUT_DIR | synthetic OUTPUT | analyse OUTPUT ROOT"
    )
