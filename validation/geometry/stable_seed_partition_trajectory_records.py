"""Bounded, append-only raw evidence for the unfrozen trajectory proposal.

Each value is durable before its index entry; a completion manifest is last.
Orphaned writes, partial indices and failure files are retained and never pass.
No model, fixture, NumPy or solver is imported here.
"""

import hashlib
import json
import math
import os
import struct
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def safe(value):
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        return (
            value
            if math.isfinite(value)
            else dict(nonfinite_binary64_le=struct.pack("<d", value).hex())
        )
    if isinstance(value, dict):
        if not all(type(key) is str for key in value):
            raise ValueError("Evidence keys require explicit strings")
        return {key: safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    # NumPy values remain exact arrays; importing NumPy is not necessary here.
    if hasattr(value, "dtype") and hasattr(value, "shape") and hasattr(value, "tobytes"):
        if value.dtype.kind not in "bifu" or value.dtype.itemsize > 8:
            raise TypeError(
                "Raw numeric evidence requires explicit real, integer or boolean storage"
            )
        return dict(
            dtype=value.dtype.str, shape=list(value.shape), data_hex=value.tobytes(order="C").hex()
        )
    raise TypeError("Uncaptured raw evidence type: " + type(value).__qualname__)


def encoded(value):
    return json.dumps(safe(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def write(path, value):
    path = Path(path)
    with path.open("xb") as stream:
        stream.write(encoded(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return dict(path=path.name, sha256=sha(path), bytes=path.stat().st_size)


class Journal:
    def __init__(self, directory):
        self.path = Path(directory)
        self.path.mkdir(parents=True, exist_ok=False)
        (self.path / "chunks").mkdir()
        self.count, self.chain, self.closed = 0, "0" * 64, False
        self.index = (self.path / "index.jsonl").open("xb")
        for parent in (self.path, self.path.parent):
            descriptor = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)

    def append(self, name, value):
        if self.closed or type(name) is not str or not name:
            raise ValueError("Append requires a live journal and explicit record role")
        rel = "chunks/" + str(self.count).zfill(9) + ".json"
        item = write(self.path / rel, value)
        row = dict(
            sequence=self.count,
            name=name,
            file=rel,
            sha256=item["sha256"],
            bytes=item["bytes"],
            previous=self.chain,
        )
        self.chain = digest(row)
        row["chain"] = self.chain
        self.index.write(encoded(row) + b"\n")
        self.index.flush()
        os.fsync(self.index.fileno())
        self.count += 1
        return row

    def close(self):
        if not self.closed:
            self.index.close()
            self.closed = True

    def complete(self, value):
        self.close()
        return write(
            self.path / "complete.json",
            dict(
                kind="cells.partition_trajectory_durable_segment@1",
                records=self.count,
                index_sha256=sha(self.path / "index.jsonl"),
                final_chain=self.chain,
                result=value,
                numerical_qualification_inherited=False,
            ),
        )

    def fail(self, value):
        self.close()
        return write(
            self.path / "failure.json",
            dict(
                kind="cells.partition_trajectory_failed_prefix@1",
                records=self.count,
                index_sha256=sha(self.path / "index.jsonl"),
                final_chain=self.chain,
                failure=value,
                completed=False,
            ),
        )


def entries(directory):
    """Verify a completed stream lazily, retaining at most one raw value."""
    path = Path(directory)
    manifest = json.loads((path / "complete.json").read_text())
    if (path / "failure.json").exists() or manifest[
        "kind"
    ] != "cells.partition_trajectory_durable_segment@1":
        raise ValueError("A failed prefix is not a completed segment")
    if sha(path / "index.jsonl") != manifest["index_sha256"]:
        raise ValueError("Changed completed evidence index")
    count, chain = 0, "0" * 64
    with (path / "index.jsonl").open("rb") as stream:
        for line in stream:
            row = json.loads(line)
            current = row.pop("chain")
            rel = "chunks/" + str(count).zfill(9) + ".json"
            if (
                row["sequence"] != count
                or row["previous"] != chain
                or row["file"] != rel
                or digest(row) != current
            ):
                raise ValueError("Changed evidence order, role or chain")
            chunk = path / rel
            if chunk.stat().st_size != row["bytes"] or sha(chunk) != row["sha256"]:
                raise ValueError("Changed raw evidence chunk")
            count, chain = count + 1, current
            yield row["name"], json.loads(chunk.read_text())
    if count != manifest["records"] or chain != manifest["final_chain"]:
        raise ValueError("Incomplete raw evidence stream")
    if sum(1 for _ in (path / "chunks").iterdir()) != count:
        raise ValueError("Unindexed raw writes are retained but cannot pass")
