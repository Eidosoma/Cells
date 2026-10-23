"""Mechanistic injury controls and numerical checks, not biological repair cases."""

from copy import deepcopy

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core.batch import BatchSpec, WorldSpec, plan_batch, run_batch
from cells.core.errors import NumericalError
from cells.core.runner import branch_checkpoint, event_index, run, timeline, validate_checkpoint
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import Checkpoint
from cells.core.surface_repair_spec import base_spec
from cells.ensemble import ionic
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import surface_calcium_cav as prior
from cells.models import surface_repair as model
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_checked_step, rk4_step
from cells.processes import membrane_injury
from tests.unit.test_surface_calcium import BACKEND, evidence
from tests.unit.test_surface_kinetic import assert_states, exact
from validation.tissue import surface_repair_fixtures as fixtures
from validation.tissue import surface_repair_reference as reference


def initial(raw=None):
    spec = parse_spec(fixtures.definition() if raw is None else raw)
    state, p = model.initial_values(spec)
    return spec, state, p


def held(spec, time):
    controls = control_values(spec, [time])
    return type(controls)(*(v[0] for v in controls))


def test_identity_schedules_padding_and_resource_guards():
    spec, state, p = initial()
    assert parse_spec(spec.to_dict()) == spec
    assert get_model(spec.model) is model
    assert type(p) is model.LAYOUT_TYPE
    assert 5.3e-6 in timeline(spec) and 15.3e-6 in timeline(spec)
    assert held(spec, 5.3e-6).injury[0] == 1
    assert held(spec, 15.3e-6).injury[0] == 0
    assert np.count_nonzero(held(spec, 5.3e-6).injury) == 1
    assert all(not np.any(getattr(state, k)[..., -1]) for k in model.EXTRA_AXES)
    raw = spec.to_dict()
    for row in raw["model"]["injury_patches"]:
        row.update(injury_rate_per_s=1e5, resealing_rate_per_s=1e5)
        row["permeability_m_per_s"]["Na"] = 1e-5
    with pytest.raises(ConfigError, match="combined transport loss"):
        timeline(parse_spec(raw))


@pytest.mark.parametrize(
    "kind",
    [
        "negative_damage",
        "over_damage",
        "nan_rate",
        "boolean_rate",
        "negative_permeability",
        "calcium_route",
        "missing_patch",
        "duplicate_patch",
        "missing_control",
        "duplicate_time",
        "nonzero_start",
        "unknown_law",
    ],
)
def test_bad_definitions_reject(kind):
    raw = fixtures.definition()
    p, c = raw["model"]["injury_patches"][0], raw["experiment"]["injury_controls"][0]
    if kind in ("negative_damage", "over_damage"):
        p["initial_damage"] = -0.1 if kind == "negative_damage" else 1.1
    elif kind in ("nan_rate", "boolean_rate"):
        p["injury_rate_per_s"] = float("nan") if kind == "nan_rate" else True
    elif kind == "negative_permeability":
        p["permeability_m_per_s"]["Na"] = -1e-9
    elif kind == "calcium_route":
        p["permeability_m_per_s"]["Ca"] = 1e-9
    elif kind == "missing_patch":
        raw["model"]["injury_patches"].pop()
    elif kind == "duplicate_patch":
        raw["model"]["injury_patches"][1] = deepcopy(p)
    elif kind == "missing_control":
        raw["experiment"]["injury_controls"].pop()
    elif kind == "duplicate_time":
        c["schedule"][1]["time"] = 0.0
    elif kind == "nonzero_start":
        c["schedule"][0]["time"] = 1e-6
    else:
        p["law"] = "biological_regeneration@1"
    with pytest.raises(ConfigError):
        parse_spec(raw)


def test_jitted_damage_law_vmap_and_analytic_refinement():
    # Independent analytic solution: injury pulse followed by prescribed closure.
    damage, hazard, closure = np.array([0.0, 0.25, 1.0]), 20000.0, 4000.0
    kernel = jax.jit(jax.vmap(lambda d: membrane_injury.rates(d, hazard, closure, 1.0, 1.0)))
    actual = kernel(jnp.asarray(damage))
    exact(
        actual, (hazard * (1 - damage) - closure * damage, hazard * (1 - damage), closure * damage)
    )
    target = reference.analytic_damage(0.0, hazard, closure, 10e-6)
    errors = []
    for step in (1.25e-6, 0.625e-6, 0.3125e-6):
        d = np.asarray(0.0)
        for _ in range(round(10e-6 / step)):
            d = rk4_step(
                lambda z: membrane_injury.rates(z, hazard, closure, 1, 1, xp=np)[0], d, step
            )
        errors.append(abs(float(d) - target))
    assert errors[0] < 2e-9 and errors[1] < errors[0] / 10 and errors[2] < errors[1] / 10
    assert reference.analytic_damage(0.5, 0, 0, 1) == 0.5
    assert reference.analytic_damage(0.5, 0, closure, 1e-4) < 0.5
    evidence(
        "resolved-repair-damage-law",
        dict(
            status="passed",
            errors=errors,
            expected=target,
            scope="Synthetic law control, not fitted physiology",
        ),
    )


def test_sham_reduces_to_prior_without_state_resets():
    spec, state, p = initial(fixtures.definition("sham"))
    original = base_spec(spec)
    old, q = prior.initial_values(original)
    control = held(spec, 5.3e-6)
    before = prior.readouts(old, model.base_control(control), q, xp=np)
    after = model.readouts(state, control, p, xp=np)
    exact(model.base_state(state), old)
    exact(model.base_state(after.derivative), before.derivative)
    exact(jax.tree.leaves(after.field), jax.tree.leaves(before.field))
    assert after.valid
    assert all(not np.any(getattr(after.derivative, k)) for k in model.EXTRA_AXES)
    # Injury input changes the derivative of damage only at onset.
    triggered = model.readouts(
        state, control._replace(injury=np.array([1, 0, 0, 0, 0.0])), p, xp=np
    )
    exact(model.base_state(triggered.derivative), model.base_state(after.derivative))
    assert triggered.derivative.damage[0] > 0 and not np.any(state.damage)
    evidence(
        "resolved-repair-sham",
        dict(status="passed", state_rates_field="bitwise prior", concentration_or_gate_reset=False),
    )


def test_local_transport_ownership_independent_rates_and_controls():
    raw = fixtures.definition()
    raw["model"]["injury_patches"][0]["initial_damage"] = 0.3
    spec, state, p = initial(raw)
    control = held(spec, 5.3e-6)
    actual = model.readouts(state, control, p, xp=np)
    c = reference.bind(spec.to_dict())
    target, _, proof = reference.evaluate(c, reference.initial(c), 5.3e-6)
    ratio = assert_states(
        c,
        reference.flatten(c, actual.derivative._asdict()),
        target,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    assert actual.valid and abs(actual.field.energy_balance_pJ_s) < 1e-9
    assert abs(proof["physical_energy_balance_pJ_s"]) < 1e-9
    d = actual.derivative
    assert np.count_nonzero(d.injury_transferred) == 2
    assert np.all(d.injury_dissipated_energy_pJ >= 0)
    original = prior.readouts(
        model.base_state(state), model.base_control(control), model.base_layout(p), xp=np
    )
    delta = d.chemical_amount_increment - original.derivative.chemical_amount_increment
    np.testing.assert_allclose(
        np.sum(delta, axis=(0, 2))[p.ionic_species],
        -np.sum(d.injury_transferred, axis=1),
        atol=1e-12,
    )
    assert not np.any(delta[1])
    exact(d.channel_gate, original.derivative.channel_gate)
    exact(d.calcium_gate, original.derivative.calcium_gate)
    # Blocking ordinary membrane availability must not erase an already open lesion.
    blocked = model.readouts(
        state, control._replace(membrane=np.zeros_like(control.membrane)), p, xp=np
    )
    np.testing.assert_allclose(
        blocked.derivative.injury_transferred, d.injury_transferred, atol=1e-12, rtol=1e-12
    )
    evidence(
        "resolved-repair-owned-rates",
        dict(
            status="passed",
            inputs=spec.to_dict(),
            max_error_over_budget=ratio,
            independent_proof=proof,
        ),
    )


def test_invalid_damage_control_and_ledger_refused():
    spec, state, p = initial()
    for field, index, value in (
        ("damage", 0, -0.1),
        ("damage", -1, 0.2),
        ("damage_opened", 0, 1.0),
        ("injury_transferred", (2, 0), 0.1),
    ):
        invalid = model.STATE_TYPE(*(np.array(v) for v in state))
        getattr(invalid, field)[index] = value
        assert not model.domain_valid(invalid, p, p.active, xp=np)
        with pytest.raises(NumericalError):
            model.check_values(invalid, spec)
    invalid_control = held(spec, 0)._replace(injury=np.full_like(state.damage, np.nan))
    assert not model.control_domain_valid(state, invalid_control, p, p.active, xp=np)


def test_independent_worlds_and_gpu_definition_planning():
    for backend in ("cpu", "gpu"):
        first = parse_spec(fixtures.definition("resealing", backend=backend))
        second = parse_spec(fixtures.definition("held", backend=backend))
        plan = plan_batch(BatchSpec((WorldSpec(7, first), WorldSpec(29, second)), 2, 256, 2**30))
        assert plan.spec.worlds[0].world_id == 7 and plan.spec.worlds[1].world_id == 29
        cohort = ionic.parse_spec(
            dict(model="ionic_worlds@1", simulation=first.to_dict(), worlds=2, window_steps=16)
        )
        assert cohort.simulation.model == first.model
        assert model.STATE_AXES["damage"] == ["membrane_slot"]
        assert model.STATE_AXES["injury_transferred"] == ["species", "membrane_slot"]
    evidence(
        "resolved-repair-world-planning",
        dict(
            status="passed",
            backends=["cpu", "gpu"],
            scope="Host planning only; no GPU or multi-GPU execution",
        ),
    )


@pytest.mark.parametrize("arm", fixtures.ARMS)
def test_short_numpy_trajectory_reference_and_damage_controls(arm):
    raw = fixtures.definition(arm)
    raw["experiment"].update(end_time=20e-6, observation_times=[0.0, 5.3e-6, 15.3e-6, 20e-6])
    spec, state, p = initial(raw)
    times = timeline(spec)
    history = [state]
    for t, h in zip(times[:-1], np.diff(times), strict=True):
        control = held(spec, t)
        state = rk4_step(
            lambda y, control=control: model.rhs(y, control, p, p.active, xp=np), state, h
        )
        model.check_values(state, spec)
        history.append(state)
    history = model.STATE_TYPE(*(np.stack(v) for v in zip(*history, strict=True)))
    observations = model.observe_history(times, history, p, spec.experiment.observation_times, spec)
    expected = reference.integrate(spec.to_dict())
    c = reference.bind(spec.to_dict())
    actual = reference.flatten(c, vars(observations))
    evidence(
        "resolved-repair-" + arm + "-trajectory",
        dict(status="checking", inputs=spec.to_dict()),
        dict(observed=actual, reference=expected["state"]),
    )
    ratio = assert_states(c, actual, expected["state"])
    hazard = 20000.0 if arm in ("held", "resealing") else 0.0
    closure = 0.0 if arm == "held" else 4000.0
    opened = reference.analytic_damage(0.0, hazard, closure, 10e-6)
    target = reference.analytic_damage(opened, 0.0, closure, 4.7e-6)
    np.testing.assert_allclose(state.damage[0], target, rtol=0, atol=2e-9)
    assert not np.any(state.damage[1:])
    if arm == "resealing":
        assert state.damage_closed[0] > 0 and state.damage_opened[0] > 0
    elif arm == "held":
        assert state.damage_closed[0] == 0 and state.damage_opened[0] > 0
    else:
        assert state.damage_closed[0] == state.damage_opened[0] == 0
        assert not np.any(state.injury_transferred)
    empty = model.observe_history(times, history, p, [], spec)
    assert empty.damage.shape == (0, len(state.damage))
    evidence(
        "resolved-repair-" + arm + "-trajectory",
        dict(
            status="passed",
            inputs=spec.to_dict(),
            diagnostics=model.check_values(history, spec),
            max_error_over_budget=ratio,
            independent_evaluations=expected["evaluations"],
            final_damage=float(state.damage[0]),
            analytic_damage=target,
        ),
        dict(observed=actual, reference=expected["state"]),
    )


def test_compiled_smoke_checkpoint_and_event_branch(tmp_path):
    spec = parse_spec(fixtures.definition(backend=BACKEND))
    value = run(spec)
    assert all(v.device.platform == BACKEND for v in value.final.state)
    c = reference.bind(spec.to_dict())
    expected = reference.integrate(spec.to_dict())
    ratio = assert_states(c, reference.flatten(c, vars(value.observations)), expected["state"])
    write_run(tmp_path / "injury", value)
    restored = load_snapshot(tmp_path / "injury/checkpoint_final")
    exact(restored.checkpoint.state, value.final.state)
    assert restored.spec == spec and type(restored.checkpoint.layout) is model.LAYOUT_TYPE
    # A restart exactly at the off-grid end of the injury pulse retains damage.
    t = 15.3e-6
    i = int(np.flatnonzero(value.times == t)[0])
    boundary = Checkpoint(
        model.STATE_TYPE(*(jnp.asarray(v[i]) for v in value.history)),
        value.final.layout,
        t,
        i,
        event_index(spec, t),
    )
    validate_checkpoint(spec, boundary)
    write_snapshot(tmp_path / "injury-boundary", spec, boundary)
    saved = load_snapshot(tmp_path / "injury-boundary")
    exact(saved.checkpoint.state, boundary.state)
    replay = run(saved.spec, saved.checkpoint)
    exact(replay.final.state, value.final.state)
    changed = spec.to_dict()
    for row in changed["experiment"]["injury_controls"]:
        row["schedule"][-1]["resealing"] = 0.0
    changed = parse_spec(changed)
    branch = branch_checkpoint(spec, boundary, changed)
    exact(branch.state, boundary.state)
    kept_open = run(changed, branch)
    exact(kept_open.final.state.damage, boundary.state.damage)
    assert value.final.state.damage[0] < kept_open.final.state.damage[0]
    batch = run_batch(BatchSpec((WorldSpec(7, spec), WorldSpec(29, changed)), 2, 256, 2**30))
    exact(batch.worlds[7].final.state, value.final.state)
    exact(batch.worlds[29].final.state, kept_open.final.state)
    evidence(
        "resolved-repair-compiled-replay",
        dict(
            status="passed",
            inputs=spec.to_dict(),
            diagnostics=value.diagnostics,
            max_error_over_budget=ratio,
            replay="bitwise complete state at injury-pulse boundary",
            branch="future closure disabled; complete boundary unchanged",
            independent_worlds="two worlds match complete scalar states bitwise",
            backend=BACKEND,
        ),
    )


def test_compiled_guard_retains_complete_state():
    spec, state, p = initial(fixtures.definition(backend=BACKEND))
    device = jax.devices(BACKEND)[0]
    state, p, control = jax.device_put((state, p, held(spec, 5.3e-6)), device)
    compute = jax.jit(
        lambda y, c, dt: rk4_checked_step(model.rhs, model.domain_valid, y, dt, c, p, p.active)
    )
    invalid = control._replace(injury=jnp.full_like(control.injury, 1.01))
    kept, valid = compute(state, invalid, spec.execution.dt)
    assert not valid
    exact(kept, state)
    bad_state = state._replace(damage=state.damage.at[0].set(-0.1))
    kept, valid = compute(bad_state, control, spec.execution.dt)
    assert not valid
    exact(kept, bad_state)
    # Valid starting values with an unresolved trial are refused, not clipped.
    kept, valid = compute(state, control, 1e6)
    assert not valid
    exact(kept, state)
    evidence(
        "resolved-repair-compiled-guard",
        dict(
            status="passed",
            backend=BACKEND,
            invalid_controls="refused",
            invalid_damage="refused",
            invalid_trial="refused",
            rejected_step_state="bitwise unchanged",
        ),
    )
