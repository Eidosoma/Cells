"""E07-v1: every registered prediction scored against the judged runs (post-processing).

Reads the judged execution's outputs (validation/tissue/e07_v1_run.py: runs/*/seed*/
outcome.json, plan.json and records.npz; e1/verdict-seed1.json) and the registered
predictions (validation/tissue/e07_v1_protocol.json, key "predictions"). It changes no rule
and no prediction. Where a prediction's wording needs a numerical reading, the reading is
written beside its score ("scored_as"); the readings were fixed before any judged outcome
existed. Run classes, group classes and every registered readout come from the driver's
outcome.json; the record-level readings here (all H, collective falls, conversions of
interior newcomers, junction weight after the first turnover, osmotic excess to the run's
end) are recomputed from records.npz the same way the driver reads them.

Usage: python -m validation.tissue.e07_v1_score --output DIR [--protocol PATH] [--development]
"""

import argparse
import functools
import json
import math
import sys
from pathlib import Path

import numpy as np

from validation.tissue import e07_v1_run as run
from validation.tissue import e07_v1_turnover as e7

COLLECTIVE_CELLS = 5  # The protocol's descriptive collective loss: 5 cells in 10 s (post hoc).
NOMINAL_WEIGHT = 1.0  # A fully formed, fully open junction (A = 1, gate = 1).


def load_runs(base, development=False):
    out = {}
    for path in sorted(Path(base).glob("runs/*/seed*/outcome.json")):
        o = json.loads(path.read_text())
        if o["label"] != "registered seed" and not development:
            continue
        out[f"{o['arm']}/seed{o['seed']}"] = dict(outcome=o, folder=path.parent)
    return out


@functools.lru_cache(maxsize=4)
def series(folder):
    from validation.tissue.heredity_pilot import THRESHOLD_V

    folder = Path(folder)
    z = np.load(folder / "records.npz")
    plan = json.loads((folder / "plan.json").read_text())
    return dict(t=z["t"], d=z["vm"] > THRESHOLD_V, regular=z["regular"], osm=z["osm"],
                abundance=z["abundance"], gate=z["gate"], plan=plan)  # fmt: skip


def events(plan):
    return [(int(k) * plan["dt"], int(slot), None if donor is None else int(donor))
            for k, slot, donor, *_ in plan["events"]]  # fmt: skip


def all_h_time(folder):
    """The all-H stop's record: the first of two consecutive 10 s records with no D cell."""
    s = series(str(folder))
    t, d = s["t"][s["regular"]], s["d"][s["regular"]]
    none = ~d.any(axis=1)
    hit = np.flatnonzero(none[:-1] & none[1:])
    return float(t[hit[0]]) if len(hit) else None


def largest_fall(folder, until_s):
    """The largest number of cells that went from D to H between two consecutive 10 s
    records, not counting slots replaced in that interval (to the record at until_s)."""
    s = series(str(folder))
    t, d = s["t"][s["regular"]], s["d"][s["regular"]]
    ev = events(s["plan"])
    best = (0, None)
    for i in range(1, len(t)):
        if t[i] > until_s + 1e-9:
            break
        replaced = {slot for te, slot, _ in ev if t[i - 1] - 1e-9 <= te <= t[i] + 1e-9}
        fell = [c for c in np.flatnonzero(d[i - 1] & ~d[i]) if int(c) not in replaced]
        if len(fell) > best[0]:
            best = (len(fell), float(t[i]))
    return dict(cells=best[0], at_s=best[1])


def templates(folder, outcome):
    """Isolated newcomers (templates) to the judged record, read as the driver reads them:
    interior when the slot and its six neighbours are in the disc; converted when the slot is
    D at any record of its life up to the judged record."""
    s = series(str(folder))
    t_all, d_all = s["t"], s["d"]
    judged = outcome["judged_s"]
    _, _, neighbours = e7.sheet()
    inside = np.zeros(d_all.shape[1], dtype=bool)
    inside[sorted(e7.disc(outcome["size"]))] = True
    ev = events(s["plan"])
    births = {}
    for te, slot, _ in ev:
        births.setdefault(slot, []).append(te)
    rows = []
    for te, slot, donor in ev:
        if donor is not None or te >= judged - 1e-9 or te > t_all[-1] + 1e-9:
            continue
        later = [x for x in births[slot] if x > te]
        death = later[0] if later else math.inf
        window = (t_all > te + 1e-9) & (t_all <= min(death, judged) + 1e-9)
        states = d_all[window, slot]
        rows.append(dict(slot=slot, birth_s=te,
                         interior=bool(inside[slot] and all(inside[x] for x in neighbours[slot])),
                         converted=bool(len(states) and states.any())))  # fmt: skip
    return rows


def weight_after_first_turnover(folder, outcome):
    """E6's prediction window: after the first turnover, to the judged record (within the
    first turnover for runs judged there); time-averaged A and A x gate by junction class."""
    s = series(str(folder))
    reg = s["regular"]
    t = s["t"][reg]
    first = s["plan"]["turnover_complete_s"][0]
    judged = outcome["judged_s"]
    if s["plan"]["judged_at"] == "first turnover":
        mask, window = (t > 0) & (t <= judged + 1e-9), "the first turnover"
    else:
        mask = (t > first + 1e-9) & (t <= judged + 1e-9)
        window = "after the first turnover, to the judged record"
    _, edges, _ = e7.sheet()
    out = run.junction_weight(edges, s["d"][reg], s["abundance"][reg], s["gate"][reg], mask)
    out["window"] = window
    return out, t[mask]


def law_a(folder, outcome, times):
    """The formation law's A (all junctions) from the schedule, over the given records
    (validation/tissue/e07_v1_turnover.abundance_series, called as the driver calls it)."""
    plan = series(str(folder))["plan"]
    ev = [(int(k), int(slot), None if donor is None else int(donor))
          for k, slot, donor, *_ in plan["events"]]  # fmt: skip
    law = e7.abundance_series(ev, outcome["size"], plan["planned_end_s"], plan["formation"],
                              dt=plan["dt"])  # fmt: skip
    index = {round(float(x), 9): i for i, x in enumerate(law["t"])}
    vals = [law["all"][index[round(float(x), 9)]] for x in times if round(float(x), 9) in index]
    return float(np.mean(vals)) if vals else None


def max_excess_to_end(folder):
    s = series(str(folder))
    return float((s["osm"] / sum(run.e7_h_state()) - 1.0).max())


def within(value, lo, hi):
    return value is not None and lo - 1e-12 <= value <= hi + 1e-12


def ratio(w, key):
    return w[key]["weight"] / w[key]["A"] if w[key]["A"] else None


def score(base, protocol, development=False):
    runs = load_runs(base, development)
    pred = protocol["predictions"]
    scores = {}
    expected = set(runs) if development else {
        f"{a['id']}/seed{r}" for a in e7.arm_set() for r in a["seeds"]}  # fmt: skip
    missing = sorted(expected - set(runs))
    scores["coverage"] = dict(expected=len(expected), loaded=len(runs), missing=missing)

    def complete(prefixes):
        """No expected run of these arms is missing (an item is not scored otherwise)."""
        return not any(k.startswith(prefixes) for k in missing)

    def group(name, s):
        return {k: v for k, v in runs.items() if v["outcome"]["group"] == name
                and v["outcome"]["s"] == s and v["outcome"]["refusal"] is None}  # fmt: skip

    def row(k, v):
        o = v["outcome"]
        return dict(run=k, run_class=o["run_class"], delta_J=o["delta_J"],
                    D_loss=o["D_loss_fraction"], recruitment=o["recruitment_fraction"],
                    basis=o["basis"], judged_s=o["judged_s"],
                    all_H_s=all_h_time(v["folder"]))  # fmt: skip

    # E1: the numerics gate.
    name = "verdict-seed101.json" if development else "verdict-seed1.json"
    v = json.loads((Path(base) / "e1" / name).read_text())
    dv = 1e3 * max(x["max_vm_difference_mV_all"] for x in v["segments"].values())
    da = max(x["max_relative_amount_difference"] for x in v["segments"].values())
    scores["E1"] = dict(
        predicted=pred["E1"],
        observed=dict(passed=v["passed"], max_vm_difference_uV=dv, max_relative_amount=da),
        scored_as="the gate passes, every |dVm| at most 10 uV (all records) and every relative "
        "amount difference at most 3e-6",
        held=bool(v["passed"] and dv <= 10.0 and da <= 3e-6),
    )

    # E3: run classes and group classes of (a).
    e3 = dict(groups={})
    for g in ("fast k1", "central k1", "fast k3"):
        for s in (0.3, 0.6, 1.0):
            members = group(g, s)
            if members:
                classes = [m["outcome"]["run_class"] for m in members.values()]
                e3["groups"][f"{g}, s {s}"] = dict(
                    class_=run.group_class(classes), runs=[row(k, m) for k, m in members.items()]
                )

    def joint(members, lo, hi, d_lo=None, d_hi=None):
        n = 0
        for m in members.values():
            o = m["outcome"]
            ok = o["run_class"] == "erosion" and within(o["delta_J"], lo, hi)
            if d_lo is not None:
                ok = ok and within(o["D_loss_fraction"], d_lo, d_hi)
            n += ok
        return n

    m03 = group("fast k1", 0.3)
    zero = sum(m["outcome"]["delta_J_over_records"]["nonzero_records"] == 0 for m in m03.values())
    e3["fast_k1_s0.3"] = dict(
        predicted=pred["E3"]["fast_k1_s0.3"],
        runs_neutral=sum(m["outcome"]["run_class"] == "neutral" for m in m03.values()),
        runs=len(m03), runs_with_dJ_0_at_every_record=zero,
        scored_as="all 4 runs neutral, and dJ = 0 at every 10 s record to the judged record "
        "(|dJ| <= 1e-12) in at least 3",
        held=bool(len(m03) == 4 and all(m["outcome"]["run_class"] == "neutral"
                                        for m in m03.values()) and zero >= 3),
    )  # fmt: skip
    m06 = group("fast k1", 0.6)
    c06 = run.group_class([m["outcome"]["run_class"] for m in m06.values()])
    weights = {k: (m["outcome"].get("junction_weight") or {}).get("all", {}).get("weight")
               for k, m in m06.items() if m["outcome"]["run_class"] == "neutral"}  # fmt: skip
    low = bool(weights) and all(w is not None and w <= 0.5 * NOMINAL_WEIGHT
                                for w in weights.values())  # fmt: skip
    e3["fast_k1_s0.6"] = dict(
        predicted=pred["E3"]["fast_k1_s0.6"],
        runs=len(m06),
        group_class=c06,
        neutral_runs_mean_weight=weights,
        low_effective_coupling=low,
        scored_as="the group class is neutral (at least 6 of 8 runs), and every neutral run's "
        "mean junction weight (E6's readout, all junctions, to the judged record) is at most "
        "half the nominal (A x gate = 1)",
        held=bool(len(m06) == 8 and c06 == "neutral" and low),
    )
    m10 = group("fast k1", 1.0)
    c10 = run.group_class([m["outcome"]["run_class"] for m in m10.values()])
    in_range = joint(m10, -0.35, -0.05, 0.05, 0.25)
    all_h10 = sum(within(all_h_time(m["folder"]), 0.0, m["outcome"]["judged_target_s"])
                  for m in m10.values())  # fmt: skip
    e3["fast_k1_s1.0"] = dict(
        predicted=pred["E3"]["fast_k1_s1.0"], runs=len(m10), group_class=c10,
        runs_erosion_with_dJ_and_D_loss_in_range=in_range,
        runs_with_dJ_in_range=sum(within(m["outcome"]["delta_J"], -0.35, -0.05)
                                  for m in m10.values()),
        runs_with_D_loss_in_range=sum(within(m["outcome"]["D_loss_fraction"], 0.05, 0.25)
                                      for m in m10.values()),
        runs_all_H_by_the_judged_record=all_h10,
        scored_as="at least 6 of the 8 runs are erosion with dJ in [-0.35, -0.05] and D-loss "
        "in [5%, 25%] (so erosion holds), and the sheet all H (the stop rule's record) by the "
        "judged record in at most 2 runs",
        held=bool(len(m10) == 8 and in_range >= 6 and all_h10 <= 2),
    )  # fmt: skip
    cc = {s: [m["outcome"]["run_class"] for m in group("central k1", s).values()]
          for s in (1.0, 0.6)}  # fmt: skip
    e3["central_k1"] = dict(
        predicted=pred["E3"]["central_k1"],
        classes={f"s{s}": c for s, c in cc.items()},
        scored_as="both s 1.0 runs erosion and both s 0.6 runs neutral",
        held=bool(cc[1.0] == ["erosion"] * 2 and cc[0.6] == ["neutral"] * 2),
    )
    k3 = group("fast k3", 1.0)
    dj3 = [m["outcome"]["delta_J"] for m in k3.values()]
    dj1 = [m["outcome"]["delta_J"] for m in m10.values()]
    end_h = [all_h_time(m["folder"]) for m in k3.values()]
    sub = dict(
        erosion_in_all_3=bool(len(k3) == 3 and all(m["outcome"]["run_class"] == "erosion"
                                                   for m in k3.values())),
        mean_dJ_below_fast_k1_s1_0=bool(dj3 and dj1 and np.mean(dj3) < np.mean(dj1)),
        dJ_in_range_in_all_3=bool(len(dj3) == 3 and all(within(x, -0.6, -0.1) for x in dj3)),
        all_H_by_70_min_in_at_least_1=sum(x is not None for x in end_h) >= 1,
    )  # fmt: skip
    e3["fast_k3_s1.0"] = dict(
        predicted=pred["E3"]["fast_k3_s1.0"],
        runs=len(k3),
        delta_J=dj3,
        mean_delta_J=float(np.mean(dj3)) if dj3 else None,
        mean_delta_J_fast_k1_s1_0=float(np.mean(dj1)) if dj1 else None,
        all_H_s=end_h,
        sub_claims=sub,
        scored_as="all 3 runs erosion; their mean dJ (at the first turnover's record) below "
        "the fast k1 s 1.0 runs' mean dJ; every dJ in [-0.6, -0.1]; the sheet all H (the stop "
        "rule's record) by the run's end, 70 min after the cue, in at least 1",
        held=all(sub.values()),
    )
    k36 = group("fast k3", 0.6)
    c36 = run.group_class([m["outcome"]["run_class"] for m in k36.values()])
    in36 = joint(k36, -0.4, -0.05)
    e3["fast_k3_s0.6"] = dict(
        predicted=pred["E3"]["fast_k3_s0.6"],
        runs=len(k36),
        group_class=c36,
        runs_erosion_with_dJ_in_range=in36,
        scored_as="at least 2 of the 3 runs are erosion with dJ in [-0.4, -0.05] (so erosion "
        "holds)",
        held=bool(len(k36) == 3 and in36 >= 2),
    )
    a_runs = {k: v for k, v in runs.items()
              if v["outcome"]["group"] in ("fast k1", "central k1", "fast k3")}  # fmt: skip
    converted = sum(v["outcome"]["H_copies_converted"] for v in a_runs.values())
    e3["recruitment"] = dict(
        predicted=pred["E3"]["recruitment"],
        H_copies=sum(v["outcome"]["H_copies"] for v in a_runs.values()),
        H_copies_converted=converted,
        scored_as="no H copy converted (to the judged record) in any (a) run",
        held=(bool(a_runs) and converted == 0) if complete(("a-",)) else None,
    )
    scores["E3"] = e3

    # E4: the control.
    e4 = {}
    for s in (0.6, 1.0):
        members = group("control", s)
        if not members:
            continue
        k, m = next(iter(members.items()))
        o = m["outcome"]
        series_ = o["J_series"]
        judged = [j for x, j in zip(series_["t_s"], series_["engine"], strict=True)
                  if x <= o["judged_s"] + 1e-9]  # fmt: skip
        entry = dict(
            run=k, criterion_met=o.get("e4_disc_held"), J_min_to_judged=min(judged),
            J_min_to_end=min(series_["engine"]), J_at_judged=o["J_engine"],
            founders_lost=o["founders_lost"], D_copies_lost=o["D_copies_lost"],
            largest_fall=largest_fall(m["folder"], o["judged_s"]),
        )  # fmt: skip
        if s == 0.6:
            entry.update(predicted=pred["E4"]["s0.6"],
                         scored_as="J = 1 at every 10 s record to the judged record (the "
                         "second turnover's completion)", held=min(judged) == 1.0)  # fmt: skip
        else:
            held = bool(o["J_engine"] >= 0.9 and entry["largest_fall"]["cells"] < COLLECTIVE_CELLS)
            entry.update(
                predicted=pred["E4"]["s1.0"],
                scored_as="J >= 0.9 at the judged record (the second turnover's completion), "
                f"and no {COLLECTIVE_CELLS} or more cells going from D to H between two "
                "consecutive 10 s records (slots replaced in that interval not counted) to it",
                held=held,
            )
        e4[f"s{s}"] = entry
    scores["E4"] = e4

    # E5: threshold-finding (reported, no pass or fail; its prediction scored).
    e5 = {}
    for s in (0.6, 1.0):
        per = {}
        for k, m in group("threshold-finding", s).items():
            o = m["outcome"]
            tau = float(o["arm"].split("tau")[1].split("-")[0])
            rows = templates(m["folder"], o)
            n, c = (
                o["interior_templates_with_5plus_D"],
                o["interior_templates_with_5plus_D_converted"],
            )
            per[tau] = dict(
                run=k, interior_with_5plus_D=n, converted=c, fraction=c / n if n else None,
                interior_converted_any_neighbours=sum(r["converted"] and r["interior"]
                                                      for r in rows),
                templates_converted=o["templates_converted"], templates=o["templates"],
                templates_converted_recomputed=sum(r["converted"] for r in rows),
                all_H_s=all_h_time(m["folder"]),
                first_turnover_s=series(str(m["folder"]))["plan"]["turnover_complete_s"][0],
            )  # fmt: skip
        star = max((tau for tau, x in per.items() if x["interior_converted_any_neighbours"]),
                   default=None)  # fmt: skip
        star_5 = max((tau for tau, x in per.items() if x["converted"]), default=None)
        entry = dict(per_tau={str(t_): x for t_, x in sorted(per.items())},
                     tau_star_single_draw=star, tau_star_among_5plus_D=star_5,
                     tau_star_definitions="items.E5: the largest ladder tau with at least one "
                     "converted interior newcomer (tau_star_single_draw, scored); the driver's "
                     "summary.json counts only interior newcomers arriving with five or more D "
                     "neighbours (tau_star_among_5plus_D): a driver-versus-protocol discrepancy, "
                     "reported whether or not the two values differ")  # fmt: skip
        if s == 0.6:
            f = {tau: per[tau]["fraction"] if tau in per else None for tau in e7.LADDER_TAU_S}
            f300 = 0.0 if f[300.0] is None and 300.0 in per else f[300.0]
            sub = dict(
                at_least_40_percent_at_40_s=within(f[40.0], 0.40, 1.0),
                at_least_20_percent_at_120_s=within(f[120.0], 0.20, 1.0),
                at_most_20_percent_at_300_s=within(f300, 0.0, 0.20),
                falls_with_tau=bool(None not in (f[40.0], f[120.0], f300)
                                    and f[40.0] >= f[120.0] >= f300),
                tau_star_at_least_120_s=star is not None and star >= 120.0,
            )  # fmt: skip
            entry.update(
                predicted=pred["E5"]["s0.6"],
                sub_claims=sub,
                scored_as="fractions (interior newcomers arriving with five or more D "
                "neighbours that convert) at least 0.40 at 40 s and 0.20 at 120 s, at most 0.20 "
                "at 300 s (0 when none arrives), non-increasing with tau; tau* (the largest "
                "ladder tau with at least one converted interior newcomer, items.E5) at least "
                "120 s",
                held=all(sub.values()),
            )
        else:
            sub = dict(
                all_H_within_the_first_turnover_at_every_tau=bool(len(per) == 3 and all(
                    x["all_H_s"] is not None and x["all_H_s"] <= x["first_turnover_s"] + 1e-9
                    for x in per.values())),
                no_conversion_at_120_or_300_s=all(per[t_]["templates_converted"] == 0
                                                  for t_ in (120.0, 300.0) if t_ in per),
            )  # fmt: skip
            entry.update(
                predicted=pred["E5"]["s1.0"],
                sub_claims=sub,
                scored_as="at every tau the sheet all H (the stop rule's record) by the first "
                "turnover's completion, and no isolated newcomer converted at 120 or 300 s "
                "(any converted at 40 s is then early, within the first turnover)",
                held=all(sub.values()),
            )
        e5[f"s{s}"] = entry
    scores["E5"] = e5

    # E6: junction weight in the (a) runs.
    law = {"fast k1": 0.20, "central k1": 0.15, "fast k3": 0.6}
    e6 = {}
    for k, m in a_runs.items():
        o = m["outcome"]
        w, times = weight_after_first_turnover(m["folder"], o)
        dd, dh, hh = ratio(w, "D-D"), ratio(w, "D-H"), ratio(w, "H-H")
        a, a_law = w["all"]["A"], law[o["group"]]
        s_ = series(str(m["folder"]))
        truncated = bool(s_["t"][s_["regular"]][-1] < o["judged_target_s"] - 1e-9)
        a_ok = None if truncated else within(a, 0.75 * a_law, 1.25 * a_law)
        ratios_ok = bool((dh is None or within(dh, 0.05, 0.2)) and (dd is None or dd >= 0.8)
                         and (hh is None or hh >= 0.8))  # fmt: skip
        e6[k] = dict(
            window=w["window"], A=a, law_A_quoted=a_law,
            law_A_same_records=law_a(m["folder"], o, times), records=w["all"]["records"],
            truncated=truncated, A_within_25_percent_of_quoted=a_ok,
            weight_over_A={"D-D": dd, "D-H": dh, "H-H": hh}, ratios_held=ratios_ok,
            held=None if a is None else bool(ratios_ok and a_ok is not False),
        )  # fmt: skip
    scored = [x["held"] for x in e6.values() if x["held"] is not None]
    scores["E6"] = dict(
        predicted=pred["E6"],
        runs=e6,
        held_in=sum(scored),
        runs_scored=len(scored),
        runs_not_evaluable=[k for k, x in e6.items() if x["held"] is None],
        scored_as="in every (a) run: A (all junctions, time-averaged over the window) within "
        "25% of the law's value; weight / A at least 0.8 on D-D and H-H junctions and in "
        "[0.05, 0.2] on D-H junctions (a junction class absent from the window is not scored; "
        "a run with no record in the window is not evaluable)",
        held=(bool(scored) and all(scored)) if complete(("a-",)) else None,
    )

    # Validity (item E2).
    every = list(runs.items())
    excess = {k: max_excess_to_end(m["folder"]) for k, m in every}
    failed = [k for k, m in every if not all((m["outcome"].get("checks") or {}).get(c, False)
              for c in ("donor_P_equals_slot_P", "field_solver_as_declared",
                        "layout_equals_sheet70"))]  # fmt: skip
    worst = max(excess.values()) if excess else None
    scores["validity"] = dict(
        item="E2", predicted=pred["validity"],
        refusals=[k for k, m in every if m["outcome"]["refusal"] is not None],
        censored=[k for k, m in every if m["outcome"]["stop"] == "censor"],
        definition_checks_failed=failed,
        max_osmotic_excess_to_end=worst,
        max_osmotic_excess_to_end_run=max(excess, key=excess.get) if excess else None,
        max_osmotic_excess_to_judged=max(m["outcome"]["max_osmotic_excess"] for _, m in every)
        if every else None,
        scored_as="no refusal (a failed device check on any row refuses the run), no censor, "
        "every definition check passed, and the largest osmotic excess against the H start, "
        "any cell and any record to the run's end (at most 70 min after the cue), at most 0.13",
    )  # fmt: skip
    val = scores["validity"]
    val["held"] = bool(every and not val["refusals"] and not val["censored"] and not failed
                       and worst <= 0.13) if complete(("",)) else None  # fmt: skip

    # B1, reported beside the null's P(B1).
    b1 = {k: m["outcome"]["b1"] for k, m in every if "b1" in m["outcome"]}
    fast_b = {k: x for k, x in b1.items() if k.startswith(("a-donor-fast-k1", "b-"))}
    c06 = [x for k, x in b1.items() if k.startswith("c-disconly-fast-k1-d37-s0.6/")]
    scores["B1"] = dict(
        predicted=pred["B1"],
        runs=b1,
        scored_as="B1 false in every fast k1 and (b) run, and true in the (c) run at s 0.6",
        held=(bool(fast_b) and not any(fast_b.values()) and c06 == [True])
        if complete(("a-donor-fast-k1", "b-", "c-"))
        else None,
    )

    # Cross-checks against the driver's summary and outcomes.
    checks = dict(
        templates_converted_recomputed_equal=all(
            x["templates_converted"] == x["templates_converted_recomputed"]
            for item in e5.values() for x in item["per_tau"].values()),
    )  # fmt: skip
    summary_path = Path(base) / "summary.json"
    if summary_path.exists():
        sm = json.loads(summary_path.read_text())
        mine = {k: v["class_"] for k, v in e3["groups"].items()}
        checks.update(
            group_classes_equal_summary=mine
            == {k: v["class_"] for k, v in sm["group_classes"].items()},
            tau_star_among_5plus_D_equals_summary={
                str(s): e5[f"s{s}"]["tau_star_among_5plus_D"] for s in (0.6, 1.0)
                if e5.get(f"s{s}", {}).get("per_tau")} == sm["tau_star_single_draw"],
            summary_runs=len(sm["runs"]), summary_development_runs=sm["development_runs"],
        )  # fmt: skip
    scores["cross_checks"] = checks
    return scores


def held(value):
    if "held" in value:
        return value["held"]
    return {k: held(v) for k, v in value.items() if isinstance(v, dict) and k != "groups"}


READINGS = [
    "held means held under the reading in its item's scored_as; these readings are the "
    "scorer's, not the registration's, and were fixed before any judged outcome existed",
    "E1: 'about 10 uV' read as at most 10 uV over all records; amounts at most 3e-6",
    "E3 fast k1 s 1.0 and fast k3 s 0.6: the ranges read jointly per run (erosion with dJ, "
    "and D-loss, in range), counted against the group's two-thirds number",
    "E3 fast k1 s 0.6: 'low effective coupling' read as every neutral run's mean weight "
    "(E6's readout to the judged record, all junctions) at most half the nominal",
    "E3 fast k3 s 1.0: 'stronger than at k1' read as a lower mean dJ than fast k1 s 1.0",
    "all H: the stop rule's record (the first of two consecutive 10 s records with no D)",
    "E4 s 1.0: 'after the second turnover' read as at the judged record; collective loss as "
    "5 or more cells from D to H between consecutive 10 s records, replaced slots excluded",
    "E5 s 0.6: a 300 s run with no candidate newcomer counts as 0; 'falls with tau' as "
    "non-increasing fractions; tau* as items.E5 defines it",
    "E6: A within 25% of the quoted value (not scored for a run cut short before its judged "
    "record); weight / A at least 0.8 on D-D and H-H, in [0.05, 0.2] on D-H; an absent "
    "junction class not scored",
    "validity: 'about 12.5%' read as at most 0.13, any cell and record to the run's end",
    "an item whose runs are not all present is not scored (held null)",
]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--protocol", default=str(Path(__file__).with_name("e07_v1_protocol.json")))
    parser.add_argument(
        "--development", action="store_true", help="score development seeds (tests)"
    )
    args = parser.parse_args(argv)
    protocol = json.loads(Path(args.protocol).read_text())
    value = dict(kind="cells.e07_v1_scores@1", protocol=args.protocol,
                 note="post-processing of the judged outputs; no rule or prediction changed",
                 development=args.development, readings=READINGS,
                 scores=score(args.output, protocol, args.development))  # fmt: skip
    name = "scores-development.json" if args.development else "scores.json"
    run.write_json(Path(args.output) / name, value)
    print(json.dumps({k: held(v) for k, v in value["scores"].items()
                      if k not in ("coverage", "cross_checks")}, indent=1))  # fmt: skip
    print(json.dumps(dict(coverage=value["scores"]["coverage"],
                          cross_checks=value["scores"]["cross_checks"])))  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
