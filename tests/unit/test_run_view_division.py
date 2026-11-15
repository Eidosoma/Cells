"""The run view of a division through the windowed path (docs/RUN_VIEW_DESIGN.md §5).

S5's compact partition world (tests/partition_fixtures.py; partition sources only, never a J1
source: the J2 bright line): the parent's slot retires and the daughters' slots are born at the
division, from living_intervals; the events name the parent and both daughters. The partition
retires slots, so the inner ledgers restart at zero on a retired slot (its history moves into the
partition's record): their records say so and claim no monotonicity, and the reader's check
passes on the saved arrays. The fields operators change are listed as unstated, naming them.

The membrane state's and the partition's view declarations are planted for the test only.
"""

import json

import pytest

from cells import run_view
from cells.core.specs import parse_spec
from cells.core.windows import WindowPolicy
from cells.models.operators import OPERATORS
from cells.window_io import write_windowed_run
from tests import partition_fixtures as pf

PARTITION = "isopotential_partition@1"
STATE = "membrane_entity_state@1"


def plant(patch, law, **declarations):
    for name, value in declarations.items():
        patch.setattr(type(OPERATORS[law]), name, value, raising=False)


def layer(layer_id, label, representation):
    return (dict(id=layer_id, label=label, representation=representation),)


@pytest.fixture
def declared(monkeypatch):
    plant(
        monkeypatch,
        STATE,
        VIEW_LAYERS=layer("membrane_state", "Membrane entity state", "simulated"),
        UNITS={"population_abundance_increment": "1", "population_units": "1"},
        OBSERVATION_AXES={
            "membrane_area_m2": ("membrane_slot",),
            "membrane_capacitance_F": ("membrane_slot",),
            "population_units": ("channel_slot",),
        },
    )
    plant(
        monkeypatch,
        PARTITION,
        VIEW_LAYERS=layer("division", "Cell division", "prescribed"),
        UNITS={"division_applied": "1", "partition_units_moved": "1", "partition_slot_phase": "1"},
        OBSERVATION_AXES={"partition_slot_phase": ("cell_slot",)},
        view_sets=lambda self, spec, declaration: {
            "division_slot": {
                "id": "division",
                "ids": tuple(d.id for d in declaration.divisions),
                "holds": "division",
            }
        },
    )


def test_a_division_through_the_windowed_path(declared, tmp_path):
    raw = pf.divided()
    raw["experiment"]["observation_times"] = [0.0, 0.001, 0.002, 0.003, 0.004]
    spec = parse_spec(raw)
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
    for name in ("membrane_dissipated_energy_pJ", "observed_membrane_transferred"):
        assert records[name]["resets"]["by"] == [PARTITION] and "monotone" not in records[name]
    assert "resets" not in records["observed_amount"]  # Not a cumulative ledger.
    unstated = {(u["id"], u["what"]) for u in view["unstated"]}
    assert ("partition_retired_membrane_heat_pJ", "kind") in unstated
    assert {("active", "view field"), ("membrane_area", "view field")} <= unstated
    assert sets["division"]["ids"] == ["first"]
