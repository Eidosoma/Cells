"""Bounded saved-state checks and negative controls; no solver execution."""

import copy
import importlib
import math
import os
import struct
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ctx = importlib.import_module("release_audit_context")
control = importlib.import_module("release_audit_math")
native = importlib.import_module("release_audit_native")
cm = importlib.import_module("release_audit_cells")
replay = importlib.import_module("release_audit_replay")
job = importlib.import_module("release_audit_job")
c, io, am = ctx.c, ctx.io, control.am
CONDITIONS = ("baseline", "no_op", "static_blocked", "suppression_release")


@pytest.fixture(scope="module")
def data():
    with ctx.model_fence():
        return ctx.load_capture()


@pytest.fixture(scope="module")
def histories(data):
    result = {}
    saved = io.read_compressed(ctx.CAPTURE / "native-accounting.json.gz")["by_history"]
    with ctx.model_fence():
        for name, view in data["registration"]["views"].items():
            h = replay.History(
                name,
                view,
                {
                    "cells": data["workers"]["cells"]["by_history"][name],
                    "betse": data["workers"]["betse"],
                },
            )
            # Only routing tests use these saved outputs; native equations are tested separately.
            h.native_points, h.native_sides = saved[name]["points"], saved[name]["sides"]
            result[name] = h
    return result


@pytest.fixture(scope="module")
def rows():
    return {
        (h, v): io.read_compressed(
            ctx.CAPTURE / h / "native" / v / "dt_2.5e-05/observed/result.json.gz"
        )
        for h in ("a", "b")
        for v in CONDITIONS
    }


def audit_shell(data, histories, output):
    audit = replay.Audit.__new__(replay.Audit)
    audit.data, audit.output = data, output
    audit.r = data["registration"] | {
        "protocol": c.read(replay.frozen.paired_compare.ctx.PROTOCOL)
        | {
            "variants": list(CONDITIONS),
            "common_times_s": data["registration"]["plan"]["common_times_s"],
        }
    }
    audit.histories, audit.ledgers, audit.writes, audit.contrasts = histories, [], set(), {}
    return audit


def test_capture_authenticates_without_models(data):
    assert len(data["hashes"]) == 555 and len(ctx.sources()) == 203
    assert len(ctx.payloads(data["registration"])) == 551
    assert data["completion"]["coarse_diagnostic_failures"] == 49
    assert data["registration"]["tests"]["tests"] == 121


@pytest.mark.parametrize("fault", ["count", "missing", "extra", "bytes", "qualification"])
def test_provenance_corruption_rejected(data, fault):
    done, hashes = copy.deepcopy(data["completion"]), data["hashes"].copy()
    if fault == "count":
        done["coarse_diagnostic_failures"] = 0
    elif fault == "missing":
        hashes.pop("a/cells-sides.json.gz")
    elif fault == "extra":
        hashes["unexpected"] = "0" * 64
    elif fault == "bytes":
        hashes["a/cells-sides.json.gz"] = "0" * 64
    else:
        done["release_response_qualified"] = True
    with pytest.raises(ValueError):
        ctx.provenance(data["registration"], done, data["workers"], hashes)


@pytest.mark.parametrize("module", ctx.FORBIDDEN)
def test_model_imports_forbidden(module):
    with ctx.model_fence(), pytest.raises(RuntimeError, match="forbidden"):
        importlib.import_module(module)


@pytest.mark.parametrize("condition", CONDITIONS)
@pytest.mark.parametrize(
    "time_s,side",
    [
        (0.0, "left"),
        (0.0005, "left"),
        (0.0005, "right"),
        (0.001, "left"),
        (0.001, "right"),
        (0.002, "right"),
    ],
)
def test_independent_input_clock(data, condition, time_s, side):
    schedule = data["registration"]["views"]["a"]["schedules"][condition]
    assert control.availability(schedule, time_s, side) == ctx.pilot.availability(
        schedule, time_s, side
    )


@pytest.mark.parametrize("value", [4.0, 4.000000000000001, 12.0, 140.0, 1e-12])
def test_rational_source_order_mean(value):
    values = [value] * 30
    assert control.ordered_mean(values) == replay.native_check.remix.mean30(values)
    old = value
    for _ in range(6):
        old += 1e-25
    assert control.nonce_voltage([value]) == [old]


@pytest.mark.parametrize("history", ["a", "b"])
@pytest.mark.parametrize("condition", CONDITIONS)
def test_native_inputs_first_step_and_side_probes(data, rows, history, condition):
    view, row = data["registration"]["views"][history], rows[history, condition]
    native.inputs(view, row)
    _, metrics = next(native.steps(view, row))
    budgets = view["preparation_registration"]["transport_protocol"]["tolerances"] | {
        "amount_fmol": native.accumulated_atol(view, row)
    }
    for a, b, unit in metrics.values():
        am.ind.near(a, b, budgets[unit], budgets["relative"])
    for side in (None, "left", "right"):
        values, points = native.probes(view, row, side)
        assert len(points) == (8 if side is None else 2)
        for a, b, unit in values.values():
            am.ind.near(a, b, budgets[unit], budgets["relative"])


@pytest.mark.parametrize(
    "fault",
    ["index", "availability", "baseline", "restoration", "inventory", "state", "mean", "nonce"],
)
def test_native_corruption_rejected(data, rows, fault):
    view = data["registration"]["views"]["a"]
    row = copy.deepcopy(rows["a", "suppression_release"])
    receipt = row["timed_input"]["applications"][-1]
    if fault == "index":
        receipt["completed_updates"] -= 1
    elif fault == "availability":
        row["timed_input"]["intervals"][20]["availability"] = 1
    elif fault == "baseline":
        receipt["baseline_maxDm_m2_per_s"] = 0
    elif fault == "restoration":
        receipt["applied_maxDm_m2_per_s"] = 0
    elif fault == "inventory":
        receipt["numeric_inventory"]["numeric"]["gates/m"]["bytes_sha256"] = "0" * 64
    elif fault == "state":
        receipt["after"]["channel"]["m"][0] = 0
    elif fault == "mean":
        value = row["trace"]["steps"][0]["after_ordinary"]["physical"]["outside_mM"][1][0]
        row["trace"]["steps"][0]["after_ordinary"]["physical"]["outside_mM"][1] = [
            math.nextafter(value, math.inf)
        ] * 30
    else:
        row["trace"]["steps"][0]["before"]["physical"]["voltage_V"][0] += 1e-15
    with pytest.raises(ValueError):
        native.inputs(view, row)
        next(native.steps(view, row))


def test_complete_coarse_native_case_replays_every_column(data, histories, tmp_path):
    audit = audit_shell(data, histories, tmp_path)
    h = histories["a"]
    key = "suppression_release/dt_2.5e-05"
    row = io.read_compressed(h.capture / "native" / key / "observed/result.json.gz")
    budgets = h.r["preparation_registration"]["transport_protocol"]["tolerances"] | {
        "amount_fmol": native.accumulated_atol(h.r, row)
    }
    ledger = audit.ledger_type(replay.native_check.Ledger, native=True)(
        budgets, h.capture / "native" / key / "boundary-failures.jsonl"
    )
    variant = next(
        v
        for v in h.r["preparation_registration"]["transport_protocol"]["variants"]
        if v["id"] == "active_channel"
    )
    registration = ctx.pilot.feedback.loop_registration(h.r, row["dt_s"])
    with ctx.model_fence(), replay.capture_write_guard(ctx.CAPTURE):
        replay.native_check.observed(registration, variant, row, ledger)
        replay.native_check.points(h.r, row, variant, ledger)
        for side in ("left", "right"):
            replay.native_check.points(h.r, row, variant, ledger, side)
    summary = ledger.summary()
    assert summary["status"] == "pass" and ledger.count > 250000
    assert ledger.count == ledger.independent.count
    assert ledger.independent.failed == ledger.independent.numerical_rejections == 0
    assert len(ledger.remix_records) == 500


@pytest.mark.parametrize("history", ["a", "b"])
def test_definitions_complete_checkpoints_and_refinement(histories, history):
    h = histories[history]
    assert h.checkpoints == 24 and h.checkpoint_arrays == 1296
    assert all(v["status"] == "pass" for v in h.decisions().values())


@pytest.mark.parametrize("condition", CONDITIONS)
@pytest.mark.parametrize("time_s", [0.0, 0.0005, 0.001, 0.002])
def test_checkpoint_event_clock(data, condition, time_s):
    definition = data["registration"]["views"]["a"]["cells_definitions"][
        condition + "/jax_jit/dt_2.5e-05"
    ]
    expected = (
        (int(time_s >= 0.0005) + int(time_s >= 0.001))
        if condition in ("no_op", "suppression_release")
        else 0
    )
    assert cm.event_index(definition, time_s) == expected


@pytest.mark.parametrize("fault", ["clock", "state_hash", "source", "spec", "manifest"])
def test_checkpoint_corruption_rejected(histories, monkeypatch, fault):
    h, key = histories["b"], "suppression_release/jax_jit/dt_2.5e-05"
    directory = h.capture / "cells" / key / "midpoint-checkpoint"
    row = h.cells.records[key]
    manifest = copy.deepcopy(c.read(directory / "manifest.json"))
    sources = manifest["source_hashes"].copy()
    if fault == "clock":
        manifest["clock"]["event_index"] = 0
    elif fault == "state_hash":
        manifest["state_sha256"] = "0" * 64
    elif fault == "source":
        manifest["source_hashes"] = {}
    elif fault == "spec":
        manifest["spec"]["experiment"]["end_time"] = 1
    if fault != "manifest":
        manifest["manifest_sha256"] = cm.digest(
            {k: v for k, v in manifest.items() if k != "manifest_sha256"}
        )
    else:
        manifest["manifest_sha256"] = "0" * 64
    layout = cm.layout_contract("active_channel", "b", "jax_jit")
    monkeypatch.setattr(c, "read", lambda _: manifest)
    with pytest.raises(ValueError):
        cm.checkpoint(directory, row, 40, sources, layout)


@pytest.mark.parametrize("fault", ["version", "object", "fortran", "nan", "extent"])
def test_numeric_decoder_rejects_unsafe_array(fault):
    header = {"descr": "<f8", "fortran_order": False, "shape": (1,)}
    if fault == "object":
        header["descr"] = "|O"
    elif fault == "fortran":
        header["fortran_order"] = True
    elif fault == "extent":
        header["shape"] = (1000001,)
    raw_header = repr(header).encode("ascii")
    raw = (
        b"\x93NUMPY"
        + (b"\x02\x00" if fault == "version" else b"\x01\x00")
        + struct.pack("<H", len(raw_header))
        + raw_header
        + struct.pack("<d", float("nan") if fault == "nan" else 0.0)
    )
    with pytest.raises(ValueError):
        cm.raw_array(raw)


@pytest.mark.parametrize("history", ["a", "b"])
def test_full_side_rhs_frozen_replay(data, histories, tmp_path, monkeypatch, history):
    audit = audit_shell(data, histories, tmp_path)
    h = histories[history]
    with ctx.model_fence(), replay.capture_write_guard(ctx.CAPTURE):
        monkeypatch.setattr(io, "Ledger", audit.ledger_type(io.Ledger))
        result = replay.frozen.check_side_probes(h.r, h.capture, h.workers["cells"])
    assert result == io.read_compressed(h.capture / "cells-sides.json.gz")
    ledger = audit.ledgers[0]
    assert ledger.count == ledger.independent.count == 8960
    assert ledger.independent.failed == ledger.independent.numerical_rejections == 0


@pytest.mark.parametrize("column", ["actual", "expected"])
def test_crosscheck_rejects_corrupted_original_column(tmp_path, column):
    check = am.Crosscheck(tmp_path / "mismatch.jsonl")
    check.add(
        "gate/0",
        1.0 if column == "actual" else 0.0,
        1.0 if column == "expected" else 0.0,
        0.0,
        0.0,
        "gate",
        1e-8,
        2e-11,
    )
    assert check.summary()["column_mismatches"] == 1


@pytest.mark.parametrize("history", ["a", "b"])
def test_dynamic_noop_and_sides_preserve_coarse_misses(
    data, histories, tmp_path, monkeypatch, history
):
    audit = audit_shell(data, histories, tmp_path)
    h = histories[history]
    reference = replay.frozen.reference_view(data["registration"], history)
    native_result = {"points": h.native_points}
    with ctx.model_fence(), replay.capture_write_guard(ctx.CAPTURE):
        monkeypatch.setattr(io, "Ledger", audit.ledger_type(io.Ledger))
        result = replay.frozen.compare.dynamic_checks(
            h.r, h.capture, reference, native_result, {"points": h.cells.points}
        )
        for condition in CONDITIONS:
            oracle = replay.frozen.reference_sides(h.r, condition, reference)
            for engine, step, backend in (
                ("native", h.r["protocol"]["native_steps_s"][-1], None),
                ("cells", h.r["protocol"]["cells_steps_s"][-1], "jax_jit"),
            ):
                key = ctx.pilot.key(condition, step, backend)
                points = h.native_sides[key] if engine == "native" else h.cells.sides[key]
                for side in ("left", "right"):
                    replay.frozen.compare.compare_points(
                        engine + "/" + condition + "/" + side,
                        points[side],
                        oracle[side],
                        h.r["protocol"],
                        h.capture,
                        energy=engine == "cells",
                    )
        for step in h.r["protocol"]["cells_steps_s"]:
            a, b = (
                h.cells.points[ctx.pilot.key(v, step, "jax_jit")] for v in ("baseline", "no_op")
            )
            replay.frozen.compare.compare_points(
                "no_op/" + str(step), a, b, h.r["protocol"], h.capture
            )
    assert result == c.read(h.capture / "trajectory-comparison.json")["dynamic"]
    assert len(audit.ledgers) == 63
    for ledger in audit.ledgers:
        assert (
            ledger.independent.failed == 0
            and ledger.failed == ledger.independent.numerical_rejections
        )
    assert (tmp_path / "replayed" / history / "trajectory-failures.jsonl").read_bytes() == (
        h.capture / "trajectory-failures.jsonl"
    ).read_bytes()


def test_all_twelve_contrast_groups_replay(data, histories, tmp_path, monkeypatch):
    audit = audit_shell(data, histories, tmp_path)
    references = {h: replay.frozen.reference_view(data["registration"], h) for h in histories}
    results = {
        name: {"native": {"points": h.native_points}, "cells": {"points": h.cells.points}}
        for name, h in histories.items()
    }
    with ctx.model_fence(), replay.capture_write_guard(ctx.CAPTURE):
        monkeypatch.setattr(io, "Ledger", audit.ledger_type(io.Ledger))
        result = replay.frozen.paired_compare.histories(audit.r, ctx.CAPTURE, references, results)
    assert result == c.read(ctx.CAPTURE / "history-contrasts.json") and len(audit.ledgers) == 12
    assert all(
        row.independent.failed == row.independent.numerical_rejections == 0 for row in audit.ledgers
    )


@pytest.mark.parametrize("mode", ["builtins", "path", "os"])
def test_capture_write_guard(tmp_path, mode):
    with replay.capture_write_guard(tmp_path), pytest.raises(ValueError):
        if mode == "builtins":
            open(tmp_path / "forbidden", "w")
        elif mode == "path":
            (tmp_path / "forbidden").open("x")
        else:
            os.open(tmp_path / "forbidden", os.O_WRONLY | os.O_CREAT, 0o600)
    assert not (tmp_path / "forbidden").exists()


def test_detached_launch_never_waits_or_polls(tmp_path, monkeypatch):
    plan = c.read(ctx.PLAN)
    monkeypatch.setattr(job, "register", lambda *_: {"plan": plan})
    monkeypatch.setattr(c, "sha", lambda _: "0" * 64)
    calls = []

    def popen(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(pid=12345)

    monkeypatch.setattr(job.subprocess, "Popen", popen)
    result = job.launch(tmp_path, tmp_path / "tests.xml")
    assert result["pid"] == 12345 and result["automatic_polling"] is False
    assert len(calls) == 1 and calls[0][1]["start_new_session"] is True
    assert calls[0][0][:3] == ["taskset", "-c", "0,1,2,3"]


def test_controller_authentication_failure_is_durable(tmp_path, monkeypatch):
    monkeypatch.setattr(job.resource, "setrlimit", lambda *_: None)
    monkeypatch.setattr(job.signal, "setitimer", lambda *_: None)
    monkeypatch.setattr(job.signal, "signal", lambda *_: None)

    def reject(_):
        raise ValueError("injected authentication rejection")

    monkeypatch.setattr(job, "authenticate", reject)
    with pytest.raises(ValueError, match="injected"):
        job.execute(tmp_path)
    failure = c.read(tmp_path / "failure.json")
    assert failure["stage"] == "authentication" and failure["automatic_retry"] is False
    assert not (tmp_path / "completion.json").exists()


def test_existing_capture_is_not_audit_output(tmp_path):
    with pytest.raises(ValueError, match="fresh"):
        job.register(ctx.CAPTURE, tmp_path / "unused.xml")


@pytest.mark.parametrize(
    "field",
    ["total_identities", "automatic_retry", "reference_review_rerun", "total_timeout_seconds"],
)
def test_changed_plan_rejected(field):
    plan = c.read(ctx.PLAN)
    plan[field] = True
    with pytest.raises(ValueError):
        ctx.validate_plan(plan)


@pytest.mark.parametrize("history", ["a", "b"])
def test_cells_full_state_restart_backend_replay(data, histories, tmp_path, monkeypatch, history):
    audit = audit_shell(data, histories, tmp_path)
    h = histories[history]
    with ctx.model_fence(), replay.capture_write_guard(ctx.CAPTURE):
        monkeypatch.setattr(io, "Ledger", audit.ledger_type(io.Ledger))
        result = replay.frozen.cells_check.cells_checks(h.r, h.capture, h.workers["cells"])
    assert result == io.read_compressed(h.capture / "cells-accounting.json.gz")
    assert len(audit.ledgers) == 9
    assert sum(row.count for row in audit.ledgers) == 95840
    assert all(
        row.independent.failed == row.independent.numerical_rejections == 0 for row in audit.ledgers
    )


@pytest.mark.parametrize("fault", ["state", "side", "rhs"])
def test_side_probe_corruption_detected(histories, fault):
    h = histories["a"]
    records = {
        k: io.read_compressed(h.capture / p) for k, p in h.workers["cells"]["side_probes"].items()
    }
    key = "suppression_release/jax_jit/dt_5e-05"
    target = records[key][0]
    if fault == "state":
        target["state"]["gate"][0][0] += 0.1
    elif fault == "side":
        target["right"]["availability"] = 1.0
    else:
        target["right"]["rhs"]["amount_increment"][1][0] = 1.0
    clone = copy.copy(h.cells)
    with pytest.raises(ValueError):
        clone.side_probes(records)


@pytest.mark.parametrize("fault", ["negative", "duplicate", "reversed", "nonfinite", "boolean"])
def test_input_schedule_domain_rejected(fault):
    rows = [{"time": 0.0, "availability": 1.0}, {"time": 0.001, "availability": 0.0}]
    if fault == "negative":
        rows[1]["availability"] = -1
    elif fault == "duplicate":
        rows[1]["time"] = 0
    elif fault == "reversed":
        rows = rows[::-1]
    elif fault == "nonfinite":
        rows[1]["time"] = float("nan")
    else:
        rows[1]["availability"] = True
    with pytest.raises(ValueError):
        control.availability(rows, 0.001)


@pytest.mark.parametrize("deadline", [False, True])
def test_controller_success_and_deadline_receipts(tmp_path, monkeypatch, deadline):
    monkeypatch.setattr(job.resource, "setrlimit", lambda *_: None)
    monkeypatch.setattr(job.signal, "setitimer", lambda *_: None)
    monkeypatch.setattr(job.signal, "signal", lambda *_: None)
    monkeypatch.setattr(job.os, "sched_getaffinity", lambda _: {0, 1, 2, 3})
    monkeypatch.setattr(job, "authenticate", lambda _: {"tests": {"tests": 120}})
    monkeypatch.setattr(ctx, "load_capture", lambda: {"hashes": {}, "provenance": {}})
    monkeypatch.setattr(c, "sha", lambda _: "0" * 64)

    class FakeAudit:
        def __init__(self, *_):
            pass

        def run(self):
            if deadline:
                job.alarm(None, None)
            return {"independent_column_mismatches": 0}

    monkeypatch.setattr(replay, "Audit", FakeAudit)
    if deadline:
        with pytest.raises(TimeoutError):
            job.execute(tmp_path)
        receipt = c.read(tmp_path / "failure.json")
        assert receipt["stage"] == "frozen_and_independent_reconstruction"
        assert not (tmp_path / "completion.json").exists()
    else:
        job.execute(tmp_path)
        receipt = c.read(tmp_path / "completion.json")
        assert receipt["status"] == "timed_release_pilot_audit_closed"
        assert receipt["release_response_qualified"] is True
        assert receipt["capture_files_unchanged"] == 555
        assert receipt["biology_validated"] is receipt["gpu_tested"] is False
    assert receipt["reference_review_rerun"] is receipt["simulators_rerun"] is False


def test_frozen_write_only_verifies_original(data, histories, tmp_path):
    audit = audit_shell(data, histories, tmp_path)
    path = ctx.CAPTURE / "comparison.json"
    before = c.sha(path)
    with replay.capture_write_guard(ctx.CAPTURE):
        audit.recorded_write(path, c.read(path))
        with pytest.raises(ValueError, match="Duplicate"):
            audit.recorded_write(path, c.read(path))
    assert before == c.sha(path)
