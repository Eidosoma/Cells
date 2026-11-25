"""Part 2's sections of a world's block: the calcium stores in its cells, what carries calcium
across its plasma membranes, and the schedules of both (PART2 §2, PART2_BLOCKS).

They make a composite of the inner model that worlds.py's own sections wrote: an outside node with
the compartment law and one bounding patch for each store, the buffers as local reactions, the pumps
and the exchangers as transporter populations, calcium's leaks and the release as passive routes,
and the release's factor as a species condition. Their readers take what they wrote out again, so
that the inner model's own readers read the rest.

What a composite needs and a block does not say is declared by rule (README.md): a trace of each row
at each node that the block does not name it at, its tolerance, the moieties that the reactions
imply, and a cell's and a store's fixed charge by the model's anchor rule.
"""

import copy
import math

from cells.laws.electrochemistry import CHARGE_PER_FMOL, R
from validation.ensemble_reexpression.blocks import (
    ONES,
    RELATIVE,
    Section,
    channel_rows,
    entities,
    groups,
    known,
    mapped,
    no_section,
    nothing_else,
    pairs,
    read_channels,
    schedule,
    taken,
)
from validation.ensemble_reexpression.inputs import EPS, FUEL_POTENTIALS
from validation.ensemble_reexpression.labels import LABELS, label, string
from validation.ensemble_reexpression.pieces import CALCIUM, CYTOSOL, FUEL, STORE, Pieces

TRACE_MM = 1e-12  # A row's amount over the volume, at a node that the block does not name it at.
TOLERANCE_FMOL = 1e-10  # The material tolerance of a row that the block gives none.
CLOSED = {"reservoir": False, "boundary_potential_V": 0.0}
NONE_OF = {"label": None, "reference": None}  # A compartment's metadata.
ONE_MOLAR_MM = 1000.0

# The IDs of the pieces, from the block's own. No block names them (PART2 §2.3).


def store_id(cell):
    return f"store_{cell}"


def patch_id(cell):
    return f"store_membrane_{cell}"


def compartment_id(cell):
    return f"compartment_{cell}"


def condition_id(cell):
    return f"release_factor_{cell}"


def release_id(cell):
    return f"store_release_{cell}"


def store_leak_id(cell, species):
    return f"store_leak_{species}_{cell}"


def leak_id(membrane, species):
    return f"leak_{species}_{membrane}"


def junction_route_id(junction, species):
    return f"junction_{species}_{junction}"


def store_pump_id(cell):
    return f"store_pump_{cell}"


def plasma_pump_id(membrane):
    return f"calcium_pump_{membrane}"


def exchanger_id(membrane):
    return f"exchanger_{membrane}"


# ------------------------------------------------------------------ the composite and its rows


def composite(raw):
    """The raw definition as a composite: what every section here writes into."""
    model = raw["model"]
    if model["id"] != LABELS["composite_model"]:
        model |= {
            "id": LABELS["composite_model"],
            "inner_model": LABELS["inner_model"],
            "operators": [],
        }
    return raw


def nodes(model):
    return [*model["cells"], *model["extracellular"]]


def add_row(raw, species, valence, standard_mu_RT):
    """A species row and its standard potential. A new row has a trace at every node, no route of
    the inner model's and a tolerance; a row that is there already keeps what it has."""
    model = raw["model"]
    entry = next((s for s in model["species"] if s["id"] == species), None)
    if entry is None:
        entry = {"id": species, "valence": valence}
        model["species"].append(entry)
        for node in nodes(model):
            node["initial_amount_fmol"][species] = TRACE_MM * node["volume_pL"]
        for key, name in (
            ("membranes", "permeability_m_per_s"),
            ("junctions", "permeability_m_per_s"),
            ("faces", "diffusivity_m2_per_s"),
        ):
            for owner in model[key]:
                owner[name][species] = 0.0
        tolerance = raw["execution"].setdefault("material_balance_atol_fmol", {})
        tolerance[species] = TOLERANCE_FMOL
    elif entry["valence"] != valence:
        raise no_section(f"the row {species} has two valences, {entry['valence']} and {valence}")
    if entry.setdefault("standard_mu_RT", standard_mu_RT) != standard_mu_RT:
        raise no_section(
            f"the row {species} has two standard potentials, {entry['standard_mu_RT']!r} and "
            f"{standard_mu_RT!r}"
        )


def anchored(node, valence):
    """A node's fixed charge by the model's anchor rule, over every row of it (PART2 §2.2)."""
    content = math.fsum(valence[s] * n for s, n in node["initial_amount_fmol"].items())
    return node["initial_charge_C"] / CHARGE_PER_FMOL - content


def anchor(raw):
    """The fixed charges of the cells and of the stores. The regions keep the block's."""
    model = raw["model"]
    valence = {s["id"]: s["valence"] for s in model["species"]}
    owned = Pieces(raw).cell_of_store
    for node in (*model["cells"], *(o for o in model["extracellular"] if o["id"] in owned)):
        node["fixed_charge_equivalent_fmol"] = anchored(node, valence)


def move_to_routes(raw, species, host, key, name):
    """Turn the inner model's own permeability of a reacting species on its hosts into a passive
    route of each: the engine carries such a row by routes alone."""
    for owner in raw["model"][key]:
        value = owner["permeability_m_per_s"].get(species, 0.0)
        owner["permeability_m_per_s"][species] = 0.0
        if value != 0.0:
            add_route(raw, name(owner["id"], species), {host: owner["id"]}, species, value)


def add_route(raw, name, host, species, permeability, factors=()):
    route = {"id": name, **host, "law": LABELS["passive_constant_field"], "species": species}
    route["permeability_m_per_s"] = permeability
    if factors:
        route["factors"] = list(factors)
    raw["model"].setdefault("passive_routes", []).append(route)


# ------------------------------------------------------------------ a calcium pump


PUMP = ("law", "capacity_fmol_per_s", "km_ca_mM", "km_atp_mM", *FUEL.values())
ENERGY = "delta_g0_at_1M_J_per_mol"
OWN = (FUEL_POTENTIALS, "standard_concentration_mM")  # The exporter's own keys of a pump.
OURS = object()  # A world that gives no potentials: the generator's own are declared.
LARGEST_A = 3200.0  # PART2 §2.4: "A is at most 3,200, and a larger one is a departing echo".
PARAMETERS = {"km_ca_mM": "km_role_mM", "km_atp_mM": "km_atp_mM"}
HELD = [[role, "N"] for role in FUEL]
STANDING = {  # What every calcium pump declares and no block says.
    "roles": {"role": CALCIUM} | {role: role for role in FUEL},
    "orientation": {"N": "a"},
    "held_rows": HELD,
}


def fuel_potentials(energy, temperature, concentration):
    """The standard potentials of a pump's three fuel rows: ADP's alone carries the pump's free
    energy at 1 M, less the two standard states' difference (PART2 §2.2)."""
    return {
        "ATP": 0.0,
        "ADP": energy / (R * temperature) - math.log(ONE_MOLAR_MM / concentration),
        "Pi": 0.0,
    }


def free_energy(potentials, temperature, concentration):
    """delta_g0_at_1M_J_per_mol of three standard potentials (PART2 §2.2)."""
    difference = potentials["ADP"] + potentials["Pi"] - potentials["ATP"]
    return R * temperature * (difference + math.log(ONE_MOLAR_MM / concentration))


def energy_bound(pump, temperature):
    """What PART2 §2.4 adds to the tolerance of a pump's free energy at 1 M: 16 eps R T A of the
    potentials that a read-back pump holds, 0 where it holds none, and nothing (a departure whatever
    the number) where A is above 3,200."""
    if not all(key in pump for key in OWN):
        return 0.0
    terms = [abs(mu) for mu in pump[FUEL_POTENTIALS].values()]
    size = math.fsum(terms) + abs(math.log(ONE_MOLAR_MM / pump["standard_concentration_mM"]))
    if size > LARGEST_A:
        return -math.inf
    return 16 * EPS * R * temperature * size


def same_energy(found, expected, pump, temperature):
    """Whether a pump's free energy at 1 M is the expected one (PART2 §2.4)."""
    return abs(found - expected) <= RELATIVE * abs(expected) + energy_bound(pump, temperature)


def told_potentials(fuel, pump, temperature, concentration, where):
    """The potentials that a world gives its fuel rows in place of the generator's own. They must
    make the block's free energy at 1 M, by the echo's own rule."""
    numbers = fuel.values() if isinstance(fuel, dict) and set(fuel) == set(FUEL) else ()
    if not numbers or any(type(v) not in (int, float) for v in numbers):
        raise no_section(f"{FUEL_POTENTIALS} is three numbers, {', '.join(FUEL)}")
    found = free_energy(fuel, temperature, concentration)
    own = dict(zip(OWN, (fuel, concentration), strict=True))
    if not same_energy(found, pump[ENERGY], own, temperature):
        raise no_section(
            f"{where}: {FUEL_POTENTIALS} make {found!r} J/mol at 1 M and the block says "
            f"{pump[ENERGY]!r} (PART2 §2.4's tolerance, A at most {LARGEST_A:g})"
        )
    return dict(fuel)


def hold_fuel(raw, cell, pump, where, fuel):
    """Hold a pump's fuel at its cell, as rows that every pump of the cell reads, with the world's
    own potentials (`fuel`) or the generator's."""
    model = raw["model"]
    missing = sorted({*FUEL.values(), ENERGY} - set(pump))
    if missing:
        raise no_section(f"{where} names no {', '.join(missing)}")
    at = (model["temperature_K"], model["standard_concentration_mM"])
    if fuel is OURS:
        potentials = fuel_potentials(pump[ENERGY], *at)
    else:
        potentials = told_potentials(fuel, pump, *at, where)
    for species in FUEL:
        add_row(raw, species, 0, potentials[species])
    (node,) = (c for c in model["cells"] if c["id"] == cell)
    for species, key in FUEL.items():
        held = pump[key] * node["volume_pL"]
        if node["initial_amount_fmol"][species] not in (TRACE_MM * node["volume_pL"], held):
            raise no_section(f"{where} holds another {key} than the other pump of {cell}")
        node["initial_amount_fmol"][species] = held


def write_pump(raw, name, host, cell, pump, where, fuel):
    known(pump, (*PUMP, ENERGY), where)
    hold_fuel(raw, cell, pump, where, fuel)
    raw["model"].setdefault("transporters", []).append(
        {
            "id": name,
            "host": host,
            "law": string(pump.get("law")),
            "capacity_fmol_s": pump.get("capacity_fmol_per_s"),
            "parameters": {"stoichiometry": 1}
            | {theirs: pump[ours] for ours, theirs in PARAMETERS.items() if ours in pump},
            **copy.deepcopy(STANDING),
        }
    )


def read_pump(raw, population, cell):
    """A pump's block, with the exporter's own two keys. One that does not move one calcium a cycle
    on held fuel, N at its cell, has no place in a block."""
    model = raw["model"]
    (node,) = (c for c in model["cells"] if c["id"] == cell)
    potential = {s["id"]: s.get("standard_mu_RT", 0.0) for s in model["species"]}
    roles, values = population["roles"], population["parameters"]
    fuel = {role: potential[roles[role]] for role in FUEL}
    concentration = model["standard_concentration_mM"]
    out = {"law": label(population["law"]), "capacity_fmol_per_s": population["capacity_fmol_s"]}
    out |= {ours: values[theirs] for ours, theirs in PARAMETERS.items()}
    for role, key in FUEL.items():
        out[key] = node["initial_amount_fmol"][roles[role]] / node["volume_pL"]
    out[ENERGY] = free_energy(fuel, model["temperature_K"], concentration)
    out[FUEL_POTENTIALS] = fuel
    out["standard_concentration_mM"] = concentration
    nothing_else(values, set(PARAMETERS.values()), {"stoichiometry": 1}, population["id"])
    named = {"id", "host", "law", "capacity_fmol_s", "parameters"}
    nothing_else(population, named, STANDING, population["id"])
    return out


# ------------------------------------------------------------------ the stores


STORE_KEYS = (
    "law",
    "temperature_K",
    "standard_concentration_mM",
    "species",
    "compartments",
    "reactions",
    "membrane",
)
COMPARTMENT = ("volume_pL", "initial_amount_fmol")
REACTION = ("compartment", "reactants", "products", "forward_rate_per_s")
MEMBRANE = (
    "area_m2",
    "capacitance_F",
    "initial_voltage_V",
    "initial_charge_C",
    "permeability_m_per_s",
)
HILL = {  # {the block's pair of keys: the condition's form}, in the order a release reads them.
    ("activation_mM", "activation_n"): "hill_activation",
    ("inhibition_mM", "inhibition_n"): "hill_inhibition",
}
RELEASE = ("law", "permeability_m_per_s", *(key for two in HILL for key in two))


def shared(stores, key):
    """The one value that every store of a world gives, which the model declares once."""
    values = [store[key] for store in stores.values()]
    if any(v != values[0] for v in values):
        raise no_section(f"the stores' {key} are not one value, and the model has one")
    return values[0]


def _write_stores(block, raw):
    stores, fuel = dict(entities(block.get("stores"))), block.get(FUEL_POTENTIALS, OURS)
    pumps = [s["membrane"].get("pump") for s in stores.values()]
    pumps += [t.get("pump") for _, t in entities(block.get("plasma_transport"))]
    if fuel is not OURS and not any(pump is not None for pump in pumps):
        raise no_section(f"a world without calcium pumps has {FUEL_POTENTIALS}")
    if not stores:
        return
    model = composite(raw)["model"]
    for cell, store in stores.items():
        known(store, STORE_KEYS, f"the store of {cell}")
        known(store["compartments"], (CYTOSOL, STORE), f"{cell}'s compartments")
        known(store["membrane"], (CYTOSOL, STORE, *MEMBRANE, "pump", "release"), f"{cell}'s store")
    if shared(stores, "temperature_K") != model["temperature_K"]:
        raise no_section("the stores' temperature is not the model's")
    model["standard_concentration_mM"] = shared(stores, "standard_concentration_mM")
    for species, row in shared(stores, "species").items():
        add_row(raw, species, row["valence"], row["standard_mu_RT"])
    for cell, store in stores.items():
        _write_compartments(raw, cell, store["compartments"])
    _write_reactions(raw, stores)
    for cell, store in stores.items():
        _write_membrane(raw, cell, store["membrane"])
    for species in Pieces(raw).reacting:
        move_to_routes(raw, species, "patch", "membranes", _leak_name(raw))
        move_to_routes(raw, species, "junction", "junctions", junction_route_id)
    for cell, store in stores.items():
        _write_release(raw, cell, store["membrane"].get("release"))
        pump = store["membrane"].get("pump")
        if pump is not None:
            where = f"the store's pump of {cell}"
            write_pump(raw, store_pump_id(cell), patch_id(cell), cell, pump, where, fuel)
    anchor(raw)


def _leak_name(raw):
    """A leak's ID by the patch it crosses: a store's own, or a plasma membrane's."""
    owner = Pieces(raw).cell_of_patch
    return lambda patch, species: (
        store_leak_id(owner[patch], species) if patch in owner else leak_id(patch, species)
    )


def _write_compartments(raw, cell, compartments):
    """A cell's own chemical rows, and its store as an outside node with the compartment law."""
    model = raw["model"]
    (node,) = (c for c in model["cells"] if c["id"] == cell)
    inside, er = (known(compartments[k], COMPARTMENT, f"{cell}'s {k}") for k in (CYTOSOL, STORE))
    if inside["volume_pL"] != node["volume_pL"]:
        raise no_section(f"{cell}'s volume is not its cytosol's")
    trace = TRACE_MM * node["volume_pL"]
    for species, amount in inside["initial_amount_fmol"].items():
        if node["initial_amount_fmol"].get(species) not in (trace, amount):
            raise no_section(f"{cell}'s {species} is not its cytosol's")
        node["initial_amount_fmol"][species] = amount
    amounts = {s["id"]: TRACE_MM * er["volume_pL"] for s in model["species"]}
    store = {"id": store_id(cell), "volume_pL": er["volume_pL"]}
    store["initial_amount_fmol"] = amounts | er["initial_amount_fmol"]
    store["fixed_charge_equivalent_fmol"] = 0.0  # Until the anchor rule gives it (anchor).
    model["extracellular"].append(store | {"initial_charge_C": 0.0} | CLOSED)
    for operator in model["operators"]:
        if operator["law"] == LABELS["compartment_law"]:
            break
    else:
        operator = {"law": LABELS["compartment_law"], "compartments": []}
        model["operators"].append(operator)
    operator["compartments"].append(
        {"id": compartment_id(cell), "node": store_id(cell), "patch": patch_id(cell)}
        | {"owner": cell}
        | NONE_OF
    )


def moieties(reactions):
    """What each species that the reactions name is made of: a species that no reaction makes is its
    own (None), and one that a reaction makes is what its reactants are."""
    made = {s for r in reactions for s in r["products"]}
    named = dict.fromkeys(s for r in reactions for s in (*r["reactants"], *r["products"]))
    parts = {s: {s: 1} for s in named if s not in made}
    waiting = list(reactions)
    while waiting:
        ready = [r for r in waiting if set(r["reactants"]) <= set(parts)]
        if not ready:
            raise no_section("the moieties of the reactions' species do not follow from them")
        for reaction in ready:
            waiting.remove(reaction)
            whole = {}
            for species, count in reaction["reactants"].items():
                for moiety, n in parts[species].items():
                    whole[moiety] = whole.get(moiety, 0) + n * count
            if list(reaction["products"].values()) != [1]:
                raise no_section("a reaction makes more than one of one species")
            (product,) = reaction["products"]
            if parts.setdefault(product, whole) != whole:
                raise no_section(f"two reactions make {product} of different moieties")
    return {s: None if s not in made else parts[s] for s in named}


def _write_reactions(raw, stores):
    model, found = raw["model"], {}
    for cell, store in stores.items():
        for name, reaction in entities(store["reactions"]):
            known(reaction, REACTION, f"{cell}'s reaction {name}")
            sites = found.setdefault(name, (reaction, []))[1]
            if found[name][0] != reaction:
                raise no_section(f"the reaction {name} is not the same in every store")
            sites.append(cell)
    if not found:
        return
    law, parts = string(shared(stores, "law")), moieties([r for r, _ in found.values()])
    model["operators"].append(
        {
            "law": LABELS["local_reactions"],
            "standard_concentration_mM": model["standard_concentration_mM"],
            "species": [
                {"id": s["id"], "moieties": parts[s["id"]], "standard_mu_RT": s["standard_mu_RT"]}
                | {"catalogue": None, "evidence": None}
                for s in model["species"]
                if s["id"] in parts
            ],
            "reactions": [
                _reaction(name, reaction, cells, law) for name, (reaction, cells) in found.items()
            ],
        }
    )


def _reaction(name, reaction, cells, law):
    inside = reaction["compartment"] == CYTOSOL
    if not inside and reaction["compartment"] != STORE:
        raise no_section(f"the reaction {name} names the compartment {reaction['compartment']!r}")
    sites = {"cells": list(cells)} if inside else {"outside": [store_id(c) for c in cells]}
    return {"id": name, "sites": sites, "law": law, "factors": []} | taken(
        reaction, ("reactants", "products", "forward_rate_per_s")
    )


def _write_membrane(raw, cell, membrane):
    model = raw["model"]
    if (membrane[CYTOSOL], membrane[STORE]) != (CYTOSOL, STORE):
        raise no_section(f"{cell}'s store's membrane names other compartments")
    if membrane["initial_charge_C"] != 0.0 or membrane["initial_voltage_V"] != 0.0:
        raise no_section(f"{cell}'s store is charged at time 0, and the cell's charge is its own")
    own = membrane["permeability_m_per_s"]
    permeability = {s["id"]: own.get(s["id"], 0.0) for s in model["species"]}
    if set(own) - set(permeability):
        raise no_section(f"{cell}'s store's permeability names a species the model has not")
    model["membranes"].append(
        {"id": patch_id(cell), "inside": cell, "outside": store_id(cell)}
        | taken(membrane, ("area_m2", "capacitance_F"))
        | {"permeability_m_per_s": permeability, "law": LABELS["constant_field"]}
        | {"pump": None, "calcium_pump": None}
    )


def _write_release(raw, cell, release):
    if release is None:
        return
    known(release, RELEASE, f"{cell}'s release")
    reads = [
        {"species": CALCIUM, "form": form, "half_saturation_mM": release[k], "hill_coefficient": n}
        for (k, count), form in HILL.items()
        for n in (release[count],)
    ]
    raw["model"].setdefault("species_conditions", []).append(
        {"id": condition_id(cell), "node": cell, "law": string(release["law"]), "reads": reads}
    )
    add_route(
        raw,
        release_id(cell),
        {"patch": patch_id(cell)},
        CALCIUM,
        release["permeability_m_per_s"],
        [condition_id(cell)],
    )


def _read_stores(raw):
    p = Pieces(raw)
    if not p.composite:
        return {}
    p.complete()
    return {"stores": mapped({cell: _read_store(raw, p, cell) for cell in p.store})}


def _read_store(raw, p, cell):
    model = p.model
    (node,) = (c for c in model["cells"] if c["id"] == cell)
    (store,) = (o for o in model["extracellular"] if o["id"] == p.store[cell])
    (patch,) = (m for m in model["membranes"] if m["id"] == p.patch[cell])
    species = {s["id"]: s for s in model["species"] if s["id"] in p.chemical}
    laws = {r["law"] for _, r in p.reactions.values()}
    out = {
        "law": label(laws.pop()) if len(laws) == 1 else sorted(label(x) for x in laws),
        "temperature_K": model["temperature_K"],
        "standard_concentration_mM": model["standard_concentration_mM"],
        "species": {name: _read_row(entry) for name, entry in species.items()},
        "compartments": {
            CYTOSOL: _read_compartment(node, species),
            STORE: _read_compartment(store, species),
        },
        "reactions": {
            name: _read_reaction(kind, r)
            for name, (kind, r) in p.reactions.items()
            if cell in p.reaction_route[name]
        },
    }
    out["reactions"] = mapped(out["reactions"])
    out["membrane"] = _read_membrane(raw, p, cell, store, patch, species)
    nothing_else(store, {"id", *NODE}, CLOSED, f"the store {store['id']}")
    entry = p.compartment[cell]
    nothing_else(entry, {"id", "node", "patch", "owner"}, NONE_OF, f"the compartment {entry['id']}")
    return out


NODE = (*COMPARTMENT, "fixed_charge_equivalent_fmol", "initial_charge_C")


def _read_row(entry):
    nothing_else(entry, {"id", "valence", "standard_mu_RT"}, {}, f"the row {entry['id']}")
    return {"valence": entry["valence"], "standard_mu_RT": entry.get("standard_mu_RT", 0.0)}


def _read_reaction(kind, reaction):
    named = {"id", "sites", "law", "reactants", "products", "forward_rate_per_s"}
    nothing_else(reaction, named, {"factors": []}, f"the reaction {reaction['id']}")
    return {"compartment": kind, "reactants": dict(reaction["reactants"])} | {
        "products": dict(reaction["products"]),
        "forward_rate_per_s": reaction["forward_rate_per_s"],
    }


def _read_compartment(node, species):
    amounts = node["initial_amount_fmol"]
    return {
        "volume_pL": node["volume_pL"],
        "initial_amount_fmol": {s: amounts[s] for s in species},
    }


def _read_membrane(raw, p, cell, store, patch, species):
    """The bounding patch, with each reacting species' leak route as its permeability."""
    own = patch["permeability_m_per_s"]
    leak = {s: route["permeability_m_per_s"] for (c, s), route in p.store_leak.items() if c == cell}
    both = sorted(s for s in leak if own[s] != 0.0)
    if both:
        raise no_section(
            f"the store of {cell} carries {', '.join(both)} by a route and by its patch"
        )
    out = {
        CYTOSOL: CYTOSOL,
        STORE: STORE,
        "area_m2": patch["area_m2"],
        "capacitance_F": patch["capacitance_F"],
        "initial_voltage_V": 0.0 + store["initial_charge_C"] / patch["capacitance_F"],
        "initial_charge_C": store["initial_charge_C"],
        "permeability_m_per_s": {s: leak.get(s, own[s]) for s in species},
    }
    pump = p.store_pump.get(cell)
    out["pump"] = None if pump is None else read_pump(raw, pump, cell)
    out["release"] = _read_release(p, cell)
    named = {"id", "inside", "outside", "area_m2", "capacitance_F", "permeability_m_per_s"}
    nothing_else(patch, named, BOUNDING, f"the patch {patch['id']}")
    for (owner, _), route in p.store_leak.items():
        if owner == cell:
            nothing_else(route, ROUTE, {}, f"the route {route['id']}")
    return out


ROUTE = {"id", "patch", "junction", "law", "species", "permeability_m_per_s"}
BOUNDING = {"law": LABELS["constant_field"], "pump": None, "calcium_pump": None}


def _read_release(p, cell):
    route = p.release.get(cell)
    if route is None:
        return None
    condition = p.release_condition[cell]
    reads = [r for r in condition["reads"] if r["species"] == CALCIUM]
    if [r["form"] for r in reads] != list(HILL.values()) or len(reads) != len(condition["reads"]):
        raise no_section(f"the release of {cell} does not read an activation and an inhibition")
    out = {"law": label(condition["law"]), "permeability_m_per_s": route["permeability_m_per_s"]}
    for (k, n), read in zip(HILL, reads, strict=True):
        out |= {k: read["half_saturation_mM"], n: read["hill_coefficient"]}
    nothing_else(route, ROUTE | {"factors"}, {}, f"the route {route['id']}")
    return out


def _take_stores(raw):
    """The inner model's own part of a composite: the ionic rows, the regions and the plasma
    membranes, with each reacting species' routes back as the permeabilities they were."""
    p = Pieces(raw)
    if not p.composite:
        return raw
    out = copy.deepcopy(raw)
    model, experiment, execution = out["model"], out["experiment"], out["execution"]
    for key in (
        "inner_model",
        "operators",
        "passive_routes",
        "transporters",
        "species_conditions",
        "standard_concentration_mM",
    ):
        model.pop(key, None)
    model["id"] = p.model["inner_model"]

    def ionic(values):
        return {s: values[s] for s in p.ionic}

    model["species"] = [
        {k: v for k, v in s.items() if k != "standard_mu_RT"}
        for s in model["species"]
        if s["id"] in p.ionic
    ]
    model["extracellular"] = [o for o in model["extracellular"] if o["id"] in p.regions]
    model["membranes"] = [m for m in model["membranes"] if m["id"] in p.plasma]
    for node in nodes(model):
        node["initial_amount_fmol"] = ionic(node["initial_amount_fmol"])
    for key, place in (("membranes", p.leak), ("junctions", p.junction_route)):
        for owner in model[key]:
            own = ionic(owner["permeability_m_per_s"])
            for (host, species), route in place.items():
                if host == owner["id"]:
                    if own[species] != 0.0:
                        raise no_section(f"{host} carries {species} by a route and by its own")
                    own[species] = route["permeability_m_per_s"]
                    nothing_else(route, ROUTE, {}, f"the route {route['id']}")
            owner["permeability_m_per_s"] = own
    for face in model["faces"]:
        face["diffusivity_m2_per_s"] = ionic(face["diffusivity_m2_per_s"])
    experiment["membrane_controls"] = [
        g for g in experiment["membrane_controls"] if g["membrane_id"] in p.plasma
    ]
    for key in ("reaction_controls", "transporter_controls"):
        experiment.pop(key, None)
    tolerance = execution["material_balance_atol_fmol"]
    execution["material_balance_atol_fmol"] = ionic(tolerance)
    return out


# ------------------------------------------------------------------ the plasma membranes' pieces


EXCHANGER = ("law", "capacity_fmol_per_s", "km_na_mM", "km_ca_mM")
EXCHANGING = {  # What every exchanger declares and no block says.
    "roles": {"Na": "Na", "Ca": CALCIUM},
    "orientation": {"N": "a"},
    "held_rows": [],
}


def _write_plasma_transport(block, raw):
    transport = entities(block.get("plasma_transport"))
    if transport and not entities(block.get("stores")):
        raise no_section("a world without stores has plasma_transport")
    for membrane, entry in transport:
        known(entry, ("pump", "exchanger"), f"{membrane}'s calcium transport")
        model = raw["model"]
        (patch,) = (m for m in model["membranes"] if m["id"] == membrane)
        if entry.get("pump") is not None:
            where = f"the calcium pump of {membrane}"
            write_pump(
                raw,
                plasma_pump_id(membrane),
                membrane,
                patch["inside"],
                entry["pump"],
                where,
                block.get(FUEL_POTENTIALS, OURS),
            )
        exchanger = entry.get("exchanger")
        if exchanger is not None:
            known(exchanger, EXCHANGER, f"the exchanger of {membrane}")
            model.setdefault("transporters", []).append(
                {
                    "id": exchanger_id(membrane),
                    "host": membrane,
                    "law": string(exchanger.get("law")),
                    "capacity_fmol_s": exchanger.get("capacity_fmol_per_s"),
                    "parameters": taken(exchanger, ("km_na_mM", "km_ca_mM")),
                    **copy.deepcopy(EXCHANGING),
                }
            )


def _read_plasma_transport(raw):
    p = Pieces(raw)
    if not (p.plasma_pump or p.exchanger):
        return {}
    inside = {m["id"]: m["inside"] for m in p.model["membranes"]}
    out = {}
    for membrane in p.plasma:
        entry = {}
        if membrane in p.plasma_pump:
            entry["pump"] = read_pump(raw, p.plasma_pump[membrane], inside[membrane])
        if membrane in p.exchanger:
            entry["exchanger"] = _read_exchanger(p.exchanger[membrane])
        if entry:
            out[membrane] = entry
    return {"plasma_transport": out}


def _read_exchanger(population):
    out = {"law": label(population["law"]), "capacity_fmol_per_s": population["capacity_fmol_s"]}
    out |= taken(population["parameters"], ("km_na_mM", "km_ca_mM"))
    named = {"id", "host", "law", "capacity_fmol_s", "parameters"}
    nothing_else(population, named, EXCHANGING, population["id"])
    return out


# ------------------------------------------------------------------ the calcium channels


def _write_calcium_channels(block, raw):
    raw["model"]["channels"] += channel_rows(block.get("calcium_channels"))


def _read_calcium_channels(raw):
    p = Pieces(raw)
    own = [c for c in p.model["channels"] if c["id"] in p.calcium_channels]
    return {"calcium_channels": read_channels(own)} if own else {}


def _take_calcium_channels(raw):
    p = Pieces(raw)
    if not p.calcium_channels:
        return raw
    out = copy.deepcopy(raw)
    model, experiment = out["model"], out["experiment"]
    model["channels"] = [c for c in model["channels"] if c["id"] in p.channels]
    experiment["channel_controls"] = [
        g for g in experiment["channel_controls"] if g["channel_id"] in p.channels
    ]
    return out


# ------------------------------------------------------------------ the release's further read


FURTHER = ("species_id", "law", "activation_mM", "activation_n")


def _write_further_reads(block, raw):
    for cell, entry in entities(block.get("ip3_release")):
        known(entry, FURTHER, f"{cell}'s further read")
        condition = Pieces(raw).release_condition.get(cell)
        if condition is None or condition["law"] != string(entry["law"]):
            raise no_section(f"{cell} has no release whose factor reads {entry['species_id']} so")
        condition["reads"].append(
            {
                "species": entry["species_id"],
                "form": "hill_activation",
                "half_saturation_mM": entry["activation_mM"],
                "hill_coefficient": entry["activation_n"],
            }
        )


def _further(condition):
    return [r for r in condition["reads"] if r["species"] != CALCIUM]


def _read_further_reads(raw):
    out = {}
    for cell, condition in Pieces(raw).release_condition.items():
        reads = _further(condition)
        if not reads:
            continue
        if [r["form"] for r in reads] != ["hill_activation"]:
            raise no_section(f"the release of {cell} reads more than one further activation")
        out[cell] = {
            "species_id": reads[0]["species"],
            "law": label(condition["law"]),
            "activation_mM": reads[0]["half_saturation_mM"],
            "activation_n": reads[0]["hill_coefficient"],
        }
    return {"ip3_release": out} if out else {}


def _take_further_reads(raw):
    out = copy.deepcopy(raw)
    for condition in Pieces(out).release_condition.values():
        condition["reads"] = [r for r in condition["reads"] if r["species"] == CALCIUM]
    return out


# ------------------------------------------------------------------ the calcium pieces' schedules


CONTROLS = (
    "store_passive",
    "store_pump",
    "store_release",
    "reactions",
    "calcium_pump",
    "exchanger",
    "calcium_channel",
)


def placed(schedules, owners, where):
    """Refuse a schedule of a piece that is not there, unless it is the default written out, which
    says nothing (SPEC §2.4): no place of a definition would hold it."""
    lost = [n for n, s in entities(schedules) if n not in owners and s != ONES]
    if lost:
        raise no_section(f"{where} has no place for {', '.join(lost)}")


def _of_patch(p, cell, controls):
    """The one schedule of a store's bounding patch: the engine opens the patch's own routes, its
    passive routes and its release by one availability."""
    given = _given(controls, "store_passive", cell, {})
    found = [given.get(s, ONES) for s in _store_carried(p, cell)]
    if cell in p.release:
        found.append(_given(controls, "store_release", cell))
    if any(s != found[0] for s in found):
        raise no_section(f"the store of {cell} has one schedule, and its block gives several")
    return found[0] if found else ONES


def _store_carried(p, cell):
    """The species that a store's membrane lets leak, in the rows' order."""
    (patch,) = (m for m in p.model["membranes"] if m["id"] == p.patch[cell])
    own = patch["permeability_m_per_s"]
    return [s for s in p.species if own.get(s, 0.0) != 0.0 or (cell, s) in p.store_leak]


def _write_calcium_controls(block, raw):
    p = Pieces(raw)
    if not p.composite:
        if block.get("calcium_controls"):
            raise no_section("a world without calcium pieces has calcium_controls")
        return
    controls = known(block.get("calcium_controls", {}), CONTROLS, "calcium_controls")
    experiment = raw["experiment"]
    for key, owners in (
        ("store_pump", p.store_pump),
        ("store_release", p.release),
        ("calcium_pump", p.plasma_pump),
        ("exchanger", p.exchanger),
        ("calcium_channel", p.calcium_channels),
    ):
        placed(controls.get(key), owners, f"calcium_controls.{key}")
    for cell, given in entities(controls.get("store_passive")):
        carried = _store_carried(p, cell) if cell in p.store else ()
        placed(given, carried, f"calcium_controls.store_passive of {cell}")
    for cell, given in entities(controls.get("reactions")):
        own = [name for name in p.reactions if cell in p.reaction_route[name]]
        placed(given, own, f"calcium_controls.reactions of {cell}")
    experiment["membrane_controls"] += [
        {"membrane_id": patch, "schedule": schedule(_of_patch(p, cell, controls))}
        for cell, patch in p.patch.items()
    ]
    experiment["channel_controls"] += groups(
        controls.get("calcium_channel"), p.calcium_channels, "channel_id"
    )
    own = {
        **{q["id"]: ("store_pump", cell) for cell, q in p.store_pump.items()},
        **{q["id"]: ("calcium_pump", m) for m, q in p.plasma_pump.items()},
        **{q["id"]: ("exchanger", m) for m, q in p.exchanger.items()},
    }
    if p.populations:
        experiment["transporter_controls"] = [
            {"transporter_id": q["id"], "schedule": schedule(_given(controls, *own[q["id"]]))}
            for q in p.populations
        ]
    reactions = dict(entities(controls.get("reactions")))
    if p.reactions:
        experiment["reaction_controls"] = [
            {
                "reaction_id": name,
                "site": cell if kind == CYTOSOL else p.store[cell],
                "schedule": [
                    {"time": t, "multiplier": m} for t, m in reactions.get(cell, {}).get(name, ONES)
                ],
            }
            for name, (kind, _) in p.reactions.items()
            for cell in p.reaction_route[name]
        ]


def _given(controls, key, owner, default=ONES):
    return dict(entities(controls.get(key))).get(owner, default)


def _read_calcium_controls(raw):
    p = Pieces(raw)
    if not p.composite:
        return {}
    experiment = raw["experiment"]
    of_patch = {g["membrane_id"]: pairs(g["schedule"]) for g in experiment["membrane_controls"]}
    of_channel = {g["channel_id"]: pairs(g["schedule"]) for g in experiment["channel_controls"]}
    of_population = {q["id"]: ONES for q in p.populations} | {
        g["transporter_id"]: pairs(g["schedule"])
        for g in experiment.get("transporter_controls", ())
    }
    of_reaction = {
        (g["reaction_id"], g["site"]): [[c["time"], c["multiplier"]] for c in g["schedule"]]
        for g in experiment.get("reaction_controls", ())
    }

    def reaction(name, cell):
        kind, _ = p.reactions[name]
        own = (name, cell if kind == CYTOSOL else p.store[cell])
        return copy.deepcopy(of_reaction.get(own, of_reaction.get((name, None))))

    out = {
        "store_passive": {
            cell: {s: copy.deepcopy(of_patch[patch]) for s in _store_carried(p, cell)}
            for cell, patch in p.patch.items()
        },
        "store_pump": {cell: of_population[q["id"]] for cell, q in p.store_pump.items()},
        "store_release": {cell: copy.deepcopy(of_patch[p.patch[cell]]) for cell in p.release},
        "reactions": {
            cell: {n: reaction(n, cell) for n in p.reactions if cell in p.reaction_route[n]}
            for cell in p.store
        },
        "calcium_pump": {m: of_population[q["id"]] for m, q in p.plasma_pump.items()},
        "exchanger": {m: of_population[q["id"]] for m, q in p.exchanger.items()},
        "calcium_channel": {c: of_channel[c] for c in p.calcium_channels},
    }
    return {"calcium_controls": {key: value for key, value in out.items() if value}}


# In the order of the literal blocks, which is the order they are written in (PART2_BLOCKS). The
# schedules are written last and read first, since every piece stands then.
SECTIONS = (
    Section(("stores",), _write_stores, _read_stores, _take_stores),
    Section(("plasma_transport",), _write_plasma_transport, _read_plasma_transport),
    Section(
        ("calcium_channels",),
        _write_calcium_channels,
        _read_calcium_channels,
        _take_calcium_channels,
    ),
    Section(("ip3_release",), _write_further_reads, _read_further_reads, _take_further_reads),
    Section(("calcium_controls",), _write_calcium_controls, _read_calcium_controls),
)
