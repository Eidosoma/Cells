"""The declarations manifest: every registered law, kind and operator, from the build's registries.

D185 decided it. FR-12 asks for it, and docs/CORE_SEAMS_DESIGN.md §8.7 calls it one generator
over the registries.

    python -m cells declarations --out FILE

**The contract is the file's format, `cells.declarations@1`**, not this or any other Python module
(cells.modules is provisional, D195). The viewer reads the file and never imports the engine. The
same revision gives the same bytes: the file holds no time stamp, its keys are sorted and its
pieces are in (piece, id) order.

**Top level:**
- `kind`: "cells.declarations@1";
- `revision`, `dirty` and `origin`: the Git revision and dirty state of the checkout or source
  snapshot it was written from (cells.ensemble.cli.source_revision), or null where neither is
  found;
- `pieces`: every registered piece, in the active registries;
- `legacy`: the older model families (D188's legacy/, D196). They are listed by model ID only
  (`id`, `piece` "model", `legacy` true), read from the legacy registration's model dispatch,
  without importing it.

**Each piece:**
- identity:
  - `id`: namespaced (`namespace.name@version`);
  - `declared_id`: as the piece spells it, which is how definitions name it;
  - `namespace`, `name` and `version`;
  - `piece`: "law", "kind" or "operator";
  - `interface`: a law's own (registry/laws.py), `cells.kind@1` or `cells.operator@1`;
- where it runs:
  - `host`: what runs it, a kind or a model (registry/laws.py: `host`). Kinds run in the inner
    model and operators in the composite;
  - `family`: the model family whose registries hold it;
  - `models`: the models whose definitions can declare it;
- `module`: its declaring module (for a law, the module that registered it; for a kind, the module
  of its hooks; for an operator, its class's), and `kernels` (a law's functions, by field, as
  `module.qualname`);
- `provenance`: a law's tag ("parity", "cited" or "calibrated"), its citation (source, place,
  licence and departures) and any other source record. It is null for kinds and operators, which
  declare none;
- what it touches, each by the role its declaration states:
  - `reads`;
  - `changes`: the rows a law moves (a channel law's permeant ions, a cycle law's moves);
  - `owns`: state fields, with their axes;
  - `writes`: an operator's entity writes, with the accumulators that book them;
  - `provides`: view fields and readout columns;
  - `controls`;
- `ledgers`, `energy` (heat and work fields), `units` and `signs`, where declared;
- `requires`: the operators and kinds an operator needs;
- `laws`: the laws a kind hosts;
- `fields`: the rest of its declaration, as declared;
- `status` and `status_source`: a level copied from a record that states one per piece. No such
  record exists today, so both are null; a level is never inferred;
- `test`: the test ID a law names, or null.

Values are written as JSON: tuples as lists, mappings as objects, functions as `module.qualname`.
"""

import argparse
import ast
import dataclasses
import json
from collections.abc import Mapping
from pathlib import Path

import cells
from cells.core import kind_registry
from cells.core import pump_composite_spec as composite_spec
from cells.core import surface_pump_v3_spec as inner_spec
from cells.core.kind_registry import qualified
from cells.core.legacy_entry import LEGACY
from cells.registry import laws as law_registry
from cells.registry import operators as operator_registry

FORMAT = "cells.declarations@1"
KIND_INTERFACE = "cells.kind@1"
OPERATOR_INTERFACE = "cells.operator@1"
INNER = qualified(inner_spec.MODEL_ID)  # Runs @3's own laws and its kinds (core/kind_registry.py).
COMPOSITE = qualified(composite_spec.MODEL_ID)  # Runs the operators.
PIECE_KEYS = (
    "changes",
    "controls",
    "declared_id",
    "energy",
    "family",
    "fields",
    "host",
    "id",
    "interface",
    "kernels",
    "laws",
    "ledgers",
    "models",
    "module",
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
LEGACY_KEYS = ("id", "legacy", "piece")
TEMPLATE_FIELDS = frozenset(f.name for f in dataclasses.fields(law_registry.Law))


def _json(value):
    """A declared value as JSON data: functions as module.qualname, tuples as lists."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, law_registry.Citation):
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


def _identity(declared_id, piece, interface, host):
    key = qualified(declared_id)
    namespace, rest = key.split(".", 1)
    name, version = rest.rsplit("@", 1)
    family = INNER if host in kind_registry.active() else host
    return dict(
        id=key,
        declared_id=declared_id,
        namespace=namespace,
        name=name,
        version=int(version),
        piece=piece,
        interface=interface,
        host=host,
        family=family,
        models=_models(family),
    )


def _models(family):
    """The models whose definitions can declare a piece of `family`: the model itself, and each
    composite whose inner model it is."""
    out = [family]
    if family == INNER and inner_spec.MODEL_ID in composite_spec.INNER_MODEL_IDS:
        out.append(COMPOSITE)
    return sorted(out)


def _entry(**values):
    out = dict.fromkeys(PIECE_KEYS)
    out.update(values)
    return out


def law_entry(law, registry):
    """A law's entry: its template fields, then its interface's own (registry/laws.py)."""
    own = [f.name for f in dataclasses.fields(law) if f.name not in TEMPLATE_FIELDS]
    values = {name: getattr(law, name) for name in own}
    kernels = {name: _json(v) for name, v in values.items() if callable(v)}
    changes = []
    if isinstance(law, law_registry.ChannelLaw):
        changes = [dict(species=s, valence=z, relative_permeability=w) for s, z, w in law.permeant]
    elif isinstance(law, law_registry.CycleLaw):
        changes = [dict(role=role, per_cycle=count) for role, count in law.moves]
    source = law.source
    return _entry(
        **_identity(law.law_id, "law", type(law).interface, qualified(law.host)),
        module=registry.module(law.law_id),
        kernels=kernels,
        provenance=dict(
            tag=law.provenance,
            citation=_json(source) if isinstance(source, law_registry.Citation) else None,
            source=None
            if source is None or isinstance(source, law_registry.Citation)
            else _json(source),
        ),
        reads=_json(getattr(law, "reads", ())),
        changes=_json(changes),
        units=_json(type(law).UNITS),
        signs=_json(type(law).SIGNS),
        fields={n: _json(v) for n, v in values.items() if not callable(v) and n != "reads"},
        test=law.test,
    )


def kind_entry(kind, laws):
    """A kind's entry: its fields by role, its hooks, its view's units and signs, and the laws it
    hosts."""
    hooks = [
        f.name
        for f in dataclasses.fields(kind)
        if f.name != "view" and callable(getattr(kind, f.name))
    ]
    module = next((getattr(kind, h).__module__ for h in hooks), None)
    view = kind.view or kind_registry.KindView()
    return _entry(
        **_identity(kind.kind_id, "kind", KIND_INTERFACE, INNER),
        module=module,
        owns=_json(dict(kind.state_axes)),
        provides=_json([*kind.readout_columns]),
        controls=_json([*kind.control_fields]),
        units=_json(view.units),
        signs=_json(view.orientation),
        laws=sorted(
            qualified(law.law_id)
            for law in laws._laws.values()
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


def operator_entry(operator):
    """An operator's entry: its contract declarations (models/operators/contract.py) by role."""
    cls = type(operator)
    parts = (("event", "EVENT"), ("split", "SPLIT"), ("process", "PROCESS"))
    return _entry(
        **_identity(cls.LAW_ID, "operator", OPERATOR_INTERFACE, COMPOSITE),
        module=cls.__module__,
        reads=_json([*cls.VIEW_READS, *cls.CONFLICTS_VIEW]),
        owns=_json(cls.STATE_AXES),
        writes=_json(cls.ENTITY_WRITES),
        provides=_json([*cls.VIEW_FIELDS, *cls.READOUT_COLUMNS]),
        controls=_json([*cls.CONTROL_FIELDS, *cls.CONTROL_FACTORS]),
        ledgers=_json(cls.LEDGERS),
        energy=dict(heat=_json(cls.HEAT_FIELDS), work=_json(cls.WORK_FIELDS)),
        units=_json(cls.UNITS),
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


def legacy_entries(path=None):
    """The older model families by model ID (D196), read from the legacy registration's `parse`
    dispatch (core/legacy_entry.LEGACY; `path` for another file) without importing it: each
    comparison of the definition's model ID with a literal, a tuple of literals or a name imported
    from an active module. Anything else refuses, so no family is dropped silently."""
    if path is None:
        path = Path(cells.__file__).parent.joinpath(*LEGACY.split(".")[1:]).with_suffix(".py")
    path = Path(path)
    tree = ast.parse(path.read_text())
    legacy_package = LEGACY.rsplit(".", 1)[0]
    names = {  # Names imported from active modules only: nothing here imports the legacy package.
        alias.asname or alias.name: node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.level == 0
        and node.module != legacy_package
        and not (node.module or "").startswith(legacy_package + ".")
        for alias in node.names
    }
    (dispatch,) = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "parse"]
    found = set()
    for node in ast.walk(dispatch):
        if not isinstance(node, ast.Compare) or ast.unparse(node.left) != "data['model'].get('id')":
            continue
        for comparator in node.comparators:
            items = comparator.elts if isinstance(comparator, ast.Tuple) else [comparator]
            for item in items:
                if isinstance(item, ast.Constant) and isinstance(item.value, str):
                    found.add(item.value)
                elif isinstance(item, ast.Name) and item.id in names:
                    module = __import__(names[item.id], fromlist=[item.id])
                    found.add(getattr(module, item.id))
                else:
                    raise ValueError(f"An unread model-ID form in {path.name}: {ast.unparse(item)}")
    if not found:
        raise ValueError(f"No older family found in {path.name}'s parse dispatch")
    return [dict(id=model_id, legacy=True, piece="model") for model_id in sorted(found)]


def manifest():
    """The manifest of the active registries, as JSON data (module docstring)."""
    from cells.ensemble.cli import source_revision

    laws = law_registry.active()
    kinds = kind_registry.active()
    pieces = [law_entry(law, laws) for law in laws._laws.values()]
    pieces += [kind_entry(kind, laws) for kind in kinds.model_keys().values()]
    pieces += [operator_entry(op) for op in operator_registry.active().operators()]
    pieces.sort(key=lambda entry: (entry["piece"], entry["id"]))
    revision = source_revision() or {}
    return dict(
        kind=FORMAT,
        revision=revision.get("revision"),
        dirty=revision.get("dirty"),
        origin=revision.get("origin"),
        pieces=pieces,
        legacy=legacy_entries(),
    )


def dumps(doc):
    """The manifest's bytes: sorted keys, one space of indent, a final newline."""
    return json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def format_errors(doc):
    """Why `doc` is not a `cells.declarations@1` manifest (empty: it is one)."""
    if not isinstance(doc, dict) or doc.get("kind") != FORMAT:
        return [f"its kind is {FORMAT}"]
    out = []
    if set(doc) != {"kind", "revision", "dirty", "origin", "pieces", "legacy"}:
        out.append("its top-level keys are kind, revision, dirty, origin, pieces and legacy")
    pieces = doc.get("pieces")
    if not isinstance(pieces, list):
        return [*out, "its pieces are a list"]
    seen = set()
    for entry in pieces:
        if not isinstance(entry, dict) or set(entry) != set(PIECE_KEYS):
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
    for entry in doc.get("legacy") or ():
        if (
            not isinstance(entry, dict)
            or set(entry) != set(LEGACY_KEYS)
            or entry["legacy"] is not True
        ):
            out.append(f"a legacy entry is its model ID, flagged legacy: {entry!r:.120}")
    return out


def coverage_errors(doc):
    """Where `doc` and the active registries disagree: a registered piece with no entry, or an
    entry whose ID is not in its registry."""
    laws = law_registry.active()
    registered = {("law", key) for key in laws._laws}
    registered |= {
        ("kind", qualified(k.kind_id)) for k in kind_registry.active().model_keys().values()
    }
    registered |= {
        ("operator", qualified(op.LAW_ID)) for op in operator_registry.active().operators()
    }
    listed = {(e["piece"], e["id"]) for e in doc["pieces"]}
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
                legacy=len(doc["legacy"]),
                revision=doc["revision"],
                dirty=doc["dirty"],
            )
        )
    )
    return 0
