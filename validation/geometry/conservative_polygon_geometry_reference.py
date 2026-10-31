"""Independent integer-grid polygon/owner checks and full Decimal targets.

No production imports or Fraction arithmetic. Global moments and an independent
ear decomposition check the supplied polygons; no Voronoi/Delaunay claim is made.
"""

import hashlib
import json
import math
import struct
from collections import Counter, defaultdict
from decimal import Decimal, localcontext

from validation.geometry import stable_geometry_primitives_reference as rounding


class ReferenceRejected(ValueError):
    pass


def _hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _ratio(n, d=1):
    if d == 0:
        raise ReferenceRejected("zero_ratio_denominator")
    if d < 0:
        n, d = -n, -d
    common = math.gcd(n, d)
    return dict(numerator=str(n // common), denominator=str(d // common))


def _pair(row):
    return int(row["numerator"]), int(row["denominator"])


def _decimal(row):
    n, d = _pair(row)
    return Decimal(n) / Decimal(d)


def _mul(a, b):
    an, ad = _pair(a)
    bn, bd = _pair(b)
    return _ratio(an * bn, ad * bd)


def _float_ratio(value):
    return _ratio(*float(value).as_integer_ratio())


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _orient(a, b, c):
    return _cross((b[0] - a[0], b[1] - a[1]), (c[0] - a[0], c[1] - a[1]))


def _edges(ring):
    return list(zip(ring, ring[1:] + ring[:1], strict=True))


def _on(a, b, p):
    return (
        _orient(a, b, p) == 0
        and min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
        and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])
    )


def _location(p, polygon):
    # Even/odd ray crossings, separate from the production winding accumulator.
    parity = False
    for a, b in _edges(polygon):
        if _on(a, b, p):
            return 0
        if (a[1] > p[1]) != (b[1] > p[1]):
            determinant = _orient(a, b, p)
            if (determinant > 0) == (b[1] > a[1]):
                parity = not parity
    return 1 if parity else -1


def _intersections(a, b, c, d):
    proper = _orient(a, b, c) * _orient(a, b, d) < 0 and _orient(c, d, a) * _orient(c, d, b) < 0
    overlap = False
    if _orient(a, b, c) == _orient(a, b, d) == 0:
        axis = int(a[0] == b[0])
        overlap = max(min(a[axis], b[axis]), min(c[axis], d[axis])) < min(
            max(a[axis], b[axis]), max(c[axis], d[axis])
        )
    touch = any((_on(a, b, c), _on(a, b, d), _on(c, d, a), _on(c, d, b)))
    return proper, overlap, touch


def _ear_decomposition(points):
    active = list(points)
    removed = []
    changed = True
    while changed and len(active) > 3:
        changed = False
        for i, p in enumerate(active):
            before, after = active[i - 1], active[(i + 1) % len(active)]
            if _orient(before, p, after) == 0:
                if not _on(before, after, p):
                    raise ReferenceRejected("collinear_backtrack")
                removed.append(p)
                active.pop(i)
                changed = True
                break
    triangles = []
    while len(active) > 3:
        found = False
        for i, b in enumerate(active):
            a, c = active[i - 1], active[(i + 1) % len(active)]
            if _orient(a, b, c) <= 0:
                continue
            if any(
                all(v >= 0 for v in (_orient(a, b, p), _orient(b, c, p), _orient(c, a, p)))
                for p in active
                if p not in (a, b, c)
            ):
                continue
            triangles.append((a, b, c))
            active.pop(i)
            found = True
            break
        if not found:
            raise ReferenceRejected("no_simple_polygon_ear")
    if len(active) != 3 or _orient(*active) <= 0:
        raise ReferenceRejected("degenerate_final_ear")
    triangles.append(tuple(active))
    return triangles, removed


def _polygon(points, scale):
    if len(points) < 3 or len(set(points)) != len(points):
        raise ReferenceRejected("polygon_vertex_axis")
    weights = [_cross(a, b) for a, b in _edges(points)]
    area2 = sum(weights)
    if area2 <= 0:
        raise ReferenceRejected("polygon_orientation_or_area")
    for i, (a, b) in enumerate(_edges(points)):
        for j, (c, d) in enumerate(_edges(points)):
            if j <= i:
                continue
            proper, overlap, touch = _intersections(a, b, c, d)
            if (
                proper
                or overlap
                or (touch and j not in ((i + 1) % len(points), (i - 1) % len(points)))
            ):
                raise ReferenceRejected("polygon_not_simple")
    triangles, collinear = _ear_decomposition(points)
    if sum(_orient(a, b, c) for a, b, c in triangles) != area2:
        raise ReferenceRejected("ear_area_not_global_green_area")
    # Ear moments are an independent dissection identity, not the production
    # translated fan. Retain exact global moment targets below.
    moments = [
        sum((a[axis] + b[axis]) * w for (a, b), w in zip(_edges(points), weights, strict=True))
        for axis in (0, 1)
    ]
    ear_moments = [
        sum((a[axis] + b[axis] + c[axis]) * _orient(a, b, c) for a, b, c in triangles)
        for axis in (0, 1)
    ]
    if moments != ear_moments:
        raise ReferenceRejected("ear_centroid_not_global_green_centroid")
    return dict(
        area=_ratio(area2, 2 * scale * scale),
        centroid=[_ratio(m, 3 * area2 * scale) for m in moments],
        signed_double_area_integer=str(area2),
        ear_count=len(triangles),
        collinear_vertices_removed_in_reference_only=len(collinear),
    )


def _complex(vertices, cells, scale):
    ids = [row["id"] for row in cells]
    if len(ids) != len(set(ids)):
        raise ReferenceRejected("duplicate_cell")
    incidence = defaultdict(list)
    polygons = []
    measures = {}
    for row in cells:
        ring = row["vertex_ids"]
        if not 3 <= len(ring) <= 256 or any(v not in vertices for v in ring):
            raise ReferenceRejected("unknown_ring_vertex")
        points = [vertices[v] for v in ring]
        measures[row["id"]] = _polygon(points, scale)
        polygons.append(points)
        for a, b in _edges(ring):
            coordinate_edge = tuple(sorted((vertices[a], vertices[b])))
            incidence[coordinate_edge].append((row["id"], a, b))
    for owners in incidence.values():
        if len(owners) > 2 or (
            len(owners) == 2
            and (owners[0][0] == owners[1][0] or owners[0][1:] != tuple(reversed(owners[1][1:])))
        ):
            raise ReferenceRejected("nonreciprocal_coordinate_edge")
    unique = list(incidence)
    for i, (a, b) in enumerate(unique):
        for c, d in unique[i + 1 :]:
            proper, overlap, touch = _intersections(a, b, c, d)
            if proper or overlap or (touch and not ({a, b} & {c, d})):
                raise ReferenceRejected("nonconforming_coordinate_edges")
    for i, points in enumerate(polygons):
        for other in polygons[i + 1 :]:
            if any(_location(p, other) == 1 for p in points) or any(
                _location(p, points) == 1 for p in other
            ):
                raise ReferenceRejected("interior_overlap")
    boundary = [owners[0][1:] for owners in incidence.values() if len(owners) == 1]
    starts = Counter(a for a, _ in boundary)
    ends = Counter(b for _, b in boundary)
    if any(starts[v] != 1 or ends[v] != 1 for v in starts.keys() | ends.keys()):
        raise ReferenceRejected("boundary_not_manifold")
    face_sum = sum(int(row["signed_double_area_integer"]) for row in measures.values())
    boundary_sum = sum(_cross(vertices[a], vertices[b]) for a, b in boundary)
    if face_sum != boundary_sum:
        raise ReferenceRejected("green_boundary_balance")
    return incidence, measures


def _merged(vertices, source, groups):
    source_by_id = {row["id"]: row for row in source}
    covered = [name for group in groups for name in group["source_cell_ids"]]
    if (
        len(covered) != len(set(covered))
        or set(covered) != set(source_by_id)
        or len({g["id"] for g in groups}) != len(groups)
    ):
        raise ReferenceRejected("cell_partition")
    result = []
    for group in groups:
        coefficients = Counter()
        for name in group["source_cell_ids"]:
            for a, b in _edges(source_by_id[name]["vertex_ids"]):
                edge = tuple(sorted((a, b)))
                coefficients[edge] += 1 if (a, b) == edge else -1
        directed = []
        for (a, b), coefficient in coefficients.items():
            if coefficient not in (-1, 0, 1):
                raise ReferenceRejected("nonmanifold_merge_incidence")
            if coefficient:
                directed.append((a, b) if coefficient == 1 else (b, a))
        starts = defaultdict(list)
        for a, b in directed:
            starts[a].append(b)
        if not directed or any(len(v) != 1 for v in starts.values()):
            raise ReferenceRejected("branched_merge_boundary")
        cursor = min(starts, key=lambda name: vertices[name])
        ring = []
        while cursor not in ring:
            ring.append(cursor)
            if cursor not in starts:
                raise ReferenceRejected("open_merge_boundary")
            cursor = starts[cursor][0]
        if cursor != ring[0] or len(ring) != len(directed):
            raise ReferenceRejected("holed_or_disconnected_merge")
        result.append(
            dict(id=group["id"], vertex_ids=ring, source_cell_ids=group["source_cell_ids"])
        )
    return result


def evaluate(raw, *, refinement=1):
    if refinement not in (1, 2):
        raise ReferenceRejected("refinement")
    if (
        raw["units"] != dict(coordinates="m", height="m", thickness="m", area="m2", volume="m3")
        or raw["axial_caps"] != "sealed_no_transport@1"
    ):
        raise ReferenceRejected("explicit_SI_and_caps")
    if (
        not 3 <= len(raw["vertices"]) <= 256
        or not 1 <= len(raw["source_cells"]) <= 32
        or not 1 <= len(raw["baths"]) <= 16
        or sum(len(r["vertex_ids"]) for r in raw["source_cells"]) > 512
        or any(len(r["vertex_ids"]) > 64 for r in raw["source_cells"])
    ):
        raise ReferenceRejected("bounded_axes")
    for value in [raw["height_m"], raw["thickness_m"], *[b["volume_m3"] for b in raw["baths"]]]:
        if type(value) not in (float, int) or not math.isfinite(value) or value <= 0:
            raise ReferenceRejected("positive_finite_measures")
    values = [v for row in raw["vertices"] for v in row["xy_m"]]
    if any(type(v) not in (float, int) or not math.isfinite(v) for v in values):
        raise ReferenceRejected("binary64_coordinates")
    ratios = [float(v).as_integer_ratio() for v in values]
    scale = max(d for _, d in ratios)
    integers = [n * (scale // d) for n, d in ratios]
    names = [row["id"] for row in raw["vertices"]]
    points = list(zip(integers[::2], integers[1::2], strict=True))
    if len(set(names)) != len(names) or len(set(points)) != len(points):
        raise ReferenceRejected("duplicate_vertex")
    vertices = dict(zip(names, points, strict=True))
    if {name for row in raw["source_cells"] for name in row["vertex_ids"]} != set(vertices):
        raise ReferenceRejected("unused_or_unknown_vertices")
    _, source_measures = _complex(vertices, raw["source_cells"], scale)
    cells = _merged(vertices, raw["source_cells"], raw["cell_groups"])
    incidence, measures = _complex(vertices, cells, scale)
    if sum(int(v["signed_double_area_integer"]) for v in source_measures.values()) != sum(
        int(v["signed_double_area_integer"]) for v in measures.values()
    ):
        raise ReferenceRejected("merge_measure_balance")
    bath_ids = [row["id"] for row in raw["baths"]]
    if len(set(bath_ids)) != len(bath_ids) or set(bath_ids) & {row["id"] for row in cells}:
        raise ReferenceRejected("bath_owner_ids")
    assignment = raw["bath_assignment"]
    if assignment["kind"] == "one_explicit_bath@1":
        if len(bath_ids) != 1 or assignment["bath_id"] != bath_ids[0]:
            raise ReferenceRejected("one_bath")
        baths = {
            tuple(sorted((a, b))): bath_ids[0]
            for owners in incidence.values()
            for _, a, b in owners
        }
    elif assignment["kind"] == "explicit_edge_baths@1":
        baths = {tuple(sorted(row["vertex_ids"])): row["bath_id"] for row in assignment["rows"]}
        expected = {tuple(sorted((a, b))) for owners in incidence.values() for _, a, b in owners}
        if (
            len(baths) != len(assignment["rows"])
            or set(baths) != expected
            or set(baths.values()) != set(bath_ids)
        ):
            raise ReferenceRejected("explicit_bath_edges")
    else:
        raise ReferenceRejected("bath_policy")
    nonzero = [Decimal.from_float(float(v)) for v in values if v]
    span = max(v.adjusted() for v in nonzero) - min(v.as_tuple().exponent for v in nonzero) + 1
    precision = max(4096, 6 * span + 160) + (512 if refinement == 2 else 0)
    if precision > 16384:
        raise ReferenceRejected("precision_domain")
    with localcontext() as context:
        context.prec = precision
        height = _float_ratio(raw["height_m"])
        cell_targets = []
        for row in cells:
            metric = measures[row["id"]]
            exact = dict(
                area_m2=metric["area"],
                volume_m3=_mul(metric["area"], height),
                centroid_x_m=metric["centroid"][0],
                centroid_y_m=metric["centroid"][1],
            )
            cell_targets.append(
                dict(
                    row,
                    exact_ratios=exact,
                    values_decimal={k: str(_decimal(v)) for k, v in exact.items()},
                    ear_decomposition=dict(
                        count=metric["ear_count"],
                        reference_collinear_removals=metric[
                            "collinear_vertices_removed_in_reference_only"
                        ],
                    ),
                )
            )
        edge_targets = []
        for owners in incidence.values():
            _, a, b = owners[0]
            a, b = sorted((a, b))
            pa, pb = vertices[a], vertices[b]
            dx, dy = pb[0] - pa[0], pb[1] - pa[1]
            squared = dx * dx + dy * dy
            radicals = dict(
                length_m=_ratio(squared, scale * scale),
                area_m2=_mul(_ratio(squared, scale * scale), _mul(height, height)),
                tangent_x=_ratio(dx * dx, squared),
                tangent_y=_ratio(dy * dy, squared),
            )
            signs = dict(
                length_m=1, area_m2=1, tangent_x=-1 if dx < 0 else 1, tangent_y=-1 if dy < 0 else 1
            )
            exact = dict(
                midpoint_x_m=_ratio(pa[0] + pb[0], 2 * scale),
                midpoint_y_m=_ratio(pa[1] + pb[1], 2 * scale),
            )
            targets = {k: signs[k] * _decimal(v).sqrt() for k, v in radicals.items()}
            targets.update({k: _decimal(v) for k, v in exact.items()})
            edge_targets.append(
                dict(
                    vertex_ids=[a, b],
                    cell_ids=[owner for owner, _, _ in owners],
                    directed_half_edges=[
                        dict(cell_id=owner, vertex_ids=[u, v]) for owner, u, v in owners
                    ],
                    bath_id=baths[(a, b)],
                    exact_ratios=exact,
                    squared_targets=radicals,
                    signs=signs,
                    values_decimal={k: str(v) for k, v in targets.items()},
                )
            )
    representability = []
    with localcontext() as context:
        context.prec = precision
        for row in cell_targets:
            for name, exact in row["exact_ratios"].items():
                representability.append(
                    rounding._rounded_ratio(exact, Decimal(row["values_decimal"][name])) is not None
                )
        for row in edge_targets:
            for name, value in row["values_decimal"].items():
                candidate = float(Decimal(value))
                if name in row["exact_ratios"]:
                    representability.append(
                        rounding._rounded_ratio(row["exact_ratios"][name], Decimal(value))
                        is not None
                    )
                else:
                    representability.append(
                        math.isfinite(candidate)
                        and (candidate != 0 or int(row["squared_targets"][name]["numerator"]) == 0)
                    )
    return dict(
        kind="cells.conforming_polygon_independent_geometry@1",
        refinement=refinement,
        precision_digits=precision,
        input_sha256=_hash(raw),
        integer_scale=str(scale),
        cells=cell_targets,
        edges=edge_targets,
        baths=raw["baths"],
        height_m=raw["height_m"],
        thickness_m=raw["thickness_m"],
        source_signed_double_area_integer=str(
            sum(int(v["signed_double_area_integer"]) for v in source_measures.values())
        ),
        merged_signed_double_area_integer=str(
            sum(int(v["signed_double_area_integer"]) for v in measures.values())
        ),
        production_imports=False,
        native_equivalence=False,
        source_generation_authenticated=False,
        source_voronoi_or_delaunay_generated=False,
        declared_union_boundaries_reconstructed=True,
        polygon_ear_decomposition_only=True,
        required_outputs_representable=all(representability),
    )


def _same_ratio(a, b):
    an, ad = _pair(a)
    bn, bd = _pair(b)
    return an * bd == bn * ad


def _sqrt_rounding_cell(actual, squared):
    candidate = abs(float(actual))
    n, d = _pair(squared)
    if n == 0:
        return candidate == 0
    if not math.isfinite(candidate) or candidate == 0:
        return False
    lower = math.nextafter(candidate, 0.0)
    upper = math.nextafter(candidate, math.inf)
    cn, cd = candidate.as_integer_ratio()
    ln, ld = lower.as_integer_ratio()
    un, ud = upper.as_integer_ratio() if math.isfinite(upper) else (1 << 1024, 1)
    lo_n, lo_d = cn * ld + ln * cd, 2 * cd * ld
    hi_n, hi_d = cn * ud + un * cd, 2 * cd * ud
    lower_sign = n * lo_d * lo_d - lo_n * lo_n * d
    upper_sign = hi_n * hi_n * d - n * hi_d * hi_d
    even = int.from_bytes(struct.pack(">d", candidate), "big") % 2 == 0
    return (lower_sign > 0 or (lower_sign == 0 and even)) and (
        upper_sign > 0 or (upper_sign == 0 and even)
    )


def _quantity(
    label,
    actual,
    primary,
    refined,
    *,
    exact=None,
    squared=None,
    sign=1,
    certificate=None,
    area=False,
    volume=False,
    unit=False,
    absolute_floor=None,
):
    a = Decimal.from_float(float(actual))
    target, second = Decimal(primary), Decimal(refined)
    floor = Decimal(
        absolute_floor or ("1e-30" if volume else "1e-26" if area else "1e-14" if unit else "1e-27")
    )
    budget = floor + Decimal("6e-12") * abs(target)
    ulp = Decimal.from_float(math.ulp(float(actual)))
    error = abs(a - target)
    assert math.isfinite(float(actual))
    assert error <= 32 * ulp and error <= budget, (
        label,
        float(actual).hex(),
        str(target),
        str(second),
        str(error / ulp),
        str(error / budget),
    )
    assert (
        abs(target - second) <= Decimal("0.01") * ulp
        and abs(target - second) <= Decimal("0.1") * budget
    )
    if exact is not None:
        expected = rounding._rounded_ratio(exact, target)
        assert float(actual).hex() == expected or (float(actual) == 0 and target == 0)
        if certificate is not None:
            assert certificate.get("sign", sign) == sign
            assert certificate["kind"] == "correctly_rounded_binary_rational" and _same_ratio(
                certificate["exact"], exact
            )
    if squared is not None:
        assert _sqrt_rounding_cell(actual, squared)
        assert float(actual) == 0 or (float(actual) > 0) == (sign > 0)
        if certificate is not None:
            assert certificate.get("sign", sign) == sign
            if int(squared["numerator"]) == 0:
                assert (
                    certificate["kind"] == "correctly_rounded_binary_rational"
                    and int(certificate["exact"]["numerator"]) == 0
                )
            else:
                assert certificate["kind"] == "resolved_dyadic_sqrt_interval"
                assert _same_ratio(certificate["radicand"], squared)
                ln, ld = _pair(certificate["lower"])
                un, ud = _pair(certificate["upper"])
                n, d = _pair(squared)
                assert ln * ln * d <= n * ld * ld and un * un * d >= n * ud * ud
                for endpoint in (certificate["lower"], certificate["upper"]):
                    assert (
                        rounding._rounded_ratio(endpoint, _decimal(endpoint))
                        == abs(float(actual)).hex()
                    )
    return dict(
        label=label,
        actual_binary64_hex=float(actual).hex(),
        reference_decimal=str(target),
        refined_reference_decimal=str(second),
        error_ulps=str(error / ulp),
        error_fraction=float(error / budget),
        reference_resolution_fraction=float(abs(target - second) / budget),
        correct_rounding_checked=True,
        certificate_checked=certificate is not None,
    )


def _cyclic_equal(a, b):
    return len(a) == len(b) and any(a == b[i:] + b[:i] for i in range(len(b)))


def compare(raw, actual, primary, refined):
    assert primary["input_sha256"] == refined["input_sha256"] == _hash(raw)
    assert primary["required_outputs_representable"] and refined["required_outputs_representable"]
    assert actual["request_identity"] == _hash(
        dict(
            kind="cells.conforming_polygon_physical_owner_request@1",
            law="cells_conforming_polygon_physical_owners@1",
            declaration=raw,
        )
    )
    assert (
        actual["units"] == raw["units"]
        and actual["height_m"] == raw["height_m"]
        and actual["thickness_m"] == raw["thickness_m"]
    )
    assert (
        actual["vertices"] == raw["vertices"]
        and actual["source_cells"] == raw["source_cells"]
        and actual["cell_groups"] == raw["cell_groups"]
    )
    assert actual["baths"] == raw["baths"]
    active = {v for cell in primary["cells"] for v in cell["vertex_ids"]}
    assert actual["physical_vertex_ids"] == [v["id"] for v in raw["vertices"] if v["id"] in active]
    assert actual["source_only_vertex_ids"] == [
        v["id"] for v in raw["vertices"] if v["id"] not in active
    ]
    assert [c["id"] for c in actual["cells"]] == [c["id"] for c in raw["cell_groups"]]
    assert len(actual["edges"]) == len(primary["edges"]) == len(refined["edges"])
    targets = {tuple(row["vertex_ids"]): row for row in primary["edges"]}
    refined_edges = {tuple(row["vertex_ids"]): row for row in refined["edges"]}
    membranes = {m["id"]: m for m in actual["membranes"]}
    contacts = {c["edge_id"]: c for c in actual["contacts"]}
    assert len(membranes) == len(actual["membranes"]) and len(contacts) == len(actual["contacts"])
    rows = []
    with localcontext() as context:
        context.prec = max(primary["precision_digits"], refined["precision_digits"]) + 128
        for cell, a, b in zip(actual["cells"], primary["cells"], refined["cells"], strict=True):
            assert (
                cell["id"] == a["id"] == b["id"]
                and cell["source_cell_ids"] == a["source_cell_ids"] == b["source_cell_ids"]
            )
            assert _cyclic_equal(cell["vertex_ids"], a["vertex_ids"])
            for name, certificate in (
                ("area_m2", cell["certificates"]["area"]),
                ("volume_m3", cell["certificates"]["volume"]),
                ("centroid_x_m", cell["certificates"]["centroid"][0]),
                ("centroid_y_m", cell["certificates"]["centroid"][1]),
            ):
                value = (
                    cell["centroid_m"][0 if name == "centroid_x_m" else 1]
                    if name.startswith("centroid")
                    else cell[name]
                )
                rows.append(
                    _quantity(
                        cell["id"] + "/" + name,
                        value,
                        a["values_decimal"][name],
                        b["values_decimal"][name],
                        exact=a["exact_ratios"][name],
                        certificate=certificate,
                        area=name == "area_m2",
                        volume=name == "volume_m3",
                    )
                )
            expected_halves = _edges(cell["vertex_ids"])
            assert [
                tuple(membranes[mid]["vertex_ids"]) for mid in cell["membrane_ids"]
            ] == expected_halves
            assert all(membranes[mid]["cell_id"] == cell["id"] for mid in cell["membrane_ids"])
        used_membranes = set()
        seen_edges = set()
        for edge in actual["edges"]:
            key = tuple(edge["vertex_ids"])
            assert key not in seen_edges and key in targets and list(key) == sorted(key)
            seen_edges.add(key)
            a, b = targets[key], refined_edges[key]
            assert edge["id"] == "edge-" + _hash(list(key)) and edge["bath_id"] == a["bath_id"]
            assert set(edge["cell_ids"]) == set(a["cell_ids"]) and len(edge["cell_ids"]) == len(
                a["cell_ids"]
            )
            values = dict(
                length_m=edge["length_m"],
                area_m2=edge["area_m2"],
                midpoint_x_m=edge["midpoint_m"][0],
                midpoint_y_m=edge["midpoint_m"][1],
                tangent_x=edge["tangent_xy"][0],
                tangent_y=edge["tangent_xy"][1],
            )
            certificates = dict(
                length_m=edge["certificates"]["length"],
                area_m2=edge["certificates"]["area"],
                midpoint_x_m=edge["certificates"]["midpoint"][0],
                midpoint_y_m=edge["certificates"]["midpoint"][1],
                tangent_x=edge["certificates"]["tangent"][0],
                tangent_y=edge["certificates"]["tangent"][1],
            )
            assert [float(v).hex() for v in edge["normal_xy"]] == [
                float(edge["tangent_xy"][1]).hex(),
                (-float(edge["tangent_xy"][0])).hex(),
            ]
            for name, value in values.items():
                rows.append(
                    _quantity(
                        edge["id"] + "/" + name,
                        value,
                        a["values_decimal"][name],
                        b["values_decimal"][name],
                        exact=a["exact_ratios"].get(name),
                        squared=a["squared_targets"].get(name),
                        sign=a["signs"].get(name, 1),
                        certificate=certificates[name],
                        area=name == "area_m2",
                        unit=name.startswith("tangent"),
                    )
                )
            halves = [membranes[mid] for mid in edge["membrane_ids"]]
            assert {(m["cell_id"], tuple(m["vertex_ids"])) for m in halves} == {
                (m["cell_id"], tuple(m["vertex_ids"])) for m in a["directed_half_edges"]
            }
            assert len(halves) == len(a["directed_half_edges"])
            for membrane in halves:
                mid = membrane["id"]
                assert mid not in used_membranes
                used_membranes.add(mid)
                assert mid == "membrane-" + _hash([membrane["cell_id"], *membrane["vertex_ids"]])
                assert (
                    membrane["bath_id"] == edge["bath_id"]
                    and membrane["edge_id"] == edge["id"]
                    and membrane["thickness_m"] == raw["thickness_m"]
                )
                assert float(membrane["area_m2"]).hex() == float(edge["area_m2"]).hex()
                direction = 1 if tuple(membrane["vertex_ids"]) == key else -1
                for vector in ("normal_xy", "tangent_xy"):
                    assert [float(v).hex() for v in membrane[vector]] == [
                        (direction * float(v)).hex() for v in edge[vector]
                    ]
            if len(halves) == 2:
                first, second = halves
                assert (
                    first["partner_id"] == second["id"]
                    and second["partner_id"] == first["id"]
                    and first["cell_id"] != second["cell_id"]
                )
                assert [float(v).hex() for v in first["normal_xy"]] == [
                    (-float(v)).hex() for v in second["normal_xy"]
                ]
                contact = contacts[edge["id"]]
                assert contact["id"] == "contact-" + _hash(list(key))
                assert contact["membrane_ids"] == edge["membrane_ids"] and [
                    contact["sender"],
                    contact["receiver"],
                ] == [m["cell_id"] for m in halves]
                assert float(contact["area_m2"]).hex() == float(edge["area_m2"]).hex()
                assert contact["vertex_ids"] == first["vertex_ids"]
                assert [float(v).hex() for v in contact["normal_xy"]] == [
                    float(v).hex() for v in first["normal_xy"]
                ]
            else:
                assert halves[0]["partner_id"] == halves[0]["id"] and edge["id"] not in contacts
        assert used_membranes == set(membranes) and seen_edges == set(targets)
        assert set(contacts) == {
            edge["id"] for edge in actual["edges"] if len(edge["cell_ids"]) == 2
        }
    owner_axis = [c["id"] for c in actual["cells"]] + [b["id"] for b in raw["baths"]]
    assert actual["owner_axis"] == owner_axis
    expected_mem = [
        [int(owner == m["bath_id"]) - int(owner == m["cell_id"]) for m in actual["membranes"]]
        for owner in owner_axis
    ]
    expected_contacts = [
        [int(owner == c["receiver"]) - int(owner == c["sender"]) for c in actual["contacts"]]
        for owner in owner_axis
    ]
    assert (
        actual["membrane_incidence"] == expected_mem
        and actual["contact_incidence"] == expected_contacts
    )
    assert all(sum(row[i] for row in expected_mem) == 0 for i in range(len(actual["membranes"])))
    assert all(
        sum(row[i] for row in expected_contacts) == 0 for i in range(len(actual["contacts"]))
    )
    return dict(
        full_precision_quantities=rows,
        maximum_error_fraction=max((r["error_fraction"] for r in rows), default=0),
        maximum_reference_resolution_fraction=max(
            (r["reference_resolution_fraction"] for r in rows), default=0
        ),
        independent_ear_and_green_measures_agree=True,
        source_and_merged_complex_checked=True,
        exact_physical_owner_and_interface_correspondence=True,
        integer_incidence_columns_sum_to_zero=True,
        trajectory_conservation_claimed=False,
        source_generation_authenticated=False,
        native_equivalence=False,
    )


def _at_precision(function, reference):
    with localcontext() as context:
        context.prec = reference["precision_digits"]
        return str(function())


def compare_physical(geometry, request, definition, primary, refined):
    """Check initial physical owners and SI conversions, without a field solve."""
    physical = request["physics"]
    model = definition["model"]
    assert model["id"] == "resolved_tissue@1" and model["species"] == physical["species"]
    assert (
        model["temperature_K"] == physical["temperature_K"]
        and model["closure"] == physical["closure"]
    )
    assert model["faces"] == []
    assert definition["execution"] == request["execution"]
    assert definition["experiment"]["end_time"] == request["experiment"]["end_time"]
    assert (
        definition["experiment"]["observation_times"] == request["experiment"]["observation_times"]
    )
    for family in ("membrane_controls", "junction_controls"):
        id_key = family.removesuffix("_controls") + "_id"
        for container in (definition["experiment"], request["experiment"]):
            rows = container[family]
            assert len({row[id_key] for row in rows}) == len(rows)
        assert {row[id_key]: row for row in definition["experiment"][family]} == {
            row[id_key]: row for row in request["experiment"][family]
        }
    actual_axes = {
        "cells": "cells",
        "baths": "extracellular",
        "membranes": "membranes",
        "contacts": "junctions",
    }
    for geometric, field in actual_axes.items():
        assert [row["id"] for row in model[field]] == [row["id"] for row in geometry[geometric]]
    input_rows = {key: {row["id"]: row for row in physical[key]} for key in actual_axes}
    targets = {tuple(row["vertex_ids"]): row for row in primary["edges"]}
    target_cells = {row["id"]: row for row in primary["cells"]}
    refined_cells = {row["id"]: row for row in refined["cells"]}
    species = [row["id"] for row in physical["species"]]
    membranes = {row["id"]: row for row in geometry["membranes"]}
    edges = {row["id"]: row for row in geometry["edges"]}
    rows = []
    with localcontext() as context:
        context.prec = max(primary["precision_digits"], refined["precision_digits"]) + 128
        for kind, field in (("cells", "cells"), ("baths", "extracellular")):
            for geometric, actual in zip(geometry[kind], model[field], strict=True):
                declared = input_rows[kind][actual["id"]]
                for key in (
                    "initial_amount_fmol",
                    "initial_charge_C",
                    "fixed_charge_equivalent_fmol",
                ):
                    assert actual[key] == declared[key]
                if kind == "cells":
                    exact = _mul(
                        target_cells[actual["id"]]["exact_ratios"]["volume_m3"], _ratio(10**15)
                    )
                    second = _mul(
                        refined_cells[actual["id"]]["exact_ratios"]["volume_m3"], _ratio(10**15)
                    )
                else:
                    assert (
                        actual["reservoir"] == declared["reservoir"]
                        and actual["boundary_potential_V"] == declared["boundary_potential_V"]
                    )
                    exact = _mul(_float_ratio(geometric["volume_m3"]), _ratio(10**15))
                    second = exact
                rows.append(
                    _quantity(
                        actual["id"] + "/volume_pL",
                        actual["volume_pL"],
                        _at_precision(lambda exact=exact: _decimal(exact), primary),
                        _at_precision(lambda second=second: _decimal(second), refined),
                        exact=exact,
                        absolute_floor="1e-30",
                    )
                )
        for actual in model["membranes"]:
            geometric = membranes[actual["id"]]
            declared = input_rows["membranes"][actual["id"]]
            assert (
                (actual["inside"], actual["outside"])
                == (declared["cell_id"], declared["bath_id"])
                == (geometric["cell_id"], geometric["bath_id"])
            )
            assert actual["law"] == "constant_field@1"
            target = targets[tuple(edges[geometric["edge_id"]]["vertex_ids"])]
            area_squared = target["squared_targets"]["area_m2"]
            rows.append(
                _quantity(
                    actual["id"] + "/area_m2",
                    actual["area_m2"],
                    _at_precision(lambda value=area_squared: _decimal(value).sqrt(), primary),
                    _at_precision(lambda value=area_squared: _decimal(value).sqrt(), refined),
                    squared=area_squared,
                    area=True,
                )
            )
            specific = _float_ratio(declared["specific_capacitance_F_per_m2"])
            cap_squared = _mul(area_squared, _mul(specific, specific))
            rows.append(
                _quantity(
                    actual["id"] + "/capacitance_F",
                    actual["capacitance_F"],
                    _at_precision(lambda value=cap_squared: _decimal(value).sqrt(), primary),
                    _at_precision(lambda value=cap_squared: _decimal(value).sqrt(), refined),
                    squared=cap_squared,
                    absolute_floor="1e-30",
                )
            )
            for name in species:
                diffusion = _float_ratio(declared["diffusivity_m2_per_s"][name])
                tn, td = float(geometry["thickness_m"]).as_integer_ratio()
                permeability = _mul(diffusion, _ratio(td, tn))
                rows.append(
                    _quantity(
                        actual["id"] + "/permeability/" + name,
                        actual["permeability_m_per_s"][name],
                        _at_precision(lambda value=permeability: _decimal(value), primary),
                        _at_precision(lambda value=permeability: _decimal(value), refined),
                        exact=permeability,
                        absolute_floor="1e-30",
                    )
                )
        contact_geometry = {row["id"]: row for row in geometry["contacts"]}
        for actual in model["junctions"]:
            contact = contact_geometry[actual["id"]]
            declared = input_rows["contacts"][actual["id"]]
            assert (
                (actual["sender"], actual["receiver"])
                == (declared["sender"], declared["receiver"])
                == (contact["sender"], contact["receiver"])
            )
            assert declared["membrane_ids"] == contact["membrane_ids"]
            assert (
                actual["law"] == "constant_field@1"
                and actual["permeability_m_per_s"] == declared["permeability_m_per_s"]
            )
            target = targets[tuple(edges[contact["edge_id"]]["vertex_ids"])]["squared_targets"][
                "area_m2"
            ]
            rows.append(
                _quantity(
                    actual["id"] + "/one_contact_area_m2",
                    actual["area_m2"],
                    _at_precision(lambda value=target: _decimal(value).sqrt(), primary),
                    _at_precision(lambda value=target: _decimal(value).sqrt(), refined),
                    squared=target,
                    area=True,
                )
            )
    return dict(
        full_precision_quantities=rows,
        maximum_error_fraction=max((r["error_fraction"] for r in rows), default=0),
        inventories_and_charge_anchors_preserved_by_exact_owner_id=True,
        explicit_bath_volumes_only=True,
        membrane_diffusivity_over_explicit_thickness=True,
        one_surface_per_reciprocal_junction=True,
        controls_and_execution_preserved=True,
        physical_admission_replaced=False,
        field_or_solver_executed_by_reference=False,
        native_equivalence=False,
    )
