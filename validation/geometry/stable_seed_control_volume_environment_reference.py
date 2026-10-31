"""Independent integer-grid source correspondence; no finite-ECM admission.

Accepted bridge truth is checked without replaying its construction. Every new
index, boundary row and exact obstruction is derived before reading output.
"""

import argparse
import hashlib
import json
import os
import traceback
from pathlib import Path

from validation.geometry import stable_seed_control_volume_physical_bridge_reference as upstream

LAW = "cells_fixed_seed_environment_prerequisite_correspondence@1"
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
INVALIDATED = [
    "all_native_cell_to_environment_and_membrane_to_environment_indices",
    "all_environment_grid_volumes_boundaries_divergence_maps_and_operators",
    "all_bath_face_centroid_links_lengths_and_diffusion_stores",
    "all_native_initialization_ordinary_loop_and_solver_cache_bindings",
]
same, keys, require, digest = upstream.same, upstream.keys, upstream.require, upstream.digest
polygon = upstream.polygons


def complete_upstream_axes(incoming):
    """Close known bridge01 oracle gaps before accepting its saved truth."""
    candidate = incoming["candidate"]
    g = upstream.json_record(
        candidate["geometry_preparation"]["geometry_binding"]["geometry_json"], 16 * 2**20
    )
    for rows, fields in (
        (g["cells"], ("centroid_m",)),
        (g["edges"], ("midpoint_m", "tangent_xy", "normal_xy")),
        (g["membranes"], ("tangent_xy", "normal_xy")),
        (g["contacts"], ("normal_xy",)),
    ):
        for row in rows:
            for field in fields:
                require(
                    type(row[field]) is list and len(row[field]) == 2,
                    "Complete exact two-component upstream vector: " + field,
                )
    physical = candidate["physical_preparation"]
    require(physical is not None, "Complete physical bridge required")
    model = upstream.json_record(physical["physical_preparation"]["definition_json"], 16 * 2**20)[
        "model"
    ]
    species = {row["id"] for row in incoming["physical_input"]["physics"]["species"]}
    for family in ("membranes", "junctions"):
        for row in model[family]:
            require(
                type(row["permeability_m_per_s"]) is dict
                and set(row["permeability_m_per_s"]) == species,
                "Complete exact upstream permeability species axis",
            )


def accepted_source(request):
    require(
        hashlib.sha256(Path(upstream.__file__).read_bytes()).hexdigest() == BRIDGE_REFERENCE_SHA256,
        "Changed frozen independent bridge source",
    )
    keys(
        request,
        {
            "bridge_request",
            "geometry_preparation",
            "physical_preparation",
            "bridge_evidence",
            "declaration",
            "identity",
        },
        "complete environment request",
    )
    proof = request["bridge_evidence"]
    keys(
        proof,
        {"input_json", "report_json", "caller_acceptance"},
        "complete accepted bridge evidence",
    )
    incoming = upstream.json_record(proof["input_json"], 128 * 2**20)
    report = upstream.json_record(proof["report_json"], 128 * 2**20)
    geometry, physical = request["geometry_preparation"], request["physical_preparation"]
    expected_input = dict(
        request=request["bridge_request"],
        physical_input=physical["physical_input"],
        candidate=dict(geometry_preparation=geometry, physical_preparation=physical),
    )
    same(incoming, expected_input, "complete original positive bridge input")
    complete_upstream_axes(incoming)
    truth = report["reference"]
    constructor_truth, constructor_acceptance = upstream.evidence(incoming["request"])
    same(
        truth["polygon_input"],
        upstream.declaration(incoming["request"], constructor_truth, constructor_acceptance),
        "accepted constructor to bridge target link",
    )
    require(
        report["status"] == "complete"
        and report["baseline_passed"] is True
        and report["candidate_passed"] is True
        and report["control_detected"] is False
        and report["controls"] == []
        and report.get("runtime_capture_failed", False) is False,
        "Complete positive physical bridge report required",
    )
    require(
        upstream.verify(incoming["request"], incoming["candidate"], truth)["passed"],
        "Saved independent complete bridge truth disagrees",
    )
    require(
        incoming["physical_input"] is not None
        and report["baseline"]["physical"] is not None
        and report["baseline"]["passed"] is True
        and report["baseline"]["complete_owner_metric_evidence_inventory"] is True
        and report["baseline"]["field_or_solver_executed_by_reference"] is False,
        "Complete accepted physical baseline required",
    )
    g = upstream.json_record(geometry["geometry_binding"]["geometry_json"], 16 * 2**20)
    n, e, m, j, b = (len(g[key]) for key in ("cells", "edges", "membranes", "contacts", "baths"))
    species = len(physical["physical_input"]["physics"]["species"])
    require(
        len(report["baseline"]["geometry"]["full_precision_quantities"]) == 4 * n + 6 * e
        and len(report["baseline"]["physical"]["full_precision_quantities"])
        == n + b + (2 + species) * m + j,
        "Complete independent bridge scalar inventory required",
    )
    accepted = proof["caller_acceptance"]
    keys(
        accepted,
        {
            "kind",
            "caller",
            "bridge_request_identity",
            "geometry_preparation_identity",
            "physical_preparation_identity",
            "input_sha256",
            "report_sha256",
            "scope",
        },
        "caller acceptance",
    )
    input_sha = hashlib.sha256(proof["input_json"].encode("utf-8")).hexdigest()
    report_sha = hashlib.sha256(proof["report_json"].encode("utf-8")).hexdigest()
    require(
        type(accepted["caller"]) is str and bool(accepted["caller"]),
        "Named explicit caller required",
    )
    same(
        accepted,
        dict(
            kind="caller_accepts_complete_positive_manufactured_physical_bridge@1",
            caller=accepted["caller"],
            bridge_request_identity=request["bridge_request"]["identity"],
            geometry_preparation_identity=geometry["identity"],
            physical_preparation_identity=physical["identity"],
            input_sha256=input_sha,
            report_sha256=report_sha,
            scope="initial_manufactured_physical_bridge_only_no_ECM_or_native_environment_admission",
        ),
        "accepted scope and identities",
    )
    runtime = report["runtime_origin"]
    require(
        runtime["input_sha256"] == input_sha
        and runtime["source_sha256"] == BRIDGE_REFERENCE_SHA256
        and runtime["files"].get(runtime["source"]) == BRIDGE_REFERENCE_SHA256
        and runtime["production_and_scientific_imports_denied"] is True
        and runtime["production_or_scientific_modules_loaded"] == []
        and runtime["file_errors"] == {}
        and runtime["mapped_file_errors"] == []
        and type(runtime["pid"]) is int
        and type(runtime["parent_pid"]) is int
        and runtime["pid"] > 0
        and runtime["parent_pid"] > 0
        and runtime["pid"] != runtime["parent_pid"],
        "Actual independent bridge runtime origin required",
    )
    same(
        request["identity"],
        digest(
            [LAW]
            + [
                request[key]
                for key in (
                    "bridge_request",
                    "geometry_preparation",
                    "physical_preparation",
                    "bridge_evidence",
                    "declaration",
                )
            ]
        ),
        "full request seal",
    )
    summary = dict(
        input_sha256=input_sha,
        report_sha256=report_sha,
        caller_acceptance_digest=digest(accepted),
        reference_sha256=BRIDGE_REFERENCE_SHA256,
        complete_physical_bridge_accepted_by_caller=True,
        public_hash_consistency_alone_is_scientific_review=False,
    )
    return g, summary


def declaration(request, g):
    raw = request["declaration"]
    keys(
        raw,
        {
            "kind",
            "opted_in_law",
            "scope",
            "domain_selection",
            "baths",
            "membrane_baths",
            "outer_boundary",
            "operator_policy",
        },
        "explicit caller declaration",
    )
    same(raw["kind"], INPUT_KIND, "input kind")
    same(raw["opted_in_law"], LAW, "correspondence law")
    same(
        raw["scope"],
        "prerequisite_correspondence_only_no_finite_ECM_or_native_environment_admission",
        "correspondence-only scope",
    )
    same(
        raw["operator_policy"],
        dict(
            kind="invalidate_all_environment_indices_and_operators@1",
            provided_cached_operators=None,
        ),
        "stale-cache refusal",
    )
    selected = raw["domain_selection"]
    keys(
        selected,
        {"caller", "document_sha256", "selected_domain", "native_equivalence"},
        "fresh domain",
    )
    require(type(selected["caller"]) is str and bool(selected["caller"]), "Named domain selector")
    sha = selected["document_sha256"]
    require(
        type(sha) is str and len(sha) == 64 and all(c in "0123456789abcdef" for c in sha),
        "Caller domain declaration hash",
    )
    same(
        selected["selected_domain"],
        request["bridge_request"]["declaration"]["domain_selection"]["selected_domain"],
        "no domain extension",
    )
    same(selected["native_equivalence"], False, "no native claim")
    definition = upstream.json_record(
        request["physical_preparation"]["physical_preparation"]["definition_json"], 16 * 2**20
    )
    compartments = {row["id"]: row for row in definition["model"]["extracellular"]}
    expected_baths = {
        row["id"]: dict(
            id=row["id"],
            volume_m3=row["volume_m3"],
            reservoir=compartments[row["id"]]["reservoir"],
            boundary_potential_V=compartments[row["id"]]["boundary_potential_V"],
            geometry_role="declared_compartment_without_polygon_geometry@1",
        )
        for row in g["baths"]
    }
    expected_membranes = {
        row["id"]: dict(
            membrane_id=row["id"],
            cell_id=row["cell_id"],
            bath_id=row["bath_id"],
            directed_vertex_ids=row["vertex_ids"],
        )
        for row in g["membranes"]
    }
    expected_boundary = {
        row["id"]: dict(
            membrane_id=row["id"],
            cell_id=row["cell_id"],
            assigned_bath_id=row["bath_id"],
            directed_vertex_ids=row["vertex_ids"],
        )
        for row in g["membranes"]
        if row["partner_id"] == row["id"]
    }
    boundary = raw["outer_boundary"]
    keys(boundary, {"kind", "condition", "rows"}, "prospective boundary")
    same(boundary["kind"], "prospective_same_ring_ECM_boundary_not_admitted@1", "boundary scope")
    same(boundary["condition"], "sealed_no_transport@1", "caller boundary condition")
    for rows, key, expected in (
        (raw["baths"], "id", expected_baths),
        (raw["membrane_baths"], "membrane_id", expected_membranes),
        (boundary["rows"], "membrane_id", expected_boundary),
    ):
        require(type(rows) is list and len(rows) == len(expected), "Complete explicit caller axis")
        indexed = {row[key]: row for row in rows}
        require(len(indexed) == len(rows), "Duplicate caller rows")
        same(indexed, expected, "all explicit caller owners and selected boundary data")
    return raw, expected_baths


def derive(request, partial):
    partial["stage"] = "complete_accepted_source"
    g, accepted = accepted_source(request)
    raw, baths = declaration(request, g)
    partial["stage"] = "independent_integer_grid_ownership"
    scale = max(float(v).as_integer_ratio()[1] for row in g["vertices"] for v in row["xy_m"])
    points = {
        row["id"]: tuple(
            n * (scale // d) for n, d in (float(v).as_integer_ratio() for v in row["xy_m"])
        )
        for row in g["vertices"]
    }
    names = sorted(points, key=lambda name: (*points[name], name))
    number = {name: i for i, name in enumerate(names)}
    source_vertices = {row["id"]: i for i, row in enumerate(g["vertices"])}
    coordinates = [
        dict(
            index=i,
            vertex_id=name,
            xy_m=g["vertices"][source_vertices[name]]["xy_m"],
            source_vertex_index=source_vertices[name],
        )
        for i, name in enumerate(names)
    ]
    cell_ids = [row["id"] for row in g["cells"]]
    bath_ids = sorted(baths)
    owners = cell_ids + bath_ids
    owner_index = {name: i for i, name in enumerate(owners)}
    by_half = {
        (row["cell_id"], tuple(row["vertex_ids"])): (i, row) for i, row in enumerate(g["membranes"])
    }
    cells, halves = [], []
    for ci, cell in enumerate(g["cells"]):
        rotations = [
            cell["vertex_ids"][i:] + cell["vertex_ids"][:i] for i in range(len(cell["vertex_ids"]))
        ]
        ring = min(rotations, key=lambda row: tuple(number[name] for name in row))
        ids = []
        for local, pair in enumerate(polygon._edges(ring)):
            si, membrane = by_half[(cell["id"], pair)]
            ids.append(len(halves))
            halves.append(
                dict(
                    index=len(halves),
                    membrane_id=membrane["id"],
                    source_membrane_index=si,
                    cell_id=cell["id"],
                    cell_index=ci,
                    local_edge=local,
                    vertex_indices=[number[name] for name in pair],
                    bath_id=membrane["bath_id"],
                    bath_owner_index=owner_index[membrane["bath_id"]],
                )
            )
        cells.append(
            dict(
                index=ci,
                cell_id=cell["id"],
                vertex_indices=[number[name] for name in ring],
                membrane_indices=ids,
            )
        )
    edges = sorted({tuple(sorted(row["vertex_indices"])) for row in halves})
    edge_rows, boundary, direct = [], [], []
    h = polygon._float_ratio(g["height_m"])
    for ei, edge in enumerate(edges):
        selected = [row["index"] for row in halves if tuple(sorted(row["vertex_indices"])) == edge]
        require(len(selected) in (1, 2), "Independent one/two-owner edge axis")
        for i in selected:
            halves[i].update(edge_index=ei, partner_index=next((j for j in selected if j != i), i))
        row = dict(
            index=ei,
            vertex_indices=list(edge),
            membrane_indices=selected,
            cell_ids=[halves[i]["cell_id"] for i in selected],
            kind="direct_cell_cell" if len(selected) == 2 else "cell_owned_exterior",
        )
        edge_rows.append(row)
        if len(selected) == 2:
            direct.append(row)
        else:
            membrane = halves[selected[0]]
            a, b = (points[names[i]] for i in membrane["vertex_indices"])
            normal = [
                polygon._mul(polygon._ratio(b[1] - a[1], scale), h),
                polygon._mul(polygon._ratio(a[0] - b[0], scale), h),
            ]
            boundary.append(
                dict(
                    edge_index=ei,
                    membrane_index=membrane["index"],
                    cell_id=membrane["cell_id"],
                    assigned_bath_id=membrane["bath_id"],
                    vertex_indices=membrane["vertex_indices"],
                    selected_prospective_condition=raw["outer_boundary"]["condition"],
                    actual_polygon_owner_kind="cell",
                    exact_side_area_normal_xy_m2=normal,
                )
            )
    polygon._complex(points, g["cells"], scale)
    areas = [
        polygon._polygon([points[name] for name in row["vertex_ids"]], scale)["area"]
        for row in g["cells"]
    ]
    domain = raw["domain_selection"]["selected_domain"]["vertices_m"]
    # Use a separate common grid because an original domain corner need not be
    # the first stored vertex on a split outer cell edge.
    ds = max(float(v).as_integer_ratio()[1] for row in domain for v in row)
    dp = [
        tuple(n * (ds // d) for n, d in (float(v).as_integer_ratio() for v in row))
        for row in domain
    ]
    da = polygon._polygon(dp, ds)["area"]
    total = upstream.total(areas)
    same(total, da, "exact cell exhaustion of selected domain")
    volume = upstream.total(polygon._float_ratio(row["volume_m3"]) for row in raw["baths"])
    hn, hd = polygon._pair(h)
    required_area = polygon._mul(volume, polygon._ratio(hd, hn))
    bath_rows = [
        dict(
            baths[name],
            index=i,
            owner_index=owner_index[name],
            source_owner_index=g["owner_axis"].index(name),
        )
        for i, name in enumerate(bath_ids)
    ]
    indices = dict(
        vertices=coordinates,
        cells=cells,
        owner_axis=owners,
        baths=bath_rows,
        membranes=halves,
        edges=edge_rows,
        boundary=boundary,
        direct_cell_cell_interfaces=direct,
        membrane_incidence=[
            [int(name == row["bath_id"]) - int(name == row["cell_id"]) for row in halves]
            for name in owners
        ],
        contact_incidence=[
            [int(name == row["cell_ids"][1]) - int(name == row["cell_ids"][0]) for row in direct]
            for name in owners
        ],
        bath_bath_faces=[],
        bath_centroid_links=[],
        nearest_midpoint_or_native_grid_mapping_used=False,
    )
    witnesses = dict(
        domain_area_m2_exact=da,
        cell_area_m2_exact=areas,
        cell_area_sum_m2_exact=total,
        available_disjoint_bath_area_m2_exact=polygon._ratio(0),
        requested_bath_volume_m3_exact=volume,
        requested_bath_area_at_same_height_m2_exact=required_area,
        exact_bath_area_shortfall_m2=required_area,
        cell_owned_outer_boundary_edges=len(boundary),
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
        law=LAW,
        accepted_bridge_evidence=accepted,
        physical_bridge_identity=request["physical_preparation"]["identity"],
        geometry_preparation_identity=request["geometry_preparation"]["identity"],
        source_pins=SOURCE_PINS,
        scope_correction=upstream.SCOPE_CORRECTION,
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
    return dict(
        candidate_fields=dict(
            request_identity=request["identity"],
            indices=indices,
            witnesses=witnesses,
            provenance=provenance,
        ),
        exact_integer_grid_scale=str(scale),
        constructor_or_bridge_geometry_replayed=False,
        finite_ECM_geometry_constructed=False,
        field_or_solver_executed=False,
    )


def verify(candidate, truth):
    try:
        fields = truth["candidate_fields"]
        keys(candidate, set(fields) | {"identity"}, "complete correspondence fields")
        for name, value in fields.items():
            same(candidate[name], value, "all independent " + name)
        same(
            candidate["identity"],
            digest(
                [LAW]
                + [
                    candidate[key]
                    for key in ("request_identity", "indices", "witnesses", "provenance")
                ]
            ),
            "complete output seal",
        )
        return dict(
            passed=True,
            complete_owner_and_obstruction_arrays=True,
            finite_ECM_adapted=False,
            native_equivalence=False,
            numerical_tolerance_added=False,
        )
    except Exception as error:
        return dict(
            passed=False,
            type=type(error).__name__,
            reason=str(error),
            traceback=traceback.format_exc(),
        )


def evaluate(payload):
    partial = dict(stage="input")
    try:
        keys(
            payload,
            {"request", "candidate"} | ({"controls"} if "controls" in payload else set()),
            "environment reference input",
        )
        controls = payload.get("controls", [])
        require(type(controls) is list and len(controls) <= 64, "Bounded explicit controls")
        require(
            all(
                type(row) is dict
                and set(row) == {"name", "candidate"}
                and type(row["name"]) is str
                and bool(row["name"])
                for row in controls
            ),
            "Complete named control rows",
        )
        require(len({row["name"] for row in controls}) == len(controls), "Distinct control IDs")
        truth = derive(payload["request"], partial)
        baseline = verify(payload["candidate"], truth)
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
            dict(name=row["name"], verification=verify(row["candidate"], truth)) for row in controls
        ]
        return dict(
            status="complete",
            baseline_passed=True,
            candidate_passed=True,
            control_detected=bool(controls)
            and all(not row["verification"]["passed"] for row in checked),
            baseline=baseline,
            controls=checked,
            reference=truth,
            raw_partial=partial,
            finite_ECM_adapted=False,
        )
    except Exception as error:
        return dict(
            status="reference_failed",
            baseline_passed=False,
            candidate_passed=False,
            control_detected=False,
            controls=[],
            raw_partial=partial,
            type=type(error).__name__,
            reason=str(error),
            traceback=traceback.format_exc(),
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = upstream.json_record(args.input.read_text(), 256 * 2**20)
    report = evaluate(payload)
    try:
        origin = upstream.runtime_inventory(args.input)
        origin.update(
            source=str(Path(__file__).resolve()),
            source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        )
        report["runtime_origin"] = origin
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
