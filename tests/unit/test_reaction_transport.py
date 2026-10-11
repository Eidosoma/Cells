import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.core.errors import NumericalError
from cells.core.runner import branch_checkpoint, run, timeline, validate_checkpoint
from cells.core.schedule import control_values
from cells.core.specs import (
    ConfigError,
    ContactChange,
    GraphContactChange,
    InputChange,
    load_spec,
    parse_spec,
)
from cells.core.state import ReactionTransportState, initialise
from cells.coupling.passive import ContactParameters, edge_flux, scatter_exchange
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import reaction_transport as model
from cells.observers import sample_history
from cells.processes.reactions import reversible_rate
from tests.reference_reaction_transport import generator, reference

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def graph_data():
    return json.loads((ROOT / "configs/reaction_transport_chain.json").read_text())


def constant_control(data, values, end=12):
    data["experiment"].update(end_time=end, observation_times=[0, end])
    data["experiment"]["contact"]["schedule"] = [{"time": 0, "open_fractions": values}]
    return data


def assert_reference(result, atol=4e-8):
    n, e = len(result.spec.model.cell_ids), len(result.spec.model.contacts)
    expected = reference(result.spec, result.times)
    for actual, wanted in zip(
        (
            result.history.amount[..., :n],
            result.history.transferred[..., :e],
            result.history.converted[..., :n],
        ),
        expected,
        strict=True,
    ):
        np.testing.assert_allclose(actual, wanted, atol=atol, rtol=0)
    return expected


@pytest.mark.parametrize("name", ["single", "pair", "chain", "release"])
def test_definition_round_trip_and_axes(name):
    spec = load_spec(ROOT / f"configs/reaction_transport_{name}.json")
    assert parse_spec(spec.to_dict()) == spec
    state = initialise(spec)
    assert state.state.amount.shape == (2, spec.execution.capacity)
    assert state.state.transferred.shape == (2, spec.execution.edge_capacity)
    assert state.state.converted.shape == (spec.execution.capacity,)
    assert all(v.dtype == np.float64 for v in state.state)
    assert state.layout.ids.dtype == np.int64
    assert_reference(run(spec))


@pytest.mark.parametrize(
    "path,value",
    [
        (("model", "species"), ["A", "A"]),
        (("model", "species"), ["A", "B", "C"]),
        (("model", "species"), [[], "B"]),
        (("model", "species"), ["", "B"]),
        (("model", "species"), ["exec()", "B"]),
        (("model", "population", "count"), 0),
        (("model", "population", "count"), True),
        (("model", "population", "count"), 2),
        (("model", "population", "cell_ids"), [101, 101, 303]),
        (("model", "population", "cell_ids"), [101, True, 303]),
        (("model", "initial_state", "amount"), [[1, 2, 3]]),
        (("model", "initial_state", "amount"), [[1, 2], [3, 4]]),
        (("model", "initial_state", "amount"), [[-1, 0, 0], [0, 0, 0]]),
        (("model", "initial_state", "amount"), [[1e308, 1e308, 0], [0, 0, 0]]),
        (("model", "initial_state", "volume"), [1, 0, 2]),
        (("model", "initial_state", "volume"), [1e308, 1e308, 1]),
        (("model", "units", "time"), "bitsey_time_unit"),
        (("model", "parameters", "reaction", "from_species"), "missing"),
        (("model", "parameters", "reaction", "to_species"), "A"),
        (("model", "parameters", "reaction", "forward_rate"), [1, 2]),
        (("model", "parameters", "reaction", "reverse_rate"), [0, float("inf"), 0]),
        (("model", "parameters", "contacts"), {}),
        (("model", "parameters", "contacts", 0, "contact_id"), 9),
        (("model", "parameters", "contacts", 0, "from_cell_id"), 999),
        (("model", "parameters", "contacts", 0, "to_cell_id"), 101),
        (("model", "parameters", "contacts", 0, "permeability"), [0.1]),
        (("model", "parameters", "contacts", 0, "permeability"), [True, 0]),
        (("model", "parameters", "contacts", 0, "permeability"), [0, -1]),
        (("experiment", "source"), {"kind": "prescribed_external_amount_rate", "schedule": []}),
        (("experiment", "contact", "kind"), "prescribed_open_fraction"),
        (("experiment", "contact", "contact_ids"), [7, 7]),
        (("experiment", "contact", "contact_ids"), [7, 100]),
        (("experiment", "contact", "schedule"), []),
        (("experiment", "contact", "schedule", 0, "time"), 1),
        (("experiment", "contact", "schedule", 1, "time"), 0),
        (("experiment", "contact", "schedule", 2, "time"), 13),
        (("experiment", "contact", "schedule", 0, "open_fractions"), [1]),
        (("experiment", "contact", "schedule", 0, "open_fractions"), [1, 1.1]),
        (("experiment", "contact", "schedule", 0, "open_fractions"), [True, 0]),
        (("execution", "capacity"), 2),
        (("execution", "edge_capacity"), 1),
        (("execution", "edge_capacity"), -1),
        (("execution", "edge_capacity"), False),
    ],
)
def test_invalid_graph_definitions(graph_data, path, value):
    node = graph_data
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(ConfigError):
        parse_spec(graph_data)


def test_python_api_cannot_drop_or_substitute_controls(graph_data):
    spec = parse_spec(graph_data)
    for changed in (
        replace(spec.experiment, source=(InputChange(0, 1),)),
        replace(spec.experiment, contact=(ContactChange(0, 1),)),
        replace(spec.experiment, contact=()),
    ):
        with pytest.raises(ConfigError):
            run(replace(spec, experiment=changed))


def test_contact_ids_resolve_control_order_and_no_alias(graph_data):
    original = parse_spec(graph_data)
    control = graph_data["experiment"]["contact"]
    control["contact_ids"].reverse()
    for entry in control["schedule"]:
        entry["open_fractions"].reverse()
    changed = parse_spec(graph_data)
    assert changed == original and changed.fingerprint == original.fingerprint
    control["schedule"][0]["open_fractions"][0] = 0
    assert changed.experiment.contact[0].open_fractions == (1, 0.5)


def test_processes_share_stage_state_and_accumulate(graph_data):
    spec = parse_spec(graph_data)
    checkpoint = initialise(spec)
    before = tuple(np.array(v) for v in checkpoint.state)
    params = model.parameters(spec, checkpoint.layout)
    slope = model.rhs(checkpoint.state, np.array([1, 0.5]), params, checkpoint.layout.active)
    np.testing.assert_allclose(slope.converted, [1.6, -0.06, 0.15], atol=1e-15, rtol=0)
    np.testing.assert_allclose(
        slope.transferred, [[3.2, -0.05], [-1 / 15, 1 / 60]], atol=1e-15, rtol=0
    )
    np.testing.assert_allclose(
        slope.amount, [[-4.8, 3.31, -0.2], [5 / 3, -43 / 300, 1 / 6]], atol=1e-15, rtol=0
    )
    assert abs(np.sum(slope.amount)) < 2e-15
    for a, b in zip(before, checkpoint.state, strict=True):
        np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize(
    "variant",
    [
        "combined",
        "reaction_only",
        "transport_only",
        "one_way",
        "zero",
        "blocked",
        "equal_volume",
        "parallel_edges",
    ],
)
def test_independent_full_state_reference(graph_data, variant):
    reaction = graph_data["model"]["parameters"]["reaction"]
    if variant in ("transport_only", "zero"):
        reaction["forward_rate"] = reaction["reverse_rate"] = [0, 0, 0]
    if variant == "one_way":
        reaction["reverse_rate"] = [0, 0, 0]
    if variant in ("reaction_only", "blocked", "zero"):
        constant_control(graph_data, [0, 0])
    if variant == "equal_volume":
        graph_data["model"]["initial_state"]["volume"] = [1, 1, 1]
    if variant == "parallel_edges":
        graph_data["model"]["parameters"]["contacts"][1].update(from_cell_id=101, to_cell_id=202)
    result = run(parse_spec(graph_data))
    if variant in ("equal_volume", "parallel_edges"):
        result = assert_finer_accuracy(result)
    assert_reference(result)
    assert result.diagnostics["max_balance_error_fmol"] < 1e-12
    assert result.diagnostics["max_process_accounting_error_fmol"] < 1e-12
    if variant == "transport_only":
        np.testing.assert_allclose(
            result.amount.sum(axis=-1),
            np.broadcast_to([9, 2], (len(result.times), 2)),
            atol=1e-13,
            rtol=0,
        )
        assert np.all(result.history.converted == 0)
    if variant == "zero":
        np.testing.assert_array_equal(
            result.amount, np.broadcast_to(result.amount[0], result.amount.shape)
        )


def test_reaction_only_closed_form_and_empty_edges():
    spec = load_spec(ROOT / "configs/reaction_transport_single.json")
    result = run(spec)
    expected_a = 1.6 + 6.4 * np.exp(-0.25 * result.times)
    np.testing.assert_allclose(result.amount[:, 0, 0], expected_a, atol=1e-9, rtol=0)
    np.testing.assert_allclose(result.amount[:, 1, 0], 8 - expected_a, atol=1e-9, rtol=0)
    assert result.history.transferred.shape == (241, 2, 0)
    assert result.observations.contact_flux.shape == (8, 2, 0)
    assert result.observations.open_fraction.shape == (8, 0)


def test_three_cell_disconnection_and_route_specific_control(graph_data):
    constant_control(graph_data, [1, 0])
    original = run(parse_spec(graph_data))
    changed = deepcopy(graph_data)
    changed["model"]["initial_state"]["amount"][0][:2] = [40, 10]
    altered = run(parse_spec(changed))
    np.testing.assert_array_equal(original.amount[:, :, 2], altered.amount[:, :, 2])
    assert np.all(original.history.transferred[:, :, 1] == 0)
    assert np.any(original.history.transferred[:, :, 0] != 0)
    assert_reference(original)


def test_population_size_is_not_hardcoded(graph_data):
    graph_data["model"]["population"] = {"count": 5, "cell_ids": [11, 22, 33, 44, 55]}
    graph_data["model"]["initial_state"] = {
        "amount": [[8, 0, 1, 2, 3], [1, 2, 0, 4, 5]],
        "volume": [1, 3, 2, 1, 4],
    }
    params = graph_data["model"]["parameters"]
    params["reaction"]["forward_rate"] = [0.1, 0.2, 0, 0.3, 0.05]
    params["reaction"]["reverse_rate"] = [0.05, 0.1, 0.4, 0, 0.1]
    params["contacts"][0].update(from_cell_id=11, to_cell_id=44)
    params["contacts"][1].update(from_cell_id=22, to_cell_id=44)
    graph_data["execution"]["capacity"] = 5
    assert_reference(assert_finer_accuracy(run(parse_spec(graph_data))))


def assert_finer_accuracy(coarse):
    # Faster variants exceeded 4e-8 at dt=.05. Refine their numerical resolution,
    # retain the error limit, and require the expected convergence rate.
    coarse_error = np.max(np.abs(coarse.amount - reference(coarse.spec, coarse.times)[0]))
    fine = run(replace(coarse.spec, execution=replace(coarse.spec.execution, dt=0.025)))
    fine_error = np.max(np.abs(fine.amount - reference(fine.spec, fine.times)[0]))
    assert 14 < coarse_error / fine_error < 20
    assert_reference(fine)
    return fine


@pytest.mark.parametrize("kind", ["cells", "species", "edges", "orientation", "names"])
def test_identity_and_representation_invariance(graph_data, kind):
    baseline = run(parse_spec(graph_data))
    data = graph_data["model"]
    cell_order, species_order, edge_order = [0, 1, 2], [0, 1], [0, 1]
    if kind == "cells":
        cell_order = [2, 0, 1]
        data["population"]["cell_ids"] = [data["population"]["cell_ids"][i] for i in cell_order]
        data["initial_state"]["amount"] = [
            [row[i] for i in cell_order] for row in data["initial_state"]["amount"]
        ]
        data["initial_state"]["volume"] = [data["initial_state"]["volume"][i] for i in cell_order]
        for name in ("forward_rate", "reverse_rate"):
            data["parameters"]["reaction"][name] = [
                data["parameters"]["reaction"][name][i] for i in cell_order
            ]
    if kind == "species":
        species_order = [1, 0]
        data["species"].reverse()
        data["initial_state"]["amount"].reverse()
        for edge in data["parameters"]["contacts"]:
            edge["permeability"].reverse()
    if kind == "edges":
        edge_order = [1, 0]
        data["parameters"]["contacts"].reverse()  # Control IDs keep their own order.
    if kind == "orientation":
        for edge in data["parameters"]["contacts"]:
            edge["from_cell_id"], edge["to_cell_id"] = edge["to_cell_id"], edge["from_cell_id"]
    if kind == "names":
        data["species"] = ["substrate", "product"]
        data["parameters"]["reaction"].update(from_species="substrate", to_species="product")
    result = run(parse_spec(graph_data))
    expected = baseline.amount[:, species_order][:, :, cell_order]
    np.testing.assert_allclose(result.amount, expected, atol=2e-13, rtol=0)
    expected_q = baseline.history.transferred[:, species_order][:, :, edge_order]
    np.testing.assert_allclose(
        result.history.transferred,
        -expected_q if kind == "orientation" else expected_q,
        atol=2e-13,
        rtol=0,
    )
    np.testing.assert_allclose(
        result.history.converted, baseline.history.converted[:, cell_order], atol=2e-13, rtol=0
    )


def test_refinement_and_noncommuting_event_order(graph_data):
    spec = parse_spec(constant_control(graph_data, [1, 0.5], end=2))
    errors = []
    for dt in (0.4, 0.2, 0.1):
        result = run(replace(spec, execution=replace(spec.execution, dt=dt)))
        expected = reference(result.spec, result.times)[0]
        errors.append(np.max(np.abs(result.amount - expected)))
    assert all(14 < a / b < 20 for a, b in zip(errors, errors[1:], strict=False))
    g0, g1 = generator(spec, [1, 0]), generator(spec, [0, 1])
    assert np.max(np.abs(g0 @ g1 - g1 @ g0)) > 0.01
    first = replace(
        spec,
        experiment=replace(
            spec.experiment, contact=(GraphContactChange(0, (1, 0)), GraphContactChange(1, (0, 1)))
        ),
    )
    second = replace(
        first,
        experiment=replace(
            first.experiment, contact=(GraphContactChange(0, (0, 1)), GraphContactChange(1, (1, 0)))
        ),
    )
    a, b = run(first), run(second)
    assert_reference(a)
    assert_reference(b)
    assert np.max(np.abs(a.amount[-1] - b.amount[-1])) > 0.01


def test_padding_sampling_empty_observations_and_jit(graph_data):
    spec = parse_spec(constant_control(graph_data, [1, 0.5], end=1))
    plain = run(spec)
    padded = run(replace(spec, execution=replace(spec.execution, capacity=7, edge_capacity=5)))
    eager = run(replace(spec, execution=replace(spec.execution, jit=False)))
    sampled = run(
        replace(spec, experiment=replace(spec.experiment, observation_times=(0.013, 0.37, 1)))
    )
    for a, p, e, o, count in zip(
        plain.history, padded.history, eager.history, sampled.history, [3, 2, 3], strict=True
    ):
        np.testing.assert_allclose(a, p[..., :count], atol=1e-13, rtol=0)
        assert np.all(p[..., count:] == 0)
        np.testing.assert_allclose(a, e, atol=1e-13, rtol=0)
        np.testing.assert_array_equal(a, o)
        assert not a.flags.writeable
    assert np.all(padded.observations.open_fraction[:, 2:] == 0)
    assert np.all(padded.observations.contact_flux[:, :, 2:] == 0)
    assert all(v.device.platform == "cpu" for v in plain.final.state)
    early_obs = replace(spec, experiment=replace(spec.experiment, observation_times=(0,)))
    empty = run(early_obs, plain.final)
    assert empty.observations.amount.shape == (0, 2, 3)
    assert empty.observations.contact_flux.shape == (0, 2, 2)
    np.testing.assert_allclose(
        sampled.observations.amount[0],
        plain.amount[0] * 0.74 + plain.amount[1] * 0.26,
        atol=1e-15,
        rtol=0,
    )


def test_empty_edge_padding_and_general_observer_axes():
    spec = load_spec(ROOT / "configs/reaction_transport_single.json")
    plain = run(spec)
    padded = run(replace(spec, execution=replace(spec.execution, capacity=4, edge_capacity=3)))
    np.testing.assert_allclose(plain.amount, padded.amount[..., :1], atol=1e-13, rtol=0)
    assert not np.any(padded.history.transferred)
    values = np.arange(48.0).reshape(2, 2, 3, 4)
    np.testing.assert_array_equal(sample_history([0, 1], values, [0.5]), values.mean(axis=0)[None])
    assert sample_history([0, 1], np.zeros((2, 2, 0)), [0.5]).shape == (1, 2, 0)


def test_event_sliver_and_final_time_controls(graph_data):
    data = constant_control(graph_data, [0, 0], end=1)
    data["experiment"]["contact"]["schedule"] += [
        {"time": 0.203, "open_fractions": [1, 0]},
        {"time": 0.204, "open_fractions": [0, 0]},
    ]
    spec = parse_spec(data)
    result = run(spec)
    assert {0.203, 0.204}.issubset(set(result.times))
    assert np.max(np.abs(result.history.transferred[-1])) > 0
    assert_reference(result)
    changed = replace(
        spec,
        experiment=replace(
            spec.experiment, contact=(*spec.experiment.contact, GraphContactChange(1, (1, 1)))
        ),
    )
    final_event = run(changed)
    for a, b in zip(result.history, final_event.history, strict=True):
        np.testing.assert_array_equal(a, b)
    assert np.all(result.observations.contact_flux[-1] == 0)
    assert np.any(final_event.observations.contact_flux[-1] != 0)


@pytest.mark.parametrize("time", [0, 2.03, 5.07, 6, 12])
def test_complete_replay(graph_data, tmp_path, time):
    spec = parse_spec(graph_data)
    whole = run(spec)
    checkpoint = whole.checkpoint_at(time)
    write_snapshot(tmp_path / "snapshot", spec, checkpoint)
    saved = load_snapshot(tmp_path / "snapshot")
    replay = run(saved.spec, saved.checkpoint)
    for a, b in zip(whole.history, replay.history, strict=True):
        np.testing.assert_array_equal(a[checkpoint.step_index :], b)
    assert type(saved.checkpoint.state) is ReactionTransportState
    assert_reference(replay)


def test_release_freezes_transfer_but_reactions_continue(graph_data):
    spec = parse_spec(graph_data)
    whole = run(spec)
    checkpoint = whole.checkpoint_at(6)
    release = load_spec(ROOT / "configs/reaction_transport_release.json")
    released = run(release, branch_checkpoint(spec, checkpoint, release))
    np.testing.assert_array_equal(
        released.history.transferred,
        np.broadcast_to(
            np.asarray(checkpoint.state.transferred), released.history.transferred.shape
        ),
    )
    assert np.max(np.abs(released.amount[-1] - released.amount[0])) > 0.1
    assert np.max(np.abs(released.history.converted[-1] - released.history.converted[0])) > 0.1
    np.testing.assert_allclose(
        released.amount.sum(axis=1),
        np.broadcast_to(released.amount[0].sum(axis=0), (len(released.times), 3)),
        atol=2e-13,
        rtol=0,
    )
    assert_reference(released)
    for name in ("forward_rate", "volumes", "cell_ids"):
        values = getattr(spec.model, name)
        bad = replace(spec, model=replace(spec.model, **{name: tuple(reversed(values))}))
        with pytest.raises(ConfigError):
            branch_checkpoint(spec, checkpoint, bad)
    past = replace(
        release,
        experiment=replace(
            release.experiment,
            contact=(GraphContactChange(0, (0, 0)), *release.experiment.contact[1:]),
        ),
    )
    with pytest.raises(ConfigError, match="before its checkpoint"):
        branch_checkpoint(spec, checkpoint, past)
    offgrid = whole.checkpoint_at(2.03)
    missing_boundary = replace(
        spec,
        experiment=replace(
            spec.experiment, contact=(spec.experiment.contact[0], *spec.experiment.contact[2:])
        ),
    )
    with pytest.raises(ConfigError, match="integration boundary"):
        branch_checkpoint(spec, offgrid, missing_boundary)


def test_domain_combines_reaction_and_all_incident_edges(graph_data):
    spec = parse_spec(constant_control(graph_data, [1, 1], end=2))
    # Cell 101 loses A at rate .2 + .4 = .6/s; dt=1 is outside h*alpha<=.5.
    with pytest.raises(ConfigError, match="maximum exit rate"):
        timeline(replace(spec, execution=replace(spec.execution, dt=1)))
    blocked = replace(
        spec, experiment=replace(spec.experiment, contact=(GraphContactChange(0, (0, 0)),))
    )
    timeline(replace(blocked, execution=replace(blocked.execution, dt=1)))
    with pytest.raises(ConfigError, match="storage"):
        timeline(replace(spec, execution=replace(spec.execution, capacity=1000000)))
    with pytest.raises(ConfigError, match="storage"):
        timeline(replace(spec, execution=replace(spec.execution, edge_capacity=1000000)))
    for amounts, volumes in [
        (((1e308, 0, 0), (0, 0, 0)), spec.model.volumes),
        (spec.model.initial_amounts, (1e-320, 3, 2)),
    ]:
        bad = replace(spec, model=replace(spec.model, initial_amounts=amounts, volumes=volumes))
        with pytest.raises(ConfigError, match="finite float64"):
            timeline(bad)


def test_checkpoint_shapes_topology_ledgers_and_padding(graph_data):
    spec = parse_spec(graph_data)
    cp = run(spec).checkpoint_at(6)
    for state in (
        cp.state._replace(amount=cp.state.amount.T),
        cp.state._replace(converted=cp.state.converted + 1),
        cp.state._replace(transferred=cp.state.transferred + 1),
        cp.state._replace(amount=cp.state.amount.at[0, 0].set(-1)),
    ):
        with pytest.raises((ConfigError, NumericalError)):
            validate_checkpoint(spec, replace(cp, state=state))
    with pytest.raises(ConfigError, match="layout"):
        validate_checkpoint(
            spec, replace(cp, layout=cp.layout._replace(contact_ids=cp.layout.contact_ids[::-1]))
        )
    padded_spec = replace(spec, execution=replace(spec.execution, capacity=4, edge_capacity=3))
    padded = initialise(padded_spec)
    for state in (
        padded.state._replace(converted=padded.state.converted.at[-1].set(1)),
        padded.state._replace(transferred=padded.state.transferred.at[0, -1].set(1)),
    ):
        with pytest.raises(NumericalError, match="Inactive"):
            validate_checkpoint(padded_spec, replace(padded, state=state))


def test_multispecies_graph_primitive_and_batched_world_independence(graph_data):
    params = ContactParameters(
        np.array([1.0, 2, 3]),
        np.array([0, 0, 1]),
        np.array([1, 2, 2]),
        np.array([[0.4, 0.2, 0.1], [0.1, 0.3, 0.2], [0.7, 0, 0.1]]),
        np.array([True, True, False]),
    )
    amount = np.array([[8.0, 0, 1], [0, 2, 0], [1, 2, 3]])
    active = np.array([True, True, False])
    flux = edge_flux(amount, np.ones(3), params, active)
    assert np.all(np.asarray(flux)[:, 1:] == 0)
    expected = np.zeros_like(amount)
    for edge, (a, b) in enumerate(zip(params.senders, params.receivers, strict=True)):
        expected[:, a] -= flux[:, edge]
        expected[:, b] += flux[:, edge]
    np.testing.assert_allclose(
        scatter_exchange(flux, params.senders, params.receivers, amount), expected, atol=1e-15
    )
    np.testing.assert_array_equal(
        reversible_rate(
            [8, 1], [0, 5], np.array([0.2, 0.4]), np.array([0.1, 0.1]), np.array([True, False])
        ),
        [1.6, 0],
    )
    spec = parse_spec(graph_data)
    cp = initialise(spec)
    parameters = model.parameters(spec, cp.layout)
    states = jax.tree.map(lambda x: np.stack([x, x * 0.5, x * 2]), cp.state)
    openings = np.array([[1.0, 0], [0, 1], [1, 1]])
    batched = jax.jit(jax.vmap(model.rhs, in_axes=(0, 0, None, None)))(
        states, openings, parameters, cp.layout.active
    )
    for i in range(3):
        independent = model.rhs(
            jax.tree.map(lambda x, index=i: x[index], states),
            openings[i],
            parameters,
            cp.layout.active,
        )
        for a, b in zip(batched, independent, strict=True):
            np.testing.assert_allclose(a[i], b, atol=2e-15, rtol=0)


def test_artifacts_describe_axes_and_independent_controls(graph_data, tmp_path):
    result = run(parse_spec(graph_data))
    summary = write_run(tmp_path / "world", result, checkpoint_times=(6,))
    assert summary["species"] == ["A", "B"]
    assert summary["state_axes"]["amount"] == ["species", "cell_slot"]
    assert summary["physical_contacts"] == 2
    with np.load(tmp_path / "world/trajectory.npz", allow_pickle=False) as arrays:
        assert arrays["amount"].shape == (243, 2, 3)
        np.testing.assert_array_equal(
            arrays["observed_open_fraction"], control_values(result.spec, result.observations.times)
        )
        assert arrays["contact_ids"].tolist() == [7, 9]
    loaded = load_snapshot(tmp_path / "world/checkpoint_final")
    for a, b in zip(loaded.checkpoint.state, result.final.state, strict=True):
        np.testing.assert_array_equal(a, b)
