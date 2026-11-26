"""Door S's merged view in the run view (cells/records/run_view.py, module docstring; route B).

* A provider: the bath schedule's dose (cells.operator.scheduled_bath_composition@1) is recorded through
  write_run in view_extracellular_amount_reference, bitwise the view the host observer formed for
  each observed row: the held content at the bath, the bound value elsewhere. The row saved at the
  dose's time holds the content before it, the next row after it. (The windowed path, a closer and
  its propagation: test_run_view_division.)
* The recording subset applies to the merged view (its cadence and elements).
* Refused with nothing written: a view field that changes where no change declares it, and an
  observed state column an operator replaces.
* Not covered, and stated with the reason: a run already on disk (write_view) and a run that saved
  no observed rows.

The bath schedule's layer is planted for the tests only.
"""

import copy
import json

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.models import pump_composite
from cells.records import run_view
from cells.records.io import write_run
from cells.registry.models import get_model
from tests.run_view_fixtures import (
    capture,
    layers,
    load,
    plant,
    reference_constants,
    same_as_observed,
)
from validation.tissue import bath_schedule_fixtures as bfx
from validation.tissue import secreted_species_fixtures as fx

BATH = bfx.LAW
DT, END, DOSE = 1e-3, 0.008, 0.004


def merged(view):
    return [r for r in view["records"] if r["id"].startswith(run_view.VIEW_PREFIX)]


@pytest.fixture(scope="module")
def dosed():
    """The bath schedule's dose leg, run once: one cell, a finite node, the held bath dosed with
    cargo S at DOSE; observed at every step. (The run, the views its observer formed.) The bath
    schedule's layer is planted."""
    with pytest.MonkeyPatch.context() as patch:
        plant(patch, BATH, VIEW_LAYERS=layers("bath", "Bath composition"))
        raw = bfx.dosed_world(dt=DT, end=END, observation_times=fx.grid_times(END, DT, DT))
        raw = bfx.with_bath_schedule(raw, ["bath"], bfx.CARGO, [(DOSE, ["bath"], {"cargo": 5e-4})])
        with pytest.MonkeyPatch.context() as watch:
            seen = capture(watch)
            result = run(parse_spec(raw))
        yield result, list(seen)


def test_a_dose_is_recorded_after_the_row_at_its_time(dosed, tmp_path):
    dosed, seen = dosed
    write_run(tmp_path / "r", dosed, view=run_view.Request())
    view = load(tmp_path / "r")
    run_view.validate(view, tmp_path / "r")
    (record,) = merged(view)
    assert record["field"] == "extracellular_amount_reference"
    assert record["writers"] == [BATH] and record["owner"] == BATH and record["layer"] == "bath"
    assert record["axes"] == ["time", "species", "outside"] and record["unit"] == "fmol"
    constants = {c["id"] for c in view["constants"]}
    expected = set(run_view.VIEW_FIELD_AXES) - {"extracellular_amount_reference"}
    assert constants == expected | reference_constants()  # Also the increments' references.
    outside = [s for s in view["sets"] if s["id"] == "outside"][0]["ids"]
    bath, node = outside.index("bath"), outside.index("ecs_0")
    with np.load(tmp_path / "r" / "trajectory.npz") as saved:
        times = saved["observation_times"]
        reference = saved["view_extracellular_amount_reference"]
        held = saved["observed_bath_held_amount_fmol"]
        dose = saved["observed_bath_dose_fmol"]
    bound = np.asarray(dosed.final.layout.extracellular_amount_reference)
    assert np.array_equal(reference[:, :, bath], held[:, :, bath])  # The held content.
    assert np.all(reference[:, :, node] == bound[None, :, node])  # Bound elsewhere.
    at = times.tolist().index(DOSE)
    assert not dose[: at + 1].any() and dose[at + 1 :, :, bath].any()
    assert np.array_equal(reference[at, :, bath], bound[:, bath])  # Before the dose.
    assert not np.array_equal(reference[at + 1, :, bath], bound[:, bath])  # After it.
    assert len(seen) == len(times) and same_as_observed(tmp_path / "r", view, seen) == 1


def test_the_recording_subset_applies_to_the_merged_view(dosed, tmp_path):
    dosed, _ = dosed
    write_run(tmp_path / "all", dosed, view=run_view.Request())
    subset = run_view.Recording(
        fields=("amount", "view_extracellular_amount_reference"),
        elements={"outside": ["bath"]},
        every=2,
    )
    write_run(tmp_path / "s", dosed, view=run_view.Request(recording=subset))
    view = load(tmp_path / "s")
    run_view.validate(view, tmp_path / "s")
    assert [r["id"] for r in merged(view)] == ["view_extracellular_amount_reference"]
    bath = [s for s in view["sets"] if s["id"] == "outside"][0]["ids"].index("bath")
    with np.load(tmp_path / "all" / "trajectory.npz") as saved:
        full = saved["view_extracellular_amount_reference"]
    with np.load(tmp_path / "s" / "trajectory.npz") as saved:
        kept = saved["view_extracellular_amount_reference"]
        assert "observed_bath_held_amount_fmol" not in saved.files
    assert np.array_equal(kept, full[::2][:, :, [bath]])


def test_an_undeclared_change_is_refused_with_nothing_written(dosed, monkeypatch, tmp_path):
    dosed, _ = dosed
    form = pump_composite.Composition.view

    def warmer(self, p, state, **kwargs):  # A change no declaration states.
        q = form(self, p, state, **kwargs)
        return q._replace(temperature=q.temperature + 1.0)

    monkeypatch.setattr(pump_composite.Composition, "view", warmer)
    with pytest.raises(run_view.ViewRefused, match=r"\['temperature'\] differ from their bound"):
        write_run(tmp_path / "r", dosed, view=run_view.Request())
    assert not (tmp_path / "r").exists()


def test_a_replaced_state_column_is_refused(dosed, monkeypatch):
    dosed, _ = dosed
    model = get_model(dosed.spec.model)
    owners = copy.deepcopy(model.field_owners(dosed.spec))
    owners["observations"]["amount_increment"].append("planted_replacer@1")
    monkeypatch.setattr(type(model), "field_owners", lambda self, spec: owners)
    with pytest.raises(run_view.ViewRefused, match="replaces the observed state columns"):
        run_view.prepare(dosed.spec, run_view.Request(), layout=dosed.final.layout)


def test_a_run_on_disk_and_a_run_without_observed_rows_say_why(dosed, tmp_path):
    dosed, _ = dosed
    write_run(tmp_path / "plain", dosed)
    run_view.write_view(tmp_path / "plain")
    view = load(tmp_path / "plain")
    assert not merged(view)
    (why,) = [u["why"] for u in view["unstated"] if u["what"] == "view field"]
    assert why.startswith(f"changed by {BATH}: a run already on disk")
    with np.load(tmp_path / "plain" / "trajectory.npz") as saved:
        assert "view_extracellular_amount_reference" not in saved.files
    plan = run_view.prepare(dosed.spec, run_view.Request(), layout=dosed.final.layout)
    rows = len(dosed.times)
    view = plan.view({"accepted": [("trajectory.npz", rows)]}, "checkpoints")
    run_view.validate(json.loads(run_view.dumps(view)))
    assert not merged(view)
    (why,) = [u["why"] for u in view["unstated"] if u["what"] == "view field"]
    assert why == f"changed by {BATH}: the run saved no observed rows"


def test_a_field_reference_needs_its_unstated_entry(dosed, tmp_path):
    """§9's item 3 (docs/CORE_SEAMS_DESIGN.md): a record whose fixed reference door S changes,
    in a view that saves no merged view of it, names the field, and the view says why under
    unstated; without that entry the reader's check refuses the view (the plant)."""
    dosed, _ = dosed
    write_run(tmp_path / "plain", dosed)
    run_view.write_view(tmp_path / "plain")
    view = load(tmp_path / "plain")
    named = [r for r in view["records"] if r["field"] == "extracellular_amount_increment"]
    assert len(named) == 2  # Its history and its observed column.
    assert all(r["reference"] == {"field": "extracellular_amount_reference"} for r in named)
    run_view.validate(view, tmp_path / "plain")
    view["unstated"] = [u for u in view["unstated"] if u["id"] != "extracellular_amount_reference"]
    with pytest.raises(run_view.ViewInvalid, match="leaves unstated"):
        run_view.validate(view)
