"""Pilot gates on fabricated extensions of retained data; no native integration."""

import copy
import subprocess
import sys
from types import SimpleNamespace

import contact as c
import full_loop_bridge as bridge
import full_loop_bridge_check as check
import full_loop_bridge_context as ctx
import numpy as np
import profile_bridge_context as preparation
import pytest
import trajectory as native
import trajectory_evidence as evidence
from full_loop_observer import PRE_LOOP_CALLS


@pytest.fixture(scope="module")
def plan():
    return c.read(ctx.PLAN)


@pytest.fixture(scope="module")
def prior():
    return evidence.trusted_registration()


def test_d074_and_all_older_frozen_evidence_is_preserved():
    assert len(ctx.authenticate()["implementation_files_sha256"]) == 352


@pytest.mark.parametrize(
    "key,value",
    [
        ("case_ids", ["passive"]),
        ("constant_profile", "source_constants"),
        ("dt_s", 0.0000125),
        ("duration_s", 0.1),
        ("native_runs", 72),
        ("observed_steps", 3360),
        ("worker_timeout_seconds", 10000),
        ("total_timeout_seconds", 10000),
        ("max_artifact_bytes", 999999999),
        ("max_worker_file_bytes", 999999999),
        ("cpu_affinity", "0-31"),
        ("cells_runs", 8),
        ("modes", ["observed"]),
        ("independent_audit", "automatic"),
        ("automatic_retry", True),
        ("automatic_retry", 0),
        ("expanded_bridge_qualified", True),
        ("nonzero_intervention", True),
        ("biology_validated", True),
        ("gpu_tested", True),
        ("extra_silent_override", True),
        ("equality", "approximately_equal"),
        ("partial_evidence", "discard_on_error"),
    ],
)
def test_unregistered_expansion_or_relaxation_is_rejected(plan, key, value):
    altered = copy.deepcopy(plan)
    altered[key] = value
    with pytest.raises(ValueError):
        ctx.validate_plan(altered)


def test_six_inputs_twelve_runs_and_separate_observed_counts(plan):
    rows = ctx.rows(plan)
    assert len(rows) == 6 and len({ctx.key(row) for row in rows}) == 6
    assert len(rows) * len(ctx.MODES) == plan["native_runs"] == 12
    assert len(rows) * round(plan["duration_s"] / plan["dt_s"]) == plan["observed_steps"] == 240
    assert sum(row["variant"] == "zero_amplitude" for row in rows) * 40 == 80
    assert rows == preparation.rows(c.read(preparation.PLAN))
    for row in rows:
        _, mapped = preparation.mapping(row)
        assert mapped["steps"] == 40 and mapped["raw_clock_scale"] == 40 / 39


def test_sizing_is_prospective_and_below_declared_cap(plan):
    result = ctx.resource_estimate(plan)
    assert result["estimated_panel_bytes_with_allowances"] == 142920656
    assert result["estimated_panel_bytes_with_allowances"] < result["max_artifact_bytes"]
    assert "not a measured runtime" in result["basis"]


def state_from_snapshot(snapshot, initial, owners, fluxes=None):
    state = copy.deepcopy(initial)
    for key, name in check.LINKS.items():
        state["arrays"][name] = native.array_record(np.asarray(snapshot[key], dtype=np.float64))
    inside = state["arrays"]["cc_cells"]["values"]
    state["arrays"]["cc_at_mem"] = native.array_record(
        np.asarray(inside, dtype=np.float64)[:, owners]
    )
    if fluxes is not None:
        state["arrays"]["fluxes_mem"] = native.array_record(np.asarray(fluxes, dtype=np.float64))
    return state


@pytest.fixture(scope="module")
def fabricated(plan, prior):
    """Invent only event/lifecycle records around already saved INIT trajectories."""
    packets = {}
    owners = prior["geometry"]["membrane_owners"]
    for row in ctx.rows(plan):
        prepared = check.prepared_packet(row)
        initial = prepared["ready"]["state"]
        for mode in ctx.MODES:
            numerical = c.read(ctx.retained_path(row, mode))
            final = copy.deepcopy(initial)
            final["arrays"].update(copy.deepcopy(numerical["final"]))
            result = {
                "schema": "cells.betse_full_loop_bridge_row@1",
                "status": "exported_not_qualified",
                "row": row,
                "mode": mode,
                "numerical": numerical,
                "final_state": final,
                "final_metadata": copy.deepcopy(prepared["metadata"])
                | {"pickles_present": {"seed": True, "init": False, "sim": True}},
                "final_junctions": prepared["core"]["junctions"],
                "hook_restored": True,
                "lifecycle": {"calls": PRE_LOOP_CALLS, "run_returns": 1, "hook_restored": True}
                if mode == "observed"
                else None,
            }
            packet = {"core": prepared["core"], "result": result}
            if mode == "observed":
                trace, events = numerical["trace"], []
                previous = trace["initial"]
                for index, step in enumerate(trace["steps"]):
                    before = state_from_snapshot(previous, initial, owners)
                    events.append(
                        {
                            "index": index,
                            "raw_label_s": trace["labels_s"][index],
                            "before": before,
                            "after": copy.deepcopy(before),
                            "before_update": state_from_snapshot(
                                step["before"], initial, owners, step["density_mol_per_m2_s"]
                            ),
                            "flux_ion_indices": list(range(6)),
                        }
                    )
                    previous = step["after"]
                packet |= {
                    "dynamics": copy.deepcopy(prepared["core"]),
                    "metadata": prepared["metadata"],
                    "entry": {
                        "state": initial,
                        "initial": trace["initial"],
                        "pre_loop_calls": PRE_LOOP_CALLS,
                        "labels_s": trace["labels_s"],
                        "sampled_indices": trace["sampled_indices"],
                    },
                    "events": {
                        "mode": "full_sim_loop",
                        "initial": initial,
                        "events": events,
                        "hook_restored": True,
                        "integration_calls": 1,
                    },
                }
            packets[ctx.key(row), mode] = packet
    return packets


@pytest.mark.parametrize("index", range(6))
@pytest.mark.parametrize("mode", ctx.MODES)
def test_fabricated_full_loop_rows_exercise_all_saved_gates(plan, prior, fabricated, index, mode):
    row = ctx.rows(plan)[index]
    checked = check.check_row(
        row,
        mode,
        fabricated[ctx.key(row), mode],
        prior,
        c.read(ctx.retained_path(row, mode)),
        check.prepared_packet(row),
    )
    assert checked == {
        "status": "capture_row_checks_pass",
        "observed_steps": 40 if mode == "observed" else 0,
    }


@pytest.mark.parametrize("index", range(6))
def test_fabricated_observer_pairs_are_exact(plan, fabricated, index):
    row = ctx.rows(plan)[index]
    pair = {mode: fabricated[ctx.key(row), mode] for mode in ctx.MODES}
    assert check.check_pair(pair)["status"] == "observer_pair_exact"


@pytest.mark.parametrize("case_id", ["passive", "blocked"])
def test_fabricated_variant_controls_are_exact(plan, fabricated, case_id):
    variants = {
        row["variant"]: fabricated[ctx.key(row), "observed"]
        for row in ctx.rows(plan)
        if row["case"]["id"] == case_id
    }
    assert check.check_variants(variants)["comparisons"] == 2


def set_path(data, path, value):
    for part in path[:-1]:
        data = data[part]
    data[path[-1]] = value


@pytest.mark.parametrize(
    "path,value",
    [
        (("result", "mode"), "unobserved"),
        (("result", "status"), "qualified"),
        (("result", "hook_restored"), False),
        (("result", "lifecycle", "run_returns"), 0),
        (("result", "final_metadata", "profiles_enabled"), True),
        (("result", "final_metadata", "pickles_present", "sim"), False),
        (("result", "final_metadata", "pickles_present", "init"), True),
        (("result", "final_metadata", "cut_event_enabled"), True),
        (("entry", "sampled_indices"), []),
        (("entry", "pre_loop_calls", "init_dynamics"), 2),
        (("events", "mode"), "preparation_dispatch_only"),
        (("events", "integration_calls"), 0),
        (("events", "hook_restored"), False),
        (("events", "events", 0, "index"), 1),
        (("events", "events", 0, "raw_label_s"), 0.000025),
        (("events", "events", 0, "flux_ion_indices"), [0, 1, 2]),
        (("events", "events", 0, "after", "temperature_K"), 311.0),
        (("events", "events", 0, "before_update", "arrays", "vm", "dtype"), "<f4"),
        (("events", "events", 0, "before_update", "arrays", "cc_cells", "shape"), [7, 6]),
        (
            ("events", "events", 0, "before_update", "arrays", "fluxes_mem", "bytes_sha256"),
            "0" * 64,
        ),
    ],
)
def test_corrupt_or_relabelled_evidence_cannot_pass(plan, prior, fabricated, path, value):
    row = ctx.rows(plan)[0]
    changed = copy.deepcopy(fabricated[ctx.key(row), "observed"])
    set_path(changed, path, value)
    with pytest.raises(ValueError):
        check.check_row(
            row,
            "observed",
            changed,
            prior,
            c.read(ctx.retained_path(row)),
            check.prepared_packet(row),
        )


@pytest.mark.parametrize("field", ["vm", "cc_cells", "Dm_cells", "fluxes_mem", "I_mem"])
def test_rehashed_event_corruption_is_rejected(plan, prior, fabricated, field):
    row = ctx.rows(plan)[0]
    changed = copy.deepcopy(fabricated[ctx.key(row), "observed"])
    target = changed["events"]["events"][0]["before_update"]["arrays"]
    values = np.array(target[field]["values"], dtype=np.float64)
    values.flat[0] += 0.01
    target[field] = native.array_record(values)
    with pytest.raises(ValueError):
        check.check_row(
            row,
            "observed",
            changed,
            prior,
            c.read(ctx.retained_path(row)),
            check.prepared_packet(row),
        )


def test_source_nonce_and_flux_reset_have_distinct_boundaries(plan, prior, fabricated):
    row = ctx.rows(plan)[0]
    packet = fabricated[ctx.key(row), "observed"]
    first = packet["events"]["events"][0]
    assert first["before"] == first["after"]
    assert first["after"]["arrays"]["vm"] != first["before_update"]["arrays"]["vm"]
    assert first["after"]["arrays"]["fluxes_mem"] != first["before_update"]["arrays"]["fluxes_mem"]
    assert (
        check.check_row(
            row,
            "observed",
            packet,
            prior,
            c.read(ctx.retained_path(row)),
            check.prepared_packet(row),
        )["observed_steps"]
        == 40
    )


@pytest.mark.parametrize("missing", ["core", "dynamics", "entry", "metadata", "events"])
def test_missing_physical_evidence_is_rejected(plan, prior, fabricated, missing):
    row = ctx.rows(plan)[0]
    altered = {k: v for k, v in fabricated[ctx.key(row), "observed"].items() if k != missing}
    with pytest.raises(ValueError):
        check.check_row(
            row,
            "observed",
            altered,
            prior,
            c.read(ctx.retained_path(row)),
            check.prepared_packet(row),
        )


def test_missing_comparison_partner_is_rejected():
    with pytest.raises(ValueError, match="partner"):
        check.check_pair({"observed": {}})
    with pytest.raises(ValueError, match="control"):
        check.check_variants({"baseline": {}})


def test_detached_launch_does_not_wait_poll_or_start_audit(tmp_path, monkeypatch, plan):
    calls = []

    def register(output):
        c.write(output / "registration.json", {"synthetic": True})
        return {"plan": plan}

    def spawn(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(pid=12345)

    monkeypatch.setattr(bridge, "register", register)
    monkeypatch.setattr(bridge.subprocess, "Popen", spawn)
    bridge.launch(tmp_path)
    assert len(calls) == 1 and calls[0][1]["start_new_session"] is True
    assert calls[0][1]["stdin"] == subprocess.DEVNULL
    receipt = c.read(tmp_path / "launch.json")
    assert receipt["pid"] == 12345 and receipt["automatic_polling"] is False
    assert receipt["independent_audit"] == "await_user_instruction"
    assert not (tmp_path / "capture.json").exists()


def test_worker_timeout_retains_terminal_failure_without_retry(tmp_path, monkeypatch, plan):
    c.write(tmp_path / "registration.json", {"plan": plan})
    monkeypatch.setattr(bridge, "validate_registration", lambda registered: None)
    calls = []

    def timeout(*args, **kwargs):
        calls.append(kwargs)
        raise subprocess.TimeoutExpired("synthetic worker", kwargs["timeout"])

    monkeypatch.setattr(bridge.subprocess, "run", timeout)
    with pytest.raises(subprocess.TimeoutExpired):
        bridge.execute(tmp_path)
    failure = c.read(tmp_path / "failure.json")
    assert len(calls) == 1 and calls[0]["timeout"] <= plan["worker_timeout_seconds"]
    assert failure["status"] == "failed_not_qualified" and failure["automatic_retry"] is False
    assert "worker.log" in failure["files_sha256"]
    assert not (tmp_path / "capture.json").exists()


def test_successful_fake_worker_remains_pending_independent_audit(tmp_path, monkeypatch, plan):
    c.write(tmp_path / "registration.json", {"plan": plan})
    monkeypatch.setattr(bridge, "validate_registration", lambda registered: None)
    monkeypatch.setattr(bridge.ctx, "preservation_check", lambda: {})

    def complete(*args, **kwargs):
        c.write(
            tmp_path / "worker.json",
            {
                "status": "capture_controls_pass_pending_independent_audit",
                "native_runs": 12,
                "observed_steps": 240,
            },
        )
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(bridge.subprocess, "run", complete)
    bridge.execute(tmp_path)
    result = c.read(tmp_path / "capture.json")
    assert result["trajectory_qualified"] is result["independent_audit_run"] is False
    assert result["expanded_bridge_qualified"] is False
    assert not (tmp_path / "failure.json").exists()


def test_checker_imports_neither_model_runtime():
    assert not any(
        n == "betse" or n.startswith("betse.") or n == "cells" or n.startswith("cells.")
        for n in sys.modules
    )
