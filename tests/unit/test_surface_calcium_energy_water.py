"""Live shared fuel, chemical ownership, bounded water and complete CPU state."""

import json
from pathlib import Path

import numpy as np
import pytest

from cells.core.errors import NumericalError
from cells.core.runner import timeline
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.surface_calcium_energy_spec import initial_prior_spec
from cells.core.surface_calcium_energy_water_spec import energy_spec, minimum_energy_spec
from cells.ensemble import ionic
from cells.models import surface_calcium_energy as fuel
from cells.models import surface_calcium_energy_water as model
from cells.models import surface_calcium_water as chemical_water
from cells.models.registry import get_model
from cells.processes import morris_lecar_catalog as catalog
from tests.unit.test_morris_lecar_catalog import perturb_free_calcium
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_kinetic import assert_states, exact
from validation.tissue import calcium_energy_water_fixtures as fixtures


def initial(raw=None, time=0.0):
    spec = parse_spec(fixtures.definition() if raw is None else raw)
    state, p = model.initial_values(spec)
    table = control_values(spec, [time])
    return spec, state, p, type(table)(*(v[0] for v in table))


def changed(spec, state, p, *, move_water=True):
    y = perturb_free_calcium("calcium", spec, state, p)
    delta = 0.1 * p.energy_initial_amount_fmol[0, 0]
    y.energy_amount_increment_fmol[:, 0] = [-delta, delta, delta]
    y.channel_gate[0, p.channel_laws == 40] = 0.51
    if move_water:
        patch = int(np.flatnonzero(p.membrane_active)[0])
        y.volume_increment_pL[p.membrane_cell[patch]] += 0.08
        y.extracellular_volume_increment_pL[p.membrane_outside[patch]] -= 0.08
        y.water_transferred_pL[patch] -= 0.08
    return y


def compare(spec, state, derivative, time=0.0):
    from validation.tissue import calcium_energy_water_reference as reference

    c = reference.bind(spec.to_dict())
    target, _, proof = reference.evaluate(c, reference.flatten(c, state._asdict()), time)
    ratio = assert_states(
        c,
        reference.flatten(c, derivative._asdict()),
        target,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    assert abs(proof["physical_energy_balance_pJ_s"]) < 1e-9
    return dict(max_error_over_budget=ratio, independent_stage=proof)


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
@pytest.mark.parametrize("padded", [False, True])
def test_identity_projection_and_complete_43field_owner(backend, padded):
    raw = fixtures.definition(backend=backend, padded=padded)
    spec, state, p, _ = initial(raw)
    assert get_model(spec.model) is model and type(p) is model.LAYOUT_TYPE
    assert len(state) == 43 and len(spec.model.channels) == 60
    assert set(p.channel_laws[p.channel_active]) == set(range(53))
    assert spec == parse_spec(spec.to_dict())
    finite = energy_spec(spec)
    assert finite.to_dict()["model"]["id"] == "resolved_calcium_energy@4"
    assert initial_prior_spec(finite).to_dict()["model"]["id"] == "resolved_calcium@10"
    assert (
        ionic.parse_spec(dict(model="ionic_worlds@1", simulation=raw, worlds=2)).simulation == spec
    )
    timeline(spec)
    model.check_values(state, spec)
    if backend == "cpu" and padded:
        path = Path(__file__).resolve().parents[2] / "configs/resolved_calcium_energy_water.json"
        assert json.loads(path.read_text()) == raw


@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("padded", [False, True])
def test_full43_rates_at_live_calcium_fuel_and_volume(arm, padded):
    time = 36e-6 if arm == "release" else 0.0
    spec, state, p, u = initial(fixtures.definition(arm, padded=padded), time)
    y = changed(spec, state, p, move_water=arm != "sealed")
    before = tuple(v.copy() for v in y)
    v = model.readouts(y, u, p, xp=np)
    assert v.valid
    proof = compare(spec, y, v.derivative, time)
    exact(y, before)
    absent = ~(catalog.gate_active(p.channel_laws, xp=np) & p.channel_active)
    assert np.all(v.derivative.channel_gate[absent] == 0)
    if arm in ("blocked", "empty"):
        assert not np.any(v.derivative.channel_transferred)
    if arm == "supply_off":
        assert not np.any(v.derivative.regeneration_cycles_fmol)
    if arm == "sealed":
        assert not np.any(v.water.edge_flow_pL_s)
        assert not np.any(v.derivative.pool_volume_work_pJ)
    if arm == "absent":
        assert not np.any(v.derivative.pump_cycles)
        assert not np.any(v.derivative.plasma_pump_cycles)
        assert not np.any(v.derivative.er_pump_transferred)
    evidence(f"joint-stage-{arm}-{padded}", dict(status="passed", inputs=spec.to_dict(), **proof))


def test_all_three_pumps_and_particle_counts_use_live_pool_and_cytosol():
    spec, state, p, u = initial()
    y = changed(spec, state, p)
    current = model.effective_layout(y, p)
    stage = fuel.stage_layout(model.prior_state(y), current, xp=np)
    pool = fuel.energy_amounts(y, p) / current.volume
    for key, owner in (
        ("pump_", p.membrane_cell),
        ("pmca_", p.membrane_cell),
        ("er_pump_", np.arange(len(p.er_pump_present))),
    ):
        active = getattr(p, key + "present")
        for i, name in enumerate(("atp", "adp", "pi")):
            # Na/K uses the ionic pump layout's concentration names.
            name = key + name + ("_mM" if key == "pump_" else "")
            actual = getattr(stage, name)
            np.testing.assert_array_equal(actual[active], pool[i, owner[active]])
    cy = p.cytosol_selector.astype(bool)
    np.testing.assert_array_equal(current.er_volume[cy], current.volume[: len(p.er_volume)])
    np.testing.assert_array_equal(current.er_volume[~cy], p.er_volume[~cy])
    chemical = chemical_water.osmolyte_amounts(y, p)
    all_particles = model.osmolyte_amounts(y, p)
    exact(all_particles[:-3], chemical)
    exact(all_particles[-3:, : p.active.size], fuel.energy_amounts(y, p))
    assert np.all(all_particles[-3:, p.active.size :] == 0)
    assert np.all(np.sum(all_particles, axis=0) <= model.maximum_osmolytes(p))
    value = model.readouts(y, u, p, xp=np)
    assert value.valid and abs(value.field.energy_balance_pJ_s) < 1e-9


@pytest.mark.parametrize(
    "kind", ["fuel", "water", "er", "gate", "padding", "work", "heat", "regeneration_heat"]
)
def test_invalid_states_rejected_under_blocked_controls(kind):
    spec, state, p, u = initial()
    y = type(state)(*(v.copy() for v in state))
    if kind == "fuel":
        y.energy_amount_increment_fmol[0, 0] = -p.energy_initial_amount_fmol[0, 0]
    elif kind == "water":
        y.volume_increment_pL[0] = -p.volume[0]
    elif kind == "er":
        y.chemical_amount_increment[0, 0, p.er_er[0]] = (
            -2 * p.er_initial_amount[0, 0, p.er_er[0]] - 1
        )
    elif kind == "gate":
        y.channel_gate[0, np.flatnonzero(p.channel_laws == 46)[0]] = 0.25
    elif kind == "padding":
        y.volume_increment_pL[-1] = 0.1
    elif kind == "work":
        y.pool_volume_work_pJ[-1] = 1.0
    elif kind == "regeneration_heat":
        y.regeneration_dissipated_energy_pJ[0] = -0.1
    else:
        y.water_dissipated_energy_pJ[0] = -0.1
    blocked = type(u)(*(np.zeros_like(v) for v in u))
    with np.errstate(all="ignore"):
        assert not model.control_domain_valid(y, blocked, p, p.active, xp=np)
        with pytest.raises(NumericalError):
            model.check_values(y, spec)


def test_permanently_sealed_routes_cannot_own_water_or_pool_volume_work():
    spec, state, p, u = initial(fixtures.definition("sealed"))
    for key in ("water_transferred_pL", "water_dissipated_energy_pJ", "pool_volume_work_pJ"):
        y = type(state)(*(v.copy() for v in state))
        getattr(y, key)[0] = 0.01
        assert not model.control_domain_valid(y, u, p, p.active, xp=np)


@pytest.mark.parametrize("family", ["water_controls", "regeneration_controls"])
def test_control_only_boundary_is_not_lost_in_projection(family):
    raw = fixtures.definition()
    dt = raw["execution"]["dt"]
    time = 4.5 * dt
    raw["experiment"][family][0]["schedule"].append(dict(time=time, availability=0.2))
    raw["experiment"][family][0]["schedule"].sort(key=lambda x: x["time"])
    raw["experiment"]["observation_times"] = sorted(raw["experiment"]["observation_times"] + [time])
    spec = parse_spec(raw)
    assert time in timeline(spec)
    assert getattr(control_values(spec, [time]), family.removesuffix("_controls"))[0, 0] == 0.2


@pytest.mark.parametrize("key", ["chemical_osmotic_coupling", "energy_osmotic_coupling"])
def test_explicit_osmotic_ownership_required(key):
    raw = fixtures.definition()
    raw["model"][key] = "implicit"
    with pytest.raises(ConfigError, match="osmotic"):
        parse_spec(raw)


def test_minimum_volume_bound_changes_all_cytosols_but_not_er():
    spec, _, _, _ = initial()
    lower = minimum_energy_spec(spec)
    limits = {x.compartment_id: x.minimum_volume_pL for x in spec.model.water_compartments}
    for cell, original, store in zip(
        lower.model.cells, spec.model.stores, lower.model.stores, strict=True
    ):
        assert cell.volume_pL == limits[cell.id]
        for old, new in zip(original.compartments, store.compartments, strict=True):
            assert new.volume_pL == (
                limits[cell.id] if old.id == store.membrane.cytosol else old.volume_pL
            )
    assert lower.experiment is spec.experiment


def test_no_duplicated_chemical_fuel_species():
    raw = fixtures.definition()
    # Rename one chemically neutral species consistently; species reordering
    # must not provide a second inventory of the already-owned fuel molecules.
    raw = json.loads(json.dumps(raw).replace('"B"', '"ATP"'))
    with pytest.raises(ConfigError, match="exclusively"):
        parse_spec(raw)


def test_sealed_water_reproduces_fixed_volume_finite_calcium_rates_exactly():
    spec, state, p, u = initial(fixtures.definition("sealed"))
    fixed = energy_spec(spec)
    old, q = fuel.initial_values(fixed)
    exact(model.prior_state(state), old)
    exact(model.prior_layout(p), q)
    actual = model.readouts(state, u, p, xp=np)
    target = fuel.readouts(old, model.base_control(u), q, xp=np)
    exact(model.prior_state(actual.derivative), target.derivative)
    for key in model.EXTRA_AXES:
        assert not np.any(getattr(actual.derivative, key))


def test_observer_uses_current_chemical_and_fuel_volume_and_joint_energy():
    spec, state, p, u = initial()
    y = changed(spec, state, p)
    history = type(y)(*(v[None] for v in y))
    obs = model.observe_history(np.array([0.0]), history, p, np.array([0.0]), spec)
    np.testing.assert_array_equal(
        obs.energy_concentration_mM[0],
        fuel.energy_amounts(y, p) / (p.volume + y.volume_increment_pL),
    )
    np.testing.assert_array_equal(
        obs.er_volume_pL[0], p.er_volume[np.arange(len(p.er_volume)), p.er_er]
    )
    assert obs.energy_balance_pJ[0, 0] == model.balances(y, p)["energy"]
    np.testing.assert_array_equal(
        obs.energy_free_energy_change_pJ[0], model.pool_free_energy_change_pJ(y, p)
    )
    exact(
        obs.pool_volume_power_pJ_s[0], model.readouts(y, u, p, xp=np).derivative.pool_volume_work_pJ
    )
