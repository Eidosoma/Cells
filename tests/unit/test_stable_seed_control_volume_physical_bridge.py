"""Held prospective manufactured bridge tests; no trajectory or native credit."""

import hashlib
import json
import math
import os
import subprocess
import sys
import traceback
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace

import pytest

from cells.processes import conservative_polygon_geometry as polygons
from cells.processes import stable_mesh_physical_reconstruction as topology
from cells.processes import stable_seed_control_volume_physical_bridge as bridge
from cells.processes import stable_seed_control_volumes as volumes
from validation.geometry import stable_seed_control_volume_physical_bridge_fixtures as fixtures

DECLARATION_REFUSALS = (
    "missing-domain",
    "changed-domain",
    "native-domain-claim",
    "old-geometry-scope",
    "empty-cached-operators",
    "provided-old-inverse",
    "zero-height",
    "zero-thickness",
    "wrong-units",
    "unsealed-caps",
    "unselected-boundary-partner",
    "cell-merge-policy",
    "missing-bath-assignment",
    "unknown-bath-id",
)
EVIDENCE_REFUSALS = (
    "missing-acceptance",
    "changed-input-digest",
    "truncated-original-input",
    "negative-control-report",
    "baseline-failed",
    "truncated-counts",
    "empty-independent-fields",
    "runtime-source-missing",
    "runtime-import-contamination",
)
GEOMETRY_CORRUPTIONS = (
    "cell-volume",
    "cell-centroid",
    "stored-vertex",
    "empty-contact-axes",
    "truncated-membranes",
    "wrong-bath-owner",
    "nonreciprocal-boundary-partner",
    "double-contact-area",
    "wrong-local-edge-map",
    "wrong-lexical-direction",
    "wrong-boundary-translation",
    "coherent-wrong-volume-target",
    "outgoing-selected-bound",
    "native-promotion",
    "extra-certificate-field",
    "missing-owner-map-row",
    "extra-centroid-component",
    "extra-midpoint-component",
    "coherent-extra-tangent-component",
)
PHYSICAL_CORRUPTIONS = (
    "cell-volume-pL",
    "neutral-inventory-change",
    "bath-volume-pL",
    "membrane-area",
    "capacitance",
    "permeability",
    "double-contact-area",
    "reversed-contact",
    "missing-membrane",
    "truncated-controls",
    "native-promotion",
    "extra-model-field",
    "unknown-membrane-permeability-species",
    "unknown-contact-permeability-species",
)
PHYSICAL_REFUSALS = (
    "wrong-geometry",
    "missing-cell",
    "wrong-membrane-cell",
    "wrong-membrane-bath",
    "reversed-contact",
    "missing-contact",
    "zero-specific-capacitance",
    "negative-diffusivity",
    "unknown-closure",
    "gpu",
    "float32",
    "jit",
)


def persist(root, name, value):
    root.mkdir(parents=True, exist_ok=True)
    target = root / (name + ".json")
    with target.open("x") as stream:
        json.dump(bridge.plain(value), stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    return target


@contextmanager
def evidence_tree(root, case, purpose):
    state = dict(
        case=case,
        purpose=purpose,
        stage="declared",
        original=None,
        constructor_request=None,
        constructor_candidate=None,
        constructor_evidence=None,
        request=None,
        geometry=None,
        physical_input=None,
        physical=None,
    )
    persist(
        root,
        "declared-manufactured-test-input",
        dict(
            case=case,
            purpose=purpose,
            domain=fixtures.constructor_declaration(case),
            original_mesh_outcome="0/9 unchanged",
            native_equivalence=False,
            constructor_proposals_automatically_selected=False,
            missing_lattice_caller_envelopes_resolved=False,
            numerical_trajectory_executed=False,
        ),
    )
    try:
        yield state
    except BaseException as error:
        try:
            persist(
                root,
                "bridge-failure",
                dict(
                    state=state,
                    type=type(error).__name__,
                    reason=str(error),
                    traceback=traceback.format_exc(),
                    stage=getattr(error, "stage", None),
                    original=getattr(error, "original", None),
                    partial=getattr(error, "partial", None),
                ),
            )
        except BaseException as capture:
            error.add_note("Bridge failure capture also failed: " + repr(capture))
            try:
                persist(
                    root,
                    "bridge-failure-capture-error",
                    dict(
                        original_type=type(error).__name__,
                        original_reason=str(error),
                        capture_type=type(capture).__name__,
                        capture_reason=str(capture),
                    ),
                )
            except BaseException as fallback:
                error.add_note("Bridge failure capture fallback also failed: " + repr(fallback))
        raise


def observe(root, prefix):
    sequence = [0]

    def event(stage, value):
        persist(root, prefix + "-" + str(sequence[0]) + "-" + stage, value)
        sequence[0] += 1

    return event


def reference_child(root, prefix, module, payload, *, expected_baseline_failure=False):
    source = persist(root, prefix + "-input", payload)
    target = root / (prefix + "-output.json")
    with (root / (prefix + ".stdout.log")).open("x") as log:
        process = None
        try:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    module,
                    "--input",
                    str(source),
                    "--output",
                    str(target),
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            persist(
                root,
                prefix + "-started",
                dict(
                    pid=process.pid,
                    parent_pid=os.getpid(),
                    module=module,
                    input_path=str(source),
                    input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                    timeout_seconds=480,
                    kind="actual_nested_worker_not_standalone_replay@1",
                ),
            )
            process.wait(timeout=480)
        except BaseException as error:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
            persist(
                root,
                prefix + "-process-failure",
                dict(
                    type=type(error).__name__,
                    reason=str(error),
                    pid=None if process is None else process.pid,
                    traceback=traceback.format_exc(),
                ),
            )
            raise
        finally:
            log.flush()
            os.fsync(log.fileno())
    persist(
        root,
        prefix + "-process",
        dict(pid=process.pid, parent_pid=os.getpid(), returncode=process.returncode),
    )
    report = json.loads(target.read_text()) if target.is_file() else None
    assert report is not None, (
        "Actual input/start/log/process artifacts retained; no complete child report"
    )
    runtime = report["runtime_origin"]
    assert runtime["pid"] == process.pid and runtime["parent_pid"] == os.getpid()
    assert runtime["input_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert runtime["production_and_scientific_imports_denied"] is True
    assert runtime["production_or_scientific_modules_loaded"] == []
    assert runtime["file_errors"] == {} and runtime["mapped_file_errors"] == []
    assert report.get("runtime_capture_failed", False) is False
    if expected_baseline_failure:
        assert process.returncode == 2 and report["status"] == "baseline_failed"
        assert report["baseline_passed"] is False and report["candidate_passed"] is False
        assert report["control_detected"] is False and report["controls"] == []
        return source.read_text(), target.read_text(), report
    assert process.returncode == 0 and report["baseline_passed"] is True
    if payload.get("controls"):
        assert report["control_detected"] is True
        assert [row["name"] for row in report["controls"]] == [
            row["name"] for row in payload["controls"]
        ]
        assert all(row["verification"]["passed"] is False for row in report["controls"])
    else:
        assert report["candidate_passed"] is True and report["control_detected"] is False
    return source.read_text(), target.read_text(), report


def constructor(root, state):
    state["stage"] = "original_retained_seed_input"
    original = fixtures.original_request(state["case"])
    state["original"] = original
    persist(root, "original-retained-seed-input", original)
    parent = topology.bind(original)
    corrected = topology.reconstruct(parent)
    persist(root, "original-topology-request", parent)
    persist(root, "retained-original-topology", corrected)
    request = volumes.bind(parent, corrected, fixtures.constructor_declaration(state["case"]))
    state["constructor_request"] = request
    persist(root, "constructor-request", request)
    state["stage"] = "new_fixed_seed_constructor"
    candidate = volumes.prepare(request, observer=observe(root, "constructor-event"))
    state["constructor_candidate"] = candidate
    persist(root, "constructor-candidate", candidate)
    state["stage"] = "actual_complete_constructor_reference_child"
    input_json, report_json, _ = reference_child(
        root,
        "constructor-reference",
        "validation.geometry.stable_seed_control_volumes_reference",
        dict(request=request, candidate=candidate),
    )
    accepted = fixtures.acceptance(candidate, input_json, report_json)
    state["constructor_evidence"] = accepted
    persist(root, "accepted-complete-constructor-evidence", accepted)
    return request, candidate, accepted


def prepare(root, state, *, physical=False):
    cv_request, cv, proof = constructor(root, state)
    declared = fixtures.declaration(state["case"], cv)
    persist(root, "explicit-bridge-caller-declaration", declared)
    request = bridge.bind(cv_request, cv, proof, declared)
    state["request"] = request
    persist(root, "bridge-request", request)
    state["stage"] = "fresh_conservative_geometry_preparation"
    geometry = bridge.prepare(request, observer=observe(root, "geometry-event"))
    state["geometry"] = geometry
    persist(root, "geometry-preparation", geometry)
    admitted = None
    if physical:
        raw = fixtures.physical_input(geometry)
        # Explicitly exercise ID joins and parser ordering with the second case.
        if state["case"] == fixtures.SECOND:
            for family in ("cells", "baths", "membranes", "contacts"):
                raw["physics"][family].reverse()
            for family in ("membrane_controls", "junction_controls"):
                raw["experiment"][family].reverse()
        state["physical_input"] = raw
        persist(root, "explicit-physical-caller-input", raw)
        state["stage"] = "existing_physical_parser_initial_admission"
        admitted = bridge.prepare_physical(
            request, geometry, raw, observer=observe(root, "physical-event")
        )
        state["physical"] = admitted
        persist(root, "physical-preparation", admitted)
    return request, dict(
        geometry_preparation=bridge.plain(geometry), physical_preparation=bridge.plain(admitted)
    )


def independent(root, state, snapshot, *, controls=None, expected_baseline_failure=False):
    state["stage"] = "actual_independent_bridge_reference_child"
    payload = dict(
        request=state["request"], physical_input=state["physical_input"], candidate=snapshot
    )
    if controls is not None:
        payload["controls"] = controls
    _, _, report = reference_child(
        root,
        "bridge-reference",
        "validation.geometry.stable_seed_control_volume_physical_bridge_reference",
        payload,
        expected_baseline_failure=expected_baseline_failure,
    )
    return report


def reseal(snapshot):
    prepared = snapshot["geometry_preparation"]
    bound = prepared["geometry_binding"]
    geometry = json.loads(bound["geometry_json"])
    bound["geometry_json"] = polygons._json(geometry)
    bound["identity"] = polygons._digest(geometry)
    prepared["identity"] = bridge.digest(
        [bridge.LAW_ID]
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
    )
    admitted = snapshot["physical_preparation"]
    if admitted is not None:
        admitted["geometry_preparation_identity"] = prepared["identity"]
        inner = admitted["physical_preparation"]
        definition, provenance = (
            json.loads(inner[key]) for key in ("definition_json", "provenance_json")
        )
        provenance["definition_sha256"] = polygons._digest(definition)
        inner["definition_json"], inner["provenance_json"] = (
            polygons._json(definition),
            polygons._json(provenance),
        )
        inner["identity"] = polygons._digest(dict(definition=definition, provenance=provenance))
        admitted["identity"] = bridge.digest(
            [bridge.LAW_ID]
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
        )
    return snapshot


def geometry_corruption(name, snapshot):
    changed = deepcopy(snapshot)
    prepared = changed["geometry_preparation"]
    g = json.loads(prepared["geometry_binding"]["geometry_json"])
    if name == "cell-volume":
        g["cells"][0]["volume_m3"] = math.nextafter(g["cells"][0]["volume_m3"], math.inf)
    elif name == "cell-centroid":
        g["cells"][0]["centroid_m"][0] = math.nextafter(g["cells"][0]["centroid_m"][0], math.inf)
    elif name == "stored-vertex":
        g["vertices"][0]["xy_m"][0] = math.nextafter(g["vertices"][0]["xy_m"][0], math.inf)
    elif name == "empty-contact-axes":
        g["contacts"] = []
        g["contact_incidence"] = [[] for _ in g["owner_axis"]]
        prepared["conservation"]["contact_incidence_column_sums"] = []
        for row in prepared["owner_maps"]["edges"]:
            row["geometry_contact"] = row["geometry_contact_id"] = None
    elif name == "truncated-membranes":
        g["membranes"].pop()
    elif name == "wrong-bath-owner":
        g["membranes"][0]["bath_id"] = "unknown-manufactured-bath"
    elif name == "nonreciprocal-boundary-partner":
        membrane = next(row for row in g["membranes"] if row["partner_id"] == row["id"])
        membrane["partner_id"] = next(
            row["id"] for row in g["membranes"] if row["id"] != membrane["id"]
        )
    elif name == "double-contact-area":
        g["contacts"][0]["area_m2"] *= 2
    elif name == "wrong-local-edge-map":
        prepared["owner_maps"]["occurrences"][0]["geometry_local_edge"] += 1
    elif name == "wrong-lexical-direction":
        row = next(
            row for row in prepared["owner_maps"]["edges"] if row["canonical_direction"] == -1
        )
        row["canonical_direction"] = 1
    elif name == "wrong-boundary-translation":
        row = next(
            row
            for row in prepared["owner_maps"]["occurrences"]
            if row["boundary_none_to_self_translation"]
        )
        row["boundary_none_to_self_translation"] = False
    elif name == "coherent-wrong-volume-target":
        for field in ("volume_sum_exact", "domain_extruded_volume_exact"):
            value = prepared["conservation"][field]
            value["numerator"] = str(int(value["numerator"]) + 1)
    elif name == "outgoing-selected-bound":
        value = prepared["conservation"]["cells"][0]["rounded_product_absolute_error_bound"][0]
        value["numerator"] = str(2 * int(value["numerator"]) + 1)
    elif name == "extra-centroid-component":
        g["cells"][0]["centroid_m"].append(0.0)
    elif name == "extra-midpoint-component":
        g["edges"][0]["midpoint_m"].append(0.0)
    elif name == "coherent-extra-tangent-component":
        for edge in g["edges"]:
            edge["tangent_xy"].append(0.0)
        edges = {row["id"]: row for row in g["edges"]}
        for membrane in g["membranes"]:
            edge = edges[membrane["edge_id"]]
            direction = 1 if membrane["vertex_ids"] == edge["vertex_ids"] else -1
            membrane["tangent_xy"].append(direction * 0.0)
    elif name == "native-promotion":
        g["native_equivalence"] = True
        prepared["provenance"]["native_equivalence"] = True
    elif name == "extra-certificate-field":
        g["cells"][0]["certificates"]["area"]["caller_selected_tolerance"] = 1.0
    elif name == "missing-owner-map-row":
        prepared["owner_maps"]["occurrences"].pop()
    else:
        raise ValueError(name)
    prepared["geometry_binding"]["geometry_json"] = polygons._json(g)
    return reseal(changed)


def physical_corruption(name, snapshot):
    changed = deepcopy(snapshot)
    admitted = changed["physical_preparation"]
    inner = admitted["physical_preparation"]
    definition = json.loads(inner["definition_json"])
    model = definition["model"]
    if name == "cell-volume-pL":
        model["cells"][0]["volume_pL"] = math.nextafter(model["cells"][0]["volume_pL"], math.inf)
    elif name == "neutral-inventory-change":
        for species in ("Na", "Cl"):
            model["cells"][0]["initial_amount_fmol"][species] *= 2
    elif name == "bath-volume-pL":
        model["extracellular"][0]["volume_pL"] = math.nextafter(
            model["extracellular"][0]["volume_pL"], math.inf
        )
    elif name == "membrane-area":
        model["membranes"][0]["area_m2"] *= 2
    elif name == "capacitance":
        model["membranes"][0]["capacitance_F"] = math.nextafter(
            model["membranes"][0]["capacitance_F"], math.inf
        )
    elif name == "permeability":
        model["membranes"][0]["permeability_m_per_s"]["Na"] *= 2
    elif name == "double-contact-area":
        model["junctions"][0]["area_m2"] *= 2
    elif name == "reversed-contact":
        contact = model["junctions"][0]
        contact["sender"], contact["receiver"] = contact["receiver"], contact["sender"]
    elif name == "missing-membrane":
        model["membranes"].pop()
    elif name == "truncated-controls":
        definition["experiment"]["membrane_controls"].pop()
    elif name == "unknown-membrane-permeability-species":
        model["membranes"][0]["permeability_m_per_s"]["unknown-ion"] = 0.0
    elif name == "unknown-contact-permeability-species":
        model["junctions"][0]["permeability_m_per_s"]["unknown-ion"] = 0.0
    elif name == "native-promotion":
        admitted["provenance"]["native_equivalence"] = True
    elif name == "extra-model-field":
        model["implicit_inventory_rescaling"] = True
    else:
        raise ValueError(name)
    inner["definition_json"] = polygons._json(definition)
    return reseal(changed)


@pytest.mark.parametrize("case,with_physical", fixtures.POSITIVE_CASES, ids=fixtures.POSITIVE_IDS)
def test_complete_manufactured_geometry_and_physical_owners(case, with_physical, tmp_path):
    with evidence_tree(
        tmp_path, case, "complete_positive_geometry_and_optional_existing_physical_admission"
    ) as state:
        _, snapshot = prepare(tmp_path, state, physical=with_physical)
        report = independent(tmp_path, state, snapshot)
        assert report["reference"]["constructor_geometry_replayed"] is False
        geometry = state["geometry"]
        assert len(geometry.owner_maps["cells"]) == len(
            state["constructor_candidate"].owners["retained_point_ids"]
        )
        assert (
            geometry.provenance["constructor_prerequisites_unchanged"]
            == state["constructor_candidate"].prerequisites
        )
        assert geometry.provenance["native_equivalence"] is False
        if with_physical:
            assert state["physical"].provenance["manufactured_physical_model_prepared"] is True
            assert state["physical"].provenance["ordinary_ECM_loop_ready"] is False
        persist(
            tmp_path,
            "bridge-positive-verdict",
            dict(
                passed=True,
                case=case,
                physical=with_physical,
                reference_baseline_passed=report["baseline_passed"],
                native_equivalence=False,
                actual_reference_children=2,
            ),
        )


def test_complete_caller_contract_and_stale_request_refusals(tmp_path):
    with evidence_tree(
        tmp_path,
        fixtures.BASE,
        "batched_caller_contract_refusals_after_positive_independent_baseline",
    ) as state:
        request, snapshot = prepare(tmp_path, state)
        independent(tmp_path, state, snapshot)
        for name in DECLARATION_REFUSALS:
            raw = bridge.plain(request.declaration)
            if name == "missing-domain":
                raw.pop("domain_selection")
            elif name == "changed-domain":
                raw["domain_selection"]["selected_domain"]["vertices_m"][0][0] *= 2
            elif name == "native-domain-claim":
                raw["domain_selection"]["native_tissue_or_bath_equivalence"] = True
            elif name == "old-geometry-scope":
                raw["scope"] = "native_tissue_boundary"
            elif name == "empty-cached-operators":
                raw["operator_policy"]["provided_cached_operators"] = {}
            elif name == "provided-old-inverse":
                raw["operator_policy"]["provided_cached_operators"] = dict(lapGJinv=[[1.0]])
            elif name in ("zero-height", "zero-thickness"):
                raw["extrusion"]["height_m" if name == "zero-height" else "thickness_m"] = 0.0
            elif name == "wrong-units":
                raw["extrusion"]["units"]["coordinates"] = "um"
            elif name == "unsealed-caps":
                raw["extrusion"]["axial_caps"] = "open"
            elif name == "unselected-boundary-partner":
                raw["extrusion"]["boundary_partner_policy"] = "None"
            elif name == "cell-merge-policy":
                raw["extrusion"]["cell_policy"] = "automatic_merge"
            elif name == "missing-bath-assignment":
                raw["extrusion"].pop("bath_assignment")
            elif name == "unknown-bath-id":
                raw["extrusion"]["bath_assignment"]["bath_id"] = "unknown"
            persist(tmp_path, "caller-refusal-" + name + "-input", raw)
            with pytest.raises(ValueError) as caught:
                changed = bridge.bind(
                    request.constructor_request,
                    request.constructor_candidate,
                    request.constructor_evidence,
                    raw,
                )
                bridge.prepare(changed)
            persist(
                tmp_path,
                "caller-refusal-" + name + "-verdict",
                dict(
                    refused=True,
                    type=type(caught.value).__name__,
                    reason=str(caught.value),
                    original=getattr(caught.value, "original", None),
                    partial=getattr(caught.value, "partial", None),
                ),
            )
        changed = replace(request, identity="0" * 64)
        with pytest.raises(ValueError, match="request or seal"):
            bridge.validate_request(changed)
        persist(
            tmp_path,
            "caller-contract-panel",
            dict(
                passed=True,
                ids=DECLARATION_REFUSALS,
                positive_baseline_first=True,
                changed_request_seal_refused=True,
                actual_reference_children=2,
            ),
        )


def test_complete_positive_constructor_evidence_is_required(tmp_path):
    with evidence_tree(
        tmp_path, fixtures.BASE, "batched_evidence_refusals_after_positive_independent_baseline"
    ) as state:
        request, snapshot = prepare(tmp_path, state)
        independent(tmp_path, state, snapshot)
        for name in EVIDENCE_REFUSALS:
            incoming = json.loads(request.constructor_evidence.input_json)
            report = json.loads(request.constructor_evidence.report_json)
            if name == "truncated-original-input":
                incoming["candidate"]["certificates"]["arithmetic_events"].pop()
            elif name == "negative-control-report":
                report["control_detected"] = True
            elif name == "baseline-failed":
                report["baseline_passed"] = False
            elif name == "truncated-counts":
                report["reference"]["counts"]["scalar_events"] -= 1
            elif name == "empty-independent-fields":
                report["reference"]["candidate_fields"] = {}
            elif name == "runtime-source-missing":
                report["runtime_origin"]["files"].pop(report["runtime_origin"]["source"])
            elif name == "runtime-import-contamination":
                report["runtime_origin"]["production_or_scientific_modules_loaded"] = ["cells"]
            incoming_text, report_text = (
                json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
                for value in (incoming, report)
            )
            proof = fixtures.acceptance(request.constructor_candidate, incoming_text, report_text)
            if name == "missing-acceptance":
                proof = replace(proof, caller_acceptance={})
            elif name == "changed-input-digest":
                proof.caller_acceptance["input_sha256"] = "0" * 64
            # Rewritten JSON bytes also require matching original child input
            # SHA; otherwise controls would be credited for that incidental gate.
            if name not in (
                "truncated-original-input",
                "changed-input-digest",
                "missing-acceptance",
            ):
                report["runtime_origin"]["input_sha256"] = hashlib.sha256(
                    incoming_text.encode()
                ).hexdigest()
                proof = fixtures.acceptance(
                    request.constructor_candidate,
                    incoming_text,
                    json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n",
                )
            persist(tmp_path, "constructor-evidence-refusal-" + name + "-input", proof)
            with pytest.raises(ValueError) as caught:
                bridge.bind(
                    request.constructor_request,
                    request.constructor_candidate,
                    proof,
                    request.declaration,
                )
            persist(
                tmp_path,
                "constructor-evidence-refusal-" + name + "-verdict",
                dict(refused=True, type=type(caught.value).__name__, reason=str(caught.value)),
            )
        persist(
            tmp_path,
            "constructor-evidence-panel",
            dict(
                passed=True,
                ids=EVIDENCE_REFUSALS,
                positive_baseline_first=True,
                actual_reference_children=2,
            ),
        )


def test_resealed_complete_geometry_corruptions_need_passing_same_worker_baseline(tmp_path):
    with evidence_tree(
        tmp_path, fixtures.BASE, "one_truth_for_all_resealed_geometry_output_controls"
    ) as state:
        _, snapshot = prepare(tmp_path, state)
        controls = [
            dict(name=name, candidate=geometry_corruption(name, snapshot))
            for name in GEOMETRY_CORRUPTIONS
        ]
        assert all(bridge.digest(row["candidate"]) != bridge.digest(snapshot) for row in controls)
        independent(tmp_path, state, snapshot, controls=controls)
        persist(
            tmp_path,
            "geometry-control-panel",
            dict(
                passed=True,
                ids=GEOMETRY_CORRUPTIONS,
                positive_baseline_same_worker_first=True,
                actual_reference_children=2,
                separate_control_replays=0,
            ),
        )


def test_resealed_complete_physical_corruptions_need_passing_same_worker_baseline(tmp_path):
    with evidence_tree(
        tmp_path, fixtures.BASE, "one_truth_for_all_resealed_physical_output_controls"
    ) as state:
        _, snapshot = prepare(tmp_path, state, physical=True)
        controls = [
            dict(name=name, candidate=physical_corruption(name, snapshot))
            for name in PHYSICAL_CORRUPTIONS
        ]
        assert all(bridge.digest(row["candidate"]) != bridge.digest(snapshot) for row in controls)
        independent(tmp_path, state, snapshot, controls=controls)
        persist(
            tmp_path,
            "physical-control-panel",
            dict(
                passed=True,
                ids=PHYSICAL_CORRUPTIONS,
                positive_baseline_same_worker_first=True,
                actual_reference_children=2,
                separate_control_replays=0,
            ),
        )


def test_failed_bridge_baseline_cannot_credit_output_controls(tmp_path):
    with evidence_tree(
        tmp_path, fixtures.BASE, "failed_baseline_must_block_all_negative_control_credit"
    ) as state:
        _, snapshot = prepare(tmp_path, state)
        broken_baseline = geometry_corruption("cell-volume", snapshot)
        controls = [
            dict(
                name="wrong-local-edge-map",
                candidate=geometry_corruption("wrong-local-edge-map", snapshot),
            )
        ]
        report = independent(
            tmp_path, state, broken_baseline, controls=controls, expected_baseline_failure=True
        )
        assert report["baseline"]["passed"] is False
        persist(
            tmp_path,
            "baseline-failure-guard-verdict",
            dict(
                passed=True,
                original_geometry_retained=True,
                changed_baseline_refused=True,
                output_controls_credited=False,
                actual_reference_children=2,
            ),
        )


def test_explicit_physics_and_existing_parser_refusals(tmp_path):
    with evidence_tree(
        tmp_path,
        fixtures.BASE,
        "batched_physical_contract_refusals_after_positive_independent_baseline",
    ) as state:
        request, snapshot = prepare(tmp_path, state, physical=True)
        independent(tmp_path, state, snapshot)
        for name in PHYSICAL_REFUSALS:
            raw = deepcopy(state["physical_input"])
            physics = raw["physics"]
            if name == "wrong-geometry":
                raw["geometry_identity"] = "0" * 64
            elif name == "missing-cell":
                physics["cells"].pop()
            elif name == "wrong-membrane-cell":
                physics["membranes"][0]["cell_id"] = "wrong-cell"
            elif name == "wrong-membrane-bath":
                physics["membranes"][0]["bath_id"] = "wrong-bath"
            elif name == "reversed-contact":
                row = physics["contacts"][0]
                row["sender"], row["receiver"] = row["receiver"], row["sender"]
            elif name == "missing-contact":
                physics["contacts"].pop()
            elif name == "zero-specific-capacitance":
                physics["membranes"][0]["specific_capacitance_F_per_m2"] = 0.0
            elif name == "negative-diffusivity":
                physics["membranes"][0]["diffusivity_m2_per_s"]["Na"] = -1e-18
            elif name == "unknown-closure":
                physics["closure"]["law"] = "unknown"
            elif name == "gpu":
                raw["execution"]["backend"] = "gpu"
            elif name == "float32":
                raw["execution"]["precision"] = "float32"
            elif name == "jit":
                raw["execution"]["jit"] = True
            persist(tmp_path, "physical-refusal-" + name + "-input", raw)
            with pytest.raises(bridge.BridgeRejected) as caught:
                bridge.prepare_physical(request, state["geometry"], raw)
            assert caught.value.stage in (
                "geometry_validation",
                "existing_passive_physical_admission",
            )
            if name == "unknown-closure":
                assert caught.value.stage == "existing_passive_physical_admission"
                assert caught.value.original["type"] == "PhysicalRejected"
                assert caught.value.original["trial"]["physical_model_prepared"] is False
            persist(
                tmp_path,
                "physical-refusal-" + name + "-verdict",
                dict(
                    refused=True,
                    stage=caught.value.stage,
                    reason=str(caught.value),
                    original=caught.value.original,
                    partial=caught.value.partial,
                ),
            )
        persist(
            tmp_path,
            "physical-refusal-panel",
            dict(
                passed=True,
                ids=PHYSICAL_REFUSALS,
                positive_baseline_first=True,
                actual_reference_children=2,
            ),
        )


def test_closed_native_and_cached_operator_gates_remain_closed(tmp_path):
    with evidence_tree(
        tmp_path,
        fixtures.BASE,
        "new_manufactured_admission_does_not_promote_native_or_operator_gates",
    ) as state:
        request, snapshot = prepare(tmp_path, state, physical=True)
        independent(tmp_path, state, snapshot)
        bridge.validate_geometry(request, state["geometry"])
        # Complete physical output validation calls existing initial admission;
        # it performs no solver trajectory and is not another reference child.
        bridge.validate_physical(request, state["geometry"], state["physical"])
        with pytest.raises(ValueError, match="invalidated"):
            bridge.require_cached_operators(state["physical"])
        with pytest.raises(ValueError):
            volumes.require_physical_admission(request.constructor_candidate)
        persist(
            tmp_path,
            "closed-gates-verdict",
            dict(
                passed=True,
                physical_admission_scope="manufactured existing parser only",
                constructor_gate_unchanged=True,
                old_operator_gate_closed=True,
                native_equivalence=False,
                original_mesh_outcome="0/9 unchanged",
                actual_reference_children=2,
            ),
        )
