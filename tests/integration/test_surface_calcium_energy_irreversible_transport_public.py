"""Public irreversible-transport interfaces; full physical comparisons are separate."""

from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from cells.core import surface_calcium_energy_irreversible_transport_spec as schema
from cells.core.batch import BatchSpec, WorldSpec, parse_batch
from cells.core.runner import timeline, validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import Checkpoint
from cells.core.windows import WindowPolicy, iter_windows
from cells.ensemble.ionic import parse_spec as parse_worlds
from cells.io import load_snapshot, write_snapshot
from cells.models import surface_calcium_energy_irreversible_transport as model
from cells.models import surface_calcium_energy_transport as reversible
from cells.models.registry import get_model
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_kinetic import exact
from validation.tissue import calcium_energy_network_transport_fixtures as prior_fixtures


def definition(*, backend="cpu", jit=True, padded=True):
    """Manufactured public-interface case; work is an explicit external supply."""
    raw = prior_fixtures.compact_probe(backend=backend, padded=padded)
    raw["model"]["id"] = schema.MODEL_ID
    block = raw["model"]["network_transport"]
    block["accounting"] = schema.ACCOUNTING
    for i, route in enumerate(block["routes"]):
        route["configuration"]["standard free energy"] = None if i % 2 == 0 else "None"
        route["drive"]["supplied_energy_J_per_mol"] = 50000.0
    raw["execution"]["jit"] = jit
    return raw


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
def test_public_roundtrip_controls_registry_and_world_admission(backend):
    raw = definition(backend=backend)
    spec = parse_spec(raw)
    assert type(spec.model) is schema.SurfaceCalciumEnergyIrreversibleTransportModel
    assert get_model(spec.model) is model
    assert parse_spec(spec.to_dict()) == spec
    assert [r.configuration["standard free energy"] for r in spec.model.network_transporters] == [
        None,
        "None",
        None,
        "None",
    ]
    assert all(
        r.drive.supplied_energy_J_per_mol == 50000.0 for r in spec.model.network_transporters
    )
    assert len(model.STATE_TYPE._fields) == 44
    table = control_values(spec, [0.0, 13.3e-6, 31.1e-6])
    assert type(table) is schema.Control
    index = [r.id for r in spec.model.network_transporters].index("na_drive")
    np.testing.assert_array_equal(table.network_transport[:, index], [0.8, 0.0, 0.6])
    np.testing.assert_array_equal(
        table.network_transport[:, len(spec.model.network_transporters) :], 0.0
    )
    inherited = control_values(schema.base_spec(spec), [0.0, 13.3e-6, 31.1e-6])
    for field in inherited._fields:
        np.testing.assert_array_equal(getattr(table, field), getattr(inherited, field), strict=True)
    assert {0.0, 13.3e-6, 31.1e-6} <= set(timeline(spec))
    worlds = parse_worlds(dict(model="ionic_worlds@1", simulation=raw, worlds=2, window_steps=256))
    assert worlds.simulation == spec
    batch = BatchSpec((WorldSpec(7, spec), WorldSpec(79, spec)), 2, 2048, 2**32)
    assert parse_batch(batch.to_dict()) == batch
    previous = parse_spec(prior_fixtures.compact_probe(backend=backend))
    assert get_model(previous.model) is reversible
    with pytest.raises(ConfigError, match="model family"):
        parse_batch(
            BatchSpec((WorldSpec(7, spec), WorldSpec(9, previous)), 2, 2048, 2**32).to_dict()
        )
    evidence(
        "irreversible-public-admission-" + backend,
        dict(
            definition=spec.to_dict(),
            host_admission_only=True,
            GPU_or_compiled_execution=False,
            complete_state_fields=list(model.STATE_TYPE._fields),
            source_energy_forms_preserved=True,
        ),
    )


def test_complete_initial_snapshot_retains_44_fields_and_rejects_reversible_layout(tmp_path):
    spec = parse_spec(definition(jit=False))
    state, layout = model.initial_values(spec)
    point = Checkpoint(state, layout, 0.0, 0, event_index(spec, 0.0))
    path = write_snapshot(tmp_path / "complete", spec, point)
    restored = load_snapshot(path)
    assert restored.spec == spec
    assert type(restored.checkpoint.state) is model.STATE_TYPE
    assert type(restored.checkpoint.layout) is model.LAYOUT_TYPE
    exact(restored.checkpoint.state, point.state)
    exact(restored.checkpoint.layout, point.layout)
    with np.load(path / "state.npz", allow_pickle=False) as arrays:
        assert set(arrays.files) == set(state._fields) | set(layout._fields)
        for key, value in state._asdict().items():
            np.testing.assert_array_equal(arrays[key], value, strict=True)
    parent = parse_spec(prior_fixtures.compact_probe())
    _, parent_layout = reversible.initial_values(parent)
    with pytest.raises(ConfigError, match="state/layout|types"):
        validate_checkpoint(spec, replace(point, layout=parent_layout))
    changed = deepcopy(spec.to_dict())
    changed["model"]["id"] = prior_fixtures.MODEL_ID
    with pytest.raises(ConfigError):
        parse_spec(changed)
    evidence(
        "irreversible-public-snapshot",
        dict(
            definition=spec.to_dict(),
            state_fields=list(state._fields),
            portable_restart_fields=True,
            numerical_trajectory=False,
        ),
    )


def test_actual_guarded_window_restart_preserves_work_and_heat_history(tmp_path):
    raw = definition(jit=False, padded=False)
    dt = raw["execution"]["dt"]
    # Keep the complete original recipe and controls. Only execute its first
    # two accepted windows here; this is a public restart probe, not convergence.
    spec = parse_spec(raw)
    iterator = iter_windows(spec, WindowPolicy(1, "full"))
    first, expected = next(iterator), next(iterator)
    iterator.close()
    assert first.final.time == dt and expected.final.time == 2 * dt
    saved = load_snapshot(write_snapshot(tmp_path / "middle", spec, first.final))
    iterator = iter_windows(saved.spec, WindowPolicy(1, "full"), saved.checkpoint)
    actual = next(iterator)
    iterator.close()
    exact(actual.final.state, expected.final.state)
    exact(actual.final.layout, expected.final.layout)
    exact(actual.history, expected.history)
    baseline_times = np.concatenate((first.observations.times, expected.observations.times))
    selected = baseline_times >= dt
    for key in vars(expected.observations):
        baseline = np.concatenate(
            (getattr(first.observations, key), getattr(expected.observations, key)), axis=0
        )
        np.testing.assert_array_equal(
            getattr(actual.observations, key), baseline[selected], strict=True
        )
    state = actual.final.state
    assert len(state) == 44
    assert np.any(state.network_cycles_fmol != 0)
    assert np.any(state.network_supplied_work_pJ != 0)
    assert np.any(state.network_dissipated_energy_pJ > 0)
    assert np.any(state.energy_amount_increment_fmol != 0)
    for result in (first, expected, actual):
        assert result.timings["compile_or_cache_seconds"] == 0
    evidence(
        "irreversible-public-window-restart",
        dict(
            definition=spec.to_dict(),
            duration_s=2 * dt,
            complete_restart_exact=True,
            full_trajectory_credit=False,
            GPU_or_compiled_execution=False,
        ),
        {"state__" + key: np.asarray(value) for key, value in state._asdict().items()},
    )
