"""Public finite-ATP transport interfaces and complete event-boundary restart."""

from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from cells.core import surface_calcium_energy_atp_transport_spec as schema
from cells.core.batch import BatchSpec, WorldSpec, parse_batch
from cells.core.runner import timeline, validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import Checkpoint
from cells.core.windows import WindowPolicy, iter_windows
from cells.ensemble.ionic import parse_spec as parse_worlds
from cells.io import load_snapshot, write_snapshot
from cells.models import surface_calcium_energy_atp_transport as model
from cells.models import surface_calcium_energy_transport as maintained
from cells.models.registry import get_model
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_kinetic import exact
from validation.tissue import calcium_energy_atp_transport_fixtures as fixtures
from validation.tissue import calcium_energy_network_transport_fixtures as prior_fixtures


def definition(*, backend="cpu", jit=True, padded=True):
    """Two nominal steps; opposing routes share actual finite fuel owners."""
    raw = fixtures.probe("mixed", padded=padded)
    raw["execution"].update(backend=backend, jit=jit)
    return raw


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
def test_public_roundtrip_complete_controls_and_ensemble_admission(backend):
    raw = definition(backend=backend)
    spec = parse_spec(raw)
    assert type(spec.model) is schema.SurfaceCalciumEnergyATPTransportModel
    assert get_model(spec.model) is model
    assert parse_spec(spec.to_dict()) == spec
    assert len(model.STATE_TYPE._fields) == 46 and len(model.EXTRA_AXES) == 8
    assert "network_supplied_work_pJ" not in model.STATE_TYPE._fields
    membranes = {row.id: row.inside for row in spec.model.membranes}
    pools = {row.id: row for row in spec.model.energy_pools}
    for route in spec.model.network_transporters:
        assert route.drive.kind == "finite_energy_pool_hydrolysis@1"
        assert route.drive.atp_per_cycle == 1
        assert pools[route.drive.pool_id].cell_id == membranes[route.membrane_id]
        assert (
            route.configuration["standard free energy"]
            == pools[route.drive.pool_id].delta_g0_J_per_mol
        )
    dt = spec.execution.dt
    times = [0.0, 0.75 * dt, dt]
    table = control_values(spec, times)
    assert type(table) is schema.Control
    first = raw["experiment"]["network_transport_controls"][0]["transporter_id"]
    index = [row.id for row in spec.model.network_transporters].index(first)
    np.testing.assert_array_equal(table.network_transport[:, index], [0.8, 0.35, 0.35])
    np.testing.assert_array_equal(
        table.network_transport[:, len(spec.model.network_transporters) :], 0
    )
    inherited = control_values(schema.base_spec(spec), times)
    for name in inherited._fields:
        np.testing.assert_array_equal(getattr(table, name), getattr(inherited, name), strict=True)
    assert set(times) <= set(timeline(spec))
    worlds = parse_worlds(dict(model="ionic_worlds@1", simulation=raw, worlds=2, window_steps=8))
    assert worlds.simulation == spec
    batch = BatchSpec((WorldSpec(7, spec), WorldSpec(79, spec)), 2, 2048, 2**32)
    assert parse_batch(batch.to_dict()) == batch
    previous = parse_spec(prior_fixtures.compact_probe(backend=backend))
    assert get_model(previous.model) is maintained
    with pytest.raises(ConfigError, match="model family"):
        parse_batch(
            BatchSpec((WorldSpec(7, spec), WorldSpec(9, previous)), 2, 2048, 2**32).to_dict()
        )
    evidence(
        "atp-transport-public-admission-" + backend,
        dict(
            definition=spec.to_dict(),
            complete_state_fields=list(model.STATE_TYPE._fields),
            host_admission_only=True,
            GPU_or_compiled_execution=False,
            physical_fuel_owner=True,
            external_work_ledger=False,
        ),
    )


def test_complete_initial_snapshot_retains46_fields_and_refuses_maintained_layout(tmp_path):
    spec = parse_spec(definition(jit=False))
    state, layout = model.initial_values(spec)
    point = Checkpoint(state, layout, 0.0, 0, event_index(spec, 0.0))
    path = write_snapshot(tmp_path / "complete", spec, point)
    restored = load_snapshot(path)
    assert restored.spec == spec
    assert type(restored.checkpoint.state) is model.STATE_TYPE
    assert type(restored.checkpoint.layout) is model.LAYOUT_TYPE
    exact(restored.checkpoint.state, state)
    exact(restored.checkpoint.layout, layout)
    with np.load(path / "state.npz", allow_pickle=False) as arrays:
        assert set(arrays.files) == set(state._fields) | set(layout._fields)
        for key, value in state._asdict().items():
            np.testing.assert_array_equal(arrays[key], value, strict=True)
    old = parse_spec(prior_fixtures.compact_probe())
    _, old_layout = maintained.initial_values(old)
    with pytest.raises(ConfigError, match="state/layout|types"):
        validate_checkpoint(spec, replace(point, layout=old_layout))
    changed = deepcopy(spec.to_dict())
    changed["model"]["id"] = prior_fixtures.MODEL_ID
    with pytest.raises(ConfigError):
        parse_spec(changed)
    evidence(
        "atp-transport-public-snapshot",
        dict(
            definition=spec.to_dict(),
            state_fields=list(state._fields),
            complete_pool_layout=True,
            numerical_trajectory=False,
        ),
    )


def test_actual_event_boundary_restart_preserves_fuel_and_both_gross_histories(tmp_path):
    spec = parse_spec(definition(jit=False, padded=False))
    dt = spec.execution.dt
    baseline = list(iter_windows(spec, WindowPolicy(1, "full")))
    assert len(baseline) == 3
    assert [row.final.time for row in baseline] == [0.75 * dt, dt, 2 * dt]
    first = baseline[0]
    saved = load_snapshot(write_snapshot(tmp_path / "event-boundary", spec, first.final))
    resumed = list(iter_windows(saved.spec, WindowPolicy(1, "full"), saved.checkpoint))
    assert len(resumed) == 2
    for actual, expected in zip(resumed, baseline[1:], strict=True):
        exact(actual.final.state, expected.final.state)
        exact(actual.final.layout, expected.final.layout)
        exact(actual.history, expected.history)
    times = np.concatenate([row.observations.times for row in baseline])
    for key in vars(baseline[-1].observations):
        expected = np.concatenate([getattr(row.observations, key) for row in baseline])
        actual = np.concatenate([getattr(row.observations, key) for row in resumed])
        np.testing.assert_array_equal(actual, expected[times >= first.final.time], strict=True)
    state = resumed[-1].final.state
    assert len(state) == 46
    assert np.any(state.network_gross_hydrolysis_fmol > 0)
    assert np.any(state.network_gross_synthesis_fmol > 0)
    assert np.any(state.network_fuel_work_pJ != 0)
    assert np.any(state.network_dissipated_energy_pJ > 0)
    assert np.any(state.energy_amount_increment_fmol != 0)
    assert "network_supplied_work_pJ" not in state._fields
    assert all(row.timings["compile_or_cache_seconds"] == 0 for row in (*baseline, *resumed))
    evidence(
        "atp-transport-public-event-restart",
        dict(
            definition=spec.to_dict(),
            duration_s=2 * dt,
            restart_time_s=first.final.time,
            complete_restart_exact=True,
            forward_and_reverse_fuel_history=True,
            long_relaxation_or_order_claim=False,
            GPU_or_compiled_execution=False,
        ),
        {"state__" + key: np.asarray(value) for key, value in state._asdict().items()},
    )
