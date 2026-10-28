"""Instantaneous free-calcium potassium in versioned ionic and owned/fuel models."""

import json
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
    surface_calcium_activated,
    surface_calcium_activated_catalog,
    surface_calcium_energy_activated,
    surface_kinetic,
)
from cells.models.registry import get_model
from cells.processes import calcium_activated_catalog as catalog
from cells.processes import shared_channel_catalog_v2 as old_catalog
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_kinetic import assert_states, exact
from validation.channels import calcium_activated_potassium_reference as scalar
from validation.tissue import calcium_activated_catalog_fixtures as fixtures
from validation.tissue import channel_catalog_v2_fixtures as previous
from validation.tissue import surface_calcium_energy_reference as energy_reference
from validation.tissue import surface_calcium_reference as calcium_reference
from validation.tissue import surface_kinetic_reference as ionic_reference

MODELS = dict(
    ionic=surface_calcium_activated,
    calcium=surface_calcium_activated_catalog,
    energy=surface_calcium_energy_activated,
)
REFERENCES = dict(ionic=ionic_reference, calcium=calcium_reference, energy=energy_reference)
OLD_IDS = dict(
    ionic="resolved_tissue@9", calcium="resolved_calcium@8", energy="resolved_calcium_energy@2"
)


def initial(family, raw=None):
    spec = parse_spec(fixtures.definition(family) if raw is None else raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    table = control_values(spec, [0.0])
    return spec, model, state, p, type(table)(*(v[0] for v in table))


def perturb_free_calcium(family, spec, state, p, owner=0):
    changed = type(state)(*(v.copy() for v in state))
    if family == "ionic":
        ca, chloride = [spec.model.species_ids.index(k) for k in ("Ca", "Cl")]
        changed.amount_increment[ca, owner] += 1e-4
        changed.amount_increment[chloride, owner] += 2e-4
    else:
        names = [s.id for s in spec.model.stores[owner].species]
        ids = [names.index(k) for k in ("Ca", "B", "CaB")]
        changed.chemical_amount_increment[owner, ids, int(p.er_cytosol[owner])] += 1e-4 * np.array(
            [-1, -1, 1]
        )
    return changed


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
    assert set(p.channel_laws[p.channel_active]) == set(range(40))
    assert len(spec.model.channels) == 47
    view = (
        p
        if family == "ionic"
        else (
            surface_calcium_activated_catalog.ionic_layout(state, p, xp=np)
            if family == "calcium"
            else surface_calcium_activated_catalog.ionic_layout(
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
    assert np.all(value.derivative.channel_gate[:, p.channel_laws == 39] == 0)
    model.check_values(state, spec)
    if arm in ("blocked", "empty"):
        assert not np.any(value.derivative.channel_transferred)
    if padded:
        assert not np.any(value.derivative.channel_gate[:, -1])
        assert not np.any(value.derivative.channel_transferred[:, -1])
    evidence(
        f"calcium-activated-stage-{family}-{arm}-{padded}",
        dict(status="passed", inputs=raw, scope="complete instantaneous stage", **checked),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_old_39_law_models_and_rates_remain_bitwise_identical(family):
    raw = previous.definition(family)
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
    evidence(
        "calcium-activated-old-" + family,
        dict(status="passed", complete_rates_and_fields="bitwise"),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize(
    "fault", ["old_identity", "inner_identity", "law", "route", "step", "invented_gate"]
)
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
        m["channels"][-1]["permeant_ions"][0]["species_id"] = "Ca"
    elif fault == "invented_gate":
        m["channels"][-1]["initial_gate"] = [0.0, 0.0]
    else:
        raw["execution"]["dt"] = 2.5e-6
    with pytest.raises(ConfigError):
        timeline(parse_spec(raw))


def test_instantaneous_dispatch_and_absent_clock_match_scalar_reference():
    codes = np.arange(40)
    voltage = np.linspace(-0.100, 0.040, 40)
    calcium = np.geomspace(1e-8, 1e-3, 40)
    gate = np.broadcast_to(np.array([0.3, 0.7])[:, None], (2, 40)).copy()
    gate[:, 39] = 0.0
    targets, taus = catalog.kinetics(voltage, codes, xp=np)
    opened = catalog.opening(
        gate, codes, voltage=voltage, calcium_free_mM=calcium, temperature_K=298.15, xp=np
    )
    exact((targets[:, :39], taus[:, :39]), old_catalog.kinetics(voltage[:39], codes[:39], xp=np))
    np.testing.assert_array_equal(opened[:39], old_catalog.opening(gate[:, :39], codes[:39], xp=np))
    assert not old_catalog.valid_codes(codes, xp=np)
    assert np.all(targets[:, 39] == 0) and np.all(taus[:, 39] == 0)
    expected = scalar.evaluate(voltage[39], calcium[39], 298.15)["opening"]
    assert abs(opened[39] - expected) < 2e-15
    assert not catalog.gate_active(codes, xp=np)[39]
    evidence(
        "calcium-activated-dispatch",
        dict(
            status="passed",
            opening=float(opened[39]),
            scope="Zero tau denotes absent state, never a relaxation equation",
        ),
    )


def test_sensor_is_required_and_instantaneous_populations_add_no_gate_clock():
    raw = fixtures.definition("ionic", "instant_only")
    renamed = json.loads(json.dumps(raw).replace('"Ca"', '"calcium_alias"'))
    with pytest.raises(ConfigError, match="Ca \\+2 sensor"):
        parse_spec(renamed)
    raw["execution"]["dt"] = 2.5e-6
    spec = parse_spec(raw)
    timeline(spec)
    assert all(ch.initial_gate == () for ch in spec.model.channels)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_current_owner_calcium_controls_only_the_instantaneous_opening(family):
    spec, model, state, p, u = initial(family)
    before = model.readouts(state, u, p, xp=np)
    changed = perturb_free_calcium(family, spec, state, p)
    after = model.readouts(changed, u, p, xp=np)
    assert before.valid and after.valid
    ca = spec.model.species_ids.index("Ca")
    potassium = spec.model.species_ids.index("K")
    old_ca = model.physical_amounts(state, p)[0][ca] / p.volume
    new_ca = model.physical_amounts(changed, p)[0][ca] / p.volume
    checks = []
    for slot in np.flatnonzero(p.channel_laws == 39):
        patch = int(p.channel_membranes[slot])
        owner = int(p.membrane_cell[patch])
        v0, v1 = (float(r.field.rates.membrane_voltage_V[patch]) for r in (before, after))
        np.testing.assert_allclose(v1, v0, atol=3e-15, rtol=3e-13)
        prob0 = scalar.evaluate(v0, old_ca[owner], float(p.temperature))["opening"]
        prob1 = scalar.evaluate(v1, new_ca[owner], float(p.temperature))["opening"]
        flux0 = before.derivative.channel_transferred[potassium, slot]
        flux1 = after.derivative.channel_transferred[potassium, slot]
        assert flux0 != 0
        np.testing.assert_allclose(flux1 / flux0, prob1 / prob0, rtol=2e-10, atol=2e-12)
        if owner == 0:
            assert not np.isclose(prob1, prob0, atol=1e-8, rtol=1e-8)
        else:
            assert old_ca[owner] == new_ca[owner]
        checks.append(
            dict(slot=int(slot), owner=owner, old_probability=prob0, new_probability=prob1)
        )
    compare(family, spec, changed, after.derivative)
    evidence("calcium-activated-current-owner-" + family, dict(status="passed", cases=checks))


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_blocked_or_zero_permeability_instantaneous_slots_stay_zero(family):
    spec, model, state, p, control = initial(family)
    slots = p.channel_laws == 39
    assert np.all(state.channel_gate[:, slots] == 0)
    for fault in ("blocked", "zero_permeability"):
        held = control._replace(channel=control.channel.copy())
        q = p._replace(channel_permeability=p.channel_permeability.copy())
        if fault == "blocked":
            held.channel[slots] = 0.0
        else:
            q.channel_permeability[slots] = 0.0
        value = model.readouts(state, held, q, xp=np)
        assert value.valid
        assert np.all(value.derivative.channel_gate[:, slots] == 0)
        assert np.all(value.derivative.channel_transferred[:, slots] == 0)
        bad = state._replace(channel_gate=state.channel_gate.copy())
        bad.channel_gate[0, np.flatnonzero(slots)[0]] = 0.1
        assert not model.control_domain_valid(bad, held, q, q.active, xp=np)


@pytest.mark.parametrize("family", ["calcium", "energy"])
def test_potassium_route_senses_free_calcium_without_consuming_calcium_or_atp(family):
    spec, model, state, p, control = initial(family)
    slot = int(np.flatnonzero(p.channel_laws == 39)[0])
    patch = int(p.channel_membranes[slot])
    owner, outside = int(p.membrane_cell[patch]), int(p.membrane_outside[patch])
    held = control._replace(channel=control.channel.copy())
    held.channel[slot] = 0.0
    before, after = (model.readouts(state, u, p, xp=np) for u in (control, held))
    flux = before.derivative.channel_transferred[:, slot]
    assert np.count_nonzero(flux) == 1
    assert flux[spec.model.species_ids.index("Ca")] == 0
    assert flux[spec.model.species_ids.index("K")] != 0
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
    evidence("calcium-activated-free-owner-" + family, dict(status="passed", **checked))


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize(
    "fault", ["hidden_species", "pad_control", "pad_law", "unknown_law", "nan_gate", "nonzero_gate"]
)
def test_new_routes_cannot_hide_invalid_state_or_controls(family, fault):
    _, model, state, p, u = initial(family, fixtures.definition(family, "blocked"))
    slot = int(np.flatnonzero(p.channel_laws == 39)[0])
    if fault == "hidden_species":
        state.channel_transferred[0, slot] = 1e-5
    elif fault == "pad_control":
        u.channel[-1] = 0.1
    elif fault == "pad_law":
        p.channel_laws[-1] = 39
    elif fault == "unknown_law":
        p.channel_laws[slot] = 40
    elif fault == "nonzero_gate":
        state.channel_gate[0, slot] = 1e-12
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
    old_spec = parse_spec(previous.definition(family))
    old_type = get_model(old_spec.model).LAYOUT_TYPE
    with pytest.raises(ConfigError, match="state/layout"):
        validate_checkpoint(
            spec, replace(point, layout=old_type(*(getattr(p, k) for k in old_type._fields)))
        )


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
        "calcium-activated-assembly-" + family,
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
    changed = perturb_free_calcium(family, spec, state, p)
    states = model.STATE_TYPE(*(np.stack((a, b)) for a, b in zip(state, changed, strict=True)))
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
    bad.channel_gate[1, 0, np.flatnonzero(p.channel_laws == 39)[0]] = 1.01
    failed, valid = evaluate(bad, controls, p)
    assert np.array_equal(np.asarray(valid), [True, False])
    assert all(np.isnan(v[1]).all() for v in failed)
    exact((v[0] for v in failed), (v[0] for v in got))
    evidence(
        "calcium-activated-compiled-" + family,
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
        "calcium-activated-trajectory",
        report,
        dict(observed=actual, reference=target, signed_error=actual - target),
    )
    write_run(tmp_path / "early", result)
    ratio = assert_states(c, actual, target)
    instantaneous = result.final.layout.channel_laws == 39
    assert np.all(result.observations.channel_gate[:, :, instantaneous] == 0)
    saved = load_snapshot(tmp_path / "early/checkpoint_final")
    assert saved.spec == result.spec
    exact(saved.checkpoint.state, result.final.state)
    exact(saved.checkpoint.layout, result.final.layout)
    assert type(saved.checkpoint.layout) is surface_calcium_energy_activated.LAYOUT_TYPE
    evidence(
        "calcium-activated-trajectory",
        report
        | dict(
            status="passed",
            max_error_over_budget=ratio,
            complete_final_snapshot=True,
            instantaneous_gate_slots_exact_zero=True,
        ),
    )
