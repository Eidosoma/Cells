"""T7 of scheduled_membrane_trafficking@1 (FR-2 version 1), batches: a vmapped batch of three
cycle worlds (retrieval at 0.05, 0.1 and 0.15 of the plasma area per ms) is bitwise against the
same worlds in reversed order, and reproduces each world's own run to 1e-12 of each field's scale;
the carriers' work, whose terms cancel, to 1e-14 of its terms' accumulated magnitude.

"""

import jax
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.batch import BatchSpec, WorldSpec
from cells.execution.runner import run
from cells.execution.vector_windows import run_vector_windowed
from cells.execution.windows import WindowPolicy
from validation.tissue import composite_guard as guard
from validation.tissue import membrane_trafficking_fixtures as fx


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def vector_batch(specs):
    worlds = tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs))
    return run_vector_windowed(
        BatchSpec(worlds, len(worlds), 10**6, 2**31), WindowPolicy(4, "checkpoints")
    )


def test_the_vmapped_batch_reproduces_each_world():
    specs = [parse_spec(fx.cycle(retrieval=r)) for r in (0.05, 0.1, 0.15)]
    batch = vector_batch(specs)
    reversed_batch = vector_batch(specs[::-1])
    for i in range(len(specs)):  # World IDs are 1, 2, ... in each batch's order.
        x = batch.worlds[i + 1].final.state
        y = reversed_batch.worlds[len(specs) - i].final.state
        for name in type(x)._fields:
            assert guard.compare_arrays(name, getattr(x, name), getattr(y, name)) is None, name
    for world, spec in zip(batch.worlds, specs, strict=True):
        single = run(spec)
        final = batch.worlds[world].final.state
        for name in type(final)._fields:
            a, b = np.asarray(getattr(final, name)), np.asarray(getattr(single.history, name))[-1]
            bound = 1e-12 * np.max(np.abs(b), initial=0.0) + 1e-30
            if name == "trafficking_work_pJ":
                # The carriers' work is a difference of terms (their free-energy change less the
                # baths' share) that cancel: their accumulated magnitude,
                # trafficking_energy_magnitude_pJ, was 3.97e4 times the work in world 1, and the
                # batch differed by 0.11 eps of it (FR-2's probes/work_scale). A rounding claim is
                # made at the terms' scale: 1e-14 of it is about 45 eps, some 400 times the
                # measured difference.
                terms = np.asarray(single.history.trafficking_energy_magnitude_pJ)[-1]
                bound = 1e-14 * float(np.max(terms)) + 1e-30
            assert np.max(np.abs(a - b), initial=0.0) <= bound, (world, name)
        assert np.isfinite(batch.worlds[world].diagnostics["max_energy_balance_error_pJ"])
