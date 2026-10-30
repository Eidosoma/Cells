"""An actual one-step history survives an injected post-integration rejection."""

import json
from copy import deepcopy

import numpy as np
import pytest

from cells.core import runner
from cells.core.errors import NumericalError
from cells.core.specs import parse_spec
from cells.models import surface_cotransport_water as model
from tests.unit import test_surface_cotransport_water_response_full as full
from tests.unit.test_surface_cotransport_water_response_full import (
    run_captured,
    score,
    state_comparison,
)
from validation.tissue import surface_cotransport_water_response as panel


def reference_receipts(tmp_path, monkeypatch, coordinates="transport_ledgers"):
    """Manufactured saved records exercise admission, not physical integration."""
    stop = 20001 * panel.DT
    declaration = dict(
        local_times_s=[panel.INTERVENTION_TIME, (panel.INTERVENTION_TIME + stop) / 2, stop],
        reference_material_coordinates=coordinates,
        reference_tolerance_scale=1 / 32,
    )
    path = tmp_path / "declaration.json"
    path.write_text(json.dumps(declaration))
    monkeypatch.setenv("CELLS_RECOVERY_GRID_INPUTS", str(path))
    monkeypatch.setenv("CELLS_COMPONENT_EVIDENCE", str(tmp_path))
    raw = panel.refined_recovery_definition(declaration["local_times_s"])
    context = full.reference.bind(raw)
    start = full.reference.initial(context)
    state = np.tile(start, (len(raw["experiment"]["observation_times"]), 1))
    arrays = dict(
        state=state,
        potential_V=np.zeros((state.shape[0], 2)),
        initial_state=start.copy(),
        final_state=state[-1].copy(),
    )
    records = {}
    for factor in (1, 2):
        report = dict(
            status="passed",
            inputs=raw,
            segment_coordinates="local_delta",
            production_imports_denied=True,
            refinement=factor,
            tolerance_scale=1 / 32,
            rtol=(2e-11 / factor) / 32,
            amount_volume_energy_atol=(2e-14 / factor) / 32,
            electrode_charge_atol_C=(1e-29 / factor) / 32,
            times=raw["experiment"]["observation_times"],
        )
        if coordinates == "transport_ledgers":
            codec = full.material.bind(context)
            report.update(
                material_coordinates=coordinates,
                integrated_scalar_count=int(codec.size),
                complete_scalar_count=int(start.size),
                derived_fields=list(full.material.BULK_FIELDS),
                field_charge_source="electrogenic_transport_ledgers",
                fresh_original_start=True,
            )
        records[f"response-reference-supply_recovery-r{factor}"] = (
            report,
            {key: value.copy() for key, value in arrays.items()},
        )
    monkeypatch.setattr(full, "saved", records.__getitem__)
    return declaration, records


@pytest.mark.parametrize("coordinates", ["full", "transport_ledgers"])
def test_declared_reference_coordinates_reach_the_production_gate(
    tmp_path, monkeypatch, coordinates
):
    _, records = reference_receipts(tmp_path, monkeypatch, coordinates)
    before = deepcopy(records)
    calls = []

    def capture(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(full, "qualify_complete_response", capture)
    full.test_full_recovery_with_declared_local_resolution(monkeypatch)
    assert len(calls) == 1 and calls[0][1]["reference_material_coordinates"] == coordinates
    assert calls[0][1]["reference_coordinates"] == "local_delta"
    assert calls[0][1]["expected"] is records["response-reference-supply_recovery-r1"][1]
    for name, (report, arrays) in records.items():
        assert report == before[name][0]
        for key, value in arrays.items():
            np.testing.assert_array_equal(value, before[name][1][key])
    evidence = json.loads(
        (tmp_path / "cpu/response-reference-stability-before-trajectory.json").read_text()
    )
    assert evidence["budgets"] == dict(atol=3e-14, charge_atol=3e-28, rtol=3e-11)
    assert evidence["max_error_over_budget"] == 0


@pytest.mark.parametrize(
    "damage",
    [
        "undeclared_coordinates",
        "mixed_reference_modes",
        "wrong_solver_dimension",
        "wrong_charge_source",
        "different_original_state",
        "inconsistent_bulk",
        "different_endpoint",
    ],
)
def test_incompatible_reference_coordinates_stop_before_production(tmp_path, monkeypatch, damage):
    declaration, records = reference_receipts(tmp_path, monkeypatch)
    report, arrays = records["response-reference-supply_recovery-r2"]
    if damage == "undeclared_coordinates":
        declaration.pop("reference_material_coordinates")
        (tmp_path / "declaration.json").write_text(json.dumps(declaration))
    elif damage == "mixed_reference_modes":
        report["material_coordinates"] = "full"
    elif damage == "wrong_solver_dimension":
        report["integrated_scalar_count"] = report["complete_scalar_count"]
    elif damage == "wrong_charge_source":
        report["field_charge_source"] = "bulk_increments"
    elif damage == "different_original_state":
        arrays["initial_state"][-1] = 1e-20
    elif damage == "inconsistent_bulk":
        arrays["state"][1, 0] = 1e-20  # Below accuracy budget, still off the exact coordinate map.
    elif damage == "different_endpoint":
        arrays["final_state"][-1] = 1e-20
    preserved = {key: value.copy() for key, value in arrays.items()}

    def forbidden(*args, **kwargs):
        pytest.fail("Production launched with incompatible reference coordinates")

    monkeypatch.setattr(full, "qualify_complete_response", forbidden)
    with pytest.raises((AssertionError, ValueError)):
        full.test_full_recovery_with_declared_local_resolution(monkeypatch)
    assert not (tmp_path / "cpu/response-trajectory-supply_recovery.json").exists()
    for key, value in arrays.items():
        np.testing.assert_array_equal(value, preserved[key])


def test_refinement_cannot_mix_reference_coordinates_with_a_previous_baseline(
    tmp_path, monkeypatch
):
    _, records = reference_receipts(tmp_path, monkeypatch)
    raw = records["response-reference-supply_recovery-r1"][0]["inputs"]
    records["response-trajectory-supply_recovery"] = (
        dict(
            status="passed",
            inputs=raw,
            reference_coordinates="local_delta",
            window_steps=256,
            reference_material_coordinates="full",
        ),
        {},
    )

    def forbidden(*args, **kwargs):
        pytest.fail("Refinement launched against a baseline using different reference coordinates")

    monkeypatch.setattr(full, "qualify_recovery_refinement", forbidden)
    with pytest.raises(AssertionError):
        full.test_declared_recovery_refinement_against_fresh_references(monkeypatch)


def test_failed_reference_stability_prevents_production_launch(tmp_path, monkeypatch):
    monkeypatch.setenv("CELLS_COMPONENT_EVIDENCE", str(tmp_path))
    raw = panel.definition("supply_recovery")
    context = full.reference.bind(raw)
    count = len(raw["experiment"]["observation_times"])
    ordinary = np.zeros((count, full.reference.initial(context).size))
    tighter = ordinary.copy()
    tighter[1, 0] = 1.0
    inputs_seen = []

    def supplied(factor):
        inputs_seen.append(factor)
        return raw, dict(state=ordinary if factor == 1 else tighter)

    def forbidden(*args, **kwargs):
        pytest.fail("Production was launched after failed reference stability")

    monkeypatch.setattr(full, "declared_recovery_reference", supplied)
    monkeypatch.setattr(full, "qualify_complete_response", forbidden)
    with pytest.raises(AssertionError):
        full.test_full_recovery_with_declared_local_resolution(monkeypatch)
    assert inputs_seen == [1, 2]
    report = json.loads(
        (tmp_path / "cpu/response-reference-stability-before-trajectory.json").read_text()
    )
    assert report["status"] == "failed" and report["failed_fields"] == ["amount_increment"]
    assert report["budgets"] == dict(atol=3e-14, charge_atol=3e-28, rtol=3e-11)


def test_all_failed_comparisons_are_saved_before_accuracy_rejection(tmp_path, monkeypatch):
    monkeypatch.setenv("CELLS_COMPONENT_EVIDENCE", str(tmp_path))
    context = {"shapes": {"amount_increment": (2, 1), "charge_C": (1,), "empty": (1, 0)}}
    expected = np.zeros((2, 3))
    actual = np.array([[0.0, 0.0, 0.0], [2e-4, 0.0, 3e-6]])
    preserved = actual.copy()
    with pytest.raises(AssertionError):
        score(
            context,
            actual,
            expected,
            times=[0.0, 0.5],
            atol=1e-4,
            charge_atol=1e-6,
            rtol=0.0,
            evidence_name="deliberate-accuracy-failure",
        )
    record = json.loads((tmp_path / "cpu/deliberate-accuracy-failure.json").read_text())
    assert record["status"] == "failed" and record["finite"]
    assert record["failed_fields"] == ["amount_increment", "charge_C"]
    assert record["max_error_over_budget"] == pytest.approx(3.0)
    worst = record["fields"]["amount_increment"]["worst"]
    assert worst["index"] == [1, 0, 0] and worst["time_s"] == 0.5
    assert worst["actual"] == 2e-4 and worst["expected"] == 0.0
    assert worst["budget"] == 1e-4
    assert record["fields"]["charge_C"]["worst"]["budget"] == 1e-6
    assert record["fields"]["empty"]["compared_values"] == 0
    assert record["fields"]["empty"]["worst"] is None
    np.testing.assert_array_equal(actual, preserved)
    assert score(context, expected[0], expected[0]) == 0.0


def test_comparison_refuses_broadcasting_partial_fields_and_wrong_time_axis():
    context = {"shapes": {"amount_increment": (2, 1)}}
    actual = np.zeros((3, 2))
    with pytest.raises(ValueError, match="matching complete"):
        state_comparison(context, actual, actual[:1])
    with pytest.raises(ValueError, match="matching complete"):
        state_comparison(context, actual[:, :1], actual[:, :1])
    with pytest.raises(ValueError, match="observation axis"):
        state_comparison(context, actual, actual, times=[0.0, 0.5])


@pytest.mark.parametrize("invalid", [np.nan, np.inf, -np.inf])
def test_nonfinite_comparison_remains_json_safe_and_rejected(tmp_path, monkeypatch, invalid):
    monkeypatch.setenv("CELLS_COMPONENT_EVIDENCE", str(tmp_path))
    context = {"shapes": {"amount_increment": (1,)}}
    with pytest.raises(AssertionError):
        score(context, [invalid], [0.0], evidence_name="nonfinite-comparison")
    record = json.loads((tmp_path / "cpu/nonfinite-comparison.json").read_text())
    assert record["status"] == "failed" and not record["finite"]
    assert record["max_error_over_budget"] is None
    assert record["failed_fields"] == ["amount_increment"]
    json.dumps(record, allow_nan=False)


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


def test_numbered_windows_keep_full_history_restart_and_late_rejection(tmp_path, monkeypatch):
    monkeypatch.setenv("CELLS_COMPONENT_EVIDENCE", str(tmp_path))
    raw = panel.definition()
    raw["experiment"].update(
        end_time=2 * panel.DT,
        observation_times=[0.0, panel.DT / 2, panel.DT, 2 * panel.DT],
    )
    raw["execution"].update(jit=False, refinement_times=[panel.DT / 2])
    spec = parse_spec(raw)
    whole = run_captured(spec, "whole", monkeypatch)
    windows = run_captured(spec, "windows", monkeypatch, window_steps=2)
    np.testing.assert_array_equal(windows.times, whole.times)
    for actual, expected in zip(windows.history, whole.history, strict=True):
        np.testing.assert_array_equal(actual, expected)
    for field, expected in vars(whole.observations).items():
        np.testing.assert_array_equal(getattr(windows.observations, field), expected)
    assert windows.diagnostics == whole.diagnostics
    resumed = run_captured(
        spec,
        "resumed",
        monkeypatch,
        checkpoint=windows.checkpoint_at(panel.DT / 2),
        window_steps=1,
    )
    np.testing.assert_array_equal(resumed.times, whole.times[1:])
    for actual, expected in zip(resumed.history, whole.history, strict=True):
        np.testing.assert_array_equal(actual, expected[1:])
    for actual, expected in zip(
        (*resumed.final.state, *resumed.final.layout),
        (*whole.final.state, *whole.final.layout),
        strict=True,
    ):
        np.testing.assert_array_equal(actual, expected)
    assert (resumed.final.time, resumed.final.step_index, resumed.final.event_index) == (
        whole.final.time,
        whole.final.step_index,
        whole.final.event_index,
    )
    original = model.check_values
    failure = NumericalError("deliberate rejection after one accepted window")

    def reject_later_history(value, definition):
        if value.amount_increment.ndim == 3 and np.any(value.pump_cycles[0] != 0):
            raise failure
        return original(value, definition)

    monkeypatch.setattr(model, "check_values", reject_later_history)
    with pytest.raises(NumericalError) as caught:
        run_captured(spec, "refused", monkeypatch, window_steps=1)
    assert caught.value is failure
    folder = tmp_path / "cpu"
    assert (folder / "refused-window-000000-acceptance.json").exists()
    assert not (folder / "refused-window-000001-acceptance.json").exists()
    report = json.loads((folder / "refused-window-000001-rejection.json").read_text())
    assert report["accepted_result_returned"] is False
    with np.load(folder / report["proposed_history"], allow_pickle=False) as data:
        np.testing.assert_array_equal(data["proposed_times"], [panel.DT / 2, panel.DT])
        for name, field in whole.history._asdict().items():
            np.testing.assert_array_equal(data[name], field[1:3])
