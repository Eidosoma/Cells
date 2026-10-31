"""Synthetic byte/metadata contracts only; no scientific modules or arrays."""

import copy
import hashlib
import json
import struct
import unittest

from validation.betse import native_single_cell_prefix_compare as comparator


def digest(value):
    return hashlib.sha256(value).hexdigest()


def stream(*, position=17, gaussian=-0.0):
    state = ["MT19937", list(range(1, 625)), position, 1, gaussian]
    payload = dict(rng_id=comparator.RNG_ID, numpy_version="synthetic-1", state=state)
    return dict(
        state_json=json.dumps(state, separators=(",", ":")),
        numpy_version=payload["numpy_version"],
        identity=digest(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()),
    )


def layout(dtype="<f8", shape=None, strides=None, *, c=True, f=True):
    return dict(
        dtype=dtype,
        shape=[2] if shape is None else shape,
        strides_bytes=[8] if strides is None else strides,
        C_contiguous=c,
        F_contiguous=f,
    )


def scalar(kind="str", value="field"):
    return dict(kind=kind, value=value)


def array(name="owned-data", *, source=None, raw=None, stored_strides=None):
    source = layout() if source is None else source
    raw = struct.pack("<dd", -0.0, 1.0).hex() if raw is None else raw
    column = dict(
        __ndarray__=True,
        dtype=source["dtype"],
        shape=copy.deepcopy(source["shape"]),
        strides=source["strides_bytes"][:] if stored_strides is None else stored_strides,
        raw_bytes_hex=raw,
    )
    node = dict(
        kind="numeric_array", source_layout=source, column=name, sha256=digest(bytes.fromhex(raw))
    )
    return node, dict(name=name, values=column)


def owned_cache(tree=None, columns=None, *, finite=True):
    if tree is None:
        leaf, column = array()
        tree = dict(
            kind="dict",
            items=[
                [
                    scalar(value="caller"),
                    dict(kind="dict", items=[[scalar(value="vertices"), leaf]]),
                ],
                [
                    scalar(value="mesh"),
                    dict(kind="tuple", items=[scalar("int", 7), scalar("bool", True)]),
                ],
                [
                    scalar(value="parameters"),
                    dict(kind="float", bits=struct.pack("<d", -0.0).hex()),
                ],
            ],
        )
        columns = [column]
    text = json.dumps(tree, sort_keys=True, separators=(",", ":"))
    return dict(
        descriptor_json=text,
        columns=columns or [],
        all_finite=finite,
        identity=digest(text.encode()),
    )


def native_cache(owned):
    """A deliberately local fixture translation; not the comparator under test."""
    tree = json.loads(owned["descriptor_json"])
    columns = {}
    stored = {v["name"]: v["values"] for v in owned["columns"]}

    def translate(node):
        kind = node["kind"]
        if kind == "numeric_array":
            name = "independent-" + str(len(columns))
            columns[name] = copy.deepcopy(stored[node["column"]])
            return dict(
                type="array",
                layout=copy.deepcopy(node["source_layout"]),
                column=name,
                sha256=node["sha256"],
            )
        if kind == "dict":
            return dict(type=kind, values=[[translate(k), translate(v)] for k, v in node["items"]])
        if kind == "object_array":
            return dict(
                type=kind,
                layout=copy.deepcopy(node["source_layout"]),
                values=[translate(v) for v in node["items"]],
            )
        if "items" in node:
            return dict(type=kind, values=[translate(v) for v in node["items"]])
        return {"type": kind, **{k: copy.deepcopy(v) for k, v in node.items() if k != "kind"}}

    return dict(tree=translate(tree), columns=columns)


def inputs(cache=None):
    cache = owned_cache() if cache is None else cache
    owned = dict(
        source_completed=True,
        failure_type=None,
        failure_stage=None,
        failure_message=None,
        stages=[[name, copy.deepcopy(cache)] for name in comparator.STAGES],
        cache=copy.deepcopy(cache),
        stream_before=stream(),
        stream_after=stream(position=29),
    )
    native = dict(
        status="source_completed",
        source_error=None,
        capture_error=None,
        stages=[[name, native_cache(cache)] for name in comparator.STAGES],
        cache=native_cache(cache),
        stream_before=stream(),
        stream_after=stream(position=29),
    )
    return owned, native


def reseal(cache, tree):
    cache["descriptor_json"] = json.dumps(tree, sort_keys=True, separators=(",", ":"))
    cache["identity"] = digest(cache["descriptor_json"].encode())


def leaf(snapshot):
    return snapshot["tree"]["values"][0][1]["values"][0][1]


class PrefixComparisonTests(unittest.TestCase):
    def test_complete_exact_all_stages_and_streams_without_mutation(self):
        a, b = inputs()
        before = copy.deepcopy((a, b))
        result = comparator.compare(a, b)
        self.assertTrue(result["exact_match"])
        self.assertEqual(result["stages_compared"], 6)
        self.assertEqual(result["cache_pairs_compared"], 7)
        self.assertEqual(result["arrays_compared"], 7)
        self.assertEqual(result["streams_compared"], 2)
        self.assertEqual(result["mismatches"], [])
        self.assertEqual((a, b), before)

    def test_every_stage_numeric_change_is_found_at_semantic_path(self):
        for index, name in enumerate(comparator.STAGES):
            with self.subTest(stage=name):
                a, b = inputs()
                cache = b["stages"][index][1]
                changed = struct.pack("<dd", 0.0, 1.0).hex()
                cache["columns"]["independent-0"]["raw_bytes_hex"] = changed
                leaf(cache)["sha256"] = digest(bytes.fromhex(changed))
                result = comparator.compare(a, b)
                self.assertFalse(result["exact_match"])
                rows = [v for v in result["mismatches"] if v["path"].endswith(".raw")]
                self.assertTrue(
                    any(f'cache.{name}["caller"]["vertices"]' in v["path"] for v in rows)
                )

    def test_final_cache_must_match_last_stage_even_if_both_sides_reseal(self):
        a, b = inputs()
        tree = json.loads(a["cache"]["descriptor_json"])
        tree["items"][1][1]["items"][0]["value"] = 8
        reseal(a["cache"], tree)
        b["cache"] = native_cache(a["cache"])
        result = comparator.compare(a, b)
        self.assertFalse(result["exact_match"])
        self.assertTrue(
            any(v["path"].startswith("owned.final_vs_near_neigh") for v in result["mismatches"])
        )
        self.assertTrue(
            any(v["path"].startswith("native.final_vs_near_neigh") for v in result["mismatches"])
        )

    def test_original_layout_exact_but_C_and_K_storage_can_differ(self):
        node, col = array(
            source=layout(shape=[2, 3], strides=[8, 16], c=False, f=True),
            raw=bytes(48).hex(),
            stored_strides=[24, 8],
        )
        a, b = inputs(owned_cache(node, [col]))
        for _, cache in b["stages"]:
            cache["columns"]["independent-0"]["strides"] = [8, 16]
        b["cache"]["columns"]["independent-0"]["strides"] = [8, 16]
        self.assertTrue(comparator.compare(a, b)["exact_match"])
        b["stages"][2][1]["tree"]["layout"] = layout(shape=[2, 3], strides=[24, 8], c=True, f=False)
        result = comparator.compare(a, b)
        self.assertFalse(result["exact_match"])
        self.assertTrue(any("layout.strides_bytes" in v["path"] for v in result["mismatches"]))

    def test_negative_and_broadcast_original_layouts_are_preserved(self):
        for strides in ([-8], [0], [16]):
            with self.subTest(strides=strides):
                node, col = array(
                    source=layout(strides=strides, c=False, f=False), stored_strides=[8]
                )
                self.assertTrue(
                    comparator.compare(*inputs(owned_cache(node, [col])))["exact_match"]
                )

    def test_dense_permuted_storage_is_valid_without_array_hydration(self):
        source = layout(shape=[2, 3, 4], strides=[24, 8, 48], c=False, f=False)
        node, col = array(source=source, raw=bytes(192).hex(), stored_strides=[96, 32, 8])
        a, b = inputs(owned_cache(node, [col]))
        for _, cache in b["stages"]:
            cache["columns"]["independent-0"]["strides"] = [24, 8, 48]
        b["cache"]["columns"]["independent-0"]["strides"] = [24, 8, 48]
        self.assertTrue(comparator.compare(a, b)["exact_match"])

    def test_object_array_nesting_and_leaf_count(self):
        n, c = array()
        tree = dict(
            kind="object_array",
            source_layout=layout("|O", [2], [struct.calcsize("P")]),
            items=[n, dict(kind="list", items=[scalar("int", 4)])],
        )
        a, b = inputs(owned_cache(tree, [c]))
        self.assertTrue(comparator.compare(a, b)["exact_match"])
        b["stages"][1][1]["tree"]["values"][1]["type"] = "tuple"
        self.assertFalse(comparator.compare(a, b)["exact_match"])
        a, b = inputs(owned_cache(tree, [c]))
        b["cache"]["tree"]["values"].pop()
        with self.assertRaisesRegex(ValueError, "leaf count"):
            comparator.compare(a, b)

    def test_dict_order_and_exact_scalar_types_are_not_normalized(self):
        a, b = inputs()
        b["stages"][1][1]["tree"]["values"].reverse()
        self.assertFalse(comparator.compare(a, b)["exact_match"])
        a, b = inputs()
        target = b["stages"][1][1]["tree"]["values"][1][1]["values"][1]
        target.update(type="int", value=1)
        self.assertFalse(comparator.compare(a, b)["exact_match"])

    def test_nan_payload_signed_zero_and_complex_bits_remain_exact(self):
        for dtype, raw in (
            ("<f8", "010000000000f87f"),
            (">f8", "7ff8000000000001"),
            ("<c16", "010000000000f87f0000000000000080"),
        ):
            with self.subTest(dtype=dtype):
                size = len(bytes.fromhex(raw))
                n, c = array(source=layout(dtype, [], []), raw=raw)
                a, b = inputs(owned_cache(n, [c], finite=False))
                self.assertTrue(comparator.compare(a, b)["exact_match"])
                self.assertEqual(size, int(dtype[2:]))
                changed = raw[:-2] + f"{int(raw[-2:], 16) ^ 1:02x}"
                b["stages"][0][1]["columns"]["independent-0"]["raw_bytes_hex"] = changed
                b["stages"][0][1]["tree"]["sha256"] = digest(bytes.fromhex(changed))
                self.assertFalse(comparator.compare(a, b)["exact_match"])

    def test_python_float_and_numpy_scalar_bits_are_distinct(self):
        for node in (
            dict(kind="float", bits="010000000000f87f"),
            dict(kind="numpy_scalar", dtype="<f8", bits="010000000000f87f"),
        ):
            a, b = inputs(owned_cache(node, finite=False))
            self.assertTrue(comparator.compare(a, b)["exact_match"])
            b["stages"][3][1]["tree"]["bits"] = "020000000000f87f"
            self.assertFalse(comparator.compare(a, b)["exact_match"])

    def test_empty_arrays_singletons_and_scalars(self):
        for shape, strides, raw in (
            ([0, 3], [24, 8], ""),
            ([1, 2], [999, 8], bytes(16).hex()),
            ([], [], bytes(8).hex()),
        ):
            with self.subTest(shape=shape):
                n, c = array(source=layout(shape=shape, strides=strides), raw=raw)
                self.assertTrue(comparator.compare(*inputs(owned_cache(n, [c])))["exact_match"])

    def test_all_supported_numeric_dtype_widths(self):
        dtypes = ["|b1", "|u1", "|i1"] + [
            end + kind + str(size)
            for end in "<>"
            for kind, sizes in (
                ("i", (2, 4, 8)),
                ("u", (2, 4, 8)),
                ("f", (2, 4, 8)),
                ("c", (8, 16)),
            )
            for size in sizes
        ]
        for dtype in dtypes:
            with self.subTest(dtype=dtype):
                size = int(dtype[2:])
                n, c = array(source=layout(dtype, [2], [size]), raw=bytes(size * 2).hex())
                self.assertTrue(comparator.compare(*inputs(owned_cache(n, [c])))["exact_match"])

    def test_missing_unused_and_duplicate_column_references_both_sides(self):
        for side in ("owned", "native"):
            for fault in ("missing", "unused", "duplicate-reference", "duplicate-name"):
                if side == "native" and fault == "duplicate-name":
                    continue
                with self.subTest(side=side, fault=fault):
                    a, b = inputs()
                    cache = a["cache"] if side == "owned" else b["cache"]
                    if fault == "missing":
                        cache["columns"].clear()
                    elif fault in ("unused", "duplicate-name"):
                        if side == "owned":
                            extra = copy.deepcopy(cache["columns"][0])
                            if fault == "unused":
                                extra["name"] = "unused"
                            cache["columns"].append(extra)
                        else:
                            cache["columns"]["unused"] = copy.deepcopy(
                                next(iter(cache["columns"].values()))
                            )
                    elif side == "owned":
                        tree = json.loads(cache["descriptor_json"])
                        tree["items"].append(copy.deepcopy(tree["items"][0]))
                        reseal(cache, tree)
                    else:
                        cache["tree"]["values"].append(copy.deepcopy(cache["tree"]["values"][0]))
                    with self.assertRaisesRegex(ValueError, "column"):
                        comparator.compare(a, b)

    def test_malformed_column_headers_bytes_and_layout_refused(self):
        mutations = {
            "marker": lambda c: c.update(__ndarray__=1),
            "object": lambda c: c.update(dtype="|O"),
            "implicit endian": lambda c: c.update(dtype="f8"),
            "unsupported float": lambda c: c.update(dtype="<f16"),
            "invalid integer width": lambda c: c.update(dtype="<i3"),
            "bool dimension": lambda c: c.update(shape=[True]),
            "negative dimension": lambda c: c.update(shape=[-1]),
            "rank": lambda c: c.update(shape=[1] * 65),
            "element bound": lambda c: c.update(shape=[comparator.MAX_ELEMENTS + 1]),
            "stride rank": lambda c: c.update(strides=[]),
            "bool stride": lambda c: c.update(strides=[True]),
            "overlap": lambda c: c.update(strides=[0]),
            "negative copied stride": lambda c: c.update(strides=[-8]),
            "wrong shape": lambda c: c.update(shape=[1, 2], strides=[16, 8]),
            "short bytes": lambda c: c.update(raw_bytes_hex="00"),
            "odd hex": lambda c: c.update(raw_bytes_hex="0"),
            "hex whitespace": lambda c: c.update(raw_bytes_hex=" " * 32),
            "invalid hex": lambda c: c.update(raw_bytes_hex="zz" * 16),
            "uppercase hex": lambda c: c.update(raw_bytes_hex="AA" * 16),
            "extra field": lambda c: c.update(unchecked=True),
        }
        for side in ("owned", "native"):
            for fault, mutate in mutations.items():
                with self.subTest(side=side, fault=fault):
                    a, b = inputs()
                    column = (
                        a["cache"]["columns"][0]["values"]
                        if side == "owned"
                        else b["cache"]["columns"]["independent-0"]
                    )
                    mutate(column)
                    with self.assertRaises(ValueError):
                        comparator.compare(a, b)

    def test_descriptor_hash_and_byte_hash_are_independently_required(self):
        a, b = inputs()
        a["cache"]["identity"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "descriptor hash"):
            comparator.compare(a, b)
        a, b = inputs()
        b["cache"]["columns"]["independent-0"]["raw_bytes_hex"] = bytes(16).hex()
        with self.assertRaisesRegex(ValueError, "byte hash"):
            comparator.compare(a, b)
        a, b = inputs()
        leaf(b["cache"])["sha256"] = True
        with self.assertRaisesRegex(ValueError, "SHA256"):
            comparator.compare(a, b)

    def test_source_layout_flags_dtype_shape_and_overflow_refused(self):
        for fault in ("contiguous", "dtype", "shape", "strides", "overflow", "bool flag"):
            with self.subTest(fault=fault):
                a, b = inputs()
                target = leaf(b["cache"])["layout"]
                if fault == "contiguous":
                    target["C_contiguous"] = False
                elif fault == "dtype":
                    target["dtype"] = "<i8"
                elif fault == "shape":
                    target["shape"] = [1]
                elif fault == "strides":
                    target["strides_bytes"] = [8, 8]
                elif fault == "overflow":
                    target.update(
                        shape=[3], strides_bytes=[2**62], C_contiguous=False, F_contiguous=False
                    )
                else:
                    target["C_contiguous"] = 1
                with self.assertRaises(ValueError):
                    comparator.compare(a, b)

    def test_false_finite_flag_and_invalid_scalar_widths_refused(self):
        for node, finite in (
            (dict(kind="float", bits="010000000000f87f"), True),
            (dict(kind="float", bits="00"), False),
            (dict(kind="numpy_scalar", dtype="<f8", bits="00"), True),
            (scalar("int", True), True),
        ):
            a, b = inputs(owned_cache(node, finite=finite))
            with self.assertRaises(ValueError):
                comparator.compare(a, b)

    def test_malformed_node_schemas_cycles_and_json_duplicates(self):
        a, b = inputs()
        a["cache"]["descriptor_json"] = '{"kind":"int","kind":"int","value":3}'
        a["cache"]["identity"] = digest(a["cache"]["descriptor_json"].encode())
        with self.assertRaisesRegex(ValueError, "duplicate JSON"):
            comparator.compare(a, b)
        for fault in ("unknown", "wrong tag", "cycle", "unhashable", "extra"):
            with self.subTest(fault=fault):
                a, b = inputs()
                tree = b["cache"]["tree"]
                if fault == "unknown":
                    tree["type"] = "untrusted"
                elif fault == "wrong tag":
                    tree["type"] = []
                elif fault == "cycle":
                    tree["values"][0][1] = tree
                elif fault == "unhashable":
                    tree["values"][0][0] = dict(type="list", values=[])
                else:
                    tree["unvalidated"] = 1
                with self.assertRaises(ValueError):
                    comparator.compare(a, b)

    def test_stage_roster_missing_duplicate_reordered_refused(self):
        for side in ("owned", "native"):
            for fault in ("missing", "duplicate", "reordered", "tuple row"):
                with self.subTest(side=side, fault=fault):
                    a, b = inputs()
                    stages = (a if side == "owned" else b)["stages"]
                    if fault == "missing":
                        stages.pop()
                    elif fault == "duplicate":
                        stages[1][0] = stages[0][0]
                    elif fault == "reordered":
                        stages.reverse()
                    else:
                        stages[0] = tuple(stages[0])
                    with self.assertRaisesRegex(ValueError, "stage"):
                        comparator.compare(a, b)

    def test_false_completed_markers_and_source_capture_errors_never_pass(self):
        mutations = (
            ("owned", "source_completed", False),
            ("owned", "failure_type", "OriginalFailure"),
            ("owned", "failure_stage", "cellMatrices"),
            ("owned", "failure_message", "failed"),
            ("native", "status", "source_failed"),
            ("native", "source_error", {"type": "NativeFailure"}),
            ("native", "capture_error", {"type": "CaptureFailure"}),
            ("native", "source_error", False),
        )
        for side, key, value in mutations:
            with self.subTest(side=side, key=key, value=value):
                a, b = inputs()
                (a if side == "owned" else b)[key] = value
                result = comparator.compare(a, b)
                self.assertFalse(result["exact_match"])
                self.assertEqual(result["stages_compared"], 0)
                self.assertEqual(result["mismatches"][0]["path"], side + "." + key)
        for side, key, value in (("owned", "source_completed", 1), ("native", "status", True)):
            a, b = inputs()
            (a if side == "owned" else b)[key] = value
            with self.assertRaises(ValueError):
                comparator.compare(a, b)

    def test_missing_success_error_fields_are_not_defaulted(self):
        for side, key in (
            ("owned", "source_completed"),
            ("owned", "failure_message"),
            ("native", "source_error"),
            ("native", "capture_error"),
        ):
            a, b = inputs()
            del (a if side == "owned" else b)[key]
            with self.assertRaises(ValueError):
                comparator.compare(a, b)

    def test_both_MT_boundaries_compare_words_position_and_gaussian_bits(self):
        for key in ("stream_before", "stream_after"):
            for replacement in (
                stream(position=30),
                stream(position=17 if key == "stream_before" else 29, gaussian=0.0),
            ):
                a, b = inputs()
                b[key] = replacement
                result = comparator.compare(a, b)
                self.assertFalse(result["exact_match"])
                self.assertTrue(any(v["path"].startswith(key) for v in result["mismatches"]))

    def test_stream_schema_hash_complete_words_types_and_text_refused(self):
        for fault in (
            "hash",
            "bool word",
            "missing word",
            "all zero",
            "position",
            "cache",
            "nan",
            "integer gaussian",
            "whitespace",
            "manifest",
        ):
            with self.subTest(fault=fault):
                a, b = inputs()
                value = b["stream_before"]
                state = json.loads(value["state_json"])
                if fault == "hash":
                    value["identity"] = "0" * 64
                elif fault == "bool word":
                    state[1][0] = True
                elif fault == "missing word":
                    state[1].pop()
                elif fault == "all zero":
                    state[1] = [0] * 624
                elif fault == "position":
                    state[2] = 625
                elif fault == "cache":
                    state[3] = True
                elif fault == "nan":
                    state[4] = float("nan")
                elif fault == "integer gaussian":
                    state[4] = 0
                elif fault == "manifest":
                    value["state"] = state
                if fault == "whitespace":
                    value["state_json"] = json.dumps(state)
                else:
                    value["state_json"] = json.dumps(state, separators=(",", ":"))
                with self.assertRaises(ValueError):
                    comparator.compare(a, b)


if __name__ == "__main__":
    unittest.main()
