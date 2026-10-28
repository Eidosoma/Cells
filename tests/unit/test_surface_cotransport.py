"""Complete host/reference stages and conservative cotransport tissue accounting."""

import json
import os
from pathlib import Path

import numpy as np
import pytest

from cells.core import surface_cotransport_spec as schema
from cells.core.errors import NumericalError
from cells.core.schedule import control_values
from cells.core.specs import parse_spec
from cells.models import surface_cotransport as model
from cells.models import surface_energy as energy
from validation.tissue import surface_cotransport_fixtures as fixtures
from validation.tissue import surface_cotransport_reference as reference
from validation.transport import cotransport_reference as chemistry

EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")
BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")


def evidence(name, report, arrays=None):
    if EVIDENCE:
        root = Path(EVIDENCE) / BACKEND
        root.mkdir(parents=True, exist_ok=True)
        if arrays is not None:
            np.savez_compressed(root / ("resolved-cotransport-" + name + ".npz"), **arrays)
        (root / ("resolved-cotransport-" + name + ".json")).write_text(
            json.dumps(report, indent=2, allow_nan=False, default=lambda v: v.tolist()) + "\n"
        )


def initial(arm="coupled", *, padded=False, time=0.0):
    raw = fixtures.definition(arm, backend=BACKEND, padded=padded)
    spec = parse_spec(raw)
    state, p = model.initial_values(spec)
    table = control_values(spec, [time])
    return raw, spec, state, p, type(table)(*(v[0] for v in table))


def compact(c, values):
    return reference.flatten(
        c,
        {
            key: np.asarray(values[key])[tuple(slice(0, n) for n in shape)]
            for key, shape in c["shapes"].items()
        },
    )


def compare_stage(raw, spec, state, p, control, name, time):
    actual = model.readouts(state, control, p, xp=np)
    captured = {"actual_" + k: np.asarray(v) for k, v in actual.derivative._asdict().items()}
    evidence(name, dict(status="actual_captured", inputs=raw, time=time), captured)
    c = reference.bind(raw)
    d = reference.unpack(c, reference.initial(c))
    for key, shape in c["shapes"].items():
        d[key] = np.asarray(getattr(state, key))[tuple(slice(0, n) for n in shape)]
    expected, phi, proof = reference.evaluate(c, reference.flatten(c, d), time)
    observed = compact(c, actual.derivative._asdict())
    observed_phi = np.r_[
        actual.field.potential_V[: p.active.size][p.active],
        actual.field.potential_V[p.active.size :][p.outside_active],
    ]
    evidence(
        name,
        dict(status="captured", inputs=raw, time=time, independent=proof),
        captured
        | dict(actual=observed, expected=expected, actual_phi=observed_phi, expected_phi=phi),
    )
    atol = reference.flatten(
        c,
        {
            key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
            for key, shape in c["shapes"].items()
        },
    )
    score = float(
        np.max(np.abs(observed - expected) / (atol + 3e-10 * np.abs(expected)), initial=0)
    )
    assert score <= 1.0
    np.testing.assert_allclose(observed_phi, phi, rtol=3e-10, atol=3e-13)
    assert actual.valid and model.domain_valid(state, p, p.active, xp=np)
    assert abs(actual.field.energy_balance_pJ_s) < 2e-8
    assert abs(proof["physical_energy_balance_pJ_s"]) < 2e-8
    assert np.min(actual.derivative.cotransport_dissipated_energy_pJ, initial=0) >= 0
    evidence(
        name,
        dict(
            status="passed", inputs=raw, time=time, max_error_over_budget=score, independent=proof
        ),
    )
    return actual


@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("padded", [False, True])
def test_complete_26_field_stage_against_independent_reference(arm, padded):
    raw, spec, state, p, control = initial(arm, padded=padded)
    compare_stage(
        raw, spec, state, p, control, f"stage-{arm}-{'padded' if padded else 'compact'}", 0.0
    )
    model.check_values(state, spec)


@pytest.mark.parametrize("time", [11.1e-6, 19.1e-6, 29.9e-6, 43.3e-6])
def test_actual_independent_clock_stage_matches_right_continuous_reference(time):
    raw, spec, state, p, control = initial("release", padded=True, time=time)
    compare_stage(raw, spec, state, p, control, f"clock-{time:.9g}", time)


@pytest.mark.parametrize("arm", ["sealed", "absent"])
def test_closed_or_absent_routes_reduce_exactly_to_finite_energy(arm):
    _, spec, state, p, control = initial(arm, padded=True)
    actual = model.readouts(state, control, p, xp=np)
    projected = schema.energy_spec(spec)
    old_state, old_p = energy.initial_values(projected)
    old = energy.readouts(old_state, model.prior_control(control), old_p, xp=np)
    for a, b in zip(model.prior_state(actual.derivative), old.derivative, strict=True):
        np.testing.assert_array_equal(a, b)
    for key in model.EXTRA_AXES:
        assert not np.any(getattr(actual.derivative, key))
    np.testing.assert_array_equal(
        actual.field.rates.membrane_flux_fmol_s, old.field.rates.membrane_flux_fmol_s
    )


def test_same_stage_changes_material_without_direct_capacitive_or_atp_shortcut():
    _, _, state, p, control = initial(padded=True)
    live = model.readouts(state, control, p, xp=np)
    sealed = model.readouts(
        state, control._replace(cotransport=np.zeros_like(control.cotransport)), p, xp=np
    )
    assert not np.array_equal(live.derivative.amount_increment, sealed.derivative.amount_increment)
    np.testing.assert_array_equal(
        live.field.membrane_voltage_rate_V_s, sealed.field.membrane_voltage_rate_V_s
    )
    np.testing.assert_array_equal(live.field.electrode_current_A, sealed.field.electrode_current_A)
    np.testing.assert_array_equal(
        live.derivative.electrode_charge_transferred_C,
        sealed.derivative.electrode_charge_transferred_C,
    )
    np.testing.assert_array_equal(
        live.derivative.energy_amount_increment_fmol, sealed.derivative.energy_amount_increment_fmol
    )
    np.testing.assert_array_equal(live.derivative.pump_cycles, sealed.derivative.pump_cycles)
    transfer = live.derivative.amount_increment - sealed.derivative.amount_increment
    np.testing.assert_allclose(np.sum(p.valence * transfer, axis=0), 0, atol=3e-12, rtol=0)
    heat = np.sum(live.derivative.cotransport_dissipated_energy_pJ)
    np.testing.assert_allclose(
        live.field.chemical_energy_rate_pJ_s - sealed.field.chemical_energy_rate_pJ_s,
        -heat,
        rtol=3e-10,
        atol=3e-10,
    )


def test_reversed_and_equal_products_have_the_declared_signed_regimes():
    values = {}
    for arm in ("coupled", "reverse", "stall"):
        _, _, state, p, control = initial(arm)
        values[arm] = model.readouts(state, control, p, xp=np).cotransport
    assert values["coupled"].cycle_fmol_s[0] < 0 < values["coupled"].cycle_fmol_s[1]
    np.testing.assert_allclose(
        values["reverse"].cycle_fmol_s, -values["coupled"].cycle_fmol_s, rtol=3e-10, atol=3e-12
    )
    np.testing.assert_array_equal(values["stall"].cycle_fmol_s, 0)
    np.testing.assert_array_equal(values["stall"].affinity_J_mol, 0)


def test_live_cotransport_material_changes_the_next_channel_and_pump_stage():
    raw, spec, state, p, control = initial(padded=True)
    sealed_control = control._replace(cotransport=np.zeros_like(control.cotransport))
    live = model.readouts(state, control, p, xp=np)
    sealed = model.readouts(state, sealed_control, p, xp=np)
    # A manufactured stage displacement isolates only the neutral route contribution.
    changed = model.STATE_TYPE(
        *(
            v + 1e-7 * (a - b)
            for v, a, b in zip(state, live.derivative, sealed.derivative, strict=True)
        )
    )
    next_stage = model.readouts(changed, sealed_control, p, xp=np)
    assert next_stage.valid
    assert not np.array_equal(next_stage.derivative.pump_cycles, sealed.derivative.pump_cycles)
    assert not np.array_equal(
        next_stage.derivative.channel_transferred, sealed.derivative.channel_transferred
    )
    for row in raw["experiment"]["cotransport_controls"]:
        row["schedule"][0]["availability"] = 0.0
    compare_stage(raw, spec, changed, p, sealed_control, "live-ionic-stage", 0.0)


def test_repeated_routes_on_patches_share_one_pool_and_scatter_once():
    _, _, state, p, control = initial("two_patches", padded=True)
    live = model.readouts(state, control, p, xp=np)
    for route in range(3):
        blocked = control.cotransport.copy()
        blocked[route] = 0
        off = model.readouts(state, control._replace(cotransport=blocked), p, xp=np)
        expected = (
            p.cotransport_stoichiometry[:, route] * live.derivative.cotransport_cycles_fmol[route]
        )
        np.testing.assert_allclose(
            live.derivative.amount_increment[:, 0] - off.derivative.amount_increment[:, 0],
            expected,
            rtol=3e-10,
            atol=3e-12,
        )
        np.testing.assert_allclose(
            live.derivative.extracellular_amount_increment[:, 0]
            - off.derivative.extracellular_amount_increment[:, 0],
            -expected,
            rtol=3e-10,
            atol=3e-12,
        )
        np.testing.assert_array_equal(
            live.derivative.energy_amount_increment_fmol,
            off.derivative.energy_amount_increment_fmol,
        )
    assert p.cotransport_membrane[0] == p.cotransport_membrane[2]
    assert p.membrane_cell[p.cotransport_membrane[0]] == p.membrane_cell[p.cotransport_membrane[1]]


def conservative_state(arm="coupled", padded=True):
    _, spec, state, p, _ = initial(arm, padded=padded)
    xi = state.cotransport_cycles_fmol.copy()
    xi[0] = -0.01  # Initially outward KCl gradient, positive heat.
    transfer = p.cotransport_stoichiometry * xi
    patch = model.route_to_membrane(transfer, p, xp=np)
    di = energy.ordered_scatter(
        patch, np.zeros_like(state.amount_increment), (p.membrane_cell,), xp=np
    )
    do = -energy.ordered_scatter(
        patch, np.zeros_like(state.extracellular_amount_increment), (p.membrane_outside,), xp=np
    )
    active = np.r_[p.active, p.outside_active]
    before = np.concatenate(model.physical_amounts(state, p), axis=-1)[:, active]
    after = before + np.concatenate((di, do), axis=-1)[:, active]
    volume = np.r_[p.volume, p.extracellular_volume][active]
    heat = np.zeros_like(xi)
    heat[0] = -chemistry.chemical_free_energy_change(
        before.tolist(), after.tolist(), volume.tolist(), float(p.temperature)
    )
    assert heat[0] > 0
    return (
        spec,
        state._replace(
            amount_increment=di,
            extracellular_amount_increment=do,
            cotransport_cycles_fmol=xi,
            cotransport_transferred_fmol=transfer,
            cotransport_dissipated_energy_pJ=heat,
        ),
        p,
    )


def test_exact_manufactured_extent_reconstructs_local_material_and_full_energy():
    spec, state, p = conservative_state()
    checked = model.check_values(state, spec)
    assert checked["max_energy_balance_error_pJ"] < energy.passive.ENERGY_ATOL_PJ
    for key in ("local", "outside", "total", "cotransport_material", "cotransport_charge"):
        np.testing.assert_allclose(model.balances(state, p)[key], 0, atol=3e-12, rtol=0)
    evidence("closed-extent", dict(status="passed", diagnostics=checked), state._asdict())


@pytest.mark.parametrize(
    "corruption", ["cycles", "compensating_routes", "heat", "inactive_transfer", "pool"]
)
def test_local_route_and_energy_ledger_corruption_is_rejected(corruption):
    spec, state, p = conservative_state("two_patches")
    model.check_values(state, spec)
    if corruption == "cycles":
        v = state.cotransport_cycles_fmol.copy()
        v[0] += 0.001
        state = state._replace(cotransport_cycles_fmol=v)
    elif corruption == "compensating_routes":
        v = state.cotransport_transferred_fmol.copy()
        delta = p.cotransport_stoichiometry[:, 0] * 0.001
        v[:, 0] += delta
        v[:, 2] -= delta
        state = state._replace(cotransport_transferred_fmol=v)
        # Material/charge totals are unchanged; only individual route evidence detects it.
        b = model.balances(state, p)
        assert (
            np.max(np.abs(b["local"])) < 3e-12
            and np.max(np.abs(b["cotransport_material"])) > 0.0009
        )
    elif corruption == "heat":
        state = state._replace(
            cotransport_dissipated_energy_pJ=state.cotransport_dissipated_energy_pJ * 2
        )
    elif corruption == "inactive_transfer":
        v = state.cotransport_transferred_fmol.copy()
        v[0, -1] = 0.001
        state = state._replace(cotransport_transferred_fmol=v)
    else:
        v = state.energy_amount_increment_fmol.copy()
        v[0, 0] = 1e-5
        state = state._replace(energy_amount_increment_fmol=v)
    with pytest.raises(NumericalError):
        model.check_values(state, spec)


def test_exhaustion_is_rejected_with_every_route_blocked():
    _, _, state, p, control = initial(padded=True)
    zeroed = state.amount_increment.copy()
    zeroed[1, 0] = -p.amount_reference[1, 0]
    bad = state._replace(amount_increment=zeroed)
    blocked = schema.Control(*(np.zeros_like(v) for v in control))
    assert not model.domain_valid(bad, p, p.active, xp=np)
    assert not model.control_domain_valid(bad, blocked, p, p.active, xp=np)


def test_complete_initial_observation_and_ensemble_voltage_use_new_live_rates():
    _, spec, state, p, control = initial(padded=True)
    times = np.array([0.0])
    observed = model.observe_history(
        times, model.STATE_TYPE(*(np.asarray([v]) for v in state)), p, times, spec
    )
    value = model.readouts(state, control, p, xp=np)
    for key in model.STATE_TYPE._fields:
        np.testing.assert_array_equal(getattr(observed, key)[0], getattr(state, key))
    np.testing.assert_array_equal(
        observed.membrane_flux_fmol_s[0], value.field.rates.membrane_flux_fmol_s
    )
    np.testing.assert_array_equal(
        observed.cotransport_cycle_rate_fmol_s[0], value.cotransport.cycle_fmol_s
    )
    np.testing.assert_array_equal(
        model.ensemble_voltage(state, p, spec, 0.0),
        value.field.rates.membrane_voltage_V[p.membrane_active],
    )


def test_nonzero_transfer_history_observer_retains_total_flux_and_complete_energy():
    spec, state, p = conservative_state()
    start, _ = model.initial_values(spec)
    times = np.array([0.0, fixtures.CHECKPOINT_TIME])
    history = model.STATE_TYPE(*(np.stack((a, b)) for a, b in zip(start, state, strict=True)))
    observed = model.observe_history(times, history, p, times, spec)
    table = control_values(spec, [times[-1]])
    value = model.readouts(state, type(table)(*(v[0] for v in table)), p, xp=np)
    np.testing.assert_array_equal(
        observed.cotransport_transferred_fmol[-1], state.cotransport_transferred_fmol
    )
    assert np.any(observed.cotransport_transferred_fmol[-1] != 0)
    np.testing.assert_array_equal(
        observed.membrane_flux_fmol_s[-1], value.field.rates.membrane_flux_fmol_s
    )
    assert np.max(np.abs(observed.energy_balance_pJ)) <= energy.passive.ENERGY_ATOL_PJ
    evidence(
        "nonzero-observer",
        dict(
            status="passed",
            manufactured_closed_extent=True,
            times=times.tolist(),
            state_fields=list(model.STATE_TYPE._fields),
        ),
        vars(observed),
    )


def test_jax_complete_rhs_matches_numpy_and_retains_neutral_capacitive_response():
    import jax

    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    raw, _, state, p, control = initial(padded=True)
    compiled = jax.jit(model.rhs)
    actual = compiled(state, control, p, p.active)
    expected = model.rhs(state, control, p, p.active, xp=np)
    evidence(
        "jax-rhs",
        dict(status="actual_captured", inputs=raw),
        {"actual_" + key: np.asarray(v) for key, v in actual._asdict().items()},
    )
    for key in model.STATE_TYPE._fields:
        np.testing.assert_allclose(
            np.asarray(getattr(actual, key)),
            getattr(expected, key),
            rtol=3e-10,
            atol=3e-23 if key.endswith("_C") else 3e-12,
        )
    blocked = control._replace(cotransport=np.zeros_like(control.cotransport))
    off = compiled(state, blocked, p, p.active)
    np.testing.assert_array_equal(
        np.asarray(actual.electrode_charge_transferred_C),
        np.asarray(off.electrode_charge_transferred_C),
    )
    np.testing.assert_array_equal(
        np.asarray(actual.energy_amount_increment_fmol),
        np.asarray(off.energy_amount_increment_fmol),
    )
    evidence(
        "jax-rhs", dict(status="passed", inputs=raw, state_fields=list(model.STATE_TYPE._fields))
    )


def test_jax_state_domain_rejects_exhaustion_bad_valence_and_route_padding():
    import jax

    _, _, state, p, _ = initial(padded=True)
    valid = jax.jit(model.domain_valid)
    assert bool(valid(state, p, p.active))
    bad = state.amount_increment.copy()
    bad[1, 0] = -p.amount_reference[1, 0]
    assert not bool(valid(state._replace(amount_increment=bad), p, p.active))
    bad_valence = p.cotransport_valence.copy()
    bad_valence[0] = 2
    assert not bool(valid(state, p._replace(cotransport_valence=bad_valence), p.active))
    cycle = state.cotransport_cycles_fmol.copy()
    cycle[-1] = 1e-6
    assert not bool(valid(state._replace(cotransport_cycles_fmol=cycle), p, p.active))
    evidence(
        "jax-domain",
        dict(
            status="passed",
            exhaustion_rejected=True,
            actual_valence_mismatch_rejected=True,
            inactive_cycle_rejected=True,
        ),
    )
