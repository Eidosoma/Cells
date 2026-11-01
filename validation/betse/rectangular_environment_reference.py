"""Independent exact-arithmetic diagnostics of supplied rectangular matrices.

No production module, numerical library, inverse constructor or solver is used.
Binary64 bounds define exact rational spans; the ideal all-flux stencil is
derived from those spans and the declared cell counts. Stored matrices remain
unchanged. Their coefficient rounding, complete support, products, constant
modes and supplied probes are observations, never an acceptance decision.
"""

import math
from decimal import Decimal, Inexact, localcontext
from fractions import Fraction

KIND = "cells.rectangular_environment_reference_diagnostic@1"
MAX_POINTS = 625
MAX_PROBES = 32
MAX_ARITHMETIC_TERMS = 16_000_000
MAX_PRECISION = 8192
DISPLAY_PRECISION = 80
MAX_EXAMPLES = 16
NO_CREDIT = dict(
    numerical_acceptance=False,
    physical_admission=False,
    native_source_correspondence=False,
    biological_cases=0,
    solver_calls=0,
    inverse_constructions=0,
    new_residual_acceptance_tolerance=None,
)


def _finite(value, label):
    if type(value) is not float or not math.isfinite(value):
        raise ValueError("Require finite binary64 " + label)
    return value


def _vector(values, count, label):
    if type(values) not in (list, tuple) or len(values) != count:
        raise ValueError("Require complete flattened " + label)
    return tuple(_finite(value, label + " entry") for value in values)


def _grid(shape, indices, bounds_m):
    if (
        type(shape) not in (list, tuple)
        or len(shape) != 2
        or any(type(size) is not int or size < 2 for size in shape)
        or math.prod(shape) > MAX_POINTS
    ):
        raise ValueError("Require a 2D rectangle, at least 2 by 2 and at most 625 cells")
    n = math.prod(shape)
    if type(indices) not in (list, tuple) or len(indices) != n:
        raise ValueError("Require the complete grid-to-matrix row mapping")
    lookup = {}
    for row, pair in enumerate(indices):
        if (
            type(pair) not in (list, tuple)
            or len(pair) != 2
            or any(
                type(index) is not int or not 0 <= index < size
                for index, size in zip(pair, shape, strict=True)
            )
            or tuple(pair) in lookup
        ):
            raise ValueError("Invalid, repeated or out-of-domain grid index")
        lookup[tuple(pair)] = row
    bounds = _vector(bounds_m, 4, "bounds (xmin,xmax,ymin,ymax)")
    xmin, xmax, ymin, ymax = map(Fraction.from_float, bounds)
    if not xmin < xmax or not ymin < ymax:
        raise ValueError("Require positive exact bound spans")
    ny, nx = shape
    dx, dy = (xmax - xmin) / nx, (ymax - ymin) / ny
    cx, cy = 1 / (dx * dx), 1 / (dy * dy)
    expected = [dict() for _ in range(n)]
    edges = []
    for pair, row in lookup.items():
        i, j = pair
        for neighbour, coefficient, axis in (
            ((i, j + 1), cx, "x"),
            ((i + 1, j), cy, "y"),
        ):
            if neighbour not in lookup:
                continue
            other = lookup[neighbour]
            edges.append((row, other, coefficient, axis))
            expected[row][other] = coefficient
            expected[other][row] = coefficient
            expected[row][row] = expected[row].get(row, Fraction(0)) - coefficient
            expected[other][other] = expected[other].get(other, Fraction(0)) - coefficient
    return bounds, dx, dy, cx, cy, expected, edges


def _ratio(value, denominator=1):
    """An exact rational with a separately marked rounded decimal display."""
    ratio = Fraction(value) / denominator
    with localcontext() as context:
        context.prec = DISPLAY_PRECISION
        context.traps[Inexact] = False
        context.clear_flags()
        display = Decimal(ratio.numerator) / Decimal(ratio.denominator)
        inexact = context.flags[Inexact]
    return dict(
        numerator=str(ratio.numerator),
        denominator=str(ratio.denominator),
        decimal80=str(display),
        display_inexact=inexact,
    )


def _rounding(value):
    try:
        rounded = float(value)
    except OverflowError:
        rounded = math.inf
    representable = math.isfinite(rounded)
    return dict(
        exact=_ratio(value),
        nearest_binary64_hex=rounded.hex() if representable else None,
        nearest_binary64_minus_exact=(
            _ratio(Fraction.from_float(rounded) - value) if representable else None
        ),
        nearest_binary64_finite=representable,
    )


def _precision(values, n):
    """Bound all exact dyadic expressions, including x_i*A_ij*x_j.

    Each scalar expression has at most three input factors. The global decimal
    exponent range therefore covers their products; eight digit-counts of n
    plus32 cover sums, norms and integer-cleared projector entries. Inexact is
    additionally trapped. Rational stencil/area arithmetic uses Fraction.
    """
    low = high = 0
    for value in values:
        if value:
            low = min(low, value.as_tuple().exponent)
            high = max(high, value.adjusted())
    precision = max(32, 3 * high + 3 - 3 * low + 1 + 8 * len(str(n)) + 32)
    if precision > MAX_PRECISION:
        raise ValueError("Exact decimal precision bound exceeded")
    return precision


def _max_signed(values):
    index, value = max(enumerate(values), key=lambda item: abs(item[1]))
    return dict(max_abs=_ratio(abs(value)), signed_value=_ratio(value), index=index)


def _stats(rows, columns, n):
    zero = Decimal(0)
    row_sums = [sum((value for _, value in row), zero) for row in rows]
    column_sums = [sum((value for _, value in column), zero) for column in columns]
    mapping = [dict(row) for row in rows]
    maximum, location, signed = zero, [0, 0], zero
    for i, row in enumerate(mapping):
        # The reverse support is required too: no asymmetric entry is skipped.
        keys = row.keys() | dict(columns[i]).keys()
        for j in sorted(keys):
            error = row.get(j, zero) - mapping[j].get(i, zero)
            if abs(error) > maximum:
                maximum, location, signed = abs(error), [i, j], error
    return dict(
        entries_checked=n * n,
        norm_inf=_ratio(max(sum((abs(value) for _, value in row), zero) for row in rows)),
        norm_one=_ratio(max(sum((abs(value) for _, value in column), zero) for column in columns)),
        row_sums=[_ratio(value) for value in row_sums],
        column_sums=[_ratio(value) for value in column_sums],
        row_constant_mode=_max_signed(row_sums),
        column_constant_mode=_max_signed(column_sums),
        symmetry=dict(max_abs=_ratio(maximum), at=location, signed_error=_ratio(signed)),
    )


def _inverse_stats(g, n):
    """Scan dense G without constructing a second dense matrix of tuples."""
    zero = Decimal(0)
    rows = [sum(g[i * n : (i + 1) * n], zero) for i in range(n)]
    columns = [sum((g[i * n + j] for i in range(n)), zero) for j in range(n)]
    maximum, location, signed = zero, [0, 0], zero
    for i in range(n):
        for j in range(n):
            error = g[i * n + j] - g[j * n + i]
            if abs(error) > maximum:
                maximum, location, signed = abs(error), [i, j], error
    return dict(
        entries_checked=n * n,
        norm_inf=_ratio(
            max(sum((abs(value) for value in g[i * n : (i + 1) * n]), zero) for i in range(n))
        ),
        norm_one=_ratio(max(sum((abs(g[i * n + j]) for i in range(n)), zero) for j in range(n))),
        row_sums=[_ratio(value) for value in rows],
        column_sums=[_ratio(value) for value in columns],
        row_constant_mode=_max_signed(rows),
        column_constant_mode=_max_signed(columns),
        symmetry=dict(max_abs=_ratio(maximum), at=location, signed_error=_ratio(signed)),
    )


def _support(operator, expected, n):
    sparse, columns = [], [[] for _ in range(n)]
    missing, unexpected, examples_missing, examples_unexpected = 0, 0, [], []
    maximum, row_norm, location, signed = Fraction(0), Fraction(0), [0, 0], Fraction(0)
    for i in range(n):
        row, errors = [], Fraction(0)
        for j in range(n):
            value = operator[i * n + j]
            ideal = expected[i].get(j, Fraction(0))
            if value != 0.0:
                retained = Decimal.from_float(value)
                row.append((j, retained))
                columns[j].append((i, retained))
                if not ideal:
                    unexpected += 1
                    if len(examples_unexpected) < MAX_EXAMPLES:
                        examples_unexpected.append(dict(row=i, column=j, binary64_hex=value.hex()))
            elif ideal:
                missing += 1
                if len(examples_missing) < MAX_EXAMPLES:
                    examples_missing.append(dict(row=i, column=j, expected=_ratio(ideal)))
            if value or ideal:
                error = Fraction.from_float(value) - ideal
                errors += abs(error)
                if abs(error) > maximum:
                    maximum, location, signed = abs(error), [i, j], error
        row_norm = max(row_norm, errors)
        sparse.append(row)
    return (
        sparse,
        columns,
        dict(
            entries_checked=n * n,
            expected_nonzeros=sum(map(len, expected)),
            observed_nonzeros=sum(map(len, sparse)),
            missing_nonzeros=missing,
            unexpected_nonzeros=unexpected,
            missing_examples=examples_missing,
            unexpected_examples=examples_unexpected,
            examples_limit=MAX_EXAMPLES,
            coefficient_error=dict(
                max_abs=_ratio(maximum),
                at=location,
                signed_error=_ratio(signed),
                norm_inf=_ratio(row_norm),
            ),
            interpretation=(
                "Stored binary64 A minus the exact bound-span/count stencil; coefficient "
                "rounding is retained, not classified as equation or physical failure"
            ),
            unexpected_entries_dropped=0,
        ),
    )


def _products(sparse, columns, g, n):
    zero = Decimal(0)
    stats = {
        name: dict(maximum=zero, norm=zero, at=[0, 0], signed=zero)
        for name in ("AG_minus_P", "GA_minus_P")
    }
    for i in range(n):
        row_norms = dict.fromkeys(stats, zero)
        for j in range(n):
            target_n = n * int(i == j) - 1
            errors = (
                n * sum((value * g[k * n + j] for k, value in sparse[i]), zero) - target_n,
                n * sum((g[i * n + k] * value for k, value in columns[j]), zero) - target_n,
            )
            for name, error in zip(stats, errors, strict=True):
                magnitude = abs(error)
                row_norms[name] += magnitude
                if magnitude > stats[name]["maximum"]:
                    stats[name].update(maximum=magnitude, at=[i, j], signed=error)
        for name in stats:
            stats[name]["norm"] = max(stats[name]["norm"], row_norms[name])
    return {
        name: dict(
            entries_checked=n * n,
            max_abs=_ratio(values["maximum"], n),
            norm_inf=_ratio(values["norm"], n),
            at=values["at"],
            signed_error=_ratio(values["signed"], n),
        )
        for name, values in stats.items()
    }


def _probes(probes, n):
    if type(probes) not in (tuple, list) or len(probes) > MAX_PROBES:
        raise ValueError("Require at most32 supplied probes")
    retained, names = [], set()
    for probe in probes:
        if type(probe) is not dict or set(probe) != {"name", "rhs", "solution"}:
            raise ValueError("Probe schema must be exactly name/rhs/solution")
        name = probe["name"]
        if type(name) is not str or not name or len(name) > 128 or name in names:
            raise ValueError("Require bounded unique probe names")
        names.add(name)
        rhs = _vector(probe["rhs"], n, "probe RHS")
        solution = (
            None if probe["solution"] is None else _vector(probe["solution"], n, "probe solution")
        )
        retained.append(
            (
                name,
                tuple(map(Decimal.from_float, rhs)),
                None if solution is None else tuple(map(Decimal.from_float, solution)),
            )
        )
    return retained


def _probe(name, b, x, sparse, g, n, area, edges, arithmetic_available):
    zero = Decimal(0)
    total, absolute = sum(b, zero), sum(map(abs, b), zero)
    result = dict(
        name=name,
        rhs_sum=_ratio(total),
        rhs_abs_sum=_ratio(absolute),
        rhs_relative_imbalance=_ratio(Fraction(abs(total)) / Fraction(absolute) if absolute else 0),
        rhs_exactly_balanced=total == 0,
        area_weighted_rhs_sum=_ratio(area * Fraction(total)),
        supplied_solution=x is not None,
        solution_diagnostics_available=x is not None and arithmetic_available,
        rhs_modified=False,
    )
    if x is None or not arithmetic_available:
        return result
    ax = [sum((value * x[j] for j, value in row), zero) for row in sparse]
    residual = [left - right for left, right in zip(ax, b, strict=True)]
    inverse_action = [sum((g[i * n + j] * b[j] for j in range(n)), zero) for i in range(n)]
    action_error = [left - right for left, right in zip(inverse_action, x, strict=True)]
    potential_sum = sum(x, zero)
    stored_quadratic = -sum((value * image for value, image in zip(x, ax, strict=True)), zero)
    exact_x = tuple(map(Fraction, x))
    edge_quadratic = sum(
        (coefficient * (exact_x[i] - exact_x[j]) ** 2 for i, j, coefficient, _ in edges),
        Fraction(0),
    )
    balance = sum(ax, zero)
    result.update(
        residual=_max_signed(residual),
        residual_sum=_ratio(sum(residual, zero)),
        potential_sum=_ratio(potential_sum),
        potential_mean=_ratio(potential_sum, n),
        inverse_action_minus_supplied_solution=_max_signed(action_error),
        operator_image_sum=_ratio(balance),
        area_weighted_operator_image_sum=_ratio(area * Fraction(balance)),
        area_weighted_residual_sum=_ratio(area * Fraction(sum(residual, zero))),
        energy=dict(
            stored_negative_x_A_x=_ratio(stored_quadratic),
            exact_stencil_edge_form=_ratio(edge_quadratic),
            stored_minus_exact_edge_form=_ratio(Fraction(stored_quadratic) - edge_quadratic),
            area_weighted_stored=_ratio(area * Fraction(stored_quadratic)),
            area_weighted_exact_edges=_ratio(area * edge_quadratic),
            units=(
                "Formal discrete quadratic forms; these are not thermodynamic energy "
                "without a separately specified physical field/material model"
            ),
        ),
    )
    return result


def diagnose(*, shape, indices, bounds_m, operator, inverse, probes=()):
    """Report on complete finite stored A/G and optional supplied (b,x) pairs.

    indices maps each retained matrix row to (y-index,x-index); complete
    permutations are honored. Bounds are (xmin,xmax,ymin,ymax). Probe mappings
    contain exactly name/rhs/solution; solution may be None. Inputs are not
    modified. Products include every actual nonzero, even off-stencil entries.
    An explicit work refusal can suppress products/probe actions, never support
    checks or hide unexpected entries. No report field grants acceptance.
    """
    bounds, dx, dy, cx, cy, expected, edges = _grid(shape, indices, bounds_m)
    n = len(expected)
    a_values = _vector(operator, n * n, "operator")
    g_values = _vector(inverse, n * n, "inverse")
    retained_probes = _probes(probes, n)
    sparse, columns, support = _support(a_values, expected, n)
    g = list(map(Decimal.from_float, g_values))
    decimals = (value for row in sparse for _, value in row)
    precision = _precision(decimals, n)
    precision = max(precision, _precision(g, n))
    for _, b, x in retained_probes:
        precision = max(precision, _precision(b, n), _precision(x or (), n))
    # Each individual range includes zero, so the largest derived precision
    # covers any mixed product of up to three of these input collections.
    nnz = support["observed_nonzeros"]
    terms = 2 * n * nnz + sum(x is not None for _, _, x in retained_probes) * (nnz + n * n)
    available = terms <= MAX_ARITHMETIC_TERMS
    report = dict(
        kind=KIND,
        shape=list(shape),
        indices=[list(pair) for pair in indices],
        points=n,
        bounds_m=list(bounds),
        boundary="homogeneous_all_flux",
        exact_spacing_m=dict(x=_ratio(dx), y=_ratio(dy)),
        exact_cell_area_m2=_ratio(dx * dy),
        coefficients_per_m2=dict(x=_rounding(cx), y=_rounding(cy)),
        support=support,
        arithmetic=dict(
            kind="exact dyadic Decimal products and Fraction geometry",
            precision_digits=precision,
            precision_limit=MAX_PRECISION,
            decimal_inexact_trapped=True,
            rational_format="integer-string numerator / positive integer-string denominator",
            display_precision=DISPLAY_PRECISION,
            display_rounding_is_not_acceptance=True,
        ),
        work=dict(
            scalar_product_terms=terms,
            maximum_scalar_product_terms=MAX_ARITHMETIC_TERMS,
            products_and_solution_actions_available=available,
            refusal=None if available else "Complete product/action arithmetic exceeds work bound",
            omitted_operator_entries=0,
        ),
        product_target="I-J/n",
        input_matrices_changed=False,
        coordinate_or_geometry_repair=False,
        original_rhs_centered=False,
        **NO_CREDIT,
    )
    with localcontext() as context:
        context.prec = precision
        context.traps[Inexact] = True
        context.clear_flags()
        report["operator"] = _stats(sparse, columns, n)
        report["inverse"] = _inverse_stats(g, n)
        report["products"] = _products(sparse, columns, g, n) if available else None
        report["probes"] = [
            _probe(name, b, x, sparse, g, n, dx * dy, edges, available)
            for name, b, x in retained_probes
        ]
        report["arithmetic"]["inexact_flag"] = bool(context.flags[Inexact])
    return report
