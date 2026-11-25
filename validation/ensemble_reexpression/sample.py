"""The format sample (spec/TABLE.md §7): tables of invented worlds, with every number replaced.

    python -m validation.ensemble_reexpression.sample make DIRECTORY
    python -m validation.ensemble_reexpression.sample scrub DIRECTORY DESTINATION
    python -m validation.ensemble_reexpression.sample keys FOLDER

`make` writes the invented inputs, makes their runs with the run driver and exports their tables
with the exporter. `scrub` writes those tables with every number replaced by a meaningless one of
its type, and every registered string and fingerprint by a placeholder. `keys` lists every key and
type of a folder of tables, to the leaf. The worlds are this file's own: no number of them is
inputs.json's or a rehearsal's, and nothing of them is judged.
"""

import argparse
import json
import math
import re
from pathlib import Path

from cells.laws.electrochemistry import CHARGE_PER_FMOL
from validation.ensemble_reexpression import run as driver
from validation.ensemble_reexpression import table as exporter
from validation.ensemble_reexpression.inputs import SCHEMA, Inputs, read_json

VALENCE = {"Na": 1, "K": 1, "Cl": -1}
ONES = [[0.0, 1.0]]
END_S = 0.0002


# ------------------------------------------------------------------ the invented worlds


def compartment(volume, amounts, charge):
    """A compartment whose fixed charge closes its declared charge."""
    moved = math.fsum(VALENCE[s] * n for s, n in amounts.items())
    return {
        "volume_pL": volume,
        "initial_amount_fmol": amounts,
        "fixed_charge_equivalent_fmol": charge / CHARGE_PER_FMOL - moved,
    }


def amounts(volume, na, k, cl):
    """Amounts (fmol) of these concentrations (mM) in a volume (pL)."""
    return {"Na": na * volume, "K": k * volume, "Cl": cl * volume}


def cell(volume, capacitance, voltage, na, k, cl):
    charge = capacitance * voltage
    out = compartment(volume, amounts(volume, na, k, cl), charge)
    return out | {"initial_voltage_V": voltage, "initial_charge_C": charge}


def region(volume, na, k, cl, charges):
    charge = -math.fsum(charges) if charges else 0.0
    out = compartment(volume, amounts(volume, na, k, cl), charge)
    return out | {"initial_charge_C": charge}


def membrane(inside, outside, area, capacitance, permeability, capacity=None):
    pump = None
    if capacity is not None:
        pump = {
            "law": "nak_pump_positive",
            "roles": {"sodium": "Na", "potassium": "K"},
            "stoichiometry": {"Na": -3, "K": 2},
            "capacity_fmol_per_s": capacity,
            "km_na_mM": 11.0,
            "km_k_mM": 0.25,
            "km_atp_mM": 0.4,
            "metabolism": {
                "kind": "maintained_fuel",
                "atp_mM": 1.2,
                "adp_mM": 0.15,
                "pi_mM": 0.2,
                "delta_g0_J_per_mol": -36500.0,
            },
        }
    return {
        "inside": inside,
        "outside": outside,
        "area_m2": area,
        "capacitance_F": capacitance,
        "passive": {"law": "constant_field", "permeability_m_per_s": permeability},
        "pump": pump,
    }


def channel(patch, permeability, abundance):
    return {
        "membrane_id": patch,
        "species_id": "K",
        "kinetic_law": "kv15_mh",
        "max_permeability_m_per_s": permeability,
        "abundance": abundance,
        "initial_gate": {"m": 0.25, "h": 0.65},
    }


def junction(sender, receiver, area, permeability, initial):
    return {
        "from_cell": sender,
        "to_cell": receiver,
        "area_m2": area,
        "permeability_m_per_s": permeability,
        "gate": {
            "initial_gate": initial,
            "law": "junction_relaxation",
            "minimum_open_fraction": 0.15,
            "threshold_voltage_V": 0.018,
        },
    }


def face(sender, receiver):
    return {
        "sender": sender,
        "receiver": receiver,
        "area_m2": 1.4e-11,
        "length_m": 1.7e-05,
        "diffusivity_m2_per_s": {"Na": 1.3e-09, "K": 1.8e-09, "Cl": 1.9e-09},
        "law": "logmean_face",
    }


def closed(cells, outside, membranes, *, channels=(), junctions=(), faces=(), gauge, controls):
    """A block of these entities in the literal blocks' form."""
    return {
        "temperature_K": 301.0,
        "species": VALENCE,
        "cells": cells,
        "outside": outside,
        "closure": {"gauge_reference": gauge},
        "membranes": membranes,
        "channels": channels or [],
        "junctions": junctions or [],
        "faces": faces or [],
        "controls": controls,
        "material_tolerance_fmol": {"Na": 3e-11, "K": 3e-11, "Cl": 3e-11},
        "end_s": END_S,
    }


LEAK = {"Na": 2e-11, "K": 4e-10, "Cl": 6e-11}


def cluster(channel_controls):
    """Two pumped cells, one junction, and a ring of three regions, two of them floating."""
    cells = {
        "c_a": cell(0.8, 2.5e-12, -0.05, 12.0, 136.0, 10.0),
        "c_b": cell(0.6, 3.1e-12, -0.03, 14.0, 133.0, 9.0),
    }
    charges = [c["initial_charge_C"] for c in cells.values()]
    return closed(
        cells,
        {
            "bath": region(2.5, 138.0, 4.0, 120.0, charges),
            "shell": region(1.5, 130.0, 6.0, 110.0, []),
            "rim": region(2.2, 145.0, 3.8, 120.0, []),
        },
        {
            "m_a": membrane("c_a", "bath", 2.5e-10, 2.5e-12, LEAK, 0.07),
            "m_b": membrane("c_b", "bath", 3.1e-10, 3.1e-12, LEAK, 0.06),
        },
        channels={"k_a": channel("m_a", 4e-10, 0.55), "k_b": channel("m_b", 4e-10, 0.45)},
        junctions={
            "j_ab": junction("c_a", "c_b", 1.3e-10, {"Na": 2e-10, "K": 6e-10, "Cl": 3e-10}, 0.5)
        },
        faces={
            "f_0": face("bath", "shell"),
            "f_1": face("shell", "rim"),
            "f_2": face("rim", "bath"),
        },
        gauge="bath",
        controls={
            "leak": {"m_a": ONES, "m_b": ONES},
            "pump": {name: [[0.0, 1.0], [4e-05, 0.0], [0.00012, 1.0]] for name in ("m_a", "m_b")},
            "channel": channel_controls,
            "junction": {"j_ab": ONES},
        },
    )


def lone():
    """One pumped cell in one finite region, its channel driven."""
    cells = {"c_a": cell(0.9, 8e-12, -0.07, 13.0, 137.0, 11.0)}
    charges = [c["initial_charge_C"] for c in cells.values()]
    return closed(
        cells,
        {"bath": region(1.3, 141.0, 4.4, 118.0, charges)},
        {"m_a": membrane("c_a", "bath", 8e-10, 8e-12, LEAK, 0.09)},
        channels={"k_a": channel("m_a", 7e-09, 0.9)},
        gauge="bath",
        controls={"leak": {"m_a": ONES}, "pump": {"m_a": ONES}, "channel": PATH, "junction": []},
    )


PATH = "the pool's path (SPEC.md section 3.2)"


def sheet(scale=1.0):
    """Three cells and two gated junctions on a schedule; no pump, leak or channel."""
    volumes = {"c_a": 0.5, "c_b": 0.45, "c_c": 0.62}
    voltages = {"c_a": -0.021, "c_b": -0.004, "c_c": 0.013}
    cells = {
        name: cell(volume, 2.9e-12, voltages[name], 9.0, 141.0, 9.5)
        for name, volume in volumes.items()
    }
    charges = [c["initial_charge_C"] for c in cells.values()]
    none = {"Na": 0.0, "K": 0.0, "Cl": 0.0}
    carried = {"Na": 5.1e-10 * scale, "K": 7.4e-10 * scale, "Cl": 7.9e-10 * scale}
    steps = [[0.0, 1.0], [8e-05, 0.5], [0.00016, 0.0]]
    return closed(
        cells,
        {"bath": region(5.5, 144.0, 4.2, 119.0, charges)},
        {f"m_{n[-1]}": membrane(n, "bath", 2.9e-10, 2.9e-12, none) for n in cells},
        junctions={
            "j_ab": junction("c_a", "c_b", 5.7e-11, carried, 0.3),
            "j_bc": junction("c_b", "c_c", 5.5e-11, carried, 0.8),
        },
        gauge="bath",
        controls={
            "leak": {f"m_{n[-1]}": ONES for n in cells},
            "pump": [],
            "channel": [],
            "junction": {"j_ab": steps, "j_bc": steps},
        },
    )


def pool(channel_id, position, seeds):
    """A pool whose events fall inside the short horizon."""
    return {
        "channel": channel_id,
        "stream_id": position,
        "pool": {
            "model": "pool_model",
            "topology": "pool_topology",
            "initial_nodes": [10, 12, 14, 16, 18],
            "initial_bond_indices": [20, 21, 24, 26, 28],
            "root_node": 10,
            "initial_free_trimers": 40,
            "pool_volume_L": 4e-15,
            "k_on_M_inv_s": 2e7,
            "k_close_s_inv": 3e4,
            "k_off_s_inv": 9e3,
            "k_fragment_dissolve_s_inv": 2.0,
            "world_id_start": 0,
            "worlds": 3,
            "end_time_s": END_S,
            "max_events_per_world": 4000,
        },
        "harness": {
            "event_chunk_size": 64,
            "recording": "summary",
            "max_output_bytes": 268435456,
            "max_wall_seconds": 300.0,
        },
        "seeds": seeds,
    }


def world(consumer, ionic, *, order=4, **more):
    return {
        "consumer": consumer,
        "ionic": ionic,
        **more,
        "scales": {},
        "p": order,
        "amount_refs": {},
        "closure_terms_V": {},
    }


def grid(spacing, potentials):
    history = {"first_s": 0.0, "last_s": END_S, "spacing_s": spacing}
    return {"history_times": history, "potential_times_s": potentials}


def run(name, consumer, family, of, *, seed=None, at=None, step=None, role="judged", variant=None):
    return {
        "name": name,
        "consumer": consumer,
        "family": family,
        "world": of,
        "seed_index": seed,
        "world_id": at,
        "step_s": step,
        "role": role,
        "variant": variant,
    }


SLOW = "inv_sample_slow h=4e-05"  # Ended by the driver's own clock: a harness refusal.
OFF_GRID = "inv_sample_off_grid h=4e-05"  # Made by the switch: a change that splits a step.


def invented():
    """The invented inputs: one run of each kind, refused runs of each kind, a plant and a restart
    of each kind, one run off its grid and one on the second-order integrator."""
    coupling = {"law": "assembly_observable", "active": 1.0, "inactive": 0.0}
    summary = {"final_s": END_S, "coupling": coupling}
    unsupported, cold, tight = sheet(), sheet(), sheet(scale=3e3)
    for m in unsupported["membranes"].values():
        m["passive"]["law"] = "no_such_law"
    cold["temperature_K"] = 150.0
    off = sheet()
    off["controls"]["junction"]["j_ab"] = [[0.0, 1.0], [9.1e-05, 0.5]]
    plain = grid(4e-05, [0.0, 4e-05, 0.00012, 0.0002])
    worlds = {
        "inv_sample_cluster": world("jupiter", cluster({"k_a": ONES, "k_b": ONES}), **plain),
        "inv_sample_unsupported": world("jupiter", unsupported, **plain),
        "inv_sample_cold": world("jupiter", cold, **plain),
        "inv_sample_tight": world("jupiter", tight, **plain),
        "inv_sample_slow": world("jupiter", sheet(), **plain),
        "inv_sample_lone": world(
            "cell",
            lone(),
            summary_times_s=[END_S],
            pools={"c_a": pool("k_a", 0, [611, 612])},
            **summary,
        ),
        "inv_sample_pair": world(
            "base",
            cluster(PATH),
            summary_times_s=[8e-05, END_S],
            pools={"c_a": pool("k_a", 0, [711, 712]), "c_b": pool("k_b", 1, [721, 722])},
            **summary,
        ),
        "inv_sample_sheet": world("integrated", sheet(), **grid(4e-05, [0.0, 8e-05, 0.00016])),
        "inv_sample_off_grid": world("integrated", off, **grid(4e-05, [0.0, 8e-05, 0.00016])),
        "inv_sample_imex": world("jupiter", cluster({"k_a": ONES, "k_b": ONES}), order=2, **plain),
    }
    step, coarse = 2e-05, 4e-05
    a, b, c, d = "inv_sample_cluster", "inv_sample_lone", "inv_sample_pair", "inv_sample_sheet"
    runs = [
        run(f"{a} h={step!r}", "jupiter", a, a, step=step),
        run(
            f"{a} h={step!r} restart",
            "jupiter",
            None,
            a,
            step=step,
            role="support",
            variant="restart at 0.00012",
        ),
        run(f"{a} plant channel", "jupiter", a, a, step=step, role="plant", variant="inv_plant")
        | {
            "declared_change": [
                {"path": ["channels", "k_a", "max_permeability_m_per_s"], "value": 5e-10}
            ]
        },
        run(
            "inv_sample_unsupported h=4e-05", "jupiter", None, "inv_sample_unsupported", step=coarse
        ),
        run("inv_sample_cold h=4e-05", "jupiter", None, "inv_sample_cold", step=coarse),
        run("inv_sample_tight h=4e-05", "jupiter", None, "inv_sample_tight", step=coarse),
        run("inv_sample_slow h=4e-05", "jupiter", None, "inv_sample_slow", step=coarse),
        run("inv_sample_lone s1 pool", "cell", None, b, seed=1, variant="pool"),
        run(
            "inv_sample_lone s1 pool restart",
            "cell",
            None,
            b,
            seed=1,
            role="support",
            variant="pool restart at 0.0001",
        ),
        run(
            f"inv_sample_lone s1 w2 h={step!r}",
            "cell",
            "inv_sample_lone s1 w2",
            b,
            seed=1,
            at=2,
            step=step,
            variant="ionic",
        ),
        run("inv_sample_pair s0 pool", "base", None, c, seed=0, variant="pool"),
        run(
            "inv_sample_pair s0 pool restart",
            "base",
            None,
            c,
            seed=0,
            role="support",
            variant="pool restart at 0.0001",
        ),
        run(
            f"inv_sample_pair s0 w1 h={step!r}",
            "base",
            "inv_sample_pair s0 w1",
            c,
            seed=0,
            at=1,
            step=step,
            variant="ionic",
        ),
        run(f"{d} h={coarse!r}", "integrated", d, d, step=coarse),
        run(OFF_GRID, "integrated", None, "inv_sample_off_grid", step=coarse),
        run("inv_sample_imex h=2e-05", "jupiter", None, "inv_sample_imex", step=step),
    ]
    runs.append(
        run(
            "inv_sample_pair plant swapped",
            "base",
            "inv_sample_pair s0 w1",
            c,
            seed=0,
            at=1,
            step=step,
            role="plant",
            variant="inv_swapped",
        )
        | {"declared_change": [{"exchange_channels": ["c_a", "c_b"]}]}
    )
    return {"schema": SCHEMA, "part": 1, "constants": {}, "worlds": worlds, "runs": runs}


def make(directory, workers=1):
    """Make the invented runs and their tables under a new folder, as a campaign is made."""
    directory.mkdir(parents=True)
    path = directory / "inputs_sample.json"
    path.write_text(json.dumps(invented(), indent=1) + "\n")
    inputs = Inputs(path)
    owed = directory / "retry_owed.json"
    names = ["inv_sample_sheet h=2e-05 retry"]
    note = {"kind": "ensemble-reexpression retry owed, version 1", "part": 1, "runs": names}
    owed.write_text(json.dumps(note | {"why": {"inv_sample_sheet": ["voltage: order"]}}) + "\n")
    driver.one(inputs, inputs.run(SLOW), directory, max_seconds=0.05)
    driver.one(inputs, inputs.run(OFF_GRID), directory, off_grid=True)
    command = ["all", "--inputs", str(path), "--runs", str(directory), "--workers", str(workers)]
    for more in ([], ["--owed", str(owed)]):
        driver.main([*command, *more])
    folders = driver.Folders(directory)
    exporter.write(exporter.tables(inputs, folders), directory / "table")
    exporter.write(exporter.tables(inputs, folders, owed=owed), directory / "table-retry")
    faults = exporter.check(directory / "table") + exporter.check(directory / "table-retry")
    print(json.dumps({"faults": faults}))
    return faults


# ------------------------------------------------------------------ the scrub


_VERSIONED = re.compile(r"(?:[A-Za-z][A-Za-z0-9_]*\.)*[A-Za-z][A-Za-z0-9_]*@[0-9]+")
_HEX = re.compile(r"[0-9a-f]{40,64}")
_UTC = re.compile(r"\d{4}-\d\d-\d\dT[0-9:.+Z]+")
TIMES = ("t", "potential_t")


def scrubbed(table):
    """A table with every number replaced by a meaningless one of its type, every registered string
    by a placeholder, every fingerprint by a run of zeros, and what a source is by its key."""
    named = {}

    def placeholder(text):
        return named.setdefault(text, f"registered_string_{len(named):02}")

    def words(text):
        if _VERSIONED.fullmatch(text) or text == "rk4":
            return placeholder(text)
        if _HEX.fullmatch(text):
            return "0" * len(text)
        return "a time" if _UTC.fullmatch(text) else text

    def walk(value):
        if isinstance(value, bool) or value is None:
            return value
        if isinstance(value, int):
            return 7
        if isinstance(value, float):
            return 0.5
        if isinstance(value, str):
            return words(value)
        if isinstance(value, list):
            return [walk(v) for v in value]
        return {key: walk(v) for key, v in value.items()}

    out = walk(table)
    for made in out["runs"].values():
        for key in TIMES:  # A run's times still increase, and begin at 0 but for a restart's.
            first = 0 if made["restart"] is None else 1
            made[key] = [0.75 * (k + first) for k in range(len(made[key]))]
        made["declared_strings"] = sorted(made["declared_strings"])
        made["source"] = {
            key: value if not isinstance(value, str) or _HEX.fullmatch(value) else f"a {key}"
            for key, value in made["source"].items()
        }
    return out


def scrub(directory, destination):
    """The format sample of a folder of made tables."""
    for folder in ("table", "table-retry"):
        target = destination / folder
        target.mkdir(parents=True)
        for path in sorted((directory / folder).glob("table_*.json")):
            (target / path.name).write_text(exporter.text(scrubbed(read_json(path))))
        exporter.write_sums(target)
    return exporter.check(destination / "table") + exporter.check(destination / "table-retry")


# ------------------------------------------------------------------ the list of keys and types


# {a map's key, or (its parent's, its own) where the same word is also an object's: what its keys
# are}. Each is printed as a placeholder, so the list has one line for each place and not for each
# entity.
MAPS = {
    "rows": ("<readout>", "<entity ID>"),
    "potentials": ("<readout>", "<entity ID>"),
    "path": ("<cell ID>", "<world ID>"),
    ("entry", "pool"): ("<cell ID>",),
    ("pool run", "pool"): ("<cell ID>",),
    ("pool run", "inputs"): ("<cell ID>",),
    ("pool run", "checks"): ("<cell ID>",),
    ("definition", "pools"): ("<cell ID>",),
    "strings": ("<label>",),
    "cells": ("<cell ID>",),
    "outside": ("<region ID>",),
    "membranes": ("<membrane ID>",),
    "channels": ("<channel ID>",),
    "junctions": ("<junction ID>",),
    "faces": ("<face ID>",),
    "species": ("<species>",),
    "stoichiometry": ("<species>",),
    "initial_amount_fmol": ("<species>",),
    "permeability_m_per_s": ("<species>",),
    "diffusivity_m2_per_s": ("<species>",),
    "material_tolerance_fmol": ("<species>",),
    "material_balance_atol_fmol": ("<species>",),
    ("controls", "leak"): ("<membrane ID>",),
    ("controls", "pump"): ("<membrane ID>",),
    ("controls", "channel"): ("<channel ID>",),
    ("controls", "junction"): ("<junction ID>",),
    "pool_seeds": ("<cell ID>",),
    "switch_list": ("<channel ID>",),
}


def keys(folder):
    """Every key path and its types over a folder of tables, to the leaf, in two lists: an ionic
    run's entry ("entry") and a pool run's ("pool run"). {path: sorted types}."""
    found = {}

    def walk(path, value, names):
        found.setdefault(path, set()).add(type(value).__name__)
        if isinstance(value, dict):
            parent, own = path.split(".")[-2:] if "." in path else ("", path)
            own = own.removesuffix("[]")
            levels = names or MAPS.get((parent, own)) or MAPS.get(own) or ()
            for key, item in value.items():
                walk(f"{path}.{levels[0] if levels else key}", item, levels[1:])
        elif isinstance(value, list):
            for item in value:
                walk(f"{path}[]", item, ())

    for path in sorted(folder.glob("table_*.json")):
        table = read_json(path)
        for made in table.pop("runs").values():
            for key, value in made.items():
                head = "pool run" if made["step_s"] is None else "entry"
                walk(f"{head}.{key}", value, ())
        for key, value in table.items():
            walk(f"table.{key}", value, ())
    return {path: sorted(types) for path, types in sorted(found.items())}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("make")
    command.add_argument("directory", type=Path)
    command.add_argument("--workers", type=int, default=1)
    command = commands.add_parser("scrub")
    command.add_argument("directory", type=Path)
    command.add_argument("destination", type=Path)
    commands.add_parser("keys").add_argument("folder", type=Path)
    args = parser.parse_args(argv)
    if args.command == "make":
        return 1 if make(args.directory, args.workers) else 0
    if args.command == "scrub":
        faults = scrub(args.directory, args.destination)
        print(json.dumps({"faults": faults}))
        return 1 if faults else 0
    for path, types in keys(args.folder).items():
        print(f"{path}: {', '.join(types)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
