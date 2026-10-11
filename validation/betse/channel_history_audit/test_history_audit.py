"""Bounded saved-data slices and rejection controls, with no numerical integration."""

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
ctx = importlib.import_module("history_audit_context")
hm = importlib.import_module("history_audit_math")
cm = importlib.import_module("history_audit_cells")
reference = importlib.import_module("history_audit_reference")
replay = importlib.import_module("history_audit_replay")
job = importlib.import_module("history_audit_job")
native = importlib.import_module("feedback_audit_native")
c, io = ctx.c, ctx.io
VARIANTS = ("active_channel", "blocked_channel")


@pytest.fixture(scope="module")
def data():
    with ctx.model_fence():
        return ctx.load_capture()


@pytest.fixture(scope="module")
def histories(data):
    result = {}
    with ctx.model_fence():
        for name, view in data["registration"]["views"].items():
            history = replay.History(
                name, view, {kind: row["by_history"][name] for kind, row in data["workers"].items()}
            )
            # Saved points test routing/decisions; native mathematics is checked separately.
            history.native_points = io.read_compressed(
                ctx.CAPTURE / name / "native-accounting.json.gz"
            )["points"]
            result[name] = history
    return result


@pytest.fixture(scope="module")
def native_rows():
    return {
        (name, variant): io.read_compressed(
            ctx.CAPTURE / name / "native" / variant / "dt_2.5e-05/observed/result.json.gz"
        )
        for name in ("a", "b")
        for variant in VARIANTS
    }


@pytest.mark.parametrize("history", ["a", "b"])
@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("setting", ["dop853_base", "dop853_tight", "radau_check"])
def test_actual_reference_metadata_uses_explicit_history(histories, history, variant, setting):
    h = histories[history]
    row = h.reference.records[variant + "/" + setting]
    chosen = next(s for s in h.r["protocol"]["reference"]["solves"] if s["id"] == setting)
    reference.Reference.validate(row, h.r["reference_parameters"][variant], chosen, h.r["protocol"])
    assert row["initial_gate"] == ([0.2, 0.6] if history == "a" else [0.6, 0.2])


@pytest.mark.parametrize("history", ["a", "b"])
@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("index", [0, 160, 320])
def test_alternate_reference_readout_energy_and_blocked_analytic(
    histories, history, variant, index
):
    h = histories[history]
    key = variant + "/dop853_tight"
    row, p = h.reference.records[key], h.r["reference_parameters"][variant]
    rebuilt = h.reference.own(key, index)
    for field in rebuilt:
        hm.ind.near(
            rebuilt[field],
            row["readouts"][index][field],
            h.r["protocol"]["reference"]["comparison_absolute"][field],
        )
    q, _m, _h, energy = hm.unpack(p, row["sample_states"][index])
    hm.ind.near(hm.dissipated(p, q), math.fsum(energy), 1e-9)
    if variant == "blocked_channel":
        a, b, unit = h.reference.resolve(key + f"/analytic/{index}/0/1")
        assert unit == "gate"
        hm.ind.near(a, b, 1e-11)


@pytest.mark.parametrize("history", ["a", "b"])
@pytest.mark.parametrize("setting", ["dop853_base", "radau_check"])
@pytest.mark.parametrize("fraction", [0, 0.37, 1])
def test_alternate_dense_basis_agrees(histories, history, setting, fraction):
    interval = histories[history].reference.records["active_channel/" + setting]["dense_intervals"][
        0
    ]
    time = interval["left_s"] + fraction * (interval["right_s"] - interval["left_s"])
    hm.ind.near(hm.dense(interval, time), replay.am.dense(interval, time), 5e-13, 2e-13)


@pytest.mark.parametrize(
    "fault", ["history", "initial", "axis", "method", "clock", "counter", "sample"]
)
def test_reference_history_metadata_corruption_rejected(histories, fault):
    h = histories["b"]
    row = copy.deepcopy(h.reference.records["active_channel/dop853_tight"])
    if fault == "history":
        row["initial_gate"] = [0.2, 0.6]
    elif fault == "initial":
        row["accepted_states"][0][7] = 0.2
    elif fault == "axis":
        row["state_axes"]["channel_cell_indices"] = [0]
    elif fault == "method":
        row["dense_intervals"][0]["method"] = "unknown"
    elif fault == "clock":
        row["accepted_times_s"][1] = 0
    elif fault == "counter":
        row["stats"]["nfev"] = True
    else:
        row["sample_times_s"][1] += 1
    with pytest.raises(ValueError):
        reference.Reference.validate(
            row,
            h.r["reference_parameters"]["active_channel"],
            h.r["protocol"]["reference"]["solves"][1],
            h.r["protocol"],
        )


@pytest.mark.parametrize("fault", ["readout", "polynomial"])
def test_reference_numeric_corruption_changes_independent_columns(histories, fault):
    h = histories["b"]
    ref = reference.Reference.__new__(reference.Reference)
    ref.r, ref.records, ref.calculated = h.r, copy.deepcopy(h.reference.records), {}
    row = ref.records["active_channel/dop853_tight"]
    if fault == "readout":
        row["readouts"][1]["voltage_V"][0] += 0.1
        a, b, _unit = ref.resolve("active_channel/dop853_tight/readout/1/voltage_V/0")
    else:
        row["dense_intervals"][0]["coefficients"][0][0] += 0.1
        a, b, _unit = ref.resolve("active_channel/dop853_tight/accepted/0/0", dense=True)
    assert abs(a - b) > 0.01


@pytest.mark.parametrize("history", ["a", "b"])
@pytest.mark.parametrize("variant", VARIANTS)
def test_native_fixture_and_first_step_reconstruction(histories, native_rows, history, variant):
    h, row = histories[history], native_rows[history, variant]
    replay.native_fixture(h.r, row, h.prepared[variant + "/observed"])
    prefix, metrics = next(native.steps(h.r, row))
    assert prefix == variant + "/step/0" and len(metrics) > 1000
    tolerance = h.r["preparation_registration"]["transport_protocol"]["tolerances"] | {
        "amount_fmol": native.accumulated_atol(h.r, row)
    }
    for a, b, unit in metrics.values():
        hm.ind.near(a, b, tolerance[unit], tolerance["relative"])
    assert native.array_contract(row) > 20
    probes, points = native.probes(h.r, row)
    assert len(probes) == 300
    assert points == h.native_points[variant + "/dt_2.5e-05"]


@pytest.mark.parametrize("fault", ["gates", "physical", "metadata", "repeat", "product", "cache"])
def test_native_fixture_corruption_rejected(histories, native_rows, fault):
    h, row = histories["b"], copy.deepcopy(native_rows["b", "active_channel"])
    f = row["fixture"]
    if fault == "gates":
        f["after"]["channel"]["m"][0] = 0.2
    elif fault == "physical":
        f["after"]["physical"]["inside_mM"][1][0] += 1
    elif fault == "metadata":
        f["metadata"]["sim_temperature_K"] += 1
    elif fault == "repeat":
        f["applications"] = 2
    elif fault == "product":
        f["after"]["channel"]["derived_m_times_h"][0] += 0.01
    else:
        f["after"]["channel"]["P"] = [0.12] * 30
    with pytest.raises(ValueError):
        replay.native_fixture(h.r, row, h.prepared["active_channel/observed"])


@pytest.mark.parametrize("history", ["a", "b"])
def test_full_definitions_states_and_checkpoints_are_prepared(histories, history):
    h = histories[history]
    assert len(h.cells.records) == 8 and len(h.cells.resumed) == 2
    assert h.checkpoints == 12 and h.checkpoint_arrays == 648
    assert len(h.decisions()) == 4


@pytest.mark.parametrize("history", ["a", "b"])
@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("kind", ["final-checkpoint", "midpoint-checkpoint", "resumed-checkpoint"])
def test_every_checkpoint_kind_raw_bytes(histories, history, variant, kind):
    h = histories[history]
    key = variant + "/jax_jit/dt_2.5e-05"
    row = h.cells.resumed[key] if kind == "resumed-checkpoint" else h.cells.records[key]
    directory = h.capture / "cells" / key / kind
    manifest = c.read(directory / "manifest.json")
    index = 40 if kind == "midpoint-checkpoint" else len(row["times"]["values"]) - 1
    assert (
        cm.checkpoint(
            directory,
            row,
            index,
            manifest["source_hashes"],
            cm.layout_contract(variant, history, "jax_jit"),
        )
        == 54
    )


@pytest.mark.parametrize("field", ["gate", "owners", "outside_owners", "channel_membranes"])
def test_rehashed_checkpoint_payload_corruption_rejected(histories, monkeypatch, field):
    h, key = histories["b"], "active_channel/jax_jit/dt_2.5e-05"
    directory = h.capture / "cells" / key / "final-checkpoint"
    row = h.cells.records[key]
    layout = cm.layout_contract("active_channel", "b", "jax_jit")
    actual = cm.raw_checkpoint(directory / "state.npz")
    actual[field]["sha256"] = "0" * 64
    monkeypatch.setattr(cm, "raw_checkpoint", lambda _: actual)
    with pytest.raises(ValueError, match="state/layout bytes"):
        cm.checkpoint(
            directory, row, 80, c.read(directory / "manifest.json")["source_hashes"], layout
        )


def raw_npy(dtype, shape, payload, order=False):
    header = repr({"descr": dtype, "shape": shape, "fortran_order": order}).encode("ascii")
    return b"\x93NUMPY\x01\x00" + len(header).to_bytes(2, "little") + header + payload


@pytest.mark.parametrize("fault", ["object", "shape", "truncated", "nan", "bool", "order"])
def test_unsafe_npy_payload_rejected(fault):
    dtype, shape, payload, order = "<f8", (1,), struct.pack("<d", 1.0), False
    if fault == "object":
        dtype = "|O"
    elif fault == "shape":
        shape = (2,)
    elif fault == "truncated":
        payload = payload[:-1]
    elif fault == "nan":
        payload = struct.pack("<d", math.nan)
    elif fault == "bool":
        dtype, payload = "|b1", b"\x02"
    else:
        order = True
    with pytest.raises(ValueError):
        cm.raw_array(raw_npy(dtype, shape, payload, order))


@pytest.mark.parametrize("history", ["a", "b"])
def test_initial_state_is_defined_by_data_not_implicit_a(histories, history):
    row = histories[history].cells.records["active_channel/jax_jit/dt_2.5e-05"]
    state = cm.initial_from_definition(row["definition"])
    assert state["gate"] == row["history"]["gate"]["values"][0]
    assert state["gate"][0][0] == (0.2 if history == "a" else 0.6)


@pytest.fixture(scope="module")
def routing_audit(data, histories):
    audit = replay.Audit.__new__(replay.Audit)
    audit.r, audit.histories, audit.contrasts = data["registration"], histories, {}
    return audit


@pytest.mark.parametrize("engine", ["native", "cells", "cross_engine"])
@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize(
    "field,tail", [("voltage_V", "0"), ("interval_transfer_fmol", "0"), ("gate", "0/0")]
)
def test_signed_contrast_and_interval_routing(routing_audit, engine, variant, field, tail):
    a, b, unit = routing_audit.contrast_resolve(
        f"history_contrast/{variant}/{engine}/observation/4/{field}/{tail}"
    )
    multiplier = 4 if engine == "cross_engine" else 2
    hm.ind.near(
        a, b, routing_audit.r["views"]["a"]["protocol"]["trajectory_absolute"][unit] * multiplier
    )


def test_actual_signal_reconstructed(data, histories):
    gate = c.read(ctx.CAPTURE / "reference-gate.json")
    result = replay.independent_signal(data["registration"]["protocol"], histories, gate["signal"])
    assert min(map(abs, result["active_channel"]["voltage_contrast_V"])) > 0.0007
    assert result["blocked_channel"]["voltage_contrast_V"] == [0.0] * 7


@pytest.mark.parametrize("fault", ["sign", "threshold", "gate_threshold", "blocked", "missing"])
def test_signal_and_pair_corruption_rejected(data, histories, fault):
    p = copy.deepcopy(data["registration"]["protocol"])
    saved = c.read(ctx.CAPTURE / "reference-gate.json")["signal"]
    chosen = histories
    if fault == "sign":
        saved["active_channel"]["voltage_contrast_V"][0] *= -1
    elif fault == "threshold":
        p["minimum_final_voltage_contrast_V"] = 1
    elif fault == "gate_threshold":
        p["minimum_final_open_fraction_contrast"] = 1
    elif fault == "blocked":
        saved["blocked_channel"]["voltage_contrast_V"][0] = 1
    else:
        chosen = {"a": histories["a"]}
    with pytest.raises(ValueError):
        replay.independent_signal(p, chosen, saved)


def test_twin_ledger_has_separate_history_identity(tmp_path):
    audit = replay.Audit.__new__(replay.Audit)
    audit.output, audit.ledgers = tmp_path, []
    audit.histories = {
        "b": SimpleNamespace(
            r={"protocol": {}}, reference=SimpleNamespace(resolve=lambda _: (1.0, 1.0, "gate"))
        )
    }
    ledger = audit.ledger_type(io.Ledger)(
        {"gate": 1e-8}, failure_path=ctx.CAPTURE / "b/reference-failures.jsonl"
    )
    ledger.compare("some/identity", 1.0, 1.0, "gate")
    assert ledger.count == ledger.independent.count == 1 and ledger.independent.failed == 0
    with pytest.raises(ValueError, match="Duplicate"):
        ledger.compare("some/identity", 1.0, 1.0, "gate")


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


def test_frozen_write_redirection_never_changes_capture():
    audit = replay.Audit.__new__(replay.Audit)
    audit.writes = set()
    path = ctx.CAPTURE / "comparison.json"
    before = c.sha(path)
    with replay.capture_write_guard(ctx.CAPTURE):
        audit.recorded_write(path, c.read(path))
        with pytest.raises(ValueError, match="Duplicate"):
            audit.recorded_write(path, c.read(path))
    assert c.sha(path) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("native_identities", 1),
        ("automatic_retry", True),
        ("reference_integrator_rerun", True),
        ("total_timeout_seconds", 1),
    ],
)
def test_changed_audit_plan_rejected(field, value):
    plan = c.read(ctx.PLAN)
    plan[field] = value
    with pytest.raises(ValueError):
        ctx.validate_plan(plan)


def test_capture_scope_authenticates_without_numerical_replay(data):
    assert len(data["hashes"]) == 291 and len(ctx.sources()) == 152
    assert data["completion"]["coarse_diagnostic_failures"] == 21
    assert data["registration"]["tests"]["tests"] == 56


@pytest.mark.parametrize("fault", ["count", "missing", "extra", "bytes", "qualified"])
def test_provenance_corruption_rejected(data, fault):
    done, hashes = copy.deepcopy(data["completion"]), data["hashes"].copy()
    if fault == "count":
        done["coarse_diagnostic_failures"] = 14
    elif fault == "missing":
        hashes.pop("b/trajectory-comparison.json")
    elif fault == "extra":
        hashes["unexpected"] = "0" * 64
    elif fault == "bytes":
        hashes["b/trajectory-comparison.json"] = "0" * 64
    else:
        done["coupled_history_qualified"] = True
    with pytest.raises(ValueError):
        ctx.provenance(data["registration"], done, data["workers"], hashes)


@pytest.mark.parametrize("module", ctx.FORBIDDEN)
def test_model_imports_are_forbidden(module):
    with ctx.model_fence(), pytest.raises(RuntimeError, match="forbidden"):
        importlib.import_module(module)


def test_existing_capture_is_not_audit_output(tmp_path):
    with pytest.raises(ValueError, match="fresh"):
        job.register(ctx.CAPTURE, tmp_path / "unused.xml")


def test_job_has_no_simulator_or_reference_worker_call():
    source = (HERE / "history_audit_job.py").read_text()
    assert "subprocess.run" not in source and 'add_parser("worker")' not in source
    assert '"reference_integrator_rerun": False' in source
    assert '"automatic_followup": False' in source


@pytest.mark.parametrize("history", ["a", "b"])
def test_bounded_reference_replay_checks_every_selected_column(
    data, histories, tmp_path, monkeypatch, history
):
    audit = replay.Audit.__new__(replay.Audit)
    # Test-only three-observation slices; full registered replay belongs to the detached audit.
    view = copy.deepcopy(histories[history].r)
    view["protocol"]["reference"]["solves"] = [view["protocol"]["reference"]["solves"][1]]
    view["protocol"]["reference"]["sample_dt_s"] = 0.001
    records, aggregate = {}, {"records": {}, "reference_solves": 2}
    by_path = {}
    for variant in VARIANTS:
        key = variant + "/dop853_tight"
        row = copy.deepcopy(histories[history].reference.records[key])
        for field in ("sample_times_s", "sample_states", "readouts"):
            row[field] = [row[field][i] for i in (0, 160, 320)]
        records[key] = row
        relative = "reference/" + key + "/result.json.gz"
        aggregate["records"][key] = relative
        by_path[ctx.CAPTURE / history / relative] = row
    audit.r, audit.contrasts = data["registration"], {}
    audit.histories = {
        history: SimpleNamespace(r=view, reference=reference.Reference(view, records))
    }
    audit.output, audit.ledgers, audit.writes = tmp_path, [], set()
    writes = []
    with ctx.model_fence(), replay.capture_write_guard(ctx.CAPTURE):
        monkeypatch.setattr(io, "Ledger", audit.ledger_type(io.Ledger))
        monkeypatch.setattr(io, "read_compressed", lambda path: by_path[path])
        monkeypatch.setattr(
            io, "write_compressed", lambda path, value: writes.append((path, value))
        )
        result = replay.frozen.reference_check.check(
            view,
            ctx.CAPTURE / history,
            aggregate,
        )
    assert result["status"] == "pass" and len(audit.ledgers) == 2
    assert writes == [(ctx.CAPTURE / history / "reference-gate.json.gz", result)]
    for ledger in audit.ledgers:
        assert ledger.count == ledger.independent.count > 100
        assert ledger.failed == ledger.independent.failed == 0


def test_frozen_contrast_replay_checks_all_six_groups(data, histories, tmp_path, monkeypatch):
    audit = replay.Audit.__new__(replay.Audit)
    audit.r, audit.histories, audit.contrasts = data["registration"], histories, {}
    audit.output, audit.ledgers = tmp_path, []
    references = {
        name: io.read_compressed(ctx.CAPTURE / name / "reference-gate.json.gz")
        for name in histories
    }
    results = {
        name: {"native": {"points": h.native_points}, "cells": {"points": h.cells.points}}
        for name, h in histories.items()
    }
    with ctx.model_fence(), replay.capture_write_guard(ctx.CAPTURE):
        monkeypatch.setattr(io, "Ledger", audit.ledger_type(io.Ledger))
        result = replay.frozen.histories(audit.r, ctx.CAPTURE, references, results)
    assert result == c.read(ctx.CAPTURE / "history-contrasts.json")
    assert len(audit.ledgers) == 6
    for ledger in audit.ledgers:
        assert ledger.kind == "history_contrast" and ledger.count == ledger.independent.count
        assert ledger.failed == ledger.independent.failed == 0


@pytest.mark.parametrize("engine,multiplier", [("native", 2), ("cells", 2), ("cross_engine", 4)])
def test_contrast_budget_cannot_change(data, tmp_path, engine, multiplier):
    audit = replay.Audit.__new__(replay.Audit)
    audit.r, audit.output, audit.ledgers, audit.histories = data["registration"], tmp_path, [], {}
    audit.contrast_resolve = lambda _: (0.0, 0.0, "gate")
    p = audit.r["views"]["a"]["protocol"]
    ledger = audit.ledger_type(io.Ledger)(
        {k: v * (multiplier + 1) for k, v in p["trajectory_absolute"].items()},
        p["comparison_relative"],
        ctx.CAPTURE / "trajectory-failures.jsonl",
    )
    with pytest.raises(ValueError, match="budget changed"):
        ledger.compare(
            f"history_contrast/active_channel/{engine}/observation/0/gate/0/0", 0.0, 0.0, "gate"
        )


def test_checkpoint_hash_uses_canonical_not_raw_input(histories):
    h, key = histories["b"], "active_channel/jax_eager/dt_5e-05"
    row = h.cells.records[key]
    manifest = c.read(h.capture / "cells" / key / "final-checkpoint/manifest.json")
    assert row["definition"] == row["canonical_definition"]
    assert cm.digest(row["definition"]) != cm.digest(row["canonical_definition"])
    assert manifest["spec_sha256"] == cm.digest(row["canonical_definition"])


@pytest.mark.parametrize("fault", ["duplicate", "omission"])
def test_streaming_native_coverage_refuses_missing_or_duplicate_identity(fault):
    case = native.Case.__new__(native.Case)
    name = "active_channel/step/0/identity"
    case.sequence = iter([("active_channel/step/0", {name: (1.0, 1.0, "gate")})])
    case.pending, case.current, case.fresh = {}, None, {}
    if fault == "duplicate":
        assert case.resolve(name) == (1.0, 1.0, "gate")
        with pytest.raises(ValueError):
            case.resolve(name)
    else:
        with pytest.raises(ValueError):
            case.finish()
