"""cells.route.passive_constant_field_permeation@1: passive constant-field permeation of a charged species.

FR-15 F2, part P2 (the lead's rulings of 19 November 2026); the passive routes kind's charged
route law beside its neutral one (laws/routes/passive_permeation.py). It is
cells.route.proton_constant_field_leak@1's flux (laws/transport/proton_leak.py) at any valence z != 0, read
from the row's amounts at both ends instead of through a closure:

    J = A P m [c_out B(x) - c_in B(-x)] / 1e-15   (fmol/s, positive inward),   x = z F V / (R T),

with V = phi_in - phi_out, B the Bernoulli function (electrochemistry.ghk_leak), c in mM =
mol/m^3, A in m^2, P in m/s and m the route's opening (a patch's availability, after the routing
door's factors). The leak stays as it is (FR-4 is judged on it): it reads free h through B4's
closure, and this law reads amounts, so a row whose free/total split a closure owns is refused on
it (fail-closed; the hosting kind's check).

Step terms (the kind contract, docs/CORE_SEAMS_DESIGN.md §18):
- conductance_S: the max-side slope conductance F^2/RT z^2 P A m max(c) (S), the stage rule's
  charge term. It bounds the constant-field slope at every voltage, since
  |B'(x)| + |B'(-x)| = 1 and so |dJ/dx| <= max(c_in, c_out) (A P m / 1e-15);
- material_slope_per_s: the material slope at each end, |dJ/dn_in| = A P m B(-x) / V_in and
  |dJ/dn_out| = A P m B(x) / V_out (1/s, V in m^3), at the stage's amounts and potentials. It
  follows the voltage with no assumed range: a charged trace row's bound, which @3's static
  explicit-rate bound cannot hold (FR-15).

Heat: the instantaneous rate J (mu-tilde_out - mu-tilde_in) (pJ/s), the tableau's booking, as the
leak's: >= 0 in exact arithmetic and within rounding in float64 (the small-|x| series can reverse
its sign in an interval of relative width about 1e-33 around reversal), so the booking checks use
RAW_SUM_FACTOR*eps floors, not an exact sign. The neutral law's exact divided-difference booking
does not apply: the potentials move within the step.

Hosts: membrane patches, where its flux joins the patch's membrane current, and junctions (D310),
between two cells at the junction voltage V = phi_sender - phi_receiver. The hosting kind takes 2G
at each cell on a junction (G this law's conductance_S), and refuses, in version 1, a junction that
joins two capacitor components where one floats: such a component's offset is set by the field
solve's current balance, which holds @3's own currents, not a kind's (the lead's rulings on the @3
owner's two questions, D310).

Inert (docs/CORE_SEAMS_DESIGN.md §8.2): the module declares its one law as LAW and registers
nothing at import; its registration on the passive routes kind is the kinds owner's.

Pure functions in the xp style of processes/; nothing floors or clips.

**Scope (D351, D355).** The law has one permeability at every voltage. Two indications go against
carrying one across voltage: red-cell chloride and a valinomycin bilayer miss in opposite
directions. Neither is confirmed.

**A comparison rule (D344).** Raising outside K depolarizes squid axons, intact and perfused, and
the law reproduces the direction. Quantitative comparisons use preparation-specific permeability
ratios: its +12.63 mV against the measured +2.0 mV carried the intact axons' ratios to perfused
axons, whose own were never measured.
"""

import jax.numpy as jnp

from cells.laws.electrochemistry import (
    MOL_PER_FMOL,
    F,
    R,
    bernoulli,
    electrochemical_potential,
    ghk_leak,
)
from cells.modules import Citation, RouteLaw

LAW_ID = "cells.route.passive_constant_field_permeation@1"


def flux_fmol_s(
    c_in_mM,
    c_out_mM,
    voltage_V,
    valence,
    temperature_K,
    area_m2,
    permeability_m_s,
    availability,
    *,
    xp=jnp,
):
    """Inward flux (fmol/s) of a charged species from its amounts' concentrations at both ends;
    V = phi_in - phi_out."""
    return ghk_leak(
        c_in_mM,
        c_out_mM,
        voltage_V,
        valence,
        temperature_K,
        area_m2,
        permeability_m_s,
        availability,
        xp=xp,
    )


def heat_pJ_s(flux_in_fmol_s, c_in_mM, c_out_mM, voltage_V, valence, temperature_K, *, xp=jnp):
    """Instantaneous dissipation (pJ/s): J_in (mu-tilde_out - mu-tilde_in), >= 0 for this flux in
    exact arithmetic and within rounding in float64 (module docstring)."""
    inward = electrochemical_potential(c_in_mM, c_out_mM, voltage_V, valence, temperature_K, xp=xp)
    return -1e-3 * flux_in_fmol_s * inward


def conductance_S(
    c_in_mM,
    c_out_mM,
    voltage_V,
    valence,
    temperature_K,
    area_m2,
    permeability_m_s,
    availability,
    *,
    xp=jnp,
):
    """Max-side slope conductance F^2/RT z^2 P A m max(c) (S): the stage rule's charge term."""
    return (
        F
        * F
        / (R * temperature_K)
        * valence
        * valence
        * permeability_m_s
        * area_m2
        * availability
        * xp.maximum(c_in_mM, c_out_mM)
    )


def material_slope_per_s(
    voltage_V,
    valence,
    temperature_K,
    area_m2,
    permeability_m_s,
    availability,
    volume_in_pL,
    volume_out_pL,
    *,
    xp=jnp,
):
    """(|dJ/dn_in|, |dJ/dn_out|) (1/s): the flux's material slope at each end, V in pL (a held
    bath's slope is the hosting kind's to drop, as its volume is not finite)."""
    x = valence * F * voltage_V / (R * temperature_K)
    rate = area_m2 * permeability_m_s * availability / MOL_PER_FMOL  # fmol/s per mM.
    return (
        rate * bernoulli(-x, xp=xp) / volume_in_pL,
        rate * bernoulli(x, xp=xp) / volume_out_pL,
    )


# The law's declaration (CORE_SEAMS §8.2): a route law of the passive routes kind, inert until the
# kinds owner registers it there (the lead's ruling of 19 November 2026). The works it names were
# named from memory, not read (CORE_SEAMS §15).
LAW = RouteLaw(
    LAW_ID,
    ("membrane", "junction"),
    "the Goldman-Hodgkin-Katz constant-field flux of a charged species at its valence, read from "
    "its amounts at both ends (laws/routes/constant_field_permeation.py)",
    stage_term="conductance_S",  # Its max-side slope in the stage rule: CORE_SEAMS §18.
    material_term="material_slope_per_s",  # Its material slope per stage (FR-15's trace rows).
    host="cells.kind.passive_routes@1",
    provenance="cited",
    source=Citation(
        "the Goldman-Hodgkin-Katz constant-field flux (D. E. Goldman, 1943; A. L. Hodgkin and "
        "B. Katz, 1949; named from memory and not read; standard theory)",
        "docs/FEATURE_REQUESTS.md FR-15",
        "no numbers taken: the law is a form, its permeability a definition's value",
        (
            "it reads the row's amounts at both ends, so a row whose free/total split a closure "
            "owns is refused on it",
        ),
    ),
)
