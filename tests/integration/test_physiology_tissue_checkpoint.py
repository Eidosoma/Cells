"""Persist explicit tissue/component ownership without silently coupling their clocks."""

import hashlib
from dataclasses import replace

import numpy as np
import pytest

from cells import physiology_checkpoint as paired
from cells.core import physiology_perturbation_step as step
from cells.core import physiology_random_streams as streams
from cells.core import physiology_tissue_binding as tissue
from cells.core.schedule import event_index
from cells.core.specs import ConfigError, digest, parse_spec, read_json
from cells.core.state import Checkpoint
from cells.models.registry import get_model
from cells.processes import betse_perturbations as perturb
from tests.integration.test_physiology_checkpoint import assert_same_component, write_json
from tests.unit.test_physiology_tissue_binding import arguments, definition, evidence
from tests.unit.test_surface_kinetic import exact


def setup(kind="passive", engine="native"):
    raw = definition(kind)
    raw["execution"].update(jit=False)
    spec = parse_spec(raw)
    binding = tissue.bind_tissue(spec, **arguments(spec, reverse=True))
    numeric, layout = get_model(spec.model).initial_values(spec)
    point = Checkpoint(numeric, layout, 0.0, 0, event_index(spec, 0.0))
    component = binding.component
    rng = perturb.native_stream(17) if engine == "native" else perturb.StableCoordinates(17, 79)
    stream = streams.new_stream(component, rng, stream_id="tissue-physiology", world_id=79)
    _, stream = streams.draw(stream, component, site="microtubule_gaussian")
    controls = perturb.Controls("SIM", "normal", True, True, 2.0, 3e-8, 0.002)
    state = step.initialise(
        component,
        controls,
        perturb.ProteinState(
            np.full(len(component.cell_ids), 8.0),
            np.full(len(component.membrane_ids), 6.0),
            np.full(len(component.environment_ids), 5.0),
        ),
        tissue.initial_diffusion(binding),
        stream,
    )
    state = replace(
        state, diffusion=state.diffusion._replace(scheduled_m2_s=-0.25 * state.diffusion.base_m2_s)
    )
    return spec, point, binding, state


def save(path, spec, point, binding, state):
    return paired.write_physiology_checkpoint(
        path,
        spec,
        point,
        state.stream,
        binding.component,
        component_state=state,
        tissue_binding=binding,
    )


def reseal(root, manifest=None):
    manifest = read_json(root / "manifest.json") if manifest is None else manifest
    manifest["files"] = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in paired.BOUND_FILES
    }
    manifest["identity"] = digest({k: v for k, v in manifest.items() if k != "identity"})
    write_json(root / "manifest.json", manifest)


@pytest.mark.parametrize("kind", ["passive", "ionic", "calcium", "fuel"])
@pytest.mark.parametrize("engine", ["native", "stable"])
def test_actual_tissue_binding_and_six_buffers_restore_with_exact_component_continuation(
    tmp_path, kind, engine
):
    spec, point, binding, state = setup(kind, engine)
    for _ in range(3):
        state = step.advance(state, binding.component).state
    root = save(tmp_path / "bound", spec, point, binding, state)
    restored = paired.load_physiology_checkpoint(
        root,
        binding.component,
        expected_stream_id="tissue-physiology",
        expected_world_id=79,
        require_component=True,
        require_tissue_binding=True,
    )
    assert tissue.binding_record(restored.tissue_binding) == tissue.binding_record(binding)
    assert_same_component(restored.component_state, state)
    exact(restored.snapshot.checkpoint.state, point.state)
    exact(restored.snapshot.checkpoint.layout, point.layout)
    assert restored.snapshot.spec == spec
    assert restored.snapshot.checkpoint.time == 0.0
    assert restored.component_state.time_s == 0.006
    assert restored.component_state.stream is restored.stream
    manifest = read_json(root / "manifest.json")
    assert manifest["kind"] == paired.BOUND_KIND
    assert set(manifest["files"]) == paired.BOUND_FILES
    assert manifest["tissue_binding_identity"] == binding.identity
    actual = restored.component_state
    for _ in range(4):
        state = step.advance(state, binding.component).state
        actual = step.advance(actual, restored.tissue_binding.component).state
        assert_same_component(actual, state)
        expected_p = tissue.component_permeability(state, binding)
        actual_p = tissue.component_permeability(actual, restored.tissue_binding)
        for key in ("current_m_s", "base_m_s", "scheduled_m_s"):
            np.testing.assert_array_equal(
                getattr(actual_p, key), getattr(expected_p, key), strict=True
            )
    evidence(
        "checkpoint-" + kind + "-" + engine,
        dict(
            definition=spec.to_dict(),
            binding=tissue.binding_record(binding),
            exact_numeric_snapshot=True,
            component_calls_before_save=3,
            exact_continued_component_calls=4,
            numeric_clock_s=0.0,
            automatic_tissue_coupling=False,
        ),
        {"protein__" + k: v for k, v in state.protein._asdict().items()}
        | {"diffusion__" + k: v for k, v in state.diffusion._asdict().items()},
    )


@pytest.mark.parametrize(
    "defect",
    [
        "bytes",
        "missing",
        "extra",
        "identity",
        "geometry",
        "thickness",
        "axes",
        "definition",
        "mixed",
    ],
)
def test_corrupt_or_resealed_binding_cannot_change_physical_ownership(tmp_path, defect):
    spec, point, binding, state = setup()
    root = save(tmp_path / "bound", spec, point, binding, state)
    manifest = read_json(root / "manifest.json")
    record = read_json(root / "binding.json")
    if defect == "bytes":
        record["inputs"]["provenance"]["revision"] += 1
        write_json(root / "binding.json", record)
    elif defect == "missing":
        (root / "binding.json").unlink()
    elif defect == "extra":
        write_json(root / "unrecorded.json", {})
    elif defect == "identity":
        manifest["tissue_binding_identity"] = "0" * 64
        reseal(root, manifest)
    else:
        if defect == "geometry":
            record["geometry"]["cell_volume_m3"][0] *= 2
        elif defect == "thickness":
            record["membrane_thickness_m"][0] *= 2
        elif defect == "axes":
            record["slot_maps"]["membrane"].reverse()
        elif defect == "definition":
            record["source_definition_sha256"] = "0" * 64
        else:
            inputs = arguments(spec, reverse=True)
            inputs["provenance"]["revision"] = 2
            record = tissue.binding_record(tissue.bind_tissue(spec, **inputs))
        record["identity"] = digest({k: v for k, v in record.items() if k != "identity"})
        write_json(root / "binding.json", record)
        manifest["tissue_binding_identity"] = record["identity"]
        reseal(root, manifest)
    before = streams.stream_record(state.stream)
    with pytest.raises((ConfigError, ValueError)):
        paired.load_physiology_checkpoint(root, binding.component)
    assert streams.stream_record(state.stream) == before


@pytest.mark.parametrize("complete", [False, True])
def test_legacy_pair_remains_loadable_but_cannot_satisfy_required_tissue_binding(
    tmp_path, complete
):
    spec, point, binding, state = setup()
    root = paired.write_physiology_checkpoint(
        tmp_path / "legacy",
        spec,
        point,
        state.stream,
        binding.component,
        component_state=state if complete else None,
    )
    assert paired.load_physiology_checkpoint(root, binding.component).tissue_binding is None
    for kwargs in (dict(require_tissue_binding=True), dict(tissue_binding=binding)):
        with pytest.raises(ConfigError, match="unbound checkpoint"):
            paired.load_physiology_checkpoint(root, binding.component, **kwargs)


@pytest.mark.parametrize("defect", ["no-material", "changed-spec", "foreign-component"])
def test_invalid_binding_association_refuses_before_publication_or_draw(tmp_path, defect):
    spec, point, binding, state = setup()
    component = binding.component
    if defect == "changed-spec":
        raw = spec.to_dict()
        raw["execution"]["max_steps"] += 1
        spec = parse_spec(raw)
    elif defect == "foreign-component":
        component = tissue.bind_tissue(spec, **arguments(spec)).component
    before = streams.stream_record(state.stream)
    with pytest.raises((ConfigError, ValueError)):
        paired.write_physiology_checkpoint(
            tmp_path / "refused",
            spec,
            point,
            state.stream,
            component,
            component_state=None if defect == "no-material" else state,
            tissue_binding=binding,
        )
    assert not (tmp_path / "refused").exists()
    assert streams.stream_record(state.stream) == before


def test_explicit_expected_binding_and_no_implicit_component_work(tmp_path, monkeypatch):
    spec, point, binding, state = setup()
    before = streams.stream_record(state.stream)
    # Keep distinct current/base/scheduled buffers at initialization: a silent
    # SIM finalization here would discard the saved static permeability change.
    assert not np.array_equal(
        state.diffusion.current_m2_s, state.diffusion.base_m2_s + state.diffusion.scheduled_m2_s
    )

    def forbidden(*args, **kwargs):
        pytest.fail("Checkpoint binding must not draw, initialize, finalize or advance")

    with monkeypatch.context() as guarded:
        for module, name in (
            (streams, "draw"),
            (step, "initialise"),
            (step, "advance"),
            (perturb, "finalize_scheduled"),
        ):
            guarded.setattr(module, name, forbidden)
        root = save(tmp_path / "bound", spec, point, binding, state)
        restored = paired.load_physiology_checkpoint(
            root, binding.component, tissue_binding=binding
        )
    assert_same_component(restored.component_state, state)
    assert streams.stream_record(state.stream) == before
    inputs = arguments(spec, reverse=True)
    inputs["membrane_thickness_m"][spec.model.membranes[0].id] *= 2
    other = tissue.bind_tissue(spec, **inputs)
    with pytest.raises(ConfigError, match="binding"):
        paired.load_physiology_checkpoint(root, binding.component, tissue_binding=other)


def test_binding_requirement_must_be_an_explicit_boolean(tmp_path):
    spec, point, binding, state = setup()
    root = save(tmp_path / "bound", spec, point, binding, state)
    with pytest.raises(ConfigError, match="booleans"):
        paired.load_physiology_checkpoint(root, binding.component, require_tissue_binding=1)
