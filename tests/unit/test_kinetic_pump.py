"""Local-law tests; no historical artifacts, native BETSE or model registry edits."""

import math
from decimal import Decimal, localcontext

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.processes import kinetic_pump as pump
from cells.processes.electrochemistry import F, R

BASE = pump.Parameters(0.1, 1.5, 0.1, 0.1, 12.0, 0.2, 0.5, -37000.0)
TEMPERATURE = 298.15


def potentials(voltage=-0.08):
    return (
        R * TEMPERATURE * math.log(12.0 / 140.0) + F * voltage,
        R * TEMPERATURE * math.log(140.0 / 4.0) + F * voltage,
    )


def oracle(na, k, mu_na, mu_k, temperature, p, availability):
    with localcontext() as context:
        context.prec = 80
        d = Decimal
        p = pump.Parameters(*(d(v) for v in p))
        rt = d(R) * d(temperature)
        drive = p.delta_g0_J_mol + rt * (p.adp_mM * p.pi_mM / (1000 * p.atp_mM)).ln()
        energy = drive - 3 * d(mu_na) + 2 * d(mu_k)
        saturation = (
            d(na) ** 3
            / (p.km_na_mM**3 + d(na) ** 3)
            * d(k) ** 2
            / (p.km_k_mM**2 + d(k) ** 2)
            * p.atp_mM
            / (p.km_atp_mM + p.atp_mM)
        )
        cycles = p.capacity_fmol_s * d(availability) * saturation * (1 - (energy / rt).exp())
        return np.array([float(v) for v in (cycles, energy, drive)])


@pytest.mark.parametrize("voltage", [-0.4, -0.35, -0.12, -0.08, 0.0, 0.06])
def test_forward_reverse_scalar_law_and_second_law(voltage):
    mu = potentials(voltage)
    assert pump.domain_valid(12.0, 4.0, *mu, TEMPERATURE, BASE, 1.0, xp=np)
    actual = pump.kinetics(12.0, 4.0, *mu, TEMPERATURE, BASE, 1.0, xp=np)
    np.testing.assert_allclose(
        actual, oracle(12.0, 4.0, *mu, TEMPERATURE, BASE, 1.0), atol=2e-11, rtol=2e-13
    )
    assert -actual.cycles_fmol_s * actual.cycle_free_energy_J_mol >= 0


@pytest.mark.parametrize("engine", ["numpy", "eager", "jit"])
def test_broadcast_worlds_and_membranes(engine):
    xp = np if engine == "numpy" else jnp
    p = pump.Parameters(*(xp.asarray(value) for value in BASE))
    p = p._replace(capacity_fmol_s=xp.asarray([[0.1], [0.2]]))
    na = xp.asarray([[6.0, 12.0, 24.0]])
    availability = xp.asarray([[1.0, 0.5, 0.0]])
    args = (na, 4.0, *potentials(), TEMPERATURE, p, availability)

    def evaluate(*args):
        return pump.kinetics(*args, xp=xp)

    def domain(*args):
        return pump.domain_valid(*args, xp=xp)

    actual = jax.jit(evaluate)(*args) if engine == "jit" else evaluate(*args)
    valid = jax.jit(domain)(*args) if engine == "jit" else domain(*args)
    assert np.asarray(valid).shape == (2, 3) and np.asarray(valid).all()
    assert actual.cycles_fmol_s.shape == (2, 3)
    np.testing.assert_allclose(actual.cycles_fmol_s[1], 2 * actual.cycles_fmol_s[0], rtol=1e-13)
    assert np.array_equal(np.asarray(actual.cycles_fmol_s[:, 2]), [0.0, 0.0])
    for world in range(2):
        for lane in range(3):
            expected = oracle(
                float(na[0, lane]),
                4.0,
                *potentials(),
                TEMPERATURE,
                BASE._replace(capacity_fmol_s=0.1 * (world + 1)),
                float(availability[0, lane]),
            )[0]
            assert actual.cycles_fmol_s[world, lane] == pytest.approx(
                expected, rel=2e-13, abs=1e-15
            )


@pytest.mark.parametrize(
    "change,value",
    [
        ("na", 0.0),
        ("na", -1.0),
        ("na", math.nan),
        ("k", 0.0),
        ("mu_na", math.inf),
        ("mu_na", 1e308),
        ("temperature", 199.0),
        ("temperature", 401.0),
        ("temperature", 1e308),
        ("temperature", math.nan),
        ("atp_mM", 0.0),
        ("adp_mM", math.nan),
        ("pi_mM", math.inf),
        ("km_na_mM", -1.0),
        ("delta_g0_J_mol", 1e308),
        ("capacity_fmol_s", -1.0),
        ("availability", 1.1),
        ("availability", math.nan),
    ],
)
def test_invalid_domain_rejected_even_with_blocked_pump(change, value):
    fields = dict(
        na=12.0,
        k=4.0,
        mu_na=potentials()[0],
        mu_k=potentials()[1],
        temperature=TEMPERATURE,
        availability=0.0,
    )
    p = BASE
    if change in fields:
        fields[change] = value
    else:
        p = p._replace(**{change: value})
    args = (
        *(fields[name] for name in ("na", "k", "mu_na", "mu_k", "temperature")),
        p,
        fields["availability"],
    )
    with np.errstate(all="raise"):
        assert not pump.domain_valid(*args, xp=np)


def test_neutral_inactive_lane_has_no_effect_or_nan():
    p = pump.Parameters(
        *(
            np.asarray([v, neutral])
            for v, neutral in zip(BASE, (0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0), strict=True)
        )
    )
    args = (
        np.array([12.0, 1.0]),
        np.array([4.0, 1.0]),
        np.array([potentials()[0], 0.0]),
        np.array([potentials()[1], 0.0]),
        TEMPERATURE,
        p,
        np.ones(2),
    )
    assert pump.domain_valid(*args, xp=np).all()
    values = pump.kinetics(*args, xp=np)
    assert np.isfinite(values).all() and values.cycles_fmol_s[1] == 0
    assert values.cycles_fmol_s[0] == pytest.approx(
        pump.kinetics(12.0, 4.0, *potentials(), TEMPERATURE, BASE, 1.0, xp=np).cycles_fmol_s
    )


def test_stall_and_positive_interior_gradient():
    # Exact zero-drive arithmetic fixture. Two large potentials equal to the
    # drive cancel in real arithmetic, but need not cancel exactly in float64.
    p = BASE._replace(atp_mM=1.0, adp_mM=1.0, pi_mM=1000.0, delta_g0_J_mol=0.0)
    mu_na, mu_k = 0.0, 0.0
    args = (12.0, 4.0, mu_na, mu_k, TEMPERATURE, p, 1.0)
    assert pump.kinetics(*args, xp=np).cycles_fmol_s == 0
    derivative = jax.jit(
        jax.grad(
            lambda sodium_mu: (
                pump.kinetics(12.0, 4.0, sodium_mu, mu_k, TEMPERATURE, p, 1.0).cycles_fmol_s
            )
        )
    )(mu_na)
    saturation = 0.5 / (1 + (0.2 / 4.0) ** 2) / (1 + 0.5 / p.atp_mM)
    assert float(derivative) == pytest.approx(3 * 0.1 * saturation / (R * TEMPERATURE), rel=1e-12)


def test_log_rate_recovers_representable_tiny_saturation_large_capacity():
    p = BASE._replace(capacity_fmol_s=1e300, km_na_mM=1.0)
    args = (1e-120, 4.0, 0.0, 0.0, TEMPERATURE, p, 1.0)
    actual = pump.kinetics(*args, xp=np)
    assert pump.domain_valid(*args, xp=np)
    assert actual.cycles_fmol_s > 0
    np.testing.assert_allclose(actual, oracle(*args), rtol=3e-13, atol=0)


def test_stoichiometry_does_not_add_a_second_charge_source():
    rate = pump.kinetics(12.0, 4.0, *potentials(), TEMPERATURE, BASE, 1.0, xp=np)
    ions = np.asarray([pump.SODIUM_PER_CYCLE, pump.POTASSIUM_PER_CYCLE, 0]) * rate.cycles_fmol_s
    assert ions.sum() == pytest.approx(-rate.cycles_fmol_s)
    assert -0.001 * rate.cycles_fmol_s * rate.cycle_free_energy_J_mol >= 0
    assert -0.001 * rate.cycles_fmol_s * rate.chemical_drive_J_mol > 0


def test_jax_vmap_keeps_parameters_as_dynamic_numeric_leaves():
    p = pump.Parameters(*(jnp.asarray([v, v]) for v in BASE))
    apply = jax.jit(
        jax.vmap(
            lambda parameters: pump.kinetics(12.0, 4.0, *potentials(), TEMPERATURE, parameters, 1.0)
        )
    )
    first = apply(p)
    second = apply(p._replace(capacity_fmol_s=2 * p.capacity_fmol_s))
    np.testing.assert_allclose(second.cycles_fmol_s, 2 * first.cycles_fmol_s, rtol=1e-13)
