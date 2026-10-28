"""Hybrid channel catalog, current concentrations and conservative compliant water."""

import jax
import numpy as np
import pytest

from cells.core.runner import run, timeline
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.surface_water_kinetic_spec import prior_spec
from cells.ensemble import ionic
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import surface_kinetic, surface_water_kinetic
from cells.models import surface_water_morris_lecar as model
from cells.models.registry import get_model
from cells.processes import morris_lecar_catalog as catalog
from tests.unit.test_surface_kinetic import exact
from tests.unit.test_surface_water_kinetic import error_budget, evidence
from validation.tissue import morris_lecar_water_fixtures as fixtures
from validation.tissue import surface_water_kinetic_fixtures as old_fixtures
from validation.tissue import surface_water_kinetic_reference as reference


def initial(raw=None, time=0.0):
    spec = parse_spec(fixtures.definition() if raw is None else raw)
    state, p = model.initial_values(spec)
    controls = control_values(spec, [time])
    return spec, state, p, type(controls)(*(v[0] for v in controls))


def moved_water(state, p):
    y = type(state)(*(v.copy() for v in state))
    patch = int(np.flatnonzero(p.membrane_active)[0])
    a, b = int(p.membrane_cell[patch]), int(p.membrane_outside[patch])
    y.volume_increment_pL[a] += 0.08
    y.extracellular_volume_increment_pL[b] -= 0.08
    y.water_transferred_pL[patch] -= 0.08
    return y


def compare(spec, state, derivative, time=0.0):
    c = reference.bind(spec.to_dict())
    target, _, proof = reference.evaluate(c, reference.flatten(c, state._asdict()), time)
    ratio = error_budget(
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
def test_registered_version_and_complete_state(backend, padded):
    spec, state, p, _ = initial(fixtures.definition(backend=backend, padded=padded))
    assert get_model(spec.model) is model and type(p) is model.LAYOUT_TYPE
    assert len(state) == 23 and len(spec.model.channels) == 60
    assert set(p.channel_laws[p.channel_active]) == set(range(53))
    assert spec == parse_spec(spec.to_dict())
    assert prior_spec(spec).to_dict()["model"]["id"] == "resolved_tissue@11"
    assert (
        ionic.parse_spec(
            dict(model="ionic_worlds@1", simulation=spec.to_dict(), worlds=2)
        ).simulation
        == spec
    )
    timeline(spec)
    model.check_values(state, spec)


@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("padded", [False, True])
@pytest.mark.parametrize("nonzero", [False, True])
def test_complete_stage_uses_current_volume_and_channel_owner(arm, padded, nonzero):
    spec, state, p, control = initial(fixtures.definition(arm, padded=padded))
    if nonzero:
        state = moved_water(state, p)
    before = tuple(v.copy() for v in state)
    value = model.readouts(state, control, p, xp=np)
    if arm == "sealed" and nonzero:
        # A permanently absent hydraulic route cannot have accumulated flow.
        # Preserve this impossible history as a rejection case.
        assert not value.valid
        assert not model.control_domain_valid(state, control, p, p.active, xp=np)
        exact(state, before)
        evidence(
            f"morris-lecar-sealed-history-rejected-{padded}",
            dict(
                status="passed",
                inputs=spec.to_dict(),
                scope="Nonzero flow history on a permanently sealed route is invalid",
            ),
        )
        return
    assert value.valid
    checked = compare(spec, state, value.derivative)
    exact(state, before)
    absent = ~(catalog.gate_active(p.channel_laws, xp=np) & p.channel_active)
    assert np.all(value.derivative.channel_gate[absent] == 0)
    assert (
        abs(
            sum(value.derivative.volume_increment_pL)
            + sum(value.derivative.extracellular_volume_increment_pL)
        )
        < 3e-13
    )
    if arm in ("blocked", "empty"):
        assert not np.any(value.derivative.channel_transferred)
    if arm == "sealed":
        assert not np.any(value.water.edge_flow_pL_s)
    if padded:
        assert not np.any(value.derivative.channel_transferred[:, -1])
        assert value.derivative.volume_increment_pL[-1] == 0
        assert value.derivative.extracellular_volume_increment_pL[-1] == 0
    evidence(
        f"morris-lecar-stage-{arm}-{padded}-{nonzero}",
        dict(
            status="passed",
            inputs=spec.to_dict(),
            nonzero_volume=nonzero,
            scope="complete instantaneous stage",
            **checked,
        ),
    )


@pytest.mark.parametrize("arm", old_fixtures.ARMS)
@pytest.mark.parametrize("nonzero", [False, True])
def test_previous_water_catalog_rates_stay_bitwise_identical(arm, nonzero):
    raw = old_fixtures.definition(arm)
    old, state, p, control = initial(raw)
    raw["model"]["id"] = fixtures.MODEL_ID
    spec, newer, q, other = initial(raw)
    if nonzero:
        state, newer = moved_water(state, p), moved_water(newer, q)
    exact(state, newer)
    a = surface_water_kinetic.readouts(state, control, p, xp=np)
    b = model.readouts(newer, other, q, xp=np)
    exact(a.derivative, b.derivative)
    exact(jax.tree.leaves(a.field), jax.tree.leaves(b.field))
    exact(a.water, b.water)
    assert old.to_dict()["model"]["id"] == "resolved_water@2"
    assert spec.to_dict()["model"]["id"] == "resolved_water@3"


def test_sealed_water_reduces_to_exact_53_law_ionic_rates():
    spec, state, p, u = initial(fixtures.definition("sealed"))
    ionic_spec = prior_spec(spec)
    old, q = surface_kinetic.initial_values(ionic_spec)
    table = control_values(ionic_spec, [0.0])
    control = type(table)(*(v[0] for v in table))
    expected = surface_kinetic.readouts(old, control, q, xp=np)
    actual = model.readouts(state, u, p, xp=np)
    exact(model.prior_state(actual.derivative), expected.derivative)
    assert all(not np.any(getattr(actual.derivative, name)) for name in model.EXTRA_AXES)


@pytest.mark.parametrize(
    "fault",
    [
        "old_identity",
        "gate_count",
        "ion_route",
        "water_owner",
        "reservoir",
        "temperature",
        "gate_step",
        "water_step",
    ],
)
def test_strict_schema_and_independent_step_bounds(fault):
    raw = fixtures.definition()
    m = raw["model"]
    if fault == "old_identity":
        m["id"] = "resolved_water@2"
    elif fault == "gate_count":
        m["channels"][-1]["initial_gate"] = [0.0]
    elif fault == "ion_route":
        m["channels"][-1]["permeant_ions"].append(dict(species_id="Ca", relative_permeability=0.0))
    elif fault == "water_owner":
        m["water_compartments"][0]["compartment_id"] = "absent_owner"
    elif fault == "reservoir":
        m["extracellular"][0]["reservoir"] = True
    elif fault == "temperature":
        m["temperature_K"] = 300.0
    elif fault == "gate_step":
        raw["execution"]["dt"] = 2.5e-6
    else:
        raw = fixtures.definition("instant_only")
        raw["execution"]["dt"] = 1e-2
        raw["experiment"].update(end_time=1e-2, observation_times=[0.0, 1e-2])
    with pytest.raises(ConfigError):
        timeline(parse_spec(raw))


@pytest.mark.parametrize("arm", ["instant_only", "dynamic_only"])
def test_only_real_gate_clocks_constrain_the_water_timestep(arm):
    raw = fixtures.definition(arm)
    # Above the older two-gate catalog's 1.25-us ceiling, below this fixture's
    # independent water bound. Removing a gate clock does not remove water's.
    raw["execution"]["dt"] = 2.5e-6
    spec = parse_spec(raw)
    timeline(spec)
    assert all(
        len(c.initial_gate) == (0 if arm == "instant_only" else 1) for c in spec.model.channels
    )
    raw["execution"]["dt"] = 25e-6
    with pytest.raises(ConfigError, match="water relaxation"):
        timeline(parse_spec(raw))


@pytest.mark.parametrize(
    "fault",
    [
        "instant_m",
        "dynamic_h",
        "pad_gate",
        "hidden_species",
        "pad_control",
        "unknown_law",
        "volume",
        "water_control",
    ],
)
def test_blocked_populations_do_not_hide_invalid_state(fault):
    _, y, p, u = initial(fixtures.definition("blocked"))
    slot = int(np.flatnonzero(p.channel_laws == 46)[0])
    if fault == "instant_m":
        y.channel_gate[0, slot] = 0.25
    elif fault == "dynamic_h":
        y.channel_gate[1, np.flatnonzero(p.channel_laws == 40)[0]] = 0.25
    elif fault == "pad_gate":
        y.channel_gate[0, -1] = 0.25
    elif fault == "hidden_species":
        y.channel_transferred[0, slot] = 1e-6
    elif fault == "pad_control":
        u.channel[-1] = 0.1
    elif fault == "unknown_law":
        p.channel_laws[slot] = 53
    elif fault == "volume":
        y.volume_increment_pL[0] = -p.volume[0]
    else:
        u.water[-1] = 0.1
    assert not model.control_domain_valid(y, u, p, p.active, xp=np)


def test_blocking_and_zero_permeability_keep_dynamic_gate_clocks():
    spec, y, p, u = initial()
    y = moved_water(y, p)
    dynamics = (p.channel_laws >= 40) & (p.channel_laws <= 44)
    for mode in ("blocked", "zero_permeability"):
        q = p._replace(channel_permeability=p.channel_permeability.copy())
        held = u._replace(channel=u.channel.copy())
        if mode == "blocked":
            held.channel[p.channel_active] = 0.0
        else:
            q.channel_permeability[p.channel_active] = 0.0
        value = model.readouts(y, held, q, xp=np)
        assert value.valid and not np.any(value.derivative.channel_transferred)
        assert np.all(value.derivative.channel_gate[0, dynamics] != 0)
        assert np.all(value.derivative.channel_gate[1, dynamics] == 0)


def test_initial_snapshot_keeps_the_new_catalog_and_water_owners(tmp_path):
    spec, y, p, _ = initial(fixtures.compact_probe())
    from cells.core.state import Checkpoint

    checkpoint = Checkpoint(y, p, 0.0, 0, 0)
    write_snapshot(tmp_path / "initial", spec, checkpoint)
    saved = load_snapshot(tmp_path / "initial")
    assert saved.spec == spec and type(saved.checkpoint.layout) is model.LAYOUT_TYPE
    exact(saved.checkpoint.state, y)
    exact(saved.checkpoint.layout, p)


def test_compiled_two_world_stage_uses_live_volumes_and_isolates_failure():
    spec, y, p, u = initial()
    changed = moved_water(y, p)
    changed.channel_gate[0, p.channel_laws == 40] = 0.51
    states = model.STATE_TYPE(*(np.stack((a, b)) for a, b in zip(y, changed, strict=True)))
    controls = type(u)(*(np.stack((v, v)) for v in u))
    evaluate = jax.jit(
        jax.vmap(
            lambda state, control, q: (
                model.rhs(state, control, q, q.active),
                model.control_domain_valid(state, control, q, q.active),
            ),
            in_axes=(0, 0, None),
        )
    )
    rates, valid = evaluate(states, controls, p)
    assert np.all(valid)
    checked = []
    for i in (0, 1):
        state = model.STATE_TYPE(*(v[i] for v in states))
        derivative = model.STATE_TYPE(*(v[i] for v in rates))
        checked.append(compare(spec, state, derivative))
    bad = states._replace(channel_gate=states.channel_gate.copy())
    bad.channel_gate[1, 0, np.flatnonzero(p.channel_laws == 46)[0]] = 0.25
    failed, valid = evaluate(bad, controls, p)
    assert np.array_equal(np.asarray(valid), [True, False])
    assert all(np.isnan(v[1]).all() for v in failed)
    exact((v[0] for v in failed), (v[0] for v in rates))
    evidence(
        "morris-lecar-compiled-stage",
        dict(
            status="passed",
            inputs=spec.to_dict(),
            world_checks=checked,
            invalid_world_isolated=True,
        ),
    )


def test_compiled_early_trajectory_controls_conservation_and_final_snapshot(tmp_path):
    raw = fixtures.compact_probe()
    result = run(parse_spec(raw))
    c = reference.bind(raw)
    expected = reference.integrate(raw)
    actual = reference.flatten(c, vars(result.observations))
    target = np.asarray(expected["state"])
    report = dict(
        status="captured",
        inputs=raw,
        diagnostics=result.diagnostics,
        scope="50-us full23 early coupling; separate channel/water/pump events; no full settling",
        independent_reference={
            k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in expected.items()
        },
    )
    evidence(
        "morris-lecar-trajectory",
        report,
        dict(observed=actual, reference=target, signed_error=actual - target),
    )
    ratio = error_budget(c, actual, target)
    absent = ~(
        catalog.gate_active(result.final.layout.channel_laws, xp=np)
        & result.final.layout.channel_active
    )
    assert np.all(result.observations.channel_gate[:, absent] == 0)
    assert np.max(np.abs(result.observations.volume_increment_pL)) > 1e-4
    write_run(tmp_path / "coupled", result)
    saved = load_snapshot(tmp_path / "coupled/checkpoint_final")
    assert saved.spec == result.spec and type(saved.checkpoint.layout) is model.LAYOUT_TYPE
    exact(saved.checkpoint.state, result.final.state)
    exact(saved.checkpoint.layout, result.final.layout)
    evidence(
        "morris-lecar-trajectory",
        report
        | dict(
            status="passed",
            max_error_over_budget=ratio,
            complete_final_snapshot=True,
            absent_gate_slots_exact_zero=True,
        ),
    )
