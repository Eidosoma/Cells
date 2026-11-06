"""Bounded original-parameter AST metadata measurements, never source execution.

The candidate shape is only a measurement prototype until its producer is
integrated and independently guarded. No parameter or owner is constructed.
"""

import argparse
import ast
import hashlib
import json
import operator
import os
import runpy
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PARAMETERS = "src/cells/processes/betse_native_phase_parameters.py"
REUSED_TEST = "tests/unit/test_betse_native_source_compilation_cache.py"
ORIGINAL = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse/science/parameters.py")
ORIGINAL_SHA256 = "f36ec747918aa285ca043fe51086bcff4e4e2198cd4f30a138f1e58a51ecf85e"


def _prototype_shape(value):
    """Closed, iterative common-AST value; unsupported values require old dump."""
    pending, result = [value], []
    while pending:
        value = pending.pop()
        cls = type(value)
        if isinstance(value, ast.AST) and cls.__module__ == "ast":
            namespace = vars(value)
            names, children = [], []
            for name in (*value._fields, *value._attributes):
                if name not in namespace:
                    continue
                current = namespace[name]
                if current is None and getattr(cls, name, ...) is None:
                    continue
                if name in value._fields and type(current) is list and not current:
                    if getattr(cls._field_types.get(name), "__origin__", ...) is list:
                        continue
                names.append(name)
                children.append(current)
            result.append(("node", cls.__name__, tuple(names)))
            pending.extend(reversed(children))
        elif cls is list:
            result.append(("list", len(value)))
            pending.extend(reversed(value))
        elif cls in (str, bytes, int, bool, type(None)):
            result.append((cls.__name__, value))
        elif cls in (float, complex):
            result.append((cls.__name__, repr(value)))
        else:
            return None
        if len(result) > 100000:
            raise ValueError("Bounded AST metadata shape exhausted")
    return tuple(result)


def _compilation_class_plan(node):
    """Immutable metadata selectors/values only; retain no mutable AST node."""
    rows, pending, classes, guards = [None], [(node, 0)], set(), []
    primitive = (str, bytes, int, bool, type(None), float, complex, type(Ellipsis))
    while pending:
        value, index = pending.pop()
        cls = type(value)
        if isinstance(value, ast.AST):
            if cls not in classes:
                classes.add(cls)
                for base in cls.__mro__:
                    if base in classes and base is not cls:
                        continue
                    classes.add(base)
                    items = tuple(vars(base).items())
                    field_types = vars(base).get("_field_types")
                    guards.append(
                        (
                            base,
                            base.__mro__,
                            items,
                            None
                            if type(field_types) is not dict
                            else (field_types, tuple(field_types.items())),
                        )
                    )
            fields, attributes = value._fields, value._attributes
            names = (*fields, *attributes)
            getter = operator.attrgetter(*names) if names else None
            try:
                values = () if getter is None else getter(value)
            except AttributeError:
                return None
            if len(names) == 1:
                values = (values,)
            header = ("node", cls, cls.__name__, fields, attributes, getter, len(names))
        elif cls is list:
            values = value
            header = ("list", len(value))
        else:
            return None
        scalar_positions, scalar_values, floating, float_values, children = [], [], [], [], []
        for position, current in enumerate(values):
            current_type = type(current)
            if isinstance(current, ast.AST) or current_type is list:
                child = len(rows)
                rows.append(None)
                children.append((position, child))
                pending.append((current, child))
            elif current_type in primitive:
                if current_type in (float, complex):
                    floating.append(position)
                    float_values.append(repr(current))
                else:
                    scalar_positions.append(position)
                    scalar_values.append(current)
            else:
                return None
        rows[index] = (
            header,
            tuple(map(id, map(type, values))),
            None if not scalar_positions else operator.itemgetter(*scalar_positions),
            tuple(scalar_values),
            None if not floating else operator.itemgetter(*floating),
            tuple(float_values),
            tuple(children),
        )
        if len(rows) > 100000:
            raise ValueError("Bounded class metadata plan exhausted")
    return tuple(rows), tuple(guards)


def _compilation_class_matches(node, plan):
    """Fast positive proof; every mismatch/unsupported case uses original dump."""
    if plan is None:
        return False
    rows, guards = plan
    for cls, mro, items, field_types in guards:
        if cls.__mro__ is not mro:
            return False
        current = tuple(vars(cls).items())
        if len(current) != len(items) or any(
            name is not old_name or value is not old_value
            for (name, value), (old_name, old_value) in zip(current, items, strict=True)
        ):
            return False
        if field_types is not None:
            mapping, entries = field_types
            current = tuple(dict.items(mapping))
            if len(current) != len(entries) or any(
                name is not old_name or value is not old_value
                for (name, value), (old_name, old_value) in zip(current, entries, strict=True)
            ):
                return False
    pending = [(node, 0)]
    while pending:
        value, index = pending.pop()
        header, types, selector, expected, float_selector, floats, children = rows[index]
        if header[0] == "node":
            _, cls, name, fields, attributes, getter, count = header
            if (
                type(value) is not cls
                or value.__class__ is not cls
                or cls.__name__ != name
                or value._fields is not fields
                or value._attributes is not attributes
            ):
                return False
            try:
                values = () if getter is None else getter(value)
            except AttributeError:
                return False
            if count == 1:
                values = (values,)
        else:
            if type(value) is not list or len(value) != header[1]:
                return False
            values = value
        if tuple(map(id, map(type, values))) != types:
            return False
        if selector is not None:
            actual = selector(values)
            if len(expected) == 1:
                actual = (actual,)
            if actual != expected:
                return False
        if float_selector is not None:
            actual = float_selector(values)
            if len(floats) == 1:
                actual = (actual,)
            if tuple(map(repr, actual)) != floats:
                return False
        pending.extend((values[position], child) for position, child in children)
    return True


def _write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def measure(directory):
    """Exercise actual extracted metadata functions; compiled bodies forbidden."""
    directory.mkdir()
    raw = ORIGINAL.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ORIGINAL_SHA256:
        raise ValueError("Exact pinned original Parameters source required")
    node = next(
        n for n in ast.parse(raw).body if type(n) is ast.ClassDef and n.name == "Parameters"
    )
    reuse = runpy.run_path(str(ROOT / REUSED_TEST))
    parameters, producer = reuse["_load"](
        ROOT / PARAMETERS, reuse["PARAMETER_FUNCTIONS"], "_COMPILATION_"
    )
    calls, attempted, samples = {}, [], []
    prior, trace = sys.getprofile(), sys.gettrace()

    def guard(frame, event, arg):
        if prior is not None:
            prior(frame, event, arg)
        if event == "call":
            name = frame.f_globals.get("__name__", "")
            if name.startswith(
                ("cells.", "betse.", "numpy.", "scipy.")
            ) or frame.f_code.co_filename == str(ORIGINAL):
                attempted.append((name, frame.f_code.co_qualname))
                raise AssertionError("Native/owner/compiled source execution held")
            if frame.f_code is ast.dump.__code__:
                calls["ast.dump"] = calls.get("ast.dump", 0) + 1

    try:
        sys.setprofile(guard)
        start = time.perf_counter_ns()
        code = parameters._method_code(
            node, "_load_ion_profile", str(ORIGINAL), native_context=True
        )
        cold_ns = time.perf_counter_ns() - start
        expected = _prototype_shape(node)
        assert expected is not None
        candidate = _compilation_class_plan(node)
        assert candidate is not None
        for name, function in (
            (
                "native_method_check",
                lambda: parameters._method_code(
                    node, "_load_ion_profile", str(ORIGINAL), native_context=True
                ),
            ),
            ("complete_class_dump", lambda: ast.dump(node, include_attributes=True)),
            ("candidate_closed_shape", lambda: _prototype_shape(node)),
            ("candidate_selector_match", lambda: _compilation_class_matches(node, candidate)),
        ):
            for index in range(7):
                wall, cpu = time.perf_counter_ns(), time.process_time_ns()
                value = function()
                elapsed = time.perf_counter_ns() - wall
                cpu = time.process_time_ns() - cpu
                if name == "native_method_check":
                    assert value is code
                elif name == "candidate_closed_shape":
                    assert value == expected
                elif name == "candidate_selector_match":
                    assert value is True
                samples.append(dict(operation=name, repeat=index, wall_ns=elapsed, cpu_ns=cpu))
        assert not attempted
    finally:
        sys.settrace(trace)
        sys.setprofile(prior)
    _write(
        directory / "measurement.json",
        dict(
            phase_parameters_sha256=producer,
            original_source_sha256=ORIGINAL_SHA256,
            original_source_bytes=len(raw),
            candidate_shape_items=len(expected),
            cold_method_ns=cold_ns,
            samples=samples,
            ast_dump_calls=calls,
            forbidden_entries=attempted,
            hooks_restored=sys.getprofile() is prior and sys.gettrace() is trace,
            compiled_native_source_entries=0,
            numerical_or_owner_work=0,
            scope=(
                "Repeated source-metadata-only measurement under a minimal rejecting profiler; "
                "not total runtime attribution or actual parent validation."
            ),
            candidate_not_yet_production=True,
            scientific_credit=0,
        ),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measure", type=Path, required=True)
    args = parser.parse_args()
    measure(args.measure)


if __name__ == "__main__":
    main()
