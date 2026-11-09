"""Device checks of the resolved pump family against the host check_values.

surface_pump.device_checks and surface_pump_v2.device_checks evaluate the host
check's tests for one accepted row with jax.numpy (models/surface_pump_checks.py).
On accepted rows of real IMEX runs both must pass with the same diagnostics
(rounding residuals agree to a small fraction of their bounds; the energy
residual, a truncation quantity, to relative 1e-9). Injected faults must fail
both at the same first row, with the host's message for the first failed check.
"""

import jax
import numpy as np
import pytest

from cells.core.errors import NumericalError
from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.models import surface_pump, surface_pump_v2
from cells.numerics import surface_imex as imex
from validation.tissue import surface_pump_fixtures, surface_pump_v2_fixtures

CASES = {
    "pump@1-release": (surface_pump, surface_pump_fixtures, "release"),
    "pump@2-clamped": (surface_pump_v2, surface_pump_v2_fixtures, "clamped"),
}


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


@pytest.fixture(scope="module")
def runs():
    result = {}
    for name, (model, fixtures, arm) in CASES.items():
        raw = fixtures.definition(arm, solver=imex.ARS222_ID)
        raw["experiment"]["end_time"] = 0.0012
        raw["experiment"]["observation_times"] = [0.0, 0.0012]
        spec = parse_spec(raw)
        value = run(spec)
        history = model.STATE_TYPE(*(np.asarray(v) for v in value.history))
        _, p = model.initial_values(spec)
        result[name] = model, spec, history, p
    return result


def device_rows(model, spec, history, p):
    """(failed [row, check], values [row, diagnostic]); row 0 is its own predecessor."""
    previous = type(history)(*(np.concatenate((v[:1], v[:-1])) for v in history))
    checks = jax.jit(jax.vmap(model.device_checks, in_axes=(0, 0, None, None)))
    failed, values = checks(previous, history, p, model.device_check_constants(spec))
    return np.asarray(failed), np.asarray(values)


def host_first_failure(model, spec, history):
    """First row at which the host check of the history up to it raises, and why."""
    for j in range(len(history.amount_increment)):
        try:
            model.check_values(type(history)(*(v[: j + 1] for v in history)), spec)
        except NumericalError as error:
            return j, str(error)
    return None, None


def device_first_failure(model, failed):
    rows = np.flatnonzero(failed.any(axis=1))
    if not len(rows):
        return None, None
    row = int(rows[0])
    check = model.DEVICE_CHECKS[int(np.flatnonzero(failed[row])[0])]
    return row, model.device_failure_message(check)


@pytest.mark.parametrize("case", CASES)
def test_device_diagnostics_match_host_check_values_on_accepted_rows(case, runs):
    model, spec, history, p = runs[case]
    failed, values = device_rows(model, spec, history, p)
    assert not failed.any()
    assert model.DEVICE_CHECKS[0] == "domain" and model.DEVICE_CHECKS[-1] == "dissipation"
    tol = np.asarray(spec.execution.material_balance_atol_fmol)
    bounds = {  # Smallest bound of each rounding residual (host bounds).
        "max_balance_error_fmol": tol.min(),
        "max_extracellular_balance_error_fmol": tol.min(),
        "max_global_balance_error_fmol": tol.min(),
        "max_capacitor_charge_error_C": 3e-25,
        "max_electrode_charge_error_C": 3e-25,
        "max_global_charge_error_C": surface_pump.GLOBAL_CHARGE_ATOL_C,
        "max_reservoir_work_error_pJ": 3e-12,
        "max_electrode_work_error_pJ": 3e-12,
        "max_metabolic_work_error_pJ": 3e-12,
        "max_global_charge_bound_ratio": 1.0,
    }
    for j in range(len(history.amount_increment)):
        row = type(history)(*(v[j] for v in history))
        host = model.check_values(row, spec)
        assert list(host) == list(model.DEVICE_DIAGNOSTICS)
        device = dict(zip(model.DEVICE_DIAGNOSTICS, values[j], strict=True))
        for key, value in host.items():
            if key in bounds:
                assert abs(device[key] - value) <= 0.02 * bounds[key], (case, j, key)
            else:  # Energy residual: a truncation quantity, not a rounding one.
                assert abs(device[key] - value) <= 1e-9 * abs(value) + 1e-15, (case, j, key)


def inject(history, p, fault, row):
    """A copy of the history with one fault from ``row`` (or at it only)."""
    values = history._asdict()
    reservoir = int(np.flatnonzero(p.reservoir)[0]) if np.any(p.reservoir) else 0
    if fault == "dissipation":  # Falls 2e-12 below the previous row; energy stays in bound.
        array = values["face_dissipated_energy_pJ"].copy()
        array[row, 0] = array[row - 1, 0] - 2e-12
        return history._replace(face_dissipated_energy_pJ=array)
    name, index, delta = {
        "material": ("reservoir_supplied", (0, reservoir), 1e-6),
        "metabolic": ("metabolic_work_pJ", (0,), 1e-10),
        "electrode": ("electrode_charge_transferred_C", (reservoir,), 1e-18),
        "energy": ("pump_dissipated_energy_pJ", (0,), -1e-3),
        "domain": ("amount_increment", (0, 0), np.nan),
    }[fault]
    array = values[name].copy()
    array[(slice(row, None), *index)] += delta
    values[name] = array
    return type(history)(**values)


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize(
    "fault", ["material", "metabolic", "electrode", "energy", "dissipation", "domain"]
)
def test_injected_fault_fails_host_and_device_at_the_same_row(case, fault, runs):
    model, spec, history, p = runs[case]
    if fault == "electrode" and not np.any(p.reservoir):
        pytest.skip("No reservoir electrode in this arm")
    row = 5
    corrupted = inject(history, p, fault, row)
    host = host_first_failure(model, spec, corrupted)
    failed, _ = device_rows(model, spec, corrupted, p)
    assert host[0] == row and device_first_failure(model, failed) == host, (host, failed[row])


def test_host_and_device_failure_messages_share_one_definition():
    for model in (surface_pump, surface_pump_v2):
        assert model.device_failure_message("domain") == surface_pump.DOMAIN_MESSAGE
        assert model.device_failure_message("global_charge") == (
            "Resolved pump accounting failed: global_charge"
        )
        assert model.device_failure_message("dissipation") == surface_pump.DISSIPATION_MESSAGE
        assert model.DEVICE_CHECKS == ("domain", *surface_pump.LEDGERS, "dissipation")
