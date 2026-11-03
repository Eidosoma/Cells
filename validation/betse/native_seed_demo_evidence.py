"""Lossless, finite multipart transport for SEED demonstration observations.

Ordinary payload defaults are untouched. This explicit profile accommodates a
100,000-entry work ledger (400,001 typed nodes for triples) without truncation.
It stores already serialized data, never decodes an owner or invokes a model.
"""

import hashlib
import json
from pathlib import Path

from validation import source_snapshot as snapshot
from validation.betse import native_single_cell_prefix_payload as payload

KIND = "cells.seed_demo_multipart_evidence@1"
REFERENCE = "__seed_demo_part__"
PAGES = "__seed_demo_pages__"
MAX_NODES = 1048576
MAX_PARTS = 64
MAX_METADATA = 64 * 2**20
TARGET_NODES = 32768
TARGET_BYTES = 2 * 2**20
PROFILE = dict(
    nodes=MAX_NODES,
    parts=MAX_PARTS,
    metadata_bytes=MAX_METADATA,
    part_nodes=payload.MAX_NODES,
    part_metadata_bytes=payload.MAX_METADATA,
    depth=payload.MAX_DEPTH,
    blob_bytes=payload.MAX_BLOB,
    unique_bytes=payload.MAX_UNIQUE,
    expanded_bytes=payload.MAX_EXPANDED,
)
_RAW_FAILURES = []


def source_plan():
    return dict(
        kind=KIND,
        profile=PROFILE,
        ordinary_defaults_unchanged=True,
        work_ledger_domain=100000,
        case_credit=0,
        owner_hydration=False,
        scalar_array_layout_or_bit_normalization=False,
    )


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _seal(value):
    digest = hashlib.sha256()
    # Typed dict order is not authority in the existing sorted-key JSON format;
    # all explicit ordered item/record lists, strings and bit payloads are exact.
    for piece in json.JSONEncoder(
        sort_keys=True, separators=(",", ":"), allow_nan=False
    ).iterencode(value):
        digest.update(piece.encode())
    return digest.hexdigest()


def _measure(value, *, blobs=None):
    """Validate aggregate extents before writing, retaining per-container weights."""
    counts = dict(nodes=0, depth=0, unique_bytes=0, expanded_bytes=0)
    raw, weights = {}, {}

    def walk(item, key=None, depth=0):
        counts["nodes"] += 1
        counts["depth"] = max(counts["depth"], depth)
        require(
            counts["nodes"] <= MAX_NODES and depth <= payload.MAX_DEPTH,
            "Aggregate evidence tree bound",
        )
        if (
            key == "raw_bytes_hex"
            and type(item) is dict
            and payload.TOKEN in item
            and blobs is not None
        ):
            require(
                set(item) == {payload.TOKEN}
                and type(item[payload.TOKEN]) is str
                and item[payload.TOKEN] in blobs,
                "Unbound aggregate raw token",
            )
            digest, size = item[payload.TOKEN], blobs[item[payload.TOKEN]]["size"]
            preview = item
        elif key == "raw_bytes_hex" and type(item) is str and len(item) >= 2 * payload.THRESHOLD:
            require(
                len(item) <= 2 * payload.MAX_BLOB and len(item) % 2 == 0,
                "Raw evidence extent bound",
            )
            binary = bytes.fromhex(item)
            require(binary.hex() == item, "Canonical raw evidence hex required")
            digest = hashlib.sha256(binary).hexdigest()
            size = len(binary)
            preview = {payload.TOKEN: digest}
        else:
            digest = None
        if digest is not None:
            counts["expanded_bytes"] += size
            if digest not in raw:
                raw[digest] = size
                counts["unique_bytes"] += size
            require(
                counts["unique_bytes"] <= payload.MAX_UNIQUE
                and counts["expanded_bytes"] <= payload.MAX_EXPANDED,
                "Aggregate raw evidence bound",
            )
            return preview, 1, len(json.dumps(preview))
        if type(item) is dict:
            require(all(type(k) is str for k in item), "Typed string keys required")
            require(payload.TOKEN not in item, "Reserved raw token in original input")
            require(
                not ({REFERENCE, PAGES} & item.keys()),
                "Reserved multipart token in input",
            )
            preview, nodes, size = {}, 1, 2
            for name, child in item.items():
                child_preview, child_nodes, child_size = walk(child, name, depth + 1)
                preview[name] = child_preview
                nodes += child_nodes
                size += len(json.dumps(name)) + child_size + 4
            weights[id(item)] = (nodes, size)
            return preview, nodes, size
        if type(item) is list:
            preview, nodes, size = [], 1, 2
            for child in item:
                child_preview, child_nodes, child_size = walk(child, depth=depth + 1)
                preview.append(child_preview)
                nodes += child_nodes
                size += child_size + 2
            weights[id(item)] = (nodes, size)
            return preview, nodes, size
        require(item is None or type(item) in (str, int, bool), "Require already typed JSON data")
        return item, 1, len(json.dumps(item, allow_nan=False))

    preview, _, _ = walk(value)
    blobs = [dict(name=digest + ".bin", sha256=digest, size=size) for digest, size in raw.items()]
    ordinary_size = (
        len(
            json.dumps(
                dict(kind=payload.KIND, payload=preview, blobs=blobs),
                indent=2,
                sort_keys=True,
                allow_nan=False,
            ).encode()
        )
        + 1
    )
    require(ordinary_size <= MAX_METADATA, "Aggregate metadata bound")
    counts["ordinary_metadata_bytes"] = ordinary_size
    return counts, weights, preview


def _partition(value, weights):
    parts = []

    def store(item):
        require(len(parts) < MAX_PARTS, "Multipart count bound")
        index = len(parts)
        parts.append(item)
        return {REFERENCE: index}, 2, 40

    def weight(item, key=None):
        if type(item) in (dict, list):
            return weights[id(item)]
        if key == "raw_bytes_hex" and type(item) is str and len(item) >= 2 * payload.THRESHOLD:
            return 1, 100
        return 1, len(json.dumps(item, allow_nan=False))

    def pack(item, key=None):
        nodes, size = weight(item, key)
        if nodes <= TARGET_NODES and size <= TARGET_BYTES:
            return item, nodes, size
        if type(item) not in (list, dict):
            # A raw-byte string must remain beneath its original ndarray key;
            # it is never detached as an untyped string part.
            require(key != "raw_bytes_hex", "Raw leaf must remain in its typed container")
            return store(item)
        mapping = type(item) is dict
        children = []
        for name, child in item.items() if mapping else enumerate(item):
            converted, child_nodes, child_size = pack(child, name if mapping else None)
            if mapping:
                children.append(
                    ([name, converted], child_nodes + 2, child_size + len(json.dumps(name)) + 5)
                )
            else:
                children.append((converted, child_nodes, child_size))
        # Keep a compact transformed container intact where possible.
        total_nodes = 1 + sum(n for _, n, _ in children)
        total_bytes = 2 + sum(n for _, _, n in children)
        if total_nodes <= TARGET_NODES and total_bytes <= TARGET_BYTES:
            result = dict(x for x, _, _ in children) if mapping else [x for x, _, _ in children]
            return result, total_nodes, total_bytes
        pages, group, group_nodes, group_bytes = [], [], 1, 2
        for child, child_nodes, child_bytes in children:
            if group and (
                group_nodes + child_nodes > TARGET_NODES or group_bytes + child_bytes > TARGET_BYTES
            ):
                pages.append(store(group)[0][REFERENCE])
                group, group_nodes, group_bytes = [], 1, 2
            group.append(child)
            group_nodes += child_nodes
            group_bytes += child_bytes
        if group:
            pages.append(store(group)[0][REFERENCE])
        token = {PAGES: dict(kind="dict" if mapping else "list", parts=pages)}
        return token, 5 + len(pages), 70 + 10 * len(pages)

    root, _, _ = pack(value)
    # Keep every raw leaf inside an ordinary payload part, including leaves
    # remaining beside a paged ledger at the logical root.
    root = store(root)[0]
    return root, parts


def _label(value):
    require(type(value) is str and 0 < len(value) <= 512, "Bounded explicit capture label required")
    return value


def _folder(path):
    return payload._regular(path.with_name(path.name + ".parts"))


def _refused(folder, primary, rows, attempted):
    try:
        _RAW_FAILURES.append((primary, rows, attempted))
    except BaseException:
        pass
    try:
        snapshot.write_json(
            folder / "INCOMPLETE.json",
            dict(
                kind=KIND,
                completed_parts=rows,
                attempted_part=attempted,
                primary_type=type(primary).__module__ + "." + type(primary).__qualname__,
                primary_preserved=True,
                complete=False,
            ),
        )
    except BaseException as secondary:
        try:
            _RAW_FAILURES.append((primary, secondary, "incomplete-publication"))
        except BaseException:
            pass


def _index(value):
    require(
        type(value) is dict
        and set(value) == {"kind", "profile", "label", "root", "parts", "counts", "logical_sha256"},
        "Exact multipart manifest required",
    )
    require(value["kind"] == KIND and value["profile"] == PROFILE, "Multipart profile changed")
    _label(value["label"])
    require(
        type(value["parts"]) is list and 0 < len(value["parts"]) <= MAX_PARTS,
        "Bounded part roster required",
    )
    require(
        type(value["logical_sha256"]) is str
        and len(value["logical_sha256"]) == 64
        and all(c in "0123456789abcdef" for c in value["logical_sha256"]),
        "Logical payload digest required",
    )


def _load(path, value):
    _index(value)
    folder = _folder(path)
    require(
        folder.is_dir() and not (folder / "INCOMPLETE.json").exists(),
        "Incomplete multipart evidence",
    )
    pieces, pins, expected, metadata = [], [], set(), 0
    paths, blobs, encoded_nodes = [], {}, 0
    for index, row in enumerate(value["parts"]):
        require(
            type(row) is dict
            and set(row) == {"name", "sha256", "metadata_bytes"}
            and row["name"] == f"part-{index:04d}.json",
            "Part name/order/roster changed",
        )
        require(
            type(row["metadata_bytes"]) is int
            and 0 < row["metadata_bytes"] <= payload.MAX_METADATA,
            "Part metadata extent",
        )
        p = payload._regular(folder / row["name"])
        require(
            p.is_file() and p.stat().st_size == row["metadata_bytes"], "Missing/changed part extent"
        )
        metadata += row["metadata_bytes"]
        require(metadata <= MAX_METADATA, "Aggregate part metadata bound")
        # Authenticate metadata first. No expanded raw reads occur until the
        # complete logical graph and its global byte/node budgets are checked.
        record, _ = payload._metadata(p, payload.MAX_METADATA, row["sha256"])
        require(
            type(record) is dict
            and set(record) == {"kind", "payload", "blobs"}
            and record["kind"] == payload.KIND
            and type(record["blobs"]) is list,
            "Ordinary typed part envelope required",
        )
        pending, part_nodes = [record["payload"]], 0
        while pending:
            item = pending.pop()
            part_nodes += 1
            require(part_nodes <= payload.MAX_NODES, "Part node bound")
            if type(item) is dict:
                pending.extend(item.values())
            elif type(item) is list:
                pending.extend(item)
        encoded_nodes += part_nodes
        require(encoded_nodes <= 3 * MAX_NODES + MAX_PARTS * 16, "Encoded aggregate node bound")
        for blob in record["blobs"]:
            require(
                type(blob) is dict
                and set(blob) == {"name", "sha256", "size"}
                and type(blob["sha256"]) is str
                and len(blob["sha256"]) == 64
                and all(c in "0123456789abcdef" for c in blob["sha256"])
                and blob["name"] == blob["sha256"] + ".bin"
                and type(blob["size"]) is int
                and payload.THRESHOLD <= blob["size"] <= payload.MAX_BLOB,
                "Exact bounded blob declaration required",
            )
            key = blob["sha256"]
            require(
                key not in blobs or blobs[key]["size"] == blob["size"],
                "Inconsistent raw digest extent",
            )
            blobs.setdefault(
                key, dict(size=blob["size"], path=p.with_name(p.name + ".arrays") / blob["name"])
            )
        require(
            sum(blob["size"] for blob in blobs.values()) <= payload.MAX_UNIQUE,
            "Aggregate raw evidence bound",
        )
        paths.append((p, row["sha256"]))
        pieces.append(record["payload"])
    used = set()
    visited = 0

    def take(index):
        require(
            type(index) is int and 0 <= index < len(pieces) and index not in used,
            "Duplicate, cyclic or absent part reference",
        )
        used.add(index)
        return pieces[index]

    def reference(index, depth):
        return resolve(take(index), depth)

    def resolve(item, depth=0):
        nonlocal visited
        visited += 1
        require(
            visited <= 3 * MAX_NODES + MAX_PARTS * 16 and depth <= payload.MAX_DEPTH,
            "Multipart reconstruction bound",
        )
        if type(item) is dict and REFERENCE in item:
            require(set(item) == {REFERENCE}, "Misplaced part reference")
            return reference(item[REFERENCE], depth)
        if type(item) is dict and PAGES in item:
            require(set(item) == {PAGES}, "Misplaced page reference")
            spec = item[PAGES]
            require(
                type(spec) is dict
                and set(spec) == {"kind", "parts"}
                and spec["kind"] in ("dict", "list")
                and type(spec["parts"]) is list
                and 0 < len(spec["parts"]) <= MAX_PARTS,
                "Exact page schema",
            )
            output = {} if spec["kind"] == "dict" else []
            for index in spec["parts"]:
                page = take(index)
                require(type(page) is list and bool(page), "Nonempty ordered page required")
                if spec["kind"] == "list":
                    output.extend(resolve(child, depth + 1) for child in page)
                else:
                    for pair in page:
                        require(
                            type(pair) is list
                            and len(pair) == 2
                            and type(pair[0]) is str
                            and pair[0] not in output,
                            "Duplicate/malformed mapping member",
                        )
                        output[pair[0]] = resolve(pair[1], depth + 1)
            return output
        if type(item) is dict and payload.TOKEN in item:
            return item  # One logical raw string; _measure validates its placement.
        if type(item) is dict:
            return {key: resolve(child, depth + 1) for key, child in item.items()}
        if type(item) is list:
            return [resolve(child, depth + 1) for child in item]
        require(item is None or type(item) in (str, int, bool), "Untyped reconstructed scalar")
        return item

    result = resolve(value["root"])
    require(used == set(range(len(pieces))), "Unused multipart evidence")
    counts, _, preview = _measure(result, blobs=blobs)
    require(
        counts == value["counts"] and _seal(preview) == value["logical_sha256"],
        "Changed reconstructed counts/order/typed bits",
    )
    # The ordinary reader still authenticates every sidecar, placement, extent
    # and per-part budget. expand=False never creates binary hex copies.
    for index, (p, digest) in enumerate(paths):
        checked, part_pins = payload._read(
            p, expand=False, metadata_bytes=payload.MAX_METADATA, expected_sha256=digest
        )
        require(checked == pieces[index], "Part changed during authentication")
        expected.update(Path(pin["path"]).relative_to(folder).as_posix() for pin in part_pins)
        pins.extend(part_pins)
    require(all(not p.is_symlink() for p in folder.rglob("*")), "Linked multipart evidence")
    require(
        {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()} == expected,
        "Extra or missing multipart payload",
    )
    return result, pins, metadata, blobs


def write(path, serialized, *, label="observation"):
    """Write once; retain partial files, including possible manifest bytes.

    File existence is not a successful capture. Publication or verification
    failures propagate, and the consumer must retain the failed capture status.
    """
    path = payload._regular(path)
    folder = _folder(path)
    require(not path.exists() and not folder.exists(), "Evidence cannot be overwritten")
    _label(label)
    counts, weights, preview = _measure(serialized)
    if (
        counts["nodes"] <= payload.MAX_NODES
        and counts["ordinary_metadata_bytes"] <= payload.MAX_METADATA
    ):
        return payload.write(path, serialized)
    root, parts = _partition(serialized, weights)
    require(parts, "Oversized atomic metadata cannot be paged")
    folder.mkdir()
    rows, attempted = [], None
    try:
        for index, piece in enumerate(parts):
            attempted = f"part-{index:04d}.json"
            p = folder / attempted
            payload.write(p, piece)
            rows.append(
                dict(name=attempted, sha256=snapshot.digest(p), metadata_bytes=p.stat().st_size)
            )
        value = dict(
            kind=KIND,
            profile=PROFILE,
            label=label,
            root=root,
            parts=rows,
            counts=counts,
            logical_sha256=_seal(preview),
        )
        _, _, size, _ = _load(path, value)
        manifest_bytes = (
            len(json.dumps(value, sort_keys=True, indent=2, allow_nan=False).encode()) + 1
        )
        require(
            manifest_bytes <= payload.MAX_METADATA and size + manifest_bytes <= MAX_METADATA,
            "Aggregate manifest/part metadata bound",
        )
        snapshot.write_json(path, value)
        return files(path)
    except BaseException as primary:
        # A profile/trace hook may reject the helper CALL before its own try
        # executes. Preserve that secondary separately at this caller boundary.
        try:
            _refused(folder, primary, rows, attempted)
        except BaseException as secondary:
            try:
                _RAW_FAILURES.append((primary, secondary, "refused-boundary", rows, attempted))
            except BaseException:
                pass
        raise


def capture_writer(label, path, serialized):
    return write(path, serialized, label=label)


def _expand(value, blobs):
    """Only after global preflight; cache each same-read authenticated hex once."""
    decoded = {}

    def visit(item, key=None):
        if key == "raw_bytes_hex" and type(item) is dict and payload.TOKEN in item:
            digest = item[payload.TOKEN]
            if digest not in decoded:
                row = blobs[digest]
                path = payload._regular(row["path"])
                with path.open("rb") as stream:
                    raw = stream.read(row["size"] + 1)
                require(
                    len(raw) == row["size"] and hashlib.sha256(raw).hexdigest() == digest,
                    "Raw sidecar changed during expanded read",
                )
                decoded[digest] = raw.hex()
            return decoded[digest]
        if type(item) is dict:
            return {name: visit(child, name) for name, child in item.items()}
        if type(item) is list:
            return [visit(child) for child in item]
        return item

    return visit(value)


def _read(path, expected_sha256, *, expand):
    path = payload._regular(path)
    value, digest = payload._metadata(path, payload.MAX_METADATA, expected_sha256)
    if type(value) is not dict or value.get("kind") != KIND:
        return payload.read(path, expected_sha256=digest, expand=expand), payload.files(
            path, expected_sha256=digest
        )
    result, pins, size, blobs = _load(path, value)
    require(size + path.stat().st_size <= MAX_METADATA, "Aggregate metadata bound")
    return _expand(result, blobs) if expand else result, [
        dict(path=str(path), sha256=digest),
        *pins,
    ]


def read(path, *, expand=True, expected_sha256=None):
    require(type(expand) is bool, "Explicit binary expansion mode")
    return _read(path, expected_sha256, expand=expand)[0]


def files(path, *, expected_sha256=None):
    return _read(path, expected_sha256, expand=False)[1]
