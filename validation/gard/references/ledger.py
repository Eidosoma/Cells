"""Row 8. The thermodynamic ledger: cumulative heat equals k_BT Delta ln pi, plus the
fission and sink terms, at every saved row.

Claim (GARD_DESIGN §2.4). Each event books q = ln(w(x -> x') / w(x' -> x)) in k_BT.
For the pair-consistent law the booking is a state function. Let ln pi~ be the
unnormalised product measure, ln[(N - 1)! prod (K_i rho_i)^{x_i} / x_i!]. Detailed
balance gives q = ln pi~(x') - ln pi~(x) for every event. A fission books work
W_f = ln pi(P) - ln pi(D1) - ln pi(D2) on the assembly. The sink receives
S_f = -ln pi(U) for the unfollowed daughter U. Across a fission, ln pi of the slot jumps
from ln pi(P) to ln pi(D), and W_f - S_f = ln pi(P) - ln pi(D) cancels that jump exactly.
So at every row r:
    Q(r) - Q(0) = [ln pi(x_r) - ln pi(x_0)] + W(r) - S(r).
A normalising constant C (ln pi = ln pi~ + C) cancels in W - S.

The reference's checks:
A. Convention-free, the hard one. Over each growth segment (start row to the first
   parent row, then each daughter row to the next parent row), Delta Q equals
   Delta ln pi~, computed by the reference. Across each fission pair, Delta Q = 0.
B. The engine's ``log_weight`` equals ln pi~ + C, with one constant C on every row.
C. The work and sink increments equal the declared conventions in the engine's constant.
   They are zero inside growth segments.
D. Closure: the engine's ``ledger_residual_kT`` equals
   Q - (Delta log_weight + W - S). For the pair-consistent law it is zero to rounding;
   for the single-event law it is reported, as the unsourced cycle work.
E. Booking: replaying the event trace from the founder, the cumulative sum of
   ln(forward/reverse propensity) at each row's ``row_event`` equals the saved heat, in
   either form.

Tolerance. ``rounding_tol(E, M, G)`` = u [E (2G + 72) + 8 (E + 2) M + 64]. Each event's
q is two logs of propensities, each with relative error up to about (G + 4) u,
so q is off by at most about 2 (G + 4) u plus 64 u for the logs. Each of the E running
additions is off by at most u times a magnitude M that bounds |Q| and |ln pi|. For a
60-event growth at G = 100 and M = 300 that is 1.8e-11. A heat sign error moves a
growth's heat by twice its size, about 2 x 90 k_BT.

Planted control: a heat sign error. A and E must catch it.
"""

from __future__ import annotations

import numpy as np

from .common import UNIT_ROUNDOFF, CheckResult
from .conservation import followed_and_unfollowed
from .kernels import PAIR_CONSISTENT, ExchangeLaw, event_heat, log_weight, propensities


def rounding_tol(n_events: int, magnitude: float, n_types: int) -> float:
    u = UNIT_ROUNDOFF
    return u * (n_events * (2 * n_types + 72) + 8 * (n_events + 2) * magnitude + 64)


def check_ledger(law: ExchangeLaw, count, heat, work, sink, log_w, residual, fission_split, fission_followed,
                 row_event, event_channel=None, founder=None, end_row: bool = False) -> CheckResult:
    count = np.asarray(count)[:, :, 0].astype(np.int64)
    R, G = count.shape
    F = int(np.asarray(fission_split).shape[0])
    parents = 1 + 2 * np.arange(F)
    daughters = parents + 1
    Q = np.asarray(heat, dtype=np.float64)[:, 0]
    W = np.asarray(work, dtype=np.float64)[:, 0]
    S = np.asarray(sink, dtype=np.float64)[:, 0]
    LW = np.asarray(log_w, dtype=np.float64)[:, 0]
    RES = np.asarray(residual, dtype=np.float64)[:, 0]
    row_event = np.asarray(row_event, dtype=np.int64)
    lp = np.array([log_weight(law, count[r]) for r in range(R)])
    mag = float(max(np.max(np.abs(Q)), np.max(np.abs(lp)), np.max(np.abs(LW)), np.max(np.abs(W)),
                    np.max(np.abs(S)), 1.0))
    segs = ([(0, int(parents[0]))] + [(int(daughters[f]), int(parents[f + 1])) for f in range(F - 1)]) if F else []
    if end_row:
        segs.append((int(daughters[-1]) if F else 0, R - 1))  # the final growth, to the end row
    elif not F:
        segs = [(0, R - 1)]
    seg_err = []
    for a, b in segs:
        E = int(row_event[b] - row_event[a])
        err = (Q[b] - Q[a]) - (lp[b] - lp[a])
        seg_err.append((a, b, float(err), rounding_tol(E, mag, G)))
    seg_abs = np.array([abs(e) for _, _, e, _ in seg_err])
    seg_tol = np.array([t for _, _, _, t in seg_err])
    closes = bool(np.all(seg_abs <= seg_tol))
    pair_heat = [float(Q[daughters[f]] - Q[parents[f]]) for f in range(F)]
    no_fission_heat = all(v == 0.0 for v in pair_heat)
    # B. log_weight = ln pi~ + C
    C = LW - lp
    c0 = float(np.median(C))
    const_tol = rounding_tol(0, mag, G)
    lw_ok = bool(np.all(np.abs(C - c0) <= const_tol))
    # C. work and sink increments
    w_err, s_err = [], []
    for f in range(F):
        pr, dr = int(parents[f]), int(daughters[f])
        P = count[pr]
        D, U = followed_and_unfollowed(P, np.asarray(fission_split)[f], np.asarray(fission_followed)[f])
        d1 = np.asarray(fission_split)[f]
        d2 = P - d1
        want_w = log_weight(law, P) - log_weight(law, d1) - log_weight(law, d2) - c0
        want_s = -log_weight(law, U) - c0
        w_err.append(abs((W[dr] - W[pr]) - want_w))
        s_err.append(abs((S[dr] - S[pr]) - want_s))
    growth_rows = [(a, b) for a, b in segs]
    w_flat = all(W[b] == W[a] and S[b] == S[a] for a, b in growth_rows)
    ws_ok = bool((not w_err or max(w_err) <= const_tol and max(s_err) <= const_tol) and w_flat)
    # D. closure residual
    mine = Q - Q[0] - ((LW - LW[0]) + (W - W[0]) - (S - S[0]))
    total_tol = rounding_tol(int(row_event[-1]), mag, G)
    resid_matches = bool(np.all(np.abs(RES - mine) <= total_tol))
    max_resid = float(np.max(np.abs(mine)))
    # E. booking along the trace
    booking = None
    if event_channel is not None and founder is not None:
        booking = _check_booking(law, np.asarray(founder, dtype=np.int64), count, Q,
                                 np.asarray(event_channel, dtype=np.int64), row_event, F, mag, parents, daughters)
    if law.form == PAIR_CONSISTENT:
        passed = closes and no_fission_heat and lw_ok and ws_ok and resid_matches and max_resid <= total_tol
    else:
        passed = no_fission_heat and lw_ok and ws_ok and resid_matches
    if booking is not None:
        passed = passed and booking["ok"]
    return CheckResult("thermodynamic_ledger", bool(passed), dict(
        form=law.form, rows=R, fissions=F,
        convention_free_closes=closes, max_segment_error=float(seg_abs.max()) if seg_abs.size else 0.0,
        max_segment_tol=float(seg_tol.max()) if seg_tol.size else 0.0,
        heat_booked_at_fissions=not no_fission_heat, log_weight_constant=c0, log_weight_constant_ok=lw_ok,
        work_sink_ok=ws_ok, max_work_error=float(max(w_err)) if w_err else 0.0,
        max_sink_error=float(max(s_err)) if s_err else 0.0,
        residual_matches_engine=resid_matches, max_closure_residual=max_resid,
        unsourced_cycle_work=max_resid if law.form != PAIR_CONSISTENT else None,
        closure_tol=total_tol, booking=booking))


def _check_booking(law, founder, count, Q, chan, row_event, F, mag, parent_rows, daughter_rows) -> dict:
    G = founder.size
    x = founder.copy()
    q_cum = np.zeros(chan.size + 1)
    parents: dict = {}
    for f in range(F):
        parents.setdefault(int(row_event[parent_rows[f]]), f)  # the first fission at that event count
    acc = 0.0
    ap, am = propensities(law, x)
    for k, code in enumerate(chan):
        i = abs(int(code)) - 1
        sign = 1 if code > 0 else -1
        y = x.copy()
        y[i] += sign
        bp, bm = propensities(law, y)
        acc += event_heat(law, x, i, sign, (ap, am), (bp, bm))
        q_cum[k + 1] = acc
        x = y
        ap, am = bp, bm
        f = parents.get(k + 1)
        while f is not None:
            if not np.array_equal(x, count[parent_rows[f]]):
                return dict(ok=False, error=f"trace does not reach the parent of fission {f}")
            x = count[daughter_rows[f]].copy()
            ap, am = propensities(law, x)
            # a daughter born at the fission size splits at once, before any event
            nxt = f + 1
            f = nxt if nxt < F and int(row_event[parent_rows[nxt]]) == k + 1 else None
    want = q_cum[row_event]
    tol = rounding_tol(int(row_event[-1]), mag, G)
    err = np.abs(want - (Q - Q[0]))
    return dict(ok=bool(np.all(err <= tol)), max_error=float(err.max()), tol=tol)
