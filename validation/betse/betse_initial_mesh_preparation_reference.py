"""Independent Decimal geometry and exact-rational Delaunay diagnostics.

Captured topology is an input. This is not an independent triangulation or
native tie-order generator, and diagnostics do not silently certify topology.
"""

from decimal import Decimal, localcontext
from fractions import Fraction


class ReferenceFailure(ValueError):
    def __init__(self, error, trial):
        super().__init__("Initial mesh reference failed: " + str(error))
        self.trial = trial


def d(value):
    return Decimal.from_float(float(value))


def serial(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (list, tuple)):
        return [serial(v) for v in value]
    if isinstance(value, dict):
        return {key: serial(v) for key, v in value.items()}
    return value


def polygon(points):
    p = [[d(x), d(y)] for x, y in points]
    q = p[1:] + p[:1]
    cross = [a[0] * b[1] - b[0] * a[1] for a, b in zip(p, q, strict=True)]
    area = sum(cross) / 2
    if area:
        centre = [
            sum((a[k] + b[k]) * c for a, b, c in zip(p, q, cross, strict=True)) / (6 * area)
            for k in (0, 1)
        ]
    else:
        # Preserve the named native zero-area fallback, not a true centroid.
        centre = [(p[i][0] + p[i][1]) / 2 for i in (0, 1)] if len(p) >= 2 else None
    return area, centre


def distance(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b, strict=True)).sqrt()


def triangle(A, B, C):
    a, b, c = ([d(x), d(y)] for x, y in (A, B, C))
    aa, bb, cc = (sum(v * v for v in row) for row in (a, b, c))
    denom = 2 * (a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1]))
    centre = [
        (aa * (b[1] - c[1]) + bb * (c[1] - a[1]) + cc * (a[1] - b[1])) / denom,
        (aa * (c[0] - b[0]) + bb * (a[0] - c[0]) + cc * (b[0] - a[0])) / denom,
    ]
    ab, bc, ca = distance(a, b), distance(b, c), distance(c, a)
    s = (ab + bc + ca) / 2
    area = (s * (s - ab) * (s - bc) * (s - ca)).sqrt()
    radius = ab * bc * ca / (4 * area) if area > 0 else Decimal(0)
    return [*centre, radius, 2 * area / (ab + bc + ca)]


def source_quad(A, B, C, D):
    points = [[d(x), d(y)] for x, y in (A, B, C, D)]
    a, b, c, e = [distance(points[i], points[(i + 1) % 4]) for i in range(4)]
    s = (a + b + c + e) / 2
    area = ((s - a) * (s - b) * (s - c) * (s - e)).sqrt()
    radius = ((a * c + b * e) * (a * e + b * c) * (a * b + c * e)).sqrt() / (4 * area)
    diagonal = [points[2][i] - points[0][i] for i in (0, 1)]
    length = sum(v * v for v in diagonal).sqrt()
    centre = [points[0][i] + radius * diagonal[i] / length for i in (0, 1)]
    shoelace, centroid = polygon((A, B, C, D))
    return [radius, area, *centre], dict(
        source_quantity="Brahmagupta area and radius-along-AC centre",
        general_polygon_signed_area_m2=shoelace,
        general_polygon_centroid_m=centroid,
        general_circumcentre_or_cyclicity_claim=False,
    )


def primitive(method, parameters):
    if method == "area":
        return polygon(parameters["p"])[0], {}
    if method == "poly_centroid":
        return polygon(parameters["p"])[1], {}
    if method == "circumc":
        return triangle(parameters["A"], parameters["B"], parameters["C"]), {}
    if method == "quad_circumc":
        return source_quad(parameters["A"], parameters["B"], parameters["C"], parameters["D"])
    raise ValueError("No analytic result oracle for this native helper")


def nearest(payload):
    data = [[d(v) for v in row] for row in payload["data"]]
    points = payload["points"]
    if not points:
        return []
    scalar = not isinstance(points[0], (tuple, list))
    queries = [points] if scalar else points
    k = payload["kwargs"].get("k", payload["args"][0] if payload["args"] else 1)
    if type(k) is not int:
        raise ValueError("Prepared native trees use scalar integer k")
    result = []
    for point in queries:
        query = [d(v) for v in point]
        squared = [sum((a - b) ** 2 for a, b in zip(row, query, strict=True)) for row in data]
        ordered = sorted(squared)
        result.append(
            dict(
                ranked_distances=[
                    ordered[i].sqrt() if i < len(ordered) else "infinity" for i in range(k)
                ],
                exact_tie_candidate_indices=[
                    [j for j, value in enumerate(squared) if value == ordered[i]]
                    if i < len(ordered)
                    else [len(data)]
                    for i in range(k)
                ],
                independent_index_order_claim=False,
            )
        )
    return result


def delaunay_diagnostic(payload):
    """Exact binary-input circle signs; report rather than hide Qhull ambiguity."""
    points = [[Fraction(float(v)) for v in row] for row in payload["points"]]
    reports = []
    for indices in payload["simplices"]:
        A, B, C = (points[i] for i in indices)
        aa, bb, cc = (sum(v * v for v in row) for row in (A, B, C))
        denom = 2 * (A[0] * (B[1] - C[1]) + B[0] * (C[1] - A[1]) + C[0] * (A[1] - B[1]))
        if not denom:
            reports.append(dict(indices=indices, exact_degenerate=True))
            continue
        centre = [
            (aa * (B[1] - C[1]) + bb * (C[1] - A[1]) + cc * (A[1] - B[1])) / denom,
            (aa * (C[0] - B[0]) + bb * (A[0] - C[0]) + cc * (B[0] - A[0])) / denom,
        ]
        r2 = sum((v - c) ** 2 for v, c in zip(A, centre, strict=True))
        signs = []
        for i, point in enumerate(points):
            if i not in indices:
                gap = sum((v - c) ** 2 for v, c in zip(point, centre, strict=True)) - r2
                signs.append(dict(index=i, sign=(gap > 0) - (gap < 0), exact_gap=str(gap)))
        reports.append(
            dict(
                indices=indices,
                exact_degenerate=False,
                circle_signs=signs,
                strictly_inside_indices=[r["index"] for r in signs if r["sign"] < 0],
                cocircular_indices=[r["index"] for r in signs if r["sign"] == 0],
            )
        )
    return dict(
        triangles=reports,
        exact_predicates=True,
        source_topology_is_input=True,
        independent_Delaunay_generation=False,
        topology_qualified=False,
    )


def _accumulate(events, report):
    stack = []
    primitives, trees, triangulations = (
        report[k] for k in ("primitives", "nearest", "triangulations")
    )
    try:
        for event in events:
            report["last_event_sequence"] = event["sequence"]
            kind, name, payload = event["kind"], event["method"], event["payload"]
            if kind == "method_enter":
                stack.append((name, payload["call_parameters"]))
            elif kind in ("method_return", "method_failure"):
                method, parameters = stack.pop()
                if method != name:
                    raise ValueError("Broken native method ordering")
                if kind == "method_return" and method in (
                    "area",
                    "poly_centroid",
                    "circumc",
                    "quad_circumc",
                ):
                    expected, diagnostics = primitive(method, parameters)
                    primitives.append(
                        dict(
                            sequence=event["sequence"],
                            method=method,
                            expected_result=expected,
                            diagnostics=diagnostics,
                        )
                    )
            elif kind == "nearest_query":
                trees.append(dict(sequence=event["sequence"], expected=nearest(payload)))
            elif kind == "delaunay_output":
                triangulations.append(
                    dict(sequence=event["sequence"], diagnostic=delaunay_diagnostic(payload))
                )
        if stack:
            raise ValueError("Unclosed native method trace")
    except Exception as error:
        report.update(
            status="retained_reference_failure",
            open_methods=[name for name, _ in stack],
            failure=dict(type=type(error).__name__, message=str(error)),
        )
        raise ReferenceFailure(error, serial(report)) from error


def evaluate(events, *, refinement=1):
    """Input event payloads are ordinary values, decoded outside this reference."""
    if refinement not in (1, 2):
        raise ValueError("Require the two declared independent precision settings")
    with localcontext() as context:
        context.prec = 100 if refinement == 1 else 160
        report = dict(
            precision=context.prec,
            primitives=[],
            nearest=[],
            triangulations=[],
            last_event_sequence=None,
            status="reference_complete",
            topology_qualified=False,
            physical_area_or_volume_claim=False,
        )
        _accumulate(events, report)
        return serial(report)
