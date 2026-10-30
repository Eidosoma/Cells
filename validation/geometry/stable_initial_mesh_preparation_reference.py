"""Independent supplied-mesh geometry: integers/Decimal, no production imports.

References are computed on the supplied coordinates and incidence. Neither a
new triangulation nor a canonical Qhull tie ordering is invented here.
"""

import hashlib
import json
import sys
from collections import Counter, defaultdict
from decimal import Decimal, localcontext

from validation.geometry import stable_geometry_primitives_checks as primitive_checks
from validation.geometry import stable_geometry_primitives_reference as primitive_reference


def _hex(points):
    return [[float(v).hex() for v in row] for row in points]


def _grid(polygons):
    ratios = [
        [[(float(v).as_integer_ratio()) for v in point] for point in polygon]
        for polygon in polygons
    ]
    scale = max((d for polygon in ratios for point in polygon for _, d in point), default=1)
    return [
        [tuple(n * (scale // d) for n, d in point) for point in polygon] for polygon in ratios
    ], scale


def _cross(a, b):
    return a[0] * b[1] - b[0] * a[1]


def _orient(a, b, c):
    return _cross((b[0] - a[0], b[1] - a[1]), (c[0] - a[0], c[1] - a[1]))


def _edges(points):
    return list(zip(points, points[1:] + points[:1], strict=True))


def _on(a, b, p):
    return _orient(a, b, p) == 0 and all(
        min(x, y) <= z <= max(x, y) for x, y, z in zip(a, b, p, strict=True)
    )


def _inside(point, polygon):
    winding = 0
    for a, b in _edges(polygon):
        if _on(a, b, point):
            return 0
        if a[1] <= point[1] < b[1] and _orient(a, b, point) > 0:
            winding += 1
        if b[1] <= point[1] < a[1] and _orient(a, b, point) < 0:
            winding -= 1
    return 1 if winding else -1


def _proper_cross(a, b, c, d):
    return _orient(a, b, c) * _orient(a, b, d) < 0 and _orient(c, d, a) * _orient(c, d, b) < 0


def _overlap(a, b, c, d):
    if _orient(a, b, c) or _orient(a, b, d):
        return False
    axis = 0 if a[0] != b[0] else 1
    return max(min(a[axis], b[axis]), min(c[axis], d[axis])) < min(
        max(a[axis], b[axis]), max(c[axis], d[axis])
    )


def _hull(points):
    points = sorted(set(points))
    if len(points) < 3:
        return points
    chains = []
    for sequence in (points, list(reversed(points))):
        chain = []
        for point in sequence:
            while len(chain) >= 2 and _orient(chain[-2], chain[-1], point) <= 0:
                chain.pop()
            chain.append(point)
        chains.append(chain[:-1])
    return chains[0] + chains[1]


def complex_geometry(polygons, *, label):
    """Exact incidence, intersection, disjoint-interior and boundary checks.

    Boundary cancellation alone is only an accounting identity. It is combined
    with independent ring, crossing, overlap, edge-incidence and degree checks.
    Signed zero is mathematically the same coordinate on the integer grid.
    """
    grid, scale = _grid(polygons)
    issues, areas2, incidence = [], [], defaultdict(list)
    for owner, points in enumerate(grid):
        area2 = sum(_cross(a, b) for a, b in _edges(points))
        areas2.append(area2)
        if len(points) < 3 or len(set(points)) != len(points) or area2 <= 0:
            issues.append(dict(kind="invalid_or_nonpositive_ring", owner=owner))
        for edge_i, (a, b) in enumerate(_edges(points)):
            incidence[tuple(sorted((a, b)))].append((owner, a, b))
            for j, (c, d) in enumerate(_edges(points)):
                if j <= edge_i or j in ((edge_i + 1) % len(points), (edge_i - 1) % len(points)):
                    continue
                if _proper_cross(a, b, c, d) or any(
                    (_on(a, b, c), _on(a, b, d), _on(c, d, a), _on(c, d, b))
                ):
                    issues.append(
                        dict(kind="self_intersection_or_touch", owner=owner, edges=[edge_i, j])
                    )
    boundary = []
    for edge, owners in incidence.items():
        if len(owners) == 1:
            boundary.append(owners[0])
        elif (
            len(owners) != 2
            or owners[0][0] == owners[1][0]
            or owners[0][1:] != tuple(reversed(owners[1][1:]))
        ):
            issues.append(
                dict(
                    kind="nonmanifold_or_same_direction_edge",
                    edge=[list(p) for p in edge],
                    owners=[v[0] for v in owners],
                )
            )
    incoming, outgoing = Counter(), Counter()
    for _, a, b in boundary:
        outgoing[a] += 1
        incoming[b] += 1
    for vertex in set(incoming) | set(outgoing):
        if incoming[vertex] != 1 or outgoing[vertex] != 1:
            issues.append(
                dict(
                    kind="boundary_degree",
                    vertex=list(vertex),
                    incoming=incoming[vertex],
                    outgoing=outgoing[vertex],
                )
            )
    for i, polygon in enumerate(grid):
        for j in range(i + 1, len(grid)):
            other = grid[j]
            crosses = any(
                _proper_cross(a, b, c, d) for a, b in _edges(polygon) for c, d in _edges(other)
            )
            containment = any(_inside(p, other) == 1 for p in polygon) or any(
                _inside(p, polygon) == 1 for p in other
            )
            same_side = any(
                _overlap(a, b, c, d)
                and (b[0] - a[0]) * (d[0] - c[0]) + (b[1] - a[1]) * (d[1] - c[1]) > 0
                for a, b in _edges(polygon)
                for c, d in _edges(other)
            )
            duplicate = set(_edges(polygon)) == set(_edges(other))
            if crosses or containment or same_side or duplicate:
                issues.append(
                    dict(
                        kind="interior_overlap",
                        owners=[i, j],
                        crossing=crosses,
                        containment=containment,
                        same_side_shared_segment=same_side,
                        duplicate=duplicate,
                    )
                )
    boundary_area2 = sum(_cross(a, b) for _, a, b in boundary)
    if boundary_area2 != sum(areas2):
        issues.append(dict(kind="oriented_boundary_area_mismatch"))
    # Check boundary intersections independently of face interiors.
    for i, (_, a, b) in enumerate(boundary):
        for _, c, d in boundary[i + 1 :]:
            if _proper_cross(a, b, c, d) or _overlap(a, b, c, d):
                issues.append(
                    dict(
                        kind="boundary_crossing_or_overlap",
                        segments=[[list(a), list(b)], [list(c), list(d)]],
                    )
                )
    return dict(
        label=label,
        polygon_count=len(grid),
        unique_edges=len(incidence),
        boundary_edges=len(boundary),
        exact_integer_scale=str(scale),
        face_signed_double_area_integer=[str(v) for v in areas2],
        summed_signed_double_area_integer=str(sum(areas2)),
        boundary_signed_double_area_integer=str(boundary_area2),
        denominator_for_double_area=str(scale * scale),
        disjoint_interiors_checked=True,
        oriented_incidence_checked=True,
        boundary_degree_and_intersections_checked=True,
        issues=issues,
        passed=not issues,
        topology_generated=False,
        topology_qualified=False,
    )


def _incircle(a, b, c, p):
    x, y, z = [(q[0] - p[0], q[1] - p[1]) for q in (a, b, c)]
    norms = [v[0] ** 2 + v[1] ** 2 for v in (x, y, z)]
    determinant = norms[0] * _cross(y, z) - norms[1] * _cross(x, z) + norms[2] * _cross(x, y)
    return determinant * (1 if _orient(a, b, c) > 0 else -1)


def delaunay_geometry(events):
    reports = []
    for event in events:
        if event["kind"] != "delaunay_output":
            continue
        payload = event["payload"]
        grid, scale = _grid([payload["points"]])
        points, rows = grid[0], []
        for simplex in payload["simplices"]:
            vertices = [points[int(i)] for i in simplex]
            inside, ties = [], []
            for i, p in enumerate(points):
                if i in simplex:
                    continue
                sign = _incircle(*vertices, p)
                if sign > 0:
                    inside.append(i)
                elif sign == 0:
                    ties.append(i)
            rows.append(
                dict(
                    simplex=simplex,
                    exactly_collinear=_orient(*vertices) == 0,
                    strict_inside_occurrences=inside,
                    cocircular_ties=ties,
                )
            )
        reports.append(
            dict(
                sequence=event["sequence"],
                integer_scale=str(scale),
                supplied_simplex_checks=rows,
                empty_circle_passed=all(
                    not row["exactly_collinear"] and not row["strict_inside_occurrences"]
                    for row in rows
                ),
                canonical_tie_order_claimed=False,
            )
        )
    return reports


def _indices(row, bound):
    return isinstance(row, list) and all(type(i) is int and 0 <= i < bound for i in row)


def ownership(cache):
    findings = []

    def check(label, condition):
        findings.append(dict(check=label, passed=bool(condition)))

    points, cells = cache.get("tri_verts", []), cache.get("tri_cells", [])
    dual_points, dual_cells = cache.get("vor_verts", []), cache.get("vor_cells", [])
    check(
        "primal_counts", cache.get("n_tverts") == len(points) and cache.get("n_tcell") == len(cells)
    )
    check(
        "dual_counts_and_seed_owners",
        cache.get("n_vverts") == len(dual_points)
        and cache.get("n_vcells") == len(dual_cells) == len(points),
    )
    primal_valid = all(_indices(row, len(points)) and len(row) in (3, 4) for row in cells)
    dual_valid = all(_indices(row, len(dual_points)) and 3 <= len(row) <= 64 for row in dual_cells)
    check("primal_cell_indices", primal_valid)
    check("dual_cell_indices", dual_valid)
    if primal_valid:
        check(
            "primal_polygon_cache_ownership",
            cache.get("tcell_verts") == [[points[i] for i in row] for row in cells],
        )
        check(
            "vertex_to_cell_incidence",
            cache.get("_tverts_to_tcell")
            == [[ci for ci, row in enumerate(cells) if vi in row] for vi in range(len(points))],
        )
    if dual_valid:
        check(
            "dual_polygon_cache_ownership",
            cache.get("vcell_verts") == [[dual_points[i] for i in row] for row in dual_cells],
        )
    edges = cache.get("tri_edges", [])
    edges_valid = all(
        _indices(row, len(points)) and len(row) == 2 and row[0] != row[1] for row in edges
    )
    check("primal_edge_indices", edges_valid)
    if primal_valid and edges_valid:
        owners = defaultdict(list)
        for ci, row in enumerate(cells):
            for a, b in _edges(row):
                owners[tuple(sorted((a, b)))].append(ci)
        edge_lookup = {tuple(sorted(edge)): ei for ei, edge in enumerate(edges)}
        check(
            "primal_unique_edge_coverage",
            len(edge_lookup) == len(edges) == cache.get("n_tedges")
            and set(edge_lookup) == set(owners),
        )
        expected_faces = [
            [edge_lookup.get(tuple(sorted(edge)), -1) for edge in _edges(row)] for row in cells
        ]
        # Incidence is set-valued mathematically. Exact native list ordering is
        # checked separately by the conditional source replay.
        check(
            "face_to_edge_geometric_incidence",
            [sorted(row) for row in cache.get("tcell_to_tedges", [])]
            == [sorted(row) for row in expected_faces],
        )
        check(
            "edge_to_face_geometric_incidence",
            [sorted(row) for row in cache.get("tedges_to_tcell", [])]
            == [sorted(owners.get(tuple(sorted(edge)), [])) for edge in edges],
        )
        check(
            "vertex_to_edge_geometric_incidence",
            [sorted(row) for row in cache.get("tverts_to_tedges", [])]
            == [[ei for ei, edge in enumerate(edges) if vi in edge] for vi in range(len(points))],
        )
        boundary = {ei for ei, edge in enumerate(edges) if len(owners[tuple(sorted(edge))]) == 1}
        check("primal_boundary_edge_flags", set(cache.get("bflags_tedges", [])) == boundary)
        check(
            "primal_boundary_vertex_flags",
            set(cache.get("bflags_tverts", [])) == {i for ei in boundary for i in edges[ei]},
        )
        check(
            "primal_interior_edge_partition",
            set(cache.get("inner_tedge_i", [])) == set(range(len(edges))) - boundary,
        )
    selected = cache.get("vor_edges", [])
    selected_valid = all(
        _indices(row, len(dual_points)) and len(row) == 2 and row[0] != row[1] for row in selected
    )
    check(
        "selected_dual_edge_indices_and_count",
        selected_valid and cache.get("n_vedges") == len(selected) == len(edges),
    )
    if dual_valid and selected_valid:
        dual_complex = {tuple(sorted(edge)) for row in dual_cells for edge in _edges(row)}
        keys = [tuple(sorted(edge)) for edge in selected]
        check(
            "selected_dual_edges_belong_to_cell_complex", all(edge in dual_complex for edge in keys)
        )
        check("selected_dual_edges_not_duplicated", len(set(keys)) == len(keys))
    return findings


def _fraction(value):
    # Keep a finite sortable display and the full ratio separately. Saturation
    # never affects the Decimal acceptance comparison.
    return float(min(value, Decimal.from_float(sys.float_info.max)))


def _comparison(label, actual, expected, *, area=False, dimensionless=False):
    value = Decimal.from_float(float(actual))
    truth = Decimal(expected)
    floor = Decimal("1e-14" if dimensionless else "1e-26" if area else "1e-27")
    budget = floor + Decimal("6e-12") * abs(truth)
    error = abs(value - truth)
    return dict(
        label=label,
        actual_binary64_hex=float(actual).hex(),
        reference_decimal=str(truth),
        absolute_error_decimal=str(error),
        budget_decimal=str(budget),
        error_fraction=_fraction(error / budget),
        error_fraction_decimal=str(error / budget),
        passed=bool(error <= budget),
    )


def _edge_geometry(cache, prefix):
    points = [[Decimal.from_float(float(v)) for v in p] for p in cache[prefix + "_verts"]]
    rows = []
    for ei, (a, b) in enumerate(cache[prefix + "_edges"]):
        pa, pb = points[a], points[b]
        delta = [y - x for x, y in zip(pa, pb, strict=True)]
        length = sum((v * v for v in delta), Decimal(0)).sqrt()
        if not length:
            rows.append(
                dict(label=f"{prefix}_edge_{ei}_nonzero", passed=False, error_fraction=None)
            )
            continue
        rows.append(
            _comparison(f"{prefix}_edge_{ei}_length", cache[prefix + "_edge_len"][ei], length)
        )
        for axis in (0, 1):
            rows.append(
                _comparison(
                    f"{prefix}_edge_{ei}_mid_{axis}",
                    cache[prefix + "_mids"][ei][axis],
                    (pa[axis] + pb[axis]) / 2,
                )
            )
            rows.append(
                _comparison(
                    f"{prefix}_edge_{ei}_tangent_{axis}",
                    cache[prefix + "_tang"][ei][axis],
                    delta[axis] / length,
                    dimensionless=True,
                )
            )
    return rows


def _dual_pairing(cache):
    points, cells, edges = cache["tri_verts"], cache["tri_cells"], cache["tri_edges"]
    centers = cache["tri_cents" if cache["use_centroids"] else "tri_ccents"]
    rows = []
    for ei, (a, b) in enumerate(edges):
        owners = [
            ci
            for ci, cell in enumerate(cells)
            if a in cell
            and b in cell
            and tuple(sorted((a, b))) in {tuple(sorted(edge)) for edge in _edges(cell)}
        ]
        if len(owners) == 2:
            expected = [centers[i] for i in owners]
        elif len(owners) == 1:
            center = centers[owners[0]]
            # Independent exact reflection target; no repeated native mean.
            reflected = [
                Decimal.from_float(float(points[a][axis]))
                + Decimal.from_float(float(points[b][axis]))
                - Decimal.from_float(float(center[axis]))
                for axis in (0, 1)
            ]
            expected = [center, reflected]
        else:
            rows.append(dict(label=f"dual_pair_{ei}_owner_count", passed=False))
            continue
        actual = [cache["vor_verts"][i] for i in cache["vor_edges"][ei]]
        alternatives = []
        for candidate in (expected, list(reversed(expected))):
            alternatives.append(
                [
                    _comparison(f"dual_pair_{ei}_{j}_{axis}", actual[j][axis], candidate[j][axis])
                    for j in (0, 1)
                    for axis in (0, 1)
                ]
            )
        chosen = min(alternatives, key=lambda option: max(row["error_fraction"] for row in option))
        rows.extend(chosen)
        tang_t, tang_v = cache["tri_tang"][ei], cache["vor_tang"][ei]
        sign = Decimal.from_float(float(tang_t[0])) * Decimal.from_float(
            float(tang_v[1])
        ) - Decimal.from_float(float(tang_t[1])) * Decimal.from_float(float(tang_v[0]))
        rows.append(
            dict(
                label=f"dual_pair_{ei}_orientation", determinant_decimal=str(sign), passed=sign <= 0
            )
        )
    return rows


def evaluate(cache, events, *, completed, refinement=1):
    if refinement not in (1, 2):
        raise ValueError("Declared independent refinement required")
    memo = {}

    def primitive(kind, points):
        bits = _hex(points)
        key = (kind, tuple(tuple(p) for p in bits))
        if key not in memo:
            memo[key] = primitive_reference.evaluate(kind, bits, refinement=refinement)
        return memo[key]

    repairs, issues = [], []
    pending = None
    for event in events:
        payload = event["payload"]
        if event["kind"] == "primitive_repair_input":
            if pending is not None:
                issues.append(dict(kind="unclosed_repair_input", sequence=event["sequence"]))
            pending = event
        elif event["kind"] in ("primitive_repair_result", "primitive_repair_failure"):
            if pending is None or pending["method"] != event["method"]:
                raise ValueError("Changed repair event pairing")
            parameters = pending["payload"]["call_parameters"]
            method = event["method"]
            points = (
                [parameters[k] for k in ("A", "B", "C")] if method == "circumc" else parameters["p"]
            )
            kind = "triangle" if method == "circumc" else "polygon"
            if event["kind"] == "primitive_repair_failure":
                try:
                    target = primitive(kind, points)
                except primitive_reference.ReferenceRejected as error:
                    target = dict(independent_refusal=error.code)
                repairs.append(
                    dict(
                        sequence=event["sequence"],
                        method=method,
                        outcome="retained_refusal",
                        failure=payload,
                        reference=target,
                    )
                )
            else:
                if (
                    payload["request"]["points_binary64_hex"] != _hex(points)
                    or payload["request"]["primitive"] != kind
                ):
                    issues.append(
                        dict(kind="changed_repair_input_bits", sequence=event["sequence"])
                    )
                for key in ("request", "result"):
                    digest = hashlib.sha256(
                        json.dumps(
                            payload[key], sort_keys=True, separators=(",", ":"), allow_nan=False
                        ).encode()
                    ).hexdigest()
                    if digest != payload[key + "_identity"]:
                        issues.append(
                            dict(
                                kind="changed_repair_" + key + "_identity",
                                sequence=event["sequence"],
                            )
                        )
                names = {
                    "area": ("signed_area_m2",),
                    "poly_centroid": ("centroid_x_m", "centroid_y_m"),
                    "circumc": (
                        "circumcenter_x_m",
                        "circumcenter_y_m",
                        "circumradius_m",
                        "inradius_m",
                    ),
                }[method]
                values = (
                    [payload["adapter_output"]] if method == "area" else payload["adapter_output"]
                )
                if [float(v).hex() for v in values] != [
                    payload["result"]["quantities_binary64_hex"][name] for name in names
                ]:
                    issues.append(
                        dict(kind="changed_repair_adapter_output", sequence=event["sequence"])
                    )
                repairs.append(
                    dict(
                        sequence=event["sequence"],
                        method=method,
                        outcome="result",
                        actual=payload["result"],
                        reference=primitive(kind, points),
                    )
                )
            pending = None
    if pending is not None:
        issues.append(dict(kind="unclosed_repair_input", sequence=pending["sequence"]))
    report = dict(
        kind="cells.stable_initial_mesh_independent_geometry@1",
        refinement=refinement,
        precision_digits=4096 + (512 if refinement == 2 else 0),
        primitive_repairs=repairs,
        delaunay=delaunay_geometry(events),
        complete_mesh_checked=bool(completed),
        issues=issues,
        source_equivalence_claimed=False,
        topology_generated=False,
        topology_qualified=False,
        physical_geometry_admitted=False,
    )
    if not completed:
        report.update(status="retained_partial_mesh_only", whole_mesh_passed=False)
        return report
    with localcontext() as context:
        context.prec = report["precision_digits"]
        findings = ownership(cache)
        rows, domains = [], []
        for prefix, polygons in (("tri", cache["tcell_verts"]), ("vor", cache["vcell_verts"])):
            for owner, polygon in enumerate(polygons):
                try:
                    target = primitive("polygon", polygon)
                    values = target["values_decimal"]
                    rows.append(
                        _comparison(
                            f"{prefix}_cell_{owner}_area",
                            cache[prefix + "_sa"][owner],
                            values["signed_area_m2"],
                            area=True,
                        )
                    )
                    for axis, name in enumerate(("centroid_x_m", "centroid_y_m")):
                        rows.append(
                            _comparison(
                                f"{prefix}_cell_{owner}_centroid_{axis}",
                                cache[prefix + "_cents"][owner][axis],
                                values[name],
                            )
                        )
                    if prefix == "tri":
                        # A retained quad still uses the unchanged native quad
                        # formula. Test it against a separately computed circle
                        # through its first three supplied vertices.
                        circle = primitive("triangle", polygon[:3])["values_decimal"]
                        for axis, name in enumerate(("circumcenter_x_m", "circumcenter_y_m")):
                            rows.append(
                                _comparison(
                                    f"tri_cell_{owner}_circumcenter_{axis}",
                                    cache["tri_ccents"][owner][axis],
                                    circle[name],
                                )
                            )
                        rows.append(
                            _comparison(
                                f"tri_cell_{owner}_circumradius",
                                cache["tri_rcircs"][owner],
                                circle["circumradius_m"],
                            )
                        )
                        if len(polygon) == 4:
                            cx, cy, radius = (
                                Decimal(circle[name])
                                for name in (
                                    "circumcenter_x_m",
                                    "circumcenter_y_m",
                                    "circumradius_m",
                                )
                            )
                            last = [Decimal.from_float(float(v)) for v in polygon[3]]
                            actual_radius = ((last[0] - cx) ** 2 + (last[1] - cy) ** 2).sqrt()
                            budget = Decimal("1e-27") + Decimal("6e-12") * radius
                            rows.append(
                                dict(
                                    label=f"tri_quad_{owner}_fourth_vertex_circle",
                                    fourth_radius_decimal=str(actual_radius),
                                    reference_radius_decimal=str(radius),
                                    budget_decimal=str(budget),
                                    absolute_error_decimal=str(abs(actual_radius - radius)),
                                    error_fraction=_fraction(abs(actual_radius - radius) / budget),
                                    error_fraction_decimal=str(
                                        abs(actual_radius - radius) / budget
                                    ),
                                    passed=abs(actual_radius - radius) <= budget,
                                )
                            )
                except primitive_reference.ReferenceRejected as error:
                    domains.append(dict(prefix=prefix, owner=owner, code=error.code))
        if all(
            row["passed"]
            for row in findings
            if row["check"] in ("primal_edge_indices", "selected_dual_edge_indices_and_count")
        ):
            rows.extend(_edge_geometry(cache, "tri"))
            rows.extend(_edge_geometry(cache, "vor"))
            rows.extend(_dual_pairing(cache))
        primal = complex_geometry(cache["tcell_verts"], label="retained_primal_complex")
        dual = complex_geometry(cache["vcell_verts"], label="supplied_dual_complex")
        for prefix, complex_report in (("tri", primal), ("vor", dual)):
            actual_sum = sum(
                (Decimal.from_float(float(v)) for v in cache[prefix + "_sa"]), Decimal(0)
            )
            reference_sum = Decimal(complex_report["boundary_signed_double_area_integer"]) / (
                2 * Decimal(complex_report["denominator_for_double_area"])
            )
            budget = Decimal("1e-26") + Decimal("6e-12") * abs(reference_sum)
            error = abs(actual_sum - reference_sum)
            rows.append(
                dict(
                    label=prefix + "_cached_area_sum_vs_independent_boundary",
                    actual_sum_decimal=str(actual_sum),
                    reference_decimal=str(reference_sum),
                    budget_decimal=str(budget),
                    absolute_error_decimal=str(error),
                    error_fraction=_fraction(error / budget),
                    error_fraction_decimal=str(error / budget),
                    passed=error <= budget,
                )
            )
        all_points_grid, scale = _grid([cache["tri_verts"], *cache["tcell_verts"]])
        hull = _hull(all_points_grid[0])
        hull_area2 = sum(_cross(a, b) for a, b in _edges(hull))
        face_area2 = sum(sum(_cross(a, b) for a, b in _edges(p)) for p in all_points_grid[1:])
        hull_check = dict(
            required=not cache["use_alpha_shape"],
            integer_scale=str(scale),
            hull_signed_double_area_integer=str(hull_area2),
            retained_signed_double_area_integer=str(face_area2),
            passed=cache["use_alpha_shape"] or hull_area2 == face_area2,
            alpha_holes_not_relabelled_as_hull_coverage=True,
        )
        report.update(
            ownership_checks=findings,
            geometry_quantities=rows,
            primitive_domain_failures=domains,
            primal_complex=primal,
            dual_complex=dual,
            hull_area_check=hull_check,
            maximum_error_fraction=max(
                (row.get("error_fraction", 0) or 0 for row in rows), default=0
            ),
            whole_mesh_passed=not issues
            and not domains
            and all(row["passed"] for row in findings + rows)
            and primal["passed"]
            and dual["passed"]
            and hull_check["passed"]
            and all(r["empty_circle_passed"] for r in report["delaunay"]),
            status="independent_complete_mesh_checked",
        )
    return report


def compare_repairs(primary, refined):
    rows = []
    for a, b in zip(primary["primitive_repairs"], refined["primitive_repairs"], strict=True):
        assert (a["sequence"], a["method"], a["outcome"]) == (
            b["sequence"],
            b["method"],
            b["outcome"],
        )
        if a["outcome"] == "result":
            rows.append(
                dict(
                    sequence=a["sequence"],
                    method=a["method"],
                    **primitive_checks.compare(a["actual"], a["reference"], b["reference"]),
                )
            )
        else:
            assert a["failure"] == b["failure"]
            if "independent_refusal" in a["reference"]:
                assert a["reference"] == b["reference"]
            else:
                # A representability/platform/bounded-rounding refusal may be
                # retained even when the independent mathematical input exists.
                assert a["failure"]["failure_type"] == "GeometryRejected"
            rows.append(
                dict(
                    sequence=a["sequence"],
                    method=a["method"],
                    retained_refusal=True,
                    mathematical_success_not_adapter_acceptance=True,
                )
            )
    return rows


def compare_whole_mesh(primary, refined):
    assert primary["complete_mesh_checked"] == refined["complete_mesh_checked"]
    assert primary["issues"] == refined["issues"]
    assert primary["delaunay"] == refined["delaunay"]
    if not primary["complete_mesh_checked"]:
        return dict(
            complete_mesh_checked=False, whole_mesh_passed=False, partial_failure_preserved=True
        )
    for key in (
        "ownership_checks",
        "primitive_domain_failures",
        "primal_complex",
        "dual_complex",
        "hull_area_check",
    ):
        assert primary[key] == refined[key], key
    maximum = 0.0
    with localcontext() as context:
        context.prec = max(primary["precision_digits"], refined["precision_digits"]) + 128
        for a, b in zip(
            primary["geometry_quantities"], refined["geometry_quantities"], strict=True
        ):
            assert a["label"] == b["label"]
            if "reference_decimal" in a:
                key = "actual_binary64_hex" if "actual_binary64_hex" in a else "actual_sum_decimal"
                assert a[key] == b[key]
                difference = abs(Decimal(a["reference_decimal"]) - Decimal(b["reference_decimal"]))
                fraction = difference / Decimal(a["budget_decimal"])
                assert fraction <= Decimal("0.1"), (a["label"], str(fraction))
                maximum = max(maximum, float(fraction))
            elif "fourth_radius_decimal" in a:
                for key in ("fourth_radius_decimal", "reference_radius_decimal"):
                    difference = abs(Decimal(a[key]) - Decimal(b[key]))
                    fraction = difference / Decimal(a["budget_decimal"])
                    assert fraction <= Decimal("0.1"), (a["label"], key, str(fraction))
                    maximum = max(maximum, float(fraction))
            assert a["passed"] == b["passed"], a["label"]
    assert primary["whole_mesh_passed"] == refined["whole_mesh_passed"]
    return dict(
        complete_mesh_checked=True,
        whole_mesh_passed=primary["whole_mesh_passed"],
        maximum_error_fraction=primary["maximum_error_fraction"],
        maximum_reference_resolution_fraction=maximum,
        failed_ownership_checks=[
            r["check"] for r in primary["ownership_checks"] if not r["passed"]
        ],
        failed_geometry_quantities=[
            r["label"] for r in primary["geometry_quantities"] if not r["passed"]
        ],
        primal_issues=primary["primal_complex"]["issues"],
        dual_issues=primary["dual_complex"]["issues"],
        primitive_domain_failures=primary["primitive_domain_failures"],
        exact_native_arithmetic_equivalence=False,
        topology_qualified=False,
        physical_geometry_admitted=False,
    )
