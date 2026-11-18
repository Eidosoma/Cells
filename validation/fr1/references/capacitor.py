"""A.9: a dense capacitor solve of its own.

A network of free nodes (cells, compartments, finite extracellular nodes) and held baths at fixed
potentials, joined by capacitors (membrane patches). Each free node k's row is

    sum over its patches (k, m) of C_km (phi_k - phi_m) = q_k,

with a held bath's phi given. For a cell i, its held bath b and its compartment j this is
C_pm (phi_i - phi_b) + C_b (phi_i - phi_j) = q_i and C_b (phi_j - phi_i) = q_j, so
V_b = phi_i - phi_j = -q_j/C_b and V_pm = phi_i - phi_b = (q_i + q_j)/C_pm. With q_j = 0, V_b = 0
and V_pm is the cell's alone.

The primary solve is exact in rationals; the second is NumPy's dense solve; the floor is their
difference plus half an ulp. Each patch's voltage is reported as its first node less its second,
with the capacitor energy 1/2 C V^2 (pJ when C is in pF and V in V... here J, with C in F).
"""

from __future__ import annotations

from fractions import Fraction

import numpy as np

from .exact import exact, solve_rational


def solve(free: list, held: dict, patches: list, charges: dict) -> dict:
    """Potentials of the free nodes, each patch's voltage and energy.

    ``free``: names of free nodes; ``held``: {name: phi (V)}; ``patches``: [(node_a, node_b,
    C (F))]; ``charges``: {free node: q (C)}. A free node with no path to a held bath is refused
    (its potential has no gauge).
    """
    idx = {n: i for i, n in enumerate(free)}
    n = len(free)
    A = [[Fraction(0)] * n for _ in range(n)]
    rhs = [exact(charges.get(k, 0)) for k in free]
    for a, b, C in patches:
        Cx = exact(C)
        if C <= 0:
            raise ValueError(f"patch {a}-{b} has no capacitance")
        for p, q in ((a, b), (b, a)):
            if p in idx:
                i = idx[p]
                A[i][i] += Cx
                if q in idx:
                    A[i][idx[q]] -= Cx
                elif q in held:
                    rhs[i] += Cx * exact(held[q])
                else:
                    raise ValueError(f"patch names an unknown node {q!r}")
    _check_gauge(free, held, patches)
    phi = solve_rational(A, rhs)
    Af = np.array([[float(x) for x in row] for row in A])
    phi_f = np.linalg.solve(Af, np.array([float(x) for x in rhs]))
    pot = {k: phi[idx[k]] for k in free}
    pot.update({k: exact(v) for k, v in held.items()})
    potf = {k: phi_f[idx[k]] for k in free}
    potf.update({k: float(v) for k, v in held.items()})
    out_phi = {k: float(v) for k, v in pot.items()}
    floor = {k: abs(out_phi[k] - potf[k]) + 0.5 * float(np.spacing(abs(out_phi[k])))
             for k in pot}
    V = {f"{a}|{b}": float(pot[a] - pot[b]) for a, b, _ in patches}
    U = {f"{a}|{b}": float(Fraction(1, 2) * exact(C) * (pot[a] - pot[b]) ** 2)
         for a, b, C in patches}
    return {"phi_V": out_phi, "phi_floor_V": floor, "patch_V": V, "patch_energy_J": U}


def _check_gauge(free, held, patches) -> None:
    reach = set(held)
    changed = True
    while changed:
        changed = False
        for a, b, _ in patches:
            if (a in reach) != (b in reach):
                reach |= {a, b}
                changed = True
    lost = [k for k in free if k not in reach]
    if lost:
        raise ValueError(f"nodes {lost} have no path to a held bath")


def cell_compartment(C_pm, C_b, q_cell, q_comp, phi_bath=0.0) -> dict:
    """The three-node case: V_b and V_pm by the dense solve and by A.9's closed relations."""
    r = solve(["cell", "comp"], {"bath": phi_bath},
              [("cell", "bath", C_pm), ("cell", "comp", C_b)],
              {"cell": q_cell, "comp": q_comp})
    V_b_closed = float(-exact(q_comp) / exact(C_b))
    V_pm_closed = float((exact(q_cell) + exact(q_comp)) / exact(C_pm))
    return {"V_b_V": r["patch_V"]["cell|comp"], "V_pm_V": r["patch_V"]["cell|bath"],
            "V_b_closed_V": V_b_closed, "V_pm_closed_V": V_pm_closed, "solve": r}
