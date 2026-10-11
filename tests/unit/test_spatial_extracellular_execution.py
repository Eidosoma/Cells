"""Spatial family uses the ordinary engine, checkpoint, window and cohort paths."""

import copy
from dataclasses import replace

import numpy as np
import pytest

from cells.batch_io import load_batch_snapshot, write_batch_snapshot
from cells.core.batch import BatchSpec, WorldSpec, parse_batch, run_batch
from cells.core.batch_windows import iter_batch_windows
from cells.core.errors import NumericalError
from cells.core.runner import branch_checkpoint, run, validate_checkpoint
from cells.core.schedule import control_values
from cells.core.specs import ChannelChange, ConfigError, parse_spec
from cells.core.state import initialise
from cells.core.windows import WindowPolicy, iter_windows
from cells.io import load_snapshot, write_snapshot
from cells.models import spatial_extracellular as model
from cells.numerics.fixed_step import rk4_checked_step
from tests import spatial_extracellular_numerical_data as data
from tests.spatial_extracellular_fixtures import canonical, definition, load_cases, spec_for

PLAN, CASES = load_cases()


def short(name="binary_unequal", *, controls=True, end=0.001):
    raw = copy.deepcopy(next(c.raw for c in CASES if c.id == name))
    raw["horizon_s"], raw["analytic_kind"] = end, None
    raw["controls"] = [
        {"time_s": t, "membrane_availability": {p["id"]: v for p in raw["world"]["membranes"]}}
        for t, v in ([(0, 1), (0.0003, 0), (0.0007, 1), (end, 0.35)] if controls else [(0, 1)])
    ]
    return data.resolve(raw)


@pytest.mark.parametrize(
    "name",
    [
        "single_outside",
        "binary_unequal",
        "ternary_loop",
        "two_cells_chain",
        "divalent",
        "pure_bulk",
    ],
)
def test_complete_restart_windows_and_eager(tmp_path, name):
    case = short(name)
    spec = spec_for(case)
    result = run(spec)
    at = 0.0005
    cp = result.checkpoint_at(at)
    write_snapshot(tmp_path / "snapshot", spec, cp)
    loaded = load_snapshot(tmp_path / "snapshot")
    restored = run(loaded.spec, loaded.checkpoint)
    index = int(np.flatnonzero(result.times == at)[0])
    for a, b in zip(result.history, restored.history, strict=True):
        np.testing.assert_array_equal(a[index:], b)
    eager = run(replace(spec, execution=replace(spec.execution, jit=False)))
    for a, b in zip(result.history, eager.history, strict=True):
        np.testing.assert_allclose(a, b, atol=2e-12, rtol=3e-11)
    windows = list(iter_windows(spec, WindowPolicy(3, "full")))
    for key in model.STATE_TYPE._fields:
        actual = np.concatenate(
            [getattr(w.history, key)[0 if i == 0 else 1 :] for i, w in enumerate(windows)]
        )
        np.testing.assert_array_equal(actual, getattr(result.history, key))
    for key in vars(result.observations):
        actual = np.concatenate([getattr(w.observations, key) for w in windows])
        np.testing.assert_array_equal(actual, getattr(result.observations, key))


def test_future_branch_nonzero_blocked_history_and_no_state_jump():
    case = short(controls=False)
    spec = spec_for(case)
    result = run(spec)
    at = 0.0005
    cp = result.checkpoint_at(at)
    assert np.any(cp.state.membrane_transferred != 0)
    changes = (ChannelChange(0, 1), ChannelChange(at, 0))
    changed = replace(spec, experiment=replace(spec.experiment, membranes=(changes,)))
    branch = run(changed, branch_checkpoint(spec, cp, changed))
    for key in ("amount_increment", "membrane_transferred", "membrane_dissipated_energy_pJ"):
        expected = np.asarray(getattr(cp.state, key))
        for group in (branch.history, branch.observations):
            values = getattr(group, key)
            np.testing.assert_array_equal(values, np.broadcast_to(expected, values.shape))
    assert not np.array_equal(
        branch.history.extracellular_amount_increment[0],
        branch.history.extracellular_amount_increment[-1],
    )
    invalid = replace(
        changed, experiment=replace(changed.experiment, membranes=((ChannelChange(0, 0),),))
    )
    with pytest.raises(ConfigError, match="rewrite"):
        branch_checkpoint(spec, cp, invalid)


@pytest.mark.parametrize("name", ["single_outside", "pure_bulk"])
def test_terminal_and_empty_observation_continuation(name):
    spec = spec_for(short(name, controls=False), samples=[0, 0.0001])
    result = run(spec)
    resumed = run(spec, result.final)
    assert len(resumed.times) == 1 and len(resumed.observations.times) == 0
    for a, b in zip(result.final.state, resumed.history, strict=True):
        np.testing.assert_array_equal(a, b[0])


def test_heterogeneous_cohort_restart_and_independent_clock_windows(tmp_path):
    sizes = dict(capacity=3, membrane_capacity=4, extracellular_capacity=4, face_capacity=4)
    specs = [
        spec_for(short(name, end=end), capacities=sizes)
        for name, end in (
            ("single_outside", 0.001),
            ("two_cells_chain", 0.0015),
            ("pure_bulk", 0.002),
        )
    ]
    batch = BatchSpec(tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs)), 3, 1000, 2**29)
    result = run_batch(batch)
    for world in result.worlds.values():
        scalar = run(world.spec)
        for a, b in zip(scalar.history, world.history, strict=True):
            np.testing.assert_allclose(a, b, atol=2e-12, rtol=3e-11)
    checkpoints = {i: world.checkpoint_at(0.0005) for i, world in result.worlds.items()}
    write_batch_snapshot(tmp_path / "snapshot", batch, checkpoints)
    saved = load_batch_snapshot(tmp_path / "snapshot")
    restored = run_batch(saved.spec, saved.checkpoints)
    for i, world in restored.worlds.items():
        original = result.worlds[i]
        at = int(np.flatnonzero(original.times == 0.0005)[0])
        for a, b in zip(original.history, world.history, strict=True):
            np.testing.assert_array_equal(a[at:], b)
    rounds = list(iter_batch_windows(batch, WindowPolicy(3, "full")))
    for i, world in result.worlds.items():
        pieces = [r.worlds[i] for r in rounds if i in r.worlds]
        for key in model.STATE_TYPE._fields:
            actual = np.concatenate(
                [getattr(w.history, key)[0 if n == 0 else 1 :] for n, w in enumerate(pieces)]
            )
            np.testing.assert_allclose(actual, getattr(world.history, key), atol=2e-12, rtol=3e-11)
    for key in ("face_capacity", "extracellular_capacity", "membrane_capacity", "capacity"):
        raw = batch.to_dict()
        raw["worlds"][1]["simulation"]["execution"][key] += 1
        with pytest.raises(ConfigError, match=key):
            parse_batch(raw)


def test_gauge_orientation_and_species_permutation_do_not_change_physics():
    case = short("ternary_loop", controls=False)
    spec = spec_for(case)
    state, layout = model.initial_values(spec)
    held = control_values(spec, [0])[0]
    expected = model.rhs(state, held, layout, layout.active, xp=np)
    raw = spec.to_dict()
    raw["model"]["closure"]["gauge_reference"] = raw["model"]["extracellular"][0]["id"]
    raw["model"]["species"].reverse()
    raw["model"]["faces"].reverse()
    for f in raw["model"]["faces"]:
        f["sender"], f["receiver"] = f["receiver"], f["sender"]
    modified = parse_spec(raw)
    y, g = model.initial_values(modified)
    actual = model.rhs(y, control_values(modified, [0])[0], g, g.active, xp=np)
    for key in ("amount_increment", "extracellular_amount_increment", "membrane_transferred"):
        np.testing.assert_allclose(
            getattr(actual, key)[::-1], getattr(expected, key), atol=2e-12, rtol=3e-12
        )
    n = len(case.g.face_pairs)
    np.testing.assert_allclose(
        actual.face_transferred[::-1, :n][:, ::-1],
        -expected.face_transferred[:, :n],
        atol=2e-12,
        rtol=3e-12,
    )
    a, b = model.field_values(state, layout, xp=np), model.field_values(y, g, xp=np)
    count = len(case.outside)
    delta = a.potential_V[:count] - b.potential_V[:count]
    np.testing.assert_allclose(delta, np.full_like(delta, delta[0]), atol=1e-14)


def test_component_charge_not_only_global_neutrality_is_guarded():
    spec = spec_for(short("pure_bulk", controls=False), padded=False)
    state, layout = model.initial_values(spec)
    state.extracellular_amount_increment[0, :2] = [1e-3, -1e-3]
    assert np.sum(state.extracellular_amount_increment) == 0
    assert not model.domain_valid(state, layout, layout.active, xp=np)
    with pytest.raises(NumericalError):
        model.check_values(state, spec)


def test_negative_stage_is_refused_before_invalid_logarithms():
    spec = spec_for(short("line_32", controls=False))
    cp = initialise(spec)
    held = control_values(spec, [0])[0]
    state, layout = model.initial_values(spec)
    rate = model.rhs(state, held, layout, layout.active, xp=np)
    amount = layout.extracellular_amount_reference
    decreasing = rate.extracellular_amount_increment < 0
    # Construct a first-half-stage depletion, rather than assuming the frozen
    # coarse cosine trajectory becomes unstable on its very first step.
    step = 4 * np.min(amount[decreasing] / -rate.extracellular_amount_increment[decreasing])
    _, valid = rk4_checked_step(
        model.rhs, model.domain_valid, cp.state, step, held, cp.layout, cp.layout.active
    )
    assert not bool(valid)


@pytest.mark.parametrize("kind", ["inventory", "voltage", "component"])
def test_whole_cubic_domain_not_only_endpoints(kind):
    spec = spec_for(short())
    y, layout = model.initial_values(spec)
    history = model.STATE_TYPE(*(np.stack((v, v)) for v in y))
    left = model.STATE_TYPE(*(np.zeros_like(v[:1]) for v in history))
    right = model.STATE_TYPE(*(np.zeros_like(v[:1]) for v in history))
    if kind == "inventory":
        left.extracellular_amount_increment[0, :, 0] = -1000
        right.extracellular_amount_increment[0, :, 0] = 1000
        message = "inventory"
    elif kind == "voltage":
        left.amount_increment[0, 0, 0], right.amount_increment[0, 0, 0] = 1, -1
        message = "voltage"
    else:
        left.extracellular_amount_increment[0, 0, 0] = 1e-4
        right.extracellular_amount_increment[0, 0, 0] = -1e-4
        message = "component"
    with pytest.raises(NumericalError, match=message):
        model.check_interpolants(np.array([0.0, 1.0]), history, left, right, layout)


@pytest.mark.parametrize("key", model.LAYOUT_TYPE._fields)
def test_every_layout_leaf_is_part_of_checkpoint_identity(key):
    spec = spec_for(short())
    cp = initialise(spec)
    fields = {k: np.asarray(v).copy() for k, v in cp.layout._asdict().items()}
    array = fields[key]
    array.flat[0] = not array.flat[0] if array.dtype == bool else array.flat[0] + 1
    with pytest.raises(ConfigError, match="layout"):
        validate_checkpoint(spec, replace(cp, layout=model.LAYOUT_TYPE(**fields)))


def test_cell_and_membrane_owner_order_normalizes_controls():
    raw = definition(short("two_cells_chain"))
    original = parse_spec(raw)
    raw["model"]["membranes"].reverse()
    raw["experiment"]["membrane_controls"].reverse()
    assert parse_spec(raw) == original
    assert canonical(
        short("two_cells_chain"), model.initial_values(original)[0]._asdict()
    ).shape == (short("two_cells_chain").size,)
