"""D077 preflight: saved pilot overlap, synthetic expanded gates and safe job controls.

Synthetic extensions are test fixtures only, never new native preparation evidence.
No simulator is integrated and no detached job is launched by this module.
"""

import copy
import hashlib
import subprocess
import zipfile
from types import SimpleNamespace

import contact as c
import expanded_bridge as bridge
import expanded_bridge_check as check
import expanded_bridge_context as ctx
import full_loop_bridge_check as shared
import full_loop_bridge_context as pilot
import pytest
import trajectory_evidence as evidence
from full_loop_observer import PRE_LOOP_CALLS
from test_full_loop_bridge import state_from_snapshot


@pytest.fixture(scope="module")
def plan():
    return c.read(ctx.PLAN)


@pytest.fixture(scope="module")
def prior():
    return evidence.trusted_registration()


@pytest.fixture(scope="module")
def saved(plan):
    return {
        (pilot.key(row), mode): shared.read_packet(ctx.pilot_path(row, mode), mode)
        for row in ctx.rows(plan)
        if ctx.overlap(row)
        for mode in ctx.MODES
    }


def test_qualified_pilot_and_older_evidence_are_unchanged():
    assert len(ctx.authenticate()["implementation_files_sha256"]) == 352
    assert len(ctx.previous.packet_hashes(ctx.SESSION)) == 11
    assert len(ctx.previous.packet_hashes()) == 142


@pytest.mark.parametrize(
    "key,value",
    [
        ("case_ids", ["passive"]),
        ("dt_s", [0.000025]),
        ("constant_profiles", ["matched_constants"]),
        ("duration_s", 0.01),
        ("native_runs", 12),
        ("observed_steps", 240),
        ("enabled_target_dispatches", 3360),
        ("observer_pairs", 35),
        ("variant_comparisons", 12),
        ("pilot_overlap_runs", 0),
        ("modes", ["observed"]),
        ("cells_runs", 8),
        ("worker_timeout_seconds", 9999),
        ("total_timeout_seconds", 9999),
        ("max_artifact_bytes", 9999999999),
        ("max_worker_file_bytes", 999999999),
        ("cpu_affinity", "0-31"),
        ("equality", "approximately_equal"),
        ("automatic_retry", True),
        ("automatic_retry", 0),
        ("independent_audit", "automatic"),
        ("expanded_bridge_qualified", True),
        ("nonzero_intervention", True),
        ("biology_validated", True),
        ("gpu_tested", True),
        ("extra_override", True),
        ("pilot_closeout_sha256", "0" * 64),
    ],
)
def test_unregistered_scope_or_relaxation_is_rejected(plan, key, value):
    changed = copy.deepcopy(plan)
    changed[key] = value
    with pytest.raises(ValueError):
        ctx.validate_plan(changed)


def test_full_coverage_and_no_narrow_plan_mutation(plan):
    rows = ctx.rows(plan)
    assert len(rows) == len({pilot.key(row) for row in rows}) == 36
    assert len({ctx.group_key(row) for row in rows}) == 12
    assert sum(round(0.001 / row["dt_s"]) for row in rows) == 3360
    assert len(bridge.reference_hashes(rows)) == 24
    assert sum(ctx.overlap(row) for row in rows) == 6
    assert c.read(pilot.PLAN) == pilot.EXPECTED_PLAN
    assert bridge.native.run_row.__module__ == "full_loop_bridge"


@pytest.mark.parametrize("index", range(36))
def test_all_expanded_metadata_is_explicit_input_not_native_preparation(plan, prior, index):
    row = ctx.rows(plan)[index]
    prepared, expected, mapped = check.input_expectations(row, prior)
    assert expected["constants"] == prior["base_protocol"]["profiles"][row["profile"]]
    assert expected["configured_steps"] == round(0.001 / row["dt_s"])
    assert expected["dt_s"] == expected["sampling_s"] == row["dt_s"]
    assert mapped["raw_clock_scale"] == mapped["steps"] / (mapped["steps"] - 1)
    assert prepared["ready"]["row"] == ctx.pilot_row(row)
    if row["variant"] == "zero_amplitude":
        for ion in ("Na", "K", "Cl"):
            assert expected["scheduled_options"][ion + "_mem"][:3] == mapped["mapped_pulse_times_s"]
            assert expected["scheduled_options"][ion + "_mem"][3] == 0.0
    if ctx.overlap(row):
        assert expected == prepared["metadata"]
    else:
        assert expected != prepared["metadata"]


def test_resource_extrapolation_has_time_storage_and_disk_headroom(plan):
    result = ctx.resource_estimate(plan)
    assert (
        500_000_000 < result["estimated_panel_bytes_with_allowances"] < plan["max_artifact_bytes"]
    )
    assert result["estimated_largest_worker_file_bytes"] < plan["max_worker_file_bytes"]
    assert 1.5 * result["step_scaled_seconds"] <= result["seconds_with_50_percent_allowance"] < 600
    assert "not a benchmark" in result["basis"]


def test_low_disk_blocks_registration(plan, monkeypatch):
    monkeypatch.setattr(ctx.shutil, "disk_usage", lambda _: SimpleNamespace(free=1024))
    with pytest.raises(ValueError, match="disk"):
        ctx.resource_estimate(plan)


@pytest.mark.parametrize("index", range(6))
@pytest.mark.parametrize("mode", ctx.MODES)
def test_actual_pilot_rows_pass_new_gates_and_overlap(plan, prior, saved, index, mode):
    row = [r for r in ctx.rows(plan) if ctx.overlap(r)][index]
    packet = saved[pilot.key(row), mode]
    assert check.check_row(row, mode, packet, prior, c.read(pilot.retained_path(row, mode))) == {
        "status": "capture_row_checks_pass",
        "observed_steps": 40 if mode == "observed" else 0,
    }
    assert check.check_overlap(row, mode, packet)["status"] == "original_pilot_overlap_exact"


def test_actual_observer_and_variant_controls(plan, saved):
    baseline = None
    for row in (r for r in ctx.rows(plan) if ctx.overlap(r)):
        pair = {mode: saved[pilot.key(row), mode] for mode in ctx.MODES}
        assert shared.check_pair(pair)["status"] == "observer_pair_exact"
        if row["variant"] == "baseline":
            baseline = pair["observed"]
        else:
            assert (
                check.check_variant(baseline, pair["observed"])["status"] == "variant_control_exact"
            )


def synthetic_packet(row, mode, prior):
    """Invent observer exports from retained INIT; these are not a SIM execution."""
    prepared, expected, _ = check.input_expectations(row, prior)
    owners = prior["geometry"]["membrane_owners"]
    numerical = c.read(pilot.retained_path(row, mode))
    observed = numerical if mode == "observed" else c.read(pilot.retained_path(row))
    initial = state_from_snapshot(observed["trace"]["initial"], prepared["ready"]["state"], owners)
    final = copy.deepcopy(initial)
    final["arrays"].update(copy.deepcopy(numerical["final"]))
    result = {
        "schema": "cells.betse_full_loop_bridge_row@1",
        "status": "exported_not_qualified",
        "row": row,
        "mode": mode,
        "numerical": numerical,
        "final_state": final,
        "final_metadata": expected
        | {"pickles_present": {"seed": True, "init": False, "sim": True}},
        "final_junctions": prepared["core"]["junctions"],
        "hook_restored": True,
        "lifecycle": {"calls": PRE_LOOP_CALLS, "run_returns": 1, "hook_restored": True}
        if mode == "observed"
        else None,
    }
    packet = {"core": prepared["core"], "result": result}
    if mode == "unobserved":
        return packet
    trace, events, previous = numerical["trace"], [], numerical["trace"]["initial"]
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
        "metadata": expected,
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
            "integration_calls": 1,
            "hook_restored": True,
        },
    }
    return packet


@pytest.mark.parametrize("case_id", ["passive", "blocked"])
@pytest.mark.parametrize("profile", ["source_constants", "matched_constants"])
@pytest.mark.parametrize("dt", [0.0000125, 0.00000625])
def test_synthetic_finer_steps_and_constants_include_actual_init_charge(
    plan, prior, case_id, profile, dt
):
    row = next(
        r
        for r in ctx.rows(plan)
        if r["case"]["id"] == case_id
        and r["profile"] == profile
        and r["dt_s"] == dt
        and r["variant"] == "zero_amplitude"
    )
    pair = {mode: synthetic_packet(row, mode, prior) for mode in ctx.MODES}
    for mode, packet in pair.items():
        checked = check.check_row(row, mode, packet, prior, c.read(pilot.retained_path(row, mode)))
        assert checked["observed_steps"] == (round(0.001 / dt) if mode == "observed" else 0)
    assert shared.check_pair(pair)["status"] == "observer_pair_exact"
    with pytest.raises(ValueError, match="outside"):
        check.check_overlap(row, "observed", pair["observed"])


def modify(data, path, value):
    for key in path[:-1]:
        data = data[key]
    data[path[-1]] = value


@pytest.mark.parametrize(
    "path,value",
    [
        (("result", "mode"), "unobserved"),
        (("result", "status"), "qualified"),
        (("result", "hook_restored"), False),
        (("result", "lifecycle", "run_returns"), 2),
        (("result", "numerical", "constants", "F"), 96485.0),
        (("result", "final_metadata", "pickles_present", "init"), True),
        (("result", "final_metadata", "pickles_present", "sim"), False),
        (("metadata", "configured_steps"), 160),
        (("metadata", "dt_s"), 0.00000625),
        (("entry", "pre_loop_calls", "init_dynamics"), 2),
        (("entry", "sampled_indices"), []),
        (("events", "mode"), "preparation_dispatch_only"),
        (("events", "integration_calls"), 0),
        (("events", "hook_restored"), False),
        (("events", "events", 0, "index"), 1),
        (("events", "events", 0, "raw_label_s"), 0.001),
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
def test_corrupt_saved_evidence_is_rejected(plan, prior, saved, path, value):
    row = next(r for r in ctx.rows(plan) if ctx.overlap(r))
    packet = copy.deepcopy(saved[pilot.key(row), "observed"])
    modify(packet, path, value)
    with pytest.raises(ValueError):
        check.check_row(row, "observed", packet, prior, c.read(pilot.retained_path(row)))


def coverage_fixture(plan):
    rows = ctx.rows(plan)
    results = [
        {
            "row": row,
            "mode": mode,
            "status": "capture_row_checks_pass",
            "observed_steps": round(0.001 / row["dt_s"]) if mode == "observed" else 0,
        }
        for row in rows
        for mode in ctx.MODES
    ]
    pairs = [{"key": pilot.key(row), "status": "observer_pair_exact"} for row in rows]
    variants = [
        {"key": pilot.key(row), "status": "variant_control_exact", "variant": row["variant"]}
        for row in rows
        if row["variant"] != "baseline"
    ]
    overlaps = [
        {"key": pilot.key(row), "mode": mode, "status": "original_pilot_overlap_exact"}
        for row in rows
        if ctx.overlap(row)
        for mode in ctx.MODES
    ]
    return [results, pairs, variants, overlaps]


def test_complete_capture_totals(plan):
    bridge.require_coverage(plan, *coverage_fixture(plan))


@pytest.mark.parametrize("index", range(4))
@pytest.mark.parametrize("kind", ["missing", "duplicate", "reorder"])
def test_bad_coverage_cannot_be_closed(plan, index, kind):
    values = coverage_fixture(plan)
    if kind == "missing":
        values[index].pop()
    elif kind == "duplicate":
        values[index][-1] = values[index][0]
    else:
        values[index].reverse()
    with pytest.raises(ValueError):
        bridge.require_coverage(plan, *values)


def test_capsule_is_verified_and_not_deserialized(tmp_path):
    data = b"# harmless test source\n"
    registered = {"sources": {"test.py": hashlib.sha256(data).hexdigest()}}
    with zipfile.ZipFile(tmp_path / "sources.zip", "x") as archive:
        archive.writestr("test.py", data)
    bridge.check_capsule(tmp_path, registered)
    registered["sources"]["test.py"] = "0" * 64
    with pytest.raises(ValueError, match="bytes"):
        bridge.check_capsule(tmp_path, registered)


def test_timeout_retains_partial_evidence_and_never_retries(tmp_path, plan, monkeypatch):
    c.write(tmp_path / "registration.json", {"plan": plan})
    c.write(tmp_path / "partial.json", {"status": "incomplete"})
    monkeypatch.setattr(bridge, "validate_registration", lambda _: None)
    monkeypatch.setattr(bridge, "check_capsule", lambda *_: None)
    calls = []

    def timeout(*args, **kwargs):
        calls.append((args, kwargs))
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr(bridge.subprocess, "run", timeout)
    with pytest.raises(subprocess.TimeoutExpired):
        bridge.execute(tmp_path)
    assert len(calls) == 1 and calls[0][1]["timeout"] <= 600
    failure = c.read(tmp_path / "failure.json")
    assert failure["automatic_retry"] is False and failure["expanded_bridge_qualified"] is False
    assert failure["files_sha256"]["partial.json"] == c.sha(tmp_path / "partial.json")
    assert not (tmp_path / "capture.json").exists()


def test_launch_is_detached_without_a_wait(tmp_path, plan, monkeypatch):
    calls = []
    monkeypatch.setattr(bridge, "register", lambda _: {"plan": plan})
    c.write(tmp_path / "registration.json", {"plan": plan})

    def popen(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(pid=12345)

    monkeypatch.setattr(bridge.subprocess, "Popen", popen)
    bridge.launch(tmp_path)
    assert len(calls) == 1 and calls[0][1]["start_new_session"] is True
    launched = c.read(tmp_path / "launch.json")
    assert launched["automatic_polling"] is False
    assert launched["independent_audit"] == "await_user_instruction"
