"""cells.kind.rapid_proton_buffer@1: the rapid-buffer closure for protons at a node (FR-4).

docs/COMPARTMENT_PH_TRANSFER_DESIGN.md §4 (accepted direction, D176), built against the inner-model
note's §7.4 (g) 1: a per-stage algebraic read. A declared reduced representation (D175) of the
protonation reactions HB_k <=> H+ + B_k at its node.

State. At a buffered node the proton row holds the proton equivalents H_eq (free H+ plus protons
bound to the node's buffers, counted from each buffer's base form), and each buffer row holds its
total B_tot,k. Free h is algebraic: the unique positive root of

    g(h) = h + sum_k B_k h / (h + K_k) - H = 0,     H = H_eq / V,  B_k = B_tot,k / V   (mM).

The node's charge depends on the totals only (H_eq with +1, B_tot,k with the base form's valence),
so the inner model's charge sum over stored rows is exact as it stands.

K_k comes from the registry's standard potentials, never from a second parameter (B3):
K_k = c0 exp(-(mu_H + mu_B,k - mu_HB,k) / RT), with c0 the registry's declared
standard_concentration_mM (one authority) and mu in units of RT. pH stays defined against 1 M.

Energy (§4.4). The node's free energy at fixed totals is the minimum over speciation, G*, in the
inner model's convention (D152 §3.3): per species n (RT (ln c - 1) + mu°'), c in mM and
mu°' = RT (mu°/RT - ln c0). dG*/dH_eq is the free proton's potential. The closure owns the declared
term G* minus the inner model's own per-row term on the stored rows (RT n (ln(n/V) - 1)).

Envelope (§4.2, revised after the FR-4 references' run 02): the closure's estimated first-order lag
behind the kinetic system, (rho/lambda)(beta/ln 10 - h)/(h ln 10) pH units, stays within the
declared budget (1e-3 pH) at every stage. lambda = min_k k_on,k (h + b_k + K_k) over the buffers
present, and rho = ln 10 |dH/dt| / beta. The bound-to-free factor (beta/ln 10 - h)/h is about
1.5e4 at the FR-4 lumen's start, so a fixed lambda/rho ratio does not imply the budget. The step
size plays no part.

Pure functions in the xp style of processes/: no state, no layout, no clipping. Invalid inputs give
valid=False; the composing model refuses the step.
"""

from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from cells.laws.electrochemistry import R

READ_ID = "cells.kind.rapid_proton_buffer@1"
PH_REFERENCE_mM = 1000.0  # pH = -log10(h / 1 M), whatever the registry's c0
RESIDUAL_RTOL = 1e-13  # |g(h)| / H at the returned root; above it the read fails.
BISECTION_STEPS = 80  # Log-space bisection for several buffers: full double precision.
LAG_BUDGET_PH = 1e-3  # the declared budget the estimated lag must stay within (§4.2).
LN10 = float(np.log(10.0))


def dissociation_constant_mM(mu_acid_RT, mu_base_RT, mu_proton_RT=0.0, *, c0_mM, xp=jnp):
    """K (mM) of HB <=> H+ + B from the registry's standard potentials (units of RT, at c0)."""
    return c0_mM * xp.exp(-(mu_proton_RT + mu_base_RT - mu_acid_RT))


def residual(h, total_mM, buffer_mM, k_mM, *, xp=jnp):
    """g(h); total [...], h [...], buffer_mM and k_mM [buffer, ...] (broadcastable)."""
    return h + xp.sum(buffer_mM * h / (h + k_mM), axis=0) - total_mM


def _one_buffer(total, buffer, k, *, xp):
    b1 = k + buffer - total
    disc = xp.sqrt(b1 * b1 + 4.0 * k * total)
    # Both forms avoid cancellation: the first for b1 >= 0, the second for b1 < 0.
    safe = xp.where(b1 >= 0, b1 + disc, 1.0)
    return xp.where(b1 >= 0, 2.0 * k * total / safe, (disc - b1) / 2.0)


def _bisect(total, buffer, k, *, xp):
    lo = xp.log(total / (1.0 + xp.sum(buffer / k, axis=0)))
    hi = xp.log(total)
    for _ in range(BISECTION_STEPS):
        mid = 0.5 * (lo + hi)
        positive = residual(xp.exp(mid), total, buffer, k, xp=xp) > 0
        hi = xp.where(positive, mid, hi)
        lo = xp.where(positive, lo, mid)
    return xp.exp(0.5 * (lo + hi))


def free_proton(total_mM, buffer_mM, k_mM, *, xp=jnp):
    """Free h (mM) and validity, from H (mM) [...] and buffers B_k, K_k [buffer, ...].

    One buffer takes the closed form; several take log-space bisection on the bracket
    [H / (1 + sum B/K), H], on which g changes sign. Valid where H > 0 and finite, every B >= 0,
    every K > 0, and |g(h)| <= RESIDUAL_RTOL * H.
    """
    total = xp.asarray(total_mM)
    buffer = xp.asarray(buffer_mM)
    k = xp.broadcast_to(xp.asarray(k_mM), buffer.shape)
    ok_inputs = (
        xp.isfinite(total)
        & (total > 0)
        & xp.all(xp.isfinite(buffer) & (buffer >= 0), axis=0)
        & xp.all(xp.isfinite(k) & (k > 0), axis=0)
    )
    safe_total = xp.where(ok_inputs, total, 1.0)
    safe_buffer = xp.where(ok_inputs, buffer, 0.0)
    safe_k = xp.where(ok_inputs, k, 1.0)
    if buffer.shape[0] == 1:
        h = _one_buffer(safe_total, safe_buffer[0], safe_k[0], xp=xp)
    else:
        h = _bisect(safe_total, safe_buffer, safe_k, xp=xp)
    g = residual(h, safe_total, safe_buffer, safe_k, xp=xp)
    valid = ok_inputs & xp.isfinite(h) & (h > 0) & (xp.abs(g) <= RESIDUAL_RTOL * safe_total)
    return h, valid


def speciation(h, buffer_mM, k_mM, *, xp=jnp):
    """Acid and base concentrations (mM) of each buffer at free h: (a_k, b_k), [buffer, ...]."""
    acid = buffer_mM * h / (h + k_mM)
    return acid, buffer_mM - acid


def buffer_capacity(h, buffer_mM, k_mM, *, xp=jnp):
    """beta = -dH/dpH (mM per pH unit) at free h."""
    return LN10 * (h + xp.sum(buffer_mM * k_mM * h / (h + k_mM) ** 2, axis=0))


def free_per_total(h, buffer_mM, k_mM, *, xp=jnp):
    """dh/dH at fixed buffer totals: 1 / (1 + sum B K / (h + K)^2)."""
    return 1.0 / (1.0 + xp.sum(buffer_mM * k_mM / (h + k_mM) ** 2, axis=0))


def _row_term(n_fmol, c_mM, mu_RT, c0, *, xp):
    """n (ln c - 1 + mu/RT - ln c0), with n ln n -> 0 at n = 0 (units of RT times fmol)."""
    safe_c = xp.where(n_fmol > 0, c_mM, 1.0)
    return xp.where(n_fmol > 0, n_fmol * (xp.log(safe_c) - 1.0 + mu_RT - xp.log(c0)), 0.0)


def closure_free_energy_pJ(total_fmol, buffer_fmol, volume_pL, k_mM, mu_proton_RT, mu_acid_RT,
                           mu_base_RT, temperature_K, *, c0_mM, xp=jnp):
    """G* (pJ) of one or more nodes at the closure's speciation, with free energy, valid.

    total_fmol [...]; buffer_fmol, k_mM, mu_acid_RT, mu_base_RT [buffer, ...] (broadcastable).
    """
    total = total_fmol / volume_pL
    buffer = buffer_fmol / volume_pL
    h, valid = free_proton(total, buffer, k_mM, xp=xp)
    acid, base = speciation(h, buffer, k_mM, xp=xp)
    c0 = c0_mM  # the registry's standard_concentration_mM
    terms = _row_term(h * volume_pL, h, mu_proton_RT, c0, xp=xp) + xp.sum(
        _row_term(acid * volume_pL, acid, mu_acid_RT, c0, xp=xp)
        + _row_term(base * volume_pL, base, mu_base_RT, c0, xp=xp),
        axis=0,
    )
    return 1e-3 * R * temperature_K * terms, valid


def inner_row_energy_pJ(n_fmol, volume_pL, temperature_K, *, xp=jnp):
    """The inner model's per-row chemical term, RT n (ln(n/V) - 1) with n/V in mM (pJ)."""
    c = xp.where(n_fmol > 0, n_fmol / volume_pL, 1.0)
    return 1e-3 * R * temperature_K * xp.where(n_fmol > 0, n_fmol * (xp.log(c) - 1.0), 0.0)


def declared_term_pJ(total_fmol, buffer_fmol, volume_pL, k_mM, mu_proton_RT, mu_acid_RT,
                     mu_base_RT, temperature_K, *, c0_mM, xp=jnp):
    """The closure's declared free-energy term: G* less the inner model's stored-row terms."""
    g_star, valid = closure_free_energy_pJ(
        total_fmol, buffer_fmol, volume_pL, k_mM, mu_proton_RT, mu_acid_RT, mu_base_RT,
        temperature_K, c0_mM=c0_mM, xp=xp,
    )
    stored = inner_row_energy_pJ(total_fmol, volume_pL, temperature_K, xp=xp) + xp.sum(
        inner_row_energy_pJ(buffer_fmol, volume_pL, temperature_K, xp=xp), axis=0
    )
    return g_star - stored, valid


def relaxation_rate(h, buffer_mM, k_mM, k_on_per_mM_s, declared, *, xp=jnp):
    """lambda = min_k k_on,k (h + b_k + K_k) (1/s) over the buffers present at the node.

    A buffer row with zero total is absent there and takes no part; a node with no buffer has
    lambda = inf (nothing to relax).
    """
    _, base = speciation(h, buffer_mM, k_mM, xp=xp)
    rates = xp.where(declared, k_on_per_mM_s * (h + base + k_mM), xp.inf)
    return xp.min(rates, axis=0)


def drive_rate(total_rate_mM_s, h, buffer_mM, k_mM, *, xp=jnp):
    """rho = ln 10 |dH/dt| / beta (1/s): how fast transport moves ln h."""
    return LN10 * xp.abs(total_rate_mM_s) / buffer_capacity(h, buffer_mM, k_mM, xp=xp)


def lag_estimate_ph(h, buffer_mM, k_mM, k_on_per_mM_s, total_rate_mM_s, declared, *, xp=jnp):
    """The closure's first-order lag behind the kinetic system (pH units), from Appendix A.2:
    (rho / lambda) (beta/ln 10 - h) / (h ln 10),
    with beta/ln 10 - h = h sum_k B_k K_k / (h + K_k)^2."""
    lam = relaxation_rate(h, buffer_mM, k_mM, k_on_per_mM_s, declared, xp=xp)
    rho = drive_rate(total_rate_mM_s, h, buffer_mM, k_mM, xp=xp)
    bound_slope = xp.sum(buffer_mM * k_mM / (h + k_mM) ** 2, axis=0)
    return (rho / lam) * bound_slope / LN10


def envelope_valid(h, buffer_mM, k_mM, k_on_per_mM_s, total_rate_mM_s, declared, *,
                   budget_ph=LAG_BUDGET_PH, xp=jnp):
    """§4.2's run-time check, state-dependent: the estimated lag within the budget, per node."""
    lag = lag_estimate_ph(h, buffer_mM, k_mM, k_on_per_mM_s, total_rate_mM_s, declared, xp=xp)
    return lag <= budget_ph


class ReadLayout(NamedTuple):
    """The read's bound values, per node of the read's node axis (cells, then outside nodes)."""

    volume_pL: object  # [node]
    k_mM: object  # [buffer]
    k_on_per_mM_s: object  # [buffer]: the closure's D175 stand-in (envelope and reference only)
    c0_mM: object  # the registry's standard_concentration_mM
    temperature_K: object


class ReadStructure(NamedTuple):
    """Static structure (P5: closed over, never a value): the rows the read uses."""

    proton_row: int
    buffer_rows: tuple
    declared: tuple  # [buffer][node] bools: the declared (node, row) pairs, the closure's mask


def evaluate(structure, cell_amounts, outside_amounts, p, *, xp=jnp):
    """The stage read: ({"h": [node], "pH": [node]}, valid[node]) on a stage's own state.

    cell_amounts [species, cell] and outside_amounts [species, outside] are the stored rows; the
    node axis is cells then outside nodes. The mask is the declared (node, row) pairs, never the
    amounts: an undeclared trace row is a free row at a fixed amount, whose charge counts in the
    inner model and which has no protonation here.
    """
    amounts = xp.concatenate((cell_amounts, outside_amounts), axis=1)
    total = amounts[structure.proton_row] / p.volume_pL
    rows = xp.asarray(structure.buffer_rows)
    buffer = xp.where(xp.asarray(structure.declared), amounts[rows] / p.volume_pL, 0.0)
    h, valid = free_proton(total, buffer, xp.asarray(p.k_mM)[:, None], xp=xp)
    return {"h": h, "pH": -xp.log10(h / PH_REFERENCE_mM)}, valid


class StageRead(NamedTuple):
    """§7.4 (g) 1's declaration, in the published form. The core's own type replaces this record
    when it lands; the fields and the evaluate signature are the published ones."""

    read_id: str
    structure: ReadStructure
    evaluate: object  # evaluate(cell_amounts, outside_amounts, p, *, xp) -> (values, valid)
    observation_columns: tuple
    free_energy_term: object  # declared_term_pJ, evaluated on every node holding the H row


def make_read(structure):
    """The stage read for one structure: evaluate closes over the structure only (P5)."""

    def bound(cell_amounts, outside_amounts, p, *, xp=jnp):
        return evaluate(structure, cell_amounts, outside_amounts, p, xp=xp)

    return StageRead(READ_ID, structure, bound, ("h", "pH"), declared_term_pJ)
