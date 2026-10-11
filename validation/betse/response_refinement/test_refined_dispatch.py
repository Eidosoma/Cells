"""Finer dispatch software checks: saved preparations and fabricated events, no native run."""

import copy
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import refined_dispatch_check as check
import refined_dispatch_context as ctx
import refined_dispatch_job as job
import refined_dispatch_native as native

c = ctx.c


@pytest.fixture(scope="module")
def plan():
    return c.read(ctx.PLAN)


@pytest.fixture(scope="module")
def prior():
    return ctx.legacy.evidence.trusted_registration()


def test_closed_rejection_and_production_preserved():
    result = ctx.preservation_check()
    assert result["baseline_files"] == 979
    assert result["audit_files_unchanged"] == 16
    assert result["capture_files_unchanged"] == 150
    assert result["accepted_implementation_files_unchanged"] == 352
    assert result["production_modules_unchanged"] == 51
    assert len(ctx.audit_context.prior.old.sources()) == 88
    assert len(ctx.sources()) == 98


def test_panel_is_only_two_finer_holds_and_no_trajectory(plan):
    rows = ctx.rows(plan)
    assert len(rows) == 8 and len({ctx.key(r) for r in rows}) == 8
    assert {r["dt_s"] for r in rows} == {12.5e-6, 6.25e-6}
    assert sum(ctx.mapping(r)[1]["steps"] for r in rows) == 960
    assert plan["integration_calls"] == 0
    assert all(plan[k] is False for k in ctx.FALSE_FLAGS)


@pytest.mark.parametrize("condition", ctx.held.CONDITIONS)
def test_coarse_mapping_and_metadata_remain_exact_software_overlaps(condition, prior):
    row = ctx.coarse_row(condition)
    original = ctx.legacy.mapping(row)
    assert ctx.mapping(row) == original
    assert check.expected_metadata(row, prior, original[1]) == check.legacy.expected_metadata(
        row, prior, original[1]
    )


@pytest.mark.parametrize("h,count", [(12.5e-6, 80), (6.25e-6, 160)])
@pytest.mark.parametrize("condition", ctx.held.CONDITIONS)
def test_finer_mapping_changes_only_time_inputs(h, count, condition):
    coarse = ctx.coarse_row(condition)
    before = ctx.legacy.mapping(coarse)
    protocol, mapped = ctx.mapping(coarse | {"dt_s": h})
    left, right = ({tuple(k): v for k, v in p["yaml_overrides"]} for p in (before[0], protocol))
    changes = {k for k in set(left) | set(right) if left.get(k) != right.get(k)}
    assert changes and all(
        (
            k[0] in ("init time settings", "sim time settings")
            and k[1] in ("time step", "sampling rate")
        )
        or (
            k[0] in ("change Na mem", "change K mem", "change Cl mem")
            and k[1] in ("change start", "change finish", "change rate")
        )
        for k in changes
    )
    assert mapped["steps"] == count
    assert mapped["raw_labels_s"] == np.linspace(0, 0.001, count).tolist()
    assert mapped["elapsed_times_s"] == [k * h for k in range(count)]
    assert mapped["raw_clock_scale"] == count / (count - 1)
    assert mapped["elapsed_times_s"][-1] == (count - 1) * h < 0.001
    assert ctx.legacy.mapping(coarse) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("hold_steps_s", [25e-6, 12.5e-6, 6.25e-6]),
        ("conditions", ["suppression_recovery"]),
        ("duration_s", 0.01),
        ("constant_profile", "source_constants"),
        ("event_dispatch_calls", 959),
        ("targeted_dispatches", 960),
        ("control_values_checked", 0),
        ("control_atol", 1e-8),
        ("control_atol", float("nan")),
        ("integration_calls", False),
        ("trajectory_run", True),
        ("automatic_trajectory_launch", True),
        ("worker_timeout_seconds", 900),
        ("max_worker_file_bytes", 10**9),
        ("cpu_affinity", "0-31"),
    ],
)
def test_changed_panel_or_tolerance_is_rejected(plan, field, value):
    with pytest.raises(ValueError):
        ctx.validate_plan(plan | {field: value})


@pytest.mark.parametrize(
    "change", [{"dt_s": True}, {"dt_s": 1e-5}, {"profile": "other"}, {"condition": "other"}]
)
def test_unregistered_mapping_rejected(change):
    with pytest.raises(ValueError):
        ctx.mapping(ctx.coarse_row("baseline") | change)


@pytest.fixture(scope="module")
def synthetic(plan, prior):
    """Use retained initial state only; all finer dispatch records here are fabricated."""
    packets, references = {}, {}
    for row in ctx.rows(plan):
        original, preparation, _ = native.legacy.retained(row)
        ready = copy.deepcopy(preparation["ready"])
        mapped = ctx.mapping(row)[1]
        ready |= {"row": row, "mapping": mapped}
        state = ready["state"]
        metadata = check.expected_metadata(row, prior, mapped)
        previous, events = copy.deepcopy(state), []
        schedule = ctx.held.held_schedule(c.read(ctx.held.PLAN), row["condition"], row["dt_s"])
        baseline = np.asarray(state["arrays"]["Dm_base"]["values"], dtype=np.float64)
        for k, control in enumerate(schedule):
            after = copy.deepcopy(state)
            multiplier = (
                control["multipliers"]["Na"] - 1
                if row["condition"] == "suppression_recovery"
                else 0
            )
            scheduled = multiplier * baseline
            scheduled[3:] = 0
            after["arrays"]["Dm_scheduled"] = native.native.array_record(scheduled)
            after["arrays"]["Dm_cells"] = native.native.array_record(scheduled + baseline)
            events.append(
                {
                    "index": k,
                    "raw_label_s": mapped["raw_labels_s"][k],
                    "before": previous,
                    "after": after,
                    "flux_ion_indices": [],
                }
            )
            previous = after
        packets[ctx.key(row)] = {
            "core": copy.deepcopy(preparation["core"]),
            "dynamics": copy.deepcopy(preparation["core"]),
            "ready": ready,
            "metadata": metadata,
            "dispatch": {
                "mode": "preparation_dispatch_only",
                "initial": None,
                "hook_restored": True,
                "integration_calls": 0,
                "events": events,
            },
            "final": {
                "state": previous,
                "metadata": copy.deepcopy(metadata),
                "junctions": copy.deepcopy(preparation["core"]["junctions"]),
            },
        }
        references[ctx.key(row)] = original, preparation
    return packets, references


@pytest.mark.parametrize("h", [12.5e-6, 6.25e-6])
@pytest.mark.parametrize("condition", ctx.held.CONDITIONS)
def test_complete_synthetic_row_gates(h, condition, synthetic, prior, plan):
    row = ctx.coarse_row(condition) | {"dt_s": h}
    packet = synthetic[0][ctx.key(row)]
    original, preparation = synthetic[1][ctx.key(row)]
    result = check.check_row(row, packet, prior, original, plan, preparation)
    count = round(plan["duration_s"] / h)
    assert result["status"] == "refined_dispatch_checks_pass"
    assert result["event_dispatch_calls"] == count
    assert result["control_values_checked"] == count * 360
    assert result["maximum_baseline_scaled_control_error"] <= plan["control_atol"]


@pytest.mark.parametrize("h", [12.5e-6, 6.25e-6])
def test_synthetic_exact_controls_at_each_hold(h, synthetic, plan):
    packets = {r["condition"]: synthetic[0][ctx.key(r)] for r in ctx.rows(plan) if r["dt_s"] == h}
    assert check.legacy.check_controls(packets, plan)["baseline_zero_dispatch_equal"] is True


@pytest.mark.parametrize(
    "fault",
    [
        "phase",
        "target",
        "modulator",
        "multiplier",
        "dynamic_length",
        "pulse_time",
        "unscaled_clock",
        "bad_dt",
        "missing_event",
        "event_index",
        "event_chain",
        "flux_call",
        "integration",
        "hook",
        "missing_stage",
        "ready_calls",
        "voltage",
        "concentration",
        "temperature",
        "pump",
        "dtype",
        "hash",
        "shape",
        "effective",
        "scheduled",
        "immobile",
        "final_state",
        "topology",
        "new_endpoint",
    ],
)
def test_rehashed_or_semantic_corruptions_rejected(fault, synthetic, prior, plan):
    row = ctx.coarse_row("suppression_recovery") | {"dt_s": 6.25e-6}
    packet = copy.deepcopy(synthetic[0][ctx.key(row)])
    original, preparation = synthetic[1][ctx.key(row)]
    m, probe = packet["metadata"], packet["dispatch"]
    event = probe["events"][60]
    a = event["after"]["arrays"]
    if fault == "phase":
        m["phase"] = "INIT"
    elif fault == "target":
        m["event_targets"]["Na"].pop()
    elif fault == "modulator":
        m["event_effectors"]["Na"]["scalar"] = 2
    elif fault == "multiplier":
        m["event_effectors"]["Na"]["multiplier"] = 0
    elif fault == "dynamic_length":
        m["event_effectors"]["Na"]["dynamic_values"] = [1.0] * 40
    elif fault == "pulse_time":
        m["event_effectors"]["Na"]["pulse_times_s"][0] = 0
    elif fault == "unscaled_clock":
        event["raw_label_s"] = 60 * row["dt_s"]
    elif fault == "bad_dt":
        m["dt_s"] = 25e-6
    elif fault == "missing_event":
        probe["events"].pop()
    elif fault == "event_index":
        event["index"] = 0
    elif fault == "event_chain":
        event["before"] = packet["ready"]["state"]
    elif fault == "flux_call":
        event["flux_ion_indices"] = [0]
    elif fault == "integration":
        probe["integration_calls"] = 1
    elif fault == "hook":
        probe["hook_restored"] = False
    elif fault == "missing_stage":
        packet.pop("core")
    elif fault == "ready_calls":
        packet["ready"]["preparation_calls"]["update_V"] = 2
    elif fault == "temperature":
        event["after"]["temperature_K"] = 300
    elif fault == "pump":
        a["NaKATP_block"] = {"scalar": 0}
    elif fault in ("dtype", "hash", "shape"):
        field, value = {
            "dtype": ("dtype", "<f4"),
            "hash": ("bytes_sha256", "0" * 64),
            "shape": ("shape", [30, 6]),
        }[fault]
        a["Dm_cells"][field] = value
    elif fault == "final_state":
        packet["final"]["state"] = packet["ready"]["state"]
    elif fault == "topology":
        packet["final"]["junctions"]["membrane_neighbours"][0] = 99
    elif fault == "new_endpoint":
        after = probe["events"][-1]["after"]
        baseline = np.asarray(after["arrays"]["Dm_base"]["values"], dtype=np.float64)
        law = c.read(ctx.held.law.PLAN)["candidate_pulse"]
        scheduled = (ctx.held.law.decimal_availability(0.001, law) - 1) * baseline
        scheduled[3:] = 0
        after["arrays"]["Dm_scheduled"] = native.native.array_record(scheduled)
        after["arrays"]["Dm_cells"] = native.native.array_record(scheduled + baseline)
    else:
        name = {
            "voltage": "vm",
            "concentration": "cc_env",
            "effective": "Dm_cells",
            "scheduled": "Dm_scheduled",
            "immobile": "Dm_cells",
        }[fault]
        values = np.asarray(a[name]["values"], dtype=np.float64).copy()
        if fault == "immobile":
            values[3, 0] = 1e-18
        else:
            values.flat[0] += 1e-9 if name.startswith("Dm") else 1
        a[name] = native.native.array_record(values)
    with pytest.raises(ValueError):
        check.check_row(row, packet, prior, original, plan, preparation)


def test_prospective_resources_use_measured_old_dispatch(plan):
    estimate = ctx.resources(plan)
    assert (
        estimate["estimated_worker_seconds_with_allowances"] == 251 < plan["worker_timeout_seconds"]
    )
    assert (
        estimate["estimated_artifact_bytes_with_allowances"]
        == 206406234
        < plan["max_artifact_bytes"]
    )
    assert (
        estimate["estimated_largest_worker_file_bytes_with_allowances"]
        == 17333340
        < plan["max_worker_file_bytes"]
    )
    assert estimate["peak_RAM_measured"] is False


@pytest.mark.parametrize(
    "source,name",
    [
        (source, name)
        for source, names in native.legacy.PreparationFence.FORBIDDEN.items()
        for name in sorted(names)
    ],
)
def test_preparation_fence_stops_forbidden_bodies(source, name, tmp_path):
    namespace = {}
    exec(
        compile(
            f"def {name}():\n    raise AssertionError('body ran')\n", str(tmp_path / source), "exec"
        ),
        namespace,
    )
    with pytest.raises(ValueError, match="Preflight forbids"):
        with native.legacy.PreparationFence(tmp_path):
            namespace[name]()
    assert sys.getprofile() is None


def test_finer_dispatch_exception_preserves_completed_and_open_event(monkeypatch, tmp_path):
    observer = SimpleNamespace(events=[], open_event=None)

    class Observer:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        @property
        def events(self):
            return observer.events

        @property
        def open_event(self):
            return observer.open_event

    monkeypatch.setattr(native.legacy, "NativeEventObserver", lambda *args: Observer())

    def fire(*, phase, t):
        if len(observer.events) == 45:
            observer.open_event = {"index": 45, "raw_label_s": t}
            raise ValueError("synthetic interrupted dispatch")
        observer.events.append({"index": len(observer.events), "raw_label_s": t})

    phase = SimpleNamespace(
        p=SimpleNamespace(total_time=0.001), dyna=SimpleNamespace(fire_events=fire)
    )
    mapped = ctx.mapping(ctx.coarse_row("suppression_recovery") | {"dt_s": 6.25e-6})[1]
    with pytest.raises(ValueError, match="synthetic interrupted"):
        native.legacy.dispatch(phase, tmp_path, mapped, tmp_path)
    assert len(list((tmp_path / "events").glob("*.json"))) == 45
    partial = c.read(tmp_path / "dispatch-partial.json")
    assert partial["events"] == observer.events and partial["open_event"] == observer.open_event
    assert partial["hook_restored"] is True


@pytest.fixture
def registered(plan, prior, monkeypatch):
    read, sha = c.read, c.sha
    sources = ctx.sources()
    pre = {
        "status": "software_checks_pass_not_native_execution",
        "plan": plan,
        "sources": sources,
        "preservation_sha256": sha(ctx.PRESERVATION),
        "test_receipt": "AGENTS.md",
        "test_receipt_sha256": sha(c.ROOT / "AGENTS.md"),
        "new_files_sha256_before_prelaunch": {},
    }
    monkeypatch.setattr(c, "read", lambda p: pre if Path(p) == ctx.PRELAUNCH else read(p))
    monkeypatch.setattr(c, "sha", lambda p: "f" * 64 if Path(p) == ctx.PRELAUNCH else sha(p))
    return {
        "schema": "cells.betse_refined_dispatch_registration@1",
        "plan": plan,
        "sources": sources,
        "audit_completion_sha256": ctx.AUDIT_SHA,
        "prelaunch_sha256": "f" * 64,
        "preservation_sha256": sha(ctx.PRESERVATION),
        "upstream": prior["upstream"],
        "inputs": job.inputs(plan),
    }


def test_registration_binds_prescribed_inputs_and_frozen_sources(registered):
    job.validate_registration(registered)


@pytest.mark.parametrize("fault", ["sources", "upstream", "inputs", "audit", "prelaunch"])
def test_registration_rejects_changed_provenance(registered, fault):
    bad = copy.deepcopy(registered)
    if fault == "sources":
        bad["sources"]["dispatch_preflight.py"] = "0" * 64
    elif fault in ("inputs", "upstream"):
        bad[fault] = {}
    elif fault == "audit":
        bad["audit_completion_sha256"] = "0" * 64
    else:
        bad["prelaunch_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        job.validate_registration(bad)


def test_detached_launcher_does_not_wait_or_poll(tmp_path, monkeypatch):
    c.write(tmp_path / "registration.json", {"synthetic": True})
    monkeypatch.setattr(job, "register", lambda output: None)
    called = {}

    def popen(command, **kwargs):
        called.update(command=command, **kwargs)
        return SimpleNamespace(pid=123)

    monkeypatch.setattr(job.subprocess, "Popen", popen)
    job.launch(tmp_path)
    assert called["start_new_session"] is True and called["stdin"] == subprocess.DEVNULL
    receipt = c.read(tmp_path / "launch.json")
    assert receipt["pid"] == 123
    assert receipt["automatic_polling"] is receipt["automatic_trajectory_launch"] is False


@pytest.mark.parametrize("outcome", ["timeout", "nonzero"])
def test_worker_failure_is_durable_without_retry(outcome, plan, monkeypatch, tmp_path):
    c.write(tmp_path / "registration.json", {"plan": plan, "synthetic": True})
    monkeypatch.setattr(job, "validate_registration", lambda r: None)
    monkeypatch.setattr(ctx.audit_job, "capsule", lambda output, r: None)
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        c.write(tmp_path / "partial.json", {"completed_dispatches": 45})
        assert str(c.REFERENCE_PYTHON) in command
        assert 0 < kwargs["timeout"] <= 300
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return SimpleNamespace(returncode=2)

    monkeypatch.setattr(job.subprocess, "run", run)
    with pytest.raises((ValueError, subprocess.TimeoutExpired)):
        job.execute(tmp_path)
    result = c.read(tmp_path / "failure.json")
    assert result["stage"] == "native_preflight" and len(calls) == 1
    assert result["automatic_retry"] is result["automatic_trajectory_launch"] is False
    assert c.read(tmp_path / "partial.json")["completed_dispatches"] == 45
    assert not (tmp_path / "completion.json").exists()
    assert result["files_sha256"] == {
        n: h for n, h in job.payloads(tmp_path).items() if n != "failure.json"
    }


@pytest.mark.parametrize("destination", ["root", "capture_child", "audit_child", "existing"])
def test_launch_destination_cannot_modify_old_evidence(destination):
    output = {
        "root": c.ROOT / "runs",
        "capture_child": ctx.audit_context.SESSION / "new",
        "audit_child": ctx.AUDIT / "new",
        "existing": ctx.AUDIT,
    }[destination]
    with pytest.raises(ValueError, match="fresh preflight"):
        job.register(output)


@pytest.fixture
def worker_receipt(registered, tmp_path):
    """Tiny fabricated payloads exercise receipt linkage only, not physical-law gates."""
    c.write(tmp_path / "registration.json", registered)
    results = []
    for row in ctx.rows(registered["plan"]):
        count = ctx.mapping(row)[1]["steps"]
        directory = tmp_path / ctx.key(row)
        directory.mkdir(parents=True)
        events = [{"synthetic_index": k} for k in range(count)]
        for name in job.row_paths(count):
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            value = (
                {"events": events}
                if name == "dispatch.json"
                else events[int(path.stem)]
                if name.startswith("events/")
                else {"synthetic": True}
            )
            c.write(path, value)
        result = {
            "row": row,
            "status": "refined_dispatch_checks_pass",
            "integration_calls": 0,
            "trajectory_qualified": False,
            "event_dispatch_calls": count,
            "control_values_checked": count * 360,
            "maximum_baseline_scaled_control_error": 0.0,
        }
        c.write(
            directory / "result.json",
            result
            | {
                "files_sha256": ctx.audit_context.packet_hashes(directory),
                "retained_files_sha256": job.import_retained(row),
            },
        )
        results.append(
            result
            | {"path": ctx.key(row) + "/result.json", "sha256": c.sha(directory / "result.json")}
        )
    captured = c.read(ctx.audit_context.SESSION / "native.json")
    result = {
        "schema": "cells.betse_refined_dispatch_worker@1",
        "status": "refined_dispatch_checks_pass",
        "registration_sha256": c.sha(tmp_path / "registration.json"),
        "sources": registered["sources"],
        "warnings": [],
        "integration_calls": 0,
        "results": results,
        "maximum_baseline_scaled_control_error": 0.0,
        "installed_python_sha256": captured["installed_python_sha256"],
        "package_path": captured["package_path"],
        "environment": captured["environment"],
        "controls": {
            f"{h:.8f}": {
                "status": "exact_preparation_controls_pass",
                "baseline_zero_dispatch_equal": True,
                "fresh_normal_preparations_equal": True,
            }
            for h in registered["plan"]["hold_steps_s"]
        },
    }
    result |= {
        k: registered["plan"][k]
        for k in (
            "preparations",
            "event_dispatch_calls",
            "targeted_dispatches",
            "nonzero_targeted_dispatches",
            "control_values_checked",
            *ctx.FALSE_FLAGS,
        )
    }
    return result, registered, tmp_path


def test_worker_receipt_links_every_row_event_and_reference(worker_receipt):
    job.validate_worker(*worker_receipt)


@pytest.mark.parametrize(
    "fault",
    [
        "warnings",
        "row_count",
        "total",
        "controls",
        "source",
        "runtime",
        "installed",
        "path",
        "hash",
        "integration",
        "claim",
    ],
)
def test_worker_receipt_rejects_incomplete_or_overclaimed_results(worker_receipt, fault):
    result, registered, output = worker_receipt
    if fault == "warnings":
        result["warnings"] = ["warning"]
    elif fault == "row_count":
        result["results"].pop()
    elif fault == "total":
        result["event_dispatch_calls"] = 959
    elif fault == "controls":
        result["controls"] = {}
    elif fault == "source":
        result["sources"] = {}
    elif fault == "runtime":
        result["environment"]["python"] = "other"
    elif fault == "installed":
        result["installed_python_sha256"] = {}
    elif fault in ("path", "hash"):
        result["results"][0]["path" if fault == "path" else "sha256"] = "wrong"
    elif fault == "integration":
        result["integration_calls"] = 1
    else:
        result["trajectory_qualified"] = True
    with pytest.raises(ValueError):
        job.validate_worker(result, registered, output)


def test_worker_rejects_rehashed_individual_event_disagreement(worker_receipt):
    result, registered, output = worker_receipt
    row = result["results"][0]
    directory = output / ctx.key(row["row"])
    path = directory / "events/0000.json"
    path.write_text(json.dumps({"synthetic_index": -1}))
    saved = c.read(directory / "result.json")
    saved["files_sha256"]["events/0000.json"] = c.sha(path)
    (directory / "result.json").write_text(json.dumps(saved))
    row["sha256"] = c.sha(directory / "result.json")
    with pytest.raises(ValueError, match="Durable/aggregate"):
        job.validate_worker(result, registered, output)
