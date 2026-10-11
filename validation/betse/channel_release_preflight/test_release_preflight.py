"""Short software/native-smoke checks; the full registered panel remains detached."""

import copy
import importlib
import json
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ctx = importlib.import_module("release_context")
inputs = importlib.import_module("release_input")
checker = importlib.import_module("release_check")
job = importlib.import_module("release_job")


@pytest.fixture(scope="module")
def registration():
    return {"plan": ctx.c.read(ctx.PLAN), "data": ctx.data()}


def test_plan_counts_and_unchanged_design(registration):
    p = registration["plan"]
    ctx.validate_plan(p)
    assert p["geometry_seeds"] == 6
    assert p["fresh_phases"] == 144
    assert p["single_updates"] == p["input_applications"] == 288
    assert p["observer_pairs"] == 72
    assert p["resources"]["total_timeout_seconds"] == 480
    assert p["resources"]["max_artifact_bytes"] == 256 * 1024**2


@pytest.mark.parametrize(
    "field",
    [
        "protocol_query_time_is_simulated_elapsed_time",
        "full_simulator_loop_executed",
        "cells_trajectory_executed",
        "reference_integration_executed",
        "release_response_qualified",
        "production_changed",
        "automatic_polling",
        "automatic_retry",
        "automatic_followup",
    ],
)
def test_expanded_scope_rejected(registration, field):
    plan = copy.deepcopy(registration["plan"])
    plan[field] = True
    with pytest.raises(ValueError):
        ctx.validate_plan(plan)


@pytest.mark.parametrize(
    "field,value",
    [
        ("single_updates", 72),
        ("input_applications", 144),
        ("histories", ["a"]),
        ("native_steps_s", [0.0001]),
        ("protocol_query_times_s", [0, 0.001, 0.003]),
        ("geometry_seeds", True),
        ("extra", False),
    ],
)
def test_changed_panel_rejected(registration, field, value):
    plan = copy.deepcopy(registration["plan"])
    plan[field] = value
    with pytest.raises(ValueError):
        ctx.validate_plan(plan)


def test_design_and_paired_evidence_authenticate_without_models():
    source = (
        f"import sys; sys.path.insert(0,{str(HERE)!r})\n"
        "import release_context as c\n"
        "with c.audit.model_fence():\n"
        " d=c.design_evidence(); p=c.design.prerequisite()\n"
        " assert d['manifest']['tests']['passed']==107\n"
        " assert len(p['audit_files_sha256'])==10\n"
        " import release_input,release_check\n"
        "print('model_free_ok')\n"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", source], text=True, capture_output=True, timeout=15, check=True
    )
    assert result.stdout.strip() == "model_free_ok"


def test_changed_design_manifest_anchor_is_rejected(monkeypatch):
    monkeypatch.setattr(ctx, "MANIFEST_SHA256", "0" * 64)
    with pytest.raises(ValueError, match="manifest changed"):
        ctx.design_evidence()


@pytest.mark.parametrize("history", ["a", "b"])
@pytest.mark.parametrize("step", [25e-6, 12.5e-6, 6.25e-6])
def test_original_captured_initial_states_and_labels_are_explicit(registration, history, step):
    data = registration["data"][history]
    initial = data["saved_initial"][f"{step:.8g}"]
    labels = data["saved_labels"][f"{step:.8g}"]
    assert len(labels) == round(0.002 / step)
    assert labels[-1] == 0.002
    assert labels[1] != step
    assert initial["channel"]["m"] == [data["initial_gate"][0]] * 30
    assert initial["channel"]["h"] == [data["initial_gate"][1]] * 30
    assert initial["channel"]["P"] is None


@pytest.mark.parametrize("value", [-0.1, 1.01, True, float("nan"), float("inf"), "1"])
def test_invalid_input_rejected_before_parameter_write(value):
    channel = SimpleNamespace(maxDm=7.5e-17, m=[0.2], h=[0.6])
    before = copy.deepcopy(vars(channel))
    with pytest.raises(ValueError):
        inputs.AvailabilityInput(7.5e-17).apply(channel, value)
    assert vars(channel) == before


def test_absolute_input_is_immutable_and_restores_zero_without_changing_gates():
    channel = SimpleNamespace(maxDm=7.5e-17, m=[0.2], h=[0.6], flux=[-0.002])
    controller = inputs.AvailabilityInput(7.5e-17)
    for value in (1, 0, 0, 1, 0.25, 1):
        record = controller.apply(channel, value)
        assert record["applied_maxDm_m2_per_s"] == 7.5e-17 * value
        assert channel.m == [0.2] and channel.h == [0.6] and channel.flux == [-0.002]
    with pytest.raises(FrozenInstanceError):
        controller.baseline_maxDm = 0


def fake_phase():
    core = SimpleNamespace(m=np.array([0.2]), h=np.array([0.6]))
    channel = SimpleNamespace(maxDm=7.5e-17, channel_core=core, table=np.array([1, 2]))
    network = SimpleNamespace(channels={"Kv1p5_contact": channel}, extra_J_mem=np.array([2.0]))
    sim = SimpleNamespace(molecules=SimpleNamespace(core=network), cc_cells=np.array([[3.0]]))
    return SimpleNamespace(
        sim=sim, cells=SimpleNamespace(area=np.array([1.0])), p=SimpleNamespace()
    )


def test_numeric_inventory_excludes_only_input_and_detects_hidden_state_change():
    phase = fake_phase()
    before = inputs.numeric_inventory(phase)
    channel = inputs.old.channel(phase.sim)
    inputs.AvailabilityInput(channel.maxDm).apply(channel, 0)
    assert inputs.numeric_inventory(phase) == before
    channel.channel_core.m[0] = 0.0
    assert inputs.numeric_inventory(phase) != before
    assert before["excluded_input"] == "channel/maxDm"
    assert "gates/m" in before["numeric"]
    assert "geometry/area" in before["numeric"]


def test_reused_or_occupied_observer_is_rejected_without_replacing_hook(tmp_path):
    phase = fake_phase()
    watch = inputs.StepObserver(phase, tmp_path)
    watch.events.append("already_used")
    with pytest.raises(ValueError):
        watch.__enter__()
    assert sys.getprofile() is None


def test_observer_restores_hook_when_native_work_raises(tmp_path):
    watch = inputs.StepObserver(fake_phase(), tmp_path)
    with pytest.raises(RuntimeError, match="native test failure"):
        with watch:
            raise RuntimeError("native test failure")
    assert sys.getprofile() is None
    assert watch.result()["hook_restored"]


def test_failed_single_update_retains_completed_boundaries(monkeypatch, tmp_path):
    phase = fake_phase()
    network = phase.sim.molecules.core
    network.clear_run_loop = lambda sim: None

    def fail(phase):
        raise RuntimeError("native test failure")

    network.run_loop_channels = fail
    monkeypatch.setattr(inputs.old, "snapshot", lambda sim: {"test_only": "saved_boundary"})
    record = {}
    with pytest.raises(RuntimeError, match="native test failure"):
        inputs.single_update(phase, tmp_path, "unobserved", 0.0, record=record)
    assert set(record) == {"before", "after_clear"}
    assert record["before"] == record["after_clear"] == {"test_only": "saved_boundary"}


@pytest.fixture(scope="module")
def actual_smoke(registration, tmp_path_factory):
    output = tmp_path_factory.mktemp("release-native-software-smoke")
    ctx.io.write(output / "input.json", registration)
    selections = [("a", 25e-6, "suppression_release", 1), ("b", 6.25e-6, "suppression_release", 2)]
    source = (
        f"import sys; sys.path.insert(0,{str(HERE)!r})\n"
        "from pathlib import Path\n"
        "import release_context as c,release_native as n\n"
        "out=Path(sys.argv[1]); r=c.c.read(out/'input.json')\n"
        f"result=n.worker(r,out,selections={selections!r})\n"
        "c.io.write(out/'smoke.json',result)\n"
    )
    environment = job.environment_of(registration["data"]["a"]["preparation_registration"], output)
    with (output / "native.log").open("x") as stream:
        process = subprocess.run(
            [str(ctx.c.REFERENCE_PYTHON), "-B", "-c", source, str(output)],
            env=environment,
            stdout=stream,
            stderr=subprocess.STDOUT,
            timeout=30,
        )
    assert process.returncode == 0, (output / "native.log").read_text()[-10000:]
    native = ctx.c.read(output / "smoke.json")
    return output, native


def test_actual_native_subset_counts_and_no_full_loop(actual_smoke):
    _, native = actual_smoke
    assert native["test_only_subset"]
    assert native["geometry_seeds"] == 2
    assert native["fresh_phases"] == 4
    assert native["single_updates"] == 8
    assert native["observer_pairs"] == 2
    assert not native["full_simulator_loop_executed"]


@pytest.mark.parametrize("history,step,query", [("a", 25e-6, 1), ("b", 6.25e-6, 2)])
@pytest.mark.parametrize("mode", ["observed", "unobserved"])
def test_actual_native_input_and_single_updates_pass_independent_equations(
    registration, actual_smoke, history, step, query, mode
):
    output, native = actual_smoke
    group = f"{history}/dt_{step:.8g}"
    key = group + f"/suppression_release/query_{query}"
    row = ctx.io.read_compressed(output / native["records"][key][mode])
    checker.preparation_artifacts(registration, output, group, native["preparations"][group])
    checker.case_artifacts((output / native["records"][key][mode]).parent, row)
    physics = registration["data"][history]["preparation_registration"]["transport_protocol"]
    ledger = checker.Ledger(physics["tolerances"])
    checker.case_metrics(registration, row, native["preparations"][group], ledger, key + "/" + mode)
    assert ledger.failed == 0, ledger.failures[:4]
    assert ledger.count > 2000


def test_software_subset_cannot_be_reported_as_completed_preflight(registration, actual_smoke):
    output, native = actual_smoke
    with pytest.raises(ValueError, match="subset"):
        checker.check(registration, output, native)
    changed = copy.deepcopy(native)
    changed["test_only_subset"] = False
    with pytest.raises(ValueError, match="coverage"):
        checker.check(registration, output, changed)


@pytest.mark.parametrize(
    "fault",
    [
        "reset_gate",
        "reset_flux",
        "parameter",
        "clock",
        "elapsed",
        "double_transfer",
        "freeze_gate",
        "observer",
        "scope",
        "state_hash",
        "metadata",
        "fresh_current",
        "fresh_voltage_copy",
        "fresh_valence_copy",
        "initialization_seed",
        "fixture_gate",
        "gate_entry_modulator",
        "transfer_voltage",
    ],
)
def test_corrupted_native_evidence_is_rejected(registration, actual_smoke, fault):
    output, native = actual_smoke
    group = "a/dt_2.5e-05"
    key = group + "/suppression_release/query_1"
    row = ctx.io.read_compressed(output / native["records"][key]["observed"])
    app = row["applications"][-1]
    if fault == "reset_gate":
        app["after"]["channel"]["m"][0] = 0.0
    elif fault == "reset_flux":
        app["after"]["channel"]["density_mol_per_m2_s"][0] = 0.0
    elif fault == "parameter":
        app["applied_maxDm_m2_per_s"] = 7.5e-17
    elif fault == "clock":
        app["candidate_step_index"] += 1
    elif fault == "elapsed":
        app["actual_completed_single_updates"] = 20
    elif fault == "double_transfer":
        row["probe"]["after_ordinary"]["physical"]["inside_mM"][1][0] += 0.1
    elif fault == "freeze_gate":
        row["probe"]["after_channel"]["channel"]["m"] = row["probe"]["before"]["channel"]["m"]
        row["probe"]["after_channel"]["channel"]["h"] = row["probe"]["before"]["channel"]["h"]
    elif fault == "observer":
        row["probe"]["observer"]["events"].reverse()
    elif fault == "scope":
        row["protocol_query_time_is_simulated_elapsed_time"] = True
    elif fault == "state_hash":
        row["primed_numeric_inventory"]["numeric"]["gates/m"]["bytes_sha256"] = "0" * 64
    elif fault == "metadata":
        row["final_metadata"]["channel"]["targets"] = [0]
    elif fault == "fresh_voltage_copy":
        app["fresh"]["voltage_after_V"][0] += 0.001
    elif fault == "fresh_valence_copy":
        app["fresh"]["valence_after"][0] = -1.0
    elif fault == "initialization_seed":
        row["initialization_seed"] += 1
    elif fault == "fixture_gate":
        row["fixture"]["after"]["channel"]["m"][0] = 0.0
    elif fault == "gate_entry_modulator":
        row["prime"]["observer"]["snapshots"]["before_gate"]["channel"]["modulator"][0] = 0.0
    elif fault == "transfer_voltage":
        row["prime"]["observer"]["snapshots"]["before_transfer"]["physical"]["voltage_V"][0] = 0.0
    else:
        app["fresh"]["density_mol_per_m2_s"][0] = 1e-30
    ledger = checker.Ledger(
        registration["data"]["a"]["preparation_registration"]["transport_protocol"]["tolerances"]
    )
    try:
        checker.case_metrics(registration, row, native["preparations"][group], ledger, key)
    except (ValueError, KeyError):
        return
    assert ledger.failed > 0


@pytest.mark.parametrize("filename", ["initial.json.gz", "input-applied.json.gz"])
def test_saved_boundary_artifact_corruption_is_rejected(actual_smoke, monkeypatch, filename):
    output, native = actual_smoke
    path = output / native["records"]["a/dt_2.5e-05/suppression_release/query_1"]["observed"]
    row = ctx.io.read_compressed(path)
    original = ctx.io.read_compressed

    def altered(path):
        value = original(path)
        if path.name == filename:
            value["initialization_seed"] += 1
        return value

    monkeypatch.setattr(ctx.io, "read_compressed", altered)
    with pytest.raises(ValueError, match="artifact differs"):
        checker.case_artifacts(path.parent, row)


@pytest.mark.parametrize("field", ["native_yaml_sha256", "candidate_steps", "labels_origin"])
def test_preparation_artifact_corruption_is_rejected(registration, actual_smoke, field):
    output, native = actual_smoke
    group = "a/dt_2.5e-05"
    changed = copy.deepcopy(native["preparations"][group])
    changed[field] = 0
    with pytest.raises(ValueError):
        checker.preparation_artifacts(registration, output, group, changed)


def test_duplicate_comparison_identity_refused():
    ledger = checker.Ledger({"relative": 1e-11, "gate": 1e-12})
    ledger.add("x", [0.1], [0.1], "gate")
    with pytest.raises(ValueError, match="Duplicate"):
        ledger.add("x", [0.1], [0.1], "gate")


def test_existing_output_refused_before_registration(tmp_path):
    with pytest.raises(ValueError, match="fresh"):
        job.register(tmp_path, tmp_path / "absent.xml")


def test_detached_launch_does_not_wait_or_poll(tmp_path, registration, monkeypatch):
    output = tmp_path / "job"
    output.mkdir()
    ctx.io.write(output / "registration.json", registration)
    calls = []

    def popen(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(pid=12345)

    monkeypatch.setattr(job, "register", lambda output, tests: registration)
    monkeypatch.setattr(job.subprocess, "Popen", popen)
    result = job.launch(output, tmp_path / "unused.xml")
    assert result["status"] == "launched_detached"
    assert (
        result["automatic_polling"]
        is result["automatic_retry"]
        is result["automatic_followup"]
        is False
    )
    assert calls[0][1]["start_new_session"] is True
    assert ctx.c.read(output / "launch.json")["pid"] == 12345


def test_worker_flags_match_accepted_absences(registration, tmp_path):
    env = job.environment_of(
        registration["data"]["a"]["preparation_registration"],
        tmp_path,
        inherited={"JAX_DISABLE_JIT": "false", "XLA_FLAGS": "wrong", "PYTHONPATH": "wrong"},
    )
    assert "JAX_DISABLE_JIT" not in env and "XLA_FLAGS" not in env and "PYTHONPATH" not in env
    assert env["JAX_PLATFORMS"] == "cpu" and env["JAX_ENABLE_X64"] == "true"


def test_incomplete_software_receipt_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(ctx, "ROOT", tmp_path)
    path = tmp_path / "reports" / "empty.xml"
    path.parent.mkdir()
    # Test artifact, not a source file or registration.
    path.write_text('<testsuite tests="0" failures="0" errors="0" skipped="0"/>')
    with pytest.raises(ValueError):
        ctx.test_receipt(path)


def test_registrations_do_not_invent_a_release_reference_or_cells_run(registration):
    assert all("reference_parameters" not in v for v in registration["data"].values())
    assert json.dumps(registration, allow_nan=False)
    assert registration["plan"]["cells_trajectory_executed"] is False
