"""cells.binding.rapid_binding@1: the rapid-equilibrium binding closure for several ligands on multi-form binders
(seam C; docs/CORE_SEAMS_DESIGN.md §5 and §19 as amended on 18 November 2026).

The generalisation of cells.kind.rapid_proton_buffer@1 (B4, laws/reactions/rapid_proton_buffer.py): at a node,
ligand rows L (H, Mg, Ca, ...) and binder rows B whose forms the species registry declares
(registry/species_registry.py, ``forms``). Each binder row holds its total T_B; each ligand row holds
its total equivalents T_L, the free ligand plus every bound one counted from each binder's base form
(negative counts allowed: a form below its base). Charge depends on the totals only, so the field
solve is exact as it stands. Every species here is a free ligand or a binder's form.

The equilibrium, from the one authority. With u_L = ln x_L (free ligand, mM) and each form's
stability in the mM frame, ln beta'_f = ln beta_f - (sum_L n_L,f) ln c0 (species_registry
.form_log_constants), a binder's forms are c_f = T_B p_f, p_f = exp(a_f - ln P_B), with
a_f = ln beta'_f + sum_L n_L,f u_L and P_B = sum_f e^(a_f) (the binding polynomial, taken by
log-sum-exp). The conservation residual is g_L = x_L + sum_B T_B <n_L>_B - T_L.

The solve (free_ligands), at every stage, with no loop count that depends on data:
- one ligand on binders of one one-step form each (B4's case): B4's free_proton, with each
  binder's K from species_registry.one_step_dissociation_constant_mM, bit for bit with B4;
- otherwise: Newton on the strictly convex dual Phi(u) = sum_L (e^u_L - T_L u_L) + sum_B T_B ln P_B.
  Its gradient is g, and its Hessian H = diag(x) + sum_B T_B Cov_B(n) is positive definite. A fixed
  number of iterations each take the step d = -H^-1 g (an unrolled Cholesky solve of the static
  L x L system), capped at STEP_CAP in ln units. Armijo backtracking on each connected ligand set's
  own Phi runs over a fixed ladder of halvings, and the full step is taken once max |d| <= FULL_STEP.
  A ligand the node's binders do not bind is not held there and is left at ln T_L.
- converged: |g_L| <= RESIDUAL_RTOL A_L at every held ligand, with A_L = x_L + sum_B T_B
  <|n_L|>_B the residual's own scale (CORE_SEAMS §19 as amended: identical to RESIDUAL_RTOL T_L
  wherever every count is >= 0); every input finite and every binder total nonnegative. Otherwise
  the read is invalid and the step is refused, as B4's is.
- jointly valid (amendment C4, the core-seams references; given the network's margin vertices):
  t* > 0 at every node that holds a ligand. t* is the largest amount every free ligand can keep,
  t* = min over the ligand simplex of lambda.T - sum_B T_B min_f lambda.n_f. The per-ligand
  floors are its values at the simplex's corners, necessary but not sufficient once counts have
  both signs. The function is linear on each cell of an arrangement set by the counts alone (the
  hyperplanes lambda.(n_f - n_g) = 0 of each binder's forms, and the simplex's facets), so its
  minimum lies at a vertex of that arrangement: margin_vertices enumerates them exactly on the
  host, in rationals, and joint_margin takes the minimum over them at run time. A vertex that
  weighs a ligand the node does not hold is left out.

The free energy (CORE_SEAMS §19 as amended, the booked term). In pJ, with n = c V (fmol):
E_c = RT sum_s n_s (ln c_s - 1 - ln beta'_s) over the free ligands (beta' = 1) and every form, which
is G* - sum_r T_r mu°'_r with the stored rows' standard parts in @3's 1 mM frame. Its derivatives are
RT ln of each row's free form, free ligand or free base, in mM. G* = E_c + sum_r T_r mu°'_r.
S_c = E_c - sum_r ideal_r, where ideal_r = RT T_r (ln(T_r/V) - 1) is @3's per-row term; it is
undefined where a total is <= 0, and phase 1 books it.

Its change from increments (booked_change_pJ; the @3 owner's finding under X2, CORE_SEAMS_STEP0
§9.4). At the dual's optimum, S_c = -RT [sum_L (V x_L - N_L u_L) + sum_B N_B ln P_B(u) +
sum_L N_L (ln(N_L/V) - 1)], N the rows' amounts: the binders' ideal terms cancel. Its change since
the start, every term at the change's own scale (dN the stored increments, du = u - u_s):
  - the dual's move at the new totals: sum_L (V x_L,s expm1(du_L) - N_L du_L) +
    sum_B N_B log1p(sum_f p_f,s expm1(n_f.du));
  - the totals' move at the start's optimum: -sum_L dN_L u_L,s + sum_B dN_B ln P_B,s;
  - the ligands' ideal terms in @3's stable form: dN (ln(N_s/V) - 1) + N log1p(dN/N_s).
The dual is stationary at its optimum, so the solves' errors at either end, and the solve's own
rounding of its totals, enter only at second order. The difference of two bulk values would
carry their rounding instead (2 to 3 units in the last place of S_c, about 1e-12 pJ at 3,583 pJ),
far above the change X2 counts. The volume is the node's declared one, held constant.

The envelope (lag_first_order): the closure's first-order lag behind the kinetic binding network,
per ligand. The unit steps f + L <=> g (g = f + e_L, through declared forms) carry k_on per binding
and the one-way fluxes F = k_on x_L c_f at the speciation. The linearised network is
Lap = S diag(F) S^T over the species. Under a drive d (a ligand row's moves enter its free ligand,
a binder row's its base form), the lag y = delta ln c solves Lap y = d - dc*/dt with
M diag(c) y = 0, where M is the conservation matrix. It reduces to B4's estimate for one two-form
buffer.

Pure functions in the xp style of laws/: no state, no layout objects beyond arrays, no clipping.
Arrays put the ligand, binder or form axes first and the node axes last.
"""

import math

import numpy as np

from cells.laws.electrochemistry import R
from cells.laws.reactions import rapid_proton_buffer as b4
from cells.modules import BindingLaw, Citation

READ_ID = "cells.binding.rapid_binding@1"
RESIDUAL_RTOL = 1e-13  # |g_L| / A_L at the returned root; above it the read fails.
NEWTON_STEPS = 48  # Fixed: 2.5 x the worst first convergence (19) over 2471 swept states.
LINE_STEPS = 10  # Armijo halvings evaluated at every iteration.
STEP_CAP = 4.0  # The largest change of any ln x_L in one iteration.
FULL_STEP = 0.25  # max |d| (ln units) at or below which the full Newton step is taken.
ARMIJO = 1e-4
TINY_mM = 1e-300  # The start's floor for a free ligand, mM.
LAG_BUDGET_PX = b4.LAG_BUDGET_PH  # 1e-3 in log10 units of every free ligand, B4's budget.
LN10 = math.log(10.0)


def _jax_loop(xp):
    if xp is np:
        return None
    import jax

    return jax.lax.fori_loop


def _forms(u, log_beta, counts, present, *, xp):
    """(a [B, F, ...], ln P [B, ...], p [B, F, ...]): each form's log weight, the binding
    polynomial and the form fractions at u [L, ...]."""
    shape = (1,) * (u.ndim - 1)
    a = log_beta.reshape(log_beta.shape + shape) + xp.einsum("bfl,l...->bf...", counts, u)
    mask = present.reshape(present.shape + shape)
    a = xp.where(mask, a, -xp.inf)
    top = xp.max(a, axis=1)  # The base is always present, so finite.
    log_p = top + xp.log(xp.sum(xp.exp(a - top[:, None]), axis=1))
    p = xp.where(mask, xp.exp(a - log_p[:, None]), 0.0)
    return a, log_p, p


def _moments(p, counts, *, xp):
    """(<n> [B, L, ...], <|n|> [B, L, ...], Cov [B, L, L, ...]) of each binder's form fractions."""
    mean = xp.einsum("bf...,bfl->bl...", p, counts)
    absolute = xp.einsum("bf...,bfl->bl...", p, xp.abs(counts))
    second = xp.einsum("bf...,bfl,bfm->blm...", p, counts, counts)
    cov = second - mean[:, :, None] * mean[:, None, :]
    return mean, absolute, cov


def residual(u, total_ligand, total_binder, log_beta, counts, present, held, *, xp):
    """(g [L, ...], A [L, ...]): the conservation residual and its scale at u, in mM, held
    ligands only (0 elsewhere). total_binder [B, ...] is 0 where a binder is not held."""
    x = xp.exp(u)
    _, _, p = _forms(u, log_beta, counts, present, xp=xp)
    mean, absolute, _ = _moments(p, counts, xp=xp)
    bound = xp.einsum("b...,bl...->l...", total_binder, mean)
    scale = x + xp.einsum("b...,bl...->l...", total_binder, absolute)
    return xp.where(held, x + bound - total_ligand, 0.0), xp.where(held, scale, 0.0)


def _hessian(u, total_binder, log_beta, counts, present, held, *, xp):
    x = xp.exp(u)
    _, _, p = _forms(u, log_beta, counts, present, xp=xp)
    _, _, cov = _moments(p, counts, xp=xp)
    hess = xp.einsum("b...,blm...->lm...", total_binder, cov)
    n = u.shape[0]
    eye = xp.eye(n).reshape((n, n) + (1,) * (u.ndim - 1))
    both = held[:, None] & held[None, :]
    # Unheld ligands take the identity: their step is zero.
    return xp.where(both, hess + eye * x[:, None], eye)


def _spd_solve(hess, rhs, *, xp):
    """hess^-1 rhs for a static n x n symmetric positive definite hess [n, n, ...], unrolled
    (Cholesky, no pivoting: a block-diagonal system solves blockwise, exactly as its blocks)."""
    n = rhs.shape[0]
    low = [[None] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = hess[i, j]
            for k in range(j):
                s = s - low[i][k] * low[j][k]
            low[i][j] = xp.sqrt(s) if i == j else s / low[j][j]
    y = []
    for i in range(n):
        s = rhs[i]
        for k in range(i):
            s = s - low[i][k] * y[k]
        y.append(s / low[i][i])
    out = [None] * n
    for i in reversed(range(n)):
        s = y[i]
        for k in range(i + 1, n):
            s = s - low[k][i] * out[k]
        out[i] = s / low[i][i]
    return xp.stack(out)


def _phi(u, total_ligand, total_binder, log_beta, counts, present, held, comp_l, comp_b, *, xp):
    """Phi per connected ligand set [C, ...]: sum over its held ligands of e^u - T u, plus
    sum over its binders of T_B ln P_B."""
    _, log_p, _ = _forms(u, log_beta, counts, present, xp=xp)
    ligand = xp.where(held, xp.exp(u) - total_ligand * u, 0.0)
    binder = total_binder * log_p
    return xp.einsum("cl...,l...->c...", comp_l, ligand) + xp.einsum(
        "cb...,b...->c...", comp_b, binder
    )


def admissible_floor(total_binder, counts, present, *, xp):
    """sum_B T_B min_f n_L,f [L, ...] (mM): a ligand total at or below it has no speciation (for
    one ligand exactly; with several ligands and mixed-sign counts only necessarily, CORE_SEAMS §19
    as amended: the joint condition is the solve's own validity)."""
    lowest = xp.min(xp.where(present[:, :, None], counts, 0.0), axis=1)  # [B, L]; the base's 0.
    return xp.einsum("b...,bl->l...", total_binder, lowest)


def newton_ligands(total_ligand, total_binder, log_beta, counts, present, held, comp_l, comp_b,
                   *, steps=NEWTON_STEPS, xp):
    """ln x [L, ...] after `steps` iterations of the dual Newton (module docstring), from the
    start ln(max(T_L - floor_L, TINY)) at held ligands and ln T_L elsewhere. Every argument is
    already masked: total_binder is 0 where a binder is not held, held [L, ...] marks the held
    ligands, comp_l [C, L, ...] and comp_b [C, B, ...] are the connected sets' one-hots."""
    floor = admissible_floor(total_binder, counts, present, xp=xp)
    room = xp.where(held, total_ligand - floor, total_ligand)
    u0 = xp.log(xp.maximum(room, TINY_mM))
    ladder = [0.5**k for k in range(LINE_STEPS)]
    args = (log_beta, counts, present, held)

    def step(_, u):
        g, _ = residual(u, total_ligand, total_binder, *args, xp=xp)
        d = -_spd_solve(_hessian(u, total_binder, *args, xp=xp), g, xp=xp)
        size = xp.einsum("cl...,l...->cl...", comp_l, xp.abs(d)).max(axis=1)  # [C, ...]
        cap = xp.minimum(1.0, STEP_CAP / xp.maximum(size, TINY_mM))
        phi0 = _phi(u, total_ligand, total_binder, *args, comp_l, comp_b, xp=xp)
        slope = xp.einsum("cl...,l...->c...", comp_l, g * d)
        chosen = xp.zeros_like(cap)
        found = xp.zeros(cap.shape, dtype=bool)
        for t in ladder:
            trial = cap * t
            u_t = u + xp.einsum("cl...,c...->l...", comp_l, trial) * d
            phi = _phi(u_t, total_ligand, total_binder, *args, comp_l, comp_b, xp=xp)
            ok = (phi <= phi0 + ARMIJO * trial * slope) & ~found
            chosen = xp.where(ok, trial, chosen)
            found = found | ok
        chosen = xp.where(size <= FULL_STEP, 1.0, chosen)
        return u + xp.einsum("cl...,c...->l...", comp_l, chosen) * d

    loop = _jax_loop(xp)
    if loop is None:
        u = u0
        for i in range(steps):
            u = step(i, u)
        return u
    return loop(0, steps, step, u0)


def free_ligands(total_ligand, total_binder, log_beta, counts, present, held, comp_l, comp_b,
                 k_mM=None, *, path="newton", steps=NEWTON_STEPS, vertices=None, xp):
    """(ln x [L, ...] in ln mM, valid [...]): the closure's free ligands from the totals (mM).

    path "b4" (one ligand; every binder one one-step form, k_mM [B] its K): B4's free_proton, bit
    for bit; path "newton": newton_ligands. valid where every input is finite, every binder total
    is nonnegative, and |g_L| <= RESIDUAL_RTOL A_L at every held ligand; with the network's margin
    `vertices` (path "newton"), also where the joint margin t* > 0 (amendment C4)."""
    finite = (
        xp.all(xp.isfinite(total_ligand), axis=0)
        & xp.all(xp.isfinite(total_binder) & (total_binder >= 0), axis=0)
    )
    safe_l = xp.where(xp.isfinite(total_ligand), total_ligand, 1.0)
    safe_b = xp.where(xp.isfinite(total_binder) & (total_binder >= 0), total_binder, 0.0)
    if path == "b4":
        k = k_mM.reshape(k_mM.shape + (1,) * (safe_b.ndim - 1))
        h, ok = b4.free_proton(safe_l[0], safe_b, k, xp=xp)
        u = xp.where(held, xp.log(h)[None], xp.log(xp.maximum(safe_l, TINY_mM)))
        return u, finite & xp.where(held[0], ok, True)
    u = newton_ligands(safe_l, safe_b, log_beta, counts, present, held, comp_l, comp_b,
                       steps=steps, xp=xp)
    g, scale = residual(u, safe_l, safe_b, log_beta, counts, present, held, xp=xp)
    good = xp.isfinite(u) & (xp.abs(g) <= RESIDUAL_RTOL * scale)
    converged = xp.all(xp.where(held, good, True), axis=0)
    if vertices is None:
        return u, finite & converged
    margin = joint_margin(safe_l, safe_b, counts, present, vertices, held, xp=xp)
    jointly = xp.where(xp.any(held, axis=0), margin > 0, True)
    return u, finite & converged & jointly


def joint_margin(total_ligand, total_binder, counts, present, vertices, held, *, xp):
    """t* [...] (mM): min over the margin vertices [V, L] of lambda.T - sum_B T_B min_f lambda.n_f
    (module docstring, amendment C4), leaving out each vertex that weighs a ligand not held at the
    node; +inf at a node that holds none."""
    shape = (1,) * (total_ligand.ndim - 1)
    linear = xp.einsum("vl,l...->v...", vertices, total_ligand)
    projected = xp.einsum("vl,bfl->vbf", vertices, counts)
    lowest = xp.min(xp.where(present[None], projected, xp.inf), axis=2)  # [V, B]; the base's 0.
    bound = xp.einsum("vb,b...->v...", lowest, total_binder)
    support = (vertices > 0).reshape(vertices.shape + shape)  # [V, L, ...]
    allowed = xp.all(~support | held[None], axis=1)  # [V, ...]
    return xp.min(xp.where(allowed, linear - bound, xp.inf), axis=0)


MARGIN_VERTEX_CAP = 4096  # The most margin vertices a closure may have (the parse refuses more).
MARGIN_COMBINATION_CAP = 200_000  # The most hyperplane combinations the host may enumerate.


def margin_vertices(counts, present, *, vertex_cap=MARGIN_VERTEX_CAP,
                    combination_cap=MARGIN_COMBINATION_CAP):
    """(exact, floats [V, L]): the vertices, inside the ligand simplex, of the arrangement on which
    the joint margin is linear (module docstring), host side and exact in rationals. The hyperplanes
    are lambda.(n_f - n_g) = 0 for every two present forms of a binder, and the simplex's facets
    lambda_L = 0. A vertex is where L - 1 of them meet on the simplex. ValueError past either cap,
    since the enumeration grows fast with the ligands."""
    from fractions import Fraction
    from itertools import combinations

    nb, nf, nl = counts.shape
    if nl == 1:
        exact = [(Fraction(1),)]
        return exact, np.ones((1, 1))
    planes = set()
    for b in range(nb):
        forms = [tuple(int(v) for v in counts[b, f]) for f in range(nf) if present[b, f]]
        for f, g in combinations(forms, 2):
            normal = tuple(a - c for a, c in zip(f, g, strict=True))
            if any(normal):
                scale = math.gcd(*normal)
                lead = next(v for v in normal if v)
                sign = 1 if lead > 0 else -1
                planes.add(tuple(sign * v // scale for v in normal))
    planes |= {tuple(int(i == j) for j in range(nl)) for i in range(nl)}
    planes = sorted(planes)
    if math.comb(len(planes), nl - 1) > combination_cap:
        raise ValueError(
            f"the joint margin's arrangement has {len(planes)} hyperplanes in {nl} ligands: "
            f"{math.comb(len(planes), nl - 1)} combinations, past the cap of {combination_cap}"
        )
    found = set()
    for chosen in combinations(planes, nl - 1):
        rows = [[Fraction(v) for v in plane] + [Fraction(0)] for plane in chosen]
        rows.append([Fraction(1)] * nl + [Fraction(1)])
        solution = _solve_exact(rows, nl)
        if solution is not None and all(v >= 0 for v in solution):
            found.add(solution)
            if len(found) > vertex_cap:
                raise ValueError(
                    f"the joint margin has more than {vertex_cap} vertices in {nl} ligands"
                )
    exact = sorted(found)
    return exact, np.array([[float(v) for v in vertex] for vertex in exact])


def _solve_exact(rows, n):
    """The unique solution of the augmented system `rows` [n x (n + 1)], in rationals, or None."""
    a = [row[:] for row in rows]
    for col in range(n):
        pivot = next((r for r in range(col, n) if a[r][col] != 0), None)
        if pivot is None:
            return None
        a[col], a[pivot] = a[pivot], a[col]
        for r in range(n):
            if r != col and a[r][col] != 0:
                factor = a[r][col] / a[col][col]
                a[r] = [x - factor * y for x, y in zip(a[r], a[col], strict=True)]
    return tuple(a[i][n] / a[i][i] for i in range(n))


def speciation(u, total_binder, log_beta, counts, present, *, xp):
    """(x [L, ...], forms [B, F, ...]) in mM at ln x u: the free ligands and every form's
    concentration (the base first; 0 where a form is absent or a binder is not held)."""
    _, _, p = _forms(u, log_beta, counts, present, xp=xp)
    return xp.exp(u), total_binder[:, None] * p


def free_amounts(ligand_fmol, binder_fmol, volume_pL, log_beta, counts, present, held, comp_l,
                 comp_b, k_mM=None, *, path="newton", steps=NEWTON_STEPS, xp):
    """(free ligands [L, ...], free base forms [B, ...], valid [...]) in fmol: the closure's free
    forms after equilibration, from stored totals in fmol at each node's volume (pL), at whatever
    totals it is given. P1's predictor reads it at the predicted totals (CORE_SEAMS §17, and §19 as
    amended: the general layout only). Rows a node's closure does not hold are meaningless here
    and are left to the caller; binder_fmol must be 0 where a binder is not held."""
    total_ligand, total_binder = ligand_fmol / volume_pL, binder_fmol / volume_pL
    u, valid = free_ligands(total_ligand, total_binder, log_beta, counts, present, held, comp_l,
                            comp_b, k_mM, path=path, steps=steps, xp=xp)
    x, forms = speciation(u, total_binder, log_beta, counts, present, xp=xp)
    return x * volume_pL, forms[:, 0] * volume_pL, valid


def forms_from_free(u, base_mM, log_beta, counts, present, *, xp):
    """Every form's concentration [B, F, ...] from the free ligands and each binder's free base
    form (the read's rows): c_f = c_base exp(ln beta'_f + n_f . u). No solve."""
    shape = (1,) * (u.ndim - 1)
    a = log_beta.reshape(log_beta.shape + shape) + xp.einsum("bfl,l...->bf...", counts, u)
    return xp.where(present.reshape(present.shape + shape), base_mM[:, None] * xp.exp(a), 0.0)


def _entropy_terms(c_mM, log_beta, volume_pL, *, xp):
    """sum of n (ln c - 1 - ln beta') over species, with 0 ln 0 -> 0 (fmol, in units of RT)."""
    safe = xp.where(c_mM > 0, c_mM, 1.0)
    return xp.where(c_mM > 0, c_mM * volume_pL * (xp.log(safe) - 1.0 - log_beta), 0.0)


def booked_terms_pJ(u, total_ligand, total_binder, log_beta, counts, present, held,
                    mu0p_ligand_RT, mu0p_binder_RT, volume_pL, temperature_K, *, xp):
    """(E_c, G*, S_c, S_c defined) per node, pJ (module docstring), at ln x u. total_binder is 0
    where a binder is not held, and only held ligands count. mu0p_*_RT are the rows' standard
    parts in @3's 1 mM frame, mu°/RT - ln c0. S_c is defined where every held total is > 0."""
    rt = 1e-3 * R * temperature_K
    x, forms = speciation(u, total_binder, log_beta, counts, present, xp=xp)
    shape = (1,) * (u.ndim - 1)
    ligands = _entropy_terms(xp.where(held, x, 0.0), 0.0, volume_pL, xp=xp)
    beta = log_beta.reshape(log_beta.shape + shape)
    binders = _entropy_terms(forms, beta, volume_pL, xp=xp)
    e_c = rt * (xp.sum(ligands, axis=0) + xp.sum(binders, axis=(0, 1)))
    lig_t = xp.where(held, total_ligand, 0.0) * volume_pL
    bind_t = total_binder * volume_pL
    standard = xp.einsum("l,l...->...", mu0p_ligand_RT, lig_t) + xp.einsum(
        "b,b...->...", mu0p_binder_RT, bind_t
    )
    rows = xp.concatenate((lig_t, bind_t), axis=0)
    counted = xp.concatenate((held, total_binder > 0), axis=0)
    positive = xp.where(counted, rows > 0, True)
    safe = xp.where(counted & (rows > 0), rows, 1.0)
    ideal = xp.where(counted & (rows > 0), safe * (xp.log(safe / volume_pL) - 1.0), 0.0)
    return e_c, e_c + rt * standard, e_c - rt * xp.sum(ideal, axis=0), xp.all(positive, axis=0)


def booked_change_pJ(u, u_start, ligand_start, ligand_increment, binder_start, binder_increment,
                     log_beta, counts, present, held, member, volume_pL, temperature_K, *, xp):
    """(S_c now less S_c at the start, defined) per node, pJ: the change formed from increments
    (module docstring), every term at the change's scale. u and u_start [L, ...] are the free
    ligands' ln x (mM) now and at the start; ligand_* [L, ...] and binder_* [B, ...] the rows'
    amounts at the start and their stored increments (fmol); held [L, ...] and member [B, ...] the
    closure's rows at each node. Defined where every held ligand's amount is > 0 at both ends, as
    S_c is."""
    rt = 1e-3 * R * temperature_K
    d = xp.where(held, u - u_start, 0.0)
    n_s = xp.where(held, ligand_start, 1.0)
    dn = xp.where(held, ligand_increment, 0.0)
    n = n_s + dn
    b_s = xp.where(member, binder_start, 0.0)
    db = xp.where(member, binder_increment, 0.0)
    # A ligand a node does not hold may sit at ln 0 there, so a binder that is not the node's can
    # carry NaN forms: every binder term is masked to the node's own binders.
    _, log_p, p = _forms(u_start, log_beta, counts, present, xp=xp)
    shift = xp.einsum("bfl,l...->bf...", counts, d)
    moved = xp.log1p(xp.sum(xp.where(p > 0, p * xp.expm1(shift), 0.0), axis=1))
    free = volume_pL * xp.exp(u_start)
    dual = xp.sum(xp.where(held, free * xp.expm1(d) - n * d, 0.0), axis=0)
    dual = dual + xp.sum(xp.where(member, (b_s + db) * moved, 0.0), axis=0)
    totals = xp.sum(xp.where(held, -dn * u_start, 0.0), axis=0)
    totals = totals + xp.sum(xp.where(member, db * log_p, 0.0), axis=0)
    safe = xp.where(held & (n_s > 0), n_s, 1.0)
    ratio = xp.where(held, dn / safe, 0.0)
    ideal = xp.where(held, dn * (xp.log(safe / volume_pL) - 1.0) + n * xp.log1p(ratio), 0.0)
    positive = xp.where(held, (n_s > 0) & (n > 0), True)
    return -rt * (dual + totals + xp.sum(ideal, axis=0)), xp.all(positive, axis=0)


def free_log_sensitivity_block(u, base_free, log_beta, counts, present, held, member, volume_pL,
                               rows, n_species, *, xp):
    """(D [S, S, ...] in 1/fmol, held [S, ...]) at a stage's read: D[i, k] = d ln c_i / d n_k,
    c_i the free form the read writes into species row i (a free ligand, or a binder's free base
    form) and n_k the stored total of row k, the other totals at the node held fixed (the kinds
    owner's K3b, its material term's step bound). The implicit-function derivative of the
    closure's mass balances at the read's free values, per node, in the totals' concentrations:
      - d u / d T_L = H^-1 and d u / d T_B = -H^-1 <n>_B, H the dual's Hessian diag(x) +
        sum_B T_B Cov_B(n) (one block per connected ligand set);
      - ln c_base,B = ln T_B - ln P_B(u), so d ln c_base,B / d T_L = -<n>_B.H^-1 e_L and
        d ln c_base,B / d T_B' = delta_BB' / T_B + <n>_B.H^-1 <n>_B';
      - each divided by the node's volume, for amounts.
    u [L, ...] is ln x (mM) at the held ligands, base_free [B, ...] the free base forms (mM) at the
    held binders (member), whose totals are base_free P_B(u); rows [L + B] the closure's species
    indices, ligands then binders. D is exactly 0 wherever row i or row k is not a closure row at
    the node; held marks the closure's rows on the species axis. The domain is a valid read's: a
    finite u at every held ligand. An empty binder (T_B = 0 at a member node) keeps its row and
    column, whose cross terms are finite, but its own 1/T_B, unbounded there, is left out, as a
    kind's material term leaves out an empty row's own 1/n; D stays finite."""
    n_l = u.shape[0]
    u = xp.where(held, u, 0.0)
    _, log_p, p = _forms(u, log_beta, counts, present, xp=xp)
    total_b = xp.where(member, base_free * xp.exp(log_p), 0.0)
    hess = _hessian(u, total_b, log_beta, counts, present, held, xp=xp)
    eye = xp.eye(n_l).reshape((n_l, n_l) + (1,) * (u.ndim - 1))
    inverse = _spd_solve(hess, eye * xp.ones_like(hess), xp=xp)  # One factorization, n columns.
    keep = held[:, None] & held[None, :]
    inverse = xp.where(keep, inverse, 0.0)
    mean, _, _ = _moments(p, counts, xp=xp)  # [B, L, ...]
    mean = xp.where(member[:, None] & held[None, :], mean, 0.0)
    a = xp.einsum("lm...,bm...->lb...", inverse, mean)  # H^-1 <n>_B
    filled = member & (total_b > 0)
    diag = xp.where(filled, 1.0 / xp.where(filled, total_b, 1.0), 0.0)
    n_b = base_free.shape[0]
    beye = xp.eye(n_b).reshape((n_b, n_b) + (1,) * (u.ndim - 1))
    bb = xp.einsum("bl...,lc...->bc...", mean, a) + beye * diag[:, None]
    top = xp.concatenate((inverse, -a), axis=1)
    bottom = xp.concatenate((-xp.einsum("lb...->bl...", a), bb), axis=1)
    block = xp.concatenate((top, bottom), axis=0) / volume_pL  # [L + B, L + B, ...], 1/fmol
    hold = xp.concatenate((held, member), axis=0)
    block = xp.where(hold[:, None] & hold[None, :], block, 0.0)
    onehot = (rows[:, None] == xp.arange(n_species)[None, :]).astype(float)  # [L + B, S]
    d = xp.einsum("is,ij...,jt->st...", onehot, block, onehot)
    return d, xp.einsum("is,i...->s...", onehot, hold.astype(float)) > 0


def lag_first_order(u, forms, total_binder, drive_ligand, drive_binder, log_beta, counts, present,
                    held, step_matrix, step_from, step_ligand, step_kon, conservation, *, xp):
    """delta ln x_L [L, ...]: the closure's first-order lag behind the binding network (module
    docstring), at ln x u and the forms [B, F, ...] (mM), under drives [L, ...] and [B, ...]
    (mM/s: a ligand row's change enters its free ligand, a binder row's its base form).

    step_matrix [n_species, n_steps]: each unit step's stoichiometry over the species (the free
    ligands, then every binder's forms, binder-major); step_from [n_steps] the reacting form's
    species index, step_ligand [n_steps] its ligand's, step_kon [n_steps] (1/(mM s), 0 for a
    padded step); conservation [n_rows, n_species] (the ligand totals, then the binder totals)."""
    lig, nb, nf = u.shape[0], forms.shape[0], forms.shape[1]
    tail = u.shape[1:]
    x = xp.exp(u)
    conc = xp.concatenate((xp.where(held, x, 0.0), forms.reshape((nb * nf,) + tail)), axis=0)
    live = conc > 0
    flux = step_kon.reshape((-1,) + (1,) * len(tail)) * conc[step_ligand] * conc[step_from]
    lap = xp.einsum("sr,r...,tr->st...", step_matrix, flux, step_matrix)
    # The closure's drift under the drive: du/dt = H^-1 (dT_L - sum_B <n_L>_B dT_B).
    _, _, p = _forms(u, log_beta, counts, present, xp=xp)
    mean, _, _ = _moments(p, counts, xp=xp)
    drive_free = xp.where(
        held, drive_ligand - xp.einsum("bl...,b...->l...", mean, drive_binder), 0.0
    )
    hess = _hessian(u, total_binder, log_beta, counts, present, held, xp=xp)
    du = _spd_solve(hess, drive_free, xp=xp)
    positive = total_binder > 0
    rel = xp.where(positive, drive_binder / xp.where(positive, total_binder, 1.0), 0.0)
    shift = xp.einsum("bfl,l...->bf...", counts, du) - xp.einsum("bl...,l...->b...", mean, du)[:, None]
    dform = forms * (shift + rel[:, None])
    drift = xp.concatenate((x * du, dform.reshape((nb * nf,) + tail)), axis=0)
    base = xp.concatenate((drive_binder[:, None], xp.zeros((nb, nf - 1) + tail)), axis=1)
    drive = xp.concatenate(
        (xp.where(held, drive_ligand, 0.0), base.reshape((nb * nf,) + tail)), axis=0
    )
    rhs = xp.where(live, drive - drift, 0.0)
    # Lap y = rhs with M diag(c) y = 0: y0 = (Lap + alpha M^T M)^-1 rhs, then y0 + M^T lambda.
    rows = conservation.shape[0]
    n_s = conc.shape[0]
    alpha = xp.sum(xp.where(live, xp.einsum("ss...->s...", lap), 0.0), axis=0) / xp.maximum(
        xp.sum(live, axis=0), 1
    )
    mtm = xp.einsum("rs,rt->st", conservation, conservation)
    eye = xp.eye(n_s).reshape((n_s, n_s) + (1,) * len(tail))
    both = live[:, None] & live[None, :]
    system = xp.where(both, lap + alpha * mtm.reshape(mtm.shape + (1,) * len(tail)), eye)
    y0 = _dense_solve(system, rhs, xp=xp)
    weighted = conservation.reshape(conservation.shape + (1,) * len(tail)) * conc[None]
    gram = xp.einsum("rs...,ts->rt...", weighted, conservation)
    used = xp.any(weighted != 0, axis=1)
    eye_r = xp.eye(rows).reshape((rows, rows) + (1,) * len(tail))
    gram = xp.where(used[:, None] & used[None, :], gram, eye_r)
    lam = _dense_solve(gram, -xp.einsum("rs...,s...->r...", weighted, y0), xp=xp)
    y = y0 + xp.einsum("rs,r...->s...", conservation, lam)
    return xp.where(held, y[:lig], 0.0)


def _dense_solve(system, rhs, *, xp):
    """system^-1 rhs for [n, n, ...] and [n, ...], node axes last (a batched library solve)."""
    n = rhs.shape[0]
    tail = rhs.shape[1:]
    a = xp.moveaxis(system.reshape((n, n, -1)), -1, 0)
    b = xp.moveaxis(rhs.reshape((n, -1)), -1, 0)[..., None]
    return xp.moveaxis(xp.linalg.solve(a, b)[..., 0], 0, -1).reshape((n,) + tail)


# ---------------------------------------------------------------------------- host-side layout


def network(ligands, binders):
    """The static arrays of one closure (host side, NumPy), from its ligand IDs in layout order
    and its binders: ((binder ID, ((form ID, ((ligand, n), ...), ln beta_f at c0), ...), c0_mM,
    ((ligand, k_on), ...)), ...), each binder's forms base first (counts (), ln beta 0).

    Returns {counts [B, F, L], present [B, F], log_beta [B, F] (the mM frame), step_matrix
    [n_species, n_steps], step_from, step_ligand, step_kon [n_steps], conservation [L + B,
    n_species], path, margin_vertices [V, L]}, with the species the free ligands then every form,
    binder-major, and the unit steps every pair of declared forms that differ by one more of a
    single ligand. path is "b4" for one ligand on binders of one one-step form each, else
    "newton". margin_vertices are the joint margin's (margin_vertices; ValueError past its caps)."""
    lig = {name: k for k, name in enumerate(ligands)}
    width = max(len(forms) for _, forms, _, _ in binders)
    nb, nl = len(binders), len(ligands)
    counts = np.zeros((nb, width, nl))
    present = np.zeros((nb, width), dtype=bool)
    log_beta = np.zeros((nb, width))
    froms, tos, step_lig, kons = [], [], [], []
    for b, (_, forms, c0, kon) in enumerate(binders):
        rates = dict(kon)
        for f, (_, pairs, beta) in enumerate(forms):
            present[b, f] = True
            for ligand, n in pairs:
                counts[b, f, lig[ligand]] = n
            log_beta[b, f] = beta - sum(n for _, n in pairs) * math.log(c0)
        for f in range(len(forms)):
            for g in range(len(forms)):
                step = counts[b, g] - counts[b, f]
                if np.count_nonzero(step) == 1 and step.max() == 1:
                    ligand = int(np.argmax(step))
                    froms.append(nl + b * width + f)
                    tos.append(nl + b * width + g)
                    step_lig.append(ligand)
                    kons.append(rates[ligands[ligand]])
    n_species = nl + nb * width
    matrix = np.zeros((n_species, len(froms)))
    for r, (f, g, ligand) in enumerate(zip(froms, tos, step_lig, strict=True)):
        matrix[ligand, r] -= 1.0
        matrix[f, r] -= 1.0
        matrix[g, r] += 1.0
    conservation = np.zeros((nl + nb, n_species))
    conservation[np.arange(nl), np.arange(nl)] = 1.0
    for b in range(nb):
        for f in range(width):
            if present[b, f]:
                conservation[:nl, nl + b * width + f] = counts[b, f]
                conservation[nl + b, nl + b * width + f] = 1.0
    one_step = nl == 1 and all(
        len(forms) == 2 and tuple(forms[1][1]) == ((ligands[0], 1),) for _, forms, _, _ in binders
    )
    return dict(
        counts=counts, present=present, log_beta=log_beta, step_matrix=matrix,
        step_from=np.asarray(froms, dtype=int), step_ligand=np.asarray(step_lig, dtype=int),
        step_kon=np.asarray(kons, dtype=float), conservation=conservation,
        path="b4" if one_step else "newton",
        margin_vertices=margin_vertices(counts, present)[1],
    )  # fmt: skip


def connected_sets(member, counts):
    """(held [L, N], comp_l [L, L, N], comp_b [L, B, N]) per node, host side: the ligands each
    node's member binders bind, and the connected ligand sets (ligands sharing a binder at the
    node), each a one-hot over ligands and over binders, at most L sets per node."""
    nb, _, nl = counts.shape
    binds = np.any(counts != 0, axis=1)  # [B, L]
    nodes = member.shape[1]
    held = np.zeros((nl, nodes), dtype=bool)
    comp_l = np.zeros((nl, nl, nodes))
    comp_b = np.zeros((nl, nb, nodes))
    for n in range(nodes):
        at = [b for b in range(nb) if member[b, n]]
        parent = list(range(nl))

        def root(k):
            while parent[k] != k:
                k = parent[k]
            return k

        for b in at:
            ligs = np.flatnonzero(binds[b])
            for other in ligs[1:]:
                parent[root(other)] = root(ligs[0])
            held[ligs, n] = True
        sets = sorted({root(k) for k in range(nl) if held[k, n]})
        for c, top in enumerate(sets):
            for k in range(nl):
                if held[k, n] and root(k) == top:
                    comp_l[c, k, n] = 1.0
            for b in at:
                if root(int(np.flatnonzero(binds[b])[0])) == top:
                    comp_b[c, b, n] = 1.0
    return held, comp_l, comp_b


# The law's declaration (CORE_SEAMS §8.2 and §19 as amended): the general closure, run by the
# closure's kind and registered by the law registry's loader from @3's law homes. Its general
# fields beyond version 1's (forms, free_energy, envelope and free_amounts) join when the law
# template's hand-off lands on main (the F owner's e74d3599).
def onto_species(rows, hold, values, n_species, *, xp):
    """(mask [species, node], value [species, node]): the closure's rows (ligand rows, then binder
    rows; `rows` their species indices) placed on the species axis, a host's stage read. mask is
    true where a row is held at the node and value is its value there, 0 elsewhere. The rows are
    distinct species, so each output takes at most one term, an exact placement with no rounding.
    It lives in the kernel, as version 1's arithmetic does, so the kind keeps A7's sum rule."""
    onehot = (rows[:, None] == xp.arange(n_species)[None, :]).astype(float)
    mask = xp.einsum("ks,kn->sn", onehot, hold.astype(float)) > 0
    value = xp.einsum("ks,kn->sn", onehot, xp.where(hold, values, 0.0))
    return mask, value


def binder_totals(forms, *, xp):
    """Each binder's total [B, ...] (mM): the sum of its forms' concentrations [B, F, ...]."""
    return xp.sum(forms, axis=1)


def free_energy_pJ(u, total_ligand, total_binder, log_beta, counts, present, held,
                   mu0p_ligand_RT, mu0p_binder_RT, volume_pL, temperature_K, *, xp):
    """G* per node, pJ: the closure's free-energy term at ln x u (booked_terms_pJ's second part;
    the law's free_energy). Defined wherever the solve is, whatever the totals' signs."""
    return booked_terms_pJ(u, total_ligand, total_binder, log_beta, counts, present, held,
                           mu0p_ligand_RT, mu0p_binder_RT, volume_pL, temperature_K, xp=xp)[1]


# The general form's declarations (CORE_SEAMS §19 as amended; seam F's BindingLaw fields): the
# binders' forms are the species registry's, and its kernels are G*, the envelope's first-order
# lag and P1's free amounts.
LAW = BindingLaw(
    READ_ID,
    ("ligand",),
    free_ligands,
    forms="registry",
    free_energy=free_energy_pJ,
    envelope=lag_first_order,
    free_amounts=free_amounts,
    host="cells.kind.rapid_proton_buffer@1",
    provenance="cited",
    source=Citation(
        "the rapid-equilibrium binding closure: B4's rapid-buffer closure generalised to several "
        "ligands on multi-form binders, by Newton on the speciation's convex dual, with the "
        "first-order lag of its unit-step network as its envelope",
        "docs/CORE_SEAMS_DESIGN.md §5 and §19 (as amended, 18 November 2026); "
        "docs/COMPARTMENT_PH_TRANSFER_DESIGN.md §4",
        "no numbers taken: the law is a form, its constants the species registry's",
    ),
    test="tests/unit/test_rapid_binding_kernel.py::test_the_solve_meets_the_references_at_every_registered_state",
)
