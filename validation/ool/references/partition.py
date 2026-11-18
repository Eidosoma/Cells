"""OL3: the membrane split C3x and the lumen split, exactly as §0.2c rules 9 and 10 define them,
replayable from the parent's fission uniforms (domain 2), with their exact laws by enumeration.

**C3x** (rule 9). The parent's membrane molecules are listed by species in the world's declared
species order (species i contributes n_i entries, each of area k_i quanta). With the first N
uniforms, one per listed molecule:
1. rank the molecules by their uniforms, ascending, ties by list position;
2. S_c is the summed k of the first c ranked molecules (S_0 = 0, S_N = W);
3. c_0 = 0 and c_k = N; for t = 1..k-1, c_t is the smallest c >= c_(t-1) minimising |k S_c - t W|;
4. block t is ranked molecules c_(t-1) + 1 .. c_t;
5. with the next k uniforms, pi is their argsort (ascending, ties by index), and block t goes to
   daughter pi(t).
Indices here are 0-based: block b = 0..k-1 goes to daughter pi[b].

**The lumen** (rule 10). p_j = V_sph(A_j)/Sum_l V_sph(A_l), from the daughters' areas, so with
A_j proportional to W_j, p_j = W_j^(3/2)/Sum W_l^(3/2) (the area quantum cancels). With one more
uniform per lumen molecule, listed by species in declared order, a molecule with uniform u goes to
daughter pi[b] for the smallest b with u < Sum_(s <= b) p_pi[s]; the last cumulative weight is 1.

**The laws** (rule 7's properties, rule 9's reading):
- the daughters' areas sum exactly to the parent's (counts are conserved by construction);
- at equal areas per molecule the split is the multivariate hypergeometric on the balanced size
  vector (N mod k daughters take ceil(N/k), the rest floor(N/k)), assigned to the daughters in a
  uniformly random order;
- the daughters are exchangeable: each one's composition has the same law.
``exact_law`` enumerates every ranking and every pi (N! k! equally likely outcomes, small N) and
returns the law of the daughters' count matrix in exact fractions; ``balanced_hypergeometric_law``
is the closed form it must equal at equal areas.

Planted forms (each must fail): ``g1_sizes`` (G1's floor-to-first sizes, the extra molecules to
the last daughter, and no random order), ``ties_last`` (ties broken by the larger list position),
``no_pi`` (blocks given to daughters in block order), ``largest_c`` (the largest minimiser c).
"""

from __future__ import annotations

import itertools
import math
from fractions import Fraction

PLANTED_SPLITS = ("g1_sizes", "ties_last", "no_pi", "largest_c")


def molecule_list(counts) -> list:
    """Species index per listed molecule, species in declared order."""
    return [i for i, n in enumerate(counts) for _ in range(int(n))]


def rank(uniforms, planted=None) -> list:
    idx = range(len(uniforms))
    if planted == "ties_last":
        return sorted(idx, key=lambda j: (uniforms[j], -j))
    return sorted(idx, key=lambda j: (uniforms[j], j))


def cuts(S, k: int, planted=None) -> list:
    """c_0 = 0, ..., c_k = N, with c_t the smallest (or, planted, largest) minimiser."""
    N, W = len(S) - 1, S[-1]
    c = [0]
    for t in range(1, k):
        best, arg = None, None
        for cc in range(c[-1], N + 1):
            d = abs(k * S[cc] - t * W)
            if best is None or d < best or (planted == "largest_c" and d == best):
                best, arg = d, cc
        c.append(arg)
    c.append(N)
    return c


def c3x(counts, areas_k, k: int, uniforms, planted=None) -> tuple[list, list]:
    """The daughters' membrane counts (k rows, one column per species) and pi, from the uniforms."""
    mols = molecule_list(counts)
    N = len(mols)
    if len(uniforms) < N + k:
        raise ValueError(f"C3x needs {N + k} uniforms, {len(uniforms)} given")
    G = len(counts)
    if planted == "g1_sizes":
        # G1's floor-to-first: floor(N/k) to each daughter but the last, which takes the rest
        order = rank(uniforms[:N])
        size = N // k
        bounds = [b * size for b in range(k)] + [N]
        pi = list(range(k))
    else:
        order = rank(uniforms[:N], planted)
        S = [0]
        for j in order:
            S.append(S[-1] + int(areas_k[mols[j]]))
        bounds = cuts(S, k, planted)
        pi = list(range(k)) if planted == "no_pi" else sorted(range(k), key=lambda j: (uniforms[N + j], j))
    out = [[0] * G for _ in range(k)]
    for b in range(k):
        for j in order[bounds[b]:bounds[b + 1]]:
            out[pi[b]][mols[j]] += 1
    return out, pi


def lumen_weights(daughter_counts, areas_k) -> list:
    """p_j = W_j^(3/2)/Sum W_l^(3/2) (floats: V_sph's exponent makes them irrational)."""
    W = [sum(int(n) * int(a) for n, a in zip(row, areas_k)) for row in daughter_counts]
    v = [w ** 1.5 for w in W]
    tot = sum(v)
    return [x / tot for x in v]


def lumen_split(lumen_counts, p, pi, uniforms) -> list:
    """The daughters' lumen counts (k rows) from one uniform per lumen molecule."""
    k = len(p)
    mols = molecule_list(lumen_counts)
    if len(uniforms) < len(mols):
        raise ValueError(f"the lumen split needs {len(mols)} uniforms")
    cum, acc = [], 0.0
    for b in range(k):
        acc += p[pi[b]]
        cum.append(acc)
    cum[-1] = 1.0
    out = [[0] * len(lumen_counts) for _ in range(k)]
    for j, s in enumerate(mols):
        u = uniforms[j]
        b = next(b for b in range(k) if u < cum[b])
        out[pi[b]][s] += 1
    return out


def split_from_uniforms(counts, areas_k, lumen_counts, k: int, uniforms, planted=None) -> dict:
    """The whole fission's partition from the parent's domain-2 uniforms, in rule 9-10's order."""
    N = sum(int(n) for n in counts)
    mem, pi = c3x(counts, areas_k, k, uniforms[: N + k], planted)
    p = lumen_weights(mem, areas_k)
    lum = lumen_split(lumen_counts, p, pi, uniforms[N + k:])
    return dict(membrane=mem, lumen=lum, pi=pi, weights=p, uniforms_used=N + k + sum(int(x) for x in lumen_counts))


# ---------------------------------------------------------------- exact laws

def exact_law(counts, areas_k, k: int, planted=None) -> dict:
    """The law of the daughters' membrane count matrix, by enumerating every ranking and every pi.

    Rankings stand for the uniforms' order (all N! equally likely, ties having probability zero),
    and pi for the k uniforms' order (k! equally likely)."""
    mols = molecule_list(counts)
    N = len(mols)
    law: dict = {}
    total = 0
    perms_k = list(itertools.permutations(range(k)))
    for order in itertools.permutations(range(N)):
        # a ranking 'order' is produced by uniforms whose ascending order is 'order'
        u = [0.0] * N
        for pos, j in enumerate(order):
            u[j] = (pos + 0.5) / N
        for perm in perms_k:
            uk = [0.0] * k
            for pos, j in enumerate(perm):
                uk[j] = (pos + 0.5) / k
            mem, _ = c3x(counts, areas_k, k, u + uk, planted)
            key = tuple(tuple(r) for r in mem)
            law[key] = law.get(key, 0) + 1
            total += 1
    return {key: Fraction(v, total) for key, v in law.items()}


def balanced_sizes(N: int, k: int) -> list:
    """N mod k daughters take ceil(N/k), the rest floor(N/k) (as a multiset)."""
    return [N // k + (1 if t < N % k else 0) for t in range(k)]


def balanced_hypergeometric_law(counts, k: int) -> dict:
    """The closed form at equal areas: the multivariate hypergeometric on the balanced size vector,
    the sizes assigned to the daughters in a uniformly random order."""
    N, G = sum(counts), len(counts)
    sizes = balanced_sizes(N, k)
    law: dict = {}
    orders = list(itertools.permutations(range(k)))
    for perm in orders:
        sz = [sizes[perm[j]] for j in range(k)]
        for mat in _matrices(list(counts), sz):
            num = 1
            for i in range(G):
                col = [mat[j][i] for j in range(k)]
                num *= math.factorial(counts[i]) // math.prod(math.factorial(x) for x in col)
            den = math.factorial(N) // math.prod(math.factorial(s) for s in sz)
            key = tuple(tuple(r) for r in mat)
            law[key] = law.get(key, Fraction(0)) + Fraction(num, den) / len(orders)
    return law


def _matrices(col_totals, row_sizes):
    """Every k x G non-negative integer matrix with the given row sums and column sums."""
    k = len(row_sizes)

    def rows(j, remaining):
        if j == k - 1:
            if sum(remaining) == row_sizes[j]:
                yield [list(remaining)]
            return
        for r in _compositions_bounded(row_sizes[j], remaining):
            rest = [a - b for a, b in zip(remaining, r)]
            for tail in rows(j + 1, rest):
                yield [r] + tail

    yield from rows(0, col_totals)


def _compositions_bounded(total, bounds):
    if len(bounds) == 1:
        if total <= bounds[0]:
            yield [total]
        return
    for first in range(min(total, bounds[0]) + 1):
        for rest in _compositions_bounded(total - first, bounds[1:]):
            yield [first] + rest


def total_variation(p: dict, q: dict) -> Fraction:
    keys = set(p) | set(q)
    return sum(abs(p.get(x, Fraction(0)) - q.get(x, Fraction(0))) for x in keys) / 2


def daughter_marginals(law: dict, k: int) -> list:
    """Each daughter's composition law (exchangeability: all k equal)."""
    out = [dict() for _ in range(k)]
    for key, pr in law.items():
        for j in range(k):
            out[j][key[j]] = out[j].get(key[j], Fraction(0)) + pr
    return out
