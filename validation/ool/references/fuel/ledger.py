"""Rows OL4-3 and OL4-4: closure with fuel, the payers' split, and the moieties (fuel note §5
checks 2 and 5).

**Records** (canonical run layout, OL1's ``records.py`` plus one array): ``event_channel``,
``event_time``, ``row_event``, ``counts`` [rows, D] over the finite places, ``heat_kT`` and
``work_kT`` (cumulative), and ``supplied`` [rows, H]: for each held place, in the world's place
order, the net number of molecules its reservoir has supplied to the system (a molecule a step
takes from the reservoir counts +1, one it puts into the reservoir -1). The engine's
``reservoir_supplied`` is this record (fuel note §1, "Reservoir work").

**OL4-3, closure** (§5.2, engine note §3.3). The trace is replayed in exact integers and every
event re-booked: q = ln a(drawn) - ln a(reverse at the new state) = -Delta F + w and w = -Sum_h nu_h
mu_h (OL1's ``ledger.check_ledger``, unchanged). At every row F(n_t) - F(n_0) = W_t - Q_t within its
derived bound. With held fuel W gains mu_F - mu_W per net fuel event; with finite fuel the fuel's
free energy is inside F and W gains nothing.

**The payers' split.** W_t = Sum_h mu_h supplied_h(t) at every row: the split by payer is exact
from the supply record (fuel note §1). Tolerance 2(16 u E_t (1 + max|mu|) + 4 u Sum_h |mu_h
supplied_h|), the same form as OL1's closure bound.

**OL4-4, moieties** (§5.5). For the block's moiety and the fuel's,
    Sum_s M_s n_s(t) - Sum_held M_h supplied_h(t)
is the same integer at every row. The supply record is also re-derived from the trace (each event
supplies -nu_h of each held place) and must equal the engine's exactly.

Planted: the fuel's term dropped from F (an engine error, ``law.FuelLaw('fuel_term_dropped')``,
registered on the finite-fuel world, the one place it bites); reservoir work dropped; and three
reader's errors applied to honest records: the payers swapped, every reservoir's supply ignored
(registered on the worlds where it bites: held fuel with finite waste, and the held-block world;
with fuel and waste both held the fuel's finite sum is zero, so it cannot bite there), and the
waste's supply ignored (the both-held world, the note's §8 plant).
"""

from __future__ import annotations

import math

import numpy as np

from ..common import UNIT_ROUNDOFF, CheckResult
from ..ledger import check_ledger
from ..ssa_oracle import ChannelTable
from ..world import World

U = UNIT_ROUNDOFF
READER_PLANTS = ("payers_swapped", "supply_ignored", "waste_supply_ignored")


def held_places(world: World) -> list:
    return [p.name for p in world.places.values() if p.held]


def held_nu(world: World) -> np.ndarray:
    """[R, H]: the net change of each held place's reservoir-side count per forward event, nu_h."""
    H = held_places(world)
    out = np.zeros((len(world.steps), len(H)), dtype=np.int64)
    for r, st in enumerate(world.steps):
        for h, v in world.nu_held(st).items():
            out[r, H.index(h)] = v
    return out


def held_mu(world: World) -> np.ndarray:
    c0 = world.c0_mM.exact
    return np.array([world.places[h].mu0_kT + math.log(float(world.places[h].held_mM.exact / c0))
                     for h in held_places(world)])


def supplied_from_trace(world: World, table: ChannelTable, event_channel, row_event) -> np.ndarray:
    """[rows, H]: the net supply of each held place at each row, re-derived from the channels."""
    nu = held_nu(world)
    code_to_row = {c: j for j, c in enumerate(table.code)}
    per = np.zeros((len(event_channel) + 1, nu.shape[1]), dtype=np.int64)
    acc = np.zeros(nu.shape[1], dtype=np.int64)
    for e, code in enumerate(event_channel):
        j = code_to_row[int(code)]
        acc = acc - table.sign[j] * nu[table.step[j]]   # a step consuming a held molecule supplies it
        per[e + 1] = acc
    return per[np.asarray(row_event, dtype=np.int64)]


def check_closure(law, table, n0, event_channel, row_event, counts, heat, work) -> CheckResult:
    return check_ledger(law, table, n0, event_channel, row_event, counts, heat, work)


def check_payers(world: World, row_event, supplied, work, planted: str | None = None) -> CheckResult:
    """W_t = Sum_h mu_h supplied_h(t) at every row."""
    mu = held_mu(world)
    s = np.asarray(supplied, dtype=np.int64)
    if planted == "payers_swapped" and len(mu) == 2:
        mu = mu[::-1]
    worst, problems = 0.0, []
    for k, e in enumerate(np.asarray(row_event, dtype=np.int64)):
        expected = math.fsum(float(m) * float(v) for m, v in zip(mu, s[k]))
        tol = 2 * (16 * U * max(int(e), 1) * (1 + float(np.max(np.abs(mu), initial=0.0)))
                   + 4 * U * math.fsum(abs(float(m) * float(v)) for m, v in zip(mu, s[k])))
        res = float(work[k]) - expected
        worst = max(worst, abs(res))
        if abs(res) > tol and len(problems) < 5:
            problems.append(dict(row=k, work=float(work[k]), expected=expected, residual=res, tol=tol))
    return CheckResult("work_by_payer", not problems,
                       dict(rows=len(row_event), max_abs_residual=worst, held=held_places(world),
                            mu=mu.tolist(), problems=problems, planted=planted))


def moiety_totals(world: World, counts, supplied, planted: str | None = None) -> np.ndarray:
    """[rows, Q]: Sum_s M_s n_s - Sum_held M_h supplied_h, per moiety."""
    names = world.moiety_names()
    Mf = np.array(world.moiety_matrix(), dtype=np.int64)            # [Q, D] over finite places
    H = held_places(world)
    Mh = np.array([[int(world.moieties[world.places[h].species].get(q, 0)) for h in H] for q in names],
                  dtype=np.int64).reshape(len(names), len(H))
    counts = np.asarray(counts, dtype=np.int64)
    s = np.asarray(supplied, dtype=np.int64)
    s = s.reshape(counts.shape[0], len(H)) if len(H) else np.zeros((counts.shape[0], 0), dtype=np.int64)
    if planted == "supply_ignored":
        s = np.zeros_like(s)
    elif planted == "waste_supply_ignored":
        s = s.copy()
        for k, h in enumerate(H):
            if h.startswith("W@"):
                s[:, k] = 0
    return counts @ Mf.T - s @ Mh.T


def check_moieties(world: World, counts, supplied, planted: str | None = None, *,
                   trace_supplied=None) -> CheckResult:
    tot = moiety_totals(world, counts, supplied, planted)
    drift = tot - tot[:1]
    bad_rows = np.nonzero(np.any(drift != 0, axis=1))[0]
    detail = dict(moieties=world.moiety_names(), rows=int(tot.shape[0]), initial=tot[0].tolist(),
                  rows_drifting=int(bad_rows.size), first_drift=None, planted=planted)
    if bad_rows.size:
        k = int(bad_rows[0])
        detail["first_drift"] = dict(row=k, totals=tot[k].tolist())
    ok = bad_rows.size == 0
    if trace_supplied is not None:
        a, b = np.asarray(trace_supplied, dtype=np.int64), np.asarray(supplied, dtype=np.int64)
        same = a.size == b.size and np.array_equal(a.reshape(-1), b.reshape(-1))
        detail["supply_matches_trace"] = bool(same)
        ok = ok and same
    return CheckResult("moieties_conserved", ok, detail)
