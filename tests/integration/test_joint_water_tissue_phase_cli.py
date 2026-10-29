"""Public complete-water phase preparation; independent dynamics stay separate."""

import json
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from cells.core import joint_water_profile_phase_handoff as handoff
from cells.core.batch import BatchSpec, WorldSpec, parse_batch
from cells.core.errors import NumericalError
from cells.core.runner import branch_checkpoint, validate_checkpoint
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import initialise
from cells.ensemble.ionic import parse_spec as parse_ensemble
from cells.io import load_snapshot, write_snapshot
from cells.models.registry import get_model
from cells.tissue_phase import _source_adapter, read_preparation, replay
from tests.joint_water_phase_fixtures import components, prepared, request, source_checkpoint
from tests.joint_water_profile_fixtures import DT, FAMILIES, FIELDS
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_kinetic import exact


def invoke(directory, label, *arguments):
    """Use the public CLI in a fresh process and keep its actual diagnostics."""
    result = subprocess.run(
        [sys.executable, "-B", "-m", "cells", *map(str, arguments)],
        capture_output=True,
        text=True,
        timeout=240,
    )
    (directory / (label + ".stdout.log")).write_text(result.stdout)
    (directory / (label + ".stderr.log")).write_text(result.stderr)
    assert result.returncode == 0, result.stderr
    return result


@pytest.mark.parametrize("family", FAMILIES)
def test_public_water_epoch_keeps_all_carried_state_and_original_references(family, tmp_path):
    schema, model = components(family)
    value = prepared(family)
    spec = parse_spec(value.definition)
    source, original = source_checkpoint(family)
    parent = handoff.owner(source).runtime
    assert get_model(spec.model) is model
    assert spec == parse_spec(spec.to_dict())
    assert _source_adapter(source) == (handoff, schema.POLICIES)
    point = initialise(spec)
    assert len(point.state) == FIELDS[family]
    assert type(point.state) is model.STATE_TYPE and type(point.layout) is model.LAYOUT_TYPE
    exact(parent.parent_state(point.state), parent.parent_state(original.state))
    exact(parent.parent_layout(point.layout), parent.parent_layout(original.layout))
    assert point.time == point.step_index == 0 and original.time == DT
    np.testing.assert_array_equal(point.state.phase_clock_s, [0.0])
    for name in (
        "channel_transferred",
        "pump_cycles",
        "chemical_amount_increment",
        "energy_amount_increment_fmol",
    ):
        assert np.any(getattr(point.state, name) != 0), name
    table = control_values(spec, [0.0, DT])
    exact(table, control_values(schema.scheduled_spec(spec), [0.0, DT]))
    assert np.any(table.water != control_values(source, [0.0, DT]).water)
    laws = np.asarray(point.layout.channel_laws)[np.asarray(point.layout.channel_active)]
    assert set(laws) == set(range(56))
    restored = load_snapshot(write_snapshot(tmp_path / "epoch", spec, point))
    exact(restored.checkpoint.state, point.state)
    exact(restored.checkpoint.layout, point.layout)
    for other, wrong in ((spec, original), (source, point)):
        with pytest.raises(ConfigError):
            validate_checkpoint(other, wrong)
    with pytest.raises(ConfigError):
        branch_checkpoint(source, original, spec)
    with pytest.raises(ConfigError):
        _source_adapter(spec)
    mixed = BatchSpec(
        (WorldSpec(3, spec), WorldSpec(79, schema.scheduled_spec(spec))), 2, 100, 2**32
    )
    with pytest.raises(ConfigError, match="model family"):
        parse_batch(mixed.to_dict())
    bad = deepcopy(value.provenance)
    bad["preservation"]["carried_parent_fields"] = []
    with pytest.raises(ConfigError):
        replay(bad)
    evidence(
        "joint-water-public-epoch-" + family,
        dict(
            definition=spec.to_dict(),
            physical_fields=FIELDS[family] - 1,
            all_carried_arrays_and_original_layout_exact=True,
            only_phase_clock_reset=True,
            scope=(
                "One host INIT step and public phase/snapshot contracts; not physical qualification"
            ),
        ),
        arrays={k: np.asarray(v) for k, v in point.state._asdict().items()},
    )


@pytest.mark.parametrize("family", FAMILIES)
def test_water_epoch_public_snapshot_preparation_and_portable_replay(family, tmp_path):
    schema, _ = components(family)
    source, point = source_checkpoint(family)
    snapshot = write_snapshot(tmp_path / "INIT", source, point)
    before = {p.name: p.read_bytes() for p in snapshot.iterdir()}
    simulation = tmp_path / "SIM.json"
    simulation.write_text(json.dumps(request(family)["simulation"]))
    output = tmp_path / "prepared"
    result = invoke(
        tmp_path,
        "prepare",
        "tissue-phase",
        "from-snapshot",
        snapshot,
        simulation,
        "--output",
        output,
    )
    summary = json.loads(result.stdout)
    assert summary["model_id"] == schema.MODEL_ID
    assert len(summary["carried_parent_fields"]) == FIELDS[family] - 1
    assert read_preparation(output) == prepared(family)
    assert {p.name: p.read_bytes() for p in snapshot.iterdir()} == before
    invoke(tmp_path, "validate", "tissue-phase", "validate", output)
    # The source directory and SIM input are unavailable to the fresh replay.
    snapshot.rename(tmp_path / "archived-INIT")
    simulation.unlink()
    invoke(
        tmp_path,
        "replay",
        "tissue-phase",
        "replay",
        output / "provenance.json",
        "--output",
        tmp_path / "replayed",
    )
    assert read_preparation(tmp_path / "replayed") == prepared(family)
    evidence(
        "joint-water-public-epoch-cli-" + family,
        dict(
            physical_fields=FIELDS[family] - 1,
            summary=summary,
            source_snapshot_unchanged=True,
            portable_fresh_process_replay=True,
            scope="Public preparation/validation/replay only; no post-handoff trajectory",
        ),
    )


@pytest.mark.parametrize("family", FAMILIES)
def test_water_epoch_fresh_sim_execution_and_complete_intermediate_restart(family, tmp_path):
    schema, model = components(family)
    value = prepared(family)
    spec = parse_spec(value.definition)
    source, before = source_checkpoint(family)
    parent = handoff.owner(source).runtime
    config = tmp_path / "epoch.json"
    config.write_text(json.dumps(value.definition))
    original, resumed = tmp_path / "original", tmp_path / "resumed"
    invoke(tmp_path, "run", "run", config, "--output", original, "--checkpoint-at", DT)
    manifest = json.loads((original / "manifest.json").read_text())
    middle = original / manifest["snapshots"][0]
    saved_middle = load_snapshot(middle)
    assert saved_middle.spec == spec and saved_middle.checkpoint.time == DT
    damaged = replace(
        saved_middle.checkpoint,
        state=saved_middle.checkpoint.state._replace(phase_clock_s=np.zeros(1)),
    )
    with pytest.raises((ConfigError, NumericalError), match="clock"):
        validate_checkpoint(spec, damaged)
    invoke(tmp_path, "resume", "resume", middle, "--output", resumed)
    expected = load_snapshot(original / "checkpoint_final")
    actual = load_snapshot(resumed / "checkpoint_final")
    assert type(actual.checkpoint.state) is model.STATE_TYPE
    assert type(actual.checkpoint.layout) is model.LAYOUT_TYPE
    assert actual.spec == expected.spec == spec
    assert actual.checkpoint.time == expected.checkpoint.time == 2 * DT
    exact(actual.checkpoint.state, expected.checkpoint.state)
    exact(actual.checkpoint.layout, expected.checkpoint.layout)
    with (
        np.load(original / "trajectory.npz", allow_pickle=False) as first,
        np.load(resumed / "trajectory.npz", allow_pickle=False) as second,
    ):
        arrays = {"original_" + k: first[k] for k in first.files}
        arrays.update({"resumed_" + k: second[k] for k in second.files})
        assert len(first["accepted_times"]) == 3
        np.testing.assert_array_equal(second["accepted_times"], first["accepted_times"][1:])
        for name in model.STATE_TYPE._fields:
            np.testing.assert_array_equal(second[name], first[name][1:])
        # The new phase begins with actual, nonzero INIT histories and original anchors.
        for name in parent.parent_state(before.state)._fields:
            np.testing.assert_array_equal(first[name][0], getattr(before.state, name))
        observed = [k for k in first.files if k.startswith("observed_")]
        selected = first["observation_times"] >= DT
        for name in ["observation_times", *observed]:
            np.testing.assert_array_equal(second[name], first[name][selected])
        np.testing.assert_array_equal(
            first["observed_init_phase_clock_s"],
            np.full_like(first["observed_init_phase_clock_s"], before.state.phase_clock_s[0]),
        )
        np.testing.assert_allclose(
            first["observed_elapsed_time_s"][:, 0],
            before.time + first["observation_times"],
            atol=1e-23,
            rtol=0,
        )
    summary = json.loads((resumed / "summary.json").read_text())
    assert summary["executed_steps"] == 1
    assert summary["model"] == schema.MODEL_ID
    evidence(
        "joint-water-epoch-fresh-sim-" + family,
        dict(
            definition=value.definition,
            init_time_s=before.time,
            sim_end_time_s=2 * DT,
            complete_fields=FIELDS[family],
            layout_fields=len(actual.checkpoint.layout),
            observation_fields=len(observed),
            restored_steps=1,
            restored_summary=summary,
            init_state_preserved=True,
            all_final_arrays_and_observation_suffix_exact=True,
            scope="One1-ns host INIT step, two eager CPU SIM steps and one real fresh-process "
            "restored step; no physical or compiled/GPU qualification",
        ),
        arrays=arrays,
    )


@pytest.mark.parametrize("family", FAMILIES)
def test_water_epoch_ensemble_admission_keeps_carried_state(family):
    schema, model = components(family)
    raw = deepcopy(prepared(family).definition)
    with pytest.raises(ValueError, match="JIT"):
        parse_ensemble(dict(model="ionic_worlds@1", simulation=raw, worlds=2))
    raw["execution"]["jit"] = True
    spec = parse_spec(raw)
    ensemble = parse_ensemble(dict(model="ionic_worlds@1", simulation=raw, worlds=2))
    assert ensemble.simulation == spec and get_model(spec.model) is model
    batch = BatchSpec((WorldSpec(3, spec), WorldSpec(79, spec)), 2, 100, 2**32)
    assert parse_batch(batch.to_dict()) == batch
    assert spec.to_dict()["model"]["id"] == schema.MODEL_ID
    evidence(
        "joint-water-epoch-ensemble-" + family,
        dict(
            definition=raw,
            exact_epoch_identity_and_source=True,
            scope="CPU/GPU scheduler admission only; no batched or GPU execution",
        ),
    )


def test_water_epoch_offline_world_assignment_through_sixteen_gpus():
    from tests.unit.test_hcn_extra_catalog_planning import verify
    from tests.unit.test_integrated_ensemble import experiment

    raw = experiment("ionic", backend="gpu", worlds=8, width=1)
    # Complete carried INIT provenance is included in the conservative output
    # estimate. This is a disk allowance, separate from the worker RAM guard.
    raw["execution"]["max_output_bytes"] = 4 * 1024**3
    template = deepcopy(raw["arms"][0])
    raw["arms"] = []
    expected_definitions = {}
    for family in FAMILIES:
        arm = deepcopy(template)
        arm["id"] = family
        definition = deepcopy(prepared(family).definition)
        definition["execution"].update(backend="gpu", jit=True)
        expected_definitions[family] = parse_spec(definition).to_dict()
        arm["definition"]["simulation"] = definition
        raw["arms"].append(arm)
    plans = verify(raw)
    ids, counts = [], dict.fromkeys(FAMILIES, 0)
    for task in plans["local"]["tasks"]:
        definition = task["definition"]
        assert definition["model"] == "ionic_worlds@1"
        assert definition["seed"] == raw["seed"]
        # Every task must carry the complete canonical definition, including
        # INIT state/layout/provenance, with no flattening or physics mutation.
        assert definition["simulation"] == expected_definitions[task["arm"]]
        counts[task["arm"]] += definition["worlds"]
        ids.extend(
            range(definition["world_id_start"], definition["world_id_start"] + definition["worlds"])
        )
    assert sorted(ids) == list(range(16)) and set(counts.values()) == {8}
    evidence(
        "joint-water-epoch-offline-planning",
        dict(
            inputs=raw,
            plans=plans,
            per_arm_worlds=counts,
            world_ids=sorted(ids),
            scope=(
                "Offline 1/4/16-GPU planning of independent worlds; "
                "no remote execution or utilization"
            ),
        ),
    )
