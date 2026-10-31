"""Metadata/comparison controls; no native source, callback or oracle execution."""

import ast
import copy
import json
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from tests.unit.test_betse_normal_ecm_molecule_event_checkpoint import (
    no_actual_execution as no_actual_execution,
)
from tests.unit.test_betse_normal_ecm_molecule_periodic_checkpoint import (
    forbid_actual_periodic as forbid_actual_periodic,
)
from validation.betse import betse_normal_ecm_molecule_temporal_reference as reference


@pytest.fixture(autouse=True)
def forbid_reference_execution(forbid_actual_periodic, tmp_path):
    codes = {
        reference.native.capture.__wrapped__.__code__,
        reference.native.prepare.__code__,
        reference.native.evaluate.__code__,
        reference.independent.evaluate.__code__,
        reference.independent.resolved_slope.__code__,
        reference.independent.sine.__code__,
        reference.independent.pi.__wrapped__.__code__,
        reference._original_parameters.__code__,
    }
    attempted = []
    previous = sys.getprofile()

    def guard(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if event == "call" and frame.f_code in codes:
            attempted.append(frame.f_code.co_name)
            raise AssertionError("Original/reference numerical execution forbidden")

    sys.setprofile(guard)
    try:
        yield attempted
        assert not attempted
    finally:
        sys.setprofile(previous)
        (tmp_path / "paired-reference-control.json").write_text(
            json.dumps(
                dict(
                    original_reference_entry_attempts=attempted,
                    independent_cases=0,
                    actual_parent_admission=False,
                )
            )
        )


def value(number=0.25):
    return dict(value=number, hex=number.hex(), shape=[], dtype="<f8", category="numpy_scalar")


def test_source_plan_matches_both_pinned_factories_and_exact_selected_statements(tmp_path):
    plan = reference.source_plan()
    assert plan["compiled_or_executed"] is False
    assert plan["selected_statement_count"] == 7 and plan["temporal_lookup_defaults"] is False
    assert set(plan["native_sources"]) == set(reference.periodic.NATIVE_PINS)
    assert len(plan["reference_files"]) == 2
    assert "not complete Parameters" in plan["scope"]
    (tmp_path / "source-plan.json").write_text(json.dumps(plan))


def test_actual_callback_ABI_support_is_source_only_and_explicit(tmp_path):
    plan = reference.callback_abi()
    assert plan["callback_access"] == {"periodic": "factor", "sweep": "factor"}
    assert plan["result_fields"] == ("factor", "phase_rad", "finite")
    assert plan["compatible"] is True and plan["evaluated"] is False
    assert reference.require_abi() == plan
    (tmp_path / "callback-ABI-supported.json").write_text(json.dumps(plan))


@pytest.mark.parametrize("drift", ["annotation", "doc-content", "coefficient", "default"])
def test_factory_comparison_does_not_normalize_executable_or_unknown_differences(drift):
    original = ast.parse(
        "def f_sweep(pc,cells,p) -> tuple:\n    '''Factory.'''\n    return 1,p\n"
    ).body[0]
    adopted = copy.deepcopy(original)
    adopted.returns = None
    if drift == "annotation":
        adopted.returns = ast.Name(id="float", ctx=ast.Load())
    elif drift == "doc-content":
        adopted.body[0].value = ast.Constant(value="Foreign factory.")
    elif drift == "coefficient":
        adopted.body[-1].value.elts[0] = ast.Constant(value=2)
    else:
        adopted.args.defaults = [ast.Constant(value=None)]
    with pytest.raises(ValueError):
        reference.factory_correspondence(original, adopted, "f_sweep")


@pytest.mark.parametrize("field", ["factor", "value", "missing"])
def test_ABI_inspection_does_not_hydrate_a_callback_alias(tmp_path, monkeypatch, field):
    callbacks = tmp_path / "callbacks.py"
    callbacks.write_text(
        "def prepared_callback(record):\n"
        "    if record['kind'] == 'periodic':\n"
        f"        return lambda t: laws.evaluate(None, t).{field}\n"
        "    if record['kind'] == 'sweep':\n"
        f"        return lambda t: laws.evaluate(None, t).{field}\n"
    )
    monkeypatch.setattr(reference, "literal", SimpleNamespace(__file__=str(callbacks)))
    result = reference.callback_abi()
    assert result["compatible"] is (field == "factor")
    assert result["evaluated"] is False


@pytest.mark.parametrize("target", ["parameters", "modulate"])
def test_original_source_drift_refuses_without_capture(tmp_path, target):
    root = tmp_path / "native"
    for name in reference.periodic.NATIVE_PINS:
        destination = root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((reference.NATIVE_ROOT / name).read_bytes())
        if target in name:
            destination.write_bytes(destination.read_bytes() + b"\n# drift\n")
    with pytest.raises(ValueError, match="pin changed"):
        reference.source_plan(root)


@pytest.mark.parametrize(
    "bad", ["value", "hex", "dtype", "shape", "category", "nonfinite", "oracle"]
)
def test_comparison_refuses_value_category_and_independent_budget_drift(bad):
    original, candidate = value(), value()
    oracle = dict(factor=0.25, factor_budget=1e-15)
    if bad == "value":
        candidate = value(0.25000000000000006)
    elif bad == "hex":
        candidate["hex"] = "foreign"
    elif bad == "dtype":
        candidate["dtype"] = "<f4"
    elif bad == "shape":
        candidate["shape"] = [1]
    elif bad == "category":
        candidate["category"] = "python_callable"
    elif bad == "nonfinite":
        candidate["value"] = float("nan")
    else:
        oracle["factor"] = 0.250001
    with pytest.raises(ValueError):
        reference.compare_factor(original, candidate, oracle)


def test_zero_vs_0D_categories_are_retained_without_new_numeric_tolerance():
    scalar = reference.stamp(np.float64(0.25))
    array = reference.stamp(np.array(0.25, dtype=np.float64))
    assert scalar["category"] == "numpy_scalar" and array["category"] == "array"
    assert (
        reference.compare_factor(scalar, array, dict(factor=0.25, factor_budget=1e-15))[
            "exact_original_match"
        ]
        is True
    )


@pytest.mark.parametrize("bad", [1.0, np.float32(0.25), np.array([0.25]), np.array(float("inf"))])
def test_non_source_scalar_or_axis_is_not_coerced(bad):
    with pytest.raises(ValueError):
        reference.stamp(bad)


@pytest.mark.parametrize("gates", [("0", "0"), ("1", "0"), ("0", "1")])
def test_reference_requires_both_releases_before_output(monkeypatch, tmp_path, gates):
    for name, state in zip(reference.RELEASES, gates, strict=True):
        monkeypatch.setenv(name, state)
    destination = tmp_path / "held"
    with pytest.raises(ValueError, match="both releases"):
        reference.paired_compare(
            destination,
            None,
            None,
            expected_binding_identity=None,
            expected_entry_identity=None,
            labels=[0.0, 1.5, 3.0],
        )
    assert not destination.exists()


def test_missing_actual_SIM_parent_retained_before_original_or_reference_entry(
    monkeypatch, tmp_path
):
    for name in reference.RELEASES:
        monkeypatch.setenv(name, "1")
    destination = tmp_path / "missing-SIM"
    with pytest.raises(ValueError, match="Missing actual retained SIM") as caught:
        reference.paired_compare(
            destination,
            None,
            None,
            expected_binding_identity="not-admitted",
            expected_entry_identity="not-admitted",
            labels=[0.0, 1.5, 3.0],
        )
    assert caught.value.checkpoint_retention["complete"] is True
    assert (destination / "failure/manifest.json").is_file()
    attempts = json.loads((destination / "attempts.json").read_bytes())["attempts"]
    assert len(attempts) == 1 and attempts[0]["operation"] == "required-retained-SIM"
    assert not (destination / "result.json").exists()


def test_failure_and_attempt_IO_do_not_mask_primary_error(monkeypatch, tmp_path):
    for name in reference.RELEASES:
        monkeypatch.setenv(name, "1")
    primary = TypeError("synthetic primary source refusal")

    def retainer(*args):
        def take(*args, **kwargs):
            raise primary

        return take

    def io_failure(*args, **kwargs):
        raise OSError("synthetic secondary I/O")

    monkeypatch.setattr(reference.preparation, "_retainer", retainer)
    monkeypatch.setattr(reference.preparation.archives, "write_archive", io_failure)
    monkeypatch.setattr(reference.preparation.checkpoint.codec, "_write_json", io_failure)
    with pytest.raises(TypeError) as caught:
        reference.paired_compare(
            tmp_path / "failed",
            None,
            None,
            expected_binding_identity=None,
            expected_entry_identity=None,
            labels=[0.0, 1.5, 3.0],
        )
    assert caught.value is primary and len(primary.__notes__) == 2
