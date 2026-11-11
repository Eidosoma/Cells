"""Full-size dry-run inputs for the G2-Q1 judge (development; nothing registered is compared).

Writes, into --output: predictions.json, protocol.json and parameters.json for
`cell_replacement_judge --predictions ... --protocol ... --parameters ...`, so the whole
judged driver runs end to end at full size (10 s horizons, 0.1 s records, the 825-node
Q7 world and the 127-cell W37 world) on NON-registered inputs:

* the same nine case names (Q5 and Q6 select cases by name) with different slots and
  event times: W7 events at 1.5, 2.5 and 3.5 s on cells 2, 5, 6 (a donor copy of the
  D centre) and 2 again; C9 slot 3 (not 4) at 1.5 s, donor cell 4;
* Q2 predictions from R-ops and Q4 predictions from R-fast (real references, so the
  data paths are exercised); Q3 predictions with the registered structure but
  placeholder values (R-full is slow and the values are not judged here);
* placeholder pinned tolerances (1 V, 1e3 fmol): dry-run verdicts of Q3 and Q4 mean
  nothing; Q1, Q2, Q5, Q6 and Q7 verdicts are real engine checks on these inputs;
* W37 with other slots (rim cells 2 and 3, interior cell 1) at step 300, and the
  Q7 world with channel permeabilities x 1.05.

The worlds have no random draws, so there is no seed to vary.

Usage: python -m validation.tissue.cell_replacement_dryrun --output DIR
"""

import argparse
import json
from pathlib import Path

from validation.tissue import cell_replacement_fixtures as fx
from validation.tissue import cell_replacement_predictions as pr
from validation.tissue import cell_replacement_reference as ref

T = {k: int(round(k / pr.DT)) * pr.DT for k in (1.5, 2.5, 3.5)}


def w7(formation):
    raw = fx.heredity_sheet(1, 0, scale=0.1, dt=pr.DT, end_time=pr.HORIZON)
    raw["experiment"]["observation_times"] = pr.RECORDS
    templates = [
        fx.template_from_cell(raw, "cell_1", "h"),
        fx.template_from_cell(raw, "cell_3", "d"),
    ]
    events = [
        (T[1.5], "cell_2", "d", "x1"),
        (T[1.5], "cell_5", "h", "x2"),  # Junction (2, 5): both ends at once.
        (T[2.5], "cell_6", None, "x3", "cell_3"),
        (T[3.5], "cell_2", "h", "x4"),
    ]
    return fx.with_replacement(raw, templates, events, formation=pr.FORMATION[formation])


def c9(arm, formation):
    raw = pr.c9(arm, formation)
    event = raw["experiment"]["replacement_events"][0]
    event.update(time=T[1.5], slot="cell_3")
    if arm == "donor":
        event["donor"] = "cell_4"
    return raw


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    cases, pinned = {}, {}
    for formation in pr.FORMATION:
        defs = {f"W7/{formation}": w7(formation)}
        for arm in ("isolated", "donor"):
            defs[f"C9/{arm}/{formation}"] = c9(arm, formation)
        for name, raw in defs.items():
            slots = sorted({e["slot"] for e in raw["experiment"]["replacement_events"]})
            order = {c["id"]: i for i, c in enumerate(raw["model"]["cells"])}
            entry = dict(definition=raw, q2=pr.q2(raw))
            entry["q3_r_full"] = [
                dict(
                    time_s=t,
                    membrane_voltage_V=[-0.08] * len(raw["model"]["cells"]),
                    slot_amount_fmol={order[s]: [0.0] * 4 for s in slots},
                )
                for t in pr.RECORDS
            ]
            pinned[name] = dict(
                q3_membrane_voltage_V=dict(tolerance=1.0, unit="V"),
                q3_slot_amount_fmol=dict(tolerance=1e3, unit="fmol"),
            )
            if name.startswith("C9/"):
                chain = ref.ReducedChain(raw)
                states = chain.integrate(pr.HORIZON, pr.RECORDS)
                entry["q4_r_fast"] = [
                    dict(time_s=t, membrane_voltage_V=states[t].tolist()) for t in pr.RECORDS
                ]
                pinned[name]["q4_membrane_voltage_V"] = dict(tolerance=1.0, unit="V")
            cases[name] = entry
            print(name, flush=True)
    predictions = dict(kind="cells.cell_replacement_q1_dryrun_predictions@1", cases=cases)
    protocol = dict(
        kind="cells.cell_replacement_q1_dryrun_protocol@1",
        pinned_tolerances=dict(note="placeholders for the dry run", cases=pinned),
    )
    parameters = dict(w37_rim=[2, 3], w37_inner=1, w37_step=300, q7_channel_scale=1.05)
    for name, value in (
        ("predictions", predictions),
        ("protocol", protocol),
        ("parameters", parameters),
    ):
        with open(args.output / f"{name}.json", "x") as f:
            json.dump(value, f, indent=1, default=float)


if __name__ == "__main__":
    main()
