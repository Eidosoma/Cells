"""The @3 entity adapter's derived field arrays (design §3.3, §3.7, §3.8).

refresh_field selects the bound arrays bitwise when no capacitance or mask
changed; otherwise it recomputes the capacitor reduction and its Cholesky factor
(on the device or the host) and agrees with surface_field.bind on the changed
definition to rounding (the host accumulates patch capacitances sequentially).
A definition with floating capacitor components is refused for a field-input
provider. No S1 operator provides a field input, so this path is not exercised
in a run yet (division's insertion operator, S2, is its first user).
"""

import copy

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core.specs import ConfigError, parse_spec
from cells.models import pump_composite_adapter as pump3
from cells.models import surface_pump_v3
from cells.numerics import surface_imex as imex
from validation.tissue import cell_replacement_fixtures as fx
from validation.tissue import surface_pump_v3_fixtures as v3fx


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def layout(raw):
    return pump3.inner_layout(surface_pump_v3.initial_values(parse_spec(raw))[1])


def sheet():
    raw = fx.heredity_sheet(1, 0, end_time=0.01)
    raw["experiment"]["observation_times"] = [0.0, 0.01]
    return raw


def test_unchanged_inputs_select_the_bound_arrays_bitwise():
    q = layout(sheet())
    for xp in (np, jnp):
        refreshed = pump3.refresh_field(jax.tree.map(xp.asarray, q), q, xp=xp)
        for name in pump3.DERIVED_FIELD_ARRAYS:
            a, b = np.asarray(getattr(refreshed, name)), np.asarray(getattr(q, name))
            assert a.dtype == b.dtype and a.tobytes() == b.tobytes(), name


def test_recomputed_arrays_are_the_host_binding():
    q = layout(sheet())
    for xp in (np, jnp):
        arrays, finite = pump3.field_arrays(jax.tree.map(xp.asarray, q), xp=xp)
        assert bool(finite)
        for name, value in arrays.items():
            np.testing.assert_allclose(
                np.asarray(value, dtype=float),
                np.asarray(getattr(q, name), dtype=float),
                rtol=1e-14,
                atol=0,
                err_msg=name,
            )


def test_a_changed_capacitance_refreshes_to_the_changed_binding():
    raw = sheet()
    changed = copy.deepcopy(raw)
    changed["model"]["membranes"][2]["capacitance_F"] *= 1.25
    bound, target = layout(raw), layout(changed)
    q = bound._replace(membrane_capacitance=target.membrane_capacitance)
    for xp, refresh in ((np, pump3.refresh_field), (jnp, jax.jit(pump3.refresh_field))):
        if xp is np:
            refreshed = refresh(q, bound, xp=np)
        else:
            refreshed = refresh(jax.tree.map(jnp.asarray, q), jax.tree.map(jnp.asarray, bound))
        for name in pump3.DERIVED_FIELD_ARRAYS:
            np.testing.assert_allclose(
                np.asarray(getattr(refreshed, name), dtype=float),
                np.asarray(getattr(target, name), dtype=float),
                rtol=1e-14,
                atol=1e-300,
                err_msg=name,
            )


def test_floating_components_are_refused_for_a_field_input_provider():
    pump3.check_field_inputs(surface_pump_v3.initial_values(parse_spec(sheet()))[1])
    raw = v3fx.definition("release", solver=imex.ARS222_ID)
    p = surface_pump_v3.initial_values(parse_spec(raw))[1]
    with pytest.raises(ConfigError, match="reservoir"):
        pump3.check_field_inputs(p)
