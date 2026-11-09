"""Pseudo-arclength continuation of stationary states in one parameter.

Part of stationary_continuation_analysis@1 (analysis/stationary.py). The branch
is followed in w = (z, theta / scale): z the coordinates on the conservation
set, theta the continuation parameter. Keller's pseudo-arclength corrector
solves F(w) = 0 with t . (w - w_pred) = 0 from the predictor w + ds t, where t
is the unit tangent (null vector of [F_z F_theta]) oriented along the branch.
The step adapts to the corrector's iteration count and to the turning angle
of the tangent, so the branch is not left at sharp turns.

Special points between consecutive accepted points. The step between them is
first walked again in REWALK_PIECES sub-steps (a long step can pass a fold
while the tangent turns only in its small parameter component); the first
sub-step whose end changes sign is then bisected in arclength from its start
with the same Keller corrector:

* fold (limit point, the edge of a multistability window): the theta
  component of the tangent changes sign. Confirmed by a small singular value of
  F_z with [F_z F_theta] of full rank (otherwise: branch point).
* Hopf: the real part of the leading complex-conjugate pair changes sign.
* stability change: the leading growth rate changes sign without a fold or
  Hopf point, so a real eigenvalue, or a group made degenerate by symmetry,
  crosses zero (a branch point; the bifurcating branches are not followed).
  Located like the others and reported with its crossing multiplicity.
* real crossing: the unstable count changes while the leading rate stays
  positive (reported at the later point, not refined).

Stability at every point comes from the dense reduced Jacobian (growth rates,
or log(mu)/T for the step map); continuation therefore uses dense linear
algebra and is meant for worlds up to stationary.DENSE_LIMIT coordinates.
"""

from __future__ import annotations

import math

import numpy as np
import scipy.linalg

from cells.analysis import stationary as sa
from cells.core.specs import ConfigError

CORRECTOR_ITERATIONS = 8
MIN_TANGENT_COSINE = 0.95
COMPLEX_IMAG_RELATIVE = 1e-9
REFINE_ITERATIONS = 60
REWALK_PIECES = 16


class _Branch:
    """One problem's branch coordinates w = (z, theta / scale)."""

    def __init__(self, pb, origin, scale):
        self.pb, self.origin, self.scale = pb, origin, float(scale)
        self.red = pb.reduction()

    def u(self, w):
        return self.red.lift(self.origin, w[:-1])

    def theta(self, w):
        return float(w[-1] * self.scale)

    def linearize(self, w):
        """Reduced (residual, F_z, F_theta-scaled, voltages, field converged)."""
        r, ju, jt, voltages, ok = self.pb.evaluate(self.u(w), self.theta(w))
        red = self.red
        return red.vector(r), red.operator(ju), self.scale * red.vector(jt), voltages, ok

    def norm(self, dw):
        return max(sa._norm(self.red.full(dw[:-1])), abs(float(dw[-1])))


def tangent(fz, ft, reference):
    """Unit null vector of [F_z F_theta] with a positive projection on reference."""
    a = np.hstack((fz, ft[:, None]))
    bordered = np.vstack((a, reference[None, :]))
    rhs = np.zeros(bordered.shape[0])
    rhs[-1] = 1.0
    t = np.linalg.solve(bordered, rhs)
    t /= np.linalg.norm(t)
    return t if t @ reference >= 0 else -t


def corrector(branch, predicted, direction, *, tolerance):
    """Keller corrector from a predictor; returns (w, linearization) or (None, None)."""
    w = predicted.copy()
    for _ in range(CORRECTOR_ITERATIONS):
        values = branch.linearize(w)
        r, fz, ft = values[:3]
        if not (sa._finite(r) and sa._finite(fz) and sa._finite(ft)):
            return None, None
        system = np.vstack((np.hstack((fz, ft[:, None])), direction[None, :]))
        rhs = -np.r_[r, direction @ (w - predicted)]
        try:
            dw = np.linalg.solve(system, rhs)
        except np.linalg.LinAlgError:
            return None, None
        w = w + dw
        if branch.norm(dw) <= tolerance:
            values = branch.linearize(w)
            if sa._finite(values[0]) and sa._finite(values[1]):
                return w, values
            return None, None
    return None, None


def _point(branch, w, values, reference):
    r, fz, ft, voltages, converged = values
    t = tangent(fz, ft, reference)
    rates, bound, _ = sa.dense_spectrum(branch.pb, fz)
    complex_pairs = np.abs(rates.imag) > COMPLEX_IMAG_RELATIVE * np.maximum(np.abs(rates), 1.0)
    singular = scipy.linalg.svdvals(fz)
    return dict(
        w=w,
        t=t,
        theta=branch.theta(w),
        u=branch.u(w),
        tangent_theta=float(t[-1]),
        unstable=int(np.sum(rates.real > bound)),
        marginal=int(np.sum(np.abs(rates.real) <= bound)),
        rates=rates,
        bound=bound,
        leading_pair=float(np.max(rates.real[complex_pairs], initial=-math.inf)),
        sigma_min_relative=float(singular[-1] / singular[0]) if len(singular) else 0.0,
        voltages=np.asarray(voltages),
        field_converged=bool(converged),
        fz=fz,
        ft=ft,
    )


def _record(branch, point, leading=6):
    rates = point["rates"][:leading]
    membranes = branch.pb.spec.model.membranes
    active = np.flatnonzero(np.asarray(branch.pb.p.membrane_active))
    return dict(
        parameter_value=point["theta"],
        membrane_voltage_V={membranes[i].id: float(point["voltages"][i]) for i in active},
        unstable_count=point["unstable"],
        marginal_count=point["marginal"],
        stable=point["unstable"] == 0 and point["marginal"] == 0,
        leading_eigenvalues_per_s=[[float(v.real), float(v.imag)] for v in rates],
        tangent_parameter_component=point["tangent_theta"],
        jacobian_sigma_min_relative=point["sigma_min_relative"],
        field_converged=point["field_converged"],
    )


def _at(branch, start, s, *, tolerance):
    w, values = corrector(branch, start["w"] + s * start["t"], start["t"], tolerance=tolerance)
    return None if w is None else _point(branch, w, values, start["t"])


def _refine(branch, start, length, indicator, *, tolerance):
    """Bisection in arclength for a sign change of indicator(point) on (0, length].

    Returns (point, bracket width, parameter error estimate): the estimate is
    the parameter change over the last two bisection points plus the corrector
    tolerance (bisection halves the bracket, so the change bounds the rest).
    """
    lo, hi = 0.0, length
    g_lo = indicator(start)
    best, previous = None, None
    for _ in range(REFINE_ITERATIONS):
        mid = 0.5 * (lo + hi)
        point = _at(branch, start, mid, tolerance=tolerance)
        if point is None:
            break
        g = indicator(point)
        previous, best = best, point
        if g == 0 or (hi - lo) <= 1e-13 * max(length, 1e-300):
            break
        if (g > 0) == (g_lo > 0):
            lo, g_lo = mid, g
        else:
            hi = mid
    if best is None:
        return None, hi - lo, math.inf
    change = math.inf if previous is None else abs(best["theta"] - previous["theta"])
    return best, hi - lo, change + tolerance


def continue_branch(
    pb,
    u_start,
    *,
    theta_start=None,
    direction=1,
    step=0.01,
    min_step=1e-7,
    max_step=0.05,
    max_points=400,
    bounds=(0.0, 1.0),
    parameter_scale=1.0,
    tolerance=sa.NEWTON_TOLERANCE,
    log=None,
):
    """Follow the branch through u_start; returns a bifurcation-diagram record.

    log, if given, is called with a short text line per accepted point.
    """
    if pb.parameter is None:
        raise ConfigError("Continuation requires a declared parameter")
    if direction not in (-1, 1):
        raise ConfigError("Continuation direction must be +1 or -1")
    if pb.reduction().size > sa.DENSE_LIMIT:
        raise ConfigError("Continuation uses dense linear algebra; the world is too large")
    theta_start = pb.theta0() if theta_start is None else float(theta_start)
    lo, hi = (float(b) for b in bounds)
    if not lo <= theta_start <= hi:
        raise ConfigError("The start parameter lies outside the continuation bounds")
    start = sa.newton(pb, u_start, theta=theta_start, tolerance=tolerance)
    if not start.converged:
        return dict(
            points=[], special_points=[], termination="start_not_converged: " + start.message
        )
    origin = pb.reduction().project(start.u)
    branch = _Branch(pb, origin, parameter_scale)
    w = np.r_[np.zeros(branch.red.size), theta_start / branch.scale]
    seed = np.zeros(len(w))
    seed[-1] = direction
    current = _point(branch, w, branch.linearize(w), seed)
    points, special = [_record(branch, current)], []
    states = [current["u"]]
    ds, termination, beyond = float(step), "max_points", False
    while len(points) < max_points:
        nxt = _at(branch, current, ds, tolerance=tolerance)
        if nxt is not None and float(nxt["t"] @ current["t"]) < MIN_TANGENT_COSINE:
            nxt = None
        if nxt is None:
            # Availabilities outside [0, 1] are outside the law's domain, so a
            # corrector failure next to a bound ends the branch at that bound.
            predicted = current["theta"] + ds * current["tangent_theta"] * branch.scale
            beyond |= not lo <= predicted <= hi
            ds /= 2
            if ds < min_step or (beyond and ds < 1e3 * min_step):
                termination = "parameter_bound" if beyond else "step_below_minimum"
                break
            continue
        beyond = False
        special.extend(_special(branch, current, nxt, ds, tolerance=tolerance))
        if not lo <= nxt["theta"] <= hi:
            termination = "parameter_bound"
            break
        current = nxt
        points.append(_record(branch, current))
        states.append(current["u"])
        if log is not None:
            log(
                f"point {len(points)} theta {current['theta']:.10g} unstable "
                f"{current['unstable']} tangent {current['tangent_theta']:+.3e} ds {ds:.3e}"
            )
        ds = min(max_step, ds * 1.4)
    return dict(
        parameter=pb.parameter.to_dict(),
        start_parameter=theta_start,
        bounds=[lo, hi],
        direction=direction,
        points=points,
        special_points=special,
        termination=termination,
        _states=np.asarray(states),
    )


def _bracket(branch, a, length, indicator, *, tolerance, pieces=REWALK_PIECES):
    """(start point, sub-length) of the first sub-step from a whose end changes sign.

    A long step can pass a fold while the tangent turns only in its small
    parameter component, so before bisecting the interval is walked again in
    `pieces` predictor-corrector sub-steps that follow the branch.
    """
    g_a, current, h = indicator(a), a, length / pieces
    for _ in range(pieces):
        nxt = _at(branch, current, h, tolerance=tolerance)
        if nxt is None:
            return a, length
        if (indicator(nxt) > 0) != (g_a > 0):
            return current, h
        current = nxt
    return a, length


def _special(branch, a, b, length, *, tolerance):
    found = []
    if np.sign(a["tangent_theta"]) != np.sign(b["tangent_theta"]) and a["tangent_theta"] != 0:
        sign = np.sign(a["tangent_theta"])

        def turning(q):
            return q["tangent_theta"] * sign

        start, sub = _bracket(branch, a, length, turning, tolerance=tolerance)
        point, width, error = _refine(branch, start, sub, turning, tolerance=tolerance)
        if point is not None:
            augmented = scipy.linalg.svdvals(np.hstack((point["fz"], point["ft"][:, None])))
            kind = (
                "fold"
                if augmented[-1] / augmented[0] > 1e3 * point["sigma_min_relative"]
                else ("branch_point_candidate")
            )
            found.append(
                _special_record(branch, point, kind, width, error)
                | dict(augmented_sigma_min_relative=float(augmented[-1] / augmented[0]))
            )
    if (
        np.isfinite(a["leading_pair"])
        and np.isfinite(b["leading_pair"])
        and (np.sign(a["leading_pair"]) != np.sign(b["leading_pair"]))
    ):

        def pair(q):
            return q["leading_pair"]

        start, sub = _bracket(branch, a, length, pair, tolerance=tolerance)
        point, width, error = _refine(branch, start, sub, pair, tolerance=tolerance)
        if point is not None:
            pair = point["rates"][
                np.argmax(np.where(np.abs(point["rates"].imag) > 0, point["rates"].real, -np.inf))
            ]
            found.append(
                _special_record(branch, point, "hopf", width, error)
                | dict(frequency_hz=float(abs(pair.imag) / (2 * math.pi)))
            )
    lead_a, lead_b = a["rates"].real[0], b["rates"].real[0]
    if a["unstable"] != b["unstable"] and not found and (lead_a > 0) != (lead_b > 0):
        # Loss (or gain) of stability without a fold: a real eigenvalue, or a
        # symmetry-degenerate group of them, crosses zero (branch point).
        def leading(q):
            return q["rates"].real[0]

        start, sub = _bracket(branch, a, length, leading, tolerance=tolerance)
        point, width, error = _refine(branch, start, sub, leading, tolerance=tolerance)
        if point is not None:
            rates = point["rates"]
            scale = max(float(np.max(np.abs(rates))), 1e-300)
            multiplicity = int(np.sum(np.abs(rates - rates[0]) <= 1e-8 * scale))
            # A pair that was real at the earlier point can cross as a complex
            # pair: then the located point is a Hopf point.
            oscillatory = abs(rates[0].imag) > COMPLEX_IMAG_RELATIVE * max(abs(rates[0]), 1.0)
            kind = "hopf" if oscillatory else "stability_change"
            extra = dict(
                unstable_before=a["unstable"],
                unstable_after=b["unstable"],
                crossing_multiplicity=multiplicity,
            )
            if oscillatory:
                extra["frequency_hz"] = float(abs(rates[0].imag) / (2 * math.pi))
            found.append(_special_record(branch, point, kind, width, error) | extra)
    elif a["unstable"] != b["unstable"] and not found:
        found.append(
            _special_record(branch, b, "real_crossing_after", length, math.inf)
            | dict(unstable_before=a["unstable"], unstable_after=b["unstable"])
        )
    return found


def _special_record(branch, point, kind, width, error):
    return dict(
        kind=kind,
        arclength_bracket=float(width),
        parameter_error_estimate=float(error),
        **_record(branch, point),
    )
