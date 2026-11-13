"""Live phase markers (cells.core.phases) on vectorized windows, and the phase totals.

The markers are log records on "cells.phases": silent without a handler, and in order
when one is attached (each world's plan, the plan, binding, compile, the first window;
later windows at DEBUG). The windows' and the result's timing keys are unchanged, and
phase_totals groups them into preparation, execution, observation and output.
"""

import io
import logging

import jax
import pytest

from cells.core import phases
from cells.core.batch import BatchSpec, WorldSpec
from cells.core.specs import parse_spec
from cells.core.vector_windows import iter_vector_windows, run_vector_windowed
from cells.core.windows import WindowPolicy
from cells.numerics import surface_imex as imex
from validation.tissue import surface_pump_fixtures

POLICY = WindowPolicy(5, "checkpoints")
WINDOW_KEYS_BEFORE = {  # The keys before the markers; device_wait_seconds is the one added.
    "static_preparation_seconds",
    "window_preparation_seconds",
    "compile_seconds",
    "execute_seconds",
    "host_transfer_seconds",
    "analysis_seconds",
}
WINDOW_KEYS = WINDOW_KEYS_BEFORE | {"device_wait_seconds"}
RESULT_KEYS = WINDOW_KEYS | {"preflight_seconds", "sink_seconds", "total_run_seconds"}


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


def test_markers_are_silent_without_a_handler(capsys):
    assert not phases.LOGGER.handlers
    assert not phases.LOGGER.isEnabledFor(logging.INFO)
    list(iter_vector_windows(cohort(), POLICY))
    out = capsys.readouterr()
    assert "cells.phases" not in out.out + out.err


def test_markers_report_each_phase_as_it_ends(captured):
    windows = list(iter_vector_windows(cohort(), POLICY))
    names = [line.split()[2] for line in captured.getvalue().splitlines()]
    expected = ["plan.world", "plan.world", "plan", "binding", "compile", "first_window"]
    assert names == expected + ["window"] * (len(windows) - 1)
    first = next(line for line in captured.getvalue().splitlines() if " first_window " in line)
    assert "execute_seconds=" in first and "steps=" in first


def test_the_timing_keys_are_unchanged():
    for window in iter_vector_windows(cohort(), POLICY):
        assert set(window.timings) == WINDOW_KEYS
    assert set(run_vector_windowed(cohort(), POLICY).timings) == RESULT_KEYS


def test_phase_totals_group_the_timings():
    timings = dict(
        preflight_seconds=1.0,
        static_preparation_seconds=2.0,
        window_preparation_seconds=0.5,
        compile_seconds=3.0,
        execute_seconds=10.0,
        host_transfer_seconds=0.25,
        analysis_seconds=0.75,
        sink_seconds=1.5,
        total_run_seconds=20.0,
        new_seconds=4.0,
    )
    split = phases.phase_totals(timings, output_seconds=0.5)
    assert split["preparation"] == 6.5 and split["compile"] == 3.0
    assert split["execution"] == 10.0 and split["observation"] == 1.0
    assert split["output"] == 2.0 and split["other"] == {"new_seconds": 4.0}
    assert split["unaccounted"] == 0.5
    real = phases.phase_totals(run_vector_windowed(cohort(), POLICY).timings)
    # The host loop's phases do not overlap: what they leave out is the loop's own
    # bookkeeping (launch dispatch, Python), never negative.
    assert real["other"] == {} and real["unaccounted"] >= -1e-6
    assert real["execution"] <= real["device_from_launch"]


def test_enabled_restores_the_logger():
    level, handlers = phases.LOGGER.level, list(phases.LOGGER.handlers)
    with phases.enabled(io.StringIO()) as handler:
        assert handler in phases.LOGGER.handlers
        assert phases.LOGGER.isEnabledFor(logging.INFO)
    assert phases.LOGGER.handlers == handlers and phases.LOGGER.level == level
