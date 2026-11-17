"""The second consumer of cells.relations@1 (D202): lineages from saved summaries, and the graphs.

validation/relationships/lineage_summaries.py turns the partition's and replacement's summary
``lineage`` into rows through the writer's one function; draw_relations.py draws the graphs
from the tables with no engine code. Host only: each summary is the one the operator writes for
a run whose scheduled events all apply (its own lineage builder, from the definition alone),
round-tripped through JSON as summary.json is, beside the run's definition and fingerprint. A
replacement run's record file is stood in for by zeros at the run's shapes on its own step grid.
The real worlds run in validation/relationships/second_consumer.py. Each claim once, with a
planted error (D187):
1. A division world's lineage (S5's compact world with a neighbour): the writer takes it as it
   is, its keys are §5.4's (cell_0 0:0, cell_1 1:0, c1 0:1, c2 0:2, which opens sub-lineage 2)
   and its tree is the definition's. Planted: a wrong parent, a lost daughter.
2. A replacement world's lineage (crossrev's donor and two-replacement worlds): each newcomer
   follows its slot's occupant, a copy names its donor's carrier, and every supply points at its
   species' and slot's column. Planted: a wrong predecessor.
3. The graphs: draw_relations.py draws the tree and the supply graph from the tables, in a fresh
   process where the engine is importable, and loads no cells or jax module. Planted: the same
   script with an import of cells.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from cells.core import cell_replacement_spec as replacement_spec
from cells.core.cell_replacement_spec import exact_event_times
from cells.core.pump_composite_spec import entries
from cells.core.specs import parse_spec
from cells.records import relations as rel
from tests import partition_fixtures as pf
from validation.relationships import lineage_summaries as adapter
from validation.tissue import cell_replacement_fixtures as rfx

ROOT = Path(__file__).resolve().parents[2]
DRAW = ROOT / "validation" / "relationships" / "draw_relations.py"


def _json(value):
    return json.loads(json.dumps(value))


def _run_folder(directory, spec, summary):
    directory.mkdir()
    (directory / "summary.json").write_text(json.dumps(_json(summary)))
    (directory / "resolved_config.json").write_text(json.dumps(spec.to_dict()))
    (directory / "manifest.json").write_text(json.dumps({"definition_sha256": spec.fingerprint}))
    return directory


def division_run(directory, change=None):
    """S5's compact world with a neighbour, as io.write_run would save its summary."""
    spec = parse_spec(pf.divided(neighbour=True))
    ((op, declaration, schedule),) = [e for e in entries(spec) if e[0].LAW_ID == adapter.PARTITION]
    summary = op.summary(spec, declaration, schedule, None)  # Every scheduled event applies.
    summary = dict(
        _json(summary), end_time=spec.experiment.end_time, inner_model=spec.model.inner_model
    )
    if change is not None:
        change(summary["lineage"])
    return spec, _run_folder(directory, spec, summary)


def replacement_worlds():
    """crossrev's base worlds `replacement` and `replacement_donors` (composite_crossrev.worlds)."""
    dt = 1e-3
    t1, t2, t3 = exact_event_times((10, 20, 30), dt)
    cells = rfx.heredity_sheet(1, 0, dt=dt, end_time=0.05)
    cells["experiment"]["observation_times"] = [0.0, 0.05]
    templates = [
        rfx.template_from_cell(cells, "cell_1", "h"),
        rfx.template_from_cell(cells, "cell_3", "d"),
    ]
    events = ((t1, "cell_0", "h", "n1"), (t2, "cell_2", "h", "n2"), (t3, "cell_0", "d", "n4"))
    fast = dict(rfx.NO_ROUTES, channel_permeability_m_per_s={"nav1p2_m3h_regularized@1": 3e-7})
    donors = ((t1, "cell_0", None, "c1", "cell_3"), (t2, "cell_4", "fast_nav", "c2", "cell_3"))
    route = rfx.route_template("fast_nav", fast)
    return {
        "replacement": rfx.with_replacement(cells, templates, events),
        "replacement_donors": rfx.with_replacement(cells, [*templates, route], donors),
    }


def replacement_run(directory, raw, change=None):
    """A replacement world as io.write_run would save its summary, with its record file stood in
    for by zeros at the run's shapes on its step grid (bitwise k * dt, as the run saves them)."""
    spec = parse_spec(raw)
    summary = dict(
        lineage=replacement_spec.lineage(spec),  # Every declared event applies.
        replacement_law=replacement_spec.OPERATION_LAW_ID,
        inner_model=spec.model.replacement.inner_model,
        end_time=spec.experiment.end_time,
        species_ids=list(spec.model.species_ids),
    )
    summary = _json(summary)
    if change is not None:
        change(summary["lineage"])
    _run_folder(directory, spec, summary)
    x = spec.execution
    rows = round(spec.experiment.end_time / x.dt) + 1
    shape = (rows, len(spec.model.species_ids), x.capacity)
    np.savez(
        directory / adapter.RECORD_FILE,
        accepted_times=np.arange(rows) * x.dt,
        replacement_supplied_fmol=np.zeros(shape),
        replacement_removed_fmol=np.zeros(shape),
    )
    return spec, directory


def _edges(tables, relation):
    return sorted((e.from_, e.to) for e in tables["edges"] if e.relation == relation)


def _record(lineage, carrier):
    return next(r for r in lineage if r["carrier_id"] == carrier)


# ------------------------------------------------------------------ 1. a division world


def test_a_division_worlds_lineage_through_the_writer(tmp_path):
    spec, run = division_run(tmp_path / "run")
    adapter.write_relations(run)
    _, tables = rel.read(run)
    lives = {x.id: x for x in tables["lives"]}
    keys = {name.split(":", 1)[1]: (rel.key_text(x.key), x.lineage) for name, x in lives.items()}
    assert keys == {
        "cell_0": ("0:0", 0),
        "cell_1": ("1:0", 1),
        "c1": ("0:1", 0),
        "c2": ("0:2", 2),
    }  # §5.4's keys.
    raw = spec.to_dict()  # The tree is the definition's: its division's parent and carriers.
    ((block,),) = [
        op["divisions"] for op in raw["model"]["operators"] if op["law"] == adapter.PARTITION
    ]
    (event,) = raw["experiment"]["partition_events"]
    expected = [(f"carrier:{block['parent']}", f"carrier:{c}") for c in event["carriers"]]
    assert (
        _edges(tables, "parent_of")
        == sorted(expected)
        == [
            ("carrier:cell_0", "carrier:c1"),
            ("carrier:cell_0", "carrier:c2"),
        ]
    )
    assert [lives[f"carrier:{c}"].share for c in ("c1", "c2")] == [0.5, 0.5]
    assert _edges(tables, "occupies") == sorted(
        [
            (f"carrier:{c}", f"slot:{s}")
            for c, s in (("cell_0", "cell_0"), ("cell_1", "cell_1"), ("c1", "d1"), ("c2", "d2"))
        ]
    )
    assert (lives["carrier:cell_0"].end_reason, lives["carrier:cell_0"].end_time) == (
        "divided",
        pf.EVENT,
    )
    end = spec.experiment.end_time
    assert {(x.end_reason, x.end_time) for x in tables["lives"] if x.id != "carrier:cell_0"} == {
        ("censored", end)
    }


def _wrong_parent(lineage):
    _record(lineage, "c2")["parent_carrier"] = "cell_1"


def _lost_daughter(lineage):
    lineage.remove(_record(lineage, "c2"))


@pytest.mark.parametrize(
    "plant, rule",
    [
        (_wrong_parent, "born where its parent ended"),
        (_lost_daughter, "divided into two daughters or more"),
    ],
)
def test_a_wrong_division_lineage_is_refused(plant, rule, tmp_path):
    _, run = division_run(tmp_path / "run", plant)
    with pytest.raises(rel.RelationsRefused, match=rule):
        adapter.write_relations(run)
    assert not (run / rel.ARRAYS).exists()


# ------------------------------------------------------------------ 2. a replacement world


def test_a_replacement_worlds_lineage_through_the_writer(tmp_path):
    worlds = replacement_worlds()
    spec, run = replacement_run(tmp_path / "chain", worlds["replacement"])
    adapter.write_relations(run)
    _, tables = rel.read(run)
    assert _edges(tables, "precedes_in_slot") == [
        ("carrier:cell_0", "carrier:n1"),
        ("carrier:cell_2", "carrier:n2"),
        ("carrier:n1", "carrier:n4"),
    ]
    spec, run = replacement_run(tmp_path / "donors", worlds["replacement_donors"])
    adapter.write_relations(run)
    _, tables = rel.read(run)
    assert _edges(tables, "precedes_in_slot") == [
        ("carrier:cell_0", "carrier:c1"),
        ("carrier:cell_4", "carrier:c2"),
    ]
    assert _edges(tables, "copied_from") == [
        ("carrier:cell_3", "carrier:c1"),
        ("carrier:cell_3", "carrier:c2"),
    ]
    assert {(x.id, x.birth_kind, x.generation, x.root) for x in tables["lives"] if x.donor} == {
        ("carrier:c1", "copy", 0, "carrier:c1"),
        ("carrier:c2", "copy", 0, "carrier:c2"),
    }
    cells = [c.id for c in spec.model.cells]
    species = list(spec.model.species_ids)
    weighed = [e for e in tables["edges"] if e.weight_record]
    assert len(weighed) == 2 * 2 * len(species)  # Supply and removal, per species, per event.
    for edge in weighed:
        place = edge.to if edge.relation == "supplies" else edge.from_
        column = cells.index(place.split(":", 1)[1])
        assert edge.weight_index == f"{species.index(edge.species)},{column}"
    machinery = [s for s in tables["sources"] if s.class_ == "machinery"]
    assert [s.id for s in machinery] == ["source:template/fast_nav"]


def test_a_wrong_predecessor_is_refused(tmp_path):
    def plant(lineage):
        _record(lineage, "n4")["predecessor"] = "cell_2"

    _, run = replacement_run(tmp_path / "run", replacement_worlds()["replacement"], plant)
    with pytest.raises(rel.RelationsRefused, match="its predecessor left its slot"):
        adapter.write_relations(run)


# ------------------------------------------------------------------ 3. the graphs, no engine code

PROBE = (
    "import runpy, sys; sys.argv = sys.argv[1:]; runpy.run_path(sys.argv[0], run_name='__main__'); "
    "bad = sorted(m for m in sys.modules if m.split('.')[0] in ('cells', 'jax', 'jaxlib')); "
    "print('ENGINE MODULES', bad); sys.exit(1 if bad else 0)"
)


def drawn(script, run, out):
    """Run a drawing script in a fresh process where the engine is importable."""
    env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(ROOT / "src"), str(ROOT))))
    return subprocess.run(
        [sys.executable, "-B", "-c", PROBE, str(script), str(run), str(out)],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=False,
    )


def test_the_graphs_are_drawn_from_the_tables_with_no_engine_code(tmp_path):
    _, run = replacement_run(tmp_path / "run", replacement_worlds()["replacement_donors"])
    adapter.write_relations(run)
    _, tables = rel.read(run)
    done = drawn(DRAW, run, tmp_path / "graphs")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "ENGINE MODULES []" in done.stdout
    lineage = (tmp_path / "graphs" / "lineage.svg").read_text()
    supply = (tmp_path / "graphs" / "supply.svg").read_text()
    assert all(x.id in lineage for x in tables["lives"])
    assert all(s.id in supply for s in tables["sources"])
    graphs = json.loads((tmp_path / "graphs" / "graphs.json").read_text())
    descent = {(e["relation"], e["from"], e["to"]) for e in graphs["descent"]}
    assert descent == {
        (e.relation, e.from_, e.to)
        for e in tables["edges"]
        if e.relation in ("parent_of", "precedes_in_slot", "copied_from")
    }
    supplied = {(s["from"], s["to"]) for s in graphs["supply"] if s["relation"] == "supplies"}
    assert supplied == {(e.from_, e.to) for e in tables["edges"] if e.relation == "supplies"}
    # Planted: the same script with an import of the engine.
    planted = tmp_path / "planted.py"
    planted.write_text("import cells  # noqa: F401\n" + DRAW.read_text())
    done = drawn(planted, run, tmp_path / "planted-graphs")
    assert done.returncode == 1 and "ENGINE MODULES ['cells'" in done.stdout, done.stdout
