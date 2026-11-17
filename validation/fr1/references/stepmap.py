"""A.4: the palindrome's step map for two-way first-order exchange, its fixed point and its
splitting term.

With x = n_c/N (N = n_c + n_o conserved), a = k_e and b = kappa:
- E(tau): x -> x e^{-a tau} (the first-order export over tau);
- I(tau): x -> 1 - (1 - x) e^{-b tau} (the first-order import over tau).

One half-step of length h is S(h) = E(h/2) I(h) E(h/2), and one composite step of length dt is
S(dt/2) twice. **The stage plan** follows the declaration: with no saturable route anywhere the
last stage is the first-order imports, as above (``plan="single"``); with a saturable route the
imports run as two halves around it, E(h/2) I(h/2) [saturable] I(h/2) E(h/2) (``plan="halves"``,
the saturable stage being identity when it moves nothing). The two plans are the same map in
exact arithmetic and differ at rounding.

**Fixed point.** S(x) = alpha(1 - beta) + alpha^2 beta x with alpha = e^{-a h/2} and
beta = e^{-b h}, so x* = alpha(1 - beta)/(1 - alpha^2 beta), against x_eq = b/(a + b). Expanding,
x*/x_eq - 1 = -a(a + 2b) h^2/24 + O(h^3), so the composite step's bias is -a(a + 2b) dt^2/96.

The iteration is given in 50-digit decimals (the map's truth) and in float64 in the moved-amount
form the design describes (moved = n (1 - e^{-k tau}); n_from -= moved; n_to += moved). The
float64 iteration's distance from the truth is the rounding the engine's own iteration can show;
``rounding_allowance`` bounds it at 4 ulps of N per stage.
"""

from __future__ import annotations

import math
from decimal import localcontext

import numpy as np

from .exact import DIGITS, UNIT_ROUNDOFF, dec


def _stages(plan: str) -> list:
    if plan == "single":
        return [("E", 0.5), ("I", 1.0), ("E", 0.5)]
    if plan == "halves":
        return [("E", 0.5), ("I", 0.5), ("I", 0.5), ("E", 0.5)]
    raise ValueError(f"unknown stage plan {plan!r}")


def iterate(n_c0, n_o0, a, b, dt, steps: int, plan: str = "single", every: int = 1) -> dict:
    """The composite step iterated ``steps`` times; amounts after every ``every`` steps.

    Returns ``n_c_fmol`` and ``n_o_fmol`` (decimal truth, rounded), their float64 iteration, and
    the step indices recorded (0 included).
    """
    stages = _stages(plan)
    with localcontext() as ctx:
        ctx.prec = DIGITS + 10
        h = dec(dt) / 2
        fac = {}
        for kind, frac in stages:
            rate = dec(a) if kind == "E" else dec(b)
            fac[(kind, frac)] = (-rate * h * dec(frac)).exp()
        nc, no = dec(n_c0), dec(n_o0)
        rec_idx, dec_c, dec_o = [0], [float(nc)], [float(no)]
        for s in range(1, steps + 1):
            for _half in range(2):
                for kind, frac in stages:
                    f = fac[(kind, frac)]
                    if kind == "E":
                        moved = nc * (1 - f)
                        nc, no = nc - moved, no + moved
                    else:
                        moved = no * (1 - f)
                        no, nc = no - moved, nc + moved
            if s % every == 0:
                rec_idx.append(s)
                dec_c.append(float(nc))
                dec_o.append(float(no))
    # float64, the moved-amount form
    h = float(dt) / 2
    facf = {(k, fr): -math.expm1(-(float(a) if k == "E" else float(b)) * h * fr)
            for k, fr in stages}
    fc, fo = float(n_c0), float(n_o0)
    flo_c, flo_o = [fc], [fo]
    for s in range(1, steps + 1):
        for _half in range(2):
            for kind, frac in stages:
                m = (fc if kind == "E" else fo) * facf[(kind, frac)]
                if kind == "E":
                    fc, fo = fc - m, fo + m
                else:
                    fo, fc = fo - m, fc + m
        if s % every == 0:
            flo_c.append(fc)
            flo_o.append(fo)
    return {"steps": np.array(rec_idx), "n_c_fmol": np.array(dec_c), "n_o_fmol": np.array(dec_o),
            "n_c_float64_fmol": np.array(flo_c), "n_o_float64_fmol": np.array(flo_o),
            "plan": plan, "stages_per_step": 2 * len(stages)}


def rounding_allowance(N, steps: int, plan: str = "single") -> float:
    """A bound on a float64 iteration's rounding: 4 ulps of N per stage, accumulated."""
    return 4.0 * UNIT_ROUNDOFF * abs(float(N)) * steps * 2 * len(_stages(plan))


def fixed_point(a, b, dt) -> dict:
    """x*, x_eq, the bias x*/x_eq - 1, and its leading term -a(a + 2b) dt^2/96, in decimals."""
    with localcontext() as ctx:
        ctx.prec = DIGITS
        A, B, h = dec(a), dec(b), dec(dt) / 2
        alpha = (-A * h / 2).exp()
        beta = (-B * h).exp()
        xs = alpha * (1 - beta) / (1 - alpha * alpha * beta)
        xeq = B / (A + B)
        bias = xs / xeq - 1
        lead = -A * (A + 2 * B) * dec(dt) * dec(dt) / 96
        return {"x_star": float(xs), "x_eq": float(xeq), "bias": float(bias),
                "leading_term": float(lead), "ratio": float(bias / lead)}
