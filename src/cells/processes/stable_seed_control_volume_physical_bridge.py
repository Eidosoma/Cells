"""Explicit fixed-seed output to manufactured polygon physical preparation.

Constructor proposals, native geometry and cached operators are not admission
authorities here. Full positive constructor evidence and fresh caller domain,
extrusion, bath and physical declarations are required.
"""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path

from cells.core import conservative_polygon_tissue_preparation as physical
from cells.processes import conservative_polygon_geometry as geometry
from cells.processes import stable_seed_control_volumes as volumes

LAW_ID = "cells_fixed_seed_explicit_domain_manufactured_polygon_physical_bridge@1"
INPUT_KIND = "cells.fixed_seed_control_volume_physical_bridge_declaration@1"
SOURCE_PINS = {
    "core/conservative_polygon_tissue_preparation.py": (
        "91c4bab5a1dd194c411d787e749d57f864ccffc17336f0d957cd1d856c10a039"
    ),
    "processes/conservative_polygon_geometry.py": (
        "5d267b20cdb3a05f4f036bbc3fa6978b40780ca4394f67ac6c33a8b605af4b0d"
    ),
    "processes/stable_seed_control_volumes.py": (
        "a1f743f2b1c8adb2b169693870d1de2916b2fa0dc616b39200b5f8f905327916"
    ),
}
CONSTRUCTOR_REFERENCE_SHA256 = "643ea598f74c4a5d56753b5712d528937683cc35b57e6c904bc113bed1ac7813"
CONSTRUCTOR_SOURCE_REVIEW_SHA256 = (
    "97bd51e675c3840bbdc7a654604ee1d08c2e58972b177b03aa3bb878c1cea3d5"
)
INVALIDATED = (
    "all_original_and_constructor_cached_operators_inverses_and_Hodge_stores",
    "native_primal_dual_membrane_gap_profile_and_boundary_maps",
    "all_old_coordinate_dependent_areas_volumes_normals_and_capacitances",
    "environment_grid_bath_geometry_and_solver_caches",
    "native_initialization_trajectory_and_ordinary_loop_bindings",
)
SCOPE_CORRECTION = dict(
    five_failed_layout_owners=37,
    five_failed_layout_outside_owners=20,
    earlier_six_layout_panel_owners=50,
    earlier_passing_square_zero_owners=13,
    missing_envelope_cases=("caller-single-square-cache", "caller-single-hex-cache"),
    missing_envelope_origin="lattice_seeded_ring_and_centre_caller_caches",
    missing_envelopes_resolved=False,
    original_mesh_outcome="0/9 unchanged",
)


@dataclass(frozen=True)
class ConstructorEvidence:
    input_json: str
    report_json: str
    caller_acceptance: object


@dataclass(frozen=True)
class Request:
    constructor_request: volumes.Request
    constructor_candidate: volumes.Candidate
    constructor_evidence: ConstructorEvidence
    declaration: object
    identity: str


@dataclass(frozen=True)
class GeometryPreparation:
    request_identity: str
    geometry_request: geometry.Request
    geometry_binding: geometry.Binding
    owner_maps: object
    conservation: object
    provenance: object
    identity: str


@dataclass(frozen=True)
class PhysicalPreparation:
    request_identity: str
    geometry_preparation_identity: str
    physical_input: object
    physical_preparation: physical.Preparation
    provenance: object
    identity: str


class BridgeRejected(ValueError):
    def __init__(self, reason, *, stage, original=None, partial=None):
        super().__init__(
            "Fixed-seed manufactured physical bridge refused at " + stage + ": " + str(reason)
        )
        self.stage, self.original, self.partial = stage, original, partial


def plain(value):
    return volumes.plain(value)


def digest(value):
    return volumes.digest(value)


def _verify_sources():
    root = Path(__file__).resolve().parents[1]
    for relative, expected in SOURCE_PINS.items():
        if hashlib.sha256((root / relative).read_bytes()).hexdigest() != expected:
            raise ValueError("Changed frozen physical bridge dependency: " + relative)


def _json_record(text, limit):
    if type(text) is not str or len(text.encode("utf-8")) > limit:
        raise ValueError("Supply complete bounded original UTF-8 JSON evidence")

    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError("Duplicate evidence JSON key: " + key)
            result[key] = value
        return result

    def constant(value):
        raise ValueError("Nonfinite JSON evidence constant: " + value)

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def _constructor_evidence_fields(request, candidate, evidence):
    if type(evidence) is not ConstructorEvidence:
        raise ValueError(
            "Complete original positive constructor input/report and caller acceptance required"
        )
    incoming = _json_record(evidence.input_json, 32 * 2**20)
    report = _json_record(evidence.report_json, 64 * 2**20)
    accepted = evidence.caller_acceptance
    if not isinstance(accepted, Mapping) or set(accepted) != {
        "kind",
        "caller",
        "constructor_identity",
        "input_sha256",
        "report_sha256",
        "scope",
    }:
        raise ValueError(
            "Explicit caller acceptance must bind the full constructor identity and evidence"
        )
    input_sha = hashlib.sha256(evidence.input_json.encode("utf-8")).hexdigest()
    report_sha = hashlib.sha256(evidence.report_json.encode("utf-8")).hexdigest()
    if (
        accepted["kind"] != "caller_accepts_complete_positive_constructor_reference@1"
        or type(accepted["caller"]) is not str
        or not accepted["caller"]
        or accepted["constructor_identity"] != candidate.identity
        or accepted["input_sha256"] != input_sha
        or accepted["report_sha256"] != report_sha
        or accepted["scope"] != "constructor_geometry_only_no_native_physical_or_operator_admission"
    ):
        raise ValueError("Changed constructor acceptance identity, evidence bytes or scope")
    if (
        type(incoming) is not dict
        or set(incoming) != {"request", "candidate"}
        or digest(incoming["request"]) != digest(request)
        or digest(incoming["candidate"]) != digest(candidate)
    ):
        raise ValueError(
            "Constructor evidence must be the original complete positive input, not a control"
        )
    if (
        report.get("status") != "complete"
        or report.get("baseline_passed") is not True
        or report.get("candidate_passed") is not True
        or report.get("control_detected") is not False
        or report.get("baseline", {}).get("passed") is not True
        or report.get("candidate", {}).get("passed") is not True
        or report.get("runtime_capture_failed", False) is not False
    ):
        raise ValueError(
            "A failed/incomplete/negative-control report is not constructor validation"
        )
    expected = report["reference"]["candidate_fields"]
    original = plain(candidate)
    if set(expected) != set(original) - {"identity"} or any(
        digest(expected[key]) != digest(value)
        for key, value in original.items()
        if key != "identity"
    ):
        raise ValueError("Complete independent constructor arrays/owners/evidence do not match")
    n = len(candidate.owners["retained_point_ids"])
    v = len(candidate.stored_geometry["vertices_m"])
    counts = dict(
        seeds=n,
        domain_vertices=len(request.declaration["domain"]["vertices_m"]),
        vertices=v,
        cells=n,
        edges=len(candidate.connectivity["edges"]),
        cell_occurrences=len(candidate.connectivity["occurrences"]),
        clip_events=n * (n - 1),
        scalar_events=2 * v + 3 * n + 1,
    )
    if report["reference"]["counts"] != counts:
        raise ValueError("Constructor validation dropped an owner, clip or scalar axis")
    runtime = report["runtime_origin"]
    if (
        runtime["input_sha256"] != input_sha
        or runtime["source_sha256"] != CONSTRUCTOR_REFERENCE_SHA256
        or runtime["files"].get(runtime["source"]) != CONSTRUCTOR_REFERENCE_SHA256
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
        raise ValueError("Missing/changed independent constructor runtime provenance")
    return dict(
        constructor_identity=candidate.identity,
        input_sha256=input_sha,
        report_sha256=report_sha,
        caller_acceptance_digest=digest(accepted),
        reference_source_sha256=CONSTRUCTOR_REFERENCE_SHA256,
        independent_complete_constructor_arrays_accepted_by_caller=True,
        public_hash_consistency_alone_is_scientific_review=False,
        constructor_source_review_sha256=CONSTRUCTOR_SOURCE_REVIEW_SHA256,
    )


def _positive_constructor_evidence(request, candidate, evidence):
    try:
        return _constructor_evidence_fields(request, candidate, evidence)
    except (KeyError, TypeError, AttributeError, IndexError) as error:
        raise ValueError(
            "Incomplete constructor input, report, complete axes or runtime fields"
        ) from error


def _declaration(value, constructor_request):
    if not isinstance(value, Mapping) or set(value) != {
        "kind",
        "opted_in_law",
        "domain_selection",
        "extrusion",
        "operator_policy",
        "scope",
    }:
        raise ValueError("Complete explicit manufactured bridge declaration required")
    if value["kind"] != INPUT_KIND or value["opted_in_law"] != LAW_ID:
        raise ValueError("Explicit new physical bridge law required")
    if value["scope"] != "manufactured_polygon_preparation_not_native_geometry_equivalence":
        raise ValueError(
            "Native geometry/loop admission cannot be inferred from manufactured geometry"
        )
    operator = value["operator_policy"]
    if (
        not isinstance(operator, Mapping)
        or set(operator) != {"kind", "provided_cached_operators"}
        or operator["kind"] != "invalidate_all_and_rebuild_under_new_geometry_identity@1"
        or operator["provided_cached_operators"] is not None
    ):
        raise ValueError(
            "Stale cached operators are refused; separate rebuild/qualification required"
        )
    selected = value["domain_selection"]
    if (
        not isinstance(selected, Mapping)
        or set(selected)
        != {
            "kind",
            "selected_domain",
            "caller",
            "document_sha256",
            "purpose",
            "native_tissue_or_bath_equivalence",
        }
        or selected["kind"] != "fresh_explicit_caller_domain_selection@1"
        or type(selected["caller"]) is not str
        or not selected["caller"]
        or type(selected["document_sha256"]) is not str
        or len(selected["document_sha256"]) != 64
        or any(c not in "0123456789abcdef" for c in selected["document_sha256"])
        or selected["purpose"] != "manufactured_prismatic_partition_geometry_only"
        or selected["native_tissue_or_bath_equivalence"] is not False
        or digest(selected["selected_domain"]) != digest(constructor_request.declaration["domain"])
    ):
        raise ValueError(
            "Explicit caller-selected domain must match the complete validated constructor domain"
        )
    extrusion = value["extrusion"]
    if (
        not isinstance(extrusion, Mapping)
        or set(extrusion)
        != {
            "height_m",
            "thickness_m",
            "baths",
            "bath_assignment",
            "axial_caps",
            "units",
            "cell_policy",
            "boundary_partner_policy",
        }
        or extrusion["units"] != geometry.UNITS
        or extrusion["axial_caps"] != "sealed_no_transport@1"
        or extrusion["cell_policy"] != "one_manufactured_cell_per_retained_seed_no_merge"
        or extrusion["boundary_partner_policy"] != "conservative_self_partner_with_explicit_bath@1"
    ):
        raise ValueError(
            "Explicit uniform extrusion, membrane path, baths and boundary semantics required"
        )
    geometry._number(extrusion["height_m"], positive=True)
    geometry._number(extrusion["thickness_m"], positive=True)
    return volumes.topology.freeze(plain(value))


def request_record(value):
    return (
        LAW_ID,
        value.constructor_request,
        value.constructor_candidate,
        value.constructor_evidence,
        value.declaration,
    )


def bind(constructor_request, constructor_candidate, evidence, declaration):
    _verify_sources()
    if (
        type(constructor_request) is not volumes.Request
        or type(constructor_candidate) is not volumes.Candidate
    ):
        raise ValueError("Complete owned constructor request/candidate required")
    declared = _declaration(declaration, constructor_request)
    rebuilt = volumes.prepare(constructor_request)
    if digest(rebuilt) != digest(constructor_candidate):
        raise ValueError("Changed or resealed complete constructor geometry/owner/evidence payload")
    _positive_constructor_evidence(constructor_request, constructor_candidate, evidence)
    accepted = ConstructorEvidence(
        evidence.input_json,
        evidence.report_json,
        volumes.topology.freeze(plain(evidence.caller_acceptance)),
    )
    value = Request(constructor_request, constructor_candidate, accepted, declared, "")
    return replace(value, identity=digest(request_record(value)))


def validate_request(request):
    if type(request) is not Request:
        raise ValueError("Owned complete fixed-seed physical bridge request required")
    expected = bind(
        request.constructor_request,
        request.constructor_candidate,
        request.constructor_evidence,
        request.declaration,
    )
    if digest(request) != digest(expected):
        raise ValueError("Changed complete bridge request or seal")
    return request


def polygon_input(request):
    """Translate coordinates and directed rings; no cached measures are inputs."""
    cv = request.constructor_candidate
    ext = plain(request.declaration["extrusion"])
    seed_ids = list(cv.owners["retained_point_ids"])
    vertex_ids = list(cv.connectivity["vertices"])
    accepted = _positive_constructor_evidence(
        request.constructor_request, cv, request.constructor_evidence
    )
    source = dict(
        kind="declared_polygon_complex@1",
        generator=LAW_ID,
        recipe=dict(
            bridge_request_identity=request.identity,
            constructor_request_identity=request.constructor_request.identity,
            constructor_identity=cv.identity,
            constructor_evidence=accepted,
            caller_domain_selection=plain(request.declaration["domain_selection"]),
            cell_policy=ext["cell_policy"],
            boundary_partner_policy=ext["boundary_partner_policy"],
            coordinate_policy="constructor_shared_binary64_vertices_recompute_all_metrics@1",
            native_equivalence=False,
        ),
        generation_coverage=False,
    )
    return dict(
        source=source,
        vertices=[
            dict(id=name, xy_m=list(point))
            for name, point in zip(vertex_ids, cv.stored_geometry["vertices_m"], strict=True)
        ],
        source_cells=[
            dict(id=name, vertex_ids=[vertex_ids[i] for i in ring])
            for name, ring in zip(seed_ids, cv.stored_geometry["cells"], strict=True)
        ],
        cell_groups=[dict(id=name, source_cell_ids=[name]) for name in seed_ids],
        **{
            key: ext[key]
            for key in (
                "baths",
                "bath_assignment",
                "height_m",
                "thickness_m",
                "axial_caps",
                "units",
            )
        },
    )


def _owner_maps(cv, g):
    names = list(cv.connectivity["vertices"])
    seeds = list(cv.owners["retained_point_ids"])
    if [row["id"] for row in g["vertices"]] != names or [row["id"] for row in g["cells"]] != seeds:
        raise ValueError("New geometry lost an original vertex or retained seed owner")
    if digest([row["xy_m"] for row in g["vertices"]]) != digest(cv.stored_geometry["vertices_m"]):
        raise ValueError("New physical geometry changed a shared binary64 coordinate")
    edge_by_ids = {tuple(row["vertex_ids"]): i for i, row in enumerate(g["edges"])}
    mem_by_half = {
        (row["cell_id"], tuple(row["vertex_ids"])): i for i, row in enumerate(g["membranes"])
    }
    mem_by_id = {row["id"]: i for i, row in enumerate(g["membranes"])}
    contact_by_edge = {row["edge_id"]: i for i, row in enumerate(g["contacts"])}
    if len(edge_by_ids) != len(cv.connectivity["edges"]) or len(mem_by_half) != len(
        cv.connectivity["occurrences"]
    ):
        raise ValueError("Incomplete or duplicate physical interface axis")
    vertices = [
        dict(constructor_vertex=i, constructor_id=name, geometry_vertex=i, geometry_id=name)
        for i, name in enumerate(names)
    ]
    cells, occurrences, edges = [], [], []
    for i, cell in enumerate(g["cells"]):
        if cell["source_cell_ids"] != [seeds[i]]:
            raise ValueError("A physical cell must own exactly its retained seed polygon")
        expected = [names[j] for j in cv.stored_geometry["cells"][i]]
        ring = cell["vertex_ids"]
        if len(ring) != len(expected) or not any(
            ring == expected[j:] + expected[:j] for j in range(len(expected))
        ):
            raise ValueError("A directed physical cell boundary changed")
        cells.append(
            dict(
                constructor_cell=i,
                retained_seed_id=seeds[i],
                physical_cell=i,
                physical_cell_id=cell["id"],
                constructor_ring=list(cv.stored_geometry["cells"][i]),
                geometry_ring=ring,
            )
        )
    for index, occurrence in enumerate(cv.connectivity["occurrences"]):
        owner = occurrence["owner"]
        a, b = (names[i] for i in occurrence["directed"])
        mid = mem_by_half[(seeds[owner], (a, b))]
        membrane = g["membranes"][mid]
        edge_index = edge_by_ids[tuple(sorted((a, b)))]
        ring = g["cells"][owner]["vertex_ids"]
        local = next(i for i, v in enumerate(ring) if (v, ring[(i + 1) % len(ring)]) == (a, b))
        partner = cv.connectivity["partners"][index]
        if partner is None:
            expected_partner = mid
        else:
            other = cv.connectivity["occurrences"][partner]
            expected_partner = mem_by_half[
                (seeds[other["owner"]], tuple(names[i] for i in other["directed"]))
            ]
        if mem_by_id[membrane["partner_id"]] != expected_partner:
            raise ValueError(
                "Physical reciprocal/self partner differs from the declared translation"
            )
        occurrences.append(
            dict(
                constructor_occurrence=index,
                owner_index=owner,
                owner_id=seeds[owner],
                constructor_local_edge=occurrence["local_edge"],
                constructor_edge=occurrence["edge"],
                constructor_directed_vertices=list(occurrence["directed"]),
                directed_vertex_ids=[a, b],
                geometry_local_edge=local,
                geometry_edge=edge_index,
                geometry_edge_id=membrane["edge_id"],
                geometry_membrane=mid,
                geometry_membrane_id=membrane["id"],
                constructor_partner_occurrence=partner,
                geometry_partner_membrane=expected_partner,
                geometry_partner_membrane_id=g["membranes"][expected_partner]["id"],
                boundary_none_to_self_translation=partner is None,
            )
        )
    for index, (a, b) in enumerate(cv.connectivity["edges"]):
        pair = (names[a], names[b])
        gi = edge_by_ids[tuple(sorted(pair))]
        edge = g["edges"][gi]
        oi = list(cv.connectivity["edge_occurrences"][index])
        contact = contact_by_edge.get(edge["id"])
        if (contact is None) != (len(oi) == 1):
            raise ValueError("Boundary edge/contact cardinality differs")
        edges.append(
            dict(
                constructor_edge=index,
                constructor_directed_vertices=[a, b],
                geometry_edge=gi,
                geometry_edge_id=edge["id"],
                geometry_vertex_ids=edge["vertex_ids"],
                canonical_direction=1 if pair == tuple(edge["vertex_ids"]) else -1,
                constructor_occurrences=oi,
                geometry_membranes=[occurrences[i]["geometry_membrane"] for i in oi],
                geometry_membrane_ids=[occurrences[i]["geometry_membrane_id"] for i in oi],
                geometry_contact=contact,
                geometry_contact_id=None if contact is None else g["contacts"][contact]["id"],
            )
        )
    if {row["geometry_membrane"] for row in occurrences} != set(range(len(g["membranes"]))):
        raise ValueError("Physical membrane map is not a complete bijection")
    return dict(
        vertices=vertices,
        cells=cells,
        edges=edges,
        occurrences=occurrences,
        constructor_local_edge_convention="previous_vertex_to_current_vertex",
        geometry_local_edge_convention="current_vertex_to_next_vertex",
        canonical_edge_policy="constructor_numeric_indices_to_geometry_lexical_ids_by_endpoints",
        boundary_partner_policy="caller_declared_None_to_self_with_explicit_bath",
        cell_merges_performed=False,
        nearest_midpoint_mapping_used=False,
    )


def _ratio(value):
    return dict(numerator=str(value.numerator), denominator=str(value.denominator))


def _conservation(request, g):
    points = {
        row["id"]: tuple(Fraction.from_float(v) for v in row["xy_m"]) for row in g["vertices"]
    }
    height = Fraction.from_float(g["height_m"])
    domain = [
        tuple(Fraction.from_float(x) for x in row)
        for row in request.constructor_request.declaration["domain"]["vertices_m"]
    ]
    domain_area = geometry._moments(domain)[0]
    membranes = {row["id"]: row for row in g["membranes"]}
    cells, area_sum = [], Fraction(0)
    for cell in g["cells"]:
        ring = [points[name] for name in cell["vertex_ids"]]
        area = geometry._moments(ring)[0]
        area_sum += area
        exact_normals, readout_normals = [], []
        for mid in cell["membrane_ids"]:
            membrane = membranes[mid]
            a, b = (points[name] for name in membrane["vertex_ids"])
            exact_normals.append(((b[1] - a[1]) * height, (a[0] - b[0]) * height))
            readout_normals.append(
                tuple(
                    Fraction.from_float(value) * Fraction.from_float(membrane["area_m2"])
                    for value in membrane["normal_xy"]
                )
            )
        exact_closure = tuple(
            sum((row[axis] for row in exact_normals), Fraction(0)) for axis in (0, 1)
        )
        readout_closure = tuple(
            sum((row[axis] for row in readout_normals), Fraction(0)) for axis in (0, 1)
        )
        bound = tuple(
            sum(
                (
                    abs(b[axis] - a[axis])
                    for a, b in zip(exact_normals, readout_normals, strict=True)
                ),
                Fraction(0),
            )
            for axis in (0, 1)
        )
        if exact_closure != (0, 0) or any(
            abs(value) > limit for value, limit in zip(readout_closure, bound, strict=True)
        ):
            raise ValueError("Extruded side-area normal closure failed")
        cells.append(
            dict(
                id=cell["id"],
                area_exact=_ratio(area),
                volume_exact=_ratio(area * height),
                volume_pL_exact=_ratio(area * height * 10**15),
                side_area_normals_exact=[list(map(_ratio, row)) for row in exact_normals],
                exact_side_area_normal_sum=list(map(_ratio, exact_closure)),
                rounded_normal_times_area_sum=list(map(_ratio, readout_closure)),
                rounded_product_absolute_error_bound=list(map(_ratio, bound)),
            )
        )

    def columns(name):
        return [
            sum(row[i] for row in g[name])
            for i in range(len(g["membranes"] if name == "membrane_incidence" else g["contacts"]))
        ]

    membrane_sums, contact_sums = columns("membrane_incidence"), columns("contact_incidence")
    if area_sum != domain_area or any(membrane_sums + contact_sums):
        raise ValueError("Exact declared-domain extrusion or owner incidence balance failed")
    return dict(
        cells=cells,
        domain_area_exact=_ratio(domain_area),
        area_sum_exact=_ratio(area_sum),
        area_defect_exact=_ratio(area_sum - domain_area),
        volume_sum_exact=_ratio(area_sum * height),
        domain_extruded_volume_exact=_ratio(domain_area * height),
        volume_defect_exact=_ratio((area_sum - domain_area) * height),
        membrane_incidence_column_sums=membrane_sums,
        contact_incidence_column_sums=contact_sums,
        contacts_count_shared_interfaces_once=True,
        axial_caps="sealed_no_transport@1",
        rounded_unit_normal_times_area_exact_closure_claimed=False,
        rounding_bound_basis=(
            "fresh_geometry_projection_errors; independent reference must derive its own bound"
        ),
        inventories_rescaled=False,
        trajectory_conservation_claimed=False,
    )


def geometry_record(value):
    return (
        LAW_ID,
        value.request_identity,
        value.geometry_request,
        value.geometry_binding,
        value.owner_maps,
        value.conservation,
        value.provenance,
    )


def prepare(request, *, observer=None):
    partial = dict(stage="request", request=plain(request))
    try:
        validate_request(request)
        raw = polygon_input(request)
        partial.update(stage="declared_polygons", polygon_input=raw)
        if observer is not None:
            observer(partial["stage"], plain(partial))
        polygon_request = geometry.from_polygons(raw, law_id=geometry.LAW_ID)
        partial.update(stage="conservative_geometry", geometry_request=plain(polygon_request))
        bound = geometry.prepare(polygon_request)
        partial["geometry_binding"] = plain(bound)
        maps = _owner_maps(request.constructor_candidate, bound.geometry)
        conservation = _conservation(request, bound.geometry)
        provenance = dict(
            kind="cells.fixed_seed_manufactured_geometry_preparation@1",
            law=LAW_ID,
            constructor_evidence=_positive_constructor_evidence(
                request.constructor_request,
                request.constructor_candidate,
                request.constructor_evidence,
            ),
            declared_domain_selection=plain(request.declaration["domain_selection"]),
            scope_correction=SCOPE_CORRECTION,
            source_pins=SOURCE_PINS,
            measures_recomputed_from_shared_binary64_coordinates=True,
            constructor_cached_measures_used_as_physical_authority=False,
            one_physical_cell_per_retained_seed=True,
            geometry_law=geometry.LAW_ID,
            physical_bridge_law=physical.BRIDGE_ID,
            invalidated=INVALIDATED,
            cached_operators_accepted=False,
            independently_qualified_physical_geometry=False,
            manufactured_physical_model_prepared=False,
            native_equivalence=False,
            native_mesh_cache_admitted=False,
            inverse_operators_qualified=False,
            ordinary_ECM_loop_ready=False,
            biological_calibration=False,
            solver_trajectory_executed=False,
            constructor_prerequisites_unchanged=plain(request.constructor_candidate.prerequisites),
        )
        value = GeometryPreparation(
            request.identity,
            polygon_request,
            bound,
            volumes.topology.freeze(plain(maps)),
            volumes.topology.freeze(plain(conservation)),
            volumes.topology.freeze(plain(provenance)),
            "",
        )
        result = replace(value, identity=digest(geometry_record(value)))
        if observer is not None:
            observer("geometry_prepared", plain(result))
        return result
    except Exception as error:
        raise BridgeRejected(
            str(error),
            stage=partial["stage"],
            original=dict(
                type=type(error).__name__,
                reason=str(error),
                trial=plain(getattr(error, "trial", None)),
                partial=plain(getattr(error, "partial", None)),
            ),
            partial=partial,
        ) from error


def validate_geometry(request, prepared):
    if type(prepared) is not GeometryPreparation:
        raise ValueError("Owned complete manufactured geometry preparation required")
    expected = prepare(request)
    if digest(prepared) != digest(expected):
        raise ValueError(
            "Changed complete geometry, metrics, owners, conservation, provenance or seal"
        )
    return prepared


def physical_record(value):
    return (
        LAW_ID,
        value.request_identity,
        value.geometry_preparation_identity,
        value.physical_input,
        value.physical_preparation,
        value.provenance,
    )


def prepare_physical(request, prepared, raw, *, observer=None):
    partial = dict(
        stage="geometry_validation",
        request_identity=getattr(request, "identity", None),
        geometry_preparation=plain(prepared),
        physical_input=plain(raw),
    )
    try:
        validate_geometry(request, prepared)
        owned = json.loads(geometry._json(plain(raw)))
        execution = owned["execution"]
        if (
            execution["backend"] != "cpu"
            or execution["precision"] != "float64"
            or execution["jit"] is not False
        ):
            raise ValueError(
                "This bounded manufactured preparation requires explicit "
                "CPU/float64/non-JIT execution"
            )
        partial["stage"] = "existing_passive_physical_admission"
        if observer is not None:
            observer(partial["stage"], plain(partial))
        admitted = physical.prepare(prepared.geometry_request, prepared.geometry_binding, owned)
        provenance = dict(
            kind="cells.fixed_seed_manufactured_physical_preparation@1",
            law=LAW_ID,
            geometry_identity=prepared.geometry_binding.identity,
            constructor_identity=request.constructor_candidate.identity,
            caller_physical_input_digest=digest(owned),
            existing_physical_bridge_law=physical.BRIDGE_ID,
            physical_admission_source_sha256=physical.ADMISSION_SOURCE_SHA256,
            manufactured_physical_model_prepared=True,
            inventories_rescaled=False,
            native_equivalence=False,
            native_mesh_cache_admitted=False,
            inverse_operators_qualified=False,
            ordinary_ECM_loop_ready=False,
            biological_calibration=False,
            solver_trajectory_executed=False,
            invalidated=INVALIDATED,
            source_scope_correction=SCOPE_CORRECTION,
            constructor_prerequisites_unchanged=plain(request.constructor_candidate.prerequisites),
        )
        value = PhysicalPreparation(
            request.identity,
            prepared.identity,
            volumes.topology.freeze(owned),
            admitted,
            volumes.topology.freeze(plain(provenance)),
            "",
        )
        result = replace(value, identity=digest(physical_record(value)))
        if observer is not None:
            observer("manufactured_physical_model_prepared", plain(result))
        return result
    except Exception as error:
        raise BridgeRejected(
            str(error),
            stage=partial["stage"],
            original=dict(
                type=type(error).__name__,
                reason=str(error),
                trial=plain(getattr(error, "trial", None)),
                partial=plain(getattr(error, "partial", None)),
            ),
            partial=partial,
        ) from error


def validate_physical(request, prepared, admitted):
    if type(admitted) is not PhysicalPreparation:
        raise ValueError("Owned complete manufactured physical preparation required")
    expected = prepare_physical(request, prepared, admitted.physical_input)
    if digest(expected) != digest(admitted):
        raise ValueError(
            "Changed complete manufactured physical owners, measures, inventories, "
            "provenance or seal"
        )
    return admitted


def require_cached_operators(_prepared):
    raise ValueError(
        "All old operators are invalidated; separate rebuild and independent "
        "qualification under the new geometry identity required"
    )
