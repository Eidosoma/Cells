"""Compiled full-state checks for prescribed repair with the 53-law catalog."""

import jax
import numpy as np

from cells.core.runner import run
from cells.core.schedule import control_values
from cells.core.specs import parse_spec
from cells.io import load_snapshot, write_run
from cells.models import surface_repair_morris_lecar as model
from cells.processes import morris_lecar_catalog as catalog
from tests.unit.test_morris_lecar_catalog import perturb_free_calcium
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_kinetic import assert_states, exact
from validation.tissue import morris_lecar_repair_fixtures as fixtures
from validation.tissue import morris_lecar_repair_reference as reference


def test_compiled_two_world_repair_rates_and_absent_state_rejection():
    raw = fixtures.definition()
    spec = parse_spec(raw)
    state, p = model.initial_values(spec)
    table = control_values(spec, [0.0])
    u = type(table)(*(v[0] for v in table))
    changed = perturb_free_calcium("calcium", spec, state, p)
    changed.channel_gate[0, p.channel_laws == 40] = 0.51
    changed.damage[0] = changed.damage_opened[0] = 0.15
    states = model.STATE_TYPE(*(np.stack((a, b)) for a, b in zip(state, changed, strict=True)))
    controls = type(u)(*(np.stack((v, v)) for v in u))
    evaluate = jax.jit(
        jax.vmap(
            lambda y, ctl, q: (
                model.rhs(y, ctl, q, q.active),
                model.control_domain_valid(y, ctl, q, q.active),
            ),
            in_axes=(0, 0, None),
        )
    )
    rates, valid = evaluate(states, controls, p)
    assert np.all(valid)
    c = reference.bind(raw)
    checked = []
    for i in (0, 1):
        y = model.STATE_TYPE(*(v[i] for v in states))
        derivative = model.STATE_TYPE(*(v[i] for v in rates))
        target, _, proof = reference.evaluate(c, reference.flatten(c, y._asdict()), 0.0)
        ratio = assert_states(
            c,
            reference.flatten(c, derivative._asdict()),
            target,
            atol=3e-12,
            charge_atol=3e-23,
            rtol=3e-10,
        )
        assert abs(proof["physical_energy_balance_pJ_s"]) < 1e-9
        checked.append(dict(max_error_over_budget=ratio, independent_stage=proof))
    assert np.any(np.asarray(rates.injury_transferred[1]))
    bad = states._replace(channel_gate=states.channel_gate.copy())
    bad.channel_gate[1, 0, np.flatnonzero(p.channel_laws == 46)[0]] = 0.25
    failed, valid = evaluate(bad, controls, p)
    assert np.array_equal(np.asarray(valid), [True, False])
    assert all(np.isnan(v[1]).all() for v in failed)
    exact((v[0] for v in failed), (v[0] for v in rates))
    evidence(
        "morris-lecar-repair-compiled-stage",
        dict(
            status="passed",
            inputs=raw,
            world_checks=checked,
            invalid_world_isolated=True,
            scope="Two manufactured stages with changed free calcium, m and damage",
        ),
    )


def test_compiled_prescribed_repair_trajectory_and_complete_final_snapshot(tmp_path):
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
        scope=(
            "50-us full39 early coupling; prescribed injury/resealing and "
            "dynamic/instantaneous channel controls"
        ),
        independent_reference={
            k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in expected.items()
        },
    )
    evidence(
        "morris-lecar-repair-trajectory",
        report,
        dict(observed=actual, reference=target, signed_error=actual - target),
    )
    ratio = assert_states(c, actual, target)
    assert np.max(result.observations.damage) > 0.01
    assert np.max(np.abs(result.observations.injury_transferred)) > 0
    absent = ~(
        catalog.gate_active(result.final.layout.channel_laws, xp=np)
        & result.final.layout.channel_active
    )
    assert np.all(result.observations.channel_gate[:, absent] == 0)
    write_run(tmp_path / "coupled", result)
    saved = load_snapshot(tmp_path / "coupled/checkpoint_final")
    assert saved.spec == result.spec and type(saved.checkpoint.layout) is model.LAYOUT_TYPE
    exact(saved.checkpoint.state, result.final.state)
    exact(saved.checkpoint.layout, result.final.layout)
    evidence(
        "morris-lecar-repair-trajectory",
        report
        | dict(
            status="passed",
            max_error_over_budget=ratio,
            complete_final_snapshot=True,
            absent_gate_slots_exact_zero=True,
        ),
    )
