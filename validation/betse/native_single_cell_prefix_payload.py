"""Lossless bounded transport for dense prefix evidence, without NumPy.

The existing typed archive schema is preserved on read. Large raw-byte strings
move to hash-bound binary sidecars; repeated observations share storage, never
case credit. Metadata stays under its original 16 MiB limit. This transport
does not change production cache admission, numerical arrays or source methods.
"""

import hashlib
import json
from pathlib import Path

from validation import source_snapshot
from validation.geometry.qualification_typed_evidence import read_json

KIND = "cells.single_cell_prefix_capture@1"
TOKEN = "__prefix_raw_bytes__"
THRESHOLD = 32 * 2**10
MAX_BLOB = 16 * 2**20
MAX_UNIQUE = 64 * 2**20
MAX_EXPANDED = 128 * 2**20
MAX_NODES = 262144
MAX_DEPTH = 64


def _regular(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Linked evidence path")
    return path


def _digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(2**20), b""):
            h.update(block)
    return h.hexdigest()


def write(path, serialized):
    """Store already typed JSON data; no source object is decoded or replayed."""
    path = _regular(path)
    folder = _regular(path.with_name(path.name + ".arrays"))
    if path.exists() or folder.exists():
        raise FileExistsError("Evidence cannot be overwritten")
    blobs, counts = {}, dict(nodes=0, expanded=0, unique=0)

    def visit(value, key=None, depth=0):
        counts["nodes"] += 1
        if depth > MAX_DEPTH or counts["nodes"] > MAX_NODES:
            raise ValueError("Evidence tree bound")
        if key == "raw_bytes_hex" and type(value) is str and len(value) >= 2 * THRESHOLD:
            if len(value) > 2 * MAX_BLOB or len(value) % 2:
                raise ValueError("Raw evidence extent bound")
            raw = bytes.fromhex(value)
            if raw.hex() != value:
                raise ValueError("Require canonical raw evidence hex")
            counts["expanded"] += len(raw)
            if counts["expanded"] > MAX_EXPANDED:
                raise ValueError("Expanded evidence bound")
            digest = hashlib.sha256(raw).hexdigest()
            if digest not in blobs:
                counts["unique"] += len(raw)
                if counts["unique"] > MAX_UNIQUE:
                    raise ValueError("Unique evidence bound")
                folder.mkdir(exist_ok=True)
                name = digest + ".bin"
                with (folder / name).open("xb") as stream:
                    stream.write(raw)
                blobs[digest] = dict(name=name, sha256=digest, size=len(raw))
            return {TOKEN: digest}
        if type(value) is dict:
            if TOKEN in value:
                raise ValueError("Reserved evidence token in input")
            if any(type(k) is not str for k in value):
                raise ValueError("Typed JSON requires string keys")
            return {k: visit(v, k, depth + 1) for k, v in value.items()}
        if type(value) is list:
            return [visit(v, depth=depth + 1) for v in value]
        if value is None or type(value) in (str, int, bool):
            return value
        raise ValueError("Require typed JSON; no raw scalar/object substitution")

    tree = visit(serialized)
    record = dict(kind=KIND, payload=tree, blobs=list(blobs.values()))
    if len(json.dumps(record, indent=2, sort_keys=True, allow_nan=False).encode()) + 1 > 16 * 2**20:
        raise ValueError("Evidence metadata bound")
    source_snapshot.write_json(path, record)
    # Verify the bytes just written, not only the in-memory producer record.
    return files(path)


def _read(path, *, expand):
    path = _regular(path)
    record = read_json(path)
    if type(record) is not dict or record.get("kind") != KIND:
        return record, []
    if set(record) != {"kind", "payload", "blobs"} or type(record["blobs"]) is not list:
        raise ValueError("Incomplete evidence envelope")
    folder = _regular(path.with_name(path.name + ".arrays"))
    blobs, pins, unique = {}, [], 0
    for row in record["blobs"]:
        if type(row) is not dict or set(row) != {"name", "sha256", "size"}:
            raise ValueError("Malformed evidence sidecar")
        digest, size = row["sha256"], row["size"]
        if (
            type(digest) is not str
            or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
            or row["name"] != digest + ".bin"
            or digest in blobs
            or type(size) is not int
            or not THRESHOLD <= size <= MAX_BLOB
        ):
            raise ValueError("Invalid or duplicate evidence sidecar")
        unique += size
        if unique > MAX_UNIQUE:
            raise ValueError("Unique evidence bound")
        file = _regular(folder / row["name"])
        if not file.is_file() or file.stat().st_size != size:
            raise ValueError("Missing or changed evidence sidecar")
        # Authenticate exactly the bytes returned, with a bound on that same
        # read. A second unverified read could race a file change or growth.
        with file.open("rb") as stream:
            raw = stream.read(size + 1)
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("Missing or changed evidence sidecar")
        blobs[digest] = (size, raw.hex() if expand else None)
        pins.append(dict(path=str(file), sha256=digest))
    counts, used = dict(nodes=0, expanded=0), set()

    def visit(value, key=None, depth=0):
        counts["nodes"] += 1
        if depth > MAX_DEPTH or counts["nodes"] > MAX_NODES:
            raise ValueError("Evidence tree bound")
        if type(value) is dict and TOKEN in value:
            if set(value) != {TOKEN} or key != "raw_bytes_hex":
                raise ValueError("Misplaced evidence token")
            digest = value[TOKEN]
            if type(digest) is not str or digest not in blobs:
                raise ValueError("Unbound evidence token")
            size, text = blobs[digest]
            counts["expanded"] += size
            if counts["expanded"] > MAX_EXPANDED:
                raise ValueError("Expanded evidence bound")
            used.add(digest)
            return text if expand else value
        if type(value) is dict:
            return {k: visit(v, k, depth + 1) for k, v in value.items()}
        if type(value) is list:
            return [visit(v, depth=depth + 1) for v in value]
        if value is None or type(value) in (str, int, bool):
            return value
        raise ValueError("Untyped evidence scalar")

    tree = visit(record["payload"])
    if used != set(blobs):
        raise ValueError("Unused evidence sidecar")
    return tree, pins


def read(path, *, expand=True):
    """Read legacy JSON or a fully authenticated sidecar capture.

    expand=False validates every byte but leaves tokens for metadata-only
    lineage checks. It must not be used for a numerical comparison.
    """
    return _read(path, expand=expand)[0]


def files(path):
    """Return all required input pins, including payloads outside the JSON file."""
    path = _regular(path)
    _, pins = _read(path, expand=False)
    return [dict(path=str(path), sha256=_digest(path)), *pins]
