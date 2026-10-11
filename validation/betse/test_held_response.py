"""Held-response gates on saved data and pytest-owned synthetic copies; no new ODE runs."""

import copy
import hashlib
import json
import struct
import subprocess
import zipfile
from types import SimpleNamespace

import contact as c
import full_loop_bridge_check as links
import held_intervention as held
import held_response_context as ctx
import held_response_job as job
import held_response_native as native
import pytest
import trajectory_context as old
import trajectory_evidence as evidence
from trajectory_check import numbers


def array(values, shape):
    return {
        "dtype": "<f8",
        "shape": shape,
        "values": copy.deepcopy(values),
        "bytes_sha256": hashlib.sha256(
            b"".join(struct.pack("<d", v) for v in numbers(values))
        ).hexdigest(),
    }


@pytest.fixture(scope="module")
def plan():
    return c.read(ctx.PLAN)


@pytest.fixture(scope="module")
def prior():
    return evidence.trusted_registration()


@pytest.fixture(scope="module")
def registered(plan, prior):
    """Declared test input, not a registered or executed scientific attempt."""
    return {
        "schema": "cells.betse_held_response_registration@1",
        "plan": plan,
        "native_rows": ctx.native_rows(plan),
        "cells_rows": ctx.cells_rows(plan),
        "cells_definitions": ctx.definitions(plan),
        "common_times_s": ctx.common_times(plan),
        "cells_export_shapes": ctx.export_shapes(),
        "criteria": prior["protocol"],
        "sources": old.sources(),
        "upstream": prior["upstream"],
        "prior_handoff_sha256": ctx.PRIOR_SHA,
        "preservation_sha256": c.sha(ctx.PRESERVATION),
        **{k: prior[k] for k in ("base_protocol", "geometry", "settings", "cells_runtime")},
    }


@pytest.fixture(scope="module")
def saved(plan):
    """Reuse real no-op numerical data, changing only test envelope/metadata schema."""
    packets = {}
    for row in ctx.native_rows(plan):
        if row["condition"] == "suppression_recovery":
            continue
        pair = {}
        for mode in plan["native_modes"]:
            packet = links.read_packet(ctx.overlap_path(row, mode).parent, mode)
            metadata = ctx.prepared(row)["metadata"]
            packet["result"] |= {
                "schema": "cells.betse_held_response_native_row@1",
                "row": row,
                "final_metadata": metadata
                | {"pickles_present": {"seed": True, "init": False, "sim": True}},
            }
            if mode == "observed":
                packet["metadata"] = metadata
            pair[mode] = packet
        packets[row["condition"]] = pair
    return packets


def test_earlier_evidence_and_engineering_preserved():
    result = ctx.preservation_check()
    assert result["baseline_files"] == 954
    assert result["dispatch_files_unchanged"] == 201
    assert result["accepted_implementation_files_unchanged"] == 352
    assert result["production_modules_unchanged"] == 51


def test_resources_are_prospective_with_eager_step_allowance(plan):
    result = ctx.resources(plan)
    assert result["stage_seconds_with_allowances"] == {
        "native": 134,
        "cells": 1894,
        "comparison": 120,
    }
    assert (
        128 * 1024**2
        < result["estimated_artifact_bytes_with_allowances"]
        < plan["max_artifact_bytes"]
    )
    assert result["peak_RAM_measured"] is False


@pytest.mark.parametrize(
    "key,value",
    [
        ("hold_step_s", 0.0000125),
        ("cells_subdivisions", [1, 4]),
        ("constant_profile", "source_constants"),
        ("native_runs", 4),
        ("cells_runs", 12),
        ("control_atol", 1e-3),
        ("control_atol", float("nan")),
        ("cells_steps_total", True),
        ("terminal_rate_policy", "fresh_endpoint"),
        ("cross_failure_policy", "ignore_baseline"),
        ("max_artifact_bytes", 1),
        ("max_worker_file_bytes", 1),
        ("total_timeout_seconds", 3600),
        ("stage_timeout_seconds", {"native": 1000, "cells": 2100, "comparison": 180}),
        ("cpu_affinity", "0-31"),
        ("automatic_polling", True),
        ("automatic_retry", True),
        ("automatic_expansion", True),
        ("trajectory_qualified", True),
        ("native_convergence_qualified", True),
        ("forcing_convergence_qualified", True),
        ("gpu_tested", True),
        ("biology_validated", True),
    ],
)
def test_no_silent_scope_resource_or_tolerance_change(plan, key, value):
    with pytest.raises(ValueError):
        ctx.validate_plan(plan | {key: value})


@pytest.mark.parametrize("condition", held.CONDITIONS)
def test_input_grid_is_fixed_across_solver_refinements(registered, condition):
    rows = [r for r in registered["cells_rows"] if r["condition"] == condition]
    assert len(rows) == 6
    controls = None
    original = registered["cells_definitions"]
    for row in rows:
        definition = original[row["id"]]
        assert definition == held.cells_definition(
            c.read(held.PLAN), condition, 0.000025, row["subdivision"], row["backend"]
        )
        assert definition["execution"]["dt"] == 0.000025 / row["subdivision"]
        assert definition["execution"]["max_steps"] == 40 * row["subdivision"]
        assert definition["experiment"]["observation_times"] == registered["common_times_s"]
        inputs = definition["experiment"]["membrane_controls"]
        assert controls is None or inputs == controls
        controls = inputs
        assert len(inputs[0]["leak"]) == 40
        assert inputs[0]["leak"][-1]["time"] < 0.001


@pytest.mark.parametrize("condition", ["baseline", "zero_amplitude", "static_blocked"])
@pytest.mark.parametrize("mode", ["observed", "unobserved"])
def test_real_retained_noop_capture_passes_new_linkage_gates(plan, prior, saved, condition, mode):
    row = next(r for r in ctx.native_rows(plan) if r["condition"] == condition)
    result = native.check_row(
        row,
        mode,
        saved[condition][mode],
        prior,
        plan,
        ctx.prepared(row),
        c.read(ctx.overlap_path(row, mode)),
    )
    assert result["observed_steps"] == (40 if mode == "observed" else 0)


def test_real_retained_observer_pairs_and_zero_control(saved):
    for pair in saved.values():
        assert links.check_pair(pair)["status"] == "observer_pair_exact"
    assert (
        native.check_zero({k: pair["observed"] for k, pair in saved.items()})["status"]
        == "baseline_zero_response_exact"
    )


@pytest.fixture(scope="module")
def synthetic_pulse(saved, plan):
    """Synthetic control-only linkage fixture; baseline transport is NOT pulse evidence."""
    row = ctx.native_rows(plan)[-1]
    packet = copy.deepcopy(saved["baseline"]["observed"])
    packet["result"]["row"] = row
    packet["metadata"] = ctx.prepared(row)["metadata"]
    packet["result"]["final_metadata"] = packet["metadata"] | {
        "pickles_present": {"seed": True, "init": False, "sim": True}
    }
    actual_dispatches = c.read(ctx.DISPATCH / "suppression_recovery/dispatch.json")["events"]
    for event, dispatched in zip(packet["events"]["events"], actual_dispatches, strict=True):
        for name in native.VARIABLE:
            event["before"]["arrays"][name] = copy.deepcopy(dispatched["before"]["arrays"][name])
            for boundary in ("after", "before_update"):
                event[boundary]["arrays"][name] = copy.deepcopy(dispatched["after"]["arrays"][name])
    last = actual_dispatches[-1]["after"]["arrays"]
    packet["result"]["final_state"]["arrays"].update(
        {k: copy.deepcopy(last[k]) for k in native.VARIABLE}
    )
    numerical = packet["result"]["numerical"]
    numerical["final"]["Dm_cells"] = copy.deepcopy(last["Dm_cells"])
    numerical["permeability_m_per_s"] = [
        [v / 7.5e-9 for v in a] for a in last["Dm_cells"]["values"]
    ]
    numerical["ordinary"]["dd_time"] = array(
        [e["after"]["arrays"]["Dm_cells"]["values"] for e in actual_dispatches[1:]], [39, 6, 30]
    )
    return packet


def test_synthetic_pulse_links_use_actual_D080_controls(synthetic_pulse, plan, prior):
    row = ctx.native_rows(plan)[-1]
    result = native.check_row(row, "observed", synthetic_pulse, prior, plan, ctx.prepared(row))
    assert result["observed_steps"] == 40
    assert result["maximum_baseline_scaled_control_error"] < 2e-14


@pytest.mark.parametrize(
    "corruption",
    [
        "row",
        "metadata",
        "missing_event",
        "label",
        "nonce",
        "ion_order",
        "dispatch_state",
        "post_flux_state",
        "control_shift",
        "control_bytes",
        "final_state",
        "final_control",
        "observer",
        "storage",
        "dtype",
    ],
)
def test_rejects_synthetic_pulse_linkage_corruptions(synthetic_pulse, plan, prior, corruption):
    packet = copy.deepcopy(synthetic_pulse)
    result, event = packet["result"], packet["events"]["events"][15]
    if corruption == "row":
        result["row"] = ctx.native_rows(plan)[0]
    elif corruption == "metadata":
        packet["metadata"]["event_targets"]["Na"].pop()
    elif corruption == "missing_event":
        packet["events"]["events"].pop()
    elif corruption == "label":
        event["raw_label_s"] = 0.000375
    elif corruption == "ion_order":
        event["flux_ion_indices"].reverse()
    elif corruption in ("nonce", "dispatch_state", "post_flux_state"):
        boundary, name = {
            "nonce": ("before_update", "vm"),
            "dispatch_state": ("after", "cc_cells"),
            "post_flux_state": ("before_update", "I_mem"),
        }[corruption]
        a = event[boundary]["arrays"][name]
        if name == "cc_cells":
            a["values"][0][0] += 1
        else:
            a["values"][0] += 1
        event[boundary]["arrays"][name] = array(a["values"], a["shape"])
    elif corruption == "control_shift":
        event["after"]["arrays"]["Dm_cells"] = copy.deepcopy(event["before"]["arrays"]["Dm_cells"])
    elif corruption == "control_bytes":
        event["after"]["arrays"]["Dm_cells"]["bytes_sha256"] = "0" * 64
    elif corruption == "final_state":
        result["final_state"]["arrays"]["cc_cells"] = copy.deepcopy(
            packet["entry"]["state"]["arrays"]["cc_cells"]
        )
    elif corruption == "final_control":
        result["numerical"]["permeability_m_per_s"][0][0] *= 0.5
    elif corruption == "observer":
        result["lifecycle"]["hook_restored"] = False
    elif corruption == "storage":
        result["numerical"]["trace"]["storage"].pop()
    elif corruption == "dtype":
        event["after"]["arrays"]["Dm_cells"]["dtype"] = "<f4"
    row = ctx.native_rows(plan)[-1]
    with pytest.raises(ValueError):
        native.check_row(row, "observed", packet, prior, plan, ctx.prepared(row))


def test_noop_requires_its_frozen_overlap(saved, plan, prior):
    row = ctx.native_rows(plan)[0]
    with pytest.raises(ValueError, match="No-op overlap"):
        native.check_row(
            row, "observed", saved["baseline"]["observed"], prior, plan, ctx.prepared(row)
        )


def test_provenance_rejects_changed_capsule(tmp_path):
    with zipfile.ZipFile(tmp_path / "sources.zip", "x") as archive:
        archive.writestr("fixture.py", "wrong")
    with pytest.raises(ValueError, match="content"):
        job.capsule(tmp_path, {"sources": {"fixture.py": hashlib.sha256(b"right").hexdigest()}})


def test_duplicate_capsule_members_are_rejected(tmp_path):
    with zipfile.ZipFile(tmp_path / "sources.zip", "x") as archive:
        archive.writestr("fixture.py", "right")
        with pytest.warns(UserWarning):
            archive.writestr("fixture.py", "right")
    with pytest.raises(ValueError, match="coverage"):
        job.capsule(tmp_path, {"sources": {"fixture.py": hashlib.sha256(b"right").hexdigest()}})


@pytest.mark.parametrize(
    "stage,interpreter",
    [("native", c.REFERENCE_PYTHON), ("cells", c.CELLS_PYTHON), ("comparison", c.CELLS_PYTHON)],
)
def test_stage_isolation_and_cpu_command(plan, tmp_path, stage, interpreter):
    command = job.stage_command(stage, tmp_path, plan)
    assert command[:5] == ["taskset", "-c", "0-3", str(interpreter), "-B"]
    assert command[-2:] == [stage, str(tmp_path)]


def test_worker_environment_does_not_inherit_disabled_JIT(tmp_path, monkeypatch):
    monkeypatch.setenv("JAX_DISABLE_JIT", "1")
    monkeypatch.setenv("PYTHONPATH", "/wrong")
    env = job.environment(tmp_path)
    assert "JAX_DISABLE_JIT" not in env and "PYTHONPATH" not in env
    assert env["JAX_ENABLE_X64"] == "1" and env["JAX_PLATFORMS"] == "cpu"


@pytest.mark.parametrize("failure", ["timeout", "worker_error", "numerical_failure"])
def test_failure_is_durable_and_never_retried(tmp_path, monkeypatch, registered, failure):
    c.write(tmp_path / "registration.json", registered)
    monkeypatch.setattr(ctx, "validate_registration", lambda r: None)
    monkeypatch.setattr(job, "capsule", lambda output, r: None)
    calls = []

    def run(command, **kwargs):
        calls.append(command[-2])
        assert kwargs["timeout"] <= registered["plan"]["stage_timeout_seconds"][command[-2]]
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        if failure == "worker_error":
            raise subprocess.CalledProcessError(1, command)
        if command[-2] == "comparison":
            c.write(
                tmp_path / "comparison.json",
                {"status": "failed_not_qualified", "failed_comparisons": 18},
            )

    monkeypatch.setattr(job.subprocess, "run", run)
    with pytest.raises((subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError)):
        job.execute(tmp_path)
    saved = c.read(tmp_path / "failure.json")
    assert saved["status"] == "failed_not_qualified"
    assert saved["automatic_retry"] is saved["automatic_expansion"] is False
    assert calls == (
        ["native", "cells", "comparison"] if failure == "numerical_failure" else ["native"]
    )
    assert not (tmp_path / "capture.json").exists()
    if failure == "numerical_failure":
        assert c.read(tmp_path / "comparison.json")["failed_comparisons"] == 18


def test_launch_detaches_and_never_calls_poll_or_wait(tmp_path, monkeypatch, registered):
    c.write(tmp_path / "registration.json", registered)
    monkeypatch.setattr(job, "register", lambda output: registered)
    calls = []

    def popen(command, **kwargs):
        calls.append(command)
        assert kwargs["start_new_session"] is True
        assert kwargs["stdin"] == subprocess.DEVNULL
        return SimpleNamespace(pid=4242)  # Deliberately no poll(), wait() or terminate().

    monkeypatch.setattr(job.subprocess, "Popen", popen)
    job.launch(tmp_path)
    receipt = c.read(tmp_path / "launch.json")
    assert len(calls) == 1 and receipt["pid"] == 4242
    assert receipt["automatic_polling"] is False
    assert receipt["independent_audit"] == "await_user_instruction"


def test_native_failure_retains_partial_observer(tmp_path, monkeypatch, plan, prior):
    class Observer:
        def __init__(self, *args):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def partial(self):
            return {"synthetic": True, "completed_events": [0], "open_event": 1}

    def fail(phase):
        raise ValueError("synthetic native failure")

    monkeypatch.setattr(
        native.preparation,
        "fresh_phase",
        lambda *a: (SimpleNamespace(sim=SimpleNamespace(run_sim_core=fail)), {}),
    )
    monkeypatch.setattr(native.base, "core_snapshot", lambda *a: {})
    monkeypatch.setattr(native, "FullLoopObserver", Observer)
    directory = tmp_path / "row"
    with pytest.raises(ValueError, match="synthetic native failure"):
        native.run_row(ctx.native_rows(plan)[0], "observed", directory, prior, tmp_path)
    assert c.read(directory / "partial-observer.json")["open_event"] == 1
    assert (directory / "core.json").exists() and (directory / "failure.json").exists()
    assert not (directory / "result.json").exists()


def test_registration_rejects_changed_definitions_or_criteria(tmp_path, monkeypatch, registered):
    pre = tmp_path / "prelaunch.json"
    receipt = tmp_path / "tests.xml"
    receipt.write_text("synthetic test receipt")
    c.write(
        pre,
        {
            "status": "software_checks_pass_not_native_execution",
            "plan_sha256": c.sha(ctx.PLAN),
            "test_receipt": str(receipt),
            "test_receipt_sha256": c.sha(receipt),
            "sources": registered["sources"],
            "new_files_sha256_before_prelaunch": {str(receipt): c.sha(receipt)},
        },
    )
    monkeypatch.setattr(ctx, "PRELAUNCH", pre)
    good = registered | {"prelaunch_sha256": c.sha(pre)}
    ctx.validate_registration(good)
    bad = copy.deepcopy(good)
    bad["cells_definitions"][next(iter(bad["cells_definitions"]))]["execution"]["dt"] *= 2
    with pytest.raises(ValueError, match="definitions"):
        ctx.validate_registration(bad)
    bad = copy.deepcopy(good)
    bad["criteria"]["trajectory_tolerances"]["amount_fmol"] *= 10
    with pytest.raises(ValueError, match="tolerances"):
        ctx.validate_registration(bad)
    receipt.write_text("changed test evidence")
    with pytest.raises(ValueError, match="inputs/source/tests"):
        ctx.validate_registration(good)


def test_prior_counts_helper_and_full_source_coverage(registered):
    assert callable(ctx.prior.prior.prior.prior.test_counts)
    assert ctx.FILES <= set(registered["sources"])
    assert len(registered["sources"]) == 88
    assert json.dumps(registered, allow_nan=False)
