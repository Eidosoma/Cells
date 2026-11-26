"""bounding_patch_constant_field@1: the bounding patch as an implicit route kind (FR-4, FR-5).

docs/COMPARTMENT_PH_TRANSFER_DESIGN.md §7.3, built against the inner-model note's §7.4 (g) 4. The
IMEX step's implicit set holds a declared list of route kinds. Each provides weights frozen at
the predicted state, a node-space Laplacian block added to the operator (C + a dt L) before its
one factorization, the implicit flux at each stage's potentials, the explicit remainder, and its
own heat. Faces are the first member; this kind is the second. It couples one face-free node j to
its owner cell i, giving four entries per compartment in the same dense factorization.

The constant-field flux into the cell (inward, as electrochemistry.ghk_leak) is split as

    J_s(V) = W_s V + [J_s(V) - W_s V],     W_s = dJ_s/dV at the predicted state,

with V = phi_i - phi_j. The first part is implicit: its charge current I = G V with
G = F 1e-15 sum_s z_s W_s (S), so the block is G [[1, -1], [-1, 1]] on (i, j). The second part,
the remainder, is explicit; its derivative in V vanishes at the predicted state, so the stiff
charge mode sits wholly in the implicit part. G >= 0, because the constant-field current
increases with V for every species, so the operator stays positive definite on the free nodes.

Heat: exact over a step (§7.3's booking). Each node's divided-difference potentials
(passive_permeation.divided_potential_RT) and the mean patch voltage V-bar, exact for a linear
capacitor, make the route's heat equal the free-energy decrease of what it moved. That is to
rounding when it is the only route at its nodes, and O(h^2) in attribution otherwise.

Pure functions in the xp style of processes/.
"""

import jax.numpy as jnp

from cells.laws.electrochemistry import (
    CHARGE_PER_FMOL,
    MOL_PER_FMOL,
    F,
    R,
    bernoulli,
    ghk_leak,
)

KIND_ID = "bounding_patch_constant_field@1"
SERIES_BELOW = 1e-3  # |x| below which B'(x) takes its series


def bernoulli_slope(x, *, xp=jnp):
    """B'(x) for B(x) = x/(e^x - 1), stable for every x (series near 0, e^-x form for x > 0)."""
    small = xp.abs(x) < SERIES_BELOW
    pos = x > 0
    xs = xp.where(small, 1.0, x)  # mask-safe: the regular forms never see 0/0
    em = xp.exp(-xp.abs(xs))  # e^-|x| <= 1
    # x > 0: (e^-x (1 - x) - e^-2x) / (1 - e^-x)^2 ;  x < 0: (e^x - 1 - x e^x) / (e^x - 1)^2
    pos_form = (em * (1.0 - xs) - em * em) / (1.0 - em) ** 2
    neg_form = (em - 1.0 - xs * em) / (em - 1.0) ** 2
    regular = xp.where(pos, pos_form, neg_form)
    series = -0.5 + x / 6.0 - x**3 / 180.0
    return xp.where(small, series, regular)


def flux_fmol_s(ci, co, voltage, valence, temperature, area, permeability, availability, *,
                xp=jnp):
    """The constant-field flux into the cell (fmol/s), as electrochemistry.ghk_leak."""
    return ghk_leak(ci, co, voltage, valence, temperature, area, permeability, availability,
                    xp=xp)


def flux_slope(ci, co, voltage, valence, temperature, area, permeability, availability, *,
               xp=jnp):
    """W = dJ/dV (fmol/s per V) of the inward flux, at the given (predicted) state."""
    k = valence * F / (R * temperature)
    x = k * voltage
    pref = area * permeability * availability / MOL_PER_FMOL
    return pref * k * (co * bernoulli_slope(x, xp=xp) + ci * bernoulli_slope(-x, xp=xp))


def weights(ci, co, voltage, valence, temperature, area, permeability, availability, *, xp=jnp):
    """Frozen for the step: (W [species, ...], G [...] in S), at the predicted state.

    ci, co [species, ...]; valence [species] broadcast against them.
    """
    w = flux_slope(ci, co, voltage, valence, temperature, area, permeability, availability, xp=xp)
    g = -CHARGE_PER_FMOL * xp.sum(valence * w, axis=0)  # I into j = -z F J_in; dI/d(phi_i-phi_j)
    return w, g


def laplacian_block(g, cell_index, node_index, n_nodes, *, xp=jnp):
    """The kind's node-space block: G on (i, i) and (j, j), -G on (i, j) and (j, i).

    One patch; the slot sums blocks over the declared patches before the one factorization.
    """
    block = xp.zeros((n_nodes, n_nodes))
    i, j = cell_index, node_index
    if xp is jnp:
        block = block.at[i, i].add(g).at[j, j].add(g).at[i, j].add(-g).at[j, i].add(-g)
    else:
        block[i, i] += g
        block[j, j] += g
        block[i, j] -= g
        block[j, i] -= g
    return block


def implicit_flux(w, voltage):
    """The implicit part at a stage's potentials: W V (fmol/s into the cell, per species)."""
    return w * voltage


def explicit_remainder(ci, co, voltage, valence, temperature, area, permeability, availability,
                       w, *, xp=jnp):
    """The explicit part: J(V) - W V, evaluated among the explicit rates."""
    j = flux_fmol_s(ci, co, voltage, valence, temperature, area, permeability, availability, xp=xp)
    return j - w * voltage


def step_heat_pJ(moved_in_fmol, mu_bar_in_RT, mu_bar_out_RT, valence, voltage_start,
                 voltage_end, temperature, *, xp=jnp):
    """Exact heat (pJ) of the route over a step: the free-energy decrease of what it moved.

    moved_in_fmol [species]: amounts moved into the cell over the step. mu_bar_*_RT: each node's
    divided-difference potentials (passive_permeation.divided_potential_RT) from its total change.
    The electrical term is V-bar times the charge moved in, exact for the patch's linear
    capacitor: Q = -RT sum_s dn_s (mu_in - mu_out) - V-bar F sum_s z_s dn_s.
    """
    chemical = 1e-3 * R * temperature * xp.sum(moved_in_fmol * (mu_bar_in_RT - mu_bar_out_RT),
                                               axis=0)
    charge_in_C = CHARGE_PER_FMOL * xp.sum(valence * moved_in_fmol, axis=0)
    electrical = 1e12 * 0.5 * (voltage_start + voltage_end) * charge_in_C
    return -(chemical + electrical)


# --- the per-compartment stage solve (§7.3): Newton on the compartment's own amounts -----------

SOLVER_ID = "cells.solver.imex_ars222_face_patch_electromigration@1"  # the implicit set: faces + patches
NEWTON_ITERATIONS = 6
NEWTON_RTOL = 1e-13


def patch_voltage(x, valence, fixed_fmol, other_charge_fmol, capacitance_F, *, xp=jnp):
    """V_b = phi_i - phi_j = -q_j / C_b, q_j from the node's fixed charge and every row there."""
    q = CHARGE_PER_FMOL * (fixed_fmol + xp.sum(valence * x, axis=0) + other_charge_fmol)
    return -q / capacitance_F


def node_inflow(x, ci, valence, temperature, area, permeability, availability, volume_pL,
                fixed_fmol, other_charge_fmol, capacitance_F, *, xp=jnp):
    """(J into j [species] fmol/s, V_b): minus the inward-to-cell constant-field flux."""
    v = patch_voltage(x, valence, fixed_fmol, other_charge_fmol, capacitance_F, xp=xp)
    j_in = flux_fmol_s(ci, x / volume_pL, v, valence, temperature, area, permeability,
                       availability, xp=xp)
    return -j_in, v


def stage_solve(x_hat, ci, valence, temperature, area, permeability, availability, volume_pL,
                fixed_fmol, other_charge_fmol, capacitance_F, gamma_h, *, xp=jnp,
                sign_of_rank_one=1.0, owner_hat_fmol=None, owner_volume_pL=None):
    """Solve R(x) = x - x_hat - gamma_h J_j(x) = 0 for the compartment's permeant amounts.

    Newton at a fixed count. The Jacobian is I - gamma_h (D + u w^T): D diagonal
    (dJ_j,s/dc_j,s / V), u_s = dJ_j,s/dV_b, w_t = dV_b/dx_t = -z_t F 1e-15 / C_b. Sherman-Morrison
    solves it in O(m). Returns (x, V_b, valid), valid where the residual is within
    NEWTON_RTOL (|x| + |x_hat|) for every species. sign_of_rank_one is for the planted-error test
    only: -1 flips w, and the solve must then fail.

    The owner (the core's question 2): with owner_hat_fmol and owner_volume_pL given, the owner's
    concentration follows the solve, c_i = (owner_hat - (x - x_hat)) / V_i. The owner receives
    exactly -(x - x_hat) at the same stage; its known part owner_hat carries what x_hat carries.
    That adds -dJ_j/dc_i / V_i to the diagonal, so the Jacobian stays diagonal plus rank one.
    Without them, ci is frozen at the stage's value, an O(V_j/V_i) approximation.
    """
    x = x_hat
    k = valence * F / (R * temperature)
    pref = area * permeability * availability / MOL_PER_FMOL
    w_vec = sign_of_rank_one * (-CHARGE_PER_FMOL * valence / capacitance_F)
    coupled = owner_hat_fmol is not None

    def owner_c(x_now):
        return (owner_hat_fmol - (x_now - x_hat)) / owner_volume_pL if coupled else ci

    for _ in range(NEWTON_ITERATIONS):
        ci_now = owner_c(x)
        inflow, v = node_inflow(x, ci_now, valence, temperature, area, permeability, availability,
                                volume_pL, fixed_fmol, other_charge_fmol, capacitance_F, xp=xp)
        r = x - x_hat - gamma_h * inflow

        d_diag = -pref * bernoulli(k * v, xp=xp) / volume_pL  # dJ_j/dx on the diagonal
        if coupled:  # dJ_j/dc_i = pref B(-kv), times dc_i/dx = -1/V_i
            d_diag = d_diag - pref * bernoulli(-k * v, xp=xp) / owner_volume_pL
        u = -flux_slope(ci_now, x / volume_pL, v, valence, temperature, area, permeability,
                        availability, xp=xp)  # dJ_j/dV_b
        a = 1.0 - gamma_h * d_diag
        uu = -gamma_h * u
        y = r / a
        z = uu / a
        delta = y - z * xp.sum(w_vec * y, axis=0) / (1.0 + xp.sum(w_vec * z, axis=0))
        x = x - delta
    inflow, v = node_inflow(x, owner_c(x), valence, temperature, area, permeability,
                            availability, volume_pL, fixed_fmol, other_charge_fmol, capacitance_F,
                            xp=xp)
    r = x - x_hat - gamma_h * inflow
    valid = xp.all(xp.abs(r) <= NEWTON_RTOL * (xp.abs(x) + xp.abs(x_hat))) & xp.all(x > 0)
    return x, v, valid


def patch_booking_pJ(moved_in_by_route, work_by_route, mu_bar_in_RT, mu_bar_out_RT, valence,
                     voltage_start, voltage_end, temperature, *, xp=jnp):
    """The patch-wide booking split per route: Q_r = (route r's exact heat) + W_r.

    moved_in_by_route [route, species]; work_by_route [route] (the pump's supplied work, 0 for a
    passive route). The divided differences use each node's total change from every route, so
    sum_r (Q_r - W_r) is the patch's exact free-energy decrease.
    """
    heat = step_heat_pJ(moved_in_by_route.T, mu_bar_in_RT[:, None], mu_bar_out_RT[:, None],
                        valence[:, None], voltage_start, voltage_end, temperature, xp=xp)
    return heat + work_by_route
