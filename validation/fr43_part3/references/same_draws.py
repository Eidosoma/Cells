"""FR-43 part 3 references: the same-draws integration of spec/part3.json's worlds.

A low-count integer population N = (n_free, n_active) on continuous pools x = (n_cell, n_node).
Between events N is constant and x follows the spec's linear ODEs. Event k fires when the
integrated hazard H (restarted at every event) reaches E_k = -ln(u1_k). The channel is drawn
with u2_k at the crossing state. Three evaluations are made of each world, and each assembles
the model from the spec on its own:

- ``closed form`` (the reported values): the exact solution between events, x(tau) =
  e^{A tau} x0 + tau phi1(A tau) p and its integral tau phi1(A tau) x0 + tau^2 phi2(A tau) p, by
  Sylvester's formula on the 2x2 matrix. It is evaluated in Python's decimal arithmetic, with
  event times from a bracketed safeguarded Newton on H(tau) - E_k;
- ``ode``: the ODE with H, the transferred, produced and cleared amounts appended, integrated by
  scipy's Radau (and DOP853 as a third method), with events found by solve_ivp's event function
  H - E_k and refined by Newton on re-integrated end points;
- the closed form again at more digits, which measures its arithmetic only.

    python same_draws.py                 the premise check, then every world: results/*.json
    python same_draws.py --worlds W1_two_subunits_feedback

No engine code is imported: numpy, scipy, the standard library and, for the premise check's
second route, JAX's random primitives.
"""

import argparse
import datetime
import decimal
import json
import math
import pathlib
import platform
import subprocess
import sys
import time

import numpy as np
import scipy
from scipy.integrate import solve_ivp

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import stream_draws  # noqa: E402  (this folder's premise check, not an engine module)

HERE = pathlib.Path(__file__).resolve().parent
SPEC_DIR = HERE / "spec"
RESULTS_DIR = HERE / "results"
SPEC_COMMIT = "0ab4c9d2e9df80fe61845cd05af9cc04d2fa6b13"
CODE_PATHS = ("validation/fr43_part3/references/same_draws.py",
              "validation/fr43_part3/references/stream_draws.py")

D = decimal.Decimal
DIGITS = 50          # the reported closed form
DIGITS_CHECK = 70    # the closed form's arithmetic check
ODE_RTOL = 1e-12
ODE_ATOL = 1e-15
ODE_TIGHT_RTOL = 1e-13   # DOP853 tightened, to show the ODE converging on the closed form
TARGET = {"event_time_s": 1e-10, "amount_relative": 1e-12}


def falling_factorial(n, r):
    """ff(n, r) = n!/(n - r)!: ordered tuples; ff(n, 0) = 1 and ff(n, r) = 0 for r > n."""
    if r > n:
        return 0
    out = 1
    for i in range(r):
        out *= n - i
    return out


def jump(counts, channel):
    """N <- N - r_j + p_j."""
    out = dict(counts)
    for s, r in channel["reactants"].items():
        out[s] -= r
    for s, p in channel["products"].items():
        out[s] += p
    if any(v < 0 for v in out.values()):
        raise RuntimeError(f"a jump left a negative count: {out}")
    return out


def _turnover(world):
    t = world["turnover"]
    if t is None:
        return 0.0, 0.0
    return float(t["production_cell_fmol_per_s"]), float(t["clearance_node_per_s"])


def _check_reads(world):
    for ch in world["channels"]:
        rd = ch["read"]
        if rd is not None and (rd["species"] != "S" or rd["order"] != 1 or rd["at"] not in ("cell", "node")):
            raise NotImplementedError(f"only first-order reads of S at the cell or node: {rd}")
    if world["transfer"]["species"] != "S":
        raise NotImplementedError("only the transfer of S")


# ----------------------------------------------------------------------------------------------
# The closed form, in decimal arithmetic.
# ----------------------------------------------------------------------------------------------

def _phi(n, z, digits):
    """The exponential phi-functions: phi0 = e^z, phi1 = (e^z - 1)/z, phi2 = (e^z - 1 - z)/z^2."""
    if n == 0:
        return z.exp()
    if abs(z) < D("0.5"):
        term = D(1) / math.factorial(n)
        total = term
        eps = D(10) ** (-(digits + 8))
        m = 0
        while abs(term) > eps:
            m += 1
            term = term * z / (m + n)
            total += term
        return total
    ez = z.exp()
    return (ez - 1) / z if n == 1 else (ez - 1 - z) / (z * z)


class ClosedFormSegment:
    """One stretch of constant N: x' = A x + p, H' = alpha + beta . x, in decimal arithmetic."""

    def __init__(self, world, counts, digits):
        self.digits = digits
        vc = D(world["volumes_pL"]["cell"])
        vn = D(world["volumes_pL"]["node"])
        g = world["transfer"]["conductance_pL_per_s_per_unit"]
        conductance = sum((D(g[s]) * counts[s] for s in counts), D(0))
        prod, clr = _turnover(world)
        self.P, self.k = D(prod), D(clr)
        # J = G (n_cell/V_cell - n_node/V_node) = a n_cell - b n_node
        self.a, self.b = conductance / vc, conductance / vn
        # the propensities: a_j = coef_j (constant) or coef_j * n_pool / V_pool (a first-order read)
        self.rates = []
        for ch in world["channels"]:
            coef = D(ch["rate_constant_per_s"])
            for s, r in ch["reactants"].items():
                coef *= falling_factorial(counts[s], r)
            rd = ch["read"]
            if rd is None:
                self.rates.append((coef, D(0), D(0)))
            elif rd["at"] == "cell":
                self.rates.append((D(0), coef / vc, D(0)))
            else:
                self.rates.append((D(0), D(0), coef / vn))
        self.alpha = sum((r[0] for r in self.rates), D(0))
        self.beta = (sum((r[1] for r in self.rates), D(0)), sum((r[2] for r in self.rates), D(0)))
        # A = [[-a, b], [a, -(b + k)]]
        a, b, k = self.a, self.b, self.k
        self.A = ((-a, b), (a, -(b + k)))
        if conductance == 0:
            self.diagonal = True
        else:
            self.diagonal = False
            disc = (a - k) ** 2 + b * b + 2 * a * b + 2 * b * k       # (a+b+k)^2 - 4ak > 0
            lam2 = (-(a + b + k) - disc.sqrt()) / 2                     # the faster rate
            lam1 = a * k / lam2                                         # det A / lam2 (0 when k = 0)
            self.lam = (lam1, lam2)
            gap = lam1 - lam2
            eye = ((D(1), D(0)), (D(0), D(1)))
            # Sylvester's projectors: f(A tau) = f(lam1 tau) P1 + f(lam2 tau) P2
            self.P1 = tuple(tuple((self.A[i][j] - lam2 * eye[i][j]) / gap for j in range(2))
                            for i in range(2))
            self.P2 = tuple(tuple((self.A[i][j] - lam1 * eye[i][j]) / (-gap) for j in range(2))
                            for i in range(2))

    def _functions(self, tau):
        """(e^{A tau}, phi1(A tau), phi2(A tau)) as 2x2 tuples."""
        dg = self.digits
        if self.diagonal:                       # A = diag(0, -k)
            z = -self.k * tau
            return tuple(((_phi(n, D(0), dg), D(0)), (D(0), _phi(n, z, dg))) for n in (0, 1, 2))
        out = []
        for n in (0, 1, 2):
            f1 = _phi(n, self.lam[0] * tau, dg)
            f2 = _phi(n, self.lam[1] * tau, dg)
            out.append(tuple(tuple(f1 * self.P1[i][j] + f2 * self.P2[i][j] for j in range(2))
                             for i in range(2)))
        return tuple(out)

    def propagate(self, x0, tau):
        """x(tau) and I(tau) = integral of x from 0 to tau, from x(0) = x0."""
        e0, f1, f2 = self._functions(tau)
        p = (self.P, D(0))
        x = tuple(e0[i][0] * x0[0] + e0[i][1] * x0[1] + tau * (f1[i][0] * p[0] + f1[i][1] * p[1])
                  for i in range(2))
        integral = tuple(tau * (f1[i][0] * x0[0] + f1[i][1] * x0[1])
                         + tau * tau * (f2[i][0] * p[0] + f2[i][1] * p[1]) for i in range(2))
        return x, integral

    def hazard(self, tau, integral):
        return self.alpha * tau + self.beta[0] * integral[0] + self.beta[1] * integral[1]

    def total_rate(self, x):
        return self.alpha + self.beta[0] * x[0] + self.beta[1] * x[1]

    def propensities(self, x):
        return [c + bc * x[0] + bn * x[1] for c, bc, bn in self.rates]

    def increments(self, tau, integral):
        """(transferred, produced, cleared) over the stretch."""
        return (self.a * integral[0] - self.b * integral[1], self.P * tau, self.k * integral[1])

    def solve(self, x0, target, tau_max=None):
        """The tau with H(tau) = target, or None when H(tau_max) < target (no crossing by tau_max)."""
        def h_of(tau):
            x, integral = self.propagate(x0, tau)
            return self.hazard(tau, integral) - target, self.total_rate(x)

        if tau_max is not None and h_of(tau_max)[0] < 0:
            return None
        lo, hi = D(0), None
        tau = target / self.total_rate(x0)
        for _ in range(400):
            f, _rate = h_of(tau)
            if f >= 0:
                hi = tau
                break
            lo, tau = tau, 2 * tau
        if hi is None:
            raise RuntimeError("no bracket for the hazard crossing")
        tol = D(10) ** (-(self.digits - 5))
        tau = hi
        for _ in range(400):
            f, rate = h_of(tau)
            if f == 0:
                return tau
            if f > 0:
                hi = tau
            else:
                lo = tau
            step = tau - f / rate
            if not lo < step < hi:
                step = (lo + hi) / 2
            if abs(step - tau) <= tol * max(D(1), tau):
                return step
            tau = step
        raise RuntimeError("the hazard root did not converge")


def channel_rule_exact(props, u2):
    """The first j with c_j > u2 a0 (exact; u2 < 1, so nextafter's guard never binds)."""
    a0 = sum(props, D(0))
    thr = D(u2) * a0
    c_prev = D(0)
    for j, a in enumerate(props):
        c = c_prev + a
        if c > thr:
            nonzero = sum(1 for p in props if p > 0)
            margin = None if nonzero < 2 else min(thr - c_prev, c - thr) / a0
            return j, margin
        c_prev = c
    raise RuntimeError("the channel rule chose no channel")


def channel_rule_float(props, u2):
    """The spec's rule in binary64: the first j with c_j > min(u2 a0, nextafter(a0, 0))."""
    a0 = 0.0
    for a in props:
        a0 += a
    thr = min(u2 * a0, math.nextafter(a0, 0.0))
    c = 0.0
    for j, a in enumerate(props):
        c += a
        if c > thr:
            return j
    raise RuntimeError("the binary64 channel rule chose no channel")


def run_closed_form(world, draws, digits=DIGITS):
    """Every event to the horizon and the samples, in decimal arithmetic at `digits` digits."""
    _check_reads(world)
    ctx = decimal.Context(prec=digits, rounding=decimal.ROUND_HALF_EVEN, Emin=-999999, Emax=999999,
                          traps=[decimal.InvalidOperation, decimal.DivisionByZero, decimal.Overflow])
    with decimal.localcontext(ctx):
        horizon = D(world["horizon_s"])
        chans = world["channels"]
        counts = {s["id"]: int(world["initial_counts"][s["id"]]) for s in world["unit_states"]}
        x = (D(world["initial_amounts_fmol"]["cell"]), D(world["initial_amounts_fmol"]["node"]))
        t = D(0)
        totals = (D(0), D(0), D(0))                 # transferred, produced, cleared
        starts = [(t, x, totals, dict(counts))]     # each stretch's start (H = 0 there)
        events, extra = [], []
        k = 0
        while True:
            if k >= len(draws["u1"]):
                raise RuntimeError("the draws ran out before the horizon")
            seg = ClosedFormSegment(world, counts, digits)
            target = -D(draws["u1"][k]).ln()
            tau = seg.solve(x, target, tau_max=horizon - t)
            if tau is None:
                beyond = seg.solve(x, target)
                next_event = t + beyond
                break
            x_new, integral = seg.propagate(x, tau)
            inc = seg.increments(tau, integral)
            totals = tuple(totals[i] + inc[i] for i in range(3))
            t = t + tau
            props = seg.propensities(x_new)
            j, margin = channel_rule_exact(props, draws["u2"][k])
            j_float = channel_rule_float([float(p) for p in props], draws["u2"][k])
            hazard = seg.hazard(tau, integral)
            counts = jump(counts, chans[j])
            events.append({"k": k, "t": t, "channel": j, "counts_after": dict(counts), "x": x_new,
                           "totals": totals})
            extra.append({"k": k, "E": target, "hazard_residual": hazard - target, "props": props,
                          "a0": sum(props, D(0)), "margin": margin, "channel_float": j_float,
                          "u1_hex": draws["u1_hex"][k], "u2_hex": draws["u2_hex"][k]})
            x = x_new
            starts.append((t, x, totals, dict(counts)))
            k += 1

        samples = []
        for ts in world["sample_times_s"]:
            ts = D(ts)
            t0, x0, tot0, n0 = [s for s in starts if s[0] <= ts][-1]
            seg = ClosedFormSegment(world, n0, digits)
            tau = ts - t0
            xs, integral = seg.propagate(x0, tau)
            inc = seg.increments(tau, integral)
            samples.append({"t": ts, "x": xs, "totals": tuple(tot0[i] + inc[i] for i in range(3)),
                            "counts": dict(n0), "hazard": seg.hazard(tau, integral)})
        return {"events": events, "event_extra": extra, "samples": samples, "next_event": next_event,
                "next_k": k, "digits": digits}


# ----------------------------------------------------------------------------------------------
# The ODE with the hazard appended, in binary64 (scipy).
# ----------------------------------------------------------------------------------------------

def _float_propensities(world, n_cell, n_node, counts):
    """a_j = k_j prod ff(n, r) phi_j, phi_j = c_read/(1 mM) for a read, c = n/V at the state."""
    conc = {"cell": n_cell / world["volumes_pL"]["cell"], "node": n_node / world["volumes_pL"]["node"]}
    out = []
    for ch in world["channels"]:
        a = float(ch["rate_constant_per_s"])
        for s, r in ch["reactants"].items():
            a *= falling_factorial(counts[s], r)
        if ch["read"] is not None:
            a *= conc[ch["read"]["at"]] / 1.0
        out.append(a)
    return out


def _ode_rhs(world, counts):
    """y = (n_cell, n_node, H, transferred, produced, cleared), from part3.json's `system`."""
    v_cell, v_node = world["volumes_pL"]["cell"], world["volumes_pL"]["node"]
    g = world["transfer"]["conductance_pL_per_s_per_unit"]
    big_g = sum(g[s] * counts[s] for s in counts)
    p_cell, k_node = _turnover(world)

    def rhs(t, y):
        n_cell, n_node = y[0], y[1]
        flux = big_g * (n_cell / v_cell - n_node / v_node)
        a0 = sum(_float_propensities(world, n_cell, n_node, counts))
        return np.array([-flux + p_cell, flux - k_node * n_node, a0, flux, p_cell, k_node * n_node])

    # the right-hand side is affine in y, so its Jacobian is exact from unit vectors
    zero = rhs(0.0, np.zeros(6))
    jac = np.column_stack([rhs(0.0, np.eye(6)[i]) - zero for i in range(6)])
    return rhs, jac


def _integrate(rhs, jac, t0, t1, y0, method, rtol, atol, events=None):
    kw = {"jac": jac} if method in ("Radau", "BDF", "LSODA") else {}
    sol = solve_ivp(rhs, (t0, t1), y0, method=method, rtol=rtol, atol=atol, events=events, **kw)
    if sol.status < 0:
        raise RuntimeError(f"solve_ivp failed: {sol.message}")
    return sol


def run_ode(world, draws, method="Radau", rtol=ODE_RTOL, atol=ODE_ATOL):
    """Every event to the horizon and the samples by solve_ivp with H appended."""
    _check_reads(world)
    horizon = float(world["horizon_s"])
    chans = world["channels"]
    counts = {s["id"]: int(world["initial_counts"][s["id"]]) for s in world["unit_states"]}
    y = np.array([world["initial_amounts_fmol"]["cell"], world["initial_amounts_fmol"]["node"], 0, 0, 0, 0],
                 dtype=float)
    t = 0.0
    starts = [(t, y.copy(), dict(counts))]
    events = []
    newton_steps = []
    k = 0
    while True:
        rhs, jac = _ode_rhs(world, counts)
        target = -math.log(draws["u1"][k])

        def crossing(_t, yy, target=target):
            return yy[2] - target
        crossing.terminal = True
        crossing.direction = 1

        sol = _integrate(rhs, jac, t, horizon, y, method, rtol, atol, events=crossing)
        if sol.status == 0:
            break
        te = float(sol.t_events[0][0])
        for it in range(8):
            ye = _integrate(rhs, jac, t, te, y, method, rtol, atol).y[:, -1]
            rate = sum(_float_propensities(world, ye[0], ye[1], counts))
            dt = -(ye[2] - target) / rate
            te += dt
            if abs(dt) <= 1e-15 * max(1.0, te):
                break
        newton_steps.append(it + 1)
        if te > horizon:
            break
        ye = _integrate(rhs, jac, t, te, y, method, rtol, atol).y[:, -1]
        props = _float_propensities(world, ye[0], ye[1], counts)
        j = channel_rule_float(props, draws["u2"][k])
        counts = jump(counts, chans[j])
        t = te
        y = ye.copy()
        y[2] = 0.0
        events.append({"k": k, "t": t, "channel": j, "counts_after": dict(counts), "x": (y[0], y[1]),
                       "totals": (y[3], y[4], y[5])})
        starts.append((t, y.copy(), dict(counts)))
        k += 1
        if k >= len(draws["u1"]):
            raise RuntimeError("the draws ran out before the horizon")

    samples = []
    for ts in world["sample_times_s"]:
        t0, y0, n0 = [s for s in starts if s[0] <= ts][-1]
        rhs, jac = _ode_rhs(world, n0)
        ys = y0 if ts == t0 else _integrate(rhs, jac, t0, float(ts), y0, method, rtol, atol).y[:, -1]
        samples.append({"t": float(ts), "x": (ys[0], ys[1]), "totals": (ys[3], ys[4], ys[5]),
                        "counts": dict(n0), "hazard": ys[2]})
    return {"events": events, "samples": samples, "method": method, "rtol": rtol, "atol": atol,
            "newton_iterations_max": max(newton_steps) if newton_steps else 0}


# ----------------------------------------------------------------------------------------------
# Comparison, output.
# ----------------------------------------------------------------------------------------------

def _amounts(rec, turnover):
    vals = [rec["x"][0], rec["x"][1], rec["totals"][0]]
    if turnover:
        vals += [rec["totals"][1], rec["totals"][2]]
    return [float(v) for v in vals]


def compare_runs(ref, other, turnover):
    """The largest differences of `other` from `ref` over the events and the samples."""
    out = {"events_ref": len(ref["events"]), "events_other": len(other["events"])}
    same = len(ref["events"]) == len(other["events"]) and all(
        a["channel"] == b["channel"] and a["counts_after"] == b["counts_after"]
        for a, b in zip(ref["events"], other["events"]))
    out["same_events_channels_and_counts"] = same
    if not same:
        return out
    dt, da, dr = 0.0, 0.0, 0.0
    for part in ("events", "samples"):
        for a, b in zip(ref[part], other[part]):
            if part == "events":
                dt = max(dt, abs(float(a["t"]) - float(b["t"])))
            elif a["counts"] != b["counts"]:
                out["same_sample_counts"] = False
            for u, v in zip(_amounts(a, turnover), _amounts(b, turnover)):
                da = max(da, abs(u - v))
                if u != 0.0:
                    dr = max(dr, abs(u - v) / abs(u))
                elif v != 0.0:
                    dr = math.inf
    out.update({"max_event_time_diff_s": dt, "max_amount_diff_fmol": da, "max_amount_rel_diff": dr})
    out.setdefault("same_sample_counts", True)
    return out


def compare_closed_forms(fine, coarse, turnover):
    """The closed form at two precisions, compared in decimal (its arithmetic error, not a check
    of the derivation): the largest differences in event times and amounts, before rounding."""
    out = {"same_events_channels_and_counts": len(fine["events"]) == len(coarse["events"]) and all(
        a["channel"] == b["channel"] and a["counts_after"] == b["counts_after"]
        for a, b in zip(fine["events"], coarse["events"]))}
    if not out["same_events_channels_and_counts"]:
        return out
    with decimal.localcontext(decimal.Context(prec=fine["digits"] + 10)):
        dt, da, dr = D(0), D(0), D(0)
        for part in ("events", "samples"):
            for a, b in zip(fine[part], coarse[part]):
                dt = max(dt, abs(a["t"] - b["t"]))
                amounts = list(zip(a["x"] + a["totals"][:1], b["x"] + b["totals"][:1]))
                if turnover:
                    amounts += list(zip(a["totals"][1:], b["totals"][1:]))
                for u, v in amounts:
                    da = max(da, abs(u - v))
                    if u != 0:
                        dr = max(dr, abs(u - v) / abs(u))
        out.update({"digits": [fine["digits"], coarse["digits"]], "max_event_time_diff_s": float(dt),
                    "max_amount_diff_fmol": float(da), "max_amount_rel_diff": float(dr)})
    return out


def _f(x):
    return float(x)


def _record(rec, turnover, names, counts_key):
    """The requested fields, in requested_outputs' order (events: counts first; samples: pools first)."""
    out = {}
    counts = {name: rec[counts_key][name] for name in names}
    if counts_key == "counts_after":
        out[counts_key] = counts
    out["cell_S_fmol"] = _f(rec["x"][0])
    out["node_S_fmol"] = _f(rec["x"][1])
    if counts_key == "counts":
        out[counts_key] = counts
    out["transferred_fmol"] = _f(rec["totals"][0])
    if turnover:
        out["turnover_produced_fmol"] = _f(rec["totals"][1])
        out["turnover_cleared_fmol"] = _f(rec["totals"][2])
    return out


def _git(*args):
    try:
        return subprocess.run(["git", "-C", str(HERE), *args], capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def provenance():
    dirty = _git("status", "--porcelain", "--", *[str(HERE.parents[2] / p) for p in CODE_PATHS])
    return {
        "spec_commit": SPEC_COMMIT,
        "spec_unchanged_at_code_commit": _git("diff", "--quiet", SPEC_COMMIT, "HEAD", "--",
                                              str(SPEC_DIR)) is not None,
        "code_commit": _git("rev-parse", "HEAD"),
        "code_dirty_paths": [line[3:] for line in dirty.splitlines()] if dirty else [],
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def world_result(world, draws, prov):
    turnover = world["turnover"] is not None
    names = [s["id"] for s in world["unit_states"]]
    chan_ids = [ch["id"] for ch in world["channels"]]
    clock = {}
    t0 = time.perf_counter()
    cf = run_closed_form(world, draws, DIGITS)
    clock["closed_form_50"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    cf_check = run_closed_form(world, draws, DIGITS_CHECK)
    clock["closed_form_70"] = time.perf_counter() - t0
    odes = {}
    for label, method, rtol in (("radau", "Radau", ODE_RTOL), ("dop853", "DOP853", ODE_RTOL),
                                ("dop853_tight", "DOP853", ODE_TIGHT_RTOL)):
        t0 = time.perf_counter()
        odes[label] = run_ode(world, draws, method, rtol, ODE_ATOL)
        clock[label] = time.perf_counter() - t0

    events = []
    for ev in cf["events"]:
        row = {"k": ev["k"], "time_s": _f(ev["t"]), "channel": chan_ids[ev["channel"]]}
        row.update(_record(ev, turnover, names, "counts_after"))
        events.append(row)
    samples = []
    for sm in cf["samples"]:
        row = {"time_s": _f(sm["t"])}
        row.update(_record(sm, turnover, names, "counts"))
        samples.append(row)

    # the closed form's own checks, at its working precision
    init = (D(world["initial_amounts_fmol"]["cell"]), D(world["initial_amounts_fmol"]["node"]))
    prod_rate = D(_turnover(world)[0])
    with decimal.localcontext(decimal.Context(prec=DIGITS)):
        cons = D(0)
        for rec in cf["events"] + cf["samples"]:
            (nc, nn), (tr, pr, cl) = rec["x"], rec["totals"]
            cons = max(cons, abs(nc + nn + cl - pr - init[0] - init[1]),
                       abs(tr - (init[0] + pr - nc)), abs(pr - prod_rate * rec["t"]))
    margins = [e["margin"] for e in cf["event_extra"] if e["margin"] is not None]
    times = [ev["t"] for ev in cf["events"]]
    sample_gaps = [abs(D(ts) - te) for ts in world["sample_times_s"] for te in times]
    last_t = times[-1] if times else D(0)
    visited = sorted({tuple(ev["counts_after"][n] for n in names) for ev in cf["events"]}
                     | {tuple(world["initial_counts"][n] for n in names)})
    sub = {s["id"]: s["subunits"] for s in world["unit_states"]}

    acc = {
        "target": dict(TARGET),
        "closed_form_vs_radau": compare_runs(cf, odes["radau"], turnover),
        "closed_form_vs_dop853": compare_runs(cf, odes["dop853"], turnover),
        "closed_form_vs_dop853_rtol_1e-13": compare_runs(cf, odes["dop853_tight"], turnover),
        "radau_vs_dop853": compare_runs(odes["radau"], odes["dop853"], turnover),
        "closed_form_50_vs_70_digits_arithmetic_only": compare_closed_forms(cf_check, cf, turnover),
        "closed_form_50_vs_70_digits_after_rounding_to_binary64": compare_runs(cf_check, cf, turnover),
    }
    radau = acc["closed_form_vs_radau"]
    acc["radau_meets_target"] = bool(
        radau["same_events_channels_and_counts"]
        and radau["max_event_time_diff_s"] <= TARGET["event_time_s"]
        and radau["max_amount_rel_diff"] <= TARGET["amount_relative"])
    arith = acc["closed_form_50_vs_70_digits_arithmetic_only"]
    acc["stated"] = (
        "events and samples are the closed form at 50 digits, rounded to binary64 (half an ulp). Against "
        f"the independent ODE (Radau, rtol {ODE_RTOL:g}) the largest differences are "
        f"{radau.get('max_event_time_diff_s', float('nan')):.2e} s in event times and "
        f"{radau.get('max_amount_rel_diff', float('nan')):.2e} relative "
        f"({radau.get('max_amount_diff_fmol', float('nan')):.2e} fmol) in amounts; the closed form's "
        "own arithmetic, 50 against 70 digits, differs by "
        f"{arith.get('max_event_time_diff_s', float('nan')):.1e} s "
        f"and {arith.get('max_amount_rel_diff', float('nan')):.1e} relative")

    method = {
        "values_from": "the closed form at 50 significant digits (decimal arithmetic), rounded to binary64",
        "closed_form": {
            "law": ("between events N is constant and x' = A x + p, A = [[-a, b], [a, -(b + k)]], "
                    "a = G/V_cell, b = G/V_node, p = (P_cell, 0); x(tau) = e^{A tau} x0 + tau phi1(A tau) p "
                    "and int_0^tau x = tau phi1(A tau) x0 + tau^2 phi2(A tau) p by Sylvester's formula on "
                    "the eigenvalues of A (A = diag(0, -k) when G = 0); H, the transferred, produced and "
                    "cleared amounts are linear in int x"),
            "arithmetic": ("Python decimal at 50 significant digits; declared values and draws enter as "
                           "their exact binary64 values; E_k = -ln(u1_k) at that precision"),
            "event_location": ("bracketed, safeguarded Newton on H(tau) - E_k (H' = a0 > 0), stopped at "
                               "|delta tau| <= 1e-45 s (relative to max(1, tau)); hazard residual at each "
                               "event in diagnostics"),
            "channel_rule": ("the spec's rule at the crossing state in exact arithmetic, and in binary64 "
                             "with the nextafter guard as a check (diagnostics: channel_float_agrees)"),
        },
        "ode": {
            "integrator": (f"scipy.integrate.solve_ivp Radau, rtol {ODE_RTOL:g}, atol {ODE_ATOL:g}, the "
                           "Jacobian of the affine right-hand side exact from unit vectors"),
            "state": "(n_cell, n_node, H, transferred, produced, cleared); H restarts at 0 after each event",
            "event_location": ("solve_ivp's terminal event H - E_k (brentq on the dense output, xtol 4 eps), "
                               "then Newton on H(t) - E_k, H at the end point of a re-integration from the "
                               "previous event, stopped at |delta t| <= 1e-15 max(1, t) s"),
            "channel_rule": "the spec's rule in binary64 at the ODE's crossing state",
        },
        "cross_checks": [
            "the ODE (Radau, as above) against the closed form: accuracy.closed_form_vs_radau",
            f"DOP853 at the same tolerances, and at rtol {ODE_TIGHT_RTOL:g}",
            "the closed form at 70 digits (arithmetic only, not a check of the derivation)",
        ],
        "seconds": {k: round(v, 3) for k, v in clock.items()},
    }

    diag = {
        "events_up_to_horizon": len(events),
        "draws_consulted": cf["next_k"] + 1,
        "next_event_after_horizon": {"k": cf["next_k"], "time_s": _f(cf["next_event"])},
        "horizon_minus_last_event_s": _f(D(world["horizon_s"]) - last_t),
        "next_event_minus_horizon_s": _f(cf["next_event"] - D(world["horizon_s"])),
        "min_distance_event_to_sample_time_s": _f(min(sample_gaps)) if sample_gaps else None,
        "min_channel_margin_relative": _f(min(margins)) if margins else None,
        "competing_channel_events": len(margins),
        "channel_float_agrees": all(e["channel_float"] == ev["channel"]
                                    for e, ev in zip(cf["event_extra"], cf["events"])),
        "max_hazard_residual": _f(max((abs(e["hazard_residual"]) for e in cf["event_extra"]), default=D(0))),
        "max_conservation_residual_fmol": _f(cons),
        "counts_visited": [dict(zip(names, v)) for v in visited],
        "subunits_conserved": len({sum(sub[n] * v[i] for i, n in enumerate(names)) for v in visited}) == 1,
        "ode_newton_iterations_max": {k: v["newton_iterations_max"] for k, v in odes.items()},
    }
    event_diag = []
    for e in cf["event_extra"]:
        event_diag.append({
            "k": e["k"], "u1_hex": e["u1_hex"], "u2_hex": e["u2_hex"], "hazard_threshold": _f(e["E"]),
            "propensities_at_crossing": {cid: _f(p) for cid, p in zip(chan_ids, e["props"])},
            "total_rate_at_crossing": _f(e["a0"]),
            "channel_margin_relative": None if e["margin"] is None else _f(e["margin"]),
        })
    sample_diag = [{"time_s": _f(s["t"]), "hazard_since_last_event": _f(s["hazard"])} for s in cf["samples"]]

    return {
        "kind": "cells.fr43_part3_reference_result@1",
        "world": world["id"],
        "events": events,
        "samples": samples,
        "method": method,
        "accuracy": acc,
        "diagnostics": diag,
        "event_diagnostics": event_diag,
        "sample_diagnostics": sample_diag,
        "provenance": prov,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--worlds", default="", help="comma-separated world ids (default: all)")
    parser.add_argument("--routes", default="scratch,jax", help="the premise check's routes")
    parser.add_argument("--out", default=str(RESULTS_DIR))
    args = parser.parse_args(argv)
    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    check = stream_draws.premise_check(tuple(r for r in args.routes.split(",") if r))
    with open(out_dir / "draws_check.json", "w") as f:
        json.dump(check, f, indent=1)
        f.write("\n")
    if not check["identical"]:
        print("the premise check failed: the draws differ from spec/draws.json")
        return 1
    print("premise check: draws identical (" + ", ".join(check["routes"]) + ")")

    spec = stream_draws.load_spec()
    draws = stream_draws.load_draws()
    wanted = {w for w in args.worlds.split(",") if w}
    prov = provenance()
    for world in spec["worlds"]:
        if wanted and world["id"] not in wanted:
            continue
        result = world_result(world, draws[world["id"]], prov)
        with open(out_dir / f"{world['id']}.json", "w") as f:
            json.dump(result, f, indent=1)
            f.write("\n")
        acc = result["accuracy"]["closed_form_vs_radau"]
        print(f"{world['id']}: {len(result['events'])} events; closed form vs Radau: "
              f"dt {acc.get('max_event_time_diff_s')}, d amount rel {acc.get('max_amount_rel_diff')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
