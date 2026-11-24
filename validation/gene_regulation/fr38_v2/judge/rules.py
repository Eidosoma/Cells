"""The rules: READOUTS.md §3's scales, CRITERIA.md C1 to C4, and LAWS.md §6's route-2 forms.

C1 and C4 call the shared pair rule (`validation/assembly_lineages_v2/agreement.py`):
`judge_constant` bit for bit, and `judge_derived` with each bound stated from arithmetic. C2 and
C3 stand outside the pair rule, as FR-47's C1 does (CRITERIA.md §2).
"""

import math

import numpy as np

from validation.assembly_lineages_v2 import agreement

from . import spec

# ------------------------------------------------------------------ READOUTS.md §3's scales

HEATS = {
    "A": [
        "H_tx",
        "H_deg_R",
        "H_deg_R_s",
        "H_rel_tx_release_durable",
        "H_rel_tx_release_short_lived",
    ],
}
HEATS["B"] = HEATS["A"] + ["H_tl", "H_deg_P", "H_rc"]
HEATS["C"] = HEATS["A"] + ["H_store"]
HEATS["D"] = HEATS["A"] + ["H_water"]
ION_ROWS = ("K", "Y")  # family D: species rows that move only by dilution, μ° = 0 (LAWS.md §5)


def g_rows(profile, blank):
    """The rows whose term in G moves (READOUTS.md §3 with amendment 1, item 7)."""
    if profile == "B":
        return ["N", "M", "A", "ATP", "ADP", "Pi", "R", "R_s", "P"]
    if profile == "D":
        return ["N", "M", "Pi", "R", "R_s"] + list(ION_ROWS)
    rows = ["M", "R", "R_s"] if blank else ["N", "M", "Pi", "R", "R_s"]
    if profile == "C":
        rows.append("Mx")
    return rows


class ScaleContext:
    """The scales of one run's series (reference or engine), with its blank's for the excess."""

    def __init__(self, profile, inputs, values, *, blank, blank_values=None):
        self.profile, self.inputs, self.values = profile, inputs, values
        self.blank, self.blank_values = blank, blank_values
        n = len(next(iter(values.values())))
        self.n = n
        self.V = (
            np.asarray(values["V"]) if profile == "D" else np.full(n, float(inputs["volume_pL"]))
        )

    def _v(self, name):
        if name not in self.values:
            raise KeyError(name)
        return np.asarray(self.values[name], dtype=np.float64)

    def row_amount(self, row):
        if row in ION_ROWS:
            return np.full(
                self.n,
                float(self.inputs["cell_background_mM"][row]) * float(self.inputs["volume_pL"]),
            )
        return self._v(f"n_{row}")

    def mu0(self, row):
        if row in ION_ROWS:
            return 0.0
        if row == "Mx":
            return float(self.inputs["store"]["mu0_Mx_RT_at_1M"])
        return float(self.inputs["mu0_RT_at_1M"][row])

    def heat_series(self):
        tot = np.zeros(self.n)
        for h in HEATS[self.profile]:
            tot = tot + np.abs(self._v(h))
        if self.profile == "D":
            tot = tot + np.abs(self._v("W_bath"))
        return tot

    def heat_scale(self):
        return float(np.max(self.heat_series()))

    def rows_series(self, rows):
        tot = np.zeros(self.n)
        for row in rows:
            n = self.row_amount(row)
            if np.any(n <= 0.0):
                raise ValueError(f"row {row} is not strictly positive")
            tot = tot + n * spec.RT_KJ * (
                abs(self.mu0(row)) + np.abs(np.log(n / (self.V * spec.C_STANDARD_MM))) + 1.0
            )
        return tot

    def residue_series(self):
        L = spec.chain_length(self.inputs)
        r = (
            spec.RT_KJ
            * abs(spec.residue_potential(self.inputs))
            * (self._v("W_tx") + L * self._v("H_tx_release"))
        )
        if self.profile == "B" and spec.B_G_SCALE_TRANSLATION_RESIDUES:
            r = r + spec.RT_KJ * abs(float(self.inputs["mu_res_P_RT"])) * (
                self._v("W_tl") + self._v("W_tl_s")
            )
        return r

    def g_scale(self):
        rows = g_rows(self.profile, self.blank)
        return (
            self.heat_scale()
            + float(np.max(self.rows_series(rows)))
            + float(np.max(self.residue_series()))
        )

    def d_identity_scale(self):
        """Amendment 3, item 1: the bookings' magnitude plus every species row's G term."""
        return self.heat_scale() + float(np.max(self.rows_series(g_rows("D", self.blank))))

    def scale(self, kind, name=None):
        if kind == "amount":
            return float(np.max(np.abs(self._v(name))))
        if kind == "heat":
            return self.heat_scale()
        if kind == "G":
            return self.g_scale()
        head, _, arg = kind.partition(":")
        if head == "label":
            return float(np.max(np.abs(self.row_amount(arg))))
        if head == "excess":
            if self.blank_values is None:
                raise KeyError("the blank's series")
            return float(np.max(self._v(f"n_{arg}") + np.asarray(self.blank_values[f"n_{arg}"])))
        if head == "route2":
            return float(np.max(np.abs(self._v(f"int_Q_tx_release_{arg}"))))
        raise KeyError(f"scale kind {kind!r}")


# ------------------------------------------------------------------ C1, constants


def c1(values):
    """`agreement.judge_constant` against +0.0, bit for bit (the sign of zero included)."""
    values = np.asarray(values, dtype=np.float64)
    if values.size == 0:
        return {"replicas": 0, "replicas_off": 0, "passes": True, "fails": False}
    return agreement.judge_constant(values, 0.0)


def bit_equal(a, b):
    """The engine-only equalities of C1: entry for entry, judge_constant's bit rule."""
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    if a.shape != b.shape:
        return {"passes": False, "fails": True, "entries_off": None, "why": "shapes differ"}
    off = int(np.sum(a.view(np.uint64) != b.view(np.uint64)))
    return {"passes": off == 0, "fails": off > 0, "entries_off": off}


# ------------------------------------------------------------------ C2 and C3, stepped entries


def step_estimate(d1, d2, p):
    a = 2.0**p - 1.0
    return max(d1 / a, d2 / (2.0**p * a))


def rounding(steps_h, s_y):
    return 8.0 * spec.EPS * steps_h * s_y


def c2(y4h, y2h, yh, yref, acc, p, s_y, steps_h):
    """C2 for one readout over its compared times, with C3's order and the reported figures."""
    y4h, y2h, yh, yref = (np.asarray(x, dtype=np.float64) for x in (y4h, y2h, yh, yref))
    acc = np.asarray(acc, dtype=np.float64)
    d1 = float(np.max(np.abs(y2h - yh)))
    d2 = float(np.max(np.abs(y4h - y2h)))
    est = step_estimate(d1, d2, p)
    e_round = rounding(steps_h, s_y)
    e_ref = float(np.max(acc)) if acc.size else 0.0
    tau = 3.0 * est + e_ref + e_round
    gap = float(np.max(np.abs(yh - yref)))
    err_2h = float(np.max(np.abs(y2h - yref)))
    out = order(d1, d2, p, e_round)
    out.update(
        {
            "d1": d1,
            "d2": d2,
            "est": est,
            "e_round": e_round,
            "e_ref": e_ref,
            "tolerance": tau,
            "gap": gap,
            "passes": bool(gap <= tau),
            "s_y": s_y,
            "p": p,
            "error_2h": err_2h,
            "error_h": gap,
        }
    )
    ratio = err_2h / gap if gap > 0.0 else None
    out["error_ratio_2h_over_h"] = ratio
    out["saturated"] = bool(ratio is not None and ratio < 1.5 and gap > 10.0 * (e_ref + e_round))
    return out


def order(d1, d2, p, e_round, *, low=None):
    """C3: resolved where both differences exceed 10 e_round; q = log₂(d₂/d₁) in [p − 0.5, 3.5]."""
    resolved = bool(d1 > 10.0 * e_round and d2 > 10.0 * e_round)
    q = math.log2(d2 / d1) if (d1 > 0.0 and d2 > 0.0) else None
    lo = (p - 0.5) if low is None else low
    in_window = None if not resolved else bool(lo <= q <= spec.ORDER_WINDOW_TOP)
    eff = None if q is None else 3.0 * (2.0**q - 1.0) / (2.0**p - 1.0)
    return {
        "resolved": resolved,
        "q": q,
        "order_in_window": in_window,
        "window": [lo, spec.ORDER_WINDOW_TOP],
        "effective_factor": eff,
    }


# ------------------------------------------------------------------ route 2 (LAWS.md §6)


def _frac(x):
    """(1 − e^(−x))/x, with its limit 1 at x = 0."""
    return -math.expm1(-x) / x if x != 0.0 else 1.0


def known_rate(times, A, k, t1, t2, ts, idx=None):
    """Σ over kept outputs t1 ≤ t_i < t2 of (A_{i+1} − A_i) e^(−k (ts − t_{i+1}))
    (1 − e^(−k h))/(k h), h = t_{i+1} − t_i."""
    idx = list(range(len(times))) if idx is None else list(idx)
    total = 0.0
    for a, b in zip(idx[:-1], idx[1:], strict=True):
        if not (t1 <= times[a] < t2):
            continue
        h = times[b] - times[a]
        total += (A[b] - A[a]) * math.exp(-k * (ts - times[b])) * _frac(k * h)
    return total


def window_indices(times, t1, t2):
    return [i for i, t in enumerate(times) if t1 <= t <= t2]


def grid_error(times, A, k, t1, t2, ts):
    """|known_rate on every output − on every second output, t1, t2 and ts kept|; None where the
    window holds no output to drop (amendment 3, item 3d: then the entry is refused)."""
    times = list(times)
    if t1 not in times or t2 not in times or ts not in times:
        return None
    fine = window_indices(times, t1, t2)
    i1 = fine[0]
    coarse = sorted({i for i in fine if (i - i1) % 2 == 0} | {fine[0], fine[-1]})
    if coarse == fine:
        return None
    return abs(
        known_rate(times, A, k, t1, t2, ts, fine) - known_rate(times, A, k, t1, t2, ts, coarse)
    )


def net_rate_cohort(times, A, D, n, t1, t2, ts):
    """P1′: the same carry with each interval's net per-molecule rate (D_{i+1} − D_i)/∫n dt (the
    trapezoid); survivors carried interval by interval, with ΔA inside the window only."""
    S = 0.0
    for i in range(len(times) - 1):
        ta, tb = times[i], times[i + 1]
        if ta < t1 or ta >= ts:
            continue
        h = tb - ta
        k_i = (D[i + 1] - D[i]) / (0.5 * (n[i] + n[i + 1]) * h)
        x = k_i * h
        S = S * math.exp(-x) + ((A[i + 1] - A[i]) * _frac(x) if ta < t2 else 0.0)
    return S


# ------------------------------------------------------------------ C4, engine-only identities


def _derived(name, residual, bound, **extra):
    residual = np.asarray(residual, dtype=np.float64)
    res = agreement.judge_derived(residual, 0.0, float(bound))
    res.update({"identity": name, **extra})
    return res


def identities(values, inputs, profile, machine, steps, *, blank):
    """C4 on one record: the membership sum, §9.7's identities and (A, B and C) G's identity."""
    v = {k: np.asarray(x, dtype=np.float64) for k, x in values.items()}
    out = []
    eps, S = spec.EPS, float(steps)
    # the membership sum, per output: |Σ_c label − n_row| ≤ 128 ε n_row
    for row in ("R", "R_s"):
        tot = sum(v[f"label_{row}_{c}"] for c in spec.CLASSES)
        n = v[f"n_{row}"]
        worst, ok = 0.0, True
        for i in range(n.size):
            r = agreement.judge_derived(np.array([tot[i]]), float(n[i]), float(128.0 * eps * n[i]))
            worst = max(worst, r["largest_gap"] / n[i] if n[i] > 0 else math.inf)
            ok = ok and r["passes"]
        out.append(
            {
                "identity": f"membership_sum_{row}",
                "passes": ok,
                "fails": not ok,
                "largest_relative": worst,
                "bound_relative": 128.0 * eps,
            }
        )

    def bound(*terms):
        return spec.FLOOR_FMOL + 8.0 * eps * S * max(float(np.max(np.abs(t))) for t in terms)

    H, A = v["H_tx_release"], v["int_Q_tx"]
    Qd, Qs = v["int_Q_tx_release_durable"], v["int_Q_tx_release_short_lived"]
    H0 = np.full(H.size, H[0])
    out.append(_derived("hold", H0 + A - H - Qd - Qs, bound(H0, A, H, Qd, Qs)))
    lost, gained = 0.0, 0.0
    for fate, Q in (("durable", Qd), ("short_lived", Qs)):
        row = spec.FATE_ROW[fate]
        n, D = v[f"n_{row}"], v[f"int_D_{row}"]
        n0 = np.full(n.size, n[0])
        out.append(_derived(f"fate_row_{row}", n - n0 - Q + D, bound(n, n0, Q, D)))
        lost, gained = lost + D, gained + (n - n0)
    terms = (
        [H0, A, H] + [v[f"n_{r}"] for r in ("R", "R_s")] + [v[f"int_D_{r}"] for r in ("R", "R_s")]
    )
    out.append(_derived("producer", H0 + A - H - gained - lost, bound(*terms)))
    # machines: F + Σ_j C_j (+ H under held) = M, and E_tx = Σ_j C_j (+ H)
    Cs = sum(v[f"C_tx_{j}"] for j in range(1, 9))
    held = H if machine == "held" else np.zeros(H.size)
    M = np.full(H.size, spec.pool_fmol(inputs, "pol"))
    F, E = v["F_pol"], v["E_tx"]
    out.append(_derived("machines_pol", F + Cs + held - M, bound(F, Cs, held, M)))
    out.append(_derived("engaged_tx", E - Cs - held, bound(E, Cs, held)))
    if profile == "B":
        Ct = sum(v[f"C_tl_{j}"] for j in range(1, 9))
        Cts = sum(v[f"C_tl_s_{j}"] for j in range(1, 9))
        Mr = np.full(H.size, spec.pool_fmol(inputs, "rib"))
        Fr = v["F_rib"]
        out.append(_derived("machines_rib", Fr + Ct + Cts - Mr, bound(Fr, Ct, Cts, Mr)))
        out.append(_derived("engaged_tl", v["E_tl"] - Ct, bound(v["E_tl"], Ct)))
        out.append(_derived("engaged_tl_s", v["E_tl_s"] - Cts, bound(v["E_tl_s"], Cts)))
    if profile != "D":
        ctx = ScaleContext(profile, inputs, v, blank=blank)
        s_g = ctx.g_scale()
        heats = sum(v[h] for h in HEATS[profile])
        out.append(_derived("G", v["G_minus_G0"] + heats, 8.0 * eps * S * s_g, scale=s_g))
    return out


def d_identity_residual(values):
    """Family D (amendment 3, item 1): r = G − G(0) + U(V) − U(V₀) + Σ heats − W_bath, U = 0."""
    v = {k: np.asarray(x, dtype=np.float64) for k, x in values.items()}
    return v["G_minus_G0"] + sum(v[h] for h in HEATS["D"]) - v["W_bath"]
