"""Open calcium/fuel public ownership, full-array snapshots and guarded restart.

These short probes qualify interfaces. Component stage/reference checks and
full physical trajectories have separate evidence and acceptance scopes.
"""

import json
from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from cells.core.batch import BatchSpec, WorldSpec, parse_batch
from cells.core.runner import branch_checkpoint, timeline, validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import initialise
from cells.core.windows import WindowPolicy, iter_windows
from cells.ensemble.ionic import parse_spec as parse_worlds
from cells.io import load_snapshot, write_snapshot
from cells.models.registry import get_model
from tests.integration.test_surface_bath_events_public import invoke
from tests.surface_open_calcium_fixtures import OWNERS, PREFIX_DT, definition, prefix
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_kinetic import exact
from validation.tissue import open_calcium_fixtures as fixtures


def arrays_and_observations(model, spec, point):
    state = model.STATE_TYPE(*(np.asarray(v) for v in point.state))
    layout = model.LAYOUT_TYPE(*(np.asarray(v) for v in point.layout))
    inside, outside = model.physical_amounts(state, layout)
    history = model.STATE_TYPE(*(v[None] for v in state))
    observed = model.observe_history(np.asarray([point.time]), history, layout, [point.time], spec)
    return {
        group + "_" + key: np.asarray(value)
        for group, values in (
            ("state", state._asdict()),
            ("layout", layout._asdict()),
            ("physical", dict(inside_fmol=inside, outside_fmol=outside)),
            ("observed", vars(observed)),
        )
        for key, value in values.items()
    }


def export_restored_snapshot(snapshot, output):
    """Fresh interpreter entrypoint; no original input file is required."""
    saved = load_snapshot(snapshot)
    model = get_model(saved.spec.model)
    assert type(saved.checkpoint.state) is model.STATE_TYPE
    assert type(saved.checkpoint.layout) is model.LAYOUT_TYPE
    np.savez(output, **arrays_and_observations(model, saved.spec, saved.checkpoint))
    print(
        json.dumps(
            dict(
                definition=saved.spec.to_dict(),
                time=saved.checkpoint.time,
                state_fields=list(model.STATE_TYPE._fields),
                layout_fields=list(model.LAYOUT_TYPE._fields),
            )
        )
    )


@pytest.mark.parametrize("family", OWNERS)
def test_open_calcium_public_routes_controls_and_complete_snapshot(tmp_path, family):
    schema, model, spec, point = prefix(family)
    assert get_model(spec.model) is model
    assert parse_spec(spec.to_dict()) == spec
    assert len(point.state) == OWNERS[family][2]
    assert len({channel.kinetic_law for channel in spec.model.channels}) == 56
    assert spec.experiment.end_time == fixtures.END
    table = [0.0, PREFIX_DT, 2 * PREFIX_DT, *spec.experiment.observation_times]
    exact(control_values(spec, table), control_values(schema.equation_spec(spec), table))
    initial = initialise(spec)
    exact(point.layout, initial.layout)
    active_outside = np.asarray(point.layout.outside_active)
    reservoir = np.asarray(point.layout.reservoir)
    assert np.any(reservoir & active_outside)
    assert np.any(~reservoir & active_outside)
    np.testing.assert_array_equal(point.state.extracellular_amount_increment[:, reservoir], 0.0)
    assert np.any(point.state.reservoir_supplied[:, reservoir] != 0)
    assert np.any(point.state.electrode_charge_transferred_C != 0)
    assert np.any(point.state.reservoir_work_pJ != 0)
    if family == "energy":
        assert np.any(point.state.energy_amount_increment_fmol != 0)
    saved = load_snapshot(write_snapshot(tmp_path / "prefix", spec, point))
    assert saved.spec == spec
    exact(saved.checkpoint.state, point.state)
    exact(saved.checkpoint.layout, point.layout)
    bad = replace(
        point,
        layout=point.layout._replace(
            open_ionic_moiety_ceiling_fmol=point.layout.open_ionic_moiety_ceiling_fmol * 1.01,
        ),
    )
    with pytest.raises(ConfigError, match="layout"):
        validate_checkpoint(spec, bad)
    # The private equation view is not an admitted closed-family simulation.
    with pytest.raises(ConfigError):
        parse_spec(schema.equation_spec(spec).to_dict())
    closed = parse_spec(fixtures.original_definition(fixtures.definition(family, "empty")))
    with pytest.raises(ConfigError, match="types"):
        validate_checkpoint(
            closed,
            replace(point, event_index=event_index(closed, PREFIX_DT)),
            times=np.asarray([0.0, PREFIX_DT]),
        )
    changed = deepcopy(spec.to_dict())
    name = next(iter(changed["model"]["ionic_moiety_ceiling_fmol"]))
    changed["model"]["ionic_moiety_ceiling_fmol"][name] *= 1.01
    with pytest.raises(ConfigError, match="model"):
        branch_checkpoint(spec, point, parse_spec(changed))
    mixed = BatchSpec((WorldSpec(3, spec), WorldSpec(71, closed)), 2, 512, 2**30)
    with pytest.raises(ConfigError, match="model family"):
        parse_batch(mixed.to_dict())
    evidence(
        "open-calcium-public-prefix-" + family,
        dict(
            definition=spec.to_dict(),
            state_fields=list(point.state._fields),
            layout_fields=list(point.layout._fields),
            duration_s=PREFIX_DT,
            full_trajectory_credit=False,
        ),
        arrays_and_observations(model, spec, point),
    )


@pytest.mark.parametrize("backend", ("cpu", "gpu"))
@pytest.mark.parametrize("family", OWNERS)
def test_open_calcium_public_world_admission(family, backend):
    raw = definition(family)
    raw["execution"]["backend"] = backend
    with pytest.raises(ValueError, match="JIT"):
        parse_worlds(dict(model="ionic_worlds@1", simulation=raw, worlds=2, window_steps=8))
    raw["execution"]["jit"] = True
    spec = parse_spec(raw)
    worlds = parse_worlds(dict(model="ionic_worlds@1", simulation=raw, worlds=2, window_steps=8))
    assert worlds.simulation == spec
    assert get_model(spec.model) is OWNERS[family][1]
    batch = BatchSpec((WorldSpec(3, spec), WorldSpec(71, spec)), 2, 512, 2**30)
    assert parse_batch(batch.to_dict()) == batch
    evidence(
        "open-calcium-public-admission-" + family + "-" + backend,
        dict(
            definition=raw,
            worlds=2,
            window_steps=8,
            host_admission_only=True,
            compiled_or_GPU_execution=False,
        ),
    )


@pytest.mark.parametrize("family", OWNERS)
def test_open_calcium_fresh_cli_and_complete_portable_snapshot(tmp_path, family):
    _, model, spec, point = prefix(family)
    config = tmp_path / "definition.json"
    config.write_text(json.dumps(spec.to_dict()))
    validated = invoke(tmp_path, "validate", ["-m", "cells", "validate", config])
    assert validated == dict(status="valid", steps=len(timeline(spec)) - 1, sha256=spec.fingerprint)
    snapshot = write_snapshot(tmp_path / "snapshot", spec, point)
    before = {path.name: path.read_bytes() for path in snapshot.iterdir()}
    config.unlink()
    restored = tmp_path / "restored.npz"
    result = invoke(
        tmp_path,
        "restore",
        [
            "-c",
            "from tests.integration.test_surface_open_calcium_public import "
            "export_restored_snapshot; import sys; export_restored_snapshot(*sys.argv[1:])",
            snapshot,
            restored,
        ],
    )
    assert result["definition"] == spec.to_dict()
    assert result["time"] == PREFIX_DT
    assert result["state_fields"] == list(model.STATE_TYPE._fields)
    assert result["layout_fields"] == list(model.LAYOUT_TYPE._fields)
    assert {path.name: path.read_bytes() for path in snapshot.iterdir()} == before
    expected = arrays_and_observations(model, spec, point)
    with np.load(restored, allow_pickle=False) as actual:
        assert set(actual.files) == set(expected)
        for key, value in expected.items():
            assert actual[key].dtype == value.dtype
            np.testing.assert_array_equal(actual[key], value, err_msg=key)
    evidence(
        "open-calcium-public-fresh-snapshot-" + family,
        dict(
            definition=spec.to_dict(),
            complete_state_layout_physical_observations_exact=True,
            full_trajectory_credit=False,
        ),
        expected,
    )


@pytest.mark.parametrize("family", OWNERS)
def test_open_calcium_actual_guarded_window_restart(tmp_path, family):
    spec = parse_spec(definition(family))
    model = OWNERS[family][1]
    assert spec.execution.jit is False
    iterator = iter_windows(spec, WindowPolicy(1, "full"))
    first, expected = next(iterator), next(iterator)
    iterator.close()
    assert first.final.time == PREFIX_DT
    assert expected.final.time == 2 * PREFIX_DT
    saved = load_snapshot(write_snapshot(tmp_path / "middle", spec, first.final))
    iterator = iter_windows(spec, WindowPolicy(1, "full"), saved.checkpoint)
    actual = next(iterator)
    iterator.close()
    exact(actual.final.state, expected.final.state)
    exact(actual.final.layout, expected.final.layout)
    exact(actual.history, expected.history)
    baseline_times = np.concatenate((first.observations.times, expected.observations.times))
    selected = baseline_times >= PREFIX_DT
    for name in vars(expected.observations):
        baseline = np.concatenate(
            (getattr(first.observations, name), getattr(expected.observations, name)),
            axis=0,
        )
        np.testing.assert_array_equal(
            getattr(actual.observations, name), baseline[selected], err_msg=name
        )
    for result in (first, expected, actual):
        assert result.timings["compile_or_cache_seconds"] == 0
        assert np.any(result.final.state.reservoir_supplied != 0)
        np.testing.assert_array_equal(
            result.final.state.extracellular_amount_increment[:, result.final.layout.reservoir], 0.0
        )
    evidence(
        "open-calcium-public-guarded-window-restart-" + family,
        dict(
            definition=spec.to_dict(),
            duration_s=2 * PREFIX_DT,
            complete_restart_exact=True,
            full_trajectory_credit=False,
            compiled_or_GPU_execution=False,
        ),
        arrays_and_observations(model, spec, actual.final),
    )
