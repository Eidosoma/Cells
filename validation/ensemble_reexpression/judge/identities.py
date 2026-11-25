"""What the judge forms from a run's own rows (READOUTS section 5): the balances, the capacitor, the
energy identity, the exposure.

`Rows` is any reader with `get(series, times)`, which gives [time, entity] or None for a series that
the world does not have, and `voltage(times)` and `initial_voltage()`, by membrane.
"""

from __future__ import annotations

import math

import numpy as np

from . import constants as c
from .registration import World


def stoichiometry(world: World, membrane: str, species: str) -> int:
    """nu of the pump's cycle for a species: -3 for Na and +2 for K, 0 where there is none."""
    pump = world.block["membranes"][membrane]["pump"]
    return 0 if pump is None else pump["stoichiometry"].get(species, 0)


def membrane_flow(world: World, rows, species: str, times) -> np.ndarray:
    """leak + channel + nu pump of every membrane, into its cell, [time, membrane]. An absent series
    counts as zero.
    """
    out = np.zeros((len(times), len(world.membranes)))
    if not world.zero_routes:
        out += rows.get(f"leak_{species}", times)
    channels = [k for k in world.channels if world.block["channels"][k]["species_id"] == species]
    if channels:
        values = rows.get(f"channel_{species}", times)
        for i, channel in enumerate(channels):
            membrane = world.block["channels"][channel]["membrane_id"]
            out[:, world.membranes.index(membrane)] += values[:, i]
    if world.pumps:
        values = rows.get("pump", times)
        for i, membrane in enumerate(world.pumps):
            out[:, world.membranes.index(membrane)] += (
                stoichiometry(world, membrane, species) * values[:, i]
            )
    return out


def cell_residual(world: World, rows, species: str, times) -> np.ndarray:
    """n_cell less the sum of its routes, [time, cell]."""
    flow = membrane_flow(world, rows, species, times)
    expected = np.zeros((len(times), len(world.cells)))
    for i, membrane in enumerate(world.membranes):
        expected[:, world.cells.index(world.block["membranes"][membrane]["inside"])] += flow[:, i]
    if world.junctions:
        values = rows.get(f"junction_{species}", times)
        for i, junction in enumerate(world.junctions):
            block = world.block["junctions"][junction]
            expected[:, world.cells.index(block["from_cell"])] -= values[:, i]
            expected[:, world.cells.index(block["to_cell"])] += values[:, i]
    return rows.get(f"n_cell_{species}", times) - expected


def region_residual(world: World, rows, species: str, times) -> np.ndarray:
    """n_out less the sum of its routes, [time, region]."""
    flow = membrane_flow(world, rows, species, times)
    expected = np.zeros((len(times), len(world.regions)))
    for i, membrane in enumerate(world.membranes):
        expected[:, world.regions.index(world.block["membranes"][membrane]["outside"])] -= flow[
            :, i
        ]
    if world.faces:
        values = rows.get(f"face_{species}", times)
        for i, face in enumerate(world.faces):
            block = world.block["faces"][face]
            expected[:, world.regions.index(block["sender"])] -= values[:, i]
            expected[:, world.regions.index(block["receiver"])] += values[:, i]
    return rows.get(f"n_out_{species}", times) - expected


def closed_residual(world: World, rows, species: str, times) -> np.ndarray:
    """The sum over the world of a species' increments, [time, 1]."""
    cells = rows.get(f"n_cell_{species}", times).sum(axis=1)
    regions = rows.get(f"n_out_{species}", times).sum(axis=1)
    return (cells + regions)[:, None]


def charge_voltage(world: World, rows, times) -> np.ndarray:
    """(F 1e-15 / C) sum z n_cell of each membrane's cell, [time, membrane]."""
    F, unit = world.constants["F_C_per_mol"], world.constants["fmol_to_mol"]
    total = sum(world.valence[x] * rows.get(f"n_cell_{x}", times) for x in world.species)
    out = np.zeros((len(times), len(world.membranes)))
    for i, membrane in enumerate(world.membranes):
        block = world.block["membranes"][membrane]
        out[:, i] = F * unit / block["capacitance_F"] * total[:, world.cells.index(block["inside"])]
    return out


def capacitor_residual(world: World, rows, times) -> np.ndarray:
    """voltage - V0 less the charge's, [time, membrane]. V0 is the run's own voltage at time 0."""
    return rows.voltage(times) - rows.initial_voltage() - charge_voltage(world, rows, times)


def energy(world: World, rows, times) -> np.ndarray:
    """The energy identity's E, [time, 1]."""
    R, T = world.constants["R_J_per_mol_K"], world.block["temperature_K"]
    total = np.zeros(len(times))
    for group, prefix, order in (
        ("cells", "n_cell_", world.cells),
        ("outside", "n_out_", world.regions),
    ):
        for x in world.species:
            d = rows.get(f"{prefix}{x}", times)
            for i, compartment in enumerate(order):
                block = world.block[group][compartment]
                n0, volume = block["initial_amount_fmol"][x], block["volume_pL"]
                part = d[:, i] * (math.log(n0 / volume) - 1) + (n0 + d[:, i]) * np.log1p(
                    d[:, i] / n0
                )
                total += 1e-3 * R * T * part
    dV, V0 = charge_voltage(world, rows, times), rows.initial_voltage()
    for i, membrane in enumerate(world.membranes):
        total += (
            0.5
            * 1e12
            * world.block["membranes"][membrane]["capacitance_F"]
            * dV[:, i]
            * (2 * V0[i] + dV[:, i])
        )
    for series in rows.heats():
        values = rows.get(series, times)
        if values is not None:
            total += values.sum(axis=1)
    if world.pumps:
        total -= rows.get("work_pump", times).sum(axis=1)
    return total[:, None]


def heat_series(world: World) -> tuple:
    """The heats of a run of the candidate, by what the world has."""
    out = []
    if not world.zero_routes:
        out.append("heat_leak")
    if world.pumps:
        out.append("heat_pump")
    if world.channels:
        out.append("heat_channel")
    if world.junctions:
        out.append("heat_junction")
    if world.faces:
        out.append("heat_face")
    return tuple(out)


def fuel_energy(world: World, membrane: str) -> float:
    """The work of one fmol of a membrane's pump cycles on maintained fuel, in pJ."""
    fuel = world.block["membranes"][membrane]["pump"]["metabolism"]
    R, T = world.constants["R_J_per_mol_K"], world.block["temperature_K"]
    return -1e-3 * (
        fuel["delta_g0_J_per_mol"]
        + R * T * math.log(fuel["adp_mM"] * fuel["pi_mM"] / (1000 * fuel["atp_mM"]))
    )


def balance_bound(world: World, kind: str, species: str, steps: int):
    """(bound with e_store, bound without) of a class R balance. (0, 0) where the identity has zero
    scale (a class E zero).
    """
    scales, refs = world.data["scales"], world.data["amount_refs"]

    def part(name):
        return (
            c.ROUND_COUNT * c.EPS * (steps + 1) * scales[name],
            c.STORE_COUNT * c.EPS * (steps + 1) * refs.get(name, 0.0),
        )

    cell_round, cell_store = part(f"n_cell_{species}")
    out_round, out_store = part(f"n_out_{species}")
    if kind == "cells":
        return (
            (0.0, 0.0)
            if scales[f"n_cell_{species}"] == 0.0
            else (cell_round + cell_store, cell_round)
        )
    if kind == "regions":
        return (
            (0.0, 0.0) if scales[f"n_out_{species}"] == 0.0 else (out_round + out_store, out_round)
        )
    if scales[f"n_cell_{species}"] == 0.0 and scales[f"n_out_{species}"] == 0.0:
        return 0.0, 0.0
    cells, regions = len(world.cells), len(world.regions)
    without = cells * cell_round + regions * out_round
    return without + cells * cell_store + regions * out_store, without


def capacitor_bound(world: World, steps: int):
    """(bound with e_store, bound without) of the capacitor."""
    scale = world.data["scales"]["voltage"]
    without = (c.ROUND_COUNT * c.EPS * (steps + 1) + c.CLOSE_SHARE) * scale
    return without + c.STORE_COUNT * c.EPS * (steps + 1) * world.data["amount_refs"].get(
        "voltage", 0.0
    ), without


def exposure(path: list, end_s: float) -> float:
    """The time during which a path's availability is 1, from 0 to the end."""
    level, since, parts = 1, 0.0, []
    for time, value in path:
        if level == 1:
            parts += [time, -since]
        level, since = value, time
    if level == 1:
        parts += [end_s, -since]
    return math.fsum(parts)


def exposure_bound(end_s: float, segments: int) -> float:
    """2 eps end_s (2 + segments), READOUTS section 5."""
    return 2 * c.EPS * end_s * (2 + int(segments))
