"""Row 10. Observers: H against NumPy, the strict inheritance threshold, and F12's
predicate over all 4,096 twelve-boundary sequences.

Sources: PNAS 2000 Eq. 2, H(n_p, n_q) = v_p . v_q with v = n/|n|. The preprint p. 11
(and its reader's guide and Appendix B): H(x, y) = x . y / (|x|_2 |y|_2), and
inheritance at a boundary is strict, I_t = 1{H(P_t, D_t) > 0.9}, so H = 0.9 is a break.
F12 (JOINT_BREAK_RUN3, p. 11): within the next twelve fissions, an inheritance break
and, strictly after it, three consecutive inherited fissions. A break with no later run
of three, or a run with no earlier break, scores zero. The preprint (p. 68) checked its
detector against an independent predicate on all 4,096 sequences, with floating and
exact integer thresholds agreeing. Extinction before certification is negative, and an
event certified before a later extinction stays positive (Appendix F).

References:
- ``similarity``: H by NumPy, for checking the engine's ``fission_similarity``
  (parent against each daughter) and H(P_t, D_t) from the two fission rows.
- ``inherited_exact``: the threshold in exact integers. For nonnegative counts,
  H > 9/10 iff x . y > 0 and 100 (x . y)^2 > 81 |x|^2 |y|^2. For masses up to 80,
  |H - 0.9| is either 0 or at least about 5e-10, so a float H decides correctly except at
  exactly 0.9. There, rounding the norms can push a float H above 0.9.
  ``make_observer_probes`` includes such exact-0.9 pairs.
- Two independent F12 predicates. ``f12_scan`` is a left-to-right automaton.
  ``f12_regex`` searches for the pattern 0[01]*111. Both must give ``F12_POSITIVES``
  = 2065 positives of 4,096. That count is derived in closed form: a sequence is negative
  iff it is all ones, or its first break is followed by a suffix with no 111. Strings
  of length m with no 111 number a(m) = a(m-1) + a(m-2) + a(m-3), with a(0..2) = 1, 2, 4,
  so negatives = 1 + sum_{m=0}^{11} a(m) = 2031.

Planted control: H = 0.9 counted as inherited (a >= threshold), caught on the exact-0.9
probes. An off-by-one F12 detector is also caught by the exhaustive table.
"""

from __future__ import annotations

import itertools
import re

import numpy as np

from .common import CheckResult

H_ATOL = 1e-14
HORIZON = 12
F12_POSITIVES = 2065
F12_PATTERN = re.compile(r"0[01]*111")


def similarity(x, y) -> float:
    """H(x, y) by NumPy; NaN if either vector is empty."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    nx, ny = np.linalg.norm(x), np.linalg.norm(y)
    if nx == 0.0 or ny == 0.0:
        return float("nan")
    return float(np.dot(x, y) / (nx * ny))


def inherited_exact(x, y) -> bool:
    """1{H(x, y) > 0.9} in exact integer arithmetic (nonnegative, nonzero vectors)."""
    xi = [int(v) for v in np.asarray(x).ravel()]
    yi = [int(v) for v in np.asarray(y).ravel()]
    if any(v < 0 for v in xi + yi):
        raise ValueError("compositions are nonnegative")
    nx = sum(v * v for v in xi)
    ny = sum(v * v for v in yi)
    if nx == 0 or ny == 0:
        raise ValueError("H is undefined for an empty composition")
    dot = sum(a * b for a, b in zip(xi, yi))
    return dot > 0 and 100 * dot * dot > 81 * nx * ny


def f12_scan(marks, horizon: int = HORIZON) -> bool:
    seen_break = False
    run = 0
    for m in list(marks)[:horizon]:
        if not m:
            seen_break = True
            run = 0
        elif seen_break:
            run += 1
            if run >= 3:
                return True
    return False


def f12_regex(marks, horizon: int = HORIZON) -> bool:
    s = "".join("1" if m else "0" for m in list(marks)[:horizon])
    return F12_PATTERN.search(s) is not None


def sequence(index: int, bit_order: str = "lsb_first", horizon: int = HORIZON) -> list[bool]:
    bits = [bool((index >> t) & 1) for t in range(horizon)]
    if bit_order == "lsb_first":
        return bits
    if bit_order == "msb_first":
        return bits[::-1]
    raise ValueError(f"unknown bit order {bit_order!r}")


def f12_reference_table(bit_order: str = "lsb_first") -> np.ndarray:
    return np.array([f12_scan(sequence(k, bit_order)) for k in range(1 << HORIZON)], dtype=bool)


def check_f12_table(table, bit_order: str = "lsb_first") -> CheckResult:
    """An F12 detector's verdicts on all 4,096 sequences against both reference predicates."""
    table = np.asarray(table).astype(bool).ravel()
    if table.size != 1 << HORIZON:
        return CheckResult("f12_exhaustive", False, dict(error=f"{table.size} verdicts, expected 4096"))
    scan = f12_reference_table(bit_order)
    regex = np.array([f12_regex(sequence(k, bit_order)) for k in range(1 << HORIZON)], dtype=bool)
    refs_agree = bool(np.array_equal(scan, regex)) and int(scan.sum()) == F12_POSITIVES
    wrong = np.flatnonzero(table != scan)
    return CheckResult("f12_exhaustive", bool(refs_agree and wrong.size == 0), dict(
        bit_order=bit_order, references_agree=refs_agree, reference_positives=int(scan.sum()),
        detector_positives=int(table.sum()), mismatches=int(wrong.size),
        first_mismatches=[("".join("1" if b else "0" for b in sequence(int(k), bit_order)), bool(table[k]))
                          for k in wrong[:5]]))


def check_fission_similarity(parents, splits, followed, daughters_rows, fission_similarity) -> CheckResult:
    """fission_similarity [f, 2] against NumPy, and H(P_t, D_t) from the rows."""
    parents = np.asarray(parents, dtype=np.int64)
    splits = np.asarray(splits, dtype=np.int64)
    sim = np.asarray(fission_similarity, dtype=np.float64)
    F = parents.shape[0]
    err = 0.0
    nan_mismatch = 0
    row_err = 0.0
    for f in range(F):
        P = parents[f]
        for k, d in enumerate((splits[f], P - splits[f])):
            want = similarity(P, d)
            got = sim[f, k]
            if np.isnan(want) or np.isnan(got):
                nan_mismatch += int(np.isnan(want) != np.isnan(got))
            else:
                err = max(err, abs(got - want))
        D = np.asarray(daughters_rows[f], dtype=np.int64)
        h_rows = similarity(P, D)
        h_rec = sim[f, int(np.asarray(followed)[f])]
        if not (np.isnan(h_rows) and np.isnan(h_rec)):
            row_err = max(row_err, abs(h_rows - h_rec))
    passed = err <= H_ATOL and row_err <= H_ATOL and nan_mismatch == 0
    return CheckResult("fission_similarity", bool(passed), dict(
        fissions=F, max_abs_error=err, max_row_pair_error=row_err, nan_mismatches=nan_mismatch, atol=H_ATOL))


def exact_point_nine_pairs(max_entry: int = 12, n_types: int = 4, limit: int = 200) -> list[tuple]:
    """Small nonnegative integer pairs with H exactly 0.9, found by search."""
    out = []
    vecs = [v for v in itertools.product(range(max_entry + 1), repeat=n_types) if any(v)]
    rng = np.random.default_rng(9)
    picks = rng.choice(len(vecs), size=min(len(vecs), 3000), replace=False)
    cand = [vecs[k] for k in picks]
    for x in cand:
        nx = sum(v * v for v in x)
        for y in cand:
            ny = sum(v * v for v in y)
            dot = sum(a * b for a, b in zip(x, y))
            if dot > 0 and 100 * dot * dot == 81 * nx * ny:
                out.append((x, y))
                if len(out) >= limit:
                    return out
    return out


def make_observer_probes(rng: np.random.Generator, n_types: int = 100, n_random: int = 200) -> dict:
    """Probe pairs (parent, daughter) for the engine's H and inheritance mark.

    The probes are: exact-0.9 pairs, including ones whose float H rounds above 0.9; near
    ties on both sides; and random GARD-like pairs, with mass-80 parents and mass-40
    daughters drawn without replacement.
    """
    pairs = []
    P = np.zeros(n_types, dtype=np.int64); P[:4] = (45, 15, 15, 5)
    D = np.zeros(n_types, dtype=np.int64); D[0] = 40
    pairs.append((P, D))
    P = np.zeros(n_types, dtype=np.int64); P[:5] = (45, 20, 5, 5, 5)
    pairs.append((P, D.copy()))
    for x, y in exact_point_nine_pairs():
        a = np.zeros(n_types, dtype=np.int64); a[:len(x)] = x
        b = np.zeros(n_types, dtype=np.int64); b[:len(y)] = y
        pairs.append((a, b))
    for tail in (4, 6):  # near ties: H = 0.9016 and 0.8980
        P = np.zeros(n_types, dtype=np.int64); P[:4] = (45, 15, 15, tail)
        pairs.append((P, D.copy()))
    for _ in range(n_random):
        k = int(rng.integers(5, 41))
        types = rng.choice(n_types, size=k, replace=False)
        P = np.zeros(n_types, dtype=np.int64)
        P[types] = 1 + rng.multinomial(80 - k, np.full(k, 1.0 / k))
        d = rng.multivariate_hypergeometric(P, 40)
        pairs.append((P, d))
    parents = np.stack([p for p, _ in pairs])
    daughters = np.stack([d for _, d in pairs])
    return dict(probe_parent=parents, probe_daughter=daughters)


def check_observer_probes(parents, daughters, H_engine, inherited_engine) -> CheckResult:
    parents = np.asarray(parents)
    daughters = np.asarray(daughters)
    H_engine = np.asarray(H_engine, dtype=np.float64)
    mark = np.asarray(inherited_engine).astype(bool)
    want_H = np.array([similarity(p, d) for p, d in zip(parents, daughters)])
    want_I = np.array([inherited_exact(p, d) for p, d in zip(parents, daughters)])
    h_err = float(np.max(np.abs(H_engine - want_H)))
    wrong = np.flatnonzero(mark != want_I)
    exact_nine = np.array([100 * int(np.dot(p, d)) ** 2 == 81 * int(np.dot(p, p)) * int(np.dot(d, d))
                           for p, d in zip(parents, daughters)])
    return CheckResult("observer_probes", bool(h_err <= H_ATOL and wrong.size == 0), dict(
        probes=int(parents.shape[0]), exact_point_nine=int(exact_nine.sum()), max_abs_H_error=h_err,
        mark_mismatches=int(wrong.size), mismatches_at_exact_point_nine=int(np.sum(exact_nine[wrong])),
        atol=H_ATOL))
