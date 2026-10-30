"""Complete perturbation restart, separately from the deterministic numeric clock."""

import hashlib
from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from cells import physiology_checkpoint as paired
from cells.core import physiology_perturbation_step as step
from cells.core import physiology_random_streams as streams
from cells.core.runner import run
from cells.core.specs import ConfigError, digest, parse_spec, read_json
from cells.io import load_snapshot, write_snapshot
from cells.processes import betse_perturbations as perturb


@pytest.fixture
def setup(config_data):
    raw = deepcopy(config_data)
    raw["experiment"] = dict(
        end_time=0.1,
        source=dict(kind="prescribed_external_amount_rate", schedule=[dict(time=0.0, rate=0.1)]),
        observation_times=[0.0, 0.05, 0.1],
    )
    raw["execution"].update(jit=False, max_steps=4)
    spec = parse_spec(raw)
    result = run(spec)
    point = result.checkpoint_at(0.05)
    layout = perturb.Layout(
        cell_ids=("1",),
        membrane_ids=("m1", "m2", "m3"),
        environment_ids=("bath",),
        ion_ids=("Na", "K", "P"),
        membrane_cell_ids=("1",) * 3,
        membrane_environment_ids=("bath",) * 3,
        boundary_cell_occurrences=("1",),
        membrane_area_m2=np.array([1e-12, 2e-12, 3e-12]),
        cell_volume_m3=np.array([2e-15]),
        environment_parameter_volume_m3=1e-12,
        environment_mode="matrix",
        provenance=dict(test="explicit independent perturbation binding"),
    )
    binding = perturb.bind_layout(layout)
    return spec, point, result, layout, binding


def stream(binding, engine="native"):
    rng = (
        perturb.native_stream(17)
        if engine == "native"
        else perturb.StableCoordinates(17, 2**32 + 7)
    )
    value = streams.new_stream(
        binding, rng, stream_id="physiology", world_id=2**32 + 7, next_tick=100
    )
    _, value = streams.draw(value, binding, site="microtubule_gaussian")
    _, value = streams.draw(value, binding, site="static_K")
    return value


def write_json(path, value):
    import json

    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def rehash_outer(root, manifest=None):
    manifest = read_json(root / "manifest.json") if manifest is None else manifest
    files = paired.COMPLETE_FILES if manifest["kind"] == paired.COMPLETE_KIND else paired.FILES
    manifest["files"] = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files
    }
    manifest["identity"] = digest(
        {key: value for key, value in manifest.items() if key != "identity"}
    )
    write_json(root / "manifest.json", manifest)


@pytest.mark.parametrize("engine", ["native", "stable"])
def test_paired_restore_preserves_complete_state_and_future_packets(tmp_path, setup, engine):
    spec, point, uninterrupted, _, binding = setup
    current = stream(binding, engine)
    if engine == "native":
        assert perturb.native_stream_manifest(current.rng)["state"][3] == 1
    original = streams.stream_record(current)
    root = paired.write_physiology_checkpoint(tmp_path / "paired", spec, point, current, binding)
    loaded = paired.load_physiology_checkpoint(
        root, binding, expected_stream_id="physiology", expected_world_id=2**32 + 7
    )
    assert streams.stream_record(loaded.stream) == original == streams.stream_record(current)
    assert loaded.stream.next_tick == 102 and loaded.snapshot.checkpoint.step_index == 1
    assert loaded.snapshot.checkpoint.time == 0.05
    for actual, expected in zip(
        (*loaded.snapshot.checkpoint.state, *loaded.snapshot.checkpoint.layout),
        (*point.state, *point.layout),
        strict=True,
    ):
        np.testing.assert_array_equal(np.asarray(actual), np.asarray(expected), strict=True)
    saved_stream = loaded.stream
    for site in ("microtubule_gaussian", "protein_flux", "boundary_choice", "static_K"):
        expected, current = streams.draw(current, binding, site=site)
        actual, saved_stream = streams.draw(saved_stream, binding, site=site)
        assert perturb.draw_manifest(actual, binding) == perturb.draw_manifest(expected, binding)
        assert streams.stream_record(saved_stream) == streams.stream_record(current)
    continued = run(loaded.snapshot.spec, loaded.snapshot.checkpoint)
    for actual, expected in zip(continued.final.state, uninterrupted.final.state, strict=True):
        np.testing.assert_array_equal(np.asarray(actual), np.asarray(expected), strict=True)
    # Numeric integration does not silently consume unrelated RNG or turn the
    # deterministic parent model into a stochastic physiology model.
    assert streams.stream_record(loaded.stream) == original
    inner = load_snapshot(root / "snapshot")
    assert inner.fingerprint == loaded.snapshot.fingerprint
    assert read_json(root / "snapshot/manifest.json")["random_state"] is None


@pytest.mark.parametrize(
    "defect",
    [
        "payload",
        "numeric_bytes",
        "missing",
        "extra",
        "failure",
        "clock",
        "clock_type",
        "world",
        "tick_type",
        "mixed_numeric",
        "mixed_stream",
    ],
)
def test_corrupt_or_mixed_pair_is_refused(tmp_path, setup, defect):
    spec, point, result, _, binding = setup
    current = stream(binding)
    root = paired.write_physiology_checkpoint(tmp_path / "paired", spec, point, current, binding)
    manifest = read_json(root / "manifest.json")
    if defect == "payload":
        raw = read_json(root / "stream.json")
        raw["next_tick"] += 1
        write_json(root / "stream.json", raw)
    elif defect == "numeric_bytes":
        with (root / "snapshot/state.npz").open("ab") as handle:
            handle.write(b"changed")
    elif defect == "missing":
        (root / "stream.json").unlink()
    elif defect == "extra":
        (root / "unrecorded.json").write_text("{}")
    elif defect == "failure":
        (root / "failure.json").write_text("{}")
    elif defect == "clock":
        manifest["clock"]["step_index"] += 1
        rehash_outer(root, manifest)
    elif defect == "clock_type":
        manifest["clock"]["event_index"] = False
        rehash_outer(root, manifest)
    elif defect == "world":
        manifest["world_id"] += 1
        rehash_outer(root, manifest)
    elif defect == "tick_type":
        manifest["next_tick"] = True
        rehash_outer(root, manifest)
    elif defect == "mixed_numeric":
        other = write_snapshot(tmp_path / "other", spec, result.final)
        for name in ("state.npz", "manifest.json"):
            (root / "snapshot" / name).write_bytes((other / name).read_bytes())
        rehash_outer(root)
    else:
        _, another = streams.draw(current, binding, site="protein_flux")
        write_json(root / "stream.json", streams.stream_record(another))
        rehash_outer(root)
    with pytest.raises((ConfigError, ValueError)):
        paired.load_physiology_checkpoint(root, binding)


@pytest.mark.parametrize(
    "expected",
    [dict(expected_world_id=7), dict(expected_world_id=True), dict(expected_stream_id="foreign")],
)
def test_callers_expected_owner_is_checked(tmp_path, setup, expected):
    spec, point, _, _, binding = setup
    current = stream(binding)
    root = paired.write_physiology_checkpoint(tmp_path / "paired", spec, point, current, binding)
    with pytest.raises(ConfigError, match="another world|another stream"):
        paired.load_physiology_checkpoint(root, binding, **expected)


def test_foreign_layout_refuses_both_restore_and_write_without_consuming_rng(tmp_path, setup):
    spec, point, _, layout, binding = setup
    current = stream(binding)
    before = streams.stream_record(current)
    root = paired.write_physiology_checkpoint(tmp_path / "paired", spec, point, current, binding)
    changed = perturb.bind_layout(replace(layout, membrane_ids=("foreign", "m2", "m3")))
    with pytest.raises(ValueError):
        paired.load_physiology_checkpoint(root, changed)
    with pytest.raises(ValueError):
        paired.write_physiology_checkpoint(tmp_path / "refused", spec, point, current, changed)
    assert not (tmp_path / "refused").exists()
    assert streams.stream_record(current) == before


def component(binding, engine="native", *, dynamic_level=3e-8):
    controls = perturb.Controls("SIM", "normal", True, True, 2.0, dynamic_level, 0.002)
    value = step.initialise(
        binding,
        controls,
        perturb.ProteinState(np.array([8.0]), np.array([6.0] * 3), np.array([5.0])),
        np.array([[1e-18, 2e-18, 3e-18]] * 3),
        stream(binding, engine),
    )
    # Preserve a pending signed modifier and the distinct pre-noise base. Its
    # effect becomes current only at the next explicit SIM finalization.
    return replace(
        value,
        diffusion=value.diffusion._replace(scheduled_m2_s=-0.25 * value.diffusion.base_m2_s),
    )


def assert_same_component(actual, expected):
    assert actual.controls == expected.controls
    assert actual.time_s == expected.time_s
    assert actual.loop_calls == expected.loop_calls
    assert streams.stream_record(actual.stream) == streams.stream_record(expected.stream)
    for restored, original in zip(
        (*actual.protein, *actual.diffusion), (*expected.protein, *expected.diffusion), strict=True
    ):
        np.testing.assert_array_equal(restored, original, strict=True)
        assert restored.dtype == np.dtype("float64") and not restored.flags.writeable


@pytest.mark.parametrize("engine", ["native", "stable"])
@pytest.mark.parametrize("completed_calls", [0, 3])
def test_complete_component_restart_preserves_material_controls_and_future_updates(
    tmp_path, setup, engine, completed_calls
):
    spec, point, numeric, _, binding = setup
    current = component(binding, engine)
    for _ in range(completed_calls):
        current = step.advance(current, binding).state
    root = paired.write_physiology_checkpoint(
        tmp_path / "complete", spec, point, current.stream, binding, component_state=current
    )
    loaded = paired.load_physiology_checkpoint(root, binding, require_component=True)
    restored = loaded.component_state
    assert_same_component(restored, current)
    assert restored.stream is loaded.stream
    manifest = read_json(root / "manifest.json")
    assert manifest["kind"] == paired.COMPLETE_KIND
    assert set(manifest["files"]) == paired.COMPLETE_FILES
    assert manifest["component_clock"] == dict(
        elapsed_time_s=current.time_s, loop_calls=completed_calls, policy=paired.CLOCK_POLICY
    )
    # Explicitly independent clocks: this test does not claim coupled tissue
    # integration. No reinitialization or clock-derived random tick on restore.
    assert loaded.snapshot.checkpoint.time == 0.05 != restored.time_s
    assert restored.stream.next_tick == 103 + completed_calls
    if engine == "native":
        assert perturb.native_stream_manifest(restored.stream.rng)["state"][3] == 1
    for _ in range(completed_calls, 7):
        expected = step.advance(current, binding)
        actual = step.advance(restored, binding)
        assert perturb.draw_manifest(actual.packet, binding) == perturb.draw_manifest(
            expected.packet, binding
        )
        assert dict(actual.diagnostics) == dict(expected.diagnostics)
        assert_same_component(actual.state, expected.state)
        current, restored = expected.state, actual.state
    assert restored.loop_calls == 7
    continued = run(loaded.snapshot.spec, loaded.snapshot.checkpoint)
    for actual, expected in zip(continued.final.state, numeric.final.state, strict=True):
        np.testing.assert_array_equal(np.asarray(actual), np.asarray(expected), strict=True)


def rehash_component(root, record):
    replay = record["replay"]
    replay["identity"] = digest({key: value for key, value in replay.items() if key != "identity"})
    record["identity"] = digest({key: value for key, value in record.items() if key != "identity"})
    write_json(root / "component.json", record)
    manifest = read_json(root / "manifest.json")
    manifest["component_identity"] = record["identity"]
    rehash_outer(root, manifest)


@pytest.mark.parametrize(
    "defect",
    [
        "missing_buffer",
        "owner_shape",
        "negative_protein",
        "negative_permeability",
        "controls",
        "mixed_rng",
        "mixed_tick",
        "loop_count_type",
        "clock_policy",
        "component_clock",
        "component_identity",
        "payload",
        "missing_file",
    ],
)
def test_complete_component_integrity_and_domains_are_checked(tmp_path, setup, defect):
    spec, point, _, _, binding = setup
    state = component(binding)
    root = paired.write_physiology_checkpoint(
        tmp_path / "complete", spec, point, state.stream, binding, component_state=state
    )
    record = read_json(root / "component.json")
    replay = record["replay"]
    if defect == "missing_buffer":
        replay["protein"].pop("membrane_mol_m3")
    elif defect == "owner_shape":
        replay["protein"]["membrane_mol_m3"] = [6.0]
    elif defect == "negative_protein":
        replay["protein"]["cell_mol_m3"][0] = -1.0
    elif defect == "negative_permeability":
        replay["diffusion"]["current_m2_s"][0][0] = -1e-18
    elif defect == "controls":
        replay["controls"]["dynamic_enabled"] = 1
    elif defect == "mixed_rng":
        replay["rng"] = perturb.native_stream_manifest(perturb.native_stream(19))
    elif defect == "mixed_tick":
        replay["tick"] += 1
    elif defect == "loop_count_type":
        record["loop_calls"] = False
    elif defect == "clock_policy":
        record["clock_policy"] = "inferred_from_numeric_steps"
    elif defect in ("component_clock", "component_identity"):
        manifest = read_json(root / "manifest.json")
        if defect == "component_clock":
            manifest["component_clock"]["elapsed_time_s"] = 0.05
        else:
            manifest["component_identity"] = "0" * 64
        rehash_outer(root, manifest)
    elif defect == "payload":
        replay["protein"]["cell_mol_m3"][0] += 1
        write_json(root / "component.json", record)
    elif defect == "missing_file":
        (root / "component.json").unlink()
    if defect not in ("component_clock", "component_identity", "payload", "missing_file"):
        # Even repinned file hashes must not bypass schema, ownership, physical
        # domains or association with the outer RNG and component clock.
        rehash_component(root, record)
    with pytest.raises((ConfigError, ValueError)):
        paired.load_physiology_checkpoint(root, binding, require_component=True)


def test_required_material_state_is_never_inferred_from_rng_only_checkpoint(tmp_path, setup):
    spec, point, _, _, binding = setup
    current = stream(binding)
    root = paired.write_physiology_checkpoint(tmp_path / "rng_only", spec, point, current, binding)
    assert paired.load_physiology_checkpoint(root, binding).component_state is None
    with pytest.raises(ConfigError, match="RNG-only"):
        paired.load_physiology_checkpoint(root, binding, require_component=True)


def test_component_with_another_stream_is_refused_before_publication(tmp_path, setup):
    spec, point, _, _, binding = setup
    current = component(binding)
    _, another = streams.draw(current.stream, binding, site="protein_flux")
    root = tmp_path / "mixed"
    with pytest.raises(ConfigError, match="another stream"):
        paired.write_physiology_checkpoint(
            root, spec, point, another, binding, component_state=current
        )
    assert not root.exists()


@pytest.mark.parametrize("engine", ["native", "stable"])
def test_rejected_next_trial_leaves_a_restartable_accepted_prefix(tmp_path, setup, engine):
    spec, point, _, _, binding = setup
    current = step.advance(component(binding, engine), binding).state
    attempted = replace(current, controls=replace(current.controls, dynamic_level_mol_m2_s=1e12))
    before = paired._component_record(current, binding, current.stream)
    with pytest.raises(step.PerturbationRejected) as failure:
        step.advance(attempted, binding)
    rejected = failure.value
    assert rejected.stage == "protein_trial" and rejected.packet is not None
    assert rejected.stream.next_tick == current.stream.next_tick + 1
    assert any(np.any(value < 0) for value in rejected.trial.protein)
    assert paired._component_record(current, binding, current.stream) == before
    root = paired.write_physiology_checkpoint(
        tmp_path / "accepted", spec, point, current.stream, binding, component_state=current
    )
    restored = paired.load_physiology_checkpoint(
        root, binding, require_component=True
    ).component_state
    assert_same_component(restored, current)
    # Continuing the accepted branch samples the same packet as the refused
    # attempt, since no proposed random state was silently committed.
    continued = step.advance(restored, binding)
    assert perturb.draw_manifest(continued.packet, binding) == perturb.draw_manifest(
        rejected.packet, binding
    )
    assert_same_component(continued.state, step.advance(current, binding).state)


def test_existing_bundle_is_never_overwritten(tmp_path, setup):
    spec, point, _, _, binding = setup
    current = stream(binding)
    root = paired.write_physiology_checkpoint(tmp_path / "paired", spec, point, current, binding)
    before = {name: (root / name).read_bytes() for name in paired.FILES | {"manifest.json"}}
    with pytest.raises(FileExistsError):
        paired.write_physiology_checkpoint(root, spec, point, current, binding)
    assert {name: (root / name).read_bytes() for name in before} == before


@pytest.mark.parametrize("cause", ["invalid_clock", "publication_error", "source_change"])
def test_failed_publication_retains_failure_and_never_commits_pair(
    tmp_path, setup, monkeypatch, cause
):
    spec, point, _, _, binding = setup
    current = stream(binding)
    before = streams.stream_record(current)
    if cause == "invalid_clock":
        point = replace(point, time=0.037)
    elif cause == "publication_error":

        def fail(*args):
            raise RuntimeError("Synthetic numeric publication failure")

        monkeypatch.setattr(paired, "write_snapshot", fail)
    else:
        monkeypatch.setattr(paired, "source_hashes", lambda: {})
    root = tmp_path / "failed"
    with pytest.raises((ConfigError, RuntimeError)):
        paired.write_physiology_checkpoint(root, spec, point, current, binding)
    assert (root / "failure.json").exists() and not (root / "manifest.json").exists()
    with pytest.raises(ConfigError, match="Failed physiological"):
        paired.load_physiology_checkpoint(root, binding)
    assert streams.stream_record(current) == before
