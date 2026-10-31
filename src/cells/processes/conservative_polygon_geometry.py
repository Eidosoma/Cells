"""Candidate Cells polygon extrusion and exact physical-owner correspondence.

Conforming polygon coordinates are the geometric authority. Native nearest-edge
maps and triangle/quad metrics do not supply contacts or physical measures.
"""

import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from types import MappingProxyType

from cells.processes import stable_geometry_primitives as arithmetic

LAW_ID = "cells_conforming_polygon_physical_owners@1"
REQUEST_KIND = "cells.conforming_polygon_physical_owner_request@1"
RESULT_KIND = "cells.conforming_polygon_physical_owner_binding@1"
MAX_SOURCE_CELLS = 32
MAX_VERTICES = 256
MAX_SOURCE_RING = 64
MAX_MERGED_RING = 256
MAX_HALF_EDGES = 512
MAX_BATHS = 16
ARITHMETIC_SHA256 = "c9fab4f34aa9166711431844f2af72eb6b8fe4873154bfe01dfce3f656326958"
MESH_BRIDGE_SHA256 = "056cb2e47772a63416a9eebd89dd60a7019fcf217d3433403b9b053a209bedc4"
MESH_BRIDGE_BUNDLE_SHA256 = "996dbe391b0b35fcae43682fd6f09c353d9b2b2f86a54b953073b234a42b430e"
UNITS = dict(coordinates="m", height="m", thickness="m", area="m2", volume="m3")


def _json(value):
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if len(text.encode()) > 16 * 2**20:
        raise GeometryRejected("metadata_size", stage="representation")
    return text


def _digest(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _keys(value, names, stage):
    if type(value) is not dict or set(value) != set(names):
        raise GeometryRejected("fields", stage=stage)


def _id(value):
    if (
        type(value) is not str
        or not 1 <= len(value) <= 128
        or any(ord(c) < 33 or ord(c) > 126 for c in value)
    ):
        raise GeometryRejected("stable_id", stage="input")
    return value


def _number(value, *, positive=False):
    if type(value) is int and abs(value) <= 2**53:
        value = float(value)
    if type(value) is not float or not math.isfinite(value) or (positive and value <= 0):
        raise GeometryRejected("finite_binary64", stage="input")
    return value


def _ratio(value):
    return dict(numerator=str(value.numerator), denominator=str(value.denominator))


class GeometryRejected(ValueError):
    def __init__(self, code, *, stage, detail=None, trial=None):
        super().__init__(code + " at " + stage)
        self.code, self.stage, self.detail, self.trial = code, stage, detail, trial


@dataclass(frozen=True, slots=True)
class Request:
    declaration_json: str
    upstream: tuple
    identity: str

    @property
    def declaration(self):
        return json.loads(self.declaration_json)


@dataclass(frozen=True, slots=True)
class Binding:
    request_identity: str
    geometry_json: str
    identity: str

    @property
    def geometry(self):
        return json.loads(self.geometry_json)


def request_record(request):
    return dict(kind=REQUEST_KIND, law=LAW_ID, declaration=request.declaration)


def _normalise(raw):
    _keys(
        raw,
        {
            "source",
            "vertices",
            "source_cells",
            "cell_groups",
            "baths",
            "bath_assignment",
            "height_m",
            "thickness_m",
            "axial_caps",
            "units",
        },
        "request",
    )
    if raw["units"] != UNITS or raw["axial_caps"] != "sealed_no_transport@1":
        raise GeometryRejected("units_or_axial_caps", stage="input")
    source = raw["source"]
    if type(source) is not dict or source.get("kind") not in (
        "declared_polygon_complex@1",
        "owned_stable_initial_dual_mesh@1",
    ):
        raise GeometryRejected("source_kind", stage="provenance")
    if source["kind"] == "declared_polygon_complex@1":
        _keys(source, {"kind", "generator", "recipe", "generation_coverage"}, "declared_source")
        _id(source["generator"])
        if (
            type(source["recipe"]) is not dict
            or not source["recipe"]
            or source["generation_coverage"] is not False
        ):
            raise GeometryRejected("declared_source_provenance", stage="provenance")
    else:
        _keys(
            source,
            {
                "kind",
                "request_identity",
                "state_identity",
                "cache_identity",
                "bridge_bundle_sha256",
                "bridge_request",
                "bridge_state",
                "coordinate_policy",
            },
            "generated_source",
        )
        if (
            source["coordinate_policy"] != "owned_vor_verts_and_vor_cells@1"
            or source["bridge_bundle_sha256"] != MESH_BRIDGE_BUNDLE_SHA256
        ):
            raise GeometryRejected("generated_source_policy", stage="provenance")
    vertices = raw["vertices"]
    cells, groups, baths = raw["source_cells"], raw["cell_groups"], raw["baths"]
    if type(vertices) is not list or not 3 <= len(vertices) <= MAX_VERTICES:
        raise GeometryRejected("vertex_count", stage="input")
    if (
        any(type(rows) is not list for rows in (cells, groups, baths))
        or not 1 <= len(cells) <= MAX_SOURCE_CELLS
        or not 1 <= len(groups) <= len(cells)
        or not 1 <= len(baths) <= MAX_BATHS
    ):
        raise GeometryRejected("owner_counts", stage="input")
    clean_vertices = []
    for row in vertices:
        _keys(row, {"id", "xy_m"}, "vertex")
        if type(row["xy_m"]) not in (list, tuple) or len(row["xy_m"]) != 2:
            raise GeometryRejected("coordinate_axis", stage="input")
        clean_vertices.append(dict(id=_id(row["id"]), xy_m=[_number(v) for v in row["xy_m"]]))
    for rows, key, limit in (
        (cells, "vertex_ids", MAX_SOURCE_RING),
        (groups, "source_cell_ids", MAX_SOURCE_CELLS),
    ):
        for row in rows:
            _keys(row, {"id", key}, key)
            _id(row["id"])
            if type(row[key]) is not list or not 1 <= len(row[key]) <= limit:
                raise GeometryRejected("owner_axis", stage=key)
            for name in row[key]:
                _id(name)
    if sum(len(row["vertex_ids"]) for row in cells) > MAX_HALF_EDGES:
        raise GeometryRejected("half_edge_count", stage="input")
    clean_baths = []
    for row in baths:
        _keys(row, {"id", "volume_m3"}, "bath")
        clean_baths.append(
            dict(id=_id(row["id"]), volume_m3=_number(row["volume_m3"], positive=True))
        )
    assignment = raw["bath_assignment"]
    if type(assignment) is not dict:
        raise GeometryRejected("bath_assignment", stage="input")
    if assignment.get("kind") == "one_explicit_bath@1":
        _keys(assignment, {"kind", "bath_id"}, "bath_assignment")
        if len(baths) != 1 or assignment["bath_id"] != baths[0]["id"]:
            raise GeometryRejected("single_bath_ownership", stage="input")
    elif assignment.get("kind") == "explicit_edge_baths@1":
        _keys(assignment, {"kind", "rows"}, "bath_assignment")
        if (
            type(assignment["rows"]) is not list
            or not 1 <= len(assignment["rows"]) <= MAX_HALF_EDGES
        ):
            raise GeometryRejected("bath_edge_count", stage="input")
        for row in assignment["rows"]:
            _keys(row, {"vertex_ids", "bath_id"}, "edge_bath")
            if type(row["vertex_ids"]) is not list or len(row["vertex_ids"]) != 2:
                raise GeometryRejected("bath_edge_axis", stage="input")
            for name in [*row["vertex_ids"], row["bath_id"]]:
                _id(name)
    else:
        raise GeometryRejected("bath_assignment_policy", stage="input")
    result = json.loads(_json(raw))
    result.update(
        vertices=clean_vertices,
        baths=clean_baths,
        height_m=_number(raw["height_m"], positive=True),
        thickness_m=_number(raw["thickness_m"], positive=True),
    )
    return result


def _make(raw, upstream):
    clean = _normalise(raw)
    value = Request(_json(clean), upstream, "")
    return Request(value.declaration_json, upstream, _digest(request_record(value)))


def from_polygons(raw, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise GeometryRejected("explicit_opt_in", stage="input")
    clean = _normalise(raw)
    if clean["source"]["kind"] != "declared_polygon_complex@1":
        raise GeometryRejected("owned_upstream_required", stage="provenance")
    return _make(clean, ())


def from_generated(
    request, state, *, cell_groups, baths, bath_assignment, height_m, thickness_m, law_id
):
    """Authenticate complete upstream ownership, then admit geometry separately."""
    if type(law_id) is not str or law_id != LAW_ID:
        raise GeometryRejected("explicit_opt_in", stage="input")
    from cells.processes import betse_initial_mesh_preparation_cache as cache_transport
    from cells.processes import stable_initial_mesh_preparation as upstream

    if hashlib.sha256(Path(upstream.__file__).read_bytes()).hexdigest() != MESH_BRIDGE_SHA256:
        raise GeometryRejected("changed_mesh_bridge", stage="provenance")
    upstream.validate_state(request, state)
    if not state.pre_mesh_completed or state.status != "stable_mesh_completed_unqualified":
        raise GeometryRejected("incomplete_generated_mesh", stage="provenance")
    cache = cache_transport.plain(state.cache)
    points, rings = cache["vor_verts"], cache["vor_cells"]
    if len(rings) != len(state.retained_point_ids) or cache["vcell_verts"] != [
        [points[i] for i in ring] for ring in rings
    ]:
        raise GeometryRejected("generated_polygon_cache_ownership", stage="provenance")
    vertex_ids = ["vertex-" + str(i) for i in range(len(points))]

    def plain(value):
        if isinstance(value, MappingProxyType):
            return dict(value)
        if hasattr(value, "tolist"):
            return value.tolist()
        raise TypeError(type(value).__name__)

    source = dict(
        kind="owned_stable_initial_dual_mesh@1",
        request_identity=request.identity,
        state_identity=state.identity,
        cache_identity=state.cache.identity,
        bridge_bundle_sha256=MESH_BRIDGE_BUNDLE_SHA256,
        bridge_request=json.loads(
            json.dumps(upstream.request_record(request), default=plain, allow_nan=False)
        ),
        bridge_state=upstream.state_record(state),
        coordinate_policy="owned_vor_verts_and_vor_cells@1",
    )
    raw = dict(
        source=source,
        vertices=[
            dict(id=name, xy_m=point) for name, point in zip(vertex_ids, points, strict=True)
        ],
        source_cells=[
            dict(id=name, vertex_ids=[vertex_ids[i] for i in ring])
            for name, ring in zip(state.retained_point_ids, rings, strict=True)
        ],
        cell_groups=cell_groups,
        baths=baths,
        bath_assignment=bath_assignment,
        height_m=height_m,
        thickness_m=thickness_m,
        axial_caps="sealed_no_transport@1",
        units=UNITS,
    )
    return _make(raw, (request, state))


def validate_request(request):
    if (
        type(request) is not Request
        or type(request.declaration_json) is not str
        or type(request.upstream) is not tuple
    ):
        raise GeometryRejected("request_ownership", stage="identity")
    raw = request.declaration
    if raw["source"]["kind"] == "declared_polygon_complex@1":
        if request.upstream:
            raise GeometryRejected("unexpected_upstream", stage="identity")
        expected = from_polygons(raw, law_id=LAW_ID)
    else:
        if len(request.upstream) != 2:
            raise GeometryRejected("owned_upstream_required", stage="identity")
        expected = from_generated(
            *request.upstream,
            **{
                key: raw[key]
                for key in ("cell_groups", "baths", "bath_assignment", "height_m", "thickness_m")
            },
            law_id=LAW_ID,
        )
    if (
        request.declaration_json != expected.declaration_json
        or request.identity != expected.identity
    ):
        raise GeometryRejected("changed_request", stage="identity")
    return request


def _edges(ring):
    return list(zip(ring, ring[1:] + ring[:1], strict=True))


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _orient(a, b, c):
    return _cross((b[0] - a[0], b[1] - a[1]), (c[0] - a[0], c[1] - a[1]))


def _on(a, b, p):
    return _orient(a, b, p) == 0 and all(
        min(x, y) <= z <= max(x, y) for x, y, z in zip(a, b, p, strict=True)
    )


def _inside(p, polygon):
    winding = 0
    for a, b in _edges(polygon):
        if _on(a, b, p):
            return 0
        if a[1] <= p[1] < b[1] and _orient(a, b, p) > 0:
            winding += 1
        if b[1] <= p[1] < a[1] and _orient(a, b, p) < 0:
            winding -= 1
    return 1 if winding else -1


def _segments(a, b, c, d):
    proper = _orient(a, b, c) * _orient(a, b, d) < 0 and _orient(c, d, a) * _orient(c, d, b) < 0
    overlap = False
    if _orient(a, b, c) == 0 and _orient(a, b, d) == 0:
        axis = 0 if a[0] != b[0] else 1
        overlap = max(min(a[axis], b[axis]), min(c[axis], d[axis])) < min(
            max(a[axis], b[axis]), max(c[axis], d[axis])
        )
    touches = any(_on(x, y, p) for x, y, p in ((a, b, c), (a, b, d), (c, d, a), (c, d, b)))
    return proper, overlap, touches


def _moments(points):
    origin = points[0]
    local = [(p[0] - origin[0], p[1] - origin[1]) for p in points]
    weights = [_cross(a, b) for a, b in _edges(local)]
    twice = sum(weights, Fraction(0))
    if twice <= 0:
        raise GeometryRejected("nonpositive_or_clockwise_polygon", stage="geometry")
    centroid = tuple(
        origin[axis]
        + sum(
            ((a[axis] + b[axis]) * w for (a, b), w in zip(_edges(local), weights, strict=True)),
            Fraction(0),
        )
        / (3 * twice)
        for axis in (0, 1)
    )
    return twice / 2, centroid


def _complex(vertices, cells, *, stage):
    ids = [row["id"] for row in cells]
    if len(set(ids)) != len(ids):
        raise GeometryRejected("duplicate_cell_id", stage=stage)
    incidence = defaultdict(list)
    polygons = []
    for owner, row in enumerate(cells):
        ring = row["vertex_ids"]
        if (
            not 3 <= len(ring) <= MAX_MERGED_RING
            or len(set(ring)) != len(ring)
            or any(v not in vertices for v in ring)
        ):
            raise GeometryRejected("simple_known_vertex_ring", stage=stage, detail=row["id"])
        points = [vertices[v] for v in ring]
        _moments(points)
        polygons.append(points)
        for i, (a, b) in enumerate(_edges(ring)):
            incidence[tuple(sorted((a, b)))].append((owner, a, b))
            for j, (c, d) in enumerate(_edges(ring)):
                if j <= i:
                    continue
                proper, overlap, touch = _segments(
                    vertices[a], vertices[b], vertices[c], vertices[d]
                )
                adjacent = j in ((i + 1) % len(ring), (i - 1) % len(ring))
                if proper or overlap or (touch and not adjacent):
                    raise GeometryRejected(
                        "polygon_crossing_touch_or_backtrack",
                        stage=stage,
                        detail=dict(cell=row["id"], edges=[i, j]),
                    )
    for edge, owners in incidence.items():
        if len(owners) > 2 or (
            len(owners) == 2
            and (owners[0][0] == owners[1][0] or owners[0][1:] != tuple(reversed(owners[1][1:])))
        ):
            raise GeometryRejected("nonreciprocal_shared_edge", stage=stage, detail=list(edge))
    all_edges = list(incidence)
    for i, (a, b) in enumerate(all_edges):
        for c, d in all_edges[i + 1 :]:
            proper, overlap, touch = _segments(vertices[a], vertices[b], vertices[c], vertices[d])
            if proper or overlap or (touch and not ({a, b} & {c, d})):
                raise GeometryRejected(
                    "nonconforming_edge_join", stage=stage, detail=[[a, b], [c, d]]
                )
    for i, polygon in enumerate(polygons):
        for j in range(i + 1, len(polygons)):
            other = polygons[j]
            if any(_inside(p, other) == 1 for p in polygon) or any(
                _inside(p, polygon) == 1 for p in other
            ):
                raise GeometryRejected(
                    "polygon_interior_overlap", stage=stage, detail=[ids[i], ids[j]]
                )
    incoming, outgoing = Counter(), Counter()
    boundary_cross = Fraction(0)
    for owners in incidence.values():
        if len(owners) == 1:
            _, a, b = owners[0]
            outgoing[a] += 1
            incoming[b] += 1
            boundary_cross += _cross(vertices[a], vertices[b])
    if any(incoming[v] != 1 or outgoing[v] != 1 for v in set(incoming) | set(outgoing)):
        raise GeometryRejected("nonmanifold_boundary_vertex", stage=stage)
    area = sum((_moments(p)[0] for p in polygons), Fraction(0))
    if 2 * area != boundary_cross:
        raise GeometryRejected("boundary_area_balance", stage=stage)
    return incidence, area


def _merge(vertices, source_cells, groups):
    lookup = {row["id"]: row for row in source_cells}
    flat = [name for row in groups for name in row["source_cell_ids"]]
    if (
        len(flat) != len(set(flat))
        or set(flat) != set(lookup)
        or len({row["id"] for row in groups}) != len(groups)
    ):
        raise GeometryRejected("cell_group_partition", stage="merge")
    result = []
    for group in groups:
        half = defaultdict(list)
        for name in group["source_cell_ids"]:
            for a, b in _edges(lookup[name]["vertex_ids"]):
                half[tuple(sorted((a, b)))].append((a, b))
        boundary = [owners[0] for owners in half.values() if len(owners) == 1]
        next_vertex = {}
        incoming = Counter()
        for a, b in boundary:
            if a in next_vertex:
                raise GeometryRejected("merge_boundary_branch", stage="merge", detail=group["id"])
            next_vertex[a] = b
            incoming[b] += 1
        if (
            not boundary
            or any(incoming[v] != 1 for v in next_vertex)
            or set(incoming) != set(next_vertex)
        ):
            raise GeometryRejected(
                "merge_boundary_not_one_simple_ring", stage="merge", detail=group["id"]
            )
        start = boundary[0][0]
        ring = []
        cursor = start
        while cursor not in ring:
            ring.append(cursor)
            cursor = next_vertex[cursor]
        if cursor != start or len(ring) != len(boundary):
            raise GeometryRejected("disconnected_or_holed_merge", stage="merge", detail=group["id"])
        if len(ring) > MAX_MERGED_RING:
            raise GeometryRejected("merged_ring_count", stage="merge")
        if _moments([vertices[v] for v in ring])[0] != sum(
            (
                _moments([vertices[v] for v in lookup[name]["vertex_ids"]])[0]
                for name in group["source_cell_ids"]
            ),
            Fraction(0),
        ):
            raise GeometryRejected("merge_area_balance", stage="merge")
        result.append(
            dict(id=group["id"], vertex_ids=ring, source_cell_ids=group["source_cell_ids"])
        )
    return result


def _rounded(value, label):
    return arithmetic._round(value, label), dict(
        kind="correctly_rounded_binary_rational", exact=_ratio(value)
    )


def _root(value, label):
    if value == 0:
        return _rounded(Fraction(0), label)
    rounded, certificate = arithmetic._irrational(
        lambda bits: arithmetic._sqrt_bounds(value, bits), label
    )
    return rounded, dict(certificate, radicand=_ratio(value))


def _edge_geometry(a, b, height):
    delta = (b[0] - a[0], b[1] - a[1])
    squared = sum((v * v for v in delta), Fraction(0))
    if squared <= 0:
        raise GeometryRejected("zero_edge", stage="measures")
    length, length_cert = _root(squared, "edge_length_m")
    area, area_cert = _root(squared * height * height, "membrane_area_m2")
    midpoint, mid_certs = zip(
        *[_rounded((x + y) / 2, "edge_midpoint_m") for x, y in zip(a, b, strict=True)], strict=True
    )
    tangent = []
    tangent_certs = []
    for value in delta:
        component, certificate = _root(value * value / squared, "unit_tangent")
        sign = -1 if value < 0 else 1
        tangent.append(sign * component)
        tangent_certs.append(dict(certificate, sign=sign))
    normal = (tangent[1], -tangent[0])
    return dict(
        length_m=length,
        area_m2=area,
        midpoint_m=list(midpoint),
        tangent_xy=tangent,
        normal_xy=list(normal),
        certificates=dict(
            length=length_cert, area=area_cert, midpoint=list(mid_certs), tangent=tangent_certs
        ),
    )


def _platform():
    if hashlib.sha256(Path(arithmetic.__file__).read_bytes()).hexdigest() != ARITHMETIC_SHA256:
        raise GeometryRejected("changed_rounding_helpers", stage="platform")
    if (
        sys.float_info.radix,
        sys.float_info.mant_dig,
        sys.float_info.min_exp,
        sys.float_info.max_exp,
    ) != (2, 53, -1021, 1024):
        raise GeometryRejected("binary64_platform", stage="platform")
    tiny = float.fromhex("0x0.0000000000001p-1022")
    half = math.ldexp(1.0, -53)
    if (
        tiny + tiny != float.fromhex("0x0.0000000000002p-1022")
        or 1.0 + half != 1.0
        or 1.0 + 1.5 * half != math.nextafter(1.0, math.inf)
    ):
        raise GeometryRejected("rounding_environment", stage="platform")


def _construct(request):
    raw = request.declaration
    names = [row["id"] for row in raw["vertices"]]
    coordinates = [tuple(Fraction.from_float(v) for v in row["xy_m"]) for row in raw["vertices"]]
    if len(set(names)) != len(names) or len(set(coordinates)) != len(coordinates):
        raise GeometryRejected("duplicate_vertex_identity_or_coordinate", stage="geometry")
    vertices = dict(zip(names, coordinates, strict=True))
    used = {v for row in raw["source_cells"] for v in row["vertex_ids"]}
    if used != set(vertices):
        raise GeometryRejected("unowned_vertex", stage="geometry")
    source_incidence, source_area = _complex(vertices, raw["source_cells"], stage="source_complex")
    merged = _merge(vertices, raw["source_cells"], raw["cell_groups"])
    incidence, merged_area = _complex(vertices, merged, stage="physical_complex")
    if source_area != merged_area:
        raise GeometryRejected("merged_complex_area", stage="merge")
    bath_ids = [row["id"] for row in raw["baths"]]
    if len(set(bath_ids)) != len(bath_ids) or set(bath_ids) & {row["id"] for row in merged}:
        raise GeometryRejected("physical_owner_ids", stage="owners")
    assignment = raw["bath_assignment"]
    if assignment["kind"] == "one_explicit_bath@1":
        edge_bath = {edge: assignment["bath_id"] for edge in incidence}
    else:
        edge_bath = {}
        for row in assignment["rows"]:
            edge = tuple(sorted(row["vertex_ids"]))
            if edge in edge_bath or edge not in incidence or row["bath_id"] not in bath_ids:
                raise GeometryRejected("edge_bath_ownership", stage="owners", detail=row)
            edge_bath[edge] = row["bath_id"]
        if set(edge_bath) != set(incidence):
            raise GeometryRejected("incomplete_edge_baths", stage="owners")
    if set(edge_bath.values()) != set(bath_ids):
        raise GeometryRejected("unused_or_unknown_bath", stage="owners")
    height = Fraction.from_float(raw["height_m"])
    cells = []
    for row in merged:
        area, centroid = _moments([vertices[v] for v in row["vertex_ids"]])
        rounded_area, area_cert = _rounded(area, "cell_area_m2")
        volume, volume_cert = _rounded(area * height, "cell_volume_m3")
        centers, center_certs = zip(
            *[_rounded(v, "cell_centroid_m") for v in centroid], strict=True
        )
        cells.append(
            dict(
                row,
                area_m2=rounded_area,
                volume_m3=volume,
                centroid_m=list(centers),
                membrane_ids=[],
                certificates=dict(area=area_cert, volume=volume_cert, centroid=list(center_certs)),
            )
        )
    edges = []
    membranes = []
    contacts = []
    for edge, owners in incidence.items():
        edge_id = "edge-" + _digest(list(edge))
        metric = _edge_geometry(vertices[edge[0]], vertices[edge[1]], height)
        mids = []
        for owner, a, b in owners:
            mid = "membrane-" + _digest([cells[owner]["id"], a, b])
            direction = 1 if (a, b) == edge else -1
            normal = [direction * v for v in metric["normal_xy"]]
            tangent = [direction * v for v in metric["tangent_xy"]]
            membranes.append(
                dict(
                    id=mid,
                    cell_id=cells[owner]["id"],
                    bath_id=edge_bath[edge],
                    edge_id=edge_id,
                    vertex_ids=[a, b],
                    area_m2=metric["area_m2"],
                    thickness_m=raw["thickness_m"],
                    normal_xy=normal,
                    tangent_xy=tangent,
                    partner_id=None,
                )
            )
            cells[owner]["membrane_ids"].append(mid)
            mids.append(mid)
        selected = membranes[-len(owners) :]
        for i, membrane in enumerate(selected):
            membrane["partner_id"] = mids[1 - i] if len(owners) == 2 else mids[i]
        if len(owners) == 2:
            contacts.append(
                dict(
                    id="contact-" + _digest(list(edge)),
                    edge_id=edge_id,
                    membrane_ids=mids,
                    sender=cells[owners[0][0]]["id"],
                    receiver=cells[owners[1][0]]["id"],
                    area_m2=metric["area_m2"],
                    normal_xy=selected[0]["normal_xy"],
                    vertex_ids=selected[0]["vertex_ids"],
                )
            )
        edges.append(
            dict(
                id=edge_id,
                vertex_ids=list(edge),
                cell_ids=[cells[i]["id"] for i, _, _ in owners],
                membrane_ids=mids,
                bath_id=edge_bath[edge],
                **metric,
            )
        )
    # Restore each cell's original directed boundary sequence explicitly. The
    # edge discovery order is a different axis, with an exact declared map.
    mem_by_edge = {(m["cell_id"], tuple(m["vertex_ids"])): m["id"] for m in membranes}
    for cell in cells:
        cell["membrane_ids"] = [
            mem_by_edge[(cell["id"], edge)] for edge in _edges(cell["vertex_ids"])
        ]
    cell_ids = [row["id"] for row in cells]
    owner_ids = cell_ids + bath_ids
    physical_ids = owner_ids + [row["id"] for row in membranes] + [row["id"] for row in contacts]
    if len(set(physical_ids)) != len(physical_ids):
        raise GeometryRejected("physical_owner_and_route_id_collision", stage="owners")
    membrane_incidence = [
        [int(owner == m["bath_id"]) - int(owner == m["cell_id"]) for m in membranes]
        for owner in owner_ids
    ]
    contact_incidence = [
        [int(owner == c["receiver"]) - int(owner == c["sender"]) for c in contacts]
        for owner in owner_ids
    ]
    if any(sum(row[i] for row in membrane_incidence) != 0 for i in range(len(membranes))) or any(
        sum(row[i] for row in contact_incidence) != 0 for i in range(len(contacts))
    ):
        raise GeometryRejected("owner_incidence_balance", stage="owners")
    physical_vertices = {v for cell in cells for v in cell["vertex_ids"]}
    return dict(
        kind=RESULT_KIND,
        law=LAW_ID,
        request_identity=request.identity,
        source=raw["source"],
        units=UNITS,
        height_m=raw["height_m"],
        thickness_m=raw["thickness_m"],
        axial_caps=raw["axial_caps"],
        vertices=raw["vertices"],
        physical_vertex_ids=[name for name in names if name in physical_vertices],
        source_only_vertex_ids=[name for name in names if name not in physical_vertices],
        source_cells=raw["source_cells"],
        cell_groups=raw["cell_groups"],
        cells=cells,
        edges=edges,
        membranes=membranes,
        contacts=contacts,
        baths=raw["baths"],
        owner_axis=owner_ids,
        membrane_incidence=membrane_incidence,
        contact_incidence=contact_incidence,
        geometry_checks=dict(
            source_complex_validated=True,
            physical_complex_validated=True,
            shared_edges_exact_and_opposite=True,
            source_area_exact=_ratio(source_area),
            merged_area_exact=_ratio(merged_area),
            source_edges=len(source_incidence),
            physical_edges=len(incidence),
            merge_internal_edges_removed=len(source_incidence) - len(incidence),
            each_source_cell_owned_once=True,
        ),
        measure_policy="exact_polygon_area_times_uniform_extrusion_height@1",
        contact_policy="one_shared_edge_surface_with_reciprocal_half_membranes@1",
        bath_volume_policy="explicit_physical_volume_no_geometric_exterior_tessellation@1",
        thickness_policy="zero_volume_interface_with_explicit_constitutive_path_length@1",
        arithmetic_helper_sha256=ARITHMETIC_SHA256,
        candidate_geometry_and_owner_admission=True,
        physical_model_prepared=False,
        native_equivalence=False,
        B09_admission_inherited=False,
        biological_calibration=False,
        scientific_qualification_inherited=False,
        conservation_scope=(
            "Exact interface ownership/incidence and geometric measures; "
            "no simulated mass/charge/energy trajectory claim"
        ),
    )


def prepare(request):
    validate_request(request)
    try:
        _platform()
        geometry = _construct(request)
    except (GeometryRejected, arithmetic.GeometryRejected) as error:
        if isinstance(error, arithmetic.GeometryRejected):
            error = GeometryRejected(
                error.code, stage="arithmetic/" + error.stage, detail=error.detail
            )
        error.trial = dict(
            request=request_record(request),
            status="retained_geometry_or_owner_refusal",
            code=error.code,
            stage=error.stage,
            detail=error.detail,
            native_equivalence=False,
            physical_model_prepared=False,
        )
        raise error
    return Binding(request.identity, _json(geometry), _digest(geometry))


def validate_binding(request, binding):
    if (
        type(binding) is not Binding
        or type(binding.geometry_json) is not str
        or binding.request_identity != request.identity
    ):
        raise GeometryRejected("binding_ownership", stage="identity")
    expected = prepare(request)
    if binding.geometry_json != expected.geometry_json or binding.identity != expected.identity:
        raise GeometryRejected("changed_geometry_or_owners", stage="identity")
    return binding
