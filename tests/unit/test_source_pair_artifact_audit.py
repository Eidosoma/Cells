"""Independent saved-state audit checks; no reference integration or upstream files."""

import json

import numpy as np
import pytest

from scripts import audit_source_pair_numerics as audit
from scripts.source_pair_native_protocol import native_plan

PANEL = audit.ROOT / "configs/reference/source_emt_pair_panel_v1.json"
EXTENSION = audit.ROOT / "configs/reference/source_emt_pair_event_refinement_v1.json"


def fixture():
    panel = json.loads(PANEL.read_text())
    case = panel["cases"][5]
    anchor, _ = audit.initial(panel, case)
    value = np.zeros((1, 30))
    value[0, :12] = anchor.ravel() + np.array(
        [0.00007, 0.00014, 0.00001, 0.00005, 0, 0, -0.007, 0.014, 0.005, 0.006, 0.007, 0.008]
    )
    value[0, 12:14] = [0.0001, 0.0002]
    value[0, 18:20] = [0.00001, 0.00002]
    value[0, 21] = 0.00001
    value[0, 23:29] = [0.003, 0.004, 0.005, 0.006, 0.007, 0.008]
    value[0, 29] = 0.01
    return panel, case, value


@pytest.mark.parametrize("increments", [False, True])
def test_independent_typed_exchange_accounting(increments):
    panel, case, value = fixture()
    if increments:
        anchor, _ = audit.initial(panel, case)
        value[:, :12] -= anchor.ravel()
    result = audit.check_state(value, panel, case, increments=increments)
    assert result["states"] == 1
    assert result["max_accounting_error"] < 1e-12


@pytest.mark.parametrize("case_index", [0, 5])
def test_prepared_and_constructed_anchors(case_index):
    panel = json.loads(PANEL.read_text())
    case = panel["cases"][case_index]
    assert (
        audit.check_state(np.zeros((1, 30)), panel, case, increments=True)["max_accounting_error"]
        == 0
    )


@pytest.mark.parametrize("kind", ["ledger", "finite", "shape", "primary", "voltage"])
def test_saved_state_corruption_refused(kind):
    panel, case, value = fixture()
    if kind == "ledger":
        value[0, 29] += 1
    elif kind == "finite":
        value[0, 0] = np.nan
    elif kind == "shape":
        value = value[:, :-1]
    elif kind == "primary":
        value[0, 0] -= 11
        value[0, 12] -= 11
    else:
        value[0, 0] += 0.1
        value[0, 12] += 0.1
    with pytest.raises(ValueError):
        audit.check_state(value, panel, case)


def test_native_extension_preserves_the_baseline_and_refines_all_three_knobs():
    original_cases, original_levels = native_plan()
    cases, levels = native_plan(EXTENSION)
    assert len(original_cases) == 14
    assert [c["id"] for c in cases] == ["S12"]
    assert levels[0] == original_levels[-1]
    for index, scale in ((1, 0.5), (2, 0.25)):
        for key in ("time_step", "max_delta_voltage", "max_fractional_concentration"):
            assert levels[index][key] == levels[0][key] * scale


@pytest.mark.parametrize("kind", ["identity", "cases", "scale", "name", "count"])
def test_invalid_native_extension_refused(tmp_path, kind):
    data = json.loads(EXTENSION.read_text())
    if kind == "identity":
        data["base_protocol_sha256"] = "bad"
    elif kind == "cases":
        data["case_ids"] = ["S99"]
    elif kind == "scale":
        data["native_refinements"][1]["scale_from_fine"] = 0.75
    elif kind == "name":
        data["native_refinements"][1]["name"] = "fine"
    else:
        data["native_refinements"] = data["native_refinements"][:1]
    path = tmp_path / "extension.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        native_plan(path)
