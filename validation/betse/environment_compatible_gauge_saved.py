"""Retained-matrix diagnostic with explicit physical and operator-grid scopes.

The original coordinates/bounds are tried unchanged. A separately requested
uniform operator-metric grid is a labelled algebraic construction, never a
replacement for the retained physical grid or a source-equivalence claim.
"""

import argparse
import math
import struct
from dataclasses import replace
from pathlib import Path

import numpy as np

from validation.betse import environment_compatible_gauge as gauge
from validation.betse import native_single_cell_poisson_spectrum as saved

prior, compare, payload, algebra = saved.prior, saved.compare, saved.payload, saved.algebra
KIND = "cells.retained_flux_compatible_gauge_comparison@1"


def grid_spec(fields, problem, baseline_sha256):
    def scalar(name):
        node = fields[name]
        if set(node) != {"type", "dtype", "bits"} or (
            node["type"] != "numpy_scalar" or node["dtype"] != "<f8"
        ):
            raise ValueError("Require retained binary64 grid scalar: " + name)
        value = struct.unpack("<d", bytes.fromhex(node["bits"]))[0]
        if not math.isfinite(value):
            raise ValueError("Nonfinite retained grid scalar: " + name)
        return value

    shape, n = tuple(problem["shape"]), math.prod(problem["shape"])
    coordinates = algebra._numbers(
        fields["xy_cents"], kind="f", shape=(n, 2), label="retained grid centres"
    )
    return gauge.geometry.GridSpec(
        tuple(f"saved-grid-index:{i}" for i in range(n)),
        shape,
        tuple(scalar(k) for k in ("xmin", "xmax", "ymin", "ymax")),
        scalar("delta"),
        np.array(coordinates, dtype=np.float64).reshape(n, 2),
        dict.fromkeys(("N", "S", "E", "W"), "flux"),
        dict(
            baseline_sha256=baseline_sha256,
            role="retained_grid_data_only",
            generated_ids_are_index_labels=True,
            live_native_owner=False,
        ),
    )


def load_grid(baseline, baseline_sha256):
    problem = saved.saved_problem(baseline, baseline_sha256)
    native = next(p for p in problem["inputs"] if Path(p["path"]).name == "native.json")
    raw = payload.read(native["path"], expected_sha256=native["sha256"])
    fields = compare._fields(
        compare._Cache(raw["environment"]["cache"], "saved", False).tree, "env"
    )
    grid = compare._fields(fields["grid"], "grid")
    return grid_spec(grid, problem, baseline_sha256), problem


def operator_metric_grid(retained):
    """Explicit index-space construction using the unchanged operator spacing."""
    ny, nx = retained.shape
    xmin, _, ymin, _ = retained.bounds_m
    delta = retained.delta_m
    return replace(
        retained,
        bounds_m=(xmin, xmin + nx * delta, ymin, ymin + ny * delta),
        coordinates_m=np.array(
            [
                [xmin + (j + 0.5) * delta, ymin + (i + 0.5) * delta]
                for i, j in np.ndindex(retained.shape)
            ]
        ),
        provenance=dict(
            retained.provenance,
            role="explicit_uniform_operator_metric_only",
            retained_physical_geometry=False,
            geometry_repair_or_admission=False,
        ),
    )


def probes(shape, indices):
    algebra._grid(shape, indices)
    return {
        "zero": np.zeros(len(indices)),
        "corner_dipole": np.array(
            [
                int(tuple(p) == (0, 0)) - int(tuple(p) == (shape[0] - 1, shape[1] - 1))
                for p in indices
            ],
            dtype=np.float64,
        ),
        "opposing_edges": np.array(
            [int(p[0] == 0) - int(p[0] == shape[0] - 1) for p in indices], dtype=np.float64
        ),
        "centred_coordinate": np.array(
            [2 * p[1] - (shape[1] - 1) for p in indices], dtype=np.float64
        ),
        "incompatible_constant": np.ones(len(indices)),
    }


def run(baseline, baseline_sha256, output, *, include_operator_metric=False):
    if type(include_operator_metric) is not bool:
        raise ValueError("Declare the independent operator-metric calculation explicitly")
    output = prior.output_path(output)
    baseline = Path(baseline).absolute()
    if output.is_relative_to(baseline.parent) or baseline.parent.is_relative_to(output):
        raise ValueError("Do not write into retained input evidence")
    output.mkdir(parents=True, exist_ok=False)
    report = dict(
        kind=KIND,
        include_operator_metric=include_operator_metric,
        numerical_acceptance=False,
        physical_admission=False,
        independent_biological_cases=0,
        source_equivalence=False,
        new_tolerance=None,
        scopes={},
    )
    try:
        spec, problem = load_grid(baseline, baseline_sha256)
        report["inputs"] = problem["inputs"]
        report["blas_before"] = saved.blas_state(np)
        report["libraries_before"] = saved.loaded_libraries()
        n = math.prod(spec.shape)
        a = np.array(problem["operator"], dtype=np.float64).reshape(n, n)
        g = np.array(problem["inverse"], dtype=np.float64).reshape(n, n)
        loads = probes(spec.shape, problem["indices"])
        rhs = np.stack(list(loads.values()))
        report["probe_names"] = list(loads)
        report["arrays"] = {}
        for key, value in (
            ("retained_operator", a),
            ("retained_inverse", g),
            ("retained_coordinates", spec.coordinates_m),
            ("rhs", rhs),
        ):
            report["arrays"][key] = saved.array_evidence(np, output, key, value)
        scopes = [("retained_grid", spec)]
        if include_operator_metric:
            scopes.append(("operator_metric_only", operator_metric_grid(spec)))
        for name, candidate in scopes:
            folder = output / name
            folder.mkdir()
            row = dict(
                bounds=candidate.bounds_m,
                shape=candidate.shape,
                delta=candidate.delta_m,
                interval_counts=[
                    (candidate.bounds_m[1] - candidate.bounds_m[0]) / candidate.delta_m,
                    (candidate.bounds_m[3] - candidate.bounds_m[2]) / candidate.delta_m,
                ],
                provenance=candidate.provenance,
                status="started",
            )
            report["scopes"][name] = row
            row["coordinates"] = saved.array_evidence(
                np, folder, "coordinates", candidate.coordinates_m
            )
            try:
                result = gauge.diagnose(
                    candidate, indices=problem["indices"], operator=a, native_inverse=g, rhs=rhs
                )
            except ValueError as error:
                row.update(status="refused", error=prior.exception_record(error))
                prior.write(folder / "refusal.json", row)
                continue
            row.update(
                status="diagnosed",
                checks={
                    k: v
                    for k, v in result.items()
                    if k
                    not in (
                        "native_operator",
                        "native_inverse",
                        "rhs",
                        "compatible_inverse",
                        "solutions",
                    )
                },
            )
            row["inverse"] = saved.array_evidence(
                np, folder, "compatible_inverse", result["compatible_inverse"]
            )
            row["solutions"] = []
            for i, value in enumerate(result["solutions"]):
                row["solutions"].append(
                    None
                    if value is None
                    else saved.array_evidence(np, folder, f"solution_{i}", value)
                )
            row["exact_forcing"] = saved.forcing_report(
                a.ravel().tolist(),
                result["compatible_inverse"].ravel().tolist(),
                spec.shape,
                problem["indices"],
            )
            prior.write(folder / "report.json", row)
        prior.verify_pins(problem["inputs"])
        report["blas_after"] = saved.blas_state(np)
        report["libraries_after"] = saved.loaded_libraries()
        report["status"] = "completed_diagnostic_only"
        prior.write(output / "report.json", report)
        return report
    except BaseException as error:
        report.update(status="failed", error=prior.exception_record(error))
        try:
            prior.write(output / "failure.json", report)
        except BaseException as capture:
            error.diagnostic_persistence_error = capture
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inputs = prior.read(args.inputs)
    run(
        inputs["baseline"]["path"],
        inputs["baseline"]["sha256"],
        args.output,
        include_operator_metric=inputs["include_operator_metric"],
    )


if __name__ == "__main__":
    main()
