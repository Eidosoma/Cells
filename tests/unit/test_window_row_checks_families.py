"""Device row checks on cells.model.resolved_pump_tissue@2 and on @3 with a declared kind.

docs/WINDOW_DEVICE_CHECKS_DESIGN.md §9.6, conditions C1 and C2 beyond @1 and the composites:
@2's calcium pump, and @3 with a declared kind (tests/kind_fixtures.py's exchange), whose
device checks fold the kind's ledger terms. Windows of 5 steps, a partial last window
included: every array is host mode's, bitwise, and each device-decided window's diagnostics
agree with the host's check of the same rows.
"""

from contextlib import nullcontext

import jax
import pytest

from cells.definitions.specs import parse_spec
from cells.numerics import surface_imex as imex
from cells.registry import kind_registry
from tests.window_row_check_fixtures import assert_agreement, assert_same_windows, windows
from validation.tissue import surface_pump_v2_fixtures

WIDTH = 5


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def cases():
    from tests.unit.test_kind_schedules import scheduled, world

    raw = surface_pump_v2_fixtures.definition("clamped", solver=imex.ARS222_ID)
    raw["experiment"]["end_time"] = 0.0012
    raw["experiment"]["observation_times"] = [0.0, 0.0007, 0.0012]
    return {"@2": (None, raw), "@3-kind": (scheduled(), world(None, end_time=0.012))}


@pytest.fixture(scope="module")
def runs():
    out = {}
    for name, (registry, raw) in cases().items():
        with kind_registry.scope(registry) if registry is not None else nullcontext():
            spec = parse_spec(raw)
            out[name] = spec, windows(spec, WIDTH, "host"), windows(spec, WIDTH, "device")
    return out


@pytest.mark.parametrize("name", ["@2", "@3-kind"])
def test_device_mode_keeps_every_array_and_agrees_with_the_host(name, runs):
    spec, host, device = runs[name]
    steps = [len(w.times) - 1 for w in host]
    assert len(steps) > 1 and steps[-1] < WIDTH  # A partial last window.
    assert_same_windows(host, device)
    assert assert_agreement(spec, host, device) == len(device)
