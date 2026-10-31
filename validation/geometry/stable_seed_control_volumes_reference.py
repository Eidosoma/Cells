"""Independent constraint-intersection construction and saved candidate checks.

No production geometry or clipping kernel is imported. Inputs choose all exact
targets and independent binary64 projections before any outgoing value is read.
"""

import argparse
import hashlib
import importlib.abc
import json
import math
import os
import sys
import traceback
from decimal import Decimal, localcontext
from fractions import Fraction
from functools import cmp_to_key
from pathlib import Path

DENIED = {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "PIL", "torch"}


class DenyScience(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in DENIED:
            raise ImportError("Independent control-volume reference denies: " + fullname)


sys.meta_path.insert(0, DenyScience())
if DENIED & {name.split(".")[0] for name in sys.modules}:
    raise ImportError("Production/scientific module already loaded in independent reference")

from validation.geometry import (  # noqa: E402
    stable_geometry_primitives_reference as primitive_reference,
)

LAW = "cells_fixed_seed_explicit_domain_voronoi_control_volumes@1"
TOPOLOGY_LAW = "cells_stable_mesh_incidence_physical_reconstruction_candidate@1"
INVALIDATED = [
    "all_source_dual_vertices_cell_rings_and_edge_pairings",
    "source_primal_connectivity_as_a_dual_neighbor_map",
    "all_old_metrics_normals_areas_reference_face_areas_and_inverses",
    "native_gap_boundary_profile_and_membrane_owner_maps",
    "physical_cells_membrane_measures_volumes_and_extrusion",
    "environment_grid_maps_operators_and_bath_policy",
    "native_initialization_and_all_loop_state_bindings",
]


def pack(value):
    if isinstance(value, Fraction):
        return dict(numerator=str(value.numerator), denominator=str(value.denominator))
    if isinstance(value, dict):
        return {key: pack(child) for key, child in value.items()}
    if isinstance(value, (tuple, list)):
        return [pack(child) for child in value]
    return value


def record(value):
    if type(value) is float:
        return dict(binary64_hex=value.hex())
    if isinstance(value, dict):
        return {str(key): record(child) for key, child in value.items()}
    if isinstance(value, (tuple, list)):
        return [record(child) for child in value]
    return value


def digest(value):
    return hashlib.sha256(
        json.dumps(
            record(pack(value)), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def typed_equal(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            typed_equal(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            typed_equal(a, b) for a, b in zip(actual, expected, strict=True)
        )
    if type(expected) is float:
        return actual.hex() == expected.hex()
    return actual == expected


def point(row):
    if (
        type(row) is not list
        or len(row) != 2
        or any(type(x) is not float or not math.isfinite(x) for x in row)
    ):
        raise ValueError("Independent complete finite binary64 coordinate pair required")
    return tuple(Fraction.from_float(x) for x in row)


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def turn(a, b, c):
    return cross((b[0] - a[0], b[1] - a[1]), (c[0] - a[0], c[1] - a[1]))


def hull(points):
    """Andrew hull, unlike the production polygon-clipping construction."""
    points = sorted(set(points))
    chains = []
    for sequence in (points, list(reversed(points))):
        row = []
        for value in sequence:
            while len(row) >= 2 and turn(row[-2], row[-1], value) <= 0:
                row.pop()
            row.append(value)
        chains.append(row)
    result = chains[0][:-1] + chains[1][:-1]
    if len(result) < 3:
        raise ValueError("Independent feasible cell has no positive two-dimensional interior")
    return tuple(result)


def edge_plane(a, b):
    normal = (b[1] - a[1], a[0] - b[0])
    return (normal[0], normal[1], normal[0] * a[0] + normal[1] * a[1])


def site_plane(a, b):
    # Twice the production normalization; exact feasibility is identical.
    return (
        2 * (b[0] - a[0]),
        2 * (b[1] - a[1]),
        b[0] * b[0] + b[1] * b[1] - a[0] * a[0] - a[1] * a[1],
    )


def slack(line, p):
    return line[2] - line[0] * p[0] - line[1] * p[1]


def intersection(first, second):
    determinant = first[0] * second[1] - first[1] * second[0]
    if not determinant:
        return None
    return (
        (first[2] * second[1] - first[1] * second[2]) / determinant,
        (first[0] * second[2] - first[2] * second[0]) / determinant,
    )


def moments(poly):
    twice = Fraction(0)
    numerator = [Fraction(0), Fraction(0)]
    for i, b in enumerate(poly):
        a = poly[i - 1]
        coefficient = cross(a, b)
        twice += coefficient
        for axis in range(2):
            numerator[axis] += (a[axis] + b[axis]) * coefficient
    if twice <= 0:
        raise ValueError("Independent nonpositive/orientation area")
    return twice / 2, tuple(x / (3 * twice) for x in numerator)


def project(value):
    with localcontext() as context:
        context.prec = 4096
        approximation = Decimal(value.numerator) / Decimal(value.denominator)
        output = primitive_reference._rounded_ratio(pack(value), approximation)
    if output is None:
        raise ValueError("Independent rational coordinate/metric is unrepresentable in binary64")
    return float.fromhex(output)


def authenticate(request):
    if type(request) is not dict or set(request) != {
        "topology_request",
        "topology_candidate",
        "declaration",
        "identity",
    }:
        raise ValueError("Incomplete original constructor request")
    parent, supplied, declared = (
        request["topology_request"],
        request["topology_candidate"],
        request["declaration"],
    )
    if set(parent) != {"evidence", "original_cache", "retained_point_ids", "identity"}:
        raise ValueError("Incomplete/extra original source parent fields")
    if parent["identity"] != digest(
        (TOPOLOGY_LAW, parent["evidence"], parent["original_cache"], parent["retained_point_ids"])
    ):
        raise ValueError("Changed source parent request seal")
    names = (
        "request_identity",
        "geometry",
        "primal",
        "dual",
        "physical_owner_plan",
        "differences",
        "prerequisites",
    )
    if set(supplied) != set(names) | {"identity"}:
        raise ValueError("Incomplete/extra retained source topology fields")
    if supplied["request_identity"] != parent["identity"] or supplied["identity"] != digest(
        [TOPOLOGY_LAW] + [supplied[key] for key in names]
    ):
        raise ValueError("Changed supplied retained topology seal")
    if request["identity"] != digest((LAW, parent, supplied, declared)):
        raise ValueError("Changed complete fixed-seed request")
    if any(
        not typed_equal(supplied["geometry"][key], parent["original_cache"][key])
        for key in ("tri_verts", "tri_cells", "vor_verts", "vor_cells")
    ):
        raise ValueError("Retained source geometry changed")
    if not typed_equal(supplied["primal"]["edges"], parent["original_cache"]["tri_edges"]):
        raise ValueError("Original source seed-edge descriptor changed")
    ids = parent["retained_point_ids"]
    seeds = tuple(point(row) for row in parent["original_cache"]["tri_verts"])
    if (
        not 1 <= len(seeds) <= 32
        or len(set(seeds)) != len(seeds)
        or type(ids) is not list
        or len(ids) != len(seeds)
        or len(set(ids)) != len(ids)
        or any(type(x) is not str or not x for x in ids)
    ):
        raise ValueError("Ambiguous complete fixed-seed owner axis")
    if set(declared) != {
        "kind",
        "opted_in_law",
        "units",
        "domain",
        "seed_policy",
        "connectivity_policy",
        "rounding_policy",
        "physical_status",
    }:
        raise ValueError("Complete explicit declaration fields required")
    expected = dict(
        kind="cells.stable_seed_control_volume_declaration@1",
        opted_in_law=LAW,
        units=dict(coordinates="m", area="m2", integrated_line_normal="m"),
        seed_policy="retain_original_binary64_coordinates_and_owner_ids",
        connectivity_policy="replace_dual_and_seed_adjacency_explicitly",
        rounding_policy="shared_vertex_once_strict_domain_no_collision_or_seed_loss",
        physical_status="prospective_geometry_only_no_physical_admission",
    )
    if any(not typed_equal(declared[key], value) for key, value in expected.items()):
        raise ValueError("Unsupported independent geometry law, units or admission")
    raw = declared["domain"]
    if (
        set(raw) != {"id", "vertices_m", "provenance", "role"}
        or type(raw["id"]) is not str
        or not raw["id"]
        or raw["role"] != "prospective_partition_envelope_not_native_tissue_boundary"
    ):
        raise ValueError("Explicit caller domain role required")
    source = raw["provenance"]
    if (
        set(source)
        != {"kind", "authority", "document_sha256", "field", "native_tissue_equivalence"}
        or source["kind"] != "explicit_caller_polygon@1"
        or source["native_tissue_equivalence"] is not False
        or any(type(source[key]) is not str or not source[key] for key in ("authority", "field"))
        or type(source["document_sha256"]) is not str
        or len(source["document_sha256"]) != 64
        or any(c not in "0123456789abcdef" for c in source["document_sha256"])
    ):
        raise ValueError("Independent domain provenance is incomplete")
    domain = tuple(point(row) for row in raw["vertices_m"])
    if not 3 <= len(domain) <= 16 or len(set(domain)) != len(domain):
        raise ValueError("Independent finite domain owner axis required")
    first = min(range(len(domain)), key=domain.__getitem__)
    if tuple(domain[first:] + domain[:first]) != hull(domain) or any(
        turn(domain[i - 1], domain[i], domain[(i + 1) % len(domain)]) <= 0
        for i in range(len(domain))
    ):
        raise ValueError("Require strict convex CCW input domain")
    if any(turn(domain[i - 1], domain[i], p) <= 0 for p in seeds for i in range(len(domain))):
        raise ValueError("Independent seed must be strictly inside the declared domain")
    if any(
        supplied["prerequisites"][key] is not False
        for key in (
            "physical_geometry_admitted",
            "native_mesh_qualified",
            "ordinary_ECM_loop_ready",
        )
    ):
        raise ValueError("Parent may not promote qualification")
    return seeds, domain, ids


def independent_partition(seeds, domain, partial):
    domain_lines = [edge_plane(domain[i - 1], point) for i, point in enumerate(domain)]
    candidates, all_lines = [], []
    journal = []
    partial["constraint_intersection_construction"] = journal
    for owner, seed in enumerate(seeds):
        lines = domain_lines + [
            site_plane(seed, p) for other, p in enumerate(seeds) if other != owner
        ]
        entry = dict(owner=owner, constraints=lines, pairs=[])
        journal.append(entry)
        feasible = set()
        for left in range(len(lines)):
            for right in range(left + 1, len(lines)):
                trial = dict(left=left, right=right)
                entry["pairs"].append(trial)
                value = intersection(lines[left], lines[right])
                trial["intersection"] = value
                if value is None:
                    trial["status"] = "parallel"
                    continue
                violated = next((i for i, line in enumerate(lines) if slack(line, value) < 0), None)
                trial["first_violated_constraint"] = violated
                trial["status"] = "outside" if violated is not None else "feasible"
                if violated is None:
                    feasible.add(value)
        candidates.append(hull(feasible))
        all_lines.append(lines)
    vertices = sorted({point for row in candidates for point in row})
    if len(vertices) > 256:
        raise ValueError("Independent global vertex bound exceeded")
    rings = []
    for owner, lines in enumerate(all_lines):
        selected = [
            i
            for i, value in enumerate(vertices)
            if all(slack(line, value) >= 0 for line in lines)
            and any(slack(line, value) == 0 for line in lines)
        ]
        seed = seeds[owner]

        def compare(left, right, seed=seed):
            if left == right:
                return 0
            a = (vertices[left][0] - seed[0], vertices[left][1] - seed[1])
            b = (vertices[right][0] - seed[0], vertices[right][1] - seed[1])
            ah = int(a[1] < 0 or a[1] == 0 and a[0] < 0)
            bh = int(b[1] < 0 or b[1] == 0 and b[0] < 0)
            if ah != bh:
                return ah - bh
            orientation = cross(a, b)
            if not orientation:
                raise ValueError("Independent distinct boundary points share a seed ray")
            return -1 if orientation > 0 else 1

        selected.sort(key=cmp_to_key(compare))
        first = selected.index(min(selected))
        rings.append(tuple(selected[first:] + selected[:first]))
    if sum(map(len, rings)) > 512:
        raise ValueError("Independent complete occurrence bound exceeded")
    return tuple(vertices), tuple(rings)


def on_segment(a, b, value):
    return turn(a, b, value) == 0 and all(
        min(x, y) <= z <= max(x, y) for x, y, z in zip(a, b, value, strict=True)
    )


def admit(vertices, rings, seeds, domain):
    """Convex separating axes, global segment owners and domain interval cover."""
    if len(set(vertices)) != len(vertices):
        raise ValueError("Independent rounded shared vertices collided")
    owner_edges, metrics = {}, []
    polygons = [[vertices[index] for index in ring] for ring in rings]
    for owner, poly in enumerate(polygons):
        if len(poly) < 3 or len(set(rings[owner])) != len(poly):
            raise ValueError("Independent simple nonempty cell axis required")
        metrics.append(moments(poly))
        for local, b in enumerate(rings[owner]):
            a = rings[owner][local - 1]
            if any(turn(vertices[a], vertices[b], p) < 0 for p in poly):
                raise ValueError("Independent shared geometry lost CCW convexity")
            if turn(vertices[a], vertices[b], seeds[owner]) <= 0:
                raise ValueError("Independent strict seed containment failed")
            owner_edges.setdefault(tuple(sorted((a, b))), []).append((owner, a, b))
    for left, poly in enumerate(polygons):
        for other in polygons[left + 1 :]:
            separated = False
            for shape in (poly, other):
                for i, b in enumerate(shape):
                    a = shape[i - 1]
                    axis = (b[1] - a[1], a[0] - b[0])
                    first = [axis[0] * p[0] + axis[1] * p[1] for p in poly]
                    second = [axis[0] * p[0] + axis[1] * p[1] for p in other]
                    if max(first) <= min(second) or max(second) <= min(first):
                        separated = True
                        break
                if separated:
                    break
            if not separated:
                raise ValueError("Independent convex-cell interior overlap")
    for (a, b), owners in owner_edges.items():
        if (
            len(owners) not in (1, 2)
            or len(owners) == 2
            and owners[0][1:] != tuple(reversed(owners[1][1:]))
        ):
            raise ValueError("Independent shared edge lacks exact opposite ownership")
        if any(
            index not in (a, b) and on_segment(vertices[a], vertices[b], value)
            for index, value in enumerate(vertices)
        ):
            raise ValueError("Independent nonconforming vertex inside an unsplit edge")
    if any(turn(domain[i - 1], domain[i], p) < 0 for p in vertices for i in range(len(domain))):
        raise ValueError("Independent vertex outside declared domain")
    domain_area, domain_centroid = moments(domain)
    if sum((row[0] for row in metrics), Fraction(0)) != domain_area:
        raise ValueError("Independent positive nonoverlapping cell areas leave a domain gap")
    boundary, pieces = [], [[] for _ in domain]
    for edge, owners in sorted(owner_edges.items()):
        if len(owners) != 1:
            continue
        owner, a, b = owners[0]
        matches = [
            i
            for i in range(len(domain))
            if on_segment(domain[i - 1], domain[i], vertices[a])
            and on_segment(domain[i - 1], domain[i], vertices[b])
        ]
        if len(matches) != 1:
            raise ValueError("Independent boundary left its declared domain segment")
        index = matches[0]
        start, end = domain[index - 1], domain[index]
        axis = 0 if start[0] != end[0] else 1
        lo, hi = ((vertices[p][axis] - start[axis]) / (end[axis] - start[axis]) for p in (a, b))
        if not 0 <= lo < hi <= 1:
            raise ValueError("Independent boundary orientation/extent")
        pieces[index].append((lo, hi))
        boundary.append(
            dict(edge=edge, owner=owner, directed=(a, b), domain_edge=index, interval=(lo, hi))
        )
    for row in pieces:
        end = Fraction(0)
        for lo, hi in sorted(row):
            if lo != end:
                raise ValueError("Independent domain side coverage has a gap or repetition")
            end = hi
        if end != 1:
            raise ValueError("Independent domain side is incomplete")
    return owner_edges, tuple(metrics), domain_area, domain_centroid, tuple(boundary)


def topology_target(vertices, rings, owners, source_edges):
    edges = sorted(owners)
    incidence = [[0] * len(edges) for _ in rings]
    endpoints = [[0] * len(vertices) for _ in edges]
    for edge, (a, b) in enumerate(edges):
        endpoints[edge][a], endpoints[edge][b] = -1, 1
    occurrences, by_cell, by_edge = [], [], [[] for _ in edges]
    for owner, ring in enumerate(rings):
        local_ids = []
        for local in range(len(ring)):
            a, b = ring[local - 1], ring[local]
            edge = edges.index(tuple(sorted((a, b))))
            direction = 1 if (a, b) == edges[edge] else -1
            index = len(occurrences)
            local_ids.append(index)
            by_edge[edge].append(index)
            incidence[owner][edge] = direction
            occurrences.append(
                dict(owner=owner, local_edge=local, edge=edge, directed=(a, b), sign=direction)
            )
        by_cell.append(local_ids)
    neighbors = sorted(
        {tuple(sorted(item[0] for item in row)) for row in owners.values() if len(row) == 2}
    )
    old_neighbors = sorted({tuple(sorted(row)) for row in source_edges})
    partners = []
    for row in occurrences:
        values = by_edge[row["edge"]]
        partners.append(
            next((index for index in values if occurrences[index]["owner"] != row["owner"]), None)
        )
    chain = [
        [
            sum(a * b for a, b in zip(row, [edge[vertex] for edge in endpoints], strict=True))
            for vertex in range(len(vertices))
        ]
        for row in incidence
    ]
    if any(value for row in chain for value in row):
        raise ValueError("Independent chain boundary did not cancel")
    return dict(
        vertices=tuple("cv-v" + str(i) for i in range(len(vertices))),
        edges=edges,
        delta_0=endpoints,
        delta_1=incidence,
        cell_occurrences=by_cell,
        occurrences=occurrences,
        partners=partners,
        edge_occurrences=by_edge,
        boundary_edges=[i for i, row in enumerate(by_edge) if len(row) == 1],
        new_seed_adjacency=neighbors,
        source_seed_adjacency=old_neighbors,
        added_seed_pairs=sorted(set(neighbors) - set(old_neighbors)),
        removed_seed_pairs=sorted(set(old_neighbors) - set(neighbors)),
        seed_adjacency_is_native_primal_triangulation_claimed=False,
        original_primal_and_dual_cache_axes_reused=False,
        local_edge_convention="previous_vertex_to_current_vertex",
        boundary_partner_policy=None,
        boundary_of_boundary=chain,
    )


def flux_target(vertices, rings, metrics, connection, domain_area, area_readouts):
    cells = []
    for owner, ring in enumerate(rings):
        normals = []
        matrix = [[Fraction(0), Fraction(0)] for _ in range(2)]
        for i, end in enumerate(ring):
            p, q = vertices[ring[i - 1]], vertices[end]
            normal = (q[1] - p[1], p[0] - q[0])
            normals.append(normal)
            for axis in range(2):
                for component in range(2):
                    matrix[axis][component] += (p[axis] + q[axis]) * normal[component] / 2
        closure = [sum((row[axis] for row in normals), Fraction(0)) for axis in range(2)]
        defect = [
            [matrix[i][j] - (metrics[owner][0] if i == j else 0) for j in range(2)]
            for i in range(2)
        ]
        if any(closure) or any(x for row in defect for x in row):
            raise ValueError("Independent constant/affine finite-volume flux identities failed")
        cells.append(
            dict(
                integrated_line_normals_xy_m=normals,
                constant_flux_closure=closure,
                affine_flux_moments_m2=matrix,
                affine_area_defect_m2=defect,
            )
        )
    internal = []
    for edge, rows in enumerate(connection["edge_occurrences"]):
        if len(rows) == 2:
            owners = [connection["occurrences"][index]["owner"] for index in rows]
            normals = [
                cells[connection["occurrences"][index]["owner"]]["integrated_line_normals_xy_m"][
                    connection["occurrences"][index]["local_edge"]
                ]
                for index in rows
            ]
            residual = tuple(sum(row[axis] for row in normals) for axis in range(2))
            if any(residual):
                raise ValueError("Independent reciprocal edge flux did not cancel")
            internal.append(dict(edge=edge, owners=owners, residual=residual))
    total = sum((row[0] for row in metrics), Fraction(0))
    return dict(
        cells=cells,
        internal_edge_cancellation=internal,
        exact_stored_geometry_area_sum=total,
        declared_domain_area_exact=domain_area,
        stored_geometry_domain_area_defect=total - domain_area,
        rounded_area_readout_sum_defect=sum(
            (Fraction.from_float(x) for x in area_readouts), Fraction(0)
        )
        - domain_area,
        binary64_area_readouts_sum_exactly_claimed=False,
        unit_normals_physical_membranes_and_height_used=False,
    )


def independent_clip_journal(seeds, domain, final_vertices, final_rings):
    """Check prefix polygons via line intersections plus hull, never clipping traversal."""
    result = []
    for owner, seed in enumerate(seeds):
        current = hull(domain)
        for other, p in enumerate(seeds):
            if owner == other:
                continue
            line = tuple(value / 2 for value in site_plane(seed, p))
            trial = dict(
                sequence=len(result),
                owner=owner,
                other=other,
                plane=line,
                before=current,
                input_residuals=tuple(slack(line, value) for value in current),
            )
            values = [value for value in current if slack(line, value) >= 0]
            for i, end in enumerate(current):
                start = current[i - 1]
                hit = intersection(edge_plane(start, end), line)
                if hit is not None and on_segment(start, end, hit):
                    values.append(hit)
            current = hull(values)
            trial["after"] = current
            result.append(trial)
        if hull(final_vertices[index] for index in final_rings[owner]) != current:
            raise ValueError(
                "Independent full-constraint construction and prefix hull proof disagree"
            )
    if len(result) != len(seeds) * (len(seeds) - 1):
        raise ValueError("Independent complete clip evidence cardinality")
    return result


def derive(request, partial):
    seeds, domain, ids = authenticate(request)
    partial["stage"] = "independent_constraint_intersections"
    vertices, rings = independent_partition(seeds, domain, partial)
    owners, ideal, domain_area, domain_centroid, exact_boundary = admit(
        vertices, rings, seeds, domain
    )
    ledger = []

    def scalar(target, field, owner, axis):
        entry = dict(sequence=len(ledger), field=field, owner=owner, axis=axis, input_exact=target)
        ledger.append(entry)
        value = project(target)
        entry["returned"] = dict(value=value, binary64_hex=value.hex(), exact_target=target)
        return value

    partial["stage"] = "independent_shared_binary64_projection"
    partial["independent_scalar_projections"] = ledger
    stored_vertices = [
        [scalar(value, "shared_vertex_coordinate_m", owner, axis) for axis, value in enumerate(row)]
        for owner, row in enumerate(vertices)
    ]
    stored_exact = tuple(point(row) for row in stored_vertices)
    stored_owners, actual, area_again, _, stored_boundary = admit(
        stored_exact, rings, seeds, domain
    )
    if stored_owners != owners or area_again != domain_area:
        raise ValueError("Independent rounding changed ownership/domain")
    areas, centroids = [], []
    for owner, (area, centre) in enumerate(actual):
        areas.append(scalar(area, "stored_geometry_area_m2", owner, 0))
        centroids.append(
            [
                scalar(value, "stored_geometry_centroid_m", owner, axis)
                for axis, value in enumerate(centre)
            ]
        )
    area_readout = scalar(domain_area, "declared_domain_area_m2", 0, 0)
    connection = topology_target(
        vertices, rings, owners, request["topology_request"]["original_cache"]["tri_edges"]
    )
    conserved = flux_target(stored_exact, rings, actual, connection, domain_area, areas)
    residuals, bounds = [], []
    for owner, ring in enumerate(rings):
        residual_row, bound_row = [], []
        for index in ring:
            residual_point, bound_point = [], []
            errors = [abs(stored_exact[index][axis] - vertices[index][axis]) for axis in range(2)]
            for other, value in enumerate(seeds):
                if other == owner:
                    continue
                line = tuple(x / 2 for x in site_plane(seeds[owner], value))
                before, after = slack(line, vertices[index]), slack(line, stored_exact[index])
                budget = abs(line[0]) * errors[0] + abs(line[1]) * errors[1]
                if before < 0 or abs(after - before) > budget:
                    raise ValueError(
                        "Independent exact cell constraints or projection-error bound failed"
                    )
                residual_point.append(dict(other=other, exact_target=before, actual_stored=after))
                bound_point.append(dict(other=other, error=after - before, budget=budget))
            residual_row.append(residual_point)
            bound_row.append(bound_point)
        residuals.append(residual_row)
        bounds.append(bound_row)
    area_bound = sum(
        (
            abs(Fraction.from_float(value) - row[0])
            for value, row in zip(areas, actual, strict=True)
        ),
        Fraction(0),
    )
    if abs(conserved["rounded_area_readout_sum_defect"]) > area_bound:
        raise ValueError("Independent finite-volume area-storage bound failed")
    clip_events = independent_clip_journal(seeds, domain, vertices, rings)
    if len(ledger) != 2 * len(vertices) + 3 * len(seeds) + 1:
        raise ValueError("Independent complete scalar evidence cardinality")
    result = dict(
        request_identity=request["identity"],
        owners=dict(
            retained_point_ids=ids,
            seed_points_binary64_hex=[
                [x.hex() for x in row]
                for row in request["topology_request"]["original_cache"]["tri_verts"]
            ],
            source_request_identity=request["topology_request"]["identity"],
            source_topology_identity=request["topology_candidate"]["identity"],
        ),
        exact_geometry=dict(vertices_m=vertices, cells=rings, domain_vertices_m=domain),
        stored_geometry=dict(
            vertices_m=stored_vertices,
            cells=rings,
            area_m2=areas,
            centroid_m=centroids,
            domain_area_m2=area_readout,
        ),
        connectivity=connection,
        moments=dict(
            ideal_voronoi=ideal,
            actual_shared_binary64_geometry=actual,
            declared_domain=(domain_area, domain_centroid),
        ),
        conservation=conserved,
        certificates=dict(clip_events=clip_events, arithmetic_events=ledger),
        diagnostics=dict(
            exact_boundary_domain_coverage=exact_boundary,
            stored_boundary_domain_coverage=stored_boundary,
            stored_bisector_residuals=residuals,
            stored_geometry_is_exact_nearest_seed_partition_claimed=False,
            input_seed_coordinates_or_ids_changed=False,
            native_equivalence_claimed=False,
            exact_voronoi_targets_distinct_from_stored_geometry=True,
            original_source_dual_vertices_or_rings_reused=False,
            ideal_to_stored_area_defects=[b[0] - a[0] for a, b in zip(ideal, actual, strict=True)],
        ),
        prerequisites=dict(
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
        ),
    )
    return dict(
        candidate_fields=pack(result),
        independent_storage_bounds=pack(
            dict(
                area_readout_sum_bound=area_bound,
                stored_bisector_errors=bounds,
                basis="independent exact vertices/projections and stored-geometry moments",
                outgoing_selected_tolerance=False,
            )
        ),
        counts=dict(
            seeds=len(seeds),
            domain_vertices=len(domain),
            vertices=len(vertices),
            cells=len(rings),
            edges=len(connection["edges"]),
            cell_occurrences=sum(map(len, rings)),
            clip_events=len(clip_events),
            scalar_events=len(ledger),
        ),
    )


def candidate_record(value):
    return [LAW] + [
        value[key]
        for key in (
            "request_identity",
            "owners",
            "exact_geometry",
            "stored_geometry",
            "connectivity",
            "moments",
            "conservation",
            "certificates",
            "diagnostics",
            "prerequisites",
        )
    ]


def verify(candidate, truth):
    try:
        fields = truth["candidate_fields"]
        if type(candidate) is not dict or set(candidate) != set(fields) | {"identity"}:
            raise ValueError("Incomplete/extra candidate field inventory")
        if candidate["identity"] != digest(candidate_record(candidate)):
            raise ValueError("Changed full candidate seal")
        checked = []
        for name, value in fields.items():
            checked.append(dict(group=name, passed=typed_equal(candidate[name], value)))
            if not checked[-1]["passed"]:
                raise ValueError(
                    "Independent complete source-target/evidence group differs: " + name
                )
        return dict(
            passed=True,
            checks=checked,
            complete_owner_and_evidence_inventory=True,
            independent_construction="constraint intersections/hull; no production imports",
            exact_and_stored_domain_area_and_affine_conservation=True,
            numerical_tolerance_added=False,
            physical_geometry_admitted=False,
        )
    except Exception as error:
        return dict(
            passed=False,
            reason=str(error),
            type=type(error).__name__,
            traceback=traceback.format_exc(),
            numerical_tolerance_added=False,
            physical_geometry_admitted=False,
        )


def evaluate(payload):
    partial = dict(stage="input")
    try:
        truth = derive(payload["request"], partial)
        baseline = verify(payload.get("baseline", payload["candidate"]), truth)
        if not baseline["passed"]:
            return dict(
                status="baseline_failed",
                baseline_passed=False,
                candidate_passed=False,
                control_detected=False,
                baseline=baseline,
                reference=truth,
                raw_partial=partial,
            )
        checked = verify(payload["candidate"], truth) if "baseline" in payload else baseline
        return dict(
            status="complete",
            baseline_passed=True,
            candidate_passed=checked["passed"],
            control_detected="baseline" in payload and not checked["passed"],
            baseline=baseline,
            candidate=checked,
            reference=truth,
            raw_partial=partial,
            physical_geometry_admitted=False,
            native_cache_admitted=False,
        )
    except Exception as error:
        return dict(
            status="reference_failed",
            baseline_passed=False,
            candidate_passed=False,
            control_detected=False,
            type=type(error).__name__,
            reason=str(error),
            traceback=traceback.format_exc(),
            raw_partial=partial,
        )


def runtime_inventory(input_path):
    paths = {
        str(Path(sys.executable).resolve()),
        str(Path(__file__).resolve()),
        str(input_path.resolve()),
    }
    for module in tuple(sys.modules.values()):
        name = getattr(module, "__file__", None)
        if name and Path(name).is_file():
            paths.add(str(Path(name).resolve()))
    mapping_errors = []
    for line in Path("/proc/self/maps").read_text().splitlines():
        parts = line.split(maxsplit=5)
        if len(parts) == 6 and parts[5].startswith("/"):
            path = Path(parts[5])
            if path.is_file():
                paths.add(str(path.resolve()))
            else:
                mapping_errors.append(str(path))
    if len(paths) > 20000:
        raise ValueError("Independent runtime file-inventory bound exceeded")
    files, errors = {}, {}
    for path in sorted(paths):
        try:
            files[path] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        except OSError as error:
            errors[path] = str(error)
    return dict(
        pid=os.getpid(),
        parent_pid=os.getppid(),
        executable=sys.executable,
        source=str(Path(__file__).resolve()),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        input_sha256=hashlib.sha256(input_path.read_bytes()).hexdigest(),
        python=sys.version,
        affinity=sorted(os.sched_getaffinity(0)),
        files=files,
        file_errors=errors,
        mapped_file_errors=mapping_errors,
        production_and_scientific_imports_denied=True,
        production_or_scientific_modules_loaded=sorted(
            name for name in sys.modules if name.split(".")[0] in DENIED
        ),
        threads={
            name: os.environ.get(name)
            for name in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text())
    report = pack(evaluate(payload))
    try:
        runtime = runtime_inventory(args.input)
        report["runtime_origin"] = runtime
        if (
            runtime["file_errors"]
            or runtime["mapped_file_errors"]
            or runtime["production_or_scientific_modules_loaded"]
        ):
            report["runtime_capture_failed"] = True
    except Exception as error:
        report["runtime_capture_failed"] = True
        report["runtime_capture_failure"] = dict(
            type=type(error).__name__, reason=str(error), traceback=traceback.format_exc()
        )
    with args.output.open("x") as stream:
        json.dump(report, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    passed = (
        report["baseline_passed"]
        and not report.get("runtime_capture_failed", False)
        and (report["control_detected"] if "baseline" in payload else report["candidate_passed"])
    )
    if not passed:
        raise SystemExit(2 if report["status"] == "baseline_failed" else 1)


if __name__ == "__main__":
    main()
