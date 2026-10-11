"""Actual D077 evidence and offline guards; no arithmetic audit or simulation run."""

import copy
import hashlib
import json
import os
import shutil
import struct
import subprocess
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace

import contact as c
import expanded_audit as audit
import expanded_audit_context as ctx
import expanded_audit_job as job
import pytest


@pytest.fixture(scope="module")
def registered():
    return audit.trusted_registration()


@pytest.fixture(scope="module")
def prepared():
    return audit.prepared_rows()


@pytest.fixture(scope="module")
def prior():
    return audit.previous.trusted_registration()


@pytest.fixture(scope="module")
def nonce():
    return audit.shared.voltage_nonce()


@pytest.fixture(scope="module")
def first(registered):
    return audit.shared.read_row(ctx.SESSION, registered["rows"][0], "observed")


def test_captured_sources_production_and_prior_evidence_are_preserved():
    assert len(ctx.authenticate()["implementation_files_sha256"]) == 352
    assert len(ctx.packet_hashes()) == 802


def test_manifest_capsule_metadata_and_registered_coverage():
    registered, capture = audit.inspect_packet(ctx.SESSION)
    assert len(registered["sources"]) == 67 and len(capture["files_sha256"]) == 798
    assert len(audit.expected_rows()) == 36
    assert capture["expanded_bridge_qualified"] is False
    assert sum(266 + 364 * audit.count(r) for r in registered["rows"]) == ctx.COMPARISONS


@pytest.mark.parametrize("index", range(36))
@pytest.mark.parametrize("mode", audit.MODES)
def test_actual_saved_rows_across_constants_timesteps_and_variants(
    registered, prepared, prior, nonce, index, mode
):
    row = registered["rows"][index]
    packet = audit.shared.read_row(ctx.SESSION, row, mode)
    steps = audit.audit_row(
        row, mode, packet, prepared, c.read(audit.pilot.retained_path(row, mode)), prior, nonce
    )
    assert steps == (audit.count(row) if mode == "observed" else 0)
    if audit.is_overlap(row):
        audit.audit_overlap(row, mode, packet)


def test_actual_controls_are_checked_group_by_group(registered):
    counts = {"observer_pairs": 0, "variant_comparisons": 0}
    baseline = None
    for row in registered["rows"]:
        pair = {mode: audit.shared.read_row(ctx.SESSION, row, mode) for mode in audit.MODES}
        audit.audit_pair(pair["observed"], pair["unobserved"])
        counts["observer_pairs"] += 1
        if row["variant"] == "baseline":
            baseline = pair["observed"]
        else:
            audit.audit_variant(baseline, pair["observed"])
            counts["variant_comparisons"] += 1
    assert counts == {"observer_pairs": 36, "variant_comparisons": 24}


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
        (("entry", "pre_loop_calls", "init_dynamics"), 2),
        (("entry", "sampled_indices"), []),
        (("metadata", "configured_steps"), 160),
        (("metadata", "constants", "R"), 8.31446261815324),
        (("events", "mode"), "preparation_dispatch_only"),
        (("events", "integration_calls"), 0),
        (("events", "hook_restored"), False),
        (("events", "events", 0, "index"), 1),
        (("events", "events", 0, "raw_label_s"), 0.001),
        (("events", "events", 0, "flux_ion_indices"), [0, 1, 2]),
        (("events", "events", 0, "after", "temperature_K"), 311.0),
        (("events", "events", 0, "before_update", "arrays", "vm", "dtype"), "<f4"),
        (("events", "events", 0, "before_update", "arrays", "cc_cells", "shape"), [7, 6]),
        (("result", "final_metadata", "pickles_present", "init"), True),
        (("result", "final_metadata", "pickles_present", "sim"), False),
        (("checks", "observed_steps"), 160),
    ],
)
def test_corrupted_row_evidence_is_rejected(registered, prepared, prior, nonce, first, path, value):
    row = registered["rows"][0]
    changed = copy.deepcopy(first)
    modify(changed, path, value)
    with pytest.raises(ValueError):
        audit.audit_row(
            row, "observed", changed, prepared, c.read(audit.pilot.retained_path(row)), prior, nonce
        )


@pytest.mark.parametrize("field", ["vm", "cc_cells", "Dm_scheduled", "fluxes_mem", "I_mem"])
def test_rehashed_event_arrays_still_need_physical_links(
    registered, prepared, prior, nonce, first, field
):
    row = registered["rows"][0]
    changed = copy.deepcopy(first)
    record = changed["events"]["events"][0]["before_update"]["arrays"][field]
    values = record["values"]
    while isinstance(values[0], list):
        values = values[0]
    values[0] += 0.001
    record["bytes_sha256"] = hashlib.sha256(
        b"".join(struct.pack("<d", v) for v in audit.arithmetic.numbers(record["values"]))
    ).hexdigest()
    audit.arithmetic.unpack(record)
    with pytest.raises(ValueError):
        audit.audit_row(
            row, "observed", changed, prepared, c.read(audit.pilot.retained_path(row)), prior, nonce
        )


def test_source_nonce_cannot_be_replaced_by_unchanged_voltage(registered, prepared, prior, first):
    row = registered["rows"][0]
    with pytest.raises(ValueError, match="nonce"):
        audit.audit_row(
            row, "observed", first, prepared, c.read(audit.pilot.retained_path(row)), prior, 0.0
        )


def test_profile_clock_mapping_does_not_reuse_25_us_metadata(registered, prepared, prior, nonce):
    row = next(
        r
        for r in registered["rows"]
        if r["variant"] == "zero_amplitude" and r["dt_s"] == 0.00000625
    )
    packet = audit.shared.read_row(ctx.SESSION, row, "observed")
    packet["metadata"]["scheduled_options"] = audit.expected_metadata(
        row | {"dt_s": 0.000025}, prepared, prior
    )["scheduled_options"]
    with pytest.raises(ValueError, match="preparation"):
        audit.audit_row(
            row, "observed", packet, prepared, c.read(audit.pilot.retained_path(row)), prior, nonce
        )


@pytest.fixture(scope="module")
def metadata(registered):
    return [
        registered,
        *[
            c.read(ctx.SESSION / n)
            for n in ("capture.json", "worker.json", "launch.json", "started.json")
        ],
    ]


@pytest.mark.parametrize(
    "index,path,value",
    [
        (1, ("status",), "pass"),
        (1, ("expanded_bridge_qualified",), True),
        (1, ("observed_steps",), 240),
        (1, ("native_runs",), 12),
        (1, ("elapsed_seconds",), 661),
        (1, ("finished_utc",), "2026-09-11T00:00:00+00:00"),
        (1, ("accepted_implementation_files_unchanged",), 1),
        (2, ("enabled_target_event_dispatches_observed",), 3360),
        (2, ("environment", "packages", "numpy"), "0.0.0"),
        (2, ("installed_python_sha256", "betse/science/sim.py"), "0" * 64),
        (2, ("warnings",), ["unexpected"]),
        (2, ("observer_pairs",), []),
        (2, ("variant_controls",), []),
        (2, ("pilot_overlap",), []),
        (2, ("results",), []),
        (3, ("automatic_polling",), True),
        (4, ("pid",), 1),
    ],
)
def test_metadata_claims_are_checked_independently_of_digest_acceptance(
    metadata, index, path, value
):
    changed = copy.deepcopy(metadata)
    modify(changed[index], path, value)
    with pytest.raises(ValueError):
        audit.inspect_metadata(*changed)


@pytest.fixture
def linked_copy():
    # Hard links require the same filesystem. Keep temporary test copies outside
    # the frozen packet but beside it, and unlink before writing any mutation.
    with tempfile.TemporaryDirectory(prefix="audit-test-", dir=ctx.SESSION.parent) as temporary:
        path = Path(temporary) / "packet"
        shutil.copytree(ctx.SESSION, path, copy_function=os.link)
        yield path


def replace(path, value):
    path.unlink()
    c.write(path, value)


def test_missing_payload_cannot_be_hidden_by_rehashing(linked_copy, registered):
    name = "native/passive/source_constants/0.00002500/baseline/observed/events.json"
    (linked_copy / name).unlink()
    receipt = c.read(linked_copy / "capture.json")
    del receipt["files_sha256"][name]
    replace(linked_copy / "capture.json", receipt)
    with pytest.raises(ValueError, match="coverage"):
        audit.verify_manifest(linked_copy, registered)


def test_symlink_payload_is_rejected(linked_copy, registered):
    p = linked_copy / "worker.log"
    p.unlink()
    p.symlink_to(ctx.SESSION / "worker.log")
    with pytest.raises(ValueError, match="link"):
        audit.verify_manifest(linked_copy, registered)


def test_rehashed_capsule_corruption_is_not_accepted(tmp_path, registered):
    with zipfile.ZipFile(ctx.SESSION / "sources.zip") as original:
        content = {n: original.read(n) for n in original.namelist()}
    content["full_loop_observer.py"] += b"\n# unexpected change\n"
    with zipfile.ZipFile(tmp_path / "sources.zip", "x") as changed:
        for name, data in content.items():
            changed.writestr(name, data)
    assert c.sha(tmp_path / "sources.zip") != ctx.ANCHORS["sources.zip"]
    with pytest.raises(ValueError, match="capsule bytes"):
        audit.check_capsule(tmp_path, registered)


@pytest.mark.parametrize("module", ["cells", "betse.science.sim", "numpy", "jax.numpy"])
def test_model_and_array_imports_are_refused(module):
    with pytest.raises(RuntimeError, match="forbids"):
        audit.shared.ImportFence().find_spec(module)


def test_metadata_inspection_imports_no_model_array_or_capture_checker():
    code = """
import sys
import expanded_audit as a
sys.meta_path.insert(0, a.shared.ImportFence())
a.inspect_packet(a.ctx.SESSION)
assert not any(n.split('.')[0] in a.shared.FORBIDDEN for n in sys.modules)
assert 'expanded_bridge_check' not in sys.modules and 'full_loop_bridge_check' not in sys.modules
print('offline expanded metadata checked')
"""
    result = subprocess.run(
        [str(c.CELLS_PYTHON), "-B", "-c", code],
        cwd=c.HERE,
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    assert result.stdout.strip() == "offline expanded metadata checked"


def test_variant_comparison_labels_are_unambiguous():
    checks = audit.VariantChecks()
    for variant in audit.VARIANTS:
        checks.variant = variant
        checks.compare("same-row", 2.0, 0.0, "unit", {"unit": 1.0, "relative": 0.0})
    assert [v["id"] for v in checks.failures] == [v + "/same-row" for v in audit.VARIANTS]


def test_commands_do_not_launch_either_simulator_or_a_full_matrix(tmp_path):
    commands = job.stage_commands(tmp_path)
    assert [name for name, _ in commands] == ["audit", "regression"]
    text = json.dumps(commands)
    assert str(c.REFERENCE_PYTHON) not in text and '"expanded_bridge.py"' not in text
    assert "test_expanded_bridge.py" in text and "test_saved_expanded.py" in text
    assert "test_full_loop_observer.py" in text and "--receipt" in text
    assert len(ctx.JOB_PLAN["test_modules"]) == 5


def synthetic_audit_result():
    return {
        "schema": "cells.betse_expanded_bridge_audit@1",
        "status": "pass",
        "scope": audit.SCOPE,
        "anchors": ctx.ANCHORS,
        "comparisons": ctx.COMPARISONS,
        "failed_comparisons": 0,
        "maximum_normalized_error": 0.5,
        "failures": [],
        "observed_steps": 3360,
        "controls": audit.CONTROLS,
        "enabled_target_event_dispatches": 1120,
        "payload_files": 798,
        "capsule_sources": 67,
        "row_summaries": [
            {"row": r, "comparisons": 266 + 364 * audit.count(r)} for r in audit.expected_rows()
        ],
        "model_imports": [],
        "production_calls": 0,
        "criteria_registration_sha256": audit.previous.ANCHORS["registration.json"],
        "driver_sha256": c.sha(c.HERE / "expanded_audit.py"),
        "qualification_pending_regression_closeout": True,
        "trajectory_qualified": False,
        "expanded_bridge_qualified": False,
        "capture_rerun": False,
        "nonzero_intervention": False,
        "restart_qualified": False,
        "biology_validated": False,
        "gpu_tested": False,
        "cells_runs": 0,
    }


def test_closeout_requires_the_full_independent_result():
    job.validate_audit(synthetic_audit_result(), {"sources": ctx.sources()})


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "fail"),
        ("comparisons", 88956),
        ("observed_steps", 240),
        ("row_summaries", []),
        ("controls", {"observer_pairs": 6}),
        ("failed_comparisons", 1),
        ("maximum_normalized_error", 1.01),
        ("model_imports", ["numpy"]),
        ("production_calls", 1),
        ("expanded_bridge_qualified", True),
        ("cells_runs", 8),
    ],
)
def test_closeout_rejects_incomplete_or_overclaimed_audits(field, value):
    result = synthetic_audit_result()
    result[field] = value
    with pytest.raises(ValueError):
        job.validate_audit(result, {"sources": ctx.sources()})


def test_timeout_preserves_evidence_and_does_not_run_regression(tmp_path, monkeypatch):
    c.write(tmp_path / "registration.json", {"synthetic": True})
    monkeypatch.setattr(job, "validate_registration", lambda _: None)
    monkeypatch.setattr(job, "check_capsule", lambda *_: None)
    attempts = []

    def timeout(*args, **kwargs):
        attempts.append(kwargs)
        raise subprocess.TimeoutExpired("synthetic audit", kwargs["timeout"])

    monkeypatch.setattr(job.subprocess, "run", timeout)
    with pytest.raises(subprocess.TimeoutExpired):
        job.execute(tmp_path)
    failure = c.read(tmp_path / "failure.json")
    assert len(attempts) == 1 and attempts[0]["timeout"] <= 180
    assert failure["automatic_retry"] is failure["capture_rerun"] is False
    assert failure["expanded_bridge_qualified"] is False
    assert "audit.log" in failure["files_sha256"]
    assert (
        not (tmp_path / "completion.json").exists() and not (tmp_path / "regression.log").exists()
    )


def test_detached_launch_does_not_poll(tmp_path, monkeypatch):
    c.write(tmp_path / "registration.json", {"synthetic": True})
    monkeypatch.setattr(job, "register", lambda _: None)
    calls = []

    def popen(*args, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(pid=23456)

    monkeypatch.setattr(job.subprocess, "Popen", popen)
    job.launch(tmp_path)
    result = c.read(tmp_path / "launch.json")
    assert len(calls) == 1 and calls[0]["start_new_session"] is True
    assert result["automatic_polling"] is False and result["automatic_expansion"] is False
