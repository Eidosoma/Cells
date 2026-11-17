"""Row OL1-5: the ledgers for reactions close against one free-energy function.

Claim (§3.3, §7.1). At every saved row, F(n_t) - F(n_0) = W_t - Q_t: the reservoir work booked
by held species minus the cumulative heat released (OL1 has no fission, schedule or sink terms;
those join in OL3 and OL4).

**Booking, per event** (the family's declared form, re-derived from §0.1). An event that fires
step r forward from n to n' releases heat q = ln a+(n) - ln a-(n') = -(F(n') - F(n)) + w_r and
books reservoir work w_r = -Sum_h nu_h mu_h. Its reverse books -q and -w_r. A one-way extinct
event books its heat against F_mem(empty) = 0, by the same formula.

**The checks:**
1. the trace, replayed from the initial state, reproduces the counts at every row, in exact
   integers;
2. the engine's cumulative Q and W at every row equal the reference's re-booking from the trace
   (the reference sums with ``math.fsum``, correctly rounded);
3. **closure:** with the engine's Q and W and the reference's F,
   |F(n_t) - F(n_0) - (W_t - Q_t)| is within tolerance at every row.

**Tolerance (derived).** The engine forms each event's q from at most a dozen terms of size at
most L = max |ln a|, so each carries an error of at most 16 u (1 + L); a running sum of E such
terms adds at most gamma_E Sum |q_e| (gamma_E = E u/(1 - E u), Higham's bound for recursive
summation). F(n_t) - F(n_0) is computed by the reference from exact values (error below
4 u (|F_t| + |F_0|)). The tolerance is the sum of these three bounds, doubled:
    tol_t = 2 [16 u E_t (1 + L) + gamma_E (Sum_e<=t |q_e| + |w_e|) + 4 u (|F_t| + |F_0|)].
A heat sign error moves the closure by 2 Q_t, and a dropped reservoir term by W_t, both of order
one or more after the first few events of the registered run (it starts supersaturated in A).
"""

from __future__ import annotations

import math

import numpy as np

from .common import UNIT_ROUNDOFF, CheckResult
from .laws import Law
from .ssa_oracle import ChannelTable, FloatRates

U = UNIT_ROUNDOFF


def rebook(law: Law, table: ChannelTable, n0, event_channel) -> dict:
    """Re-book every event of a trace: per-event heat q and work w, and the states visited."""
    rates = FloatRates(law)
    code_to_row = {c: j for j, c in enumerate(table.code)}
    n = np.array(n0, dtype=np.int64)
    work = [law.reservoir_work(st) for st in law.world.steps]
    q, w, states, lmax = [], [], [n.copy()], 0.0
    for code in event_channel:
        j = code_to_row[int(code)]
        r, s = table.step[j], table.sign[j]
        if s > 0:
            a_f = rates.forward(r, n)
            p = n + rates.nu[r]
            a_b = rates.reverse(r, p)
            one_way = a_b == 0.0
            if one_way:
                dq = -(law.free_energy(tuple(p)) - law.free_energy(tuple(n))) + work[r]
            else:
                dq = math.log(a_f) - math.log(a_b)
            q.append(dq)
            w.append(work[r])
            lmax = max(lmax, abs(math.log(a_f)), 0.0 if one_way else abs(math.log(a_b)))
            n = p
        else:
            a_b = rates.reverse(r, n)
            p = n - rates.nu[r]
            a_f = rates.forward(r, p)
            one_way = a_f == 0.0
            if one_way:
                dq = -(law.free_energy(tuple(p)) - law.free_energy(tuple(n))) - work[r]
            else:
                dq = math.log(a_b) - math.log(a_f)
            q.append(dq)
            w.append(-work[r])
            lmax = max(lmax, abs(math.log(a_b)), 0.0 if one_way else abs(math.log(a_f)))
            n = p
        if np.any(n < 0):
            raise ValueError("the trace drives a count negative")
        states.append(n.copy())
    return dict(q=np.array(q), w=np.array(w), states=np.array(states), max_abs_log_rate=lmax)


def check_ledger(law: Law, table: ChannelTable, n0, event_channel, row_event, counts, heat, work) -> CheckResult:
    """Rows: ``row_event[k]`` events have fired at row k; ``counts[k]`` the finite places' counts;
    ``heat[k]`` and ``work[k]`` the engine's cumulative Q and W (k_BT)."""
    book = rebook(law, table, n0, event_channel)
    q, w, states = book["q"], book["w"], book["states"]
    L = book["max_abs_log_rate"]
    F0 = law.free_energy(tuple(int(v) for v in n0))
    gamma = lambda E: E * U / (1 - E * U)  # noqa: E731
    rows, problems, worst = [], [], 0.0
    for k, e in enumerate(np.asarray(row_event, dtype=np.int64)):
        n_ref = states[e]
        if not np.array_equal(n_ref, np.asarray(counts[k], dtype=np.int64)):
            problems.append(dict(row=k, problem="counts differ from the replayed trace",
                                 engine=np.asarray(counts[k]).tolist(), trace=n_ref.tolist()))
            continue
        Q_ref, W_ref = math.fsum(q[:e]), math.fsum(w[:e])
        Ft = law.free_energy(tuple(int(v) for v in n_ref))
        tol = 2 * (16 * U * e * (1 + L) + gamma(max(e, 1)) * (math.fsum(np.abs(q[:e])) + math.fsum(np.abs(w[:e])))
                   + 4 * U * (abs(Ft) + abs(F0)))
        closure = (Ft - F0) - (float(work[k]) - float(heat[k]))
        dq, dw = float(heat[k]) - Q_ref, float(work[k]) - W_ref
        worst = max(worst, abs(closure))
        bad = abs(closure) > tol or abs(dq) > tol or abs(dw) > tol
        rows.append(dict(row=k, events=int(e), closure=closure, heat_minus_rebooked=dq, work_minus_rebooked=dw, tol=tol))
        if bad:
            problems.append(dict(row=k, closure=closure, heat_minus_rebooked=dq, work_minus_rebooked=dw, tol=tol))
    return CheckResult("ledger_closure", not problems,
                       dict(rows=len(rows), events=int(len(q)), max_abs_closure=worst, problems=problems[:5],
                            conventions=law.conv.as_dict()))
