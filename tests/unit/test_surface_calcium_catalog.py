"""Expanded shared routes with one owned free cytosol/ER and explicit assembly controls."""

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
from cells.core.errors import NumericalError
from cells.core.runner import branch_checkpoint, run, timeline, validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import Checkpoint
from cells.core.surface_calcium_spec import ionic_spec
from cells.ensemble import ionic
from cells.ensemble.cluster import aggregate
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import surface_calcium_catalog as model
from cells.models import surface_calcium_cav as prior
from cells.models import surface_catalog, surface_kinetic
from cells.models.registry import get_model
from cells.processes import shared_channel_catalog
from tests.unit.test_surface_calcium import assert_owned_assembly_readouts
from tests.unit.test_surface_catalog import evidence as shared_evidence
from tests.unit.test_surface_kinetic import assert_states, exact
from validation.tissue import surface_calcium_catalog_fixtures as fixtures
from validation.tissue import surface_calcium_cav_fixtures as prior_fixtures
from validation.tissue import surface_calcium_reference as reference


def evidence(name, report, arrays=None):
    shared_evidence("owned-calcium-" + name, report, arrays)


def initial(raw=None, time=0.0):
    spec = parse_spec(fixtures.definition() if raw is None else raw)
    state, p = get_model(spec.model).initial_values(spec)
    controls = control_values(spec, [time])
    return spec, state, p, type(controls)(*(v[0] for v in controls))


def compare(spec, state, value, *, time=0.0, levels=None):
    c = reference.bind(spec.to_dict())
    target, _, proof = reference.evaluate(
        c, reference.flatten(c, state._asdict()), time, channel_levels=levels
    )
    ratio = assert_states(
        c,
        reference.flatten(c, value.derivative._asdict()),
        target,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    assert value.valid and abs(value.field.energy_balance_pJ_s) < 1e-10
    assert abs(proof["physical_energy_balance_pJ_s"]) < 1e-10
    return dict(max_error_over_budget=ratio, independent_root=proof)


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
def test_registered_identity_routes_owned_view_and_roundtrip(backend):
    raw = fixtures.definition(backend=backend)
    spec, state, p, _ = initial(raw)
    assert spec == parse_spec(spec.to_dict())
    assert get_model(spec.model) is model and type(p) is model.LAYOUT_TYPE
    assert spec.to_dict()["model"]["id"] == "resolved_calcium@7"
    projected = ionic_spec(spec)
    assert get_model(projected.model) is surface_catalog
    assert projected.to_dict()["model"]["id"] == "resolved_tissue@8"
    assert parse_spec(projected.to_dict()) == projected
    view = model.ionic_layout(state, p, xp=np)
    assert type(view) is surface_kinetic.CATALOG_OWNED_VIEW_TYPE
    assert surface_kinetic.channel_process(view) is shared_channel_catalog
    np.testing.assert_array_equal(view.cytosol_amount, model.cytosol_amount(state, p, xp=np))
    assert len(state) == 34 and state.channel_transferred.shape == (4, 40)
    assert set(p.channel_laws[p.channel_active]) == set(range(35))
    assert (
        ionic.parse_spec(dict(model="ionic_worlds@1", simulation=raw, worlds=2)).simulation == spec
    )
    batch = BatchSpec((WorldSpec(7, spec), WorldSpec(39, spec)), 2, 2048, 2**32)
    assert parse_batch(batch.to_dict()) == batch
    timeline(spec)
    evidence(
        "identity-" + backend, dict(status="passed", inputs=raw, state_fields=list(state._fields))
    )


@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("padded", [False, True])
def test_independent_complete_stage_rates(arm, padded):
    spec, state, p, control = initial(fixtures.definition(arm, padded=padded))
    value = model.readouts(state, control, p, xp=np)
    checked = compare(spec, state, value)
    assert model.control_domain_valid(state, control, p, p.active, xp=np)
    assert model.check_values(state, spec)["max_energy_error"] == 0
    if padded:
        assert not np.any(value.derivative.channel_gate[:, -1])
        assert not np.any(value.derivative.channel_transferred[:, -1])
    evidence(
        f"stage-{arm}-{padded}",
        dict(
            status="passed",
            inputs=spec.to_dict(),
            scope="Instantaneous complete ownership/physics only",
            **checked,
        ),
    )


@pytest.mark.parametrize(
    "fault",
    ["outer", "inner", "old_catalog", "missing_ca", "ca_weight", "owner", "capacity", "step"],
)
def test_reject_mismatched_identities_routes_and_time_step(fault):
    raw = fixtures.definition()
    m, x = raw["model"], raw["execution"]
    if fault in ("outer", "old_catalog"):
        m["id"] = "resolved_calcium@6"
    if fault in ("inner", "old_catalog"):
        m["ionic"]["id"] = "resolved_tissue@7"
    if fault == "missing_ca":
        m["ionic"]["channels"][-2]["permeant_ions"].pop()
    elif fault == "ca_weight":
        m["ionic"]["channels"][-2]["permeant_ions"][-1]["relative_permeability"] = 1.0
    elif fault == "owner":
        m["stores"][1]["cell_id"] = m["stores"][0]["cell_id"]
    elif fault == "capacity":
        x["channel_capacity"] = 38
    elif fault == "step":
        x["dt"] = 2.5e-6
    with pytest.raises(ConfigError):
        timeline(parse_spec(raw))


def test_previous_calcium_catalog_reduces_bitwise():
    raw = prior_fixtures.definition()
    old, state, p, control = initial(raw)
    raw["model"]["id"], raw["model"]["ionic"]["id"] = "resolved_calcium@7", "resolved_tissue@8"
    new, newer, q, held = initial(raw)
    assert get_model(old.model) is prior and get_model(new.model) is model
    exact(state, newer)
    first, second = prior.readouts(state, control, p, xp=np), model.readouts(newer, held, q, xp=np)
    exact(first.derivative, second.derivative)
    exact(jax.tree.leaves(first.field), jax.tree.leaves(second.field))
    evidence(
        "legacy",
        dict(status="passed", complete_state_rates_fields="bitwise", old_identity=prior.MODEL_ID),
    )


@pytest.mark.parametrize("kind", ["binding", "er_transfer", "ip3_binding"])
def test_free_ion_feedback_preserves_plasma_ownership(kind):
    spec, state, p, control = initial()
    changed = model.STATE_TYPE(*(v.copy() for v in state))
    names = [s.id for s in spec.model.stores[0].species]
    cy, er = int(p.er_cytosol[0]), int(p.er_er[0])
    if kind == "binding":
        indices = [names.index(k) for k in ("Ca", "B", "CaB")]
        changed.chemical_amount_increment[0, indices, cy] += 1e-4 * np.array([-1, -1, 1])
    elif kind == "er_transfer":
        changed.chemical_amount_increment[0, names.index("Ca"), [cy, er]] += 1e-4 * np.array(
            [-1, 1]
        )
    else:
        indices = [names.index(k) for k in ("IP3", "IP3_buffer", "IP3_bound")]
        changed.chemical_amount_increment[0, indices, cy] += (
            p.er_initial_amount[0, indices[0], cy] / 4 * np.array([-1, -1, 1])
        )
    assert model.domain_valid(changed, p, p.active, xp=np)
    exact(
        (model.ensemble_voltage(state, p, spec, 0),), (model.ensemble_voltage(changed, p, spec, 0),)
    )
    before, after = (model.readouts(y, control, p, xp=np) for y in (state, changed))
    if kind == "ip3_binding":
        assert (
            after.derivative.er_release_transferred[0]
            != before.derivative.er_release_transferred[0]
        )
    else:
        # Fixture CatLeak2 belongs to cell0 and reads its current free Ca.
        ca = spec.model.species_ids.index("Ca")
        slot = int(np.flatnonzero(p.channel_laws == 34)[0])
        assert int(p.membrane_cell[p.channel_membranes[slot]]) == 0
        assert (
            after.derivative.channel_transferred[ca, slot]
            != before.derivative.channel_transferred[ca, slot]
        )
        assert not np.any(after.derivative.channel_transferred[ca, p.channel_laws == 33])
    checked = compare(spec, changed, after)
    duplicate = changed._replace(amount_increment=changed.amount_increment.copy())
    duplicate.amount_increment[int(p.plasma_ca), 0] += 1e-4
    assert not model.domain_valid(duplicate, p, p.active, xp=np)
    evidence(
        "free-owner-" + kind,
        dict(status="passed", unchanged_plasma_voltage=True, duplicate_rejected=True, **checked),
    )


def test_mixed_cation_transport_updates_one_chemical_owner_once():
    spec, state, p, control = initial()
    slot = int(np.flatnonzero(p.channel_laws == 34)[0])
    patch = int(p.channel_membranes[slot])
    owner, outside = int(p.membrane_cell[patch]), int(p.membrane_outside[patch])
    before = model.readouts(state, control, p, xp=np)
    levels = control.channel.copy()
    levels[slot] = 0
    after = model.readouts(state, control._replace(channel=levels), p, xp=np)
    flux = before.derivative.channel_transferred[:, slot]
    assert np.count_nonzero(flux) == 3
    expected = np.zeros_like(state.chemical_amount_increment)
    expected[owner, p.ionic_species, int(p.er_cytosol[owner])] = -flux
    np.testing.assert_allclose(
        before.derivative.chemical_amount_increment - after.derivative.chemical_amount_increment,
        expected,
        atol=3e-14,
        rtol=3e-10,
    )
    for key, index, sign in (
        ("amount_increment", owner, -1),
        ("extracellular_amount_increment", outside, 1),
    ):
        expected = np.zeros_like(getattr(state, key))
        expected[:, index] = sign * flux
        np.testing.assert_allclose(
            getattr(before.derivative, key) - getattr(after.derivative, key),
            expected,
            atol=3e-14,
            rtol=3e-10,
        )
    exact(before.derivative.channel_gate, after.derivative.channel_gate)


@pytest.mark.parametrize("stopped_owner", [0, 1])
def test_assembly_modulates_all_owned_routes_and_preserves_gate_clocks(stopped_owner):
    spec = parse_assembly(fixtures.assembly_definition())
    _, state, p, control = initial(spec.ionic.to_dict())
    owners = channel_owners(spec)
    levels = np.ones(2)
    levels[stopped_owner] = 0
    held = modulate(control, levels, owners)
    before, after = (model.readouts(state, v, p, xp=np) for v in (control, held))
    assert not np.any(after.derivative.channel_transferred[:, owners == stopped_owner])
    exact(
        (after.derivative.channel_transferred[:, owners != stopped_owner],),
        (before.derivative.channel_transferred[:, owners != stopped_owner],),
    )
    exact(after.derivative.channel_gate, before.derivative.channel_gate)
    exact(
        after.derivative.calcium_channel_transferred, before.derivative.calcium_channel_transferred
    )
    checked = compare(spec.ionic, state, after, levels=levels)
    evidence(
        f"assembly-owner-{stopped_owner}",
        dict(status="passed", owner_indices=owners.tolist(), shared_routes_only=True, **checked),
    )


@pytest.mark.parametrize(
    "fault", ["pad_control", "nan_control", "blocked_gate", "absent_calcium_route", "law"]
)
def test_invalid_owned_domains_remain_visible_when_blocked(fault):
    _, state, p, control = initial(fixtures.definition("blocked"))
    if fault in ("pad_control", "nan_control"):
        levels = control.channel.copy()
        levels[-1 if fault == "pad_control" else -2] = 0.1 if fault == "pad_control" else np.nan
        control = control._replace(channel=levels)
    elif fault == "blocked_gate":
        state.channel_gate[1, -2] = 1.01
    elif fault == "absent_calcium_route":
        state.channel_transferred[int(p.plasma_ca), p.channel_laws == 33] = 1e-6
    else:
        p.channel_laws[-2] = 35
    assert not model.control_domain_valid(state, control, p, p.active, xp=np)


@pytest.mark.parametrize("name", model.STATE_TYPE._fields)
def test_corrupt_complete_state_is_rejected(name):
    spec, state, _, _ = initial()
    wrong = getattr(state, name).copy()
    wrong.flat[0] += 1.1 if name.endswith("gate") else (1e-16 if name.endswith("_C") else 0.01)
    with pytest.raises(NumericalError):
        model.check_values(state._replace(**{name: wrong}), spec)


def test_species_route_heat_must_not_decrease():
    spec, state, _, _ = initial()
    history = model.STATE_TYPE(*(np.stack((v, v)) for v in state))
    history.channel_dissipated_energy_pJ[0, 0, 38] = 1e-11
    history.channel_dissipated_energy_pJ[1, 1, 38] = 1e-11
    for i in (0, 1):
        model.check_values(model.STATE_TYPE(*(v[i] for v in history)), spec)
    with pytest.raises(NumericalError, match="dissipation decreased"):
        model.check_values(history, spec)


def test_complete_snapshot_and_branch_identity(tmp_path):
    spec, state, p, _ = initial(fixtures.compact_probe())
    checkpoint = Checkpoint(state, p, 0.0, 0, event_index(spec, 0.0))
    write_snapshot(tmp_path / "initial", spec, checkpoint)
    saved = load_snapshot(tmp_path / "initial")
    assert saved.spec == spec and type(saved.checkpoint.layout) is model.LAYOUT_TYPE
    exact(saved.checkpoint.state, state)
    exact(saved.checkpoint.layout, p)
    with pytest.raises(ConfigError, match="state/layout"):
        validate_checkpoint(spec, replace(checkpoint, layout=prior.LAYOUT_TYPE(*p)))
    raw = spec.to_dict()
    raw["experiment"]["channel_controls"][-1]["schedule"].append(
        dict(time=20 * spec.execution.dt, availability=0.0)
    )
    changed = parse_spec(raw)
    exact(branch_checkpoint(spec, checkpoint, changed).state, state)
    raw["model"]["ionic"]["channels"][-1]["abundance"] *= 2
    with pytest.raises(ConfigError, match="model or execution"):
        branch_checkpoint(spec, checkpoint, parse_spec(raw))
    evidence(
        "snapshot",
        dict(
            status="passed",
            state_fields=list(state._fields),
            complete_layout=True,
            scope="Initial host snapshot; integrated replay separate",
        ),
    )


def test_initial_assembly_report_aggregation_and_complete_checkpoint(tmp_path):
    spec = parse_assembly(fixtures.assembly_definition())
    state = assembly.initial_state(spec)
    report = assembly.summary(spec, state) | dict(
        arm="catalog", wall_start=0.0, wall_end=1.0, execute_seconds=0.0
    )
    assert_owned_assembly_readouts(spec, state, report)
    assert report["physical_model"] == "resolved_calcium@7"
    assert report["channel_transfer_axes"] == ["world", "species", "channel"]
    assert report["channel_species_ids"] == list(spec.ionic.model.species_ids)
    matrix = np.array(report["channel_relative_permeability"])
    assert matrix.shape == (4, 39) and matrix[3, -2] == 0 and matrix[3, -1] == 1
    combined = aggregate([report, report])["catalog"]
    assert combined["worlds"] == 2 * spec.pool.worlds
    for key in (
        "ip3",
        "calcium",
        "channel_transfer_axes",
        "channel_species_ids",
        "channel_relative_permeability",
    ):
        missing = deepcopy(report)
        missing.pop(key)
        with pytest.raises(ValueError):
            aggregate([report, missing])
    write_checkpoint(tmp_path / "assembly", spec, state, backend="cpu")
    restored, newer, _ = load_checkpoint(tmp_path / "assembly", backend="cpu")
    assert restored == spec
    exact(flatten(newer).values(), flatten(state).values())
    evidence(
        "assembly-host",
        dict(
            status="passed",
            inputs=spec.to_dict(),
            report=report,
            scope="Initial report/checkpoint and owner controls; no stochastic event trajectory",
        ),
    )


def test_compiled_owned_stage_guard_and_assembly_controls():
    spec, state, p, control = initial()
    evaluate = jax.jit(
        lambda y, u, q: (
            model.rhs(y, u, q, q.active),
            model.control_domain_valid(y, u, q, q.active),
        )
    )
    got, valid = evaluate(state, control, p)
    assert valid
    c = reference.bind(spec.to_dict())
    target, _, proof = reference.evaluate(c, reference.initial(c), 0)
    ratio = assert_states(
        c, reference.flatten(c, got._asdict()), target, atol=3e-12, charge_atol=3e-23, rtol=3e-10
    )
    owners = channel_owners(parse_assembly(fixtures.assembly_definition()))
    levels = np.array([0.0, 1.0])
    controlled, valid = evaluate(state, modulate(control, levels, owners), p)
    assert valid
    target, _, _ = reference.evaluate(c, reference.initial(c), 0, channel_levels=levels)
    controlled_ratio = assert_states(
        c,
        reference.flatten(c, controlled._asdict()),
        target,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    invalid = control.channel.copy()
    invalid[-1] = 0.1
    failed, valid = evaluate(state, control._replace(channel=invalid), p)
    assert not valid and all(np.isnan(v).all() for v in failed)
    evidence(
        "compiled-stage",
        dict(
            status="passed",
            inputs=spec.to_dict(),
            max_error_over_budget=max(ratio, controlled_ratio),
            independent_root=proof,
            invalid_padding_rejected=True,
        ),
    )


def test_compiled_early_trajectory_and_full_final_snapshot(tmp_path):
    raw = fixtures.compact_probe()
    value = run(parse_spec(raw))
    c = reference.bind(raw)
    expected = reference.integrate(raw, rtol=1e-13, state_atol=1e-16, charge_atol=5e-32)
    actual = reference.flatten(c, vars(value.observations))
    target = np.array(expected["state"])
    report = dict(
        status="captured",
        inputs=raw,
        scope="50-us coupled feedback only; no slow-gate/ER settling or long-time qualification",
        diagnostics=value.diagnostics,
        independent_reference=expected,
    )
    evidence(
        "early-trajectory",
        report,
        dict(observed=actual, reference=target, signed_error=actual - target),
    )
    write_run(tmp_path / "early", value)
    ratio = assert_states(c, actual, target)
    saved = load_snapshot(tmp_path / "early/checkpoint_final")
    exact(saved.checkpoint.state, value.final.state)
    exact(saved.checkpoint.layout, value.final.layout)
    assert saved.spec == value.spec and type(saved.checkpoint.layout) is model.LAYOUT_TYPE
    evidence(
        "early-trajectory",
        report | dict(status="passed", max_error_over_budget=ratio, complete_final_snapshot=True),
    )
