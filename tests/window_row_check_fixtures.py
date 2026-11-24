"""Shared checks of the scalar windows' device row checks (WindowPolicy row_checks="device").

docs/WINDOW_DEVICE_CHECKS_DESIGN.md §9.5: between the modes, times, histories, observations and
checkpoints are bitwise; diagnostics agree to rounding, under the host's keys in its order. A
step-doubled run's (FR-18's X2) energy records are bitwise too, and its own diagnostics equal:
the host decides them in both modes, from the same rollout values.
"""

import numpy as np

from cells.execution import energy_check
from cells.execution.windows import WindowPolicy, iter_windows
from cells.models import surface_pump
from cells.operators import osmotic_water as water

# Each rounding residual's smallest bound (tests/unit/test_surface_pump_device_checks.py), and
# the water operator's own ledgers' floors (operators/osmotic_water.py).
FLOORS = {
    "max_capacitor_charge_error_C": 3e-25,
    "max_electrode_charge_error_C": 3e-25,
    "max_global_charge_error_C": surface_pump.GLOBAL_CHARGE_ATOL_C,
    "max_reservoir_work_error_pJ": 3e-12,
    "max_electrode_work_error_pJ": 3e-12,
    "max_metabolic_work_error_pJ": 3e-12,
    "max_global_charge_bound_ratio": 1.0,
    "max_cell_water_balance_error_pL": water.VOLUME_ATOL_PL,
    "max_outside_water_balance_error_pL": water.VOLUME_ATOL_PL,
    "max_global_water_balance_error_pL": water.VOLUME_ATOL_PL,
    "max_bath_water_work_error_pJ": water.WORK_ATOL_PJ,
}
MATERIAL = (
    "max_balance_error_fmol",
    "max_extracellular_balance_error_fmol",
    "max_global_balance_error_fmol",
)
ENERGY = ("max_energy_balance_error_pJ", "max_energy_balance_relative")


def windows(spec, width, mode, checkpoint=None):
    return list(iter_windows(spec, WindowPolicy(width, "checkpoints", mode), checkpoint))


def assert_same_windows(host, device):
    """Every array of each window bitwise, and the diagnostics under the same keys in order."""
    assert len(host) == len(device)
    for a, b in zip(host, device, strict=True):
        assert a.times.tobytes() == b.times.tobytes()
        for x, y in zip((*a.history, *a.final.state), (*b.history, *b.final.state), strict=True):
            x, y = np.asarray(x), np.asarray(y)
            assert x.dtype == y.dtype and x.shape == y.shape and x.tobytes() == y.tobytes()
        for k, x in vars(a.observations).items():
            assert np.asarray(x).tobytes() == np.asarray(getattr(b.observations, k)).tobytes(), k
        assert (a.final.time, a.final.step_index) == (b.final.time, b.final.step_index)
        assert (a.final.energy_check is None) is (b.final.energy_check is None)
        if a.final.energy_check is not None:
            assert a.final.energy_check.same(b.final.energy_check)
        assert list(a.diagnostics) == list(b.diagnostics)


def agrees(key, host, device, tol):
    """The device-check tests' criteria (test_surface_pump_device_checks.py): a rounding
    residual within 2% of its smallest bound (tol: the smallest material tolerance); the energy
    residual, a truncation quantity, to relative 1e-9. A diagnostic without a declared
    criterion fails: a new ledger must name its floor here."""
    if key in MATERIAL:
        return abs(device - host) <= 0.02 * tol
    if key in FLOORS:
        return abs(device - host) <= 0.02 * FLOORS[key]
    if key in ENERGY:
        return abs(device - host) <= 1e-9 * abs(host) + 1e-15
    if key in energy_check.DIAGNOSTICS:  # The same host code on the same values.
        return device == host
    raise AssertionError(f"No agreement criterion for the diagnostic {key}")


def assert_agreement(spec, host, device):
    """Each device-decided window's diagnostics against the host's check of the same rows."""
    tol = float(np.min(spec.execution.material_balance_atol_fmol))
    decided = 0
    for a, b in zip(host, device, strict=True):
        if b.row_checks.decided_by != "device":
            continue
        decided += 1
        for key, value in a.diagnostics.items():
            assert agrees(key, value, b.diagnostics[key], tol), (key, value, b.diagnostics[key])
        # The margins read the bound the diagnostics read (a misplaced bound would not).
        ratio = b.diagnostics["max_global_charge_bound_ratio"]
        assert abs(b.row_checks.ratios["global_charge"] - ratio) <= 1e-12 * ratio
    return decided
