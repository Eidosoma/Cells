"""Complete scheduled-barrier public ownership, controls, snapshots and admission.

These software contracts do not replace the independent full-stage comparisons
or the longer, refined trajectories. GPU admission does not execute a GPU.
"""

import json
import subprocess
import sys
from dataclasses import replace

import numpy as np
import pytest

from cells.core.batch import BatchSpec, WorldSpec, parse_batch
from cells.core.grid import EventGrid
from cells.core.runner import branch_checkpoint, validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, digest, parse_spec
from cells.core.state import initialise
from cells.ensemble.ionic import parse_spec as parse_worlds
from cells.io import load_snapshot, write_snapshot
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_step
from tests.joint_water_profile_barrier_dispatch_fixtures import DT, OWNERS, definition
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_kinetic import exact


@pytest.mark.parametrize("family", OWNERS)
@pytest.mark.parametrize("backend", ["cpu", "gpu"])
def test_joint_water_combined_profile_barrier_public_admission_preserves_all_parent_controls(
    family, backend
):
    schema, model, fields = OWNERS[family]
    spec = parse_spec(definition(family, backend=backend))
    parent = schema.owner_spec(spec)
    assert get_model(spec.model) is model
    assert spec == schema.parse(spec.to_dict()) == parse_spec(spec.to_dict())
    assert parent.to_dict()["model"]["id"] == schema.PARENT_MODEL_ID
    assert get_model(parent.model) is model.base
    assert parse_spec(parent.to_dict()) == parent
    times = [0.0, np.nextafter(DT, 0.0), DT, 2 * DT]
    table = control_values(spec, times)
    exact(table, control_values(parent, times))
    np.testing.assert_array_equal(table.channel[0], table.channel[1])
    assert np.any(table.channel[1] != table.channel[2])
    np.testing.assert_array_equal(table.channel[2], table.channel[3])
    batch = BatchSpec((WorldSpec(17, spec), WorldSpec(53, spec)), 2, 100, 2**30)
    assert parse_batch(batch.to_dict()) == batch
    worlds = parse_worlds(
        dict(model="ionic_worlds@1", simulation=spec.to_dict(), worlds=2, window_steps=4)
    )
    assert worlds.simulation == spec
    assert len(model.STATE_TYPE._fields) == fields
    evidence(
        "joint-water-combined-profile-barrier-dispatch-" + family + "-" + backend,
        dict(
            definition=spec.to_dict(),
            state_fields=list(model.STATE_TYPE._fields),
            control_fields=list(table._fields),
            exact_parent_control_arrays=True,
            scope="Software admission only; no compiled/GPU execution or trajectory claim",
        ),
    )


@pytest.mark.parametrize("family", OWNERS)
@pytest.mark.parametrize("phase", ["INIT", "SIM"])
def test_joint_water_combined_profile_barrier_snapshot_retains_every_physical_field_and_recipe(
    family, phase, tmp_path
):
    schema, model, fields = OWNERS[family]
    spec = parse_spec(definition(family, phase))
    parent = schema.owner_spec(spec)
    point, original = initialise(spec), initialise(parent)
    assert type(point.state) is model.STATE_TYPE and len(point.state) == fields
    assert type(point.layout) is model.LAYOUT_TYPE
    exact(model.parent_state(point.state), original.state)
    exact(model.parent_layout(point.layout), original.layout)
    np.testing.assert_array_equal(point.state.phase_clock_s, [0.0])
    assert len(spec.model.channels) == 63
    laws = np.asarray(point.layout.channel_laws)[np.asarray(point.layout.channel_active)]
    assert set(laws.tolist()) == set(range(56))
    folder = write_snapshot(tmp_path / "checkpoint", spec, point)
    restored = load_snapshot(folder)
    assert restored.spec == spec
    exact(restored.checkpoint.state, point.state)
    exact(restored.checkpoint.layout, point.layout)
    # Fresh-process loading must recover complete types, phase and coefficient
    # provenance; a parent-only serializer would silently lose these fields.
    script = """
import json,sys,numpy as np
from cells.io import load_snapshot
from cells.core.specs import digest
x=load_snapshot(sys.argv[1])
arrays={k:np.asarray(v).tolist() for k,v in x.checkpoint.state._asdict().items()}
print(json.dumps(dict(definition=x.spec.fingerprint, state=digest(arrays),
                     phase=x.spec.model.phase, fields=list(x.checkpoint.state._fields))))
"""
    loaded = subprocess.run(
        [sys.executable, "-B", "-c", script, str(folder)],
        capture_output=True,
        text=True,
        timeout=90,
        check=True,
    )
    assert json.loads(loaded.stdout) == dict(
        definition=spec.fingerprint,
        state=digest({k: np.asarray(v).tolist() for k, v in point.state._asdict().items()}),
        phase=phase,
        fields=list(point.state._fields),
    )
    evidence(
        "joint-water-combined-profile-barrier-snapshot-" + family + "-" + phase,
        dict(
            definition=spec.to_dict(),
            all_physical_state_and_layout_exact=True,
            fresh_process_restored=True,
            scope="Complete initial snapshots; no evolved trajectory claim",
        ),
        arrays={k: np.asarray(v) for k, v in point.state._asdict().items()},
    )


@pytest.mark.parametrize("family", OWNERS)
def test_joint_water_combined_interfaces_refuse_implicit_parent_or_phase_change(
    family,
):
    schema, _, _ = OWNERS[family]
    spec = parse_spec(definition(family))
    parent = schema.owner_spec(spec)
    point = initialise(spec)
    with pytest.raises(ConfigError):
        validate_checkpoint(parent, point)
    with pytest.raises(ConfigError):
        branch_checkpoint(spec, point, parent)
    other_phase = parse_spec(definition(family, "INIT"))
    with pytest.raises(ConfigError):
        branch_checkpoint(spec, point, other_phase)
    mixed = BatchSpec((WorldSpec(17, spec), WorldSpec(53, parent)), 2, 100, 2**30)
    with pytest.raises(ConfigError, match="model family"):
        parse_batch(mixed.to_dict())


@pytest.mark.parametrize("family", OWNERS)
def test_joint_water_combined_profile_barrier_evolved_history_and_both_coefficient_readouts(
    family, tmp_path
):
    _, model, _ = OWNERS[family]
    spec = parse_spec(definition(family))
    point = initialise(spec)
    state = model.STATE_TYPE(*(np.asarray(v) for v in point.state))
    layout = model.LAYOUT_TYPE(*(np.asarray(v) for v in point.layout))
    table = control_values(spec, [0.0])
    control = type(table)(*(np.asarray(v[0]) for v in table))
    evolved = rk4_step(
        lambda y, *args: model.rhs(y, *args, xp=np), state, DT, control, layout, layout.active
    )
    point = replace(
        point,
        state=evolved,
        layout=layout,
        time=DT,
        step_index=EventGrid(spec).exact_index(DT),
        event_index=event_index(spec, DT),
    )
    validate_checkpoint(spec, point)
    for name in (
        "membrane_transferred",
        "face_transferred",
        "channel_transferred",
        "pump_cycles",
        "chemical_amount_increment",
    ):
        assert np.any(getattr(evolved, name) != getattr(state, name)), name
    assert np.any(evolved.energy_amount_increment_fmol != state.energy_amount_increment_fmol)
    assert np.any(evolved.volume_increment_pL != state.volume_increment_pL)
    assert np.any(
        evolved.extracellular_volume_increment_pL != state.extracellular_volume_increment_pL
    )
    if family == "repair":
        assert np.any(evolved.damage != state.damage)
        assert np.any(evolved.injury_transferred != state.injury_transferred)
    restored = load_snapshot(write_snapshot(tmp_path / "evolved", spec, point))
    exact(restored.checkpoint.state, evolved)
    exact(restored.checkpoint.layout, layout)
    history = model.STATE_TYPE(*(np.stack((a, b)) for a, b in zip(state, evolved, strict=True)))
    times = np.asarray([0.0, DT])
    observed = model.observe_history(times, history, layout, times, spec)
    for name in state._fields:
        np.testing.assert_array_equal(getattr(observed, name), getattr(history, name))
    for i, y in enumerate((state, evolved)):
        signal = model.signal_values(y, layout, xp=np)
        np.testing.assert_array_equal(
            observed.membrane_permeability_m_per_s[i], signal.membrane.permeability
        )
        np.testing.assert_array_equal(
            observed.extracellular_face_diffusivity_m2_s[i], signal.barrier.face_diffusivity
        )
        np.testing.assert_array_equal(observed.native_membrane_pulse[i], signal.membrane.pulse)
        np.testing.assert_array_equal(observed.native_barrier_pulse[i], signal.barrier.pulse)
    evidence(
        "joint-water-combined-profile-barrier-evolved-" + family,
        dict(
            state_fields=list(state._fields),
            all_history_exact=True,
            both_schedules_observed=True,
            duration_s=DT,
            full_trajectory_credit=False,
        ),
        arrays={k: np.asarray(v) for k, v in history._asdict().items()},
    )
