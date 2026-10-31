"""Certified centroid-layout mesh metrics on explicitly corrected topology.

Coordinates and source axes remain fixed. Areas/centroids are exact rational
targets; lengths and directions use the existing certified dyadic square-root
helpers. Native reference-area owners are explicit, not nearest-neighbor ties.
This metric candidate supplies no inverse operator or physical admission.
"""

import hashlib
import math
from dataclasses import dataclass, fields, is_dataclass, replace
from fractions import Fraction
from pathlib import Path

from cells.processes import conservative_polygon_geometry as polygons
from cells.processes import stable_geometry_primitives as arithmetic
from cells.processes import stable_mesh_physical_reconstruction as topology

LAW_ID = "cells_stable_corrected_topology_centroid_mesh_metrics@1"
INPUT_KIND = "cells.stable_mesh_metric_reconstruction_request@1"
UNITS = dict(
    coordinates="m",
    edge_lengths="m",
    polygon_areas="m2",
    directions="1",
    length_ratios="1",
    inverse_areas="1/m2",
)
SOURCE_PINS = (
    (
        "stable_mesh_physical_reconstruction",
        "b0633f93978dba2db684e23ee1e3e348c0f3edde624b3069c57b115e3d7ab582",
    ),
    (
        "stable_geometry_primitives",
        "c9fab4f34aa9166711431844f2af72eb6b8fe4873154bfe01dfce3f656326958",
    ),
    (
        "conservative_polygon_geometry",
        "5d267b20cdb3a05f4f036bbc3fa6978b40780ca4394f67ac6c33a8b605af4b0d",
    ),
)
INVALIDATED = (
    "all_original_metric_arrays",
    "circumcentres_and_circumradii_not_required_by_centroid_layout",
    "inverse_DEC_operators",
    "graph_Laplacians_and_inverses",
    "scaled_physical_cells",
    "physical_membrane_measures_and_volumes",
    "gap_boundary_profile_maps",
    "environment_grid_maps_volumes_and_inverses",
    "initializer_sigma_ko",
    "all_loop_state_bindings",
)


@dataclass(frozen=True)
class Request:
    topology_request: topology.Request
    topology_candidate: topology.Candidate
    declaration: object
    identity: str


@dataclass(frozen=True)
class Candidate:
    request_identity: str
    topology_identity: str
    native_roles: object
    full_dual_metrics: object
    coefficients: object
    anchor_roles: object
    certificates: object
    diagnostics: object
    prerequisites: object
    identity: str


class MetricRejected(ValueError):
    def __init__(self, reason, *, stage, original=None, partial=None):
        super().__init__("Mesh metric candidate refused at " + stage + ": " + str(reason))
        self.stage, self.original, self.partial = stage, original, partial


class _Refusal(ValueError):
    def __init__(self, reason, detail):
        super().__init__(reason)
        self.detail = detail


def plain(value):
    if is_dataclass(value):
        return {field.name: plain(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Fraction):
        return dict(numerator=str(value.numerator), denominator=str(value.denominator))
    if isinstance(value, dict) or hasattr(value, "items"):
        return {key: plain(child) for key, child in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(child) for child in value]
    return value


def digest(value):
    return topology.digest(plain(value))


def _verify_sources():
    for (name, expected), module in zip(SOURCE_PINS, (topology, arithmetic, polygons), strict=True):
        if (
            module.__name__.rsplit(".", 1)[-1] != name
            or hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() != expected
        ):
            raise ValueError("Changed metric dependency: " + name)


def request_record(value):
    return (LAW_ID, value.topology_request, value.topology_candidate, value.declaration)


def bind(parent, corrected, declaration):
    _verify_sources()
    if not isinstance(declaration, dict) or set(declaration) != {
        "kind",
        "opted_in_law",
        "units",
        "layout_policy",
    }:
        raise ValueError("Declare the separate complete metric law and units")
    if (
        declaration["kind"] != INPUT_KIND
        or declaration["opted_in_law"] != LAW_ID
        or declaration["units"] != UNITS
    ):
        raise ValueError("Require explicit metre/m2 metric law; no coordinate conversion")
    if declaration["layout_policy"] != "preserve_source_centroid_and_reflection_coordinates":
        raise ValueError("The supplied geometry is fixed; no re-layout or snapped centres")
    if type(parent) is not topology.Request or type(corrected) is not topology.Candidate:
        raise ValueError("Require the complete explicitly corrected topology and original request")
    if parent.identity != topology.digest(topology.request_record(parent)):
        raise ValueError("Changed original topology request")
    rebuilt = topology.reconstruct(parent)
    if corrected.identity != rebuilt.identity or digest(corrected) != digest(rebuilt):
        raise ValueError("Changed corrected topology or owner axes")
    if parent.original_cache["use_centroids"] is not True:
        raise ValueError(
            "This metric law requires centroid layout; circumcenter layout is separate"
        )
    for key in ("tri_cents", "tri_verts", "tri_cells", "vor_verts", "vor_cells"):
        if key not in parent.original_cache:
            raise ValueError("Missing actual source metric-role owner: " + key)
    result = Request(parent, corrected, topology.freeze(declaration), "")
    return replace(result, identity=digest(request_record(result)))


def _fraction_points(points):
    return [tuple(Fraction.from_float(value) for value in point) for point in points]


def _ratio(value):
    return dict(numerator=str(value.numerator), denominator=str(value.denominator))


def _stored(value, label):
    value, certificate = polygons._rounded(value, label)
    return value, dict(certificate, store_seam="correctly_rounded_binary64")


def _root(value, label):
    return polygons._root(value, label)


class _Work:
    def __init__(self):
        self.events = []

    def call(self, target, label, *, root):
        row = dict(
            sequence=len(self.events),
            label=label,
            operation="dyadic_square_root" if root else "rational_round",
            input_exact=_ratio(target),
        )
        self.events.append(row)
        try:
            value, certificate = (_root if root else _stored)(target, label)
            certificate = dict(certificate, arithmetic_event_index=row["sequence"])
        except Exception as error:
            row["failure"] = dict(
                type=type(error).__name__,
                reason=str(error),
                detail=plain(getattr(error, "detail", None)),
                trial=plain(getattr(error, "trial", None)),
            )
            raise
        row["returned"] = dict(value=value, binary64_hex=value.hex(), certificate=certificate)
        return value, certificate

    def rounded(self, target, label):
        return self.call(target, label, root=False)

    def root(self, target, label):
        return self.call(target, label, root=True)


def _edge_metrics(points, edges, work, *, partial=None):
    values, certificates, squared = [], [], []
    if partial is not None:
        partial.update(values=values, certificates=certificates, squared_lengths_exact=squared)
    for index, (a, b) in enumerate(edges):
        x, y = points[a], points[b]
        delta = tuple(q - p for p, q in zip(x, y, strict=True))
        norm2 = sum((v * v for v in delta), Fraction(0))
        if norm2 <= 0:
            raise ValueError("Zero-length geometric edge: " + str(index))
        length, lc = work.root(norm2, "edge_length_m")
        midpoint, mc = zip(
            *[work.rounded((p + q) / 2, "edge_midpoint_m") for p, q in zip(x, y, strict=True)],
            strict=True,
        )
        tangent, tc = [], []
        for component in delta:
            value, cert = work.root(component * component / norm2, "unit_tangent")
            sign = -1 if component < 0 else 1
            tangent.append(sign * value)
            tc.append(dict(cert, sign=sign))
        values.append(
            dict(
                length_m=length,
                midpoint_m=midpoint,
                tangent_xy=tangent,
                normal_xy=(tangent[1], -tangent[0]),
            )
        )
        certificates.append(dict(length=lc, midpoint=mc, tangent=tc))
        squared.append(norm2)
    return values, certificates, squared


def _polygon_metrics(points, rings, label, work, *, partial=None):
    rows, certificates, exact = [], [], []
    if partial is not None:
        partial.update(values=rows, certificates=certificates, exact_targets=exact)
    for index, ring in enumerate(rings):
        area, centroid = polygons._moments([points[i] for i in ring])
        area_store, ac = work.rounded(area, label + "_area_m2")
        centre_store, cc = zip(
            *[work.rounded(v, label + "_centroid_m") for v in centroid], strict=True
        )
        if area_store <= 0:
            raise ValueError("Unrepresentable positive polygon area: " + str(index))
        rows.append(dict(area_m2=area_store, centroid_m=centre_store))
        certificates.append(dict(area=ac, centroid=cc))
        exact.append((area, centroid))
    return rows, certificates, exact


def _layout_check(actual, target, *, primitive):
    if type(actual) is not float or not math.isfinite(actual):
        raise ValueError("Actual source layout anchor must remain finite binary64")
    error = abs(Fraction.from_float(actual) - target)
    budget = Fraction("1e-27") + Fraction("6e-12") * abs(target)
    row = dict(
        actual_binary64_hex=actual.hex(),
        exact_target=_ratio(target),
        exact_error=_ratio(error),
        fixed_budget=_ratio(budget),
        primitive_32_ulp_required=primitive,
    )
    if error > budget or primitive and error > 32 * Fraction.from_float(math.ulp(actual)):
        raise _Refusal(
            "Source layout anchor does not match its declared centroid/reflection role", row
        )
    return row


def _coalesce_roles(roles, areas):
    values = []
    for vertex, row in enumerate(roles):
        if not row:
            raise ValueError("Missing source area owner for dual vertex: " + str(vertex))
        targets = {areas[role["face"]][0] for role in row}
        if len(targets) != 1:
            raise _Refusal(
                "Ambiguous unequal source face-area roles at dual vertex: " + str(vertex),
                dict(vertex=vertex, roles=row, exact_areas=[_ratio(v) for v in sorted(targets)]),
            )
        values.append(next(iter(targets)))
    return values


def _anchors(request, exact_faces, point_fractions, *, partial=None):
    parent, corrected = request.topology_request, request.topology_candidate
    original = parent.original_cache
    source_centres, vertices = original["tri_cents"], original["vor_verts"]
    if len(source_centres) != len(exact_faces):
        raise ValueError("Incomplete actual source face-centre axis")
    lookup = {point: i for i, point in enumerate(vertices)}
    roles, centres, checks = [[] for _ in vertices], [], []
    if partial is not None:
        partial.update(roles=roles, centre_indices=centres, layout_checks=checks)
    for face, point in enumerate(source_centres):
        point = tuple(point)
        if point not in lookup:
            raise ValueError(
                "Actual source face centre is absent from the retained dual vertex axis"
            )
        checks.append(
            [
                _layout_check(value, target, primitive=True)
                for value, target in zip(point, exact_faces[face][1], strict=True)
            ]
        )
        index = lookup[point]
        centres.append(index)
        roles[index].append(dict(kind="source_face_centroid", face=face))
    for ei, owners in enumerate(corrected.primal["edge_to_faces"]):
        selected = corrected.dual["selected_edges"][ei]
        if len(owners) == 2:
            expected = {centres[owner] for owner in owners}
            if len(expected) != 2 or set(selected) != expected:
                raise ValueError(
                    "Selected interior dual endpoints are not their actual source face centres"
                )
        elif len(owners) == 1:
            face = owners[0]
            if centres[face] not in selected:
                raise ValueError("Boundary dual edge lacks its actual source face centre")
            other = next(i for i in selected if i != centres[face])
            a, b = corrected.primal["edges"][ei]
            # Keep the original layout. The target matches the existing
            # independent native reflection check, using the stored centre.
            target = tuple(
                point_fractions[a][axis]
                + point_fractions[b][axis]
                - Fraction.from_float(source_centres[face][axis])
                for axis in (0, 1)
            )
            check = [
                _layout_check(value, wanted, primitive=False)
                for value, wanted in zip(vertices[other], target, strict=True)
            ]
            checks.append(check)
            roles[other].append(dict(kind="source_boundary_reflection", face=face, primal_edge=ei))
        else:
            raise ValueError("Unsupported primal face ownership")
    reference_areas = _coalesce_roles(roles, exact_faces)
    return roles, centres, checks, reference_areas


def candidate_record(value):
    return (
        LAW_ID,
        value.request_identity,
        value.topology_identity,
        value.native_roles,
        value.full_dual_metrics,
        value.coefficients,
        value.anchor_roles,
        value.certificates,
        value.diagnostics,
        value.prerequisites,
    )


def prepare(request, *, observer=None):
    work = _Work()
    stage, partial = "request", dict(arithmetic_events=work.events)
    try:
        _verify_sources()
        if type(request) is not Request or request.identity != digest(request_record(request)):
            raise ValueError("Changed metric request or corrected topology")
        checked = bind(
            request.topology_request, request.topology_candidate, plain(request.declaration)
        )
        if checked.identity != request.identity or digest(request_record(checked)) != digest(
            request_record(request)
        ):
            raise ValueError("Resealed metric request differs from the complete declaration")
        parent, corrected = request.topology_request, request.topology_candidate
        if digest(topology.reconstruct(parent)) != digest(corrected):
            raise ValueError("Changed corrected topology")
        polygons._platform()
        geometry = corrected.geometry
        points = _fraction_points(geometry["tri_verts"])
        vertices = _fraction_points(geometry["vor_verts"])
        stage = "global_polygon_domains"
        for row in geometry["tri_cells"]:
            if len(row) not in (3, 4):
                raise ValueError(
                    "Only original triangular/convex quadrilateral primal faces are supported"
                )
            ring = [points[i] for i in row]
            turns = [
                polygons._orient(ring[i - 1], ring[i], ring[(i + 1) % len(ring)])
                for i in range(len(ring))
            ]
            if any(turn <= 0 for turn in turns):
                raise ValueError("Nonconvex/collinear primal face requires a separate metric law")
        for label, coordinates, rings in (
            ("primal", points, geometry["tri_cells"]),
            ("dual", vertices, geometry["vor_cells"]),
        ):
            incidence, total = polygons._complex(
                dict(enumerate(coordinates)),
                [dict(id=str(i), vertex_ids=list(row)) for i, row in enumerate(rings)],
                stage=label,
            )
            partial[label + "_complex"] = dict(total_area_exact=_ratio(total), edges=len(incidence))
        for owner, polygon in enumerate(geometry["vor_cells"]):
            if polygons._inside(points[owner], [vertices[i] for i in polygon]) != 1:
                raise ValueError(
                    "Source seed owner is not strictly inside its retained dual polygon"
                )
        stage = "polygon_metrics"
        partial["primal_metrics"] = {}
        faces, face_cert, exact_faces = _polygon_metrics(
            points, geometry["tri_cells"], "primal", work, partial=partial["primal_metrics"]
        )
        partial["dual_metrics"] = {}
        cells, cell_cert, _ = _polygon_metrics(
            vertices, geometry["vor_cells"], "dual", work, partial=partial["dual_metrics"]
        )
        if observer is not None:
            observer(stage, plain(partial))
        stage = "oriented_edge_metrics"
        partial["primal_edges"] = {}
        tri, tri_cert, tq = _edge_metrics(
            points, corrected.primal["edges"], work, partial=partial["primal_edges"]
        )
        partial["full_dual_edges"] = {}
        full, full_cert, _ = _edge_metrics(
            vertices, corrected.dual["full_edges"], work, partial=partial["full_dual_edges"]
        )
        partial["selected_dual_edges"] = {}
        selected, selected_cert, vq = _edge_metrics(
            vertices, corrected.dual["selected_edges"], work, partial=partial["selected_dual_edges"]
        )
        orientations = []
        for (a, b), (x, y) in zip(
            corrected.primal["edges"], corrected.dual["selected_edges"], strict=True
        ):
            t = tuple(points[b][i] - points[a][i] for i in (0, 1))
            v = tuple(vertices[y][i] - vertices[x][i] for i in (0, 1))
            det = t[0] * v[1] - t[1] * v[0]
            if det >= 0:
                raise ValueError(
                    "Zero/positive dual handedness is outside the strict metric domain"
                )
            orientations.append(
                dict(
                    determinant_exact=_ratio(det),
                    dot_exact=_ratio(sum((x * y for x, y in zip(t, v, strict=True)), Fraction(0))),
                )
            )
        if observer is not None:
            observer(stage, plain(partial))
        stage = "dual_vertex_reference_area_roles"
        partial["dual_vertex_roles"] = {}
        roles, centre_indices, layout_checks, reference_areas = _anchors(
            request, exact_faces, points, partial=partial["dual_vertex_roles"]
        )
        reference_stores, reference_certs = zip(
            *[work.rounded(v, "dual_vertex_reference_area_m2") for v in reference_areas],
            strict=True,
        )
        stage = "native_store_metric_coefficients"
        forward, inverse, geometric, coefficient_certs = [], [], [], []
        partial["coefficients"] = dict(
            native_forward=forward,
            native_inverse=inverse,
            coordinate_geometric=geometric,
            certificates=coefficient_certs,
        )
        for i, (primal, dual) in enumerate(zip(tri, selected, strict=True)):
            a, b = Fraction.from_float(primal["length_m"]), Fraction.from_float(dual["length_m"])
            f, fc = work.rounded(b / a, "native_stored_dual_over_primal")
            r, rc = work.rounded(a / b, "native_stored_primal_over_dual")
            g, gc = work.root(vq[i] / tq[i], "coordinate_geometric_length_ratio")
            forward.append(f)
            inverse.append(r)
            geometric.append(g)
            coefficient_certs.append(
                dict(
                    native_forward=fc,
                    native_inverse=rc,
                    coordinate_geometric=gc,
                    input_store_hex=dict(
                        primal_length=primal["length_m"].hex(), dual_length=dual["length_m"].hex()
                    ),
                )
            )
        inverse_areas, inverse_area_certs = zip(
            *[
                work.rounded(
                    1 / Fraction.from_float(row["area_m2"]), "native_stored_inverse_dual_area"
                )
                for row in cells
            ],
            strict=True,
        )
        native = dict(
            tri_sa=[row["area_m2"] for row in faces],
            tri_cents=[row["centroid_m"] for row in faces],
            vor_sa=[row["area_m2"] for row in cells],
            vor_cents=[row["centroid_m"] for row in cells],
            tri_edge_len=[row["length_m"] for row in tri],
            tri_mids=[row["midpoint_m"] for row in tri],
            tri_tang=[row["tangent_xy"] for row in tri],
            vor_edge_len=[row["length_m"] for row in selected],
            vor_mids=[row["midpoint_m"] for row in selected],
            vor_tang=[row["tangent_xy"] for row in selected],
            tri_sa_o=reference_stores,
            inner_vvert_i=centre_indices,
            tri_ccents=None,
            tri_rcircs=None,
        )
        result = Candidate(
            request.identity,
            corrected.identity,
            topology.freeze(native),
            topology.freeze(full),
            topology.freeze(
                dict(
                    native_stored_dual_over_primal=forward,
                    native_stored_primal_over_dual=inverse,
                    coordinate_geometric_length_ratio=geometric,
                    native_stored_inverse_dual_area=inverse_areas,
                )
            ),
            topology.freeze(roles),
            topology.freeze(
                dict(
                    primal_polygons=face_cert,
                    dual_polygons=cell_cert,
                    primal_edges=tri_cert,
                    full_dual_edges=full_cert,
                    selected_dual_edges=selected_cert,
                    dual_vertex_reference_area=reference_certs,
                    coefficients=coefficient_certs,
                    inverse_dual_area=inverse_area_certs,
                    arithmetic_events=work.events,
                )
            ),
            topology.freeze(
                dict(
                    layout_checks=layout_checks,
                    orientation=orientations,
                    global_complexes={k: v for k, v in partial.items() if k.endswith("_complex")},
                    geometric_orthogonality_required=False,
                    geometric_metric_law="native_centroid_layout_length_ratio",
                    coordinate_bits_preserved=True,
                    source_axes_preserved=True,
                )
            ),
            topology.freeze(
                dict(
                    physical_geometry_admitted=False,
                    native_mesh_cache_admitted=False,
                    layout_regeneration_permitted=False,
                    ordinary_ECM_loop_ready=False,
                    native_equivalence=False,
                    inverse_operators=None,
                    physical_cell_geometry=None,
                    centroid_layout_only=True,
                    original_metric_caches_reused=False,
                    invalidated=INVALIDATED,
                    independent_metric_checks_required=True,
                )
            ),
            "",
        )
        return replace(result, identity=digest(candidate_record(result)))
    except Exception as error:
        detail = dict(
            type=type(error).__name__,
            reason=str(error),
            stage=getattr(error, "stage", None),
            detail=getattr(error, "detail", None),
            trial=getattr(error, "trial", None),
        )
        raise MetricRejected(
            error,
            stage=stage,
            original=request,
            partial=topology.freeze(plain(dict(completed=partial, source_error=detail))),
        ) from error


def require_physical_admission(candidate):
    raise MetricRejected(
        "Metric reconstruction does not qualify inverse operators, physical cells, "
        "environment or the initialized loop",
        stage="physical_admission",
        original=candidate,
    )
