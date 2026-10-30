"""Prepared native lattice/draw checks; no automatic numerical launch."""

import json
import os
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.core.specs import digest
from cells.processes import betse_lattice_seed_generation as lattice
from cells.processes import betse_normal_current as records
from cells.processes import betse_perturbations as streams
from validation.betse import betse_lattice_seed_generation_checks as checks
from validation.betse import betse_lattice_seed_generation_fixtures as fixtures
from validation.betse import betse_lattice_seed_generation_native as native
from validation.betse import betse_lattice_seed_generation_reference as reference


def source_stream(raw):
    rng = np.random.RandomState(raw["seed"])
    rng.random(raw["warmup_uniforms"])
    state = rng.get_state()
    return streams._native_stream(
        [state[0], state[1].tolist(), int(state[2]), raw["has_gauss"], raw["cached_gaussian"]],
        np.__version__,
    )


def write(name, record, columns=None, *, raw=False):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        root = Path(directory) / ("lattice-seeds-raw" if raw else "lattice-seeds")
        root.mkdir(parents=True, exist_ok=True)
        if columns is not None:
            with (root / (name + ".npz")).open("xb") as stream:
                np.savez_compressed(stream, **columns)
                stream.flush()
                os.fsync(stream.fileno())
        from cells.processes.betse_environment_field import plain

        with (root / (name + ".json")).open("x") as stream:
            json.dump(plain(record), stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())


def prepare(case="square_disordered"):
    data = fixtures.fixture(case)
    stream = None
    try:
        binding = lattice.bind(data["recipe"])
        stream = source_stream(data["stream_setup"])
        state = lattice.generate(binding, stream)
    except lattice.LatticeSeedRejected as error:
        trial = error.trial
        columns = checks.numeric(trial.values) if type(trial) is lattice.SeedState else None
        suffix = digest({"test": os.environ.get("PYTEST_CURRENT_TEST", "direct")})[:12]
        write(
            case + "-core-failure-" + suffix,
            dict(
                mode="raw_component_failure",
                inputs=data,
                reason=str(error),
                stage=error.stage,
                source_trial=records.record(trial)
                if type(trial) is not lattice.SeedState
                else dict(
                    identity=trial.identity,
                    fields=list(columns),
                    stream_after=streams.native_stream_manifest(trial.stream_after),
                ),
                stream_before=None if stream is None else streams.native_stream_manifest(stream),
            ),
            columns,
            raw=True,
        )
        raise
    return data, binding, stream, state


@pytest.mark.parametrize("case", fixtures.CASES)
def test_complete_native_lattice_parameters_draws_and_independent_coordinates(case):
    data, binding, stream, state = prepare(case)
    before = streams.native_stream_manifest(stream)["state"]
    write(
        case + "-actual",
        dict(
            mode="actual_before_native_capture",
            inputs=data,
            actual=lattice.export_seed_stage(binding, state),
        ),
        checks.numeric(state.values),
        raw=True,
    )
    proof = native.evaluate(data["recipe"], before)
    write(
        case + "-native",
        dict(
            mode="native_precomparison",
            inputs=data,
            actual=lattice.export_seed_stage(binding, state),
            native=proof,
        ),
        {"actual__" + key: value for key, value in checks.numeric(state.values).items()}
        | {"native_local__" + key: value for key, value in proof["raw_locals"].items()},
        raw=True,
    )
    assert proof["status"] == "source_completed" and proof["failure"] is None
    assert not proof["warnings"]
    assert all(
        proof["source_sites"]["wrapper_verification"][key]
        for key in (
            "parameter_body_exact",
            "loop_annotations_and_decorator_exact",
            "pinned_type_check_exact",
            "postponed_annotations",
            "normalized_call_boundary_validated",
        )
    )
    assert not proof["source_sites"]["wrapper_verification"]["native_package_import_hook_executed"]
    first = reference.evaluate(data["recipe"], before)
    second = reference.evaluate(data["recipe"], before, refinement=2)
    columns = {
        prefix + "__" + key: value
        for prefix, values in (
            ("actual", state.values),
            ("native", proof["values"]),
            ("reference", first["values"]),
            ("refined", second["values"]),
        )
        for key, value in checks.numeric(values).items()
    }
    write(
        case,
        dict(
            mode="precomparison",
            inputs=data,
            actual=lattice.export_seed_stage(binding, state),
            native=proof,
            reference=first,
            refined_reference=second,
        ),
        columns,
        raw=True,
    )
    assert proof["status"] == "source_completed" and proof["failure"] is None
    checks.compare(state.values, proof["values"], exact=True)
    maximum = checks.compare(state.values, first["values"])
    resolution = checks.compare(first["values"], second["values"])
    assert resolution <= 0.1
    p, actual_parameters = binding.parameters, proof["parameters"]
    expected_parameters = dict(
        world_len=p.requested_world_len_m,
        cell_radius=p.cell_radius_m,
        cell_lattice_disorder=p.disorder,
        wsx=p.expanded_width_m,
        wsy=p.expanded_height_m,
        ac=p.drawing_gap_m,
        d_cell=p.diameter_m,
        nx=p.nx,
        ny=p.ny,
    )
    assert digest(actual_parameters) == digest(expected_parameters) == digest(first["parameters"])
    if data["recipe"]["lattice_type"] == "HEX":
        assert list(p.blue_shape) == first["blue_shape"]
        assert list(p.red_shape) == first["red_shape"]
        assert p.blue_shape == (
            proof["source_color_counts"]["blue_y_num"],
            proof["source_color_counts"]["blue_x_num"],
        )
        assert p.red_shape == (
            proof["source_color_counts"]["red_y_num"],
            proof["source_color_counts"]["red_x_num"],
        )
    assert len(proof["calls"]) == 2
    assert [row["shape"] for row in proof["calls"]] == [list(row[1]) for row in state.draw_order]
    assert [row["count"] for row in proof["calls"]] == [p.lattice_count, p.lattice_count]
    after = streams.native_stream_manifest(state.stream_after)["state"]
    assert digest(after) == digest(proof["rng_after"]) == digest(first["rng_after"])
    assert proof["original_global_rng_unchanged"] and not proof["downstream_mesh_or_image_executed"]
    payload = lattice.export_seed_stage(binding, state)
    restored = lattice.restore_seed_stage(binding, json.loads(json.dumps(payload)))
    assert restored.identity == state.identity
    write(
        case,
        dict(
            mode="complete_native_lattice_seed_stage",
            inputs=data,
            seed_stage=payload,
            native_source_sha256=proof["native_source_sha256"],
            native_source_sites=proof["source_sites"],
            native_source_layouts=proof["source_layouts"],
            native_calls=proof["calls"],
            native_parameters=proof["parameters"],
            reference=first,
            refined_reference=second,
            fields=list(checks.numeric(state.values)),
            maximum_error_fraction=maximum,
            maximum_reference_resolution_fraction=resolution,
            full_refined_buffers_retained=True,
            reused_B09_and_MT_coverage=True,
            topology_generated=False,
            biological_geometry=False,
        ),
        columns,
    )


@pytest.mark.parametrize("lattice_type", ("SQUARE", "HEX"))
def test_zero_disorder_draws_both_axes_and_retains_complete_cache(lattice_type):
    data = fixtures.fixture("square_zero" if lattice_type == "SQUARE" else "hex_zero")
    raw = data["stream_setup"] | dict(has_gauss=1, cached_gaussian=0.125)
    stream = source_stream(raw)
    binding = lattice.bind(data["recipe"])
    state = lattice.generate(binding, stream)
    assert state.stream_after.identity != stream.identity
    assert np.count_nonzero(state.values.x_displacement_m) == 0
    assert np.count_nonzero(state.values.y_displacement_m) == 0
    after = streams.native_stream_manifest(state.stream_after)["state"]
    assert after[3:] == [1, 0.125]


def source_points_for_mean(data, binding, stream, state, suffix):
    """Retain and use original native reduction layout, before C-order storage."""
    name = data["recipe"]["lattice_type"] + "-" + suffix
    write(
        name + "-actual",
        dict(
            mode="actual_before_native_capture",
            inputs=data,
            actual=lattice.export_seed_stage(binding, state),
        ),
        checks.numeric(state.values),
        raw=True,
    )
    proof = native.evaluate(data["recipe"], streams.native_stream_manifest(stream)["state"])
    write(
        name,
        dict(mode="original_centroid_reduction", native=proof),
        {"native_local__" + key: value for key, value in proof["raw_locals"].items()},
        raw=True,
    )
    assert proof["status"] == "source_completed" and proof["failure"] is None
    layout = proof["source_layouts"]["xypts"]
    points = np.array(
        proof["raw_locals"]["xypts"],
        copy=True,
        order="F" if layout["F_contiguous"] else "C",
    )
    assert list(points.shape) == layout["shape"]
    assert list(points.strides) == layout["strides_bytes"]
    assert points.dtype.str == layout["dtype"]
    np.testing.assert_array_equal(points, state.values.lattice_points_m)
    np.testing.assert_array_equal(points.mean(axis=0), proof["values"]["centre_m"])
    return points


def test_bbox_occurrences_are_appended_without_deduplication_or_centre_replacement():
    data, binding, stream, state = prepare("square_zero")
    source_points = source_points_for_mean(data, binding, stream, state, "bbox-centroid")
    n = binding.parameters.lattice_count
    assert len(state.occurrence_ids) == n + 4
    assert state.roles[-4:] == ("bbox_BL", "bbox_BR", "bbox_TR", "bbox_TL")
    assert len(state.duplicate_groups) == 4
    np.testing.assert_array_equal(
        state.values.all_seed_points_m[-4:], state.values.bbox_seed_points_m
    )
    np.testing.assert_array_equal(state.values.centre_m, source_points.mean(axis=0))
    assert len(set(state.occurrence_ids)) == n + 4


def test_centre_excludes_appended_bbox_occurrences():
    data, binding, stream, state = prepare("square_disordered")
    source_points = source_points_for_mean(data, binding, stream, state, "excludes-bbox")
    np.testing.assert_array_equal(state.values.centre_m, source_points.mean(axis=0))
    assert not np.array_equal(state.values.centre_m, state.values.all_seed_points_m.mean(axis=0))


def test_generation_preserves_process_global_random_state():
    before = np.random.get_state()
    prepare("hex_cached")
    after = np.random.get_state()
    assert before[0] == after[0] and np.array_equal(before[1], after[1]) and before[2:] == after[2:]


def test_hex_order_is_blue_block_then_red_and_empty_red_is_retained():
    _, binding, _, state = prepare("hex_disordered")
    count = np.prod(binding.parameters.blue_shape)
    np.testing.assert_array_equal(state.values.base_points_m[:count], state.values.blue_points_m)
    np.testing.assert_array_equal(state.values.base_points_m[count:], state.values.red_points_m)
    assert all(role == "blue_lattice" for role in state.roles[:count])
    _, _, _, empty_red = prepare("hex_red_empty")
    assert empty_red.values.red_points_m.shape == (0, 2)
    assert len(empty_red.occurrence_ids) == 5


def test_parameter_counts_precede_expansion_and_gap_is_native_drawing_constant():
    _, binding, _, _ = prepare("square_disordered")
    p = binding.parameters
    assert p.nx == int(p.requested_world_len_m / p.diameter_m)
    assert p.expanded_width_m > p.requested_world_len_m
    assert p.nx != int(p.expanded_width_m / p.diameter_m)
    assert p.drawing_gap_m == 1e-6
    _, hx, _, _ = prepare("hex_raw_count_zero")
    assert hx.parameters.nx == 0 and hx.parameters.lattice_count > 0


def test_twist_at_y_preserves_cached_gaussian_and_exact_draw_successors():
    data, _, stream, state = prepare("square_twist_cache")
    proof = native.evaluate(data["recipe"], streams.native_stream_manifest(stream)["state"])
    assert proof["calls"][0]["rng_after"][2] == 624
    assert proof["calls"][1]["rng_after"][2] == 32
    assert streams.native_stream_manifest(state.stream_after)["state"][3:] == [1, -0.25]


@pytest.mark.parametrize("lattice_type", ("SQUARE", "HEX"))
def test_raw_empty_native_failure_is_retained_without_rng_change(lattice_type):
    recipe = fixtures.empty(lattice_type)
    before_stream = streams.native_stream(17)
    before = streams.native_stream_manifest(before_stream)["state"]
    with pytest.raises(lattice.LatticeSeedRejected) as caught:
        lattice.bind(recipe)
    write(
        "empty-" + lattice_type + "-actual",
        dict(
            mode="actual_before_native_capture",
            recipe=recipe,
            stream_before=streams.native_stream_manifest(before_stream),
            source_trial=caught.value.trial,
        ),
        raw=True,
    )
    proof = native.evaluate(recipe, before)
    reference_trial = reference.evaluate(recipe, before)
    raw_columns = {"native_local__" + key: value for key, value in proof["raw_locals"].items()}
    write(
        "empty-" + lattice_type,
        dict(
            mode="raw_empty_precomparison",
            recipe=recipe,
            source_trial=caught.value.trial,
            native=proof,
            reference=reference_trial,
        ),
        raw_columns,
        raw=True,
    )

    assert proof["status"] == "source_failed" and proof["failure"]
    assert len(proof["calls"]) == 2 and all(row["count"] == 0 for row in proof["calls"])
    assert digest(proof["rng_after"]) == digest(before) == digest(reference_trial["rng_after"])
    assert reference_trial["status"] == "empty_native_lattice"
    write(
        "empty-" + lattice_type,
        dict(
            mode="retained_raw_empty_failure",
            recipe=recipe,
            stream_before=streams.native_stream_manifest(before_stream),
            source_trial=caught.value.trial,
            native=proof,
            reference=reference_trial,
            no_partial_commit=True,
            accepted_seed_stage=False,
        ),
        raw_columns,
    )


def test_raw_native_centre_overflow_retains_trial_and_successor_without_commit():
    recipe = fixtures.overflowing_centre()
    binding = lattice.bind(recipe)
    stream = streams.native_stream(17)
    before = streams.native_stream_manifest(stream)
    with pytest.raises(lattice.LatticeSeedRejected) as caught:
        lattice.generate(binding, stream)
    trial = caught.value.trial
    assert trial is not None
    write(
        "centre-overflow-actual",
        dict(
            mode="actual_before_native_capture",
            recipe=recipe,
            stream_before=before,
            source_trial_identity=trial.identity,
            stream_after=streams.native_stream_manifest(trial.stream_after),
            fields=list(checks.numeric(trial.values)),
        ),
        checks.numeric(trial.values),
        raw=True,
    )
    proof = native.evaluate(recipe, before["state"])
    reference_trial = reference.evaluate(recipe, before["state"])
    columns = {
        prefix + "__" + key: value
        for prefix, values in (
            ("trial", trial.values),
            ("native", proof["values"]),
            ("reference", reference_trial["values"]),
        )
        for key, value in checks.numeric(values).items()
    }
    record = dict(
        mode="retained_raw_nonfinite_centre_failure",
        recipe=recipe,
        stream_before=before,
        source_trial_identity=trial.identity,
        fields=list(checks.numeric(trial.values)),
        native_status=proof["status"],
        native_parameters=proof["parameters"],
        native_warnings=proof["warnings"],
        native_rng_after=proof["rng_after"],
        native_source_sha256=proof["native_source_sha256"],
        reference=reference_trial,
        no_partial_commit=True,
        accepted_seed_stage=False,
        binary64_overflow_reference_parity=False,
    )
    write("centre-overflow", record, columns, raw=True)
    assert proof["status"] == "source_completed" and proof["warnings"]
    checks.compare(trial.values, proof["values"], exact=True)
    assert np.isinf(trial.values.centre_m).any()
    assert np.isfinite(np.asarray(reference_trial["values"]["centre_m"])).all()
    assert streams.native_stream_manifest(stream) == before
    assert digest(streams.native_stream_manifest(trial.stream_after)["state"]) == digest(
        proof["rng_after"]
    )
    write("centre-overflow", record, columns)


@pytest.mark.parametrize("target", ("points", "roles", "cache", "parameters"))
def test_resealed_seed_or_parameter_tampering_is_rejected(target):
    _, binding, _, state = prepare()
    if target == "points":
        points = state.values.all_seed_points_m.copy()
        points[0, 0] += 1e-7
        state = replace(
            state, values=state.values._replace(all_seed_points_m=lattice.arrays.frozen(points))
        )
    elif target == "roles":
        state = replace(state, roles=tuple(reversed(state.roles)))
    elif target == "cache":
        manifest = streams.native_stream_manifest(state.stream_after)
        raw = manifest["state"]
        raw[3], raw[4] = 1, 0.99
        state = replace(state, stream_after=streams._native_stream(raw, np.__version__))
    else:
        binding = replace(binding, parameters=binding.parameters._replace(drawing_gap_m=2e-6))
        binding = replace(binding, identity=records._digest(lattice.binding_record(binding)))
    state = replace(state, identity=records._digest(lattice.state_record(state)))
    with pytest.raises((ValueError, lattice.LatticeSeedRejected)):
        lattice.validate_state(binding, state)


def test_state_buffers_and_input_stream_are_immutable_and_handoff_is_seed_only():
    _, binding, stream, state = prepare()
    before = streams.native_stream_manifest(stream)
    for value in state.values:
        if value is not None:
            with pytest.raises(ValueError):
                value.setflags(write=True)
    assert streams.native_stream_manifest(stream) == before
    payload = lattice.export_seed_stage(binding, state)
    assert payload["classification"] == "native_lattice_seed_occurrences"
    assert not payload["downstream_geometry_admitted"] and not payload["topology_generated"]


@pytest.mark.parametrize(
    "defect",
    (
        "ac_override",
        "nx_override",
        "expanded_override",
        "spacing_override",
        "disorder_negative",
        "disorder_large",
        "unknown_lattice",
        "oversize",
    ),
)
def test_unapproved_inputs_refuse_before_any_sampling(defect):
    raw = fixtures.fixture()["recipe"]
    if defect.endswith("override"):
        raw[
            {
                "ac_override": "drawing_gap_m",
                "nx_override": "nx",
                "expanded_override": "expanded_width_m",
                "spacing_override": "cell_space_m",
            }[defect]
        ] = 1
    elif defect == "disorder_negative":
        raw["lattice_disorder"] = -0.1
    elif defect == "disorder_large":
        raw["lattice_disorder"] = 1.1
    elif defect == "unknown_lattice":
        raw["lattice_type"] = "TRI"
    else:
        raw["world_len_m"] = 1.0
    with pytest.raises(lattice.LatticeSeedRejected):
        lattice.bind(raw)


def test_duplicate_points_do_not_become_a_manufactured_geometry_declaration():
    _, binding, _, state = prepare("square_zero")
    payload = lattice.export_seed_stage(binding, state)
    with pytest.raises(ValueError):
        lattice.prior_geometry.bind(payload)
