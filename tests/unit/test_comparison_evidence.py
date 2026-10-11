"""D040 short exactness/dependency/failure checks, not long candidate qualification."""

import copy
import io
import json
import shutil
import subprocess
import zipfile
from contextlib import closing
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace

import numpy as np
import pytest

from scripts import audit_comparison_evidence as audit
from scripts import profile_comparison_evidence as profile
from tests import reference_comparison_evidence as codec
from tests import reference_graph_diagnostics as diagnostics
from tests import reference_graph_evidence as evidence
from tests import reference_recorded_candidate as runner
from tests import source_graph_fixtures as fixtures
from tests.unit.test_graph_candidate import short_references as short_references
from tests.unit.test_graph_evidence import assert_bits, collect, tiny_window

ref, prep = profile.ref, profile.prep


@pytest.fixture
def protocol():
    return profile.campaign.frozen.load_protocol()


def arguments(root, protocol, width=2):
    return {
        "step": 0.01,
        "end": 0.037,
        "numerics": protocol["numerics"],
        "resources": protocol["resources"] | {"window_steps": width},
        "identity": {"fixture": "D040-short"},
        "artifact_root": root,
        "policy": "rk4_basis",
    }


def expected(model, args):
    return runner.contract(
        model, runner.Grid(args["step"], args["end"]), args["numerics"], args["identity"]
    )


def execute(
    root, protocol, references, policy="trajectory_backed", width=2, name="run", initial=None
):
    directories, selected = references
    model = prep.graph.Model(selected["case"])
    args, output = arguments(root, protocol, width), root / name
    consumer = codec.Comparison(
        directories,
        selected,
        output,
        root,
        args["resources"],
        [0, 0.013, 0.031, 0.037],
        policy="batched_cached",
        storage_policy=policy,
    )
    result = codec.integrate(model, output, comparison=consumer, initial=initial, **args)
    return output, result, consumer, args


def decoded(directory):
    with closing(codec.chunks(directory)) as stream:
        return [data for _, data in stream]


def logical_fixture():
    return {
        "times": np.array([0.0, 0.01]),
        "observer": np.array([True, False]),
        **{k: np.zeros((2, 13)) for k in ("candidate", "radau", "bdf", "refined")},
    }


@pytest.mark.parametrize(
    "change", ["nan", "dtype", "shape", "missing", "extra", "flags", "clock_order", "clock_scalar"]
)
def test_malformed_logical_arrays_are_refused_before_encoding(change):
    arrays = logical_fixture()
    if change == "nan":
        arrays["bdf"][0, 0] = np.nan
    elif change == "dtype":
        arrays["candidate"] = arrays["candidate"].astype(np.float32)
    elif change == "shape":
        arrays["refined"] = arrays["refined"][:, :-1]
    elif change == "missing":
        arrays.pop("radau")
    elif change == "extra":
        arrays["extra"] = np.zeros(2)
    elif change == "flags":
        arrays["observer"] = arrays["observer"].astype(np.int64)
    elif change == "clock_order":
        arrays["times"][:] = 0
    else:
        arrays["times"] = np.array(0.0)
    with pytest.raises(ValueError):
        codec.encode_samples(
            "full_samples",
            arrays,
            size=13,
            variants=["radau", "bdf", "refined"],
            reconstruct=None,
            budget=268435456,
        )


@pytest.mark.parametrize("budget", [1, 0, -1, True, 1.0])
def test_decode_budget_refuses_before_reconstruction(budget):
    arrays = {k: v for k, v in logical_fixture().items() if k in ("times", "observer")}

    def forbidden(times):
        raise AssertionError("reconstruction called before budget refusal")

    with pytest.raises(ref.BudgetExceeded):
        codec.decode_samples(
            "trajectory_backed",
            arrays,
            size=13,
            variants=["radau", "bdf", "refined"],
            reconstruct=forbidden,
            budget=budget,
        )


@pytest.mark.parametrize("samples", [0, -1, 257, True, 2.0])
def test_layout_sample_capacity_is_explicit(samples):
    with pytest.raises(ValueError):
        codec.layout("trajectory_backed", samples, 13, ["radau", "bdf", "refined"])


def test_comparison_archive_header_refused_before_payload_allocation(tmp_path, monkeypatch):
    path = tmp_path / "forged.npz"
    arrays = {k: v for k, v in logical_fixture().items() if k in ("times", "observer")}
    evidence.save_arrays(path, arrays, tmp_path, 10_000_000)
    with zipfile.ZipFile(path) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    header = io.BytesIO()
    np.lib.format.write_array_header_1_0(
        header, {"descr": "<f8", "fortran_order": False, "shape": (2**40,)}
    )
    members["times.npy"] = header.getvalue()
    with zipfile.ZipFile(path, "w") as archive:
        for name, value in members.items():
            archive.writestr(name, value)

    def forbidden(*args, **kwargs):
        raise AssertionError("allocation occurred before advertised-header check")

    monkeypatch.setattr(evidence.np, "frombuffer", forbidden)
    with pytest.raises(ValueError, match="NPY header differs"):
        evidence.read_arrays(
            path,
            codec.layout("trajectory_backed", 2, 13, ["radau", "bdf", "refined"]),
            budget=268435456,
        )


@pytest.mark.parametrize("field", ["case", "methods", "numerics", "duration"])
def test_expected_reference_selection_is_not_inferred_from_manifest(
    tmp_path, protocol, short_references, field
):
    directory, _, _, _ = execute(tmp_path, protocol, short_references)
    selected = copy.deepcopy(short_references[1])
    selected[field] = "different"
    with pytest.raises(ValueError, match="selection differs"):
        codec.check_dependencies(directory, selected=selected)


@pytest.mark.parametrize(
    "field",
    ["encoded_array_bytes", "logical_array_bytes", "aggregate_array_estimate_bytes", "samples"],
)
def test_storage_summary_tampering_refused(tmp_path, protocol, short_references, field):
    directory, _, _, _ = execute(tmp_path, protocol, short_references)
    path = directory / "comparison/storage.json"
    storage = ref.read_json(path)
    storage[field] += 1
    path.write_text(json.dumps(storage))
    with pytest.raises(ValueError, match="storage closure differs"):
        decoded(directory)


def test_exclusive_output_and_refused_oversized_manifest(tmp_path, protocol, short_references):
    directory, _, _, _ = execute(tmp_path, protocol, short_references)
    with pytest.raises(FileExistsError):
        execute(tmp_path, protocol, short_references)
    path = directory / "comparison/dependencies.json"
    path.write_bytes(b" " * (codec.MAX_MANIFEST_BYTES + 1))
    with pytest.raises(ValueError, match="manifest exceeds bound"):
        decoded(directory)


@pytest.mark.parametrize("field", ["resources", "folder", "root", "numerics"])
def test_adapter_mismatch_refused_before_output_creation(
    tmp_path, protocol, short_references, field
):
    directories, selected = short_references
    selected = copy.deepcopy(selected)
    model = prep.graph.Model(selected["case"])
    args, output = arguments(tmp_path, protocol), tmp_path / "run"
    consumer = codec.Comparison(
        directories,
        selected,
        output,
        tmp_path,
        copy.deepcopy(args["resources"]),
        [],
        policy="batched_cached",
        storage_policy="trajectory_backed",
    )
    if field == "resources":
        consumer.resources["window_steps"] += 1
    elif field == "folder":
        consumer.folder = tmp_path / "other/comparison"
    elif field == "root":
        consumer.root = tmp_path / "other"
    else:
        consumer.selected["numerics"]["accounting_atol"] *= 2
    with pytest.raises(ValueError, match="adapter case/numerics/resources/output"):
        codec.integrate(model, output, comparison=consumer, **args)
    assert not output.exists()


@pytest.mark.parametrize("case", fixtures.cases(), ids=lambda c: c["id"])
@pytest.mark.parametrize("policy", codec.POLICIES)
def test_all_graph_shapes_exact_sample_codec(case, policy, tmp_path):
    model, window = tiny_window(case)
    times = np.array([0, 0.5e-8, 1e-8, 2.7e-8, 3e-8])
    states = {"candidate": diagnostics.original.candidate.sample_window(window, times)}
    states.update(
        {k: states["candidate"] + i * 1e-12 for i, k in enumerate(["radau", "bdf", "refined"])}
    )
    arrays = {"times": times, "observer": np.array([True, False, True, False, True]), **states}
    readers = {
        k: SimpleNamespace(sample=lambda t, k=k: states[k]) for k in ("radau", "bdf", "refined")
    }
    assert_bits(audit.independent_reconstruct(window, times, readers), states)
    kwargs = dict(
        size=model.coordinates.size,
        variants=["radau", "bdf", "refined"],
        reconstruct=lambda t: {k: v.copy() for k, v in states.items()},
        budget=268435456,
    )
    encoded, logical = codec.encode_samples(policy, arrays, **kwargs)
    path = tmp_path / "samples.npz"
    evidence.save_arrays(path, encoded, tmp_path, 10_000_000)
    loaded = evidence.read_arrays(
        path,
        codec.layout(policy, len(times), model.coordinates.size, kwargs["variants"]),
        budget=kwargs["budget"],
    )
    assert_bits(codec.decode_samples(policy, loaded, **kwargs), arrays)
    assert_bits(audit.independent_decode_samples(policy, loaded, **kwargs), arrays)
    assert logical == evidence.array_digest(arrays)
    assert set(encoded) == ({"times", "observer"} if policy == "trajectory_backed" else set(arrays))


@pytest.mark.parametrize("policy", codec.POLICIES)
@pytest.mark.parametrize("width", [1, 2, 3, 16, 256])
def test_short_full_evidence_matches_D039_and_independent_audit(
    tmp_path, protocol, short_references, policy, width
):
    directory, report, consumer, args = execute(tmp_path, protocol, short_references, policy, width)
    directories, selected = short_references
    model = prep.graph.Model(selected["case"])
    original = tmp_path / "D039"
    old_consumer = diagnostics.Comparison(
        directories,
        selected,
        original,
        tmp_path,
        args["resources"],
        [0, 0.013, 0.031, 0.037],
        policy="batched_cached",
    )
    runner.integrate(model, original, comparison=old_consumer, **args)
    assert_bits(collect(directory), collect(original))
    with closing(diagnostics.original.chunks(original, comparison=True)) as stream:
        old = [data for _, data in stream]
    new = decoded(directory)
    assert len(new) == len(old)
    for a, b in zip(new, old, strict=True):
        assert_bits(a, b)
    checked = audit.audit_samples(
        directory,
        directories,
        selected,
        [0, 0.013, 0.031, 0.037],
        args["resources"],
        perf_counter() + 60,
    )
    assert checked["samples"] == report["comparison"]["samples"]
    assert checked["observer_samples"] == 4
    assert all(r._iterator.gi_frame is None for r in consumer.readers.values())
    if consumer.decoding_readers:
        assert all(r._iterator.gi_frame is None for r in consumer.decoding_readers.values())
    audit.audit_trajectory(
        directory, expected(model, args), args["resources"], model.panel, perf_counter() + 60
    )
    tol = ref.read_json(profile.ROOT / "configs/reference/source_emt_graph_probes_v1.json")[
        "instantaneous_tolerances"
    ]
    checked_readouts = audit.audit_readouts(
        directory, selected, "batched_cached", tol, args["resources"], perf_counter() + 60
    )
    assert checked_readouts["maximum_scalar_difference_score"] == 0


@pytest.mark.parametrize("source", codec.POLICIES)
@pytest.mark.parametrize("destination", codec.POLICIES)
@pytest.mark.parametrize("chunk", [0, 1, 2])
def test_complete_dependency_checked_restart_policy_and_width_change(
    tmp_path, protocol, short_references, source, destination, chunk
):
    directory, _, _, args = execute(tmp_path, protocol, short_references, source, 1)
    model = prep.graph.Model(short_references[1]["case"])
    carry = codec.load_checkpoint(directory, chunk, expected(model, args))
    continued, _, _, _ = execute(
        tmp_path, protocol, short_references, destination, 3, "restart", carry
    )
    original, resumed = collect(directory), collect(continued)
    start = carry["tick"]
    for key in ["times", "increments"]:
        np.testing.assert_array_equal(resumed[key], original[key][start:])
    for key in ["coefficients", "slopes"]:
        np.testing.assert_array_equal(resumed[key], original[key][start:])


@pytest.mark.parametrize("policy", codec.POLICIES)
def test_independent_decoder_never_calls_writer_decoders_or_sampler(
    tmp_path, protocol, short_references, monkeypatch, policy
):
    directory, _, _, _ = execute(tmp_path, protocol, short_references, policy)
    wanted = decoded(directory)

    def forbidden(*args, **kwargs):
        raise AssertionError("writer path was called")

    monkeypatch.setattr(codec, "decode_samples", forbidden)
    monkeypatch.setattr(codec, "reconstruct_states", forbidden)
    monkeypatch.setattr(evidence, "decode_window", forbidden)
    monkeypatch.setattr(diagnostics.original.candidate, "sample_window", forbidden)
    with closing(audit.logical_stream(directory)) as stream:
        actual = [data for _, data in stream]
    for a, b in zip(actual, wanted, strict=True):
        assert_bits(a, b)


@pytest.mark.parametrize(
    "target", ["case.json", "trajectory.json", "chunks.jsonl", "chunk-000000.npz"]
)
@pytest.mark.parametrize("operation", ["change", "remove", "symlink", "hardlink"])
def test_changed_missing_or_linked_reference_dependency_refuses_restart(
    tmp_path, protocol, short_references, target, operation
):
    directories, selected = short_references
    copies = {key: tmp_path / "refs" / key for key in directories}
    for key, source in directories.items():
        shutil.copytree(source, copies[key])
    directory, _, _, args = execute(tmp_path, protocol, (copies, selected))
    chosen = next(iter(copies.values())) / target
    if operation == "change":
        chosen.write_bytes(chosen.read_bytes() + b" ")
    else:
        backup = chosen.with_name("retained-original")
        chosen.rename(backup)
        if operation == "symlink":
            chosen.symlink_to(backup)
        elif operation == "hardlink":
            chosen.hardlink_to(backup)
    model = prep.graph.Model(selected["case"])
    with pytest.raises((ValueError, OSError)):
        codec.load_checkpoint(directory, 0, expected(model, args))


@pytest.mark.parametrize(
    "field",
    [
        "policy",
        "runtime",
        "source_hashes",
        "candidate_attempt_sha256",
        "candidate_contract_sha256",
        "RHS_replay",
    ],
)
def test_dependency_manifest_tampering_refused(tmp_path, protocol, short_references, field):
    directory, _, _, _ = execute(tmp_path, protocol, short_references)
    path = directory / "comparison/dependencies.json"
    manifest = ref.read_json(path)
    manifest[field] = "changed"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        decoded(directory)


@pytest.mark.parametrize("policy", ["unknown", None, 1, True])
def test_explicit_policy_required(policy):
    with pytest.raises(ValueError):
        codec.validate_policy(policy)


def test_aggregate_array_preflight_before_comparison_readers(
    tmp_path, protocol, short_references, monkeypatch
):
    args = arguments(tmp_path, protocol)
    args["resources"]["estimated_array_budget_bytes"] = 1
    dirs, selected = short_references
    consumer = codec.Comparison(
        dirs,
        selected,
        tmp_path / "run",
        tmp_path,
        args["resources"],
        [],
        policy="batched_cached",
        storage_policy="trajectory_backed",
    )
    with pytest.raises(ref.BudgetExceeded, match="Aggregate comparison"):
        consumer.open(0, runner.Grid(0.01, 0.037), lambda: None)
    assert not (tmp_path / "run").exists()


def test_real_profile_plan_source_inventory_and_unchanged_shared_quota():
    r = profile.specification(profile.OUTPUT_PARENT / "comparison-01")
    r["source_hashes"] = {name: ref.sha(profile.ROOT / name) for name in profile.SOURCES}
    assert len(profile.SOURCES) == len(set(profile.SOURCES)) == 68
    assert all((profile.ROOT / name).is_file() for name in profile.SOURCES)
    assert len(r["planned_attempts"]) == 12
    assert r["storage_budget"]["prior_bytes"] == 821019434
    assert r["storage_budget"]["new_root_limit_bytes"] == 252722390
    assert r["plan"]["trajectory_policy"] == "rk4_basis"
    for case in r["plan"]["cases"]:
        assert profile.identity(r, case) == profile.parent.identity(r, case)


def rebind_comparison_index(directory):
    """Rehash outer fixture receipts so semantic checks must reject the forgery."""
    path = directory / "chunks.jsonl"
    commits = [json.loads(line) for line in path.read_text().splitlines()]
    head = ref.sha(directory / "attempt.json")
    for record in commits:
        record["comparison"] = evidence.comparison_prefix(directory, record["comparison"]["chunks"])
        record["previous_sha256"] = head
        record.pop("commit_sha256")
        head = record["commit_sha256"] = runner.digest(record)
    path.write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in commits))
    closure = ref.read_json(directory / "trajectory.json")
    closure["index_sha256"] = ref.sha(path)
    closure["evidence"]["head_sha256"] = head
    index_hash = ref.sha(directory / "comparison/chunks.jsonl")
    closure["comparison"]["index_sha256"] = index_hash
    (directory / "trajectory.json").write_text(json.dumps(closure))
    summary = ref.read_json(directory / "comparison/comparison.json")
    summary["index_sha256"] = index_hash
    (directory / "comparison/comparison.json").write_text(json.dumps(summary))
    storage = ref.read_json(directory / "comparison/storage.json")
    storage["index_sha256"] = index_hash
    (directory / "comparison/storage.json").write_text(json.dumps(storage))


@pytest.mark.parametrize(
    "field",
    [
        "dependency_sha256",
        "logical_sha256",
        "input_hashes",
        "candidate_window",
        "encoded_array_bytes",
        "logical_array_bytes",
        "policy",
        "revision",
    ],
)
def test_rehashed_comparison_record_forgery_refused(tmp_path, protocol, short_references, field):
    directory, _, _, _ = execute(tmp_path, protocol, short_references)
    path = directory / "comparison/chunks.jsonl"
    entries = [json.loads(line) for line in path.read_text().splitlines()]
    entries[0][field] = "forged"
    path.write_text("".join(json.dumps(entry, sort_keys=True) + "\n" for entry in entries))
    rebind_comparison_index(directory)
    with pytest.raises(ValueError):
        decoded(directory)


@pytest.mark.parametrize("field", ["times", "observer"])
def test_rehashed_payload_cannot_change_logical_samples(
    tmp_path, protocol, short_references, field
):
    directory, _, _, _ = execute(tmp_path, protocol, short_references)
    path = directory / "comparison/chunk-000000.npz"
    with np.load(path, allow_pickle=False) as archive:
        arrays = {k: archive[k].copy() for k in archive.files}
    arrays[field][0] = (
        np.nextafter(arrays[field][0], np.inf) if field == "times" else not arrays[field][0]
    )
    with path.open("wb") as handle:
        np.savez_compressed(handle, **arrays)
    index = directory / "comparison/chunks.jsonl"
    entries = [json.loads(line) for line in index.read_text().splitlines()]
    entries[0]["sha256"] = ref.sha(path)
    index.write_text("".join(json.dumps(entry, sort_keys=True) + "\n" for entry in entries))
    rebind_comparison_index(directory)
    with pytest.raises(ValueError):
        decoded(directory)


@pytest.mark.parametrize(
    "operation", ["missing_payload", "partial_index", "reordered_index", "extra_index", "unclosed"]
)
def test_missing_partial_reordered_extra_and_unclosed_evidence_refused(
    tmp_path, protocol, short_references, operation
):
    directory, _, _, args = execute(tmp_path, protocol, short_references)
    if operation == "missing_payload":
        (directory / "comparison/chunk-000000.npz").rename(directory / "retained-payload.npz")
    elif operation == "unclosed":
        (directory / "trajectory.json").rename(directory / "retained-closure.json")
    else:
        path = directory / "comparison/chunks.jsonl"
        lines = path.read_text().splitlines(keepends=True)
        if operation == "partial_index":
            lines[-1] = lines[-1][:-3]
        elif operation == "reordered_index":
            lines[0], lines[1] = lines[1], lines[0]
        else:
            lines.append(lines[-1])
        path.write_text("".join(lines))
    with pytest.raises((ValueError, OSError)):
        codec.load_checkpoint(
            directory, 0, expected(prep.graph.Model(short_references[1]["case"]), args)
        )


@pytest.mark.parametrize("target", ["payload", "index", "codec"])
def test_interrupted_comparison_keeps_only_prior_committed_restart(
    tmp_path, protocol, short_references, monkeypatch, target
):
    saved_arrays, saved_commit = evidence.save_arrays, evidence.append_commit
    attempts = []

    def fail_payload(path, arrays, *args, **kwargs):
        if (
            Path(path).parent.name == "comparison"
            and "times" in arrays
            and arrays["times"][0] > 0.02
            and target == "payload"
        ):
            attempts.append(str(path))
            Path(path).write_bytes(b"partial comparison payload")
            raise OSError("injected comparison publication failure")
        return saved_arrays(path, arrays, *args, **kwargs)

    def fail_index(path, entry, *args, **kwargs):
        if Path(path).parent.name == "comparison" and entry["start"] > 0.02 and target == "index":
            attempts.append(str(path))
            with Path(path).open("ab") as handle:
                handle.write(b'{"partial":')
            raise OSError("injected comparison publication failure")
        return saved_commit(path, entry, *args, **kwargs)

    original_reconstruct = codec.Comparison.reconstruct

    def bad_reconstruct(self, times):
        result = original_reconstruct(self, times)
        if times[0] > 0.02 and target == "codec":
            attempts.append("codec")
            result["candidate"][0, 0] += 1
        return result

    monkeypatch.setattr(evidence, "save_arrays", fail_payload)
    monkeypatch.setattr(evidence, "append_commit", fail_index)
    monkeypatch.setattr(codec.Comparison, "reconstruct", bad_reconstruct)
    with pytest.raises((ValueError, OSError)):
        execute(tmp_path, protocol, short_references)
    directory = tmp_path / "run"
    failed = ref.read_json(directory / "failure.json")
    assert len(attempts) == 1 and failed["committed_chunks"] == 1
    assert failed["evidence"]["committed_tick"] == 2 and failed["accepted_tick"] == 4
    assert all(
        v["status"] == "retained_diagnostic_not_restart" for v in failed["preservation"].values()
    )
    contract = expected(
        prep.graph.Model(short_references[1]["case"]), arguments(tmp_path, protocol)
    )
    carry = codec.load_checkpoint(directory, 0, contract)
    assert carry["tick"] == 2
    with pytest.raises(ValueError):
        codec.load_checkpoint(directory, 1, contract)


def test_same_score_limit_stops_before_any_commit(
    tmp_path, protocol, short_references, monkeypatch
):
    monkeypatch.setattr(prep, "comparison_scores", lambda *a: {"ionic_state": 2.0})
    with pytest.raises(ValueError, match="limits failed before window commit"):
        execute(tmp_path, protocol, short_references)
    failed = ref.read_json(tmp_path / "run/failure.json")
    assert failed["committed_chunks"] == 0 and failed["accepted_tick"] == 2


@pytest.fixture
def registration_fixture(tmp_path, monkeypatch, protocol):
    source = tmp_path / "fixture.txt"
    source.write_text("short comparison source fixture\n")
    spec = {
        "resources": protocol["resources"],
        "runtime": prep.runtime(),
        "planned_attempts": ["first/full_samples", "first/trajectory_backed"],
    }
    monkeypatch.setattr(profile, "ROOT", tmp_path)
    monkeypatch.setattr(profile, "SOURCES", ["fixture.txt"])
    monkeypatch.setattr(profile, "specification", lambda output: copy.deepcopy(spec))
    for key, value in profile.campaign.THREADS.items():
        monkeypatch.setenv(key, value)
    return tmp_path / "new", source


def test_registration_source_identity_and_exclusivity(registration_fixture):
    output, source = registration_fixture
    registered = profile.register(output)
    assert profile.check_registration(output) == registered
    with pytest.raises(FileExistsError):
        profile.register(output)
    source.write_text("changed comparison source fixture\n")
    with pytest.raises(ValueError, match="source identity"):
        profile.check_registration(output)


@pytest.mark.parametrize("timeout", [False, True])
def test_profile_stop_is_closed_and_never_retried(registration_fixture, monkeypatch, timeout):
    output, _ = registration_fixture
    calls = []

    def stop(command, **kwargs):
        calls.append(command)
        if timeout:
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(profile.subprocess, "run", stop)
    with pytest.raises((ValueError, subprocess.TimeoutExpired)):
        profile.run(output)
    failed = ref.read_json(output / "failure.json")
    assert len(calls) == 1 and failed["no_automatic_retry"]
    assert failed["not_started"] == ["first/trajectory_backed"]
    with pytest.raises(ValueError, match="Closed comparison session"):
        profile.worker(output, "first/trajectory_backed")
