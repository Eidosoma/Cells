"""OL5's fuel references (option (d) of the OL4 fuel note, tag ol4-fuel-note-2026-11-20): rows
OL4-1 to OL4-9 at module level, honest and planted.

Host-only; no engine import. About 20 s on one core (measured at landing; the docstring's number
is updated with it). Why it is worth that: it holds the committed design files to their generator
and shows that every registered check passes on the references' own values and fails on each
planted error, on small instances of the registered worlds. Each world that needs a large exact
solve is checked here at a smaller size; the full registered sizes run in the stand-in evidence.

Planted controls: a fuel step without its reservoir work, the drive of the wrong sign, the held
activities dropped, the core step's extent N - r + 1, the factor at each direction's own state,
catalysis on the forward channel only, the fuel's term dropped from F, the payers swapped, the
reservoirs' supply ignored, the waste's supply ignored, the flux counted without its reverse
events, three wrong closed forms, and a factor on a pool-only step accepted.
"""

from __future__ import annotations

import math
from fractions import Fraction as Fr

import numpy as np
import pytest

from validation.ool.references.detailed_balance import reference_table
from validation.ool.references.fuel import bistability as BI
from validation.ool.references.fuel import chem as C
from validation.ool.references.fuel import design as DS
from validation.ool.references.fuel import kernel as K
from validation.ool.references.fuel import ledger as LG
from validation.ool.references.fuel import registered as R
from validation.ool.references.fuel import standin as SI
from validation.ool.references.fuel import stationary as ST
from validation.ool.references.fuel import vesicle as V
from validation.ool.references.fuel.law import FuelLaw, parse_fuel_world
from validation.ool.references.common import RecordFormatError


# ---------------------------------------------------------------------------- registration

def test_committed_design_files_equal_the_generator(tmp_path):
    written = DS.write_all(tmp_path)
    for p in written:
        rel = p.relative_to(tmp_path)
        assert (R.DESIGN_DIR / rel).read_bytes() == p.read_bytes(), str(rel)
    on_disk = {str(p.relative_to(R.DESIGN_DIR)) for p in R.DESIGN_DIR.rglob("*.json")}
    assert on_disk == {str(p.relative_to(tmp_path)) for p in written}


def test_every_world_parses_and_the_refusal_is_refused():
    for wid, doc in R.world_documents().items():
        w = parse_fuel_world(doc)
        assert w.world_role is None, wid
    with pytest.raises(RecordFormatError, match="pool-only"):
        parse_fuel_world(R.refusal_documents()["refuse_factor_on_pool_step"])


# ---------------------------------------------------------------------------- OL4-1, OL4-2

@pytest.fixture(scope="module")
def kernel():
    w = R.registered_world("ol4_fd_kernel")
    states, cycles = DS.kernel_inputs("ol4_fd_kernel")
    on_cycles = {s for c in cycles for s in K.walk(w, c["start"], [(a, b) for a, b in c["path"]])}
    sub = np.array(sorted(on_cycles), dtype=np.int64)     # the cycles' states, for the planted tables (speed)
    law = FuelLaw(w)
    return w, law, states, cycles, sub


def test_the_kernel_identities_hold_exactly_and_on_the_float_table(kernel):
    w, law, states, cycles, _ = kernel
    assert K.exact_cycles(law, cycles).passed
    fuel = [c for c in cycles if c["kind"] == "fuel"]
    assert fuel and all(K.expected_exp(law, c) == 24 for c in fuel)     # mu_F - mu_W = ln 24
    t = ST.float_table(law, states)
    res = K.check_kernel(law, states, t["a_plus"], t["a_minus"], cycles)
    assert all(c.passed for c in res.values()), {k: c.detail for k, c in res.items() if not c.passed}


@pytest.mark.parametrize("planted, caught_by", [
    ("no_reservoir_work", ("identity", "cycle_drive")),
    ("work_sign", ("identity", "cycle_drive")),
    ("held_activity_dropped", ("identity", "forward_form", "cycle_drive")),
    ("extent_n_minus_r", ("forward_form",)),
    ("at_state_factor", ("identity", "cycle_drive")),
    ("forward_only_catalysis", ("identity", "cycle_drive")),
])
def test_each_planted_kernel_is_caught(kernel, planted, caught_by):
    w, law, states, cycles, sub = kernel
    ref = reference_table(law, sub)
    t = ST.float_table(FuelLaw(w, planted=planted), sub)
    res = K.check_kernel(law, sub, t["a_plus"], t["a_minus"], [c for c in cycles if _within(c, w, sub)], ref)
    for name in caught_by:
        assert not res[name].passed, (planted, name)


def _within(cyc, w, states) -> bool:
    listed = {tuple(int(v) for v in s) for s in states}
    return all(s in listed for s in K.walk(w, cyc["start"], [(a, b) for a, b in cyc["path"]]))


def test_the_drive_of_the_wrong_sign_is_off_by_twice_the_drive(kernel):
    w, law, states, cycles, _ = kernel
    w_, law_, _, _, sub = kernel
    t = ST.float_table(FuelLaw(w, planted="work_sign"), sub)
    cyc = [c for c in cycles if c["kind"] == "fuel"]
    res = K.check_cycles(law, sub, t["a_plus"], t["a_minus"], cyc)
    assert not res.passed and abs(res.detail["max_abs_residual"] - 2 * math.log(24)) < 1e-9


def test_held_block_and_zero_affinity_cycles():
    for wid, value in (("ol4_fd_heldB", Fr(12)), ("ol4_fd_d0", Fr(1)), ("ol4_fd_null", Fr(1))):
        w = R.registered_world(wid)
        _, cycles = DS.kernel_inputs(wid)
        law = FuelLaw(w)
        assert K.exact_cycles(law, cycles).passed
        assert {K.expected_exp(law, c) for c in cycles if c["kind"] == "block"} == {value}


# ---------------------------------------------------------------------------- OL4-3, OL4-4

@pytest.mark.parametrize("run_id", ["ol4_run_fuel_finite", "ol4_run_heldF", "ol4_run_heldB"])
def test_short_runs_close_and_conserve(run_id):
    spec = dict(DS.LEDGER_RUNS[run_id], max_events=300, row_every=50)
    h = SI.host_run(spec["world"], spec)
    w = h["world"]
    law = FuelLaw(w)
    n0 = w.state_from(w.initial_state)
    c = LG.check_closure(law, h["table"], n0, h["run"]["event_channel"], h["rows"], h["counts"], h["heat"], h["work"])
    assert c.passed, c.detail
    assert LG.check_payers(w, h["rows"], h["supplied"], h["work"]).passed
    tr = LG.supplied_from_trace(w, h["table"], h["run"]["event_channel"], h["rows"])
    assert LG.check_moieties(w, h["counts"], h["supplied"], trace_supplied=tr).passed
    # reader's plants, each on the world where it bites
    if run_id in ("ol4_run_heldF", "ol4_run_heldB"):
        assert not LG.check_moieties(w, h["counts"], h["supplied"], "supply_ignored").passed


def test_the_fuel_term_dropped_from_F_breaks_closure():
    spec = dict(DS.LEDGER_RUNS["ol4_run_fuel_finite"], max_events=300, row_every=50)
    h = SI.host_run(spec["world"], spec, planted="fuel_term_dropped")
    w = h["world"]
    c = LG.check_closure(FuelLaw(w), h["table"], w.state_from(w.initial_state), h["run"]["event_channel"], h["rows"],
                         h["counts"], h["heat"], h["work"])
    assert not c.passed and c.detail["max_abs_closure"] > 1.0


def test_the_waste_supply_ignored_and_payers_swapped_are_caught():
    spec = dict(DS.LEDGER_RUNS["ol4_run_fuel_held"], max_events=300, row_every=50)
    h = SI.host_run(spec["world"], spec)
    w = h["world"]
    assert LG.check_moieties(w, h["counts"], h["supplied"]).passed
    assert LG.check_moieties(w, h["counts"], h["supplied"], "supply_ignored").passed    # both held: cannot bite
    assert not LG.check_moieties(w, h["counts"], h["supplied"], "waste_supply_ignored").passed
    assert LG.check_payers(w, h["rows"], h["supplied"], h["work"]).passed
    assert not LG.check_payers(w, h["rows"], h["supplied"], h["work"], "payers_swapped").passed


# ---------------------------------------------------------------------------- OL4-5 to OL4-7, small worlds

def _small(wid: str, M: int):
    """A registered closed world's chemistry at a smaller block total (speed)."""
    doc = R.world_documents()[wid]
    doc["initial_state"] = {"L1@membrane": 1, "L2@membrane": 1, "B@pool": M - 2}
    w = parse_fuel_world(doc)
    states = ST.reachable_states(w, w.initial_state)
    assert len(states) == len(ST.closed_states(w, {"block": M}))     # with held fuel, every state is reachable
    return w, states


def test_true_equilibrium_holds_with_and_without_catalysis_and_the_factor_at_own_state_moves_it():
    for wid in ("ol4_fd_zero", "ol4_fd_zero_beta0"):
        w, states = _small(wid, 6)
        law = FuelLaw(w)
        t = ST.float_table(law, states)
        res = ST.check_equilibrium(law, states, t["a_plus"], t["a_minus"])
        assert res["stationary_law"].passed and res["kolmogorov"].passed, res["stationary_law"].detail
        assert res["modality"].detail["kind"] == "one_central"
    w, states = _small("ol4_fd_zero", 6)
    t = ST.float_table(FuelLaw(w, planted="at_state_factor"), states)
    res = ST.check_equilibrium(FuelLaw(w), states, t["a_plus"], t["a_minus"])
    assert not res["stationary_law"].passed and res["stationary_law"].detail["total_variation"] > 1e-4


def test_the_driven_law_flux_heat_and_switching_on_a_small_world():
    w, states = _small("ol4_fd_ness", 6)
    law = FuelLaw(w)
    ref = ST.reference_solution(law, states)
    assert ref["connected"] and ref["residual"] < 1e-12
    A = math.log(float(w.places["F@pool"].held_mM.exact / w.places["W@pool"].held_mM.exact))
    assert abs(ref["heat_rate"] - ref["J"] * A) <= 1e-9 * abs(ref["J"] * A)
    assert ref["J_forward_only"] > 1.5 * ref["J"] > 0          # reverse fuel events are common here
    start = states[int(np.argmax(np.where(ST.regions(w, states)[0], ref["pi"], -1.0)))]
    res = ST.check_driven(law, states, ref["table"]["a_plus"], ref["table"]["a_minus"], ref, A, start=start)
    assert all(c.passed for c in res.values()), {k: c.detail for k, c in res.items() if not c.passed}
    t = ST.float_table(FuelLaw(w, planted="no_reservoir_work"), states)
    bad = ST.check_driven(law, states, t["a_plus"], t["a_minus"], ref, A, start=start)
    assert not bad["stationary_law"].passed and not bad["flux"].passed


def test_the_variance_rate_matches_the_tilted_generator():
    """D from the Poisson equation against theta''(0) of the tilted generator (dense, tiny world)."""
    w, states = _small("ol4_fd_ness", 3)
    law = FuelLaw(w)
    t = ST.float_table(law, states)
    e = ST.edges(w, states, t["a_plus"], t["a_minus"])
    Q = ST.generator(len(states), e)
    pi = ST.stationary(Q)
    r = ST.fuel_step_index(w)
    ps = ST.poisson(Q, pi, e, r)
    c = np.where(e[3] == r, e[4], 0)

    out_rate = np.bincount(e[0], weights=e[2], minlength=len(states))

    def theta(lam):
        """The largest eigenvalue of the tilted generator Q_nm e^(lam c_nm) (diagonal unchanged)."""
        M = np.diag(-out_rate)
        for s_, d_, v_, cc in zip(e[0], e[1], e[2], c):
            M[s_, d_] += v_ * math.exp(lam * cc)
        return max(np.linalg.eigvals(M).real)

    h = 1e-3
    d2 = (theta(h) - 2 * theta(0.0) + theta(-h)) / h ** 2
    d1 = (theta(h) - theta(-h)) / (2 * h)
    assert abs(d1 - ps["J"]) < 1e-6 * max(1.0, abs(ps["J"]))
    assert abs(d2 - ps["D"]) < 1e-4 * ps["D"]


def test_the_switching_time_solver_against_exact_rationals():
    from validation.ool.references.closed_world import exact_rates_dict

    w, states = _small("ol4_fd_ness", 3)
    law = FuelLaw(w)
    t = ST.float_table(law, states)
    Q = ST.generator(len(states), ST.edges(w, states, t["a_plus"], t["a_minus"]))
    R1, R2 = ST.regions(w, states)
    t1, _ = ST.first_passage(Q, R2)
    # exact: Q_kk tau = -1 off R2, in rationals
    st = [tuple(int(v) for v in s) for s in states]
    rates = exact_rates_dict(law, st)
    keep = [s for s, tgt in zip(st, R2) if not tgt]
    idx = {s: k for k, s in enumerate(keep)}
    n = len(keep)
    A = [[Fr(0)] * (n + 1) for _ in range(n)]
    for s in keep:
        tot = sum(rates[s].values(), Fr(0))
        A[idx[s]][idx[s]] -= tot
        for y, rr in rates[s].items():
            if y in idx:
                A[idx[s]][idx[y]] += rr
        A[idx[s]][n] = Fr(-1)
    for col in range(n):
        p = next(rr for rr in range(col, n) if A[rr][col] != 0)
        A[col], A[p] = A[p], A[col]
        pv = A[col][col]
        A[col] = [v / pv for v in A[col]]
        for rr in range(n):
            if rr != col and A[rr][col] != 0:
                f = A[rr][col]
                A[rr] = [a - f * b for a, b in zip(A[rr], A[col])]
    for s, k in idx.items():
        assert abs(float(A[k][n]) - t1[st.index(s)]) <= 1e-9 * float(A[k][n])


# ---------------------------------------------------------------------------- OL4-8

def test_the_closed_form_its_nulls_and_the_notes_numbers():
    S = BI.sample(400)
    assert BI.check_sample(S)["disagreements"] == 0
    for planted in BI.PLANTED:
        assert BI.check_sample(S, planted)["disagreements"] > 0, planted
    assert BI.check_A_star(S)["disagreements"] == 0
    assert all(v["failures"] == 0 and v["sets"] > 100 for v in BI.nulls(S).values())
    rep = BI.reproductions()
    assert [round(f, 3) for f in rep["c4"]["stable"]] == [0.082, 0.918] and abs(rep["c4"]["gamma"][0] - 1.06) < 0.006
    assert round(rep["c5"]["A_star_beta2_rho4"], 1) == 6.6 and round(rep["c5"]["A_star_beta64_rho4"], 1) == 3.4
    assert rep["zero_affinity_rho_quarter"] == "655680" and rep["feed_regime_rho_ninth"] == "8"
    assert rep["constructed_c4b"]["gamma_even"] == "0" and rep["constructed_c4b"]["bistable"]
    pred = DS.zero_affinity_predictions()
    assert pred["ol4_fd_d0"]["bistable"] and pred["ol4_fd_d0"]["rho_exact"] == "1/9"
    assert not pred["ol4_fd_null"]["bistable"] and pred["ol4_fd_null"]["gamma_even"] > 0


# ---------------------------------------------------------------------------- V1

def test_the_vesicle_kernel_and_its_plants():
    w = DS.v_world("ol4_fv_kernel")
    states, cycles = DS.v_kernel_inputs("ol4_fv_kernel")
    law = V.FuelLaw2(w)
    tab = V.table(law, states)
    assert V.check_identity(law, states, tab).passed
    assert V.check_forward(law, states, tab).passed
    cyc = V.check_cycles(law, states, tab, cycles)
    assert cyc.passed and abs(cyc.detail["sums_by_kind"]["fuel"]["min"] - (2.5 + math.log(3))) < 1e-9
    names = {c.id: c for c in w.steps}
    sub = set()
    for c in cycles:
        s = tuple(tuple(x) for x in c["start"])
        sub.add(s)
        for sid, g in c["path"]:
            s = V.after(law, s, names[sid], g)
            sub.add(s)
    sub = sorted(sub)
    for planted, check in (("no_reservoir_work", V.check_identity), ("work_sign", V.check_identity),
                           ("extent_n_minus_r", V.check_forward), ("factor_dropped", V.check_forward),
                           ("at_state_factor", V.check_identity)):
        assert not check(law, sub, V.table(V.FuelLaw2(w, planted=planted), sub)).passed, planted


def test_the_closed_vesicle_relaxes_to_exp_minus_F():
    w = DS.v_world("ol4_fv_closed")
    law = V.FuelLaw2(w)
    states = V.closed_states(law, 5)
    tab = V.table(law, states)
    res = V.check_closed(law, states, tab)["stationary_law"]
    assert res.passed and res.detail["tense_states"] > 0 and res.detail["connected"]
    bad = V.check_closed(law, states, V.table(V.FuelLaw2(w, planted="at_state_factor"), states))["stationary_law"]
    assert not bad.passed
