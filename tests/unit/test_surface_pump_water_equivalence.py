"""resolved_pump_water@1 with every water route closed is resolved_pump_tissue@3, bitwise.

"Off" is water declared with every route closed (availability 0, or hydraulic
permeability 0): the full split step runs, every water flow is an exact zero,
the volumes stay at their declared values and @3's own checked step sees
exactly @3's inputs. On the heredity single cell (from H and from D) and the
seven-cell gated held-bath sheet, with IMEX Euler and ARS(2,2,2) at 1 ms over
1,200 steps containing a NaV1.2 and a Na/K pump schedule change, every @3 state
field, observation and check diagnostic equals @3's run bitwise: compiled with
default XLA flags, uncompiled (jit off, over a shorter horizon) and as vmap
batches. The water fields stay exactly zero. Row checks: a junction-heat fault,
a ledger fault and a domain fault give @3's verdict and message, on the host
and on the device, because the water model calls @3's own check functions.
The 825-node world is checked by validation/tissue/pump_water_equivalence.py
(detached; it runs longer than a unit test).
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
from cells.core.windows import WindowPolicy
from cells.models import surface_pump_v3, surface_pump_water
from cells.numerics import surface_imex as imex
from validation.tissue import pump_water_fixtures as fixtures

SOLVERS = (imex.EULER_ID, imex.ARS222_ID)
WORLDS = {
    "cell_H": lambda **k: fixtures.heredity_cell("H", **k),
    "cell_D": lambda **k: fixtures.heredity_cell("D", **k),
    "sheet7": fixtures.gated_sheet,
}
WATER_FIELDS = tuple(surface_pump_water.WATER_STATE_AXES)


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def pair(world, solver, *, end=1.2, changes=((0.4, 0.5), (0.6, 0.8)), jit=True, closed="off"):
    raw = WORLDS[world](dt=1e-3, end_time=end, solver=solver)
    raw = fixtures.scheduled(raw, channel_change=changes[0], pump_change=changes[1])
    raw["experiment"]["observation_times"] = [0.0, round(end / 3, 3), round(end / 2, 3), end]
    raw["execution"]["jit"] = jit
    water = (
        fixtures.with_water(raw, availability=0.0)
        if closed == "off"
        else fixtures.with_water(raw, pf_m_s=0.0)
    )
    return parse_spec(raw), parse_spec(water)


def assert_reproduces(reference, result):
    np.testing.assert_array_equal(result.times, reference.times)
    for key in surface_pump_v3.STATE_TYPE._fields:
        a, b = np.asarray(getattr(result.history, key)), np.asarray(getattr(reference.history, key))
        assert a.shape == b.shape and np.array_equal(a, b), key
    for key in WATER_FIELDS:
        assert not np.any(np.asarray(getattr(result.history, key))), key
    for key, value in vars(reference.observations).items():
        assert np.array_equal(np.asarray(getattr(result.observations, key)), value), key
    for key, value in reference.diagnostics.items():
        if key.startswith("max_"):
            assert result.diagnostics[key] == value, key


@pytest.mark.parametrize("solver", SOLVERS)
@pytest.mark.parametrize("world", WORLDS)
def test_closed_water_reproduces_resolved_pump_tissue_3_compiled(world, solver):
    reference, water = pair(world, solver)
    assert_reproduces(run(reference), run(water))


def test_zero_permeability_reproduces_resolved_pump_tissue_3():
    reference, water = pair("sheet7", imex.ARS222_ID, closed="lp")
    assert_reproduces(run(reference), run(water))


@pytest.mark.parametrize("world", WORLDS)
def test_closed_water_reproduces_resolved_pump_tissue_3_uncompiled(world):
    reference, water = pair(
        world, imex.ARS222_ID, end=0.012, changes=((0.004, 0.5), (0.007, 0.8)), jit=False
    )
    assert_reproduces(run(reference), run(water))


def batch(specs):
    worlds = tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs))
    return BatchSpec(worlds, len(worlds), 10**6, 2**31)


def test_closed_water_vmap_batch_reproduces_resolved_pump_tissue_3_batch():
    references, waters = [], []
    for i, world in enumerate(("cell_H", "cell_D", "cell_H")):
        raw = WORLDS[world](dt=1e-3, end_time=0.3, solver=imex.ARS222_ID)
        raw = fixtures.scheduled(raw, channel_change=(0.1, 0.5 + 0.1 * i), pump_change=(0.2, 0.8))
        raw["experiment"]["observation_times"] = [0.0, 0.15, 0.3]
        for c in raw["model"]["channels"]:
            c["max_permeability_m_per_s"] *= 1 + 0.05 * i
        references.append(parse_spec(raw))
        waters.append(parse_spec(fixtures.with_water(raw, availability=0.0)))
    policy = WindowPolicy(100, "checkpoints")
    a, b = (
        run_vector_windowed(batch(references), policy),
        run_vector_windowed(batch(waters), policy),
    )
    for world in a.worlds:
        reference, result = a.worlds[world], b.worlds[world]
        for key in surface_pump_v3.STATE_TYPE._fields:
            x = np.asarray(getattr(result.final.state, key))
            y = np.asarray(getattr(reference.final.state, key))
            assert np.array_equal(x, y), (world, key)
        for key in WATER_FIELDS:
            assert not np.any(np.asarray(getattr(result.final.state, key))), key
        for key, value in reference.diagnostics.items():
            if key.startswith("max_"):
                assert result.diagnostics[key] == value, (world, key)


# --------------------------------------------------------------- row checks


@pytest.fixture(scope="module")
def sheet_rows():
    reference, water = pair("sheet7", imex.ARS222_ID, end=0.05, changes=((0.01, 0.5), (0.02, 0.8)))
    return reference, run(reference), water, run(water)


FAULTS = {
    # A junction's booked heat below zero (the ARS(2,2,2) weight case): dissipation.
    "junction_heat": (
        1,
        lambda s, i: s._replace(
            junction_dissipated_energy_pJ=s.junction_dissipated_energy_pJ.at[i, 0].set(-2e-12)
        ),
    ),
    "membrane_transfer": (
        20,
        lambda s, i: s._replace(membrane_transferred=s.membrane_transferred.at[i, 0, 0].add(1e-6)),
    ),
    "gate": (20, lambda s, i: s._replace(channel_gate=s.channel_gate.at[i, 0, 0].set(1.5))),
}


def corrupt(history, fault, row):
    history = type(history)(*(jnp.asarray(v) for v in history))
    return type(history)(*(np.asarray(v) for v in FAULTS[fault][1](history, row)))


def host_message(model, history, spec, steps):
    try:
        model.check_values(history, spec, steps=steps)
    except NumericalError as error:
        return str(error)
    return None


@pytest.mark.parametrize("fault", FAULTS)
def test_row_checks_give_resolved_pump_tissue_3_verdicts(sheet_rows, fault):
    reference_spec, reference, water_spec, water = sheet_rows
    row = FAULTS[fault][0]
    steps = np.arange(len(reference.times))
    bad_reference = corrupt(reference.history, fault, row)
    bad_water = corrupt(water.history, fault, row)
    expected = host_message(surface_pump_v3, bad_reference, reference_spec, steps)
    assert expected is not None
    assert host_message(surface_pump_water, bad_water, water_spec, steps) == expected
    # Device: the same failing checks, by name, at the corrupted row.
    _, p3 = surface_pump_v3.initial_values(reference_spec)
    _, pw = surface_pump_water.initial_values(water_spec)

    def failed(model, history, p, spec):
        constants = model.device_check_constants(spec)
        rows = [type(history)(*(jnp.asarray(v[i]) for v in history)) for i in (row - 1, row)]
        bits, _ = model.device_checks(
            rows[0], rows[1], jax.tree.map(jnp.asarray, p), constants, row
        )
        return {
            name for name, bit in zip(model.DEVICE_CHECKS, np.asarray(bits), strict=True) if bit
        }

    assert failed(surface_pump_water, bad_water, pw, water_spec) == failed(
        surface_pump_v3, bad_reference, p3, reference_spec
    )
    clean = failed(surface_pump_water, water.history, pw, water_spec)
    assert clean == set()


def test_check_diagnostics_are_resolved_pump_tissue_3s(sheet_rows):
    reference_spec, reference, water_spec, water = sheet_rows
    steps = np.arange(len(reference.times))
    a = surface_pump_v3.check_values(reference.history, reference_spec, steps=steps)
    b = surface_pump_water.check_values(water.history, water_spec, steps=steps)
    for key, value in a.items():
        assert b[key] == value, key
    assert set(b) - set(a) == {"max_" + k for k in surface_pump_water.WATER_DIAGNOSTICS}
