"""The readouts of spec/READOUTS.md §2 and PART2 §6.1, read from a run's own rows: each name's
array, entities and sign, and which of them a world has.

Every series is one array of the engine's record with, at most, its sign turned: the engine books
leak and channel transfers outward, and READOUTS reads them inward (PART2 §6's table for Part 2's).
Nothing is summed here but a channel's heat over the species (READOUTS §2, PART2 §6.1). Where each
entity stands on an axis is read from the definition (pieces.py).
"""

from dataclasses import dataclass

import numpy as np

from cells.definitions.surface_pump_v3_spec import channel_laws
from validation.ensemble_reexpression.pieces import CALCIUM, CYTOSOL, STORE, Pieces


@dataclass(frozen=True)
class Series:
    """One family of readouts: the record's `array`, whose last axis is its entities' and whose axis
    before that, where it has one, is the species' or the modes'.

    entities(pieces): {entity: its place on the last axis}. names(pieces): {readout: its place on
    the axis before}, or one readout (a string) for an array without that axis. sign: -1 where the
    record's direction is the opposite one. total: the axis before is summed (a channel's heat over
    the species), and `names` is a string. present(pieces): whether a world has it; a family without
    an entity is not there either."""

    array: str
    names: object
    entities: object
    present: object = None
    sign: int = 1
    total: bool = False


# ------------------------------------------------------------------ the entities of an axis


def _of(key):
    """The places of every entity of one of the model's lists."""
    return lambda p: _ids(p, key)


def _ids(p, key):
    return {entity["id"]: k for k, entity in enumerate(p.model[key])}


def _regions(p):
    return {name: k for name, k in _ids(p, "extracellular").items() if name in p.regions}


def _plasma(p):
    return {name: k for name, k in _ids(p, "membranes").items() if name in p.plasma}


def _channels(p):
    return {name: k for name, k in _ids(p, "channels").items() if name in p.channels}


def _calcium_channels(p):
    return {name: k for name, k in _ids(p, "channels").items() if name in p.calcium_channels}


def _stores(p):
    places = _ids(p, "extracellular")
    return {cell: places[node] for cell, node in p.store.items()}


def _bounding(p):
    places = _ids(p, "membranes")
    return {cell: places[patch] for cell, patch in p.patch.items()}


def _routes(held):
    """{owner: its route's place}, of routes held by their owner and species (calcium's alone)."""
    return lambda p: {
        owner: p.route_index(route)
        for (owner, species), route in getattr(p, held).items()
        if species == CALCIUM
    }


def _releases(p):
    return {cell: p.route_index(route) for cell, route in p.release.items()}


def _populations(held):
    return lambda p: {
        owner: p.population_index(population) for owner, population in getattr(p, held).items()
    }


def _with_reactions(kind, places):
    """The places of the cells that have a reaction in the compartment of this kind."""
    return lambda p: {
        cell: k
        for cell, k in places(p).items()
        if any(own == kind and cell in p.reaction_route[r] for r, (own, _) in p.reactions.items())
    }


# ------------------------------------------------------------------ the readouts of an array


def _each(name, species):
    """One readout for each of these species, name_x."""
    return lambda p: {f"{name}_{x}": p.species.index(x) for x in species(p)}


def _calcium(name):
    """One readout, of calcium's row."""
    return lambda p: {name: p.species.index(CALCIUM)}


def _first_mode(name):
    return lambda p: {name: 0}


def _ionic(p):
    return p.ionic


def _own_ionic(p):
    """The ions that the inner model's own routes carry: the others have passive routes."""
    return [s for s in p.ionic if s not in p.reacting]


def _chemical(p):
    return p.chemical if p.composite else []


def _permeant(p):
    """The species that a channel population carries, calcium's apart, in the rows' order."""
    carried = {
        ion["species_id"]
        for c in p.model["channels"]
        if c["id"] in p.channels
        for ion in c["permeant_ions"]
    }
    return [s for s in p.species if s in carried]


def _store_carried(p):
    """The species that a store's own patch carries."""
    patches = [m for m in p.model["membranes"] if m["id"] in p.cell_of_patch]
    return [s for s in p.species if any(m["permeability_m_per_s"].get(s, 0.0) for m in patches)]


# ------------------------------------------------------------------ what a world has


def _inner(p):
    return not p.composite


def _any_permeability(p):
    return any(
        value
        for m in p.model["membranes"]
        if m["id"] in p.plasma
        for value in m["permeability_m_per_s"].values()
    )


def _pumped(p):
    return any(m["pump"] is not None for m in p.model["membranes"])


def _composite(p):
    return p.composite


SERIES = (
    Series("amount_increment", _each("n_cell", _ionic), _of("cells"), _inner),
    Series("amount_increment", _each("cyt", _chemical), _of("cells")),
    Series("extracellular_amount_increment", _each("store", _chemical), _stores),
    Series("extracellular_amount_increment", _each("n_out", _ionic), _regions),
    Series("membrane_transferred", _each("leak", _own_ionic), _plasma, _any_permeability, -1),
    Series("passive_transferred", _calcium("leak_Ca"), _routes("leak")),
    Series("channel_transferred", _each("channel", _permeant), _channels, sign=-1),
    Series("junction_transferred", _each("junction", _own_ionic), _of("junctions")),
    Series("passive_transferred", _calcium("junction_Ca"), _routes("junction_route"), sign=-1),
    Series("face_transferred", _each("face", _ionic), _of("faces")),
    Series("pump_cycles", "pump", _plasma, _pumped),
    Series("junction_gate", "junction_gate", _of("junctions")),
    Series("passive_transferred", _calcium("store_leak_Ca"), _routes("store_leak"), sign=-1),
    Series("membrane_transferred", _each("store_leak", _store_carried), _bounding),
    Series("cycle_count", _first_mode("store_pump"), _populations("store_pump")),
    Series("passive_transferred", _calcium("store_release"), _releases, sign=-1),
    Series("cycle_count", _first_mode("ca_pump"), _populations("plasma_pump")),
    Series("cycle_count", _first_mode("exchanger"), _populations("exchanger")),
    Series("channel_transferred", _calcium("ca_channel"), _calcium_channels, sign=-1),
    Series("membrane_dissipated_energy_pJ", "heat_leak", _plasma, _any_permeability),
    Series("passive_dissipated_energy_pJ", "heat_leak_Ca", _routes("leak")),
    Series("pump_dissipated_energy_pJ", "heat_pump", _plasma, _pumped),
    Series("channel_dissipated_energy_pJ", "heat_channel", _channels, total=True),
    Series("junction_dissipated_energy_pJ", "heat_junction", _of("junctions"), _inner),
    Series("junction_dissipated_energy_pJ", "heat_junction_own", _of("junctions"), _composite),
    Series("passive_dissipated_energy_pJ", "heat_junction_Ca", _routes("junction_route")),
    Series("face_dissipated_energy_pJ", "heat_face", _of("faces")),
    Series("passive_dissipated_energy_pJ", "heat_store_leak_Ca", _routes("store_leak")),
    Series("membrane_dissipated_energy_pJ", "heat_store_leak_K", _bounding),
    Series("cycle_dissipated_energy_pJ", "heat_store_pump", _populations("store_pump")),
    Series("passive_dissipated_energy_pJ", "heat_store_release", _releases),
    Series("cycle_dissipated_energy_pJ", "heat_ca_pump", _populations("plasma_pump")),
    Series("cycle_dissipated_energy_pJ", "heat_exchanger", _populations("exchanger")),
    Series("channel_dissipated_energy_pJ", "heat_ca_channel", _calcium_channels, total=True),
    Series(
        "reaction_dissipated_energy_pJ",
        "heat_reactions_cytosol",
        _with_reactions(CYTOSOL, _of("cells")),
    ),
    Series(
        "reaction_outside_dissipated_energy_pJ",
        "heat_reactions_store",
        _with_reactions(STORE, _stores),
    ),
    Series("metabolic_work_pJ", "work_pump", _plasma, _pumped),
    Series("cycle_metabolic_work_pJ", "work_store_pump", _populations("store_pump")),
    Series("cycle_metabolic_work_pJ", "work_ca_pump", _populations("plasma_pump")),
)


POTENTIALS = (  # Read from the observations' arrays.
    Series("observed_membrane_voltage_V", "voltage", _plasma),
    Series(
        "observed_extracellular_potential_V",
        "phi_out",
        lambda p: {
            name: k
            for name, k in _regions(p).items()
            if name != p.model["closure"]["gauge_reference"]
        },
    ),
    Series("observed_membrane_voltage_V", "store_voltage", _bounding, sign=-1),
)


def _numbers(values):
    return [float(v) for v in values]


def _columns(array, places, sign):
    """{entity: its column}; a turned sign never writes a negative zero."""
    array = np.asarray(array, dtype=float)
    if sign < 0:
        array = 0.0 - array
    return {name: _numbers(array[:, k]) for name, k in places.items()}


def _read(family, pieces, arrays, indices):
    """{readout: {entity ID: its values}} of a family of series at these rows of their arrays. No
    readout has two sources."""
    out = {}
    for series in family:
        if series.present is not None and not series.present(pieces):
            continue
        places = series.entities(pieces)
        if not places:
            continue
        array = np.asarray(arrays[series.array])[indices]
        if series.total:
            array = array.sum(axis=1)
        names = series.names if isinstance(series.names, str) else series.names(pieces)
        found = (
            {names: array} if isinstance(names, str) else {n: array[:, k] for n, k in names.items()}
        )
        for name, column in found.items():
            if name in out:
                raise ValueError(f"The readout {name} has two sources")
            out[name] = _columns(column, places, series.sign)
    return out


def rows(definition, arrays, indices):
    """{readout: {entity ID: its values}} at these rows of a run's record.

    definition: the engine's canonical form; arrays: the record's arrays by name, as trajectory.npz
    holds them; indices: the rows."""
    p = Pieces(definition)
    return (
        _read(SERIES, p, arrays, indices) | gates(p, arrays, indices) | extents(p, arrays, indices)
    )


def potentials(definition, arrays, indices):
    """{"voltage": {membrane: ...}, "phi_out": {region: ...}, "store_voltage": {cell: ...}} at these
    observations; phi_out for every region but the gauge, and each left out where there is none."""
    return _read(POTENTIALS, Pieces(definition), arrays, indices)


def gates(p, arrays, indices):
    """{gate_<name>: {channel: its values}}, each channel's gates in its law's order; calcium's
    channels' are ca_gate_<name> (PART2 §6.1)."""
    laws, out = channel_laws(), {}
    for slot, channel in enumerate(p.model["channels"]):
        array = np.asarray(arrays["channel_gate"])[indices]
        head = "ca_gate" if channel["id"] in p.calcium_channels else "gate"
        for k, name in enumerate(laws[channel["kinetic_law"]].gates):
            out.setdefault(f"{head}_{name}", {})[channel["id"]] = _numbers(array[:, k, slot])
    return out


def extents(p, arrays, indices):
    """{extent_<reaction>: {cell: its values}}, positive from reactants to products: each reaction's
    route at its cell, or at the cell's store (PART2 §6.1)."""
    out = {}
    for name, places in p.reaction_route.items():
        array = np.asarray(arrays["reaction_extent_fmol"])[indices]
        out[f"extent_{name}"] = _columns(array, places, 1)
    return out
