"""The emulator's constant-explicit laws equal the engine laws bitwise with CODATA F and R."""

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.coupling.selective import selective_flux
from cells.processes import electrochemistry, er_calcium, kinetic_pump, plasma_calcium
from validation.betse.emulator import laws

CODATA = laws.QUALIFIED


def inputs(seed, size=64):
    rng = np.random.default_rng(seed)
    pump = kinetic_pump.Parameters(
        rng.uniform(0, 5, size), *(rng.uniform(0.05, 20, size) for _ in range(6)),
        rng.uniform(-45e3, -30e3, size),
    )  # fmt: skip
    return (
        rng.uniform(1, 150, size),
        rng.uniform(1, 150, size),
        rng.uniform(-0.1, 0.05, size),
        rng.uniform(280, 320, size),
        pump,
    )


@pytest.mark.parametrize("xp", [np, jnp], ids=["numpy", "jax"])
def test_codata_variant_equals_engine_laws_bitwise(xp):
    jax.config.update("jax_enable_x64", True)
    ci, co, v, t, pump = inputs(3)
    area, perm, mult = 1e-10, 2e-9, 0.7
    pairs = [
        (
            electrochemistry.electrochemical_potential(ci, co, v, 1, t, xp=xp),
            laws.electrochemical_potential(ci, co, v, 1, t, CODATA, xp=xp),
        ),
        (
            electrochemistry.ghk_leak(ci, co, v, -1, t, area, perm, mult, xp=xp),
            laws.ghk_leak(ci, co, v, -1, t, area, perm, mult, CODATA, xp=xp),
        ),
        (
            selective_flux(ci, co, v, 1, t, area, perm, 0.0, 1.0, mult, xp=xp),
            laws.selective_flux(ci, co, v, 1, t, area, perm, 0.0, 1.0, mult, CODATA, xp=xp),
        ),
    ]
    mu_na = laws.electrochemical_potential(ci, co, v, 1, t, CODATA, xp=xp)
    mu_k = laws.electrochemical_potential(co, ci, v, 1, t, CODATA, xp=xp)
    for engine, emulator in zip(
        kinetic_pump.kinetics(ci, co, mu_na, mu_k, t, pump, 0.8, xp=xp),
        laws.pump_kinetics(ci, co, mu_na, mu_k, t, pump, 0.8, CODATA, xp=xp),
        strict=True,
    ):
        pairs.append((engine, emulator))
    pairs.append(
        (
            kinetic_pump.domain_valid(ci, co, mu_na, mu_k, t, pump, 0.8, xp=xp),
            laws.pump_domain_valid(ci, co, mu_na, mu_k, t, pump, 0.8, CODATA, xp=xp),
        )
    )
    for engine, emulator in pairs:
        np.testing.assert_array_equal(np.asarray(emulator), np.asarray(engine))


def test_betse_constants_change_only_through_f_and_r():
    ci, co, v, t, _ = inputs(5)
    betse = laws.default_world("betse")
    flux = laws.ghk_leak(ci, co, v, 1, t, 1e-10, 2e-9, 1.0, betse, xp=np)
    scaled_t = (
        t * betse.gas_J_mol_K / betse.faraday_C_mol * CODATA.faraday_C_mol / CODATA.gas_J_mol_K
    )
    np.testing.assert_allclose(
        flux, laws.ghk_leak(ci, co, v, 1, scaled_t, 1e-10, 2e-9, 1.0, CODATA, xp=np), rtol=1e-12
    )
    assert laws.default_world("codata")[1:3] == CODATA[1:3]


def calcium_inputs(seed, size=64):
    rng = np.random.default_rng(seed)
    pump = er_calcium.PumpParameters(
        rng.uniform(0, 1, size), rng.uniform(1e-4, 1e-2, size), rng.uniform(0.1, 1, size),
        *(rng.uniform(0.05, 3, size) for _ in range(3)), rng.uniform(-45e3, -30e3, size),
    )  # fmt: skip
    return (
        rng.uniform(1e-5, 1e-3, size),
        rng.uniform(0.5, 3.0, size),
        rng.uniform(-0.1, 0.05, size),
        rng.uniform(280, 320, size),
        pump,
    )


@pytest.mark.parametrize("xp", [np, jnp], ids=["numpy", "jax"])
def test_codata_calcium_pump_equals_the_engine_kernel_bitwise(xp):
    jax.config.update("jax_enable_x64", True)
    ci, co, v, t, pump = calcium_inputs(11)
    engine = plasma_calcium.pump_rates(ci, co, v, t, pump, 0.8, xp=xp)
    emulator = laws.calcium_pump_kinetics(ci, co, v, t, pump, 0.8, CODATA, xp=xp)
    for a, b in zip(engine, emulator, strict=True):
        np.testing.assert_array_equal(np.asarray(b), np.asarray(a))


def test_betse_calcium_pump_is_pumpcaatp_per_unit_area():
    """BETSE 1.5 pumpCaATP: f = -alpha frwd (1 - Q/Keq), numeric-mM quotient, into cell +."""
    ci, co, v, t, pump = calcium_inputs(13)
    betse = laws.default_world("betse")
    f, r = betse.faraday_C_mol, betse.gas_J_mol_K
    area = 2e-10
    alpha = pump.capacity_fmol_per_s / area / 1e15  # mol / (m^2 s)
    q = pump.adp_mM * pump.pi_mM * co / (pump.atp_mM * ci)
    keq = np.exp(-(pump.delta_g0_J_per_mol / (r * t) - 2 * (f * v / (r * t))))
    forward = (ci / pump.km_ca_mM) * (pump.atp_mM / pump.km_atp_mM)
    forward = forward / ((1 + ci / pump.km_ca_mM) * (1 + pump.atp_mM / pump.km_atp_mM))
    flux = -alpha * forward * (1 - q / keq)
    cycles, _, _ = laws.calcium_pump_kinetics(ci, co, v, t, pump, 1.0, betse, xp=np)
    np.testing.assert_allclose(-cycles / area / 1e15, flux, rtol=1e-12)
