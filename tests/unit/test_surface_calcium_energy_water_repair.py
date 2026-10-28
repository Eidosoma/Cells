"""Full-owner injury composition, current-volume transport and rejection checks."""

from copy import deepcopy

import numpy as np
import pytest

from cells.core.errors import NumericalError
from cells.core.runner import timeline
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.surface_calcium_energy_water_repair_spec import base_spec
from cells.models import surface_calcium_energy_water as parent
from cells.models import surface_calcium_energy_water_repair as model
from cells.models.registry import get_model
from tests.unit.test_surface_calcium_energy_water import changed as change_parent
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_kinetic import assert_states, exact
from validation.tissue import calcium_energy_water_repair_fixtures as fixtures


def initial(raw=None, time=0.0):
    spec = parse_spec(fixtures.definition() if raw is None else raw)
    state, p = model.initial_values(spec)
    table = control_values(spec, [time])
    return spec, state, p, type(table)(*(v[0] for v in table))


def changed(spec, state, p):
    y = change_parent(spec, state, p, move_water=bool(np.any(p.water_conductance_pL_per_Pa_s > 0)))
    y.damage[0] += 0.15
    y.damage_opened[0] += 0.15
    return y


def compare(raw, state, rate, time):
    from validation.tissue import calcium_energy_water_repair_reference as reference

    c = reference.bind(raw)
    target, _, proof = reference.evaluate(c, reference.flatten(c, state._asdict()), time)
    ratio = assert_states(
        c,
        reference.flatten(c, rate._asdict()),
        target,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    assert abs(proof["physical_energy_balance_pJ_s"]) < 1e-9
    return dict(max_error_over_budget=ratio, independent_stage=proof)


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
@pytest.mark.parametrize("padded", [False, True])
def test_complete_identity_roundtrip_and_parent_projection(backend, padded):
    raw = fixtures.definition(backend=backend, padded=padded)
    spec, state, p, u = initial(raw)
    assert get_model(spec.model) is model
    assert parse_spec(spec.to_dict()) == spec
    assert len(state) == 48 and len(u) == 15
    prior = base_spec(spec)
    assert prior.to_dict()["model"]["id"] == parent.MODEL_ID
    ps, pp = parent.initial_values(prior)
    exact(model.base_state(state), ps)
    exact(model.base_layout(p), pp)
    assert model.check_values(state, spec)["max_damage_ledger_error"] == 0
    assert model.working_size(spec) > parent.working_size(prior)
    assert set(model.STATE_AXES) <= set(model.OBSERVATION_FIELDS)


def test_zero_damage_has_exact_parent_rates_without_resetting_fuel_or_water():
    spec, state, p, u = initial(fixtures.definition("sham"))
    y = change_parent(spec, state, p)
    actual = model.readouts(y, u, p, xp=np)
    target = parent.readouts(
        model.base_state(y), model.base_control(u), model.base_layout(p), xp=np
    )
    exact(model.base_state(actual.derivative), target.derivative)
    for key in model.EXTRA_AXES:
        assert not np.any(getattr(actual.derivative, key))
    opened = model.readouts(y, u._replace(injury=np.asarray(p.membrane_active, float)), p, xp=np)
    exact(model.base_state(opened.derivative), target.derivative)
    assert np.any(opened.derivative.damage > 0)
    assert not np.any(y.damage)


@pytest.mark.parametrize("arm", ["uninjured", "sham", "held", "resealing", "preinjured"])
@pytest.mark.parametrize("padded", [False, True])
def test_full48_reference_at_initial_and_changed_live_owners(arm, padded):
    raw = fixtures.definition(arm, padded=padded)
    spec, state, p, u = initial(raw, time=7e-6)
    checks = []
    for y in (state, changed(spec, state, p)):
        value = model.readouts(y, u, p, xp=np)
        assert value.valid and abs(value.field.energy_balance_pJ_s) < 1e-9
        assert np.all(value.derivative.injury_dissipated_energy_pJ >= 0)
        checks.append(compare(raw, y, value.derivative, 7e-6))
    evidence(f"joint-repair-stage-{arm}-{padded}", dict(status="passed", inputs=raw, checks=checks))


@pytest.mark.parametrize(
    "arm",
    [
        "blocked",
        "reordered",
        "empty",
        "instant_only",
        "dynamic_only",
        "sealed",
        "supply_off",
        "reverse",
        "absent",
    ],
)
def test_lesion_composes_with_parent_controls_and_absent_routes(arm):
    raw = fixtures.definition("preinjured", parent=arm)
    spec, state, p, u = initial(raw, time=7e-6)
    y = changed(spec, state, p)
    value = model.readouts(y, u, p, xp=np)
    assert value.valid
    proof = compare(raw, y, value.derivative, 7e-6)
    assert np.any(value.derivative.injury_transferred)
    blocked = model.readouts(y, u._replace(channel=np.zeros_like(u.channel)), p, xp=np)
    exact([blocked.derivative.injury_transferred], [value.derivative.injury_transferred])
    # No direct ATP debit or new water port is introduced by prescribed closure.
    original = parent.readouts(
        model.base_state(y), model.base_control(u), model.base_layout(p), xp=np
    )
    for key in ("energy_amount_increment_fmol", "volume_increment_pL", "pool_volume_work_pJ"):
        exact([getattr(value.derivative, key)], [getattr(original.derivative, key)])
    evidence(f"joint-repair-parent-{arm}", dict(status="passed", inputs=raw, check=proof))


@pytest.mark.parametrize(
    "fault",
    ["damage", "ledger", "heat", "padding", "ca_route", "fuel", "water", "regeneration_heat"],
)
def test_invalid_damage_and_parent_state_rejected_with_controls_blocked(fault):
    spec, state, p, u = initial()
    y = type(state)(*(v.copy() for v in state))
    if fault == "damage":
        y.damage[0] = 1.1
    elif fault == "ledger":
        y.damage_opened[0] = 0.1
    elif fault == "heat":
        y.injury_dissipated_energy_pJ[0, 0] = -0.1
    elif fault == "padding":
        y.damage[-1] = 0.1
    elif fault == "ca_route":
        y.injury_transferred[spec.model.species_ids.index("Ca"), 0] = 0.1
    elif fault == "fuel":
        y.energy_amount_increment_fmol[0, 0] = -p.energy_initial_amount_fmol[0, 0]
    elif fault == "water":
        y.volume_increment_pL[0] = -p.volume[0]
    else:
        y.regeneration_dissipated_energy_pJ[0] = -0.1
    blocked = type(u)(*(np.zeros_like(v) for v in u))
    assert not model.control_domain_valid(y, blocked, p, p.active, xp=np)
    with pytest.raises(NumericalError):
        model.check_values(y, spec)


@pytest.mark.parametrize("family", ["injury_controls", "water_controls", "regeneration_controls"])
def test_all_control_only_clocks_survive_timestep_projection(family):
    raw = fixtures.definition()
    time = 4.5 * raw["execution"]["dt"]
    row = raw["experiment"][family][0]
    value = dict(time=time, availability=0.2)
    if family == "injury_controls":
        value = dict(time=time, injury=0.2, resealing=0.3)
    row["schedule"].append(value)
    row["schedule"].sort(key=lambda v: v["time"])
    raw["experiment"]["observation_times"] = sorted(raw["experiment"]["observation_times"] + [time])
    spec = parse_spec(raw)
    assert time in timeline(spec)
    control = control_values(spec, [time])
    name = "injury" if family == "injury_controls" else family.removesuffix("_controls")
    assert getattr(control, name)[0, 0] == 0.2


def test_injury_loss_uses_minimum_volumes_and_damage_clock_is_bounded():
    raw = fixtures.definition()
    spec, _, _, _ = initial(raw)
    original = model.injury_loss_bound(spec)
    smaller = deepcopy(raw)
    for row in smaller["model"]["water_compartments"]:
        row["minimum_volume_pL"] *= 0.5
    lower = parse_spec(smaller)
    assert model.injury_loss_bound(lower) == 2 * original
    for row in raw["model"]["injury_patches"]:
        row.update(injury_rate_per_s=1e5, resealing_rate_per_s=1e5)
    with pytest.raises(ConfigError, match="damage rate"):
        timeline(parse_spec(raw))


@pytest.mark.parametrize("fault", ["calcium", "duplicate", "law", "missing", "bad_control"])
def test_injury_schema_has_explicit_owners_routes_and_controls(fault):
    raw = fixtures.definition()
    if fault == "calcium":
        raw["model"]["injury_patches"][0]["permeability_m_per_s"]["Ca"] = 1e-8
    elif fault == "duplicate":
        raw["model"]["injury_patches"][1] = deepcopy(raw["model"]["injury_patches"][0])
    elif fault == "law":
        raw["model"]["injury_patches"][0]["law"] = "implicit_healing"
    elif fault == "missing":
        raw["experiment"].pop("injury_controls")
    else:
        raw["experiment"]["injury_controls"][0]["schedule"][0]["injury"] = 1.1
    with pytest.raises(ConfigError):
        parse_spec(raw)


def test_observer_counts_injury_in_total_flux_and_energy_and_keeps_separate_ledgers():
    spec, state, p, u = initial(fixtures.definition("preinjured"))
    # Manufactured history only checks observer/accounting, not a trajectory claim.
    y = changed(spec, state, p)
    y.injury_dissipated_energy_pJ[0, 0] = 0.01
    history = type(y)(*(v[None] for v in y))
    obs = model.observe_history(np.array([0.0]), history, p, np.array([0.0]), spec)
    value = model.readouts(y, u, p, xp=np)
    np.testing.assert_array_equal(
        obs.membrane_flux_fmol_s[0], value.field.rates.membrane_flux_fmol_s
    )
    assert obs.energy_balance_pJ[0, 0] == model.balances(y, p)["energy"]
    assert obs.energy_balance_pJ_s[0, 0] == value.field.energy_balance_pJ_s
    np.testing.assert_array_equal(obs.injury_dissipated_energy_pJ[0], y.injury_dissipated_energy_pJ)
    np.testing.assert_array_equal(
        obs.energy_amount_increment_fmol[0], y.energy_amount_increment_fmol
    )
    np.testing.assert_array_equal(obs.volume_increment_pL[0], y.volume_increment_pL)
    assert np.isclose(
        model.free_energy_change(y, p),
        model.free_energy_change(
            y._replace(injury_dissipated_energy_pJ=np.zeros_like(y.injury_dissipated_energy_pJ)), p
        ),
        rtol=0,
        atol=1e-12,
    )
