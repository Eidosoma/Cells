"""R-faces: a neutral species on a face chain with a stepped held bath (Appendix A.2, item B1).

**The law (A.2).** Each finite node i (volume V_i, pL) holds n_i = V_i c_i fmol, and

    dn_i/dt = sum_{faces f = (i, j)} kappa_f (c_j - c_i) + kappa_b (c_b(t) - c_i),

the last term for a face to the held bath, with kappa_f = 1e15 D_f A_f / L_f pL/s (D in m^2/s,
A in m^2, L in m). The bath's concentration c_b(t) is piecewise constant and right-continuous: an
event at t_e sets it for t >= t_e. Node amounts are continuous at an event.

**The exact solution.** Write dn/dt = L c + k_b c_b with L the conductance matrix (L_ij = kappa_ij
off the diagonal, L_ii = -sum_j kappa_ij - kappa_b,i), so L 1 = -k_b. When every node has a path
to the bath, L is negative definite on the volume-weighted space and an epoch's steady state is
c = c_b 1 exactly. The deviation d = c - c_b^e 1 then obeys dd/dt = V^-1 L d, and with W = V^1/2
the matrix S = W^-1 L W^-1 is symmetric, S = Q diag(lambda) Q^T, so

    c(t) = c(t_e) + W^-1 Q diag(expm1(lambda (t - t_e))) Q^T W d(t_e)   (primary, numpy eigh)

epoch by epoch, each epoch started from the previous one's end, so a record at t_e returns the
epoch's start exactly. The second method is SciPy's
``expm`` of the augmented generator [[V^-1 L, V^-1 k_b c_b], [0, 0]] acting on [c; 1], chained
independently. The floor is their difference at each record time. For two nodes, ``solve_decimal``
evaluates Sylvester's formula exp(M t) = [e^{l1 t}(M - l2) - e^{l2 t}(M - l1)]/(l1 - l2) in
50-digit decimals, which the tests use as the truth for both.

**The supply.** With the bath the only source and no other sink, the cumulative supply (fmol,
positive out of the bath) is S(t) = sum_i (n_i(t) - n_i(0)), computed from exact offsets.

Refused: a node with no path to the bath (its epoch steady state is not c_b), a face whose ends
are not declared nodes or the bath, and a nonpositive volume, conductance or concentration.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction

import numpy as np
from scipy.linalg import expm

from .common import DIGITS, dec, exact
from .records import bath_epochs

BATH = "bath"


@dataclass
class FaceWorld:
    """A parsed R_faces block: exact inputs, plus float64 matrices for the solvers."""

    species: str
    nodes: list
    volume: list            # Fraction, pL
    c0: list                # Fraction, mM
    kappa: list             # [(i, j or None for the bath, Fraction pL/s, face id)]
    epochs: list            # [(t_start Fraction, c_b Fraction)]
    times: np.ndarray       # record times, s

    @property
    def n(self) -> int:
        return len(self.nodes)

    def conductance_matrix(self) -> tuple:
        """(L, k_b) as exact Fractions: L_ij = kappa_ij, L_ii = -sum - kappa_b,i."""
        N = self.n
        L = [[Fraction(0)] * N for _ in range(N)]
        kb = [Fraction(0)] * N
        for i, j, k, _ in self.kappa:
            if j is None:
                kb[i] += k
                L[i][i] -= k
            else:
                L[i][j] += k
                L[j][i] += k
                L[i][i] -= k
                L[j][j] -= k
        return L, kb


def _species_of(block: dict) -> str:
    keys = set()
    for spec in block["finite_nodes"].values():
        keys |= {k[:-3] for k in spec if k.endswith("_mM")}
    declared = str(block.get("species", "")).split(",")[0].strip()
    if len(keys) != 1 or (declared and declared not in keys):
        raise ValueError(f"cannot tell the face species: nodes carry {sorted(keys)}, "
                         f"the block says {declared!r}")
    return keys.pop()


def parse(block: dict) -> FaceWorld:
    """Parse an R_faces block (the inputs file's layout)."""
    sp = _species_of(block)
    nodes = list(block["finite_nodes"])
    index = {name: i for i, name in enumerate(nodes)}
    volume = [exact(block["finite_nodes"][n]["volume_pL"]) for n in nodes]
    c0 = [exact(block["finite_nodes"][n][f"{sp}_mM"]) for n in nodes]
    if any(v <= 0 for v in volume) or any(c <= 0 for c in c0):
        raise ValueError("volumes and initial concentrations must be positive")
    kappa = []
    for face in block["faces"]:
        a, b = face["between"]
        ends = [x for x in (a, b) if x != BATH]
        if any(x not in index for x in ends) or len(ends) == 0 or a == b:
            raise ValueError(f"face {face.get('id')} joins {a!r} and {b!r}")
        k = 10 ** 15 * exact(face[f"{sp}_diffusivity_m2_per_s"]) * exact(face["area_m2"]) \
            / exact(face["length_m"])
        if k <= 0:
            raise ValueError(f"face {face.get('id')} has no conductance")
        if len(ends) == 1:
            kappa.append((index[ends[0]], None, k, face.get("id")))
        else:
            kappa.append((index[a], index[b], k, face.get("id")))
    epochs = [(t, comp[sp]) for t, comp in bath_epochs(block["bath"])]
    world = FaceWorld(sp, nodes, volume, c0, kappa, epochs,
                      np.asarray(block["record_times_s"], dtype=np.float64))
    _check_connected(world)
    return world


def _check_connected(world: FaceWorld) -> None:
    reach = {i for i, j, _, _ in world.kappa if j is None}
    changed = True
    while changed:
        changed = False
        for i, j, _, _ in world.kappa:
            if j is None:
                continue
            if (i in reach) != (j in reach):
                reach |= {i, j}
                changed = True
    if len(reach) != world.n:
        lost = [world.nodes[i] for i in range(world.n) if i not in reach]
        raise ValueError(f"nodes {lost} have no path to the bath")


def kappas(world: FaceWorld) -> dict:
    """Each face's conductance (pL/s) by face id, and each node's relaxation rate to the bath."""
    return {fid: float(k) for _, _, k, fid in world.kappa}


def _epoch_of(t: Fraction, epochs) -> int:
    e = 0
    while e + 1 < len(epochs) and t >= epochs[e + 1][0]:
        e += 1
    return e


def solve(world: FaceWorld, epochs=None, times=None) -> dict:
    """The exact amounts at the record times by both methods, with the floor and the supply.

    ``epochs`` overrides the bath's [(t_start, c_b)] (the planted controls use it); ``times``
    overrides the record times. Returns ``amount_fmol`` [T, N] (primary), ``amount_expm_fmol``,
    ``floor_fmol`` [T, N], ``supply_fmol`` [T], ``supply_floor_fmol`` [T], ``nodes``, ``times_s``
    and the relaxation rates ``rates_per_s`` (the eigenvalues of V^-1 L, ascending).
    """
    epochs = world.epochs if epochs is None else [(exact(t), exact(c)) for t, c in epochs]
    times = world.times if times is None else np.asarray(times, dtype=np.float64)
    L, kb = world.conductance_matrix()
    V = np.array([float(v) for v in world.volume])
    Lf = np.array([[float(x) for x in row] for row in L])
    kbf = np.array([float(x) for x in kb])
    w = np.sqrt(V)
    S = Lf / np.outer(w, w)
    S = 0.5 * (S + S.T)
    lam, Q = np.linalg.eigh(S)
    M = Lf / V[:, None]
    N = world.n
    texact = [exact(t) for t in times]

    def change_eig(d, tau):
        """c(t_e + tau) - c(t_e) = W^-1 Q diag(expm1(lambda tau)) Q^T W d(t_e)."""
        return (Q @ (np.expm1(lam * tau) * (Q.T @ (w * d)))) / w

    def prop_expm(c, tau, cb):
        A = np.zeros((N + 1, N + 1))
        A[:N, :N] = M
        A[:N, N] = kbf * float(cb) / V
        return (expm(A * tau) @ np.append(c, 1.0))[:N]

    def deviation(c, cb):
        """c - c_b with each element's difference taken exactly, then rounded."""
        return np.array([float(exact(x) - cb) for x in c])

    # Chain the epoch starts by each method: the concentrations c(t_e) and, for the primary, the
    # supply S(t_e), so that a record at t_e returns exactly the epoch's start.
    c0 = np.array([float(c) for c in world.c0])
    c_start = [c0.copy()]
    s_start = [0.0]
    c_start_x = [c0.copy()]
    for e in range(1, len(epochs)):
        tau = float(epochs[e][0] - epochs[e - 1][0])
        delta = change_eig(deviation(c_start[-1], epochs[e - 1][1]), tau)
        c_start.append(c_start[-1] + delta)
        s_start.append(s_start[-1] + float(np.sum(V * delta)))
        c_start_x.append(prop_expm(c_start_x[-1], tau, epochs[e - 1][1]))
    amount = np.empty((times.size, N))
    amount_x = np.empty((times.size, N))
    supply = np.empty(times.size)
    supply_x = np.empty(times.size)
    for k, t in enumerate(texact):
        e = _epoch_of(t, epochs)
        tau = float(t - epochs[e][0])
        delta = change_eig(deviation(c_start[e], epochs[e][1]), tau)
        amount[k] = V * (c_start[e] + delta)
        supply[k] = s_start[e] + float(np.sum(V * delta))
        cx = prop_expm(c_start_x[e], tau, epochs[e][1])
        amount_x[k] = V * cx
        supply_x[k] = float(np.sum(V * (cx - c0)))
    # The floor: the two methods' difference plus 16 ulps of the largest amount in play (the
    # primary's own rounding, a few ulps of each term, is not seen by the difference alone).
    scale = np.maximum(np.abs(amount), np.max(V) * max(float(c) for _, c in epochs))
    floor = np.abs(amount - amount_x) + 16 * np.spacing(scale)
    supply_floor = np.abs(supply - supply_x) + 16 * np.spacing(np.max(scale, axis=1) * N)
    rates = np.sort(np.linalg.eigvals(M).real)
    return {
        "species": world.species,
        "nodes": list(world.nodes),
        "times_s": times,
        "amount_fmol": amount,
        "amount_expm_fmol": amount_x,
        "floor_fmol": floor,
        "supply_fmol": supply,
        "supply_floor_fmol": supply_floor,
        "rates_per_s": rates,
    }


def solve_decimal(world: FaceWorld, epochs=None, times=None) -> np.ndarray:
    """Amounts [T, 2] (fmol) for a two-node world by Sylvester's formula in 50-digit decimals."""
    if world.n != 2:
        raise ValueError("the decimal closed form is for two nodes")
    epochs = world.epochs if epochs is None else [(exact(t), exact(c)) for t, c in epochs]
    times = world.times if times is None else np.asarray(times, dtype=np.float64)
    L, _ = world.conductance_matrix()
    with localcontext() as ctx:
        ctx.prec = DIGITS
        M = [[dec(L[i][j] / world.volume[i]) for j in range(2)] for i in range(2)]
        m = (M[0][0] + M[1][1]) / 2
        det = M[0][0] * M[1][1] - M[0][1] * M[1][0]
        delta = (m * m - det).sqrt()
        l1, l2 = m + delta, m - delta

        def prop(d, tau: Decimal):
            e1, e2 = (l1 * tau).exp(), (l2 * tau).exp()
            out = []
            for i in range(2):
                acc = Decimal(0)
                for j in range(2):
                    a = M[i][j] - (l2 if i == j else 0)
                    b = M[i][j] - (l1 if i == j else 0)
                    acc += (e1 * a - e2 * b) / (l1 - l2) * d[j]
                out.append(acc)
            return out

        d_start = [[dec(world.c0[i] - epochs[0][1]) for i in range(2)]]
        for e in range(1, len(epochs)):
            d_end = prop(d_start[-1], dec(epochs[e][0] - epochs[e - 1][0]))
            d_start.append([x + dec(epochs[e - 1][1] - epochs[e][1]) for x in d_end])
        out = np.empty((times.size, 2))
        for k, t in enumerate(times):
            te = exact(t)
            e = _epoch_of(te, epochs)
            d = prop(d_start[e], dec(te - epochs[e][0]))
            for i in range(2):
                out[k, i] = float(dec(world.volume[i]) * (dec(epochs[e][1]) + d[i]))
        return out


def reference(block: dict) -> dict:
    """R-faces on an inputs block: ``solve(parse(block))`` plus the face conductances."""
    world = parse(block)
    out = solve(world)
    out["kappa_pL_per_s"] = kappas(world)
    out["volume_pL"] = [float(v) for v in world.volume]
    return out
