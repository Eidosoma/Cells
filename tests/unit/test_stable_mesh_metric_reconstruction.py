"""Prospective metric panel; saved declarations precede every operation."""

import hashlib
import json
import os
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from cells.processes import stable_mesh_metric_reconstruction as metric
from cells.processes import stable_mesh_physical_reconstruction as topology
from tests.unit import test_stable_mesh_physical_reconstruction as archives
from validation.geometry import stable_mesh_metric_reconstruction_checks as checks
from validation.geometry import stable_mesh_physical_reconstruction_saved as saved

CANDIDATES = ("caller-square-zero",)
DOMAIN_REFUSALS = (
    "irregular-centroid-aux",
    "native-single-preset-seed17",
    "native-single-preset-seed23",
    "caller-single-square-cache",
    "caller-single-hex-cache",
)
DOMAIN_ROSTER_SHA256 = "43c6c6b8e1dbd3bc375672a985231cf3f065d5cd8bba4eb7028ff2781aaec86c"
REFUSALS = (
    "wrong-units",
    "wrong-law",
    "wrong-layout",
    "circumcenter-mode",
    "missing-centres",
    "changed-parent",
    "changed-topology",
)
ROLE_CONTROLS = ("missing", "unequal", "equal-coalesced")
RESEALED_CONTROLS = ("units", "mode")
CORRUPTIONS = (
    "area",
    "length",
    "tangent",
    "full-normal",
    "reference-area",
    "stored-coefficient",
    "geometric-ratio",
    "role-owner",
    "certificate",
    "structured-certificate",
    "unused-arithmetic",
)
COVERAGE_CORRUPTIONS = (
    "empty-all",
    "coherent-truncated-owner",
    "missing-scalar-slot",
    "extra-scalar-slot",
    "extra-owner-row",
    "missing-group",
    "extra-group",
)
BASE = "caller-square-zero"


def declaration():
    return dict(
        kind=metric.INPUT_KIND,
        opted_in_law=metric.LAW_ID,
        units=metric.UNITS.copy(),
        layout_policy="preserve_source_centroid_and_reflection_coordinates",
    )


def begin(root, case, purpose):
    state = dict(
        case=case,
        purpose=purpose,
        stage="original_input",
        raw=None,
        parent=None,
        corrected=None,
        request=None,
        candidate=None,
        references=[],
    )
    archives.persist(
        root,
        "declared-input",
        dict(
            case=case,
            purpose=purpose,
            metric_declaration=declaration(),
            source_run=str(saved.evidence_run()),
            source_review_sha256=saved.REVIEW_SHA256,
            launch_authority="Chief/Root; no automatic execution",
        ),
    )
    return state


def load(root, state, mutation=None):
    state["raw"] = saved.retained_request(state["case"], run=saved.evidence_run())
    archives.persist(root, "original-request", state["raw"])
    raw = deepcopy(state["raw"])
    if mutation == "circumcenter-mode":
        raw["cache"]["use_centroids"] = False
    elif mutation == "missing-centres":
        del raw["cache"]["tri_cents"]
    if mutation:
        archives.persist(root, "declared-changed-input", raw)
    state["stage"] = "corrected_topology"
    parent = topology.bind(raw)
    state["parent"] = parent
    archives.persist(root, "topology-request", parent)
    corrected = topology.reconstruct(parent)
    state["corrected"] = corrected
    archives.persist(root, "corrected-topology", corrected)
    return parent, corrected


def construct(root, state):
    parent, corrected = load(root, state)
    state["stage"] = "metric_bind"
    request = metric.bind(parent, corrected, declaration())
    state["request"] = request
    archives.persist(root, "metric-request", request)
    state["stage"] = "metric_prepare"
    candidate = metric.prepare(request)
    state["candidate"] = candidate
    archives.persist(root, "metric-candidate", candidate)
    return parent, corrected, request, candidate


def references(root, state, payload, *, refused=False):
    state["stage"] = "independent_reference"
    archives.persist(root, "reference-input", payload)
    result = []
    for refinement in (1, 2):
        path = root / ("reference-" + str(refinement) + ".json")
        with (root / ("reference-" + str(refinement) + ".stdout.log")).open("x") as stream:
            process = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "validation.geometry.stable_mesh_metric_reconstruction_reference",
                    "--input",
                    str(root / "reference-input.json"),
                    "--output",
                    str(path),
                    "--refinement",
                    str(refinement),
                ],
                stdout=stream,
                stderr=subprocess.STDOUT,
                timeout=480,
                check=False,
            )
            stream.flush()
            os.fsync(stream.fileno())
        archives.persist(
            root, "reference-process-" + str(refinement), dict(returncode=process.returncode)
        )
        report = json.loads(path.read_text()) if path.is_file() else None
        state["references"].append(report)
        if refused:
            assert process.returncode != 0 and report["status"] == "reference_failed"
        elif process.returncode != 0 or report is None:
            raise RuntimeError(
                "Independent reference failed; input/log/report/partial are retained"
            )
        result.append(report)
    return result


@pytest.mark.parametrize("case", CANDIDATES)
def test_preserved_layout_and_independent_metrics(case, tmp_path):
    state = begin(tmp_path, case, "prospective conditional metrics on unchanged coordinates")
    try:
        parent, corrected, request, candidate = construct(tmp_path, state)
        original = metric.digest((parent, corrected, request))
        refs = references(
            tmp_path,
            state,
            dict(
                source_cache=archives.plain(parent.original_cache),
                corrected=archives.plain(corrected),
            ),
        )
        state["stage"] = "comparison"
        report = checks.compare(archives.plain(candidate), *refs)
        archives.persist(tmp_path, "comparison", report)
        assert report["passed"]
        assert original == metric.digest((parent, corrected, request))
        assert candidate.topology_identity == corrected.identity
        assert candidate.prerequisites["physical_geometry_admitted"] is False
        assert candidate.prerequisites["inverse_operators"] is None
        assert candidate.prerequisites["physical_cell_geometry"] is None
        assert (
            candidate.native_roles["tri_ccents"] is None
            and candidate.native_roles["tri_rcircs"] is None
        )
        assert candidate.diagnostics["coordinate_bits_preserved"] is True
    except Exception as error:
        archives.failure(tmp_path, state, error)
        raise


@pytest.mark.parametrize("name", REFUSALS)
def test_explicit_units_layout_and_parent_admission(name, tmp_path):
    state = begin(tmp_path, BASE, "declared input control: " + name)
    try:
        parent, corrected = load(
            tmp_path, state, name if name in ("circumcenter-mode", "missing-centres") else None
        )
        declared = declaration()
        if name == "wrong-units":
            declared["units"]["edge_lengths"] = "cm"
        elif name == "wrong-law":
            declared["opted_in_law"] = "native"
        elif name == "wrong-layout":
            declared["layout_policy"] = "move_to_new_exact_centres"
        elif name == "changed-parent":
            parent = replace(parent, identity="0" * 64)
        elif name == "changed-topology":
            corrected = replace(corrected, identity="0" * 64)
        archives.persist(
            tmp_path,
            "binding-input",
            dict(parent=parent, corrected=corrected, declaration=declared),
        )
        with pytest.raises(ValueError) as caught:
            metric.bind(parent, corrected, declared)
        archives.persist(
            tmp_path,
            "expected-refusal",
            dict(
                reason=str(caught.value),
                original=getattr(caught.value, "original", None),
                partial=getattr(caught.value, "partial", None),
            ),
        )
    except Exception as error:
        archives.failure(tmp_path, state, error)
        raise


@pytest.mark.parametrize("name", ROLE_CONTROLS)
def test_reference_area_owners_are_explicit(name, tmp_path):
    state = begin(tmp_path, BASE, "reference-area role helper control: " + name)
    try:
        roles = [[]] if name == "missing" else [[dict(face=0), dict(face=1)]]
        areas = [(Fraction(1), ()), (Fraction(2 if name == "unequal" else 1), ())]
        archives.persist(
            tmp_path,
            "role-control-input",
            dict(roles=roles, exact_areas=[str(a) for a, _ in areas]),
        )
        if name == "equal-coalesced":
            values = metric._coalesce_roles(roles, areas)
            assert values == [Fraction(1)]
            archives.persist(
                tmp_path, "coalesced-area", dict(exact_area=str(values[0]), summed=False)
            )
        else:
            with pytest.raises(ValueError) as caught:
                metric._coalesce_roles(roles, areas)
            archives.persist(
                tmp_path,
                "expected-refusal",
                dict(
                    reason=str(caught.value),
                    detail=metric.plain(getattr(caught.value, "detail", None)),
                ),
            )
    except Exception as error:
        archives.failure(tmp_path, state, error)
        raise


@pytest.mark.parametrize("name", RESEALED_CONTROLS)
def test_resealed_metric_requests_are_revalidated(name, tmp_path):
    state = begin(tmp_path, BASE, "declared resealed request control: " + name)
    try:
        parent, corrected = load(tmp_path, state)
        request = metric.bind(parent, corrected, declaration())
        state["request"] = request
        if name == "units":
            changed = metric.plain(request.declaration)
            changed["units"]["polygon_areas"] = "cm2"
            request = replace(request, declaration=topology.freeze(changed), identity="")
        else:
            raw = deepcopy(state["raw"])
            raw["cache"]["use_centroids"] = False
            changed_parent = topology.bind(raw)
            changed_topology = topology.reconstruct(changed_parent)
            request = replace(
                request,
                topology_request=changed_parent,
                topology_candidate=changed_topology,
                identity="",
            )
        request = replace(request, identity=metric.digest(metric.request_record(request)))
        archives.persist(tmp_path, "resealed-request", request)
        with pytest.raises(ValueError) as caught:
            metric.prepare(request)
        archives.persist(
            tmp_path,
            "expected-refusal",
            dict(
                reason=str(caught.value),
                original=getattr(caught.value, "original", None),
                partial=getattr(caught.value, "partial", None),
            ),
        )
    except Exception as error:
        archives.failure(tmp_path, state, error)
        raise


def test_unrepresentable_scalar_retains_arithmetic_trial(tmp_path):
    state = begin(tmp_path, BASE, "raw helper underflow; no mesh accuracy credit")
    try:
        target = Fraction(1, 1 << 2200)
        archives.persist(
            tmp_path,
            "scalar-input",
            dict(numerator=str(target.numerator), denominator=str(target.denominator)),
        )
        work = metric._Work()
        with pytest.raises(ValueError) as caught:
            work.root(target, "retained_unrepresentable_length_m")
        archives.persist(
            tmp_path,
            "expected-refusal",
            dict(
                reason=str(caught.value),
                events=work.events,
                detail=metric.plain(getattr(caught.value, "detail", None)),
                trial=metric.plain(getattr(caught.value, "trial", None)),
            ),
        )
        assert work.events[0]["failure"] and "returned" not in work.events[0]
    except Exception as error:
        archives.failure(tmp_path, state, error)
        raise


@pytest.mark.parametrize("name", CORRUPTIONS)
def test_independent_metric_and_certificate_gates(name, tmp_path):
    state = begin(tmp_path, BASE, "declared outgoing corruption: " + name)
    try:
        parent, corrected, _, candidate = construct(tmp_path, state)
        changed = archives.plain(candidate)
        if name == "area":
            changed["native_roles"]["vor_sa"][0] *= 1.01
        elif name == "length":
            changed["native_roles"]["tri_edge_len"][0] *= 1.01
        elif name == "tangent":
            changed["native_roles"]["vor_tang"][0][0] += 0.01
        elif name == "full-normal":
            changed["full_dual_metrics"][0]["normal_xy"][0] += 0.01
        elif name == "reference-area":
            changed["native_roles"]["tri_sa_o"][0] *= 1.01
        elif name == "stored-coefficient":
            changed["coefficients"]["native_stored_dual_over_primal"][0] *= 1.01
        elif name == "geometric-ratio":
            changed["coefficients"]["coordinate_geometric_length_ratio"][0] *= 1.01
        elif name == "role-owner":
            changed["anchor_roles"][0][0]["face"] = (
                changed["anchor_roles"][0][0]["face"] + 1
            ) % len(parent.original_cache["tri_cells"])
        elif name == "certificate":
            changed["certificates"]["arithmetic_events"][0]["returned"]["certificate"]["exact"][
                "numerator"
            ] = "0"
        elif name == "structured-certificate":
            changed["certificates"]["primal_polygons"][0]["area"]["exact"]["numerator"] = "0"
        elif name == "unused-arithmetic":
            extra = deepcopy(changed["certificates"]["arithmetic_events"][0])
            extra["sequence"] = len(changed["certificates"]["arithmetic_events"])
            extra["returned"]["certificate"]["arithmetic_event_index"] = extra["sequence"]
            changed["certificates"]["arithmetic_events"].append(extra)
        archives.persist(tmp_path, "changed-metric-output", changed)
        refs = references(
            tmp_path,
            state,
            dict(
                source_cache=archives.plain(parent.original_cache),
                corrected=archives.plain(corrected),
            ),
        )
        require_positive_baseline(tmp_path, candidate, refs)
        report = checks.compare(changed, *refs)
        archives.persist(tmp_path, "comparison", report)
        assert report["passed"] is False
    except Exception as error:
        archives.failure(tmp_path, state, error)
        raise


def cohere_certificate_ledger(certs):
    """Keep each surviving/extra scalar valid while changing evidence coverage."""
    original = certs["arithmetic_events"]
    events = []

    def visit(value):
        if isinstance(value, dict):
            if "arithmetic_event_index" in value:
                event = deepcopy(original[value["arithmetic_event_index"]])
                index = len(events)
                value["arithmetic_event_index"] = index
                event["sequence"] = index
                event["returned"]["certificate"]["arithmetic_event_index"] = index
                events.append(event)
            else:
                for child in value.values():
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    for group, rows in certs.items():
        if group != "arithmetic_events":
            visit(rows)
    certs["arithmetic_events"] = events


@pytest.mark.parametrize("name", COVERAGE_CORRUPTIONS)
def test_complete_certificate_owner_axes_and_scalar_slots(name, tmp_path):
    state = begin(tmp_path, BASE, "declared certificate coverage control: " + name)
    try:
        parent, corrected, _, candidate = construct(tmp_path, state)
        changed = archives.plain(candidate)
        certs = changed["certificates"]
        if name == "empty-all":
            for group in certs:
                certs[group] = []
        elif name == "coherent-truncated-owner":
            certs["primal_polygons"].pop()
            cohere_certificate_ledger(certs)
        elif name == "missing-scalar-slot":
            del certs["primal_polygons"][0]["area"]
            cohere_certificate_ledger(certs)
        elif name == "extra-scalar-slot":
            certs["primal_polygons"][0]["centroid"].append(
                deepcopy(certs["primal_polygons"][0]["centroid"][0])
            )
            cohere_certificate_ledger(certs)
        elif name == "extra-owner-row":
            certs["primal_polygons"].append(deepcopy(certs["primal_polygons"][-1]))
            cohere_certificate_ledger(certs)
        elif name == "missing-group":
            del certs["inverse_dual_area"]
            cohere_certificate_ledger(certs)
        elif name == "extra-group":
            certs["unexpected_group"] = []
        archives.persist(tmp_path, "changed-certificate-coverage-output", changed)
        refs = references(
            tmp_path,
            state,
            dict(
                source_cache=archives.plain(parent.original_cache),
                corrected=archives.plain(corrected),
            ),
        )
        require_positive_baseline(tmp_path, candidate, refs)
        report = checks.compare(changed, *refs)
        archives.persist(tmp_path, "coverage-comparison", report)
        assert report["passed"] is False
        assert any(
            row["label"] == "complete_source_owner_certificate_contract" and row["passed"] is False
            for row in report["arithmetic_certificates"]
        )
    except Exception as error:
        archives.failure(tmp_path, state, error)
        raise


def test_coherent_extra_full_edge_is_refused_independently(tmp_path):
    state = begin(tmp_path, BASE, "coherent unused-edge corruption; no new geometry case")
    try:
        parent, corrected, _, _ = construct(tmp_path, state)
        changed = archives.plain(corrected)
        present = {tuple(sorted(row)) for row in changed["dual"]["full_edges"]}
        n = len(changed["geometry"]["vor_verts"])
        a, b = next((a, b) for a in range(n) for b in range(a + 1, n) if (a, b) not in present)
        changed["dual"]["full_edges"].append([a, b])
        changed["dual"]["full_edge_owner_occurrences"].append([])
        changed["dual"]["full_to_selected"].append([])
        changed["dual"]["full_delta_0"].append([int(v == b) - int(v == a) for v in range(n)])
        for row in changed["dual"]["full_polygon_delta_1"]:
            row.append(0)
        archives.persist(tmp_path, "changed-corrected-topology", changed)
        refs = references(
            tmp_path,
            state,
            dict(source_cache=archives.plain(parent.original_cache), corrected=changed),
            refused=True,
        )
        assert all("exact original ring union" in row["reason"] for row in refs)
    except Exception as error:
        archives.failure(tmp_path, state, error)
        raise


def test_metrics_do_not_admit_initialized_physical_geometry(tmp_path):
    state = begin(tmp_path, BASE, "physical admission remains refused")
    try:
        _, _, _, candidate = construct(tmp_path, state)
        with pytest.raises(metric.MetricRejected) as caught:
            metric.require_physical_admission(candidate)
        archives.persist(
            tmp_path,
            "expected-refusal",
            dict(
                reason=str(caught.value),
                original=caught.value.original,
                partial=caught.value.partial,
            ),
        )
    except Exception as error:
        archives.failure(tmp_path, state, error)
        raise


def domain_roster():
    path = (
        Path(__file__).resolve().parents[2]
        / "validation/geometry/stable_mesh_metric_reconstruction_domain_roster.json"
    )
    if hashlib.sha256(path.read_bytes()).hexdigest() != DOMAIN_ROSTER_SHA256:
        raise ValueError("Changed reviewed domain roster or baseline probe binding")
    return json.loads(path.read_text())


def require_positive_baseline(root, candidate, refs):
    """A rejected output is control evidence only when this reference pair accepts its source."""
    report = checks.compare(archives.plain(candidate), *refs)
    archives.persist(root, "positive-baseline-comparison", report)
    assert report["passed"] is True, "Broken positive reference baseline earns no control credit"
    return report


@pytest.mark.parametrize("case", DOMAIN_REFUSALS)
def test_retained_source_domain_refusals_are_explicit(case, tmp_path):
    state = begin(tmp_path, case, "retained source domain refusal; no metric pass credit")
    try:
        roster = domain_roster()
        row = next(row for row in roster["cases"] if row["case"] == case)
        archives.persist(tmp_path, "reviewed-domain-witness", row)
        assert row["role"] == "retained_source_domain_refusal"
        assert row["diagnostic_witness"]["noninterior_owners"]
        with pytest.raises(metric.MetricRejected) as caught:
            construct(tmp_path, state)
        error = caught.value
        archives.persist(
            tmp_path,
            "expected-domain-refusal",
            dict(
                stage=error.stage,
                reason=str(error),
                original=error.original,
                partial=error.partial,
                reviewed_case=case,
                original_metric02_failed_run_reclassified=False,
                metric_qualification_credit=False,
                physical_geometry_admitted=False,
            ),
        )
        assert error.stage == "global_polygon_domains"
        assert error.partial["source_error"]["reason"] == (
            "Source seed owner is not strictly inside its retained dual polygon"
        )
        assert state["candidate"] is None and state["references"] == []
        assert state["request"] is not None
        assert metric.digest(error.original) == metric.digest(state["request"])
        actual = archives.plain(state["corrected"])
        reviewed = row["retained_topology_candidate"]
        context_fields = {"identity", "request_identity"}
        actual_payload = {key: value for key, value in actual.items() if key not in context_fields}
        reviewed_payload = {
            key: value for key, value in reviewed.items() if key not in context_fields
        }
        archives.persist(
            tmp_path,
            "domain-parent-context",
            dict(
                actual_identity=actual["identity"],
                actual_request_identity=actual["request_identity"],
                reviewed_identity=reviewed["identity"],
                reviewed_request_identity=reviewed["request_identity"],
                separately_bound_context_fields=sorted(context_fields),
                actual_payload_digest=metric.digest(actual_payload),
                reviewed_payload_digest=metric.digest(reviewed_payload),
                full_original_records=["corrected-topology.json", "reviewed-domain-witness.json"],
            ),
        )
        assert set(actual) == set(reviewed)
        assert actual["request_identity"] == state["parent"].identity
        assert actual["identity"] == topology.digest(topology.candidate_record(state["corrected"]))
        assert reviewed["identity"] == row["diagnostic_witness"]["candidate_identity"]
        assert reviewed["identity"] == metric.digest(
            (
                topology.LAW_ID,
                reviewed["request_identity"],
                reviewed["geometry"],
                reviewed["primal"],
                reviewed["dual"],
                reviewed["physical_owner_plan"],
                reviewed["differences"],
                reviewed["prerequisites"],
            )
        )
        assert metric.digest(actual_payload) == metric.digest(reviewed_payload)
    except Exception as error:
        archives.failure(tmp_path, state, error)
        raise
