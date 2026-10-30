"""Exact public restart of held-permeability steps, not new biology cases."""

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
from cells.core import physiology_tissue_step as tissue
from cells.core.grid import EventGrid
from cells.core.specs import ConfigError, read_json
from cells.processes import betse_perturbations as perturb
from tests.integration.test_physiology_checkpoint import assert_same_component
from tests.unit.test_physiology_permeability_view import exact_tree
from tests.unit.test_physiology_tissue_step import case


def inputs(kind="passive", engine="native"):
    spec, point, binding, component, _ = case(kind, at_event=True)
    if engine == "native":
        rng = np.random.RandomState(17)
        rng.normal()  # A real cached Gaussian must survive an unrelated tissue step.
        rng = perturb._native_stream(rng.get_state(), np.__version__)
    else:
        rng = perturb.StableCoordinates(17, 79)
    stream = streams.new_stream(
        binding.component, rng, stream_id="held-tissue", world_id=79, next_tick=101
    )
    controls = component.controls
    component = replace(component, stream=stream, controls=replace(controls, phase="INIT"))
    # Two explicit inactive component calls create a legitimately independent
    # clock; neither finalizes current P nor consumes a draw.
    for _ in range(2):
        component = component_step.advance(component, binding.component).state
    component = replace(component, controls=controls)
    assert component.time_s == 0.004 and component.loop_calls == 2
    assert component.stream.next_tick == 101
    if engine == "native":
        assert perturb.native_stream_manifest(component.stream.rng)["state"][3] == 1
    return spec, point, binding, component


def save(path, spec, point, binding, component, *, bound=True, complete=True):
    return paired.write_physiology_checkpoint(
        path,
        spec,
        point,
        component.stream,
        binding.component,
        component_state=component if complete else None,
        tissue_binding=binding if bound else None,
    )


def hashes(directory):
    return {
        str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def exact_checkpoint(actual, expected):
    exact_tree(actual.state, expected.state)
    exact_tree(actual.layout, expected.layout)
    assert (actual.time, actual.step_index, actual.event_index) == (
        expected.time,
        expected.step_index,
        expected.event_index,
    )


def evidence(name, record, arrays=None):
    if root := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        folder = Path(root) / "tissue-step-checkpoint"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / (name + ".json")).write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
        if arrays is not None:
            np.savez_compressed(folder / (name + ".npz"), **arrays)


@pytest.mark.parametrize("kind", ["passive", "ionic", "calcium", "fuel"])
@pytest.mark.parametrize("engine", ["native", "stable"])
def test_two_full_intervals_restarted_at_control_event_are_exact(tmp_path, kind, engine):
    spec, point, binding, component = inputs(kind, engine)
    source = save(tmp_path / "source", spec, point, binding, component)
    retained = hashes(source)
    expected, actual, archives = point, point, {}
    layout = point.layout
    times = EventGrid(spec)
    for index in range(2):
        wanted = tissue.advance(spec, expected, binding, component)
        target = tmp_path / ("step-" + str(index + 1))
        result = paired.advance_tissue_checkpoint(
            source,
            target,
            binding.component,
            expected_stream_id="held-tissue",
            expected_world_id=79,
            tissue_binding=binding,
            end_time_s=times[index + 1],
        )
        loaded = paired.load_physiology_checkpoint(target, binding.component)
        actual, expected = loaded.snapshot.checkpoint, wanted.checkpoint
        exact_checkpoint(actual, expected)
        exact_checkpoint(result.checkpoint, expected)
        exact_tree(actual.layout, layout)
        assert_same_component(loaded.component_state, component)
        assert_same_component(result.component, component)
        assert units.binding_record(loaded.tissue_binding) == units.binding_record(binding)
        assert result.component.stream.next_tick == 101 and actual.step_index == index + 1
        assert actual.time == times[index + 1] and actual.time != component.time_s
        assert loaded.snapshot.spec == spec and hashes(source) == retained
        for label, values in (("actual", actual.state), ("uninterrupted", expected.state)):
            archives.update(
                {str(index) + "__" + label + "__" + k: v for k, v in values._asdict().items()}
            )
        source, retained = target, hashes(target)
    assert read_json(tmp_path / "step-1/snapshot/manifest.json")["clock"]["event_index"] > 0
    uninterrupted_stream, resumed_stream = component.stream, loaded.stream
    for site in ("microtubule_gaussian", "protein_flux", "boundary_choice"):
        before, uninterrupted_stream = streams.draw(
            uninterrupted_stream, binding.component, site=site
        )
        after, resumed_stream = streams.draw(resumed_stream, binding.component, site=site)
        np.testing.assert_array_equal(before.values, after.values, strict=True)
        assert streams.stream_record(uninterrupted_stream) == streams.stream_record(resumed_stream)
    evidence(
        "restart-" + kind + "-" + engine,
        dict(
            definition=spec.to_dict(),
            binding=units.binding_record(binding),
            accepted_times_s=[times[i] for i in range(3)],
            complete_fields=len(actual.state),
            actual_final_clock=dict(
                time=actual.time, step=actual.step_index, event=actual.event_index
            ),
            component_clock_s=component.time_s,
            component_calls=component.loop_calls,
            unchanged_stream=streams.stream_record(component.stream),
            original_sources_preserved=True,
            all_fields_exact=True,
            scope="Two original grid intervals and future stream equality; restart evidence only",
        ),
        archives,
    )


def test_public_tissue_advance_does_not_draw_finalize_or_advance_component(tmp_path, monkeypatch):
    spec, point, binding, component = inputs()
    source = save(tmp_path / "source", spec, point, binding, component)

    def forbidden(*args, **kwargs):
        pytest.fail("Implicit component/RNG work during a held-permeability tissue interval")

    for module, name in (
        (streams, "draw"),
        (component_step, "advance"),
        (perturb, "sample_native"),
        (perturb, "sample_stable"),
        (perturb, "static_initialize"),
    ):
        monkeypatch.setattr(module, name, forbidden)
    result = paired.advance_tissue_checkpoint(source, tmp_path / "accepted", binding.component)
    assert_same_component(result.component, component)
    assert not np.array_equal(
        component.diffusion.current_m2_s,
        component.diffusion.base_m2_s + component.diffusion.scheduled_m2_s,
    )


@pytest.mark.parametrize("kind", ["directory", "file", "dangling_symlink"])
def test_existing_destination_refuses_before_numerical_work(tmp_path, monkeypatch, kind):
    target = tmp_path / "existing"
    if kind == "directory":
        target.mkdir()
        (target / "retained.txt").write_text("retained")
    elif kind == "file":
        target.write_text("retained")
    else:
        target.symlink_to(tmp_path / "absent")

    def forbidden(*args, **kwargs):
        pytest.fail("Existing destination should refuse before loading or stepping")

    monkeypatch.setattr(paired, "load_physiology_checkpoint", forbidden)
    monkeypatch.setattr(tissue, "advance", forbidden)
    with pytest.raises(FileExistsError):
        paired.advance_tissue_checkpoint(tmp_path / "unused", target, None)
    if kind == "directory":
        assert (target / "retained.txt").read_text() == "retained"
    elif kind == "file":
        assert target.read_text() == "retained"
    else:
        assert target.is_symlink()


@pytest.mark.parametrize("complete", [False, True])
def test_older_unbound_formats_cannot_enter_public_tissue_step(tmp_path, monkeypatch, complete):
    spec, point, binding, component = inputs()
    source = save(
        tmp_path / "source", spec, point, binding, component, bound=False, complete=complete
    )

    def forbidden(*args, **kwargs):
        pytest.fail("Unbound checkpoint reached tissue stepping")

    monkeypatch.setattr(tissue, "advance", forbidden)
    with pytest.raises(ConfigError):
        paired.advance_tissue_checkpoint(source, tmp_path / "refused", binding.component)
    assert not (tmp_path / "refused").exists()


@pytest.mark.parametrize("wrong", ["stream", "world", "binding"])
def test_caller_identity_expectations_are_enforced_before_stepping(tmp_path, monkeypatch, wrong):
    spec, point, binding, component = inputs()
    source = save(tmp_path / "source", spec, point, binding, component)
    retained = hashes(source)
    expectations = dict(
        expected_stream_id="held-tissue", expected_world_id=79, tissue_binding=binding
    )
    if wrong == "stream":
        expectations["expected_stream_id"] = "other"
    elif wrong == "world":
        expectations["expected_world_id"] = 80
    else:
        from tests.unit.test_physiology_tissue_binding import arguments

        expectations["tissue_binding"] = units.bind_tissue(spec, **arguments(spec))

    def forbidden(*args, **kwargs):
        pytest.fail("Foreign ownership reached tissue stepping")

    monkeypatch.setattr(tissue, "advance", forbidden)
    with pytest.raises(ConfigError):
        paired.advance_tissue_checkpoint(
            source, tmp_path / "refused", binding.component, **expectations
        )
    assert hashes(source) == retained and not (tmp_path / "refused").exists()


def test_skipped_event_refusal_keeps_source_and_creates_no_destination(tmp_path):
    spec, point, binding, component = inputs()
    source = save(tmp_path / "source", spec, point, binding, component)
    retained = hashes(source)
    with pytest.raises(tissue.TissueStepRejected) as raised:
        paired.advance_tissue_checkpoint(
            source, tmp_path / "refused", binding.component, end_time_s=EventGrid(spec)[2]
        )
    assert raised.value.trial is None
    assert hashes(source) == retained and not (tmp_path / "refused").exists()


def test_rejected_raw_trial_propagates_without_publication(tmp_path, monkeypatch):
    spec, point, binding, component = inputs()
    source = save(tmp_path / "source", spec, point, binding, component)
    retained = hashes(source)
    original, captured = tissue.array_rk4_step, []

    def rejected(*args, **kwargs):
        trial = original(*args, **kwargs)._replace(valid=np.bool_(False), first_invalid_stage=2)
        captured.append(trial)
        return trial

    monkeypatch.setattr(tissue, "array_rk4_step", rejected)
    with pytest.raises(tissue.TissueStepRejected) as raised:
        paired.advance_tissue_checkpoint(source, tmp_path / "refused", binding.component)
    exact_tree(raised.value.trial, captured[0])
    assert raised.value.stage == "rk4_trial"
    assert_same_component(raised.value.component, component)
    assert hashes(source) == retained and not (tmp_path / "refused").exists()
    evidence(
        "injected-rejection",
        dict(
            stage=raised.value.stage,
            raw_trial_retained=True,
            source_unchanged=True,
            no_destination=True,
            synthetic_status_fault=True,
        ),
        raised.value.trial.proposed_state._asdict(),
    )


def test_publication_failure_preserves_failure_artifact_and_original_source(tmp_path, monkeypatch):
    spec, point, binding, component = inputs()
    source = save(tmp_path / "source", spec, point, binding, component)
    retained, original = hashes(source), paired._write_json

    def broken(path, value):
        if path.name == "component.json":
            raise OSError("injected component publication failure")
        original(path, value)

    monkeypatch.setattr(paired, "_write_json", broken)
    with pytest.raises(OSError, match="injected"):
        paired.advance_tissue_checkpoint(source, tmp_path / "failed", binding.component)
    assert (tmp_path / "failed/failure.json").exists()
    assert not (tmp_path / "failed/manifest.json").exists()
    with pytest.raises(ConfigError, match="Failed physiological"):
        paired.load_physiology_checkpoint(tmp_path / "failed", binding.component)
    assert hashes(source) == retained


@pytest.mark.parametrize("when", ["during_step", "during_numeric_publication"])
def test_source_drift_cannot_relabel_an_already_computed_step(tmp_path, monkeypatch, when):
    from cells import io

    spec, point, binding, component = inputs()
    source = save(tmp_path / "source", spec, point, binding, component)
    retained = hashes(source)
    altered = paired.source_hashes() | {"core/physiology_tissue_step.py": "changed"}

    def change_source():
        monkeypatch.setattr(paired, "source_hashes", lambda: altered)
        monkeypatch.setattr(io, "source_hashes", lambda: altered)

    if when == "during_step":
        original = tissue.advance

        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            change_source()
            return result

        monkeypatch.setattr(tissue, "advance", changed)
    else:
        original = paired.write_snapshot

        def changed(*args, **kwargs):
            change_source()
            return original(*args, **kwargs)

        monkeypatch.setattr(paired, "write_snapshot", changed)
    with pytest.raises(ConfigError, match="source"):
        paired.advance_tissue_checkpoint(source, tmp_path / "refused", binding.component)
    assert hashes(source) == retained and not (tmp_path / "refused/manifest.json").exists()
    if when == "during_step":
        assert not (tmp_path / "refused").exists()
    else:
        assert (tmp_path / "refused/failure.json").exists()
