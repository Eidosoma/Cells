"""Strict, allocation-free array comparison of two saved single-cell prefixes.

Only metadata and bytes are inspected. No arrays, RNGs or source owners are
restored. The original source layout matters; storage-column labels and copied
column strides do not (the two serializers copy in C and K order respectively).
"""

import hashlib
import json
import math
import re
import struct

STAGES = ("before", "cellVerts", "cellMatrices", "cell_vols", "mem_processing", "near_neigh")
RNG_ID = "numpy_mt19937_legacy_state_with_gaussian_cache@1"
MAX_ELEMENTS = 262144
MAX_NODES = 262144
MAX_DEPTH = 32
MAX_BYTES = 64 * 1024 * 1024
_HEX = re.compile(r"[0-9a-f]*\Z")
_DTYPE = re.compile(r"(?:\|[biu]1|[<>][iu][248]|[<>]f[248]|[<>]c(?:8|16))\Z")


def _bad(path, message):
    raise ValueError(f"{path}: {message}")


def _keys(value, expected, path):
    if type(value) is not dict or set(value) != set(expected):
        _bad(path, "require exactly " + ", ".join(sorted(expected)))


def _required(value, names, path):
    if type(value) is not dict or not set(names) <= set(value):
        _bad(path, "missing required fields: " + ", ".join(names))


def _json(text, path):
    if type(text) is not str or len(text) > MAX_BYTES:
        _bad(path, "require bounded JSON text")

    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                _bad(path, "duplicate JSON key " + key)
            result[key] = value
        return result

    def constant(value):
        _bad(path, "nonfinite JSON literal " + value)

    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except (RecursionError, json.JSONDecodeError) as error:
        _bad(path, "malformed JSON: " + str(error))


def _dtype(value, path, *, objects=False):
    if objects and value == "|O":
        # Object pointers are not serialized; only their source layout is kept.
        return "O", struct.calcsize("P"), "little"
    if type(value) is not str or not _DTYPE.fullmatch(value):
        _bad(path, "unsupported explicit numeric dtype")
    return value[1], int(value[2:]), "big" if value[0] == ">" else "little"


def _shape(value, path):
    if type(value) is not list or len(value) > 64:
        _bad(path, "require a dimension list of rank at most 64")
    if any(type(v) is not int or not 0 <= v < 2**63 for v in value):
        _bad(path, "dimensions must be nonnegative int64 values, not bools")
    size = math.prod(value)
    if size > MAX_ELEMENTS:
        _bad(path, "array exceeds the source element bound")
    return size


def _strides(value, shape, itemsize, path):
    if type(value) is not list or len(value) != len(shape):
        _bad(path, "stride rank differs from shape")
    if any(type(v) is not int or not -(2**63) <= v < 2**63 for v in value):
        _bad(path, "strides must be signed int64 byte counts, not bools")
    if (
        0 not in shape
        and sum((n - 1) * abs(s) for n, s in zip(shape, value, strict=True)) + itemsize >= 2**63
    ):
        _bad(path, "source layout byte span overflows int64")


def _contiguous(shape, strides, itemsize, *, reverse):
    if 0 in shape:
        return True
    axes = list(zip(shape, strides, strict=True))
    if reverse:
        axes.reverse()
    expected = itemsize
    for size, stride in axes:
        if size > 1:
            if stride != expected:
                return False
            expected *= size
    return True


def _layout(value, path, *, objects=False):
    _keys(value, ("dtype", "shape", "strides_bytes", "C_contiguous", "F_contiguous"), path)
    kind, itemsize, _ = _dtype(value["dtype"], path + ".dtype", objects=objects)
    if objects and kind != "O":
        _bad(path, "object array requires the object dtype")
    size = _shape(value["shape"], path + ".shape")
    _strides(value["strides_bytes"], value["shape"], itemsize, path + ".strides_bytes")
    for name, reverse in (("C_contiguous", True), ("F_contiguous", False)):
        if type(value[name]) is not bool or value[name] != _contiguous(
            value["shape"], value["strides_bytes"], itemsize, reverse=reverse
        ):
            _bad(path + "." + name, "contiguity flag disagrees with the source layout")
    return size


def _hex_bytes(value, size, path):
    if type(value) is not str or len(value) != size * 2 or not _HEX.fullmatch(value):
        _bad(path, "require exact-length lowercase byte hex")
    return bytes.fromhex(value)


def _digest(value, path):
    if type(value) is not str or len(value) != 64 or not _HEX.fullmatch(value):
        _bad(path, "require a lowercase SHA256 digest")


def _finite(raw, kind, itemsize, byteorder):
    if kind not in "fc":
        return True
    width = itemsize // 2 if kind == "c" else itemsize
    fraction, exponent = {2: (10, 5), 4: (23, 8), 8: (52, 11)}[width]
    mask = (1 << exponent) - 1
    return all(
        (int.from_bytes(raw[i : i + width], byteorder) >> fraction) & mask != mask
        for i in range(0, len(raw), width)
    )


def _column(value, path):
    _keys(value, ("__ndarray__", "dtype", "shape", "strides", "raw_bytes_hex"), path)
    if value["__ndarray__"] is not True:
        _bad(path, "array marker must be true")
    kind, itemsize, byteorder = _dtype(value["dtype"], path + ".dtype")
    size = _shape(value["shape"], path + ".shape")
    _strides(value["strides"], value["shape"], itemsize, path + ".strides")
    # These are copied storage columns, not arbitrary views. K-order copies can
    # have a dense axis permutation which is neither C nor F contiguous.
    expected = itemsize
    if size:
        for stride, count in sorted(
            (s, n) for n, s in zip(value["shape"], value["strides"], strict=True) if n > 1
        ):
            if stride != expected:
                _bad(path + ".strides", "copied column is not a dense positive layout")
            expected *= count
    raw = _hex_bytes(value["raw_bytes_hex"], size * itemsize, path + ".raw_bytes_hex")
    return hashlib.sha256(raw).hexdigest(), _finite(raw, kind, itemsize, byteorder), len(raw)


class _Cache:
    def __init__(self, value, path, owned):
        self.path, self.owned = path, owned
        self.nodes, self.arrays, self.byte_count = 0, 0, 0
        self.finite, self.active, self.seen = True, set(), set()
        self.columns = {}
        if owned:
            _keys(value, ("descriptor_json", "columns", "all_finite", "identity"), path)
            _digest(value["identity"], path + ".identity")
            tree = _json(value["descriptor_json"], path + ".descriptor_json")
            if hashlib.sha256(value["descriptor_json"].encode()).hexdigest() != value["identity"]:
                _bad(path + ".identity", "descriptor hash mismatch")
            if type(value["all_finite"]) is not bool or type(value["columns"]) is not list:
                _bad(path, "require boolean all_finite and a column list")
            for i, row in enumerate(value["columns"]):
                _keys(row, ("name", "values"), f"{path}.columns[{i}]")
                name = row["name"]
                if type(name) is not str or not name or name in self.columns:
                    _bad(path + ".columns", "invalid or duplicate storage column name")
                self.columns[name] = row["values"]
        else:
            _keys(value, ("tree", "columns"), path)
            tree = value["tree"]
            if type(value["columns"]) is not dict:
                _bad(path + ".columns", "require the complete column mapping")
            self.columns = value["columns"]
            if any(type(n) is not str or not n for n in self.columns):
                _bad(path + ".columns", "invalid storage column name")
        self.tree = self.visit(tree, path, 0)
        if self.seen != set(self.columns):
            _bad(
                path + ".columns", "unused columns: " + repr(sorted(set(self.columns) - self.seen))
            )
        if owned and value["all_finite"] != self.finite:
            _bad(path + ".all_finite", "flag disagrees with the complete scalar/array bits")

    def visit(self, node, path, depth):
        self.nodes += 1
        if depth > MAX_DEPTH or self.nodes > MAX_NODES:
            _bad(path, "source tree depth/node bound exceeded")
        if type(node) is not dict or id(node) in self.active:
            _bad(path, "require an acyclic typed node")
        self.active.add(id(node))
        try:
            return self._visit(node, path, depth)
        finally:
            self.active.remove(id(node))

    def _visit(self, node, path, depth):
        tag, values, layout = (
            ("kind", "items", "source_layout") if self.owned else ("type", "values", "layout")
        )
        kind = node.get(tag)
        if type(kind) is not str:
            _bad(path, "typed node requires a string tag")
        if kind == ("numeric_array" if self.owned else "array"):
            _keys(node, (tag, layout, "column", "sha256"), path)
            _layout(node[layout], path + ".layout")
            name = node["column"]
            if type(name) is not str or name not in self.columns or name in self.seen:
                _bad(path + ".column", "missing or multiply referenced column")
            self.seen.add(name)
            column = self.columns[name]
            digest, finite, size = _column(column, path + ".column[" + repr(name) + "]")
            if column["dtype"] != node[layout]["dtype"] or column["shape"] != node[layout]["shape"]:
                _bad(path, "storage column dtype/shape differs from source layout")
            _digest(node["sha256"], path + ".sha256")
            if digest != node["sha256"]:
                _bad(path + ".sha256", "numeric byte hash mismatch")
            self.arrays += 1
            self.byte_count += size
            if self.byte_count > MAX_BYTES:
                _bad(path, "cache numeric bytes exceed the metadata bound")
            self.finite = self.finite and finite
            return dict(
                type="array", layout=node[layout], sha256=digest, raw=column["raw_bytes_hex"]
            )
        if kind in ("dict", "object_array", "list", "tuple", "set", "frozenset"):
            fields = (tag, layout, values) if kind == "object_array" else (tag, values)
            _keys(node, fields, path)
            children = node[values]
            if type(children) is not list:
                _bad(path, "require an ordered child list")
            result = dict(type=kind, items=[])
            if kind == "object_array":
                count = _layout(node[layout], path + ".layout", objects=True)
                if len(children) != count:
                    _bad(path, "object-array leaf count differs from shape")
                result["layout"] = node[layout]
            for i, child in enumerate(children):
                at = f"{path}.items[{i}]"
                if kind == "dict":
                    if type(child) is not list or len(child) != 2:
                        _bad(at, "require one ordered key/value pair")
                    key = self.visit(child[0], at + ".key", depth + 1)
                    if not _hashable(key):
                        _bad(at + ".key", "unhashable dictionary key")
                    value = self.visit(child[1], at + ".value", depth + 1)
                    result["items"].append([key, value])
                else:
                    item = self.visit(child, at, depth + 1)
                    if kind in ("set", "frozenset") and not _hashable(item):
                        _bad(at, "unhashable set member")
                    result["items"].append(item)
            return result
        if kind in ("float", "numpy_scalar"):
            _keys(node, (tag, "bits", "dtype") if kind == "numpy_scalar" else (tag, "bits"), path)
            scalar, width, order = (
                _dtype(node["dtype"], path + ".dtype")
                if kind == "numpy_scalar"
                else ("f", 8, "little")
            )
            raw = _hex_bytes(node["bits"], width, path + ".bits")
            self.finite = self.finite and _finite(raw, scalar, width, order)
            result = dict(type=kind, bits=node["bits"])
            if kind == "numpy_scalar":
                result["dtype"] = node["dtype"]
            return result
        types = {"NoneType": type(None), "str": str, "int": int, "bool": bool}
        if kind not in types:
            _bad(path, "unknown typed node")
        _keys(node, (tag, "value"), path)
        if type(node["value"]) is not types[kind]:
            _bad(path, "scalar value has the wrong exact Python type")
        return dict(type=kind, value=node["value"])


def _hashable(node):
    if node["type"] in ("tuple", "frozenset"):
        return all(_hashable(v) for v in node["items"])
    return node["type"] in ("NoneType", "str", "int", "bool", "float", "numpy_scalar")


def _stream(value, path):
    _keys(value, ("state_json", "numpy_version", "identity"), path)
    state = _json(value["state_json"], path + ".state_json")
    version = value["numpy_version"]
    if type(version) is not str or not version or len(version) > 128:
        _bad(path, "require the recorded NumPy version")
    if type(state) is not list or len(state) != 5 or state[0] != "MT19937":
        _bad(path, "require the complete MT19937 state")
    _, words, position, cached, gaussian = state
    if (
        type(words) is not list
        or len(words) != 624
        or any(type(v) is not int or not 0 <= v < 2**32 for v in words)
        or not any(words)
        or type(position) is not int
        or not 0 <= position <= 624
        or type(cached) is not int
        or cached not in (0, 1)
        or type(gaussian) is not float
        or not math.isfinite(gaussian)
    ):
        _bad(path, "invalid MT words, position or Gaussian cache")
    if json.dumps(state, separators=(",", ":"), allow_nan=False) != value["state_json"]:
        _bad(path, "state_json is not the exact canonical stream representation")
    _digest(value["identity"], path + ".identity")
    payload = dict(rng_id=RNG_ID, numpy_version=version, state=state)
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    if digest != value["identity"]:
        _bad(path + ".identity", "stream hash mismatch")
    return dict(
        numpy_version=version,
        identity=digest,
        algorithm=state[0],
        words=words,
        position=position,
        has_gauss=cached,
        gaussian_bits=struct.pack("<d", gaussian).hex(),
    )


def _brief(value):
    if type(value) is str and len(value) > 160:
        return dict(length=len(value), sha256=hashlib.sha256(value.encode()).hexdigest())
    if type(value) in (str, int, bool, type(None)):
        return value
    return value


def _difference(left, right, path, differences):
    """Keep each differing field's path; large byte strings retain hashes/lengths."""
    if type(left) is not type(right):
        differences.append(dict(path=path, reason="type", left=_brief(left), right=_brief(right)))
        return
    if type(left) is dict:
        if left.get("type") == right.get("type") == "dict":
            a, b = left["items"], right["items"]
            if len(a) != len(b):
                differences.append(dict(path=path + ".length", left=len(a), right=len(b)))
            for i, ((ak, av), (bk, bv)) in enumerate(zip(a, b, strict=False)):
                _difference(ak, bk, f"{path}.keys[{i}]", differences)
                at = (
                    path + "[" + json.dumps(ak["value"]) + "]"
                    if ak == bk and ak["type"] == "str"
                    else f"{path}.items[{i}].value"
                )
                _difference(av, bv, at, differences)
            return
        if set(left) != set(right):
            differences.append(dict(path=path + ".fields", left=list(left), right=list(right)))
        for key in left:
            if key in right:
                _difference(left[key], right[key], path + "." + key, differences)
        return
    if type(left) is list:
        if len(left) != len(right):
            differences.append(dict(path=path + ".length", left=len(left), right=len(right)))
        for i, (a, b) in enumerate(zip(left, right, strict=False)):
            _difference(a, b, f"{path}[{i}]", differences)
        return
    if left != right:
        row = dict(path=path, left=_brief(left), right=_brief(right))
        if path.endswith(".raw"):
            i = next(
                (
                    i
                    for i in range(0, min(len(left), len(right)), 2)
                    if left[i : i + 2] != right[i : i + 2]
                ),
                min(len(left), len(right)),
            )
            row.update(
                first_different_byte=i // 2, left_byte=left[i : i + 2], right_byte=right[i : i + 2]
            )
        differences.append(row)


def compare(owned_trial: dict, native: dict) -> dict:
    """Compare complete six-stage evidence; malformed metadata raises ValueError.

    Error/noncompleted source markers return a refusal with zero compared stages.
    Otherwise every stage, final cache and both authenticated MT streams must be
    exact. Mismatch values are retained, or hash/length/first-byte evidence for
    large buffers; the caller retains the complete input archives.
    """
    _required(
        owned_trial,
        ("source_completed", "failure_stage", "failure_type", "failure_message"),
        "owned",
    )
    _required(native, ("status", "source_error", "capture_error"), "native")
    if type(owned_trial["source_completed"]) is not bool or type(native["status"]) is not str:
        _bad("source markers", "require exact boolean completion and string status")
    differences = []
    for side, key, expected in (
        ("owned", "source_completed", True),
        ("owned", "failure_stage", None),
        ("owned", "failure_type", None),
        ("owned", "failure_message", None),
        ("native", "status", "source_completed"),
        ("native", "source_error", None),
        ("native", "capture_error", None),
    ):
        value = (owned_trial if side == "owned" else native)[key]
        if value != expected:
            differences.append(
                dict(
                    path=side + "." + key,
                    reason="source_not_completed",
                    expected=expected,
                    observed=value,
                )
            )
    result = dict(
        kind="cells.single_cell_saved_prefix_exact_comparison@1",
        exact_match=False,
        stages_compared=0,
        cache_pairs_compared=0,
        arrays_compared=0,
        streams_compared=0,
        mismatches=differences,
    )
    if differences:
        return result
    for side, value in (("owned", owned_trial), ("native", native)):
        _required(value, ("stages", "cache", "stream_before", "stream_after"), side)
        stages = value["stages"]
        if type(stages) is not list or len(stages) != len(STAGES):
            _bad(side + ".stages", "require all six ordered stages")
        for expected, row in zip(STAGES, stages, strict=True):
            if type(row) is not list or len(row) != 2 or row[0] != expected:
                _bad(side + ".stages", "missing, duplicated or reordered stage " + expected)
    final_stage = {}
    for i, name in enumerate((*STAGES, "final")):
        a = owned_trial["stages"][i][1] if i < len(STAGES) else owned_trial["cache"]
        b = native["stages"][i][1] if i < len(STAGES) else native["cache"]
        left, right = _Cache(a, "owned." + name, True), _Cache(b, "native." + name, False)
        _difference(left.tree, right.tree, "cache." + name, differences)
        result["cache_pairs_compared"] += 1
        result["arrays_compared"] += left.arrays
        if name == STAGES[-1]:
            final_stage = dict(owned=left.tree, native=right.tree)
        if name == "final":
            _difference(final_stage["owned"], left.tree, "owned.final_vs_near_neigh", differences)
            _difference(
                final_stage["native"], right.tree, "native.final_vs_near_neigh", differences
            )
        else:
            result["stages_compared"] += 1
    for name in ("stream_before", "stream_after"):
        _difference(
            _stream(owned_trial[name], "owned." + name),
            _stream(native[name], "native." + name),
            name,
            differences,
        )
        result["streams_compared"] += 1
    result["exact_match"] = not differences
    return result
