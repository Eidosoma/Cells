"""Fixed merged-B09 constructor input, separate from physical geometry admission.

This authenticates the existing capture and owns constructor arguments. It
does not generate a mesh, build operators, or produce a geometry bridge input.
"""

import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType

import numpy as np

from cells.processes import betse_environment_field as arrays
from cells.processes import betse_normal_current as records
from cells.processes import betse_perturbations as streams

KIND = "cells.fixed_B09_constructor_input@1"
LAW_ID = "betse_fixed_merged_B09_constructor_input_v1_5_0@1"
CASE = "merged-square-aux"
B09_RECEIPT = Path("/mnt/workspaces/Cells/betse-geometry-development-20261029-03/result.json")
B09_SHA256 = "cbc165a2a899d30136ce3c78224ebec3e9acab9ce11ed08de680a7cd81b6a46f"
NATIVE_REVISION = "5269a714aa2593ed2a6708c4516289977d8ae1a2"
POINT_COUNT = 9


@dataclass(frozen=True, slots=True)
class ConstructorInput:
    case_name: str
    native_input_json: str
    constructor_kwargs: object
    point_ids: tuple
    stream_before: streams.NativeStream
    captured_constructor_points_m: object
    authentication_json: str
    identity: str

    @property
    def native_input(self):
        return json.loads(self.native_input_json)

    @property
    def authentication(self):
        return json.loads(self.authentication_json)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _evidence(case_name):
    if case_name != CASE:
        raise ValueError("Only the fixed merged-square B09 constructor input is admitted")
    receipt_path = B09_RECEIPT.resolve()
    if _sha(receipt_path) != B09_SHA256:
        raise ValueError("Require the unchanged reviewed B09 receipt")
    receipt = json.loads(receipt_path.read_text())
    if receipt["status"] != "passed":
        raise ValueError("Require passed original B09 evidence")
    selected = {}
    for relative in ("native-source/" + CASE + ".json", "native-source/source-manifest.json"):
        path = (receipt_path.parent / relative).resolve()
        if (
            not path.is_relative_to(receipt_path.parent)
            or _sha(path) != receipt["output_sha256"][relative]
        ):
            raise ValueError("Changed fixed B09 constructor capture or source manifest")
        selected[relative] = json.loads(path.read_text())
    raw = selected["native-source/" + CASE + ".json"]
    manifest = selected["native-source/source-manifest.json"]
    if (
        raw["status"] != "passed"
        or raw["name"] != CASE
        or raw["input"]["name"] != CASE
        or manifest["status"] != "passed"
        or manifest["revision"] != NATIVE_REVISION
        or manifest["version"] != "1.5.0"
        or manifest["versions"]["numpy"] != np.__version__
    ):
        raise ValueError("Fixed case, native source revision or exact replay NumPy version differs")
    proof = dict(
        receipt_path=str(receipt_path),
        receipt_sha256=B09_SHA256,
        case_record_sha256=receipt["output_sha256"]["native-source/" + CASE + ".json"],
        source_manifest_sha256=receipt["output_sha256"]["native-source/source-manifest.json"],
        native_source_sha256={k: v["sha256"] for k, v in manifest["files"].items()},
        native_revision=NATIVE_REVISION,
        source_numpy_version=manifest["versions"]["numpy"],
        reused_B09_coverage=True,
        new_geometry_or_RNG_qualification_credit=False,
    )
    return raw, proof


def record(value):
    return dict(
        kind=KIND,
        law_id=LAW_ID,
        case_name=value.case_name,
        native_input=value.native_input,
        constructor_kwargs=value.constructor_kwargs,
        point_ids=value.point_ids,
        stream_before=streams.native_stream_manifest(value.stream_before),
        captured_constructor_points_m=value.captured_constructor_points_m,
        authentication=value.authentication,
        classification="fixed_native_constructor_input_evidence",
        geometry_bridge_admitted=False,
        mesh_computation_executed=False,
        topology_qualified=False,
        physical_geometry=False,
    )


def load(case_name=CASE):
    raw, proof = _evidence(case_name)
    original = raw["input"]
    points = np.asarray(original["seed_points_m"], dtype=np.float64)
    captured = np.asarray(raw["constructed_seed_points_m"], dtype=np.float64)
    ids = tuple(raw["seed_binding"]["original_ids"])
    if (
        points.shape != (POINT_COUNT, 2)
        or captured.shape != points.shape
        or not np.isfinite(points).all()
        or not np.array_equal(points, captured)
        or ids != tuple(original["seed_ids"])
        or len(ids) != POINT_COUNT
        or len(set(ids)) != POINT_COUNT
    ):
        raise ValueError("Fixed constructor coordinates and original occurrence IDs differ")
    kwargs = dict(original["mesh"], seed_points=arrays.frozen(points))
    if (
        not kwargs["allow_merging"]
        or kwargs["mesh_type"] != "quad"
        or not kwargs["make_all_operators"]
    ):
        raise ValueError("Retain all original merged constructor flags without a bridge override")
    if records.record(raw["rng_before"]) != records.record(raw["rng_after_constructor"]):
        raise ValueError("The fixed explicit-point constructor must preserve its full RNG state")
    before = streams._native_stream(raw["rng_before"], np.__version__)
    value = ConstructorInput(
        CASE,
        _json(original),
        MappingProxyType(kwargs),
        ids,
        before,
        arrays.frozen(captured),
        _json(proof),
        "",
    )
    return replace(value, identity=records._digest(record(value)))


def validate(value):
    if type(value) is not ConstructorInput:
        raise ValueError("Require the complete fixed constructor input")
    if type(value.constructor_kwargs) is not MappingProxyType or type(value.point_ids) is not tuple:
        raise ValueError("Require immutable constructor metadata and occurrence IDs")
    expected = load(value.case_name)
    if value.identity != expected.identity or records.record(record(value)) != records.record(
        record(expected)
    ):
        raise ValueError("Changed constructor arguments, ownership, RNG or fixed source authority")
    for array in (value.constructor_kwargs["seed_points"], value.captured_constructor_points_m):
        owner = array
        while isinstance(owner, np.ndarray):
            owner = owner.base
        if array.flags.writeable or not isinstance(owner, bytes):
            raise ValueError("Constructor coordinate evidence must remain immutable")
    return value


def export_input(value):
    validate(value)
    return dict(
        record(value),
        identity=value.identity,
        allowed_next_stage="Source constructor and pre_mesh under separate qualification",
        original_make_all_operators_flag_preserved=True,
        operators_created=False,
        downstream_geometry_admitted=False,
        biological_geometry=False,
    )
