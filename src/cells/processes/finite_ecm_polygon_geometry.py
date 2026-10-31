"""Explicit finite cell/ECM partition with orthogonal bath-face distances.

Thin membranes occupy an explicitly zero excluded volume; their constitutive
path is caller supplied. Bath volumes come only from their declared polygons.
This law has no native mesh, whole-mesh or pending polygon qualification credit.
"""

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from cells.processes import conservative_polygon_geometry as exact

LAW_ID = "cells_finite_ecm_conforming_polygon_partition@1"
REQUEST_KIND = "cells.finite_ecm_polygon_request@1"
RESULT_KIND = "cells.finite_ecm_polygon_binding@1"
EXACT_HELPERS_SHA256 = "5d267b20cdb3a05f4f036bbc3fa6978b40780ca4394f67ac6c33a8b605af4b0d"
MAX_REGIONS = 32
MAX_CELLS = 16
MAX_VERTICES = 256
MAX_RING = 64
MAX_HALF_EDGES = 512
UNITS = dict(coordinates="m", height="m", membrane_path="m", area="m2", volume="m3")


class PartitionRejected(ValueError):
    def __init__(self, reason, *, stage, trial=None):
        super().__init__(reason)
        self.stage, self.trial = stage, trial


@dataclass(frozen=True, slots=True)
class Request:
    declaration_json: str
    identity: str

    @property
    def declaration(self):
        return json.loads(self.declaration_json)


@dataclass(frozen=True, slots=True)
class Binding:
    geometry_json: str
    identity: str

    @property
    def geometry(self):
        return json.loads(self.geometry_json)


def _ratio(row):
    return Fraction(int(row["numerator"]), int(row["denominator"]))


def _canonical(raw):
    exact._keys(
        raw,
        {
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
        },
        "finite_ecm_input",
    )
    exact._keys(raw["source"], {"kind", "generator", "provenance"}, "finite_ecm_source")
    if (
        raw["source"]["kind"] != "explicit_cell_bath_partition@1"
        or type(raw["source"]["provenance"]) is not dict
        or not raw["source"]["provenance"]
    ):
        raise ValueError("Require complete explicit cell and bath polygon provenance")
    exact._id(raw["source"]["generator"])
    if (
        raw["units"] != UNITS
        or raw["membrane_geometry_policy"] != "zero_volume_interface_explicit_path@1"
        or raw["face_distance_policy"] != "orthogonal_volume_centroids_shared_face@1"
        or raw["axial_caps"] != "sealed_no_transport@1"
    ):
        raise ValueError("Unsupported finite-ECM units, membrane, face or axial-boundary policy")
    if type(raw["vertices"]) is not list or not 3 <= len(raw["vertices"]) <= MAX_VERTICES:
        raise ValueError("Require 3..256 explicit partition vertices")
    vertices = []
    for row in raw["vertices"]:
        exact._keys(row, {"id", "xy_m"}, "partition_vertex")
        if type(row["xy_m"]) is not list or len(row["xy_m"]) != 2:
            raise ValueError("Require explicit planar binary64 vertices")
        vertices.append(dict(id=exact._id(row["id"]), xy_m=[exact._number(v) for v in row["xy_m"]]))
    if type(raw["regions"]) is not list or not 2 <= len(raw["regions"]) <= MAX_REGIONS:
        raise ValueError("Require 2..32 physical regions")
    regions = []
    for row in raw["regions"]:
        exact._keys(row, {"id", "kind", "vertex_ids"}, "partition_region")
        if (
            row["kind"] not in ("cell", "bath")
            or type(row["vertex_ids"]) is not list
            or not 3 <= len(row["vertex_ids"]) <= MAX_RING
        ):
            raise ValueError("Require identified convex cell or bath polygons with 3..64 vertices")
        regions.append(
            dict(
                id=exact._id(row["id"]),
                kind=row["kind"],
                vertex_ids=[exact._id(v) for v in row["vertex_ids"]],
            )
        )
    if (
        not 1 <= sum(row["kind"] == "cell" for row in regions) <= MAX_CELLS
        or not any(row["kind"] == "bath" for row in regions)
        or sum(len(row["vertex_ids"]) for row in regions) > MAX_HALF_EDGES
    ):
        raise ValueError("Require 1..16 cells, finite bath polygons and at most512 directed edges")
    ring = raw["domain_vertex_ids"]
    if type(ring) is not list or not 3 <= len(ring) <= MAX_VERTICES:
        raise ValueError("Require one explicit complete outer domain ring")
    ring = [exact._id(v) for v in ring]
    if type(raw["boundary"]) is not list:
        raise ValueError("Every exterior polygon side must declare its boundary condition")
    boundary = []
    for row in raw["boundary"]:
        exact._keys(row, {"region_id", "vertex_ids", "condition"}, "partition_boundary")
        if (
            type(row["vertex_ids"]) is not list
            or len(row["vertex_ids"]) != 2
            or row["condition"] != "sealed_no_transport@1"
        ):
            raise ValueError("Only explicit sealed outer polygon sides are supported")
        boundary.append(
            dict(
                region_id=exact._id(row["region_id"]),
                vertex_ids=[exact._id(v) for v in row["vertex_ids"]],
                condition=row["condition"],
            )
        )
    return dict(
        raw,
        vertices=vertices,
        regions=regions,
        domain_vertex_ids=ring,
        boundary=boundary,
        height_m=exact._number(raw["height_m"], positive=True),
        membrane_thickness_m=exact._number(raw["membrane_thickness_m"], positive=True),
    )


def from_partition(declaration, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise PartitionRejected(
            "Require explicit finite-ECM polygon law opt-in", stage="opt_in", trial=declaration
        )
    raw = json.loads(exact._json(declaration))
    try:
        raw = _canonical(raw)
    except Exception as error:
        raise PartitionRejected(str(error), stage="input", trial=raw) from error
    return Request(
        exact._json(raw), exact._digest(dict(kind=REQUEST_KIND, law=LAW_ID, declaration=raw))
    )


def request_record(request):
    if type(request) is not Request:
        raise ValueError("Require complete immutable finite-ECM request")
    return dict(
        kind=REQUEST_KIND, law=LAW_ID, declaration=request.declaration, identity=request.identity
    )


def _construct(request):
    raw = request.declaration
    vertices = {
        row["id"]: tuple(Fraction.from_float(v) for v in row["xy_m"]) for row in raw["vertices"]
    }
    if len(vertices) != len(raw["vertices"]) or len(set(vertices.values())) != len(vertices):
        raise ValueError("Distinct partition vertex IDs and coordinates required")
    regions = raw["regions"]
    used = {v for row in regions for v in row["vertex_ids"]}
    if used != set(vertices):
        raise ValueError("Every supplied vertex must belong to the complete partition")
    incidence, total_area = exact._complex(vertices, regions, stage="finite_ecm_partition")
    ring = raw["domain_vertex_ids"]
    exact._complex(vertices, [dict(id="domain", vertex_ids=ring)], stage="finite_ecm_domain")
    if exact._moments([vertices[v] for v in ring])[0] != total_area:
        raise ValueError("Region area must exactly exhaust the declared domain")
    outer = {
        tuple(owners[0][1:]): regions[owners[0][0]]["id"]
        for owners in incidence.values()
        if len(owners) == 1
    }
    if set(outer) != set(exact._edges(ring)):
        raise ValueError("Require one complete conforming outer boundary with no gaps or holes")
    declared = {tuple(row["vertex_ids"]): row["region_id"] for row in raw["boundary"]}
    if len(declared) != len(raw["boundary"]) or declared != outer:
        raise ValueError("Boundary rows must match every actual directed exterior side and owner")
    centers = {}
    for row in regions:
        points = [vertices[v] for v in row["vertex_ids"]]
        if any(exact._orient(a, b, p) < 0 for a, b in exact._edges(points) for p in points):
            raise ValueError("This finite-ECM law supports convex region polygons only")
        centers[row["id"]] = exact._moments(points)[1]
    neighbors = defaultdict(set)
    for owners in incidence.values():
        if len(owners) == 2:
            a, b = (regions[item[0]]["id"] for item in owners)
            neighbors[a].add(b)
            neighbors[b].add(a)
    reached = {regions[0]["id"]}
    todo = list(reached)
    while todo:
        for name in neighbors[todo.pop()] - reached:
            reached.add(name)
            todo.append(name)
    if reached != {row["id"] for row in regions}:
        raise ValueError("Require one connected finite-ECM partition")
    height = Fraction.from_float(raw["height_m"])
    measures = []
    for row in regions:
        area, center = exact._moments([vertices[v] for v in row["vertex_ids"]])
        area_value, area_cert = exact._rounded(area, "region_area_m2")
        volume, volume_cert = exact._rounded(area * height, "region_volume_m3")
        center_values, center_certs = zip(
            *[exact._rounded(v, "region_centroid_m") for v in center], strict=True
        )
        measures.append(
            dict(
                row,
                area_m2=area_value,
                volume_m3=volume,
                centroid_m=list(center_values),
                certificates=dict(area=area_cert, volume=volume_cert, centroid=list(center_certs)),
            )
        )
    edges = []
    membranes = []
    faces = []
    boundary = []
    half_edges = []
    for edge, owners in incidence.items():
        edge_id = "ecm-edge-" + exact._digest(list(edge))
        metric = exact._edge_geometry(vertices[edge[0]], vertices[edge[1]], height)
        owner_names = [regions[item[0]]["id"] for item in owners]
        row = dict(id=edge_id, vertex_ids=list(edge), region_ids=owner_names, **metric)
        if len(owners) == 1:
            index, a, b = owners[0]
            if regions[index]["kind"] != "bath":
                raise ValueError("A physical cell cannot meet the sealed domain boundary")
            route = dict(
                id="ecm-boundary-" + exact._digest(list(edge)),
                edge_id=edge_id,
                region_id=regions[index]["id"],
                vertex_ids=[a, b],
                condition="sealed_no_transport@1",
                area_m2=metric["area_m2"],
            )
            boundary.append(route)
            kind = "boundary"
        else:
            roles = [regions[item[0]]["kind"] for item in owners]
            if roles == ["cell", "cell"]:
                raise ValueError(
                    "Direct cell-cell interfaces have no declared finite cleft geometry"
                )
            if "cell" in roles:
                ci = roles.index("cell")
                bi = 1 - ci
                _, a, b = owners[ci]
                route = dict(
                    id="ecm-membrane-" + exact._digest(list(edge)),
                    edge_id=edge_id,
                    cell_id=owner_names[ci],
                    bath_id=owner_names[bi],
                    vertex_ids=[a, b],
                    area_m2=metric["area_m2"],
                    thickness_m=raw["membrane_thickness_m"],
                )
                membranes.append(route)
                kind = "membrane"
            else:
                sender, receiver = owner_names
                _, a, b = owners[0]
                left, right = centers[sender], centers[receiver]
                pa, pb = vertices[a], vertices[b]
                tangent = tuple(y - x for x, y in zip(pa, pb, strict=True))
                delta = tuple(y - x for x, y in zip(left, right, strict=True))
                norm2 = sum(v * v for v in tangent)
                if sum(d * t for d, t in zip(delta, tangent, strict=True)) != 0:
                    raise ValueError(
                        "Bath centroid link is not exactly orthogonal to its shared face"
                    )
                if exact._orient(pa, pb, left) <= 0 or exact._orient(pa, pb, right) >= 0:
                    raise ValueError("Bath centroids must lie strictly on their actual face sides")
                alpha = sum((p - x) * t for p, x, t in zip(left, pa, tangent, strict=True)) / norm2
                if not 0 < alpha < 1:
                    raise ValueError(
                        "Common normal projection must lie strictly inside the shared face"
                    )
                foot = tuple(x + alpha * t for x, t in zip(pa, tangent, strict=True))
                foot_value, foot_cert = zip(
                    *[exact._rounded(v, "face_common_projection_m") for v in foot], strict=True
                )
                length, length_cert = exact._root(
                    sum(v * v for v in delta), "face_centroid_distance_m"
                )
                side_values = []
                side_certs = []
                for center in (left, right):
                    value, cert = exact._root(
                        sum((p - f) ** 2 for p, f in zip(center, foot, strict=True)),
                        "face_centroid_to_interface_distance_m",
                    )
                    side_values.append(value)
                    side_certs.append(cert)
                route = dict(
                    id="ecm-face-" + exact._digest(list(edge)),
                    edge_id=edge_id,
                    sender=sender,
                    receiver=receiver,
                    vertex_ids=[a, b],
                    area_m2=metric["area_m2"],
                    length_m=length,
                    centroid_to_face_m=side_values,
                    common_projection_m=list(foot_value),
                    certificates=dict(
                        length=length_cert,
                        centroid_to_face=side_certs,
                        common_projection=list(foot_cert),
                    ),
                )
                faces.append(route)
                kind = "face"
        direction = 1 if tuple(route["vertex_ids"]) == edge else -1
        route["normal_xy"] = [direction * v for v in metric["normal_xy"]]
        route["tangent_xy"] = [direction * v for v in metric["tangent_xy"]]
        row.update(interface_kind=kind, interface_id=route["id"])
        edges.append(row)
        for index, a, b in owners:
            direction = 1 if (a, b) == edge else -1
            half_edges.append(
                dict(
                    region_id=regions[index]["id"],
                    vertex_ids=[a, b],
                    edge_id=edge_id,
                    interface_id=route["id"],
                    interface_kind=kind,
                    normal_xy=[direction * v for v in metric["normal_xy"]],
                    neighbor_id=next(
                        (name for name in owner_names if name != regions[index]["id"]), None
                    ),
                )
            )
    cells = [row["id"] for row in regions if row["kind"] == "cell"]
    baths = [row["id"] for row in regions if row["kind"] == "bath"]
    if {row["cell_id"] for row in membranes} != set(cells) or not faces:
        raise ValueError(
            "Require membrane ownership for every cell and at least one bath-bath face"
        )
    owners = cells + baths
    names = owners + [row["id"] for row in edges + membranes + faces + boundary]
    if len(set(names)) != len(names):
        raise ValueError("Global physical region, edge and interface IDs must be distinct")

    def incidence_matrix(routes, ends):
        return [
            [int(owner == route[ends[1]]) - int(owner == route[ends[0]]) for route in routes]
            for owner in owners
        ]

    return dict(
        kind=RESULT_KIND,
        law=LAW_ID,
        request_identity=request.identity,
        source=raw["source"],
        vertices=raw["vertices"],
        domain_vertex_ids=ring,
        regions=measures,
        cell_ids=cells,
        bath_ids=baths,
        edges=edges,
        half_edges=half_edges,
        membranes=membranes,
        faces=faces,
        boundary=boundary,
        owner_axis=owners,
        membrane_incidence=incidence_matrix(membranes, ("cell_id", "bath_id")),
        face_incidence=incidence_matrix(faces, ("sender", "receiver")),
        height_m=raw["height_m"],
        membrane_thickness_m=raw["membrane_thickness_m"],
        domain_area_exact=exact._ratio(total_area),
        domain_volume_exact=exact._ratio(total_area * height),
        units=UNITS,
        face_distance_policy=raw["face_distance_policy"],
        membrane_geometry_policy=raw["membrane_geometry_policy"],
        axial_caps=raw["axial_caps"],
        native_equivalence=False,
        qualification_inherited=False,
        cell_cell_contacts_supported=False,
        outer_transport_supported=False,
    )


def prepare(request):
    stage = "request_authority"
    try:
        if (
            type(request) is not Request
            or from_partition(request.declaration, law_id=LAW_ID) != request
        ):
            raise ValueError("Changed or incomplete finite-ECM partition authority")
        stage = "pinned_exact_predicates_and_binary64_platform"
        if hashlib.sha256(Path(exact.__file__).read_bytes()).hexdigest() != EXACT_HELPERS_SHA256:
            raise ValueError("Changed pinned exact geometry helpers")
        exact._platform()
        stage = "partition_and_physical_faces"
        result = _construct(request)
        return Binding(exact._json(result), exact._digest(result))
    except Exception as error:
        raise PartitionRejected(
            str(error),
            stage=stage,
            trial=dict(
                request=request_record(request) if type(request) is Request else None,
                failure_type=type(error).__name__,
                reason=str(error),
                physical_model_prepared=False,
            ),
        ) from error


def validate_binding(request, binding):
    if type(binding) is not Binding or prepare(request) != binding:
        raise ValueError("Changed finite-ECM geometry, distances, physical owner or boundary")
    return binding
