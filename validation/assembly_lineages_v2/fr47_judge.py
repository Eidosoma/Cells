"""FR-47's judge: the reference files' reader and the criteria's arithmetic (fr47_spec/CRITERIA.md
and its amendments; D323).

The judge reads three things:
- **the references' files** (SPEC.md §5, as amended), by structure first (`read_reference`);
- **the exact replicas' observables and stop records,** from `cells.assembly_lineages@2` runs
  (`exact_observables`, `exact_stops`);
- **(d)'s,** from `cells.rate_equations@1` runs (`d_observables`, `d_stops`, `d_intervals`). FR-47's
  build writes the stop events and rows these readers name.

It judges with the shared pair rule (`agreement.py`) and the deterministic bounds.

- `python -m validation.assembly_lineages_v2.fr47_judge read FILE...` reads reference files by
  structure: the judge's first read, on the references' invented files, before any engine run.
- `python -m validation.assembly_lineages_v2.fr47_judge check` runs its synthetic checks, on made-up
  inputs only.
"""

import json
import math
import sys
from pathlib import Path

import numpy as np

from validation.assembly_lineages_v2 import agreement

D_BOUND = 1e-5  # C1, C4 for (d), C7, C9: |y_d - y_ref| <= D_BOUND s_y
STEP_GUARD = 10_000  # C1: beyond this many accepted steps the deterministic result is inconclusive
EPS = 2.0**-52
TRACERS = ("S@pool", "S@lumen")  # C8 reads the tracer observables only (the second amendment)
RESOLVED = 4.5  # C8: a rung is resolved when |gap| / (SD / sqrt(M)) >= 4.5
M = 128

# ------------------------------------------------------------------ the references' files

_PAIR_KEYS = {"constant": {"value"}, "derived": {"value", "tolerance"},
              "spread": {"mean", "var", "mu4"}}  # fmt: skip


def _quantity_problems(q, where):
    """A pair-like quantity's problems: its class, and the keys and values its class needs."""
    if not isinstance(q, dict):
        return [f"{where}: not an object"]
    kind = q.get("class")
    if kind not in _PAIR_KEYS:
        return [f"{where}: class {kind!r} is not one of {sorted(_PAIR_KEYS)}"]
    missing = sorted(_PAIR_KEYS[kind] - set(q))
    if missing:
        return [f"{where}: a {kind} quantity lacks {missing}"]
    numbers = [q[k] for k in _PAIR_KEYS[kind]]
    if any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)
           for v in numbers):  # fmt: skip
        return [f"{where}: a {kind} quantity's values are finite numbers"]
    if kind == "spread" and not q["var"] > 0:
        return [f"{where}: a spread quantity's variance is positive"]
    return []


def founder_of(ref):
    """The founder's molecules per place, as the references' world block echoes them."""
    return dict(ref.get("world", {}).get("founder_molecules", {}))


def rung_of(ref):
    """A gated file's N_g, the founder's G@wall + H@wall (each rung is its own file), else None."""
    f = founder_of(ref)
    return int(f["G@wall"] + f["H@wall"]) if {"G@wall", "H@wall"} <= set(f) else None


def engine_place(name):
    """The engine's place for a reference observable: the references write the wall as `@wall`, the
    engine as `@membrane`."""
    return name.replace("@wall", "@membrane")


def read_reference(path):
    """(doc, summary, problems): one reference file read by structure (SPEC.md §5, amended)."""
    doc = json.loads(Path(path).read_text())
    problems = []
    for key in ("world", "pairs", "stops", "d", "plants", "provenance"):
        if key not in doc:
            problems.append(f"missing the key {key!r}")
    for i, p in enumerate(doc.get("pairs", [])):
        where = f"pairs[{i}]"
        if not isinstance(p, dict) or not {"observable", "time_s"} <= set(p):
            problems.append(f"{where}: needs observable and time_s")
            continue
        problems += _quantity_problems(p, where)
    for i, s in enumerate(doc.get("stops", [])):
        where = f"stops[{i}]"
        keys = {"time_s", "kind", "f", "removed", "mixing_heat"}
        if not isinstance(s, dict) or not keys <= set(s):
            problems.append(f"{where}: needs time_s, kind, f, removed and mixing_heat")
            continue
        if s["kind"] not in ("withdrawal", "replacement"):
            problems.append(f"{where}: kind {s['kind']!r}")
        problems += _quantity_problems(s["removed"], f"{where}.removed")
        if s["kind"] == "replacement":
            if s["f"] != 1.0 or s["mixing_heat"] is not None:
                problems.append(f"{where}: a replacement has f 1.0 and mixing_heat null")
        else:
            problems += _quantity_problems(s["mixing_heat"], f"{where}.mixing_heat")
    d = doc.get("d", {})
    for key in ("pairs", "stops", "intervals"):
        if not isinstance(d.get(key), list):
            problems.append(f"d.{key} is a list")
    for i, p in enumerate(d.get("pairs", []) or []):
        if not isinstance(p, dict) or not {"observable", "time_s", "value"} <= set(p):
            problems.append(f"d.pairs[{i}]: needs observable, time_s and value")
    for i, iv in enumerate(d.get("intervals", []) or []):
        if not isinstance(iv, dict) or not {"start_s", "end_s", "heat"} <= set(iv):
            problems.append(f"d.intervals[{i}]: needs start_s, end_s and heat")
    for i, g in enumerate(doc.get("gap", []) or []):
        if not isinstance(g, dict) or not {"observable", "time_s", "gap", "resolution"} <= set(g):
            problems.append(f"gap[{i}]: needs observable, time_s, gap and resolution")
    for i, pl in enumerate(doc.get("plants", [])):
        need = {"plant", "criterion", "honest", "planted", "distance_in_bounds"}
        if not isinstance(pl, dict) or not need <= set(pl):
            problems.append(f"plants[{i}]: needs {sorted(need)}")
    classes = {}
    for p in doc.get("pairs", []):
        if isinstance(p, dict):
            classes[p.get("class")] = classes.get(p.get("class"), 0) + 1
    summary = {"pairs": len(doc.get("pairs", [])), "classes": classes,
               "stops": len(doc.get("stops", [])),
               "d": {k: len(d.get(k) or []) for k in ("pairs", "stops", "intervals")},
               "gap": len(doc.get("gap", []) or []),
               "plants": len(doc.get("plants", [])), "rung": rung_of(doc)}  # fmt: skip
    return doc, summary, problems


# ------------------------------------------------------------------ the engine's runs

OBSERVED = 3  # population.ROW_KINDS' "observed"


def exact_observables(run, world, places, times):
    """{(place, time): value} of one exact population run's observed rows (one slot)."""
    names = [p.name for p in world.places]
    kinds = np.asarray(run.rows["row_kind"])
    at = np.asarray(run.rows["row_time"])[kinds == OBSERVED]
    pool = np.asarray(run.rows["pool_count"])[kinds == OBSERVED]
    slot = np.asarray(run.rows["slot_count"])[kinds == OBSERVED][:, 0]
    out = {}
    for place in places:
        i = names.index(place)
        column = pool[:, i] if place.endswith("@pool") else slot[:, i]
        for t in times:
            hit = np.flatnonzero(at == t)
            out[(place, t)] = float(column[hit[0]]) if hit.size else math.nan
    return out


def exact_stops(run, tracer="S@pool"):
    """[(time, kind, removed, mixing heat or None)] of one exact run's washes."""
    pop = run.population or {}
    out = [(w["time_s"], "withdrawal", float(w["withdrawn"][tracer]), float(w["mixing_heat_kT"]))
           for w in pop.get("withdrawals", [])]  # fmt: skip
    out += [(r["time_s"], "replacement", float(r["removed"][tracer]), None)
            for r in pop.get("replacements", [])]  # fmt: skip
    return sorted(out)


def d_observables(run, world, places, times):
    """{(place, time): value} of one (d) population run's observed rows (one slot)."""
    names = [p.name for p in world.places]
    rows = run.rows
    obs = np.asarray(rows["row_kind"]) == "observed"
    at = np.asarray(rows["row_time_s"])[obs]
    pool = np.asarray(rows["pool_counts"])[obs]
    slot = np.asarray(rows["slot_counts"])[obs][:, 0]
    out = {}
    for place in places:
        i = names.index(place)
        column = pool[:, i] if place.endswith("@pool") else slot[:, i]
        for t in times:
            hit = np.flatnonzero(at == t)
            out[(place, t)] = float(column[hit[0]]) if hit.size else math.nan
    return out


def d_stops(run, tracer="S@pool"):
    """[(time, kind, removed, mixing heat or None)] of one (d) run's washes, from its events of kind
    withdrawal or replacement (FR-47's build writes `removed` by place and `mixing_heat_kT`)."""
    out = []
    for e in run.events:
        if e.get("kind") in ("withdrawal", "replacement"):
            heat = e.get("mixing_heat_kT") if e["kind"] == "withdrawal" else None
            out.append((e["time_s"], e["kind"], float(e["removed"][tracer]),
                        None if heat is None else float(heat)))  # fmt: skip
    return sorted(out)


def d_intervals(run, stop_times, horizon):
    """[(start, end, heat)]: (d)'s continuous heat over each interval between stops, from the rows'
    continuous_heat_kT at the interval's ends (the start row, each stop's row, the end row)."""
    rows = run.rows
    t = np.asarray(rows["row_time_s"])
    q = np.asarray(rows["continuous_heat_kT"])
    edges = [0.0, *stop_times, horizon]
    out = []
    for a, b in zip(edges, edges[1:], strict=False):
        qa, qb = q[np.flatnonzero(t == a)], q[np.flatnonzero(t == b)]
        out.append((a, b, float(qb[-1] - qa[-1]) if qa.size and qb.size else math.nan))
    return out


# ------------------------------------------------------------------ the criteria


def scales(ref, founder):
    """s_y (the amendments' §6): per observable over the founder and the times, per stop quantity
    over the world's stops (heats over withdrawals), and over the intervals."""
    def mag(q):
        return abs(q["value"] if q["class"] in ("constant", "derived") else q["mean"])

    per = {}
    for p in ref["pairs"]:
        per[p["observable"]] = max(per.get(p["observable"], abs(founder.get(p["observable"], 0.0))),
                                   mag(p))  # fmt: skip
    removed = max([mag(s["removed"]) for s in ref["stops"]] or [0.0])
    heat = max([mag(s["mixing_heat"]) for s in ref["stops"] if s["mixing_heat"]] or [0.0])
    interval = max([abs(i["heat"]) for i in ref["d"]["intervals"]] or [0.0])
    return {"pairs": per, "removed": removed, "heat": heat, "interval": interval}


def judge_d(ref, d_pairs, d_stops_, d_intervals_, founder, accepted_steps):
    """C1, C4's (d) part and C9 (C7 on W2's mean-field reference): every (d) value within
    D_BOUND s_y of the reference's (d) value; inconclusive beyond STEP_GUARD accepted steps."""
    s = scales(ref, founder)
    worst, failures = 0.0, []

    def one(name, got, want, scale):
        nonlocal worst
        if scale > 0:
            ratio = abs(got - want) / (D_BOUND * scale)
        else:
            ratio = 0.0 if got == want else math.inf
        worst = max(worst, ratio)
        if not ratio <= 1.0:
            failures.append(name)

    for p in ref["d"]["pairs"]:
        one(f"{p['observable']}@{p['time_s']}", d_pairs[(p["observable"], p["time_s"])],
            p["value"], s["pairs"].get(p["observable"], 0.0))  # fmt: skip
    for (t, kind, removed, heat), r in zip(d_stops_, ref["d"]["stops"], strict=True):
        one(f"removed@{t}", removed, r["removed"], s["removed"])
        if kind == "withdrawal":
            one(f"heat@{t}", heat, r["mixing_heat"], s["heat"])
    for (a, b, heat), r in zip(d_intervals_, ref["d"]["intervals"], strict=True):
        one(f"interval {a}-{b}", heat, r["heat"], s["interval"])
    inconclusive = accepted_steps > STEP_GUARD
    return {"worst_in_bounds": worst, "failures": failures, "inconclusive": inconclusive,
            "passes": not failures and not inconclusive, "fails": bool(failures)}  # fmt: skip


def judge_exact(ref, replicas, stops_by_replica):
    """C2, C3 and C4 (C6 on W2): every pair and stop quantity under the pair rule.
    replicas: {(observable, time): [M values]}; stops_by_replica: [M lists of exact_stops]."""
    results = []
    for p in ref["pairs"]:
        results.append((f"{p['observable']}@{p['time_s']}",
                        agreement.judge(replicas[(p["observable"], p["time_s"])], p)))
    for k, s in enumerate(ref["stops"]):
        removed = [stops[k][2] for stops in stops_by_replica]
        results.append((f"removed@{s['time_s']}", agreement.judge(removed, s["removed"])))
        if s["mixing_heat"] is not None:
            heats = [stops[k][3] for stops in stops_by_replica]
            results.append((f"heat@{s['time_s']}", agreement.judge(heats, s["mixing_heat"])))
    fails = [n for n, r in results if r["fails"]]
    band = [n for n, r in results if not r["passes"] and not r["fails"]]
    return {"results": results, "fails": fails, "inconclusive": band,
            "passes": not fails and not band}  # fmt: skip


def books(exact_closures, exact_balances, d_closure, d_balance_gap, accepted, stops, places,
          tracer_founder):
    """C5: every run's ledger closes; the tracer moiety balances, exactly in exact events, and in
    (d) within 16 eps (A + S) P_t T (CRITERIA C5)."""
    bound = 16.0 * EPS * (accepted + stops) * places * tracer_founder
    ok = all(exact_closures) and all(exact_balances) and d_closure and abs(d_balance_gap) <= bound
    return {"passes": ok, "fails": not ok, "d_bound": bound}


def c8_report(gaps_by_rung):
    """C8, reported only (the second amendment): per rung the largest |gap| over the tracer
    observables (ties to S@pool, then the earliest time), its resolution, and the slope of ln|gap|
    in ln N_g over every rung; never claimed as measured."""
    chosen = {}
    for n_g, rows in sorted(gaps_by_rung.items()):
        tracer = [g for g in rows if g["observable"] in TRACERS]
        tracer.sort(key=lambda g: (-abs(g["gap"]), TRACERS.index(g["observable"]), g["time_s"]))
        chosen[n_g] = tracer[0]
    x = np.log(np.asarray(sorted(chosen), dtype=float))
    y = np.log(np.asarray([abs(chosen[n]["gap"]) for n in sorted(chosen)]))
    slope = float(np.polyfit(x, y, 1)[0]) if len(x) >= 2 else math.nan
    resolved = [n for n in sorted(chosen) if chosen[n]["resolution"] >= RESOLVED]
    return {"pairs": {n: chosen[n] for n in sorted(chosen)}, "slope": slope,
            "rungs_resolved": resolved, "claimed": False}  # fmt: skip


def plant_caught(criteria, refused=False):
    """A plant is caught when one of its criteria fails, or when its run is refused by its own
    books or checks (CRITERIA, the plants)."""
    return bool(refused or any(c.get("fails") for c in criteria))


def world_verdict(criteria):
    """pass when every criterion passes; fail when one fails; inconclusive otherwise."""
    if any(c.get("fails") for c in criteria):
        return "fail"
    return "pass" if all(c.get("passes") for c in criteria) else "inconclusive"


# ------------------------------------------------------------------ the synthetic checks


def _made_up_reference():
    """A made-up reference in SPEC.md §5's layout: one constant, two spread pairs, a withdrawal and
    a replacement, (d)'s values and an interval, and one plant. No protocol value."""
    return {
        "world": {"name": "made-up"},
        "pairs": [{"observable": "B@wall", "time_s": 1.0, "class": "constant", "value": 7.0},
                  {"observable": "S@pool", "time_s": 1.0, "class": "spread", "mean": 50.0,
                   "var": 20.0, "mu4": 3 * 20.0**2 + 20.0},
                  {"observable": "S@lumen", "time_s": 1.0, "class": "spread", "mean": 10.0,
                   "var": 8.0, "mu4": 3 * 8.0**2 + 8.0}],
        "stops": [{"time_s": 2.0, "kind": "withdrawal", "f": 0.5,
                   "removed": {"class": "spread", "mean": 25.0, "var": 12.5,
                               "mu4": 3 * 12.5**2 + 12.5},
                   "mixing_heat": {"class": "spread", "mean": 17.3, "var": 6.0,
                                   "mu4": 3 * 6.0**2 + 6.0}},
                  {"time_s": 3.0, "kind": "replacement", "f": 1.0,
                   "removed": {"class": "spread", "mean": 20.0, "var": 10.0,
                               "mu4": 3 * 10.0**2 + 10.0},
                   "mixing_heat": None}],
        "d": {"pairs": [{"observable": "S@pool", "time_s": 1.0, "value": 50.0}],
              "stops": [{"time_s": 2.0, "removed": 25.0, "mixing_heat": 17.3},
                        {"time_s": 3.0, "removed": 20.0, "mixing_heat": None}],
              "intervals": [{"start_s": 0.0, "end_s": 2.0, "heat": 100.0}]},
        "plants": [{"plant": "P0", "criterion": "C1", "honest": 50.0, "planted": 60.0,
                    "distance_in_bounds": 1.0e4}],
        "provenance": {"made_up": True},
    }  # fmt: skip


def check():
    rng = np.random.default_rng(470000)
    out = {}
    ref = _made_up_reference()
    tmp = Path("/tmp/fr47_judge_made_up_reference.json")
    tmp.write_text(json.dumps(ref))
    _, summary, problems = read_reference(tmp)
    broken = dict(ref, pairs=[dict(ref["pairs"][0], **{"class": "exact"})])
    tmp.write_text(json.dumps(broken))
    _, _, broken_problems = read_reference(tmp)
    tmp.unlink()
    out["the reader: a well-formed file reads clean, a wrong class is named"] = {
        "summary": summary, "ok": not problems and bool(broken_problems)}
    founder = {"S@pool": 60.0, "S@lumen": 0.0, "B@wall": 7.0}
    honest = judge_d(ref, {("S@pool", 1.0): 50.0 + 1e-6},
                     [(2.0, "withdrawal", 25.0, 17.3), (3.0, "replacement", 20.0, None)],
                     [(0.0, 2.0, 100.0)], founder, accepted_steps=500)  # fmt: skip
    off = judge_d(ref, {("S@pool", 1.0): 50.5},
                  [(2.0, "withdrawal", 25.0, 17.3), (3.0, "replacement", 20.0, None)],
                  [(0.0, 2.0, 100.0)], founder, accepted_steps=500)  # fmt: skip
    long = judge_d(ref, {("S@pool", 1.0): 50.0},
                   [(2.0, "withdrawal", 25.0, 17.3), (3.0, "replacement", 20.0, None)],
                   [(0.0, 2.0, 100.0)], founder, accepted_steps=STEP_GUARD + 1)  # fmt: skip
    out["(d): within the bound passes, beyond fails, past the step guard inconclusive"] = {
        "ok": honest["passes"] and off["fails"] and long["inconclusive"]}
    replicas = {("B@wall", 1.0): np.full(M, 7.0),
                ("S@pool", 1.0): rng.normal(50.0, math.sqrt(20.0), M),
                ("S@lumen", 1.0): rng.normal(10.0, math.sqrt(8.0), M)}  # fmt: skip
    stops = [[(2.0, "withdrawal", rng.normal(25.0, math.sqrt(12.5)),
               rng.normal(17.3, math.sqrt(6.0))),
              (3.0, "replacement", rng.normal(20.0, math.sqrt(10.0)), None)]
             for _ in range(M)]  # fmt: skip
    good = judge_exact(ref, replicas, stops)
    one_wrong = dict(replicas)
    one_wrong[("B@wall", 1.0)] = np.r_[np.full(M - 1, 7.0), 8.0]
    bad = judge_exact(ref, one_wrong, stops)
    out["exact: honest replicas pass; one wrong replica of a constant fails"] = {
        "ok": good["passes"] and "B@wall@1.0" in bad["fails"]}
    gaps = {64: [{"observable": "S@pool", "time_s": 1.0, "gap": -4.0, "resolution": 1.0},
                 {"observable": "S@lumen", "time_s": 1.0, "gap": 4.0, "resolution": 1.0},
                 {"observable": "G@wall", "time_s": 1.0, "gap": 9.0, "resolution": 3.0}],
            256: [{"observable": "S@pool", "time_s": 1.0, "gap": -1.0, "resolution": 0.5},
                  {"observable": "S@lumen", "time_s": 1.0, "gap": 1.0, "resolution": 0.5},
                  {"observable": "G@wall", "time_s": 1.0, "gap": 9.0, "resolution": 3.0}]}
    report = c8_report(gaps)
    out["C8: tracers only, ties to S@pool, slope reported, never claimed"] = {
        "slope": report["slope"],
        "ok": all(p["observable"] == "S@pool" for p in report["pairs"].values())
        and abs(report["slope"] - (-1.0)) < 1e-12 and report["claimed"] is False}  # fmt: skip
    out["plants and verdicts"] = {
        "ok": plant_caught([{"fails": True}]) and plant_caught([], refused=True)
        and not plant_caught([{"fails": False}])
        and world_verdict([{"passes": True}, {"passes": True}]) == "pass"
        and world_verdict([{"passes": False, "fails": False}]) == "inconclusive"
        and world_verdict([{"fails": True}]) == "fail"}  # fmt: skip
    return out


def main(argv):
    if argv[:1] == ["read"] and argv[1:]:
        bad = False
        for path in argv[1:]:
            _, summary, problems = read_reference(path)
            print(json.dumps({"file": path, "summary": summary, "problems": problems}, indent=1))
            bad |= bool(problems)
        return 1 if bad else 0
    if argv == ["check"]:
        results = check()
        print(json.dumps(results, indent=1, default=str))
        return 0 if all(r["ok"] for r in results.values()) else 1
    raise SystemExit("usage: python -m validation.assembly_lineages_v2.fr47_judge "
                     "read FILE... | check")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
