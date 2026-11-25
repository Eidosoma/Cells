"""A world's block (spec/SPEC.md §2) and the engine's definition of it: each is written from the
other, section by section.

**write** makes a raw `resolved_pump_tissue@3` definition from a block. Every number in it is the
block's own double. **read** makes a block from a definition the engine parsed (its canonical JSON
form), in the block's own names, with a label for every registered string and every default written
out. Nothing of inputs.json enters `read`.

**A section** holds one or more of the block's top keys, with how they are written and how they are
read. Part 2 adds its sections to SECTIONS (in order: a later section may add to what an earlier one
wrote) and its labels to labels.py; nothing else here knows which sections there are. A key of a
block that no section holds, or a field of an entity that no section has a place for, is refused by
name, so nothing in a block is dropped in silence. A field that a block lacks is left out of the
definition, for the engine to refuse. The defaults (spec/SPEC.md §2.4) may be left out of a block.
"""

import copy
import math
from dataclasses import dataclass

from cells.definitions.surface_pump_v3_spec import channel_laws
from validation.ensemble_reexpression.labels import LABELS, label, string

ONES = [[0.0, 1.0]]  # A schedule of 1 throughout, the default of every control.
RELATIVE = 1e-12  # The echo's precision (spec/SPEC.md §2.4).


class NoSection(ValueError):
    """A key or a field of a block that has no place in a definition."""


@dataclass(frozen=True)
class Section:
    """Some of a block's top keys, and how they are written and read.

    write(block, raw) adds them to the raw definition; read(raw) gives {key: value} back."""

    keys: tuple[str, ...]
    write: object
    read: object


def entities(value):
    """The (ID, entity) pairs of a block's map of entities; none for [], {} or an omitted one."""
    return tuple(value.items()) if isinstance(value, dict) else ()


def _known(value, fields, where):
    unknown = sorted(set(value) - set(fields))
    if unknown:
        raise NoSection(f"no_section: {where} has no place for {', '.join(unknown)}")
    return value


def _taken(value, fields):
    return {name: copy.deepcopy(value[name]) for name in fields if name in value}


def _map(rows):
    """Entities as the block prints them: a map by ID, or [] for none."""
    return rows if rows else []


def _schedule(changes):
    return [{"time": t, "availability": a} for t, a in changes]


def _pairs(schedule):
    return [[c["time"], c["availability"]] for c in schedule]


def _rest(entry, known, defaults):
    """The fields of a definition's entity that the block has no name for, without the ones at their
    defaults: they are read back under their own names, so nothing declared is hidden."""
    return {
        key: value
        for key, value in entry.items()
        if key not in known and not (key in defaults and value == defaults[key])
    }


# ------------------------------------------------------------------ the species and compartments


def _write_species(block, raw):
    raw["model"]["temperature_K"] = block["temperature_K"]
    raw["model"]["species"] = [{"id": s, "valence": z} for s, z in block["species"].items()]


def _read_species(raw):
    model = raw["model"]
    species = {}
    for entry in model["species"]:
        rest = _rest(entry, {"id", "valence"}, {})
        species[entry["id"]] = (
            entry["valence"] if not rest else rest | {"valence": entry["valence"]}
        )
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
        {"id": name} | _taken(_known(c, (*_COMPARTMENT, "initial_voltage_V"), name), _COMPARTMENT)
        for name, c in entities(block["cells"])
    ]
    raw["model"]["extracellular"] = [
        {"id": name} | _taken(_known(c, _COMPARTMENT, name), _COMPARTMENT) | _CLOSED
        for name, c in entities(block["outside"])
    ]


def _read_compartments(raw):
    model = raw["model"]
    capacitance = {}
    for membrane in model["membranes"]:
        capacitance.setdefault(membrane["inside"], []).append(membrane["capacitance_F"])
    cells, outside = {}, {}
    for c in model["cells"]:
        out = _taken(c, _COMPARTMENT) | _rest(c, {"id", *_COMPARTMENT}, {})
        own = capacitance.get(c["id"], [])
        if len(own) == 1:  # "divided by the capacitance of its membrane" (SPEC §2.4).
            out["initial_voltage_V"] = c["initial_charge_C"] / own[0]
        order = (*_COMPARTMENT[:-1], "initial_voltage_V", _COMPARTMENT[-1])
        cells[c["id"]] = {k: out[k] for k in (*order, *out) if k in out}
    for c in model["extracellular"]:
        outside[c["id"]] = _taken(c, _COMPARTMENT) | _rest(c, {"id", *_COMPARTMENT}, _CLOSED)
    return {"cells": cells, "outside": outside}


def _write_closure(block, raw):
    closure = _known(block["closure"], ("gauge_reference",), "closure")
    raw["model"]["closure"] = {"law": LABELS["closure"]} | _taken(closure, ("gauge_reference",))


def _read_closure(raw):
    closure = raw["model"]["closure"]
    return {"closure": _rest(closure, {"law"}, {})}


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
    out = {"id": pump_id(name)} | _taken(_known(pump, _PUMP, f"{name}'s pump"), _PUMP)
    if "law" in out:
        out["law"] = string(out["law"])
    if isinstance(out.get("metabolism"), dict):
        fuel = _known(out["metabolism"], _FUEL, f"{name}'s fuel")
        if "kind" in fuel:
            fuel["kind"] = string(fuel["kind"])
    return out


def _write_membranes(block, raw):
    rows = []
    for name, m in entities(block["membranes"]):
        _known(m, (*_MEMBRANE, "passive", "pump"), name)
        passive = _known(m["passive"], _PASSIVE, f"{name}'s passive route")
        row = {"id": name} | _taken(m, _MEMBRANE) | _taken(passive, ("permeability_m_per_s",))
        row["law"] = string(passive["law"]) if "law" in passive else LABELS["constant_field"]
        row["pump"] = _write_pump(name, m.get("pump"))
        row["calcium_pump"] = None  # None in Part 1 (SPEC §2.1); a later section may set it.
        rows.append(row)
    raw["model"]["membranes"] = rows


def _read_pump(pump):
    if pump is None:
        return None
    out = _taken(pump, _PUMP) | _rest(pump, {"id", *_PUMP}, {})
    out["law"] = label(out["law"])
    fuel = dict(out["metabolism"])
    out["metabolism"] = fuel | {"kind": label(fuel["kind"])}
    return out


def _read_membranes(raw):
    out = {}
    for m in raw["model"]["membranes"]:
        row = _taken(m, _MEMBRANE)
        row["passive"] = {
            "law": label(m["law"]),
            "permeability_m_per_s": dict(m["permeability_m_per_s"]),
        }
        row["pump"] = _read_pump(m["pump"])
        known = {"id", *_MEMBRANE, "permeability_m_per_s", "law", "pump"}
        out[m["id"]] = row | _rest(m, known, {"calcium_pump": None})
    return {"membranes": _map(out)}


# ------------------------------------------------------------------ channels


_CHANNEL = ("membrane_id", "kinetic_law", "max_permeability_m_per_s", "abundance")


def _law_of(law_id):
    return channel_laws().get(law_id)


def _permeant(species, law):
    """The permeant ions of a population of this species, with the law's own relative permeability
    (1 where the law does not carry the species, for the engine to refuse)."""
    ratios = {s: weight for s, _, weight in law.permeant} if law is not None else {}
    return [{"species_id": species, "relative_permeability": ratios.get(species, 1.0)}]


def _write_channels(block, raw):
    rows = []
    for name, c in entities(block.get("channels")):
        _known(c, (*_CHANNEL, "species_id", "initial_gate"), name)
        row = {"id": name} | _taken(c, _CHANNEL)
        row["kinetic_law"] = string(c.get("kinetic_law"))
        law = _law_of(row["kinetic_law"])
        gate = c.get("initial_gate", {})
        order = tuple(gate) if law is None or set(gate) != set(law.gates) else law.gates
        row["initial_gate"] = [gate[g] for g in order]
        row["permeant_ions"] = _permeant(c.get("species_id"), law)
        rows.append(row)
    raw["model"]["channels"] = rows


def _read_channels(raw):
    out = {}
    for c in raw["model"]["channels"]:
        law = _law_of(c["kinetic_law"])
        gates = law.gates if law is not None else tuple(map(str, range(len(c["initial_gate"]))))
        ions = c["permeant_ions"]
        row = {
            "membrane_id": c["membrane_id"],
            "species_id": ions[0]["species_id"]
            if len(ions) == 1
            else [i["species_id"] for i in ions],
            "kinetic_law": label(c["kinetic_law"]),
            "max_permeability_m_per_s": c["max_permeability_m_per_s"],
            "abundance": c["abundance"],
            "initial_gate": dict(zip(gates, c["initial_gate"], strict=True)),
        }
        if any(i["relative_permeability"] != 1 for i in ions):
            row["permeant_ions"] = copy.deepcopy(ions)
        out[c["id"]] = row | _rest(c, {"id", *_CHANNEL, "initial_gate", "permeant_ions"}, {})
    return {"channels": _map(out)}


# ------------------------------------------------------------------ junctions and faces


_JUNCTION = ("area_m2", "permeability_m_per_s")
_GATE = ("law", "threshold_voltage_V", "minimum_open_fraction", "initial_gate")


def _write_junctions(block, raw):
    rows = []
    for name, j in entities(block.get("junctions")):
        _known(j, ("from_cell", "to_cell", *_JUNCTION, "gate"), name)
        gate = _taken(_known(j["gate"], _GATE, f"{name}'s gate"), _GATE)
        if "law" in gate:
            gate["law"] = string(gate["law"])
        row = {"id": name, "sender": j["from_cell"], "receiver": j["to_cell"]}
        rows.append(row | _taken(j, _JUNCTION) | {"law": LABELS["constant_field"], "gate": gate})
    raw["model"]["junctions"] = rows


def _read_junctions(raw):
    out = {}
    for j in raw["model"]["junctions"]:
        row = {"from_cell": j["sender"], "to_cell": j["receiver"]} | _taken(j, _JUNCTION)
        row["gate"] = dict(j["gate"]) | {"law": label(j["gate"]["law"])}
        known = {"id", "sender", "receiver", *_JUNCTION, "gate"}
        out[j["id"]] = row | _rest(j, known, {"law": LABELS["constant_field"]})
    return {"junctions": _map(out)}


_FACE = ("sender", "receiver", "area_m2", "length_m", "diffusivity_m2_per_s")


def _write_faces(block, raw):
    raw["model"]["faces"] = [
        {"id": name}
        | _taken(_known(f, (*_FACE, "law"), name), _FACE)
        | {"law": string(f.get("law"))}
        for name, f in entities(block.get("faces"))
    ]


def _read_faces(raw):
    out = {}
    for f in raw["model"]["faces"]:
        out[f["id"]] = _taken(f, _FACE) | {"law": label(f["law"])}
        out[f["id"]] |= _rest(f, {"id", *_FACE, "law"}, {})
    return {"faces": _map(out)}


# ------------------------------------------------------------------ the controls


_CONTROLS = ("leak", "pump", "channel", "junction")


def _groups(schedules, names, key, rename=lambda name: name):
    """One control group for each name, its schedule or 1 throughout; a schedule of any other name
    is written too, for the engine to refuse."""
    given = schedules if isinstance(schedules, dict) else {}
    return [
        {key: rename(name), "schedule": _schedule(given.get(name, ONES))}
        for name in (*names, *(n for n in given if n not in names))
    ]


def _write_controls(block, raw):
    controls = _known(block.get("controls", {}), _CONTROLS, "controls")
    model, experiment = raw["model"], raw["experiment"]
    pumped = [m["id"] for m in model["membranes"] if m["pump"] is not None]
    channel = controls.get("channel")
    experiment["membrane_controls"] = _groups(
        controls.get("leak"), [m["id"] for m in model["membranes"]], "membrane_id"
    )
    experiment["pump_controls"] = _groups(controls.get("pump"), pumped, "pump_id", pump_id)
    # A sentence stands for the schedule of a channel that a pool drives: its base is 1.
    experiment["channel_controls"] = _groups(
        {} if isinstance(channel, str) else channel,
        [c["id"] for c in model["channels"]],
        "channel_id",
    )
    experiment["junction_controls"] = _groups(
        controls.get("junction"), [j["id"] for j in model["junctions"]], "junction_id"
    )
    experiment["calcium_pump_controls"] = []


def _read_controls(raw):
    experiment = raw["experiment"]
    of_pump = {m["pump"]["id"]: m["id"] for m in raw["model"]["membranes"] if m["pump"] is not None}

    def schedules(key, name, rename=lambda value: value):
        return _map({rename(g[name]): _pairs(g["schedule"]) for g in experiment[key]})

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


# In the order of the literal blocks (SPEC §2.5), which is the order they are written in too.
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
        raise NoSection(f"no_section: no section holds the block's {', '.join(unknown)}")
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
    to_dict(), or a declaration as submitted)."""
    out = {}
    for section in sections:
        out |= section.read(raw)
    return {key: out[key] for section in sections for key in section.keys if key in out}


# ------------------------------------------------------------------ the echo's comparison


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _with_defaults(block):
    """The block with the defaults of SPEC §2.4 written out."""
    out = copy.deepcopy(block)
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
        held = dict(entities(given))
        controls[key] = {n: held.get(n, ONES) for n in names} | held
    return out


def charge_scale(block, region):
    """The sum of the magnitudes of the charges of the cells that face an outside region."""
    facing = [m["inside"] for _, m in entities(block["membranes"]) if m["outside"] == region]
    return math.fsum(abs(block["cells"][c]["initial_charge_C"]) for c in facing)


def departures(found, expected, *, exact=False, skip=()):
    """[(path, found, expected), ...]: the leaves of two blocks that differ, by SPEC §2.4's rule, or
    with exact=True by their doubles. `skip` names top-level paths left out (class E leaves). Keys
    that `expected` does not hold are no departure."""
    found, expected = _with_defaults(found), _with_defaults(expected)
    out = []

    def same(a, b, path):
        if not (_number(a) and _number(b)):
            return type(a) is type(b) and a == b
        if exact or b == 0:
            return a == b
        if path[0] == "outside" and path[-1] == "initial_charge_C":
            return abs(a - b) <= RELATIVE * charge_scale(expected, path[1])
        return abs(a - b) <= RELATIVE * abs(b)

    def walk(a, b, path):
        if path in skip:
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
