"""R-loop's registered references, bands and plants (a dated addition).

python -m validation.fr7.references.loop_design [--check]

From interface/loop_inputs.json (loop_worlds.py) it writes interface/loop_rows.json,
loop_plants.json and loop_zero_power.json. Those hold:
- the closed and clamped arms, with every row's value, bound, band and status;
- the plants and their margins;
- the cut's power and persistence;
- the regulator's observed range;
- the excursion of N, the pump, Na and V.

--check regenerates and compares, as design.py does (about 2 minutes of one CPU). --calibrate
also writes interface/loop_calibration.json, the bands' calibration against an emulated split
(about 10 minutes); --check never regenerates it.
"""

import argparse
import json
import sys
import time

import numpy as np
from scipy.integrate import solve_ivp

from validation.fr7.references import clearance, design, loop, loop_worlds

IFACE = loop_worlds.IFACE
ROWS_FILE = IFACE / "loop_rows.json"
CALIBRATION_FILE = IFACE / "loop_calibration.json"
PLANTS_FILE = IFACE / "loop_plants.json"
ZERO_FILE = IFACE / "loop_zero_power.json"

# The compared core: compared at every row the arm compares. Every other compared row is judged
# only where a plant moves it by the power margin (R-chain's rule).
CORE = ("n_P_fmol", "N_units", "PA_units_m3_s", "W_fmol", "R_units", "C_P_fmol", "total_fmol",
        "s")
INFORMATION = ("u", "F_loop", "c_mM", "pump_G_J_per_mol", "I_units_A", "I_pump_A", "P_fmol",
               "supplied_fmol")
# The clamp moves no material, so no plant moves the clamped arm's total: the account is judged
# on the closed arm (where nu and c_u move it), and is outside the clamped arm's core.
CORE_BY_ARM = {"closed": CORE, "clamped": tuple(k for k in CORE if k != "total_fmol")}
SPLIT_STEPS = (0.1, 0.05)


def arm_values(world, recs):
    """The registered quantities of one arm's records, as arrays."""
    t = np.array([r["t"] for r in recs])
    out = {"n_T_fmol": [r["n_T"] for r in recs], "F_T": [r["F_T"] for r in recs],
           "s": [r["s"] for r in recs], "u": [r["u"] for r in recs],
           "F_loop": [r["F_loop"] for r in recs], "n_P_fmol": [r["n_P"] for r in recs],
           "N_units": [r["N"] for r in recs], "PA_units_m3_s": [r["PA_units"] for r in recs],
           "W_fmol": [r["W"] for r in recs], "R_units": [r["R"] for r in recs],
           "C_P_fmol": [r["C_P"] for r in recs], "total_fmol": [r["total"] for r in recs],
           "V_V": [r["V"] for r in recs], "pump_fmol_per_s": [r["pump_cycles_fmol_s"]
                                                             for r in recs],
           "pump_G_J_per_mol": [r["pump_G"] for r in recs], "I_units_A": [r["I_units"]
                                                                          for r in recs],
           "I_pump_A": [r["I_pump"] for r in recs], "supplied_fmol": world.S * t}
    for s, sp in enumerate(world.species):
        out[f"{sp}_fmol"] = [r["amounts"][s] for r in recs]
    out["c_mM"] = [r["n_T"] / world.volume for r in recs]
    out["D"] = clearance.hill_drive(np.array(out["c_mM"]), world.K, world.n)
    return {k: np.asarray(v, dtype=float) for k, v in out.items()}


def rule_of(inputs, quantity):
    for name, rule in inputs["loop_band_rules"].items():
        if name != "note" and quantity in rule["quantities"]:
            return rule
    return None


def build(inputs, log=print):
    started = time.perf_counter()
    lp = inputs["loop"]
    dt = inputs["step"]["dt_s"]
    m_min = inputs["power"]["margin"]
    rows = np.array(lp["rows_s"], dtype=float)
    times = [float(t) for t in rows]
    arms_in = lp["arms"]
    t_d, F_star, F_bound = arms_in["t_d_s"], arms_in["F_star"], arms_in["F_star_bound"]
    i_d = times.index(t_d)
    V = loop.LoopVariant
    variants = {"closed": loop.CLOSED,
                "clamped": V("clamped", clamp_from_s=t_d, clamp_value=F_star)}

    def run(variant, rtol=1e-12, dense=False):
        w = loop.LoopWorld(inputs, variant)
        out = loop.simulate(w, rows, rtol=rtol, dense=dense)
        return w, out

    arms, dense = {}, {}
    for arm, variant in variants.items():
        w, (r12, steps, s_dense) = run(variant, dense=True)
        _, (r10, _) = run(variant, rtol=1e-10)
        v12, v10 = arm_values(w, r12), arm_values(w, r10)
        bounds = {k: np.abs(v12[k] - v10[k]) + design.CLOSED_BOUND * np.abs(v12[k])
                  for k in v12}
        # the material total is a small difference of large ledger terms (C_P and S_P t near
        # 0.05 fmol against a total near 1e-4 fmol): its rounding is that of its terms
        terms = (np.abs(v12["n_P_fmol"]) + (np.abs(v12["N_units"]) + np.abs(v12["R_units"]))
                 / w.cu_declared + np.abs(v12["C_P_fmol"]) + np.abs(v12["supplied_fmol"]))
        bounds["total_fmol"] = np.abs(v12["total_fmol"] - v10["total_fmol"]) + \
            design.CLOSED_BOUND * terms
        arms[arm] = dict(world=w, values=v12, bounds=bounds, steps=steps)
        dense[arm] = s_dense
        log(f"  {arm}: {time.perf_counter() - started:.1f} s")
    closed, clamped = arms["closed"], arms["clamped"]
    if abs(closed["values"]["F_loop"][i_d] - F_star) > 1e-12:
        raise RuntimeError("F* is not the closed trajectory's loop factor at t_d")

    # the clamped arm's allowance for the engine's own F*: the arm at F* +- the bound
    sens = {}
    for sign in (1.0, -1.0):
        w, (r, _) = run(V("clamped_shifted", clamp_from_s=t_d, clamp_value=F_star
                          + sign * F_bound))
        sens[sign] = arm_values(w, r)
    allowance = {k: 0.5 * np.abs(sens[1.0][k] - sens[-1.0][k]) for k in clamped["values"]}

    # classes, bands and first statuses
    for arm, d in arms.items():
        d["classes"], d["bands"], d["status"] = {}, {}, {}
        first = 1 if arm == "closed" else i_d + 1  # the clamped arm is the closed one until t_d
        for k, x in d["values"].items():
            rule = rule_of(inputs, k)
            compared = rule is not None and k not in INFORMATION and np.any(x)
            d["classes"][k] = "compared" if compared else "information"
            st = ["information"] * rows.size
            if compared:
                extra = allowance[k] if arm == "clamped" else 0.0
                d["bands"][k] = design.band(rule, x, d["bounds"][k]) + extra
                st = ["information"] * first + ["compared"] * (rows.size - first)
            d["status"][k] = st

    # plants: the closed arm's, and the cut at F = 1 on the clamped arm
    plants, margins = {}, {}
    w0 = closed["world"]
    for pname, variant in loop_worlds.plant_variants(dt).items():
        reason = loop_worlds.applicability(w0, pname)
        if reason:
            plants[pname] = dict(applicable=False, reason=reason)
            continue
        arm = "clamped" if pname == "cut_at_one" else "closed"
        if pname == "cut_at_one":
            variant = V("cut_at_one", clamp_from_s=t_d, clamp_value=1.0)
        t0 = time.perf_counter()
        wp, (recs, _) = run(variant)
        pv = arm_values(w0, recs) if wp.m == w0.m else arm_values(wp, recs)
        base = arms[arm]
        pm = {k: design.margins(pv[k], base["values"][k], base["bands"][k])
              for k in base["bands"]}
        plants[pname] = dict(applicable=True, arm=arm, values={k: pv[k] for k in base["bands"]},
                             margin=pm)
        margins[pname] = pm
        log(f"    {pname}: {time.perf_counter() - t0:.1f} s")

    # every other compared row: judged only where a plant has power on it
    gaps = {}
    for arm, d in arms.items():
        pms = {p: m for p, m in margins.items() if plants[p]["arm"] == arm}
        compared = list(d["bands"])
        union = design.power_union(pms, compared, rows.size, m_min)
        core = CORE_BY_ARM[arm]
        for k in compared:
            if k in core:
                continue
            d["status"][k] = ["compared" if (st == "compared" and union[k][r]) else
                              "information" for r, st in enumerate(d["status"][k])]
        gaps[arm] = {k: [times[r] for r in range(rows.size)
                         if d["status"][k][r] == "compared" and not union[k][r]]
                     for k in compared if k in core}
        gaps[arm] = {k: v for k, v in gaps[arm].items() if v}

    # the cut's power: |closed - clamped| against the clamped arm's band, after t_d
    cut_power = {}
    for k, b in clamped["bands"].items():
        m = np.abs(closed["values"][k] - clamped["values"][k]) / b
        sel = [r for r in range(rows.size) if clamped["status"][k][r] == "compared"]
        if sel:
            cut_power[k] = dict(margin=m.tolist(), rows_compared=len(sel),
                                rows_with_power=int(sum(m[r] >= m_min for r in sel)),
                                min_margin=float(min(m[r] for r in sel)),
                                max_margin=float(max(m[r] for r in sel)))
    # persistence: N_closed - N_clamped after t_clear
    eps = inputs["clearance"]["epsilon"]
    tc = clearance.t_clear(times, closed["values"]["D"], eps)
    dN = closed["values"]["N_units"] - clamped["values"]["N_units"]
    dN_band = closed["bands"]["N_units"] + clamped["bands"]["N_units"]
    after = [r for r in range(rows.size) if tc is not None and times[r] >= tc
             and times[r] > t_d]
    persistence = dict(
        t_clear_s=tc, t_d_s=t_d, F_star=F_star, F_star_bound=F_bound,
        rows_s=[times[r] for r in after], dN_units=[float(dN[r]) for r in after],
        dN_relative_to_closed=[float(dN[r] / closed["values"]["N_units"][r]) for r in after],
        band_units=[float(dN_band[r]) for r in after],
        margin=[float(abs(dN[r]) / dN_band[r]) for r in after],
        note="N_closed - N_clamped; its band is the sum of the two arms' N bands")
    # the regulator's observed range
    s_range = dict(
        closed=dict(rows=[float(np.min(closed["values"]["s"])),
                          float(np.max(closed["values"]["s"]))], dense=list(dense["closed"])),
        clamped=dict(rows=[float(np.min(clamped["values"]["s"])),
                           float(np.max(clamped["values"]["s"]))], dense=list(dense["clamped"])),
        plants={p: [float(np.min(d["values"]["s"])), float(np.max(d["values"]["s"]))]
                for p, d in plants.items() if d.get("applicable") and "s" in d["values"]},
        note="dense: over every accepted integration step (rtol 1e-12), not only the rows")
    # excursions the lead asked to see
    excursion = dict(
        N_over_N0=[float(np.min(closed["values"]["N_units"]) / w0.N0),
                   float(np.max(closed["values"]["N_units"]) / w0.N0)],
        pump_over_capacity=[float(np.min(closed["values"]["pump_fmol_per_s"])
                                  / w0.pump["capacity_fmol_cycles_per_s"]),
                            float(np.max(closed["values"]["pump_fmol_per_s"])
                                  / w0.pump["capacity_fmol_cycles_per_s"])],
        Na_mM=[float(np.min(closed["values"]["Na_fmol"]) / w0.volume),
               float(np.max(closed["values"]["Na_fmol"]) / w0.volume)],
        V_mV=[float(np.min(closed["values"]["V_V"]) * 1e3),
              float(np.max(closed["values"]["V_V"]) * 1e3)])
    log(f"  loop: {time.perf_counter() - started:.1f} s")
    docs = documents(inputs, times, arms, plants, margins, gaps, cut_power, persistence,
                     s_range, excursion, allowance)
    return docs, closed


# ---------------------------------------------------------------- the bands' calibration


def split_calibration(inputs, rows, closed, log=print):
    """A second-order engine emulated: Strang splitting of A (the regulator, the precursor, the
    producer and the units, with Na and V frozen) around B (the ions and the pump, with N
    frozen), each sub-flow integrated tightly (DOP853 at rtol 1e-12; Radau for B). It runs at
    steps of 0.1 and 0.05 s. The errors' ratio checks the order, and the errors at 1 ms follow as
    e(0.05) (1 ms/0.05 s)^2. Reported: the extrapolated error over the band, per quantity, at
    the worst row after the start."""
    out = {}
    errs = {}
    for h in SPLIT_STEPS:
        t0 = time.perf_counter()
        v = _split_run(inputs, rows, h)
        errs[h] = {k: np.abs(v[k] - closed["values"][k]) for k in v}
        log(f"    split at {h} s: {time.perf_counter() - t0:.1f} s")
    h1, h2 = SPLIT_STEPS
    dt = inputs["step"]["dt_s"]
    for k in errs[h2]:
        if k not in closed["bands"]:
            continue
        e1, e2 = errs[h1][k][1:], errs[h2][k][1:]
        # an order only where the split's error stands above the reference's bound and above
        # the sub-flows' own integration noise (rtol 1e-10): not for the material total, which
        # the split conserves to rounding
        noise = 1e-8 * float(np.max(np.abs(closed["values"][k])))
        sel = e2 > np.maximum(100.0 * closed["bounds"][k][1:], noise)
        order = (float(np.median(np.log(e1[sel] / e2[sel]) / np.log(h1 / h2)))
                 if sel.any() else None)
        at_dt = e2 * (dt / h2) ** 2
        out[k] = dict(order=order, max_band_fraction_at_dt=float(np.max(
            at_dt / closed["bands"][k][1:])))
    return out


def _split_run(inputs, rows, h):
    world = loop.LoopWorld(inputs)
    model = loop.LoopModel(world)
    y = model.initial()
    ion_idx = list(range(model.i_s))  # the charge and the amounts
    a_idx = [i for i in range(model.size) if i not in ion_idx]
    atol = model.atol()

    def flow(idx, t0, t1, y0, method):
        def f(t, z):
            yy = y0.copy()
            yy[idx] = z
            return model.rhs(t, yy)[idx]

        sol = solve_ivp(f, (t0, t1), y0[idx], method=method, rtol=1e-10, atol=atol[idx])
        y1 = y0.copy()
        y1[idx] = sol.y[:, -1]
        return y1

    t, records = 0.0, {0.0: model.record(0.0, y)}
    targets = sorted(set(float(r) for r in rows))
    n_steps = int(round(world.horizon / h))
    for k in range(n_steps):
        t0 = k * h
        y = flow(a_idx, t0, t0 + 0.5 * h, y, "DOP853")
        y = flow(ion_idx, t0, t0 + h, y, "Radau")
        y = flow(a_idx, t0 + 0.5 * h, t0 + h, y, "DOP853")
        t = t0 + h
        for r in targets:
            if abs(r - t) < 1e-9 * max(1.0, t):
                records[r] = model.record(r, y)
    recs = [records[min(records, key=lambda x: abs(x - float(r)))] for r in rows]
    return arm_values(world, recs)


# ---------------------------------------------------------------- the documents


def documents(inputs, times, arms, plants, margins, gaps, cut_power, persistence, s_range,
              excursion, allowance):
    lp = inputs["loop"]
    m_min = inputs["power"]["margin"]
    head = dict(registered=lp["registered"], dt_s=inputs["step"]["dt_s"], power_margin=m_min)
    rows_doc = dict(head, kind="cells.fr7_reference_loop_rows@1", rows_s=times, arms={},
                    persistence=persistence, s_range=s_range, excursion=excursion)
    for arm, d in arms.items():
        q = {}
        for k, x in d["values"].items():
            e = dict(cls=d["classes"][k], status=d["status"][k], value=x.tolist(),
                     bound=d["bounds"][k].tolist())
            if k in d["bands"]:
                e["band"] = d["bands"][k].tolist()
                if arm == "clamped":
                    e["F_star_allowance"] = allowance[k].tolist()
            q[k] = e
        rows_doc["arms"][arm] = dict(quantities=q, radau_steps=d["steps"])
    plants_doc = dict(head, kind="cells.fr7_reference_loop_plants@1", plants={},
                      cut_power=cut_power)
    for p, d in plants.items():
        if not d.get("applicable"):
            plants_doc["plants"][p] = d
            continue
        plants_doc["plants"][p] = dict(applicable=True, arm=d["arm"],
                                       values={k: v.tolist() for k, v in d["values"].items()},
                                       margin={k: v.tolist() for k, v in d["margin"].items()})
    zero = dict(head, kind="cells.fr7_reference_loop_zero_power@1",
                inapplicable={p: d["reason"] for p, d in plants.items()
                              if not d.get("applicable")},
                core_rows_without_any_plant=gaps, unaffected={}, rows_without_power={},
                cut_rows_without_power={
                    k: [[times[r], v["margin"][r]] for r in range(len(times))
                        if arms["clamped"]["status"][k][r] == "compared"
                        and v["margin"][r] < m_min]
                    for k, v in cut_power.items()})
    for p, pm in margins.items():
        status = arms[plants[p]["arm"]]["status"]
        kinds = design.zero_power_kinds(p, pm, status, list(pm), m_min)
        zero["unaffected"][p] = {k: float(max(pm[k][r] for r in range(len(times))
                                              if status[k][r] == "compared"))
                                 for k, kd in kinds.items() if kd == "unaffected"}
        zero["rows_without_power"][p] = {
            k: [[times[r], float(pm[k][r])] for r in range(len(times))
                if status[k][r] == "compared" and pm[k][r] < m_min]
            for k, kd in kinds.items() if kd == "rows"}
    return rows_doc, plants_doc, zero


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--calibrate", action="store_true",
                    help="also write loop_calibration.json (about 10 minutes); --check never "
                         "regenerates it")
    args = ap.parse_args(argv)
    inputs = json.loads(loop_worlds.INPUTS.read_text())
    started = time.perf_counter()
    docs, closed = build(inputs)
    if args.calibrate:
        cal = split_calibration(inputs, np.array(inputs["loop"]["rows_s"], dtype=float), closed)
        CALIBRATION_FILE.write_text(json.dumps(dict(
            kind="cells.fr7_reference_loop_calibration@1",
            registered=inputs["loop"]["registered"], steps_s=list(SPLIT_STEPS),
            dt_s=inputs["step"]["dt_s"], quantities=cal,
            note="a Strang split of the regulator, precursor, producer and units around the ions "
                 "and the pump, each sub-flow integrated at rtol 1e-10; its errors at the two "
                 "steps give the order, and e(dt) = e(0.05 s) (dt/0.05 s)^2 the error at 1 ms, "
                 "as a fraction of the closed arm's band at the worst row. Computed once at "
                 "registration; --check does not regenerate it (its cost)"), indent=1) + "\n")
        print(f"wrote {CALIBRATION_FILE}")
    files = (ROWS_FILE, PLANTS_FILE, ZERO_FILE)
    if args.check:
        problems = []
        for path, doc in zip(files, docs, strict=True):
            design._close(json.loads(design.dump(doc)), json.loads(path.read_text()), path.name,
                          problems)
        print(f"check: {len(problems)} differences ({time.perf_counter() - started:.0f} s)")
        for p in problems[:40]:
            print("  ", p)
        return 1 if problems else 0
    for path, doc in zip(files, docs, strict=True):
        path.write_text(design.dump(doc))
        print(f"wrote {path} ({path.stat().st_size} bytes)")
    print(f"loop design: {time.perf_counter() - started:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
