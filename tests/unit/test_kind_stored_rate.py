"""The stored-rate term in the stage energy-rate observation (INNER_MODEL_V4_DESIGN.md §7.4 (m)).

tests/kind_fixtures.py's `tests.kind.conversion@1` converts a neutral S1 into a neutral S2 at a heredity
cell at a constant rate, with declared standard potentials that @3's RT ln c terms leave out and no
stage read carries: finite fuel's bookkeeping in miniature. It stores the standard part
(mu°_P - mu°_S) x moved (ledger_terms' stored_pJ) and gives its rate (KindRates.stored_pJ_s):
- the stage energy-rate observation, energy_balance_pJ_s, closes to rounding with the rate, and
  without it is off by exactly minus the stored rate, while the cumulative energy ledger closes in
  both (the host checks of every accepted row);
- through the runner every ledger closes, the material moves land at the cell, and the observed
  rows' residuals are zero to rounding.
"""

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.execution.runner import run
from cells.laws.electrochemistry import R
from cells.registry import kind_registry
from cells.registry.inventory_species import add_inventory_species
from cells.registry.models import get_model
from tests import kind_fixtures as kf
from validation.tissue import pump_water_fixtures as water_fixtures

RATE = 1e-3  # fmol/s, small against S's amount in the cell.
DROP_RT = -20.0  # mu°_P - mu°_S over RT: a strongly downhill conversion.


def world():
    raw = water_fixtures.heredity_cell("D", end_time=0.004)
    for species in ("S1", "S2"):
        raw = add_inventory_species(
            raw, species, trace_mM=1.0, diffusivity_m2_per_s=1e-10, floor_fmol=1e-12
        )
    return kf.declare_conversion(
        raw, rate=RATE, substrate_mu_RT=0.0, product_mu_RT=DROP_RT, substrate="S1", product="S2"
    )


def stored_rate(spec):
    """The conversion's stored rate (pJ/s): its standard part's rate, 1e-3 x r x (mu°_P - mu°_S)."""
    return 1e-3 * RATE * R * spec.model.temperature_K * DROP_RT


def initial_residual(*, stored):
    with kind_registry.scope(kf.registry(kf.conversion(stored_rate=stored))):
        spec = parse_spec(world())
        impl = get_model(spec.model)
        state, p = impl.initial_values(spec)
        control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
        field = impl.readouts(state, control, p, xp=np).field
    return spec, float(field.energy_balance_pJ_s)


def test_the_stored_rate_closes_the_stage_energy_rate():
    spec, closed = initial_residual(stored=True)
    _, open_ = initial_residual(stored=False)
    rate = stored_rate(spec)
    assert rate < -1e-6  # The term matters: about -5e-5 pJ/s here.
    assert abs(closed) <= 1e-9 * abs(rate)
    assert open_ - closed == pytest.approx(-rate, rel=1e-9)  # Exactly the omitted rate.


def test_a_kinds_net_production_joins_the_total_ledger():
    """A conversion changes the species' totals, which the global material ledger holds to zero
    for transfers; its `produced` record is what closes it (§7.4 (m))."""
    moved = 2.5e-6  # fmol converted at the first cell: a row the step would make.
    totals = {}
    for produced in (True, False):
        with kind_registry.scope(kf.registry(kf.conversion(produced=produced))):
            spec = parse_spec(world())
            impl = get_model(spec.model)
            state, p = impl.initial_values(spec)
            ids = list(spec.model.species_ids)
            amounts = np.array(state.amount_increment, copy=True)
            amounts[ids.index("S1"), 0] -= moved
            amounts[ids.index("S2"), 0] += moved
            converted = np.zeros_like(np.asarray(state.conversion_moved_fmol))
            converted[0] = moved
            row = state._replace(amount_increment=amounts, conversion_moved_fmol=converted)
            ledgers = impl.balances(row, p)
            assert np.all(ledgers["local"] == 0.0)  # Both close the node ledgers.
            totals[produced] = ledgers["total"]
            device = impl.device_balances(row, p)["total"]  # The device's rows fold it alike.
            assert np.array_equal(np.asarray(device), ledgers["total"])
    assert np.all(totals[True] == 0.0)
    unclosed = totals[False]
    assert unclosed[ids.index("S1")] == -moved and unclosed[ids.index("S2")] == moved


def test_every_ledger_closes_and_the_observed_rows_stay_closed():
    with kind_registry.scope(kf.registry(kf.conversion())):
        spec = parse_spec(world())
        result = run(spec)  # Host checks on every accepted row: all ten ledgers.
    final = result.final.state
    moved = float(final.conversion_moved_fmol[0])
    assert moved == pytest.approx(RATE * spec.experiment.end_time, rel=1e-12)
    ids = list(spec.model.species_ids)
    assert float(final.amount_increment[ids.index("S1"), 0]) == pytest.approx(-moved, rel=1e-12)
    assert float(final.amount_increment[ids.index("S2"), 0]) == pytest.approx(moved, rel=1e-12)
    residuals = np.asarray(result.observations.energy_balance_pJ_s)
    assert np.all(np.abs(residuals) <= 1e-9 * abs(stored_rate(spec)))


def test_the_device_ledgers_take_the_net_production_on_the_vector_window_path():
    from cells.execution import vector_windows
    from cells.execution.batch import BatchSpec, WorldSpec
    from cells.execution.windows import WindowPolicy

    big = 2**53 - 1
    with kind_registry.scope(kf.registry(kf.conversion())):
        spec = parse_spec(world())
        batch = BatchSpec((WorldSpec(1, spec),), 1, big, big)
        window = next(  # Every row passed the device checks, the total ledger included.
            iter(vector_windows.iter_vector_windows(batch, WindowPolicy(8, "checkpoints")))
        )
        names = get_model(spec.model).STATE_TYPE._fields
    final = window.checkpoints[1].state
    moved = float(np.ravel(final[names.index("conversion_moved_fmol")])[0])
    assert moved == pytest.approx(RATE * spec.experiment.end_time, rel=1e-12)
