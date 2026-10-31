"""Unrun prospective complete ownership/obstruction tests, never ECM admission."""

import json
from copy import deepcopy
from dataclasses import replace

import pytest

from cells.processes import stable_seed_control_volume_environment as environment
from cells.processes import stable_seed_control_volume_physical_bridge as bridge
from tests.unit import test_stable_seed_control_volume_physical_bridge as upstream
from validation.geometry import stable_seed_control_volume_environment_fixtures as fixtures

BASE = "manufactured-irregular-square"
REFUSALS = (
    "missing-domain",
    "enlarged-domain",
    "native-domain",
    "new-bath-role",
    "changed-bath-volume",
    "missing-bath",
    "duplicate-membrane",
    "wrong-membrane-bath",
    "missing-boundary",
    "reversed-boundary",
    "open-boundary",
    "old-cache",
    "empty-cache",
    "finite-admission-scope",
)
EVIDENCE_REFUSALS = (
    "missing-acceptance",
    "wrong-identity",
    "negative-control-report",
    "geometry-only-report",
    "truncated-physical-scalars",
    "empty-owner-truth",
    "runtime-source-missing",
    "runtime-imports",
)
CORRUPTIONS = (
    "coordinate",
    "bath-index",
    "cell-ring",
    "drop-membrane",
    "partner",
    "direct-cell-owner",
    "boundary-owner-role",
    "positive-leftover",
    "drop-cleft-prerequisite",
    "empty-witnesses",
    "invented-bath-face",
    "finite-promotion",
    "cached-operator-promotion",
    "extra-field",
)


def build(root, state, profile):
    bridge_request, _ = upstream.prepare(root, state, physical=False)
    geometry = state["geometry"]
    raw = fixtures.physical_input(geometry, state["case"], profile)
    upstream.persist(root, "explicit-environment-profile-physical-input", raw)
    state["physical_input"] = raw
    physical = bridge.prepare_physical(
        bridge_request,
        geometry,
        raw,
        observer=upstream.observe(root, "environment-profile-admission-event"),
    )
    state["physical"] = physical
    upstream.persist(root, "environment-profile-physical-preparation", physical)
    snapshot = dict(
        geometry_preparation=environment.plain(geometry),
        physical_preparation=environment.plain(physical),
    )
    upstream.independent(root, state, snapshot)
    proof = fixtures.acceptance(
        bridge_request,
        geometry,
        physical,
        (root / "bridge-reference-input.json").read_text(),
        (root / "bridge-reference-output.json").read_text(),
    )
    upstream.persist(root, "accepted-complete-physical-bridge", proof)
    declared = fixtures.declaration(bridge_request, geometry, physical)
    upstream.persist(root, "explicit-environment-caller-input", declared)
    state["stage"] = "new_environment_prerequisite_correspondence"
    request = environment.bind(bridge_request, geometry, physical, proof, declared)
    state["environment_request"] = request
    upstream.persist(root, "environment-request", request)
    value = environment.prepare(request)
    state["environment_correspondence"] = value
    upstream.persist(root, "environment-correspondence", value)
    return request, value


def independent(root, request, value, *, controls=None, failed_baseline=False):
    payload = dict(request=request, candidate=value)
    if controls is not None:
        payload["controls"] = controls
    return upstream.reference_child(
        root,
        "environment-reference",
        "validation.geometry.stable_seed_control_volume_environment_reference",
        payload,
        expected_baseline_failure=failed_baseline,
    )[2]


def corrupt(name, value):
    changed = environment.plain(value)
    if name == "coordinate":
        changed["indices"]["vertices"][0]["xy_m"][0] *= 2
    elif name == "bath-index":
        changed["indices"]["membranes"][0]["bath_owner_index"] = 0
    elif name == "cell-ring":
        changed["indices"]["cells"][0]["vertex_indices"].reverse()
    elif name == "drop-membrane":
        changed["indices"]["membranes"].pop()
    elif name == "partner":
        changed["indices"]["membranes"][0]["partner_index"] += 1
    elif name == "direct-cell-owner":
        changed["indices"]["direct_cell_cell_interfaces"][0]["cell_ids"].reverse()
    elif name == "boundary-owner-role":
        changed["indices"]["boundary"][0]["actual_polygon_owner_kind"] = "bath"
    elif name == "positive-leftover":
        changed["witnesses"]["available_disjoint_bath_area_m2_exact"] = dict(
            numerator="1", denominator="1"
        )
    elif name == "drop-cleft-prerequisite":
        changed["witnesses"]["unmet_prerequisites"].remove("declared_intercellular_cleft_geometry")
    elif name == "empty-witnesses":
        changed["witnesses"] = {}
    elif name == "invented-bath-face":
        changed["indices"]["bath_bath_faces"] = [dict(id="invented", length_m=1e-6)]
    elif name == "finite-promotion":
        changed["provenance"]["finite_ECM_adapted"] = True
    elif name == "cached-operator-promotion":
        changed["provenance"]["cached_operators_accepted"] = True
    elif name == "extra-field":
        changed["native_grid"] = []
    else:
        raise ValueError(name)
    changed["identity"] = environment.digest(
        [environment.LAW_ID]
        + [changed[key] for key in ("request_identity", "indices", "witnesses", "provenance")]
    )
    return changed


@pytest.mark.parametrize("case,profile", fixtures.POSITIVE_CASES, ids=fixtures.POSITIVE_IDS)
def test_complete_accepted_bridge_correspondence_and_exact_obstruction(case, profile, tmp_path):
    with upstream.evidence_tree(
        tmp_path, case, "positive_correspondence_not_positive_finite_ECM_adaptation"
    ) as state:
        request, value = build(tmp_path, state, profile)
        report = independent(tmp_path, request, value)
        assert report["baseline_passed"] is True
        assert value.witnesses["available_disjoint_bath_area_m2_exact"]["numerator"] == "0"
        assert int(value.witnesses["exact_bath_area_shortfall_m2"]["numerator"]) > 0
        assert value.provenance["finite_ECM_adapted"] is False
        assert [row["reservoir"] for row in value.indices["baths"]] == (
            [True] if profile == "held-compartments" else [False] * len(value.indices["baths"])
        )
        upstream.persist(
            tmp_path,
            "environment-positive-verdict",
            dict(
                passed=True,
                scope="source_owner_correspondence_and_exact_obstruction_only",
                physical_profile=profile,
                finite_ECM_adapted=False,
                actual_reference_children=3,
            ),
        )


def test_explicit_caller_domain_baths_boundaries_and_cache_refusals(tmp_path):
    with upstream.evidence_tree(
        tmp_path, BASE, "batched_caller_refusals_after_positive_correspondence"
    ) as state:
        request, value = build(tmp_path, state, "finite-compartments")
        independent(tmp_path, request, value)
        for name in REFUSALS:
            raw = environment.plain(request.declaration)
            if name == "missing-domain":
                raw.pop("domain_selection")
            elif name == "enlarged-domain":
                raw["domain_selection"]["selected_domain"]["vertices_m"][0][0] *= 2
            elif name == "native-domain":
                raw["domain_selection"]["native_equivalence"] = True
            elif name == "new-bath-role":
                raw["baths"][0]["reservoir"] = True
            elif name == "changed-bath-volume":
                raw["baths"][0]["volume_m3"] *= 2
            elif name == "missing-bath":
                raw["baths"].pop()
            elif name == "duplicate-membrane":
                raw["membrane_baths"][-1] = deepcopy(raw["membrane_baths"][0])
            elif name == "wrong-membrane-bath":
                raw["membrane_baths"][0]["bath_id"] = "unknown"
            elif name == "missing-boundary":
                raw["outer_boundary"]["rows"].pop()
            elif name == "reversed-boundary":
                raw["outer_boundary"]["rows"][0]["directed_vertex_ids"].reverse()
            elif name == "open-boundary":
                raw["outer_boundary"]["condition"] = "open"
            elif name == "old-cache":
                raw["operator_policy"]["provided_cached_operators"] = dict(map_mem2ecm=[0])
            elif name == "empty-cache":
                raw["operator_policy"]["provided_cached_operators"] = {}
            elif name == "finite-admission-scope":
                raw["scope"] = "finite_ECM_adapted"
            upstream.persist(tmp_path, "environment-refusal-" + name + "-input", raw)
            with pytest.raises(ValueError) as caught:
                environment.bind(
                    request.bridge_request,
                    request.geometry_preparation,
                    request.physical_preparation,
                    request.bridge_evidence,
                    raw,
                )
            upstream.persist(
                tmp_path,
                "environment-refusal-" + name + "-verdict",
                dict(refused=True, reason=str(caught.value)),
            )
        upstream.persist(
            tmp_path,
            "environment-contract-panel",
            dict(
                passed=True,
                ids=REFUSALS,
                positive_correspondence_first=True,
                actual_reference_children=3,
            ),
        )


def test_complete_positive_physical_bridge_evidence_is_required(tmp_path):
    with upstream.evidence_tree(
        tmp_path, BASE, "accepted_bridge_evidence_refusals_after_positive_correspondence"
    ) as state:
        request, value = build(tmp_path, state, "finite-compartments")
        independent(tmp_path, request, value)
        for name in EVIDENCE_REFUSALS:
            report = json.loads(request.bridge_evidence.report_json)
            if name == "negative-control-report":
                report["control_detected"] = True
            elif name == "geometry-only-report":
                report["baseline"]["physical"] = None
            elif name == "truncated-physical-scalars":
                report["baseline"]["physical"]["full_precision_quantities"].pop()
            elif name == "empty-owner-truth":
                report["reference"]["axes"]["owner_maps"] = {}
            elif name == "runtime-source-missing":
                report["runtime_origin"]["files"].pop(report["runtime_origin"]["source"])
            elif name == "runtime-imports":
                report["runtime_origin"]["production_or_scientific_modules_loaded"] = ["cells"]
            proof = fixtures.acceptance(
                request.bridge_request,
                request.geometry_preparation,
                request.physical_preparation,
                request.bridge_evidence.input_json,
                json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n",
            )
            if name == "missing-acceptance":
                proof = replace(proof, caller_acceptance={})
            elif name == "wrong-identity":
                proof.caller_acceptance["physical_preparation_identity"] = "0" * 64
            upstream.persist(tmp_path, "environment-evidence-refusal-" + name + "-input", proof)
            with pytest.raises(ValueError) as caught:
                environment.bind(
                    request.bridge_request,
                    request.geometry_preparation,
                    request.physical_preparation,
                    proof,
                    request.declaration,
                )
            upstream.persist(
                tmp_path,
                "environment-evidence-refusal-" + name + "-verdict",
                dict(refused=True, reason=str(caught.value)),
            )
        upstream.persist(
            tmp_path,
            "environment-evidence-panel",
            dict(
                passed=True,
                ids=EVIDENCE_REFUSALS,
                positive_correspondence_first=True,
                actual_reference_children=3,
            ),
        )


def test_complete_resealed_output_controls_need_same_worker_baseline(tmp_path):
    with upstream.evidence_tree(
        tmp_path, BASE, "one_independent_truth_for_all_environment_output_controls"
    ) as state:
        request, value = build(tmp_path, state, "finite-compartments")
        controls = [dict(name=name, candidate=corrupt(name, value)) for name in CORRUPTIONS]
        assert all(
            environment.digest(row["candidate"]) != environment.digest(value) for row in controls
        )
        independent(tmp_path, request, value, controls=controls)
        upstream.persist(
            tmp_path,
            "environment-control-panel",
            dict(
                passed=True,
                ids=CORRUPTIONS,
                positive_correspondence_same_worker_first=True,
                actual_reference_children=3,
            ),
        )


def test_failed_correspondence_baseline_cannot_credit_controls(tmp_path):
    with upstream.evidence_tree(
        tmp_path, BASE, "failed_correspondence_baseline_blocks_negative_credit"
    ) as state:
        request, value = build(tmp_path, state, "finite-compartments")
        independent(
            tmp_path,
            request,
            corrupt("coordinate", value),
            controls=[dict(name="finite-promotion", candidate=corrupt("finite-promotion", value))],
            failed_baseline=True,
        )
        upstream.persist(
            tmp_path,
            "environment-baseline-failure-guard",
            dict(passed=True, negative_controls_credited=False, actual_reference_children=3),
        )


def test_missing_ECM_geometry_and_old_operator_gates_remain_closed(tmp_path):
    with upstream.evidence_tree(
        tmp_path, BASE, "source_correspondence_retains_every_ECM_native_and_operator_gate"
    ) as state:
        request, value = build(tmp_path, state, "finite-compartments")
        independent(tmp_path, request, value)
        environment.validate(request, value)
        with pytest.raises(environment.EnvironmentRejected) as caught:
            environment.require_finite_ecm(value)
        assert caught.value.stage == "finite_ECM_adaptation"
        upstream.persist(
            tmp_path,
            "environment-finite-ECM-refusal",
            dict(
                reason=str(caught.value),
                original=caught.value.original,
                partial=caught.value.partial,
            ),
        )
        with pytest.raises(ValueError, match="invalidated"):
            environment.require_cached_operators(value)
        upstream.persist(
            tmp_path,
            "environment-closed-gates-verdict",
            dict(
                passed=True,
                source_correspondence_only=True,
                finite_ECM_adapted=False,
                actual_reference_children=3,
            ),
        )
