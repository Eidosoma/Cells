"""Strict saved-declaration/owner guards; actual transition checks remain held."""

import copy
import json
import math
import os
from types import SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_normal_ecm_molecule_lifecycle as lifecycle
from validation.betse import betse_normal_current_native as archives
from validation.betse import betse_normal_ecm_molecule_handoff as handoff


def _geometry():
    # Deliberately use fixture insertion order rather than bound sorted order.
    return dict(
        geometry=dict(
            cell_centres_m=[[0.0, 0.0], [1.0, 1.0]],
            membrane_midpoints_m=[[0.5, 0.0], [1.0, 0.5]],
            cell_volume_m3=[1.0, 1.0],
        ),
        world=dict(xmin_m=0.0, xmax_m=2.0, ymin_m=0.0, ymax_m=2.0, grid_size=1.0),
        current_definition=dict(
            geometry=dict(
                cell_ids=["c0", "c1"],
                membrane_ids=["m0", "m1"],
                owner=[0, 1],
                membrane_area_m2=[1.0, 1.0],
                cell_area_m2=[1.0, 1.0],
                normal_xy=[[1.0, 0.0], [0.0, 1.0]],
            ),
            ions=dict(ids=["Na", "K", "Ca"], valence=[1, 1, 2]),
        ),
    )


def _bound(definition):
    # Plain metadata record: this is neither geometry evaluation nor admission.
    return lifecycle.material.geometry_source.Binding(
        json.dumps(
            lifecycle.material.geometry_source.plain(definition),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ),
        None,
        None,
        None,
        "unowned-software-record",
    )


@pytest.fixture
def owner_guard(monkeypatch, tmp_path):
    calls = []

    def forbidden(label):
        def stop(*args, **kwargs):
            calls.append(label)
            raise AssertionError("Actual setup/owner/geometry/RNG entry forbidden: " + label)

        return stop

    for module, names in (
        (lifecycle, ("bind", "prepare_complete", "check_complete", "transition", "verify")),
        (lifecycle.init, ("bind", "initialize", "verify", "advance")),
        (lifecycle.setup, ("prepare", "numpy_restore")),
        (lifecycle.setup.init_setup, ("python_restore",)),
        (lifecycle.material, ("bind", "state")),
        (lifecycle.material.geometry_source, ("bind",)),
        (lifecycle.fields, ("reconstruct",)),
        (np.random, ("get_state", "set_state", "RandomState")),
    ):
        for name in names:
            monkeypatch.setattr(module, name, forbidden(module.__name__ + "." + name))
    grid = _geometry()
    old = _bound(grid)
    streams = dict(
        numpy_rng_after=dict(owned="numpy-after-INIT"),
        event_finalization=dict(python_rng_after=dict(owned="python-after-INIT")),
    )
    completed = SimpleNamespace(
        binding=SimpleNamespace(
            identity="actual-saved-identity",
            setup_receipt=streams,
            inputs_raw=dict(
                field=dict(definition=dict(environment_geometry_definition=copy.deepcopy(grid)))
            ),
            material_binding=SimpleNamespace(geometry_binding=old),
        ),
        parent=SimpleNamespace(
            network=SimpleNamespace(
                material=SimpleNamespace(
                    values=SimpleNamespace(environment_mol_m3=[[1.0, 1.0, 1.0]])
                )
            )
        ),
    )
    profile = dict(
        name="tissue",
        cell_indices=[0, 1],
        membrane_indices=[0, 1],
        diffusion_m2_s={"Dm_" + role: 1.0 for role in lifecycle.setup.ROLES},
        provenance="Synthetic supplied selector metadata",
    )
    setup = dict(
        global_options={},
        scheduled_options={},
        maps=dict(tissue_target_inds={}, cell_target_inds={}, env_target_inds={}),
    )
    raw = dict(
        sim_phase=dict(
            setup=setup,
            flags={},
            time_profile={},
            field=dict(definition=dict(environment_geometry_definition=grid)),
            calcium={},
            catalog=dict(tissue_profiles={"tissue": [0, 1]}),
            mechanics_definition={},
            mechanics_initial={},
        ),
        source_setup=dict(
            rng_mode="same_process_no_unowned_draws",
            numpy_rng=copy.deepcopy(streams["numpy_rng_after"]),
            python_rng=copy.deepcopy(streams["event_finalization"]["python_rng_after"]),
            environment_diffusion=dict(
                adherens_multiplier=0.5,
                tight_junction_multiplier=0.4,
                environment_in_cluster_indices=[0, 1, 2],
                tight_junction_relative=[1.0, 1.0, 1.0],
                provenance="Synthetic dimension guard",
            ),
            tissue_profiles=[profile],
            cbnd=None,
        ),
    )
    new = _bound(grid)
    declaration = SimpleNamespace(
        base=SimpleNamespace(material_binding=SimpleNamespace(geometry_binding=new))
    )
    binding = lifecycle.Binding(
        raw, completed.binding.identity, declaration, "unowned-software-record"
    )
    value = SimpleNamespace(binding=binding, completed=completed, grid=grid, old=old, new=new)
    yield value
    (tmp_path / "software-control.json").write_text(
        json.dumps(
            dict(
                actual_geometry_setup_bind_transition_RNG_timestep_attempts=calls,
                scientific_acceptance=False,
                parent_admission=False,
            ),
            indent=2,
        )
        + "\n"
    )
    assert calls == []


def test_owner_guard_matches_same_bound_owner_despite_raw_mapping_order(owner_guard):
    fixture = owner_guard
    raw = copy.deepcopy(fixture.binding.inputs)
    old_parent = fixture.completed.parent
    old_binding = fixture.completed.binding.material_binding.geometry_binding
    assert (
        lifecycle.catalog.equal_tree(fixture.old.definition["world"], fixture.grid["world"])
        is False
    )
    assert lifecycle.catalog.equal_tree(fixture.old.definition, fixture.new.definition) is True
    lifecycle.check_owners(fixture.binding, fixture.completed)
    assert fixture.binding.inputs == raw
    assert fixture.completed.parent is old_parent
    assert fixture.completed.binding.material_binding.geometry_binding is old_binding
    assert fixture.binding.declaration.base.material_binding.geometry_binding is fixture.new
    assert fixture.old.definition_json == fixture.new.definition_json


def test_owner_guard_allows_only_raw_mapping_insertion_order_change(owner_guard):
    fixture = owner_guard
    for keys in handoff.OWNER_PATHS.values():
        target = fixture.grid
        for key in keys[:-1]:
            target = target[key]
        target[keys[-1]] = dict(reversed(list(target[keys[-1]].items())))
    fixture.binding.declaration.base.material_binding.geometry_binding = _bound(fixture.grid)
    lifecycle.check_owners(fixture.binding, fixture.completed)
    assert fixture.completed.binding.material_binding.geometry_binding is fixture.old


@pytest.mark.parametrize(
    "path",
    [
        ("geometry", "cell_centres_m"),
        ("geometry", "membrane_midpoints_m"),
        ("geometry", "cell_volume_m3"),
        ("world", "xmax_m"),
        ("world", "grid_size"),
        ("current_definition", "geometry", "cell_ids"),
        ("current_definition", "geometry", "membrane_ids"),
        ("current_definition", "geometry", "owner"),
        ("current_definition", "geometry", "membrane_area_m2"),
        ("current_definition", "geometry", "cell_area_m2"),
        ("current_definition", "geometry", "normal_xy"),
        ("current_definition", "ions", "ids"),
        ("current_definition", "ions", "valence"),
    ],
)
def test_owner_guard_still_refuses_changed_values_axes_and_measures(owner_guard, path):
    fixture = owner_guard
    target = fixture.grid
    for key in path[:-1]:
        target = target[key]
    value = target[path[-1]]
    if isinstance(value, list):
        target[path[-1]] = list(reversed(value)) if value[0] != value[-1] else value + [value[0]]
    else:
        target[path[-1]] = math.nextafter(value, math.inf)
    # A corresponding SIM bound declaration must still fail exact old-owner
    # equality; merely choosing a consistent declaration is not admission.
    fixture.binding.declaration.base.material_binding.geometry_binding = _bound(fixture.grid)
    with pytest.raises(ValueError, match="may not replace retained"):
        lifecycle.check_owners(fixture.binding, fixture.completed)
    assert fixture.completed.binding.material_binding.geometry_binding is fixture.old


def test_owner_guard_refuses_raw_bound_mismatch_without_rebinding(owner_guard):
    fixture = owner_guard
    fixture.grid["world"]["xmax_m"] = 9.0
    with pytest.raises(ValueError, match="differs from its bound geometry declaration"):
        lifecycle.check_owners(fixture.binding, fixture.completed)
    assert fixture.binding.declaration.base.material_binding.geometry_binding is fixture.new


def _typed_owner_array(fixture):
    previous = fixture.completed.binding.inputs_raw["field"]["definition"][
        "environment_geometry_definition"
    ]
    array = np.array(previous["geometry"]["cell_centres_m"], dtype="<f8")
    previous["geometry"]["cell_centres_m"] = array
    fixture.grid["geometry"]["cell_centres_m"] = array.copy()
    fixture.binding.declaration.base.material_binding.geometry_binding = _bound(fixture.grid)
    return previous, array


def test_owner_guard_keeps_identical_typed_arrays_without_replacing_them(owner_guard):
    fixture = owner_guard
    previous, array = _typed_owner_array(fixture)
    supplied = fixture.grid["geometry"]["cell_centres_m"]
    lifecycle.check_owners(fixture.binding, fixture.completed)
    assert previous["geometry"]["cell_centres_m"] is array
    assert fixture.grid["geometry"]["cell_centres_m"] is supplied
    assert supplied.dtype == array.dtype and supplied.shape == array.shape


@pytest.mark.parametrize(
    "fault", ["dtype", "endian", "shape", "row_order", "column_order", "value", "list_conversion"]
)
def test_owner_guard_rejects_typed_array_drift_even_if_JSON_hides_it(owner_guard, fault):
    fixture = owner_guard
    _, original = _typed_owner_array(fixture)
    changed = (
        original.astype("<f4")
        if fault == "dtype"
        else original.astype(">f8")
        if fault == "endian"
        else original.reshape(4)
        if fault == "shape"
        else original[::-1].copy()
        if fault == "row_order"
        else original[:, ::-1].copy()
        if fault == "column_order"
        else original.tolist()
        if fault == "list_conversion"
        else original.copy()
    )
    if fault == "value":
        changed[0, 0] = np.nextafter(changed[0, 0], 1.0)
    # This array is symmetric across columns; make column-order observable in
    # both old and new declarations before applying its swap.
    if fault == "column_order":
        original[0, 1] = 0.5
        fixture.completed.binding.material_binding.geometry_binding = _bound(
            fixture.completed.binding.inputs_raw["field"]["definition"][
                "environment_geometry_definition"
            ]
        )
        changed = original[:, ::-1].copy()
    fixture.grid["geometry"]["cell_centres_m"] = changed
    bound = _bound(fixture.grid)
    fixture.binding.declaration.base.material_binding.geometry_binding = bound
    if fault in ("dtype", "endian", "list_conversion"):
        assert (
            fixture.completed.binding.material_binding.geometry_binding.definition_json
            == bound.definition_json
        )
    with pytest.raises(ValueError, match="may not (replace|change) retained"):
        lifecycle.check_owners(fixture.binding, fixture.completed)


@pytest.mark.parametrize("fault", ["dtype", "python_scalar", "zero_dimensional_array"])
def test_owner_guard_keeps_numpy_scalar_dtype_and_category_distinct(owner_guard, fault):
    fixture = owner_guard
    previous = fixture.completed.binding.inputs_raw["field"]["definition"][
        "environment_geometry_definition"
    ]
    previous["world"]["grid_size"] = np.float64(1.0)
    fixture.grid["world"]["grid_size"] = (
        np.float32(1.0) if fault == "dtype" else 1.0 if fault == "python_scalar" else np.array(1.0)
    )
    fixture.binding.declaration.base.material_binding.geometry_binding = _bound(fixture.grid)
    with pytest.raises(ValueError, match="sequence/array type, dtype, shape"):
        lifecycle.check_owners(fixture.binding, fixture.completed)


def test_owner_guard_preserves_identical_numpy_scalars(owner_guard):
    fixture = owner_guard
    previous = fixture.completed.binding.inputs_raw["field"]["definition"][
        "environment_geometry_definition"
    ]
    before, after = np.float64(1.0), np.float64(1.0)
    previous["world"]["grid_size"] = before
    fixture.grid["world"]["grid_size"] = after
    fixture.binding.declaration.base.material_binding.geometry_binding = _bound(fixture.grid)
    lifecycle.check_owners(fixture.binding, fixture.completed)
    assert previous["world"]["grid_size"] is before
    assert fixture.grid["world"]["grid_size"] is after


def test_owner_guard_refuses_foreign_INIT_association(owner_guard):
    fixture = owner_guard
    changed = lifecycle.Binding(
        fixture.binding.inputs, "foreign", fixture.binding.declaration, fixture.binding.identity
    )
    with pytest.raises(ValueError, match="another INIT binding"):
        lifecycle.check_owners(changed, fixture.completed)


def test_owner_guard_preserves_actual_stream_and_selector_guards(owner_guard):
    fixture = owner_guard
    fixture.binding.inputs["source_setup"]["numpy_rng"] = dict(owned="different")
    with pytest.raises(ValueError, match="actual post-INIT setup streams"):
        lifecycle.check_owners(fixture.binding, fixture.completed)
    fixture.binding.inputs["source_setup"]["numpy_rng"] = copy.deepcopy(
        fixture.completed.binding.setup_receipt["numpy_rng_after"]
    )
    fixture.binding.inputs["source_setup"]["tissue_profiles"][0]["membrane_indices"] = [99]
    with pytest.raises(ValueError, match="Foreign supplied source profile"):
        lifecycle.check_owners(fixture.binding, fixture.completed)


def _saved_inputs(tmp_path, *, foreign=False):
    grid = _geometry()
    text = _bound(grid).definition_json
    complete = dict(
        identity="complete",
        binding=dict(
            identity="INIT",
            inputs_raw=dict(
                field=dict(definition=dict(environment_geometry_definition=copy.deepcopy(grid)))
            ),
            material_binding=dict(geometry_binding=dict(definition_json=text)),
        ),
        parent=dict(identity="parent"),
    )
    component = dict(
        identity="SIM",
        expected_init_identity="foreign" if foreign else "INIT",
        inputs=dict(
            sim_phase=dict(field=dict(definition=dict(environment_geometry_definition=grid)))
        ),
        declaration=dict(
            base=dict(material_binding=dict(geometry_binding=dict(definition_json=text)))
        ),
    )
    for name, value in (
        (
            "actual-complete-INIT",
            dict(returned=dict(identity="completed-run", complete_init=complete)),
        ),
        ("SIM-component-binding", dict(returned=component)),
        ("actual-INIT-to-SIM", dict(failure="original synthetic refused input/partial")),
    ):
        archives.write_archive(tmp_path / name, value)


def test_saved_projection_preserves_order_and_original_evidence(owner_guard, tmp_path):
    _saved_inputs(tmp_path)
    before = {
        str(path.relative_to(tmp_path)): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    report = handoff.compare_saved(tmp_path)
    assert report["whole_bound_definition_differences"] == []
    assert [row["kind"] for row in report["projections"]["world"]["raw_differences"]] == [
        "mapping_order"
    ]
    assert report["projections"]["ions"]["raw_differences"] == []
    assert all(value["original_raw_differences"] == [] for value in report["projections"].values())
    assert report["actual_setup_bind_transition_RNG_timestep_calls"] == 0
    assert report["scientific_acceptance"] is False
    assert before == {
        str(path.relative_to(tmp_path)): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }


def test_saved_projection_refuses_changed_evidence(owner_guard, tmp_path):
    _saved_inputs(tmp_path)
    with (tmp_path / "actual-INIT-to-SIM/data.json").open("ab") as stream:
        stream.write(b"preserved corruption")
    with pytest.raises(ValueError, match="Changed saved handoff evidence"):
        handoff.compare_saved(tmp_path)


def test_saved_projection_refuses_foreign_parent(owner_guard, tmp_path):
    _saved_inputs(tmp_path, foreign=True)
    with pytest.raises(ValueError, match="different INIT binding"):
        handoff.compare_saved(tmp_path)


def test_actual_continuity_is_held_before_any_setup_or_output(owner_guard, tmp_path, monkeypatch):
    monkeypatch.delenv(handoff.RELEASE_ENV, raising=False)
    output = tmp_path / "held"
    with pytest.raises(RuntimeError, match="Root run-lifecycle release required"):
        handoff.actual_continuity(output, case="one_INIT_call")
    assert not output.exists()


@pytest.mark.skipif(
    os.environ.get(handoff.RELEASE_ENV) != "1",
    reason="Root-coordinated actual transition/continuity release required",
)
@pytest.mark.parametrize("case", ["zero_INIT_calls", "one_INIT_call"])
def test_actual_retained_handoff_and_checkpoint_continuation(tmp_path, case):
    report = handoff.actual_continuity(tmp_path / case, case=case)
    assert report["restored_exact"] is True and report["cursor"] == 2
    assert report["journals"] == 2 and report["observations"] >= 1
    assert report["scientific_acceptance"] is False
