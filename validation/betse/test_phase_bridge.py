"""Bounded adapter mapping and strict preparation gates; never launch native work."""

import ast
import copy
import hashlib
import sys
import zipfile

import contact as c
import intervention_design as design
import phase_bridge as bridge
import phase_bridge_context as ctx
import pytest
import trajectory_context as old
import trajectory_evidence as evidence


@pytest.fixture(scope="module")
def prior():
    return evidence.trusted_registration()


def test_predecessor_and_accepted_sources_are_unchanged():
    assert len(ctx.authenticate()["implementation_files_sha256"]) == 352


@pytest.mark.parametrize("case_id", ["passive", "blocked"])
@pytest.mark.parametrize("dt", [0.000025, 0.0000125, 0.00000625])
@pytest.mark.parametrize("mode", ctx.EVENT_MODES)
def test_mapping_preserves_old_preparation_and_declares_sim_clock_and_noop(
    case_id, dt, mode, prior
):
    case = next(case for case in prior["protocol"]["cases"] if case["id"] == case_id)
    original = old.native_protocol(case, dt)
    unchanged = copy.deepcopy(original)
    mapped, info = ctx.mapping(case, dt, mode)
    after = {tuple(path): value for path, value in mapped["yaml_overrides"]}
    assert original == unchanged
    assert all(after[tuple(path)] == value for path, value in original["yaml_overrides"])
    assert after[("sim time settings", "time step")] == dt
    assert after[("sim time settings", "sampling rate")] == dt
    assert after[("sim time settings", "total time")] == 0.001
    for ion in ("Na", "K", "Cl"):
        group = "change " + ion + " mem"
        assert after[(group, "event happens")] is (mode == "zero_amplitude")
        assert after[(group, "multiplier")] == 0
        assert after[(group, "modulator function")] == "None"
        assert after[(group, "apply to")] == ["Base"]
        assert [
            after[(group, field)] for field in ("change start", "change finish", "change rate")
        ] == info["mapped_pulse_times_s"]
    assert info["raw_clock_scale"] == info["steps"] / (info["steps"] - 1)


@pytest.mark.parametrize(
    "case,dt,mode",
    [
        ({"id": "passive", "availability": 0.5}, 0.000025, "disabled"),
        ({"id": "passive", "availability": 1.0}, 0.0001, "disabled"),
        ({"id": "passive", "availability": 1.0}, True, "disabled"),
        ({"id": "passive", "availability": 1.0}, float("nan"), "disabled"),
        ({"id": "passive", "availability": 1.0}, 0.000025, "pulse"),
    ],
)
def test_mapping_rejects_nonbridge_inputs(case, dt, mode):
    with pytest.raises(ValueError):
        ctx.mapping(case, dt, mode)


def test_bounded_preflight_has_no_trajectory_or_solver_control():
    plan = ctx.preflight_plan()
    assert plan["trajectory_run"] is plan["trajectory_qualified"] is False
    assert len(plan["rows"]) == 4
    assert len(plan["dispatch_elapsed_times_s"]) == 5
    assert plan["worker_timeout_seconds"] == 25
    assert plan["max_artifact_bytes"] == 16 * 1024 * 1024
    assert all(row["profile"] == "matched_constants" for row in plan["rows"])


def test_missing_and_fabricated_preparation_arrays_are_rejected():
    with pytest.raises(ValueError, match="coverage"):
        bridge.check_arrays({}, bridge.CORE_ARRAYS)
    with pytest.raises(ValueError, match="scalar"):
        bridge.check_arrays({"cc_cells": {"scalar": 1}}, ("cc_cells",))
    with pytest.raises(ValueError, match="scalar"):
        bridge.check_arrays({"gj_block": {"scalar": True}}, ("gj_block",))


def test_flatten_is_shape_agnostic_without_numpy():
    assert list(bridge.flatten([[1, 2], [3, 4]])) == [1, 2, 3, 4]
    assert list(bridge.flatten(1)) == [1]


@pytest.mark.parametrize("mode", ctx.EVENT_MODES)
def test_profile_prerequisite_does_not_silently_enable_tissues(mode):
    protocol, _ = ctx.mapping({"id": "passive", "availability": 1.0}, 0.000025, mode)
    before = copy.deepcopy(protocol)
    if mode == "disabled":
        ctx.require_dispatch_profiles(protocol)
    else:
        with pytest.raises(ValueError, match="require tissue profiles"):
            ctx.require_dispatch_profiles(protocol)
    assert protocol == before


def test_unamended_plan_is_rejected_without_another_worker_or_output_directory(tmp_path):
    output = tmp_path / "must-not-launch"
    with pytest.raises(ValueError, match="versioned profile bridge"):
        bridge.preflight(output)
    assert not output.exists()
    assert not any(name == "betse" or name.startswith("betse.") for name in sys.modules)


def test_pinned_source_returns_before_creating_default_tissue_when_profiles_disabled():
    source = (c.SOURCE / "betse/science/tissue/tishandler.py").read_text()
    init = design.method(source, "_init_tissues")
    guards = [
        node
        for node in init.body
        if isinstance(node, ast.If) and ast.unparse(node.test) == "not p.is_tissue_profiles"
    ]
    assert len(guards) == 1 and isinstance(guards[0].body[0], ast.Return)
    defaults = [
        node
        for node in ast.walk(init)
        if isinstance(node, ast.Assign)
        and any(ast.unparse(target) == "self.tissue_default" for target in node.targets)
    ]
    assert len(defaults) == 1 and guards[0].lineno < defaults[0].lineno
    event_setup = design.method(source, "_finalize_events_tissue")
    assert any(
        isinstance(node, ast.Subscript) and ast.unparse(node) == "self.tissue_target_inds[profile]"
        for node in ast.walk(event_setup)
    )


def test_failed_native_preflight_is_retained_and_not_qualified():
    output = c.ROOT / "runs/ref-003e0-2026-09-12/preflight-01"
    anchors = {
        "failure.json": "a59ff3debb871735a8376a0a18805a3aadb0ca2d899518cb6520819261a59c95",
        "registration.json": "56e3a3b4eeca2a697ac4a002557fd1e13b7d5a706000837df5b50abaa46d75bb",
        "sources.zip": "a55df2422cddacd02de18eb7af57bb4793e98c42575505f11e9f44eddcae0c24",
        "worker.log": "e844f3e4dea0f065e9506a9f9abc51029e845bf7ffb133f2edc961146394fe8a",
        "preparation-00/native.yaml": (
            "b917937e837098aa913a7e031186f6261b47c2c45b320e4fd011c959532e3708"
        ),
        "preparation-00/INITS/world_1.betse.gz": (
            "d3cd0fbb27cc489d661b5f5060a27fe0b1dcf4d93f92cc9c0e2abe8ae659c973"
        ),
    }
    assert {
        str(path.relative_to(output)): c.sha(path) for path in output.rglob("*") if path.is_file()
    } == anchors
    failed = c.read(output / "failure.json")
    assert failed["status"] == "fail" and failed["trajectory_qualified"] is False
    assert "no attribute 'tissue_default'" in (output / "worker.log").read_text()
    assert not (output / "completion.json").exists()
    assert not (output / "worker.json").exists()
    assert not (output / "preparation-00/result.json").exists()
    registered = c.read(output / "registration.json")
    with zipfile.ZipFile(output / "sources.zip") as archive:
        assert set(archive.namelist()) == set(registered["sources"])
        assert all(
            hashlib.sha256(archive.read(name)).hexdigest() == digest
            for name, digest in registered["sources"].items()
        )
