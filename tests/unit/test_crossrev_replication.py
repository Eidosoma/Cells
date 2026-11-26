"""validation/tissue/composite_crossrev.py's replication set (D219).

The set holds quick worlds of the gap-junction replication
(docs/GAP_JUNCTION_CANCER_REPLICATION.md), each built by its driver's own generator
(validation/gap_junction_tissue/). They carry the replication's two neutral transport laws: @3's
neutral permeant species (the linear model's Norton form) and the passive routes' neutral law on a
junction host (the linear model as written and the neither condition's line, sheet and ladder
point). Like crossrev's other sets they are recorded as programs (jaxprs) and bindings, compared
bitwise at every core landing, by the set's own record functions. The last two tests below are the
two blind spots of the other sets' record that those functions close (an external review,
18 November 2026).
- The set builds: every world parses with its driver's model and laws over its first five steps,
  its bindings hold the schedule's timing, and they record themselves again bit for bit.
- A planted parameter changes that world's record, and nothing else in the set's. Each plant is the
  driver's own: every junction permeability x1.01 for the linear model (its planted control, K1),
  and the junction diffusion constant D x1.01 for the neither worlds (the searched parameter; each
  keeps its step).
- Timing: a schedule change one step later, and nothing else, changes the record (its step and
  every step's controls are recorded; the controls at the change times alone would not move).
- Transitions: the device row checks are traced with the previous and the current state as
  independent inputs, beside production's window check program, so a planted change that makes
  the checks compare a row with itself changes all three traces. This traces the smallest world
  only; the gates' crossrev runs trace every world.
"""

import numpy as np
import pytest

from validation.tissue import composite_crossrev as crossrev

PASSIVE = "cells.route.passive_neutral_permeation@1"
REACTIONS = "cells.operator.local_species_reactions@1"
COMPOSITE = "cells.model.resolved_pump_composite@1"
STEPS = 5
# (model, operators, passive routes as (host, species), cells, junctions, step in s)
EXPECTED = {
    "linear_norton": ("cells.model.resolved_pump_tissue@3", set(), set(), 3, 2, 0.125),
    "linear_as_written": (COMPOSITE, {REACTIONS}, {("junction", "S"), ("patch", "S")}, 3, 2, 0.125),
    "neither_line": (COMPOSITE, {REACTIONS}, {("junction", "u")}, 25, 24, 0.125),
    "neither_sheet": (COMPOSITE, {REACTIONS}, {("junction", "u")}, 81, 144, 0.0625),
    "neither_ladder": (COMPOSITE, {REACTIONS}, {("junction", "u")}, 25, 24, 0.03125),
}
TIMING = (
    "steps.dt",
    "timing.grid",
    "timing.change_time",
    "timing.change_step",
    "timing.event_index",
)


def plants():
    """One planted parameter per world, as replication_world's keyword arguments."""
    from validation.gap_junction_tissue import neither

    scale = dict(junction_scale=1.01)
    return {
        "linear_norton": scale,
        "linear_as_written": scale,
        "neither_line": dict(d=1.01 * neither.X2_M2_S),
        "neither_sheet": dict(d=1.01 * neither.X2_M2_S),
        "neither_ladder": dict(d=1.01 * crossrev.REPLICATION_LADDER_D_M2_S),
    }


@pytest.fixture(scope="module")
def honest(tmp_path_factory):
    directory = tmp_path_factory.mktemp("honest")
    crossrev.bindings(directory, "replication")
    return directory


def _differs(capsys, a, b):
    capsys.readouterr()
    same = crossrev.compare(a, b)
    return same, [line for line in capsys.readouterr().out.splitlines() if "DIFFERS" in line]


def test_the_set_builds(honest, tmp_path):
    from cells.definitions.specs import parse_spec

    worlds = crossrev.replication_worlds()
    assert tuple(worlds) == crossrev.REPLICATION and set(worlds) == set(EXPECTED)
    for name, raw in worlds.items():
        model_id, operators, routes, n_cells, n_junctions, dt = EXPECTED[name]
        spec, m = parse_spec(raw), raw["model"]
        assert m["id"] == model_id, name
        assert {op["law"] for op in m.get("operators", [])} == operators, name
        hosts = {
            ("junction" if "junction" in r else "patch", r["species"])
            for r in m.get("passive_routes", [])
        }
        assert hosts == routes and {r["law"] for r in m.get("passive_routes", [])} <= {PASSIVE}
        assert (len(m["cells"]), len(m["junctions"])) == (n_cells, n_junctions), name
        assert {j["gate"]["law"] for j in m["junctions"]} == {
            "cells.junction.junction_voltage_relaxation@1"
        }
        assert all(j["gate"]["minimum_open_fraction"] == 1.0 for j in m["junctions"]), name
        neutral = {s["id"] for s in m["species"] if s["valence"] == 0}
        assert {s for _, s in routes} <= neutral, name
        if (
            model_id == "cells.model.resolved_pump_tissue@3"
        ):  # @3's own route for its neutral permeant species
            assert {s["id"] for s in m["species"]} == {"mR"} <= neutral
            assert {mb["law"] for mb in m["membranes"]} == {"cells.route.constant_field@1"}
            assert {j["law"] for j in m["junctions"]} == {"cells.route.constant_field@1"}
        assert spec.execution.dt == dt, name
        changes = [c.time for c in spec.experiment.changes]
        assert spec.experiment.end_time == STEPS * dt and set(changes) <= {0.0}, name
        with np.load(honest / f"{name}.npz") as record:  # The schedule's timing, step by step.
            assert set(TIMING) <= set(record.files), name
            assert record["timing.grid"].tolist() == [k * dt for k in range(STEPS + 1)], name
            assert record["steps.dt"].tolist() == [dt] * STEPS, name
            assert record["timing.change_step"].tolist() == [0] * len(changes), name
            assert record["timing.event_index"].tolist() == [len(changes) - 1] * STEPS, name
            controls = [k for k in record.files if k.startswith("steps.control.")]
            assert controls and all(record[k].shape[0] == STEPS for k in controls), name
            assert not any(k.startswith("control.") for k in record.files), name
    assert sorted(p.name for p in honest.glob("*.npz")) == sorted(f"{n}.npz" for n in EXPECTED)
    again = tmp_path / "again"
    crossrev.bindings(again, "replication")
    assert crossrev.compare(honest, again)


@pytest.mark.parametrize("planted", sorted(EXPECTED))
def test_a_planted_parameter_changes_its_record(planted, honest, tmp_path, monkeypatch, capsys):
    worlds = crossrev.replication_worlds()
    worlds[planted] = crossrev.replication_world(planted, **plants()[planted])
    assert worlds[planted]["execution"]["dt"] == EXPECTED[planted][-1]  # The plant keeps the step.
    monkeypatch.setattr(crossrev, "replication_worlds", lambda: worlds)
    crossrev.bindings(tmp_path / "planted", "replication")
    same, differs = _differs(capsys, honest, tmp_path / "planted")
    assert not same
    assert len(differs) == 1 and differs[0].startswith(f"{planted}.npz DIFFERS"), differs


def _probe_change_at(step):
    """linear_norton with its probe membrane's availability stepped from 1 to 0.5 at `step`."""
    raw = crossrev.replication_world("linear_norton")
    dt = raw["execution"]["dt"]
    (control,) = [c for c in raw["experiment"]["membrane_controls"] if c["membrane_id"] == "probe"]
    control["schedule"] = [dict(time=0.0, availability=1.0), dict(time=step * dt, availability=0.5)]
    return raw


def test_a_one_step_delay_changes_its_record(tmp_path, monkeypatch, capsys):
    from cells.definitions.specs import parse_spec
    from cells.execution.schedule import control_values

    honest = crossrev.replication_worlds()
    for step in (2, 3):
        worlds = dict(honest, linear_norton=_probe_change_at(step))
        monkeypatch.setattr(crossrev, "replication_worlds", lambda worlds=worlds: worlds)
        crossrev.bindings(tmp_path / f"at-{step}", "replication")
    same, differs = _differs(capsys, tmp_path / "at-2", tmp_path / "at-3")
    assert not same and len(differs) == 1 and differs[0].startswith("linear_norton.npz DIFFERS")
    with (
        np.load(tmp_path / "at-2/linear_norton.npz") as a,
        np.load(tmp_path / "at-3/linear_norton.npz") as b,
    ):
        assert (a["timing.change_step"].tolist(), b["timing.change_step"].tolist()) == (
            [0, 2],
            [0, 3],
        )
        assert a["timing.event_index"].tolist() == [0, 0, 1, 1, 1]
        assert b["timing.event_index"].tolist() == [0, 0, 0, 1, 1]
        assert a["steps.control.membrane"].tobytes() != b["steps.control.membrane"].tobytes()
    # The controls at the change times alone (the other sets' bindings) do not see the delay.
    old = []
    for step in (2, 3):
        spec = parse_spec(_probe_change_at(step))
        times = sorted({0.0, *(c.time for c in spec.experiment.changes), spec.experiment.end_time})
        old.append([np.asarray(v).tobytes() for v in control_values(spec, times)])
    assert old[0] == old[1]


def test_the_checks_are_traced_on_a_transition(monkeypatch):
    import jax

    spec, model, arrays = crossrev._setup(crossrev.replication_world("linear_norton"))
    state, _, parameters = arrays
    honest = crossrev._replication_traced(spec, model, arrays)
    leaves = len(jax.tree.leaves(state))
    inputs = 2 * leaves + len(jax.tree.leaves(parameters)) + 1  # previous, row, p, steps
    for kind in ("device_checks", "device_checks_margins"):
        assert len(honest[kind].jaxpr.invars) == inputs, kind
    real = model.device_checks
    monkeypatch.setattr(
        model, "device_checks", lambda previous, row, *a, **k: real(row, row, *a, **k)
    )
    planted = crossrev._replication_traced(spec, model, arrays)
    for kind in ("device_checks", "device_checks_margins", "window_checks"):
        assert str(planted[kind]) != str(honest[kind]), kind
    for kind in ("checked_step", "rhs"):
        assert str(planted[kind]) == str(honest[kind]), kind
