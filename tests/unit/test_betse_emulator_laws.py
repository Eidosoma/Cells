"""The emulator's constant-explicit laws equal the engine laws bitwise with CODATA F and R."""

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.coupling.selective import selective_flux
from cells.processes import electrochemistry, kinetic_pump
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
