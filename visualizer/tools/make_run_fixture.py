#!/usr/bin/env python3
"""Write the synthetic run folders that the adapter's test reads.

    python3 tools/make_run_fixture.py            # writes tests/fixtures/
    python3 tools/make_run_fixture.py --out DIR  # writes the same files into DIR

Four folders, each in the layout of one kind of evidence folder, on the same 19-cell
hexagonal sheet:

    run-small/   an E07-v1 folder: runs/<arm>/seedN, a summary with a class, snapshot/
    run-arms/    a turnover pre-screen folder: arms/<arm>, no seed and no class; one arm
                 ran to its planned end, the other records a refusal
    run-cue/     a W1 pilot folder: <study>/run with a definition per world, per-cell
                 voltages and a cue as a schedule; one study records a failure
    run-history/ two runs in the layout of the engine's shared output paths: one with
                 trajectory.npz, one with windows.jsonl and a chunk for each window; the
                 same numbers in both, under the engine's own names for its readouts

and beside them overlay.json and selection.json, which name all three experiments.
Every number is invented here. No engine ran, and nothing in these folders is evidence.

The same call always writes the same bytes. Standard library only.

The adapter's test writes these folders afresh into a temporary folder and reads them
there, so it does not depend on which of them the checkout holds: the repository ignores
every folder called runs/, which run-small has.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
import zipfile
from array import array
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE.parent / "tests" / "fixtures"
OUT = FIXTURES / "run-small"
ARMS = FIXTURES / "run-arms"
CUE = FIXTURES / "run-cue"
HISTORY = FIXTURES / "run-history"
EXPERIMENT, ARM, SEED = "synthetic-sheet", "synthetic-s1.0", 1
ARMS_EXPERIMENT, CUE_EXPERIMENT, HISTORY_EXPERIMENT = "synthetic-arms", "synthetic-cue", "synthetic-history"
SYNTHETIC = "synthetic fixture"
DIRECTIONS = ((1, 0), (0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1))
RADIUS, DISC_RING = 2, 1
DT, RECORD_S, END_S = 0.005, 10.0, 60.0
H_V, U_V, D_V = -0.0796, -0.0394, -0.0215  # resting, threshold and written voltages of the fixture
LAG_S, TAU_S = 5.0, 15.0
HEADER = "# Synthetic test fixture for the visualizer's run adapter. Not Cells code.\n"
REVISION = "0123456789abcdef0123456789abcdef01234567"


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


def the_sheet():
    """19 cells in a scrambled order, so nothing can lean on the numbering."""
    sites = [(q, r) for q in range(-RADIUS, RADIUS + 1) for r in range(-RADIUS, RADIUS + 1) if ring((q, r)) <= RADIUS]
    sites.sort(key=lambda site: ((site[0] * 7 + site[1] * 13) % 19, site))
    index = {site: number for number, site in enumerate(sites)}
    cells = [f"cell_{number}" for number in range(len(sites))]
    pairs = sorted({tuple(sorted((index[site], index[(site[0] + dq, site[1] + dr)]))) for site in sites for dq, dr in DIRECTIONS if (site[0] + dq, site[1] + dr) in index})
    # Every other junction is written receiver first: the sheet is undirected.
    junctions = [{"id": f"junction_{number}", "sender": cells[b if number % 2 else a], "receiver": cells[a if number % 2 else b]} for number, (a, b) in enumerate(pairs)]
    disc = sorted(number for site, number in index.items() if ring(site) <= DISC_RING)
    neighbours = {number: sorted(index[(q + dq, r + dr)] for dq, dr in DIRECTIONS if (q + dq, r + dr) in index) for (q, r), number in index.items()}
    return sites, index, cells, pairs, junctions, disc, neighbours


def write_snapshot(folder, modules, manifest="SNAPSHOT.json"):
    """A source snapshot of a few lines, in the shape the adapter reads constants from."""
    tissue = folder / "validation" / "tissue"
    tissue.mkdir(parents=True, exist_ok=True)
    for name, body in modules.items():
        (tissue / name).write_text(HEADER + body)
    write_json(
        folder / manifest,
        # A real snapshot manifest also names the checkout it was copied from. The adapter must not copy that path.
        {"kind": "cells.checkout_source_snapshot@1", "git_revision": REVISION, "repository": "/home/nobody/checkout", "status": "complete", "note": SYNTHETIC},
    )


STATES = f"HEREDITY_STATES = dict(H=({H_V}, 1.0), U=({U_V}, 2.0), D=({D_V}, 3.0))\n"
PILOT = "from validation.tissue import surface_pump_v3_fixtures as fixtures\n\nTHRESHOLD_V = fixtures.HEREDITY_STATES[\"U\"][0]\n"


def turnover_records(cells, pairs, disc, events, marks, fallen=None, lowered=()):
    """The arrays of a turnover run. events: (step, slot, donor or None, label)."""
    every = round(RECORD_S / DT)
    times = [step * DT for step in marks]
    regular = [step % every == 0 for step in marks]
    vm, generation, abundance, gate, conc, osm, valid = [], [], [], [], [], [], []
    for step, t in zip(marks, times):
        row = []
        for cell in range(len(cells)):
            level = D_V if cell in disc else H_V
            if cell == fallen and t > 45.0:
                level = H_V
            # An isolated newcomer arrives at the resting voltage and stays there.
            if any(slot == cell and event_step < step for event_step, slot in lowered):
                level = H_V
            row.append(level + 1e-5 * cell + 2e-6 * t)
        vm += row
        # A record at an event's time is taken before the event, so a replacement shows in later records.
        generation += [sum(1 for event_step, slot, *_ in events if slot == cell and event_step < step) for cell in range(len(cells))]
        for a, b in pairs:
            born = max((event_step * DT for event_step, slot, *_ in events if slot in (a, b) and event_step < step), default=None)
            abundance.append(1.0 if born is None else max(0.0, 1.0 - math.exp(-(t - born - LAG_S) / TAU_S)) if t > born + LAG_S else 0.0)
            # A junction across the disc's edge has its gate mostly shut; the others are open.
            gate.append(0.25 if (a in disc) != (b in disc) else 1.0)
        conc += [value + 0.01 * cell for value in (8.0, 140.0, 20.0) for cell in range(len(cells))]
        osm += [300.0 + 0.1 * cell for cell in range(len(cells))]
        valid.append(not math.isclose(t, 41.355))  # one record marked not valid, to exercise the flag
    count, n, j = len(marks), len(cells), len(pairs)
    arrays = {
        "t": npy("<f8", (count,), times),
        "vm": npy("<f8", (count, n), vm),
        "conc": npy("<f8", (count, 3, n), conc),
        "osm": npy("<f8", (count, n), osm),
        "abundance": npy("<f8", (count, j), abundance),
        "gate": npy("<f8", (count, j), gate),
        "generation": npy("<i8", (count, n), generation),
        "regular": npy("|b1", (count,), regular),
        "valid": npy("|b1", (count,), valid),
    }
    return arrays, times, regular, vm


# What a full definition states of every cell, membrane and bath: invented, like every number here.
VOLUME_PL, CAPACITANCE_F, AREA_M2, TEMPERATURE_K = 0.75, 1.6e-11, 3.2e-10, 310.0
SPECIES = (("Na", 1), ("K", 1), ("M", -1), ("P", -1))
BATH_FMOL = {"Na": 145.0, "K": 5.0, "M": 140.0, "P": 10.0}  # in a bath of 1 pL: mM
CONC_MM = (8.0, 140.0, 20.0)  # what turnover_records saves for the first three species, in cell 0


def turnover_definition(cells, junctions, events, newcomer, full=False, first=None):
    """A definition in the shape of a turnover run's. `full` writes what a judged run's
    definition states and the bare fixture leaves out: the model's own name and its laws of
    replacement, the species with their valences, the temperature, each cell's amounts and
    charge, its one membrane with a capacitance and an area, and its held bath. The names of
    the model and of its laws are the engine's, because the adapter states a constant only
    for a model it knows; the numbers are invented. `first` is the first record's voltage of
    every cell: a full definition's charges are that voltage times the capacitance, as a real
    definition's are."""
    model = {
        "id": "synthetic_sheet@0",
        "cells": [{"id": cell, "volume_pL": VOLUME_PL} for cell in cells],
        "junctions": junctions,
    }
    if full:
        amounts = lambda number: {**{name: (CONC_MM[row] + 0.01 * number) * VOLUME_PL for row, (name, _) in enumerate(SPECIES[:3])}, "P": 76.0}  # noqa: E731
        model = {
            "id": "resolved_pump_replacement@1",
            "temperature_K": TEMPERATURE_K,
            "species": [{"id": name, "valence": valence} for name, valence in SPECIES],
            "cells": [
                {"id": cell, "volume_pL": VOLUME_PL, "initial_amount_fmol": amounts(number), "fixed_charge_equivalent_fmol": 0.0, "initial_charge_C": first[number] * CAPACITANCE_F}
                for number, cell in enumerate(cells)
            ],
            "extracellular": [
                {"id": f"bath_{number}", "volume_pL": 1.0, "initial_amount_fmol": dict(BATH_FMOL), "fixed_charge_equivalent_fmol": 0.0, "initial_charge_C": 0.0, "reservoir": True, "boundary_potential_V": 0.0}
                for number in range(len(cells))
            ],
            "membranes": [
                {"id": f"membrane_{number}", "inside": cell, "outside": f"bath_{number}", "area_m2": AREA_M2, "capacitance_F": CAPACITANCE_F, "permeability_m_per_s": {"Na": 5e-11, "K": 1e-10, "M": 1e-10, "P": 0.0}, "law": "constant_field@1", "pump": None, "calcium_pump": None}
                for number, cell in enumerate(cells)
            ],
            "junctions": [dict(junction, gate={"law": "junction_voltage_relaxation@1"}) for junction in junctions],
            "faces": [],
            "closure": {"law": "resolved_capacitor_components_current_continuity@1", "gauge_reference": None},
            "channels": [],
            "junction_heat_booking": "trapezoid_nonnegative@1",
            "replacement": {
                "law": "scheduled_cell_replacement@1",
                "inner_model": "resolved_pump_tissue@3",
                "junction_formation": {"law": "delayed_first_order_junction_formation@1", "initial_abundance": 0.0, "lag_s": LAG_S, "time_constant_s": TAU_S, "gate_at_arrival": "law_open"},
                "templates": [{"id": "h_isolated", "volume_pL": VOLUME_PL, "fixed_charge_equivalent_fmol": 0.0, "amounts_fmol": amounts(0), "channel_gates": {}, "route_values": {"channel_abundance": {}, "membrane_permeability_m_per_s": {}}}],
                "template_capacity": 1,
            },
        }  # fmt: skip
    return {
        "schema_version": 1,
        "note": f"{SYNTHETIC}: not a Cells definition",
        "model": model,
        "experiment": {
            "end_time": END_S,
            "replacement_events": [
                {
                    "time": round(step * DT, 9), "slot": cells[slot], "newcomer": newcomer, "template": None if donor is not None else "h_isolated",
                    "donor": None if donor is None else cells[donor], "carrier_id": label,
                }
                for step, slot, donor, label in events
            ],
        },
        "execution": {"dt": DT},
    }  # fmt: skip


def write_small(sheet):
    """run-small: the layout and file shapes of an E07-v1 evidence folder."""
    sites, index, cells, pairs, junctions, disc, neighbours = sheet
    centre = index[(0, 0)]

    # ---- the schedule: three replacements of disc cells by a disc neighbour
    order = [disc[1], disc[3], disc[5]]
    steps = [2757, 4000, 8271]  # 13.785 s, 20 s (on the record grid) and 41.355 s
    events = []
    for number, (step, slot) in enumerate(zip(steps, order)):
        donor = next(cell for cell in neighbours[slot] if cell in disc and cell != slot)
        events.append((step, slot, donor, f"n{number}"))
    every, end = round(RECORD_S / DT), round(END_S / DT)
    marks = sorted({0} | set(range(every, end + 1, every)) | {step for step, *_ in events} | {end})
    fallen = order[2]  # this copy falls from D to H after its replacement
    arrays, times, regular, voltages = turnover_records(cells, pairs, disc, events, marks, fallen=fallen)
    count, first = len(marks), voltages[: len(cells)]

    run = OUT / "runs" / ARM / f"seed{SEED}"
    run.mkdir(parents=True, exist_ok=True)
    write_npz(run / "records.npz", arrays)
    write_json(run / "definition.json", turnover_definition(cells, junctions, events, "donor_copy", full=True, first=first), indent=None)
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
    entry = {
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
    write_json(
        OUT / "overlay.json",
        {"format": "cells.visualizer.replay_overlay@1", "note": f"{SYNTHETIC}: labels for the adapter's test only.", "experiments": {EXPERIMENT: entry}},
    )
    selected = {"evidence_folder": OUT.name, "runs": [f"{ARM}/seed{SEED}"]}
    write_json(OUT / "selection.json", {"note": SYNTHETIC, EXPERIMENT: selected})

    # ---- a source snapshot of three lines, in the shape the adapter reads constants from
    write_snapshot(
        OUT / "snapshot",
        {
            "surface_pump_v3_fixtures.py": STATES,
            "heredity_pilot.py": PILOT,
            "e07_v1_turnover.py": f"RECORD_S = {RECORD_S}\n",
            "e07_v1_run.py": "def part_analyse(z):\n    from validation.tissue.heredity_pilot import THRESHOLD_V\n\n    return z[\"vm\"] > THRESHOLD_V\n",
        },
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
    print(f"wrote {OUT.name}: {len(cells)} cells, {len(pairs)} junctions, {count} records, {len(events)} events")
    print(f"  disc {disc}, centre cell_{centre}, replaced {order}, falls {fallen}")
    return entry, selected


def write_arms(sheet):
    """run-arms: the layout of the turnover pre-screen's folder. No seed, no group, no class."""
    sites, index, cells, pairs, junctions, disc, neighbours = sheet
    every, end = round(RECORD_S / DT), round(END_S / DT)
    order = [disc[2], disc[4], disc[6], disc[0], disc[1], disc[3], disc[5]]
    steps = [1714, 5142, 8571, 13714, 17142, 20571]  # the last three fall after the planned end
    source = "/mnt/nowhere/run-arms/source-01/validation/tissue/heredity_turnover_literature.py"
    arms, summary = [], {}
    for name, kind, stopped in (("synthetic-iso-s1.0", "iso", None), ("synthetic-donor-s1.0", "donor", 6200)):
        events = []
        for number, (step, slot) in enumerate(zip(steps, order)):
            donor = None if kind == "iso" else next(cell for cell in neighbours[slot] if cell in disc and cell != slot)
            events.append((step, slot, donor, f"n{number}"))
        # The donor arm is refused at step 6200 (31 s): it keeps its records to 30 s.
        last = end if stopped is None else (stopped // every) * every
        marks = sorted({0} | set(range(every, last + 1, every)) | {step for step, *_ in events if step <= last} | {last})
        lowered = [(step, slot) for step, slot, donor, _ in events if donor is None]
        arrays, times, regular, vm = turnover_records(cells, pairs, disc, events, marks, lowered=lowered)
        count, width = len(marks), len(cells)
        folder = ARMS / "arms" / name
        folder.mkdir(parents=True, exist_ok=True)
        write_npz(folder / "records.npz", arrays)
        # The arm with isolated newcomers has a full definition, as the real arms have; the other is left bare,
        # so that the adapter is also met with a definition that states too little.
        write_json(folder / "definition.json", turnover_definition(cells, junctions, events, "isolated_template" if kind == "iso" else "donor_copy", full=kind == "iso", first=vm[:width]), indent=None)
        write_json(
            folder / "plan.json",
            {
                "kind": kind, "bracket": "fast", "formation": {"lag_s": LAG_S, "time_constant_s": TAU_S}, "formation_time_s": LAG_S + TAU_S, "k": 1,
                "residence_s": 60.0, "size": len(disc), "s": 1.0, "dt": DT, "end_s": END_S, "interval_s": 60.0 / len(disc),
                "permutation": order, "events": [[step, slot, donor, label] for step, slot, donor, label in events],
                "turnover_complete_s": [55.0, 115.0], "start": {"seconds_after_cue_off_at_t0": 117.5}, "seeds": {"order": 11, "donor": 12},
            },
        )  # fmt: skip
        inside, outside = [], []
        for row in range(count):
            d = [cell for cell in range(width) if vm[row * width + cell] > U_V]
            inside.append(sum(1 for cell in d if cell in disc))
            outside.append(len(d) - inside[-1])
        grid = [row for row in range(count) if regular[row]]
        stop = "planned end" if stopped is None else "refusal"
        refusal = None if stopped is None else {"step": stopped, "time_s": stopped * DT, "failed": ["field_not_converged"], "state_kept": "the last accepted row before the refusal"}
        outcome = {
            "kind": "synthetic.arm_outcome@0", "arm": name, "stop": stop, "end_s": last * DT, "planned_end_s": END_S, "refusal": refusal,
            "residence_s": 60.0, "turnovers_reached": [stopped is None, False], "jaccard_after_turnover": [inside[-1] / len(disc) if stopped is None else None, None],
            "jaccard_after_turnover_basis": ["record" if stopped is None else stop, stop], "all_h_s": None, "d_inside_end": inside[-1], "max_d_outside": max(outside),
            "newcomers": sum(1 for step, *_ in events if step <= last), "osmotic": {"max_excess": 0.01}, "b1_jaccard_0p8_through_two_turnovers": False,
            "series": {"t_s": [times[row] for row in grid], "d_inside": [inside[row] for row in grid], "d_outside": [outside[row] for row in grid]},
        }  # fmt: skip
        write_json(folder / "outcome.json", outcome)
        write_json(
            folder / "result.json",
            {
                "arm": name, "engine_models": [f"none ({SYNTHETIC}: no engine ran)"], "dt": DT, "end_step": last, "end_s": last * DT, "planned_end_s": END_S,
                "stop": stop, "refusal": refusal, "records": count,
                # A real result.json carries a host name and machine paths here. The adapter takes one folder's name from the source path and writes neither.
                "provenance": {"argv": ["/home/nobody/checkout/validation/driver.py", "arm"], "host": "fixture-host-01", "revision": None, "source": source},
            },
        )  # fmt: skip
        summary[name] = {key: outcome[key] for key in ("stop", "end_s", "planned_end_s", "jaccard_after_turnover")}
        arms.append((name, count, len([step for step, *_ in events if step <= last]), stop))
    write_json(ARMS / "summary.json", {"kind": "synthetic.arms_summary@0", "arms": summary, "arms_without_outcome": []})
    # A folder a killed process left behind: it has no outcome, and the selection does not list it.
    (ARMS / "arms" / "synthetic-iso-s1.0.killed").mkdir(parents=True, exist_ok=True)
    write_json(ARMS / "arms" / "synthetic-iso-s1.0.killed" / "plan.json", {"kind": "iso", "note": SYNTHETIC})
    write_snapshot(
        ARMS / "source-01",
        {
            "surface_pump_v3_fixtures.py": STATES,
            "heredity_pilot.py": PILOT,
            "heredity_turnover_literature.py": "from validation.tissue import heredity_pilot as pilot\n\nTHRESHOLD_V = pilot.THRESHOLD_V\n"
            f"RECORD_S = {RECORD_S}\n\n\ndef analyse(vm):\n    return vm > THRESHOLD_V\n",
        },
    )
    (ARMS / "README.md").write_text(
        "# Synthetic arms folder\n\n"
        "Written by `tools/make_run_fixture.py` for `tests/adapt_run.test.mjs`. It has the layout of the\n"
        "turnover pre-screen's evidence folder (`arms/<arm>`), but every number is invented: no engine\n"
        "ran, and nothing here is evidence. Do not edit by hand; change the tool and run it again.\n\n"
        "- An arm is one run: it has no seed, its plan names no group, and nothing records a class.\n"
        "- `synthetic-iso-s1.0` ran to its planned end; its newcomers arrive with no donor.\n"
        "- `synthetic-donor-s1.0` records a refusal at 31 s and keeps its records to 30 s.\n"
        "- `synthetic-iso-s1.0.killed` has no outcome, as a killed process leaves a folder.\n"
    )
    for name, count, happened, stop in arms:
        print(f"wrote {ARMS.name}/arms/{name}: {count} records, {happened} events, stop {stop!r}")
    entry = {
        "adapter": "heredity-turnover-literature",
        "label": "Synthetic arms (test fixture)",
        "plain": "Invented numbers in the layout of the turnover pre-screen's folder. No engine ran; nothing here is evidence.",
        "sources": [],
        "outcome": {"judged": False, "status": "Synthetic: not judged", "answer": None, "text": "Synthetic wording.", "sources": []},
        "stops": {"planned end": {"label": "Ran to its planned end"}, "refusal": {"label": "Stopped: the model refused a step"}},
        "engine_entities": [],
        "groups": {"iso": {"label": "Isolated newcomers"}, "donor": {"label": "Donor copies"}},
        "regions": {"disc": {"label": "The disc"}},
        "records": {"vm": {"label": "Membrane voltage"}},
        "events": {"replacement": {"label": "Replacement"}},
        "parameters": {"kind": {"label": "Newcomer"}, "size": {"label": "Disc size", "unit": "cells"}, "formation.lag_s": {"label": "Formation lag", "unit": "s"}, "seeds.order": {"label": "Seed of the order"}},
        "readouts": {
            "jaccard_after_turnover.0": {"label": "J after the first turnover"},
            "jaccard_after_turnover.1": {"label": "J after the second turnover"},
            "jaccard_after_turnover_basis.0": {"label": "Basis of J after the first turnover"},
            "jaccard_after_turnover.2": {"label": "Absent"},
            "osmotic.max_excess": {"label": "Largest osmotic excess"},
            "b1_jaccard_0p8_through_two_turnovers": {"label": "B1"},
        },
    }
    return entry, {"evidence_folder": ARMS.name, "runs": [name for name, *_ in arms]}


def write_cue(sheet):
    """run-cue: the layout of a W1 pilot folder. A cue writes the disc; nothing is replaced."""
    sites, index, cells, pairs, junctions, disc, neighbours = sheet
    patches = 2  # membrane patches per cell: the cue is a channel on each of them
    membranes, channels, controls = [], [], []
    on_s, off_s, start_s, end_s = 3.0, 4.0, 2.0, 5.0
    for cell in range(len(cells)):
        for patch in range(patches):
            number = cell * patches + patch
            membranes.append({"id": f"membrane_{number}", "inside": cells[cell], "outside": f"ecm_{number % 5}"})
            channels.append({"id": f"kir_{number}", "membrane_id": f"membrane_{number}", "kinetic_law": "synthetic_gate@0"})
            controls.append({"channel_id": f"kir_{number}", "schedule": [{"time": 0.0, "availability": 1.0}]})
    # Every cell carries the cue population, as the real worlds share one shape; only the disc's is switched on.
    for cell in range(len(cells)):
        for patch in range(patches):
            number = cell * patches + patch
            channels.append({"id": f"cue_{number}", "membrane_id": f"membrane_{number}", "kinetic_law": "synthetic_leak@0"})
            schedule = [{"time": 0.0, "availability": 0.0}]
            if cell in disc:
                schedule += [{"time": on_s, "availability": 1.0}, {"time": off_s, "availability": 0.0}]
            controls.append({"channel_id": f"cue_{number}", "schedule": schedule})
    definition = {
        "schema_version": 1,
        "note": f"{SYNTHETIC}: not a Cells definition",
        "model": {
            "id": "synthetic_tissue@0",
            "cells": [{"id": cell, "volume_pL": 0.75} for cell in cells],
            "extracellular": [{"id": f"ecm_{number}"} for number in range(5)],
            "membranes": membranes,
            "junctions": junctions,
            "faces": [{"id": f"face_{number}", "sender": f"ecm_{number}", "receiver": f"ecm_{number + 1}"} for number in range(4)],
            "channels": channels,
            "junction_heat_booking": "synthetic_booking@0",
        },
        "experiment": {"end_time": end_s, "channel_controls": controls},
        "execution": {"dt": 0.001},
    }
    quarter = [start_s + 0.25 * step for step in range(round((end_s - start_s) / 0.25) + 1)]
    late = disc[3]  # this cell is written one record later than the others
    failure = {
        "error": "SyntheticCheckError('World 1: refused at accepted time 3.001')", "world_id": 1, "step_index": 3001, "time_interval": [on_s, on_s + 0.001], "checks": ["dissipation"],
        # A real failure carries a traceback with machine paths. The adapter must leave it out.
        "traceback": "Traceback (most recent call last):\n  File \"/mnt/nowhere/run-cue/source-01/validation/tissue/heredity_pilot.py\", line 1, in run_batch\n",
    }  # fmt: skip
    written = []
    for study, failed in (("study-a", None), ("study-b", failure)):
        times = quarter if failed is None else [t for t in quarter if t <= on_s]
        vm, lines = [], []
        for t in times:
            row = [(D_V if cell in disc and (t >= on_s + 0.5 if cell == late else t >= on_s + 0.25) else H_V) + 1e-5 * cell + 2e-6 * t for cell in range(len(cells))]
            vm += row
            d = [cell for cell, value in enumerate(row) if value > U_V]
            inside = sum(1 for cell in d if cell in disc)
            lines.append(json.dumps({"t": t, "d_inside": inside, "d_outside": len(d) - inside, "d_outside_cells": []}))
        run = CUE / study / "run"
        (run / "records").mkdir(parents=True, exist_ok=True)
        write_json(run / "definitions" / "world-1.json", definition, indent=None)
        write_npz(run / "records" / "world-1-cell-vm.npz", {"times_s": npy("<f8", (len(times),), times), "cell_vm_V": npy("<f8", (len(times), len(cells)), vm)})
        (run / "records" / "world-1.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        recorded = {
            "kind": "synthetic.pilot_run@0", "resumed_from": None,
            "phases_s": {"preparation_end": start_s, "cue_on": on_s, "cue_off": off_s, "end": end_s, "baseline": on_s - start_s, "cue": off_s - on_s, "retention": end_s - off_s},
            "observations_per_world": len(quarter), "worlds": {"1": {"seed": 3, "s": 1.0, "disc_cells": len(disc)}},
        }  # fmt: skip
        if failed is not None:
            recorded["failure"] = failed
            write_json(run / "results.json", {"kind": "synthetic.pilot_results@0", "worlds": {"1": {"seed": 3, "written": False, "d_inside_at_end": 0, "last_time_s": on_s}}, "failure": failed})
        write_json(run / "run.json", recorded)
        written.append((study, len(times)))
    log = [
        {"label": "a-prepare", "exit": 0, "source": "/mnt/nowhere/run-cue/source-01", "output": "study-a", "args": "prepare --seeds 3"},
        {"label": "a-run", "exit": 0, "source": "/mnt/nowhere/run-cue/source-01", "output": "study-a", "args": "run --seeds 3 --cue-seconds 1"},
        {"note": f"{SYNTHETIC}: a line that is not a launch"},
        {"label": "b-run", "exit": 1, "source": "/mnt/nowhere/run-cue/source-01", "output": "study-b", "args": "run --seeds 3 --cue-seconds 1"},
    ]
    (CUE / "runs.jsonl").write_text("".join(json.dumps(line) + "\n" for line in log), encoding="utf-8")
    write_snapshot(
        CUE / "source-01",
        {
            "surface_pump_v3_fixtures.py": STATES,
            "heredity_pilot.py": '"""Synthetic wording: the cells lie on a jittered hexagonal\nlattice."""\n\n' + PILOT + "\n\ndef count(vm):\n    return vm > THRESHOLD_V\n",
        },
    )
    (CUE / "README.md").write_text(
        "# Synthetic cue folder\n\n"
        "Written by `tools/make_run_fixture.py` for `tests/adapt_run.test.mjs`. It has the layout of a W1\n"
        "pilot evidence folder (`<study>/run`), but every number is invented: no engine ran, and nothing\n"
        "here is evidence. Do not edit by hand; change the tool and run it again.\n\n"
        f"- Every cell has {patches} membrane patches and a cue channel on each; the schedule switches it on\n"
        f"  from {on_s:g} s to {off_s:g} s in the disc's {len(disc)} cells only.\n"
        "- `study-a` runs to its end: the disc is written within two records and stays written.\n"
        "- `study-b` records a failure at the cue's first step, with a traceback that holds a machine\n"
        "  path, and keeps its records up to the cue.\n"
        "- `runs.jsonl` names the source snapshot each study ran from, by a path the adapter must not copy.\n"
    )
    for study, count in written:
        print(f"wrote {CUE.name}/{study}: {count} records, cue on {len(disc)} cells from {on_s:g} s to {off_s:g} s")
    entry = {
        "adapter": "heredity-pilot-w1",
        "label": "Synthetic cue (test fixture)",
        "plain": "Invented numbers in the layout of a W1 pilot folder. No engine ran; nothing here is evidence.",
        "sources": [],
        "outcome": {"judged": False, "status": "Synthetic: not judged", "answer": None, "text": "Synthetic wording.", "sources": []},
        "engine_entities": [],
        "groups": {"study-a": {"label": "Synthetic study A"}, "study-b": {"label": "Synthetic study B"}},
        "regions": {"disc": {"label": "The disc", "plain": "The cells the cue acts on."}},
        "records": {"vm": {"label": "Membrane voltage"}},
        "events": {"cue_on": {"label": "Cue on"}, "cue_off": {"label": "Cue off"}},
        "parameters": {"disc_cells": {"label": "Disc size", "unit": "cells"}, "phases_s.cue_on": {"label": "Cue on", "unit": "s"}, "execution.dt": {"label": "Time step", "unit": "s"}, "model.junction_heat_booking": {"label": "Booking"}},
        "readouts": {"written": {"label": "Written"}, "last_time_s": {"label": "Last record", "unit": "s"}},
    }
    return entry, {"evidence_folder": CUE.name, "runs": [f"{study}/world-1" for study, _ in written]}


def write_history(sheet):
    """run-history: two runs in the layout of the engine's shared output paths, with the same invented numbers.

    `whole/run` holds trajectory.npz; `windowed/run` holds windows.jsonl and one chunk for each
    of two windows, the second of which begins with the record the first ended on. Readouts
    stand under the engine's own names (observed_<field> at observation_times). Arrays are made
    for two more places than the run uses, as the engine makes them for its capacity.
    """
    sites, index, cells, pairs, junctions, disc, neighbours = sheet
    n, j, spare = len(cells), len(pairs), 2
    times = [0.0, 10.0, 20.0, 30.0, 40.0]
    voltage = lambda cell, t: (D_V if cell in disc else H_V) + 1e-5 * cell + 2e-6 * t  # noqa: E731
    definition = turnover_definition(cells, junctions, [], "donor_copy", full=True, first=[voltage(cell, 0.0) for cell in range(n)])
    model = definition["model"]
    # A composition over the pump tissue with no operator: the engine's own names for the model and its inner model.
    del model["replacement"]
    model.update({"id": "resolved_pump_composite@1", "inner_model": "resolved_pump_tissue@3", "operators": []})
    model["channels"] = [{"id": f"kir_{number}", "membrane_id": f"membrane_{number}", "kinetic_law": "kir2p1_mh2@1", "abundance": 1.0} for number in range(n)]
    definition["experiment"] = {"end_time": times[-1], "observation_times": times}
    species = [name for name, _ in SPECIES]

    def padded(values_at, width):
        """One row for each time: `width` values and then the spare places, which hold zero."""
        return [value for t in times for value in [*values_at(t), *([0.0] * spare)]][: len(times) * (width + spare)]

    amount = lambda row, cell: ((CONC_MM[row] + 0.01 * cell) if row < 3 else 101.0) * VOLUME_PL  # noqa: E731
    fields = {
        # A voltage for each membrane; the potential of its cell; the baths are held at 0 V.
        "membrane_voltage_V": ((n + spare,), padded(lambda t: [voltage(cell, t) for cell in range(n)], n)),
        "cell_potential_V": ((n + spare,), padded(lambda t: [voltage(cell, t) for cell in range(n)], n)),
        "extracellular_potential_V": ((n + spare,), padded(lambda t: [0.0] * n, n)),
        # A junction's voltage is the potential of its sender less that of its receiver, as the engine has it.
        "junction_voltage_V": ((j + spare,), padded(lambda t: [voltage(cells.index(item["sender"]), t) - voltage(cells.index(item["receiver"]), t) for item in junctions], j)),
        "junction_gate": ((j + spare,), padded(lambda t: [0.25 if (a in disc) != (b in disc) else 1.0 for a, b in pairs], j)),
        "pump_cycles": ((n + spare,), padded(lambda t: [0.002 * t * (1 + 0.01 * cell) for cell in range(n)], n)),
        "membrane_dissipated_energy_pJ": ((n + spare,), padded(lambda t: [0.03 * t for _ in range(n)], n)),
        "channel_transferred": ((n + spare,), padded(lambda t: [0.004 * t * (1 + 0.02 * cell) for cell in range(n)], n)),
    }
    # One row for each species, then the places: amounts in the cell and outside, and what crossed each membrane since the start.
    for field, value in (
        ("amount", lambda row, place, t: amount(row, place) + (0.001 * t if row == 1 else 0.0)),
        ("extracellular_amount", lambda row, place, t: BATH_FMOL[species[row]]),
        ("membrane_transferred", lambda row, place, t: (0.001, -0.002, 0.0005, 0.0)[row] * t * (1 + 0.01 * place)),
    ):
        fields[field] = ((len(species), n + spare), [v for t in times for row in range(len(species)) for v in [*[value(row, place, t) for place in range(n)], *([0.0] * spare)]])

    def arrays(rows):
        """The .npz arrays for some of the records: observation_times and each observed field."""
        out = {"observation_times": npy("<f8", (len(rows),), [times[row] for row in rows])}
        for field, (shape, values) in fields.items():
            width = 1
            for size in shape:
                width *= size
            out[f"observed_{field}"] = npy("<f8", (len(rows), *shape), [value for row in rows for value in values[row * width : (row + 1) * width]])
        return out

    summary = {"status": "complete", "start_time": 0.0, "end_time": times[-1], "executed_steps": 8000, "active_cells": n, "note": f"{SYNTHETIC}: no engine ran"}
    whole = HISTORY / "whole" / "run"
    whole.mkdir(parents=True, exist_ok=True)
    write_npz(whole / "trajectory.npz", arrays(range(len(times))))
    write_json(whole / "resolved_config.json", definition, indent=None)
    write_json(whole / "summary.json", summary)
    windowed = HISTORY / "windowed" / "run"
    (windowed / "chunks").mkdir(parents=True, exist_ok=True)
    lines = []
    # Two windows; the second begins with the record the first ended on. A third kept no readouts.
    for number, rows in enumerate(([0, 1, 2], [2, 3, 4])):
        write_npz(windowed / "chunks" / f"window-{number:08d}.npz", arrays(rows))
        lines.append({"kind": "window", "index": number, "start_time": times[rows[0]], "end_time": times[rows[-1]], "accepted_records": 0, "observation_records": len(rows), "path": f"chunks/window-{number:08d}.npz"})
    lines.append({"kind": "window", "index": 2, "start_time": times[-1], "end_time": times[-1], "accepted_records": 0, "observation_records": 0, "path": None})
    lines.append({"kind": "checkpoint", "step_index": 8000, "time": times[-1], "path": "snapshots/step-0000008000"})
    (windowed / "windows.jsonl").write_text("".join(json.dumps(line, sort_keys=True) + "\n" for line in lines), encoding="utf-8")
    write_json(windowed / "resolved_config.json", definition, indent=None)
    write_json(windowed / "summary.json", summary)
    (HISTORY / "README.md").write_text(
        "# Synthetic runs in the layout of the engine's shared output paths\n\n"
        "Written by `tools/make_run_fixture.py` for `tests/adapt_run.test.mjs`. Every number is invented: no engine\n"
        "ran, and nothing here is evidence. Do not edit by hand; change the tool and run it again.\n\n"
        f"- {n} cells with one membrane and one held bath each, {j} junctions, {n} channel populations, {len(species)} species.\n"
        f"- {len(times)} observation times. `whole/run` holds them in `trajectory.npz`; `windowed/run` in two window chunks.\n"
        f"- Arrays are made for {spare} more places than the run uses, as the engine makes them for its capacity.\n"
    )
    print(f"wrote {HISTORY.name}: {n} cells, {j} junctions, {len(times)} observation times, as one file and as two windows")
    entry = {
        "adapter": "standard-history",
        "development": True,
        "label": "Synthetic development run (test fixture)",
        "plain": "Invented numbers in the layout of the engine's shared output paths. No engine ran; nothing here is evidence.",
        "sources": [],
        "engine_entities": [],
        "outcome": {"judged": False, "status": "A development run: not judged"},
        "records": {"vm": {"label": "Membrane voltage"}},
        "parameters": {"execution.dt": {"label": "Time step", "unit": "s"}, "model.inner_model": {"label": "Inner model"}},
        "readouts": {"status": {"label": "Status"}, "end_time": {"label": "End", "unit": "s"}},
    }
    return entry, {"evidence_folder": HISTORY.name, "runs": ["whole/run", "windowed/run"]}


def main(argv=None):
    global FIXTURES, OUT, ARMS, CUE, HISTORY
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", default=str(FIXTURES), help="the folder to write the four run folders, overlay.json and selection.json into")
    FIXTURES = Path(parser.parse_args(argv).out).resolve()
    OUT, ARMS, CUE, HISTORY = FIXTURES / "run-small", FIXTURES / "run-arms", FIXTURES / "run-cue", FIXTURES / "run-history"
    sheet = the_sheet()
    experiments, selection = {}, {"note": f"{SYNTHETIC}: the four synthetic experiments, each with the folder beside this file that holds it."}
    for identifier, (entry, selected) in ((EXPERIMENT, write_small(sheet)), (ARMS_EXPERIMENT, write_arms(sheet)), (CUE_EXPERIMENT, write_cue(sheet)), (HISTORY_EXPERIMENT, write_history(sheet))):
        experiments[identifier] = entry
        selection[identifier] = selected
    write_json(FIXTURES / "overlay.json", {"format": "cells.visualizer.replay_overlay@1", "note": f"{SYNTHETIC}: labels for the adapter's test only.", "experiments": experiments})
    write_json(FIXTURES / "selection.json", selection)
    size = sum(path.stat().st_size for folder in (OUT, ARMS, CUE, HISTORY) for path in folder.rglob("*") if path.is_file())
    print(f"wrote overlay.json and selection.json; {size:,} bytes in the four folders of {FIXTURES.name}/")


if __name__ == "__main__":
    main()
