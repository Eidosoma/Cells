"""Prepared owner-routing checks. Construction/execution require Chief's launch."""

import json
from dataclasses import replace

import numpy as np
import pytest

from cells.processes import betse_ecm_grn_join as network
from cells.processes import betse_ecm_grn_source as source
from cells.processes import betse_normal_ecm_calcium_join as calcium
from cells.processes import betse_normal_ecm_field_join as field
from cells.processes import betse_normal_ecm_initialization as handoff
from cells.processes import betse_normal_ecm_mechanics_join as mechanical
from cells.processes import betse_normal_ion_join as ions
from validation.betse import betse_normal_ecm_initialization_fixtures as fixtures
from validation.betse import betse_normal_ecm_mechanics_join_runtime as archives


def persist(root, name, value):
    root.mkdir(parents=True, exist_ok=True)
    archives.write(root / (name + ".json"), value)
    archives.write(root / (name + "-types.json"), archives.typed_inventory(value))
    with (root / (name + ".npz")).open("xb") as stream:
        np.savez_compressed(stream, **archives.arrays(value))


def forbid(*args, **kwargs):
    raise AssertionError("The handoff must not call a cold initializer or replay native dynamics")


def recorded(root, name, operation, *args, before=None, **kwargs):
    """Persist the accepted input and complete exception partials without a retry."""
    persist(root, name + "-before", dict(operation=operation.__qualname__, previous=before))
    try:
        return operation(*args, **kwargs)
    except BaseException as error:
        try:
            persist(
                root,
                name + "-failure",
                dict(previous=before, **fixtures.failure_record(error)),
            )
        except BaseException as capture_error:
            # The traceback and last complete archives survive a sidecar error;
            # the original exception remains authoritative.
            error.add_note("Numeric failure capture also failed: " + repr(capture_error))
            try:
                with (root / (name + "-capture-failure.json")).open("x") as stream:
                    json.dump(
                        dict(
                            original_type=type(error).__name__,
                            original_message=str(error),
                            capture_type=type(capture_error).__name__,
                            capture_message=str(capture_error),
                        ),
                        stream,
                    )
            except BaseException as sidecar_error:
                error.add_note("Failure sidecar also failed: " + repr(sidecar_error))
        raise


def fixture_observer(root):
    return lambda name, value: persist(root, "fixture-" + name, value)


def owner_baseline(spec, cold, supplied):
    """Rebind cold component output to independently captured supplied owners.

    Physical fields, material, clock, calcium and mechanics remain the cold
    component's outputs. Only its declaration-based controls/cache are replaced
    by the pre-capture owners, preserving their exact representations. This is
    an existing-component comparison, not an independent numerical reference.
    """
    component = cold.field if type(cold) is mechanical.State else cold
    assert ions.digest(component.network.network_cache) == ions.digest(supplied["network_cache"])
    assert set(component.network.controls) == set(supplied["controls"])
    for key, values in component.network.controls.items():
        declared = np.asarray(values)
        actual = supplied["controls"][key]
        assert declared.dtype == actual.dtype and declared.shape == actual.shape
        np.testing.assert_array_equal(declared, actual)
    parent = network._state(
        spec["binding"],
        component.network.material,
        supplied["network_cache"],
        supplied["controls"],
    )
    expected = (
        calcium.joined_state(
            spec["binding"], parent, component.field, component.rate_cache, component.clock
        )
        if type(component) is calcium.CalciumFieldState
        else field.state(spec["binding"], parent, component.field)
    )
    return (
        mechanical.state(spec["outer"], expected, cold.mechanics)
        if type(cold) is mechanical.State
        else expected
    )


@pytest.mark.parametrize("case", fixtures.CASES)
def test_complete_supplied_handoff(case, tmp_path, monkeypatch):
    spec = recorded(
        tmp_path,
        "specimen",
        fixtures.specimen,
        case,
        before=dict(case=case),
        on_capture=fixture_observer(tmp_path),
    )
    # Read the real owners before admission, without using handoff._copy or
    # any value returned by the candidate. Freeze arrays against later mutation.
    supplied = ions.freeze(
        dict(
            controls={key: getattr(spec["ctx"].sim, key) for key in ("gj_block", "NaKATP_block")},
            network_cache=spec["network_cache"],
        )
    )
    persist(tmp_path, "supplied-owner-baseline-input", supplied)
    boundary = recorded(
        tmp_path,
        "capture",
        fixtures.capture,
        spec,
        before=dict(raw=spec["raw"]),
    )
    persist(tmp_path, "original-inputs", spec["raw"])
    persist(tmp_path, "boundary", boundary)
    original_boundary = ions.digest(boundary)
    original_material = ions.digest(source.material_values(spec["ctx"].sim))
    original_cache = ions.digest(spec["network_cache"])
    binding = spec["binding"]
    # This is an existing-component baseline on the same declared owners, not
    # an independent scientific reference or a native initialization run.
    if case != "warm-owner":
        baseline = (
            recorded(
                tmp_path,
                "baseline",
                mechanical.initialize,
                spec["outer"],
                before=dict(boundary=boundary, binding=spec["outer"]),
            )
            if case == "mechanics"
            else recorded(
                tmp_path,
                "baseline",
                calcium.initialize,
                binding,
                before=dict(boundary=boundary, binding=binding),
            )
            if case == "calcium"
            else recorded(
                tmp_path,
                "baseline",
                field.initialize,
                binding,
                before=dict(boundary=boundary, binding=binding),
            )
        )
        persist(tmp_path, "component-baseline", baseline)
        baseline = owner_baseline(spec, baseline, supplied)
        persist(tmp_path, "supplied-owner-component-baseline", baseline)
    calls = []
    reconstruct = field.reconstruct

    def bootstrap(*args, **kwargs):
        calls.append("bootstrap")
        return reconstruct(*args, **kwargs)

    monkeypatch.setattr(source, "cold", forbid)
    monkeypatch.setattr(field, "initialize", forbid)
    monkeypatch.setattr(calcium, "initialize", forbid)
    monkeypatch.setattr(mechanical, "initialize", forbid)
    monkeypatch.setattr(field, "reconstruct", bootstrap)
    entered = recorded(
        tmp_path,
        "handoff",
        handoff.handoff,
        binding,
        boundary,
        before=dict(binding=binding, boundary=boundary),
    )
    persist(tmp_path, "field-handoff", entered)
    assert calls == ["bootstrap"]
    assert entered.provenance["cold_owner_calls"] == 0
    assert entered.provenance["native_init_dynamics_calls"] == 0
    assert entered.provenance["native_seed_init_load_chain_established"] is False
    assert entered.provenance["full_SimRunner_executed"] is False
    assert entered.provenance["geometry_classification"] == "supplied_layout"
    if case == "mechanics":
        entered = recorded(
            tmp_path,
            "mechanics-handoff-call",
            handoff.handoff_mechanics,
            spec["outer"],
            boundary,
            entered,
            before=dict(binding=spec["outer"], boundary=boundary, previous_handoff=entered),
        )
        persist(tmp_path, "mechanics-handoff", entered)
        assert entered.provenance["mechanics_admitted"] is True
        assert entered.provenance["mechanical_calls"] == 0
    assert original_boundary == ions.digest(boundary)
    assert original_material == ions.digest(source.material_values(spec["ctx"].sim))
    assert original_cache == ions.digest(spec["network_cache"])
    parent = entered.parent
    component = parent.field if type(parent) is mechanical.State else parent
    # Check the full typed inventories as well as the existing state identities.
    assert archives.typed_inventory(component.network.network_cache) == archives.typed_inventory(
        supplied["network_cache"]
    )
    assert archives.typed_inventory(component.network.controls) == archives.typed_inventory(
        supplied["controls"]
    )
    if case == "warm-owner":
        assert ions.digest(parent.network.network_cache) == original_cache
        np.testing.assert_array_equal(
            parent.network.network_cache["wire"]["molecule_fields"]["X"]["c_cells"],
            spec["ctx"].sim.grn.core.molecules["X"].c_cells,
        )
    else:
        assert ions.digest(parent) == ions.digest(baseline)
        assert archives.typed_inventory(parent) == archives.typed_inventory(baseline)
    # The returned object can enter the unchanged existing loop directly.
    # No source comparison/accuracy credit is earned by this identity check.
    for index in range(3):
        if case == "mechanics":
            parent, context = recorded(
                tmp_path,
                "advance-" + str(index),
                mechanical.advance,
                spec["outer"],
                parent,
                before=dict(binding=spec["outer"], boundary=boundary, parent=parent),
            )
        elif case == "calcium":
            result = recorded(
                tmp_path,
                "advance-" + str(index),
                calcium.advance,
                binding,
                parent,
                before=dict(binding=binding, boundary=boundary, parent=parent),
            )
            parent, context = result[0], result[1:]
        else:
            result = recorded(
                tmp_path,
                "advance-" + str(index),
                field.advance,
                binding,
                parent,
                before=dict(binding=binding, boundary=boundary, parent=parent),
            )
            parent, context = result[0], result[1:]
        persist(tmp_path, "step-" + str(index) + "-parent", parent)
        persist(tmp_path, "step-" + str(index) + "-context", context)
    assert calls == ["bootstrap"] * 4
    assert original_boundary == ions.digest(boundary)


@pytest.mark.parametrize("name", fixtures.REFUSALS)
def test_incomplete_or_changed_boundary_is_refused(name, tmp_path, monkeypatch):
    spec, case = recorded(
        tmp_path,
        "refusal-specimen",
        fixtures.refusal,
        name,
        before=dict(refusal=name),
        on_capture=fixture_observer(tmp_path),
    )
    persist(tmp_path, "original-inputs", spec["raw"])
    # Capture/declaration refusals retain their complete original declaration.
    if name in ("wrong-stage", "native-chain-claim"):
        persist(tmp_path, "rejected-declaration", spec["declaration"])
        with pytest.raises(ValueError):
            recorded(
                tmp_path,
                "capture",
                fixtures.capture,
                spec,
                before=dict(raw=spec["raw"], declaration=spec["declaration"]),
            )
        return
    if name == "namespace-is-not-native":
        with pytest.raises(ValueError, match="pinned native owner class"):
            recorded(
                tmp_path,
                "native-capture",
                handoff.capture_native,
                fixtures.namespace_phase(spec),
                spec["declaration"],
                before=dict(raw=spec["raw"], declaration=spec["declaration"]),
            )
        return
    boundary = recorded(tmp_path, "capture", fixtures.capture, spec, before=dict(raw=spec["raw"]))
    if name == "changed-seal":
        boundary = replace(boundary, identity="0" * 64)
    persist(tmp_path, "rejected-boundary", boundary)
    if name == "missing-Egj":
        assert "Egj" in handoff.missing_stores(boundary)["sim"]
        assert boundary.owners["sim"]["Egj"] == {"present": False}
    if name == "persisted-CaATP-rate":
        assert boundary.owners["sim"]["rate_CaATP"]["present"] is True
    original = ions.digest(boundary)
    monkeypatch.setattr(source, "cold", forbid)
    monkeypatch.setattr(field, "initialize", forbid)
    monkeypatch.setattr(calcium, "initialize", forbid)
    monkeypatch.setattr(mechanical, "initialize", forbid)
    with pytest.raises(handoff.InitializationRejected) as caught:
        entered = recorded(
            tmp_path,
            "handoff",
            handoff.handoff,
            spec["binding"],
            boundary,
            before=dict(binding=spec["binding"], boundary=boundary),
        )
        if case == "mechanics":
            persist(tmp_path, "completed-field-before-mechanics-refusal", entered)
            recorded(
                tmp_path,
                "mechanics-handoff-call",
                handoff.handoff_mechanics,
                spec["outer"],
                boundary,
                entered,
                before=dict(binding=spec["outer"], boundary=boundary, previous_handoff=entered),
            )
    persist(
        tmp_path,
        "refusal",
        dict(
            type=type(caught.value).__name__,
            message=str(caught.value),
            stage=caught.value.stage,
            boundary=caught.value.boundary,
            partial=caught.value.partial,
        ),
    )
    assert original == ions.digest(boundary)
    if name == "missing-mechanical-PP":
        assert "PP" in handoff.missing_stores(boundary)["sim"]


def test_snapshot_owns_its_numeric_buffers(tmp_path):
    spec = recorded(
        tmp_path,
        "specimen",
        fixtures.specimen,
        "field",
        before=dict(case="field"),
        on_capture=fixture_observer(tmp_path),
    )
    boundary = recorded(tmp_path, "capture", fixtures.capture, spec, before=dict(raw=spec["raw"]))
    before = ions.digest(boundary)
    spec["owners"]["sim"].cc_cells[0, 0] += 1.0
    spec["network_cache"]["wire"]["molecule_fields"]["X"]["c_cells"][0] += 2.0
    assert before == ions.digest(boundary)
    assert boundary.owners["sim"]["cc_cells"]["value"].flags.writeable is False
    assert (
        boundary.network_cache["value"]["wire"]["molecule_fields"]["X"]["c_cells"].flags.writeable
        is False
    )
    persist(tmp_path, "owned-boundary", boundary)


def test_unreadable_optional_store_is_preserved(tmp_path):
    spec = recorded(
        tmp_path,
        "specimen",
        fixtures.specimen,
        "field",
        before=dict(case="field"),
        on_capture=fixture_observer(tmp_path),
    )
    spec["owners"]["sim"].PP = object()
    boundary = recorded(tmp_path, "capture", fixtures.capture, spec, before=dict(raw=spec["raw"]))
    entry = boundary.owners["sim"]["PP"]
    assert entry["present"] is True and entry["captured"] is False
    assert entry["type"] == "object"
    assert "PP" in handoff.missing_stores(boundary)["sim"]
    persist(tmp_path, "unreadable-boundary", boundary)
