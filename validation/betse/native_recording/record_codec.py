"""Bounded, lossless JSON-tree records with explicit little-endian float64.

This is an adapter evidence format, not a simulator, checkpoint or pickle. The
writer retains one encoded chunk, not a horizon-length list or index. Caller
objects, compression workspace, decoded objects and Python overhead are NOT
included in the encoded-byte limit. Whole-process memory must be measured too.
"""

import hashlib
import json
import math
import os
import re
import struct
import zlib
from pathlib import Path

SCHEMA = "cells.native_record_stream@1"
MAGIC = b"CNRS\x01\n"
MAX_BYTES = 8 * 1024**2
MAX_RECORDS = 32
MAX_DEPTH = 64
CONTROL_BYTES = 64 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def canonical_sha(value):
    digest = hashlib.sha256()
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"), allow_nan=False)
    for piece in encoder.iterencode(value):
        digest.update(piece.encode())
    return digest.hexdigest()


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while piece := stream.read(1024**2):
            digest.update(piece)
    return digest.hexdigest()


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result

    def number(value):
        result = float(value)
        require(math.isfinite(result), "Nonfinite JSON number")
        return result

    return json.loads(
        data,
        object_pairs_hook=pairs,
        parse_float=number,
        parse_constant=lambda _: require(False, "Nonfinite JSON constant"),
    )


def read_json(path, limit=None):
    require(not Path(path).is_symlink(), "Linked JSON file")
    with Path(path).open("rb") as stream:
        data = stream.read() if limit is None else stream.read(limit + 1)
    require(limit is None or len(data) <= limit, "JSON byte limit")
    return strict_json(data)


def write_json(path, value):
    with Path(path).open("xb") as stream:
        stream.write(canonical(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def encode(value, limit=MAX_BYTES):
    """Encode supported JSON trees; integers are signed int64, floats binary64."""
    require(type(limit) is int and 0 < limit <= MAX_BYTES, "Record byte limit")
    result = bytearray()

    def add(raw):
        require(len(result) + len(raw) <= limit, "Record byte limit")
        result.extend(raw)

    def length(tag, count):
        require(count <= limit, "Container length limit")
        add(tag + struct.pack("<I", count))

    def visit(item, depth):
        require(depth <= MAX_DEPTH, "Record depth limit")
        kind = type(item)
        if item is None:
            add(b"n")
        elif kind is bool:
            add(b"t" if item else b"f")
        elif kind is int:
            require(-(2**63) <= item < 2**63, "Integer outside int64")
            add(b"i" + struct.pack("<q", item))
        elif kind is float:
            require(math.isfinite(item), "Nonfinite float64")
            add(b"d" + struct.pack("<d", item))
        elif kind is str:
            require(len(item) <= limit, "String length limit")
            raw = item.encode("utf-8", errors="strict")
            length(b"s", len(raw))
            add(raw)
        elif kind is list:
            if item and all(type(v) is float for v in item):
                require(all(math.isfinite(v) for v in item), "Nonfinite float64 vector")
                require(5 + 8 * len(item) + len(result) <= limit, "Record byte limit")
                length(b"D", len(item))
                add(struct.pack(f"<{len(item)}d", *item))
            else:
                length(b"l", len(item))
                for child in item:
                    visit(child, depth + 1)
        elif kind is dict:
            require(all(type(k) is str for k in item), "Dictionary keys must be strings")
            length(b"m", len(item))
            for key in sorted(item):
                visit(key, depth + 1)
                visit(item[key], depth + 1)
        else:
            raise ValueError("Unsupported record type: " + kind.__name__)

    try:
        visit(value, 0)
        return bytes(result)
    finally:
        # Break the recursive closure cycle: releasing buffers must not depend
        # on cyclic-GC scheduling (or on cyclic GC being enabled at all).
        visit = None


def decode(data, limit=MAX_BYTES):
    """Decode one bounded tree. No executable or object-construction opcodes."""
    require(type(limit) is int and 0 < limit <= MAX_BYTES, "Record byte limit")
    require(0 < len(data) <= limit, "Record byte limit")
    view, position = memoryview(data), 0

    def take(count):
        nonlocal position
        require(0 <= count <= len(view) - position, "Truncated binary record")
        piece = view[position : position + count]
        position += count
        return piece

    def integer():
        return struct.unpack("<I", take(4))[0]

    def visit(depth):
        require(depth <= MAX_DEPTH, "Record depth limit")
        tag = bytes(take(1))
        if tag in (b"n", b"t", b"f"):
            return {b"n": None, b"t": True, b"f": False}[tag]
        if tag == b"i":
            return struct.unpack("<q", take(8))[0]
        if tag == b"d":
            value = struct.unpack("<d", take(8))[0]
            require(math.isfinite(value), "Nonfinite float64")
            return value
        require(tag in (b"s", b"D", b"l", b"m"), "Unknown binary tag")
        count = integer()
        if tag == b"s":
            return bytes(take(count)).decode("utf-8", errors="strict")
        if tag == b"D":
            values = [v for (v,) in struct.iter_unpack("<d", take(8 * count))]
            require(all(math.isfinite(v) for v in values), "Nonfinite float64 vector")
            return values
        require(count <= len(view) - position, "Container length exceeds payload")
        if tag == b"l":
            return [visit(depth + 1) for _ in range(count)]
        result, previous = {}, None
        for _ in range(count):
            key = visit(depth + 1)
            require(
                type(key) is str and (previous is None or key > previous),
                "Dictionary keys must be sorted unique strings",
            )
            result[key] = visit(depth + 1)
            previous = key
        return result

    try:
        result = visit(0)
        require(position == len(view), "Trailing binary data")
        return result
    finally:
        visit = None


def limits(records, size):
    require(type(records) is int and 1 <= records <= MAX_RECORDS, "Chunk record limit")
    require(type(size) is int and 32 <= size <= MAX_BYTES, "Chunk byte limit")


class RecordSink:
    """Append-only chunks/index; a manifest is published only by finish().

    There is no resume/overwrite API. An incomplete directory is partial evidence.
    A failed append poisons the sink, even if a caller catches the exception.
    """

    def __init__(
        self,
        directory,
        chunk_records=MAX_RECORDS,
        chunk_bytes=MAX_BYTES,
        max_output_bytes=256 * 1024**2,
    ):
        limits(chunk_records, chunk_bytes)
        require(
            type(max_output_bytes) is int and CONTROL_BYTES < max_output_bytes <= 2**40,
            "Stream output budget",
        )
        self.directory = Path(directory)
        self.directory.mkdir()  # Must be new; parent is selected by the caller.
        self.index = (self.directory / "index.jsonl").open("xb")
        self.chunk_records, self.chunk_bytes = chunk_records, chunk_bytes
        self.buffer, self.pending = bytearray(MAGIC), 0
        self.records = self.chunks = self.payload_bytes = 0
        self.output_bytes = 0
        self.max_output_bytes = max_output_bytes
        self.peak_chunk_bytes = self.peak_record_bytes = 0
        self.index_hash, self.previous = hashlib.sha256(), "0" * 64
        self.closed = self.failed = False

    def append(self, value):
        require(not self.closed and not self.failed, "Closed or failed sink")
        try:
            raw = encode(value, self.chunk_bytes - len(MAGIC) - 4)
            if self.pending and len(self.buffer) + 4 + len(raw) > self.chunk_bytes:
                self._flush()
            self.buffer.extend(struct.pack("<I", len(raw)))
            self.buffer.extend(raw)
            self.pending += 1
            self.peak_record_bytes = max(self.peak_record_bytes, len(raw))
            self.peak_chunk_bytes = max(self.peak_chunk_bytes, len(self.buffer))
            if self.pending == self.chunk_records:
                self._flush()
        except BaseException:
            self.failed = True
            raise

    def _flush(self):
        if not self.pending:
            return
        compressed = zlib.compress(self.buffer, level=6)
        name = f"chunk-{self.chunks:08d}.bin.z"
        entry = dict(
            chunk=self.chunks,
            first_record=self.records,
            records=self.pending,
            raw_bytes=len(self.buffer),
            compressed_bytes=len(compressed),
            raw_sha256=hashlib.sha256(self.buffer).hexdigest(),
            compressed_sha256=hashlib.sha256(compressed).hexdigest(),
            previous_entry_sha256=self.previous,
        )
        line = canonical(entry) + b"\n"
        require(
            self.output_bytes + len(compressed) + len(line)
            <= self.max_output_bytes - CONTROL_BYTES,
            "Stream output budget exhausted",
        )
        with (self.directory / name).open("xb") as stream:
            stream.write(compressed)
            stream.flush()
            os.fsync(stream.fileno())
        self.index.write(line)
        self.index.flush()
        os.fsync(self.index.fileno())
        self.index_hash.update(line)
        self.previous = hashlib.sha256(line).hexdigest()
        self.records += self.pending
        self.chunks += 1
        self.payload_bytes += len(compressed)
        self.output_bytes += len(compressed) + len(line)
        self.buffer, self.pending = bytearray(MAGIC), 0

    def finish(self):
        require(not self.closed and not self.failed, "Closed or failed sink")
        try:
            self._flush()
            self.index.close()
            result = dict(
                schema=SCHEMA,
                records=self.records,
                chunks=self.chunks,
                payload_bytes=self.payload_bytes,
                chunk_records=self.chunk_records,
                chunk_bytes=self.chunk_bytes,
                max_output_bytes=self.max_output_bytes,
                index_sha256=self.index_hash.hexdigest(),
                last_entry_sha256=self.previous,
                peak_encoded_record_bytes=self.peak_record_bytes,
                peak_encoded_chunk_bytes=self.peak_chunk_bytes,
            )
            # Exclusive hard-link publication prevents replacement and torn manifests.
            partial = self.directory / "manifest.partial"
            write_json(partial, result)
            os.link(partial, self.directory / "manifest.json")
            partial.unlink()
            self.closed = True
            return result
        except BaseException:
            self.failed = True
            raise

    def close(self):
        self.index.close()
        self.closed = True
        self.buffer = bytearray()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()  # Never implicitly publish success on context exit.


def iter_records(directory):
    """Verify and iterate without retaining a horizon-length index or record list.

    Consumers must exhaust the iterator to establish completeness. Manifest/index
    hashes are checked up front; payload checks are performed before each chunk
    is yielded. This function does not authenticate the scientific provenance.
    """
    directory = Path(directory)
    require(not directory.is_symlink(), "Linked record directory")
    manifest = read_json(directory / "manifest.json", CONTROL_BYTES)
    required = {
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
    }
    require(set(manifest) == required and manifest["schema"] == SCHEMA, "Stream schema")
    for key in (
        "records",
        "chunks",
        "payload_bytes",
        "peak_encoded_record_bytes",
        "peak_encoded_chunk_bytes",
    ):
        require(type(manifest[key]) is int and manifest[key] >= 0, "Manifest integer")
    limits(manifest["chunk_records"], manifest["chunk_bytes"])
    require(
        type(manifest["max_output_bytes"]) is int
        and CONTROL_BYTES < manifest["max_output_bytes"] <= 2**40,
        "Stream output budget",
    )
    require(
        manifest["chunks"] <= manifest["records"] <= manifest["chunks"] * manifest["chunk_records"],
        "Manifest record extent",
    )
    # Count expected deterministic names without keeping an in-memory file inventory.
    files = file_bytes = 0
    for path in directory.iterdir():
        require(path.is_file() and not path.is_symlink(), "Unexpected or linked payload")
        if path.name not in ("manifest.json", "index.jsonl"):
            match = re.fullmatch(r"chunk-(\d{8})\.bin\.z", path.name)
            require(match is not None and int(match[1]) < manifest["chunks"], "Extra payload")
        files += 1
        file_bytes += path.stat().st_size
        require(file_bytes <= manifest["max_output_bytes"], "Stream output budget exceeded")
    require(files == manifest["chunks"] + 2, "Missing payload")
    index = directory / "index.jsonl"
    require(file_sha(index) == manifest["index_sha256"], "Index checksum")
    total = count = used = peak_chunk = peak_record = 0
    previous = "0" * 64
    index_hash = hashlib.sha256()
    with index.open("rb") as stream:
        while line := stream.readline(CONTROL_BYTES + 1):
            require(len(line) <= CONTROL_BYTES and line.endswith(b"\n"), "Torn/large index line")
            entry = strict_json(line)
            require(
                set(entry)
                == {
                    "chunk",
                    "first_record",
                    "records",
                    "raw_bytes",
                    "compressed_bytes",
                    "raw_sha256",
                    "compressed_sha256",
                    "previous_entry_sha256",
                },
                "Index schema",
            )
            for key in ("chunk", "first_record", "records", "raw_bytes", "compressed_bytes"):
                require(type(entry[key]) is int, "Index integer")
            require(
                entry["chunk"] == count < manifest["chunks"]
                and entry["first_record"] == total
                and entry["previous_entry_sha256"] == previous,
                "Reordered/duplicate/missing chunk",
            )
            require(1 <= entry["records"] <= manifest["chunk_records"], "Chunk record extent")
            require(len(MAGIC) < entry["raw_bytes"] <= manifest["chunk_bytes"], "Chunk raw extent")
            require(0 < entry["compressed_bytes"] <= MAX_BYTES + 65536, "Compressed extent")
            path = directory / f"chunk-{count:08d}.bin.z"
            require(path.stat().st_size == entry["compressed_bytes"], "Compressed size mismatch")
            compressed = path.read_bytes()  # Checked, bounded to one chunk above.
            require(
                hashlib.sha256(compressed).hexdigest() == entry["compressed_sha256"],
                "Payload checksum",
            )
            inflater = zlib.decompressobj()
            raw = inflater.decompress(compressed, entry["raw_bytes"] + 1)
            require(
                len(raw) == entry["raw_bytes"]
                and inflater.eof
                and not inflater.unused_data
                and not inflater.unconsumed_tail,
                "Compressed stream extent/trailer",
            )
            require(hashlib.sha256(raw).hexdigest() == entry["raw_sha256"], "Raw checksum")
            require(raw.startswith(MAGIC), "Chunk magic/version")
            offset = len(MAGIC)
            for _ in range(entry["records"]):
                require(offset + 4 <= len(raw), "Truncated frame length")
                size = struct.unpack_from("<I", raw, offset)[0]
                offset += 4
                require(0 < size <= len(raw) - offset, "Truncated frame")
                yield decode(memoryview(raw)[offset : offset + size], manifest["chunk_bytes"])
                offset += size
                peak_record = max(peak_record, size)
            require(offset == len(raw), "Extra frames/bytes")
            peak_chunk = max(peak_chunk, len(raw))
            index_hash.update(line)
            previous = hashlib.sha256(line).hexdigest()
            total += entry["records"]
            count += 1
            used += len(compressed)
    require(
        count == manifest["chunks"]
        and total == manifest["records"]
        and used == manifest["payload_bytes"]
        and previous == manifest["last_entry_sha256"]
        and index_hash.hexdigest() == manifest["index_sha256"]
        and peak_chunk == manifest["peak_encoded_chunk_bytes"]
        and peak_record == manifest["peak_encoded_record_bytes"],
        "Incomplete stream or inconsistent metrics",
    )
