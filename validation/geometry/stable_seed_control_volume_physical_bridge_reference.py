"""Independent full-array bridge checks from accepted constructor truth.

The saved constructor report supplies its already independently derived complete
partition. This worker does not construct it again. Polygon physical targets use
the frozen integer-grid/ear/Decimal reference, with no production imports.
"""

import argparse
import hashlib
import json
import math
import os
import traceback
from decimal import Decimal
from pathlib import Path

from validation.geometry import conservative_polygon_geometry_reference as polygons

# Importing this frozen reference installs an active production/science denial
# before importing either other reference. No constructor derive/evaluate call.
from validation.geometry import stable_seed_control_volumes_reference as constructor

LAW = "cells_fixed_seed_explicit_domain_manufactured_polygon_physical_bridge@1"
INPUT_KIND = "cells.fixed_seed_control_volume_physical_bridge_declaration@1"
PHYSICAL_LAW = "cells_polygon_physical_owners_passive_tissue@1"
PHYSICAL_KIND = "cells.polygon_physical_owners_tissue_preparation@1"
CONSTRUCTOR_REFERENCE_SHA256 = "643ea598f74c4a5d56753b5712d528937683cc35b57e6c904bc113bed1ac7813"
CONSTRUCTOR_SOURCE_REVIEW_SHA256 = (
    "97bd51e675c3840bbdc7a654604ee1d08c2e58972b177b03aa3bb878c1cea3d5"
)
POLYGON_REFERENCE_SHA256 = "5b3e621e75ebf1c539315e12ab213c7e0f6a019856db55121bf0f2f95acf06f8"
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
PHYSICAL_PINS = {
    "core/surface_tissue_spec.py": (
        "ca325e50b59a29ae25eaebc846cd126366e44c94ce0a931b833f26bb693db3aa"
    ),
    "models/surface_tissue.py": "a0c9993799b752913deaae7ccdab6780397e05d4e2ac30f66bd60de928eafe29",
    "numerics/surface_field.py": "6ae86409650223e5e81214ee2f57a5d6a0637c7d8ab2d3613e7dbc0d3dc26378",
    "numerics/surface_transport.py": (
        "f64cb3c0201be098793ce916ad65a19fd607b292c143c1b91950d03758f593d9"
    ),
    "processes/electrochemistry.py": (
        "e52dc29e3514268d538b7ceff293d32fd24d36ed3e9ef6242dc2906592c112f2"
    ),
}
INVALIDATED = [
    "all_original_and_constructor_cached_operators_inverses_and_Hodge_stores",
    "native_primal_dual_membrane_gap_profile_and_boundary_maps",
    "all_old_coordinate_dependent_areas_volumes_normals_and_capacitances",
    "environment_grid_bath_geometry_and_solver_caches",
    "native_initialization_trajectory_and_ordinary_loop_bindings",
]
SCOPE_CORRECTION = dict(
    five_failed_layout_owners=37,
    five_failed_layout_outside_owners=20,
    earlier_six_layout_panel_owners=50,
    earlier_passing_square_zero_owners=13,
    missing_envelope_cases=["caller-single-square-cache", "caller-single-hex-cache"],
    missing_envelope_origin="lattice_seeded_ring_and_centre_caller_caches",
    missing_envelopes_resolved=False,
    original_mesh_outcome="0/9 unchanged",
)
digest = constructor.digest
equal = constructor.typed_equal


def require(value, reason):
    if not value:
        raise ValueError(reason)


def same(actual, expected, label):
    require(equal(actual, expected), "Complete typed field/array differs: " + label)


def keys(value, expected, label):
    require(
        type(value) is dict and set(value) == set(expected), "Incomplete/extra fields: " + label
    )


def json_record(text, limit):
    require(
        type(text) is str and len(text.encode("utf-8")) <= limit,
        "Bounded original JSON evidence required",
    )

    def pairs(rows):
        result = {}
        for name, value in rows:
            require(name not in result, "Duplicate JSON evidence key")
            result[name] = value
        return result

    def constant(value):
        raise ValueError("Nonfinite JSON evidence: " + value)

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def evidence(request):
    keys(
        request,
        {
            "constructor_request",
            "constructor_candidate",
            "constructor_evidence",
            "declaration",
            "identity",
        },
        "request",
    )
    cv_request, cv, proof = (
        request[name]
        for name in ("constructor_request", "constructor_candidate", "constructor_evidence")
    )
    constructor.authenticate(cv_request)
    keys(proof, {"input_json", "report_json", "caller_acceptance"}, "constructor evidence")
    incoming = json_record(proof["input_json"], 32 * 2**20)
    report = json_record(proof["report_json"], 64 * 2**20)
    keys(incoming, {"request", "candidate"}, "original positive constructor input")
    same(incoming, dict(request=cv_request, candidate=cv), "original complete constructor input")
    input_sha = hashlib.sha256(proof["input_json"].encode("utf-8")).hexdigest()
    report_sha = hashlib.sha256(proof["report_json"].encode("utf-8")).hexdigest()
    accepted = proof["caller_acceptance"]
    keys(
        accepted,
        {"kind", "caller", "constructor_identity", "input_sha256", "report_sha256", "scope"},
        "explicit acceptance",
    )
    require(
        type(accepted["caller"]) is str and bool(accepted["caller"]),
        "Named caller acceptance required",
    )
    same(
        accepted,
        dict(
            kind="caller_accepts_complete_positive_constructor_reference@1",
            caller=accepted["caller"],
            constructor_identity=cv["identity"],
            input_sha256=input_sha,
            report_sha256=report_sha,
            scope="constructor_geometry_only_no_native_physical_or_operator_admission",
        ),
        "constructor acceptance",
    )
    require(
        report["status"] == "complete"
        and report["baseline_passed"] is True
        and report["candidate_passed"] is True
        and report["control_detected"] is False
        and report["baseline"]["passed"] is True
        and report["candidate"]["passed"] is True
        and report.get("runtime_capture_failed", False) is False,
        "Complete positive constructor report required",
    )
    require(
        constructor.verify(cv, report["reference"])["passed"],
        "Saved complete independent constructor truth disagrees",
    )
    truth = report["reference"]["candidate_fields"]
    n, v = len(truth["owners"]["retained_point_ids"]), len(truth["stored_geometry"]["vertices_m"])
    same(
        report["reference"]["counts"],
        dict(
            seeds=n,
            domain_vertices=len(cv_request["declaration"]["domain"]["vertices_m"]),
            vertices=v,
            cells=n,
            edges=len(truth["connectivity"]["edges"]),
            cell_occurrences=len(truth["connectivity"]["occurrences"]),
            clip_events=n * (n - 1),
            scalar_events=2 * v + 3 * n + 1,
        ),
        "constructor evidence cardinalities",
    )
    runtime = report["runtime_origin"]
    require(
        runtime["input_sha256"] == input_sha
        and runtime["source_sha256"] == CONSTRUCTOR_REFERENCE_SHA256
        and runtime["files"].get(runtime["source"]) == CONSTRUCTOR_REFERENCE_SHA256
        and runtime["production_and_scientific_imports_denied"] is True
        and runtime["production_or_scientific_modules_loaded"] == []
        and runtime["file_errors"] == {}
        and runtime["mapped_file_errors"] == []
        and type(runtime["pid"]) is int
        and type(runtime["parent_pid"]) is int
        and runtime["pid"] > 0
        and runtime["parent_pid"] > 0
        and runtime["pid"] != runtime["parent_pid"],
        "Independent constructor runtime/source/input provenance required",
    )
    same(
        request["identity"],
        digest([LAW, cv_request, cv, proof, request["declaration"]]),
        "request seal",
    )
    summary = dict(
        constructor_identity=cv["identity"],
        input_sha256=input_sha,
        report_sha256=report_sha,
        caller_acceptance_digest=digest(accepted),
        reference_source_sha256=CONSTRUCTOR_REFERENCE_SHA256,
        independent_complete_constructor_arrays_accepted_by_caller=True,
        public_hash_consistency_alone_is_scientific_review=False,
        constructor_source_review_sha256=CONSTRUCTOR_SOURCE_REVIEW_SHA256,
    )
    return truth, summary


def declaration(request, truth, accepted):
    value = request["declaration"]
    keys(
        value,
        {"kind", "opted_in_law", "domain_selection", "extrusion", "operator_policy", "scope"},
        "bridge declaration",
    )
    same(
        {key: value[key] for key in ("kind", "opted_in_law", "scope", "operator_policy")},
        dict(
            kind=INPUT_KIND,
            opted_in_law=LAW,
            scope="manufactured_polygon_preparation_not_native_geometry_equivalence",
            operator_policy=dict(
                kind="invalidate_all_and_rebuild_under_new_geometry_identity@1",
                provided_cached_operators=None,
            ),
        ),
        "new law and stale cache refusal",
    )
    domain = value["domain_selection"]
    keys(
        domain,
        {
            "kind",
            "selected_domain",
            "caller",
            "document_sha256",
            "purpose",
            "native_tissue_or_bath_equivalence",
        },
        "fresh domain",
    )
    require(
        type(domain["caller"]) is str and bool(domain["caller"]), "Named domain selector required"
    )
    sha = domain["document_sha256"]
    require(
        type(sha) is str and len(sha) == 64 and all(c in "0123456789abcdef" for c in sha),
        "Domain document hash required",
    )
    same(
        domain,
        dict(
            kind="fresh_explicit_caller_domain_selection@1",
            selected_domain=request["constructor_request"]["declaration"]["domain"],
            caller=domain["caller"],
            document_sha256=sha,
            purpose="manufactured_prismatic_partition_geometry_only",
            native_tissue_or_bath_equivalence=False,
        ),
        "complete explicit selected domain",
    )
    ext = value["extrusion"]
    keys(
        ext,
        {
            "height_m",
            "thickness_m",
            "baths",
            "bath_assignment",
            "axial_caps",
            "units",
            "cell_policy",
            "boundary_partner_policy",
        },
        "explicit extrusion",
    )
    same(
        ext["units"],
        dict(coordinates="m", height="m", thickness="m", area="m2", volume="m3"),
        "SI units",
    )
    same(ext["axial_caps"], "sealed_no_transport@1", "sealed axial caps")
    same(ext["cell_policy"], "one_manufactured_cell_per_retained_seed_no_merge", "cell policy")
    same(
        ext["boundary_partner_policy"],
        "conservative_self_partner_with_explicit_bath@1",
        "boundary partner translation",
    )
    for number in (
        ext["height_m"],
        ext["thickness_m"],
        *(row["volume_m3"] for row in ext["baths"]),
    ):
        require(
            type(number) in (int, float)
            and (type(number) is not int or abs(number) <= 2**53)
            and math.isfinite(number)
            and number > 0,
            "Positive finite explicit binary64 measure required",
        )
    names = truth["connectivity"]["vertices"]
    seeds = truth["owners"]["retained_point_ids"]
    raw = dict(
        source=dict(
            kind="declared_polygon_complex@1",
            generator=LAW,
            recipe=dict(
                bridge_request_identity=request["identity"],
                constructor_request_identity=request["constructor_request"]["identity"],
                constructor_identity=request["constructor_candidate"]["identity"],
                constructor_evidence=accepted,
                caller_domain_selection=domain,
                cell_policy=ext["cell_policy"],
                boundary_partner_policy=ext["boundary_partner_policy"],
                coordinate_policy="constructor_shared_binary64_vertices_recompute_all_metrics@1",
                native_equivalence=False,
            ),
            generation_coverage=False,
        ),
        vertices=[
            dict(id=name, xy_m=point)
            for name, point in zip(names, truth["stored_geometry"]["vertices_m"], strict=True)
        ],
        source_cells=[
            dict(id=name, vertex_ids=[names[i] for i in ring])
            for name, ring in zip(seeds, truth["stored_geometry"]["cells"], strict=True)
        ],
        cell_groups=[dict(id=name, source_cell_ids=[name]) for name in seeds],
        height_m=float(ext["height_m"]),
        thickness_m=float(ext["thickness_m"]),
        baths=[dict(row, volume_m3=float(row["volume_m3"])) for row in ext["baths"]],
        bath_assignment=ext["bath_assignment"],
        axial_caps=ext["axial_caps"],
        units=ext["units"],
    )
    return raw


def topology(raw, cv):
    """Enumerate independent directed owner axes, never using outgoing indices."""
    incidence = {}
    for owner, cell in enumerate(raw["source_cells"]):
        for local, (a, b) in enumerate(polygons._edges(cell["vertex_ids"])):
            incidence.setdefault(tuple(sorted((a, b))), []).append((owner, local, a, b))
    edges, membranes, contacts = [], [], []
    for ei, (pair, owners) in enumerate(incidence.items()):
        eid = "edge-" + polygons._hash(list(pair))
        mids = [
            "membrane-" + polygons._hash([raw["source_cells"][owner]["id"], a, b])
            for owner, _, a, b in owners
        ]
        for i, (owner, local, a, b) in enumerate(owners):
            membranes.append(
                dict(
                    id=mids[i],
                    cell_id=raw["source_cells"][owner]["id"],
                    edge_id=eid,
                    vertex_ids=[a, b],
                    partner_id=mids[1 - i] if len(mids) == 2 else mids[i],
                    local=local,
                    edge=ei,
                )
            )
        ci = None
        if len(owners) == 2:
            ci = len(contacts)
            contacts.append(
                dict(
                    id="contact-" + polygons._hash(list(pair)),
                    edge_id=eid,
                    membrane_ids=mids,
                    sender=raw["source_cells"][owners[0][0]]["id"],
                    receiver=raw["source_cells"][owners[1][0]]["id"],
                )
            )
        edges.append(
            dict(
                id=eid,
                vertex_ids=list(pair),
                cell_ids=[raw["source_cells"][owner]["id"] for owner, _, _, _ in owners],
                membrane_ids=mids,
                contact=ci,
            )
        )
    half = {(row["cell_id"], tuple(row["vertex_ids"])): i for i, row in enumerate(membranes)}
    edge_index = {tuple(row["vertex_ids"]): i for i, row in enumerate(edges)}
    mid_index = {row["id"]: i for i, row in enumerate(membranes)}
    names, seeds = cv["connectivity"]["vertices"], cv["owners"]["retained_point_ids"]
    mapped = dict(
        vertices=[
            dict(constructor_vertex=i, constructor_id=name, geometry_vertex=i, geometry_id=name)
            for i, name in enumerate(names)
        ],
        cells=[
            dict(
                constructor_cell=i,
                retained_seed_id=name,
                physical_cell=i,
                physical_cell_id=name,
                constructor_ring=cv["stored_geometry"]["cells"][i],
                geometry_ring=raw["source_cells"][i]["vertex_ids"],
            )
            for i, name in enumerate(seeds)
        ],
        edges=[],
        occurrences=[],
        constructor_local_edge_convention="previous_vertex_to_current_vertex",
        geometry_local_edge_convention="current_vertex_to_next_vertex",
        canonical_edge_policy="constructor_numeric_indices_to_geometry_lexical_ids_by_endpoints",
        boundary_partner_policy="caller_declared_None_to_self_with_explicit_bath",
        cell_merges_performed=False,
        nearest_midpoint_mapping_used=False,
    )
    for oi, occurrence in enumerate(cv["connectivity"]["occurrences"]):
        owner = occurrence["owner"]
        directed = [names[i] for i in occurrence["directed"]]
        mi = half[(seeds[owner], tuple(directed))]
        membrane = membranes[mi]
        partner = mid_index[membrane["partner_id"]]
        mapped["occurrences"].append(
            dict(
                constructor_occurrence=oi,
                owner_index=owner,
                owner_id=seeds[owner],
                constructor_local_edge=occurrence["local_edge"],
                constructor_edge=occurrence["edge"],
                constructor_directed_vertices=occurrence["directed"],
                directed_vertex_ids=directed,
                geometry_local_edge=membrane["local"],
                geometry_edge=membrane["edge"],
                geometry_edge_id=membrane["edge_id"],
                geometry_membrane=mi,
                geometry_membrane_id=membrane["id"],
                constructor_partner_occurrence=cv["connectivity"]["partners"][oi],
                geometry_partner_membrane=partner,
                geometry_partner_membrane_id=membrane["partner_id"],
                boundary_none_to_self_translation=partner == mi,
            )
        )
    for i, (a, b) in enumerate(cv["connectivity"]["edges"]):
        pair = [names[a], names[b]]
        ei = edge_index[tuple(sorted(pair))]
        row = edges[ei]
        occurrences = cv["connectivity"]["edge_occurrences"][i]
        mapped["edges"].append(
            dict(
                constructor_edge=i,
                constructor_directed_vertices=[a, b],
                geometry_edge=ei,
                geometry_edge_id=row["id"],
                geometry_vertex_ids=row["vertex_ids"],
                canonical_direction=1 if pair == row["vertex_ids"] else -1,
                constructor_occurrences=occurrences,
                geometry_membranes=[
                    mapped["occurrences"][j]["geometry_membrane"] for j in occurrences
                ],
                geometry_membrane_ids=[
                    mapped["occurrences"][j]["geometry_membrane_id"] for j in occurrences
                ],
                geometry_contact=row["contact"],
                geometry_contact_id=None
                if row["contact"] is None
                else contacts[row["contact"]]["id"],
            )
        )
    return dict(edges=edges, membranes=membranes, contacts=contacts, owner_maps=mapped)


def add(a, b):
    n, d = polygons._pair(a)
    m, e = polygons._pair(b)
    return polygons._ratio(n * e + m * d, d * e)


def neg(a):
    n, d = polygons._pair(a)
    return polygons._ratio(-n, d)


def absolute(a):
    n, d = polygons._pair(a)
    return polygons._ratio(abs(n), d)


def total(rows):
    result = polygons._ratio(0)
    for value in rows:
        result = add(result, value)
    return result


def projected_edge(row):
    values = {}
    for name in ("area_m2", "tangent_x", "tangent_y"):
        value = float(Decimal(row["values_decimal"][name]))
        require(
            polygons._sqrt_rounding_cell(value, row["squared_targets"][name]),
            "Independent projection not resolved",
        )
        require(
            value == 0 or (value > 0) == (row["signs"].get(name, 1) > 0),
            "Independent projection sign",
        )
        values[name] = value
    return values


def conservation(request, raw, primary, axes):
    points = {row["id"]: [polygons._float_ratio(v) for v in row["xy_m"]] for row in raw["vertices"]}
    target_edges = {tuple(row["vertex_ids"]): row for row in primary["edges"]}
    target_cells = {row["id"]: row for row in primary["cells"]}
    height = polygons._float_ratio(raw["height_m"])
    domain = request["constructor_request"]["declaration"]["domain"]["vertices_m"]
    scale = max(float(v).as_integer_ratio()[1] for p in domain for v in p)
    integer_points = [
        tuple(n * (scale // d) for n, d in (float(v).as_integer_ratio() for v in point))
        for point in domain
    ]
    domain_area = polygons._polygon(integer_points, scale)["area"]
    cells = []
    for cell in raw["source_cells"]:
        area = target_cells[cell["id"]]["exact_ratios"]["area_m2"]
        volume = polygons._mul(area, height)
        exact, rounded = [], []
        for a, b in polygons._edges(cell["vertex_ids"]):
            delta = [add(y, neg(x)) for x, y in zip(points[a], points[b], strict=True)]
            exact.append([polygons._mul(delta[1], height), neg(polygons._mul(delta[0], height))])
            pair = tuple(sorted((a, b)))
            projected = projected_edge(target_edges[pair])
            direction = 1 if (a, b) == pair else -1
            normal = [direction * projected["tangent_y"], direction * (-projected["tangent_x"])]
            rounded.append(
                [
                    polygons._mul(
                        polygons._float_ratio(v), polygons._float_ratio(projected["area_m2"])
                    )
                    for v in normal
                ]
            )
        sums = [total(row[i] for row in rounded) for i in (0, 1)]
        bounds = [
            total(absolute(add(b[i], neg(a[i]))) for a, b in zip(exact, rounded, strict=True))
            for i in (0, 1)
        ]
        require(
            all(int(total(row[i] for row in exact)["numerator"]) == 0 for i in (0, 1)),
            "Independent exact side-area closure",
        )
        require(
            all(
                polygons._pair(add(limit, neg(absolute(value))))[0] >= 0
                for limit, value in zip(bounds, sums, strict=True)
            ),
            "Independent normal-area rounding bound",
        )
        cells.append(
            dict(
                id=cell["id"],
                area_exact=area,
                volume_exact=volume,
                volume_pL_exact=polygons._mul(volume, polygons._ratio(10**15)),
                side_area_normals_exact=exact,
                exact_side_area_normal_sum=[polygons._ratio(0), polygons._ratio(0)],
                rounded_normal_times_area_sum=sums,
                rounded_product_absolute_error_bound=bounds,
            )
        )
    area_sum = total(row["area_exact"] for row in cells)
    same(area_sum, domain_area, "independent area partition")
    return dict(
        cells=cells,
        domain_area_exact=domain_area,
        area_sum_exact=area_sum,
        area_defect_exact=polygons._ratio(0),
        volume_sum_exact=polygons._mul(area_sum, height),
        domain_extruded_volume_exact=polygons._mul(domain_area, height),
        volume_defect_exact=polygons._ratio(0),
        membrane_incidence_column_sums=[0] * len(axes["membranes"]),
        contact_incidence_column_sums=[0] * len(axes["contacts"]),
        contacts_count_shared_interfaces_once=True,
        axial_caps="sealed_no_transport@1",
        rounded_unit_normal_times_area_exact_closure_claimed=False,
        rounding_bound_basis=(
            "fresh_geometry_projection_errors; independent reference must derive its own bound"
        ),
        inventories_rescaled=False,
        trajectory_conservation_claimed=False,
    )


def geometry_provenance(request, accepted):
    return dict(
        kind="cells.fixed_seed_manufactured_geometry_preparation@1",
        law=LAW,
        constructor_evidence=accepted,
        declared_domain_selection=request["declaration"]["domain_selection"],
        scope_correction=SCOPE_CORRECTION,
        source_pins=SOURCE_PINS,
        measures_recomputed_from_shared_binary64_coordinates=True,
        constructor_cached_measures_used_as_physical_authority=False,
        one_physical_cell_per_retained_seed=True,
        geometry_law="cells_conforming_polygon_physical_owners@1",
        physical_bridge_law=PHYSICAL_LAW,
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
        constructor_prerequisites_unchanged=request["constructor_candidate"]["prerequisites"],
    )


def derive(request, physical_input, partial):
    for module, pin in (
        (constructor, CONSTRUCTOR_REFERENCE_SHA256),
        (polygons, POLYGON_REFERENCE_SHA256),
    ):
        require(
            hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() == pin,
            "Changed independent reference source",
        )
    partial["stage"] = "accepted_complete_constructor_evidence"
    cv, accepted = evidence(request)
    raw = declaration(request, cv, accepted)
    partial.update(stage="independent_polygon_measures", polygon_input=raw)
    primary = polygons.evaluate(raw, refinement=1)
    refined = polygons.evaluate(raw, refinement=2)
    axes = topology(raw, cv)
    expected_conservation = conservation(request, raw, primary, axes)
    return dict(
        polygon_input=raw,
        primary=primary,
        refined=refined,
        axes=axes,
        conservation=expected_conservation,
        provenance=geometry_provenance(request, accepted),
        physical_input=physical_input,
        constructor_geometry_replayed=False,
        new_polygon_reference_derivations=2,
        accepted_constructor_reference=accepted,
    )


def certificate_fields(value, *, tangent=False):
    require(type(value) is dict, "Complete certificate object required")
    extra = {"sign"} if tangent else set()
    expected = (
        {"kind", "exact"}
        if value.get("kind") == "correctly_rounded_binary_rational"
        else {"kind", "lower", "upper", "precision_bits", "radicand"}
    )
    keys(value, expected | extra, "metric certificate")
    if "precision_bits" in value:
        require(
            type(value["precision_bits"]) is int
            and value["precision_bits"] in (80, 160, 320, 640, 1280, 2560, 5120, 8192),
            "Declared bounded interval precision",
        )
    for field in ("exact", "lower", "upper", "radicand"):
        if field in value:
            keys(value[field], {"numerator", "denominator"}, "canonical rational certificate")
            same(
                value[field],
                polygons._ratio(*polygons._pair(value[field])),
                "canonical reduced rational",
            )


def complete_vector_axes(geometry):
    for family, fields in (
        ("cells", ("centroid_m",)),
        ("edges", ("midpoint_m", "normal_xy", "tangent_xy")),
        ("membranes", ("normal_xy", "tangent_xy")),
        ("contacts", ("normal_xy",)),
    ):
        for row in geometry[family]:
            for field in fields:
                require(
                    type(row[field]) is list and len(row[field]) == 2,
                    "Exact two-component geometry vector required: " + field,
                )


def complete_permeability_species(request, model):
    species = {row["id"] for row in request["physics"]["species"]}
    for family in ("membranes", "junctions"):
        for row in model[family]:
            keys(
                row["permeability_m_per_s"],
                species,
                "Complete exact permeability species axis: " + family,
            )


def geometry_fields(g, truth):
    keys(
        g,
        {
            "kind",
            "law",
            "request_identity",
            "source",
            "units",
            "height_m",
            "thickness_m",
            "axial_caps",
            "vertices",
            "physical_vertex_ids",
            "source_only_vertex_ids",
            "source_cells",
            "cell_groups",
            "cells",
            "edges",
            "membranes",
            "contacts",
            "baths",
            "owner_axis",
            "membrane_incidence",
            "contact_incidence",
            "geometry_checks",
            "measure_policy",
            "contact_policy",
            "bath_volume_policy",
            "thickness_policy",
            "arithmetic_helper_sha256",
            "candidate_geometry_and_owner_admission",
            "physical_model_prepared",
            "native_equivalence",
            "B09_admission_inherited",
            "biological_calibration",
            "scientific_qualification_inherited",
            "conservation_scope",
        },
        "complete conservative geometry",
    )
    complete_vector_axes(g)
    raw, axes = truth["polygon_input"], truth["axes"]
    metadata = dict(
        kind="cells.conforming_polygon_physical_owner_binding@1",
        law="cells_conforming_polygon_physical_owners@1",
        source=raw["source"],
        axial_caps="sealed_no_transport@1",
        measure_policy="exact_polygon_area_times_uniform_extrusion_height@1",
        contact_policy="one_shared_edge_surface_with_reciprocal_half_membranes@1",
        bath_volume_policy="explicit_physical_volume_no_geometric_exterior_tessellation@1",
        thickness_policy="zero_volume_interface_with_explicit_constitutive_path_length@1",
        arithmetic_helper_sha256="c9fab4f34aa9166711431844f2af72eb6b8fe4873154bfe01dfce3f656326958",
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
    same({name: g[name] for name in metadata}, metadata, "geometry policies and admission scope")
    for name in (
        "source",
        "units",
        "height_m",
        "thickness_m",
        "axial_caps",
        "vertices",
        "source_cells",
        "cell_groups",
        "baths",
    ):
        same(g[name], raw[name], "typed geometric input " + name)
    for family in ("edges", "membranes", "contacts"):
        same(
            [row["id"] for row in g[family]],
            [row["id"] for row in axes[family]],
            "independent ordered " + family,
        )
    for i, cell in enumerate(g["cells"]):
        keys(
            cell,
            {
                "id",
                "vertex_ids",
                "source_cell_ids",
                "area_m2",
                "volume_m3",
                "centroid_m",
                "membrane_ids",
                "certificates",
            },
            "cell",
        )
        same(
            cell["vertex_ids"], raw["source_cells"][i]["vertex_ids"], "directed singleton cell ring"
        )
        finite_binary64([cell["area_m2"], cell["volume_m3"], *cell["centroid_m"]], "cell measures")
        keys(cell["certificates"], {"area", "volume", "centroid"}, "cell certificates")
        require(len(cell["certificates"]["centroid"]) == 2, "Centroid certificate axis")
        for cert in (
            cell["certificates"]["area"],
            cell["certificates"]["volume"],
            *cell["certificates"]["centroid"],
        ):
            certificate_fields(cert)
    for edge in g["edges"]:
        keys(
            edge,
            {
                "id",
                "vertex_ids",
                "cell_ids",
                "membrane_ids",
                "bath_id",
                "length_m",
                "area_m2",
                "midpoint_m",
                "tangent_xy",
                "normal_xy",
                "certificates",
            },
            "edge",
        )
        keys(edge["certificates"], {"length", "area", "midpoint", "tangent"}, "edge certificates")
        finite_binary64(
            [
                edge["length_m"],
                edge["area_m2"],
                *edge["midpoint_m"],
                *edge["normal_xy"],
                *edge["tangent_xy"],
            ],
            "edge measures",
        )
        require(
            len(edge["certificates"]["midpoint"]) == len(edge["certificates"]["tangent"]) == 2,
            "Edge certificate axes",
        )
        for cert in (
            edge["certificates"]["length"],
            edge["certificates"]["area"],
            *edge["certificates"]["midpoint"],
        ):
            certificate_fields(cert)
        for cert in edge["certificates"]["tangent"]:
            certificate_fields(cert, tangent=True)
    for row in g["membranes"]:
        keys(
            row,
            {
                "id",
                "cell_id",
                "bath_id",
                "edge_id",
                "vertex_ids",
                "area_m2",
                "thickness_m",
                "normal_xy",
                "tangent_xy",
                "partner_id",
            },
            "membrane",
        )
        finite_binary64(
            [row["area_m2"], row["thickness_m"], *row["normal_xy"], *row["tangent_xy"]],
            "membrane measures",
        )
    for row in g["contacts"]:
        keys(
            row,
            {
                "id",
                "edge_id",
                "membrane_ids",
                "sender",
                "receiver",
                "area_m2",
                "normal_xy",
                "vertex_ids",
            },
            "contact",
        )
        finite_binary64([row["area_m2"], *row["normal_xy"]], "contact measures")
    same(
        g["geometry_checks"],
        dict(
            source_complex_validated=True,
            physical_complex_validated=True,
            shared_edges_exact_and_opposite=True,
            source_area_exact=truth["conservation"]["area_sum_exact"],
            merged_area_exact=truth["conservation"]["area_sum_exact"],
            source_edges=len(axes["edges"]),
            physical_edges=len(axes["edges"]),
            merge_internal_edges_removed=0,
            each_source_cell_owned_once=True,
        ),
        "complete geometry checks",
    )


def physical_provenance(request, prepared, raw):
    return dict(
        kind="cells.fixed_seed_manufactured_physical_preparation@1",
        law=LAW,
        geometry_identity=prepared["geometry_binding"]["identity"],
        constructor_identity=request["constructor_candidate"]["identity"],
        caller_physical_input_digest=digest(raw),
        existing_physical_bridge_law=PHYSICAL_LAW,
        physical_admission_source_sha256=PHYSICAL_PINS,
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
        constructor_prerequisites_unchanged=request["constructor_candidate"]["prerequisites"],
    )


def finite_binary64(values, label):
    require(
        all(type(value) is float and math.isfinite(value) for value in values),
        "Complete finite binary64 scalars: " + label,
    )


def physical_fields(request, prepared, raw, admitted, g, truth):
    keys(
        admitted,
        {
            "request_identity",
            "geometry_preparation_identity",
            "physical_input",
            "physical_preparation",
            "provenance",
            "identity",
        },
        "physical preparation",
    )
    same(admitted["request_identity"], request["identity"], "physical request identity")
    same(
        admitted["geometry_preparation_identity"],
        prepared["identity"],
        "new geometry preparation identity",
    )
    same(admitted["physical_input"], raw, "all caller physical inventories and coefficients")
    same(
        admitted["provenance"],
        physical_provenance(request, prepared, raw),
        "complete physical bridge provenance",
    )
    inner = admitted["physical_preparation"]
    keys(inner, {"definition_json", "provenance_json", "identity"}, "existing physical preparation")
    definition = json_record(inner["definition_json"], 16 * 2**20)
    provenance = json_record(inner["provenance_json"], 16 * 2**20)
    keys(
        definition,
        {"schema_version", "model", "experiment", "execution"},
        "complete physical definition",
    )
    same(definition["schema_version"], 1, "physical schema version")
    model = definition["model"]
    complete_permeability_species(raw, model)
    keys(
        model,
        {
            "id",
            "species",
            "temperature_K",
            "cells",
            "extracellular",
            "membranes",
            "junctions",
            "faces",
            "closure",
        },
        "complete physical model",
    )
    for field in ("species", "temperature_K", "closure"):
        same(model[field], raw["physics"][field], "typed physical " + field)
    same(definition["execution"], raw["execution"], "complete typed execution declaration")
    keys(definition["experiment"], set(raw["experiment"]), "complete experiment fields")
    for field in ("end_time", "observation_times"):
        same(
            definition["experiment"][field],
            raw["experiment"][field],
            "complete typed experiment " + field,
        )
    for family, key in (("membrane_controls", "membrane_id"), ("junction_controls", "junction_id")):
        same(
            {row[key]: row for row in definition["experiment"][family]},
            {row[key]: row for row in raw["experiment"][family]},
            "complete typed controls by owner ID",
        )
    inventory = {
        "id",
        "initial_amount_fmol",
        "initial_charge_C",
        "fixed_charge_equivalent_fmol",
        "volume_pL",
    }
    for row in model["cells"]:
        keys(row, inventory, "physical cell")
        finite_binary64([row["volume_pL"]], "physical cell volume")
    for row in model["extracellular"]:
        keys(row, inventory | {"reservoir", "boundary_potential_V"}, "physical bath")
        finite_binary64([row["volume_pL"]], "physical bath volume")
    for row in model["membranes"]:
        keys(
            row,
            {"id", "inside", "outside", "area_m2", "capacitance_F", "permeability_m_per_s", "law"},
            "physical membrane",
        )
        finite_binary64(
            [row["area_m2"], row["capacitance_F"], *row["permeability_m_per_s"].values()],
            "physical membrane measures",
        )
    for row in model["junctions"]:
        keys(
            row,
            {"id", "sender", "receiver", "area_m2", "permeability_m_per_s", "law"},
            "physical contact",
        )
        finite_binary64(
            [row["area_m2"], *row["permeability_m_per_s"].values()], "physical contact measures"
        )
    for family, field in (("cells", "cells"), ("baths", "extracellular")):
        supplied = {row["id"]: row for row in raw["physics"][family]}
        for row in model[field]:
            for key in ("initial_amount_fmol", "initial_charge_C", "fixed_charge_equivalent_fmol"):
                same(
                    row[key],
                    supplied[row["id"]][key],
                    "typed caller inventory/charge " + row["id"] + "/" + key,
                )
            if family == "baths":
                for key in ("reservoir", "boundary_potential_V"):
                    same(row[key], supplied[row["id"]][key], "typed bath boundary declaration")
    checked = polygons.compare_physical(g, raw, definition, truth["primary"], truth["refined"])
    expected = dict(
        kind=PHYSICAL_KIND,
        bridge_id=PHYSICAL_LAW,
        geometry_identity=prepared["geometry_binding"]["identity"],
        geometry_law="cells_conforming_polygon_physical_owners@1",
        geometry_request=dict(
            kind="cells.conforming_polygon_physical_owner_request@1",
            law="cells_conforming_polygon_physical_owners@1",
            declaration=truth["polygon_input"],
        ),
        geometry=g,
        request=raw,
        definition_sha256=polygons._hash(definition),
        unit_policy=dict(
            cell_volume="Exact polygon extrusion rational converted to pL before rounding",
            bath_volume="Explicit binary64 physical m3 converted to pL before rounding",
            membrane_area="One exact shared-edge length times uniform height, rounded once",
            capacitance="Exact geometric area times declared specific capacitance, rounded once",
            permeability="Explicit diffusivity divided by explicit membrane thickness",
            contacts="One physical interface surface per exact shared edge; no doubled area",
            axial_caps="sealed_no_transport@1",
        ),
        exact_owner_axes=dict(
            cells=[row["id"] for row in g["cells"]],
            baths=[row["id"] for row in g["baths"]],
            membranes=[row["id"] for row in g["membranes"]],
            contacts=[row["id"] for row in g["contacts"]],
        ),
        inventories_rescaled=False,
        physical_model_prepared=True,
        physical_admission="Existing resolved_tissue@1 parser and initial definition checks",
        physical_admission_source_sha256=PHYSICAL_PINS,
        native_equivalence=False,
        B09_admission_inherited=False,
        scientific_qualification_inherited=False,
        solver_trajectory_executed=False,
    )
    same(provenance, expected, "all existing physical provenance fields")
    same(
        inner["identity"],
        polygons._hash(dict(definition=definition, provenance=provenance)),
        "existing physical seal",
    )
    same(
        admitted["identity"],
        digest(
            [LAW]
            + [
                admitted[key]
                for key in (
                    "request_identity",
                    "geometry_preparation_identity",
                    "physical_input",
                    "physical_preparation",
                    "provenance",
                )
            ]
        ),
        "physical bridge seal",
    )
    return checked


def verify(request, candidate, truth):
    partial = dict(stage="complete_geometry_fields")
    try:
        keys(candidate, {"geometry_preparation", "physical_preparation"}, "candidate snapshot")
        prepared = candidate["geometry_preparation"]
        keys(
            prepared,
            {
                "request_identity",
                "geometry_request",
                "geometry_binding",
                "owner_maps",
                "conservation",
                "provenance",
                "identity",
            },
            "geometry preparation",
        )
        same(prepared["request_identity"], request["identity"], "geometry request identity")
        raw = truth["polygon_input"]
        expected_request = dict(
            kind="cells.conforming_polygon_physical_owner_request@1",
            law="cells_conforming_polygon_physical_owners@1",
            declaration=raw,
        )
        same(
            prepared["geometry_request"],
            dict(
                declaration_json=json.dumps(
                    raw, sort_keys=True, separators=(",", ":"), allow_nan=False
                ),
                upstream=[],
                identity=polygons._hash(expected_request),
            ),
            "complete polygon request",
        )
        bound = prepared["geometry_binding"]
        keys(bound, {"request_identity", "geometry_json", "identity"}, "geometry binding")
        same(
            bound["request_identity"],
            prepared["geometry_request"]["identity"],
            "polygon binding identity",
        )
        g = json_record(bound["geometry_json"], 16 * 2**20)
        same(bound["identity"], polygons._hash(g), "complete conservative geometry seal")
        geometry_fields(g, truth)
        partial["stage"] = "independent_complete_polygon_arrays"
        checked = polygons.compare(raw, g, truth["primary"], truth["refined"])
        same(prepared["owner_maps"], truth["axes"]["owner_maps"], "all owner/index maps")
        same(
            prepared["conservation"],
            truth["conservation"],
            "all exact and rounded conservation arrays and independent bounds",
        )
        same(
            prepared["provenance"], truth["provenance"], "all geometry provenance and closed gates"
        )
        same(
            prepared["identity"],
            digest(
                [LAW]
                + [
                    prepared[key]
                    for key in (
                        "request_identity",
                        "geometry_request",
                        "geometry_binding",
                        "owner_maps",
                        "conservation",
                        "provenance",
                    )
                ]
            ),
            "geometry preparation seal",
        )
        partial["stage"] = "independent_complete_physical_arrays"
        raw_physical = truth["physical_input"]
        if raw_physical is None:
            same(candidate["physical_preparation"], None, "no implicit physical admission")
            checked_physical = None
        else:
            require(
                raw_physical["geometry_identity"] == bound["identity"],
                "Caller physical input targets a different geometry",
            )
            require(
                raw_physical["execution"]["backend"] == "cpu"
                and raw_physical["execution"]["precision"] == "float64"
                and raw_physical["execution"]["jit"] is False,
                "Bounded CPU physical preparation policy",
            )
            checked_physical = physical_fields(
                request, prepared, raw_physical, candidate["physical_preparation"], g, truth
            )
        return dict(
            passed=True,
            geometry=checked,
            physical=checked_physical,
            complete_owner_metric_evidence_inventory=True,
            source_scope_corrections_checked=True,
            independent_rounding_bounds=True,
            outgoing_selected_tolerance=False,
            native_equivalence=False,
            field_or_solver_executed_by_reference=False,
            trajectory_conservation_claimed=False,
        )
    except Exception as error:
        return dict(
            passed=False,
            partial=partial,
            type=type(error).__name__,
            reason=str(error),
            traceback=traceback.format_exc(),
        )


def evaluate(payload):
    partial = dict(stage="input")
    try:
        keys(
            payload,
            {"request", "physical_input", "candidate"}
            | ({"controls"} if "controls" in payload else set()),
            "reference input",
        )
        controls = payload.get("controls", [])
        require(
            type(controls) is list and len(controls) <= 64,
            "Bounded explicit output control panel required",
        )
        require(
            all(
                type(row) is dict
                and set(row) == {"name", "candidate"}
                and type(row["name"]) is str
                and bool(row["name"])
                for row in controls
            ),
            "Complete named controls required",
        )
        require(
            len({row["name"] for row in controls}) == len(controls), "Duplicate output control ID"
        )
        truth = derive(payload["request"], payload["physical_input"], partial)
        baseline = verify(payload["request"], payload["candidate"], truth)
        if not baseline["passed"]:
            return dict(
                status="baseline_failed",
                baseline_passed=False,
                candidate_passed=False,
                control_detected=False,
                baseline=baseline,
                controls=[],
                reference=truth,
                raw_partial=partial,
            )
        checked = [
            dict(name=row["name"], verification=verify(payload["request"], row["candidate"], truth))
            for row in controls
        ]
        return dict(
            status="complete",
            baseline_passed=True,
            candidate_passed=True,
            baseline=baseline,
            control_detected=bool(controls)
            and all(not row["verification"]["passed"] for row in checked),
            controls=checked,
            reference=truth,
            raw_partial=partial,
            constructor_geometry_replayed=False,
            numerical_trajectory_executed=False,
            native_equivalence=False,
        )
    except Exception as error:
        return dict(
            status="reference_failed",
            baseline_passed=False,
            candidate_passed=False,
            control_detected=False,
            controls=[],
            type=type(error).__name__,
            reason=str(error),
            traceback=traceback.format_exc(),
            raw_partial=partial,
        )


def runtime_inventory(input_path):
    result = constructor.runtime_inventory(input_path)
    result.update(
        source=str(Path(__file__).resolve()),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        constructor_geometry_replayed=False,
        polygon_reference_sha256=POLYGON_REFERENCE_SHA256,
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = json_record(args.input.read_text(), 128 * 2**20)
    report = evaluate(payload)
    try:
        report["runtime_origin"] = runtime_inventory(args.input)
        origin = report["runtime_origin"]
        if (
            origin["file_errors"]
            or origin["mapped_file_errors"]
            or origin["production_or_scientific_modules_loaded"]
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
    if not (
        report["baseline_passed"]
        and not report.get("runtime_capture_failed", False)
        and (report["control_detected"] if payload.get("controls") else report["candidate_passed"])
    ):
        raise SystemExit(2 if report["status"] == "baseline_failed" else 1)


if __name__ == "__main__":
    main()
