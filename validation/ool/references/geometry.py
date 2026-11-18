"""OL2 (registered ahead of its engine; no ruling needed): geometry from the counts, the lumen's
free energy and tension, and the tension-driven end states, in closed form (design §2.5, §4.1).

**The physical state, algebraic in the counts** (§4.1). For a bilayer vesicle with amphiphile
counts n_i, each with area a_L,i per molecule per leaflet, impermeant lumen solutes N_imp and an
outside osmolarity c_ext (molar):
- area A = Sum_i n_i a_L,i / 2;
- the osmotic volume V_osm = N_imp / (N_A c_ext) and the sphere's volume V_sph(A) = A^(3/2)/(6 sqrt pi);
- the volume V = min(V_osm, V_sph(A)) (water is fast), the reduced volume v = V/V_sph(A) <= 1,
  and the radius R = sqrt(A/(4 pi));
- the pressure difference Dp = k_BT (N_imp/V - N_A c_ext) (number densities), zero while the
  vesicle is floppy (V = V_osm) and positive when its area caps the volume;
- the tension, Laplace's sigma = Dp R/2.

**The lumen's free energy** (§2.2): impermeant solutes ideal in V, plus the outside pressure's
work, F_lumen/k_BT = Sum_s [n_s (mu0_s - ln(N_A V c0)) + ln n_s!] + N_A c_ext V. Then
dF/dV = -Dp, dV_sph/dA = R/2 and dA/dn_i = a_L,i/2, so in the tense regime each amphiphile's
potential falls by sigma a_L,i / 2 (§2.5). At V_osm = V_sph the tension is zero on both sides, so F
is continuously differentiable there; only its second derivative jumps. ``lumen_free_energy``
evaluates F with V from the counts, and the tests hold its numerical derivative equal to
-sigma a_L/2 on both sides of the kink.

**End states** (minima of F; §4.2, §7.1 "Tension-driven exchange"):
- ``zero_tension_area``: the smallest area at which a vesicle is not tense,
  A_osm = (6 sqrt pi V_osm)^(2/3). A tense vesicle in contact with amphiphile at the CAC grows to it.
- ``two_vesicle_split``: two vesicles sharing a fixed total area (their amphiphile exchanged
  through the pool at the CAC) reach equal tensions. If the total area exceeds
  A_osm,1 + A_osm,2 both can relax to zero tension and the deterministic split is degenerate (it
  is reported as such); otherwise both are tense and the split is the unique root of
  sigma_1(A_1) = sigma_2(A_tot - A_1), sigma decreasing in A.

Units are SI inside (m^2, m^3, Pa, N/m, J); molar concentrations are converted with N_A and
1000 L per m^3. k_B and N_A take their exact SI values.

Planted controls: a_L off by a factor of two (the bilayer's 1/2 dropped), a wrong Laplace factor
(sigma = Dp R), and a wrong sphere constant (6 pi for 6 sqrt pi). Each moves a registered
quantity by far more than the comparison's tolerance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.optimize import brentq

K_B = 1.380649e-23          # J/K, exact (SI 2019)
N_A = 6.02214076e23         # 1/mol, exact
L_PER_M3 = 1000.0
PLANTED_GEOMETRY = ("aL_double", "laplace_double", "sphere_constant")


@dataclass(frozen=True)
class Vesicle:
    """One vesicle's counts and parameters: amphiphile counts with areas per molecule per leaflet
    (m^2), the impermeant lumen count, the outside osmolarity (mol/L) and the temperature (K)."""

    n_amph: tuple
    a_L: tuple
    n_imp: int
    c_ext_M: float
    T: float = 298.15
    planted: str | None = None

    @property
    def kT(self) -> float:
        return K_B * self.T

    @property
    def area(self) -> float:
        a = sum(n * a for n, a in zip(self.n_amph, self.a_L, strict=True))
        return a if self.planted == "aL_double" else a / 2

    @property
    def rho_ext(self) -> float:
        """Outside number density of osmolytes, per m^3."""
        return self.c_ext_M * L_PER_M3 * N_A

    @property
    def v_osm(self) -> float:
        return self.n_imp / self.rho_ext

    def v_sph(self, A: float | None = None) -> float:
        A = self.area if A is None else A
        const = 6 * math.pi if self.planted == "sphere_constant" else 6 * math.sqrt(math.pi)
        return A ** 1.5 / const

    @property
    def volume(self) -> float:
        return min(self.v_osm, self.v_sph())

    @property
    def reduced_volume(self) -> float:
        return self.volume / self.v_sph()

    @property
    def radius(self) -> float:
        return math.sqrt(self.area / (4 * math.pi))

    @property
    def tense(self) -> bool:
        return self.v_osm > self.v_sph()

    @property
    def pressure(self) -> float:
        """Dp (Pa): zero while floppy."""
        if not self.tense:
            return 0.0
        return self.kT * (self.n_imp / self.volume - self.rho_ext)

    @property
    def tension(self) -> float:
        """sigma (N/m), Laplace's Dp R / 2."""
        factor = 1.0 if self.planted == "laplace_double" else 0.5
        return factor * self.pressure * self.radius

    def potential_drop_kT(self, i: int) -> float:
        """sigma a_L,i / 2 in k_BT: how far species i's potential in the membrane falls."""
        return self.tension * self.a_L[i] / 2 / self.kT

    def derived(self) -> dict:
        return dict(area_m2=self.area, v_osm_m3=self.v_osm, v_sph_m3=self.v_sph(), volume_m3=self.volume,
                    reduced_volume=self.reduced_volume, radius_m=self.radius, pressure_Pa=self.pressure,
                    tension_N_per_m=self.tension)


def lumen_free_energy(ves: Vesicle, mu0_imp_kT: float = 0.0, c0_M: float = 1.0) -> float:
    """F_lumen / k_BT with V from the counts (one impermeant species, discrete ln n!)."""
    V_L = ves.volume * L_PER_M3
    n = ves.n_imp
    return n * (mu0_imp_kT - math.log(N_A * V_L * c0_M)) + math.lgamma(n + 1) + N_A * ves.c_ext_M * V_L


def zero_tension_area(n_imp: int, c_ext_M: float) -> float:
    """A_osm = (6 sqrt(pi) V_osm)^(2/3): the smallest area at which the vesicle is not tense."""
    v_osm = n_imp / (c_ext_M * L_PER_M3 * N_A)
    return (6 * math.sqrt(math.pi) * v_osm) ** (2.0 / 3.0)


def tension_at_area(A: float, n_imp: int, c_ext_M: float, T: float = 298.15) -> float:
    """sigma (N/m) of a vesicle of area A (any composition), from §4.1."""
    v_sph = A ** 1.5 / (6 * math.sqrt(math.pi))
    rho = c_ext_M * L_PER_M3 * N_A
    if n_imp / rho <= v_sph:
        return 0.0
    return K_B * T * (n_imp / v_sph - rho) * math.sqrt(A / (4 * math.pi)) / 2


def two_vesicle_split(A_tot: float, n_imp: tuple, c_ext_M: float, T: float = 298.15) -> dict:
    """The deterministic end state of two vesicles sharing area A_tot: equal tensions."""
    a1, a2 = zero_tension_area(n_imp[0], c_ext_M), zero_tension_area(n_imp[1], c_ext_M)
    if A_tot >= a1 + a2:
        return dict(degenerate=True, both_relaxed=True, range_A1=(a1, A_tot - a2), tension=0.0)

    def gap(A1):
        return tension_at_area(A1, n_imp[0], c_ext_M, T) - tension_at_area(A_tot - A1, n_imp[1], c_ext_M, T)

    lo, hi = A_tot * 1e-9, A_tot * (1 - 1e-9)
    A1 = brentq(gap, lo, hi, xtol=A_tot * 1e-15, rtol=4 * 2.0 ** -52, maxiter=500)
    return dict(degenerate=False, A1=A1, A2=A_tot - A1, tension=tension_at_area(A1, n_imp[0], c_ext_M, T))


def admission_threshold(k: int) -> float:
    """The largest reduced volume at which a vesicle can split into k equal spheres: k^(-1/2).

    k spheres sharing the area A have total volume k (A/k)^(3/2)/(6 sqrt pi) = k^(-1/2) V_sph(A),
    so the parent's V fits only if v = V/V_sph(A) <= k^(-1/2) (§4.3, D2)."""
    if k < 2:
        raise ValueError("division needs at least two daughters")
    return k ** -0.5
