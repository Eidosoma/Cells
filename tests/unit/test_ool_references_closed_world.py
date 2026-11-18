"""OL5 references, rows OL1-2 and OL1-3a: the closed world relaxes to exp(-F)/Z, with and
without its catalysts.

Planted controls: the factor at each direction's own state, a one-sided off rate, catalysis in
the forward direction only, a dropped c0, a sign error, the other measure, and a rate that leads
outside the listed states.
"""

from __future__ import annotations

import numpy as np
import pytest

from validation.ool.references import closed_world as CW
from validation.ool.references import detailed_balance as DB
from validation.ool.references import probes as P
from validation.ool.references import registered as R
from validation.ool.references.laws import Law
from validation.ool.references.world import Conventions

PHYSICAL = Conventions(condensed_measure="multinomial", last_molecule="kept")
GARD_LIMIT = Conventions(condensed_measure="multinomial_less_one", last_molecule="extinct")
PP = dict(step="r3", place="D@membrane", lam=1)
# Registered magnitudes (README, row OL1-2): each planted law's total variation from exp(-F)/Z.
PLANTED_TV_AT_LEAST = {"at_state_factor": 0.08, "forward_only_catalysis": 0.29, "one_sided": 0.0075,
                       "dropped_c0": 0.99, "wrong_sign": 0.99}


@pytest.fixture(scope="module")
def closed():
    w = R.registered_world("ol1_wa_closed")
    states = P.closed_world_states(w, w.initial_state)
    return w, states


def test_the_closed_world_is_the_registered_one(closed):
    w, states = closed
    assert len(states) == 387
    assert min(sum(v for v, m in zip(s, w.membrane_mask()) if m) for s in states) >= 5
    moieties = np.asarray(w.moiety_matrix()) @ states.T
    assert np.all(moieties == moieties[:, :1])


@pytest.mark.parametrize("conv", [PHYSICAL, GARD_LIMIT], ids=["physical", "gard_limit"])
def test_exact_edge_identity_and_the_stationary_law(closed, conv):
    w, states = closed
    law = Law(w, conv)
    ex = CW.exact_edge_identity(law, states)
    assert ex.passed and ex.detail["edges"] == 1312
    t = DB.reference_table(law, states)
    res = CW.check_closed_world(law, states, t["a_plus"], t["a_minus"])
    assert res["stationary_law"].passed and res["stationary_law"].detail["total_variation"] < 1e-13
    assert res["kolmogorov"].passed and res["kolmogorov"].detail["cycles_checked"] > 1500


@pytest.mark.parametrize("conv", [PHYSICAL, GARD_LIMIT], ids=["physical", "gard_limit"])
def test_planted_laws_depart_from_exp_minus_F(closed, conv):
    w, states = closed
    tvs = CW.planted_tvs(w, conv, states, {k: (k, PP) for k in PLANTED_TV_AT_LEAST})
    for form, bound in PLANTED_TV_AT_LEAST.items():
        assert tvs[form] > bound > 1e6 * CW.TV_ATOL, (form, tvs[form])


def test_the_other_measure_departs(closed):
    w, states = closed
    t = DB.reference_table(Law(w, GARD_LIMIT), states)
    res = CW.check_closed_world(Law(w, PHYSICAL), states, t["a_plus"], t["a_minus"])
    assert not res["stationary_law"].passed and res["stationary_law"].detail["total_variation"] > 0.03
    assert res["kolmogorov"].passed  # a consistent law under another F: only the stationary law sees it


def test_catalysts_do_not_move_the_stationary_law(closed):
    w, states = closed
    wu = R.registered_world("ol1_wa_closed_uncatalysed")
    for conv in (PHYSICAL, GARD_LIMIT):
        tc = DB.reference_table(Law(w, conv), states)
        tu = DB.reference_table(Law(wu, conv), states)
        pc = CW.stationary_float(CW.generator_from_table(w, states, tc["a_plus"], tc["a_minus"]))
        pu = CW.stationary_float(CW.generator_from_table(wu, states, tu["a_plus"], tu["a_minus"]))
        assert CW.total_variation(pc, pu) < 1e-13
        assert not np.allclose(tc["a_plus"], tu["a_plus"])  # the catalysts do change the rates


def test_a_rate_leading_outside_the_listed_states_fails(closed):
    w, states = closed
    t = DB.reference_table(Law(w, PHYSICAL), states)
    res = CW.check_closed_world(Law(w, PHYSICAL), states[:-1], t["a_plus"][:-1], t["a_minus"][:-1])
    assert set(res) == {"generator"} and not res["generator"].passed
