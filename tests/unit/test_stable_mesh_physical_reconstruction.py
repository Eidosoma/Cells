"""Prospective saved-mesh candidate panel; never collected in preparation."""

import json
import os
import subprocess
import sys
import traceback
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import fields, is_dataclass, replace

import pytest

from cells.processes import stable_mesh_physical_reconstruction as adapter
from validation.geometry import stable_mesh_physical_reconstruction_saved as saved

CANDIDATES = (
    "irregular-centroid-aux",
    "native-single-preset-seed17",
    "native-single-preset-seed23",
    "caller-square-zero",
    "caller-single-square-cache",
    "caller-single-hex-cache",
)
UNSUPPORTED = ("irregular-circumcenter-aux", "caller-square-disordered", "caller-hex-disordered")
RAW = ("caller-single-point-lattice", "caller-alpha-removes-all")
MUTATIONS = (
    "missing-field",
    "wrong-law",
    "wrong-revision",
    "raw-status",
    "missing-occurrence-ID",
    "duplicate-primal-edge",
    "missing-primal-edge",
    "duplicate-primal-vertex",
    "reversed-primal-face",
    "reversed-dual-face",
    "missing-dual-owner",
    "changed-seal",
)
CORRUPTIONS = (
    "missing-reverse-incidence",
    "duplicated-vertex-incidence",
    "wrong-primal-delta1",
    "wrong-dual-boundary-axis",
    "wrong-selected-pair",
    "wrong-selected-axis-map",
    "default-boundary-partner",
    "wrong-physical-owner",
    "coherent-unused-full-dual-edge",
)
BASE = "native-single-preset-seed17"


def plain(value):
    if is_dataclass(value):
        return {field.name: plain(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): plain(child) for key, child in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(child) for child in value]
    return value


def persist(root, name, value):
    root.mkdir(parents=True, exist_ok=True)
    with (root / (name + ".json")).open("x") as stream:
        json.dump(plain(value), stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def begin(root, case, purpose):
    # Durable declaration precedes loading, binding, candidate construction or
    # any independent worker. An early failure still has its exact case/role.
    state = dict(
        case=case,
        purpose=purpose,
        stage="load_original",
        raw=None,
        request=None,
        candidate=None,
        independent_report=None,
    )
    persist(
        root,
        "declared-input",
        dict(
            case=case,
            purpose=purpose,
            original_run=str(saved.evidence_run()),
            original_review_sha256=saved.REVIEW_SHA256,
            opted_in_law=adapter.LAW_ID,
            native_or_reference_evaluations_authorized_by_test_launch_only=True,
        ),
    )
    return state


def failure(root, state, error):
    persist(
        root,
        "failure",
        dict(
            type=type(error).__name__,
            reason=str(error),
            traceback=traceback.format_exc(),
            state=state,
            rejected_stage=getattr(error, "stage", None),
            rejected_original=getattr(error, "original", None),
            rejected_partial=getattr(error, "partial", None),
            original_saved_evidence=getattr(error, "saved_evidence", None),
        ),
    )


def load(root, state):
    raw = saved.retained_request(state["case"], run=saved.evidence_run())
    state["raw"] = raw
    persist(root, "original-request", raw)
    state["stage"] = "bind"
    return raw


def construct(root, state, raw):
    request = adapter.bind(raw)
    state["request"] = request
    persist(root, "bound-request", request)
    state["stage"] = "candidate"
    candidate = adapter.reconstruct(request)
    state["candidate"] = candidate
    persist(root, "candidate", candidate)
    return request, candidate


def independent(root, state, original, candidate):
    state["stage"] = "independent_geometry"
    persist(root, "independent-input", dict(original=original, candidate=candidate))
    with (root / "independent.stdout.log").open("x") as stream:
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "validation.geometry.stable_mesh_physical_reconstruction_reference",
                "--input",
                str(root / "independent-input.json"),
                "--output",
                str(root / "independent-report.json"),
            ],
            stdout=stream,
            stderr=subprocess.STDOUT,
            timeout=480,
            check=False,
        )
        stream.flush()
        os.fsync(stream.fileno())
    persist(root, "independent-process", dict(returncode=result.returncode))
    if result.returncode != 0:
        raise RuntimeError("Independent worker failed; original input and log are retained")
    report = json.loads((root / "independent-report.json").read_text())
    state["independent_report"] = report
    return report


@pytest.mark.parametrize("case", CANDIDATES)
def test_saved_candidate_and_independent_complex_geometry(case, tmp_path):
    state = begin(tmp_path, case, "prospective corrected topology; not physical admission")
    try:
        raw = load(tmp_path, state)
        before = adapter.digest(raw)
        request, candidate = construct(tmp_path, state, raw)
        report = independent(tmp_path, state, raw["cache"], plain(candidate))
        state["stage"] = "checks"
        assert report["candidate_topology_and_complex_geometry_passed"]
        assert adapter.digest(raw) == before
        assert request.identity == candidate.request_identity
        assert candidate.prerequisites["physical_geometry_admitted"] is False
        assert candidate.prerequisites["ordinary_ECM_loop_ready"] is False
        assert candidate.primal["edges"] == request.original_cache["tri_edges"]
        assert adapter.digest(candidate.geometry) == adapter.digest(
            {key: raw["cache"][key] for key in ("tri_verts", "tri_cells", "vor_verts", "vor_cells")}
        )
        assert candidate.primal["inverse_operators"] is None
        assert candidate.dual["inverse_operators"] is None
        assert candidate.physical_owner_plan["boundary_partner_policy"] is None
        assert candidate.differences["native_equivalence_claimed"] is False
    except Exception as error:
        failure(tmp_path, state, error)
        raise


@pytest.mark.parametrize("case", UNSUPPORTED)
def test_saved_unrepairable_complex_is_retained(case, tmp_path):
    state = begin(tmp_path, case, "missing/nonmanifold owners remain refused")
    try:
        raw = load(tmp_path, state)
        request = adapter.bind(raw)
        state["request"] = request
        persist(tmp_path, "bound-request", request)
        with pytest.raises(adapter.ReconstructionRejected) as caught:
            adapter.reconstruct(request)
        persist(
            tmp_path,
            "expected-refusal",
            dict(
                reason=str(caught.value),
                stage=caught.value.stage,
                original=caught.value.original,
                partial=caught.value.partial,
            ),
        )
        assert caught.value.original is request
    except Exception as error:
        failure(tmp_path, state, error)
        raise


@pytest.mark.parametrize("case", RAW)
def test_original_raw_source_failure_cannot_be_admitted(case, tmp_path):
    state = begin(tmp_path, case, "preserve original source failure")
    try:
        with pytest.raises(ValueError) as caught:
            load(tmp_path, state)
        persist(
            tmp_path,
            "expected-refusal",
            dict(
                reason=str(caught.value),
                original_saved_evidence=getattr(caught.value, "saved_evidence", None),
            ),
        )
    except Exception as error:
        failure(tmp_path, state, error)
        raise


@pytest.mark.parametrize("name", MUTATIONS)
def test_missing_changed_or_ambiguous_owner_is_refused(name, tmp_path):
    state = begin(tmp_path, BASE, "declared owner corruption: " + name)
    try:
        original = load(tmp_path, state)
        raw = deepcopy(original)
        cache = raw["cache"]
        if name == "missing-field":
            del cache["tri_edges"]
        elif name == "wrong-law":
            raw["opted_in_law"] = "native"
        elif name == "wrong-revision":
            raw["evidence"]["source_revision"] = "0" * 40
        elif name == "raw-status":
            raw["evidence"]["original_status"] = "retained_stable_mesh_failure"
        elif name == "missing-occurrence-ID":
            raw["retained_point_ids"].pop()
        elif name == "duplicate-primal-edge":
            cache["tri_edges"].append(cache["tri_edges"][0][:])
        elif name == "missing-primal-edge":
            cache["tri_edges"].pop(0)
        elif name == "duplicate-primal-vertex":
            cache["tri_verts"].append(cache["tri_verts"][0][:])
            raw["retained_point_ids"].append("declared-duplicate-control")
        elif name == "reversed-primal-face":
            cache["tri_cells"][0].reverse()
        elif name == "reversed-dual-face":
            cache["vor_cells"][0].reverse()
        elif name == "missing-dual-owner":
            cache["vor_cells"].pop()
        persist(tmp_path, "changed-request", raw)
        with pytest.raises(ValueError) as caught:
            request = adapter.bind(raw)
            if name == "changed-seal":
                request = replace(request, identity="0" * 64)
            state["request"] = request
            persist(tmp_path, "bound-request", request)
            adapter.reconstruct(request)
        persist(
            tmp_path,
            "expected-refusal",
            dict(
                reason=str(caught.value),
                original=getattr(caught.value, "original", None),
                partial=getattr(caught.value, "partial", None),
            ),
        )
    except Exception as error:
        failure(tmp_path, state, error)
        raise


@pytest.mark.parametrize("name", CORRUPTIONS)
def test_independent_checks_detect_changed_outputs(name, tmp_path):
    state = begin(tmp_path, BASE, "declared output corruption: " + name)
    try:
        raw = load(tmp_path, state)
        _, candidate = construct(tmp_path, state, raw)
        changed = plain(candidate)
        if name == "missing-reverse-incidence":
            changed["primal"]["face_to_edges"][0].pop()
        elif name == "duplicated-vertex-incidence":
            changed["primal"]["vertex_to_edges"][0].append(
                changed["primal"]["vertex_to_edges"][0][0]
            )
        elif name == "wrong-primal-delta1":
            changed["primal"]["delta_1"][0] = [0] * len(changed["primal"]["edges"])
        elif name == "wrong-dual-boundary-axis":
            changed["dual"]["full_boundary_edges"] = [0]
        elif name == "wrong-selected-pair":
            changed["dual"]["selected_edges"][0], changed["dual"]["selected_edges"][1] = (
                changed["dual"]["selected_edges"][1],
                changed["dual"]["selected_edges"][0],
            )
        elif name == "wrong-selected-axis-map":
            changed["dual"]["selected_to_full"][0] = (
                changed["dual"]["selected_to_full"][0] + 1
            ) % len(changed["dual"]["full_edges"])
        elif name == "default-boundary-partner":
            i = changed["physical_owner_plan"]["boundary_membrane_occurrences"][0]
            changed["physical_owner_plan"]["interior_partner_occurrences"][i] = i
        elif name == "wrong-physical-owner":
            changed["physical_owner_plan"]["membrane_to_cells"][0] = (
                changed["physical_owner_plan"]["membrane_to_cells"][0] + 1
            ) % len(changed["geometry"]["vor_cells"])
        elif name == "coherent-unused-full-dual-edge":
            dual = changed["dual"]
            count = len(changed["geometry"]["vor_verts"])
            existing = {tuple(sorted(edge)) for edge in dual["full_edges"]}
            a, b = next(
                (a, b)
                for a in range(count)
                for b in range(a + 1, count)
                if (a, b) not in existing
            )
            # Preserve matching dimensions and boundary-of-boundary: only the
            # independently derived inventory exposes this unowned extra edge.
            dual["full_edges"].append([a, b])
            dual["full_edge_owner_occurrences"].append([])
            dual["full_delta_0"].append([int(v == b) - int(v == a) for v in range(count)])
            for row in dual["full_polygon_delta_1"]:
                row.append(0)
            dual["full_to_selected"].append([])
        persist(tmp_path, "changed-candidate", changed)
        report = independent(tmp_path, state, raw["cache"], changed)
        assert report["candidate_topology_and_complex_geometry_passed"] is False
        assert any(not row["passed"] for row in report["exact_topology_checks"])
        if name == "coherent-unused-full-dual-edge":
            assert any(
                row["check"] == "full_dual_edge_inventory" and not row["passed"]
                for row in report["exact_topology_checks"]
            )
    except Exception as error:
        failure(tmp_path, state, error)
        raise


def test_candidate_cannot_be_used_as_initialized_physical_geometry(tmp_path):
    state = begin(tmp_path, BASE, "explicit physical-admission guard")
    try:
        raw = load(tmp_path, state)
        _, candidate = construct(tmp_path, state, raw)
        with pytest.raises(adapter.ReconstructionRejected) as caught:
            adapter.require_physical_admission(candidate)
        persist(
            tmp_path,
            "expected-refusal",
            dict(
                reason=str(caught.value),
                stage=caught.value.stage,
                original=caught.value.original,
                partial=caught.value.partial,
            ),
        )
    except Exception as error:
        failure(tmp_path, state, error)
        raise
