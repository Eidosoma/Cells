"""B5 of FR-3's milestone 1: the stage condition refuses dt L > 1 at run time (§4.2).

Criteria fixed before any code (/mnt/workspaces/Cells/site-occupancy-m1-20261115-01/HANDOFF.md):
a world whose binding rate makes h max L exceed 1/2 (dt L > 1) fails the runner, and the model's
own checked step refuses the step and returns its start state bit for bit; the same world with a
slower k_on is admitted by the checked step. One compile: not tier 1.
"""

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core import pump_composite_spec as cs
from cells.core.errors import NumericalError
from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.models.operators import site_occupancy as so
from cells.models.registry import get_model
from validation.tissue import site_occupancy_fixtures as sfx

jax.config.update("jax_enable_x64", True)

DT = 1e-3


def world(k_on):
    # Free sites R ~ 8e-5 fmol in a 1 pL node: L_n = k_on R / V and L_R = k_on c; with c = 1e-3 mM
    # a k_on of 2e6 /mM/s gives dt L_R = 2.
    pops = [sfx.population("out", k_on=k_on, k_off=k_on * 1e-6)]
    return parse_spec(sfx.face_free_sites(pops, end=0.005, dt=DT))


def test_dt_L_above_one_is_refused_at_run_time_and_the_step_returns_its_start():
    spec = world(2e6)
    with pytest.raises(NumericalError):
        run(spec)
    model = get_model(spec.model)
    state, p = jax.tree.map(jnp.asarray, model.initial_values(spec))
    controls = cs.control_values(spec, [0.0])
    control = type(controls)(*(jnp.asarray(v[0]) for v in controls))
    step = jax.jit(lambda x, c: model.checked_step(x, jnp.asarray(DT), c, p, p.active))
    moved, ok = step(state, control)
    assert not bool(ok)
    for a, b in zip(moved, state, strict=True):
        assert np.asarray(a).tobytes() == np.asarray(b).tobytes()
    report = so.stage_report(
        type(state)(*(np.asarray(v) for v in state)),
        type(controls)(*(np.asarray(v[0]) for v in controls)),
        type(p)(*(np.asarray(v) for v in p)),
        DT,
    )
    assert report["max_hL"] > so.THETA and not report["admitted"]
    slow = world(2e3)
    s_state, s_p = jax.tree.map(jnp.asarray, get_model(slow.model).initial_values(slow))
    slow_step = jax.jit(
        lambda x, c: get_model(slow.model).checked_step(x, jnp.asarray(DT), c, s_p, s_p.active)
    )
    assert bool(slow_step(s_state, control)[1])
