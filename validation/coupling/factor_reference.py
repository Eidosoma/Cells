"""R-fac: the coupling factors of cells.operator.species_regulated_availability@1, an independent reference.

Written from docs/INVENTORY_COUPLING_DESIGN.md, Appendix A.2 with §1.3 (laws, sides, the basal
level) and §1.6 (declaration), and from the textbook Hill forms. It was written without reading
the operator, its Hill helper or their tests. numpy and the standard library only.

Every law is evaluated in linear space, x^n/(K^n + x^n) and K^n/(K^n + x^n), never through the
log-space kernel z = n (ln x - ln K) that the design names for the engine (§1.9). There are two
evaluators:

* **float64** (vectorised numpy, for grids). The Hill laws use a ratio form that cannot overflow:
  r = (x/K)^n below K and q = (K/x)^n above it. Its error is a few ulps and grows with n, because
  pow amplifies the rounding of x/K n-fold. The self-tests measure it.
* **exact** (``exact_*``): the same laws in 40-digit decimal arithmetic, rounded once to float64
  by ``to_float``. Python's decimal exp and ln are correctly rounded, so (x/K)^n, formed as
  exp(n ln(x/K)) or by repeated multiplication for an integral n, carries a relative error near
  1e-39, and the rounded values are within half an ulp of the true law at the float64 inputs.
  They are the reference values for acceptance A1's "within a few ulps of R-fac".

The laws (Appendix A.2):
* hill_activation f = x^n/(K^n + x^n) and hill_inhibition f = K^n/(K^n + x^n), with x a
  concentration (mM), K > 0 (mM) and n > 0. At x = 0 they give 0 and 1.
* state_fraction f = s and state_complement f = 1 - s, with s in [0, 1].
* A coupling's factor is F = b + (1 - b) f, with 0 <= b < 1. A switched-off coupling has F = 1.
* A contact's side: "first" reads the contact's first cell a(e), "second" its second cell b(e),
  and "both" gives F_e = F(source at a(e)) * F(source at b(e)), the basal level applied on each
  side before the product. A population has no side (None).
* An element's product is G = prod_r F_r over its routes in declared order, and 1 with none.
  The effective availability is a_sched * G (version 1 has no other operator's factor).
  ``element_product`` multiplies left to right, (F_1 F_2) F_3 ..., and ``effective_availability``
  forms G first, then a_sched * G. The exact evaluators round the exact product once.

Sources: Hill AV (1910) J Physiol 40 (Suppl) iv-vii; Weiss JN (1997) FASEB J 11:835-841;
Goutelle S et al. (2008) Fundam Clin Pharmacol 22:633-648 (the four-parameter form with a basal
level, written here as F = b + (1 - b) f).
"""

import math
from decimal import MAX_EMAX, MIN_EMIN, Decimal, localcontext

import numpy as np

HILL_LAWS = ("hill_activation", "hill_inhibition")
STATE_LAWS = ("state_fraction", "state_complement")
LAWS = HILL_LAWS + STATE_LAWS
SIDES = ("first", "second", "both")
DIGITS = 40  # decimal digits of the exact evaluators (about 1e-40 relative)
EPS = float(np.finfo(float).eps)


# ---------------------------------------------------------------- domain


def _check_law(law):
    if law not in LAWS:
        raise ValueError(f"unknown law {law!r}; one of {LAWS}")


def _check_hill(x, K, n):
    x, K, n = (np.asarray(v, dtype=float) for v in (x, K, n))
    if not (np.all(np.isfinite(x)) and np.all(x >= 0.0)):
        raise ValueError("a concentration is finite and >= 0")
    if not (np.all(np.isfinite(K)) and np.all(K > 0.0)):
        raise ValueError("a half-saturation K is finite and > 0")
    if not (np.all(np.isfinite(n)) and np.all(n > 0.0)):
        raise ValueError("a Hill coefficient n is finite and > 0")
    return x, K, n


def _check_state(s):
    s = np.asarray(s, dtype=float)
    if not (np.all(np.isfinite(s)) and np.all((s >= 0.0) & (s <= 1.0))):
        raise ValueError("a state fraction lies in [0, 1]")
    return s


def _check_basal(b):
    b = np.asarray(b, dtype=float)
    if not (np.all(np.isfinite(b)) and np.all((b >= 0.0) & (b < 1.0))):
        raise ValueError("a basal level b lies in [0, 1)")
    return b


# ---------------------------------------------------------------- float64 (vectorised)


def hill_activation(x, K, n):
    """x^n/(K^n + x^n), elementwise (numpy broadcasting)."""
    x, K, n = _check_hill(x, K, n)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore", under="ignore"):
        below = x < K
        r = np.where(below, x / K, 1.0) ** n  # (x/K)^n <= 1 below K
        q = np.where(below, 1.0, K / np.where(x > 0.0, x, 1.0)) ** n  # (K/x)^n <= 1 above
        out = np.where(below, r / (1.0 + r), 1.0 / (1.0 + q))
    return out[()] if out.ndim == 0 else out


def hill_inhibition(x, K, n):
    """K^n/(K^n + x^n), elementwise (numpy broadcasting)."""
    x, K, n = _check_hill(x, K, n)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore", under="ignore"):
        below = x < K
        r = np.where(below, x / K, 1.0) ** n
        q = np.where(below, 1.0, K / np.where(x > 0.0, x, 1.0)) ** n
        out = np.where(below, 1.0 / (1.0 + r), q / (1.0 + q))
    return out[()] if out.ndim == 0 else out


def hill_scalar(law, x, K, n):
    """One point of the float64 Hill laws (the same ratio forms as hill_activation and
    hill_inhibition), in plain floats without checks: for integrators' right-hand sides."""
    if x < K:
        r = (x / K) ** n
        return r / (1.0 + r) if law == "hill_activation" else 1.0 / (1.0 + r)
    q = (K / x) ** n
    return 1.0 / (1.0 + q) if law == "hill_activation" else q / (1.0 + q)


def law_value(law, *, x=None, s=None, K=None, n=None):
    """The law's f: a Hill law of the concentration x (mM) with K (mM) and n, or a state law of
    the fraction s."""
    _check_law(law)
    if law in HILL_LAWS:
        if x is None or K is None or n is None or s is not None:
            raise ValueError(f"{law} takes x, K and n (and no s)")
        return (hill_activation if law == "hill_activation" else hill_inhibition)(x, K, n)
    if s is None or x is not None or K is not None or n is not None:
        raise ValueError(f"{law} takes s only")
    s = _check_state(s)
    out = s if law == "state_fraction" else 1.0 - s
    return out[()] if np.ndim(out) == 0 else out


def coupling_factor(law, basal, *, x=None, s=None, K=None, n=None, enabled=True):
    """F = b + (1 - b) f, or exactly 1 where the coupling is switched off (enabled false)."""
    b = _check_basal(basal)
    f = law_value(law, x=x, s=s, K=K, n=n)
    out = np.where(np.asarray(enabled, dtype=bool), b + (1.0 - b) * f, 1.0)
    return out[()] if out.ndim == 0 else out


def side_factor(side, law, basal, *, first=None, second=None, K=None, n=None, enabled=True):
    """A contact route's factor. ``first`` and ``second`` are the source's values (x for a Hill
    law, s for a state law) at the contact's first and second cells; a side reads only its own.
    "both" is F(first) * F(second), each with the basal level."""
    if side not in SIDES:
        raise ValueError(f"unknown side {side!r}; one of {SIDES}")
    key = "x" if law in HILL_LAWS else "s"

    def one(value):
        if value is None:
            raise ValueError(f"side {side!r} needs the source at that cell")
        return coupling_factor(law, basal, K=K, n=n, enabled=enabled, **{key: value})

    if side == "first":
        return one(first)
    if side == "second":
        return one(second)
    out = np.asarray(one(first)) * np.asarray(one(second))
    return out[()] if out.ndim == 0 else out


def element_product(factors):
    """G = prod of the routes' factors in declared order, (F_1 F_2) F_3 ...; 1 with none."""
    out = np.asarray(1.0)
    for f in factors:
        out = out * np.asarray(f, dtype=float)
    return out[()] if out.ndim == 0 else out


def effective_availability(a_sched, factors):
    """a_sched * G, with G formed first in declared order."""
    a = np.asarray(a_sched, dtype=float)
    if not (np.all(np.isfinite(a)) and np.all((a >= 0.0) & (a <= 1.0))):
        raise ValueError("a scheduled availability lies in [0, 1]")
    out = a * np.asarray(element_product(factors))
    return out[()] if out.ndim == 0 else out


# ---------------------------------------------------------------- exact (40-digit decimal)


def _context():
    """A 40-digit decimal context with the widest exponent range (no overflow or underflow)."""
    return localcontext(prec=DIGITS, Emax=MAX_EMAX, Emin=MIN_EMIN)


def _dec(v):
    """A float, int, str or Decimal as an exact Decimal (a float converts exactly)."""
    if isinstance(v, Decimal):
        return v
    if isinstance(v, str):
        return Decimal(v)
    v = float(v)
    if not math.isfinite(v):
        raise ValueError("inputs are finite")
    return Decimal(v)


def to_float(d):
    """A Decimal rounded once to the nearest float64 (via its decimal string, which CPython
    converts with correct rounding, subnormals included)."""
    return float(d)


def exact_hill(law, x, K, n):
    """The Hill law at (x, K, n) as a 40-digit Decimal, from r = (x/K)^n: activation r/(1 + r),
    inhibition 1/(1 + r) (equal to x^n/(K^n + x^n) and K^n/(K^n + x^n) in exact arithmetic)."""
    x, K, n = _dec(x), _dec(K), _dec(n)
    if x < 0 or K <= 0 or n <= 0:
        raise ValueError("x >= 0, K > 0 and n > 0")
    with _context():
        if x == 0:
            r = Decimal(0)
        elif n == n.to_integral_value() and n <= 64:
            r = (x / K) ** int(n)
        else:
            r = (n * (x / K).ln()).exp()
        return (r if law == "hill_activation" else Decimal(1)) / (1 + r)


def exact_law_value(law, *, x=None, s=None, K=None, n=None):
    """f as a 40-digit Decimal (see law_value)."""
    _check_law(law)
    if law in HILL_LAWS:
        if x is None or K is None or n is None or s is not None:
            raise ValueError(f"{law} takes x, K and n (and no s)")
        return exact_hill(law, x, K, n)
    if s is None or x is not None or K is not None or n is not None:
        raise ValueError(f"{law} takes s only")
    s = _dec(s)
    if not 0 <= s <= 1:
        raise ValueError("a state fraction lies in [0, 1]")
    with _context():
        return s if law == "state_fraction" else 1 - s


def exact_coupling_factor(law, basal, *, x=None, s=None, K=None, n=None, enabled=True):
    """F = b + (1 - b) f as a 40-digit Decimal; exactly 1 when switched off."""
    b = _dec(basal)
    if not 0 <= b < 1:
        raise ValueError("a basal level b lies in [0, 1)")
    f = exact_law_value(law, x=x, s=s, K=K, n=n)
    if not enabled:
        return Decimal(1)
    with _context():
        return b + (1 - b) * f


def exact_side_factor(side, law, basal, *, first=None, second=None, K=None, n=None, enabled=True):
    """A contact route's factor as a 40-digit Decimal (see side_factor)."""
    if side not in SIDES:
        raise ValueError(f"unknown side {side!r}; one of {SIDES}")
    key = "x" if law in HILL_LAWS else "s"

    def one(value):
        if value is None:
            raise ValueError(f"side {side!r} needs the source at that cell")
        return exact_coupling_factor(law, basal, K=K, n=n, enabled=enabled, **{key: value})

    if side == "first":
        return one(first)
    if side == "second":
        return one(second)
    with _context():
        return one(first) * one(second)


def exact_product(factors, a_sched=1.0):
    """a_sched * prod F_r as a 40-digit Decimal (exact factors in, one rounding at the end by
    to_float). Factors may be Decimals from the exact evaluators or floats."""
    out = _dec(a_sched)
    if not 0 <= out <= 1:
        raise ValueError("a scheduled availability lies in [0, 1]")
    with _context():
        for f in factors:
            out = out * _dec(f)
    return out


def exact_grid(law, basal, *, x=None, s=None, K=None, n=None, enabled=True, side=None,
               second=None):
    """The exact evaluator over a broadcast grid, rounded once per point to float64.

    Without a side this is F (exact_coupling_factor) at each point; with a side, x or s is the
    first cell's value and ``second`` the second cell's. About 30 microseconds per point."""
    key = "x" if law in HILL_LAWS else "s"
    first = x if key == "x" else s
    arrays = np.broadcast_arrays(
        *(np.asarray(v, dtype=float) for v in (first, second if side else first, K if K is not
          None else 1.0, n if n is not None else 1.0, basal, enabled))
    )
    out = np.empty(arrays[0].shape)
    for idx in np.ndindex(out.shape):
        v1, v2, k, m, b, on = (float(a[idx]) for a in arrays)
        hill = dict(K=k, n=m) if key == "x" else {}
        if side is None:
            d = exact_coupling_factor(law, b, enabled=bool(on), **hill, **{key: v1})
        else:
            d = exact_side_factor(side, law, b, first=v1, second=v2, enabled=bool(on), **hill)
        out[idx] = to_float(d)
    return out[()] if out.ndim == 0 else out


# ---------------------------------------------------------------- comparing


def _ordered(v):
    """The monotone int64 image of float64 values (+0 and -0 map to 0)."""
    i = np.ascontiguousarray(v, dtype=np.float64).view(np.int64)
    return np.where(i < 0, -(i & 0x7FFFFFFFFFFFFFFF), i)


def ulp_distance(a, b):
    """The number of float64 steps between a and b (0 when equal; +0 and -0 are one value),
    elementwise, as uint64."""
    a, b = np.broadcast_arrays(np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64))
    if not (np.all(np.isfinite(a)) and np.all(np.isfinite(b))):
        raise ValueError("ulp_distance takes finite values")
    ia, ib = _ordered(a), _ordered(b)
    same = (ia >= 0) == (ib >= 0)
    with np.errstate(over="ignore"):
        d_same = np.abs(np.where(same, ia - ib, 0)).astype(np.uint64)
    d_split = np.abs(ia).astype(np.uint64) + np.abs(ib).astype(np.uint64)
    out = np.where(same, d_same, d_split).reshape(a.shape)
    return out[()] if out.ndim == 0 else out


def eps_error(a, b):
    """|a - b| in units of float64 eps (2.22e-16): the absolute scale for factors in [0, 1]."""
    out = np.abs(np.asarray(a, dtype=float) - np.asarray(b, dtype=float)) / EPS
    return out[()] if out.ndim == 0 else out


def log_space_condition(law, x, K, n):
    """An estimate, in units of eps, of the relative error of a Hill factor formed from
    z = n (ln x - ln K) (the design's §1.9 form), from the formula's conditioning only (no
    implementation is assumed): |d ln f / dz| = 1 - f for both laws, and z carries an absolute
    rounding of about n (|ln x| + |ln K|) eps. It is large in a deep tail, where f is tiny
    (activation far below K, inhibition far above it). A guide for setting A1's tolerance, not a
    tolerance."""
    x, K, n = _check_hill(x, K, n)
    f = hill_activation(x, K, n) if law == "hill_activation" else hill_inhibition(x, K, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        logs = np.abs(np.log(np.where(x > 0, x, 1.0))) + np.abs(np.log(K))
    out = (1.0 - np.asarray(f)) * n * logs
    return out[()] if np.ndim(out) == 0 else out
