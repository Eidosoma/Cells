"""R-state: the two-state regulatory fraction (cells.regulation.hill_regulated_two_state@1), an independent
reference.

Written from docs/INVENTORY_COUPLING_DESIGN.md Appendix A.3 (with §1.5) and the turnover law of
docs/SECRETED_SPECIES_TRANSPORT_DESIGN.md §2.2, re-derived here, without reading the operator,
its helpers or their tests. numpy, scipy and the standard library only.

The law (Appendix A.3), for one (state, cell):

    ds/dt = k_on u(t) (1 - s) - k_off s,    u(t) = prod_j f_j(c_j(t)),    s(0) = s0,

with each f_j a Hill activation or inhibition (R-fac) of a concentration c_j(t) (mM), k_on and
k_off >= 0 (1/s), and s0 in [0, 1]. It is the deterministic kinetics of a population of two-state
units, the gating-variable form of Hodgkin & Huxley (1952) and a covalent-modification cycle in
its first-order regime (Goldbeter & Koshland 1981); Keener & Sneyd (2009) ch. 1 gives the
first-order kinetics. The exposure is U(t) = int_0^t u dtau.

Closed forms (derived again here):
* quasi-steady value s* = k_on u / (k_on u + k_off); for one activation input
  s* = [k_on/(k_on + k_off)] c^n/(c^n + K_eff^n), K_eff^n = K^n k_off/(k_on + k_off);
* frozen input: s(t) = s* + (s0 - s*) exp(-lambda t), lambda = k_on u + k_off;
* retention (u = 0): s(t) = s0 exp(-k_off t);
* commitment (k_off = 0): s(t) = 1 - (1 - s0) exp(-k_on U(t)), for any input;
* one input under first-order clearance c(t) = c0 exp(-k t): with w = c^n, dw/dt = -n k w, so
  int w/(K^n + w) dt = -(1/(n k)) ln(K^n + w) and
      U_act(t) = (1/(n k)) ln[(K^n + c0^n)/(K^n + c(t)^n)],    U_inh(t) = t - U_act(t);
  commitment then gives s(t) in closed form, and its crossing time t* too (activation);
* general input, k_off > 0 (variation of constants, written so that no exponential overflows):
      s(t) = s0 exp(-Lambda(t)) + k_on int_0^t u(tau) exp(-(Lambda(t) - Lambda(tau))) dtau,
      Lambda(t) - Lambda(tau) = k_off (t - tau) + k_on (U(t) - U(tau)).
* the regulator under turnover (production P in fmol/s, clearance k in 1/s, piecewise constant
  in time): n(t) = n_j exp(-k (t - t_j)) + (P/k)(1 - exp(-k (t - t_j))) on segment j, and
  n_j + P (t - t_j) when k = 0; c = n/V.

Numerical paths for general inputs:
* ``exposure`` and ``state_quadrature``: adaptive Gauss-Kronrod quadrature (QUADPACK, Piessens
  et al. 1983, through scipy.integrate.quad), nested for Lambda, split at every breakpoint;
* ``integrate``: the pair (s, U) by DOP853 at rtol 1e-13 (default) or Radau with the exact
  Jacobian, segment by segment; the crossing time t* of a level theta by Brent's method on
  re-integrations (piecewise_ode). The equation is scalar and linear in s, so an explicit method
  stays accurate at any admitted rate (its error control shortens the step where lambda h nears
  its stability bound). Measured (independent-references-20261114-01): DOP853 was 3 to 50 times
  faster than Radau at rtol 1e-12 on slow inputs and 1.5 times faster at lambda t_end = 2e4, and
  Radau 3 times faster at lambda t_end = 2e5 (5724 steps against 44628), the two agreeing to
  1e-14. Use Radau past about lambda t_end = 1e5.

The exact (``exact=True``) closed forms use 40-digit decimal arithmetic and return Decimals.
Sources: Hodgkin AL, Huxley AF. J Physiol 1952;117:500-544. Goldbeter A, Koshland DE Jr. PNAS
1981;78:6840-6844. Keener J, Sneyd J. Mathematical Physiology I, 2nd ed., Springer 2009.
Piessens R et al. QUADPACK, Springer 1983. Brent RP. Algorithms for Minimization without
Derivatives, Prentice-Hall 1973.
"""

import math
from decimal import Decimal

import numpy as np
from scipy.integrate import quad

from validation.coupling import factor_reference as fr
from validation.coupling import piecewise_ode

# ---------------------------------------------------------------- regulators


class Turnover:
    """A regulator amount under D150's turnover (§2.2): production P (fmol/s) and first-order
    clearance k (1/s), piecewise constant, in a node of fixed volume V (pL).

    ``segments`` is ((t_start_s, P_fmol_per_s, k_per_s), ...), sorted, the first starting at 0;
    each holds until the next start."""

    def __init__(self, n0_fmol, volume_pL, segments=((0.0, 0.0, 0.0),)):
        n0, volume = float(n0_fmol), float(volume_pL)
        if not (math.isfinite(n0) and n0 >= 0.0):
            raise ValueError("the initial amount is finite and >= 0")
        if not (math.isfinite(volume) and volume > 0.0):
            raise ValueError("the volume is finite and > 0")
        segments = tuple((float(a), float(p), float(k)) for a, p, k in segments)
        starts = [a for a, _, _ in segments]
        if not segments or starts[0] != 0.0 or starts != sorted(set(starts)):
            raise ValueError("segments start at 0 and are strictly increasing")
        if any(not (math.isfinite(p) and p >= 0.0 and math.isfinite(k) and k >= 0.0)
               for _, p, k in segments):
            raise ValueError("production and clearance are finite and >= 0")
        self.n0_fmol, self.volume_pL, self.segments = n0, volume, segments
        self._starts = starts
        starts_n = [n0]
        for (a, p, k), (b, _, _) in zip(segments, segments[1:], strict=False):
            starts_n.append(float(_amount_float(starts_n[-1], p, k, b - a)))
        self._start_amounts = starts_n

    def breakpoints(self):
        """Segment starts after 0, where c(t) has a kink."""
        return tuple(a for a, _, _ in self.segments[1:])

    def amount(self, t):
        """n(t) in fmol (a float for a scalar t, else vectorised over t >= 0)."""
        if isinstance(t, (int, float)):
            return self._amount_scalar(float(t))
        t = np.asarray(t, dtype=float)
        out = np.empty(t.shape)
        for idx in np.ndindex(t.shape):
            out[idx] = self._amount_scalar(float(t[idx]))
        return out[()] if out.ndim == 0 else out

    def _amount_scalar(self, t):
        if t < 0.0:
            raise ValueError("t >= 0")
        j = len(self._starts) - 1
        while self._starts[j] > t:
            j -= 1
        _, p, k = self.segments[j]
        return _amount_float(self._start_amounts[j], p, k, t - self._starts[j])

    def concentration(self, t):
        """c(t) = n(t)/V in mM."""
        return self.amount(t) / self.volume_pL

    def exact_amount(self, t):
        """n(t) as a 40-digit Decimal, every segment carried exactly."""
        t = fr._dec(t)
        with fr._context():
            n = fr._dec(self.n0_fmol)
            for j, (a, p, k) in enumerate(self.segments):
                a = fr._dec(a)
                end = fr._dec(self.segments[j + 1][0]) if j + 1 < len(self.segments) else None
                stop = t if end is None or t <= end else end
                n = _amount_exact(n, fr._dec(p), fr._dec(k), stop - a)
                if end is None or t <= end:
                    return n
        return n

    def exact_concentration(self, t):
        with fr._context():
            return self.exact_amount(t) / fr._dec(self.volume_pL)


def _amount_float(n, p, k, tau):
    if k == 0.0:
        return n + p * tau
    return n * math.exp(-k * tau) - (p / k) * math.expm1(-k * tau)


def _amount_exact(n, p, k, tau):
    with fr._context():
        if k == 0:
            return n + p * tau
        e = (-k * tau).exp()
        return n * e + (p / k) * (1 - e)


def clearance(c0_mM, k_per_s, volume_pL=1.0):
    """First-order clearance from c0: c(t) = c0 exp(-k t)."""
    return Turnover(c0_mM * volume_pL, volume_pL, ((0.0, 0.0, k_per_s),))


def constant(c_mM, volume_pL=1.0):
    """A frozen concentration."""
    return Turnover(c_mM * volume_pL, volume_pL)


class Function:
    """Any concentration c(t) (mM) given as a callable, with its kinks as breakpoints: for
    example the dense solution of D152's network reference for the first consumer (§4.5)."""

    def __init__(self, fn, breakpoints=()):
        self.fn = fn
        self._breakpoints = tuple(float(b) for b in breakpoints)

    def breakpoints(self):
        return self._breakpoints

    def concentration(self, t):
        out = self.fn(t)
        return float(out) if np.ndim(out) == 0 else np.asarray(out, dtype=float)


class Input:
    """One Hill input of a state: law ("hill_activation" or "hill_inhibition"), its regulator
    (Turnover, Function, or anything with concentration(t) and breakpoints()), K (mM) and n."""

    def __init__(self, law, regulator, K_mM, n):
        if law not in fr.HILL_LAWS:
            raise ValueError(f"an input law is one of {fr.HILL_LAWS}")
        if not (math.isfinite(K_mM) and K_mM > 0.0 and math.isfinite(n) and n > 0.0):
            raise ValueError("K > 0 and n > 0, finite")
        self.law, self.regulator, self.K_mM, self.n = law, regulator, float(K_mM), float(n)

    def value(self, t):
        """f(c(t)): a float for a scalar t (the float64 linear form), else an array."""
        c = self.regulator.concentration(t)
        if np.ndim(c) == 0:
            c = float(c)
            if not (math.isfinite(c) and c >= 0.0):
                raise ValueError(f"a concentration is finite and >= 0 (got {c})")
            return fr.hill_scalar(self.law, c, self.K_mM, self.n)
        return fr.law_value(self.law, x=c, K=self.K_mM, n=self.n)


def input_value(inputs, t):
    """u(t) = prod_j f_j(c_j(t)), in declared order."""
    u = 1.0
    for inp in inputs:
        u = u * inp.value(t)
    return u


def breakpoints(inputs):
    return tuple(sorted({b for inp in inputs for b in inp.regulator.breakpoints()}))


# ---------------------------------------------------------------- closed forms


def _check_rates(k_on, k_off, s0):
    if not all(math.isfinite(r) and r >= 0.0 for r in (k_on, k_off)):
        raise ValueError("rates are finite and >= 0")
    if not 0.0 <= s0 <= 1.0:
        raise ValueError("s0 lies in [0, 1]")


def quasi_steady(u, k_on, k_off):
    """s* = k_on u / (k_on u + k_off); NaN where both vanish (a frozen state)."""
    lam = k_on * np.asarray(u, dtype=float) + k_off
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(lam > 0.0, k_on * np.asarray(u, dtype=float) / np.where(lam > 0, lam, 1),
                       np.nan)
    return out[()] if out.ndim == 0 else out


def effective_half_saturation(K_mM, n, k_on, k_off):
    """K_eff = K (k_off/(k_on + k_off))^(1/n): one activation input's quasi-steady state is
    [k_on/(k_on + k_off)] c^n/(c^n + K_eff^n)."""
    return K_mM * (k_off / (k_on + k_off)) ** (1.0 / n)


def frozen(t, s0, u, k_on, k_off, *, exact=False):
    """s(t) with u held constant: s* + (s0 - s*) exp(-lambda t); s0 where lambda = 0."""
    _check_rates(k_on, k_off, s0)
    if exact:
        t, s0, u, k_on, k_off = (fr._dec(v) for v in (t, s0, u, k_on, k_off))
        with fr._context():
            lam = k_on * u + k_off
            if lam == 0:
                return s0
            star = k_on * u / lam
            return star + (s0 - star) * (-lam * t).exp()
    t = np.asarray(t, dtype=float)
    lam = k_on * u + k_off
    if lam == 0.0:
        return np.full(t.shape, float(s0))[()]
    star = k_on * u / lam
    out = s0 * np.exp(-lam * t) - star * np.expm1(-lam * t)
    return out[()] if np.ndim(out) == 0 else out


def retention(t, s0, k_off, *, exact=False):
    """u = 0: s(t) = s0 exp(-k_off t)."""
    return frozen(t, s0, 0.0, 0.0, k_off, exact=exact)


def commitment(U, s0, k_on, *, exact=False):
    """k_off = 0: s = 1 - (1 - s0) exp(-k_on U), for any input with exposure U."""
    _check_rates(k_on, 0.0, s0)
    if exact:
        U, s0, k_on = (fr._dec(v) for v in (U, s0, k_on))
        with fr._context():
            return 1 - (1 - s0) * (-k_on * U).exp()
    out = 1.0 - (1.0 - s0) * np.exp(-k_on * np.asarray(U, dtype=float))
    return out[()] if np.ndim(out) == 0 else out


def clearance_exposure(t, c0_mM, k_per_s, K_mM, n, law, *, exact=False):
    """U(t) for one Hill input of c(t) = c0 exp(-k t):
    activation (1/(n k)) ln[(K^n + c0^n)/(K^n + c(t)^n)], inhibition t minus that; with k = 0,
    u(c0) t."""
    if law not in fr.HILL_LAWS:
        raise ValueError(f"law is one of {fr.HILL_LAWS}")
    if exact:
        t, c0, k, K, n = (fr._dec(v) for v in (t, c0_mM, k_per_s, K_mM, n))
        with fr._context():
            if k == 0:
                return fr.exact_hill(law, c0, K, n) * t
            r0 = (n * (c0 / K).ln()).exp() if c0 > 0 else Decimal(0)  # (c0/K)^n
            rt = r0 * (-n * k * t).exp()
            act = ((1 + r0) / (1 + rt)).ln() / (n * k)
            return act if law == "hill_activation" else t - act
    t = np.asarray(t, dtype=float)
    if k_per_s == 0.0:
        out = fr.law_value(law, x=c0_mM, K=K_mM, n=n) * t
        return out[()] if np.ndim(out) == 0 else out
    r0 = (c0_mM / K_mM) ** n
    em = np.expm1(-n * k_per_s * t)  # exp(-n k t) - 1
    act = np.log1p(-r0 * em / (1.0 + r0 * (1.0 + em))) / (n * k_per_s)
    out = act if law == "hill_activation" else t - act
    return out[()] if np.ndim(out) == 0 else out


def clearance_commitment(t, s0, k_on, c0_mM, k_per_s, K_mM, n, law, *, exact=False):
    """s(t) for k_off = 0 and one Hill input under first-order clearance (Appendix A.3)."""
    U = clearance_exposure(t, c0_mM, k_per_s, K_mM, n, law, exact=exact)
    return commitment(U, s0, k_on, exact=exact)


def commitment_level(theta, s0, k_on):
    """The exposure at which a committing state (k_off = 0) reaches theta:
    U_theta = ln((1 - s0)/(1 - theta))/k_on; 0 if s0 >= theta, inf if theta = 1 > s0."""
    if s0 >= theta:
        return 0.0
    if theta >= 1.0 or k_on == 0.0:
        return math.inf
    return math.log((1.0 - s0) / (1.0 - theta)) / k_on


def clearance_commitment_crossing(theta, s0, k_on, c0_mM, k_per_s, K_mM, n, law):
    """t* with s(t*) = theta for k_off = 0 and one input under clearance; inf if never.

    Activation in closed form: c*^n = (K^n + c0^n) exp(-n k U_theta) - K^n and
    t* = ln(c0/c*)/k. Inhibition (U strictly increasing) by Brent's method on the closed U."""
    U_theta = commitment_level(theta, s0, k_on)
    if U_theta == 0.0:
        return 0.0
    if not math.isfinite(U_theta):
        return math.inf
    if law == "hill_activation":
        if k_per_s == 0.0:
            u = float(fr.hill_activation(c0_mM, K_mM, n))
            return U_theta / u if u > 0.0 else math.inf
        r0 = (c0_mM / K_mM) ** n
        # (c*/K)^n = (1 + r0) exp(-x) - 1 = r0 + (1 + r0) expm1(-x), x = n k U_theta.
        rstar = r0 + (1.0 + r0) * math.expm1(-n * k_per_s * U_theta)
        if rstar <= 0.0:
            return math.inf
        return math.log(r0 / rstar) / (n * k_per_s)
    # Inhibition: U(t) >= t u_min grows without bound, so a bracket exists.
    hi = 1.0
    while clearance_exposure(hi, c0_mM, k_per_s, K_mM, n, law) < U_theta:
        hi *= 2.0
    from scipy.optimize import brentq

    return float(brentq(lambda t: clearance_exposure(t, c0_mM, k_per_s, K_mM, n, law) - U_theta,
                        0.0, hi, xtol=1e-15, rtol=4 * fr.EPS))


def frozen_crossing(theta, s0, u, k_on, k_off):
    """t* with s(t*) = theta under a frozen input: ln((s* - s0)/(s* - theta))/lambda when
    s0 < theta < s*; 0 when s0 >= theta; inf otherwise."""
    if s0 >= theta:
        return 0.0
    lam = k_on * u + k_off
    if lam == 0.0:
        return math.inf
    star = k_on * u / lam
    if star <= theta:
        return math.inf
    return math.log((star - s0) / (star - theta)) / lam


# ---------------------------------------------------------------- quadrature (general inputs)


def _pieces(inputs, a, b):
    cuts = [a, *(x for x in breakpoints(inputs) if a < x < b), b]
    return list(zip(cuts, cuts[1:], strict=False))


def exposure(inputs, t, t_from=0.0, *, epsrel=1e-13):
    """U(t) - U(t_from) = int u dtau, by adaptive quadrature split at every breakpoint."""
    total = 0.0
    for a, b in _pieces(inputs, t_from, t):
        if b > a:
            total += quad(lambda x: float(input_value(inputs, x)), a, b, epsabs=0.0,
                          epsrel=epsrel, limit=200)[0]
    return total


def state_quadrature(inputs, k_on, k_off, s0, t, *, epsrel=1e-12):
    """s(t) by the variation-of-constants integral with nested quadrature (any input, any
    k_off). Slow (tens of milliseconds per t): a cross-check, not a production path."""
    _check_rates(k_on, k_off, s0)
    U_t = exposure(inputs, t)
    total = s0 * math.exp(-(k_off * t + k_on * U_t))
    if k_on == 0.0:
        return total

    def integrand(tau):
        decay = k_off * (t - tau) + k_on * exposure(inputs, t, tau, epsrel=epsrel)
        return float(input_value(inputs, tau)) * math.exp(-decay)

    for a, b in _pieces(inputs, 0.0, t):
        if b > a:
            total += k_on * quad(integrand, a, b, epsabs=0.0, epsrel=epsrel, limit=200)[0]
    return total


# ---------------------------------------------------------------- adaptive integration


class StateRun:
    """The pair (s, U) of one (state, cell), integrated from 0 to t_end.

    ``at[t]`` gives (s, U) at each record time (each an integration end point); ``s(t)`` and
    ``U(t)`` give them anywhere by re-integration from the last stored step; ``crossing(theta)``
    gives t*; ``crossing_step(theta, dt)`` gives the step index k* = min{k : s(k dt) >= theta}
    with its margins."""

    def __init__(self, run, record):
        self.run = run
        self.at = {t: tuple(run.state(t)) for t in record}
        self.steps = run.steps

    def s(self, t):
        return float(self.run.state(t)[0])

    def U(self, t):
        return float(self.run.state(t)[1])

    def crossing(self, theta):
        """t* = the first t with s(t) >= theta (0 if s0 >= theta; inf if not before t_end)."""
        return self.run.first_crossing(lambda t, y: y[0], theta)

    def crossing_step(self, theta, dt):
        return crossing_step(self.s, self.crossing(theta), theta, dt, self.run.t_end)


def integrate(inputs, k_on, k_off, s0, t_end, *, record=(), rtol=1e-13, atol=(1e-16, 1e-15),
              method="DOP853", max_step=math.inf):
    """Integrate (s, U) with ds/dt = k_on u (1 - s) - k_off s and dU/dt = u, segment by segment
    between the inputs' breakpoints and the records (DOP853 by default; Radau, BDF and LSODA
    receive the exact Jacobian)."""
    _check_rates(k_on, k_off, s0)
    if not inputs:
        raise ValueError("a state has at least one input")
    record = tuple(float(t) for t in record)
    if any(not 0.0 <= t <= t_end for t in record):
        raise ValueError("records lie in [0, t_end]")
    points = {0.0, float(t_end), *record, *(b for b in breakpoints(inputs) if 0.0 < b < t_end)}

    def segment(t0, t1):
        def fun(t, y):
            u = float(input_value(inputs, t))
            return np.array([k_on * u * (1.0 - y[0]) - k_off * y[0], u])

        def jac(t, y):
            u = float(input_value(inputs, t))
            return np.array([[-(k_on * u + k_off), 0.0], [0.0, 0.0]])

        return fun, jac

    run = piecewise_ode.Run(segment, (s0, 0.0), points, rtol=rtol, atol=atol, method=method,
                            max_step=max_step)
    return StateRun(run, record)


def crossing_step(s_of_t, t_star, theta, dt, t_end=math.inf):
    """k* = min{k : s(k dt) >= theta} from the reference's own s, given t* (the first t with
    s >= theta). Returns dict(k, t_star, margin_after = s(k* dt) - theta >= 0,
    margin_before = theta - s((k* - 1) dt) > 0 (None for k* = 0), slope = ds/dt estimate at t*
    from the two grid points). k* is None if no grid point up to t_end reaches theta."""
    if t_star == 0.0:
        return dict(k=0, t_star=0.0, margin_after=s_of_t(0.0) - theta, margin_before=None,
                    slope=None)
    if not math.isfinite(t_star):
        return dict(k=None, t_star=t_star, margin_after=None, margin_before=None, slope=None)
    k = max(1, math.ceil(t_star / dt))
    while (k - 1) * dt >= t_star:  # rounding of t*/dt
        k -= 1
    while k * dt <= t_end and s_of_t(k * dt) < theta:  # s dipped back below theta
        k += 1
    if k * dt > t_end:
        return dict(k=None, t_star=t_star, margin_after=None, margin_before=None, slope=None)
    after, before = s_of_t(k * dt), s_of_t((k - 1) * dt)
    return dict(k=k, t_star=t_star, margin_after=after - theta, margin_before=theta - before,
                slope=(after - before) / dt)
