"""cells.osmotic_lumen@1: the lumen's volume and free energy from the counts (OL2; §2.2, §4.1).

The lead's rulings are §0.2b rules 2 and 3, §0.2c rules 6–8 and §0.2d item 3
(docs/ORIGIN_OF_LIFE_OL2_OL3_CHECK.md §1.2–§1.6).

**The volume.** Water is fast, so the lumen's volume minimises F at fixed solute counts:

    V(n) = min(V_osm, V_sph(A(n))),   V_osm = N_L / (N_A c_ext),   V_sph = A^(3/2) / (6 √π)

with V in L (V_sph from A in m², times 10³), N_L every lumen species (§0.2c rule 6), c_ext the
outside's total osmolarity in mol/L, held, and A = q·W/2 (geometry.py).

**The term** (k_BT), an excess term over the ideal term with the lumen's X taken at 1:

    F_osm(n) = −N_L ln(N_A c0 V(n)) + N_A c_ext V(n),   and 0 at an empty lumen

Together with cells.ideal_mixing@1's lumen part, Σ_s [n_s μ°_s + ln n_s!], it is §0.2d item 3's
F_lumen. As an excess term it enters each reverse as exp(F_osm(n′) − F_osm(n′ − ν)), so every pair
keeps ln a⁺ − ln a⁻ = −ΔF + w exactly, whichever way V moves (the check note's §1.4).

**The tension** (N/m): σ = max(0, Δp·R/2), with Δp = k_BT (N_L/V − N_A c_ext) in molecules per m³
and R = (A/4π)^(1/2). It is 0 while the vesicle is floppy (V_osm ≤ V_sph), and continuous at the
kink. Its magnitude is formed from the physical area: A = q·W/2 first, then R, then
V = (4/3)πR³, so the area's unit cannot move it beyond rounding, and a power-of-two change of the
quantum (q/32 with W·32) gives the same float area and the same σ. Whether the vesicle is tense
stays F's test in log space (log_volume), which the tension does not change. (Repaired 20
November 2026 on the lead's ruling, from the Lean proofs project's finding at revision
c85b2b88: V had come from separate logarithms of the quantum and the footprint, and two encodings
of one vesicle, 1.45e-17 N/m apart, took different strict decisions at σ_max.)

**Lysis** (§0.2b rule 3, §0.2c rule 8, §0.2d item 7): an event whose end state has σ > σ_max fires
at its pair-rule rate and ends the life `lysed`. The membrane's and the lumen's molecules return to
their pool places as monomers, and the closure cost is released. The run books one ledger row for
the event, q = −(F(n_after) − F(n)) + w, with w the step's work and the reservoir work of held
places that receive molecules (runner.py).

**Incremental state:** (N_L, W), two exact integers, updated by each event's change.
"""

import math

import numpy as np

from cells.definitions.specs import ConfigError, require_fields
from cells.models.assembly_lineages_v2 import MODEL_ID, OSMOTIC_LUMEN
from cells.models.assembly_lineages_v2.interfaces import FreeEnergyTerm
from cells.models.assembly_lineages_v2.mass_action import entry_sum
from cells.modules import Citation

# The registration call is the registry's own (the surface exports it in module stage 1).
from cells.registry import laws as law_registry

TEST = (
    "tests/unit/test_assembly_lineages_v2_lumen.py::"
    "test_the_osmotic_volume_is_f_s_minimiser_and_its_tension_is_laplace_s"
)
AVOGADRO = 6.02214076e23
BOLTZMANN = 1.380649e-23  # J/K, exact (SI 2019).


def outside_mM(world):
    """c_ext in mM, from the term's data."""
    for law_id, data in world.terms:
        if law_id == OSMOTIC_LUMEN:
            return data["outside_osmolarity_mM"][0]
    return None


def parse_data(raw, world):
    require_fields(raw, {"law", "outside_osmolarity_mM"}, "world: free_energy: osmotic lumen")
    entry = raw["outside_osmolarity_mM"]
    if not isinstance(entry, dict) or set(entry) != {"value", "provenance"}:
        raise ConfigError(
            "world: osmotic lumen: outside_osmolarity_mM is {value, provenance} (the outside's "
            "total osmolarity, held: §0.2c rule 6)"
        )
    value = entry["value"]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not value > 0:
        raise ConfigError("world: osmotic lumen: outside_osmolarity_mM's value is positive")
    if not math.isfinite(value):
        raise ConfigError("world: osmotic lumen: outside_osmolarity_mM's value is finite")
    if not isinstance(entry["provenance"], str) or not entry["provenance"]:
        raise ConfigError("world: osmotic lumen: outside_osmolarity_mM states its provenance")
    return {"outside_osmolarity_mM": (float(value), entry["provenance"])}


def data_to_dict(data):
    value, provenance = data["outside_osmolarity_mM"]
    return {"outside_osmolarity_mM": {"value": value, "provenance": provenance}}


def constants(world):
    """(ln(N_A c0), N_A c_ext, ln(N_A c_ext), ln of V_sph's coefficient in W) for F_osm."""
    from cells.models.assembly_lineages_v2 import geometry

    c0 = world.units.standard_concentration_mM * 1e-3
    c_ext = outside_mM(world) * 1e-3
    q = world.geometry[1]["area_quantum_m2"]
    sphere = (q / 2.0) ** 1.5 / (6.0 * math.sqrt(math.pi)) * 1e3  # V_sph [L] = sphere · W^1.5
    del geometry
    return (
        math.log(AVOGADRO * c0),
        AVOGADRO * c_ext,
        math.log(AVOGADRO * c_ext),
        math.log(sphere),
    )


def layout(data, world, capacity):
    """(lumen [P] int64, quanta [P] int64, constants [4] float64)."""
    from cells.models.assembly_lineages_v2 import geometry

    lumen = np.zeros(capacity, dtype=np.int64)
    for i, place in enumerate(world.places):
        if place.phase == "lumen":
            lumen[i] = 1
    return (lumen, geometry.place_quanta(world, capacity), np.asarray(constants(world)))


def log_branches(nl, w, c, xp):
    """(ln V_osm, ln V_sph), both in L, of states with nl lumen molecules and footprint w (floats),
    each taken at 1 where its count is 0: the two branches of V = min(V_osm, V_sph), shared by
    log_volume, tension and host_derived."""
    log_osm = xp.log(xp.where(nl > 0, nl, 1.0)) - c[2]
    log_sph = c[3] + 1.5 * xp.log(xp.where(w > 0, w, 1.0))
    return log_osm, log_sph


def area_radius(w, q, xp):
    """(A in m², R in m) of footprint w: A = q·W/2, the physical area first, then R = (A/4π)^½."""
    area = q * w / 2.0
    return area, xp.sqrt(area / (4.0 * math.pi))


def log_volume(n_lumen, footprint, c, xp):
    """ln V (L) of states with N_L lumen molecules and footprint W; −inf at an empty lumen."""
    nl = n_lumen.astype(np.float64)
    w = footprint.astype(np.float64)
    log_osm, log_sph = log_branches(nl, w, c, xp)
    log_v = xp.minimum(log_osm, xp.where(w > 0, log_sph, -xp.inf))
    return xp.where(nl > 0, log_v, -xp.inf)


def free_energy(n_lumen, footprint, c, xp):
    """F_osm (k_BT) of states (N_L, W): 0 at an empty lumen, +inf where W ≤ 0 holds molecules."""
    nl = n_lumen.astype(np.float64)
    finite = (n_lumen > 0) & (footprint > 0)
    log_v = xp.where(finite, log_volume(n_lumen, footprint, c, xp), 0.0)  # no 0·(−inf) formed
    value = -nl * (c[0] + log_v) + c[1] * xp.exp(log_v)
    return xp.where(n_lumen > 0, xp.where(finite, value, xp.inf), 0.0)


def state(counts, totals, term_layout, xp):
    lumen, quanta, _ = term_layout
    return xp.sum(counts * lumen), xp.sum(counts * quanta)


def update(term_state, term_layout, places, delta, xp):
    lumen, quanta, _ = term_layout
    n_lumen, footprint = term_state
    return n_lumen + xp.sum(lumen[places] * delta), footprint + xp.sum(quanta[places] * delta)


def value(counts, tables, term_layout):
    """F_osm(n) on the host."""
    lumen, quanta, c = term_layout
    n = np.asarray(counts, dtype=np.int64)
    return float(free_energy(np.sum(n * lumen), np.sum(n * quanta), c, np))


def delta(term_state, term_layout, view, change, xp):
    """F_osm(n + change) − F_osm(n) for each step's change at its entries ([R, K] -> [R])."""
    lumen, quanta, c = term_layout
    n_lumen, footprint = term_state
    d_lumen = entry_sum(lumen[view.places] * change, xp)
    d_quanta = entry_sum(quanta[view.places] * change, xp)
    after_lumen = xp.maximum(n_lumen + d_lumen, 0)
    after_quanta = footprint + d_quanta
    before = free_energy(n_lumen + xp.zeros_like(d_lumen), footprint + xp.zeros_like(d_quanta), c,
                         xp)  # fmt: skip
    return free_energy(after_lumen, after_quanta, c, xp) - before


def tension(n_lumen, footprint, world_kT, q, c, xp):
    """σ (N/m) of states (N_L, W): Δp·R/2 where tense (V_osm > V_sph, so V = V_sph), and exactly
    0 while floppy or at the kink (§0.2b rule 3)."""
    nl = n_lumen.astype(np.float64)
    w = footprint.astype(np.float64)
    log_osm, log_sph = log_branches(nl, w, c, xp)
    tense = (n_lumen > 0) & (footprint > 0) & (log_osm > log_sph)
    area, radius = area_radius(w, q, xp)  # m², the physical area first (module docstring)
    volume_m3 = 4.0 / 3.0 * math.pi * radius**3
    safe = xp.where(tense, volume_m3, 1.0)
    pressure = world_kT * (nl / safe - c[1] * 1e3)  # N_A c_ext in molecules per m³
    return xp.where(tense, xp.maximum(0.0, pressure * radius / 2.0), 0.0)


def host_tension(world, counts):
    """σ (N/m) of one state, on the host (the parser's founder check, records)."""
    from cells.models.assembly_lineages_v2 import geometry

    n = np.asarray(counts, dtype=np.int64)
    lumen = np.asarray([p.phase == "lumen" for p in world.places], dtype=np.int64)
    quanta = geometry.place_quanta(world, len(world.places))
    kT = BOLTZMANN * world.units.temperature_K
    q = world.geometry[1]["area_quantum_m2"]
    return float(tension(np.sum(n * lumen), np.sum(n * quanta), kT, q, np.asarray(constants(world)),
                         np))  # fmt: skip


def host_volume_L(world, counts):
    from cells.models.assembly_lineages_v2 import geometry

    n = np.asarray(counts, dtype=np.int64)
    lumen = np.asarray([p.phase == "lumen" for p in world.places], dtype=np.int64)
    quanta = geometry.place_quanta(world, len(world.places))
    log_v = log_volume(np.sum(n * lumen), np.sum(n * quanta), np.asarray(constants(world)), np)
    return float(np.exp(log_v))


DERIVED = ("W", "A_m2", "R_m", "V_osm_L", "V_sph_L", "V_L", "tension_N_per_m")


def host_derived(world, counts):
    """One state's derived geometry on the host, from the kernel's own expressions (log_branches,
    area_radius, log_volume, tension): {W in quanta, A in m², R in m, V_osm, V_sph and V in L, σ in
    N/m} (OL5's kernel probe; validation/assembly_lineages_v2/FORMAT_OL2.md). V_osm is 0 at an
    empty lumen and V_sph 0 at W = 0; `counts` covers the world's places."""
    from cells.models.assembly_lineages_v2 import geometry

    n = np.asarray(counts, dtype=np.int64)
    lumen = np.asarray([p.phase == "lumen" for p in world.places], dtype=np.int64)
    quanta = geometry.place_quanta(world, len(world.places))
    n_lumen, footprint = np.sum(n * lumen), np.sum(n * quanta)
    c = np.asarray(constants(world))
    q = world.geometry[1]["area_quantum_m2"]
    log_osm, log_sph = log_branches(n_lumen.astype(np.float64), footprint.astype(np.float64), c,
                                    np)  # fmt: skip
    area, radius = area_radius(footprint.astype(np.float64), q, np)
    kT = BOLTZMANN * world.units.temperature_K
    return {
        "W": int(footprint),
        "A_m2": float(area),
        "R_m": float(radius),
        "V_osm_L": float(np.exp(log_osm)) if n_lumen > 0 else 0.0,
        "V_sph_L": float(np.exp(log_sph)) if footprint > 0 else 0.0,
        "V_L": float(np.exp(log_volume(n_lumen, footprint, c, np))),
        "tension_N_per_m": float(tension(n_lumen, footprint, kT, q, c, np)),
    }


FORMULAS = {
    "volume": "V(n) = min(N_L / (N_A c_ext), V_sph(A(n))) (L): N_L every lumen species, c_ext the "
    "outside's total osmolarity (mol/L, held), V_sph = A^(3/2) / (6 sqrt(pi)) from A = q W / 2",
    "F_osm": "-N_L ln(N_A c0 V(n)) + N_A c_ext V(n) (k_BT), 0 at an empty lumen; with the ideal "
    "term's lumen part at X = 1 it is the lumen's F",
    "tension": "sigma = max(0, dp R / 2), dp = k_BT (N_L / V - N_A c_ext), R = (A / 4 pi)^(1/2)",
    "lysis": "an event whose end state has sigma > sigma_max ends the life lysed; its molecules "
    "return to their pool places and the closure cost is released (one ledger row)",
}

TERM = law_registry.BUILTIN.register(
    FreeEnergyTerm(
        "cells.osmotic_lumen@1",
        host=MODEL_ID,
        provenance="cited",
        source=Citation(
            "docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md §2.2, §4.1, §0.2b rules 2 and 3, §0.2c rules "
            "6-8, §0.2d item 3 (van 't Hoff's osmotic pressure and Laplace's law, cited from "
            "memory there)",
            "the lumen's ideal solutes in a volume that water sets at once, against a held outside",
            "no numbers taken",
            (
                "water is fast: the volume minimises F at fixed solute counts",
                "c_ext is held; for a finite pool that is a declared approximation, and a run "
                "reports the pool's drift against it",
            ),
        ),
        test=TEST,
        part="excess",
        phases=("lumen", "membrane"),
        data=("outside_osmolarity_mM",),
        parse_data=parse_data,
        data_to_dict=data_to_dict,
        layout=layout,
        state=state,
        update=update,
        value=value,
        delta=delta,
        formulas=FORMULAS,
    )
)
assert TERM.law_id == OSMOTIC_LUMEN
