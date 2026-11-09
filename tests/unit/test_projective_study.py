"""The projective qualification driver builds protocol cases from the registered protocol.

Q1L honours its tolerance_override and its absolute caps are reported, not
judged; every other buildable case takes the protocol's projective parameters
unchanged. Q2 is the seven-cell world. Cases the driver cannot build are
refused. (The protocol parts run end to end in test_projective_protocol_runs.py.)
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


@pytest.mark.parametrize("case_id", ["F2-near-fold", "unknown"])
def test_cases_without_a_driver_world_are_refused(case_id):
    with pytest.raises(ValueError):
        study.protocol_case(PROTOCOL, case_id)


def test_q2_is_the_seven_cell_world():
    """U -+2 mV, U -+5 mV, H, D and H + 10 mV, each with its own held bath."""
    from cells.core.state import initialise
    from cells.models import surface_pump_projective as readouts
    from validation.tissue import surface_pump_v3_fixtures as heredity

    raw, _ = study.protocol_definition(PROTOCOL, "Q2-relax-world")
    spec = parse_spec(raw)
    assert len(spec.model.cells) == 7 and sum(x.reservoir for x in spec.model.extracellular) == 7
    p = readouts.host_layout(initialise(spec).layout)
    active = np.asarray(p.membrane_active, dtype=bool)
    u, h, d = (heredity.HEREDITY_STATES[k][0] for k in "UHD")
    expected = np.array([u - 0.002, u + 0.002, u - 0.005, u + 0.005, h, d, h + 0.010])
    np.testing.assert_allclose(
        np.asarray(p.initial_membrane_voltage_V)[active],
        expected[np.asarray(p.membrane_cell)[active]],
        rtol=0,
        atol=1e-12,
    )
