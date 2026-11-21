"""R-noise (sheet §6): an exact stochastic simulation in counts, and its deterministic mean.

Two worlds, the factors frozen and the machines counted:
- A1's phase 1 over [0, 10 800 s]: 10⁴ polymerases, 10⁶ ribosomes; outputs every 60 s;
- the polymerase-limited world at T = 10 over [0, 3600 s]: 100 polymerases; outputs every 30 s.
  Its system is linear in counts, so its exact mean is the deterministic one (the control).

The simulation is Gillespie's direct method. Each replicate has its own PCG64 stream, spawned from
the recorded master seed, and draws two uniforms per event (the waiting time, then the reaction).
The replicates advance together, one event each per pass (`simulate`); `simulate_scalar` is the
same algorithm one replicate at a time, used to show that a replicate's counts do not depend on
the batch. Within a chain, the stage that exits is drawn in proportion to its complexes, which is
the direct method on the stage exits κ₀ c_j grouped by their common rate.

Propensities (per second): initiation λ f_pol and k_I_tl c₁ N_R f_rib; a stage exit κ₀ c_j; a
degradation k₀ N. All are the sheet's.
"""

from __future__ import annotations

import math
from decimal import Decimal as D
from decimal import localcontext

import numpy as np
from scipy.integrate import DOP853

from . import closed_forms, sheet

BLOCK = 4096  # uniforms drawn per refill of a replicate's stream


def params(pot: sheet.Potentials, world: str) -> dict:
    """The frozen system's constants, from the sheet (`world` is 'A1' or 'T10')."""
    a, m = sheet.A1, sheet.A1M
    times = list(range(0, a["t_off"] + 1, a["dt_out"])) if world == "A1" else list(
        range(0, m["t_end_pol"] + 1, m["dt_pol"]))
    with localcontext() as ctx:
        ctx.prec = 50
        f = closed_forms.Frozen(pot)
        if world == "A1":
            fr = closed_forms.a1_limit(pot, [0, 60], 50)["frozen"]
            p = {"lam": float(D(fr["lambda_tx"])), "kap_tx": float(D(fr["kappa0_tx"])),
                 "k_R": float(D(fr["k0_R"])), "kap_tl": float(D(fr["kappa0_tl"])),
                 "k_P": float(D(fr["k0_P"])),
                 "k_tl": float(D(a["k_I_tl"]) * f.c1),  # per (mRNA copy × free ribosome)
                 "m_tx": a["m_tx"], "m_tl": a["m_tl"], "M_pol": int(D(a["M_pol"])),
                 "M_rib": int(D(a["M_rib"]))}
        else:
            c = {"N": m["c_N"], "Pi": a["c_Pi"]}
            x_tx = f.x_tx(c)
            phi = f.sat(c["N"], a["K_N_tx"]) * (1 - x_tx.exp())
            y_R = f.y_deg(a["L_R"], "M", "R_res", a["c_M"], a["c_R"])
            p = {"lam": float(10 * D(m["k_I_tx"]) * f.c1),
                 "kap_tx": float(D(a["v_tx"]) / (a["L_R"] // a["m_tx"]) * phi),
                 "k_R": float(D(a["k_R"]) * (1 - y_R.exp())), "m_tx": a["m_tx"],
                 "M_pol": int(D(m["M_pol"]))}
    p["world"] = world
    p["times"] = times
    return p


class _Streams:
    """One PCG64 generator per replicate, consumed in order, refilled in blocks."""

    def __init__(self, seeds):
        self.gens = [np.random.Generator(np.random.PCG64(s)) for s in seeds]
        self.buf = np.stack([g.random(BLOCK) for g in self.gens])
        self.ptr = np.zeros(len(self.gens), dtype=np.int64)

    def next(self, idx: np.ndarray) -> np.ndarray:
        full = idx[self.ptr[idx] >= BLOCK]
        for i in full:
            self.buf[i] = self.gens[i].random(BLOCK)
            self.ptr[i] = 0
        u = self.buf[idx, self.ptr[idx]]
        self.ptr[idx] += 1
        return u


def replicate_seeds(world: str, n: int = sheet.NOISE_REPLICATES):
    """numpy SeedSequence(master).spawn(2)[w].spawn(n): w = 0 for A1, 1 for T = 10."""
    w = {"A1": 0, "T10": 1}[world]
    return np.random.SeedSequence(sheet.NOISE_MASTER_SEED).spawn(2)[w].spawn(n)


def _pick_stage(c: np.ndarray, r: np.ndarray) -> np.ndarray:
    """The first stage j with Σ_{i≤j} c_i > r (r in complexes), guarded against rounding."""
    cs = np.cumsum(c, axis=1)
    j = (cs <= r[:, None]).sum(axis=1)
    over = j >= c.shape[1]
    if over.any():  # r reached the total by rounding: the last occupied stage
        last = c.shape[1] - 1 - np.argmax(c[over][:, ::-1] > 0, axis=1)
        j[over] = last
    return j


def simulate(p: dict, seeds) -> np.ndarray:
    """All replicates together, one event each per pass: counts (replicate, output, readout).

    A replicate that has passed its last output keeps drawing events that are never recorded, so
    every replicate's recorded counts depend on its own stream alone.
    """
    R = len(seeds)
    times = np.asarray(p["times"], dtype=float)
    n_out = len(times)
    A1 = p["world"] == "A1"
    out = np.zeros((R, n_out, 6 if A1 else 3), dtype=np.int64)
    st = _Streams(seeds)
    rows = np.arange(R)
    m_tx = p["m_tx"]
    f_pol = np.full(R, p["M_pol"], dtype=np.int64)
    c_tx = np.zeros((R, m_tx), dtype=np.int64)
    e_tx = np.zeros(R, dtype=np.int64)
    n_R = np.zeros(R, dtype=np.int64)
    if A1:
        m_tl = p["m_tl"]
        f_rib = np.full(R, p["M_rib"], dtype=np.int64)
        c_tl = np.zeros((R, m_tl), dtype=np.int64)
        e_tl = np.zeros(R, dtype=np.int64)
        n_P = np.zeros(R, dtype=np.int64)
    t = np.zeros(R)
    k_out = np.zeros(R, dtype=np.int64)
    lam, kap_tx, kR = p["lam"], p["kap_tx"], p["k_R"]
    if A1:
        k_tl, kap_tl, kP = p["k_tl"], p["kap_tl"], p["k_P"]
    while (k_out < n_out).any():
        a_ti = lam * f_pol
        a_tx = kap_tx * e_tx
        a_dR = kR * n_R
        if A1:
            a_li = k_tl * n_R * f_rib
            a_tl = kap_tl * e_tl
            a_dP = kP * n_P
            a0 = a_ti + a_tx + a_dR + a_li + a_tl + a_dP
        else:
            a0 = a_ti + a_tx + a_dR
        u1 = st.next(rows)
        u2 = st.next(rows)
        with np.errstate(divide="ignore"):
            t_next = t + (-np.log1p(-u1)) / a0
        # Record every output passed before the next event (the state holds until then).
        due = k_out < n_out
        due[due] = times[k_out[due]] < t_next[due]
        while due.any():
            i = rows[due]
            if A1:
                out[i, k_out[i]] = np.stack([f_pol[i], f_rib[i], e_tx[i], e_tl[i], n_R[i], n_P[i]],
                                            axis=1)
            else:
                out[i, k_out[i]] = np.stack([f_pol[i], e_tx[i], n_R[i]], axis=1)
            k_out[i] += 1
            due = k_out < n_out
            due[due] = times[k_out[due]] < t_next[due]
        t = t_next
        r = u2 * a0
        b1 = a_ti
        b2 = b1 + a_tx
        b3 = b2 + a_dR
        g_ti = r < b1
        g_tx = ~g_ti & (r < b2)
        g_dR = ~g_ti & ~g_tx & (r < b3)
        if g_ti.any():
            i = rows[g_ti]
            f_pol[i] -= 1
            c_tx[i, 0] += 1
            e_tx[i] += 1
        if g_tx.any():
            i = rows[g_tx]
            j = _pick_stage(c_tx[i], (r[i] - b1[i]) / kap_tx)
            c_tx[i, j] -= 1
            last = j == m_tx - 1
            c_tx[i[~last], j[~last] + 1] += 1
            il = i[last]
            f_pol[il] += 1
            e_tx[il] -= 1
            n_R[il] += 1
        if g_dR.any():
            n_R[g_dR] -= 1
        if A1:
            rest = ~g_ti & ~g_tx & ~g_dR
            b4 = b3 + a_li
            b5 = b4 + a_tl
            g_li = rest & (r < b4)
            g_tl = rest & ~g_li & (r < b5)
            g_dP = rest & ~g_li & ~g_tl
            if g_li.any():
                i = rows[g_li]
                f_rib[i] -= 1
                c_tl[i, 0] += 1
                e_tl[i] += 1
            if g_tl.any():
                i = rows[g_tl]
                j = _pick_stage(c_tl[i], (r[i] - b4[i]) / kap_tl)
                c_tl[i, j] -= 1
                last = j == m_tl - 1
                c_tl[i[~last], j[~last] + 1] += 1
                il = i[last]
                f_rib[il] += 1
                e_tl[il] -= 1
                n_P[il] += 1
            if g_dP.any():
                n_P[g_dP] -= 1
    return out


def simulate_scalar(p: dict, seed) -> np.ndarray:
    """One replicate, event by event: the same algorithm and the same stream as `simulate`."""
    g = np.random.Generator(np.random.PCG64(seed))
    buf, ptr = g.random(BLOCK), 0
    times = p["times"]
    A1 = p["world"] == "A1"
    m_tx = p["m_tx"]
    f_pol, c_tx, n_R = p["M_pol"], [0] * m_tx, 0
    if A1:
        m_tl = p["m_tl"]
        f_rib, c_tl, n_P = p["M_rib"], [0] * m_tl, 0
    out = []
    t, k = 0.0, 0

    def uni():
        nonlocal buf, ptr
        if ptr >= BLOCK:
            buf, ptr = g.random(BLOCK), 0
        ptr += 1
        return float(buf[ptr - 1])

    def pick(c, rr):
        acc = 0
        for jj, cj in enumerate(c):
            acc += cj
            if acc > rr:
                return jj
        return max(jj for jj, cj in enumerate(c) if cj > 0)

    while k < len(times):
        e_tx = sum(c_tx)
        a_ti, a_tx, a_dR = p["lam"] * f_pol, p["kap_tx"] * e_tx, p["k_R"] * n_R
        if A1:
            e_tl = sum(c_tl)
            a_li, a_tl, a_dP = p["k_tl"] * n_R * f_rib, p["kap_tl"] * e_tl, p["k_P"] * n_P
            a0 = a_ti + a_tx + a_dR + a_li + a_tl + a_dP
        else:
            a0 = a_ti + a_tx + a_dR
        u1, u2 = uni(), uni()
        t_next = t + float(-np.log1p(np.array([-u1]))[0]) / a0 if a0 > 0 else math.inf
        while k < len(times) and times[k] < t_next:
            out.append([f_pol, f_rib, e_tx, e_tl, n_R, n_P] if A1 else [f_pol, e_tx, n_R])
            k += 1
        if k >= len(times):
            break
        t = t_next
        r = u2 * a0
        b1 = a_ti
        b2 = b1 + a_tx
        b3 = b2 + a_dR
        if r < b1:
            f_pol -= 1
            c_tx[0] += 1
        elif r < b2:
            j = pick(c_tx, (r - b1) / p["kap_tx"])
            c_tx[j] -= 1
            if j == m_tx - 1:
                f_pol += 1
                n_R += 1
            else:
                c_tx[j + 1] += 1
        elif r < b3:
            n_R -= 1
        elif A1:
            b4 = b3 + a_li
            b5 = b4 + a_tl
            if r < b4:
                f_rib -= 1
                c_tl[0] += 1
            elif r < b5:
                j = pick(c_tl, (r - b4) / p["kap_tl"])
                c_tl[j] -= 1
                if j == m_tl - 1:
                    f_rib += 1
                    n_P += 1
                else:
                    c_tl[j + 1] += 1
            else:
                n_P -= 1
    return np.array(out, dtype=np.int64)


def deterministic_mean(p: dict, rtol: float = 1e-13, prec: int = 50) -> np.ndarray:
    """The frozen system's ODE with the machines counted (F = M − E), from zero products.

    T = 10 is linear: e^(At) y(0) exactly, in decimal arithmetic. A1's initiation of translation
    is bilinear (N_R f_rib): DOP853 at the given rtol, outputs hit exactly.
    """
    times = p["times"]
    if p["world"] == "T10":
        m = p["m_tx"]
        n = m + 2  # f, c_1..c_m, n_R
        with localcontext() as ctx:
            ctx.prec = prec
            lam, kap, kR = D(repr(p["lam"])), D(repr(p["kap_tx"])), D(repr(p["k_R"]))
            A = [[D(0)] * n for _ in range(n)]
            A[0][0], A[0][m] = -lam, kap
            A[1][0], A[1][1] = lam, -kap
            for j in range(2, m + 1):
                A[j][j - 1], A[j][j] = kap, -kap
            A[m + 1][m], A[m + 1][m + 1] = kap, -kR
            dt = D(times[1] - times[0])
            E = closed_forms._expm([[x * dt for x in row] for row in A], prec)
            y = [D(p["M_pol"])] + [D(0)] * (n - 1)
            rows = []
            for k in range(len(times)):
                if k:
                    y = [sum(E[i][q] * y[q] for q in range(n)) for i in range(n)]
                rows.append([float(y[0]), float(sum(y[1:m + 1])), float(y[m + 1])])
        return np.array(rows)
    m_tx, m_tl = p["m_tx"], p["m_tl"]
    # y = (f_pol, c_tx[m], n_R, f_rib, c_tl[m], n_P), molecules.
    iR, iF2 = 1 + m_tx, 2 + m_tx
    iP = iF2 + 1 + m_tl

    def fun(t, y):
        dy = np.zeros_like(y)
        ti = p["lam"] * y[0]
        ex = p["kap_tx"] * y[1:1 + m_tx]
        dy[0] = -ti + ex[-1]
        dy[1] = ti - ex[0]
        dy[2:1 + m_tx] = ex[:-1] - ex[1:]
        dy[iR] = ex[-1] - p["k_R"] * y[iR]
        li = p["k_tl"] * y[iR] * y[iF2]
        el = p["kap_tl"] * y[iF2 + 1:iF2 + 1 + m_tl]
        dy[iF2] = -li + el[-1]
        dy[iF2 + 1] = li - el[0]
        dy[iF2 + 2:iF2 + 1 + m_tl] = el[:-1] - el[1:]
        dy[iP] = el[-1] - p["k_P"] * y[iP]
        return dy

    y = np.zeros(iP + 1)
    y[0], y[iF2] = p["M_pol"], p["M_rib"]
    scale = np.ones_like(y)
    scale[0], scale[iF2] = p["M_pol"], p["M_rib"]
    rows = [[y[0], y[iF2], y[1:iR].sum(), y[iF2 + 1:iP].sum(), y[iR], y[iP]]]
    for k in range(1, len(times)):
        s = DOP853(fun, times[k - 1], y, times[k], rtol=rtol, atol=rtol * scale)
        while s.status == "running":
            s.step()
        y = s.y.copy()
        rows.append([y[0], y[iF2], y[1:iR].sum(), y[iF2 + 1:iP].sum(), y[iR], y[iP]])
    return np.array(rows)


def band_report(counts: np.ndarray, det: np.ndarray) -> dict:
    """The sampling band of §6: |mean − det| ≤ 4.5 SE + 10/N at every output and readout."""
    N = counts.shape[0]
    mean = counts.mean(axis=0)
    sd = counts.std(axis=0, ddof=1)
    se = sd / math.sqrt(N)
    band = sheet.NOISE_BAND_SE * se + sheet.NOISE_FLOOR / N
    gap = np.abs(mean - det)
    return {"N": N, "mean": mean, "se": se, "det": det, "gap": gap, "band": band,
            "ratio": gap / band, "outside": int((gap > band).sum()), "comparisons": gap.size}
