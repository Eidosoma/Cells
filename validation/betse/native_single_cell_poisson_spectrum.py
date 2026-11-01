"""Diagnose the saved flux inverse using the actual NumPy pinv SVD branch.

This is a new numerical calculation on retained matrices, not a Cells/BETSE
trajectory or a solver repair. The default pinv call is unchanged. A separate
rank-n-1 reconstruction is an explicitly labelled diagnostic counterfactual.
"""

import argparse
import ctypes
import hashlib
import math
import sys
import traceback
from decimal import Decimal, Inexact, localcontext
from pathlib import Path

from validation.betse import native_single_cell_poisson_algebra as algebra
from validation.betse import native_single_cell_prefix_compare as compare
from validation.betse import native_single_cell_prefix_payload as payload
from validation.betse import native_single_cell_prefix_qualification as prior

KIND = "cells.saved_flux_pinv_spectrum_diagnostic@1"
NO_CREDIT = dict(
    numerical_acceptance=False,
    physical_admission=False,
    independent_biological_cases=0,
    model_source_executions=0,
    production_repair=False,
    new_acceptance_tolerance=None,
)


def saved_problem(baseline, expected_sha256):
    """Bind to the reviewed exact-arithmetic report and every original sidecar."""
    baseline = Path(baseline).absolute()
    if ".." in baseline.parts or any(p.is_symlink() for p in (baseline, *baseline.parents)):
        raise ValueError("Require an unaliased canonical baseline")
    bound = prior.pin(baseline)
    if bound["sha256"] != expected_sha256:
        raise ValueError("Changed exact-arithmetic baseline")
    report = prior.read(baseline)
    if (
        report.get("kind") != algebra.CONSTANT_KIND
        or report.get("numerical_acceptance") is not False
        or len(report.get("operators", [])) != 1
        or report["operators"][0].get("boundary") != "flux"
        or report["operators"][0].get("exact_arithmetic_inexact_flag") is not False
    ):
        raise ValueError("Require the complete exact saved-flux baseline")
    pins = report["inputs"]
    prior.verify_pins(pins)
    native = [p for p in pins if Path(p["path"]).name == "native.json"]
    if len(native) != 1:
        raise ValueError("Require one retained original-source input")
    raw = payload.read(native[0]["path"])
    if (
        raw.get("status") != "source_completed"
        or raw.get("stop_after") != "lapENV_P_inv"
        or raw.get("source_error", True) is not None
        or raw.get("capture_error", True) is not None
    ):
        raise ValueError("Require completed source evidence")
    parent = compare._Cache(raw["environment"]["cache"], "saved.environment", False)
    matrix_shape = compare._poisson_shape(parent.tree)
    grid = compare._fields(compare._fields(parent.tree, "environment")["grid"], "grid")
    shape = tuple(v["value"] for v in grid["cents_shape"]["items"])
    mapping = algebra._numbers(
        grid["map_ij2k_cents"], kind="iu", shape=(matrix_shape[0], 2), label="mapping"
    )
    indices = list(zip(mapping[::2], mapping[1::2], strict=True))
    algebra._grid(shape, indices)
    cache = compare._Cache(
        raw["poisson"]["cache"]["outputs"], "saved.outputs", False, poisson_shape=matrix_shape
    )
    differences = []
    outputs = compare._poisson_outputs(cache.tree, "saved.outputs", 2, matrix_shape, differences)
    if differences:
        raise ValueError("Changed operator/helper associations")
    a, g = outputs["results"]["items"][1]["items"][1]["items"]
    for name, node in (("operator", a), ("inverse", g)):
        if node["sha256"] != report["operators"][0]["source_byte_hashes"][name]:
            raise ValueError("Baseline does not bind the selected flux " + name)
        # The original input is a contiguous real binary64 square matrix.
        if node["layout"]["dtype"] != "<f8" or node["layout"]["shape"] != list(matrix_shape):
            raise ValueError("Unsupported original matrix representation")
    if (
        a["layout"]["strides_bytes"] != [8 * matrix_shape[0], 8]
        or a["layout"]["C_contiguous"] is not True
    ):
        raise ValueError("Require the original contiguous operator layout")
    return dict(
        shape=shape,
        indices=indices,
        operator=algebra._numbers(a, kind="f", shape=matrix_shape, label="operator"),
        inverse=algebra._numbers(g, kind="f", shape=matrix_shape, label="inverse"),
        layouts=dict(operator=a["layout"], inverse=g["layout"]),
        inputs=[bound, *pins],
    )


def connected_flux_operator(operator, shape, indices):
    """Exact stored coefficient proof of a connected scaled graph Laplacian.

    Positive common edge weight and these exact rows establish rank n-1 over
    the reals. A numerical rank estimate is not used to justify that rank.
    """
    stencil = algebra._stencil(shape, indices, "flux")
    n = len(stencil)
    if len(operator) != n * n:
        raise ValueError("Incomplete operator")
    for v in operator:
        algebra._finite(v, "operator")
    edge = next(operator[i * n + j] for i, row in enumerate(stencil) for j in row if i != j)
    if edge <= 0:
        raise ValueError("Require positive common flux edge weight")
    from fractions import Fraction

    scale = Fraction.from_float(edge)
    for i, row in enumerate(stencil):
        for j in range(n):
            if Fraction.from_float(operator[i * n + j]) != row.get(j, 0) * scale:
                raise ValueError("Stored operator is not the exact connected flux stencil")
    return dict(points=n, exact_rank=n - 1, edge_weight=edge, nullspace="span of all-ones")


def capture_pinv(np, operator):
    """Observe one unchanged pinv call; preserve singular values before mutation.

    Profiling is local to this thread and always restored. Observer errors are
    retained separately and never replace a primary numerical exception.
    """
    pinv, svd = np.linalg.pinv, np.linalg.svd
    pinv_code, svd_code = pinv.__wrapped__.__code__, svd.__wrapped__.__code__
    previous = sys.getprofile()
    captured = {"entries": [], "capture_errors": [], "raw_returns": {}}

    def observe(frame, event, argument):
        if frame.f_code in (pinv_code, svd_code) and event == "return" and argument is not None:
            captured["raw_returns"]["pinv" if frame.f_code is pinv_code else "svd"] = argument
        if previous is not None:
            try:
                previous(frame, event, argument)
            except BaseException as error:
                if frame.f_code in (pinv_code, svd_code) and event == "return" and argument is None:
                    # These primitives never successfully return None. Let the
                    # original exception unwind; retain the observer failure
                    # separately. Call-entry guards still reject immediately.
                    captured["capture_errors"].append(
                        dict(stage="prior_profiler_unwind", error=prior.exception_record(error))
                    )
                    return
                raise
        if frame.f_code not in (pinv_code, svd_code):
            return
        name = "pinv" if frame.f_code is pinv_code else "svd"
        try:
            if event == "call":
                captured["entries"].append(name)
            elif event == "return" and argument is not None:
                if name in captured:
                    raise ValueError("Repeated numerical primitive return")
                local = frame.f_locals
                if name == "svd":
                    captured[name] = dict(
                        full_matrices=local["full_matrices"],
                        compute_uv=local["compute_uv"],
                        hermitian=local["hermitian"],
                    )
                    values = dict(u=argument[0], s=argument[1], vt=argument[2], input=local["a"])
                else:
                    captured[name] = {}
                    values = {k: local[k] for k in ("cutoff", "large", "s", "rcond")}
                for key, value in values.items():
                    try:
                        captured[name][key] = value.copy(order="K")
                    except BaseException as error:
                        captured["capture_errors"].append(
                            dict(stage=name + "." + key, error=prior.exception_record(error))
                        )
        except Exception as error:
            captured["capture_errors"].append(prior.exception_record(error))

    sys.setprofile(observe)
    try:
        result = pinv(operator)
    except BaseException as error:
        error.spectrum_capture = captured
        raise
    finally:
        sys.setprofile(previous)
    if captured["capture_errors"] or captured["entries"] != ["pinv", "svd"]:
        error = ValueError("Incomplete or repeated pinv/SVD observation")
        error.spectrum_capture = captured
        raise error
    if set(captured) != {"entries", "capture_errors", "raw_returns", "pinv", "svd"}:
        error = ValueError("Incomplete pinv/SVD return")
        error.spectrum_capture = captured
        raise error
    return result, captured


def reconstruct(np, u, s, vt, keep):
    """Same operation order as pinned NumPy, on separate diagnostic arrays."""
    reciprocal = s.copy()
    np.divide(1, reciprocal, where=keep, out=reciprocal)
    reciprocal[~keep] = 0
    return np.matmul(np.transpose(vt), np.multiply(reciprocal[:, None], np.transpose(u)))


def smallest_pair(operator, u, sigma, v):
    """Binary64/compensated-sum diagnostics, not an exact spectral proof."""
    n = len(u)
    if len(v) != n or len(operator) != n * n:
        raise ValueError("Incomplete singular pair")
    left, right = [], []
    norm_a = 0.0
    for i in range(n):
        row = operator[i * n : (i + 1) * n]
        left.append(math.fsum([*(a * b for a, b in zip(row, v, strict=True)), -sigma * u[i]]))
        right.append(math.fsum([*(operator[j * n + i] * u[j] for j in range(n)), -sigma * v[i]]))
        norm_a = max(norm_a, math.fsum(map(abs, row)))
    return dict(
        left_residual_max_abs=max(map(abs, left)),
        right_residual_max_abs=max(map(abs, right)),
        operator_norm_inf=norm_a,
        left_vector_range=[min(u), max(u)],
        right_vector_range=[min(v), max(v)],
        accumulation=(
            "binary64 products and math.fsum; diagnostic, not exact residual certification"
        ),
    )


def forcing_report(operator, inverse, shape, indices):
    """Exact Decimal responses to three specified, exactly zero-sum integer loads.

    These are diagnostic probes of the same matrix, not independent cases or
    physiological forcing. Their solutions have no production authority.
    """
    n = math.prod(shape)
    if len(operator) != n * n or len(inverse) != n * n:
        raise ValueError("Incomplete forcing matrices")
    for v in (*operator, *inverse):
        algebra._finite(v, "forcing matrix")
    algebra._grid(shape, indices)
    loads = dict(
        corner_dipole=[
            int(tuple(p) == (0, 0)) - int(tuple(p) == (shape[0] - 1, shape[1] - 1)) for p in indices
        ],
        opposing_edges=[int(p[0] == 0) - int(p[0] == shape[0] - 1) for p in indices],
        centred_coordinate=[2 * p[1] - (shape[1] - 1) for p in indices],
    )
    decimal_a = [Decimal.from_float(v) for v in operator]
    g = [Decimal.from_float(v) for v in inverse]
    precision = algebra._exact_precision(decimal_a, g, n) + 32
    rows = [[(j, decimal_a[i * n + j]) for j in range(n) if operator[i * n + j]] for i in range(n)]
    result = {}
    with localcontext() as context:
        context.prec = precision
        context.traps[Inexact] = True
        for name, b in loads.items():
            assert sum(b) == 0 and any(b)
            x = [sum((g[i * n + j] * b[j] for j in range(n) if b[j]), Decimal(0)) for i in range(n)]
            residual = [
                sum((a * x[j] for j, a in row), Decimal(0)) - b[i] for i, row in enumerate(rows)
            ]
            result[name] = dict(
                rhs=b,
                exact_rhs_sum=0,
                solution=[str(v) for v in x],
                residual=[str(v) for v in residual],
                residual_max_abs=str(max(map(abs, residual))),
                solution_sum=str(sum(x, Decimal(0))),
                precision=precision,
                inexact=False,
            )
    return result


def array_evidence(np, output, name, value):
    if type(value) is not np.ndarray or value.dtype.kind not in "fb" or value.size > 625**2:
        raise ValueError("Unexpected diagnostic array")
    path = output / (name + ".npy")
    with path.open("xb") as stream:
        np.save(stream, value, allow_pickle=False)
    loaded = np.load(path, allow_pickle=False)
    if (
        loaded.dtype != value.dtype
        or loaded.shape != value.shape
        or loaded.tobytes() != value.tobytes()
    ):
        raise ValueError("Diagnostic array roundtrip changed")
    return dict(
        **prior.pin(path),
        shape=list(value.shape),
        dtype=value.dtype.str,
        raw_c_sha256=hashlib.sha256(value.tobytes(order="C")).hexdigest(),
    )


def blas_state(np):
    libraries = list(
        (Path(np.__file__).parent.parent / "numpy.libs").glob("libscipy_openblas64_*.so")
    )
    if len(libraries) != 1:
        raise ValueError("Require the declared NumPy OpenBLAS runtime")
    path = libraries[0]
    library = ctypes.CDLL(str(path))
    threads = library.scipy_openblas_get_num_threads64_
    threads.argtypes, threads.restype = [], ctypes.c_int
    config = library.scipy_openblas_get_config64_
    config.argtypes, config.restype = [], ctypes.c_char_p
    count = threads()
    if count != 1:
        raise ValueError("Diagnostic requires one BLAS thread")
    return dict(
        library=prior.pin(path),
        threads=count,
        configuration=config().decode(),
        old_run_library_hash_independently_bound=False,
    )


def loaded_libraries():
    """Prospective identity of mapped ELF libraries, including BLAS dependencies."""
    paths = set()
    for line in Path("/proc/self/maps").read_text().splitlines():
        parts = line.split(maxsplit=5)
        if len(parts) == 6 and parts[5].startswith("/") and ".so" in parts[5]:
            path = Path(parts[5])
            if not path.is_file():
                raise ValueError("Unavailable mapped numerical library")
            paths.add(path.resolve())
    return [prior.pin(path) for path in sorted(paths)]


def primitive_bindings(np, pins):
    """Bind actual dispatch to the reviewed real binary64 NumPy implementation."""
    from numpy.linalg import _linalg

    table = {row["path"]: row["sha256"] for row in pins}
    for path in (
        np.__file__,
        _linalg.__file__,
        np._core._multiarray_umath.__file__,
        _linalg._umath_linalg.__file__,
    ):
        row = prior.pin(path)
        if table.get(row["path"]) != row["sha256"]:
            raise ValueError("Unbound NumPy primitive producer")
    if (
        np.__version__ != "2.5.3"
        or np.linalg.pinv is not _linalg.pinv
        or np.linalg.svd is not _linalg.svd
        or _linalg.pinv.__wrapped__.__globals__ is not vars(_linalg)
        or _linalg.svd.__wrapped__.__globals__ is not vars(_linalg)
        or _linalg.pinv.__wrapped__.__globals__["svd"] is not np.linalg.svd
    ):
        raise ValueError("Unexpected NumPy primitive dispatch")
    return tuple(
        (f, f.__wrapped__, f.__wrapped__.__code__) for f in (np.linalg.pinv, np.linalg.svd)
    )


def captured_failure(np, output, captured, arrays):
    """Save every available numeric observation separately from the primary error."""
    metadata = {k: captured.get(k) for k in ("entries", "capture_errors")}
    metadata["svd_flags"] = {
        k: captured.get("svd", {}).get(k) for k in ("full_matrices", "compute_uv", "hermitian")
    }
    errors = []
    available = {}
    for stage in ("svd", "pinv"):
        for name, value in captured.get(stage, {}).items():
            if type(value) is np.ndarray:
                label = "failed_" + stage + "_" + name
                available[label] = value
    raw = captured.get("raw_returns", {})
    if type(raw.get("pinv")) is np.ndarray:
        available["failed_raw_pinv_return"] = raw["pinv"]
    if isinstance(raw.get("svd"), tuple):
        for i, value in enumerate(raw["svd"]):
            if type(value) is np.ndarray:
                available["failed_raw_svd_return_" + str(i)] = value
    for label, value in available.items():
        try:
            arrays[label] = array_evidence(np, output, label, value)
        except BaseException as error:
            errors.append(dict(name=label, error=prior.exception_record(error)))
    metadata["persistence_errors"] = errors
    return metadata


def run(baseline, baseline_sha256, output, numpy_pins):
    output = prior.output_path(output)
    baseline = Path(baseline).absolute()
    if ".." in baseline.parts or any(p.is_symlink() for p in (baseline, *baseline.parents)):
        raise ValueError("Require an unaliased canonical baseline")
    if output.is_relative_to(baseline.parent) or baseline.parent.is_relative_to(output):
        raise ValueError("Do not write beside frozen baseline evidence")
    output.mkdir(parents=True, exist_ok=False)
    work, arrays = [], {}
    status = dict(kind=KIND, work=work, arrays=arrays, **NO_CREDIT)
    try:
        prior.verify_pins(numpy_pins)
        problem = saved_problem(baseline, baseline_sha256)
        status["inputs"] = problem["inputs"]
        proof = connected_flux_operator(problem["operator"], problem["shape"], problem["indices"])
        status["exact_graph_rank"] = proof
        import numpy as np

        binding = primitive_bindings(np, numpy_pins)
        status["blas_before"] = blas_state(np)
        if status["blas_before"]["library"] not in numpy_pins:
            raise ValueError("Unbound current BLAS runtime")
        status["mapped_libraries_before"] = loaded_libraries()
        status["numpy_version"] = np.__version__
        status["cpu_features"] = dict(np._core._multiarray_umath.__cpu_features__)
        status["numpy_pins"] = numpy_pins
        n = proof["points"]
        a = np.array(problem["operator"], dtype="<f8").reshape(n, n)
        g = np.array(problem["inverse"], dtype="<f8").reshape(n, n)
        for name, array in (("operator", a), ("saved_inverse", g)):
            arrays[name] = array_evidence(np, output, name, array)
        work.append(
            dict(
                operation="numpy.linalg.pinv",
                arguments="A only; defaults unchanged",
                attempted=True,
            )
        )
        try:
            observed, capture = capture_pinv(np, a)
        except BaseException as error:
            try:
                status["partial_capture"] = captured_failure(
                    np, output, getattr(error, "spectrum_capture", {}), arrays
                )
            except BaseException as capture_error:
                status["capture_persistence_error"] = prior.exception_record(capture_error)
            raise
        work[-1]["completed"] = True
        svd, pinv = capture["svd"], capture["pinv"]
        status["observed_primitive"] = dict(
            entries=capture["entries"],
            capture_errors=capture["capture_errors"],
            svd_flags={k: svd.get(k) for k in ("full_matrices", "compute_uv", "hermitian")},
        )
        values = {
            "observed_inverse": observed,
            **{k: svd[k] for k in ("u", "s", "vt", "input")},
            **{k: pinv[k] for k in ("cutoff", "large", "rcond")},
            "reciprocal_weights": pinv["s"],
        }
        persistence_errors = []
        for name, value in values.items():
            try:
                arrays[name] = array_evidence(np, output, name, value)
            except BaseException as error:
                persistence_errors.append(dict(name=name, error=prior.exception_record(error)))
        if persistence_errors:
            status["capture_persistence_errors"] = persistence_errors
            raise ValueError("Incomplete numeric observation archives")
        for name, value in values.items():
            shape = (n, n) if name in ("observed_inverse", "u", "vt", "input") else (n,)
            if name == "rcond":
                shape = ()
            elif name == "cutoff":
                shape = (1,)
            dtype = np.dtype(bool) if name == "large" else np.dtype("<f8")
            if type(value) is not np.ndarray or value.shape != shape or value.dtype != dtype:
                raise ValueError("Unexpected observation shape/dtype: " + name)
            if not np.isfinite(value).all():
                raise ValueError("Nonfinite observation: " + name)
        if (
            svd["full_matrices"] is not False
            or svd["compute_uv"] is not True
            or svd["hermitian"] is not False
            or svd["input"].tobytes() != a.tobytes()
            or float(pinv["rcond"]) != 1e-15
        ):
            raise ValueError("Unexpected original pinv/SVD primitive path")
        s, u, vt = svd["s"], svd["u"], svd["vt"]
        keep = s > pinv["cutoff"]
        if (
            s.shape != (n,)
            or u.shape != (n, n)
            or vt.shape != (n, n)
            or any(not np.isfinite(v).all() for v in (s, u, vt, observed))
            or not np.array_equal(keep, pinv["large"])
            or not np.all(s[:-1] >= s[1:])
            or not np.all(s >= 0)
            or not np.all(s[:-1] > 0)
        ):
            raise ValueError("Unexpected singular spectrum/cutoff decisions")
        default = reconstruct(np, u, s, vt, keep)
        arrays["default_reconstruction"] = array_evidence(
            np, output, "default_reconstruction", default
        )
        work.append(
            dict(
                operation="factor_reconstruction", mode="unchanged observed cutoff", completed=True
            )
        )
        if default.tobytes() != observed.tobytes():
            raise ValueError("Captured factor reconstruction differs from actual default pinv")
        alternative_keep = np.ones(n, dtype=bool)
        alternative_keep[-1] = False
        alternative = reconstruct(np, u, s, vt, alternative_keep)
        work.append(
            dict(
                operation="factor_reconstruction",
                mode="diagnostic exact graph rank n-1",
                completed=True,
            )
        )
        arrays["rank_n_minus_one_diagnostic"] = array_evidence(
            np, output, "rank_n_minus_one_diagnostic", alternative
        )
        status["spectrum"] = dict(
            singular_values=s.tolist(),
            cutoff=pinv["cutoff"].tolist(),
            kept=keep.tolist(),
            retained_rank=int(np.count_nonzero(keep)),
            smallest_over_cutoff=float(s[-1] / pinv["cutoff"][0]),
            smallest_left_constant_overlap=math.fsum(map(float, u[:, -1])) / math.sqrt(n),
            smallest_right_constant_overlap=math.fsum(map(float, vt[-1, :])) / math.sqrt(n),
            svd_calls=1,
            compute_uv=True,
            hermitian=False,
            full_matrices=False,
        )
        spectrum = status["spectrum"]
        spectrum["signed_constant_overlap_product"] = (
            spectrum["smallest_left_constant_overlap"] * spectrum["smallest_right_constant_overlap"]
        )
        spectrum["rank_n_minus_one_changes_default_mask"] = (
            alternative_keep.tolist() != keep.tolist()
        )
        spectrum["default_discarded_indices"] = np.flatnonzero(~keep).tolist()
        spectrum["counterfactual_discarded_indices"] = [n - 1]
        spectrum["smallest_mode_constant_entry_contribution"] = (
            spectrum["signed_constant_overlap_product"] / (n * float(s[-1])) if s[-1] > 0 else None
        )
        spectrum["smallest_pair"] = smallest_pair(
            problem["operator"], u[:, -1].tolist(), float(s[-1]), vt[-1, :].tolist()
        )
        status["default_matches_saved_bits"] = observed.tobytes() == g.tobytes()
        status["default_matches_own_reconstruction_bits"] = True
        status["compatible_forcing"] = {
            name: forcing_report(
                problem["operator"], matrix.ravel().tolist(), problem["shape"], problem["indices"]
            )
            for name, matrix in (("saved_inverse", g), ("rank_n_minus_one_diagnostic", alternative))
        }
        status["counterfactual_scope"] = (
            "Same captured factors, smallest singular mode discarded using exact graph rank; "
            "not a new production cutoff or admitted inverse"
        )
        status["blas_after"] = blas_state(np)
        if status["blas_after"] != status["blas_before"]:
            raise ValueError("BLAS runtime changed")
        if primitive_bindings(np, numpy_pins) != binding:
            raise ValueError("NumPy dispatch changed during diagnostic")
        status["mapped_libraries_after"] = loaded_libraries()
        prior.verify_pins(status["mapped_libraries_before"])
        if hashlib.sha256(a.tobytes()).hexdigest() != arrays["operator"]["raw_c_sha256"]:
            raise ValueError("Diagnostic mutated the saved operator copy")
        prior.verify_pins([*numpy_pins, *problem["inputs"]])
        status["status"] = "completed_diagnostic_only"
        prior.write(output / "report.json", status)
        return status
    except BaseException as error:
        status.update(
            status="failed", error=prior.exception_record(error), traceback=traceback.format_exc()
        )
        try:
            prior.write(output / "failure.json", status)
        except BaseException as persistence_error:
            error.spectrum_failure_persistence_error = persistence_error
            try:
                traceback.print_exception(persistence_error, file=sys.stderr)
            except BaseException as stderr_error:
                error.spectrum_stderr_error = stderr_error
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    inputs = prior.read(args.inputs)
    run(inputs["baseline"]["path"], inputs["baseline"]["sha256"], args.output, inputs["numpy_pins"])


if __name__ == "__main__":
    main()
