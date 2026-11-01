"""Saved JSON/byte controls only; no NumPy, native source or live owners."""

import copy
import hashlib
import json
import struct
import unittest

from validation.betse import native_multi_cell_caller_compare as comparator


def digest(value):
    return hashlib.sha256(value).hexdigest()


def scalar(value):
    if type(value) is float:
        return dict(kind="float", bits=struct.pack("<d", value).hex())
    return dict(kind=type(value).__name__, value=value)


def mapping(rows):
    return dict(kind="dict", items=[[scalar(name), value] for name, value in rows])


def column(name, values=(0.0, -0.0), *, shape=(2,), strides=(8,), c=True, f=True):
    raw = struct.pack("<" + "d" * len(values), *values)
    layout = dict(
        dtype="<f8", shape=list(shape), strides_bytes=list(strides), C_contiguous=c, F_contiguous=f
    )
    node = dict(kind="numeric_array", source_layout=layout, column=name, sha256=digest(raw))
    stride, stored = 8, []
    for size in reversed(shape):
        stored.insert(0, stride)
        stride *= size
    return node, dict(
        name=name,
        values=dict(
            __ndarray__=True,
            dtype="<f8",
            shape=list(shape),
            strides=stored,
            raw_bytes_hex=raw.hex(),
        ),
    )


def cache(tree, columns=(), *, finite=True):
    text = json.dumps(tree, sort_keys=True, separators=(",", ":"))
    return dict(
        descriptor_json=text,
        columns=list(columns),
        all_finite=finite,
        identity=digest(text.encode()),
    )


def native_cache(owned):
    """Fixture encoder, independent of the comparator's parser/normalization."""
    stored = {row["name"]: row["values"] for row in owned["columns"]}
    columns = {}

    def convert(node):
        kind = node["kind"]
        if kind == "numeric_array":
            name = "native-" + str(len(columns))
            columns[name] = copy.deepcopy(stored[node["column"]])
            return dict(
                type="array",
                layout=copy.deepcopy(node["source_layout"]),
                column=name,
                sha256=node["sha256"],
            )
        if kind == "dict":
            return dict(type="dict", values=[[convert(k), convert(v)] for k, v in node["items"]])
        if "items" in node:
            return dict(type=kind, values=[convert(v) for v in node["items"]])
        return {"type": kind, **{key: value for key, value in node.items() if key != "kind"}}

    return dict(tree=convert(json.loads(owned["descriptor_json"])), columns=columns)


def stream(*, position=17, gaussian=-0.0):
    state = ["MT19937", list(range(1, 625)), position, 1, gaussian]
    payload = dict(rng_id=comparator.wire.RNG_ID, numpy_version="synthetic-only", state=state)
    return dict(
        state_json=json.dumps(state, separators=(",", ":")),
        numpy_version=payload["numpy_version"],
        identity=digest(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()),
    )


def inputs():
    parameters = cache(mapping([("world_len", scalar(4.0)), ("flag", scalar(False))]))
    vertices, vertex_column = column("vertices")
    caller = cache(
        mapping([("cell_centres", vertices), ("cell_count", scalar(2))]), [vertex_column]
    )
    rows = [
        ("kind", scalar("owned_image_prelude_mask_token")),
        ("identity", scalar("a" * 64)),
        ("image_identity", scalar("b" * 64)),
    ]
    columns = []
    for name in ("xpts_m", "ypts_m", "clipping_matrix", "clipcurve_m"):
        if name in ("xpts_m", "ypts_m"):
            node, stored = column(name)
        else:
            node, stored = column(
                name,
                (0.0, 1.0, 1.0, 0.0),
                shape=(2, 2),
                strides=(-16, 8) if name == "clipping_matrix" else (16, 8),
                c=name != "clipping_matrix",
                f=False,
            )
        rows.append((name, node))
        columns.append(stored)
    mesh = cache(mapping([("image_mask", mapping(rows)), ("cell_count", scalar(2))]), columns)
    owned = dict(
        request_identity="c" * 64,
        parent_identities=["d" * 64, "e" * 64, "f" * 64],
        parameter_cache=parameters,
        caller_cache=caller,
        mesh_cache=mesh,
        lattice_audit={"retained_outside_comparison": True},
        image_audit={"retained_outside_comparison": True},
        stages=[],
        events=[],
        ordering=[],
        point_ids=[],
        warnings=[],
        work=[],
        stream_before=stream(),
        stream_after=stream(position=53),
        source_completed=True,
        failure_stage=None,
        failure_type=None,
        failure_message=None,
        identity="1" * 64,
    )
    native = dict(
        kind=comparator.KIND,
        stop_after="cell_index",
        status="source_completed",
        source_error=None,
        capture_error=None,
        **{name: native_cache(owned[name]) for name in comparator.CACHES},
        stream_before=stream(),
        stream_after=stream(position=53),
        image_unchanged=True,
        global_random_stream_unchanged=True,
        aliases=dict.fromkeys(comparator.ALIASES, True),
        original_source_pins={"betse/science/cells.py": "2" * 64},
        source_sites={"Cells.make_world": [397, 454]},
        events=[],
        image_file_sha256="3" * 64,
    )
    token = native["mesh_cache"]["tree"]["values"][0][1]["values"]
    token[0][1] = dict(type="str", value="independent_image_mask_token")
    token[1][1] = dict(type="NoneType", value=None)
    token[2][1] = dict(type="NoneType", value=None)
    return owned, native


def native_token(native):
    return native["mesh_cache"]["tree"]["values"][0][1]["values"]


def reseal(owned, tree):
    owned["descriptor_json"] = json.dumps(tree, sort_keys=True, separators=(",", ":"))
    owned["identity"] = digest(owned["descriptor_json"].encode())


def mutate_raw(native, cache_name, node, raw):
    native[cache_name]["columns"][node["column"]]["raw_bytes_hex"] = raw.hex()
    node["sha256"] = digest(raw)


class MultiCellComparisonTests(unittest.TestCase):
    def test_exact_match_scope_and_inputs_are_unchanged(self):
        owned, native = inputs()
        before = copy.deepcopy((owned, native))
        result = comparator.compare(owned, native)
        self.assertTrue(result["exact_match"])
        self.assertEqual(result["cache_pairs_compared"], 3)
        self.assertEqual(result["streams_compared"], 2)
        self.assertEqual(result["arrays_compared"], 5)
        self.assertEqual(result["aliases_checked"], 5)
        self.assertEqual((owned, native), before)
        self.assertFalse(result["scope"]["input_plan_authenticated"])
        self.assertFalse(result["scope"]["owned_token_ids_authenticated"])
        self.assertFalse(result["scope"]["per_method_events_compared"])

    def test_only_three_disclosed_provenance_scalars_differ(self):
        owned, native = inputs()
        result = comparator.compare(owned, native)
        disclosure = result["provenance_normalization"]
        self.assertEqual(disclosure["path"], "mesh_cache.image_mask")
        self.assertEqual(
            disclosure["owned"],
            dict(kind="owned_image_prelude_mask_token", identity="a" * 64, image_identity="b" * 64),
        )
        self.assertEqual(
            disclosure["independent"],
            dict(kind="independent_image_mask_token", identity=None, image_identity=None),
        )
        tree = json.loads(owned["mesh_cache"]["descriptor_json"])
        tree["items"][0][1]["items"][1][1]["value"] = "9" * 64
        reseal(owned["mesh_cache"], tree)
        changed = comparator.compare(owned, native)
        self.assertTrue(changed["exact_match"])
        self.assertEqual(changed["provenance_normalization"]["owned"]["identity"], "9" * 64)

    def test_missing_and_extra_headers_refuse(self):
        for side, fields in ((0, comparator.TRIAL_FIELDS), (1, comparator.NATIVE_FIELDS)):
            for name in fields:
                with self.subTest(side=side, name=name):
                    pair = inputs()
                    del pair[side][name]
                    with self.assertRaises(ValueError):
                        comparator.compare(*pair)
        for side, name in ((0, "descriptor_proof"), (1, "ordinary_descriptor")):
            with self.subTest(side=side, extra=name):
                pair = inputs()
                pair[side][name] = []
                with self.assertRaises(ValueError):
                    comparator.compare(*pair)

    def test_wrong_endpoint_kind_and_marker_types_refuse(self):
        for side, name, value in (
            (1, "kind", "cells.independent_single_cell@1"),
            (1, "stop_after", "makeECM"),
            (1, "stop_after", None),
            (0, "source_completed", 1),
            (1, "status", True),
            (1, "image_unchanged", 1),
            (1, "global_random_stream_unchanged", "true"),
        ):
            with self.subTest(name=name, value=value):
                pair = inputs()
                pair[side][name] = value
                with self.assertRaises(ValueError):
                    comparator.compare(*pair)

    def test_failed_or_incomplete_source_never_compares_caches(self):
        for side, name, value in (
            (0, "source_completed", False),
            (0, "failure_stage", "clip_to_curve"),
            (0, "failure_type", "AssertionError"),
            (0, "failure_message", ""),
            (1, "status", "source_failed"),
            (1, "source_error", {"type": "ValueError"}),
            (1, "capture_error", {"type": "OSError"}),
            (1, "image_unchanged", False),
            (1, "global_random_stream_unchanged", False),
        ):
            with self.subTest(side=side, name=name):
                pair = inputs()
                pair[side][name] = value
                pair[side]["caller_cache"] = None
                result = comparator.compare(*pair)
                self.assertFalse(result["exact_match"])
                self.assertEqual(result["cache_pairs_compared"], 0)
                self.assertEqual(result["streams_compared"], 0)

    def test_exact_alias_roster_and_true_boolean_required(self):
        for name in comparator.ALIASES:
            for value in (False, 0, 1, "true"):
                with self.subTest(name=name, value=value):
                    owned, native = inputs()
                    native["aliases"][name] = value
                    if value is False:
                        result = comparator.compare(owned, native)
                        self.assertFalse(result["exact_match"])
                        self.assertEqual(result["cache_pairs_compared"], 0)
                    else:
                        with self.assertRaises(ValueError):
                            comparator.compare(owned, native)
        for change in ("missing", "extra"):
            owned, native = inputs()
            if change == "missing":
                del native["aliases"][comparator.ALIASES[0]]
            else:
                native["aliases"]["unrequested"] = True
            with self.assertRaises(ValueError):
                comparator.compare(owned, native)

    def test_digest_and_source_header_types(self):
        edits = (
            (0, "identity", "bad"),
            (0, "request_identity", "A" * 64),
            (0, "parent_identities", []),
            (0, "parent_identities", ["bad"]),
            (0, "events", {}),
            (0, "lattice_audit", []),
            (0, "failure_type", True),
            (1, "image_file_sha256", "not-a-digest"),
            (1, "original_source_pins", {}),
            (1, "original_source_pins", {"x": "bad"}),
            (1, "source_sites", []),
            (1, "source_sites", "unbound"),
            (1, "events", [float("nan")]),
            (1, "capture_error", object()),
        )
        for side, name, value in edits:
            with self.subTest(side=side, name=name, value=repr(value)):
                pair = inputs()
                pair[side][name] = value
                with self.assertRaises(ValueError):
                    comparator.compare(*pair)

    def test_parameter_caller_and_mesh_field_value_order_mismatches(self):
        for name in comparator.CACHES:
            for change in ("field", "value", "order"):
                with self.subTest(cache=name, change=change):
                    owned, native = inputs()
                    rows = native[name]["tree"]["values"]
                    if change == "field":
                        rows[-1][0]["value"] += "-changed"
                    elif change == "value":
                        rows[-1][1] = dict(type="int", value=99)
                    else:
                        rows.reverse()
                    self.assertFalse(comparator.compare(owned, native)["exact_match"])

    def test_empty_and_duplicate_root_fields_refuse(self):
        for name in comparator.CACHES:
            for change in ("empty", "duplicate"):
                with self.subTest(cache=name, change=change):
                    owned, native = inputs()
                    if change == "empty":
                        native[name] = dict(tree=dict(type="dict", values=[]), columns={})
                    else:
                        row = native[name]["tree"]["values"][-1]
                        native[name]["tree"]["values"].append(copy.deepcopy(row))
                    with self.assertRaises(ValueError):
                        comparator.compare(owned, native)

    def test_signed_zero_and_numeric_bytes_mismatch_after_valid_rehash(self):
        for raw in (struct.pack("<dd", 0.0, 0.0), struct.pack("<dd", 0.0, 7.0)):
            owned, native = inputs()
            node = native["caller_cache"]["tree"]["values"][0][1]
            mutate_raw(native, "caller_cache", node, raw)
            result = comparator.compare(owned, native)
            self.assertFalse(result["exact_match"])
            self.assertTrue(any(row["path"].endswith(".raw") for row in result["mismatches"]))

    def test_numeric_dtype_shape_and_layout_mismatch(self):
        for change in ("dtype", "shape", "stride"):
            with self.subTest(change=change):
                owned, native = inputs()
                node = native["caller_cache"]["tree"]["values"][0][1]
                values = native["caller_cache"]["columns"][node["column"]]
                if change == "dtype":
                    node["layout"]["dtype"] = values["dtype"] = "<i8"
                elif change == "shape":
                    node["layout"]["shape"] = values["shape"] = [1, 2]
                    node["layout"]["strides_bytes"] = values["strides"] = [16, 8]
                else:
                    node["layout"]["strides_bytes"] = [-8]
                    node["layout"]["C_contiguous"] = node["layout"]["F_contiguous"] = False
                self.assertFalse(comparator.compare(owned, native)["exact_match"])

    def test_nonfinite_arrays_and_scalars_refuse_completed_evidence(self):
        for value in (float("inf"), float("-inf"), float("nan")):
            with self.subTest(value=repr(value)):
                owned, native = inputs()
                node = native["caller_cache"]["tree"]["values"][0][1]
                mutate_raw(native, "caller_cache", node, struct.pack("<dd", value, 0.0))
                with self.assertRaises(ValueError):
                    comparator.compare(owned, native)
                owned, native = inputs()
                native["parameter_cache"]["tree"]["values"][0][1]["bits"] = struct.pack(
                    "<d", value
                ).hex()
                with self.assertRaises(ValueError):
                    comparator.compare(owned, native)

    def test_hash_storage_dtype_and_finite_flag_corruption_refuse(self):
        for change in ("hash", "column_bits", "dtype", "unused", "duplicate", "finite"):
            with self.subTest(change=change):
                owned, native = inputs()
                node = native["caller_cache"]["tree"]["values"][0][1]
                values = native["caller_cache"]["columns"][node["column"]]
                if change == "hash":
                    node["sha256"] = "0" * 64
                elif change == "column_bits":
                    values["raw_bytes_hex"] = "01" + values["raw_bytes_hex"][2:]
                elif change == "dtype":
                    values["dtype"] = "<i8"
                elif change == "unused":
                    native["caller_cache"]["columns"]["extra"] = copy.deepcopy(values)
                elif change == "duplicate":
                    native["caller_cache"]["tree"]["values"].append(
                        [dict(type="str", value="new"), copy.deepcopy(node)]
                    )
                else:
                    owned["caller_cache"]["all_finite"] = False
                with self.assertRaises(ValueError):
                    comparator.compare(owned, native)

    def test_owned_descriptor_identity_is_checked_before_normalizing(self):
        owned, native = inputs()
        owned["mesh_cache"]["identity"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "descriptor hash"):
            comparator.compare(owned, native)

    def test_mask_order_missing_extra_duplicate_and_roles_refuse(self):
        for change in ("order", "missing", "extra", "duplicate", "kind", "role"):
            with self.subTest(change=change):
                owned, native = inputs()
                rows = native_token(native)
                if change == "order":
                    rows[3], rows[4] = rows[4], rows[3]
                elif change == "missing":
                    rows.pop(1)
                elif change == "extra":
                    rows.append([dict(type="str", value="other"), dict(type="int", value=0)])
                elif change == "duplicate":
                    rows[2][0]["value"] = "identity"
                elif change == "kind":
                    rows[0][1]["value"] = "owned_image_prelude_mask_token"
                else:
                    rows[3][1] = dict(type="list", values=[])
                    del native["mesh_cache"]["columns"]["native-0"]
                with self.assertRaises(ValueError):
                    comparator.compare(owned, native)

    def test_owned_and_native_provenance_roles_are_not_interchangeable(self):
        for name in ("identity", "image_identity"):
            for value in ("f" * 64, False):
                owned, native = inputs()
                index = comparator.MASK_FIELDS.index(name)
                native_token(native)[index][1] = dict(type=type(value).__name__, value=value)
                with self.assertRaises(ValueError):
                    comparator.compare(owned, native)
            owned, native = inputs()
            tree = json.loads(owned["mesh_cache"]["descriptor_json"])
            tree["items"][0][1]["items"][comparator.MASK_FIELDS.index(name)][1] = scalar("bad")
            reseal(owned["mesh_cache"], tree)
            with self.assertRaises(ValueError):
                comparator.compare(owned, native)

    def test_only_direct_mesh_image_mask_is_normalized(self):
        for change in ("nested", "renamed"):
            with self.subTest(change=change):
                owned, native = inputs()
                row = native["mesh_cache"]["tree"]["values"][0]
                if change == "renamed":
                    row[0]["value"] = "not_image_mask"
                else:
                    native["mesh_cache"]["tree"]["values"][0] = [
                        dict(type="str", value="nested"),
                        dict(type="dict", values=[row]),
                    ]
                with self.assertRaises(ValueError):
                    comparator.compare(owned, native)
        owned, native = inputs()
        tree = json.loads(owned["caller_cache"]["descriptor_json"])
        tree["items"].append([scalar("kind"), scalar("owned_image_prelude_mask_token")])
        reseal(owned["caller_cache"], tree)
        native["caller_cache"]["tree"]["values"].append(
            [dict(type="str", value="kind"), dict(type="str", value="independent_image_mask_token")]
        )
        self.assertFalse(comparator.compare(owned, native)["exact_match"])

    def test_mask_pixels_and_negative_row_layout_remain_exact(self):
        for change in ("pixels", "copied_layout"):
            with self.subTest(change=change):
                owned, native = inputs()
                node = native_token(native)[5][1]
                if change == "pixels":
                    mutate_raw(native, "mesh_cache", node, struct.pack("<dddd", 1.0, 1.0, 1.0, 0.0))
                else:
                    node["layout"]["strides_bytes"] = [16, 8]
                    node["layout"]["C_contiguous"] = True
                self.assertFalse(comparator.compare(owned, native)["exact_match"])

    def test_stream_words_position_version_gaussian_and_hash(self):
        for name in ("stream_before", "stream_after"):
            for change in ("position", "gaussian", "words", "version", "hash"):
                with self.subTest(name=name, change=change):
                    owned, native = inputs()
                    old = native[name]
                    state = json.loads(old["state_json"])
                    if change == "hash":
                        old["identity"] = "0" * 64
                        with self.assertRaises(ValueError):
                            comparator.compare(owned, native)
                        continue
                    if change == "position":
                        state[2] += 1
                    elif change == "gaussian":
                        state[4] = 0.0
                    elif change == "words":
                        state[1][0] += 1
                    else:
                        old["numpy_version"] = "another-runtime"
                    old["state_json"] = json.dumps(state, separators=(",", ":"))
                    old["identity"] = digest(
                        json.dumps(
                            dict(
                                rng_id=comparator.wire.RNG_ID,
                                numpy_version=old["numpy_version"],
                                state=state,
                            ),
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode()
                    )
                    self.assertFalse(comparator.compare(owned, native)["exact_match"])


if __name__ == "__main__":
    unittest.main()
