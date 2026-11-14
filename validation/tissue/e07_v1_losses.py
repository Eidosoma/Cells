"""E07-v1, item E4: every loss in the (c) controls with its time and neighbourhood.

This is a descriptive readout. The registered E4 item reports "any loss ... with its time and
neighbourhood". It reads each (c) run's records.npz, plan.json and outcome.json the way the
driver reads them (validation/tissue/e07_v1_run.reading):
* D means Vm above the U state;
* a founder is lost when it is H at any record up to its first replacement or the judged
  record;
* a D copy is lost when it is H at any record of its life up to the judged record.

For each loss it gives:
* the slot, and whether it was a founder or a D copy;
* the first H record;
* the slot's ring, and whether it is a rim slot (a neighbour outside the disc);
* its D neighbours at the record before the loss and at the loss record.

It was written after the judged outcomes existed and lives outside the frozen scorer
(validation/tissue/e07_v1_score.py). It scores nothing and changes no score. Its counts are
checked against the outcome's founders_lost and D_copies_lost.

Usage: python -m validation.tissue.e07_v1_losses --output DIR
"""

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

from validation.stationary import worlds
from validation.tissue import e07_v1_run as run
from validation.tissue import e07_v1_turnover as e7


def losses(folder):
    from validation.tissue.heredity_pilot import THRESHOLD_V

    folder = Path(folder)
    z = np.load(folder / "records.npz")
    plan = json.loads((folder / "plan.json").read_text())
    outcome = json.loads((folder / "outcome.json").read_text())
    t_all, d_all = z["t"], z["vm"] > THRESHOLD_V
    judged, dt = outcome["judged_s"], plan["dt"]
    cells, _, neighbours = e7.sheet()
    inside = sorted(e7.disc(plan["size"]))
    events = [(int(k) * dt, int(slot), None if donor is None else int(donor))
              for k, slot, donor, *_ in plan["events"]]  # fmt: skip
    births = {}
    for te, slot, _ in events:
        births.setdefault(slot, []).append(te)
    index = {round(float(x), 9): i for i, x in enumerate(t_all)}

    def describe(slot, kind, start, until):
        window = np.flatnonzero((t_all > start + 1e-9) & (t_all <= until + 1e-9))
        h = [i for i in window if not d_all[i, slot]]
        if not h:
            return None
        i = h[0]
        before = window[window < i]
        j = int(before[-1]) if len(before) else int(np.searchsorted(t_all, start + 1e-9) - 1)
        nb = neighbours[slot]
        return dict(slot=slot, kind=kind, since_s=float(start), lost_at_s=float(t_all[i]),
                    ring=int(worlds.ring(cells[slot])),
                    rim=bool(any(x not in inside for x in nb)),
                    d_neighbours_before=int(d_all[j, nb].sum()),
                    d_neighbours_at_loss=int(d_all[i, nb].sum()), neighbours=len(nb))  # fmt: skip

    rows = []
    for cell in inside:
        first = min(births.get(cell, [math.inf]))
        r = describe(cell, "founder", 0.0, min(first, judged))
        if r:
            rows.append(r)
    for te, slot, donor in events:
        if donor is None or te >= judged - 1e-9 or te > t_all[-1] + 1e-9:
            continue
        if not d_all[index[round(te, 9)], donor]:
            continue  # An H copy, not a D copy.
        later = [x for x in births[slot] if x > te]
        r = describe(slot, "D copy", te, min(later[0] if later else math.inf, judged))
        if r:
            rows.append(r)
    rows.sort(key=lambda r: r["lost_at_s"])
    counts = dict(founders=sum(r["kind"] == "founder" for r in rows),
                  D_copies=sum(r["kind"] == "D copy" for r in rows))  # fmt: skip
    return dict(run=f"{outcome['arm']}/seed{outcome['seed']}", judged_s=judged, losses=rows,
                counts=counts,
                counts_equal_outcome=counts == dict(founders=outcome["founders_lost"],
                                                    D_copies=outcome["D_copies_lost"]))  # fmt: skip


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    base = Path(args.output)
    value = dict(
        kind="cells.e07_v1_e4_losses@1",
        status="descriptive: E4's registered readout (each loss with its time and "
        "neighbourhood); written after the judged outcomes, outside the frozen scorer; scores "
        "nothing",
        runs=[losses(p) for p in sorted(base.glob("runs/c-disconly-*/seed*"))],
    )
    run.write_json(base / "e4-losses.json", value)
    for r in value["runs"]:
        print(r["run"], r["counts"], "equal to outcome:", r["counts_equal_outcome"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
