"""R-loop's mean-field floor table (D233), registered with the rows:
python -m validation.fr7.references.loop_floor [--check]. Writes
interface/loop_floor_sensitivity_x5.json.

F4's template falls under D150's mean-field floor (10^2 molecules per cell) at T_FLOOR. The
reference runs three cases, each with the closed arm and the cut (clamped) arm at its own F* from
t_d:
1. nominal;
2. the template set to zero from T_FLOOR;
3. the template held at 10^2 molecules from T_FLOOR.

For each judged row the table gives:
- the spread, max - min over the three cases;
- the spread against the registered band;
- the spread against |closed - cut| at that row, on rows after t_d;
- the row where that last ratio is largest, and its value at the horizon.
"""

import argparse
import json
import sys

import numpy as np

from validation.fr7.references import loop, loop_design, loop_worlds

T_FLOOR = 289.3  # s: the x5 template's 10^2 molecules in 7.505 fL (289.29 s; D233)
FLOOR_FILE = loop_worlds.IFACE / "loop_floor_sensitivity_x5.json"


def table(inputs, rows_doc, t_floor=T_FLOOR):
    lp = inputs["loop"]
    rows = np.array(lp["rows_s"], dtype=float)
    times = [float(t) for t in rows]
    t_d = lp["arms"]["t_d_s"]
    i_d = times.index(t_d)
    hundred = 100.0 / (inputs["constants"]["avogadro_per_mol"] * 1e-15)
    L = loop.LoopVariant
    cases = {"nominal": {}, "zero": dict(template_hold_from_s=t_floor, template_hold_fmol=0.0),
             "held_100_molecules": dict(template_hold_from_s=t_floor,
                                        template_hold_fmol=hundred)}
    vals = {}
    for name, kw in cases.items():
        w = loop.LoopWorld(inputs, L("closed_" + name, **kw))
        rc, _ = loop.simulate(w, rows)
        Fs = rc[i_d]["F_loop"]
        wc = loop.LoopWorld(inputs, L("clamped_" + name, clamp_from_s=t_d, clamp_value=Fs,
                                      **kw))
        rk, _ = loop.simulate(wc, rows)
        vals[name] = dict(closed=loop_design.arm_values(w, rc),
                          clamped=loop_design.arm_values(wc, rk), F_star=Fs)
    nominal_world = loop.LoopWorld(inputs)
    out = dict(kind="cells.fr7_reference_loop_floor@1", registered=lp["registered"],
               ruling="D233", t_floor_s=t_floor, hundred_molecules_fmol=hundred,
               template_molecules_at_t_floor=float(nominal_world.template_amount(t_floor)
                                                   * inputs["constants"]["avogadro_per_mol"]
                                                   * 1e-15),
               F_star={c: v["F_star"] for c, v in vals.items()}, quantities={})
    for arm in ("closed", "clamped"):
        for k, e in rows_doc["arms"][arm]["quantities"].items():
            if "band" not in e:
                continue
            judged = [r for r in range(len(times)) if e["status"][r] == "compared"]
            if not judged:
                continue
            stack = np.array([vals[c][arm][k] for c in cases])
            spread = stack.max(axis=0) - stack.min(axis=0)
            band = np.array(e["band"])
            cut = np.abs(vals["nominal"]["closed"][k] - vals["nominal"]["clamped"][k])
            sb = np.array([spread[r] / band[r] for r in judged])
            # the clamp moves no material: the total's closed-minus-cut is rounding, no ratio
            after = ({} if k == "total_fmol" else
                     {r: spread[r] / cut[r] for r in judged if times[r] > t_d and cut[r] > 0})
            r_sc = max(after, key=after.get) if after else None
            end = len(times) - 1
            out["quantities"][f"{arm}/{k}"] = dict(
                rows=len(judged), max_spread_over_band=float(sb.max()),
                at_s=times[judged[int(np.argmax(sb))]],
                max_spread_over_cut=float(after[r_sc]) if after else None,
                max_over_cut_at_s=times[r_sc] if after else None,
                over_cut_at_horizon=(float(spread[end] / cut[end]) if end in after else None),
                per_row=[dict(t=times[r], spread=float(spread[r]), band=float(band[r]),
                              closed_minus_cut=float(cut[r]) if times[r] > t_d else None)
                         for r in judged])
    cut_rows = [d for d in out["quantities"].values() if d["max_spread_over_cut"] is not None]
    out["summary"] = dict(
        max_spread_over_cut_any_row=max(d["max_spread_over_cut"] for d in cut_rows),
        max_spread_over_cut_at_horizon=max(d["over_cut_at_horizon"] for d in cut_rows
                                           if d["over_cut_at_horizon"] is not None),
        max_spread_over_band=max(d["max_spread_over_band"] for k, d in out["quantities"].items()
                                 if not k.endswith("F_T")),
        F_star_spread=max(out["F_star"].values()) - min(out["F_star"].values()),
        note="the material total has no cut ratio: the clamp moves no material, so its "
             "closed-minus-cut difference is rounding")
    return out


def compare(fresh, stored):
    """Spreads are differences between runs, so their last digits carry the runs' noise: each
    row's spread to 1e-3 of its band, ratios to 1e-2 absolute plus 1e-3 relative, F* to 1e-12,
    and the rows and times exactly."""
    problems = []
    if set(fresh["quantities"]) != set(stored["quantities"]):
        return ["quantities differ"]
    for k, a in fresh["quantities"].items():
        b = stored["quantities"][k]
        if [r["t"] for r in a["per_row"]] != [r["t"] for r in b["per_row"]]:
            problems.append(f"{k}: rows differ")
            continue
        for ra, rb in zip(a["per_row"], b["per_row"], strict=True):
            if abs(ra["spread"] - rb["spread"]) > 1e-3 * rb["band"]:
                problems.append(f"{k} at {ra['t']}: spread")
        for key in ("max_spread_over_band", "max_spread_over_cut", "over_cut_at_horizon"):
            x, y = a[key], b[key]
            if (x is None) != (y is None) or (x is not None and abs(x - y) > 1e-2 + 1e-3 * abs(y)):
                problems.append(f"{k}: {key}")
    for c, v in fresh["F_star"].items():
        if abs(v - stored["F_star"][c]) > 1e-12:
            problems.append(f"F* {c}")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    inputs = json.loads(loop_worlds.INPUTS.read_text())
    rows_doc = json.loads(loop_design.ROWS_FILE.read_text())
    fresh = table(inputs, rows_doc)
    if args.check:
        problems = compare(fresh, json.loads(FLOOR_FILE.read_text()))
        print(f"floor table: {len(problems)} differences")
        for p in problems[:20]:
            print("  ", p)
        return 1 if problems else 0
    FLOOR_FILE.write_text(json.dumps(fresh, indent=1) + "\n")
    print(f"wrote {FLOOR_FILE}")
    print(json.dumps(fresh["summary"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
