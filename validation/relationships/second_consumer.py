"""The second consumer's runs (D202): real division and replacement worlds through the one writer.

Each world below runs through io.write_run into OUT/<world>. Its relationship tables are written
beside it through the writer's one function (lineage_summaries.write_relations), read back with
the reader's check (record files included), checked against what the definition declares (never
against the summary the rows came from), and drawn by draw_relations.py in a fresh process that
imports no engine code. The report is OUT/second_consumer.json. Development runs, not judged.

Engine models run (AGENTS.md):
- egg: cells.model.resolved_pump_composite@1 over cells.model.resolved_pump_tissue@3 with cells.operator.membrane_entity_state@1,
  cells.operator.scheduled_membrane_insertion@2, cells.operator.restricted_cleft_lumen@2, cells.operator.isopotential_partition@1,
  cells.operator.cytoplasmic_bridge_closure@1 and cells.operator.electrode_current_injection@1: S5's egg-scale accounting
  world (validation/division/egg_division_world) at scale 0.002, three partitions in two
  generations;
- replacement and replacement_donors: cells.model.resolved_pump_replacement@1, the composite over @3 with
  cells.operator.scheduled_cell_replacement@1: crossrev's base worlds of those names (composite_crossrev.worlds,
  rebuilt here from the same fixtures and recipe): one slot replaced twice, donor copies, one with
  a route-only template;
- volume_events: the composite over @3 with cells.operator.ideal_osmosis_linear_compliance_water@1 and
  cells.operator.scheduled_cell_replacement@2: crossrev's volume set's world of that name: templates at their own
  volumes, two events at one time, and a copy that replaces a newcomer.

The checks, against the definition:
- division: each scheduled division's daughters are its declared carriers, in its declared
  daughter slots, born at its time with its volume fraction (the first) and the rest (the
  second), from the carrier its parent slot held; every founder is a cell no division names as a
  daughter; keys follow §1.3 in the schedule's order (the expected keys are listed);
- replacement: each event's newcomer follows the carrier its slot held (precedes_in_slot); a
  copy's donor is the carrier the donor slot held before the event (copied_from); each supplies
  edge, weighed by the operator's record across its event (the descriptor's event_rows), equals
  the template's declared amount (a template) or the donor's saved amount at the event's row (a
  copy), species by species, to a relative 1e-12.

Usage: python -m validation.relationships.second_consumer OUT
"""

import copy
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from cells.records import relations as rel
from validation.relationships import lineage_summaries as adapter

STATUS = "Development runs of the relationship tables' second consumer (D202); not judged"
EGG_SCALE = 0.002
DRAW = Path(__file__).with_name("draw_relations.py")
TOLERANCE = 1e-12


def worlds():
    """{name: raw definition}: the division world and the replacement worlds (module docstring)."""
    from cells.definitions.cell_replacement_spec import exact_event_times
    from validation.division import egg_division_world as egg
    from validation.tissue import cell_replacement_fixtures as rfx

    out = {"egg": egg.definition(scale=EGG_SCALE)}
    dt = 1e-3
    t1, t2, t3 = exact_event_times((10, 20, 30), dt)
    cells = rfx.heredity_sheet(1, 0, dt=dt, end_time=0.05)
    cells["experiment"]["observation_times"] = [0.0, 0.05]
    templates = [
        rfx.template_from_cell(cells, "cell_1", "h"),
        rfx.template_from_cell(cells, "cell_3", "d"),
    ]
    events = ((t1, "cell_0", "h", "n1"), (t2, "cell_2", "h", "n2"), (t3, "cell_0", "d", "n4"))
    out["replacement"] = rfx.with_replacement(cells, templates, events)
    fast = dict(rfx.NO_ROUTES, channel_permeability_m_per_s={"cells.channel.nav1p2_m3h_regularized@1": 3e-7})
    donor_events = (
        (t1, "cell_0", None, "c1", "cell_3"),
        (t2, "cell_4", "fast_nav", "c2", "cell_3"),
    )
    out["replacement_donors"] = rfx.with_replacement(
        cells, [*templates, rfx.route_template("fast_nav", fast)], donor_events
    )
    u1, u2 = exact_event_times((10, 20), dt)
    raw = rfx.heredity_sheet(1, 0, dt=dt, end_time=0.03)
    raw["experiment"]["observation_times"] = [0.0, 0.03]
    v0 = raw["model"]["cells"][0]["volume_pL"]
    own = [rfx.template_from_cell(raw, "cell_1", "h"), rfx.template_from_cell(raw, "cell_3", "d")]
    own[0]["volume_pL"], own[1]["volume_pL"] = 0.97 * v0, 1.03 * v0
    events = (
        (u1, "cell_0", "h", "n1"),
        (u1, "cell_1", "d", "n2"),
        (u2, "cell_0", None, "c1", "cell_3"),
    )
    out["volume_events"] = rfx.over_water(raw, own, events)
    return out


# ------------------------------------------------------------------ checks against the definition


def _by(rows, field="id"):
    return {getattr(r, field): r for r in rows}


def division_checks(definition, tables):
    """The lives and parent_of edges against the definition's divisions and schedule."""
    model, experiment = definition["model"], definition["experiment"]
    (partition,) = [op for op in model["operators"] if op["law"] == adapter.PARTITION]
    blocks = {d["id"]: d for d in partition["divisions"]}
    lives = _by(tables["lives"])
    daughters = {d for block in blocks.values() for d in block["daughters"]}
    founders = [c["id"] for c in model["cells"] if c["id"] not in daughters]
    held = {name: name for name in founders}  # slot: the carrier it holds
    problems = []
    for name in founders:
        life = lives.get(adapter.carrier(name))
        if life is None or life.birth_kind != "founder" or life.slot != adapter.slot(name):
            problems.append(f"founder {name}")
    for event in sorted(experiment["partition_events"], key=lambda e: e["time"]):
        block = blocks[event["division"]]
        parent = held[block["parent"]]
        shares = (block["volume_fraction"], 1.0 - block["volume_fraction"])
        for k, (slot_name, name) in enumerate(
            zip(block["daughters"], event["carriers"], strict=True)
        ):
            life = lives.get(adapter.carrier(name))
            ok = (
                life is not None
                and life.parent == adapter.carrier(parent)
                and life.slot == adapter.slot(slot_name)
                and life.birth_time == event["time"]
                and life.share == shares[k]
            )
            if not ok:
                problems.append(f"daughter {name} of {event['division']}")
            held[slot_name] = name
    parent_of = sorted((e.from_, e.to) for e in tables["edges"] if e.relation == "parent_of")
    expected = sorted((x.parent, x.id) for x in tables["lives"] if x.parent)
    if parent_of != expected or len(parent_of) != 2 * len(experiment["partition_events"]):
        problems.append("parent_of edges")
    return problems


def replacement_checks(definition, tables, directory):
    """The newcomers' chains, donors and supplies against the definition's replacement events and
    templates, the supplies weighed by the run's own record across each event."""
    model, experiment = definition["model"], definition["experiment"]
    cells = [c["id"] for c in model["cells"]]
    species = [s["id"] for s in model["species"]]
    if "replacement" in model:  # cells.model.resolved_pump_replacement@1's own block, or the operator's.
        declared = model["replacement"]
    else:
        (declared,) = [op for op in model["operators"] if op["law"] in adapter.REPLACEMENTS]
    templates = {t["id"]: t for t in declared["templates"]}
    lives = _by(tables["lives"])
    order = {name: i for i, name in enumerate(cells)}
    held = {name: name for name in cells}
    problems, checked = [], 0
    with np.load(Path(directory) / adapter.RECORD_FILE, allow_pickle=False) as saved:
        times, supplied = saved[adapter.TIMES], saved[adapter.SUPPLIED]
        increment, reference = saved["amount_increment"], saved["amount_reference"]
    supplies = [e for e in tables["edges"] if e.relation == "supplies" and e.weight_record]
    events = sorted(experiment["replacement_events"], key=lambda e: (e["time"], order[e["slot"]]))
    groups = {}
    for event in events:  # Donors are read before any event at their time.
        groups.setdefault(event["time"], []).append(event)
    for when, group in sorted(groups.items()):
        before = dict(held)
        row = int(np.searchsorted(times, when, side="left"))
        for event in group:
            name, slot_name = event["carrier_id"], event["slot"]
            life = lives.get(adapter.carrier(name))
            donor = event["donor"]
            ok = (
                life is not None
                and life.predecessor == adapter.carrier(held[slot_name])
                and life.birth_time == when
                and life.donor == (adapter.carrier(before[donor]) if donor else "")
            )
            if not ok:
                problems.append(f"newcomer {name}")
            if donor:  # The donor's amounts in the row saved before the event.
                declared = reference[:, order[donor]] + increment[row, :, order[donor]]
            else:
                template = templates[event["template"]]
                declared = np.array([template["amounts_fmol"][s] for s in species])
            event_id = rel.entity_id("event", f"replacement/{name}")
            for i, s in enumerate(species):
                (edge,) = [e for e in supplies if e.event == event_id and e.species == s]
                column = supplied[:, i, order[slot_name]]
                weight = column[row + 1] - column[row]
                if abs(weight - declared[i]) > TOLERANCE * max(abs(declared[i]), 1.0):
                    problems.append(f"supply of {s} at {name}: {weight!r} against {declared[i]!r}")
                checked += 1
            held[slot_name] = name
    return problems, checked


def draw(directory, out):
    """draw_relations.py in a fresh process with the engine importable; it must load none."""
    probe = (
        "import runpy, sys; sys.argv = sys.argv[1:]; "
        "runpy.run_path(sys.argv[0], run_name='__main__'); "
        "bad = sorted(m for m in sys.modules if m.split('.')[0] in ('cells', 'jax', 'jaxlib')); "
        "print('ENGINE MODULES', bad); sys.exit(1 if bad else 0)"
    )
    env = dict(os.environ, PYTHONPATH=str(Path(rel.__file__).parents[2]))
    done = subprocess.run(
        [sys.executable, "-B", "-c", probe, str(DRAW), str(directory), str(out)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return done.returncode, done.stdout.strip().splitlines()[
        -1:
    ] + done.stderr.strip().splitlines()[-3:]


def main(argv=None):
    import jax

    from cells.definitions.specs import parse_spec
    from cells.execution.runner import run
    from cells.records.io import write_run

    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        raise SystemExit("usage: python -m validation.relationships.second_consumer OUT")
    jax.config.update("jax_enable_x64", True)
    out = Path(argv[0])
    out.mkdir(parents=True, exist_ok=False)
    report = {"status": STATUS, "writer": rel.FORMAT, "worlds": {}}
    for name, raw in worlds().items():
        start = time.perf_counter()
        spec = parse_spec(copy.deepcopy(raw))
        directory = out / name
        write_run(directory, run(spec))
        seconds = time.perf_counter() - start
        descriptor = adapter.write_relations(directory)
        _, tables = rel.read(directory)  # The reader's check, record files included.
        definition = json.loads((directory / "resolved_config.json").read_text())
        summary = json.loads((directory / "summary.json").read_text())
        if summary.get("partition_law") == adapter.PARTITION:
            problems, checked = division_checks(definition, tables), None
        else:
            problems, checked = replacement_checks(definition, tables, directory)
        code, drawn = draw(directory, out / "graphs" / name)
        report["worlds"][name] = {
            "definition_sha256": spec.fingerprint,
            "world": descriptor["world"],
            "run_seconds": round(seconds, 1),
            "steps": summary["executed_steps"],
            "rows": {t: e["rows"] for t, e in descriptor["tables"].items()},
            "keys": {x.id: rel.key_text(x.key) for x in tables["lives"]},
            "lineages": {x.id: x.lineage for x in tables["lives"]},
            "end_reasons": {x.id: x.end_reason for x in tables["lives"]},
            "supplies_checked": checked,
            "problems": problems,
            "drawn": {"exit": code, "tail": drawn},
        }
        print(name, "problems", problems, "drawn", code, flush=True)
    passed = all(not w["problems"] and w["drawn"]["exit"] == 0 for w in report["worlds"].values())
    report["verdict"] = "pass" if passed else "fail"
    (out / "second_consumer.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(report["verdict"], flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
