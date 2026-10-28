"""Finite-energy host/stage contracts; full trajectories belong to qualification."""

import json
import os
from pathlib import Path

import numpy as np
import pytest

from cells.core.errors import NumericalError
from cells.core.schedule import control_values
from cells.core.specs import parse_spec
from cells.core.surface_energy_spec import initial_ionic_spec
from cells.models import surface_cav as prior
from cells.models import surface_energy as model
from validation.chemistry import finite_energy_reference as chemistry
from validation.tissue import surface_energy_fixtures as fixtures
from validation.tissue import surface_energy_reference as reference

EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")
BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")


def definition(arm="coupled", **kwargs):
    return fixtures.definition(arm, backend=BACKEND, **kwargs)


def evidence(name, report, arrays=None):
    if EVIDENCE:
        root = Path(EVIDENCE) / BACKEND
        root.mkdir(parents=True, exist_ok=True)
        if arrays is not None:
            np.savez_compressed(root / ("resolved-energy-" + name + ".npz"), **arrays)
        (root / ("resolved-energy-" + name + ".json")).write_text(
            json.dumps(
                report,
                indent=2,
                allow_nan=False,
                default=lambda v: v.tolist(),
            )
            + "\n"
        )


def initial(raw=None, time=0.0):
    spec = parse_spec(definition() if raw is None else raw)
    state, p = model.initial_values(spec)
    table = control_values(spec, [time])
    return spec, state, p, type(table)(*(v[0] for v in table))


def normalized(c, values):
    return reference.flatten(
        c,
        {
            key: np.asarray(values[key])[tuple(slice(0, n) for n in shape)]
            for key, shape in c["shapes"].items()
        },
    )


@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("padded", [False, True])
def test_complete_stage_against_independent_finite_energy_reference(arm, padded):
    raw = definition(arm, padded=padded)
    spec, state, p, control = initial(raw)
    actual = model.readouts(state, control, p, xp=np)
    name = f"stage-{arm}-{'padded' if padded else 'compact'}"
    captured = {"actual_" + key: np.asarray(v) for key, v in actual.derivative._asdict().items()}
    evidence(name, dict(status="actual_captured", inputs=raw), captured)
    c = reference.bind(raw)
    expected, phi, proof = reference.evaluate(c, reference.initial(c), 0.0)
    values = normalized(c, actual.derivative._asdict())
    observed_phi = np.r_[
        actual.field.potential_V[: p.active.size][p.active],
        actual.field.potential_V[p.active.size :][p.outside_active],
    ]
    evidence(
        name,
        dict(status="captured", inputs=raw, independent=proof),
        captured
        | dict(
            actual=values,
            expected=expected,
            actual_phi=observed_phi,
            expected_phi=phi,
        ),
    )
    atol = reference.flatten(
        c,
        {
            key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
            for key, shape in c["shapes"].items()
        },
    )
    score = float(np.max(np.abs(values - expected) / (atol + 3e-10 * np.abs(expected)), initial=0))
    assert score <= 1.0
    np.testing.assert_allclose(observed_phi, phi, rtol=3e-10, atol=3e-13)
    assert actual.valid and model.domain_valid(state, p, p.active, xp=np)
    assert abs(actual.field.energy_balance_pJ_s) < 2e-8
    assert abs(proof["physical_energy_balance_pJ_s"]) < 2e-8
    assert np.min(actual.derivative.regeneration_dissipated_energy_pJ, initial=0) >= 0
    model.check_values(state, spec)
    evidence(
        name, dict(status="passed", inputs=raw, max_error_over_budget=score, independent=proof)
    )


def test_initial_maintained_pool_rates_are_the_exact_initial_limit():
    spec, state, p, control = initial()
    old_spec = initial_ionic_spec(spec)
    old_state, old_p = prior.initial_values(old_spec)
    old_table = control_values(old_spec, [0.0])
    old = prior.readouts(old_state, type(old_table)(*(v[0] for v in old_table)), old_p, xp=np)
    actual = model.readouts(state, control, p, xp=np)
    for a, b in zip(model.prior_state(actual.derivative), old.derivative, strict=True):
        np.testing.assert_array_equal(a, b)


def test_finite_current_pool_changes_actual_pumping_and_internal_transfer_power():
    _, state, p, control = initial()
    increment = state.energy_amount_increment_fmol.copy()
    increment[:, 0] = [-0.0005, 0.0005, 0.0005]
    changed = state._replace(energy_amount_increment_fmol=increment)
    actual = model.readouts(changed, control, p, xp=np)
    first = model.readouts(state, control, p, xp=np)
    assert actual.valid
    assert not np.array_equal(actual.derivative.pump_cycles, first.derivative.pump_cycles)
    drive = actual.energy.hydrolysis_free_energy_J_mol[p.membrane_cell]
    np.testing.assert_allclose(
        actual.derivative.metabolic_work_pJ,
        -1e-3 * actual.derivative.pump_cycles * drive,
        atol=3e-12,
        rtol=3e-10,
    )
    c = reference.bind(definition())
    d = reference.unpack(c, reference.initial(c))
    d["energy_amount_increment_fmol"][:, 0] = increment[:, 0]
    expected, _, proof = reference.evaluate(c, reference.flatten(c, d), 0.0)
    np.testing.assert_allclose(
        normalized(c, actual.derivative._asdict()), expected, atol=3e-12, rtol=3e-10
    )
    assert abs(proof["physical_energy_balance_pJ_s"]) < 2e-8


def test_two_pump_patches_consume_one_shared_pool_once():
    _, state, p, control = initial(definition("two_patches", padded=True))
    value = model.readouts(state, control, p, xp=np)
    total = float(
        np.sum(value.derivative.pump_cycles) - np.sum(value.derivative.regeneration_cycles_fmol)
    )
    np.testing.assert_allclose(
        value.derivative.energy_amount_increment_fmol[:, 0],
        [-total, total, total],
        atol=3e-12,
        rtol=3e-10,
    )
    assert p.membrane_cell[0] == p.membrane_cell[1] == 0
    assert value.derivative.pump_cycles[0] != value.derivative.pump_cycles[1]
    assert not np.any(value.derivative.energy_amount_increment_fmol[:, ~p.active])


def test_regeneration_has_no_instantaneous_ionic_or_charge_shortcut():
    _, state, p, control = initial()
    first = model.readouts(state, control, p, xp=np)
    off = model.readouts(
        state, control._replace(regeneration=np.zeros_like(control.regeneration)), p, xp=np
    )
    for a, b in zip(
        model.prior_state(first.derivative), model.prior_state(off.derivative), strict=True
    ):
        np.testing.assert_array_equal(a, b)
    assert np.any(
        first.derivative.energy_amount_increment_fmol != off.derivative.energy_amount_increment_fmol
    )
    assert not np.any(off.derivative.regeneration_cycles_fmol)
    assert not np.any(off.derivative.regeneration_supplied_work_pJ)


@pytest.mark.parametrize("arm", ["supply_off", "inhibited", "reverse"])
def test_signed_demand_and_source_controls(arm):
    _, state, p, control = initial(definition(arm))
    value = model.readouts(state, control, p, xp=np)
    if arm == "supply_off":
        assert not np.any(value.derivative.regeneration_cycles_fmol)
        assert value.derivative.energy_amount_increment_fmol[0, 0] < 0
    elif arm == "inhibited":
        assert not np.any(value.derivative.pump_cycles)
        assert value.derivative.energy_amount_increment_fmol[0, 0] > 0
    else:
        assert value.derivative.pump_cycles[0] < 0
        assert value.derivative.energy_amount_increment_fmol[0, 0] > 0


@pytest.mark.parametrize("key", [*model.EXTRA_AXES, "metabolic_work_pJ", "pump_cycles"])
def test_corrupt_finite_energy_material_or_transfer_ledgers_are_rejected(key):
    spec, state, _, _ = initial(definition(padded=True))
    changed = getattr(state, key).copy()
    changed.flat[0] += 0.001
    with pytest.raises(NumericalError):
        model.check_values(state._replace(**{key: changed}), spec)


def test_exhausted_atp_is_invalid_even_with_all_pump_and_supply_controls_off():
    _, state, p, control = initial()
    increment = state.energy_amount_increment_fmol.copy()
    increment[0, 0] = -p.energy_initial_amount_fmol[0, 0]
    exhausted = state._replace(energy_amount_increment_fmol=increment)
    blocked = control._replace(
        pump=np.zeros_like(control.pump), regeneration=np.zeros_like(control.regeneration)
    )
    assert not model.control_domain_valid(exhausted, blocked, p, p.active, xp=np)
    assert increment[0, 0] == -p.energy_initial_amount_fmol[0, 0]


def test_pool_free_energy_change_uses_correct_standard_state_and_small_increments():
    _, state, p, _ = initial()
    increment = state.energy_amount_increment_fmol.copy()
    increment[:, 0] = [-1e-9, 1e-9, 1e-9]
    changed = state._replace(energy_amount_increment_fmol=increment)
    expected = chemistry.free_energy_change(
        p.energy_initial_amount_fmol[:, 0],
        p.energy_initial_amount_fmol[:, 0] + increment[:, 0],
        p.volume[0],
        p.volume[0],
        float(p.temperature),
        p.energy_delta_g0_J_mol[0],
    )
    np.testing.assert_allclose(
        model.pool_free_energy_change_pJ(changed, p)[0], expected, atol=3e-15, rtol=3e-9
    )


def test_initial_observer_retains_all_state_fields_and_internal_work_semantics():
    spec, state, p, _ = initial(definition(padded=True))
    history = model.STATE_TYPE(*(np.asarray([v]) for v in state))
    observations = model.observe_history(np.asarray([0.0]), history, p, np.asarray([0.0]), spec)
    assert all(hasattr(observations, field) for field in model.STATE_TYPE._fields)
    assert observations.energy_amount_fmol.shape == (1, 3, spec.execution.capacity)
    assert observations.regeneration_power_pJ_s.shape == (1, spec.execution.regeneration_capacity)
    assert np.max(np.abs(observations.energy_balance_pJ)) == 0.0
    assert (
        "Internal"
        in model.summarize(history, model.check_values(state, spec), spec)["metabolic_work_role"]
    )
