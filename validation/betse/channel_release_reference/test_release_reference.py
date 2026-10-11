"""Short synthetic integration, corruption and detached-job tests, not the campaign."""

import ast
import copy
import importlib
import math
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ctx = importlib.import_module("piecewise_context")
ref = importlib.import_module("piecewise_reference")
check = importlib.import_module("piecewise_check")
job = importlib.import_module("piecewise_job")


def fixture_inputs():
    plan = copy.deepcopy(ctx.c.read(ctx.PLAN))
    data = ctx.inputs(plan)
    plan.update(duration_s=2e-6, block_time_s=0.5e-6, release_time_s=1e-6, sample_dt_s=0.25e-6)
    for p in data["parameters"].values():
        for name, value in p.items():
            if isinstance(value, list):
                p[name] = value[:1]
    for schedule in data["schedules"].values():
        for row in schedule:
            row["time"] *= 0.001
    return {"plan": plan, "inputs": data}


@pytest.fixture(scope="module")
def short(tmp_path_factory):
    output = tmp_path_factory.mktemp("piecewise-short")
    r = fixture_inputs()
    ctx.io.write(output / "fixture.json", r)
    script = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import piecewise_context as ctx
import piecewise_reference as ref
import piecewise_job as job
output = Path(sys.argv[2])
sys.meta_path.insert(0, job.SimulatorFence())
result = ref.worker(ctx.c.read(output / 'fixture.json'), output)
ctx.io.write(output / 'aggregate.json', result)
"""
    subprocess.run(
        [str(ctx.feedback.REFERENCE_PYTHON), "-B", "-c", script, str(HERE), str(output)],
        check=True,
        capture_output=True,
        text=True,
        timeout=40,
    )
    aggregate = ctx.c.read(output / "aggregate.json")
    return r, output, aggregate


def row_case(short, history="a", condition="suppression_release", method="dop853_tight"):
    r, output, aggregate = short
    key = f"{history}/{condition}/{method}"
    row = ctx.io.read_compressed(output / aggregate["records"][key])
    ledger = ctx.io.Ledger(
        r["inputs"]["reference"]["comparison_absolute"]
        | {"gate_rate_per_s": 2e-9, "power_pJ_per_s": 2e-7}
    )
    dense = ctx.io.Ledger({"state": 5e-13}, 2e-13)
    return r, row, ledger, dense, key


def validate(r, row, ledger, dense, key):
    history, condition, method = key.split("/")
    data = r["inputs"]
    setting = next(s for s in data["reference"]["solves"] if s["id"] == method)
    check.validate_record(
        row,
        data["parameters"][history],
        r["plan"]["histories"][history],
        data["schedules"][condition],
        setting,
        r["plan"],
        data["reference"],
        ledger,
        dense,
        key,
    )


def test_registered_scope_and_inherited_settings():
    plan = ctx.c.read(ctx.PLAN)
    ctx.validate_plan(plan)
    data = ctx.inputs(plan)
    assert len(plan["histories"]) * len(plan["conditions"]) * len(data["reference"]["solves"]) == 24
    assert (
        sum(len(ref.segments(s, plan["duration_s"])) for s in data["schedules"].values()) * 6 == 48
    )
    assert len(ref.sample_times(plan["duration_s"], plan["sample_dt_s"])) == 321
    assert all(x > 0 for p in data["parameters"].values() for x in p["Pmax_m_per_s"])
    assert data["reference"] == ctx.design.view("a")["protocol"]["reference"]
    assert len(ref.base.initial_state(data["parameters"]["a"])) == 28


@pytest.mark.parametrize(
    "field,value",
    [
        ("simulator_execution_allowed", True),
        ("production_changed", True),
        ("automatic_polling", True),
        ("automatic_retry", True),
        ("automatic_followup", True),
        ("duration_s", 0.003),
        ("block_time_s", 0.0006),
        ("segment_integrations", 72),
        ("reference_paths", 12),
        ("gpu_tested", True),
        ("extra", 0),
    ],
)
def test_changed_plan_rejected(field, value):
    plan = copy.deepcopy(ctx.c.read(ctx.PLAN))
    plan[field] = value
    with pytest.raises(ValueError):
        ctx.validate_plan(plan)


@pytest.mark.parametrize("u", [True, False, None, "0", -0.01, 1.01, math.nan, math.inf])
def test_bad_availability_rejected(u):
    with pytest.raises(ValueError):
        ref.availability(u)
    with pytest.raises(ValueError):
        check.effective({}, u)


@pytest.mark.parametrize("starts", [[0, 0], [0, -1], [0, 2], [0.1], [0, math.nan], [0, math.inf]])
def test_bad_switches_rejected(starts):
    with pytest.raises(ValueError):
        ref.segments([{"time": t, "availability": 1} for t in starts], 2)


@pytest.mark.parametrize("u", [0, 0.25, 1])
@pytest.mark.parametrize("history", ["a", "b"])
def test_transport_scales_but_gate_and_state_do_not(u, history):
    data = ctx.inputs(ctx.c.read(ctx.PLAN))
    p = data["parameters"][history]
    p0 = copy.deepcopy(p)
    state = ref.base.initial_state(p, {"a": [0.2, 0.6], "b": [0.6, 0.2]}[history])
    state[0] = -1e-6
    original = state.copy()
    active = ref.derivative(p, state, 1)
    blocked = ref.derivative(p, state, u)
    independent = check.rhs(p, state, u)
    n = len(p["volume_pL"])
    assert blocked[n : 3 * n] == active[n : 3 * n]
    assert blocked[:n] == [u * x for x in active[:n]]
    assert blocked[3 * n :] == [u * x for x in active[3 * n :]]
    assert blocked == pytest.approx(independent, abs=2e-12, rel=2e-11)
    assert state == original and p == p0
    assert ref.readout(p, state, u)["gate"] == ref.readout(p, state, 1)["gate"]


def test_real_short_solvers_and_saved_checker(short):
    r, output, aggregate = short
    result = check.check(r, output, aggregate)
    assert aggregate["reference_paths"] == 24 and aggregate["segment_integrations"] == 48
    assert aggregate["simulator_imports"] == []
    assert result["comparison"]["failed_comparisons"] == 0
    assert result["dense_replay"]["failed_comparisons"] == 0
    # A deliberately microscopic software fixture cannot qualify the registered 2 ms signal.
    assert result["signal"]["pass"] is False
    assert result["status"] == "fail" and result["simulator_execution_allowed"] is False


@pytest.mark.parametrize("method", ["dop853_base", "dop853_tight", "radau_check"])
@pytest.mark.parametrize(
    "condition", ["baseline", "no_op", "static_blocked", "suppression_release"]
)
def test_short_records_keep_exact_switch_and_block_carry(short, method, condition):
    r, row, ledger, dense, key = row_case(short, condition=condition, method=method)
    validate(r, row, ledger, dense, key)
    assert ledger.failed == dense.failed == 0
    for switch in row["switches"]:
        assert switch["state_before"] == switch["state_after"]
        n = len(r["inputs"]["parameters"]["a"]["volume_pL"])
        assert switch["left_rhs"][n : 3 * n] == switch["right_rhs"][n : 3 * n]
    if condition == "suppression_release":
        block, release = row["switches"]
        assert block["left_readout"]["flux_fmol_per_s"] != [0.0]
        assert block["right_readout"]["flux_fmol_per_s"] == [0.0]
        assert release["left_readout"]["flux_fmol_per_s"] == [0.0]
        assert release["right_readout"]["flux_fmol_per_s"] != [0.0]
        assert (
            row["segments"][1]["accepted_states"][0][1:3]
            != row["segments"][1]["accepted_states"][-1][1:3]
        )


@pytest.mark.parametrize(
    "corruption",
    [
        "carry_q",
        "carry_gate",
        "carry_energy",
        "block_flux",
        "gate_reset",
        "switch_side",
        "switch_state",
        "left_rhs",
        "dense_coefficient",
        "cross_switch",
        "missing_switch",
        "sample_clock",
        "sample_state",
        "bath",
        "sample_flux",
        "solver_failure",
        "budget",
        "initial_gate",
        "nan_coefficient",
        "axes",
    ],
)
def test_saved_corruptions_rejected(short, corruption):
    r, row, ledger, dense, key = row_case(short)
    if corruption.startswith("carry_"):
        i = {"carry_q": 0, "carry_gate": 1, "carry_energy": 3}[corruption]
        row["segments"][1]["accepted_states"][0][i] += 1e-8
    elif corruption == "block_flux":
        row["segments"][1]["accepted_states"][-1][0] += 1e-8
    elif corruption == "gate_reset":
        row["segments"][1]["accepted_states"][-1][1] = 0.2
    elif corruption == "switch_side":
        row["switches"][0]["right_readout"] = row["switches"][0]["left_readout"]
    elif corruption == "switch_state":
        row["switches"][0]["state_after"][1] += 1e-8
    elif corruption == "left_rhs":
        row["switches"][0]["left_rhs"][1] += 0.01
    elif corruption in ("dense_coefficient", "nan_coefficient"):
        row["segments"][0]["dense_intervals"][0]["coefficients"][0][0] += (
            math.nan if corruption == "nan_coefficient" else 1e-5
        )
    elif corruption == "cross_switch":
        row["segments"][0]["dense_intervals"][-1]["right_s"] = 1e-6
    elif corruption == "missing_switch":
        row["switches"].pop()
    elif corruption == "sample_clock":
        row["sample_times_s"][1] += 1e-10
    elif corruption == "sample_state":
        row["sample_states"][1][1] += 1e-6
    elif corruption == "bath":
        row["readouts"][1]["bath_K_fmol"] += 1e-5
    elif corruption == "sample_flux":
        row["readouts"][2]["flux_fmol_per_s"][0] = 0.01
    elif corruption == "solver_failure":
        row["segments"][0]["stats"]["success"] = False
    elif corruption == "budget":
        row["stats"]["rhs_calls_including_jacobian"] = 999999
    elif corruption == "initial_gate":
        row["initial_gate"] = [0.6, 0.2]
    elif corruption == "axes":
        row["state_axes"]["order"].reverse()
    try:
        validate(r, row, ledger, dense, key)
    except ValueError:
        return
    assert ledger.failed + dense.failed > 0, corruption


def test_no_cross_boundary_dense_read(short):
    _, row, _, _, _ = row_case(short)
    with pytest.raises(ValueError, match="Cross-boundary"):
        check.state_in_segment(row["segments"][0], 1e-6)
    assert check.segment_at(row, 0.5e-6) is row["segments"][1]
    assert check.segment_at(row, 1e-6) is row["segments"][2]


def test_reference_rhs_budget_is_live_in_the_solver(tmp_path):
    r = fixture_inputs()
    r["inputs"]["reference"]["max_rhs_calls_per_solve"] = 1
    ctx.io.write(tmp_path / "fixture.json", r)
    script = """
import sys
sys.path.insert(0, sys.argv[1])
import piecewise_context as c
import piecewise_reference as r
p = c.c.read(sys.argv[2])
try:
    r.integrate(p['inputs']['parameters']['a'], [.2,.6], p['inputs']['schedules']['no_op'],
                p['inputs']['reference']['solves'][0], p['plan'], p['inputs']['reference'])
except ValueError as error:
    assert 'RHS budget' in str(error)
else:
    raise AssertionError('Missing RHS cap')
"""
    subprocess.run(
        [
            str(ctx.feedback.REFERENCE_PYTHON),
            "-B",
            "-c",
            script,
            str(HERE),
            str(tmp_path / "fixture.json"),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )


@pytest.mark.parametrize("root", ["cells", "betse", "jax", "jaxlib"])
def test_worker_fence_blocks_simulators(root):
    with pytest.raises(RuntimeError):
        job.SimulatorFence().find_spec(root + ".anything")


def test_prerequisite_authenticates_without_replay():
    with ctx.model_fence():
        saved = ctx.prerequisite()
    assert len(saved["files_sha256"]) == 10
    assert saved["files_sha256"]["completion.json"] == ctx.PRIOR_SHA


def test_existing_output_refused_before_prerequisite(tmp_path, monkeypatch):
    monkeypatch.setattr(
        ctx, "prerequisite", lambda: pytest.fail("must reject before authentication")
    )
    with pytest.raises(ValueError, match="fresh"):
        job.register(tmp_path, tmp_path / "test.xml")


def test_incomplete_software_receipt_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(ctx, "ROOT", tmp_path)
    (tmp_path / "reports").mkdir()
    path = tmp_path / "reports/test.xml"
    path.write_text(
        '<testsuite tests="1" failures="1"><testcase classname="x" name="y">'
        "<failure/></testcase></testsuite>"
    )
    with pytest.raises(ValueError):
        ctx.test_receipt(path)


def test_detached_launcher_does_not_poll_or_wait(tmp_path, monkeypatch):
    r = {"plan": ctx.c.read(ctx.PLAN)}
    monkeypatch.setattr(job, "register", lambda *_: r)
    monkeypatch.setattr(ctx.c, "sha", lambda *_: "registered")
    commands = []

    class Process:
        pid = 314159

        def __init__(self, command, **kwargs):
            commands.append((command, kwargs))

        def poll(self):
            pytest.fail("No polling")

        def wait(self):
            pytest.fail("No waiting")

    monkeypatch.setattr(job.subprocess, "Popen", Process)
    result = job.launch(tmp_path, tmp_path / "tests.xml")
    assert result["pid"] == 314159 and result["automatic_polling"] is False
    assert commands[0][1]["start_new_session"] is True
    assert commands[0][0][-2:] == ["execute", str(tmp_path)]
    assert result["simulator_execution_allowed"] is False


def test_failed_reference_is_durable_and_cannot_start_simulators(tmp_path, monkeypatch):
    def rejected(_):
        raise ValueError("synthetic authentication rejection")

    monkeypatch.setattr(ctx, "authenticate", rejected)
    monkeypatch.setattr(job.resource, "setrlimit", lambda *_: None)
    monkeypatch.setattr(
        job.subprocess, "run", lambda *_a, **_k: pytest.fail("Must not run a worker")
    )
    with pytest.raises(ValueError, match="synthetic"):
        job.execute(tmp_path)
    assert not (tmp_path / "completion.json").exists()
    failed = ctx.c.read(tmp_path / "failure.json")
    assert failed["stage"] == "authentication" and failed["automatic_retry"] is False
    assert failed["simulator_execution_allowed"] is False


def test_worker_provenance_and_warnings_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(ctx.c, "sha", lambda *_: "registered")
    r = {"reference_runtime": {"packages": {}, "python": "3.13.5"}, "plan": ctx.c.read(ctx.PLAN)}
    ctx.io.write(
        tmp_path / "reference.json", {"registration_sha256": "registered", "warnings": ["bad"]}
    )
    with pytest.raises(ValueError):
        job.validate_worker(r, tmp_path)


def test_sources_have_no_production_entrypoint():
    for name in ("piecewise_reference.py", "piecewise_check.py", "piecewise_job.py"):
        source = (HERE / name).read_text()
        tree = ast.parse(source)
        imports = {
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        imports |= {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        assert not imports & {"cells", "betse", "jax", "jaxlib"}
        assert "pickle.load" not in source
    assert "solve_ivp(" not in (HERE / "piecewise_check.py").read_text()


def test_worker_call_cannot_select_a_simulator():
    tree = ast.parse((HERE / "piecewise_job.py").read_text())
    launch = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "launch")
    assert all(
        not isinstance(n, ast.Attribute) or n.attr not in {"poll", "wait", "sleep"}
        for n in ast.walk(launch)
    )
    assert "--kind" not in (HERE / "piecewise_job.py").read_text()
    assert job.FORBIDDEN == {"cells", "betse", "jax", "jaxlib"}


@pytest.mark.parametrize("part", ["start", "switch", "final"])
def test_single_ulp_boundary_sample_corruption_rejected(short, part):
    r, row, ledger, dense, key = row_case(short)
    index = {"start": 0, "switch": 2, "final": -1}[part]
    row["sample_states"][index][1] = math.nextafter(row["sample_states"][index][1], math.inf)
    with pytest.raises(ValueError, match="exact.*carry"):
        validate(r, row, ledger, dense, key)


@pytest.mark.parametrize(
    "bad", ["gate_low", "gate_high", "voltage", "bath", "amount", "nonfinite", "extent"]
)
def test_reference_domain_rejects_bad_state(bad):
    p = ctx.inputs(ctx.c.read(ctx.PLAN))["parameters"]["a"]
    state = ref.base.initial_state(p)
    n = len(p["volume_pL"])
    if bad == "gate_low":
        state[n] = -0.001
    elif bad == "gate_high":
        state[n] = 1.001
    elif bad == "voltage":
        state[0] = 0.061 * p["area_m2"][0] * p["cm_F_per_m2"] / (p["F"] * 1e-15)
    elif bad == "bath":
        state[0] = p["outside_K_fmol"]
    elif bad == "amount":
        state[0] = -p["initial_K_fmol"][0]
    elif bad == "nonfinite":
        state[0] = math.nan
    elif bad == "extent":
        state.pop()
    with pytest.raises(ValueError):
        ref.derivative(p, state, 1)
    with pytest.raises(ValueError):
        check.readout(p, state, 1)


def signal_fixture():
    plan = ctx.c.read(ctx.PLAN)
    data = ctx.inputs(plan)
    records = {}
    for h in plan["histories"]:
        for setting in data["reference"]["solves"]:
            points = [
                {"voltage_V": [v], "gate": [[m], [0.6]], "flux_fmol_per_s": [0.01]}
                for v, m in ((0, 0.2), (-0.001, 0.21), (-0.001, 0.22), (-0.002, 0.23))
            ]
            release = {"sample_times_s": [0, 0.0005, 0.001, 0.002], "readouts": points}
            baseline = copy.deepcopy(release)
            baseline["readouts"][2]["voltage_V"] = [-0.002]
            records[f"{h}/baseline/{setting['id']}"] = baseline
            records[f"{h}/suppression_release/{setting['id']}"] = release
    return plan, data, records


def test_prospective_signal_can_pass_without_a_history_contrast():
    plan, data, records = signal_fixture()
    before = copy.deepcopy((plan, data, records))
    result = check.signal_gate(plan, data, records)
    assert result["pass"] is True and result["positive_history_effect_required"] is False
    assert (plan, data, records) == before


@pytest.mark.parametrize(
    "metric", ["block_effect", "post_release_change", "release_flux", "block_gate_change"]
)
def test_any_one_solver_history_or_metric_can_stop_the_signal_gate(metric):
    plan, data, records = signal_fixture()
    release = records["b/suppression_release/radau_check"]["readouts"]
    if metric == "block_effect":
        records["b/baseline/radau_check"]["readouts"][2]["voltage_V"] = release[2]["voltage_V"]
    elif metric == "post_release_change":
        release[-1]["voltage_V"] = release[2]["voltage_V"]
    elif metric == "release_flux":
        release[2]["flux_fmol_per_s"] = [0]
    else:
        release[2]["gate"] = release[1]["gate"]
    result = check.signal_gate(plan, data, records)
    assert result["pass"] is False
    assert result["by_history"]["b"][metric]["pass"] is False
    assert result["window_extended"] is False and plan["duration_s"] == 0.002


def test_signal_uncertainty_uses_magnitude_not_only_absolute_budget():
    plan, data, records = signal_fixture()
    for row in records.values():
        for point in row["readouts"]:
            point["flux_fmol_per_s"] = [10.0]
    result = check.signal_gate(plan, data, records)
    observed = result["by_history"]["a"]["release_flux"]
    assert observed["relative_uncertainty_magnitude_bound"] == 10
    assert observed["required_minimum"] == plan["signal"]["minimum_release_flux_fmol_per_s"] + 2 * (
        data["reference"]["comparison_absolute"]["flux_fmol_per_s"]
        + 10 * data["comparison_relative"]
    )


@pytest.mark.parametrize("field", ["records", "reference_paths", "segment_integrations"])
def test_incomplete_reference_coverage_rejected_before_reading_records(short, field, tmp_path):
    r, _output, aggregate = short
    aggregate = copy.deepcopy(aggregate)
    aggregate[field] = {} if field == "records" else 0
    with pytest.raises(ValueError, match="coverage"):
        check.check(r, tmp_path, aggregate)


def test_frozen_capsule_and_registration_reject_source_and_packet_mutation(tmp_path, monkeypatch):
    import zipfile

    monkeypatch.setattr(ctx, "ROOT", tmp_path)
    source = tmp_path / "source.py"
    source.write_text("# immutable test fixture\n")
    r = {
        "schema": "cells.betse_release_reference_registration@1",
        "plan": {},
        "prerequisite": {},
        "inputs": {},
        "reference_runtime": {},
        "sources_sha256": {"source.py": ctx.c.sha(source)},
        "historical_reports_sha256": {},
        "tests": {"path": "tests.xml"},
    }
    monkeypatch.setattr(ctx, "validate_plan", lambda _: None)
    monkeypatch.setattr(ctx, "prerequisite", lambda: {})
    monkeypatch.setattr(ctx, "inputs", lambda _: {})
    monkeypatch.setattr(ctx.feedback, "reference_runtime", lambda: {})
    monkeypatch.setattr(ctx, "sources", lambda: {"source.py": ctx.c.sha(source)})
    monkeypatch.setattr(ctx, "reports", lambda: {})
    monkeypatch.setattr(ctx, "test_receipt", lambda _: {"path": "tests.xml"})
    ctx.io.write(tmp_path / "registration.json", r)
    with zipfile.ZipFile(tmp_path / "sources.zip", "x") as archive:
        archive.write(source, "source.py")
    assert ctx.authenticate(tmp_path) == r
    source.write_text("# deliberately changed fixture\n")
    with pytest.raises(ValueError, match="sources changed"):
        ctx.authenticate(tmp_path)


@pytest.mark.parametrize("outcome", ["pass", "fail", "timeout"])
def test_controller_stops_after_reference_with_durable_receipt(tmp_path, monkeypatch, outcome):
    r = {"plan": ctx.c.read(ctx.PLAN), "tests": {"tests": 1}}
    r["plan"]["resources"]["cpu_affinity"] = sorted(job.os.sched_getaffinity(0))
    real_read = ctx.c.read
    monkeypatch.setattr(ctx.c, "read", lambda p: r["plan"] if p == ctx.PLAN else real_read(p))
    monkeypatch.setattr(ctx, "authenticate", lambda _: r)
    monkeypatch.setattr(job.resource, "setrlimit", lambda *_: None)
    monkeypatch.setattr(job, "validate_worker", lambda *_: {"records": {}})
    monkeypatch.setattr(
        check, "check", lambda *_: {"status": outcome, "simulator_execution_allowed": False}
    )
    commands = []
    for name in ("registration.json", "sources.zip", *ctx.OPERATIONAL):
        (tmp_path / name).write_text("test fixture\n")

    def run(command, **kwargs):
        commands.append(command)
        assert kwargs["timeout"] == 480
        assert command[0] == str(ctx.feedback.REFERENCE_PYTHON)
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(command, 480)
        ctx.io.write(tmp_path / "reference.json", {})

    monkeypatch.setattr(job.subprocess, "run", run)
    if outcome == "pass":
        job.execute(tmp_path)
        done = real_read(tmp_path / "completion.json")
        assert done["status"] == "piecewise_reference_pass_pending_review"
        assert done["simulator_execution_allowed"] is False
        assert set(done["files_sha256"]) == {
            "registration.json",
            "sources.zip",
            "started.json",
            "reference.log",
            "reference.json",
            "reference-gate.json",
        }
        assert not (tmp_path / "failure.json").exists()
    else:
        with pytest.raises((ValueError, subprocess.TimeoutExpired)):
            job.execute(tmp_path)
        assert not (tmp_path / "completion.json").exists()
        assert real_read(tmp_path / "failure.json")["automatic_followup"] is False
    assert len(commands) == 1
