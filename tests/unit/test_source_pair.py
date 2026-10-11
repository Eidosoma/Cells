"""Source-compatible production engineering, independent of generated run artifacts."""

import copy
from dataclasses import replace

import jax
import numpy as np
import pytest

from cells.core.errors import NumericalError
from cells.core.runner import branch_checkpoint, run, validate_checkpoint
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, ContactChange, ExperimentSpec, load_spec, parse_spec
from cells.core.state import initialise
from cells.io import load_snapshot, write_snapshot
from cells.models import source_pair as model
from cells.numerics.fixed_step import rk4_checked_step
from tests import reference_source_pair_numerics as ref
from tests.source_pair_fixtures import definition, reference_model, spec_for, values

PANEL = ref.eq.load_panel()
CASES = PANEL["cases"]


@pytest.mark.parametrize("name", ["baseline", "controls", "branch"])
def test_roundtrip_complete_typed_state(name):
    spec = load_spec(ref.eq.ROOT / f"configs/source_pair_{name}.json")
    assert parse_spec(spec.to_dict()) == spec
    state = initialise(spec)
    assert [v.shape for v in state.state] == [(3, 2), (3, 2), (3, 2), (2,), (3, 1), (3, 2), (1,)]
    assert all(v.dtype == np.float64 for v in state.state)
    np.testing.assert_array_equal(state.layout.ion_reference, state.state.ions)
    np.testing.assert_array_equal(state.layout.regulatory_reference, state.state.regulation)
    np.testing.assert_array_equal(state.layout.ids, [101, 102])
    assert set(model.STATE_TYPE._fields).isdisjoint(model.LAYOUT_TYPE._fields)
    assert "gate" not in model.STATE_TYPE._fields and "free_mirna" not in model.STATE_TYPE._fields


@pytest.mark.parametrize(
    "path,value",
    [
        (("model", "units", "time"), "s"),
        (("model", "ionic_species"), ["K", "Na", "Cl"]),
        (("model", "regulatory_coordinates"), ["u", "m", "z"]),
        (("model", "population", "count"), 1),
        (("model", "population", "count"), True),
        (("model", "population", "cell_ids"), [101, 101]),
        (("model", "initial_state", "ions", 0, 0), 0),
        (("model", "initial_state", "regulation", 0, 0), -1),
        (("model", "initial_state", "regulation", 0, 0), 1001),
        (("model", "parameters", "parameter_set"), "physical"),
        (("model", "parameters", "context", "P", 0), 79),
        (("model", "parameters", "context", "ST", 0), -1),
        (("model", "parameters", "context", "snail", 0), float("nan")),
        (("model", "parameters", "membranes", 1, "owner_cell_id"), 101),
        (("model", "parameters", "membranes", 1, "membrane_id"), 201),
        (("model", "parameters", "membranes", 1, "bath_id"), 999),
        (("model", "parameters", "membranes", 0, "diffusion", 0), 1e308),
        (("model", "parameters", "bath", "kind"), "finite"),
        (("model", "parameters", "bath", "ions", 0), 0),
        (("model", "parameters", "contact", "to_cell_id"), 101),
        (("model", "parameters", "contact", "ion_diffusion"), [0, -1, 0]),
        (("model", "parameters", "contact", "mirna_diffusion"), float("inf")),
        (("model", "parameters", "contact", "gate_profile"), "dynamic"),
        (("model", "parameters", "contact", "swap_hemichannels"), 1),
        (("experiment", "source", "kind"), "supply"),
        (("experiment", "membrane_controls", 0, "leak"), []),
        (("experiment", "membrane_controls", 1, "membrane_id"), 201),
        (("experiment", "membrane_controls", 0, "pump", 0, "multiplier"), 2),
        (("experiment", "contact_controls", 0, "route"), "all"),
        (("experiment", "contact_controls", 1, "route"), "ions"),
        (("experiment", "contact_controls", 0, "contact_id"), 999),
        (("experiment", "contact_controls", 0, "schedule", 0, "time"), 0.001),
        (("experiment", "observation_times"), [0.02, 0.01]),
        (("execution", "capacity"), 1),
        (("execution", "edge_capacity"), 0),
        (("execution", "membrane_capacity"), 1),
        (("execution", "jit"), 1),
        (("execution", "precision"), "float32"),
        (("execution", "backend"), "gpu"),
        (("execution", "solver"), "euler"),
    ],
)
def test_strict_source_definition(path, value):
    data = definition(dict(CASES[5], end_time=0.03))
    node = data
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(ConfigError):
        parse_spec(data)


@pytest.mark.parametrize(
    "key,value",
    [
        ("max_trace_bytes", 100),
        ("max_steps", 1),
        ("dt", 0.02),
        ("dt", 1e-300),
        ("edge_capacity", 2**31 - 1),
    ],
)
def test_resource_guards_precede_capacity_allocation(key, value):
    data = definition(dict(CASES[5], end_time=0.03))
    data["execution"][key] = value
    with pytest.raises(ConfigError):
        run(parse_spec(data))


@pytest.mark.parametrize("index", range(14))
def test_complete_coupled_paths_and_readouts_against_independent_reference(index):
    case = CASES[index]
    reference = ref.Model(PANEL, case)
    expected = ref.integrate_reference(reference, refinement=0.1)
    spec = spec_for(case)
    initial = initialise(spec)
    held = control_values(spec, [0])
    control = type(held)(*(v[0] for v in held))
    slope = model.rhs(initial.state, control, initial.layout, initial.layout.active)
    np.testing.assert_allclose(
        values(slope), reference.derivative(reference.initial(), 0), atol=2e-12, rtol=2e-12
    )
    result = run(spec)
    times = ref.comparison_grid(reference, result.times)
    obs = model.observe_history(result.times, result.history, result.final.layout, times, spec)
    scores = ref.scores(reference, times, values(obs), expected.sample(times))
    assert max(scores.values()) <= 1, scores
    independently_reconstructed = ref.observations(reference, times, values(obs))
    np.testing.assert_allclose(
        obs.voltage_V, independently_reconstructed["voltage"], atol=1e-13, rtol=1e-12
    )
    np.testing.assert_allclose(
        obs.gate_scales[..., 0], independently_reconstructed["gate_scale"], atol=2e-12, rtol=2e-12
    )
    flux = np.c_[
        obs.leak_flux.reshape(len(times), 6),
        (model.NU * obs.pump_cycle_flux[:, None, :]).reshape(len(times), 6),
        obs.ionic_junction_flux[..., 0],
        obs.mirna_junction_flux,
    ]
    np.testing.assert_allclose(
        flux, independently_reconstructed["membrane_and_junction_flux"], atol=1e-18, rtol=2e-11
    )
    np.testing.assert_allclose(
        obs.bound_complexes, independently_reconstructed["packet"][:, 9:16], atol=2e-12, rtol=2e-12
    )
    np.testing.assert_array_equal(obs.free_mirna_proxy, obs.regulation[:, 0])
    assert max(result.diagnostics.values()) < 2e-9


def test_state_roles_and_independent_routes():
    spec = spec_for(CASES[5])
    s, layout = model.initial_values(spec)
    held = control_values(spec, [0])
    control = type(held)(*(v[0] for v in held))
    original = model.rhs(s, control, layout, layout.active, xp=np)
    changed_history = s._replace(**{name: getattr(s, name) + 1 for name in s._fields[2:]})
    for a, b in zip(
        original, model.rhs(changed_history, control, layout, layout.active, xp=np), strict=True
    ):
        np.testing.assert_array_equal(a, b)
    different_regulation = s._replace(regulation=s.regulation + 1)
    np.testing.assert_array_equal(
        model.rhs(different_regulation, control, layout, layout.active, xp=np).ions, original.ions
    )
    for route in (0, 1):
        reduced = control.contact.copy()
        reduced[route] = 0
        slope = model.rhs(s, control._replace(contact=reduced), layout, layout.active, xp=np)
        field = "ion_transferred" if route == 0 else "mirna_transferred"
        other = "mirna_transferred" if route == 0 else "ion_transferred"
        np.testing.assert_array_equal(getattr(slope, field), 0)
        np.testing.assert_array_equal(getattr(slope, other), getattr(original, other))
    for index, pumping in ((8, False), (9, True)):
        spec = spec_for(CASES[index])
        s, layout = model.initial_values(spec)
        h = control_values(spec, [0])
        c = type(h)(*(v[0] for v in h))
        r = model.rhs(s, c, layout, layout.active, xp=np)
        np.testing.assert_array_equal(r.leak_history, 0)
        assert bool(np.any(r.pump_history != 0)) == pumping


def test_padding_id_order_and_sampling_independence():
    case = dict(CASES[5], end_time=0.03)
    a = run(spec_for(case))
    data = definition(
        case, capacity=5, membrane_capacity=4, edge_capacity=3, samples=[0, 0.001, 0.013, 0.03]
    )
    b = run(parse_spec(data))
    np.testing.assert_allclose(values(a.history), values(b.history), atol=2e-12, rtol=2e-13)
    sparse = run(
        replace(b.spec, experiment=replace(b.spec.experiment, observation_times=(0, 0.03)))
    )
    for x, y, n in zip(b.history, sparse.history, (2, 2, 2, 2, 1, 2, 1), strict=True):
        np.testing.assert_array_equal(x, y)
        np.testing.assert_array_equal(x[..., n:], 0)
    data["model"]["parameters"]["membranes"].reverse()
    data["experiment"]["membrane_controls"].reverse()
    data["experiment"]["contact_controls"].reverse()
    assert parse_spec(data) == b.spec
    data["model"]["population"]["cell_ids"] = [711, 911]
    for membrane in data["model"]["parameters"]["membranes"]:
        membrane["owner_cell_id"] = {101: 711, 102: 911}[membrane["owner_cell_id"]]
    data["model"]["parameters"]["contact"].update(from_cell_id=711, to_cell_id=911)
    renamed = run(parse_spec(data))
    for x, y in zip(b.history, renamed.history, strict=True):
        np.testing.assert_array_equal(x, y)


def test_asymmetric_orientation_and_zero_voltage_boundary():
    base, reversed_only, swapped = [run(spec_for(CASES[i])) for i in (5, 6, 7)]
    mapped = values(swapped.history)
    mapped[:, 20:23] *= -1
    mapped[:, 29] *= -1
    np.testing.assert_allclose(mapped, values(base.history), atol=2e-12, rtol=2e-13)
    assert np.max(abs(values(reversed_only.history)[:, :12] - values(base.history)[:, :12])) > 0.1
    with jax.debug_nans(True):
        result = run(
            spec_for(
                dict(CASES[10], end_time=0.02), capacity=4, membrane_capacity=4, edge_capacity=3
            )
        )
    np.testing.assert_array_equal(result.observations.voltage_V[0], 0)


def test_replay_branches_and_immutable_context(tmp_path):
    spec = spec_for(CASES[13], samples=[0, 0.1, 0.137, 0.2, 0.274, 0.5, 1])
    result = run(spec)
    for time in (0, 0.13, 0.137, 0.274, 1):
        checkpoint = result.checkpoint_at(time)
        path = tmp_path / str(time)
        write_snapshot(path, spec, checkpoint)
        restored = load_snapshot(path)
        resumed = run(restored.spec, restored.checkpoint)
        start = np.flatnonzero(result.times == time)[0]
        for a, b in zip(result.history, resumed.history, strict=True):
            np.testing.assert_array_equal(a[start:], b)
        for name, value in vars(result.observations).items():
            np.testing.assert_array_equal(
                value[result.observations.times >= time], getattr(resumed.observations, name)
            )
    checkpoint = result.checkpoint_at(0.137)
    contacts = (spec.experiment.contacts[0], (ContactChange(0, 1), ContactChange(0.137, 0)))
    changed = replace(spec, experiment=replace(spec.experiment, contacts=contacts))
    branch = run(changed, branch_checkpoint(spec, checkpoint, changed))
    oracle_model = reference_model(changed)
    oracle = ref.integrate_reference(oracle_model, refinement=0.1)
    assert (
        max(
            ref.scores(
                oracle_model, branch.times, values(branch.history), oracle.sample(branch.times)
            ).values()
        )
        <= 1
    )
    for a, b in zip(checkpoint.state, branch.history, strict=True):
        np.testing.assert_array_equal(a, b[0])
    bad = checkpoint.layout._replace(context=np.asarray(checkpoint.layout.context) + 0.01)
    with pytest.raises(ConfigError):
        validate_checkpoint(spec, replace(checkpoint, layout=bad))
    with pytest.raises(NumericalError):
        validate_checkpoint(
            spec,
            replace(
                checkpoint,
                state=checkpoint.state._replace(pump_history=checkpoint.state.pump_history + 1),
            ),
        )
    with pytest.raises(ConfigError):
        branch_checkpoint(
            spec, checkpoint, replace(changed, execution=replace(spec.execution, dt=0.005))
        )
    with pytest.raises(ConfigError):
        run(replace(spec, experiment=ExperimentSpec(1, (), (0, 1))))


def test_invalid_stages_and_cubic_interiors_are_refused():
    spec = spec_for(dict(CASES[5], end_time=0.02))
    checkpoint = initialise(spec)
    h = control_values(spec, [0])
    control = type(h)(*(v[0] for v in h))
    unchanged, valid = rk4_checked_step(
        model.rhs,
        model.domain_valid,
        checkpoint.state,
        1e4,
        control,
        checkpoint.layout,
        checkpoint.layout.active,
    )
    assert not bool(valid)
    for a, b in zip(checkpoint.state, unchanged, strict=True):
        np.testing.assert_array_equal(a, b)
    state, layout = model.initial_values(spec)
    history = model.STATE_TYPE(*(np.stack((v, v)) for v in state))
    history.regulation[:, 0, 0] = 0.01
    left = model.STATE_TYPE(*(np.zeros_like(v[:1]) for v in history))
    right = copy.deepcopy(left)
    left.regulation[0, 0, 0], right.regulation[0, 0, 0] = -0.1, 0.1
    with pytest.raises(NumericalError, match="cubic interior"):
        model.check_interpolants(np.array([0.0, 1.0]), history, left, right, layout)
    left.local_regulation[0, 0, 0] = np.inf
    with pytest.raises(NumericalError):
        model.check_interpolants(np.array([0.0, 1.0]), history, left, right, layout)


def test_eager_and_compiled_paths():
    case = dict(CASES[5], end_time=0.02)
    a, b = run(spec_for(case)), run(spec_for(case, jit=False))
    np.testing.assert_allclose(values(a.history), values(b.history), atol=2e-12, rtol=2e-13)
