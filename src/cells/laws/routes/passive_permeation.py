"""cells.route.passive_neutral_permeation@1: the passive permeation law's kernel for neutral species (A5).

The inner-model note §11 (the law, D174/D176) and §7.4; ARCHITECTURE.md, "Transport laws by
physical contract". The kernel is the constant-field route at valence 0, which is Fick's law:

    J = A P m (c_out - c_in) / 1e-15   (fmol/s, positive inward, as electrochemistry.ghk_leak)

with c in mM = mol/m^3, A in m^2, P in m/s and m the route's availability. The core's passive
conventions (its note's §7.5): a membrane patch passes m = availability, a junction passes
m = gate x availability; the inner model books the heat in its own `passive_dissipated_energy_pJ`
and the transfers in `passive_transferred`. What the law adds to
the route is:
- **exact booking:** a step's heat is the exact free-energy decrease of what the route moved,
  from divided differences of each node's chemical free energy over the step (route_heat_pJ). So
  a passive route books Q >= 0, the heat of a closed pair equals the free-energy decrease to
  rounding, and a start at zero amount is admitted (the divided difference at n = 0 is finite).
  The core's declared booking calls these functions once it exists (D176 ruling, 15 November);
- **the trace and background policy** from the species registry (A7): the per-species material
  floor and the trace concentration a definition may start from (TracePolicy);
- finding 3's z = 0 bound term is the core's (I0); its rate per route is bound_rate_per_s.

Pure functions in the xp style of processes/; nothing floors or clips.
"""

from typing import Any, NamedTuple

import jax.numpy as jnp

from cells.laws.electrochemistry import R, ghk_leak
from cells.modules import Citation, RouteLaw

LAW_ID = "cells.route.passive_neutral_permeation@1"
SERIES_BELOW = 1e-6  # |x| below which (1 + x) log1p(x) / x takes its series (as D152).


class TracePolicy(NamedTuple):
    """The registry's policy for one species (A7): its material floor and its trace level."""

    material_floor_fmol: Any  # species-scaled ledger floor (D150's rule; FR-4 §10)
    trace_mM: Any  # the lowest declared start; a start below it is refused at the definition


def flux_fmol_s(c_in_mM, c_out_mM, area_m2, permeability_m_s, availability, *, xp=jnp):
    """Inward flux (fmol/s) of a neutral species: the constant-field route at valence 0."""
    return ghk_leak(c_in_mM, c_out_mM, 0.0, 0, 300.0, area_m2, permeability_m_s, availability,
                    xp=xp)


def bound_rate_per_s(area_m2, permeability_m_s, volume_pL, *, xp=jnp):
    """Finding 3's per-route material rate P A / V (1/s), V in pL (the core sums and bounds it)."""
    return permeability_m_s * area_m2 / (volume_pL * 1e-15)


def _plogp_ratio(x, *, xp):
    """(1 + x) log1p(x) / x, with its series for small |x| (the divided difference's kernel)."""
    small = xp.abs(x) < SERIES_BELOW
    safe = xp.where(small, 1.0, x)
    series = 1.0 + x / 2.0 - x * x / 6.0
    return xp.where(small, series, (1.0 + safe) * xp.log1p(safe) / safe)


def divided_potential_RT(n_start_fmol, n_end_fmol, volume_pL, *, xp=jnp):
    """mu-bar / RT of one ideal row over a step: [G(n1) - G(n0)] / (n1 - n0), G = n (ln(n/V) - 1).

    Exact for the inner model's per-row term. Where n0 = n1 it is the potential, ln(n/V); where one
    end is zero it is G(other)/other. Both ends nonnegative; c = n/V in mM.
    """
    n0, n1 = n_start_fmol, n_end_fmol
    both = (n0 > 0) & (n1 > 0)
    safe0 = xp.where(both, n0, 1.0)
    x = xp.where(both, (n1 - n0) / safe0, 0.0)
    regular = xp.log(safe0 / volume_pL) + _plogp_ratio(x, xp=xp) - 1.0
    other = xp.where(n1 > 0, n1, xp.where(n0 > 0, n0, 1.0))
    one_end = xp.log(other / volume_pL) - 1.0
    return xp.where(both, regular, one_end)


def route_heat_pJ(moved_in_fmol, mu_bar_in_RT, mu_bar_out_RT, temperature_K, *, xp=jnp):
    """Exact heat (pJ) of a passive neutral route over a step.

    moved_in_fmol: the amount the route moved inward (outside -> inside) over the step;
    mu_bar_*: each node's divided-difference potential over the step, from its total change by
    every route (divided_potential_RT), so the routes' heats sum to the exact free-energy decrease.
    Q = -moved_in (mu-bar_in - mu-bar_out) RT x 1e-3, nonnegative for a passive route.
    """
    return -1e-3 * R * temperature_K * moved_in_fmol * (mu_bar_in_RT - mu_bar_out_RT)


def start_admitted(amount_fmol, volume_pL, policy, *, xp=jnp):
    """The definition's trace check: a declared start at or above the policy's trace level."""
    return (amount_fmol >= 0) & (amount_fmol / volume_pL >= policy.trace_mM)


# The law's declaration (CORE_SEAMS §8.2): a route law of the passive routes kind, registered by
# the law registry's loader. Moved from kinds/passive_routes.py (the lead's recorded exception, 18
# November 2026). The work it names was named from memory, not read (CORE_SEAMS §15).
LAW = RouteLaw(
    LAW_ID,
    ("membrane", "junction"),
    "Fick's law: the constant-field flux at valence 0 (laws/routes/passive_permeation.py), with "
    "the exact booking of docs/INNER_MODEL_V4_DESIGN.md §7.5",
    material_bound="bound_rate_per_s",  # dt L <= 1 (the kind's bound_rate): CORE_SEAMS §18.
    host="cells.kind.passive_routes@1",
    provenance="cited",
    source=Citation(
        "Fick's law of diffusion (A. Fick, 1855, named from memory and not read; standard theory)",
        "docs/INNER_MODEL_V4_DESIGN.md §11",
        "no numbers taken: the law is a form, its permeability a definition's value",
    ),
)
