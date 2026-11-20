"""Rows OL4-5 to OL4-7: the true-equilibrium control, the driven steady state with its flux and
heat, the modality and the mean switching time, on finite worlds (fuel note §5 checks 4 and 6,
§3 (d) "OL5's references").

**The worlds.** A registered closed world without geometry holds a fixed number M of blocks
(B, S, L1, L2 in pool and membrane together); F and W are held. Its states are every count vector
with that block total and a non-empty membrane: under ``kept`` no pair whose step changes the
membrane's count may empty it (engine note §0.2a), so the empty-membrane states are a separate,
pool-only class that the registered worlds never enter. The chain on the listed states is
irreducible (checked by ``connected``), so each world has one stationary law.

**Check 4, true equilibrium** (fuel note §5.4, the lead's ruling Q1). At zero drive,
mu_F = mu_W with held potentials including their activities, every step's reservoir work is
zero, and the pair identity a+(n) e^(-F(n)) = a-(n') e^(-F(n')) holds on every edge. So
pi = exp(-F)/Z is stationary, whatever the catalysts (engine note §0.1). The factor does not move
it: the arm with beta > 0 and the arm with beta = 0 relax to the same law. By the product form,
pi(L1 = a, L2 = b) = c(a + b)/(a! b!) (L1 and L2 have equal potentials), so the law of the two
amphiphiles has its maxima only where |a - b| <= 1: the zero-drive arm is never bimodal.

**Check 6, heat at stationarity** (fuel note §5.6). With held fuel the drive per turn is
A = mu_F - mu_W. At a stationary law pi, with J_e the net probability flux on edge e,
    mean heat rate = Sum_e J_e ln(a+_e/a-_e) = Sum_e J_e (-Delta F_e + w_e) = J A,
because Sum_e J_e Delta F_e = Sum_n F(n) (outflow(n) - inflow(n)) = 0 at stationarity and only the
fuel step books work. J = Sum_n pi(n) (a+_f1(n) - a-_f1(n)) is the fuel step's net flux. On one
long run the ledger gives Q_t = N_net A - (F(n_t) - F(n_0)), so |Q_t - N_net A| is at most the range
of F over the states (plus rounding). The net count N_net = N_+ - N_- obeys a central limit law:
N_net/t -> J with variance rate
    D = Sum_n pi(n) Sum_m Q_nm (c_nm + u_m - u_n)^2,   Q u = -(h - J),
h(n) = a+_f1(n) - a-_f1(n), c_nm = +1 (-1) on a forward (reverse) fuel event and 0 otherwise. This
is the martingale decomposition of an additive functional of a finite Markov chain (derived in
``variance_rate``). Planted (a reader's error): the flux counted without its reverse events.

**The modality** (the lead's ruling Q2: reported, under a registered definition). The law of
(L1@membrane, L2@membrane) is marginalised from pi. Its modes are the clusters of local maxima
over the 8-neighbourhood (a point is a local maximum when no neighbour in the support is larger;
ties form one cluster), keeping clusters whose peak is at least ``MODE_REL`` of the largest. Kinds:
``one_central`` (one mode, |a - b| <= 1), ``two_interior`` (two mirrored modes, |a - b| >= 2, both
amphiphiles present in each), ``two_edge`` (two mirrored modes on the edge where one amphiphile is
absent), and ``one_offcentre`` or ``other``.

**The mean switching time** (fuel note §3 (d)). Regions on the share f = L1/(L1 + L2) with
L1 + L2 >= ``SWITCH_MIN_L``: R1 = {f >= 3/4}, R2 = {f <= 1/4}. tau_1 solves Q tau_1 = -1 off R2
with tau_1 = 0 on R2; tau_2 solves Q tau_2 = -2 tau_1. The registered start is one state, so the
reference and the engine's table are compared at the same point.

**Solves.** pi Q = 0 with pi at the first state fixed, then normalised (no dense row, so the LU
stays sparse; SuperLU with MMD on A^T + A). Every solve reports its residual max |pi Q|.
"""

from __future__ import annotations

import itertools
import math

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from ..common import CheckResult
from ..detailed_balance import kolmogorov
from ..probes import add
from ..ssa_oracle import FloatRates
from ..world import World

MODE_REL = 1 / 20
SWITCH_MIN_L = 2
TV_EQUILIBRIUM = 1e-10
TV_DRIVEN = 1e-9
MFPT_RTOL = 1e-7
FLUX_RTOL = 1e-8


# ---------------------------------------------------------------------------- states

def closed_states(world: World, totals: dict) -> np.ndarray:
    """Every finite-place count vector with the given moiety totals and a non-empty membrane."""
    names = world.moiety_names()
    Wm = np.array(world.moiety_matrix(), dtype=np.int64)
    D = world.dim
    mem = np.array(world.membrane_mask())
    # each place carries one moiety unit here (registered worlds): enumerate per moiety class
    groups = {}
    for i in range(D):
        carried = [q for q in range(len(names)) if Wm[q, i]]
        if len(carried) != 1 or Wm[carried[0], i] != 1:
            raise ValueError("closed_states needs each finite place to carry exactly one unit of one moiety")
        groups.setdefault(names[carried[0]], []).append(i)
    parts = []
    for q, idx in groups.items():
        tot = int(totals[q])
        opts = []
        for c in itertools.product(range(tot + 1), repeat=len(idx) - 1):
            s = sum(c)
            if s <= tot:
                opts.append(c + (tot - s,))
        parts.append((idx, opts))
    out = []
    for combo in itertools.product(*[p[1] for p in parts]):
        n = [0] * D
        for (idx, _), vals in zip(parts, combo):
            for i, v in zip(idx, vals):
                n[i] = v
        if sum(v for v, m in zip(n, mem) if m) >= 1:
            out.append(tuple(n))
    return np.array(sorted(out), dtype=np.int64)


def reachable_states(world: World, initial) -> np.ndarray:
    """Every state reachable from ``initial`` by possible events, sorted: a forward (reverse) event
    is possible when the finite reactants (products) are present, no count goes negative, and
    ``kept`` does not forbid it (a membrane-locus step that changes the membrane's count with an
    empty end state). With positive rate constants and factors g > 0 every possible event has a
    positive rate, so this is the support of the chain from ``initial``; its rates come in
    reversible pairs, so the set is one communicating class. (It excludes, for instance, a
    finite-fuel world's closed class with every block as B and no waste, which no other state
    enters or leaves.)"""
    nus = [world.nu(st) for st in world.steps]
    al = [world.alpha(st) for st in world.steps]
    be = [world.beta_finite(st) for st in world.steps]
    mem = world.membrane_mask()
    memloc = [st.locus == "membrane" for st in world.steps]

    def N(n):
        return sum(v for v, m in zip(n, mem) if m)

    start = world.state_from(initial) if isinstance(initial, dict) else tuple(int(v) for v in initial)
    seen = {start}
    frontier = [start]
    while frontier:
        nxt = []
        for n in frontier:
            for r, nu in enumerate(nus):
                for sign, need in ((1, al[r]), (-1, be[r])):
                    if any(v < a for v, a in zip(n, need)):
                        continue
                    p = add(n, nu, sign)
                    if any(v < 0 for v in p):
                        continue
                    if memloc[r] and N(n) != N(p) and (N(n) == 0 or N(p) == 0):
                        continue
                    if p not in seen:
                        seen.add(p)
                        nxt.append(p)
        frontier = nxt
    return np.array(sorted(seen), dtype=np.int64)


def float_table(law, states) -> dict:
    """The reference's rates at every listed state, from the float path (``FloatRates``) for the
    honest law, or from the exact law for a planted one."""
    R = len(law.world.steps)
    S = len(states)
    ap, am = np.zeros((S, R)), np.zeros((S, R))
    if getattr(law, "planted_label", None) is None and law.planted is None:
        fr = FloatRates(law)
        for k, s in enumerate(states):
            for r in range(R):
                ap[k, r] = fr.forward(r, s)
                am[k, r] = fr.reverse(r, s)
    else:
        for k, s in enumerate(states):
            t = tuple(int(v) for v in s)
            for r, st in enumerate(law.world.steps):
                ap[k, r] = float(law.forward(st, t))
                am[k, r] = float(law.reverse(st, t))
    return dict(a_plus=ap, a_minus=am)


# ---------------------------------------------------------------------------- generators

def _index(states) -> dict:
    return {tuple(int(v) for v in s): k for k, s in enumerate(states)}


def edges(world: World, states, a_plus, a_minus):
    """(source, target, rate, step, sign) arrays for every positive rate; a rate leading outside
    the listed states is an error."""
    idx = _index(states)
    nus = [world.nu(st) for st in world.steps]
    src, dst, val, stp, sgn = [], [], [], [], []
    a_plus, a_minus = np.asarray(a_plus, float), np.asarray(a_minus, float)
    for k, s in enumerate(states):
        n = tuple(int(v) for v in s)
        for r, nu in enumerate(nus):
            for sign, rate in ((1, a_plus[k, r]), (-1, a_minus[k, r])):
                if rate > 0:
                    t = add(n, nu, sign)
                    j = idx.get(t)
                    if j is None:
                        raise ValueError(f"a rate at {n} (step {world.steps[r].name}, direction {sign}) leads "
                                         f"outside the listed states, to {t}")
                    src.append(k)
                    dst.append(j)
                    val.append(float(rate))
                    stp.append(r)
                    sgn.append(sign)
    return (np.array(src, dtype=np.int64), np.array(dst, dtype=np.int64), np.array(val), np.array(stp, dtype=np.int64),
            np.array(sgn, dtype=np.int64))


def generator(n_states: int, e) -> sp.csr_matrix:
    src, dst, val = e[0], e[1], e[2]
    out = np.zeros(n_states)
    np.add.at(out, src, val)
    rows = np.concatenate([src, np.arange(n_states)])
    cols = np.concatenate([dst, np.arange(n_states)])
    vals = np.concatenate([val, -out])
    return sp.csr_matrix((vals, (rows, cols)), shape=(n_states, n_states))


def connected(Q: sp.csr_matrix) -> bool:
    """Strong connectivity of the rate graph (irreducibility)."""
    from scipy.sparse.csgraph import connected_components

    A = (Q != 0).astype(np.int8)
    k, _ = connected_components(A, directed=True, connection="strong")
    return k == 1


def stationary(Q: sp.csr_matrix) -> np.ndarray:
    A = Q.T.tocsc()
    x = spla.splu(A[1:, 1:].tocsc(), permc_spec="MMD_AT_PLUS_A").solve(-A[1:, 0].toarray().ravel())
    pi = np.concatenate([[1.0], x])
    return pi / pi.sum()


def boltzmann(law, states) -> np.ndarray:
    lw = np.array([law.weight(tuple(int(v) for v in s)).log() for s in states])
    lw -= lw.max()
    w = np.exp(lw)
    return w / w.sum()


def total_variation(p, q) -> float:
    return 0.5 * float(np.sum(np.abs(np.asarray(p, float) - np.asarray(q, float))))


# ---------------------------------------------------------------------------- flux, heat, variance

def fuel_step_index(world: World, name: str = "f1") -> int:
    return [st.name for st in world.steps].index(name)


def flux_and_heat(world: World, states, a_plus, a_minus, pi, step: str = "f1") -> dict:
    """J of ``step`` and the mean heat rate Sum_e J_e ln(a+/a-) over every edge (k_BT/s)."""
    r = fuel_step_index(world, step)
    ap, am = np.asarray(a_plus, float), np.asarray(a_minus, float)
    J = float(pi @ (ap[:, r] - am[:, r]))
    J_forward_only = float(pi @ ap[:, r])
    idx = _index(states)
    nus = [world.nu(st) for st in world.steps]
    heat = 0.0
    for k, s in enumerate(states):
        n = tuple(int(v) for v in s)
        for q_, nu in enumerate(nus):
            a = ap[k, q_]
            if a > 0:
                j = idx[add(n, nu)]
                b = am[j, q_]
                if not (b > 0 and math.isfinite(a) and math.isfinite(b)):
                    return dict(J=J, J_forward_only=J_forward_only, heat_rate=math.inf)
                heat += (pi[k] * a - pi[j] * b) * (math.log(a) - math.log(b))
    return dict(J=J, J_forward_only=J_forward_only, heat_rate=heat)


def poisson(Q: sp.csr_matrix, pi, e, step_index: int) -> dict:
    """J, D and u for the net count of one step's events, at stationarity.

    N_net(t) - J t = M_t + Int_0^t (h(X_s) - J) ds, with M the compensated jump martingale and
    h(n) = a+(n) - a-(n) for that step. With Q u = -(h - J), Ito's formula gives
    Int (h - J) ds = u(X_0) - u(X_t) + M^u_t, M^u a martingale. So N_net - J t = M_t + M^u_t + u(X_0)
    - u(X_t): from a start n_0 its mean tends to J t + u(n_0) - pi u, and its variance per unit time
    to D = Sum_n pi_n Sum_m Q_nm (c_nm + u_m - u_n)^2, the predictable variation of M + M^u."""
    src, dst, val, stp, sgn = e
    c = np.where(stp == step_index, sgn, 0).astype(float)
    S = Q.shape[0]
    h = np.zeros(S)
    np.add.at(h, src, val * c)
    J = float(pi @ h)
    rhs = -(h - J)
    Qc = Q.tocsc()
    u = np.zeros(S)                       # u_0 = 0; drop the first equation (the system has rank S - 1)
    u[1:] = spla.splu(Qc[1:, 1:].tocsc(), permc_spec="MMD_AT_PLUS_A").solve(rhs[1:])
    D = float(np.sum(pi[src] * val * (c + u[dst] - u[src]) ** 2))
    return dict(J=J, D=D, u=u)


def variance_rate(Q: sp.csr_matrix, pi, e, step_index: int) -> float:
    return poisson(Q, pi, e, step_index)["D"]


# ---------------------------------------------------------------------------- modality

def joint_L(world: World, states, pi) -> np.ndarray:
    i1, i2 = world.index("L1@membrane"), world.index("L2@membrane")
    S = np.asarray(states)
    top = int(max(S[:, i1].max(), S[:, i2].max()))
    J = np.zeros((top + 1, top + 1))
    np.add.at(J, (S[:, i1], S[:, i2]), pi)
    return J


def modes(J: np.ndarray, rel: float = MODE_REL) -> list:
    size = J.shape[0]
    sup = J > 0
    nbr = [(da, db) for da in (-1, 0, 1) for db in (-1, 0, 1) if (da, db) != (0, 0)]
    loc = set()
    for a in range(size):
        for b in range(size):
            if not sup[a, b]:
                continue
            if all(not (0 <= a + da < size and 0 <= b + db < size and sup[a + da, b + db] and J[a + da, b + db] > J[a, b])
                   for da, db in nbr):
                loc.add((a, b))
    clusters, seen = [], set()
    for p in sorted(loc):
        if p in seen:
            continue
        comp, stack = [], [p]
        seen.add(p)
        while stack:
            u = stack.pop()
            comp.append(u)
            for da, db in nbr:
                w = (u[0] + da, u[1] + db)
                if w in loc and w not in seen:
                    seen.add(w)
                    stack.append(w)
        clusters.append(sorted(comp))
    top = max(J[a, b] for cl in clusters for a, b in cl)
    out = [dict(states=[list(x) for x in cl], peak=float(max(J[a, b] for a, b in cl))) for cl in clusters]
    return sorted([m for m in out if m["peak"] >= rel * top], key=lambda m: (-m["peak"], m["states"]))


def classify(ms: list) -> str:
    if len(ms) == 1:
        a, b = ms[0]["states"][0]
        return "one_central" if abs(a - b) <= 1 else "one_offcentre"
    if len(ms) == 2:
        s0 = {tuple(x) for x in ms[0]["states"]}
        s1 = {(b, a) for a, b in ms[1]["states"]}
        if s0 == s1 and all(abs(a - b) >= 2 for m in ms for a, b in m["states"]):
            interior = all(min(a, b) >= 1 for m in ms for a, b in m["states"])
            return "two_interior" if interior else "two_edge"
    return "other"


def modality(world: World, states, pi) -> dict:
    J = joint_L(world, states, pi)
    ms = modes(J)
    S = np.asarray(states)
    L = S[:, world.index("L1@membrane")] + S[:, world.index("L2@membrane")]
    mem = np.array(world.membrane_mask())
    N = S[:, mem].sum(axis=1)
    diag = max(J[a, b] for a in range(J.shape[0]) for b in range(J.shape[0]) if abs(a - b) <= 1 and J[a, b] > 0)
    xB = S[:, world.index("B@membrane")] / N
    xS = S[:, world.index("S@membrane")] / N
    return dict(kind=classify(ms), modes=ms, mean_L=float(pi @ L), p_L0=float(pi[L == 0].sum()),
                dip=float(diag / ms[0]["peak"]),
                mean_fractions=dict(x_B=float(pi @ xB), x_S=float(pi @ xS), T=float(pi @ (L / N))))


# ---------------------------------------------------------------------------- switching

def regions(world: World, states) -> tuple:
    S = np.asarray(states)
    a, b = S[:, world.index("L1@membrane")], S[:, world.index("L2@membrane")]
    big = (a + b) >= SWITCH_MIN_L
    return big & (4 * a >= 3 * (a + b)), big & (4 * a <= (a + b))


def first_passage(Q: sp.csr_matrix, target: np.ndarray) -> tuple:
    """tau_1 and tau_2 (first and second moments of the hitting time of ``target``) at every state."""
    keep = np.nonzero(~target)[0]
    Qk = Q.tocsc()[keep][:, keep].tocsc()
    lu = spla.splu(Qk, permc_spec="MMD_AT_PLUS_A")
    t1 = np.zeros(Q.shape[0])
    t2 = np.zeros(Q.shape[0])
    t1[keep] = lu.solve(-np.ones(len(keep)))
    t2[keep] = lu.solve(-2.0 * t1[keep])
    return t1, t2


def switching(world: World, states, Q, start) -> dict:
    R1, R2 = regions(world, states)
    idx = _index(states)
    k = idx[tuple(int(v) for v in start)]
    if not R1[k]:
        raise ValueError("the registered start state is not in the L1-rich region")
    t1, t2 = first_passage(Q, R2)
    return dict(start=[int(v) for v in start], mean=float(t1[k]), second_moment=float(t2[k]),
                sd=float(math.sqrt(max(t2[k] - t1[k] ** 2, 0.0))))


# ---------------------------------------------------------------------------- the checks on tables

def check_equilibrium(law, states, a_plus, a_minus) -> dict:
    """Row OL4-5: the engine table's stationary law against exp(-F)/Z."""
    out = {}
    try:
        e = edges(law.world, states, a_plus, a_minus)
    except ValueError as exc:
        return {"generator": CheckResult("generator", False, dict(problem=str(exc)))}
    Q = generator(len(states), e)
    if not connected(Q):
        return {"generator": CheckResult("generator", False, dict(problem="the table's rate graph is not connected"))}
    pi = stationary(Q)
    tv = total_variation(pi, boltzmann(law, states))
    out["stationary_law"] = CheckResult("stationary_law_is_exp_minus_F", tv <= TV_EQUILIBRIUM,
                                        dict(total_variation=tv, atol=TV_EQUILIBRIUM, states=len(states),
                                             residual=float(np.abs(pi @ Q).max()), world=law.world.name))
    out["kolmogorov"] = kolmogorov(law.world, states, a_plus, a_minus)
    out["modality"] = CheckResult("modality_reported", True, dict(world=law.world.name, **modality(law.world, states, pi)))
    return out


def reference_solution(law, states) -> dict:
    """The reference's own law, flux, heat and variance on a finite world (float solve of the
    exact rates)."""
    t = float_table(law, states)
    e = edges(law.world, states, t["a_plus"], t["a_minus"])
    Q = generator(len(states), e)
    pi = stationary(Q)
    out = dict(table=t, Q=Q, pi=pi, residual=float(np.abs(pi @ Q).max()), connected=connected(Q))
    if "f1" in [st.name for st in law.world.steps]:
        out.update(flux_and_heat(law.world, states, t["a_plus"], t["a_minus"], pi))
        ps = poisson(Q, pi, e, fuel_step_index(law.world))
        out["D"], out["u"] = ps["D"], ps["u"]
    return out


def check_driven(law, states, a_plus, a_minus, ref: dict, drive: float, start=None) -> dict:
    """Rows OL4-6 and OL4-7 on an engine table: its law against the reference's, its flux and
    heat, the identity heat = J A on its own law, the modality and the mean switching time."""
    out = {}
    try:
        e = edges(law.world, states, a_plus, a_minus)
    except ValueError as exc:
        return {"generator": CheckResult("generator", False, dict(problem=str(exc)))}
    Q = generator(len(states), e)
    pi = stationary(Q)
    tv = total_variation(pi, ref["pi"])
    out["stationary_law"] = CheckResult("driven_law_matches_reference", tv <= TV_DRIVEN,
                                        dict(total_variation=tv, atol=TV_DRIVEN, world=law.world.name,
                                             residual=float(np.abs(pi @ Q).max())))
    fh = flux_and_heat(law.world, states, a_plus, a_minus, pi)
    rel = abs(fh["J"] - ref["J"]) / abs(ref["J"])
    heat_id = abs(fh["heat_rate"] - fh["J"] * drive) / max(abs(fh["J"] * drive), 1e-300)
    out["flux"] = CheckResult("fuel_flux_matches_reference", rel <= FLUX_RTOL,
                              dict(J=fh["J"], J_reference=ref["J"], rel=rel, rtol=FLUX_RTOL))
    out["heat"] = CheckResult("mean_heat_rate_is_flux_times_drive", heat_id <= FLUX_RTOL,
                              dict(heat_rate=fh["heat_rate"], J_times_drive=fh["J"] * drive, rel=heat_id,
                                   rtol=FLUX_RTOL, drive=drive))
    out["modality"] = CheckResult("modality_reported", True, dict(world=law.world.name,
                                                                   **modality(law.world, states, pi)))
    if start is not None:
        mine = switching(law.world, states, Q, start)
        theirs = switching(law.world, states, ref["Q"], start)
        r = abs(mine["mean"] - theirs["mean"]) / theirs["mean"]
        out["switching"] = CheckResult("mean_switching_time_matches_reference", r <= MFPT_RTOL,
                                       dict(engine=mine, reference=theirs, rel=r, rtol=MFPT_RTOL))
    return out
