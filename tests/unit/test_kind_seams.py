"""Schema A's kind seams with the planted kind (docs/INNER_MODEL_V4_DESIGN.md §7.4 (j), (k)).

tests/kind_fixtures.py's `tests.exchange@1` moves a neutral species B at a constant rate from a
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

from cells.core import kind_registry
from cells.core.inventory_species import add_inventory_species
from cells.core.runner import run
from cells.core.specs import ConfigError, parse_spec
from cells.models import surface_pump_v3
from cells.models.registry import get_model
from tests import kind_fixtures
from validation.tissue import pump_water_fixtures as water_fixtures

RATE = 1e-3  # fmol/s, small against B's 1 fmol in the cell.


def world(**kwargs):
    raw = water_fixtures.heredity_cell("D", end_time=0.004)
    raw = add_inventory_species(raw, "B", trace_mM=1.0, diffusivity_m2_per_s=1e-10, floor_fmol=1e-12)
    return kind_fixtures.declare(raw, rate=RATE, **kwargs)


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

    from cells.io import write_snapshot

    with kind_registry.scope(kind_fixtures.registry()):
        spec = parse_spec(world())
        result = run(spec)
        path = write_snapshot(tmp_path / "snapshot", spec, result.final)
        moved = float(result.final.state.exchange_moved_fmol[0])
    script = (
        "import sys\n"
        "from cells.core import kind_registry\n"
        "from cells.io import load_snapshot\n"
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
    assert name.startswith("SurfacePumpChannelState") and "tests_exchange" in name


def test_a_planted_kind_runs_on_the_vector_window_path():
    from cells.core import vector_windows
    from cells.core.batch import BatchSpec, WorldSpec
    from cells.core.windows import WindowPolicy

    steps = 4
    with kind_registry.scope(kind_fixtures.registry()):
        spec = parse_spec(world())
        batch = BatchSpec((WorldSpec(1, spec),), 1, 2**53 - 1, 2**53 - 1)
        window = next(
            iter(vector_windows.iter_vector_windows(batch, WindowPolicy(steps, "checkpoints")))
        )
        final = window.checkpoints[1]
        names = get_model(spec.model).STATE_TYPE._fields
        moved = np.asarray(final.state[names.index("exchange_moved_fmol")])
    assert float(np.ravel(moved)[0]) == pytest.approx(RATE * steps * spec.execution.dt, rel=1e-9)
