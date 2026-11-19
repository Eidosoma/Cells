"""FR-8 stage 0's M1, @3's explicit bound term by term (validation/long_duration/m1_bound_terms.py;
validation/long_duration/REGISTRATION_20261118.md §3 and §8). Each claim with its plant, on the
registered seven-cell sheet S7b:

- the terms reproduce the engine's explicit-rate bound bitwise, and the binding term perturbed by
  the factor (1 + 2^-40) does not (C1.1);
- the step checks admit 0.999 dt_def and refuse 1.001 dt_def with the binding check's own message
  (C1.2);
- the junction-gate term equals its formula, 1.3 exp(77 x 0.015) + 20 = 24.13 /s on E07's gated
  junctions, which admits at most 5.18 ms, and a 16 mV threshold would give another value.
"""

import math

import pytest

from cells.definitions import surface_pump_v3_spec as v3spec
from cells.definitions.specs import parse_spec
from cells.models import surface_pump as first
from cells.models import surface_pump_v3 as v3
from validation.long_duration import m1_bound_terms as m1
from validation.long_duration import worlds


@pytest.fixture(scope="module")
def sheet():
    spec = parse_spec(worlds.s7b())
    return spec, v3spec.projection(spec)


def test_terms_reproduce_the_bound_and_a_perturbed_binding_term_does_not(sheet):
    _, base = sheet
    terms = m1.explicit_terms(base)
    engine = first.explicit_rate_bound(base)
    assert max(terms.values()) == engine
    binding = max(terms, key=terms.get)
    planted = dict(terms, **{binding: terms[binding] * (1 + 2.0**-40)})
    assert max(planted.values()) != engine


def test_step_checks_admit_below_and_refuse_above_the_binding_term(sheet):
    spec, _ = sheet
    result = m1.measure(worlds.s7b())
    c12 = result["criteria"]["C1_2"]
    assert c12["passed"] and c12["admits_0p999"]
    assert c12["refusal_at_1p001"] == m1.MESSAGES[c12["binding"]]
    checks = v3.bind_step_checks(spec)
    assert m1.step_refusal(checks, 0.999 * c12["dt_def_s"]) is None
    assert m1.step_refusal(checks, 1.001 * c12["dt_def_s"]) is not None


def test_the_junction_gate_term_equals_its_formula(sheet):
    spec, _ = sheet
    rate = first.junction_gate_rate_bound(spec)
    formula = 1.3 * math.exp(77 * 0.015) + 20
    assert rate == pytest.approx(formula, rel=1e-15)
    assert rate == pytest.approx(worlds.registration()["m1"]["e07_gate_rate_per_s_by_formula"])
    assert first.GATE_STEP_BOUND / rate == pytest.approx(5.181082900473453e-3, rel=1e-12)
    assert abs(rate - (1.3 * math.exp(77 * 0.016) + 20)) > 0.1  # The plant: another threshold.
