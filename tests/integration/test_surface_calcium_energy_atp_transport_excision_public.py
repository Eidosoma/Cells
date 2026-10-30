"""Public finite-ATP cut ownership, portable archives and a short actual restart."""

import json
from functools import lru_cache

import numpy as np
import pytest

from cells.core import surface_calcium_energy_atp_transport_excision_spec as schema
from cells.core.batch import BatchSpec, WorldSpec, parse_batch
from cells.core.excision import excise
from cells.core.grid import EventGrid
from cells.core.runner import timeline
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import Checkpoint
from cells.core.windows import WindowPolicy, iter_windows
from cells.ensemble.ionic import parse_spec as parse_worlds
from cells.excision_io import CALCIUM_ENERGY_ATP_TRANSPORT_KIND, load_excision, write_excision
from cells.io import load_snapshot, write_snapshot
from cells.models import surface_calcium_energy_atp_transport as parent
from cells.models import surface_calcium_energy_atp_transport_excision as model
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_step
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_kinetic import exact
from validation.tissue import calcium_energy_atp_transport_excision_fixtures as fixtures


def controls(spec, time):
    table = control_values(spec, [time])
    return type(table)(*(v[0] for v in table))


@lru_cache(maxsize=1)
def source_point():
    raw = fixtures.definition(padded=False)
    # Declare the smaller nominal step before any evolution or removal. Public
    # restart is a two-step prefix; independent full-interval qualification is
    # separate and keeps the original absolute event clocks and horizons.
    raw["execution"]["dt"] = fixtures.DT / 8
    spec = parse_spec(raw)
    state, layout = parent.initial_values(spec)
    grid = EventGrid(spec)
    cut_index = grid.exact_index(fixtures.DT)

    def rhs(value, control, params, active):
        result = parent.readouts(value, control, params, xp=np)
        assert result.valid and abs(float(result.field.energy_balance_pJ_s)) <= 1e-10
        return result.derivative

    for i in range(cut_index):
        state = rk4_step(
            rhs, state, grid[i + 1] - grid[i], controls(spec, grid[i]), layout, layout.active
        )
        parent.check_values(state, spec)
    return spec, Checkpoint(
        state, layout, grid[cut_index], cut_index, event_index(spec, grid[cut_index])
    )


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
def test_public_ATP_cut_identity_controls_and_ensemble_admission(backend):
    spec, point = source_point()
    cut = excise(spec, point, ["cell_1"])
    raw = cut.spec.to_dict()
    raw["execution"].update(backend=backend, jit=True)
    parsed = parse_spec(raw)
    assert type(parsed.model) is schema.SurfaceCalciumEnergyATPTransportExcisionModel
    assert get_model(parsed.model) is model and get_model(spec.model) is parent
    assert parse_spec(parsed.to_dict()) == parsed
    batch = BatchSpec((WorldSpec(11, parsed), WorldSpec(31, parsed)), 2, 2048, 2**32)
    assert parse_batch(batch.to_dict()) == batch
    assert (
        parse_worlds(
            dict(model="ionic_worlds@1", simulation=raw, worlds=2, window_steps=8)
        ).simulation
        == parsed
    )
    assert point.time == model.initial_time(parsed)
    # This fine-step fixture is admitted for bounded windows. A full-horizon
    # trace correctly exceeds its original memory budget; preserve that guard.
    with pytest.raises(ConfigError, match="max_trace_bytes"):
        timeline(parsed)
    assert EventGrid(parsed)[point.step_index] == point.time
    assert EventGrid(parsed).exact_index(point.time) == point.step_index
    for time in (point.time, 1.75 * fixtures.DT, 13.3e-6, 61.1e-6):
        exact(controls(parsed, time), controls(schema.base_spec(parsed), time))
    assert set(cut.report["archived_removed_state"]) == set(parent.STATE_TYPE._fields)
    for key in ("network_gross_hydrolysis_fmol", "network_gross_synthesis_fmol"):
        assert np.any(np.asarray(cut.report["archived_removed_state"][key]) > 0)
    evidence(
        "atp-cut-public-admission-" + backend,
        dict(definition=raw, host_admission_only=True, GPU_or_compiled_execution=False),
    )


def test_portable46_field_ATP_cut_and_exact_two_step_continuation_restart(tmp_path):
    spec, point = source_point()
    cut = excise(spec, point, ["cell_1"])
    path = write_excision(tmp_path / "cut", cut)
    assert json.loads((path / "manifest.json").read_text())["kind"] == (
        CALCIUM_ENERGY_ATP_TRANSPORT_KIND
    )
    restored = load_excision(path)
    assert restored.spec == cut.spec and restored.report == cut.report
    exact(restored.source_checkpoint.state, point.state)
    exact(restored.checkpoint.state, cut.checkpoint.state)
    exact(restored.checkpoint.layout, cut.checkpoint.layout)
    iterator = iter_windows(restored.spec, WindowPolicy(1, "full"), restored.checkpoint)
    first, expected = next(iterator), next(iterator)
    iterator.close()
    saved = load_snapshot(write_snapshot(tmp_path / "resume", restored.spec, first.final))
    iterator = iter_windows(saved.spec, WindowPolicy(1, "full"), saved.checkpoint)
    actual = next(iterator)
    iterator.close()
    exact(actual.final.state, expected.final.state)
    exact(actual.final.layout, expected.final.layout)
    exact(actual.history, expected.history)
    times = np.r_[first.observations.times, expected.observations.times]
    for key in vars(expected.observations):
        combined = np.concatenate(
            (getattr(first.observations, key), getattr(expected.observations, key))
        )
        np.testing.assert_array_equal(
            getattr(actual.observations, key), combined[times >= first.final.time], strict=True
        )
    assert actual.final.time == point.time + 2 * spec.execution.dt
    for name in (
        "network_gross_hydrolysis_fmol",
        "network_gross_synthesis_fmol",
        "network_dissipated_energy_pJ",
    ):
        assert np.any(getattr(actual.final.state, name) > 0)
    assert np.any(actual.final.state.network_fuel_work_pJ != 0)
    assert "network_supplied_work_pJ" not in actual.final.state._fields
    assert all(r.timings["compile_or_cache_seconds"] == 0 for r in (first, expected, actual))
    evidence(
        "atp-cut-public-actual-restart",
        dict(
            source=spec.to_dict(),
            report=cut.report,
            after=cut.spec.to_dict(),
            initial_time_s=point.time,
            final_time_s=actual.final.time,
            complete46_state_layout_history_observers_exact=True,
            postcut_interval_s=2 * spec.execution.dt,
            full_transient_claim=False,
            GPU_or_compiled_execution=False,
        ),
    )
    with pytest.raises(FileExistsError):
        write_excision(path, cut)
    tampered = json.loads((path / "transition.json").read_text())
    tampered["archived_removed_state"]["network_gross_synthesis_fmol"][0] += 1
    (path / "transition.json").write_text(json.dumps(tampered))
    with pytest.raises(ConfigError, match="checksum"):
        load_excision(path)


def test_terminal_ATP_archive_retains_fuel_and_refuses_relabelled_family(tmp_path):
    spec, point = source_point()
    terminal = excise(spec, point, [row.id for row in spec.model.cells])
    path = write_excision(tmp_path / "terminal", terminal)
    restored = load_excision(path)
    assert restored.spec is None and restored.checkpoint is None
    assert restored.report == terminal.report and not (path / "after").exists()
    exact(restored.source_checkpoint.state, point.state)
    for key in ("network_gross_hydrolysis_fmol", "network_gross_synthesis_fmol"):
        assert np.any(np.asarray(restored.report["archived_removed_state"][key]) > 0)
    manifest = json.loads((path / "manifest.json").read_text())
    manifest["kind"] = "cells.calcium_energy_irreversible_transport_tissue_excision@1"
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ConfigError, match="family"):
        load_excision(path)
