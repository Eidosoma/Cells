"""Physical invariants and analytic solutions for lateral membrane transport."""

import json
import os
from decimal import Decimal, localcontext
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.numerics import membrane_redistribution as model
from cells.processes.electrochemistry import F, R


def layout():
    # Two separate cells, unequal patch areas, three populations and one pad.
    return model.validate_layout(
        model.Layout(
            np.array(298.15),
            np.array([0.0, 1.0, -1.0]),
            np.array([True, True, False]),
            np.array([True, True, True, True, False]),
            np.array([0, 0, 1, 1, 2]),
            np.array([2.0, 5.0, 3.0, 4.0, 0.0]),
            np.array([True, True, False]),
            np.array([0, 2, 4]),
            np.array([1, 3, 4]),
            np.array([[0.2, 0.4, 0.0], [0.3, 0.1, 0.0], [0.15, 0.2, 0.0]]),
            np.array([1.5, 1.0, 0.0]),
            np.array([0.8, 0.6, 0.0]),
        )
    )


def inputs():
    return (
        np.array([[1.0, 2.0, 0.4, 0.9, 0.0], [0.3, 0.8, 0.5, 0.7, 0.0], [0.9, 0.2, 0.6, 0.2, 0.0]]),
        np.array([-0.012, 0.006, 0.003, -0.004, 0.0]),
        layout(),
    )


def scalar_rates(amount, potential, p):
    """Independent high-precision edge law and explicit owner bookkeeping."""
    flux = np.zeros_like(p.edge_diffusivity_um2_s)
    derivative = np.zeros_like(amount)
    with localcontext() as context:
        context.prec = 80
        d = lambda value: Decimal(str(float(value)))  # noqa: E731
        f = Decimal("6.02214076e23") * Decimal("1.602176634e-19")
        r = Decimal("6.02214076e23") * Decimal("1.380649e-23")
        for k, charge in enumerate(p.effective_charge_e):
            for edge in np.flatnonzero(p.edge_active):
                i, j = p.edge_sender[edge], p.edge_receiver[edge]
                x = d(charge) * f * (d(potential[j]) - d(potential[i])) / (r * d(p.temperature_K))
                left = d(amount[k, i]) / d(p.patch_area_um2[i])
                right = d(amount[k, j]) / d(p.patch_area_um2[j])
                if x == 0:
                    drive = left - right
                else:
                    drive = x * (left - x.exp() * right) / (x.exp() - 1)
                g = d(p.edge_diffusivity_um2_s[k, edge]) * d(p.edge_width_um[edge])
                g /= d(p.edge_distance_um[edge])
                value = float(g * drive)
                flux[k, edge] = value
                derivative[k, i] -= value
                derivative[k, j] += value
    return flux, derivative


@pytest.fixture(scope="module", autouse=True)
def precision():
    jax.config.update("jax_enable_x64", True)


def test_independent_rates_and_cell_conservation():
    amount, potential, p = inputs()
    actual = model.rates(amount, potential, p, xp=np)
    assert actual.valid
    flux, derivative = scalar_rates(amount, potential, p)
    np.testing.assert_allclose(actual.flux_fmol_s, flux, rtol=2e-13, atol=2e-16)
    np.testing.assert_allclose(actual.amount_rate_fmol_s, derivative, rtol=2e-13, atol=2e-16)
    np.testing.assert_allclose(actual.cell_rate_residual_fmol_s, 0, rtol=0, atol=2e-16)
    np.testing.assert_array_equal(actual.amount_rate_fmol_s[:, -1], 0)
    # Material cannot change a neighbouring cell even when its population differs.
    changed = amount.copy()
    changed[:, :2] *= 3
    other = model.rates(changed, potential, p, xp=np)
    np.testing.assert_array_equal(other.amount_rate_fmol_s[:, 2:], actual.amount_rate_fmol_s[:, 2:])


def test_uniform_density_and_boltzmann_equilibria():
    _, potential, p = inputs()
    uniform = np.ones((3, 5)) * p.patch_area_um2
    zero = model.rates(uniform, np.zeros(5), p, xp=np)
    np.testing.assert_allclose(zero.flux_fmol_s, 0, rtol=0, atol=2e-16)
    equilibrium = uniform * np.exp(
        -p.effective_charge_e[:, None] * F * potential / (R * p.temperature_K)
    )
    values = model.rates(equilibrium, potential, p, xp=np)
    assert values.valid
    np.testing.assert_allclose(values.flux_fmol_s, 0, rtol=0, atol=5e-16)
    # Equal amounts on unequal areas are deliberately not a diffusion equilibrium.
    equal_amounts = np.ones((3, 5)) * p.patch_active
    assert np.any(model.rates(equal_amounts, np.zeros(5), p, xp=np).flux_fmol_s != 0)


def test_field_reversal_gauge_and_edge_orientation():
    _, potential, p = inputs()
    amount = np.ones((3, 5)) * p.patch_area_um2
    original = model.rates(amount, potential, p, xp=np)
    field_reversed = model.rates(amount, -potential, p, xp=np)
    np.testing.assert_allclose(
        field_reversed.flux_fmol_s, -original.flux_fmol_s, rtol=2e-13, atol=2e-16
    )
    shifted = model.rates(amount, potential + 0.03 * p.patch_active, p, xp=np)
    np.testing.assert_allclose(
        shifted.amount_rate_fmol_s, original.amount_rate_fmol_s, rtol=2e-13, atol=2e-16
    )
    reverse = p._replace(edge_sender=p.edge_receiver, edge_receiver=p.edge_sender)
    model.validate_layout(reverse)
    oriented = model.rates(amount, potential, reverse, xp=np)
    np.testing.assert_allclose(oriented.flux_fmol_s, -original.flux_fmol_s, rtol=2e-13, atol=2e-16)
    np.testing.assert_allclose(
        oriented.amount_rate_fmol_s, original.amount_rate_fmol_s, rtol=2e-13, atol=2e-16
    )
    assert original.flux_fmol_s[1, 0] < 0  # Positive cargo drifts down potential.
    assert original.flux_fmol_s[2, 0] > 0


@pytest.mark.parametrize("x", [0.0, 1e-12, -1e-12, 1e-5, -1e-5, 49.9, -49.9])
def test_zero_field_limit_and_large_drift_against_decimal(x):
    amount, potential, p = inputs()
    potential[:] = 0
    potential[1] = x * R * p.temperature_K / F
    expected, _ = scalar_rates(amount, potential, p)
    actual = model.rates(amount, potential, p, xp=np)
    assert actual.valid
    np.testing.assert_allclose(actual.flux_fmol_s, expected, rtol=3e-13, atol=2e-15)


def test_passive_free_energy_and_transfer_ledger():
    amount, potential, p = inputs()
    r = model.rates(amount, potential, p, xp=np)
    active = p.patch_active
    density = amount[:, active] / p.patch_area_um2[active]
    mu = (
        R * p.temperature_K * np.log(density)
        + p.effective_charge_e[:, None] * F * potential[active]
    )
    # Free energy includes the imposed electric potential; no claim of a closed field reservoir.
    derivative = np.sum(mu * r.amount_rate_fmol_s[:, active], axis=1)
    assert np.all(derivative < 0)
    step = model.explicit_step(amount, potential, 0.1, p, xp=np)
    assert step.valid
    reconstructed = amount.copy()
    for edge in np.flatnonzero(p.edge_active):
        reconstructed[:, p.edge_sender[edge]] -= step.transferred_fmol[:, edge]
        reconstructed[:, p.edge_receiver[edge]] += step.transferred_fmol[:, edge]
    np.testing.assert_allclose(step.amount_fmol, reconstructed, rtol=2e-15, atol=2e-16)
    np.testing.assert_allclose(step.cell_residual_fmol, 0, rtol=0, atol=6e-16)


def test_empty_population_and_positivity_bound():
    p = model.validate_layout(
        model.Layout(
            np.array(298.15),
            np.array([0.0]),
            np.array([True]),
            np.array([True, True]),
            np.array([0, 0]),
            np.array([1.0, 1.0]),
            np.array([True]),
            np.array([0]),
            np.array([1]),
            np.array([[1.0]]),
            np.array([1.0]),
            np.array([1.0]),
        )
    )
    amount, potential = np.array([[1.0, 0.0]]), np.zeros(2)
    step = model.explicit_step(amount, potential, 1.0, p, xp=np)
    assert step.valid
    np.testing.assert_array_equal(step.amount_fmol, [[0.0, 1.0]])
    rejected = model.explicit_step(amount, potential, np.nextafter(1.0, 2.0), p, xp=np)
    assert not rejected.valid and np.isnan(rejected.amount_fmol).all()
    empty = model.explicit_step(np.zeros_like(amount), potential, 0.25, p, xp=np)
    assert empty.valid
    np.testing.assert_array_equal(empty.amount_fmol, 0)


def test_blocked_and_no_edge_reductions():
    amount, potential, p = inputs()
    blocked = p._replace(edge_diffusivity_um2_s=np.zeros_like(p.edge_diffusivity_um2_s))
    none = p._replace(
        edge_active=np.empty(0, dtype=bool),
        edge_sender=np.empty(0, dtype=int),
        edge_receiver=np.empty(0, dtype=int),
        edge_diffusivity_um2_s=np.empty((3, 0)),
        edge_width_um=np.empty(0),
        edge_distance_um=np.empty(0),
    )
    for definition in (blocked, none):
        model.validate_layout(definition)
        value = model.explicit_step(amount, potential, 1e6, definition, xp=np)
        assert value.valid
        np.testing.assert_array_equal(value.amount_fmol, amount)


def test_branching_surface_sums_all_outgoing_routes():
    p = model.validate_layout(
        model.Layout(
            np.array(298.15),
            np.array([0.0]),
            np.array([True]),
            np.ones(3, dtype=bool),
            np.zeros(3, dtype=int),
            np.ones(3),
            np.ones(2, dtype=bool),
            np.array([0, 0]),
            np.array([1, 2]),
            np.array([[1.0, 2.0]]),
            np.ones(2),
            np.ones(2),
        )
    )
    amount, potential = np.array([[1.0, 0.0, 0.0]]), np.zeros(3)
    step = jax.jit(model.explicit_step)(amount, potential, 0.3, p)
    assert step.valid
    np.testing.assert_allclose(step.amount_fmol, [[0.1, 0.3, 0.6]], rtol=0, atol=2e-16)
    rejected = model.explicit_step(amount, potential, 0.4, p, xp=np)
    assert not rejected.valid  # Each edge alone would permit this step.
    assert np.isnan(rejected.amount_fmol).all()


def test_patch_subdivision_preserves_density_and_total_transport():
    amount, potential, p = inputs()
    original = model.rates(amount, potential, p, xp=np)
    split = model.validate_layout(
        model.Layout(
            p.temperature_K,
            p.effective_charge_e,
            np.array([True]),
            np.ones(3, dtype=bool),
            np.zeros(3, dtype=int),
            np.array([1.0, 1.0, 5.0]),
            np.ones(2, dtype=bool),
            np.array([0, 1]),
            np.array([2, 2]),
            np.repeat(p.edge_diffusivity_um2_s[:, :1], 2, axis=1),
            np.array([0.75, 0.75]),
            np.array([0.8, 0.8]),
        )
    )
    n = np.stack([amount[:, 0] / 2, amount[:, 0] / 2, amount[:, 1]], axis=1)
    phi = np.array([potential[0], potential[0], potential[1]])
    value = model.rates(n, phi, split, xp=np)
    assert value.valid
    np.testing.assert_allclose(
        value.flux_fmol_s.sum(axis=1), original.flux_fmol_s[:, 0], rtol=2e-13, atol=2e-16
    )
    grouped = np.stack(
        [
            value.amount_rate_fmol_s[:, :2].sum(axis=1),
            value.amount_rate_fmol_s[:, 2],
        ],
        axis=1,
    )
    np.testing.assert_allclose(grouped, original.amount_rate_fmol_s[:, :2], rtol=2e-13, atol=2e-16)


@pytest.mark.parametrize("dt", [-1e-12, np.nan, np.inf])
def test_invalid_step_rejects_without_advancing(dt):
    amount, potential, p = inputs()
    with np.errstate(invalid="ignore"):
        value = model.explicit_step(amount, potential, dt, p, xp=np)
    assert not value.valid
    assert all(np.isnan(v).all() for v in value[:-1])


@pytest.mark.parametrize(
    "change",
    [
        "cross-cell",
        "duplicate",
        "inactive-owner",
        "negative-D",
        "zero-area",
        "padding",
        "shape",
        "index",
        "temperature",
    ],
)
def test_invalid_geometry_is_rejected(change):
    p = layout()
    changes = {
        "cross-cell": {"edge_receiver": np.array([2, 3, 4])},
        "duplicate": {"edge_sender": np.array([0, 1, 4]), "edge_receiver": np.array([1, 0, 4])},
        "inactive-owner": {"patch_cell": np.array([0, 0, 1, 2, 2])},
        "negative-D": {"edge_diffusivity_um2_s": -p.edge_diffusivity_um2_s},
        "zero-area": {"patch_area_um2": np.array([0.0, 5.0, 3.0, 4.0, 0.0])},
        "padding": {"edge_width_um": np.array([1.5, 1.0, 1.0])},
        "shape": {"edge_diffusivity_um2_s": np.zeros((2, 3))},
        "index": {"edge_sender": np.array([0, 2, -1])},
        "temperature": {"temperature_K": np.array(0.0)},
    }
    with pytest.raises(ValueError):
        model.validate_layout(p._replace(**changes[change]))


@pytest.mark.parametrize(
    "change", ["negative", "nan", "material-padding", "potential-padding", "drift"]
)
def test_invalid_state_is_reported_without_clipping(change):
    amount, potential, p = inputs()
    if change == "negative":
        amount[0, 0] = -1e-15
    elif change == "nan":
        amount[0, 0] = np.nan
    elif change == "material-padding":
        amount[0, -1] = 1e-15
    elif change == "potential-padding":
        potential[-1] = 1e-15
    else:
        potential[0] = 2.0
    value = model.rates(amount, potential, p, xp=np)
    assert not value.valid
    assert all(np.isnan(v).all() for v in value[:-1])


def test_jitted_cpu_worlds_match_numpy_and_reordering():
    amount, potential, p = inputs()
    expected = model.rates(amount, potential, p, xp=np)
    actual = jax.jit(model.rates)(amount, potential, p)
    jax.block_until_ready(actual)
    assert actual.valid
    for want, got in zip(expected[:-1], actual[:-1], strict=True):
        np.testing.assert_allclose(got, want, rtol=3e-13, atol=5e-16)
        assert got.dtype == jnp.float64
        assert got.device.platform == "cpu"
    amounts = np.stack([amount, amount * 0.7])
    potentials = np.stack([potential, -potential])
    batched = jax.jit(jax.vmap(model.explicit_step, in_axes=(0, 0, None, None)))
    values = batched(amounts, potentials, 0.1, p)
    reversed_values = batched(amounts[::-1], potentials[::-1], 0.1, p)
    assert np.all(values.valid)
    for field, reversed_field in zip(values, reversed_values, strict=True):
        np.testing.assert_array_equal(field, reversed_field[::-1])
    for world in range(2):
        want = model.explicit_step(amounts[world], potentials[world], 0.1, p, xp=np)
        np.testing.assert_allclose(
            values.amount_fmol[world], want.amount_fmol, rtol=3e-13, atol=5e-16
        )


def test_two_patch_analytic_relaxation_refinement_and_restart():
    amount, potential, p = inputs()
    exact = amount.copy()
    # Recover each two-patch generator from independent unit-inventory probes.
    for k in range(3):
        for i, j in ((0, 1), (2, 3)):
            left, right = np.zeros_like(amount), np.zeros_like(amount)
            left[k, i], right[k, j] = 1.0, 1.0
            _, left_rate = scalar_rates(left, potential, p)
            _, right_rate = scalar_rates(right, potential, p)
            a, b = -left_rate[k, i], -right_rate[k, j]
            total = amount[k, i] + amount[k, j]
            equilibrium = total * b / (a + b)
            exact[k, i] = equilibrium + (amount[k, i] - equilibrium) * np.exp(-(a + b) * 2.0)
            exact[k, j] = total - exact[k, i]

    def integrate(start, dt, count):
        def advance(state, _):
            value = model.explicit_step(state, jnp.asarray(potential), dt, p)
            return value.amount_fmol, value.valid

        return jax.lax.scan(advance, start, None, length=count)

    execute = jax.jit(integrate, static_argnums=(2,))
    errors, traces = [], []
    for count in (40, 80, 160):
        actual, valid = execute(jnp.asarray(amount), 2.0 / count, count)
        assert np.all(valid)
        errors.append(float(np.max(np.abs(actual - exact))))
        traces.append(np.asarray(actual))
        np.testing.assert_allclose(
            np.asarray(actual)[:, :2].sum(axis=1), amount[:, :2].sum(axis=1), rtol=0, atol=5e-14
        )
        np.testing.assert_allclose(
            np.asarray(actual)[:, 2:4].sum(axis=1), amount[:, 2:4].sum(axis=1), rtol=0, atol=5e-14
        )
    ratios = np.array(errors[:-1]) / errors[1:]
    assert np.all((ratios > 1.98) & (ratios < 2.06))
    midpoint, valid = execute(jnp.asarray(amount), 2.0 / 160, 80)
    assert np.all(valid)
    resumed, valid = execute(jnp.asarray(np.asarray(midpoint)), 2.0 / 160, 80)
    assert np.all(valid)
    np.testing.assert_array_equal(resumed, traces[-1])
    output = os.environ.get("CELLS_COMPONENT_EVIDENCE")
    if output:
        path = Path(output)
        path.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            path / "redistribution-relaxation.npz",
            initial=amount,
            potential_V=potential,
            exact=exact,
            candidates=np.stack(traces),
        )
        (path / "redistribution-relaxation.json").write_text(
            json.dumps(
                {
                    "law": model.LAW_ID,
                    "duration_s": 2.0,
                    "step_counts": [40, 80, 160],
                    "max_absolute_errors_fmol": errors,
                    "refinement_ratios": ratios.tolist(),
                    "same_process_split_restart_exact": True,
                    "scope": "isolated prescribed-field operator; tissue/GPU qualification pending",
                },
                indent=2,
            )
            + "\n"
        )
