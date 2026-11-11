"""resolved_pump_water@1 device checks and vectorized worlds.

On a water-on trajectory the device checks (core/vector_windows.py hooks)
pass every row and their diagnostics match the host's to rounding. Faults in
the water ledgers (a water transfer booking, a bath-work booking, negative
water heat) fail the same checks on the host and on the device, with the water
messages. A vmap batch of heterogeneous water-on worlds reproduces each world's
own windowed run to rounding (1e-12 of each field, as for resolved_pump_tissue@3),
and ionic_worlds@1 admits the model with world_batching "vmap".
"""

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core.batch import BatchSpec, WorldSpec
from cells.core.errors import NumericalError
from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.core.vector_windows import run_vector_windowed
from cells.core.windows import WindowPolicy, run_windowed
from cells.ensemble import ionic as ensemble
from cells.models import surface_pump_water as model
from cells.numerics import surface_imex as imex
from validation.tissue import pump_water_fixtures as fixtures

AQUAPORIN_PF = 5e-4


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def definition(state="D", *, scale=1.0, end=0.1, pf=AQUAPORIN_PF):
    raw = fixtures.heredity_cell(state, dt=1e-3, end_time=end, solver=imex.ARS222_ID)
    raw["experiment"]["observation_times"] = [0.0, end / 2, end]
    for c in raw["model"]["channels"]:
        c["max_permeability_m_per_s"] *= scale
    return parse_spec(fixtures.with_water(raw, pf_m_s=pf * scale))


@pytest.fixture(scope="module")
def trajectory():
    spec = definition()
    return spec, run(spec)


@pytest.fixture(scope="module")
def slow_trajectory():
    """H cell at the default permeability: the water heat per step is far below the
    energy ledger's bound, so a falling heat is caught by the dissipation check alone."""
    spec = definition("H", end=0.3, pf=fixtures.NO_AQUAPORIN_PF_M_S)
    return spec, run(spec)


def device(history, spec, row):
    _, p = model.initial_values(spec)
    p = jax.tree.map(jnp.asarray, p)
    constants = model.device_check_constants(spec)
    rows = [model.STATE_TYPE(*(jnp.asarray(v[i]) for v in history)) for i in (row - 1, row)]
    bits, values = model.device_checks(rows[0], rows[1], p, constants, row)
    failed = {k for k, bit in zip(model.DEVICE_CHECKS, np.asarray(bits), strict=True) if bit}
    return failed, dict(zip(model.DEVICE_DIAGNOSTICS, map(float, np.asarray(values)), strict=True))


def test_device_checks_pass_and_match_the_host(trajectory):
    spec, result = trajectory
    history = result.history
    steps = np.arange(len(result.times))
    host = model.check_values(history, spec, steps=steps)
    maxima = {k: 0.0 for k in model.DEVICE_DIAGNOSTICS}
    for row in range(1, len(result.times)):
        failed, values = device(history, spec, row)
        assert failed == set(), row
        maxima = {k: max(maxima[k], values[k]) for k in maxima}
    assert set(maxima) == set(host)
    for key, value in host.items():
        assert abs(maxima[key] - value) <= 1e-6 * max(abs(value), 1e-30) + 1e-24, key


FAULTS = {
    "water_transfer": (
        lambda s, i: s._replace(water_transferred_pL=s.water_transferred_pL.at[i, 0].add(1e-9)),
        "Resolved pump water accounting failed: water_local",
        {"water_local", "water_outside"},
    ),
    "bath_work": (
        lambda s, i: s._replace(bath_water_work_pJ=s.bath_water_work_pJ.at[i, 0].add(1e-6)),
        "Resolved pump water accounting failed: bath_water_work",
        {"bath_water_work"},
    ),
    # The water heat falls by 2e-12 pJ in one step: dissipation, the energy ledger holds.
    "water_heat": (
        lambda s, i: s._replace(
            water_dissipated_energy_pJ=s.water_dissipated_energy_pJ.at[i, 0].set(
                s.water_dissipated_energy_pJ[i - 1, 0] - 2e-12
            )
        ),
        "Resolved pump dissipation cannot be negative or decrease",
        {"dissipation"},
    ),
}


@pytest.mark.parametrize("fault", FAULTS)
def test_water_faults_fail_the_same_checks_on_host_and_device(trajectory, slow_trajectory, fault):
    spec, result = slow_trajectory if fault == "water_heat" else trajectory
    change, message, checks = FAULTS[fault]
    row = 200 if fault == "water_heat" else 40
    history = model.STATE_TYPE(*(jnp.asarray(v) for v in result.history))
    bad = model.STATE_TYPE(*(np.asarray(v) for v in change(history, row)))
    with pytest.raises(NumericalError) as error:
        model.check_values(bad, spec, steps=np.arange(len(result.times)))
    assert str(error.value) == message
    failed, _ = device(bad, spec, row)
    assert failed == checks
    if fault == "water_transfer":
        assert model.device_failure_message("water_local") == message


def cohort(specs):
    worlds = tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs))
    return BatchSpec(worlds, len(worlds), 10**6, 2**31)


def test_vmap_batch_reproduces_single_worlds():
    specs = [definition(state, scale=1 + 0.1 * i) for i, state in enumerate(("D", "H", "D"))]
    policy = WindowPolicy(40, "checkpoints")
    batch = run_vector_windowed(cohort(specs), policy)
    for world in cohort(specs).worlds:
        own = run_windowed(world.simulation, policy).final.state
        mine = batch.worlds[world.world_id].final.state
        for name, a, b in zip(model.STATE_TYPE._fields, mine, own, strict=True):
            a, b = np.asarray(a), np.asarray(b)
            assert np.max(np.abs(a - b), initial=0) <= 1e-12 * np.max(np.abs(b), initial=0), name
        assert np.any(np.asarray(mine.volume_increment_pL))


def test_ionic_worlds_admit_the_model_with_vmap():
    simulation = definition().to_dict()
    spec = ensemble.parse_spec(
        dict(model=ensemble.MODEL_ID, simulation=simulation, worlds=2, world_batching="vmap")
    )
    assert spec.world_batching == "vmap"
    assert spec.simulation.to_dict()["model"]["id"] == "resolved_pump_water@1"
