"""Short D039 recording/recovery tests; never a long candidate study."""

import copy
import inspect
import io
import json
import subprocess
import zipfile
from contextlib import closing
from pathlib import Path
from time import perf_counter

import numpy as np
import pytest

from scripts import audit_graph_evidence as audit
from scripts import profile_graph_evidence as profile
from tests import reference_graph_candidate as frozen
from tests import reference_graph_diagnostics as diagnostics
from tests import reference_graph_evidence as evidence
from tests import reference_recorded_candidate as runner
from tests import source_graph_fixtures as fixtures
from tests.unit.test_graph_candidate import short_references as short_references

ref, prep = frozen.ref, profile.prep


@pytest.fixture
def protocol():
    return profile.campaign.frozen.load_protocol()


@pytest.fixture
def model():
    return prep.graph.Model(prep.preparations()["E"])


def arguments(root, protocol, width=2, end=0.037, policy="rk4_basis"):
    return {
        "step": 0.01,
        "end": end,
        "numerics": protocol["numerics"],
        "resources": protocol["resources"] | {"window_steps": width},
        "identity": {"fixture": "D039-short"},
        "artifact_root": root,
        "policy": policy,
    }


def expected(model, args):
    return frozen.contract(
        model, frozen.Grid(args["step"], args["end"]), args["numerics"], args["identity"]
    )


def collect(directory, *, old=False):
    with closing(
        diagnostics.original.chunks(directory) if old else evidence.chunks(directory)
    ) as stream:
        windows = [data for _, data in stream]
    return {
        "times": np.r_[windows[0]["times"][0], *[w["times"][1:] for w in windows]],
        "increments": np.vstack(
            [windows[0]["increments"][0], *[w["increments"][1:] for w in windows]]
        ),
        "slopes": np.concatenate([w["slopes"] for w in windows]),
        "coefficients": np.concatenate([w["coefficients"] for w in windows]),
    }


def assert_bits(left, right):
    assert set(left) == set(right)
    for name in left:
        assert left[name].shape == right[name].shape and left[name].dtype == right[name].dtype
        assert left[name].tobytes() == right[name].tobytes(), name


def tiny_window(case):
    model = prep.graph.Model(case)
    width, size = 3, model.coordinates.size
    times, values = np.arange(width + 1, dtype=np.float64) * 1e-8, np.zeros((width + 1, size))
    slopes, coefficients = np.empty((width, 5, size)), np.empty((width, 4, size))
    for i in range(width):
        values[i + 1], slopes[i], coefficients[i] = frozen.rk4_step(
            lambda t, y: model.derivative(y, increments=True), times[i], times[i + 1], values[i]
        )
    return model, {
        "times": times,
        "ticks": np.arange(width + 1, dtype=np.int64),
        "increments": values,
        "slopes": slopes,
        "coefficients": coefficients,
        "anchor": model.anchor,
        "context": model.context,
    }


@pytest.mark.parametrize("case", fixtures.cases(), ids=lambda c: c["id"])
@pytest.mark.parametrize("policy", evidence.POLICIES)
def test_all_graph_fixtures_lossless_codec_and_independent_decode(tmp_path, case, policy):
    model, data = tiny_window(case)
    args = dict(width=3, size=model.coordinates.size, cells=model.n, budget=268435456)
    before = evidence.array_digest(data)
    encoded, digest = evidence.encode_window(policy, data, **args)
    path = tmp_path / "window.npz"
    evidence.save_arrays(path, encoded, tmp_path, 10_000_000)
    loaded = evidence.read_arrays(
        path, evidence.layout(policy, 3, model.coordinates.size, model.n), budget=args["budget"]
    )
    assert_bits(evidence.decode_window(policy, loaded, **args), data)
    assert_bits(audit.independent_decode(policy, loaded, **args), data)
    assert digest == before == evidence.array_digest(data)
    if policy == "rk4_basis":
        assert sum(a.nbytes for a in encoded.values()) < sum(a.nbytes for a in data.values())


@pytest.mark.parametrize("policy", evidence.POLICIES)
@pytest.mark.parametrize("width", [1, 2, 3, 16, 256])
def test_short_final_step_full_numerical_identity_and_independent_audit(
    tmp_path, model, protocol, policy, width
):
    args = arguments(tmp_path, protocol, width, policy=policy)
    frozen.integrate(model, tmp_path / "old", **{k: v for k, v in args.items() if k != "policy"})
    result = runner.integrate(model, tmp_path / "new", **args)
    assert_bits(collect(tmp_path / "new"), collect(tmp_path / "old", old=True))
    assert result["evidence"]["policy"] == policy and result["end"] == 0.037
    checked = audit.audit_trajectory(
        tmp_path / "new", expected(model, args), args["resources"], model.panel, perf_counter() + 60
    )
    assert checked["steps"] == 4


@pytest.mark.parametrize(
    "source_policy,target_policy", [(a, b) for a in evidence.POLICIES for b in evidence.POLICIES]
)
@pytest.mark.parametrize("boundary", [0, 1, 2])
def test_complete_restart_at_each_boundary_across_policy_and_width(
    tmp_path, model, protocol, source_policy, target_policy, boundary
):
    args = arguments(tmp_path, protocol, width=2, end=0.077, policy=source_policy)
    runner.integrate(model, tmp_path / "parent", **args)
    initial = evidence.load_checkpoint(tmp_path / "parent", boundary, expected(model, args))
    resumed = args | {
        "policy": target_policy,
        "resources": args["resources"] | {"window_steps": 3},
        "initial": initial,
    }
    runner.integrate(model, tmp_path / "child", **resumed)
    baseline, suffix = collect(tmp_path / "parent"), collect(tmp_path / "child")
    tick = initial["tick"]
    assert_bits(suffix, {k: v[tick:] for k, v in baseline.items()})
    assert len(initial["increments"]) == model.coordinates.size
    audit.audit_trajectory(
        tmp_path / "child",
        expected(model, args),
        resumed["resources"],
        model.panel,
        perf_counter() + 60,
    )


@pytest.mark.parametrize("policy", [None, "sparse", "rk4_basis@2", True])
def test_unknown_policy_refused_without_output(tmp_path, model, protocol, policy):
    with pytest.raises(ValueError, match="policy"):
        runner.integrate(model, tmp_path / "bad", **arguments(tmp_path, protocol, policy=policy))
    assert not (tmp_path / "bad").exists()


@pytest.mark.parametrize(
    "field", ["increments", "coefficients", "slopes", "times", "ticks", "context"]
)
def test_codec_refuses_wrong_dtype_or_shape(model, field):
    _, data = tiny_window(model.case)
    data[field] = data[field].astype(np.float32)
    with pytest.raises(ValueError, match="inventory/shape/precision"):
        evidence.encode_window(
            "rk4_basis", data, width=3, size=model.coordinates.size, cells=model.n, budget=268435456
        )


@pytest.mark.parametrize("field", ["increments", "coefficients"])
def test_nonredundant_data_refused_without_fallback(model, field):
    _, data = tiny_window(model.case)
    if field == "increments":
        data[field][1, 0] += 1
    else:
        data[field].flat[1] += 1
    with pytest.raises(ValueError, match="reconstruction differs"):
        evidence.encode_window(
            "rk4_basis", data, width=3, size=model.coordinates.size, cells=model.n, budget=268435456
        )


def test_preallocation_guard_precedes_decoder_arrays(model, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("allocation before guard")

    monkeypatch.setattr(evidence.np, "empty", forbidden)
    with pytest.raises(ref.BudgetExceeded, match="encode/decode"):
        evidence.decode_window(
            "rk4_basis", {}, width=256, size=model.coordinates.size, cells=model.n, budget=1
        )


def reclose(folder, entries):
    """Forge local hashes deliberately, leaving numerical/structural checks to catch it."""
    head = ref.sha(folder / "attempt.json")
    for entry in entries:
        entry["previous_sha256"] = head
        entry["commit_sha256"] = frozen.digest(
            {k: v for k, v in entry.items() if k != "commit_sha256"}
        )
        head = entry["commit_sha256"]
    (folder / "chunks.jsonl").write_text(
        "".join(json.dumps(e, sort_keys=True) + "\n" for e in entries)
    )
    receipt = ref.read_json(folder / "trajectory.json")
    receipt["index_sha256"] = ref.sha(folder / "chunks.jsonl")
    receipt["evidence"]["head_sha256"] = head
    (folder / "trajectory.json").write_text(json.dumps(receipt))


@pytest.mark.parametrize(
    "kind",
    [
        "bytes",
        "missing",
        "reordered",
        "truncated",
        "extra",
        "logical_digest",
        "bad_header",
        "extra_member",
    ],
)
def test_corrupt_and_rehashed_incomplete_evidence_refused(tmp_path, model, protocol, kind):
    args, folder = arguments(tmp_path, protocol), tmp_path / "run"
    runner.integrate(model, folder, **args)
    entries = [json.loads(line) for line in (folder / "chunks.jsonl").read_text().splitlines()]
    payload = folder / entries[0]["path"]
    if kind == "bytes":
        payload.write_bytes(b"corrupt")
    elif kind == "missing":
        payload.unlink()
    elif kind == "reordered":
        reclose(folder, entries[::-1])
    elif kind == "truncated":
        reclose(folder, entries[:-1])
    elif kind == "extra":
        reclose(folder, entries + [copy.deepcopy(entries[-1])])
    elif kind == "logical_digest":
        entries[0]["logical_sha256"] = "0" * 64
        reclose(folder, entries)
    else:
        with np.load(payload, allow_pickle=False) as saved:
            data = {k: saved[k].copy() for k in saved.files}
        if kind == "bad_header":
            data["slopes"] = data["slopes"].astype(np.float32)
        else:
            data["unexpected"] = np.ones(1)
        with payload.open("wb") as handle:
            np.savez_compressed(handle, **data)
        entries[0]["sha256"] = ref.sha(payload)
        reclose(folder, entries)
    with pytest.raises((ValueError, AssertionError, FileNotFoundError)):
        evidence.load_checkpoint(folder, 0, expected(model, args))


@pytest.mark.parametrize("kind", ["source", "carry", "closure", "policy", "linked_payload"])
def test_checkpoint_source_carry_schema_and_closure_refusals(tmp_path, model, protocol, kind):
    args, folder = arguments(tmp_path, protocol), tmp_path / "parent"
    runner.integrate(model, folder, **args)
    identity = expected(model, args)
    if kind == "source":
        identity["numerical_source_runtime_identity"]["fixture"] = "changed"
    elif kind == "carry":
        initial = evidence.load_checkpoint(folder, 0, identity)
        initial["increments"][0] += 1
        with pytest.raises(ValueError, match="carry was changed"):
            runner.integrate(model, tmp_path / "child", initial=initial, **args)
        return
    elif kind == "closure":
        (folder / "trajectory.json").unlink()
    elif kind == "policy":
        value = ref.read_json(folder / "attempt.json")
        value["recording"]["policy"] = "implicit-migration"
        (folder / "attempt.json").write_text(json.dumps(value))
    else:
        (folder / "alias.npz").hardlink_to(folder / "chunk-000000.npz")
    with pytest.raises((ValueError, AssertionError)):
        evidence.load_checkpoint(folder, 0, identity)


@pytest.mark.parametrize("tail_failure", [None, "last-evaluation.npz", "uncommitted-window.npz"])
def test_failed_payload_is_not_retried_and_preservation_attempts_are_independent(
    tmp_path, model, protocol, monkeypatch, tail_failure
):
    args, folder = arguments(tmp_path, protocol, end=0.057), tmp_path / "failed"
    real, calls = evidence.save_arrays, []

    def broken(path, arrays, *a, **kw):
        calls.append(Path(path).name)
        if Path(path).name == "chunk-000001.npz":
            Path(path).write_bytes(b"partial payload fixture")
            raise OSError("original chunk refusal")
        if Path(path).name == tail_failure:
            raise OSError("secondary preservation refusal")
        return real(path, arrays, *a, **kw)

    with monkeypatch.context() as patch:
        patch.setattr(evidence, "save_arrays", broken)
        with pytest.raises(OSError, match="original chunk refusal"):
            runner.integrate(model, folder, **args)
    failed = ref.read_json(folder / "failure.json")
    assert failed["steps"] == 4 and failed["committed_chunks"] == 1
    assert calls.count("chunk-000001.npz") == 1 and failed["no_automatic_retry"]
    assert failed["evidence"]["committed_tick"] == 2 and failed["accepted_tick"] == 4
    for name in ("last-evaluation.npz", "uncommitted-window.npz"):
        assert failed["preservation"][name]["status"] == (
            "preservation_failed" if name == tail_failure else "retained_diagnostic_not_restart"
        )
    initial = evidence.load_checkpoint(folder, 0, expected(model, args))
    with pytest.raises(ValueError, match="committed accepted boundary"):
        evidence.load_checkpoint(folder, 1, expected(model, args))
    runner.integrate(
        model, tmp_path / "resumed", **(args | {"policy": "full_trace", "initial": initial})
    )
    assert (folder / "chunk-000001.npz").read_bytes() == b"partial payload fixture"


@pytest.mark.parametrize("partial", [True, False])
def test_partial_commit_line_refuses_automatic_checkpoint_recovery(
    tmp_path, model, protocol, monkeypatch, partial
):
    args, folder = arguments(tmp_path, protocol), tmp_path / "failed"
    real, calls = evidence.append_commit, []

    def interrupted(path, entry, *a, **kw):
        calls.append(entry["path"])
        if len(calls) == 2:
            if partial:
                with Path(path).open("ab") as handle:
                    handle.write(b'{"partial":')
            else:
                real(path, entry, *a, **kw)
            raise KeyboardInterrupt("interrupted commit fixture")
        return real(path, entry, *a, **kw)

    monkeypatch.setattr(evidence, "append_commit", interrupted)
    with pytest.raises(KeyboardInterrupt):
        runner.integrate(model, folder, **args)
    failed = ref.read_json(folder / "failure.json")
    assert failed["committed_chunks"] == 1 and failed["status"] == "incomplete"
    with pytest.raises(ValueError, match="index tail"):
        evidence.load_checkpoint(folder, 0, expected(model, args))


@pytest.mark.parametrize(
    "resource,value",
    [
        ("estimated_array_budget_bytes", 1),
        ("artifact_budget_bytes", 4194305),
        ("max_steps_per_trajectory", 1),
    ],
)
def test_array_disk_and_step_limits_refuse_without_promoted_checkpoint(
    tmp_path, model, protocol, resource, value
):
    args, folder = arguments(tmp_path, protocol), tmp_path / "limited"
    args["resources"][resource] = value
    with pytest.raises(ref.BudgetExceeded):
        runner.integrate(model, folder, **args)
    failed = ref.read_json(folder / "failure.json")
    assert failed["committed_chunks"] == 0 and failed["steps"] == 0
    assert not (folder / "trajectory.json").exists()


def test_exclusive_output_keeps_prior_payloads(tmp_path, model, protocol):
    args, folder = arguments(tmp_path, protocol), tmp_path / "only"
    runner.integrate(model, folder, **args)
    hashes = profile.previous.payload_hashes(folder)
    with pytest.raises(FileExistsError):
        runner.integrate(model, folder, **args)
    assert hashes == profile.previous.payload_hashes(folder)


@pytest.mark.parametrize("policy", evidence.POLICIES)
def test_full_reference_comparison_and_independent_audit_never_use_writer_decoder(
    tmp_path, model, protocol, short_references, monkeypatch, policy
):
    directories, selected = short_references
    args = arguments(tmp_path, protocol, policy=policy)
    observations, reports = [0, 0.013, 0.037], []
    for name, integrate in (("old", frozen.integrate), ("new", runner.integrate)):
        folder = tmp_path / name
        consumer = diagnostics.Comparison(
            directories,
            selected,
            folder,
            tmp_path,
            args["resources"],
            observations,
            policy="batched_cached",
        )
        passed = args if name == "new" else {k: v for k, v in args.items() if k != "policy"}
        reports.append(integrate(model, folder, comparison=consumer, **passed))
        assert all(r._iterator.gi_frame is None for r in consumer.readers.values())
    assert reports[0]["comparison"]["scores"] == reports[1]["comparison"]["scores"]

    def forbidden(*args, **kwargs):
        raise AssertionError("audit used writer decoder")

    monkeypatch.setattr(evidence, "decode_window", forbidden)
    folder = tmp_path / "new"
    audit.audit_trajectory(
        folder, expected(model, args), args["resources"], model.panel, perf_counter() + 60
    )
    sampled = audit.audit_samples(
        folder, directories, selected, observations, args["resources"], perf_counter() + 60
    )
    baseline = audit.source_audit.audit_samples(
        tmp_path / "old",
        directories,
        selected,
        observations,
        args["resources"],
        perf_counter() + 60,
    )
    assert sampled["ordered_sample_arrays_sha256"] == baseline["ordered_sample_arrays_sha256"]
    checked = audit.prior_audit.audit_readouts(
        folder,
        selected,
        "batched_cached",
        fixtures.definition()["instantaneous_tolerances"],
        args["resources"],
        perf_counter() + 60,
    )
    assert checked["maximum_scalar_difference_score"] == 0
    assert "evidence.decode_window(" not in inspect.getsource(audit)


def test_comparison_disagreement_stops_before_checkpoint_publication(
    tmp_path, model, protocol, short_references, monkeypatch
):
    directories, selected = short_references
    args, folder = arguments(tmp_path, protocol), tmp_path / "failed"
    consumer = diagnostics.Comparison(
        directories,
        selected,
        folder,
        tmp_path,
        args["resources"],
        [0, 0.037],
        policy="batched_cached",
    )
    monkeypatch.setattr(diagnostics.prep, "comparison_scores", lambda *a: {"ionic_state": 2.0})
    with pytest.raises(ValueError, match="limits failed before window commit"):
        runner.integrate(model, folder, comparison=consumer, **args)
    failed = ref.read_json(folder / "failure.json")
    assert failed["committed_chunks"] == 0 and failed["steps"] == 2
    assert all(r._iterator.gi_frame is None for r in consumer.readers.values())
    assert not (folder / "chunks.jsonl").exists() and (folder / "chunk-000000.npz").exists()


@pytest.mark.parametrize("interrupt", [True, False])
def test_interrupted_or_mutating_consumer_closes_and_cannot_promote_window(
    tmp_path, model, protocol, interrupt
):
    class Consumer:
        closed = False

        def open(self, *args):
            pass

        def consume(self, data):
            if interrupt:
                raise KeyboardInterrupt("consumer interruption fixture")
            data["increments"][0, 0] = 99

        def close(self):
            self.closed = True

    consumer, args, folder = Consumer(), arguments(tmp_path, protocol), tmp_path / "failed"
    with pytest.raises(KeyboardInterrupt if interrupt else ValueError):
        runner.integrate(model, folder, comparison=consumer, **args)
    assert consumer.closed
    failed = ref.read_json(folder / "failure.json")
    assert failed["committed_chunks"] == 0 and failed["accepted_tick"] == 2
    assert (
        failed["preservation"]["uncommitted-window.npz"]["status"]
        == "retained_diagnostic_not_restart"
    )


def test_real_scope_prior_sources_and_shared_quota():
    r = profile.specification(profile.OUTPUT_PARENT / "evidence-01")
    assert len(profile.SOURCES) == 62 and len(r["planned_attempts"]) == 12
    assert r["plan"]["policies"] == ["full_trace", "rk4_basis"]
    assert r["plan"]["readout_policy"] == "batched_cached"
    assert r["storage_budget"]["prior_bytes"] == 803085279
    assert r["storage_budget"]["new_root_limit_bytes"] == 270656545
    assert not r["plan"]["long_study_run"] and not r["plan"]["compact_long_policy_adopted"]
    assert len(r["production_source_hashes"]) == 39


@pytest.fixture
def registration_fixture(tmp_path, monkeypatch, protocol):
    source = tmp_path / "fixture.txt"
    source.write_text("short evidence source fixture\n")
    spec = {
        "resources": protocol["resources"],
        "runtime": prep.runtime(),
        "planned_attempts": ["first/full_trace", "first/rk4_basis"],
    }
    monkeypatch.setattr(profile, "ROOT", tmp_path)
    monkeypatch.setattr(profile, "SOURCES", ["fixture.txt"])
    monkeypatch.setattr(profile, "specification", lambda output: copy.deepcopy(spec))
    for key, value in profile.campaign.THREADS.items():
        monkeypatch.setenv(key, value)
    return tmp_path / "new", source


def test_registration_archive_identity_and_exclusivity(registration_fixture):
    output, source = registration_fixture
    registered = profile.register(output)
    assert profile.check_registration(output) == registered
    with pytest.raises(FileExistsError):
        profile.register(output)
    source.write_text("changed source fixture\n")
    with pytest.raises(ValueError, match="source identity"):
        profile.check_registration(output)


@pytest.mark.parametrize("timeout", [False, True])
def test_profile_failure_or_timeout_stops_once_and_keeps_closed_session(
    registration_fixture, monkeypatch, timeout
):
    output, _ = registration_fixture
    calls = []

    def fail(command, **kwargs):
        calls.append(command)
        if timeout:
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(profile.subprocess, "run", fail)
    with pytest.raises((ValueError, subprocess.TimeoutExpired)):
        profile.run(output)
    failed = ref.read_json(output / "failure.json")
    assert len(calls) == 1 and failed["no_automatic_retry"]
    assert failed["not_started"] == ["first/rk4_basis"]
    with pytest.raises(ValueError, match="Closed diagnostic session"):
        profile.worker(output, "first/rk4_basis")


@pytest.mark.parametrize("field", ["slopes", "first_increments", "last_increments", "times"])
def test_nonfinite_basis_inputs_are_refused(model, field):
    _, data = tiny_window(model.case)
    args = dict(width=3, size=model.coordinates.size, cells=model.n, budget=268435456)
    encoded, _ = evidence.encode_window("rk4_basis", data, **args)
    encoded = {k: v.copy() for k, v in encoded.items()}
    encoded[field].flat[0] = np.nan
    with pytest.raises(ValueError, match="values differ"):
        evidence.decode_window("rk4_basis", encoded, **args)


@pytest.mark.parametrize("policy", evidence.POLICIES)
def test_noncontiguous_and_fortran_inputs_serialize_in_c_order(tmp_path, model, policy):
    _, original = tiny_window(model.case)
    data = {k: np.asfortranarray(v) if v.ndim > 1 else v.copy() for k, v in original.items()}
    backing = np.repeat(data["slopes"], 2, axis=-1)
    data["slopes"] = backing[..., ::2]
    assert not data["slopes"].flags.c_contiguous
    args = dict(width=3, size=model.coordinates.size, cells=model.n, budget=268435456)
    encoded, _ = evidence.encode_window(policy, data, **args)
    path = tmp_path / "strided.npz"
    evidence.save_arrays(path, encoded, tmp_path, 10_000_000)
    loaded = evidence.read_arrays(
        path, evidence.layout(policy, 3, model.coordinates.size, model.n), budget=args["budget"]
    )
    assert_bits(evidence.decode_window(policy, loaded, **args), original)


@pytest.mark.parametrize("field", ["logical_array_bytes", "encoded_array_bytes", "policy"])
def test_recording_summary_tampering_is_not_trusted(tmp_path, model, protocol, field):
    args, folder = arguments(tmp_path, protocol), tmp_path / "run"
    runner.integrate(model, folder, **args)
    report = ref.read_json(folder / "trajectory.json")
    report["evidence"][field] = "full_trace" if field == "policy" else report["evidence"][field] + 1
    (folder / "trajectory.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match="encoding totals/policy"):
        evidence.load_checkpoint(folder, 0, expected(model, args))


def test_advertised_huge_npy_shape_is_rejected_before_loading(tmp_path, model, monkeypatch):
    _, data = tiny_window(model.case)
    args = dict(width=3, size=model.coordinates.size, cells=model.n, budget=268435456)
    encoded, _ = evidence.encode_window("rk4_basis", data, **args)
    path = tmp_path / "encoded.npz"
    evidence.save_arrays(path, encoded, tmp_path, 10_000_000)
    with zipfile.ZipFile(path) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    header = io.BytesIO()
    np.lib.format.write_array_header_1_0(
        header,
        {"descr": "<f8", "fortran_order": False, "shape": (2**40, 5, model.coordinates.size)},
    )
    members["slopes.npy"] = header.getvalue()
    forged = tmp_path / "forged.npz"
    with zipfile.ZipFile(forged, "x") as archive:
        for name, value in members.items():
            archive.writestr(name, value)
    layout = evidence.layout("rk4_basis", 3, model.coordinates.size, model.n)
    layout = {"slopes": layout["slopes"], **layout}

    def forbidden(*a, **kw):
        raise AssertionError("data allocation before header validation")

    monkeypatch.setattr(evidence.np, "frombuffer", forbidden)
    with pytest.raises(ValueError, match="NPY header differs"):
        evidence.read_arrays(forged, layout, budget=args["budget"])


def test_missing_comparison_payload_prevents_checkpoint_reuse(
    tmp_path, model, protocol, short_references
):
    directories, selected = short_references
    args, folder = arguments(tmp_path, protocol), tmp_path / "run"
    consumer = diagnostics.Comparison(
        directories,
        selected,
        folder,
        tmp_path,
        args["resources"],
        [0, 0.037],
        policy="batched_cached",
    )
    runner.integrate(model, folder, comparison=consumer, **args)
    (folder / "comparison/chunk-000000.npz").write_bytes(b"corrupt comparison fixture")
    with pytest.raises(ValueError, match="Committed comparison payload differs"):
        evidence.load_checkpoint(folder, 0, expected(model, args))
