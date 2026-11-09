"""The projective qualification driver builds protocol cases from the registered protocol.

Q1L honours its tolerance_override and its absolute caps are reported, not
judged; every other buildable case takes the protocol's projective parameters
unchanged and has judged caps. Cases the driver cannot build are refused.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from cells.core.specs import parse_spec
from validation.tissue import projective_study as study

PROTOCOL = json.loads(
    (Path(study.__file__).parent / "protocols" / "projective_c_qualification_v1.json").read_text()
)
PARAMETERS = PROTOCOL["projective_parameters"]


def test_q1l_takes_its_tolerance_override_and_nothing_else_changes():
    loose, case = study.protocol_definition(PROTOCOL, "Q1L-relax-pair-loose")
    strict, _ = study.protocol_definition(PROTOCOL, "Q1-relax-pair")
    assert loose["execution"]["projective"]["tolerance"] == case["tolerance_override"]
    assert strict["execution"]["projective"]["tolerance"] == PARAMETERS["tolerance"]
    assert case["tolerance_override"] != PARAMETERS["tolerance"]
    a, b = dict(loose["execution"]["projective"]), dict(strict["execution"]["projective"])
    a.pop("tolerance"), b.pop("tolerance")
    assert a == b  # Same burst, slope, jump rule, safety and windows.
    assert {k: v for k, v in loose.items() if k != "execution"} == {
        k: v for k, v in strict.items() if k != "execution"
    }
    spec = parse_spec(loose)
    assert spec.projective.tolerance.concentration_mM == 0.01
    assert spec.projective.tolerance.membrane_voltage_V == 1e-4
    assert spec.projective.tolerance.gate == 1e-3


@pytest.mark.parametrize("case_id", sorted(study.PROTOCOL_WORLDS))
def test_buildable_cases_take_the_protocol_parameters(case_id):
    raw, case = study.protocol_definition(PROTOCOL, case_id)
    block, jump = raw["execution"]["projective"], PARAMETERS["jump"]
    assert block["burst_steps"] == PARAMETERS["burst_steps"] == 3000
    assert block["slope_steps"] == PARAMETERS["slope_steps"]
    assert block["jump"] == jump
    assert block["safety"] == PARAMETERS["safety"]
    assert block["row_checks"] == "host"
    assert [[w["start_time"], w["end_time"]] for w in block["windows"]] == case["windows"]
    assert raw["experiment"]["end_time"] == case["horizon_s"]
    times = raw["experiment"]["observation_times"]
    assert times[0] == 0.0 and times[-1] == case["horizon_s"]
    assert np.allclose(np.diff(times), case["observation_every_s"])
    expected = case.get("tolerance_override", PARAMETERS["tolerance"])
    assert block["tolerance"] == expected
    assert raw["model"]["id"] == case["model"]


def test_absolute_caps_are_judged_except_for_q1l():
    assert study.REPORTED_CAPS == {"Q1L-relax-pair-loose"}
    assert "except Q1L" in PROTOCOL["criteria"]["absolute_caps"]
    theirs = dict(
        membrane_voltage_V=np.array([-0.08, -0.03]), concentration_mM=np.array([10.0, 140.0])
    )
    mine = dict(
        membrane_voltage_V=theirs["membrane_voltage_V"] + [0.0, 3e-5],
        concentration_mM=theirs["concentration_mM"] * (1 + np.array([1e-4, 0.0])),
    )
    caps = study.absolute_caps(mine, theirs, judged=False)
    assert caps["judged"] is False and not caps["within"]
    assert np.isclose(caps["voltage_V"], 3e-5) and np.isclose(caps["relative_concentration"], 1e-4)
    assert study.absolute_caps(theirs, theirs, judged=True)["within"]


@pytest.mark.parametrize("case_id", ["Q2-relax-world", "F2-near-fold", "unknown"])
def test_cases_without_a_driver_world_are_refused(case_id):
    with pytest.raises(ValueError):
        study.protocol_case(PROTOCOL, case_id)
