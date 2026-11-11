"""resolved_pump_replacement@1 in vectorized worlds (core/vector_windows.py).

Two worlds with different replacement schedules and templates, advanced as one
vmapped batch with device checks, reproduce each world's own windowed run to
rounding (lax.cond becomes a select under vmap, so the event map runs every step
in every world and is discarded where no slot is due).
"""

import jax
import numpy as np
import pytest

from cells.core.batch import BatchSpec, WorldSpec
from cells.core.cell_replacement_spec import exact_event_times
from cells.core.specs import parse_spec
from cells.core.vector_windows import run_vector_windowed
from cells.core.windows import WindowPolicy, run_windowed
from validation.tissue import cell_replacement_fixtures as fx

DT = 1e-3
POLICY = WindowPolicy(8, "checkpoints")


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def world(events):
    raw = fx.heredity_sheet(1, 0, dt=DT, end_time=24 * DT)
    raw["experiment"]["observation_times"] = [0.0, 12 * DT, 24 * DT]
    templates = [
        fx.template_from_cell(raw, "cell_1", "h"),
        fx.template_from_cell(raw, "cell_3", "d"),
    ]
    formation = dict(fx.FORMATION, lag_s=0.0, time_constant_s=40.0)
    return parse_spec(fx.with_replacement(raw, templates, events, formation=formation))


def test_vectorized_worlds_reproduce_their_own_runs():
    t = exact_event_times((5, 9, 16), DT)
    specs = [
        world(((t[0], "cell_0", "h", "a1"), (t[2], "cell_0", "d", "a2"))),
        world(((t[1], "cell_3", "h", "b1"), (t[1], "cell_4", "h", "b2"))),
    ]
    cohort = BatchSpec(tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs)), 2, 10**6, 2**31)
    batch = run_vector_windowed(cohort, POLICY)
    for w in cohort.worlds:
        own = run_windowed(w.simulation, POLICY).final.state
        mine = batch.worlds[w.world_id].final.state
        for name, a, b in zip(type(own)._fields, mine, own, strict=True):
            a, b = np.asarray(a), np.asarray(b)
            assert a.shape == b.shape and a.dtype == b.dtype, name
            scale = np.max(np.abs(b), initial=0)
            assert np.max(np.abs(a - b), initial=0) <= 1e-12 * max(scale, 1e-300), name
    final = {w: np.asarray(batch.worlds[w].final.state.generation) for w in (1, 2)}
    assert final[1].tolist() == [2, 0, 0, 0, 0, 0, 0]
    assert final[2].tolist() == [0, 0, 0, 1, 1, 0, 0]
