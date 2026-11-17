"""Row 7. Conservation: the exact integer identity per slot.

Claim (GARD_DESIGN §5.1): in single-lineage mode, at every saved row, for every type,
    count = founders + joined - left - discarded,
in exact integers. A dropped molecule must be caught.

The reference checks, in integers only:
1. The identity at every row and type. Founders come from the world record.
2. The row layout: the start row, then two rows per fission, so there are 1 + 2F rows.
3. Cumulative totals never decrease, and no count is negative.
4. At each fission (parent row 1 + 2f, daughter row 2 + 2f), the count falls from the
   parent P to the followed daughter D, and the discarded total rises by exactly the
   unfollowed daughter U = P - D. D is the recorded split d if the first daughter is
   followed, and P - d otherwise. Joined and left do not change across the pair.
5. The event trace (on by default for one lineage) replayed from the founders. Each
   signed channel +(i+1) joins type i and -(i+1) leaves it. Each growth ends at its
   recorded parent, and the joined and left totals at each row equal the trace's counts
   of +1 and -1 events up to ``row_event``.

Population mode adds between-slot transfers at fissions; it is outside this reference
and refused loudly.
"""

from __future__ import annotations

import numpy as np

from .common import CheckResult


def followed_and_unfollowed(P: np.ndarray, split: np.ndarray, followed: int) -> tuple[np.ndarray, np.ndarray]:
    d1 = np.asarray(split, dtype=np.int64)
    d2 = np.asarray(P, dtype=np.int64) - d1
    if int(followed) not in (0, 1):
        raise ValueError(f"fission_followed must be 0 or 1, found {followed}")
    return (d1, d2) if int(followed) == 0 else (d2, d1)


def check_conservation(founder, count, joined, left, discarded, fission_split, fission_followed,
                       event_channel=None, events_per_growth=None, row_event=None) -> CheckResult:
    founder = np.asarray(founder, dtype=np.int64)
    count = np.asarray(count)
    R, G, A = count.shape
    F = int(np.asarray(fission_split).shape[0])
    problems: list[str] = []
    if A != 1:
        problems.append(f"{A} assembly slots; only single-lineage mode (one slot) is covered")
    if R != 1 + 2 * F:
        problems.append(f"{R} rows for {F} fissions; the layout needs 1 + 2F = {1 + 2 * F}")
    if problems:
        return CheckResult("conservation", False, dict(problems=problems))
    c = count[:, :, 0].astype(np.int64)
    j = np.asarray(joined)[:, :, 0].astype(np.int64)
    lv = np.asarray(left)[:, :, 0].astype(np.int64)
    dc = np.asarray(discarded)[:, :, 0].astype(np.int64)
    ident = c - (founder[None, :] + j - lv - dc)
    bad_rows = np.flatnonzero(np.any(ident != 0, axis=1))
    monotone = bool(np.all(np.diff(j, axis=0) >= 0) and np.all(np.diff(lv, axis=0) >= 0)
                    and np.all(np.diff(dc, axis=0) >= 0))
    nonneg = bool(np.all(c >= 0) and np.all(j >= 0) and np.all(lv >= 0) and np.all(dc >= 0))
    fission_bad = []
    for f in range(F):
        pr, dr = 1 + 2 * f, 2 + 2 * f
        P = c[pr]
        D, U = followed_and_unfollowed(P, np.asarray(fission_split)[f], np.asarray(fission_followed)[f])
        if np.any(D < 0) or np.any(U < 0) or not np.array_equal(c[dr], D) \
                or not np.array_equal(dc[dr] - dc[pr], U) \
                or not np.array_equal(j[dr], j[pr]) or not np.array_equal(lv[dr], lv[pr]):
            fission_bad.append(f)
    trace = None
    if event_channel is not None:
        trace = _check_trace(founder, c, j, lv, np.asarray(event_channel, dtype=np.int64),
                             None if events_per_growth is None else np.asarray(events_per_growth, dtype=np.int64),
                             None if row_event is None else np.asarray(row_event, dtype=np.int64), F)
    passed = bool(bad_rows.size == 0 and monotone and nonneg and not fission_bad
                  and (trace is None or trace["ok"]))
    return CheckResult("conservation", passed, dict(
        rows=R, fissions=F, identity_failures=int(bad_rows.size),
        first_failing_row=None if bad_rows.size == 0 else int(bad_rows[0]),
        cumulative_monotone=monotone, nonnegative=nonneg, fission_failures=fission_bad[:10],
        trace=trace))


def _check_trace(founder, c, j, lv, chan, epg, row_event, F) -> dict:
    G = founder.size
    E = chan.size
    types = np.abs(chan) - 1
    if np.any(chan == 0) or np.any(types >= G):
        return dict(ok=False, error="event_channel holds a code outside +-(1..G)")
    joins = np.zeros((E + 1, G), dtype=np.int64)
    leaves = np.zeros((E + 1, G), dtype=np.int64)
    np.add.at(joins[1:], (np.arange(E)[chan > 0], types[chan > 0]), 1)
    np.add.at(leaves[1:], (np.arange(E)[chan < 0], types[chan < 0]), 1)
    joins = np.cumsum(joins, axis=0)
    leaves = np.cumsum(leaves, axis=0)
    out = dict(ok=True, events=int(E))
    if row_event is not None:
        if row_event.size != c.shape[0] or np.any(row_event < 0) or np.any(row_event > E):
            return dict(ok=False, error="row_event does not index the trace")
        out["totals_match_trace"] = bool(np.array_equal(joins[row_event], j) and np.array_equal(leaves[row_event], lv))
        out["ok"] &= out["totals_match_trace"]
    if epg is not None:
        ends = np.cumsum(epg)
        if ends.size < F or (ends.size and ends[-1] > E):
            return dict(ok=False, error=f"events_per_growth ({epg.size} growths) does not cover {F} fissions")
        x = founder.copy()
        start = 0
        growth_ok = True
        for f in range(F):
            seg = chan[start:ends[f]]
            np.add.at(x, np.abs(seg) - 1, np.sign(seg))
            if not np.array_equal(x, c[1 + 2 * f]):
                growth_ok = False
                break
            x = c[2 + 2 * f].copy()
            start = ends[f]
        out["growths_end_at_parents"] = growth_ok
        out["ok"] &= growth_ok
    return out
