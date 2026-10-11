"""Saved-prefix arithmetic, corruption refusals and detached diagnosis lifecycle."""

import copy
import subprocess
from decimal import Decimal
from functools import lru_cache
from types import SimpleNamespace as NS

import bath_diagnosis as bath
import diagnose_job as job
import numpy as np
import pytest

c = job.c


@lru_cache(maxsize=3)
def prefix(index):
    stream = bath.recording.stream(job.CAPTURE / f"native/pump_only/{index}/stream")
    iterator = iter(stream)
    header, records = next(iterator), []
    try:
        for record in iterator:
            if record["kind"] == "native_step":
                records.append(record)
                if len(records) == 4:
                    break
    finally:
        iterator.close()
    assert not stream.complete  # This is a prefix smoke, never a full-row review.
    return header, records


def test_saved_coordinates():
    result = bath.diagnostic_summary()
    assert not result["original_convergence_verdict_changed"]
    assert all(v["largest_coordinates"][0]["coordinate"] == "bath/Na" for v in result["rows"])
    stored = [v["stored_amount_error_fmol"] for v in result["rows"]]
    integral = [v["pump_integral_bath_error_fmol"] for v in result["rows"]]
    assert stored[0] < 5e-11 < stored[1] < stored[2]
    assert all(b < 0.6 * a for a, b in zip(integral[:-1], integral[1:], strict=True))
    assert max(result["reference_amount_agreement_fmol"].values()) < 1e-17
    for row in result["rows"]:
        for v in row["common_decomposition"]:
            assert np.allclose(
                np.asarray(v["pump_integral_bath_fmol"]) + v["stored_minus_integral_fmol"],
                v["stored_bath_fmol"],
                rtol=0,
                atol=1e-18,
            )


@pytest.mark.parametrize("index", range(3))
def test_recorded_replay(index):
    header, records = prefix(index)
    bath.validate_header(header, job.STEPS[index])
    for record in records:
        result = bath.replay_step(header, record)
        assert len(result) == 3 and result[2]["exact_flux_fmol"] == 0
        for row in result:
            total = (
                row["addition_error_fmol"] + row["mixing_error_fmol"] + row["product_error_fmol"]
            )
            assert abs(row["storage_error_fmol"] - total) < Decimal("1e-39")
    assert abs(result[0]["storage_error_fmol"]) > Decimal("1e-15")


def test_decimal_precision(monkeypatch):
    header, records = prefix(2)
    baseline = bath.replay_step(header, records[0])
    monkeypatch.setattr(job, "PRECISION", 100)
    tighter = bath.replay_step(header, records[0])
    for a, b in zip(baseline, tighter, strict=True):
        for key in a:
            if isinstance(a[key], Decimal):
                assert abs(a[key] - b[key]) < Decimal("1e-65")
            else:
                assert a[key] == b[key]


@pytest.mark.parametrize(
    "change", ["final", "control", "calls", "leak", "junction", "uniform", "applied", "nonfinite"]
)
def test_corrupted_record(change):
    header, records = prefix(2)
    record = copy.deepcopy(records[0])
    raw = record["raw_step"]
    if change == "final":
        record["step"]["after_voltage"]["physical"]["outside_mM"][0][0] += 1e-10
    elif change == "control":
        raw["before"]["rho_pump"] = 0.5
    elif change == "calls":
        raw["calls"].pop()
    elif change == "leak":
        raw["calls"][1]["returned"][0] = 1e-10
    elif change == "junction":
        record["step"]["before_ordinary"]["physical"]["junction_density_mol_per_m2_s"][0][0] = 1e-10
    elif change == "uniform":
        raw["before"]["physical"]["outside_mM"][0][1] += 1e-10
    elif change == "applied":
        record["step"]["before_ordinary"]["physical"]["ordinary_density_mol_per_m2_s"][0][0] += (
            1e-10
        )
    elif change == "nonfinite":
        raw["before"]["physical"]["outside_mM"][0][0] = float("nan")
    with pytest.raises(ValueError):
        bath.replay_step(header, record)


@pytest.mark.parametrize("change", ["case", "mode", "step", "ecm", "volume"])
def test_wrong_scope(change):
    header = copy.deepcopy(prefix(0)[0])
    row = header["row"]
    if change == "case":
        row["id"] = "pump_leak"
    elif change == "mode":
        row["mode"] = "unobserved"
    elif change == "step":
        row["dt_s"] *= 2
    elif change == "ecm":
        row["settings"]["is_ecm"] = True
    else:
        row["geometry"]["configured_bath_volume_m3"] *= 2
    with pytest.raises(ValueError):
        bath.validate_header(header, job.STEPS[0])


def synthetic_stream():
    header, recorded = prefix(0)
    header, sample = copy.deepcopy(header), copy.deepcopy(recorded[0])
    step = 0.00025
    header["row"].update(dt_s=step, steps=40)
    initial = header["trace"]["initial"]["physical"]["outside_mM"]
    sample["raw_step"]["calls"][0]["returned"] = [[0.0] * 30 for _ in range(3)]
    sample["step"]["before_ordinary"]["physical"]["ordinary_density_mol_per_m2_s"] = [
        [0.0] * 30 for _ in range(6)
    ]
    sample["raw_step"]["before"]["physical"]["outside_mM"] = copy.deepcopy(initial)
    sample["step"]["after_voltage"]["physical"]["outside_mM"] = copy.deepcopy(initial)
    records = [header]
    for i in range(40):
        row = copy.deepcopy(sample)
        row["index"] = row["raw_step"]["index"] = row["step"]["index"] = i
        row["step"].update(before_elapsed_s=i * step, after_elapsed_s=(i + 1) * step)
        records.append(row)
        if i:
            records.append(dict(kind="native_history", index=i - 1))
    records.append(
        dict(kind="native_footer", row=dict(final=dict(physical=dict(outside_mM=initial))))
    )
    return records


@pytest.mark.parametrize("change", [None, "order", "clock", "truncated", "saved_link"])
def test_stream_coverage(tmp_path, monkeypatch, change):
    records = synthetic_stream()
    if change == "order":
        records[1]["index"] = 1
    elif change == "clock":
        records[1]["step"]["after_elapsed_s"] *= 2
    elif change == "truncated":
        records.pop()

    class Stream:
        complete = False
        metrics = {}

        def __iter__(self):
            yield from records
            self.complete = True

    saved = dict(common_points=dict(states=[[0.0] * 59 for _ in range(41)]))
    if change == "saved_link":
        saved["common_points"]["states"][10][21] = 1.0
    monkeypatch.setattr(job, "STEPS", [0.00025])
    monkeypatch.setattr(bath.recording, "stream", lambda _: Stream())
    monkeypatch.setattr(
        bath,
        "common_reference",
        lambda: ([i * 0.00025 for i in range(41)], [[0.0] * 59 for _ in range(41)]),
    )
    monkeypatch.setattr(c, "read", lambda *_: saved)
    if change is None:
        result = bath.stream_row(0, job.write, tmp_path)
        assert result["steps"] == 40 and result["exact_bath_scalar_matches"] == 3600
        assert result["decimal_decomposition_max_residual_fmol"] == 0.0
    else:
        with pytest.raises(ValueError):
            bath.stream_row(0, job.write, tmp_path)


@pytest.mark.parametrize("change", [None, "scope", "input", "source", "digest"])
def test_binding(tmp_path, monkeypatch, change):
    proof = dict(path="runs/diagnosis-software-fixture/completion.json", sha256="1" * 64)
    r = dict(
        schema="cells.saved_bath_diagnosis@1",
        scope=copy.deepcopy(job.SCOPE),
        input=job.links(),
        software=proof,
        sources_sha256={},
        runtime=job.prior.ctx.runtime(),
    )
    if change == "scope":
        r["scope"]["decimal_precision"] = 50
    elif change == "input":
        r["input"]["completion_sha256"] = "0" * 64
    elif change == "source":
        r["sources_sha256"]["changed.py"] = "0" * 64
    monkeypatch.setattr(job, "sources", lambda: {})
    monkeypatch.setattr(job, "software", lambda _: proof)
    monkeypatch.setattr(c, "capsule", lambda *_: None)
    job.write(tmp_path / "registration.json", r)
    digest = "0" * 64 if change == "digest" else c.sha(tmp_path / "registration.json")
    if change is None:
        assert job.authenticate(tmp_path, digest) == r
    else:
        with pytest.raises(ValueError):
            job.authenticate(tmp_path, digest)


def test_detached(tmp_path, monkeypatch):
    def register(output, _):
        output.mkdir()
        job.write(output / "registration.json", {})

    calls = []
    monkeypatch.setattr(job, "register", register)
    monkeypatch.setattr(
        job.subprocess, "Popen", lambda *a, **kw: calls.append((a, kw)) or NS(pid=123)
    )
    result = job.launch(tmp_path / "job", tmp_path / "proof")
    assert result["automatic_polling"] is False
    assert calls[0][1]["start_new_session"] and calls[0][1]["stdin"] == subprocess.DEVNULL


def test_failed_child(tmp_path, monkeypatch):
    monkeypatch.setattr(job.helpers, "deadline", lambda _: None)
    monkeypatch.setattr(job, "authenticate", lambda *_: dict(input={}))
    monkeypatch.setattr(job, "inputs", lambda: {})
    calls = []

    def fail(command, *_):
        calls.append(command)
        raise RuntimeError("intentional replay failure")

    monkeypatch.setattr(job.helpers, "run_child", fail)
    with pytest.raises(RuntimeError, match="intentional"):
        job.execute(tmp_path, "test")
    assert len(calls) == 1 and "worker" in calls[0]
    assert (tmp_path / "failure.json").is_file() and not (tmp_path / "completion.json").exists()
