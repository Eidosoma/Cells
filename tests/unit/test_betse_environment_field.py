"""Complete native fields, independent operators and narrower admission evidence."""

import hashlib
import json
import os
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_environment_field as field
from cells.processes import betse_normal_current as current
from validation.betse import betse_environment_field_checks as checks
from validation.betse import betse_environment_field_fixtures as fixtures
from validation.betse import betse_environment_field_native as native
from validation.betse import betse_environment_field_reference as reference


def current_readout(binding, row):
    return current.evaluate(binding.current_binding, current.inputs(binding.current_binding, **row))


def actual(data):
    binding = field.bind(data["definition"])
    frames = []
    for row in data["frames"]:
        prefix = current_readout(binding, row["current"])
        readout = field.evaluate(binding, prefix, row["environment"])
        frames.append(
            dict(
                values=readout.values,
                current=dict(values=prefix.values),
                smoothing_hodge=readout.smoothing_hodge,
                current_hodge=readout.current_hodge,
            )
        )
    geometry = binding.geometry._asdict()
    geometry.pop("diagnostics")
    return binding, dict(geometry=geometry, cache=binding.cache, frames=frames)


def write(name, record, categories):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        root = Path(directory) / "environment-field"
        root.mkdir(exist_ok=True, parents=True)
        columns = {
            category + "__" + key.replace(".", "__"): value
            for category, values in categories.items()
            for key, value in values.items()
        }
        with (root / (name + ".npz")).open("xb") as stream:
            np.savez_compressed(stream, **columns)
            stream.flush()
            os.fsync(stream.fileno())
        with (root / (name + ".json")).open("x") as stream:
            json.dump(field.plain(record), stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())


@pytest.mark.parametrize("is_ecm", (True, False), ids=("ECM", "noECM"))
@pytest.mark.parametrize("case", fixtures.CASES)
def test_complete_native_and_independent_fields(case, is_ecm):
    data = fixtures.fixture(case, is_ecm=is_ecm)
    inputs_before = deepcopy(data)
    binding, observed = actual(data)
    proof = native.evaluate(data)
    first, second = reference.evaluate(data), reference.evaluate(data, refinement=2)
    assert data == inputs_before
    assert proof["RNG_unchanged"] and not proof["warnings"]
    factor = checks.prefix_factor(data["definition"])
    maximum = checks.compare(
        dict(geometry=observed["geometry"], cache=observed["cache"]),
        dict(geometry=proof["geometry"], cache=proof["cache"]),
        exact=True,
    )
    maximum = max(
        maximum,
        checks.compare(
            dict(geometry=observed["geometry"], cache=observed["cache"]),
            dict(geometry=first["geometry"], cache=first["cache"]),
        ),
    )
    resolution = checks.compare(
        dict(geometry=first["geometry"], cache=first["cache"]),
        dict(geometry=second["geometry"], cache=second["cache"]),
    )
    for i, row in enumerate(observed["frames"]):
        checks.compare(checks.data_frame(row), checks.data_frame(proof["frames"][i]), exact=True)
        maximum = max(
            maximum,
            checks.compare(
                checks.data_frame(row),
                checks.data_frame(first["frames"][i]),
                gross=first["frames"][i]["current"]["gross"],
                factor=factor,
            ),
        )
        resolution = max(
            resolution,
            checks.compare(
                checks.data_frame(first["frames"][i]),
                checks.data_frame(second["frames"][i]),
                gross=second["frames"][i]["current"]["gross"],
                factor=factor,
            ),
        )
    assert resolution <= 0.1
    write(
        case + ("-ECM" if is_ecm else "-noECM"),
        dict(
            mode="complete_instantaneous_fields",
            inputs=data,
            original_binding_identity=binding.identity,
            native_source_sha256=proof["native_source_sha256"],
            native_source_sites=proof["source_sites"],
            fields=list(checks.source_arrays(observed)),
            maximum_error_fraction=maximum,
            maximum_reference_resolution_fraction=resolution,
            reference=first,
            refined_reference=second,
            derived_geometry=True,
            inverse_supplied=False,
            cache_supplied=False,
            full_refined_buffers_retained=True,
            physical_field_energy_parity=False,
        ),
        {
            name: checks.source_arrays(value)
            for name, value in (
                ("actual", observed),
                ("native", proof),
                ("reference", first),
                ("refined", second),
            )
        },
    )


@pytest.mark.parametrize("is_ecm", (True, False), ids=("ECM", "noECM"))
def test_nearest_tie_refusal_retains_actual_native_choice(is_ecm):
    data = fixtures.fixture(is_ecm=is_ecm)
    data["definition"]["geometry"]["membrane_midpoints_m"][0] = [1.0, 0.5]
    with pytest.raises(field.EnvironmentFieldRejected) as caught:
        field.bind(data["definition"])
    trial = caught.value.trial
    assert caught.value.stage == "nearest_mapping" and not trial["native_tie_equivalence"]
    assert not trial["unique"][0] and trial["distances"][0, 0] == trial["distances"][0, 1]
    proof = native.evaluate(data)
    np.testing.assert_array_equal(
        proof["geometry"]["membrane_to_grid"], trial["native_single_nearest"]
    )
    with pytest.raises(ValueError, match="ambiguous"):
        reference.evaluate(data)
    write(
        "nearest-tie-" + str(is_ecm),
        dict(
            mode="narrower_nearest_tie_refusal",
            inputs=data,
            native_source_sha256=proof["native_source_sha256"],
            no_partial_commit=True,
            native_tie_equivalence=False,
            trial_fields=list(checks.flat(trial)),
        ),
        dict(trial=checks.flat(trial), native=checks.source_arrays(proof)),
    )


def test_zero_screening_retains_raw_native_nonfinite_trial():
    data = fixtures.fixture()
    initial = data["definition"]["cache_initial_state"]
    initial["environment_mol_m3"] = [[0.0] * 9 for _ in initial["environment_mol_m3"]]
    binding = field.bind(data["definition"])
    saved = current._digest(field.binding_record(binding))
    row = data["frames"][0]
    prefix = current_readout(binding, row["current"])
    with pytest.raises(field.EnvironmentFieldRejected) as caught:
        field.evaluate(binding, prefix, row["environment"])
    trial = caught.value.trial
    assert trial is not None and not trial.diagnostics["finite"]
    assert current._digest(field.binding_record(binding)) == saved
    proof = native.evaluate(data)
    assert proof["warnings"]
    checks.compare(
        dict(values=trial.values, current_hodge=trial.current_hodge),
        {key: proof["frames"][0][key] for key in ("values", "current_hodge")},
        exact=True,
    )
    assert reference.evaluate(data)["frames"][0]["values"]["refused_zero_screening"]
    write(
        "zero-screening",
        dict(
            mode="raw_zero_screening_refusal",
            inputs=data,
            native_source_sha256=proof["native_source_sha256"],
            no_partial_commit=True,
            fields=list(checks.flat(dict(values=trial.values, current_hodge=trial.current_hodge))),
        ),
        dict(
            trial=checks.flat(dict(values=trial.values, current_hodge=trial.current_hodge)),
            native=checks.source_arrays(proof),
        ),
    )


def test_zero_screening_is_unused_and_allowed_without_ecm():
    data = fixtures.fixture(is_ecm=False)
    initial = data["definition"]["cache_initial_state"]
    initial["environment_mol_m3"] = [[0.0] * 9 for _ in initial["environment_mol_m3"]]
    binding, observed = actual(data)
    assert binding.cache.ko_environment_per_m == 0
    proof = native.evaluate(data)
    checks.compare(
        dict(values=observed["frames"][0]["values"]),
        dict(values=proof["frames"][0]["values"]),
        exact=True,
    )


def test_current_overflow_retains_complete_raw_native_trial():
    data = fixtures.fixture()
    for row in data["frames"]:
        row["environment"]["extra_environment_current_xy"] = [
            [1e308 if k % 3 == 2 else -1e308, 0.0] for k in range(9)
        ]
    binding = field.bind(data["definition"])
    saved = current._digest(field.binding_record(binding))
    prefix = current_readout(binding, data["frames"][0]["current"])
    with pytest.raises(field.EnvironmentFieldRejected) as caught:
        field.evaluate(binding, prefix, data["frames"][0]["environment"])
    trial = caught.value.trial
    assert trial is not None and not trial.diagnostics["finite"]
    assert current._digest(field.binding_record(binding)) == saved
    proof = native.evaluate(data)
    wanted = {key: proof["frames"][0][key] for key in ("values", "current_hodge")}
    observed = dict(values=trial.values, current_hodge=trial.current_hodge)
    checks.compare(observed, wanted, exact=True)
    write(
        "current-overflow",
        dict(
            mode="raw_current_overflow_refusal",
            inputs=data,
            native_source_sha256=proof["native_source_sha256"],
            no_partial_commit=True,
            fields=list(checks.flat(observed)),
        ),
        dict(trial=checks.flat(observed), native=checks.source_arrays(proof)),
    )


@pytest.mark.parametrize("target", ("dirichlet", "neumann", "cache"))
def test_resealed_derived_operator_or_cache_is_rejected(target):
    binding = field.bind(fixtures.fixture()["definition"])
    if target == "cache":
        altered = replace(binding, cache=binding.cache._replace(sigma_S_m=field.frozen(0.5)))
    else:
        key = target + "_inverse_m2"
        value = getattr(binding.geometry, key).copy()
        value[0, 0] += 1.0
        altered = replace(binding, geometry=binding.geometry._replace(**{key: field.frozen(value)}))
    altered = replace(altered, identity=current._digest(field.binding_record(altered)))
    with pytest.raises(ValueError, match="Derived geometry"):
        field.validate_binding(altered)


def test_resealed_current_prefix_is_recomputed():
    data = fixtures.fixture()
    binding = field.bind(data["definition"])
    prefix = current_readout(binding, data["frames"][0]["current"])
    changed = prefix.values.normal_current_A_m2.copy()
    changed[0] += 1
    prefix = replace(
        prefix, values=prefix.values._replace(normal_current_A_m2=field.frozen(changed))
    )
    with pytest.raises(field.EnvironmentFieldRejected, match="actual source prefix"):
        field.evaluate(binding, prefix, data["frames"][0]["environment"])


def test_inverses_and_geometry_have_fixed_source_gauges():
    binding = field.bind(fixtures.fixture("five_by_five")["definition"])
    g = binding.geometry
    size = np.prod(g.shape)
    np.testing.assert_allclose(
        g.dirichlet_laplacian_per_m2 @ g.dirichlet_inverse_m2, np.eye(size), atol=1e-13
    )
    p = np.eye(size) - np.ones((size, size)) / size
    np.testing.assert_allclose(g.neumann_laplacian_per_m2 @ g.neumann_inverse_m2, p, atol=1e-13)
    assert g.diagnostics["HH_uses_dirichlet_inverse"]
    assert all(
        value < field.OPERATOR_RESIDUAL_LIMIT
        for key, value in g.diagnostics.items()
        if key.endswith(("residual", "symmetry", "gauge"))
    )
    assert np.linalg.matrix_rank(g.dirichlet_laplacian_per_m2) == size
    assert np.linalg.matrix_rank(g.neumann_laplacian_per_m2) == size - 1


def test_source_projection_can_erase_uniform_current():
    _, proof = actual(fixtures.fixture("uniform_current"))
    v = proof["frames"][0]["values"]
    assert np.any(v.raw_environment_current_x != 0)
    np.testing.assert_array_equal(v.total_current_x_source, np.zeros((3, 3)))
    np.testing.assert_array_equal(v.total_current_y_source, np.zeros((3, 3)))


def test_duplicate_owner_index_and_corner_order_are_literal():
    data = fixtures.fixture("duplicate", is_ecm=False)
    binding, proof = actual(data)
    v = proof["frames"][0]["values"]
    owner = data["definition"]["current_definition"]["geometry"]["owner"]
    assert (
        v.local_voltage_assignment[0]
        == data["frames"][0]["environment"]["old_voltage_V"][owner[-1]] / 2
    )
    assert np.count_nonzero(v.local_voltage_assignment) == 1
    boundary = data["frames"][0]["environment"]["boundary_V"]
    assert v.boundary_rhs[0, 0] == -boundary["B"] / binding.geometry.delta_m**2
    assert v.boundary_rhs[-1, -1] == -boundary["T"] / binding.geometry.delta_m**2
    hodge = proof["frames"][0]["current_hodge"]
    np.testing.assert_array_equal(hodge.divergence[[0, -1]], np.zeros((2, 3)))


def test_ecm_repeated_area_mean_and_dirichlet_hodge():
    data = fixtures.fixture()
    binding, proof = actual(data)
    g, v = binding.geometry, proof["frames"][0]["values"]
    repeated_mean = g.membrane_area_per_site_m2[g.membrane_to_grid].mean()
    occupied_mean = g.membrane_area_per_site_m2[g.membranes_per_site > 0].mean()
    assert repeated_mean != occupied_mean
    wanted = v.environment_charge_C_m3[g.membrane_to_grid] * (0.1 * g.delta_m**2) / repeated_mean
    np.testing.assert_array_equal(v.surface_charge_C_m2[g.membrane_to_grid], wanted)
    hodge = proof["frames"][0]["current_hodge"]
    np.testing.assert_array_equal(hodge.BB, g.dirichlet_inverse_m2 @ hodge.divergence.ravel())
    assert np.max(abs(hodge.BB - g.neumann_inverse_m2 @ hodge.divergence.ravel())) > 1e-6


def test_source_diff_and_gradient_edges_have_different_signs():
    grid = np.asarray([[0.0, 1.0, 2.0], [3.0, 4.0, 5.0], [6.0, 7.0, 8.0]])
    gx, gy = field.gradient(grid, 1.0)
    dx, dy = field.source_diff(grid, 1.0, 0), field.source_diff(grid, 1.0, 1)
    np.testing.assert_array_equal(gx, np.ones((3, 3)))
    np.testing.assert_array_equal(gy, np.full((3, 3), 3.0))
    np.testing.assert_array_equal(dx[:, (0, -1)], np.full((3, 2), -1.0))
    np.testing.assert_array_equal(dy[(0, -1), :], np.full((2, 3), -3.0))


def test_cache_is_initializer_owned_and_outputs_are_immutable():
    data = fixtures.fixture()
    binding = field.bind(data["definition"])
    original = current._digest(field.binding_record(binding))
    prefix = current_readout(binding, data["frames"][0]["current"])
    output = field.evaluate(binding, prefix, data["frames"][0]["environment"])
    for value in (
        binding.geometry.dirichlet_inverse_m2,
        binding.geometry.cell_to_grid,
        binding.cache.sigma_S_m,
        output.values.environment_voltage_V,
    ):
        with pytest.raises(ValueError):
            value.setflags(write=True)
    data["definition"]["cache_initial_state"]["cell_mol_m3"][0][0] *= 2
    assert field.bind(data["definition"]).cache.sigma_S_m != binding.cache.sigma_S_m
    assert current._digest(field.binding_record(binding)) == original


def test_explicit_voltage_dependency_export_retains_binding_provenance():
    binding = field.bind(fixtures.fixture()["definition"])
    exported = field.voltage_dependencies(binding)
    assert set(exported) == {
        "shape",
        "delta_m",
        "membrane_to_grid",
        "inverse_m2",
        "operator_provenance",
    }
    assert json.loads(exported["operator_provenance"])["binding_identity"] == binding.identity
    np.testing.assert_array_equal(exported["inverse_m2"], binding.geometry.dirichlet_inverse_m2)


@pytest.mark.parametrize(
    "defect",
    (
        "missing_parameter",
        "wrong_current_axis",
        "nonfinite_input",
        "negative_weight",
        "oversize_grid",
    ),
)
def test_incomplete_or_nonfinite_sources_refuse_without_commit(defect):
    data = fixtures.fixture(is_ecm=False)
    if defect == "missing_parameter":
        data["definition"]["parameters"].pop("cell_height_m")
    elif defect == "wrong_current_axis":
        data["definition"]["current_definition"]["geometry"]["owner"][0] = 99
    elif defect == "oversize_grid":
        data["definition"]["world"]["grid_size"] = 8
    else:
        data["frames"][0]["environment"]["environment_weight"][0][0] = (
            float("nan") if defect == "nonfinite_input" else -1
        )
    with pytest.raises(field.EnvironmentFieldRejected):
        actual(data)


def test_protocol_is_explicit_about_supplied_and_derived_dependencies():
    protocol = json.loads(Path(native.PROTOCOL).read_text())
    assert protocol["law_id"] == field.LAW_ID
    assert len(protocol["native_source"]["source_sha256"]) == 7
    assert protocol["derived"] and protocol["supplied"]
    assert protocol["tolerances"]["reference_resolution_fraction"] == 0.1
    assert not protocol["automatic_followup"] and not protocol["automatic_polling"]
    digest = hashlib.sha256(Path(native.PROTOCOL).read_bytes()).hexdigest()
    assert len(digest) == 64
