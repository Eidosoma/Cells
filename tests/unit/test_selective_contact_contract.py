"""SPEC-002 design/provenance checks, not production pair acceptance."""

import hashlib
import json

import numpy as np
import pytest

from scripts import check_selective_contact_contract as ref


def flux(gate=0.25, control=1.0, delta_v=-0.02, **changes):
    kwargs = dict(
        ca=[12.0, 140.0, 10.0],
        cb=[18.0, 130.0, 15.0],
        delta_v=delta_v,
        valence=ref.Z,
        permeability=[1e-8, 5e-9, 2e-9],
        area=1e-11,
        gate=gate,
        residual=[0.1, 0.1, 0.0],
        control=control,
        temperature=298.15,
    )
    kwargs.update(changes)
    return ref.edge_flux(**kwargs)


def test_independent_instantaneous_panel():
    result = ref.verify()
    assert result["status"] == "pass"
    assert (result["source_checks"], result["physical_checks"]) == (106, 603)
    assert result["checks_passed"] == 709


def test_retained_fixture_identity():
    assert hashlib.sha256(ref.FIXTURE.read_bytes()).hexdigest() == (
        "714a1cd51d11e4cee00db212ee1bc243ef7776d015d82e38a1c6c0568816fe86"
    )


@pytest.mark.parametrize("gate", [0.0, 0.25, 1.0])
@pytest.mark.parametrize("control", [0.0, 0.3, 1.0])
def test_contact_control_scales_flux_not_gate_dynamics(gate, control):
    np.testing.assert_allclose(flux(gate, control), control * flux(gate, 1), atol=1e-18)
    if control == 0:
        np.testing.assert_array_equal(flux(gate, control), np.zeros(3))
    assert ref.gate_slope(gate, -0.02) != 0


def test_same_ions_and_voltage_can_have_different_gate_state_and_response():
    assert not np.array_equal(flux(gate=0.1), flux(gate=0.9))
    assert ref.gate_slope(0.1, -0.02) != ref.gate_slope(0.9, -0.02)
    assert not np.array_equal(flux(gate=0.1), flux(gate=ref.gate_target(-0.02)))


@pytest.mark.parametrize("tau", [0.0, -1.0, np.inf, np.nan])
def test_no_implicit_instantaneous_gate_limit(tau):
    with pytest.raises(ValueError):
        ref.gate_slope(0.25, -0.02, tau)


@pytest.mark.parametrize("gate", [-0.1, 1.1, np.inf, np.nan])
def test_invalid_gate_state_refused_not_clipped(gate):
    with pytest.raises(ValueError):
        ref.gate_slope(gate, -0.02)
    with pytest.raises(ValueError):
        flux(gate=gate)


@pytest.mark.parametrize("control", [-0.1, 1.1, np.inf, np.nan])
def test_invalid_intervention_refused(control):
    with pytest.raises(ValueError):
        flux(control=control)


@pytest.mark.parametrize(
    "changes",
    [
        {"ca": [0, 140, 10]},
        {"cb": [18, -1, 15]},
        {"permeability": [1e-8, -1, 0]},
        {"residual": [-0.1, 0.1, 0]},
        {"residual": [0.1, 1.1, 0]},
        {"area": 0},
        {"temperature": 0},
        {"delta_v": 2.0},
        {"delta_v": np.nan},
    ],
)
def test_physical_design_domain(changes):
    with pytest.raises(ValueError):
        flux(**changes)


@pytest.mark.parametrize("corruption", ["flux", "stateful_source", "physical_mirna_charge"])
def test_source_correspondence_checker_detects_changed_meaning(tmp_path, corruption):
    data = json.loads(ref.FIXTURE.read_text())
    if corruption == "flux":
        data["probes"]["transport"][0]["flux"][0] *= -1
    elif corruption == "stateful_source":
        data["probes"]["gates"][0]["records"][0]["time_independent"] = False
    else:
        data["probes"]["mirna"]["charge_excluded"] = False
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        ref.verify(changed)
