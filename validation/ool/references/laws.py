"""The event-pair contract, written from the design's equations (ORIGIN_OF_LIFE_ENGINE_DESIGN
§0.1, §2.1-2.4) and the OL1 family's declared forms, exactly.

**State.** n is the vector of counts of the world's finite places (membrane places and finite
dilute places), in declared order. N(n) is the membrane's total count. Held places have a fixed
concentration c_h and are not state.

**Free energy** (in k_BT), with X_phi = N_A V_phi c0 for a dilute phase and the measure offset
c (0 for ``multinomial``, 1 for ``multinomial_less_one``):

    F(n) = Sum_dilute p [n_p (mu0_p - ln X_phi) + ln n_p!]
         + Sum_membrane i n_i mu0_i - ln (N - c)! + Sum_i ln n_i!  + R(n),

with the membrane part 0 at N = 0, and regular mixing R(n) = (1/2N) Sum_ij chi_ij n_i n_j over
the membrane (§2.2; R(0) = 0). Every term is the exact discrete form: ln n! where §2.2's table
writes the Stirling form n ln n - n. Only the discrete form makes the exact kernel's reverse
rate mass action (§2.1), so the continuum form is refused here as the family refuses it.

A held place h has mu_h = mu0_h + ln(c_h/c0). A forward event books reservoir work
w = -Sum_h nu_h mu_h.

**Rates** (§0.1). For the pair n -> n' = n + nu, with the common state m = min(n, n'):

    a+(n)  = E(m) g(m) theta+(n),
    a-(n') = E(m) g(m) theta+(n) exp(F(n') - F(n) - w),

so ln a+(n) - ln a-(n') = -(F(n') - F(n)) + w on every pair, by construction.
- **Activities at the firing state:** a dilute reactant p contributes n_p!/(n_p - alpha_p)!
  / X_phi^alpha_p; the membrane reactants together contribute
  prod_i n_i!/(n_i - alpha_i)! / ff(N - c, r_mem), the draw of r_mem molecules without
  replacement from N - c; a held reactant contributes (c_h/c0)^alpha_h. theta+ is the forward
  rate constant times their product.
- **The extent on the common state:** X_phi for a dilute locus; N(m) - c + 1 for the membrane.
- **The transition-state factor** (§2.4, form (b)): g(m) = 1 + Sum_j beta_j x_j(m), with x_j the
  catalyst's fraction of the membrane at m and beta_j = exp(ddG_j/k_BT) - 1 > -1. Where the
  membrane is empty at m, g = 1 (``empty_catalyst_phase = uncatalysed``).
- **Zero factors.** Where a reactant is missing, ff(N - c, r_mem) = 0 or E(m) = 0, both rates of
  the pair are zero.
- **The last molecule.** ``kept``: E(m) = 0 where the membrane is empty at m, so it never
  empties. ``reversible`` (c = 0): the empty membrane is an ordinary state (E = 1 there).
  ``extinct`` (c = 1): a channel whose target state has an empty membrane fires at the continued
  value of its rate, its membrane factor E(m)/ff(N - 1, r) continued to 1/ff(N - 1, r - 1). It
  has no reverse (the empty state is absorbing), so it is excluded from every detailed-balance
  check, and its rate is checked against this form directly. For the last molecule's leave it is
  k-, as in the lineage family.

**The products' rule** (an independent path, §2.1). The reverse rate is the same rule applied to
the products with k- = k+ exp(Sum_places nu mu0) (held places at their standard potential), times
the activity coefficient exp(R(n') - R(n)) of regular mixing:

    a-(n') = k- [products' activities at n'] E(m) g(m) exp(R(n') - R(n)).

It is derived here for every order up to three on each side and under both measures: the
membrane's ff(N - c, r) normalisations and the N!-ratio of the measure cancel exactly against
E(m) = N(m) - c + 1 (the tests hold the two paths equal, exactly, on every probe state).

**Planted forms** (each must be caught by the check README.md names):
- ``at_state_factor``: g at each direction's own state (E1's form);
- ``forward_only_catalysis``: g on the forward channel and 1 on the reverse;
- ``one_sided``: one step's reverse multiplied by exp(lam x_j(n')), with no reciprocal term in F
  (E2's lesson);
- ``power_propensity``: n^alpha in place of the falling factorial, the reverse still from F;
- ``normaliser_power``: N^r in place of ff(N - c, r) for the membrane draw;
- ``extent_offset``: E = N(m) whatever the measure;
- ``dropped_c0``: X = N_A V without c0, everywhere (a consistent engine with a wrong X);
- ``wrong_sign``: the reverse from exp(-(F(n') - F(n) - w)).
"""

from __future__ import annotations

import math
from fractions import Fraction

from .common import RecordFormatError
from .exact import ONE, ZERO, RatExp, falling_factorial
from .world import Conventions, Step, World

PLANTED_FORMS = ("at_state_factor", "forward_only_catalysis", "one_sided", "power_propensity",
                 "normaliser_power", "extent_offset", "dropped_c0", "wrong_sign")


def factorial_ratio(a: int, b: int) -> Fraction:
    """a!/b! for non-negative integers, without forming either factorial."""
    if a >= b:
        out = 1
        for j in range(b + 1, a + 1):
            out *= j
        return Fraction(out)
    out = 1
    for j in range(a + 1, b + 1):
        out *= j
    return Fraction(1, out)


class Law:
    """One world's event-pair law under declared conventions, exactly (RatExp)."""

    def __init__(self, world: World, conventions: Conventions, planted: str | None = None,
                 planted_params: dict | None = None):
        if planted is not None and planted not in PLANTED_FORMS:
            raise ValueError(f"unknown planted form {planted!r}")
        if not isinstance(conventions, Conventions):
            raise RecordFormatError("conventions must be a Conventions instance")
        self.world = world
        self.conv = conventions
        self.c = conventions.c
        self.planted = planted
        self.pp = dict(planted_params or {})
        self.D = world.dim
        self.mem = world.membrane_mask()
        self.chi = world.chi_matrix()
        self.places = world.finite
        self.nu = {st.name: world.nu(st) for st in world.steps}
        self.alpha = {st.name: world.alpha(st) for st in world.steps}
        self.beta = {st.name: world.beta_finite(st) for st in world.steps}
        self.nu_h = {st.name: world.nu_held(st) for st in world.steps}
        self.cat = {st.name: [(world.index(c.place), c.beta) for c in st.catalysts] for st in world.steps}
        self.em = [p.exp_minus_mu0 for p in self.places]
        self.c0_M = world.c0_mM.exact / 1000
        self.Xp = {i: self.X(p.phase) for i, p in enumerate(self.places) if not p.membrane}

    # ---------------------------------------------------------------- structure
    def X(self, phase: str) -> Fraction:
        x = self.world.avogadro.exact * self.world.volumes_L[phase].exact
        return x if self.planted == "dropped_c0" else x * self.c0_M

    def N(self, n) -> int:
        return sum(v for v, is_m in zip(n, self.mem) if is_m)

    def common_state(self, st: Step, n) -> tuple:
        return tuple(min(a, a + d) for a, d in zip(n, self.nu[st.name]))

    # ---------------------------------------------------------------- free energy
    def membrane_measure(self, n) -> Fraction:
        """exp(-[Sum ln n_i! - ln (N - c)!]), with 1 at N = 0."""
        N = self.N(n)
        if N == 0:
            return Fraction(1)
        out = Fraction(math.factorial(N - self.c))
        for v, is_m in zip(n, self.mem):
            if is_m:
                out /= math.factorial(v)
        return out

    def regular(self, n) -> Fraction:
        N = self.N(n)
        if N == 0:
            return Fraction(0)
        acc = Fraction(0)
        for i in range(self.D):
            if n[i] and self.mem[i]:
                row = self.chi[i]
                for j in range(self.D):
                    if n[j] and row[j]:
                        acc += row[j] * n[i] * n[j]
        return acc / (2 * N)

    def weight(self, n) -> RatExp:
        """exp(-F(n)), exactly."""
        r = self.membrane_measure(n)
        for i, v in enumerate(n):
            if self.mem[i]:
                r *= self.em[i] ** v
            else:
                r *= (self.em[i] * self.Xp[i]) ** v / math.factorial(v)
        return RatExp(r, -self.regular(n))

    def free_energy(self, n) -> float:
        return -self.weight(n).log()

    def exp_minus_w(self, st: Step) -> Fraction:
        """exp(-w) = exp(Sum_h nu_h mu_h) for the forward event, exactly."""
        out = Fraction(1)
        for h, v in self.nu_h[st.name].items():
            pl = self.world.places[h]
            act = pl.held_mM.exact / self.world.c0_mM.exact
            out *= (act / pl.exp_minus_mu0) ** v
        return out

    def reservoir_work(self, st: Step) -> float:
        """w = -Sum_h nu_h mu_h (k_BT), booked by the forward event."""
        return -RatExp(self.exp_minus_w(st)).log()

    def exp_delta(self, st: Step, n) -> RatExp:
        """exp(F(n') - F(n) - w) for the forward event from n, by an incremental ratio."""
        nu = self.nu[st.name]
        p = tuple(a + d for a, d in zip(n, nu))
        r = Fraction(1)
        for i, d in enumerate(nu):
            if not d:
                continue
            if self.mem[i]:
                r *= self.em[i] ** (-d)
            else:
                r *= (self.em[i] * self.Xp[i]) ** (-d)
            r *= factorial_ratio(p[i], n[i])
        N, P = self.N(n), self.N(p)
        if N == 0 or P == 0:
            mn = Fraction(1) if N == 0 else Fraction(math.factorial(N - self.c))
            mp = Fraction(1) if P == 0 else Fraction(math.factorial(P - self.c))
            r *= mn / mp
        else:
            r *= factorial_ratio(N - self.c, P - self.c)
        r *= self.exp_minus_w(st)
        return RatExp(r, self.regular(p) - self.regular(n))

    def delta_F_minus_w(self, st: Step, n) -> float:
        """F(n') - F(n) - w for the forward event from n (k_BT, float from the exact value)."""
        return self.exp_delta(st, n).log()

    # ---------------------------------------------------------------- kinetics
    def factor(self, st: Step, m) -> Fraction:
        cats = self.cat[st.name]
        if not cats:
            return Fraction(1)
        N = self.N(m)
        if N == 0:
            return Fraction(1)
        return 1 + sum((beta * m[j] for j, beta in cats), Fraction(0)) / N

    def _ff(self, v: int, a: int) -> int:
        return v ** a if self.planted == "power_propensity" else falling_factorial(v, a)

    def activity(self, st: Step, n, *, continued: bool = False) -> Fraction | None:
        """The reactants' activities at the firing state n; None for a zero factor.

        With ``continued``, the membrane draw is divided by ff(N - 1, r_mem - 1) instead of
        ff(N - c, r_mem): the extinct boundary's continued value (the extent then drops out)."""
        alpha = self.alpha[st.name]
        if any(a > v for a, v in zip(alpha, n)):
            return None
        out = Fraction(1)
        r_mem = 0
        for i, (a, v) in enumerate(zip(alpha, n)):
            if not a:
                continue
            if self.mem[i]:
                out *= self._ff(v, a)
                r_mem += a
            else:
                out *= Fraction(self._ff(v, a)) / self.Xp[i] ** a
        if r_mem:
            N = self.N(n)
            if continued:
                den = falling_factorial(N - 1, r_mem - 1)
            elif self.planted == "normaliser_power":
                den = N ** r_mem
            else:
                den = falling_factorial(N - self.c, r_mem) if N - self.c >= 0 else 0
            if den == 0:
                return None
            out /= den
        for p, a in st.reactants.items():
            pl = self.world.places[p]
            if pl.held:
                out *= (pl.held_mM.exact / self.world.c0_mM.exact) ** a
        return out

    def extent(self, st: Step, m) -> Fraction:
        if st.locus != "membrane":
            return self.X(st.locus)
        N = self.N(m)
        if self.conv.last_molecule == "kept" and N == 0:
            return Fraction(0)
        if self.planted == "extent_offset":
            return Fraction(N)
        return Fraction(N - self.c + 1)

    def empties_membrane(self, st: Step, n, sign: int) -> bool:
        """True if the channel (sign +1 forward, -1 reverse) from n leaves the membrane empty."""
        nu = self.nu[st.name]
        q = tuple(a + sign * d for a, d in zip(n, nu))
        return self.N(n) > 0 and self.N(q) == 0

    def forward(self, st: Step, n) -> RatExp:
        """a+(n): the rate of n -> n + nu (zero when the pair has a zero factor)."""
        n = tuple(n)
        if self.conv.last_molecule == "extinct" and self.empties_membrane(st, n, +1):
            act = self.activity(st, n, continued=True)
            return ZERO if act is None else RatExp(st.rate.exact * act)
        act = self.activity(st, n)
        if act is None:
            return ZERO
        m = self.common_state(st, n)
        E = self.extent(st, m)
        if E <= 0:
            return ZERO
        g = self.factor(st, n if self.planted == "at_state_factor" else m)
        return RatExp(st.rate.exact * g * E * act)

    def reverse(self, st: Step, p) -> RatExp:
        """a-(p): the rate of p -> p - nu, the reverse channel at p."""
        p = tuple(p)
        nu = self.nu[st.name]
        n = tuple(a - d for a, d in zip(p, nu))
        if any(v < 0 for v in n):
            return ZERO
        if self.conv.last_molecule == "extinct" and self.empties_membrane(st, p, -1):
            return self.continued_reverse(st, p)
        if self.conv.last_molecule == "extinct" and self.empties_membrane(st, n, +1):
            return ZERO  # the forward from n is a one-way extinction: it has no reverse
        act = self.activity(st, n)
        if act is None:
            return ZERO
        m = self.common_state(st, n)
        E = self.extent(st, m)
        if E <= 0:
            return ZERO
        if self.planted == "at_state_factor":
            g = self.factor(st, p)
        elif self.planted == "forward_only_catalysis":
            g = Fraction(1)
        else:
            g = self.factor(st, m)
        edf = self.exp_delta(st, n)
        if self.planted == "wrong_sign":
            edf = ONE / edf
        out = RatExp(st.rate.exact * g * E * act) * edf
        if self.planted == "one_sided" and st.name == self.pp.get("step"):
            j = self.world.index(self.pp["place"])
            P = self.N(p)
            if P:
                out = out * RatExp.exp(Fraction(self.pp["lam"]) * Fraction(p[j], P))
        return out

    def k_minus(self, st: Step) -> Fraction:
        """k- = k+ exp(Sum_places nu mu0), held places at their standard potential."""
        out = st.rate.exact
        for side, sign in ((st.reactants, -1), (st.products, 1)):
            for pname, cnt in side.items():
                out *= self.world.places[pname].exp_minus_mu0 ** (-sign * cnt)
        return out

    def product_activity(self, st: Step, p, *, continued: bool = False) -> Fraction | None:
        """The forward products' activities at p (the reverse channel's own draw)."""
        beta = self.beta[st.name]
        if any(b > v for b, v in zip(beta, p)):
            return None
        out = Fraction(1)
        r_b = 0
        for i, (b, v) in enumerate(zip(beta, p)):
            if not b:
                continue
            if self.mem[i]:
                out *= falling_factorial(v, b)
                r_b += b
            else:
                out *= Fraction(falling_factorial(v, b)) / self.Xp[i] ** b
        if r_b:
            P = self.N(p)
            den = falling_factorial(P - 1, r_b - 1) if continued else (
                falling_factorial(P - self.c, r_b) if P - self.c >= 0 else 0)
            if den == 0:
                return None
            out /= den
        for pname, b in st.products.items():
            pl = self.world.places[pname]
            if pl.held:
                out *= (pl.held_mM.exact / self.world.c0_mM.exact) ** b
        return out

    def continued_reverse(self, st: Step, p) -> RatExp:
        """The extinct boundary's reverse channel that empties the membrane: k- times the
        products' draw continued to 1/ff(N - 1, r_b - 1), with g = 1, and the regular-mixing
        activity coefficient exp(R(p) - R(n))."""
        nu = self.nu[st.name]
        n = tuple(a - d for a, d in zip(p, nu))
        act = self.product_activity(st, p, continued=True)
        if act is None:
            return ZERO
        return RatExp(self.k_minus(st) * act, self.regular(p) - self.regular(n))

    def products_rule(self, st: Step, p) -> RatExp:
        """a-(p) by the products' rule (§2.1), without F; equal to ``reverse`` (a theorem here)."""
        p = tuple(p)
        nu = self.nu[st.name]
        n = tuple(a - d for a, d in zip(p, nu))
        if any(v < 0 for v in n):
            return ZERO
        if self.conv.last_molecule == "extinct" and self.empties_membrane(st, p, -1):
            return self.continued_reverse(st, p)
        if self.conv.last_molecule == "extinct" and self.empties_membrane(st, n, +1):
            return ZERO
        if self.activity(st, n) is None:
            return ZERO
        m = self.common_state(st, n)
        E = self.extent(st, m)
        if E <= 0:
            return ZERO
        act = self.product_activity(st, p)
        if act is None:
            return ZERO
        return RatExp(self.k_minus(st) * act * E * self.factor(st, m), self.regular(p) - self.regular(n))

    # ---------------------------------------------------------------- boundary bookkeeping
    def one_way_forward(self, st: Step, n) -> bool:
        return self.conv.last_molecule == "extinct" and self.empties_membrane(st, tuple(n), +1)

    def one_way_reverse(self, st: Step, p) -> bool:
        return self.conv.last_molecule == "extinct" and self.empties_membrane(st, tuple(p), -1)
