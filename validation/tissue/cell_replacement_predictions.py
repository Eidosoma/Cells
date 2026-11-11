"""Frozen predictions for protocol G2-Q1 (resolved_pump_replacement@1), from the references only.

No engine run. The world definitions are built here and stored, whole, with their
predictions, so the judged run uses exactly these definitions. The predictions come
from validation/tissue/cell_replacement_reference.py (numpy/scipy, no Cells code):

* Q2 (R-ops): each case's first event set applied to the declared initial state.
  Records the slot's post-event amounts and gates, the incident junction gates and
  the bookings (removed, supplied, charge, image charge, free energy).
* Q3 (R-full): W7 and C9 trajectories under each formation rule, recorded every
  0.1 s for 10 s: every cell's Vm, the replaced slots' amounts and gates.
* Q4 (R-fast): the C9 arms under each formation rule, Vm every 0.1 s for 10 s. The
  same cases are run with R-full, and |R-full - R-fast| per record is stored as the
  measured reduction term.

Usage: python -m validation.tissue.cell_replacement_predictions --output FILE
"""

import argparse
import copy
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from validation.stationary import worlds
from validation.tissue import cell_replacement_fixtures as fx
from validation.tissue import cell_replacement_reference as ref
from validation.tissue import surface_pump_v3_fixtures as v3fx

DT = 1e-3
HORIZON = 10.0
RECORDS = [round(0.1 * k, 10) for k in range(101)]
FORMATION = dict(
    literature=dict(fx.FORMATION),
    immediate=dict(fx.FORMATION, initial_abundance=1.0, lag_s=0.0, time_constant_s=40.0),
    short_lag=dict(fx.FORMATION, initial_abundance=0.0, lag_s=1.0, time_constant_s=40.0),
)
T1, T2, T3 = (int(round(t / DT)) * DT for t in (1.0, 2.0, 3.0))


def w7(formation):
    """The seven-cell gated heredity sheet, D centre; swaps, both ends, donor, generation 2."""
    raw = fx.heredity_sheet(1, 0, scale=0.1, dt=DT, end_time=HORIZON)
    raw["experiment"]["observation_times"] = RECORDS
    templates = [
        fx.template_from_cell(raw, "cell_1", "h"),
        fx.template_from_cell(raw, "cell_3", "d"),
    ]
    events = [
        (T1, "cell_0", "d", "w1"),  # H -> D
        (T1, "cell_3", "h", "w2"),  # D -> H, the other end of junction (0, 3)
        (T2, "cell_1", None, "w3", "cell_0"),  # donor copy of the new D carrier
        (T3, "cell_0", "h", "w4"),  # second generation
    ]
    return fx.with_replacement(raw, templates, events, formation=FORMATION[formation])


def c9(arm, formation):
    """A nine-cell chain, ungated junctions, written D segment 3-5; slot 4 renewed at 1 s."""
    states = {k: v[:4] for k, v in v3fx.HEREDITY_STATES.items()}
    written = [states["D"] if 3 <= i <= 5 else states["H"] for i in range(9)]
    edges = [(i, i + 1) for i in range(8)]
    raw = worlds.ionic_background(
        worlds.e07_sheet_definition(written, edges, scale=0.1, gated=False, dt=DT, end_time=HORIZON)
    )
    raw["experiment"]["observation_times"] = RECORDS
    templates = [fx.template_from_cell(raw, "cell_0", "h")]
    event = (T1, "cell_4", "h", "c1") if arm == "isolated" else (T1, "cell_4", None, "c1", "cell_3")
    return fx.with_replacement(raw, templates, [event], formation=FORMATION[formation])


def cases():
    out = {}
    for formation in FORMATION:
        out[f"W7/{formation}"] = w7(formation)
        for arm in ("isolated", "donor"):
            out[f"C9/{arm}/{formation}"] = c9(arm, formation)
    return out


def q2(raw):
    model = ref.ReplacementReference(raw)
    first = min(e["time"] for e in raw["experiment"]["replacement_events"])
    events = [e for e in model.events if e["time"] == first]
    y, booking = model.apply(first, model.ref.initial(), events)
    observed = model.observe(y)
    slots = booking["slots"]
    r = model.ref
    incident = np.isin(r.j_send, slots) | np.isin(r.j_recv, slots)
    gated_rows = [row for row, mem, _ in model.gated if r.mem_cell[mem] in slots]
    return dict(
        event_time_s=first,
        slot_amount_fmol={i: observed["cell_amount_fmol"][i] for i in slots},
        slot_channel_gate=[observed["channel_gate"][row] for row in gated_rows],
        incident_junction_gate=np.asarray(observed["junction_gate"])[incident].tolist(),
        bookings=booking,
    )


def q3(raw):
    model = ref.ReplacementReference(raw)
    states = model.integrate(HORIZON, RECORDS)
    slots = sorted({model.cell_index[e["slot"]] for e in model.events})
    out = []
    for t in RECORDS:
        o = model.observe(states[t])
        out.append(
            dict(
                time_s=t,
                membrane_voltage_V=o["membrane_voltage_V"],
                slot_amount_fmol={i: o["cell_amount_fmol"][i] for i in slots},
            )
        )
    return out


def q4(raw):
    chain = ref.ReducedChain(raw)
    states = chain.integrate(HORIZON, RECORDS)
    return [dict(time_s=t, membrane_voltage_V=states[t].tolist()) for t in RECORDS]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    out = dict(
        kind="cells.cell_replacement_q1_predictions@1",
        scope="Protocol G2-Q1 predictions from the independent references; no engine run",
        records_s=RECORDS,
        formation_rules=FORMATION,
        cases={},
    )
    for name, raw in cases().items():
        t0 = time.perf_counter()
        entry = dict(definition=copy.deepcopy(raw), q2=q2(raw))
        entry["q3_r_full"] = q3(raw)
        if name.startswith("C9/"):
            entry["q4_r_fast"] = q4(raw)
            entry["q4_reduction_term_V"] = [
                float(np.max(np.abs(np.subtract(a["membrane_voltage_V"], b["membrane_voltage_V"]))))
                for a, b in zip(entry["q3_r_full"], entry["q4_r_fast"], strict=True)
            ]
        entry["reference_seconds"] = time.perf_counter() - t0
        out["cases"][name] = entry
        print(name, round(entry["reference_seconds"], 1), "s", flush=True)
    git = ["git", "-C", str(Path(__file__).resolve().parents[2])]
    out.update(
        wall_s=time.perf_counter() - started,
        argv=sys.argv,
        host=platform.node(),
        revision=subprocess.run(
            [*git, "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip(),
        dirty=subprocess.run(
            [*git, "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True
        ).stdout,
    )
    with open(args.output, "x") as f:
        json.dump(out, f, indent=1, default=float)


if __name__ == "__main__":
    main()
