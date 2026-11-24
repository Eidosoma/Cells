"""open_channel_block_weighted_modes@1: an open-channel blocker in weighted modes (FR-51, D327).

The law is Woodhull's single-site block (Woodhull 1973, J. Gen. Physiol. 61:687-708, PMID 4541078,
DOI 10.1085/jgp.61.6.687), applied in up to MAX_MODES weighted modes of one channel population.

A blocker of valence z_B is held at the constant concentration c_B on its declared side. Mode k
binds it with the dissociation constant

    K_k(V_ref) = K_k(0) exp(a_k V_ref),   a_k = s sgn(z_B) m_k F/(R T).

- s is +1 for a blocker from the outside and -1 for one from the inside.
- m_k is either |z_B| delta_k, with the electrical distance delta_k in [0, 1], or the effective
  valence z_eff,k > 0 (ruling 7).
- V_ref is the patch voltage V = phi_in - phi_out, or V - E of the population's permeant ion.

The layout carries the signed steepness s sgn(z_B) m_k (dimensionless), and a_k = steepness F/(R T)
in 1/V.

**The unblocked fraction.** Both fractions of each mode are formed directly:

    1 - theta_k = K_k/(c_B + K_k),   theta_k = c_B/(c_B + K_k),
    u = (sum_k w_k (1 - theta_k)) / (sum_k w_k).

Both sums run left to right, in declared mode order, over the static mode axis. So:
- u is exactly 1 at c_B = 0, whatever the weights' float sum;
- u is relatively accurate at strong block, where the literal 1 - sum w theta loses every digit
  (D327; fr51-channel-block-v1 §1.3).

**The slope bound.** u's slope in V_ref is bounded by

    |du/dV_ref| <= (sum_k w_k |a_k| theta_k (1 - theta_k)) / (sum_k w_k),

which the per-stage rules use.

The block is instantaneous and has no state. Arrays are [mode, ...], in NumPy or JAX. The admitted
domain (fr51-channel-block-v1 §1.2) keeps every intermediate a normal binary64 number, and
domain_valid refuses one that is not, since compiled CPU code flushes subnormals to zero.

**Scope (D355, D356).**
- The reversal reference ({"reversal_of": ion}) is supported for changes of that ion outside the
  cell only.
  - When external K changes, a non-blind two-lab replay (Lean commit fccbb5e5, run on engine
    revision 7ca7c9c1) finds the half-conductance shift tracking the measured reversal at about
    0.97 to 0.98 mV per mV.
  - One lab finds that raising internal K moves the half-block voltage about +5 mV, where V - E_K
    predicts -36 mV. That is an indication.
- kir2p1_mh2@1's gates read absolute voltage. A world in which external K changes declares Kir2.1
  as an always-open K population carrying this block on a K reversal reference (D356). That
  composition is development-only until the post-landing registration (D353) passes.
- Version 1's limits: the blocker is held at a declared constant concentration, not a species row;
  the block has no kinetics; and binding is trace, with no count.
"""

import numpy as np

from cells.laws.electrochemistry import F, R

LAW_ID = "open_channel_block_weighted_modes@1"
MAX_MODES = 4  # The mode axis is static, and its sums are unrolled.
MAX_STEEPNESS = 8.0  # m_k's limit: |a_k V_ref| <= 147 over the admitted domain.
K0_RANGE_MM = (1e-15, 1e15)
BLOCKER_RANGE_MM = (0.0, 1e3)
SUM_ULPS = 8  # The weights sum to 1 within this many ulps of 1 (the labels' rule).
SIDES = {"outside": 1, "inside": -1}  # s.
MEMBRANE_VOLTAGE = "membrane_voltage"  # The reference V; {"reversal_of": ion} is V - E.
NORMAL = float(np.finfo(np.float64).tiny)  # The smallest normal binary64 number.


def reversal_potential(inside_mM, outside_mM, valence, temperature, *, xp=np):
    """E (V) of an ion of this valence: (R T/(z F)) ln(c_o/c_i), as a difference of logarithms."""
    return R * temperature * (xp.log(outside_mM) - xp.log(inside_mM)) / (valence * F)


def exponent_per_volt(steepness, temperature):
    """a_k (1/V): the signed steepness s sgn(z_B) m_k times F/(R T)."""
    return steepness * (F / (R * temperature))


def dissociation(k0_mM, steepness, v_ref, temperature, *, xp=np):
    """K_k(V_ref) (mM) [mode, ...]: K_k(0) exp(a_k V_ref)."""
    return k0_mM * xp.exp(exponent_per_volt(steepness, temperature) * v_ref)


def fractions(blocker_mM, dissociation_mM):
    """(theta, 1 - theta) [mode, ...], each formed directly from c_B and K_k."""
    total = blocker_mM + dissociation_mM
    return blocker_mM / total, dissociation_mM / total


def unblocked_fraction(weight, free):
    """u [...]: (sum_k w_k (1 - theta_k)) / (sum_k w_k), both sums left to right over the mode
    axis (axis 0), unrolled."""
    numerator, denominator = weight[0] * free[0], weight[0]
    for k in range(1, weight.shape[0]):
        numerator = numerator + weight[k] * free[k]
        denominator = denominator + weight[k]
    return numerator / denominator


def slope(weight, steepness, temperature, theta, free, *, xp=np):
    """(sum_k w_k |a_k| theta_k (1 - theta_k)) / (sum_k w_k) (1/V) [...], u's slope bound in V_ref;
    each theta_k (1 - theta_k) is the product of the two directly formed fractions."""
    a = xp.abs(exponent_per_volt(steepness, temperature))
    numerator, denominator = weight[0] * a[0] * (theta[0] * free[0]), weight[0]
    for k in range(1, weight.shape[0]):
        numerator = numerator + weight[k] * a[k] * (theta[k] * free[k])
        denominator = denominator + weight[k]
    return numerator / denominator


def domain_valid(blocker_mM, dissociation_mM, *, xp=np):
    """[mode, ...] True where K_k and c_B + K_k are finite and normal."""
    total = blocker_mM + dissociation_mM
    return (
        xp.isfinite(dissociation_mM)
        & (dissociation_mM >= NORMAL)
        & xp.isfinite(total)
        & (total >= NORMAL)
    )
