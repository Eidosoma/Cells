"""Unchanged 50-check review suite plus exact native-clock regressions."""

import copy
import hashlib
import json
import math
import struct
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace as NS

import clock_job as fixed
import clock_labels as clock
import pytest

ctx, c, e = fixed.previous, fixed.c, fixed.e
# Reuse the frozen tests and their original globals. Do not rewrite the previous
# suite or bind its fixtures to the new implementation by changing shared modules.
prior_tests = ctx.private("_clock_prior_tests", fixed.OLD_HERE / "test_review.py")
for _name, _value in vars(prior_tests).items():
    if _name.startswith("test_") or _name in ("inputs", "prefix", "wiring"):
        globals()[_name] = _value


def test_clock_numpy_grids():
    # NumPy is permitted only in this separate, pinned label-generator process.
    # Neither parent reviewer nor child invokes BETSE, Cells, or an integrator.
    program = """
import hashlib, json, numpy as np
steps = [6.25e-6, 3.125e-6, 1.5625e-6, 7.8125e-7, 3.90625e-7]
rows = []
for duration in (0.001, 0.01):
    for dt in steps:
        n = round(duration / dt)
        values = np.linspace(0, duration, n)
        rows.append(dict(duration=duration, count=n,
                         sha256=hashlib.sha256(values.astype('<f8').tobytes()).hexdigest()))
print(json.dumps(dict(numpy=np.__version__, rows=rows)))
"""
    with e.model_fence():
        child = subprocess.run(
            [str(fixed.ROOT / "upstream/betse-venv/bin/python"), "-B", "-c", program],
            cwd=fixed.ROOT,
            env=fixed.util.environment(),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        result = json.loads(child.stdout)
        native = c.read(ctx.path("probe") / "native.json", None)
        assert result["numpy"] == native["environment"]["packages"]["numpy"]
        assert child.stderr == "" and len(result["rows"]) == 10
        for row in result["rows"]:
            values = clock.labels(row["duration"], row["count"])
            raw = struct.pack("<" + "d" * len(values), *values)
            assert hashlib.sha256(raw).hexdigest() == row["sha256"]
        assert sum(v["count"] for v in result["rows"]) == 54560


def test_clock_saved_failure():
    stream = ctx.reader()(ctx.path("probe") / "native/2/stream")
    labels = []
    with e.model_fence(), closing(iter(stream)) as iterator:
        header = next(iterator)["row"]
        for record in iterator:
            if record["kind"] == "native_step":
                i = record["index"]
                labels.append(record["label_s"])
                assert record["step"]["before_elapsed_s"] == i * header["dt_s"]
                assert record["step"]["after_elapsed_s"] == (i + 1) * header["dt_s"]
    n = header["steps"]
    assert stream.complete and len(labels) == n == 6400
    old = [i * 0.01 / (n - 1) for i in range(n)]
    assert (
        next(i for i, (a, b) in enumerate(zip(labels, old, strict=True)) if abs(a - b) > 1e-18)
        == 4462
    )
    assert labels[4462] == 0.006972964525707143
    with pytest.raises(ValueError, match="raw_labels_s"):
        e.Ledger().compare("raw_labels_s", labels, old, 1e-18, 0.0)
    ledger = e.Ledger()
    adapter = clock.ClockLedger(ledger, 0.01, n, c.exact.Exact)
    adapter.compare("raw_labels_s", labels, old, 1e-18, 0.0)
    assert adapter.calls == 1 and ledger.count == 6400 and ledger.maxima["raw_labels_s"] == 0


@pytest.mark.parametrize(
    "change", ["ulp_low", "ulp_high", "negative_zero", "missing", "endpoint", "nan"]
)
def test_clock_corruption(change):
    values = clock.labels(0.01, 6400)
    if change == "ulp_low":
        values[1] = math.nextafter(values[1], 0.0)
    elif change == "ulp_high":
        values[4462] = math.nextafter(values[4462], math.inf)
    elif change == "negative_zero":
        values[0] = -0.0
    elif change == "missing":
        values.pop()
    elif change == "endpoint":
        values[-1] = math.nextafter(values[-1], 0.0)
    else:
        values[10] = math.nan
    adapter = clock.ClockLedger(e.Ledger(), 0.01, 6400, c.exact.Exact)
    with pytest.raises(ValueError):
        adapter.compare("raw_labels_s", values, [i * 0.01 / 6399 for i in range(6400)], 1e-18, 0.0)


def test_clock_passthrough():
    calls = []
    target = NS(compare=lambda *a: calls.append(a))
    adapter = clock.ClockLedger(target, 0.01, 6400, c.exact.Exact)
    actual, expected = [1.0], [1.0]
    adapter.compare("raw_pump_density", actual, expected, 2e-18)
    assert calls == [("raw_pump_density", actual, expected, 2e-18, 2e-11)]
    assert calls[0][1] is actual and calls[0][2] is expected
    strict = clock.ClockLedger(e.Ledger(), 0.01, 6400, c.exact.Exact)
    with pytest.raises(ValueError):
        strict.compare("raw_pump_density", 1e-9, 0.0, 2e-18)


def test_clock_private_dispatch():
    job = fixed.controller()
    assert (
        "clock_amendment" not in ctx.SCOPE and job.ctx.SCOPE["clock_amendment"] == fixed.AMENDMENT
    )
    assert job.saved_review.native_records is not prior_tests.work.native_records
    assert job.saved_review.native_records.identity is prior_tests.work.native_records.identity
    assert job.saved_review.native_energy is prior_tests.work.native_energy
    baseline = c.read(e.CAPTURE / "betse.json", None)["rows"]["pump_leak/observed"]
    plan = dict(ctx.preparation()[0]["protocol"], duration_s=0.0002)
    variant = next(
        v
        for v in ctx.preparation()[1]["native_preparation"]["protocol"]["variants"]
        if v["id"] == "pump_leak"
    )
    before = ctx.original.arrays.digest(baseline)
    with e.model_fence():
        result = job.saved_review.native_records.inspect(
            baseline, baseline, plan, variant, e.Ledger()
        )
    assert result == dict(steps=8, physical_records=25, exact_raw_labels=8)
    assert ctx.original.arrays.digest(baseline) == before


@pytest.mark.parametrize("change", [None, "formula", "tolerance", "input", "source"])
def test_clock_binding(tmp_path, monkeypatch, change):
    job = fixed.controller()
    proof = dict(path="runs/clock-software-fixture/completion.json", sha256="1" * 64)
    r = dict(
        schema="cells.saved_relaxation_review@1",
        scope=copy.deepcopy(job.ctx.SCOPE),
        bounds=job.BOUNDS,
        rows=ctx.rows(),
        sources_sha256={},
        python=sys.version,
        inputs={},
        software=proof,
    )
    if change == "formula":
        r["scope"]["clock_amendment"]["corrected_formula"] = "wrong"
    elif change == "tolerance":
        r["scope"]["clock_amendment"]["scientific_tolerances_changed"] = True
    elif change == "input":
        r["inputs"]["preserved_review"] = "changed"
    elif change == "source":
        r["sources_sha256"]["changed.py"] = "0" * 64
    monkeypatch.setattr(job.ctx, "sources", lambda: {})
    monkeypatch.setattr(job.ctx, "authenticate_inputs", lambda: {})
    monkeypatch.setattr(job, "software", lambda _: proof)
    monkeypatch.setattr(c, "capsule", lambda *_: None)
    job.write(tmp_path / "registration.json", r)
    if change is None:
        assert job.authenticate(tmp_path, c.sha(tmp_path / "registration.json")) == r
    else:
        with pytest.raises(ValueError):
            job.authenticate(tmp_path, c.sha(tmp_path / "registration.json"))


def test_clock_detached(tmp_path, monkeypatch):
    job = fixed.controller()

    def register(output, _):
        output.mkdir()
        job.write(output / "registration.json", {})

    calls = []
    monkeypatch.setattr(job, "register", register)
    monkeypatch.setattr(
        fixed.subprocess, "Popen", lambda *a, **kw: calls.append((a, kw)) or NS(pid=123)
    )
    result = fixed.launch(job, tmp_path / "job", tmp_path / "proof")
    assert not result["automatic_polling"] and calls[0][1]["start_new_session"]
    assert calls[0][1]["stdin"] == subprocess.DEVNULL
    assert calls[0][0][0][5] == str(Path(fixed.__file__).resolve())


def test_clock_preserved_failure():
    with e.model_fence():
        receipt = fixed.failure_receipt(c.read(fixed.FAILED / "registration.json", None)["inputs"])
    assert len(receipt["files_sha256"]) == 7 and not receipt["original_completion_present"]
    assert receipt["files_sha256"]["failure.json"] == fixed.FAILED_SHA
