"""Step checks bound to a definition (resolved_pump_tissue@1-@3) and clock validation.

core.grid.checked_grid validates a definition's whole declared clock in chunks of
at most 1024 steps. The pump family's step checks read each chunk's largest step
and quantities of the definition alone, so bind_step_checks evaluates those once
per definition (two of its rate bounds build the layout). These tests pin that the
bound checks refuse exactly as the step checks did before (reference_* below are
those functions, unchanged), chunk by chunk in the same order, and that a long
clock builds the layout once, not once per chunk. No JIT and no device.
"""

import copy
from dataclasses import replace

import numpy as np
import pytest

from cells.core import grid as grid_module
from cells.core.grid import EventGrid, checked_grid, clock_checks
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.surface_pump_v3_spec import NAV1P2_LAW_ID, projection
from cells.models import surface_kinetic as kinetic
from cells.models import surface_pump as first
from cells.models import surface_pump_v2 as second
from cells.models import surface_pump_v3 as third
from cells.models import surface_tissue as tissue
from cells.models.registry import get_model
from cells.numerics import surface_imex as imex
from validation.tissue import pump_water_fixtures as water
from validation.tissue import surface_pump_fixtures as fixtures_1
from validation.tissue import surface_pump_v2_fixtures as fixtures_2
from validation.tissue import surface_pump_v3_fixtures as fixtures_3

SOLVERS = (imex.EULER_ID, imex.ARS222_ID, "rk4")
MODULES = {1: first, 2: second, 3: third}
OBSERVATIONS = "Resolved pump observations require accepted integration boundaries"


def reference_1(spec, steps, controls):
    """surface_pump.check_steps before bind_step_checks, verbatim."""
    if spec.execution.solver == "rk4":
        return kinetic.check_steps(spec, steps, controls)
    grid = EventGrid(spec)
    for t in spec.experiment.observation_times:
        try:
            grid.exact_index(t)
        except ConfigError as error:
            raise ConfigError(OBSERVATIONS) from error
    if np.max(steps, initial=0) * first.junction_gate_rate_bound(spec) > first.GATE_STEP_BOUND:
        raise ConfigError("Resolved junction step exceeds conservative kinetic bound")
    if np.max(steps, initial=0) * first.explicit_rate_bound(spec) > first.EXPLICIT_STEP_BOUND:
        raise ConfigError("IMEX step exceeds the explicit-rate stability bound")


def reference_2(spec, steps, controls):
    """surface_pump_v2.check_steps before bind_step_checks, verbatim."""
    reference_1(spec, steps, controls)
    if spec.execution.solver != "rk4" and (
        np.max(steps, initial=0) * second.calcium_rate_bound(spec) > second.EXPLICIT_STEP_BOUND
    ):
        raise ConfigError("IMEX step exceeds the explicit calcium pump rate bound")


def reference_3(spec, steps, controls):
    """surface_pump_v3.check_steps before bind_step_checks, verbatim."""
    step, base = np.max(steps, initial=0), projection(spec)
    if spec.execution.solver == "rk4":
        tissue.check_steps(spec, steps, controls)
        laws = {c.kinetic_law for c in spec.model.channels if c.initial_gate}
        if NAV1P2_LAW_ID in laws and step > third.RK4_SODIUM_STEP + 1e-16:
            raise ConfigError("Resolved NaV1.2 channels require RK4 steps <= 2.5 us")
        if laws and step > third.RK4_POTASSIUM_STEP + 1e-16:
            raise ConfigError("Resolved gated channels require RK4 steps <= 25 us")
    else:
        grid = EventGrid(spec)
        for t in spec.experiment.observation_times:
            try:
                grid.exact_index(t)
            except ConfigError as error:
                raise ConfigError(OBSERVATIONS) from error
        if step * first.explicit_rate_bound(base) > third.EXPLICIT_STEP_BOUND:
            raise ConfigError("IMEX step exceeds the explicit-rate stability bound")
        if step * second.calcium_rate_bound(base) > third.EXPLICIT_STEP_BOUND:
            raise ConfigError("IMEX step exceeds the explicit calcium pump rate bound")
    if step * first.junction_gate_rate_bound(spec) > first.GATE_STEP_BOUND:
        raise ConfigError("Resolved junction step exceeds conservative kinetic bound")


REFERENCES = {1: reference_1, 2: reference_2, 3: reference_3}


def definition(version, solver, *, end_time=None, early_event=False):
    """The clamped fixture world of each version (@3 with its eight channels)."""
    raw = {1: fixtures_1, 2: fixtures_2, 3: fixtures_3}[version].definition(
        "clamped", solver=solver
    )
    raw = copy.deepcopy(raw)
    e, x = raw["experiment"], raw["execution"]
    if end_time is not None:
        e["end_time"] = end_time
        x["max_steps"] = int(round(end_time / x["dt"])) + 8
    if early_event:  # An event-split step (3e-5 s, then 7e-5 s) in the first chunk.
        schedule = e["membrane_controls"][0]["schedule"]
        schedule.append(dict(schedule[-1], time=3e-5))
    return parse_spec(raw)


def outcome(function, *args):
    """None, or a refusal's type and message and those of its cause."""
    try:
        function(*args)
    except Exception as error:  # Every refusal is compared.
        cause = error.__cause__
        return type(error), str(error), None if cause is None else (type(cause), str(cause))
    return None


def patch_bounds(monkeypatch, explicit, calcium, junction):
    """Declared rate bounds (1/s); the explicit and calcium ones double on a definition
    that still has channels, so a check that read the wrong definition would differ."""

    def scaled(value):
        return lambda spec: value * (2.0 if getattr(spec.execution, "channel_capacity", 0) else 1)

    monkeypatch.setattr(first, "explicit_rate_bound", scaled(explicit))
    monkeypatch.setattr(second, "calcium_rate_bound", scaled(calcium))
    monkeypatch.setattr(first, "junction_gate_rate_bound", lambda spec: junction)


STEPS = (1e-6, 3e-6, 3e-5, 1e-4, 2e-4, 4e-3, 6e-3, 3e-2, 0.2)


@pytest.mark.parametrize("solver", SOLVERS)
@pytest.mark.parametrize("version", (1, 2, 3))
def test_bound_checks_refuse_as_the_step_checks_did(monkeypatch, version, solver):
    """Every refusal, message and cause, in order, over bounds and step sizes."""
    spec, module, reference = definition(version, solver), MODULES[version], REFERENCES[version]
    controls = control_values(spec, np.zeros(4))
    refusals = set()
    for explicit in (0.0, 150.0, 400.0):
        for calcium in (0.0, 30.0, 300.0):
            for junction in (0.0, 20.0, 60.0):
                patch_bounds(monkeypatch, explicit, calcium, junction)
                bound = module.bind_step_checks(spec)  # Kept across the step sizes.
                for size in STEPS:
                    steps = np.full(4, size)
                    expected = outcome(reference, spec, steps, controls)
                    assert outcome(module.check_steps, spec, steps, controls) == expected
                    assert outcome(bound, steps) == expected
                    refusals.add(None if expected is None else expected[1])
    imex_refusals = {
        1: {"junction step", "explicit-rate"},
        2: {"junction step", "explicit-rate", "calcium pump"},
        3: {"junction step", "explicit-rate", "calcium pump"},
    }[version]
    rk4_refusals = {"0.0001 s", *(("2.5 us",) if version == 3 else ())}  # NaV1.2 present.
    wanted = rk4_refusals if solver == "rk4" else imex_refusals
    for part in wanted:  # Each refusal of the order was reached.
        assert any(r is not None and part in r for r in refusals), part
    assert None in refusals


@pytest.mark.parametrize("solver", SOLVERS)
@pytest.mark.parametrize("version", (1, 2, 3))
def test_off_grid_observations_refuse_as_before(version, solver):
    spec = definition(version, solver)
    off = replace(spec, experiment=replace(spec.experiment, observation_times=(0.0, 3e-5)))
    steps = np.full(4, spec.execution.dt)
    controls = control_values(off, np.zeros(4))
    expected = outcome(REFERENCES[version], off, steps, controls)
    assert expected is not None and "accepted integration boundaries" in expected[1]
    assert expected[2] is not None  # The grid's own refusal is kept as the cause.
    assert outcome(MODULES[version].check_steps, off, steps, controls) == expected
    assert outcome(MODULES[version].bind_step_checks(off), steps) == expected
    assert outcome(checked_grid, off) == expected


def reference_checked_grid(spec, reference, window_steps):
    for times in EventGrid(spec).windows(0, window_steps):
        reference(spec, np.diff(times), control_values(spec, times[:-1]))


@pytest.mark.parametrize(
    "version, explicit, calcium, junction, refusal",
    [
        # The first chunk's largest step is 7e-5 s, the next chunks' 1e-4 s. Validating
        # the whole clock's largest step at once would refuse with the junction bound
        # (@1, @2) or the explicit bound (@3) instead.
        (1, 2e4, 0.0, 1500.0, "explicit-rate"),
        (2, 2e4, 0.0, 1500.0, "explicit-rate"),
        (2, 0.0, 2e4, 1500.0, "calcium pump"),
        (3, 1.2e4, 2e4, 0.0, "calcium pump"),
        (3, 1.2e4, 0.0, 1500.0, "explicit-rate"),
    ],
)
def test_clock_refusals_are_chunk_by_chunk_in_order(
    monkeypatch, version, explicit, calcium, junction, refusal
):
    spec = definition(version, imex.ARS222_ID, early_event=True)
    patch_bounds(monkeypatch, explicit, calcium, junction)
    expected = outcome(reference_checked_grid, spec, REFERENCES[version], 2)
    assert expected is not None and refusal in expected[1]
    assert outcome(lambda: checked_grid(spec, window_steps=2)) == expected


@pytest.mark.parametrize("solver", SOLVERS)
@pytest.mark.parametrize("version", (1, 2, 3))
def test_valid_clocks_pass_with_the_same_grid(version, solver):
    if version == 3 and solver == "rk4":
        spec = definition(3, solver)  # Gated NaV1.2: RK4 at 1e-4 s is refused.
        expected = outcome(reference_checked_grid, spec, reference_3, 1024)
        assert expected is not None and "2.5 us" in expected[1]
        assert outcome(checked_grid, spec) == expected
        return
    spec = definition(version, solver)
    reference_checked_grid(spec, REFERENCES[version], 1024)
    grid = checked_grid(spec)
    assert list(grid) == list(EventGrid(spec))


def counted(monkeypatch, module, name):
    calls, function = [0], getattr(module, name)

    def wrapper(*args, **kwargs):
        calls[0] += 1
        return function(*args, **kwargs)

    monkeypatch.setattr(module, name, wrapper)
    return calls


@pytest.mark.parametrize(
    "version, solver, builds",
    [(1, imex.ARS222_ID, 1), (2, imex.EULER_ID, 2), (3, imex.ARS222_ID, 2), (1, "rk4", 0)],
)
def test_a_long_clock_builds_each_layout_once(monkeypatch, version, solver, builds):
    """Layout builds (initial_values) per checked_grid do not grow with the clock.

    explicit_rate_bound and calcium_rate_bound each build one layout; before the
    bound checks, every chunk rebuilt them (100 and 200 chunks here). No chunk
    builds a control table either.
    """
    layouts = counted(monkeypatch, tissue, "initial_values")
    tables = counted(monkeypatch, grid_module, "control_values")
    for chunks in (100, 200):
        spec = definition(version, solver, end_time=chunks * 1024 * 1e-4)
        layouts[0] = tables[0] = 0
        grid = checked_grid(spec)
        assert -(-(len(grid) - 1) // 1024) == chunks
        assert (layouts[0], tables[0]) == (builds, 0)
    layouts[0] = 0  # One direct check_steps call (one chunk) builds as many.
    MODULES[version].check_steps(spec, np.full(4, 1e-4), None)
    assert layouts[0] == builds


def test_composites_keep_their_step_checks_per_chunk(monkeypatch):
    """Water @1/@2 and replacement @1 are compositions over @3 (models/pump_composite.py).

    Their check_steps is the composite's: @3's step checks on the definition the
    operators declare, then each operator's own (the water bounds, for instance).
    The composite does not bind those to the definition yet, so clock_checks calls
    it once per chunk with the chunk's control table and no operator refusal is
    skipped; the thin modules must not expose @3's bind_step_checks either. When
    pump_composite binds its step checks, this test changes with it.
    """
    from cells.models import (
        cell_replacement,
        pump_composite,
        surface_pump_water,
        surface_pump_water_v2,
    )

    for module in (surface_pump_water, surface_pump_water_v2, cell_replacement):
        assert not hasattr(module, "bind_step_checks"), module.__name__
    assert not hasattr(pump_composite.Composition, "bind_step_checks")
    spec = parse_spec(water.with_water(water.heredity_cell(end_time=3.0)))
    assert get_model(spec.model) is surface_pump_water
    composite = counted(monkeypatch, pump_composite.Composition, "check_steps")
    tables = counted(monkeypatch, grid_module, "control_values")
    grid = checked_grid(spec)
    assert -(-(len(grid) - 1) // 1024) == 3 and composite[0] == tables[0] == 3
    # 100 cm/s: dt x the water relaxation rate far above 0.05, an operator's refusal.
    fast = parse_spec(water.with_water(water.heredity_cell(end_time=0.01), pf_m_s=1.0))
    with pytest.raises(ConfigError, match="Water relaxation"):
        checked_grid(fast)
    with pytest.raises(ConfigError, match="Water relaxation"):
        clock_checks(fast)(np.full(2, 1e-3), np.array([0.0, 1e-3, 2e-3]))
