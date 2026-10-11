"""Engineering contracts for the physical pair, not assay-specific outcome rules."""

import json
from dataclasses import replace

import jax
import numpy as np
import pytest

from cells.core.errors import NumericalError
from cells.core.runner import branch_checkpoint, run, validate_checkpoint
from cells.core.schedule import PairControl, control_values
from cells.core.specs import ConfigError, ContactChange, ExperimentSpec, load_spec, parse_spec
from cells.core.state import BioelectricPairState, initialise
from cells.coupling.selective import gate_target, selective_flux
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import bioelectric_pair as model
from cells.numerics.fixed_step import rk4_checked_step
from cells.observers import hermite_bounds, sample_hermite_history, sample_history
from tests import reference_bioelectric_pair as ref
from tests.bioelectric_pair_fixtures import (
    ROOT,
    assert_targets,
    case_for,
    definition,
    physical_values,
    spec_for,
)

CASES = ref.load_panel()[1]


@pytest.fixture
def data():
    return definition(replace(CASES[0], horizon=0.02))


@pytest.mark.parametrize("name", ["baseline", "controls", "branch"])
def test_roundtrip_ids_and_complete_state(name):
    spec = load_spec(ROOT / f"configs/bioelectric_pair_{name}.json")
    assert parse_spec(spec.to_dict()) == spec
    assert case_for(spec).parameters == CASES[0].parameters
    s = initialise(spec)
    assert [v.shape for v in s.state] == [(3, 2), (3, 2), (2,), (3, 1), (1,), (3,)]
    assert all(v.dtype == np.float64 for v in s.state)
    np.testing.assert_array_equal(s.layout.ids, [101, 202])
    np.testing.assert_array_equal(s.layout.membrane_ids, [501, 502])
    np.testing.assert_array_equal(s.layout.contact_ids, [901])
    np.testing.assert_array_equal(s.layout.owners, [0, 1])
    np.testing.assert_array_equal(s.layout.cell_membranes, [0, 1])
    np.testing.assert_array_equal(s.layout.amount_reference, s.state.amount)
    assert np.all(np.asarray(s.layout.fixed_charge) < 0)
    assert float(s.state.gate[0]) == 0.25


@pytest.mark.parametrize(
    "path,value",
    [
        (("model", "species"), ["Na", "K", "Ca"]),
        (("model", "units", "time"), "bitsey_time_unit"),
        (("model", "units", "gate"), "instantaneous"),
        (("model", "population", "count"), 3),
        (("model", "population", "count"), True),
        (("model", "population", "cell_ids"), [101, 101]),
        (("model", "population", "cell_ids"), [101, True]),
        (("model", "initial_state", "amount_fmol", 0, 1), 0),
        (("model", "initial_state", "amount_fmol", 0), [12]),
        (("model", "initial_state", "volume_pL", 1), 1e-320),
        (("model", "initial_state", "voltage_V"), [0.8, -0.8]),
        (("model", "parameters", "membranes", 1, "membrane_id"), 501),
        (("model", "parameters", "membranes", 1, "owner_cell_id"), 101),
        (("model", "parameters", "membranes", 1, "bath_id"), 702),
        (("model", "parameters", "bath", "potential_V"), 0.01),
        (("model", "parameters", "bath", "kind"), "finite"),
        (("model", "parameters", "contact", "from_cell_id"), 202),
        (("model", "parameters", "contact", "to_cell_id"), 999),
        (("model", "parameters", "contact", "area_m2"), 0),
        (("model", "parameters", "contact", "area_m2"), 1e308),
        (("model", "parameters", "contact", "permeability_m_per_s"), [-1, 0, 0]),
        (("model", "parameters", "contact", "permeability_m_per_s"), [1, float("inf"), 0]),
        (("model", "parameters", "contact", "residual"), [0, 1.1, 0]),
        (("model", "parameters", "contact", "residual"), [0, -0.1, 0]),
        (("model", "parameters", "contact", "initial_gate"), -0.01),
        (("model", "parameters", "contact", "initial_gate"), 1.01),
        (("model", "parameters", "contact", "initial_gate"), True),
        (("model", "parameters", "contact", "initial_gate"), float("nan")),
        (("model", "parameters", "contact", "tau_s"), 0),
        (("model", "parameters", "contact", "tau_s"), 1e-320),
        (("model", "parameters", "contact", "sensitivity_per_V"), 0),
        (("model", "parameters", "contact", "sensitivity_per_V"), 1.7e308),
        (("model", "parameters", "contact", "half_voltage_V"), -1),
        (("experiment", "source"), {"kind": "supply"}),
        (("experiment", "membrane_controls", 1, "leak", "membrane_id"), 501),
        (("experiment", "membrane_controls", 1, "pump", "membrane_id"), 501),
        (("experiment", "membrane_controls", 0, "leak"), []),
        (("experiment", "contact", "kind"), "prescribed_open_fraction"),
        (("experiment", "contact", "contact_id"), 900),
        (("experiment", "contact", "schedule"), []),
        (("experiment", "contact", "schedule", 0, "time"), 0.001),
        (("experiment", "contact", "schedule", 0, "multiplier"), 2),
        (("execution", "capacity"), 1),
        (("execution", "membrane_capacity"), 1),
        (("execution", "edge_capacity"), 0),
        (("execution", "backend"), "gpu"),
        (("execution", "precision"), "float32"),
        (("execution", "solver"), "radau"),
    ],
)
def test_strict_physical_definitions(data, path, value):
    node = data
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(ConfigError):
        parse_spec(data)


def test_definition_domain_extremes_and_resource_refusal(data):
    for kind, value in (
        ("max_trace_bytes", 100),
        ("max_steps", 1),
        ("dt", 0.005),
        ("edge_capacity", 2**31 - 1),
    ):
        changed = json.loads(json.dumps(data))
        changed["execution"][kind] = value
        with pytest.raises(ConfigError):
            run(parse_spec(changed))
    for time in (0, 0.03):
        changed = json.loads(json.dumps(data))
        changed["experiment"]["contact"]["schedule"].append({"time": time, "multiplier": 0})
        with pytest.raises(ConfigError):
            parse_spec(changed)
    del data["execution"]["edge_capacity"]
    with pytest.raises(ConfigError):
        parse_spec(data)


def test_python_spec_never_silently_discards_a_control_family():
    spec = spec_for(replace(CASES[0], horizon=0.01))
    for experiment in (
        ExperimentSpec(0.01, (), (0, 0.01)),
        replace(spec.experiment, contact=()),
        replace(spec.experiment, membranes=()),
    ):
        with pytest.raises(ConfigError):
            run(replace(spec, experiment=experiment))
    different = replace(
        spec.model.cells[1], bath=replace(spec.model.cells[1].bath, temperature_K=300)
    )
    with pytest.raises(ConfigError, match="shared"):
        run(replace(spec, model=replace(spec.model, cells=(spec.model.cells[0], different))))


@pytest.mark.parametrize("index", range(20), ids=[c.id for c in CASES])
def test_stage_equations_and_complete_trajectories_against_independent_oracle(index):
    case = CASES[index]
    spec = spec_for(case)
    state = initialise(spec)
    ctl = control_values(spec, [0])
    rhs = model.rhs(
        state.state, PairControl(*(v[0] for v in ctl)), state.layout, state.layout.active
    )
    expected = ref.derivative(
        case.parameters, case.controls[0], ref.initial_state(case.parameters), increments=False
    )
    np.testing.assert_allclose(physical_values(rhs), expected, atol=3e-16, rtol=3e-14)
    # Ordinary tests require no generated runs, checkout, network, or acceptance artifacts.
    result = run(spec)
    reference = ref.integrate_reference(case, rtol=1e-12, atol=1e-14)
    assert_targets(case.parameters, physical_values(result.history), reference.sample(result.times))
    requested = ref.observation_grid(result.times)
    observed = model.observe_history(
        result.times, result.history, result.final.layout, requested, spec
    )
    assert_targets(case.parameters, physical_values(observed), reference.sample(requested))
    assert result.diagnostics["max_balance_error_fmol"] < 1e-8
    assert result.diagnostics["max_charge_balance_error_V"] < 1e-8
    assert result.diagnostics["max_energy_balance_error_pJ"] < 1e-6


def test_zero_voltage_gate_and_flux_gradients_are_mask_safe():
    initialise(spec_for(replace(CASES[0], horizon=0.01)))
    with jax.debug_nans(True):
        target = jax.jit(lambda v: gate_target(v, 100.0, 0.04))
        assert float(target(0.0)) == pytest.approx(1 / (1 + 2 * np.exp(-4)))
        assert float(jax.jit(jax.grad(target))(0.0)) == 0

        def flux(v):
            return selective_flux(10.0, 10.0, v, 1.0, 298.15, 1e-11, 1e-8, 0.1, 0.25, 1.0)

        assert float(jax.jit(flux)(0.0)) == 0
        assert np.isfinite(float(jax.jit(jax.grad(flux))(0.0)))
        assert float(target(1e3)) == 0
    for voltage in np.linspace(-1.2, 1.2, 51):
        np.testing.assert_allclose(target(voltage), target(-voltage), rtol=1e-14)


def test_selective_flux_limits_orientation_and_passive_sign():
    p = CASES[0].parameters
    state, layout = model.initial_values(spec_for(CASES[0]))
    control = PairControl(np.ones((4, 2)), np.ones(1))
    dv, _, rate, flux, mu = model.junction_readouts(state, control, layout, xp=np)
    np.testing.assert_allclose(
        flux[:, 0],
        [-0.0005842358395709245, -0.0015370675141613678, 0.000022402330526346456],
        rtol=3e-14,
    )
    assert np.all(flux * mu <= 0)
    assert rate[0] == pytest.approx(3.144391213660754)
    assert dv[0] == pytest.approx(-0.02)
    blocked = model.junction_readouts(state, control._replace(contact=np.zeros(1)), layout, xp=np)
    np.testing.assert_array_equal(blocked[2], rate)
    np.testing.assert_array_equal(blocked[3], 0)
    closed = model.junction_readouts(state._replace(gate=np.zeros(1)), control, layout, xp=np)[3]
    assert np.all(closed[:2] != 0) and closed[2, 0] == 0
    reverse = replace(p, junction=replace(p.junction, endpoints=(1, 0)))
    reverse_case = replace(CASES[0], parameters=reverse, horizon=0.02)
    a, b = run(spec_for(replace(CASES[0], horizon=0.02))), run(spec_for(reverse_case))
    for field in ("amount", "leak_transferred", "pump_cycles", "gate"):
        np.testing.assert_array_equal(getattr(a.history, field), getattr(b.history, field))
    # Reorientation and capacity changes can change floating reduction/fusion
    # order. Do not confuse algebraic equivalence with same-layout exact replay.
    np.testing.assert_allclose(
        a.history.transferred, -b.history.transferred, atol=1e-18, rtol=5e-15
    )
    np.testing.assert_allclose(
        a.history.dissipated_energy_pJ, b.history.dissipated_energy_pJ, atol=1e-18, rtol=5e-15
    )


def test_padding_identity_control_permutation_and_observation_independence(data):
    base = run(parse_spec(data))
    data["execution"].update(capacity=5, membrane_capacity=4, edge_capacity=3)
    data["experiment"]["observation_times"] = [0, 0.00025, 0.0005, 0.00075, 0.0102, 0.02]
    padded = run(parse_spec(data))
    np.testing.assert_array_equal(
        physical_values(base.history)[:, :18], physical_values(padded.history)[:, :18]
    )
    np.testing.assert_allclose(
        base.history.dissipated_energy_pJ,
        padded.history.dissipated_energy_pJ,
        atol=1e-18,
        rtol=5e-15,
    )
    sparse = run(
        replace(
            padded.spec, experiment=replace(padded.spec.experiment, observation_times=(0, 0.02))
        )
    )
    for a, b in zip(sparse.history, padded.history, strict=True):
        np.testing.assert_array_equal(a, b)
    for field, active_count in (
        ("amount", 2),
        ("leak_transferred", 2),
        ("pump_cycles", 2),
        ("transferred", 1),
        ("gate", 1),
    ):
        assert np.all(getattr(padded.history, field)[..., active_count:] == 0)
    ids, memids = [311, 411], [811, 911]
    data["model"]["population"]["cell_ids"] = ids
    for i, m in enumerate(data["model"]["parameters"]["membranes"]):
        m.update(membrane_id=memids[i], owner_cell_id=ids[i], bath_id=1001)
        for group in ("leak", "pump"):
            data["experiment"]["membrane_controls"][i][group]["membrane_id"] = memids[i]
    data["model"]["parameters"]["bath"]["bath_id"] = 1001
    data["model"]["parameters"]["contact"].update(contact_id=1101, from_cell_id=311, to_cell_id=411)
    data["experiment"]["contact"]["contact_id"] = 1101
    spec = parse_spec(data)
    data["model"]["parameters"]["membranes"].reverse()
    data["experiment"]["membrane_controls"].reverse()
    for group in data["experiment"]["membrane_controls"]:
        group["leak"]["species"] = ["Cl", "Na", "K"]
    assert parse_spec(data) == spec
    renamed = run(spec)
    for a, b in zip(padded.history, renamed.history, strict=True):
        np.testing.assert_array_equal(a, b)
    assert base.times.tolist() == padded.times.tolist()
    assert not base.history.gate.flags.writeable


def test_independent_events_substep_block_and_right_continuous_readouts():
    case = CASES[17]
    times = [0, 0.123, 0.1234, 0.1235, 0.124, 0.1241, 0.12425, 1]
    spec = spec_for(case, samples=times)
    result = run(spec)
    for t in (0.1234, 0.1241):
        assert t in result.times
    blocked = (result.times >= 0.1234) & (result.times <= 0.1241)
    assert np.max(np.ptp(result.history.transferred[blocked], axis=0)) == 0
    assert result.history.gate[blocked][-1, 0] != result.history.gate[blocked][0, 0]
    obs = result.observations
    assert np.all(obs.junction_flux_fmol_per_s[(obs.times >= 0.1234) & (obs.times < 0.1241)] == 0)
    assert np.any(obs.junction_flux_fmol_per_s[obs.times == 0.1241] != 0)
    controlled = spec_for(CASES[18])
    assert [p.time for p in controlled.experiment.changes] == [0, 0.117, 0.211, 0.301, 0.437]
    held = control_values(controlled, [0.117, 0.211, 0.301, 0.437])
    assert np.all(held.membrane[:, :3, 0] == 0)
    assert np.all(held.membrane[1:, 3, 1] == 0)
    np.testing.assert_array_equal(held.contact[:, 0], [1, 1, 0, 1])


def test_gate_only_analytic_identical_and_unequal_capacitance_conservation():
    case = CASES[3]
    out = run(spec_for(case, samples=np.linspace(0, 1, 101)))
    target = case.parameters.junction.target(-0.02)
    expected = target + (0.25 - target) * np.exp(-out.observations.times / 0.2)
    np.testing.assert_allclose(out.observations.gate[:, 0], expected, atol=1e-11, rtol=0)
    np.testing.assert_array_equal(
        out.history.amount, np.broadcast_to(out.history.amount[0], out.history.amount.shape)
    )
    assert np.all(out.history.dissipated_energy_pJ == 0)
    identical = run(spec_for(replace(CASES[4], horizon=0.05)))
    assert np.all(identical.history.transferred == 0)
    p = replace(
        CASES[2].parameters,
        cells=(CASES[2].parameters.cells[0], replace(CASES[2].parameters.cells[1], area_m2=1.6e-9)),
    )
    isolated = run(spec_for(replace(CASES[2], parameters=p, horizon=0.1)))
    n = isolated.history.amount
    np.testing.assert_allclose(
        n.sum(axis=-1), np.broadcast_to(n[0].sum(axis=-1), n.shape[:-1]), atol=1e-11, rtol=0
    )
    dv = p.voltage(n) - p.initial_voltage
    np.testing.assert_allclose(dv @ p.capacitance, 0, atol=1e-22, rtol=0)
    assert np.max(np.abs(dv.sum(axis=-1))) > 1e-5


def test_linear_and_postevent_slope_negative_controls():
    spec = spec_for(CASES[9])
    out = run(spec)
    times = ref.observation_grid(out.times)
    expected = ref.integrate_reference(CASES[9], rtol=1e-12, atol=1e-14).sample(times)
    linear = sample_history(out.times, out.history.gate, times)
    assert np.max(np.abs(linear[:, 0] - expected[:, 17])) > 1e-7
    event = run(spec_for(CASES[18]))
    layout = model.LAYOUT_TYPE(*(np.asarray(v) for v in event.final.layout))
    left = BioelectricPairState(*(v[:-1] for v in event.history))
    right = BioelectricPairState(*(v[1:] for v in event.history))
    a = model.rhs(left, control_values(event.spec, event.times[:-1]), layout, layout.active, xp=np)
    wrong = model.rhs(
        right, control_values(event.spec, event.times[1:]), layout, layout.active, xp=np
    )
    request = np.array([0.1165, 0.2105, 0.3005, 0.4365])
    bad = sample_hermite_history(
        event.times,
        event.history.leak_transferred,
        request,
        a.leak_transferred,
        wrong.leak_transferred,
    )
    good = model.observe_history(event.times, event.history, layout, request, event.spec)
    assert np.max(np.abs(bad - good.leak_transferred)) > 1e-7


def test_eager_jit_and_gate_refinement():
    case = replace(CASES[9], horizon=0.01)
    compiled = run(spec_for(case))
    eager = run(spec_for(case, jit=False))
    np.testing.assert_allclose(
        physical_values(compiled.history), physical_values(eager.history), rtol=0, atol=3e-13
    )
    short = replace(CASES[9], horizon=0.1)
    oracle = ref.integrate_reference(short, rtol=1e-12, atol=1e-14)
    errors = []
    for dt in (0.001, 0.0005):
        out = run(spec_for(short, dt=dt))
        errors.append(np.max(np.abs(out.history.gate[:, 0] - oracle.sample(out.times)[:, 17])))
    assert errors[0] / errors[1] > 12


@pytest.mark.parametrize("jit", [False, True])
def test_invalid_trial_refused_without_publication_or_repair(data, tmp_path, jit):
    data["model"]["parameters"]["contact"]["tau_s"] = 1e-6
    data["execution"]["jit"] = jit
    spec = parse_spec(data)
    with pytest.raises(NumericalError, match="trial/endpoint"):
        write_run(tmp_path / "invalid", run(spec))
    assert not (tmp_path / "invalid").exists()
    c = initialise(spec)
    control = PairControl(*(v[0] for v in control_values(spec, [0])))
    candidate, ok = rk4_checked_step(
        model.rhs, model.domain_valid, c.state, 0.001, control, c.layout, c.layout.active
    )
    assert not bool(ok)
    for a, b in zip(candidate, c.state, strict=True):
        np.testing.assert_array_equal(a, b)


def test_cubic_extrema_catch_hidden_overshoot_and_degenerate_limits():
    times = np.array([0.0, 1.0])
    values = np.array([[0.5], [0.5]])
    lo, hi = hermite_bounds(times, values, np.array([[4.0]]), np.array([[-4.0]]))
    assert lo[0, 0] == 0.5 and hi[0, 0] == 1.5
    for left, right in ((0.0, 0.0), (1.0, 1.0), (0.0, 2.0), (3.0, 0.0)):
        y = np.array([[0.0], [1.0]])
        a, b = np.array([[left]]), np.array([[right]])
        lower, upper = hermite_bounds(times, y, a, b)
        dense = sample_hermite_history(times, y, np.linspace(0, 1, 10001), a, b)
        assert lower[0, 0] <= dense.min() + 1e-15 and upper[0, 0] >= dense.max() - 1e-15
    s, layout = model.initial_values(spec_for(CASES[0]))
    h = BioelectricPairState(*(np.stack((v, v)) for v in s))._replace(gate=values)
    f0 = BioelectricPairState(*(np.zeros_like(v[:1]) for v in h))._replace(gate=np.array([[4.0]]))
    f1 = f0._replace(gate=-f0.gate)
    with pytest.raises(NumericalError, match="Cubic interior"):
        model.check_interpolants(times, h, f0, f1, layout)
    # Amount and affine-voltage cubic domains are checked independently as well.
    for rate in (-1000.0, 10.0):
        f0 = f0._replace(gate=np.zeros((1, 1)), amount=f0.amount.copy())
        f0.amount[0, 0, 0] = rate
        f1 = BioelectricPairState(*(-v for v in f0))
        with pytest.raises(NumericalError, match="Cubic interior"):
            model.check_interpolants(times, h, f0, f1, layout)


def test_nonfinite_cubic_slopes_and_coefficients_cannot_evade_extrema_check():
    times, values = np.array([0.0, 1.0]), np.array([[0.5], [0.5]])
    for slope in (np.inf, np.nan, 1e308):
        with pytest.raises(NumericalError, match="cubic"):
            hermite_bounds(times, values, np.array([[slope]]), np.array([[-slope]]))
    spec = spec_for(replace(CASES[0], horizon=0.001))
    state, layout = model.initial_values(spec)
    history = BioelectricPairState(*(np.stack((v, v)) for v in state))
    slope = BioelectricPairState(*(np.zeros_like(v[:1]) for v in history))
    slope.dissipated_energy_pJ[0, 0] = np.inf
    with pytest.raises(NumericalError, match="endpoint slope"):
        model.check_interpolants(times, history, slope, slope, layout)


@pytest.mark.parametrize("time", [0, 0.003, 0.0034, 0.0041, 0.01])
def test_exact_restart_gate_ledgers_anchors_and_future_branch(tmp_path, time):
    case = replace(
        CASES[0],
        horizon=0.01,
        controls=(ref.Control(), ref.Control(0.0034, contact=0), ref.Control(0.0041)),
    )
    spec = spec_for(
        case,
        samples=[0, 0.003, 0.0034, 0.0036, 0.0041, 0.0055, 0.01],
        capacity=3,
        membrane_capacity=4,
        edge_capacity=2,
    )
    out = run(spec)
    path = write_snapshot(tmp_path / "snapshot", spec, out.checkpoint_at(time))
    snapshot = load_snapshot(path)
    restored = run(snapshot.spec, snapshot.checkpoint)
    offset = snapshot.checkpoint.step_index
    for a, b in zip(out.history, restored.history, strict=True):
        np.testing.assert_array_equal(a[offset:], b)
    for name, a in vars(out.observations).items():
        np.testing.assert_array_equal(
            a[out.observations.times >= time], getattr(restored.observations, name)
        )
    # Future controls change, not current state or immutable electrical anchors.
    past = tuple(p for p in spec.experiment.contact if p.time < time)
    changed = replace(
        spec, experiment=replace(spec.experiment, contact=(*past, ContactChange(time, 0.4)))
    )
    branch = run(changed, branch_checkpoint(spec, snapshot.checkpoint, changed))
    for old, current in zip(snapshot.checkpoint.state, branch.history, strict=True):
        np.testing.assert_array_equal(old, current[0])
    for old, current in zip(snapshot.checkpoint.layout, branch.final.layout, strict=True):
        np.testing.assert_array_equal(old, current)
    oracle = ref.integrate_reference(case_for(changed), rtol=1e-12, atol=1e-14)
    assert_targets(case.parameters, physical_values(branch.history), oracle.sample(branch.times))


@pytest.mark.parametrize("field", model.LAYOUT_TYPE._fields)
def test_every_layout_anchor_and_identity_is_checked(field):
    spec = spec_for(
        replace(CASES[0], horizon=0.001), capacity=3, membrane_capacity=3, edge_capacity=2
    )
    checkpoint = initialise(spec)
    value = np.asarray(getattr(checkpoint.layout, field)).copy()
    value.flat[0] = (
        not value.flat[0]
        if value.dtype == bool
        else value.flat[0] + (1e-6 if value.dtype.kind == "f" else 1)
    )
    changed = replace(checkpoint, layout=checkpoint.layout._replace(**{field: value}))
    with pytest.raises(ConfigError, match="layout"):
        validate_checkpoint(spec, changed)


@pytest.mark.parametrize("field", BioelectricPairState._fields)
def test_every_state_field_is_required_and_checksumming_catches_corruption(tmp_path, field):
    spec = spec_for(replace(CASES[0], horizon=0.005))
    out = run(spec)
    path = write_snapshot(tmp_path / field, spec, out.final)
    with np.load(path / "state.npz") as data:
        values = {key: data[key] for key in data.files}
    values[field].flat[0] += 0.1
    np.savez(path / "state.npz", **values)
    with pytest.raises(ConfigError, match="checksum"):
        load_snapshot(path)


def test_invalid_gates_padding_ledgers_and_past_rewrite_are_rejected():
    spec = spec_for(
        replace(CASES[0], horizon=0.01), capacity=3, membrane_capacity=3, edge_capacity=2
    )
    out = run(spec)
    c = out.checkpoint_at(0.005)
    for field, index, value in (
        ("gate", (0,), -1),
        ("gate", (1,), 0.1),
        ("transferred", (0, 1), 1),
        ("amount", (0, 2), 1),
        ("leak_transferred", (0, 2), 1),
        ("pump_cycles", (2,), 1),
        ("dissipated_energy_pJ", (0,), -1),
    ):
        array = np.asarray(getattr(c.state, field)).copy()
        array[index] = value
        with pytest.raises(NumericalError):
            validate_checkpoint(spec, replace(c, state=c.state._replace(**{field: array})))
    changed = replace(spec, experiment=replace(spec.experiment, contact=(ContactChange(0, 0),)))
    with pytest.raises(ConfigError, match="before"):
        branch_checkpoint(spec, c, changed)
