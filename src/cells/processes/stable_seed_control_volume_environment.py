"""Owned bridge-to-environment correspondence with finite-ECM obstruction proof.

This law does not create ECM polygons, choose baths or alter the physical model.
All indices and geometric witnesses are rebuilt from accepted shared coordinates.
"""

import hashlib
from collections import defaultdict
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path

from cells.processes import stable_seed_control_volume_physical_bridge as bridge

LAW_ID = "cells_fixed_seed_environment_prerequisite_correspondence@1"
INPUT_KIND = "cells.fixed_seed_environment_correspondence_declaration@1"
BRIDGE_REFERENCE_SHA256 = "817cec999961c7403e99addead76a720caad8ef16011a1a4e2f6319d0d72ee8c"
SOURCE_PINS = {
    "processes/stable_seed_control_volume_physical_bridge.py": (
        "be08b8953ff81107d12f39e19e3a870b2f1dd1604199d318fb823bd061842156"
    ),
    "processes/finite_ecm_polygon_geometry.py": (
        "9769a8ec6e2816fa3b4d939c6b0f4d0518b01a7ec6679e9090442d984534c925"
    ),
    "core/finite_ecm_polygon_preparation.py": (
        "a4b94d721023b98e8acc4df935f6e7ce651ad4ad0a63a692b09d346c56fc1180"
    ),
    "core/active_ecm_polygon_preparation.py": (
        "58786f33f5e6910adf1b37e4ab6b7f098c04733bfcd81c3c31be749d82af2884"
    ),
}
INVALIDATED = (
    "all_native_cell_to_environment_and_membrane_to_environment_indices",
    "all_environment_grid_volumes_boundaries_divergence_maps_and_operators",
    "all_bath_face_centroid_links_lengths_and_diffusion_stores",
    "all_native_initialization_ordinary_loop_and_solver_cache_bindings",
)


@dataclass(frozen=True)
class BridgeEvidence:
    input_json: str
    report_json: str
    caller_acceptance: object


@dataclass(frozen=True)
class Request:
    bridge_request: bridge.Request
    geometry_preparation: bridge.GeometryPreparation
    physical_preparation: bridge.PhysicalPreparation
    bridge_evidence: BridgeEvidence
    declaration: object
    identity: str


@dataclass(frozen=True)
class Correspondence:
    request_identity: str
    indices: object
    witnesses: object
    provenance: object
    identity: str


class EnvironmentRejected(ValueError):
    def __init__(self, reason, *, stage, original=None, partial=None):
        super().__init__(
            "Fixed-seed environment correspondence refused at " + stage + ": " + str(reason)
        )
        self.stage, self.original, self.partial = stage, original, partial


plain, digest = bridge.plain, bridge.digest


def _pins():
    package = Path(__file__).resolve().parents[1]
    for relative, expected in SOURCE_PINS.items():
        if hashlib.sha256((package / relative).read_bytes()).hexdigest() != expected:
            raise ValueError("Changed frozen environment correspondence source: " + relative)


def _evidence(request, geometry, physical, proof):
    if type(proof) is not BridgeEvidence:
        raise ValueError("Complete original positive physical bridge evidence required")
    incoming = bridge._json_record(proof.input_json, 128 * 2**20)
    report = bridge._json_record(proof.report_json, 128 * 2**20)
    expected = dict(
        request=plain(request),
        physical_input=plain(physical.physical_input),
        candidate=dict(geometry_preparation=plain(geometry), physical_preparation=plain(physical)),
    )
    if digest(incoming) != digest(expected):
        raise ValueError(
            "Require original complete positive bridge input without control candidates"
        )
    accepted = proof.caller_acceptance
    if not isinstance(accepted, bridge.Mapping) or set(accepted) != {
        "kind",
        "caller",
        "bridge_request_identity",
        "geometry_preparation_identity",
        "physical_preparation_identity",
        "input_sha256",
        "report_sha256",
        "scope",
    }:
        raise ValueError("Explicit caller acceptance of the complete physical bridge required")
    input_sha = hashlib.sha256(proof.input_json.encode("utf-8")).hexdigest()
    report_sha = hashlib.sha256(proof.report_json.encode("utf-8")).hexdigest()
    wanted = dict(
        kind="caller_accepts_complete_positive_manufactured_physical_bridge@1",
        caller=accepted["caller"],
        bridge_request_identity=request.identity,
        geometry_preparation_identity=geometry.identity,
        physical_preparation_identity=physical.identity,
        input_sha256=input_sha,
        report_sha256=report_sha,
        scope="initial_manufactured_physical_bridge_only_no_ECM_or_native_environment_admission",
    )
    if (
        type(accepted["caller"]) is not str
        or not accepted["caller"]
        or digest(accepted) != digest(wanted)
    ):
        raise ValueError("Changed accepted bridge identity, original evidence bytes or scope")
    if (
        report["status"] != "complete"
        or report["baseline_passed"] is not True
        or report["candidate_passed"] is not True
        or report["control_detected"] is not False
        or report["controls"] != []
        or report.get("runtime_capture_failed", False) is not False
    ):
        raise ValueError(
            "Only a complete positive physical bridge report can supply prerequisite evidence"
        )
    baseline, truth = report["baseline"], report["reference"]
    if (
        baseline["passed"] is not True
        or baseline["complete_owner_metric_evidence_inventory"] is not True
        or baseline["physical"] is None
        or baseline["field_or_solver_executed_by_reference"] is not False
    ):
        raise ValueError("Physical bridge baseline must cover every owner and physical quantity")
    g = geometry.geometry_binding.geometry
    n, e, m, j, b = (len(g[key]) for key in ("cells", "edges", "membranes", "contacts", "baths"))
    species = len(physical.physical_input["physics"]["species"])
    if (
        len(baseline["geometry"]["full_precision_quantities"]) != 4 * n + 6 * e
        or len(baseline["physical"]["full_precision_quantities"]) != n + b + (2 + species) * m + j
        or digest(truth["axes"]["owner_maps"]) != digest(geometry.owner_maps)
        or digest(truth["conservation"]) != digest(geometry.conservation)
        or digest(truth["provenance"]) != digest(geometry.provenance)
        or digest(truth["physical_input"]) != digest(physical.physical_input)
        or digest(truth["polygon_input"]) != digest(geometry.geometry_request.declaration)
        or truth["constructor_geometry_replayed"] is not False
    ):
        raise ValueError("Incomplete/changed accepted bridge target or scalar inventory")
    for precision in ("primary", "refined"):
        if len(truth[precision]["cells"]) != n or len(truth[precision]["edges"]) != e:
            raise ValueError("Truncated independent bridge polygon target axis")
    runtime = report["runtime_origin"]
    if (
        runtime["input_sha256"] != input_sha
        or runtime["source_sha256"] != BRIDGE_REFERENCE_SHA256
        or runtime["files"].get(runtime["source"]) != BRIDGE_REFERENCE_SHA256
        or runtime["production_and_scientific_imports_denied"] is not True
        or runtime["production_or_scientific_modules_loaded"] != []
        or runtime["file_errors"] != {}
        or runtime["mapped_file_errors"] != []
        or type(runtime["pid"]) is not int
        or type(runtime["parent_pid"]) is not int
        or runtime["pid"] <= 0
        or runtime["parent_pid"] <= 0
        or runtime["pid"] == runtime["parent_pid"]
    ):
        raise ValueError("Complete independent bridge child/runtime provenance required")
    return dict(
        input_sha256=input_sha,
        report_sha256=report_sha,
        caller_acceptance_digest=digest(accepted),
        reference_sha256=BRIDGE_REFERENCE_SHA256,
        complete_physical_bridge_accepted_by_caller=True,
        public_hash_consistency_alone_is_scientific_review=False,
    )


def _accepted(request, geometry, physical, proof):
    try:
        return _evidence(request, geometry, physical, proof)
    except (KeyError, TypeError, AttributeError, IndexError) as error:
        raise ValueError("Incomplete positive bridge evidence fields, axes or runtime") from error


def _rows(rows, key, wanted, label):
    if not isinstance(rows, (tuple, list)) or len(rows) != len(wanted):
        raise ValueError("Complete explicit caller rows required: " + label)
    indexed = {row[key]: row for row in rows}
    if len(indexed) != len(rows) or set(indexed) != set(wanted):
        raise ValueError("Duplicate, missing or unknown caller owner: " + label)
    if any(digest(indexed[name]) != digest(value) for name, value in wanted.items()):
        raise ValueError(
            "Caller row changes an accepted owner or selects an unsupported condition: " + label
        )


def _declaration(value, request, prepared, physical):
    if not isinstance(value, bridge.Mapping) or set(value) != {
        "kind",
        "opted_in_law",
        "scope",
        "domain_selection",
        "baths",
        "membrane_baths",
        "outer_boundary",
        "operator_policy",
    }:
        raise ValueError(
            "Complete explicit caller domain, baths and boundary correspondence required"
        )
    if (
        value["kind"] != INPUT_KIND
        or value["opted_in_law"] != LAW_ID
        or value["scope"]
        != "prerequisite_correspondence_only_no_finite_ECM_or_native_environment_admission"
    ):
        raise ValueError("Explicit correspondence-only law and scope required")
    selected = value["domain_selection"]
    if (
        not isinstance(selected, bridge.Mapping)
        or set(selected) != {"caller", "document_sha256", "selected_domain", "native_equivalence"}
        or type(selected["caller"]) is not str
        or not selected["caller"]
        or type(selected["document_sha256"]) is not str
        or len(selected["document_sha256"]) != 64
        or any(c not in "0123456789abcdef" for c in selected["document_sha256"])
        or selected["native_equivalence"] is not False
        or digest(selected["selected_domain"])
        != digest(request.declaration["domain_selection"]["selected_domain"])
    ):
        raise ValueError(
            "Caller must select the complete accepted domain without extension or native claim"
        )
    if digest(value["operator_policy"]) != digest(
        dict(
            kind="invalidate_all_environment_indices_and_operators@1",
            provided_cached_operators=None,
        )
    ):
        raise ValueError("All stale environment caches/operators are refused")
    g = prepared.geometry_binding.geometry
    baths = {
        row["id"]: row for row in physical.physical_preparation.definition["model"]["extracellular"]
    }
    wanted_baths = {
        row["id"]: dict(
            id=row["id"],
            volume_m3=row["volume_m3"],
            reservoir=baths[row["id"]]["reservoir"],
            boundary_potential_V=baths[row["id"]]["boundary_potential_V"],
            geometry_role="declared_compartment_without_polygon_geometry@1",
        )
        for row in g["baths"]
    }
    _rows(value["baths"], "id", wanted_baths, "baths")
    wanted_membranes = {
        row["id"]: dict(
            membrane_id=row["id"],
            cell_id=row["cell_id"],
            bath_id=row["bath_id"],
            directed_vertex_ids=row["vertex_ids"],
        )
        for row in g["membranes"]
    }
    _rows(value["membrane_baths"], "membrane_id", wanted_membranes, "membrane baths")
    boundary = value["outer_boundary"]
    if (
        not isinstance(boundary, bridge.Mapping)
        or set(boundary) != {"kind", "condition", "rows"}
        or boundary["kind"] != "prospective_same_ring_ECM_boundary_not_admitted@1"
        or boundary["condition"] != "sealed_no_transport@1"
    ):
        raise ValueError(
            "Explicit prospective sealed boundary selection required; "
            "no actual ECM boundary inferred"
        )
    wanted_boundary = {
        row["id"]: dict(
            membrane_id=row["id"],
            cell_id=row["cell_id"],
            assigned_bath_id=row["bath_id"],
            directed_vertex_ids=row["vertex_ids"],
        )
        for row in g["membranes"]
        if row["partner_id"] == row["id"]
    }
    _rows(boundary["rows"], "membrane_id", wanted_boundary, "cell-owned prospective outer boundary")
    return bridge.volumes.topology.freeze(plain(value))


def request_record(value):
    return (
        LAW_ID,
        value.bridge_request,
        value.geometry_preparation,
        value.physical_preparation,
        value.bridge_evidence,
        value.declaration,
    )


def bind(request, geometry, physical, proof, declaration):
    _pins()
    if (
        type(request) is not bridge.Request
        or type(geometry) is not bridge.GeometryPreparation
        or type(physical) is not bridge.PhysicalPreparation
    ):
        raise ValueError(
            "Complete owned accepted bridge request, geometry and physical preparation required"
        )
    bridge.validate_physical(request, geometry, physical)
    _accepted(request, geometry, physical, proof)
    declared = _declaration(declaration, request, geometry, physical)
    owned = BridgeEvidence(
        proof.input_json,
        proof.report_json,
        bridge.volumes.topology.freeze(plain(proof.caller_acceptance)),
    )
    value = Request(request, geometry, physical, owned, declared, "")
    return replace(value, identity=digest(request_record(value)))


def _ratio(value):
    return dict(numerator=str(value.numerator), denominator=str(value.denominator))


def _area(points):
    return (
        sum(
            (
                a[0] * b[1] - a[1] * b[0]
                for a, b in zip(points, points[1:] + points[:1], strict=True)
            ),
            Fraction(0),
        )
        / 2
    )


def _construct(request):
    g = request.geometry_preparation.geometry_binding.geometry
    vertices = {
        row["id"]: tuple(Fraction.from_float(v) for v in row["xy_m"]) for row in g["vertices"]
    }
    vertex_ids = sorted(vertices, key=lambda name: (*vertices[name], name))
    vi = {name: i for i, name in enumerate(vertex_ids)}
    source_vi = {row["id"]: i for i, row in enumerate(g["vertices"])}
    coordinate_rows = [
        dict(
            index=i,
            vertex_id=name,
            xy_m=g["vertices"][source_vi[name]]["xy_m"],
            source_vertex_index=source_vi[name],
        )
        for i, name in enumerate(vertex_ids)
    ]
    cell_ids, bath_ids = [row["id"] for row in g["cells"]], sorted(row["id"] for row in g["baths"])
    owners = cell_ids + bath_ids
    oi = {name: i for i, name in enumerate(owners)}
    half, cell_rows, incidence = [], [], defaultdict(list)
    source_half = {
        (row["cell_id"], tuple(row["vertex_ids"])): i for i, row in enumerate(g["membranes"])
    }
    for ci, cell in enumerate(g["cells"]):
        ring = cell["vertex_ids"]
        first = min(range(len(ring)), key=lambda i: vi[ring[i]])
        ring = ring[first:] + ring[:first]
        start = len(half)
        for local, (a, b) in enumerate(zip(ring, ring[1:] + ring[:1], strict=True)):
            si = source_half[(cell["id"], (a, b))]
            membrane = g["membranes"][si]
            row = dict(
                index=len(half),
                membrane_id=membrane["id"],
                source_membrane_index=si,
                cell_id=cell["id"],
                cell_index=ci,
                local_edge=local,
                vertex_indices=[vi[a], vi[b]],
                bath_id=membrane["bath_id"],
                bath_owner_index=oi[membrane["bath_id"]],
            )
            incidence[tuple(sorted((vi[a], vi[b])))].append(len(half))
            half.append(row)
        cell_rows.append(
            dict(
                index=ci,
                cell_id=cell["id"],
                vertex_indices=[vi[name] for name in ring],
                membrane_indices=list(range(start, len(half))),
            )
        )
    edge_rows, boundary_rows, direct = [], [], []
    selected_boundary = {
        row["membrane_id"]: row for row in request.declaration["outer_boundary"]["rows"]
    }
    height = Fraction.from_float(g["height_m"])
    for ei, (edge, halves) in enumerate(sorted(incidence.items())):
        for index in halves:
            half[index]["edge_index"] = ei
            half[index]["partner_index"] = (
                halves[1 - halves.index(index)] if len(halves) == 2 else index
            )
        row = dict(
            index=ei,
            vertex_indices=list(edge),
            membrane_indices=halves,
            cell_ids=[half[i]["cell_id"] for i in halves],
            kind="direct_cell_cell" if len(halves) == 2 else "cell_owned_exterior",
        )
        edge_rows.append(row)
        if len(halves) == 2:
            direct.append(row)
        else:
            membrane = half[halves[0]]
            selected = selected_boundary[membrane["membrane_id"]]
            a, b = (vertices[name] for name in selected["directed_vertex_ids"])
            boundary_rows.append(
                dict(
                    edge_index=ei,
                    membrane_index=membrane["index"],
                    cell_id=membrane["cell_id"],
                    assigned_bath_id=membrane["bath_id"],
                    vertex_indices=membrane["vertex_indices"],
                    selected_prospective_condition=request.declaration["outer_boundary"][
                        "condition"
                    ],
                    actual_polygon_owner_kind="cell",
                    exact_side_area_normal_xy_m2=[
                        _ratio((b[1] - a[1]) * height),
                        _ratio((a[0] - b[0]) * height),
                    ],
                )
            )
    membrane_incidence = [
        [int(name == row["bath_id"]) - int(name == row["cell_id"]) for row in half]
        for name in owners
    ]
    contact_incidence = [
        [int(name == row["cell_ids"][1]) - int(name == row["cell_ids"][0]) for row in direct]
        for name in owners
    ]
    if any(sum(row[i] for row in membrane_incidence) for i in range(len(half))) or any(
        sum(row[i] for row in contact_incidence) for i in range(len(direct))
    ):
        raise ValueError("Rebuilt complete owner incidence is not conservative")
    areas = [_area([vertices[name] for name in row["vertex_ids"]]) for row in g["cells"]]
    domain = request.declaration["domain_selection"]["selected_domain"]["vertices_m"]
    domain_area = _area([tuple(Fraction.from_float(v) for v in p) for p in domain])
    remaining = domain_area - sum(areas, Fraction(0))
    if remaining != 0 or not boundary_rows:
        raise ValueError(
            "Accepted shared cell partition no longer exactly exhausts its selected domain"
        )
    bath_volume = sum(
        (Fraction.from_float(row["volume_m3"]) for row in request.declaration["baths"]), Fraction(0)
    )
    if bath_volume <= 0:
        raise ValueError("Explicit accepted baths require positive volume")
    actual_baths = {row["id"]: row for row in request.declaration["baths"]}
    bath_rows = [
        dict(
            actual_baths[name],
            index=i,
            owner_index=oi[name],
            source_owner_index=g["owner_axis"].index(name),
        )
        for i, name in enumerate(bath_ids)
    ]
    indices = dict(
        vertices=coordinate_rows,
        cells=cell_rows,
        owner_axis=owners,
        baths=bath_rows,
        membranes=half,
        edges=edge_rows,
        boundary=boundary_rows,
        direct_cell_cell_interfaces=direct,
        membrane_incidence=membrane_incidence,
        contact_incidence=contact_incidence,
        bath_bath_faces=[],
        bath_centroid_links=[],
        nearest_midpoint_or_native_grid_mapping_used=False,
    )
    witnesses = dict(
        domain_area_m2_exact=_ratio(domain_area),
        cell_area_m2_exact=[_ratio(value) for value in areas],
        cell_area_sum_m2_exact=_ratio(sum(areas, Fraction(0))),
        available_disjoint_bath_area_m2_exact=_ratio(remaining),
        requested_bath_volume_m3_exact=_ratio(bath_volume),
        requested_bath_area_at_same_height_m2_exact=_ratio(bath_volume / height),
        exact_bath_area_shortfall_m2=_ratio(bath_volume / height - remaining),
        cell_owned_outer_boundary_edges=len(boundary_rows),
        direct_cell_cell_edges=len(direct),
        source_bath_polygons=0,
        source_bath_bath_faces=0,
        source_bath_centroid_links=0,
        finite_ECM_requirements=dict(
            positive_bath_polygons=True,
            bath_only_outer_boundary=True,
            direct_cell_cell_interfaces_supported=False,
            at_least_one_bath_bath_face=True,
            orthogonal_centroid_face_distances=True,
        ),
        unmet_prerequisites=[
            "positive_disjoint_bath_polygons_inside_selected_domain",
            "bath_owned_complete_exterior",
            "bath_bath_faces_and_orthogonal_centroid_links",
        ]
        + (["declared_intercellular_cleft_geometry"] if direct else []),
        prospective_boundary_condition_applied_to_physics=False,
        cell_geometry_changed=False,
        bath_roles_or_volumes_changed=False,
    )
    provenance = dict(
        kind="cells.fixed_seed_environment_prerequisite_correspondence@1",
        law=LAW_ID,
        accepted_bridge_evidence=_accepted(
            request.bridge_request,
            request.geometry_preparation,
            request.physical_preparation,
            request.bridge_evidence,
        ),
        physical_bridge_identity=request.physical_preparation.identity,
        geometry_preparation_identity=request.geometry_preparation.identity,
        source_pins=SOURCE_PINS,
        scope_correction=plain(bridge.SCOPE_CORRECTION),
        invalidated=INVALIDATED,
        source_owner_correspondence_prepared=True,
        finite_ECM_adapted=False,
        environment_grid_bound=False,
        physical_model_changed=False,
        native_equivalence=False,
        cached_operators_accepted=False,
        ordinary_ECM_loop_ready=False,
        solver_trajectory_executed=False,
        inherited_qualification=False,
        required_next_authority=(
            "explicit cell/ECM physical geometry law resolving clefts, positive bath polygons, "
            "domain and distances; independently qualified"
        ),
    )
    return indices, witnesses, provenance


def correspondence_record(value):
    return (LAW_ID, value.request_identity, value.indices, value.witnesses, value.provenance)


def prepare(request):
    partial = dict(request=plain(request), stage="complete_accepted_bridge")
    try:
        if type(request) is not Request:
            raise ValueError("Owned complete environment correspondence request required")
        rebuilt = bind(
            request.bridge_request,
            request.geometry_preparation,
            request.physical_preparation,
            request.bridge_evidence,
            request.declaration,
        )
        if digest(rebuilt) != digest(request):
            raise ValueError("Changed or resealed complete environment request")
        partial["stage"] = "coordinate_owner_correspondence_and_obstruction"
        indices, witnesses, provenance = _construct(request)
        value = Correspondence(
            request.identity,
            *(
                bridge.volumes.topology.freeze(plain(row))
                for row in (indices, witnesses, provenance)
            ),
            "",
        )
        return replace(value, identity=digest(correspondence_record(value)))
    except Exception as error:
        raise EnvironmentRejected(
            str(error),
            stage=partial["stage"],
            original=dict(
                type=type(error).__name__,
                reason=str(error),
                original=plain(getattr(error, "original", None)),
                partial=plain(getattr(error, "partial", None)),
            ),
            partial=partial,
        ) from error


def validate(request, value):
    if type(value) is not Correspondence or digest(prepare(request)) != digest(value):
        raise ValueError(
            "Changed complete environment correspondence, obstruction, provenance or seal"
        )
    return value


def require_finite_ecm(value):
    raise EnvironmentRejected(
        "Positive ECM partition/cleft/bath-face geometry is unavailable; "
        "correspondence is not adaptation",
        stage="finite_ECM_adaptation",
        original=plain(value),
        partial=dict(admitted=False),
    )


def require_cached_operators(_value):
    raise ValueError("All old environment indices and operators are invalidated")
