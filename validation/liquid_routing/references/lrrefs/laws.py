"""The closed forms of LAWS.md: two wells, the one-step scheme, the default heat, an exchange, a chain, portions."""

from decimal import Decimal

from .arith import HALF, ONE, TWO, ZERO, phi, x_ln_ratio


# ---- free energy (LAWS section 0) --------------------------------------------------------------------

def free_energy(rt, n, volume):
    """F(n, V) = RT n (ln(n/V) - 1); F(0, .) = 0."""
    if n == 0:
        return ZERO
    return rt * n * ((n / volume).ln() - 1)


def free_energy_density(rt, c):
    """f(c) = RT c (ln c - 1), per pL of liquid."""
    if c == 0:
        return ZERO
    return rt * c * (c.ln() - 1)


# ---- two wells (LAWS sections 1 and 2) ----------------------------------------------------------------

class TwoWells:
    """One neutral species, permeance PA, between volumes V1 and V2, starting at n1 and n2."""

    def __init__(self, rt, n1, n2, v1, v2, pa):
        self.rt, self.n1, self.n2, self.v1, self.v2, self.pa = rt, n1, n2, v1, v2, pa
        self.c1, self.c2 = n1 / v1, n2 / v2
        self.k = pa * (1 / v1 + 1 / v2)
        self.reach = (self.c1 - self.c2) / (1 / v1 + 1 / v2)          # M_infinity

    # the exact solution
    def moved(self, t):
        return self.reach * (1 - (-(self.k * t)).exp())

    # the scheme's one step
    @staticmethod
    def stability(z):
        return 1 - z + z * z / 2

    def moved_by_scheme(self, h):
        z = self.k * h
        return self.reach * (z - z * z / 2)

    def levels(self, m):
        return self.n1 - m, self.n2 + m

    # the free energy lost and its slope
    def lost(self, m):
        before = free_energy(self.rt, self.n1, self.v1) + free_energy(self.rt, self.n2, self.v2)
        after = free_energy(self.rt, self.n1 - m, self.v1) + free_energy(self.rt, self.n2 + m, self.v2)
        return before - after

    def affinity(self, s):
        return self.rt * (((self.n1 - s) / self.v1) / ((self.n2 + s) / self.v2)).ln()

    def affinity_slope(self, s):
        """|A'(s)|"""
        return self.rt * (1 / (self.n1 - s) + 1 / (self.n2 + s))

    def affinity_curvature(self, s):
        """A''(s)"""
        return self.rt * (1 / (self.n2 + s) ** 2 - 1 / (self.n1 - s) ** 2)

    # the default heat's declared law
    def default_heat(self, h):
        """The two-well form: RT m_R ln(c1*/c2*)."""
        flux = self.pa * (self.c1 - self.c2)
        c1_star = self.c1 - (h / 2) * flux / self.v1
        c2_star = self.c2 + (h / 2) * flux / self.v2
        return self.rt * self.moved_by_scheme(h) * (c1_star / c2_star).ln()

    def default_heat_by_weight(self, h):
        """The declared form: RT h Jbar^2 / W, with ARS(2,2,2)'s gamma and delta and a logarithmic-mean W."""
        gamma, delta = ars_constants()
        j1 = self.pa * (self.c1 - self.c2)
        c1_stage = self.c1 - gamma * h * j1 / self.v1
        c2_stage = self.c2 + gamma * h * j1 / self.v2
        j2 = self.pa * (c1_stage - c2_stage)
        mean_flux = delta * j1 + (1 - delta) * j2
        c1_star = self.c1 - (h / 2) * j1 / self.v1
        c2_star = self.c2 + (h / 2) * j1 / self.v2
        weight = self.pa * (c1_star - c2_star) / (c1_star / c2_star).ln()
        return self.rt * h * mean_flux * mean_flux / weight

    def default_bound(self, h):
        """B_def(h), the Taylor remainder of H_def against D(m_R)."""
        z = self.k * h
        m = self.moved_by_scheme(h)
        s_star = self.reach * z / 2
        d = self.reach * z * z / 4
        slope = max(self.affinity_slope(m / 2), self.affinity_slope(s_star))
        curvature = max(abs(self.affinity_curvature(ZERO)), abs(self.affinity_curvature(m)))
        return abs(m * d * slope) + abs(m ** 3 / 24 * curvature)

    def leading_constant(self):
        """C2 of H_def - D = -C2 z^2 D + ..."""
        total = self.v1 + self.v2
        a1, a2 = self.v2 / total, self.v1 / total
        dc = self.c1 - self.c2
        s1 = dc * (a1 / self.c1 + a2 / self.c2)
        s2 = dc * dc * (a1 * a1 / (self.c1 * self.c1) - a2 * a2 / (self.c2 * self.c2))
        return (s1 / 4 - s2 / 24) / (self.c1 / self.c2).ln()


def ars_constants():
    """gamma = 1 - 1/sqrt(2), delta = 1 - 1/(2 gamma) (Ascher, Ruuth and Spiteri 1997)."""
    gamma = 1 - 1 / TWO.sqrt()
    delta = 1 - 1 / (2 * gamma)
    return gamma, delta


def explicit_step(y, h, slope):
    """One ARS(2,2,2) explicit step of a list-valued state (LAWS section 2)."""
    gamma, delta = ars_constants()
    g1 = slope(y)
    stage = [a + gamma * h * b for a, b in zip(y, g1)]
    g2 = slope(stage)
    return [a + h * (delta * b + (1 - delta) * c) for a, b, c in zip(y, g1, g2)]


# ---- an exchange (LAWS section 3) ---------------------------------------------------------------------

def exchange(rt, n, volume, fraction, level):
    """(sample, supplied, after, heat) of a partial exchange at a well, by the first form of H_ev."""
    sample = fraction * n
    supplied = fraction * volume * level
    after = (1 - fraction) * n + supplied
    c, c_after = n / volume, after / volume
    heat = rt * (x_ln_ratio((1 - fraction) * n, c, c_after) + x_ln_ratio(supplied, level, c_after))
    return sample, supplied, after, heat


def exchange_heat_by_phi(rt, n, volume, fraction, level):
    """H_ev by the second form: RT V c' [(1 - f) phi(c/c') + f phi(x/c')]."""
    after = (1 - fraction) * n + fraction * volume * level
    c, c_after = n / volume, after / volume
    return rt * volume * c_after * ((1 - fraction) * phi(c / c_after) + fraction * phi(level / c_after))


# ---- a chain I -> A -> B -> K (LAWS section 4) --------------------------------------------------------

class Chain:
    """The two-chamber chain: first, second, the flow and the inlet level."""

    def __init__(self, n_first, n_second, v_first, v_second, rate, level):
        self.n1, self.n2, self.v1, self.v2, self.q, self.x = n_first, n_second, v_first, v_second, rate, level
        self.a = rate / v_first
        self.b = rate / v_second

    def difference_quotient(self, t):
        """E(t) = (e^(-at) - e^(-bt))/(b - a); t e^(-at) where a = b."""
        if self.a == self.b:
            return t * (-(self.a * t)).exp()
        return ((-(self.a * t)).exp() - (-(self.b * t)).exp()) / (self.b - self.a)

    def state(self, t):
        u1 = self.n1 - self.v1 * self.x
        u2 = self.n2 - self.v2 * self.x
        first = self.v1 * self.x + u1 * (-(self.a * t)).exp()
        second = self.v2 * self.x + u2 * (-(self.b * t)).exp() + self.a * u1 * self.difference_quotient(t)
        collected = self.n1 + self.n2 + self.q * self.x * t - first - second
        return first, second, collected


# ---- portions (LAWS section 6) ------------------------------------------------------------------------

def portion(rt, n, volume, v, x):
    """(n', V', loss, resident part, arriving part) of a portion (v, x) joining (n, V), by the phi form.

    Into zero volume both parts are zero.
    """
    n_after = n + v * x
    v_after = volume + v
    y = n_after / v_after
    if volume == 0:
        return n_after, v_after, ZERO, ZERO, ZERO
    resident = rt * volume * y * phi((n / volume) / y)
    arriving = rt * v * y * phi(x / y)
    return n_after, v_after, resident + arriving, resident, arriving


def portion_loss_by_logs(rt, n, volume, v, x):
    """The first form: RT [n ln(c/y) + v x ln(x/y)]."""
    y = (n + v * x) / (volume + v)
    loss = x_ln_ratio(v * x, x, y)
    if volume != 0:
        loss += x_ln_ratio(n, n / volume, y)
    return rt * loss


__all__ = ["Decimal", "HALF", "ONE"]
