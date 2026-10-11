"""Independent, read-only CNRS@1 decoder; no producer-code imports.

The parser is a cursor object, and vectors use the standard-library array type.
Only one bounded chunk is retained. Returned objects belong to the consumer;
retaining them all is not bounded-memory use of this interface.
"""

import array
import hashlib
import json
import math
import re
import struct
import sys
import zlib
from pathlib import Path

CHUNK_BYTES = 8 * 1024**2
CONTROL_BYTES = 64 * 1024
STREAM_BYTES = 32 * 1024**2


def need(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def unique_pairs(items):
    result = {}
    for key, value in items:
        need(key not in result, "Repeated JSON key")
        result[key] = value
    return result


def finite_number(text):
    value = float(text)
    need(math.isfinite(value), "Nonfinite JSON number")
    return value


def json_value(text):
    return json.loads(
        text,
        object_pairs_hook=unique_pairs,
        parse_float=finite_number,
        parse_constant=lambda _: need(False, "Nonfinite JSON constant"),
    )


def read_json(path, limit=CONTROL_BYTES):
    path = Path(path)
    need(path.is_file() and not path.is_symlink(), "Missing/linked JSON input")
    with path.open("r", encoding="utf-8") as stream:
        if limit is None:
            # Legacy-only compatibility input. Explicitly materialized, not bounded
            # by CHUNK_BYTES; the registered review worker has a process memory cap.
            return json.load(
                stream,
                object_pairs_hook=unique_pairs,
                parse_float=finite_number,
                parse_constant=lambda _: need(False, "Nonfinite JSON constant"),
            )
        need(path.stat().st_size <= limit, "JSON input cap")
        text = stream.read(limit + 1)
        need(len(text) <= limit, "JSON input cap")
        return json_value(text)


def fields(value, expected, label):
    need(type(value) is dict and set(value) == set(expected), label + " fields")


def uint(value, maximum, label):
    need(type(value) is int and 0 <= value <= maximum, label + " integer/extent")


def digest_string(value):
    need(
        type(value) is str and re.fullmatch("[0-9a-f]{64}", value) is not None,
        "SHA-256 representation",
    )


class Cursor:
    def __init__(self, payload):
        need(0 < len(payload) <= CHUNK_BYTES, "Tree byte extent")
        self.data = memoryview(payload)
        self.offset = 0

    def take(self, size):
        end = self.offset + size
        need(0 <= size and end <= len(self.data), "Truncated tree")
        result = self.data[self.offset : end]
        self.offset = end
        return result

    def count(self):
        return int.from_bytes(self.take(4), "little", signed=False)

    def value(self, depth=0):
        need(depth <= 64, "Tree depth")
        tag = self.take(1)[0]
        if tag == ord("n"):
            return None
        if tag in (ord("t"), ord("f")):
            return tag == ord("t")
        if tag == ord("i"):
            return int.from_bytes(self.take(8), "little", signed=True)
        if tag == ord("d"):
            number = struct.unpack("<d", self.take(8))[0]
            need(math.isfinite(number), "Nonfinite binary64")
            return number
        need(tag in (ord("s"), ord("l"), ord("D"), ord("m")), "Unknown tree tag")
        count = self.count()
        if tag == ord("s"):
            return bytes(self.take(count)).decode("utf-8", "strict")
        if tag == ord("D"):
            values = array.array("d")
            need(values.itemsize == 8, "Platform float64 representation")
            values.frombytes(self.take(8 * count))
            if sys.byteorder != "little":
                values.byteswap()
            need(all(math.isfinite(v) for v in values), "Nonfinite binary64 vector")
            return values.tolist()
        if tag == ord("l"):
            need(count <= len(self.data) - self.offset, "List extent")
            return [self.value(depth + 1) for _ in range(count)]
        # A map pair needs at least an empty string key (5 bytes) and null (1).
        need(count <= (len(self.data) - self.offset) // 6, "Map extent")
        result = {}
        previous = None
        for _ in range(count):
            key = self.value(depth + 1)
            need(
                type(key) is str and (previous is None or key > previous),
                "Map keys are not ordered unique strings",
            )
            result[key] = self.value(depth + 1)
            previous = key
        return result


def tree(payload):
    cursor = Cursor(payload)
    value = cursor.value()
    need(cursor.offset == len(payload), "Trailing tree bytes")
    return value


class Stream:
    """Single-use iterator. complete stays false unless the entire stream passes."""

    def __init__(self, directory):
        self.directory = Path(directory)
        need(self.directory.is_dir() and not self.directory.is_symlink(), "Stream directory")
        m = self.manifest = read_json(self.directory / "manifest.json")
        fields(
            m,
            (
                "schema",
                "records",
                "chunks",
                "payload_bytes",
                "chunk_records",
                "chunk_bytes",
                "max_output_bytes",
                "index_sha256",
                "last_entry_sha256",
                "peak_encoded_record_bytes",
                "peak_encoded_chunk_bytes",
            ),
            "Manifest",
        )
        need(m["schema"] == "cells.native_record_stream@1", "Stream version")
        for key in (
            "records",
            "chunks",
            "payload_bytes",
            "peak_encoded_record_bytes",
            "peak_encoded_chunk_bytes",
        ):
            uint(m[key], STREAM_BYTES, "Manifest " + key)
        uint(m["chunk_records"], 32, "Chunk record cap")
        uint(m["chunk_bytes"], CHUNK_BYTES, "Chunk byte cap")
        uint(m["max_output_bytes"], STREAM_BYTES, "Stream byte cap")
        need(
            m["chunk_records"] > 0
            and m["chunk_bytes"] >= 32
            and m["max_output_bytes"] > CONTROL_BYTES,
            "Invalid stream limits",
        )
        need(m["chunks"] <= m["records"] <= m["chunks"] * m["chunk_records"], "Stream extent")
        for key in ("index_sha256", "last_entry_sha256"):
            digest_string(m[key])
        files = used = largest = 0
        for path in self.directory.iterdir():
            need(path.is_file() and not path.is_symlink(), "Nonregular/linked stream member")
            if path.name not in ("manifest.json", "index.jsonl"):
                match = re.fullmatch(r"chunk-(\d{8})\.bin\.z", path.name)
                need(match is not None and int(match[1]) < m["chunks"], "Unexpected stream member")
            size = path.stat().st_size
            largest = max(largest, size)
            files += 1
            used += size
        need(files == m["chunks"] + 2, "Missing stream member")
        need(used <= m["max_output_bytes"], "Stream byte budget")
        need(sha(self.directory / "index.jsonl") == m["index_sha256"], "Index digest")
        self.metrics = dict(
            records=0,
            chunks=0,
            raw_bytes=0,
            compressed_bytes=0,
            peak_record_bytes=0,
            peak_chunk_bytes=0,
            stream_bytes=used,
            stream_files=files,
            largest_stream_file_bytes=largest,
        )
        self.started = self.complete = False

    def __iter__(self):
        need(not self.started, "Stream iterator is single-use")
        self.started = True
        m, totals = self.manifest, self.metrics
        index_hash = hashlib.sha256()
        previous = "0" * 64
        with (self.directory / "index.jsonl").open("rb") as index:
            while line := index.readline(CONTROL_BYTES + 1):
                need(len(line) <= CONTROL_BYTES and line.endswith(b"\n"), "Index line extent")
                entry = json_value(line)
                fields(
                    entry,
                    (
                        "chunk",
                        "first_record",
                        "records",
                        "raw_bytes",
                        "compressed_bytes",
                        "raw_sha256",
                        "compressed_sha256",
                        "previous_entry_sha256",
                    ),
                    "Index",
                )
                for key in ("chunk", "first_record", "records", "raw_bytes", "compressed_bytes"):
                    uint(entry[key], STREAM_BYTES, "Index " + key)
                for key in ("raw_sha256", "compressed_sha256", "previous_entry_sha256"):
                    digest_string(entry[key])
                need(
                    entry["chunk"] == totals["chunks"] < m["chunks"]
                    and entry["first_record"] == totals["records"]
                    and entry["previous_entry_sha256"] == previous,
                    "Index sequence/chain",
                )
                need(1 <= entry["records"] <= m["chunk_records"], "Chunk record extent")
                need(6 < entry["raw_bytes"] <= m["chunk_bytes"], "Raw chunk extent")
                need(
                    0 < entry["compressed_bytes"] <= CHUNK_BYTES + CONTROL_BYTES,
                    "Compressed chunk extent",
                )
                path = self.directory / f"chunk-{totals['chunks']:08d}.bin.z"
                need(path.is_file() and not path.is_symlink(), "Linked/missing chunk")
                with path.open("rb") as file:
                    compressed = file.read(entry["compressed_bytes"] + 1)
                need(len(compressed) == entry["compressed_bytes"], "Compressed size")
                need(
                    hashlib.sha256(compressed).hexdigest() == entry["compressed_sha256"],
                    "Compressed digest",
                )
                inflater = zlib.decompressobj()
                raw = inflater.decompress(compressed, entry["raw_bytes"] + 1)
                need(
                    len(raw) == entry["raw_bytes"]
                    and inflater.eof
                    and not inflater.unconsumed_tail
                    and not inflater.unused_data,
                    "Compressed stream extent",
                )
                need(hashlib.sha256(raw).hexdigest() == entry["raw_sha256"], "Raw digest")
                need(raw[:6] == b"CNRS\x01\n", "Chunk version/magic")
                offset = 6
                for _ in range(entry["records"]):
                    need(offset + 4 <= len(raw), "Missing frame length")
                    size = int.from_bytes(raw[offset : offset + 4], "little")
                    offset += 4
                    need(0 < size <= len(raw) - offset, "Frame extent")
                    value = tree(memoryview(raw)[offset : offset + size])
                    offset += size
                    totals["records"] += 1
                    totals["peak_record_bytes"] = max(totals["peak_record_bytes"], size)
                    yield value
                    del value
                need(offset == len(raw), "Trailing chunk frames/bytes")
                totals["chunks"] += 1
                totals["raw_bytes"] += len(raw)
                totals["compressed_bytes"] += len(compressed)
                totals["peak_chunk_bytes"] = max(totals["peak_chunk_bytes"], len(raw))
                previous = hashlib.sha256(line).hexdigest()
                index_hash.update(line)
        need(
            index_hash.hexdigest() == m["index_sha256"] and previous == m["last_entry_sha256"],
            "Terminal index digest/chain",
        )
        for actual, expected in (
            ("records", "records"),
            ("chunks", "chunks"),
            ("compressed_bytes", "payload_bytes"),
            ("peak_record_bytes", "peak_encoded_record_bytes"),
            ("peak_chunk_bytes", "peak_encoded_chunk_bytes"),
        ):
            need(totals[actual] == m[expected], "Terminal count/measurement: " + actual)
        self.complete = True
