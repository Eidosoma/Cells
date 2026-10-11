"""Explicit retry resources, preserved stop identity and literal byte-exact replay."""

import json
from dataclasses import replace

import numpy as np
import pytest

from cells.io import _sha256 as sha
from cells.io import runtime_identity, source_hashes
from scripts import spatial_extracellular_acceptance_plan as science
from scripts import spatial_extracellular_acceptance_resources as resources
from scripts import verify_spatial_extracellular_build as driver
from scripts.audit_spatial_extracellular_build import ARRAY_FIELDS, compare, implementation
from tests.spatial_extracellular_fixtures import load_cases


def registration(name):
    selected = resources.get_resources(name)
    return selected.registration_fields() | {
        "source_hashes": source_hashes(),
        "runtime": runtime_identity(),
        "implementation_files_sha256": implementation(selected),
    }


@pytest.mark.parametrize("name,seconds", [("v1", 3600), ("v2", 7200)])
def test_explicit_profiles_roundtrip_without_mutating_science(name, seconds):
    selected = resources.get_resources(name)
    assert selected.max_seconds == seconds
    assert resources.from_registration(registration(name)) == selected
    assert science.MAX_SECONDS == 3600 and science.MAX_BYTES == 2 * 2**30
    assert sha(science.PROTOCOL) == (
        "55a8a5aec1968793b598c728275950cf4b92fbc30beb75043984fe39421c8d45"
    )


@pytest.mark.parametrize("name", [None, [], {}, 2, "v3"])
def test_unknown_profiles_are_refused(name):
    with pytest.raises(ValueError, match="Unknown"):
        resources.get_resources(name)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", "cells.core010_registration@1"),
        ("resource_plan", "v1"),
        ("resource_plan", "v3"),
        ("resource_plan", []),
        ("max_seconds", 3600),
        ("max_seconds", 10000),
        ("max_artifact_bytes", 4 * 2**30),
        ("protocol_sha256", "0" * 64),
        ("resource_definition_sha256", "0" * 64),
    ],
)
def test_registered_resources_cannot_be_changed(field, value):
    saved = registration("v2") | {field: value}
    with pytest.raises(ValueError):
        resources.from_registration(saved)


@pytest.mark.parametrize("field", ["resource_plan", "resource_definition_sha256"])
def test_legacy_registration_rejects_retry_metadata(field):
    saved = registration("v1") | {field: "v1"}
    with pytest.raises(ValueError):
        resources.from_registration(saved)


def test_v2_captures_both_protocols_projection_and_baseline():
    selected = resources.get_resources("v2")
    captured = implementation(selected)
    for path in selected.capture_paths:
        assert captured[str(path.relative_to(resources.ROOT))] == sha(path)
    assert resources.STOPPED not in selected.capture_paths
    assert selected.baseline == resources.V2_BASELINE
    assert selected.allowed_edits == resources.RETRY_EDITS


def test_prior_stopped_evidence_and_frozen_definition_coverage():
    proof = resources.authenticate_prior_stop(resources.get_resources("v2"))
    assert proof == {"receipt_sha256": sha(resources.STOPPED), "files": 880}
    saved = json.loads(resources.STOPPED.read_text())
    prior = json.loads((resources.ROOT / saved["session"] / "registration.json").read_text())
    _, cases = load_cases()
    assert prior["eager_schedule"] == science.eager_schedule(cases)
    assert prior["definitions"] == {
        f"{mode}/{case.id}": science.registered_spec(case, mode).to_dict()
        for mode in ("jit", "eager", "refined")
        for case in cases
    }


@pytest.mark.parametrize("name", ["v1", "v2"])
def test_child_context_selects_the_saved_resource_profile(tmp_path, name):
    saved = registration(name)
    (tmp_path / "registration.json").write_text(json.dumps(saved))
    driver.context(tmp_path)
    saved["max_seconds"] += 1
    (tmp_path / "registration.json").write_text(json.dumps(saved))
    with pytest.raises(ValueError, match="Registered resource"):
        driver.context(tmp_path)


@pytest.mark.parametrize("name", ["v1", "v2"])
def test_guard_enforces_selected_time_limit(tmp_path, monkeypatch, name):
    selected = resources.get_resources(name)
    monkeypatch.setattr(driver, "monotonic", lambda: selected.max_seconds)
    driver.guard(tmp_path, 0, selected)
    monkeypatch.setattr(driver, "monotonic", lambda: selected.max_seconds + 0.001)
    with pytest.raises(ValueError, match="wall budget"):
        driver.guard(tmp_path, 0, selected)


def test_artifact_budget_still_applies(tmp_path, monkeypatch):
    (tmp_path / "payload").write_bytes(b"123")
    monkeypatch.setattr(science, "MAX_BYTES", 2)
    monkeypatch.setattr(driver, "monotonic", lambda: 0)
    with pytest.raises(ValueError, match="artifact budget"):
        driver.guard(tmp_path, 0, resources.PROFILES["v1"])


@pytest.mark.parametrize("name", ["v1", "v2"])
def test_driver_registers_before_work_and_retains_failure(tmp_path, monkeypatch, name):
    selected = resources.get_resources(name)
    alarms = []
    monkeypatch.setattr(driver.signal, "alarm", alarms.append)
    monkeypatch.setattr(driver.os, "sched_getaffinity", lambda _: {0, 1, 2, 3})
    for key in science.THREADS:
        monkeypatch.setenv(key, "1")

    def refuse_trajectory_work(*args, **kwargs):
        raise RuntimeError("synthetic prelude stop")

    monkeypatch.setattr(driver, "audit_reference", refuse_trajectory_work)
    output = tmp_path / "capture"
    with pytest.raises(RuntimeError, match="synthetic prelude stop"):
        driver.verify(output, resources=selected)
    saved = json.loads((output / "registration.json").read_text())
    assert resources.from_registration(saved) == selected
    assert saved["implementation_files_sha256"] == implementation(selected)
    failure = json.loads((output / "failure.json").read_text())
    assert failure["error"] == "synthetic prelude stop"
    assert failure["implementation_files_sha256"] == implementation(selected)
    assert not (output / "verification.json").exists()
    assert alarms == [selected.max_seconds, 0]
    with pytest.raises(FileExistsError):
        driver.verify(output, resources=selected)


def test_profile_is_immutable():
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        resources.PROFILES["v2"].max_seconds = 10000
    # A different object is not the registered profile.
    assert replace(resources.PROFILES["v2"], max_seconds=10000) != resources.PROFILES["v2"]


def exact_arrays():
    return {field: np.zeros((2,), dtype=np.float64) for field in ARRAY_FIELDS}


def test_exact_comparison_accepts_an_identical_copy():
    values = exact_arrays()
    assert compare(None, values, {k: v.copy() for k, v in values.items()}, {}, exact=True) == {
        "exact_arrays": 73
    }


@pytest.mark.parametrize("field", sorted(ARRAY_FIELDS))
def test_exact_comparison_rejects_changed_zero_sign_in_every_field(field):
    values = exact_arrays()
    changed = {k: v.copy() for k, v in values.items()}
    changed[field][0] = -0.0
    with pytest.raises(ValueError, match="Byte-exact"):
        compare(None, values, changed, {}, exact=True)


@pytest.mark.parametrize("dtype", [np.float32, np.int64, ">f8"])
def test_exact_comparison_rejects_changed_dtype(dtype):
    values = exact_arrays()
    changed = values | {"amount_increment": values["amount_increment"].astype(dtype)}
    with pytest.raises(ValueError, match="Byte-exact"):
        compare(None, values, changed, {}, exact=True)


def test_exact_comparison_rejects_changed_shape():
    values = exact_arrays()
    changed = values | {"amount_increment": values["amount_increment"].reshape(1, 2)}
    with pytest.raises(AssertionError):
        compare(None, values, changed, {}, exact=True)
