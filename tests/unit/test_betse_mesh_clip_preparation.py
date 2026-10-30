"""Prepared clipping panel; execution requires Chief's separate authorization."""

import json
import os
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_environment_field as arrays
from cells.processes import betse_initial_mesh_preparation as initial
from cells.processes import betse_initial_mesh_preparation_cache as caches
from cells.processes import betse_mesh_clip_preparation as clip
from cells.processes import betse_normal_current as records
from cells.processes import betse_perturbations as streams
from validation.betse import betse_initial_mesh_preparation_native as caller_native
from validation.betse import betse_initial_mesh_preparation_wire as wire
from validation.betse import betse_mesh_clip_preparation_fixtures as fixtures
from validation.betse import betse_mesh_clip_preparation_native as native
from validation.betse import betse_mesh_clip_preparation_reference as reference


def save(label, value, columns=None):
    if folder := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        root = Path(folder) / "mesh-clip"
        root.mkdir(parents=True, exist_ok=True)
        if columns is not None:
            with (root / (label + ".npz")).open("xb") as handle:
                np.savez_compressed(handle, **columns)
                handle.flush()
                os.fsync(handle.fileno())
        with (root / (label + ".json")).open("x") as handle:
            json.dump(arrays.plain(value), handle, indent=2, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())


def retain_caches(label, metadata, named, events):
    columns = {}

    def record(prefix, cache):
        columns.update(
            {prefix + "__" + name: value for name, value in cache.numeric_columns().items()}
        )
        return dict(column_prefix=prefix, descriptor=cache.descriptor, identity=cache.identity)

    value = dict(
        metadata,
        caches={name: record(name, cache) for name, cache in named.items()},
        events=[
            dict(
                sequence=e.sequence,
                kind=e.kind,
                method=e.method,
                depth=e.depth,
                payload=record(f"event{e.sequence}", e.payload),
            )
            for e in events
        ],
    )
    save(label, value, columns)


def retain_native(label, proof):
    columns = {}

    def record(prefix, cache):
        columns.update({prefix + "__" + name: value for name, value in cache["columns"].items()})
        return dict(column_prefix=prefix, tree=cache["tree"])

    value = {
        k: v
        for k, v in proof.items()
        if k not in ("initial_cache", "cache", "events", "helper_result")
    }
    value.update(
        initial_cache=record("initial", proof["initial_cache"]),
        cache=record("final", proof["cache"]),
        helper_result=None
        if proof["helper_result"] is None
        else record("result", proof["helper_result"]),
        events=[
            {
                **{k: v for k, v in e.items() if k != "payload"},
                "payload": record(f"event{e['sequence']}", e["payload"]),
            }
            for e in proof["events"]
        ],
    )
    save(label, value, columns)


def build_request(case, directory, *, label=None):
    label = case if label is None else label
    base, inputs = fixtures.case(case, directory)
    retain_caches(
        label + "-input",
        dict(inputs=inputs, initial_request=initial.request_record(base)),
        dict(constructor=caches.snapshot(dict(base.constructor_kwargs))),
        (),
    )
    try:
        state = initial.prepare(base)
    except initial.InitialMeshRejected as error:
        if error.trial is not None:
            retain_caches(
                label + "-upstream-failure",
                dict(state=initial.state_record(error.trial)),
                dict(constructed=error.trial.constructed_cache, final=error.trial.cache),
                error.trial.events,
            )
        raise
    return clip.from_initial_mesh(base, state), inputs


def compare_events(actual, expected, *, failed=False):
    assert len(actual) == len(expected)
    for event, proof in zip(actual, expected, strict=True):
        assert (event.sequence, event.kind, event.method, event.depth) == (
            proof["sequence"],
            proof["kind"],
            proof["method"],
            proof["depth"],
        )
        if failed and event.kind.endswith("failure"):
            left, right = (
                caches.plain(event.payload),
                wire.plain(proof["payload"]["tree"], proof["payload"]["columns"]),
            )
            left.pop("reason", None)
            right.pop("reason", None)
            assert records.record(left) == records.record(right)
        else:
            wire.compare_owned(
                event.payload.descriptor, event.payload.numeric_columns(), proof["payload"]
            )


def fraction(actual, expected, atol):
    a, b = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
    assert a.shape == b.shape
    value = float(np.max(abs(a - b) / (np.asarray(atol) + 6e-12 * abs(b)), initial=0))
    assert value <= 1, value
    return value


def plain_events(events):
    return [
        dict(sequence=e.sequence, kind=e.kind, method=e.method, payload=caches.plain(e.payload))
        for e in events
    ]


def retained_reference(label, events, mask, refinement):
    try:
        report = reference.evaluate(events, mask, refinement=refinement)
    except reference.ReferenceFailure as error:
        save(label + f"-reference-{refinement}-failure", error.trial)
        raise
    save(label + f"-reference-{refinement}", report)
    return report


@pytest.mark.parametrize("case", fixtures.CASES)
def test_owned_native_clipping_trace_and_independent_diagnostics(tmp_path, case):
    request, inputs = build_request(case, tmp_path)
    rejection = None
    try:
        state = clip.prepare(request)
    except clip.ClipRejected as error:
        rejection, state = error, error.trial
    assert state is not None
    retain_caches(
        case + "-actual",
        dict(
            mode="actual_before_native",
            request=clip.request_record(request),
            state=clip.state_record(state),
            inputs=inputs,
        ),
        dict(
            initial=state.initial_cache,
            final=state.cache,
            mask=caches.snapshot(clip.mask_record(request)),
        ),
        state.events,
    )
    caller = caller_native.caller_kwargs(
        inputs["seed_recipe"], inputs["seed_stream_before"], inputs["controls"]
    )
    captured = wire.capture(caller["kwargs"])
    save(
        case + "-native-caller",
        dict(kwargs=captured["tree"], caller={k: v for k, v in caller.items() if k != "kwargs"}),
        captured["columns"],
    )
    proof = native.evaluate(
        caller["kwargs"],
        request.initial_request.constructor_point_ids,
        caller["rng_before_constructor"],
        clip.mask_record(request),
    )
    retain_native(case + "-native", proof)
    events = plain_events(state.events)
    mask = arrays.plain(clip.mask_record(request))
    first = retained_reference(case, events, mask, 1)
    second = retained_reference(case, events, mask, 2)
    save(case + "-precomparison", dict(reference=first, refined_reference=second))
    assert rejection is None, (
        "Unexpected source refusal retained before native/reference comparison"
    )
    assert proof["status"] == "source_completed" and proof["failure"] is None
    wire.compare_owned(
        state.initial_cache.descriptor,
        state.initial_cache.numeric_columns(),
        proof["initial_cache"],
    )
    wire.compare_owned(state.cache.descriptor, state.cache.numeric_columns(), proof["cache"])
    compare_events(state.events, proof["events"])
    assert list(state.parent_point_ids) == list(proof["parent_point_ids"])
    assert list(state.derived_point_ids_before_rebuild) == list(
        proof["derived_point_ids_before_rebuild"]
    )
    assert list(state.retained_point_ids) == list(proof["retained_point_ids"])
    assert (
        streams.native_stream_manifest(state.stream_after_initial)["state"]
        == proof["rng_after_initial"]
    )
    assert streams.native_stream_manifest(state.stream_after)["state"] == proof["rng_after"]
    assert state.stream_after.identity == state.stream_after_initial.identity
    assert proof["original_global_rng_unchanged"] and not proof["topology_qualified"]
    start = next(e.sequence for e in state.events if e.kind == "clip_continuation_start")
    by_sequence = {e["sequence"]: e["payload"] for e in events}
    maximum = resolution = 0.0
    # Initial geometry is an explicitly unqualified input. Apply the unchanged
    # proposed B09 budgets to new clipping/rebuild primitive results only.
    for a, b in zip(
        first["source_geometry"]["primitives"], second["source_geometry"]["primitives"], strict=True
    ):
        assert (a["sequence"], a["method"]) == (b["sequence"], b["method"])
        if a["sequence"] <= start:
            continue
        method = a["method"]
        atol = (
            1e-26
            if method == "area"
            else [1e-27, 1e-26, 1e-27, 1e-27]
            if method == "quad_circumc"
            else 1e-27
        )
        maximum = max(
            maximum, fraction(by_sequence[a["sequence"]]["result"], a["expected_result"], atol)
        )
        resolution = max(resolution, fraction(a["expected_result"], b["expected_result"], atol))
    for a, b in zip(
        first["source_geometry"]["nearest"], second["source_geometry"]["nearest"], strict=True
    ):
        assert a["sequence"] == b["sequence"]
        if a["sequence"] <= start:
            continue
        payload = by_sequence[a["sequence"]]
        actual_values = np.asarray(payload["result"][0]).ravel().tolist()
        expected = [v for row in a["expected"] for v in row["ranked_distances"]]
        refined = [v for row in b["expected"] for v in row["ranked_distances"]]
        assert [r["exact_tie_candidate_indices"] for r in a["expected"]] == [
            r["exact_tie_candidate_indices"] for r in b["expected"]
        ]
        floor = 2e-14 if np.asarray(payload["data"]).dtype.kind in "iu" else 1e-27
        for value, target, refined_value in zip(actual_values, expected, refined, strict=True):
            if target == "infinity":
                assert np.isinf(value) and refined_value == "infinity"
            else:
                maximum = max(maximum, fraction(value, target, floor))
                resolution = max(resolution, fraction(target, refined_value, floor))
    for a, b in zip(first["mask_queries"], second["mask_queries"], strict=True):
        assert a["sequence"] == b["sequence"]
        if a["within_closed_window"]:
            maximum = max(maximum, fraction(a["observed_value"], a["independent_value"], 2e-14))
            resolution = max(
                resolution, fraction(a["independent_value"], b["independent_value"], 2e-14)
            )
    for a, b in zip(first["helper_diagnostics"], second["helper_diagnostics"], strict=True):
        assert (a["sequence"], a["method"]) == (b["sequence"], b["method"])
        left, right = a["diagnostic"], b["diagnostic"]
        if a["method"] == "intersect_lines" and left["exact_unique"]:
            maximum = max(
                maximum,
                fraction(by_sequence[a["sequence"]]["result"], left["expected_point_m"], 1e-27),
            )
            resolution = max(
                resolution, fraction(left["expected_point_m"], right["expected_point_m"], 1e-27)
            )
        elif a["method"] == "clip_counterclockwise" and left["supported"]:
            maximum = max(
                maximum,
                fraction(left["source_result_signed_area_m2"], left["signed_area_m2"], 1e-26),
            )
            resolution = max(
                resolution, fraction(left["signed_area_m2"], right["signed_area_m2"], 1e-26)
            )
    assert resolution <= 0.1
    predicate_disagreements = sum(r["predicate_agrees"] is False for r in first["mask_queries"])
    predicate_disagreements += sum(
        r["diagnostic"].get("predicate_agrees") is False for r in first["helper_diagnostics"]
    )
    save(
        case,
        dict(
            mode="complete_source_clipping_preparation",
            maximum_error_fraction=maximum,
            maximum_reference_resolution_fraction=resolution,
            predicate_disagreements_retained=predicate_disagreements,
            outside_window_native_only_queries=sum(
                not r["within_closed_window"] for r in first["mask_queries"]
            ),
            upstream_accuracy_qualification="open",
            new_initial_mesh_qualification_credit=False,
            independent_selection_or_topology_claim=False,
            topology_qualified=False,
            downstream_geometry_admitted=False,
        ),
    )


def helper_actual(method, parameters):
    observer = clip._Observer(())
    obj = object.__new__(clip._Runtime) if method == "search_point_cloud" else clip._Tools(observer)
    obj._cells_observer = observer
    result, failure = None, None
    try:
        result = getattr(obj, method)(**parameters)
    except Exception as error:
        failure = error
    return result, failure, observer.events


def helper_pair(case):
    method, parameters = fixtures.helper(case)
    result, failure, events = helper_actual(method, parameters)
    retain_caches(
        case + "-actual",
        dict(
            classification="isolated_manufactured_helper_only",
            method=method,
            failure_type=None if failure is None else type(failure).__name__,
            failure_message=None if failure is None else str(failure),
        ),
        dict(parameters=caches.snapshot(parameters), result=caches.snapshot(result)),
        events,
    )
    before = streams.native_stream_manifest(streams.native_stream(17))["state"]
    proof = native.evaluate({}, (), before, None, helper=(method, parameters))
    retain_native(case + "-native", proof)
    return method, parameters, result, failure, events, proof


@pytest.mark.parametrize("case", fixtures.HELPER_CASES)
def test_manufactured_helpers_match_original_and_independent_geometry(case):
    method, parameters, result, failure, events, proof = helper_pair(case)
    reports = []
    for refinement in (1, 2):
        try:
            report = reference.evaluate_helper(
                method, arrays.plain(parameters), arrays.plain(result), refinement=refinement
            )
        except reference.ReferenceFailure as error:
            save(case + f"-reference-{refinement}-failure", error.trial)
            raise
        save(case + f"-reference-{refinement}", report)
        reports.append(report)
    assert failure is None and proof["failure"] is None
    wire.compare_owned(
        caches.snapshot(result).descriptor,
        caches.snapshot(result).numeric_columns(),
        proof["helper_result"],
    )
    compare_events(events, proof["events"])
    diagnostic = reports[0]["diagnostic"]
    refined = reports[1]["diagnostic"]
    save(
        case,
        dict(
            diagnostic=reference.mesh_reference.serial(diagnostic),
            classification="manufactured_helper_only",
        ),
    )
    if method == "is_left_of_vector":
        assert bool(result) == diagnostic["exact_strict_side"]
    elif method == "intersect_lines":
        fraction(result, [float(v) for v in diagnostic["expected_point_m"]], 1e-27)
        assert fraction(diagnostic["expected_point_m"], refined["expected_point_m"], 1e-27) <= 0.1
    elif method == "clip_counterclockwise":
        fraction(
            float(diagnostic["source_result_signed_area_m2"]),
            float(diagnostic["signed_area_m2"]),
            1e-26,
        )
        assert fraction(diagnostic["signed_area_m2"], refined["signed_area_m2"], 1e-26) <= 0.1
    elif case == "duplicate-cloud":
        assert len(result[0]) == 2 and np.array_equal(result[0][0], result[0][1])
    elif case == "keeper-complement":
        throw_away_pts, keeper_pts = result
        np.testing.assert_array_equal(throw_away_pts, parameters["pts"][[0, 2]])
        np.testing.assert_array_equal(keeper_pts, parameters["pts"][[1]])
        assert diagnostic["exact_matching_occurrence_pairs"] == [[0, 0], [2, 1]]
        save(
            "keeper-complement-witness",
            dict(
                source_result_order=["matched_discarded", "unmatched_kept"],
                matched_indices=[0, 2],
                keeper_indices=[1],
                classification="isolated_helper_before_branch_credit",
                production_clip_selection_qualified=False,
            ),
        )
    else:
        assert result == ([], [])


@pytest.mark.parametrize("case", fixtures.RAW_HELPER_CASES)
def test_raw_helper_failure_retains_unexpected_completion_and_native_proof(case):
    _, _, _, failure, events, proof = helper_pair(case)
    assert failure is not None, "Unexpected manufactured-helper completion retained"
    assert proof["failure"]["type"] == type(failure).__name__
    compare_events(events, proof["events"], failed=True)


@pytest.mark.parametrize(
    "target", ("request_identity", "initial_identity", "initial_owner_order", "initial_cache")
)
def test_resealed_clipping_request_tampering_is_refused(tmp_path, target):
    request, _ = build_request("dense4-square-centroid", tmp_path, label="tamper-" + target)
    if target == "request_identity":
        request = replace(request, identity="changed")
    else:
        state = request.initial_state
        if target == "initial_identity":
            state = replace(state, identity="changed")
        elif target == "initial_owner_order":
            state = replace(state, retained_point_ids=tuple(reversed(state.retained_point_ids)))
            state = replace(state, identity=records._digest(initial.state_record(state)))
        else:
            state = replace(state, cache=caches.snapshot({}))
            state = replace(state, identity=records._digest(initial.state_record(state)))
        request = replace(request, initial_state=state)
        request = replace(request, identity=records._digest(clip.request_record(request)))
    with pytest.raises(ValueError):
        clip.validate_request(request)


def test_single_cell_caller_does_not_enter_clipping(tmp_path):
    base, _ = fixtures.upstream.caller("caller-single-square-cache", tmp_path)
    state = initial.prepare(base)
    with pytest.raises(ValueError):
        clip.from_initial_mesh(base, state)


def test_cache_ownership_and_no_geometry_bridge_or_operators(tmp_path):
    request, _ = build_request("dense4-square-centroid", tmp_path, label="ownership-no-bridge")
    state = clip.prepare(request)
    for cache in (state.cache, *(e.payload for e in state.events)):
        caches.validate(cache)
        for value in cache.numeric_columns().values():
            with pytest.raises(ValueError):
                value.setflags(write=True)
    cache = caches.plain(state.cache)
    assert cache["image_mask"]["kind"] == "owned_image_prelude_mask_token"
    assert not any(name.startswith("delta_") for name in cache)
    exported = clip.export_trial(request, state)
    assert not exported["topology_qualified"] and not exported["downstream_geometry_admitted"]
    assert not exported["operators_created"] and not exported["refinement_executed"]


def test_reference_accepts_captured_float_and_integer_binary_coefficients():
    mask = dict(xpts_m=[0.0, 1.0], ypts_m=[0.0, 1.0], clipping_matrix=[[0.0, 1], [1, 0.0]])
    events = [
        dict(
            sequence=0,
            kind="mask_query",
            method="manufactured_reference_domain",
            payload=dict(x=0.25, y=0.75, result=[[0.625]]),
        )
    ]
    reports = []
    for refinement in (1, 2):
        report = retained_reference("binary-coefficient-domain", events, mask, refinement)
        reports.append(report)
    assert reference.binary_coefficients(mask) == [[0, 1], [1, 0]]
    assert reports[0]["mask_queries"][0]["independent_value"] == 0.625
    assert reports[1]["mask_queries"][0]["independent_value"] == 0.625
    assert all(r["binary_mask_coefficients_validated"] for r in reports)


@pytest.mark.parametrize("coefficient", (0.5, "1", True))
def test_reference_refuses_coefficients_outside_the_exact_binary_numeric_domain(coefficient):
    mask = dict(
        xpts_m=[0.0, 1.0], ypts_m=[0.0, 1.0], clipping_matrix=[[0.0, coefficient], [1.0, 0.0]]
    )
    failure = None
    try:
        report = reference.evaluate([], mask)
    except reference.ReferenceFailure as error:
        failure = error
        report = error.trial
    # Retain any unexpected reference completion before the refusal assertion.
    save("binary-coefficient-refusal-" + type(coefficient).__name__, report)
    assert failure is not None
    assert report["failure"]["type"] == "ValueError"
