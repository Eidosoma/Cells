"""Focused software checks plus a HELD native/independent qualification matrix."""

import copy
import hashlib
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import asdict
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_post_cut_mesh_contact as owner
from cells.processes import betse_post_cut_mesh_contact_records as wire
from validation.topology import betse_post_cut_mesh_contact_fixtures as cases


def save(path, name, value):
    with (path / (name + ".json")).open("x") as stream:
        json.dump(value, stream, sort_keys=True, separators=(",", ":"), allow_nan=False)


def failure(error, seen=()):
    if id(error) in seen:
        return dict(type=type(error).__name__, repeated_exception=True)
    chain = (*seen, id(error))
    return dict(
        type=type(error).__name__,
        reason=str(error),
        partial=getattr(error, "partial", None),
        trial=asdict(error.trial) if getattr(error, "trial", None) is not None else None,
        cause=None if error.__cause__ is None else failure(error.__cause__, chain),
        context=None
        if error.__cause__ is not None or error.__suppress_context__ or error.__context__ is None
        else failure(error.__context__, chain),
    )


@pytest.fixture
def evidence(request, tmp_path):
    root = Path(os.environ.get("CELLS_POST_CUT_EVIDENCE_DIR", str(tmp_path)))
    assert root.is_absolute() and root.is_dir()
    path = root / hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:20]
    path.mkdir(exist_ok=False)
    save(path, "case", dict(nodeid=request.node.nodeid))
    return path


@pytest.fixture(autouse=True)
def explicit_science_release(request):
    if (
        not request.node.originalname.startswith("test_software_")
        and os.environ.get("CELLS_POST_CUT_SCIENCE_RELEASED") != "1"
    ):
        pytest.skip("Post-cut scientific qualification remains held pending coordinated release")


@contextmanager
def archived(path):
    available = {}
    try:
        yield available
    except Exception as error:
        save(path, "failure", dict(available=available, error=failure(error)))
        raise


def child(path, label, worker, request, *, stdlib=False):
    text = json.dumps(request, sort_keys=True, allow_nan=False)
    save(path, label + "_request", request)
    argv = [sys.executable, "-I", "-B"]
    if stdlib:
        argv.append("-S")
    argv.append(str(worker))
    process = subprocess.Popen(
        argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    try:
        stdout, stderr = process.communicate(text, timeout=90)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        save(path, label + "_timeout", dict(pid=process.pid, stdout=stdout, stderr=stderr))
        raise
    save(
        path,
        label + "_actual_process",
        dict(
            pid=process.pid,
            ppid=os.getpid(),
            argv=argv,
            returncode=process.returncode,
            input_sha256=hashlib.sha256(text.encode()).hexdigest(),
            worker_sha256=hashlib.sha256(worker.read_bytes()).hexdigest(),
            stdout=stdout,
            stderr=stderr,
        ),
    )
    assert process.returncode == 0, stderr
    result = json.loads(stdout)
    save(path, label + "_raw_return", result)
    assert result["runtime"]["pid"] == process.pid and result["runtime"]["ppid"] == os.getpid()
    return result


def capture(path, raw):
    save(path, "original_input", dict(graph=wire.snapshot(raw)))
    trial = owner.capture(
        raw, observer=lambda row: save(path, "actual_event_" + str(row["sequence"]), row)
    )
    save(path, "complete_primary_trial", asdict(trial))
    return trial


def native(path, raw):
    worker = (
        Path(__file__).resolve().parents[2]
        / "validation/topology/betse_post_cut_mesh_contact_native.py"
    )
    return child(path, "native", worker, dict(input_graph=wire.snapshot(raw)))


def reference(path, raw, mode, precision):
    worker = (
        Path(__file__).resolve().parents[2]
        / "validation/topology/betse_post_cut_mesh_contact_reference.py"
    )
    result = child(
        path,
        "reference_" + str(precision),
        worker,
        dict(input_graph=wire.snapshot(raw), mode=mode, precision=precision),
        stdlib=True,
    )
    assert result["scientific_modules_loaded"] == []
    assert result["runtime"]["isolated"] == 1 and result["runtime"]["no_site"] == 1
    return result


def assert_precision_agreement(path, refs, *, label="precision_pair_metrics"):
    """Retain raw audits; compare exact fields and certify rounded distances.

    For the two-coordinate squared-distance expression, each of two differences,
    two squares and one sum is rounded. The fixed 16*10**(1-p) relative bound
    exceeds the five-operation error envelope at p>=80. This checks reference
    arithmetic only; native/contact/pseudoinverse tolerances are unchanged.
    """
    assert [ref["precision"] for ref in refs] == [80, 140]
    exact_results = []
    metrics = []
    for ref in refs:
        result = copy.deepcopy(ref["result"])
        key = "nearest_audit" if "nearest_audit" in result else "incoming_query_audit"
        count = 0
        maximum = Fraction(0)
        for row in result[key]:
            rounded = row.pop("rounded_squared_distances")
            exact_rows = row["exact_squared_distances"]
            assert len(rounded) == len(exact_rows)
            for token, pair in zip(rounded, exact_rows, strict=True):
                assert type(token) is str and type(pair) is list and len(pair) == 2
                assert all(type(value) is int for value in pair) and pair[0] >= 0 and pair[1] > 0
                exact = Fraction(*pair)
                assert pair == [exact.numerator, exact.denominator]
                approximation = Fraction(token)
                error = abs(approximation - exact)
                bound = Fraction(16, 10 ** (ref["precision"] - 1)) * exact
                assert error <= bound
                normalized = Fraction(0) if bound == 0 else error / bound
                maximum = max(maximum, normalized)
                count += 1
        assert count > 0
        exact_results.append(result)
        metrics.append(
            dict(
                precision=ref["precision"],
                exact_distance_entries=count,
                maximum_normalized_roundoff=float(maximum),
                bound="16*10**(1-p)*exact_squared_distance",
            )
        )
    assert exact_results[0] == exact_results[1]
    save(
        path,
        label,
        dict(
            precision_checks=metrics,
            exact_discrete_and_rational_outputs_equal=True,
            raw_80_and_140_distance_strings_preserved=True,
            native_and_pseudoinverse_tolerances_unchanged=True,
        ),
    )


def equivalent(first, second):
    assert first["before_json"] == second["before_json"]
    a, b = wire.restore(first["after_json"]), wire.restore(second["after_json"])
    # Source filenames and line numbers are retained in each raw result but are
    # provenance, not mathematical or typed owner equivalence.
    for value in (a, b):
        for warning in value["warnings"]:
            warning.pop("filename")
            warning.pop("lineno")
    assert wire.snapshot(a) == wire.snapshot(b)
    assert first["source_completed"] is second["source_completed"]
    left = None if first["failure_json"] is None else json.loads(first["failure_json"])
    right = None if second["failure_json"] is None else json.loads(second["failure_json"])
    if left is None:
        assert right is None
    else:
        assert (left["type"], left["message"]) == (right["type"], right["message"])
    events_a = json.loads(first["events_json"])
    events_b = json.loads(second["events_json"])
    assert events_a == events_b
    assert second["runtime"]["production_kernel_imported"] is False


def test_software_codec_preserves_nonfinite_bits_and_shared_containers(evidence):
    shared = [np.asarray([1.0, np.nan, np.inf, -np.inf, -0.0], dtype="<f8")]
    raw = dict(first=shared, second=shared, integer=np.asarray([2, 3], dtype=np.int64))
    encoded = wire.snapshot(raw)
    save(evidence, "codec_input", dict(graph=encoded))
    restored = wire.restore(encoded)
    assert restored["first"] is restored["second"]
    assert wire.snapshot(restored) == encoded
    assert restored["first"][0].tobytes() == raw["first"][0].tobytes()
    # Synthetic rational arithmetic exercises the precision comparator, without
    # any cut/contact kernel, physical fixture or independent worker execution.
    refs = []
    for precision in (80, 140):
        with localcontext() as context:
            context.prec = precision
            rounded = str(Decimal(1) / Decimal(2**144))
        refs.append(
            dict(
                precision=precision,
                result=dict(
                    exact_marker="fixed",
                    nearest_audit=[
                        dict(
                            exact_squared_distances=[[1, 2**144]],
                            rounded_squared_distances=[rounded],
                            minimizers=[0],
                        )
                    ],
                ),
            )
        )
    save(evidence, "synthetic_precision_inputs", dict(refs=refs, scientific_credit=False))
    assert (
        refs[0]["result"]["nearest_audit"][0]["rounded_squared_distances"]
        != (refs[1]["result"]["nearest_audit"][0]["rounded_squared_distances"])
    )
    assert_precision_agreement(evidence, refs, label="synthetic_precision_metrics")
    wrong_discrete = copy.deepcopy(refs)
    wrong_discrete[0]["result"]["exact_marker"] = "corrupt"
    with pytest.raises(AssertionError):
        assert_precision_agreement(evidence, wrong_discrete, label="must_not_write_discrete")
    wrong_audit = copy.deepcopy(refs)
    wrong_audit[0]["result"]["nearest_audit"][0]["rounded_squared_distances"] = ["0"]
    with pytest.raises(AssertionError):
        assert_precision_agreement(evidence, wrong_audit, label="must_not_write_roundoff")
    save(
        evidence,
        "synthetic_precision_refusals",
        dict(
            wrong_discrete_refused=True, wrong_rounded_audit_refused=True, scientific_credit=False
        ),
    )


@pytest.mark.parametrize("defect", ["duplicate_owner", "picker_membrane_mismatch", "legacy_ER"])
def test_software_admission_retains_available_input(defect, evidence):
    raw = cases.fixture()
    if defect == "duplicate_owner":
        raw["owners"]["cell_ids"][1] = raw["owners"]["cell_ids"][0]
    elif defect == "picker_membrane_mismatch":
        raw["selection"]["membranes"] = np.asarray([], dtype=np.int64)
    else:
        raw["parameters"]["Ca_dyn"] = True
    save(evidence, "refused_input", dict(graph=wire.snapshot(raw)))
    with pytest.raises(owner.BoundaryRejected) as result:
        owner.capture(raw)
    save(evidence, "admission_refusal", failure(result.value))
    assert result.value.partial["available_input_json"] == wire.snapshot(raw)


def test_software_metadata_cannot_unlock_ordinary_checkpoint(evidence):
    record = dict(
        law_id=owner.LAW_ID,
        mode="mesh_only",
        before_json="{}",
        after_json="{}",
        events_json="[]",
        failure_json=None,
        source_completed=True,
        first_failure_stage=None,
        source_pin="metadata-only-control",
    )
    trial = owner.Trial(**record, identity=owner.digest(record))
    declaration = {name: "supplied" for name in ("environment", "Poisson", "checkpoint")}
    with pytest.raises(owner.BoundaryRejected) as result:
        owner.request_ordinary_continuation(trial, declarations=declaration)
    save(
        evidence,
        "metadata_refusal",
        dict(no_scientific_accuracy_credit=True, failure=failure(result.value)),
    )
    assert result.value.partial["metadata_cannot_unlock_checkpoint"] is True
    assert result.value.partial["requires_admitted_executable_DEC_parent"] is True
    assert result.value.partial["executable_DEC_parent_admitted"] is False
    assert result.value.partial["invalidated_owners"] == list(owner.INVALIDATED_OWNERS)
    raw = cases.fixture()
    before = wire.snapshot(raw)
    for stage, length in (("before_deletion", 5), ("differently_shortened_buffers", 2)):
        # These are metadata-only invented failed frames, never native outcomes.
        partial = wire.snapshot(
            dict(
                synthetic_failed_stage=stage,
                first_buffer=np.arange(length),
                second_buffer=np.arange(3),
                scientific_credit=False,
            )
        )
        record = dict(
            law_id=owner.LAW_ID,
            mode="cut_through_contacts",
            before_json=before,
            after_json=partial,
            events_json="[]",
            failure_json=json.dumps(dict(type="SyntheticFailure", message=stage)),
            source_completed=False,
            first_failure_stage=stage,
            source_pin="synthetic_failure_projection_software_only",
        )
        failed_trial = owner.Trial(**record, identity=owner.digest(record))
        projection = owner.owner_projection(failed_trial)
        assert projection["requested_removed_cell_ids"] == ["cell-0"]
        assert projection["requested_survivor_cell_ids"] == ["cell-1", "cell-2", "cell-3", "cell-4"]
        for name in (
            "cell_ids_after",
            "removed_cell_ids",
            "mesh_survivor_edge_ids",
            "mesh_removed_edge_ids",
            "native_edge_endpoint_owner_pairs",
            "hanging_cell_ids",
        ):
            assert projection[name] is None
        assert projection["observed_lineage_status"] == "unavailable_failed_source"
        assert projection["original_partial_state"]["after_json_sha256"] == (
            hashlib.sha256(partial.encode()).hexdigest()
        )
        assert failed_trial.before_json == before and failed_trial.after_json == partial
        assert projection["invalidated_owners"] == list(owner.INVALIDATED_OWNERS)
        save(
            evidence,
            "synthetic_failure_projection_" + stage,
            dict(trial=asdict(failed_trial), projection=projection, scientific_credit=False),
        )


@pytest.mark.parametrize(
    "case",
    [
        "corner_cut",
        "centre_cut",
        "no_cut",
        "all_cut",
        "ordered_two_cut",
        "uniform_polygon_raw",
        "nonfinite_mesh_raw",
    ],
)
def test_native_cut_to_contact_boundary_preserves_full_raw_result(case, evidence):
    with archived(evidence) as available:
        raw = cases.fixture(case)
        available["input_graph"] = wire.snapshot(raw)
        trial = capture(evidence, raw)
        available["primary_trial"] = asdict(trial)
        original = native(evidence, raw)
        available["original_native"] = original
        equivalent(asdict(trial), original)
        projection = owner.owner_projection(trial)
        save(evidence, "owner_projection", projection)
        if not trial.source_completed:
            assert projection["observed_lineage_status"] == "unavailable_failed_source"
            assert projection["cell_ids_after"] is None and projection["removed_cell_ids"] is None
            assert projection["original_partial_state"]["source_trial_identity"] == trial.identity
        with pytest.raises(owner.BoundaryRejected):
            owner.request_ordinary_continuation(trial)


@pytest.mark.parametrize("case", ["corner_cut", "centre_cut", "ordered_two_cut"])
def test_mesh_cut_exact_topology_and_rational_pseudoinverse(case, evidence):
    with archived(evidence) as available:
        raw = cases.fixture(case, mode="mesh_only")
        available["input_graph"] = wire.snapshot(raw)
        trial = capture(evidence, raw)
        available["primary_trial"] = asdict(trial)
        assert trial.source_completed
        equivalent(asdict(trial), native(evidence, raw))
        refs = [reference(evidence, raw, "mesh", precision) for precision in (80, 140)]
        assert_precision_agreement(evidence, refs)
        oracle = refs[1]["result"]
        after = wire.restore(trial.after_json)["world"]
        mesh = after["cells"].mesh
        for name in (
            "tri_cells",
            "tri_edges",
            "tcell_to_tedges",
            "tverts_to_tedges",
            "tedges_to_tcell",
        ):
            actual = [np.asarray(row).tolist() for row in getattr(mesh, name)]
            assert actual == oracle[name], name
        np.testing.assert_array_equal(mesh.delta_tri_0, np.asarray(oracle["delta_tri_0"]))
        wanted = np.asarray(oracle["pseudoinverse_binary64"])
        budget = 2e-12 + 5e-12 * np.abs(wanted)
        normalized = np.abs(mesh.delta_tri_0_inv - wanted) / budget
        save(
            evidence,
            "pseudoinverse_metrics",
            dict(
                maximum_normalized_error=float(np.max(normalized, initial=0)),
                rtol=5e-12,
                atol=2e-12,
                exact_fraction_rows=oracle["exact_pseudoinverse"],
            ),
        )
        assert np.max(normalized, initial=0) <= 1
        projection = owner.owner_projection(trial)
        save(evidence, "owner_projection", projection)
        assert projection["physical_mesh_admitted"] is False
        original_owners = raw["owners"]
        survivor_indices = oracle["survivor_vertex_indices"]
        expected_cells = [original_owners["cell_ids"][i] for i in survivor_indices]
        removed_cells = [
            name for i, name in enumerate(original_owners["cell_ids"]) if i not in survivor_indices
        ]
        assert projection["cell_ids_after"] == expected_cells
        assert projection["removed_cell_ids"] == removed_cells
        assert projection["requested_survivor_cell_ids"] == expected_cells
        assert projection["requested_removed_cell_ids"] == removed_cells
        assert projection["observed_lineage_status"] == "observed_completed_mesh_vertices"
        assert projection["vertex_axis_matches_literal_deletion"] is True
        removed_edges = oracle["removed_edge_indices"]
        kept_edges = [
            i for i in range(len(original_owners["mesh_edge_ids"])) if i not in removed_edges
        ]
        assert projection["mesh_survivor_edge_ids"] == [
            original_owners["mesh_edge_ids"][i] for i in kept_edges
        ]
        assert projection["mesh_removed_edge_ids"] == [
            original_owners["mesh_edge_ids"][i] for i in removed_edges
        ]
        expected_pairs = [[expected_cells[v] for v in pair] for pair in oracle["tri_edges"]]
        old_pairs = [
            [original_owners["cell_ids"][int(v)] for v in raw["mesh"]["tri_edges"][i]]
            for i in kept_edges
        ]
        assert projection["native_edge_endpoint_owner_pairs"] == expected_pairs
        assert projection["survivor_edge_endpoints_preserved"] is (old_pairs == expected_pairs)
        assert projection["survivor_edge_endpoints_preserved"] is True
        expected_hanging = [expected_cells[i] for i in oracle["hanging_vertex_indices"]]
        assert projection["hanging_cell_ids"] == expected_hanging
        if case == "centre_cut":
            assert expected_hanging, (
                "The existing centre cut must exercise hanging-owner assertions"
            )
        assert projection["invalidated_owners"] == list(owner.INVALIDATED_OWNERS)
        np.testing.assert_array_equal(
            mesh.stale_auxiliary_witness, raw["mesh"]["stale_auxiliary_witness"]
        )
        returned = wire.restore(trial.after_json)["return_value"]
        assert np.asarray(returned[0]).tolist() == oracle["removed_edge_indices"]
        assert np.asarray(returned[1]).tolist() == oracle["removed_face_indices"]


@pytest.mark.parametrize("ambiguous", [False, True])
def test_supplied_contact_helper_exact_native_and_independent_predicates(ambiguous, evidence):
    with archived(evidence) as available:
        raw = cases.contact_fixture(ambiguous=ambiguous)
        available["input_graph"] = wire.snapshot(raw)
        trial = capture(evidence, raw)
        available["primary_trial"] = asdict(trial)
        equivalent(asdict(trial), native(evidence, raw))
        if ambiguous:
            assert not trial.source_completed
            assert json.loads(trial.failure_json)["type"] == "IndexError"
            assert trial.first_failure_stage == "near_neigh"
        else:
            assert trial.source_completed
        reference_input = dict(cells=raw["cells"], parameters=raw["parameters"])
        refs = [
            reference(evidence, reference_input, "contact", precision) for precision in (80, 140)
        ]
        assert_precision_agreement(evidence, refs)
        cells = wire.restore(trial.after_json)["world"]["cells"]
        for name in ("mem_nn", "nn_i", "cell_nn_i", "bflags_mems"):
            np.testing.assert_array_equal(getattr(cells, name), np.asarray(refs[1]["result"][name]))
        projection = owner.owner_projection(trial)
        save(evidence, "contact_projection", projection)
        if not ambiguous:
            assert projection["contact_pairs"] == [["a/s", "b/s"]]
            assert projection["contact_validation"]["conservative_contact_candidate"] is True
        assert projection["ordinary_checkpoint_ready"] is False
