"""Focused regressions for the reused review/probe path; no native integration."""

import copy
import subprocess
import sys
from contextlib import nullcontext
from types import SimpleNamespace as NS

import probe_job as job
import probe_native as native
import probe_review as review
import pytest

c = job.c


@pytest.fixture
def saved():
    r = c.read(job.REFERENCE / "registration.json", None)
    row = c.read(job.REFERENCE / "reference/pump_leak/dop853_tight/result.json", None)
    constants = job.ctx.inherited()["native_preparation"]["protocol"]["constants"]
    return r, row, constants


def test_real_saved_reference(saved):
    r, row, constants = saved
    ledger = c.e.Ledger()
    result = review.row_checks(
        r["cases"]["pump_leak"], row, row["setting"], r["protocol"], constants, ledger
    )
    assert result["independent_accounting_states"] == 41 + len(row["accepted_times_s"])
    assert ledger.count > 10000


@pytest.mark.parametrize(
    "change", ["clock", "state", "voltage", "initial", "accepted", "setting", "budget"]
)
def test_reference_corruption(saved, change):
    r, row, constants = saved
    setting = copy.deepcopy(row["setting"])
    if change == "clock":
        row["times_s"][10] += 1e-8
    elif change == "state":
        row["states"][10][0] = -1000.0
    elif change == "voltage":
        row["voltage_V"][10][0] += 1e-4
    elif change == "initial":
        row["states"][0][0] = 1e-5
    elif change == "accepted":
        row["accepted_times_s"][1] = 0.0
    elif change == "setting":
        row["setting"]["rtol"] *= 10
    else:
        row["stats"]["rhs_calls"] = 30001
    with pytest.raises(ValueError):
        review.row_checks(
            r["cases"]["pump_leak"], row, setting, r["protocol"], constants, c.e.Ledger()
        )


def test_independent_energy(saved):
    r, row, constants = saved
    state = row["states"][-1]
    case = r["cases"]["pump_leak"]
    assert review.physics.physical(case, state, constants)["energy_residual_pJ"] < 2e-8
    state[52] += 1e-6
    assert review.physics.physical(case, state, constants)["energy_residual_pJ"] > 2e-8


def test_preparation():
    old = job.ctx.inherited()
    protected = copy.deepcopy(old)
    for row in job.SCOPE["rows"]:
        changed = native.preparation(old, row["dt_s"])
        plan = changed["protocol"]
        assert plan["steps"] * plan["dt_s"] == plan["duration_s"] == 0.01
        for name in ("dt_s", "duration_s", "steps"):
            plan[name] = old["native_preparation"]["protocol"][name]
        assert changed == old["native_preparation"]
    assert old == protected
    assert sum(round(0.01 / v["dt_s"]) for v in job.SCOPE["rows"]) == 17600


class Stream(list):
    complete = True


def prefix_fixture():
    initial = dict(physical={"ion": 1.0})
    steps = [
        dict(
            index=i,
            raw_label_s=i * 0.01 / 3,
            before_elapsed_s=i * 0.0005,
            after_elapsed_s=(i + 1) * 0.0005,
            after_voltage=dict(physical={"ion": float(i + 2)}),
        )
        for i in range(4)
    ]
    raw = [dict(index=i, calls=[float(i)]) for i in range(4)]
    row = dict(
        id="pump_leak",
        dt_s=0.0005,
        trace=dict(initial=initial, steps=steps, raw_steps=raw),
        histories=dict(cc_time=dict(values=[[3.0], [4.0], [5.0]])),
    )
    old_steps = copy.deepcopy(steps[:2])
    for i, value in enumerate(old_steps):
        value["raw_label_s"] = i * 0.001
    stream = Stream(
        [
            dict(
                kind="native_header",
                row=dict(id="pump_leak", dt_s=0.0005, steps=2, mode="observed"),
                trace=dict(initial=copy.deepcopy(initial)),
            )
        ]
        + [
            dict(kind="native_step", index=i, step=s, raw_step=copy.deepcopy(raw[i]))
            for i, s in enumerate(old_steps)
        ]
        + [
            dict(kind="native_history", index=0, values=dict(cc_time=[3.0], time=0.001)),
            dict(kind="native_footer", row=dict(final=copy.deepcopy(steps[1]["after_voltage"]))),
        ]
    )
    return row, stream


@pytest.mark.parametrize("change", [None, "physical", "elapsed", "history", "incomplete"])
def test_prefix(change):
    row, stream = prefix_fixture()
    if change == "physical":
        row["trace"]["steps"][1]["after_voltage"]["physical"]["ion"] += 1e-10
    elif change == "elapsed":
        row["trace"]["steps"][1]["after_elapsed_s"] += 1e-9
    elif change == "history":
        row["histories"]["cc_time"]["values"][0][0] += 1e-9
    elif change == "incomplete":
        stream.complete = False
    if change is None:
        assert native.prefix(row, stream)["steps"] == 2
    else:
        with pytest.raises(ValueError):
            native.prefix(row, stream)


def test_saved_native_decoder():
    sys.path.insert(0, str(job.HERE.parent / "native_recording"))
    import native_row

    records = c.read(c.NATIVE / "native.json", None)["records"]
    directory = c.child(c.NATIVE, records["pump_leak/dt_6.25e-06/observed"]["directory"]) / "stream"
    row = native_row.restore(c.wire.Stream(directory))
    assert native.prefix(row, c.wire.Stream(directory))["steps"] == 160


def test_numerical_miss_retained():
    sys.path.insert(0, str(job.HERE.parent / "pump_pilot_refinement"))
    import refinement_check as checker

    plan = job.ctx.inherited()["protocol"]
    points = dict(states=[[0.0] * 59], voltage_V=[[0.0] * 7])
    ledger = checker.Ledger()
    assert not native.assess(checker, ledger, points, points, dict(energy_pJ=2e-7), plan)
    assert ledger.failed_comparisons == 1 and ledger.examples[0]["budget"] == 1e-7


def test_native_dispatch(tmp_path, monkeypatch):
    package = tmp_path / "env/betse"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("# fake package for dispatch only\n")
    template = tmp_path / "source/betse/data/yaml/sim_config.yaml"
    template.parent.mkdir(parents=True)
    template.write_text("{}\n")
    old = job.ctx.inherited()
    old["native_preparation"]["upstream"]["files_sha256"] = {
        "betse/__init__.py": c.sha(package / "__init__.py")
    }
    calls = []

    def row(r, variant, mode, directory, actual_package, actual_template):
        assert variant["id"] == "pump_leak" and actual_package == package and actual_template == {}
        calls.append((r["protocol"]["dt_s"], r["protocol"]["duration_s"], mode))
        directory.mkdir(parents=True)
        job.write(directory / "capture.json", dict(steps=r["protocol"]["steps"]))
        return dict(steps=r["protocol"]["steps"])

    monkeypatch.setattr(job.ctx, "inherited", lambda: old)
    monkeypatch.setitem(sys.modules, "betse", NS(__file__=str(package / "__init__.py")))
    monkeypatch.setitem(sys.modules, "numpy", NS(errstate=lambda **_: nullcontext()))
    monkeypatch.setitem(sys.modules, "ruamel", NS())
    monkeypatch.setitem(sys.modules, "ruamel.yaml", NS(YAML=lambda **_: NS(load=lambda _: {})))
    monkeypatch.setitem(
        sys.modules,
        "live_native",
        NS(
            run_row=row,
            ctx=NS(NATIVE_PYTHON=tmp_path / "env/bin/python"),
            prior=NS(
                c=NS(
                    SOURCE=tmp_path / "source",
                    environment=lambda: dict(packages={}),
                    locked_reference_packages=lambda: {},
                )
            ),
        ),
    )
    result = native.capture(dict(scope=job.SCOPE), tmp_path / "capture", job.write, lambda _: None)
    assert result["native_runs"] == len(calls) == 4
    assert [dict(dt_s=h, mode=m) for h, t, m in calls] == job.SCOPE["rows"]
    assert all(t == 0.01 for _, t, _ in calls)


def test_registration_tamper(tmp_path):
    job.write(tmp_path / "registration.json", dict(scope=job.SCOPE))
    with pytest.raises(ValueError, match="registration identity"):
        job.authenticate(tmp_path, "0" * 64)


def test_launch_detached(tmp_path, monkeypatch):
    def register(output, _):
        output.mkdir()
        job.write(output / "registration.json", {})

    calls = []
    monkeypatch.setattr(job, "register", register)
    monkeypatch.setattr(
        job.subprocess, "Popen", lambda *a, **k: calls.append((a, k)) or NS(pid=123)
    )
    result = job.launch(tmp_path / "job", tmp_path / "software")
    assert result["pid"] == 123 and result["automatic_polling"] is False
    assert calls[0][1]["start_new_session"] is True and calls[0][1]["stdin"] == subprocess.DEVNULL


def test_phase_failure_stops(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(job.previous, "deadline", lambda _: None)
    monkeypatch.setattr(job, "authenticate", lambda *_: {})
    monkeypatch.setattr(job, "reference", lambda: None)

    def fail(command, *_):
        calls.append(command)
        raise RuntimeError("intentional review failure")

    monkeypatch.setattr(job.previous, "run_child", fail)
    with pytest.raises(RuntimeError, match="intentional"):
        job.execute(tmp_path, "test")
    assert len(calls) == 1 and calls[0][-3] == "review"
    assert (tmp_path / "failure.json").is_file() and not (tmp_path / "completion.json").exists()
    assert not (tmp_path / "native.stdout.log").exists()


@pytest.mark.parametrize(
    "text",
    [
        "",
        "[betse] Ignoring cutting event, as cut profiles are disabled.\n" * 8,
        "[probe_job.py] Ignoring cutting event, as cut profiles are disabled.\n" * 7,
        "unexpected warning\n",
    ],
)
def test_stderr_rejects_unexpected(text):
    with pytest.raises(ValueError):
        job.stderr_check("native", text)


def test_stderr_known_notice():
    job.stderr_check(
        "native", "[probe_job.py] Ignoring cutting event, as cut profiles are disabled.\n" * 8
    )
    job.stderr_check("review", "")


def test_review_import_fence():
    code = (
        "import sys; sys.path.insert(0, " + repr(str(job.HERE)) + "); "
        "import probe_job, probe_review; "
        "exec('with probe_review.e.model_fence():\\n import coupled_reference')"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", code],
        text=True,
        capture_output=True,
        timeout=15,
        env=job.previous.previous.environment(),
    )
    assert result.returncode != 0 and "Forbidden in independent" in result.stderr
