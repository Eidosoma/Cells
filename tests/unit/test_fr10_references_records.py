"""FR-10's R-records (A.4, A.5, §2.2 and §2.3, item B4): dose, dG_b, charge and K.

Planted controls: every dG_b booking error of ``controls`` against the 1e-12 criterion, a step
missing its counter-ion, K without its accumulator, a dose in mM on a bath that is not 1 pL, and
constants that are not the exact SI values.
"""

from __future__ import annotations

import copy
from decimal import localcontext
from fractions import Fraction

import numpy as np
import pytest

from validation.fr10.references import controls, faces, ion, records
from validation.fr10.references.common import (
    DIGITS,
    Constants,
    constants_from_block,
    dec,
    exact,
    load_inputs,
)

INPUTS = load_inputs()
CONST = Constants()
WORLDS = INPUTS["R_records"]["worlds"]


def test_doses_are_exact_and_neutral_steps_carry_no_charge():
    w1 = records.event_records(WORLDS["W1"], INPUTS["constants"])
    d = exact(0.010000000000000002) - exact(0.001)
    assert Fraction(w1[0]["dose_exact"]["S"]) == d
    assert Fraction(w1[1]["dose_exact"]["S"]) == -d
    assert all(w1[k]["dose_fmol"][s] == 0.0 for k in (0, 1) for s in ("Na", "K", "Cl"))
    w2 = records.event_records(WORLDS["W2"], INPUTS["constants"])[0]
    assert w2["dose_fmol"] == {"Cl": 0.0, "K": 45.0, "Na": -45.0, "S": 0.0}
    for w in ("W1", "W2", "W3"):
        for ev in records.event_records(WORLDS[w], INPUTS["constants"]):
            assert ev["charge_C"] == 0.0 and ev["neutral"]
    # planted: a substitution that adds KCl but removes no NaCl carries a net charge
    bad = copy.deepcopy(WORLDS["W2"])
    bad["baths"]["bath"]["events"][0]["concentration_mM"]["Na"] = 145.0
    ev = records.event_records(bad, INPUTS["constants"])[0]
    assert not ev["neutral"]
    assert Fraction(ev["charge_exact"]) == CONST.faraday * 45 / 10 ** 15


def test_dG_b_against_the_endpoint_form_and_float64():
    for w in ("W1", "W2", "W3"):
        evs = records.event_records(WORLDS[w], INPUTS["constants"])
        for ev in evs:
            assert ev["floor"]["dG_b_pJ"] / abs(ev["dG_b_pJ"]) < 1e-15
        assert abs(evs[-1]["cumulative_dG_b_pJ"] - evs[-1]["endpoint_dG_b_pJ"]) <= \
            1e-15 * max(1.0, abs(evs[-1]["endpoint_dG_b_pJ"]))
    w1 = records.event_records(WORLDS["W1"], INPUTS["constants"])
    assert w1[0]["dG_b_pJ"] == -w1[1]["dG_b_pJ"]
    assert w1[1]["cumulative_dG_b_pJ"] == 0.0
    # W1's first event by hand, in decimals: 1e-3 RT [dn (ln c - 1) + V c' ln(c'/c)]
    c, c2 = exact(0.001), exact(0.010000000000000002)
    with localcontext() as ctx:
        ctx.prec = DIGITS
        by_hand = dec(CONST.RT(310)) / 1000 * (dec(c2 - c) * (dec(c).ln() - 1) +
                                               dec(c2) * (dec(c2) / dec(c)).ln())
    assert abs(float(by_hand) - w1[0]["dG_b_pJ"]) <= 1e-16 * abs(w1[0]["dG_b_pJ"])


def test_every_dG_b_control_fails_where_it_has_power():
    zero_power = {("W2", "dG_no_minus_one"), ("W2", "dG_one_molar")}
    for w in ("W1", "W2", "W3"):
        for row in controls.records_controls(WORLDS[w], CONST):
            for key, rel in row["deviation"].items():
                if not key.startswith("dG_") or rel is None:
                    continue
                if (w, key) in zero_power:
                    assert rel < 1e-15, (w, key, rel)
                else:
                    assert rel > 1e3 * 1e-12, (w, key, rel)


def test_K_forms_agree_and_K_without_B_is_caught_in_W1_only():
    fw = faces.solve(faces.parse(INPUTS["R_faces"]))
    K1 = records.reconciliation_K(WORLDS["W1"], fw["times_s"], {"S": fw["supply_fmol"]},
                                  INPUTS["constants"])
    assert np.abs(K1["K_pJ"] - K1["K_float64_pJ"]).max() <= 1e-15
    t = fw["times_s"]
    i1, i2 = K1["event_rows"]
    assert np.all(K1["K_pJ"][: i1 + 1] == 0.0)
    assert np.all(K1["K_pJ"][i2:] == K1["K_pJ"][i2])            # back at mu0 after 2 s
    with localcontext() as ctx:
        ctx.prec = DIGITS
        expect = dec(CONST.RT(310)) * dec(10).ln() / 1000 * \
            (dec(fw["supply_fmol"][i2]) - dec(fw["supply_fmol"][i1]))
    assert abs(K1["K_pJ"][-1] - float(expect)) <= 1e-17
    assert t[i1] == 1.0 and t[i2] == 2.0
    c1 = controls.K_controls(K1, {"S": fw["supply_fmol"]}, WORLDS["W1"], CONST)
    assert c1["K_without_B"] > 0.1 and c1["K_previous_epoch"] > 0.1
    iw = ion.solve(ion.parse(INPUTS["R_ion"], INPUTS["constants"]))
    K2 = records.reconciliation_K(WORLDS["W2"], iw["times_s"], iw["supply_fmol"],
                                  INPUTS["constants"])
    c2 = controls.K_controls(K2, iw["supply_fmol"], WORLDS["W2"], CONST)
    assert c2["K_without_B"] < 1e-17                    # registered zero power in W2
    assert c2["K_dropped"] > 3e-3


def test_K_refuses_a_missing_event_time_and_unknown_species():
    times = [0.0, 0.5, 0.999, 1.5, 2.5]
    with pytest.raises(ValueError, match="not among the record times"):
        records.reconciliation_K(WORLDS["W1"], times, {"S": np.zeros(5)})
    with pytest.raises(ValueError, match="does not declare"):
        records.reconciliation_K(WORLDS["W3"], [0.0, 0.002], {"X": np.zeros(2)})


def test_a_bath_of_another_volume_gives_the_dose_in_mM_power():
    big = copy.deepcopy(WORLDS["W3"])
    big["baths"]["bath"]["volume_pL"] = 25.0
    ev = records.event_records(big, INPUTS["constants"])[0]
    dc = exact(0.0015) - exact(0.001)
    assert Fraction(ev["dose_exact"]["S"]) == 25 * dc
    dev = controls.records_controls(big, CONST)[0]["deviation"]["dose_in_mM"]
    assert dev > 1e-3
    assert controls.records_controls(WORLDS["W3"], CONST)[0]["deviation"]["dose_in_mM"] == 0.0


def test_constants_must_be_the_exact_SI_values():
    assert constants_from_block(INPUTS["constants"]) == Constants()
    bad = dict(INPUTS["constants"], boltzmann_J_per_K=1.3806e-23)
    with pytest.raises(ValueError, match="not the exact SI value"):
        constants_from_block(bad)
    with pytest.raises(ValueError, match="lacks"):
        constants_from_block({"avogadro_per_mol": 6.02214076e23})
