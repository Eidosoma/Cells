"""k_anion_symport_mass_action@1: KCC-type electroneutral K+/anion symport.

Thermodynamics: the heat 1e-3 J A is never negative, J vanishes exactly where
the concentration products are equal and changes sign across that point, and
the route carries no current (1 K+ : 1 anion). Volume factor: 1 at the set
volume, exp(0.2) at +20% with s = 1 (Lew et al. 1991), about 5x with s = 0.12
(Kaji 1986's 4-5x). Units: a red-cell flux per cell volume converts to a route
capacity and back. NumPy and JAX agree; invalid inputs fail domain_valid. The
independent reduced reference's transcription (validation/tissue/
pump_water_reference.kcc_cycles) gives the same cycles.
"""

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.processes import k_anion_symport as law
from cells.processes.electrochemistry import R


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def parameters(k=2.5e-7, v_set=0.75, s=1.0):
    return law.Parameters(np.asarray(k), np.asarray(v_set), np.asarray(s))


def test_heat_is_never_negative_and_the_flux_reverses_at_equal_products():
    rng = np.random.default_rng(5)
    c = 10 ** rng.uniform(-1, 2.5, (4, 10000))
    volume = rng.uniform(0.4, 1.5, 10000)
    p = parameters(k=rng.uniform(0, 1e-6, 10000), v_set=0.75, s=rng.uniform(0.05, 2, 10000))
    r = law.rates(*c, volume, 310.0, p, rng.uniform(0, 1, 10000), xp=np)
    assert np.all(r.dissipation_pJ_s >= 0)
    assert np.all(np.sign(r.cycles_fmol_s) * np.sign(r.affinity_J_mol) >= 0)
    # Equal products: no flux, zero affinity; crossing them reverses the flux.
    k_in, a_in, k_out = 140.0, 60.0, 5.0
    a_out = k_in * a_in / k_out
    for scale, sign in ((1.0, 0.0), (0.9, 1.0), (1.1, -1.0)):
        r = law.rates(k_in, a_in, k_out, a_out * scale, 0.75, 310.0, parameters(), 1.0, xp=np)
        assert np.sign(r.cycles_fmol_s) == sign
        assert np.sign(r.affinity_J_mol) == sign
    r = law.rates(k_in, a_in, k_out, a_out, 0.75, 310.0, parameters(), 1.0, xp=np)
    assert r.cycles_fmol_s == 0.0 and abs(r.affinity_J_mol) < 1e-9


def test_affinity_and_flux_values():
    r = law.rates(141.0, 73.0, 5.0, 140.0, 0.75, 310.0, parameters(), 0.5, xp=np)
    assert r.cycles_fmol_s == pytest.approx(2.5e-7 * 0.5 * (141 * 73 - 5 * 140), rel=1e-15)
    assert r.affinity_J_mol == pytest.approx(R * 310 * np.log(141 * 73 / (5 * 140)), rel=1e-14)
    assert r.dissipation_pJ_s == pytest.approx(1e-3 * r.cycles_fmol_s * r.affinity_J_mol)


def test_volume_factor():
    p = parameters(v_set=0.75, s=1.0)
    assert law.volume_factor(0.75, p, xp=np) == 1.0
    assert law.volume_factor(0.9, p, xp=np) == pytest.approx(np.exp(0.2), rel=1e-14)
    steep = parameters(v_set=0.75, s=0.12)
    assert 4.0 < law.volume_factor(0.9, steep, xp=np) < 6.0  # Kaji 1986: 4-5x at 1.2.
    assert law.volume_factor(0.6, steep, xp=np) < 1.0


def test_capacity_from_a_red_cell_flux():
    # Lew et al. 1991 reference: 15 mmol/(L cells h) at K 140 x Cl 95 - K 5 x Cl 140.
    difference = 140 * 95 - 5 * 140
    k = law.capacity_from_flux(15.0, difference, 0.75)
    flux = k * difference  # fmol/s for 0.75 pL
    assert flux / 0.75 * 3600 == pytest.approx(15.0, rel=1e-14)


def test_numpy_and_jax_agree_and_invalid_inputs_fail():
    args = (141.0, 73.0, 5.0, 140.0, 0.9, 310.0, parameters(s=0.12), 0.7)
    a = law.rates(*args, xp=np)
    b = law.rates(*(jnp.asarray(v) if not isinstance(v, tuple) else v for v in args), xp=jnp)
    for x, y in zip(a, b, strict=True):
        np.testing.assert_allclose(np.asarray(y), x, rtol=1e-14)
    good = (141.0, 73.0, 5.0, 140.0, 0.9)
    assert law.domain_valid(*good, parameters(), 1.0, xp=np)
    for bad in (
        (0.0, 73.0, 5.0, 140.0, 0.9),
        (141.0, -1.0, 5.0, 140.0, 0.9),
        (141.0, 73.0, 5.0, np.nan, 0.9),
        (141.0, 73.0, 5.0, 140.0, 0.0),
    ):
        assert not law.domain_valid(*bad, parameters(), 1.0, xp=np)
    assert not law.domain_valid(*good, parameters(s=0.0), 1.0, xp=np)
    assert not law.domain_valid(*good, parameters(k=-1.0), 1.0, xp=np)
    assert not law.domain_valid(*good, parameters(), 1.5, xp=np)
    assert not law.domain_valid(*good, parameters(s=1e-4), 1.0, xp=np)  # exp overflow domain


def test_reference_transcription_gives_the_same_cycles():
    from validation.tissue import pump_water_reference as reference

    rng = np.random.default_rng(9)
    c = 10 ** rng.uniform(-1, 2.5, (4, 1000))
    volume = rng.uniform(0.4, 1.5, 1000)
    k, s, a = rng.uniform(0, 1e-6, 1000), rng.uniform(0.05, 2, 1000), rng.uniform(0, 1, 1000)
    engine = law.rates(*c, volume, 310.0, parameters(k=k, v_set=0.75, s=s), a, xp=np)
    expected = reference.kcc_cycles(
        *c, volume, dict(capacity_fmol_s_mM2=k, set_volume_pL=0.75, steepness=s, availability=a)
    )
    np.testing.assert_allclose(engine.cycles_fmol_s, expected, rtol=1e-13, atol=0)
