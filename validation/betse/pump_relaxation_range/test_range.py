"""Range selection and reused-science regression checks; not new numerical evidence."""

import copy
import subprocess
import sys
from contextlib import nullcontext
from types import SimpleNamespace as NS

import pytest
import range_job as job
import range_work as work

c = job.c


def test_scope():
    old = job.prior.ctx.inherited()
    assert job.STEPS == old["protocol"]["native_steps_s"]
    assert job.SCOPE["native_step_ranges_s"]["pump_only"] == job.STEPS
    assert all(
        steps == job.prior.STEPS
        for key, steps in job.SCOPE["native_step_ranges_s"].items()
        if key != "pump_only"
    )
    assert sum(round(row["duration_s"] / row["dt_s"]) for row in job.SCOPE["rows"]) == 11200
    assert work.capture is work.matched.capture
    for row in job.SCOPE["rows"]:
        prepared = work.matched.refined_work.preparation(old, row)
        assert prepared["protocol"]["steps"] == round(0.01 / row["dt_s"])
        for name in ("dt_s", "duration_s", "steps"):
            prepared["protocol"][name] = old["native_preparation"]["protocol"][name]
        assert prepared == old["native_preparation"]
    current = work.matched.prepared()["protocol"]
    for name in ("mapping", "trajectory", "refinement", "accounting", "reference"):
        assert current[name] == old["protocol"][name]


def fixture():
    # Coarse results here are explicit wiring fixtures, not measured trajectories.
    fine = c.read(job.CAPTURE / "native/pump_only/0/comparison.json", None)
    rows = []
    for step, scale in zip(job.STEPS, (4, 2, 1), strict=True):
        row = copy.deepcopy(fine)
        row["dt_s"] = step
        row["reference_errors"] = {k: v * scale for k, v in fine["reference_errors"].items()}
        rows.append(row)
    previous = c.read(job.CAPTURE / "comparison.json", None)
    packet = c.read(job.CAPTURE / "cells.json", None)
    cells = packet["records"]["pump_only/dt_1.25e-05/jax_jit"]
    pair = dict(records=6401, failed_comparisons=0)
    return rows, pair, previous, cells, work.matched.prepared()["protocol"]


@pytest.mark.parametrize(
    "change",
    [
        None,
        "fine_energy",
        "coarse_mapping",
        "contraction",
        "cross",
        "pair",
        "other_case",
        "old_verdict",
    ],
)
def test_conclusion(change):
    rows, pair, previous, cells, plan = fixture()
    if change in ("fine_energy", "coarse_mapping"):
        row = rows[-1] if change == "fine_energy" else rows[0]
        group = "energy_balance" if change == "fine_energy" else "native_live_rate_fmol_s"
        row.update(
            failed_comparisons=1, failed_groups={"fixture/" + group: 1}, within_finest_limits=False
        )
    elif change == "contraction":
        rows[0]["reference_errors"]["amount"] = 2e-10
        rows[1]["reference_errors"]["amount"] = 1.9e-10
    elif change == "cross":
        cells["states"][2][0] += 1e-3
    elif change == "pair":
        pair["failed_comparisons"] = 1
    elif change == "other_case":
        previous["cases"]["half_density"]["passed"] = False
    elif change == "old_verdict":
        previous["producer_passed"] = True
    if change in ("other_case", "old_verdict"):
        with pytest.raises(ValueError):
            work.conclude(rows, pair, previous, cells, plan)
    else:
        result = work.conclude(rows, pair, previous, cells, plan)
        job.gate("comparison", result)
        assert result["producer_passed"] is (change is None)
        assert not result["original_common_range_passed"] and not result["original_verdict_changed"]
        assert not result["matched_10ms_qualified"] and result["independent_review_pending"]
        assert result["original_pump_only_amount_refinement"]["passed"] is False


def test_native_dispatch(tmp_path, monkeypatch):
    package = tmp_path / "env/betse"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("# Dispatch fixture, not physics\n")
    template = tmp_path / "source/betse/data/yaml/sim_config.yaml"
    template.parent.mkdir(parents=True)
    template.write_text("{}\n")
    original = job.prior.ctx.inherited()
    original["native_preparation"]["upstream"]["files_sha256"] = {
        "betse/__init__.py": c.sha(package / "__init__.py")
    }
    calls = []
    codec = NS(RecordSink=lambda directory, **kw: kw)
    native = NS(
        codec=codec,
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
        assert variant["id"] == "pump_only" and actual_package == package and actual_template == {}
        plan = prepared["protocol"]
        calls.append((plan["dt_s"], plan["duration_s"], mode))
        directory.mkdir(parents=True)
        result = dict(
            id=variant["id"],
            mode=mode,
            steps=plan["steps"],
            stream=native.codec.RecordSink(directory / "stream", max_output_bytes=32 * 1024**2),
        )
        job.write(directory / "capture.json", result)
        return result

    native.run_row = run_row
    monkeypatch.setattr(job.prior.ctx, "inherited", lambda: original)
    for name, module in {
        "betse": NS(__file__=str(package / "__init__.py")),
        "live_native": native,
        "numpy": NS(errstate=lambda **_: nullcontext()),
        "ruamel": NS(),
        "ruamel.yaml": NS(YAML=lambda **_: NS(load=lambda _: {})),
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    result = work.capture(dict(scope=job.SCOPE), tmp_path / "capture", job.write, lambda _: None)
    job.gate("native", result)
    assert calls == [(r["dt_s"], r["duration_s"], r["mode"]) for r in job.SCOPE["rows"]]
    assert native.codec is codec


def test_compare_dispatch(tmp_path, monkeypatch):
    rows, *_ = fixture()
    records = []
    for row in job.SCOPE["rows"]:
        directory = tmp_path / "native" / row["role"]
        directory.mkdir(parents=True)
        job.write(directory / "capture.json", {})
        records.append(
            dict(
                **row,
                directory=str(directory.relative_to(tmp_path)),
                capture_sha256=c.sha(directory / "capture.json"),
            )
        )
    job.write(
        tmp_path / "native.json",
        dict(status="matched_native_captured", native_runs=3, records=records),
    )
    calls, pairs = [], []

    def compare(directory, link, prepared, variant, write):
        assert variant["id"] == "pump_only" and prepared["protocol"]["duration_s"] == 0.01
        calls.append(link["role"])
        return copy.deepcopy(rows[len(calls) - 1])

    def pair(left, right):
        pairs.append((left, right))
        return dict(records=6401, failed_comparisons=0)

    monkeypatch.setattr(work.matched, "compare_row", compare)
    monkeypatch.setattr(work.matched.recording, "pair", pair)
    result = work.compare({}, tmp_path, job.write, lambda _: None)
    job.gate("comparison", result)
    assert calls == ["pump_only/coarse", "pump_only/medium"]
    assert pairs == [
        (job.CAPTURE / "native/pump_only/0/stream", tmp_path / "native/pump_only/fine_quiet/stream")
    ]
    assert result["producer_passed"]
    assert result["cases"]["pump_only"]["rows"][-1]["dt_s"] == 1.5625e-6


@pytest.mark.parametrize("change", [None, "step", "case", "tolerance", "input", "source", "digest"])
def test_binding(tmp_path, monkeypatch, change):
    proof = dict(path="runs/range-software-fixture/completion.json", sha256="1" * 64)
    r = dict(
        schema="cells.pump_only_range@1",
        scope=copy.deepcopy(job.SCOPE),
        input=job.links(),
        software=proof,
        sources_sha256={},
        runtime=job.prior.ctx.runtime(),
    )
    if change == "step":
        r["scope"]["rows"][0]["dt_s"] *= 2
    elif change == "case":
        r["scope"]["rows"][0]["id"] = "pump_leak"
    elif change == "tolerance":
        r["scope"]["scientific_tolerances_changed"] = True
    elif change == "input":
        r["input"]["diagnosis_completion_sha256"] = "0" * 64
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
    assert not result["automatic_polling"] and calls[0][1]["start_new_session"]
    assert calls[0][1]["stdin"] == subprocess.DEVNULL


def test_failed_child(tmp_path, monkeypatch):
    monkeypatch.setattr(job.helpers, "deadline", lambda _: None)
    monkeypatch.setattr(job, "authenticate", lambda *_: dict(input={}))
    monkeypatch.setattr(job, "inputs", lambda: {})
    calls = []

    def fail(command, *_):
        calls.append(command)
        raise RuntimeError("intentional native failure")

    monkeypatch.setattr(job.helpers, "run_child", fail)
    with pytest.raises(RuntimeError, match="intentional"):
        job.execute(tmp_path, "fixture")
    assert len(calls) == 1 and calls[0][-3] == "native"
    assert (tmp_path / "failure.json").is_file() and not (tmp_path / "completion.json").exists()
    assert not (tmp_path / "comparison.stdout.log").exists()


@pytest.mark.parametrize("passed", [True, False])
def test_completion(tmp_path, monkeypatch, passed):
    monkeypatch.setattr(job.helpers, "deadline", lambda _: None)
    monkeypatch.setattr(job, "authenticate", lambda *_: dict(input={}))
    monkeypatch.setattr(job, "inputs", lambda: {})
    monkeypatch.setattr(job, "budget", lambda _: None)
    phases = []

    def run_child(command, out, err, timeout):
        phase = command[-3]
        phases.append(phase)
        assert timeout == job.SCOPE["phase_timeout_seconds"][phase]
        if phase == "native":
            result = dict(
                status="matched_native_captured", native_runs=3, records=job.SCOPE["rows"]
            )
            err.write("[range_job.py] Ignoring cutting event, as cut profiles are disabled.\n" * 6)
        else:
            result = work.conclude(*fixture())
            result["producer_passed"] = passed
            result["cases"]["pump_only"]["passed"] = passed
        job.write(tmp_path / (phase + ".json"), result)

    monkeypatch.setattr(job.helpers, "run_child", run_child)
    job.execute(tmp_path, "fixture")
    done = c.read(tmp_path / "completion.json", None)
    assert phases == ["native", "comparison"] and done["producer_passed"] is passed
    assert not done["original_common_range_passed"] and not done["matched_10ms_qualified"]
    assert c.sha(tmp_path / "comparison.json") == done["files_sha256"]["comparison.json"]


@pytest.mark.parametrize(
    "phase,text,passes",
    [
        (
            "native",
            "[range_job.py] Ignoring cutting event, as cut profiles are disabled.\n" * 6,
            True,
        ),
        (
            "native",
            "[matched_job.py] Ignoring cutting event, as cut profiles are disabled.\n" * 6,
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
