"""The structure-only mode (TABLE section 7): keys and types to the leaf, for the format sample. No
number is read for its value.

The files are read by the code that reads the registered tables (`table.TableSet`). What each run is
(a pool run, a restart, a refused run) is taken from the entry itself, since the sample's worlds are
invented.
"""

from __future__ import annotations

import re

from . import constants as c
from .strictjson import is_integer, is_number
from .table import TableSet

ROW_SERIES = re.compile(
    r"(n_cell_\w+|n_out_\w+|leak_\w+|channel_\w+|junction_(?!gate$)\w+|face_\w+|pump|"
    r"gate_m|gate_h|junction_gate|"
    r"heat_leak|heat_pump|heat_channel|heat_junction|heat_face|work_pump)"
)
BLOCK_KEYS = (
    "temperature_K",
    "species",
    "cells",
    "outside",
    "closure",
    "membranes",
    "channels",
    "junctions",
    "faces",
    "controls",
    "material_tolerance_fmol",
    "end_s",
)
MAY_BE_ABSENT = (
    "channels",
    "junctions",
    "faces",
    "controls",
)  # empty by default (SPEC section 2.4)
NUMBER, TEXT, MAP = "a number", "a string", "a map of numbers"
ENTITIES = {
    "cells": {
        "volume_pL": NUMBER,
        "initial_amount_fmol": MAP,
        "fixed_charge_equivalent_fmol": NUMBER,
        "initial_voltage_V": NUMBER,
        "initial_charge_C": NUMBER,
    },
    "outside": {
        "volume_pL": NUMBER,
        "initial_amount_fmol": MAP,
        "fixed_charge_equivalent_fmol": NUMBER,
        "initial_charge_C": NUMBER,
    },
    "membranes": {
        "inside": TEXT,
        "outside": TEXT,
        "area_m2": NUMBER,
        "capacitance_F": NUMBER,
        "passive": {"law": TEXT, "permeability_m_per_s": MAP},
    },
    "channels": {
        "membrane_id": TEXT,
        "species_id": TEXT,
        "kinetic_law": TEXT,
        "max_permeability_m_per_s": NUMBER,
        "abundance": NUMBER,
        "initial_gate": MAP,
    },
    "junctions": {
        "from_cell": TEXT,
        "to_cell": TEXT,
        "area_m2": NUMBER,
        "permeability_m_per_s": MAP,
        "gate": {
            "initial_gate": NUMBER,
            "law": TEXT,
            "minimum_open_fraction": NUMBER,
            "threshold_voltage_V": NUMBER,
        },
    },
    "faces": {
        "sender": TEXT,
        "receiver": TEXT,
        "area_m2": NUMBER,
        "length_m": NUMBER,
        "diffusivity_m2_per_s": MAP,
        "law": TEXT,
    },
}
PUMP = {
    "law": TEXT,
    "roles": {"sodium": TEXT, "potassium": TEXT},
    "stoichiometry": MAP,
    "capacity_fmol_per_s": NUMBER,
    "km_na_mM": NUMBER,
    "km_k_mM": NUMBER,
    "km_atp_mM": NUMBER,
    "metabolism": {
        "kind": TEXT,
        "atp_mM": NUMBER,
        "adp_mM": NUMBER,
        "pi_mM": NUMBER,
        "delta_g0_J_per_mol": NUMBER,
    },
}
POOL = {
    "model": TEXT,
    "topology": TEXT,
    "initial_nodes": list,
    "initial_free_trimers": NUMBER,
    "pool_volume_L": NUMBER,
    "k_on_M_inv_s": NUMBER,
    "k_close_s_inv": NUMBER,
    "k_off_s_inv": NUMBER,
    "k_fragment_dissolve_s_inv": NUMBER,
    "worlds": NUMBER,
    "end_time_s": NUMBER,
    "max_events_per_world": NUMBER,
}


class Faults:
    """The departures from the contract's structure, by run."""

    def __init__(self):
        self.items = []

    def need(self, good, where, what) -> bool:
        """Record a departure where it is not good."""
        if not good:
            self.items.append(f"{where}: {what}")
        return bool(good)

    def shape(self, value, wanted, where):
        """A value against a template of keys and types. Extra keys are allowed."""
        if wanted == NUMBER:
            self.need(is_number(value), where, "no number")
        elif wanted == TEXT:
            self.need(isinstance(value, str) and value, where, "no string")
        elif wanted == MAP:
            good = isinstance(value, dict) and value and all(is_number(v) for v in value.values())
            self.need(good, where, "no map of numbers")
        elif wanted is list:
            self.need(
                isinstance(value, list) and all(is_integer(v) for v in value),
                where,
                "no list of integers",
            )
        elif self.need(isinstance(value, dict), where, "no object"):
            for key, item in wanted.items():
                if self.need(key in value, f"{where}.{key}", "missing"):
                    self.shape(value[key], item, f"{where}.{key}")


def table_faults(folder, consumers=None, part: int = c.PART) -> dict:
    """Every structural departure of the tables of a folder, and what kinds of run they hold."""
    from pathlib import Path

    folder = Path(folder)
    found = consumers or sorted(
        p.name[len("table_") : -len(".json")] for p in folder.glob("table_*.json")
    )
    tables = TableSet.read(folder, found, part)
    out = Faults()
    out.need(found, str(folder), "no table")
    for what, detail in tables.flags:
        out.need(False, what, detail)
    kinds = {}
    for file in tables.files.values():
        for reason in file.refusals:
            out.need(False, file.name, f"refused: {reason}")
        out.need(file.data is not None, file.name, "not read")
    for (consumer, name), entry in tables.runs.items():
        kind = entry_faults(entry, f"{consumer} / {name}", out)
        kinds[kind] = kinds.get(kind, 0) + 1
    return {
        "folder": str(folder),
        "consumers": list(found),
        "kinds_of_run": kinds,
        "faults": out.items,
    }


def entry_faults(entry, where: str, out: Faults) -> str:
    """One run's entry against TABLE section 3. Returns what kind of run it is."""
    if not out.need(isinstance(entry, dict), where, "no object"):
        return "unreadable"
    for key in c.RUN_KEYS:
        out.need(key in entry, f"{where}.{key}", "missing")
    get = entry.get
    pool = get("pool") is not None
    inputs = get("inputs")
    assembly = isinstance(inputs, dict) and "assembly" in inputs
    refusal = get("refusal")
    # A refused run without a row may hold a declaration that the engine could not read, or none at
    # all (Amendment 2, item 7).
    bare = refusal is not None and get("t") == [] and not pool
    out.need(
        get("status") in ("completed", "refused"),
        f"{where}.status",
        "neither completed nor refused",
    )
    out.need(
        (get("status") == "completed") == (refusal is None),
        f"{where}.refusal",
        "disagrees with status",
    )
    out.need(isinstance(get("world"), str), f"{where}.world", "no string")
    out.need(
        get("variant") is None or isinstance(get("variant"), str),
        f"{where}.variant",
        "neither a string nor null",
    )
    for key in ("seed_index", "world_id"):
        out.need(
            get(key) is None or is_integer(get(key)),
            f"{where}.{key}",
            "neither an integer nor null",
        )
    if pool:
        for key in ("step_s", "steps"):
            out.need(get(key) is None, f"{where}.{key}", "not null in a pool run")
    else:
        out.need(is_number(get("step_s")) or bare, f"{where}.step_s", "no number")
        out.need(is_integer(get("steps")) or refusal is not None, f"{where}.steps", "no integer")
    rows_faults(entry, where, out, pool)
    pool_faults(entry, where, out, pool)
    if pool:
        if out.need(isinstance(inputs, dict) and inputs, f"{where}.inputs", "no object by cell"):
            for cell, block in inputs.items():
                out.shape(
                    block,
                    {"channel": TEXT, "stream_id": NUMBER, "seed": NUMBER, "pool": POOL},
                    f"{where}.inputs.{cell}",
                )
    elif bare:
        out.need(isinstance(inputs, dict), f"{where}.inputs", "no object")
    else:
        block_faults(inputs, f"{where}.inputs", out)
        if assembly:
            assembly_faults(inputs["assembly"], f"{where}.inputs.assembly", out)
    strings, declared = get("strings"), get("declared_strings")
    good = (
        isinstance(strings, dict)
        and (strings or bare)
        and all(isinstance(v, str) and v for v in strings.values())
    )
    out.need(good, f"{where}.strings", "no map of strings")
    if out.need(
        isinstance(declared, list) and all(isinstance(s, str) for s in declared),
        f"{where}.declared_strings",
        "no list of strings",
    ):
        out.need(
            declared == sorted(set(declared)),
            f"{where}.declared_strings",
            "not sorted, or a string stands twice",
        )
    for key in ("definition", "checks"):
        out.need(get(key) is not None, f"{where}.{key}", "null")
    restart = get("restart")
    if restart is not None and out.need(
        isinstance(restart, dict), f"{where}.restart", "neither null nor an object"
    ):
        out.need(is_number(restart.get("time_s")), f"{where}.restart.time_s", "no number")
        out.need(isinstance(restart.get("through"), str), f"{where}.restart.through", "no string")
        if pool:
            out.need(
                "step_index" in restart and restart["step_index"] is None,
                f"{where}.restart.step_index",
                "not null in a pool restart",
            )
        else:
            out.need(
                is_integer(restart.get("step_index")), f"{where}.restart.step_index", "no integer"
            )
    out.need(get("host_patch") is None, f"{where}.host_patch", "not null")
    if refusal is not None and out.need(isinstance(refusal, dict), f"{where}.refusal", "no object"):
        out.need(
            refusal.get("kind") in c.REFUSAL_KINDS,
            f"{where}.refusal.kind",
            "not one of the four kinds",
        )
        out.need(isinstance(refusal.get("message"), str), f"{where}.refusal.message", "no string")
        if refusal.get("kind") == "check":
            out.need(is_number(refusal.get("time_s")), f"{where}.refusal.time_s", "no number")
        else:
            out.need(
                "time_s" in refusal and refusal["time_s"] is None,
                f"{where}.refusal.time_s",
                "not null",
            )
    source = get("source")
    if out.need(isinstance(source, dict), f"{where}.source", "no object"):
        for key in c.SOURCE_STRINGS:
            out.need(
                isinstance(source.get(key), str) and source.get(key),
                f"{where}.source.{key}",
                "no string",
            )
        out.need(
            isinstance(source.get("checkout_dirty"), bool),
            f"{where}.source.checkout_dirty",
            "no boolean",
        )
        out.need(
            is_integer(source.get("blas_threads")), f"{where}.source.blas_threads", "no integer"
        )
    out.need(isinstance(get("record"), str) and get("record"), f"{where}.record", "no string")
    digest = get("record_sha256")
    out.need(
        isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
        f"{where}.record_sha256",
        "not 64 hex digits",
    )
    if "off_grid" in entry:
        out.need(isinstance(entry["off_grid"], bool), f"{where}.off_grid", "no boolean")
    what = "pool run" if pool else "assembly ionic run" if assembly else "ionic run"
    if restart is not None:
        what += ", restart"
    if isinstance(refusal, dict):
        what += f", refused ({refusal.get('kind')})"
    return what


def rows_faults(entry, where, out: Faults, pool: bool):
    """`t`, `rows`, `potential_t` and `potentials`."""
    for times, table in (("t", "rows"), ("potential_t", "potentials")):
        held, values = entry.get(times), entry.get(table)
        if not out.need(
            isinstance(held, list) and all(is_number(v) for v in held),
            f"{where}.{times}",
            "no list of numbers",
        ):
            continue
        if not out.need(isinstance(values, dict), f"{where}.{table}", "no object"):
            continue
        if pool:
            out.need(held == [] and values == {}, f"{where}.{times}", "not empty in a pool run")
            continue
        out.need(
            bool(held) == bool(values),
            f"{where}.{table}",
            f"disagrees with {times}: one is empty and the other is not",
        )
        for name, entities in values.items():
            here = f"{where}.{table}.{name}"
            known = (
                ROW_SERIES.fullmatch(name) if table == "rows" else name in ("voltage", "phi_out")
            )
            out.need(known or table == "rows", here, "no potential of READOUTS section 2")
            if not out.need(isinstance(entities, dict) and entities, here, "no object by entity"):
                continue
            for entity, column in entities.items():
                good = (
                    isinstance(column, list)
                    and len(column) == len(held)
                    and all(is_number(v) for v in column)
                )
                out.need(good, f"{here}.{entity}", f"no list of numbers as long as {times}")


def pool_faults(entry, where, out: Faults, pool: bool):
    """`pool` and `path`."""
    path = entry.get("path")
    if not pool:
        out.need(path is None, f"{where}.path", "not null in an ionic run")
        return
    if out.need(
        isinstance(entry["pool"], dict) and entry["pool"], f"{where}.pool", "no object by cell"
    ):
        for cell, block in entry["pool"].items():
            here = f"{where}.pool.{cell}"
            if not out.need(isinstance(block, dict), here, "no object"):
                continue
            for key in ("seed", "stream_id"):
                out.need(is_integer(block.get(key)), f"{here}.{key}", "no integer")
            arrays = block.get("arrays")
            if out.need(isinstance(arrays, dict), f"{here}.arrays", "no object"):
                for name in c.POOL_ARRAYS:
                    out.need(
                        nested(arrays.get(name)),
                        f"{here}.arrays.{name}",
                        "no nested list of numbers by world",
                    )
    if out.need(isinstance(path, dict) and path, f"{where}.path", "no object by cell"):
        for cell, worlds in path.items():
            here = f"{where}.path.{cell}"
            if out.need(isinstance(worlds, dict) and worlds, here, "no object by world ID"):
                for world, events in worlds.items():
                    out.need(
                        events_shape(events), f"{here}.{world}", "no list of [time, availability]"
                    )
        if isinstance(entry["pool"], dict):
            out.need(
                set(path) == set(entry["pool"]), f"{where}.path", "its cells are not the pool's"
            )


def nested(value) -> bool:
    """True for a nested list of numbers or booleans, by world."""
    if not isinstance(value, list) or not value:
        return False

    def leaf(item):
        return (
            all(leaf(part) for part in item)
            if isinstance(item, list)
            else is_number(item) or isinstance(item, bool)
        )

    return leaf(value)


def events_shape(value) -> bool:
    """True for a list of [time, availability]."""
    return isinstance(value, list) and all(
        isinstance(e, list) and len(e) == 2 and all(is_number(v) for v in e) for e in value
    )


def block_faults(block, where, out: Faults):
    """An ionic run's block (SPEC section 2.5), to the leaf. Defaults may be absent."""
    if not out.need(isinstance(block, dict), where, "no object"):
        return
    for key in BLOCK_KEYS:
        out.need(key in block or key in MAY_BE_ABSENT, f"{where}.{key}", "missing")
    for key, wanted in (
        ("temperature_K", NUMBER),
        ("species", MAP),
        ("material_tolerance_fmol", MAP),
        ("end_s", NUMBER),
    ):
        if key in block:
            out.shape(block[key], wanted, f"{where}.{key}")
    if "closure" in block:
        out.shape(block["closure"], {"gauge_reference": TEXT}, f"{where}.closure")
    for key, wanted in ENTITIES.items():
        found = block.get(key, [])
        if found == [] and key in MAY_BE_ABSENT:
            continue
        if not out.need(isinstance(found, dict), f"{where}.{key}", "neither a map nor []"):
            continue
        for name, entity in found.items():
            out.shape(entity, wanted, f"{where}.{key}.{name}")
            if key == "membranes" and isinstance(entity, dict) and entity.get("pump") is not None:
                out.shape(entity["pump"], PUMP, f"{where}.{key}.{name}.pump")
    controls = block.get("controls", {})
    if out.need(isinstance(controls, dict), f"{where}.controls", "no object"):
        for group, schedules in controls.items():
            if schedules == []:
                continue
            if out.need(
                isinstance(schedules, dict), f"{where}.controls.{group}", "neither a map nor []"
            ):
                for name, schedule in schedules.items():
                    out.need(
                        events_shape(schedule) and schedule,
                        f"{where}.controls.{group}.{name}",
                        "no list of [time, value]",
                    )


def assembly_faults(assembly, where, out: Faults):
    """`inputs.assembly` holds exactly its four keys (TABLE section 3)."""
    if not out.need(isinstance(assembly, dict), where, "no object"):
        return
    out.need(set(assembly) == set(c.ASSEMBLY_KEYS), where, f"its keys are {sorted(assembly)}")
    for key in ("assembly_observable", "composed_file_fingerprint"):
        out.need(
            isinstance(assembly.get(key), str) and assembly.get(key), f"{where}.{key}", "no string"
        )
    seeds = assembly.get("pool_seeds")
    out.need(
        isinstance(seeds, dict) and seeds and all(is_integer(v) for v in seeds.values()),
        f"{where}.pool_seeds",
        "no map of integers",
    )
    switches = assembly.get("switch_list")
    good = (
        isinstance(switches, dict) and switches and all(events_shape(v) for v in switches.values())
    )
    out.need(good, f"{where}.switch_list", "no map of lists of [time, availability]")
