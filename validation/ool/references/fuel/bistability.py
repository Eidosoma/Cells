"""Row OL4-8: §2.3's reduced model in closed form, exactly, with its nulls (fuel note §2.3 and
§3 (d); the lead's ruling L6).

**The model** (note §2.3). One membrane holds the activated block B and the spent form S at
fractions x_B and x_S, set by fast exchange with the pool, and two amphiphiles at x_1 and x_2,
T = x_1 + x_2. Steps: B + L_i <-> 2 L_i (forward k1, factor g_i = 1 + beta x_i, reverse k1 e^Delta1
g_i) and L_i <-> S (forward k2, reverse k2 e^Delta2). Here E1 = e^Delta1 and E2 = e^Delta2. The net
rate of making L_i per molecule is

    r(x_i) = k1 (1 + beta x_i)(x_B - E1 x_i) - k2 (1 - E2 x_S/x_i),

and the share f = x_1/T moves as df/dt = f (1 - f)(r(x_1) - r(x_2)) (growth dilutes every fraction
alike, so it drops out of f).

**The closed form (derived here).** Subtracting the two rates,

    r(x_1) - r(x_2) = (x_1 - x_2) [k1 C - k2 E2 x_S/(x_1 x_2)],   C = beta x_B - E1 (1 + beta T).

The even mixture f = 1/2 is a fixed point; it is unstable exactly when the bracket is positive at
x_1 x_2 = T^2/4, that is

    beta x_B > E1 (1 + beta T) + 4 (k2/k1) E2 x_S / T^2      (note §2.3, the condition),

and then the asymmetric fixed points solve x_1 x_2 = K/C with K = (k2/k1) E2 x_S:
f_+- = (1 +- sqrt(1 - 4K/(C T^2)))/2. Both are stable (the bracket changes sign from + to - across
them), and the boundaries f = 0, 1 repel whenever x_S > 0 (df/dt -> +-k2 E2 x_S/T there). Otherwise
f = 1/2 is the only fixed point in (0, 1), and it is stable.

**The drives** (note §2.3). A = ln(x_B/x_S) - (Delta1 + Delta2), T_eq = 2 E2 x_S, rho = T/T_eq.
Dividing the condition by beta E1 E2 x_S gives e^A > e^{A*},
    e^{A*} = 2 rho + 2/(beta T_eq) + 4 (k2/k1)/(beta E1 rho^2 T_eq^2),
an exact comparison of rationals.

**The nulls, in closed form.**
- **True equilibrium** (A = 0, rho = 1): x_B = E1 E2 x_S and T = 2 E2 x_S give
  C = -E1 (1 + beta E2 x_S) < 0, so one composition, for every beta >= 0.
- **beta = 0:** C = -E1 < 0, so one composition.
- **The dividing null** (L6: A = 0 with 1/2 <= rho < 1): C = E1 [beta E2 x_S (1 - 2 rho) - 1] < 0, so
  one composition; and at f = 1/2 the growth rate is
      gamma = r(T/2) = (1 - rho) [k1 (1 + beta T/2) E1 E2 x_S + k2/rho] > 0,
  so the vesicle grows (and can divide) while holding one composition.
- **(d0)** (A = 0, rho < 1/2): two compositions exactly when
  E1 [beta E2 x_S (1 - 2 rho) - 1] rho^2 E2 x_S > k2/k1, which holds for large enough beta; gamma > 0
  at f = 1/2 as above, since rho < 1.
Here gamma = f r(x_1) + (1 - f) r(x_2) is the amphiphiles' net growth per molecule, the membrane's
growth rate when x_B and x_S are held (it reproduces the note's C4 value, gamma = 1.06).

**The independent count.** The number and stability of the fixed points is also found from the raw
rates, without the factorisation: P(f) = (r(x_1) - r(x_2)) x_1 x_2, with x_1 = fT and
x_2 = (1 - f)T, is a polynomial of degree at most 4 with rational coefficients and the sign of
df/dt on (0, 1). Sturm's theorem counts its distinct roots in (0, 1); each is isolated in a
rational interval and classified by the signs of P at the ends (+ then - is stable). Exact.

**Self-tests: the note's own numbers** (§2.3): C4 (Delta1 = Delta2 = 0, x_B = x_S = 0.45,
T = 0.1, k2/k1 = 0.01, beta = 20): f = 0.082 and 0.918, gamma = 1.06; C5's A* = 6.6 k_BT at
beta = 2, rho = 4 and 3.4 at beta = 64; on the zero-affinity line at rho = 1/4 two compositions
need beta >= 6.6e5; in the feed regime at rho = 1/9 they need beta >= 8. The note gives C4b's
property (a fuel-driven set whose even mixture neither grows nor shrinks) but not its parameters,
so ``constructed_c4b`` is a set constructed here with that property, labelled as such.

Planted closed forms (each must disagree with the raw count on the registered sample): 2 in place
of 4; T in place of T^2; the E1 term of C without its 1 (C = beta x_B - E1 beta T).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, replace
from fractions import Fraction as Fr

SAMPLE_SEED = 2026112001
SAMPLE_SIZE = 4000
PLANTED = ("two_for_four", "T_for_T2", "drop_E1_one")


@dataclass(frozen=True)
class Reduced:
    """The reduced model's parameters, exact. E1 = e^Delta1, E2 = e^Delta2."""

    beta: Fr
    xB: Fr
    xS: Fr
    T: Fr
    k1: Fr
    k2: Fr
    E1: Fr
    E2: Fr

    def __post_init__(self):
        for k in ("xB", "xS", "T", "k1", "k2", "E1", "E2"):
            if getattr(self, k) <= 0:
                raise ValueError(f"{k} must be positive")
        if self.beta < 0:
            raise ValueError("the reduced model's catalysis has beta >= 0")
        if self.xB + self.xS + self.T > 1:
            raise ValueError("membrane fractions exceed 1")

    @property
    def C(self) -> Fr:
        return self.beta * self.xB - self.E1 * (1 + self.beta * self.T)

    @property
    def K(self) -> Fr:
        return self.k2 / self.k1 * self.E2 * self.xS

    @property
    def T_eq(self) -> Fr:
        return 2 * self.E2 * self.xS

    @property
    def rho(self) -> Fr:
        return self.T / self.T_eq

    @property
    def exp_A(self) -> Fr:
        return self.xB / (self.xS * self.E1 * self.E2)

    def exp_A_star(self) -> Fr | None:
        if self.beta == 0:
            return None
        rho, Te = self.rho, self.T_eq
        return 2 * rho + 2 / (self.beta * Te) + 4 * (self.k2 / self.k1) / (self.beta * self.E1 * rho ** 2 * Te ** 2)

    @property
    def A(self) -> float:
        return math.log(self.exp_A)

    def A_star(self) -> float | None:
        e = self.exp_A_star()
        return None if e is None else math.log(e)


# ---------------------------------------------------------------------------- rates

def r(p: Reduced, x: Fr) -> Fr:
    """The net making of an amphiphile per molecule at fraction x (exact)."""
    return p.k1 * (1 + p.beta * x) * (p.xB - p.E1 * x) - p.k2 * (1 - p.E2 * p.xS / x)


def dfdt(p: Reduced, f: Fr) -> Fr:
    return f * (1 - f) * (r(p, f * p.T) - r(p, (1 - f) * p.T))


def gamma(p: Reduced, f) -> float:
    """The amphiphiles' growth per molecule, f r(x_1) + (1 - f) r(x_2), at a share f (float ok)."""
    if isinstance(f, Fr):
        return float(f * r(p, f * p.T) + (1 - f) * r(p, (1 - f) * p.T))
    x1, x2 = f * float(p.T), (1 - f) * float(p.T)

    def rf(x):
        return float(p.k1) * (1 + float(p.beta) * x) * (float(p.xB) - float(p.E1) * x) - float(p.k2) * (
            1 - float(p.E2) * float(p.xS) / x)
    return f * rf(x1) + (1 - f) * rf(x2)


# ---------------------------------------------------------------------------- the closed form

def bistable(p: Reduced, planted: str | None = None) -> bool:
    """§2.3's condition, exactly (with a planted variant for the controls)."""
    C, K, T = p.C, p.K, p.T
    if planted == "drop_E1_one":
        C = p.beta * p.xB - p.E1 * p.beta * T
    if planted == "two_for_four":
        return C > 0 and C * T * T > 2 * K
    if planted == "T_for_T2":
        return C > 0 and C * T > 4 * K
    return C > 0 and C * T * T > 4 * K


def closed_form(p: Reduced) -> dict:
    """The fixed points and their stability from the closed form; f_+- as floats with the exact
    discriminant D = 1 - 4K/(C T^2)."""
    if bistable(p):
        D = 1 - 4 * p.K / (p.C * p.T * p.T)
        s = math.sqrt(float(D))
        lo, hi = (1 - s) / 2, (1 + s) / 2
        return dict(bistable=True, discriminant=D, stable=[lo, hi], unstable=[0.5],
                    gamma_stable=[gamma(p, lo), gamma(p, hi)], gamma_even=float(r(p, p.T / 2)))
    return dict(bistable=False, discriminant=None, stable=[0.5], unstable=[],
                gamma_stable=[float(r(p, p.T / 2))], gamma_even=float(r(p, p.T / 2)))


# ---------------------------------------------------------------------------- polynomials and Sturm

def _trim(a: list) -> list:
    a = list(a)
    while len(a) > 1 and a[-1] == 0:
        a.pop()
    return a


def padd(a, b):
    n = max(len(a), len(b))
    return _trim([(a[i] if i < len(a) else 0) + (b[i] if i < len(b) else 0) for i in range(n)])


def pscale(a, c):
    return _trim([c * x for x in a])


def pmul(a, b):
    out = [Fr(0)] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            out[i + j] += x * y
    return _trim(out)


def peval(a, x):
    out = Fr(0)
    for c in reversed(a):
        out = out * x + c
    return out


def pderiv(a):
    return _trim([i * a[i] for i in range(1, len(a))]) if len(a) > 1 else [Fr(0)]


def pdivmod(a, b):
    """Quotient and remainder of polynomials with Fraction coefficients (lowest degree first)."""
    a, b = list(_trim(a)), _trim(b)
    if len(b) == 1 and b[0] == 0:
        raise ZeroDivisionError("polynomial division by zero")
    q = [Fr(0)] * max(len(a) - len(b) + 1, 1)
    while len(a) >= len(b) and not (len(a) == 1 and a[0] == 0):
        k = len(a) - len(b)
        c = a[-1] / b[-1]
        q[k] = c
        for i, y in enumerate(b):
            a[i + k] -= c * y
        a.pop()                                    # the leading term is now exactly zero
        a = _trim(a) if a else [Fr(0)]
    return _trim(q), a


def pgcd(a, b):
    a, b = _trim(a), _trim(b)
    while not (len(b) == 1 and b[0] == 0):
        a, b = b, pdivmod(a, b)[1]
    return pscale(a, 1 / a[-1])


def sturm_chain(p):
    chain = [_trim(p), pderiv(p)]
    while True:
        rem = pdivmod(chain[-2], chain[-1])[1]
        if len(rem) == 1 and rem[0] == 0:
            return chain
        chain.append(pscale(rem, Fr(-1)))


def sign_changes(chain, x) -> int:
    vals = [v for v in (peval(c, x) for c in chain) if v != 0]
    return sum(1 for a, b in zip(vals, vals[1:]) if (a > 0) != (b > 0))


def isolate(P) -> list:
    """Disjoint rational intervals (a, b) in (0, 1), each holding exactly one distinct root of P,
    with P non-zero at both ends (Sturm's theorem on P's square-free part)."""
    Q = pdivmod(P, pgcd(P, pderiv(P)))[0]
    chain = sturm_chain(Q)

    def count(a, b):
        return sign_changes(chain, a) - sign_changes(chain, b)

    if peval(Q, Fr(0)) == 0 or peval(Q, Fr(1)) == 0:
        raise ValueError("a root at the boundary")
    out, work = [], [(Fr(0), Fr(1))]
    while work:
        a, b = work.pop()
        k = count(a, b)
        if k == 0:
            continue
        if k == 1:
            out.append((a, b))
            continue
        m = (a + b) / 2
        if peval(Q, m) == 0:
            d = (b - a) / 4
            while count(m - d, m + d) != 1 or peval(Q, m - d) == 0 or peval(Q, m + d) == 0:
                d /= 2
            out.append((m - d, m + d))
            work += [(a, m - d), (m + d, b)]
        else:
            work += [(a, m), (m, b)]
    return sorted(out)


def raw_polynomial(p: Reduced) -> list:
    """P(f) = (r(x_1) - r(x_2)) x_1 x_2 from the raw rates, as coefficients in f."""
    T = p.T
    x1 = [Fr(0), T]                 # f T
    x2 = [T, -T]                    # (1 - f) T

    def r_times_x(x):
        # k1 (1 + beta x)(xB - E1 x) x - k2 (x - E2 xS)
        a = pmul(pmul(padd([Fr(1)], pscale(x, p.beta)), padd([p.xB], pscale(x, -p.E1))), x)
        b = pscale(padd(x, [-p.E2 * p.xS]), p.k2)
        return padd(pscale(a, p.k1), pscale(b, Fr(-1)))

    return padd(pmul(r_times_x(x1), x2), pscale(pmul(r_times_x(x2), x1), Fr(-1)))


def raw_count(p: Reduced) -> dict:
    """The fixed points of df/dt in (0, 1) and their stability, from the raw polynomial. P(0) =
    k2 E2 x_S T > 0 and P(1) < 0, so neither boundary is a root."""
    P = raw_polynomial(p)
    if len(P) == 1 and P[0] == 0:
        raise ValueError("df/dt vanishes identically")
    roots = []
    for a, b in isolate(P):
        left, right = peval(P, a), peval(P, b)
        roots.append(dict(interval=(a, b), at=float((a + b) / 2), stable=bool(left > 0 > right)))
    return dict(fixed_points=len(roots), stable=sum(1 for x in roots if x["stable"]), roots=roots)


def agrees(p: Reduced, planted: str | None = None) -> bool:
    """The closed form's verdict (two stable states or one) against the raw count."""
    return (raw_count(p)["stable"] == 2) == bistable(p, planted)


# ---------------------------------------------------------------------------- samples and nulls

def _rand_fr(rng: random.Random, lo: int, hi: int, den: int = 64) -> Fr:
    return Fr(rng.randint(lo, hi), den)


def sample(n: int = SAMPLE_SIZE, seed: int = SAMPLE_SEED) -> list:
    """Registered random sets: beta = 2^u with u in [0, 7] (and 0 one time in ten), fractions on a
    1/256 grid with x_B + x_S + T <= 1, E1 and E2 powers of 2 from 1/64 to 4, k2/k1 = 2^v with v in
    [-7, 2]."""
    rng = random.Random(seed)
    out = []
    while len(out) < n:
        beta = Fr(0) if rng.random() < 0.1 else Fr(2) ** rng.randint(0, 7) * Fr(rng.randint(64, 127), 64)
        a, b, c = (Fr(rng.randint(1, 254), 256) for _ in range(3))
        if a + b + c > 1:
            continue
        E1 = Fr(2) ** rng.randint(-6, 2)
        E2 = Fr(2) ** rng.randint(-6, 2)
        k2 = Fr(2) ** rng.randint(-7, 2)
        out.append(Reduced(beta=beta, xB=a, xS=b, T=c, k1=Fr(1), k2=k2, E1=E1, E2=E2))
    return out


def on_line(p: Reduced, rho: Fr) -> Reduced | None:
    """The same set moved to zero affinity (x_B = E1 E2 x_S) at supersaturation rho, if it fits."""
    xB, T = p.E1 * p.E2 * p.xS, rho * 2 * p.E2 * p.xS
    if xB + p.xS + T > 1:
        return None
    return replace(p, xB=xB, T=T)


def nulls(samples: list, seed: int = SAMPLE_SEED + 1) -> dict:
    """Every null on the sample: true equilibrium, beta = 0, and the dividing null at rho in
    [1/2, 1) (with gamma > 0 at the even mixture), each by the closed form and the raw count."""
    rng = random.Random(seed)
    res = dict(equilibrium=[0, 0], beta0=[0, 0], dividing=[0, 0], dividing_gamma_positive=[0, 0])
    for p in samples:
        q = on_line(p, Fr(1))
        if q is not None:
            res["equilibrium"][0] += 1
            res["equilibrium"][1] += int(bistable(q) or raw_count(q)["stable"] != 1 or r(q, q.T / 2) != 0)
        q = replace(p, beta=Fr(0))
        res["beta0"][0] += 1
        res["beta0"][1] += int(bistable(q) or raw_count(q)["stable"] != 1)
        rho = Fr(1, 2) + Fr(rng.randint(0, 255), 512)
        q = on_line(p, rho)
        if q is not None:
            res["dividing"][0] += 1
            res["dividing"][1] += int(bistable(q) or raw_count(q)["stable"] != 1)
            res["dividing_gamma_positive"][0] += 1
            res["dividing_gamma_positive"][1] += int(not r(q, q.T / 2) > 0)
    return {k: dict(sets=v[0], failures=v[1]) for k, v in res.items()}


def check_sample(samples: list, planted: str | None = None) -> dict:
    disagree = [k for k, p in enumerate(samples) if not agrees(p, planted)]
    return dict(sets=len(samples), bistable=sum(1 for p in samples if bistable(p)), disagreements=len(disagree),
                first=disagree[:5], planted=planted)


def check_A_star(samples: list) -> dict:
    """bistable <=> e^A > e^{A*} on every set with beta > 0 (exact)."""
    bad = [k for k, p in enumerate(samples) if p.beta > 0 and bistable(p) != (p.exp_A > p.exp_A_star())]
    return dict(sets=sum(1 for p in samples if p.beta > 0), disagreements=len(bad), first=bad[:5])


# ---------------------------------------------------------------------------- the note's numbers

def c4() -> Reduced:
    """C4 (note §2.3): Delta1 = Delta2 = 0, x_B = x_S = 0.45, T = 0.1, k2/k1 = 0.01, beta = 20."""
    return Reduced(beta=Fr(20), xB=Fr(9, 20), xS=Fr(9, 20), T=Fr(1, 10), k1=Fr(1), k2=Fr(1, 100), E1=Fr(1),
                   E2=Fr(1))


def c5_A_star(beta, rho) -> float:
    """C5's regime (note §2.3): e^Delta1 = e^Delta2 = 1/8, x_S = 1/20, k2/k1 = 1/10, T_eq = 1/80."""
    E, xS, k = Fr(1, 8), Fr(1, 20), Fr(1, 10)
    Te = 2 * E * xS
    beta, rho = Fr(beta), Fr(rho)
    return math.log(2 * rho + 2 / (beta * Te) + 4 * k / (beta * E * rho ** 2 * Te ** 2))


def zero_affinity_beta_threshold(E1: Fr, E2: Fr, xS: Fr, k2_over_k1: Fr, rho: Fr) -> Fr:
    """On the zero-affinity line, two compositions need beta above this value (exact), from
    E1 [beta E2 xS (1 - 2 rho) - 1] rho^2 E2 xS > k2/k1 (rho < 1/2)."""
    if rho >= Fr(1, 2):
        raise ValueError("no threshold at rho >= 1/2: one composition for every beta")
    return (k2_over_k1 / (E1 * rho ** 2 * E2 * xS) + 1) / (E2 * xS * (1 - 2 * rho))


def constructed_c4b() -> Reduced:
    """Constructed here (not the note's C4b, whose parameters the note does not give): a
    fuel-driven set whose even mixture neither grows nor shrinks, r(T/2) = 0 exactly, and which
    holds two compositions. E1 = E2 = 1/8, x_S = 1/20, T = 1/2, k1 = k2 = 1, beta = 32, and x_B solves
    (1 + beta T/2)(x_B - E1 T/2) = 1 - 2 E2 x_S/T: x_B = 67/480 (A = 5.19 k_BT)."""
    return Reduced(beta=Fr(32), xB=Fr(67, 480), xS=Fr(1, 20), T=Fr(1, 2), k1=Fr(1), k2=Fr(1), E1=Fr(1, 8),
                   E2=Fr(1, 8))


def reproductions() -> dict:
    p = c4()
    cf = closed_form(p)
    q = constructed_c4b()
    cq = closed_form(q)
    return dict(
        c4=dict(stable=cf["stable"], gamma=cf["gamma_stable"], rho=float(p.rho), A=p.A,
                raw=raw_count(p)["stable"]),
        c5=dict(A_star_beta2_rho4=c5_A_star(2, 4), A_star_beta64_rho4=c5_A_star(64, 4)),
        zero_affinity_rho_quarter=str(zero_affinity_beta_threshold(Fr(1, 8), Fr(1, 8), Fr(1, 20), Fr(1, 10),
                                                                   Fr(1, 4))),
        feed_regime_rho_ninth=str(zero_affinity_beta_threshold(Fr(1), Fr(1), Fr(9, 20), Fr(1, 100), Fr(1, 9))),
        constructed_c4b=dict(gamma_even=str(r(q, q.T / 2)), bistable=cq["bistable"], stable=cq["stable"],
                             gamma_stable=cq["gamma_stable"], A=q.A, raw=raw_count(q)["stable"],
                             label="constructed by OL5, not the note's C4b"),
    )
