"""Synthetic control-aware gates, provenance and failure preservation; no native runs."""

import copy
import subprocess
from types import SimpleNamespace

import contact as c
import dispatch_preflight as run
import dispatch_preflight_check as check
import dispatch_preflight_context as ctx
import held_intervention as held
import numpy as np
import profile_bridge as base
import pytest
import trajectory as native
import trajectory_context as old
import trajectory_evidence as evidence


@pytest.fixture(scope="module")
def plan():
    return c.read(ctx.PLAN)


@pytest.fixture(scope="module")
def prior():
    return evidence.trusted_registration()


def test_previous_design_and_accepted_sources_are_unchanged():
    saved = ctx.preservation_check()
    assert saved["baseline_files"] == 942
    assert saved["accepted_implementation_files_unchanged"] == 352
    assert saved["production_modules_unchanged"] == 51
    assert saved["expanded_capture_files_unchanged"] == 802
    assert saved["expanded_audit_files_unchanged"] == 11


def test_scope_is_four_preparations_160_dispatches_without_integration(plan):
    ctx.validate_plan(plan)
    assert len(ctx.rows(plan)) == 4
    assert plan["dispatches_per_preparation"] == 40
    assert plan["trajectory_run"] is plan["trajectory_qualified"] is False


@pytest.mark.parametrize("condition", held.CONDITIONS)
def test_mapping_only_adds_declared_SIM_profile_and_event_inputs(condition, plan):
    row = next(r for r in ctx.rows(plan) if r["condition"] == condition)
    original = old.native_protocol(row["case"], row["dt_s"])
    before = copy.deepcopy(original)
    protocol, mapped = ctx.mapping(row)
    left = {tuple(k): v for k, v in original["yaml_overrides"]}
    right = {tuple(k): v for k, v in protocol["yaml_overrides"]}
    changed = {k for k in set(left) | set(right) if left.get(k) != right.get(k)}
    allowed_groups = {"sim time settings", "change Na mem", "change K mem", "change Cl mem"}
    assert all(
        k[0] in allowed_groups or k == ("tissue profile definition", "profiles enabled")
        for k in changed
    )
    assert original == before
    assert right[("tissue profile definition", "profiles enabled")] is True
    assert mapped["events_enabled"] is (condition in ("zero_amplitude", "suppression_recovery"))
    assert mapped["multiplier"] == (-1 if condition == "suppression_recovery" else 0)
    assert mapped["raw_labels_s"] == np.linspace(0, 0.001, 40).tolist()
    assert mapped["elapsed_times_s"] == [k * 0.000025 for k in range(40)]
    assert mapped["elapsed_times_s"][-1] == plan["terminal_dispatch_elapsed_s"] < 0.001
    for ion in ("Na", "K", "Cl"):
        assert right[("change " + ion + " mem", "multiplier")] == mapped["multiplier"]
        assert right[("change " + ion + " mem", "apply to")] == ["Base"]
        assert right[("change " + ion + " mem", "modulator function")] == "None"


@pytest.mark.parametrize(
    "key,value",
    [
        ("conditions", ["suppression_recovery"]),
        ("dt_s", 0.0001),
        ("constant_profile", "source_constants"),
        ("duration_s", 0.01),
        ("dispatches_per_preparation", 39),
        ("terminal_dispatch_elapsed_s", 0.001),
        ("raw_clock", "elapsed"),
        ("control_atol", 1e-3),
        ("control_atol", float("nan")),
        ("worker_timeout_seconds", 450),
        ("total_timeout_seconds", 600),
        ("max_artifact_bytes", 1),
        ("max_worker_file_bytes", 1),
        ("cpu_affinity", "0-31"),
        ("persist_each_completed_dispatch", False),
        ("integration_calls", 1),
        ("trajectory_run", True),
        ("trajectory_qualified", True),
        ("automatic_retry", True),
        ("automatic_trajectory_launch", True),
    ],
)
def test_rejects_changed_coverage_criteria_resources_or_scope(plan, key, value):
    with pytest.raises(ValueError):
        ctx.validate_plan(plan | {key: value})


def test_unknown_row_is_rejected(plan):
    with pytest.raises(ValueError):
        ctx.mapping(ctx.rows(plan)[0] | {"condition": "new_event"})


@pytest.fixture(scope="module")
def synthetic(plan, prior):
    """Retained initial states with fabricated dispatches test gates, not biology."""
    packets, references = {}, {}
    for row in ctx.rows(plan):
        original, preparation, _ = run.retained(row)
        _, mapped = ctx.mapping(row)
        ready = copy.deepcopy(preparation["ready"])
        ready |= {"row": row, "mapping": mapped}
        state = ready["state"]
        metadata = check.expected_metadata(row, prior, mapped)
        previous = copy.deepcopy(state)
        events = []
        controls = held.held_schedule(c.read(held.PLAN), row["condition"], row["dt_s"])
        for k, control in enumerate(controls):
            after = copy.deepcopy(state)
            baseline = np.asarray(state["arrays"]["Dm_base"]["values"], dtype=np.float64)
            multiplier = (
                control["multipliers"]["Na"] - 1
                if row["condition"] == "suppression_recovery"
                else 0
            )
            scheduled = multiplier * baseline
            # Avoid negative zero on immobile rows, matching a targeted mobile-only event.
            scheduled[3:] = 0
            after["arrays"]["Dm_scheduled"] = native.array_record(scheduled)
            after["arrays"]["Dm_cells"] = native.array_record(scheduled + baseline)
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
        packets[row["condition"]] = {
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
        references[row["condition"]] = (original, preparation)
    return packets, references


@pytest.mark.parametrize("condition", held.CONDITIONS)
def test_synthetic_dispatch_gates(condition, synthetic, plan, prior):
    packet = synthetic[0][condition]
    original, preparation = synthetic[1][condition]
    result = check.check_row(packet["ready"]["row"], packet, prior, original, plan, preparation)
    assert result["status"] == "nonzero_dispatch_checks_pass"
    assert result["event_dispatch_calls"] == 40 and result["control_values_checked"] == 14400
    assert result["maximum_baseline_scaled_control_error"] <= plan["control_atol"]
    assert result["integration_calls"] == 0 and result["trajectory_qualified"] is False


def test_synthetic_control_panel(synthetic, plan):
    assert check.check_controls(synthetic[0], plan)["baseline_zero_dispatch_equal"] is True
    changed = dict(synthetic[0])
    del changed["static_blocked"]
    with pytest.raises(ValueError, match="Incomplete"):
        check.check_controls(changed, plan)


@pytest.mark.parametrize(
    "fault",
    [
        "phase",
        "target",
        "duplicate_target",
        "cell_target",
        "extra_profile",
        "modulator",
        "scalar",
        "dynamic",
        "multiplier",
        "pulse_time",
        "base_diffusion",
        "global_event",
        "cut",
        "loaded_init",
        "bad_dt",
        "raw_clock",
        "missing_event",
        "repeated_event",
        "event_chain",
        "flux_call",
        "integration",
        "hook",
        "missing_stage",
        "ready_calls",
        "voltage",
        "concentration",
        "pump",
        "dtype",
        "hash",
        "effective",
        "scheduled",
        "immobile",
        "shape",
        "final_state",
        "topology",
        "temperature",
    ],
)
def test_rejects_corrupted_nonzero_dispatch(fault, synthetic, plan, prior):
    packet = copy.deepcopy(synthetic[0]["suppression_recovery"])
    row = packet["ready"]["row"]
    m = packet["metadata"]
    event = packet["dispatch"]["events"][20]
    a = event["after"]["arrays"]
    if fault == "phase":
        m["phase"] = "INIT"
    elif fault == "target":
        m["event_targets"]["Na"].pop()
    elif fault == "duplicate_target":
        m["event_targets"]["Na"][0] = 1
    elif fault == "cell_target":
        m["cell_targets"]["Base"].pop()
    elif fault == "extra_profile":
        m["additional_profile_count"] = 1
    elif fault == "modulator":
        m["event_effectors"]["Na"]["function"] = "gradient_x"
    elif fault == "scalar":
        m["event_effectors"]["Na"]["scalar"] = 2
    elif fault == "dynamic":
        m["event_effectors"]["Na"]["dynamic_values"][20] = 0
    elif fault == "multiplier":
        m["event_effectors"]["Na"]["multiplier"] = 1
    elif fault == "pulse_time":
        m["event_effectors"]["Na"]["pulse_times_s"][0] = 0
    elif fault == "base_diffusion":
        m["resolved_default"]["diffusion_m2_per_s"]["Na"] = 0
    elif fault == "global_event":
        m["global_options"]["T_change"] = 1
    elif fault == "cut":
        m["cut_event_enabled"] = True
    elif fault == "loaded_init":
        m["pickles_present"]["init"] = True
    elif fault == "bad_dt":
        m["dt_s"] = 0.0001
    elif fault == "raw_clock":
        event["raw_label_s"] += 0.01
    elif fault == "missing_event":
        packet["dispatch"]["events"].pop()
    elif fault == "repeated_event":
        event["index"] = 0
    elif fault == "event_chain":
        event["before"] = packet["ready"]["state"]
    elif fault == "flux_call":
        event["flux_ion_indices"] = [0]
    elif fault == "integration":
        packet["dispatch"]["integration_calls"] = 1
    elif fault == "hook":
        packet["dispatch"]["hook_restored"] = False
    elif fault == "missing_stage":
        del packet["core"]
    elif fault == "ready_calls":
        packet["ready"]["preparation_calls"]["update_V"] = 2
    elif fault == "dtype":
        a["Dm_cells"]["dtype"] = "<f4"
    elif fault == "hash":
        a["Dm_cells"]["bytes_sha256"] = "0" * 64
    elif fault == "shape":
        a["Dm_cells"]["shape"] = [30, 6]
    elif fault == "final_state":
        packet["final"]["state"] = packet["ready"]["state"]
    elif fault == "topology":
        packet["final"]["junctions"]["membrane_neighbours"][0] = 99
    elif fault == "temperature":
        event["after"]["temperature_K"] = 300
    elif fault == "pump":
        a["NaKATP_block"] = {"scalar": 0}
    else:
        name = {
            "voltage": "vm",
            "concentration": "cc_env",
            "effective": "Dm_cells",
            "scheduled": "Dm_scheduled",
            "immobile": "Dm_cells",
        }[fault]
        values = np.array(a[name]["values"], dtype=np.float64)
        if fault == "immobile":
            values[3, 0] = 1e-18
        else:
            values.flat[0] += 1e-9 if name.startswith("Dm") else 1
        a[name] = native.array_record(values)
    with pytest.raises(ValueError):
        check.check_row(
            row,
            packet,
            prior,
            *synthetic[1]["suppression_recovery"][:1],
            plan,
            synthetic[1]["suppression_recovery"][1],
        )


def test_partial_ready_and_exclusive_dispatch_files_survive_failures(tmp_path):
    def fail():
        raise ValueError("metadata failure")

    with pytest.raises(ValueError, match="metadata failure"):
        base.save_ready_before_metadata(tmp_path, {"preserved": True}, fail)
    assert c.read(tmp_path / "ready.json") == {"preserved": True}
    c.write(tmp_path / "event.json", {"index": 0})
    with pytest.raises(FileExistsError):
        c.write(tmp_path / "event.json", {"index": 1})


def test_resource_estimate_fits_explicit_caps(plan):
    estimate = ctx.resources(plan)
    assert estimate["estimated_bytes_with_allowances"] < plan["max_artifact_bytes"]
    assert estimate["estimated_worker_seconds_with_allowances"] < plan["worker_timeout_seconds"]
    assert estimate["peak_RAM_measured"] is False


def test_dispatch_exception_retains_completed_and_open_event(plan, monkeypatch, tmp_path):
    class Observer:
        def __init__(self, *args):
            self.events = []
            self.open_event = None

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    observer = Observer()
    monkeypatch.setattr(run, "NativeEventObserver", lambda *args: observer)

    def fire(*, phase, t):
        if observer.events:
            observer.open_event = {"index": 1, "raw_label_s": t}
            raise ValueError("synthetic dispatch failure")
        observer.events.append({"index": 0, "raw_label_s": t})

    phase = SimpleNamespace(
        p=SimpleNamespace(total_time=0.001), dyna=SimpleNamespace(fire_events=fire)
    )
    _, mapped = ctx.mapping(ctx.rows(plan)[-1])
    with pytest.raises(ValueError, match="synthetic dispatch failure"):
        run.dispatch(phase, tmp_path, mapped, tmp_path)
    assert c.read(tmp_path / "events/0000.json") == observer.events[0]
    assert not (tmp_path / "events/0001.json").exists()
    partial = c.read(tmp_path / "dispatch-partial.json")
    assert partial["events"] == observer.events
    assert partial["open_event"] == observer.open_event
    assert partial["hook_restored"] is True


@pytest.fixture
def registered(plan, prior, monkeypatch):
    read, sha = c.read, c.sha
    sources = old.sources()
    pre = {
        "status": "software_checks_pass_not_native_execution",
        "plan_sha256": sha(ctx.PLAN),
        "sources": sources,
        "test_receipt": "AGENTS.md",
        "test_receipt_sha256": sha(c.ROOT / "AGENTS.md"),
    }
    monkeypatch.setattr(c, "read", lambda p: pre if p == ctx.PRELAUNCH else read(p))
    monkeypatch.setattr(c, "sha", lambda p: "f" * 64 if p == ctx.PRELAUNCH else sha(p))
    return {
        "schema": "cells.betse_nonzero_dispatch_registration@1",
        "plan": plan,
        "sources": sources,
        "prior_review_sha256": ctx.PRIOR_SHA,
        "prelaunch_sha256": "f" * 64,
        "preservation_sha256": sha(ctx.PRESERVATION),
        "upstream": prior["upstream"],
    }


def test_registration_provenance(registered):
    run.validate_registration(registered)
    changed = copy.deepcopy(registered)
    changed["sources"]["dispatch_preflight.py"] = "0" * 64
    with pytest.raises(ValueError):
        run.validate_registration(changed)


@pytest.mark.parametrize("failure", ["timeout", "worker_exit"])
def test_failed_worker_retains_registered_sources_and_partial_evidence(
    failure, registered, monkeypatch, tmp_path
):
    monkeypatch.setattr(ctx, "preservation_check", lambda: {})
    monkeypatch.setattr(c, "inspect_source", lambda: registered["upstream"])

    def worker(output, plan, timeout):
        c.write(output / "partial.json", {"completed_dispatches": 3})
        assert 0 < timeout <= 45
        if failure == "timeout":
            raise subprocess.TimeoutExpired("synthetic-worker", timeout)
        return SimpleNamespace(returncode=2)

    monkeypatch.setattr(run, "execute_worker", worker)
    output = tmp_path / "attempt"
    with pytest.raises((ValueError, subprocess.TimeoutExpired)):
        run.preflight(output)
    result = c.read(output / "failure.json")
    assert result["status"] == "fail" and result["trajectory_qualified"] is False
    assert not (output / "completion.json").exists()
    assert run.manifest(output, exclude={"failure.json"}) == result["files_sha256"]
    assert {"registration.json", "sources.zip", "partial.json"} <= set(result["files_sha256"])
    with pytest.raises(ValueError, match="reuse"):
        run.preflight(output)


def test_manifest_rejects_linked_artifacts(tmp_path):
    c.write(tmp_path / "original.json", {})
    (tmp_path / "linked.json").symlink_to(tmp_path / "original.json")
    with pytest.raises(ValueError, match="linked"):
        run.manifest(tmp_path)
