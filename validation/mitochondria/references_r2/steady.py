"""Steady states by Newton in ln variables, with the conserved inventories imposed.

At a steady state every physical row's rate is zero. Seven quantities are conserved by the
dynamics: the NAD, Q and cytochrome c totals, the matrix adenylates, the matrix Mg2+ total (held
fixed here), the matrix charge inventory I_N = C_IM dPsi + W_x sum_N z c, and the matrix-plus-IMS
row charge I_NP = W_x sum_N z c + W_i sum_P z c, which zero net outer-membrane current (G5)
conserves. So six rate equations are redundant; each is replaced by its inventory, and the
outer one, I_NP, either by a held value or by a condition on the outer membrane's potential.

The unknowns are ln c for every concentration and dPsi itself; the residuals are d ln c/dt (s-1)
and the inventories' conditions. The Jacobian is by forward differences; the iteration is Newton
with Deuflhard's natural monotonicity test on the step and stops one step after the step falls
below 1e-12, or at its rounding floor.

The start state (world declaration G7) is the state-4 steady state at [Pi]e = 10 mM whose matrix
charge inventory puts the state-4 steady state at [Pi]e = 0 at pH_N = 7.1418. [Pi]e = 0 is reached
as a limit: the steady state is continued down in [Pi]e to each declared small value, and I_N is
found there by a secant on pH_N.
"""

import math

import numpy as np
from scipy.linalg import lu_factor, lu_solve

from . import model

FIXED = ("Mg_N", "O2_node")
IX = model.IDX


def _unknowns():
    return [i for i, n in enumerate(model.PHYS) if n not in FIXED]


class NoConvergence(RuntimeError):
    pass


def solve(world, ctl, y_guess, inventory, outer=("potential", 0.0), tol=1e-12, max_iter=60,
          debug=False):
    """The steady state at ``ctl`` with matrix charge inventory ``inventory``.

    ``outer`` closes the seventh inventory: ("inventory", I_NP) holds the matrix-plus-IMS row
    charge, ("potential", mV) sets phi_IMS - phi_bath at the steady state.
    """
    unknown = _unknowns()
    base = np.array(y_guess, dtype=float)
    base[model.NPHYS:] = 0.0
    is_dpsi = np.array([model.PHYS[i] == "dpsi" for i in unknown])
    kind, value = outer

    def assemble(z):
        y = base.copy()
        for k, i in enumerate(unknown):
            y[i] = z[k] if is_dpsi[k] else math.exp(z[k])
        return y

    def residual(z):
        y = assemble(z)
        f = world.rhs(0.0, y, ctl)
        r = np.empty(len(unknown))
        for k, i in enumerate(unknown):
            name = model.PHYS[i]
            if name == "dpsi":
                r[k] = (world.charge_inventory(y) - inventory) / world.C_IM  # mV
            elif name == "NAD":
                r[k] = (y[IX["NADH"]] + y[IX["NAD"]]) / world.NAD_tot - 1.0
            elif name == "Q":
                r[k] = (y[IX["QH2"]] + y[IX["Q"]]) / world.Q_tot - 1.0
            elif name == "c3":
                r[k] = (y[IX["c2"]] + y[IX["c3"]]) / world.cytC_tot - 1.0
            elif name == "ADP_N":
                r[k] = (y[IX["ATP_N"]] + y[IX["ADP_N"]]) / world.A_tot - 1.0
            elif name == "K_P":
                if kind == "inventory":
                    r[k] = (sum(world.row_charge(y)) - value) / world.C_IM  # mV equivalent
                else:
                    v = world.evaluate(list(y), ctl)["v"]
                    r[k] = -v / world.f_mV - value  # mV
            else:
                r[k] = f[i] / y[i]
        return r

    def safe_residual(z):
        try:
            r = residual(z)
        except (OverflowError, ValueError, ZeroDivisionError):
            return None
        return r if np.all(np.isfinite(r)) else None

    z = np.array([base[i] if d else math.log(base[i])
                  for i, d in zip(unknown, is_dpsi, strict=True)])
    r = residual(z)
    last = False
    size = np.inf
    for it in range(max_iter):
        Jm = np.empty((len(z), len(z)))
        for k in range(len(z)):
            h = 1e-7 * max(1.0, abs(z[k]))
            z2 = z.copy()
            z2[k] += h
            Jm[:, k] = (residual(z2) - r) / (z2[k] - z[k])
        lu = lu_factor(Jm)
        step = lu_solve(lu, -r)
        # At most one e-fold in any ln c and 20 mV in dPsi per iteration.
        cap = max(np.max(np.abs(np.where(is_dpsi, step / 20.0, step))), 1.0)
        step = step / cap
        snorm = np.linalg.norm(step)
        lam = 1.0
        while True:
            z_new = z + lam * step
            r_new = safe_residual(z_new)
            if r_new is not None:
                simplified = np.linalg.norm(lu_solve(lu, -r_new))
                if last or simplified <= (1.0 - lam / 4.0) * snorm or snorm < 1e-9:
                    break
            if lam < 1e-4:
                raise NoConvergence("steady state: no monotone step (|step| %.3g)" % snorm)
            lam *= 0.5
        z, r = z_new, r_new
        size = float(np.max(np.abs(lam * step)))
        if debug:
            worst = int(np.argmax(np.abs(r)))
            print("  it %2d |r| %.3e lam %.3g step %.3e worst %s %.3e" % (
                it, np.linalg.norm(r), lam, size, model.PHYS[unknown[worst]], r[worst]))
        if last:
            return assemble(z), dict(iterations=it + 1, step=size,
                                     residual=float(np.max(np.abs(r))))
        if size < tol or (size < 1e-9 and simplified >= 0.5 * snorm):
            last = True  # converged, or at the rounding floor: one more step
    raise NoConvergence("steady state did not converge (step %.3g)" % size)


def continue_in_Pi(world, y, inventory, start_pi, target_pi, outer=("potential", 0.0),
                   bath="trace", **controls):
    """Follow the steady state in [Pi]e from start_pi to target_pi, halving failed steps."""
    current = start_pi
    step = 0.5 if target_pi < start_pi else -0.5  # decades per step
    solves = 0
    info = None
    while current != target_pi:
        nxt = current * 10.0 ** (-step)
        if (step > 0 and nxt <= target_pi) or (step < 0 and nxt >= target_pi):
            nxt = target_pi
        ctl = model.Controls(world, bath=bath, Pi_e=nxt, **controls)
        try:
            y_new, info = solve(world, ctl, y, inventory, outer)
        except NoConvergence:
            step /= 2.0
            if abs(step) < 1e-3:
                raise
            continue
        y, current = y_new, nxt
        solves += 1
    return y, dict(solves=solves, newton=info)


def pH_N(world, y):
    return -math.log10(world.speciate(y, remember=False)[0])


def outer_potential_mV(world, y, ctl):
    return -world.evaluate(list(y), ctl)["v"] / world.f_mV


def secant(fun, x0, x1, tol, max_iter=60):
    f0, f1 = fun(x0), fun(x1)
    for _ in range(max_iter):
        if f1 == f0:
            break
        x2 = x1 - f1 * (x1 - x0) / (f1 - f0)
        x0, f0, x1, f1 = x1, f1, x2, fun(x2)
        if abs(f1) < tol:
            break
    return x1, f1


def start_state(world, settled, target_pH, limits, rule="zero_potential_each"):
    """The anchored inventories and the start state (G7).

    ``settled``: any state-4 state at the declared [Pi]e. ``rule`` closes I_NP:
    - "zero_potential_each", the declared rule (G5's erratum, tag
      mito-mt1b-declaration-erratum-2026-11-22): the outer membrane's potential is zero at the
      anchor state and again at the start state, each IMS at its own bath's free ions;
    - "held_from_start" and "held_from_anchor": the alternatives R2 reported, recorded and not
      used (I_NP set by zero potential at one state and held at the other).
    """
    Pi_decl = world.values["Pi_tot"]
    ctl10 = model.Controls(world, bath="trace")
    I_N = world.charge_inventory(settled)
    y10, _ = solve(world, ctl10, settled, I_N, ("potential", 0.0))
    I_NP_start = sum(world.row_charge(y10))
    records = []
    y_low, pi_now = y10, Pi_decl
    for eps in limits:
        outer_low = ("inventory", I_NP_start) if rule == "held_from_start" else ("potential", 0.0)
        y_low, cinfo = continue_in_Pi(world, y_low, I_N, pi_now, eps, outer_low)
        pi_now = eps
        ctl = model.Controls(world, bath="trace", Pi_e=eps)
        for _ in range(8):  # alternate: I_N at the anchor, I_NP at the start (held_from_start)
            state = {"y": y_low}

            def miss(inv, ctl=ctl, state=state, outer_low=outer_low):
                y, _ = solve(world, ctl, state["y"], inv, outer_low)
                state["y"] = y
                return pH_N(world, y) - target_pH

            I_N, miss_pH = secant(miss, I_N, I_N + 1e-6, 1e-13)
            y_low = state["y"]
            if rule != "held_from_start":
                break
            y_up, _ = continue_in_Pi(world, y_low, I_N, eps, Pi_decl, ("potential", 0.0))
            new = sum(world.row_charge(y_up))
            done = abs(new - I_NP_start) < 1e-15
            I_NP_start = new
            outer_low = ("inventory", I_NP_start)
            if done:
                break
        records.append(dict(Pi_e=eps, I_N=I_N, I_NP=sum(world.row_charge(y_low)),
                            pH_N=pH_N(world, y_low), pH_miss=miss_pH,
                            outer_potential_mV=outer_potential_mV(world, y_low, ctl),
                            continuation=cinfo))
    if rule == "held_from_anchor":
        outer_up = ("inventory", sum(world.row_charge(y_low)))
    else:
        outer_up = ("potential", 0.0)
    start, cinfo = continue_in_Pi(world, y_low, I_N, pi_now, Pi_decl, outer_up)
    return dict(rule=rule, limits=records, I_N=I_N, I_NP=sum(world.row_charge(start)),
                start=start, outer_potential_mV=outer_potential_mV(world, start, ctl10),
                continuation=cinfo)
