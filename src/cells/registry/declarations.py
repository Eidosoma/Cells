"""The declarations manifest: every registered law, kind and operator, and every active model, from
the build's registries and the static model table.

D185 decided it. FR-12 asks for it, and docs/CORE_SEAMS_DESIGN.md §8.7 calls it one generator
over the registries.

    python -m cells declarations --out FILE

**The contract is the file's format, `cells.declarations@3`.** Its specification is its format
page, docs/library/DECLARATIONS_FORMAT.md, whose key tables tests/unit/test_library_pages.py holds
to this module's key sets; not this or any other Python module (cells.modules is provisional,
D195). The viewer reads the file and never imports the engine. The same tree gives the same
bytes: the file holds no time stamp, its keys are sorted, its pieces are in (piece, id) order and
its models in the static model table's order, and the registries load every home of that table
before they are read (registry/model_table.py), whatever was imported first.

**In short** (the page has the rest):
- top level: `kind`, `revision`, `dirty`, `origin`, `pieces`, `models` and `not_extracted`;
- each piece: its identity (`id`, `namespace.family.name@major`, and `declared_id`, as
  definitions write it: one spelling, so the two are equal; `name` is its last part); where it
  runs (`host` and `declared_host`, `family`, `models`); where it is declared (`module`,
  `module_path`, `line`, `kernels`); its page (`doc`); what it rests on (`provenance`, with
  structured `works`, and `test`); what it touches by role (`reads`, each with its mode,
  `changes`, `owns`, `writes`, `provides`, `controls`, `ledgers`, `energy`); `units`, resolved as
  the run view resolves them; `signs`; `requires`; `laws`; `fields`; `status` and its source;
- each active model: `type`, `module`, `module_path`, `doc`, `rows` (the pieces it declares or
  requires, by slot) and, for the inner model, `next_code`;
- a null means one of three things: the key does not apply to the piece; the pair (interface,
  key) is listed in `not_extracted`, because the interface's contract has no such field yet; or
  else it is not stated.

Values are written as JSON: tuples as lists, mappings and named tuples as objects, functions as
`module.qualname`.
"""

import argparse
import ast
import dataclasses
import functools
import importlib.util
import inspect
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

import cells
from cells.definitions import pump_composite_spec as composite_spec
from cells.definitions import surface_pump_v3_spec as inner_spec
from cells.records import run_view
from cells.registry import ids, kind_registry, model_table
from cells.registry import laws as law_registry
from cells.registry import operators as operator_registry
from cells.registry.kind_registry import qualified

FORMAT = "cells.declarations@3"
KIND_INTERFACE = "cells.kind@1"
OPERATOR_INTERFACE = operator_registry.COMPOSITE_INTERFACE
# Runs @3's own laws and its kinds (registry/kind_registry.py).
INNER = qualified(inner_spec.MODEL_ID)
COMPOSITE = qualified(composite_spec.MODEL_ID)  # Runs the composite's operators.
# The library of pages (docs/LAW_DOCUMENTATION_DESIGN.md §1.2): one page per piece and per model
# with declared structure, at LIBRARY/<namespace>/<section>/<family>.<name>@<major>.md.
LIBRARY = "docs/library"
SECTIONS = MappingProxyType(
    {"law": "laws", "kind": "kinds", "operator": "operators", "model": "models"}
)
# The one switch (§3.4): `doc` stays null until every page is written, so a `doc` that is not null
# always names a file. The commit that writes the last page sets it, with the library's check.
PAGES_COMPLETE = False

TOP_KEYS = ("dirty", "kind", "models", "not_extracted", "origin", "pieces", "revision")
PIECE_KEYS = (
    "changes",
    "controls",
    "declared_host",
    "declared_id",
    "doc",
    "energy",
    "family",
    "fields",
    "host",
    "id",
    "interface",
    "kernels",
    "laws",
    "ledgers",
    "line",
    "models",
    "module",
    "module_path",
    "name",
    "namespace",
    "owns",
    "piece",
    "provenance",
    "provides",
    "reads",
    "requires",
    "signs",
    "status",
    "status_source",
    "test",
    "units",
    "version",
    "writes",
)
MODEL_KEYS = ("declared_id", "doc", "id", "module", "module_path", "next_code", "rows", "type")
ROW_KEYS = ("declared_id", "id", "piece", "role", "slot")
READ_KEYS = ("mode", "name", "scoped", "stage")
KERNEL_KEYS = ("function", "line", "module_path")
PROVENANCE_KEYS = ("citation", "source", "tag")
CITATION_KEYS = law_registry.Citation._fields
WORK_KEYS = law_registry.CitedWork._fields
NOT_EXTRACTED_KEYS = ("interface", "key")
# The keys a contract has no field for yet (CORE_SEAMS §8.1, §15): written as null and listed in
# `not_extracted`, never read as "not stated". Every law interface lacks the template's energy role,
# and every family operator interface its operator's.
UNEXTRACTED = MappingProxyType(
    {
        KIND_INTERFACE: ("energy", "ledgers", "provenance", "test"),
        OPERATOR_INTERFACE: ("provenance", "test"),
    }
)
UNEXTRACTED_LAWS = ("energy",)
UNEXTRACTED_FAMILY_OPERATORS = ("energy",)
# A law's stage reads (registry/laws.py; B4) are taken at every stage of the inner step, at the
# stage's read state: in the operator contract's words, a current read at the inner stage.
LAW_READ = MappingProxyType({"mode": "current", "stage": "inner", "scoped": False})
# The rows of the inner model, by its laws' interfaces, in this order.
INNER_ROLES = (
    (law_registry.CHANNEL_LAW, "channel law"),
    (law_registry.JUNCTION_LAW, "junction law"),
    (law_registry.CYCLE_LAW, "cycle law"),
    (law_registry.ROUTE_LAW, "route law"),
    (law_registry.BINDING_LAW, "binding law"),
)
TEMPLATE_FIELDS = frozenset(f.name for f in dataclasses.fields(law_registry.Law))
FAMILY_OPERATOR_FIELDS = frozenset(
    f.name for f in dataclasses.fields(operator_registry.FamilyOperator)
)
_SOURCE_ROOT = Path(cells.__file__).resolve().parent.parent  # Holds the cells package: src/.
_UNREAD = object()


def _json(value):
    """A declared value as JSON data: functions as module.qualname, named tuples as objects,
    other tuples as lists."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, tuple) and hasattr(value, "_asdict"):
        return {k: _json(v) for k, v in value._asdict().items()}
    if isinstance(value, (tuple, list)):
        return [_json(v) for v in value]
    if isinstance(value, Mapping):
        return {str(k): _json(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted(_json(v) for v in value)
    if callable(value):
        return f"{value.__module__}.{value.__qualname__}"
    raise TypeError(f"No JSON form for a declared {type(value).__name__}: {value!r}")


# ------------------------------------------------------------------ where a piece is declared


def in_tree(module):
    """Whether a module is in the cells package, and so in this repository's src/cells."""
    return isinstance(module, str) and (module == "cells" or module.startswith("cells."))


def module_path(module):
    """The repository path of an in-tree module (`src/cells/...`, the same from a checkout, a
    snapshot or an installed engine), or None outside the cells package."""
    if not in_tree(module):
        return None
    loaded = sys.modules.get(module)
    origin = getattr(loaded, "__file__", None)
    if origin is None:
        found = importlib.util.find_spec(module)
        origin = found.origin if found is not None else None
    if origin is None:
        return None
    return "src/" + Path(origin).resolve().relative_to(_SOURCE_ROOT).as_posix()


@functools.cache
def _syntax(module):
    """An imported in-tree module's syntax tree and namespace."""
    loaded = importlib.import_module(module)
    return ast.parse(inspect.getsource(loaded)), vars(loaded)


def _evaluate(node, namespace):
    """A literal, a name or an attribute chain, read in a module's namespace; _UNREAD otherwise."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return namespace.get(node.id, _UNREAD)
    if isinstance(node, ast.Attribute):
        base = _evaluate(node.value, namespace)
        return _UNREAD if base is _UNREAD else getattr(base, node.attr, _UNREAD)
    return _UNREAD


def declaration_line(module, declared_type, identifier, field):
    """The first line of a declaration in its in-tree module: the one call of `declared_type`
    whose ID (its first argument, or the keyword `field`) is `identifier`, as a literal or a name.
    None outside the cells package. A declaration the read cannot find once is refused, so a
    line never points at another piece."""
    if not in_tree(module):
        return None
    tree, namespace = _syntax(module)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _evaluate(node.func, namespace) is not declared_type:
            continue
        given = [k.value for k in node.keywords if k.arg == field] or node.args[:1]
        if given and _evaluate(given[0], namespace) == identifier:
            found.append(node.lineno)
    if len(found) != 1:
        raise ValueError(
            f"{module}: {len(found)} declarations of {identifier} found; a manifest needs one call "
            f"of {declared_type.__name__} with its ID as a literal or a module-level name"
        )
    return found[0]


def kernel(function):
    """A kernel's record: its `module.qualname`, and the file and first line of its code (null for
    a callable without code of its own, or outside the cells package)."""
    code = getattr(function, "__code__", None)
    module = getattr(function, "__module__", None)
    path = module_path(module) if code is not None else None
    return dict(
        function=_json(function),
        line=code.co_firstlineno if path is not None else None,
        module_path=path,
    )


# ------------------------------------------------------------------ pages and units


def page_path(piece, identifier):
    """A piece's or a model's page (docs/LAW_DOCUMENTATION_DESIGN.md §1.2):
    `docs/library/<namespace>/<section>/<family>.<name>@<major>.md`, from its ID alone."""
    namespace, rest = qualified(identifier).split(".", 1)
    return f"{LIBRARY}/{namespace}/{SECTIONS[piece]}/{rest}.md"


def _doc(piece, identifier, module):
    return page_path(piece, identifier) if PAGES_COMPLETE and in_tree(module) else None


def unit(name, declared):
    """A field's unit as the run view resolves it (docs/RUN_VIEW_DESIGN.md §3): its owner's
    declared unit; else, for a view field of the inner model, the run view's table
    (run_view.VIEW_FIELD_AXES); else the run view's suffix rule (run_view.SUFFIX_UNITS); else
    None, not stated."""
    if name in declared:
        return declared[name]
    view = run_view.VIEW_FIELD_AXES.get(name)
    if view is not None:
        return view[1]
    for suffix, found in run_view.SUFFIX_UNITS:
        if name.endswith(suffix):
            return found
    return None


def _units(role_fields, declared, own=()):
    """{field: unit or None} for every field of a role, and every own field with a unit."""
    out = {name: unit(name, declared) for name in role_fields}
    out.update({name: declared[name] for name in declared})
    out.update({n: unit(n, declared) for n in own if unit(n, declared) is not None})
    return dict(sorted(out.items()))


# ------------------------------------------------------------------ pieces


class _Context:
    """The registries a manifest reads, and the declared spelling of every ID that can host."""

    def __init__(self, laws, kinds, operators):
        self.laws, self.kinds, self.operators = laws, kinds, operators
        spellings = {qualified(key): key for key in model_table.MODELS}
        spellings.update({qualified(k.kind_id): k.kind_id for k in kinds.model_keys().values()})
        spellings.update({qualified(o.LAW_ID): o.LAW_ID for o in operators.operators()})
        spellings.update(
            {qualified(d.operator_id): d.operator_id for d in operators.family_operators()}
        )
        for law in laws._laws.values():  # A host that none of them names: as its laws spell it.
            spellings.setdefault(qualified(law.host), law.host)
        self.spellings = spellings

    def identity(self, declared_id, piece, interface, host, module, line):
        key = qualified(declared_id)
        parts = ids.parts(key)
        family = INNER if host in self.kinds else host
        return dict(
            id=key,
            declared_id=declared_id,
            namespace=parts.namespace,
            name=parts.name,
            version=parts.major,
            piece=piece,
            interface=interface,
            host=host,
            declared_host=self.spellings.get(host),
            family=family,
            models=_models(family),
            module=module,
            module_path=module_path(module),
            line=line,
            doc=_doc(piece, key, module),
        )


def _models(family):
    """The models whose definitions can declare a piece of `family`: the model itself, and each
    composite whose inner model it is; none where `family` is no active model (a host that has no
    row in the static model table)."""
    if family not in {qualified(key) for key in model_table.MODELS}:
        return []
    out = [family]
    if family == INNER and inner_spec.MODEL_ID in composite_spec.INNER_MODEL_IDS:
        out.append(COMPOSITE)
    return sorted(out)


def _entry(**values):
    out = dict.fromkeys(PIECE_KEYS)
    out.update(values)
    return out


def _provenance(declaration):
    """A law's or a family operator's provenance: its tag, its Citation or other source record."""
    source = declaration.source
    return dict(
        tag=declaration.provenance,
        citation=_json(source) if isinstance(source, law_registry.Citation) else None,
        source=None
        if source is None or isinstance(source, law_registry.Citation)
        else _json(source),
    )


def _cycle_changes(law):
    """A cycle law's change rows, from their one source (registry/laws.cycle_changes): its general
    form's ({role, per_cycle, mode}, ...) where the form is set, else its moves."""
    return [dict(row) for row in law_registry.cycle_changes(law)]


def law_entry(law, context):
    """A law's entry: its template fields, then its interface's own (registry/laws.py). The role
    keys are read from the cells interfaces' own fields; a family's interface keeps all of its own
    fields under `fields`."""
    own = [f.name for f in dataclasses.fields(law) if f.name not in TEMPLATE_FIELDS]
    values = {name: getattr(law, name) for name in own}
    cells_interface = isinstance(law, tuple(law_registry.INTERFACES.values()))
    reads = changes = None
    if cells_interface:
        reads = [dict(name=r, **LAW_READ) for r in getattr(law, "reads", ())]
        changes = []
        if isinstance(law, law_registry.ChannelLaw):
            changes = [
                dict(species=s, valence=z, relative_permeability=w) for s, z, w in law.permeant
            ]
        elif isinstance(law, law_registry.CycleLaw):
            changes = _cycle_changes(law)
    module = context.laws.module(law.law_id)
    fields = {
        n: _json(v)
        for n, v in values.items()
        if not callable(v) and not (cells_interface and n == "reads")
    }
    return _entry(
        **context.identity(
            law.law_id,
            "law",
            type(law).interface,
            qualified(law.host),
            module,
            declaration_line(module, type(law), law.law_id, "law_id"),
        ),
        kernels={name: kernel(v) for name, v in values.items() if callable(v)},
        provenance=_provenance(law),
        reads=_json(reads),
        changes=_json(changes),
        units=_units((), type(law).UNITS, own=fields),
        signs=_json(type(law).SIGNS),
        fields=fields,
        test=law.test,
    )


def kind_entry(kind, context):
    """A kind's entry: its fields by role, its hooks, its view's units and signs, and the laws it
    hosts."""
    hooks = [
        f.name
        for f in dataclasses.fields(kind)
        if f.name != "view" and callable(getattr(kind, f.name))
    ]
    module = next((getattr(kind, h).__module__ for h in hooks), None)
    view = kind.view or kind_registry.KindView()
    owns, provides, controls = (
        dict(kind.state_axes),
        [*kind.readout_columns],
        [*kind.control_fields],
    )
    return _entry(
        **context.identity(
            kind.kind_id,
            "kind",
            KIND_INTERFACE,
            INNER,
            module,
            declaration_line(module, type(kind), kind.kind_id, "kind_id"),
        ),
        owns=_json(owns),
        provides=_json(provides),
        controls=_json(controls),
        units=_units([*owns, *provides, *controls], view.units),
        signs=_json(view.orientation),
        laws=sorted(
            qualified(law.law_id)
            for law in context.laws._laws.values()
            if qualified(law.host) == qualified(kind.kind_id)
        ),
        fields=dict(
            model_key=kind.model_key,
            layout_fields=_json(kind.layout_fields),
            experiment_keys=_json(kind.experiment_keys),
            hooks=sorted(hooks),
            record_kinds=_json(view.record_kinds),
            record_layers=_json(view.record_layers),
        ),
    )


def operator_entry(operator, context):
    """A composite operator's entry: its contract declarations (operators/contract.py) by
    role, each read with its mode (door S's Read: current, fixed or reference)."""
    cls = type(operator)
    parts = (("event", "EVENT"), ("split", "SPLIT"), ("process", "PROCESS"))
    read_fields = [*dict.fromkeys((*cls.VIEW_READS, *cls.CONFLICTS_VIEW, *cls.SCOPED_READS))]
    # Every Read of each field, one per stage (door S's reads_of; composition's M2 reads one field
    # at two stages).
    from cells.operators.contract import reads_of

    reads = [dict(name=f, **_json(read)) for f in read_fields for read in reads_of(cls, f)]
    writes = _json(cls.ENTITY_WRITES)
    accumulators = [a for booked in writes.values() for a in booked]
    provides = [*cls.VIEW_FIELDS, *cls.READOUT_COLUMNS]
    controls = [*cls.CONTROL_FIELDS, *cls.CONTROL_FACTORS]
    role_fields = [*read_fields, *cls.STATE_AXES, *writes, *accumulators, *provides, *controls]
    return _entry(
        **context.identity(
            cls.LAW_ID,
            "operator",
            OPERATOR_INTERFACE,
            COMPOSITE,
            cls.__module__,
            cls.__firstlineno__ if in_tree(cls.__module__) else None,
        ),
        reads=reads,
        owns=_json(cls.STATE_AXES),
        writes=writes,
        provides=_json(provides),
        controls=_json(controls),
        ledgers=_json(cls.LEDGERS),
        energy=dict(heat=_json(cls.HEAT_FIELDS), work=_json(cls.WORK_FIELDS)),
        units=_units(role_fields, cls.UNITS),
        signs=_json(cls.ORIENTATION),
        requires=dict(laws=_json(cls.REQUIRES), kinds=_json(cls.REQUIRES_KINDS)),
        fields=dict(
            parts=[word for word, flag in parts if getattr(cls, flag)],
            declaration_only=cls.DECLARATION_ONLY,
            step_method=cls.STEP_ID,
            closes=_json(cls.CLOSES),
            retires=cls.RETIRES,
            experiment_keys=_json(cls.EXPERIMENT_KEYS),
            record_kinds=_json(cls.RECORD_KINDS),
            record_layers=_json(cls.RECORD_LAYERS),
            class_name=cls.__qualname__,
        ),
    )


def family_operator_entry(declaration, context):
    """A family's operator's entry: its template fields, then its interface's own, all under
    `fields` (registry/operators.py, FamilyOperator)."""
    own = [f.name for f in dataclasses.fields(declaration) if f.name not in FAMILY_OPERATOR_FIELDS]
    values = {name: getattr(declaration, name) for name in own}
    module = context.operators.module(declaration.operator_id)
    fields = {n: _json(v) for n, v in values.items() if not callable(v)}
    return _entry(
        **context.identity(
            declaration.operator_id,
            "operator",
            type(declaration).interface,
            qualified(declaration.host),
            module,
            declaration_line(module, type(declaration), declaration.operator_id, "operator_id"),
        ),
        kernels={name: kernel(v) for name, v in values.items() if callable(v)},
        provenance=_provenance(declaration),
        units=_units((), type(declaration).UNITS, own=fields),
        signs=_json(type(declaration).SIGNS),
        fields=fields,
        test=declaration.test,
    )


def not_extracted(pieces):
    """The (interface, key) pairs whose contract has no field for the key yet, for the interfaces
    the pieces use, sorted."""
    pairs = set()
    for entry in pieces:
        interface = entry["interface"]
        if entry["piece"] == "law":
            keys = UNEXTRACTED_LAWS
        elif entry["piece"] == "operator" and interface != OPERATOR_INTERFACE:
            keys = UNEXTRACTED_FAMILY_OPERATORS
        else:
            keys = UNEXTRACTED.get(interface, ())
        pairs |= {(interface, key) for key in keys}
    return [dict(interface=i, key=k) for i, k in sorted(pairs)]


# ------------------------------------------------------------------ models


def _row(role, declared_id, piece, slot=None):
    return dict(
        role=role, id=qualified(declared_id), declared_id=declared_id, piece=piece, slot=slot
    )


def _rows(model_id, model, context):
    """A model's rows (module docstring): the pieces it declares or requires, by slot where it has
    slots; and its next free channel code (the inner model's), or None."""
    laws = context.laws._laws.values()
    hosted = sorted(
        (law for law in laws if qualified(law.host) == model_id),
        key=lambda law: qualified(law.law_id),
    )
    if model.type == "inner":
        out = []
        channels = sorted(
            (law for law in hosted if type(law).interface == law_registry.CHANNEL_LAW),
            key=lambda law: law.code,
        )
        out += [_row("channel law", law.law_id, "law", dict(code=law.code)) for law in channels]
        for interface, role in INNER_ROLES[1:]:
            out += [
                _row(role, law.law_id, "law") for law in hosted if type(law).interface == interface
            ]
        roles = {interface for interface, _ in INNER_ROLES}
        out += [
            _row("law", law.law_id, "law") for law in hosted if type(law).interface not in roles
        ]
        fuels = sorted(
            {f for law in hosted if isinstance(law, law_registry.CycleLaw) for f in law.fuel_kinds}
        )
        out += [_row("fuel kind", fuel, None) for fuel in fuels]
        kinds = sorted(context.kinds.model_keys().values(), key=lambda k: qualified(k.kind_id))
        out += [_row("kind", k.kind_id, "kind", dict(key=k.model_key)) for k in kinds]
        return out, max((law.code for law in channels), default=-1) + 1
    if model.type == "composite":
        operators = sorted(context.operators.operators(), key=lambda op: qualified(op.LAW_ID))
        return [_row("operator", op.LAW_ID, "operator") for op in operators], None
    if model.type == "composition":
        inner, operators = model.composition
        rows = [_row("inner model", inner, "model")]
        rows += [
            _row("operator", law_id, "operator", dict(position=position))
            for position, law_id in enumerate(operators)
        ]
        return rows, None
    rows = [_row("law", law.law_id, "law") for law in hosted]
    rows += [
        _row("operator", d.operator_id, "operator")
        for d in context.operators.family_operators(host=model_id)
    ]
    return rows, None


def model_entries(context):
    """Every active model of the static model table, in its order (registry/model_table.py)."""
    out = []
    for key, model in model_table.MODELS.items():
        model_id = qualified(key)
        rows, next_code = _rows(model_id, model, context)
        paged = model.type != "family" or bool(rows)  # A family with no rows gets no page.
        out.append(
            dict(
                id=model_id,
                declared_id=key,
                type=model.type,
                module=model.module,
                module_path=module_path(model.module),
                doc=_doc("model", model_id, model.module) if paged else None,
                rows=rows,
                next_code=next_code,
            )
        )
    return out


# ------------------------------------------------------------------ the manifest


def manifest():
    """The manifest of the active registries and the static model table, as JSON data (module
    docstring)."""
    from cells.ensemble.cli import source_revision

    context = _Context(law_registry.active(), kind_registry.active(), operator_registry.active())
    pieces = [law_entry(law, context) for law in context.laws._laws.values()]
    pieces += [kind_entry(kind, context) for kind in context.kinds.model_keys().values()]
    pieces += [operator_entry(op, context) for op in context.operators.operators()]
    pieces += [family_operator_entry(d, context) for d in context.operators.family_operators()]
    pieces.sort(key=lambda entry: (entry["piece"], entry["id"]))
    revision = source_revision() or {}
    return dict(
        kind=FORMAT,
        revision=revision.get("revision"),
        dirty=revision.get("dirty"),
        origin=revision.get("origin"),
        pieces=pieces,
        models=model_entries(context),
        not_extracted=not_extracted(pieces),
    )


def dumps(doc):
    """The manifest's bytes: sorted keys, one space of indent, a final newline."""
    return json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def _keys(item, keys):
    return isinstance(item, dict) and set(item) == set(keys)


def format_errors(doc):
    """Why `doc` is not a `cells.declarations@3` manifest (empty: it is one)."""
    if not isinstance(doc, dict) or doc.get("kind") != FORMAT:
        return [f"its kind is {FORMAT}"]
    out = []
    if set(doc) != set(TOP_KEYS):
        out.append(f"its top-level keys are {', '.join(TOP_KEYS)}")
    pieces = doc.get("pieces")
    if not isinstance(pieces, list):
        return [*out, "its pieces are a list"]
    seen = set()
    for entry in pieces:
        if not _keys(entry, PIECE_KEYS):
            out.append(f"a piece has exactly the keys {', '.join(PIECE_KEYS)}: {entry!r:.120}")
            continue
        if (
            entry["piece"] not in ("law", "kind", "operator")
            or (entry["piece"], entry["id"]) in seen
        ):
            out.append(f"{entry['id']}: a law, kind or operator, listed once")
        seen.add((entry["piece"], entry["id"]))
        if entry["status"] is not None and not entry["status_source"]:
            out.append(f"{entry['id']}: a status is copied from a record, which it names")
        page = page_path(entry["piece"], entry["id"]) if entry["piece"] in SECTIONS else None
        if entry["doc"] is not None and entry["doc"] != page:
            out.append(f"{entry['id']}: its doc is its page's path, {page}")
        if any(not _keys(read, READ_KEYS) for read in entry["reads"] or ()):
            out.append(f"{entry['id']}: each read has exactly the keys {', '.join(READ_KEYS)}")
        if any(not _keys(k, KERNEL_KEYS) for k in (entry["kernels"] or {}).values()):
            out.append(f"{entry['id']}: each kernel has exactly the keys {', '.join(KERNEL_KEYS)}")
    unextracted = doc.get("not_extracted")
    if not isinstance(unextracted, list) or any(
        not _keys(p, NOT_EXTRACTED_KEYS) or p["key"] not in PIECE_KEYS for p in unextracted
    ):
        out.append("not_extracted lists (interface, piece key) pairs")
    else:
        for pair in unextracted:
            if any(
                e.get("interface") == pair["interface"] and e.get(pair["key"]) is not None
                for e in pieces
                if isinstance(e, dict)
            ):
                out.append(f"{pair['interface']}'s {pair['key']}: not extracted, so null")
    models = doc.get("models")
    if not isinstance(models, list):
        out.append("its models are a list")
    else:
        ids = [m.get("id") for m in models if isinstance(m, dict)]
        if len(ids) != len(set(ids)):
            out.append("each model is listed once")
        for model in models:
            if not _keys(model, MODEL_KEYS) or model["type"] not in model_table.TYPES:
                out.append(f"a model has exactly the keys {', '.join(MODEL_KEYS)} and a type")
            elif any(not _keys(row, ROW_KEYS) for row in model["rows"]):
                out.append(f"{model['id']}: each row has exactly the keys {', '.join(ROW_KEYS)}")
    return out


def coverage_errors(doc):
    """Where `doc` and the active registries and model table disagree: a registered piece or an
    active model with no entry, or an entry with nothing registered."""
    laws = law_registry.active()
    registered = {("law", key) for key in laws._laws}
    registered |= {
        ("kind", qualified(k.kind_id)) for k in kind_registry.active().model_keys().values()
    }
    operators = operator_registry.active()
    registered |= {("operator", qualified(op.LAW_ID)) for op in operators.operators()}
    registered |= {("operator", qualified(d.operator_id)) for d in operators.family_operators()}
    registered |= {("model", qualified(key)) for key in model_table.MODELS}
    listed = {(e["piece"], e["id"]) for e in doc["pieces"]}
    listed |= {("model", m["id"]) for m in doc["models"]}
    return [f"registered {p} {i} has no entry" for p, i in sorted(registered - listed)] + [
        f"listed {p} {i} is not registered" for p, i in sorted(listed - registered)
    ]


def read(path):
    """A manifest file, refused unless it keeps the format."""
    doc = json.loads(Path(path).read_text())
    errors = format_errors(doc)
    if errors:
        raise ValueError(f"{path}: not a {FORMAT} manifest: " + "; ".join(errors))
    return doc


def write(path):
    """Write the active registries' manifest to `path` (refused if it exists), checked first."""
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"{path} exists; choose a new file")
    doc = manifest()
    errors = format_errors(doc) + coverage_errors(doc)
    if errors:
        raise ValueError("The manifest does not cover the registries: " + "; ".join(errors))
    path.write_text(dumps(doc))
    return doc


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="cells declarations",
        description=f"Write the declarations manifest ({FORMAT}) of the registered pieces.",
    )
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    doc = write(args.out)
    print(
        json.dumps(
            dict(
                out=str(args.out),
                kind=FORMAT,
                pieces=len(doc["pieces"]),
                models=len(doc["models"]),
                revision=doc["revision"],
                dirty=doc["dirty"],
            )
        )
    )
    return 0
