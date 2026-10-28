"""Complete shared stages and once-owned energy under changing ATP and volumes."""

import json
import os
from pathlib import Path

import numpy as np
import pytest

from cells.core.errors import NumericalError
from cells.core.schedule import control_values
from cells.core.specs import parse_spec
from cells.core.surface_energy_water_spec import energy_spec
from cells.models import surface_energy as energy
from cells.models import surface_energy_water as model
from cells.models import surface_water as water
from cells.processes.electrochemistry import R
from validation.chemistry import finite_energy_reference as chemistry
from validation.tissue import surface_energy_water_fixtures as fixtures
from validation.tissue import surface_energy_water_reference as reference

BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")


def evidence(name, value, arrays=None):
    if EVIDENCE:
        root = Path(EVIDENCE) / BACKEND
        root.mkdir(parents=True, exist_ok=True)
        path = root / ("energy-water-" + name)
        path.with_suffix(".json").write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
        if arrays is not None:
            np.savez_compressed(path.with_suffix(".npz"), **arrays)


def initial(raw=None, time=0.0):
    spec = parse_spec(fixtures.definition(backend=BACKEND) if raw is None else raw)
    state, p = model.initial_values(spec)
    table = control_values(spec, [time])
    return spec, state, p, type(table)(*(v[0] for v in table))


def normalized(c, state):
    values = state._asdict() if hasattr(state, "_asdict") else state
    return reference.flatten(
        c,
        {
            k: np.asarray(values[k])[tuple(slice(0, n) for n in shape)]
            for k, shape in c["shapes"].items()
        },
    )


def error_budget(c, actual, expected, *, atol=3e-12, charge_atol=3e-23, rtol=3e-10):
    absolute = reference.flatten(
        c,
        {
            k: np.full(shape, charge_atol if k.endswith("_C") else atol)
            for k, shape in c["shapes"].items()
        },
    )
    ratio = np.abs(actual - expected) / (absolute + rtol * np.abs(expected))
    assert np.isfinite(ratio).all() and np.max(ratio, initial=0) <= 1
    return float(np.max(ratio, initial=0))


@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("padded", [False, True])
def test_complete_stage_with_current_volume_and_pool_particles(arm, padded):
    raw = fixtures.definition(arm, backend=BACKEND, padded=padded)
    time = 32e-6 if arm == "release" else 0.0
    spec, state, p, control = initial(raw, time)
    delta = 0.1 * p.energy_initial_amount_fmol[0, 0]
    state.energy_amount_increment_fmol[:, 0] = [-delta, delta, delta]
    if arm != "sealed":
        state.volume_increment_pL[0] = 0.01
        state.extracellular_volume_increment_pL[0] = -0.01
        state.water_transferred_pL[0] = -0.01
    before = [v.copy() for v in state]
    actual = model.readouts(state, control, p, xp=np)
    c = reference.bind(spec.to_dict())
    expected, phi, proof = reference.evaluate(c, normalized(c, state), time)
    values = normalized(c, actual.derivative)
    name = f"stage-{arm}-{int(padded)}"
    evidence(
        name,
        dict(status="captured", inputs=raw, independent=proof),
        dict(actual=values, expected=expected, state=normalized(c, state)),
    )
    score = error_budget(c, values, expected)
    actual_phi = np.r_[
        actual.field.potential_V[: p.active.size][p.active],
        actual.field.potential_V[p.active.size :][p.outside_active],
    ]
    np.testing.assert_allclose(actual_phi, phi, atol=3e-13, rtol=3e-10)
    assert actual.valid and model.domain_valid(state, p, p.active, xp=np)
    assert abs(actual.field.energy_balance_pJ_s) < 2e-8
    assert abs(proof["physical_energy_balance_pJ_s"]) < 2e-8
    assert np.max(np.abs(proof["pool_internal_transfer_balance_pJ_s"]), initial=0) < 2e-8
    for a, b in zip(state, before, strict=True):
        np.testing.assert_array_equal(a, b)
    evidence(
        name, dict(status="passed", inputs=raw, max_error_over_budget=score, independent=proof)
    )


def test_sealed_water_reduces_exactly_to_complete_finite_energy():
    spec, state, p, control = initial(fixtures.definition("sealed", padded=True))
    base = energy_spec(spec)
    old, q = energy.initial_values(base)
    table = control_values(base, [0.0])
    expected = energy.rhs(old, type(table)(*(v[0] for v in table)), q, q.active, xp=np)
    actual = model.rhs(state, control, p, p.active, xp=np)
    for a, b in zip(model.energy_state(actual), expected, strict=True):
        np.testing.assert_array_equal(a, b)
    assert all(not np.any(getattr(actual, k)) for k in model.EXTRA_AXES)
    evidence("sealed-reduction", dict(status="passed", preserved_fields=23, extra_fields=5))


@pytest.mark.parametrize("padded", [False, True])
def test_multicell_pool_ownership_shared_outside_and_reordered_species(padded):
    raw = fixtures.multicell(backend=BACKEND, padded=padded)
    raw["model"]["species"].reverse()
    spec, state, p, control = initial(raw)
    state.volume_increment_pL[:2] = [0.01, -0.02]
    state.extracellular_volume_increment_pL[0] = 0.01
    state.energy_amount_increment_fmol[:, :2] = [
        [-0.0001, -0.0003],
        [0.0001, 0.0003],
        [0.0001, 0.0003],
    ]
    c = reference.bind(spec.to_dict())
    value = model.readouts(state, control, p, xp=np)
    expected, _, proof = reference.evaluate(c, normalized(c, state), 0.0)
    ratio = error_budget(c, normalized(c, value.derivative), expected)
    assert value.valid and abs(proof["physical_energy_balance_pJ_s"]) < 2e-8
    assert np.max(np.abs(proof["pool_internal_transfer_balance_pJ_s"]), initial=0) < 2e-8
    assert len(set(p.membrane_cell[p.membrane_active])) == 2
    assert p.membrane_active.sum() > 2
    assert np.count_nonzero(p.regeneration_active) == 2
    assert not np.any(value.derivative.pool_volume_work_pJ[~p.active])
    evidence(
        f"multicell-{int(padded)}", dict(status="passed", inputs=raw, max_error_over_budget=ratio)
    )


def test_live_pool_count_changes_osmotic_pressure_without_direct_charge_or_advection():
    _, state, p, control = initial()
    first = model.readouts(state, control, p, xp=np)
    delta = 0.001
    state.energy_amount_increment_fmol[:, 0] = [-delta, delta, delta]
    second = model.readouts(state, control, p, xp=np)
    np.testing.assert_allclose(
        second.water.osmotic_pressure_Pa[0] - first.water.osmotic_pressure_Pa[0],
        R * p.temperature * delta / p.volume[0],
        atol=3e-10,
        rtol=3e-10,
    )
    assert second.water.edge_flow_pL_s[0] != first.water.edge_flow_pL_s[0]
    shut = model.readouts(state, control._replace(water=np.zeros_like(control.water)), p, xp=np)
    for a, b in zip(
        model.energy_state(second.derivative), model.energy_state(shut.derivative), strict=True
    ):
        np.testing.assert_array_equal(a, b)
    assert not np.any(shut.derivative.volume_increment_pL)


def test_conserved_particle_bound_exceeds_initial_count_during_hydrolysis():
    _, state, p, _ = initial(fixtures.definition(padded=True))
    ionic_max = np.sum(water.amounts(state, p))
    bound = model.maximum_osmolyte_amount_fmol(state, p)
    pool_bound = bound[0] - ionic_max - p.water_impermeant_amount_fmol[0]
    current = p.energy_initial_amount_fmol[:, 0]
    np.testing.assert_allclose(pool_bound, 2 * current[0] + current[1] + current[2], atol=2e-13)
    changed = current + np.array([-0.9, 0.9, 0.9]) * current[0]
    assert current.sum() < changed.sum() < pool_bound
    np.testing.assert_array_equal(
        bound[p.active.size :] - ionic_max, p.water_impermeant_amount_fmol[p.active.size :]
    )


def test_free_energy_endpoint_uses_both_current_amount_and_current_volume():
    _, state, p, _ = initial(fixtures.definition(padded=True))
    state.energy_amount_increment_fmol[:, 0] = [-0.001, 0.001, 0.001]
    state.volume_increment_pL[0] = 0.02
    expected = chemistry.free_energy_change(
        p.energy_initial_amount_fmol[:, 0],
        energy.energy_amounts(state, p)[:, 0],
        float(p.volume[0]),
        float(p.volume[0] + state.volume_increment_pL[0]),
        float(p.temperature),
        float(p.energy_delta_g0_J_mol[0]),
    )
    np.testing.assert_allclose(
        model.pool_free_energy_change_pJ(state, p)[0], expected, atol=3e-15, rtol=3e-10
    )
    assert not np.any(model.pool_free_energy_change_pJ(state, p)[~p.active])


def test_volume_work_is_internal_signed_and_cannot_be_added_as_external_supply():
    spec, state, p, control = initial()
    value = model.readouts(state, control, p, xp=np)
    assert value.derivative.pool_volume_work_pJ[0] < 0
    original = model.balances(state, p)
    state.pool_volume_work_pJ[0] = -0.001
    changed = model.balances(state, p)
    assert original["energy"] == changed["energy"]
    np.testing.assert_allclose(changed["pool_energy"] - original["pool_energy"], 0.001)
    with pytest.raises(NumericalError, match="pool_energy"):
        model.check_values(state, spec)


@pytest.mark.parametrize(
    "key", [*model.EXTRA_AXES, "energy_amount_increment_fmol", "regeneration_supplied_work_pJ"]
)
def test_corrupted_complete_ledgers_are_rejected(key):
    spec, state, _, _ = initial(fixtures.definition(padded=True))
    getattr(state, key).flat[0] += 0.001
    with pytest.raises(NumericalError):
        model.check_values(state, spec)


@pytest.mark.parametrize(
    "fault", ["atp", "minimum_volume", "maximum_volume", "padded_volume_work", "nan_volume_work"]
)
def test_invalid_trials_rejected_even_when_routes_are_blocked(fault):
    _, state, p, control = initial(fixtures.definition(padded=True))
    if fault == "atp":
        state.energy_amount_increment_fmol[0, 0] = -p.energy_initial_amount_fmol[0, 0]
    elif fault.endswith("volume"):
        target = (
            p.water_minimum_volume_pL[0]
            if fault.startswith("minimum")
            else p.water_maximum_volume_pL[0]
        )
        state.volume_increment_pL[0] = target - p.volume[0]
    elif fault == "padded_volume_work":
        state.pool_volume_work_pJ[-1] = 1e-9
    else:
        state.pool_volume_work_pJ[0] = np.nan
    off = type(control)(*(np.zeros_like(v) for v in control))
    assert not model.control_domain_valid(state, off, p, p.active, xp=np)


def test_small_host_trajectory_preserves_combined_energy_and_observer_semantics():
    spec, state, p, control = initial()
    dt = fixtures.DT

    def add(base, slope, factor):
        return model.STATE_TYPE(*(a + factor * b for a, b in zip(base, slope, strict=True)))

    for _ in range(10):
        k1 = model.rhs(state, control, p, p.active, xp=np)
        k2 = model.rhs(add(state, k1, dt / 2), control, p, p.active, xp=np)
        k3 = model.rhs(add(state, k2, dt / 2), control, p, p.active, xp=np)
        k4 = model.rhs(add(state, k3, dt), control, p, p.active, xp=np)
        state = model.STATE_TYPE(
            *(
                a + dt * (b + 2 * c + 2 * d + e) / 6
                for a, b, c, d, e in zip(state, k1, k2, k3, k4, strict=True)
            )
        )
    diagnostics = model.check_values(state, spec)
    assert state.pool_volume_work_pJ[0] < 0
    assert abs(model.pool_dilution_pJ(state, p)[0] - state.pool_volume_work_pJ[0]) > 1e-12
    time = np.asarray([10 * dt])
    observations = model.observe_history(
        time, model.STATE_TYPE(*(v[None] for v in state)), p, time, spec
    )
    assert all(hasattr(observations, k) for k in model.STATE_TYPE._fields)
    expected = chemistry.free_energy_change(
        p.energy_initial_amount_fmol[:, 0],
        energy.energy_amounts(state, p)[:, 0],
        float(p.volume[0]),
        float(p.volume[0] + state.volume_increment_pL[0]),
        float(p.temperature),
        float(p.energy_delta_g0_J_mol[0]),
    )
    np.testing.assert_allclose(
        observations.energy_free_energy_change_pJ[0, 0], expected, atol=3e-15, rtol=3e-10
    )
    np.testing.assert_allclose(
        observations.energy_concentration_mM[0],
        energy.energy_amounts(state, p) / (p.volume + state.volume_increment_pL),
        atol=1e-18,
        rtol=3e-14,
    )
    np.testing.assert_array_equal(observations.pool_volume_work_pJ[0], state.pool_volume_work_pJ)
    evidence(
        "host-trajectory",
        dict(
            status="passed",
            inputs=spec.to_dict(),
            diagnostics=diagnostics,
            endpoint_pool_dilution_pJ=float(model.pool_dilution_pJ(state, p)[0]),
            integrated_pool_volume_work_pJ=float(state.pool_volume_work_pJ[0]),
        ),
    )
