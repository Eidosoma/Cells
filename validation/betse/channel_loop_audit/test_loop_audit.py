"""Saved-data arithmetic/corruption tests; never execute a native simulation."""

import ast
import copy
import hashlib
import importlib
import math
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ctx = importlib.import_module("loop_audit_context")
ind = importlib.import_module("loop_independent")
ready = importlib.import_module("readiness_independent")
job = importlib.import_module("loop_audit_job")
c = ctx.c


@pytest.fixture(scope="module")
def saved():
    return ctx.load_capture()


@pytest.fixture(scope="module")
def rebuilt(saved):
    return ctx.numerical_audit(saved)


def test_all_saved_rows_and_contracts_rebuild(saved, rebuilt):
    summary, rows = rebuilt
    assert (
        summary["independent_comparisons"]
        == summary["frozen_comparisons_replayed"]
        == len(rows)
        == 74092
    )
    assert summary["failed_comparisons"] == 0, [r for r in rows if not r["passed"]][:8]
    assert summary["native_comparisons_by_variant"] == {
        "network_off": 8000,
        "empty_network": 13376,
        "blocked_channel": 26184,
        "active_channel": 26184,
    }
    assert summary["observer_pairs_checked"] == 4
    assert summary["array_records_reconstructed"] == 204
    assert summary["direct_charge_snapshots_checked"] == 36
    for field in (
        "candidate_definition_contracts_checked",
        "full_initial_states_checked",
        "full_initial_rhs_checked",
        "candidate_grid_resource_contracts_checked",
    ):
        assert summary[field] == 12
    assert saved["provenance"]["capture_files"] == 74


@pytest.mark.parametrize("filename", ["loop_independent.py", "readiness_independent.py"])
def test_independent_math_has_no_model_or_old_oracle_imports(filename):
    tree = ast.parse((HERE / filename).read_text())
    allowed = {"hashlib", "math", "struct", "decimal", "loop_independent"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(n.name in allowed for n in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.module in allowed
    assert not any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id in ("open", "eval", "exec", "__import__")
        for n in ast.walk(tree)
    )


@pytest.mark.parametrize("module", ctx.FORBIDDEN)
def test_fresh_process_import_fence(module):
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); import loop_audit_context as c\n"
        "with c.model_fence():\n    __import__(sys.argv[2])\n"
    )
    result = subprocess.run(
        [str(c.CELLS_PYTHON), "-B", "-c", code, str(HERE), module],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode != 0
    assert "Model import forbidden by saved-data audit" in result.stderr


@pytest.mark.parametrize(
    "values,shape",
    [
        (0.0, []),
        (-0.0, []),
        ([1.0, -2.0], [2]),
        ([[0.2, 0.6]], [1, 2]),
        ([], [0]),
        ([[], []], [2, 0]),
    ],
)
def test_float64_bytes_positive(values, shape):
    raw = b"".join(struct.pack("<d", v) for v in ind.scalars(values, shape))
    record = {
        "dtype": "<f8",
        "shape": shape,
        "values": values,
        "bytes_sha256": hashlib.sha256(raw).hexdigest(),
    }
    assert ind.array_bytes(record, shape) == raw


@pytest.mark.parametrize(
    "field,value",
    [
        ("dtype", ">f8"),
        ("shape", [2]),
        ("values", [True]),
        ("values", [float("nan")]),
        ("values", [[1.0]]),
        ("bytes_sha256", "0" * 64),
    ],
)
def test_float64_corruption_is_rejected(field, value):
    record = {
        "dtype": "<f8",
        "shape": [1],
        "values": [1.0],
        "bytes_sha256": hashlib.sha256(struct.pack("<d", 1.0)).hexdigest(),
    }
    record[field] = value
    with pytest.raises(ValueError):
        ind.array_bytes(record, [1])


def test_signed_zero_bytes_not_collapsed():
    record = {
        "dtype": "<f8",
        "shape": [1],
        "values": [-0.0],
        "bytes_sha256": hashlib.sha256(struct.pack("<d", 0.0)).hexdigest(),
    }
    with pytest.raises(ValueError, match="bytes"):
        ind.array_bytes(record, [1])


@pytest.mark.parametrize("voltage", [-0.12, -0.08, -0.0253, -0.006, 0.0, 0.06])
def test_gate_equations_in_si_units(voltage):
    targets = [
        1 / (1 + math.exp(-(voltage + 0.006) / 0.0064)),
        1 / (1 + math.exp((voltage + 0.0253) / 0.0035)),
    ]
    taus = [0.008330 - 0.1163 * voltage, 1.620 - 15.5 * voltage]
    initial, dt = [0.2, 0.6], 25e-6
    expected_rate = [(a - q) / tau for a, q, tau in zip(targets, initial, taus, strict=True)]
    ind.near(ind.gate_values(voltage, initial), expected_rate, 1e-12)
    expected_step = [
        (q + dt * a / tau) / (1 + dt / tau)
        for a, q, tau in zip(targets, initial, taus, strict=True)
    ]
    ind.near(ind.gate_values(voltage, initial, dt), expected_step, 1e-15)


@pytest.mark.parametrize(
    "voltage,inside,outside,permeability",
    [
        (0, 140, 4, 1e-8),
        (0, 4, 140, 1e-8),
        (-0.08, 140, 4, 1e-8),
        (0.03, 140, 4, 1e-8),
        (-0.08, 140, 4, 0),
    ],
)
def test_ghk_sign_and_zero_limit(voltage, inside, outside, permeability):
    constants = {"F": 96485.33212331001, "R": 8.31446261815324}
    x = constants["F"] * voltage / (constants["R"] * 298.15)
    expected = (
        permeability * (outside - inside)
        if x == 0
        else permeability * x * (outside - inside * math.exp(x)) / math.expm1(x)
    )
    ind.near(
        float(ind.inward_density(voltage, inside, outside, permeability, constants, 298.15)),
        expected,
        1e-20,
    )


@pytest.mark.parametrize(
    "corruption", ["actual", "expected", "unit", "missing", "duplicate", "nonfinite"]
)
def test_metric_reconciliation_catches_corruption(corruption):
    metrics = ind.Metrics()
    metrics.add("gate", 0.2, 0.2, "gate")
    rows = [
        {
            "id": "gate",
            "actual": 0.2,
            "expected": 0.2,
            "unit": "gate",
            "passed": True,
            "scaled_error": 0.0,
        }
    ]
    tolerances = {"gate": 2e-13, "relative": 2e-11}
    if corruption in ("actual", "expected"):
        rows[0][corruption] = 0.4
        assert metrics.audit(rows, tolerances)[0]["passed"] is False
        return
    if corruption == "unit":
        rows[0]["unit"] = "voltage_V"
    elif corruption == "missing":
        rows = []
    elif corruption == "duplicate":
        rows += rows
    else:
        rows[0]["actual"] = float("inf")
    with pytest.raises(ValueError):
        metrics.audit(rows, tolerances)


def test_tolerance_uses_expected_not_maximum_magnitude():
    assert ind.scaled(2.0, 0.0, 0.25, 0.5) == 8.0


def coupled_parameters():
    return {
        "F": 96485.33212331001,
        "R": 8.31446261815324,
        "temperature_K": 298.15,
        "volume_pL": [1.0, 2.0],
        "area_m2": [1e-9, 2e-9],
        "cm_F_per_m2": 0.01,
        "initial_K_fmol": [140.0, 280.0],
        "outside_volume_pL": 8.0,
        "outside_K_fmol": 32.0,
        "initial_voltage_V": [-0.04, -0.06],
        "channel_enabled": [True, True],
        "Pmax_m_per_s": [1e-8, 1e-8],
    }


def test_shared_bath_feedback_without_cell_state_injection():
    p = coupled_parameters()
    a = ready.vector_field(p, [0.0, 0.0], [0.2, 0.3], [0.6, 0.4])
    b = ready.vector_field(p, [-1e-5, 0.0], [0.2, 0.3], [0.6, 0.4])
    assert b["outside_K_mM"] > a["outside_K_mM"]
    assert b["voltage_V"][0] < a["voltage_V"][0]
    assert b["voltage_V"][1] == a["voltage_V"][1]
    assert b["inward_K_fmol_per_s"][1] != a["inward_K_fmol_per_s"][1]
    assert b["outside_K_fmol_per_s"] == -math.fsum(b["inward_K_fmol_per_s"])


def test_equal_open_probability_does_not_erase_hidden_gates():
    p = coupled_parameters()
    a = ready.vector_field(p, [0.0, 0.0], [0.2, 0.2], [0.6, 0.6])
    b = ready.vector_field(p, [0.0, 0.0], [0.3, 0.3], [0.4, 0.4])
    assert a["permeability_m_per_s"] == b["permeability_m_per_s"]
    assert a["inward_K_fmol_per_s"] == b["inward_K_fmol_per_s"]
    assert a["gate_rate_per_s"] != b["gate_rate_per_s"]


def test_blocked_gates_keep_evolving():
    p = coupled_parameters()
    p["Pmax_m_per_s"] = [0.0, 0.0]
    result = ready.vector_field(p, [0.0, 0.0], [0.2, 0.2], [0.6, 0.6])
    assert result["inward_K_fmol_per_s"] == [0.0, 0.0]
    assert all(v != 0 for values in result["gate_rate_per_s"] for v in values)


@pytest.mark.parametrize(
    "case",
    [
        "temperature",
        "absent_state",
        "nonboolean_mask",
        "empty_bath",
        "negative_volume",
        "mismatched_axes",
    ],
)
def test_continuous_reference_rejects_out_of_scope_inputs(case):
    p, q = coupled_parameters(), [0.0, 0.0]
    if case == "temperature":
        p["temperature_K"] = 310.0
    elif case == "absent_state":
        p["channel_enabled"][0] = False
    elif case == "nonboolean_mask":
        p["channel_enabled"][0] = 1
    elif case == "empty_bath":
        q = [32.0, 0.0]
    elif case == "negative_volume":
        p["volume_pL"][0] = -1.0
    else:
        q = [0.0]
    with pytest.raises(ValueError):
        ready.vector_field(p, q, [0.2, 0.2], [0.6, 0.6])


@pytest.mark.parametrize(
    "case", ["raw_clock", "steps", "reservation", "integration", "convergence"]
)
def test_readiness_resource_corruption(saved, case):
    record = copy.deepcopy(saved["cells"]["records"][0])
    definition = saved["definitions"][record["id"]]
    if case == "raw_clock":
        record["grid_s"][1] = 25e-6
    elif case == "steps":
        record["steps"] += 1
    elif case == "reservation":
        record["estimated_trace_bytes"] -= 1
    elif case == "integration":
        record["integration_executed"] = True
    else:
        record["convergence_qualified"] = True
    with pytest.raises(ValueError):
        ready.resources(definition, record)


@pytest.mark.parametrize(
    "case",
    ["initial_padding", "rhs_padding", "missing_state", "wrong_gate", "active_leak", "bath_charge"],
)
def test_full_state_corruption(saved, case):
    record = copy.deepcopy(
        next(v for v in saved["cells"]["records"] if v["id"] == "active_channel/dt_5e-05")
    )
    definition = copy.deepcopy(saved["definitions"][record["id"]])
    if case == "initial_padding":
        record["initial_state"]["gate"][0][-1] = 0.2
    elif case == "rhs_padding":
        record["initial_rhs"]["amount_increment"][1][-1] = 1e-25
    elif case == "missing_state":
        record["initial_state"].pop("junction_gate")
    elif case == "wrong_gate":
        record["initial_state"]["gate"][0][0] = 0.3
    elif case == "active_leak":
        record["initial_rhs"]["leak_transferred"][1][0] = 0.001
    else:
        definition["model"]["extracellular"]["fixed_charge_equivalent_fmol"] += 1.0
    with pytest.raises(ValueError):
        ready.state_contract(record, definition, record["independent_initial_rates"], True)


@pytest.mark.parametrize("case", ["missing_history", "bytes", "sample_count", "raw_final"])
def test_native_array_contract_rejects_corruption(saved, case):
    row = copy.deepcopy(saved["native"]["rows"]["active_channel/observed"])
    if case == "missing_history":
        row["histories"].pop("cc_time")
    elif case == "bytes":
        row["final_arrays"]["channel/m"]["bytes_sha256"] = "0" * 64
    elif case == "sample_count":
        row["histories"]["time"]["shape"] = [8]
    else:
        row["final"]["physical"]["voltage_V"][0] += 0.001
    with pytest.raises(ValueError):
        ind.array_contract(row)


def test_nonuniform_hidden_state_cannot_be_averaged(saved):
    g = saved["native"]["rows"]["active_channel/observed"]["geometry"]
    values = [0.2] * 30
    values[0] = 0.3
    with pytest.raises(ValueError, match="Nonuniform"):
        ind.owner_values(values, g)


def test_changed_loop_entry_partial_is_rejected(saved, monkeypatch):
    original_read = c.read
    path = ctx.CAPTURE / "native/active_channel/observed/loop-entry.json"
    entry = copy.deepcopy(original_read(path))
    entry["calls"]["loop_return"] = 1
    monkeypatch.setattr(c, "read", lambda p: entry if p == path else original_read(p))
    with pytest.raises(ValueError, match="Loop-entry"):
        ctx.partials(ctx.CAPTURE, saved["native"])


def test_capsule_corruption_rejected(tmp_path):
    with zipfile.ZipFile(tmp_path / "sources.zip", "x") as archive:
        archive.writestr("input.py", "changed")
    with pytest.raises(ValueError, match="bytes"):
        job.capsule_matches(tmp_path, {"input.py": hashlib.sha256(b"original").hexdigest()})


def test_existing_output_is_never_reused(tmp_path):
    with pytest.raises(ValueError, match="fresh"):
        job.register(ctx.CAPTURE, tmp_path / "not-used.xml")


def test_plan_resources_and_source_scope():
    plan = c.read(ctx.PLAN)
    ctx.validate_plan(plan)
    assert len(ctx.sources()) == 101
    assert not any(name.startswith("src/") for name in ctx.NEW_SOURCES)
    assert plan["max_artifact_bytes"] == 64 * 1024**2


@pytest.mark.parametrize(
    "key,value",
    [
        ("expected_comparisons", 348),
        ("precision_digits", 40),
        ("automatic_followup", True),
        ("simulators_rerun", True),
        ("max_artifact_bytes", 1024),
    ],
)
def test_mutated_plan_rejected(key, value):
    plan = c.read(ctx.PLAN)
    plan[key] = value
    with pytest.raises(ValueError):
        ctx.validate_plan(plan)


@pytest.mark.parametrize("case", ["label", "elapsed", "order", "sampling", "paired_history"])
def test_native_clock_order_and_pair_corruption(saved, case):
    native = copy.deepcopy(saved["native"])
    row = native["rows"]["network_off/observed"]
    trace = row["trace"]
    if case == "label":
        trace["steps"][0]["raw_label_s"] = 25e-6
    elif case == "elapsed":
        trace["steps"][0]["after_elapsed_s"] = 0.0
    elif case == "order":
        trace["steps"][0]["order"] = list(reversed(trace["steps"][0]["order"]))
    elif case == "sampling":
        trace["sampled_indices"] = list(range(8))
    else:
        row["histories"]["time"]["values"][0] = 0.0
    with pytest.raises(ValueError):
        ind.native_metrics(saved["registration"], native, ind.Metrics())


def test_authentication_can_run_with_models_forbidden():
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); import loop_audit_context as c\n"
        "with c.model_fence():\n"
        "    data = c.load_capture()\n"
        "    assert len(data['hashes']) == 74\n"
        "print('model_free_authentication_pass')\n"
    )
    result = subprocess.run(
        [str(c.CELLS_PYTHON), "-B", "-c", code, str(HERE)],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "model_free_authentication_pass"
