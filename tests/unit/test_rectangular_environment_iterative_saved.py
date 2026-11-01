"""Retained-input/orchestration controls; real solves and JAX are replaced.

The exact reference controls use declared four-cell rational examples only.
"""

import copy
import json
from fractions import Fraction
from types import SimpleNamespace

import numpy as np
import pytest

from validation.betse import rectangular_environment_iterative_saved as adapter


def ratio(record):
    return Fraction(int(record["numerator"]), int(record["denominator"]))


def test_exact_reference_detects_wrong_dense_and_candidate_independently():
    good = [-0.5, 0.0, 0.0, 0.5]
    args = ((2, 2), (0.0, 2.0, 0.0, 2.0), [1.0, 0.0, 0.0, -1.0])
    exact = adapter.arithmetic(*args, good, good, 2e-12)
    assert exact["residual_ok"] and exact["gauge_ok"] and exact["dense_agreement_bounded"]
    assert ratio(exact["residual_inf"]) == ratio(exact["potential_difference_bound"]) == 0
    bad = adapter.arithmetic(*args, [0.0] * 4, good, 2e-12)
    assert not bad["residual_ok"] and bad["dense_agreement_bounded"]
    wrong_dense = adapter.arithmetic(*args, good, [0.0] * 4, 2e-12)
    assert wrong_dense["residual_ok"] and ratio(wrong_dense["dense_residual_inf"]) == 1
    assert ratio(wrong_dense["potential_difference_bound"]) >= Fraction(1, 2)


def test_exact_reference_keeps_gauge_shift_and_incompatible_rhs_visible():
    shift = adapter.arithmetic((2, 2), (0.0, 2.0, 0.0, 2.0), [0.0] * 4, [3.0] * 4, [0.0] * 4, 0.0)
    assert shift["residual_ok"] and not shift["gauge_ok"]
    assert ratio(shift["potential_difference_bound"]) == 3
    bad = adapter.arithmetic((2, 2), (0.0, 2.0, 0.0, 2.0), [1.0] * 4, [0.0] * 4, [0.0] * 4, 2e-12)
    assert not bad["rhs_exactly_balanced"] and not bad["residual_ok"]


def test_exact_reference_uses_bound_coefficients_not_rounded_spacing_or_stored_residual():
    bounds = (0.0, 0.6, 0.0, 1.0)
    x = [-0.09, 0.09, -0.09, 0.09]
    b = [2.0, -2.0, 2.0, -2.0]
    result = adapter.arithmetic((2, 2), bounds, b, x, x, 2e-12)
    dx = Fraction.from_float(0.6) / 2
    exact = abs(2 * Fraction.from_float(0.09) / dx**2 - 2)
    assert ratio(result["residual_inf"]) == exact
    assert ratio(result["dense_residual_inf"]) == exact


@pytest.fixture
def retained(tmp_path, monkeypatch):
    saved = tmp_path / "retained"
    saved.mkdir()
    baseline = saved / "baseline.json"
    adapter.prior.write(baseline, dict(inputs=[]))
    baseline_pin = adapter.prior.pin(baseline)
    shape, bounds = (2, 2), (0.0, 2.0, 0.0, 2.0)
    points = np.array([[0.5, 0.5], [1.5, 0.5], [0.5, 1.5], [1.5, 1.5]])
    vx = np.array([[0.0, 1.0, 2.0]] * 3)
    vy = vx.T.copy()
    indices = list(np.ndindex(shape))
    observed = adapter.previous.metric.GridObservation(
        shape,
        bounds,
        1.0,
        tuple(map(tuple, points.tolist())),
        tuple(indices),
        (0.0, 1.0, 2.0),
        (0.0, 1.0, 2.0),
        "synthetic-retained",
    )
    arrays = dict(retained_coordinates=points, retained_vertices_x=vx, retained_vertices_y=vy)
    probes = adapter.previous.probes(shape, indices)
    rhs = np.stack(list(probes.values()))
    phi = np.array(
        [
            [0.0] * 4,
            [-0.5, 0.0, 0.0, 0.5],
            [-0.5, -0.5, 0.5, 0.5],
            [0.5, -0.5, 0.5, -0.5],
            [0.0] * 4,
        ]
    )
    reference = saved / "reference.json"
    adapter.prior.write(reference, dict(synthetic=True))
    report = dict(
        kind=adapter.previous.KIND,
        status="completed_numerical_diagnostic_only",
        inputs=[baseline_pin],
        independent_arithmetic=adapter.prior.pin(reference),
        grid=dict(shape=list(shape), bounds_m=list(bounds), spacing_xy_m=[1.0, 1.0]),
        probes=list(probes),
        arrays={
            name: adapter.saved.array_evidence(np, saved, name, value)
            for name, value in dict(**arrays, rhs=rhs, potential=phi).items()
        },
    )
    report_path = saved / "report.json"
    adapter.prior.write(report_path, report)
    review = saved / "review.json"
    adapter.prior.write(
        review,
        dict(report=adapter.prior.pin(report_path), reference=report["independent_arithmetic"]),
    )
    data = dict(
        scope=adapter.SCOPE,
        baseline=baseline_pin,
        dense_report=adapter.prior.pin(report_path),
        dense_review=adapter.prior.pin(review),
        numpy_pins=[],
        policy=dict(adapter.POLICY),
    )
    monkeypatch.setattr(
        adapter.previous, "load_grid", lambda *a: (observed, arrays, dict(indices=indices))
    )
    monkeypatch.setattr(adapter.saved, "primitive_bindings", lambda *a: ())
    calls = []

    def solve(b, grid, *, initial_potential=None, **policy):
        assert policy == adapter.POLICY and b.tobytes() == rhs.tobytes()
        calls.append("warm" if initial_potential is not None else "cold")
        compatible = np.array([True] * 4 + [False])
        residual = np.zeros_like(rhs)
        residual[-1] = -1.0
        iterations = np.array(
            [0, 1, 1, 1, 0] if initial_potential is None else [0] * 5, dtype=np.int32
        )
        return adapter.iterative.SolveResult(
            phi.copy(),
            residual,
            compatible.copy(),
            compatible.copy(),
            np.ones(5, dtype=bool),
            np.ones(5, dtype=bool),
            np.zeros(5, dtype=bool),
            iterations,
            np.max(iterations),
            np.max(abs(residual), axis=-1),
            np.max(abs(rhs), axis=-1) * policy["rtol"],
            np.zeros(5),
        )

    class FakeCompiled:
        def lower(self, b, initial=None):
            return SimpleNamespace(
                compiler_ir=lambda **kw: "stablehlo.while synthetic software only",
                compile=lambda: (
                    lambda *args: solve(
                        args[0],
                        None,
                        initial_potential=args[1] if len(args) == 2 else None,
                        **adapter.POLICY,
                    )
                ),
            )

    monkeypatch.setattr(adapter.iterative, "solve", solve)
    monkeypatch.setattr(adapter, "cpu_jax", lambda *a: (None, FakeCompiled(), dict(synthetic=True)))
    monkeypatch.setattr(adapter, "compiled_host", lambda j, result: result)
    return data, tmp_path / "output", calls, report, report_path


def test_full_adapter_preserves_inputs_and_cold_warm_outputs(retained):
    data, output, calls, _, _ = retained
    result = adapter.run(data, output)
    assert calls == ["cold", "warm", "cold", "warm"]
    assert result["criteria_passed"] and result["inverse_constructions"] == 0
    assert not result["physical_tissue_admission"] and not result["gpu_qualification"]
    assert result["work"]["new_independent_cases"] == 0
    for name, values in result["results"].items():
        assert set(values) == set(adapter.iterative.SolveResult._fields)
        for record in values.values():
            assert adapter.prior.pin(record["path"])["sha256"] == record["sha256"]
        assert result["checks"][name][-1]["rhs_exactly_balanced"] is False


@pytest.mark.parametrize("field", ["scope", "policy", "baseline", "dense_report", "dense_review"])
def test_changed_declaration_or_pins_refuse_before_solve(retained, field):
    data, output, calls, _, _ = retained
    data = copy.deepcopy(data)
    if field == "scope":
        data[field] = "unknown"
    elif field == "policy":
        data[field]["rtol"] *= 2
    else:
        data[field]["sha256"] = "0" * 64
    with pytest.raises(ValueError):
        adapter.run(data, output)
    assert not calls and not output.exists()


@pytest.mark.parametrize("kind", ["shape", "dtype", "raw", "file"])
def test_saved_array_has_independent_file_shape_dtype_and_bit_checks(retained, kind):
    _, _, _, report, _ = retained
    item = dict(report["arrays"]["rhs"])
    if kind == "shape":
        item["shape"] = [20]
    elif kind == "dtype":
        item["dtype"] = "<f4"
    elif kind == "raw":
        item["raw_c_sha256"] = "0" * 64
    else:
        item["sha256"] = "0" * 64
    with pytest.raises(ValueError):
        adapter.read_array(item, (5, 4))


def test_output_cannot_overlap_retained_inputs(retained):
    data, _, calls, _, report_path = retained
    with pytest.raises(ValueError, match="overlaps"):
        adapter.run(data, report_path.parent / "new-output")
    assert not calls


def test_preflight_allows_sibling_input_declaration_and_protects_evidence(retained):
    data, output, calls, _, report_path = retained
    declaration = output.parent / "analysis-inputs.json"
    adapter.prior.write(declaration, data)
    pin, checked = adapter.preflight(output, declaration)
    assert pin == adapter.prior.pin(declaration) and checked == data
    assert not output.exists() and not calls
    with pytest.raises(ValueError, match="overlaps"):
        adapter.preflight(report_path.parent / "unsafe", declaration)
    with pytest.raises(ValueError, match="overlaps"):
        adapter.preflight(declaration, declaration)


@pytest.mark.parametrize(
    "stage", ["solver", "capture", "arithmetic", "tolerance", "warm_mutation", "bad_candidate"]
)
def test_failure_preserves_prior_results_and_original_error(retained, monkeypatch, stage):
    data, output, calls, _, _ = retained
    primary, cause = RuntimeError("synthetic failure"), ValueError("original source")
    solve = adapter.iterative.solve
    if stage in ("solver", "tolerance", "warm_mutation", "bad_candidate"):

        def broken(*args, **kw):
            if stage == "solver" and kw["initial_potential"] is not None:
                raise primary from cause
            result = solve(*args, **kw)
            if stage == "tolerance":
                result = result._replace(tolerance=result.tolerance + 1)
            if stage == "warm_mutation" and kw["initial_potential"] is not None:
                kw["initial_potential"][0, 0] = 1
            if stage == "bad_candidate":
                result = result._replace(potential=np.zeros_like(result.potential))
            return result

        monkeypatch.setattr(adapter.iterative, "solve", broken)
    elif stage == "capture":
        original = adapter.saved.array_evidence

        def writer(np, out, name, value):
            if name == "numpy_cold_potential":
                raise primary from cause
            return original(np, out, name, value)

        monkeypatch.setattr(adapter.saved, "array_evidence", writer)
    else:

        def fail(*a, **kw):
            raise primary from cause

        monkeypatch.setattr(adapter, "arithmetic", fail)
    with pytest.raises((RuntimeError, ValueError, ArithmeticError)) as caught:
        adapter.run(data, output)
    if stage in ("solver", "capture", "arithmetic"):
        assert caught.value is primary and primary.__cause__ is cause
    report = json.loads((output / "failure.json").read_text())
    assert report["status"] == "failed" and calls
    assert set(report["failed_return_capture"]) >= {
        "numpy_cold." + name for name in adapter.iterative.SolveResult._fields
    }
    assert "numpy_cold" in caught.value.rectangular_raw_returns


def test_iterative_suite_declares_its_actual_inputs_and_test_producers():
    files, test = adapter.runner.suite_files("iterative_saved")
    assert test.endswith("test_rectangular_environment_iterative_saved.py")
    assert len(files) == len(set(files)) and test in files
    assert "src/cells/processes/rectangular_environment_iterative.py" in files


@pytest.mark.parametrize("which", ["rhs", "warm"])
def test_source_mutation_then_failure_retains_actual_failed_inputs(retained, monkeypatch, which):
    data, output, _, _, _ = retained
    old = adapter.iterative.solve
    primary, cause = RuntimeError("mutated then failed"), ValueError("cause")

    def fail(rhs, grid, **kw):
        if which == "warm" and kw["initial_potential"] is None:
            return old(rhs, grid, **kw)
        target = rhs if which == "rhs" else kw["initial_potential"]
        target[0, 0] = 123.0
        raise primary from cause

    monkeypatch.setattr(adapter.iterative, "solve", fail)
    with pytest.raises(RuntimeError) as caught:
        adapter.run(data, output)
    assert caught.value is primary and primary.__cause__ is cause
    report = json.loads((output / "failure.json").read_text())
    key = "rhs" if which == "rhs" else "numpy_warm_initial"
    assert np.load(report["failed_input_capture"][key]["path"], allow_pickle=False)[0, 0] == 123
    assert primary.rectangular_live_inputs[key][0, 0] == 123
    assert np.load(report["arrays"]["rhs"]["path"], allow_pickle=False)[0, 0] == 0


def test_partial_arithmetic_and_primary_survive_secondary_capture_failure(retained, monkeypatch):
    data, output, _, _, _ = retained
    primary = RuntimeError("third arithmetic row")
    arithmetic, capture = adapter.arithmetic, adapter.array_evidence
    calls = []

    def compute(*args):
        calls.append(1)
        if len(calls) == 3:
            raise primary
        return arithmetic(*args)

    def save(out, name, value):
        if name.startswith("failed_"):
            early = json.loads((out / "primary-failure.json").read_text())
            assert len(early["checks"]["numpy_cold"]) == 2
            raise ValueError("secondary persistence failed")
        return capture(out, name, value)

    monkeypatch.setattr(adapter, "arithmetic", compute)
    monkeypatch.setattr(adapter, "array_evidence", save)
    with pytest.raises(RuntimeError) as caught:
        adapter.run(data, output)
    assert caught.value is primary
    report = json.loads((output / "failure.json").read_text())
    assert len(report["checks"]["numpy_cold"]) == 2
    assert all("error" in v for v in report["failed_return_capture"].values())
    assert all("error" in v for v in report["failed_input_capture"].values())
