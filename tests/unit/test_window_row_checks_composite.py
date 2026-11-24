"""Device row checks on a composite with an operator's own ledger (water@1's OsmoticWater).

docs/WINDOW_DEVICE_CHECKS_DESIGN.md §9.3–§9.6, conditions C1 and C2 for a composition. Its
device diagnostics list the operator's own ledger before the energy and charge ratios, and its
host diagnostics after them, so a device-decided window must report them in the host's order.
Windows the device decides and windows it hands back merge into one run's diagnostics. Every
array stays host mode's, bitwise. On a GPU (CELLS_TEST_GPU=1, D330), the composite qualified there,
under the sparse field solver, keeps the same conditions on GJ-N1's line.
"""

import os

import jax
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution import row_checks
from cells.execution.windows import WindowPolicy, run_windowed
from cells.registry.models import get_model
from tests.window_row_check_fixtures import (
    assert_agreement,
    assert_same_windows,
    require_deterministic_gpu,
    windows,
)
from validation.tissue import composite_crossrev as crossrev

WIDTH = 4  # water_sheet's 10 steps: windows of 4, 4 and 2.
GPU = pytest.mark.skipif(os.environ.get("CELLS_TEST_GPU") != "1", reason="explicit CUDA test")
SPARSE = "sparse_capacitive_reduction_gauged_damped_newton@1"


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


@GPU
def test_on_a_gpu_the_composite_under_the_sparse_solver_keeps_agrees_and_merges(monkeypatch):
    """D330, the composite's GPU rows: GJ-N1's line (not blind) under the sparse field solver on
    the GPU backend, with XLA's deterministic ops (the qualified configuration), at windows of WIDTH
    steps. Device mode keeps every array of host mode (C1);
    each device-decided window's ratios to the bounds lie within 0.1 of the host's on the same
    rows (C2 in units of the bound: the tests' absolute floors do not fit these worlds' large
    amounts, gpu_row_checks.host_ratios); and with the band between the windows' peaks, host- and
    device-decided windows merge into one run (C3's routing)."""
    from validation.execution.gpu_row_checks import host_ratios
    from validation.gap_junction_tissue import neither

    require_deterministic_gpu()
    dt = neither.step(1e-13, 2)
    raw = neither.coupled_world(1e-13, neither.STAGE1_END_UNITS, end=10 * dt, shape="line")
    raw["execution"].update(field_solver=SPARSE, backend="gpu")
    spec = parse_spec(raw)
    host, device = windows(spec, WIDTH, "host"), windows(spec, WIDTH, "device")
    assert [len(w.times) - 1 for w in host] == [4, 4, 2]
    assert_same_windows(host, device)
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    p = type(p)(*(np.asarray(v) for v in p))
    constants = model.device_check_constants(spec)
    for w in device:
        assert w.row_checks.decided_by == "device"
        ratios = host_ratios(model, spec, p, constants, w)
        assert all(abs(ratios[k] - v) <= 0.1 for k, v in w.row_checks.ratios.items())
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
