"""Read a completed legacy multi-cell diagnostic without replay or hydration.

All eight saved boundaries and their immutable source/capture pins remain
evidence. This checks their recorded associations, not live owner authority or
the correctness of geometry. Large sidecars are authenticated without expansion.
"""

import hashlib
import json

from validation import source_snapshot
from validation.betse import native_multi_cell_caller_compare as comparison
from validation.betse import native_multi_cell_caller_native as native
from validation.betse import native_multi_cell_caller_qualification as prior
from validation.betse import native_single_cell_prefix_payload as payload

shared = prior.shared
RAW_FIELDS = ("seed_recipe", "seed_stream_before", "controls", "image_recipe")
INITIAL_REQUEST_FIELDS = (
    "origin",
    "upstream",
    "constructor_kwargs",
    "source_occurrence_ids",
    "constructor_point_ids",
    "stream_before",
    "next_action",
    "identity",
)
INITIAL_STATE_FIELDS = (
    "request_identity",
    "constructed_cache",
    "cache",
    "events",
    "retained_point_ids",
    "stream_before",
    "stream_after_constructor",
    "stream_after",
    "warnings",
    "constructor_completed",
    "pre_mesh_completed",
    "status",
    "failure_stage",
    "failure_type",
    "failure_message",
    "identity",
)
CLIP_STATE_FIELDS = (
    "request_identity",
    "initial_cache",
    "cache",
    "events",
    "parent_point_ids",
    "derived_point_ids_before_rebuild",
    "retained_point_ids",
    "stream_after_initial",
    "stream_after",
    "warnings",
    "status",
    "failure_stage",
    "failure_type",
    "failure_message",
    "identity",
)
LIFECYCLE_STATE_FIELDS = (
    "request_identity",
    "before_cache",
    "cache",
    "events",
    "point_ids_before",
    "point_ids_after",
    "stream_before",
    "stream_after",
    "termination_json",
    "warnings",
    "status",
    "failure_stage",
    "failure_type",
    "failure_message",
    "identity",
)


def _keys(value, names, label):
    comparison.wire._keys(value, names, label)


def _identity(value):
    comparison.wire._digest(value, "saved identity")
    return value


def _same(left, right):
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(
        right, sort_keys=True, allow_nan=False
    )


def _equal(left, right, label):
    if not _same(left, right):
        raise ValueError("Changed saved " + label)


def _json(text, label):
    return comparison.wire._json(text, label)


def _scalars(value):
    return native.source.shared.scalars(value)


def _cache(value):
    _keys(value, ("descriptor_json", "columns", "all_finite", "identity"), "saved cache")
    _identity(value["identity"])
    _json(value["descriptor_json"], "saved cache descriptor")
    if (
        type(value["columns"]) is not list
        or value["all_finite"] is not True
        or hashlib.sha256(value["descriptor_json"].encode()).hexdigest() != value["identity"]
    ):
        raise ValueError("Incomplete finite saved cache seal")


def _state(value, fields, request, status):
    _keys(value, fields, "saved " + status)
    if (
        value["request_identity"] != _identity(request["identity"])
        or value["status"] != status
        or any(
            value[name] is not None for name in ("failure_stage", "failure_type", "failure_message")
        )
    ):
        raise ValueError("Incomplete or mismatched saved state")
    _identity(value["identity"])
    _cache(value["cache"])


def _mask_association(trial, prelude):
    tree = _json(trial["mesh_cache"]["descriptor_json"], "mesh descriptor")

    def fields(node):
        _keys(node, ("kind", "items"), "owned mask mapping")
        if node["kind"] != "dict" or type(node["items"]) is not list:
            raise ValueError("Missing owned mask mapping")
        result = {}
        for pair in node["items"]:
            if type(pair) is not list or len(pair) != 2:
                raise ValueError("Malformed owned mask mapping")
            key, value = pair
            _keys(key, ("kind", "value"), "owned mask key")
            if key["kind"] != "str" or type(key["value"]) is not str or key["value"] in result:
                raise ValueError("Duplicate or invalid owned mask key")
            result[key["value"]] = value
        return result

    token = fields(fields(tree)["image_mask"])
    if list(token) != list(comparison.MASK_FIELDS):
        raise ValueError("Changed owned image-mask token roster")
    for name, expected in (
        ("kind", "owned_image_prelude_mask_token"),
        ("identity", prelude["identity"]),
        ("image_identity", prelude["image"]["identity"]),
    ):
        _equal(token[name], dict(kind="str", value=expected), "mask/prelude " + name)
    if any(token[name].get("kind") != "numeric_array" for name in comparison.MASK_FIELDS[3:]):
        raise ValueError("Incomplete retained mask array roles")


def _recipe(first, initial_request, configuration, case):
    raw = first["native_comparison_inputs"]
    _keys(
        raw,
        (
            *RAW_FIELDS,
            "classification",
            "upstream_accuracy_qualification",
            "image_bytes_hex",
            "lifecycle_case",
            "native_option_recipe",
        ),
        "saved fixture",
    )
    prior._declaration(case, _scalars(raw))
    if (
        raw["classification"] != "native_lattice_and_owned_image_source_inputs"
        or raw["upstream_accuracy_qualification"] != "open"
    ):
        raise ValueError("Changed registered fixture classification")
    selected = {name: raw[name] for name in RAW_FIELDS}
    declared, conf, image_path = native.inputs(selected, configuration)
    _equal(conf, prior.configuration(), "registered configuration")
    _equal(_scalars(first["configuration"]), conf, "captured configuration")
    recipe = declared["seed_recipe"]
    _equal(
        recipe,
        dict(
            kind="cells.betse_lattice_seed_recipe@1",
            provenance="Native scalar world controls, no image/mesh or biological geometry",
            lattice_type="SQUARE" if case == prior.CASES[0] else "HEX",
            world_len_m=4e-5,
            cell_radius_m=5e-6,
            lattice_disorder=0.35,
        ),
        "registered seed recipe",
    )
    upstream = initial_request["upstream"]
    if type(upstream) is not list or len(upstream) != 3:
        raise ValueError("Require binding, seed state and image prelude")
    binding, seeds, prelude = upstream
    for value in upstream:
        _identity(value["identity"])
    _equal(_json(binding["definition_json"], "seed definition"), recipe, "binding recipe")
    if (
        seeds["binding_identity"] != binding["identity"]
        or prelude["lattice_binding_identity"] != binding["identity"]
        or prelude["lattice_state_identity"] != seeds["identity"]
        or prelude["next_method"] != "clip_and_refine"
    ):
        raise ValueError("Changed seed/image prelude lineage")
    for record in (seeds["stream_before"], seeds["stream_after"], prelude["stream"]):
        comparison.wire._stream(record, "saved seed/prelude stream")
    _equal(
        _json(seeds["stream_before"]["state_json"], "seed stream"),
        declared["seed_stream_before"],
        "raw/retained seed stream",
    )
    _equal(prelude["stream"], seeds["stream_after"], "prelude stream")
    _equal(_json(prelude["controls_json"], "prelude controls"), prior.CONTROLS, "prelude controls")
    _equal(initial_request["stream_before"], prelude["stream"], "initial/prelude stream")
    _equal(
        initial_request["constructor_kwargs"],
        prelude["constructor_kwargs"],
        "initial constructor declaration",
    )
    kwargs = _scalars(
        {k: v for k, v in prelude["constructor_kwargs"].items() if k != "seed_points"}
    )
    _equal(
        kwargs,
        dict(
            cell_radius=recipe["cell_radius_m"],
            use_alpha_shape=True,
            allow_merging=True,
            single_cell_noise=0.5,
            single_cell_sides=6,
            image_mask=None,
            make_all_operators=False,
            mesh_type="rect" if recipe["lattice_type"] == "SQUARE" else "tri",
            alpha_shape=0.05,
            use_centroids=True,
            merge_thresh=0.1,
            close_thresh=0.1,
        ),
        "registered constructor options",
    )
    _equal(
        initial_request["constructor_kwargs"]["seed_points"],
        seeds["values"]["all_seed_points_m"],
        "retained complete seed points",
    )
    for name in ("source_occurrence_ids", "constructor_point_ids"):
        _equal(initial_request[name], seeds["occurrence_ids"], "initial point IDs")
    image = prelude["image"]
    _identity(image["identity"])
    _equal(
        _json(image["definition_json"], "retained image recipe"),
        declared["image_recipe"],
        "image recipe",
    )
    if (
        image["file_sha256"] != declared["image_recipe"]["image_sha256"]
        or image["native_filename"] != str(image_path)
        or image["resolved_filename"] != str(image_path.resolve(strict=True))
        or image["file_bytes"] != {"bytes_hex": raw["image_bytes_hex"]}
    ):
        raise ValueError("Changed retained image file association")
    data = bytes.fromhex(raw["image_bytes_hex"])
    if (
        data != b"P5\n4 4\n255\n" + bytes(16)
        or declared["image_recipe"]["filename"] != "dense4.pgm"
        or hashlib.sha256(data).hexdigest() != image["file_sha256"]
    ):
        raise ValueError("Changed retained image bytes")
    return selected, seeds, prelude


def capture_lineage(values, configuration, case):
    """Validate recorded associations only; return the four-field source input."""
    if case not in prior.CASES or type(values) is not list or len(values) != len(prior.STAGES):
        raise ValueError("Require the eight registered legacy caller captures")
    try:
        first, initial, clip_request, clip, life_request, life, request, trial = values
        _keys(first, ("request", "native_comparison_inputs", "configuration"), "first capture")
        initial_request = first["request"]
        _keys(initial_request, INITIAL_REQUEST_FIELDS, "initial request")
        if (
            initial_request["origin"] != "owned_image_prelude"
            or initial_request["next_action"] != "clip_to_curve(owned_image_mask)"
        ):
            raise ValueError("Unregistered initial source branch")
        selected, seeds, prelude = _recipe(first, initial_request, configuration, case)
        _state(initial, INITIAL_STATE_FIELDS, initial_request, "source_completed_unqualified")
        if (
            initial["constructor_completed"] is not True
            or initial["pre_mesh_completed"] is not True
        ):
            raise ValueError("Incomplete saved constructor/pre-mesh")
        _cache(initial["constructed_cache"])
        _keys(clip_request, ("initial_request", "initial_state", "identity"), "clip request")
        _equal(clip_request["initial_request"], initial_request, "clip/initial request")
        _equal(clip_request["initial_state"], initial, "clip/initial state")
        _state(clip, CLIP_STATE_FIELDS, clip_request, "source_clipped_rebuilt_unqualified")
        _equal(clip["initial_cache"], initial["cache"], "clip initial cache")
        _equal(clip["parent_point_ids"], initial["retained_point_ids"], "clip parent point IDs")
        _keys(
            life_request,
            ("clip_request", "clip_state", "origin", "options_json", "identity"),
            "lifecycle request",
        )
        _equal(life_request["clip_request"], clip_request, "lifecycle clip request")
        _equal(life_request["clip_state"], clip, "lifecycle clip state")
        options = dict(
            smoothing=None, refinement=False, max_steps=2, convergence=1e-30, fix_bounds=True
        )
        if life_request["origin"] != "owned_make_voronoi_lifecycle":
            raise ValueError("Manufactured lifecycle options are not the caller")
        _equal(_json(life_request["options_json"], "lifecycle options"), options, "caller options")
        _equal(_scalars(prelude["next_kwargs"]), options, "prelude lifecycle options")
        _state(life, LIFECYCLE_STATE_FIELDS, life_request, "source_lifecycle_completed_unqualified")
        _equal(life["before_cache"], clip["cache"], "lifecycle initial cache")
        _equal(life["point_ids_before"], clip["retained_point_ids"], "lifecycle parent point IDs")
        _keys(
            request,
            ("lifecycle_request", "lifecycle_state", "configuration_json", "identity"),
            "plain caller request",
        )
        _equal(request["lifecycle_request"], life_request, "caller lifecycle request")
        _equal(request["lifecycle_state"], life, "caller lifecycle state")
        _equal(
            _json(request["configuration_json"], "caller configuration"),
            _scalars(configuration),
            "caller configuration",
        )
        _keys(trial, comparison.TRIAL_FIELDS, "plain caller Trial")
        _identity(trial["identity"])
        if (
            trial["request_identity"] != _identity(request["identity"])
            or trial["parent_identities"]
            != [initial["identity"], clip["identity"], life["identity"]]
            or trial["source_completed"] is not True
            or any(
                trial[name] is not None
                for name in ("failure_stage", "failure_type", "failure_message")
            )
        ):
            raise ValueError("Incomplete or mismatched final caller Trial")
        for name in comparison.CACHES:
            _cache(trial[name])
        for name in ("lattice_audit", "image_audit"):
            _cache(trial[name])
        _equal(trial["point_ids"], life["point_ids_after"], "final point IDs")
        _mask_association(trial, prelude)
        for left, right, label in (
            (initial["stream_before"], initial_request["stream_before"], "initial stream"),
            (clip["stream_after_initial"], initial["stream_after"], "clip stream"),
            (life["stream_before"], clip["stream_after"], "lifecycle stream"),
            (trial["stream_before"], seeds["stream_before"], "fresh caller initial stream"),
            (trial["stream_after"], life["stream_after"], "fresh caller final stream"),
        ):
            comparison.wire._stream(left, label)
            comparison.wire._stream(right, label)
            _equal(left, right, label)
        return selected
    except (KeyError, TypeError, IndexError, OverflowError, RecursionError) as error:
        raise ValueError("Malformed saved multi-cell lineage") from error


def saved_caller(diagnostic, parent):
    """Read authenticated, completed saved outputs; never query a process."""
    diagnostic, parent = shared.output_path(diagnostic), shared.output_path(parent)
    if any(
        (diagnostic / name).exists()
        for name in (
            "failure.json",
            "process/failure.json",
            "process/resource-stop.json",
        )
    ):
        raise ValueError("Failed diagnostic evidence cannot be compared as completed")
    result = shared.read(diagnostic / "result.json")
    recorded = shared.read(diagnostic / "diagnostic.json")
    if (
        result.get("status") != "completed_unqualified"
        or result.get("failure", True) is not None
        or result.get("diagnostic") != shared.pin(diagnostic / "diagnostic.json")
        or result.get("stop_after") != prior.ENDPOINT
        or result.get("automatic_retry") is not False
        or recorded.get("status") != "source_completed_unqualified"
        or recorded.get("stop_after") != prior.ENDPOINT
        or recorded.get("completed_stages") != list(prior.STAGES)
        or any(
            key not in recorded or recorded[key] is not None
            for key in (
                "observer_error",
                "source_error",
                "failed_stage",
                "interrupted_exception_graph",
            )
        )
    ):
        raise ValueError("Require a completed cell_index diagnostic without failures")
    plan = prior.verify_plan(parent, _identity(recorded["plan_sha256"]))
    case = recorded["case"]
    if case not in prior.CASES or case != result["case"]:
        raise ValueError("Unregistered or changed diagnostic case")
    process_path = diagnostic / "process/result.json"
    process = shared.read(process_path)
    if (
        process.get("status") != "completed"
        or type(process.get("returncode")) is not int
        or process["returncode"] != 0
        or not _same(result.get("process"), process)
        or result.get("process_receipts") != [shared.pin(process_path)]
    ):
        raise ValueError("Missing or changed completed resource-guard receipt")
    inputs = shared.read(diagnostic / "inputs.json")
    if (
        inputs.get("case") != case
        or inputs.get("stop_after") != prior.ENDPOINT
        or inputs.get("plan_sha256") != recorded["plan_sha256"]
    ):
        raise ValueError("Changed diagnostic launch inputs")
    _keys(inputs["release"], ("path", "sha256"), "release pin")
    shared.verify_pins([inputs["release"]])
    release = shared.read(inputs["release"]["path"])
    if (
        release.get("kind") != prior.KINDS[1]
        or release.get("case") != case
        or release.get("plan_sha256") != recorded["plan_sha256"]
        or release.get("snapshot_sha256") != plan["snapshot_sha256"]
        or release.get("stop_after") != prior.ENDPOINT
        or release.get("allow_actual_source_diagnostic") is not True
        or release.get("scientific_qualification") is not False
    ):
        raise ValueError("Changed retained exact diagnostic release")
    _keys(release["source_review"], ("path", "sha256"), "source review pin")
    shared.verify_pins([release["source_review"]])
    rows = recorded["captures"]
    if type(rows) is not list or len(rows) != len(prior.STAGES):
        raise ValueError("Require all eight saved capture records")
    values, paths = [], set()
    for index, (stage, row) in enumerate(zip(prior.STAGES, rows, strict=True)):
        _keys(row, ("label", "path", "status", "sha256"), "capture record")
        path = source_snapshot.relative_path(row["path"])
        if (
            row["label"] != stage
            or row["status"] != "saved"
            or path in paths
            or str(path) != f"capture-{index:04d}.json"
            or shared.pin(diagnostic / path)["sha256"] != _identity(row["sha256"])
        ):
            raise ValueError("Incomplete, changed, duplicated or reordered saved capture")
        paths.add(path)
        values.append(payload.read(diagnostic / path, expand=False))
    raw = capture_lineage(values, plan["configuration"], case)
    return dict(
        case=case,
        parent_plan=plan,
        captures=rows,
        raw=raw,
        configuration=plan["configuration"],
        owned_trial=values[-1],
    )
