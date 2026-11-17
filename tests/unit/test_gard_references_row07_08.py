"""GARD references, rows 7 and 8: conservation and the thermodynamic ledger.

Planted controls: a dropped molecule, and a heat sign error (plus a work sign error
and a mis-booked discard).
"""

from __future__ import annotations

import numpy as np
import pytest

from validation.gard.references import conservation as cons
from validation.gard.references import ledger
from validation.gard.references.kernels import PAIR_CONSISTENT, SINGLE_EVENT
from validation.gard.references.lineage_oracle import simulate_lineage
from validation.gard.references.standin import preprint_law


@pytest.fixture(scope="module")
def runs():
    out = {}
    for form in (PAIR_CONSISTENT, SINGLE_EVENT):
        law, founder = preprint_law(12, form)
        _, run, a = simulate_lineage(law, founder, n_fissions=15, seed=41)
        out[form] = (law, founder, a)
    return out


def _conserve(founder, a, **over):
    r = dict(a, **over)
    return cons.check_conservation(founder, r["assembly_count"], r["joined_total"], r["left_total"],
                                   r["discarded_total"], r["fission_split"], r["fission_followed"],
                                   r["event_channel"], r["events_per_growth"], r["row_event"])


def _ledger(law, founder, a, **over):
    r = dict(a, **over)
    return ledger.check_ledger(law, r["assembly_count"], r["exchange_heat_kT"], r["fission_work_kT"],
                               r["discarded_free_energy_kT"], r["log_weight"], r["ledger_residual_kT"],
                               r["fission_split"], r["fission_followed"], r["row_event"], r["event_channel"], founder)


@pytest.mark.parametrize("form", [PAIR_CONSISTENT, SINGLE_EVENT])
def test_conservation_holds_and_a_dropped_molecule_is_caught(runs, form):
    law, founder, a = runs[form]
    res = _conserve(founder, a)
    assert res.passed, res.detail
    assert res.detail["trace"]["totals_match_trace"] and res.detail["trace"]["growths_end_at_parents"]
    dropped = a["assembly_count"].copy()
    i = int(np.flatnonzero(dropped[7, :, 0])[0])
    dropped[7:, i, 0] -= 1  # one molecule vanishes from row 7 on, booked nowhere
    bad = _conserve(founder, a, assembly_count=dropped)
    assert not bad.passed and bad.detail["first_failing_row"] == 7


def test_a_misbooked_discard_is_caught(runs):
    law, founder, a = runs[PAIR_CONSISTENT]
    disc = a["discarded_total"].copy()
    j = int(np.flatnonzero(a["joined_total"][4, :, 0])[0])
    disc[4:, j, 0] += 1
    joined = a["joined_total"].copy()
    joined[4:, j, 0] += 1  # the identity still balances, but the fission booking does not
    bad = _conserve(founder, a, discarded_total=disc, joined_total=joined)
    assert not bad.passed


def test_pair_consistent_ledger_closes(runs):
    law, founder, a = runs[PAIR_CONSISTENT]
    res = _ledger(law, founder, a)
    assert res.passed, res.detail
    assert res.detail["convention_free_closes"] and res.detail["booking"]["ok"]
    assert res.detail["max_segment_error"] < res.detail["max_segment_tol"]


def test_single_event_residual_is_reported_not_closed(runs):
    law, founder, a = runs[SINGLE_EVENT]
    res = _ledger(law, founder, a)
    assert res.passed, res.detail
    assert not res.detail["convention_free_closes"]
    assert res.detail["unsourced_cycle_work"] > 1e-3


@pytest.mark.parametrize("form", [PAIR_CONSISTENT, SINGLE_EVENT])
def test_a_heat_sign_error_is_caught(runs, form):
    law, founder, a = runs[form]
    heat = -a["exchange_heat_kT"]
    resid = heat - ((a["log_weight"] - a["log_weight"][0]) + a["fission_work_kT"] - a["discarded_free_energy_kT"])
    bad = _ledger(law, founder, a, exchange_heat_kT=heat, ledger_residual_kT=resid)
    assert not bad.passed
    assert not bad.detail["booking"]["ok"]
    if form == PAIR_CONSISTENT:
        assert not bad.detail["convention_free_closes"]


def test_a_work_sign_error_is_caught(runs):
    law, founder, a = runs[PAIR_CONSISTENT]
    work = -a["fission_work_kT"]
    resid = a["exchange_heat_kT"] - ((a["log_weight"] - a["log_weight"][0]) + work - a["discarded_free_energy_kT"])
    bad = _ledger(law, founder, a, fission_work_kT=work, ledger_residual_kT=resid)
    assert not bad.passed and not bad.detail["work_sink_ok"]


def test_log_weight_constant_is_allowed_and_found(runs):
    law, founder, a = runs[PAIR_CONSISTENT]
    C = 17.25
    done = (np.arange(a["fission_work_kT"].shape[0]) // 2)[:, None]  # fissions completed by each row
    res = _ledger(law, founder, a, log_weight=a["log_weight"] + C,
                  fission_work_kT=a["fission_work_kT"] - C * done,
                  discarded_free_energy_kT=a["discarded_free_energy_kT"] - C * done)
    assert res.detail["log_weight_constant_ok"] and abs(res.detail["log_weight_constant"] - C) < 1e-9
    assert res.passed, res.detail
