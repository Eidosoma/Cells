"""Lossless partition of the closed pump INIT row into bounded evidence records.

Only the already-qualified pump row layout is supported. This module performs
structural/clock/array-integrity checks, not a new scientific acceptance review.
It imports neither the frozen producer nor either simulator.
"""

import hashlib
import math
import re
import struct

import record_codec as codec

SCHEMA = "cells.native_pump_row@1"
ROW_KEYS = set(
    """dt_s final final_arrays fixture fixture_hook geometry histories hook_restored
id metadata mode moving_ions native_pickle phase potassium_index settings sodium_index
source_constants steps trace""".split()
)
ROW_LATE = {"final", "final_arrays", "fixture_hook", "hook_restored", "native_pickle"}
TRACE_LISTS = {"steps", "raw_steps", "labels_s", "sampled_indices", "storage"}
TRACE_STATIC = {
    "calls",
    "gate_initializations",
    "hook_restored",
    "inflight_calls",
    "initial",
    "pending",
    "status",
}
HISTORIES = {
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
require = codec.require


def same(left, right, message):
    require(codec.canonical(left) == codec.canonical(right), message)


def array_spec(spec, checksum=True):
    keys = {"dtype", "shape", "bytes_sha256"} if checksum else {"dtype", "shape"}
    require(set(spec) == keys and spec["dtype"] == "<f8", "Array schema/dtype")
    require(
        type(spec["shape"]) is list
        and 0 < len(spec["shape"]) <= 8
        and all(type(v) is int and 0 <= v <= 1000000 for v in spec["shape"]),
        "Array shape",
    )
    if checksum:
        require(
            type(spec["bytes_sha256"]) is str
            and re.fullmatch(r"[0-9a-f]{64}", spec["bytes_sha256"]) is not None,
            "Array checksum format",
        )


def hash_array(value, shape, digest):
    if shape:
        require(type(value) is list and len(value) == shape[0], "Array shape mismatch")
        for child in value:
            hash_array(child, shape[1:], digest)
    else:
        require(type(value) in (float, int) and math.isfinite(value), "Array finite scalar")
        digest.update(struct.pack("<d", value))


def check_array(record):
    require(set(record) == {"dtype", "shape", "bytes_sha256", "values"}, "Array fields")
    spec = {k: v for k, v in record.items() if k != "values"}
    array_spec(spec)
    digest = hashlib.sha256()
    hash_array(record["values"], record["shape"], digest)
    require(digest.hexdigest() == record["bytes_sha256"], "Array byte checksum")


class Validator:
    """Constant-in-horizon semantic state; history digests update one sample at a time."""

    def __init__(self):
        self.header = None
        self.steps = self.samples = self.stored = 0
        self.complete = False

    def accept(self, record):
        require(type(record) is dict, "Native record object")
        require(not self.complete, "Record after native footer")
        if self.header is None:
            self._header(record)
        elif record.get("kind") == "native_step":
            self._step(record)
        elif record.get("kind") == "native_history":
            self._history(record)
        elif record.get("kind") == "native_footer":
            self._footer(record)
        else:
            raise ValueError("Unexpected/repeated native record kind")

    def _header(self, record):
        require(
            set(record) == {"kind", "schema", "row", "trace", "histories"}
            and record["kind"] == "native_header"
            and record["schema"] == SCHEMA,
            "Native header schema",
        )
        row, trace = record["row"], record["trace"]
        require(set(row) == ROW_KEYS - {"trace", "histories"} - ROW_LATE, "Native row fields")
        require(type(row["steps"]) is int and row["steps"] > 1, "Native step extent")
        require(
            type(row["dt_s"]) is float and math.isfinite(row["dt_s"]) and row["dt_s"] > 0,
            "Native dt",
        )
        require(
            row["mode"] in ("observed", "unobserved") and row["phase"] == "INIT",
            "Native mode/lifecycle",
        )
        if row["mode"] == "observed":
            require(type(trace) is dict and set(trace) == {"initial"}, "Trace fields")
        else:
            require(trace is None, "Quiet row has observation")
        require(set(record["histories"]) == HISTORIES, "Native history fields")
        for spec in record["histories"].values():
            array_spec(spec, checksum=False)
            require(spec["shape"][0] == row["steps"] - 1, "Native history extent")
        self.header = record
        self.hashes = {name: hashlib.sha256() for name in HISTORIES}

    def _step(self, record):
        require(
            set(record) == {"kind", "index", "step", "raw_step", "label_s", "storage"},
            "Native step fields",
        )
        row = self.header["row"]
        i = self.steps
        require(
            row["mode"] == "observed"
            and self.samples == max(0, i - 1)
            and type(record["index"]) is int
            and record["index"] == i < row["steps"],
            "Duplicate/missing/reordered native step",
        )
        step, raw = record["step"], record["raw_step"]
        require(
            set(step)
            == {
                "after_elapsed_s",
                "after_ordinary",
                "after_voltage",
                "before",
                "before_elapsed_s",
                "before_ordinary",
                "index",
                "order",
                "raw_label_s",
            }
            and set(raw) == {"before", "calls", "index"},
            "Physical step fields",
        )
        require(
            type(step["index"]) is int
            and type(raw["index"]) is int
            and step["index"] == raw["index"] == i,
            "Physical step index",
        )
        same(step["before_elapsed_s"], i * row["dt_s"], "Before physical clock")
        same(step["after_elapsed_s"], (i + 1) * row["dt_s"], "After physical clock")
        same(step["raw_label_s"], record["label_s"], "Raw label link")
        require(
            step["order"] == ["before_ordinary", "after_ordinary", "after_voltage"],
            "Physical boundary order",
        )
        calls = raw["calls"]
        pump = row["settings"]["alpha_NaK"] > 0
        require(
            [c["function"] for c in calls]
            == (["pumpNaKATP"] if pump else []) + ["electroflux"] * len(row["moving_ions"]),
            "Native call order/extent",
        )
        for j, call in enumerate(calls):
            pumping = pump and j == 0
            require(
                set(call)
                == (
                    {"function", "inputs", "returned"}
                    if pumping
                    else {"function", "inputs", "returned", "species_index"}
                ),
                "Incomplete native call pair",
            )
            expected = (
                {"T", "Vm", "block", "cKi", "cKo", "cNai", "cNao"}
                if pumping
                else {"Dc", "T", "cA", "cB", "d", "rho", "vBA", "zc"}
            )
            require(
                set(call["inputs"]) == expected and call["returned"] is not None,
                "Native call fields",
            )
            if not pumping:
                same(
                    call["species_index"],
                    row["moving_ions"][j - int(pump)],
                    "Native call species order",
                )
        if i == 0:
            require(record["storage"] is None, "First update unexpectedly stored")
        else:
            storage = record["storage"]
            require(
                set(storage) == {"index", "raw_label_s"}
                and type(storage["index"]) is int
                and storage["index"] == i,
                "Native storage index",
            )
            same(storage["raw_label_s"], record["label_s"], "Storage label link")
            self.stored += 1
        self.steps += 1

    def _history(self, record):
        require(set(record) == {"kind", "index", "values"}, "History record fields")
        row = self.header["row"]
        require(
            self.steps == (self.samples + 2 if row["mode"] == "observed" else 0),
            "History/observation order",
        )
        require(
            type(record["index"]) is int and record["index"] == self.samples < row["steps"] - 1,
            "Duplicate/missing/reordered history",
        )
        require(set(record["values"]) == HISTORIES, "History sample fields")
        for name, value in record["values"].items():
            hash_array(value, self.header["histories"][name]["shape"][1:], self.hashes[name])
        self.samples += 1

    def _footer(self, record):
        require(set(record) == {"kind", "row", "trace", "histories_sha256"}, "Native footer fields")
        require(
            set(record["row"]) == ROW_LATE and record["row"]["hook_restored"] is True,
            "Native endpoint/lifecycle",
        )
        row = self.header["row"]
        observed = row["mode"] == "observed"
        require(
            self.steps == (row["steps"] if observed else 0)
            and self.stored == (row["steps"] - 1 if observed else 0)
            and self.samples == row["steps"] - 1,
            "Incomplete native row",
        )
        trace = record["trace"]
        if observed:
            require(
                type(trace) is dict and set(trace) == TRACE_STATIC - {"initial"},
                "Trace terminal fields",
            )
            require(
                trace["pending"] is None
                and type(trace["inflight_calls"]) is int
                and trace["inflight_calls"] == 0
                and type(trace["gate_initializations"]) is int
                and trace["gate_initializations"] == 0
                and trace["hook_restored"] is True
                and trace["status"] == "complete_observation_not_qualification",
                "Incomplete observation",
            )
            require(
                set(trace["calls"])
                == {
                    "clear_storage",
                    "init_dynamics",
                    "initial_update_V",
                    "loop",
                    "loop_return",
                    "run_return",
                    "run_sim_core",
                }
                and all(type(v) is int and v == 1 for v in trace["calls"].values()),
                "Observer lifecycle counts",
            )
        else:
            require(trace is None, "Quiet row has observation")
        for array in record["row"]["final_arrays"].values():
            check_array(array)
        require(set(record["histories_sha256"]) == HISTORIES, "History checksum fields")
        for name, digest in self.hashes.items():
            require(
                digest.hexdigest() == record["histories_sha256"][name],
                "History byte checksum: " + name,
            )
        self.complete = True

    def finish(self):
        require(self.complete, "Missing native footer")


def records(row):
    """Partition every field. Legacy input is already materialized, not memory-bounded."""
    require(set(row) == ROW_KEYS, "Native row fields")
    trace, histories = row["trace"], row["histories"]
    if trace is not None:
        require(set(trace) == TRACE_STATIC | TRACE_LISTS, "Trace fields")
        require(all(type(trace[k]) is list for k in TRACE_LISTS), "Trace lists")
        require(
            all(len(trace[k]) == row["steps"] for k in ("steps", "raw_steps", "labels_s"))
            and len(trace["storage"]) == len(trace["sampled_indices"]) == row["steps"] - 1,
            "Trace extent",
        )
        require(
            all(type(v) is int and v == i + 1 for i, v in enumerate(trace["sampled_indices"])),
            "Sampled indices",
        )
    for array in histories.values():
        require(set(array) == {"dtype", "shape", "bytes_sha256", "values"}, "History fields")
        require(
            type(array["values"]) is list and len(array["values"]) == row["steps"] - 1,
            "History extent",
        )
    yield dict(
        kind="native_header",
        schema=SCHEMA,
        row={k: v for k, v in row.items() if k not in {"trace", "histories"} | ROW_LATE},
        trace=None if trace is None else {"initial": trace["initial"]},
        histories={
            k: {a: b for a, b in v.items() if a in {"dtype", "shape"}} for k, v in histories.items()
        },
    )

    def history(i):
        return dict(
            kind="native_history", index=i, values={k: v["values"][i] for k, v in histories.items()}
        )

    if trace is not None:
        for i in range(row["steps"]):
            yield dict(
                kind="native_step",
                index=i,
                step=trace["steps"][i],
                raw_step=trace["raw_steps"][i],
                label_s=trace["labels_s"][i],
                storage=None if i == 0 else trace["storage"][i - 1],
            )
            if i > 0:
                yield history(i - 1)
    else:
        for i in range(row["steps"] - 1):
            yield history(i)
    yield dict(
        kind="native_footer",
        row={k: row[k] for k in ROW_LATE},
        trace=None if trace is None else {k: trace[k] for k in TRACE_STATIC - {"initial"}},
        histories_sha256={k: v["bytes_sha256"] for k, v in histories.items()},
    )


def write_row(row, directory, **bounds):
    validator = Validator()
    with codec.RecordSink(directory, **bounds) as sink:
        for record in records(row):
            validator.accept(record)
            sink.append(record)
        validator.finish()
        return sink.finish()


def restore(stream):
    """Explicitly UNBOUNDED offline compatibility decoder; do not use for live runs.

    Reconstruct the original tree independently of the partition generator, for
    whole-row canonical comparison. Streaming consumers use Validator instead.
    """
    validator, result = Validator(), None
    for record in stream:
        validator.accept(record)
        if record["kind"] == "native_header":
            result = dict(record["row"])
            result["histories"] = {k: dict(v, values=[]) for k, v in record["histories"].items()}
            result["trace"] = None
            if record["trace"] is not None:
                result["trace"] = dict(record["trace"]) | {k: [] for k in TRACE_LISTS}
        elif record["kind"] == "native_step":
            trace = result["trace"]
            trace["steps"].append(record["step"])
            trace["raw_steps"].append(record["raw_step"])
            trace["labels_s"].append(record["label_s"])
            if record["storage"] is not None:
                trace["storage"].append(record["storage"])
                trace["sampled_indices"].append(record["storage"]["index"])
        elif record["kind"] == "native_history":
            for key, value in record["values"].items():
                result["histories"][key]["values"].append(value)
        else:
            result.update(record["row"])
            if record["trace"] is not None:
                result["trace"].update(record["trace"])
            for key, digest in record["histories_sha256"].items():
                result["histories"][key]["bytes_sha256"] = digest
    validator.finish()
    return result
