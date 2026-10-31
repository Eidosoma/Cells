"""Proposed exact graph/cache checks; no test is collected during preparation."""

import json
import math
import os
import subprocess
import sys
import traceback
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction

import pytest

from cells.processes import stable_mesh_metric_reconstruction as metric
from cells.processes import stable_mesh_operator_reconstruction as operators
from cells.processes import stable_mesh_operator_reconstruction_algebra as algebra
from cells.processes import stable_mesh_physical_reconstruction as topology
from tests.unit import test_stable_mesh_metric_reconstruction as parents

CANDIDATES = ("caller-square-zero",)
DOMAIN_REFUSALS = (
    "irregular-centroid-aux",
    "native-single-preset-seed17",
    "native-single-preset-seed23",
    "caller-single-square-cache",
    "caller-single-hex-cache",
)
REFUSALS = (
    "wrong-law",
    "wrong-units",
    "Dirichlet-policy",
    "regularization",
    "SVD-threshold",
    "parent-qualification",
    "changed-metric-identity",
    "resealed-metric-store",
    "changed-topology-identity",
    "resealed-boundary",
    "resealed-regularization",
    "resealed-units",
    "changed-baseline-review",
    "resealed-baseline-payload",
    "old-parent-status",
)
CORRUPTIONS = (
    "exact-pinv",
    "rounded-forward",
    "source-factorized-map",
    "vertex-nullspace",
    "cycle-nullspace",
    "rank",
    "source-area-defect",
    "source-hodge-seam",
    "empty-scalar-evidence",
    "truncated-coherent-scalars",
    "coherent-wrong-scalar-target",
    "empty-pivot-journal",
    "changed-pivot-input",
    "physical-promotion",
    "extra-scalar-event",
    "missing-matrix",
)
RAW_ALGEBRA = (
    "zero-rank",
    "disconnected",
    "dependent-rows",
    "singular-inverse",
    "factorized-map-distinct",
    "area-conservation-seam",
)
BASE = "caller-square-zero"


def declaration():
    return dict(
        kind=operators.INPUT_KIND,
        opted_in_law=operators.LAW_ID,
        units=operators.UNITS.copy(),
        boundary_policy="primal_closed_graph_no_Dirichlet_injection",
        rank_policy="exact_unweighted_Moore_Penrose_no_cutoff",
        regularization=None,
        parent_status="explicit_reviewed_square_metric03_baseline_no_physical_qualification",
        parent_baseline=operators.BASELINE_BINDING.copy(),
    )


def persist(root, name, value):
    parents.archives.persist(root, name, operators.plain(value))


def begin(root, case, purpose):
    persist(
        root,
        "operator-declared-input",
        dict(
            case=case,
            purpose=purpose,
            declaration=declaration(),
            source_status="explicit_reviewed_square_metric03_baseline_no_physical_qualification",
            physical_admission=False,
            original_complete_geometries="0/9; unchanged",
            new_biological_cases=0,
            launch_owner="Chief/Root; no automatic execution",
        ),
    )
    return dict(
        case=case,
        purpose=purpose,
        stage="declared",
        metric_state=None,
        request=None,
        candidate=None,
        reference=None,
    )


def failure(root, state, error):
    try:
        persist(
            root,
            "operator-failure",
            dict(
                state=state,
                type=type(error).__name__,
                reason=str(error),
                traceback=traceback.format_exc(),
                original=getattr(error, "original", None),
                partial=getattr(error, "partial", None),
                detail=getattr(error, "detail", None),
            ),
        )
    except BaseException as capture_error:
        error.add_note("Operator failure sidecar also failed: " + repr(capture_error))
        try:
            with (root / "operator-failure-capture-error.json").open("x") as stream:
                json.dump(
                    dict(
                        original_type=type(error).__name__,
                        original_message=str(error),
                        capture_type=type(capture_error).__name__,
                        capture_message=str(capture_error),
                    ),
                    stream,
                )
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException as fallback:
            error.add_note("Operator failure fallback also failed: " + repr(fallback))


def construct(root, state):
    parent_state = parents.begin(
        root, state["case"], "conditional metric parents for graph operators"
    )
    state["metric_state"] = parent_state
    _, _, request, candidate = parents.construct(root, parent_state)
    state["stage"] = "operator_bind"
    persist(
        root,
        "operator-bind-input",
        dict(metric_request=request, metric_candidate=candidate, declaration=declaration()),
    )
    bound = operators.bind(request, candidate, declaration())
    state["request"] = bound
    persist(root, "operator-request", bound)
    state["stage"] = "operator_prepare"
    count = [0]

    def observer(stage, value):
        persist(root, "operator-stage-" + str(count[0]) + "-" + stage, value)
        count[0] += 1

    result = operators.prepare(bound, observer=observer)
    state["candidate"] = result
    persist(root, "operator-candidate", result)
    return bound, result


def independent(root, state, request, candidate, *, baseline=None):
    state["stage"] = "independent_exact_reference"
    payload = dict(request=request, candidate=candidate)
    if baseline is not None:
        payload["baseline"] = baseline
    persist(root, "operator-reference-input", payload)
    path = root / "operator-reference-output.json"
    parent_pid = os.getpid()
    with (root / "operator-reference.stdout.log").open("x") as stream:
        try:
            process = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "validation.geometry.stable_mesh_operator_reconstruction_reference",
                    "--input",
                    str(root / "operator-reference-input.json"),
                    "--output",
                    str(path),
                ],
                stdout=stream,
                stderr=subprocess.STDOUT,
                timeout=480,
                check=False,
            )
        except Exception as error:
            persist(
                root,
                "operator-reference-process-failure",
                dict(type=type(error).__name__, reason=str(error)),
            )
            raise
        finally:
            stream.flush()
            os.fsync(stream.fileno())
    persist(root, "operator-reference-process", dict(returncode=process.returncode))
    report = json.loads(path.read_text()) if path.is_file() else None
    state["reference"] = report
    if report is None:
        raise RuntimeError("Reference input/log/process receipt retained; no complete report")
    assert report["runtime_origin"]["parent_pid"] == parent_pid
    assert report["runtime_origin"]["pid"] != parent_pid
    assert process.returncode == 0
    assert report["baseline_passed"] is True
    if baseline is None:
        assert report["candidate_passed"] is True
    else:
        assert report["control_detected"] is True and report["candidate_passed"] is False
    return report


@pytest.mark.parametrize("case", CANDIDATES)
def test_conditional_primal_graph_and_independent_algebra(case, tmp_path):
    state = begin(
        tmp_path, case, "exact source factorization; no physical/native cache qualification"
    )
    try:
        request, candidate = construct(tmp_path, state)
        original = operators.digest(request)
        independent(tmp_path, state, request, candidate)
        assert operators.digest(request) == original
        assert candidate.prerequisites["weighted_laplacian_inverse_admitted"] is False
        assert candidate.prerequisites["physical_geom_weight"] is None
        assert candidate.prerequisites["ordinary_ECM_loop_ready"] is False
    except Exception as error:
        failure(tmp_path, state, error)
        raise


@pytest.mark.parametrize("name", REFUSALS)
def test_unsupported_policies_and_changed_parent_stores_refuse(name, tmp_path):
    state = begin(tmp_path, BASE, "declared request control: " + name)
    try:
        bound, baseline = construct(tmp_path, state)
        persist(tmp_path, "accepted-constructor-baseline", baseline)
        mreq, mcandidate, declared = bound.metric_request, bound.metric_candidate, declaration()
        if name == "wrong-law":
            declared["opted_in_law"] = "native_qualified"
        elif name == "wrong-units":
            declared["units"]["area"] = "cm2"
        elif name == "Dirichlet-policy":
            declared["boundary_policy"] = "Dirichlet"
        elif name == "regularization":
            declared["regularization"] = 1e-12
        elif name == "SVD-threshold":
            declared["rank_policy"] = "relative_SVD_cutoff"
        elif name == "parent-qualification":
            declared["parent_status"] = "already_qualified"
        elif name == "changed-metric-identity":
            mcandidate = replace(mcandidate, identity="0" * 64)
        elif name == "resealed-metric-store":
            native = metric.plain(mcandidate.native_roles)
            native["vor_sa"][0] *= 1.01
            mcandidate = replace(mcandidate, native_roles=topology.freeze(native), identity="")
            mcandidate = replace(
                mcandidate, identity=metric.digest(metric.candidate_record(mcandidate))
            )
        elif name == "changed-topology-identity":
            mreq = replace(
                mreq, topology_candidate=replace(mreq.topology_candidate, identity="0" * 64)
            )
        elif name == "resealed-boundary":
            declared["boundary_policy"] = "Dirichlet"
        elif name == "resealed-regularization":
            declared["regularization"] = 1e-12
        elif name == "resealed-units":
            declared["units"]["inverse_area"] = "1/cm2"
        elif name == "changed-baseline-review":
            declared["parent_baseline"]["probe_review_sha256"] = "0" * 64
        elif name == "resealed-baseline-payload":
            declared["parent_baseline"]["metric_payload_sha256"] = "0" * 64
        elif name == "old-parent-status":
            declared["parent_status"] = "conditional_unqualified_topology02_metric02"
        persist(
            tmp_path,
            "declared-operator-control-input",
            dict(metric_request=mreq, metric_candidate=mcandidate, declaration=declared),
        )
        if name.startswith("resealed-") and name != "resealed-metric-store":
            changed = replace(bound, declaration=topology.freeze(declared), identity="")
            changed = replace(changed, identity=operators.digest(operators.request_record(changed)))
            persist(tmp_path, "resealed-operator-request", changed)
            with pytest.raises(operators.OperatorRejected) as caught:
                operators.prepare(changed)
            assert caught.value.stage == "request"
        else:
            with pytest.raises(ValueError) as caught:
                operators.bind(mreq, mcandidate, declared)
        persist(
            tmp_path,
            "expected-operator-refusal",
            dict(
                reason=str(caught.value),
                original=getattr(caught.value, "original", None),
                partial=getattr(caught.value, "partial", None),
            ),
        )
    except Exception as error:
        failure(tmp_path, state, error)
        raise


def change_exact(matrix, row=0, column=0):
    scalar = matrix["data"][row][column]
    value = Fraction(int(scalar["numerator"]), int(scalar["denominator"])) + 1
    matrix["data"][row][column] = operators.plain(value)


def reseal(changed):
    candidate = operators.Candidate(
        **{name: topology.freeze(value) for name, value in changed.items()}
    )
    return replace(candidate, identity=operators.digest(operators.candidate_record(candidate)))


def cohere_scalars(changed):
    certs = changed["certificates"]
    original, events = certs["arithmetic_events"], []
    for slots in certs["matrix_event_indices"].values():
        for row in slots:
            for column, old in enumerate(row):
                event = deepcopy(original[old])
                row[column] = len(events)
                event["sequence"] = len(events)
                event["returned"]["certificate"]["event_index"] = len(events)
                events.append(event)
    certs["arithmetic_events"] = events


@pytest.mark.parametrize("name", CORRUPTIONS)
def test_resealed_corruption_requires_a_passing_independent_baseline(name, tmp_path):
    state = begin(tmp_path, BASE, "declared corruption with same-worker positive baseline: " + name)
    try:
        request, candidate = construct(tmp_path, state)
        changed = operators.plain(candidate)
        certs = changed["certificates"]
        if name == "exact-pinv":
            change_exact(changed["exact_matrices"]["delta_tri_0_inv"])
        elif name == "rounded-forward":
            changed["rounded_matrices"]["lapGJ"][0][0] = math.nextafter(
                changed["rounded_matrices"]["lapGJ"][0][0], math.inf
            )
        elif name == "source-factorized-map":
            change_exact(changed["exact_matrices"]["lapGJinv"])
        elif name == "vertex-nullspace":
            change_exact(changed["algebra"]["vertex_nullspace"])
        elif name == "cycle-nullspace":
            change_exact(changed["algebra"]["edge_cycle_nullspace"])
        elif name == "rank":
            changed["algebra"]["rank"] += 1
        elif name == "source-area-defect":
            change_exact(changed["diagnostics"]["source_area_forward_conservation_defect"])
        elif name == "source-hodge-seam":
            changed["source_diagonals"]["star_eij_inv"]["values"][0] *= 1.01
        elif name == "empty-scalar-evidence":
            certs["arithmetic_events"] = []
            certs["matrix_event_indices"] = {key: [] for key in certs["matrix_event_indices"]}
        elif name == "truncated-coherent-scalars":
            certs["matrix_event_indices"]["stiffness"].pop()
            cohere_scalars(changed)
        elif name == "coherent-wrong-scalar-target":
            event = next(
                row
                for row in certs["arithmetic_events"]
                if row["matrix"] == "delta_tri_0" and row["input_exact"]["numerator"] != "0"
            )
            exact = event["input_exact"]
            target = Fraction(int(exact["numerator"]), int(exact["denominator"])) + Fraction(
                1, 1 << 60
            )
            event["input_exact"] = operators.plain(target)
            event["returned"]["certificate"]["exact"] = operators.plain(target)
        elif name == "empty-pivot-journal":
            certs["algebra_pivots"] = []
        elif name == "changed-pivot-input":
            change_exact(certs["algebra_pivots"][0]["before"])
        elif name == "physical-promotion":
            changed["prerequisites"]["physical_geometry_admitted"] = True
        elif name == "extra-scalar-event":
            extra = deepcopy(certs["arithmetic_events"][0])
            extra["sequence"] = len(certs["arithmetic_events"])
            extra["returned"]["certificate"]["event_index"] = extra["sequence"]
            certs["arithmetic_events"].append(extra)
        elif name == "missing-matrix":
            for group in ("exact_matrices", "rounded_matrices"):
                del changed[group]["L2_inv"]
            del certs["matrix_event_indices"]["L2_inv"]
            del changed["diagnostics"]["storage_errors"]["L2_inv"]
            cohere_scalars(changed)
        changed = reseal(changed)
        persist(tmp_path, "resealed-corrupted-operator-output", changed)
        independent(tmp_path, state, request, changed, baseline=candidate)
    except Exception as error:
        failure(tmp_path, state, error)
        raise


@pytest.mark.parametrize("name", RAW_ALGEBRA)
def test_explicit_singular_components_and_source_map_defects(name, tmp_path):
    state = begin(tmp_path, "raw-algebra-only", "raw exact control, no mesh/science case: " + name)
    journal = []
    state["raw_pivots"] = journal
    try:
        if name == "zero-rank":
            value = algebra.zeros(2, 3)
            expected = algebra.zeros(3, 2)
        elif name == "disconnected":
            value = algebra.matrix([[-1, 1, 0, 0], [0, 0, -1, 1]])
            expected = algebra.matrix(
                [
                    [Fraction(-1, 2), 0],
                    [Fraction(1, 2), 0],
                    [0, Fraction(-1, 2)],
                    [0, Fraction(1, 2)],
                ]
            )
        elif name == "dependent-rows":
            value = algebra.matrix([[-1, 1, 0], [-2, 2, 0], [0, 0, 0]])
            expected = algebra.matrix(
                [
                    [Fraction(-1, 10), Fraction(-1, 5), 0],
                    [Fraction(1, 10), Fraction(1, 5), 0],
                    [0, 0, 0],
                ]
            )
        elif name == "singular-inverse":
            value = algebra.matrix([[1, 1], [2, 2]])
            persist(
                tmp_path, "raw-exact-input", dict(matrix=value, ordinary_inverse_requested=True)
            )
            with pytest.raises(ValueError) as caught:
                algebra.inverse(value, journal=journal)
            persist(
                tmp_path,
                "expected-singular-inverse-refusal",
                dict(reason=str(caught.value), pivots=journal),
            )
            return
        else:
            value = algebra.matrix([[-1, 1, 0], [0, -1, 1], [1, 0, -1]])
            area = (
                tuple(Fraction(x) for x in (1, 2, 4))
                if name == "factorized-map-distinct"
                else tuple(Fraction(x) for x in (3, 5, 7))
            )
            w = (
                tuple(Fraction(x) for x in (1, 2, 3))
                if name == "factorized-map-distinct"
                else (Fraction(1),) * 3
            )
            r = (
                tuple(Fraction.from_float(x) for x in (1.0, 0.5, 0.3333333333333333))
                if name == "factorized-map-distinct"
                else (Fraction(1),) * 3
            )
            alpha = tuple(Fraction.from_float(1.0 / float(x)) for x in area)
            persist(
                tmp_path,
                "raw-exact-input",
                dict(
                    matrix=value, w=w, r=r, area=area, alpha=alpha, physical_admission_credit=False
                ),
            )
            pinv, factors = algebra.pseudoinverse(value, journal=journal)
            maps = operators.source_factors(value, pinv, w, r, alpha, area)
            if name == "factorized-map-distinct":
                defect = algebra.subtract(
                    algebra.multiply(
                        algebra.multiply(maps["lapGJ"], maps["lapGJinv"]), maps["lapGJ"]
                    ),
                    maps["lapGJ"],
                )
            else:
                defect = algebra.multiply(algebra.matrix([list(area)]), maps["lapGJ"])
            persist(
                tmp_path,
                "raw-source-law-defect",
                dict(maps=maps, factors=factors, pivots=journal, defect=defect),
            )
            assert any(x != 0 for row in defect.data for x in row)
            return
        persist(
            tmp_path,
            "raw-exact-input",
            dict(
                matrix=value,
                independently_declared_expected=expected,
                physical_admission_credit=False,
            ),
        )
        result, factors = algebra.pseudoinverse(value, journal=journal)
        persist(tmp_path, "raw-exact-return", dict(result=result, factors=factors, pivots=journal))
        assert result == expected
    except Exception as error:
        failure(tmp_path, state, error)
        raise


def test_unrepresentable_scalar_retains_exact_rounding_input(tmp_path):
    state = begin(tmp_path, "raw-scalar-only", "underflow evidence; no mesh/science credit")
    work = operators._Work()
    state["arithmetic_events"] = work.scalars
    try:
        target = Fraction(1, 1 << 1100)
        persist(tmp_path, "raw-unrepresentable-input", target)
        with pytest.raises(ValueError) as caught:
            work.round(target, "raw_scalar", 0, 0)
        persist(
            tmp_path,
            "expected-unrepresentable-refusal",
            dict(reason=str(caught.value), events=work.scalars),
        )
        assert work.scalars[0]["failure"] and "returned" not in work.scalars[0]
    except Exception as error:
        failure(tmp_path, state, error)
        raise


def test_conditional_operator_caches_cannot_admit_native_or_physical_loop(tmp_path):
    state = begin(tmp_path, BASE, "continued native/physical admission refusal")
    try:
        _, candidate = construct(tmp_path, state)
        with pytest.raises(operators.OperatorRejected) as caught:
            operators.require_native_cache(candidate)
        persist(
            tmp_path,
            "expected-native-cache-refusal",
            dict(
                reason=str(caught.value),
                original=caught.value.original,
                partial=caught.value.partial,
            ),
        )
        assert caught.value.stage == "native_cache_admission"
    except Exception as error:
        failure(tmp_path, state, error)
        raise


@pytest.mark.parametrize("case", DOMAIN_REFUSALS)
def test_retained_metric_parent_domain_refusal_has_no_operator_credit(case, tmp_path):
    state = begin(tmp_path, case, "retained original parent domain refusal; zero operator credit")
    try:
        row = next(row for row in parents.domain_roster()["cases"] if row["case"] == case)
        persist(tmp_path, "reviewed-parent-domain-witness", row)
        with pytest.raises(metric.MetricRejected) as caught:
            construct(tmp_path, state)
        error = caught.value
        persist(
            tmp_path,
            "expected-metric-parent-refusal",
            dict(
                stage=error.stage,
                original=error.original,
                partial=error.partial,
                reason=str(error),
                operator_constructed=False,
                operator_qualification_credit=False,
                original_metric02_failure_reclassified=False,
            ),
        )
        assert error.stage == "global_polygon_domains"
        assert error.partial["source_error"]["reason"] == (
            "Source seed owner is not strictly inside its retained dual polygon"
        )
        assert (
            state["request"] is None and state["candidate"] is None and state["reference"] is None
        )
        actual_parent = state["metric_state"]["parent"]
        corrected = state["metric_state"]["corrected"]
        actual, reviewed = operators.plain(corrected), row["retained_topology_candidate"]
        context = {"identity", "request_identity"}
        persist(
            tmp_path,
            "parent-domain-capture-context",
            dict(
                actual_identity=actual["identity"],
                actual_request_identity=actual["request_identity"],
                reviewed_identity=reviewed["identity"],
                reviewed_request_identity=reviewed["request_identity"],
                separately_bound_fields=sorted(context),
            ),
        )
        assert actual["request_identity"] == actual_parent.identity
        assert actual["identity"] == topology.digest(topology.candidate_record(corrected))
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
        assert set(actual) == set(reviewed)
        assert operators.digest(
            {k: v for k, v in actual.items() if k not in context}
        ) == operators.digest({k: v for k, v in reviewed.items() if k not in context})
    except Exception as error:
        failure(tmp_path, state, error)
        raise
