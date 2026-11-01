"""Evaluate the separate physical rectangular law on retained grid evidence.

The original BETSE geometry, operator and inverse are kept as independent inputs.
Only the new Cells metric and inverse are calculated. No native world, phase,
trajectory or executable owner is reconstructed from the saved data.
"""

import argparse
import math
import struct
from pathlib import Path

import numpy as np

from cells.processes import betse_native_grid_metric_audit as metric
from cells.processes import rectangular_environment as field
from validation.betse import native_single_cell_poisson_spectrum as saved
from validation.betse import rectangular_environment_reference as reference
from validation.betse import rectangular_environment_validation as runner

prior, algebra, compare, payload = saved.prior, saved.algebra, saved.compare, saved.payload
KIND = "cells.retained_physical_rectangle_diagnostic@1"


def inverse_bindings():
    from numpy.linalg import _linalg

    function = np.linalg.inv
    if function is not _linalg.inv or function.__wrapped__.__globals__ is not vars(_linalg):
        raise ValueError("Unexpected inverse primitive dispatch")
    return (
        function,
        function.__wrapped__,
        function.__wrapped__.__code__,
        _linalg._umath_linalg.inv,
        np.matmul,
    )


def observation(fields, problem, source_receipt):
    """Decode complete original arrays before selecting the two vertex axes."""
    shape = tuple(problem["shape"])
    algebra._grid(shape, problem["indices"])
    if tuple(map(tuple, problem["indices"])) != tuple(np.ndindex(shape)):
        raise ValueError("Require the retained complete C-order mapping without reordering")
    ny, nx = shape
    n = nx * ny

    def scalar(name):
        node = fields[name]
        if (
            set(node) != {"type", "dtype", "bits"}
            or node["type"] != "numpy_scalar"
            or node["dtype"] != "<f8"
        ):
            raise ValueError("Require retained binary64 grid scalar: " + name)
        value = struct.unpack("<d", bytes.fromhex(node["bits"]))[0]
        if not math.isfinite(value):
            raise ValueError("Nonfinite retained grid scalar: " + name)
        return value

    def array(name, extent):
        node = fields[name]
        if node.get("layout", {}).get("dtype") != "<f8":
            raise ValueError("Require original binary64 grid array: " + name)
        values = algebra._numbers(node, kind="f", shape=extent, label="retained " + name)
        return np.array(values, dtype=np.float64).reshape(extent)

    points = array("xy_cents", (n, 2))
    vx, vy = array("verts_X", (ny + 1, nx + 1)), array("verts_Y", (ny + 1, nx + 1))
    # Every row/column must match its retained axis byte-for-byte. Sampling only
    # one axis would otherwise conceal a nonrectangular or mutated saved grid.
    if any(vx[i].tobytes() != vx[0].tobytes() for i in range(ny + 1)) or any(
        vy[:, j].tobytes() != vy[:, 0].tobytes() for j in range(nx + 1)
    ):
        raise ValueError("Original full vertex grids are not tensor-product axes")
    original = metric.GridObservation(
        shape,
        tuple(scalar(k) for k in ("xmin", "xmax", "ymin", "ymax")),
        scalar("delta"),
        tuple(map(tuple, points.tolist())),
        tuple(map(tuple, problem["indices"])),
        tuple(vx[0].tolist()),
        tuple(vy[:, 0].tolist()),
        source_receipt,
    )
    return original, dict(
        retained_coordinates=points, retained_vertices_x=vx, retained_vertices_y=vy
    )


def load_grid(baseline, baseline_sha256):
    problem = saved.saved_problem(baseline, baseline_sha256)
    native = next(p for p in problem["inputs"] if Path(p["path"]).name == "native.json")
    raw = payload.read(native["path"], expected_sha256=native["sha256"])
    fields = compare._fields(
        compare._Cache(raw["environment"]["cache"], "saved", False).tree, "environment"
    )
    grid = compare._fields(fields["grid"], "grid")
    observed, arrays = observation(grid, problem, native["sha256"])
    return observed, arrays, problem


def probes(shape, indices):
    """Same five declared index probes as the earlier uniform-metric analysis."""
    algebra._grid(shape, indices)
    return dict(
        zero=np.zeros(len(indices)),
        corner_dipole=np.array(
            [
                int(tuple(p) == (0, 0)) - int(tuple(p) == (shape[0] - 1, shape[1] - 1))
                for p in indices
            ],
            dtype=np.float64,
        ),
        opposing_edges=np.array(
            [int(p[0] == 0) - int(p[0] == shape[0] - 1) for p in indices], dtype=np.float64
        ),
        centred_coordinate=np.array([2 * p[1] - (shape[1] - 1) for p in indices], dtype=np.float64),
        incompatible_constant=np.ones(len(indices)),
    )


def _retain_failed(output, raw, report):
    """Attempt every available public-return buffer independently, without replay."""
    retained = report["failed_return_capture"] = dict(arrays={}, errors=[], reference=None)

    def capture(name, get):
        try:
            value = get()
            retained["arrays"][name] = saved.array_evidence(np, output, "failed_" + name, value)
        except BaseException as error:
            retained["errors"].append(dict(field=name, error=prior.exception_record(error)))

    for name, value in raw.get("inputs", {}).items():
        capture(name, lambda value=value: value)
    if "rhs" in raw:
        capture("rhs", lambda: raw["rhs"])
    if "grid" in raw:
        for name in (
            "coordinates_m",
            "vertices_x_m",
            "vertices_y_m",
            "laplacian",
            "compatible_inverse",
        ):
            capture("grid_" + name, lambda name=name: getattr(raw["grid"], name))
    if "solve" in raw:
        for name in ("potential", "residual", "rhs_compatible", "finite_result"):
            capture("solve_" + name, lambda name=name: getattr(raw["solve"], name))
    if "reference" in raw:
        try:
            prior.write(output / "failed_reference.json", raw["reference"])
            retained["reference"] = prior.pin(output / "failed_reference.json")
        except BaseException as error:
            retained["errors"].append(dict(field="reference", error=prior.exception_record(error)))


def run(baseline, baseline_sha256, output, *, numpy_pins):
    output = runner.retained_output(output, baseline, baseline_sha256, numpy_pins)
    output.mkdir(parents=True, exist_ok=False)
    report = dict(
        kind=KIND,
        status="started",
        arrays={},
        stage="load_grid",
        probes=(),
        source_equivalence=False,
        numerical_acceptance=False,
        physical_tissue_admission=False,
        native_owner_or_checkpoint_admission=False,
        independent_biological_cases=0,
        input_mean_subtracted=False,
        native_inverse_replaced=False,
        return_capture_scope=(
            "Complete public bind/solve/reference returns and loaded inputs only; "
            "an inverse primitive return preceding a failed bind is not captured"
        ),
    )
    raw_returns = {}
    try:
        prior.verify_pins(numpy_pins)
        saved.primitive_bindings(np, numpy_pins)
        bindings = inverse_bindings()
        report["blas_before"] = saved.blas_state(np)
        if report["blas_before"]["library"] not in numpy_pins:
            raise ValueError("Actual BLAS library is absent from declared numerical pins")
        report["libraries_before"] = saved.loaded_libraries()
        observed, arrays, problem = load_grid(baseline, baseline_sha256)
        report["inputs"] = problem["inputs"]
        n = math.prod(observed.shape)
        native_a = np.array(problem["operator"], dtype=np.float64).reshape(n, n)
        native_g = np.array(problem["inverse"], dtype=np.float64).reshape(n, n)
        arrays.update(retained_native_operator=native_a, retained_native_inverse=native_g)
        raw_returns["inputs"] = arrays
        for name, value in arrays.items():
            report["arrays"][name] = saved.array_evidence(np, output, name, value)
        report["stage"] = "metric_audit"
        audit = metric.audit(observed, boundaries=tuple((s, "flux") for s in metric.SIDES))
        prior.write(output / "metric-audit.json", audit.record)
        report["metric_audit"] = dict(
            **prior.pin(output / "metric-audit.json"), identity=audit.identity
        )
        spec = field.spec_from_observation(
            audit, environment_ids=tuple("saved-index:" + str(i) for i in range(n))
        )
        report["stage"] = "physical_binding"
        grid = field.bind(spec)
        raw_returns["grid"] = grid
        report["grid"] = dict(
            identity=grid.identity,
            shape=grid.shape,
            bounds_m=grid.bounds_m,
            spacing_xy_m=grid.spacing_xy_m,
            area_m2=grid.cell_area_m2,
            original_scalar_delta_m=observed.delta_m,
            generated_ids_are_index_labels=True,
        )
        for name, value in (
            ("physical_operator", grid.laplacian),
            ("physical_inverse", grid.compatible_inverse),
        ):
            report["arrays"][name] = saved.array_evidence(np, output, name, value)
        if grid.coordinates_m.tobytes() != arrays["retained_coordinates"].tobytes():
            raise ValueError("Physical binding changed retained coordinate bits")
        loads = probes(observed.shape, problem["indices"])
        rhs = np.stack(list(loads.values()))
        raw_returns["rhs"] = rhs
        report["probes"] = list(loads)
        report["arrays"]["rhs"] = saved.array_evidence(np, output, "rhs", rhs)
        report["stage"] = "physical_solve"
        result = field.solve(rhs, grid)
        raw_returns["solve"] = result
        for name, value in (
            ("potential", result.potential),
            ("residual", result.residual),
            ("rhs_compatible", result.rhs_compatible),
            ("finite_result", result.finite_result),
        ):
            report["arrays"][name] = saved.array_evidence(np, output, name, value)
        report["usable"] = result.usable.tolist()
        report["usable_scope"] = (
            "Input compatibility and finite arithmetic only; not residual acceptance"
        )
        report["refused_rows_still_evaluated"] = True
        report["native_difference"] = dict(
            changed_entries=int(np.count_nonzero(grid.laplacian != native_a)),
            maximum_absolute_difference=float(np.max(np.abs(grid.laplacian - native_a))),
            intentional_distinct_metric=True,
        )
        report["stage"] = "independent_arithmetic"
        diagnosis = reference.diagnose(
            shape=observed.shape,
            indices=problem["indices"],
            bounds_m=observed.bounds_m,
            operator=grid.laplacian.ravel().tolist(),
            inverse=grid.compatible_inverse.ravel().tolist(),
            probes=tuple(
                dict(name=name, rhs=rhs[i].tolist(), solution=result.potential[i].tolist())
                for i, name in enumerate(loads)
            ),
        )
        raw_returns["reference"] = diagnosis
        prior.write(output / "reference.json", diagnosis)
        report["independent_arithmetic"] = prior.pin(output / "reference.json")
        prior.verify_pins(problem["inputs"])
        prior.verify_pins(numpy_pins)
        report["blas_after"] = saved.blas_state(np)
        report["libraries_after"] = saved.loaded_libraries()
        if (
            inverse_bindings() != bindings
            or report["blas_after"]["library"] not in numpy_pins
            or report["blas_after"] != report["blas_before"]
            or report["libraries_after"] != report["libraries_before"]
        ):
            raise ValueError("Numerical dispatch or mapped library changed during calculation")
        report.update(
            status="completed_numerical_diagnostic_only",
            stage="complete",
            work=dict(
                saved_grid_inputs=1,
                new_physical_bindings=1,
                batch_solves=1,
                rhs_rows=len(loads),
                declared_probes_are_not_independent_cases=True,
                native_source_replays=0,
            ),
        )
        prior.write(output / "report.json", report)
        return report
    except BaseException as error:
        report.update(status="failed", error=prior.exception_record(error))
        error.rectangular_raw_returns = raw_returns
        try:
            _retain_failed(output, raw_returns, report)
        except BaseException as capture:
            report["failed_return_capture_error"] = prior.exception_record(capture)
        try:
            prior.write(output / "failure.json", report)
        except BaseException as capture:
            error.rectangular_persistence_error = capture
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = prior.read(args.inputs)
    run(
        data["baseline"]["path"],
        data["baseline"]["sha256"],
        args.output,
        numpy_pins=data["numpy_pins"],
    )


if __name__ == "__main__":
    main()
