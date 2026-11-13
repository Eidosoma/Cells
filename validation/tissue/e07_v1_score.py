"""E07-v1: every registered prediction scored against the judged runs (post-processing).

Reads the judged execution's outputs (validation/tissue/e07_v1_run.py: runs/*/seed*/
outcome.json, records.npz and plan.json; e1/verdict-seed1.json; summary.json) and the
registered protocol's predictions (validation/tissue/e07_v1_protocol.json). It changes no
rule and no prediction. Where a registered prediction's wording needs a numerical reading,
the reading used is written beside its score ("scored_as"), so it can be checked.

Usage: python -m validation.tissue.e07_v1_score --output DIR [--protocol PATH]
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from validation.tissue import e07_v1_run as run
from validation.tissue import e07_v1_turnover as e7

THRESHOLD_V = -0.039445199111173515  # heredity_pilot.THRESHOLD_V: the U voltage.
COLLECTIVE_CELLS = 5  # The pre-screen's descriptive collective loss: 5 cells in one 10 s step.


def load_runs(base, development=False):
    out = {}
    for path in sorted(Path(base).glob("runs/*/seed*/outcome.json")):
        o = json.loads(path.read_text())
        if o["label"] != "registered seed" and not development:
            continue
        out[(o["arm"], o["seed"])] = dict(outcome=o, folder=path.parent)
    return out


def group_runs(runs, group, s):
    return [v for (arm, _), v in runs.items() if v["outcome"]["group"] == group
            and v["outcome"]["s"] == s]  # fmt: skip


def records(folder):
    z = np.load(folder / "records.npz")
    plan = json.loads((folder / "plan.json").read_text())
    return z, plan


def all_h_time(folder):
    z, _ = records(folder)
    d = z["vm"] > THRESHOLD_V
    reg = z["regular"]
    t = z["t"][reg]
    none = np.flatnonzero(~d[reg].any(axis=1))
    return None if not len(none) else float(t[none[0]])


def largest_fall(folder):
    """The largest fall of the sheet's D count between two 10 s records beyond the D carriers
    that events removed in that interval (the pre-screen's descriptive collective loss)."""
    z, plan = records(folder)
    d = z["vm"] > THRESHOLD_V
    t_all = z["t"]
    reg = z["regular"]
    t, total = t_all[reg], d[reg].sum(axis=1)
    index = {round(float(x), 9): i for i, x in enumerate(t_all)}
    events = [(k * plan["dt"], slot) for k, slot, *_ in plan["events"]]
    best = (0, None)
    for i in range(1, len(t)):
        removed = sum(1 for te, slot in events if t[i - 1] < te <= t[i] + 1e-9
                      and round(te, 9) in index and d[index[round(te, 9)], slot])  # fmt: skip
        fall = int(total[i - 1] - total[i]) - removed
        if fall > best[0]:
            best = (fall, float(t[i]))
    return best


def weight_after_first_turnover(folder, outcome):
    """E6 after the first turnover (within it for runs judged at the first turnover):
    time-averaged A and A x gate by junction class."""
    z, plan = records(folder)
    reg = z["regular"]
    t = z["t"][reg]
    first = plan["turnover_complete_s"][0]
    judged = outcome["judged_s"]
    if plan["judged_at"] == "first turnover":
        mask = (t > 0) & (t <= judged + 1e-9)
        window = "first turnover"
    else:
        mask = (t > first + 1e-9) & (t <= judged + 1e-9)
        window = "after the first turnover"
    _, edges, _ = e7.sheet()
    out = run.junction_weight(edges, z["vm"][reg] > THRESHOLD_V, z["abundance"][reg],
                              z["gate"][reg], mask)  # fmt: skip
    out["window"] = window
    return out


def within(value, lo, hi):
    return value is not None and lo - 1e-12 <= value <= hi + 1e-12


def score(base, protocol, development=False):
    runs = load_runs(base, development)
    pred = protocol["predictions"]
    scores = {}

    verdict = Path(base) / "e1" / ("verdict-seed101.json" if development else "verdict-seed1.json")
    v = json.loads(verdict.read_text())
    worst_dv = max(s["max_vm_difference_mV_all"] for s in v["segments"].values())
    worst_amount = max(s["max_relative_amount_difference"] for s in v["segments"].values())
    scores["E1"] = dict(
        predicted=pred["E1"],
        observed=dict(
            passed=v["passed"],
            max_vm_difference_uV=1e3 * worst_dv,
            max_relative_amount_difference=worst_amount,
        ),  # fmt: skip
        scored_as="passed, with every Vm difference <= 10 uV and amounts <= 3e-6",
        held=bool(v["passed"] and 1e3 * worst_dv <= 10.0 and worst_amount <= 3e-6),
    )

    def classes(group, s):
        return [r["outcome"]["run_class"] for r in group_runs(runs, group, s)]

    def ids(group, s):
        return [
            f"{r['outcome']['arm']}/seed{r['outcome']['seed']}" for r in group_runs(runs, group, s)
        ]

    e3 = {}
    g = group_runs(runs, "fast k1", 0.3)
    zero_every = [r["outcome"]["delta_J_over_records"]["nonzero_records"] == 0 for r in g]
    e3["fast_k1_s0.3"] = dict(
        predicted=pred["E3"]["fast_k1_s0.3"], runs=ids("fast k1", 0.3),
        classes=classes("fast k1", 0.3), runs_with_dJ_0_at_every_record=sum(zero_every),
        scored_as="all runs neutral, and dJ = 0 at every 10 s record (to the judged record) in "
        "at least 3",
        held=bool(len(g) == 4 and all(c == "neutral" for c in classes("fast k1", 0.3))
                  and sum(zero_every) >= 3),
    )  # fmt: skip
    c06 = classes("fast k1", 0.6)
    e3["fast_k1_s0.6"] = dict(
        predicted=pred["E3"]["fast_k1_s0.6"],
        runs=ids("fast k1", 0.6),
        classes=c06,
        group_class=run.group_class(c06),
        scored_as="the group class is neutral (at least 6 of 8 runs)",
        held=run.group_class(c06) == "neutral",
    )
    g = group_runs(runs, "fast k1", 1.0)
    c10 = [r["outcome"]["run_class"] for r in g]
    dj = [r["outcome"]["delta_J"] for r in g]
    dloss = [r["outcome"]["D_loss_fraction"] for r in g]
    all_h = [r["outcome"]["basis"].startswith("absorbed") for r in g]
    e3["fast_k1_s1.0"] = dict(
        predicted=pred["E3"]["fast_k1_s1.0"], runs=ids("fast k1", 1.0), classes=c10,
        group_class=run.group_class(c10), delta_J=dj, D_loss=dloss, all_H=sum(all_h),
        sub_claims=dict(
            erosion_holds=run.group_class(c10) == "erosion",
            dJ_in_minus_0p35_to_minus_0p05=sum(within(x, -0.35, -0.05) for x in dj),
            D_loss_in_5_to_25_percent=sum(within(x, 0.05, 0.25) for x in dloss),
            all_H_in_at_most_2=sum(all_h) <= 2,
        ),
        scored_as="erosion holds (at least 6 of 8), at least 6 runs with dJ in [-0.35, -0.05] "
        "and D-loss in [5%, 25%], and all H in at most 2 runs",
    )  # fmt: skip
    sc = e3["fast_k1_s1.0"]["sub_claims"]
    e3["fast_k1_s1.0"]["held"] = bool(sc["erosion_holds"]
                                      and sc["dJ_in_minus_0p35_to_minus_0p05"] >= 6
                                      and sc["D_loss_in_5_to_25_percent"] >= 6
                                      and sc["all_H_in_at_most_2"])  # fmt: skip
    cc10, cc06 = classes("central k1", 1.0), classes("central k1", 0.6)
    e3["central_k1"] = dict(
        predicted=pred["E3"]["central_k1"],
        runs=ids("central k1", 1.0) + ids("central k1", 0.6),
        classes={"s1.0": cc10, "s0.6": cc06},
        scored_as="both s 1.0 runs erosion and both s 0.6 runs neutral",
        held=bool(cc10 == ["erosion", "erosion"] and cc06 == ["neutral", "neutral"]),
    )
    g3 = group_runs(runs, "fast k3", 1.0)
    dj3 = [r["outcome"]["delta_J"] for r in g3]
    all_h3 = [all_h_time(r["folder"]) for r in g3]
    k3_10 = [r["outcome"]["run_class"] for r in g3]
    stronger = bool(dj3 and dj and np.mean(dj3) < np.mean(dj))
    e3["fast_k3_s1.0"] = dict(
        predicted=pred["E3"]["fast_k3_s1.0"], runs=ids("fast k3", 1.0), classes=k3_10,
        delta_J=dj3, all_H_time_s=all_h3,
        sub_claims=dict(
            erosion_in_all_3=k3_10 == ["erosion"] * 3,
            stronger_than_k1=stronger,
            dJ_in_minus_0p6_to_minus_0p1=sum(within(x, -0.6, -0.1) for x in dj3),
            all_H_by_70_min_in_at_least_1=sum(x is not None for x in all_h3) >= 1,
        ),
        scored_as="erosion in all 3; mean dJ below fast k1's at s 1.0; dJ in [-0.6, -0.1] in "
        "all 3; the sheet all H by the run's end (70 min after the cue) in at least 1",
    )  # fmt: skip
    sc = e3["fast_k3_s1.0"]["sub_claims"]
    e3["fast_k3_s1.0"]["held"] = bool(sc["erosion_in_all_3"] and sc["stronger_than_k1"]
                                      and sc["dJ_in_minus_0p6_to_minus_0p1"] == 3
                                      and sc["all_H_by_70_min_in_at_least_1"])  # fmt: skip
    g36 = group_runs(runs, "fast k3", 0.6)
    k3_06 = [r["outcome"]["run_class"] for r in g36]
    dj36 = [r["outcome"]["delta_J"] for r in g36]
    e3["fast_k3_s0.6"] = dict(
        predicted=pred["E3"]["fast_k3_s0.6"], runs=ids("fast k3", 0.6), classes=k3_06,
        group_class=run.group_class(k3_06), delta_J=dj36,
        scored_as="erosion holds (at least 2 of 3) and the eroding runs' dJ in [-0.4, -0.05]",
        held=bool(run.group_class(k3_06) == "erosion" and all(
            within(x, -0.4, -0.05) for x, c in zip(dj36, k3_06, strict=True) if c == "erosion")),
    )  # fmt: skip
    a_runs = [r for r in runs.values() if r["outcome"]["group"] in ("fast k1", "central k1",
                                                                    "fast k3")]  # fmt: skip
    converted = sum(r["outcome"]["H_copies_converted"] for r in a_runs)
    e3["recruitment"] = dict(
        predicted=pred["E3"]["recruitment"],
        H_copies_converted_in_all_a_runs=converted,
        H_copies_in_all_a_runs=sum(r["outcome"]["H_copies"] for r in a_runs),
        scored_as="no H copy converted in any (a) run",
        held=converted == 0,
    )
    scores["E3"] = e3

    e4 = {}
    for s in (0.6, 1.0):
        g = group_runs(runs, "control", s)
        if not g:
            continue
        r = g[0]
        o = r["outcome"]
        series = o["J_series"]
        upto = [j for x, j in zip(series["t_s"], series["engine"], strict=True)
                if x <= o["judged_s"] + 1e-9]  # fmt: skip
        fall = largest_fall(r["folder"])
        entry = dict(
            run=f"{o['arm']}/seed{o['seed']}", criterion_met=o.get("e4_disc_held"),
            J_min=min(upto), J_at_second_turnover=o["J_engine"], founders_lost=o["founders_lost"],
            D_copies_lost=o["D_copies_lost"], largest_10s_fall=dict(cells=fall[0], at_s=fall[1]),
        )  # fmt: skip
        if s == 0.6:
            entry.update(predicted=pred["E4"]["s0.6"], scored_as="J = 1 at every record",
                         held=min(upto) == 1.0)  # fmt: skip
        else:
            held = bool(o["J_engine"] >= 0.9 and fall[0] < COLLECTIVE_CELLS)
            entry.update(
                predicted=pred["E4"]["s1.0"],
                scored_as="J >= 0.9 at the second turnover's record and no fall of "
                f"{COLLECTIVE_CELLS} or more cells in one 10 s step beyond events",
                held=held,
            )
        e4[f"s{s}"] = entry
    scores["E4"] = e4

    e5 = {}
    for s in (0.6, 1.0):
        rows = {}
        for r in group_runs(runs, "threshold-finding", s):
            o = r["outcome"]
            tau = float(o["arm"].split("tau")[1].split("-")[0])
            n = o["interior_templates_with_5plus_D"]
            k = o["interior_templates_with_5plus_D_converted"]
            first = json.loads((r["folder"] / "plan.json").read_text())["turnover_complete_s"][0]
            rows[tau] = dict(interior_with_5plus_D=n, converted=k,
                             fraction=None if not n else k / n, all_H_s=all_h_time(r["folder"]),
                             first_turnover_s=first)  # fmt: skip
        star = max((tau for tau, x in rows.items() if x["converted"] > 0), default=None)
        entry = dict(per_tau=rows, tau_star_single_draw=star)
        if s == 0.6:
            f = {tau: rows.get(tau, {}).get("fraction") for tau in e7.LADDER_TAU_S}
            entry.update(predicted=pred["E5"]["s0.6"],
                         scored_as="fractions >= 0.40 at 40 s, >= 0.20 at 120 s, <= 0.20 at "
                         "300 s, and tau* >= 120 s",
                         held=bool(f[40.0] is not None and f[40.0] >= 0.40
                                   and f[120.0] is not None and f[120.0] >= 0.20
                                   and (f[300.0] is None or f[300.0] <= 0.20)
                                   and star is not None and star >= 120.0))  # fmt: skip
        else:
            entry.update(predicted=pred["E5"]["s1.0"],
                         scored_as="every tau all H by its first turnover's completion, and no "
                         "conversion at 120 or 300 s",
                         held=bool(rows and all(x["all_H_s"] is not None
                                                and x["all_H_s"] <= x["first_turnover_s"] + 1e-9
                                                for x in rows.values())
                                   and all(rows[tau]["converted"] == 0 for tau in (120.0, 300.0)
                                           if tau in rows)))  # fmt: skip
        e5[f"s{s}"] = entry
    scores["E5"] = e5

    e6 = {}
    law = {"fast k1": 0.20, "central k1": 0.15, "fast k3": 0.6}
    for r in a_runs:
        o = r["outcome"]
        w = weight_after_first_turnover(r["folder"], o)
        dh = w["D-H"]["weight"] / w["D-H"]["A"] if w["D-H"]["A"] else None
        dd = w["D-D"]["weight"] / w["D-D"]["A"] if w["D-D"]["A"] else None
        hh = w["H-H"]["weight"] / w["H-H"]["A"] if w["H-H"]["A"] else None
        e6[f"{o['arm']}/seed{o['seed']}"] = dict(
            window=w["window"], A=w["all"]["A"], law_A=law[o["group"]],
            weight_over_A=dict(D_D=dd, D_H=dh, H_H=hh),
            held=bool(w["all"]["A"] is not None and abs(w["all"]["A"] - law[o["group"]])
                      <= 0.25 * law[o["group"]] and dh is not None and 0.05 <= dh <= 0.2
                      and (dd is None or dd >= 0.8) and (hh is None or hh >= 0.8)),
        )  # fmt: skip
    scores["E6"] = dict(
        predicted=pred["E6"],
        scored_as="per (a) run: A within 25% of the law's value, D-H weight/A in [0.05, 0.2], "
        "D-D and H-H weight/A at least 0.8",
        runs=e6,
        held_in=sum(x["held"] for x in e6.values()),
        runs_scored=len(e6),
    )

    every = list(runs.values())
    refusals = [k for k, r in runs.items() if r["outcome"]["refusal"] is not None]
    censored = [k for k, r in runs.items() if r["outcome"]["stop"] == "censor"]
    worst = max(r["outcome"]["max_osmotic_excess"] for r in every) if every else None
    scores["validity"] = dict(
        predicted=pred["validity"], refusals=[f"{a}/seed{s}" for a, s in refusals],
        censored=[f"{a}/seed{s}" for a, s in censored], max_osmotic_excess=worst,
        definition_checks_failed=[f"{k[0]}/seed{k[1]}" for k, r in runs.items() if not all(
            (r["outcome"].get("checks") or {}).get(c, False) for c in (
                "donor_P_equals_slot_P", "field_solver_as_declared", "layout_equals_sheet70"))],
        scored_as="no refusal (a failed device check refuses the run), no censor, and the "
        "largest osmotic excess at most 0.13",
    )  # fmt: skip
    v_ = scores["validity"]
    v_["held"] = bool(not v_["refusals"] and not v_["censored"] and worst is not None
                      and worst <= 0.13 and not v_["definition_checks_failed"])  # fmt: skip

    b1 = {}
    for r in every:
        o = r["outcome"]
        if "b1" in o:
            b1[f"{o['arm']}/seed{o['seed']}"] = o["b1"]
    k1_b = [v for k, v in b1.items() if k.startswith(("a-donor-fast-k1", "b-"))]
    c06 = [v for k, v in b1.items() if k.startswith("c-disconly-fast-k1-d37-s0.6")]
    scores["B1"] = dict(
        predicted=pred["B1"],
        runs=b1,
        scored_as="B1 false in every fast k1 and (b) run, true in (c) at s 0.6",
        held=bool(k1_b and not any(k1_b) and c06 == [True]),
    )
    return scores


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
                 development=args.development,
                 scores=score(args.output, protocol, args.development))  # fmt: skip
    name = "scores-development.json" if args.development else "scores.json"
    run.write_json(Path(args.output) / name, value)
    print(json.dumps({k: (v.get("held") if isinstance(v, dict) and "held" in v else
                          {kk: vv.get("held") for kk, vv in v.items() if isinstance(vv, dict)})
                      for k, v in value["scores"].items()}, indent=1))  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
