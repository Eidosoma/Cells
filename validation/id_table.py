"""Old IDs to new, for the files that are never rewritten (D345; D371, Q7).

A tagged spec, reference, judge or protocol, and a saved definition, keep the IDs they were written
with. A live driver that feeds one to the engine, or compares its IDs with the engine's, translates
it first, so the engine stays strict and the file stays as it was:

    predictions = id_table.load(PREDICTIONS)
    spec = parse_spec(id_table.translate(frozen_builder()))
    found = id_table.function(frozen_judge.reading)(spec, result)

**The table** is the committed one, cells.registry.renamed_ids.RENAMED: {old spelling: new ID}. With
an empty table every call returns its argument itself.

**The rule** is the move's own, so a translated file reads as if the move had rewritten it. In every
string of JSON-like data (dicts, lists, tuples and strings), keys included, each whole token that is
an old spelling becomes its new ID. It may stand alone or among other words, as in a registered text
that a driver looks up by. Everything else passes through: a new ID, an ID that keeps its name, a
format's name, a plain word, and a token after '/', '-', '.' or a backslash, which is part of a
path, a test's ID or a pattern. The input is never changed.

**Refused as ambiguous** (Ambiguous, a ValueError): a mapping in which two keys become one, and a
table that gives one spelling two new IDs, or whose new ID is an old spelling of another.
"""

import ast
import json
import re
from pathlib import Path
from types import CodeType, FunctionType

__all__ = ("Ambiguous", "check", "function", "load", "read_table", "translate")

TOKEN = re.compile(
    r"(?<![A-Za-z0-9_./@\-\\])((?:[a-z][A-Za-z0-9_]*\.)*[a-z][A-Za-z0-9_]*@[0-9]+)(?![A-Za-z0-9_])"
)


class Ambiguous(ValueError):
    """A spelling or a key that the table cannot place in one way."""


def renamed():
    """The committed table."""
    from cells.registry.renamed_ids import RENAMED

    return RENAMED


def check(table):
    """`table`, refused where a new ID is also an old spelling: a second translation would move it
    again."""
    chained = sorted(new for new in set(table.values()) if new in table)
    if chained:
        raise Ambiguous(f"the table maps to old spellings: {', '.join(chained)}")
    return table


def read_table(path):
    """A table file: a generated module (its RENAMED literal) or a JSON object {old: new}. A
    spelling given twice is refused, whichever it is given."""
    path = Path(path)
    if path.suffix == ".py":
        (node,) = (
            n.value
            for n in ast.parse(path.read_text()).body
            if isinstance(n, ast.Assign) and [ast.unparse(t) for t in n.targets] == ["RENAMED"]
        )
        keys = [ast.literal_eval(k) for k in node.keys]
        pairs = list(zip(keys, (ast.literal_eval(v) for v in node.values), strict=True))
    else:
        pairs = json.loads(path.read_text(), object_pairs_hook=list)
    repeated = sorted({old for old, _ in pairs if [o for o, _ in pairs].count(old) > 1})
    if repeated:
        raise Ambiguous(f"{path}: given twice: {', '.join(repeated)}")
    return check(dict(pairs))


def translate(value, table=None):
    """`value` with every old spelling replaced (the module's rule), by `table` or the committed
    one."""
    table = renamed() if table is None else table
    if not table:
        return value
    return _translate(value, table)


def _translate(value, table):
    if isinstance(value, str):
        if "@" not in value:
            return value
        return TOKEN.sub(lambda m: table.get(m[1], m[1]), value)
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            new = _translate(key, table)
            if new in out:
                raise Ambiguous(f"two keys of one mapping become {new!r}, one of them {key!r}")
            out[new] = _translate(item, table)
        return out
    if type(value) in (list, tuple, frozenset):
        return type(value)(_translate(item, table) for item in value)
    return value


def load(path, table=None):
    """A JSON file, translated."""
    return translate(json.loads(Path(path).read_text()), table)


def function(frozen, table=None):
    """A frozen module's function with its own literals translated. Its module's names, and what
    it calls, stay as they are."""
    table = renamed() if table is None else table
    if not table:
        return frozen
    out = FunctionType(
        _code(frozen.__code__, table),
        frozen.__globals__,
        frozen.__name__,
        _translate(frozen.__defaults__, table),
        frozen.__closure__,
    )
    out.__kwdefaults__ = _translate(frozen.__kwdefaults__, table)
    return out


def _code(code, table):
    constants = [
        _code(c, table) if isinstance(c, CodeType) else _translate(c, table)
        for c in code.co_consts
    ]
    return code.replace(co_consts=tuple(constants))
