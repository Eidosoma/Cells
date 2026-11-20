"""Relationship tables, ``cells.relations@1``: descent, events, sources and edges as plain columns.

**Bound** (D202). A second consumer has used this writer: the partition's and replacement's
lineages, from four real worlds (validation/relationships/). The one gap it found was fixed in the
format, and the provisional label was lifted with it. A change to the format is now a new version.

D200 asks that relationships come as plain node and edge tables with stable string ids, so that a
lineage tree, a supply graph or a dependency graph is a join, not a reconstruction
(docs/RELATIONSHIPS_DESIGN.md §5). This module is the one writer of those tables: it defines the
row interface, owns the schema, the ids, the keys and every check, and refuses a malformed row
with nothing written. Mechanisms make rows and call it. It imports no model family, operator or
law (numpy and the standard library only), and nothing reads the tables back into a run.

**Files**, beside a run's own (one pair per run, per world in a batch):
- ``relations.npz``: one array per column, named ``<table>.<column>``. Text is fixed-width Unicode
  (``<U<n>``), numbers ``<i8`` or ``<f8``, flags ``|b1``. Nothing is pickled, so every array loads
  with ``numpy.load(..., allow_pickle=False)``. Rows are sorted and the zip's members carry a fixed
  date, so equal tables give equal bytes.
- ``relations.json``: the descriptor (FORMAT): the world, each table's columns with their types,
  nulls and meanings, the vocabularies, the id and key rules, and the records that edge weights
  point at. Sorted keys, no host path, no time stamp.

**Records.** A weight that is not a number on its edge points at a run record: ``weight_record``
names it and ``weight_index`` gives one position on each of its axes after the first. The
descriptor's ``records`` say where each lives: its array, the array of its rows' times, its kind
(``cumulative``, weighing an interval by its change over it, or ``amount``) and its files, which
hold its rows in order (one file, or a windowed run's chunks). An event at time t acts between a
record's first row saved at a time no earlier than t and the row after it (EVENT_ROWS), so an edge
with an event is weighed by the record's change there. The writer checks that every record is in
its files at its shape, that its times never fall, and that an event's two rows exist.

**The tables.** Every row also carries ``world``, the run qualifier (``qualifier``).
- ``nodes``: every vertex by id and kind. Carrier, source and label nodes are derived from
  ``lives``, ``sources`` and ``labels``; a caller declares the rest (slots, held nodes, sinks,
  mechanisms).
- ``lives`` (§1.2): one row per carrier, from its birth to its end: its key and sub-lineage (§1.3),
  where it came from (a parent and its share, a donor, a predecessor), its birth and end events,
  kinds and reasons, its generation and root, and the mechanism that declared it.
- ``events``: births, ends and interventions, each with its time and step, its kind, the vertex it
  acts at, the mechanism that made it and the source that supplied or paid for it.
- ``edges``: relations between vertices. The descent edges (``parent_of``, ``precedes_in_slot``,
  ``copied_from``, ``occupies``) are derived from ``lives``; a caller declares the rest. A weight
  is a number on the edge (a daughter's share) or a pointer to a run record and a position in it,
  whose rows weigh the edge, so no array is copied.
- ``sources``: suppliers of material and payers of work, by kind and class (§3.3).
- ``labels``: material labels. RT3 fills them; the schema is fixed now.

**Ids** are ``<kind>:<name>``. A vertex's kind is its node kind (``carrier:c1``, ``slot:cell_0``,
``source:template/T1``), an event's is ``event`` (``event:division/first``). A name is ASCII
segments of letters, digits and ``_ . @ + -`` joined by ``/``. Ids are unique within a world, event
ids included; a family may qualify an event's name by the carrier it belongs to where that is what
makes it unique (``event:extinction/<carrier key>/<count>``). Across runs, the ``world`` column (the
run qualifier) tells ids apart; no id carries the qualifier itself.

**Keys** (§1.3), int64: ``s * 2**32 + c``, written ``s:c``, a count c in sub-lineage s. A life
without a parent opens a sub-lineage s and holds ``s:0``, founders first, in declared order. A
division's daughters draw the next counts of their parent's sub-lineage, in daughter order. One
daughter may continue that sub-lineage, and each other daughter that lives on opens a new one.
``lineage`` names the sub-lineage a life's own daughters draw from (-1: none). A mechanism that
assigns keys on the host uses ``Keys``; others pass their own, and the writer checks the rule
either way.

Usage: ``write(directory, world=qualifier(fingerprint), lives=[...], events=[...], nodes=[...])``.
"""

import hashlib
import json
import math
import re
import zipfile
from dataclasses import astuple, dataclass
from pathlib import Path, PurePosixPath

import numpy as np

FORMAT = "cells.relations@1"
# The next version (§0.2e item 1): @1's tables with one more end reason, `lysed`, for the
# assembly family's lysis. It is chosen by the writer's `version`; @1's writers keep @1, so their
# bytes are unchanged.
FORMAT_V2 = "cells.relations@2"
ARRAYS = "relations.npz"
DESCRIPTOR = "relations.json"

# ------------------------------------------------------------------ vocabularies

NODE_KINDS = (
    "carrier",
    "face",
    "junction",
    "label",
    "mechanism",
    "node",
    "patch",
    "population",
    "sink",
    "slot",
    "source",
    "world",
)
DERIVED_NODE_KINDS = ("carrier", "label", "source")  # From lives, labels and sources.
ID_KINDS = (*NODE_KINDS, "event")
BIRTH_KINDS = ("founder", "division", "template", "copy", "transplant", "continued")
END_REASONS = (
    "divided",
    "replaced",
    "extinct",
    "not_followed",
    "removed",
    "transplanted_out",
    "censored",
)
VOCABULARY = {FORMAT: END_REASONS, FORMAT_V2: (*END_REASONS, "lysed")}  # end reasons, by version
DESCENT = ("parent_of", "precedes_in_slot", "copied_from", "occupies")  # Derived from lives.
MATERIAL = ("supplies", "removes_to", "moves_to", "contains")
FLOWS = ("supplies", "removes_to", "moves_to")  # Each states its mode.
DEPENDENCE = ("reads", "changes", "moves")
HISTORY = ("branched_into", "transplanted_into")  # May name another world's vertex.
RELATIONS = (*DESCENT, *MATERIAL, *DEPENDENCE, *HISTORY)
MODES = ("event", "one_way", "net")
SOURCE_KINDS = (
    "chemostat",
    "copy",
    "dose",
    "electrode",
    "feeder",
    "held_bath",
    "production",
    "reservoir",
    "schedule",
    "template",
    "transplant",
    "unmodelled",
)
SOURCE_CLASSES = ("substrate", "energy", "machinery", "intervention")
CHEMISTRY = ("species", "moiety")
RECORD_KINDS = ("cumulative", "amount")  # What a weight may point at (§5.2).
RECORD_KEYS = {"array", "times", "kind", "shape", "files"}
EVENT_ROWS = (
    "an event at time t acts between a record's first row saved at a time no earlier than t and "
    "the row after it: an edge with an event and a record is weighed by that change"
)

PARENTLESS = ("founder", "template", "copy", "transplant")  # Each opens a sub-lineage, s:0.
NEWCOMERS = ("template", "copy", "transplant")  # May replace a predecessor in its slot.
ENDS_AT_EVENT = ("divided", "replaced", "not_followed", "removed", "transplanted_out")

COUNT_LIMIT = 1 << 32
LINEAGE_LIMIT = 1 << 31
SHARE_SUM_TOLERANCE = 1e-9  # A division's shares sum to at most 1, with rounding.

SEGMENT = r"[A-Za-z0-9_.@+\-]+"
NAME = re.compile(rf"{SEGMENT}(?:/{SEGMENT})*")
WORD = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.+\-]*")
PIECE = re.compile(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*@[0-9]+")
QUALIFIER = re.compile(r"[0-9a-f]{64}")
INDEX = re.compile(r"[0-9]+(?:,[0-9]+)*")


class RelationsRefused(ValueError):
    """The writer cannot state the tables as given: nothing is written."""


class RelationsInvalid(ValueError):
    """Saved tables break the format: the reader's check."""


# ------------------------------------------------------------------ rows

NAN = math.nan


@dataclass(frozen=True, order=True)
class Node:
    """A vertex that is not a carrier, source or label: a slot, a held node, a sink, a mechanism."""

    id: str
    kind: str
    declared_by: str


@dataclass(frozen=True)
class Life:
    """One carrier from its birth to its end (§1.2).

    key and lineage: its s:c key and the sub-lineage its daughters draw from (-1: none; §1.3).
    slot: the storage it occupies ("" for an unfollowed daughter). parent and share: the life it
    was split from, and its share of that parent's material (division only). donor: the life a
    copy was made from (copy only). predecessor: the previous occupant of its slot. generation and
    root: divisions since its root, its earliest ancestor by division (itself without a parent).
    declared_by: the mechanism whose rows it is (a piece ID).
    """

    id: str
    key: int
    lineage: int
    birth_time: float
    birth_kind: str
    end_time: float
    end_reason: str
    generation: int
    root: str
    declared_by: str
    slot: str = ""
    parent: str = ""
    share: float = NAN
    donor: str = ""
    predecessor: str = ""
    birth_event: str = ""
    end_event: str = ""


@dataclass(frozen=True)
class Event:
    """A birth, end or intervention: at a time and step (-1: off any step grid), of a kind, acting
    at a vertex, made by a mechanism, supplied or paid for by a source ("" if none is declared)."""

    id: str
    time: float
    kind: str
    by: str
    scheduled: bool
    step: int = -1
    at: str = ""
    source: str = ""


@dataclass(frozen=True)
class Edge:
    """A relation from one vertex to another (``from_`` is the ``from`` column). weight: a number on
    the edge; or weight_record and weight_index: a declared record and one position on each of its
    axes after the first, whose rows weigh the edge. mode: the flux material rode."""

    relation: str
    from_: str
    to: str
    declared_by: str
    event: str = ""
    time_from: float = NAN
    time_to: float = NAN
    species: str = ""
    weight: float = NAN
    weight_record: str = ""
    weight_index: str = ""
    mode: str = ""


@dataclass(frozen=True)
class Source:
    """A supplier of material or payer of work (``class_`` is the ``class`` column): where it acts
    ("" for several places, which its edges name), the species it carries and the work records it
    pays (comma-separated), and the record that books its supply."""

    id: str
    kind: str
    class_: str
    declared_by: str
    at: str = ""
    carries: str = ""
    record: str = ""
    payer_of: str = ""


@dataclass(frozen=True)
class Label:
    """A material label on a tracked species or moiety, with its origins (comma-separated) and the
    chemistry rule it follows."""

    id: str
    quantity: str
    origins: str
    chemistry: str
    declared_by: str


# ------------------------------------------------------------------ the schema

TEXT, INT, FLOAT, BOOL = "text", "int64", "float64", "bool"
NULLS = {TEXT: "", INT: -1, FLOAT: "NaN", BOOL: None}
DTYPES = {INT: np.dtype("<i8"), FLOAT: np.dtype("<f8"), BOOL: np.dtype("|b1")}


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    says: str
    required: bool = False  # No null value.
    attribute: str = ""  # The row's field, where it is not the column's name.


def _columns(*specs):
    return tuple(Column(*spec) for spec in specs)


R = True  # A required column (readability of the table below).
WORLD_COLUMN = Column("world", TEXT, "the run qualifier (keys and ids are unique within it)", R)
TABLES = {
    "nodes": (
        "id",
        Node,
        _columns(
            ("id", TEXT, "<kind>:<name>", R),
            ("kind", TEXT, "vocabulary.node_kinds", R),
            ("declared_by", TEXT, "the piece declaring it (a law, operator, kind or model ID)", R),
        ),
    ),
    "lives": (
        "id",
        Life,
        _columns(
            ("id", TEXT, "carrier:<name>", R),
            ("key", INT, "keys.form", R),
            ("lineage", INT, "the sub-lineage its daughters draw their keys from; -1: none", R),
            ("slot", TEXT, "the slot it occupies; '' for none (an unfollowed daughter)"),
            ("parent", TEXT, "the life it was split from (birth_kind division)"),
            ("share", FLOAT, "its share of its parent's material at its birth (division)"),
            ("donor", TEXT, "the life it was copied from (birth_kind copy)"),
            ("predecessor", TEXT, "the previous occupant of its slot, which it replaced"),
            ("birth_time", FLOAT, "on the run's clock", R),
            ("birth_event", TEXT, "the event that made it; '' for a founder or continued life"),
            ("birth_kind", TEXT, "vocabulary.birth_kinds", R),
            ("end_time", FLOAT, "on the run's clock (censored: where the run stopped it)", R),
            ("end_event", TEXT, "the event that ended it; '' when censored, or extinct off one"),
            ("end_reason", TEXT, "vocabulary.end_reasons: every life has one", R),
            ("generation", INT, "divisions since its root", R),
            ("root", TEXT, "its earliest ancestor by division (itself, without a parent)", R),
            ("declared_by", TEXT, "the mechanism whose rows it is", R),
        ),
    ),
    "events": (
        "id",
        Event,
        _columns(
            ("id", TEXT, "event:<name>", R),
            ("time", FLOAT, "on the run's clock", R),
            ("step", INT, "the step index it acts at; -1 off any step grid", R),
            ("kind", TEXT, "what happened, in the mechanism's word", R),
            ("at", TEXT, "the vertex it acts at"),
            ("by", TEXT, "the mechanism that made it (a piece ID)", R),
            ("source", TEXT, "the source that supplied or paid for it"),
            ("scheduled", BOOL, "declared in the definition's schedule, not made by the state", R),
        ),
    ),
    "edges": (
        None,
        Edge,
        _columns(
            ("relation", TEXT, "vocabulary.relations", R),
            ("from", TEXT, "a vertex id", R, "from_"),
            ("to", TEXT, "a vertex id", R),
            ("event", TEXT, "the event it belongs to"),
            ("time_from", FLOAT, "when it starts to hold (occupies: the carrier's birth)"),
            ("time_to", FLOAT, "when it stops (occupies: the carrier's end)"),
            ("species", TEXT, "the species or type it carries"),
            ("weight", FLOAT, "a weight on the edge (parent_of: the daughter's share)"),
            ("weight_record", TEXT, "a record (records) whose rows weigh it"),
            ("weight_index", TEXT, "positions on the record's axes after its first, by commas"),
            ("mode", TEXT, "vocabulary.modes: the flux material rode"),
            ("declared_by", TEXT, "the piece declaring it", R),
        ),
    ),
    "sources": (
        "id",
        Source,
        _columns(
            ("id", TEXT, "source:<name>", R),
            ("kind", TEXT, "vocabulary.source_kinds", R),
            ("class", TEXT, "vocabulary.source_classes", R, "class_"),
            ("at", TEXT, "the vertex it acts at; '' for several, which its edges name"),
            ("carries", TEXT, "species, comma-separated"),
            ("record", TEXT, "the record that books its supply (records)"),
            ("payer_of", TEXT, "work records it pays, comma-separated (records)"),
            ("declared_by", TEXT, "the piece declaring it", R),
        ),
    ),
    "labels": (
        "id",
        Label,
        _columns(
            ("id", TEXT, "label:<name>", R),
            ("quantity", TEXT, "the tracked species or moiety", R),
            ("origins", TEXT, "origin names or ids, comma-separated", R),
            ("chemistry", TEXT, "vocabulary.chemistry", R),
            ("declared_by", TEXT, "the piece declaring it", R),
        ),
    ),
}


def _attribute(column):
    return column.attribute or column.name


def array_name(table, column):
    """The array of a table's column in relations.npz."""
    return f"{table}.{column}"


# ------------------------------------------------------------------ keys, ids and qualifiers


def key(lineage, count):
    """The int64 key s:c (§1.3)."""
    if not (0 <= lineage < LINEAGE_LIMIT and 0 <= count < COUNT_LIMIT):
        raise RelationsRefused(f"a key's sub-lineage and count are in range: {lineage}:{count}")
    return lineage * COUNT_LIMIT + count


def key_parts(value):
    """(s, c) of a key."""
    return divmod(int(value), COUNT_LIMIT)


def key_text(value):
    """A key as s:c."""
    return "{}:{}".format(*key_parts(value))


class Keys:
    """Keys by the s:c rule (§1.3), for a mechanism that assigns them on the host.

    Call open() for each founder in declared order first. Then, in the world's event order (or the
    mode's own order), call open() for each life without a parent and split() for each division.
    """

    def __init__(self):
        self._next = []  # The next count of each sub-lineage.

    def open(self):
        """A life without a parent: (s:0, s), in a new sub-lineage s."""
        lineage = len(self._next)
        self._next.append(1)
        return key(lineage, 0), lineage

    def split(self, lineage, lives_on, continues=0):
        """A division's daughters, in daughter order: [(key, lineage)]. Each draws the next count
        of the parent's sub-lineage `lineage`. Daughter `continues` (an index, or None) keeps that
        sub-lineage; each other daughter that lives on (lives_on[k]) opens a new one, in daughter
        order; the rest hold none (-1)."""
        if not 0 <= lineage < len(self._next):
            raise RelationsRefused(f"a split draws from an open sub-lineage, not {lineage}")
        if continues is not None and not 0 <= continues < len(lives_on):
            raise RelationsRefused(f"the continuing daughter is one of {len(lives_on)}")
        out = []
        for k, living in enumerate(lives_on):
            count = self._next[lineage]
            self._next[lineage] += 1
            if k == continues:
                own = lineage
            elif living:
                own = len(self._next)
                self._next.append(1)
            else:
                own = -1
            out.append((key(lineage, count), own))
        return out


def qualifier(fingerprint, start="fresh", stop=None):
    """A run's qualifier (§1.3): the SHA-256 of {definition fingerprint, start}, and its stop if it
    stopped before its end, as canonical JSON (sorted keys). start: "fresh", or {"checkpoint": its
    digest, "time": t} for a run that starts from one. stop: None, or where the run was stopped
    in the family's own measure (GARD's {"events": e, "fissions": k}), whose last lives end there,
    censored; a run without one keeps the qualifier of {fingerprint, start} alone."""
    if not isinstance(fingerprint, str) or not fingerprint:
        raise RelationsRefused("a qualifier needs the definition's fingerprint")
    if start != "fresh" and not (
        isinstance(start, dict)
        and set(start) == {"checkpoint", "time"}
        and isinstance(start["checkpoint"], str)
        and start["checkpoint"]
        and _finite(start["time"])
    ):
        raise RelationsRefused('a start is "fresh" or {"checkpoint": digest, "time": t}')
    body = {"definition": fingerprint, "start": start}
    if stop is not None:
        if not (
            isinstance(stop, dict)
            and stop
            and all(isinstance(k, str) and k and _finite(v) for k, v in stop.items())
        ):
            raise RelationsRefused("a stop is a mapping of names to finite numbers")
        body["stop"] = stop
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def entity_id(kind, name):
    """The id <kind>:<name>, checked."""
    value = f"{kind}:{name}"
    if kind not in ID_KINDS or not isinstance(name, str) or not NAME.fullmatch(name):
        raise RelationsRefused(f"not an id: {value!r}")
    return value


# ------------------------------------------------------------------ checks


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _id_kind(value):
    """The kind of a well-formed id, or None."""
    if not isinstance(value, str) or ":" not in value:
        return None
    kind, name = value.split(":", 1)
    return kind if kind in ID_KINDS and NAME.fullmatch(name) else None


def _items(text):
    return text.split(",") if text else []


def _piece(value):
    return isinstance(value, str) and PIECE.fullmatch(value) is not None


class _Problems(list):
    def check(self, condition, message):
        if not condition:
            self.append(message)
        return bool(condition)


def _row_name(table, row):
    if table == "edges":
        return f"{row.relation} {row.from_} -> {row.to}"
    return getattr(row, "id", "?")


def _types(table, row, problems):
    """Each value has its column's type; text holds no NUL; a required text is not empty."""
    for column in TABLES[table][2]:
        value = getattr(row, _attribute(column))
        where = f"{table} {_row_name(table, row)}: {column.name}"
        if column.type == TEXT:
            if problems.check(isinstance(value, str), f"{where} is text"):
                problems.check("\0" not in value, f"{where} holds no NUL")
                problems.check(not column.required or value != "", f"{where} is required")
        elif column.type == INT:
            problems.check(_integer(value), f"{where} is an integer")
        elif column.type == FLOAT:
            problems.check(
                isinstance(value, (int, float)) and not isinstance(value, bool),
                f"{where} is a number",
            )
        else:
            problems.check(isinstance(value, bool), f"{where} is a flag")


def _inside(file):
    """A relative .npz path inside the run's folder."""
    if not isinstance(file, str) or not file.endswith(".npz"):
        return False
    path = PurePosixPath(file)
    return not path.is_absolute() and ".." not in path.parts


def _check_records(records, problems):
    """Each record an edge or source may point at: its array and the array of its rows' times, in
    each of its files (rows split across files in order, as windowed runs save them), its kind
    and its whole shape (rows first)."""
    for name, entry in records.items():
        where = f"record {name}"
        if not problems.check(isinstance(name, str) and WORD.fullmatch(name), f"{where}: a word"):
            continue
        if not problems.check(
            isinstance(entry, dict) and set(entry) == RECORD_KEYS,
            f"{where}: its {', '.join(sorted(RECORD_KEYS))}",
        ):
            continue
        for key_name in ("array", "times"):
            value = entry[key_name]
            problems.check(isinstance(value, str) and WORD.fullmatch(value), f"{where}: {key_name}")
        problems.check(entry["kind"] in RECORD_KINDS, f"{where}: its kind is one of {RECORD_KINDS}")
        shape, files = entry["shape"], entry["files"]
        if not problems.check(
            isinstance(shape, (list, tuple))
            and len(shape) >= 1
            and all(_integer(n) and n >= 0 for n in shape),
            f"{where}: its shape lists its axes' lengths, rows first",
        ):
            continue
        end = 0
        parts = files if isinstance(files, (list, tuple)) and files else [None]
        for part in parts:
            if not problems.check(
                isinstance(part, dict)
                and set(part) == {"file", "rows"}
                and _inside(part["file"])
                and isinstance(part["rows"], (list, tuple))
                and len(part["rows"]) == 2
                and all(_integer(n) for n in part["rows"]),
                f"{where}: each part is an .npz file inside the run's folder and its rows",
            ):
                break
            problems.check(
                part["rows"][0] == end and part["rows"][1] >= end,
                f"{where}: its files hold its rows in order, each from where the last stopped",
            )
            end = part["rows"][1]
        else:
            problems.check(end == shape[0], f"{where}: its files hold its {shape[0]} rows")


def _check_pointer(where, record, index, records, problems):
    """weight_record and weight_index: a declared record, and one position on each of its axes
    after the first, inside its shape."""
    if not record:
        problems.check(index == "", f"{where}: a weight_index needs its weight_record")
        return
    if not problems.check(record in records, f"{where}: weight_record {record} is declared"):
        return
    shape = list(records[record]["shape"])
    positions = [int(p) for p in _items(index)] if INDEX.fullmatch(index) else None
    if index == "":
        positions = []
    problems.check(
        positions is not None
        and len(positions) == len(shape) - 1
        and all(p < n for p, n in zip(positions, shape[1:], strict=True)),
        f"{where}: weight_index {index!r} gives one position on each axis of {record}'s shape "
        f"{shape} after the first",
    )


def _derive(lives, sources, labels):
    """The rows derived from lives, sources and labels: their nodes, and the descent edges."""
    nodes = [Node(x.id, "carrier", x.declared_by) for x in lives]
    nodes += [Node(x.id, "source", x.declared_by) for x in sources]
    nodes += [Node(x.id, "label", x.declared_by) for x in labels]
    edges = []
    for life in lives:
        at = dict(event=life.birth_event, time_from=life.birth_time, time_to=life.birth_time)
        if life.parent:
            share = dict(weight=life.share, mode="event")
            edges.append(Edge("parent_of", life.parent, life.id, life.declared_by, **at, **share))
        if life.predecessor:
            edges.append(
                Edge("precedes_in_slot", life.predecessor, life.id, life.declared_by, **at)
            )
        if life.donor:
            edges.append(Edge("copied_from", life.donor, life.id, life.declared_by, **at))
        if life.slot:
            held = dict(at, time_to=life.end_time)
            edges.append(Edge("occupies", life.id, life.slot, life.declared_by, **held))
    return nodes, edges


def _check_life(life, by_id, events, vertices, children, successors, problems, reasons=None):
    """§1.2's rules for one life: its kinds, times, events, origin and end."""
    where = f"lives {life.id}"
    if not problems.check(_id_kind(life.id) == "carrier", f"{where}: its id is carrier:<name>"):
        return
    problems.check(_piece(life.declared_by), f"{where}: declared_by is a piece ID")
    kind, reason = life.birth_kind, life.end_reason
    if not problems.check(
        kind in BIRTH_KINDS, f"{where}: birth_kind {kind!r} is in the vocabulary"
    ):
        return
    if not problems.check(
        reason in (END_REASONS if reasons is None else reasons),
        f"{where}: end_reason {reason!r} is in the vocabulary",
    ):
        return
    if not problems.check(
        _finite(life.birth_time) and _finite(life.end_time) and life.birth_time <= life.end_time,
        f"{where}: born at a finite time no later than its end",
    ):
        return
    if life.slot:
        problems.check(
            _id_kind(life.slot) == "slot" and life.slot in vertices,
            f"{where}: its slot {life.slot} is a declared slot",
        )
    problems.check(
        bool(life.parent) == (kind == "division"),
        f"{where}: a parent exactly when born by division",
    )
    problems.check(bool(life.donor) == (kind == "copy"), f"{where}: a donor exactly when a copy")
    problems.check(
        not life.predecessor or kind in NEWCOMERS,
        f"{where}: only a newcomer ({', '.join(NEWCOMERS)}) has a predecessor",
    )
    problems.check(
        (math.isnan(life.share) and kind != "division")
        or (kind == "division" and 0.0 <= life.share <= 1.0),
        f"{where}: a share in [0, 1] exactly when born by division",
    )
    problems.check(
        bool(life.birth_event) == (kind not in ("founder", "continued")),
        f"{where}: a birth event unless a founder or continued",
    )
    problems.check(
        bool(life.end_event) == (reason in ENDS_AT_EVENT or reason == "lysed")
        or reason == "extinct",
        f"{where}: an end event exactly when it ended at one ({', '.join(ENDS_AT_EVENT)}; "
        "extinct: either)",
    )
    for name, event, time in (
        ("birth", life.birth_event, life.birth_time),
        ("end", life.end_event, life.end_time),
    ):
        if event and problems.check(event in events, f"{where}: its {name} event {event} exists"):
            problems.check(
                events[event].time == time, f"{where}: its {name} is at its event's time"
            )
    if reason == "not_followed":
        problems.check(
            kind == "division"
            and not life.slot
            and life.end_time == life.birth_time
            and life.end_event == life.birth_event,
            f"{where}: an unfollowed daughter ends at its birth event, with no slot",
        )
    parent = by_id.get(life.parent)
    if life.parent and problems.check(
        parent is not None, f"{where}: its parent {life.parent} is a life"
    ):
        problems.check(
            parent.end_reason == "divided"
            and parent.end_time == life.birth_time
            and parent.end_event == life.birth_event,
            f"{where}: born where its parent ended, divided, at the same event and time",
        )
        problems.check(
            life.generation == parent.generation + 1 and life.root == parent.root,
            f"{where}: one generation after its parent, with its parent's root",
        )
    elif kind in PARENTLESS:
        problems.check(
            life.generation == 0 and life.root == life.id,
            f"{where}: generation 0 and its own root, without a parent",
        )
    elif kind == "continued":  # Carried from the run it continues.
        problems.check(
            life.generation >= 0 and _id_kind(life.root) == "carrier",
            f"{where}: a continued life carries its generation and root",
        )
    before = by_id.get(life.predecessor)
    if life.predecessor and problems.check(
        before is not None, f"{where}: its predecessor is a life"
    ):
        problems.check(
            bool(life.slot)
            and before.slot == life.slot
            and before.end_reason == "replaced"
            and before.end_time == life.birth_time
            and before.end_event == life.birth_event,
            f"{where}: its predecessor left its slot, replaced, at its birth event",
        )
    donor = by_id.get(life.donor)
    if life.donor and problems.check(
        donor is not None, f"{where}: its donor {life.donor} is a life"
    ):
        problems.check(
            donor.id != life.id and donor.birth_time <= life.birth_time <= donor.end_time,
            f"{where}: its donor is another life, alive at the copy",
        )
    daughters = children.get(life.id, [])
    if reason == "divided":
        if problems.check(len(daughters) >= 2, f"{where}: divided into two daughters or more"):
            total = math.fsum(d.share for d in daughters if not math.isnan(d.share))
            problems.check(
                total <= 1.0 + SHARE_SUM_TOLERANCE,
                f"{where}: its daughters' shares sum to at most 1 ({total!r})",
            )
    else:
        problems.check(not daughters, f"{where}: only a divided life has daughters")
    followers = successors.get(life.id, [])
    if reason == "replaced":
        problems.check(
            len(followers) == 1 and bool(life.slot),
            f"{where}: replaced by exactly one newcomer in its slot",
        )
    else:
        problems.check(not followers, f"{where}: only a replaced life has a successor")


def _check_slots(lives, problems):
    """A slot holds at most one carrier at a time."""
    held = {}
    for life in lives:
        if life.slot and _finite(life.birth_time) and _finite(life.end_time):
            held.setdefault(life.slot, []).append(life)
    for slot, occupants in held.items():
        occupants.sort(key=lambda x: (x.birth_time, x.end_time, x.id))
        for before, after in zip(occupants, occupants[1:], strict=False):
            problems.check(
                after.birth_time >= before.end_time,
                f"slot {slot}: {before.id} and {after.id} occupy it at once",
            )


def _check_keys(lives, by_id, problems):
    """§1.3 across the world: keys unique; a life without a parent holds s:0 and opens s; a
    daughter draws a count of its parent's sub-lineage, and at most one daughter of a division
    continues it; every sub-lineage is opened once; its counts run 1, 2, ... in birth order; the
    sub-lineages are 0 .. S-1, the founders' first. A world with a continued life carries counts
    and sub-lineages from the run it continues, so there only the openers, the uniqueness and the
    order of counts are checked."""
    holder = {}
    for life in lives:
        where = f"lives {life.id}"
        if not problems.check(
            0 <= life.key < LINEAGE_LIMIT * COUNT_LIMIT and -1 <= life.lineage < LINEAGE_LIMIT,
            f"{where}: its key and lineage are in range",
        ):
            return
        if not problems.check(
            life.key not in holder,
            f"{where}: key {key_text(life.key)} is unique (also held by {holder.get(life.key)})",
        ):
            return
        holder[life.key] = life.id
    continued = any(x.birth_kind == "continued" for x in lives)
    openers, counts, continuing = {}, {}, {}
    for life in lives:
        where = f"lives {life.id}"
        s, c = key_parts(life.key)
        if life.birth_kind in PARENTLESS:
            problems.check(
                c == 0 and life.lineage == s,
                f"{where}: without a parent it holds s:0 and opens s "
                f"({key_text(life.key)}, lineage {life.lineage})",
            )
            openers.setdefault(s, []).append(life.id)
        elif life.birth_kind == "division" and life.parent in by_id:
            parent = by_id[life.parent]
            if problems.check(
                parent.lineage >= 0 and s == parent.lineage and c >= 1,
                f"{where}: a daughter draws a count of its parent's sub-lineage "
                f"({key_text(life.key)}; the parent's lineage {parent.lineage})",
            ):
                counts.setdefault(s, []).append(life)
            if life.lineage == parent.lineage:
                continuing.setdefault((life.parent, life.birth_event), []).append(life.id)
            elif life.lineage >= 0:
                openers.setdefault(life.lineage, []).append(life.id)
        elif life.birth_kind == "continued":
            if c >= 1:
                counts.setdefault(s, []).append(life)
            if life.lineage >= 0 and (life.lineage != s or c == 0):
                openers.setdefault(life.lineage, []).append(life.id)
    for s, ids in sorted(openers.items()):
        problems.check(len(ids) == 1, f"sub-lineage {s} is opened once, not by {sorted(ids)}")
    for (parent, _), ids in sorted(continuing.items()):
        problems.check(
            len(ids) <= 1, f"lives {parent}: one daughter at most continues its sub-lineage {ids}"
        )
    for s, members in sorted(counts.items()):
        members.sort(key=lambda x: (x.birth_time, x.key))
        drawn = [key_parts(x.key)[1] for x in members]
        problems.check(
            drawn == sorted(drawn), f"sub-lineage {s}: its counts are drawn in birth order {drawn}"
        )
        if not continued:
            problems.check(
                drawn == list(range(1, len(drawn) + 1)),
                f"sub-lineage {s}: its counts run 1, 2, ... with no gap {drawn}",
            )
    if continued:
        return
    for life in lives:
        problems.check(
            life.lineage < 0 or life.lineage in openers,
            f"lives {life.id}: its lineage {life.lineage} is opened by a life",
        )
    opened = sorted(openers)
    problems.check(
        opened == list(range(len(opened))), f"the sub-lineages run 0 .. S-1 with no gap {opened}"
    )
    founders = sorted(key_parts(x.key)[0] for x in lives if x.birth_kind == "founder")
    problems.check(
        founders == list(range(len(founders))),
        f"the founders open the first sub-lineages {founders}",
    )


def _check_events(events, vertices, sources, problems):
    for event in events:
        where = f"events {event.id}"
        if not problems.check(_id_kind(event.id) == "event", f"{where}: its id is event:<name>"):
            continue
        problems.check(_finite(event.time), f"{where}: at a finite time")
        problems.check(event.step >= -1, f"{where}: its step is -1 or more")
        problems.check(WORD.fullmatch(event.kind) is not None, f"{where}: its kind is a word")
        problems.check(_piece(event.by), f"{where}: by is a piece ID")
        problems.check(not event.at or event.at in vertices, f"{where}: it acts at a vertex")
        problems.check(
            not event.source or event.source in sources,
            f"{where}: its source {event.source} is a declared source",
        )


def _check_nodes(nodes, problems):
    for node in nodes:
        where = f"nodes {node.id}"
        problems.check(node.kind in NODE_KINDS, f"{where}: its kind {node.kind!r} is a node kind")
        problems.check(_id_kind(node.id) == node.kind, f"{where}: its id is {node.kind}:<name>")
        problems.check(_piece(node.declared_by), f"{where}: declared_by is a piece ID")


def _check_sources(sources, vertices, records, problems):
    for source in sources:
        where = f"sources {source.id}"
        problems.check(_id_kind(source.id) == "source", f"{where}: its id is source:<name>")
        problems.check(
            source.kind in SOURCE_KINDS, f"{where}: its kind {source.kind!r} is a source kind"
        )
        problems.check(
            source.class_ in SOURCE_CLASSES,
            f"{where}: its class {source.class_!r} is a source class",
        )
        problems.check(_piece(source.declared_by), f"{where}: declared_by is a piece ID")
        problems.check(not source.at or source.at in vertices, f"{where}: it acts at a vertex")
        carried = _items(source.carries)
        problems.check(
            all(WORD.fullmatch(s) for s in carried) and carried == sorted(set(carried)),
            f"{where}: carries lists species, sorted, once each",
        )
        problems.check("," not in source.record, f"{where}: one supply record")
        for name in (*_items(source.record), *_items(source.payer_of)):
            problems.check(
                records.get(name, {}).get("kind") == "cumulative",
                f"{where}: its record {name} is a declared cumulative record",
            )


def _check_labels(labels, problems):
    for label in labels:
        where = f"labels {label.id}"
        problems.check(_id_kind(label.id) == "label", f"{where}: its id is label:<name>")
        problems.check(
            WORD.fullmatch(label.quantity) is not None, f"{where}: its quantity is a word"
        )
        problems.check(label.chemistry in CHEMISTRY, f"{where}: its chemistry is in the vocabulary")
        problems.check(_piece(label.declared_by), f"{where}: declared_by is a piece ID")
        origins = _items(label.origins)
        problems.check(
            bool(origins) and all(NAME.fullmatch(o) or _id_kind(o) for o in origins),
            f"{where}: its origins are names or ids, comma-separated",
        )


def _check_edges(edges, vertices, events, records, problems):
    seen = set()
    for edge in edges:
        where = f"edges {edge.relation} {edge.from_} -> {edge.to}"
        row = _row_key(edge)
        problems.check(row not in seen, f"{where}: listed once")
        seen.add(row)
        if not problems.check(
            edge.relation in RELATIONS, f"{where}: its relation is in the vocabulary"
        ):
            continue
        for end in (edge.from_, edge.to):
            if edge.relation in HISTORY:  # Between worlds: an end may be another world's.
                problems.check(_id_kind(end) in NODE_KINDS, f"{where}: {end} is a vertex id")
            else:
                problems.check(end in vertices, f"{where}: {end} is a vertex of this world")
        problems.check(_piece(edge.declared_by), f"{where}: declared_by is a piece ID")
        problems.check(not edge.event or edge.event in events, f"{where}: its event exists")
        problems.check(
            all(
                math.isnan(t) or math.isfinite(t)
                for t in (edge.time_from, edge.time_to, edge.weight)
            ),
            f"{where}: its times and weight are finite or NaN",
        )
        problems.check(
            math.isnan(edge.time_from)
            or math.isnan(edge.time_to)
            or edge.time_from <= edge.time_to,
            f"{where}: it starts no later than it stops",
        )
        problems.check(
            not edge.species or WORD.fullmatch(edge.species) is not None,
            f"{where}: its species is a word",
        )
        problems.check(
            not (edge.weight_record and not math.isnan(edge.weight)),
            f"{where}: a weight on the edge or a record's, not both",
        )
        _check_pointer(where, edge.weight_record, edge.weight_index, records, problems)
        if edge.relation in FLOWS:
            problems.check(edge.mode in MODES, f"{where}: a flow states its mode")
        elif edge.relation == "parent_of":
            problems.check(edge.mode == "event", f"{where}: parent_of moves material at its event")
        else:
            problems.check(edge.mode in ("", *MODES), f"{where}: its mode is in the vocabulary")


def _unique(table, rows, problems):
    seen = set()
    for row in rows:
        problems.check(row.id not in seen, f"{table} {row.id}: its id is unique")
        seen.add(row.id)


def _problems(world, rows, records, reasons=None):
    """Every problem of a world's complete tables (rows: {table: [row]}, derived rows included)."""
    problems = _Problems()
    problems.check(
        isinstance(world, str) and QUALIFIER.fullmatch(world) is not None,
        "world is a run qualifier (qualifier(): 64 hex digits)",
    )
    if not problems.check(isinstance(records, dict), "records maps record names to their files"):
        records = {}
    _check_records(records, problems)
    for table, items in rows.items():
        cls = TABLES[table][1]
        for row in items:
            if problems.check(type(row) is cls, f"{table}: a row is a {cls.__name__}"):
                _types(table, row, problems)
    if problems:
        return problems
    for table in ("nodes", "lives", "events", "sources", "labels"):
        _unique(table, rows[table], problems)
    vertices = {x.id: x for x in rows["nodes"]}
    by_id = {x.id: x for x in rows["lives"]}
    events = {x.id: x for x in rows["events"]}
    sources = {x.id: x for x in rows["sources"]}
    children, successors = {}, {}
    for life in rows["lives"]:
        if life.parent:
            children.setdefault(life.parent, []).append(life)
        if life.predecessor:
            successors.setdefault(life.predecessor, []).append(life)
    _check_nodes(rows["nodes"], problems)
    for life in rows["lives"]:
        _check_life(life, by_id, events, vertices, children, successors, problems, reasons)
    if not problems:  # The world-wide rules read every life's own as already checked.
        _check_slots(rows["lives"], problems)
        _check_keys(rows["lives"], by_id, problems)
    _check_events(rows["events"], vertices, sources, problems)
    _check_sources(rows["sources"], vertices, records, problems)
    _check_labels(rows["labels"], problems)
    _check_edges(rows["edges"], vertices, events, records, problems)
    return problems


# ------------------------------------------------------------------ columns


def _row_key(row):
    """A row's values as a comparable tuple in which NaN equals NaN and sorts last (a dataclass's
    own equality never finds two NaN fields equal)."""
    return tuple(
        (math.isnan(v), 0.0 if math.isnan(v) else v) if isinstance(v, float) else (False, v)
        for v in astuple(row)
    )


def _sort_key(table, row):
    if table == "lives":
        return (row.key,)
    if table == "events":
        return (row.time, row.id)
    if table == "edges":
        return _row_key(row)
    return (row.id,)


def _text(values):
    width = max([1, *(len(v) for v in values)])
    return np.asarray(values, dtype=f"<U{width}").reshape(len(values))


def _encode(table, rows, world):
    """{array name: column} of a table's rows, sorted."""
    rows = sorted(rows, key=lambda row: _sort_key(table, row))
    out = {array_name(table, "world"): _text([world] * len(rows))}
    for column in TABLES[table][2]:
        values = [getattr(row, _attribute(column)) for row in rows]
        name = array_name(table, column.name)
        if column.type == TEXT:
            out[name] = _text(values)
        else:
            out[name] = np.asarray(values, dtype=DTYPES[column.type]).reshape(len(rows))
    return out


def _decode(table, arrays):
    """The rows of a table's saved columns."""
    cls, columns = TABLES[table][1], TABLES[table][2]
    cast = {TEXT: str, INT: int, FLOAT: float, BOOL: bool}
    data = [(c, arrays[array_name(table, c.name)]) for c in columns]
    count = len(arrays[array_name(table, "world")])
    return [
        cls(**{_attribute(c): cast[c.type](values[i].item()) for c, values in data})
        for i in range(count)
    ]


def _descriptor(world, arrays, records, version=FORMAT):
    out_tables = {}
    for table, (key_column, _, columns) in TABLES.items():
        out_tables[table] = {
            "key": key_column,
            "rows": int(len(arrays[array_name(table, "world")])),
            "columns": [
                {
                    "name": c.name,
                    "array": array_name(table, c.name),
                    "type": c.type,
                    "null": None if c.required else NULLS[c.type],
                    "says": c.says,
                }
                for c in (WORLD_COLUMN, *columns)
            ],
        }
    return {
        "format": version,
        "world": world,
        "arrays": ARRAYS,
        "tables": out_tables,
        "records": {
            name: {
                "array": e["array"],
                "times": e["times"],
                "kind": e["kind"],
                "shape": [int(n) for n in e["shape"]],
                "files": [
                    {"file": f["file"], "rows": [int(n) for n in f["rows"]]} for f in e["files"]
                ],
            }
            for name, e in sorted(records.items())
        },
        "vocabulary": {
            "node_kinds": list(NODE_KINDS),
            "birth_kinds": list(BIRTH_KINDS),
            "end_reasons": list(VOCABULARY[version]),
            "relations": list(RELATIONS),
            "modes": list(MODES),
            "source_kinds": list(SOURCE_KINDS),
            "source_classes": list(SOURCE_CLASSES),
            "chemistry": list(CHEMISTRY),
        },
        "ids": "<kind>:<name>: a vertex's kind is its node kind, an event's is event; a name is "
        "ASCII segments of letters, digits and _ . @ + - joined by /. Unique within a world, "
        "event ids included (a family may qualify an event's name by its carrier); the world "
        "column, the run qualifier, tells them apart across runs, and no id carries it",
        "keys": {
            "form": "s:c, stored as s * 2**32 + c (int64)",
            "rule": "a life without a parent holds s:0 and opens sub-lineage s, the founders "
            "0 .. F-1 in declared order; a division's daughters draw the next counts of their "
            "parent's sub-lineage, in daughter order; one may continue it, and each other "
            "daughter that lives on opens a new one, numbered in the mechanism's event order",
            "lineage": "the sub-lineage a life's daughters draw from; -1: none",
        },
        "derived": {
            "nodes": "each life, source and label is also a node (carrier, source, label)",
            "edges": "from lives, each at the later life's birth event and declared by its "
            "mechanism: parent_of (parent to daughter; weight its share; mode event), "
            "precedes_in_slot (predecessor to newcomer), copied_from (donor to copy) and occupies "
            "(carrier to slot, from its birth to its end)",
        },
        "weights": "weight_record names a record above; weight_index gives one position on each "
        "of its axes after the first; that column of the record's rows weighs the edge. A record "
        "names the array of its rows' times (times) and its files, which hold its rows in order. "
        "A cumulative record weighs an interval by its change over it, an amount by its value "
        "at a row",
        "event_rows": EVENT_ROWS,
        "sorted": "nodes, sources and labels by id; lives by key; events by time, then id; "
        "edges by every column",
    }


def tables(
    *,
    world,
    lives=(),
    events=(),
    nodes=(),
    sources=(),
    labels=(),
    edges=(),
    records=None,
    version=FORMAT,
):
    """(descriptor, arrays) of a world's tables, checked: refused (RelationsRefused, every problem
    listed) before anything is built. Callers give lives, events, sources and labels, and the nodes
    and edges that are not derived (module docstring). records: {name: {"array", "times", "kind",
    "shape", "files"}} (records_in), the run's records that edges and sources point at."""
    given = dict(
        lives=list(lives),
        events=list(events),
        nodes=list(nodes),
        sources=list(sources),
        labels=list(labels),
        edges=list(edges),
    )
    records = {} if records is None else records
    problems = _Problems()
    for node in given["nodes"]:
        problems.check(
            not (isinstance(node, Node) and node.kind in DERIVED_NODE_KINDS),
            f"nodes {getattr(node, 'id', node)}: carrier, source and label nodes are derived",
        )
    for edge in given["edges"]:
        problems.check(
            not (isinstance(edge, Edge) and edge.relation in DESCENT),
            f"edges {getattr(edge, 'relation', edge)}: descent edges are derived from lives",
        )
    for table in ("lives", "sources", "labels"):
        cls = TABLES[table][1]
        problems.check(
            all(type(x) is cls for x in given[table]), f"{table}: every row is a {cls.__name__}"
        )
    if not problems:
        nodes, edges = _derive(given["lives"], given["sources"], given["labels"])
        rows = dict(given, nodes=given["nodes"] + nodes, edges=given["edges"] + edges)
        problems += _problems(world, rows, records, VOCABULARY[version])
    if problems:
        raise RelationsRefused(f"{len(problems)} problem(s) in the tables: " + "; ".join(problems))
    arrays = {}
    for table in TABLES:
        arrays.update(_encode(table, rows[table], world))
    return _descriptor(world, arrays, records, version), arrays


def dumps(descriptor):
    """The descriptor's bytes: sorted keys, no NaN, a final newline."""
    return json.dumps(descriptor, indent=1, sort_keys=True, allow_nan=False) + "\n"


def _npz_shapes(path):
    """{array: shape} of an .npz archive, from its arrays' headers alone."""
    readers = {
        (1, 0): np.lib.format.read_array_header_1_0,
        (2, 0): np.lib.format.read_array_header_2_0,
    }
    out = {}
    with zipfile.ZipFile(path) as archive:
        for member in archive.namelist():
            if member.endswith(".npy"):
                with archive.open(member) as stream:
                    version = np.lib.format.read_magic(stream)
                    if version in readers:
                        out[member[: -len(".npy")]] = tuple(readers[version](stream)[0])
    return out


def records_in(directory, files, kinds, *, times):
    """The records that edges and sources may point at, {name: record}, for arrays saved across
    a run's record files (.npz files in `directory`, in row order), read from their headers.
    kinds: {array: "cumulative" or "amount"}; times: the array of their rows' times, in each
    file."""
    out = {
        name: {"array": name, "times": times, "kind": kind, "files": []}
        for name, kind in kinds.items()
    }
    for file in files:
        shapes = _npz_shapes(Path(directory) / file)
        missing = [name for name in (times, *kinds) if name not in shapes]
        if missing:
            raise RelationsRefused(f"{file} holds no array {missing}")
        rows = shapes[times][0]
        for name, entry in out.items():
            start = entry["files"][-1]["rows"][1] if entry["files"] else 0
            if (
                shapes[name][0] != rows
                or entry.setdefault("axes", shapes[name][1:]) != shapes[name][1:]
            ):
                raise RelationsRefused(
                    f"{file}: {name} has shape {shapes[name]} against {rows} rows"
                )
            entry["files"].append({"file": file, "rows": [start, start + rows]})
    for entry in out.values():
        axes = entry.pop("axes", ())
        entry["shape"] = [entry["files"][-1]["rows"][1] if entry["files"] else 0, *axes]
    return out


def _record_times(directory, entry, name, problems, shapes):
    """A record's rows' times, across its files, after checking each file holds the record and
    its times at the declared shapes; None if one does not."""
    times = []
    for part in entry["files"]:
        path = Path(directory) / part["file"]
        if not problems.check(path.is_file(), f"record {name}: its file {part['file']} exists"):
            return None
        if part["file"] not in shapes:
            shapes[part["file"]] = _npz_shapes(path)
        rows = part["rows"][1] - part["rows"][0]
        held = shapes[part["file"]]
        for array, shape in (
            (entry["array"], (rows, *entry["shape"][1:])),
            (entry["times"], (rows,)),
        ):
            if not problems.check(
                held.get(array) == shape,
                f"record {name}: {part['file']} holds {array} with shape {list(shape)} "
                f"(found {held.get(array)})",
            ):
                return None
        with np.load(path, allow_pickle=False) as saved:
            times.append(np.asarray(saved[entry["times"]], dtype=np.float64))
    times = np.concatenate(times) if times else np.zeros(0)
    if not problems.check(
        bool(np.all(np.isfinite(times))) and bool(np.all(np.diff(times) >= 0.0)),
        f"record {name}: its times are finite and never fall",
    ):
        return None
    return times


def _check_files(directory, records, edges, events, problems):
    """Each declared record is in its files in `directory` at its declared shape, with finite
    times that never fall; and each edge weighed by a record across an event has the record's
    rows on both sides of it (EVENT_ROWS)."""
    shapes, times = {}, {}
    for name, entry in sorted(records.items()):
        times[name] = _record_times(directory, entry, name, problems, shapes)
    when = {event.id: event.time for event in events}
    for edge in edges:
        found = times.get(edge.weight_record)
        if not edge.event or found is None or edge.event not in when:
            continue
        at = when[edge.event]
        before = int(np.searchsorted(found, at, side="left"))
        problems.check(
            before + 1 < len(found),
            f"edges {edge.relation} {edge.from_} -> {edge.to}: {edge.weight_record} has a row at "
            f"or after its event's time {at!r} and the row after it",
        )


def _save(path, arrays):
    """An .npz archive whose bytes follow from the arrays alone: members in name order, stored,
    each dated 1980-01-01 (numpy.savez stamps the time of writing)."""
    with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        for name in sorted(arrays):
            info = zipfile.ZipInfo(name + ".npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o644 << 16
            with archive.open(info, "w", force_zip64=True) as stream:
                np.lib.format.write_array(stream, arrays[name], version=(1, 0), allow_pickle=False)


def write(
    directory,
    *,
    world,
    lives=(),
    events=(),
    nodes=(),
    sources=(),
    labels=(),
    edges=(),
    records=None,
    version=FORMAT,
):
    """Write a world's tables into `directory`, beside the run's files: relations.npz, then
    relations.json. The keywords are tables()'s, and `version` is FORMAT, or FORMAT_V2 for a
    writer whose lives may end lysed. Refused, with nothing written, if either file exists, if a
    row is malformed (tables()), or if a declared record is not in its file with its shape.
    Returns the descriptor."""
    directory = Path(directory)
    records = {} if records is None else records
    lives, events, nodes = list(lives), list(events), list(nodes)
    sources, labels, edges = list(sources), list(labels), list(edges)
    descriptor, arrays = tables(
        version=version,
        world=world,
        lives=lives,
        events=events,
        nodes=nodes,
        sources=sources,
        labels=labels,
        edges=edges,
        records=records,
    )
    problems = _Problems()
    for name in (ARRAYS, DESCRIPTOR):
        problems.check(not (directory / name).exists(), f"{directory / name} exists")
    _check_files(directory, records, edges, events, problems)
    if problems:
        raise RelationsRefused("nothing is written: " + "; ".join(problems))
    _save(directory / ARRAYS, arrays)
    (directory / DESCRIPTOR).write_text(dumps(descriptor))
    return descriptor


# ------------------------------------------------------------------ the reader's check


def _check_arrays(descriptor, arrays, problems):
    """The arrays are the descriptor's columns, each with its type and one value per row."""
    expected = set()
    described = descriptor.get("tables")
    if not problems.check(isinstance(described, dict), "the tables are described"):
        return
    for table, (_, _, columns) in TABLES.items():
        entry = described.get(table)
        if not problems.check(isinstance(entry, dict), f"table {table} is described"):
            continue
        for column in (WORLD_COLUMN, *columns):
            name = array_name(table, column.name)
            expected.add(name)
            array = arrays.get(name)
            if not problems.check(array is not None, f"{name} is saved"):
                continue
            problems.check(array.shape == (entry.get("rows"),), f"{name}: one value per row")
            if column.type == TEXT:
                problems.check(
                    array.dtype.kind == "U" and array.dtype.str.startswith("<"),
                    f"{name}: fixed-width little-endian text, not {array.dtype.str}",
                )
            else:
                problems.check(
                    array.dtype == DTYPES[column.type], f"{name}: {column.type}, not {array.dtype}"
                )
    problems.check(set(arrays) <= expected, f"no other arrays: {sorted(set(arrays) - expected)}")


def _machine(descriptor):
    """What a reader relies on in a descriptor: the format, world and arrays file, each table's
    key, rows and columns (name, array, type, null), and the records. Its prose (says, ids, keys,
    derived, weights, event_rows, sorted) and its vocabulary lists are the writer's account, which
    may be reworded within a version; rows are checked against the reader's own vocabulary."""
    columns = ("name", "array", "type", "null")
    tables = descriptor.get("tables") or {}
    return {
        "format": descriptor.get("format"),
        "world": descriptor.get("world"),
        "arrays": descriptor.get("arrays"),
        "tables": {
            name: {
                "key": entry.get("key"),
                "rows": entry.get("rows"),
                "columns": [{k: c.get(k) for k in columns} for c in entry.get("columns") or []],
            }
            for name, entry in tables.items()
            if isinstance(entry, dict)
        },
        "records": descriptor.get("records"),
    }


def validate(descriptor, arrays, directory=None):
    """The reader's check of saved tables (RelationsInvalid, every problem listed): the descriptor's
    machine fields (_machine) are this format's for these arrays; the arrays are its columns; the
    rows pass the writer's checks; the derived rows are exactly those the lives, sources and labels
    give; and, with the run's folder, each record a weight points at is in its file with its
    declared shape."""
    problems = _Problems()
    if not problems.check(
        isinstance(descriptor, dict) and descriptor.get("format") in VOCABULARY,
        f"its format is {FORMAT} or {FORMAT_V2}",
    ):
        raise RelationsInvalid("; ".join(problems))
    _check_arrays(descriptor, arrays, problems)
    if problems:
        raise RelationsInvalid("; ".join(problems))
    world, records = descriptor.get("world"), descriptor.get("records")
    rows = {table: _decode(table, arrays) for table in TABLES}
    for table in TABLES:
        problems.check(
            all(str(w) == world for w in arrays[array_name(table, "world")].tolist()),
            f"{table}: each row's world is the descriptor's",
        )
    version = descriptor["format"]
    problems += _problems(world, rows, records, VOCABULARY[version])
    if not problems:
        nodes, edges = _derive(rows["lives"], rows["sources"], rows["labels"])
        saved_nodes = [n for n in rows["nodes"] if n.kind in DERIVED_NODE_KINDS]
        saved_edges = [e for e in rows["edges"] if e.relation in DESCENT]
        problems.check(
            sorted(saved_nodes) == sorted(nodes),
            "the carrier, source and label nodes are those the lives, sources and labels give",
        )
        problems.check(  # Compared by their NaN-safe sort keys (NaN is never equal to NaN).
            sorted(_row_key(e) for e in saved_edges) == sorted(_row_key(e) for e in edges),
            "the descent edges are those the lives give",
        )
        problems.check(
            _machine(descriptor) == _machine(_descriptor(world, arrays, records, version)),
            "the descriptor's machine fields are the writer's for these tables",
        )
    if directory is not None and not problems:
        _check_files(directory, records, rows["edges"], rows["events"], problems)
    if problems:
        raise RelationsInvalid("; ".join(problems))


def read(directory, *, files=True):
    """(descriptor, {table: [rows]}) of a run's saved tables, checked (validate(); with files, the
    records the weights point at too). Every array loads with allow_pickle=False."""
    directory = Path(directory)
    descriptor = json.loads((directory / DESCRIPTOR).read_text())
    with np.load(directory / ARRAYS, allow_pickle=False) as saved:
        arrays = {name: saved[name] for name in saved.files}
    validate(descriptor, arrays, directory if files else None)
    return descriptor, {table: _decode(table, arrays) for table in TABLES}
