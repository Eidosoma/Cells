"""Ownership, closure, independent rates and ordinary lifecycle contracts."""

import copy
import importlib.util
from pathlib import Path

import numpy as np
import pytest

from cells.core.batch import BatchSpec, WorldSpec, run_batch
from cells.core.errors import NumericalError
from cells.core.runner import branch_checkpoint, run
from cells.core.schedule import PhysicalIonicGraphControl, control_values
from cells.core.specs import ConfigError, parse_spec
from cells.ensemble.ionic import parse_spec as parse_ensemble
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import junction_finite_extracellular as local
from cells.models import spatial_extracellular as passive
from cells.models import spatial_junction as model
from cells.models.registry import get_model


def private(name, filename):
    s = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


fixture = private("spatial_cluster_fixture", "fixtures.py")
reference = private("spatial_cluster_reference", "reference.py")


def initial(raw=None):
    raw = fixture.definition(end=0.0002) if raw is None else raw
    spec = parse_spec(raw)
    state, layout = model.initial_values(spec)
    control = PhysicalIonicGraphControl(*(v[0] for v in control_values(spec, [0.0])))
    return spec, state, layout, control


def same(actual, expected):
    for a, b in zip(actual, expected, strict=True):
        np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
def test_roundtrip_backend_and_ensemble_definition(backend):
    raw = fixture.definition(end=0.0002, backend=backend)
    spec = parse_spec(raw)
    assert parse_spec(spec.to_dict()) == spec
    assert get_model(spec.model) is model
    assert spec.fingerprint != parse_spec(fixture.local_definition(raw)).fingerprint
    ensemble = parse_ensemble({"model": "ionic_worlds@1", "simulation": raw, "worlds": 2})
    assert ensemble.simulation == spec


@pytest.mark.parametrize("padded", [False, True])
def test_independent_full_rhs_ownership_and_current_closure(padded):
    raw = fixture.definition(padded=padded, end=0.0002)
    _, state, layout, control = initial(raw)
    rates = model.rhs(state, control, layout, layout.active, xp=np)
    c = reference.bind(raw)
    actual = reference.flatten(c, rates._asdict())
    expected = reference.rhs(c, reference.control_at(raw, 0.0), reference.initial(c))
    np.testing.assert_allclose(actual, expected, rtol=2e-12, atol=2e-12)
    np.testing.assert_allclose(
        np.sum(rates.amount_increment, axis=-1)
        + np.sum(rates.extracellular_amount_increment, axis=-1),
        0,
        rtol=0,
        atol=2e-14,
    )
    np.testing.assert_allclose(
        passive.component_charge(rates, layout, xp=np, derivative=True), 0, atol=1e-20
    )
    field = model.field_values(state, layout, xp=np)
    phi, flux, power, _ = reference.bulk(c, c["outside_initial"] / c["outside_volume"])
    np.testing.assert_allclose(field.potential_V[:3], phi, atol=2e-15, rtol=2e-12)
    np.testing.assert_allclose(field.flux_fmol_per_s[:, :3], flux, atol=2e-12, rtol=2e-12)
    np.testing.assert_allclose(field.dissipation_rate_pJ_per_s[:3], power, atol=2e-12, rtol=2e-12)


def test_rhs_responds_to_same_stage_outside_inventory():
    _, state, layout, control = initial()
    original = model.rhs(state, control, layout, layout.active, xp=np)
    increment = state.extracellular_amount_increment.copy()
    increment[0, 0] += 0.1
    increment[2, 0] += 0.1
    state = state._replace(extracellular_amount_increment=increment)
    assert model.domain_valid(state, layout, layout.active, xp=np)
    updated = model.rhs(state, control, layout, layout.active, xp=np)
    assert np.max(np.abs(updated.leak_transferred - original.leak_transferred)) > 1e-7
    assert np.max(np.abs(updated.face_transferred - original.face_transferred)) > 1e-4


def test_zero_face_limit_reproduces_existing_local_rates():
    raw = fixture.definition(arm="finite_limit", end=0.0002)
    _, state, layout, control = initial(raw)
    previous = parse_spec(fixture.local_definition(raw))
    s0, l0 = local.initial_values(previous)
    new = model.rhs(state, control, layout, layout.active, xp=np)
    old = local.rhs(s0, control, l0, l0.active, xp=np)
    same(model.base_state(new), old)
    np.testing.assert_array_equal(new.face_transferred, 0)
    np.testing.assert_array_equal(new.face_dissipated_energy_pJ, 0)


def test_gauge_and_face_orientation_do_not_change_physical_rates():
    raw = fixture.definition(end=0.0002)
    _, state, layout, control = initial(raw)
    rates = model.rhs(state, control, layout, layout.active, xp=np)
    raw["model"]["closure"]["gauge_reference"] = "far"
    _, alt, geometry, controls = initial(raw)
    changed = model.rhs(alt, controls, geometry, geometry.active, xp=np)
    for a, b in zip(rates, changed, strict=True):
        np.testing.assert_allclose(a, b, atol=2e-12, rtol=2e-12)
    for face in raw["model"]["faces"]:
        face["sender"], face["receiver"] = face["receiver"], face["sender"]
    _, alt, geometry, controls = initial(raw)
    changed = model.rhs(alt, controls, geometry, geometry.active, xp=np)
    same_fields = set(model.STATE_TYPE._fields) - {"face_transferred"}
    for name in same_fields:
        np.testing.assert_allclose(
            getattr(rates, name), getattr(changed, name), atol=2e-12, rtol=2e-12
        )
    np.testing.assert_allclose(
        rates.face_transferred, -changed.face_transferred, atol=2e-12, rtol=2e-12
    )


@pytest.mark.parametrize(
    "change",
    [
        "cross_region",
        "disconnected",
        "identity",
        "charge",
        "solver",
        "tolerance",
        "capacity",
        "gpu_eager",
    ],
)
def test_invalid_spatial_meanings_are_rejected(change):
    raw = fixture.definition()
    if change == "cross_region":
        raw["model"]["cells"][1]["membrane"]["outside"] = "near"
    elif change == "disconnected":
        raw["model"]["faces"] = raw["model"]["faces"][:1]
    elif change == "identity":
        raw["model"]["faces"][0]["id"] = "pump_0"
    elif change == "charge":
        raw["model"]["surroundings"][0]["fixed_charge_equivalent_fmol"] += 0.01
    elif change == "solver":
        raw["execution"]["field_solver"] = "unknown"
    elif change == "tolerance":
        raw["execution"]["material_balance_atol_fmol"]["Na"] = 1e-7
    elif change == "capacity":
        raw["execution"]["face_capacity"] = 2
    else:
        raw["execution"].update(backend="gpu", jit=False)
    with pytest.raises(ConfigError):
        parse_spec(raw)


@pytest.mark.parametrize(
    "name",
    [
        "face_transferred",
        "face_dissipated_energy_pJ",
        "pump_cycles",
        "extracellular_amount_increment",
    ],
)
def test_corrupt_owned_histories_fail(name):
    spec, state, _, _ = initial()
    value = getattr(state, name).copy()
    value.flat[0] = 0.01
    with pytest.raises(NumericalError):
        model.check_values(state._replace(**{name: value}), spec)


def test_padding_and_nonpositive_inventory_fail():
    _, state, layout, _ = initial()
    bad = state.face_transferred.copy()
    bad[0, -1] = 1e-9
    assert not model.domain_valid(
        state._replace(face_transferred=bad), layout, layout.active, xp=np
    )
    bad = state.extracellular_amount_increment.copy()
    bad[0, 1] = -layout.extracellular_amount_reference[0, 1]
    assert not model.domain_valid(
        state._replace(extracellular_amount_increment=bad), layout, layout.active, xp=np
    )


def test_reference_work_budget():
    with pytest.raises(ValueError, match="RHS budget"):
        reference.integrate(
            fixture.definition(end=0.0002),
            {"method": "DOP853", "rtol": 1e-10, "atol": 1e-13, "max_step_s": 1e-4},
            rhs_cap=1,
        )


def test_compiled_runner_disk_restart_branch_and_observation_rates(tmp_path):
    raw = fixture.definition(end=0.0002)
    raw["experiment"]["observation_times"] = [0.0, 0.000073, 0.0001, 0.0002]
    spec = parse_spec(raw)
    result = run(spec)
    write_run(tmp_path / "run", result)
    cp = result.checkpoint_at(0.0001)
    write_snapshot(tmp_path / "checkpoint", spec, cp)
    saved = load_snapshot(tmp_path / "checkpoint")
    same(saved.checkpoint.state, cp.state)
    resumed = run(saved.spec, saved.checkpoint)
    same(resumed.history, tuple(v[cp.step_index :] for v in result.history))
    changed = copy.deepcopy(raw)
    for group in changed["experiment"]["membrane_controls"]:
        group["pump"].append({"time": cp.time, "multiplier": 0.0})
    branch_spec = parse_spec(changed)
    branch = run(branch_spec, branch_checkpoint(spec, cp, branch_spec))
    same(tuple(v[0] for v in branch.history), cp.state)
    np.testing.assert_array_equal(branch.history.pump_cycles[-1], cp.state.pump_cycles)
    assert np.max(np.abs(branch.history.face_transferred[-1] - cp.state.face_transferred)) > 0
    obs = result.observations
    # Observation rates use NumPy; keep the comparison on the same backend.
    layout = model.LAYOUT_TYPE(*(np.asarray(v) for v in result.final.layout))
    state = model.STATE_TYPE(*(getattr(obs, name) for name in model.STATE_TYPE._fields))
    controls = control_values(spec, obs.times)
    expected = model.rhs(state, controls, layout, layout.active, xp=np)
    np.testing.assert_allclose(
        obs.extracellular_rate_fmol_per_s,
        expected.extracellular_amount_increment,
        rtol=0,
        atol=1e-14,
    )
    assert result.diagnostics["max_energy_balance_error_pJ"] < 2e-8


def test_batch_world_identity_and_scalar_agreement():
    specs = [parse_spec(fixture.definition(end=0.0001, arm=arm)) for arm in ("baseline", "blocked")]
    batch = BatchSpec(tuple(WorldSpec(i + 10, s) for i, s in enumerate(specs)), 2, 20, 2**28)
    result = run_batch(batch)
    assert set(result.worlds) == {10, 11}
    for world in result.worlds.values():
        same(world.history, run(world.spec).history)
