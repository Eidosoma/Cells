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
- **Zero, cancelled and singular factors** (§0.2a as amended, §0.2b rule 8). Where a reactant is
  missing, both rates of the pair are zero. Where the membrane factor E(m)/ff(N - c, r) is 0/0 (the
  common state's membrane is empty while neither end state's is: a lone molecule changing form, two
  joining, or under ``extinct`` a channel whose result empties the membrane) it takes its
  continuous extension, 1/ff(N - 1, r - 1), under every token; detailed balance holds there as for
  every other pair. Where only the normaliser vanishes (``multinomial_less_one``, a membrane place
  on both sides, N = r) the rate is +inf: such a step is admitted only in a world declaring
  ``world_role: probe``, whose probes report +inf, and a run that reaches it stops ``stalled``.
- **The last molecule.** ``kept``: rate zero only for a pair whose step changes the membrane's count
  and one of whose end states has an empty membrane, so the membrane never empties and nothing else
  is frozen: a step in which the membrane takes no part fires at its own rate under every token, and
  a pool step at a probe state with an empty membrane fires at the pool's mass action (§0.2a as
  reworded by the lead, main bbcbec69, 18 November 2026; amendment 5). ``reversible`` (c = 0): the
  empty membrane is an ordinary state (E = 1 there). ``extinct`` (c = 1): a channel whose result
  empties the membrane fires at the pair rule's cancelled form, in either direction (k- for the last
  molecule's leave); the empty state is absorbing, so that channel is one-way and is excluded from
  every detailed-balance check, its rate checked against the cancelled form directly. Written
  through F with F_mem(empty) = 0 the same rate is a literal zero (``reverse_F``), which is an error.

**The reverse rate** is the pair rule on the reverse channel's own side, the products' rule (§2.1):
k- = k+ exp(Sum_places nu mu0) (held places at their standard potential), times the products'
activities at n', E(m) g(m), and the activity coefficient exp(R(n') - R(n)) of regular mixing,
cancelled where it is 0/0. Wherever the forward rate is finite and positive it equals the F path,
a+(n) exp(F(n') - F(n) - w), exactly: the membrane's ff(N - c, r) normalisations and the measure's
N!-ratio cancel against E(m) = N(m) - c + 1 for every order up to three on each side and under both
measures (the tests hold the two paths equal on every probe state).

**Planted forms** (each must be caught by the check README.md names):
- ``at_state_factor``: g at each direction's own state (E1's form);
- ``forward_only_catalysis``: g on the forward channel and 1 on the reverse;
- ``one_sided``: one step's reverse multiplied by exp(lam x_j(n')), with no reciprocal term in F
  (E2's lesson);
- ``power_propensity``: n^alpha in place of the falling factorial, the reverse still from F;
- ``normaliser_power``: N^r in place of ff(N - c, r) for the membrane draw;
- ``extent_offset``: E = N(m) whatever the measure;
- ``dropped_c0``: X = N_A V without c0, everywhere (a consistent engine with a wrong X);
- ``wrong_sign``: the reverse from exp(-(F(n') - F(n) - w));
- ``empty_m_zero``: the superseded reading of §0.2a, rate 0 wherever the common state's membrane
  is empty (amendment 4 plants it).
"""

from __future__ import annotations

import math
from fractions import Fraction

from .common import RecordFormatError
from .exact import ONE, ZERO, RatExp, falling_factorial
from .world import Conventions, Step, World, check_world_role

PLANTED_FORMS = ("at_state_factor", "forward_only_catalysis", "one_sided", "power_propensity",
                 "normaliser_power", "extent_offset", "dropped_c0", "wrong_sign", "empty_m_zero")


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
        check_world_role(world, conventions.condensed_measure)
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

    def extent(self, st: Step, m) -> Fraction:
        """E(m): X for a dilute locus; N(m) - c + 1 for the membrane."""
        if st.locus != "membrane":
            return self.X(st.locus)
        if self.planted == "extent_offset":
            return Fraction(self.N(m))
        return Fraction(self.N(m) - self.c + 1)

    def draw(self, st: Step, counts, coeff, m):
        """E(m) times one side's draw at ``counts`` (the firing state for the forward channel, the
        target state for the products' rule): 0, a Fraction, or INF.

        The membrane's part is E(m) prod ff(n_i, a_i)/ff(N - c, r). Where both E(m) and
        ff(N - c, r) vanish (0/0) the factor takes its continuous extension, E(m)/ff(N - 1, r) ->
        1/ff(N - 1, r - 1), under every token (§0.2a, the empty common state). Where only the
        normaliser vanishes the rate is +inf (§0.2b rule 8, a membrane place on both sides)."""
        num, r_mem, dil = 1, 0, Fraction(1)
        for i, a in enumerate(coeff):
            if not a:
                continue
            if counts[i] < a:
                return 0
            if self.mem[i]:
                num *= self._ff(counts[i], a)
                r_mem += a
            else:
                dil *= Fraction(self._ff(counts[i], a)) / self.Xp[i] ** a
        E = self.extent(st, m)
        if st.locus != "membrane" or r_mem == 0:
            return dil * num * E
        N = self.N(counts)
        if self.planted == "normaliser_power":
            den = N ** r_mem
        else:
            den = falling_factorial(N - self.c, r_mem) if N - self.c >= 0 else 0
        if den:
            return dil * num * E / den
        if E == 0:
            if self.planted == "empty_m_zero":
                return 0
            return dil * num / falling_factorial(N - 1, r_mem - 1)
        return INF

    def held_activity(self, side: dict) -> Fraction:
        out = Fraction(1)
        for pname, a in side.items():
            pl = self.world.places[pname]
            if pl.held:
                out *= (pl.held_mM.exact / self.world.c0_mM.exact) ** a
        return out

    def end_empty(self, st: Step, n, p) -> bool:
        return st.locus == "membrane" and (self.N(n) == 0 or self.N(p) == 0)

    def _kept_zero(self, st: Step, n, p) -> bool:
        """``kept`` gives rate zero only to a pair whose step changes the membrane's count and one of
        whose end states has an empty membrane (main bbcbec69). A pool step is never zeroed, nor a
        step in which the membrane takes no part."""
        return (self.conv.last_molecule == "kept" and self.end_empty(st, n, p)
                and self.N(n) != self.N(p))

    def forward(self, st: Step, n) -> RatExp:
        """a+(n): the rate of n -> n + nu (zero when impossible; INF when singular)."""
        n = tuple(n)
        nu = self.nu[st.name]
        p = tuple(a + d for a, d in zip(n, nu))
        if any(v < 0 for v in p) or any(a > v for a, v in zip(self.alpha[st.name], n)):
            return ZERO
        if self._kept_zero(st, n, p):
            return ZERO
        m = tuple(min(a, b) for a, b in zip(n, p))
        if self.planted == "empty_m_zero" and st.locus == "membrane" and self.N(m) == 0:
            return ZERO
        d = self.draw(st, n, self.alpha[st.name], m)
        if d is INF:
            return INF
        if d == 0:
            return ZERO
        g = self.factor(st, n if self.planted == "at_state_factor" else m)
        return RatExp(st.rate.exact * g * d * self.held_activity(st.reactants))

    def reverse_F(self, st: Step, p) -> RatExp:
        """a-(p) written through F: a+(n) exp(F(p) - F(n) - w). Equal to ``reverse`` on every pair
        whose forward rate is finite and positive; a literal zero at the extinct boundary."""
        p = tuple(p)
        n = tuple(a - d for a, d in zip(p, self.nu[st.name]))
        if any(v < 0 for v in n):
            return ZERO
        f = self.forward(st, n)
        if f is INF:
            return INF
        if f.is_zero():
            return ZERO
        e = self.exp_delta(st, n)
        return f * (ONE / e if self.planted == "wrong_sign" else e)

    def reverse(self, st: Step, p) -> RatExp:
        """a-(p): the rate of p -> p - nu, by the pair rule on the reverse channel's own side (the
        products' rule), cancelled where it is 0/0. Planted forms that model an engine computing
        its reverse from its own (wrong) forward use the F path."""
        p = tuple(p)
        if self.planted in ("power_propensity", "normaliser_power", "extent_offset", "dropped_c0", "wrong_sign"):
            return self.reverse_F(st, p)
        nu = self.nu[st.name]
        n = tuple(a - d for a, d in zip(p, nu))
        if any(v < 0 for v in n) or any(a > v for a, v in zip(self.alpha[st.name], n)):
            return ZERO
        if self._kept_zero(st, n, p):
            return ZERO
        m = tuple(min(a, b) for a, b in zip(n, p))
        if self.planted == "empty_m_zero" and st.locus == "membrane" and self.N(m) == 0:
            return ZERO
        d = self.draw(st, p, self.beta[st.name], m)
        if d is INF:
            return INF
        if d == 0:
            return ZERO
        if self.planted == "at_state_factor":
            g = self.factor(st, p)
        elif self.planted == "forward_only_catalysis":
            g = Fraction(1)
        else:
            g = self.factor(st, m)
        out = RatExp(self.k_minus(st) * g * d * self.held_activity(st.products), self.regular(p) - self.regular(n))
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

    def products_rule(self, st: Step, p) -> RatExp:
        """The products' rule (the honest ``reverse``), kept under its old name for the tests."""
        return Law(self.world, self.conv).reverse(st, p) if self.planted else self.reverse(st, p)

    # ---------------------------------------------------------------- boundary bookkeeping
    def one_way_forward(self, st: Step, n) -> bool:
        """Under ``extinct``: a forward channel whose result empties the membrane (no reverse)."""
        n = tuple(n)
        p = tuple(a + d for a, d in zip(n, self.nu[st.name]))
        return (self.conv.last_molecule == "extinct" and st.locus == "membrane" and self.N(n) > 0
                and self.N(p) == 0)

    def one_way_reverse(self, st: Step, p) -> bool:
        """Under ``extinct``: a reverse channel whose result empties the membrane (no reverse)."""
        p = tuple(p)
        n = tuple(a - d for a, d in zip(p, self.nu[st.name]))
        return (self.conv.last_molecule == "extinct" and st.locus == "membrane" and self.N(p) > 0
                and self.N(n) == 0)

    def singular(self, st: Step, n) -> bool:
        return self.forward(st, n) is INF


class _Infinite:
    """+inf, the singular rate of §0.2b rule 8 (reported by a probe, never fired)."""

    def is_zero(self) -> bool:
        return False

    def is_one(self) -> bool:
        return False

    def log(self) -> float:
        return math.inf

    def __float__(self) -> float:
        return math.inf

    def __repr__(self) -> str:
        return "INF"


INF = _Infinite()
