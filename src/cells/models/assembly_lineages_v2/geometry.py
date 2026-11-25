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

**Scope (D340).** A footprint is declared for one temperature: each membrane species' area per
molecule is a declaration, and the engine does not vary it with temperature. Two independent
methods find fluid POPC expanding on warming (scattering +4.7% over 30 to 50 °C, solid-state NMR
+16.7% over 28 to 48 °C), and they disagree on the expansion's size. So a world compared across
temperatures declares the footprint measured at each temperature.
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
KEYS = {"law", "area_quantum_m2", "area_per_leaflet", "vesicle_floor"}
CLOSURE_FORMS = ({"closure_cost_kT"}, {"kappa_kT", "kappa_bar_kT"})  # §0.2e rule 6: one of them.
CLOSURE_LAW = "8 pi kappa + 4 pi kappa_bar (k_BT): Helfrich's closed sphere"
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


def _signed_provenanced(raw, name):
    """{value, provenance} with a finite value of any sign (κ̄, the Gaussian modulus)."""
    if not isinstance(raw, dict) or set(raw) != {"value", "provenance"}:
        raise ConfigError(f"world: geometry: {name} is {{value, provenance}}")
    if not isinstance(raw["provenance"], str) or not raw["provenance"]:
        raise ConfigError(f"world: geometry: {name}'s provenance is stated ('unsourced' if so)")
    value = raw["value"]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ConfigError(f"world: geometry: {name}'s value is a finite number")
    return float(value), raw["provenance"]


def parse_data(raw, world):
    if not isinstance(raw, dict):
        raise ConfigError("world: geometry is an object")
    osmotic = world.conventions.lumen_volume == "osmotic"
    if osmotic and "sigma_max_N_per_m" not in raw:
        raise ConfigError(
            "world: geometry: under lumen_volume osmotic the geometry declares sigma_max_N_per_m, "
            "{value, provenance}, the membrane's lysis tension (§0.2c rule 8)"
        )
    if not osmotic and "sigma_max_N_per_m" in raw:
        raise ConfigError(
            "world: geometry: sigma_max_N_per_m is declared only under lumen_volume osmotic "
            "(§0.2c rule 8)"
        )
    closure_keys = {k for form in CLOSURE_FORMS for k in form} & set(raw)
    if closure_keys not in CLOSURE_FORMS:
        raise ConfigError(
            "world: geometry: the closure cost is declared as closure_cost_kT {value, provenance} "
            "or as the bending moduli kappa_kT and kappa_bar_kT, each {value, provenance}, from "
            "which the engine computes 8 pi kappa + 4 pi kappa_bar (§0.2e rule 6); not "
            f"{sorted(closure_keys) or 'neither'}"
        )
    require_fields(
        raw, KEYS | closure_keys | ({"sigma_max_N_per_m"} if osmotic else set()), "world: geometry"
    )
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
        if not isinstance(entry, dict) or not {"quanta", "provenance"} <= set(entry):
            raise ConfigError(
                f"world: geometry: {name}'s area is {{quanta, provenance}}, with sourced_m2 and "
                "source optional and given together (§0.2e rule 5)"
            )
        extra = set(entry) - {"quanta", "provenance"}
        if extra not in (set(), {"sourced_m2", "source"}):
            raise ConfigError(
                f"world: geometry: {name}'s area gives sourced_m2 and source together, or neither "
                f"(§0.2e rule 5); not {sorted(extra)}"
            )
        k = bounded_integer(entry["quanta"], f"geometry: {name}'s quanta", minimum=1,
                            maximum=MAX_QUANTA)  # fmt: skip
        if not isinstance(entry["provenance"], str) or not entry["provenance"]:
            raise ConfigError(f"world: geometry: {name}'s area states its provenance")
        sourced = source = None
        if extra:
            sourced = finite_number(entry["sourced_m2"], f"geometry: {name}'s sourced_m2",
                                    positive=True)  # fmt: skip
            source = entry["source"]
            if not isinstance(source, str) or not source:
                raise ConfigError(f"world: geometry: {name}'s sourced area states its source")
            ratio = sourced / q
            if abs(k - ratio) > 0.5 * (1.0 + 1e-12):
                raise ConfigError(
                    f"world: geometry: {name}'s area rounds to a nearest quantum: {sourced:g} m² "
                    f"is {ratio:.6g} quanta of {q:g} m², so not {k} (§0.2c rule 4)"
                )
        areas.append((name, k, entry["provenance"], sourced, source))
    floor = _provenanced(raw["vesicle_floor"], "vesicle_floor", integer=True, key="quanta")
    if "closure_cost_kT" in raw:
        value, provenance = _provenanced(raw["closure_cost_kT"], "closure_cost_kT", integer=False)
        closure = {"value": value, "form": "declared", "closure_cost_kT": (value, provenance)}
    else:
        kappa = _provenanced(raw["kappa_kT"], "kappa_kT", integer=False)
        kappa_bar = _signed_provenanced(raw["kappa_bar_kT"], "kappa_bar_kT")
        value = 8.0 * math.pi * kappa[0] + 4.0 * math.pi * kappa_bar[0]
        if not value >= 0:
            raise ConfigError(
                f"world: geometry: the closure cost 8 pi kappa + 4 pi kappa_bar is {value:g} "
                "k_BT; a closed vesicle's is not negative"
            )
        closure = {"value": value, "form": "moduli", "kappa_kT": kappa, "kappa_bar_kT": kappa_bar}
    out = {
        "area_quantum_m2": q,
        "area_per_leaflet": tuple(areas),
        "vesicle_floor": floor,
        "closure": closure,
    }
    if osmotic:
        sigma = _provenanced(raw["sigma_max_N_per_m"], "sigma_max_N_per_m", integer=False)
        if not sigma[0] > 0:
            raise ConfigError("world: geometry: sigma_max_N_per_m's value is positive")
        out["sigma_max_N_per_m"] = sigma
    return out


def data_to_dict(data):
    areas = {}
    for name, k, provenance, sourced, source in data["area_per_leaflet"]:
        areas[name] = {"quanta": k, "provenance": provenance}
        if sourced is not None:
            areas[name].update(sourced_m2=sourced, source=source)
    closure = data["closure"]
    if closure["form"] == "declared":
        written = {"closure_cost_kT": dict(zip(("value", "provenance"), closure["closure_cost_kT"],
                                               strict=True))}  # fmt: skip
    else:
        written = {
            key: dict(zip(("value", "provenance"), closure[key], strict=True))
            for key in ("kappa_kT", "kappa_bar_kT")
        }
    out = {
        "area_quantum_m2": data["area_quantum_m2"],
        "area_per_leaflet": areas,
        "vesicle_floor": dict(zip(("quanta", "provenance"), data["vesicle_floor"], strict=True)),
        **written,
    }
    if "sigma_max_N_per_m" in data:
        out["sigma_max_N_per_m"] = dict(
            zip(("value", "provenance"), data["sigma_max_N_per_m"], strict=True)
        )
    return out


# ------------------------------------------------------------------ derived, on the host


def place_quanta(world, capacity):
    """k_i at each finite membrane place, 0 elsewhere ([P] int64); all 0 without a bilayer (FR-21's
    shell has no quanta)."""
    out = np.zeros(capacity, dtype=np.int64)
    if world.geometry is None or world.geometry[0] != BILAYER_GEOMETRY:
        return out
    k = {name: q for name, q, *_ in world.geometry[1]["area_per_leaflet"]}
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
    """C_close, once for the one living vesicle of a single-assembly world (0 with no geometry, and
    0 for FR-21's shell, which has no closure cost of its own)."""
    if world.geometry is None or world.geometry[0] != BILAYER_GEOMETRY:
        return 0.0
    return world.geometry[1]["closure"]["value"]


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
