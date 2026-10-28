"""Shared catalog integration, with stage evidence separate from settling claims."""

import json
import os
from dataclasses import replace
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.core.batch import BatchSpec, WorldSpec, parse_batch
from cells.core.runner import branch_checkpoint, run, timeline, validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import Checkpoint
from cells.ensemble import ionic
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import surface_catalog as model
from cells.models import surface_cav as prior
from cells.models.registry import get_model
from cells.processes import cav_channels, leak_channels, potassium_catalog, sodium_catalog
from cells.processes import shared_channel_catalog as channels
from tests.unit.test_surface_kinetic import assert_states, exact
from validation.tissue import surface_catalog_fixtures as fixtures
from validation.tissue import surface_kinetic_reference as reference


def evidence(name, value, arrays=None):
    destination = os.environ.get("CELLS_COMPONENT_EVIDENCE")
    if destination:
        root = Path(destination) / "cpu"
        root.mkdir(parents=True, exist_ok=True)
        (root / ("shared-catalog-" + name + ".json")).write_text(
            json.dumps(value, indent=2, allow_nan=False) + "\n"
        )
        if arrays is not None:
            np.savez(root / ("shared-catalog-" + name + ".npz"), **arrays)


def initial(raw=None, time=0.0):
    spec = parse_spec(fixtures.definition() if raw is None else raw)
    state, layout = get_model(spec.model).initial_values(spec)
    controls = control_values(spec, [time])
    return spec, state, layout, type(controls)(*(v[0] for v in controls))


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
def test_identity_roundtrip_routes_and_ensemble_registration(backend):
    raw = fixtures.definition(backend=backend)
    spec, state, p, _ = initial(raw)
    assert get_model(spec.model) is model and type(p) is model.LAYOUT_TYPE
    assert spec == parse_spec(spec.to_dict())
    assert spec.to_dict()["model"]["id"] == "resolved_tissue@8"
    assert len(state) == 19 and state.channel_gate.shape == (2, 40)
    assert state.channel_transferred.shape == state.channel_dissipated_energy_pJ.shape == (4, 40)
    assert set(p.channel_laws[p.channel_active]) == set(range(35))
    assert p.channel_laws[-1] == 0 and not p.channel_active[-1]
    assert (
        ionic.parse_spec(dict(model="ionic_worlds@1", simulation=raw, worlds=2)).simulation == spec
    )
    batch = BatchSpec((WorldSpec(11, spec), WorldSpec(71, spec)), 2, 2048, 2**32)
    assert parse_batch(batch.to_dict()) == batch
    timeline(spec)
    evidence(
        "identity-" + backend, dict(status="passed", inputs=raw, state_fields=list(state._fields))
    )


@pytest.mark.parametrize(
    "fault",
    ["old_identity", "law", "valence", "ratio", "zero_ca", "order", "owner", "capacity", "step"],
)
def test_declarations_reject_incompatible_catalogs(fault):
    raw = fixtures.definition()
    m, x = raw["model"], raw["execution"]
    if fault == "old_identity":
        m["id"] = "resolved_tissue@7"
    elif fault == "law":
        m["channels"][-1]["kinetic_law"] = "invented_leak@1"
    elif fault == "valence":
        next(s for s in m["species"] if s["id"] == "Cl")["valence"] = 1
    elif fault == "ratio":
        m["channels"][-1]["permeant_ions"][0]["relative_permeability"] = 0.5
    elif fault == "zero_ca":
        m["channels"][-2]["permeant_ions"].pop()
    elif fault == "order":
        m["channels"][-1]["permeant_ions"].reverse()
    elif fault == "owner":
        m["channels"][-1]["membrane_id"] = "nonexistent"
    elif fault == "capacity":
        x["channel_capacity"] = 38
    else:
        x["dt"] = 2.5e-6
    with pytest.raises(ConfigError):
        timeline(parse_spec(raw))


def test_old_catalog_state_rates_and_fields_are_bitwise_unchanged():
    raw = fixtures.legacy_definition()
    old, state, p, control = initial(raw)
    raw["model"]["id"] = "resolved_tissue@8"
    new, newer, q, held = initial(raw)
    assert get_model(old.model) is prior and get_model(new.model) is model
    exact(state, newer)
    first, second = prior.readouts(state, control, p, xp=np), model.readouts(newer, held, q, xp=np)
    exact(first.derivative, second.derivative)
    exact(jax.tree.leaves(first.field), jax.tree.leaves(second.field))
    voltage = np.linspace(-0.12, 0.06, 61)[:, None] * np.ones((1, 18))
    codes = np.arange(18, dtype=np.int64)
    exact(channels.kinetics(voltage, codes, xp=np), cav_channels.kinetics(voltage, codes, xp=np))
    gates = np.stack((np.full_like(voltage, 0.17), np.full_like(voltage, 0.81)), axis=-2)
    np.testing.assert_array_equal(
        channels.opening(gates, codes, xp=np), cav_channels.opening(gates, codes, xp=np)
    )
    evidence(
        "legacy",
        dict(status="passed", scope="Old 18 laws and complete initial stage", comparison="bitwise"),
    )


def test_catalog_dispatch_supports_mixed_population_world_axes():
    codes = np.arange(35, dtype=np.int64)
    voltage = np.linspace(-0.12, 0.06, 6)[:, None] * np.ones((1, 35))
    gates = np.stack((np.full_like(voltage, 0.17), np.full_like(voltage, 0.81)), axis=-2)
    target, tau = channels.kinetics(voltage, codes, xp=np)
    opened = channels.opening(gates, codes, xp=np)
    for start, end, process in (
        (0, 18, cav_channels),
        (18, 24, sodium_catalog),
        (24, 32, potassium_catalog),
        (32, 35, leak_channels),
    ):
        wanted = process.kinetics(voltage[:, start:end], codes[start:end], xp=np)
        exact((target[..., start:end], tau[..., start:end]), wanted)
        np.testing.assert_array_equal(
            opened[..., start:end], process.opening(gates[..., start:end], codes[start:end], xp=np)
        )
    assert channels.kinetics(np.empty((3, 0)), np.empty(0, np.int64), xp=np)[0].shape == (3, 2, 0)
    for wrong in (np.array([-1]), np.array([35]), np.array([0.0]), np.array([True]), np.array(0)):
        assert not channels.valid_codes(wrong, xp=np)
    with pytest.raises(ValueError):
        channels.kinetics(np.zeros(35), np.array(0), xp=np)
    with pytest.raises(ValueError):
        channels.opening(np.zeros((35, 2)), codes, xp=np)


@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("padded", [False, True])
def test_complete_stages_match_independent_reference(arm, padded):
    raw = fixtures.definition(arm, padded=padded)
    spec, state, p, control = initial(raw)
    actual = model.readouts(state, control, p, xp=np)
    c = reference.bind(raw)
    target, _, proof = reference.evaluate(c, reference.initial(c), 0.0)
    ratio = assert_states(
        c,
        reference.flatten(c, actual.derivative._asdict()),
        target,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    assert actual.valid and model.control_domain_valid(state, control, p, p.active, xp=np)
    assert abs(actual.field.energy_balance_pJ_s) < 1e-10
    assert model.check_values(state, spec)["max_energy_balance_error_pJ"] == 0
    if padded:
        assert not np.any(actual.derivative.channel_gate[:, -1])
        assert not np.any(actual.derivative.channel_transferred[:, -1])
    evidence(
        f"stage-{arm}-{padded}",
        dict(
            status="passed",
            inputs=raw,
            scope="Instantaneous full tissue wiring",
            max_error_over_budget=ratio,
            independent_root=proof,
        ),
    )


def test_blocking_keeps_clocks_and_zero_calcium_route():
    _, state, p, control = initial()
    opened = model.readouts(state, control, p, xp=np)
    blocked = control._replace(channel=np.zeros_like(control.channel))
    stopped = model.readouts(state, blocked, p, xp=np)
    assert opened.valid and stopped.valid
    exact((stopped.derivative.channel_gate,), (opened.derivative.channel_gate,))
    assert np.any(stopped.derivative.channel_gate[:, p.channel_laws == 32])
    assert not np.any(stopped.derivative.channel_transferred)
    assert not np.any(stopped.derivative.channel_dissipated_energy_pJ)
    ca = 3
    assert not np.any(opened.derivative.channel_transferred[ca, p.channel_laws == 33])
    assert np.any(opened.derivative.channel_transferred[ca, p.channel_laws == 34])
    # Inactive padding is distinct from a real Kv1.5 population at shared code0.
    assert np.any(opened.derivative.channel_gate[:, p.channel_active & (p.channel_laws == 0)])
    assert not np.any(opened.derivative.channel_gate[:, ~p.channel_active])


@pytest.mark.parametrize("fault", ["nan", "negative", "high", "pad", "gate", "law", "inactive_law"])
def test_invalid_controls_or_gates_do_not_hide_behind_blocking(fault):
    _, state, p, control = initial(fixtures.definition("blocked"))
    levels = control.channel.copy()
    if fault in ("nan", "negative", "high", "pad"):
        levels[-1 if fault == "pad" else -2] = dict(nan=np.nan, negative=-0.01, high=1.01, pad=0.1)[
            fault
        ]
        control = control._replace(channel=levels)
    elif fault == "gate":
        gates = state.channel_gate.copy()
        gates[1, -2] = 1.01
        state = state._replace(channel_gate=gates)
    else:
        laws = p.channel_laws.copy()
        laws[-1 if fault == "inactive_law" else -2] = 32 if fault == "inactive_law" else 35
        p = p._replace(channel_laws=laws)
    assert not model.control_domain_valid(state, control, p, p.active, xp=np)


def test_control_clock_union_and_empty_populations():
    raw = fixtures.definition("release")
    spec = parse_spec(raw)
    events = sorted(
        {v["time"] for g in raw["experiment"]["channel_controls"] for v in g["schedule"]}
    )
    assert set(events) <= set(timeline(spec))
    times = sorted({*events, *(np.nextafter(t, 0) for t in events if t > 0)})
    table = control_values(spec, times)
    groups = {g["channel_id"]: g["schedule"] for g in raw["experiment"]["channel_controls"]}
    for j, ch in enumerate(spec.model.channels):
        wanted = [
            next(v["availability"] for v in reversed(groups[ch.id]) if v["time"] <= t)
            for t in times
        ]
        np.testing.assert_array_equal(table.channel[:, j], wanted)
    assert not np.any(table.channel[:, -1])
    raw["model"]["channels"] = []
    raw["experiment"]["channel_controls"] = []
    raw["execution"]["channel_capacity"] = 0
    empty, state, p, control = initial(raw)
    assert model.readouts(state, control, p, xp=np).valid
    assert state.channel_gate.shape == (2, 0) and state.channel_transferred.shape == (4, 0)
    assert parse_spec(empty.to_dict()) == empty


def test_complete_initial_checkpoint_and_model_branch_protection(tmp_path):
    spec, state, p, _ = initial(fixtures.compact_probe())
    checkpoint = Checkpoint(state, p, 0.0, 0, event_index(spec, 0.0))
    write_snapshot(tmp_path / "initial", spec, checkpoint)
    restored = load_snapshot(tmp_path / "initial")
    assert restored.spec == spec and type(restored.checkpoint.layout) is model.LAYOUT_TYPE
    exact(state, restored.checkpoint.state)
    exact(p, restored.checkpoint.layout)
    changed = spec.to_dict()
    changed["experiment"]["channel_controls"][-1]["schedule"].append(
        dict(time=25e-6, availability=0.0)
    )
    branch = branch_checkpoint(spec, checkpoint, parse_spec(changed))
    exact(branch.state, state)
    wrong_layout = prior.LAYOUT_TYPE(*p)
    with pytest.raises(ConfigError, match="state/layout types"):
        validate_checkpoint(spec, replace(checkpoint, layout=wrong_layout))
    laws = p.channel_laws.copy()
    laws[-1] = 33
    with pytest.raises(ConfigError, match="layout channel_laws"):
        validate_checkpoint(spec, replace(checkpoint, layout=p._replace(channel_laws=laws)))
    changed["model"]["channels"][-1]["abundance"] *= 2
    with pytest.raises(ConfigError, match="model or execution"):
        branch_checkpoint(spec, checkpoint, parse_spec(changed))
    evidence(
        "initial-checkpoint",
        dict(
            status="passed",
            state_fields=list(state._fields),
            complete_layout=True,
            scope="Host serialization and branch guards; integrated replay separate",
        ),
    )


def test_compiled_mixed_stage_and_strict_domain():
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
    wrong = control.channel.copy()
    wrong[-2] = np.nan
    rejected, valid = evaluate(state, control._replace(channel=wrong), p)
    assert not valid and all(np.isnan(v).all() for v in rejected)
    evidence(
        "compiled-stage",
        dict(
            status="passed",
            backend="cpu",
            inputs=spec.to_dict(),
            max_error_over_budget=ratio,
            independent_root=proof,
            invalid_control_rejected=True,
        ),
    )


def test_compiled_early_trajectory_and_complete_snapshot(tmp_path):
    raw = fixtures.compact_probe()
    value = run(parse_spec(raw))
    c = reference.bind(raw)
    expected = reference.integrate(raw, rtol=1e-13, state_atol=1e-16, charge_atol=5e-32)
    observed = reference.flatten(c, vars(value.observations))
    target = np.asarray(expected["state"])
    report = dict(
        status="captured",
        inputs=raw,
        scope="50-us early trajectory only; no slow-gate settling or long-time qualification",
        diagnostics=value.diagnostics,
        independent_reference=expected,
    )
    evidence(
        "early-trajectory",
        report,
        dict(observed=observed, reference=target, signed_error=observed - target),
    )
    write_run(tmp_path / "early", value)
    ratio = assert_states(c, observed, target)
    loaded = load_snapshot(tmp_path / "early/checkpoint_final")
    exact(loaded.checkpoint.state, value.final.state)
    exact(loaded.checkpoint.layout, value.final.layout)
    assert loaded.spec == value.spec and type(loaded.checkpoint.layout) is model.LAYOUT_TYPE
    evidence(
        "early-trajectory",
        report | dict(status="passed", max_error_over_budget=ratio, complete_final_snapshot=True),
    )
