"""Independent geometry diagnostics on source topology, with bounded mask scope."""

from decimal import Decimal, localcontext
from fractions import Fraction

from validation.betse import betse_image_mask_prelude_reference as image_reference
from validation.betse import betse_initial_mesh_preparation_reference as mesh_reference


class ReferenceFailure(ValueError):
    def __init__(self, error, trial):
        super().__init__("Clipping reference failed: " + str(error))
        self.trial = trial


def f(value):
    return Fraction(float(value))


def decimal(value):
    return Decimal(value.numerator) / Decimal(value.denominator)


def point(values):
    return tuple(f(v) for v in values)


def cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def line_intersection(a, b, c, d):
    ab = (b[0] - a[0], b[1] - a[1])
    cd = (d[0] - c[0], d[1] - c[1])
    denominator = ab[0] * cd[1] - ab[1] * cd[0]
    if not denominator:
        return None
    ca = (c[0] - a[0], c[1] - a[1])
    scale = (ca[0] * cd[1] - ca[1] * cd[0]) / denominator
    return (a[0] + scale * ab[0], a[1] + scale * ab[1])


def hull(points):
    values = sorted(set(points))
    if len(values) < 3:
        return values
    halves = []
    for ordered in (values, list(reversed(values))):
        half = []
        for p in ordered:
            while len(half) >= 2 and cross(half[-2], half[-1], p) <= 0:
                half.pop()
            half.append(p)
        halves.append(half[:-1])
    return halves[0] + halves[1]


def convex_ccw(points):
    if len(points) < 3:
        return False
    turns = [
        cross(points[i - 1], points[i], points[(i + 1) % len(points)]) for i in range(len(points))
    ]
    return all(v >= 0 for v in turns) and any(v > 0 for v in turns)


def closed_convex_intersection(subject, clip):
    """All line-pair candidates filtered by exact closed half-planes.

    This differs from the source edge-by-edge clipping procedure. Topology and
    polygons remain inputs, and this routine certifies no generated topology.
    """
    a, b = [point(p) for p in subject], [point(p) for p in clip]
    if not convex_ccw(a) or not convex_ccw(b):
        return dict(supported=False, reason="Requires convex counterclockwise input polygons")
    edges = [(p[i - 1], p[i]) for p in (a, b) for i in range(len(p))]
    candidates = a + b
    for i, (u, v) in enumerate(edges):
        for w, z in edges[:i]:
            p = line_intersection(u, v, w, z)
            if p is not None:
                candidates.append(p)
    polygon = hull(p for p in candidates if all(cross(u, v, p) >= 0 for u, v in edges))
    twice_area = sum(
        (
            polygon[i - 1][0] * polygon[i][1] - polygon[i - 1][1] * polygon[i][0]
            for i in range(len(polygon))
        ),
        Fraction(0),
    )
    return dict(
        supported=True,
        source_polygons_are_input=True,
        exact_vertices=[[str(x), str(y)] for x, y in polygon],
        vertices_m=[[decimal(x), decimal(y)] for x, y in polygon],
        exact_signed_area_m2=str(twice_area / 2),
        signed_area_m2=decimal(twice_area / 2),
        boundary_rule="Independent closed convex intersection; source uses strict side tests",
    )


def helper_report(method, parameters, observed):
    if method == "is_left_of_vector":
        sign = cross(
            point(parameters["vector_tail_point"]),
            point(parameters["vector_head_point"]),
            point(parameters["subject_point"]),
        )
        return dict(
            kind="exact_binary_input_half_plane",
            exact_cross=str(sign),
            exact_strict_side=sign > 0,
            observed_source_side=bool(observed),
            predicate_agrees=(sign > 0) == bool(observed),
            disagreement_is_diagnostic_no_predicate_rewrite=True,
        )
    if method == "intersect_lines":
        p = line_intersection(
            *(
                point(parameters[k])
                for k in ("line1_point1", "line1_point2", "line2_point1", "line2_point2")
            )
        )
        return dict(
            kind="exact_binary_input_line_intersection",
            exact_unique=p is not None,
            exact_point=None if p is None else [str(v) for v in p],
            expected_point_m=None if p is None else [decimal(v) for v in p],
        )
    if method == "clip_counterclockwise":
        report = closed_convex_intersection(
            parameters["subject_polygon"], parameters["clip_polygon"]
        )
        report["source_result_signed_area_m2"] = mesh_reference.polygon(observed)[0]
        report["source_result_is_final_rebuilt_polygon"] = False
        return report
    if method == "search_point_cloud":
        points, cloud = (
            [point(v) for v in parameters["pts"]],
            [point(v) for v in parameters["pt_cloud"]],
        )
        threshold = f(1e-15) ** 2
        pairs = [
            (i, j)
            for i, a in enumerate(points)
            for j, b in enumerate(cloud)
            if sum((x - y) ** 2 for x, y in zip(a, b, strict=True)) < threshold
        ]
        return dict(
            kind="exact_binary_input_point_cloud_distances",
            threshold_m="1e-15",
            exact_matching_occurrence_pairs=pairs,
            empty_cloud_source_returns_two_empty_lists=not cloud,
            source_deduplicates_matches=False,
            independent_source_tie_order_claim=False,
        )
    return None


def evaluate_helper(method, parameters, observed, *, refinement=1):
    if refinement not in (1, 2):
        raise ValueError("Require declared independent helper precision")
    report = dict(
        method=method,
        classification="isolated_manufactured_helper_diagnostics",
        topology_qualified=False,
        downstream_geometry_admitted=False,
    )
    try:
        with localcontext() as context:
            context.prec = 100 if refinement == 1 else 160
            report.update(
                precision=context.prec, diagnostic=helper_report(method, parameters, observed)
            )
            return mesh_reference.serial(report)
    except Exception as error:
        report.update(
            status="retained_reference_failure",
            failure=dict(type=type(error).__name__, message=str(error)),
        )
        raise ReferenceFailure(error, mesh_reference.serial(report)) from error


def binary_coefficients(mask):
    rows = mask["clipping_matrix"]
    if len(rows) != len(mask["ypts_m"]) or any(len(row) != len(mask["xpts_m"]) for row in rows):
        raise ValueError("Captured binary mask dimensions differ from its grid")
    if any(type(value) not in (int, float) or value not in (0, 1) for row in rows for value in row):
        raise ValueError("Require exact numeric0/1 coefficients, with no coercion or tolerance")
    # Captured np.float64 masks become Python floats. Validate their exact
    # binary domain before passing integer coefficients to the qualified
    # Decimal bilinear helper. That helper itself remains unchanged.
    return [[int(value) for value in row] for row in rows]


def evaluate(events, mask, *, refinement=1):
    if refinement not in (1, 2):
        raise ValueError("Require declared Decimal100/160 refinement")
    report = dict(
        source_geometry=None,
        helper_diagnostics=[],
        mask_queries=[],
        emitted_polygon_diagnostics=[],
        topology_qualified=False,
        downstream_geometry_admitted=False,
        source_topology_is_input=True,
        independent_topology_generation=False,
        outside_window_mask_independent_claim=False,
    )
    try:
        coefficients = binary_coefficients(mask)
        report["binary_mask_coefficients_validated"] = True
        report["source_geometry"] = mesh_reference.evaluate(events, refinement=refinement)
        with localcontext() as context:
            context.prec = 100 if refinement == 1 else 160
            report["precision"] = context.prec
            x, y = (
                [image_reference.d(v) for v in mask["xpts_m"]],
                [image_reference.d(v) for v in mask["ypts_m"]],
            )
            stack = []
            for event in events:
                report["last_event_sequence"] = event["sequence"]
                kind, name, payload = event["kind"], event["method"], event["payload"]
                if kind == "method_enter":
                    stack.append((name, payload["call_parameters"]))
                elif kind in ("method_return", "method_failure"):
                    method, parameters = stack.pop()
                    if method != name:
                        raise ValueError("Unbalanced clipping method trace")
                    if kind == "method_return":
                        diagnostic = helper_report(method, parameters, payload.get("result"))
                        if diagnostic is not None:
                            report["helper_diagnostics"].append(
                                dict(
                                    sequence=event["sequence"], method=method, diagnostic=diagnostic
                                )
                            )
                elif kind == "mask_query":
                    qx, qy = image_reference.d(payload["x"]), image_reference.d(payload["y"])
                    within = x[0] <= qx <= x[-1] and y[0] <= qy <= y[-1]
                    expected = (
                        image_reference._linear(x, y, coefficients, qx, qy) if within else None
                    )
                    observed = float(payload["result"][0][0])
                    report["mask_queries"].append(
                        dict(
                            sequence=event["sequence"],
                            within_closed_window=within,
                            independent_value=expected,
                            observed_value=observed,
                            observed_source_nonzero=observed != 0,
                            independent_nonzero=None if expected is None else expected != 0,
                            predicate_agrees=None
                            if expected is None
                            else (expected != 0) == (observed != 0),
                            outside_scope="Native-only spline query outside closed image window"
                            if not within
                            else None,
                        )
                    )
                elif kind == "clip_centroid_emitted":
                    area, centroid = mesh_reference.polygon(payload["polygon"])
                    report["emitted_polygon_diagnostics"].append(
                        dict(
                            sequence=event["sequence"],
                            parent_id=payload["parent_id"],
                            point_id=payload["point_id"],
                            branch=payload["branch"],
                            signed_area_m2=area,
                            centroid_m=centroid,
                            is_exact_mask_intersection_claim=False,
                            is_final_rebuilt_polygon_claim=False,
                        )
                    )
            if stack:
                raise ValueError("Unclosed clipping method trace")
            report["predicate_disagreements_are_retained"] = True
            report["status"] = "diagnostics_complete"
            return mesh_reference.serial(report)
    except Exception as error:
        if isinstance(error, mesh_reference.ReferenceFailure):
            report["source_geometry"] = error.trial
        report.update(
            status="retained_reference_failure",
            failure=dict(type=type(error).__name__, message=str(error)),
        )
        raise ReferenceFailure(error, mesh_reference.serial(report)) from error
