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


def ecm_inputs(cache=None):
    owned, native = inputs(cache)
    owned["identity"] = digest(b"synthetic geometry trial")
    before = copy.deepcopy(owned["cache"])
    tree = json.loads(before["descriptor_json"])
    tree["items"].append([scalar(value="grid"), scalar("NoneType", None)])
    reseal(before, tree)
    final = copy.deepcopy(before)
    leaf, column = array("owned-grid")
    final["columns"].append(column)
    tree["items"][-1][1] = dict(kind="dict", items=[[scalar(value="cents_X"), leaf]])
    reseal(final, tree)
    ecm = dict(
        source_completed=True,
        failure_stage=None,
        failure_type=None,
        failure_message=None,
        parent_identity=owned["identity"],
        before=before,
        cache=final,
        stream_before=copy.deepcopy(owned["stream_after"]),
        stream_after=copy.deepcopy(owned["stream_after"]),
    )
    native.update(
        stop_after="makeECM",
        ecm=dict(
            before=native_cache(before),
            cache=native_cache(final),
            stream_before=copy.deepcopy(ecm["stream_before"]),
            stream_after=copy.deepcopy(ecm["stream_after"]),
        ),
    )
    return owned, ecm, native


class EcmComparisonTests(unittest.TestCase):
    def test_exact_geometry_and_ecm_with_handoffs_without_mutation(self):
        values = ecm_inputs()
        before = copy.deepcopy(values)
        result = comparator.compare_ecm(*values)
        self.assertTrue(result["exact_match"])
        self.assertEqual(result["cache_pairs_compared"], 9)
        self.assertEqual(result["ecm_cache_pairs_compared"], 2)
        self.assertEqual(result["arrays_compared"], 10)
        self.assertEqual(result["streams_compared"], 4)
        self.assertEqual(result["handoff_checks"], 4)
        self.assertEqual(result["lineage_checks"], 1)
        self.assertEqual(values, before)

    def test_final_grid_numeric_bits_are_compared(self):
        geometry, ecm, native = ecm_inputs()
        cache = native["ecm"]["cache"]
        changed = struct.pack("<dd", 0.0, 1.0).hex()
        cache["columns"]["independent-1"]["raw_bytes_hex"] = changed
        cache["tree"]["values"][-1][1]["values"][0][1]["sha256"] = digest(bytes.fromhex(changed))
        result = comparator.compare_ecm(geometry, ecm, native)
        self.assertFalse(result["exact_match"])
        self.assertTrue(
            any(row["path"] == 'ecm.cache["grid"]["cents_X"].raw' for row in result["mismatches"])
        )

    def test_equal_resealed_before_caches_cannot_change_geometry_handoff(self):
        geometry, ecm, native = ecm_inputs()
        tree = json.loads(ecm["before"]["descriptor_json"])
        tree["items"][2][1]["bits"] = struct.pack("<d", 1.0).hex()
        reseal(ecm["before"], tree)
        native["ecm"]["before"] = native_cache(ecm["before"])
        result = comparator.compare_ecm(geometry, ecm, native)
        self.assertFalse(result["exact_match"])
        self.assertEqual(
            {row["path"] for row in result["mismatches"]},
            {
                'owned.ecm.geometry_handoff["parameters"].bits',
                'native.ecm.geometry_handoff["parameters"].bits',
            },
        )

    def test_equal_resealed_MT_records_cannot_change_handoff(self):
        geometry, ecm, native = ecm_inputs()
        ecm["stream_before"] = stream(position=30)
        native["ecm"]["stream_before"] = stream(position=30)
        result = comparator.compare_ecm(geometry, ecm, native)
        self.assertFalse(result["exact_match"])
        self.assertTrue(any("owned.ecm.rng_handoff" in r["path"] for r in result["mismatches"]))
        self.assertTrue(any("native.ecm.rng_handoff" in r["path"] for r in result["mismatches"]))

    def test_final_MT_record_is_compared(self):
        geometry, ecm, native = ecm_inputs()
        native["ecm"]["stream_after"] = stream(position=31)
        result = comparator.compare_ecm(geometry, ecm, native)
        self.assertFalse(result["exact_match"])
        self.assertTrue(any("ecm.stream_after" in r["path"] for r in result["mismatches"]))

    def test_foreign_geometry_trial_cannot_supply_parent_identity(self):
        geometry, ecm, native = ecm_inputs()
        ecm["parent_identity"] = digest(b"different complete trial")
        result = comparator.compare_ecm(geometry, ecm, native)
        self.assertFalse(result["exact_match"])
        self.assertEqual(result["mismatches"][0]["path"], "owned.ecm.parent_identity")

    def test_each_ECM_failure_marker_prevents_comparison(self):
        for key, value in (
            ("source_completed", False),
            ("failure_stage", "cell_grid"),
            ("failure_type", "OriginalError"),
            ("failure_message", "retained native failure"),
        ):
            with self.subTest(key=key):
                geometry, ecm, native = ecm_inputs()
                ecm[key] = value
                result = comparator.compare_ecm(geometry, ecm, native)
                self.assertFalse(result["exact_match"])
                self.assertEqual(result["ecm_cache_pairs_compared"], 0)

    def test_whole_native_failure_never_credits_completed_geometry(self):
        geometry, ecm, native = ecm_inputs()
        native.update(status="failed", source_error={"message": "original grid failure"})
        del native["ecm"]
        result = comparator.compare_ecm(geometry, ecm, native)
        self.assertFalse(result["exact_match"])
        self.assertEqual(result["cache_pairs_compared"], 0)

    def test_endpoint_missing_payload_and_nonboolean_completion_refuse(self):
        for fault in ("near_neigh", "make_maskM", "no endpoint", "no ecm", "truthy"):
            with self.subTest(fault=fault):
                geometry, ecm, native = ecm_inputs()
                if fault == "no endpoint":
                    del native["stop_after"]
                elif fault == "no ecm":
                    del native["ecm"]
                elif fault == "truthy":
                    ecm["source_completed"] = 1
                else:
                    native["stop_after"] = fault
                with self.assertRaises(ValueError):
                    comparator.compare_ecm(geometry, ecm, native)

    def test_incomplete_grid_or_cache_roots_refuse(self):
        for fault in ("missing grid", "empty grid", "root order"):
            with self.subTest(fault=fault):
                geometry, ecm, native = ecm_inputs()
                tree = json.loads(ecm["cache"]["descriptor_json"])
                if fault == "missing grid":
                    tree["items"].pop()
                    ecm["cache"]["columns"].pop()
                elif fault == "empty grid":
                    tree["items"][-1][1] = scalar("NoneType", None)
                    ecm["cache"]["columns"].pop()
                else:
                    tree["items"] = tree["items"][::-1]
                reseal(ecm["cache"], tree)
                with self.assertRaises(ValueError):
                    comparator.compare_ecm(geometry, ecm, native)

    def test_grid_cannot_exist_before_native_construction(self):
        geometry, ecm, native = ecm_inputs()
        tree = json.loads(ecm["before"]["descriptor_json"])
        tree["items"][-1][1] = dict(kind="dict", items=[])
        reseal(ecm["before"], tree)
        native["ecm"]["before"] = native_cache(ecm["before"])
        self.assertFalse(comparator.compare_ecm(geometry, ecm, native)["exact_match"])

    def test_equal_resealed_empty_grid_dictionaries_are_not_completion(self):
        geometry, ecm, native = ecm_inputs()
        tree = json.loads(ecm["cache"]["descriptor_json"])
        tree["items"][-1][1] = dict(kind="dict", items=[])
        ecm["cache"]["columns"].pop()
        reseal(ecm["cache"], tree)
        native["ecm"]["cache"] = native_cache(ecm["cache"])
        with self.assertRaisesRegex(ValueError, "nonempty completed grid cache"):
            comparator.compare_ecm(geometry, ecm, native)


def environment_inputs():
    base = owned_cache()
    tree = json.loads(base["descriptor_json"])
    tree["items"][2][1] = dict(
        kind="dict", items=[[scalar(value="plot_grid_size"), scalar("int", 50)]]
    )
    reseal(base, tree)
    geometry, ecm, native = ecm_inputs(base)
    ecm["identity"] = digest(b"synthetic ECM trial")
    before = copy.deepcopy(ecm["cache"])
    tree = json.loads(before["descriptor_json"])
    tree["items"] = [tree["items"][i] for i in (0, 3, 1, 2)]
    tree["items"].append([scalar(value="trees"), dict(kind="list", items=[])])
    reseal(before, tree)

    def append_array(cache, name, *, matrix=False, integers=False):
        shape, strides = ([2, 2], [16, 8]) if matrix else ([2], [8])
        source = layout("<i8" if integers else "<f8", shape, strides, f=not matrix)
        count = 4 if matrix else 2
        raw = struct.pack("<" + ("q" if integers else "d") * count, *range(count)).hex()
        node, column = array(str(len(cache["columns"])) + "-" + name, source=source, raw=raw)
        cache["columns"].append(column)
        return node

    def tree_fields(cache):
        values = {
            name: append_array(cache, name, matrix=name == "data", integers=name == "indices")
            for name in ("data", "indices", "mins", "maxes")
        }
        values.update(
            n=scalar("int", 2),
            m=scalar("int", 2),
            leafsize=scalar("int", 16),
            boxsize=scalar("NoneType", None),
        )
        return dict(
            kind="dict", items=[[scalar(value=k), values[k]] for k in comparator.TREE_FIELDS]
        )

    environment = copy.deepcopy(before)
    tree = json.loads(environment["descriptor_json"])
    tree["items"][0][1]["items"].append(
        [scalar(value="xypts"), append_array(environment, "xypts", matrix=True)]
    )
    tree["items"][-1][1]["items"].append(tree_fields(environment))
    reseal(environment, tree)
    assigned = copy.deepcopy(environment)
    tree = json.loads(assigned["descriptor_json"])
    tree["items"][0][1]["items"].append([scalar(value="grid_len"), scalar("int", 2)])
    reseal(assigned, tree)
    masked = copy.deepcopy(assigned)
    tree = json.loads(masked["descriptor_json"])
    for name in ("maskM", "maskECM"):
        tree["items"][0][1]["items"].append(
            [scalar(value=name), append_array(masked, name, matrix=True)]
        )
    tree["items"][-1][1]["items"].extend([tree_fields(masked), tree_fields(masked)])
    reseal(masked, tree)
    stages = [
        [name, cache]
        for name, cache in zip(
            comparator.ENVIRONMENT_STAGES, (environment, assigned, masked), strict=True
        )
    ]
    owned = dict(
        source_completed=True,
        failure_stage=None,
        failure_type=None,
        failure_message=None,
        parent_identity=ecm["identity"],
        before=before,
        stages=stages,
        cache=copy.deepcopy(masked),
        stream_before=copy.deepcopy(ecm["stream_after"]),
        stream_after=copy.deepcopy(ecm["stream_after"]),
    )
    native.update(
        stop_after="make_maskM",
        environment=dict(
            before=native_cache(before),
            stages=[[name, native_cache(cache)] for name, cache in stages],
            cache=native_cache(owned["cache"]),
            stream_before=copy.deepcopy(owned["stream_before"]),
            stream_after=copy.deepcopy(owned["stream_after"]),
        ),
    )
    return geometry, ecm, owned, native


def edit_environment_cache(cache, change):
    tree = json.loads(cache["descriptor_json"])
    change(tree)
    referenced = set()

    def visit(node):
        if isinstance(node, dict):
            if node.get("kind") == "numeric_array":
                referenced.add(node["column"])
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(tree)
    cache["columns"] = [row for row in cache["columns"] if row["name"] in referenced]
    reseal(cache, tree)


class EnvironmentComparisonTests(unittest.TestCase):
    def test_exact_environment_and_both_handoffs_without_mutation(self):
        values = environment_inputs()
        before = copy.deepcopy(values)
        result = comparator.compare_environment(*values)
        self.assertTrue(result["exact_match"])
        self.assertEqual(result["cache_pairs_compared"], 14)
        self.assertEqual(result["environment_cache_pairs_compared"], 5)
        self.assertEqual(result["environment_stages_compared"], 3)
        self.assertEqual(result["streams_compared"], 6)
        self.assertEqual(result["handoff_checks"], 8)
        self.assertEqual(result["lineage_checks"], 2)
        self.assertEqual(result["tree_prefix_checks"], 6)
        self.assertEqual(values, before)

    def test_incomplete_environment_markers_never_pass(self):
        for name, changed in (
            ("source_completed", False),
            ("failure_stage", "environment"),
            ("failure_type", "NativeError"),
            ("failure_message", "original failure"),
        ):
            with self.subTest(name=name):
                a, e, env, n = environment_inputs()
                env[name] = changed
                result = comparator.compare_environment(a, e, env, n)
                self.assertFalse(result["exact_match"])
                self.assertEqual(result["environment_cache_pairs_compared"], 0)

    def test_foreign_ecm_parent_is_rejected(self):
        a, e, env, n = environment_inputs()
        env["parent_identity"] = digest(b"foreign ECM parent")
        result = comparator.compare_environment(a, e, env, n)
        self.assertFalse(result["exact_match"])
        self.assertTrue(
            any(r["path"] == "owned.environment.parent_identity" for r in result["mismatches"])
        )

    def test_equal_before_caches_cannot_bypass_ecm_handoff(self):
        a, e, env, n = environment_inputs()
        edit_environment_cache(
            env["before"],
            lambda t: t["items"][0][1]["items"].append([scalar(value="extra"), scalar("int", 9)]),
        )
        n["environment"]["before"] = native_cache(env["before"])
        result = comparator.compare_environment(a, e, env, n)
        self.assertFalse(result["exact_match"])
        self.assertTrue(
            any("owned.environment.ecm_handoff" in r["path"] for r in result["mismatches"])
        )
        self.assertTrue(
            any("native.environment.ecm_handoff" in r["path"] for r in result["mismatches"])
        )

    def test_equal_rng_records_cannot_bypass_ecm_handoff(self):
        a, e, env, n = environment_inputs()
        env["stream_before"] = n["environment"]["stream_before"] = stream(position=31)
        result = comparator.compare_environment(a, e, env, n)
        self.assertFalse(result["exact_match"])
        self.assertTrue(
            any("owned.environment.rng_handoff" in r["path"] for r in result["mismatches"])
        )

    def test_mask_bits_and_final_random_state_are_compared(self):
        for fault in ("mask", "stream"):
            with self.subTest(fault=fault):
                a, e, env, n = environment_inputs()
                if fault == "stream":
                    n["environment"]["stream_after"] = stream(position=33)
                else:
                    saved = n["environment"]["cache"]
                    masks = {k["value"]: v for k, v in saved["tree"]["values"][0][1]["values"]}
                    node = masks["maskM"]
                    raw = struct.pack("<dddd", -0.0, 1.0, 2.0, 3.0).hex()
                    saved["columns"][node["column"]]["raw_bytes_hex"] = raw
                    node["sha256"] = digest(bytes.fromhex(raw))
                self.assertFalse(comparator.compare_environment(a, e, env, n)["exact_match"])

    def test_equal_resealed_final_caches_must_match_last_stage(self):
        a, e, env, n = environment_inputs()
        edit_environment_cache(
            env["cache"],
            lambda t: t["items"][0][1]["items"].append([scalar(value="extra"), scalar("int", 5)]),
        )
        n["environment"]["cache"] = native_cache(env["cache"])
        result = comparator.compare_environment(a, e, env, n)
        self.assertFalse(result["exact_match"])
        self.assertTrue(any("final_vs_make_maskM" in r["path"] for r in result["mismatches"]))

    def test_missing_reordered_or_duplicate_stages_refuse(self):
        for fault in ("missing", "reordered", "duplicated"):
            with self.subTest(fault=fault):
                a, e, env, n = environment_inputs()
                if fault == "missing":
                    env["stages"].pop()
                elif fault == "reordered":
                    env["stages"].reverse()
                else:
                    env["stages"][1][0] = "environment"
                with self.assertRaises(ValueError):
                    comparator.compare_environment(a, e, env, n)

    def test_equal_empty_tree_rosters_never_certify_completion(self):
        for index in range(3):
            with self.subTest(stage=index):
                a, e, env, n = environment_inputs()
                cache = env["stages"][index][1]
                edit_environment_cache(cache, lambda t: t["items"][-1][1]["items"].clear())
                n["environment"]["stages"][index][1] = native_cache(cache)
                with self.assertRaisesRegex(ValueError, "tree roster"):
                    comparator.compare_environment(a, e, env, n)

    def test_equal_changed_old_tree_fields_are_not_retained_state(self):
        a, e, env, n = environment_inputs()
        cache = env["stages"][1][1]
        edit_environment_cache(
            cache, lambda t: t["items"][-1][1]["items"][0]["items"][6][1].update(value=32)
        )
        n["environment"]["stages"][1][1] = native_cache(cache)
        result = comparator.compare_environment(a, e, env, n)
        self.assertFalse(result["exact_match"])
        self.assertTrue(any("retained_trees" in r["path"] for r in result["mismatches"]))

    def test_missing_tree_field_or_incorrect_grid_len_refuses(self):
        for fault in ("tree field", "grid_len", "maskM", "plot grid"):
            with self.subTest(fault=fault):
                a, e, env, n = environment_inputs()

                def change(t, fault=fault):
                    if fault == "tree field":
                        t["items"][-1][1]["items"][0]["items"].pop()
                    elif fault == "plot grid":
                        t["items"][3][1]["items"][0][1]["value"] = 49
                    else:
                        for key, value in t["items"][0][1]["items"]:
                            if key["value"] == fault:
                                value.clear()
                                value.update(scalar("int", 999))

                edit_environment_cache(env["cache"], change)
                n["environment"]["cache"] = native_cache(env["cache"])
                with self.assertRaises(ValueError):
                    comparator.compare_environment(a, e, env, n)

    def test_missing_environment_wrong_endpoint_and_truthy_completion_refuse(self):
        for fault in ("missing", "makeECM", "near_neigh", "truthy"):
            with self.subTest(fault=fault):
                a, e, env, n = environment_inputs()
                if fault == "missing":
                    del n["environment"]
                elif fault == "truthy":
                    env["source_completed"] = 1
                else:
                    n["stop_after"] = fault
                with self.assertRaises(ValueError):
                    comparator.compare_environment(a, e, env, n)


if __name__ == "__main__":
    unittest.main()
