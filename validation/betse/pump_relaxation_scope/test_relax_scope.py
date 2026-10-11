"""Frozen-input, reference-only, scope/physics-guard and detached-control tests."""

import copy
import importlib
import json
import struct
import subprocess
import sys
from types import SimpleNamespace

import pytest
import relax_context as ctx
import relax_job as job
import relax_reference as ref

c = ctx.c


def put(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def fixture_record():
    old = ctx.inherited()
    scope = c.read(ctx.SCOPE)
    plan, cases = ctx.preparation(scope, old)
    return (
        dict(
            setting=plan["reference"]["solves"][0],
            times_s=[i * plan["reference"]["sample_dt_s"] for i in range(1600)] + [0.01],
            states=[[0.0] * 59 for _ in range(1601)],
            voltage_V=[[0.0] * 7 for _ in range(1601)],
            accepted_times_s=[0.0, 0.01],
            accepted_states=[[0.0] * 59, [0.0] * 59],
            accounting=[{}, {}],
            stats=dict(rhs_calls=2, nfev=2, njev=0, nlu=0, elapsed_seconds=0.01),
        ),
        scope,
        plan,
        cases,
    )


def test_real_r0_authentication():
    result = ctx.authenticate_r0()
    assert len(result["audit_files_sha256"]) == 70
    assert result["native"]["exact_scalar_comparisons"] == 54685116
    assert result["matrix"]["window_runs"] == 72
    assert result["unsaved_trajectories_directly_inspected"] is False


def test_only_duration_preparation_changes():
    old = ctx.inherited()
    before = copy.deepcopy(old)
    plan, cases = ctx.preparation(c.read(ctx.SCOPE), old)
    assert old == before
    assert plan == old["protocol"] | dict(
        schema="cells.pump_reference_scoping_protocol@1",
        decision="D130",
        scope="10 ms reference/domain study only; no native or Cells integration",
        duration_s=0.01,
        restart_time_s=0.005,
        common_times_s=[i * 0.00025 for i in range(41)],
    )
    assert cases == {k: v | dict(end_time_s=0.01) for k, v in old["cases"].items()}
    assert plan["accounting"]["native_finest_energy_pJ"] == 1e-7


@pytest.mark.parametrize(
    "field,value",
    [
        ("duration_s", 0.1),
        ("reference_solves", 17),
        ("native_runs", 1),
        ("cells_runs", 1),
        ("production_changed", True),
        ("equations_changed", True),
        ("scientific_tolerances_changed", True),
        ("automatic_polling", True),
        ("automatic_retry", True),
        ("automatic_followup", True),
        ("native_ladder_qualified", True),
        ("matched_10ms_qualified", True),
        ("steady_state_thresholds", {}),
        ("reference_samples_per_solve", 41),
        ("overlap_samples_per_solve", 5),
        ("reference_rhs_calls_per_solve", 300000),
        ("reference_accepted_steps_per_solve", 40960),
    ],
)
def test_scope_mutations(field, value):
    scope = c.read(ctx.SCOPE)
    scope[field] = value
    with pytest.raises(ValueError):
        ctx.validate(scope, ctx.inherited())


def test_no_changed_runtime(monkeypatch):
    monkeypatch.setattr(ctx, "runtime", lambda: {})
    with pytest.raises(ValueError, match="runtime changed"):
        ctx.validate(c.read(ctx.SCOPE), ctx.inherited())


@pytest.mark.parametrize(
    "mutation",
    [
        "drop_sample",
        "drop_state",
        "drop_voltage",
        "wrong_width",
        "nonfinite",
        "wrong_setting",
        "unordered",
        "wrong_end",
        "accepted_end",
        "accepted_coverage",
    ],
)
def test_reference_corruptions(mutation):
    row, scope, _, _ = fixture_record()
    setting = copy.deepcopy(row["setting"])
    if mutation == "drop_sample":
        row["times_s"].pop()
    if mutation == "drop_state":
        row["states"].pop()
    if mutation == "drop_voltage":
        row["voltage_V"].pop()
    if mutation == "wrong_width":
        row["states"][0].pop()
    if mutation == "nonfinite":
        row["states"][0][0] = float("nan")
    if mutation == "wrong_setting":
        row["setting"]["rtol"] *= 10
    if mutation == "unordered":
        row["times_s"][2] = 0.0
    if mutation == "wrong_end":
        row["times_s"][-1] = 0.001
    if mutation == "accepted_end":
        row["accepted_times_s"][-1] = 0.001
    if mutation == "accepted_coverage":
        row["accepted_states"].pop()
    with pytest.raises(ValueError):
        ref.fields(row, setting, scope["duration_s"], 1601)


def test_reference_fixture_complete():
    row, scope, _, _ = fixture_record()
    ref.fields(row, row["setting"], scope["duration_s"], 1601)


class Ledger:
    def __init__(self):
        self.comparisons, self.maxima = 0, {}

    def compare(self, name, actual, expected, atol):
        a, b = list(c.arrays.flatten(actual)), list(c.arrays.flatten(expected))
        c.need(len(a) == len(b), "extent")
        for x, y in zip(a, b, strict=True):
            c.need(abs(x - y) <= atol, "prefix error")
            self.comparisons += 1
            self.maxima[name] = max(self.maxima.get(name, 0.0), abs(x - y))


@pytest.mark.parametrize("mutation", ["time", "amount", "energy", "voltage"])
def test_prefix_corruption(mutation):
    row, _, plan, _ = fixture_record()
    old = {k: copy.deepcopy(row[k][:161]) for k in ("times_s", "states", "voltage_V")}
    if mutation == "time":
        row["times_s"][10] += 1e-7
    if mutation == "amount":
        row["states"][20][0] = 1e-8
    if mutation == "energy":
        row["states"][20][52] = 1e-7
    if mutation == "voltage":
        row["voltage_V"][20][0] = 1e-6
    with pytest.raises(ValueError):
        ref.overlap(row, old, plan, Ledger)


def test_adaptive_prefix_not_bitwise():
    row, _, plan, _ = fixture_record()
    old = {k: copy.deepcopy(row[k][:161]) for k in ("times_s", "states", "voltage_V")}
    row["states"][20][0] = 1e-12
    result = ref.overlap(row, old, plan, Ledger)
    assert result["compared_samples"] == 161 and result["comparisons"] == 161 * 66
    assert result["adaptive_prefix_bitwise_required"] is False


@pytest.mark.parametrize("setting", ["dop853_base", "radau_check"])
def test_longer_reference_smoke(tmp_path, setting):
    # Separate process: this suite's evidence checker never imports NumPy/SciPy.
    script = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import relax_context as ctx
import relax_reference as ref
with ref.model_fence():
    implementation = ref.implementation()
    scope = ctx.c.read(ctx.SCOPE)
    plan, cases = ctx.preparation(scope, ctx.inherited())
    setting = next(s for s in plan['reference']['solves'] if s['id'] == sys.argv[2])
    case = cases['pump_leak']
    output = Path(sys.argv[3])
    record = ref.solve_to_disk(case, setting, plan, output, ctx.previous.write, implementation)
    ref.fields(record, setting, .01, 1601)
    originals = ctx.c.read(ctx.c.LEGACY / 'reference.json', None)['records']
    original = originals['pump_leak/' + setting['id']]
    prefix = ref.overlap(record, original, plan, implementation.Ledger)
    metrics = ref.summary(case, record, plan, implementation.equations)
    assert metrics['min_concentration_mM'] > 0 and metrics['steady_state_tested'] is False
    assert prefix['compared_samples'] == 161
    ctx.previous.write(output / 'checks.json', dict(metrics=metrics, prefix=prefix))
print('reference-only smoke passed')
"""
    with (
        (tmp_path / "smoke.stdout.log").open("x") as out,
        (tmp_path / "smoke.stderr.log").open("x") as err,
    ):
        result = subprocess.run(
            [
                str(c.ROOT / ".venv/bin/python"),
                "-B",
                "-c",
                script,
                str(ctx.HERE),
                setting,
                str(tmp_path / "smoke"),
            ],
            cwd=c.ROOT,
            env=job.previous.environment(),
            stdout=out,
            stderr=err,
            timeout=25,
        )
    assert result.returncode == 0, (tmp_path / "smoke.stderr.log").read_text()
    assert (tmp_path / "smoke.stdout.log").read_text().strip() == "reference-only smoke passed"
    assert (tmp_path / "smoke.stderr.log").read_text() == ""


def test_serialized_reference_scalar_types(tmp_path):
    class RuntimeFloat(float):
        pass

    value = dict(
        accounting=[dict(energy_residual_pJ=RuntimeFloat(-0.0))], state=[RuntimeFloat(1.25)]
    )
    solver = SimpleNamespace(integrate=lambda *_: value)
    saved = ref.solve_to_disk({}, {}, {}, tmp_path / "solve", job.write, solver)
    assert type(saved["accounting"][0]["energy_residual_pJ"]) is float
    assert struct.pack("<d", saved["accounting"][0]["energy_residual_pJ"]) == struct.pack(
        "<d", -0.0
    )
    assert saved["state"] == [1.25]
    with pytest.raises(FileExistsError):
        ref.solve_to_disk({}, {}, {}, tmp_path / "solve", job.write, solver)


@pytest.mark.parametrize(
    "name",
    [
        "cells",
        "betse",
        "jax",
        "jaxlib",
        "pilot_cells",
        "pilot_native",
        "live_observer",
        "output_worker",
    ],
)
def test_worker_import_fence(name):
    with ref.model_fence(), pytest.raises(ImportError):
        importlib.import_module(name)


def test_missing_reference_cases():
    _, scope, plan, _ = fixture_record()
    with pytest.raises(ValueError, match="matrix coverage"):
        ref.record_gate(scope, plan, {})


@pytest.mark.parametrize("mutation", ["budget", "grid"])
def test_reference_matrix_refusal(mutation):
    row, scope, plan, _ = fixture_record()
    records = {
        v + "/" + s["id"]: copy.deepcopy(row) | dict(setting=s)
        for v in scope["variants"]
        for s in plan["reference"]["solves"]
    }
    first = next(iter(records.values()))
    if mutation == "budget":
        first["stats"]["rhs_calls"] = 30001
    if mutation == "grid":
        first["times_s"][10] += 1e-7
    with pytest.raises(ValueError):
        ref.record_gate(scope, plan, records)


@pytest.mark.parametrize(
    "mutation", ["material", "charge", "energy", "dissipation", "concentration", "voltage"]
)
def test_physical_summary_rejects(mutation):
    row, _, plan, cases = fixture_record()
    row["states"], row["voltage_V"] = row["states"][:1], row["voltage_V"][:1]
    row["accepted_states"], row["accounting"] = [], []
    balance = dict(material_residual_fmol=0.0, charge_residual_C=0.0, energy_residual_pJ=0.0)
    if mutation in ("material", "charge", "energy"):
        key = {
            "material": "material_residual_fmol",
            "charge": "charge_residual_C",
            "energy": "energy_residual_pJ",
        }[mutation]
        balance[key] = 1.0
    rates = [0.0] * 59
    if mutation == "dissipation":
        rates[52] = -1.0
    concentration = -1.0 if mutation == "concentration" else 1.0
    voltage = 1e10 if mutation == "voltage" else 0.0
    equations = SimpleNamespace(
        R=1.0,
        F=1.0,
        chemistry=lambda *_: 0.0,
        read_state=lambda *_: ([[concentration] * 3 for _ in range(7)], [1.0] * 3, [voltage] * 7),
        rhs=lambda *_: rates,
        accounting=lambda *_: balance,
    )
    with pytest.raises((ValueError, OverflowError)):
        ref.summary(cases["pump_leak"], row, plan, equations)


def test_measured_and_projected_resources():
    result = ctx.resource_context()
    assert (
        result["linear_10ms_projection"]["stream_bytes"]
        == 10 * result["measured_1ms"]["stream_bytes"]
    )
    assert not result["projection_is_measurement"] and not result["full_campaign_budget_approved"]
    assert result["native_histories_retained"]


def test_readiness_does_not_promote_missing_data():
    result = ctx.readiness(ctx.inherited())
    assert result["junction"]["selected_edges"] is None
    assert not result["junction"]["reciprocal_face_edge_map_present"]
    assert len(result["biology"]["blockers"]) == 6
    assert not result["biology"]["new_literature_review"]


def test_registration_binding(tmp_path):
    put(tmp_path / "registration.json", {})
    with pytest.raises(ValueError, match="registration digest"):
        job.authenticate(tmp_path, "0" * 64, full=False)


@pytest.mark.parametrize(
    "mutation",
    [
        "none",
        "horizon",
        "chemistry",
        "tolerance",
        "source",
        "runtime",
        "imports",
        "native",
        "followup",
    ],
)
def test_resealed_registration_context(tmp_path, monkeypatch, mutation):
    old, scope = ctx.inherited(), c.read(ctx.SCOPE)
    plan, cases = ctx.preparation(scope, old)
    sources = {"fixture": "1" * 64}
    monkeypatch.setattr(ctx, "sources", lambda: sources)
    monkeypatch.setattr(c, "capsule", lambda *_: None)
    r = dict(
        schema="cells.pump_reference_scope_registration@1",
        decision="D130",
        scope=scope,
        protocol=plan,
        cases=cases,
        sources_sha256=copy.deepcopy(sources),
        runtime=ctx.runtime(),
        inherited_registration_sha256=c.sha(c.LEGACY / "registration.json"),
        inherited_reference_sha256=c.sha(c.LEGACY / "reference.json"),
        reference_import_fence=list(ctx.FORBIDDEN_REFERENCE),
        native_runs=0,
        cells_runs=0,
        automatic_followup=False,
    )
    if mutation == "horizon":
        r["protocol"]["duration_s"] = 0.1
    if mutation == "chemistry":
        r["cases"]["pump_leak"]["initial_outside_mM"][0] += 1.0
    if mutation == "tolerance":
        r["protocol"]["reference"]["agreement_amount_fmol"] *= 10
    if mutation == "source":
        r["sources_sha256"]["fixture"] = "0" * 64
    if mutation == "runtime":
        r["runtime"]["python"] = "other"
    if mutation == "imports":
        r["reference_import_fence"] = []
    if mutation == "native":
        r["native_runs"] = 1
    if mutation == "followup":
        r["automatic_followup"] = True
    put(tmp_path / "registration.json", r)
    if mutation == "none":
        assert job.authenticate(tmp_path, c.sha(tmp_path / "registration.json"), full=False) == r
    else:
        with pytest.raises(ValueError):
            job.authenticate(tmp_path, c.sha(tmp_path / "registration.json"), full=False)


def test_reference_worker_complete_disjoint_matrix(tmp_path, monkeypatch):
    """Full actual dispatch with explicitly stubbed numerical work, not acceptance."""
    template, scope, plan, cases = fixture_record()
    calls = []

    def solve(case, setting, _, directory, write, solver):
        calls.append((case["id"], setting["id"], directory))
        directory.mkdir(parents=True)
        write(
            directory / "result.json", dict(physics_stubbed=True, case=case["id"], setting=setting)
        )
        return copy.deepcopy(template) | dict(setting=setting)

    solver = SimpleNamespace(
        equations=None,
        Ledger=None,
        gate=lambda _, rows: dict(status="independent_reference_gate_pass", fixture_rows=len(rows)),
    )
    monkeypatch.setattr(ref, "implementation", lambda: solver)
    monkeypatch.setattr(ref, "solve_to_disk", solve)
    monkeypatch.setattr(
        ref, "summary", lambda *_: dict(checked_states_including_repeated_endpoints=1603)
    )
    monkeypatch.setattr(ref, "overlap", lambda *_: dict(compared_samples=161, comparisons=161 * 66))
    r = dict(scope=scope, protocol=plan, cases=cases, runtime=ctx.runtime())
    result = ref.run(r, tmp_path, job.write, lambda _: None)
    assert len(calls) == len({p for _, _, p in calls}) == result["reference_solves"] == 18
    assert result["native_runs"] == result["cells_runs"] == 0
    assert result["matched_10ms_qualified"] is False
    for label, row in result["records"].items():
        assert row["path"] == "reference/" + label + "/result.json"


def test_detached_launch(tmp_path, monkeypatch):
    output = tmp_path / "capture"

    def register(p, _):
        p.mkdir()
        put(p / "registration.json", {})

    calls = []

    def popen(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(pid=123)

    monkeypatch.setattr(job, "register", register)
    monkeypatch.setattr(job.subprocess, "Popen", popen)
    ack = job.launch(output, tmp_path / "closeout")
    assert ack["status"] == "launched_detached" and not ack["automatic_polling"]
    assert calls[0][1]["start_new_session"] is True
    assert calls[0][1]["stdin"] == subprocess.DEVNULL
    assert calls[0][0][-2:] == ["--registration-sha", c.sha(output / "registration.json")]


def test_child_timeout_cleanup(monkeypatch):
    actions = []

    class Child:
        pid = 123

        def wait(self, timeout=None):
            actions.append(("wait", timeout))
            if timeout is not None:
                raise subprocess.TimeoutExpired("reference", timeout)
            return -9

    monkeypatch.setattr(job.subprocess, "Popen", lambda *_, **__: Child())
    monkeypatch.setattr(job.os, "killpg", lambda pid, sig: actions.append(("kill", pid, sig)))
    with pytest.raises(subprocess.TimeoutExpired):
        job.run_child(["reference"], None, None, 1)
    assert actions == [("wait", 1), ("kill", 123, job.signal.SIGKILL), ("wait", None)]


def test_failed_worker_does_not_complete(tmp_path, monkeypatch):
    root = tmp_path / "root"
    output = root / "runs/scope"
    output.mkdir(parents=True)
    monkeypatch.setattr(c, "ROOT", root)
    monkeypatch.setattr(job, "deadline", lambda _: None)

    def fail(*_, **__):
        raise ValueError("failed prerequisite")

    monkeypatch.setattr(job, "authenticate", fail)
    with pytest.raises(ValueError, match="failed prerequisite"):
        job.execute(output, "bad")
    assert not (output / "completion.json").exists()
    assert c.read(output / "failure.json")["automatic_retry"] is False


def test_controller_identity_and_model_absence():
    assert job.__file__ == str(ctx.HERE / "relax_job.py")
    assert not any(
        n.split(".")[0] in ("numpy", "scipy", "jax", "cells", "betse") for n in sys.modules
    )
