"""The exact law of (d)'s worlds without geometry, its planted forms, and the fuel parser.

**The law is OL1's, unchanged** (``laws.Law``, written from the engine note's §0.1 and §2.1-2.4).
It already carries everything option (d) adds (fuel note §1, "Fuel-to-waste cycles" and "Mass
action with held activities"):
- a pool step with held reactants or products: a+ = k X prod_finite ff(n, alpha)/X^alpha
  prod_held (c_h/c0)^alpha_h, and the reverse from F, with held activities on the products' side;
- reservoir work w = -Sum_held nu_h mu_h, mu_h = mu0_h + ln(c_h/c0), booked by the forward event
  (fuel note §5 check 1);
- the core step B + L -> 2 L, with L on both sides: its extent on the common state m is
  N(m) - c + 1 = N(n) under ``multinomial`` (c = 0), and its factor g(m) = 1 + beta x_L(m) is the
  same for both directions (engine note §2.4, the pair-consistent form);
- a finite fuel's free energy inside F, so that burning it lowers F (fuel note §1, "Stored energy").

Only (multinomial, kept) is probed (D215; the core step is singular under multinomial_less_one
outside probe worlds, engine note §0.2b rule 8).

**Planted forms** (each must fail the check README.md names; every planted engine computes its
reverse from its own forward and its own F, as the honest one does):
- ``no_reservoir_work``: the reverse from a+ e^(Delta F), with w left out (fuel note §5 check 1);
- ``work_sign``: the reverse from a+ e^(Delta F + w), the drive of the wrong sign (§5 check 3);
- ``held_activity_dropped``: the held places at c0, so mu_h = mu0_h (the reservoir pays its standard
  potential only);
- ``extent_n_minus_r``: a membrane step's extent N(n) - r + 1, counting every reactant molecule as
  consumed; it equals N(m) + 1 except where a species is on both sides, as in the core step;
- ``fuel_term_dropped``: the finite fuel's and waste's terms left out of F (§5 check 2), so the
  reverse of the fuel step misses e^(-(F_fuel(n') - F_fuel(n)));
- and OL1's ``at_state_factor`` (the factor at each direction's own state, E1's form, §5 check 4)
  and ``forward_only_catalysis``, inherited.

**The fuel parser** (fuel note §6, L1, the first builder's refusal): a transition-state factor on a
step whose places all lie in the pool is refused. A pool-only step has no membrane at its common
state, so the factor has no declared meaning there (fuel note §1, "Catalysis on fuel steps"). The
check runs after OL1's parse, so every earlier refusal keeps its message.
"""

from __future__ import annotations

import json
import math
from fractions import Fraction
from pathlib import Path

from ..common import RecordFormatError
from ..exact import ZERO, RatExp
from ..laws import INF, PLANTED_FORMS, Law
from ..world import Conventions, Step, World, parse_world

PHYSICAL = Conventions(condensed_measure="multinomial", last_molecule="kept")
FUEL_PLANTED = ("no_reservoir_work", "work_sign", "held_activity_dropped", "extent_n_minus_r", "fuel_term_dropped")
FUEL_PLACES = ("F@pool", "W@pool")


def pool_only(world: World, st: Step) -> bool:
    return all(world.places[p].phase == "pool" for p in list(st.reactants) + list(st.products))


def check_fuel_world(world: World) -> None:
    """L1: a factor entry on a step whose places all lie in the pool is refused (second pass)."""
    for st in world.steps:
        if st.catalysts and pool_only(world, st):
            raise RecordFormatError(f"{world.name}: step {st.name} has a transition_state_factor entry, but its places "
                                    "all lie in the pool; a factor on a pool-only step is refused (fuel note §6, L1)")


def parse_fuel_world(doc: dict) -> World:
    world = parse_world(doc)
    check_fuel_world(world)
    return world


def load_fuel_world(path) -> World:
    return parse_fuel_world(json.loads(Path(path).read_text()))


class FuelLaw(Law):
    """OL1's law with the fuel's planted forms. ``planted`` may be one of ``FUEL_PLANTED`` or any of
    OL1's ``PLANTED_FORMS``."""

    def __init__(self, world: World, conventions: Conventions = PHYSICAL, planted: str | None = None,
                 planted_params: dict | None = None):
        if planted is not None and planted not in FUEL_PLANTED + PLANTED_FORMS:
            raise ValueError(f"unknown planted form {planted!r}")
        self.fuel_planted = planted if planted in FUEL_PLANTED else None
        super().__init__(world, conventions, None if planted in FUEL_PLANTED else planted, planted_params)
        self.planted_label = planted
        self.fuel_idx = [i for i, p in enumerate(world.finite) if p.name in FUEL_PLACES]

    # ------------------------------------------------------------------ reservoir work
    def held_mu(self, place: str) -> float:
        pl = self.world.places[place]
        return pl.mu0_kT + math.log(float(pl.held_mM.exact / self.world.c0_mM.exact))

    def work_float(self, st: Step) -> float:
        """w = -Sum_h nu_h mu_h for the forward event (k_BT)."""
        return self.reservoir_work(st)

    # ------------------------------------------------------------------ planted helpers
    def _r_mem(self, st: Step) -> int:
        return sum(a for a, m in zip(self.alpha[st.name], self.mem) if m and a)

    def _extent_ratio(self, st: Step, n) -> Fraction:
        """(N(n) - r + 1 - c) / (N(m) + 1 - c) for a membrane step, the planted extent's factor."""
        if st.locus != "membrane":
            return Fraction(1)
        n = tuple(n)
        p = tuple(a + d for a, d in zip(n, self.nu[st.name]))
        m = tuple(min(a, b) for a, b in zip(n, p))
        honest = self.N(m) - self.c + 1
        planted = self.N(n) - self._r_mem(st) + 1 - self.c
        if honest <= 0:
            return Fraction(1)
        return Fraction(max(planted, 0), honest)

    def _fuel_weight(self, n) -> Fraction:
        """exp(-F_fuel(n)): the finite fuel and waste places' terms of F."""
        out = Fraction(1)
        for i in self.fuel_idx:
            v = n[i]
            out *= (self.em[i] * self.Xp[i]) ** v / math.factorial(v)
        return out

    # ------------------------------------------------------------------ rates
    def forward(self, st: Step, n) -> RatExp:
        f = super().forward(st, n)
        if self.fuel_planted is None or f is INF or f.is_zero():
            return f
        if self.fuel_planted == "held_activity_dropped":
            ha = self.held_activity(st.reactants)
            return f / RatExp(ha) if ha != 1 else f
        if self.fuel_planted == "extent_n_minus_r":
            ratio = self._extent_ratio(st, n)
            return ZERO if ratio == 0 else f * RatExp(ratio)
        return f

    def reverse(self, st: Step, p) -> RatExp:
        if self.fuel_planted is None:
            return super().reverse(st, p)
        p = tuple(p)
        n = tuple(a - d for a, d in zip(p, self.nu[st.name]))
        if any(v < 0 for v in n):
            return ZERO
        f = self.forward(st, n)
        if f is INF:
            return INF
        if f.is_zero():
            return ZERO
        e = self.exp_delta(st, n)          # exp(F(p) - F(n) - w), honest
        emw = RatExp(self.exp_minus_w(st))  # exp(-w)
        if self.fuel_planted == "no_reservoir_work":
            e = e / emw
        elif self.fuel_planted == "work_sign":
            e = e / emw / emw
        elif self.fuel_planted == "held_activity_dropped":
            # the planted engine's w uses mu0_h only: exp(-w') = prod_h exp(nu_h mu0_h)
            e = e / emw * RatExp(self._exp_minus_w_standard(st))
        elif self.fuel_planted == "fuel_term_dropped":
            e = e * RatExp(self._fuel_weight(p) / self._fuel_weight(n))
        return f * e

    def _exp_minus_w_standard(self, st: Step) -> Fraction:
        out = Fraction(1)
        for h, v in self.nu_h[st.name].items():
            out *= (1 / self.world.places[h].exp_minus_mu0) ** v
        return out
