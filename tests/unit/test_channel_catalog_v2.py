"""Versioned 39-law dispatch across ionic, owned calcium and finite-fuel tissue."""

from copy import deepcopy
from dataclasses import replace

import jax
import numpy as np
import pytest

from cells.assembly_cell.io import flatten, load_checkpoint, write_checkpoint
from cells.assembly_cluster import engine as assembly
from cells.assembly_cluster.controls import modulate
from cells.assembly_cluster.spec import channel_owners
from cells.assembly_cluster.spec import parse_spec as parse_assembly
from cells.core.batch import BatchSpec, WorldSpec, parse_batch
from cells.core.runner import run, timeline, validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import Checkpoint
from cells.ensemble import ionic
from cells.ensemble.cluster import aggregate
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import (
    surface_calcium_catalog_v2,
    surface_calcium_energy_catalog,
    surface_catalog_v2,
    surface_kinetic,
)
from cells.models.registry import get_model
from cells.processes import shared_channel_catalog as old_catalog
from cells.processes import shared_channel_catalog_v2 as catalog
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_kinetic import assert_states, exact
from validation.channels import calcium_catalog_extra_reference as scalar
from validation.tissue import channel_catalog_v2_fixtures as fixtures
from validation.tissue import surface_calcium_catalog_fixtures as old_calcium
from validation.tissue import surface_calcium_energy_fixtures as old_energy
from validation.tissue import surface_calcium_energy_reference as energy_reference
from validation.tissue import surface_calcium_reference as calcium_reference
from validation.tissue import surface_catalog_fixtures as old_ionic
from validation.tissue import surface_kinetic_reference as ionic_reference

MODELS = dict(
    ionic=surface_catalog_v2,
    calcium=surface_calcium_catalog_v2,
    energy=surface_calcium_energy_catalog,
)
REFERENCES = dict(ionic=ionic_reference, calcium=calcium_reference, energy=energy_reference)
PREVIOUS = dict(ionic=old_ionic, calcium=old_calcium, energy=old_energy)
OLD_IDS = dict(
    ionic="resolved_tissue@8", calcium="resolved_calcium@7", energy="resolved_calcium_energy@1"
)


def initial(family, raw=None):
    spec = parse_spec(fixtures.definition(family) if raw is None else raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    table = control_values(spec, [0.0])
    return spec, model, state, p, type(table)(*(v[0] for v in table))


def compare(family, spec, state, derivative, *, time=0.0, levels=None):
    ref = REFERENCES[family]
    c = ref.bind(spec.to_dict())
    kwargs = dict(channel_levels=levels) if levels is not None else {}
    target, _, proof = ref.evaluate(c, ref.flatten(c, state._asdict()), time, **kwargs)
    ratio = assert_states(
        c, ref.flatten(c, derivative._asdict()), target, atol=3e-12, charge_atol=3e-23, rtol=3e-10
    )
    return dict(max_error_over_budget=ratio, independent_stage=proof)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("backend", ["cpu", "gpu"])
def test_registered_versions_projection_and_roundtrip(family, backend):
    raw = fixtures.definition(family, backend=backend)
    spec, model, state, p, _ = initial(family, raw)
    assert get_model(spec.model) is MODELS[family] and type(p) is model.LAYOUT_TYPE
    assert spec == parse_spec(spec.to_dict())
    assert len(state) == dict(ionic=19, calcium=34, energy=38)[family]
    assert set(p.channel_laws[p.channel_active]) == set(range(39))
    assert len(spec.model.channels) == 43
    view = (
        p
        if family == "ionic"
        else (
            surface_calcium_catalog_v2.ionic_layout(state, p, xp=np)
            if family == "calcium"
            else surface_calcium_catalog_v2.ionic_layout(
                model.prior_state(state), model.prior_layout(p), xp=np
            )
        )
    )
    assert surface_kinetic.channel_process(view) is catalog
    assert (
        ionic.parse_spec(dict(model="ionic_worlds@1", simulation=raw, worlds=2)).simulation == spec
    )
    batch = BatchSpec((WorldSpec(3, spec), WorldSpec(79, spec)), 2, 2048, 2**32)
    assert parse_batch(batch.to_dict()) == batch
    timeline(spec)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("padded", [False, True])
def test_full_stage_fields_match_independent_reference(family, arm, padded):
    raw = fixtures.definition(family, arm, padded=padded)
    spec, model, state, p, u = initial(family, raw)
    value = model.readouts(state, u, p, xp=np)
    checked = compare(family, spec, state, value.derivative)
    assert value.valid and model.control_domain_valid(state, u, p, p.active, xp=np)
    assert abs(value.field.energy_balance_pJ_s) < 1e-10
    model.check_values(state, spec)
    if arm in ("blocked", "empty"):
        assert not np.any(value.derivative.channel_transferred)
    if padded:
        assert not np.any(value.derivative.channel_gate[:, -1])
        assert not np.any(value.derivative.channel_transferred[:, -1])
    evidence(
        f"catalog-v2-stage-{family}-{arm}-{padded}",
        dict(status="passed", inputs=raw, scope="complete instantaneous stage", **checked),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_old_35_law_models_and_rates_remain_bitwise_identical(family):
    raw = PREVIOUS[family].definition()
    old_spec, old_model, state, p, u = initial(family, raw)
    upgraded = deepcopy(raw)
    upgraded["model"]["id"] = fixtures.MODEL_IDS[family]
    if family != "ionic":
        upgraded["model"]["ionic"]["id"] = fixtures.MODEL_IDS["ionic"]
    spec, model, newer, q, v = initial(family, upgraded)
    assert old_spec.to_dict()["model"]["id"] == OLD_IDS[family]
    exact(state, newer)
    first, second = old_model.readouts(state, u, p, xp=np), model.readouts(newer, v, q, xp=np)
    exact(first.derivative, second.derivative)
    exact(jax.tree.leaves(first.field), jax.tree.leaves(second.field))
    evidence("catalog-v2-old-" + family, dict(status="passed", complete_rates_and_fields="bitwise"))


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("fault", ["old_identity", "inner_identity", "law", "route", "step"])
def test_strict_catalog_identity_route_and_step_boundaries(family, fault):
    raw = fixtures.definition(family)
    m = raw["model"] if family == "ionic" else raw["model"]["ionic"]
    if fault == "old_identity":
        raw["model"]["id"] = OLD_IDS[family]
        if family != "ionic":
            m["id"] = OLD_IDS["ionic"]
    elif fault == "inner_identity":
        m["id"] = OLD_IDS["ionic"]
    elif fault == "law":
        m["channels"][-1]["kinetic_law"] = "unknown_calcium_law@1"
    elif fault == "route":
        m["channels"][-1]["permeant_ions"][0]["species_id"] = "K"
    else:
        raw["execution"]["dt"] = 2.5e-6
    with pytest.raises(ConfigError):
        timeline(parse_spec(raw))


def test_dispatch_preserves_analytic_limit_shift_and_one_second_leak_clocks():
    voltage = np.array([-0.027] * 39)
    codes = np.arange(39)
    gate = np.broadcast_to(np.array([0.3, 0.7])[:, None], (2, 39)).copy()
    target, tau = catalog.kinetics(voltage, codes, xp=np)
    opened = catalog.opening(gate, codes, xp=np)
    for i, name in enumerate(scalar.CLASSES, 35):
        expected = scalar.kinetics(-0.027, name)
        np.testing.assert_allclose(target[:, i], expected["target"], rtol=3e-14, atol=2e-15)
        np.testing.assert_allclose(tau[:, i], expected["tau_s"], rtol=3e-14, atol=2e-15)
        assert abs(opened[i] - scalar.opening(gate[:, i], name)) < 2e-15
    exact((target[:, :35], tau[:, :35]), old_catalog.kinetics(voltage[:35], codes[:35], xp=np))
    assert not old_catalog.valid_codes(codes, xp=np)
    assert target[0, 35] != target[0, 36]
    np.testing.assert_array_equal(tau[:, 38], np.ones(2))
    assert opened[38] == 1.0
    evidence(
        "catalog-v2-limits",
        dict(
            status="passed",
            voltage_V=-0.027,
            targets=target[:, 35:].tolist(),
            tau_s=tau[:, 35:].tolist(),
        ),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_blocked_or_zero_permeability_caleak_keeps_auxiliary_clocks(family):
    spec, model, state, p, control = initial(family)
    slot = int(np.flatnonzero(p.channel_laws == 38)[0])
    blocked = control._replace(channel=control.channel.copy())
    blocked.channel[slot] = 0.0
    value = model.readouts(state, blocked, p, xp=np)
    assert not np.any(value.derivative.channel_transferred[:, slot])
    np.testing.assert_array_equal(
        value.derivative.channel_gate[:, slot], 1 - state.channel_gate[:, slot]
    )
    q = p._replace(channel_permeability=p.channel_permeability.copy())
    q.channel_permeability[slot] = 0.0
    zero = model.readouts(state, control, q, xp=np)
    np.testing.assert_array_equal(zero.derivative.channel_gate, value.derivative.channel_gate)
    assert not np.any(zero.derivative.channel_transferred[:, slot])
    wrong = state._replace(channel_gate=state.channel_gate.copy())
    wrong.channel_gate[0, slot] = 1.01
    assert not model.control_domain_valid(wrong, blocked, p, p.active, xp=np)


@pytest.mark.parametrize("family", ["calcium", "energy"])
def test_added_calcium_routes_have_one_free_chemical_owner_and_no_direct_atp_demand(family):
    spec, model, state, p, control = initial(family)
    slot = int(np.flatnonzero(p.channel_laws == 38)[0])
    patch = int(p.channel_membranes[slot])
    owner, outside = int(p.membrane_cell[patch]), int(p.membrane_outside[patch])
    held = control._replace(channel=control.channel.copy())
    held.channel[slot] = 0.0
    before, after = (model.readouts(state, u, p, xp=np) for u in (control, held))
    flux = before.derivative.channel_transferred[:, slot]
    assert np.count_nonzero(flux) == 1
    expected = np.zeros_like(state.chemical_amount_increment)
    expected[owner, p.ionic_species, int(p.er_cytosol[owner])] = -flux
    np.testing.assert_allclose(
        before.derivative.chemical_amount_increment - after.derivative.chemical_amount_increment,
        expected,
        atol=3e-14,
        rtol=3e-10,
    )
    for name, index, sign in (
        ("amount_increment", owner, -1),
        ("extracellular_amount_increment", outside, 1),
    ):
        expected = np.zeros_like(getattr(state, name))
        expected[:, index] = sign * flux
        np.testing.assert_allclose(
            getattr(before.derivative, name) - getattr(after.derivative, name),
            expected,
            atol=3e-14,
            rtol=3e-10,
        )
    if family == "energy":
        exact(
            (before.derivative.energy_amount_increment_fmol,),
            (after.derivative.energy_amount_increment_fmol,),
        )
    changed = model.STATE_TYPE(*(v.copy() for v in state))
    names = [s.id for s in spec.model.stores[owner].species]
    ids = [names.index(k) for k in ("Ca", "B", "CaB")]
    changed.chemical_amount_increment[owner, ids, int(p.er_cytosol[owner])] += 1e-4 * np.array(
        [-1, -1, 1]
    )
    value = model.readouts(changed, control, p, xp=np)
    assert value.valid and not np.array_equal(value.derivative.channel_transferred[:, slot], flux)
    checked = compare(family, spec, changed, value.derivative)
    evidence("catalog-v2-free-owner-" + family, dict(status="passed", **checked))


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize(
    "fault", ["hidden_species", "pad_control", "pad_law", "unknown_law", "nan_gate"]
)
def test_new_routes_cannot_hide_invalid_state_or_controls(family, fault):
    _, model, state, p, u = initial(family, fixtures.definition(family, "blocked"))
    slot = int(np.flatnonzero(p.channel_laws == 38)[0])
    if fault == "hidden_species":
        state.channel_transferred[0, slot] = 1e-5
    elif fault == "pad_control":
        u.channel[-1] = 0.1
    elif fault == "pad_law":
        p.channel_laws[-1] = 38
    elif fault == "unknown_law":
        p.channel_laws[slot] = 39
    else:
        state.channel_gate[0, slot] = np.nan
    assert not model.control_domain_valid(state, u, p, p.active, xp=np)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_snapshot_preserves_catalog_layout_and_rejects_other_version(family, tmp_path):
    spec, model, state, p, _ = initial(family, fixtures.compact_probe(family))
    point = Checkpoint(state, p, 0.0, 0, event_index(spec, 0.0))
    write_snapshot(tmp_path / "initial", spec, point)
    saved = load_snapshot(tmp_path / "initial")
    assert saved.spec == spec and type(saved.checkpoint.layout) is model.LAYOUT_TYPE
    exact(saved.checkpoint.state, state)
    exact(saved.checkpoint.layout, p)
    old_spec = parse_spec(PREVIOUS[family].definition())
    old_type = get_model(old_spec.model).LAYOUT_TYPE
    with pytest.raises(ConfigError, match="state/layout"):
        validate_checkpoint(spec, replace(point, layout=old_type(*p)))


@pytest.mark.parametrize("family", ["calcium", "energy"])
def test_assembly_reports_owner_controls_and_complete_checkpoint(family, tmp_path):
    spec = parse_assembly(fixtures.assembly_definition(family))
    _, model, state, p, u = initial(family, spec.ionic.to_dict())
    levels = np.array([0.0, 1.0])
    held = modulate(u, levels, channel_owners(spec))
    actual = model.readouts(state, held, p, xp=np)
    assert actual.valid
    compare(family, spec.ionic, state, actual.derivative, levels=levels)
    if family == "energy":
        np.testing.assert_array_equal(held.regeneration, u.regeneration)
    initial_state = assembly.initial_state(spec)
    report = assembly.summary(spec, initial_state) | dict(
        arm=family, wall_start=0.0, wall_end=1.0, execute_seconds=0.0
    )
    assert report["physical_model"] == fixtures.MODEL_IDS[family]
    combined = aggregate([report, report])[family]
    assert combined["worlds"] == 2 * spec.pool.worlds
    for key in ("ip3", "calcium", "channel_transfer_axes", "channel_species_ids") + (
        ("finite_energy",) if family == "energy" else ()
    ):
        wrong = deepcopy(report)
        wrong.pop(key)
        with pytest.raises(ValueError):
            aggregate([report, wrong])
    write_checkpoint(tmp_path / "assembly", spec, initial_state, backend="cpu")
    restored, newer, _ = load_checkpoint(tmp_path / "assembly", backend="cpu")
    assert restored == spec
    exact(flatten(newer).values(), flatten(initial_state).values())
    evidence(
        "catalog-v2-assembly-" + family,
        dict(
            status="passed",
            report=report,
            scope="Initial state/report/checkpoint and controlled stage; no stochastic history",
        ),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_compiled_two_world_stage_and_isolated_failure(family):
    spec, model, state, p, u = initial(family)
    states = model.STATE_TYPE(*(np.stack((v, v)) for v in state))
    controls = type(u)(*(np.stack((v, v)) for v in u))
    selected = (p.channel_laws >= 35) & p.channel_active
    states.channel_gate[1, 0, selected] = 0.51
    evaluate = jax.jit(
        jax.vmap(
            lambda y, c, q: (
                model.rhs(y, c, q, q.active),
                model.control_domain_valid(y, c, q, q.active),
            ),
            in_axes=(0, 0, None),
        )
    )
    got, valid = evaluate(states, controls, p)
    assert np.all(valid)
    checked = []
    for i in (0, 1):
        y = model.STATE_TYPE(*(v[i] for v in states))
        derivative = model.STATE_TYPE(*(v[i] for v in got))
        checked.append(compare(family, spec, y, derivative))
    bad = states._replace(channel_gate=states.channel_gate.copy())
    bad.channel_gate[1, 0, np.flatnonzero(p.channel_laws == 38)[0]] = 1.01
    failed, valid = evaluate(bad, controls, p)
    assert np.array_equal(np.asarray(valid), [True, False])
    assert all(np.isnan(v[1]).all() for v in failed)
    exact((v[0] for v in failed), (v[0] for v in got))
    evidence(
        "catalog-v2-compiled-" + family,
        dict(
            status="passed",
            inputs=spec.to_dict(),
            worlds=2,
            world_checks=checked,
            invalid_world_isolated=True,
        ),
    )


def test_compiled_coupled_fuel_trajectory_controls_and_final_snapshot(tmp_path):
    raw = fixtures.compact_probe("energy")
    result = run(parse_spec(raw))
    c = energy_reference.bind(raw)
    expected = energy_reference.integrate(raw)
    actual = energy_reference.flatten(c, vars(result.observations))
    target = np.asarray(expected["state"])
    report = dict(
        status="captured",
        inputs=raw,
        diagnostics=result.diagnostics,
        independent_reference={
            k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in expected.items()
        },
        scope="50 us of live free-calcium/fuel feedback and separate channel/supply events",
    )
    evidence(
        "catalog-v2-trajectory",
        report,
        dict(observed=actual, reference=target, signed_error=actual - target),
    )
    write_run(tmp_path / "early", result)
    ratio = assert_states(c, actual, target)
    saved = load_snapshot(tmp_path / "early/checkpoint_final")
    assert saved.spec == result.spec
    exact(saved.checkpoint.state, result.final.state)
    exact(saved.checkpoint.layout, result.final.layout)
    assert type(saved.checkpoint.layout) is surface_calcium_energy_catalog.LAYOUT_TYPE
    evidence(
        "catalog-v2-trajectory",
        report | dict(status="passed", max_error_over_budget=ratio, complete_final_snapshot=True),
    )
