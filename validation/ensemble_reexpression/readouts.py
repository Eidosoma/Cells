"""The readouts of spec/READOUTS.md §2, read from a run's own rows: each name's array, entities and
sign, and which of them a world has.

Every series is one array of the engine's record with, at most, its sign turned: the engine books
leak and channel transfers outward, and READOUTS reads them inward. Nothing is summed here but a
channel's heat over the species (READOUTS §2). Part 2 adds its series to SERIES and POTENTIALS.
"""

from dataclasses import dataclass

import numpy as np

from cells.definitions.surface_pump_v3_spec import channel_laws


def _any_permeability(definition, key="permeability_m_per_s"):
    return any(v for m in definition["model"]["membranes"] for v in m[key].values())


def _pumped(definition):
    return any(m["pump"] is not None for m in definition["model"]["membranes"])


def _has(key):
    return lambda definition: bool(definition["model"][key])


def _gauge(definition):
    return {definition["model"]["closure"]["gauge_reference"]}


@dataclass(frozen=True)
class Series:
    """One family of readouts: `name`, the record's array, and the definition's list of entities
    whose order is its last axis (or a function from the definition to their IDs).

    species: one readout for each species, named name_x. present(definition): whether a world has
    it. sign: -1 where the record's direction is the opposite one. summed: the axis it is summed
    over (a channel's heat over the species). only(definition): its species, where not all.
    without(definition): the entities it leaves out."""

    name: str
    array: str
    entities: object
    species: bool = False
    present: object = None
    sign: int = 1
    summed: int | None = None
    only: object = None
    without: object = None


def permeant(definition):
    """The species that a channel population of the world carries, in the definition's order."""
    carried = {
        ion["species_id"] for c in definition["model"]["channels"] for ion in c["permeant_ions"]
    }
    return [s["id"] for s in definition["model"]["species"] if s["id"] in carried]


SERIES = (
    Series("n_cell", "amount_increment", "cells", species=True),
    Series("n_out", "extracellular_amount_increment", "extracellular", species=True),
    Series(
        "leak",
        "membrane_transferred",
        "membranes",
        species=True,
        present=_any_permeability,
        sign=-1,
    ),
    Series(
        "channel",
        "channel_transferred",
        "channels",
        species=True,
        present=_has("channels"),
        sign=-1,
        only=permeant,
    ),
    Series(
        "junction", "junction_transferred", "junctions", species=True, present=_has("junctions")
    ),
    Series("face", "face_transferred", "faces", species=True, present=_has("faces")),
    Series("pump", "pump_cycles", "membranes", present=_pumped),
    Series("junction_gate", "junction_gate", "junctions", present=_has("junctions")),
    Series("heat_leak", "membrane_dissipated_energy_pJ", "membranes", present=_any_permeability),
    Series("heat_pump", "pump_dissipated_energy_pJ", "membranes", present=_pumped),
    Series(
        "heat_channel",
        "channel_dissipated_energy_pJ",
        "channels",
        present=_has("channels"),
        summed=1,
    ),
    Series(
        "heat_junction", "junction_dissipated_energy_pJ", "junctions", present=_has("junctions")
    ),
    Series("heat_face", "face_dissipated_energy_pJ", "faces", present=_has("faces")),
    Series("work_pump", "metabolic_work_pJ", "membranes", present=_pumped),
)


POTENTIALS = (  # Read from the observations' arrays.
    Series("voltage", "observed_membrane_voltage_V", "membranes"),
    Series("phi_out", "observed_extracellular_potential_V", "extracellular", without=_gauge),
)


def _ids(definition, entities):
    if callable(entities):
        return entities(definition)
    return [entity["id"] for entity in definition["model"][entities]]


def _numbers(values):
    return [float(v) for v in values]


def _by_entity(array, series, definition):
    """{entity: its column}; a turned sign never writes a negative zero."""
    array = np.asarray(array, dtype=float)
    if series.sign < 0:
        array = 0.0 - array
    out = set() if series.without is None else series.without(definition)
    ids = _ids(definition, series.entities)
    return {name: _numbers(array[:, k]) for k, name in enumerate(ids) if name not in out}


def _read(family, definition, arrays, indices):
    """{readout: {entity ID: its values}} of a family of series at these rows of their arrays."""
    species = [s["id"] for s in definition["model"]["species"]]
    out = {}
    for series in family:
        if series.present is not None and not series.present(definition):
            continue
        array = np.asarray(arrays[series.array])[indices]
        if series.summed is not None:
            array = array.sum(axis=series.summed)
        if not series.species:
            out[series.name] = _by_entity(array, series, definition)
            continue
        for name in species if series.only is None else series.only(definition):
            column = array[:, species.index(name)]
            out[f"{series.name}_{name}"] = _by_entity(column, series, definition)
    return {name: columns for name, columns in out.items() if columns}


def rows(definition, arrays, indices):
    """{readout: {entity ID: its values}} at these rows of a run's record.

    definition: the engine's canonical form; arrays: the record's arrays by name, as trajectory.npz
    holds them; indices: the rows."""
    return _read(SERIES, definition, arrays, indices) | gates(definition, arrays, indices)


def potentials(definition, arrays, indices):
    """{"voltage": {membrane: ...}, "phi_out": {region: ...}} at these observations; phi_out for
    every outside region but the gauge, and left out where there is no other."""
    return _read(POTENTIALS, definition, arrays, indices)


def gates(definition, arrays, indices):
    """{gate_<name>: {channel: its values}}, each channel's gates in its law's order."""
    laws, out = channel_laws(), {}
    for slot, channel in enumerate(definition["model"]["channels"]):
        array = np.asarray(arrays["channel_gate"])[indices]
        for k, name in enumerate(laws[channel["kinetic_law"]].gates):
            out.setdefault(f"gate_{name}", {})[channel["id"]] = _numbers(array[:, k, slot])
    return out
