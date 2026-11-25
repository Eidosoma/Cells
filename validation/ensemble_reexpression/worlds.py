"""A world's block (spec/SPEC.md §2) and the engine's definition of it: each is written from the
other, section by section.

**write** makes a raw definition of the inner tissue model, version 3, from a block. Every number in
it is the block's own double. **read** makes a block from a definition the engine parsed (its
canonical JSON form), in the block's own names, with a label for every registered string and every
default written out. Nothing of inputs.json enters `read`.

**A section** holds one or more of the block's top keys, with how they are written and how they are
read. Part 2 adds its sections to SECTIONS (in order: a later section may add to what an earlier one
wrote) and its labels to labels.py; nothing else here knows which sections there are. A key of a
block that no section holds, or a field of an entity that no section has a place for, is refused by
name, so nothing in a block is dropped in silence. A field that a block lacks is left out of the
definition, for the engine to refuse. The defaults (spec/SPEC.md §2.4) may be left out of a block.
"""

import copy
import math

from validation.ensemble_reexpression import stores
from validation.ensemble_reexpression.blocks import (
    ONES,
    Section,
    channel_rows,
    entities,
    groups,
    known,
    mapped,
    no_section,
    pairs,
    read_channels,
    rest,
    taken,
)
from validation.ensemble_reexpression.inputs import BESIDE, EPS, INNER
from validation.ensemble_reexpression.labels import LABELS, label, string

RELATIVE = 1e-12  # The echo's precision (spec/SPEC.md §2.4).


# ------------------------------------------------------------------ the species and compartments


def _write_species(block, raw):
    raw["model"]["temperature_K"] = block["temperature_K"]
    raw["model"]["species"] = [{"id": s, "valence": z} for s, z in block["species"].items()]


def _read_species(raw):
    model = raw["model"]
    species = {}
    for entry in model["species"]:
        more = rest(entry, {"id", "valence"}, {})
        species[entry["id"]] = entry["valence"] if not more else more | taken(entry, ("valence",))
    return {"temperature_K": model["temperature_K"], "species": species}


_COMPARTMENT = (
    "volume_pL",
    "initial_amount_fmol",
    "fixed_charge_equivalent_fmol",
    "initial_charge_C",
)
_CLOSED = {"reservoir": False, "boundary_potential_V": 0.0}  # No region is held (SPEC §2.1).


def _write_compartments(block, raw):
    raw["model"]["cells"] = [
        {"id": name} | taken(known(c, (*_COMPARTMENT, "initial_voltage_V"), name), _COMPARTMENT)
        for name, c in entities(block["cells"])
    ]
    raw["model"]["extracellular"] = [
        {"id": name} | taken(known(c, _COMPARTMENT, name), _COMPARTMENT) | _CLOSED
        for name, c in entities(block["outside"])
    ]


def _read_compartments(raw):
    model = raw["model"]
    capacitance = {}
    for membrane in model["membranes"]:
        capacitance.setdefault(membrane["inside"], []).append(membrane["capacitance_F"])
    cells, outside = {}, {}
    for c in model["cells"]:
        out = taken(c, _COMPARTMENT) | rest(c, {"id", *_COMPARTMENT}, {})
        own = capacitance.get(c["id"], [])
        if len(own) == 1:  # "divided by the capacitance of its membrane" (SPEC §2.4).
            out["initial_voltage_V"] = c["initial_charge_C"] / own[0]
        order = (*_COMPARTMENT[:-1], "initial_voltage_V", _COMPARTMENT[-1])
        cells[c["id"]] = {k: out[k] for k in (*order, *out) if k in out}
    for c in model["extracellular"]:
        outside[c["id"]] = taken(c, _COMPARTMENT) | rest(c, {"id", *_COMPARTMENT}, _CLOSED)
    return {"cells": cells, "outside": outside}


def _write_closure(block, raw):
    closure = known(block["closure"], ("gauge_reference",), "closure")
    raw["model"]["closure"] = {"law": LABELS["closure"]} | taken(closure, ("gauge_reference",))


def _read_closure(raw):
    closure = raw["model"]["closure"]
    return {"closure": rest(closure, {"law"}, {})}


# ------------------------------------------------------------------ the membranes and their pumps


_PASSIVE = ("law", "permeability_m_per_s")
_PUMP = (
    "law",
    "roles",
    "stoichiometry",
    "capacity_fmol_per_s",
    "km_na_mM",
    "km_k_mM",
    "km_atp_mM",
    "metabolism",
)
_FUEL = ("kind", "atp_mM", "adp_mM", "pi_mM", "delta_g0_J_per_mol")
_MEMBRANE = ("inside", "outside", "area_m2", "capacitance_F")


def pump_id(membrane):
    """The ID a membrane's pump is declared with: the block keys a pump by its membrane."""
    return f"pump_{membrane}"


def _write_pump(name, pump):
    if pump is None:
        return None
    out = {"id": pump_id(name)} | taken(known(pump, _PUMP, f"{name}'s pump"), _PUMP)
    if "law" in out:
        out["law"] = string(out["law"])
    if isinstance(out.get("metabolism"), dict):
        fuel = known(out["metabolism"], _FUEL, f"{name}'s fuel")
        if "kind" in fuel:
            fuel["kind"] = string(fuel["kind"])
    return out


def _write_membranes(block, raw):
    rows = []
    for name, m in entities(block["membranes"]):
        known(m, (*_MEMBRANE, "passive", "pump"), name)
        passive = known(m["passive"], _PASSIVE, f"{name}'s passive route")
        row = {"id": name} | taken(m, _MEMBRANE) | taken(passive, ("permeability_m_per_s",))
        row["law"] = string(passive["law"]) if "law" in passive else LABELS["constant_field"]
        row["pump"] = _write_pump(name, m.get("pump"))
        row["calcium_pump"] = None  # None in Part 1 (SPEC §2.1); a later section may set it.
        rows.append(row)
    raw["model"]["membranes"] = rows


def _read_pump(pump):
    if pump is None:
        return None
    out = taken(pump, _PUMP) | rest(pump, {"id", *_PUMP}, {})
    out["law"] = label(out["law"])
    fuel = dict(out["metabolism"])
    out["metabolism"] = fuel | {"kind": label(fuel["kind"])}
    return out


def _read_membranes(raw):
    out = {}
    for m in raw["model"]["membranes"]:
        row = taken(m, _MEMBRANE)
        row["passive"] = {
            "law": label(m["law"]),
            "permeability_m_per_s": dict(m["permeability_m_per_s"]),
        }
        row["pump"] = _read_pump(m["pump"])
        named = {"id", *_MEMBRANE, "permeability_m_per_s", "law", "pump"}
        out[m["id"]] = row | rest(m, named, {"calcium_pump": None})
    return {"membranes": mapped(out)}


# ------------------------------------------------------------------ channels


def _write_channels(block, raw):
    raw["model"]["channels"] = channel_rows(block.get("channels"))


def _read_channels(raw):
    return {"channels": mapped(read_channels(raw["model"]["channels"]))}


# ------------------------------------------------------------------ junctions and faces


_JUNCTION = ("area_m2", "permeability_m_per_s")
_GATE = ("law", "threshold_voltage_V", "minimum_open_fraction", "initial_gate")


def _write_junctions(block, raw):
    rows = []
    for name, j in entities(block.get("junctions")):
        known(j, ("from_cell", "to_cell", *_JUNCTION, "gate"), name)
        gate = taken(known(j["gate"], _GATE, f"{name}'s gate"), _GATE)
        if "law" in gate:
            gate["law"] = string(gate["law"])
        row = {"id": name, "sender": j["from_cell"], "receiver": j["to_cell"]}
        rows.append(row | taken(j, _JUNCTION) | {"law": LABELS["constant_field"], "gate": gate})
    raw["model"]["junctions"] = rows


def _read_junctions(raw):
    out = {}
    for j in raw["model"]["junctions"]:
        row = {"from_cell": j["sender"], "to_cell": j["receiver"]} | taken(j, _JUNCTION)
        row["gate"] = dict(j["gate"]) | {"law": label(j["gate"]["law"])}
        named = {"id", "sender", "receiver", *_JUNCTION, "gate"}
        out[j["id"]] = row | rest(j, named, {"law": LABELS["constant_field"]})
    return {"junctions": mapped(out)}


_FACE = ("sender", "receiver", "area_m2", "length_m", "diffusivity_m2_per_s")


def _write_faces(block, raw):
    raw["model"]["faces"] = [
        {"id": name} | taken(known(f, (*_FACE, "law"), name), _FACE) | {"law": string(f.get("law"))}
        for name, f in entities(block.get("faces"))
    ]


def _read_faces(raw):
    out = {}
    for f in raw["model"]["faces"]:
        out[f["id"]] = taken(f, _FACE) | {"law": label(f["law"])}
        out[f["id"]] |= rest(f, {"id", *_FACE, "law"}, {})
    return {"faces": mapped(out)}


# ------------------------------------------------------------------ the controls


_CONTROLS = ("leak", "pump", "channel", "junction")


def _write_controls(block, raw):
    controls = known(block.get("controls", {}), _CONTROLS, "controls")
    model, experiment = raw["model"], raw["experiment"]
    pumped = [m["id"] for m in model["membranes"] if m["pump"] is not None]
    channel = controls.get("channel")
    experiment["membrane_controls"] = groups(
        controls.get("leak"), [m["id"] for m in model["membranes"]], "membrane_id"
    )
    experiment["pump_controls"] = groups(controls.get("pump"), pumped, "pump_id", pump_id)
    # A sentence stands for the schedule of a channel that a pool drives: its base is 1.
    experiment["channel_controls"] = groups(
        {} if isinstance(channel, str) else channel,
        [c["id"] for c in model["channels"]],
        "channel_id",
    )
    experiment["junction_controls"] = groups(
        controls.get("junction"), [j["id"] for j in model["junctions"]], "junction_id"
    )
    experiment["calcium_pump_controls"] = []


def _read_controls(raw):
    experiment = raw["experiment"]
    of_pump = {m["pump"]["id"]: m["id"] for m in raw["model"]["membranes"] if m["pump"] is not None}

    def schedules(key, name, rename=lambda value: value):
        return mapped({rename(g[name]): pairs(g["schedule"]) for g in experiment[key]})

    return {
        "controls": {
            "leak": schedules("membrane_controls", "membrane_id"),
            "pump": schedules("pump_controls", "pump_id", lambda p: of_pump.get(p, p)),
            "channel": schedules("channel_controls", "channel_id"),
            "junction": schedules("junction_controls", "junction_id"),
        }
    }


# ------------------------------------------------------------------ the horizon and the tolerance


def _write_horizon(block, raw):
    raw["experiment"]["end_time"] = block["end_s"]
    if "material_tolerance_fmol" in block:
        raw["execution"]["material_balance_atol_fmol"] = dict(block["material_tolerance_fmol"])


def _read_horizon(raw):
    return {
        "material_tolerance_fmol": dict(raw["execution"]["material_balance_atol_fmol"]),
        "end_s": raw["experiment"]["end_time"],
    }


# In the order of the literal blocks (SPEC §2.5), which is the order they are written in too; then
# Part 2's (stores.py), which make a composite of what these wrote.
SECTIONS = (
    Section(("temperature_K", "species"), _write_species, _read_species),
    Section(("cells", "outside"), _write_compartments, _read_compartments),
    Section(("closure",), _write_closure, _read_closure),
    Section(("membranes",), _write_membranes, _read_membranes),
    Section(("channels",), _write_channels, _read_channels),
    Section(("junctions",), _write_junctions, _read_junctions),
    Section(("faces",), _write_faces, _read_faces),
    Section(("controls",), _write_controls, _read_controls),
    Section(("material_tolerance_fmol", "end_s"), _write_horizon, _read_horizon),
    *stores.SECTIONS,
)
SIZES = {  # {an execution's capacity: the model's list it counts}.
    "capacity": "cells",
    "extracellular_capacity": "extracellular",
    "membrane_capacity": "membranes",
    "edge_capacity": "junctions",
    "face_capacity": "faces",
    "channel_capacity": "channels",
}
HARNESS = {"max_steps": 10**6, "max_trace_bytes": 2**32}  # No number of the spec's (SPEC §2.3).


def write(block, *, step, observation_times, solver, field_solver, sections=SECTIONS):
    """The raw definition of a block, with this step, these observation times and these strings."""
    held = {key for section in sections for key in section.keys}
    unknown = sorted(set(block) - held)
    if unknown:
        raise no_section(f"no section holds the block's {', '.join(unknown)}")
    raw = {
        "schema_version": 1,
        "model": {"id": LABELS["inner_model"]},
        "experiment": {"observation_times": list(observation_times)},
        "execution": {
            "dt": step,
            "backend": "cpu",
            "jit": True,
            "precision": "float64",
            "solver": solver,
            "field_solver": field_solver,
            **HARNESS,
        },
    }
    for section in sections:
        section.write(block, raw)
    for capacity, entity in SIZES.items():
        raw["execution"][capacity] = len(raw["model"][entity])
    return raw


def read(raw, *, sections=SECTIONS):
    """The block of a definition in the engine's canonical JSON form (a parsed definition's
    to_dict(), or a declaration as submitted): the last section's keys first, and each section reads
    the definition without what the ones after it added."""
    out = {}
    for section in reversed(sections):
        out |= section.read(raw)
        if section.take is not None:
            raw = section.take(raw)
    return {key: out[key] for section in sections for key in section.keys if key in out}


def shown(block):
    """A table's `inputs` of a block that was read back: Part 1's is the block itself, and Part 2's
    holds the inner model's keys under `ionic` and its own beside it (PART2_BLOCKS)."""
    if not any(key in block for key in BESIDE):
        return block
    inner = {key: value for key, value in block.items() if key not in BESIDE}
    return {INNER: inner} | {key: block[key] for key in BESIDE if key in block}


# ------------------------------------------------------------------ the echo's comparison


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _with_defaults(block):
    """The block with the defaults of SPEC §2.4 written out, and PART2 §2.4's in one with stores."""
    out = copy.deepcopy(block)
    if "stores" in out:
        _store_defaults(out)
    for key in ("channels", "junctions", "faces"):
        out.setdefault(key, [])
    for _, membrane in entities(out.get("membranes")):
        membrane.setdefault("pump", None)
    owners = {
        "leak": [name for name, _ in entities(out.get("membranes"))],
        "pump": [n for n, m in entities(out.get("membranes")) if m["pump"] is not None],
        "channel": [name for name, _ in entities(out["channels"])],
        "junction": [name for name, _ in entities(out["junctions"])],
    }
    controls = out.setdefault("controls", {})
    for key, names in owners.items():
        given = controls.get(key)
        if isinstance(given, str):
            continue
        held = {n: s for n, s in entities(given) if n in names or s != ONES}
        controls[key] = {n: held.get(n, ONES) for n in names} | held
    return out


def _said(given, own):
    """The schedules that a map gives: 1 for each of these names that it leaves out, and not the 1
    throughout that it writes out for any other, which says nothing."""
    given = dict(entities(given))
    others = {n: s for n, s in given.items() if n not in own and s != ONES}
    return {n: given.get(n, ONES) for n in own} | others


def _store_defaults(out):
    """Part 2's defaults: a permeability of 0, and a schedule of 1 for every calcium piece."""
    for _, membrane in entities(out.get("membranes")):
        carried = membrane["passive"]["permeability_m_per_s"]
        carried.update({s: carried.get(s, 0.0) for s in out["species"]})
    for _, junction in entities(out.get("junctions")):
        carried = junction["permeability_m_per_s"]
        carried.update({s: carried.get(s, 0.0) for s in out["species"]})
    leaks, reactions, pumped, released = {}, {}, [], []
    for cell, store in entities(out["stores"]):
        carried = store["membrane"]["permeability_m_per_s"]
        carried.update({s: carried.get(s, 0.0) for s in store["species"]})
        leaks[cell] = [s for s, value in carried.items() if value != 0.0]
        reactions[cell] = list(dict(entities(store.get("reactions"))))
        pumped += [cell] if store["membrane"].get("pump") is not None else []
        released += [cell] if store["membrane"].get("release") is not None else []
    transport = entities(out.get("plasma_transport"))
    given = out.get("calcium_controls", {})
    controls = {
        key: _said(given.get(key), own)
        for key, own in (
            ("store_pump", pumped),
            ("store_release", released),
            ("calcium_pump", [m for m, t in transport if t.get("pump") is not None]),
            ("exchanger", [m for m, t in transport if t.get("exchanger") is not None]),
            ("calcium_channel", list(dict(entities(out.get("calcium_channels"))))),
        )
    }
    for key, own in (("store_passive", leaks), ("reactions", reactions)):
        held = dict(entities(given.get(key)))
        said = {c: _said(held.get(c), own.get(c, ())) for c in dict.fromkeys((*own, *held))}
        controls[key] = {cell: schedules for cell, schedules in said.items() if schedules}
    others = {key: value for key, value in given.items() if key not in controls}
    out["calcium_controls"] = others | {key: value for key, value in controls.items() if value}


def charge_scale(block, region):
    """The sum of the magnitudes of the charges of the cells that face an outside region."""
    facing = [m["inside"] for _, m in entities(block["membranes"]) if m["outside"] == region]
    return math.fsum(abs(block["cells"][c]["initial_charge_C"]) for c in facing)


FIXED = "fixed_charge_equivalent_fmol"
PUMPED = ("stores", "plasma_transport")  # Where the calcium pumps stand.
LARGEST_A = 3200.0  # PART2 §2.4: "A is at most 3,200, and a larger one is a departing echo".


def energy_bound(pump, temperature):
    """What PART2 §2.4 adds to the tolerance of a pump's free energy at 1 M: 16 eps R T A of the
    potentials that a read-back pump holds, 0 where it holds none, and nothing (a departure whatever
    the number) where A is above 3,200."""
    if not all(key in pump for key in stores.OWN):
        return 0.0
    concentration = pump["standard_concentration_mM"]
    terms = [abs(mu) for mu in pump["fuel_standard_mu_RT"].values()]
    size = math.fsum(terms) + abs(math.log(stores.ONE_MOLAR_MM / concentration))
    if size > LARGEST_A:
        return -math.inf
    return 16 * EPS * stores.R * temperature * size


def departures(found, expected, *, exact=False, skip=()):
    """[(path, found, expected), ...]: the leaves of two blocks that differ, by SPEC §2.4's rule and
    PART2 §2.4's, or with exact=True by their doubles. `skip` names top-level paths left out (class
    E leaves). Keys that `expected` does not hold are no departure. A cell's fixed charge is
    recorded and not compared where it has a store (PART2 §2.2). A calcium pump's free energy and
    its held fuel have no double of their own: the one is formed from potentials, and the other is
    an amount of the cell over its volume. They are compared by the rule alone."""
    found, expected = _with_defaults(found), _with_defaults(expected)
    stored = [c for c, _ in entities(expected.get("stores"))]
    out = []

    def same(a, b, path):
        if not (_number(a) and _number(b)):
            return type(a) is type(b) and a == b
        if path[-1] == stores.ENERGY:
            own = found
            for key in path[:-1]:
                own = own[key]
            return abs(a - b) <= RELATIVE * abs(b) + energy_bound(own, found["temperature_K"])
        if b == 0 or (exact and not (path[0] in PUMPED and path[-1] in stores.FUEL.values())):
            return a == b
        if path[0] == "outside" and path[-1] == "initial_charge_C":
            return abs(a - b) <= RELATIVE * charge_scale(expected, path[1])
        return abs(a - b) <= RELATIVE * abs(b)

    def walk(a, b, path):
        if path in skip:
            return
        if len(path) == 3 and path[0] == "cells" and path[2] == FIXED and path[1] in stored:
            return
        if isinstance(b, dict) or isinstance(a, dict):
            if not (a or b):  # {} and [] are both the empty set of entities.
                return
            if not (isinstance(a, dict) and isinstance(b, dict)):
                out.append((path, a, b))
                return
            for key in b:
                if key not in a:
                    out.append(((*path, key), None, b[key]))
                else:
                    walk(a[key], b[key], (*path, key))
        elif isinstance(b, list) or isinstance(a, list):
            if not (isinstance(a, list) and isinstance(b, list)) or len(a) != len(b):
                out.append((path, a, b))
                return
            for k, (x, y) in enumerate(zip(a, b, strict=True)):
                walk(x, y, (*path, k))
        elif not same(a, b, path):
            out.append((path, a, b))

    walk(found, expected, ())
    return out
