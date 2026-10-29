"""Public phase routing retains complete calcium/fuel states and original histories."""

import json
from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from cells.core import active_membrane_profile_phase_handoff as active_handoff
from cells.core import membrane_profile_phase_handoff as passive_handoff
from cells.core import owned_calcium_profile_phase_handoff as handoff
from cells.core.batch import BatchSpec, WorldSpec, parse_batch
from cells.core.errors import NumericalError
from cells.core.excision import excise
from cells.core.runner import branch_checkpoint, run, validate_checkpoint
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, digest, parse_spec
from cells.core.state import initialise
from cells.ensemble.ionic import parse_spec as parse_ensemble
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models.registry import get_model
from cells.tissue_phase import prepare_request, read_preparation, replay
from tests.integration.test_cli import cli
from tests.owned_calcium_phase_fixtures import OWNERS, prepared, request, source_checkpoint
from tests.unit.test_owned_calcium_profile_interventions_dispatch import exact
from tests.unit.test_surface_catalog import evidence


@pytest.mark.parametrize("family", OWNERS)
def test_public_owned_epoch_keeps_every_parent_array_and_original_owner(family, tmp_path):
    schema, model, parent_fields = OWNERS[family]
    value = prepared(family)
    spec = parse_spec(value.definition)
    source, before = source_checkpoint(family)
    parent = handoff.owner(source).runtime
    assert get_model(spec.model) is model
    assert type(spec.model) is not type(source.model)
    assert spec == schema.parse(value.definition) == parse_spec(spec.to_dict())
    assert digest(spec.to_dict()) == digest(value.definition)
    point = initialise(spec)
    assert len(point.state) == parent_fields + 1
    assert type(point.state) is model.STATE_TYPE and type(point.layout) is model.LAYOUT_TYPE
    assert type(point.state) is not type(before.state)
    exact(parent.parent_state(point.state), parent.parent_state(before.state))
    exact(parent.parent_layout(point.layout), parent.parent_layout(before.layout))
    np.testing.assert_array_equal(point.state.phase_clock_s, [0.0])
    assert point.time == point.step_index == 0 and before.time > 0
    assert np.any(point.state.channel_transferred != 0)
    assert np.any(point.state.pump_cycles != 0)
    assert np.any(point.state.chemical_amount_increment != 0)
    if family == "fuel5":
        assert np.any(point.state.energy_amount_increment_fmol != 0)
    controls = control_values(spec, [0.0, spec.execution.dt])
    exact(controls, control_values(schema.scheduled_spec(spec), [0.0, spec.execution.dt]))
    assert any(
        not np.array_equal(a, b)
        for a, b in zip(controls, control_values(source, [0.0, spec.execution.dt]), strict=True)
    )
    folder = write_snapshot(tmp_path / "epoch", spec, point)
    saved = load_snapshot(folder)
    assert saved.spec == spec
    exact(saved.checkpoint.state, point.state)
    exact(saved.checkpoint.layout, point.layout)
    batch = BatchSpec((WorldSpec(3, spec), WorldSpec(79, spec)), 2, 10000, 2**32)
    assert parse_batch(batch.to_dict()) == batch
    with pytest.raises(ValueError, match="JIT"):
        parse_ensemble(dict(model="ionic_worlds@1", simulation=value.definition, worlds=2))
    compiled = deepcopy(value.definition)
    compiled["execution"]["jit"] = True
    assert parse_ensemble(
        dict(model="ionic_worlds@1", simulation=compiled, worlds=2, window_steps=2)
    ).simulation == parse_spec(compiled)
    evidence(
        "public-owned-epoch-" + family,
        dict(
            definition=value.definition,
            parent_fields=parent_fields,
            complete_parent_state_layout_exact=True,
            all_original_accounting_references_retained=True,
            initial_phase_clock_reset_only=True,
            scope="Public serialization, snapshot and batch admission; no compiled execution",
        ),
    )


@pytest.mark.parametrize("family", OWNERS)
def test_owned_epoch_cli_from_snapshot_prepare_validate_and_fresh_replay(family, tmp_path):
    schema, _, parent_fields = OWNERS[family]
    source, before = source_checkpoint(family)
    folder = write_snapshot(tmp_path / "INIT", source, before)
    original_files = {p.name: p.read_bytes() for p in folder.iterdir()}
    raw = request(family)
    simulation = tmp_path / "SIM.json"
    simulation.write_text(json.dumps(raw["simulation"]))
    output = tmp_path / "prepared"
    first = cli("tissue-phase", "from-snapshot", folder, simulation, "--output", output)
    assert first.returncode == 0, first.stderr
    summary = json.loads(first.stdout)
    assert summary["model_id"] == schema.MODEL_ID
    assert len(summary["carried_parent_fields"]) == parent_fields
    assert summary["clocks"]["init_checkpoint_time_s"] == before.time
    assert read_preparation(output) == prepared(family)
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == original_files
    assert cli("tissue-phase", "validate", output).returncode == 0
    again = tmp_path / "replayed"
    second = cli("tissue-phase", "replay", output / "provenance.json", "--output", again)
    assert second.returncode == 0, second.stderr
    assert read_preparation(again) == prepared(family)
    assert cli("validate", again / "definition.json").returncode == 0
    # The embedded typed source is sufficient after its original snapshot is gone.
    simulation.unlink()
    for path in folder.iterdir():
        path.unlink()
    folder.rmdir()
    portable = tmp_path / "portable.json"
    portable.write_text(json.dumps(raw))
    third = cli("tissue-phase", "prepare", portable, "--output", tmp_path / "portable")
    assert third.returncode == 0, third.stderr
    assert read_preparation(tmp_path / "portable") == prepared(family)
    evidence(
        "public-owned-epoch-cli-" + family,
        dict(
            model_id=schema.MODEL_ID,
            fresh_process_source_and_replay_exact=True,
            portable_without_source_snapshot=True,
            parent_fields=parent_fields,
        ),
    )


@pytest.mark.parametrize("family", OWNERS)
@pytest.mark.parametrize(
    "fault", ["source-kind", "other-owner", "source-history", "resealed-history", "clock-policy"]
)
def test_public_owned_epoch_refuses_wrong_owner_history_and_policies(family, fault):
    raw = request(family)
    if fault == "source-kind":
        raw["kind"] = active_handoff.REQUEST_KIND
    elif fault == "other-owner":
        other = "fuel5" if family == "calcium6" else "calcium6"
        raw["simulation"] = request(other)["simulation"]
    elif fault in ("source-history", "resealed-history"):
        raw["source"]["checkpoint"]["state"]["pump_cycles"]["values"][0] += 1
        if fault == "resealed-history":
            raw["source"]["identity"] = digest(
                {k: v for k, v in raw["source"].items() if k != "identity"}
            )
    else:
        raw["policies"]["clock_policy"] = "reset-all-history"
    with pytest.raises((ConfigError, NumericalError)):
        prepare_request(raw)


@pytest.mark.parametrize("family", OWNERS)
def test_owned_epoch_refuses_implicit_transition_cuts_and_mixed_checkpoint_types(family):
    schema, _, _ = OWNERS[family]
    source, before = source_checkpoint(family)
    value = prepared(family)
    spec = parse_spec(value.definition)
    point = initialise(spec)
    with pytest.raises(ConfigError):
        validate_checkpoint(spec, before)
    with pytest.raises(ConfigError):
        validate_checkpoint(source, point)
    with pytest.raises(ConfigError):
        branch_checkpoint(source, before, spec)
    with pytest.raises(ConfigError):
        handoff.capture_source(spec, point)
    for bridge in (active_handoff, passive_handoff):
        with pytest.raises(ConfigError):
            bridge.capture_source(source, before)
    with pytest.raises(ConfigError):
        excise(spec, point, [spec.model.cells[0].id])
    mixed = BatchSpec(
        (WorldSpec(3, spec), WorldSpec(79, schema.scheduled_spec(spec))), 2, 10000, 2**32
    )
    with pytest.raises(ConfigError, match="model family"):
        parse_batch(mixed.to_dict())
    wrong = deepcopy(value.provenance)
    wrong["preservation"]["carried_parent_fields"] = []
    wrong["identity"] = digest({k: v for k, v in wrong.items() if k != "identity"})
    with pytest.raises(ConfigError):
        replay(wrong)


@pytest.mark.parametrize("family", OWNERS)
def test_public_eager_owned_epoch_carries_pools_and_exact_intermediate_restart(family, tmp_path):
    _, model, parent_fields = OWNERS[family]
    spec = parse_spec(prepared(family).definition)
    source, before = source_checkpoint(family)
    parent = handoff.owner(source).runtime
    result = run(spec)
    write_run(tmp_path / "run", result)
    assert result.final.step_index == 2
    for key, values in parent.parent_state(result.history)._asdict().items():
        np.testing.assert_array_equal(values[0], getattr(before.state, key))
    np.testing.assert_array_equal(
        result.observations.init_phase_clock_s,
        np.full_like(result.observations.init_phase_clock_s, before.state.phase_clock_s[0]),
    )
    np.testing.assert_allclose(
        result.observations.elapsed_time_s[:, 0], before.time + result.times, rtol=0, atol=1e-23
    )
    middle = result.checkpoint_at(spec.execution.dt)
    folder = write_snapshot(tmp_path / "middle", spec, middle)
    restored = load_snapshot(folder)
    resumed = run(restored.spec, restored.checkpoint)
    exact(resumed.final.state, result.final.state)
    exact(resumed.final.layout, result.final.layout)
    for key, values in vars(result.observations).items():
        np.testing.assert_array_equal(getattr(resumed.observations, key), values[1:])
    damaged = replace(middle, state=middle.state._replace(phase_clock_s=np.zeros(1)))
    with pytest.raises((ConfigError, NumericalError), match="clock"):
        validate_checkpoint(spec, damaged)
    evidence(
        "public-owned-epoch-eager-" + family,
        dict(
            definition=spec.to_dict(),
            parent_fields=parent_fields,
            real_sim_steps=result.final.step_index,
            init_time=before.time,
            all_initial_parent_arrays_exact=True,
            complete_restart_exact=True,
            diagnostics=result.diagnostics,
            scope="Two eager CPU steps and real intermediate restart; no compiled qualification",
        ),
    )
