"""One compiled shared-stage contract; this does not qualify a trajectory."""

import jax
import numpy as np

from cells.assembly.engine import device_for
from cells.models import surface_cotransport_water as model
from tests.unit.test_surface_cotransport_water import evidence, initial


def test_compiled_complete_rhs_and_actual_control_domain():
    jax.config.update("jax_enable_x64", True)
    _, state, p, control = initial(padded=True)
    state.volume_increment_pL[0] = 0.01
    state.extracellular_volume_increment_pL[0] = -0.01
    state.water_transferred_pL[0] = -0.01
    state.energy_amount_increment_fmol[:, 0] = [-0.0001, 0.0001, 0.0001]
    expected = model.rhs(state, control, p, p.active, xp=np)
    device = device_for("cpu", 0)
    state, control, p = jax.device_put((state, control, p), device)
    stage = jax.jit(lambda y, u, q: model.rhs(y, u, q, q.active))
    predicate = jax.jit(lambda y, u, q: model.control_domain_valid(y, u, q, q.active))
    actual = stage(state, control, p)
    assert bool(predicate(state, control, p))
    for key in model.STATE_TYPE._fields:
        a, b = np.asarray(getattr(actual, key)), np.asarray(getattr(expected, key))
        assert getattr(actual, key).device.platform == "cpu"
        np.testing.assert_allclose(a, b, rtol=3e-10, atol=3e-23 if key.endswith("_C") else 3e-12)
    bad_pool = np.asarray(state.energy_amount_increment_fmol).copy()
    bad_pool[0, 0] = -float(p.energy_initial_amount_fmol[0, 0])
    bad_volume = np.asarray(state.volume_increment_pL).copy()
    bad_volume[0] = float(p.water_minimum_volume_pL[0] - p.volume[0])
    blocked = type(control)(*(v * 0 for v in control))
    cases = (
        (state._replace(energy_amount_increment_fmol=jax.device_put(bad_pool, device)), blocked),
        (state._replace(volume_increment_pL=jax.device_put(bad_volume, device)), blocked),
        (state, control._replace(cotransport=control.cotransport * np.nan)),
        (state, control._replace(water=control.water * np.nan)),
    )
    for bad, ctl in cases:
        before = [np.asarray(v).copy() for v in bad]
        assert not bool(predicate(bad, ctl, p))
        for a, b in zip(bad, before, strict=True):
            np.testing.assert_array_equal(a, b)
    evidence(
        "compiled-stage",
        dict(
            status="passed",
            complete_fields=31,
            scope="CPU JIT RHS and actual-control domain only; no trajectory or GPU qualification",
            rejected_exhausted_pools_with_controls_off=True,
            rejected_invalid_volume_with_controls_off=True,
            rejected_invalid_cotransport_and_water_controls=True,
        ),
    )
