import json
from dataclasses import replace

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core.errors import NumericalError
from cells.core.runner import branch_checkpoint, run, timeline, validate_checkpoint
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, InputChange, LeakChange, PumpChange, load_spec, parse_spec
from cells.core.state import BioelectricState, initialise
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import bioelectric_cell as model
from cells.numerics.fixed_step import rk4_checked_step, rk4_step
from cells.observers import sample_hermite_history, sample_history
from cells.processes.electrochemistry import (
    bernoulli,
    electrochemical_potential,
    ghk_leak,
    reversible_pump,
)
from tests.bioelectric_fixtures import (
    ROOT,
    assert_targets,
    case_for,
    definition,
    errors,
    physical_values,
    spec_for,
)
from tests.reference_bioelectric import (
    CHARGE_PER_FMOL,
    NU,
    Case,
    Control,
    F,
    Parameters,
    R,
    Z,
    derivative,
    fluxes,
    integrate_reference,
    panel,
)


@pytest.fixture
def data():
    return definition(Case("short", horizon=0.1))


@pytest.mark.parametrize("name", ["baseline", "controls", "branch"])
def test_schema_roundtrip_and_owned_layout(name):
    spec = load_spec(ROOT / f"configs/bioelectric_{name}.json")
    assert parse_spec(spec.to_dict()) == spec
    assert case_for(spec).parameters == Parameters()
    s = initialise(spec)
    assert s.state.amount.shape == (3, 1)
    assert s.state.leak_transferred.shape == (3, 1)
    assert s.state.pump_cycles.shape == (1,)
    assert all(v.dtype == np.float64 for v in s.state)
    assert s.layout.membrane_ids[0] == 501 and s.layout.bath_ids[0] == 901
    assert s.layout.owners[0] == 0 and s.layout.membrane_baths[0] == 0
    np.testing.assert_array_equal(s.layout.amount_reference, s.state.amount)
    assert float(s.layout.capacitance[0]) == Parameters().capacitance
    assert -float(s.layout.fixed_charge[0]) / CHARGE_PER_FMOL == pytest.approx(142.00673677527658)


@pytest.mark.parametrize(
    "path,value",
    [
        (("model", "species"), ["Na", "K", "Ca"]),
        (("model", "units", "voltage"), "mV"),
        (("model", "units", "time"), "bitsey_time_unit"),
        (("model", "population", "count"), 2),
        (("model", "population", "cell_id"), True),
        (("model", "initial_state", "amount_fmol"), [0, 1, 1]),
        (("model", "initial_state", "amount_fmol"), [1, 1, -1]),
        (("model", "initial_state", "amount_fmol"), [1, 1]),
        (("model", "initial_state", "amount_fmol"), [1, 1, 100]),
        (("model", "initial_state", "amount_fmol"), [1e308, 1e308, 1]),
        (("model", "initial_state", "volume_pL"), 0),
        (("model", "initial_state", "volume_pL"), 1e-320),
        (("model", "initial_state", "voltage_V"), 2),
        (("model", "initial_state", "voltage_V"), float("nan")),
        (("model", "initial_state", "voltage_V"), True),
        (("model", "parameters", "membrane", "owner_cell_id"), 999),
        (("model", "parameters", "membrane", "bath_id"), 999),
        (("model", "parameters", "membrane", "area_m2"), 0),
        (("model", "parameters", "membrane", "area_m2"), 1e-320),
        (("model", "parameters", "membrane", "specific_capacitance_F_per_m2"), -1),
        (("model", "parameters", "membrane", "permeability_m_per_s"), [-1, 0, 0]),
        (("model", "parameters", "membrane", "permeability_m_per_s"), [0, float("inf"), 0]),
        (("model", "parameters", "membrane", "pump_capacity_fmol_per_s"), 1e308),
        (("model", "parameters", "bath", "kind"), "finite"),
        (("model", "parameters", "bath", "potential_V"), 0.01),
        (("model", "parameters", "bath", "concentration_mM"), [145, 5, 149]),
        (("model", "parameters", "bath", "concentration_mM"), [0, 5, 5]),
        (("model", "parameters", "bath", "concentration_mM"), [1e308, 1e308, 1e308]),
        (("model", "parameters", "bath", "temperature_K"), 1e308),
        (("model", "parameters", "bath", "atp_free_energy_J_per_mol"), False),
        (("experiment", "source"), {"kind": "source", "schedule": []}),
        (("experiment", "membrane_controls", "leak", "kind"), "pump"),
        (("experiment", "membrane_controls", "pump", "membrane_id"), 999),
        (("experiment", "membrane_controls", "leak", "species"), ["Na", "Na", "Cl"]),
        (("experiment", "membrane_controls", "leak", "species"), [[], "K", "Cl"]),
        (("experiment", "membrane_controls", "leak", "schedule"), []),
        (("experiment", "membrane_controls", "pump", "schedule", 0, "time"), 0.01),
        (("experiment", "membrane_controls", "leak", "schedule", 0, "multipliers"), [0, 1, 2]),
        (("experiment", "membrane_controls", "pump", "schedule", 0, "multiplier"), -1),
        (("experiment", "membrane_controls", "pump", "schedule", 0, "multiplier"), True),
        (("execution", "membrane_capacity"), 0),
        (("execution", "capacity"), False),
        (("execution", "backend"), "gpu"),
        (("execution", "precision"), "float32"),
        (("execution", "solver"), "radau"),
    ],
)
def test_invalid_definitions(data, path, value):
    node = data
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(ConfigError):
        parse_spec(data)


def test_controls_resolve_ion_names_and_no_silent_family_drop(data):
    control = data["experiment"]["membrane_controls"]["leak"]
    control.update(
        species=["Cl", "Na", "K"], schedule=[{"time": 0, "multipliers": [0.3, 0.1, 0.2]}]
    )
    spec = parse_spec(data)
    assert spec.experiment.leak == (LeakChange(0, (0.1, 0.2, 0.3)),)
    for experiment in (
        replace(spec.experiment, source=(InputChange(0, 1),)),
        replace(spec.experiment, leak=()),
        replace(spec.experiment, pump=()),
        replace(spec.experiment, leak=(PumpChange(0, 1),)),
    ):
        with pytest.raises(ConfigError):
            run(replace(spec, experiment=experiment))
    old = load_spec(ROOT / "configs/single_cell_pulse.json")
    with pytest.raises(ConfigError):
        run(replace(old, experiment=replace(old.experiment, pump=(PumpChange(0, 1),))))


@pytest.mark.parametrize(
    "group,key,value", [("pump", "multiplier", 0), ("leak", "multipliers", [0, 1, 1])]
)
def test_schedule_conflicts_and_horizon(data, group, key, value):
    for time in (0, 0.2):
        changed = json.loads(json.dumps(data))
        changed["experiment"]["membrane_controls"][group]["schedule"].append(
            {"time": time, key: value}
        )
        with pytest.raises(ConfigError):
            parse_spec(changed)


def test_stage_composition_matches_independent_equations():
    case = Case("probe")
    spec = spec_for(case, capacity=4, membrane_capacity=3)
    c = initialise(spec)
    before = tuple(np.array(v) for v in c.state)
    control = control_values(spec, [0])[0]
    got = model.rhs(c.state, control, c.layout, c.layout.active)
    expected = derivative(
        case.parameters,
        case.controls[0],
        np.r_[case.parameters.initial_amount, np.zeros(5)],
        increments=False,
    )
    np.testing.assert_allclose(physical_values(got), expected[:7], atol=2e-16, rtol=2e-14)
    for old, now in zip(before, c.state, strict=True):
        np.testing.assert_array_equal(old, now)
    assert np.all(np.asarray(got.amount)[:, 1:] == 0)
    assert np.all(np.asarray(got.leak_transferred)[:, 1:] == 0)
    assert np.all(np.asarray(got.pump_cycles)[1:] == 0)


def test_bernoulli_zero_and_gradient_are_mask_safe():
    initialise(spec_for(Case("init", horizon=0.01)))
    with jax.debug_nans(True):
        assert float(jax.jit(bernoulli)(jnp.array(0.0))) == 1.0
        assert float(jax.jit(jax.grad(bernoulli))(jnp.array(0.0))) == -0.5
        xs = jnp.array([-50, -1e-4, -1e-8, 0, 1e-8, 1e-4, 50])
        np.testing.assert_allclose(
            jax.jit(bernoulli)(xs), bernoulli(np.asarray(xs), xp=np), atol=2e-15, rtol=2e-15
        )


def test_ghk_limits_orientation_area_and_passive_sign():
    p = Parameters()
    ci, co = p.initial_amount, np.array(p.bath_mM)

    def leak(voltage, inside=ci, outside=co, area=p.area_m2, multiplier=None):
        multiplier = np.ones(3) if multiplier is None else multiplier
        return ghk_leak(
            inside,
            outside,
            voltage,
            Z,
            p.temperature_K,
            area,
            np.array(p.permeability_m_per_s),
            multiplier,
            xp=np,
        )

    np.testing.assert_allclose(
        leak(0), p.area_m2 * np.array(p.permeability_m_per_s) / 1e-15 * (co - ci), rtol=2e-15
    )
    nernst = R * p.temperature_K * np.log(co / ci) / (Z * F)
    np.testing.assert_allclose(leak(nernst), 0, atol=1e-16)
    for voltage in np.linspace(-1.2, 1.2, 33):
        result = leak(voltage)
        np.testing.assert_allclose(leak(-voltage, co, ci), -result, atol=1e-16)
        np.testing.assert_array_equal(leak(voltage, area=2 * p.area_m2), 2 * result)
        np.testing.assert_array_equal(leak(voltage, multiplier=np.zeros(3)), np.zeros(3))
        mu = electrochemical_potential(ci, co, voltage, Z, p.temperature_K, xp=np)
        assert np.all(result * mu <= 1e-15)
        expected = fluxes(p, ci, voltage, Control())[0]
        np.testing.assert_allclose(result, expected, atol=2e-15, rtol=1e-12)


def test_pump_off_stall_forward_reverse_and_energy_sign():
    p = Parameters()
    mu = electrochemical_potential(
        p.initial_amount, np.array(p.bath_mM), p.initial_voltage_V, Z, p.temperature_K, xp=np
    )[:, None]
    for drive in (-50000, -float(NU @ mu[:, 0]), 0):
        for multiplier in (0, 1):
            rate, energy = reversible_pump(
                mu,
                NU[:, None],
                drive,
                p.temperature_K,
                p.pump_capacity_fmol_per_s,
                multiplier,
                xp=np,
            )
            assert rate * energy <= 0
            assert abs(rate) <= p.pump_capacity_fmol_per_s
            if multiplier == 0 or energy == 0:
                assert rate == 0
            elif drive == -50000:
                assert rate > 0 and float(Z @ (NU * rate)) < 0
            else:
                assert rate < 0


@pytest.mark.parametrize("case", panel(), ids=lambda c: c.name)
def test_full_qualified_panel_against_independent_radau(case):
    spec = spec_for(case)
    grid = timeline(spec)
    samples = np.unique(np.r_[grid, *(grid[:-1] + q * np.diff(grid) for q in (0.25, 0.5, 0.75))])
    result = run(
        replace(spec, experiment=replace(spec.experiment, observation_times=tuple(samples)))
    )
    reference = integrate_reference(case, rtol=1e-12, atol=1e-14)
    assert_targets(errors(case.parameters, physical_values(result.history), reference.sample(grid)))
    assert_targets(
        errors(case.parameters, physical_values(result.observations), reference.sample(samples))
    )
    assert result.diagnostics["max_balance_error_fmol"] <= 1e-10
    assert result.diagnostics["max_charge_balance_error_V"] <= 1e-8
    obs = result.observations
    assert np.max(obs.leak_flux_fmol_per_s * obs.delta_mu_J_per_mol, initial=0) <= 1e-14
    assert np.max(obs.pump_rate_fmol_per_s * obs.cycle_energy_J_per_mol, initial=0) <= 1e-14
    np.testing.assert_allclose(
        obs.inward_current_A,
        CHARGE_PER_FMOL
        * np.sum(Z[:, None] * (obs.leak_flux_fmol_per_s + obs.pump_flux_fmol_per_s), axis=1),
        atol=1e-25,
    )


def test_independent_controls_event_union_and_exact_off_ledgers():
    spec = load_spec(ROOT / "configs/bioelectric_controls.json")
    times = [p.time for p in spec.experiment.changes]
    assert times == [0, 2.03, 3.11, 4.13, 5.07]
    c = control_values(spec, [3.109, 3.11, 4.13, 5.07])[:, :, 0]
    np.testing.assert_array_equal(c, [[1, 1, 1, 0], [0, 1, 1, 0], [1, 1, 1, 0], [1, 1, 1, 1]])
    result = run(spec)
    pump = result.history.pump_cycles[(result.times >= 2.03) & (result.times <= 5.07), 0]
    leak = result.history.leak_transferred[(result.times >= 3.11) & (result.times <= 4.13)]
    np.testing.assert_array_equal(pump, np.full_like(pump, pump[0]))
    np.testing.assert_array_equal(leak[:, 0, 0], np.full(len(leak), leak[0, 0, 0]))
    assert np.ptp(leak[:, 1, 0]) > 1e-6


def test_exact_endpoints_constant_intervals_and_control_discontinuity_slopes():
    case = Case(
        "pulse",
        horizon=0.03,
        controls=(Control(pump=0), Control(0.013, pump=1), Control(0.017, (0, 0, 0), 0)),
    )
    spec = spec_for(case, samples=np.linspace(0, 0.03, 61))
    result = run(spec)
    assert 0.013 in result.times and 0.017 in result.times
    obs = result.observations
    np.testing.assert_array_equal(
        physical_values(obs)[-10:], np.broadcast_to(physical_values(obs)[-1], (10, 7))
    )
    state_at_times = model.observe_history(
        result.times, result.history, result.final.layout, result.times, spec
    )
    np.testing.assert_array_equal(physical_values(state_at_times), physical_values(result.history))
    ref = integrate_reference(case, rtol=1e-12, atol=1e-14)
    assert_targets(errors(case.parameters, physical_values(obs), ref.sample(obs.times)))
    # Deliberately wrong right-end controls are distinguishable from the candidate.
    layout = type(result.final.layout)(*(np.asarray(v) for v in result.final.layout))
    left = BioelectricState(*(v[:-1] for v in result.history))
    right = BioelectricState(*(v[1:] for v in result.history))
    f0 = model.rhs(left, control_values(spec, result.times[:-1]), layout, layout.active, xp=np)
    wrong = model.rhs(right, control_values(spec, result.times[1:]), layout, layout.active, xp=np)
    bad = BioelectricState(
        *(
            sample_hermite_history(result.times, v, obs.times, a, b)
            for v, a, b in zip(result.history, f0, wrong, strict=True)
        )
    )
    assert errors(case.parameters, physical_values(bad), ref.sample(obs.times))["voltage_V"] > 1e-6


def test_linear_observation_is_inadequate_and_refinement_preserves_target():
    case = Case("refinement", horizon=0.1)
    ref = integrate_reference(case, rtol=1e-12, atol=1e-14)
    errors_by_step = []
    for dt in (0.005, 0.0025, 0.00125):
        result = run(spec_for(case, dt=dt, samples=np.linspace(0, 0.1, 81)))
        err = errors(case.parameters, physical_values(result.history), ref.sample(result.times))
        errors_by_step.append(err["voltage_V"])
        assert_targets(err)
        if dt == 0.005:
            linear = BioelectricState(
                *(
                    sample_history(result.times, v, result.observations.times)
                    for v in result.history
                )
            )
            assert (
                errors(
                    case.parameters, physical_values(linear), ref.sample(result.observations.times)
                )["voltage_V"]
                > 1e-6
            )
    assert errors_by_step[0] > 10 * errors_by_step[1]
    assert errors_by_step[1] > 5 * errors_by_step[2]  # Near float64 charge cancellation floor.


def test_observation_independence_eager_jit_padding_and_renaming():
    case = Case("layout", horizon=0.05)
    original = spec_for(case)
    base = run(original)
    for spec in (
        replace(original, execution=replace(original.execution, jit=False)),
        replace(
            original,
            experiment=replace(original.experiment, observation_times=(0, 0.0025, 0.009, 0.05)),
        ),
        replace(original, execution=replace(original.execution, capacity=4, membrane_capacity=3)),
        replace(
            original,
            model=replace(
                original.model,
                cell_id=11,
                membrane=replace(
                    original.model.membrane, owner_cell_id=11, membrane_id=22, bath_id=33
                ),
                bath=replace(original.model.bath, bath_id=33),
            ),
        ),
    ):
        with jax.debug_nans(True):
            result = run(spec)
        np.testing.assert_allclose(
            physical_values(result.history), physical_values(base.history), atol=3e-13, rtol=0
        )
        if spec.execution == original.execution:
            np.testing.assert_array_equal(
                physical_values(result.history), physical_values(base.history)
            )
    assert not base.times.flags.writeable and not base.history.amount.flags.writeable


@pytest.mark.parametrize("time", [0, 0.013, 0.025, 0.037, 0.05])
def test_exact_complete_restart_at_control_and_regular_boundaries(tmp_path, time):
    case = Case(
        "replay", horizon=0.05, controls=(Control(), Control(0.013, pump=0), Control(0.037))
    )
    spec = spec_for(case, capacity=3, membrane_capacity=2, samples=[0, 0.02])
    result = run(spec)
    checkpoint = result.checkpoint_at(time)
    write_snapshot(tmp_path / "checkpoint", spec, checkpoint)
    loaded = load_snapshot(tmp_path / "checkpoint")
    resumed = run(loaded.spec, loaded.checkpoint)
    i = np.flatnonzero(result.times == time)[0]
    for a, b in zip(result.history, resumed.history, strict=True):
        np.testing.assert_array_equal(a[i:], b)
    for a, b in zip(checkpoint.layout, resumed.final.layout, strict=True):
        np.testing.assert_array_equal(a, b)
    if time > 0.02:
        assert resumed.observations.amount.shape == (0, 3, 3)


def test_independent_future_branch_preserves_anchors_and_accounting(tmp_path):
    original = spec_for(Case("branch", horizon=0.1))
    result = run(original)
    checkpoint = result.checkpoint_at(0.05)
    changed = replace(
        original,
        experiment=replace(
            original.experiment,
            leak=(LeakChange(0, (1, 1, 1)), LeakChange(0.05, (0, 1, 1))),
            pump=(PumpChange(0, 1), PumpChange(0.05, 0), PumpChange(0.07, 1)),
        ),
    )
    branch = run(changed, branch_checkpoint(original, checkpoint, changed))
    fresh = run(changed)
    for a, b in zip(branch.history, fresh.history, strict=True):
        np.testing.assert_array_equal(a, b[10:])
    for a, b in zip(checkpoint.layout, branch.final.layout, strict=True):
        np.testing.assert_array_equal(a, b)
    assert branch.history.pump_cycles[0, 0] > 0
    assert_targets(
        errors(
            case_for(changed).parameters,
            physical_values(branch.history),
            integrate_reference(case_for(changed)).sample(branch.times),
        )
    )
    for invalid in (
        replace(changed, model=replace(changed.model, initial_voltage_V=-0.06)),
        replace(changed, execution=replace(changed.execution, dt=0.0025)),
        replace(changed, experiment=replace(changed.experiment, pump=(PumpChange(0, 0),))),
    ):
        with pytest.raises(ConfigError):
            branch_checkpoint(original, checkpoint, invalid)
    write_run(tmp_path / "branch", branch)
    manifest = json.loads((tmp_path / "branch/manifest.json").read_text())
    assert manifest["observer"]["sampling"] == model.OBSERVATION_SAMPLING
    assert manifest["numerics"]["stage_domain"] == model.STAGE_DOMAIN_ID
    archive = np.load(tmp_path / "branch/trajectory.npz")
    assert "fixed_charge" in archive and "bath_concentration" in archive
    assert "observed_chemical_work_J" in archive and "observed_inward_current_A" in archive


def test_final_time_events_change_readouts_but_not_evolution():
    spec = spec_for(Case("end", horizon=0.05))
    base = run(spec)
    changed = replace(
        spec,
        experiment=replace(
            spec.experiment,
            leak=(*spec.experiment.leak, LeakChange(0.05, (0, 0, 0))),
            pump=(*spec.experiment.pump, PumpChange(0.05, 0)),
        ),
    )
    result = run(changed)
    np.testing.assert_array_equal(physical_values(base.history), physical_values(result.history))
    assert result.final.event_index == 1
    assert np.all(result.observations.inward_current_A[-1] == 0)


@pytest.mark.parametrize("jit", [False, True])
def test_runtime_refuses_invalid_physical_trial_without_clipping(jit):
    spec = spec_for(
        Case(
            "too_fast",
            parameters=replace(Parameters(), pump_capacity_fmol_per_s=1000),
            horizon=0.005,
        ),
        jit=jit,
    )
    with pytest.raises(NumericalError, match="trial/endpoint"):
        run(spec)


def test_stage_guard_rejects_negative_trial_even_with_positive_endpoint():
    # Endpoint-only checks would miss this explicit RK4 counterexample.
    initial = (jnp.array([1.0], dtype=jnp.float64),)

    def rhs(state, control, params, active):
        return (-1000 * state[0],)

    def valid(state, params, active):
        return jnp.all(jnp.isfinite(state[0]) & (state[0] > 0))

    assert bool(valid(rk4_step(rhs, initial, 0.005, 0, 0, 0), 0, 0))
    checked, status = jax.jit(lambda y: rk4_checked_step(rhs, valid, y, 0.005, 0, 0, 0))(initial)
    assert not bool(status)
    np.testing.assert_array_equal(checked[0], initial[0])


@pytest.mark.parametrize("disabled", ["controls", "capacities"])
def test_exact_all_off_state_and_ledgers(disabled):
    p = Parameters()
    control = Control()
    if disabled == "controls":
        control = Control(leak=(0, 0, 0), pump=0)
    else:
        p = replace(p, permeability_m_per_s=(0, 0, 0), pump_capacity_fmol_per_s=0)
    result = run(spec_for(Case("off", p, 0.05, (control,)), samples=[0, 0.001, 0.049, 0.05]))
    for field in result.history:
        np.testing.assert_array_equal(field, np.broadcast_to(field[0], field.shape))
    obs = result.observations
    np.testing.assert_array_equal(obs.amount, np.broadcast_to(obs.amount[0], obs.amount.shape))
    assert np.all(obs.inward_current_A == 0) and np.all(obs.chemical_work_J == 0)


def test_observer_refuses_invalid_sampled_physical_state(monkeypatch):
    spec = spec_for(Case("observer", horizon=0.01))
    result = run(spec)

    def invalid_sample(times, values, requested, left, right):
        samples = sample_hermite_history(times, values, requested, left, right)
        samples[...] = -1
        return samples

    monkeypatch.setattr(model, "sample_hermite_history", invalid_sample)
    with pytest.raises(NumericalError, match="Invalid bioelectric state"):
        model.observe_history(result.times, result.history, result.final.layout, [0.0025], spec)


@pytest.mark.parametrize(
    "mutation",
    ["negative", "zero", "nonfinite", "padding", "ledger", "anchor", "owner", "bath", "clock"],
)
def test_corrupt_checkpoint_refused(mutation):
    spec = spec_for(Case("corrupt", horizon=0.01), capacity=3, membrane_capacity=2)
    checkpoint = run(spec).final
    s = BioelectricState(*(np.array(v) for v in checkpoint.state))
    layout = type(checkpoint.layout)(*(np.array(v) for v in checkpoint.layout))
    if mutation in ("negative", "zero", "nonfinite"):
        s.amount[0, 0] = {"negative": -1, "zero": 0, "nonfinite": np.inf}[mutation]
    elif mutation == "padding":
        s.leak_transferred[1, 1] = 1
    elif mutation == "ledger":
        s.pump_cycles[0] += 0.1
    elif mutation == "anchor":
        layout.voltage_reference[0] += 0.01
    elif mutation == "owner":
        layout.owners[0] = 1
    elif mutation == "bath":
        layout.bath_concentration[0, 0] += 1
    else:
        checkpoint = replace(checkpoint, event_index=999)
    with pytest.raises((ConfigError, NumericalError)):
        validate_checkpoint(spec, replace(checkpoint, state=s, layout=layout))


def test_steps_resource_budget_and_bad_interpolated_state_are_refused():
    spec = spec_for(Case("limits", horizon=0.01))
    for execution in (
        replace(spec.execution, dt=0.006),
        replace(spec.execution, max_steps=1),
        replace(spec.execution, membrane_capacity=100000, max_trace_bytes=100),
        replace(spec.execution, capacity=100000, max_trace_bytes=100),
    ):
        with pytest.raises(ConfigError):
            timeline(replace(spec, execution=execution))
    checkpoint = initialise(spec)
    # Cubic is not positivity preserving: a caller cannot bypass physical checks.
    invalid = BioelectricState(
        np.asarray(checkpoint.state.amount)[None].copy(),
        np.asarray(checkpoint.state.leak_transferred)[None].copy(),
        np.asarray(checkpoint.state.pump_cycles)[None].copy(),
    )
    invalid.amount[0, 0, 0] = -1
    with pytest.raises(NumericalError):
        model.check_values(invalid, spec)
