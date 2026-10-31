"""Prospective exact bounded Voronoi control volumes on immutable source seeds.

The explicit envelope and rebuilt connectivity define a new geometry law.
Exact targets and shared binary64 geometry are distinct; all physical, native
cache and loop gates remain closed.
"""

import hashlib
import math
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass, replace
from fractions import Fraction
from pathlib import Path

from cells.processes import conservative_polygon_geometry as polygons
from cells.processes import stable_geometry_primitives as arithmetic
from cells.processes import stable_mesh_physical_reconstruction as topology

LAW_ID = "cells_fixed_seed_explicit_domain_voronoi_control_volumes@1"
INPUT_KIND = "cells.stable_seed_control_volume_declaration@1"
SOURCE_PINS = (
    (
        "conservative_polygon_geometry",
        "5d267b20cdb3a05f4f036bbc3fa6978b40780ca4394f67ac6c33a8b605af4b0d",
    ),
    (
        "stable_geometry_primitives",
        "c9fab4f34aa9166711431844f2af72eb6b8fe4873154bfe01dfce3f656326958",
    ),
    (
        "stable_mesh_physical_reconstruction",
        "b0633f93978dba2db684e23ee1e3e348c0f3edde624b3069c57b115e3d7ab582",
    ),
)
MAX_SEEDS = 32
MAX_DOMAIN_VERTICES = 16
MAX_VERTICES = 256
MAX_HALF_EDGES = 512
UNITS = dict(coordinates="m", area="m2", integrated_line_normal="m")
INVALIDATED = (
    "all_source_dual_vertices_cell_rings_and_edge_pairings",
    "source_primal_connectivity_as_a_dual_neighbor_map",
    "all_old_metrics_normals_areas_reference_face_areas_and_inverses",
    "native_gap_boundary_profile_and_membrane_owner_maps",
    "physical_cells_membrane_measures_volumes_and_extrusion",
    "environment_grid_maps_operators_and_bath_policy",
    "native_initialization_and_all_loop_state_bindings",
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
    owners: object
    exact_geometry: object
    stored_geometry: object
    connectivity: object
    moments: object
    conservation: object
    certificates: object
    diagnostics: object
    prerequisites: object
    identity: str


class ControlVolumeRejected(ValueError):
    def __init__(self, reason, *, stage, original=None, partial=None):
        super().__init__("Fixed-seed control volumes refused at " + stage + ": " + str(reason))
        self.stage, self.original, self.partial = stage, original, partial


def plain(value):
    if isinstance(value, Fraction):
        return dict(numerator=str(value.numerator), denominator=str(value.denominator))
    if is_dataclass(value):
        return {field.name: plain(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {key: plain(child) for key, child in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(child) for child in value]
    return value


def digest(value):
    return topology.digest(plain(value))


def _verify_sources():
    for (name, expected), module in zip(SOURCE_PINS, (polygons, arithmetic, topology), strict=True):
        if (
            module.__name__.rsplit(".", 1)[-1] != name
            or hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() != expected
        ):
            raise ValueError("Changed fixed-seed geometry dependency: " + name)


def _binary_point(row):
    if not isinstance(row, (tuple, list)) or len(row) != 2:
        raise ValueError("Require a complete two-coordinate binary64 point")
    if any(type(value) is not float or not math.isfinite(value) for value in row):
        raise ValueError("Coordinates must be supplied finite binary64 values in metres")
    return tuple(Fraction.from_float(value) for value in row)


def _domain(declared):
    required = {
        "kind",
        "opted_in_law",
        "units",
        "domain",
        "seed_policy",
        "connectivity_policy",
        "rounding_policy",
        "physical_status",
    }
    if not isinstance(declared, Mapping) or set(declared) != required:
        raise ValueError("Declare the complete fixed-seed/domain/connectivity law")
    if (
        declared["kind"] != INPUT_KIND
        or declared["opted_in_law"] != LAW_ID
        or declared["units"] != UNITS
        or declared["seed_policy"] != "retain_original_binary64_coordinates_and_owner_ids"
        or declared["connectivity_policy"] != "replace_dual_and_seed_adjacency_explicitly"
        or declared["rounding_policy"]
        != "shared_vertex_once_strict_domain_no_collision_or_seed_loss"
        or declared["physical_status"] != "prospective_geometry_only_no_physical_admission"
    ):
        raise ValueError("Unsupported geometry law, units, seed move or physical promotion")
    domain = declared["domain"]
    if (
        not isinstance(domain, Mapping)
        or set(domain) != {"id", "vertices_m", "provenance", "role"}
        or type(domain["id"]) is not str
        or not domain["id"]
        or domain["role"] != "prospective_partition_envelope_not_native_tissue_boundary"
    ):
        raise ValueError("Supply an explicit finite convex envelope and its geometric role")
    source = domain["provenance"]
    if (
        not isinstance(source, Mapping)
        or set(source)
        != {"kind", "authority", "document_sha256", "field", "native_tissue_equivalence"}
        or source["kind"] != "explicit_caller_polygon@1"
        or any(type(source[key]) is not str or not source[key] for key in ("authority", "field"))
        or type(source["document_sha256"]) is not str
        or len(source["document_sha256"]) != 64
        or any(c not in "0123456789abcdef" for c in source["document_sha256"])
        or source["native_tissue_equivalence"] is not False
    ):
        raise ValueError("No default domain: record caller authority and original document/field")
    points = domain["vertices_m"]
    if not isinstance(points, (tuple, list)) or not 3 <= len(points) <= MAX_DOMAIN_VERTICES:
        raise ValueError("Outside the bounded explicit domain vertex axis")
    exact = tuple(_binary_point(row) for row in points)
    if len(set(exact)) != len(exact):
        raise ValueError("Repeated domain vertex")
    if any(
        polygons._orient(exact[i - 1], exact[i], exact[(i + 1) % len(exact)]) <= 0
        for i in range(len(exact))
    ):
        raise ValueError("Require a strictly convex CCW caller domain, without collinear corners")
    polygons._complex(
        dict(enumerate(exact)),
        [dict(id="declared-domain", vertex_ids=list(range(len(exact))))],
        stage="declared_domain",
    )
    return exact


def request_record(value):
    return (LAW_ID, value.topology_request, value.topology_candidate, value.declaration)


def bind(parent, corrected, declaration):
    _verify_sources()
    if type(parent) is not topology.Request or type(corrected) is not topology.Candidate:
        raise ValueError("Require complete retained topology02 request/candidate")
    if digest(topology.reconstruct(parent)) != digest(corrected):
        raise ValueError("Changed retained seeds, owners or source topology")
    if not 1 <= len(parent.retained_point_ids) <= MAX_SEEDS:
        raise ValueError("Outside the bounded fixed-seed owner axis")
    domain = _domain(declaration)
    seeds = tuple(_binary_point(row) for row in corrected.geometry["tri_verts"])
    if len(set(seeds)) != len(seeds):
        raise ValueError("Coincident seed owners are ambiguous; no coalescing or perturbation")
    if any(polygons._inside(seed, domain) != 1 for seed in seeds):
        raise ValueError("Every retained seed must lie strictly inside the explicit domain")
    if any(
        corrected.prerequisites[key] is not False
        for key in (
            "physical_geometry_admitted",
            "native_mesh_qualified",
            "ordinary_ECM_loop_ready",
        )
    ):
        raise ValueError("Parent qualification may not silently promote the new geometry")
    result = Request(parent, corrected, topology.freeze(plain(declaration)), "")
    return replace(result, identity=digest(request_record(result)))


class _Work:
    def __init__(self, observer=None):
        self.clips, self.scalars, self.partial = [], [], {}
        self.observer = observer

    def emit(self, stage, value):
        if self.observer is not None:
            self.observer(stage, plain(value))

    def round(self, target, field, owner, axis):
        event = dict(
            sequence=len(self.scalars), field=field, owner=owner, axis=axis, input_exact=target
        )
        self.scalars.append(event)
        self.emit("scalar_input", event)
        try:
            value = arithmetic._round(target, "fixed_seed_" + field)
        except Exception as error:
            event["failure"] = dict(
                type=type(error).__name__,
                reason=str(error),
                detail=getattr(error, "detail", None),
                trial=getattr(error, "trial", None),
            )
            self.emit("scalar_failure", event)
            raise
        event["returned"] = dict(value=value, binary64_hex=value.hex(), exact_target=target)
        self.emit("scalar_return", event)
        return value


def _canonical_polygon(points):
    row = []
    for point in points:
        if not row or row[-1] != point:
            row.append(point)
    if len(row) > 1 and row[0] == row[-1]:
        row.pop()
    changed = True
    while changed and len(row) >= 3:
        changed = False
        for i in range(len(row)):
            if polygons._on(row[i - 1], row[(i + 1) % len(row)], row[i]):
                row.pop(i)
                changed = True
                break
    if len(row) < 3:
        raise ValueError("Exact cell became lower-dimensional; no area regularization")
    first = min(range(len(row)), key=row.__getitem__)
    return tuple(row[first:] + row[:first])


def _bisector(seed, other):
    return (
        other[0] - seed[0],
        other[1] - seed[1],
        (other[0] ** 2 + other[1] ** 2 - seed[0] ** 2 - seed[1] ** 2) / 2,
    )


def _residual(plane, point):
    a, b, c = plane
    return c - a * point[0] - b * point[1]


def _clip(ring, plane, work, owner, other):
    event = dict(
        sequence=len(work.clips),
        owner=owner,
        other=other,
        plane=plane,
        before=ring,
    )
    work.clips.append(event)
    work.emit("clip_input", event)
    output = []
    try:
        values = tuple(_residual(plane, point) for point in ring)
        event["input_residuals"] = values
        work.emit("clip_residuals", event)
        for i, end in enumerate(ring):
            start = ring[i - 1]
            left, right = values[i - 1], values[i]
            if (left >= 0) != (right >= 0):
                parameter = left / (left - right)
                output.append(
                    tuple(a + parameter * (b - a) for a, b in zip(start, end, strict=True))
                )
            if right >= 0:
                output.append(end)
        result = _canonical_polygon(output)
        event["after"] = result
        work.emit("clip_return", event)
        return result
    except Exception as error:
        event["failure"] = dict(
            type=type(error).__name__, reason=str(error), partial_vertices=output
        )
        work.emit("clip_failure", event)
        raise


def exact_partition(seeds, domain, work):
    """Successive exact half-plane clipping; no source dual coordinate is reused."""
    cells = []
    work.partial.update(source_seeds=seeds, explicit_domain=domain, unfinished_cells=cells)
    for owner, seed in enumerate(seeds):
        ring = _canonical_polygon(domain)
        for other, point in enumerate(seeds):
            if other != owner:
                incoming = dict(owner=owner, other=other, seed=seed, competitor=point)
                work.partial["current_bisector_input"] = incoming
                work.emit("bisector_input", incoming)
                ring = _clip(ring, _bisector(seed, point), work, owner, other)
        cells.append(ring)
    vertices = sorted({point for row in cells for point in row})
    if len(vertices) > MAX_VERTICES:
        raise ValueError("Complete shared vertex axis exceeds its declared bound")
    rings = []
    for row in cells:
        split = []
        for i, end in enumerate(row):
            start = row[i - 1]
            axis = 0 if end[0] != start[0] else 1
            on_edge = [point for point in vertices if polygons._on(start, end, point)]
            on_edge.sort(key=lambda point: (point[axis] - start[axis]) / (end[axis] - start[axis]))
            split.extend(on_edge[:-1])
        indices = [vertices.index(point) for point in split]
        first = indices.index(min(indices))
        rings.append(tuple(indices[first:] + indices[:first]))
    if sum(map(len, rings)) > MAX_HALF_EDGES:
        raise ValueError("Complete cell occurrence axis exceeds its declared bound")
    return tuple(vertices), tuple(rings)


def admit_complex(vertices, rings, seeds, domain, *, stage):
    """Use the pinned conservative admission on the actual supplied coordinates."""
    if len(set(vertices)) != len(vertices):
        raise ValueError("Distinct exact vertices collided in the shared coordinate store")
    rows = [dict(id=str(owner), vertex_ids=list(row)) for owner, row in enumerate(rings)]
    incidence, total = polygons._complex(dict(enumerate(vertices)), rows, stage=stage)
    moments = []
    for owner, row in enumerate(rings):
        polygon = [vertices[i] for i in row]
        if any(
            polygons._orient(polygon[i - 1], polygon[i], polygon[(i + 1) % len(row)]) < 0
            for i in range(len(row))
        ):
            raise ValueError("The shared geometry lost convex cell orientation")
        if polygons._inside(seeds[owner], polygon) != 1:
            raise ValueError("A retained seed is not strictly inside its reconstructed cell")
        moments.append(polygons._moments(polygon))
    for point in vertices:
        if any(polygons._orient(domain[i - 1], domain[i], point) < 0 for i in range(len(domain))):
            raise ValueError("A reconstructed vertex left the explicitly declared domain")
    domain_area, domain_centroid = polygons._moments(domain)
    if total != domain_area:
        raise ValueError(
            "The nonoverlapping complex does not exactly cover the declared domain area"
        )
    boundary, intervals = [], [[] for _ in domain]
    for edge, owners in sorted(incidence.items()):
        if len(owners) != 1:
            continue
        owner, a, b = owners[0]
        matches = [
            i
            for i in range(len(domain))
            if polygons._on(domain[i - 1], domain[i], vertices[a])
            and polygons._on(domain[i - 1], domain[i], vertices[b])
        ]
        if len(matches) != 1:
            raise ValueError(
                "A rounded/new boundary segment left its original declared domain edge"
            )
        index = matches[0]
        start, end = domain[index - 1], domain[index]
        axis = 0 if start[0] != end[0] else 1
        lo, hi = ((vertices[v][axis] - start[axis]) / (end[axis] - start[axis]) for v in (a, b))
        if not 0 <= lo < hi <= 1:
            raise ValueError("Boundary segment orientation or domain parameter changed")
        intervals[index].append((lo, hi))
        boundary.append(
            dict(edge=edge, owner=owner, directed=(a, b), domain_edge=index, interval=(lo, hi))
        )
    for row in intervals:
        row.sort()
        previous = Fraction(0)
        for lo, hi in row:
            if lo != previous:
                raise ValueError("Gap or repeated coverage along a declared domain edge")
            previous = hi
        if previous != 1:
            raise ValueError("Incomplete declared domain-edge coverage")
    return incidence, tuple(moments), domain_area, domain_centroid, tuple(boundary)


def build_connectivity(vertices, rings, incidence, source_edges):
    edges = sorted(incidence)
    n, v = len(rings), len(vertices)
    d0 = [[int(j == b) - int(j == a) for j in range(v)] for a, b in edges]
    d1 = [[0] * len(edges) for _ in rings]
    occurrences, partners, owner_groups = [], [], [[] for _ in edges]
    cell_occurrences = []
    for owner, ring in enumerate(rings):
        row = []
        for local, b in enumerate(ring):
            a = ring[local - 1]
            edge = edges.index(tuple(sorted((a, b))))
            sign = 1 if (a, b) == edges[edge] else -1
            d1[owner][edge] = sign
            index = len(occurrences)
            row.append(index)
            owner_groups[edge].append(index)
            occurrences.append(
                dict(owner=owner, local_edge=local, edge=edge, directed=(a, b), sign=sign)
            )
        cell_occurrences.append(row)
    new_neighbors = set()
    for index, row in enumerate(occurrences):
        group = owner_groups[row["edge"]]
        partners.append(next((other for other in group if other != index), None))
    for group in owner_groups:
        if len(group) == 2:
            new_neighbors.add(tuple(sorted(occurrences[index]["owner"] for index in group)))
    source_neighbors = {tuple(sorted(pair)) for pair in source_edges}
    chain = [
        [sum(d1[i][edge] * d0[edge][j] for edge in range(len(edges))) for j in range(v)]
        for i in range(n)
    ]
    if any(value != 0 for row in chain for value in row):
        raise ValueError("New cell boundary-of-boundary does not vanish")
    return dict(
        vertices=tuple("cv-v" + str(i) for i in range(v)),
        edges=edges,
        delta_0=d0,
        delta_1=d1,
        cell_occurrences=cell_occurrences,
        occurrences=occurrences,
        partners=partners,
        edge_occurrences=owner_groups,
        boundary_edges=[i for i, group in enumerate(owner_groups) if len(group) == 1],
        new_seed_adjacency=sorted(new_neighbors),
        source_seed_adjacency=sorted(source_neighbors),
        added_seed_pairs=sorted(new_neighbors - source_neighbors),
        removed_seed_pairs=sorted(source_neighbors - new_neighbors),
        seed_adjacency_is_native_primal_triangulation_claimed=False,
        original_primal_and_dual_cache_axes_reused=False,
        local_edge_convention="previous_vertex_to_current_vertex",
        boundary_partner_policy=None,
        boundary_of_boundary=chain,
    )


def conservation(vertices, rings, moments, connectivity, domain_area, area_readouts):
    cell_results, edge_normals = [], [[] for _ in connectivity["edges"]]
    for owner, ring in enumerate(rings):
        closure = [Fraction(0), Fraction(0)]
        affine = [[Fraction(0), Fraction(0)] for _ in range(2)]
        normals = []
        for local, b in enumerate(ring):
            a = ring[local - 1]
            start, end = vertices[a], vertices[b]
            normal = (end[1] - start[1], start[0] - end[0])
            midpoint = tuple((x + y) / 2 for x, y in zip(start, end, strict=True))
            occurrence = connectivity["occurrences"][connectivity["cell_occurrences"][owner][local]]
            edge_normals[occurrence["edge"]].append((owner, normal))
            normals.append(normal)
            for j in range(2):
                closure[j] += normal[j]
                for k in range(2):
                    affine[k][j] += midpoint[k] * normal[j]
        area = moments[owner][0]
        defect = [[affine[k][j] - (area if k == j else 0) for j in range(2)] for k in range(2)]
        if any(closure) or any(value for row in defect for value in row):
            raise ValueError("Constant/affine flux closure or exact area conservation failed")
        cell_results.append(
            dict(
                integrated_line_normals_xy_m=normals,
                constant_flux_closure=closure,
                affine_flux_moments_m2=affine,
                affine_area_defect_m2=defect,
            )
        )
    internal = []
    for edge, row in enumerate(edge_normals):
        if len(row) == 2:
            residual = tuple(row[0][1][axis] + row[1][1][axis] for axis in range(2))
            if any(residual):
                raise ValueError("Opposite shared-edge fluxes failed exact cancellation")
            internal.append(dict(edge=edge, owners=[item[0] for item in row], residual=residual))
    return dict(
        cells=cell_results,
        internal_edge_cancellation=internal,
        exact_stored_geometry_area_sum=sum((row[0] for row in moments), Fraction(0)),
        declared_domain_area_exact=domain_area,
        stored_geometry_domain_area_defect=sum((row[0] for row in moments), Fraction(0))
        - domain_area,
        rounded_area_readout_sum_defect=sum(
            (Fraction.from_float(x) for x in area_readouts), Fraction(0)
        )
        - domain_area,
        binary64_area_readouts_sum_exactly_claimed=False,
        unit_normals_physical_membranes_and_height_used=False,
    )


def candidate_record(value):
    return (
        LAW_ID,
        value.request_identity,
        value.owners,
        value.exact_geometry,
        value.stored_geometry,
        value.connectivity,
        value.moments,
        value.conservation,
        value.certificates,
        value.diagnostics,
        value.prerequisites,
    )


def prepare(request, *, observer=None):
    work, stage = _Work(observer), "request"
    try:
        if type(request) is not Request or request.identity != digest(request_record(request)):
            raise ValueError("Changed or unsealed fixed-seed request")
        rebuilt = bind(request.topology_request, request.topology_candidate, request.declaration)
        if digest(request_record(rebuilt)) != digest(request_record(request)):
            raise ValueError("Resealed source/domain differs from the complete declaration")
        polygons._platform()
        original = request.topology_candidate.geometry["tri_verts"]
        seeds = tuple(_binary_point(row) for row in original)
        domain = _domain(request.declaration)
        stage = "exact_halfplane_partition"
        vertices, rings = exact_partition(seeds, domain, work)
        work.partial.update(exact_vertices=vertices, reconstructed_cells=rings)
        work.emit(stage, work.partial)
        stage = "exact_complex_admission"
        exact_incidence, ideal, domain_area, domain_centroid, exact_boundary = admit_complex(
            vertices, rings, seeds, domain, stage=stage
        )
        connectivity = build_connectivity(
            vertices, rings, exact_incidence, request.topology_candidate.primal["edges"]
        )
        work.partial.update(
            ideal_moments=ideal, exact_boundary=exact_boundary, connectivity=connectivity
        )
        stage = "shared_binary64_coordinates"
        stored_vertices = []
        work.partial["stored_vertices"] = stored_vertices
        for owner, point in enumerate(vertices):
            row = []
            stored_vertices.append(row)
            for axis, target in enumerate(point):
                row.append(work.round(target, "shared_vertex_coordinate_m", owner, axis))
        stored_exact = tuple(_binary_point(row) for row in stored_vertices)
        stage = "stored_complex_admission"
        work.emit(
            stage + "_input", dict(vertices=stored_exact, cells=rings, seeds=seeds, domain=domain)
        )
        incidence, actual, actual_domain, _, stored_boundary = admit_complex(
            stored_exact, rings, seeds, domain, stage=stage
        )
        if incidence != exact_incidence or actual_domain != domain_area:
            raise ValueError("Rounding changed shared-edge ownership or declared domain")
        work.partial.update(stored_geometry_moments=actual, stored_boundary=stored_boundary)
        stage = "stored_geometry_moment_readouts"
        areas, centroids = [], []
        work.partial.update(area_readouts=areas, centroid_readouts=centroids)
        for owner, (area, centroid) in enumerate(actual):
            areas.append(work.round(area, "stored_geometry_area_m2", owner, 0))
            centroids.append(
                [
                    work.round(target, "stored_geometry_centroid_m", owner, axis)
                    for axis, target in enumerate(centroid)
                ]
            )
        domain_readout = work.round(domain_area, "declared_domain_area_m2", 0, 0)
        stage = "finite_volume_conservation"
        conserved = conservation(stored_exact, rings, actual, connectivity, domain_area, areas)
        bisector_residuals = []
        for owner, row in enumerate(rings):
            bisector_residuals.append(
                [
                    [
                        dict(
                            other=other,
                            exact_target=_residual(_bisector(seeds[owner], point), vertices[index]),
                            actual_stored=_residual(
                                _bisector(seeds[owner], point), stored_exact[index]
                            ),
                        )
                        for other, point in enumerate(seeds)
                        if other != owner
                    ]
                    for index in row
                ]
            )
        result = Candidate(
            request.identity,
            topology.freeze(
                dict(
                    retained_point_ids=request.topology_request.retained_point_ids,
                    seed_points_binary64_hex=[[x.hex() for x in row] for row in original],
                    source_request_identity=request.topology_request.identity,
                    source_topology_identity=request.topology_candidate.identity,
                )
            ),
            topology.freeze(
                plain(dict(vertices_m=vertices, cells=rings, domain_vertices_m=domain))
            ),
            topology.freeze(
                dict(
                    vertices_m=stored_vertices,
                    cells=rings,
                    area_m2=areas,
                    centroid_m=centroids,
                    domain_area_m2=domain_readout,
                )
            ),
            topology.freeze(plain(connectivity)),
            topology.freeze(
                plain(
                    dict(
                        ideal_voronoi=ideal,
                        actual_shared_binary64_geometry=actual,
                        declared_domain=(domain_area, domain_centroid),
                    )
                )
            ),
            topology.freeze(plain(conserved)),
            topology.freeze(plain(dict(clip_events=work.clips, arithmetic_events=work.scalars))),
            topology.freeze(
                plain(
                    dict(
                        exact_boundary_domain_coverage=exact_boundary,
                        stored_boundary_domain_coverage=stored_boundary,
                        stored_bisector_residuals=bisector_residuals,
                        stored_geometry_is_exact_nearest_seed_partition_claimed=False,
                        input_seed_coordinates_or_ids_changed=False,
                        native_equivalence_claimed=False,
                        exact_voronoi_targets_distinct_from_stored_geometry=True,
                        original_source_dual_vertices_or_rings_reused=False,
                        ideal_to_stored_area_defects=[
                            b[0] - a[0] for a, b in zip(ideal, actual, strict=True)
                        ],
                    )
                )
            ),
            topology.freeze(
                dict(
                    independent_construction_and_geometry_checks_required=True,
                    physical_geometry_admitted=False,
                    native_mesh_cache_admitted=False,
                    inverse_operators_qualified=False,
                    environment_binding_admitted=False,
                    ordinary_ECM_loop_ready=False,
                    domain_is_native_tissue_boundary_claimed=False,
                    boundary_bath_or_flux_policy=None,
                    physical_parameters=None,
                    invalidated=INVALIDATED,
                )
            ),
            "",
        )
        work.emit("candidate_before_seal", plain(result))
        return replace(result, identity=digest(candidate_record(result)))
    except Exception as error:
        raise ControlVolumeRejected(
            error,
            stage=stage,
            original=request,
            partial=topology.freeze(
                plain(
                    dict(
                        completed=work.partial,
                        clip_events=work.clips,
                        arithmetic_events=work.scalars,
                        source_error=dict(
                            type=type(error).__name__,
                            reason=str(error),
                            detail=getattr(error, "detail", None),
                            trial=getattr(error, "trial", None),
                        ),
                    )
                )
            ),
        ) from error


def require_physical_admission(candidate):
    raise ControlVolumeRejected(
        "New mathematical control volumes do not qualify physical/native/loop bindings",
        stage="physical_admission",
        original=candidate,
    )
