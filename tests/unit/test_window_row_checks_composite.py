"""Device row checks on a composite with an operator's own ledger (water@1's OsmoticWater).

docs/WINDOW_DEVICE_CHECKS_DESIGN.md §9.3–§9.6, conditions C1 and C2 for a composition. Its
device diagnostics list the operator's own ledger before the energy and charge ratios, and its
host diagnostics after them, so a device-decided window must report them in the host's order.
Windows the device decides and windows it hands back merge into one run's diagnostics. Every
array stays host mode's, bitwise.
"""

import jax
import pytest

from cells.definitions.specs import parse_spec
from cells.execution import row_checks
from cells.execution.windows import WindowPolicy, run_windowed
from cells.registry.models import get_model
from tests.window_row_check_fixtures import assert_agreement, assert_same_windows, windows
from validation.tissue import composite_crossrev as crossrev

WIDTH = 4  # water_sheet's 10 steps: windows of 4, 4 and 2.


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


@pytest.fixture(scope="module")
def runs():
    spec = parse_spec(crossrev.worlds()["water_sheet"])
    return spec, windows(spec, WIDTH, "host"), windows(spec, WIDTH, "device")


def test_device_mode_keeps_every_array_and_the_host_order_of_the_diagnostics(runs):
    spec, host, device = runs
    model = get_model(spec.model)
    assert [len(w.times) - 1 for w in host] == [4, 4, 2]
    assert set(host[0].diagnostics) == set(model.DEVICE_DIAGNOSTICS)
    assert list(host[0].diagnostics) != list(model.DEVICE_DIAGNOSTICS)  # The orders differ.
    assert_same_windows(host, device)
    assert assert_agreement(spec, host, device) == len(device)


def test_device_and_host_decided_windows_merge_into_one_run(runs, monkeypatch):
    spec, host, device = runs
    peaks = [max(w.row_checks.ratios.values()) for w in device]
    assert min(peaks) < max(peaks)
    monkeypatch.setattr(row_checks, "HOST_DECIDES_ABOVE", (min(peaks) * max(peaks)) ** 0.5)
    mixed = windows(spec, WIDTH, "device")
    assert {w.row_checks.decided_by for w in mixed} == {"device", "host"}
    assert_same_windows(host, mixed)
    whole_host = run_windowed(spec, WindowPolicy(WIDTH, "checkpoints"))
    whole = run_windowed(spec, WindowPolicy(WIDTH, "checkpoints", "device"))
    assert list(whole.diagnostics) == list(whole_host.diagnostics)
    handed = sum(w.row_checks.decided_by == "host" for w in mixed)
    assert whole.resources["row_checks"]["host_decided"] == {"failed": 0, "above_band": handed}
