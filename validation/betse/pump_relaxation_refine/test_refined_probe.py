"""Storage-cap and smaller-step regressions; preserve previously qualified science."""

import array
import copy
import hashlib
import random
import subprocess
import sys
from contextlib import nullcontext
from types import SimpleNamespace as NS

import pytest
import refined_job as job
import refined_recording as recording
import refined_work as work

c = job.c
sys.path.insert(0, str(job.HERE.parent / "native_recording"))
import record_codec as codec  # noqa: E402


def test_large_stream(tmp_path):
    directory = tmp_path / "over_32mib"
    rng, expected = random.Random(917), hashlib.sha256()
    with codec.RecordSink(directory, max_output_bytes=recording.STREAM_BYTES) as sink:
        for i in range(80):
            values = [-0.0, 0.0] + [rng.uniform(-1e9, 1e9) for _ in range(65534)]
            expected.update(array.array("d", values).tobytes())
            sink.append(dict(index=i, values=values))
        manifest = sink.finish()
    assert sum(p.stat().st_size for p in directory.iterdir()) > 32 * 1024**2
    actual, stream, count = hashlib.sha256(), recording.stream(directory), 0
    for row in stream:
        assert row["index"] == count
        actual.update(array.array("d", row["values"]).tobytes())
        count += 1
    assert count == 80 and stream.complete and actual.digest() == expected.digest()
    assert manifest["peak_encoded_chunk_bytes"] <= 8 * 1024**2
    assert c.wire.STREAM_BYTES == 32 * 1024**2
    with pytest.raises(ValueError, match="Manifest payload_bytes integer/extent"):
        c.wire.Stream(directory)


def test_unchanged_chunk_bytes(tmp_path):
    records = c.read(c.NATIVE / "native.json", None)["records"]
    source = c.child(c.NATIVE, records["pump_leak/dt_6.25e-06/observed"]["directory"]) / "stream"
    rows = list(c.wire.Stream(source))
    native = NS(codec=codec)
    for name, context in (("old", nullcontext()), ("new", recording.writer_limit(native))):
        with (
            context,
            native.codec.RecordSink(tmp_path / name, max_output_bytes=32 * 1024**2) as sink,
        ):
            for row in rows:
                sink.append(row)
            sink.finish()
    assert native.codec is codec
    for p in (tmp_path / "old").iterdir():
        if p.name != "manifest.json":
            assert p.read_bytes() == (tmp_path / "new" / p.name).read_bytes()
    old, new = (c.read(tmp_path / name / "manifest.json") for name in ("old", "new"))
    assert old.pop("max_output_bytes") == 32 * 1024**2
    assert new.pop("max_output_bytes") == recording.STREAM_BYTES
    assert old == new
    exact, decoded = c.exact.Exact(), recording.stream(tmp_path / "new")
    for a, b in zip(rows, decoded, strict=True):
        exact.match(a, b, "Identical larger-cap evidence")
    assert decoded.complete and exact.floats > 0 and exact.negative_zeros > 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_output_bytes", 128 * 1024**2 + 1),
        ("chunk_bytes", 8 * 1024**2 + 1),
        ("chunk_records", 33),
    ],
)
def test_reader_limits(tmp_path, field, value):
    directory = tmp_path / "bad"
    with codec.RecordSink(directory, max_output_bytes=recording.STREAM_BYTES) as sink:
        sink.append(dict(value=1.0))
        manifest = sink.finish()
    manifest[field] = value
    (directory / "manifest.json").write_bytes(codec.canonical(manifest))
    with pytest.raises(ValueError):
        recording.stream(directory)
    assert c.wire.CHUNK_BYTES == 8 * 1024**2 and c.wire.STREAM_BYTES == 32 * 1024**2


@pytest.mark.parametrize("fail", [False, True])
def test_limits_restored(tmp_path, fail):
    native = NS(codec=codec)
    try:
        with recording.writer_limit(native):
            with native.codec.RecordSink(
                tmp_path / "stream", max_output_bytes=32 * 1024**2
            ) as sink:
                assert sink.max_output_bytes == recording.STREAM_BYTES
            if fail:
                raise RuntimeError("deliberate")
    except RuntimeError:
        assert fail
    assert native.codec is codec


def test_recorder_arguments_refused(tmp_path):
    native = NS(codec=codec)
    with recording.writer_limit(native), pytest.raises(ValueError, match="recorder arguments"):
        native.codec.RecordSink(tmp_path / "invalid", max_output_bytes=16 * 1024**2)
    assert not (tmp_path / "invalid").exists()


def test_preparation():
    original = job.ctx.inherited()
    before = copy.deepcopy(original)
    for row in job.SCOPE["rows"]:
        prepared = work.preparation(original, row)
        assert prepared["protocol"]["steps"] * row["dt_s"] == row["duration_s"]
        for name in ("duration_s", "steps", "dt_s"):
            prepared["protocol"][name] = original["native_preparation"]["protocol"][name]
        assert prepared == original["native_preparation"]
    assert original == before
    assert sum(round(r["duration_s"] / r["dt_s"]) for r in job.SCOPE["rows"]) == 66560


def test_saved_coarse_miss():
    row = c.read(job.PRIOR / "native/2/comparison.json", None)
    assert row["failed_comparisons"] == 1 and not row["within_finest_limits"]
    assert row["accounting"]["energy_pJ"] / 1e-7 == pytest.approx(3.657673158449781)


def test_numerical_miss_retained():
    sys.path.insert(0, str(job.HERE.parent / "pump_pilot_refinement"))
    import refinement_check as checker

    plan = job.ctx.inherited()["protocol"]
    points = dict(states=[[0.0] * 59], voltage_V=[[0.0] * 7])
    results = [
        dict(reference_errors=dict(amount=e, energy=e, voltage=e), within_finest_limits=True)
        for e in (1e-6, 5e-7, 2.5e-7)
    ]
    for energy, passed in ((9.2e-8, True), (1.01e-7, False)):
        ledger = checker.Ledger()
        results[-1]["within_finest_limits"] = work.prior.assess(
            checker, ledger, points, points, dict(energy_pJ=energy), plan
        )
        assert work.conclusion(results, plan, checker)["main_case_ladder_adequate"] is passed
        assert ledger.failed_comparisons == int(not passed)
        if not passed:
            assert ledger.examples[0]["budget"] == 1e-7


def test_native_dispatch(tmp_path, monkeypatch):
    package = tmp_path / "env/betse"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("# Dispatch fixture, not physics\n")
    template = tmp_path / "source/betse/data/yaml/sim_config.yaml"
    template.parent.mkdir(parents=True)
    template.write_text("{}\n")
    original = job.ctx.inherited()
    original["native_preparation"]["upstream"]["files_sha256"] = {
        "betse/__init__.py": c.sha(package / "__init__.py")
    }
    calls = []
    original_codec = NS(RecordSink=lambda directory, **kw: kw)
    native = NS(
        codec=original_codec,
        ctx=NS(NATIVE_PYTHON=tmp_path / "env/bin/python"),
        prior=NS(
            c=NS(
                SOURCE=tmp_path / "source",
                environment=lambda: dict(packages={}),
                locked_reference_packages=lambda: {},
            )
        ),
    )

    def run_row(prepared, variant, mode, directory, actual_package, actual_template):
        assert variant["id"] == "pump_leak" and actual_package == package and actual_template == {}
        plan = prepared["protocol"]
        calls.append((plan["dt_s"], plan["duration_s"], mode))
        directory.mkdir(parents=True)
        result = dict(
            steps=plan["steps"],
            stream=native.codec.RecordSink(directory / "stream", max_output_bytes=32 * 1024**2),
        )
        job.write(directory / "capture.json", result)
        return result

    native.run_row = run_row
    monkeypatch.setattr(job.ctx, "inherited", lambda: original)
    for name, module in {
        "betse": NS(__file__=str(package / "__init__.py")),
        "live_native": native,
        "numpy": NS(errstate=lambda **_: nullcontext()),
        "ruamel": NS(),
        "ruamel.yaml": NS(YAML=lambda **_: NS(load=lambda _: {})),
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    result = work.capture(dict(scope=job.SCOPE), tmp_path / "capture", job.write, lambda _: None)
    assert result["native_runs"] == len(calls) == 4 and native.codec is original_codec
    assert calls == [(r["dt_s"], r["duration_s"], r["mode"]) for r in job.SCOPE["rows"]]


def test_registration_tamper(tmp_path):
    job.write(tmp_path / "registration.json", {})
    with pytest.raises(ValueError, match="registration digest"):
        job.authenticate(tmp_path, "0" * 64)


@pytest.mark.parametrize(
    "change", [None, "step", "duration", "cap", "tolerance", "coarse", "source"]
)
def test_resealed_registration(tmp_path, monkeypatch, change):
    # Isolate registration checks; software/capsule verification has its own
    # qualified helpers. Real immutable prerequisite identities are still used.
    proof = dict(path="runs/refined-software-fixture/completion.json", sha256="1" * 64)
    r = dict(
        schema="cells.pump_relaxation_refinement@1",
        scope=copy.deepcopy(job.SCOPE),
        sources_sha256={},
        software=proof,
        runtime=job.ctx.runtime(),
        reference_directory=str(job.old.REFERENCE.relative_to(job.ROOT)),
        reference_completion_sha256=job.old.REFERENCE_SHA,
        prior=dict(
            directory=str(job.PRIOR.relative_to(job.ROOT)),
            completion_sha256=job.PRIOR_SHA,
            registration_sha256=job.PRIOR_REG,
            review_sha256=c.sha(job.PRIOR / "review.json"),
            coarse_comparison_sha256=c.sha(job.PRIOR / "native/2/comparison.json"),
        ),
    )
    if change in ("step", "duration"):
        field = "dt_s" if change == "step" else "duration_s"
        r["scope"]["rows"][0][field] *= 2
    elif change == "cap":
        r["scope"]["stream_bytes"] *= 2
    elif change == "tolerance":
        r["scope"]["scientific_tolerances_changed"] = True
    elif change == "coarse":
        r["prior"]["coarse_comparison_sha256"] = "0" * 64
    elif change == "source":
        r["sources_sha256"]["changed.py"] = "0" * 64
    monkeypatch.setattr(job, "sources", lambda: {})
    monkeypatch.setattr(job, "software", lambda _: proof)
    monkeypatch.setattr(c, "capsule", lambda *_: None)
    job.write(tmp_path / "registration.json", r)
    digest = c.sha(tmp_path / "registration.json")
    if change is None:
        assert job.authenticate(tmp_path, digest) == r
    else:
        with pytest.raises(ValueError, match="scope/sources/prior"):
            job.authenticate(tmp_path, digest)


def test_detached_launch(tmp_path, monkeypatch):
    def register(output, _):
        output.mkdir()
        job.write(output / "registration.json", {})

    calls = []
    monkeypatch.setattr(job, "register", register)
    monkeypatch.setattr(
        job.subprocess, "Popen", lambda *a, **kw: calls.append((a, kw)) or NS(pid=234)
    )
    result = job.launch(tmp_path / "job", tmp_path / "software")
    assert not result["automatic_polling"] and calls[0][1]["start_new_session"]
    assert calls[0][1]["stdin"] == subprocess.DEVNULL


def test_failure_stops(tmp_path, monkeypatch):
    monkeypatch.setattr(job.helpers, "deadline", lambda _: None)
    monkeypatch.setattr(job, "authenticate", lambda *_: dict(prior={}))
    monkeypatch.setattr(job, "prior", lambda: {})
    calls = []

    def fail(command, *_):
        calls.append(command)
        raise RuntimeError("intentional native failure")

    monkeypatch.setattr(job.helpers, "run_child", fail)
    with pytest.raises(RuntimeError, match="intentional"):
        job.execute(tmp_path, "test")
    assert len(calls) == 1 and calls[0][-3] == "native"
    assert (tmp_path / "failure.json").is_file() and not (tmp_path / "completion.json").exists()
    assert not (tmp_path / "comparison.stdout.log").exists()


@pytest.mark.parametrize(
    "phase,text,passes",
    [
        (
            "native",
            "[refined_job.py] Ignoring cutting event, as cut profiles are disabled.\n" * 8,
            True,
        ),
        (
            "native",
            "[probe_job.py] Ignoring cutting event, as cut profiles are disabled.\n" * 8,
            False,
        ),
        ("native", "", False),
        ("comparison", "", True),
        ("comparison", "warning\n", False),
    ],
)
def test_stderr(phase, text, passes):
    if passes:
        job.stderr_check(phase, text)
    else:
        with pytest.raises(ValueError):
            job.stderr_check(phase, text)
