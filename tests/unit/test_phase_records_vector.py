"""Start and failure records on the vectorized path (D156, item 3): its own refusal and its results.

A world failing its window is that path's refusal: it is raised after the window's completion
record, so it writes one failure record after the first window, with the exception's type and
message, and the exception propagates. And the records change no result: the same cohort with a
DEBUG handler attached and with none ends bitwise alike. The cohort is tests/unit/test_phases.py's.
Tier 2: three vectorized runs, each compiling its window.
"""

import io
import logging

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution import phases
from cells.execution.batch import BatchSpec, WorldSpec
from cells.execution.vector_windows import WorldCheckError, run_vector_windowed
from cells.execution.windows import WindowPolicy
from cells.models import surface_pump
from cells.numerics import surface_imex as imex
from validation.tissue import surface_pump_fixtures

POLICY = WindowPolicy(5, "checkpoints")


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def cohort():
    specs = []
    for scale in (1.0, 1.2):
        raw = surface_pump_fixtures.definition("release", solver=imex.ARS222_ID)
        raw["experiment"]["end_time"] = 0.0012
        raw["experiment"]["observation_times"] = [0.0, 0.0007, 0.0012]
        for membrane in raw["model"]["membranes"]:
            membrane["pump"]["capacity_fmol_per_s"] *= scale
        specs.append(parse_spec(raw))
    return BatchSpec(tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs)), 2, 10**6, 2**31)


@pytest.fixture
def captured():
    stream = io.StringIO()
    handler = phases.enable(stream, logging.DEBUG)
    try:
        yield stream
    finally:
        phases.LOGGER.removeHandler(handler)
        phases.LOGGER.setLevel(logging.NOTSET)


def refusing_step(original):
    """Every world's step is refused from the first row (the path's own refusal)."""

    def step(state, dt, control, p, active):
        updated, ok = original(state, dt, control, p, active)
        return state, jnp.logical_and(ok, False)

    return step


def test_a_refused_window_writes_one_failure_record_after_it(captured, monkeypatch):
    monkeypatch.setattr(surface_pump, "checked_step", refusing_step(surface_pump.checked_step))
    with pytest.raises(WorldCheckError) as caught:
        run_vector_windowed(cohort(), POLICY)
    lines = captured.getvalue().splitlines()
    names = [line.split()[2] for line in lines]
    assert names[-3:] == ["first_window.start", "first_window", "failed"]
    message = " ".join(str(caught.value).split())
    assert " after=first_window " in lines[-1]
    assert lines[-1].endswith(f" error=WorldCheckError message={message}")


def test_the_records_change_no_result():
    def finals(result):
        return {
            identity: (jax.tree.map(np.asarray, world.final.state), world.diagnostics)
            for identity, world in result.worlds.items()
        }

    plain = finals(run_vector_windowed(cohort(), POLICY))
    with phases.enabled(io.StringIO(), logging.DEBUG):
        recorded = finals(run_vector_windowed(cohort(), POLICY))
    assert plain.keys() == recorded.keys()
    for identity in plain:
        for a, b in zip(plain[identity][0], recorded[identity][0], strict=True):
            assert np.array_equal(a, b, equal_nan=True)
        assert plain[identity][1] == recorded[identity][1]
