"""SPEC-003 frozen full-RHS, state-role and negative-control tests; no integration."""

import ast
import copy
import hashlib
import json

import numpy as np
import pytest

from scripts import check_source_pair_contract as check
from tests import reference_source_pair as ref
from tests.reference_emt import reference_rhs


@pytest.fixture
def panel():
    return ref.load_panel()


def get_case(panel, name):
    return copy.deepcopy(next(case for case in panel["cases"] if case["id"] == name))


def evaluated(panel, name, time=0):
    case = get_case(panel, name)
    return ref.evaluate(*ref.initial_state(panel, case), panel, case, time)


def test_frozen_input_and_native_output_identity():
    assert hashlib.sha256(ref.PANEL.read_bytes()).hexdigest() == (
        "b67efad941db1b4c407aeddcac3836acf4a31653f3a1baa513ece6f5ce2e915d"
    )
    assert hashlib.sha256(check.FIXTURE.read_bytes()).hexdigest() == (
        "c71d0ede05060c84e466a7cc9e3a5f4ea7aa4eb2d3c1b77518c415f91a2b5f6b"
    )


def test_complete_instantaneous_native_panel():
    result = check.verify()
    assert result["status"] == "pass"
    assert (result["cases"], result["native_control_probes"]) == (14, 17)
    assert result["checks_passed"] == 3192
    assert result["trajectory_qualification"] == "not run"
    assert result["production_implementation"] == "not implemented"


def test_reference_does_not_import_production_or_upstream():
    for path in (ref.ROOT / "tests/reference_source_pair.py", ref.ROOT / "tests/reference_emt.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                imports = [node.module or ""]
            else:
                continue
            assert all(
                name.split(".")[0] not in {"cells", "sim", "GRN_miRNA", "GJ_lib"}
                for name in imports
            )


@pytest.mark.parametrize("name", [f"S{i:02d}" for i in range(14)])
def test_complete_state_pure_rhs_and_named_native_row_contract(panel, name):
    case = get_case(panel, name)
    primary, context = ref.initial_state(panel, case)
    before_primary, before_context = primary.copy(), context.copy()
    result = ref.evaluate(primary, context, panel, case)
    assert primary.shape == (6, 2)
    assert context.shape == (3, 2)
    assert "gate_rate" not in result
    np.testing.assert_array_equal(primary, before_primary)
    np.testing.assert_array_equal(context, before_context)
    np.testing.assert_array_equal(result["packet"][ref.PRIMARY_INDEX], primary)
    np.testing.assert_array_equal(result["packet"][ref.CONTEXT_INDEX], context)
    np.testing.assert_array_equal(result["packet"][8], primary[3])
    np.testing.assert_array_equal(result["contact_rate"].sum(axis=1), np.zeros(6))
    np.testing.assert_allclose(
        result["local_rate"][3:], reference_rhs(0, primary[3:], context[1]), atol=0, rtol=0
    )


def test_prepared_states_preserve_full_ionic_and_regulatory_context(panel):
    case = get_case(panel, "S01")
    primary, context = ref.initial_state(panel, case)
    for cell, prepared in enumerate(panel["preparation"]["cells"]):
        for row, name in enumerate(ref.PRIMARY):
            assert primary[row, cell] == prepared["raw_packet"][name]
        assert context[0, cell] == prepared["raw_packet"]["P"]
        assert context[1, cell] == prepared["raw_packet"]["snail"]
        assert context[2, cell] == 0  # explicit inert ST adapter, not a missing primary field
        assert prepared["last_sample_time"] < 10000 < prepared["accepted_time"]
    assert (
        panel["preparation"]["cells"][0]["accepted_time"]
        != (panel["preparation"]["cells"][1]["accepted_time"])
    )
    assert not np.array_equal(primary[:3, 0], primary[:3, 1])


def test_missing_prepared_ion_is_not_silently_replaced_by_default(panel):
    del panel["preparation"]["cells"][0]["raw_packet"]["K"]
    with pytest.raises(ValueError, match="Incomplete prepared"):
        ref.initial_state(panel, get_case(panel, "S01"))


def test_algebraic_binding_not_an_extra_state_or_exact_mirna_inventory(panel):
    result = evaluated(panel, "S01")
    packet = result["packet"]
    np.testing.assert_allclose(np.array([1, 6, 15, 20, 15, 6, 1]) @ packet[9:16], packet[6])
    excess = np.array([0, 6, 30, 60, 60, 30, 6]) @ packet[9:16]
    assert np.all(excess > 1)
    np.testing.assert_array_equal(packet[5], packet[8])


def test_regulatory_charge_excluded_but_voltage_controls_mirna_transport(panel):
    case = get_case(panel, "S01")
    primary, context = ref.initial_state(panel, case)
    baseline = ref.evaluate(primary, context, panel, case)
    changed = primary.copy()
    changed[3:] += 50
    regulator = ref.evaluate(changed, context, panel, case)
    np.testing.assert_array_equal(regulator["voltage"], baseline["voltage"])
    np.testing.assert_array_equal(regulator["primary_rate"][:3], baseline["primary_rate"][:3])
    context[0, 0] += 0.01
    voltage = ref.evaluate(primary, context, panel, case)
    assert voltage["junction_flux"][3] != baseline["junction_flux"][3]
    np.testing.assert_array_equal(voltage["local_rate"], baseline["local_rate"])


def test_inert_st_is_retained_without_feedback(panel):
    case = get_case(panel, "S01")
    primary, context = ref.initial_state(panel, case)
    baseline = ref.evaluate(primary, context, panel, case)
    context[2] = [0.37, 0.91]
    result = ref.evaluate(primary, context, panel, case)
    np.testing.assert_array_equal(result["packet"][16], context[2])
    np.testing.assert_array_equal(result["primary_rate"], baseline["primary_rate"])


def test_pumps_depend_on_base_membrane_not_leak_control_per_cell(panel):
    case = get_case(panel, "S09")
    primary, context = ref.initial_state(panel, case)
    baseline = ref.evaluate(primary, context, panel, case)
    case["membrane_diffusion"] = [[0, 1e-18]] * 3
    result = ref.evaluate(primary, context, panel, case)
    np.testing.assert_array_equal(result["pump_flux"][:, 0], np.zeros(3))
    np.testing.assert_array_equal(result["pump_flux"][:, 1], baseline["pump_flux"][:, 1])
    np.testing.assert_array_equal(result["leak_flux"], np.zeros((3, 2)))


def test_algebraic_gate_has_no_hidden_blocked_history(panel):
    case = get_case(panel, "S04")
    primary, context = ref.initial_state(panel, case)
    original = ref.evaluate(primary, context, panel, case)
    later = ref.evaluate(primary, context, panel, case, 7)
    np.testing.assert_array_equal(original["gate_scales"], later["gate_scales"])
    case["controls"] = {"ion_contact": 0, "mirna_contact": 0}
    blocked = ref.evaluate(primary, context, panel, case)
    np.testing.assert_array_equal(original["gate_scales"], blocked["gate_scales"])
    np.testing.assert_array_equal(blocked["junction_flux"], np.zeros(4))
    assert panel["gate_parameters"]["45/45"][-1] > 1  # amplitude, not a probability


def test_heterotypic_orientation_is_more_than_a_sign_change(panel):
    forward = evaluated(panel, "S05")
    reverse_wrong = evaluated(panel, "S06")
    reverse_right = evaluated(panel, "S07")
    assert not np.allclose(forward["gate_scales"], reverse_wrong["gate_scales"])
    np.testing.assert_array_equal(forward["gate_scales"], reverse_right["gate_scales"])
    np.testing.assert_array_equal(forward["primary_rate"], reverse_right["primary_rate"])
    np.testing.assert_array_equal(forward["junction_flux"], -reverse_right["junction_flux"])


def test_right_continuous_event_controls_do_not_pretend_to_evolve_state(panel):
    case = get_case(panel, "S12")
    before = ref.controls_at(panel, case, np.nextafter(0.137, 0))
    at = ref.controls_at(panel, case, 0.137)
    assert before["ion_contact"] == before["mirna_contact"] == 0
    assert at["ion_contact"] == at["mirna_contact"] == 1
    np.testing.assert_array_equal(
        evaluated(panel, "S12", 0)["packet"], evaluated(panel, "S12", 0.137)["packet"]
    )


@pytest.mark.parametrize("value", [-0.01, 1.01, np.nan, np.inf])
@pytest.mark.parametrize("name", ["ion_contact", "mirna_contact", "pump", "leak"])
def test_invalid_control_domain_refused(panel, name, value):
    case = get_case(panel, "S01")
    case["controls"] = {name: np.full(ref.CONTROL_SHAPES[name], value)}
    with pytest.raises(ValueError):
        ref.evaluate(*ref.initial_state(panel, case), panel, case)


@pytest.mark.parametrize(
    "row,value", [(0, 0), (0, 1e-9), (0, 1001), (3, -1), (3, 1001), (1, np.nan), (5, np.inf)]
)
def test_invalid_state_refused_not_clipped(panel, row, value):
    case = get_case(panel, "S01")
    primary, context = ref.initial_state(panel, case)
    primary[row, 0] = value
    with pytest.raises(ValueError):
        ref.evaluate(primary, context, panel, case)


@pytest.mark.parametrize(
    "change",
    [
        "bad_shape",
        "invalid_voltage",
        "self_edge",
        "bad_context",
        "negative_diffusion",
        "unknown_control",
        "bad_future_event",
    ],
)
def test_invalid_layout_and_future_settings_refused(panel, change):
    case = get_case(panel, "S01")
    primary, context = ref.initial_state(panel, case)
    if change == "bad_shape":
        primary = primary[:, :1]
    elif change == "invalid_voltage":
        context[0, 0] += 1
    elif change == "self_edge":
        case["edge"] = [0, 0]
    elif change == "bad_context":
        context[1, 0] = -1
    elif change == "negative_diffusion":
        case["membrane_diffusion"] = [[-1e-18, 1e-18]] * 3
    elif change == "unknown_control":
        case["controls"] = {"gate_memory": 1}
    else:
        case["events"] = [{"time": 0.5, "set": {"ion_contact": -1}}]
    with pytest.raises(ValueError):
        ref.evaluate(primary, context, panel, case)


@pytest.mark.parametrize(
    "corruption",
    [
        "rhs",
        "flux_sign",
        "derived_slope",
        "stale_cache",
        "gate",
        "charge",
        "restoration",
        "missing_probe",
        "source",
    ],
)
def test_checker_detects_corrupted_native_meanings(tmp_path, corruption):
    native = json.loads(check.FIXTURE.read_text())
    record = native["probes"]["records"][1]
    if corruption == "rhs":
        record["primary_rate"][0][0] += 0.01
    elif corruption == "flux_sign":
        record["junction_flux"][3] *= -1
    elif corruption == "derived_slope":
        record["native_packet_rate"][8][0] = 1
    elif corruption == "stale_cache":
        record["input_packet"] = record["packet"]
    elif corruption == "gate":
        record["gate_scales"][0] = 0.5
    elif corruption == "charge":
        native["probes"]["profile"]["mirna_in_voltage"] = True
    elif corruption == "restoration":
        record["audits"]["temporary_parameters_restored"] = False
    elif corruption == "missing_probe":
        native["probes"]["records"].pop()
    else:
        native["source_hashes"]["sim.py"] = "0" * 64
    path = tmp_path / "corrupted.json"
    path.write_text(json.dumps(native))
    with pytest.raises(ValueError):
        check.verify(path)
