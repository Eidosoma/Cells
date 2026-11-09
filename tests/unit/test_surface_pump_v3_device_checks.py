"""Device checks of resolved_pump_tissue@3 against its host check_values.

surface_pump_v3.device_checks evaluates check_values' tests for one accepted row
with jax.numpy (models/surface_pump_checks.py), with the same domain function,
ledgers and bounds: channel transfers enter the membrane total of the material
ledgers, channel heat the energy ledger, and channel dissipation the dissipation
check. On accepted rows of real IMEX runs (channels switched on mid-run, and
held open) both pass with the same diagnostics, rounding residuals to a small
fraction of their bounds. Seeded faults of every check class, including the
channel gates, gate-free leak and padding slots and the channel-transfer
ledgers, get the same verdict row for row, with the host's message for the
first failed check. The bounds are the host's, including the running-ledger
allowance at hour-scale step counts.
"""

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core.errors import NumericalError
from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.models import surface_pump, surface_pump_v3, surface_tissue
from cells.numerics import surface_field
from cells.numerics import surface_imex as imex
from validation.tissue import surface_pump_v3_fixtures as fixtures

MODEL = surface_pump_v3
ROW = 5  # First faulty row of the seeded histories.
HOUR = 3_600_000  # Accepted steps in one hour at dt = 1 ms.


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


@pytest.fixture(scope="module")
def runs():
    """IMEX runs of the eight-population fixture: channels off then on, and held on."""
    result = {}
    for arm in ("release", "clamped"):
        raw = fixtures.definition(arm, solver=imex.ARS222_ID)
        raw["experiment"]["end_time"] = 0.0012
        raw["experiment"]["observation_times"] = [0.0, 0.0012]
        spec = parse_spec(raw)
        history = MODEL.STATE_TYPE(*(np.asarray(v) for v in run(spec).history))
        _, p = MODEL.initial_values(spec)
        result[arm] = spec, history, p
    return result


def device_rows(spec, history, p, offset=0):
    """(failed [row, check], values [row, diagnostic]); row 0 is its own predecessor."""
    previous = type(history)(*(np.concatenate((v[:1], v[:-1])) for v in history))
    checks = jax.jit(jax.vmap(MODEL.device_checks, in_axes=(0, 0, None, None, 0)))
    steps = offset + np.arange(len(history.amount_increment))
    failed, values = checks(previous, history, p, MODEL.device_check_constants(spec), steps)
    return np.asarray(failed), np.asarray(values)


def rows_of(history, start, stop):
    return type(history)(*(v[start:stop] for v in history))


def host_verdict(spec, history, j, offset=0):
    """The host check's message for row j alone (None if it passes).

    Row j's own tests are check_values of that row; its dissipation decrease is
    check_values of rows j-1 and j, which reaches that test only when row j-1
    passes its own tests (as every seeded fault here leaves it).
    """
    try:
        MODEL.check_values(rows_of(history, j, j + 1), spec, steps=[offset + j])
        if j:
            try:
                MODEL.check_values(rows_of(history, j - 1, j), spec, steps=[offset + j - 1])
            except NumericalError:
                return None  # Row j-1 fails alone; row j's own tests passed.
            MODEL.check_values(
                rows_of(history, j - 1, j + 1), spec, steps=[offset + j - 1, offset + j]
            )
    except NumericalError as error:
        return str(error)
    return None


def device_verdicts(failed):
    """The message of each row's first failed device check (None if it passes)."""
    return [
        MODEL.device_failure_message(MODEL.DEVICE_CHECKS[int(np.argmax(f))]) if f.any() else None
        for f in failed
    ]


def test_device_checks_share_the_host_definitions():
    assert MODEL.DEVICE_CHECKS == ("domain", *surface_pump.LEDGERS, "dissipation")
    assert MODEL.DEVICE_DIAGNOSTICS == surface_pump.DEVICE_DIAGNOSTICS
    assert MODEL.device_failure_message is surface_pump.device_failure_message
    assert MODEL.device_check_constants is surface_pump.device_check_constants
    assert "channel_dissipated_energy_pJ" in MODEL.DISSIPATION_FIELDS
    assert MODEL.DISSIPATION_FIELDS == tuple(
        k for k in MODEL.STATE_AXES if k.endswith("_dissipated_energy_pJ")
    )


@pytest.mark.parametrize("arm", ["release", "clamped"])
def test_device_diagnostics_match_host_check_values_on_accepted_rows(arm, runs):
    spec, history, p = runs[arm]
    assert np.any(np.abs(history.channel_transferred[-1]) > 0)  # The channels conduct.
    failed, values = device_rows(spec, history, p)
    assert not failed.any()
    tol = np.asarray(spec.execution.material_balance_atol_fmol)
    bounds = {  # Smallest bound of each rounding residual (host bounds).
        "max_balance_error_fmol": tol.min(),
        "max_extracellular_balance_error_fmol": tol.min(),
        "max_global_balance_error_fmol": tol.min(),
        "max_capacitor_charge_error_C": surface_field.CHARGE_ATOL_C,
        "max_electrode_charge_error_C": surface_field.CHARGE_ATOL_C,
        "max_global_charge_error_C": surface_pump.GLOBAL_CHARGE_ATOL_C,
        "max_reservoir_work_error_pJ": 3e-12,
        "max_electrode_work_error_pJ": 3e-12,
        "max_metabolic_work_error_pJ": 3e-12,
        "max_global_charge_bound_ratio": 1.0,
    }
    for j in range(len(history.amount_increment)):
        host = MODEL.check_values(rows_of(history, j, j + 1), spec, steps=[j])
        assert list(host) == list(MODEL.DEVICE_DIAGNOSTICS)
        device = dict(zip(MODEL.DEVICE_DIAGNOSTICS, values[j], strict=True))
        for key, value in host.items():
            if key in bounds:
                assert abs(device[key] - value) <= 0.02 * bounds[key], (arm, j, key)
            else:  # Energy residual: a truncation quantity, not a rounding one.
                assert abs(device[key] - value) <= 1e-9 * abs(value) + 1e-15, (arm, j, key)
    # Both pass the whole run as one history, as a window checks it.
    MODEL.check_values(history, spec, steps=np.arange(len(history.amount_increment)))


def test_device_bounds_are_the_host_bounds_at_hour_scale_step_counts(runs):
    """ledger_limits with channel_magnitudes, on host arrays and traced on the device."""
    spec, history, p = runs["clamped"]
    row = type(history)(*(v[-1] for v in history))
    tol = np.asarray(spec.execution.material_balance_atol_fmol)
    rtol = surface_pump.ENERGY_RTOL[spec.execution.solver]
    steps = HOUR + len(history.amount_increment) - 1

    def limits(row, p):
        magnitudes = MODEL.channel_magnitudes(row, p, xp=jnp)
        return surface_pump.ledger_limits(
            row, p, tol, rtol, steps=steps, magnitudes=magnitudes, xp=jnp
        )

    host_flows, host = surface_pump.ledger_limits(
        row, p, tol, rtol, steps=steps, magnitudes=MODEL.channel_magnitudes(row, p)
    )
    device_flows, device = jax.jit(limits)(row, p)
    np.testing.assert_allclose(device_flows, host_flows, rtol=1e-13)
    _, fixed = surface_pump.ledger_limits(
        row, p, tol, rtol, steps=0, magnitudes=MODEL.channel_magnitudes(row, p)
    )
    for name, a, b, c in zip(surface_pump.LEDGERS, device, host, fixed, strict=True):
        np.testing.assert_allclose(np.asarray(a), np.asarray(b), rtol=1e-13, err_msg=name)
        if name in ("local", "outside", "total", "reservoir_work", "metabolic_work"):
            b, c = np.asarray(b), np.asarray(c)  # The hour's allowance (none on padding).
            assert np.all(b >= c) and np.any(b > c), name
    # The hour-scale rows pass on both, with the host's verdict per row.
    failed, _ = device_rows(spec, history, p, offset=HOUR)
    assert not failed.any()
    MODEL.check_values(history, spec, steps=HOUR + np.arange(len(history.amount_increment)))


def seeded(history, p, spec, fault):
    """A copy of the history with one fault (from ROW on, or at ROW only)."""
    values = {k: np.array(v, copy=True) for k, v in history._asdict().items()}
    species = list(spec.model.species_ids)
    na, k = species.index("Na"), species.index("K")
    tol = min(spec.execution.material_balance_atol_fmol)
    held = int(np.flatnonzero(p.reservoir)[0])
    layout = surface_tissue.field_layout(p)
    n = p.active.size
    floating = int(np.flatnonzero(surface_field.representatives(layout))[0]) - n
    free = int(np.flatnonzero(np.asarray(p.outside_active) & ~np.asarray(p.reservoir))[0])
    laws = np.asarray(p.channel_laws)
    gated = np.asarray(p.channel_gate_active)
    active = np.asarray(p.channel_active)
    kv = 0  # channel_0: Kv1.5 (K) on patch 0.
    leak = int(np.flatnonzero(active & ~gated[0])[0])  # A gate-free leak population.
    padding = int(np.flatnonzero(~active)[0])
    assert gated[:, kv].all() and laws[leak] >= 3 and not gated[:, leak].any()
    after = slice(ROW, None)

    def add(name, index, delta, rows=after):
        values[name][(rows, *index)] += delta

    if fault == "domain_nan":
        add("amount_increment", (k, 0), np.nan)
    elif fault == "gate_above_one":  # A Kv1.5 activation gate leaves [0, 1].
        values["channel_gate"][after, 0, kv] = 1.0 + 1e-9
    elif fault == "gate_below_zero":
        values["channel_gate"][after, 1, kv] = -1e-12
    elif fault == "leak_gate":  # A gate-free leak population acquires a gate state.
        values["channel_gate"][after, 0, leak] = 0.5
    elif fault == "padding_transfer":  # The padding slot carries hidden material.
        add("channel_transferred", (k, padding), 1e-15)
    elif fault == "absent_species_transfer":  # Na through the K-only Kv1.5 population.
        add("channel_transferred", (na, kv), 1e-15)
    elif fault == "absent_route_heat":
        add("channel_dissipated_energy_pJ", (na, kv), 1e-15)
    elif fault == "channel_transfer":  # K booked through Kv1.5 that no inventory holds.
        add("channel_transferred", (k, kv), 1e-6)
    elif fault == "channel_transfer_outside":  # Taken from the cell, never delivered.
        add("channel_transferred", (k, kv), 1e-6)
        add("amount_increment", (k, int(p.membrane_cell[p.channel_membranes[kv]])), -1e-6)
    elif fault == "outside":
        add("extracellular_amount_increment", (k, free), 1e-6)
    elif fault == "total":  # Each inventory within its bound, their sum not.
        add("amount_increment", (k, 0), 0.6 * tol)
        add("extracellular_amount_increment", (k, free), 0.6 * tol)
    elif fault == "charge":  # Net charge in a floating component, below the material
        # bound: 5e-12 fmol of K is 5e-22 C, 8x the component's allowance after an hour.
        add("extracellular_amount_increment", (k, floating), 5e-12)
    elif fault == "electrode":
        add("electrode_charge_transferred_C", (held,), 1e-18)
    elif fault == "global_charge":  # Supply below the material bound; its charge is not.
        add("reservoir_supplied", (k, held), 1e-12)
    elif fault == "energy":  # Channel heat that no flow produced, increasing.
        add("channel_dissipated_energy_pJ", (k, kv), 1e-3)
    elif fault == "reservoir_work":
        add("reservoir_work_pJ", (held,), 1e-10)
    elif fault == "electrode_work":
        add("electrode_work_pJ", (held,), 1e-10)
    elif fault == "metabolic_work":  # The calcium pump's half of the metabolic ledger.
        add("calcium_metabolic_work_pJ", (int(np.argmax(p.calcium_pump_present)),), 1e-10)
    elif fault == "dissipation":  # Falls 2e-12 below the previous row; energy in bound.
        array = values["face_dissipated_energy_pJ"]
        array[ROW, 0] = array[ROW - 1, 0] - 2e-12
    elif fault == "channel_dissipation":  # Kv1.5 heat rebooked to its patch from ROW on.
        array = values["channel_dissipated_energy_pJ"]  # So the energy ledger holds and
        moved = array[ROW, k, kv] - array[ROW - 1, k, kv] + 2e-12  # only ROW decreases.
        array[after, k, kv] -= moved
        add("membrane_dissipated_energy_pJ", (int(p.channel_membranes[kv]),), moved)
    else:
        raise ValueError(fault)
    return type(history)(**values)


DOMAIN = surface_pump.DOMAIN_MESSAGE
LEDGER = surface_pump.LEDGER_MESSAGE
FAULTS = {
    "domain_nan": DOMAIN,
    "gate_above_one": DOMAIN,
    "gate_below_zero": DOMAIN,
    "leak_gate": DOMAIN,
    "padding_transfer": DOMAIN,
    "absent_species_transfer": DOMAIN,
    "absent_route_heat": DOMAIN,
    "channel_transfer": LEDGER + "local",
    "channel_transfer_outside": LEDGER + "outside",
    "outside": LEDGER + "outside",
    "total": LEDGER + "total",
    "charge": LEDGER + "charge",
    "electrode": LEDGER + "electrode",
    "global_charge": LEDGER + "global_charge",
    "energy": LEDGER + "energy",
    "reservoir_work": LEDGER + "reservoir_work",
    "electrode_work": LEDGER + "electrode_work",
    "metabolic_work": LEDGER + "metabolic_work",
    "dissipation": surface_pump.DISSIPATION_MESSAGE,
    "channel_dissipation": surface_pump.DISSIPATION_MESSAGE,
}


def test_seeded_faults_cover_every_device_check():
    found = {MODEL.DEVICE_CHECKS.index("domain")} | {
        MODEL.DEVICE_CHECKS.index(m.removeprefix(LEDGER)) for m in FAULTS.values() if LEDGER in m
    }
    found.add(MODEL.DEVICE_CHECKS.index("dissipation"))
    assert found == set(range(len(MODEL.DEVICE_CHECKS)))


@pytest.mark.parametrize("offset", [0, HOUR])
@pytest.mark.parametrize("fault", FAULTS)
def test_seeded_fault_gets_the_same_verdict_on_host_and_device_row_for_row(fault, offset, runs):
    spec, history, p = runs["clamped"]
    corrupted = seeded(history, p, spec, fault)
    failed, _ = device_rows(spec, corrupted, p, offset)
    rows = len(history.amount_increment)
    host = [host_verdict(spec, corrupted, j, offset) for j in range(rows)]
    assert device_verdicts(failed) == host, (fault, failed[ROW])
    single = fault.endswith("dissipation")  # A decrease at ROW only; the rest persist.
    expected = [
        FAULTS[fault] if j == ROW or (j > ROW and not single) else None for j in range(rows)
    ]
    assert host == expected, fault
    # The host check of the whole history (one window) raises the same message.
    with pytest.raises(NumericalError) as caught:
        MODEL.check_values(corrupted, spec, steps=offset + np.arange(rows))
    assert str(caught.value) == FAULTS[fault]
