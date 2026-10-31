"""Unrun paired-owner projection/bootstrap controls; launch belongs to Chief."""

import json
import os
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace

import pytest

from cells.processes import betse_native_membrane_initialization as entry
from cells.processes import betse_native_membrane_layout as layout
from cells.processes import betse_normal_ecm_initialization as initial
from cells.processes import betse_normal_ion_join as ions
from validation.betse import betse_native_membrane_initialization_archive as archive
from validation.betse import betse_native_membrane_initialization_fixtures as fixtures


def persist(root, name, value):
    archive.write(root / (name + ".json"), value)


def observer(root, prefix):
    def save(name, value):
        if name == "capture-input":
            owners = value["owners"]
            value = dict(value)
            value.pop("owners")
            value["original_six_stores"] = archive.original_six_stores(owners["cells"])
            value["owner_inventory"] = fixtures.owner_inventory(owners)
            value["cell_to_mems"] = vars(owners["cells"]).get("cell_to_mems")
        persist(root, prefix + "-" + name, value)

    return save


def begin(root, case, purpose, refusal=None):
    persist(
        root,
        "declared-input",
        dict(
            case=case,
            refusal=refusal,
            purpose=purpose,
            entry_declaration=fixtures.declaration(),
            layout_declaration=fixtures.layout_declaration(),
            owner_specimen_source="held_initialization02_supplied_owners",
            native_seed_init_history_claim=False,
            launch_owner="Chief/Root",
        ),
    )
    return dict(
        case=case,
        purpose=purpose,
        refusal=refusal,
        stage="declared",
        inputs=None,
        original=None,
        request=None,
        candidate=None,
        reference=None,
    )


def failure(root, state, error):
    try:
        persist(
            root,
            "failure",
            dict(
                state=state,
                original=getattr(error, "original", None),
                **fixtures.previous.failure_record(error),
            ),
        )
    except BaseException as capture_error:
        error.add_note("Failure sidecar capture also failed: " + repr(capture_error))
        try:
            with (root / "failure-capture-error.json").open("x") as stream:
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
        except BaseException as sidecar_error:
            error.add_note("Failure capture fallback also failed: " + repr(sidecar_error))


def construct(root, state, *, before_prepare=None):
    state["stage"] = "deferred_supplied_owner_construction"
    spec = fixtures.specimen(
        state["case"], refusal=state["refusal"], observer=observer(root, "fixture")
    )
    # Freeze a typed, byte-exact view directly from the caller before capture.
    # This baseline is independent of both objects returned by the handoff.
    state["pre_capture_network_cache"] = archive.snapshot(spec["network_cache"])
    persist(root, "original-pre-capture-network-cache", state["pre_capture_network_cache"])
    state["inputs"] = dict(
        raw=spec["raw"],
        binding=spec["binding"],
        original_six_stores=archive.original_six_stores(spec["owners"]["cells"]),
        owner_inventory=fixtures.owner_inventory(spec["owners"]),
        network_cache=spec["network_cache"],
        entry_declaration=spec["entry_declaration"],
        layout_declaration=spec["layout_declaration"],
    )
    persist(root, "complete-supplied-inputs", state["inputs"])
    state["stage"] = "paired_capture"
    pair = fixtures.capture(spec, observer=observer(root, "capture"))
    state["original"] = pair
    persist(root, "complete-paired-original", pair)
    state["stage"] = "prepare"
    if before_prepare is not None:
        before_prepare()
    prepared = entry.prepare(
        spec["binding"], pair, spec["entry_declaration"], observer=observer(root, "prepare")
    )
    state["request"] = prepared
    persist(root, "prepared-component-entry", prepared)
    return spec, pair, prepared


def forbid(*args, **kwargs):
    raise AssertionError("The bridge may not reset native owners or replay initialization")


def guards(monkeypatch):
    calls = []
    restore, reconstruct = initial.source.restore, initial.field.reconstruct

    def tracked_restore(*args, **kwargs):
        calls.append("restore")
        return restore(*args, **kwargs)

    def tracked_reconstruct(*args, **kwargs):
        calls.append("bootstrap")
        return reconstruct(*args, **kwargs)

    monkeypatch.setattr(initial.source, "cold", forbid)
    monkeypatch.setattr(initial.field, "initialize", forbid)
    monkeypatch.setattr(initial.calcium, "initialize", forbid)
    monkeypatch.setattr(initial.source, "restore", tracked_restore)
    monkeypatch.setattr(initial.field, "reconstruct", tracked_reconstruct)
    return calls


def bootstrap(root, state, prepared):
    state["stage"] = "single_held_component_bootstrap"
    persist(root, "component-call-before", prepared)
    candidate = entry.bootstrap_component(prepared, observer=observer(root, "bootstrap"))
    state["candidate"] = candidate
    persist(root, "component-entry-return", candidate)
    return candidate


def independent(root, state, payload):
    state["stage"] = "independent_byte_owner_cache_check"
    parent_pid = os.getpid()
    payload = dict(payload, original_six_stores=state["inputs"]["original_six_stores"])
    persist(root, "independent-input", payload)
    output = root / "independent-output.json"
    with (root / "independent.stdout.log").open("x") as stream:
        try:
            process = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "validation.betse.betse_native_membrane_initialization_reference",
                    "--input",
                    str(root / "independent-input.json"),
                    "--output",
                    str(output),
                ],
                stdout=stream,
                stderr=subprocess.STDOUT,
                timeout=480,
                check=False,
            )
        except Exception as error:
            persist(
                root,
                "independent-process-failure",
                dict(type=type(error).__name__, reason=str(error)),
            )
            raise
        finally:
            stream.flush()
            os.fsync(stream.fileno())
    persist(root, "independent-process", dict(returncode=process.returncode))
    report = json.loads(output.read_text()) if output.is_file() else None
    state["reference"] = report
    if report is None:
        raise RuntimeError("Independent input, process log and partial output remain retained")
    assert report["runtime_origin"]["parent_pid"] == parent_pid
    assert report["runtime_origin"]["pid"] != parent_pid
    assert process.returncode == (0 if report["passed"] else 1)
    return report


@pytest.mark.parametrize("case", fixtures.CASES)
def test_explicit_six_column_component_entry(case, tmp_path, monkeypatch):
    state = begin(tmp_path, case, "conditional supplied component bridge; no native-chain credit")
    try:
        spec, pair, prepared = construct(tmp_path, state)
        original = entry.digest(pair)
        calls = guards(monkeypatch)
        candidate = bootstrap(tmp_path, state, prepared)
        assert calls == ["restore", "bootstrap"]
        assert entry.digest(pair) == original
        assert candidate.request.original is pair
        assert all(value is False for value in candidate.gates.values())
        assert ions.digest(candidate.component_handoff.parent.network.network_cache) == ions.digest(
            pair.boundary.network_cache["value"]
        )
        cache_retention = dict(
            original_pre_capture=state["pre_capture_network_cache"],
            boundary=archive.snapshot(pair.boundary.network_cache["value"]),
            component=archive.snapshot(candidate.component_handoff.parent.network.network_cache),
            original_after=archive.snapshot(spec["network_cache"]),
        )
        persist(tmp_path, "original-cache-through-component-retention", cache_retention)
        assert cache_retention["boundary"] == cache_retention["original_pre_capture"]
        assert cache_retention["component"] == cache_retention["original_pre_capture"]
        assert cache_retention["original_after"] == cache_retention["original_pre_capture"]
        assert independent(tmp_path, state, dict(original=pair, request=prepared, entry=candidate))[
            "passed"
        ]
        with pytest.raises(entry.EntryRejected) as caught:
            entry.require_ordinary_loop(candidate)
        persist(
            tmp_path,
            "expected-ordinary-loop-refusal",
            dict(
                reason=str(caught.value),
                original=caught.value.original,
                partial=caught.value.partial,
            ),
        )
    except Exception as error:
        failure(tmp_path, state, error)
        raise


@pytest.mark.parametrize("name", fixtures.REFUSALS)
def test_missing_changed_or_unready_owners_cannot_enter(name, tmp_path, monkeypatch):
    state = begin(tmp_path, "field", "declared source/schema refusal: " + name, name)
    try:
        unexpected_calls = []

        def unexpected_hydration(*args, **kwargs):
            unexpected_calls.append("hydration_or_bootstrap")
            raise AssertionError("Unready owners must fail before hydration/bootstrap")

        def before_prepare():
            monkeypatch.setattr(initial.source, "cold", forbid)
            monkeypatch.setattr(initial.source, "restore", unexpected_hydration)
            monkeypatch.setattr(initial.field, "reconstruct", unexpected_hydration)

        # Cold calls are needed only by the explicitly declared fixture setup.
        # Preparation itself is guarded by the recorded rejection below.
        with pytest.raises(entry.EntryRejected) as caught:
            construct(tmp_path, state, before_prepare=before_prepare)
        persist(
            tmp_path,
            "expected-source-readiness-refusal",
            dict(
                original=getattr(caught.value, "original", None),
                partial=getattr(caught.value, "partial", None),
                **fixtures.previous.failure_record(caught.value),
            ),
        )
        assert unexpected_calls == []
        expected_stage = (
            "declaration"
            if name in ("wrong-conversion", "wrong-geometry-policy", "wrong-stage")
            else "common_owner_and_hot_cache_readiness"
            if name in fixtures.OLD_REFUSALS
            else "explicit_projection"
        )
        assert caught.value.stage == expected_stage
    except Exception as error:
        failure(tmp_path, state, error)
        raise


@pytest.mark.parametrize("name", fixtures.CALCIUM_REFUSALS)
def test_existing_calcium_admission_precedes_hydration(name, tmp_path, monkeypatch):
    state = begin(tmp_path, "calcium", "retained optional calcium refusal: " + name, name)
    try:
        _, _, prepared = construct(tmp_path, state)
        calls = guards(monkeypatch)
        with pytest.raises(entry.EntryRejected) as caught:
            bootstrap(tmp_path, state, prepared)
        persist(
            tmp_path,
            "expected-calcium-admission-refusal",
            dict(
                original=caught.value.original,
                partial=caught.value.partial,
                **fixtures.previous.failure_record(caught.value),
            ),
        )
        assert calls == []
        assert caught.value.stage == "held_component_handoff"
    except Exception as error:
        failure(tmp_path, state, error)
        raise


@pytest.mark.parametrize("name", fixtures.RESEALED)
def test_resealed_projection_readiness_and_gates_are_revalidated(name, tmp_path, monkeypatch):
    state = begin(tmp_path, "field", "declared resealed bridge control: " + name)
    try:
        _, pair, prepared = construct(tmp_path, state)
        if name == "projected-store":
            boundary = prepared.projected_boundary
            cells = dict(boundary.owners["cells"])
            value = cells["mem_vects_flat"]["value"].copy()
            value[0, 0] += 0.125
            cells["mem_vects_flat"] = ions.freeze(dict(present=True, captured=True, value=value))
            changed_boundary = replace(
                boundary, owners=ions.freeze(dict(boundary.owners, cells=cells)), identity=""
            )
            changed_boundary = replace(
                changed_boundary, identity=ions.digest(initial.boundary_record(changed_boundary))
            )
            prepared = replace(prepared, projected_boundary=changed_boundary, identity="")
        elif name == "readiness":
            prepared = replace(
                prepared,
                readiness=ions.freeze(dict(prepared.readiness, common_state_identity="0" * 64)),
                identity="",
            )
        elif name == "physical-gate":
            prepared = replace(
                prepared,
                gates=ions.freeze(dict(prepared.gates, physical_geometry_admitted=True)),
                identity="",
            )
        elif name == "conversion-view":
            view = layout.normal_tangent_view(
                prepared.six_column_layout, opted_in_conversion=layout.NORMAL_TANGENT_LAW
            )
            prepared = replace(prepared, explicit_view=view, identity="")
        elif name == "original-pair":
            prepared = replace(prepared, original=replace(pair, identity="0" * 64), identity="")
        prepared = replace(prepared, identity=entry.digest(entry.request_record(prepared)))
        persist(tmp_path, "resealed-bridge-request", prepared)
        monkeypatch.setattr(initial, "handoff", forbid)
        with pytest.raises(entry.EntryRejected) as caught:
            entry.bootstrap_component(prepared)
        persist(
            tmp_path,
            "expected-resealed-request-refusal",
            dict(
                original=caught.value.original,
                partial=caught.value.partial,
                **fixtures.previous.failure_record(caught.value),
            ),
        )
        assert caught.value.stage == "request_authentication"
    except Exception as error:
        failure(tmp_path, state, error)
        raise


def flip_byte(array):
    raw = bytearray.fromhex(array["raw_bytes_hex"])
    raw[0] ^= 1
    array["raw_bytes_hex"] = bytes(raw).hex()


@pytest.mark.parametrize("name", fixtures.CORRUPTIONS)
def test_independent_projection_parent_and_cache_gates(name, tmp_path, monkeypatch):
    state = begin(tmp_path, "field", "declared independent output corruption: " + name)
    try:
        _, pair, prepared = construct(tmp_path, state)
        calls = guards(monkeypatch)
        candidate = bootstrap(tmp_path, state, prepared)
        assert calls == ["restore", "bootstrap"]
        payload = archive.snapshot(dict(original=pair, request=prepared, entry=candidate))
        request = payload["request"]
        if name == "projection-column-map":
            request["explicit_view"]["selected_columns"] = [2, 3, 4, 5]
        elif name == "projection-midpoint-byte":
            flip_byte(request["projected_boundary"]["owners"]["cells"]["mem_vects_flat"]["value"])
        elif name == "unrelated-store":
            flip_byte(request["projected_boundary"]["owners"]["sim"]["vm"]["value"])
        elif name == "cache-epoch":
            flip_byte(
                request["projected_boundary"]["network_cache"]["value"]["wire"][
                    "ion_boundary_state"
                ]
            )
        elif name == "dropped-tangent":
            request["six_column_layout"]["snapshot"]["entries"]["mem_vects_flat"]["value"]["shape"][
                1
            ] = 4
        elif name == "component-cache":
            flip_byte(
                payload["entry"]["component_handoff"]["parent"]["network"]["network_cache"]["wire"][
                    "molecule_fields"
                ]["X"]["c_cells"]
            )
        elif name == "native-observation-claim":
            request["projected_boundary"]["observation_kind"] = (
                "pinned_native_objects_at_declared_boundary"
            )
        elif name == "ordinary-loop-gate":
            payload["entry"]["gates"]["ordinary_ECM_loop_ready"] = True
        payload["entry"]["request"] = deepcopy(request)
        report = independent(tmp_path, state, payload)
        assert report["passed"] is False
        archive.require_declared_refusal(
            report,
            {
                "projection-column-map": "independent_six_column_layout_owner_and_projection_check",
                "projection-midpoint-byte": "only_named_membrane_store_projected",
                "unrelated-store": "only_named_membrane_store_projected",
                "cache-epoch": "hot_cache_and_exclusions_unchanged",
                "dropped-tangent": "independent_six_column_layout_owner_and_projection_check",
                "component-cache": "hot_cache_retained_after_bootstrap",
                "native-observation-claim": "projection_cannot_claim_native_capture",
                "ordinary-loop-gate": "unqualified_component_entry_scope",
            }[name],
        )
    except Exception as error:
        failure(tmp_path, state, error)
        raise


def test_capture_keeps_original_six_columns_and_hot_buffers(tmp_path):
    state = begin(tmp_path, "field", "caller stores may mutate after paired capture")
    try:
        spec, pair, _ = construct(tmp_path, state)
        original = entry.digest(pair)
        spec["owners"]["cells"].mem_vects_flat[:] = 17.0
        spec["owners"]["cells"].mem_mids_flat[:] = 19.0
        spec["network_cache"]["wire"]["molecule_fields"]["X"]["c_cells"][:] = 23.0
        persist(
            tmp_path,
            "changed-caller-buffers",
            dict(
                vectors=spec["owners"]["cells"].mem_vects_flat,
                mids=spec["owners"]["cells"].mem_mids_flat,
                cache=spec["network_cache"],
            ),
        )
        assert entry.digest(pair) == original
        prepared = entry.prepare(spec["binding"], pair, spec["entry_declaration"])
        persist(tmp_path, "prepared-independent-captured-buffers", prepared)
    except Exception as error:
        failure(tmp_path, state, error)
        raise


def test_native_capture_rejects_supplied_lookalikes(tmp_path):
    state = begin(tmp_path, "field", "source class/pins are required for native observations")
    try:
        spec, _, _ = construct(tmp_path, state)
        phase = fixtures.previous.namespace_phase(spec)
        with pytest.raises(entry.EntryRejected) as caught:
            entry.capture_native(
                phase,
                spec["declaration"],
                spec["layout_declaration"],
                observer=observer(tmp_path, "native-probe"),
            )
        persist(
            tmp_path,
            "expected-native-class-refusal",
            dict(
                original=caught.value.original,
                partial=caught.value.partial,
                **fixtures.previous.failure_record(caught.value),
            ),
        )
    except Exception as error:
        failure(tmp_path, state, error)
        raise
