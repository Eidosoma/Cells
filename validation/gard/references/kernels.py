"""The GARD exchange kernel in both forms, in float64 and in exact rationals.

Sources (numbers cited under D186; no text copied):

- Rate law: Segrè, Ben-Eli and Lancet 2000 (PNAS 97:4112, PMC18166), Eq. 4, and
  Gross et al. 2014 (BMC Evol Biol 14:265, PMC4357159), Eq. 2:
  dn_i/dt = (k_f rho_i N - k_b n_i) (1 + sum_j beta_ij n_j / N).
  beta_ij is the enhancement that member type j exerts on type i (2014, Methods).
- Single-event form: the preprint *Plastic heredity* v5.0 (doi:10.5281/zenodo.22799362),
  p. 10 and Appendix F: b_i(x) = 1 + (beta x)_i / N, a_i^+ = k_f rho_i N b_i,
  a_i^- = k_b x_i b_i, with k_f = 1e-2, k_b = 1e-4, rho_i = 1/100 held, 100 types,
  beta_ij = exp(-4 + 4 Z_ij) with the diagonal kept, founder of 40 distinct types.
- Pair-consistent form (derived here; GARD_DESIGN §2.3 names it): the leave
  x -> x - e_i carries the factor of the join it reverses, b_i(x - e_i). Then
  a_i^+(x) / a_i^-(x + e_i) = K_i rho_i N / (x_i + 1) with K_i = k_f,i / k_b,i, a
  ratio with no beta in it. That ratio equals pi(x + e_i) / pi(x) for
  pi(x) = (N - 1)! prod_i (K_i rho_i)^{x_i} / x_i!  (held reservoir),
  so detailed balance holds edge by edge for every beta.
- Closed world (finite reservoir): M_i molecules of type i in all, M_i - x_i of them free
  in volume V, rho_i = (M_i - x_i) / V. The ratio becomes theta_i N (M_i - x_i)/(x_i + 1),
  theta_i = k_f,i / (k_b,i V), and pi(x) = (N - 1)! prod_i theta_i^{x_i} C(M_i, x_i).

Boundary rule. The size-proportional join makes N = 0 absorbing, and the pair-consistent
leave of the last molecule would need b at the empty state, which is undefined. Three
rules are supported:
- ``last_molecule_stays`` disables leaves at N = 1 in both forms. The closed world and
  the kernel identities use it.
- ``extinction_uncatalysed`` is the engine's declared convention (17 November). The
  last molecule leaves at the bare k_b,i in both forms, the empty state is absorbing,
  Phi(empty) = ln pi(empty) = 0, and that leave books q = -ln(K_i rho_i).
- ``extinction`` (single-event only) lets the last molecule leave at k_b b_i(x), as the
  preprint's kernel would.
In the preprint's lineage regime (masses 40-80) no rule ever acts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Sequence

import numpy as np
from scipy.special import gammaln

SINGLE_EVENT = "single-event"
PAIR_CONSISTENT = "pair-consistent"
FORMS = (SINGLE_EVENT, PAIR_CONSISTENT)

LAST_MOLECULE_STAYS = "last_molecule_stays"
EXTINCTION = "extinction"
EXTINCTION_UNCATALYSED = "extinction_uncatalysed"
BOUNDARY_RULES = (LAST_MOLECULE_STAYS, EXTINCTION, EXTINCTION_UNCATALYSED)


def canonical_form(form: str) -> str:
    """Return the canonical name of a kernel form; refuse anything unknown."""
    aliases = {
        "single-event": SINGLE_EVENT,
        "single_event": SINGLE_EVENT,
        "published": SINGLE_EVENT,
        "pair-consistent": PAIR_CONSISTENT,
        "pair_consistent": PAIR_CONSISTENT,
    }
    try:
        return aliases[str(form)]
    except KeyError as exc:
        raise ValueError(f"unknown kernel form {form!r}; expected one of {FORMS}") from exc


@dataclass(frozen=True)
class HeldReservoir:
    """A held (chemostatted) reservoir: rho_i is constant (the preprint's supply)."""

    rho: np.ndarray

    def rho_at(self, x: np.ndarray) -> np.ndarray:
        return self.rho


@dataclass(frozen=True)
class ClosedReservoir:
    """A finite reservoir: M_i molecules of type i in all, free ones in volume V."""

    total: np.ndarray
    volume: float

    def rho_at(self, x: np.ndarray) -> np.ndarray:
        return (self.total - x) / self.volume


@dataclass(frozen=True)
class ExchangeLaw:
    """One world's exchange law in float64.

    ``beta[i, j]`` is the enhancement exerted by member type j on type i.
    ``k_join`` and ``k_leave`` are per-type basal constants (k_f and k_b).
    """

    beta: np.ndarray
    k_join: np.ndarray
    k_leave: np.ndarray
    reservoir: HeldReservoir | ClosedReservoir
    form: str
    boundary: str = LAST_MOLECULE_STAYS
    diag: np.ndarray = field(init=False, repr=False)

    def __post_init__(self) -> None:
        beta = np.ascontiguousarray(self.beta, dtype=np.float64)
        G = beta.shape[0]
        if beta.shape != (G, G):
            raise ValueError("beta must be square")
        object.__setattr__(self, "beta", beta)
        object.__setattr__(self, "k_join", _per_type(self.k_join, G, "k_join"))
        object.__setattr__(self, "k_leave", _per_type(self.k_leave, G, "k_leave"))
        object.__setattr__(self, "form", canonical_form(self.form))
        object.__setattr__(self, "diag", np.ascontiguousarray(np.diag(beta)))
        if self.boundary not in BOUNDARY_RULES:
            raise ValueError(f"unknown boundary rule {self.boundary!r}")
        if self.boundary == EXTINCTION and self.form == PAIR_CONSISTENT:
            raise ValueError("the pair-consistent leave of the last molecule is undefined")
        if np.any(beta < 0):
            raise ValueError("beta must be nonnegative")

    @property
    def n_types(self) -> int:
        return self.beta.shape[0]

    def with_form(self, form: str) -> "ExchangeLaw":
        return ExchangeLaw(self.beta, self.k_join, self.k_leave, self.reservoir, form, self.boundary)

    def with_beta(self, beta: np.ndarray) -> "ExchangeLaw":
        return ExchangeLaw(beta, self.k_join, self.k_leave, self.reservoir, self.form, self.boundary)


def _per_type(value, G: int, name: str) -> np.ndarray:
    arr = np.asarray(value, dtype=np.float64)
    if arr.ndim == 0:
        arr = np.full(G, float(arr))
    if arr.shape != (G,):
        raise ValueError(f"{name} must be a scalar or have one value per type")
    if np.any(arr <= 0):
        raise ValueError(f"{name} must be positive")
    return arr


def catalytic_factor(beta: np.ndarray, x: np.ndarray) -> np.ndarray:
    """b_i(x) = 1 + (beta x)_i / N, for N >= 1 (preprint p. 10)."""
    xf = np.asarray(x, dtype=np.float64)
    N = xf.sum()
    if N < 1:
        raise ValueError("the catalytic factor is undefined for an empty assembly")
    return 1.0 + (beta @ xf) / N


def propensities(law: ExchangeLaw, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Join and leave propensities (a^+, a^-) at integer state x, in float64."""
    x = np.asarray(x)
    xf = x.astype(np.float64)
    N = xf.sum()
    G = law.n_types
    if N < 1:
        return np.zeros(G), np.zeros(G)
    bx = law.beta @ xf
    b = 1.0 + bx / N
    rho = law.reservoir.rho_at(xf)
    a_plus = law.k_join * rho * N * b
    if N == 1 and law.boundary == LAST_MOLECULE_STAYS:
        return a_plus, np.zeros(G)
    if N == 1 and law.boundary == EXTINCTION_UNCATALYSED:
        return a_plus, law.k_leave * xf
    if law.form == SINGLE_EVENT:
        a_minus = law.k_leave * xf * b
    else:
        b_minus = 1.0 + (bx - law.diag) / (N - 1.0)
        a_minus = np.where(x > 0, law.k_leave * xf * b_minus, 0.0)
    return a_plus, a_minus


def log_weight(law: ExchangeLaw, x: np.ndarray) -> float:
    """ln pi~(x): the unnormalised product measure.

    Held:   ln[(N - 1)! prod_i (K_i rho_i)^{x_i} / x_i!],  K_i = k_join_i / k_leave_i.
    Closed: ln[(N - 1)! prod_i theta_i^{x_i} C(M_i, x_i)], theta_i = K_i / V.
    The empty assembly takes ln pi = 0 (the engine's Phi(empty) = 0).
    """
    x = np.asarray(x)
    N = int(x.sum())
    if N < 1:
        return 0.0
    K = law.k_join / law.k_leave
    res = law.reservoir
    if isinstance(res, HeldReservoir):
        return float(gammaln(N) + np.sum(x * np.log(K * res.rho)) - np.sum(gammaln(x + 1.0)))
    theta = K / res.volume
    M = res.total
    lc = gammaln(M + 1.0) - gammaln(x + 1.0) - gammaln(M - x + 1.0)
    return float(gammaln(N) + np.sum(x * np.log(theta)) + np.sum(lc))


def join_affinity(law: ExchangeLaw, x: np.ndarray) -> np.ndarray:
    """Declared affinity of each join x -> x + e_i: ln[pi(x + e_i) / pi(x)]."""
    xf = np.asarray(x, dtype=np.float64)
    N = xf.sum()
    K = law.k_join / law.k_leave
    rho = law.reservoir.rho_at(xf)
    with np.errstate(divide="ignore"):
        return np.log(K * rho * N / (xf + 1.0))


def event_heat(law: ExchangeLaw, x: np.ndarray, i: int, sign: int, props_x=None, props_y=None) -> float:
    """q = ln(w(x -> x') / w(x' -> x)) in k_BT: the event's booked heat (GARD_DESIGN §2.4).

    The last molecule's leave has no reverse (a join into an empty assembly has rate 0).
    It books ln pi(empty) - ln pi(x) = -ln(K_i rho_i), the engine's convention.
    """
    x = np.asarray(x)
    y = x.copy()
    y[i] += sign
    ap_x, am_x = propensities(law, x) if props_x is None else props_x
    ap_y, am_y = propensities(law, y) if props_y is None else props_y
    if sign > 0:
        return float(np.log(ap_x[i]) - np.log(am_y[i]))
    if int(y.sum()) == 0:
        return log_weight(law, y) - log_weight(law, x)
    return float(np.log(am_x[i]) - np.log(ap_y[i]))


# --------------------------------------------------------------------------- exact

@dataclass(frozen=True)
class ExactLaw:
    """The same law in exact rationals, for enumeration-scale checks."""

    beta: tuple[tuple[Fraction, ...], ...]
    k_join: tuple[Fraction, ...]
    k_leave: tuple[Fraction, ...]
    form: str
    rho: tuple[Fraction, ...] | None = None          # held reservoir
    total: tuple[int, ...] | None = None             # closed reservoir
    volume: Fraction | None = None
    boundary: str = LAST_MOLECULE_STAYS

    @staticmethod
    def make(beta, k_join, k_leave, form, *, rho=None, total=None, volume=None,
             boundary=LAST_MOLECULE_STAYS) -> "ExactLaw":
        G = len(beta)
        # Floats given as rates are read as their decimal repr (0.01 -> 1/100) so that
        # decimal parameters stay exact; beta entries keep their exact binary value.
        q = lambda v: Fraction(repr(float(v))) if isinstance(v, float) else Fraction(v)
        kj = tuple(q(k_join) for _ in range(G)) if np.ndim(k_join) == 0 else tuple(q(v) for v in k_join)
        kl = tuple(q(k_leave) for _ in range(G)) if np.ndim(k_leave) == 0 else tuple(q(v) for v in k_leave)
        b = tuple(tuple(Fraction(v) for v in row) for row in beta)
        if (rho is None) == (total is None):
            raise ValueError("give either a held rho or a closed total and volume")
        r = None if rho is None else (tuple(Fraction(rho) for _ in range(G)) if np.ndim(rho) == 0
                                      else tuple(Fraction(v) for v in rho))
        t = None if total is None else tuple(int(v) for v in total)
        v = None if volume is None else Fraction(volume)
        return ExactLaw(b, kj, kl, canonical_form(form), r, t, v, boundary)

    @property
    def n_types(self) -> int:
        return len(self.beta)

    def rho_at(self, x: Sequence[int]) -> tuple[Fraction, ...]:
        if self.rho is not None:
            return self.rho
        return tuple(Fraction(self.total[i] - x[i]) / self.volume for i in range(self.n_types))

    def b(self, x: Sequence[int]) -> tuple[Fraction, ...]:
        N = sum(x)
        if N < 1:
            raise ValueError("b is undefined for an empty assembly")
        return tuple(1 + Fraction(sum(self.beta[i][j] * x[j] for j in range(self.n_types)), N)
                     for i in range(self.n_types))

    def propensities(self, x: Sequence[int]) -> tuple[tuple[Fraction, ...], tuple[Fraction, ...]]:
        G = self.n_types
        N = sum(x)
        zero = tuple(Fraction(0) for _ in range(G))
        if N < 1:
            return zero, zero
        b = self.b(x)
        rho = self.rho_at(x)
        a_plus = tuple(self.k_join[i] * rho[i] * N * b[i] for i in range(G))
        if N == 1 and self.boundary == LAST_MOLECULE_STAYS:
            return a_plus, zero
        if N == 1 and self.boundary == EXTINCTION_UNCATALYSED:
            return a_plus, tuple(self.k_leave[i] * x[i] for i in range(G))
        if self.form == SINGLE_EVENT:
            a_minus = tuple(self.k_leave[i] * x[i] * b[i] for i in range(G))
        else:
            out = []
            for i in range(G):
                if x[i] == 0:
                    out.append(Fraction(0))
                    continue
                y = list(x)
                y[i] -= 1
                out.append(self.k_leave[i] * x[i] * self.b(y)[i])
            a_minus = tuple(out)
        return a_plus, a_minus

    def weight(self, x: Sequence[int]) -> Fraction:
        """pi~(x) exactly (unnormalised), N >= 1."""
        N = sum(x)
        w = Fraction(math.factorial(N - 1))
        for i in range(self.n_types):
            K = self.k_join[i] / self.k_leave[i]
            if self.rho is not None:
                w *= (K * self.rho[i]) ** x[i] / math.factorial(x[i])
            else:
                w *= (K / self.volume) ** x[i] * math.comb(self.total[i], x[i])
        return w


# ------------------------------------------------------------ preprint world data

def gard_beta(n_types: int, rng: np.random.Generator, A: float = -4.0, sigma: float = 4.0) -> np.ndarray:
    """beta_ij = exp(A + sigma Z_ij), Z standard normal, diagonal kept (preprint p. 10)."""
    return np.exp(A + sigma * rng.standard_normal((n_types, n_types)))


def gard_founder(n_types: int, mass: int, rng: np.random.Generator) -> np.ndarray:
    """A founder of ``mass`` distinct types drawn uniformly without replacement (App. F)."""
    x = np.zeros(n_types, dtype=np.int64)
    x[rng.choice(n_types, size=mass, replace=False)] = 1
    return x


PREPRINT = dict(n_types=100, k_join=1e-2, k_leave=1e-4, rho=1e-2, founder_mass=40,
                fission_mass=80, event_guard=40000, A=-4.0, sigma=4.0)
"""The preprint's common contract (p. 10 and Appendix F), cited as numbers."""
