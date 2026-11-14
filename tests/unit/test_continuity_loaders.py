"""Checkpoint continuity at the two loaders (docs/CHECKPOINT_CONTINUITY_DESIGN.md, section 10).

1. Refusal stays the default. Without a record, every refusal of io.load_snapshot and
   batch_io.load_batch_snapshot is today's, message for message, and cells.continuity is
   never called (section 10.1).
2. No record relaxes case 3: a corrupted fingerprint or state, a renamed model ID (D146), a
   version-3 definition over a version-2 checkpoint (D147) and a changed layout value are
   refused with a valid record (section 10.2).
3. A record binds one manifest and one pair of identities, and the first landing's scope
   (section 10.3).
Then the admitted loads, scalar and cohort, and the module's host-only imports. Snapshots are
step-0 checkpoints and the records are hand-built (validation/continuity/admit.py writes the
real ones), so nothing here compiles a model program.
"""

import ast
import copy
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from cells import batch_io, continuity, io
from cells.core.batch import parse_batch
from cells.core.specs import ConfigError, digest, parse_spec, read_json
from cells.core.state import initialise
from tests.batch_fixtures import definition, short_spec

ROOT = Path(__file__).resolve().parents[2]
POLICY = {"window_steps": 8, "recording": "checkpoints"}
CHANGED = "core/phases.py"  # The file a simulated host-only landing changes.


# ---------------------------------------------------------------- helpers


@pytest.fixture
def scalar(tmp_path, spec):
    """A step-0 snapshot of the single-cell definition (tests/conftest.py)."""
    return io.write_snapshot(tmp_path / "scalar", spec, initialise(spec))


@pytest.fixture
def cohort(tmp_path):
    """Two step-0 single-cell worlds (IDs 10 and 11) with different decay rates."""
    first = short_spec("single_cell_pulse")
    raw = first.to_dict()
    raw["model"]["parameters"]["decay_rate"] = 0.5
    batch = parse_batch(definition([first, parse_spec(raw)]).to_dict())
    starts = {w.world_id: initialise(w.simulation) for w in batch.worlds}
    return batch_io.write_batch_snapshot(tmp_path / "cohort", batch, starts)


def manifest_of(path):
    return json.loads((Path(path) / "manifest.json").read_text())


def rewrite(path, transform):
    """Change a manifest and restore its manifest_sha256, so only the change is seen."""
    manifest = manifest_of(path)
    transform(manifest)
    manifest.pop("manifest_sha256", None)
    manifest["manifest_sha256"] = digest(manifest)
    (Path(path) / "manifest.json").write_text(json.dumps(manifest))
    return manifest["manifest_sha256"]


def rewrite_child(cohort_path, world_id, transform):
    """Change one child's manifest and re-bind it in its cohort manifest."""
    child = Path(cohort_path) / f"world-{world_id}"
    fingerprint = rewrite(child, transform)

    def rebind(manifest):
        for record in manifest["worlds"]:
            if record["world_id"] == world_id:
                record["snapshot_sha256"] = fingerprint

    return rewrite(cohort_path, rebind)


def change_source(monkeypatch, name=CHANGED):
    """This installation as after a landing that changed one file under src/cells."""
    changed = {**io.source_hashes(), name: "0" * 64}
    monkeypatch.setattr(io, "source_hashes", lambda: changed)
    monkeypatch.setattr(batch_io, "source_hashes", lambda: changed)
    return changed


def change_runtime(monkeypatch, edit):
    """This installation's runtime identity, edited (for every backend)."""
    real = io.runtime_identity("cpu")

    def changed(backend="cpu"):
        value = copy.deepcopy(real)
        edit(value)
        return value

    monkeypatch.setattr(io, "runtime_identity", changed)
    monkeypatch.setattr(batch_io, "runtime_identity", changed)
    return changed("cpu")


def build_record(snapshot, **overrides):
    """A complete, sealed record admitting the snapshot under the current installation.

    overrides replace top-level fields, or nested ones as {"to.runtime": value}.
    """
    manifest = manifest_of(snapshot)
    if manifest["kind"] == continuity.FORMATS[1]:
        definitions, clocks = {}, {}
        for world in manifest["worlds"]:
            child = manifest_of(Path(snapshot) / world["path"])
            definitions[str(world["world_id"])] = child["spec_sha256"]
            clocks[str(world["world_id"])] = child["clock"]
    else:
        definitions = {continuity.SCALAR: manifest["spec_sha256"]}
        clocks = {continuity.SCALAR: manifest["clock"]}
    current = batch_io.source_hashes()
    runtime = batch_io.runtime_identity("cpu")
    record = {
        "kind": continuity.RECORD_KIND,
        "checkpoint": {
            "format": manifest["kind"],
            "path": str(snapshot),
            "manifest_sha256": manifest["manifest_sha256"],
            "definitions": definitions,
            "clocks": clocks,
        },
        "from": {
            "source_hashes_sha256": digest(manifest["source_hashes"]),
            "tree": "/scratch/s0/src",
            "git_revision": None,
            "dirty_diff": None,
            "tree_reproduces_manifest": True,
            "runtime": manifest["runtime"],
        },
        "to": {
            "source_hashes_sha256": digest(current),
            "tree": "/scratch/s1/src",
            "git_revision": None,
            "dirty_diff": None,
            "runtime": runtime,
        },
        "changed_files": continuity.changed_files(manifest["source_hashes"], current),
        "probe": {"runtime": runtime, "host_fields_equal_to_runtime": True},
        "source_admission": {"case": "identical_programs"},
        "runtime_admission": {"case": "none", "fields": []},
        "scope": {
            "paths": ["vector_windows"],
            "policy": dict(POLICY),
            "horizon_rounds": 4,
            "overlap_rounds": 2,
        },
        "lineage": [],
        "evidence": [{"role": "comparison", "path": "/evidence/compare.json", "sha256": "1" * 64}],
        "residual": ["hand-built test record; no probe ran"],
        "admitted_by": {"name": "test suite (hand-built record)", "role": "test"},
        "admitted_utc": "2026-11-13T00:00:00+00:00",
    }
    for key, value in overrides.items():
        target, *rest = key.split(".")
        if rest:
            record[target] = {**record[target], rest[0]: value}
        else:
            record[key] = value
    return continuity.seal(record)


def write_record(directory, record):
    path = Path(directory) / "record.json"
    path.write_text(json.dumps(record))
    return path


def request(directory, record, *, path="vector_windows", policy=None):
    return continuity.Request(write_record(directory, record), path=path, policy=policy or POLICY)


def refused(load, message):
    with pytest.raises(ConfigError) as caught:
        load()
    assert str(caught.value) == message
    return caught.value


# ---------------------------------------------------------------- 1. the default path


@pytest.fixture
def untouched(monkeypatch):
    """cells.continuity must not be reached without a record."""

    def forbidden(*args, **kwargs):
        raise AssertionError("cells.continuity was called without a record")

    for name in ("bind", "parse_record", "seal", "provenance"):
        monkeypatch.setattr(continuity, name, forbidden)


SCALAR_REFUSALS = {
    "fields": (lambda m: m.update(extra=1), "Invalid checkpoint manifest fields"),
    "schema": (lambda m: m.update(schema_version=99), "Unsupported checkpoint schema"),
    "kind": (lambda m: m.update(kind="other"), "Not a complete Cells numerical checkpoint"),
    "random": (
        lambda m: m.update(random_state=42),
        "These deterministic models have no random state",
    ),
    "source": (
        lambda m: m["source_hashes"].update({CHANGED: "0" * 64}),
        "Checkpoint model/engine source differs from this installation",
    ),
    "runtime": (
        lambda m: m["runtime"].update(python="0.0.0"),
        "Checkpoint runtime differs; cross-runtime migration is not supported",
    ),
    "spec": (
        lambda m: m.update(spec_sha256="0" * 64),
        "Checkpoint specification checksum mismatch",
    ),
    "state": (lambda m: m.update(state_sha256="0" * 64), "Checkpoint state checksum mismatch"),
    "clock_fields": (lambda m: m["clock"].update(extra=1), "Invalid checkpoint clock fields"),
    "time": (lambda m: m["clock"].update(time="0"), "Invalid checkpoint time"),
    "event": (
        lambda m: m["clock"].update(event_index=5),
        "Checkpoint event position is inconsistent with its schedule",
    ),
}


@pytest.mark.parametrize("case", sorted(SCALAR_REFUSALS))
def test_scalar_refusals_without_a_record_are_todays(scalar, untouched, case):
    transform, message = SCALAR_REFUSALS[case]
    rewrite(scalar, transform)
    refused(lambda: io.load_snapshot(scalar), message)
    refused(lambda: io.load_snapshot(scalar, continuity=None), message)


def test_scalar_checksum_and_state_field_refusals_are_todays(scalar, untouched, tmp_path):
    original = (scalar / "manifest.json").read_text()
    manifest = json.loads(original)
    manifest["clock"]["time"] = 1.0  # Without restoring manifest_sha256.
    (scalar / "manifest.json").write_text(json.dumps(manifest))
    refused(lambda: io.load_snapshot(scalar), "Checkpoint manifest checksum mismatch")
    (scalar / "manifest.json").write_text(original)
    with np.load(scalar / "state.npz") as archive:
        arrays = {name: archive[name] for name in archive.files}
    np.savez(scalar / "state.npz", extra=np.zeros(1), **arrays)
    rewrite(scalar, lambda m: m.update(state_sha256=io._sha256(scalar / "state.npz")))
    # Today's message: the field-set refusal is raised inside the archive read and re-raised.
    refused(
        lambda: io.load_snapshot(scalar),
        "Cannot read numeric checkpoint: Invalid checkpoint state fields",
    )


COHORT_REFUSALS = {
    "fields": (
        lambda m: m.update(extra=1),
        "batch checkpoint manifest: missing=[], unknown=['extra']",
    ),
    "schema": (lambda m: m.update(schema_version=2), "Unsupported batch checkpoint schema"),
    "kind": (lambda m: m.update(kind="other"), "Not a complete independent-world checkpoint"),
    "source": (
        lambda m: m["source_hashes"].update({CHANGED: "0" * 64}),
        "Batch checkpoint source differs from this installation",
    ),
    "runtime": (
        lambda m: m["runtime"].update(cells_version="0.0.0"),
        "Batch checkpoint runtime differs; no implicit migration",
    ),
    "spec": (
        lambda m: m.update(spec_sha256="0" * 64),
        "Batch checkpoint specification checksum mismatch",
    ),
    "inventory": (
        lambda m: m.update(worlds=m["worlds"][:1]),
        "Batch checkpoint world inventory differs",
    ),
    "order": (
        lambda m: m["worlds"][0].update(world_id=99),
        "Batch checkpoint world identity/order differs",
    ),
    "path": (
        lambda m: m["worlds"][0].update(path="../outside"),
        "Invalid batch checkpoint child path",
    ),
    "child_identity": (
        lambda m: m["worlds"][0].update(snapshot_sha256="0" * 64),
        "Batch checkpoint child specification/identity differs",
    ),
}


@pytest.mark.parametrize("case", sorted(COHORT_REFUSALS))
def test_cohort_refusals_without_a_record_are_todays(cohort, untouched, case):
    transform, message = COHORT_REFUSALS[case]
    rewrite(cohort, transform)
    refused(lambda: batch_io.load_batch_snapshot(cohort), message)
    refused(lambda: batch_io.load_batch_snapshot(cohort, continuity=None), message)


def test_cohort_checksum_and_escape_refusals_are_todays(cohort, untouched, tmp_path):
    original = (cohort / "manifest.json").read_text()
    manifest = json.loads(original)
    manifest["spec_sha256"] = "0" * 64  # Without restoring manifest_sha256.
    (cohort / "manifest.json").write_text(json.dumps(manifest))
    refused(
        lambda: batch_io.load_batch_snapshot(cohort), "Batch checkpoint manifest checksum mismatch"
    )
    (cohort / "manifest.json").write_text(original)
    first = cohort / "world-10"
    first.rename(tmp_path / "world-10")
    first.symlink_to(tmp_path / "world-10")
    refused(
        lambda: batch_io.load_batch_snapshot(cohort), "Batch checkpoint child escapes its directory"
    )


CHILD_REFUSALS = {
    "source": (
        lambda m: m["source_hashes"].update({CHANGED: "0" * 64}),
        "Checkpoint model/engine source differs from this installation",
    ),
    "runtime": (
        lambda m: m["runtime"].update(python="0.0.0"),
        "Checkpoint runtime differs; cross-runtime migration is not supported",
    ),
    "state": (lambda m: m.update(state_sha256="0" * 64), "Checkpoint state checksum mismatch"),
}


@pytest.mark.parametrize("case", sorted(CHILD_REFUSALS))
def test_cohort_child_refusals_without_a_record_are_todays(cohort, untouched, case):
    transform, message = CHILD_REFUSALS[case]
    rewrite_child(cohort, 11, transform)
    refused(lambda: batch_io.load_batch_snapshot(cohort), message)


def test_loads_without_a_record_never_reach_continuity(scalar, cohort, untouched):
    saved = io.load_snapshot(scalar)
    assert saved.admission is None and saved.spec == parse_spec(manifest_of(scalar)["spec"])
    restored = batch_io.load_batch_snapshot(cohort)
    assert restored.admission is None and sorted(restored.checkpoints) == [10, 11]


def test_without_a_record_a_source_change_still_refuses(scalar, cohort, monkeypatch):
    change_source(monkeypatch)
    refused(
        lambda: io.load_snapshot(scalar),
        "Checkpoint model/engine source differs from this installation",
    )
    refused(
        lambda: batch_io.load_batch_snapshot(cohort),
        "Batch checkpoint source differs from this installation",
    )


# ---------------------------------------------------------------- admitted loads


def test_a_record_admits_a_scalar_source_change(scalar, monkeypatch, tmp_path):
    change_source(monkeypatch)
    record = build_record(scalar)
    wanted = request(tmp_path, record)
    saved = io.load_snapshot(scalar, continuity=wanted)
    assert saved.admission.record_sha256 == record["record_sha256"]
    assert saved.admission.checkpoint_manifest_sha256 == manifest_of(scalar)["manifest_sha256"]
    for a, b in zip(saved.checkpoint.state, initialise(saved.spec).state, strict=True):
        np.testing.assert_array_equal(np.asarray(a), np.asarray(b))
    assert continuity.provenance(saved.admission) == {
        "operation": "admitted_resume",
        "continuity_record": str(wanted.record),
        "record_sha256": record["record_sha256"],
        "source_admission": "identical_programs",
        "declared_path": "vector_windows",
        "declared_policy": POLICY,
        "parent_checkpoint_sha256": manifest_of(scalar)["manifest_sha256"],
    }


def test_a_record_admits_a_cohort_source_change(cohort, monkeypatch, tmp_path):
    reference = batch_io.load_batch_snapshot(cohort)
    change_source(monkeypatch)
    record = build_record(cohort)
    saved = batch_io.load_batch_snapshot(cohort, continuity=request(tmp_path, record))
    assert saved.admission.record_sha256 == record["record_sha256"]
    assert saved.spec == reference.spec and saved.fingerprint == reference.fingerprint
    for identity, checkpoint in saved.checkpoints.items():
        for a, b in zip(checkpoint.state, reference.checkpoints[identity].state, strict=True):
            np.testing.assert_array_equal(np.asarray(a), np.asarray(b))
    assert continuity.provenance(saved.admission)["operation"] == "admitted_resume"


def test_a_window_policy_object_is_declared_as_its_dict(scalar, monkeypatch, tmp_path):
    from cells.core.windows import WindowPolicy

    change_source(monkeypatch)
    path = write_record(tmp_path, build_record(scalar))
    wanted = continuity.Request(path, path="vector_windows", policy=WindowPolicy(8, "checkpoints"))
    assert io.load_snapshot(scalar, continuity=wanted).admission.policy == POLICY


def test_a_record_admits_case_2_only_from_the_lead(scalar, monkeypatch, tmp_path):
    change_source(monkeypatch)
    d148 = {
        "case": "d148",
        "decision": "D148",
        "before": "/snapshots/B",
        "after": "/snapshots/A",
        "guard": "/evidence/inplace-compare.json",
        "ledger_fields_across_seam": ["electrode_charge_transferred_C"],
    }
    lead = {"name": "the lead", "role": "lead"}
    record = build_record(scalar, source_admission=d148, admitted_by=lead)
    assert io.load_snapshot(scalar, continuity=request(tmp_path, record)).admission.case == "d148"
    record = build_record(scalar, source_admission=d148)
    refused(
        lambda: io.load_snapshot(scalar, continuity=request(tmp_path, record)),
        "Continuity record: case 2 (a D148 record) is admitted by the lead",
    )
    for missing in ("decision", "before", "after", "guard"):
        partial = {k: v for k, v in d148.items() if k != missing}
        record = build_record(scalar, source_admission=partial, admitted_by=lead)
        with pytest.raises(ConfigError, match="source_admission \\(d148\\) must have exactly"):
            io.load_snapshot(scalar, continuity=request(tmp_path, record))


# ---------------------------------------------------------------- 2. case 3 is never relaxed


def test_no_record_relaxes_the_fingerprint_or_the_state(scalar, monkeypatch, tmp_path):
    change_source(monkeypatch)
    rewrite(scalar, lambda m: m.update(spec_sha256="0" * 64))
    record = build_record(scalar, **{"checkpoint.definitions": {"scalar": "0" * 64}})
    with pytest.raises(ConfigError):  # The record's definitions cannot match a parsed spec...
        io.load_snapshot(scalar, continuity=request(tmp_path, record))
    record = build_record(scalar)  # ... nor does a record of the true fingerprint help.
    record = continuity.seal(
        {
            **record,
            "checkpoint": {
                **record["checkpoint"],
                "definitions": {"scalar": parse_spec(manifest_of(scalar)["spec"]).fingerprint},
            },
        }
    )
    refused(
        lambda: io.load_snapshot(scalar, continuity=request(tmp_path, record)),
        "Checkpoint specification checksum mismatch",
    )
    rewrite(scalar, lambda m: m.update(spec_sha256=record["checkpoint"]["definitions"]["scalar"]))
    with (scalar / "state.npz").open("ab") as handle:
        handle.write(b"corrupted")
    record = build_record(scalar)
    refused(
        lambda: io.load_snapshot(scalar, continuity=request(tmp_path, record)),
        "Checkpoint state checksum mismatch",
    )


def test_no_record_relaxes_a_renamed_model_id(scalar, monkeypatch, tmp_path):
    """D146: old configs and checkpoints are refused; no alias."""
    change_source(monkeypatch)
    rewrite(scalar, lambda m: m["spec"]["model"].update(id="bitsey_source_decay@1"))
    record = build_record(scalar)
    with pytest.raises(ConfigError, match="^Unknown model: 'bitsey_source_decay@1'"):
        io.load_snapshot(scalar, continuity=request(tmp_path, record))


def test_no_record_relaxes_a_changed_layout_value(scalar, monkeypatch, tmp_path):
    change_source(monkeypatch)
    with np.load(scalar / "state.npz") as archive:
        arrays = {name: archive[name] for name in archive.files}
    arrays["volume"] = arrays["volume"] * 2.0
    np.savez(scalar / "state.npz", **arrays)
    rewrite(scalar, lambda m: m.update(state_sha256=io._sha256(scalar / "state.npz")))
    record = build_record(scalar)
    refused(
        lambda: io.load_snapshot(scalar, continuity=request(tmp_path, record)),
        "Checkpoint layout volume does not match the model definition",
    )


def test_no_record_relaxes_a_solver_version_switch(monkeypatch, tmp_path):
    """D147: a version-3 definition cannot resume from a version-2 checkpoint."""
    from cells.numerics import surface_field as field
    from cells.numerics import surface_imex as imex
    from validation.tissue import surface_pump_fixtures

    raw = surface_pump_fixtures.definition("clamped", solver=imex.ARS222_ID)
    raw["execution"]["field_solver"] = field.FACTORED_SOLVER_ID
    two = parse_spec(raw)
    path = io.write_snapshot(tmp_path / "v2", two, initialise(two))
    raw["execution"]["field_solver"] = field.FLOOR_SOLVER_ID
    three = parse_spec(raw)
    rewrite(path, lambda m: m.update(spec=three.to_dict(), spec_sha256=three.fingerprint))
    change_source(monkeypatch)
    record = build_record(path)
    with pytest.raises(ConfigError, match="state fields|layout") as caught:
        io.load_snapshot(path, continuity=request(tmp_path, record))
    assert "Continuity" not in str(caught.value)


# ---------------------------------------------------------------- 3. the record's binding


def test_the_record_binds_one_manifest_and_both_sources(scalar, monkeypatch, tmp_path):
    current = change_source(monkeypatch)
    cases = {
        "Continuity record binds another checkpoint manifest": {
            "checkpoint.manifest_sha256": "0" * 64
        },
        "Continuity record's from source is not the checkpoint's": {
            "from.source_hashes_sha256": digest(current)
        },
        "Continuity record's to source is not this installation's": {
            "to.source_hashes_sha256": digest(manifest_of(scalar)["source_hashes"])
        },
        "Continuity record's changed_files are not the files that differ": {
            "changed_files": ["core/runner.py"]
        },
        "Continuity record binds a cells_independent_world_checkpoint, "
        "not a cells_complete_numerical_checkpoint": {
            "checkpoint.format": continuity.FORMATS[1],
            "checkpoint.definitions": {"10": "0" * 64},
            "checkpoint.clocks": {"10": manifest_of(scalar)["clock"]},
        },
        "Continuity record's from runtime is not the checkpoint's": {
            "from.runtime": {**manifest_of(scalar)["runtime"], "python": "0.0.0"}
        },
        "Continuity record's to runtime is not this installation's": {
            "to.runtime": {**io.runtime_identity("cpu"), "python": "0.0.0"}
        },
        "Continuity record's definitions are not the checkpoint's": {
            "checkpoint.definitions": {"scalar": "0" * 64}
        },
        "Continuity record's clock of scalar is not the checkpoint's": {
            "checkpoint.clocks": {"scalar": {"time": 0.0, "step_index": 0, "event_index": 1}}
        },
    }
    for message, overrides in cases.items():
        record = build_record(scalar, **overrides)
        refused(lambda r=record: io.load_snapshot(scalar, continuity=request(tmp_path, r)), message)


def test_the_record_itself_is_verified(scalar, monkeypatch, tmp_path):
    change_source(monkeypatch)
    record = build_record(scalar)
    tampered = {**record, "residual": ["edited after admission"]}
    refused(
        lambda: io.load_snapshot(scalar, continuity=request(tmp_path, tampered)),
        "Continuity record: record_sha256 does not match the record (changed after it was "
        "admitted)",
    )
    proposed = {k: v for k, v in record.items() if k not in ("admitted_by", "record_sha256")}
    refused(
        lambda: io.load_snapshot(scalar, continuity=request(tmp_path, proposed)),
        "Continuity record: not admitted: admitted_by is missing (admit.py finalises a "
        "proposed record)",
    )
    for field, value, message in (
        ("kind", "cells.checkpoint_continuity@0", "kind must be"),
        ("probe", {"runtime": {}, "host_fields_equal_to_runtime": True}, "probe.runtime"),
        ("evidence", [], "evidence must be a nonempty list"),
        ("scope", {**record["scope"], "overlap_rounds": 1}, "at least two rounds"),
        ("from", {**record["from"], "tree_reproduces_manifest": False}, "reproduce"),
    ):
        broken = continuity.seal({**record, field: value})
        with pytest.raises(ConfigError, match=message):
            io.load_snapshot(scalar, continuity=request(tmp_path, broken))
    missing = tmp_path / "absent.json"
    with pytest.raises(ConfigError, match="Cannot read the continuity record"):
        io.load_snapshot(scalar, continuity=continuity.Request(missing, "vector_windows", POLICY))


def test_the_declared_scope_is_the_records(scalar, monkeypatch, tmp_path):
    change_source(monkeypatch)
    record = build_record(scalar)
    for path in ("runner", "windows", "batch", "batch_windows"):
        refused(
            lambda p=path: io.load_snapshot(scalar, continuity=request(tmp_path, record, path=p)),
            f"Continuity cannot decide the {path} path: the first landing decides vector "
            "windows only (docs/CHECKPOINT_CONTINUITY_DESIGN.md, section 13.1)",
        )
    other = build_record(scalar, **{"scope.paths": ["batch_windows"]})
    refused(
        lambda: io.load_snapshot(scalar, continuity=request(tmp_path, other)),
        "Continuity record's scope does not cover the path vector_windows",
    )
    policy = {"window_steps": 16, "recording": "checkpoints"}
    refused(
        lambda: io.load_snapshot(scalar, continuity=request(tmp_path, record, policy=policy)),
        f"Continuity record's scope does not cover the window policy {policy}",
    )
    with pytest.raises(ConfigError, match="Unknown execution path"):
        continuity.Request(tmp_path / "record.json", path="projective", policy=POLICY)
    with pytest.raises(ConfigError, match="must be a cells.continuity.Request"):
        io.load_snapshot(scalar, continuity={"record": str(tmp_path / "record.json")})


def test_every_runtime_change_is_refused_in_the_first_landing(scalar, monkeypatch, tmp_path):
    change_source(monkeypatch)
    before = manifest_of(scalar)["runtime"]
    after = change_runtime(monkeypatch, lambda r: r["packages"].update(numpy="0.0.0"))
    unnamed = build_record(scalar)
    refused(
        lambda: io.load_snapshot(scalar, continuity=request(tmp_path, unnamed)),
        "Continuity record must name exactly the differing runtime fields: unnamed "
        "['packages.numpy'], extra []",
    )
    entry = {
        "field": "packages.numpy",
        "class": "host",
        "from": before["packages"]["numpy"],
        "to": "0.0.0",
        "test": "P, B and H under both runtimes",
        "evidence": "/evidence/host.json",
    }
    named = build_record(scalar, runtime_admission={"case": "fields", "fields": [entry]})
    refused(
        lambda: io.load_snapshot(scalar, continuity=request(tmp_path, named)),
        "Runtime changes are parked: the first landing refuses every runtime change "
        "(['packages.numpy'])",
    )
    misstated = build_record(
        scalar, runtime_admission={"case": "fields", "fields": [{**entry, "to": "9.9.9"}]}
    )
    refused(
        lambda: io.load_snapshot(scalar, continuity=request(tmp_path, misstated)),
        "Continuity record misstates the runtime field packages.numpy",
    )
    assert after["packages"]["numpy"] == "0.0.0"


def test_an_extra_runtime_field_and_the_execution_mode_are_refused(scalar, monkeypatch, tmp_path):
    change_source(monkeypatch)
    runtime = io.runtime_identity("cpu")
    entry = {
        "field": "packages.numpy",
        "class": "host",
        "from": runtime["packages"]["numpy"],
        "to": runtime["packages"]["numpy"],
        "test": "P, B and H under both runtimes",
        "evidence": "/evidence/host.json",
    }
    extra = build_record(scalar, runtime_admission={"case": "fields", "fields": [entry]})
    refused(
        lambda: io.load_snapshot(scalar, continuity=request(tmp_path, extra)),
        "Continuity record must name exactly the differing runtime fields: unnamed [], extra "
        "['packages.numpy']",
    )
    jit = {**entry, "field": "numerical_environment.JAX_DISABLE_JIT", "class": "execution_mode"}
    named = build_record(scalar, runtime_admission={"case": "fields", "fields": [jit]})
    with pytest.raises(ConfigError, match="changes the execution mode, which is refused"):
        io.load_snapshot(scalar, continuity=request(tmp_path, named))
    compiler = {**entry, "field": "packages.jaxlib", "class": "compiler", "test": "tolerance"}
    unregistered = build_record(scalar, runtime_admission={"case": "fields", "fields": [compiler]})
    with pytest.raises(ConfigError, match="decided by tolerance and needs a registered variant"):
        io.load_snapshot(scalar, continuity=request(tmp_path, unregistered))
    source = {**entry, "field": "cells_version", "class": "source"}
    version = build_record(scalar, runtime_admission={"case": "fields", "fields": [source]})
    with pytest.raises(ConfigError, match="a source field, covered by the source admission"):
        io.load_snapshot(scalar, continuity=request(tmp_path, version))


def test_a_registered_tolerance_variant_is_still_parked(scalar, monkeypatch, tmp_path):
    change_source(monkeypatch)
    before = manifest_of(scalar)["runtime"]["packages"]["jaxlib"]
    change_runtime(monkeypatch, lambda r: r["packages"].update(jaxlib="0.0.0"))
    entry = {
        "field": "packages.jaxlib",
        "class": "compiler",
        "from": before,
        "to": "0.0.0",
        "test": "tolerance, backend-variant method, three repeats",
        "variant": "/protocols/variant.json",
        "evidence": "/evidence/terms.json",
    }
    record = build_record(scalar, runtime_admission={"case": "fields", "fields": [entry]})
    refused(
        lambda: io.load_snapshot(scalar, continuity=request(tmp_path, record)),
        "Runtime changes are parked: the first landing refuses every runtime change "
        "(['packages.jaxlib'])",
    )


def test_jax_disable_jit_in_the_resuming_runtime_is_refused(scalar, monkeypatch, tmp_path):
    change_source(monkeypatch)
    rewrite(scalar, lambda m: m["runtime"]["numerical_environment"].update(JAX_DISABLE_JIT="1"))
    change_runtime(monkeypatch, lambda r: r["numerical_environment"].update(JAX_DISABLE_JIT="1"))
    record = build_record(scalar)
    refused(
        lambda: io.load_snapshot(scalar, continuity=request(tmp_path, record)),
        "JAX_DISABLE_JIT is set: execution without JIT is refused",
    )


def test_the_probe_ran_under_the_resuming_host_fields(scalar, monkeypatch, tmp_path):
    change_source(monkeypatch)
    probe = io.runtime_identity("cpu")
    probe = {**probe, "packages": {**probe["packages"], "scipy": "0.0.0"}}
    record = build_record(scalar, **{"probe.runtime": probe})
    refused(
        lambda: io.load_snapshot(scalar, continuity=request(tmp_path, record)),
        "The probe's host-side runtime differs from the resuming runtime (['packages.scipy']); "
        "rerun the probe under the resuming runtime",
    )
    # A compiler field of the probe is not a host field (section 3.1).
    probe = io.runtime_identity("cpu")
    probe = {**probe, "packages": {**probe["packages"], "jaxlib": "0.0.0"}}
    record = build_record(scalar, **{"probe.runtime": probe})
    assert io.load_snapshot(scalar, continuity=request(tmp_path, record)).admission


def test_jit_false_definitions_are_refused(spec, monkeypatch, tmp_path):
    raw = spec.to_dict()
    raw["execution"]["jit"] = False
    eager = parse_spec(raw)
    path = io.write_snapshot(tmp_path / "eager", eager, initialise(eager))
    change_source(monkeypatch)
    record = build_record(path)
    refused(
        lambda: io.load_snapshot(path, continuity=request(tmp_path, record)),
        "Definition scalar: jit: false definitions are refused; they execute eagerly, with no "
        "compiled program to compare",
    )


def test_gpu_and_projective_definitions_are_refused():
    from types import SimpleNamespace

    def spec(backend="cpu", jit=True, projective=None):
        return SimpleNamespace(
            execution=SimpleNamespace(backend=backend, jit=jit), projective=projective
        )

    continuity._require_definition("1", spec())
    with pytest.raises(ConfigError, match="^Definition 1: GPU definitions are not yet admitted"):
        continuity._require_definition("1", spec(backend="gpu"))
    with pytest.raises(ConfigError, match="^Definition 2: projective definitions are refused"):
        continuity._require_definition("2", spec(projective=object()))


def test_a_cohort_record_checks_every_world(cohort, monkeypatch, tmp_path):
    change_source(monkeypatch)
    record = build_record(cohort)
    definitions = dict(record["checkpoint"]["definitions"])
    definitions.pop("11")
    partial = build_record(cohort, **{"checkpoint.definitions": definitions})
    with pytest.raises(ConfigError, match="clocks must name the same checkpoints"):
        batch_io.load_batch_snapshot(cohort, continuity=request(tmp_path, partial))
    clocks = {k: dict(v) for k, v in record["checkpoint"]["clocks"].items()}
    clocks["11"]["event_index"] = 7
    moved = build_record(cohort, **{"checkpoint.clocks": clocks})
    refused(
        lambda: batch_io.load_batch_snapshot(cohort, continuity=request(tmp_path, moved)),
        "Continuity record's clock of 11 is not the checkpoint's",
    )
    calls = []
    real = continuity._require_definition
    monkeypatch.setattr(
        continuity, "_require_definition", lambda key, s: calls.append(key) or real(key, s)
    )
    batch_io.load_batch_snapshot(cohort, continuity=request(tmp_path, record))
    assert sorted(set(calls)) == ["10", "11"]


def test_cohort_children_are_bound_to_the_cohorts_identity(cohort, monkeypatch, tmp_path):
    rewrite_child(cohort, 11, lambda m: m["source_hashes"].update({CHANGED: "1" * 64}))
    change_source(monkeypatch)
    record = build_record(cohort)
    refused(
        lambda: batch_io.load_batch_snapshot(cohort, continuity=request(tmp_path, record)),
        "Batch checkpoint child source differs from its admitted cohort",
    )


def test_cohort_children_share_the_cohorts_runtime(cohort, monkeypatch, tmp_path):
    rewrite_child(cohort, 10, lambda m: m["runtime"].update(python="0.0.0"))
    change_source(monkeypatch)
    record = build_record(cohort)
    refused(
        lambda: batch_io.load_batch_snapshot(cohort, continuity=request(tmp_path, record)),
        "Batch checkpoint child runtime differs from its admitted cohort",
    )


def test_a_cohort_record_keeps_the_child_checks(cohort, monkeypatch, tmp_path):
    with (cohort / "world-10" / "state.npz").open("ab") as handle:
        handle.write(b"corrupted")
    change_source(monkeypatch)
    record = build_record(cohort)
    refused(
        lambda: batch_io.load_batch_snapshot(cohort, continuity=request(tmp_path, record)),
        "Checkpoint state checksum mismatch",
    )


def test_children_come_only_from_an_admitted_cohort_binding(cohort, monkeypatch, tmp_path):
    change_source(monkeypatch)
    record = build_record(cohort)
    binding = continuity.bind(
        request(tmp_path, record),
        kind=continuity.FORMATS[1],
        fingerprint=record["checkpoint"]["manifest_sha256"],
        sources=manifest_of(cohort)["source_hashes"],
        current_sources=io.source_hashes(),
    )
    with pytest.raises(ConfigError, match="Only an admitted cohort binding has children"):
        binding.child(10)


def test_a_scalar_record_does_not_load_a_cohort_child(cohort, monkeypatch, tmp_path):
    change_source(monkeypatch)
    child = cohort / "world-10"
    record = build_record(child)
    saved = io.load_snapshot(child, continuity=request(tmp_path, record))
    assert saved.admission.checkpoint_manifest_sha256 == manifest_of(child)["manifest_sha256"]
    other = build_record(cohort)
    refused(
        lambda: io.load_snapshot(child, continuity=request(tmp_path, other)),
        "Continuity record binds a cells_independent_world_checkpoint, not a "
        "cells_complete_numerical_checkpoint",
    )


# ---------------------------------------------------------------- the module is host-only


def test_the_continuity_module_imports_neither_jax_nor_subprocess():
    code = (
        "import sys; import cells.continuity; "
        "print(sorted(m for m in ('jax', 'jaxlib', 'numpy', 'subprocess') if m in sys.modules))"
    )
    found = subprocess.run(
        [sys.executable, "-B", "-c", code],
        env={"PYTHONPATH": str(ROOT / "src"), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert found == "[]"
    tree = ast.parse((ROOT / "src/cells/continuity.py").read_text())
    imported = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert imported <= {
        "__future__",
        "math",
        "re",
        "dataclasses",
        "pathlib",
        "typing",
        "cells.core.specs",
    }


def test_a_sealed_record_round_trips_through_json(scalar, monkeypatch, tmp_path):
    change_source(monkeypatch)
    record = build_record(scalar)
    path = write_record(tmp_path, record)
    assert continuity.parse_record(read_json(path)) == record
    assert continuity.seal(record) == record
