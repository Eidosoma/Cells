"""An actual one-step history survives an injected post-integration rejection."""

import json

import numpy as np
import pytest

from cells.core import runner
from cells.core.errors import NumericalError
from cells.core.specs import parse_spec
from cells.models import surface_cotransport_water as model
from tests.unit.test_surface_cotransport_water_response_full import run_captured
from validation.tissue import surface_cotransport_water_response as panel


def test_complete_proposed_history_is_saved_before_original_rejection(tmp_path, monkeypatch):
    monkeypatch.setenv("CELLS_COMPONENT_EVIDENCE", str(tmp_path))
    raw = panel.definition()
    raw["experiment"].update(end_time=panel.DT, observation_times=[0.0, panel.DT])
    raw["execution"]["jit"] = False
    spec = parse_spec(raw)
    state, layout = model.initial_values(spec)
    original_check, original_analysis = model.check_values, runner._analyse_segment
    failure = NumericalError("injected after the real one-step integration")

    def refuse_history(value, definition):
        if value.amount_increment.ndim == 3:
            raise failure
        return original_check(value, definition)

    monkeypatch.setattr(model, "check_values", refuse_history)
    with pytest.raises(NumericalError) as caught:
        run_captured(spec, "injected", monkeypatch)
    assert caught.value is failure and runner._analyse_segment is original_analysis
    folder = tmp_path / "cpu"
    record = json.loads((folder / "injected-proposed-history.json").read_text())
    rejection = json.loads((folder / "injected-rejection.json").read_text())
    assert record["status"] == "proposed_not_yet_accepted"
    assert rejection["accepted_result_returned"] is False
    with np.load(folder / "injected-proposed-history.npz", allow_pickle=False) as saved:
        np.testing.assert_array_equal(saved["proposed_times"], [0.0, panel.DT])
        for name, value in state._asdict().items():
            assert saved[name].shape == (2, *value.shape)
            np.testing.assert_array_equal(saved[name][0], value)
        for name, value in layout._asdict().items():
            np.testing.assert_array_equal(saved["layout__" + name], value)
        assert np.any(saved["energy_amount_increment_fmol"][1] != 0)
