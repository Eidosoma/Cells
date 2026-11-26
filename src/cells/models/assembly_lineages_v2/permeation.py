"""cells.reaction.membrane_permeation@1: one molecule enters the lumen from the pool, across the membrane.

OL2: the design note's §0.2b rule 6, §0.2c rules 2, 3 and 15, and §0.2d items 2 and 4.

**The law.** A step of this law is an entry: one molecule of a pool place (finite or held) to the
lumen place of the same species, with locus `membrane`. Its forward at the firing state n is

    a⁺(n) = P_s · A(m) · ρ0 · θ⁺(n)        (`permeation_area`, whatever the exchange token)

with P_s the permeability (`permeability_m_per_s`, m/s), A(m) the bilayer's area on the pair's
common state (m²; the membrane does not change, so A(m) = A(n)), ρ0 = N_A·c0 (molecules per m³) and
θ⁺ the pool's activity alone (§0.2d item 4). The lumen enters only through F: the exit is this same
law applied to the products, with the same extent, as every reverse of this family is.

Its kernel is phase exchange's (exchange.geometric_log_direction).
"""

from cells.models.assembly_lineages_v2 import MEMBRANE_PERMEATION, MODEL_ID
from cells.models.assembly_lineages_v2.exchange import geometric_log_direction
from cells.models.assembly_lineages_v2.interfaces import ReactionLaw
from cells.modules import Citation

# The registration call is the registry's own (the surface exports it in module stage 1).
from cells.registry import laws as law_registry

TEST = (
    "tests/unit/test_assembly_lineages_v2_geometry.py::"
    "test_permeation_and_diffusion_radius_rates_are_their_closed_forms"
)
RATE_KEY = "permeability_m_per_s"

FORMULAS = {
    "forward": "a+(n) = P_s A(m) rho0 theta+(n): the entry, theta+ the pool's activity alone, "
    "A(m) = q W(m)/2 (m^2), rho0 = N_A c0 (molecules per m^3)",
    "reverse": "the exit: the same law applied to the products, k- = P_s exp(sum nu mu°), the "
    "same extent; the lumen enters only through F",
}

LAW = law_registry.BUILTIN.register(
    ReactionLaw(
        "cells.reaction.membrane_permeation@1",
        host=MODEL_ID,
        provenance="cited",
        source=Citation(
            "docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md §0.2b rule 6, §0.2c rules 2 and 3, §0.2d items "
            "2 and 4",
            "a solute crosses the membrane between the pool and the lumen, at P_s A",
            "no numbers taken",
            ("declared as the entry only, one molecule of one species",),
        ),
        test=TEST,
        energy_role="passive",
        energy_source=None,
        split="encounter",
        log_direction=geometric_log_direction,
        formulas=FORMULAS,
        rate_key={"insertion_area": RATE_KEY, "diffusion_radius": RATE_KEY},
        extent="geometric",
        limit=geometric_log_direction,  # OL6: one molecule a step, so ff(n, 1) = n: arithmetic A
        limit_formulas={
            "rule": "the same kernel on real counts: every falling factorial has a <= 1, so "
            "arithmetics A and C coincide (the design note's §1.4); the extent at real W",
        },
    )
)
assert LAW.law_id == MEMBRANE_PERMEATION
