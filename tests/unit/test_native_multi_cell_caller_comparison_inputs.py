"""Synthetic saved-record controls; no source, geometry, RNG or array execution."""

import copy
import hashlib
import importlib.abc
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from validation.betse import native_multi_cell_caller_comparison_inputs as reader


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def stream(position=624):
    state = ["MT19937", list(range(1, 625)), position, 0, 0.0]
    payload = dict(rng_id=reader.comparison.wire.RNG_ID, numpy_version="synthetic", state=state)
    return dict(
        state_json=json.dumps(state, separators=(",", ":")),
        numpy_version="synthetic",
        identity=digest(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()),
    )


def scalar(value):
    return dict(kind=type(value).__name__, value=value)


def mapping(items):
    return dict(kind="dict", items=[[scalar(k), v] for k, v in items])


def cache(tree=None, columns=()):
    tree = mapping([("retained", scalar(True))]) if tree is None else tree
    text = json.dumps(tree, sort_keys=True, separators=(",", ":"))
    return dict(
        descriptor_json=text, columns=list(columns), all_finite=True, identity=digest(text.encode())
    )


def mesh_cache(prelude):
    rows = [
        ("kind", scalar("owned_image_prelude_mask_token")),
        ("identity", scalar(prelude["identity"])),
        ("image_identity", scalar(prelude["image"]["identity"])),
    ]
    columns = []
    for name in reader.comparison.MASK_FIELDS[3:]:
        raw = struct.pack("<d", 0.0)
        layout = dict(
            dtype="<f8", shape=[1], strides_bytes=[8], C_contiguous=True, F_contiguous=True
        )
        rows.append(
            (
                name,
                dict(kind="numeric_array", source_layout=layout, column=name, sha256=digest(raw)),
            )
        )
        columns.append(
            dict(
                name=name,
                values=dict(
                    __ndarray__=True, dtype="<f8", shape=[1], strides=[8], raw_bytes_hex=raw.hex()
                ),
            )
        )
    return cache(mapping([("image_mask", mapping(rows))]), columns)


def lineage(directory, case=None):
    case = reader.prior.CASES[0] if case is None else case
    image_path = directory / "dense4.pgm"
    image_bytes = b"P5\n4 4\n255\n" + bytes(16)
    image_path.write_bytes(image_bytes)
    image_recipe = dict(
        kind="cells.betse_image_mask_source@1",
        filename=image_path.name,
        conf_dirname=str(directory),
        image_sha256=digest(image_bytes),
    )
    recipe = dict(
        kind="cells.betse_lattice_seed_recipe@1",
        provenance="Native scalar world controls, no image/mesh or biological geometry",
        lattice_type="SQUARE" if case == reader.prior.CASES[0] else "HEX",
        world_len_m=4e-5,
        cell_radius_m=5e-6,
        lattice_disorder=0.35,
    )
    points = dict(
        __ndarray__=True,
        dtype="<f8",
        shape=[1, 2],
        strides=[16, 8],
        raw_bytes_hex=struct.pack("<dd", 0.0, 0.0).hex(),
    )
    binding = dict(definition_json=json.dumps(recipe), parameters={}, identity="a" * 64)
    seeds = dict(
        binding_identity=binding["identity"],
        stream_before=stream(),
        stream_after=stream(7),
        values=dict(all_seed_points_m=points),
        occurrence_ids=["source-0"],
        roles=[],
        draw_order=[],
        duplicate_groups=[],
        identity="b" * 64,
    )
    kwargs = dict(
        cell_radius=5e-6,
        seed_points=points,
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
    )
    options = dict(
        smoothing=None, refinement=False, max_steps=2, convergence=1e-30, fix_bounds=True
    )
    image = dict(
        definition_json=json.dumps(image_recipe),
        native_filename=str(image_path),
        resolved_filename=str(image_path),
        file_bytes=dict(bytes_hex=image_bytes.hex()),
        file_sha256=digest(image_bytes),
        input_mode="L",
        bitmap={},
        pillow_version="synthetic",
        identity="c" * 64,
    )
    prelude = dict(
        lattice_binding_identity=binding["identity"],
        lattice_state_identity=seeds["identity"],
        image=image,
        controls_json=json.dumps(reader.prior.CONTROLS),
        stream=seeds["stream_after"],
        values={},
        active_file_pixel_ids=[],
        constructor_kwargs=kwargs,
        next_method="clip_and_refine",
        next_kwargs=options,
        identity="d" * 64,
    )
    request = dict(
        origin="owned_image_prelude",
        upstream=[binding, seeds, prelude],
        constructor_kwargs=kwargs,
        source_occurrence_ids=seeds["occurrence_ids"],
        constructor_point_ids=seeds["occurrence_ids"],
        stream_before=prelude["stream"],
        next_action="clip_to_curve(owned_image_mask)",
        identity="e" * 64,
    )
    raw = dict(
        seed_recipe=recipe,
        seed_stream_before=json.loads(seeds["stream_before"]["state_json"]),
        controls=reader.prior.CONTROLS,
        image_recipe=image_recipe,
        classification="native_lattice_and_owned_image_source_inputs",
        upstream_accuracy_qualification="open",
        image_bytes_hex=image_bytes.hex(),
        lifecycle_case=case,
        native_option_recipe=None,
    )
    first = dict(
        request=request, native_comparison_inputs=raw, configuration=reader.prior.configuration()
    )
    initial = dict(
        request_identity=request["identity"],
        constructed_cache=cache(),
        cache=cache(),
        events=[],
        retained_point_ids=["source-0"],
        stream_before=prelude["stream"],
        stream_after_constructor=stream(8),
        stream_after=stream(9),
        warnings=[],
        constructor_completed=True,
        pre_mesh_completed=True,
        status="source_completed_unqualified",
        failure_stage=None,
        failure_type=None,
        failure_message=None,
        identity="f" * 64,
    )
    clip_request = dict(initial_request=request, initial_state=initial, identity="1" * 64)
    clip = dict(
        request_identity=clip_request["identity"],
        initial_cache=initial["cache"],
        cache=cache(),
        events=[],
        parent_point_ids=initial["retained_point_ids"],
        derived_point_ids_before_rebuild=["derived-0"],
        retained_point_ids=["derived-0"],
        stream_after_initial=initial["stream_after"],
        stream_after=stream(10),
        warnings=[],
        status="source_clipped_rebuilt_unqualified",
        failure_stage=None,
        failure_type=None,
        failure_message=None,
        identity="2" * 64,
    )
    life_request = dict(
        clip_request=clip_request,
        clip_state=clip,
        origin="owned_make_voronoi_lifecycle",
        options_json=json.dumps(options),
        identity="3" * 64,
    )
    life = dict(
        request_identity=life_request["identity"],
        before_cache=clip["cache"],
        cache=cache(),
        events=[],
        point_ids_before=clip["retained_point_ids"],
        point_ids_after=["derived-0"],
        stream_before=clip["stream_after"],
        stream_after=stream(11),
        termination_json="{}",
        warnings=[],
        status="source_lifecycle_completed_unqualified",
        failure_stage=None,
        failure_type=None,
        failure_message=None,
        identity="4" * 64,
    )
    caller_request = dict(
        lifecycle_request=life_request,
        lifecycle_state=life,
        configuration_json=json.dumps(reader.prior.configuration()),
        identity="5" * 64,
    )
    trial = dict(
        request_identity=caller_request["identity"],
        parent_identities=[initial["identity"], clip["identity"], life["identity"]],
        parameter_cache=cache(),
        caller_cache=cache(),
        mesh_cache=mesh_cache(prelude),
        lattice_audit=cache(),
        image_audit=cache(),
        stages=[],
        events=[],
        ordering=[],
        point_ids=life["point_ids_after"],
        stream_before=seeds["stream_before"],
        stream_after=life["stream_after"],
        warnings=[],
        work=[],
        source_completed=True,
        failure_stage=None,
        failure_type=None,
        failure_message=None,
        identity="6" * 64,
    )
    # Saved records are separate JSON values, never shared in-memory objects.
    return json.loads(
        json.dumps(
            reader.shared.archive.snapshot(
                [first, initial, clip_request, clip, life_request, life, caller_request, trial]
            )
        )
    )


def packet(root, case):
    prepared, diagnostic, native_root = root / "prepared", root / "diagnostic", root / "native"
    prepared.mkdir()
    diagnostic.mkdir()
    native_root.mkdir()
    values = lineage(diagnostic, case)
    source = prepared / "source"
    source.mkdir()
    default = native_root / "defaults.yaml"
    default.write_text("# synthetic metadata only\n")
    files = {reader.prior.OWN: "raise AssertionError('source execution forbidden')\n"}
    pins = [reader.shared.pin(default)]
    for i, (name, prefix) in enumerate(reader.prior.SOURCE_TABLES):
        path = native_root / prefix / f"original-{i}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("raise AssertionError('native import forbidden')\n")
        pins.append(reader.shared.pin(path))
        files[name] = "NATIVE_PINS = " + repr({path.name: digest(path.read_bytes())})
    records = {}
    for name, text in files.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        path.chmod(0o444)
        records[name] = dict(
            checkout_path=name,
            sha256=digest(path.read_bytes()),
            observation=dict(size=path.stat().st_size),
            snapshot_mode=0o444,
        )
    (source / "checkout.patch").write_text("")
    write(
        source / "SNAPSHOT.json",
        dict(
            kind="cells.checkout_source_snapshot@1",
            status="complete",
            immutable=True,
            files=records,
            patch_sha256=digest(b""),
        ),
    )
    for path in sorted(source.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)
    source.chmod(0o555)
    plan = dict(
        kind=reader.prior.KINDS[0],
        purpose="multi_cell_caller_source_diagnostic_only",
        cases=list(reader.prior.CASES),
        configuration=reader.prior.configuration(),
        fixture_controls=reader.prior.CONTROLS,
        limits=reader.shared.LIMITS,
        stop_after=reader.prior.ENDPOINT,
        execution_stages=list(reader.prior.STAGES),
        cpu=5,
        automatic_retry=False,
        source_review_required_before_release=True,
        snapshot_sha256=reader.shared.pin(source / "SNAPSHOT.json")["sha256"],
        runner_sha256=reader.shared.pin(source / reader.prior.OWN)["sha256"],
        external_inputs=pins,
        **reader.shared.NO_CREDIT,
    )
    write(prepared / "plan.json", plan)
    plan_sha = reader.shared.pin(prepared / "plan.json")["sha256"]
    review = root / "review.json"
    write(review, dict(scope="synthetic metadata only"))
    release = root / "release.json"
    write(
        release,
        dict(
            kind=reader.prior.KINDS[1],
            case=case,
            plan_sha256=plan_sha,
            snapshot_sha256=plan["snapshot_sha256"],
            stop_after=reader.prior.ENDPOINT,
            allow_actual_source_diagnostic=True,
            scientific_qualification=False,
            source_review=reader.shared.pin(review),
        ),
    )
    rows = []
    for index, (stage, value) in enumerate(zip(reader.prior.STAGES, values, strict=True)):
        path = diagnostic / f"capture-{index:04d}.json"
        write(path, value)
        rows.append(
            dict(
                label=stage,
                path=path.name,
                status="saved",
                sha256=reader.shared.pin(path)["sha256"],
            )
        )
    recorded = dict(
        status="source_completed_unqualified",
        stop_after=reader.prior.ENDPOINT,
        completed_stages=list(reader.prior.STAGES),
        observer_error=None,
        source_error=None,
        failed_stage=None,
        interrupted_exception_graph=None,
        plan_sha256=plan_sha,
        case=case,
        captures=rows,
        **reader.shared.NO_CREDIT,
    )
    write(diagnostic / "diagnostic.json", recorded)
    process = dict(status="completed", returncode=0, limits=reader.shared.LIMITS)
    write(diagnostic / "process/result.json", process)
    write(
        diagnostic / "inputs.json",
        dict(
            case=case,
            stop_after=reader.prior.ENDPOINT,
            plan_sha256=plan_sha,
            release=reader.shared.pin(release),
        ),
    )
    result = dict(
        status="completed_unqualified",
        failure=None,
        case=case,
        stop_after=reader.prior.ENDPOINT,
        automatic_retry=False,
        diagnostic=reader.shared.pin(diagnostic / "diagnostic.json"),
        process=process,
        process_receipts=[reader.shared.pin(diagnostic / "process/result.json")],
        **reader.shared.NO_CREDIT,
    )
    write(diagnostic / "result.json", result)
    return prepared, diagnostic, default, native_root


class SavedCallerInputsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.attempts = []
        attempts = self.attempts

        class Block(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax", "PIL"}:
                    attempts.append(fullname)
                    raise AssertionError("Forbidden scientific import: " + fullname)

        block = Block()
        sys.meta_path.insert(0, block)
        self.addCleanup(sys.meta_path.remove, block)
        for obj, name in (
            (reader.native, "evaluate"),
            (reader.native.runtime, "build"),
            (reader.prior, "_steps"),
            (reader.prior, "launch"),
        ):
            patch = mock.patch.object(obj, name, side_effect=AssertionError("Execution forbidden"))
            patch.start()
            self.addCleanup(patch.stop)

    def tearDown(self):
        self.assertEqual(self.attempts, [])
        for path in self.root.rglob("*"):
            if path.is_dir() and not path.is_symlink():
                path.chmod(0o755)
        self.temp.cleanup()

    def saved(self):
        result = packet(self.root, reader.prior.CASES[0])
        prepared, diagnostic, defaults, native_root = result
        for name, value in (
            ("BASE", self.root),
            ("NATIVE", native_root),
            ("DEFAULTS", defaults),
            ("DEFAULTS_SHA256", reader.shared.pin(defaults)["sha256"]),
        ):
            patch = mock.patch.object(reader.shared, name, value)
            patch.start()
            self.addCleanup(patch.stop)
        return prepared, diagnostic

    def assert_bad(self, values, case=None):
        with self.assertRaises(ValueError):
            reader.capture_lineage(
                values, reader.prior.configuration(), case or reader.prior.CASES[0]
            )

    def test_two_registered_lineages_select_only_four_raw_keys(self):
        for case in reader.prior.CASES:
            with self.subTest(case=case):
                values = lineage(self.root, case)
                before = copy.deepcopy(values)
                raw = reader.capture_lineage(values, reader.prior.configuration(), case)
                self.assertEqual(list(raw), list(reader.RAW_FIELDS))
                self.assertEqual(
                    raw,
                    {
                        name: values[0]["native_comparison_inputs"][name]
                        for name in reader.RAW_FIELDS
                    },
                )
                self.assertEqual(values, before)

    def test_missing_reordered_and_extra_capture_values_refuse(self):
        original = lineage(self.root)
        for index in range(8):
            with self.subTest(index=index):
                values = copy.deepcopy(original)
                values.pop(index)
                self.assert_bad(values)
        values = copy.deepcopy(original)
        values[2], values[3] = values[3], values[2]
        self.assert_bad(values)
        self.assert_bad([*original, original[-1]])
        self.assert_bad(original, "unregistered")

    def test_prerequisite_and_final_failed_markers_refuse(self):
        original = lineage(self.root)
        for index in (1, 3, 5, 7):
            for field, value in (
                ("failure_stage", "raw"),
                ("failure_type", "ValueError"),
                ("failure_message", ""),
            ):
                with self.subTest(index=index, field=field):
                    values = copy.deepcopy(original)
                    values[index][field] = value
                    self.assert_bad(values)
        for index, field, value in (
            (1, "constructor_completed", False),
            (1, "pre_mesh_completed", 1),
            (3, "status", "failed"),
            (5, "status", "other"),
            (7, "source_completed", 1),
        ):
            values = copy.deepcopy(original)
            values[index][field] = value
            self.assert_bad(values)

    def test_repeated_request_and_state_content_not_just_ids(self):
        original = lineage(self.root)
        for index, field in (
            (2, "initial_request"),
            (2, "initial_state"),
            (4, "clip_request"),
            (4, "clip_state"),
            (6, "lifecycle_request"),
            (6, "lifecycle_state"),
        ):
            with self.subTest(index=index, field=field):
                values = copy.deepcopy(original)
                values[index][field]["unrecorded_drift"] = True
                self.assert_bad(values)

    def test_original_request_and_parent_identity_order(self):
        original = lineage(self.root)
        for index in (1, 3, 5, 7):
            values = copy.deepcopy(original)
            values[index]["request_identity"] = "9" * 64
            self.assert_bad(values)
        values = copy.deepcopy(original)
        values[7]["parent_identities"].reverse()
        self.assert_bad(values)
        values = copy.deepcopy(original)
        values[6]["grid_descriptor"] = "ordinary"
        self.assert_bad(values)
        values = copy.deepcopy(original)
        values[7]["descriptor_proof"] = []
        self.assert_bad(values)

    def test_raw_fixture_case_controls_and_recipe_refuse(self):
        original = lineage(self.root)
        changes = [
            ("lifecycle_case", reader.prior.CASES[1]),
            ("native_option_recipe", {}),
            ("classification", "manufactured"),
            ("upstream_accuracy_qualification", "passed"),
        ]
        for name, value in changes:
            values = copy.deepcopy(original)
            values[0]["native_comparison_inputs"][name] = value
            self.assert_bad(values)
        for field, value in (
            ("single_cell", True),
            ("refine_mesh", True),
            ("maximum_voronoi_steps", 3),
        ):
            values = copy.deepcopy(original)
            values[0]["native_comparison_inputs"]["controls"][field] = value
            self.assert_bad(values)
        values = copy.deepcopy(original)
        values[0]["native_comparison_inputs"]["seed_recipe"]["lattice_disorder"] = 0.2
        self.assert_bad(values)
        values = copy.deepcopy(original)
        values[0]["native_comparison_inputs"]["extra"] = None
        self.assert_bad(values)

    def test_seed_prelude_constructor_and_image_associations(self):
        original = lineage(self.root)
        for target, field, value in (
            (0, "definition_json", "{}"),
            (1, "binding_identity", "9" * 64),
            (2, "lattice_state_identity", "9" * 64),
            (2, "controls_json", "{}"),
            (2, "next_method", "init_mesh"),
            (2, "next_kwargs", {}),
        ):
            values = copy.deepcopy(original)
            values[0]["request"]["upstream"][target][field] = value
            self.assert_bad(values)
        for field, value in (("image_mask", {}), ("make_all_operators", True), ("seed_points", {})):
            values = copy.deepcopy(original)
            values[0]["request"]["constructor_kwargs"][field] = value
            self.assert_bad(values)
        for field, value in (
            ("file_sha256", "9" * 64),
            ("native_filename", "/wrong/image"),
            ("file_bytes", {"bytes_hex": "00"}),
            ("definition_json", "{}"),
        ):
            values = copy.deepcopy(original)
            values[0]["request"]["upstream"][2]["image"][field] = value
            self.assert_bad(values)

    def test_stream_handoffs_reject_valid_resealed_wrong_stream(self):
        original = lineage(self.root)
        for index, field in (
            (1, "stream_before"),
            (3, "stream_after_initial"),
            (5, "stream_before"),
            (7, "stream_before"),
            (7, "stream_after"),
        ):
            values = copy.deepcopy(original)
            values[index][field] = stream(59)
            self.assert_bad(values)
        values = copy.deepcopy(original)
        values[0]["native_comparison_inputs"]["seed_stream_before"][2] = 17
        self.assert_bad(values)

    def test_final_mask_token_names_original_prelude_and_image(self):
        original = lineage(self.root)
        for position in (0, 1, 2):
            values = copy.deepcopy(original)
            owned = values[-1]["mesh_cache"]
            tree = json.loads(owned["descriptor_json"])
            tree["items"][0][1]["items"][position][1]["value"] = "9" * 64
            values[-1]["mesh_cache"] = cache(tree, owned["columns"])
            self.assert_bad(values)
        values = copy.deepcopy(original)
        values[-1]["mesh_cache"]["identity"] = "0" * 64
        self.assert_bad(values)

    def test_complete_saved_packet_real_pin_and_snapshot_validators(self):
        parent, diagnostic = self.saved()
        result = reader.saved_caller(diagnostic, parent)
        self.assertEqual(
            set(result), {"case", "parent_plan", "captures", "raw", "configuration", "owned_trial"}
        )
        self.assertEqual(result["case"], reader.prior.CASES[0])
        self.assertEqual(len(result["captures"]), 8)
        self.assertEqual(result["owned_trial"]["identity"], "6" * 64)

    def test_capture_bytes_or_missing_file_are_rejected(self):
        parent, diagnostic = self.saved()
        path = diagnostic / "capture-0003.json"
        old = path.read_bytes()
        path.write_bytes(old + b" ")
        with self.assertRaises(ValueError):
            reader.saved_caller(diagnostic, parent)
        path.unlink()
        with self.assertRaises((ValueError, FileNotFoundError)):
            reader.saved_caller(diagnostic, parent)

    def test_capture_order_duplicate_status_and_escape_reject_even_resealed(self):
        parent, diagnostic = self.saved()
        original = reader.shared.read(diagnostic / "diagnostic.json")
        result = reader.shared.read(diagnostic / "result.json")
        for change in ("order", "duplicate", "status", "escape", "label"):
            with self.subTest(change=change):
                altered = copy.deepcopy(original)
                rows = altered["captures"]
                if change == "order":
                    rows[1], rows[2] = rows[2], rows[1]
                elif change == "duplicate":
                    rows[2]["path"] = rows[1]["path"]
                elif change == "status":
                    rows[2]["status"] = "capture_failed"
                elif change == "escape":
                    rows[2]["path"] = "../outside.json"
                else:
                    rows[2]["label"] = "not_declared"
                write(diagnostic / "diagnostic.json", altered)
                result["diagnostic"] = reader.shared.pin(diagnostic / "diagnostic.json")
                write(diagnostic / "result.json", result)
                with self.assertRaises(ValueError):
                    reader.saved_caller(diagnostic, parent)

    def test_failed_result_observer_and_resource_receipts_refuse(self):
        parent, diagnostic = self.saved()
        for name in ("failure.json", "process/failure.json", "process/resource-stop.json"):
            path = diagnostic / name
            write(path, dict(status="failed"))
            with self.assertRaises(ValueError):
                reader.saved_caller(diagnostic, parent)
            path.unlink()
        result = reader.shared.read(diagnostic / "result.json")
        result["failure"] = {}
        write(diagnostic / "result.json", result)
        with self.assertRaises(ValueError):
            reader.saved_caller(diagnostic, parent)

    def test_completed_top_summary_cannot_hide_observer_or_process_error(self):
        parent, diagnostic = self.saved()
        recorded = reader.shared.read(diagnostic / "diagnostic.json")
        result = reader.shared.read(diagnostic / "result.json")
        for field in (
            "source_error",
            "observer_error",
            "interrupted_exception_graph",
            "failed_stage",
        ):
            changed = copy.deepcopy(recorded)
            changed[field] = "failure"
            write(diagnostic / "diagnostic.json", changed)
            result["diagnostic"] = reader.shared.pin(diagnostic / "diagnostic.json")
            write(diagnostic / "result.json", result)
            with self.assertRaises(ValueError):
                reader.saved_caller(diagnostic, parent)
        write(diagnostic / "diagnostic.json", recorded)
        result["diagnostic"] = reader.shared.pin(diagnostic / "diagnostic.json")
        write(diagnostic / "result.json", result)
        write(diagnostic / "process/result.json", dict(status="completed", returncode=1))
        with self.assertRaises(ValueError):
            reader.saved_caller(diagnostic, parent)

    def test_parent_snapshot_external_release_and_review_pins(self):
        parent, diagnostic = self.saved()
        original = reader.shared.read(parent / "plan.json")
        native = Path(original["external_inputs"][1]["path"])
        saved = native.read_bytes()
        native.write_bytes(saved + b"# changed\n")
        with self.assertRaises(ValueError):
            reader.saved_caller(diagnostic, parent)
        native.write_bytes(saved)
        review = self.root / "review.json"
        review.write_text("{}")
        with self.assertRaises(ValueError):
            reader.saved_caller(diagnostic, parent)

    def test_parent_source_drift_refused_without_live_fallback(self):
        parent, diagnostic = self.saved()
        source = parent / "source" / reader.prior.OWN
        source.chmod(0o644)
        source.write_text("# unbound new source\n")
        source.chmod(0o444)
        with self.assertRaises(ValueError):
            reader.saved_caller(diagnostic, parent)

    def test_sidecar_payload_is_authenticated_without_expansion(self):
        parent, diagnostic = self.saved()
        path = diagnostic / "capture-0001.json"
        recorded = reader.shared.read(diagnostic / "diagnostic.json")
        values = [
            reader.payload.read(diagnostic / row["path"], expand=False)
            for row in recorded["captures"]
        ]
        size = reader.payload.THRESHOLD
        raw = bytes(size)
        node = dict(
            kind="numeric_array",
            column="retained",
            sha256=digest(raw),
            source_layout=dict(
                dtype="|u1", shape=[size], strides_bytes=[1], C_contiguous=True, F_contiguous=True
            ),
        )
        column = dict(
            name="retained",
            values=dict(
                __ndarray__=True, dtype="|u1", shape=[size], strides=[1], raw_bytes_hex=raw.hex()
            ),
        )
        values[1]["constructed_cache"] = cache(mapping([("retained", node)]), [column])
        values[2]["initial_state"] = copy.deepcopy(values[1])
        values[4]["clip_request"] = copy.deepcopy(values[2])
        values[6]["lifecycle_request"] = copy.deepcopy(values[4])
        for value, row in zip(values, recorded["captures"], strict=True):
            target = diagnostic / row["path"]
            target.unlink()
            reader.payload.write(target, value)
            row["sha256"] = reader.shared.pin(target)["sha256"]
        write(diagnostic / "diagnostic.json", recorded)
        result = reader.shared.read(diagnostic / "result.json")
        result["diagnostic"] = reader.shared.pin(diagnostic / "diagnostic.json")
        write(diagnostic / "result.json", result)
        self.assertEqual(reader.saved_caller(diagnostic, parent)["case"], reader.prior.CASES[0])
        retained = reader.payload.read(path, expand=False)["constructed_cache"]["columns"][0][
            "values"
        ]
        self.assertEqual(retained["raw_bytes_hex"], {reader.payload.TOKEN: digest(raw)})
        sidecar = next(path.with_name(path.name + ".arrays").glob("*.bin"))
        sidecar.unlink()
        with self.assertRaisesRegex(ValueError, "sidecar"):
            reader.saved_caller(diagnostic, parent)


if __name__ == "__main__":
    unittest.main()
