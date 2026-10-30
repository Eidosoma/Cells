"""Owned random setup into full initial definitions, source replay and durable IO."""

import json
import os
import random
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells import random_tissue_profiles as public
from cells.core import physiology_target_selection as selection
from cells.core import random_tissue_profile_preparation as bridge
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, digest, parse_spec
from cells.models.registry import get_model
from cells.processes import betse_tissue_profiles as profiles
from tests.unit.test_physiology_target_selection import streams
from validation.topology import random_tissue_profile_preparation_reference as reference
from validation.topology import tissue_profile_composition_fixtures as composed_fixtures
from validation.topology import tissue_profile_composition_reference as owners
from validation.topology import tissue_profile_preparation_fixtures as direct_fixtures

FAMILIES = ("passive", "ionic", "calcium", "fuel")


def json_value(value):
    return bridge.direct._json(value)


def evidence(name, value):
    if root := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        folder = Path(root) / "random-tissue-preparation"
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / (name + ".json")).open("x") as stream:
            json.dump(json_value(value), stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")


def request(family="passive", *, permuted=False):
    raw = (
        direct_fixtures.inputs("passive" if family == "passive" else "active", permuted=permuted)
        if family in ("passive", "ionic")
        else composed_fixtures.inputs(family, permuted=permuted)
    )
    raw["definition"] = parse_spec(raw["definition"]).to_dict()
    cells = raw["geometry"]["layout"]["cell_ids"]
    raw["profiles"] = [
        direct_fixtures.profile("Before", "all", None, 2e-18),
        direct_fixtures.profile("Zero", "percent", 0.0, 3e-18),
        direct_fixtures.profile("Full", "percent", 100.0, 4e-18),
        direct_fixtures.profile("Between", "all", None, 5e-18),
        direct_fixtures.profile("Region", "percent", 67.0, 6e-18, insular=True),
        direct_fixtures.profile("Duplicate", "ids", [cells[0], cells[1], cells[0]], 7e-18),
    ]
    layout = profiles.Layout(**raw["geometry"]["layout"])
    stream = streams(layout, 29 if permuted else 17)
    return json_value(
        raw
        | dict(
            schema_version=1,
            kind=bridge.REQUEST_KIND,
            selection_stream=selection.stream_record(stream),
            stream_id=stream.stream_id,
            world_id=stream.world_id,
            global_gj_percent=37.9,
        )
    )


def compare_definition(actual, expected):
    canonical = parse_spec(expected).to_dict()
    check = deepcopy(actual)
    a, b = (row["model"].get("ionic", row["model"]) for row in (check, canonical))
    for key in ("membranes", "junctions"):
        for left, right in zip(a[key], b[key], strict=True):
            assert left["id"] == right["id"]
            assert set(left["permeability_m_per_s"]) == set(right["permeability_m_per_s"])
            for ion, value in right["permeability_m_per_s"].items():
                np.testing.assert_allclose(
                    left["permeability_m_per_s"][ion], value, rtol=5e-14, atol=1e-25
                )
            left["permeability_m_per_s"] = right["permeability_m_per_s"]
    assert check == canonical


def compare_preparation(raw, result):
    expected = reference.prepare(raw)
    compare_definition(result.definition, expected["physical"]["definition"])
    actual, captured = result.provenance["selection"], expected["native"]
    assert actual["binding"]["targets"] == expected["selection"]["targets"]
    assert actual["binding"]["final_cell_order"] == captured["final_cell_order"]
    assert actual["global_gj_targets"] == captured["global_gj_targets"]
    successor = selection.stream_record(result.stream)
    assert successor["next_call"] == captured["next_call"]
    for engine in ("numpy", "python"):
        assert selection._json(successor[engine]["state"]) == selection._json(
            captured[engine + "_state"]
        )
    assert owners.owners(raw["definition"]) == owners.owners(result.definition)
    assert result.definition["experiment"] == raw["definition"]["experiment"]
    assert result.definition["execution"] == raw["definition"]["execution"]
    before = parse_spec(raw["definition"])
    after = parse_spec(result.definition)
    source_state, _ = get_model(before.model).initial_values(before)
    actual_state, _ = get_model(after.model).initial_values(after)
    for left, right in zip(source_state, actual_state, strict=True):
        np.testing.assert_array_equal(left, right, strict=True)
    assert selection._json(bridge.replay(result.provenance).provenance) == selection._json(
        result.provenance
    )
    return expected


def physical_rates(result, independent):
    target = reference.rates(independent["physical"]["definition"])
    spec = parse_spec(result.definition)
    implementation = get_model(spec.model)
    state, layout = implementation.initial_values(spec)
    table = control_values(spec, [0.0])
    controls = type(table)(*(value[0] for value in table))
    oracle = reference.ORACLES[result.definition["model"]["id"]]
    context = oracle.bind(independent["physical"]["definition"])
    np.testing.assert_array_equal(oracle.flatten(context, state._asdict()), target["initial"])
    rate = implementation.rhs(state, controls, layout, layout.active, xp=np)
    field = implementation.field_values(state, controls, layout, xp=np)
    packed = oracle.flatten(context, rate._asdict())
    budget = target["rate_atol"] + 3e-10 * np.abs(target["rate"])
    ratio = float(np.max(np.abs(packed - target["rate"]) / budget, initial=0))
    n = layout.active.size
    potential = np.r_[
        field.potential_V[:n][layout.active], field.potential_V[n:][layout.outside_active]
    ]
    potential_budget = 3e-13 + 3e-10 * np.abs(target["potential_V"])
    potential_ratio = float(np.max(np.abs(potential - target["potential_V"]) / potential_budget))
    assert ratio <= 1 and potential_ratio <= 1
    assert bool(field.converged)
    assert bool(implementation.domain_valid(state, layout, layout.active, xp=np))
    assert abs(float(field.energy_balance_pJ_s)) <= 1e-10
    return dict(
        independent=target,
        actual_rate=packed,
        actual_potential_V=potential,
        max_rate_error_over_budget=ratio,
        max_potential_error_over_budget=potential_ratio,
        full_state_fields=len(state),
        full_layout_fields=len(layout),
        stage_energy_residual_pJ_s=float(field.energy_balance_pJ_s),
        domain_valid=True,
    )


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("permuted", (False, True))
def test_three_preparations_native_tapes_full_owners_and_initial_physical_rates(family, permuted):
    raw, records = request(family, permuted=permuted), []
    original_definition = deepcopy(raw["definition"])
    original_geometry = deepcopy(raw["geometry"])
    for _ in range(3):
        before = deepcopy(raw)
        result = bridge.prepare(raw)
        expected = compare_preparation(raw, result)
        records.append(
            dict(
                request=before,
                prepared=result.definition,
                provenance=result.provenance,
                independent=expected,
                physics=physical_rates(result, expected),
                exact_recipe_replay=True,
            )
        )
        assert raw == before
        raw["selection_stream"] = selection.stream_record(result.stream)
        assert raw["definition"] == original_definition and raw["geometry"] == original_geometry
    evidence(
        f"sequence-{family}-{permuted}",
        dict(calls=records, additional_biological_cases=0, coupled_trajectory=False),
    )


@pytest.mark.parametrize("variant", ("disabled", "no-percent", "ions-off", "no-global", "no-ecm"))
def test_carried_order_and_independent_enable_guards(variant):
    raw = request()
    first = bridge.prepare(raw)
    raw["selection_stream"] = selection.stream_record(first.stream)
    assert raw["selection_stream"]["cell_order"] != raw["geometry"]["layout"]["cell_ids"]
    if variant == "disabled":
        raw["enabled"] = False
    elif variant == "no-percent":
        raw["profiles"] = [row for row in raw["profiles"] if row["selector"]["kind"] != "percent"]
    elif variant == "ions-off":
        raw["ion_enabled"] = [False] * 6
    elif variant == "no-global":
        raw["global_gj_percent"] = None
    elif variant == "no-ecm":
        raw["is_ecm"] = False
    if variant != "no-ecm":
        raw["is_ecm"] = True
    result = bridge.prepare(raw)
    expected = compare_preparation(raw, result)
    after = selection.stream_record(result.stream)
    if variant in ("disabled", "no-percent"):
        assert after["numpy"] == raw["selection_stream"]["numpy"]
        assert after["cell_order"] == raw["selection_stream"]["cell_order"]
        assert after["python"] != raw["selection_stream"]["python"]
    if variant == "disabled":
        assert result.definition == raw["definition"]
    if variant == "no-global":
        assert after["python"] == raw["selection_stream"]["python"]
    evidence(
        "guard-" + variant, dict(request=raw, provenance=result.provenance, independent=expected)
    )


def test_global_gj_setup_consumes_tape_without_firing_blocker_or_mutating_global_rngs():
    raw = request()
    numpy_before, python_before = json_value(np.random.get_state()), json_value(random.getstate())
    enabled = bridge.prepare(raw)
    raw["global_gj_percent"] = None
    disabled = bridge.prepare(raw)
    assert enabled.definition == disabled.definition
    assert enabled.stream.numpy == disabled.stream.numpy
    assert enabled.stream.python != disabled.stream.python
    assert numpy_before == json_value(np.random.get_state())
    assert python_before == json_value(random.getstate())


def test_physical_refusal_keeps_source_and_complete_successful_selection():
    raw = request()
    raw["ion_enabled"][4] = True  # Native profile M has no physical ion owner here.
    before = deepcopy(raw)
    captured = reference.native.evaluate(reference.native_parameters(raw), raw["selection_stream"])
    with pytest.raises(bridge.PreparationRejected) as failed:
        bridge.prepare(raw)
    error = failed.value
    assert error.stage == "physical_preparation" and error.selection is not None
    trial = selection.stream_record(error.trial_stream)
    assert trial["next_call"] == captured["next_call"]
    for engine in ("numpy", "python"):
        assert trial[engine]["state"] == captured[engine + "_state"]
    assert json_value(selection.stream_record(error.source_stream)) == json_value(
        raw["selection_stream"]
    )
    assert raw == before
    evidence(
        "physical-refusal",
        dict(
            request=raw,
            native=captured,
            source=selection.stream_record(error.source_stream),
            trial=trial,
            stage=error.stage,
            error=str(error),
            parent_unchanged=True,
        ),
    )


def test_late_selection_counter_refusal_retains_partial_trial_and_parent():
    raw = request()
    layout = profiles.Layout(**raw["geometry"]["layout"])
    source = streams(layout, 17, next_call=selection.MAX_CALL - 1)
    raw["selection_stream"] = selection.stream_record(source)
    before = deepcopy(raw)
    with pytest.raises(bridge.PreparationRejected) as failed:
        bridge.prepare(raw)
    error = failed.value
    assert error.stage == "owned_selection" and error.selection is None
    assert error.trial_stream.next_call == selection.MAX_CALL
    assert json_value(selection.stream_record(error.source_stream)) == json_value(
        raw["selection_stream"]
    )
    assert raw == before
    evidence(
        "counter-refusal",
        dict(
            request=raw,
            trial=selection.stream_record(error.trial_stream),
            source=selection.stream_record(error.source_stream),
            stage=error.stage,
            error=str(error),
            parent_unchanged=True,
        ),
    )


@pytest.mark.parametrize("fault", ("extra", "model", "world", "layout", "resolved", "schema"))
def test_invalid_request_preserves_inputs_and_refuses_before_publication(fault):
    raw = request()
    if fault == "extra":
        raw["unexpected"] = 1
    elif fault == "model":
        raw["definition"]["model"]["id"] = "resolved_tissue@2"
    elif fault == "world":
        raw["world_id"] += 1
    elif fault == "layout":
        raw["geometry"]["layout"]["membrane_cell_ids"][0] = "foreign"
    elif fault == "resolved":
        raw["profiles"][1]["selector"]["permutation_cell_ids"] = raw["geometry"]["layout"][
            "cell_ids"
        ]
    elif fault == "schema":
        raw["schema_version"] = True
    before = deepcopy(raw)
    with pytest.raises(ConfigError):
        bridge.prepare(raw)
    assert raw == before


@pytest.mark.parametrize("fault", ("selection", "definition", "successor", "scope"))
def test_resealed_inconsistent_provenance_refuses(fault):
    result = bridge.prepare(request())
    data = deepcopy(result.provenance)
    if fault == "selection":
        data["selection"]["global_gj_targets"] = []
    elif fault == "definition":
        data["prepared_definition_sha256"] = "0" * 64
    elif fault == "successor":
        data["selection"]["successor"]["next_call"] += 1
    elif fault == "scope":
        data["scope"] = "evolved checkpoint"
    data["identity"] = digest({k: v for k, v in data.items() if k != "identity"})
    with pytest.raises(ConfigError):
        bridge.replay(data)


@pytest.mark.parametrize("fault", ("definition", "stream", "manifest", "failed", "duplicate"))
def test_bundle_changed_payload_or_manifest_refuses(tmp_path, fault):
    result = bridge.prepare(request())
    root = public.write_preparation(tmp_path / "prepared", result)
    assert public.read_preparation(root).provenance == result.provenance
    if fault == "failed":
        (root / "failure.json").write_text("{}")
    elif fault == "duplicate":
        (root / "manifest.json").write_text('{"kind":"a","kind":"b"}')
    else:
        path = root / (fault + ".json")
        data = json.loads(path.read_text())
        if fault == "definition":
            data["model"]["cells"][0]["volume_pL"] *= 1.1
        elif fault == "stream":
            data["next_call"] += 1
        else:
            data["complete"] = False
        path.write_text(json.dumps(data))
    with pytest.raises(ConfigError):
        public.read_preparation(root)


def test_writer_refuses_forged_result_foreign_sources_and_existing_destination(tmp_path):
    result = bridge.prepare(request())
    root = public.write_preparation(tmp_path / "parent", result)
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    with pytest.raises(FileExistsError):
        public.write_preparation(root, result)
    with pytest.raises(ConfigError):
        public.write_preparation(tmp_path / "wrong-source", result, expected_source_hashes={})
    bad = deepcopy(result.definition)
    bad["model"]["cells"][0]["volume_pL"] *= 1.1
    with pytest.raises(ConfigError):
        public.write_preparation(tmp_path / "forged", replace(result, definition=bad))
    assert not (tmp_path / "forged").exists() and not (tmp_path / "wrong-source").exists()
    assert before == {p.name: p.read_bytes() for p in root.iterdir()}


def test_partial_publication_is_durable_failed_and_unreadable(tmp_path, monkeypatch):
    result = bridge.prepare(request())
    original = public.durable._write_json

    def fail(path, value):
        if path.name == "stream.json":
            raise OSError("injected disk write refusal")
        return original(path, value)

    monkeypatch.setattr(public.durable, "_write_json", fail)
    root = tmp_path / "failed"
    with pytest.raises(OSError):
        public.write_preparation(root, result)
    assert (root / "failure.json").exists() and not (root / "manifest.json").exists()
    assert (root / "definition.json").exists() and (root / "provenance.json").exists()
    with pytest.raises(ConfigError):
        public.read_preparation(root)
    evidence("publication-refusal", dict(injected=True, failed_bundle=str(root), complete=False))


def test_source_change_during_publication_leaves_failure_without_manifest(tmp_path, monkeypatch):
    result = bridge.prepare(request())
    original, calls = public.source_hashes, []

    def changing():
        calls.append(1)
        return original() if len(calls) <= 2 else {"changed": "source"}

    monkeypatch.setattr(public, "source_hashes", changing)
    root = tmp_path / "changed"
    with pytest.raises(ConfigError):
        public.write_preparation(root, result)
    assert (root / "failure.json").exists() and not (root / "manifest.json").exists()


def test_public_prepare_replay_validate_in_fresh_processes(tmp_path):
    raw = request("fuel", permuted=True)
    path = tmp_path / "request.json"
    path.write_text(json.dumps(raw))
    a, b = tmp_path / "prepared", tmp_path / "replayed"
    commands = [
        ["prepare", str(path), "--output", str(a)],
        ["replay", str(a / "provenance.json"), "--output", str(b)],
        ["validate", str(b)],
    ]
    records = []
    for arguments in commands:
        process = subprocess.run(
            [sys.executable, "-B", "-m", "cells.random_tissue_profiles", *arguments],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        records.append(
            dict(
                command=arguments,
                returncode=process.returncode,
                stdout=process.stdout,
                stderr=process.stderr,
            )
        )
        assert process.returncode == 0, process.stderr
        assert json.loads(process.stdout)["model_id"] == raw["definition"]["model"]["id"]
    assert public.read_preparation(a).provenance == public.read_preparation(b).provenance
    for name in (*public.FILES, "manifest.json"):
        assert (a / name).read_bytes() == (b / name).read_bytes()
    evidence(
        "public-cli",
        dict(
            request=raw,
            processes=records,
            bundles=[str(a), str(b)],
            exact_fresh_process_recipe_replay=True,
        ),
    )
