"""Prepared post-clipping lifecycle/source/algebra checks; no automatic run."""

import json
import os
import warnings
from dataclasses import replace
from decimal import Decimal, localcontext
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_environment_field as arrays
from cells.processes import betse_initial_mesh_preparation as initial
from cells.processes import betse_initial_mesh_preparation_cache as caches
from cells.processes import betse_mesh_clip_preparation as clipped
from cells.processes import betse_mesh_lifecycle_preparation as lifecycle
from cells.processes import betse_normal_current as records
from cells.processes import betse_perturbations as streams
from validation.betse import betse_initial_mesh_preparation_native as caller_native
from validation.betse import betse_initial_mesh_preparation_wire as wire
from validation.betse import betse_mesh_lifecycle_preparation_fixtures as fixtures
from validation.betse import betse_mesh_lifecycle_preparation_native as native
from validation.betse import betse_mesh_lifecycle_preparation_reference as reference


def save(label, value, columns=None):
    if folder := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        root = Path(folder) / "mesh-lifecycle"
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
        columns.update({prefix + "__" + k: v for k, v in cache.numeric_columns().items()})
        return dict(column_prefix=prefix, descriptor=cache.descriptor, identity=cache.identity)

    value = dict(
        metadata,
        caches={k: record(k, v) for k, v in named.items()},
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
        columns.update({prefix + "__" + k: v for k, v in cache["columns"].items()})
        return dict(column_prefix=prefix, tree=cache["tree"])

    names = ("initial_cache", "before_lifecycle_cache", "cache", "events", "helper_result")
    value = {k: v for k, v in proof.items() if k not in names}
    for key in ("initial_cache", "before_lifecycle_cache", "cache"):
        value[key] = record(key, proof[key])
    value["helper_result"] = (
        None if proof["helper_result"] is None else record("helper_result", proof["helper_result"])
    )
    value["events"] = [
        {
            **{k: v for k, v in e.items() if k != "payload"},
            "payload": record(f"event{e['sequence']}", e["payload"]),
        }
        for e in proof["events"]
    ]
    save(label, value, columns)


def build_request(case, directory, *, label=None):
    label = case if label is None else label
    base, inputs = fixtures.declaration(case, directory)
    retain_caches(
        label + "-input",
        dict(inputs=inputs, initial_request=initial.request_record(base)),
        dict(constructor=caches.snapshot(dict(base.constructor_kwargs))),
        (),
    )
    try:
        seed_mesh = initial.prepare(base)
    except initial.InitialMeshRejected as error:
        if error.trial is not None:
            retain_caches(
                label + "-initial-failure",
                dict(state=initial.state_record(error.trial)),
                dict(final=error.trial.cache),
                error.trial.events,
            )
        raise
    clip_request = clipped.from_initial_mesh(base, seed_mesh)
    try:
        clip_state = clipped.prepare(clip_request)
    except clipped.ClipRejected as error:
        if error.trial is not None:
            retain_caches(
                label + "-clipping-failure",
                dict(state=clipped.state_record(error.trial)),
                dict(final=error.trial.cache),
                error.trial.events,
            )
        raise
    return fixtures.bind(base, seed_mesh, clip_state, inputs), inputs


def compare_events(actual, expected, *, failed=False):
    assert len(actual) == len(expected)
    for a, b in zip(actual, expected, strict=True):
        assert (a.sequence, a.kind, a.method, a.depth) == (
            b["sequence"],
            b["kind"],
            b["method"],
            b["depth"],
        )
        if failed and a.kind.endswith("failure"):
            left, right = (
                caches.plain(a.payload),
                wire.plain(b["payload"]["tree"], b["payload"]["columns"]),
            )
            left.pop("reason", None)
            right.pop("reason", None)
            assert records.record(left) == records.record(right)
        else:
            wire.compare_owned(a.payload.descriptor, a.payload.numeric_columns(), b["payload"])


def plain_events(events):
    return [
        dict(sequence=e.sequence, kind=e.kind, method=e.method, payload=caches.plain(e.payload))
        for e in events
    ]


def retained_reference(label, events, refinement):
    try:
        report = reference.evaluate(plain_events(events), refinement=refinement)
    except reference.ReferenceFailure as error:
        save(label + f"-reference-{refinement}-failure", error.trial)
        raise
    save(label + f"-reference-{refinement}", report)
    return report


def retained_trial(request, label):
    rejection = None
    try:
        state = lifecycle.prepare(request)
    except lifecycle.LifecycleRejected as error:
        rejection, state = error, error.trial
    if state is not None:
        retain_caches(
            label + "-actual",
            dict(request=lifecycle.request_record(request), state=lifecycle.state_record(state)),
            dict(before=state.before_cache, final=state.cache),
            state.events,
        )
    if rejection is not None:
        raise rejection
    return state


def fraction(actual, expected, atol):
    a, b = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
    assert a.shape == b.shape
    value = float(np.max(abs(a - b) / (np.asarray(atol) + 6e-12 * abs(b)), initial=0))
    assert value <= 1, value
    return value


def check_reports(first, second):
    maximum = resolution = 0.0
    for a, b in zip(first["pinv"], second["pinv"], strict=True):
        assert (a["sequence"], a["label"]) == (b["sequence"], b["label"])
        assert a["target"]["supported"] and a["target"]["rank_gap_resolved"]
        assert b["target"]["supported"] and b["target"]["rank_gap_resolved"]
        maximum = max(maximum, fraction(a["actual"], a["target"]["expected"], 2e-14))
        resolution = max(
            resolution, fraction(a["target"]["expected"], b["target"]["expected"], 2e-14)
        )
        for key, identity in a["identities"].items():
            maximum = max(maximum, fraction(identity["actual"], identity["expected"], 2e-14))
            resolution = max(
                resolution, fraction(identity["actual"], b["identities"][key]["actual"], 2e-14)
            )
    for a, b in zip(first["dots"], second["dots"], strict=True):
        assert (a["sequence"], a["label"]) == (b["sequence"], b["label"])
        if a["independent_accuracy_claim"]:
            floor = 1e-27 if a["units"] == "m" else 2e-14
            maximum = max(maximum, fraction(a["actual"], a["expected"], floor))
            resolution = max(resolution, fraction(a["expected"], b["expected"], floor))
    for a, b in zip(first["operators"], second["operators"], strict=True):
        assert a["exact_topological_entries"] and b["exact_topological_entries"]
        np.testing.assert_array_equal(a["actual"], a["expected"])
        assert a["expected"] == b["expected"]
    for name, floor in (("quality", 1e-26), ("energy", 2e-14)):
        for a, b in zip(first[name], second[name], strict=True):
            assert a["sequence"] == b["sequence"]
            maximum = max(maximum, fraction(a["actual"], a["expected"], floor))
            resolution = max(resolution, fraction(a["expected"], b["expected"], floor))
    for a, b in zip(first["smoothing"], second["smoothing"], strict=True):
        assert a["sequence"] == b["sequence"]
        maximum = max(maximum, fraction(a["source_MM"], a["expected_MM"], 2e-14))
        resolution = max(resolution, fraction(a["expected_MM"], b["expected_MM"], 2e-14))
        assert a["semantic_inverse"]["supported"] and a["semantic_inverse"]["rank_gap_resolved"]
        assert b["semantic_inverse"]["supported"] and b["semantic_inverse"]["rank_gap_resolved"]
        maximum = max(
            maximum, fraction(a["source_points_after_m"], a["expected_full_step_points_m"], 1e-27)
        )
        resolution = max(
            resolution,
            fraction(a["expected_full_step_points_m"], b["expected_full_step_points_m"], 1e-27),
        )
    for a, b in zip(first["moves"], second["moves"], strict=True):
        assert a["sequence"] == b["sequence"] and a["point_ids_before"] == a["point_ids_after"]
        assert records.record(a["actual"]) == records.record(a["expected"])
        assert a == b
    assert resolution <= 0.1
    return maximum, resolution


@pytest.mark.parametrize("case", fixtures.CASES)
def test_owned_source_lifecycle_trace_lineage_and_independent_algebra(tmp_path, case):
    request, inputs = build_request(case, tmp_path)
    rejection = None
    try:
        state = lifecycle.prepare(request)
    except lifecycle.LifecycleRejected as error:
        rejection, state = error, error.trial
    assert state is not None
    retain_caches(
        case + "-actual",
        dict(
            mode="actual_before_native_lifecycle",
            request=lifecycle.request_record(request),
            state=lifecycle.state_record(state),
            inputs=inputs,
        ),
        dict(before=state.before_cache, final=state.cache),
        state.events,
    )
    caller = caller_native.caller_kwargs(
        inputs["seed_recipe"], inputs["seed_stream_before"], inputs["controls"]
    )
    caller_cache = wire.capture(caller["kwargs"])
    save(
        case + "-native-caller",
        dict(
            kwargs=caller_cache["tree"], caller={k: v for k, v in caller.items() if k != "kwargs"}
        ),
        caller_cache["columns"],
    )
    proof = native.evaluate(
        caller["kwargs"],
        request.clip_request.initial_request.constructor_point_ids,
        caller["rng_before_constructor"],
        clipped.mask_record(request.clip_request),
        controls=lifecycle.parameters(request),
        origin=request.origin,
    )
    retain_native(case + "-native", proof)
    first = retained_reference(case, state.events, 1)
    second = retained_reference(case, state.events, 2)
    save(case + "-precomparison", dict(reference=first, refined_reference=second))
    assert rejection is None, (
        "Unexpected lifecycle refusal retained with source/native/reference buffers"
    )
    assert proof["status"] == "source_completed" and proof["failure"] is None
    wire.compare_owned(
        state.before_cache.descriptor,
        state.before_cache.numeric_columns(),
        proof["before_lifecycle_cache"],
    )
    wire.compare_owned(state.cache.descriptor, state.cache.numeric_columns(), proof["cache"])
    compare_events(state.events, proof["events"])
    assert list(state.point_ids_before) == list(proof["point_ids_before_lifecycle"])
    assert list(state.point_ids_after) == list(proof["point_ids_after_lifecycle"])
    assert streams.native_stream_manifest(state.stream_after)["state"] == proof["rng_after"]
    assert state.stream_after.identity == state.stream_before.identity
    assert proof["original_global_rng_unchanged"]
    termination = json.loads(state.termination_json)
    for key, value in proof["lifecycle_termination"].items():
        assert termination[key] == value
    maximum, resolution = check_reports(first, second)
    save(
        case,
        dict(
            mode="complete_unqualified_native_lifecycle",
            maximum_error_fraction=maximum,
            maximum_reference_resolution_fraction=resolution,
            termination=termination,
            origin=request.origin,
            topology_qualified=False,
            physical_geometry_admitted=False,
            upstream_initial_qualification="19/22 accuracy qualification open",
            old_geometry_primitives_changed=False,
            independent_convergence_branch_claim=False,
        ),
    )


def helper_pair(case):
    method, prototype, params = fixtures.helper(case)
    n = prototype.get("n_tverts", len(prototype["tri_verts"]))
    ids = tuple("manufactured-lifecycle-point-" + str(i) for i in range(n))
    before = streams.native_stream(17)
    saved = streams.native_stream_manifest(before)["state"]
    global_before = caller_native._state(np.random)
    rng = np.random.RandomState(0)
    rng.set_state((saved[0], np.asarray(saved[1], dtype=np.uint32), saved[2], saved[3], saved[4]))
    observer = lifecycle._Observer(ids)
    observer.lifecycle_active = True
    obj = object.__new__(lifecycle._Runtime)
    obj._cells_observer, obj._cells_rng = observer, initial._Random(rng, observer)
    obj._cells_tools = clipped._Tools(observer)
    for key, value in prototype.items():
        setattr(
            obj,
            key,
            np.array(value, copy=True, order="K") if isinstance(value, np.ndarray) else value,
        )
    result, failure = None, None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            result = getattr(obj, method)(**params)
        except Exception as error:
            failure = error
    actual_cache = caches.snapshot(initial._public_cache(obj))
    retain_caches(
        case + "-actual",
        dict(
            classification="isolated_manufactured_lifecycle_helper",
            method=method,
            failure_type=None if failure is None else type(failure).__name__,
            failure_message=None if failure is None else str(failure),
            warnings=[str(w.message) for w in caught],
            stream_before=streams.native_stream_manifest(before),
            stream_after=streams.native_stream_manifest(initial._rng_stream(rng)),
            original_global_rng_unchanged=global_before == caller_native._state(np.random),
        ),
        dict(
            prototype=caches.snapshot(prototype),
            params=caches.snapshot(params),
            final=actual_cache,
            result=caches.snapshot(result),
        ),
        observer.events,
    )
    proof = native.evaluate({}, ids, saved, None, helper=(method, prototype, params))
    retain_native(case + "-native", proof)
    assert initial._rng_stream(rng).identity == before.identity
    assert proof["rng_after"] == saved
    assert proof["original_global_rng_unchanged"]
    assert global_before == caller_native._state(np.random)
    return method, prototype, params, result, failure, observer, actual_cache, proof


@pytest.mark.parametrize("case", fixtures.HELPER_CASES)
def test_manufactured_source_algebra_and_convergence_witnesses(case):
    _, _, _, _, failure, observer, cache, proof = helper_pair(case)
    first = retained_reference(case, observer.events, 1)
    second = retained_reference(case, observer.events, 2)
    save(case + "-precomparison", dict(reference=first, refined_reference=second))
    assert failure is None and proof["failure"] is None
    wire.compare_owned(cache.descriptor, cache.numeric_columns(), proof["cache"])
    compare_events(observer.events, proof["events"])
    check_reports(first, second)
    fields = caches.plain(cache)
    if case == "refine-zero-steps":
        assert fields["mesh_qual"] == 123 and fields["removed_bad_verts"] is True
        assert observer.iterations_started == 0
    elif case == "refine-converged":
        assert fields["mesh_qual"] == 2 and fields["removed_bad_verts"] is False
        assert observer.converged and observer.iterations_completed == 1
    elif case == "smoothing-singular-constant":
        assert first["pinv"][0]["target"]["exact_rank"] == 1
        np.testing.assert_allclose(
            fields["tri_verts"], [[0.5, 1], [0.5, 1]], atol=1e-27, rtol=6e-12
        )


@pytest.mark.parametrize("case", fixtures.RAW_HELPER_CASES)
def test_raw_source_failures_retain_unexpected_completion_and_partial_matrices(case):
    _, _, _, _, failure, observer, cache, proof = helper_pair(case)
    assert failure is not None, "Unexpected helper completion retained before refusal assertion"
    assert proof["status"] == "source_failed" and proof["failure"]["type"] == type(failure).__name__
    wire.compare_owned(cache.descriptor, cache.numeric_columns(), proof["cache"])
    compare_events(observer.events, proof["events"], failed=True)
    assert any(e.kind == "lifecycle_partial_locals" for e in observer.events)


@pytest.mark.parametrize(
    "target", ("smoothing", "max_steps", "convergence", "unknown_field", "provenance")
)
def test_native_option_domain_refuses_undeclared_controls(tmp_path, target):
    request, _ = build_request("native-square-zero-smoothing", tmp_path, label="domain-" + target)
    recipe = request.options
    if target == "smoothing":
        recipe["parameters"][target] = "0"
    elif target == "max_steps":
        recipe["parameters"][target] = 26
    elif target == "convergence":
        recipe["parameters"][target] = float("inf")
    elif target == "unknown_field":
        recipe["parameters"][target] = True
    else:
        recipe["classification"] = "actual_make_voronoi_smoothing"
    with pytest.raises(ValueError):
        lifecycle.from_native_option_trial(request.clip_request, request.clip_state, recipe)


@pytest.mark.parametrize("target", ("identity", "controls", "owners", "clipping_cache"))
def test_resealed_lifecycle_input_tampering_is_refused(tmp_path, target):
    request, _ = build_request("native-square-zero-smoothing", tmp_path, label="tamper-" + target)
    if target == "identity":
        request = replace(request, identity="changed")
    elif target == "controls":
        options = request.options
        options["parameters"]["refinement"] = True
        request = replace(
            request,
            origin="owned_make_voronoi_lifecycle",
            options_json=json.dumps(options["parameters"]),
        )
        request = replace(request, identity=records._digest(lifecycle.request_record(request)))
    else:
        state = request.clip_state
        state = (
            replace(state, retained_point_ids=tuple(reversed(state.retained_point_ids)))
            if target == "owners"
            else replace(state, cache=caches.snapshot({}))
        )
        state = replace(state, identity=records._digest(clipped.state_record(state)))
        request = replace(request, clip_state=state)
        request = replace(request, identity=records._digest(lifecycle.request_record(request)))
    with pytest.raises(ValueError):
        lifecycle.validate_request(request)


def test_zero_smoothing_runs_source_rebuilds_and_retains_operators_until_final(tmp_path):
    request, _ = build_request(
        "native-square-zero-smoothing", tmp_path, label="zero-smoothing-order"
    )
    state = retained_trial(request, "zero-smoothing-order")
    events = plain_events(state.events)
    start = next(e["sequence"] for e in events if e["kind"] == "lifecycle_continuation_start")
    after = [e for e in events if e["sequence"] > start]
    assert sum(e["kind"] == "lifecycle_rebuild_enter" for e in after) == 2
    core_calls = [
        e for e in after if e["kind"] == "method_enter" and e["method"] == "create_core_operators"
    ]
    assert len(core_calls) == 2
    rebuilds = [
        e for e in after if e["kind"] in ("lifecycle_rebuild_enter", "lifecycle_rebuild_return")
    ]
    for enter, exit_ in zip(rebuilds[::2], rebuilds[1::2], strict=True):
        for key, value in enter["payload"]["cache"].items():
            if key.startswith("delta_"):
                assert records.record(value) == records.record(exit_["payload"]["cache"][key])
    assert not any(e["method"] == "refine_mesh" for e in after)


def test_owned_cache_and_output_carry_no_physical_geometry_authority(tmp_path):
    request, _ = build_request("caller-square-core", tmp_path, label="ownership")
    state = retained_trial(request, "ownership")
    for cache in (state.before_cache, state.cache, *(e.payload for e in state.events)):
        caches.validate(cache)
        for value in cache.numeric_columns().values():
            with pytest.raises(ValueError):
                value.setflags(write=True)
    exported = lifecycle.export_trial(request, state)
    assert not exported["topology_qualified"] and not exported["physical_geometry_admitted"]
    assert (
        not exported["stable_geometry_path"]
        and not exported["existing_native_exact_primitives_changed"]
    )


def test_independent_rank_domain_does_not_claim_unresolved_inverse():
    reports = []
    for precision in (100, 160):
        with localcontext() as context:
            context.prec = precision
            reports.append(
                reference.serial(
                    reference.pinv_reference(
                        [[Decimal(1), Decimal(0)], [Decimal(0), Decimal("1e-18")]]
                    )
                )
            )
    save("unresolved-rank-domain", dict(primary=reports[0], refined=reports[1]))
    assert all(not r["rank_gap_resolved"] for r in reports)


def test_independent_matrix_domain_refuses_empty_input():
    with pytest.raises(ValueError):
        reference.matrix([])
