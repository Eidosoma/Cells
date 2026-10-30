"""Independent integer-grid and full-precision Decimal primitive definitions."""

import math
import struct
from decimal import Decimal, localcontext


class ReferenceRejected(ValueError):
    def __init__(self, code, trial=None):
        super().__init__(code)
        self.code, self.trial = code, trial


def _ratio(numerator, denominator):
    if denominator < 0:
        numerator, denominator = -numerator, -denominator
    return dict(numerator=str(numerator), denominator=str(denominator))


def _decimal(ratio):
    return Decimal(ratio["numerator"]) / Decimal(ratio["denominator"])


def _scaled(points):
    ratios = [[v.as_integer_ratio() for v in row] for row in points]
    exponent = max(d.bit_length() - 1 for row in ratios for _, d in row)
    scale = 1 << exponent
    return [[n * (scale // d) for n, d in row] for row in ratios], scale


def _det(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on(a, b, c):
    return all(min(x, y) <= z <= max(x, y) for x, y, z in zip(a, b, c, strict=True))


def _domain(kind, points):
    if len({tuple(p) for p in points}) != len(points):
        raise ReferenceRejected("repeated_vertex")
    if kind == "triangle":
        if _det(*points) == 0:
            raise ReferenceRejected("degenerate_triangle")
        return
    n = len(points)
    if not any(_det(points[i - 1], points[i], points[(i + 1) % n]) for i in range(n)):
        raise ReferenceRejected("degenerate_polygon")
    for i in range(n):
        a, b = points[i], points[(i + 1) % n]
        previous = points[i - 1]
        if _det(previous, a, b) == 0 and not _on(previous, b, a):
            raise ReferenceRejected("overlapping_adjacent_edges")
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue
            c, d = points[j], points[(j + 1) % n]
            turns = (_det(a, b, c), _det(a, b, d), _det(c, d, a), _det(c, d, b))
            crossing = turns[0] * turns[1] < 0 and turns[2] * turns[3] < 0
            touching = (
                (turns[0] == 0 and _on(a, b, c))
                or (turns[1] == 0 and _on(a, b, d))
                or (turns[2] == 0 and _on(c, d, a))
                or (turns[3] == 0 and _on(c, d, b))
            )
            if crossing or touching:
                raise ReferenceRejected("non_simple_polygon")


def _rational_targets(kind, points):
    grid, scale = _scaled(points)
    if kind == "polygon":
        edges = [(grid[i], grid[(i + 1) % len(grid)]) for i in range(len(grid))]
        weights = [a[0] * b[1] - b[0] * a[1] for a, b in edges]
        area2 = sum(weights)
        if area2 == 0:
            raise ReferenceRejected("degenerate_polygon")
        return dict(
            centroid_x_m=_ratio(
                sum((a[0] + b[0]) * w for (a, b), w in zip(edges, weights, strict=True)),
                3 * area2 * scale,
            ),
            centroid_y_m=_ratio(
                sum((a[1] + b[1]) * w for (a, b), w in zip(edges, weights, strict=True)),
                3 * area2 * scale,
            ),
            signed_area_m2=_ratio(area2, 2 * scale * scale),
        ), None
    a, b, c = grid
    norms = [x * x + y * y for x, y in grid]
    denominator = 2 * (a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1]))
    nx = norms[0] * (b[1] - c[1]) + norms[1] * (c[1] - a[1]) + norms[2] * (a[1] - b[1])
    ny = norms[0] * (c[0] - b[0]) + norms[1] * (a[0] - c[0]) + norms[2] * (b[0] - a[0])
    squared_radius = _ratio(
        (nx - a[0] * denominator) ** 2 + (ny - a[1] * denominator) ** 2, denominator**2 * scale**2
    )
    return dict(
        circumcenter_x_m=_ratio(nx, denominator * scale),
        circumcenter_y_m=_ratio(ny, denominator * scale),
        area_m2=_ratio(abs(_det(a, b, c)), 2 * scale * scale),
    ), squared_radius


def _rounded_ratio(ratio, approximation):
    n, d = int(ratio["numerator"]), int(ratio["denominator"])
    if abs(n) >= d * ((1 << 1024) - (1 << 970)):
        return None
    value = float(approximation)
    if not math.isfinite(value):
        value = math.copysign(float.fromhex("0x1.fffffffffffffp+1023"), -1.0 if n < 0 else 1.0)
    for _ in range(4):
        candidates = [
            v
            for v in (math.nextafter(value, -math.inf), value, math.nextafter(value, math.inf))
            if math.isfinite(v)
        ]
        best = candidates[0]
        bn, bd = best.as_integer_ratio()
        distance = abs(bn * d - n * bd)
        for candidate in candidates[1:]:
            cn, cd = candidate.as_integer_ratio()
            error = abs(cn * d - n * cd)
            left, right = error * bd, distance * cd
            even = int.from_bytes(struct.pack(">d", candidate)) & 1 == 0
            if left < right or (left == right and even):
                best, bd, distance = candidate, cd, error
        if best == value:
            return None if best == 0 and n else (0.0).hex() if n == 0 else best.hex()
        value = best
    raise ReferenceRejected("reference_rounding_unresolved")


def evaluate(kind, points_hex, *, refinement=1):
    if kind not in ("polygon", "triangle") or refinement not in (1, 2):
        raise ReferenceRejected("reference_declaration")
    points = [[float.fromhex(v) for v in row] for row in points_hex]
    if not 3 <= len(points) <= 64 or any(
        len(p) != 2 or not all(math.isfinite(v) for v in p) for p in points
    ):
        raise ReferenceRejected("reference_input_domain")
    if kind == "triangle" and len(points) != 3:
        raise ReferenceRejected("triangle_arity")
    grid, _ = _scaled(points)
    _domain(kind, grid)
    exact, squared_radius = _rational_targets(kind, points)
    decimals = [[Decimal.from_float(v) for v in p] for p in points]
    nonzero = [v for p in decimals for v in p if v]
    span = max(v.adjusted() for v in nonzero) - min(v.as_tuple().exponent for v in nonzero) + 1
    precision = max(4096, 6 * span + 160) + (512 if refinement == 2 else 0)
    if precision > 16384:
        raise ReferenceRejected("reference_precision_domain")
    with localcontext() as context:
        context.prec = precision
        if kind == "polygon":
            edges = [(decimals[i], decimals[(i + 1) % len(decimals)]) for i in range(len(decimals))]
            weights = [a[0] * b[1] - b[0] * a[1] for a, b in edges]
            area2 = sum(weights, Decimal(0))
            formula = dict(
                centroid_x_m=sum(
                    ((a[0] + b[0]) * w for (a, b), w in zip(edges, weights, strict=True)),
                    Decimal(0),
                )
                / (3 * area2),
                centroid_y_m=sum(
                    ((a[1] + b[1]) * w for (a, b), w in zip(edges, weights, strict=True)),
                    Decimal(0),
                )
                / (3 * area2),
                signed_area_m2=area2 / 2,
            )
        else:
            a, b, c = decimals
            rows = [
                [
                    2 * (p[0] - a[0]),
                    2 * (p[1] - a[1]),
                    p[0] ** 2 + p[1] ** 2 - a[0] ** 2 - a[1] ** 2,
                ]
                for p in (b, c)
            ]
            if abs(rows[0][0]) < abs(rows[1][0]):
                rows.reverse()
            multiplier = rows[1][0] / rows[0][0]
            second = [x - multiplier * y for x, y in zip(rows[1], rows[0], strict=True)]
            cy = second[2] / second[1]
            cx = (rows[0][2] - rows[0][1] * cy) / rows[0][0]
            sides = [
                sum(((x - y) ** 2 for x, y in zip(p, q, strict=True)), Decimal(0)).sqrt()
                for p, q in ((a, b), (b, c), (c, a))
            ]
            semi = sum(sides, Decimal(0)) / 2
            heron = (semi * (semi - sides[0]) * (semi - sides[1]) * (semi - sides[2])).sqrt()
            formula = dict(
                circumcenter_x_m=cx,
                circumcenter_y_m=cy,
                circumradius_m=((cx - a[0]) ** 2 + (cy - a[1]) ** 2).sqrt(),
                inradius_m=heron / semi,
                area_m2=heron,
            )
        values = dict(formula)
        values.update({name: _decimal(ratio) for name, ratio in exact.items()})
        if kind == "triangle":
            values["circumradius_m"] = _decimal(squared_radius).sqrt()
            values["inradius_m"] = values["area_m2"] / semi
        rounded = {}
        for name, value in values.items():
            if name in exact:
                rounded[name] = _rounded_ratio(exact[name], value)
            else:
                candidate = float(value)
                rounded[name] = (
                    candidate.hex() if math.isfinite(candidate) and candidate != 0 else None
                )
        return dict(
            kind="cells.stable_geometry_independent_reference@1",
            primitive=kind,
            precision_digits=precision,
            values_decimal={k: str(v) for k, v in values.items()},
            independent_formula_values_decimal={k: str(v) for k, v in formula.items()},
            values_rounded_hex=rounded,
            exact_rational_targets=exact,
            exact_squared_circumradius=squared_radius,
            input_binary64_hex=points_hex,
            output_representable=all(v is not None for v in rounded.values()),
            production_imports=False,
            native_equivalence=False,
            whole_mesh_credit=False,
            topology_qualified=False,
            physical_geometry_admitted=False,
        )
