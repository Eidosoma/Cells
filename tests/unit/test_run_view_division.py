"""The run view of a division through the windowed path (docs/RUN_VIEW_DESIGN.md §5).

S5's compact partition world (tests/partition_fixtures.py; partition sources only, never a J1
source: the J2 bright line): the parent's slot retires and the daughters' slots are born at the
division, from living_intervals; the events name the parent and both daughters. The partition
retires slots, so the inner ledgers restart at zero on a retired slot (its history moves into the
partition's record): their records say so and claim no monotonicity, and the reader's check
passes on the saved arrays. Door S: the masks the partition closes, every mask closure reaches and
the fields it pads, and the fields the membrane state provides, are records of the merged view at
each observed row (view_<field>), never constants, and bitwise the views the host observer formed
for those rows (across the run's two windows); the row saved at the division's time holds the state
before it (time.event_rows).

The membrane state's and the partition's view declarations are planted for the test only.
"""

import json

import numpy as np
import pytest

from cells import run_view
from cells.core.specs import parse_spec
from cells.core.windows import WindowPolicy
from cells.window_io import write_windowed_run
from tests import partition_fixtures as pf
from tests.run_view_fixtures import (
    PARTITION,
    STATE,
    capture,
    declare_division,
    observed,
    same_as_observed,
)


@pytest.fixture
def declared(monkeypatch):
    declare_division(monkeypatch)


def test_a_division_through_the_windowed_path(declared, monkeypatch, tmp_path):
    raw = pf.divided()
    raw["experiment"]["observation_times"] = [0.0, 0.001, 0.002, 0.003, 0.004]
    spec = parse_spec(raw)
    seen = capture(monkeypatch)
    write_windowed_run(tmp_path / "w", spec, WindowPolicy(2, "full"), view=run_view.Request())
    view = json.loads((tmp_path / "w" / run_view.FILE).read_text())
    run_view.validate(view, tmp_path / "w")  # The saved arrays: no monotonicity is claimed.
    sets = {s["id"]: s for s in view["sets"]}
    lives = dict(zip(sets["cell"]["ids"], sets["cell"]["lifetimes"], strict=True))
    assert lives["cell_0"] == [None, pf.EVENT]
    assert lives["d1"] == lives["d2"] == [pf.EVENT, None]
    assert [(e["time"], e["kind"], e["at"], e["layer"]) for e in view["events"]] == [
        (pf.EVENT, "birth", {"cell": "d1"}, "division"),
        (pf.EVENT, "birth", {"cell": "d2"}, "division"),
        (pf.EVENT, "retirement", {"cell": "cell_0"}, "division"),
    ]
    records = {r["id"]: r for r in view["records"]}
    # The ledgers the partition writes restart on a retired slot (the parent's membrane heat
    # falls to 0 at the division); the heat it does not write keeps its monotone claim, which
    # the reader's check above confirmed on the saved arrays.
    for name, mask in (
        ("membrane_dissipated_energy_pJ", "membrane_active"),
        ("channel_dissipated_energy_pJ", "channel_active"),
    ):
        assert records[name]["resets"]["by"] == [PARTITION] and "monotone" not in records[name]
        assert records[name]["resets"]["mask"] == mask
    assert records["observed_membrane_transferred"]["resets"]["by"] == [PARTITION]
    for name in ("pump_dissipated_energy_pJ", "face_dissipated_energy_pJ"):
        assert records[name]["monotone"] == "non-decreasing" and "resets" not in records[name]
    assert "resets" not in records["observed_amount"]  # Not a cumulative ledger.
    unstated = {(u["id"], u["what"]) for u in view["unstated"]}
    assert ("partition_retired_membrane_heat_pJ", "kind") in unstated
    assert sets["division"]["ids"] == ["first"]
    # Door S: what the composition's merge changes is recorded at each observed row.
    merged = {r["field"]: r for r in view["records"] if r["id"].startswith(run_view.VIEW_PREFIX)}
    assert set(merged) == {
        "active",
        "outside_active",
        "membrane_active",
        "channel_active",
        "junction_active",
        "face_active",
        "extracellular_amount_reference",
        "initial_cell_charge_C",
        "membrane_area",
        "membrane_capacitance",
        "channel_abundance",
    }
    assert merged["membrane_active"]["writers"] == [PARTITION]
    assert merged["membrane_active"]["layer"] == "division"
    assert merged["membrane_area"]["owner"] == STATE
    assert merged["active"]["base"] == "observation" and merged["active"]["kind"] == "level"
    assert not {c["id"] for c in view["constants"]} & set(merged)
    assert len(seen) == 5 and same_as_observed(tmp_path / "w", view, seen) == len(merged)
    assert not [u for u in view["unstated"] if u["what"] == "view field"]
    # The row saved at the division's time holds the state before it, the next row after it.
    assert view["time"]["event_rows"] == run_view.EVENT_ROWS
    times, active = observed(tmp_path / "w", view, "view_active")
    at = times.tolist().index(pf.EVENT)
    cells = sets["cell"]["ids"]
    assert dict(zip(cells, active[at].tolist(), strict=True)) == {
        "cell_0": True,
        "d1": False,
        "d2": False,
    }
    assert dict(zip(cells, active[at + 1].tolist(), strict=True)) == {
        "cell_0": False,
        "d1": True,
        "d2": True,
    }
    # The membrane slots whose heat restarts at the division are those whose merged mask closes
    # there (resets.mask): the parent's patch.
    times, heat = observed(tmp_path / "w", view, "membrane_dissipated_energy_pJ", "accepted")
    _, open_ = observed(tmp_path / "w", view, "view_membrane_active")
    row = times.tolist().index(pf.EVENT)
    restarted = (heat[row] > 0) & (heat[row + 1] == 0)
    closed = open_[at] & ~open_[at + 1]
    patches = sets["membrane"]["ids"]
    assert [patches[i] for i in np.flatnonzero(restarted)] == ["membrane_0"]
    assert np.array_equal(restarted, closed)
    # A membrane voltage is a difference: its cell's potential less its outside node's, on the
    # open patches (records["observed_membrane_voltage_V"]["difference"]).
    _, voltage = observed(tmp_path / "w", view, "observed_membrane_voltage_V")
    _, inside = observed(tmp_path / "w", view, "observed_cell_potential_V")
    _, outside = observed(tmp_path / "w", view, "observed_extracellular_potential_V")
    cell_of = sets["membrane"]["geometry"]["index"]
    node_of = sets["membrane"]["outside"]["index"]
    expected = inside[:, cell_of] - outside[:, node_of]
    assert np.abs(voltage[open_]).max() > 1e-3  # Nonzero: the check is not empty.
    assert np.allclose(voltage[open_], expected[open_], rtol=1e-12, atol=0.0)
    difference = records["observed_membrane_voltage_V"]["difference"]
    assert (difference["plus"], difference["minus"]) == ("inside", "outside")
