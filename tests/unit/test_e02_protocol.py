"""SPEC-004 freeze/inventory checks, not a trajectory or positive switching test."""

import ast
import json

import pytest

from cells.core.specs import parse_spec
from scripts import check_e02_protocol as check


def test_freeze_and_expanded_inventory():
    receipt = check.verify()
    assert receipt["status"] == "pass"
    assert receipt["conditions"] == 14
    assert receipt["primary_conditions"] == 2
    assert receipt["cells_across_independent_conditions"] == 36
    assert receipt["edges_across_independent_conditions"] == 22
    assert receipt["observations_per_condition"] == 1007
    assert receipt["terminal_window_observations"] == 102
    assert receipt["preparation_packets"] == "not_generated"
    assert receipt["trajectory_qualification"] == "not_run"
    assert receipt["production_graph_implementation"] == "not_implemented"
    assert receipt["switching_outcomes"] == "not_measured"
    assert "workspace_audit" not in receipt  # historical optional audit, not a moving test pin


@pytest.mark.parametrize("direction", ["E_to_M", "M_to_E"])
def test_geometry_and_controls_are_data_not_independent_pairs(direction):
    cases = {
        case["id"].split("/")[1]: case
        for case in check.case_inventory()
        if case["id"].startswith(direction)
    }
    active, blocked = cases["active"], cases["blocked"]
    for name in ("cell_ids", "edge_ids", "edges", "prepared_labels", "mirna_diffusion"):
        assert active[name] == blocked[name]
    assert active["cell_ids"] == [100, 200, 300]
    assert active["edges"] == [[100, 200], [100, 300]]
    assert active["reference_coordinate_count"] == 47
    assert active["mirna_diffusion"] == [2e-15, 2e-15]  # no degree normalization
    assert active["ion_contact"] == active["mirna_contact"] == [1.0, 1.0]
    assert blocked["ion_contact"] == blocked["mirna_contact"] == [0.0, 0.0]
    assert cases["ionic_only"]["ion_contact"] == [1.0, 1.0]
    assert cases["ionic_only"]["mirna_contact"] == [0.0, 0.0]
    assert cases["mirna_only"]["ion_contact"] == [0.0, 0.0]
    assert cases["mirna_only"]["mirna_contact"] == [1.0, 1.0]
    assert cases["one_neighbor"]["edges"] == [[100, 200]]
    assert cases["one_neighbor"]["reference_coordinate_count"] == 30
    assert cases["isolated"]["cell_ids"] == [100]
    assert cases["isolated"]["edges"] == cases["isolated"]["edge_ids"] == []
    assert cases["isolated"]["reference_coordinate_count"] == 13
    recipient, target = direction.split("_to_")
    assert active["prepared_labels"] == [recipient, target, target]
    assert cases["same_state"]["prepared_labels"] == [recipient] * 3
    assert cases["same_state"]["target_label"] == target


@pytest.mark.parametrize("case", check.case_inventory(), ids=lambda case: case["id"])
def test_complete_case_axis_clock_and_late_preparation_binding(case):
    assert len(set(case["cell_ids"])) == len(case["cell_ids"])
    assert len(set(case["edge_ids"])) == len(case["edges"])
    assert len(case["prepared_labels"]) == len(case["cell_ids"])
    assert all(len(row) == len(case["cell_ids"]) for row in case["membrane_diffusion"])
    assert all(len(row) == len(case["edges"]) for row in case["ionic_diffusion"])
    assert (case["start_time"], case["end_time"]) == (0.0, 1000.0)
    assert case["prepared_packet_status"] == "not_generated"
    assert case["model_contract"] == "bitsey_emt_graph@1-design"
    assert "initial_state" not in case  # a label must not masquerade as a full packet


def test_fresh_preparation_and_no_implicit_equilibrium_or_memory_claim():
    protocol = check.load_protocol()
    prep = protocol["preparation"]
    assert prep["duration"] == 500
    assert prep["initial_ions"] == [10.0, 125.0, 55.0]
    assert prep["initial_regulation"] == {"E": [100, 0, 0], "M": [0, 100, 100]}
    assert prep["ion_contact"] == prep["mirna_contact"] == 0
    assert prep["qualification_window"] == [400, 500]
    assert prep["equilibrium_required"] is False
    assert protocol["experiment"]["donor_removal"] is False
    assert protocol["experiment"]["early_biological_stopping"] is False
    assert protocol["equations"]["donor_clamp"] is False
    assert protocol["numerics"]["production_candidate"] == "not_selected"


def test_observations_do_not_stand_in_for_integration_steps():
    times = check.observation_times()
    assert times == sorted(set(times))
    assert times[0] == 0 and times[-1] == 1000
    assert 999.613 in times and 500.137 in times
    assert 0.01 not in times
    assert check.load_protocol()["experiment"]["events"] == []


def test_expansion_has_no_shared_mutable_cell_arrays():
    first, second = check.case_inventory()[:2]
    first["membrane_diffusion"][0][0] = 99
    assert first["membrane_diffusion"][1][0] == 1e-18
    assert second["membrane_diffusion"][0][0] == 1e-18
    assert check.case_inventory()[0]["membrane_diffusion"][0][0] == 1e-18


@pytest.mark.parametrize(
    "field",
    ["preparation", "observer", "equations", "numerics", "resources", "experiment", "provenance"],
)
def test_protocol_changes_require_a_new_named_freeze(tmp_path, field):
    protocol = check.load_protocol()
    del protocol[field]
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(protocol))
    with pytest.raises(ValueError, match="Frozen input changed"):
        check.verify(changed)


def test_design_data_is_not_a_runnable_production_config():
    with pytest.raises(ValueError):
        parse_spec(check.load_protocol())


def test_auditor_has_no_simulator_or_numerical_imports():
    tree = ast.parse((check.ROOT / "scripts/check_e02_protocol.py").read_text())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module)
    assert imports == {"argparse", "hashlib", "json", "pathlib"}
