"""Geometry-only lane extracted without formula changes from frozen finite ECM.

Source SHA256 79aaf9acb8a9cfbc557b33fbc386fbf835fb6eef12f2395e97acb08d072fde71.
Field/conversion/physical lanes are excluded to keep a stdlib-only closure.
"""

import hashlib
import json
import math
from collections import defaultdict
from decimal import localcontext

from validation.geometry import conservative_polygon_geometry_reference as polygon
from validation.geometry import stable_geometry_primitives_reference as rounding


class ReferenceRejected(ValueError):
    pass


def ratio(value):
    return polygon._ratio(*float(value).as_integer_ratio())


def add(a, b):
    an, ad = polygon._pair(a)
    bn, bd = polygon._pair(b)
    return polygon._ratio(an * bd + bn * ad, ad * bd)


def subtract(a, b):
    an, ad = polygon._pair(a)
    bn, bd = polygon._pair(b)
    return polygon._ratio(an * bd - bn * ad, ad * bd)


def multiply(a, b):
    return polygon._mul(a, b)


def divide(a, b):
    an, ad = polygon._pair(a)
    bn, bd = polygon._pair(b)
    return polygon._ratio(an * bd, ad * bn)


def dot(a, b):
    total = ratio(0)
    for x, y in zip(a, b, strict=True):
        total = add(total, multiply(x, y))
    return total


def number(exact, *, root=False, precision=4096):
    with localcontext() as ctx:
        ctx.prec = precision
        target = polygon._decimal(exact)
        if root:
            value = float(target.sqrt())
            if not math.isfinite(value) or not polygon._sqrt_rounding_cell(value, exact):
                raise ReferenceRejected("unresolved_or_unrepresentable_radical")
        else:
            exact_hex = rounding._rounded_ratio(exact, target)
            if exact_hex is None:
                raise ReferenceRejected("unrepresentable_rational")
            value = float.fromhex(exact_hex)
    return value


def identity(prefix, value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return prefix + hashlib.sha256(encoded).hexdigest()


def evaluate(raw, *, refinement=1):
    if set(raw) != {
        "source",
        "vertices",
        "domain_vertex_ids",
        "regions",
        "boundary",
        "height_m",
        "membrane_thickness_m",
        "membrane_geometry_policy",
        "face_distance_policy",
        "axial_caps",
        "units",
    }:
        raise ReferenceRejected("explicit_input_fields")
    if (
        set(raw["source"]) != {"kind", "generator", "provenance"}
        or any(set(row) != {"id", "xy_m"} for row in raw["vertices"])
        or any(set(row) != {"id", "kind", "vertex_ids"} for row in raw["regions"])
        or any(set(row) != {"region_id", "vertex_ids", "condition"} for row in raw["boundary"])
    ):
        raise ReferenceRejected("explicit_source_region_vertex_boundary_fields")
    if refinement not in (1, 2):
        raise ReferenceRejected("refinement")
    if (
        raw["source"]["kind"] != "explicit_cell_bath_partition@1"
        or not raw["source"]["provenance"]
        or raw["units"]
        != dict(coordinates="m", height="m", membrane_path="m", area="m2", volume="m3")
    ):
        raise ReferenceRejected("explicit_source_units")
    if (
        raw["membrane_geometry_policy"] != "zero_volume_interface_explicit_path@1"
        or raw["face_distance_policy"] != "orthogonal_volume_centroids_shared_face@1"
        or raw["axial_caps"] != "sealed_no_transport@1"
    ):
        raise ReferenceRejected("unsupported_geometry_or_boundary_policy")
    coordinates = [v for row in raw["vertices"] for v in row["xy_m"]]
    for value in coordinates + [raw["height_m"], raw["membrane_thickness_m"]]:
        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or (type(value) is int and abs(value) > 2**53)
        ):
            raise ReferenceRejected("binary64_inputs")
    if raw["height_m"] <= 0 or raw["membrane_thickness_m"] <= 0:
        raise ReferenceRejected("positive_height_membrane_path")
    if not 3 <= len(raw["vertices"]) <= 256 or not 2 <= len(raw["regions"]) <= 32:
        raise ReferenceRejected("partition_bounds")
    scale = max(float(v).as_integer_ratio()[1] for v in coordinates)
    vertices = {
        row["id"]: tuple(
            int(float(v).as_integer_ratio()[0]) * (scale // float(v).as_integer_ratio()[1])
            for v in row["xy_m"]
        )
        for row in raw["vertices"]
    }
    if len(vertices) != len(raw["vertices"]) or len(set(vertices.values())) != len(vertices):
        raise ReferenceRejected("distinct_vertices")
    rows = raw["regions"]
    cells = [row["id"] for row in rows if row["kind"] == "cell"]
    baths = [row["id"] for row in rows if row["kind"] == "bath"]
    if (
        not 1 <= len(cells) <= 16
        or not baths
        or len(cells) + len(baths) != len(rows)
        or any(not 3 <= len(row["vertex_ids"]) <= 64 for row in rows)
        or sum(len(row["vertex_ids"]) for row in rows) > 512
    ):
        raise ReferenceRejected("region_roles_or_bounds")
    if {v for row in rows for v in row["vertex_ids"]} != set(vertices):
        raise ReferenceRejected("unused_or_unknown_vertex")
    incidence, measures = polygon._complex(vertices, rows, scale)
    outer = {
        tuple(owners[0][1:]): owners[0][0] for owners in incidence.values() if len(owners) == 1
    }
    if set(outer) != set(polygon._edges(raw["domain_vertex_ids"])):
        raise ReferenceRejected("incomplete_single_outer_domain")
    boundary = {tuple(row["vertex_ids"]): row["region_id"] for row in raw["boundary"]}
    if (
        len(boundary) != len(raw["boundary"])
        or boundary != outer
        or any(row["condition"] != "sealed_no_transport@1" for row in raw["boundary"])
    ):
        raise ReferenceRejected("explicit_sealed_boundary_owners")
    domain = polygon._polygon([vertices[v] for v in raw["domain_vertex_ids"]], scale)
    total = ratio(0)
    for row in rows:
        pts = [vertices[v] for v in row["vertex_ids"]]
        if any(polygon._orient(a, b, p) < 0 for a, b in polygon._edges(pts) for p in pts):
            raise ReferenceRejected("convex_regions_required")
        total = add(total, measures[row["id"]]["area"])
    if not polygon._same_ratio(total, domain["area"]):
        raise ReferenceRejected("domain_area_exhaustion")
    adjacency = defaultdict(set)
    for owners in incidence.values():
        if len(owners) == 2:
            a, b = owners[0][0], owners[1][0]
            adjacency[a].add(b)
            adjacency[b].add(a)
    reached = {rows[0]["id"]}
    queue = list(reached)
    while queue:
        for neighbor in adjacency[queue.pop()] - reached:
            reached.add(neighbor)
            queue.append(neighbor)
    if reached != {row["id"] for row in rows}:
        raise ReferenceRejected("connected_partition")
    height = ratio(raw["height_m"])
    targets = {
        row["id"]: dict(
            kind=row["kind"],
            vertex_ids=row["vertex_ids"],
            area=measures[row["id"]]["area"],
            volume=multiply(measures[row["id"]]["area"], height),
            centroid=measures[row["id"]]["centroid"],
        )
        for row in rows
    }
    roles = {row["id"]: row["kind"] for row in rows}
    edges = []
    membranes = []
    faces = []
    boundary_rows = []
    half = []
    for owners in incidence.values():
        edge = tuple(sorted(owners[0][1:]))
        a, b = edge
        pa, pb = vertices[a], vertices[b]
        dx, dy = pb[0] - pa[0], pb[1] - pa[1]
        length_squared = polygon._ratio(dx * dx + dy * dy, scale * scale)
        area_squared = multiply(length_squared, multiply(height, height))
        edge_id = identity("ecm-edge-", list(edge))
        names = [owner[0] for owner in owners]
        if len(owners) == 1:
            owner, u, v = owners[0]
            if roles[owner] != "bath":
                raise ReferenceRejected("cell_at_outer_boundary")
            kind = "boundary"
            route = dict(
                id=identity("ecm-boundary-", list(edge)),
                edge_id=edge_id,
                region_id=owner,
                vertex_ids=[u, v],
                condition="sealed_no_transport@1",
            )
            boundary_rows.append(route)
        elif roles[names[0]] == roles[names[1]] == "cell":
            raise ReferenceRejected("direct_cell_cell_has_no_cleft")
        elif "cell" in (roles[name] for name in names):
            owner, u, v = next(row for row in owners if roles[row[0]] == "cell")
            bath = next(name for name in names if roles[name] == "bath")
            kind = "membrane"
            route = dict(
                id=identity("ecm-membrane-", list(edge)),
                edge_id=edge_id,
                cell_id=owner,
                bath_id=bath,
                vertex_ids=[u, v],
            )
            membranes.append(route)
        else:
            sender, u, v = owners[0]
            receiver = owners[1][0]
            cs, cr = targets[sender]["centroid"], targets[receiver]["centroid"]
            start = [polygon._ratio(x, scale) for x in vertices[u]]
            tangent = [
                polygon._ratio(y - x, scale) for x, y in zip(vertices[u], vertices[v], strict=True)
            ]
            delta = [subtract(y, x) for x, y in zip(cs, cr, strict=True)]
            if int(dot(delta, tangent)["numerator"]) != 0:
                raise ReferenceRejected("nonorthogonal_centroid_link")
            projection = divide(
                dot([subtract(x, y) for x, y in zip(cs, start, strict=True)], tangent),
                dot(tangent, tangent),
            )
            pn, pd = polygon._pair(projection)
            if not 0 < pn < pd:
                raise ReferenceRejected("projection_not_inside_shared_face")
            foot = [add(x, multiply(projection, t)) for x, t in zip(start, tangent, strict=True)]
            sign = []
            for center in (cs, cr):
                offset = [subtract(x, y) for x, y in zip(center, start, strict=True)]
                signed = subtract(multiply(tangent[0], offset[1]), multiply(tangent[1], offset[0]))
                sign.append(int(signed["numerator"]))
            if sign[0] <= 0 or sign[1] >= 0:
                raise ReferenceRejected("centroid_side_ownership")
            kind = "face"
            side_squared = []
            for center in (cs, cr):
                offset = [subtract(x, y) for x, y in zip(center, foot, strict=True)]
                side_squared.append(dot(offset, offset))
            route = dict(
                id=identity("ecm-face-", list(edge)),
                edge_id=edge_id,
                sender=sender,
                receiver=receiver,
                vertex_ids=[u, v],
                length_squared=dot(delta, delta),
                centroid_to_face_squared=side_squared,
                common_projection=foot,
            )
            faces.append(route)
        edges.append(
            dict(
                id=edge_id,
                vertex_ids=list(edge),
                region_ids=names,
                interface_kind=kind,
                interface_id=route["id"],
                length_squared=length_squared,
                area_squared=area_squared,
                midpoint=[polygon._ratio(x + y, 2 * scale) for x, y in zip(pa, pb, strict=True)],
                tangent_squared=[polygon._ratio(d * d, dx * dx + dy * dy) for d in (dx, dy)],
                tangent_sign=[-1 if d < 0 else 1 for d in (dx, dy)],
            )
        )
        for owner, u, v in owners:
            half.append(
                dict(
                    region_id=owner,
                    vertex_ids=[u, v],
                    edge_id=edge_id,
                    interface_id=route["id"],
                    interface_kind=kind,
                    neighbor_id=next((name for name in names if name != owner), None),
                )
            )
    if not faces or {row["cell_id"] for row in membranes} != set(cells):
        raise ReferenceRejected("owned_membranes_and_ECM_faces_required")
    precision = 4096 + (512 if refinement == 2 else 0)
    # Resolve every required output now, including pL conversions, so extreme
    # underflow/overflow is a refusal rather than an admitted zero volume.
    for row in targets.values():
        for q in [row["area"], row["volume"], *row["centroid"]]:
            number(q, precision=precision)
    for row in edges:
        number(row["area_squared"], root=True, precision=precision)
        number(row["length_squared"], root=True, precision=precision)
    for row in faces:
        number(row["length_squared"], root=True, precision=precision)
    return dict(
        kind="cells.finite_ecm_polygon_independent_geometry@1",
        refinement=refinement,
        precision_digits=precision,
        integer_scale=str(scale),
        regions=targets,
        cell_ids=cells,
        bath_ids=baths,
        edges=edges,
        membranes=membranes,
        faces=faces,
        boundary=boundary_rows,
        half_edges=half,
        domain_area=total,
        domain_volume=multiply(total, height),
        production_functions_called=False,
        native_equivalence=False,
        qualification_inherited=False,
    )


def _metric(actual, exact, certificate, *, root=False, precision=4096):
    target = number(exact, root=root, precision=precision)
    assert float(actual).hex() == target.hex()
    assert certificate["radicand" if root else "exact"] == exact


def compare_geometry(raw, actual, primary=None, refined=None):
    primary = evaluate(raw) if primary is None else primary
    refined = evaluate(raw, refinement=2) if refined is None else refined
    assert {k: v for k, v in primary.items() if k not in ("refinement", "precision_digits")} == {
        k: v for k, v in refined.items() if k not in ("refinement", "precision_digits")
    }
    assert actual["cell_ids"] == primary["cell_ids"] and actual["bath_ids"] == primary["bath_ids"]
    assert (
        actual["domain_area_exact"] == primary["domain_area"]
        and actual["domain_volume_exact"] == primary["domain_volume"]
    )
    assert actual["owner_axis"] == primary["cell_ids"] + primary["bath_ids"]
    regions = {row["id"]: row for row in actual["regions"]}
    assert set(regions) == set(primary["regions"])
    for name, row in regions.items():
        target = primary["regions"][name]
        assert row["kind"] == target["kind"] and row["vertex_ids"] == target["vertex_ids"]
        _metric(row["area_m2"], target["area"], row["certificates"]["area"])
        _metric(row["volume_m3"], target["volume"], row["certificates"]["volume"])
        for value, cert, q in zip(
            row["centroid_m"], row["certificates"]["centroid"], target["centroid"], strict=True
        ):
            _metric(value, q, cert)
    edge_targets = {row["id"]: row for row in primary["edges"]}
    edges = {row["id"]: row for row in actual["edges"]}
    assert set(edges) == set(edge_targets)
    normals = {}
    tangents = {}
    for name, row in edges.items():
        target = edge_targets[name]
        for key in ("vertex_ids", "region_ids", "interface_kind", "interface_id"):
            assert row[key] == target[key]
        _metric(row["area_m2"], target["area_squared"], row["certificates"]["area"], root=True)
        _metric(row["length_m"], target["length_squared"], row["certificates"]["length"], root=True)
        for value, cert, q in zip(
            row["midpoint_m"], row["certificates"]["midpoint"], target["midpoint"], strict=True
        ):
            _metric(value, q, cert)
        tangent = [
            sign * number(q, root=True)
            for q, sign in zip(target["tangent_squared"], target["tangent_sign"], strict=True)
        ]
        normal = [tangent[1], -tangent[0]]
        assert row["tangent_xy"] == tangent and row["normal_xy"] == normal
        normals[name] = normal
        tangents[name] = tangent
    for kind in ("membranes", "faces", "boundary"):
        expected = {row["id"]: row for row in primary[kind]}
        found = {row["id"]: row for row in actual[kind]}
        assert set(found) == set(expected)
        for name, row in found.items():
            target = expected[name]
            for key in ("edge_id", "vertex_ids") + (
                {
                    "membranes": ("cell_id", "bath_id"),
                    "faces": ("sender", "receiver"),
                    "boundary": ("region_id", "condition"),
                }[kind]
            ):
                assert row[key] == target[key]
            edge = edge_targets[row["edge_id"]]
            assert row["area_m2"] == number(edge["area_squared"], root=True)
            direction = 1 if row["vertex_ids"] == edge["vertex_ids"] else -1
            assert row["normal_xy"] == [direction * v for v in normals[row["edge_id"]]]
            assert row["tangent_xy"] == [direction * v for v in tangents[row["edge_id"]]]
            if kind == "membranes":
                assert row["thickness_m"] == raw["membrane_thickness_m"]
            if kind == "faces":
                _metric(
                    row["length_m"],
                    target["length_squared"],
                    row["certificates"]["length"],
                    root=True,
                )
                for value, cert, q in zip(
                    row["centroid_to_face_m"],
                    row["certificates"]["centroid_to_face"],
                    target["centroid_to_face_squared"],
                    strict=True,
                ):
                    _metric(value, q, cert, root=True)
                for value, cert, q in zip(
                    row["common_projection_m"],
                    row["certificates"]["common_projection"],
                    target["common_projection"],
                    strict=True,
                ):
                    _metric(value, q, cert)
    actual_half = []
    for row in actual["half_edges"]:
        projected = {key: value for key, value in row.items() if key != "normal_xy"}
        actual_half.append(projected)
        edge = edge_targets[row["edge_id"]]
        direction = 1 if row["vertex_ids"] == edge["vertex_ids"] else -1
        assert row["normal_xy"] == [direction * v for v in normals[row["edge_id"]]]
    assert actual_half == primary["half_edges"]
    for name, routes, ends in (
        ("membrane_incidence", primary["membranes"], ("cell_id", "bath_id")),
        ("face_incidence", primary["faces"], ("sender", "receiver")),
    ):
        expected = [
            [int(owner == route[ends[1]]) - int(owner == route[ends[0]]) for route in routes]
            for owner in actual["owner_axis"]
        ]
        assert actual[name] == expected
    return dict(
        status="passed",
        regions=len(regions),
        cell_bath_membranes=len(primary["membranes"]),
        bath_bath_faces=len(primary["faces"]),
        sealed_boundary_sides=len(primary["boundary"]),
        exact_partition_volume_and_orthogonal_distance_targets=True,
        production_functions_called=False,
        qualification_inherited=False,
    )


