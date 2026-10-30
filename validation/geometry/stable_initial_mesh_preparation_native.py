"""Conditional replay of unchanged native mesh flow using an explicit tape.

This is not a native arithmetic oracle. Only the three named primitive bodies
are replaced; their typed arguments must match the saved actual calls before
a recorded value or refusal can be returned. Every other native body and all
ordering, topology, cache, RNG and deletion behavior remain source literal.
"""

import ast
import copy
import struct

import numpy as np

from validation.betse import betse_initial_mesh_preparation_native as native
from validation.betse import betse_initial_mesh_preparation_wire as wire

REPAIRED = ("area", "poly_centroid", "circumc")
_active = None


class GeometryRejected(ValueError):
    """Transport the recorded refusal type without importing production."""


def member(tree, name):
    assert tree["type"] == "dict"
    matches = [value for key, value in tree["values"] if key == dict(type="str", value=name)]
    assert len(matches) == 1, name
    return matches[0]


def restore_scalar_tree(tree):
    kind = tree["type"]
    if kind == "numpy_scalar":
        return np.frombuffer(bytes.fromhex(tree["bits"]), dtype=np.dtype(tree["dtype"]))[0]
    if kind == "float":
        return struct.unpack("<d", bytes.fromhex(tree["bits"]))[0]
    if kind in ("tuple", "list"):
        values = [restore_scalar_tree(v) for v in tree["values"]]
        return tuple(values) if kind == "tuple" else values
    if kind == "dict":
        return {restore_scalar_tree(k): restore_scalar_tree(v) for k, v in tree["values"]}
    if kind in ("NoneType", "str", "int", "bool"):
        return tree["value"]
    raise ValueError("Tape output is outside the scalar primitive interface")


def tape_from_events(events):
    entries, pending = [], None
    for event in events:
        if event["kind"] == "primitive_repair_input":
            assert pending is None
            pending = dict(
                method=event["method"],
                call_parameters=member(event["payload"]["tree"], "call_parameters"),
                input_sequence=event["sequence"],
            )
        elif event["kind"] in ("primitive_repair_result", "primitive_repair_failure"):
            assert pending is not None and pending["method"] == event["method"]
            tree = event["payload"]["tree"]
            pending["outcome"] = "result" if event["kind"].endswith("result") else "failure"
            pending["outcome_sequence"] = event["sequence"]
            if pending["outcome"] == "result":
                pending["output"] = member(tree, "adapter_output")
            else:
                pending["failure_type"] = restore_scalar_tree(member(tree, "failure_type"))
                pending["reason"] = restore_scalar_tree(member(tree, "reason"))
            entries.append(pending)
            pending = None
    assert pending is None
    return entries


def consume(method, parameters):
    if _active is None or _active["cursor"] >= len(_active["entries"]):
        raise ValueError("Conditional primitive tape exhausted")
    entry = _active["entries"][_active["cursor"]]
    assert entry["method"] == method
    actual = wire.capture(parameters)
    assert wire.signature(actual["tree"]) == wire.signature(entry["call_parameters"]), method
    _active["cursor"] += 1
    _active["consumed"].append(
        dict(method=method, input_sequence=entry["input_sequence"], outcome=entry["outcome"])
    )
    if entry["outcome"] == "failure":
        classes = {"GeometryRejected": GeometryRejected, "ValueError": ValueError}
        if entry["failure_type"] not in classes:
            raise ValueError("Unexpected recorded primitive failure type: " + entry["failure_type"])
        raise classes[entry["failure_type"]](entry["reason"])
    return restore_scalar_tree(entry["output"])


def evaluate(kwargs, point_ids, before, tape):
    global _active
    assert _active is None
    original_capture = native.capture

    def conditional_capture():
        module, sites, helpers, pins = original_capture()
        module = copy.deepcopy(module)
        cls = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == "NativeMesh")
        changed = []
        for method in cls.body:
            if isinstance(method, ast.FunctionDef) and method.name in REPAIRED:
                arguments = "dict(A=A, B=B, C=C)" if method.name == "circumc" else "dict(p=p)"
                method.body = ast.parse(
                    "from validation.geometry.stable_initial_mesh_preparation_native "
                    "import consume\n" + f"return consume({method.name!r}, {arguments})\n"
                ).body
                changed.append(method.name)
        assert set(changed) == set(REPAIRED)
        ast.fix_missing_locations(module)
        return module, sites, helpers, pins

    _active = dict(entries=tape, cursor=0, consumed=[])
    native.capture = conditional_capture
    try:
        proof = native.evaluate(kwargs, point_ids, before)
        proof.update(
            conditional_source_equivalence=True,
            exact_native_arithmetic_equivalence=False,
            replay_condition=(
                "Exact supplied primitive argument signatures and recorded repaired values/refusals"
            ),
            replaced_primitive_bodies=list(REPAIRED),
            unchanged_source_methods=[
                name for name in proof["source_sites"] if name not in REPAIRED
            ],
            tape_entries=len(tape),
            tape_consumed=_active["cursor"],
            tape_calls=_active["consumed"],
        )
        assert _active["cursor"] == len(tape), "Unconsumed conditional primitive tape"
        return proof
    finally:
        native.capture = original_capture
        _active = None
