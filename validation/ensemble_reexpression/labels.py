"""The spec folder's labels and the registered strings they stand for, and the registered strings a
definition declares.

Every string here is the engine's own constant, so this file holds no registered ID of its own. The
lead's strings note (spec/TABLE.md §5) is the one file through which a string enters the judgement.
This map is what the generator writes a definition with and what the exporter reads one back with.
"""

import re

from cells.assembly.graph import TOPOLOGY_ID
from cells.assembly_pool import MODEL_ID as POOL_MODEL_ID
from cells.assembly_pool.observables import LAW_ID as ASSEMBLY_OBSERVABLE_ID
from cells.definitions.kinetic_pump_spec import METABOLISM_ID
from cells.definitions.pump_composite_spec import MODEL_ID as COMPOSITE_ID
from cells.definitions.surface_pump_spec import GATE_LAW_ID
from cells.definitions.surface_pump_v3_spec import KV1P5_LAW_ID
from cells.definitions.surface_pump_v3_spec import MODEL_ID as INNER_MODEL_ID
from cells.definitions.surface_tissue_spec import FACE_LAW_ID
from cells.kinds.passive_routes import KIND_ID as PASSIVE_ROUTES_ID
from cells.kinds.species_condition import KIND_ID as SPECIES_CONDITION_ID
from cells.kinds.species_condition import LAW_ID as HILL_PRODUCT_ID
from cells.kinds.transporter import KIND_ID as TRANSPORTER_ID
from cells.laws.channels.cav1p2_m2h import LAW_ID as CAV1P2_LAW_ID
from cells.laws.cycles.sodium_calcium_exchange_symmetric_barrier import DECLARED_ID as EXCHANGE_ID
from cells.laws.pumps.atp_transporter_v2 import LAW_ID as ATP_TRANSPORTER_ID
from cells.laws.pumps.kinetic_pump import LAW_ID as NAK_PUMP_ID
from cells.laws.routes.constant_field import LAW_ID as CONSTANT_FIELD_ID
from cells.laws.routes.constant_field_permeation import LAW_ID as PASSIVE_PERMEATION_ID
from cells.modules import qualified
from cells.numerics.surface_field import FACTORED_SOLVER_ID, FLOOR_SOLVER_ID
from cells.numerics.surface_field import LAW_ID as CLOSURE_ID
from cells.numerics.surface_imex import ARS222_ID
from cells.operators.compartments import LAW_ID as COMPARTMENTS_ID
from cells.operators.species_reactions import LAW_ID as REACTIONS_ID
from cells.operators.species_reactions import PASSIVE_LAW as MASS_ACTION_ID
from cells.registry import kind_registry

# {label: registered string}, as the engine writes a definition: some laws namespaced, some not. In
# Part 1 "imex" is the rehearsal's alone (Amendment 1, item 5); Part 2's worlds declare it.
LABELS = {
    "inner_model": INNER_MODEL_ID,
    "rk4": "rk4",
    "imex": ARS222_ID,
    "field_solver": FACTORED_SOLVER_ID,
    "field_solver_floor": FLOOR_SOLVER_ID,
    "closure": CLOSURE_ID,
    "constant_field": CONSTANT_FIELD_ID,
    "kv15_mh": KV1P5_LAW_ID,
    "nak_pump_positive": NAK_PUMP_ID,
    "maintained_fuel": METABOLISM_ID,
    "junction_relaxation": GATE_LAW_ID,
    "logmean_face": FACE_LAW_ID,
    "pool_model": POOL_MODEL_ID,
    "pool_topology": TOPOLOGY_ID,
    "assembly_observable": ASSEMBLY_OBSERVABLE_ID,
    "composite_model": COMPOSITE_ID,
    "passive_routes_kind": PASSIVE_ROUTES_ID,
    "transporter_kind": TRANSPORTER_ID,
    "species_condition_kind": SPECIES_CONDITION_ID,
    "compartment_law": COMPARTMENTS_ID,
    "local_reactions": REACTIONS_ID,
    "mass_action_passive": MASS_ACTION_ID,
    "calcium_pump_positive": qualified(ATP_TRANSPORTER_ID),
    "exchanger_3na_1ca": EXCHANGE_ID,
    "cav12_m2h": CAV1P2_LAW_ID,
    "hill_product_factor": HILL_PRODUCT_ID,
    "passive_constant_field": PASSIVE_PERMEATION_ID,
}

# A world's order of integration, `p` of its block, and the integrator it is declared with.
INTEGRATORS = {4: "rk4", 2: "imex"}

# The place of each label in an entry of the strings note's `runs` (spec/TABLE.md §5). The closure
# and the fuel stand among the laws: the note has no word of their own for them, and `kinds` holds
# declared kinds. A composite's inner model stands among the laws too: the note has one model.
PLACES = {
    "inner_model": "model",
    "composite_model": "model",
    "compartment_law": "operators",
    "local_reactions": "operators",
    "passive_routes_kind": "kinds",
    "transporter_kind": "kinds",
    "species_condition_kind": "kinds",
    "rk4": "solver",
    "imex": "solver",
    "field_solver": "field_solver",
    "field_solver_floor": "field_solver",
    "pool_model": "pool",
    "pool_topology": "pool",
    "assembly_observable": "observable",
}

_VERSIONED = re.compile(r"(?:[A-Za-z][A-Za-z0-9_]*\.)*[A-Za-z][A-Za-z0-9_]*@[0-9]+")


class UnknownOrder(ValueError):
    """A world whose `p` names no integrator (README.md)."""


def string(label):
    """The registered string of a label. A string that is no label passes through as it is, so the
    engine, and not this map, refuses a law it does not have."""
    return LABELS.get(label, label) if isinstance(label, str) else label


def label(value):
    """The label of a registered string, or the string itself where no label stands for it."""
    for name, registered in LABELS.items():
        if registered == value:
            return name
    return value


def integrator(order):
    """The registered string of the integrator of order `p`, refused by name for any other."""
    if order not in INTEGRATORS:
        raise UnknownOrder(
            f"unknown_order: p = {order!r} names no integrator "
            f"(known: {', '.join(f'{k} {v}' for k, v in sorted(INTEGRATORS.items()))})"
        )
    return string(INTEGRATORS[order])


def kinds(model):
    """The IDs of the kinds that a definition's model declares. A definition names a kind by its
    model key alone, so its ID is the engine's for that key."""
    if not isinstance(model, dict):
        return set()
    by_key = kind_registry.active().model_keys()
    return {qualified(kind.kind_id) for key, kind in by_key.items() if key in model}


def declared_strings(*definitions):
    """Every registered string that these JSON values declare, sorted, one each: a value or a key
    of the form name@version, the kinds whose keys a model holds, and an execution's solver, which
    has no version of its own."""
    found = set()

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if isinstance(key, str) and _VERSIONED.fullmatch(key):
                    found.add(key)
                walk(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)
        elif isinstance(value, str) and _VERSIONED.fullmatch(value):
            found.add(value)

    for definition in definitions:
        walk(definition)
        if not isinstance(definition, dict):
            continue
        found |= kinds(definition.get("model"))
        execution = definition.get("execution")
        if isinstance(execution, dict) and isinstance(execution.get("solver"), str):
            found.add(execution["solver"])
    return sorted(found)


def strings(declared):
    """{label: string} of the declared strings that a label stands for (spec/TABLE.md §3)."""
    by_string = {registered: name for name, registered in LABELS.items()}
    return {by_string[s]: s for s in declared if s in by_string}


def note_entry(declared):
    """The strings note's entry (spec/TABLE.md §5) of a run that declares these strings. A string
    without a label is listed as itself, so a reader sees it."""
    entry = {
        "model": None,
        "solver": None,
        "field_solver": None,
        "operators": [],
        "kinds": [],
        "laws": [],
        "pool": [],
        "observable": None,
    }
    names = [label(value) for value in declared]
    for name in names:
        place = PLACES.get(name, "laws")
        if name == "inner_model" and "composite_model" in names:
            place = "laws"
        if isinstance(entry[place], list):
            entry[place].append(name)
        else:
            entry[place] = name
    if entry["model"] is None and "pool_model" in entry["pool"]:
        entry["model"] = "pool_model"  # A pool run's model; its solver and field solver are null.
    return {k: sorted(v) if isinstance(v, list) else v for k, v in entry.items()}
