"""E07-v1 renewal stage: the engine-run driver (validation only).

Registered protocol: validation/tissue/e07_v1_protocol.json (E07-v1-B); design:
docs/E07_V1_DESIGN.md. Arms, schedules, donor rules, the copy-only null and the formation
law's abundance come from validation/tissue/e07_v1_turnover.py. The world, its start and
the stepping are the turnover pre-screen's (validation/tissue/heredity_turnover_literature:
definition, layout_check, Stepper, run_segments), which run the model's checked step and
its device row checks on every accepted row.

Engine models run: resolved_pump_replacement@1 (resolved_pump_composite@1 with
scheduled_cell_replacement@1 over resolved_pump_tissue@3; junction formation
delayed_first_order_junction_formation@1), IMEX ARS(2,2,2), junction_heat_booking
trapezoid_nonnegative@1. Every definition is declared through
validation/tissue/field_solver_choice.declare() (D147). Nothing here adds physics.

Parts (each its own process: the analysis never runs in an arm's process):
  arm --arm ID --seed R [--dt] [--end-s] [--resume]   one run: records, checkpoint, result
  analyse --arm ID --seed R                           the run read against its paired null
  summary                                             run classes, group classes, E4-E6, B1
  e1 --segment NAME --dt DT [--seed R] [--end-s]      a segment of the numerics gate E1
  e1compare [--seed R]                                E1's verdict (the pre-screen's criteria)

Seeds 1-8 are the registered seeds. Development runs use seeds of 101 or more and are
labelled so; --end-s shortens a development run (its judged record may then not be reached).

Supplementary readouts (protocol key supplementary_readouts) carry the label SUPPLEMENTARY
in every output: the deviation from the null over the run's records (delta_J_over_records),
added after the seed-101 dry run. They are reported, not judged, and no run class, group
class or item depends on them.

Output: DIR/runs/<arm>/seed<R>/ holds definition.json, plan.json, records.npz,
checkpoint.npz, progress.jsonl, result.json, then outcome.json and opportunity.json from
analyse; DIR/e1/ the gate's segments and verdict; DIR/summary.json.
"""

import argparse
import json
import math
import resource
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

from validation.tissue import e07_v1_turnover as e7
from validation.tissue import field_solver_choice

DEVELOPMENT_SEEDS_FROM = 101
CENSOR, FLAG = 0.15, 0.10
ALL_H_TAIL_S = 60.0
SAVE_EVERY_WALL_S = 900.0
# The run classes (protocol analysis.run_class) and the group rule (analysis.group_rule).
NEUTRAL_FRACTION, CLASS_FRACTION = 0.02, 0.05
# The label of every readout that is not part of the registered protocol (protocol key
# supplementary_readouts): reported, never judged, and no class or item depends on it.
SUPPLEMENTARY = (
    "supplementary: added to the driver after the seed-101 development dry run (49de1b1); "
    "not judged; no run class, group class or item depends on it"
)
E1_SEGMENTS = {
    "a-fast-k1-d37-s1.0": dict(arm="a-donor-fast-k1-d37-s1.0", end_s=600.0, every_s=2.0),
    "b-tau40-d37-s1.0": dict(arm="b-iso-tau40-d37-s1.0", end_s=300.0, every_s=1.0),
    "b-tau40-d37-s0.6": dict(arm="b-iso-tau40-d37-s0.6", end_s=300.0, every_s=1.0),
}
E1_GRID_DT = 0.005  # Event times on the 5 ms grid, so 1 ms and 5 ms runs share them.


def lit():
    """The pre-screen driver (JAX and the engine), imported only where stepping is needed."""
    from validation.tissue import heredity_turnover_literature

    return heredity_turnover_literature


def log(line):
    print(f"[{time.strftime('%H:%M:%S')}] {line}", flush=True)


def write_json(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=1, default=_default) + "\n")
    tmp.replace(path)


def _default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


def find_arm(arm_id):
    arms = {a["id"]: a for a in e7.arm_set()}
    if arm_id not in arms:
        raise SystemExit(f"Unknown arm {arm_id}")
    return arms[arm_id]


def label(seed):
    return "development" if seed >= DEVELOPMENT_SEEDS_FROM else "registered seed"


def run_dir(base, arm_id, seed):
    return Path(base) / "runs" / arm_id / f"seed{seed}"


def group_of(arm_id):
    for key, name in (("-fast-k1-", "fast k1"), ("-central-k1-", "central k1"),
                      ("-fast-k3-", "fast k3")):  # fmt: skip
        if arm_id.startswith("a-") and key in arm_id:
            return name
    return {"b": "threshold-finding", "c": "control"}[arm_id[0]]


# ------------------------------------------------------------------ definitions


def schedule(arm, seed, *, dt, end_s=None, grid_dt=None):
    """The arm's events for a seed (with carrier IDs) and its plan record."""
    end = arm["end_s"] if end_s is None else end_s
    p = e7.plan(scope=arm["scope"], rule=arm["rule"], size=arm["size"],
                residence_s=arm["residence_s"], end_s=end, seed=seed, dt=dt,
                grid_dt=grid_dt)  # fmt: skip
    events = [(k, slot, donor, f"n{j}") for j, (k, slot, donor) in enumerate(p["events"])]
    record = dict(
        arm=arm["id"],
        seed=seed,
        label=label(seed),
        group=group_of(arm["id"]),
        size=arm["size"],
        s=arm["s"],
        kind=arm["kind"],
        scope=arm["scope"],
        rule=arm["rule"],
        formation=arm["formation"],
        residence_s=arm["residence_s"],
        registered_end_s=arm["end_s"],
        planned_end_s=end,
        judged_at=arm["judged_at"],
        dt=dt,
        grid_dt=grid_dt or dt,
        interval_s=p["interval_s"],
        turnover_complete_s=p["turnover_complete_s"],
        permutation=p["permutation"],
        events=events,
    )
    return record


def build(record):
    """The definition (D147-declared) and the driver's checks on it."""
    raw, template = lit().definition(record["size"], record["s"], record["dt"],
                                     record["planned_end_s"], record["events"],
                                     record["formation"])  # fmt: skip
    raw = field_solver_choice.declare(raw)  # D147: version 3 if any free offset.
    p_template = template["amounts_fmol"]["P"]
    checks = dict(
        field_solver=raw["execution"]["field_solver"],
        field_solver_auto=field_solver_choice.solver_for(raw, "auto"),
        free_field_offsets=field_solver_choice.free_field_offsets(raw),
        donor_P_equals_slot_P=all(
            c["initial_amount_fmol"]["P"] == p_template for c in raw["model"]["cells"]
        ),
    )
    checks["field_solver_as_declared"] = checks["field_solver"] == checks["field_solver_auto"]
    return raw, checks


# ------------------------------------------------------------------ arm


def part_arm(args):
    arm = find_arm(args.arm)
    out = run_dir(args.output, arm["id"], args.seed)
    out.mkdir(parents=True, exist_ok=True)
    tick = time.perf_counter()
    record = schedule(arm, args.seed, dt=args.dt, end_s=args.end_s)
    raw, checks = build(record)
    if not (checks["donor_P_equals_slot_P"] and checks["field_solver_as_declared"]):
        write_json(out / "result.json", dict(stop="definition check failed", checks=checks))
        raise SystemExit("Definition check failed")
    if not (out / "plan.json").exists():
        write_json(out / "plan.json", record)
        write_json(out / "definition.json", raw)
    h = lit()
    from cells.core.specs import parse_spec

    spec = parse_spec(raw)
    layout = h.layout_check(spec, record["size"], record["s"])
    checks["layout_equals_sheet70"] = all(v == 0.0 for v in layout.values())
    stepper = h.Stepper(spec)
    dt = record["dt"]
    every = int(round(e7.RECORD_S / dt))
    end = int(round(record["planned_end_s"] / dt))
    marks = sorted(set(range(every, end + 1, every)) | {k for k, *_ in record["events"]} | {end})
    records, start_k, resumed = [], 0, None
    if args.resume and (out / "checkpoint.npz").exists():
        saved = dict(np.load(out / "checkpoint.npz"))
        stepper.load(saved)
        start_k = int(saved["step"])
        records = [r for r in h.load_records(out / "records.npz")
                   if int(round(float(r["t"]) / dt)) <= start_k]  # fmt: skip
        resumed = start_k * dt
    volume = np.asarray(stepper.host_p.volume)[: stepper.n]
    if not records:
        first = stepper.measure(0)
        first.update(t=0.0, regular=True, conc=first["amounts"][:3] / volume,
                     osm=first["amounts"].sum(axis=0) / volume)  # fmt: skip
        records.append(first)
    osm_h = h.h_osmolarity()
    state = dict(all_h=0)
    progress = open(out / "progress.jsonl", "a", buffering=1)

    def on_record(m):
        if m["regular"] and int(round(m["t"] / e7.RECORD_S)) % 6 == 0:
            d = m["vm"] > h.THRESHOLD_V
            row = dict(
                t=m["t"],
                d=int(d.sum()),
                max_excess=float(m["osm"].max() / osm_h - 1.0),
                wall_s=time.perf_counter() - tick,
                rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
            )
            progress.write(json.dumps(row) + "\n")

    def stop(m):
        d = m["vm"] > h.THRESHOLD_V
        if m["osm"].max() / osm_h - 1.0 > CENSOR:
            return "censor"
        state["all_h"] = state["all_h"] + 1 if not d.any() else 0
        if d.any():
            state.pop("all_h_since", None)
        if state["all_h"] >= 2:
            state.setdefault("all_h_since", m["t"] - e7.RECORD_S)
        if "all_h_since" in state and m["t"] >= state["all_h_since"] + ALL_H_TAIL_S - 1e-9:
            return "all_h"
        return None

    def save(k_now, worst):
        h.save_records(out / "records.npz", records)
        tmp = out / "checkpoint.tmp.npz"
        np.savez(tmp, step=k_now, **stepper.host_state())
        tmp.replace(out / "checkpoint.npz")

    setup = time.perf_counter() - tick
    k_end, outcome, worst = h.run_segments(stepper, marks, every=every, records=records,
                                           on_record=on_record, stop=stop, start_k=start_k,
                                           save=save)  # fmt: skip
    progress.close()
    save(k_end, worst)
    refusal = outcome if outcome is not None and "stop" not in outcome else None
    reason = (outcome or {}).get("stop") or ("refusal" if refusal else "planned end")
    wall = time.perf_counter() - tick
    steps = k_end - start_k
    write_json(out / "result.json", dict(
        arm=arm["id"], seed=args.seed, label=label(args.seed),
        engine_models=["resolved_pump_replacement@1 (inner resolved_pump_tissue@3)"],
        dt=dt, end_step=k_end, end_s=k_end * dt, planned_end_s=record["planned_end_s"],
        stop=reason, refusal=refusal, resumed_at_s=resumed, checks=checks, layout=layout,
        worst_device_diagnostics=None if worst is None else dict(
            zip(h.model.DEVICE_DIAGNOSTICS, worst.tolist(), strict=True)),
        records=len(records), wall_s=wall, setup_s=setup,
        ms_per_step=1e3 * (wall - setup) / max(steps, 1),
        peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        provenance=h.provenance()))  # fmt: skip
    log(f"{arm['id']} seed {args.seed}: {reason} at {k_end * dt} s; refusal {refusal}")
    return 0 if refusal is None else 3


# ------------------------------------------------------------------ the paired reading


def jaccard(d, inside):
    union = np.sum(d | inside)
    return float(np.sum(d & inside) / union) if union else 1.0


def run_class(delta_j, d_loss, recruitment, delta):
    """The protocol's run class from the run-level readouts (None fractions count as 0)."""
    d_loss, recruitment = d_loss or 0.0, recruitment or 0.0
    erosion = delta_j < -delta or d_loss > CLASS_FRACTION
    gain = delta_j > delta or recruitment > CLASS_FRACTION
    if erosion and gain:
        return "mixed"
    if erosion:
        return "erosion"
    if gain:
        return "recruitment"
    if (abs(delta_j) <= delta and d_loss <= NEUTRAL_FRACTION
            and recruitment <= NEUTRAL_FRACTION):  # fmt: skip
        return "neutral"
    return "small bias"


def group_class(classes):
    """A class holds when at least two thirds of the runs share it (both of two runs)."""
    if not classes:
        return None
    top, count = Counter(classes).most_common(1)[0]
    return top if count >= math.ceil(2 * len(classes) / 3) else "split"


def reading(record, result, t_all, d_all, osm_all, regular, *, abundance=None, gate=None):
    """A run against its paired copy-only null.

    t_all, d_all, osm_all: every record (regular and event-time); regular marks the 10 s
    records. The judged record is the protocol's (record["judged_at"]), or the last valid
    record of a censored run, or, for a run that ended all H, the judged time itself with
    the engine's J taken as 0 (all H is absorbing).
    """
    size, dt = record["size"], record["dt"]
    _, edges, neighbours = e7.sheet()
    n = d_all.shape[1]
    inside = np.zeros(n, dtype=bool)
    inside[sorted(e7.disc(size))] = True
    osm_h = sum(e7_h_state())
    t, d, excess = t_all[regular], d_all[regular], osm_all[regular] / osm_h - 1.0
    events = [(int(k), int(slot), None if donor is None else int(donor))
              for k, slot, donor, *_ in record["events"]]  # fmt: skip
    null = e7.null_series(events, size, record["planned_end_s"], dt=dt)
    null_j = dict(zip(np.round(null["t"], 9).tolist(), null["J"].tolist(), strict=True))
    turnover = record["turnover_complete_s"]
    target = e7.judged_time(dict(judged_at=record["judged_at"], end_s=record["planned_end_s"]),
                            turnover)  # fmt: skip
    stop = result["stop"]
    target_record = float(null["t"][np.searchsorted(null["t"], target + 1e-9) - 1])
    if stop == "censor":
        valid = np.flatnonzero(excess.max(axis=1) <= CENSOR)
        last_valid = float(t[valid[-1]])
        judged_t, basis = min(target_record, last_valid), "censored: last valid record"
    elif target_record <= t[-1] + 1e-9:
        judged_t, basis = target_record, "record"
    elif stop == "all_h":
        judged_t, basis = target_record, "absorbed (all H)"
    elif stop == "refusal":
        judged_t, basis = float(t[-1]), "refused"
    else:
        judged_t, basis = float(t[-1]), "development end (judged record not reached)"
    j_engine = [jaccard(row, inside) for row in d]
    if basis.startswith("absorbed"):
        j_judged = 0.0
    else:
        j_judged = j_engine[int(np.searchsorted(t, judged_t + 1e-9) - 1)]
    j_null = null_j[round(judged_t, 9)]
    delta_j = j_judged - j_null
    # Newcomers: their kind from the donor's engine state at the event record (the state
    # just before the event), their fate from their own records up to the judged record.
    index = {round(float(x), 9): i for i, x in enumerate(t_all)}
    by_slot = {}
    for j, (_k, slot, _) in enumerate(events):
        by_slot.setdefault(slot, []).append(j)
    rows, first_event = [], {}
    for k, slot, donor in events:
        te = k * dt
        first_event.setdefault(slot, te)
        if te >= judged_t - 1e-9 or te > t_all[-1] + 1e-9:  # Not yet applied, or after an
            continue  # absorbed run's last record (copies of H cells only).
        i = index[round(te, 9)]
        kind = "template" if donor is None else "D_copy" if d_all[i, donor] else "H_copy"
        later = [events[m][0] * dt for m in by_slot[slot] if events[m][0] * dt > te]
        death = later[0] if later else math.inf
        window = (t_all > te + 1e-9) & (t_all <= min(death, judged_t) + 1e-9)
        states = d_all[window, slot]
        rows.append(dict(
            slot=slot, kind=kind, birth_s=te, interior=bool(inside[slot] and all(
                inside[x] for x in neighbours[slot])),
            d_neighbours=int(d_all[i, neighbours[slot]].sum()),
            lost=bool(kind == "D_copy" and len(states) and (~states).any()),
            converted=bool(kind != "D_copy" and len(states) and states.any()),
        ))  # fmt: skip
    founders_lost = 0
    for cell in np.flatnonzero(inside):
        until = min(first_event.get(int(cell), math.inf), judged_t)
        window = (t_all > 0) & (t_all <= until + 1e-9)
        founders_lost += int((~d_all[window, cell]).any())
    d_copies = [r for r in rows if r["kind"] == "D_copy"]
    h_copies = [r for r in rows if r["kind"] == "H_copy"]
    templates = [r for r in rows if r["kind"] == "template"]
    d_loss = sum(r["lost"] for r in d_copies) / len(d_copies) if d_copies else None
    recruitment = sum(r["converted"] for r in h_copies) / len(h_copies) if h_copies else None
    candidates = [r for r in templates if r["interior"] and r["d_neighbours"] >= 5]
    delta = 2.0 / size
    upto = t <= judged_t + 1e-9
    # Supplementary (SUPPLEMENTARY), reported beside the registered single-record dJ: the
    # deviation over the run's records to the judged record, and after the first turnover.
    dj = np.array([e - null_j[round(float(x), 9)] for x, e in zip(t, j_engine, strict=True)])
    window = upto & (t > 0)
    later = window & (t > turnover[0] + 1e-9)
    out = dict(
        judged_target_s=target,
        judged_s=judged_t,
        basis=basis,
        J_engine=j_judged,
        J_null=j_null,
        delta_J=delta_j,
        delta=delta,
        delta_J_over_records=dict(
            status=SUPPLEMENTARY,
            mean=float(dj[window].mean()) if window.any() else None,
            min=float(dj[window].min()) if window.any() else None,
            max=float(dj[window].max()) if window.any() else None,
            mean_after_first_turnover=float(dj[later].mean()) if later.any() else None,
            nonzero_records=int(np.sum(np.abs(dj[window]) > 1e-12)),
            records=int(window.sum()),
        ),
        D_copies=len(d_copies),
        D_copies_lost=sum(r["lost"] for r in d_copies),
        D_loss_fraction=d_loss,
        H_copies=len(h_copies),
        H_copies_converted=sum(r["converted"] for r in h_copies),
        recruitment_fraction=recruitment,
        templates=len(templates),
        templates_converted=sum(r["converted"] for r in templates),
        interior_templates_with_5plus_D=len(candidates),
        interior_templates_with_5plus_D_converted=sum(r["converted"] for r in candidates),
        founders_lost=founders_lost,
        d_outside_max=int(d[upto][:, ~inside].sum(axis=1).max()),
        d_outside_max_null=int(null["d_outside"][null["t"] <= judged_t + 1e-9].max()),
        max_osmotic_excess=float(excess[upto].max()),
        first_flag_s=next(
            (float(x) for x, e in zip(t, excess, strict=True) if e.max() > FLAG), None
        ),  # fmt: skip
        run_class=run_class(delta_j, d_loss, recruitment, delta),
        newcomers_by_kind_and_D_neighbours={
            kind: [
                sum(1 for r in rows if r["kind"] == kind and r["d_neighbours"] == m)
                for m in range(7)
            ]
            for kind in ("D_copy", "H_copy", "template")
        },  # fmt: skip
        J_series=dict(
            t_s=t.tolist(), engine=j_engine, null=[null_j.get(round(float(x), 9)) for x in t]
        ),  # fmt: skip
    )
    if record["judged_at"] == "second turnover":
        through = t <= turnover[1] + 1e-9
        reached = turnover[1] <= t[-1] + 1e-9
        kept = [j for j, w in zip(j_engine, through, strict=True) if w]
        out["b1"] = bool(reached and all(j >= e7.B1_J for j in kept))
    if record["kind"] == "donor" and record["rule"] == "disc_neighbour":
        kept = [j for j, w in zip(j_engine, upto, strict=True) if w]
        held = all(j == 1.0 for j in kept)
        out["e4_disc_held"] = bool(held and out["D_copies_lost"] == 0 and founders_lost == 0)
    if abundance is not None and gate is not None:
        out["junction_weight"] = junction_weight(edges, d_all[regular], abundance[regular],
                                                 gate[regular], upto)  # fmt: skip
        law = e7.abundance_series(events, size, record["planned_end_s"], record["formation"],
                                  dt=dt)  # fmt: skip
        mask = (law["t"] > 0) & (law["t"] <= judged_t + 1e-9)
        out["law_abundance_to_judged"] = float(law["all"][mask].mean()) if mask.any() else None
    return out


def e7_h_state():
    """The H start's composition (Na, K, M, P in mM): the osmotic reference."""
    from validation.tissue import surface_pump_v3_fixtures as v3fx

    h = v3fx.HEREDITY_STATES["H"]
    return (h[1], h[2], h[3], v3fx.HEREDITY_FIXED_ANION_mM)


def junction_weight(edges, d, abundance, gate, mask):
    """E6: time-averaged A and A x gate over junction classes by their cells' states."""
    a_end = np.array([a for a, _ in edges])
    b_end = np.array([b for _, b in edges])
    sums = {k: dict(A=[], w=[]) for k in ("all", "D-D", "D-H", "H-H")}
    for row in np.flatnonzero(mask):
        da, db = d[row][a_end], d[row][b_end]
        a, w = abundance[row], abundance[row] * gate[row]
        for key, sel in (("all", np.ones_like(da)), ("D-D", da & db), ("D-H", da ^ db),
                         ("H-H", ~da & ~db)):  # fmt: skip
            if sel.any():
                sums[key]["A"].append(float(a[sel].mean()))
                sums[key]["w"].append(float(w[sel].mean()))
    return {k: dict(A=float(np.mean(v["A"])) if v["A"] else None,
                    weight=float(np.mean(v["w"])) if v["w"] else None,
                    records=len(v["A"])) for k, v in sums.items()}  # fmt: skip


def part_analyse(args):
    out = run_dir(args.output, args.arm, args.seed)
    record = json.loads((out / "plan.json").read_text())
    result = json.loads((out / "result.json").read_text())
    z = np.load(out / "records.npz")
    from validation.tissue.heredity_pilot import THRESHOLD_V

    value = reading(record, result, z["t"], z["vm"] > THRESHOLD_V, z["osm"], z["regular"],
                    abundance=z["abundance"], gate=z["gate"])  # fmt: skip
    value = dict(kind="cells.e07_v1_run_outcome@1", arm=record["arm"], seed=record["seed"],
                 label=record["label"], group=record["group"], s=record["s"],
                 size=record["size"], stop=result["stop"], refusal=result["refusal"],
                 checks=result.get("checks"), **value)  # fmt: skip
    # The pre-screen's per-newcomer coupling analysis (it reads plan, result and records).
    lit().opportunity(out)
    write_json(out / "outcome.json", value)
    log(f"{record['arm']} seed {record['seed']}: {value['run_class']}, dJ {value['delta_J']:.3f}"
        f" ({value['basis']})")  # fmt: skip


# ------------------------------------------------------------------ summary


def part_summary(args):
    base = Path(args.output)
    runs = sorted((base / "runs").glob("*/seed*/outcome.json"))
    rows = [json.loads(p.read_text()) for p in runs]
    groups = {}
    for r in rows:
        if r["group"] in ("fast k1", "central k1", "fast k3") and r["refusal"] is None:
            groups.setdefault(f"{r['group']}, s {r['s']}", []).append(r["run_class"])
    tau = {}
    for r in rows:
        if r["group"] == "threshold-finding":
            t_ = float(r["arm"].split("tau")[1].split("-")[0])
            tau.setdefault(r["s"], []).append((t_, r["interior_templates_with_5plus_D_converted"]))
    value = dict(
        kind="cells.e07_v1_summary@1",
        runs={
            f"{r['arm']}/seed{r['seed']}": {
                k: r.get(k)
                for k in (
                    "label",
                    "group",
                    "s",
                    "size",
                    "stop",
                    "basis",
                    "judged_s",
                    "J_engine",
                    "J_null",
                    "delta_J",
                    "delta_J_over_records",
                    "D_loss_fraction",
                    "recruitment_fraction",
                    "founders_lost",
                    "d_outside_max",
                    "d_outside_max_null",
                    "run_class",
                    "b1",
                    "e4_disc_held",
                    "max_osmotic_excess",
                    "junction_weight",
                    "law_abundance_to_judged",
                    "interior_templates_with_5plus_D",
                    "interior_templates_with_5plus_D_converted",
                    "refusal",
                    "checks",
                )
            }
            for r in rows
        },  # fmt: skip
        group_classes={k: dict(runs=v, class_=group_class(v)) for k, v in groups.items()},
        tau_star_single_draw={
            str(s): max((t_ for t_, c in v if c > 0), default=None) for s, v in tau.items()
        },
        e2_validity=dict(
            refusals=[
                k
                for k, r in ((f"{r['arm']}/seed{r['seed']}", r) for r in rows)
                if r["refusal"] is not None
            ],
            definition_checks_failed=[
                f"{r['arm']}/seed{r['seed']}"
                for r in rows
                if not all(
                    (r.get("checks") or {}).get(c, False)
                    for c in (
                        "donor_P_equals_slot_P",
                        "field_solver_as_declared",
                        "layout_equals_sheet70",
                    )
                )
            ],
        ),  # fmt: skip
        development_runs=sum(r["label"] == "development" for r in rows),
        supplementary_readouts=dict(delta_J_over_records=SUPPLEMENTARY),
    )
    write_json(base / "summary.json", value)
    log(f"summary: {len(rows)} runs, groups {value['group_classes']}")


# ------------------------------------------------------------------ E1


def e1_paths(base, segment, seed, dt):
    """(records, metadata) paths of an E1 segment at one dt (the dt's dot stays in the name)."""
    folder = Path(base) / "e1"
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"{segment}-seed{seed}-dt{dt:g}"
    return folder / f"{stem}.npz", folder / f"{stem}.json"


def part_e1(args):
    segment = E1_SEGMENTS[args.segment]
    arm = find_arm(segment["arm"])
    end_s = segment["end_s"] if args.end_s is None else args.end_s
    record = schedule(arm, args.seed, dt=args.dt, end_s=end_s, grid_dt=E1_GRID_DT)
    raw, checks = build(record)
    h = lit()
    from cells.core.specs import parse_spec

    spec = parse_spec(raw)
    tick = time.perf_counter()
    stepper = h.Stepper(spec)
    every = int(round(segment["every_s"] / args.dt))
    end = int(round(end_s / args.dt))
    marks = sorted(set(range(every, end + 1, every)) | {k for k, *_ in record["events"]} | {end})
    volume = np.asarray(stepper.host_p.volume)[: stepper.n]
    first = stepper.measure(0)
    first.update(t=0.0, regular=True, conc=first["amounts"][:3] / volume,
                 osm=first["amounts"].sum(axis=0) / volume)  # fmt: skip
    records = [first]
    k_end, refusal, worst = h.run_segments(stepper, marks, every=every, records=records)
    records_path, meta_path = e1_paths(args.output, args.segment, args.seed, args.dt)
    h.save_records(records_path, records)
    write_json(meta_path, dict(
        segment=args.segment, arm=arm["id"], seed=args.seed, label=label(args.seed), dt=args.dt,
        end_s=end_s, end_step=k_end, refusal=refusal, checks=checks,
        events=len(record["events"]), wall_s=time.perf_counter() - tick,
        worst_device_diagnostics=None if worst is None else dict(
            zip(h.model.DEVICE_DIAGNOSTICS, worst.tolist(), strict=True)),
        provenance=h.provenance()))  # fmt: skip
    log(f"e1 {args.segment} seed {args.seed} dt {args.dt}: end {k_end * args.dt} s, "
        f"refusal {refusal}")  # fmt: skip


def compare_pair(fine, coarse, refusals):
    """The pre-screen's criteria (its numerics/criteria.json) on two record sets."""
    h = lit()
    tf = {round(float(r["t"]), 6): r for r in fine if r["regular"]}
    tc = {round(float(r["t"]), 6): r for r in coarse if r["regular"]}
    common = sorted(set(tf) & set(tc))
    vf = np.array([tf[x]["vm"] for x in common])
    vc = np.array([tc[x]["vm"] for x in common])
    df, dc = vf > h.THRESHOLD_V, vc > h.THRESHOLD_V
    times = np.array(common)
    changes = dict(fine=h.transitions(times, df), coarse=h.transitions(times, dc))
    window = np.zeros_like(df)
    for which in changes.values():
        for i, rows in which.items():
            for x, _ in rows:
                window[:, i] |= np.abs(times - x) <= 1.0 + 1e-9
    mismatch = (df != dc) & ~window
    dv = np.abs(vf - vc)
    af = np.array([tf[x]["conc"] for x in common])
    ac = np.array([tc[x]["conc"] for x in common])
    rel = np.abs(af - ac) / np.maximum(np.abs(af), 1e-30)
    ex = np.abs(np.array([tf[x]["osm"] for x in common])
                - np.array([tc[x]["osm"] for x in common])) / h.h_osmolarity()  # fmt: skip
    paired, unpaired = [], []
    for i in sorted(set(changes["fine"]) | set(changes["coarse"])):
        a_, b_ = changes["fine"].get(i, []), changes["coarse"].get(i, [])
        if len(a_) != len(b_) or any(x[1] != y[1] for x, y in zip(a_, b_, strict=False)):
            unpaired.append(dict(cell=i, fine=a_, coarse=b_))
            continue
        paired += [
            dict(cell=i, to_D=x[1], shift_s=y[0] - x[0]) for x, y in zip(a_, b_, strict=True)
        ]
    checks = dict(
        no_refusal=not refusals,
        d_sets_identical_outside_windows=not bool(mismatch.any()),
        changes_paired_within_1s=not unpaired
        and all(abs(x["shift_s"]) <= 1.0 + 1e-9 for x in paired),  # fmt: skip
        vm_within_1mV=float(dv[~window].max(initial=0.0)) <= 1e-3,
        amounts_within_1em4=float(rel.max()) <= 1e-4,
        osmotic_excess_within_1em4=float(ex.max()) <= 1e-4,
    )
    return dict(
        common_records=len(common),
        checks=checks,
        passed=all(checks.values()),
        max_vm_difference_mV_outside_windows=1e3 * float(dv[~window].max(initial=0.0)),
        max_vm_difference_mV_all=1e3 * float(dv.max()),
        max_relative_amount_difference=float(rel.max()),
        max_osmotic_excess_difference=float(ex.max()),
        state_changes=len(paired),
        unpaired_state_changes=unpaired,
    )


def part_e1compare(args):
    h = lit()
    report = dict(kind="cells.e07_v1_e1@1", seed=args.seed, label=label(args.seed), segments={})
    for name in E1_SEGMENTS:
        paths = {dt: e1_paths(args.output, name, args.seed, dt) for dt in (0.001, 0.005)}
        if not all(records.exists() for records, _ in paths.values()):
            continue
        meta = {dt: json.loads(meta.read_text()) for dt, (_, meta) in paths.items()}
        refused = [m["refusal"] for m in meta.values() if m["refusal"] is not None]
        report["segments"][name] = compare_pair(
            h.load_records(paths[0.001][0]), h.load_records(paths[0.005][0]), refused
        )
    report["passed"] = bool(report["segments"]) and all(
        s["passed"] for s in report["segments"].values()
    )
    report["choose_dt"] = 0.005 if report["passed"] else 0.001
    write_json(Path(args.output) / "e1" / f"verdict-seed{args.seed}.json", report)
    log(f"e1 seed {args.seed}: passed {report['passed']}")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("part", choices=["arm", "analyse", "summary", "e1", "e1compare"])
    parser.add_argument("--output", required=True)
    parser.add_argument("--arm")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--dt", type=float, default=e7.DT)
    parser.add_argument("--end-s", type=float, help="development only: shorten the run")
    parser.add_argument("--segment", choices=sorted(E1_SEGMENTS))
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    if args.end_s is not None and args.seed < DEVELOPMENT_SEEDS_FROM:
        raise SystemExit("--end-s is for development seeds (101 or more) only")
    parts = dict(arm=part_arm, analyse=part_analyse, summary=part_summary, e1=part_e1,
                 e1compare=part_e1compare)  # fmt: skip
    return parts[args.part](args) or 0


if __name__ == "__main__":
    sys.exit(main())
