"""proton_constant_field_leak@1: passive proton permeation through free H+ (FR-4, FR-5).

docs/COMPARTMENT_PH_TRANSFER_DESIGN.md §7.1 and §9; the passive law's sibling
(laws/routes/passive_permeation.py). At a buffered node the proton row holds proton equivalents, not
free H+, so @3's constant-field law must not read it; this law reads free h at both sides through
their closures (rapid_proton_buffer@1, a stage read) and moves proton equivalents:

    J = A P m [h_out B(x) - h_in B(-x)] / 1e-15   (fmol/s, positive inward),   x = F V / (R T),

the constant-field flux at valence +1 with B the Bernoulli function (electrochemistry.ghk_leak).
m is the route's availability, or the routing door's factor for FR-5's damage leak.

Booking: the passive contract. Over a step the heat is the exact decrease of free energy of what
moved, from each node's divided-difference potentials (the closure's G* at buffered nodes) plus
the electrical term V-bar times the charge moved, when the core's declared booking exists. Until
then the instantaneous rate heat_pJ_s = J (mu_out - mu_in) applies, which is >= 0 in exact
arithmetic, and within rounding in float64: the small-|x| series can reverse sign in an interval of
relative width about 1e-33 around reversal. The booking checks use RAW_SUM_FACTOR*eps floors, not
an exact sign.

**A comparison rule (D344).** The reversal's Nernst direction is confirmed, and the law reproduces
it. At large gradients the nominal pipette and bath pH overstate the magnitude, so quantitative
comparisons use the intracellular pH at the time of the current measurement.
"""

import jax.numpy as jnp

from cells.laws.electrochemistry import F, R, electrochemical_potential, ghk_leak
from cells.modules import Citation, RouteLaw

LAW_ID = "proton_constant_field_leak@1"
VALENCE = 1


def flux_fmol_s(h_in_mM, h_out_mM, voltage_V, temperature_K, area_m2, permeability_m_s,
                availability, *, xp=jnp):
    """Inward proton flux (fmol/s) from free h at both sides; V = phi_in - phi_out."""
    return ghk_leak(h_in_mM, h_out_mM, voltage_V, VALENCE, temperature_K, area_m2,
                    permeability_m_s, availability, xp=xp)


def heat_pJ_s(flux_in_fmol_s, h_in_mM, h_out_mM, voltage_V, temperature_K, *, xp=jnp):
    """Instantaneous dissipation (pJ/s): J_in (mu-tilde_out - mu-tilde_in), >= 0 for this flux in
    exact arithmetic and within rounding in float64 (the small-|x| series can reverse sign in an
    interval of relative width about 1e-33 around reversal); the booking checks use
    RAW_SUM_FACTOR*eps floors, not an exact sign."""
    inward = electrochemical_potential(h_in_mM, h_out_mM, voltage_V, VALENCE, temperature_K, xp=xp)
    return -1e-3 * flux_in_fmol_s * inward


def conductance_S(h_in_mM, h_out_mM, voltage_V, temperature_K, area_m2, permeability_m_s,
                  availability, *, xp=jnp):
    """Max-side slope conductance F^2/RT P A m max(h) (S): the patch term for B7 and stage rules."""
    return F * F / (R * temperature_K) * permeability_m_s * area_m2 * availability * xp.maximum(
        h_in_mM, h_out_mM
    )


# The law's declaration (CORE_SEAMS §8.2): a route law of the passive routes kind, registered by
# the law registry's loader. Moved from kinds/passive_routes.py (the lead's recorded exception, 18
# November 2026). The works it names were named from memory, not read (CORE_SEAMS §15).
LAW = RouteLaw(
    LAW_ID,
    ("membrane",),
    "the Goldman-Hodgkin-Katz constant-field flux at valence +1 of free h, read through each "
    "node's closure (laws/transport/proton_leak.py)",
    stage_term="conductance_S",  # Its max-side slope in the stage rule: CORE_SEAMS §18.
    host="cells.passive_routes@1",
    provenance="cited",
    source=Citation(
        "the Goldman-Hodgkin-Katz constant-field flux (D. E. Goldman, 1943; A. L. Hodgkin and "
        "B. Katz, 1949; named from memory and not read; standard theory)",
        "docs/COMPARTMENT_PH_TRANSFER_DESIGN.md §7.1",
        "no numbers taken: the law is a form, its permeability a definition's value",
        ("it reads free h at both nodes through their closures and moves proton equivalents",),
    ),
)
