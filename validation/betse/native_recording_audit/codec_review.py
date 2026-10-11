"""Compare independently decoded records directly with every original JSON value.

No producer partitioner, decoder, canonical digest or compatibility reconstruction
is used. The old row is loaded once; decoded chunks are consumed incrementally.
"""

import hashlib
import math
import struct

import wire_decode as wire

INITIAL = {
    "dt_s",
    "fixture",
    "geometry",
    "id",
    "metadata",
    "mode",
    "moving_ions",
    "phase",
    "potassium_index",
    "settings",
    "sodium_index",
    "source_constants",
    "steps",
}
TERMINAL = {"final", "final_arrays", "fixture_hook", "hook_restored", "native_pickle"}
TRACE_END = {
    "calls",
    "gate_initializations",
    "hook_restored",
    "inflight_calls",
    "pending",
    "status",
}
TRACE_SERIES = {"labels_s", "raw_steps", "sampled_indices", "steps", "storage"}
HISTORY_NAMES = {
    "I_mem_time",
    "cc_env_time",
    "cc_time",
    "dd_time",
    "gjopen_time",
    "rate_NaKATP_time",
    "rho_cells_time",
    "time",
    "vm_time",
}


class Exact:
    def __init__(self):
        self.scalars = self.floats = self.negative_zeros = self.keys = self.containers = 0

    def match(self, actual, expected, where):
        kind = type(expected)
        wire.need(type(actual) is kind, "Changed type: " + where)
        if kind is dict:
            wire.need(actual.keys() == expected.keys(), "Changed keys: " + where)
            wire.need(all(type(k) is str for k in actual), "Nonstring key: " + where)
            self.keys += len(actual)
            self.containers += 1
            for key in sorted(expected):
                self.match(actual[key], expected[key], where + "/" + key)
        elif kind is list:
            wire.need(len(actual) == len(expected), "Changed length: " + where)
            self.containers += 1
            if expected and all(type(v) is float for v in expected):
                wire.need(
                    all(type(v) is float and math.isfinite(v) for v in actual)
                    and all(math.isfinite(v) for v in expected),
                    "Changed float vector: " + where,
                )
                wire.need(
                    struct.pack(f"<{len(actual)}d", *actual)
                    == struct.pack(f"<{len(expected)}d", *expected),
                    "Changed float64 bits: " + where,
                )
                self.scalars += len(actual)
                self.floats += len(actual)
                self.negative_zeros += sum(v == 0.0 and math.copysign(1.0, v) < 0 for v in actual)
            else:
                for i, (left, right) in enumerate(zip(actual, expected, strict=True)):
                    self.match(left, right, where + "/" + str(i))
        else:
            wire.need(kind in (str, int, float, bool, type(None)), "Unsupported JSON value")
            if kind is float:
                wire.need(
                    math.isfinite(actual)
                    and math.isfinite(expected)
                    and struct.pack("<d", actual) == struct.pack("<d", expected),
                    "Changed float64 bits: " + where,
                )
                self.floats += 1
                self.negative_zeros += actual == 0.0 and math.copysign(1.0, actual) < 0
            else:
                wire.need(actual == expected, "Changed value: " + where)
            self.scalars += 1


def leaf_count(value, *, sequence_types=(list,)):
    """Independent whole-input coverage count, not derived from the stream layout."""
    if type(value) is dict:
        return sum(leaf_count(v, sequence_types=sequence_types) for v in value.values())
    if type(value) in sequence_types:
        if not any(type(v) in (dict, *sequence_types) for v in value):
            return len(value)
        return sum(leaf_count(v, sequence_types=sequence_types) for v in value)
    return 1


def array_bytes(values, shape, digest):
    if not shape:
        wire.need(type(values) is float and math.isfinite(values), "Array float64 scalar")
        digest.update(struct.pack("<d", values))
    else:
        wire.need(type(values) is list and len(values) == shape[0], "Array shape mismatch")
        if len(shape) == 1:
            wire.need(
                all(type(v) is float and math.isfinite(v) for v in values), "Array float64 vector"
            )
            digest.update(struct.pack(f"<{len(values)}d", *values))
        else:
            for child in values:
                array_bytes(child, shape[1:], digest)


def array_shape(spec, include_values=True):
    wire.fields(
        spec,
        {"dtype", "shape", "bytes_sha256"} | ({"values"} if include_values else set()),
        "Float64 array",
    )
    wire.need(
        spec["dtype"] == "<f8" and type(spec["shape"]) is list and 0 < len(spec["shape"]) <= 8,
        "Array dtype/dimensions",
    )
    for size in spec["shape"]:
        wire.uint(size, 1000000, "Array dimension")
    wire.digest_string(spec["bytes_sha256"])


def compare_row(original, records, *, trace_sequence_types=(list,)):
    wire.fields(original, INITIAL | TERMINAL | {"histories", "trace"}, "Original root coverage")
    n = original["steps"]
    wire.need(
        type(n) is int and n > 1 and original["mode"] in ("observed", "unobserved"),
        "Original row extent/mode",
    )
    observed = original["mode"] == "observed"
    old_trace, histories = original["trace"], original["histories"]
    wire.fields(histories, HISTORY_NAMES, "Original histories")
    if observed:
        wire.fields(old_trace, TRACE_END | TRACE_SERIES | {"initial"}, "Original trace coverage")
        for key in TRACE_SERIES:
            expected = n - 1 if key in ("sampled_indices", "storage") else n
            wire.need(
                type(old_trace[key]) in trace_sequence_types and len(old_trace[key]) == expected,
                "Original trace extent: " + key,
            )
    else:
        wire.need(old_trace is None, "Original quiet trace")
    for name, history in histories.items():
        array_shape(history)
        wire.need(
            history["shape"][0] == n - 1
            and type(history["values"]) is list
            and len(history["values"]) == n - 1,
            "Original history extent: " + name,
        )

    iterator, exact = iter(records), Exact()
    read_count = 0

    def take(kind, expected_fields):
        nonlocal read_count
        item = next(iterator, None)
        wire.fields(item, expected_fields, "Record " + kind)
        wire.need(item["kind"] == kind, "Wrong native record sequence")
        read_count += 1
        return item

    header = take("native_header", {"kind", "schema", "row", "trace", "histories"})
    wire.need(header["schema"] == "cells.native_pump_row@1", "Native record schema")
    wire.fields(header["row"], INITIAL, "Initial root coverage")
    for key in INITIAL:
        exact.match(header["row"][key], original[key], key)
    if observed:
        wire.fields(header["trace"], {"initial"}, "Initial trace coverage")
        exact.match(header["trace"]["initial"], old_trace["initial"], "trace/initial")
    else:
        exact.match(header["trace"], None, "trace")
    wire.fields(header["histories"], HISTORY_NAMES, "History header coverage")
    for name, spec in header["histories"].items():
        wire.fields(spec, {"dtype", "shape"}, "History specification")
        for key in spec:
            exact.match(spec[key], histories[name][key], "histories/" + name + "/" + key)
    del header

    hashes = {k: hashlib.sha256() for k in HISTORY_NAMES}
    updates = samples = 0
    for i in range(n if observed else n - 1):
        if observed:
            item = take("native_step", {"kind", "index", "step", "raw_step", "label_s", "storage"})
            wire.need(type(item["index"]) is int and item["index"] == i, "Global update index")
            for key, source_key in (
                ("step", "steps"),
                ("raw_step", "raw_steps"),
                ("label_s", "labels_s"),
            ):
                exact.match(item[key], old_trace[source_key][i], f"trace/{source_key}/{i}")
            if i == 0:
                wire.need(item["storage"] is None, "Spurious first storage sample")
            else:
                exact.match(item["storage"], old_trace["storage"][i - 1], f"trace/storage/{i - 1}")
                exact.match(
                    item["storage"]["index"],
                    old_trace["sampled_indices"][i - 1],
                    f"trace/sampled_indices/{i - 1}",
                )
            updates += 1
            del item
            if i == 0:
                continue
        sample = i - 1 if observed else i
        item = take("native_history", {"kind", "index", "values"})
        wire.need(type(item["index"]) is int and item["index"] == sample, "History sample index")
        wire.fields(item["values"], HISTORY_NAMES, "History value coverage")
        for name, value in item["values"].items():
            exact.match(
                value, histories[name]["values"][sample], f"histories/{name}/values/{sample}"
            )
            array_bytes(value, histories[name]["shape"][1:], hashes[name])
        samples += 1
        del item

    footer = take("native_footer", {"kind", "row", "trace", "histories_sha256"})
    wire.fields(footer["row"], TERMINAL, "Terminal root coverage")
    for key in TERMINAL:
        exact.match(footer["row"][key], original[key], key)
    if observed:
        wire.fields(footer["trace"], TRACE_END, "Terminal trace coverage")
        for key in TRACE_END:
            exact.match(footer["trace"][key], old_trace[key], "trace/" + key)
    else:
        wire.need(footer["trace"] is None, "Spurious terminal quiet trace")
    wire.fields(footer["histories_sha256"], HISTORY_NAMES, "Terminal history coverage")
    for name, digest in hashes.items():
        recorded = footer["histories_sha256"][name]
        exact.match(
            recorded, histories[name]["bytes_sha256"], "histories/" + name + "/bytes_sha256"
        )
        wire.need(digest.hexdigest() == recorded, "Independent history byte digest: " + name)
    arrays = footer["row"]["final_arrays"]
    for name, spec in arrays.items():
        array_shape(spec)
        digest = hashlib.sha256()
        array_bytes(spec["values"], spec["shape"], digest)
        wire.need(
            digest.hexdigest() == spec["bytes_sha256"], "Independent endpoint byte digest: " + name
        )
    exhausted = object()
    wire.need(next(iterator, exhausted) is exhausted, "Extra native records")
    expected_scalars = leaf_count(original, sequence_types=trace_sequence_types)
    wire.need(exact.scalars == expected_scalars, "Whole-original scalar coverage")
    wire.need(read_count == (2 * n + 1 if observed else n + 1), "Native stream extent")
    return dict(
        status="exact_every_original_value",
        observed_updates=updates,
        history_samples=samples,
        stream_records=read_count,
        original_scalar_values=expected_scalars,
        exact_scalar_comparisons=exact.scalars,
        float64_bit_comparisons=exact.floats,
        negative_zero_values=exact.negative_zeros,
        dictionary_keys_checked=exact.keys,
        containers_checked=exact.containers,
        history_array_digests=len(hashes),
        endpoint_array_digests=len(arrays),
    )


def inspect(original, directory):
    stream = wire.Stream(directory)
    result = compare_row(original, stream)
    wire.need(stream.complete, "Stream not exhausted")
    return result | dict(stream=stream.metrics)
