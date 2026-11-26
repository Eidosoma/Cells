"""cells.reaction.shell_permeation@1: one molecule enters a prescribed shell's lumen from the pool (FR-21).

The design is docs/ASSEMBLY_SHELL_DESIGN.md §4.2, and the rulings are D244 and D246.

**The law.** A step of this law is an entry, in rule 2's form: one molecule of a pool place
(finite or held) goes to the lumen place of the same species, with locus `membrane`, in a world
whose geometry is cells.assembly_geometry.prescribed_shell@1. Its forward at the firing state n is

    a⁺(n) = P_s · A_sh · ρ0 · θ⁺(n)

with P_s the permeability (`permeability_m_per_s`, m/s, the bilayer's unit), A_sh the shell's
declared area (m²), ρ0 = N_A·c0 (molecules per m³) and θ⁺ the pool's activity alone. The exit is
this same law applied to the products, with the same extent, as every reverse of the family is.
So the conductance G_s = P_s·A_sh is a constant of the world: it follows neither the wall's
inventory nor the site count nor the lumen.

**Why a law of its own (D147).** cells.reaction.membrane_permeation@1's registered formula reads
A(m) = q·W(m)/2, the bilayer's area from its counts. A new law leaves that law's text as it is.

Its kernel is the geometric direction (exchange.geometric_log_direction), with the shell's
constant extent (kernel.py, dispatched by the geometry kind).

**Its large-count limit** (cells.assembly_representation.rate_equations@1; FR-47, D323) is the same kernel on real counts:
the step moves one molecule, so every falling factorial has one factor, ff(n, 1) = n, and the
extent is a constant, so the limit is the exact form (the representation dispatches the shell's
extent by the geometry kind, as the exact kernel does).
"""

from cells.models.assembly_lineages_v2 import MODEL_ID, SHELL_PERMEATION
from cells.models.assembly_lineages_v2.exchange import geometric_log_direction
from cells.models.assembly_lineages_v2.interfaces import ReactionLaw
from cells.modules import Citation

# The registration call is the registry's own (the surface exports it in module stage 1).
from cells.registry import laws as law_registry

TEST = (
    "tests/unit/test_assembly_lineages_v2_geometry.py::"
    "test_a_shell_s_rates_follow_its_declared_conductance_alone"
)
RATE_KEY = "permeability_m_per_s"

FORMULAS = {
    "forward": "a+(n) = P_s A_sh rho0 theta+(n): the entry, theta+ the pool's activity alone, "
    "A_sh the shell's declared area (m^2), rho0 = N_A c0 (molecules per m^3)",
    "reverse": "the exit: the same law applied to the products, k- = P_s exp(sum nu mu°), the "
    "same extent; the lumen enters only through F",
    "conductance": "G_s = P_s A_sh, a constant of the world",
}

LAW = law_registry.BUILTIN.register(
    ReactionLaw(
        SHELL_PERMEATION,
        host=MODEL_ID,
        provenance="cited",
        source=Citation(
            "docs/ASSEMBLY_SHELL_DESIGN.md §4.2 (FR-21; D244, D246)",
            "a solute crosses a prescribed shell between the pool and its lumen, at P_s A_sh",
            "no numbers taken",
            ("declared as the entry only, one molecule of one species",),
        ),
        test=TEST,
        energy_role="passive",
        energy_source=None,
        split="encounter",
        log_direction=geometric_log_direction,
        formulas=FORMULAS,
        rate_key=RATE_KEY,
        extent="geometric",
        limit=geometric_log_direction,  # FR-47: one molecule a step, a constant extent: exact
        limit_formulas={
            "rule": "the same kernel on real counts: one molecule a step, so ff(n, 1) = n, and "
            "the shell's constant extent A_sh rho0, so the limit is the exact form",
        },
    )
)
assert LAW.law_id == SHELL_PERMEATION
