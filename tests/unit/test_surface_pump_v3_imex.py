"""cells.model.resolved_pump_tissue@3: IMEX ledgers, orders and restart (a shard of the former file).

One module fixture (`imex_runs`: closed and release arms, both schemes, and the RK4
reference at 2.5 us) serves the ledger, dissipation, order and bitwise-restart tests.
"""

import os

import jax
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.models import surface_pump_v3
from cells.numerics import surface_imex as imex
from cells.records.io import load_snapshot, write_snapshot
from cells.registry.models import get_model
from validation.tissue import surface_pump_v3_fixtures as fixtures

BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
N2 = imex.IMPLICIT_CONDUCTANCES_ID  # FR-8 rung 1 (D235); it runs only beside X2.
SOLVERS = (imex.EULER_ID, imex.ARS222_ID, N2)
CHANNEL_FIELDS = ("channel_gate", "channel_transferred", "channel_dissipated_energy_pJ")
CHANNEL_OBSERVATIONS = (
    *CHANNEL_FIELDS,
    "channel_flux_fmol_s",
    "channel_targets",
    "channel_tau_s",
    "channel_availability",
)


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def scaled_difference(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    scale = max(np.max(np.abs(a), initial=0), np.max(np.abs(b), initial=0))
    return 0.0 if scale == 0 else float(np.max(np.abs(a - b)) / scale)


def selected(raw):
    """N2 runs only with X2 selected (its guard); the other schemes as they are."""
    if raw["execution"]["solver"] == N2:
        raw["execution"]["energy_check"] = dict(
            check="cells.execution.step_doubled_energy@1", integration_error_cap=2e-3
        )
    return raw


def initial(raw):
    spec = parse_spec(raw)
    state, layout = get_model(spec.model).initial_values(spec)
    controls = control_values(spec, [0.0])
    return spec, state, layout, type(controls)(*(v[0] for v in controls))


@pytest.fixture(autouse=True)
def clear_compiled_programs():
    """Release the compiled programs after every test: these tests compile many programs
    and one process otherwise keeps them all (the unsplit file hit a 4 GB cap in tier 3)."""
    yield
    jax.clear_caches()


@pytest.fixture(scope="module")
def imex_runs():
    runs = {
        (arm, solver): run(
            parse_spec(selected(fixtures.definition(arm, solver=solver, backend=BACKEND)))
        )
        for arm in ("closed", "release")
        for solver in SOLVERS
    }
    reference = fixtures.definition("clamped", backend=BACKEND)
    reference["execution"].update(dt=2.5e-6, max_steps=1024)
    runs["clamped", "rk4"] = run(parse_spec(reference))
    for solver in SOLVERS:
        runs["clamped", solver] = run(
            parse_spec(selected(fixtures.definition("clamped", solver=solver, backend=BACKEND)))
        )
    return runs


@pytest.mark.parametrize("arm", ["closed", "clamped", "release"])
@pytest.mark.parametrize("solver", SOLVERS)
def test_imex_ledgers_constraints_and_channel_transfer(arm, solver, imex_runs):
    value = imex_runs[arm, solver]
    d = value.diagnostics
    tol = value.spec.execution.material_balance_atol_fmol
    for key in ("balance", "extracellular_balance", "global_balance"):
        assert d[f"max_{key}_error_fmol"] <= min(tol)
    assert d["max_capacitor_charge_error_C"] <= 3e-25
    assert d["max_global_charge_bound_ratio"] <= 1.0
    assert d["max_reservoir_work_error_pJ"] <= 3e-12 and d["max_metabolic_work_error_pJ"] <= 3e-12
    assert d["max_energy_balance_relative"] <= surface_pump_v3.ENERGY_RTOL[solver]
    # Each cell's K changes by its leak, pump, channel and junction exchange, so
    # the channels move the inventory they are said to move.
    history, k = value.history, value.spec.model.species_ids.index("K")
    _, p = surface_pump_v3.initial_values(value.spec)
    expected = np.zeros_like(history.amount_increment[:, k])
    for transferred, owner, sign in (
        (history.membrane_transferred[:, k], p.membrane_cell, -1),
        (-p.stoichiometry[k] * history.pump_cycles, p.membrane_cell, -1),
        (history.channel_transferred[:, k], p.membrane_cell[p.channel_membranes], -1),
        (history.junction_transferred[:, k], p.junction_sender, -1),
        (history.junction_transferred[:, k], p.junction_receiver, 1),
    ):
        np.add.at(expected, (slice(None), owner), sign * np.asarray(transferred))
    np.testing.assert_allclose(history.amount_increment[:, k], expected, rtol=0, atol=1e-15)
    moved = np.abs(history.channel_transferred[-1]).sum(axis=0)
    assert np.all(moved[p.channel_active] > 0)
    heat = np.asarray(history.channel_dissipated_energy_pJ)
    assert np.all(np.diff(heat.sum(axis=1), axis=0) >= -1e-12)  # The family's tolerance.
    if arm == "release":
        before = value.times <= 0.00073
        assert not np.any(history.channel_transferred[before])
        assert np.all(value.observations.channel_availability[0] == 0)


@pytest.mark.parametrize(
    "solver, tolerance", [(imex.EULER_ID, 2e-2), (imex.ARS222_ID, 1e-3), (N2, 1e-3)]
)
def test_imex_dissipation_and_work_ledgers_track_rk4(solver, tolerance, imex_runs):
    value, reference = imex_runs["clamped", solver], imex_runs["clamped", "rk4"]
    for key in surface_pump_v3.STATE_TYPE._fields:
        if key.endswith(("_dissipated_energy_pJ", "_work_pJ")):
            expected = np.sum(np.asarray(getattr(reference.final.state, key)))
            actual = np.sum(np.asarray(getattr(value.final.state, key)))
            assert abs(actual - expected) <= tolerance * abs(expected) + 3e-12, key


def test_imex_observed_order_against_rk4_with_channels(imex_runs):
    """Euler first and ARS(2,2,2) second order in Vm, channel flux and energy residual; N2, on
    ARS(2,2,2)'s tableau, second order too."""
    reference = imex_runs["clamped", "rk4"].observations
    for solver, order in ((imex.EULER_ID, 1), (imex.ARS222_ID, 2), (N2, 2)):
        errors, energy = [[], []], []
        for dt in (1e-4, 5e-5, 2.5e-5):
            raw = fixtures.definition("clamped", solver=solver, backend=BACKEND)
            raw["execution"]["dt"] = dt
            value = imex_runs["clamped", solver] if dt == 1e-4 else run(parse_spec(selected(raw)))
            assert value.spec.execution.dt == dt
            for row, key in zip(errors, ("membrane_voltage_V", "channel_flux_fmol_s"), strict=True):
                observed, expected = getattr(value.observations, key), getattr(reference, key)
                row.append(float(np.max(np.abs(observed[-1] - expected[-1]))))
            energy.append(value.diagnostics["max_energy_balance_relative"])
        for values in (*errors, energy):
            rates = np.log2(np.asarray(values[:-1]) / np.asarray(values[1:]))
            assert np.all(rates > order - 0.25), (solver, values)


def test_restart_is_bitwise_and_invalid_channel_controls_refuse_the_step(tmp_path, imex_runs):
    value = imex_runs["release", imex.ARS222_ID]
    checkpoint = value.checkpoint_at(0.001)
    write_snapshot(tmp_path / "checkpoint", value.spec, checkpoint)
    loaded = load_snapshot(tmp_path / "checkpoint")
    resumed = run(loaded.spec, loaded.checkpoint)
    for a, b in zip(resumed.history, value.history, strict=True):
        np.testing.assert_array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :])
    spec, state, p, control = initial(fixtures.definition("clamped", solver=imex.ARS222_ID))
    bad = control._replace(channel=np.full_like(control.channel, 1.01))
    kept, valid = jax.jit(surface_pump_v3.checked_step)(state, 1e-4, bad, p, p.active)
    assert not valid
    for a, b in zip(kept, state, strict=True):
        np.testing.assert_array_equal(np.asarray(a), b)
    with pytest.raises(NumericalError):
        surface_pump_v3.check_values(
            state._replace(channel_transferred=state.channel_transferred + 0.01), spec
        )
    gate = state.channel_gate.copy()
    gate[:, -2] = 0.5  # A leak population has no gate state.
    with pytest.raises(NumericalError):
        surface_pump_v3.check_values(state._replace(channel_gate=gate), spec)


@pytest.mark.parametrize(
    "arm, solver",
    [
        ("closed", imex.ARS222_ID),
        ("closed", N2),
        ("clamped", imex.EULER_ID),
        ("release", imex.ARS222_ID),
    ],
)
def test_labelled_step_reports_non_negative_one_way_transfers(arm, solver):
    """FR-42 (host steps, nothing compiled): with labels the step's state and validity are the
    unlabelled call's bit for bit; every one-way amount is >= 0; forward - backward is the booked
    net per entity at rounding. The fixtures' rows are charged, so label_errors refuses them on
    their faces (the transfers are still reported, the gap carrying the faces' electromigration)."""
    spec, state, p, control = initial(fixtures.definition(arm, solver=solver))
    structure, dt = surface_pump_v3.structure(spec.model), spec.execution.dt
    rows = (spec.model.species_ids.index("K"),)
    plain = surface_pump_v3.imex_step(state, dt, control, p, xp=np, structure=structure)
    labelled = surface_pump_v3.imex_step(
        state, dt, control, p, xp=np, structure=structure, labels=rows
    )
    for a, b in zip(plain[0], labelled[0], strict=True):
        np.testing.assert_array_equal(np.asarray(a), np.asarray(b))
    assert bool(plain[1]) == bool(labelled[1]) and bool(plain[1])
    transfers = labelled[2]
    assert len(transfers) == 6 and all(np.all(np.asarray(t[0]) >= 0) for t in transfers)
    for i, field in (
        (0, "face_transferred"),
        (2, "membrane_transferred"),
        (4, "junction_transferred"),
    ):
        net = (np.asarray(getattr(plain[0], field)) - np.asarray(getattr(state, field)))[list(rows)]
        moved = np.asarray(transfers[i][0]) - np.asarray(transfers[i + 1][0])
        np.testing.assert_allclose(moved, net, rtol=0, atol=1e-14 * max(np.max(np.abs(net)), 1e-30))
    assert any(
        "logmean face" in e for e in surface_pump_v3.label_errors(p, rows, structure=structure)
    )
    with pytest.raises(Exception, match="RK4 refuses labels"):
        rk4 = fixtures.definition(arm, solver="rk4")
        spec4, state4, p4, control4 = initial(rk4)
        surface_pump_v3.checked_step(state4, dt, control4, p4, p4.active, labels=rows)


@pytest.mark.parametrize(
    "channels, species, channel_refused, pump_refused",
    [
        (False, "Cl", False, False),  # No channel population: nothing to index, no refusal.
        (True, "K", True, True),  # Carried by the fixture's channels and its Na/K pump.
        (True, "Cl", False, False),  # Not carried by any channel or pump.
    ],
)
def test_label_errors_read_the_species_rows(channels, species, channel_refused, pump_refused):
    """FR-42's refusals read [species, ...] rows: channel_relative_permeability on active
    populations, and the pumps' stoichiometry at patches with a capacity (host side only)."""
    spec, _, p, _ = initial(
        fixtures.definition("release", solver=imex.ARS222_ID, channels=channels)
    )
    errors = surface_pump_v3.label_errors(p, (spec.model.species_ids.index(species),))
    assert any("channel population" in e for e in errors) == channel_refused
    assert any("moved by a pump" in e for e in errors) == pump_refused
