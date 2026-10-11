"""Audit-only arithmetic, bounded saved-data slices, corruption and read-only guards."""

import ast
import copy
import importlib
import math
import os
import struct
import subprocess
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ctx = importlib.import_module("feedback_audit_context")
am = importlib.import_module("feedback_audit_math")
native = importlib.import_module("feedback_audit_native")
cells = importlib.import_module("feedback_audit_cells")
reference = importlib.import_module("feedback_audit_reference")
replay = importlib.import_module("feedback_audit_replay")
job = importlib.import_module("feedback_audit_job")
c, io = ctx.c, ctx.io


@pytest.fixture(scope="module")
def registration():
    return c.read(ctx.CAPTURE / "registration.json")


@pytest.fixture(scope="module")
def reference_records(registration):
    return {
        variant + "/" + setting["id"]: io.read_compressed(
            ctx.CAPTURE / f"reference/{variant}/{setting['id']}/result.json.gz"
        )
        for variant in registration["protocol"]["variants"]
        for setting in registration["protocol"]["reference"]["solves"]
    }


@pytest.fixture(scope="module")
def native_records():
    return {
        variant: io.read_compressed(
            ctx.CAPTURE / f"native/{variant}/dt_2.5e-05/observed/result.json.gz"
        )
        for variant in am.ind.VARIANTS
    }


@pytest.fixture(scope="module")
def cells_records():
    return {
        variant: io.read_compressed(
            ctx.CAPTURE / f"cells/{variant}/jax_jit/dt_2.5e-05/result.json.gz"
        )
        for variant in am.ind.VARIANTS
    }


@pytest.mark.parametrize("variant", am.ind.VARIANTS)
@pytest.mark.parametrize("setting", ["dop853_base", "dop853_tight", "radau_check"])
def test_reference_metadata_and_coordinate_domains(
    registration, reference_records, variant, setting
):
    chosen = next(s for s in registration["protocol"]["reference"]["solves"] if s["id"] == setting)
    reference.Reference.validate(
        reference_records[variant + "/" + setting],
        registration["reference_parameters"][variant],
        chosen,
        registration["protocol"],
    )


@pytest.mark.parametrize("variant", am.ind.VARIANTS)
@pytest.mark.parametrize("index", [0, 160, 320])
def test_independent_reference_readouts_and_energy(registration, reference_records, variant, index):
    p = registration["reference_parameters"][variant]
    record = reference_records[variant + "/dop853_tight"]
    state, saved = record["sample_states"][index], record["readouts"][index]
    rebuilt = am.readout(p, state)
    for field in saved:
        am.ind.near(
            rebuilt[field],
            saved[field],
            registration["protocol"]["reference"]["comparison_absolute"][field],
        )
    q, _m, _h, energy = am.unpack(p, state)
    assert am.dissipated(p, q) == pytest.approx(math.fsum(energy), abs=1e-10)


@pytest.mark.parametrize("method", ["dop853_base", "dop853_tight", "radau_check"])
@pytest.mark.parametrize("fraction", [0, 0.37, 1])
def test_independent_direct_dense_basis(reference_records, method, fraction):
    interval = reference_records["active_channel/" + method]["dense_intervals"][0]
    time_s = interval["left_s"] + fraction * (interval["right_s"] - interval["left_s"])
    am.ind.near(
        am.dense(interval, time_s),
        replay.frozen_reference.dense_value(interval, time_s),
        5e-13,
        2e-13,
    )


@pytest.mark.parametrize(
    "name,dense",
    [
        ("active_channel/dop853_tight/sample/160/0", True),
        ("active_channel/radau_check/accepted/0/7", True),
        ("active_channel/dop853_tight/readout/160/voltage_V/0", False),
        ("active_channel/dop853_tight/thermodynamics/160", False),
        ("blocked_channel/dop853_tight/analytic/160/0/1", False),
        ("active_channel/radau_check/agreement/160/flux_fmol_per_s/0", False),
        ("active_channel/radau_check/agreement/160/interval_transfer_fmol/0", False),
    ],
)
def test_reference_identity_routing(registration, reference_records, name, dense):
    resolver = reference.Reference.__new__(reference.Reference)
    resolver.r, resolver.records, resolver.calculated = registration, reference_records, {}
    a, b, unit = resolver.resolve(name, dense=dense)
    absolute = (
        5e-13 if dense else registration["protocol"]["reference"]["comparison_absolute"][unit]
    )
    am.ind.near(a, b, absolute)


@pytest.mark.parametrize("fault", ["axis", "method", "clock", "sample", "budget"])
def test_reference_metadata_corruption_is_rejected(registration, reference_records, fault):
    row = copy.deepcopy(reference_records["active_channel/dop853_tight"])
    if fault == "axis":
        row["state_axes"]["cell_count"] = 8
    elif fault == "method":
        row["dense_intervals"][0]["method"] = "unknown"
    elif fault == "clock":
        row["accepted_times_s"][-1] += 1
    elif fault == "sample":
        row["sample_times_s"][1] += 1
    else:
        row["stats"]["rhs_calls_including_jacobian"] = 1000000
    setting = registration["protocol"]["reference"]["solves"][1]
    with pytest.raises(ValueError):
        reference.Reference.validate(
            row,
            registration["reference_parameters"]["active_channel"],
            setting,
            registration["protocol"],
        )


@pytest.mark.parametrize("variant", am.ind.VARIANTS)
def test_bounded_eight_step_independent_native_identities(registration, variant):
    row = c.read(ctx.pilot.audit.CAPTURE / "betse.json")["rows"][variant + "/observed"]
    r = copy.deepcopy(registration)
    r["protocol"]["duration_s"] = row["steps"] * row["dt_s"]
    expected = {
        name: values for _group, metrics in native.steps(r, row) for name, values in metrics.items()
    }
    ledger = io.Ledger(r["preparation_registration"]["transport_protocol"]["tolerances"])
    original_compare = ledger.compare
    verified = []

    def compare(name, actual, wanted, unit):
        if not isinstance(wanted, list):
            a, b, independent_unit = expected.pop(name)
            assert independent_unit == unit
            am.ind.near(actual, a, ledger.absolute[unit])
            am.ind.near(wanted, b, ledger.absolute[unit])
            verified.append(name)
        return original_compare(name, actual, wanted, unit)

    ledger.compare = compare
    v = next(
        v
        for v in r["preparation_registration"]["transport_protocol"]["variants"]
        if v["id"] == variant
    )
    replay.frozen_compare.oldcheck.observed(
        ctx.pilot.loop_registration(r, row["dt_s"]), v, row, ledger
    )
    assert not expected and verified and ledger.failed == 0


@pytest.mark.parametrize("variant", am.ind.VARIANTS)
def test_independent_fresh_native_mapping_and_byte_contracts(registration, native_records, variant):
    row = native_records[variant]
    expected, points = native.probes(registration, row)
    ledger = io.Ledger(registration["preparation_registration"]["transport_protocol"]["tolerances"])
    v = next(
        v
        for v in registration["preparation_registration"]["transport_protocol"]["variants"]
        if v["id"] == variant
    )
    assert replay.frozen_compare.native_points(registration, row, v, ledger) == points
    assert len(expected) == ledger.count == 300 and ledger.failed == 0
    assert native.array_contract(row) > 20
    assert native.accumulated_atol(
        registration, row
    ) == replay.frozen_compare.accumulation_tolerance(registration, row["steps"])


@pytest.mark.parametrize("fault", ["bytes", "partial_history", "extra_array", "time"])
def test_native_array_and_clock_corruption_is_rejected(registration, native_records, fault):
    row = copy.deepcopy(native_records["active_channel"])
    if fault == "bytes":
        row["final_arrays"]["channel/m"]["values"][0] += 0.1
    elif fault == "partial_history":
        row["histories"]["time"]["shape"][0] -= 1
    elif fault == "extra_array":
        row["final_arrays"]["extra"] = row["final_arrays"]["channel/m"]
    else:
        row["trace"]["steps"][0]["before_elapsed_s"] = 0.2
        with pytest.raises(ValueError):
            next(native.steps(registration, row))
        return
    with pytest.raises(ValueError):
        native.array_contract(row)


@pytest.mark.parametrize("variant", am.ind.VARIANTS)
def test_independent_cells_state_and_sampled_readouts(registration, cells_records, variant):
    key = variant + "/jax_jit/dt_2.5e-05"
    record = cells_records[variant]
    rebuilt = cells.Cells(registration, {key: record}, {})
    ledger = io.Ledger(replay.frozen_compare.cells_tolerances(registration))
    assert (
        replay.frozen_compare.cells_points_and_checks(registration, record, ledger)
        == rebuilt.points[key]
    )
    assert ledger.failed == 0
    a, b, unit = rebuilt.resolve_state(key + "/constitutive/4/voltage_V/0")
    am.ind.near(a, b, ledger.absolute[unit])


@pytest.mark.parametrize("variant", am.ind.VARIANTS)
@pytest.mark.parametrize("name", ["final-checkpoint", "midpoint-checkpoint", "resumed-checkpoint"])
def test_every_checkpoint_kind_decodes_without_numpy(cells_records, variant, name):
    directory = ctx.CAPTURE / "cells" / variant / "jax_jit/dt_2.5e-05"
    record = (
        cells_records[variant]
        if name != "resumed-checkpoint"
        else io.read_compressed(directory / "resumed.json.gz")
    )
    sources = {
        str(path.relative_to(ctx.ROOT / "src/cells")): c.sha(path)
        for path in (ctx.ROOT / "src/cells").rglob("*.py")
    }
    index = 40 if name == "midpoint-checkpoint" else len(record["times"]["values"]) - 1
    assert cells.checkpoint(directory / name, record, index, sources, c.read, c.sha) == 54


@pytest.mark.parametrize("field", ["gate", "owners", "outside_owners", "channel_membranes"])
def test_checkpoint_state_and_owner_corruption_is_rejected(cells_records, monkeypatch, field):
    directory = ctx.CAPTURE / "cells/active_channel/jax_jit/dt_2.5e-05/final-checkpoint"
    record = cells_records["active_channel"]
    manifest = c.read(directory / "manifest.json")
    arrays = cells.decode_npz(directory / "state.npz")
    if field == "gate":
        arrays[field]["values"][0][0] += 0.01
    else:
        arrays[field]["values"][0] += 1
    monkeypatch.setattr(cells, "decode_npz", lambda _: arrays)
    with pytest.raises(ValueError, match="state/layout value"):
        cells.checkpoint(directory, record, 80, manifest["source_hashes"], c.read, c.sha)


def npy(values, shape, dtype="<f8", fortran=False):
    header = (
        repr({"descr": dtype, "fortran_order": fortran, "shape": shape}).encode("ascii") + b"\n"
    )
    code = {"<f8": "d", "<i8": "q", "|b1": "B"}.get(dtype, "d")
    return (
        b"\x93NUMPY\x01\x00"
        + struct.pack("<H", len(header))
        + header
        + struct.pack("<" + code * len(values), *values)
    )


@pytest.mark.parametrize(
    "values,shape,dtype",
    [
        ([1.5, -0.0], (2,), "<f8"),
        ([2, -1], (1, 2), "<i8"),
        ([0, 1], (2,), "|b1"),
        ([1.5], (), "<f8"),
    ],
)
def test_numeric_npy_decoder_shapes_and_types(values, shape, dtype):
    result = cells.decode_npy(npy(values, shape, dtype))
    assert result["shape"] == list(shape) and result["dtype"] == dtype
    if dtype == "|b1":
        assert result["values"] == [False, True]


@pytest.mark.parametrize(
    "fault", ["object", "fortran", "huge", "truncated", "version", "nan", "boolean", "trailing"]
)
def test_unsafe_numeric_checkpoint_encoding_is_rejected(fault):
    value = npy([1.0], (1,))
    if fault == "object":
        value = npy([1.0], (1,), "|O")
    elif fault == "fortran":
        value = npy([1.0], (1,), fortran=True)
    elif fault == "huge":
        value = npy([1.0], (1000001,))
    elif fault == "truncated":
        value = value[:-1]
    elif fault == "version":
        value = value[:6] + b"\x02\x00" + value[8:]
    elif fault == "nan":
        value = npy([math.nan], (1,))
    elif fault == "boolean":
        value = npy([2], (1,), "|b1")
    else:
        value += b"garbage"
    with pytest.raises(ValueError):
        cells.decode_npy(value)


def test_npz_decoder_rejects_hidden_members(tmp_path):
    path = tmp_path / "state.npz"
    with zipfile.ZipFile(path, "x") as archive:
        archive.writestr("amount.npy", npy([1.0], (1,)))
        archive.writestr("hidden/payload.npy", npy([1.0], (1,)))
    with pytest.raises(ValueError, match="membership"):
        cells.decode_npz(path)


@pytest.mark.parametrize("case", ["pass", "columns", "classification", "diagnostic"])
def test_streaming_crosscheck_keeps_mismatches_and_original_rejections(tmp_path, case):
    checker = am.Crosscheck(tmp_path / "failures.jsonl")
    values = {
        "pass": (1.0, 1.0, 1.0, 1.0),
        "columns": (1.0, 1.0, 1.0, 2.0),
        "classification": (1.100001, 1.0, 1.099999, 1.0),
        "diagnostic": (2.0, 1.0, 2.0, 1.0),
    }[case]
    checker.add("identity", *values, "state", 0.1, 0.0)
    assert checker.count == 1
    assert checker.failed == int(case in ("columns", "classification"))
    assert checker.numerical_rejections == int(case in ("columns", "diagnostic"))
    assert len(checker.digest.hexdigest()) == 64


@pytest.mark.parametrize("case", ["shrinking", "floor", "growing", "own_growing"])
def test_independent_refinement_preserves_policy(registration, case):
    values, own = [1e-5, 5e-6, 2.5e-6], [5e-6, 2.5e-6]
    if case == "floor":
        values, own = [1e-15, 2e-15, 3e-15], [1e-15, 1e-15]
    elif case == "growing":
        values = list(reversed(values))
    elif case == "own_growing":
        own = list(reversed(own))
    result = replay.refinement_decision(
        values, own, 1e-15, 1e-5, registration["protocol"]["refinement"]
    )
    assert result["passed"] is (case in ("shrinking", "floor"))
    assert (result["classification"] == "reference_or_roundoff_limited") is (case == "floor")


@pytest.fixture(scope="module")
def decision_audit(registration, reference_records):
    audit = replay.Audit.__new__(replay.Audit)
    audit.r = registration
    audit.native_points = io.read_compressed(ctx.CAPTURE / "native-accounting.json.gz")["points"]
    audit.cells = SimpleNamespace(
        points=io.read_compressed(ctx.CAPTURE / "cells-accounting.json.gz")["points"]
    )
    audit.reference = reference.Reference.__new__(reference.Reference)
    audit.reference.r, audit.reference.records = registration, reference_records
    return audit


@pytest.mark.parametrize(
    "name",
    [
        "native/active_channel/dt_6.25e-06/observation/4/voltage_V/0",
        "cells/active_channel/jax_jit/dt_1.25e-05/observation/4/voltage_V/0",
        "native/active_channel/dt_6.25e-06/own_refinement/observation/4/gate/0/0",
        "cells/active_channel/jax_jit/dt_1.25e-05/own_refinement/observation/4/transfer_fmol/0",
        "cross_engine/active_channel/observation/4/interval_transfer_fmol/0",
    ],
)
def test_independent_dynamic_pair_and_interval_routing(decision_audit, name):
    a, b, unit = decision_audit.dynamic_resolve(name)
    am.ind.near(a, b, decision_audit.r["protocol"]["trajectory_absolute"][unit] * 2)


def test_all_saved_refinement_decisions_rebuild_without_integration(decision_audit):
    decisions = decision_audit.decisions()
    assert len(decisions) == 8 and all(v["status"] == "pass" for v in decisions.values())
    assert all(
        v["classification"] == "resolved_refinement"
        for v in decisions["native/active_channel"]["fields"].values()
    )
    assert all(
        v["classification"] == "reference_or_roundoff_limited"
        for v in decisions["cells/active_channel"]["fields"].values()
    )


def test_streamed_native_coverage_cannot_skip_or_duplicate_a_group():
    case = native.Case.__new__(native.Case)
    name = "active_channel/step/0/identity"
    case.sequence = iter([("active_channel/step/0", {name: (1.0, 1.0, "gate")})])
    case.pending, case.current, case.fresh = {}, None, {}
    assert case.resolve(name) == (1.0, 1.0, "gate")
    with pytest.raises(ValueError, match="duplicate"):
        case.resolve(name)
    case.finish()


@pytest.mark.parametrize("mode", ["builtins", "path", "os"])
def test_capture_write_guard_blocks_low_and_high_level_writes(tmp_path, mode):
    with replay.capture_write_guard(tmp_path):
        with pytest.raises(ValueError, match="immutable capture"):
            if mode == "builtins":
                open(tmp_path / "forbidden", "w")
            elif mode == "path":
                (tmp_path / "forbidden").open("x")
            else:
                os.open(tmp_path / "forbidden", os.O_WRONLY | os.O_CREAT, 0o600)
    assert not (tmp_path / "forbidden").exists()


def test_frozen_write_redirection_compares_instead_of_mutating_capture():
    audit = replay.Audit.__new__(replay.Audit)
    audit.writes = set()
    path = ctx.CAPTURE / "capture-comparison.json"
    before = c.sha(path)
    with replay.capture_write_guard(ctx.CAPTURE):
        audit.recorded_write(path, c.read(path))
        with pytest.raises(ValueError, match="Duplicate"):
            audit.recorded_write(path, c.read(path))
    assert c.sha(path) == before


def test_twin_ledger_routes_every_scalar_and_preserves_counts(tmp_path):
    audit = replay.Audit.__new__(replay.Audit)
    audit.output, audit.ledgers = tmp_path, []
    audit.reference = SimpleNamespace(resolve=lambda n: (1.0, 1.0, "gate"))
    kind = audit.ledger_type(io.Ledger)
    ledger = kind({"gate": 1e-8}, failure_path=ctx.CAPTURE / "reference-failures.jsonl")
    ledger.compare("some/reference/identity", 1.0, 1.0, "gate")
    assert ledger.count == ledger.independent.count == 1
    with pytest.raises(ValueError, match="Duplicate"):
        ledger.compare("some/reference/identity", 1.0, 1.0, "gate")


@pytest.mark.parametrize(
    "field,value",
    [
        ("native_identities", 1),
        ("automatic_retry", True),
        ("reference_integrator_rerun", True),
        ("total_timeout_seconds", 1),
    ],
)
def test_changed_audit_plan_is_rejected(field, value):
    plan = c.read(ctx.PLAN)
    plan[field] = value
    with pytest.raises(ValueError):
        ctx.validate_plan(plan)


def test_original_capture_and_software_authenticate_without_numerical_work():
    with ctx.model_fence():
        data = ctx.load_capture()
    assert len(data["hashes"]) == 284 and len(ctx.sources()) == 122
    assert data["completion"]["coarse_diagnostic_failures"] == 14
    assert data["registration"]["tests"]["tests"] == 157
    assert len(ctx.historical_reports()) == 9


def test_existing_capture_cannot_be_used_as_audit_output(tmp_path):
    with pytest.raises(ValueError, match="fresh"):
        job.register(ctx.CAPTURE, tmp_path / "unused.xml")


@pytest.mark.parametrize(
    "filename",
    [
        "feedback_audit_math.py",
        "feedback_audit_native.py",
        "feedback_audit_reference.py",
        "feedback_audit_cells.py",
    ],
)
def test_independent_modules_cannot_import_original_oracle_or_models(filename):
    tree = ast.parse((HERE / filename).read_text())
    forbidden = {
        "cells",
        "betse",
        "numpy",
        "jax",
        "jaxlib",
        "scipy",
        "feedback_reference",
        "pilot_reference",
        "feedback_compare",
        "feedback_audit_context",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(n.name.split(".")[0] not in forbidden for n in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.module.split(".")[0] not in forbidden


def test_fresh_process_import_fence_rejects_models():
    code = (
        "import sys; sys.path.insert(0,sys.argv[1]); import feedback_audit_context as ctx\n"
        "with ctx.model_fence():\n import feedback_audit_replay\n"
        " for name in ctx.FORBIDDEN:\n  try: __import__(name)\n"
        "  except RuntimeError: pass\n  else: raise AssertionError(name)\n"
        "print('model_free_audit_pass')"
    )
    result = subprocess.run(
        [str(c.CELLS_PYTHON), "-B", "-c", code, str(HERE)],
        text=True,
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "model_free_audit_pass"


def test_no_simulator_or_reference_worker_entrypoint_in_audit_job():
    source = (HERE / "feedback_audit_job.py").read_text()
    assert "subprocess.run" not in source and 'add_parser("worker")' not in source
    assert '"reference_integrator_rerun": False' in source
    assert '"automatic_followup": False' in source
