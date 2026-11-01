"""Small exact arithmetic and profiler controls; no real linear-algebra solve."""

import copy
import functools
import importlib.abc
import math
import sys
from contextlib import contextmanager
from fractions import Fraction
from types import SimpleNamespace

import pytest

from validation.betse import native_single_cell_poisson_spectrum as spectrum
from validation.betse.native_single_cell_poisson_spectrum import run as run_diagnostic


@pytest.fixture(autouse=True)
def software_only(monkeypatch):
    """Permit small array arithmetic, but never a real SVD, pinv or source run."""
    attempted = []

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in {"cells", "betse", "scipy", "PIL", "jax", "jaxlib"}:
                attempted.append(fullname)
                raise AssertionError("Scientific source import forbidden: " + fullname)

    def forbidden(*args, **kwargs):
        attempted.append("numerical/source entry")
        raise AssertionError("Real numerical or source entry forbidden")

    finder = Block()
    sys.meta_path.insert(0, finder)
    try:
        import numpy as np

        monkeypatch.setattr(np.linalg, "pinv", forbidden)
        monkeypatch.setattr(np.linalg, "svd", forbidden)
        # Refuse either public or implementation-module access to the real primitive.
        monkeypatch.setattr(np.linalg._linalg, "pinv", forbidden)
        monkeypatch.setattr(np.linalg._linalg, "svd", forbidden)
        for name in ("run", "saved_problem", "blas_state", "primitive_bindings"):
            monkeypatch.setattr(spectrum, name, forbidden)
        yield np
    finally:
        sys.meta_path.remove(finder)
    assert attempted == []


def graph():
    """Four-cycle negative Laplacian and its explicit rational pseudoinverse.

    The three nonconstant eigenvalues are -1/2, -1/2 and -1 at spacing two.
    No inverse, decomposition, or production stencil constructs this fixture.
    """
    a = [-2, 1, 1, 0, 1, -2, 0, 1, 1, 0, -2, 1, 0, 1, 1, -2]
    g = [-5, 1, 1, 3, 1, -5, 3, 1, 1, 3, -5, 1, 3, 1, 1, -5]
    return dict(
        shape=(2, 2),
        indices=[(0, 0), (0, 1), (1, 0), (1, 1)],
        operator=[v / 4 for v in a],
        inverse=[v / 4 for v in g],
    )


def permute(data, order):
    previous = copy.deepcopy(data)
    data["indices"] = [previous["indices"][i] for i in order]
    for key in ("operator", "inverse"):
        data[key] = [previous[key][4 * i + j] for i in order for j in order]


def rational_forcing(data):
    """Dense Fraction oracle with independently tabulated coordinate loads."""
    coordinate_loads = {
        "corner_dipole": {(0, 0): 1, (0, 1): 0, (1, 0): 0, (1, 1): -1},
        "opposing_edges": {(0, 0): 1, (0, 1): 1, (1, 0): -1, (1, 1): -1},
        "centred_coordinate": {(0, 0): -1, (0, 1): 1, (1, 0): -1, (1, 1): 1},
    }
    a = [Fraction.from_float(v) for v in data["operator"]]
    g = [Fraction.from_float(v) for v in data["inverse"]]
    result = {}
    for name, loads in coordinate_loads.items():
        b = [loads[tuple(pair)] for pair in data["indices"]]
        x = [sum(g[4 * i + j] * b[j] for j in range(4)) for i in range(4)]
        residual = [sum(a[4 * i + j] * x[j] for j in range(4)) - b[i] for i in range(4)]
        result[name] = dict(rhs=b, solution=x, residual=residual)
    return result


@pytest.mark.parametrize("order", [(0, 1, 2, 3), (3, 0, 2, 1)])
@pytest.mark.parametrize(
    "contamination", ["none", "uniform", "constant_output", "constant_input", "mean_free"]
)
def test_forcing_matches_fraction_oracle_and_separates_nullspace_contamination(
    order, contamination
):
    data = graph()
    v = [1, -1, 1, -1]
    correction = {
        "none": [0.0] * 16,
        "uniform": [0.5] * 16,
        "constant_output": [v[j] / 8 for i in range(4) for j in range(4)],
        "constant_input": [v[i] / 8 for i in range(4) for j in range(4)],
        "mean_free": [v[i] * v[j] / 8 for i in range(4) for j in range(4)],
    }[contamination]
    data["inverse"] = [g + c for g, c in zip(data["inverse"], correction, strict=True)]
    permute(data, order)
    before = copy.deepcopy(data)
    report = spectrum.forcing_report(**data)
    expected = rational_forcing(data)
    assert list(report) == list(expected)
    for name, oracle in expected.items():
        actual = report[name]
        assert actual["rhs"] == oracle["rhs"]
        assert sum(actual["rhs"]) == actual["exact_rhs_sum"] == 0
        assert list(map(Fraction, actual["solution"])) == oracle["solution"]
        assert list(map(Fraction, actual["residual"])) == oracle["residual"]
        assert Fraction(actual["residual_max_abs"]) == max(map(abs, oracle["residual"]))
        assert Fraction(actual["solution_sum"]) == sum(oracle["solution"])
        assert actual["inexact"] is False
    assert data == before
    if contamination == "mean_free":
        assert Fraction(report["centred_coordinate"]["residual_max_abs"]) == Fraction(1, 4)
    else:
        assert all(Fraction(row["residual_max_abs"]) == 0 for row in report.values())
    if contamination == "constant_output":
        assert Fraction(report["centred_coordinate"]["solution_sum"]) == -2
    else:
        assert all(Fraction(row["solution_sum"]) == 0 for row in report.values())


def test_json_coordinate_pairs_preserve_the_same_forcing():
    data = graph()
    expected = spectrum.forcing_report(**data)
    data["indices"] = [list(pair) for pair in data["indices"]]
    assert spectrum.forcing_report(**data) == expected


@pytest.mark.parametrize("coefficient,order", [(0.25, (0, 1, 2, 3)), (0.5, (3, 0, 2, 1))])
def test_exact_connected_stencil_proves_rank_without_numerical_rank(coefficient, order):
    data = graph()
    data["operator"] = [v * coefficient / 0.25 for v in data["operator"]]
    permute(data, order)
    before = copy.deepcopy(data)
    proof = spectrum.connected_flux_operator(data["operator"], data["shape"], data["indices"])
    assert proof == dict(
        points=4, exact_rank=3, edge_weight=coefficient, nullspace="span of all-ones"
    )
    assert data == before


@pytest.mark.parametrize(
    "change",
    ["missing", "extra", "zero", "negative", "diagonal", "asymmetric", "off_stencil", "split"],
)
def test_incomplete_or_nonmatching_stencil_cannot_issue_exact_rank(change):
    data = graph()
    if change == "missing":
        data["operator"].pop()
    elif change == "extra":
        data["operator"].append(0.0)
    elif change == "zero":
        data["operator"] = [0.0] * 16
    elif change == "negative":
        data["operator"] = [-v for v in data["operator"]]
    elif change == "diagonal":
        data["operator"][0] = math.nextafter(data["operator"][0], 0.0)
    elif change == "asymmetric":
        data["operator"][4] = math.nextafter(data["operator"][4], 1.0)
    elif change == "off_stencil":
        data["operator"][3] = math.ulp(0.0)
    else:
        # A legitimate disconnected graph has rank two, not the claimed grid rank three.
        data["operator"] = [v / 4 for v in [-1, 1, 0, 0, 1, -1, 0, 0, 0, 0, -1, 1, 0, 0, 1, -1]]
    with pytest.raises(ValueError):
        spectrum.connected_flux_operator(data["operator"], data["shape"], data["indices"])


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 1, True])
def test_rank_requires_finite_binary64_coefficients(value):
    data = graph()
    data["operator"][0] = value
    with pytest.raises(ValueError, match="finite binary64"):
        spectrum.connected_flux_operator(data["operator"], data["shape"], data["indices"])


@pytest.mark.parametrize("change", ["duplicate", "missing", "outside", "bool", "mismapped"])
def test_rank_mapping_is_complete_unique_and_matches_matrix_axes(change):
    data = graph()
    if change == "missing":
        data["indices"].pop()
    elif change == "mismapped":
        data["indices"][0], data["indices"][1] = data["indices"][1], data["indices"][0]
    else:
        data["indices"][0] = {"duplicate": (0, 1), "outside": (2, 0), "bool": (False, 0)}[change]
    with pytest.raises(ValueError):
        spectrum.connected_flux_operator(data["operator"], data["shape"], data["indices"])


@pytest.mark.parametrize("shape", [(1, 4), (2, 1), (True, 2), (2.0, 2), (26, 25)])
def test_unsupported_grid_does_not_receive_a_rank_claim(shape):
    data = graph()
    with pytest.raises(ValueError, match="rectangular grid"):
        spectrum.connected_flux_operator(data["operator"], shape, data["indices"])


@pytest.mark.parametrize(
    "change", ["short_operator", "extra_inverse", "nan_operator", "inf_inverse", "bool_inverse"]
)
def test_forcing_refuses_incomplete_or_nonfinite_inputs(change):
    data = graph()
    if change == "short_operator":
        data["operator"].pop()
    elif change == "extra_inverse":
        data["inverse"].append(0.0)
    else:
        name, value = {
            "nan_operator": ("operator", float("nan")),
            "inf_inverse": ("inverse", float("inf")),
            "bool_inverse": ("inverse", True),
        }[change]
        data[name][0] = value
    with pytest.raises(ValueError):
        spectrum.forcing_report(**data)


def dispatch(function):
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        return function(*args, **kwargs)

    return wrapped


def synthetic_primitives(np, mode="normal", primary=None, cause=None, copy_error=None):
    """Actual Python profile events, with the local names used by NumPy's bodies."""
    state = dict(svd_arguments=[], returned_factors=[])
    output = np.array([[0.0, 0.5], [0.25, 0.0]], dtype="<f8")

    class Uncopyable:
        def copy(self, *, order):
            assert order == "K"
            raise copy_error

    def svd(a, full_matrices=True, compute_uv=True, hermitian=False):
        state["svd_arguments"].append((a, full_matrices, compute_uv, hermitian))
        if mode == "svd_error":
            raise primary from cause
        u = np.array([[1.0, 0.0], [0.0, 1.0]], dtype="<f8")
        s = np.array([4.0, 2.0], dtype="<f8")
        vt = np.array([[0.0, 1.0], [1.0, 0.0]], dtype="<f8")
        if copy_error is not None:
            vt = Uncopyable()
        state["returned_factors"].append((u, s, vt))
        if mode == "missing_svd_return":
            return None
        return u, s, vt

    observed_svd = dispatch(svd)

    def pinv(a, rcond=0.25):
        state["pinv_argument"] = a
        rcond = np.array(rcond, dtype="<f8")
        if mode == "missing_svd_entry":
            factors = None
        else:
            factors = observed_svd(a, full_matrices=False, compute_uv=True, hermitian=False)
        if mode == "repeated_svd":
            observed_svd(a, full_matrices=False, compute_uv=True, hermitian=False)
        if factors is None:
            u, s, vt = None, np.array([4.0, 2.0]), None
        else:
            u, s, vt = factors
        cutoff = np.array([1.0], dtype="<f8")
        large = np.array([True, True])
        # Deliberately mutate the exact returned SVD array after its profile return.
        s[:] = [0.25, 0.5]
        state["pinv_locals"] = dict(u=u, vt=vt, s=s, cutoff=cutoff, large=large, rcond=rcond)
        if mode == "pinv_error":
            raise primary from cause
        if mode == "missing_pinv_return":
            return None
        return output

    facade = SimpleNamespace(linalg=SimpleNamespace(pinv=dispatch(pinv), svd=observed_svd))
    state["output"] = output
    return facade, state


def array_identity(array):
    return array.dtype.str, array.shape, array.strides, array.tobytes(order="C")


@contextmanager
def chained_profile(observer):
    outer = sys.getprofile()

    def previous(frame, event, argument):
        if outer is not None:
            outer(frame, event, argument)
        observer(frame, event, argument)

    sys.setprofile(previous)
    try:
        yield previous
    finally:
        sys.setprofile(outer)


def test_profile_copies_singular_values_before_in_place_reciprocal_mutation(software_only):
    np = software_only
    facade, state = synthetic_primitives(np)
    a = np.array([[0.0, 4.0], [2.0, 0.0]], dtype="<f8")
    before = array_identity(a)
    previous = sys.getprofile()
    result, captured = spectrum.capture_pinv(facade, a)
    assert sys.getprofile() is previous
    assert result is state["output"]
    assert state["pinv_argument"] is a and state["svd_arguments"][0][0] is a
    assert state["svd_arguments"][0][1:] == (False, True, False)
    assert captured["entries"] == ["pinv", "svd"] and captured["capture_errors"] == []
    assert captured["raw_returns"]["pinv"] is result
    assert all(
        actual is original
        for actual, original in zip(
            captured["raw_returns"]["svd"], state["returned_factors"][0], strict=True
        )
    )
    assert captured["svd"]["s"].tolist() == [4.0, 2.0]
    assert state["returned_factors"][0][1].tolist() == [0.25, 0.5]
    assert captured["pinv"]["s"].tolist() == [0.25, 0.5]
    assert captured["pinv"]["cutoff"].tolist() == [1.0]
    assert captured["pinv"]["large"].tolist() == [True, True]
    assert captured["pinv"]["rcond"].shape == ()
    assert captured["pinv"]["rcond"].item() == 0.25
    assert captured["svd"]["full_matrices"] is False
    assert captured["svd"]["compute_uv"] is True
    assert captured["svd"]["hermitian"] is False
    for key, original in zip(("u", "s", "vt"), state["returned_factors"][0], strict=True):
        assert not np.shares_memory(captured["svd"][key], original)
    assert array_identity(captured["svd"]["input"]) == before == array_identity(a)
    for key in ("s", "cutoff", "large", "rcond"):
        original = state["pinv_locals"][key]
        assert array_identity(captured["pinv"][key]) == array_identity(original)
        assert not np.shares_memory(captured["pinv"][key], original)


@pytest.mark.parametrize("mode", ["normal", "svd_error", "pinv_error"])
def test_original_exception_cause_and_chained_profiler_are_preserved(software_only, mode):
    np = software_only
    primary, cause = RuntimeError("synthetic primitive failure"), KeyError("original cause")
    facade, state = synthetic_primitives(np, mode, primary, cause)
    codes = {
        facade.linalg.pinv.__wrapped__.__code__: "pinv",
        facade.linalg.svd.__wrapped__.__code__: "svd",
    }
    observed = []

    def observe(frame, event, argument):
        if frame.f_code in codes:
            observed.append((codes[frame.f_code], event, argument))

    a = np.array([[0.0, 4.0], [2.0, 0.0]], dtype="<f8")
    with chained_profile(observe) as previous:
        if mode == "normal":
            result, captured = spectrum.capture_pinv(facade, a)
            assert result is state["output"]
        else:
            with pytest.raises(RuntimeError) as caught:
                spectrum.capture_pinv(facade, a)
            assert caught.value is primary and primary.__cause__ is cause
            captured = primary.spectrum_capture
            assert ("svd" in captured) is (mode == "pinv_error")
            assert "pinv" not in captured
        assert sys.getprofile() is previous
    assert captured["entries"] == ["pinv", "svd"]
    assert [name for name, event, _ in observed if event == "call"] == ["pinv", "svd"]
    assert [name for name, event, _ in observed if event == "return"] == ["svd", "pinv"]


@pytest.mark.parametrize("missing", ["svd", "pinv"])
def test_missing_primitive_return_retains_partial_observations(software_only, missing):
    np = software_only
    facade, _ = synthetic_primitives(np, "missing_" + missing + "_return")
    previous = sys.getprofile()
    with pytest.raises(ValueError, match="Incomplete pinv/SVD return") as caught:
        spectrum.capture_pinv(facade, np.array([[1.0, 0.0], [0.0, 1.0]]))
    assert sys.getprofile() is previous
    captured = caught.value.spectrum_capture
    assert captured["entries"] == ["pinv", "svd"]
    assert captured["capture_errors"] == [] and missing not in captured
    assert ("pinv" if missing == "svd" else "svd") in captured


def test_repeated_svd_return_is_an_error_and_keeps_first_complete_factors(software_only):
    np = software_only
    facade, state = synthetic_primitives(np, "repeated_svd")
    previous = sys.getprofile()
    with pytest.raises(ValueError, match="Incomplete or repeated") as caught:
        spectrum.capture_pinv(facade, np.array([[1.0, 0.0], [0.0, 1.0]]))
    assert sys.getprofile() is previous
    captured = caught.value.spectrum_capture
    assert captured["entries"] == ["pinv", "svd", "svd"]
    assert captured["svd"]["s"].tolist() == [4.0, 2.0]
    assert captured["raw_returns"]["svd"][1] is state["returned_factors"][-1][1]
    assert len(captured["capture_errors"]) == 1
    root = captured["capture_errors"][0]["nodes"][0]
    assert root["type"] == "builtins.ValueError"
    assert root["message"] == "Repeated numerical primitive return"


def test_absent_svd_entry_does_not_receive_a_complete_capture(software_only):
    np = software_only
    facade, _ = synthetic_primitives(np, "missing_svd_entry")
    previous = sys.getprofile()
    with pytest.raises(ValueError, match="Incomplete or repeated") as caught:
        spectrum.capture_pinv(facade, np.array([[1.0, 0.0], [0.0, 1.0]]))
    assert sys.getprofile() is previous
    assert caught.value.spectrum_capture["entries"] == ["pinv"]
    assert "svd" not in caught.value.spectrum_capture


@pytest.mark.parametrize("source_fails", [False, True])
def test_copy_error_is_retained_separately_from_primary_primitive_error(
    software_only, source_fails
):
    np = software_only
    primary, cause = RuntimeError("source failed later"), LookupError("source cause")
    secondary = OSError("observer copy failed")
    mode = "pinv_error" if source_fails else "normal"
    facade, state = synthetic_primitives(np, mode, primary, cause, secondary)
    expected = RuntimeError if source_fails else ValueError
    previous = sys.getprofile()
    with pytest.raises(expected) as caught:
        spectrum.capture_pinv(facade, np.array([[1.0, 0.0], [0.0, 1.0]]))
    assert sys.getprofile() is previous
    if source_fails:
        assert caught.value is primary and primary.__cause__ is cause
    captured = caught.value.spectrum_capture
    errors = captured["capture_errors"]
    assert len(errors) == 1
    assert errors[0]["stage"] == "svd.vt"
    assert errors[0]["error"]["nodes"][0]["type"] == "builtins.OSError"
    assert errors[0]["error"]["nodes"][0]["message"] == "observer copy failed"
    # The failed middle copy loses neither earlier factors nor the later input copy.
    assert captured["svd"]["u"].tolist() == [[1.0, 0.0], [0.0, 1.0]]
    assert captured["svd"]["s"].tolist() == [4.0, 2.0]
    assert captured["svd"]["input"].tolist() == [[1.0, 0.0], [0.0, 1.0]]
    assert "vt" not in captured["svd"]
    assert captured["raw_returns"]["svd"][2] is state["returned_factors"][0][2]


@pytest.mark.parametrize("event_name", ["call", "return"])
def test_previous_profiler_failure_cannot_be_silently_accepted(software_only, event_name):
    np = software_only
    facade, _ = synthetic_primitives(np)
    primary = OSError("existing profiler refuses entry")

    def observe(frame, event, argument):
        if frame.f_code is facade.linalg.svd.__wrapped__.__code__ and event == event_name:
            raise primary

    with chained_profile(observe) as previous:
        with pytest.raises(OSError) as caught:
            spectrum.capture_pinv(facade, np.array([[1.0, 0.0], [0.0, 1.0]]))
        assert caught.value is primary
        assert sys.getprofile() is previous


def test_previous_profiler_unwind_error_cannot_replace_original_source_error(software_only):
    np = software_only
    primary, cause = RuntimeError("original source error"), KeyError("original source cause")
    secondary = OSError("previous profiler unwind failed")
    facade, _ = synthetic_primitives(np, "svd_error", primary, cause)

    def observe(frame, event, argument):
        if frame.f_code is facade.linalg.svd.__wrapped__.__code__ and event == "return":
            raise secondary

    with chained_profile(observe) as previous:
        with pytest.raises(RuntimeError) as caught:
            spectrum.capture_pinv(facade, np.array([[1.0, 0.0], [0.0, 1.0]]))
        assert caught.value is primary and primary.__cause__ is cause
        assert sys.getprofile() is previous
    records = primary.spectrum_capture["capture_errors"]
    assert any(
        record["stage"] == "prior_profiler_unwind"
        and record["error"]["nodes"][0]["type"] == "builtins.OSError"
        and record["error"]["nodes"][0]["message"] == str(secondary)
        for record in records
    )


@pytest.mark.parametrize(
    "mode", ["strict_cutoff", "selected_rank", "empty", "zero_singular", "all_modes"]
)
def test_small_analytic_reconstruction_uses_mask_without_mutating_factors(software_only, mode):
    np = software_only
    # Signed permutations make both transposes observable; no decomposition is needed.
    u = np.array([[0.0, 1.0, 0.0], [0.0, 0.0, -1.0], [1.0, 0.0, 0.0]], dtype="<f8")
    vt = np.array([[0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype="<f8")
    s = np.array([4.0, 2.0, 0.0 if mode == "zero_singular" else 1.0], dtype="<f8")
    if mode == "strict_cutoff":
        keep = s > 2.0
        assert keep.tolist() == [True, False, False]
    elif mode == "all_modes":
        keep = np.array([True, True, True])
    else:
        keep = np.array([False, False, False] if mode == "empty" else [True, True, False])
    before = [array_identity(v) for v in (u, s, vt, keep)]
    for array in (u, s, vt, keep):
        array.flags.writeable = False
    with np.errstate(divide="raise", invalid="raise"):
        actual = spectrum.reconstruct(np, u, s, vt, keep)
    expected = [[0.0, 0.0, 0.0] for _ in range(3)]
    if mode != "empty":
        expected[2][2] = 0.25
    if mode in ("selected_rank", "zero_singular", "all_modes"):
        expected[0][0] = 0.5
    if mode == "all_modes":
        expected[1][1] = -1.0
    assert actual.tolist() == expected
    assert [array_identity(v) for v in (u, s, vt, keep)] == before
    assert all(not v.flags.writeable for v in (u, s, vt, keep))


def test_selected_mask_can_keep_a_nonleading_mode_without_implicit_rank_policy(software_only):
    np = software_only
    identity = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    s = np.array([4.0, 2.0, 1.0])
    keep = np.array([False, True, True])
    actual = spectrum.reconstruct(np, identity, s, identity, keep)
    assert actual.tolist() == [[0.0, 0.0, 0.0], [0.0, 0.5, 0.0], [0.0, 0.0, 1.0]]
    assert s.tolist() == [4.0, 2.0, 1.0] and keep.tolist() == [False, True, True]


def test_failed_capture_retains_svd_flags_entry_metadata_and_available_arrays(
    software_only, monkeypatch, tmp_path
):
    np = software_only
    primary = RuntimeError("synthetic pinv failure")
    facade, state = synthetic_primitives(
        np,
        "pinv_error",
        primary,
        KeyError("synthetic cause"),
        OSError("synthetic vt copy failure"),
    )
    with pytest.raises(RuntimeError) as caught:
        spectrum.capture_pinv(facade, np.array([[1.0, 0.0], [0.0, 1.0]]))
    assert caught.value is primary
    captured = primary.spectrum_capture
    recorded = {}

    def record_array(numpy, output, name, value):
        assert numpy is np and output == tmp_path
        recorded[name] = value
        return dict(dtype=value.dtype.str, shape=list(value.shape), raw_hex=value.tobytes().hex())

    monkeypatch.setattr(spectrum, "array_evidence", record_array)
    arrays = {}
    metadata = spectrum.captured_failure(np, tmp_path, captured, arrays)
    full_matrices, compute_uv, hermitian = state["svd_arguments"][0][1:]
    assert metadata == dict(
        entries=["pinv", "svd"],
        capture_errors=captured["capture_errors"],
        svd_flags=dict(full_matrices=full_matrices, compute_uv=compute_uv, hermitian=hermitian),
        persistence_errors=[],
    )
    assert metadata["svd_flags"] == dict(full_matrices=False, compute_uv=True, hermitian=False)
    assert (
        list(arrays)
        == list(recorded)
        == [
            "failed_svd_u",
            "failed_svd_s",
            "failed_svd_input",
            "failed_raw_svd_return_0",
            "failed_raw_svd_return_1",
        ]
    )
    assert recorded["failed_svd_s"] is captured["svd"]["s"]
    assert recorded["failed_raw_svd_return_1"] is captured["raw_returns"]["svd"][1]
    assert recorded["failed_svd_s"].tolist() == [4.0, 2.0]
    assert recorded["failed_raw_svd_return_1"].tolist() == [0.25, 0.5]
    assert arrays["failed_svd_s"]["raw_hex"] != arrays["failed_raw_svd_return_1"]["raw_hex"]


def test_failure_writer_and_stderr_failures_cannot_replace_pre_numerical_error(
    monkeypatch, tmp_path
):
    output = tmp_path / "attempt"
    baseline = tmp_path / "parent" / "baseline.json"
    primary, cause = RuntimeError("original binding failure"), LookupError("original binding cause")
    persistence = OSError("cannot persist failure")
    stderr_error = RuntimeError("cannot print persistence failure")
    events, retained = [], []

    def fail_before_numerics(path, sha256):
        assert path == baseline and sha256 == "0" * 64
        events.append("saved_problem")
        raise primary from cause

    def fail_write(path, status):
        assert path == output / "failure.json"
        events.append("failure_write")
        retained.append(copy.deepcopy(status))
        raise persistence

    def fail_print(error, *, file):
        assert error is persistence and file is sys.stderr
        events.append("stderr_write")
        raise stderr_error

    monkeypatch.setattr(spectrum.prior, "output_path", lambda unused: output)
    monkeypatch.setattr(spectrum, "saved_problem", fail_before_numerics)
    monkeypatch.setattr(spectrum.prior, "write", fail_write)
    monkeypatch.setattr(spectrum.traceback, "print_exception", fail_print)
    # This retained function alias reaches only the injected pre-numerical refusal.
    # The autouse fixture still blocks both real primitives and numerical bindings.
    with pytest.raises(RuntimeError) as caught:
        run_diagnostic(baseline, "0" * 64, "ignored-output-path", [])
    assert caught.value is primary and primary.__cause__ is cause
    assert primary.spectrum_failure_persistence_error is persistence
    assert primary.spectrum_stderr_error is stderr_error
    assert events == ["saved_problem", "failure_write", "stderr_write"]
    assert len(retained) == 1 and retained[0]["status"] == "failed"
    assert retained[0]["work"] == [] and retained[0]["arrays"] == {}
    error = retained[0]["error"]
    root = error["nodes"][error["root"]]
    assert root["type"] == "builtins.RuntimeError" and root["message"] == str(primary)
    original_cause = error["nodes"][root["cause"]]
    assert original_cause["type"] == "builtins.LookupError"
    assert original_cause["message"] == str(cause)
    assert output.is_dir() and list(output.iterdir()) == []
