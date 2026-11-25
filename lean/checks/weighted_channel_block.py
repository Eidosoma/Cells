"""Check FR-51's exact blocker identities on synthetic cases using the native CPU clamp."""

import json
from decimal import Decimal

import jax
import jax.numpy as jnp
import numpy as np
from validation.fr51 import closed_forms, engine

from cells.laws.channels import open_channel_block as block_law


def check_relative(actual, expected):
    """Use the registered relative tolerance, with exact agreement for a zero reference."""
    assert np.isfinite(actual).all() and np.isfinite(expected).all()
    np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=0)
    errors = np.divide(actual - expected, expected, out=np.zeros_like(actual), where=expected != 0)
    return float(np.max(np.abs(errors)))


def signed_slope(declaration, temperature, parts):
    """Combine the independent reference's per-mode theta * free into the signed derivative."""
    blocker = declaration["blocker"]
    charge = int(blocker["valence"])
    direction = (1 if blocker["side"] == "outside" else -1) * (1 if charge > 0 else -1)
    modes = declaration["modes"]
    weights = np.array([float(m["weight"]) for m in modes])
    magnitudes = np.array(
        [
            float(m["effective_valence"])
            if "effective_valence" in m
            else abs(charge) * float(m["electrical_distance"])
            for m in modes
        ]
    )
    inverse_thermal = float(closed_forms.F / (closed_forms.R * Decimal(temperature)))
    return (weights * magnitudes) @ parts * (direction * inverse_thermal / weights.sum())


def clamp_case(case, spec, grid):
    name = case["id"]
    reversal = closed_forms.reversal(name)
    dv = Decimal("0.0005")
    near_reversal = (reversal - dv, reversal, reversal + dv)
    points = sorted(set(grid).union(v for v in near_reversal if grid[0] <= v <= grid[-1]))
    reference = closed_forms.case_values(name, points)
    _, state, control, layout, _ = engine.world(name)
    volts = np.array(points, dtype=np.float64)
    _, _, terms = engine.program(name)(state, control, layout, volts)
    assert np.asarray(terms.block.valid).all()
    fraction = np.asarray(terms.block.u)[:, 0]
    slope = np.asarray(terms.block.slope)[:, 0]
    current_bound = np.asarray(terms.voltage_term_S)[:, 0]

    assert np.all((0 <= fraction) & (fraction <= 1))
    fraction_error = check_relative(fraction, reference["u"])
    declaration = spec["blocks"][case["block"]]
    signed = signed_slope(declaration, spec["constants"]["T_K"], reference["slope_part"])
    slope_error = check_relative(slope, np.abs(signed))
    if Decimal(declaration["blocker"]["concentration_mM"]) == 0:
        assert np.all(fraction == 1) and np.all(slope == 0)
    current_slope = np.abs(reference["dI"])
    assert np.isfinite(current_bound).all() and np.isfinite(current_slope).all()
    assert np.all(current_bound >= current_slope * (1 - 1e-12))
    ratios = np.divide(
        current_slope, current_bound, out=np.zeros_like(current_slope), where=current_bound > 0
    )
    return dict(
        case=name,
        points=len(points),
        modes=len(declaration["modes"]),
        min_free=float(fraction.min()),
        max_free=float(fraction.max()),
        max_relative_fraction_error=fraction_error,
        max_relative_block_slope_error=slope_error,
        max_current_slope_over_bound=float(ratios.max()),
    )


def four_mode_control():
    """Test all four slots and an admitted weight sum slightly above one using autodiff."""
    weights = jnp.asarray([0.1, 0.2, 0.3, 0.4 + 2 * np.spacing(1.0)])
    k0 = jnp.asarray([0.4, 0.02, 0.7, 6.0])
    steepness = jnp.asarray([-1.0, -4.0, 0.0, -2.0])

    def unblocked(v):
        k = block_law.dissociation(k0, steepness, v, 310.0, xp=jnp)
        theta, free = block_law.fractions(0.2, k)
        return (
            block_law.unblocked_fraction(weights, free),
            block_law.slope(weights, steepness, 310.0, theta, free, xp=jnp),
        )

    volts = jnp.linspace(-0.120, 0.060, 37)
    derivative, bound = jax.jit(jax.vmap(jax.grad(unblocked, has_aux=True)))(volts)
    assert np.all(np.asarray(derivative) < 0)
    return dict(
        points=int(volts.size),
        weight_sum=float(weights.sum()),
        max_relative_block_slope_error=check_relative(
            np.asarray(bound), np.abs(np.asarray(derivative))
        ),
    )


if __name__ == "__main__":
    assert jax.config.x64_enabled and jax.default_backend() == "cpu"
    spec = engine.spec_of()
    grid_spec = spec["voltage_grid_V"]
    start, step = Decimal(grid_spec["start"]), Decimal(grid_spec["step"])
    grid = [start + k * step for k in range(grid_spec["count"])]
    cases = [clamp_case(c, spec, grid) for c in spec["cases"] if c["block"]]
    print(json.dumps(dict(cases=cases, four_modes=four_mode_control()), indent=2, allow_nan=False))
