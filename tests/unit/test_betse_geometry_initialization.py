"""Authenticated generated-geometry bridge; B09/RNG coverage remains reused."""

import json
import os
import shutil
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.core.specs import digest
from cells.processes import betse_environment_field as field
from cells.processes import betse_geometry_initialization as initialization
from cells.processes import betse_normal_current as current
from cells.processes import betse_perturbations as streams
from validation.betse import betse_environment_field_checks as field_checks
from validation.betse import betse_environment_field_native as field_native
from validation.betse import betse_environment_field_reference as field_reference
from validation.betse import betse_geometry_initialization_fixtures as fixtures
from validation.betse import betse_geometry_initialization_native as native
from validation.betse import betse_geometry_initialization_reference as reference


def write(name, record, columns=None, *, category="geometry-initialization"):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        root = Path(directory) / category
        root.mkdir(parents=True, exist_ok=True)
        if columns is not None:
            with (root / (name + ".npz")).open("xb") as stream:
                np.savez_compressed(stream, **columns)
                stream.flush()
                os.fsync(stream.fileno())
        with (root / (name + ".json")).open("x") as stream:
            json.dump(field.plain(record), stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())


def setup(case=fixtures.CASES[0]):
    data = fixtures.fixture(case)
    recipe = initialization.bind(data["recipe"])
    seed = initialization.initialise(recipe)
    capture = initialization.load_initialization(
        recipe, seed, receipt_path=fixtures.ROOT / "result.json"
    )
    return data, recipe, seed, capture


def numeric_seed(value):
    return {
        key: np.asarray(getattr(value, key)) for key in ("points_m", "x_uniforms", "y_uniforms")
    }


@pytest.mark.parametrize("case", fixtures.CASES)
def test_exact_native_seed_provenance_and_independent_coordinates(case):
    data = fixtures.fixture(case)
    recipe = initialization.bind(data["recipe"])
    global_before = np.random.get_state()
    seed = initialization.initialise(recipe)
    before = streams.native_stream_manifest(seed.stream_before)["state"]
    proof = native.evaluate(data["recipe"], before)
    first = reference.evaluate_seed(data["recipe"], before)
    second = reference.evaluate_seed(data["recipe"], before, refinement=2)
    columns = {"actual__" + key: value for key, value in numeric_seed(seed).items()}
    for prefix, values in (("native", proof), ("reference", first), ("refined", second)):
        columns.update({prefix + "__" + key: np.asarray(values[key]) for key in numeric_seed(seed)})
    write(
        case,
        dict(
            mode="seed_precomparison",
            inputs=data,
            seed_state=initialization.seed_record(seed),
            native=proof,
            reference=first,
            refined_reference=second,
        ),
        columns,
        category="geometry-initialization-raw",
    )
    for key, value in numeric_seed(seed).items():
        np.testing.assert_array_equal(value, proof[key], err_msg=key)
        if key != "points_m":
            np.testing.assert_array_equal(value, first[key], err_msg=key)
        target = np.asarray(first[key])
        assert np.max(abs(value - target) / (1e-27 + 6e-12 * abs(target)), initial=0) <= 1
        assert (
            np.max(abs(target - np.asarray(second[key])) / (1e-27 + 6e-12 * abs(target)), initial=0)
            <= 0.1
        )
    after = streams.native_stream_manifest(seed.stream_after)["state"]
    assert digest(after) == digest(proof["rng_after"]) == digest(first["rng_after"])
    global_after = np.random.get_state()
    assert (
        global_before[0] == global_after[0]
        and np.array_equal(global_before[1], global_after[1])
        and global_before[2:] == global_after[2:]
    )
    assert proof["original_global_rng_unchanged"]
    write(
        "seed-" + case,
        dict(
            mode="complete_seed_provenance",
            inputs=data,
            seed_state=initialization.seed_record(seed),
            native_source_sites=proof["source_sites"],
            native_source_sha256=proof["native_source_sha256"],
            reference=first,
            refined_reference=second,
            B09_geometry_and_MT19937_coverage_reused=True,
            biological_geometry=False,
        ),
        columns,
    )


@pytest.mark.parametrize("case", fixtures.CASES)
def test_authenticated_geometry_to_environment_without_metric_overrides(case):
    data, recipe, seed, capture = setup(case)
    source = capture.source
    metrics = reference.geometry_metrics(source)
    c = source["generation"]["native_capture_record"]["cells"]
    write(
        "bridge-" + case,
        dict(
            mode="authenticated_geometry_precomparison",
            inputs=data,
            initialization_identity=capture.identity,
            authentication=capture.authentication,
            generated_source=source,
            independent_metrics=metrics,
        ),
        category="geometry-initialization-raw",
    )
    for key, absolute in (
        ("cell_centres", 1e-27),
        ("mem_mids_flat", 1e-27),
        ("mem_sa", 1e-26),
        ("cell_sa", 1e-26),
        ("cell_vol", 1e-30),
    ):
        value, target = np.asarray(c[key]), np.asarray(metrics[key])
        assert np.max(abs(value - target) / (absolute + 6e-12 * abs(target)), initial=0) <= 1, key
    np.testing.assert_array_equal(c["mem_to_cells"], metrics["mem_to_cells"])
    try:
        prepared = initialization.prepare_environment(capture, data["material"])
    except field.EnvironmentFieldRejected as error:
        # This is the pre-existing explicit narrower nearest-map admission,
        # never a tolerated field/geometry numerical accuracy failure.
        assert error.stage == "nearest_mapping" and error.trial is not None
        trial = error.trial
        assert not np.all(trial["unique"])
        points, queries = trial["grid_points"], trial["query_points"]
        distance = np.sqrt(np.sum((queries[:, None, :] - points[None, :, :]) ** 2, axis=-1))
        ordered = np.sort(distance, axis=1)
        gap = ordered[:, 1] - ordered[:, 0]
        assert np.any(gap <= 64 * np.finfo(float).eps * np.maximum(ordered[:, 1], trial["delta_m"]))
        with pytest.raises(ValueError, match="ambiguous"):
            field_reference.geometry(error.generated_definition, precision=100)
        write(
            "bridge-" + case,
            dict(
                mode="inherited_nearest_mapping_refusal",
                inputs=data,
                initialization_identity=capture.identity,
                authentication=capture.authentication,
                reason=str(error),
                field_geometry_classification=recipe.declaration["classification"],
                source_geometry_reused_B09=True,
                mapping_source=error.source,
                generated_field_definition=error.generated_definition,
                no_metric_override=True,
            ),
            {"trial__" + key: value for key, value in field_checks.flat(trial).items()},
        )
        return
    initialization.validate_preparation(capture, prepared)
    definition = prepared.binding.definition
    np.testing.assert_array_equal(definition["geometry"]["cell_centres_m"], c["cell_centres"])
    np.testing.assert_array_equal(
        definition["geometry"]["membrane_midpoints_m"], c["mem_mids_flat"]
    )
    np.testing.assert_array_equal(definition["geometry"]["cell_volume_m3"], c["cell_vol"])
    np.testing.assert_array_equal(
        definition["current_definition"]["geometry"]["membrane_area_m2"], c["mem_sa"]
    )
    inputs = fixtures.readout(definition)
    frame = inputs["frames"][0]
    prefix = current.evaluate(
        prepared.binding.current_binding,
        current.inputs(prepared.binding.current_binding, **frame["current"]),
    )
    output = field.evaluate(prepared.binding, prefix, frame["environment"])
    geometry = prepared.binding.geometry._asdict()
    geometry.pop("diagnostics")
    observed = dict(
        geometry=geometry,
        cache=prepared.binding.cache,
        frames=[
            dict(
                values=output.values,
                smoothing_hodge=output.smoothing_hodge,
                current_hodge=output.current_hodge,
                current=dict(values=prefix.values),
            )
        ],
    )
    proof = field_native.evaluate(inputs)
    first, second = field_reference.evaluate(inputs), field_reference.evaluate(inputs, refinement=2)
    categories = {
        category + "__" + key.replace(".", "__"): value
        for category, values in (
            ("actual", observed),
            ("native", proof),
            ("reference", first),
            ("refined", second),
        )
        for key, value in field_checks.source_arrays(values).items()
    }
    write(
        "field-" + case,
        dict(
            mode="field_precomparison",
            inputs=inputs,
            reference=first,
            refined_reference=second,
            generated_source=source,
        ),
        categories,
        category="geometry-initialization-raw",
    )
    field_checks.compare(
        dict(geometry=geometry, cache=prepared.binding.cache),
        dict(geometry=proof["geometry"], cache=proof["cache"]),
        exact=True,
    )
    field_checks.compare(
        field_checks.data_frame(observed["frames"][0]),
        field_checks.data_frame(proof["frames"][0]),
        exact=True,
    )
    maximum = field_checks.compare(
        dict(geometry=geometry, cache=prepared.binding.cache),
        dict(geometry=first["geometry"], cache=first["cache"]),
    )
    maximum = max(
        maximum,
        field_checks.compare(
            field_checks.data_frame(observed["frames"][0]),
            field_checks.data_frame(first["frames"][0]),
            gross=first["frames"][0]["current"]["gross"],
            factor=field_checks.prefix_factor(definition),
        ),
    )
    resolution = field_checks.compare(
        field_checks.data_frame(first["frames"][0]),
        field_checks.data_frame(second["frames"][0]),
        gross=second["frames"][0]["current"]["gross"],
        factor=field_checks.prefix_factor(definition),
    )
    assert resolution <= 0.1
    write(
        "bridge-" + case,
        dict(
            mode="complete_generated_environment_bridge",
            inputs=data,
            field_inputs=inputs,
            initialization_identity=capture.identity,
            seed_state=initialization.seed_record(seed),
            authentication=capture.authentication,
            provenance=json.loads(prepared.provenance_json),
            fields=list(field_checks.source_arrays(observed)),
            native_source_sha256=proof["native_source_sha256"],
            maximum_error_fraction=maximum,
            maximum_reference_resolution_fraction=resolution,
            reference=first,
            refined_reference=second,
            full_refined_buffers_retained=True,
            new_B09_generation_coverage=False,
            classification=recipe.declaration["classification"],
            no_metric_override=True,
            biological_geometry=False,
            full_make_world=False,
        ),
        categories,
    )


def test_generated_preset_is_ring_plus_centre_and_cloud_is_manufactured():
    _, recipe, seed, _ = setup()
    assert len(seed.points_m) == recipe.declaration["native_input"]["mesh"]["single_cell_sides"] + 1
    assert seed.draw_order == (("noisex", 7), ("noisey", 7))
    data = fixtures.fixture("irregular-centroid-aux")
    cloud = initialization.initialise(initialization.bind(data["recipe"]))
    assert cloud.draw_order == () and cloud.stream_before == cloud.stream_after


def test_zero_noise_still_consumes_uniform_draws_and_preserves_global_stream():
    data = fixtures.fixture()
    data["recipe"]["native_input"]["mesh"]["single_cell_noise"] = 0.0
    recipe = initialization.bind(data["recipe"])
    seed = initialization.initialise(recipe)
    assert seed.stream_before.identity != seed.stream_after.identity
    assert len(seed.x_uniforms) == len(seed.y_uniforms) == 7
    with pytest.raises(ValueError, match="input/capture"):
        initialization.load_initialization(recipe, seed)


@pytest.mark.parametrize("target", ("draw", "cache", "point"))
def test_changed_seed_state_and_exact_cache_refuse(target):
    _, recipe, seed, _ = setup()
    if target == "draw":
        seed = replace(seed, x_uniforms=field.frozen(np.zeros(7)))
    elif target == "point":
        points = seed.points_m.copy()
        points[0, 0] += 1e-7
        seed = replace(seed, points_m=field.frozen(points))
    else:
        manifest = streams.native_stream_manifest(seed.stream_after)
        state = manifest["state"]
        state[3], state[4] = 1, 0.123
        changed = streams._native_stream(state, np.__version__)
        seed = replace(seed, stream_after=changed)
    seed = replace(seed, identity=current._digest(initialization.seed_record(seed)))
    with pytest.raises(ValueError, match="draw ordering|seed coordinates"):
        initialization.load_initialization(recipe, seed)


@pytest.mark.parametrize("target", ("centre", "volume", "area", "radius"))
def test_caller_metric_overrides_are_not_an_input(target):
    data, _, _, capture = setup()
    if target == "radius":
        data["material"]["constants"]["cell_radius_m"] = 1.0
    else:
        data["material"][target] = 1.0
    with pytest.raises(ValueError, match="constants|overrides"):
        initialization.prepare_environment(capture, data["material"])


def test_resealed_embedded_generation_is_reauthenticated():
    _, recipe, seed, capture = setup()
    source = capture.source
    source["generation"]["native_capture_record"]["cells"]["cell_vol"][0] *= 1.01
    altered = replace(
        capture,
        source_json=json.dumps(source, sort_keys=True, separators=(",", ":")),
        identity=digest(
            dict(
                recipe=recipe.identity,
                seed_state=seed.identity,
                source=source,
                authentication=capture.authentication,
            )
        ),
    )
    with pytest.raises(ValueError, match="authenticated B09"):
        initialization.validate_initialization(altered)


def test_damaged_capture_cannot_be_authenticated_by_caller_checksum(tmp_path):
    _, recipe, seed, _ = setup()
    shutil.copyfile(fixtures.ROOT / "result.json", tmp_path / "result.json")
    (tmp_path / "native-source").mkdir()
    for name in ("source-manifest.json", recipe.declaration["native_input"]["name"] + ".json"):
        shutil.copyfile(fixtures.ROOT / "native-source" / name, tmp_path / "native-source" / name)
    path = tmp_path / "native-source" / (recipe.declaration["native_input"]["name"] + ".json")
    source = json.loads(path.read_text())
    source["cells"]["mem_sa"][0] *= 1.01
    path.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="differs from qualified B09"):
        initialization.load_initialization(recipe, seed, receipt_path=tmp_path / "result.json")


@pytest.mark.parametrize(
    "defect",
    ("lattice", "image", "refinement", "alpha", "merge", "manufactured_native", "oversize_grid"),
)
def test_unsupported_full_world_or_mislabeled_geometry_refuses(defect):
    data = fixtures.fixture()
    raw = data["recipe"]
    if defect == "lattice":
        raw["classification"] = "native_square_lattice"
    elif defect in ("image", "refinement"):
        raw["native_input"][defect] = True
    elif defect in ("alpha", "merge"):
        raw["native_input"]["mesh"]["use_alpha_shape" if defect == "alpha" else "allow_merging"] = (
            True
        )
    elif defect == "manufactured_native":
        raw["native_input"]["seed_points_m"] = [[0.0, 0.0]] * 7
    else:
        raw["native_input"]["cell"]["grid_size"] = 8
    with pytest.raises(ValueError):
        initialization.bind(raw)


def test_declaration_seed_buffers_are_immutable_and_no_biological_claim():
    _, recipe, seed, capture = setup()
    for value in numeric_seed(seed).values():
        with pytest.raises(ValueError):
            value.setflags(write=True)
    assert not capture.authentication["biological_geometry"]
    assert recipe.declaration["classification"] == "native_generated_ring_and_centre"
