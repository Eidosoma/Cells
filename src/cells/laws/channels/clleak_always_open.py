"""cells.channel.clleak_always_open@1: an always-open chloride leak, the law and its declaration on @3.

A gate-free population: open at all times, so its flux is the host's constant-field flux of Cl⁻
(valence -1) at the population's permeability, abundance and availability, as @3's K⁺ and Na⁺ leaks'
fluxes are of theirs (laws/channels/kleak_always_open.py, naleak_always_open.py). Channel code 10
of cells.model.resolved_pump_tissue@3 (cells.channel_law@1), after the Kv1 laws' 5-9, registered by the law
registry's loader from @3's row of the model table (docs/CORE_SEAMS_DESIGN.md §8.2); it carries no
gate state, kernel or RK4 step bound. It takes the ID of the shared catalogue's always-open Cl⁻
population (laws/channels/leak_channels.py), the same form; this is @3's declaration of it.

Its constitutively open uses (D228 item 3, the H1 seam's Cl⁻ part): the population's availability
switches it, by a schedule or by cells.operator.species_regulated_availability@1's Hill factor of a ligand, so a
chloride conductance sits on a patch beside its others, with no Cl-only patch of its own. A gated
Cl⁻ law (voltage-gated, or Ca²⁺-activated) needs the H1 seam's reads, and is not this law.
"""

from cells.laws.channels.kv1p5_mh import VOLTAGE_DOMAIN_V  # @3's channel domain, -120..60 mV.
from cells.modules import ChannelLaw, Citation

LAW_ID = "cells.channel.clleak_always_open@1"
LAW = ChannelLaw(
    LAW_ID,
    10,
    (),
    (("Cl", -1, 1.0),),
    VOLTAGE_DOMAIN_V,
    None,
    host="cells.model.resolved_pump_tissue@3",
    provenance="cited",
    source=Citation(
        "Cells' own always-open leak form, @3's K⁺ and Na⁺ leaks' (laws/channels/"
        "kleak_always_open.py), with Cl⁻ as its permeant ion, moved by the host's constant-field "
        "flux",
        "docs/EXCITABLE_TISSUE_EQUATIONS.md, its flux law (the constant-field flux)",
        "no numbers taken: the permeability, abundance and availability are a definition's values",
    ),
    test="tests/unit/test_chloride_leak_law.py::test_a_chloride_population_moves_what_a_chloride_patch_does",
)
