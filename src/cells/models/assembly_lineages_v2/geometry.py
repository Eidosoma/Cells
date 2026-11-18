"""cells.bilayer_geometry@1: a closed bilayer vesicle's geometry from the counts (OL2).

The rulings are the design note's §0.2c rules 4, 5 and 8 and §0.2d items 1 and 2
(docs/ORIGIN_OF_LIFE_OL2_OL3_CHECK.md §1.2, §1.5).

**The footprint and the area.** Each membrane species declares its area per molecule per leaflet as
an integer k_i of a declared quantum q (m²), with its sourced area and source. The rounding is
declared as the nearest quantum: k_i must be an integer nearest to the sourced area over q (at a tie
either), and the parser refuses any other. The membrane's footprint is the exact
integer W(n) = Σ_i n_i k_i quanta, and the bilayer's area is A = q·W/2 (m²). From it:
R = (A/4π)^(1/2) (m), the area-equivalent radius, and V_sph(A) = A^(3/2)/(6√π) (m³). None is stored:
each is a function of the counts (R4).

**The encounter extents on m** (§0.2d item 2), for the geometric reaction laws (exchange.py,
permeation.py): `insertion_area` and `permeation_area` take E(m) = A(m) in m², `diffusion_radius`
takes E(m) = 4πR(m) in m, each times ρ0 = N_A·c0 in molecules per m³ (c0 in mol/L, times 10³ L/m³).
W(m) = W(n) − Σ_e k_e (n_e − m_e) is an exact integer, so both directions of a pair compute the same
extent, bit for bit. E(m) = 0 where W(m) = 0.

**The floor** (§0.2c rule 5): `vesicle_floor`, given in quanta, W_floor ≥ 1 (unsourced, and
marked so). A pair
whose step changes W and one of whose end states has W < W_floor has rate 0, tested on the end
states (kernel.py). A step that keeps W fires at its own rate. It requires `last_molecule: kept`,
and the founder is at or above it.

**Its part of F** is the closure cost C_close = 8πκ + 4πκ̄ (k_BT, declared, unsourced), once per
living vesicle (§0.2c rule 8): a constant here, so it enters no rate. It enters F's value (the
ledger), and later a division's and a lysis's ΔF.

Data, per world (`geometry`): {"law": "cells.bilayer_geometry@1", "area_quantum_m2": q,
"area_per_leaflet": {species: {"quanta": k, "sourced_m2": a, "source": "..."}},
"vesicle_floor": {"quanta": W_floor, "provenance": "unsourced"},
"closure_cost_kT": {"value": C, "provenance": "unsourced"}}. σ_max enters with the osmotic lumen
(lumen_volume: osmotic), which this version refuses.
"""

import math

import numpy as np

from cells.definitions.specs import ConfigError, bounded_integer, finite_number, require_fields
from cells.models.assembly_lineages_v2 import BILAYER_GEOMETRY, MODEL_ID
from cells.models.assembly_lineages_v2.interfaces import GeometryLaw
from cells.modules import Citation

# The registration call is the registry's own (the surface exports it in module stage 1).
from cells.registry import laws as law_registry

TEST = (
    "tests/unit/test_assembly_lineages_v2_geometry.py::"
    "test_insertion_area_at_equal_quanta_is_count_on_m_at_c_1"
)
KEYS = {"law", "area_quantum_m2", "area_per_leaflet", "vesicle_floor", "closure_cost_kT"}
AVOGADRO = 6.02214076e23  # mol⁻¹, exact (SI 2019).
MAX_QUANTA = 2**20


def _provenanced(raw, name, *, integer, key="value"):
    if not isinstance(raw, dict) or set(raw) != {key, "provenance"}:
        raise ConfigError(f"world: geometry: {name} is {{{key}, provenance}}")
    if not isinstance(raw["provenance"], str) or not raw["provenance"]:
        raise ConfigError(f"world: geometry: {name}'s provenance is stated ('unsourced' if so)")
    if integer:
        value = bounded_integer(raw[key], f"world: geometry: {name}", minimum=1, maximum=2**40)
    else:
        value = finite_number(raw[key], f"world: geometry: {name}")
        if value < 0:
            raise ConfigError(f"world: geometry: {name} is not negative")
    return value, raw["provenance"]


def parse_data(raw, world):
    if not isinstance(raw, dict):
        raise ConfigError("world: geometry is an object")
    if "sigma_max_N_per_m" in raw:
        raise ConfigError(
            "world: geometry: sigma_max_N_per_m belongs to lumen_volume: osmotic (§0.2c rule 8), "
            "which this version of the engine does not run yet"
        )
    require_fields(raw, KEYS, "world: geometry")
    q = finite_number(raw["area_quantum_m2"], "world: geometry: area_quantum_m2", positive=True)
    membrane = [p.species for p in world.places if p.phase == "membrane"]
    per = raw["area_per_leaflet"]
    if not isinstance(per, dict) or set(per) != set(membrane):
        raise ConfigError(
            "world: geometry: area_per_leaflet gives every membrane species exactly "
            f"({', '.join(membrane)}); a membrane species without its area is refused "
            "(§0.2b rule 1)"
        )
    areas = []
    for name in membrane:
        entry = per[name]
        require_fields(entry, {"quanta", "sourced_m2", "source"}, f"geometry: {name}'s area")
        k = bounded_integer(entry["quanta"], f"geometry: {name}'s quanta", minimum=1,
                            maximum=MAX_QUANTA)  # fmt: skip
        sourced = finite_number(entry["sourced_m2"], f"geometry: {name}'s sourced_m2",
                                positive=True)  # fmt: skip
        if not isinstance(entry["source"], str) or not entry["source"]:
            raise ConfigError(f"world: geometry: {name}'s area states its source")
        ratio = sourced / q
        if abs(k - ratio) > 0.5 * (1.0 + 1e-12):
            raise ConfigError(
                f"world: geometry: {name}'s area rounds to a nearest quantum: {sourced:g} m² is "
                f"{ratio:.6g} quanta of {q:g} m², so not {k} (§0.2c rule 4)"
            )
        areas.append((name, k, sourced, entry["source"]))
    floor = _provenanced(raw["vesicle_floor"], "vesicle_floor", integer=True, key="quanta")
    closure = _provenanced(raw["closure_cost_kT"], "closure_cost_kT", integer=False)
    return {
        "area_quantum_m2": q,
        "area_per_leaflet": tuple(areas),
        "vesicle_floor": floor,
        "closure_cost_kT": closure,
    }


def data_to_dict(data):
    return {
        "area_quantum_m2": data["area_quantum_m2"],
        "area_per_leaflet": {
            name: {"quanta": k, "sourced_m2": sourced, "source": source}
            for name, k, sourced, source in data["area_per_leaflet"]
        },
        "vesicle_floor": dict(zip(("quanta", "provenance"), data["vesicle_floor"], strict=True)),
        "closure_cost_kT": dict(zip(("value", "provenance"), data["closure_cost_kT"], strict=True)),
    }


# ------------------------------------------------------------------ derived, on the host


def place_quanta(world, capacity):
    """k_i at each finite membrane place, 0 elsewhere ([P] int64)."""
    out = np.zeros(capacity, dtype=np.int64)
    if world.geometry is None:
        return out
    k = {name: q for name, q, _, _ in world.geometry[1]["area_per_leaflet"]}
    for i, place in enumerate(world.places):
        if place.phase == "membrane":
            out[i] = k[place.species]
    return out


def rho0(world):
    """N_A·c0 in molecules per m³ (c0 in mol/L, times 10³ L/m³)."""
    return AVOGADRO * world.units.standard_concentration_mM * 1e-3 * 1e3


def log_constants(world):
    """(c_area, c_radius): ln(A ρ0) = c_area + ln W and ln(4πR ρ0) = c_radius + ½ ln W."""
    q, r0 = world.geometry[1]["area_quantum_m2"], rho0(world)
    c_area = math.log(q * r0 / 2.0)
    c_radius = math.log(4.0 * math.pi * r0) + 0.5 * math.log(q / (8.0 * math.pi))
    return c_area, c_radius


def floor_quanta(world):
    return world.geometry[1]["vesicle_floor"][0]


def closure_kT(world):
    """C_close, once for the one living vesicle of a single-assembly world (0 with no geometry)."""
    return 0.0 if world.geometry is None else world.geometry[1]["closure_cost_kT"][0]


def area_m2(world, footprint):
    return world.geometry[1]["area_quantum_m2"] * np.asarray(footprint, dtype=np.float64) / 2.0


FORMULAS = {
    "footprint": "W(n) = sum_i n_i k_i quanta (an exact integer), k_i the quanta of species i's "
    "area per molecule per leaflet",
    "area": "A = q W / 2 (m^2)",
    "radius": "R = (A / 4 pi)^(1/2) (m), the area-equivalent radius",
    "sphere": "V_sph = A^(3/2) / (6 sqrt(pi)) (m^3)",
    "extent": "insertion_area and permeation_area: E(m) = A(m); diffusion_radius: "
    "E(m) = 4 pi R(m); each times rho0 = N_A c0 (molecules per m^3); "
    "W(m) = W(n) - sum_e k_e (n_e - m_e)",
    "floor": "a pair whose step changes W, with an end state below W_floor, has rate 0",
    "free_energy": "C_close per living vesicle (a constant: no rate)",
}

LAW = law_registry.BUILTIN.register(
    GeometryLaw(
        "cells.bilayer_geometry@1",
        host=MODEL_ID,
        provenance="cited",
        source=Citation(
            "docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md §2.2, §4.1, §0.2c rules 4, 5 and 8, §0.2d items "
            "1 and 2 (Helfrich's closure cost and the sphere's geometry, cited from memory there)",
            "the bilayer's area from its molecules' footprints; the closure cost per vesicle",
            "no numbers taken",
            (
                "areas in integer quanta of a declared quantum, each rounded to the nearest one",
                "the area-equivalent radius for a floppy vesicle is a declared approximation",
            ),
        ),
        test=TEST,
        data=tuple(sorted(KEYS - {"law"})),
        parse_data=parse_data,
        data_to_dict=data_to_dict,
        formulas=FORMULAS,
    )
)
assert LAW.law_id == BILAYER_GEOMETRY
