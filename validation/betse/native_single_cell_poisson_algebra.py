"""Independent algebra diagnostics for saved environmental Poisson operators.

This module evaluates no Cells/BETSE model and imports no numerical library.
It compares the retained operator with a regular-grid stencil and measures
inverse/projector residuals using sparse products and stdlib math.fsum. Source
correspondence, residuals and physical validation remain separate. In particular,
no residual tolerance or numerical acceptance is introduced by this report.
"""

import argparse
import math
import struct
from pathlib import Path

from validation.betse import native_single_cell_prefix_compare as compare
from validation.betse import native_single_cell_prefix_payload as payload
from validation.betse import native_single_cell_prefix_qualification as prior

MAX_POINTS = 625
KIND = "cells.saved_environment_poisson_algebra_diagnostic@1"
NO_CREDIT = dict(
    numerical_acceptance=False,
    physical_admission=False,
    native_source_executions=0,
    independent_biological_cases=0,
    new_acceptance_tolerance=None,
)


def _finite(value, label):
    if type(value) is not float or not math.isfinite(value):
        raise ValueError("Require finite binary64 " + label)
    return value


def _sum(values):
    result = math.fsum(values)
    if not math.isfinite(result):
        raise ValueError("Unrepresentable diagnostic sum; source bytes are unchanged")
    return result


def _product(left, right):
    result = left * right
    if not math.isfinite(result):
        raise ValueError("Unrepresentable diagnostic product; source bytes are unchanged")
    return result


def _grid(shape, indices):
    if (
        type(shape) not in (list, tuple)
        or len(shape) != 2
        or any(type(n) is not int or n < 2 for n in shape)
        or math.prod(shape) > MAX_POINTS
    ):
        raise ValueError("Require a rectangular grid of at least 2 by 2, at most 625 points")
    n = math.prod(shape)
    if type(indices) not in (list, tuple) or len(indices) != n:
        raise ValueError("Require the complete retained grid-to-row mapping")
    rows = {}
    for row, pair in enumerate(indices):
        if (
            type(pair) not in (list, tuple)
            or len(pair) != 2
            or any(
                type(v) is not int or not 0 <= v < size for v, size in zip(pair, shape, strict=True)
            )
            or tuple(pair) in rows
        ):
            raise ValueError("Invalid, duplicate or out-of-domain grid row")
        rows[tuple(pair)] = row
    return rows


def _stencil(shape, indices, boundary):
    rows = _grid(shape, indices)
    if boundary not in ("value", "flux") or type(boundary) is not str:
        raise ValueError("Only uniform all-value or all-flux boundaries are supported")
    stencil = []
    for k, (i, j) in enumerate(indices):
        at_boundary = i in (0, shape[0] - 1) or j in (0, shape[1] - 1)
        if boundary == "value" and at_boundary:
            stencil.append({k: 1})
        else:
            neighbours = [
                rows[p] for p in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)) if p in rows
            ]
            stencil.append({k: -len(neighbours), **dict.fromkeys(neighbours, 1)})
    return stencil


def diagnose(*, shape, indices, delta, operator, inverse, boundary):
    """Inspect flat finite binary64 values in the retained row order.

    Flux products target I-J/n. Zero inverse row AND column sums are measured
    separately: adding a constant matrix leaves both products unchanged.
    Value-boundary rows are identity rows; interior-to-boundary couplings make
    that operator generally nonsymmetric. No symmetry test is imposed on it.
    """
    expected = _stencil(shape, indices, boundary)
    n = len(expected)
    _finite(delta, "spacing")
    scale = _product(delta, delta)
    if delta <= 0 or scale == 0:
        raise ValueError("Require positive representable squared spacing")
    for name, values in (("operator", operator), ("inverse", inverse)):
        if type(values) not in (list, tuple) or len(values) != n * n:
            raise ValueError("Require the full square " + name)
        for value in values:
            _finite(value, name + " entry")

    sparse, columns = [], [[] for _ in range(n)]
    off_stencil, missing, examples, coefficient_inf, coefficient_max = 0, 0, [], 0.0, 0.0
    norm_a, norm_inverse, norm_inverse_1 = 0.0, 0.0, 0.0
    for i in range(n):
        row, errors = [], []
        for j in range(n):
            value = operator[i * n + j]
            coefficient = expected[i].get(j, 0)
            error = abs(_sum((_product(value, scale), -float(coefficient))))
            errors.append(error)
            coefficient_max = max(coefficient_max, error)
            if value != 0.0:
                row.append((j, value))
                columns[j].append((i, value))
                if coefficient == 0:
                    off_stencil += 1
                    if len(examples) < 16:
                        examples.append(dict(row=i, column=j, value=value))
            elif coefficient:
                missing += 1
        sparse.append(row)
        coefficient_inf = max(coefficient_inf, _sum(errors))
        norm_a = max(norm_a, _sum(abs(v) for _, v in row))
        norm_inverse = max(norm_inverse, _sum(abs(v) for v in inverse[i * n : (i + 1) * n]))
        norm_inverse_1 = max(norm_inverse_1, _sum(abs(inverse[j * n + i]) for j in range(n)))

    report = dict(
        boundary=boundary,
        shape=list(shape),
        points=n,
        spacing=delta,
        expected_nonzeros=sum(map(len, expected)),
        observed_nonzeros=sum(map(len, sparse)),
        off_stencil_nonzeros=off_stencil,
        missing_stencil_nonzeros=missing,
        off_stencil_examples=examples,
        dimensionless_stencil_error_inf=coefficient_inf,
        dimensionless_stencil_error_max_abs=coefficient_max,
        stencil_accumulation=(
            "delta*delta and A*scale each round to binary64 before comparison with the "
            "integer stencil; rescaling roundoff alone is not an equation defect"
        ),
        operator_norm_inf=norm_a,
        inverse_norm_inf=norm_inverse,
        inverse_norm_1=norm_inverse_1,
        products_available=False,
        **NO_CREDIT,
    )
    if off_stencil:
        # Never ignore unexpected dense entries to obtain a cheap sparse product.
        report["product_refusal"] = "Unexpected off-stencil entries; complete input retained"
        return report

    target_norm = 1.0 if boundary == "value" else 2.0 * (n - 1) / n
    denominator = _sum((_product(norm_a, norm_inverse), target_norm))
    left_inf, right_inf, left_max, right_max = 0.0, 0.0, 0.0, 0.0
    for i in range(n):
        left_errors, right_errors = [], []
        for j in range(n):
            target = float(i == j) if boundary == "value" else (n - 1 if i == j else -1) / n
            left = _sum([*(_product(a, inverse[k * n + j]) for k, a in sparse[i]), -target])
            right = _sum([*(_product(inverse[i * n + k], a) for k, a in columns[j]), -target])
            left_errors.append(abs(left))
            right_errors.append(abs(right))
            left_max, right_max = max(left_max, abs(left)), max(right_max, abs(right))
        left_inf, right_inf = max(left_inf, _sum(left_errors)), max(right_inf, _sum(right_errors))
    report.update(
        products_available=True,
        target="I" if boundary == "value" else "I-J/n",
        operator_inverse_residual_inf=left_inf,
        inverse_operator_residual_inf=right_inf,
        operator_inverse_residual_max_abs=left_max,
        inverse_operator_residual_max_abs=right_max,
        normalized_operator_inverse_residual=left_inf / denominator,
        normalized_inverse_operator_residual=right_inf / denominator,
        residual_normalization=(
            "||A||inf * ||Aplus||inf + ||target||inf; residual indicator, not a forward-error bound"
        ),
        accumulation="binary64 products and math.fsum; target fractions rounded once to binary64",
    )
    if boundary == "flux":
        row_a = max(abs(_sum(v for _, v in row)) for row in sparse)
        col_a = max(abs(_sum(v for _, v in column)) for column in columns)
        row_inv = max(abs(_sum(inverse[i * n : (i + 1) * n])) for i in range(n))
        col_inv = max(abs(_sum(inverse[j * n + i] for j in range(n))) for i in range(n))
        report["constant_mode"] = dict(
            operator_row_sum_inf=row_a,
            operator_column_sum_inf=col_a,
            inverse_row_sum_inf=row_inv,
            inverse_column_sum_inf=col_inv,
            inverse_row_sum_relative=row_inv / norm_inverse if norm_inverse else 0.0,
            inverse_column_sum_relative=col_inv / norm_inverse_1 if norm_inverse_1 else 0.0,
            requirement=(
                "Both inverse sums must approach zero; "
                "product residuals alone do not fix the constant mode"
            ),
        )
    return report


def _numbers(node, *, kind, shape, label):
    if (
        node.get("type") != "array"
        or node["layout"]["shape"] != list(shape)
        or node["layout"]["dtype"][1] not in kind
    ):
        raise ValueError("Wrong saved array type or shape: " + label)
    dtype = node["layout"]["dtype"]
    formats = {
        "i1": "b",
        "u1": "B",
        "i2": "h",
        "u2": "H",
        "i4": "i",
        "u4": "I",
        "i8": "q",
        "u8": "Q",
        "f8": "d",
    }
    if dtype[1:] not in formats:
        raise ValueError("Unsupported saved numeric width: " + label)
    raw = bytes.fromhex(node["raw"])
    return [
        v[0]
        for v in struct.iter_unpack(
            (dtype[0] if dtype[0] != "|" else "=") + formats[dtype[1:]], raw
        )
    ]


def analyse(reference):
    """Read authenticated wire values; never create an executable source owner."""
    if (
        type(reference) is not dict
        or reference.get("status") != "source_completed"
        or reference.get("stop_after") != "lapENV_P_inv"
        or "source_error" not in reference
        or reference["source_error"] is not None
        or "capture_error" not in reference
        or reference["capture_error"] is not None
    ):
        raise ValueError("Require a complete saved Poisson reference without capture failures")
    parent = compare._Cache(reference["environment"]["cache"], "reference.environment", False)
    shape = compare._poisson_shape(parent.tree)
    fields = compare._fields(parent.tree, "reference.environment")
    grid = compare._fields(fields["grid"], "reference.grid")
    dimensions = tuple(v["value"] for v in grid["cents_shape"]["items"])
    mapping = _numbers(grid["map_ij2k_cents"], kind="iu", shape=(shape[0], 2), label="grid mapping")
    indices = list(zip(mapping[::2], mapping[1::2], strict=True))
    spacing = grid["delta"]
    if spacing["type"] == "float":
        delta = struct.unpack("<d", bytes.fromhex(spacing["bits"]))[0]
    elif spacing["type"] == "numpy_scalar" and spacing["dtype"] in ("<f8", ">f8"):
        delta = struct.unpack(spacing["dtype"][0] + "d", bytes.fromhex(spacing["bits"]))[0]
    else:
        raise ValueError("Require saved binary64 grid spacing")
    final = reference["poisson"]["cache"]
    parsed = compare._Cache(
        final["outputs"], "reference.poisson.outputs", False, poisson_shape=shape
    )
    differences = []
    outputs = compare._poisson_outputs(
        parsed.tree, "reference.poisson.outputs", 2, shape, differences
    )
    if differences:
        raise ValueError("Saved operator/helper return associations disagree")
    reports = []
    for boundary, row in zip(("value", "flux"), outputs["results"]["items"], strict=True):
        operator, inverse = row["items"][1]["items"]
        result = diagnose(
            shape=dimensions,
            indices=indices,
            delta=delta,
            boundary=boundary,
            operator=_numbers(operator, kind="f", shape=shape, label="operator"),
            inverse=_numbers(inverse, kind="f", shape=shape, label="inverse"),
        )
        result["source_byte_hashes"] = dict(operator=operator["sha256"], inverse=inverse["sha256"])
        reports.append(result)
    return dict(
        kind=KIND,
        operators=reports,
        input_scope="one retained original-source prefix; two operators are not independent cases",
        **NO_CREDIT,
    )


def saved_report(reference_root, output):
    """Diagnose only the complete, hash-bound output of the existing comparator."""
    root = Path(reference_root).absolute()
    if (
        ".." in root.parts
        or any(p.is_symlink() for p in (root, *root.parents))
        or not root.is_dir()
    ):
        raise ValueError("Require a regular unaliased retained input directory")
    output = prior.output_path(output)
    if output.exists() or output.is_relative_to(root) or root.is_relative_to(output):
        raise ValueError("Diagnostic output must be fresh and separate from retained inputs")
    worker_pin = prior.pin(root / "worker-result.json")
    worker = prior.read(root / "worker-result.json")
    if (
        worker.get("status") != "exact_source_match"
        or type(worker.get("accepted_source_comparisons")) is not int
        or worker["accepted_source_comparisons"] != 1
        or worker.get("stop_after") != "lapENV_P_inv"
        or type(worker.get("native_executions")) is not int
        or worker["native_executions"] != 1
        or worker.get("attempted_model_imports") != []
        or worker.get("physical_geometry_admitted") is not False
        or worker.get("error") is not None
        or worker.get("runtime_capture_error") is not None
    ):
        raise ValueError("Require a completed saved exact Poisson comparison")
    native_pin, comparison_pin = (
        prior.pin(root / "native.json"),
        prior.pin(root / "comparison.json"),
    )
    if worker.get("native") != native_pin or worker.get("comparison") != comparison_pin:
        raise ValueError("Changed retained comparison input")
    pins = payload.files(root / "native.json")
    if worker.get("native_files") != pins:
        raise ValueError("Missing or changed complete native sidecar binding")
    comparison = prior.read(root / "comparison.json")
    expected_counts = dict(
        cache_pairs_compared=22,
        streams_compared=8,
        poisson_boundaries_compared=4,
        poisson_stages_compared=2,
        poisson_output_cache_pairs_compared=4,
        poisson_environment_checks=4,
    )
    if (
        comparison.get("exact_match") is not True
        or comparison.get("mismatches") != []
        or comparison.get("kind") != "cells.single_cell_saved_poisson_exact_comparison@1"
        or comparison.get("stop_after") != "lapENV_P_inv"
        or any(
            type(comparison.get(k)) is not int or comparison[k] != v
            for k, v in expected_counts.items()
        )
    ):
        raise ValueError("Require the exact complete saved Poisson comparison report")
    report = analyse(payload.read(root / "native.json"))
    report["inputs"] = [worker_pin, comparison_pin, *pins]
    prior.verify_pins(report["inputs"])
    output.parent.mkdir(parents=True, exist_ok=True)
    prior.write(output, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    saved_report(args.reference_root, args.output)


if __name__ == "__main__":
    main()
