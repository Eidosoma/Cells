"""E07-v1: where each lost D copy and lost founder sat, in the (a) runs (descriptive).

This is a descriptive readout, like e4-losses.json. It covers every (a) run that lost a D
copy or a founder up to its judged record, read as the driver reads it
(validation/tissue/e07_v1_losses.losses). Each loss is classed by where its slot sits:

* interior: in the disc, with all six neighbours in the disc;
* rim: in the disc, with a neighbour outside it;
* stray: outside the disc.

Each loss carries its time, its slot and its D neighbours before and at the loss. A
founder is always interior or rim.

Why it matters: losing a stray shrinks the union in J and raises J (trimming), while losing
a disc slot shrinks the intersection and lowers J. The readout says which kind each run's
losses were. It is reported beside the run's class and never relabels it.

D copies that arrived are given by the same breakdown, as the denominators. The readout was
written after the judged outcomes, outside the frozen scorer, and scores nothing. Its
counts are checked against each outcome's founders_lost and D_copies_lost.

Usage: python -m validation.tissue.e07_v1_dloss --output DIR
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from validation.tissue import e07_v1_losses as readout
from validation.tissue import e07_v1_run as run
from validation.tissue import e07_v1_turnover as e7

POSITIONS = ("interior", "rim", "stray")


def position(slot, inside, neighbours):
    if slot not in inside:
        return "stray"
    return "rim" if any(x not in inside for x in neighbours[slot]) else "interior"


def arrivals(folder, inside, neighbours):
    """D copies arrived before the judged record, by position (the D-loss denominators)."""
    from validation.tissue.heredity_pilot import THRESHOLD_V

    z = np.load(folder / "records.npz")
    plan = json.loads((folder / "plan.json").read_text())
    outcome = json.loads((folder / "outcome.json").read_text())
    t_all, d_all = z["t"], z["vm"] > THRESHOLD_V
    index = {round(float(x), 9): i for i, x in enumerate(t_all)}
    out = dict.fromkeys(POSITIONS, 0)
    for k, slot, donor, *_ in plan["events"]:
        te = int(k) * plan["dt"]
        if donor is None or te >= outcome["judged_s"] - 1e-9 or te > t_all[-1] + 1e-9:
            continue
        if d_all[index[round(te, 9)], int(donor)]:
            out[position(int(slot), inside, neighbours)] += 1
    return out


def run_readout(folder):
    folder = Path(folder)
    outcome = json.loads((folder / "outcome.json").read_text())
    _, _, neighbours = e7.sheet()
    inside = set(e7.disc(outcome["size"]))
    base = readout.losses(folder)
    rows = [dict(r, position=position(r["slot"], inside, neighbours)) for r in base["losses"]]
    tally = {kind: dict.fromkeys(POSITIONS, 0) for kind in ("founder", "D copy")}
    for r in rows:
        tally[r["kind"]][r["position"]] += 1
    return dict(
        run=base["run"],
        run_class=outcome["run_class"],
        delta_J=outcome["delta_J"],
        J_engine=outcome["J_engine"],
        J_null=outcome["J_null"],
        D_loss_fraction=outcome["D_loss_fraction"],
        judged_s=outcome["judged_s"],
        founders_lost_by_position=tally["founder"],
        D_copies_lost_by_position=tally["D copy"],
        D_copies_arrived_by_position=arrivals(folder, inside, neighbours),
        counts_equal_outcome=base["counts_equal_outcome"],
        losses=rows,
    )


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    base = Path(args.output)
    runs = []
    for path in sorted(base.glob("runs/a-*/seed*/outcome.json")):
        o = json.loads(path.read_text())
        if o["label"] == "registered seed" and (o["D_copies_lost"] or o["founders_lost"]):
            runs.append(run_readout(path.parent))
    value = dict(
        kind="cells.e07_v1_loss_positions@1",
        status="descriptive: where each lost D copy and founder sat (interior, rim or stray), "
        "reported beside each run's class and never relabelling it; written after the judged "
        "outcomes, outside the frozen scorer; scores nothing",
        runs=runs,
    )
    run.write_json(base / "loss-positions.json", value)
    for r in runs:
        print(f"{r['run']}: {r['run_class']}, dJ {r['delta_J']:+.3f}; D copies lost "
              f"{r['D_copies_lost_by_position']} of {r['D_copies_arrived_by_position']}; "
              f"founders lost {r['founders_lost_by_position']}; "
              f"counts equal: {r['counts_equal_outcome']}")  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
