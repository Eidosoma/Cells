"""FR-47's code-blind references, method 2: an independent float64 check of method 1.

Written from the spec folder ``validation/assembly_lineages_v2/fr47_spec/`` (SPEC.md, CRITERIA.md
and AMENDMENT-2026-11-23.md, fr47-protocol 59cb1a12) and ``docs/FR47_SHELL_EXCHANGE_PROTOCOL.md``
only. Nothing here imports, reads or runs the engine. Nothing is shared with ``fr47_exact.py``:
this module parses the inputs, derives the rates and builds every law in its own code, by
different routes.

- **Shell worlds:**
  - a molecule's law comes from the matrix exponential of its 2x2 generator, with the stops'
    maps;
  - each count's moments come from enumerating its probability mass function, the convolution
    of the founder places' binomials;
  - (d)'s mean trajectory comes from DOP853 on the rate equations, with the stops' maps.
- **Gated worlds:**
  - the exact moments come from the master equation's moment hierarchy E[y^j 1{K = k}], j <= 4,
    over every gate state k = 0..N_g (SPEC.md section 3.3's closed linear system), with y the
    lumen fraction measured from a smooth centring function c(t). This keeps the fourth moment
    free of cancellation;
  - the hierarchy is integrated by Radau with its sparse Jacobian: an implicit method, with no
    random norm estimates;
  - the mean field comes from DOP853 on its four rate equations.

Every routine is deterministic. Run it with one BLAS thread (the generator pins it).
"""

from __future__ import annotations

import math
from fractions import Fraction

import numpy as np
import scipy.linalg
import scipy.sparse
import scipy.stats
from scipy.integrate import Radau, solve_ivp

N_A = 6.02214076e23
M = 128
ODE_RTOL = 1e-13
HIER_RTOL = 1e-12
HIER_ATOL = 1e-14  # absolute, per scaled moment; tails below it carry no measurable moment


# --------------------------------------------------------------------------------------------
# Inputs, parsed independently
# --------------------------------------------------------------------------------------------


def num(text):
    if isinstance(text, int):
        return float(text)
    total = 0.0
    for term in text.split("+"):
        term = term.strip()
        if term.startswith("ln(") and term.endswith(")"):
            total += math.log(float(term[3:-1]))
        elif "/" in term:
            total += float(Fraction(term))
        else:
            total += float(term)
    return total


def world_f64(raw):
    w = dict(raw)
    w["Vout"] = num(raw["V_out_L"]) * 1e-3  # m^3
    w["Vin"] = num(raw["V_in_L"]) * 1e-3
    w["A"] = num(raw["A_sh_m2"])
    w["P"] = num(raw["P_s_m_per_s"])
    pots = raw["tracer_potentials_kBT"]
    w["mu_s"] = num(pots["solution"])
    w["mu_l"] = w["mu_s"] if pots["lumen"] is None else num(pots["lumen"])
    w["k_in"] = w["P"] * w["A"] / w["Vout"]
    w["k_out_bare"] = w["P"] * w["A"] / w["Vin"]
    w["k_out"] = w["k_out_bare"] * math.exp(w["mu_l"] - w["mu_s"])
    w["obs_t"] = [num(t) for t in raw["observation_times_s"]]
    w["T_end"] = num(raw["horizon_s"])
    w["stops_t"] = [
        (num(s["time_s"]), s["kind"], num(s["f"]) if s["kind"] == "withdrawal" else 1.0)
        for s in raw.get("stops", [])
    ]
    fo = raw["founder_molecules"]
    w["nP"], w["nL"] = fo["S@pool"], fo["S@lumen"]
    return w


# --------------------------------------------------------------------------------------------
# Shell worlds
# --------------------------------------------------------------------------------------------


def _events(w):
    ev = [(t, "obs", None) for t in w["obs_t"]] + list(w["stops_t"])
    ev.sort(key=lambda e: e[0])
    if not (w["obs_t"] and w["obs_t"][-1] == w["T_end"]):
        ev.append((w["T_end"], "horizon", None))
    return ev


def molecule_law(w, k_out, *, removal=None, lumen="none", freeze=False):
    """Row vectors over (pool, lumen) for a pool-born and a lumen-born molecule, propagated by
    expm of the generator; the removed and kept probabilities at each stop."""
    gen = np.array([[-w["k_in"], w["k_in"]], [k_out, -k_out]])
    out = {}
    for origin, v0 in (("pool", [1.0, 0.0]), ("lumen", [0.0, 1.0])):
        v = np.array(v0)
        t_prev, frozen = 0.0, False
        rec = {"obs": {}, "stops": {}, "pre": {}, "post": {}}
        for t, kind, f in _events(w):
            if not frozen and t > t_prev:
                v = v @ scipy.linalg.expm(gen * (t - t_prev))
            t_prev = t
            if kind == "obs":
                rec["obs"][t] = v.copy()
            elif kind == "horizon":
                pass
            else:
                rec["pre"][t] = v.copy()
                if kind == "withdrawal":
                    rho = f if removal is None else removal(f)
                    removed, kept = rho * v[0], (1.0 - rho) * v[0]
                    v = np.array([kept, v[1]])
                    if lumen == "every_stop":
                        removed += f * v[1]
                        v = np.array([v[0], (1.0 - f) * v[1]])
                else:
                    removed, kept = v[0], 0.0
                    v = np.array([0.0, v[1]])
                    if lumen != "none":
                        removed += v[1]
                        v = np.array([0.0, 0.0])
                    if freeze:
                        frozen = True
                rec["stops"][t] = (removed, kept)
                rec["post"][t] = v.copy()
        rec["end"] = v.copy()
        out[origin] = rec
    return out


def pmf_moments(groups):
    """Mean, var and mu4 by enumerating the pmf of a sum of independent binomials."""
    pmf = np.array([1.0])
    for n, p in groups:
        if n == 0:
            continue
        p = min(max(p, 0.0), 1.0)
        part = scipy.stats.binom.pmf(np.arange(n + 1), n, p)
        pmf = np.convolve(pmf, part)
    k = np.arange(pmf.size, dtype=float)
    total = pmf.sum()
    mean = float(np.dot(k, pmf) / total)
    dev = k - mean
    var = float(np.dot(dev * dev, pmf) / total)
    mu4 = float(np.dot(dev**4, pmf) / total)
    return mean, var, mu4


def _rate_equations(k_in, k_out, frozen):
    def rhs(_t, n):
        if frozen:
            return [0.0, 0.0]
        j = k_in * n[0] - k_out * n[1]
        return [-j, j]

    return rhs


def d_trajectory(w, k_out, *, keep=None, lumen="none", freeze=False):
    """(d)'s mean trajectory by DOP853 between events, with each stop's mean map."""
    n = np.array([float(w["nP"]), float(w["nL"])])
    t_prev, frozen = 0.0, False
    out = {"obs": {}, "stops": {}, "bounds": []}
    start = (0.0, n.copy())
    for t, kind, f in _events(w):
        if t > t_prev and not frozen:
            sol = solve_ivp(
                _rate_equations(w["k_in"], k_out, frozen),
                (t_prev, t),
                n,
                method="DOP853",
                rtol=ODE_RTOL,
                atol=1e-12,
            )
            n = sol.y[:, -1].copy()
        t_prev = t
        if kind == "obs":
            out["obs"][t] = n.copy()
            continue
        if kind == "horizon":
            continue
        out["bounds"].append((start[0], start[1], t, n.copy()))
        if kind == "withdrawal":
            kept_frac = (1.0 - f) if keep is None else keep(f)
            kept = kept_frac * n[0]
            removed = n[0] - kept
            if lumen == "every_stop":
                removed += f * n[1]
                n = np.array([kept, (1.0 - f) * n[1]])
            else:
                n = np.array([kept, n[1]])
            heat = -math.log1p(-f) * kept
        else:
            removed = n[0]
            n = np.array([0.0, n[1]])
            if lumen != "none":
                removed += n[1]
                n = np.array([0.0, 0.0])
            heat = None
            if freeze:
                frozen = True
        out["stops"][t] = (removed, heat)
        start = (t, n.copy())
    out["bounds"].append((start[0], start[1], w["T_end"], n.copy()))
    out["end"] = n.copy()
    return out


def f_cont64(n_pool, n_lumen, w, zero_as_one=False):
    total = 0.0
    for n, mu, v_l in (
        (n_pool, w["mu_s"], num(w["V_out_L"])),
        (n_lumen, w["mu_l"], num(w["V_in_L"])),
    ):
        lnx = math.log(N_A * v_l * 1.0)
        if n == 0.0:
            if zero_as_one:
                total += mu - lnx - 1.0
            continue
        total += n * (mu - lnx) + n * math.log(n) - n
    return total


def shell_numeric(raw):
    """Method 2's results for a shell world, keyed like method 1's."""
    w = world_f64(raw)
    law = molecule_law(w, w["k_out"])
    res = {"pairs": {}, "stops": {}, "d_pairs": {}, "d_stops": {}, "intervals": [], "plants": {}}
    for obs, i in (("S@pool", 0), ("S@lumen", 1)):
        for t in w["obs_t"]:
            res["pairs"][(obs, t)] = pmf_moments(
                [(w["nP"], law["pool"]["obs"][t][i]), (w["nL"], law["lumen"]["obs"][t][i])]
            )
    for t, kind, f in w["stops_t"]:
        rem = pmf_moments(
            [(w["nP"], law["pool"]["stops"][t][0]), (w["nL"], law["lumen"]["stops"][t][0])]
        )
        heat = None
        if kind == "withdrawal":
            c = -math.log1p(-f)
            km = pmf_moments(
                [(w["nP"], law["pool"]["stops"][t][1]), (w["nL"], law["lumen"]["stops"][t][1])]
            )
            heat = (c * km[0], c * c * km[1], c**4 * km[2])
        res["stops"][t] = (rem, heat)
    d = d_trajectory(w, w["k_out"])
    for t in w["obs_t"]:
        res["d_pairs"][("S@pool", t)] = d["obs"][t][0]
        res["d_pairs"][("S@lumen", t)] = d["obs"][t][1]
    res["d_stops"] = dict(d["stops"])
    res["intervals"] = [
        (t0, t1, -(f_cont64(*n1, w) - f_cont64(*n0, w))) for t0, n0, t1, n1 in d["bounds"]
    ]
    res["plants"] = shell_plants64(raw, w, law, d, res)
    return res


def _c1(w, honest, planted, founder):
    """C1 (and C4's (d) part) candidates: {name: (honest, planted, scale)}."""
    out = {}
    for obs, i in (("S@pool", 0), ("S@lumen", 1)):
        scale = max([abs(founder[obs])] + [abs(honest["obs"][t][i]) for t in w["obs_t"]])
        for t in w["obs_t"]:
            out[(obs, t)] = (honest["obs"][t][i], planted["obs"][t][i], scale)
    return out


def shell_plants64(raw, w, law, d, res):
    """Each plant's compared quantities: {(plant, criterion): {name: (honest, planted, unit)}}."""
    founder = {"S@pool": float(w["nP"]), "S@lumen": float(w["nL"])}
    rem_scale = max(abs(d["stops"][t][0]) for t, _k, _f in w["stops_t"])
    heat_scale = max(abs(d["stops"][t][1]) for t, k, _f in w["stops_t"] if k == "withdrawal")
    out = {}

    def c1(planted):
        q = {k: (h, p, 1e-5 * s) for k, (h, p, s) in _c1(w, d, planted, founder).items()}
        for t, _k, _f in w["stops_t"]:
            q[("removed", t)] = (d["stops"][t][0], planted["stops"][t][0], 1e-5 * rem_scale)
        return q

    def c4(planted, only=None):
        q = {}
        for t, kind, _f in w["stops_t"]:
            if only is not None and t != only:
                continue
            q[("removed", t)] = (d["stops"][t][0], planted["stops"][t][0], 1e-5 * rem_scale)
            if kind == "withdrawal":
                q[("mixing_heat", t)] = (
                    d["stops"][t][1],
                    planted["stops"][t][1],
                    1e-5 * heat_scale,
                )
        return q

    for plant in raw.get("plants", []):
        if plant == "P1":
            out[("P1", "C1")] = c1(d_trajectory(w, w["k_out_bare"]))
        elif plant == "P2":
            planted = d_trajectory(w, w["k_out"], keep=lambda f: (1.0 - f) ** 2)
            out[("P2", "C1")] = c1(planted)
            out[("P2", "C4")] = c4(planted)
        elif plant == "P3":
            out[("P3", "C1")] = c1(d_trajectory(w, w["k_out"], lumen="every_stop"))
        elif plant == "P4":
            planted = d_trajectory(w, w["k_out"], freeze=True)
            out[("P4", "C1")] = c1(planted)
            seen, t4 = False, None
            for t, kind, _f in w["stops_t"]:
                if kind == "replacement":
                    seen = True
                elif seen and t4 is None:
                    t4 = t
            out[("P4", "C4")] = c4(planted, only=t4)
        elif plant == "P6":
            total = float(w["nP"] + w["nL"])
            bound = 16 * 2.0**-52 * (1e4 + len(w["stops_t"])) * 2 * total
            q = {}
            for t in w["obs_t"]:
                q[("tracer_moiety", t)] = (total, float(d["obs"][t].sum()), bound)
            if w["obs_t"][-1] != w["T_end"]:
                q[("tracer_moiety", w["T_end"])] = (total, float(d["end"].sum()), bound)
            out[("P6", "C5")] = q
        elif plant == "P7":
            law7 = molecule_law(w, w["k_out_bare"])
            q = {}
            for obs, i in (("S@pool", 0), ("S@lumen", 1)):
                for t in w["obs_t"]:
                    pm = pmf_moments(
                        [
                            (w["nP"], law7["pool"]["obs"][t][i]),
                            (w["nL"], law7["lumen"]["obs"][t][i]),
                        ]
                    )
                    hm = res["pairs"][(obs, t)]
                    q[(obs, t)] = (hm[0], pm[0], 6 * math.sqrt(hm[1] / M))
            out[("P7", "C2")] = q
        elif plant == "P8":
            law8 = molecule_law(w, w["k_out"], removal=lambda f: f * f)
            q = {}
            for t, kind, f in w["stops_t"]:
                pr = pmf_moments(
                    [
                        (w["nP"], law8["pool"]["stops"][t][0]),
                        (w["nL"], law8["lumen"]["stops"][t][0]),
                    ]
                )
                hr = res["stops"][t][0]
                q[("removed", t)] = (hr[0], pr[0], 6 * math.sqrt(hr[1] / M))
                if kind == "withdrawal":
                    c = -math.log1p(-f)
                    pk = pmf_moments(
                        [
                            (w["nP"], law8["pool"]["stops"][t][1]),
                            (w["nL"], law8["lumen"]["stops"][t][1]),
                        ]
                    )
                    hh = res["stops"][t][1]
                    q[("mixing_heat", t)] = (hh[0], c * pk[0], 6 * math.sqrt(hh[1] / M))
            out[("P8", "C4")] = q
        elif plant == "P9":
            heats = res["intervals"]
            scale = max(abs(x[2]) for x in heats)
            q = {}
            for (t0, n0, t1, n1), (_a, _b, h) in zip(d["bounds"], heats, strict=True):
                p = -(f_cont64(*n1, w, True) - f_cont64(*n0, w, True))
                q[("heat", t0, t1)] = (h, p, 1e-5 * scale)
            out[("P9", "C9")] = q
    return out


# --------------------------------------------------------------------------------------------
# Gated worlds
# --------------------------------------------------------------------------------------------


def gate_f64(raw):
    w = world_f64(raw)
    g = raw["gate"]
    w["ea"], w["eb"] = math.exp(num(g["a_open_kBT"])), math.exp(num(g["b_closed_kBT"]))
    w["alpha"] = num(g["k_GH_per_s"])
    w["beta"] = num(g["k_GH_per_s"]) * math.exp(num(g["mu0_H_kBT"]) - num(g["mu0_G_kBT"]))
    fo = raw["founder_molecules"]
    w["G0"], w["H0"], w["B0"] = fo["G@wall"], fo["H@wall"], fo["B@wall"]
    w["Ng"] = w["G0"] + w["H0"]
    w["Nw"] = w["B0"] + w["Ng"]
    w["N"] = w["nP"] + w["nL"]
    return w


def gate_window(w):
    """The gate states the hierarchy keeps: the exact-switching mean's range, padded by
    15 sqrt(N_g)/2 + 10 states, within [0, N_g].

    K is a sum of N_g copies that switch independently (SPEC.md section 1), so Hoeffding's bound
    leaves less than 2 exp(-112.5) of its mass beyond 15 sqrt(N_g)/2 of its mean at any time.
    The solve also checks, at every observation time, that the mass next to a cut edge is below
    1e-25 and that the total mass is one."""
    ng = w["Ng"]
    gam = w["alpha"] + w["beta"]
    k_eq = ng * w["beta"] / gam
    pad = 15.0 * math.sqrt(ng) / 2.0 + 10.0
    lo = max(0, int(math.floor(min(w["G0"], k_eq) - pad)))
    hi = min(ng, int(math.ceil(max(w["G0"], k_eq) + pad)))
    return lo, hi


class _Hierarchy:
    """J(t) = J0 + c(t) J1 + gbar(t) J2 + gbar(t) c(t) J3 for z_j(k) = E[((x - c)/s0)^j 1{K=k}],
    j = 0..4, over the window's gate states, in one CSR pattern with four data arrays."""

    def __init__(self, w, window):
        ng, n_tr = w["Ng"], w["N"]
        k_in, k_out = w["k_in"], w["k_out"]
        lam = k_in + k_out
        a, b = w["alpha"], w["beta"]
        h = 1.0 / n_tr
        s0 = 1.0 / math.sqrt(n_tr)
        k_lo, k_hi = window
        ks = np.arange(k_lo, k_hi + 1, dtype=float)
        pos = np.arange(ks.size)
        gk = (ks * w["ea"] + (ng - ks) * w["eb"]) / ng
        size = 5 * ks.size
        parts = []  # (matrix index, rows, cols, values)

        def idx(p, j):
            return p * 5 + j

        for j in range(5):
            # gate switching: each open copy closes at a, each closed copy opens at b; a move out
            # of the window is dropped, so a cut edge can only lose mass (checked after the solve)
            parts.append((0, idx(pos, j), idx(pos, j), -(a * ks + b * (ng - ks))))
            parts.append((0, idx(pos[:-1], j), idx(pos[1:], j), a * ks[1:]))
            parts.append((0, idx(pos[1:], j), idx(pos[:-1], j), b * (ng - ks[:-1])))
        ones = np.ones(ks.size)
        for j in range(1, 5):
            for ell in range(j):
                sigma = (-1) ** (j - ell) * k_out - k_in
                base = gk * math.comb(j, ell) * h ** (j - ell - 1)
                parts.append((0, idx(pos, j), idx(pos, ell), base * s0 ** (ell - j) * k_in))
                parts.append((1, idx(pos, j), idx(pos, ell), base * s0 ** (ell - j) * sigma))
                parts.append(
                    (0, idx(pos, j), idx(pos, ell + 1), base * s0 ** (ell + 1 - j) * sigma)
                )
            parts.append((2, idx(pos, j), idx(pos, j - 1), ones * (-j / s0 * k_in)))
            parts.append((3, idx(pos, j), idx(pos, j - 1), ones * (j / s0 * lam)))
        keys = np.concatenate([r.astype(np.int64) * size + c for _m, r, c, _v in parts])
        uniq = np.unique(keys)
        self.data = [np.zeros(uniq.size) for _ in range(4)]
        for m, r, c, v in parts:
            np.add.at(self.data[m], np.searchsorted(uniq, r.astype(np.int64) * size + c), v)
        rows = uniq // size
        self.indices = (uniq % size).astype(np.int32)
        self.indptr = np.searchsorted(rows, np.arange(size + 1)).astype(np.int32)
        self.size, self.s0, self.window = size, s0, window
        self._scratch = self.matrix(0.0, 0.0)

    def values(self, c, g):
        d = self.data
        return d[0] + c * d[1] + g * d[2] + (g * c) * d[3]

    def matrix(self, c, g):
        return scipy.sparse.csr_matrix(
            (self.values(c, g), self.indices.copy(), self.indptr.copy()),
            shape=(self.size, self.size),
        )

    def apply(self, c, g, y):
        self._scratch.data[:] = self.values(c, g)
        return self._scratch @ y


def _centring(w):
    """c(t) and gbar(t): the lumen fraction of the mean field with the exact switching rates."""
    ng = w["Ng"]
    gam = w["alpha"] + w["beta"]
    k_eq = ng * w["beta"] / gam
    lam = w["k_in"] + w["k_out"]
    pi1 = w["k_in"] / lam
    x0 = w["nL"] / w["N"]
    c1 = (w["ea"] - w["eb"]) / ng

    def kbar(t):
        return k_eq + (w["G0"] - k_eq) * math.exp(-gam * t)

    def gbar(t):
        return w["eb"] + c1 * kbar(t)

    def c(t):
        phi = w["eb"] * t + c1 * (k_eq * t + (w["G0"] - k_eq) * (-math.expm1(-gam * t)) / gam)
        return pi1 + (x0 - pi1) * math.exp(-lam * phi)

    return c, gbar


def gate_hierarchy(w):
    """Exact moments from the moment hierarchy over the gate states, by Radau."""
    window = gate_window(w)
    hier = _Hierarchy(w, window)
    s0 = hier.s0
    c, gbar = _centring(w)

    def jac(t, _y=None):
        return hier.matrix(c(t), gbar(t))

    def rhs(t, y):
        return hier.apply(c(t), gbar(t), y)

    k_lo, k_hi = window
    nk = k_hi - k_lo + 1
    y = np.zeros(hier.size)
    y[(w["G0"] - k_lo) * 5 + 0] = 1.0
    t_prev = 0.0
    ng, n_tr = w["Ng"], w["N"]
    out = {}
    for t in w["obs_t"]:
        # step the solver to the observation time itself (its last step ends exactly there),
        # keeping only the current state: no dense output and no stored trajectory
        solver = Radau(rhs, t_prev, y, t, jac=jac, rtol=HIER_RTOL, atol=HIER_ATOL)
        while solver.status == "running":
            message = solver.step()
            if solver.status == "failed":
                raise RuntimeError(message)
        if solver.t != t:
            raise RuntimeError("the hierarchy stopped short of an observation time")
        y = solver.y.copy()
        t_prev = t
        z = y.reshape(nk, 5)
        edge = 0.0
        if k_lo > 0:
            edge = max(edge, float(np.abs(z[:3, 0]).sum()))
        if k_hi < ng:
            edge = max(edge, float(np.abs(z[-3:, 0]).sum()))
        if edge > 1e-25:
            raise RuntimeError(f"the gate window is too narrow: edge mass {edge}")
        s = z.sum(axis=0)
        d1 = s[1]
        var_x = s0**2 * (s[2] - d1 * d1)
        mu4_x = s0**4 * (s[4] - 4 * d1 * s[3] + 6 * d1 * d1 * s[2] - 3 * d1**4)
        mean_l = n_tr * (c(t) + s0 * d1)
        pk = z[:, 0]
        ks = np.arange(k_lo, k_hi + 1, dtype=float)
        mk = float(np.dot(ks, pk))
        dev = ks - mk
        vk = float(np.dot(dev * dev, pk))
        m4k = float(np.dot(dev**4, pk))
        out[t] = {
            "S@lumen": (mean_l, n_tr**2 * var_x, n_tr**4 * mu4_x),
            "S@pool": (n_tr - mean_l, n_tr**2 * var_x, n_tr**4 * mu4_x),
            "G@wall": (mk, vk, m4k),
            "H@wall": (ng - mk, vk, m4k),
            "mass": float(s[0]),
            "edge_mass": edge,
            "window": window,
        }
    return out


def gate_mean_field64(w, entry_only=False):
    """The registered limit's rate equations by DOP853: switching at k (Nw + 1)/Nw."""
    fac = (w["Nw"] + 1) / w["Nw"]
    a, b = w["alpha"] * fac, w["beta"] * fac
    ng = w["Ng"]

    def rhs(_t, y):
        g_, h_, npool, nlum = y
        gate = (g_ * w["ea"] + h_ * w["eb"]) / ng
        sw = -a * g_ + b * h_
        if entry_only:
            j = gate * w["k_in"] * npool - w["k_out"] * nlum
        else:
            j = gate * (w["k_in"] * npool - w["k_out"] * nlum)
        return [sw, -sw, -j, j]

    y = np.array([float(w["G0"]), float(w["H0"]), float(w["nP"]), float(w["nL"])])
    t_prev = 0.0
    out = {}
    for t in w["obs_t"]:
        sol = solve_ivp(rhs, (t_prev, t), y, method="DOP853", rtol=ODE_RTOL, atol=1e-12)
        y = sol.y[:, -1].copy()
        t_prev = t
        out[t] = {"G@wall": y[0], "H@wall": y[1], "S@pool": y[2], "S@lumen": y[3]}
    return out


def gate_numeric(raw):
    w = gate_f64(raw)
    exact = gate_hierarchy(w)
    mf = gate_mean_field64(w)
    res = {
        "pairs": {},
        "d_pairs": {},
        "gap": {},
        "plants": {},
        "mass": {},
        "edge_mass": {},
        "window": list(gate_window(w)),
        "Ng": w["Ng"],
    }
    for t in w["obs_t"]:
        res["mass"][t] = exact[t]["mass"]
        res["edge_mass"][t] = exact[t]["edge_mass"]
        for obs in ("S@pool", "S@lumen", "G@wall", "H@wall"):
            res["pairs"][(obs, t)] = exact[t][obs]
            res["d_pairs"][(obs, t)] = mf[t][obs]
            g = mf[t][obs] - exact[t][obs][0]
            res["gap"][(obs, t)] = (g, abs(g) * math.sqrt(M) / math.sqrt(exact[t][obs][1]))
    if "P5" in raw.get("plants", []):
        planted = gate_mean_field64(w, entry_only=True)
        q = {}
        founder = raw["founder_molecules"]
        for obs in ("S@pool", "S@lumen", "G@wall", "H@wall"):
            scale = max([abs(founder[obs])] + [abs(mf[t][obs]) for t in w["obs_t"]])
            for t in w["obs_t"]:
                q[(obs, t)] = (mf[t][obs], planted[t][obs], 1e-5 * scale)
        res["plants"][("P5", "C7")] = q
    res["c8"] = c8_largest(res["gap"], w["obs_t"])
    return res


# --------------------------------------------------------------------------------------------
# The naming rules, in method 2's own code (AMENDMENT-2026-11-24 sections 1 and 2)
# --------------------------------------------------------------------------------------------

SPEC_ORDER = (
    "S@pool",
    "S@lumen",
    "G@wall",
    "H@wall",
    "B@wall",
    "removed",
    "mixing_heat",
    "heat",
    "tracer_moiety",
)
F64_TIE = 1e-9  # float64 cannot split an exact tie the way decimals do; 1e-9 relative is a tie


def largest(cands):
    """A plant entry's named quantity: the largest distance |planted - honest| / unit, a tie going
    to the earliest time or stop (an interval by its start), then the first observable in the
    spec's order. ``cands`` maps (observable, time) or (observable, start, end) to
    (honest, planted, unit)."""
    dist = {key: abs(p - h) / u for key, (h, p, u) in cands.items()}
    top = max(dist.values())
    tied = [key for key, d in dist.items() if d >= top * (1 - F64_TIE)]
    return min(tied, key=lambda key: (key[1], SPEC_ORDER.index(key[0])))


def c8_largest(gaps, times):
    """C8's pair: the largest |gap| over S@pool and S@lumen, a tie going to S@pool, then to the
    earliest time. ``gaps`` maps (observable, time) to (gap, resolution)."""
    order = [(obs, t) for obs in ("S@pool", "S@lumen") for t in sorted(times)]
    top = max(abs(gaps[key][0]) for key in order)
    return next(key for key in order if abs(gaps[key][0]) >= top * (1 - F64_TIE))


def numeric(raw):
    return shell_numeric(raw) if raw["type"] == "shell_washes" else gate_numeric(raw)
