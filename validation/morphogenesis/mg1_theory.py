"""MG1 analytic predictions for the regular hexagonal network (numpy/scipy only).

Reduced units: lengths sqrt(A0), energies K A0^2, moduli K A0, time eta/(K A0).

- Farhadifar et al. 2007 (Curr Biol 17:2095): E = sum K/2 (A-A0)^2 + sum Lambda l
  + sum Gamma/2 L^2, with Lambda_bar = Lambda/(K A0^{3/2}), Gamma_bar = Gamma/(K A0).
  On a regular hexagonal network each junction is shared by two cells, so the
  energy per cell is e(a) = (a-1)^2/2 + Lambda_bar p*/2 sqrt(a) + Gamma_bar p*^2 a/2,
  with p* = sqrt(8 sqrt 3) the perimeter of a unit-area regular hexagon.
- Staddon et al. 2023 (Soft Matter 19:3080, doi:10.1039/D2SM01580C), with
  E = (a-1)^2/2 + r (p-p0)^2/2, r = Gamma_bar, p0 = -Lambda_bar/(2 Gamma_bar):
  for p0 < p* the stress-free hexagon has p solving
  p^3 + ((r p*^4 - 2 p*^2)/2) p - (r p*^4/2) p0 = 0 (the lowest-energy positive
  root), a = p^2/p*^2, shear modulus G = r (p - p0) p / (4a) and bulk modulus
  B = a + r p p0 / (4a); for p0 >= p*, G = 0 and B = 1. These were checked against
  an independent one-cell minimization with sublattice relaxation (MG1 design note).
- The box stress of regular hexagons of area a has half trace e'(a).
- Recoil (Farhadifar's cut: Lambda_ij = 0 and Gamma = 0 for the two cells sharing
  the junction) at an equilibrium with 120-degree junctions: each end vertex starts
  at speed (Lambda + Gamma L)/eta away from the other, so the opening rate is
  2 (Lambda + Gamma L)/eta; a junction-only cut gives 2 Lambda/eta.
- The minimal perimeter of a unit-area n-gon is sqrt(4 n tan(pi/n)) (regular n-gon):
  a zero-energy T1 state (two pentagons) needs p0 >= 3.8119350 (Bi et al. 2015).
"""

import json
import sys

import numpy as np
from scipy.optimize import brentq

P_STAR = float(np.sqrt(8.0 * np.sqrt(3.0)))


def staddon_parameters(line_tension, contractility):
    """(r, p0) of a uniform Farhadifar tissue."""
    return contractility, -line_tension / (2.0 * contractility)


def hexagon_state(r, p0):
    """(a, p) of the stress-free regular hexagon; (1, p*) is not returned for p0 >= p*."""
    if p0 >= P_STAR:
        raise ValueError("p0 >= p*: compatible regime, degenerate ground states")
    c1, c0 = (r * P_STAR**4 - 2.0 * P_STAR**2) / 2.0, -r * P_STAR**4 / 2.0 * p0
    roots = [z.real for z in np.roots([1.0, 0.0, c1, c0]) if abs(z.imag) < 1e-12 and z.real > 0]

    def energy(p):
        return 0.5 * (p**2 / P_STAR**2 - 1.0) ** 2 + 0.5 * r * (p - p0) ** 2

    guess = min(roots, key=energy)
    p = brentq(lambda q: q**3 + c1 * q + c0, guess * (1 - 1e-6), guess * (1 + 1e-6), xtol=1e-16)
    return p**2 / P_STAR**2, p


def ground_state(line_tension, contractility):
    """Farhadifar case: (a*, p, side, energy per cell)."""
    r, p0 = staddon_parameters(line_tension, contractility)
    a, p = hexagon_state(r, p0)
    return a, p, p / 6.0, energy_per_cell(a, line_tension, contractility)


def energy_per_cell(a, line_tension, contractility):
    p = P_STAR * np.sqrt(a)
    return 0.5 * (a - 1.0) ** 2 + 0.5 * line_tension * p + 0.5 * contractility * p**2


def stress_half_trace(a, line_tension, contractility):
    return (a - 1.0) + line_tension * P_STAR / (4.0 * np.sqrt(a)) + contractility * P_STAR**2 / 2


def moduli(r, p0):
    """(G, B) of the regular hexagonal network (Staddon 2023)."""
    if p0 >= P_STAR:
        return 0.0, 1.0
    a, p = hexagon_state(r, p0)
    return r * (p - p0) * p / (4.0 * a), a + r * p * p0 / (4.0 * a)


def recoil_opening_rate(line_tension, contractility, perimeter, friction=1.0):
    return 2.0 * (line_tension + contractility * perimeter) / friction


def minimal_perimeter(n):
    return float(np.sqrt(4.0 * n * np.tan(np.pi / n)))


def predictions():
    cases = {}
    for name, lam, gam in (("I", 0.12, 0.04), ("II", 0.0, 0.1)):
        a, p, side, e = ground_state(lam, gam)
        r, p0 = staddon_parameters(lam, gam)
        g, b = moduli(r, p0)
        cases[name] = {
            "lambda_bar": lam,
            "gamma_bar": gam,
            "area": a,
            "perimeter": p,
            "side": side,
            "energy_per_cell": e,
            "shear_modulus": g,
            "bulk_modulus": b,
            "recoil_opening_rate": recoil_opening_rate(lam, gam, p),
            "recoil_opening_rate_junction_only": 2.0 * lam,
            "box_scan": {
                f"{s}": {
                    "area": a * s**2,
                    "energy_per_cell": energy_per_cell(a * s**2, lam, gam),
                    "stress_half_trace": stress_half_trace(a * s**2, lam, gam),
                }
                for s in (0.95, 0.975, 1.0, 1.025, 1.05)
            },
        }
    grid = {
        f"r={r},p0={p0}": dict(zip(("G", "B"), moduli(r, p0), strict=True))
        for r in (0.04, 0.1, 1.0)
        for p0 in (3.0, 3.2, 3.4, 3.5, 3.6, 3.65, 3.7, 3.71, 3.72, 3.73, 3.75, 3.8, 3.9)
    }
    return {
        "units": "reduced: lengths sqrt(A0), energies K A0^2, moduli K A0, time eta/(K A0)",
        "p_star": P_STAR,
        "pentagon_threshold": minimal_perimeter(5),
        "minimal_perimeter": {n: minimal_perimeter(n) for n in range(3, 10)},
        "cases": cases,
        "ordered_moduli": grid,
    }


if __name__ == "__main__":
    json.dump(predictions(), sys.stdout if len(sys.argv) < 2 else open(sys.argv[1], "w"), indent=1)
