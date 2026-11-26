"""The looping replay packages' builders and driver (FR-11; validation/replay/; host only).

* The planarian package (docs/LOOPING_REPLAY_DESIGN.md §4): seven heredity cells in H on the
  hexagon(1) sheet, joined by twelve junctions; an electrode in the centre cell under a
  charge-balanced square wave of the declared period; observed rows spanning exactly the last
  period. Its view prepares (with a planted engine source): the loop at the centre cell, the
  hexagons on the cell set, the recording subset with the loop reader's totals, an event for
  each current at the centre cell.
* The driver refuses before any output when the engine runs from a checkout (a package names
  its engine source, so it runs from an execution snapshot).
* The cycle's admission probe answers in the engine's words, prerequisites placed and named.
"""

import math

import pytest

from cells.definitions.specs import parse_spec
from cells.records import run_view
from cells.registry.models import get_model
from validation.replay import driver, planarian

SOURCE = {"revision": "planted-by-the-test", "dirty": False, "from": "a test"}


def test_the_planarian_package(monkeypatch):
    package = planarian.package()
    spec = parse_spec(package.definition)
    assert [c.id for c in spec.model.cells] == [f"cell_{i}" for i in range(7)]
    assert len(spec.model.junctions) == 12
    loop = package.request.loop
    assert (loop.species, loop.cell, loop.period) == ("planarian", "cell_3", planarian.PERIOD_S)
    end = spec.experiment.end_time
    assert end == (planarian.SETTLE + 1) * planarian.PERIOD_S
    (control,) = package.definition["experiment"]["injection_controls"]
    assert control["cell_id"] == loop.cell
    changes = control["schedule"]
    times = [c["time"] for c in changes] + [end]
    charge = math.fsum(c["current_A"] * (b - a) for c, a, b in zip(changes, times, times[1:]))
    assert abs(charge) <= 1e-12 * planarian.CURRENT_A * end  # Charge-balanced.
    observed = spec.experiment.observation_times
    assert (observed[0], observed[-1]) == (end - planarian.PERIOD_S, end)
    assert len(observed) == round(planarian.PERIOD_S / planarian.EVERY_S) + 1
    monkeypatch.setattr(run_view, "_engine_source", lambda root=None: SOURCE)
    _, layout = get_model(spec.model).initial_values(spec)
    plan = run_view.prepare(spec, package.request, layout=layout)
    view = plan.view({"observation": [("chunks/window-0.npz", len(observed))]}, "observations")
    run_view.validate(view)
    sets = {s["id"]: s for s in view["sets"]}
    geometry = sets["cell"]["geometry"]
    assert geometry["kind"] == "polygons" and len(geometry["faces"]) == 7
    assert {r["field"] for r in view["records"]} == set(planarian.FIELDS)
    assert set(run_view.LOOP_TOTALS) <= set(planarian.FIELDS)
    assert {e["kind"] for e in view["events"]} == {"current"}
    assert all(e["at"] == {"cell": loop.cell} for e in view["events"])
    assert view["run"]["engine_models"] == [
        "cells.model.resolved_pump_composite@1",
        "cells.model.resolved_pump_tissue@3",
        "cells.operator.electrode_current_injection@1",
    ]


def test_the_driver_refuses_from_a_checkout(monkeypatch, tmp_path):
    monkeypatch.setattr(run_view, "_engine_source", lambda root=None: None)
    code, record = driver.write("planarian", tmp_path / "out")
    assert (code, record["status"]) == (2, "refused")
    assert "names its engine source" in record["why"]
    assert not (tmp_path / "out").exists()  # Nothing written.


@pytest.mark.parametrize("argv", [[], ["no_such_package", "out"], ["planarian"]])
def test_the_driver_names_its_packages(argv, capsys):
    assert driver.main(argv) == 2
    assert "Usage" in capsys.readouterr().err


def test_the_cycle_probe_asks_the_engine():
    """The cycle's admission probe (validation/replay/cycle_probe.py, host only) gives each
    composition's answer in the engine's words, with any prerequisite an operator requires placed
    before it and named: S5's own composition (the area law, then division) is admitted, and
    insertion takes the membrane state before it."""
    from validation.replay import cycle_probe

    item = cycle_probe.admission(("area", "division"))
    assert (item["admitted"], item["errors"], item["added_prerequisites"]) == (True, [], [])
    inserted = cycle_probe.admission(("insertion", "division"))
    assert inserted["added_prerequisites"] == ["cells.operator.membrane_entity_state@1"]
    assert inserted["laws"][0] == "cells.operator.membrane_entity_state@1"
