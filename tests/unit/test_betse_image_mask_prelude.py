"""Prepared image-prelude checks; no numerical launch is implied by this file."""

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import numpy as np
import pytest

from cells.processes import betse_image_mask_prelude as prelude
from cells.processes import betse_lattice_seed_generation as lattice
from cells.processes import betse_normal_current as records
from cells.processes import betse_perturbations as streams
from validation.betse import betse_image_mask_prelude_fixtures as fixtures
from validation.betse import betse_image_mask_prelude_native as native
from validation.betse import betse_image_mask_prelude_reference as reference
from validation.betse import betse_lattice_seed_generation_fixtures as seed_fixtures


def seed(lattice_type="SQUARE", single_cell=False):
    case = (
        ("square_twist_cache" if single_cell else "square_disordered")
        if lattice_type == "SQUARE"
        else ("hex_cached" if single_cell else "hex_disordered")
    )
    raw = seed_fixtures.fixture(case)
    setup = raw["stream_setup"]
    rng = np.random.RandomState(setup["seed"])
    rng.random(setup["warmup_uniforms"])
    saved = rng.get_state()
    stream = streams._native_stream(
        [saved[0], saved[1].tolist(), int(saved[2]), setup["has_gauss"], setup["cached_gaussian"]],
        np.__version__,
    )
    binding = lattice.bind(raw["recipe"])
    return binding, lattice.generate(binding, stream)


def geometry(binding, state):
    return dict(
        bounds_m=state.values.axis_bounds_m,
        all_seed_points_m=state.values.all_seed_points_m,
        centre_m=state.values.centre_m,
        cell_radius_m=binding.parameters.cell_radius_m,
        lattice_type=binding.definition["lattice_type"],
    )


def save(label, record, columns=None, image_bytes=None):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        root = Path(directory) / "image-mask-prelude"
        root.mkdir(parents=True, exist_ok=True)
        if image_bytes is not None:
            with (root / (label + ".pgm")).open("xb") as handle:
                handle.write(image_bytes)
                handle.flush()
                os.fsync(handle.fileno())
        if columns is not None:
            with (root / (label + ".npz")).open("xb") as handle:
                np.savez_compressed(handle, **columns)
                handle.flush()
                os.fsync(handle.fileno())
        with (root / (label + ".json")).open("x") as handle:
            json.dump(prelude.arrays.plain(record), handle, indent=2, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())


def retain_positive_failure(label, error):
    """Retain actual trial arrays/bytes before an unexpected capture refusal."""
    columns, byte_count = {}, 0

    def encode(value, name):
        nonlocal byte_count
        if isinstance(value, (np.ndarray, np.generic)):
            array = np.asarray(value)
            columns[name] = array
            return records.record(array) | dict(column=name)
        if isinstance(value, bytes):
            artifact = label + f"-trial-{byte_count}.bin"
            byte_count += 1
            if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
                root = Path(directory) / "image-mask-prelude"
                root.mkdir(parents=True, exist_ok=True)
                with (root / artifact).open("xb") as handle:
                    handle.write(value)
                    handle.flush()
                    os.fsync(handle.fileno())
            return dict(
                kind="opaque_bytes",
                byte_count=len(value),
                sha256=hashlib.sha256(value).hexdigest(),
                artifact=artifact,
            )
        if isinstance(value, dict):
            return {key: encode(item, name + "__" + str(key)) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [encode(item, name + "__" + str(i)) for i, item in enumerate(value)]
        return records.record(value)

    trial = encode(error.trial, "trial")
    save(
        label + "-actual-failure",
        dict(
            mode="retained_positive_component_failure",
            stage=error.stage,
            reason=str(error),
            source_trial=trial,
            no_partial_commit=True,
        ),
        columns or None,
    )


def canonical_cycle(points):
    values = np.asarray(points)
    first = min(range(len(values)), key=lambda i: tuple(values[i]))
    return np.concatenate((values[first:], values[:first]))


def coordinates(actual, expected):
    actual, expected = np.asarray(actual), np.asarray(expected)
    assert actual.shape == expected.shape
    fraction = np.max(abs(actual - expected) / (1e-27 + 6e-12 * abs(expected)), initial=0)
    assert fraction <= 1, fraction
    return float(fraction)


@pytest.mark.parametrize("case", fixtures.CASES)
@pytest.mark.parametrize("lattice_type", ("SQUARE", "HEX"))
@pytest.mark.parametrize("single_cell", (False, True))
def test_native_mask_and_branch_arguments_with_independent_grid_hull(
    tmp_path, case, lattice_type, single_cell
):
    binding, state = seed(lattice_type, single_cell)
    recipe = fixtures.write_image(tmp_path, case, absolute=single_cell)
    controls = fixtures.controls(single_cell=single_cell)
    if case == "near_white5":
        controls.update(
            alpha_shape=0.55,
            use_centroids=False,
            refine_mesh=True,
            maximum_voronoi_steps=3,
            voronoi_convergence=2.25,
        )
    elif case == "centre_hole6":
        controls["maximum_voronoi_steps"] = 0
    label = f"{case}-{lattice_type}-{int(single_cell)}"
    path = Path(recipe["filename"])
    if not path.is_absolute():
        path = tmp_path / path
    data = path.read_bytes()
    raw_geometry = geometry(binding, state)
    save(
        label + "-input",
        dict(
            recipe=recipe,
            geometry=raw_geometry,
            controls=controls,
            upstream_seed_recipe=binding.definition,
            upstream_seed_stream_before=streams.native_stream_manifest(state.stream_before),
            upstream_seed_stream_after=streams.native_stream_manifest(state.stream_after),
        ),
        image_bytes=data,
    )
    try:
        image = prelude.capture_image(recipe)
        value = prelude.prepare(binding, state, image, controls)
        actual_record = prelude.export_prelude(binding, state, value)
    except prelude.ImagePreludeRejected as error:
        retain_positive_failure(label, error)
        raise
    save(label + "-actual", actual_record, value.values._asdict())
    xmin, xmax, ymin, ymax = state.values.axis_bounds_m
    width, height = xmax - xmin, ymax - ymin
    qx = [xmin, xmax, (xmin + xmax) / 2] + [
        xmin + fraction * width for fraction in (0.23, 0.71, 0.79, 0.31)
    ]
    qy = [ymin, ymax, (ymin + ymax) / 2] + [
        ymin + fraction * height for fraction in (0.71, 0.23, 0.31, 0.79)
    ]
    proof = native.evaluate(recipe, raw_geometry, controls, points_x=qx, points_y=qy)
    save(
        label + "-native",
        proof,
        {
            name + "__" + key: array
            for name, fields in proof["raw_locals"].items()
            for key, array in fields.items()
        },
    )
    assert proof["status"] == "mesh_method_argument_boundary" and proof["failure"] is None
    first = reference.evaluate(data, state.values.axis_bounds_m, qx, qy)
    second = reference.evaluate(data, state.values.axis_bounds_m, qx, qy, refinement=2)
    columns = {"actual__" + key: array for key, array in value.values._asdict().items()}
    columns |= {"native__" + key: array for key, array in proof["values"].items()}
    actual_linear = prelude.paired_linear_values(binding, state, value, qx, qy)
    selected = prelude.clipped_points_index(binding, state, value, qx, qy)
    columns["actual__paired_linear_values"] = actual_linear
    columns["native__paired_linear_values"] = proof["paired_linear_values"]
    columns["actual__selected_indices"] = selected
    columns["native__selected_indices"] = proof["selected_indices"]
    for prefix, record in (("reference", first), ("refined", second)):
        columns |= {
            prefix + "__" + key: np.asarray(record[key])
            for key in (
                "bitmap",
                "clipping_matrix",
                "xpts_m",
                "ypts_m",
                "active_grid_indices",
                "active_points_m",
                "canonical_hull_indices",
                "canonical_clipcurve_m",
                "paired_linear_values",
                "selected_indices",
            )
        }
    save(
        label + "-precomparison",
        dict(native=proof, reference=first, refined_reference=second),
        columns,
    )
    if case == "asymmetric4":
        # Off-diagonal pairs must distinguish the linear field from its transpose.
        assert abs(first["paired_linear_values"][3] - first["paired_linear_values"][4]) > 1e-3
    for key, expected in proof["values"].items():
        actual = getattr(value.values, key)
        assert actual.dtype == expected.dtype and actual.shape == expected.shape, key
        np.testing.assert_array_equal(actual, expected, err_msg=key)
    assert records.record(value.constructor_kwargs) == records.record(proof["calls"][0]["kwargs"])
    assert proof["calls"][1] == dict(
        name=value.next_method,
        kwargs=dict(value.next_kwargs),
        original_mask_argument=not single_cell,
    )
    assert proof["native_filename"] == image.native_filename
    assert proof["original_global_rng_unchanged"] and not proof["mesh_constructor_executed"]
    assert value.stream.identity == state.stream_after.identity
    np.testing.assert_array_equal(selected, proof["selected_indices"])
    np.testing.assert_array_equal(selected, np.asarray(first["selected_indices"], dtype=int))
    np.testing.assert_array_equal(actual_linear, proof["paired_linear_values"])
    target = np.asarray(first["paired_linear_values"])
    budget = 2e-14 + 6e-12 * abs(target)
    linear_fraction = float(np.max(abs(actual_linear - target) / budget, initial=0))
    resolution = float(
        np.max(abs(target - np.asarray(second["paired_linear_values"])) / budget, initial=0)
    )
    assert linear_fraction <= 1 and resolution <= 0.1
    maximum = 0.0
    for key in ("bitmap", "clipping_matrix", "active_grid_indices"):
        np.testing.assert_array_equal(getattr(value.values, key), first[key])
    for key in ("xpts_m", "ypts_m", "active_points_m"):
        maximum = max(maximum, coordinates(getattr(value.values, key), first[key]))
        resolution = max(resolution, coordinates(first[key], second[key]))
        assert resolution <= 0.1
    maximum = max(
        maximum,
        coordinates(canonical_cycle(value.values.clipcurve_m), first["canonical_clipcurve_m"]),
    )
    resolution = max(
        resolution, coordinates(first["canonical_clipcurve_m"], second["canonical_clipcurve_m"])
    )
    assert resolution <= 0.1
    assert first["selected_indices"] == second["selected_indices"]
    save(
        label,
        dict(
            mode="complete_image_prelude",
            maximum_coordinate_error_fraction=maximum,
            maximum_dimensionless_error_fraction=linear_fraction,
            maximum_reference_resolution_fraction=resolution,
            native=proof,
            reference=first,
            refined_reference=second,
            source_bytes_sha256=image.file_sha256,
            branch=value.next_method,
            full_refined_buffers_retained=True,
            input_record=label + "-input.json",
            image_bytes_record=label + "-input.pgm",
            fields=list(value.values._asdict()),
            points_x=qx,
            points_y=qy,
            mesh_constructor_executed=False,
            topology_generated=False,
            biological_geometry=False,
        ),
        columns,
    )


@pytest.mark.parametrize("case", ("white4", "collinear4", "small3", "nonsquare"))
def test_raw_mask_failure_precedes_single_cell_mesh_branch(tmp_path, case):
    binding, state = seed()
    recipe = fixtures.write_image(tmp_path, case)
    data = (tmp_path / recipe["filename"]).read_bytes()
    controls = fixtures.controls(single_cell=True)
    save(
        case + "-input",
        dict(
            recipe=recipe,
            geometry=geometry(binding, state),
            controls=controls,
            upstream_seed_recipe=binding.definition,
            upstream_seed_stream_before=streams.native_stream_manifest(state.stream_before),
            upstream_seed_stream_after=streams.native_stream_manifest(state.stream_after),
        ),
        image_bytes=data,
    )
    image = prelude.capture_image(recipe)
    with pytest.raises(prelude.ImagePreludeRejected) as caught:
        prelude.prepare(binding, state, image, controls)
    save(
        case + "-actual", dict(stage=caught.value.stage, no_partial_commit=True), caught.value.trial
    )
    proof = native.evaluate(recipe, geometry(binding, state), controls)
    columns = {
        name + "__" + key: array
        for name, fields in proof["raw_locals"].items()
        for key, array in fields.items()
    }
    save(
        case,
        dict(
            mode="retained_raw_native_mask_failure",
            native=proof,
            actual_stage=caught.value.stage,
            no_partial_commit=True,
        ),
        columns,
    )
    assert proof["status"] == "source_failed" and proof["failure"]
    assert not proof["calls"] and proof["original_global_rng_unchanged"]


def test_owned_image_is_immutable_and_survives_live_filename_change(tmp_path):
    binding, state = seed()
    recipe = fixtures.write_image(tmp_path, "dense4")
    image = prelude.capture_image(recipe)
    value = prelude.prepare(binding, state, image, fixtures.controls())
    (tmp_path / recipe["filename"]).write_bytes(b"later unrelated file contents")
    assert prelude.validate_image(image).identity == image.identity
    assert prelude.validate_prelude(binding, state, value).identity == value.identity
    for array in value.values:
        with pytest.raises(ValueError):
            array.setflags(write=True)
    assert type(image.file_bytes) is bytes
    exported = prelude.export_prelude(binding, state, value)
    assert not exported["downstream_mesh_admitted"] and not exported["mesh_constructor_executed"]


@pytest.mark.parametrize("target", ("pixels", "window", "pixel_ids", "mesh_type"))
def test_resealed_mask_or_branch_tampering_is_refused(tmp_path, target):
    binding, state = seed()
    recipe = fixtures.write_image(tmp_path, "asymmetric4")
    value = prelude.prepare(binding, state, prelude.capture_image(recipe), fixtures.controls())
    if target == "pixels":
        mask = value.values.clipping_matrix.copy()
        mask[0, 0] = 1 - mask[0, 0]
        value = replace(
            value, values=value.values._replace(clipping_matrix=prelude.arrays.frozen(mask))
        )
    elif target == "window":
        value = replace(
            value,
            values=value.values._replace(xpts_m=prelude.arrays.frozen(value.values.xpts_m + 1e-7)),
        )
    elif target == "pixel_ids":
        value = replace(value, active_file_pixel_ids=tuple(reversed(value.active_file_pixel_ids)))
    else:
        value = replace(
            value,
            constructor_kwargs=MappingProxyType(
                dict(value.constructor_kwargs) | dict(mesh_type="quad")
            ),
        )
    value = replace(value, identity=records._digest(prelude.prelude_record(value)))
    with pytest.raises(ValueError):
        prelude.validate_prelude(binding, state, value)


@pytest.mark.parametrize("override", ("image_window_m", "caller_bitmap"))
def test_source_window_and_pixels_do_not_accept_caller_overrides(tmp_path, override):
    binding, state = seed()
    recipe = fixtures.write_image(tmp_path, "dense4")
    with pytest.raises(prelude.ImagePreludeRejected):
        prelude.prepare(
            binding, state, prelude.capture_image(recipe), fixtures.controls() | {override: 1}
        )


def test_paired_query_retains_native_zip_truncation(tmp_path):
    binding, state = seed()
    recipe = fixtures.write_image(tmp_path, "dense4")
    value = prelude.prepare(binding, state, prelude.capture_image(recipe), fixtures.controls())
    xmin, xmax, ymin, ymax = state.values.axis_bounds_m
    result = prelude.clipped_points_index(binding, state, value, [xmin, xmax, xmin], [ymin, ymax])
    np.testing.assert_array_equal(result, [0, 1])
