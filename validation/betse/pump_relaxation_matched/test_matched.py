"""Campaign wiring and unchanged acceptance laws, plus a real 10 ms Cells smoke."""

import copy
import subprocess
import sys
from contextlib import nullcontext
from types import SimpleNamespace as NS

import matched_job as job
import matched_work as work
import pytest

c = job.c


def test_preparation():
    original = job.ctx.inherited()
    result = work.prepared()
    plan = result["protocol"]
    assert plan["variants"] == job.VARIANTS
    for name in ("mapping", "trajectory", "refinement", "accounting", "reference"):
        assert plan[name] == original["protocol"][name]
    for name in ("cells_steps_s", "cells_eager_step_s", "restart_step_s", "restart_time_s"):
        assert plan[name] == job.SCOPE[name]
    for identifier, case in result["cases"].items():
        before = copy.deepcopy(case)
        assert before.pop("end_time_s") == 0.01
        old = copy.deepcopy(original["cases"][identifier])
        assert old.pop("end_time_s") == 0.001
        assert before == old
    assert len(plan["common_times_s"]) == 41 and plan["common_times_s"][-1] == 0.01
    for row in job.SCOPE["rows"]:
        native = work.refined_work.preparation(original, row)
        assert native["protocol"]["steps"] == round(0.01 / row["dt_s"])
        for name in ("dt_s", "duration_s", "steps"):
            native["protocol"][name] = original["native_preparation"]["protocol"][name]
        assert native == original["native_preparation"]
    assert sum(round(row["duration_s"] / row["dt_s"]) for row in job.SCOPE["rows"]) == 352000
    assert len(job.SCOPE["rows"]) == 20


def test_cells_adapter():
    preparation = work.prepared()
    plan = preparation["protocol"]
    adapter = work.cells_adapter(plan)
    original = work.checker.ctx.base
    for case in preparation["cases"].values():
        for jit, step in [(True, h) for h in plan["cells_steps_s"]] + [
            (False, plan["cells_eager_step_s"])
        ]:
            expected = original.definition(case, step, jit=jit, times=plan["common_times_s"])
            assert adapter.ctx.definition(case, step, jit=jit) == expected
            assert expected["execution"]["max_steps"] >= round(0.01 / step)
    assert adapter.ctx is not original
    assert (
        len(
            original.definition(preparation["cases"]["pump_leak"], 5e-5)["experiment"][
                "observation_times"
            ]
        )
        == 5
    )


def test_cells_smoke(tmp_path):
    # Public production APIs, one dynamic case, 200 RK4 steps, 41 observations,
    # actual saved/loaded 5 ms restart. Not the full 24-trajectory acceptance.
    script = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import matched_work as work
import numpy as np
from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.io import load_snapshot, write_run
r = work.prepared()
definition = work.cells_adapter(r["protocol"]).ctx.definition(r["cases"]["pump_leak"], 5e-5)
spec = parse_spec(definition)
result = run(spec)
directory = Path(sys.argv[2]) / "smoke"
write_run(directory, result, checkpoint_times=(0.005,))
index = result.checkpoint_at(0.005).step_index
loaded = load_snapshot(directory / f"snapshots/step-{index:06d}")
resumed = run(loaded.spec, loaded.checkpoint)
assert index == 100
assert np.array_equal(result.times[index:], resumed.times)
assert all(np.array_equal(np.asarray(a)[index:], b)
           for a, b in zip(result.history, resumed.history, strict=True))
assert list(np.asarray(result.observations.times)) == r["protocol"]["common_times_s"]
assert np.asarray(result.observations.voltage_V).shape[0] == 41
print("10 ms Cells smoke and exact loaded restart passed")
"""
    result = subprocess.run(
        [
            "taskset",
            "-c",
            "0-3",
            str(job.ROOT / ".venv/bin/python"),
            "-B",
            "-W",
            "error",
            "-c",
            script,
            str(job.HERE),
            str(tmp_path),
        ],
        env=job.environment(),
        cwd=job.ROOT,
        capture_output=True,
        text=True,
        timeout=35,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not result.stderr and "passed" in result.stdout


def packet_fixture(monkeypatch):
    preparation = work.prepared()
    plan = preparation["protocol"]
    points = dict(states=[[0.0] * 59 for _ in range(41)], voltage_V=[[0.0] * 7 for _ in range(41)])
    monkeypatch.setattr(work, "primary", lambda *_: copy.deepcopy(points))
    rows, resumes = {}, {}
    key = work.checker.ctx.base.key
    diagnostic_names = (
        "max_balance_error_fmol",
        "max_extracellular_balance_error_fmol",
        "max_global_balance_error_fmol",
        "max_countercharge_error_C",
        "max_energy_balance_error_pJ",
    )
    for identifier in job.VARIANTS:
        for mode, step in [("jax_jit", h) for h in plan["cells_steps_s"]] + [
            ("jax_eager", plan["cells_eager_step_s"])
        ]:
            label = key(identifier, step) + "/" + mode
            rows[label] = dict(
                case=identifier,
                step_s=step,
                jit=mode == "jax_jit",
                times_s=plan["common_times_s"],
                **copy.deepcopy(points),
                diagnostics=dict.fromkeys(diagnostic_names, 0.0),
            )
        resumes[key(identifier, plan["restart_step_s"]) + "/jax_jit"] = dict(
            full_state_bitwise_equal=True, start_step=200
        )
    return dict(records=rows, resumes=resumes), preparation


@pytest.mark.parametrize(
    "change", [None, "amount", "voltage", "energy", "backend", "missing", "restart", "grid"]
)
def test_cells_checks(monkeypatch, change):
    packet, preparation = packet_fixture(monkeypatch)
    row = next(iter(packet["records"].values()))
    if change == "amount":
        row["states"][2][0] = 1.0
    elif change == "voltage":
        row["voltage_V"][2][0] = 1.0
    elif change == "energy":
        row["diagnostics"]["max_energy_balance_error_pJ"] = 2.01e-8
    elif change == "backend":
        row = next(v for v in packet["records"].values() if not v["jit"])
        row["states"][2][0] = 1e-9  # Below reference budget, above eager/JIT budget.
    elif change == "missing":
        packet["records"].pop(next(iter(packet["records"])))
    elif change == "restart":
        next(iter(packet["resumes"].values()))["start_step"] = 20
    elif change == "grid":
        row["times_s"] = row["times_s"][:-1]
    if change in ("missing", "restart", "grid"):
        with pytest.raises(ValueError):
            work.cells_checks(packet, preparation)
    else:
        result = work.cells_checks(packet, preparation)
        assert result["passed"] is (change is None)


@pytest.mark.parametrize(
    "group,finest,passes",
    [
        ("energy_balance", False, True),
        ("energy_balance", True, False),
        ("finest_limits_amount", False, True),
        ("native_live_rate_fmol_s", False, False),
        ("native_single_transfer_fmol", False, False),
    ],
)
def test_coarse_failure_policy(group, finest, passes):
    row = dict(within_finest_limits=False, failed_comparisons=1, failed_groups={"case/" + group: 1})
    assert work.required_native_pass(row, finest) is passes


def test_saved_pump_ladder():
    rows = [c.read(path, None) for path in job.reused_rows()]
    assert [r["dt_s"] for r in rows] == job.STEPS
    assert all(work.required_native_pass(r, i == 2) for i, r in enumerate(rows))
    assert rows[-1]["accounting"]["energy_pJ"] < 1e-7
    assert all(v["passed"] for v in work.refinement(rows, work.prepared()["protocol"]).values())


def test_native_dispatch(tmp_path, monkeypatch):
    package = tmp_path / "env/betse"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("# Dispatch fixture, no physics\n")
    template = tmp_path / "source/betse/data/yaml/sim_config.yaml"
    template.parent.mkdir(parents=True)
    template.write_text("{}\n")
    original = job.ctx.inherited()
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

    def run_row(preparation, variant, mode, directory, actual_package, actual_template):
        assert actual_package == package and actual_template == {}
        plan = preparation["protocol"]
        calls.append((variant["id"], plan["dt_s"], plan["duration_s"], mode))
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
    job.gate("native", result)
    assert calls == [(r["id"], r["dt_s"], r["duration_s"], r["mode"]) for r in job.SCOPE["rows"]]
    assert native.codec is codec


@pytest.mark.parametrize(
    "change", [None, "duration", "steps", "prior", "source", "receipt", "digest"]
)
def test_registration_binding(tmp_path, monkeypatch, change):
    proof = dict(path="runs/matched-software-fixture/completion.json", sha256="1" * 64)
    links = job.prerequisite_links()
    r = dict(
        schema="cells.pump_relaxation_matched@1",
        scope=copy.deepcopy(job.SCOPE),
        sources_sha256={},
        software=proof,
        prior=copy.deepcopy(links),
        runtime=job.ctx.runtime(),
    )
    if change == "duration":
        r["scope"]["rows"][0]["duration_s"] *= 2
    elif change == "steps":
        r["scope"]["native_steps_s"][0] *= 2
    elif change == "prior":
        r["prior"]["completion_sha256"] = "0" * 64
    elif change == "source":
        r["sources_sha256"]["changed.py"] = "0" * 64
    elif change == "receipt":
        r["software"] = dict(proof, sha256="0" * 64)
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
    assert calls[0][1]["env"]["JAX_ENABLE_X64"] == "true"


def test_failure_stops(tmp_path, monkeypatch):
    monkeypatch.setattr(job.helpers, "deadline", lambda _: None)
    monkeypatch.setattr(job, "authenticate", lambda *_: dict(prior={}))
    monkeypatch.setattr(job, "prerequisites", lambda: {})
    calls = []

    def fail(command, *_):
        calls.append(command)
        raise RuntimeError("intentional Cells failure")

    monkeypatch.setattr(job.helpers, "run_child", fail)
    with pytest.raises(RuntimeError, match="intentional"):
        job.execute(tmp_path, "test")
    assert len(calls) == 1 and calls[0][-3] == "cells"
    assert (tmp_path / "failure.json").is_file() and not (tmp_path / "completion.json").exists()
    assert not (tmp_path / "native.stdout.log").exists()


@pytest.mark.parametrize("failure", [None, "mapping", "fine_energy"])
def test_comparison_dispatch(tmp_path, monkeypatch, failure):
    packet, _ = packet_fixture(monkeypatch)
    packet.update(
        status="matched_cells_completed",
        trajectories=24,
        restart_suffixes=6,
        duration_s=0.01,
        checks=dict(passed=True),
    )
    job.write(tmp_path / "cells.json", packet)
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
        dict(status="matched_native_captured", native_runs=20, records=records),
    )
    calls, pairs = [], []
    saved = [c.read(path, None) for path in job.reused_rows()]

    def compare_row(directory, link, preparation, variant, write):
        assert link["id"] == variant["id"]
        assert preparation["protocol"]["duration_s"] == 0.01
        calls.append(link["role"])
        row = copy.deepcopy(saved[int(link["role"].split("/")[-1])])
        if (failure == "mapping" and link["role"] == "leak_only/0") or (
            failure == "fine_energy" and link["role"] == "pump_only/2"
        ):
            group = "native_live_rate_fmol_s" if failure == "mapping" else "energy_balance"
            row.update(
                within_finest_limits=False,
                failed_comparisons=1,
                failed_groups={link["role"] + "/" + group: 1},
            )
        return row

    def pair(left, right):
        pairs.append((str(left.relative_to(tmp_path)), str(right.relative_to(tmp_path))))
        return dict(failed_comparisons=0)

    monkeypatch.setattr(work, "compare_row", compare_row)
    monkeypatch.setattr(work.recording, "pair", pair)
    monkeypatch.setattr(work, "cross_check", lambda *_: dict(failed_comparisons=0))
    result = work.compare({}, tmp_path, job.write, lambda _: None)
    job.gate("comparison", result)
    assert len(calls) == 15 and len(pairs) == 5 and len(result["cases"]) == 6
    assert result["producer_passed"] is (failure is None)
    assert not result["matched_10ms_qualified"] and result["independent_review_pending"]


def test_cross_engine_budget():
    points = dict(states=[[0.0] * 59], voltage_V=[[0.0] * 7])
    perturbed = copy.deepcopy(points)
    perturbed["states"][0][0] = 2.01e-7
    result = work.cross_check(perturbed, points, work.prepared()["protocol"])
    assert result["failed_comparisons"] == 1
    assert result["failure_examples"][0]["budget"] == 2e-7


@pytest.mark.parametrize("passed", [True, False])
def test_controller_completion(tmp_path, monkeypatch, passed):
    monkeypatch.setattr(job.helpers, "deadline", lambda _: None)
    monkeypatch.setattr(job, "authenticate", lambda *_: dict(prior={}))
    monkeypatch.setattr(job, "prerequisites", lambda: {})
    monkeypatch.setattr(job, "budget", lambda _: None)
    phases = []

    def run_child(command, out, err, timeout):
        phase = command[-3]
        phases.append(phase)
        assert timeout == job.SCOPE["phase_timeout_seconds"][phase]
        if phase == "cells":
            packet, _ = packet_fixture(monkeypatch)
            result = dict(
                **packet,
                status="matched_cells_completed",
                trajectories=24,
                restart_suffixes=6,
                duration_s=0.01,
                checks=dict(passed=True),
            )
        elif phase == "native":
            result = dict(
                status="matched_native_captured", native_runs=20, records=job.SCOPE["rows"]
            )
            err.write(
                "[matched_job.py] Ignoring cutting event, as cut profiles are disabled.\n" * 40
            )
        else:
            result = dict(
                status="matched_comparison_completed",
                cases=dict.fromkeys(job.VARIANTS),
                producer_passed=passed,
                matched_10ms_qualified=False,
                independent_review_pending=True,
            )
        job.write(tmp_path / (phase + ".json"), result)

    monkeypatch.setattr(job.helpers, "run_child", run_child)
    job.execute(tmp_path, "fixture")
    done = c.read(tmp_path / "completion.json", None)
    assert phases == ["cells", "native", "comparison"]
    assert done["producer_passed"] is passed and not done["matched_10ms_qualified"]
    assert not (tmp_path / "failure.json").exists()
    assert c.sha(tmp_path / "comparison.json") == done["files_sha256"]["comparison.json"]


def test_cells_miss_gate():
    result = dict(
        status="matched_cells_completed",
        trajectories=24,
        records=dict.fromkeys(range(24)),
        restart_suffixes=6,
        resumes=dict.fromkeys(range(6)),
        duration_s=0.01,
        checks=dict(passed=False),
    )
    with pytest.raises(ValueError, match="Cells acceptance"):
        job.gate("cells", result)


@pytest.mark.parametrize(
    "phase,text,passes",
    [
        (
            "native",
            "[matched_job.py] Ignoring cutting event, as cut profiles are disabled.\n" * 40,
            True,
        ),
        (
            "native",
            "[refined_job.py] Ignoring cutting event, as cut profiles are disabled.\n" * 40,
            False,
        ),
        ("native", "", False),
        ("cells", "", True),
        ("comparison", "warning\n", False),
    ],
)
def test_stderr(phase, text, passes):
    if passes:
        job.stderr_check(phase, text)
    else:
        with pytest.raises(ValueError):
            job.stderr_check(phase, text)
