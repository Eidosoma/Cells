"""Prepared fixed-B09 input checks; no constructor or mesh is executed."""

import json
from dataclasses import replace
from types import MappingProxyType

import numpy as np
import pytest

from cells.processes import betse_b09_constructor_input as inputs
from cells.processes import betse_environment_field as arrays
from cells.processes import betse_geometry_initialization as geometry
from cells.processes import betse_normal_current as records
from cells.processes import betse_perturbations as streams


def test_fixed_constructor_input_retains_merging_flags_occurrences_and_complete_stream():
    value = inputs.load()
    assert value.case_name == "merged-square-aux" and len(value.point_ids) == 9
    assert value.constructor_kwargs["allow_merging"] is True
    assert value.constructor_kwargs["mesh_type"] == "quad"
    assert value.constructor_kwargs["make_all_operators"] is True
    np.testing.assert_array_equal(
        value.constructor_kwargs["seed_points"], value.native_input["seed_points_m"]
    )
    assert len(streams.native_stream_manifest(value.stream_before)["state"][1]) == 624
    assert value.authentication["receipt_sha256"] == inputs.B09_SHA256
    inputs.validate(value)


def test_physical_geometry_bridge_still_refuses_merged_constructor():
    value = inputs.load()
    with pytest.raises(ValueError):
        geometry.bind(
            dict(
                kind=geometry.KIND,
                classification="manufactured_seed_cloud",
                provenance="Fixed B09 constructor input only",
                native_input=value.native_input,
            )
        )
    exported = inputs.export_input(value)
    assert exported["kind"] == "cells.fixed_B09_constructor_input@1"
    assert not exported["geometry_bridge_admitted"] and not exported["topology_qualified"]
    assert not exported["operators_created"] and not exported["downstream_geometry_admitted"]


@pytest.mark.parametrize(
    "target", ("points", "merging", "stream", "point_ids", "authority", "native_input")
)
def test_resealed_constructor_evidence_tampering_is_refused(target):
    value = inputs.load()
    if target in ("points", "merging"):
        kwargs = dict(value.constructor_kwargs)
        if target == "points":
            kwargs["seed_points"] = arrays.frozen(kwargs["seed_points"] + 1e-7)
        else:
            kwargs["allow_merging"] = False
        value = replace(value, constructor_kwargs=MappingProxyType(kwargs))
    elif target == "stream":
        value = replace(value, stream_before=streams.native_stream(18))
    elif target == "point_ids":
        value = replace(value, point_ids=tuple(reversed(value.point_ids)))
    elif target == "authority":
        proof = value.authentication
        proof["case_record_sha256"] = "0" * 64
        value = replace(value, authentication_json=json.dumps(proof))
    else:
        native = value.native_input
        native["seed"] = 18
        value = replace(value, native_input_json=json.dumps(native))
    value = replace(value, identity=records._digest(inputs.record(value)))
    with pytest.raises(ValueError):
        inputs.validate(value)


@pytest.mark.parametrize(
    "name", ("caller-native-lattice", "manufactured-cloud", "irregular-centroid-aux")
)
def test_case_selector_is_a_fixed_capture_authority(name):
    with pytest.raises(ValueError):
        inputs.load(name)


def test_constructor_buffers_and_metadata_are_owned():
    value = inputs.load()
    for array in (value.constructor_kwargs["seed_points"], value.captured_constructor_points_m):
        with pytest.raises(ValueError):
            array.setflags(write=True)
    changed = value.native_input
    changed["mesh"]["allow_merging"] = False
    assert value.native_input["mesh"]["allow_merging"] is True
    with pytest.raises(TypeError):
        value.constructor_kwargs["merge_thresh"] = 0.9


def test_input_loader_preserves_global_random_state():
    before = np.random.get_state()
    inputs.load()
    after = np.random.get_state()
    assert before[0] == after[0] and before[2:] == after[2:]
    np.testing.assert_array_equal(before[1], after[1])


def test_forged_receipt_cannot_become_constructor_authority(tmp_path, monkeypatch):
    fake = tmp_path / "forged.json"
    fake.write_text(json.dumps(dict(status="passed", output_sha256={})))
    monkeypatch.setattr(inputs, "B09_RECEIPT", fake)
    with pytest.raises(ValueError):
        inputs.load()
