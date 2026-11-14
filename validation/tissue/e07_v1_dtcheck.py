"""E07-v1 development check: the s 1.0 control's collective falls at dt = 1 ms.

This is a labelled development run and changes no verdict. E1's segments did not cover the
(c) control, and a collective fall is a threshold event, so this check reruns its first
600 s at a finer step.

* run --dt DT: c-disconly-fast-k1-d37-s1.0 at seed 1 for 0-600 s.
  - It uses the judged run's own schedule, with event times on the 5 ms grid as E1 does.
  - Records are taken every 2 s.
  - It goes through the frozen driver's own functions:
    validation/tissue/e07_v1_run.schedule and build,
    heredity_turnover_literature.Stepper and run_segments.
  - It is run with PYTHONPATH on the frozen execution snapshot, so the engine and driver are
    that snapshot's.
* compare --judged RUN_DIR: reads the judged 5 ms run's records and this check's records.
  - The falls: cells going from D to H between consecutive records, with founders and D
    copies kept apart and replaced slots excluded. They are counted at 10 s resolution, the
    judged run's, and at each check's own 2 s resolution.
  - J against the disc at the common 10 s records, and the cells whose D state differs.
  - |dVm| at the common records.

Usage: python PATH/e07_v1_dtcheck.py run --dt 0.001 --output DIR
       python PATH/e07_v1_dtcheck.py compare --judged RUN_DIR --output DIR
"""

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

ARM, SEED, END_S, EVERY_S, GRID_DT = "c-disconly-fast-k1-d37-s1.0", 1, 600.0, 2.0, 0.005
LABEL = "development check (dt study of a judged run's first 600 s); changes no verdict"


def paths(output, dt):
    stem = f"dtcheck-dt{dt:g}"
    return Path(output) / f"{stem}.npz", Path(output) / f"{stem}.json"


def part_run(args):
    from cells.core.specs import parse_spec
    from validation.tissue import e07_v1_run as run

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    arm = run.find_arm(ARM)
    record = run.schedule(arm, SEED, dt=args.dt, end_s=END_S, grid_dt=GRID_DT)
    raw, checks = run.build(record)
    h = run.lit()
    spec = parse_spec(raw)
    layout = h.layout_check(spec, record["size"], record["s"])
    checks["layout_equals_sheet70"] = all(v == 0.0 for v in layout.values())
    tick = time.perf_counter()
    stepper = h.Stepper(spec)
    every = int(round(EVERY_S / args.dt))
    end = int(round(END_S / args.dt))
    marks = sorted(set(range(every, end + 1, every)) | {k for k, *_ in record["events"]} | {end})
    volume = np.asarray(stepper.host_p.volume)[: stepper.n]
    first = stepper.measure(0)
    first.update(t=0.0, regular=True, conc=first["amounts"][:3] / volume,
                 osm=first["amounts"].sum(axis=0) / volume)  # fmt: skip
    records = [first]
    k_end, refusal, worst = h.run_segments(stepper, marks, every=every, records=records)
    npz, meta = paths(out, args.dt)
    h.save_records(npz, records)
    run.write_json(meta, dict(
        label=LABEL, arm=ARM, seed=SEED, dt=args.dt, grid_dt=GRID_DT, end_s=END_S,
        every_s=EVERY_S, end_step=k_end, refusal=refusal, checks=checks,
        events=[[int(k), int(slot), None if d is None else int(d)]
                for k, slot, d, *_ in record["events"]],
        wall_s=time.perf_counter() - tick,
        ms_per_step=1e3 * (time.perf_counter() - tick) / max(k_end, 1),
        worst_device_diagnostics=None if worst is None else dict(
            zip(h.model.DEVICE_DIAGNOSTICS, worst.tolist(), strict=True)),
        provenance=h.provenance()))  # fmt: skip
    print(f"dt {args.dt}: end {k_end * args.dt} s, refusal {refusal}")
    return 0 if refusal is None else 3


def falls(t, d, ev, founders, inside, until):
    """Per interval of consecutive records to `until`: founders and D copies from D to H
    (slots replaced in the interval excluded)."""
    first_event = {}
    for te, slot in ev:
        first_event.setdefault(slot, te)
    out = []
    for i in range(1, len(t)):
        if t[i] > until + 1e-9:
            break
        replaced = {slot for te, slot in ev if t[i - 1] - 1e-9 <= te <= t[i] + 1e-9}
        cells = [int(c) for c in np.flatnonzero(d[i - 1] & ~d[i]) if int(c) not in replaced]
        if not cells:
            continue
        f = [c for c in cells if c in founders and first_event.get(c, math.inf) > t[i]]
        out.append(dict(at_s=float(t[i]), founders=len(f),
                        others=len(cells) - len(f), in_disc=sum(c in inside for c in cells),
                        cells=cells))  # fmt: skip
    return out


def part_compare(args):
    from validation.tissue import e07_v1_run as run
    from validation.tissue import e07_v1_turnover as e7
    from validation.tissue.heredity_pilot import THRESHOLD_V

    out = Path(args.output)
    judged = Path(args.judged)
    plan = json.loads((judged / "plan.json").read_text())
    inside = set(e7.disc(plan["size"]))
    sets = {}
    z = np.load(judged / "records.npz")
    sets["judged 5 ms"] = dict(t=z["t"][z["regular"]], vm=z["vm"][z["regular"]])
    for dt in (0.005, 0.001):
        npz, meta = paths(out, dt)
        if npz.exists():
            y = np.load(npz)
            sets[f"check {dt * 1e3:g} ms"] = dict(t=y["t"][y["regular"]], vm=y["vm"][y["regular"]],
                                                  meta=json.loads(meta.read_text()))  # fmt: skip
    ev = [(int(k) * plan["dt"], int(slot)) for k, slot, *_ in plan["events"]]
    ev = [(te, slot) for te, slot in ev if te < END_S]
    same_events = {}
    for name, s in sets.items():
        if "meta" in s:
            mine = [(int(k) * s["meta"]["dt"], int(slot)) for k, slot, _ in s["meta"]["events"]]
            same_events[name] = len(mine) == len(ev) and all(
                abs(a - b) < 1e-9 and x == y for (a, x), (b, y) in zip(mine, ev, strict=True)
            )
    result = dict(label=LABEL, events_equal_judged=same_events, sets={})
    ten = None
    for name, s in sets.items():
        t, d = s["t"], s["vm"] > THRESHOLD_V
        keep = (np.abs(t / 10.0 - np.round(t / 10.0)) < 1e-6) & (t <= END_S + 1e-9)
        own = falls(t, d, ev, inside, inside, END_S)
        at10 = falls(t[keep], d[keep], ev, inside, inside, END_S)
        jac = []
        for row in d[keep]:
            dset = set(np.flatnonzero(row).tolist())
            jac.append(len(dset & inside) / len(dset | inside) if dset | inside else 1.0)
        result["sets"][name] = dict(
            falls_10s=[f for f in at10 if f["founders"] + f["others"] >= 1],
            falls_own_resolution=[f for f in own if f["founders"] + f["others"] >= 1],
            J_10s=dict(t_s=t[keep].tolist(), J=jac),
            ms_per_step=s.get("meta", {}).get("ms_per_step"),
            refusal=s.get("meta", {}).get("refusal"),
        )
        if name == "judged 5 ms":
            ten = dict(t=t[keep], d=d[keep], vm=s["vm"][keep])
    for name, s in sets.items():
        if name == "judged 5 ms":
            continue
        t = s["t"]
        keep = (np.abs(t / 10.0 - np.round(t / 10.0)) < 1e-6) & (t <= END_S + 1e-9)
        tc, vc = t[keep], s["vm"][keep]
        common = sorted(set(np.round(tc, 6)) & set(np.round(ten["t"], 6)))
        ic = [int(np.flatnonzero(np.abs(tc - x) < 1e-6)[0]) for x in common]
        ij = [int(np.flatnonzero(np.abs(ten["t"] - x) < 1e-6)[0]) for x in common]
        dc, dj = vc[ic] > THRESHOLD_V, ten["d"][ij]
        diff = [dict(t_s=float(common[n]), cells=np.flatnonzero(dc[n] != dj[n]).tolist())
                for n in range(len(common)) if (dc[n] != dj[n]).any()]  # fmt: skip
        jc = result["sets"][name]["J_10s"]["J"]
        jj = result["sets"]["judged 5 ms"]["J_10s"]["J"]
        result["sets"][name]["against_judged"] = dict(
            common_10s_records=len(common),
            records_with_D_difference=len(diff), D_differences=diff,
            max_abs_J_difference=float(max(abs(a - b) for a, b in zip(jc, jj, strict=False))),
            max_abs_vm_difference_mV=float(1e3 * np.abs(vc[ic] - ten["vm"][ij]).max()),
        )  # fmt: skip
    run.write_json(out / "dtcheck-compare.json", result)
    for name, s in result["sets"].items():
        big = [(f["at_s"], f["founders"], f["others"]) for f in s["falls_10s"]
               if f["founders"] + f["others"] >= 5]  # fmt: skip
        print(
            name,
            "collective falls (10 s):",
            big,
            s.get("against_judged", {}).get("max_abs_J_difference"),
        )
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("part", choices=["run", "compare"])
    parser.add_argument("--output", required=True)
    parser.add_argument("--dt", type=float)
    parser.add_argument("--judged")
    args = parser.parse_args(argv)
    return part_run(args) if args.part == "run" else part_compare(args)


if __name__ == "__main__":
    sys.exit(main())
