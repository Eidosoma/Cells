"""Whole-loop publication and exact restart; numerical accuracy is qualified separately."""

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells import physiology_checkpoint as paired
from cells.core import physiology_perturbation_step as component_step
from cells.core import physiology_random_streams as streams
from cells.core import physiology_tissue_binding as units
from cells.core import physiology_tissue_loop as loop
from cells.core import physiology_tissue_step as tissue
from cells.core.specs import ConfigError, digest, read_json
from cells.processes import betse_perturbations as perturb
from tests.integration.test_physiology_checkpoint import assert_same_component, write_json
from tests.integration.test_physiology_tissue_step_checkpoint import exact_checkpoint, hashes
from tests.unit.test_physiology_permeability_view import exact_tree
from tests.unit.test_physiology_tissue_step import case


def inputs(kind="passive", engine="native"):
    spec, point, binding, _, _ = case(kind, at_event=True, source_dt_scale=0.5)
    if engine == "native":
        rng = np.random.RandomState(17)
        rng.normal()
        rng = perturb._native_stream(rng.get_state(), np.__version__)
    else:
        rng = perturb.StableCoordinates(17, 79)
    stream = streams.new_stream(
        binding.component, rng, stream_id="loop-physiology", world_id=79, next_tick=100
    )
    component = component_step.initialise(
        binding.component,
        perturb.Controls("INIT", "normal", True, True, 2.0, 3e-8, 0.002),
        perturb.ProteinState(
            np.full(len(binding.component.cell_ids), 8.0),
            np.full(len(binding.component.membrane_ids), 6.0),
            np.full(len(binding.component.environment_ids), 5.0),
        ),
        units.initial_diffusion(binding),
        stream,
    )
    for _ in range(2):
        component = component_step.advance(component, binding.component).state
    component = replace(
        component,
        controls=replace(component.controls, phase="SIM", dt_s=2 * spec.execution.dt),
        diffusion=component.diffusion._replace(
            scheduled_m2_s=-0.25 * component.diffusion.base_m2_s
        ),
    )
    assert component.time_s == 0.004 and component.loop_calls == 2
    assert component.stream.next_tick == 101
    return spec, point, binding, component


def save(path, spec, point, binding, component, cursor=None):
    return paired.write_physiology_checkpoint(
        path,
        spec,
        point,
        component.stream,
        binding.component,
        component_state=component,
        tissue_binding=binding,
        loop_cursor=cursor,
    )


def managed(path):
    spec, point, binding, component = inputs()
    cursor = loop.initialise(spec, point, binding, component)
    save(path, spec, point, binding, component, cursor)
    return spec, point, binding, component, cursor


def evidence(name, record, arrays=None):
    if root := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        folder = Path(root) / "loop-checkpoint"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / (name + ".json")).write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
        if arrays is not None:
            np.savez_compressed(folder / (name + ".npz"), **arrays)


@pytest.mark.parametrize("kind", ["passive", "ionic", "calcium", "fuel"])
@pytest.mark.parametrize("engine", ["native", "stable"])
def test_two_complete_loop_restarts_preserve_all_states_clocks_and_draws(tmp_path, kind, engine):
    spec, point, binding, component = inputs(kind, engine)
    original = save(tmp_path / "bound", spec, point, binding, component)
    retained = hashes(original)
    cursor = paired.initialise_loop_checkpoint(
        original,
        tmp_path / "managed",
        binding.component,
        expected_stream_id="loop-physiology",
        expected_world_id=79,
        tissue_binding=binding,
    )
    assert hashes(original) == retained
    assert cursor == loop.initialise(spec, point, binding, component)
    source, clocks, arrays = tmp_path / "managed", [], {}
    for index in range(2):
        before = hashes(source)
        expected = loop.advance(spec, point, binding, component, cursor)
        target = tmp_path / ("accepted-" + str(index + 1))
        result = paired.advance_loop_checkpoint(
            source,
            target,
            binding.component,
            expected_stream_id="loop-physiology",
            expected_world_id=79,
            tissue_binding=binding,
            loop_cursor=cursor,
        )
        restored = paired.load_physiology_checkpoint(
            target, binding.component, require_loop_cursor=True
        )
        exact_checkpoint(restored.snapshot.checkpoint, expected.checkpoint)
        exact_checkpoint(result.checkpoint, expected.checkpoint)
        assert_same_component(restored.component_state, expected.component)
        assert_same_component(result.component, expected.component)
        assert loop.cursor_record(restored.loop_cursor) == loop.cursor_record(expected.cursor)
        assert result.next_loop_index == index + 1
        assert result.component.loop_calls == 3 + index
        assert result.component.stream.next_tick == 102 + index
        assert result.cursor.component_call_origin == 2
        assert result.cursor.physiological_dt_s == 2 * spec.execution.dt
        assert len(result.tissue_steps) >= 2  # Noise is not tied to these substeps.
        assert len(result.tissue_steps) == len(expected.tissue_steps)
        exact_tree(
            result.component_transition.packet.values, expected.component_transition.packet.values
        )
        assert hashes(source) == before
        clocks.append(loop.cursor_record(result.cursor))
        arrays.update(
            {str(index) + "__actual__" + k: v for k, v in result.checkpoint.state._asdict().items()}
        )
        arrays.update(
            {
                str(index) + "__expected__" + k: v
                for k, v in expected.checkpoint.state._asdict().items()
            }
        )
        arrays[str(index) + "__packet"] = result.component_transition.packet.values
        source, point, component, cursor = (
            target,
            expected.checkpoint,
            expected.component,
            expected.cursor,
        )
    assert restored.loop_cursor.loop_index == 2 and restored.snapshot.checkpoint.step_index > 2
    assert read_json(source / "manifest.json")["kind"] == paired.LOOP_KIND
    assert set(read_json(source / "manifest.json")["files"]) == paired.LOOP_FILES
    actual_stream, expected_stream = restored.stream, component.stream
    for site in ("microtubule_gaussian", "protein_flux", "boundary_choice"):
        actual_draw, actual_stream = streams.draw(actual_stream, binding.component, site=site)
        expected_draw, expected_stream = streams.draw(expected_stream, binding.component, site=site)
        np.testing.assert_array_equal(actual_draw.values, expected_draw.values, strict=True)
        assert streams.stream_record(actual_stream) == streams.stream_record(expected_stream)
    evidence(
        "restart-" + kind + "-" + engine,
        dict(
            definition=spec.to_dict(),
            binding=units.binding_record(binding),
            loop_clocks=clocks,
            state_fields=len(point.state),
            all_fields_exact=True,
            complete_loops=2,
            physiological_calls=2,
            dynamic_draws=2,
            scope="Restart evidence only",
        ),
        arrays,
    )


def test_initialising_loading_and_saving_cursor_do_not_advance_or_draw(tmp_path, monkeypatch):
    spec, point, binding, component = inputs()
    source = save(tmp_path / "bound", spec, point, binding, component)

    def forbidden(*args, **kwargs):
        pytest.fail("Cursor/checkpoint association executed a physiological or numeric update")

    for module, name in (
        (loop, "advance"),
        (tissue, "advance"),
        (component_step, "advance"),
        (streams, "draw"),
    ):
        monkeypatch.setattr(module, name, forbidden)
    cursor = paired.initialise_loop_checkpoint(source, tmp_path / "managed", binding.component)
    loaded = paired.load_physiology_checkpoint(tmp_path / "managed", binding.component)
    assert loaded.loop_cursor == cursor
    exact_checkpoint(loaded.snapshot.checkpoint, point)
    assert_same_component(loaded.component_state, component)


def reseal(path):
    record = read_json(path / "loop.json")
    record["identity"] = digest({k: v for k, v in record.items() if k != "identity"})
    write_json(path / "loop.json", record)
    manifest = read_json(path / "manifest.json")
    manifest["files"] = {
        n: hashlib.sha256((path / n).read_bytes()).hexdigest() for n in paired.LOOP_FILES
    }
    manifest["loop_cursor_identity"] = record["identity"]
    manifest["identity"] = digest({k: v for k, v in manifest.items() if k != "identity"})
    write_json(path / "manifest.json", manifest)


@pytest.mark.parametrize(
    "defect",
    [
        "missing",
        "extra_file",
        "bytes",
        "index",
        "dt",
        "numeric_step",
        "component_time",
        "component_calls",
        "call_origin",
        "tick",
        "state_seal",
        "component_seal",
        "extra_field",
    ],
)
def test_cursor_corruption_and_resealed_wrong_associations_refuse(tmp_path, defect):
    path = tmp_path / "managed"
    _, _, binding, _, _ = managed(path)
    file = path / "loop.json"
    if defect == "missing":
        file.unlink()
    elif defect == "extra_file":
        (path / "extra.json").write_text("{}")
    elif defect == "bytes":
        file.write_text(file.read_text() + " ")
    else:
        record = read_json(file)
        key = dict(
            index="loop_index",
            dt="physiological_dt_s",
            numeric_step="numeric_step_index",
            component_time="component_time_s",
            component_calls="component_loop_calls",
            call_origin="component_call_origin",
            tick="stream_next_tick",
            state_seal="checkpoint_identity",
            component_seal="component_identity",
            extra_field="extra_field",
        )[defect]
        record[key] = (
            "changed"
            if defect in ("state_seal", "component_seal", "extra_field")
            else record[key] + 1
        )
        write_json(file, record)
        reseal(path)
    with pytest.raises(ConfigError):
        paired.load_physiology_checkpoint(path, binding.component)


@pytest.mark.parametrize("defect", ["component", "clock", "no_binding"])
def test_mixed_cursor_pair_refuses_before_directory_creation(tmp_path, defect):
    spec, point, binding, component = inputs()
    cursor = loop.initialise(spec, point, binding, component)
    if defect == "component":
        component = replace(component, time_s=component.time_s + 1)
    elif defect == "clock":
        point = replace(point, step_index=1)
    with pytest.raises((ConfigError, ValueError)):
        paired.write_physiology_checkpoint(
            tmp_path / "refused",
            spec,
            point,
            component.stream,
            binding.component,
            component_state=component,
            tissue_binding=None if defect == "no_binding" else binding,
            loop_cursor=cursor,
        )
    assert not (tmp_path / "refused").exists()


@pytest.mark.parametrize("operation", ["held_step", "initialise_again"])
def test_managed_cursor_cannot_be_silently_dropped_or_reinitialised(tmp_path, operation):
    _, _, binding, _, _ = managed(tmp_path / "managed")
    call = (
        paired.advance_tissue_checkpoint
        if operation == "held_step"
        else paired.initialise_loop_checkpoint
    )
    with pytest.raises(ConfigError, match="loop|Loop"):
        call(tmp_path / "managed", tmp_path / "refused", binding.component)
    assert not (tmp_path / "refused").exists()


def test_loop_advance_requires_explicitly_initialised_cursor(tmp_path):
    spec, point, binding, component = inputs()
    source = save(tmp_path / "bound", spec, point, binding, component)
    assert paired.load_physiology_checkpoint(source, binding.component).loop_cursor is None
    with pytest.raises(ConfigError, match="unmanaged"):
        paired.advance_loop_checkpoint(source, tmp_path / "refused", binding.component)
    assert not (tmp_path / "refused").exists()


def test_late_substep_failure_keeps_whole_accepted_pair_and_proposed_tape(tmp_path, monkeypatch):
    source = tmp_path / "managed"
    _, _, binding, component, cursor = managed(source)
    before = hashes(source)
    kernel, calls = tissue.array_rk4_step, []

    def refuse_second(*args, **kwargs):
        trial = kernel(*args, **kwargs)
        calls.append(trial)
        return (
            trial._replace(valid=np.bool_(False), first_invalid_stage=1)
            if len(calls) == 2
            else trial
        )

    with monkeypatch.context() as trial_guard:
        trial_guard.setattr(tissue, "array_rk4_step", refuse_second)
        with pytest.raises(loop.TissueLoopRejected) as raised:
            paired.advance_loop_checkpoint(source, tmp_path / "refused", binding.component)
    error = raised.value
    assert len(error.tissue_steps) == 1 and error.failed_tissue_step.trial is not None
    assert error.proposed_stream.next_tick == component.stream.next_tick + 1
    assert_same_component(error.source_component, component)
    assert error.cursor == cursor and hashes(source) == before
    assert not (tmp_path / "refused").exists()
    accepted = paired.advance_loop_checkpoint(
        source, tmp_path / "explicit-retry", binding.component
    )
    assert_same_component(accepted.component, error.proposed_component)
    assert accepted.component_transition.packet.identity == error.packet.identity
    evidence(
        "late-failure",
        dict(
            source_unchanged=True,
            committed_partial_loop=False,
            completed_local_trials=1,
            source_tick=component.stream.next_tick,
            proposed_tick=error.proposed_stream.next_tick,
            explicit_retry_packet_exact=True,
            synthetic_status_fault=True,
        ),
        error.failed_tissue_step.trial.proposed_state._asdict(),
    )


def test_loop_payload_publication_failure_is_not_an_accepted_checkpoint(tmp_path, monkeypatch):
    source = tmp_path / "managed"
    _, _, binding, _, _ = managed(source)
    before, original = hashes(source), paired._write_json

    def refuse(path, value):
        if path.name == "loop.json":
            raise OSError("injected cursor publication failure")
        original(path, value)

    monkeypatch.setattr(paired, "_write_json", refuse)
    with pytest.raises(OSError, match="injected"):
        paired.advance_loop_checkpoint(source, tmp_path / "failed", binding.component)
    assert hashes(source) == before
    assert (tmp_path / "failed/failure.json").exists()
    assert not (tmp_path / "failed/manifest.json").exists()
    with pytest.raises(ConfigError, match="Failed physiological"):
        paired.load_physiology_checkpoint(tmp_path / "failed", binding.component)


@pytest.mark.parametrize("require", [None, 0, 1, "true"])
def test_loop_requirement_is_an_explicit_boolean(tmp_path, require):
    _, _, binding, _, _ = managed(tmp_path / "managed")
    with pytest.raises(ConfigError, match="booleans"):
        paired.load_physiology_checkpoint(
            tmp_path / "managed", binding.component, require_loop_cursor=require
        )
