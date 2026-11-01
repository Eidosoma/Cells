"""Exact saved final-boundary comparison; no source execution or owner restoration.

The only normalization is the three provenance scalars of the direct root
mesh.image_mask token. All numeric bits, source layouts and mapping order remain
exact. Source/input provenance and live ownership are the runner's obligations.
"""

import json

from validation.betse import native_single_cell_prefix_compare as wire

KIND = "cells.independent_multi_cell_caller@1"
ENDPOINT = "cell_index"
CACHES = ("parameter_cache", "caller_cache", "mesh_cache")
ALIASES = (
    "ecm_verts_is_vcell_verts",
    "ecm_verts_unique_is_vor_verts",
    "cluster_mask_is_clipping_matrix",
    "cell_centres_is_vor_cents",
    "mesh_image_mask_is_actual_mask",
)
MASK_FIELDS = (
    "kind",
    "identity",
    "image_identity",
    "xpts_m",
    "ypts_m",
    "clipping_matrix",
    "clipcurve_m",
)
TRIAL_FIELDS = (
    "request_identity",
    "parent_identities",
    *CACHES,
    "lattice_audit",
    "image_audit",
    "stages",
    "events",
    "ordering",
    "point_ids",
    "stream_before",
    "stream_after",
    "warnings",
    "work",
    "source_completed",
    "failure_stage",
    "failure_type",
    "failure_message",
    "identity",
)
NATIVE_FIELDS = (
    "kind",
    "stop_after",
    "status",
    "source_error",
    "capture_error",
    *CACHES,
    "stream_before",
    "stream_after",
    "image_unchanged",
    "global_random_stream_unchanged",
    "aliases",
    "original_source_pins",
    "source_sites",
    "events",
    "image_file_sha256",
)


def _metadata(value, path):
    """Require bounded JSON metadata, without assigning source authority to it."""
    try:
        text = json.dumps(value, allow_nan=False)
    except (TypeError, ValueError, OverflowError, RecursionError) as error:
        raise ValueError(path + ": invalid JSON metadata") from error
    if len(text) > wire.MAX_BYTES:
        wire._bad(path, "metadata exceeds the existing byte bound")


def _headers(owned, native):
    wire._keys(owned, TRIAL_FIELDS, "owned")
    wire._keys(native, NATIVE_FIELDS, "native")
    if native["kind"] != KIND or native["stop_after"] != ENDPOINT:
        wire._bad("native", "require the independent multi-cell cell_index endpoint")
    if type(owned["source_completed"]) is not bool or type(native["status"]) is not str:
        wire._bad("source markers", "require exact boolean completion and string status")
    for name in ("identity", "request_identity"):
        wire._digest(owned[name], "owned." + name)
    if type(owned["parent_identities"]) is not list or not owned["parent_identities"]:
        wire._bad("owned.parent_identities", "require retained parent digest list")
    for index, identity in enumerate(owned["parent_identities"]):
        wire._digest(identity, f"owned.parent_identities[{index}]")
    for name in ("failure_stage", "failure_type", "failure_message"):
        if owned[name] is not None and type(owned[name]) is not str:
            wire._bad("owned." + name, "require null or recorded failure text")
    for name in ("stages", "events", "ordering", "point_ids", "warnings", "work"):
        if type(owned[name]) is not list:
            wire._bad("owned." + name, "require the serialized Trial list")
    for name in ("lattice_audit", "image_audit"):
        if type(owned[name]) is not dict:
            wire._bad("owned." + name, "require the retained audit mapping")
    wire._digest(native["image_file_sha256"], "native.image_file_sha256")
    pins = native["original_source_pins"]
    if type(pins) is not dict or not pins:
        wire._bad("native.original_source_pins", "require original source path/digest mapping")
    for path, digest in pins.items():
        if type(path) is not str or not path:
            wire._bad("native.original_source_pins", "require nonempty source names")
        wire._digest(digest, "native.original_source_pins[" + path + "]")
    for name in ("source_sites", "events"):
        if type(native[name]) not in (list, dict):
            wire._bad("native." + name, "require normalized source metadata")
        _metadata(native[name], "native." + name)
    if not native["source_sites"]:
        wire._bad("native.source_sites", "require the declared source-site roster")
    wire._keys(native["aliases"], ALIASES, "native.aliases")
    for name, value in native["aliases"].items():
        if type(value) is not bool:
            wire._bad("native.aliases." + name, "require exact boolean identity observation")
    for name in ("image_unchanged", "global_random_stream_unchanged"):
        if type(native[name]) is not bool:
            wire._bad("native." + name, "require exact boolean observation")
    for name in ("source_error", "capture_error"):
        _metadata(native[name], "native." + name)


def _mask(cache, path, owned):
    fields = wire._fields(cache.tree, path)
    if "image_mask" not in fields:
        wire._bad(path, "require the direct root image_mask field")
    token = wire._fields(fields["image_mask"], path + ".image_mask", MASK_FIELDS)
    expected = "owned_image_prelude_mask_token" if owned else "independent_image_mask_token"
    if token["kind"] != dict(type="str", value=expected):
        wire._bad(path + ".image_mask.kind", "wrong token role")
    original = {"kind": expected}
    for name in ("identity", "image_identity"):
        value = token[name]
        if owned:
            if value["type"] != "str":
                wire._bad(path + ".image_mask." + name, "require the original digest token")
            wire._digest(value["value"], path + ".image_mask." + name)
            original[name] = value["value"]
        else:
            if value != dict(type="NoneType", value=None):
                wire._bad(path + ".image_mask." + name, "independent token has no owner identity")
            original[name] = None
    for name in MASK_FIELDS[3:]:
        if token[name]["type"] != "array":
            wire._bad(path + ".image_mask." + name, "require the original numeric array role")
    # _Cache constructs fresh normalized nodes. Only these direct-root scalar
    # nodes are rewritten; input descriptors, byte columns and other tokens stay
    # untouched and are compared exactly.
    for name in MASK_FIELDS[:3]:
        token[name].clear()
        token[name].update(type="str", value="disclosed_provenance_only")
    return original


def compare(owned_trial, native):
    """Compare three final caches and two streams; malformed evidence raises.

    Failed source/alias observations return zero comparison credit. Complete
    evidence returns exact bit/layout/order mismatches, with no tolerance or
    independent geometric, phase, owner or biological admission.
    """
    _headers(owned_trial, native)
    differences = []
    result = dict(
        kind="cells.multi_cell_saved_final_boundary_exact_comparison@1",
        stop_after=ENDPOINT,
        exact_match=False,
        cache_pairs_compared=0,
        arrays_compared=0,
        streams_compared=0,
        aliases_checked=0,
        mismatches=differences,
        provenance_normalization=None,
        scope=dict(
            final_caches_only=True,
            per_method_events_compared=False,
            lattice_audit_compared=False,
            independent_geometry_or_biology=False,
            input_plan_authenticated=False,
            owned_token_ids_authenticated=False,
            phase_or_owner_authority_authenticated=False,
        ),
    )
    markers = [
        ("owned", "source_completed", True),
        *(("owned", name, None) for name in ("failure_stage", "failure_type", "failure_message")),
        ("native", "status", "source_completed"),
        ("native", "source_error", None),
        ("native", "capture_error", None),
        ("native", "image_unchanged", True),
        ("native", "global_random_stream_unchanged", True),
    ]
    for side, name, expected in markers:
        value = (owned_trial if side == "owned" else native)[name]
        if value != expected:
            differences.append(
                dict(
                    path=side + "." + name,
                    reason="incomplete_source_or_observation",
                    observed=value,
                )
            )
    for name in ALIASES:
        result["aliases_checked"] += 1
        if native["aliases"][name] is not True:
            differences.append(
                dict(path="native.aliases." + name, reason="incomplete_native_alias")
            )
    if differences:
        return result
    for name in CACHES:
        left = wire._Cache(owned_trial[name], "owned." + name, True)
        right = wire._Cache(native[name], "native." + name, False)
        for side, cache in (("owned", left), ("native", right)):
            if not wire._fields(cache.tree, side + "." + name):
                wire._bad(side + "." + name, "completed cache cannot be empty")
            if not cache.finite:
                wire._bad(side + "." + name, "nonfinite completed cache")
        if name == "mesh_cache":
            result["provenance_normalization"] = dict(
                path="mesh_cache.image_mask",
                fields=list(MASK_FIELDS[:3]),
                owned=_mask(left, "owned.mesh_cache", True),
                independent=_mask(right, "native.mesh_cache", False),
                declared_image_file_sha256=native["image_file_sha256"],
                token_ids_or_declared_image_not_authenticated=True,
            )
        wire._difference(left.tree, right.tree, name, differences)
        result["cache_pairs_compared"] += 1
        result["arrays_compared"] += left.arrays
    for name in ("stream_before", "stream_after"):
        wire._difference(
            wire._stream(owned_trial[name], "owned." + name),
            wire._stream(native[name], "native." + name),
            name,
            differences,
        )
        result["streams_compared"] += 1
    result["exact_match"] = not differences
    return result
