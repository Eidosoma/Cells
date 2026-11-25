"""The verdicts of FR-38's second comparison: per run, family, arm and criterion, with the plants.

- **The engine's export** is the registered tables (amendment 4, §8; amendments 5 and 6). The
  structure pass reads every entry (`shapes`), the value pass its numbers (`records`), and C0's echo
  its declaration (`definitions`).
- **Runs.** Each judged run (the labelled runs and the blanks, against the reference's runs of the
  same name) is judged at the rungs 4h, 2h and h of its attempt: C1 at every rung, C2 and C3 at h
  from the three rungs, route 2 at h alone, C4 at every rung with that rung's S. A run inconclusive
  at the primary attempt takes the retry when its retry records exist (judged at 0.25 s); otherwise
  it stays inconclusive, retry pending (CRITERIA.md §1, §4).
- **A refusal never hides a fail** (amendment 6, §1). Every entry that can be formed from the rungs
  that ran is judged, and one failing entry fails the run, whatever else is refused. With none, a
  run with a refused or missing rung of its own is scored refused, and takes no retry. A refused or
  missing support run (the blank, the twin, AN's restart) leaves the run as it is and its family at
  best inconclusive; it is listed apart (`support_refused`), and so are the differences that are
  recorded and never judged (§3).
- **Plants** (CRITERIA.md §6; amendment 4, items 5 and 7; amendment 5, items 1 to 3 and 6; amendment
  6, §1 and §4). P1 and P1″ act on copies of the mapping file; P1′ (the net-rate host form) and P6
  (G without the hold's standard term) on copies of the honest records at h; the world-data plants
  and P9 are table entries at h, whose declarations differ from their honest runs' only by their
  registered change. Each is scored with the honest run's primary tolerance at h. A plant is caught
  by a failure of its own "By" readouts, or by the engine's own refusal of its run; a C2 catch
  counts only where the honest tolerance does not exceed the reference's largest predicted distance
  for that run and quantity. A judge-side refusal is not a catch. A plant is unscorable where its
  honest run's own rungs are refused or missing (P1″: its blank's too); an unscorable core plant
  leaves FR-38 at best inconclusive.
"""

import copy
import hashlib
import json
import math
import os
import subprocess
import sys

import numpy as np

from . import definitions, records, rules, shapes, spec

MAPPING_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mapping.json")
VERDICT_KIND = "cells.fr38_v2.verdict@1"


# ------------------------------------------------------------------ the mapping


def load_mapping(path=MAPPING_PATH):
    with open(path, encoding="utf-8") as fh:
        m = json.load(fh)
    if m.get("kind") != "cells.fr38_v2.judge_mapping@1":
        raise ValueError(f"{path}: not the judge's mapping file")
    names = set()
    for e in m["readouts"]:
        for k in ("name", "engine", "reference", "scale", "order", "status", "blank"):
            if k not in e:
                raise ValueError(f"mapping entry {e.get('name')!r} lacks {k!r}")
        if e["name"] in names:
            raise ValueError(f"mapping names {e['name']!r} twice")
        names.add(e["name"])
        if not set(e["status"]) <= set(spec.PROFILES) or not set(e["status"].values()) <= {
            "judged",
            "reported",
        }:
            raise ValueError(f"mapping entry {e['name']!r}: bad status {e['status']!r}")
    return m


def planted_mapping(mapping, plant):
    """A copy of the mapping file with P1's or P1″'s confusion written into it."""
    m = copy.deepcopy(mapping)
    for e in m["readouts"]:
        if plant == "P1" and e["name"] in ("label_R_win", "label_R_s_win"):
            fate = "durable" if e["name"] == "label_R_win" else "short_lived"
            e["meta"], e["reference"] = e["reference"], f"not_compared/cohort_net_{fate}"
        elif plant == "P1″" and e["name"].startswith("excess_over_blank_"):
            fate = e["name"][len("excess_over_blank_") :]
            e["reference"] = f"series/released_present_gross_{fate}"
    return m


def ref_side(rrun, entry):
    """The reference's series that a mapping entry pairs with the engine's."""
    kind, _, name = entry["reference"].partition("/")
    if kind == "series":
        return rrun.series.get(name)
    if kind == "excess_over_blank":
        return rrun.excess.get(name)
    if kind == "not_compared":
        vals = rrun.not_compared.get(name)
        meta = ref_side(rrun, {"reference": entry["meta"]})
        if vals is None or meta is None:
            return None
        return records.RefSeries(meta.constant, vals, meta.accuracy, meta.scale)
    return None


# ------------------------------------------------------------------ the families' contexts


class Family:
    """One family's context.

    - `role` is the registered family whose structure it follows (AF, AN, B, C or D): its blanks,
      twins, restart, plants and arm. A registered family is its own role.
    - `inputs` are SPEC.md's for a registered family (`spec.spec_inputs`), so that engine
      definitions, rates, potentials and pool totals are read from the spec, never from the
      reference's echo; an invented family's are its own file's.
    - An invented family with no role keeps its own plants (those its file sizes) and verdict; one
      with a role is judged as that registered family would be (the tests' route to the
      registered branches)."""

    def __init__(self, name, profile, reference, role=None):
        self.name, self.profile, self.ref = name, profile, reference
        self.invented = name not in spec.REAL_FAMILIES
        self.role = role if self.invented else name
        self.inputs = reference.inputs if self.invented else spec.spec_inputs(name)
        self.times = [float(t) for t in reference.times]
        self.window = reference.window
        self.samples = reference.samples
        self.held_blank_present = False

    def steps(self, dt):
        return int(round(float(self.inputs["horizon_s"]) / dt))

    def blank_machines(self):
        if self.role is None:
            return ("returned", "held")
        return spec.blank_machines(self.role)

    def twin_runs(self):
        """The unlabelled twins: of p_sched `returned` in the hold worlds, of each run in B."""
        if self.profile == "B":
            return spec.honest_runs(self.inputs)
        return [r for r in spec.honest_runs(self.inputs) if r == "p_sched returned"]

    def restart(self):
        """(run, checkpoint): AN's at 7200 s; a role-playing invented family's at half its
        horizon; an invented family with no role may carry one (optional)."""
        half = float(self.inputs["horizon_s"]) / 2.0
        if self.role is None:
            return ("p_sched returned", half)
        if self.role in spec.RESTART:
            run, t = spec.RESTART[self.role]
            return (run, half if self.invented else t)
        return None

    def restart_optional(self):
        return self.role is None


# ------------------------------------------------------------------ C0 on the references


def read_references(ref_dir, families, mapping):
    """CRITERIA.md C0: the invented file first, then each family's file. `families` maps each
    family to its profile; a family whose name is not registered is read as invented."""
    out_dir = (
        os.path.join(ref_dir, "out") if os.path.isdir(os.path.join(ref_dir, "out")) else ref_dir
    )
    order = sorted(families, key=lambda f: (f != "invented", f in spec.REAL_FAMILIES, f))
    refs = {}
    for fam in order:
        path = os.path.join(out_dir, f"reference_{fam}.json")
        expected = spec.spec_inputs(fam) if fam in spec.REAL_FAMILIES else None
        refs[fam] = records.read_reference(
            path, fam, families[fam], mapping, expected_inputs=expected
        )
    return refs, order


def sizing_report(ref):
    """CRITERIA.md §6's sizing rule on the references' own plant entries (reported, before any
    run): each entry's relative distance against 10 × the expected honest relative tolerance of
    its readout's kind, and per must-catch unit the best margin among the readouts that catch it.
    C1 catches (P2, and P1″ at an idle fate) are bitwise, so the rule does not size them."""
    rows, units = [], {}
    for e in ref.plants:
        q, plant = e["quantity"], e["plant"]
        kind = (
            "route2" if q.startswith("route2_") else "G" if q == "G_minus_G0"
            else "heat" if q.startswith("H_") and q != "H_tx_release"
            else "label" if q.startswith(("label_", "released_present_gross_"))
            else "amount"
        )  # fmt: skip
        by_c1 = plant == "P2" or (plant == "P1″" and e["honest"] == 0.0)
        need = 10.0 * spec.SIZING_EXPECTATION[kind]
        if ref.family == "AF" and plant == "P1":
            role = "reported only"
        elif plant == "P8" and q in spec.P8_NEGATIVE_CONTROL:
            role = "negative control"
        elif ref.family == "AF" and plant == "P1″" and not by_c1:
            role = "not must-catch"
        else:
            role = "catch"
        rows.append(
            {
                "plant": plant,
                "run": e["run"],
                "quantity": q,
                "time_s": e["time_s"],
                "relative_distance": e["relative_distance"],
                "expected_kind": kind,
                "ten_times_expectation": need,
                "caught_by": "C1" if by_c1 else "C2",
                "role": role,
                "below_ten_times": (not by_c1) and e["relative_distance"] < need,
            }
        )
        if role != "catch":
            continue
        if by_c1:
            unit = f"{e['run']} {q}"
        elif plant in ("P1", "P1′", "P1″"):
            unit = "any run"
        else:
            unit = e["run"]
        margin = None if by_c1 else e["relative_distance"] / need
        prev = units.get((plant, unit), 0.0)
        units[(plant, unit)] = None if (margin is None or prev is None) else max(prev, margin)
    summary = [
        {
            "plant": p,
            "unit": u,
            "caught_by": "C1" if m is None else "C2",
            "best_margin_over_ten_times": m,
            "below_ten_times": m is not None and m < 1.0,
        }
        for (p, u), m in sorted(units.items())
    ]
    return {"entries": rows, "units": summary}


def _largest_checks(ref):
    """The references' own checks (SPEC.md §3, item 7): each key's largest over the runs."""
    out = {}
    for run in ref.runs.values():
        for k, v in run.checks.items():
            out[k] = max(out.get(k, 0.0), abs(v))
    return out


# ------------------------------------------------------------------ the engine records


def index_records(tables, fams, mapping, table_shapes):
    """C0 on every entry of every table, then an index by (family, role, run, plant, attempt, dt,
    machine). Returns (index, what C0 found)."""
    passes = []
    for tab in tables["tables"]:
        fam = fams.get(tab["family"])
        if fam is None:
            continue
        restart = fam.restart()
        st = records.table_structure(tab, fam.profile, fam.role, fam.inputs,
                                     restart[0] if restart else None, table_shapes)  # fmt: skip
        if fam.role is None and any(e.role == "blank" and e.machine == "held" for e in st.entries):
            fam.held_blank_present = True
        passes.append((tab, fam, st))
    recs, notes = [], []
    for tab, fam, st in passes:
        got, tab["faults"] = records.table_records(tab, st, fam.inputs, fam.times, fam.samples,
                                                   fam.window)  # fmt: skip
        label = f"{tab['family']} {tab['attempt']}"
        notes += [f"{label}: {n}" for n in st.notes]
        notes += [f"{label}: {f[1]}: {f[2]} (recorded)" for f in st.findings
                  if f[0] == "unexpected"]  # fmt: skip
        if isinstance(tab["doc"], dict) and tab["doc"].get("missing"):
            notes.append(f"{label}: the table lists missing records: {tab['doc']['missing']!r}")
        restart = fam.restart()
        for rec in got:
            records.check_record(rec, fam.inputs, fam.times, mapping, fam.profile,
                                 blank_machines=fam.blank_machines(), two_blanks=two_blanks(fam),
                                 checkpoint_s=restart[1] if restart else None)  # fmt: skip
        recs += got
    index = {}
    for rec in recs:  # a table's keys are unique, so no two entries share a key
        index[rec.key] = rec
    flags = _compare_declarations(recs, index, fams)
    flags += _decide_excess(recs, index, fams)
    flags += _source_flags(recs)
    return index, _c0_report(recs, notes, flags)


def _decide_excess(recs, index, fams):
    """Amendment 6, §1: `excess_over_blank` may be absent only where the entry's blank is refused or
    missing. Where its blank is so and the excess is there all the same, it is not judged."""
    flags = []
    for rec in recs:
        fam = fams[rec.family]
        if rec.kind not in ("labelled", "twin", "restart", "P8") or not spec.has_blank(fam.profile):
            continue
        blank = _blank_of(rec, index, fam)
        why = _usable(blank, "its blank")
        if rec.excess_absent and why is None:
            rec.faults.append(f"{rec.where}.excess_over_blank: missing, and its blank "
                              f"({blank.where}) is there and not refused")  # fmt: skip
        elif rec.status == "completed" and why is not None and not rec.faults:
            state = "absent" if rec.excess_absent else "there, and not judged"
            flags.append(f"{rec.family} {rec.attempt} {rec.where}: its excess over the blank is "
                         f"{state}: {why}")  # fmt: skip
    return flags


def _blank_of(rec, index, fam):
    """The registered blank of an entry: P8's is the planted one (amendment 5, item 2)."""
    if rec.role == "plant":
        return _get(index, fam.name, "plant", "blank", "primary", spec.H_STEP_S, plant="P8",
                    machine="returned")  # fmt: skip
    return _blank_at(index, fam, rec.run, rec.attempt, rec.dt)


def _blank_at(index, fam, run, attempt, dt):
    return _get(index, fam.name, "blank", "blank", attempt, dt,
                machine=matched_blank_machine(fam, run))  # fmt: skip


def _compare_declarations(recs, index, fams):
    """Amendment 5, item 6: a plant's declaration is its honest run's but for its registered change,
    or it is refused; a twin's and a blank's are recorded and flagged where they depart from their
    run's at a key the echo does not cover."""
    flags = []
    for rec in recs:
        if rec.faults or not isinstance(rec.definition, dict):
            continue
        if rec.role == "plant":
            if rec.blank:
                key = (rec.family, "blank", "blank", None, "primary", spec.H_STEP_S, "returned")
            else:
                key = (rec.family, "honest", rec.run, None, "primary", spec.H_STEP_S, None)
            honest = index.get(key)
            if honest is None or not isinstance(honest.definition, dict):
                rec.faults.append(f"{rec.where}: its honest run's entry at 0.5 s, needed for the "
                                  "declaration check, is missing")  # fmt: skip
                continue
            rec.faults += [f"{rec.where}.definition: {x}" for x in definitions.plant_change_faults(
                rec.plant, honest.definition, rec.definition, fams[rec.family].inputs)]  # fmt: skip
        elif rec.role in ("twin", "blank"):
            run = rec.run if rec.role == "twin" else f"p_sched {rec.machine}"
            other = index.get((rec.family, "honest", run, None, rec.attempt, rec.dt, None))
            if other is None or not isinstance(other.definition, dict):
                continue
            compare = (definitions.twin_differences if rec.role == "twin"
                       else definitions.blank_differences)  # fmt: skip
            flags += [f"{rec.family} {rec.attempt}: {rec.where}.definition: beside its run's: {x}"
                      for x in compare(other.definition, rec.definition)]  # fmt: skip
    return flags


def _source_flags(recs):
    """Amendment 5, item 5: entries that differ in engine_revision or snapshot."""
    flags = []
    for key in ("engine_revision", "snapshot"):
        seen = {}
        for r in recs:
            if r.source:
                seen.setdefault(r.source[key], []).append(f"{r.family} {r.attempt} {r.where}")
        if len(seen) > 1:
            flags.append(
                f"entries differ in source.{key}: "
                + "; ".join(
                    f"{v!r} in {len(w)} entries ({w[0]}, …)" for v, w in sorted(seen.items())
                )
            )
    return flags


def _tally(pairs):
    out = {}
    for message, where in pairs:
        out.setdefault(message, []).append(where)
    return {m: {"entries": len(w), "first": w[:3]} for m, w in out.items()}


def _c0_report(recs, notes, flags):
    """What C0 found on the engine's entries: the refusals, the engine's own, and what is recorded
    or flagged to the checker."""
    values = {}
    for r in recs:
        for path, v in r.recorded.get("declaration", {}).items():
            seen = values.setdefault(r.family, {}).setdefault(path, [])
            if v not in seen:
                seen.append(v)

    def where(r):
        return f"{r.family} {r.attempt} {r.where}"

    return {
        "entries": len(recs),
        "refused_records": [{"table": r.table, "entry": r.where, "attempt": r.attempt,
                             "dt": r.dt, "faults": r.faults} for r in recs if r.faults],
        "engine_refusals": [{"table": r.table, "entry": r.where, "attempt": r.attempt,
                             "refusal": r.refusal, "record": r.record}
                            for r in recs if _engine_refused(r)],
        "notes": notes,
        "flags_for_the_checker": flags + [f for r in recs for f in r.flags] + [
            f"{where(r)}: refused by the engine at run time; its record and log are the checker's "
            f"to confirm ({r.record})" for r in recs if _engine_refused(r)],
        "extra_keys": _tally((n, where(r)) for r in recs for n in r.notes),
        "definition_shape": _tally((n.partition(".definition")[2], where(r)) for r in recs
                                   for n in r.recorded.get("definition_shape", ())),
        "recorded_declaration_values": values,
        "checkpoints": {where(r): r.recorded["checkpoint"] for r in recs
                        if "checkpoint" in r.recorded},
        "host_patches": {where(r): r.recorded["host_patch"] for r in recs
                         if r.recorded.get("host_patch") is not None},
        "sources": sorted({json.dumps(r.source, sort_keys=True) for r in recs if r.source}),
    }  # fmt: skip


def _get(index, fam, role, run, attempt, dt, *, plant=None, machine=None):
    return index.get((fam, role, run, plant, attempt, float(dt),
                      machine if run == "blank" else None))  # fmt: skip


# ------------------------------------------------------------------ one run


def _usable(rec, what):
    """A record a run needs: present, accepted by C0 and completed; else why not."""
    if rec is None:
        return f"{what}: missing (a missing run)"
    if rec.faults:
        return f"{what}: refused by C0 ({'; '.join(rec.faults[:3])})"
    if rec.status == "refused":
        return f"{what}: refused by the engine at run time ({rec.refusal})"
    return None


def _engine_refused(rec):
    return rec is not None and not rec.faults and rec.status == "refused"


def judge_series(entry, fam, rrun, rungs, ctx_h, steps_h, formed=True):
    """C1 at every rung that is there, and C2 with C3 at h where all three are (`formed`), for one
    series readout."""
    name = entry["engine"].partition("/")[2]
    rs = ref_side(rrun, entry)
    if rs is None:
        return {"readout": entry["name"], "refused": "no reference series",
                "refused_kind": "missing"}  # fmt: skip
    ys = [rec.series[name] for rec in rungs]
    res = {
        "readout": entry["name"],
        "status": entry["status"][fam.profile],
        "reference": entry["reference"],
        "C1": [],
    }
    const = rs.constant
    if const.any():
        for rec, y in zip(rungs, ys, strict=True):
            r = rules.c1(y[const])
            r["dt_s"] = rec.dt
            res["C1"].append(r)
    res["C1_fails"] = any(r["fails"] for r in res["C1"])
    st = ~const
    if st.any() and formed:
        try:
            s_y = ctx_h.scale(entry["scale"], name)
        except (KeyError, ValueError) as exc:
            res["refused"] = f"its scale cannot be formed ({exc})"
            res["refused_kind"] = "missing"
            return res
        p = spec.declared_order(fam.profile, entry["order"])
        res["C2"] = rules.c2(
            ys[0][st], ys[1][st], ys[2][st], rs.value[st], rs.accuracy[st], p, s_y, steps_h
        )
        idx = np.nonzero(st)[0]
        worst = int(idx[int(np.argmax(np.abs(ys[2][st] - rs.value[st])))])
        res["C2"]["worst_time_s"] = fam.times[worst]
    return res


def judge_route2(fate, rrun, rungs, rec_h, fam, steps_h):
    """Route 2 at each sample time, at h alone: τ = 3 g(ts) + e_ref + e_round, no order check; C1 at
    every rung that is there. `rec_h` is None where h is refused or missing."""
    out = []
    k = spec.fate_rate(fam.inputs, fate)
    t1, t2 = fam.window
    row = spec.FATE_ROW[fate]
    for ts in fam.samples:
        e = rrun.route2[fate][ts]
        item = {"readout": f"route2_{fate}", "ts_s": ts}
        if e["class"] == "constant":
            item["C1"] = [dict(rules.c1([rec.route2[(fate, ts)]]), dt_s=rec.dt) for rec in rungs]
            item["C1_fails"] = any(r["fails"] for r in item["C1"])
            out.append(item)
            continue
        if rec_h is None:
            continue
        A = rec_h.series[f"int_Q_tx_release_{fate}"]
        s_y = float(np.max(np.abs(A)))
        e_round = rules.rounding(steps_h, s_y)
        got = rec_h.route2[(fate, ts)]
        g = rules.grid_error(fam.times, A, k, t1, t2, ts)
        mine = rules.known_rate(fam.times, A, k, t1, t2, ts)
        route1 = float(rec_h.series[f"label_{row}_win"][fam.times.index(ts)])
        item["own_known_rate"] = mine
        item["own_known_rate_minus_engine"] = mine - got
        if g is None:
            item["refused"] = "insufficient resolution: the window holds no output to drop"
            item["refused_kind"] = "resolution"
            out.append(item)
            continue
        tau = 3.0 * g + float(e["accuracy"]) + e_round
        gap = abs(got - float(e["value"]))
        split = k * rec_h.dt**2 / (12.0 * float(fam.inputs["tau_s"])) * abs(route1)
        item["C2"] = {
            "g_ts": g,
            "engine_grid_error_recorded": rec_h.route2_grid_error[(fate, ts)],
            "engine_k_per_s_recorded": rec_h.route2_k[(fate, ts)],
            "route2_bound": 3.0 * g,
            "e_ref": float(e["accuracy"]),
            "e_round": e_round,
            "s_y": s_y,
            "tolerance": tau,
            "gap": gap,
            "passes": bool(gap <= tau),
            "resolved": False,
            "q": None,
            "order_in_window": None,
        }
        item["route1_vs_route2"] = {
            "route1": route1,
            "route2": got,
            "difference": abs(route1 - got),
            "bound": g + split,
            "within": abs(route1 - got) <= g + split,
        }
        out.append(item)
    return out


def judge_survival(fate, rrun, rungs, fam, ctx_h, steps_h, formed=True):
    """Survival: both counts by C2 over the sample times, the ratio by its counts' tolerances, from
    the three rungs; at an idle fate, C1 on both counts and an undefined ratio at every rung that is
    there (amendment 1, item 3). None where nothing of it can be formed."""
    entries = [rrun.survival[fate][ts] for ts in fam.samples[1:]]
    item = {"readout": f"survival_{fate}"}
    engine = [[rec.survival[(fate, ts)] for ts in fam.samples[1:]] for rec in rungs]
    if all(e["ratio"] is None for e in entries):  # an idle fate: every entry constant
        item["C1"] = []
        for rec, rows in zip(rungs, engine, strict=True):
            r = rules.c1([x for row in rows for x in row[:2]])
            ratio_ok = all(row[2] is None for row in rows)
            item["C1"].append(
                {
                    **r,
                    "dt_s": rec.dt,
                    "ratio_undefined": ratio_ok,
                    "passes": r["passes"] and ratio_ok,
                    "fails": r["fails"] or not ratio_ok,
                }
            )
        item["C1_fails"] = any(x["fails"] for x in item["C1"])
        return item
    if not formed:
        return None
    ys = [np.array([x for r in rows for x in r[:2]]) for rows in engine]
    yref = np.array([x for e in entries for x in (e["alive_t2"], e["alive_ts"])])
    acc = np.array([x for e in entries for x in e["accuracy"][:2]])
    p = spec.declared_order(fam.profile, "label")
    s_y = ctx_h.scale(f"label:{spec.FATE_ROW[fate]}")
    c = rules.c2(ys[0], ys[1], ys[2], yref, acc, p, s_y, steps_h)
    item["C2"] = c
    ratios = []
    ok = c["passes"]
    for e, r in zip(entries, engine[-1], strict=True):
        tau = e["ratio"] * (c["tolerance"] / e["alive_t2"] + c["tolerance"] / e["alive_ts"])
        got = r[2]
        good = got is not None and abs(got - e["ratio"]) <= tau
        ratios.append(
            {
                "ts_s": e["ts_s"],
                "engine": got,
                "reference": e["ratio"],
                "tolerance": tau,
                "passes": bool(good),
            }
        )
        ok = ok and good
    item["ratio"] = ratios
    item["passes"] = bool(ok)
    return item


def compare_records(a, b, *, names, route2=True, survival=False, checks="equal"):
    """The engine-only equalities of C1, bit for bit, over the named things alone (amendment 6, §3).
    `checks` is "equal", "subset" (a twin's) or None (AF's two blanks)."""
    fails = []
    for n in names:
        if n not in a.series or n not in b.series:
            fails.append(f"series/{n}: missing on one side")
            continue
        r = rules.bit_equal(a.series[n], b.series[n])
        if r["fails"]:
            fails.append(f"series/{n}: {r['entries_off']} entries differ")
    if route2:
        if set(a.route2) != set(b.route2):
            fails.append("route2: the entries differ")
        else:
            for k in a.route2:
                if rules.bit_equal([a.route2[k]], [b.route2[k]])["fails"]:
                    fails.append(f"route2/{k}: differs")
    if survival:
        if set(a.survival) != set(b.survival):
            fails.append("survival: the entries differ")
        else:
            for k in a.survival:
                x, y = a.survival[k], b.survival[k]
                if (
                    rules.bit_equal(x[:2], y[:2])["fails"]
                    or (x[2] is None) != (y[2] is None)
                    or (x[2] is not None and rules.bit_equal([x[2]], [y[2]])["fails"])
                ):
                    fails.append(f"survival/{k}: differs")
    if checks == "equal" and not _deep_bit_equal(a.checks, b.checks):
        fails.append("checks: the engine's checks differ")
    elif checks == "subset" and not _deep_bit_subset(b.checks, a.checks):
        fails.append("checks: a twin's check is missing from, or differs in, the labelled run's")
    return {"passes": not fails, "fails": bool(fails), "differences": fails}


def recorded_differences(a, b, named, *, keep=lambda n: True, subset=False, checks=False):
    """What differs outside an equality's named things (amendment 6, §3): engine_run's other
    exports, `grid_error` and `k_per_s`, the engine's own ledgers (a twin's as a subset), and for
    AF's two blanks the checks. Recorded and flagged; it fails nothing."""
    out = [f"readouts.{n}" for n in sorted(set(a.series) | set(b.series)) if n not in named
           and keep(n) and (n not in a.series or n not in b.series
                            or rules.bit_equal(a.series[n], b.series[n])["fails"])]  # fmt: skip
    for what, x, y in (("grid_error", a.route2_grid_error, b.route2_grid_error),
                       ("k_per_s", a.route2_k, b.route2_k)):  # fmt: skip
        out += [f"route2 ({k[0]}, {k[1]!r} s).{what}" for k in sorted(set(x) | set(y)) if not (
                k in x and k in y and rules.bit_equal([x[k]], [y[k]])["passes"])]  # fmt: skip
    same = _deep_bit_subset if subset else _deep_bit_equal
    if not same(b.own_ledgers, a.own_ledgers):
        out.append("own_ledgers_at_end")
    if checks and not _deep_bit_equal(a.checks, b.checks):
        out.append("checks")
    return out


def _deep_bit_subset(sub, full):
    """Every key the twin's checks hold is present in the labelled run's and bit-equal there,
    recursively (a labelled run may carry label-only checks)."""
    if isinstance(sub, dict) and isinstance(full, dict):
        return all(k in full and _deep_bit_subset(v, full[k]) for k, v in sub.items())
    return _deep_bit_equal(sub, full)


def _deep_bit_equal(x, y):
    """Two JSON values equal, floats bit for bit (the sign of zero included)."""
    if isinstance(x, dict) and isinstance(y, dict):
        return set(x) == set(y) and all(_deep_bit_equal(x[k], y[k]) for k in x)
    if isinstance(x, list) and isinstance(y, list):
        return len(x) == len(y) and all(_deep_bit_equal(a, b) for a, b in zip(x, y, strict=True))
    if isinstance(x, float) or isinstance(y, float):
        if not (isinstance(x, (int, float)) and isinstance(y, (int, float))):
            return False
        return not rules.bit_equal([float(x)], [float(y)])["fails"]
    return x == y and type(x) is type(y)


def judge_run(fam, unit, index, mapping, attempt):
    """One run at one attempt: every entry that can be formed from the rungs that C0 accepts (C1,
    C2, C3, C4 and the reported figures). Its own refused or missing rungs are named in `refused`,
    its support runs' (the blank, the twin, the restart) in `support_refused` (amendment 6, §1)."""
    run, machine = unit
    blank = run == "blank"
    rungs_dt = spec.PRIMARY_RUNGS if attempt == "primary" else spec.RETRY_RUNGS
    h = rungs_dt[-1]
    out = {
        "run": run,
        "machine": machine if blank else None,
        "attempt": attempt,
        "rungs_s": list(rungs_dt),
        "refused": [],
        "support_refused": [],
        "not_formed": [],
        "equalities": {},
        "readouts": [],
        "identities": {},
        "recorded_differences": {},
    }

    def need(rec, what, listed):
        why = _usable(rec, what)
        if why:
            out[listed].append(why)
            return None
        return rec

    role = "blank" if blank else "honest"
    have, blanks, twins = {}, {}, {}
    for dt in rungs_dt:
        rec = _get(index, fam.name, role, run, attempt, dt, machine=machine)
        have[dt] = need(rec, f"{unit_name(unit)} at {dt!r} s", "refused")
        if not blank and spec.has_blank(fam.profile):
            m = matched_blank_machine(fam, run)
            b = _blank_at(index, fam, run, attempt, dt)
            blanks[dt] = need(b, f"its blank ({m}) at {dt!r} s", "support_refused")
        if not blank and run in fam.twin_runs():
            t = _get(index, fam.name, "twin", run, attempt, dt)
            twins[dt] = need(t, f"its twin at {dt!r} s", "support_refused")
    rungs = [have[dt] for dt in rungs_dt if have[dt] is not None]
    out["formed"] = len(rungs) == len(rungs_dt)
    _judge_readouts(out, fam, rungs, have[h], blanks, mapping, fam.steps(h), blank)
    # C4 at every rung that is there, each with its own S (amendment 4, item 2); the machine option
    # is the run's registered one (a blank's from its name)
    option = machine if blank else fam.inputs["runs"][run]["machine"]
    for rec in rungs:
        try:
            out["identities"][repr(rec.dt)] = rules.identities(
                rec.series, fam.inputs, fam.profile, option, fam.steps(rec.dt), blank=blank
            )
        except (KeyError, ValueError) as exc:
            out["refused"].append(f"C4 at {rec.dt!r} s cannot be formed: {exc}")
    _judge_equalities(out, fam, run, machine, have, blanks, twins, index, attempt, mapping)
    for item in out["readouts"]:
        if item.get("refused_kind") == "missing":
            out["refused"].append(f"{item['readout']}: {item['refused']}")
    out["verdict"] = run_verdict(out)
    return out


def _entries(mapping, fam, blank):
    return records.mapping_entries(mapping, fam.profile, blank=True if blank else None)


def _is_excess(name):
    return name.startswith("excess_over_blank_")


def _judge_readouts(out, fam, rungs, rec_h, blanks, mapping, steps_h, blank):
    """C1, C2 and C3 of every readout, as far as the rungs that are there form them: a stepped entry
    needs its three rungs, route 2 h alone, the excess its blank at each rung it reads."""
    rrun = fam.ref.runs[out["run"]]
    formed = out["formed"]
    ctx_h = None
    if formed:
        blank_h = blanks.get(rec_h.dt)
        ctx_h = rules.ScaleContext(
            fam.profile,
            fam.inputs,
            rec_h.series,
            blank=blank,
            blank_values=None if blank_h is None else blank_h.series,
        )
    for e in _entries(mapping, fam, blank):
        kind, _, name = e["engine"].partition("/")
        got = []
        if kind == "series":
            with_it = [r for r in rungs if not _is_excess(name) or blanks.get(r.dt) is not None]
            whole = formed and len(with_it) == len(rungs)
            got = [judge_series(e, fam, rrun, with_it, ctx_h, steps_h, formed=whole)]
        elif kind == "route2":
            got = judge_route2(name, rrun, rungs, rec_h, fam, steps_h)
            whole = rec_h is not None
        elif kind == "survival":
            item = judge_survival(name, rrun, rungs, fam, ctx_h, steps_h, formed)
            got, whole = [] if item is None else [item], formed
        if not whole:
            out["not_formed"].append(e["name"])
        out["readouts"] += got
    # family D's energy identity: stepped, e_ref = 0, p = 2 (amendment 3, item 1)
    if fam.profile == "D" and not formed:
        out["not_formed"].append("energy_identity_D")
    elif fam.profile == "D":
        item = {"readout": "energy_identity_D", "status": "judged", "C1": [], "C1_fails": False}
        try:
            r = [rules.d_identity_residual(rec.series) for rec in rungs]
            s_d = ctx_h.d_identity_scale()
            item["C2"] = rules.c2(r[0], r[1], r[2], np.zeros_like(r[2]), np.zeros(0), 2, s_d,
                                  steps_h)  # fmt: skip
        except (KeyError, ValueError) as exc:
            item.update(refused=f"it cannot be formed ({exc})", refused_kind="missing")
        out["readouts"].append(item)


def _judge_equalities(out, fam, run, machine, have, blanks, twins, index, attempt, mapping):
    """The engine-only equalities of C1 (CRITERIA.md §2), each where both its runs are there, over
    the things amendment 6, §3 names: READOUTS.md §1's series with `released_present_gross` (a
    twin's without the labels and it), and for a twin and the restart route 2's values, the excess
    and the checks, and for the restart `survival`. A difference in anything else is recorded."""
    series = {
        e["engine"].partition("/")[2]
        for e in _entries(mapping, fam, run == "blank")
        if e["engine"].startswith("series/")
    }

    def named(dt):  # the excess is formed only where its blank is there (§1)
        return sorted(n for n in series if not _is_excess(n) or blanks.get(dt) is not None)

    for dt, tw in twins.items():
        if tw is None or have[dt] is None:
            continue
        out["equalities"][f"twin@{dt!r}"] = compare_records(
            have[dt], tw, names=list(filter(records.physical, named(dt))), checks="subset"
        )
        out["recorded_differences"][f"twin@{dt!r}"] = recorded_differences(
            have[dt], tw, series, keep=records.physical, subset=True
        )
    restart = fam.restart()
    if attempt == "primary" and restart and restart[0] == run:
        rs = _get(index, fam.name, "restart", run, "primary", spec.H_STEP_S)
        why = _usable(rs, "the restart")
        rec = have[spec.H_STEP_S]
        if why:
            if not (fam.restart_optional() and rs is None):
                out["support_refused"].append(why)
        elif rec is not None:
            out["equalities"]["restart"] = compare_records(
                rec, rs, names=named(spec.H_STEP_S), survival=True
            )
            out["recorded_differences"]["restart"] = recorded_differences(rec, rs, series)
    if run == "blank" and machine == "held":
        for dt, rec in have.items():
            other = _get(index, fam.name, "blank", "blank", attempt, dt, machine="returned")
            if rec is None or _usable(other, "the returned blank"):
                continue  # the returned blank's own refusal is its own run's
            out["equalities"][f"two_blanks@{dt!r}"] = compare_records(
                other, rec, names=sorted(series), route2=False, checks=None
            )
            out["recorded_differences"][f"two_blanks@{dt!r}"] = recorded_differences(
                other, rec, series, checks=True
            )


def run_verdict(out):
    """CRITERIA.md §4 and amendment 6, §1 for one run, with a summary per criterion and the reported
    figures: a failing entry fails it whatever is refused; with none, a refused or missing rung of
    its own refuses it. Its support runs' refusals are counted in its family's verdict alone."""
    c1, c2, c2_outside, c3, c4, resolution = [], [], [], [], [], []
    judged_n, reported = 0, []
    for item in out["readouts"]:
        judged = item.get("status", "judged") == "judged"
        tag = item["readout"] + (f"@{item['ts_s']!r}" if item.get("ts_s") is not None else "")
        if item.get("refused"):
            if judged and item.get("refused_kind") == "resolution":
                resolution.append(tag)
            continue
        if item.get("C1_fails"):
            c1.append(tag)
        c = item.get("C2")
        if c is None:
            continue
        reported.append(
            {
                "readout": tag,
                "status": item.get("status", "judged"),
                "gap": c["gap"],
                "tolerance": c["tolerance"],
                "q": c.get("q"),
                "effective_factor": c.get("effective_factor"),
                "error_2h": c.get("error_2h"),
                "error_h": c.get("error_h"),
                "error_ratio_2h_over_h": c.get("error_ratio_2h_over_h"),
                "saturated": c.get("saturated"),
                "route1_vs_route2": item.get("route1_vs_route2"),
            }
        )
        if not judged:
            continue
        judged_n += 1
        ok = item.get("passes", c["passes"])
        if c["order_in_window"] is False:
            c3.append(f"{tag}: q = {c['q']!r} outside {c['window']!r}")
            if not ok:
                c2_outside.append(tag)
        elif not ok:
            c2.append(tag)
    c1 += [k for k, res in out["equalities"].items() if res["fails"]]
    c4 = [
        f"{r['identity']} at {dt} s"
        for dt, ids in out["identities"].items()
        for r in ids
        if r["fails"]
    ]
    out["criteria"] = {
        "C1": {"passes": not c1, "failures": c1},
        "C2": {
            "passes": not (c2 or c2_outside),
            "judged_readouts": judged_n,
            "failures": c2,
            "misses_with_order_outside_window": c2_outside,
        },
        "C3": {"inconclusive": c3},
        "C4": {"passes": not c4, "failures": c4},
        "route2_refused_for_resolution": resolution,
    }
    out["reported"] = reported
    out["why"] = (
        [f"C1: {x}" for x in c1]
        + [f"C2: {x}" for x in c2]
        + [f"C4: {x}" for x in c4]
        + [f"refused: {x}" for x in out.get("refused", ())]
        + [f"C3: {x}" for x in c3]
        + [f"route2 refused: {x}" for x in resolution]
        + [f"support refused: {x}" for x in out.get("support_refused", ())]
    )
    if c1 or c2 or c4:
        return "fail"
    if out.get("refused"):
        return "refused"
    if c3 or resolution:
        return "inconclusive"
    return "pass"


def two_blanks(fam):
    """AF runs a blank per machine option; an invented family with no role may (optional)."""
    if fam.role is not None:
        return fam.role == "AF"
    return fam.held_blank_present


def matched_blank_machine(fam, run):
    if two_blanks(fam):
        return fam.inputs["runs"][run]["machine"]
    return "returned"


def run_units(fam):
    units = [(r, None) for r in spec.honest_runs(fam.inputs)]
    if spec.has_blank(fam.profile):
        units.append(("blank", "returned"))
        if two_blanks(fam):
            units.append(("blank", "held"))
    return units


def unit_name(unit):
    run, machine = unit
    return f"blank {machine}" if run == "blank" and machine == "held" else run


def judge_family(fam, index, mapping):
    """Every run of one family, with the retry for its inconclusive runs."""
    runs = {}
    for unit in run_units(fam):
        primary = judge_run(fam, unit, index, mapping, "primary")
        res = {"primary": primary, "verdict": primary["verdict"],
               "support_refused": list(primary["support_refused"])}  # fmt: skip
        has_retry = any(
            _get(
                index,
                fam.name,
                "blank" if unit[0] == "blank" else "honest",
                unit[0],
                "retry",
                dt,
                machine=unit[1],
            )
            for dt in spec.RETRY_RUNGS
        )
        if primary["verdict"] == "inconclusive":
            if has_retry:
                retry = judge_run(fam, unit, index, mapping, "retry")
                res["retry"] = retry
                res["verdict"] = retry["verdict"]
                res["support_refused"] += retry["support_refused"]
            else:
                res["retry_pending"] = True
        elif has_retry:
            res["retry_ignored"] = "the run was not inconclusive at its primary attempt"
        runs[unit_name(unit)] = res
    return runs


def aggregate(verdicts):
    """An arm or family: fails if any run fails; inconclusive if any is inconclusive or
    refused; otherwise it passes."""
    vs = list(verdicts)
    if not vs:
        return "inconclusive"
    if "fail" in vs:
        return "fail"
    if "inconclusive" in vs or "refused" in vs:
        return "inconclusive"
    return "pass"


def family_verdict(runs):
    """CRITERIA.md §4's rule over a family's runs, where a refused or missing support run counts as
    one (amendment 6, §1): at best inconclusive. One refused at the primary attempt counts even
    where its run then takes the retry."""
    v = aggregate(r["verdict"] for r in runs.values())
    return "inconclusive" if v == "pass" and any(r["support_refused"] for r in runs.values()) else v


# ------------------------------------------------------------------ the plants


def _honest_tolerance(primary, readout, ts=None):
    for item in primary.get("readouts", []):
        if item.get("readout") == readout and (ts is None or item.get("ts_s") == ts):
            c = item.get("C2")
            return None if c is None else c["tolerance"]
    return None


def _distance(ref, plant, run, quantity):
    """The reference's largest predicted |planted − honest| for that run and quantity (SPEC.md §6;
    amendment 4, item 7), over its sample times for route 2."""
    best = None
    for e in ref.plants:
        if e["plant"] == plant and e["run"] == run and e["quantity"] == quantity:
            d = abs(e["planted"] - e["honest"])
            best = d if best is None else max(best, d)
    return best


def _score_readout(fam, plant, run, readout, ys_h, rs, honest_tau, *, ts=None):
    """One "By" readout of a planted run at h, with the honest tolerance at h. `C2_fails` is None
    where there is a stepped entry and no honest tolerance to score it with."""
    item = {"plant": plant, "run": run, "readout": readout, "ts_s": ts}
    const = rs.constant
    c1 = rules.c1(ys_h[const]) if const.any() else None
    item["C1_fails"] = bool(c1 and c1["fails"])
    st = ~const
    if st.any():
        gap = float(np.max(np.abs(ys_h[st] - rs.value[st])))
        item.update(
            {
                "gap": gap,
                "honest_tolerance": honest_tau,
                "C2_fails": None if honest_tau is None else gap > honest_tau,
            }
        )
    else:
        item["C2_fails"] = False
    return item


def _sized(item, fam, plant, quantity):
    """A C2 catch counts only where the honest tolerance does not exceed the predicted distance."""
    d = _distance(fam.ref, plant, item["run"], quantity)
    item["predicted_distance"] = d
    if item["C1_fails"]:
        item["caught"] = True
    elif item["C2_fails"] is None or (item["C2_fails"] and item.get("honest_tolerance") is None):
        item["caught"] = None  # no honest tolerance to score it with: unscorable, not a catch
    elif item["C2_fails"]:
        item["sized"] = d is None or item["honest_tolerance"] <= d
        item["caught"] = bool(item["sized"])
    else:
        item["caught"] = False
    return item


def plant_units(fam, plant):
    """The units each plant must be caught in, for this family (CRITERIA.md §6)."""
    if fam.role is None:  # an invented family: the plants its reference sizes, where it sizes them
        runs = sorted({e["run"] for e in fam.ref.plants if e["plant"] == plant})
        if plant in ("P1", "P1′", "P1″") and runs:
            runs = spec.honest_runs(fam.inputs)
        return [(fam.name, r) for r in runs]
    if plant in spec.PLANT_RUNS:
        return [(fam.name, r) for f, r in spec.PLANT_RUNS[plant] if f == fam.role and r != "blank"]
    if plant in spec.JUDGE_PLANT_FAMILIES and fam.role in spec.JUDGE_PLANT_FAMILIES[plant]:
        if plant == "P6":
            return [(fam.name, spec.P6_RUN)]
        return [(fam.name, r) for r in spec.honest_runs(fam.inputs)]
    return []


def judge_plant_unit(fam, plant, run, index, mapping, family_runs):
    """The catches of one plant in one run: a list of readout items, or why it is unscorable. A
    refused honest run makes it so, which means a rung of its own (amendment 6, §1); P1″ reads the
    excess, so its blank's rungs too."""
    honest = family_runs.get(run, {}).get("primary")
    if honest is None or not honest["formed"]:
        return {"refused": f"a rung of the honest run {run!r} is refused or missing"}
    if plant == "P1″":
        for dt in spec.PRIMARY_RUNGS:
            why = _usable(_blank_at(index, fam, run, "primary", dt), f"its blank at {dt!r} s")
            if why:
                return {"refused": f"P1″ reads the excess over the blank; {why}"}
    if spec.PLANT_KIND[plant] in ("world", "host_record"):
        return _judge_record_plant(fam, plant, run, index, mapping, honest)
    try:
        return {"items": _judge_own_plant(fam, plant, run, index, mapping, honest)}
    except (KeyError, ValueError) as exc:
        return {"refused": f"{plant} cannot be formed from the honest records ({exc})"}


def _judge_record_plant(fam, plant, run, index, mapping, honest):
    """A plant the builder runs: its entry at h, against the reference with the honest tolerance. A
    run the engine refuses by its own books is caught (CRITERIA.md §4; P9's too, amendment 6, §4).
    P8's catch does not depend on its blank: where `P8 blank` is refused or missing, or the honest
    excess has no tolerance, it is scored on its other readouts (§1)."""
    rrun = fam.ref.runs[run]
    prec = _get(index, fam.name, "plant", run, "primary", spec.H_STEP_S, plant=plant)
    if _engine_refused(prec):
        return {"items": [], "engine_refused": True}
    why = _usable(prec, f"{plant}'s record")
    if why:
        return {"refused": why}
    out = {"items": [], "not_formed": []}
    for readout in spec.plant_readouts(plant):
        entry = next(e for e in mapping["readouts"] if e["name"] == readout)
        why = _usable(_blank_of(prec, index, fam), "P8's blank") if _is_excess(readout) else None
        if why:
            out["not_formed"].append(f"{readout}: {why}")
            continue
        y = prec.series[entry["engine"].partition("/")[2]]
        tau = _honest_tolerance(honest, readout)
        scored = _score_readout(fam, plant, run, readout, y, ref_side(rrun, entry), tau)
        item = _sized(scored, fam, plant, readout)
        if _is_excess(readout) and item["caught"] is None:
            out["not_formed"].append(f"{readout}: the honest run's has no tolerance")
            continue
        out["items"].append(item)
    if plant == "P8":
        nc = []
        for readout in spec.P8_NEGATIVE_CONTROL:
            entry = next(e for e in mapping["readouts"] if e["name"] == readout)
            it = _score_readout(
                fam,
                plant,
                run,
                readout,
                prec.series[readout],
                ref_side(rrun, entry),
                _honest_tolerance(honest, readout),
            )
            it["passes"] = not it["C1_fails"] and it["C2_fails"] is False
            nc.append(it)
        out["negative_control"] = nc
        out["negative_control_passes"] = all(it["passes"] for it in nc)
    return out


def _judge_own_plant(fam, plant, run, index, mapping, honest):
    """A plant the judge forms from the honest records (amendment 4, item 5): P1, P1″, P1′, P6."""
    rrun = fam.ref.runs[run]
    rec_h = _get(index, fam.name, "honest", run, "primary", spec.H_STEP_S)
    idle = spec.idle_fate(fam.inputs["runs"][run]["p"])
    items = []
    if plant in ("P1", "P1″"):
        pm = planted_mapping(mapping, plant)
        rungs = [_get(index, fam.name, "honest", run, "primary", dt) for dt in spec.PRIMARY_RUNGS]
        blank = None
        if plant == "P1″":  # the excess's scale; its blank's rungs are all there
            blank = _blank_at(index, fam, run, "primary", spec.H_STEP_S)
        ctx_h = rules.ScaleContext(
            fam.profile,
            fam.inputs,
            rec_h.series,
            blank=False,
            blank_values=None if blank is None else blank.series,
        )
        steps_h = fam.steps(spec.H_STEP_S)
        for readout in spec.plant_readouts(plant):
            fate = "durable" if readout.endswith(("R_win", "_durable")) else "short_lived"
            if plant == "P1" and fate == idle:
                continue  # P1 acts where a fate releases (SPEC.md §6)
            entry = next(e for e in pm["readouts"] if e["name"] == readout)
            res = judge_series(entry, fam, rrun, rungs, ctx_h, steps_h)
            if res.get("refused"):
                raise ValueError(f"{readout}: {res['refused']}")
            quantity = readout if plant == "P1" else f"released_present_gross_{fate}"
            item = {
                "plant": plant,
                "run": run,
                "readout": readout,
                "ts_s": None,
                "paired_with": entry["reference"],
                "idle_fate": fate == idle,
                "C1_fails": bool(res.get("C1_fails")),
                "C2_fails": bool(res.get("C2") and not res["C2"]["passes"]),
            }
            if res.get("C2"):
                item["gap"] = res["C2"]["gap"]
                item["planted_tolerance"] = res["C2"]["tolerance"]
            item["honest_tolerance"] = _honest_tolerance(honest, readout)
            items.append(_sized(item, fam, plant, quantity))
        return items
    if plant == "P1′":
        t1, t2 = fam.window
        for fate in spec.FATES:
            if fate == idle:
                continue
            row = spec.FATE_ROW[fate]
            A = rec_h.series[f"int_Q_tx_release_{fate}"]
            D, n = rec_h.series[f"int_D_{row}"], rec_h.series[f"n_{row}"]
            for ts in fam.samples:
                planted = rules.net_rate_cohort(fam.times, A, D, n, t1, t2, ts)
                e = rrun.route2[fate][ts]
                tau = _honest_tolerance(honest, f"route2_{fate}", ts)
                gap = abs(planted - float(e["value"]))
                item = {
                    "plant": plant,
                    "run": run,
                    "readout": f"route2_{fate}",
                    "ts_s": ts,
                    "planted": planted,
                    "gap": gap,
                    "honest_tolerance": tau,
                    "C1_fails": False,
                    "C2_fails": None if tau is None else gap > tau,
                }
                items.append(_sized(item, fam, plant, f"route2_{fate}"))
        return items
    if plant == "P6":
        L = spec.chain_length(fam.inputs)
        H = rec_h.series["H_tx_release"]
        planted = rec_h.series["G_minus_G0"] - spec.RT_KJ * spec.residue_potential(
            fam.inputs
        ) * L * (H - H[0])
        entry = next(e for e in mapping["readouts"] if e["name"] == "G_minus_G0")
        tau = _honest_tolerance(honest, "G_minus_G0")
        it = _score_readout(fam, plant, run, "G_minus_G0", planted, ref_side(rrun, entry), tau)
        return [_sized(it, fam, plant, "G_minus_G0")]
    raise KeyError(plant)


def judge_plants(fams, index, mapping, family_runs):
    """Every plant over its must-catch units: caught, not caught, or refused (unscorable)."""
    out = {}
    plants = list(spec.CORE_PLANTS) + ["P8", "P9"]
    for plant in plants:
        units, reported = [], []
        for fam in fams.values():
            if not fam.ref.accepted:
                continue
            for fname, run in plant_units(fam, plant):
                res = judge_plant_unit(fam, plant, run, index, mapping, family_runs[fname])
                res.update({"family": fname, "run": run, "role": fam.role})
                if plant == "P1″":
                    res["idle_fate"] = spec.idle_fate(fam.inputs["runs"][run]["p"])
                if res.get("engine_refused"):
                    res["caught"] = True
                elif "refused" in res:
                    res["caught"] = None
                else:
                    vals = [it["caught"] for it in res["items"]]
                    res["caught"] = (
                        True
                        if any(v is True for v in vals)
                        else None
                        if any(v is None for v in vals)
                        else False
                    )
                (reported if _reported_only(fam, plant) else units).append(res)
        must = _must_catch(plant, units)
        status = _plant_status(must)
        out[plant] = {
            "kind": spec.PLANT_KIND[plant],
            "status": status,
            "units": units,
            "must_catch": must,
            "reported_only": reported,
        }
        if plant == "P8":
            ncs = [u.get("negative_control_passes") for u in units if "items" in u]
            out[plant]["negative_control_passes"] = all(ncs) if ncs else None
    return out


def _reported_only(fam, plant):
    return plant == "P1" and fam.role == "AF"


def _must_catch(plant, units):
    """P1, P1′ and P1″ must be caught somewhere in AN (or an invented family); P1″ also at every
    idle fate of AF and AN, each a group of its own, which its run's refused blank makes unscorable
    and no other (amendment 6, §1); the other plants in each of their runs."""
    groups = []
    if plant in ("P1", "P1′", "P1″"):
        by_family = {}
        for u in units:
            if plant == "P1″" and u.get("role") == "AF":
                continue
            by_family.setdefault(u["family"], []).append(u)
        for f, us in by_family.items():
            groups.append({"unit": f"{f} (any run)", "caught": _any_caught(us)})
        if plant == "P1″":
            for u in units:
                if u["idle_fate"] is None:
                    continue
                readout = f"excess_over_blank_{u['idle_fate']}"
                caught = None if "refused" in u else next(
                    it["caught"] for it in u["items"] if it["readout"] == readout)  # fmt: skip
                groups.append(
                    {"unit": f"{u['family']} {u['run']} idle {readout}", "caught": caught}
                )
        return groups
    for u in units:
        groups.append({"unit": f"{u['family']} {u['run']}", "caught": u["caught"]})
    return groups


def _any_caught(units):
    vals = [u["caught"] for u in units]
    if any(v is True for v in vals):
        return True
    if any(v is None for v in vals):
        return None
    return False


def _plant_status(must):
    if not must:
        return "not judged"
    vals = [g["caught"] for g in must]
    if any(v is False for v in vals):
        return "not caught"
    if any(v is None for v in vals):
        return "refused"
    return "caught"


# ------------------------------------------------------------------ the comparison


def comparison(families, plants, fams):
    """CRITERIA.md §4: FR-38's verdict from arms A and B and the core plants; C and D beside it. A
    family whose reference is refused leaves its arm at best inconclusive, and hides no fail."""
    fam_v = {f: family_verdict(runs) for f, runs in families.items()}
    out = {"families": fam_v}
    role = {f: fams[f].role for f in families}
    arms = {}
    for arm in ("A", "B"):
        members = [r for r, a in spec.ARM_OF.items() if a == arm]
        present = [f for f in families if role[f] in members]
        covered = {role[f] for f in present}
        arms[arm] = aggregate(fam_v[f] for f in present)
        if covered != set(members) and arms[arm] == "pass":
            arms[arm] = "inconclusive"
    out["arms"] = arms
    core = [plants[p]["status"] for p in spec.CORE_PLANTS]
    if arms["A"] == "fail" or arms["B"] == "fail" or "not caught" in core:
        fr38 = "fail"
    elif arms["A"] == "pass" and arms["B"] == "pass" and all(s == "caught" for s in core):
        fr38 = "pass"
    else:
        fr38 = "inconclusive"
    out["FR-38"] = fr38
    for r, plant in (("C", "P8"), ("D", "P9")):
        present = [f for f in families if role[f] == r]
        if not present:
            out[r] = "inconclusive"
            continue
        v = aggregate(fam_v[f] for f in present)
        p = plants[plant]["status"]
        nc_ok = plants[plant].get("negative_control_passes") if r == "C" else True
        if v == "fail" or p == "not caught":
            out[r] = "fail"
        elif v == "pass" and p == "caught" and nc_ok:
            out[r] = "pass"
        else:
            out[r] = "inconclusive"
    for f, fam in fams.items():
        if fam.role is None:  # an invented family's own verdict: its runs and the plants it sizes
            ps = [
                plants[p]["status"]
                for p in plants
                if any(u["family"] == f for u in plants[p]["units"])
            ]
            if fam_v.get(f) == "fail" or "not caught" in ps:
                out[f] = "fail"
            elif fam_v.get(f) == "pass" and all(s == "caught" for s in ps):
                out[f] = "pass"
            else:
                out[f] = "inconclusive"
    return out


# ------------------------------------------------------------------ the whole judgement


def provenance():
    """The judge's own revision and dirty paths, and its two data files' sha256, at run time."""
    here = os.path.dirname(os.path.abspath(__file__))

    def git(*args):
        try:
            out = subprocess.run(["git", "-C", here, *args], capture_output=True, text=True)
            return out.stdout if out.returncode == 0 else None
        except OSError:
            return None

    rev = git("rev-parse", "HEAD")
    status = git("status", "--porcelain", "--", ".", "../../../assembly_lineages_v2/agreement.py")

    def digest(path):
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()

    return {"revision": rev.strip() if rev else None,
            "dirty_paths": None if status is None else [x[3:] for x in status.splitlines()],
            "mapping_sha256": digest(MAPPING_PATH), "shapes_sha256": digest(shapes.SHAPES_PATH),
            "python": sys.version.split()[0], "numpy": np.__version__}  # fmt: skip


def judge(ref_dir, export_dir, families=None, mapping=None, roles=None, references=None):
    """C0 on the references (invented first), then every engine record, run, plant and verdict.
    `families` maps family -> profile, by default the invented family and the five registered;
    `roles` gives an invented family the registered family whose structure it follows;
    `references` is `read_references`'s result, for a caller judging several exports."""
    mapping = mapping or load_mapping()
    families = families or {"invented": "A", **spec.FAMILY_PROFILE}
    roles = roles or {}
    refs, order = references or read_references(ref_dir, families, mapping)
    verdict = {
        "provenance": provenance(),
        "kind": VERDICT_KIND,
        "mapping": MAPPING_PATH,
        "c0": {"read_order": order, "references": {}},
    }
    for fam_name in order:
        ref = refs[fam_name]
        verdict["c0"]["references"][fam_name] = {
            "path": ref.path,
            "sha256": ref.sha256,
            "accepted": ref.accepted,
            "faults": ref.faults,
            "notes": ref.notes,
            "sizing": sizing_report(ref) if ref.accepted else [],
            "reference_checks_largest": _largest_checks(ref),
        }
    first = order[0]
    if not refs[first].accepted:
        verdict["refused"] = (
            f"the reader's first read, {first}, is refused: no engine run is judged"
        )
        return verdict
    if export_dir is None:
        return verdict
    table_shapes = shapes.load_shapes()
    tables = records.read_tables(
        export_dir,
        [f for f in order if refs[f].accepted],
        sample=shapes.sample_hashes(table_shapes),
    )
    present = {t["family"] for t in tables["tables"]}
    # an invented family is judged only where the export carries its table; a registered family
    # always is, so that its missing runs are refusals, never gaps
    fams = {
        f: Family(f, families[f], refs[f], role=roles.get(f))
        for f in order
        if refs[f].accepted and (f in spec.REAL_FAMILIES or f in present)
    }
    index, engine = index_records(tables, fams, mapping, table_shapes)
    engine["notes"] = tables["notes"] + engine["notes"]
    engine["flags_for_the_checker"] = tables["flags"] + engine["flags_for_the_checker"]
    verdict["c0"]["engine"] = {
        "tables": [
            {k: t.get(k) for k in ("family", "attempt", "path", "sha256", "faults")}
            for t in tables["tables"]
        ],
        "index": tables["index"],
        "faults": tables["faults"],
        **engine,
    }
    family_runs = {f: judge_family(fam, index, mapping) for f, fam in fams.items()}
    attempts = [
        (f"{f} {a} {r}", v[a])
        for f, runs in family_runs.items()
        for r, v in runs.items()
        for a in ("primary", "retry")
        if a in v
    ]
    differences = [
        f"{at}: {k}: {x} differs (recorded, never judged)"
        for at, one in attempts
        for k, names in one["recorded_differences"].items()
        for x in names
    ]
    plants = judge_plants(fams, index, mapping, family_runs)
    verdict["c0"]["engine"]["flags_for_the_checker"] += differences + [
        f"{u['family']} {u['run']}: P9 is refused by the engine: caught, if its record shows that "
        "the V₀ patch was on and that the refusal is the engine's own, and unscorable if not (§4)"
        for u in plants["P9"]["units"]
        if u.get("engine_refused")
    ]
    verdict["families"] = {
        f: {"runs": runs, "verdict": family_verdict(runs)} for f, runs in family_runs.items()
    }
    for f in order:
        if f not in fams and not refs[f].accepted:
            verdict.setdefault("families", {})[f] = {
                "runs": {},
                "verdict": "refused",
                "why": "its reference is refused by C0",
            }
    verdict["plants"] = plants
    verdict["support_refused"] = [f"{at}: {x}" for at, one in attempts
                                  for x in one["support_refused"]]  # fmt: skip
    verdict["recorded_differences"] = differences
    verdict["retry_pending"] = [
        f"{f} {r}"
        for f, runs in family_runs.items()
        for r, v in runs.items()
        if v.get("retry_pending")
    ]
    verdict["comparison"] = comparison(family_runs, plants, fams)
    return verdict


def _clean(x):
    """JSON-safe: numpy scalars to Python, non-finite floats to their names as strings."""
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        x = float(x)
        return x if math.isfinite(x) else repr(x)
    return x


def write_verdict(verdict, path):
    text = json.dumps(
        _clean(verdict), sort_keys=True, indent=1, ensure_ascii=False, allow_nan=False
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
