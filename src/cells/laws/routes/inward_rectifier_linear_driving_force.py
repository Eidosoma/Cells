"""inward_rectifier_linear_driving_force@1: an instantaneous inward-rectifier route for a valence +1
row, with no gate state, on cells.passive_routes@1 (D228 item 2; its first cited use is Kir4.1, the
Xenopus lane's K+ route).

For a route on a membrane patch of area A and opening m (the patch's availability, times any
routed factor), at V = phi_in - phi_out, with c_o and c_i the carried row's concentrations (mM) at
the patch's outside and inside ends:

    E = (R T / F) ln(c_o / c_i),   u = V - E,
    q(u) = 1 / (1 + exp((u - V_h) / s)),
    I = m A g_ref (c_o / K_ref)^(1/2) q(u) u        (A, outward positive),

one charge per ion, so the inward flux is J = -I / F (mol/s), -1e15 I / F in fmol/s.
Rectification is relative to E, not to the absolute voltage: q reads u only. The current vanishes
exactly where u = 0, its sign is that of u, and at fixed u it scales as the square root of c_o.

- **Dissipation:** I u = m A g_ref (c_o/K_ref)^(1/2) q u^2 >= 0, since q > 0. The passive routes
  kind books it as the leak's, by the tableau (heat_pJ_s); it is not exact-booked.
- **Slope conductance:** dI/dV = m A g_ref (c_o/K_ref)^(1/2) q [1 - u (1 - q) / s]. It turns
  negative where u (1 - q) > s, so the kind bounds the step by its magnitude (slope_conductance_S,
  the law's stage term). Where the kind has no potentials, it uses this voltage-free bound at the
  stage's concentrations (slope_bound_S): |d(q u)/du| <= q + |V_h/s + w| q (1 - q), with w =
  (u - V_h)/s, q (1 - q) <= 1/4 and |w| q (1 - q) < 0.225 for all w, so
  |dI/dV| <= m A g_ref (c_o/K_ref)^(1/2) (5/4 + |V_h| / (4 s)).
- **Domain:** c_o > 0 and c_i > 0, finite, at both ends of every route that conducts (g_ref > 0).
- **Its concentration factor** (c_o/K_ref)^(1/2) (concentration_factor) is sqrt(c_o / K_ref)
  wherever that quotient is a normal float, as it always was. Where c_o and K_ref are normal and
  their quotient is not, it is sqrt(c_o) / sqrt(K_ref), within a few ulps. A quotient is not
  normal when it overflows, or when it falls below the smallest normal float, which compiled CPU
  code flushes to zero. So (b g_ref, b^2 K_ref) declares the same route at extreme finite b too.
  The independent Lean project (lean/) found b = 2^-512 (K_ref 2^-1022 mM) refused before this.

**Its coefficients are the route's declaration, never the law's:** g_ref (S/m^2, >= 0; 0 is a
closed route), K_ref (mM, > 0), V_h (V, finite) and s (V, > 0: q falls as u rises, so the route
rectifies inward). None is sourced today, and the law takes no numbers. Kir4.1's conductance,
its c_o dependence and its rectification must be sourced before a claim rests on their values.

**A weak rectifier is declared through V_h and s alone,** with no code change. A large s (tens of
mV), V_h well above the working range of u, or both, keep q near 1 over that range, so the route
is nearly ohmic about E. As V_h grows without bound the route becomes the ohmic g_ref
(c_o/K_ref)^(1/2) u, and as s grows q tends to 1/2. A strong rectifier is a small s with V_h near 0.

**Scope.**
- **The square root in c_o is scoped to its preparation (D340).** One preparation supports the
  exponent: rat Kir4.1 in HEK293T, 0.51 over 15 to 153 mM. Another departs from it: human Kir4.1
  reaches about 19 pS at 40 mM, against 13.9 pS from a square root anchored at its 110 mM value of
  23 pS. One dataset is an indication, so the form stays, and a calibration carries only within its
  preparation.
- **The law is silent on external Na (D351).** In Na-poor solutions two inward-rectifier
  preparations depart from the square root in the same direction; with Na, the exponent comes close
  to it (about 0.40). These are indications, kept separate from the Kir4.1 line above.
- **The reference u = V - E is supported for changes of external K only (D352, D355).** For changes
  of internal K, one lab's series is an indication against a V - E reference; its numbers are in
  the block law's scope (laws/channels/open_channel_block.py).
"""

import jax.numpy as jnp

from cells.laws.electrochemistry import F, R
from cells.modules import Citation, RouteLaw

LAW_ID = "inward_rectifier_linear_driving_force@1"
VALENCE = 1
COEFFICIENTS = ("g_ref_S_per_m2", "k_ref_mM", "v_half_V", "slope_V")  # The route's, in order.
SUP_SLOPE = 1.25  # 1 + the bound 0.225 on |w| q (1 - q), rounded up: slope_bound_S.


def reversal_V(c_in_mM, c_out_mM, temperature_K, *, xp=jnp):
    """E = (R T / F) ln(c_o / c_i), V."""
    return R * temperature_K / F * xp.log(c_out_mM / c_in_mM)


def rectification(u_V, v_half_V, slope_V, *, xp=jnp):
    """(q, q (1 - q)) at u: q = 1 / (1 + exp((u - V_h)/s)), in the overflow-free logistic form."""
    w = (u_V - v_half_V) / slope_V
    e = xp.exp(-xp.abs(w))
    q = xp.where(w >= 0, e / (1.0 + e), 1.0 / (1.0 + e))
    return q, e / ((1.0 + e) * (1.0 + e))


def concentration_factor(c_out_mM, k_ref_mM, *, xp=jnp):
    """(c_o / K_ref)^(1/2), overflow-safe (the module docstring). The split form serves only
    where c_o and K_ref are at least the smallest normal float and their quotient is not normal;
    every other input keeps sqrt(c_o / K_ref) bit for bit. A subnormal operand keeps it too, since
    compiled CPU code reads one as zero.

    The double where: the split form reads 1 for both operands where the direct form is taken,
    and the direct form reads 1 for c_o where the split form is taken. So the branch not taken
    puts no inf or NaN into a value, or into a derivative in c_o. The direct form keeps K_ref
    itself as its divisor, since compiled code divides by a broadcast K_ref as a product with its
    reciprocal, and a selected divisor would change those bits. K_ref is a declared coefficient
    that the engine never differentiates. Its derivative is not finite at a split point, nor,
    as before, wherever K_ref^-2 overflows."""
    quotient = c_out_mM / k_ref_mM
    info = xp.finfo(xp.result_type(quotient))
    split = (c_out_mM >= info.tiny) & (k_ref_mM >= info.tiny)
    split = split & ((quotient < info.tiny) | (quotient > info.max))
    direct = xp.sqrt(xp.where(split, 1.0, c_out_mM) / k_ref_mM)
    roots = xp.sqrt(xp.where(split, c_out_mM, 1.0)) / xp.sqrt(xp.where(split, k_ref_mM, 1.0))
    return xp.where(split, roots, direct)


def _terms(c_in_mM, c_out_mM, voltage_V, temperature_K, area_m2, g_S_per_m2, k_ref_mM, v_half_V,
           slope_V, availability, *, xp):
    """(scale S, q, q (1 - q), u V), with every row that does not conduct (g = 0) read at c = 1 mM,
    so a row the route does not carry never meets a logarithm of zero."""
    on = g_S_per_m2 > 0
    c_in = xp.where(on, c_in_mM, 1.0)
    c_out = xp.where(on, c_out_mM, 1.0)
    u = voltage_V - reversal_V(c_in, c_out, temperature_K, xp=xp)
    q, q1q = rectification(u, v_half_V, slope_V, xp=xp)
    scale = availability * area_m2 * g_S_per_m2 * concentration_factor(c_out, k_ref_mM, xp=xp)
    return scale, q, q1q, u


def current_A(c_in_mM, c_out_mM, voltage_V, temperature_K, area_m2, g_S_per_m2, k_ref_mM,
              v_half_V, slope_V, availability, *, xp=jnp):
    """I = m A g_ref (c_o/K_ref)^(1/2) q(u) u (A), outward positive; 0 where g = 0."""
    scale, q, _, u = _terms(c_in_mM, c_out_mM, voltage_V, temperature_K, area_m2, g_S_per_m2,
                            k_ref_mM, v_half_V, slope_V, availability, xp=xp)
    return scale * q * u


def flux_fmol_s(c_in_mM, c_out_mM, voltage_V, temperature_K, area_m2, g_S_per_m2, k_ref_mM,
                v_half_V, slope_V, availability, *, xp=jnp):
    """The inward flux (fmol/s): one ion per charge, J = -1e15 I / F."""
    current = current_A(c_in_mM, c_out_mM, voltage_V, temperature_K, area_m2, g_S_per_m2,
                        k_ref_mM, v_half_V, slope_V, availability, xp=xp)
    return -1e15 * current / F


def heat_pJ_s(c_in_mM, c_out_mM, voltage_V, temperature_K, area_m2, g_S_per_m2, k_ref_mM,
              v_half_V, slope_V, availability, *, xp=jnp):
    """The dissipation 1e12 I u (pJ/s), never negative: the scale times q u u, with q > 0."""
    scale, q, _, u = _terms(c_in_mM, c_out_mM, voltage_V, temperature_K, area_m2, g_S_per_m2,
                            k_ref_mM, v_half_V, slope_V, availability, xp=xp)
    return 1e12 * (scale * q) * (u * u)


def slope_conductance_S(c_in_mM, c_out_mM, voltage_V, temperature_K, area_m2, g_S_per_m2,
                        k_ref_mM, v_half_V, slope_V, availability, *, xp=jnp):
    """|dI/dV| (S) at the state: the scale times |q - u q (1 - q) / s|. The law's stage term."""
    scale, q, q1q, u = _terms(c_in_mM, c_out_mM, voltage_V, temperature_K, area_m2, g_S_per_m2,
                              k_ref_mM, v_half_V, slope_V, availability, xp=xp)
    return scale * xp.abs(q - u * q1q / slope_V)


def slope_bound_S(c_in_mM, c_out_mM, temperature_K, area_m2, g_S_per_m2, k_ref_mM, v_half_V,
                  slope_V, availability, *, xp=jnp):
    """A voltage-free bound on |dI/dV| (S) at the state's concentrations: the scale times
    5/4 + |V_h| / (4 s) (the module docstring)."""
    scale, _, _, _ = _terms(c_in_mM, c_out_mM, 0.0, temperature_K, area_m2, g_S_per_m2, k_ref_mM,
                            v_half_V, slope_V, availability, xp=xp)
    return scale * (SUP_SLOPE + xp.abs(v_half_V) / (4.0 * slope_V))


# The law's declaration (CORE_SEAMS §8.2): a route law of the passive routes kind, registered by
# the law registry's loader. The description it cites was named, not read (CORE_SEAMS §15).
LAW = RouteLaw(
    LAW_ID,
    ("membrane",),
    "an instantaneous inward rectifier at valence +1: a current linear in the driving force "
    "V - E, rectified by a logistic of V - E, its conductance scaling as the square root of the "
    "outside concentration (laws/routes/inward_rectifier_linear_driving_force.py)",
    stage_term="slope_conductance_S",  # Its slope's magnitude in the stage rule: CORE_SEAMS §18.
    host="cells.passive_routes@1",
    provenance="cited",
    source=Citation(
        "the √[K]o dependence of inward-rectifier conductance and its rectification referred to "
        "E_K (S. Hagiwara and K. Takahashi, 1974, named from memory and not read; standard theory)",
        "the law's docstring",
        "no numbers taken: the law is a form, its coefficients a definition's values (g_ref, "
        "K_ref, V_h and s, each route's declaration, unsourced today)",
        ("no gate state: the rectification is instantaneous",),
    ),
)
