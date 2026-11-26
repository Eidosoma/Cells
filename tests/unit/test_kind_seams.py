"""Schema A's kind seams with the planted kind (docs/INNER_MODEL_V4_DESIGN.md §7.4 (j), (k)).

tests/kind_fixtures.py's `tests.kind.exchange@1` moves a neutral species B at a constant rate from a
heredity cell to its outside node, registered from outside src/cells on a test-local registry.
Through the runner, the IMEX step:
- every hook runs;
- the move lands in the shared inventory, and the kind's accumulators record it;
- the host checks pass: the ledgers close with its terms folded in by role, and its fields are
  observation columns;
- the moved rows join @3's moved_rows;
- a charged species is refused by its definition check.
"""

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.execution.runner import run
from cells.models import surface_pump_v3
from cells.registry import kind_registry
from cells.registry.inventory_species import add_inventory_species
from cells.registry.models import get_model
from tests import kind_fixtures
from validation.tissue import pump_water_fixtures as water_fixtures

RATE = 1e-3  # fmol/s, small against B's 1 fmol in the cell.


def world(rate=RATE, **kwargs):
    raw = water_fixtures.heredity_cell("D", end_time=0.004)
    raw = add_inventory_species(
        raw, "B", trace_mM=1.0, diffusivity_m2_per_s=1e-10, floor_fmol=1e-12
    )
    return kind_fixtures.declare(raw, rate=rate, **kwargs)


def test_the_planted_kind_runs_every_seam():
    kind_fixtures.CALLS.clear()
    with kind_registry.scope(kind_fixtures.registry()):
        spec = parse_spec(world())
        model = get_model(spec.model)
        assert [k for k, _ in model.structure.kinds] == [kind_fixtures.KIND_ID]
        assert "exchange_moved_fmol" in model.STATE_TYPE._fields
        result = run(spec)
        final = result.final.state
        moved = float(final.exchange_moved_fmol[0])
        assert moved == pytest.approx(RATE * spec.experiment.end_time, rel=1e-9)
        row = list(spec.model.species_ids).index("B")
        cell_b = float(final.amount_increment[row, 0])
        assert cell_b == pytest.approx(-moved, rel=1e-9)  # The move is in the shared inventory.
        assert "exchange_moved_fmol" in result.history._fields
        movers = surface_pump_v3.moved_rows(spec.model)["B"]
        assert any(entry[0] == kind_fixtures.KIND_ID for entry in movers)
    called = {k for k, v in kind_fixtures.CALLS.items() if v}
    expected = {
        "parse", "initial", "control_values", "stage_read", "rates", "book", "ledger_terms",
        "domain", "readouts", "moved_rows", "check_definition",
    }  # fmt: skip
    assert expected <= called, expected - called


def test_a_charged_species_is_refused_by_the_kind_check():
    with kind_registry.scope(kind_fixtures.registry()):
        with pytest.raises(ConfigError, match="neutral species only"):
            parse_spec(world(species="Na"))


def test_a_planted_kind_snapshot_round_trips_in_a_fresh_process(tmp_path):
    import subprocess
    import sys

    from cells.records.io import write_snapshot

    with kind_registry.scope(kind_fixtures.registry()):
        spec = parse_spec(world())
        result = run(spec)
        path = write_snapshot(tmp_path / "snapshot", spec, result.final)
        moved = float(result.final.state.exchange_moved_fmol[0])
    script = (
        "import sys\n"
        "from cells.registry import kind_registry\n"
        "from cells.records.io import load_snapshot\n"
        "from tests import kind_fixtures\n"
        "with kind_registry.scope(kind_fixtures.registry()):\n"
        "    snapshot = load_snapshot(sys.argv[1])\n"
        "state = snapshot.checkpoint.state\n"
        "print(repr(float(state.exchange_moved_fmol[0])), type(state).__name__)\n"
    )
    done = subprocess.run(
        [sys.executable, "-c", script, str(path)], capture_output=True, text=True, check=True
    )
    value, name = done.stdout.split()
    assert float(value) == moved
    assert name.startswith("SurfacePumpChannelState") and "tests_kind_exchange" in name


CARRIED_FMOL_S = 1e-3  # K+ carried out of the cell (about 140 fmol of K inside).
CARRIER_END_S = 0.004


def carrier_world():
    """Heredity cell D facing its held bath with every route, channel and pump at availability
    0, so the planted carrier is the only charge mover; capacitor C between cell and bath."""
    raw = water_fixtures.heredity_cell("D", end_time=CARRIER_END_S)
    for group in ("membrane_controls", "channel_controls", "pump_controls"):
        for entry in raw["experiment"][group]:
            entry["schedule"] = [dict(time=0.0, availability=0.0)]
    return kind_fixtures.declare_carrier(raw, species="K", rate=CARRIED_FMOL_S)


def test_a_charged_planted_kind_closes_charge_field_and_ledgers():
    """B5's charged role in miniature (§7.4 (k), rule (c)): K+ carried across the patch.

    - material: the cell loses what the kind records, and the held bath absorbs it as supply;
    - charge and field: the cell's charge falls by z F n, the bath's electrode answers it, and
      the membrane voltage falls by exactly z F n / C, the capacitor's closed form;
    - ledgers: every row passed the host checks, the energy ledger with the kind's work at the
      stage potentials (chemical and electrical);
    - the planted error (the electrical part of the work left out) fails the energy ledger.
    """
    from cells.execution.errors import NumericalError
    from cells.laws.electrochemistry import CHARGE_PER_FMOL
    from validation.tissue.surface_pump_v3_fixtures import HEREDITY_CAPACITANCE_F

    with kind_registry.scope(kind_fixtures.registry(kind_fixtures.carrier())):
        spec = parse_spec(carrier_world())
        model = get_model(spec.model)
        assert [k for k, _ in model.structure.kinds] == [kind_fixtures.CARRIER_ID]
        result = run(spec)  # Host checks on every accepted row: all ten ledgers.
        final, obs = result.final.state, result.observations
        state, p = model.initial_values(spec)
        control = model.Control(*(v[0] for v in control_values(spec, [0.0])))
        current_A = model.readouts(state, control, p, xp=np).field.rates.membrane_current_A
        movers = surface_pump_v3.moved_rows(spec.model)["K"]
        assert any(entry[0] == kind_fixtures.CARRIER_ID for entry in movers)
    k = list(spec.model.species_ids).index("K")
    moved = CARRIED_FMOL_S * CARRIER_END_S
    assert float(final.carrier_transferred[k, 0]) == pytest.approx(moved, rel=1e-12)
    assert float(final.amount_increment[k, 0]) == pytest.approx(-moved, rel=1e-12)
    assert float(final.reservoir_supplied[k, 0]) == pytest.approx(-moved, rel=1e-12)
    for name, value in final._asdict().items():  # No other route moved anything.
        if name.endswith("_transferred") and name != "carrier_transferred":
            assert not np.any(np.asarray(value)), name
    charge = CHARGE_PER_FMOL * moved  # z = 1
    assert float(final.electrode_charge_transferred_C[0]) == pytest.approx(charge, rel=1e-9)
    dv = float(obs.membrane_voltage_V[-1, 0] - obs.membrane_voltage_V[0, 0])
    assert dv == pytest.approx(-charge / HEREDITY_CAPACITANCE_F, rel=1e-9)
    assert float(obs.carrier_current_A[-1, 0]) == pytest.approx(CHARGE_PER_FMOL * CARRIED_FMOL_S)
    # Gap 9: the kind's patch flux joins the patch's total flux and membrane current.
    assert float(obs.membrane_flux_fmol_s[-1, k, 0]) == pytest.approx(CARRIED_FMOL_S)
    assert float(current_A[0]) == pytest.approx(CHARGE_PER_FMOL * CARRIED_FMOL_S)
    work = float(final.carrier_work_pJ[0])
    assert work < 0  # K+ runs down its electrochemical gradient out of D.
    assert result.diagnostics["max_energy_balance_relative"] < 1e-3

    with kind_registry.scope(kind_fixtures.registry(kind_fixtures.carrier(electrical=False))):
        with pytest.raises(NumericalError, match="accounting failed: energy"):
            run(parse_spec(carrier_world()))


def test_a_planted_kind_runs_on_the_vector_window_path():
    from cells.execution import vector_windows
    from cells.execution.batch import BatchSpec, WorldSpec
    from cells.execution.windows import WindowPolicy

    steps, big = 4, 2**53 - 1
    with kind_registry.scope(kind_fixtures.registry(kind_fixtures.carrier())):
        specs = [  # Two value twins packed in one window, each declaring both planted kinds.
            parse_spec(
                kind_fixtures.declare_carrier(world(rate=scale * RATE), rate=scale * CARRIED_FMOL_S)
            )
            for scale in (1.0, 2.0)
        ]
        model = get_model(specs[0].model)
        assert get_model(specs[1].model) is model
        assert [kind for kind, _ in model.structure.kinds] == [
            kind_fixtures.CARRIER_ID,
            kind_fixtures.KIND_ID,
        ]  # Canonical order (sorted ID), not the order the model block names them.
        batch = BatchSpec(tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs)), 2, big, big)
        window = next(
            iter(vector_windows.iter_vector_windows(batch, WindowPolicy(steps, "checkpoints")))
        )  # Every row of both worlds passed the device checks, the kinds' terms included.
        names = model.STATE_TYPE._fields
        k = list(specs[0].model.species_ids).index("K")
        for world_id, scale in ((1, 1.0), (2, 2.0)):
            final = window.checkpoints[world_id].state
            moved = float(np.ravel(final[names.index("exchange_moved_fmol")])[0])
            carried = float(np.asarray(final[names.index("carrier_transferred")])[k, 0])
            time = steps * specs[0].execution.dt
            assert moved == pytest.approx(scale * RATE * time, rel=1e-9)
            assert carried == pytest.approx(scale * CARRIED_FMOL_S * time, rel=1e-9)
