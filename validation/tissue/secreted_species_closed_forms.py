"""Continuum closed forms of the held sphere with first-order decay (D150 version 1 qualification).

docs/SECRETED_SPECIES_TRANSPORT_DESIGN.md §6 and Appendix A; independent NumPy, written from the
equations, never from engine code. A sphere of radius R is held at c0; the medium R < r < R_out has
diffusivity D and first-order clearance k; the outer boundary is held at c_out:

    du/dt = D (1/r^2) d/dr (r^2 du/dr) - k u,    u(R) = c0,  u(R_out) = c_out.

With v = r u it is the planar problem dv/dt = D v'' - k v, v(R) = R c0, v(R_out) = R_out c_out. Its
steady state is v_ss = A e^{r/lambda} + B e^{-r/lambda}, lambda = sqrt(D/k). The start is the steady
state plus a finite sum of sine modes of v, v(r, 0) = v_ss + sum_m a_m sin(m pi (r - R)/L), L =
R_out - R: it satisfies both boundary conditions (the bath holds c0 at t = 0 too), so

    v(r, t) = v_ss(r) + sum_m a_m e^{-mu_m t} sin(m pi (r - R)/L),   mu_m = D (m pi / L)^2 + k,

is exact with finitely many terms: no truncation term. With every a_m > 0 and a_1 >= 2 |a_2| the
start lies above the steady state, so it is positive. Every quantity below is an exact integral:

* shell averages (1/V) int 4 pi r^2 u dr over [e_i, e_{i+1}] (the finite-volume amounts' own
  meaning), from the antiderivatives of r v;
* M(t), the amount in the medium; S_source(t) and S_outer(t), the amounts the two baths have
  supplied (each flux 4 pi D (r v' - v) at its boundary, signed into the medium); C(t), the amount
  cleared, k int_0^t M. They satisfy M(t) - M(0) = S_source + S_outer - C exactly.

Units: r in m, u in mM; amounts in fmol (mM x pL, 1e15 pL per m^3).
"""

import math
from dataclasses import dataclass

import numpy as np

PL_PER_M3 = 1e15


@dataclass(frozen=True)
class HeldSphere:
    radius_m: float
    outer_m: float
    diffusivity: float  # m^2/s
    clearance: float  # 1/s
    c0_mM: float
    c_out_mM: float
    modes: tuple = ()  # ((m, a_m in mM m), ...): the start's sine modes of v.

    @property
    def lam(self):
        return math.sqrt(self.diffusivity / self.clearance)

    @property
    def length(self):
        return self.outer_m - self.radius_m

    def coefficients(self):
        """The scaled (A', B') of v_ss = A e^{r/lambda} + B e^{-r/lambda}: A' = A e^{R_out/lambda},
        B' = B e^{-R/lambda} (well conditioned), from v(R) = R c0 and v(R_out) = R_out c_out."""
        lam, r0, r1 = self.lam, self.radius_m, self.outer_m
        # v(R) = A' e^{(R - R_out)/lam} + B';  v(R_out) = A' + B' e^{-(R_out - R)/lam}.
        q = math.exp(-(r1 - r0) / lam)
        m = np.array([[q, 1.0], [1.0, q]])
        a_scaled, b_scaled = np.linalg.solve(m, [r0 * self.c0_mM, r1 * self.c_out_mM])
        return a_scaled, b_scaled  # Scaled: see _exp_terms.

    def _exp_terms(self, r):
        """(e^{(r - R_out)/lam}, e^{-(r - R)/lam}): the scaled exponentials, each <= 1."""
        lam = self.lam
        return np.exp((r - self.outer_m) / lam), np.exp(-(r - self.radius_m) / lam)

    def rate(self, m):
        return self.diffusivity * (m * math.pi / self.length) ** 2 + self.clearance

    # ------------------------------------------------------------ the field

    def v(self, r, t):
        r = np.asarray(r, dtype=float)
        a, b = self.coefficients()
        up, down = self._exp_terms(r)
        value = a * up + b * down
        for m, amplitude in self.modes:
            value = value + amplitude * math.exp(-self.rate(m) * t) * np.sin(
                m * math.pi * (r - self.radius_m) / self.length
            )
        return value

    def u(self, r, t):
        return self.v(r, t) / np.asarray(r, dtype=float)

    def dv(self, r, t):
        """dv/dr."""
        r = np.asarray(r, dtype=float)
        a, b = self.coefficients()
        up, down = self._exp_terms(r)
        value = (a * up - b * down) / self.lam
        for m, amplitude in self.modes:
            w = m * math.pi / self.length
            value = value + amplitude * math.exp(-self.rate(m) * t) * w * np.cos(
                w * (r - self.radius_m)
            )
        return value

    # ------------------------------------------------------------ exact integrals

    def _antiderivative(self, r, t):
        """F(r) with F' = r v(r, t) (mM m^3 per m... units: mM m^3 before the 4 pi)."""
        r = np.asarray(r, dtype=float)
        a, b = self.coefficients()
        lam = self.lam
        up, down = self._exp_terms(r)
        value = a * lam * up * (r - lam) - b * lam * down * (r + lam)
        for m, amplitude in self.modes:
            w = m * math.pi / self.length
            s = r - self.radius_m
            value = value + amplitude * math.exp(-self.rate(m) * t) * (
                -r * np.cos(w * s) / w + np.sin(w * s) / w**2
            )
        return value

    def shell_averages(self, edges, t):
        """[shell] (1/V) int 4 pi r^2 u dr over each [e_i, e_{i+1}] (mM)."""
        e = np.asarray(edges, dtype=float)
        f = self._antiderivative(e, t)
        return 3.0 * (f[1:] - f[:-1]) / (e[1:] ** 3 - e[:-1] ** 3)

    def amount_fmol(self, t):
        """M(t) = int_R^R_out 4 pi r^2 u dr (fmol)."""
        f = self._antiderivative(np.array([self.radius_m, self.outer_m]), t)
        return 4.0 * math.pi * (f[1] - f[0]) * PL_PER_M3

    def _mode_amount_fmol(self, m):
        """4 pi int r sin(m pi (r - R)/L) dr over the medium (fmol per unit a_m)."""
        w = m * math.pi / self.length
        r0, r1 = self.radius_m, self.outer_m
        value = (-r1 * math.cos(w * self.length) + r0) / w
        return 4.0 * math.pi * value * PL_PER_M3

    def steady_amount_fmol(self):
        lam = self.lam
        a, b = self.coefficients()
        r = np.array([self.radius_m, self.outer_m])
        up, down = self._exp_terms(r)
        f = a * lam * up * (r - lam) - b * lam * down * (r + lam)
        return 4.0 * math.pi * (f[1] - f[0]) * PL_PER_M3

    def _flux_terms(self, r, sign):
        """(the steady flux into the medium at r, [(mode coefficient, rate)]) in fmol/s. The radial
        flux is -4 pi D (r v' - v); sign +1 at the source (where +r points into the medium), -1 at
        the outer boundary."""
        d = self.diffusivity
        steady = -sign * 4.0 * math.pi * d * (r * self.dv(r, math.inf) - self.v(r, math.inf))
        modes = []
        for m, amplitude in self.modes:
            w = m * math.pi / self.length
            cos = math.cos(w * (r - self.radius_m))
            modes.append((-sign * 4.0 * math.pi * d * r * amplitude * w * cos, self.rate(m)))
        return steady * PL_PER_M3, [(c * PL_PER_M3, mu) for c, mu in modes]

    def _supplied(self, r, sign, t):
        steady, modes = self._flux_terms(r, sign)
        return steady * t + sum(c * (1.0 - math.exp(-mu * t)) / mu for c, mu in modes)

    def source_supplied_fmol(self, t):
        """int_0^t of the source bath's flux into the medium (fmol)."""
        return self._supplied(self.radius_m, +1.0, t)

    def outer_supplied_fmol(self, t):
        """int_0^t of the outer bath's flux into the medium (fmol; negative: it absorbs)."""
        return self._supplied(self.outer_m, -1.0, t)

    def cleared_fmol(self, t):
        """C(t) = k int_0^t M (fmol)."""
        k = self.clearance
        value = self.steady_amount_fmol() * t
        for m, amplitude in self.modes:
            mu = self.rate(m)
            value += amplitude * self._mode_amount_fmol(m) * (1.0 - math.exp(-mu * t)) / mu
        return k * value


def gauss_shell_averages(problem, edges, t, points=24):
    """The shell averages by Gauss-Legendre quadrature (a cross-check of the exact integrals)."""
    x, w = np.polynomial.legendre.leggauss(points)
    e = np.asarray(edges, dtype=float)
    out = []
    for lo, hi in zip(e[:-1], e[1:], strict=True):
        r = 0.5 * (hi - lo) * x + 0.5 * (hi + lo)
        integral = 0.5 * (hi - lo) * np.sum(w * 4.0 * math.pi * r**2 * problem.u(r, t))
        out.append(integral / (4.0 / 3.0 * math.pi * (hi**3 - lo**3)))
    return np.asarray(out)
