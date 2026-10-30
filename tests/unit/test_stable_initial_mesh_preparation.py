"""Prepared bridge, ownership and independent geometric checks; unrun."""

import copy
import os
import traceback
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_environment_field as arrays
from cells.processes import betse_initial_mesh_preparation as initial
from cells.processes import betse_initial_mesh_preparation_cache as caches
from cells.processes import betse_normal_current as records
from cells.processes import stable_initial_mesh_preparation as bridge
from validation.geometry import stable_initial_mesh_preparation_fixtures as fixtures
from validation.geometry import stable_initial_mesh_preparation_io as transport
from validation.geometry import stable_initial_mesh_preparation_native as conditional
from validation.geometry import stable_initial_mesh_preparation_reference as reference


def evidence():
    root = Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / "stable-initial-mesh"
    root.mkdir(exist_ok=True)
    return root


def retain_actual(label, request, state, inputs, global_before, global_after):
    columns = {}

    def record(prefix, cache):
        columns.update(
            {prefix + "__" + name: value for name, value in cache.numeric_columns().items()}
        )
        return dict(column_prefix=prefix, descriptor=cache.descriptor, identity=cache.identity)

    actual = dict(
        kind="cells.stable_initial_mesh_actual_evidence@1",
        case=label,
        inputs=inputs,
        request=arrays.plain(bridge.request_record(request)),
        state=bridge.state_record(state),
        global_rng_before=global_before,
        global_rng_after=global_after,
        request_cache=record(
            "request", caches.snapshot(dict(request.native_request.constructor_kwargs))
        ),
        constructed=record("constructed", state.constructed_cache),
        final=record("final", state.cache),
        events=[
            dict(
                sequence=e.sequence,
                kind=e.kind,
                method=e.method,
                depth=e.depth,
                payload=record(f"event{e.sequence}", e.payload),
            )
            for e in state.events
        ],
    )
    transport.write(evidence() / (label + "-actual"), arrays.plain(actual), columns)
    # Round-trip through the actual persisted archive; no live object authority
    # is passed to either replay or the independent mathematical provider.
    return transport.read(evidence() / (label + "-actual.json"))


def trial(case, tmp_path):
    native_request, inputs = fixtures.native_request(case, tmp_path)
    request = bridge.opt_in(native_request, law_id=bridge.LAW_ID)
    global_before = initial.streams.native_stream_manifest(initial._rng_stream(np.random))["state"]
    failure = None
    try:
        state = bridge.prepare(request)
    except bridge.StableMeshRejected as error:
        state, failure = (
            error.trial,
            dict(
                type=type(error).__name__,
                message=str(error),
                stage=error.stage,
                traceback=traceback.format_exc(),
            ),
        )
    assert state is not None
    global_after = initial.streams.native_stream_manifest(initial._rng_stream(np.random))["state"]
    actual = retain_actual(case, request, state, inputs, global_before, global_after)
    transport.write(evidence() / (case + "-outcome"), dict(failure=failure, status=state.status))
    assert global_before == global_after
    return native_request, request, state, actual


def mathematical_report(case, actual, archive):
    events = transport.load_events(actual, archive)
    plain = transport.plain_events(events)
    final = transport.load_cache(actual["final"], archive)
    final = transport.wire.plain(final["tree"], final["columns"])
    reports = []
    for refinement in (1, 2):
        try:
            report = reference.evaluate(
                final, plain, completed=actual["state"]["pre_mesh_completed"], refinement=refinement
            )
        except Exception as error:
            transport.write(
                evidence() / (case + f"-reference-error-{refinement}"),
                dict(
                    type=type(error).__name__, message=str(error), traceback=traceback.format_exc()
                ),
            )
            raise
        transport.write(evidence() / (case + f"-reference-{refinement}"), report)
        reports.append(report)
    repairs = reference.compare_repairs(*reports)
    geometry = reference.compare_whole_mesh(*reports)
    return dict(primitive_comparisons=repairs, whole_mesh=geometry)


def assess(case, native_request, state, actual):
    with np.load(evidence() / (case + "-actual.npz"), allow_pickle=False) as archive:
        events = transport.load_events(actual, archive)
        proof = conditional.evaluate(
            dict(native_request.constructor_kwargs),
            native_request.constructor_point_ids,
            initial.streams.native_stream_manifest(native_request.stream_before)["state"],
            conditional.tape_from_events(events),
        )
        transport.retain_native(evidence() / (case + "-conditional-native"), proof)
        source_comparison = transport.compare_native(actual, archive, proof)
        mathematical = mathematical_report(case, actual, archive)
    summary = dict(
        case=case,
        status=state.status,
        source_comparison=source_comparison,
        **mathematical,
        exact_native_arithmetic_equivalence=False,
        physical_geometry_admitted=False,
        topology_qualified=False,
        original_19_of_22_limitation_reclassified=False,
    )
    transport.write(evidence() / (case + "-summary"), summary)
    return summary


@pytest.mark.parametrize("case", fixtures.MESH_CASES)
def test_bridge_case(case, tmp_path):
    native_request, request, state, actual = trial(case, tmp_path)
    summary = assess(case, native_request, state, actual)
    assert type(request) is bridge.Request and type(state) is bridge.State
    assert request.native_request is native_request
    assert type(state) is not initial.State
    assert state.status == "stable_mesh_completed_unqualified"
    assert summary["source_comparison"]["conditional_source_equivalence"]
    assert not summary["exact_native_arithmetic_equivalence"]
    # Any unchanged source mapping/quad defect leaves this candidate open.
    # Reports and all original buffers have already been durably retained.
    assert summary["whole_mesh"]["whole_mesh_passed"], summary["whole_mesh"]


@pytest.mark.parametrize("case", fixtures.RAW_CASES)
def test_raw_source_failure(case, tmp_path):
    native_request, _, state, actual = trial(case, tmp_path)
    summary = assess(case, native_request, state, actual)
    assert state.status == "retained_stable_mesh_failure"
    assert not state.pre_mesh_completed
    assert summary["source_comparison"]["conditional_source_equivalence"]
    assert summary["whole_mesh"]["partial_failure_preserved"]


def test_existing_B09_physical_admission():
    with pytest.raises(ValueError):
        fixtures.original.reused_B09("merged-square-aux")
    transport.write(
        evidence() / "B09-admission",
        dict(
            merged_square_refused_by_original_physical_adapter=True,
            native_input_flags_rewritten=False,
            physical_geometry_admitted=False,
        ),
    )


@pytest.mark.parametrize("case", fixtures.REQUEST_CASES)
def test_request_admission(case, tmp_path):
    native_request, _ = fixtures.native_request("irregular-centroid-aux", tmp_path)
    request = bridge.opt_in(native_request, law_id=bridge.LAW_ID)
    with pytest.raises(ValueError):
        if case == "wrong-law":
            bridge.opt_in(native_request, law_id=initial.LAW_ID)
        elif case == "boolean-law":
            bridge.opt_in(native_request, law_id=True)
        elif case == "native-request-type":
            bridge.validate_request(native_request)
        elif case == "changed-opt-in":
            changed = replace(request, opted_in_law=initial.LAW_ID)
            bridge.validate_request(
                replace(changed, identity=records._digest(bridge.request_record(changed)))
            )
        elif case == "changed-request-identity":
            bridge.validate_request(replace(request, identity="0" * 64))
        elif case == "forged-native-identity":
            bridge.opt_in(replace(native_request, identity="0" * 64), law_id=bridge.LAW_ID)
        else:
            raise AssertionError(case)
    transport.write(
        evidence() / (case + "-request-refusal"), dict(case=case, authenticated_refusal=True)
    )


@pytest.mark.parametrize("case", fixtures.OWNERSHIP_CASES)
def test_state_ownership(case, tmp_path):
    _, request, state, _ = trial("irregular-centroid-aux", tmp_path)
    if case == "native-state-type":
        fields = {name: getattr(state, name) for name in initial.State.__dataclass_fields__}
        changed = initial.State(**fields)
    elif case == "changed-state-identity":
        changed = replace(state, identity="0" * 64)
    elif case == "changed-cache":
        changed = replace(state, cache=caches.snapshot(dict(unowned=True)))
    elif case == "changed-rng":
        changed = replace(state, stream_after=state.stream_before)
        # This fixture may have no constructor RNG draw. Use a definitely
        # different authenticated stream from a new private source instead.
        saved = np.random.RandomState(983).get_state()
        other = initial.streams._native_stream(
            [saved[0], saved[1].tolist(), int(saved[2]), int(saved[3]), float(saved[4])],
            np.__version__,
        )
        changed = replace(changed, stream_after=other)
    elif case == "changed-occurrence-order":
        changed = replace(state, retained_point_ids=tuple(reversed(state.retained_point_ids)))
    elif case == "changed-certificate-event":
        events = list(state.events)
        i = next(i for i, event in enumerate(events) if event.kind == "primitive_repair_result")
        payload = caches.plain(events[i].payload)
        payload["result"] = copy.deepcopy(payload["result"])
        payload["result"]["method"] = "unowned"
        events[i] = replace(events[i], payload=caches.snapshot(payload))
        changed = replace(state, events=tuple(events))
    else:
        raise AssertionError(case)
    if type(changed) is bridge.State and case != "changed-state-identity":
        changed = replace(changed, identity=records._digest(bridge.state_record(changed)))
    with pytest.raises(ValueError):
        bridge.validate_state(request, changed)
    transport.write(
        evidence() / (case + "-ownership"), dict(case=case, resealed_tamper_refused=True)
    )


@pytest.mark.parametrize("case", fixtures.COMPLEX_CONTROLS)
def test_independent_complex_controls(case):
    polygons, expected = fixtures.complex_control(case)
    report = reference.complex_geometry(polygons, label=case)
    transport.write(
        evidence() / (case + "-complex-control"),
        dict(polygons=polygons, expected=expected, report=report),
    )
    assert report["passed"] is expected
    assert not report["topology_qualified"]
