"""cells.assembly_geometry.prescribed_shell@1: a prescribed protein shell's geometry, declared, not grown (FR-21).

The design is docs/ASSEMBLY_SHELL_DESIGN.md §4.2. The rulings are D244 and D246, and the shell's
acceptance is the requester's, relayed on 20 November 2026 (docs/FEATURE_REQUESTS.md, FR-21).

**The declaration.** `geometry: {"law": "cells.assembly_geometry.prescribed_shell@1", "area_m2": {value,
provenance}}`. The lumen is the existing `lumen_volume: declared`, with `phases.lumen.volume_L`.

**The wall is the membrane phase.** Its species (subunits, gate forms, free and bound sites) carry
no area quanta, and their counts set neither the shell's area nor its lumen. So the shell's entry
law, cells.reaction.shell_permeation@1, takes the constant extent A_sh·ρ0, and its conductance
G_s = P_s·A_sh does not follow the wall's counts, the site count or the lumen.

**What a shell refuses,** each at the parse with its reason:
- the bilayer's keys: `area_per_leaflet`, `area_quantum_m2`, `vesicle_floor`, a closure cost and
  `sigma_max_N_per_m` (no quanta, no floor, no tension, no lysis);
- `lumen_volume: osmotic`, since the wall does not swell, and `exchange_encounter`, since a shell
  takes up no amphiphiles;
- a join (phase exchange), the bilayer's permeation, division and shear (spec.py, division.py).

In version 1 there is one shell type per world, so the area and the lumen are world constants.
"""

import math

from cells.definitions.specs import ConfigError, finite_number
from cells.models.assembly_lineages_v2 import MODEL_ID, PRESCRIBED_SHELL
from cells.models.assembly_lineages_v2.interfaces import GeometryLaw
from cells.modules import Citation

# The registration call is the registry's own (the surface exports it in module stage 1).
from cells.registry import laws as law_registry

TEST = (
    "tests/unit/test_assembly_lineages_v2_geometry.py::"
    "test_a_shell_s_rates_follow_its_declared_conductance_alone"
)
AVOGADRO = 6.02214076e23  # mol⁻¹, exact (SI 2019).
BILAYER_KEYS = {
    "area_quantum_m2": "a shell's wall carries no area quanta",
    "area_per_leaflet": "a shell's wall carries no area quanta: its counts set neither its area "
    "nor its lumen",
    "vesicle_floor": "a prescribed wall cannot empty, so no floor applies",
    "closure_cost_kT": "a prescribed wall has no closure cost of its own",
    "kappa_kT": "a prescribed wall has no bending moduli",
    "kappa_bar_kT": "a prescribed wall has no bending moduli",
    "sigma_max_N_per_m": "a prescribed wall has no tension and does not lyse",
}


def parse_data(raw, world):
    if not isinstance(raw, dict):
        raise ConfigError("world: geometry is an object")
    for key, reason in BILAYER_KEYS.items():
        if key in raw:
            raise ConfigError(f"world: geometry: a prescribed shell declares no {key}: {reason}")
    if set(raw) != {"law", "area_m2"}:
        raise ConfigError(
            "world: geometry: a prescribed shell is {law, area_m2}; unknown="
            f"{sorted(set(raw) - {'law', 'area_m2'})}"
        )
    entry = raw["area_m2"]
    if not isinstance(entry, dict) or set(entry) != {"value", "provenance"}:
        raise ConfigError("world: geometry: area_m2 is {value, provenance}")
    if not isinstance(entry["provenance"], str) or not entry["provenance"]:
        raise ConfigError("world: geometry: area_m2 states its provenance ('unsourced' if so)")
    area = finite_number(entry["value"], "world: geometry: area_m2", positive=True)
    if world.conventions.lumen_volume != "declared":
        raise ConfigError(
            "world: geometry: a prescribed shell's lumen is declared (lumen_volume: declared, "
            "with phases.lumen.volume_L): the wall does not swell"
        )
    if world.volume("lumen") is None:
        raise ConfigError("world: geometry: a prescribed shell owns a lumen, with its volume_L")
    return {"area_m2": (area, entry["provenance"])}


def data_to_dict(data):
    return {"area_m2": dict(zip(("value", "provenance"), data["area_m2"], strict=True))}


def area(world):
    """A_sh (m²), the declared area."""
    return world.geometry[1]["area_m2"][0]


def rho0(world):
    """N_A·c0 in molecules per m³ (c0 in mol/L, times 10³ L/m³)."""
    return AVOGADRO * world.units.standard_concentration_mM * 1e-3 * 1e3


def log_extent(world):
    """ln(A_sh·ρ0): the shell permeation's constant extent, the same for every state."""
    return math.log(area(world) * rho0(world))


FORMULAS = {
    "area": "A_sh, declared (m^2): the wall's counts set neither it nor the lumen",
    "lumen": "V_lumen, declared (phases.lumen.volume_L)",
    "extent": "cells.reaction.shell_permeation@1: E = A_sh rho0, a constant of the world, rho0 = N_A c0 "
    "(molecules per m^3)",
    "conductance": "G_s = P_s A_sh (m^3/s) for each permeant, independent of the wall's "
    "inventory, the site count and the lumen",
    "free_energy": "no term of its own: no closure cost, no tension",
}

LAW = law_registry.BUILTIN.register(
    GeometryLaw(
        PRESCRIBED_SHELL,
        host=MODEL_ID,
        provenance="cited",
        source=Citation(
            "docs/ASSEMBLY_SHELL_DESIGN.md §4.2 (FR-21; D244, D246)",
            "a prescribed protein shell owns a lumen and an exchange area, both declared",
            "no numbers taken",
            ("one shell type per world in version 1: its area and lumen are world constants",),
        ),
        test=TEST,
        data=("area_m2",),
        parse_data=parse_data,
        data_to_dict=data_to_dict,
        formulas=FORMULAS,
    )
)
assert LAW.law_id == PRESCRIBED_SHELL
