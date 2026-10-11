"""Saved real cases, adversarial resealing and detached reviewer controls only."""

import copy
import hashlib
import importlib
import json
import shutil
import struct
import sys
import zipfile
from types import SimpleNamespace

import audit_context as c
import cells_review as cells
import live_audit_job as job
import native_review as native
import pytest

KEY = "pump_leak/dt_2.5e-05/jax_jit"
ACTUAL = c.CAPTURE / "matrix/cells" / KEY
ACCEPTED = c.LEGACY / "cells" / KEY


def put(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def npz(path, values):
    """Test-only handwritten NPY container, no producer serializer/NumPy."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, a in values.items():
            header = repr(dict(descr=a["dtype"], fortran_order=False, shape=tuple(a["shape"])))
            header += " " * ((-10 - len(header) - 1) % 64) + "\n"
            vals = list(c.arrays.flatten(a["values"]))
            payload = struct.pack(
                "<" + str(len(vals)) + {"<f8": "d", "<i8": "q", "|b1": "B"}[a["dtype"]], *vals
            )
            z.writestr(
                name + ".npy",
                b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header.encode() + payload,
            )


@pytest.fixture(scope="module")
def base():
    return cells.Baseline(ACCEPTED)


@pytest.mark.parametrize(
    "key,phase",
    [
        (KEY, "probe"),
        (KEY, "matrix"),
        ("all_blocked/dt_1.25e-05/jax_jit", "matrix"),
        ("pump_leak/dt_5e-05/jax_eager", "matrix"),
        ("pump_leak/dt_5e-05/jax_jit", "matrix"),
    ],
)
def test_saved_cells_paths(key, phase):
    with c.e.model_fence():
        result = cells.inspect(c.CAPTURE / phase / "cells" / key, c.LEGACY / "cells" / key)
    assert result["direct_values"] > 0
    assert result["window_receipts"] == 3
    assert result["unsaved_trajectories_directly_inspected"] is False


@pytest.mark.parametrize(
    "dtype,values,shape",
    [
        ("<f8", [1.0, -0.0], [2]),
        ("<i8", [1, -2], [2]),
        ("|b1", [True, False], [2]),
        ("<f8", 2.0, []),
        ("<f8", [], [0, 3]),
    ],
)
def test_handwritten_array_bits(tmp_path, dtype, values, shape):
    a = dict(dtype=dtype, values=values, shape=shape)
    npz(tmp_path / "a.npz", {"a": a})
    decoded = c.arrays.decode_npz(tmp_path / "a.npz")["a"]
    cells.Bytes().add(decoded, "a", a)
    if shape == [2] and dtype == "<f8":
        assert cells.raw(decoded)[8:] == b"\0\0\0\0\0\0\0\x80"


@pytest.mark.parametrize("mutation", ["signed_zero", "dtype", "shape", "value", "nan"])
def test_array_corruption(mutation):
    a = dict(dtype="<f8", shape=[1], values=[-0.0])
    b = copy.deepcopy(a)
    if mutation == "signed_zero":
        b["values"] = [0.0]
    if mutation == "dtype":
        b.update(dtype="<i8", values=[0])
    if mutation == "shape":
        b.update(shape=[], values=-0.0)
    if mutation == "value":
        b["values"] = [1.0]
    if mutation == "nan":
        b["values"] = [float("nan")]
    with pytest.raises(ValueError):
        cells.Bytes().add(b, "x", a)


def test_receipt_hand_computation():
    a = dict(dtype="<f8", shape=[1], values=[-0.0])
    d = cells.Bytes()
    d.add(a, "a")
    expected = hashlib.sha256(
        b"a\0<f8(1,)" + hashlib.sha256(b"\0\0\0\0\0\0\0\x80").digest()
    ).hexdigest()
    assert d.report() == dict(exact_arrays=1, exact_values=1, comparison_sha256=expected)


@pytest.mark.parametrize(
    "mutation",
    [
        "step",
        "time",
        "cursor",
        "spec",
        "runtime",
        "source",
        "random",
        "state",
        "layout",
        "missing",
        "extra",
        "manifest_hash",
    ],
)
def test_checkpoint_resealed_corruption(tmp_path, base, mutation):
    target = tmp_path / "checkpoint"
    shutil.copytree(ACTUAL / "recordings/full/snapshots/step-0000000020", target)
    manifest = c.read(target / "manifest.json", None)
    if mutation == "step":
        manifest["clock"]["step_index"] = 19
    if mutation == "time":
        manifest["clock"]["time"] = 0.00049
    if mutation == "cursor":
        manifest["clock"]["event_index"] = 1
    if mutation == "spec":
        manifest["spec"]["execution"]["dt"] *= 2
    if mutation == "runtime":
        manifest["runtime"]["python"] = "different"
    if mutation == "source":
        manifest["source_hashes"].pop(next(iter(manifest["source_hashes"])))
    if mutation == "random":
        manifest["random_state"] = 1
    if mutation in ("state", "layout", "missing", "extra"):
        data = c.arrays.decode_npz(target / "state.npz")
        if mutation == "state":
            data["amount_increment"]["values"][0][0] += 1e-12
        if mutation == "layout":
            data["ids"]["values"][0] = 99
        if mutation == "missing":
            data.pop("ids")
        if mutation == "extra":
            data["unexpected"] = data["ids"]
        npz(target / "state.npz", data)
    manifest["state_sha256"] = c.sha(target / "state.npz")
    manifest["spec_sha256"] = c.arrays.digest(manifest["spec"])
    manifest["manifest_sha256"] = c.arrays.digest(
        {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    )
    if mutation == "manifest_hash":
        manifest["manifest_sha256"] = "0" * 64
    put(target / "manifest.json", manifest)
    with pytest.raises(ValueError):
        cells.checkpoint(target, base, 20, cells.Bytes())


@pytest.mark.parametrize(
    "mutation",
    [
        "digest",
        "arrays",
        "values",
        "windows",
        "clock_extent",
        "host_extent",
        "observations",
        "diagnostics",
        "estimate",
        "extra_resource",
    ],
)
def test_window_receipt_corruption(base, mutation):
    saved = c.read(ACTUAL / "comparison.json", None)["windows"][1]
    if mutation == "digest":
        saved["comparison_sha256"] = "0" * 64
    if mutation == "arrays":
        saved["exact_arrays"] -= 1
    if mutation == "values":
        saved["exact_values"] -= 1
    if mutation == "windows":
        saved["windows"] += 1
    if mutation == "clock_extent":
        saved["resources"]["executed_steps"] -= 1
    if mutation == "host_extent":
        saved["resources"]["peak_host_history_bytes"] += 8
    if mutation == "observations":
        saved["resources"]["validated_observations"] -= 1
    if mutation == "diagnostics":
        saved["diagnostics"]["max_energy_balance_error_pJ"] *= 2
    if mutation == "estimate":
        saved["resources"]["estimated_working_bytes"] = 0
    if mutation == "extra_resource":
        saved["resources"]["unknown"] = 1
    with pytest.raises(ValueError):
        cells.window_receipt(saved, base, 7, diagnostics=base.diagnostics)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "duplicate",
        "step",
        "time",
        "count",
        "observations",
        "snapshot_order",
        "snapshot_clock",
        "policy",
        "payload",
        "extra_array",
        "overlap",
        "unindexed",
        "diagnostics",
    ],
)
def test_resealed_recording_corruption(tmp_path, base, mutation):
    target = tmp_path / "recording"
    shutil.copytree(ACTUAL / "recordings/full", target)
    entries = [json.loads(line) for line in (target / "windows.jsonl").read_text().splitlines()]
    manifest = c.read(target / "manifest.json", None)
    if mutation == "missing":
        entries.pop()
    if mutation == "duplicate":
        entries.append(entries[-1])
    if mutation == "step":
        entries[1]["start_step"] = 6
    if mutation == "time":
        entries[1]["start_time"] = 0.0
    if mutation == "count":
        entries[1]["accepted_records"] += 1
    if mutation == "observations":
        entries[1]["validated_observations"] = 0
    if mutation == "snapshot_order":
        entries[2], entries[3] = entries[3], entries[2]
    if mutation == "snapshot_clock":
        entries[3]["step_index"] = 21
    if mutation == "policy":
        manifest["policy"]["recording"] = "observations"
    if mutation == "diagnostics":
        entries[0]["diagnostics"]["max_energy_balance_error_pJ"] = 1.0
    if mutation in ("payload", "extra_array", "overlap"):
        chunk = target / entries[1]["path"]
        data = c.arrays.decode_npz(chunk)
        if mutation == "payload":
            data["amount_increment"]["values"][0][0][0] += 1.0
        if mutation == "extra_array":
            data["extra"] = data["accepted_times"]
        if mutation == "overlap":
            data["accepted_times"]["values"][0] = base.times[7]
        npz(chunk, data)
        entries[1]["sha256"] = c.sha(chunk)
    if mutation == "unindexed":
        (target / "extra.bin").write_bytes(b"unused")
    (target / "windows.jsonl").write_text("".join(json.dumps(v) + "\n" for v in entries))
    manifest["files_sha256"]["windows.jsonl"] = c.sha(target / "windows.jsonl")
    put(target / "manifest.json", manifest)
    saved = c.read(ACTUAL / "comparison.json", None)["recordings"][0]
    with pytest.raises(ValueError):
        cells.recording(target, base, "full", saved, cells.Bytes())


def test_native_saved_row():
    label = "pump_leak/dt_6.25e-06/observed"
    record = c.read(c.NATIVE / "native.json", None)["records"][label]
    original = c.read(c.LEGACY / "betse.json", None)["records"][label]
    with c.e.model_fence():
        result = native.inspect(label, record, c.LEGACY / original)
    assert result["observed_updates"] == 160
    assert result["history_samples"] == 159
    assert result["exact_scalar_comparisons"] > 100000


def test_native_pair():
    report = c.read(c.NATIVE / "native.json", None)
    prefix = "pump_leak/dt_6.25e-06"
    paths = [
        c.NATIVE / report["records"][prefix + "/" + mode]["directory"] / "stream"
        for mode in ("observed", "unobserved")
    ]
    with c.e.model_fence():
        result = native.pair(*paths)
    expected = next(v for v in report["observer_pairs"] if v["label"] == prefix)
    assert result | dict(label=prefix) == expected


@pytest.mark.parametrize("mutation", ["signed_zero", "missing", "extra", "type", "value"])
def test_native_pair_rejects_changed_common_fields(monkeypatch, mutation):
    left = [
        dict(kind="native_header", row=dict(mode="observed", data=-0.0), trace={}),
        dict(kind="native_history", index=0, values=[1.0]),
    ]
    right = copy.deepcopy(left)
    right[0]["row"]["mode"] = "unobserved"
    if mutation == "signed_zero":
        right[0]["row"]["data"] = 0.0
    if mutation == "missing":
        right.pop()
    if mutation == "extra":
        right.append(right[-1])
    if mutation == "type":
        right[1]["values"] = [1]
    if mutation == "value":
        right[1]["values"] = [2.0]

    class Stream:
        def __init__(self, key):
            self.data, self.complete = (left if key == 0 else right), False

        def __iter__(self):
            yield from self.data
            self.complete = True

    monkeypatch.setattr(c.wire, "Stream", Stream)
    with pytest.raises(ValueError):
        native.pair(0, 1)


@pytest.mark.parametrize(
    "name",
    [
        "cells",
        "betse",
        "numpy",
        "jax",
        "matched_windows",
        "output_worker",
        "live_observer",
        "resume_job",
    ],
)
def test_import_fence(name):
    with c.e.model_fence(), pytest.raises(ImportError):
        importlib.import_module(name)


@pytest.mark.parametrize("path", ["../outside", "/absolute", "a/../b", "a//b", "a/./b", "a\\b", ""])
def test_unsafe_path(tmp_path, path):
    with pytest.raises(ValueError):
        c.child(tmp_path, path)


def test_linked_ancestor_refused(tmp_path):
    (tmp_path / "real").mkdir()
    link = tmp_path / "alias"
    link.symlink_to(tmp_path / "real", target_is_directory=True)
    try:
        with pytest.raises(ValueError):
            c.child(tmp_path, "alias/value.json")
        with pytest.raises(ValueError):
            c.inventory(tmp_path)
    finally:
        link.unlink()


def test_authenticated_saved_chain():
    with c.e.model_fence():
        _, files = c.authenticate()
    assert {k: len(v) for k, v in files.items()} == dict(
        capture=520, native=964, stopped=24, codec=782, codec_audit=44
    )


@pytest.mark.parametrize("mutation", ["payload", "extra", "missing"])
def test_packet_membership(tmp_path, mutation):
    (tmp_path / "a").write_bytes(b"a")
    put(tmp_path / "completion.json", dict(files_sha256={"a": c.sha(tmp_path / "a")}))
    expected = c.sha(tmp_path / "completion.json")
    if mutation == "payload":
        (tmp_path / "a").write_bytes(b"changed")
    if mutation == "extra":
        (tmp_path / "extra").write_bytes(b"extra")
    if mutation == "missing":
        (tmp_path / "a").unlink()
    with pytest.raises(ValueError):
        c.packet(tmp_path, "completion.json", expected)


def test_registered_internal_file_alias(tmp_path):
    directory = tmp_path / "software"
    tests = directory / "tests"
    tests.mkdir(parents=True)
    (tests / "data.json").write_text("{}")
    alias = tests / "current"
    alias.symlink_to(tests / "data.json")
    try:
        files, links = c.inventory(directory, pytest_links=True)
        put(directory / "completion.json", dict(files_sha256=files, pytest_internal_links=links))
        sha = c.sha(directory / "completion.json")
        c.packet(directory, "completion.json", sha, pytest_links=True)
        alias.unlink()
        with pytest.raises(ValueError, match="link coverage"):
            c.packet(directory, "completion.json", sha, pytest_links=True)
    finally:
        if alias.is_symlink():
            alias.unlink()


@pytest.mark.parametrize(
    "mutation", ["schema", "bounds", "source", "capture", "counts", "packet", "software"]
)
def test_resealed_registration_refused(tmp_path, monkeypatch, mutation):
    monkeypatch.setattr(c, "ROOT", tmp_path)
    output = tmp_path / "runs/audit"
    output.mkdir(parents=True)
    sources, files = {"test.py": "1" * 64}, {"capture": {"x": "2" * 64}}
    checked = dict(path="runs/software/completion.json", sha256="3" * 64, xml={})
    monkeypatch.setattr(c, "sources", lambda: sources)
    monkeypatch.setattr(c, "capsule", lambda *_: None)
    monkeypatch.setattr(c, "authenticate", lambda: ({}, files))
    monkeypatch.setattr(job, "software", lambda _: checked)
    registration = dict(
        schema="cells.live_recording_independent_review@1",
        decision="D129",
        bounds=copy.deepcopy(job.BOUNDS),
        capture_registration_sha256=c.REG_SHA,
        capture_completion_sha256=c.DONE_SHA,
        cells_counts=copy.deepcopy(c.COUNTS),
        sources_sha256=copy.deepcopy(sources),
        software=copy.deepcopy(checked),
        prerequisite_files_sha256=copy.deepcopy(files),
    )
    if mutation == "schema":
        registration["schema"] = "wrong"
    if mutation == "bounds":
        registration["bounds"]["timeout_seconds"] += 1
    if mutation == "source":
        registration["sources_sha256"]["test.py"] = "0" * 64
    if mutation == "capture":
        registration["capture_completion_sha256"] = "0" * 64
    if mutation == "counts":
        registration["cells_counts"]["matrix"]["window_runs"] -= 1
    if mutation == "packet":
        registration["prerequisite_files_sha256"]["capture"].clear()
    if mutation == "software":
        registration["software"]["sha256"] = "0" * 64
    put(output / "registration.json", registration)
    with pytest.raises(ValueError):
        job.authenticate(output, c.sha(output / "registration.json"))


def test_registration_tamper(tmp_path):
    put(tmp_path / "registration.json", dict(value=1))
    expected = c.sha(tmp_path / "registration.json")
    put(tmp_path / "registration.json", dict(value=2))
    with pytest.raises(ValueError, match="registration digest"):
        job.authenticate(tmp_path, expected)


def test_failed_review_durable(tmp_path, monkeypatch):
    root = tmp_path / "sandbox"
    output = root / "runs/audit"
    output.mkdir(parents=True)
    monkeypatch.setattr(c, "ROOT", root)
    monkeypatch.setattr(job, "limits", lambda: None)
    monkeypatch.setattr(job.os, "sched_getaffinity", lambda _: {0, 1, 2, 3})

    def reject(*_):
        raise ValueError("deliberate audit fault")

    monkeypatch.setattr(job, "authenticate", reject)
    monkeypatch.setattr(job, "review", lambda _: pytest.fail("Must not review failed inputs"))
    with pytest.raises(ValueError, match="deliberate audit fault"):
        job.execute(output, "bad")
    assert not (output / "completion.json").exists()
    assert c.read(output / "failure.json")["automatic_retry"] is False
    with pytest.raises(ValueError, match="Fresh registered"):
        job.execute(output, "bad")


def test_launch_detaches_without_wait(tmp_path, monkeypatch):
    output = tmp_path / "audit"

    def registration(p, _):
        p.mkdir()
        put(p / "registration.json", dict(test=True))

    calls = []

    def popen(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(pid=12345)  # deliberately no wait/poll/communicate

    monkeypatch.setattr(job, "register", registration)
    monkeypatch.setattr(job.subprocess, "Popen", popen)
    ack = job.launch(output, tmp_path / "software")
    assert ack["status"] == "launched_detached" and ack["automatic_polling"] is False
    assert calls[0][1]["start_new_session"] is True
    assert calls[0][1]["stdin"] == job.subprocess.DEVNULL
    assert calls[0][0][-2:] == ["--registration-sha", c.sha(output / "registration.json")]


def test_launch_failure_durable(tmp_path, monkeypatch):
    output = tmp_path / "audit"

    def registration(p, _):
        p.mkdir()
        put(p / "registration.json", {})

    def popen(*_, **__):
        raise OSError("launch rejected")

    monkeypatch.setattr(job, "register", registration)
    monkeypatch.setattr(job.subprocess, "Popen", popen)
    with pytest.raises(OSError):
        job.launch(output, tmp_path / "software")
    assert c.read(output / "launch-failure.json")["status"] == "not_launched"


def test_cells_coverage_refusal():
    with pytest.raises(ValueError):
        job.cells_gate("matrix", {})


def test_native_coverage_refusal():
    with pytest.raises(ValueError):
        native.matrix_gate({}, {})


def test_fresh_destination_no_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "ROOT", tmp_path)
    output = tmp_path / "runs/existing"
    output.mkdir(parents=True)
    with pytest.raises(ValueError):
        job.fresh(output)


def test_no_simulator_imports():
    assert not any(n.split(".")[0] in ("cells", "betse", "jax", "numpy") for n in sys.modules)


def test_reviewer_controller_identity():
    assert job.__file__ == str(c.HERE / "live_audit_job.py")


def test_budget_failure(tmp_path, monkeypatch):
    (tmp_path / "a").write_bytes(b"too large")
    monkeypatch.setitem(job.BOUNDS, "per_file_bytes", 1)
    with pytest.raises(ValueError, match="per-file budget"):
        job.budget(tmp_path)
