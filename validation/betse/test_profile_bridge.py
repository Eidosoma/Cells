"""Profile prerequisites, partial evidence, synthetic gates and saved native preparation."""

import copy
import sys
from types import SimpleNamespace

import contact as c
import numpy as np
import phase_bridge as legacy
import phase_bridge_context as previous
import profile_bridge as bridge
import profile_bridge_check as check
import profile_bridge_context as ctx
import pytest
import trajectory as native
import trajectory_context as old
import trajectory_evidence as evidence

SESSION = c.ROOT / "runs/ref-003e0-v2-2026-09-12/preflight-01"


@pytest.fixture(scope="module")
def plan():
    return c.read(ctx.PLAN)


@pytest.fixture(scope="module")
def prior():
    return evidence.trusted_registration()


def test_d073_failed_packet_and_all_accepted_sources_remain_unchanged():
    assert len(ctx.authenticate()["implementation_files_sha256"]) == 352


@pytest.mark.parametrize("variant", ctx.VARIANTS)
@pytest.mark.parametrize("case_id", ["passive", "blocked"])
@pytest.mark.parametrize("dt", [0.000025, 0.0000125, 0.00000625])
@pytest.mark.parametrize("profile", ["source_constants", "matched_constants"])
def test_mapping_changes_only_the_declared_profile_flag(variant, case_id, dt, profile, prior):
    case = next(case for case in prior["protocol"]["cases"] if case["id"] == case_id)
    row = {"variant": variant, "case": case, "dt_s": dt, "profile": profile}
    original, _ = previous.mapping(case, dt, ctx.VARIANTS[variant]["event_mode"])
    unchanged = copy.deepcopy(original)
    protocol, mapped = ctx.mapping(row)
    left = {tuple(path): value for path, value in original["yaml_overrides"]}
    right = {tuple(path): value for path, value in protocol["yaml_overrides"]}
    changes = {path for path in left if left[path] != right[path]}
    assert changes == (
        set() if variant == "baseline" else {("tissue profile definition", "profiles enabled")}
    )
    assert original == unchanged and set(left) == set(right)
    assert mapped["profiles_enabled"] is (variant != "baseline")
    assert right[("tissue profile definition", "tissue", "profiles")] == []
    assert right[("tissue profile definition", "cut profiles")] == []
    previous.require_dispatch_profiles(protocol)


@pytest.mark.parametrize(
    "key,value",
    [
        ("revision", 1),
        ("dt_s", 0.0001),
        ("duration_s", 1),
        ("case_ids", ["passive"]),
        ("constant_profile", "source_constants"),
        ("worker_timeout_seconds", 350),
        ("max_artifact_bytes", 1),
        ("cpu_affinity", "0-31"),
        ("preserve_partial_state", False),
        ("trajectory_run", True),
        ("trajectory_qualified", True),
        ("biology_validated", True),
        ("gpu_tested", True),
        ("equality", "approximately_equal"),
    ],
)
def test_plan_rejects_unregistered_coverage_and_promotion(plan, key, value):
    altered = copy.deepcopy(plan)
    altered[key] = value
    with pytest.raises(ValueError):
        ctx.validate_plan(altered)


def test_plan_has_six_separate_fresh_preparations(plan):
    rows = ctx.rows(plan)
    assert len(rows) == 6
    assert {(r["case"]["id"], r["variant"]) for r in rows} == {
        (case, variant) for case in ("passive", "blocked") for variant in ctx.VARIANTS
    }
    assert len(plan["dispatch_elapsed_times_s"]) == 5
    assert plan["trajectory_run"] is plan["trajectory_qualified"] is False


def test_unknown_variant_is_rejected(plan):
    row = ctx.rows(plan)[0] | {"variant": "silent_activation"}
    with pytest.raises(ValueError):
        ctx.mapping(row)


def test_metadata_failure_cannot_discard_ready_state(tmp_path):
    ready = {"state": {"inventories": [12.0, 140.0]}, "integration_calls": 0}

    def fail():
        raise AttributeError("missing optional metadata")

    with pytest.raises(AttributeError, match="optional metadata"):
        bridge.save_ready_before_metadata(tmp_path, ready, fail)
    assert c.read(tmp_path / "ready.json") == ready
    assert not (tmp_path / "metadata.json").exists()


def test_stage_records_are_exclusive_and_cannot_overwrite_evidence(tmp_path):
    bridge.write_stage(tmp_path, "core", {"value": 1})
    with pytest.raises(FileExistsError):
        bridge.write_stage(tmp_path, "core", {"value": 2})
    with pytest.raises(ValueError):
        bridge.write_stage(tmp_path, "unregistered_stage", {})
    assert c.read(tmp_path / "core.json") == {"value": 1}


@pytest.fixture(scope="module")
def synthetic(plan, prior, tmp_path_factory):
    """Fabricated preparation records test gates; these are not new native results."""
    directory = tmp_path_factory.mktemp("synthetic-profile-gates")
    packets, retained = {}, {}
    for row in ctx.rows(plan):
        identifier = (row["case"]["id"], row["variant"])
        reference = c.read(
            evidence.SESSION
            / "native"
            / old.key(row["case"]["id"], row["profile"], row["dt_s"])
            / "observed/result.json"
        )
        initial = reference["trace"]["initial"]
        sim = SimpleNamespace()
        links = {
            "cc_cells": "inside_mM",
            "cc_env": "outside_mM",
            "vm": "voltage_V",
            "rho_cells": "rho_C_per_m3",
            "I_mem": "inward_current_A",
            "Phi_b": "boundary_voltage_V",
        }
        for key, value in links.items():
            setattr(sim, key, np.asarray(initial[value], dtype=np.float64))
        sim.cc_at_mem = sim.cc_cells[:, prior["geometry"]["membrane_owners"]].copy()
        sim.Dm_cells = np.array(reference["final"]["Dm_cells"]["values"], dtype=np.float64)
        sim.Dm_base = sim.Dm_cells.copy()
        sim.zs = np.array([1, 1, -1, 2, -1, -1], dtype=np.int64)
        for name in ("Dm_scheduled", "P_cells", "P_base", "P_mod", "fluxes_mem", "fluxes_gj"):
            setattr(sim, name, np.zeros(check.SHAPES[name]))
        sim.CaATP_block = np.ones(30)
        sim.NaKATP_block = sim.gj_block = sim.rho_channel = sim.rho_pump = 1
        sim.T = 310.15
        state = legacy.event_snapshot(sim)
        _, mapped = ctx.mapping(row)
        configured = {
            "name": "Base",
            "diffusion_m2_per_s": {
                ion: float(sim.Dm_cells[i, 0])
                for i, ion in enumerate(prior["base_protocol"]["expected_species"])
            },
        }
        enabled, zero = mapped["profiles_enabled"], row["variant"] == "zero_amplitude"
        scheduled = dict.fromkeys(("Na_mem", "K_mem", "Cl_mem", "Ca_mem", "pressure", "ecmJ"), 0)
        if zero:
            for ion in ("Na", "K", "Cl"):
                scheduled[ion + "_mem"] = [*mapped["mapped_pulse_times_s"], 0.0, ["Base"], "None"]
        metadata = {
            "phase": "SIM",
            "run_sim_flag": True,
            "profiles_enabled": enabled,
            "dt_s": row["dt_s"],
            "sampling_s": row["dt_s"],
            "duration_s": plan["duration_s"],
            "configured_steps": mapped["steps"],
            "sample_stride": 1,
            "geometry": prior["geometry"],
            "constants": prior["base_protocol"]["profiles"][row["profile"]],
            "settings": prior["settings"],
            "thickness_m": prior["base_protocol"]["thickness_m"],
            "species": prior["base_protocol"]["expected_species"],
            "moving_ion_indices": list(range(6)),
            "configured_default": configured,
            "resolved_default": configured if enabled else None,
            "profile_names": ["Base"] if enabled else [],
            "additional_profile_count": 0,
            "cut_profile_count": 0,
            "membrane_targets": {"Base": list(range(30))} if enabled else {},
            "cell_targets": {"Base": list(range(7))} if enabled else {},
            "scheduled_options": scheduled,
            "global_options": dict.fromkeys(
                ("K_env", "Cl_env", "Na_env", "gj_block", "T_change", "NaKATP_block"), 0
            ),
            "cut_event_configured": True,
            "cut_event_enabled": False,
            "voltage_event_configured": False,
            "voltage_event_enabled": False,
            "event_targets": {ion: list(range(30)) for ion in ("Na", "K", "Cl")} if zero else {},
            "paths": {
                "seed": "INITS/world_1.betse.gz",
                "init": "INITS/init_1.betse.gz",
                "sim": "SIMS/sim_1.betse.gz",
            },
            "pickles_present": {"seed": True, "init": False, "sim": False},
        }
        junctions = {
            "weights": native.array_record(np.ones(30)),
            "membrane_neighbours": list(range(30)),
            "cell_neighbours": [[] for _ in range(7)],
        }
        core = {
            "arrays": legacy.arrays(sim, legacy.CORE_ARRAYS),
            "geometry": prior["geometry"],
            "junctions": junctions,
        }
        dispatch = {
            "mode": "preparation_dispatch_only",
            "initial": None,
            "hook_restored": True,
            "integration_calls": 0,
            "events": [
                {
                    "index": index,
                    "raw_label_s": mapped["raw_clock_scale"] * t,
                    "before": copy.deepcopy(state),
                    "after": copy.deepcopy(state),
                    "flux_ion_indices": [],
                }
                for index, t in enumerate(plan["dispatch_elapsed_times_s"])
            ],
        }
        packets[identifier] = copy.deepcopy(
            {
                "core": core,
                "dynamics": core,
                "ready": {
                    "row": row,
                    "mapping": mapped,
                    "state": state,
                    "initial": initial,
                    "preparation_calls": check.PREPARATION_CALLS,
                    "hook_restored": True,
                },
                "metadata": metadata,
                "dispatch": dispatch,
                "final": {"state": state, "metadata": metadata, "junctions": junctions},
            }
        )
        retained[identifier] = reference
    return directory, packets, retained


@pytest.mark.parametrize(
    "case,variant", [(case, variant) for case in ("passive", "blocked") for variant in ctx.VARIANTS]
)
def test_synthetic_preparation_gates(case, variant, synthetic, plan, prior):
    _, packets, retained = synthetic
    packet = packets[case, variant]
    assert (
        check.check_row(packet["ready"]["row"], packet, prior, retained[case, variant], plan)[
            "status"
        ]
        == "preparation_checks_pass"
    )


def test_synthetic_three_control_comparison(synthetic, plan):
    assert check.check_controls(synthetic[1], plan)["comparisons"] == 4


@pytest.mark.parametrize(
    "fault",
    [
        "phase",
        "profile",
        "target",
        "extra_profile",
        "cut",
        "voltage",
        "global",
        "clock",
        "event_clock",
        "event_missing",
        "event_change",
        "dtype",
        "shape",
        "hash",
        "partial",
        "calls",
        "diffusion",
        "neighbours",
        "picker",
        "pump",
        "temperature",
        "loaded_state",
    ],
)
def test_rejects_corrupted_preparation_or_event_evidence(fault, synthetic, plan, prior):
    _, packets, retained = synthetic
    packet = copy.deepcopy(packets["passive", "zero_amplitude"])
    row, m = packet["ready"]["row"], packet["metadata"]
    if fault == "phase":
        m["phase"] = "INIT"
    elif fault == "profile":
        m["profiles_enabled"] = False
    elif fault == "target":
        m["event_targets"]["Na"].pop()
    elif fault == "extra_profile":
        m["additional_profile_count"] = 1
    elif fault == "cut":
        m["cut_event_enabled"] = True
    elif fault == "voltage":
        m["voltage_event_enabled"] = True
    elif fault == "global":
        m["global_options"]["T_change"] = 1
    elif fault == "clock":
        m["dt_s"] = 0.0001
    elif fault == "event_clock":
        packet["dispatch"]["events"][1]["raw_label_s"] += 0.001
    elif fault == "event_missing":
        packet["dispatch"]["events"].pop()
    elif fault == "event_change":
        packet["dispatch"]["events"][1]["after"]["temperature_K"] += 1
    elif fault == "dtype":
        packet["ready"]["state"]["arrays"]["vm"]["dtype"] = "<f4"
    elif fault == "shape":
        packet["core"]["arrays"]["cc_cells"]["shape"] = [42]
    elif fault == "hash":
        packet["ready"]["state"]["arrays"]["vm"]["bytes_sha256"] = "0" * 64
    elif fault == "partial":
        del packet["core"]
    elif fault == "calls":
        packet["ready"]["preparation_calls"]["seed"] = 0
    elif fault == "diffusion":
        m["configured_default"]["diffusion_m2_per_s"]["Na"] = 0.0
    elif fault == "neighbours":
        packet["core"]["junctions"]["membrane_neighbours"][0] = 30
    elif fault == "picker":
        m["cell_targets"]["Base"].pop()
    elif fault == "pump":
        packet["ready"]["state"]["rho_pump"] = 2
    elif fault == "temperature":
        packet["ready"]["state"]["temperature_K"] = 300
    else:
        m["pickles_present"]["init"] = True
    with pytest.raises(ValueError):
        check.check_row(row, packet, prior, retained["passive", "zero_amplitude"], plan)


def test_absent_default_is_valid_only_for_profiles_off(synthetic, plan, prior):
    _, packets, retained = synthetic
    for variant in ("baseline", "default_profile"):
        packet = copy.deepcopy(packets["passive", variant])
        m = packet["metadata"]
        m["resolved_default"] = m["configured_default"] if variant == "baseline" else None
        with pytest.raises(ValueError, match="profile presence"):
            check.check_row(
                packet["ready"]["row"], packet, prior, retained["passive", variant], plan
            )


def test_missing_control_is_not_a_successful_matrix(synthetic, plan):
    packets = dict(synthetic[1])
    del packets["blocked", "zero_amplitude"]
    with pytest.raises(ValueError, match="Incomplete"):
        check.check_controls(packets, plan)


def test_saved_native_attempt_is_complete_or_explicitly_failed(prior, plan):
    """A passing software test never promotes a failed/partial native preflight."""
    if (SESSION / "failure.json").exists():
        failure = c.read(SESSION / "failure.json")
        assert failure["status"] == "fail" and failure["trajectory_qualified"] is False
        assert not (SESSION / "completion.json").exists()
        assert all(
            c.sha(SESSION / name) == digest for name, digest in failure["files_sha256"].items()
        )
        return
    completed = c.read(SESSION / "completion.json")
    assert (
        completed["status"] == "preparation_checks_pass"
        and completed["trajectory_qualified"] is False
    )
    assert completed["preparations"] == 6 and completed["event_dispatch_calls"] == 30
    assert all(
        c.sha(SESSION / name) == digest for name, digest in completed["files_sha256"].items()
    )
    assert c.read(SESSION / "registration.json")["sources"] == old.sources()
    packets = {}
    for index, row in enumerate(ctx.rows(plan)):
        directory = SESSION / f"preparation-{index:02d}"
        result = c.read(directory / "result.json")
        assert result["row"] == row
        packet = {name: c.read(directory / (name + ".json")) for name in check.STAGES}
        reference_path = (
            evidence.SESSION
            / "native"
            / old.key(row["case"]["id"], row["profile"], row["dt_s"])
            / "observed/result.json"
        )
        assert c.sha(reference_path) == result["retained_init_sha256"]
        check.check_row(row, packet, prior, c.read(reference_path), plan)
        packets[row["case"]["id"], row["variant"]] = packet
    assert check.check_controls(packets, plan)["status"] == "exact_preparation_controls_pass"
    assert not any(name == "betse" or name.startswith("betse.") for name in sys.modules)
