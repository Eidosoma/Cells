from dataclasses import replace
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core.runner import NumericalError, branch_checkpoint, run, timeline, validate_checkpoint
from cells.core.specs import ConfigError, ContactChange, InputChange, load_spec, parse_spec
from cells.core.state import initialise
from cells.coupling.passive import ContactParameters, edge_flux, scatter_exchange
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import passive_pair
from tests.reference_pair import exact_pair

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def pair_spec():
    return load_spec(ROOT / "configs/pair_exchange_active.json")


def pulse(spec):
    return replace(
        spec,
        experiment=replace(
            spec.experiment,
            contact=(
                ContactChange(0, 0),
                ContactChange(2.03, 1),
                ContactChange(5.07, 0),
            ),
        ),
    )


@pytest.mark.parametrize("case", ["active", "blocked", "release"])
def test_pair_round_trip(case):
    spec = load_spec(ROOT / f"configs/pair_exchange_{case}.json")
    assert parse_spec(spec.to_dict()) == spec
    assert len(timeline(spec)) == 241


@pytest.mark.parametrize(
    "path,value",
    [
        (("model", "population", "count"), 1),
        (("model", "population", "count"), True),
        (("model", "population", "cell_ids"), [101, 101]),
        (("model", "population", "cell_ids"), [101]),
        (("model", "population", "cell_ids"), [101, -1]),
        (("model", "population", "cell_ids"), [101, True]),
        (("model", "initial_state", "amount"), [8, -1]),
        (("model", "initial_state", "amount"), [float("nan"), 0]),
        (("model", "initial_state", "amount"), [1e308, 1e308]),
        (("model", "initial_state", "volume"), [1, 0]),
        (("model", "initial_state", "volume"), [1, float("inf")]),
        (("model", "initial_state", "volume"), [1e308, 1e308]),
        (("model", "initial_state", "amount"), [8, 0, 0]),
        (("model", "parameters", "contact", "contact_id"), False),
        (("model", "parameters", "contact", "from_cell_id"), 202),
        (("model", "parameters", "contact", "to_cell_id"), 999),
        (("model", "parameters", "contact", "permeability"), -0.4),
        (("model", "parameters", "contact", "permeability"), "0.4"),
        (("model", "parameters", "contact", "hidden_voltage"), 5),
        (("model", "units", "volume"), "L"),
        (("experiment", "source", "kind"), "prescribed_external_amount_rate"),
        (("experiment", "contact", "kind"), "voltage_gated"),
        (("experiment", "contact", "schedule"), []),
        (("experiment", "contact", "schedule"), [{"time": 1, "open_fraction": 1}]),
        (("experiment", "contact", "schedule"), [{"time": 0, "open_fraction": 1.1}]),
        (("experiment", "contact", "schedule"), [{"time": 0, "open_fraction": -1}]),
        (("experiment", "contact", "schedule"), [{"time": 0, "open_fraction": True}]),
        (
            ("experiment", "contact", "schedule"),
            [{"time": 0, "open_fraction": 1}, {"time": 0, "open_fraction": 0}],
        ),
        (
            ("experiment", "contact", "schedule"),
            [{"time": 0, "open_fraction": 1}, {"time": 13, "open_fraction": 0}],
        ),
        (("execution", "capacity"), 1),
        (("execution", "edge_capacity"), 0),
        (("execution", "edge_capacity"), True),
    ],
)
def test_invalid_pair_contract(pair_spec, path, value):
    data = pair_spec.to_dict()
    node = data
    for part in path[:-1]:
        node = node[part]
    node[path[-1]] = value
    with pytest.raises(ConfigError):
        parse_spec(data)


def test_python_api_cannot_add_undeclared_channels(pair_spec, spec):
    with pytest.raises(ConfigError):
        run(
            replace(
                pair_spec, experiment=replace(pair_spec.experiment, source=(InputChange(0, 1),))
            )
        )
    with pytest.raises(ConfigError):
        run(replace(spec, experiment=replace(spec.experiment, contact=(ContactChange(0, 1),))))
    with pytest.raises(ConfigError):
        run(replace(spec, execution=replace(spec.execution, edge_capacity=1)))


def test_flux_is_reciprocal_and_accounts_in_amounts(pair_spec):
    initial = initialise(pair_spec)
    params = passive_pair.parameters(pair_spec, initial.layout)
    result = passive_pair.rhs(initial.state, 1, params, initial.layout.active)
    np.testing.assert_allclose(result.amount, [-3.2, 3.2], rtol=0, atol=1e-15)
    np.testing.assert_allclose(result.transferred, [3.2], rtol=0, atol=1e-15)
    # Concentration rates are NOT equal/opposite when volumes differ.
    np.testing.assert_allclose(result.amount / initial.layout.volume, [-3.2, 3.2 / 3])
    np.testing.assert_array_equal(initial.state.amount, [8, 0])


@pytest.mark.parametrize(
    "amounts,volumes,g,fraction",
    [
        ((8, 0), (1, 3), 0.4, 1),
        ((0, 8), (1, 3), 0.4, 1),
        ((8, 0), (1, 1), 0.4, 1),
        ((8, 0), (1, 3), 0, 1),
        ((8, 0), (1, 3), 0.4, 0),
        ((8, 0), (1, 3), 0.4, 0.3),
        ((2, 6), (1, 3), 0.4, 1),
        ((0, 0), (1, 3), 0.4, 1),
    ],
)
def test_pair_matches_closed_form(pair_spec, amounts, volumes, g, fraction):
    spec = replace(
        pair_spec,
        model=replace(pair_spec.model, initial_amounts=amounts, volumes=volumes, permeability=g),
        experiment=replace(pair_spec.experiment, contact=(ContactChange(0, fraction),)),
    )
    result = run(spec)
    for actual, expected in zip(result.history, exact_pair(spec, result.times), strict=True):
        np.testing.assert_allclose(actual, expected, atol=6e-8, rtol=0)
    assert result.max_balance_error < 1e-12
    assert result.diagnostics["max_exchange_accounting_error_fmol"] < 1e-12
    assert np.isfinite(result.amount).all() and np.all(result.amount >= 0)
    if fraction == 0 or g == 0 or amounts == (2, 6):
        np.testing.assert_array_equal(result.amount, np.broadcast_to(amounts, result.amount.shape))
        assert np.all(result.history.transferred == 0)


def test_equilibrium_equalizes_concentration_not_amount(pair_spec):
    spec = replace(pair_spec, experiment=replace(pair_spec.experiment, end_time=100))
    result = run(spec)
    np.testing.assert_allclose(result.amount[-1], [2, 6], atol=1e-12, rtol=0)
    np.testing.assert_allclose(
        result.amount[-1] / pair_spec.model.volumes, [2, 2], atol=1e-12, rtol=0
    )


def test_fourth_order_transient_refinement(pair_spec):
    spec = replace(
        pair_spec, experiment=replace(pair_spec.experiment, end_time=2, observation_times=(0, 2))
    )
    errors = []
    for dt in (0.4, 0.2, 0.1):
        result = run(replace(spec, execution=replace(spec.execution, dt=dt)))
        expected, _ = exact_pair(spec, result.times)
        errors.append(float(np.max(np.abs(result.amount - expected))))
    assert 14 < errors[0] / errors[1] < 20
    assert 14 < errors[1] / errors[2] < 20


def test_contact_events_split_steps_and_preserve_short_cues(pair_spec):
    spec = pulse(pair_spec)
    result = run(spec)
    assert 2.03 in result.times and 5.07 in result.times
    np.testing.assert_allclose(result.amount, exact_pair(spec, result.times)[0], atol=2e-8, rtol=0)
    short = replace(
        pair_spec,
        execution=replace(pair_spec.execution, dt=0.2),
        experiment=replace(
            pair_spec.experiment,
            end_time=0.333,
            observation_times=(0, 0.333),
            contact=(ContactChange(0, 0), ContactChange(0.103, 1), ContactChange(0.104, 0)),
        ),
    )
    result = run(short)
    assert result.final.time == 0.333
    assert result.history.transferred[-1, 0] > 0
    np.testing.assert_allclose(
        result.amount, exact_pair(short, result.times)[0], atol=3e-15, rtol=0
    )


def test_final_time_contact_change_has_no_integrated_effect(pair_spec):
    changed = replace(
        pair_spec,
        experiment=replace(
            pair_spec.experiment, contact=(ContactChange(0, 1), ContactChange(12, 0))
        ),
    )
    original, final_block = run(pair_spec), run(changed)
    for a, b in zip(original.history, final_block.history, strict=True):
        np.testing.assert_array_equal(a, b)
    assert final_block.observations.contact_flux[-1, 0] == 0
    assert final_block.final.event_index == 1


def test_padding_and_observers_leave_dynamics_alone(pair_spec):
    original = run(pair_spec)
    padded = run(
        replace(pair_spec, execution=replace(pair_spec.execution, capacity=8, edge_capacity=5))
    )
    observed = run(
        replace(
            pair_spec, experiment=replace(pair_spec.experiment, observation_times=(0.015, 1, 6, 12))
        )
    )
    np.testing.assert_allclose(original.amount, padded.amount[:, :2], atol=2e-14, rtol=0)
    np.testing.assert_allclose(
        original.history.transferred, padded.history.transferred[:, :1], atol=2e-14, rtol=0
    )
    assert np.all(padded.amount[:, 2:] == 0) and np.all(padded.history.transferred[:, 1:] == 0)
    assert np.all(padded.observations.contact_flux[:, 1:] == 0)
    assert np.all(padded.observations.open_fraction[:, 1:] == 0)
    for a, b in zip(original.history, observed.history, strict=True):
        np.testing.assert_array_equal(a, b)
    assert observed.observations.amount[0, 0] == np.interp(
        0.015, observed.times, observed.amount[:, 0]
    )
    with pytest.raises(ValueError):
        original.amount[0, 0] = 99
    observed.observations.amount[0, 0] = 99
    assert float(observed.final.state.amount[0]) != 99


def test_eager_jit_and_cpu(pair_spec):
    spec = replace(
        pair_spec, experiment=replace(pair_spec.experiment, end_time=1, observation_times=(0, 1))
    )
    eager, compiled = run(replace(spec, execution=replace(spec.execution, jit=False))), run(spec)
    for a, b in zip(eager.history, compiled.history, strict=True):
        np.testing.assert_allclose(a, b, atol=3e-15, rtol=0)
    assert all(value.device.platform == "cpu" for value in compiled.final.state)


def test_orientation_and_cell_order_are_not_biological_direction(pair_spec):
    original = run(pair_spec)
    reversed_edge = run(
        replace(pair_spec, model=replace(pair_spec.model, from_cell_id=202, to_cell_id=101))
    )
    np.testing.assert_array_equal(original.amount, reversed_edge.amount)
    np.testing.assert_array_equal(original.history.transferred, -reversed_edge.history.transferred)
    permuted = run(
        replace(
            pair_spec,
            model=replace(
                pair_spec.model, cell_ids=(202, 101), volumes=(3, 1), initial_amounts=(0, 8)
            ),
        )
    )
    np.testing.assert_array_equal(original.amount, permuted.amount[:, ::-1])
    np.testing.assert_array_equal(original.history.transferred, permuted.history.transferred)


def test_stability_guard_uses_effective_event_split_steps(pair_spec):
    high = replace(pair_spec, model=replace(pair_spec.model, permeability=1000))
    with pytest.raises(ConfigError, match="step"):
        timeline(high)
    blocked = replace(high, experiment=replace(high.experiment, contact=(ContactChange(0, 0),)))
    assert np.all(run(blocked).history.transferred == 0)
    short = replace(
        high,
        experiment=replace(
            high.experiment,
            contact=(ContactChange(0, 0), ContactChange(0.010, 1), ContactChange(0.0101, 0)),
        ),
    )
    result = run(short)
    assert result.history.transferred[-1, 0] > 0


@pytest.mark.parametrize("mode", ["cells", "edges", "trace", "concentration", "flux"])
def test_resource_and_derived_value_guards(pair_spec, mode):
    if mode == "cells":
        spec = replace(pair_spec, execution=replace(pair_spec.execution, capacity=10**7))
    elif mode == "edges":
        spec = replace(pair_spec, execution=replace(pair_spec.execution, edge_capacity=10**7))
    elif mode == "trace":
        spec = replace(pair_spec, execution=replace(pair_spec.execution, max_trace_bytes=100))
    elif mode == "concentration":
        spec = replace(pair_spec, model=replace(pair_spec.model, volumes=(1e-310, 1)))
    else:
        spec = replace(pair_spec, model=replace(pair_spec.model, permeability=1e308))
    with pytest.raises(ConfigError):
        run(spec)


@pytest.mark.parametrize("time", [0, 2.03, 5.07, 6, 12])
def test_pair_restart_includes_cell_and_contact_state(pair_spec, tmp_path, time):
    spec = pulse(pair_spec)
    original = run(spec)
    cp = original.checkpoint_at(time)
    path = write_snapshot(tmp_path / "snapshot", spec, cp)
    restored = load_snapshot(path)
    result = run(restored.spec, restored.checkpoint)
    for whole, suffix in zip(original.history, result.history, strict=True):
        np.testing.assert_array_equal(whole[cp.step_index :], suffix)
    assert restored.checkpoint.state.amount.shape == (2,)
    assert restored.checkpoint.state.transferred.shape == (1,)


def test_future_contact_branch_changes_only_its_continuation(pair_spec):
    whole = run(pair_spec)
    checkpoint = whole.checkpoint_at(6)
    changed = load_spec(ROOT / "configs/pair_exchange_release.json")
    branch = run(changed, branch_checkpoint(pair_spec, checkpoint, changed))
    np.testing.assert_array_equal(
        branch.amount, np.broadcast_to(whole.amount[120], branch.amount.shape)
    )
    assert whole.history.transferred[-1, 0] > branch.history.transferred[-1, 0]
    np.testing.assert_array_equal(branch.history.transferred[0], checkpoint.state.transferred)
    np.testing.assert_array_equal(run(pair_spec, checkpoint).amount, whole.amount[120:])
    with pytest.raises(ConfigError):
        branch_checkpoint(
            pair_spec, checkpoint, replace(changed, model=replace(changed.model, permeability=1))
        )
    with pytest.raises(ConfigError, match="before"):
        branch_checkpoint(
            pair_spec,
            checkpoint,
            replace(
                changed, experiment=replace(changed.experiment, contact=(ContactChange(0, 0),))
            ),
        )


def test_off_grid_branch_must_retain_accepted_boundary(pair_spec):
    spec = pulse(pair_spec)
    checkpoint = run(spec).checkpoint_at(5.07)
    changed = replace(
        spec, experiment=replace(spec.experiment, contact=spec.experiment.contact[:2])
    )
    with pytest.raises(ConfigError, match="integration boundary"):
        branch_checkpoint(spec, checkpoint, changed)
    changed = replace(
        changed,
        experiment=replace(
            changed.experiment, contact=(*changed.experiment.contact, ContactChange(5.07, 1))
        ),
    )
    branch_checkpoint(spec, checkpoint, changed)


def test_invalid_transfer_and_topology_cannot_restore(pair_spec):
    saved = run(pair_spec).checkpoint_at(6)
    for layout in (
        saved.layout._replace(senders=np.array([1])),
        saved.layout._replace(contact_ids=np.array([99])),
        saved.layout._replace(contact_active=np.array([False])),
    ):
        with pytest.raises(ConfigError):
            validate_checkpoint(pair_spec, replace(saved, layout=layout))
    for transfer in (np.array([float("nan")]), np.array([999.0])):
        with pytest.raises(NumericalError):
            validate_checkpoint(
                pair_spec, replace(saved, state=saved.state._replace(transferred=transfer))
            )
    with pytest.raises(ConfigError, match="shape"):
        validate_checkpoint(
            pair_spec, replace(saved, state=saved.state._replace(transferred=np.zeros(2)))
        )


def test_artifacts_keep_physical_contact_when_blocked(pair_spec, tmp_path):
    blocked = replace(
        pair_spec, experiment=replace(pair_spec.experiment, contact=(ContactChange(0, 0),))
    )
    summary = write_run(tmp_path / "blocked", run(blocked))
    assert summary["active_cells"] == 2 and summary["physical_contacts"] == 1
    assert summary["cell_ids"] == [101, 202]
    with np.load(tmp_path / "blocked/trajectory.npz", allow_pickle=False) as archive:
        assert archive["contact_ids"].tolist() == [7]
        assert archive["contact_active"].tolist() == [True]
        assert np.all(archive["observed_open_fraction"] == 0)
        assert np.all(archive["transferred"] == 0)


def test_shared_endpoint_scatter_and_inactive_masks(pair_spec):
    initialise(pair_spec)
    senders, receivers = jnp.array([0, 0, 2]), jnp.array([1, 1, 1])
    change = jax.jit(scatter_exchange)(
        jnp.array([1.0, 2.0, -4.0]), senders, receivers, jnp.zeros(3)
    )
    np.testing.assert_array_equal(change, [-3, -1, 4])
    assert float(change.sum()) == 0
    params = ContactParameters(
        jnp.ones(3), senders, receivers, jnp.ones(3), jnp.array([True, False, True])
    )
    flux = edge_flux(jnp.array([3.0, 0.0, 1.0]), 1, params, jnp.array([True, True, False]))
    np.testing.assert_array_equal(flux, [3, 0, 0])


def test_contact_kernel_can_batch_independent_worlds(pair_spec):
    initial = initialise(pair_spec)
    params = passive_pair.parameters(pair_spec, initial.layout)
    amounts = jnp.array([[8.0, 0.0], [0.0, 8.0], [2.0, 6.0]])
    batched = jax.jit(jax.vmap(lambda a: edge_flux(a, 1, params, initial.layout.active)))(amounts)
    np.testing.assert_allclose(batched[:, 0], [3.2, -3.2 / 3, 0], atol=1e-15, rtol=0)
