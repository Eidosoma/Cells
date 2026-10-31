"""Synthetic post-setup owner publication; actual setup/native/model/RNG blocked."""

import copy
import json
import sys
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from cells.core.physiology_native_calendar import NativePhaseCalendar
from cells.processes import betse_ecm_transport as material
from cells.processes import betse_environment_field as environment
from cells.processes import betse_mechanics_join as mechanics
from cells.processes import betse_normal_current as current_owner
from cells.processes import betse_normal_ecm_molecule_checkpoint as checkpoint
from cells.processes import betse_normal_ecm_molecule_event_owner as bridge
from cells.processes import betse_normal_ecm_molecule_lifecycle as lifecycle
from cells.processes import betse_normal_ecm_molecule_run_lifecycle as run
from tests.unit.test_betse_normal_ecm_molecule_event_checkpoint import (
    no_actual_execution as no_actual_execution,
)
from tests.unit.test_betse_normal_ecm_molecule_event_checkpoint import plain_record


@pytest.fixture(autouse=True)
def forbid_original_source_finalizers(no_actual_execution):
    codes = {
        lifecycle.setup.source._finalize_events_tissue.__code__,
        lifecycle.setup.source._finalize_events_global.__code__,
    }
    original = sys.getprofile()

    def blocked(frame, event, arg):
        if event == "call" and frame.f_code in codes:
            no_actual_execution.append("original source finalizer")
            raise AssertionError("Actual source finalizer forbidden")

    sys.setprofile(blocked)
    try:
        yield
    finally:
        sys.setprofile(original)


def explicit_inputs():
    return bridge.Inputs(
        "INIT-binding",
        "geometry",
        "all",
        run.ions.freeze(dict(Na=10.0, K=4.0, Cl=8.0, Ca=2.0)),
        ("cell-B", "cell-A", "cell-B"),
        None,
        None,
        "Synthetic explicit source configuration; no biological admission",
    )


def graph(owner=None, supplied=None):
    """Manufacture records for metadata tests, never submit them to admission."""
    supplied = explicit_inputs() if supplied is None else supplied
    maps = dict(
        tissue_target_inds=dict(region0=[2, 0], all=[0, 1, 2, 3]),
        cell_target_inds=dict(region0=[0, 1], all=[0, 1]),
        env_target_inds=dict(region0=[1, 0], all=[0, 2, 1, 2]),
    )
    owner = (
        copy.deepcopy(owner)
        if owner is not None
        else dict(
            global_options=dict.fromkeys(run.composition.events.event42.GLOBAL_KEYS, 0),
            scheduled_options=dict.fromkeys(run.composition.events.event42.TISSUE_KEYS, 0),
            callbacks={},
            handler_fields={},
            **maps,
        )
    )
    for name in maps:
        owner[name] = maps[name]
    early_owner = {
        key: owner[key]
        for key in ("global_options", "scheduled_options", "handler_fields", "callbacks", *maps)
    }
    early = run.ions.freeze(
        dict(
            owner=early_owner,
            source_phase="SIM",
            legacy_run_sim=True,
            event_fire_calls=0,
            python_rng_after={"synthetic": "retained"},
            constant_callback_authority={
                suffix: lifecycle.setup.constant_callback_record(suffix)
                for suffix in owner["callbacks"]
            },
        )
    )
    kernel = current_owner.CurrentKernel(
        **{
            name: np.array([0, 1, 0, 1]) if name == "owner" else None
            for name in current_owner.CurrentKernel._fields
        }
    )
    current = plain_record(
        current_owner.CurrentBinding,
        cell_ids=("cell-A", "cell-B"),
        membrane_ids=("m-A", "m-B", "m-C", "m-D"),
        ion_ids=("Na", "K", "Cl", "Ca"),
        kernel=kernel,
    )
    members = dict(
        grid_points_m=np.zeros((3, 2)),
        cell_to_grid=np.array([0, 1]),
        membrane_to_grid=np.array([0, 2, 1, 2]),
    )
    grid = environment.Geometry(
        **{name: members.get(name) for name in environment.Geometry._fields}
    )
    gb = plain_record(
        environment.Binding, identity="geometry", current_binding=current, geometry=grid
    )
    mb = plain_record(material.Binding, geometry_binding=gb)
    mechanical = plain_record(
        mechanics.Binding,
        identity="mechanics",
        definition_json=json.dumps(
            dict(
                geometry=dict(
                    cell_ids=list(current.cell_ids),
                    environment_ids=["external-X", "external-Z", "external-Y"],
                    layout=dict(membrane_ids=list(current.membrane_ids)),
                    cell_to_environment=[0, 1],
                    membrane_to_environment=[0, 2, 1, 2],
                )
            )
        ),
    )
    initial = plain_record(
        lifecycle.init.Binding, identity="INIT-binding", material_binding=mb, mechanics=mechanical
    )
    completed = plain_record(
        lifecycle.CompleteInit,
        binding=initial,
        parent=plain_record(lifecycle.init.State, identity="INIT-parent"),
        identity="complete-INIT",
    )
    external = dict(
        geometry=dict(owner="retained geometry"),
        world=dict(owner="retained world"),
        current_definition=dict(
            geometry=dict(cells=list(current.cell_ids)), ions=dict(ids=list(current.ion_ids))
        ),
        cache_initial_state=dict(epoch="before setup"),
    )
    before = dict(
        field=dict(definition=dict(environment_geometry_definition=external)),
        setup=dict(
            global_options=owner["global_options"], scheduled_options=owner["scheduled_options"]
        ),
    )
    profiles = [
        dict(
            name=name,
            cell_indices=maps["cell_target_inds"][name],
            membrane_indices=indices,
            diffusion_m2_s={
                "Dm_" + role: (i + 1) * 1e-18 * (2 if name == "region0" else 1)
                for i, role in enumerate(bridge.ROLES)
            },
        )
        for name, indices in maps["tissue_target_inds"].items()
    ]
    declaration = plain_record(lifecycle.init.Declaration, identity="original-SIM-declaration")
    source = lifecycle.Binding(
        run.ions.freeze(dict(sim_phase=before, source_setup=dict(tissue_profiles=profiles))),
        "INIT-binding",
        declaration,
        "",
        supplied,
    )
    source = replace(source, identity=run.ions.digest(lifecycle.binding_record(source)))
    final = copy.deepcopy(before)
    final["field"]["definition"]["environment_geometry_definition"]["cache_initial_state"] = dict(
        epoch="after source setup"
    )
    final["time_profile"] = {"phase": "SIM", "labels": (0.0, 1.5, 3.0)}
    actual_profiles = SimpleNamespace(
        tissue_name_to_profile={
            row["name"]: SimpleNamespace(**row["diffusion_m2_s"]) for row in profiles
        }
    )
    pub = bridge.publish(source, completed, early, final, mechanical, actual_profiles)
    receipt = dict(
        source_phase="SIM",
        legacy_run_sim=True,
        source_init_identity=completed.identity,
        event_finalization=dict(source_fields=early, owner_publication=pub),
        source_setup=dict(event_finalized=early, event_owner_published=pub),
    )
    phase = plain_record(
        lifecycle.init.Binding,
        identity="SIM-phase",
        inputs_raw=run.ions.freeze(final),
        inputs=run.ions.freeze(final["field"]),
        setup_receipt=receipt,
        calendar=plain_record(NativePhaseCalendar, phase="SIM"),
        mechanics=mechanical,
        material_binding=mb,
    )
    entry = plain_record(
        lifecycle.SimPhase,
        binding_identity=source.identity,
        source_init=completed,
        phase_binding=phase,
    )
    return SimpleNamespace(
        source=source,
        completed=completed,
        early=early,
        final=final,
        mechanical=mechanical,
        profiles=actual_profiles,
        pub=pub,
        receipt=receipt,
        phase=phase,
        entry=entry,
    )


def attach_publication(binding):
    """Only manufactured metadata for the existing membrane software controls."""
    value = graph(binding.raw["event_owner"])
    original = binding.base
    original.setup_receipt["event_finalization"].update(
        source_fields=run.ions.data(value.early), owner_publication=value.pub
    )
    original.setup_receipt.update(
        source_phase="SIM",
        legacy_run_sim=True,
        source_init_identity=value.completed.identity,
        source_setup=value.receipt["source_setup"],
    )
    for name in ("inputs_raw", "inputs", "mechanics", "material_binding"):
        object.__setattr__(original, name, getattr(value.phase, name))
    object.__setattr__(value.entry, "phase_binding", original)
    object.__setattr__(binding, "source_entry", value.entry)
    object.__setattr__(binding, "source_binding", value.source)
    binding.raw["event_owner"] = run.ions.data(value.pub.owner)
    return value


def republish(value, **changes):
    changed = replace(value.pub, **changes)
    changed = replace(changed, identity=run.ions.digest(bridge.record(changed)))
    value.receipt["event_finalization"]["owner_publication"] = changed
    value.receipt["source_setup"]["event_owner_published"] = changed
    return changed


def test_later_publication_preserves_early_epoch_and_traces_all_owner_fields():
    value = graph()
    before = checkpoint.codec.fingerprint(value.early)
    assert bridge.resolve(value.source, value.entry) is value.pub
    assert set(value.early["owner"]) == {
        "global_options",
        "scheduled_options",
        "handler_fields",
        "callbacks",
        "tissue_target_inds",
        "cell_target_inds",
        "env_target_inds",
    }
    assert set(value.pub.owner) == set(value.pub.field_sources) == bridge.OWNER_KEYS
    assert checkpoint.codec.fingerprint(value.early) == before
    assert value.receipt["event_finalization"]["source_fields"] is value.early
    assert value.pub.event_finalized is value.early
    assert value.pub.owner["owners"]["environment_ids"] == (
        "external-X",
        "external-Z",
        "external-Y",
    )
    assert value.pub.owner["owners"]["membrane_environment_ids"] == (
        "external-X",
        "external-Y",
        "external-Z",
        "external-Y",
    )
    assert value.pub.owner["owners"]["boundary_cell_occurrences"] == ("cell-B", "cell-A", "cell-B")
    assert value.pub.owner["configured_environment"]["Na"] == 10.0


@pytest.mark.parametrize(
    "fault",
    [
        "untyped",
        "mutable-reservoir",
        "missing-ion",
        "array-reservoir",
        "nonfinite",
        "missing-default-role",
        "unknown-default",
        "foreign-boundary",
        "foreign-INIT",
        "foreign-geometry",
        "voltage",
        "cut",
        "missing-provenance",
    ],
)
def test_absent_or_foreign_authority_is_never_filled(fault):
    supplied = explicit_inputs()
    if fault == "untyped":
        supplied = run.ions.data(supplied)
    elif fault == "mutable-reservoir":
        supplied = replace(supplied, configured_environment=dict(supplied.configured_environment))
    elif fault == "missing-ion":
        supplied = replace(supplied, configured_environment=run.ions.freeze(dict(Na=10.0)))
    elif fault == "array-reservoir":
        supplied = replace(
            supplied,
            configured_environment=run.ions.freeze(dict(Na=np.array(10.0), K=4.0, Cl=8.0, Ca=2.0)),
        )
    elif fault == "nonfinite":
        supplied = replace(
            supplied,
            configured_environment=run.ions.freeze(dict(Na=float("nan"), K=4.0, Cl=8.0, Ca=2.0)),
        )
    elif fault == "missing-default-role":
        supplied = replace(supplied, default_tissue_profile="")
    elif fault == "unknown-default":
        supplied = replace(supplied, default_tissue_profile="not-in-actual-profiles")
    elif fault == "foreign-boundary":
        supplied = replace(supplied, boundary_cell_occurrences=("invented-cell",))
    elif fault == "foreign-INIT":
        supplied = replace(supplied, source_INIT_binding_identity="foreign")
    elif fault == "foreign-geometry":
        supplied = replace(supplied, source_geometry_binding_identity="foreign")
    elif fault == "voltage":
        supplied = replace(supplied, voltage={"pulse": 1.0})
    elif fault == "cut":
        supplied = replace(supplied, event_cut={"cut": 1})
    else:
        supplied = replace(supplied, provenance="")
    with pytest.raises(ValueError):
        graph(supplied=supplied)


def test_explicit_default_profile_is_selected_from_actual_return_without_first_profile_fallback():
    first = graph()
    selected = graph(supplied=replace(explicit_inputs(), default_tissue_profile="region0"))
    assert (
        selected.pub.owner["tissue_default"]["Dm_Na"]
        == 2 * first.pub.owner["tissue_default"]["Dm_Na"]
    )
    assert bridge.resolve(selected.source, selected.entry) is selected.pub


@pytest.mark.parametrize(
    "fault",
    [
        "missing-publication",
        "dictionary-publication",
        "epoch",
        "INIT-parent",
        "complete-INIT",
        "source-binding",
        "SIM-declaration",
        "phase-input",
        "early-epoch",
        "early-field",
        "configured-env",
        "default",
        "membrane-owner",
        "grid-owner",
        "profile-map",
        "publication-observation",
        "geometry-hash",
        "field-source",
    ],
)
def test_resealed_wrong_publication_still_refuses_exact_association(fault):
    value = graph()
    if fault == "missing-publication":
        value.receipt["event_finalization"].pop("owner_publication")
    elif fault == "dictionary-publication":
        value.receipt["event_finalization"]["owner_publication"] = run.ions.data(value.pub)
    elif fault == "epoch":
        republish(value, epoch="earlier event_finalized")
    elif fault == "INIT-parent":
        republish(value, source_INIT_parent_identity="foreign")
    elif fault == "complete-INIT":
        republish(value, source_complete_INIT_identity="foreign")
    elif fault == "source-binding":
        republish(value, source_binding_identity="foreign")
    elif fault == "SIM-declaration":
        republish(value, source_SIM_declaration_identity="foreign")
    elif fault == "phase-input":
        republish(value, phase_inputs_identity="foreign")
    elif fault == "early-epoch":
        early = run.ions.data(value.early)
        early["source_phase"] = "INIT"
        value.receipt["event_finalization"]["source_fields"] = early
    elif fault == "publication-observation":
        value.receipt["source_setup"].pop("event_owner_published")
    elif fault == "field-source":
        sources = run.ions.data(value.pub.field_sources)
        sources["owners"] = "invented or fixture authority"
        republish(value, field_sources=run.ions.freeze(sources))
    else:
        owner = run.ions.data(value.pub.owner)
        if fault == "early-field":
            owner["global_options"]["T_change"] = [0.0, 1.0, 0.7, 0.1]
        elif fault == "configured-env":
            owner["configured_environment"]["Na"] = 99.0
        elif fault == "default":
            owner["tissue_default"]["Dm_Na"] *= 2
        elif fault == "membrane-owner":
            owner["owners"]["membrane_cell_ids"].reverse()
        elif fault == "grid-owner":
            owner["owners"]["environment_ids"].reverse()
        elif fault == "profile-map":
            owner["tissue_target_inds"]["region0"].reverse()
        else:
            owner["geometry_declaration_sha256"] = "0" * 64
        republish(value, owner=run.ions.freeze(owner))
    with pytest.raises(ValueError):
        bridge.resolve(value.source, value.entry)


@pytest.mark.parametrize(
    "fault",
    [
        "missing-grid-ID",
        "missing-default-field",
        "wrong-profile-order",
        "wrong-profile-return",
        "missing-env-map",
        "changed-geometry",
        "changed-ions",
        "changed-config",
        "reordered-mapping",
    ],
)
def test_publication_rejects_missing_real_source_data_without_generation(fault):
    value = graph()
    final = copy.deepcopy(value.final)
    early = run.ions.data(value.early)
    if fault == "missing-grid-ID":
        definition = run.ions.data(value.mechanical.definition)
        definition["geometry"].pop("environment_ids")
        object.__setattr__(value.mechanical, "definition_json", json.dumps(definition))
    elif fault == "missing-default-field":
        del value.profiles.tissue_name_to_profile["all"].Dm_Ca
    elif fault == "wrong-profile-order":
        value.profiles.tissue_name_to_profile = dict(
            reversed(list(value.profiles.tissue_name_to_profile.items()))
        )
    elif fault == "wrong-profile-return":
        value.profiles.tissue_name_to_profile["all"].Dm_Na *= 2
    elif fault == "missing-env-map":
        early["owner"]["env_target_inds"].pop("region0")
    elif fault == "changed-geometry":
        final["field"]["definition"]["environment_geometry_definition"]["geometry"]["owner"] = (
            "foreign"
        )
    elif fault == "changed-ions":
        final["field"]["definition"]["environment_geometry_definition"]["current_definition"][
            "ions"
        ]["ids"].reverse()
    elif fault == "changed-config":
        early["owner"]["global_options"]["K_env"] = [0.0, 1.0, 0.5, 0.1]
    else:
        definition = run.ions.data(value.mechanical.definition)
        definition["geometry"]["membrane_to_environment"].reverse()
        object.__setattr__(value.mechanical, "definition_json", json.dumps(definition))
    with pytest.raises((ValueError, KeyError, AttributeError)):
        bridge.publish(
            value.source, value.completed, early, final, value.mechanical, value.profiles
        )


def test_closed_codec_transports_both_epochs_typed_inputs_and_source_association(tmp_path):
    value = graph()
    graph_data = dict(
        publication=value.pub,
        source=value.source,
        early=value.early,
        inputs=value.source.event_owner_inputs,
        finalization=value.receipt["event_finalization"],
        source_setup=value.receipt["source_setup"],
    )
    encoder = checkpoint.codec.Encoder()
    tree = encoder.capture(graph_data)
    encoder.write(tmp_path, tree)
    loaded = checkpoint.codec.decode(tree, (tmp_path / "arrays.npz").read_bytes())
    assert (
        type(loaded["publication"]) is bridge.Publication
        and type(loaded["inputs"]) is bridge.Inputs
    )
    assert loaded["publication"].inputs is loaded["source"].event_owner_inputs is loaded["inputs"]
    assert loaded["publication"].event_finalized is loaded["early"]
    assert (
        loaded["finalization"]["owner_publication"]
        is loaded["source_setup"]["event_owner_published"]
        is loaded["publication"]
    )
    assert (
        loaded["finalization"]["source_fields"]
        is loaded["source_setup"]["event_finalized"]
        is loaded["early"]
    )
    assert checkpoint.codec.fingerprint(graph_data) == checkpoint.codec.fingerprint(loaded)
    assert not isinstance(loaded["source"], run.RunState)


def test_optional_bridge_keeps_legacy_binding_identity_and_global_route():
    value = graph()
    legacy = replace(value.source, event_owner_inputs=None)
    assert lifecycle.binding_record(legacy) == (
        lifecycle.LAW_ID,
        legacy.inputs,
        legacy.expected_init_identity,
        legacy.declaration.identity,
    )
    from tests.unit.test_betse_normal_ecm_molecule_event_checkpoint import synthetic_owner

    binding, _ = synthetic_owner()
    binding.base.setup_receipt["event_finalization"].pop("source_fields", None)
    run.composition.event_scope(binding)
    binding.raw["event_owner"]["global_options"]["T_change"] = 0
    run.composition.event_scope(binding)


def test_missing_typed_input_is_retained_before_any_actual_preparation(tmp_path, monkeypatch):
    from validation.betse import betse_normal_ecm_molecule_event_checkpoint as validation

    for name in validation.RELEASES:
        monkeypatch.setenv(name, "1")
    previous = sys.getprofile()
    sys.setprofile(None)
    try:
        with pytest.raises(ValueError, match="explicit typed SIM event-owner inputs"):
            validation.actual_continuity(tmp_path / "refused", scenario="membrane_combined", cut=1)
    finally:
        sys.setprofile(previous)
    assert not (tmp_path / "refused/result.json").exists()
    assert (tmp_path / "refused/failure/manifest.json").is_file()
    attempts = json.loads((tmp_path / "refused/attempts.json").read_bytes())["attempts"]
    assert (
        len(attempts) == 1
        and attempts[0]["operation"] == "required-typed-event-owner-inputs"
        and attempts[0]["status"] == "refused"
    )


def test_required_input_archive_failure_stays_primary_before_actual_setup(tmp_path, monkeypatch):
    from validation.betse import betse_normal_ecm_molecule_checkpoint as preparation
    from validation.betse import betse_normal_ecm_molecule_event_checkpoint as validation

    primary = OSError("Synthetic required-input archive refusal")
    archive = preparation.archives.write_archive

    def refused(path, *args, **kwargs):
        if path.name == "required-typed-event-owner-inputs":
            raise primary
        return archive(path, *args, **kwargs)

    monkeypatch.setattr(preparation.archives, "write_archive", refused)
    for name in validation.RELEASES:
        monkeypatch.setenv(name, "1")
    previous = sys.getprofile()
    sys.setprofile(None)
    try:
        with pytest.raises(OSError) as caught:
            validation.actual_continuity(
                tmp_path / "refused",
                scenario="membrane_combined",
                cut=1,
                event_owner_inputs=explicit_inputs(),
            )
    finally:
        sys.setprofile(previous)
    assert caught.value is primary and not (tmp_path / "refused/result.json").exists()
    assert (tmp_path / "refused/failure/manifest.json").is_file()
    attempts = json.loads((tmp_path / "refused/attempts.json").read_bytes())["attempts"]
    assert len(attempts) == 1 and attempts[0]["status"] == "refused"
    assert attempts[0]["operation_status"] == "returned"


def test_typed_authority_is_never_silently_ignored_by_unchanged_global_route(tmp_path, monkeypatch):
    from validation.betse import betse_normal_ecm_molecule_event_checkpoint as validation

    for name in validation.RELEASES:
        monkeypatch.setenv(name, "1")
    with pytest.raises(ValueError, match="require the targeted preparation route"):
        validation.actual_continuity(
            tmp_path / "refused",
            scenario="temperature",
            cut=1,
            event_owner_inputs=explicit_inputs(),
        )
    assert not (tmp_path / "refused").exists()


def test_supplied_provenance_is_explicitly_conditional_and_bound():
    value = graph(supplied=replace(explicit_inputs(), provenance="Supplied caller note"))
    assert bridge.resolve(value.source, value.entry) is value.pub
    assert value.pub.owner["provenance"] == "Supplied caller note"
    for field in (
        "provenance",
        "owners",
        "tissue_default",
        "configured_environment",
        "voltage",
        "event_cut",
    ):
        assert "conditional/supplied" in value.pub.field_sources[field]
        assert "qualification unestablished" in value.pub.field_sources[field]
    sources = run.ions.data(value.pub.field_sources)
    sources["configured_environment"] = "Native derivation established by typed record"
    republish(value, field_sources=run.ions.freeze(sources))
    with pytest.raises(ValueError, match="field-source correspondence"):
        bridge.resolve(value.source, value.entry)


def test_decode_owner_records_does_not_invoke_source_or_validation(tmp_path, monkeypatch):
    value = graph()
    data = dict(publication=value.pub, inputs=value.source.event_owner_inputs, early=value.early)
    called = []

    def forbidden(label):
        def refused(*args, **kwargs):
            called.append(label)
            raise AssertionError("Decoding must not replay " + label)

        return refused

    for name in ("publish", "resolve", "check_inputs", "_axes"):
        monkeypatch.setattr(bridge, name, forbidden("owner." + name))
    monkeypatch.setattr(lifecycle.setup, "prepare", forbidden("setup"))
    monkeypatch.setattr(run.composition.events.events, "prepared_callback", forbidden("callback"))
    encoder = checkpoint.codec.Encoder()
    tree = encoder.capture(data)
    encoder.write(tmp_path, tree)
    loaded = checkpoint.codec.decode(tree, (tmp_path / "arrays.npz").read_bytes())
    assert called == []
    for cls in (bridge.Inputs, bridge.Publication):
        assert cls.__dataclass_params__.frozen and not hasattr(cls, "__post_init__")
    assert type(loaded["publication"]) is bridge.Publication
    assert loaded["publication"].inputs is loaded["inputs"]
    assert loaded["publication"].event_finalized is loaded["early"]
    assert checkpoint.codec.fingerprint(loaded) == checkpoint.codec.fingerprint(data)


def reseal_outer_metadata(value):
    """Reseal only manufactured metadata; never call a public numerical verifier."""
    object.__setattr__(value.phase, "declaration", value.source.declaration)
    object.__setattr__(value.phase, "voltage_binding", SimpleNamespace(identity="unowned voltage"))
    object.__setattr__(
        value.phase, "identity", run.ions.digest(lifecycle.init.binding_record(value.phase))
    )
    object.__setattr__(value.entry, "receipt", run.ions.freeze(value.receipt))
    object.__setattr__(
        value.entry, "identity", run.ions.digest(lifecycle.phase_record(value.entry))
    )


@pytest.mark.parametrize(
    "fault",
    [
        "global-options",
        "scheduled-options",
        "source-phase",
        "legacy-false",
        "legacy-int",
        "fire-nonzero",
        "fire-bool",
        "fire-float",
    ],
)
def test_resolve_rejects_synchronized_resealed_early_drift_against_original_source(fault, tmp_path):
    value = graph()
    source_identity = value.source.identity
    source_fingerprint = checkpoint.codec.fingerprint(value.source)
    early = run.ions.data(value.early)
    if fault == "global-options":
        early["owner"]["global_options"]["T_change"] = [0.5, 2.0, 0.7, 0.01]
    elif fault == "scheduled-options":
        early["owner"]["scheduled_options"]["Na_mem"] = [0.5, 2.0, 0.7, 0.15, ["all"], "None"]
    elif fault == "source-phase":
        early["source_phase"] = "INIT"
    elif fault == "legacy-false":
        early["legacy_run_sim"] = False
    elif fault == "legacy-int":
        early["legacy_run_sim"] = 1
    else:
        early["event_fire_calls"] = {
            "fire-nonzero": 1,
            "fire-bool": False,
            "fire-float": 0.0,
        }[fault]
    early = run.ions.freeze(early)
    owner = run.ions.data(value.pub.owner)
    owner.update(run.ions.data(early["owner"]))
    value.receipt["event_finalization"]["source_fields"] = early
    value.receipt["source_setup"]["event_finalized"] = early
    changed = republish(
        value,
        event_finalized=early,
        event_finalized_identity=run.ions.digest(early),
        owner=run.ions.freeze(owner),
    )
    reseal_outer_metadata(value)
    assert value.source.identity == source_identity
    assert checkpoint.codec.fingerprint(value.source) == source_fingerprint
    assert changed.identity == run.ions.digest(bridge.record(changed))
    assert bridge.same(changed.event_finalized, early)
    assert value.receipt["source_setup"]["event_owner_published"] is changed
    assert value.entry.identity == run.ions.digest(lifecycle.phase_record(value.entry))
    match = (
        "source configuration"
        if fault in ("global-options", "scheduled-options")
        else "SIM finalization epoch"
    )
    with pytest.raises(ValueError, match=match):
        bridge.resolve(value.source, value.entry)
    (tmp_path / "resolve-repair-control.json").write_text(
        json.dumps(
            dict(
                repair="R1",
                fault=fault,
                synchronized_early_and_publication=True,
                publication_and_outer_records_resealed=True,
                original_source_binding_unchanged=True,
                synthetic_only=True,
                public_numerical_verifier_called=False,
                scientific_acceptance=False,
            )
        )
    )


@pytest.mark.parametrize(
    "fault",
    [
        "source-binding",
        "owner-content",
        "epoch",
        "field-source",
        "inputs-container",
        "owner-container",
        "early-container",
    ],
)
def test_resolve_checks_secondary_record_contents_with_retained_identity(fault, tmp_path):
    value = graph()
    before = checkpoint.codec.fingerprint(value.pub)
    if fault == "source-binding":
        secondary = replace(value.pub, source_binding_identity="foreign secondary source")
    elif fault == "owner-content":
        owner = run.ions.data(value.pub.owner)
        owner["configured_environment"]["Na"] = 99.0
        secondary = replace(value.pub, owner=run.ions.freeze(owner))
    elif fault == "epoch":
        secondary = replace(value.pub, epoch="wrong secondary epoch")
    elif fault == "field-source":
        sources = run.ions.data(value.pub.field_sources)
        sources["owners"] = "foreign secondary source"
        secondary = replace(value.pub, field_sources=run.ions.freeze(sources))
    elif fault == "inputs-container":
        secondary = replace(
            value.pub,
            inputs=replace(
                value.pub.inputs,
                configured_environment=dict(value.pub.inputs.configured_environment),
            ),
        )
    elif fault == "owner-container":
        secondary = replace(value.pub, owner=dict(value.pub.owner))
    else:
        secondary = replace(value.pub, event_finalized=dict(value.pub.event_finalized))
    assert type(secondary) is bridge.Publication and secondary.identity == value.pub.identity
    value.receipt["source_setup"]["event_owner_published"] = secondary
    reseal_outer_metadata(value)
    assert checkpoint.codec.fingerprint(value.pub) == before
    assert value.entry.identity == run.ions.digest(lifecycle.phase_record(value.entry))
    with pytest.raises(ValueError, match="later source publication observation"):
        bridge.resolve(value.source, value.entry)
    (tmp_path / "resolve-repair-control.json").write_text(
        json.dumps(
            dict(
                repair="R2",
                fault=fault,
                secondary_identity_retained=True,
                outer_records_resealed=True,
                authoritative_publication_unchanged=True,
                synthetic_only=True,
                public_numerical_verifier_called=False,
                scientific_acceptance=False,
            )
        )
    )


def test_resolve_accepts_equal_typed_secondary_without_replacing_epochs_or_aliases():
    value = graph()
    early = value.early
    authoritative = value.pub
    assert value.receipt["source_setup"]["event_owner_published"] is authoritative
    secondary = replace(authoritative)
    assert secondary is not authoritative
    value.receipt["source_setup"]["event_owner_published"] = secondary
    assert bridge.resolve(value.source, value.entry) is authoritative
    assert value.receipt["event_finalization"]["source_fields"] is early
    assert value.receipt["source_setup"]["event_finalized"] is early
    assert secondary.event_finalized is authoritative.event_finalized is early


def test_numpy_counter_remains_unsealable_under_existing_source_digest():
    value = graph()
    before = checkpoint.codec.fingerprint(value.early)
    unsealed = run.ions.data(value.early)
    unsealed["event_fire_calls"] = np.int64(0)
    with pytest.raises(TypeError, match="int64.*JSON serializable"):
        run.ions.digest(unsealed)
    assert checkpoint.codec.fingerprint(value.early) == before
