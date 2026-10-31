"""Opted-in integer incidence reconstruction on retained mesh geometry.

This changes the directed-only mapping and heuristic dual pairing laws. It
keeps all source vertex coordinates/owner occurrences and exposes full and
primal-selected dual axes separately. Metrics, inverse operators and physical
cell caches are invalidated. No native mesh is mutated or silently promoted.
"""

import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType

LAW_ID = "cells_stable_mesh_incidence_physical_reconstruction_candidate@1"
INPUT_KIND = "cells.stable_mesh_physical_reconstruction_request@1"
SOURCE_REVISION = "5269a714aa2593ed2a6708c4516289977d8ae1a2"
MAX_VERTICES = 64
MAX_FACES = 256
MAX_EDGES = 512
REQUIRED_CACHE = (
    "tri_verts",
    "tri_cells",
    "tri_edges",
    "vor_verts",
    "vor_cells",
    "tcell_to_tedges",
    "tedges_to_tcell",
    "tverts_to_tedges",
    "vor_edges",
    "bflags_tedges",
    "bflags_tverts",
    "bflags_vedges",
    "use_centroids",
)
INVALIDATED = (
    "tcell_to_tedges",
    "tedges_to_tcell",
    "tverts_to_tedges",
    "bflags_tcells",
    "tri_edge_len",
    "tri_mids",
    "tri_tang",
    "vor_edges",
    "vor_edge_i",
    "n_vedges",
    "vor_tang",
    "vor_edge_len",
    "vor_mids",
    "bflags_vedges",
    "bflags_vverts",
    "inner_vvert_i",
    "tri_sa",
    "tri_cents",
    "tri_ccents",
    "tri_rcircs",
    "vor_sa",
    "vor_cents",
    "tri_sa_o",
    "delta_tri_0",
    "delta_tri_0_inv",
    "delta_tri_1",
    "delta_tri_1_inv",
    "delta_vor_0",
    "delta_vor_0_inv",
    "delta_vor_1",
    "delta_vor_1_inv",
    "physical_cell_vertices",
    "physical_cell_centres",
    "membrane_normals_measures",
    "physical_cell_membrane_volumes",
    "gap_partner_boundary_maps",
    "lapGJ",
    "lapGJinv",
    "environment_maps_volumes_inverses",
    "initializer_sigma_ko",
    "all_loop_state_bindings",
)


def freeze(value):
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze(child) for key, child in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(freeze(child) for child in value)
    if value is None or type(value) in (str, bool, int, float):
        return value
    raise ValueError("Require explicit saved numeric/string owners, not live objects")


def record(value):
    if isinstance(value, Mapping):
        return {str(key): record(child) for key, child in value.items()}
    if isinstance(value, (tuple, list)):
        return [record(child) for child in value]
    if type(value) is float:
        return dict(binary64_hex=value.hex())
    return value


def digest(value):
    return hashlib.sha256(
        json.dumps(record(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


@dataclass(frozen=True)
class Request:
    evidence: object
    original_cache: object
    retained_point_ids: tuple
    identity: str


@dataclass(frozen=True)
class Candidate:
    request_identity: str
    geometry: object
    primal: object
    dual: object
    physical_owner_plan: object
    differences: object
    prerequisites: object
    identity: str


class ReconstructionRejected(ValueError):
    def __init__(self, reason, *, stage, original=None, partial=None):
        super().__init__(
            "Physical reconstruction candidate refused at " + stage + ": " + str(reason)
        )
        self.stage, self.original, self.partial = stage, original, partial


def request_record(value):
    return (LAW_ID, value.evidence, value.original_cache, value.retained_point_ids)


def bind(raw):
    if not isinstance(raw, Mapping) or set(raw) != {
        "kind",
        "opted_in_law",
        "evidence",
        "cache",
        "retained_point_ids",
    }:
        raise ValueError("Require a separate complete reconstruction declaration")
    if raw["kind"] != INPUT_KIND or raw["opted_in_law"] != LAW_ID:
        raise ValueError("Explicit corrected-law opt-in is required")
    evidence = raw["evidence"]
    if set(evidence) != {
        "case",
        "original_record",
        "record_sha256",
        "archive_sha256",
        "cache_identity",
        "original_status",
        "source_revision",
        "saved_decode_scope",
    }:
        raise ValueError("Require original evidence identities and decoding scope")
    if evidence["source_revision"] != SOURCE_REVISION:
        raise ValueError("Require the pinned source revision, not a substitute mesh law")
    if (
        evidence["original_status"] != "stable_mesh_completed_unqualified"
        or evidence["saved_decode_scope"] != "original_typed_saved_cache"
    ):
        raise ValueError("Raw failed sources are preserved, never repaired into completed meshes")
    for key in ("record_sha256", "archive_sha256", "cache_identity"):
        if (
            type(evidence[key]) is not str
            or len(evidence[key]) != 64
            or any(c not in "0123456789abcdef" for c in evidence[key])
        ):
            raise ValueError("Require original SHA256 identifiers")
    cache = raw["cache"]
    if not isinstance(cache, Mapping) or not set(REQUIRED_CACHE) <= cache.keys():
        raise ValueError("Do not supply missing native arrays or owner defaults")
    ids = tuple(raw["retained_point_ids"])
    if (
        len(ids) != len(cache["tri_verts"])
        or len(set(ids)) != len(ids)
        or any(type(i) is not str or not i for i in ids)
    ):
        raise ValueError("Retained source occurrence IDs must align with every primal vertex")
    result = Request(freeze(evidence), freeze(cache), ids, "")
    return replace(result, identity=digest(request_record(result)))


def _pairs(ring):
    return zip(ring, ring[1:] + ring[:1], strict=True)


def _points(rows, maximum, label):
    if not isinstance(rows, (tuple, list)) or not 1 <= len(rows) <= maximum:
        raise ValueError("Require bounded complete coordinate rows: " + label)
    if any(
        len(row) != 2 or any(type(x) is not float or not math.isfinite(x) for x in row)
        for row in rows
    ):
        raise ValueError("Retain the actual finite binary64 coordinates: " + label)
    if len(set(rows)) != len(rows):
        raise ValueError(
            "Duplicate geometric points require a separate occurrence/degeneracy policy"
        )


def _rings(rows, vertices, label):
    if not isinstance(rows, (tuple, list)) or not 1 <= len(rows) <= MAX_FACES:
        raise ValueError("Require bounded original polygon owner rows: " + label)
    if any(
        not 3 <= len(row) <= MAX_VERTICES
        or len(set(row)) != len(row)
        or any(type(i) is not int or not 0 <= i < vertices for i in row)
        for row in rows
    ):
        raise ValueError("Do not fill, reorder or simplify invalid polygon owner rows: " + label)


def _complex(rings, edges, vertices):
    """Signed exact incidence on the unchanged stored primal edge axis."""
    lookup, edge_faces, face_edges, face_signs = {}, [[] for _ in edges], [], []
    for i, edge in enumerate(edges):
        if (
            len(edge) != 2
            or edge[0] == edge[1]
            or any(type(v) is not int or not 0 <= v < vertices for v in edge)
        ):
            raise ValueError("Invalid original primal edge endpoints")
        key = tuple(sorted(edge))
        if key in lookup:
            raise ValueError("Duplicate original primal edge; owner ID cannot be selected silently")
        lookup[key] = i
    for owner, row in enumerate(rings):
        ids, signs = [], []
        for a, b in _pairs(row):
            key = tuple(sorted((a, b)))
            if key not in lookup:
                raise ValueError("Original primal edge coverage is incomplete")
            i = lookup[key]
            sign = 1 if edges[i] == (a, b) else -1
            ids.append(i)
            signs.append(sign)
            edge_faces[i].append((owner, sign))
        face_edges.append(ids)
        face_signs.append(signs)
    if any(
        len(row) not in (1, 2)
        or len(row) == 2
        and (row[0][0] == row[1][0] or row[0][1] == row[1][1])
        for row in edge_faces
    ):
        raise ValueError(
            "Nonmanifold/unused/same-direction primal incidence is outside this correction"
        )
    vertex_edges = [[i for i, edge in enumerate(edges) if v in edge] for v in range(vertices)]
    if any(not row for row in vertex_edges):
        raise ValueError("Unused retained primal vertex; no silent seed removal")
    d0 = [[(1 if v == b else -1 if v == a else 0) for v in range(vertices)] for a, b in edges]
    d1 = [[0] * len(edges) for _ in rings]
    for fi, (ids, signs) in enumerate(zip(face_edges, face_signs, strict=True)):
        for i, sign in zip(ids, signs, strict=True):
            d1[fi][i] = sign
    if any(
        sum(row[e] * d0[e][v] for e in range(len(edges))) for row in d1 for v in range(vertices)
    ):
        raise ValueError("Integer primal boundary-of-boundary does not vanish")
    boundary = [i for i, row in enumerate(edge_faces) if len(row) == 1]
    return dict(
        edges=edges,
        face_to_edges=face_edges,
        face_edge_signs=face_signs,
        edge_to_faces=[[owner for owner, _ in row] for row in edge_faces],
        vertex_to_edges=vertex_edges,
        boundary_edges=boundary,
        boundary_vertices=sorted({v for i in boundary for v in edges[i]}),
        boundary_faces_per_boundary_edge=[edge_faces[i][0][0] for i in boundary],
        delta_0=d0,
        delta_1=d1,
        inverse_operators=None,
    )


def _dual(rings, primal_edges, vertices):
    """Full polygon edges and selected primal-aligned interfaces are distinct."""
    edges, lookup, rows = [], {}, []
    for owner, ring in enumerate(rings):
        for local, (a, b) in enumerate(_pairs(ring)):
            key = tuple(sorted((a, b)))
            if key not in lookup:
                lookup[key] = len(edges)
                edges.append((a, b))
                rows.append([])
            edge = lookup[key]
            rows[edge].append((owner, local, 1 if edges[edge] == (a, b) else -1))
    if len(edges) > MAX_EDGES * 2 or any(
        len(row) not in (1, 2)
        or len(row) == 2
        and (row[0][0] == row[1][0] or row[0][2] == row[1][2])
        for row in rows
    ):
        raise ValueError("Dual rings have nonmanifold, duplicate-owner or same-direction incidence")
    by_owner = defaultdict(list)
    for i, row in enumerate(rows):
        if len(row) == 2:
            by_owner[tuple(sorted((row[0][0], row[1][0])))].append(i)
    selected, selected_to_full, full_to_selected = [], [], [[] for _ in edges]
    for pi, (owner_a, owner_b) in enumerate(primal_edges):
        candidates = by_owner[tuple(sorted((owner_a, owner_b)))]
        if len(candidates) != 1:
            raise ValueError("Primal neighbor pair has missing or ambiguous dual interface")
        i = candidates[0]
        full_to_selected[i].append(pi)
        if len(full_to_selected[i]) != 1:
            raise ValueError("Distinct primal edges cannot alias a selected dual interface")
        _, local, _ = next(row for row in rows[i] if row[0] == owner_a)
        ring = rings[owner_a]
        # Reverse the CCW owner-a traversal, matching the native clockwise
        # selected-dual convention when physical orientation is verified.
        selected.append((ring[(local + 1) % len(ring)], ring[local]))
        selected_to_full.append(i)
    shared = {i for i, row in enumerate(rows) if len(row) == 2}
    if set(selected_to_full) != shared:
        raise ValueError("A shared dual interface has no original primal owner pair")
    boundary = [i for i, row in enumerate(rows) if len(row) == 1]
    d0 = [[1 if v == b else -1 if v == a else 0 for v in range(vertices)] for a, b in edges]
    d1 = [[0] * len(edges) for _ in rings]
    for i, row in enumerate(rows):
        for owner, _, sign in row:
            d1[owner][i] = sign
    if any(
        sum(row[e] * d0[e][v] for e in range(len(edges))) for row in d1 for v in range(vertices)
    ):
        raise ValueError("Integer dual polygon boundary-of-boundary does not vanish")
    selected_d0 = [
        [1 if v == b else -1 if v == a else 0 for v in range(vertices)] for a, b in selected
    ]
    reverse_boundary = [[0] * len(selected) for _ in rings]
    for pi, (a, b) in enumerate(selected):
        for owner, local, _ in rows[selected_to_full[pi]]:
            ring = rings[owner]
            directed = (ring[local], ring[(local + 1) % len(ring)])
            reverse_boundary[owner][pi] = -1 if directed == (a, b) else 1
    expected = [
        [1 if owner == a else -1 if owner == b else 0 for a, b in primal_edges]
        for owner in range(len(rings))
    ]
    if reverse_boundary != expected:
        raise ValueError(
            "Selected dual owner incidence violates the native reverse-boundary convention"
        )
    return dict(
        full_edges=edges,
        full_edge_owner_occurrences=rows,
        full_boundary_edges=boundary,
        full_boundary_vertices=sorted({v for i in boundary for v in edges[i]}),
        selected_edges=selected,
        selected_to_full=selected_to_full,
        full_to_selected=full_to_selected,
        full_delta_0=d0,
        full_polygon_delta_1=d1,
        selected_delta_0=selected_d0,
        selected_reverse_polygon_delta_1=reverse_boundary,
        inverse_operators=None,
        orientation_requires_positive_CCW_geometry_check=True,
    )


def candidate_record(value):
    return (
        LAW_ID,
        value.request_identity,
        value.geometry,
        value.primal,
        value.dual,
        value.physical_owner_plan,
        value.differences,
        value.prerequisites,
    )


def reconstruct(request):
    """Build only the separately declared candidate; no physical admission."""
    stage, primal, dual = "request", None, None
    try:
        if type(request) is not Request or request.identity != digest(request_record(request)):
            raise ValueError("Changed original reconstruction request")
        cache = request.original_cache
        points, faces, edges, vpoints, vcells = (
            cache[k] for k in ("tri_verts", "tri_cells", "tri_edges", "vor_verts", "vor_cells")
        )
        _points(points, MAX_VERTICES, "primal")
        _points(vpoints, MAX_EDGES, "dual")
        _rings(faces, len(points), "primal")
        _rings(vcells, len(vpoints), "dual")
        if len(vcells) != len(points) or not 1 <= len(edges) <= MAX_EDGES:
            raise ValueError("Retain exactly one dual polygon per source seed owner")
        stage = "primal_incidence"
        primal = _complex(faces, edges, len(points))
        stage = "dual_owner_pairing"
        dual = _dual(vcells, edges, len(vpoints))
        stage = "physical_owner_plan"
        occurrences, cell_to_membranes = [], []
        for owner, ring in enumerate(vcells):
            row = []
            # Cells.cellVerts local membrane i is edge(i-1,i), and flattened
            # mem_verts[i] is its current endpoint. Preserve that source axis.
            for local, b in enumerate(ring):
                a = ring[local - 1]
                row.append(len(occurrences))
                occurrences.append(dict(cell=owner, local_edge=local, dual_endpoints=(a, b)))
            cell_to_membranes.append(row)
        by_edge = defaultdict(list)
        for i, row in enumerate(occurrences):
            by_edge[tuple(sorted(row["dual_endpoints"]))].append(i)
        partners, boundary_mems = [], []
        for i, row in enumerate(occurrences):
            owners = by_edge[tuple(sorted(row["dual_endpoints"]))]
            if len(owners) == 1:
                partners.append(None)
                boundary_mems.append(i)
            elif len(owners) == 2:
                partners.append(next(j for j in owners if j != i))
            else:
                raise ValueError("Ambiguous physical membrane occurrence")
        physical = dict(
            membrane_edge_convention="native_previous_vertex_to_current_vertex",
            cell_occurrence_ids=request.retained_point_ids,
            membrane_occurrences=occurrences,
            cell_to_membranes=cell_to_membranes,
            membrane_to_cells=[r["cell"] for r in occurrences],
            interior_partner_occurrences=partners,
            boundary_membrane_occurrences=boundary_mems,
            boundary_partner_policy=None,
            scaled_physical_geometry=None,
        )
        differences = dict(
            face_incidence="canonical undirected endpoint lookup with stored-edge signs",
            vertex_incidence="unique edge endpoints, not duplicated face traversals",
            dual_pairing="exact dual-cell owner pair, never nearest midpoint",
            dual_orientation=(
                "reverse the directed owner-a polygon traversal; "
                "check geometric handedness prospectively"
            ),
            dual_boundary="full dual-edge axis kept separately; selected-to-full map explicit",
            source_primal_edge_order_preserved=True,
            source_coordinates_changed=False,
            source_face_or_vertex_order_changed=False,
            native_equivalence_claimed=False,
            original_arrays_overwritten=False,
            invalidated_native_cache_fields=INVALIDATED,
        )
        prerequisites = dict(
            independent_geometry_check_required=True,
            candidate_evaluated_by_this_receipt=True,
            physical_geometry_admitted=False,
            native_mesh_qualified=False,
            ordinary_ECM_loop_ready=False,
            new_metrics_required=True,
            inverse_DEC_operators_required=True,
            physical_parameters_required=("cell_height", "scale_cell", "cell_space", "tm"),
            explicit_world_and_environment_grid_required=True,
            native_profiles_gap_policy_required=True,
            independent_CCW_nonoverlap_boundary_area_dual_pairing_checks_required=True,
            native_physical_cell_volumes_are_not_unshrunk_mesh_area_times_height=True,
        )
        result = Candidate(
            request.identity,
            freeze(dict(tri_verts=points, tri_cells=faces, vor_verts=vpoints, vor_cells=vcells)),
            freeze(primal),
            freeze(dual),
            freeze(physical),
            freeze(differences),
            freeze(prerequisites),
            "",
        )
        return replace(result, identity=digest(candidate_record(result)))
    except Exception as error:
        raise ReconstructionRejected(
            error, stage=stage, original=request, partial=freeze(dict(primal=primal, dual=dual))
        ) from error


def require_physical_admission(candidate):
    """An incidence candidate cannot stand in for initialized physical owners."""
    raise ReconstructionRejected(
        "Fresh metrics, inverses, physical cells/environment and independent geometry checks "
        "are required; this candidate is not an initialized native mesh",
        stage="physical_admission",
        original=candidate,
    )
