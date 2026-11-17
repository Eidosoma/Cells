"""OL5 references, rows OL1-3b, OL1-4c, OL1-4d, OL1-5 and OL1-6 on host runs of the registered
worlds: the oracle's replay, moiety conservation, the ledger's closure, the uniform factor's
time rescaling, and streams.

Planted controls: a biased channel choice; a stoichiometric update off by one; a heat sign
error; dropped reservoir work; a factor on forward channels only; a reused stream key.
"""

from __future__ import annotations

import numpy as np
import pytest

from validation.ool.references import catalysis, harness, ledger, streams
from validation.ool.references import registered as R
from validation.ool.references import ssa_oracle as SO
from validation.ool.references.laws import Law
from validation.ool.references.world import Conventions

PAIRS = [Conventions(condensed_measure="multinomial", last_molecule="kept"),
         Conventions(condensed_measure="multinomial_less_one", last_molecule="extinct")]
EVENTS = 600


def _run(world_id, conv, seed, events=EVENTS, bias=None):
    w = R.registered_world(world_id)
    law = Law(w, conv)
    rates = SO.FloatRates(law)
    rates.planted_bias = bias
    table = SO.ChannelTable.default(law)
    n0 = w.state_from(w.initial_state)
    run = SO.run_host_ssa(rates, table, n0, t_end=1e9, rng=np.random.default_rng(seed), max_events=events)
    return law, table, n0, run


@pytest.fixture(scope="module", params=PAIRS, ids=["physical", "gard_limit"])
def wa_run(request):
    law, table, n0, run = _run("ol1_wa", request.param, 11)
    book = ledger.rebook(law, table, n0, run["event_channel"])
    rows = list(range(0, EVENTS + 1, 100))
    return dict(law=law, table=table, n0=n0, run=run, book=book, rows=rows,
                Q=np.concatenate([[0.0], np.cumsum(book["q"])])[rows],
                W=np.concatenate([[0.0], np.cumsum(book["w"])])[rows])


def test_oracle_replays_the_run_and_catches_a_biased_choice(wa_run):
    law, table, n0, run = wa_run["law"], wa_run["table"], wa_run["n0"], wa_run["run"]
    rates = SO.FloatRates(law)
    res = SO.replay(rates, table, n0, run["event_time"], run["event_channel"], run["event_uniforms"])
    assert res.passed and res.detail["events"] == EVENTS and res.detail["max_rel_time_error"] == 0.0
    _, _, _, biased = _run("ol1_wa", law.conv, 11, bias=SO.PLANTED_REVERSE_WEIGHT)
    bad = SO.replay(rates, table, n0, biased["event_time"], biased["event_channel"], biased["event_uniforms"])
    assert not bad.passed and bad.detail["mismatches"][0]["event"] < 50


def test_ledger_closes_and_catches_planted_bookings(wa_run):
    d = wa_run
    states = d["book"]["states"][d["rows"]]
    ok = ledger.check_ledger(d["law"], d["table"], d["n0"], d["run"]["event_channel"], d["rows"], states, d["Q"], d["W"])
    assert ok.passed and ok.detail["max_abs_closure"] < 1e-11
    assert d["Q"][-1] > 10 and d["W"][-1] > 1  # supersaturated in A: heat and reservoir work accumulate
    for heat, work in ((-d["Q"], d["W"]), (d["Q"], 0 * d["W"])):
        bad = ledger.check_ledger(d["law"], d["table"], d["n0"], d["run"]["event_channel"], d["rows"], states, heat, work)
        assert not bad.passed and bad.detail["problems"][0]["row"] == 1


def test_moieties_and_a_planted_update_off_by_one(wa_run):
    d = wa_run
    rec = dict(event_channel=d["run"]["event_channel"], row_event=np.array(d["rows"]),
               counts=d["book"]["states"][d["rows"]])
    res = harness.moiety_check(d["law"], d["table"], d["n0"], rec, "test")
    assert res.passed
    counts = rec["counts"].copy()
    counts[2:, d["law"].world.index("C@membrane")] += 1  # one C too many from the third row on
    bad = harness.moiety_check(d["law"], d["table"], d["n0"], dict(rec, counts=counts), "test")
    assert not bad.passed and bad.detail["problems"][0]["row"] == 2


def test_a_uniform_factor_rescales_time_bitwise():
    conv = PAIRS[0]
    *_, base = _run("ol1_wa_closed", conv, 5, events=500)
    *_, scaled = _run("ol1_wa_closed_x2", conv, 5, events=500)
    res = catalysis.check_time_rescaling(base, scaled)
    assert res.passed and res.detail["bitwise"]
    # planted: the factor on forward channels only (reverse channels keep their rate)
    w = R.registered_world("ol1_wa_closed_x2")
    law = Law(w, conv)
    rates = SO.FloatRates(law)
    rates.k_minus = rates.k_minus / 2
    table = SO.ChannelTable.default(law)
    run = SO.run_host_ssa(rates, table, w.state_from(w.initial_state), t_end=1e9, rng=np.random.default_rng(5),
                          max_events=500)
    assert not catalysis.check_time_rescaling(base, run).passed


def test_streams_replay_bitwise_and_a_reused_key_is_caught():
    conv = PAIRS[0]
    *_, a = _run("ol1_wa", conv, 21, events=300)
    *_, b = _run("ol1_wa", conv, 21, events=300)
    *_, c = _run("ol1_wa", conv, 22, events=300)
    names = ("event_channel", "event_time", "event_uniforms")
    assert streams.check_replay(a, b, names).passed
    assert not streams.check_replay(a, c, names).passed
    assert streams.check_distinct_streams(a, c).passed
    assert not streams.check_distinct_streams(a, b).passed  # a reused key under two declared identities
