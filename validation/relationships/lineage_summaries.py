"""The second consumer of cells.relations@1 (D202): division and replacement lineages, from runs.

D202 asks that, before anyone binds to the format, a second consumer use the writer
(src/cells/records/relations.py) with no edit to it: an existing division world's lineage and an
existing replacement world's, with no operator file touched. This adapter reads only what a run
wrote with io.write_run: summary.json (the operator's own ``lineage`` and its law), the
definition (resolved_config.json), the definition's fingerprint (manifest.json) and the record
file's array headers and times. It turns them into rows and calls the writer's one function.
RT1 replaces it with each mechanism's own ``descent`` (docs/RELATIONSHIPS_DESIGN.md §1.2); it is
a validation tool, and adds no physics.

What the rows say, per mechanism:
- **cells.operator.isopotential_partition@1.** Every founder (a cell that no division names as a daughter) and
  every daughter. Keys follow the s:c rule in the schedule's order: the founders first, in declared
  order; at each division the first daughter continues its parent's sub-lineage and the second
  opens a new one. A division is the event ``event:division/<division id>``, acting at the
  parent's carrier. A daughter's share is its volume fraction.
- **cells.operator.scheduled_cell_replacement@1 and @2.** Every founder (each cell) and every newcomer, keyed in
  the schedule's order, each newcomer opening a sub-lineage. A replacement is the event
  ``event:replacement/<newcomer>`` at its slot. Its material comes from its template
  (``source:template/<id>``) or from the copy of its donor (``source:copy/<donor carrier>``); a
  copy's route-only template is a source of machinery. Per species, the supply into the slot and
  the removal of the old occupant's contents to ``sink:waste`` are edges weighed by the
  operator's own cumulative records (replacement_supplied_fmol, replacement_removed_fmol) across
  the event.
A life still alive when the run ends is censored there. No end is inferred from a missing
successor: a life ends divided or replaced only where its record says it died.
"""

import json
from pathlib import Path

from cells.records import relations as rel

PARTITION = "cells.operator.isopotential_partition@1"
REPLACEMENTS = ("cells.operator.scheduled_cell_replacement@1", "cells.operator.scheduled_cell_replacement@2")
RECORD_FILE = "trajectory.npz"
TIMES = "accepted_times"  # io.write_run's time base of the state's rows.
SUPPLIED, REMOVED = "replacement_supplied_fmol", "replacement_removed_fmol"
WASTE = "sink:waste"


def carrier(name):
    return rel.entity_id("carrier", name)


def slot(name):
    return rel.entity_id("slot", name)


def _step(time, dt):
    """The step index of an event time on the grid (events are k * dt)."""
    return int(round(time / dt))


def _end(record, run_end, reason, event):
    """(end time, end reason, end event) of a lineage record: censored at the run's end unless
    its record says it died."""
    if record["death_s"] is None:
        return run_end, "censored", ""
    return record["death_s"], reason, event


def partition_rows(summary, definition):
    """The rows of a division world (cells.operator.isopotential_partition@1) from its summary's lineage."""
    law, inner = summary["partition_law"], summary["inner_model"]
    dt, run_end = definition["execution"]["dt"], summary["end_time"]
    lineage = summary["lineage"]
    keys = rel.Keys()
    held = {}  # carrier: (key, lineage, generation, root)
    for record in lineage:  # Founders first, in declared order.
        if record["kind"] == "founder":
            name = record["carrier_id"]
            held[name] = (*keys.open(), 0, carrier(name))
    divisions = []  # (division id, time, parent, [daughter records]), in the schedule's order.
    for record in lineage:
        if record["kind"] == "daughter":
            if not divisions or divisions[-1][0] != record["division"]:
                divisions.append(
                    (record["division"], record["birth_s"], record["parent_carrier"], [])
                )
            divisions[-1][3].append(record)
    events, ended = [], {}
    for division, time, parent, daughters in divisions:
        _, lineage_of_parent, generation, root = held[parent]
        drawn = keys.split(lineage_of_parent, [True] * len(daughters), continues=0)
        for record, (key, own) in zip(daughters, drawn, strict=True):
            held[record["carrier_id"]] = (key, own, generation + 1, root)
        event = rel.entity_id("event", f"division/{division}")
        ended[parent] = event
        events.append(
            rel.Event(event, time, "division", law, True, step=_step(time, dt), at=carrier(parent))
        )
    lives = []
    for record in lineage:
        name = record["carrier_id"]
        key, own, generation, root = held[name]
        end_time, reason, end_event = _end(record, run_end, "divided", ended.get(name, ""))
        common = dict(slot=slot(record["slot"]), end_event=end_event)
        if record["kind"] == "founder":
            born = dict(birth_time=record["birth_s"], birth_kind="founder")
        else:
            born = dict(
                birth_time=record["birth_s"],
                birth_kind="division",
                parent=carrier(record["parent_carrier"]),
                share=float(record["volume_fraction"]),
                birth_event=rel.entity_id("event", f"division/{record['division']}"),
            )
        lives.append(
            rel.Life(
                id=carrier(name),
                key=key,
                lineage=own,
                end_time=end_time,
                end_reason=reason,
                generation=generation,
                root=root,
                declared_by=law,
                **born,
                **common,
            )
        )
    slots = sorted({record["slot"] for record in lineage})
    nodes = [rel.Node(slot(name), "slot", inner) for name in slots]
    return dict(lives=lives, events=events, nodes=nodes)


def replacement_rows(summary, definition, directory):
    """The rows of a replacement world (cells.operator.scheduled_cell_replacement@1 or @2) from its summary's
    lineage, with supply and removal edges weighed by the operator's records in RECORD_FILE."""
    law, inner = summary["replacement_law"], summary["inner_model"]
    dt, run_end = definition["execution"]["dt"], summary["end_time"]
    species = list(summary["species_ids"])
    cells = [c["id"] for c in definition["model"]["cells"]]
    lineage = summary["lineage"]
    keys = rel.Keys()
    held = {}
    for record in lineage:  # Founders first (every cell, in declared order), then newcomers.
        if record["founder"]:
            held[record["carrier_id"]] = keys.open()
    for record in lineage:
        if not record["founder"]:
            held[record["carrier_id"]] = keys.open()
    event_of = {
        r["carrier_id"]: rel.entity_id("event", f"replacement/{r['carrier_id']}") for r in lineage
    }
    lives, events, sources, edges = [], [], {}, []
    carried = ",".join(sorted(species))
    for record in lineage:
        name = record["carrier_id"]
        key, own = held[name]
        successor = record["successor"]
        end_time, reason, end_event = _end(
            record, run_end, "replaced", event_of[successor] if successor else ""
        )
        common = dict(
            id=carrier(name),
            key=key,
            lineage=own,
            end_time=end_time,
            end_reason=reason,
            end_event=end_event,
            generation=0,
            root=carrier(name),
            declared_by=law,
            slot=slot(record["slot"]),
            birth_time=record["birth_s"],
        )
        if record["founder"]:
            lives.append(rel.Life(birth_kind="founder", **common))
            continue
        event, place = event_of[name], slot(record["slot"])
        copy = record["newcomer"] == "donor_copy"
        if copy:
            source = rel.entity_id("source", f"copy/{record['donor_carrier']}")
            sources[source] = rel.Source(
                source, "copy", "intervention", law, carries=carried, record=SUPPLIED
            )
        else:
            source = rel.entity_id("source", f"template/{record['template']}")
            sources[source] = rel.Source(
                source, "template", "intervention", law, carries=carried, record=SUPPLIED
            )
        lives.append(
            rel.Life(
                birth_kind="copy" if copy else "template",
                predecessor=carrier(record["predecessor"]),
                donor=carrier(record["donor_carrier"]) if copy else "",
                birth_event=event,
                **common,
            )
        )
        events.append(
            rel.Event(event, record["birth_s"], "replacement", law, True,
                      step=_step(record["birth_s"], dt), at=place, source=source)
        )  # fmt: skip
        column = cells.index(record["slot"])
        for i, name_of_species in enumerate(species):
            index = f"{i},{column}"
            edges.append(
                rel.Edge("supplies", source, place, law, event=event, species=name_of_species,
                         weight_record=SUPPLIED, weight_index=index, mode="event")
            )  # fmt: skip
            edges.append(
                rel.Edge("removes_to", place, WASTE, law, event=event, species=name_of_species,
                         weight_record=REMOVED, weight_index=index, mode="event")
            )  # fmt: skip
        if copy and record["template"] is not None:  # A route-only template: machinery.
            routes = rel.entity_id("source", f"template/{record['template']}")
            sources[routes] = rel.Source(routes, "template", "machinery", law)
            edges.append(rel.Edge("supplies", routes, place, law, event=event, mode="event"))
    nodes = [rel.Node(slot(name), "slot", inner) for name in cells]
    nodes.append(rel.Node(WASTE, "sink", law))
    records = rel.records_in(
        directory, [RECORD_FILE], {SUPPLIED: "cumulative", REMOVED: "cumulative"}, times=TIMES
    )
    return dict(
        lives=lives,
        events=events,
        nodes=nodes,
        sources=list(sources.values()),
        edges=edges,
        records=records,
    )


def world_rows(directory):
    """The writer's keywords for a run written by io.write_run whose summary holds a partition's
    or a replacement's lineage: the world (its qualifier, from the definition's fingerprint and a
    fresh start) and its rows."""
    directory = Path(directory)
    summary, definition, manifest = (
        json.loads((directory / name).read_text())
        for name in ("summary.json", "resolved_config.json", "manifest.json")
    )
    world = rel.qualifier(manifest["definition_sha256"])
    if summary.get("partition_law") == PARTITION:
        return dict(world=world, **partition_rows(summary, definition))
    if summary.get("replacement_law") in REPLACEMENTS:
        return dict(world=world, **replacement_rows(summary, definition, directory))
    raise ValueError(f"{directory}: its summary holds no partition's or replacement's lineage")


def write_relations(directory):
    """Write the run's relationship tables beside its files, through the writer's one function.
    The run's manifest predates them, so its checksums do not cover them (as for a run view
    written later by run_view.write_view)."""
    return rel.write(directory, **world_rows(directory))
