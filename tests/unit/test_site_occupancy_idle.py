"""B3 of FR-3's milestone 1: idleness (§4.8, claims 1 and 2).

Criteria fixed before any code (/mnt/workspaces/Cells/site-occupancy-m1-20261115-01/HANDOFF.md):
* every multiplier zero: every inner field bitwise equal to the composition without the operator
  (the half-step selects the start state with where, never adding a computed zero);
* no populations declared: statically idle, and bitwise too.
The face-free world under ARS(2,2,2) at 1 ms, every step observed. Three compiles: not tier 1.
"""

import jax
import numpy as np

from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.models.registry import get_model
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import site_occupancy_fixtures as sfx

jax.config.update("jax_enable_x64", True)

END, DT = 0.01, 1e-3


def plain():
    return fx.face_free(
        pool_mM=1e-3,
        node_mM=1e-3,
        dt=DT,
        end=END,
        trace_mM=sfx.TRACE_mM,
        observation_times=fx.grid_times(END, DT, DT),
    )


def same_inner(a, b):
    for name in get_model(a.spec.model).STATE_TYPE._fields:
        x, y = np.asarray(getattr(a.history, name)), np.asarray(getattr(b.history, name))
        assert x.tobytes() == y.tobytes(), name


def test_zero_multipliers_and_no_populations_are_bitwise_idle():
    reference = run(parse_spec(plain()))
    pops = [
        sfx.population("out", k_int=0.5),
        sfx.population("in", patch="wall_cell_0", face="inside"),
    ]
    zero = {
        ("out", "binding"): [(0.0, 0.0)],
        ("out", "internalisation"): [(0.0, 0.0)],
        ("in", "binding"): [(0.0, 0.0)],
    }
    idle = run(parse_spec(sfx.with_site_occupancy(plain(), pops, controls=zero)))
    same_inner(reference, idle)
    empty = run(parse_spec(sfx.with_site_occupancy(plain(), [])))
    same_inner(reference, empty)
