#!/usr/bin/env python3
"""Write the synthetic run folder that the adapter's test reads.

    python3 tools/make_run_fixture.py            # writes tests/fixtures/run-small/

It has the layout and file shapes of an E07-v1 evidence folder (runs/<arm>/seedN with
definition.json, plan.json, outcome.json, result.json and records.npz, a summary.json and
a small source snapshot), but every number in it is invented here: a 19-cell hexagonal
sheet, nine records, three replacements. No engine ran, and nothing in it is evidence.

The same call always writes the same bytes. Standard library only.
"""

from __future__ import annotations

import json
import math
import struct
import sys
import zipfile
from array import array
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "tests" / "fixtures" / "run-small"
EXPERIMENT, ARM, SEED = "synthetic-sheet", "synthetic-s1.0", 1
SYNTHETIC = "synthetic fixture"
DIRECTIONS = ((1, 0), (0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1))
RADIUS, DISC_RING = 2, 1
DT, RECORD_S, END_S = 0.005, 10.0, 60.0
H_V, U_V, D_V = -0.0796, -0.0394, -0.0215  # resting, threshold and written voltages of the fixture
LAG_S, TAU_S = 5.0, 15.0


def npy(descr, shape, values):
    """The bytes of a version 1.0 .npy file."""
    header = "{'descr': '%s', 'fortran_order': False, 'shape': %s, }" % (descr, "(%s,)" % shape[0] if len(shape) == 1 else str(tuple(shape)))
    header += " " * (-(10 + len(header) + 1) % 64) + "\n"
    code = {"<f8": "d", "<i8": "q", "|b1": "B"}[descr]
    data = array(code, values)
    if sys.byteorder == "big" and data.itemsize > 1:
        data.byteswap()
    return b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header.encode("latin1") + data.tobytes()


def write_npz(path, arrays):
    # Compressed, as numpy.savez_compressed writes it, to keep the fixture to a few kilobytes.
    # A real run's records.npz is stored uncompressed; the reader takes both the same way.
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in arrays.items():
            archive.writestr(zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0)), raw, zipfile.ZIP_DEFLATED, 9)


def write_json(path, data, indent=1):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=indent) + "\n", encoding="utf-8")


def ring(site):
    q, r = site
    return max(abs(q), abs(r), abs(q + r))


def main():
    # ---- the sheet: 19 cells in a scrambled order, so nothing can lean on the numbering
    sites = [(q, r) for q in range(-RADIUS, RADIUS + 1) for r in range(-RADIUS, RADIUS + 1) if ring((q, r)) <= RADIUS]
    sites.sort(key=lambda site: ((site[0] * 7 + site[1] * 13) % 19, site))
    index = {site: number for number, site in enumerate(sites)}
    cells = [f"cell_{number}" for number in range(len(sites))]
    pairs = sorted({tuple(sorted((index[site], index[(site[0] + dq, site[1] + dr)]))) for site in sites for dq, dr in DIRECTIONS if (site[0] + dq, site[1] + dr) in index})
    # Every other junction is written receiver first: the sheet is undirected.
    junctions = [{"id": f"junction_{number}", "sender": cells[b if number % 2 else a], "receiver": cells[a if number % 2 else b]} for number, (a, b) in enumerate(pairs)]
    disc = sorted(number for site, number in index.items() if ring(site) <= DISC_RING)
    centre = index[(0, 0)]
    neighbours = {number: sorted(index[(q + dq, r + dr)] for dq, dr in DIRECTIONS if (q + dq, r + dr) in index) for (q, r), number in index.items()}

    # ---- the schedule: three replacements of disc cells by a disc neighbour
    order = [disc[1], disc[3], disc[5]]
    steps = [2757, 4000, 8271]  # 13.785 s, 20 s (on the record grid) and 41.355 s
    events = []
    for number, (step, slot) in enumerate(zip(steps, order)):
        donor = next(cell for cell in neighbours[slot] if cell in disc and cell != slot)
        events.append((step, slot, donor, f"n{number}"))
    every, end = round(RECORD_S / DT), round(END_S / DT)
    marks = sorted({0} | set(range(every, end + 1, every)) | {step for step, *_ in events} | {end})
    times = [step * DT for step in marks]
    regular = [step % every == 0 for step in marks]
    fallen = order[2]  # this copy falls from D to H after its replacement

    vm, generation, abundance, gate, conc, osm, valid = [], [], [], [], [], [], []
    for step, t in zip(marks, times):
        row = []
        for cell in range(len(cells)):
            level = D_V if cell in disc else H_V
            if cell == fallen and t > 45.0:
                level = H_V
            row.append(level + 1e-5 * cell + 2e-6 * t)
        vm += row
        # A record at an event's time is taken before the event, so a replacement shows in later records.
        generation += [sum(1 for event_step, slot, *_ in events if slot == cell and event_step < step) for cell in range(len(cells))]
        for a, b in pairs:
            born = max((event_step * DT for event_step, slot, *_ in events if slot in (a, b) and event_step < step), default=None)
            abundance.append(1.0 if born is None else max(0.0, 1.0 - math.exp(-(t - born - LAG_S) / TAU_S)) if t > born + LAG_S else 0.0)
            gate.append(1.0)
        conc += [value + 0.01 * cell for value in (8.0, 140.0, 20.0) for cell in range(len(cells))]
        osm += [300.0 + 0.1 * cell for cell in range(len(cells))]
        valid.append(not math.isclose(t, 41.355))  # one record marked not valid, to exercise the flag
    count, n, j = len(marks), len(cells), len(pairs)

    run = OUT / "runs" / ARM / f"seed{SEED}"
    run.mkdir(parents=True, exist_ok=True)
    write_npz(
        run / "records.npz",
        {
            "t": npy("<f8", (count,), times),
            "vm": npy("<f8", (count, n), vm),
            "conc": npy("<f8", (count, 3, n), conc),
            "osm": npy("<f8", (count, n), osm),
            "abundance": npy("<f8", (count, j), abundance),
            "gate": npy("<f8", (count, j), gate),
            "generation": npy("<i8", (count, n), generation),
            "regular": npy("|b1", (count,), regular),
            "valid": npy("|b1", (count,), valid),
        },
    )
    write_json(
        run / "definition.json",
        {
            "schema_version": 1,
            "note": f"{SYNTHETIC}: not a Cells definition",
            "model": {
                "id": "synthetic_sheet@0",
                "cells": [{"id": cell, "volume_pL": 0.75} for cell in cells],
                "junctions": junctions,
            },
            "experiment": {
                "end_time": END_S,
                "replacement_events": [
                    {"time": round(step * DT, 9), "slot": cells[slot], "newcomer": "donor_copy", "template": None, "donor": cells[donor], "carrier_id": label}
                    for step, slot, donor, label in events
                ],
            },
            "execution": {"dt": DT},
        },
        indent=None,
    )
    write_json(
        run / "plan.json",
        {
            "arm": ARM, "seed": SEED, "label": SYNTHETIC, "group": "control", "size": len(disc), "s": 1.0, "kind": "donor",
            "scope": "disc", "rule": "disc_neighbour", "formation": {"lag_s": LAG_S, "time_constant_s": TAU_S}, "residence_s": 30.0,
            "registered_end_s": END_S, "planned_end_s": END_S, "judged_at": "end", "dt": DT, "grid_dt": DT, "interval_s": 13.785,
            "turnover_complete_s": [41.355], "permutation": [disc[1], disc[3], disc[5], disc[0], disc[2], disc[4], disc[6]],
            "events": [[step, slot, donor, label] for step, slot, donor, label in events],
        },
    )  # fmt: skip
    status = f"supplementary: {SYNTHETIC} wording; not judged"
    outcome = {
        "kind": "synthetic.run_outcome@0", "arm": ARM, "seed": SEED, "label": SYNTHETIC, "group": "control", "s": 1.0, "size": len(disc),
        "stop": "planned end", "refusal": None, "judged_target_s": END_S, "judged_s": END_S, "basis": "record",
        "J_engine": (len(disc) - 1) / len(disc), "J_null": 1.0, "delta_J": -1 / len(disc), "delta": 2 / len(disc),
        "delta_J_over_records": {"status": status, "mean": -0.05, "min": -1 / len(disc), "max": 0.0, "nonzero_records": 2, "records": 6},
        "D_copies": 3, "D_copies_lost": 1, "D_loss_fraction": 1 / 3, "H_copies": 0, "H_copies_converted": 0, "recruitment_fraction": None,
        "founders_lost": 0, "d_outside_max": 0, "run_class": "erosion",
    }  # fmt: skip
    write_json(run / "outcome.json", outcome)
    write_json(
        run / "result.json",
        {
            "arm": ARM, "seed": SEED, "label": SYNTHETIC, "engine_models": [f"none ({SYNTHETIC}: no engine ran)"], "dt": DT, "end_step": end,
            "end_s": END_S, "planned_end_s": END_S, "stop": "planned end", "refusal": None, "records": count,
            # A real result.json carries a host name and machine paths here. The adapter must copy neither.
            "provenance": {"argv": ["/home/nobody/checkout/validation/driver.py", "run"], "host": "fixture-host-01", "revision": None, "source": "/mnt/nowhere/snapshot/validation/driver.py"},
        },
    )  # fmt: skip
    write_json(
        OUT / "summary.json",
        {
            "kind": "synthetic.summary@0",
            "runs": {f"{ARM}/seed{SEED}": {key: outcome[key] for key in ("label", "group", "s", "size", "stop", "judged_s", "delta_J", "run_class")}},
            "supplementary_readouts": {"delta_J_over_records": status},
        },
    )

    # ---- the catalogue entry and the selection the test passes to the adapter
    write_json(
        OUT / "overlay.json",
        {
            "format": "cells.visualizer.replay_overlay@1",
            "note": f"{SYNTHETIC}: labels for the adapter's test only.",
            "experiments": {
                EXPERIMENT: {
                    "adapter": "e07-v1",
                    "label": "Synthetic sheet (test fixture)",
                    "plain": "Invented numbers in the layout of an E07-v1 run folder. No engine ran; nothing here is evidence.",
                    "sources": [],
                    "engine_entities": [],
                    "groups": {"control": {"label": "Synthetic control", "plain": "Three disc cells are replaced by a disc neighbour."}},
                    "classes": [{"id": "erosion", "label": "Erosion", "description": "Synthetic wording."}],
                    "regions": {"disc": {"label": "The disc", "plain": "The cells that start at the written voltage."}},
                    "records": {"vm": {"label": "Membrane voltage"}, "junction_abundance": {"label": "Junction abundance"}},
                    "events": {"replacement": {"label": "Replacement"}},
                    "parameters": {"size": {"label": "Disc size", "unit": "cells"}, "s": {"label": "Coupling"}, "scope": {"label": "Cells replaced"}, "formation.lag_s": {"label": "Formation lag", "unit": "s"}, "not_in_the_plan": {"label": "Absent"}},
                    "readouts": {
                        "judged_s": {"label": "Judged record", "unit": "s"},
                        "delta_J": {"label": "Delta J"},
                        "recruitment_fraction": {"label": "Recruitment fraction"},
                        "delta_J_over_records.mean": {"label": "Delta J over the records, mean"},
                        "not_in_the_outcome": {"label": "Absent"},
                    },
                }
            },
        },
    )
    write_json(OUT / "selection.json", {"note": SYNTHETIC, EXPERIMENT: {"evidence_folder": OUT.name, "runs": [f"{ARM}/seed{SEED}"]}})

    # ---- a source snapshot of three lines, in the shape the adapter reads constants from
    tissue = OUT / "snapshot" / "validation" / "tissue"
    tissue.mkdir(parents=True, exist_ok=True)
    header = "# Synthetic test fixture for the visualizer's run adapter. Not Cells code.\n"
    (tissue / "surface_pump_v3_fixtures.py").write_text(header + f"HEREDITY_STATES = dict(H=({H_V}, 1.0), U=({U_V}, 2.0), D=({D_V}, 3.0))\n")
    (tissue / "heredity_pilot.py").write_text(header + "from validation.tissue import surface_pump_v3_fixtures as fixtures\n\nTHRESHOLD_V = fixtures.HEREDITY_STATES[\"U\"][0]\n")
    (tissue / "e07_v1_turnover.py").write_text(header + f"RECORD_S = {RECORD_S}\n")
    (tissue / "e07_v1_run.py").write_text(
        header + "def part_analyse(z):\n    from validation.tissue.heredity_pilot import THRESHOLD_V\n\n    return z[\"vm\"] > THRESHOLD_V\n"
    )
    write_json(
        OUT / "snapshot" / "SNAPSHOT.json",
        # A real snapshot manifest also names the checkout it was copied from. The adapter must not copy that path.
        {"kind": "cells.checkout_source_snapshot@1", "git_revision": "0123456789abcdef0123456789abcdef01234567", "repository": "/home/nobody/checkout", "status": "complete", "note": SYNTHETIC},
    )
    (OUT / "README.md").write_text(
        "# Synthetic run folder\n\n"
        "Written by `tools/make_run_fixture.py` for `tests/adapt_run.test.mjs`. It has the layout of an\n"
        "E07-v1 evidence folder, but every number is invented: no engine ran, and nothing here is\n"
        "evidence. Do not edit by hand; change the tool and run it again.\n\n"
        f"- {len(cells)} cells on a hexagonal lattice, numbered in a scrambled order, and {len(pairs)} junctions.\n"
        f"- {count} records: {sum(regular)} on the 10 s grid and {count - sum(regular)} at event times; one is marked not valid.\n"
        f"- {len(events)} replacements of disc cells; one copy falls back to the resting voltage.\n"
        "- `result.json` and `snapshot/SNAPSHOT.json` carry a made-up host name and machine paths, which\n"
        "  the adapter must leave out.\n"
    )
    size = sum(path.stat().st_size for path in OUT.rglob("*") if path.is_file())
    print(f"wrote {OUT.relative_to(HERE.parent)}: {len(cells)} cells, {len(pairs)} junctions, {count} records, {len(events)} events, {size:,} bytes in all")
    print(f"  disc {disc}, centre cell_{centre}, replaced {order}, falls {fallen}")


if __name__ == "__main__":
    main()
