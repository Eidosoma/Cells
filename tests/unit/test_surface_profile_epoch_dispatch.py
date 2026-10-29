"""Public epoch admission retains history; short execution is an engineering check."""

import json
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from cells.core import membrane_profile_phase_handoff as handoff
from cells.core import surface_profile_epoch_spec as epoch
from cells.core.batch import BatchSpec, WorldSpec, parse_batch
from cells.core.errors import NumericalError
from cells.core.excision import excise
from cells.core.grid import EventGrid
from cells.core.runner import branch_checkpoint, run, validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, digest, parse_spec
from cells.core.state import initialise
from cells.core.windows import WindowPolicy, iter_windows, plan_windows
from cells.ensemble.ionic import parse_spec as parse_ensemble
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import surface_profile_epoch as model
from cells.models import surface_profile_interventions as scheduled
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_step
from tests.phase_fixtures import prepared, request
from tests.unit.test_windows import assert_windows


def exact(left, right):
    assert left._fields == right._fields
    for a, b in zip(left, right, strict=True):
        assert np.asarray(a).dtype == np.asarray(b).dtype
        np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize("small", [False, True])
def test_public_epoch_retains_complete_source_and_initial_physical_history(small, tmp_path):
    raw = prepared(small=small).definition
    spec = parse_spec(raw)
    assert type(spec.model) is epoch.SurfaceProfileEpochModel
    assert get_model(spec.model) is model
    assert spec == epoch.parse(raw) == parse_spec(spec.to_dict())
    assert digest(spec.to_dict()) == digest(raw)
    source, before = handoff.decode_source(raw["model"]["handoff"]["source"])
    validate_checkpoint(source, before)
    point = initialise(spec)
    validate_checkpoint(spec, point)
    assert type(point.state) is model.STATE_TYPE and type(point.layout) is model.LAYOUT_TYPE
    assert type(point.state) is not type(before.state)
    exact(scheduled.base_state(point.state), scheduled.base_state(before.state))
    exact(scheduled.base_layout(point.layout), scheduled.base_layout(before.layout))
    assert any(np.any(value != 0) for value in scheduled.base_state(point.state))
    assert point.time == point.step_index == 0
    np.testing.assert_array_equal(point.state.phase_clock_s, [0.0])
    write_snapshot(tmp_path / "checkpoint", spec, point)
    restored = load_snapshot(tmp_path / "checkpoint")
    assert restored.spec == spec
    exact(restored.checkpoint.state, point.state)
    exact(restored.checkpoint.layout, point.layout)
    batch = BatchSpec((WorldSpec(3, spec), WorldSpec(79, spec)), 2, 10000, 2**32)
    assert parse_batch(batch.to_dict()) == batch
    with pytest.raises(ValueError, match="JIT"):
        parse_ensemble(dict(model="ionic_worlds@1", simulation=raw, worlds=2, window_steps=8))
    compiled_raw = deepcopy(raw)
    compiled_raw["execution"]["jit"] = True
    ensemble = parse_ensemble(
        dict(model="ionic_worlds@1", simulation=compiled_raw, worlds=2, window_steps=8)
    )
    assert ensemble.simulation == parse_spec(compiled_raw)
    assert plan_windows(spec, WindowPolicy(8)).start_step == 0


def evolved_checkpoint():
    spec = parse_spec(prepared(small=True).definition)
    initial = initialise(spec)
    state = model.STATE_TYPE(*(np.asarray(value) for value in initial.state))
    layout = model.LAYOUT_TYPE(*(np.asarray(value) for value in initial.layout))
    table = control_values(spec, [0.0])
    control = type(table)(*(value[0] for value in table))

    def rhs(value, u, p, active):
        assert model.control_domain_valid(value, u, p, active, xp=np)
        return model.rhs(value, u, p, active, xp=np)

    time = spec.execution.dt
    state = rk4_step(rhs, state, time, control, layout, layout.active)
    point = replace(
        initial,
        state=state,
        time=time,
        step_index=EventGrid(spec).exact_index(time),
        event_index=event_index(spec, time),
    )
    validate_checkpoint(spec, point)
    return spec, point


@pytest.mark.parametrize("clock", [0.0, -1e-9, float("nan")])
def test_public_epoch_refuses_clock_reset_after_a_valid_real_step(clock):
    spec, point = evolved_checkpoint()
    damaged = replace(point, state=point.state._replace(phase_clock_s=np.asarray([clock])))
    with pytest.raises((ConfigError, NumericalError), match="clock"):
        validate_checkpoint(spec, damaged)
    assert float(point.state.phase_clock_s[0]) > 0


def test_evolved_epoch_snapshot_restores_in_a_fresh_process(tmp_path):
    spec, point = evolved_checkpoint()
    folder = write_snapshot(tmp_path / "checkpoint", spec, point)
    loaded = load_snapshot(folder)
    exact(loaded.checkpoint.state, point.state)
    code = """
import json,sys
from cells.io import load_snapshot
from cells.models.surface_profile_epoch import handoff_record
saved=load_snapshot(sys.argv[1])
print(json.dumps(dict(model=saved.spec.to_dict()['model']['id'],
    accepted_time=saved.checkpoint.time, phase_clock=float(saved.checkpoint.state.phase_clock_s[0]),
    source_clocks=handoff_record(saved.spec)['clocks'])))
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", code, str(folder)],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    record = json.loads(result.stdout)
    assert record["model"] == epoch.MODEL_ID
    assert record["accepted_time"] == point.time == record["phase_clock"]
    assert record["source_clocks"] == model.handoff_record(spec)["clocks"]


def test_epoch_requires_explicit_handoff_and_cannot_fall_through_to_passive_routes():
    spec = parse_spec(prepared(small=True).definition)
    source, before = handoff.decode_source(request()["source"])
    validate_checkpoint(source, before)
    point = initialise(spec)
    validate_checkpoint(spec, point)
    with pytest.raises(ConfigError):
        validate_checkpoint(spec, before)
    with pytest.raises(ConfigError, match="model or execution"):
        branch_checkpoint(source, before, spec)
    with pytest.raises(ConfigError):
        excise(spec, point, [spec.model.cells[0].id])
    batch = BatchSpec(
        (WorldSpec(3, spec), WorldSpec(79, epoch.scheduled_spec(spec))), 2, 10000, 2**32
    )
    with pytest.raises(ConfigError, match="model family"):
        parse_batch(batch.to_dict())


def test_compiled_epoch_history_windows_and_restart_are_exact(tmp_path):
    """Two SIM steps check the new public runtime; the component covers longer physics."""
    raw = deepcopy(prepared(small=True).definition)
    raw["execution"]["jit"] = True
    spec = parse_spec(raw)
    assert spec.execution.jit
    complete = run(spec)
    write_run(tmp_path / "ordinary", complete)
    parts = list(iter_windows(spec, WindowPolicy(1)))
    assert_windows(parts, complete)
    before = model.handoff_record(spec)["source"]["checkpoint"]
    for name, values in scheduled.base_state(complete.history)._asdict().items():
        np.testing.assert_array_equal(values[0], before["state"][name]["values"])
    np.testing.assert_array_equal(
        complete.observations.init_phase_clock_s, before["state"]["phase_clock_s"]["values"][0]
    )
    np.testing.assert_allclose(
        complete.observations.elapsed_time_s[:, 0],
        before["time"] + complete.times,
        rtol=0,
        atol=1e-23,
    )
    middle = write_snapshot(tmp_path / "middle", spec, complete.checkpoint_at(spec.execution.dt))
    loaded = load_snapshot(middle)
    resumed = list(iter_windows(loaded.spec, WindowPolicy(1), loaded.checkpoint))
    assert_windows(resumed, run(spec, loaded.checkpoint))
    exact(resumed[-1].final.state, complete.final.state)
    (tmp_path / "comparison.json").write_text(
        json.dumps(
            dict(
                status="passed",
                complete_fields=list(complete.history._fields),
                init_time=before["time"],
                sim_time=complete.final.time,
                real_sim_steps=complete.final.step_index,
                ordinary_windowed_and_restart_exact=True,
                diagnostics=complete.diagnostics,
                scope="Two-step public execution; no long trajectory or native-loop parity claim",
            ),
            indent=2,
        )
        + "\n"
    )
