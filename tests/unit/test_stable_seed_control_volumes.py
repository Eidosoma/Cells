"""Unrun prospective fixed-seed construction, evidence and geometry controls."""

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

from cells.processes import stable_mesh_physical_reconstruction as topology
from cells.processes import stable_seed_control_volumes as volumes
from tests.unit import test_stable_mesh_physical_reconstruction as archives
from validation.geometry import stable_seed_control_volumes_fixtures as fixtures

REFUSALS = (
    "units",
    "old-dual-law",
    "move-seeds",
    "keep-connectivity",
    "domain-role",
    "missing-provenance",
    "nonconvex-domain",
    "reversed-domain",
    "boundary-seed",
    "changed-parent",
    "resealed-policy",
    "physical-promotion",
)
CORRUPTIONS = (
    "ideal-vertex",
    "stored-vertex",
    "seed-id",
    "cell-owner-ring",
    "neighbor-pair",
    "boundary-coverage",
    "area-readout",
    "centroid-readout",
    "flux-closure",
    "missing-domain-moment",
    "empty-clip-evidence",
    "truncated-clip-evidence",
    "coherent-wrong-scalar-target",
    "empty-scalar-evidence",
    "extra-scalar-event",
    "physical-promotion",
)
RAW_CASES = ("single", "horizontal", "collinear", "cocircular", "translated", "collapsed-domain")


def persist(root, name, value):
    archives.persist(root, name, volumes.plain(value))


def begin(root, case, purpose):
    declared = fixtures.declaration(case) if case != "raw-only" else None
    persist(
        root,
        "control-volume-declared-input",
        dict(
            case=case,
            purpose=purpose,
            declaration=declared,
            original_mesh_outcome="0/9 unchanged",
            biological_cases=0,
            physical_geometry_admitted=False,
            launch_owner="Chief/Root; no automatic numerical execution",
        ),
    )
    return dict(
        case=case,
        stage="declared",
        declaration=declared,
        raw=None,
        parent=None,
        corrected=None,
        request=None,
        candidate=None,
        reference=None,
    )


def failure(root, state, error):
    try:
        persist(
            root,
            "control-volume-failure",
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
    except BaseException as capture:
        error.add_note("Control-volume failure capture also failed: " + repr(capture))
        try:
            with (root / "control-volume-failure-capture-error.json").open("x") as stream:
                json.dump(
                    dict(
                        original_type=type(error).__name__,
                        original_message=str(error),
                        capture_type=type(capture).__name__,
                        capture_message=str(capture),
                    ),
                    stream,
                )
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException as fallback:
            error.add_note("Control-volume failure fallback also failed: " + repr(fallback))


def parents(root, state):
    state["stage"] = "load_original_retained_request"
    raw = fixtures.original_request(state["case"])
    state["raw"] = raw
    persist(root, "original-retained-request", raw)
    parent = topology.bind(raw)
    state["parent"] = parent
    persist(root, "original-topology-request", parent)
    corrected = topology.reconstruct(parent)
    state["corrected"] = corrected
    persist(root, "retained-original-topology", corrected)
    row = fixtures.case_record(state["case"])
    persist(root, "original-outside-owner-witness", row)
    assert list(parent.retained_point_ids) == row["retained_point_ids"]
    assert [[x.hex() for x in point] for point in corrected.geometry["tri_verts"]] == row[
        "retained_seed_binary64_hex"
    ]
    return parent, corrected


def construct(root, state):
    parent, corrected = parents(root, state)
    state["stage"] = "new_geometry_bind"
    bound = volumes.bind(parent, corrected, state["declaration"])
    state["request"] = bound
    persist(root, "control-volume-request", bound)
    state["stage"] = "new_geometry_construction"
    count = [0]

    def observe(stage, value):
        persist(root, "construction-event-" + str(count[0]) + "-" + stage, value)
        count[0] += 1

    candidate = volumes.prepare(bound, observer=observe)
    state["candidate"] = candidate
    persist(root, "control-volume-candidate", candidate)
    return bound, candidate


def independent(root, state, request, candidate, *, baseline=None):
    state["stage"] = "independent_constraint_intersection_reference"
    incoming = dict(request=request, candidate=candidate)
    if baseline is not None:
        incoming["baseline"] = baseline
    persist(root, "control-volume-reference-input", incoming)
    target = root / "control-volume-reference-output.json"
    with (root / "control-volume-reference.stdout.log").open("x") as stream:
        try:
            process = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "validation.geometry.stable_seed_control_volumes_reference",
                    "--input",
                    str(root / "control-volume-reference-input.json"),
                    "--output",
                    str(target),
                ],
                stdout=stream,
                stderr=subprocess.STDOUT,
                timeout=480,
                check=False,
            )
        except Exception as error:
            persist(
                root,
                "control-volume-reference-process-failure",
                dict(type=type(error).__name__, reason=str(error)),
            )
            raise
        finally:
            stream.flush()
            os.fsync(stream.fileno())
    persist(root, "control-volume-reference-process", dict(returncode=process.returncode))
    report = json.loads(target.read_text()) if target.is_file() else None
    state["reference"] = report
    if report is None:
        raise RuntimeError("Reference input/log/process receipt retained; no complete report")
    assert report["runtime_origin"]["parent_pid"] == os.getpid()
    assert report["runtime_origin"]["pid"] != os.getpid()
    assert process.returncode == 0 and report["baseline_passed"] is True
    if baseline is None:
        assert report["candidate_passed"] is True
    else:
        assert report["candidate_passed"] is False and report["control_detected"] is True
    return report


@pytest.mark.parametrize("case", fixtures.CONSTRUCTION_CASES)
def test_prospective_fixed_seed_partition_and_independent_geometry(case, tmp_path):
    state = begin(tmp_path, case, "new declared geometry; old failure unchanged")
    try:
        request, candidate = construct(tmp_path, state)
        original = volumes.digest((state["parent"], state["corrected"]))
        independent(tmp_path, state, request, candidate)
        assert volumes.digest((state["parent"], state["corrected"])) == original
        assert candidate.prerequisites["physical_geometry_admitted"] is False
        assert candidate.prerequisites["ordinary_ECM_loop_ready"] is False
        assert candidate.conservation["stored_geometry_domain_area_defect"]["numerator"] == "0"
    except Exception as error:
        failure(tmp_path, state, error)
        raise


@pytest.mark.parametrize("case", fixtures.DOMAIN_GAPS)
def test_original_parent_is_retained_without_inventing_an_envelope(case, tmp_path):
    state = begin(tmp_path, case, "explicit missing domain; no new geometry credit")
    try:
        parent, corrected = parents(tmp_path, state)
        assert state["declaration"]["domain"] is None
        with pytest.raises(ValueError) as caught:
            volumes.bind(parent, corrected, state["declaration"])
        persist(
            tmp_path,
            "expected-domain-input-gap",
            dict(
                reason=str(caught.value),
                original_parent=parent,
                original_topology=corrected,
                requested_declaration=state["declaration"],
                source_input_gap=fixtures.case_record(case)["input_gap"],
                geometry_qualification_credit=False,
                original_failure_reclassified=False,
            ),
        )
        assert (
            state["request"] is None and state["candidate"] is None and state["reference"] is None
        )
    except Exception as error:
        failure(tmp_path, state, error)
        raise


@pytest.mark.parametrize("name", REFUSALS)
def test_explicit_domain_source_seed_and_admission_contracts(name, tmp_path):
    state = begin(tmp_path, fixtures.BASE, "declared input refusal: " + name)
    try:
        parent, corrected = parents(tmp_path, state)
        declared = deepcopy(state["declaration"])
        if name == "units":
            declared["units"]["coordinates"] = "cm"
        elif name == "old-dual-law":
            declared["opted_in_law"] = "preserve_native_centroid_dual"
        elif name == "move-seeds":
            declared["seed_policy"] = "move_seed_to_old_cell_centroid"
        elif name == "keep-connectivity":
            declared["connectivity_policy"] = "reuse_old_nearest_midpoint_edges"
        elif name == "domain-role":
            declared["domain"]["role"] = "native_physical_tissue_boundary"
        elif name == "missing-provenance":
            del declared["domain"]["provenance"]
        elif name == "nonconvex-domain":
            declared["domain"]["vertices_m"] = [
                [-1.0, -1.0],
                [1.0, -1.0],
                [0.0, 0.0],
                [1.0, 1.0],
                [-1.0, 1.0],
            ]
        elif name == "reversed-domain":
            declared["domain"]["vertices_m"].reverse()
        elif name == "boundary-seed":
            declared["domain"]["vertices_m"][0][0] = 0.0
            declared["domain"]["vertices_m"][3][0] = 0.0
        elif name == "changed-parent":
            parent = replace(parent, identity="0" * 64)
        elif name == "physical-promotion":
            declared["physical_status"] = "physical_native_loop_ready"
        persist(
            tmp_path,
            "declared-input-control",
            dict(parent=parent, corrected=corrected, declaration=declared),
        )
        if name == "resealed-policy":
            bound = volumes.bind(parent, corrected, declared)
            declared["seed_policy"] = "move_seed"
            bound = replace(bound, declaration=topology.freeze(declared), identity="")
            bound = replace(bound, identity=volumes.digest(volumes.request_record(bound)))
            persist(tmp_path, "resealed-policy-request", bound)
            with pytest.raises(volumes.ControlVolumeRejected) as caught:
                volumes.prepare(bound)
            assert caught.value.stage == "request"
        else:
            with pytest.raises(ValueError) as caught:
                volumes.bind(parent, corrected, declared)
        persist(
            tmp_path,
            "expected-input-refusal",
            dict(
                reason=str(caught.value),
                original=getattr(caught.value, "original", None),
                partial=getattr(caught.value, "partial", None),
            ),
        )
    except Exception as error:
        failure(tmp_path, state, error)
        raise


def change_exact(value):
    return volumes.plain(Fraction(int(value["numerator"]), int(value["denominator"])) + 1)


def reseal(value):
    candidate = volumes.Candidate(**{name: topology.freeze(child) for name, child in value.items()})
    return replace(candidate, identity=volumes.digest(volumes.candidate_record(candidate)))


@pytest.mark.parametrize("name", CORRUPTIONS)
def test_resealed_geometry_or_evidence_requires_passing_independent_baseline(name, tmp_path):
    state = begin(
        tmp_path, fixtures.BASE, "same-worker positive baseline before output control: " + name
    )
    try:
        request, candidate = construct(tmp_path, state)
        changed = volumes.plain(candidate)
        if name == "ideal-vertex":
            changed["exact_geometry"]["vertices_m"][0][0] = change_exact(
                changed["exact_geometry"]["vertices_m"][0][0]
            )
        elif name == "stored-vertex":
            changed["stored_geometry"]["vertices_m"][0][0] = math.nextafter(
                changed["stored_geometry"]["vertices_m"][0][0], math.inf
            )
        elif name == "seed-id":
            changed["owners"]["retained_point_ids"][0] += "-changed"
        elif name == "cell-owner-ring":
            changed["exact_geometry"]["cells"][0].reverse()
            changed["stored_geometry"]["cells"][0].reverse()
        elif name == "neighbor-pair":
            changed["connectivity"]["new_seed_adjacency"][0] = [0, 0]
        elif name == "boundary-coverage":
            changed["diagnostics"]["stored_boundary_domain_coverage"].pop()
        elif name == "area-readout":
            changed["stored_geometry"]["area_m2"][0] = math.nextafter(
                changed["stored_geometry"]["area_m2"][0], math.inf
            )
        elif name == "centroid-readout":
            changed["stored_geometry"]["centroid_m"][0][0] = math.nextafter(
                changed["stored_geometry"]["centroid_m"][0][0], math.inf
            )
        elif name == "flux-closure":
            value = changed["conservation"]["cells"][0]["constant_flux_closure"][0]
            changed["conservation"]["cells"][0]["constant_flux_closure"][0] = change_exact(value)
        elif name == "missing-domain-moment":
            del changed["moments"]["declared_domain"]
        elif name == "empty-clip-evidence":
            changed["certificates"]["clip_events"] = []
        elif name == "truncated-clip-evidence":
            changed["certificates"]["clip_events"].pop()
        elif name == "coherent-wrong-scalar-target":
            event = next(
                row
                for row in changed["certificates"]["arithmetic_events"]
                if row["input_exact"]["numerator"] != "0"
            )
            value = event["input_exact"]
            target = Fraction(int(value["numerator"]), int(value["denominator"])) + Fraction(
                1, 1 << 1000
            )
            event["input_exact"] = volumes.plain(target)
            event["returned"]["exact_target"] = volumes.plain(target)
        elif name == "empty-scalar-evidence":
            changed["certificates"]["arithmetic_events"] = []
        elif name == "extra-scalar-event":
            event = deepcopy(changed["certificates"]["arithmetic_events"][0])
            event["sequence"] = len(changed["certificates"]["arithmetic_events"])
            changed["certificates"]["arithmetic_events"].append(event)
        elif name == "physical-promotion":
            changed["prerequisites"]["physical_geometry_admitted"] = True
        corrupt = reseal(changed)
        persist(tmp_path, "resealed-geometry-or-evidence-control", corrupt)
        independent(tmp_path, state, request, corrupt, baseline=candidate)
    except Exception as error:
        failure(tmp_path, state, error)
        raise


@pytest.mark.parametrize("name", RAW_CASES)
def test_raw_exact_partition_degeneracy_and_closed_form_areas(name, tmp_path):
    state = begin(tmp_path, "raw-only", "unqualified exact component control: " + name)
    work = volumes._Work()
    state["clip_events"] = work.clips
    state["partial"] = work.partial
    try:
        offset = Fraction(1 << 30) if name == "translated" else Fraction(0)
        domain = tuple((offset + x, offset + y) for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1)))
        if name == "single":
            seeds, expected = ((Fraction(0), Fraction(0)),), (Fraction(4),)
        elif name == "horizontal":
            seeds = ((Fraction(-1, 2), Fraction(0)), (Fraction(1, 2), Fraction(0)))
            expected = (Fraction(2), Fraction(2))
        elif name == "collinear":
            seeds = tuple((x, Fraction(0)) for x in (Fraction(-1, 2), Fraction(0), Fraction(1, 2)))
            expected = (Fraction(3, 2), Fraction(1), Fraction(3, 2))
        elif name == "collapsed-domain":
            seeds = ((Fraction(0), Fraction(0)),)
            domain = (
                (Fraction(0), Fraction(0)),
                (Fraction(1), Fraction(0)),
                (Fraction(2), Fraction(0)),
            )
            persist(
                tmp_path,
                "raw-exact-component-input",
                dict(seeds=seeds, domain=domain, physical_admission_credit=False),
            )
            with pytest.raises(ValueError) as caught:
                volumes.exact_partition(seeds, domain, work)
            persist(
                tmp_path,
                "expected-lower-dimensional-refusal",
                dict(reason=str(caught.value), partial=work.partial, clips=work.clips),
            )
            return
        else:
            seeds = tuple(
                (offset + Fraction(x, 2), offset + Fraction(y, 2))
                for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))
            )
            expected = (Fraction(1),) * 4
        persist(
            tmp_path,
            "raw-exact-component-input",
            dict(
                seeds=seeds,
                domain=domain,
                independently_declared_area_targets=expected,
                physical_admission_credit=False,
            ),
        )
        vertices, cells = volumes.exact_partition(seeds, domain, work)
        incidence, moments, area, centroid, boundary = volumes.admit_complex(
            vertices, cells, seeds, domain, stage="raw_component_only"
        )
        connection = volumes.build_connectivity(vertices, cells, incidence, ())
        persist(
            tmp_path,
            "raw-exact-component-return",
            dict(
                vertices=vertices,
                cells=cells,
                moments=moments,
                domain_area=area,
                domain_centroid=centroid,
                boundary=boundary,
                connectivity=connection,
                clips=work.clips,
            ),
        )
        assert tuple(row[0] for row in moments) == expected
        if name in ("cocircular", "translated"):
            middle = vertices.index((offset, offset))
            assert sum(middle in row for row in cells) == 4
            assert connection["new_seed_adjacency"] == [(0, 1), (0, 3), (1, 2), (2, 3)]
    except Exception as error:
        failure(tmp_path, state, error)
        raise


def test_underflow_keeps_exact_scalar_trial_and_failure(tmp_path):
    state = begin(tmp_path, "raw-only", "unrepresentable scalar evidence; zero geometry credit")
    work = volumes._Work()
    state["arithmetic_events"] = work.scalars
    try:
        target = Fraction(1, 1 << 1100)
        persist(tmp_path, "raw-unrepresentable-target", target)
        with pytest.raises(ValueError) as caught:
            work.round(target, "raw_scalar", 0, 0)
        persist(
            tmp_path, "expected-scalar-refusal", dict(reason=str(caught.value), events=work.scalars)
        )
        assert work.scalars[0]["failure"] and "returned" not in work.scalars[0]
    except Exception as error:
        failure(tmp_path, state, error)
        raise


def test_reconstructed_control_volumes_still_refuse_physical_admission(tmp_path):
    state = begin(tmp_path, fixtures.BASE, "no automatic physical/native/bath/loop binding")
    try:
        _, candidate = construct(tmp_path, state)
        with pytest.raises(volumes.ControlVolumeRejected) as caught:
            volumes.require_physical_admission(candidate)
        persist(
            tmp_path,
            "expected-physical-admission-refusal",
            dict(
                reason=str(caught.value),
                stage=caught.value.stage,
                original=caught.value.original,
                partial=caught.value.partial,
            ),
        )
        assert caught.value.stage == "physical_admission"
    except Exception as error:
        failure(tmp_path, state, error)
        raise
