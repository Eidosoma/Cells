"""FR-38's second registered comparison: the builder's end-to-end smoke, on invented inputs only.

The references' invented file (`reference_invented.json`, at the references' tag) holds a family
of the references agent's own invention, in arm A's layout: other tau, pools, rates, window and
times, none of SPEC.md's. Its worlds are no registered world, so the builder may run them (the
protocol's §5). This smoke builds them with worlds.hold from that file's inputs and runs them
through the campaign's own functions (campaign.one, campaign.host_side, campaign.restart_record,
campaign.v0_patch). Its reading of the invented file is its own private helper (`_invented`),
which refuses any other file. It is not the judge's reader, and no judge code is used.

What it shows, each on invented inputs:
- **The worlds and exports.** Every run of the invented family (p = 0 and p = 1 returned,
  p_sched with each machine option, and the blank) at three rungs. Every arm-A readout and
  READOUTS.md §2 quantity is held to the invented file's values:
  - the gap at h, against three times the larger-pair step estimate at the readout's order
    (CRITERIA.md C2's form), plus the rounding term 8 eps S s_y and the file's accuracy;
  - its observed order;
  - the file's `constant` entries, which must be +0.0 in the engine bit for bit.
- **The twin.** The unlabelled p_sched returned run's physical readouts equal the labelled run's,
  bit for bit.
- **The restart.** p_sched returned at h, through the snapshot files at mid-horizon, equals the
  uninterrupted run bit for bit, under the same window policy and under the campaign's POLICY.
- **C and D's exports.** The invented family with a made-up store (C) and in a made-up swelling
  cell (D), each with its blank, at h and h/2. n_Mx and H_store, or V, H_water and W_bath, are
  exported, and G's identity is formed over them: G - G(0) + H_total + H_store + H_water - W_bath.
  In C it closes at rounding (8 eps S of the bookings' magnitude, CRITERIA.md C4's form). In D
  water's bookings are second order (FR-43's C2.7), so the residual is reported with its observed
  order, which must be at least 1.8.
- **P9's V0 patch,** on the invented D: refused by the engine's books, or its records apart from
  the honest ones.

Run: PYTHONPATH=src:. JAX_ENABLE_X64=1 python -m validation.gene_regulation.fr38_v2.smoke --out DIR
[--sample FILE] (by default the invented file from the references' tag through git). It writes
DIR/smoke.json and each run's record under DIR/records/, and exits 1 when a check fails.
"""

import argparse
import json
import math
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

from validation.gene_regulation import release_check
from validation.gene_regulation.fr38_v2 import campaign, worlds

ROOT = Path(__file__).resolve().parents[3]
INVENTED = "validation/gene_regulation/fr38_v2/references/out/reference_invented.json"
REFERENCES_TAG = "fr38-v2-references-2026-11-24"
EPS = 2.0**-52
SAFETY = 3.0  # CRITERIA.md C2's factor on the step estimate
HOLD_SERIES_OF_ORDER_2 = ("label_", "released_present_gross_", "H_")  # The rest are order 3.


def _invented(sample=None):
    """The invented file, the smoke's own reading: its inputs and its runs' values. Refuses a
    file whose family is not the invented one."""
    if sample is not None:
        text = Path(sample).read_text()
    else:
        text = subprocess.run(["git", "show", f"{REFERENCES_TAG}:{INVENTED}"], cwd=ROOT,
                              capture_output=True, check=True, text=True).stdout  # fmt: skip
    doc = json.loads(text)
    if doc.get("family") != "invented":
        raise ValueError("the smoke reads the invented file only")
    return doc


def invented_hold(inputs):
    """worlds.Hold of the invented file's inputs (the references agent's names)."""
    mu, start, copies = inputs["mu0_RT_at_1M"], inputs["initial_mM"], inputs["initial_copies"]
    return worlds.Hold(
        "invented", mu_fate=float(mu["R"]), m0_mM=start["M"], n0_mM=start["N"],
        pi0_mM=start["Pi"], mu_N=float(mu["N"]), r0_copies=copies["R"],
        rs0_copies=copies["R_s"], residues=inputs["L_residues"], stages=inputs["stages"],
        speed=inputs["speed_nt_per_s"], k_N_mM=inputs["K_N_mM"],
        pool_copies=inputs["pool_machines_copies"], template_copies=inputs["template_copies"],
        k_I=inputs["k_I_per_mM_s"], tau_s=inputs["tau_s"], h0_copies=inputs["H0_copies"],
        k_d=inputs["k_d_per_s"], k_s=inputs["k_s_per_s"],
        p_sched=tuple(tuple(x) for x in inputs["p_sched"]), window=tuple(inputs["window_s"]),
        horizon=inputs["horizon_s"], every=inputs["output_interval_s"],
        samples=tuple(inputs["samples_s"]), background_mM=inputs["cell_background_mM"]["K"],
    )  # fmt: skip


# Made-up values for the invented C and D (not SPEC.md's): a faster store, and water fast enough to
# cross 2 V0 within the invented horizon.
MADE_UP_STORE = worlds.Store(mx_mM=1.0e-6, forward_per_s=1 / 200)
MADE_UP_WATER = worlds.Water(lp_m_per_Pa_s=1.0e-13)


def _order(name):
    return 2 if name.startswith(HOLD_SERIES_OF_ORDER_2) and name != "H_tx_release" else 3


def _series_scale(name, x):
    """A smoke's scale: the largest |y| of the readout, or of its row for a label or the gross."""
    if name.startswith("label_") or name.startswith("released_present_gross_"):
        row = "R_s" if ("_R_s_" in name or name.endswith("short_lived")) else "R"
        return max(abs(v) for v in x[f"n_{row}"])
    return max(abs(v) for v in x[name]) if x[name] else 0.0


def compare(runs, sample, rungs, steps):
    """{run: {readout: verdict}} of the engine's readouts at the rungs against the invented file."""
    h, h2, h4 = rungs[-1], rungs[-2], rungs[-3]
    out, failed = {}, []
    for run, ref in sample["runs"].items():
        engine = {dt: runs[(run, dt)] for dt in rungs}
        rows = {}
        for name, entry in ref["series"].items():
            ys = {dt: engine[dt][name] for dt in rungs}
            d1 = max(abs(a - b) for a, b in zip(ys[h2], ys[h], strict=True))
            d2 = max(abs(a - b) for a, b in zip(ys[h4], ys[h2], strict=True))
            p = _order(name)
            est = max(d1 / (2**p - 1), d2 / (2**p * (2**p - 1)))
            scale = _series_scale(name, engine[h])
            rounding = 8 * EPS * steps[h] * scale
            e_ref = max((a for a in entry["accuracy"] if a is not None), default=0.0)
            gap = max(abs(a - b) for a, b in zip(ys[h], entry["value"], strict=True))
            constants_ok = all(
                y == 0.0 and math.copysign(1.0, y) > 0
                for y, c in zip(ys[h], entry["class"], strict=True)
                if c == "constant"
            )
            ok = gap <= SAFETY * est + e_ref + rounding and constants_ok
            q = math.log2(d2 / d1) if d1 > 10 * rounding and d2 > 10 * rounding else None
            rows[name] = dict(gap_over_scale=gap / scale if scale else gap,
                              tolerance_over_scale=(SAFETY * est + e_ref + rounding) / scale
                              if scale else None, observed_order=q,
                              constants_plus_zero=constants_ok, ok=ok)  # fmt: skip
            if not ok:
                failed.append(f"{run} {name}")
        out[run] = rows
    return out, failed


def compare_host(host, sample, rungs, steps):
    """Route 2, survival and the excess at h against the invented file (CRITERIA.md C2's forms)."""
    h, h2, h4 = rungs[-1], rungs[-2], rungs[-3]
    out, failed = {}, []
    for run, ref in sample["runs"].items():
        if run == "blank":
            continue
        rows = {}
        for e in ref["route2"]:
            mine = next(r for r in host[(run, h)]["route2"]
                        if r["fate"] == e["fate"] and r["ts_s"] == e["ts_s"])  # fmt: skip
            g = mine["grid_error"] or 0.0
            rounding = 8 * EPS * steps[h] * max(e["scale"], 1e-300)
            gap = abs(mine["value"] - e["value"])
            ok = (gap == 0.0 and mine["value"] == 0.0) if e["class"] == "constant" else (
                gap <= SAFETY * g + (e["accuracy"] or 0.0) + rounding)  # fmt: skip
            rows[f"route2 {e['fate']} {e['ts_s']:g}"] = dict(gap=gap, grid_error=g, ok=ok)
            if not ok:
                failed.append(f"{run} route2 {e['fate']} {e['ts_s']:g}")
        for e in ref["survival"]:
            mine = next(r for r in host[(run, h)]["survival"]
                        if r["fate"] == e["fate"] and r["ts_s"] == e["ts_s"])  # fmt: skip
            if e["ratio"] is None:
                ok = mine["ratio"] is None and mine["alive_t2"] == 0.0 and mine["alive_ts"] == 0.0
            else:
                ok = mine["ratio"] is not None and abs(mine["ratio"] - e["ratio"]) <= 1e-6
            rows[f"survival {e['fate']} {e['ts_s']:g}"] = dict(
                engine_ratio=mine["ratio"], reference_ratio=e["ratio"], ok=ok
            )
            if not ok:
                failed.append(f"{run} survival {e['fate']} {e['ts_s']:g}")
        for fate, entry in ref["excess_over_blank"].items():
            ys = {dt: host[(run, dt)]["excess_over_blank"][fate] for dt in rungs}
            d1 = max(abs(a - b) for a, b in zip(ys[h2], ys[h], strict=True))
            d2 = max(abs(a - b) for a, b in zip(ys[h4], ys[h2], strict=True))
            est = max(d1 / 7, d2 / 56)
            rounding = 8 * EPS * steps[h] * entry["scale"]
            gap = max(abs(a - b) for a, b in zip(ys[h], entry["value"], strict=True))
            ok = gap <= SAFETY * est + max(entry["accuracy"]) + rounding
            rows[f"excess {fate}"] = dict(gap_over_scale=gap / entry["scale"], ok=ok)
            if not ok:
                failed.append(f"{run} excess {fate}")
        out[run] = rows
    return out, failed


def _physical(x):
    return {k: v for k, v in x.items() if not k.startswith("label_")}


def _identical(a, b):
    """Bit for bit: every readout's values, as floats, the same (the sign of zero included)."""
    if a.keys() != b.keys():
        return False
    return all(
        len(a[k]) == len(b[k])
        and all(x == y and math.copysign(1.0, x) == math.copysign(1.0, y)
                for x, y in zip(a[k], b[k], strict=True))
        for k in a
    )  # fmt: skip


def _identity(record):
    """G's identity over the engine's own series, relative to its scale (engine_run's checks)."""
    c = record["checks"]
    return c["G_identity_largest_pJ"] / max(c["energy_magnitude_at_end_pJ"], 1e-300)


def smoke(out, sample=None):
    out = Path(out)
    doc = _invented(sample)
    f = invented_hold(doc["inputs"])
    rungs = list(worlds.RUNGS)
    names = {"blank": "blank returned", "p=0 returned": "p=0 returned",
             "p=1 returned": "p=1 returned", "p_sched returned": "p_sched returned",
             "p_sched held": "p_sched held"}  # fmt: skip
    runs, host, records, steps, timing = {}, {}, {}, {}, {}
    for dt in rungs:
        for ref_name, run in names.items():
            started = time.perf_counter()
            record = campaign.one(worlds.hold("invented", run, dt=dt, f=f), family="invented",
                                  run=run)  # fmt: skip
            timing[f"{run} dt={dt:g}"] = time.perf_counter() - started
            if record.get("refused"):
                raise RuntimeError(f"the invented {run} at {dt} s was refused: {record['refusal']}")
            records[(ref_name, dt)] = record
            steps[dt] = record["steps"]
            campaign._write(out / "records" / "invented" / f"dt{dt:g}" / f"{run}.json", record,
                            {"smoke": True})  # fmt: skip
        for ref_name in names:
            blank = None if ref_name == "blank" else records[("blank", dt)]
            extra = campaign.host_side(records[(ref_name, dt)], f.window, f.samples, blank)
            runs[(ref_name, dt)] = {**records[(ref_name, dt)]["readouts"], **extra.pop("series")}
            host[(ref_name, dt)] = extra
    results, failed = {}, []
    results["readouts against the invented file"], bad = compare(runs, doc, rungs, steps)
    failed += bad
    results["host-side quantities against the invented file"], bad = compare_host(
        host, doc, rungs, steps)  # fmt: skip
    failed += bad
    h = rungs[-1]
    twin = campaign.one(worlds.hold("invented", "p_sched returned unlabelled", dt=h, f=f),
                        family="invented", run="p_sched returned unlabelled")  # fmt: skip
    same = _identical(_physical(records[("p_sched returned", h)]["readouts"]), twin["readouts"])
    same_checks = twin["checks"] == records[("p_sched returned", h)]["checks"]
    results["the twin's physical readouts and checks equal the labelled run's"] = dict(
        readouts=same, checks=same_checks, ok=same and same_checks
    )
    if not (same and same_checks):
        failed.append("twin")
    join = f.horizon / 2
    policy = campaign.WindowPolicy(window_steps=int(round(join / h)) // 2,
                                   recording="observations")  # fmt: skip
    raw = worlds.hold("invented", "p_sched returned", dt=h, f=f)
    whole = campaign.one(raw, policy=policy, family="invented", run="p_sched returned")
    resumed = campaign.restart_record(raw, join, out / "restart", policy=policy,
                                      family="invented", run="p_sched returned")  # fmt: skip
    across = _identical(whole["readouts"], records[("p_sched returned", h)]["readouts"])
    restart_ok = _identical(whole["readouts"], resumed["readouts"])
    results["the restart through the snapshot files equals the uninterrupted run"] = dict(
        join_s=join, window_steps=policy.window_steps, ok=restart_ok,
        same_under_the_campaign_policy=across)  # fmt: skip
    if not (restart_ok and across):
        failed.append("restart")
    checks = release_check.Checks()  # The net agreement's scope on an invented record (AN-like).
    path = out / "records" / "invented" / f"dt{h:g}" / "p_sched returned.json"
    for row, fate, k in (("R", "durable", f.k_d), ("R_s", "short_lived", f.k_s)):
        release_check.survival(checks, "invented p_sched returned", path, row, fate,
                               window=f.window, ts=f.samples[1], k_expected=k)  # fmt: skip
    scoped = [dict(r, ok=r["ok"] and r["net_agrees"] is None) for r in checks.rows]
    results["release_check's net agreement, out of scope at the invented e^(y_f)"] = dict(
        rows=scoped, ok=all(r["ok"] for r in scoped))  # fmt: skip
    if not all(r["ok"] for r in scoped):
        failed.append("net scope")
    variants = {"C": replace(f, name="invented C", store=MADE_UP_STORE),
                "D": replace(f, name="invented D", water=MADE_UP_WATER)}  # fmt: skip
    extra_series = {"C": ("n_Mx", "H_store"), "D": ("V", "H_water", "W_bath", "n_K", "n_Y")}
    for key, g in variants.items():
        for run in ("p_sched returned", "blank returned"):
            residuals = {}
            for dt in (h, h / 2):
                record = campaign.one(worlds.hold("invented", run, dt=dt, f=g),
                                      family=f"invented {key}", run=run)  # fmt: skip
                campaign._write(out / "records" / f"invented-{key}" / f"dt{dt:g}" / f"{run}.json",
                                record, {"smoke": True})  # fmt: skip
                residuals[dt] = record["checks"]["G_identity_largest_pJ"]
                if dt == h:
                    x, identity = record["readouts"], _identity(record)
                    bound = 8 * EPS * record["steps"]  # C4's form, relative to the magnitude
            present = all(name in x and len(x[name]) == len(x["n_R"]) for name in
                          extra_series[key])  # fmt: skip
            moved = max(x["V"]) / x["V"][0] if key == "D" else max(x["n_Mx"]) / x["n_Mx"][0]
            order = math.log2(residuals[h] / residuals[h / 2]) if residuals[h / 2] else None
            # C's books are exact per half-step, so G's identity closes at rounding. Water's are
            # second order (FR-43's C2.7), so D's residual is reported with its observed order.
            closes = identity <= bound if key == "C" else (order is not None and 1.8 <= order)
            ok = present and moved > 1.5 and closes
            results[f"the invented {key}'s exports and G's identity: {run}"] = dict(
                exports_present=present, growth=moved, G_identity_over_magnitude=identity,
                rounding_bound_over_magnitude=bound, G_identity_pJ_at_h_and_h_over_2=residuals,
                observed_order=order, ok=ok)  # fmt: skip
            if not ok:
                failed.append(f"invented {key} {run}")
    honest = campaign.one(worlds.hold("invented", "p_sched returned", dt=h, f=variants["D"]),
                          family="invented D", run="p_sched returned")  # fmt: skip
    with campaign.v0_patch():
        planted = campaign.one(
            worlds.hold("invented", "p_sched returned", dt=h, f=variants["D"]),
            family="invented D",
            run="p_sched returned",
            plant="P9",
        )
    if planted.get("refused"):
        caught = dict(refused=True, refusal=planted["refusal"][:300])
    else:
        x, y = honest["readouts"], planted["readouts"]
        caught = dict(
            refused=False,
            largest_relative_change={
                k: max(abs(a - b) for a, b in zip(x[k], y[k], strict=True)) / max(map(abs, x[k]))
                for k in ("n_R", "n_R_s", "label_R_win", "H_rel_tx_release_durable", "G_minus_G0")
            },
        )
        caught["changed"] = min(caught["largest_relative_change"].values()) > 1e-6
    results["P9's V0 patch on the invented D"] = caught | {
        "ok": caught.get("refused") or caught.get("changed", False)
    }
    if not results["P9's V0 patch on the invented D"]["ok"]:
        failed.append("P9")
    failed += coarse_rungs_and_twins(out, f, variants, results)
    failed += made_up_b(out, results)
    failed += own_checks(records, h, results)
    summary = dict(kind="cells.fr38_v2.smoke@1", what=__doc__.splitlines()[0],
                   failed=failed, seconds=timing, results=results)  # fmt: skip
    (out / "smoke.json").write_text(json.dumps(summary, indent=1, default=str) + "\n")
    return summary


# SPEC.md §4: zero in the blank at every output by the model's structure (READOUTS.md's names)
BLANK_ZEROS = ("H_tx_release", "int_Q_tx", "int_J_I_tx", "int_S_tx", *(f"C_tx_{j}" for j in
               range(1, 9)), "E_tx", "W_tx", "H_tx", "int_Q_tx_release_durable",
               "int_Q_tx_release_short_lived", "H_rel_tx_release_durable",
               "H_rel_tx_release_short_lived", *(f"label_{r}_{c}" for r in ("R", "R_s")
               for c in ("pre", "win", "post")))  # fmt: skip
# A made-up B (not SPEC.md's): A1 with another release, rates, window and a short horizon
MADE_UP_B = replace(worlds.ARM_B, tau_s=60.0, p=0.4, k_d=1 / 500, k_s=1 / 100,
                    window=(120.0, 360.0), horizon=600.0, every=30.0,
                    samples=(360.0, 480.0, 600.0))  # fmt: skip
B_SERIES = ("n_X", "n_N", "n_M", "n_A", "n_ATP", "n_ADP", "n_Pi", "n_R", "n_R_s", "n_P",
            "H_tx_release", *(f"C_tx_{j}" for j in range(1, 9)), "E_tx", "W_tx", "F_pol",
            "int_J_I_tx", "int_S_tx", "int_Q_tx", "int_Q_tx_release_durable",
            "int_Q_tx_release_short_lived", "int_D_R", "int_D_R_s", "H_tx", "H_deg_R", "H_deg_R_s",
            "H_rel_tx_release_durable", "H_rel_tx_release_short_lived", "G_minus_G0", "F_rib",
            *(f"{x}_{c}" for c in ("tl", "tl_s") for x in ("E", "W", "int_J_I", "int_S", "int_Q")),
            *(f"C_{c}_{j}" for c in ("tl", "tl_s") for j in range(1, 9)), "int_D_P", "int_J_C",
            "H_tl", "H_deg_P", "H_rc",
            *(f"label_{r}_{c}" for r in ("R", "R_s")
              for c in ("resyn", "pool0", "pre", "win", "post")))  # fmt: skip


def _plus_zero(values):
    return all(v == 0.0 and math.copysign(1.0, v) > 0 for v in values)


def coarse_rungs_and_twins(out, f, variants, results):
    """The invented C and D at the coarse rungs (2 and 1 s), each run and its blank, with the
    blank's structural zeros +0.0 by their bits at every rung, and each one's twin at h bit for bit
    in its physical readouts and checks."""
    failed = []
    for key, g in variants.items():
        rows = {}
        for dt in (2.0, 1.0, 0.5):
            for run in ("p_sched returned", "blank returned"):
                record = campaign.one(worlds.hold("invented", run, dt=dt, f=g),
                                      family=f"invented {key}", run=run)  # fmt: skip
                if record.get("refused"):
                    rows[f"{run} dt={dt:g}"] = dict(refused=record["refusal"][:300], ok=False)
                    failed.append(f"invented {key} {run} at {dt:g} s refused")
                    continue
                zeros = run.startswith("blank") and all(
                    _plus_zero(record["readouts"][name]) for name in BLANK_ZEROS
                )
                rows[f"{run} dt={dt:g}"] = dict(refused=False, ok=True,
                                                blank_zeros_plus_zero=zeros or None)  # fmt: skip
                if run.startswith("blank") and not zeros:
                    rows[f"{run} dt={dt:g}"]["ok"] = False
                    failed.append(f"invented {key} blank zeros at {dt:g} s")
                if dt == 0.5 and run == "p_sched returned":
                    honest = record
        unlabelled = "p_sched returned" + worlds.UNLABELLED
        twin = campaign.one(worlds.hold("invented", unlabelled, dt=0.5, f=g),
                            family=f"invented {key}", run=unlabelled)  # fmt: skip
        same = _identical(_physical(honest["readouts"]), twin["readouts"])
        same = same and twin["checks"] == honest["checks"]
        rows["twin at h, bit for bit"] = dict(ok=same)
        if not same:
            failed.append(f"invented {key} twin")
        results[f"the invented {key} at every rung, its blank's zeros and its twin"] = rows
    return failed


def made_up_b(out, results):
    """A made-up B (MADE_UP_B): both machine options at h, the returned one's twin, P4's label at
    completion, and the returned run at 2 s, the coarsest rung. Every arm-B readout of READOUTS.md
    §1 has one value per output; the twin equals its run bit for bit; G's identity and §9.7's
    identities hold at rounding (release_check.energy and identities)."""
    failed, rows, records = [], {}, {}
    p = f"p={MADE_UP_B.p:g}"
    jobs = [(f"{p} returned", 0.5, None), (f"{p} held", 0.5, None),
            (f"{p} returned{worlds.UNLABELLED}", 0.5, None), (f"{p} returned", 2.0, None),
            (f"{p} returned", 0.5, {"label_at": "completion"})]  # fmt: skip
    for run, dt, edits in jobs:
        name = f"{run} dt={dt:g}" + (" P4" if edits else "")
        record = campaign.one(worlds.b(run, dt=dt, edits=edits, f=MADE_UP_B), family="made-up B",
                              run=run)  # fmt: skip
        if record.get("refused"):
            rows[name] = dict(refused=record["refusal"][:300], ok=False)
            failed.append(f"made-up B {name} refused")
            continue
        records[name] = record
        x = record["readouts"]
        twin_run = run.endswith(worlds.UNLABELLED)
        wanted = [s for s in B_SERIES if not (twin_run and s.startswith("label_"))]
        missing = [s for s in wanted if len(x.get(s, ())) != len(record["t"])]
        checks = release_check.Checks()
        release_check.energy(checks, name, record)
        release_check.identities(checks, name, record, run.split(" ")[1])
        bad = [r["check"] for r in checks.rows if not r["ok"]]
        rows[name] = dict(refused=False, missing=missing, failed_checks=bad,
                          ok=not missing and not bad)  # fmt: skip
        if missing or bad:
            failed.append(f"made-up B {name}")
    labelled, twin = records.get(f"{p} returned dt=0.5"), records.get(
        f"{p} returned{worlds.UNLABELLED} dt=0.5")  # fmt: skip
    same = bool(labelled and twin) and _identical(_physical(labelled["readouts"]),
                                                  twin["readouts"])  # fmt: skip
    same = same and twin["checks"] == labelled["checks"]
    rows["the twin, bit for bit"] = dict(ok=same)
    if not same:
        failed.append("made-up B twin")
    results["a made-up B: its readouts, identities, twin and P4"] = rows
    return failed


def own_checks(records, h, results):
    """release_check's §9.7 identities need A1's pool, so on the invented hold runs (another pool)
    only its energy check runs: G's identity and the routes' heats at rounding."""
    checks = release_check.Checks()
    for (run, dt), record in records.items():
        if dt == h:
            release_check.energy(checks, f"invented {run}", record)
    bad = [r["check"] for r in checks.rows if not r["ok"]]
    results["release_check's energy check on the invented runs at h"] = dict(
        checks=len(checks.rows), failed=bad, ok=not bad)  # fmt: skip
    return [f"energy: {b}" for b in bad]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True)
    parser.add_argument("--sample")
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    source = campaign._source(out / "source")
    (out / "source.json").write_text(json.dumps(source, indent=1))
    summary = smoke(out, args.sample)
    print(json.dumps(dict(failed=summary["failed"]), indent=1))
    return 0 if not summary["failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
