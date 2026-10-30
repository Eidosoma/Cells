"""Typed immutable-cache transport; usable with production imports denied."""

import hashlib
import json
import os
from pathlib import Path

import numpy as np

from validation.betse import betse_initial_mesh_preparation_wire as wire

MAX_RECORD_BYTES = 128 * 2**20


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read(path):
    path = Path(path)
    if path.stat().st_size > MAX_RECORD_BYTES:
        raise ValueError("Mesh worker record exceeds the declared byte bound")
    with path.open() as handle:
        return json.load(handle)


def write(path, value, columns=None):
    path = Path(path)
    if columns is not None:
        with path.with_suffix(".npz").open("xb") as handle:
            np.savez_compressed(handle, **columns)
            handle.flush()
            os.fsync(handle.fileno())
    with path.with_suffix(".json").open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def owned_tree(node):
    kind = node["kind"]
    if kind == "numeric_array":
        return dict(
            type="array", layout=node["source_layout"], column=node["column"], sha256=node["sha256"]
        )
    if kind == "object_array":
        return dict(
            type=kind, layout=node["source_layout"], values=[owned_tree(v) for v in node["items"]]
        )
    if kind == "dict":
        return dict(type=kind, values=[[owned_tree(k), owned_tree(v)] for k, v in node["items"]])
    if "items" in node:
        return dict(type=kind, values=[owned_tree(v) for v in node["items"]])
    return dict(type=kind, **{k: v for k, v in node.items() if k != "kind"})


def load_cache(record, archive, *, owned=True):
    prefix = record["column_prefix"] + "__"
    columns = {
        name[len(prefix) :]: archive[name] for name in archive.files if name.startswith(prefix)
    }
    if owned:
        descriptor = json.dumps(record["descriptor"], sort_keys=True, separators=(",", ":"))
        assert hashlib.sha256(descriptor.encode()).hexdigest() == record["identity"]
        tree = owned_tree(record["descriptor"])
    else:
        tree = record["tree"]
    return wire.validate(dict(tree=tree, columns=columns))


def load_events(actual, archive):
    return [
        {
            **{k: v for k, v in event.items() if k != "payload"},
            "payload": load_cache(event["payload"], archive),
        }
        for event in actual["events"]
    ]


def plain_events(events):
    return [
        {**event, "payload": wire.plain(event["payload"]["tree"], event["payload"]["columns"])}
        for event in events
    ]


def equal(left, right, *, failure=False):
    wire.validate(left)
    wire.validate(right)

    def signature(tree):
        value = wire.signature(tree)
        if failure:
            assert value["type"] == "dict"
            value = {
                **value,
                "values": [
                    [k, v] for k, v in value["values"] if k != dict(type="str", value="reason")
                ],
            }
        return value

    assert signature(left["tree"]) == signature(right["tree"])


def constructor_equal(left, right):
    """Only the outer kwargs map is unordered; every typed value stays exact."""
    wire.validate(left)
    wire.validate(right)
    maps = []
    for cache in (left, right):
        assert cache["tree"]["type"] == "dict"
        entries = cache["tree"]["values"]
        assert all(k["type"] == "str" for k, _ in entries)
        mapping = {k["value"]: wire.signature(v) for k, v in entries}
        assert len(mapping) == len(entries)
        maps.append(mapping)
    assert maps[0] == maps[1]


def retain_native(path, proof):
    columns = {}

    def record(prefix, cache):
        columns.update({prefix + "__" + key: value for key, value in cache["columns"].items()})
        return dict(tree=cache["tree"], column_prefix=prefix)

    value = {k: v for k, v in proof.items() if k not in ("cache", "constructed_cache", "events")}
    value.update(
        constructed_cache=record("constructed", proof["constructed_cache"]),
        cache=record("final", proof["cache"]),
        events=[
            {
                **{k: v for k, v in event.items() if k != "payload"},
                "payload": record(f"event{event['sequence']}", event["payload"]),
            }
            for event in proof["events"]
        ],
    )
    write(path, value, columns)


def compare_native(actual, archive, proof):
    state = actual["state"]
    assert actual["global_rng_before"] == actual["global_rng_after"]
    failed = state["status"] == "retained_stable_mesh_failure"
    assert proof["status"] == ("source_failed" if failed else "source_completed")
    if failed:
        assert proof["failure"]["type"] == state["failure_type"]
        assert proof["stage"] == state["failure_stage"]
    else:
        assert state["status"] == "stable_mesh_completed_unqualified" and proof["failure"] is None
    equal(load_cache(actual["constructed"], archive), proof["constructed_cache"])
    equal(load_cache(actual["final"], archive), proof["cache"])
    events = [
        event
        for event in load_events(actual, archive)
        if not event["kind"].startswith("primitive_repair_")
    ]
    assert len(events) == len(proof["events"])
    for sequence, (event, expected) in enumerate(zip(events, proof["events"], strict=True)):
        assert expected["sequence"] == sequence
        for key in ("kind", "method", "depth"):
            assert event[key] == expected[key]
        equal(
            event["payload"],
            expected["payload"],
            failure=failed and event["kind"].endswith("failure"),
        )
    for actual_key, native_key in (
        ("stream_before", "rng_before"),
        ("stream_after_constructor", "rng_after_constructor"),
        ("stream_after", "rng_after"),
    ):
        assert state[actual_key]["state"] == proof[native_key]
    assert state["retained_point_ids"] == list(proof["retained_point_ids"])
    for key in ("constructor_completed", "pre_mesh_completed"):
        assert state[key] == proof[key]
    assert state["warnings"] == proof["warnings"]
    assert proof["original_global_rng_unchanged"]
    assert (
        proof["conditional_source_equivalence"] and not proof["exact_native_arithmetic_equivalence"]
    )
    assert len(proof["unchanged_source_methods"]) == 14
    assert (
        not proof["topology_qualified"]
        and not proof["operators_created"]
        and not proof["image_clip_executed"]
    )
    return dict(
        conditional_source_equivalence=True,
        exact_native_arithmetic_equivalence=False,
        original_trace_events_compared=len(events),
        full_typed_caches_and_rng_exact_given_tape=True,
        tape_entries=proof["tape_entries"],
    )
